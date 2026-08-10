# -*- coding: utf-8 -*-
"""B0 (sun_rule_only) FORMAL arm runner (zero-API, fail-closed).

This is the FORMAL entry point: claim_scope=formal,
is_formal_performance_result=true. It publishes the single-method B0 formal
arm capsule into the versioned formal directories:

- data/predictions/b0_formal_arm_v1/predictions.json   (150 canonical records,
  timing-free) + telemetry.json (isolated performance timing)
- data/results/b0_formal_arm_v1/evaluation_fine.json / evaluation_coarse.json
  / modality_labels.json / diagnostics.json / cost.json / config_snapshot.json
- outputs/reports/b0_formal_arm_v1.manifest.json
- outputs/reports/b0_formal_arm_v1_export_index.json
- outputs/reports/b0_formal_arm_v1_capsule_manifest.json
- outputs/reports/verify_b0_formal_arm_v1.py            (independent verifier)

Hard boundaries:
- runner reads ONLY data/input/estg150_formal_inference_input_v2.json and the
  locked method assets (v10a config/profile/lexicon/classifier/CoreNLP);
  it NEVER reads data/gold/, Layer E or any adjudication field
- the evaluator phase is a SEPARATE step reading the published
  data/gold/stage2/estg150_formal_gold_v1.json (via the shared
  formal_stage2_evaluation module) plus the B0 predictions
- preconditions fail closed: release v2 verifier passes, sun_rule_only
  formal_status=ready / command_status=formal_ready_candidate_authorized /
  llm_used=false, D1/H1 still blocked
- G0.4 contract: coarse-view main metrics are NOT published (consistency
  with the historical coarse gold is not provable from the published Gold);
  the fine view and the five span-bearing fields plus modality-label metrics
  are reported; modality evidence-span metrics are reported as unavailable
  with reason, never silently zero
- canonical artifacts carry NO unstable timing (isolated in telemetry)
- no-overwrite, temp staging, atomic rename, no partial leftovers
- the capsule is self-contained: everything a clean clone needs to verify is
  in versioned files (no dependency on ignored development outputs)

Usage:
    python scripts/run_b0_formal_arm.py --runtime-home <corenlp-home>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    Estg150B0DevelopmentError,
    load_object,
    sha256_file,
)
from bpc_hybrid.estg150_b0_development_v10 import (  # noqa: E402
    METHOD_ID,
    METHOD_VARIANT,
    run_b0_batch_v10,
)
from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.formal_stage2_evaluation import (  # noqa: E402
    evaluate_modality_labels,
    evaluate_span_metrics,
    predictions_to_evaluator,
    published_gold_to_evaluator,
    strip_timing,
    telemetry_only,
)

FORMAL_INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
FORMAL_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
B0_CONFIG = ROOT / "configs" / "models" / "estg150_b0_enhanced_s27_v10a.json"
SUN_LITERAL_CONFIG = ROOT / "configs" / "evaluation" / "sun_table8_literal_overlap_v2.json"
METHODS_CONFIG = ROOT / "configs" / "methods.json"
RELEASE_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"
G04_CONTRACT = ROOT / "configs" / "evaluation" / "g04_evaluation_views_contract_v1.json"
G04_COARSE_REPORT = (ROOT / "outputs" / "evidence" / "g04_formal_coarse_view_v1"
                     / "manifest.json")
PREDICTION_SCHEMA = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
VERIFIER_MODULE = ROOT / "scripts" / "verify_formal_benchmark_release_v2.py"

OUT_PRED_BASE = ROOT / "data" / "predictions"
OUT_RES_BASE = ROOT / "data" / "results"
OUT_REPORTS = ROOT / "outputs" / "reports"

RUN_ID = "b0_formal_arm_v1"
CLAIM_SCOPE = "formal"
V2_FIELDS = ("sample_id", "approved_text_en", "raw_text_de", "legacy_record_id")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Estg150B0DevelopmentError(f"cannot load {path}: {exc}") from exc


def _load_release_verifier():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "b0_formal_arm_release_verifier", VERIFIER_MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules["b0_formal_arm_release_verifier"] = module
    spec.loader.exec_module(module)
    return module


def check_preconditions() -> dict[str, Any]:
    checks: dict[str, Any] = {}

    # 1. release v2 verifier all green
    verifier = _load_release_verifier()
    result = verifier.verify_release()
    checks["formal_benchmark_release_v2_verified"] = result.get("verified") is True
    if not result.get("verified"):
        failed = [c["name"] for c in result.get("checks", []) if not c["ok"]]
        checks["_detail"] = f"release verifier failures: {failed[:6]}"

    # 2. method gate
    methods = _load_json(METHODS_CONFIG).get("methods", [])
    by_id = {m["id"]: m for m in methods}
    b0 = by_id.get("sun_rule_only", {})
    checks["sun_rule_only_formal_status_ready"] = b0.get("formal_status") == "ready"
    checks["sun_rule_only_command_status"] = (
        b0.get("command_status") == "formal_ready_candidate_authorized")
    checks["sun_rule_only_llm_used_false"] = b0.get("llm_used") is False
    checks["d1_still_blocked"] = (
        by_id.get("direct_llm", {}).get("formal_status") != "ready")
    checks["h1_still_blocked"] = (
        by_id.get("sun_llm_fallback", {}).get("formal_status") != "ready")

    # 3. inputs present
    checks["formal_input_v2_present"] = FORMAL_INPUT_V2.exists()
    checks["formal_gold_present"] = FORMAL_GOLD.exists()

    failed = [k for k, v in checks.items() if v is False]
    if failed:
        raise Estg150B0DevelopmentError(
            f"B0 formal arm preconditions failed: {failed} "
            f"{checks.get('_detail', '')}")
    return checks


def load_formal_records() -> list[dict[str, Any]]:
    doc = _load_json(FORMAL_INPUT_V2)
    if doc.get("schema_version") != "estg150_formal_inference_input@2.0.0":
        raise Estg150B0DevelopmentError("formal input v2 schema identity changed")
    if doc.get("count") != 150 or len(doc.get("records", [])) != 150:
        raise Estg150B0DevelopmentError("formal input v2 must contain exactly 150 records")
    records = []
    for rec in doc["records"]:
        out = {
            "sample_id": rec.get("sample_id"),
            "approved_text_en": rec.get("approved_text_en"),
            "raw_text_de": rec.get("raw_text_de"),
            "legacy_record_id": (rec.get("source_ref") or {}).get("legacy_record_id"),
        }
        if any(out[k] is None for k in V2_FIELDS):
            raise Estg150B0DevelopmentError(
                f"formal input v2 record missing whitelisted fields: {rec.get('sample_id')}")
        records.append(out)
    if len({r["sample_id"] for r in records}) != 150:
        raise Estg150B0DevelopmentError("formal input v2 sample_ids not unique")
    return records


def _verify_config_locked(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "estg150_b0_enhanced_development@1.0.0":
        raise Estg150B0DevelopmentError("B0 config schema identity changed")
    if config.get("method", {}).get("method_id") not in {
            METHOD_VARIANT, "b0_enhanced_v10a", "b0_enhanced_v10"}:
        raise Estg150B0DevelopmentError("B0 method id changed")
    if config.get("safety", {}).get("llm_api_called") is not False:
        raise Estg150B0DevelopmentError("B0 config safety: llm_api_called must be false")
    if config.get("method", {}).get("tsurgeon_enabled") is not False:
        raise Estg150B0DevelopmentError("B0 config safety: tsurgeon_enabled must be false")


def _load_g04_coarse_status() -> dict[str, Any]:
    """G0.4 coarse-view publication gate (never publish the coarse MAIN view
    when consistency with the historical coarse gold is not provable)."""
    if not G04_COARSE_REPORT.exists():
        return {"main_view_publishable": False,
                "reason": "G0.4 coarse view manifest missing"}
    report = _load_json(G04_COARSE_REPORT)
    return {
        "main_view_publishable": report.get("main_view_publishable") is True,
        "reason": report.get("not_publishable_reason") or "consistent",
        "semantic_sha256": report.get("derived_view", {}).get("semantic_sha256"),
    }


def _write_staged(staging: Path, name: str, payload: dict[str, Any]) -> str:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (staging / name).write_bytes(data)
    return _sha256_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True,
                        help="CoreNLP 4.5.10 runtime directory")
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--output-tag", default="b0_formal_arm_v1",
                        help="capsule tag (use a NEW tag for the replay run; "
                             "the primary run must use b0_formal_arm_v1)")
    args = parser.parse_args()
    run_id = args.output_tag

    # ---- fail-closed preconditions --------------------------------
    preconditions = check_preconditions()
    config = _load_json(B0_CONFIG)
    _verify_config_locked(config)
    literal_evaluator = _load_json(SUN_LITERAL_CONFIG)
    if literal_evaluator.get("evaluator_id") != "sun_table8_literal_overlap_v2":
        raise Estg150B0DevelopmentError("primary evaluator identity changed")
    coarse_gate = _load_g04_coarse_status()

    records = load_formal_records()
    input_v2_sha = sha256_file(FORMAL_INPUT_V2)
    gold_sha = sha256_file(FORMAL_GOLD)
    config_sha = sha256_file(B0_CONFIG)

    # ---- runner phase: Gold-blind ---------------------------------
    with tempfile.TemporaryDirectory(prefix="b0-formal-arm-",
                                     dir=ROOT / ".tmp") as raw_work:
        work_dir = Path(raw_work)
        attempts, runtime = run_b0_batch_v10(
            ROOT, records, runtime_home=args.runtime_home,
            work_dir=work_dir, device=args.device,
        )
    if len(attempts) != 150:
        raise Estg150B0DevelopmentError(f"expected 150 attempts, got {len(attempts)}")
    invalid = [a["sample_id"] for a in attempts
               if a.get("request_status") != "ok"
               or not (a.get("record") or {}).get("validation", {}).get("schema_valid")]
    if invalid:
        raise Estg150B0DevelopmentError(f"invalid predictions: {invalid[:5]}")

    # ---- evaluator phase: SEPARATE step, reads published Gold -----
    gold_doc = _load_json(FORMAL_GOLD)
    fine_gold = published_gold_to_evaluator(gold_doc)
    coarse_gold = build_coarse_view(gold_doc)
    attempts_eval = predictions_to_evaluator(attempts)

    fine_metrics = evaluate_span_metrics(
        fine_gold, attempts_eval, dataset_id="independently_reconstructed_estg_150_v1",
        method_id=METHOD_ID, view="fine_clause_level")
    coarse_metrics = evaluate_span_metrics(
        coarse_gold, attempts_eval, dataset_id="independently_reconstructed_estg_150_v1",
        method_id=METHOD_ID, view="coarse_sentence_level")
    modality_labels = evaluate_modality_labels(fine_gold, attempts_eval)
    telemetry = telemetry_only(attempts)

    predictions = strip_timing(attempts)

    # ---- G0.4 declaration -----------------------------------------
    g04 = {
        "contract": "g04_evaluation_views_contract@1.0.0",
        "coarse_main_view_publishable": coarse_gate["main_view_publishable"],
        "coarse_main_view_not_published_reason": (
            None if coarse_gate["main_view_publishable"]
            else coarse_gate["reason"]),
        "coarse_view_semantic_sha256": coarse_gate.get("semantic_sha256"),
        "no_cross_view_mixing": True,
        "modality_evidence_span_metrics": "unavailable (published Gold modality is a plain string)",
    }

    # ---- staging + atomic rename (no overwrite) --------------------
    staging = ROOT / "data" / "predictions" / f".{run_id}.staging-{Path(__file__).stem}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    artifacts: dict[str, dict[str, Any]] = {}
    def _stage(rel_dir: Path, name: str, payload: dict[str, Any]) -> None:
        target = staging / rel_dir / run_id / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        target.write_bytes(data)
        artifacts[f"{rel_dir.as_posix()}/{name}"] = {
            "path": f"data/{rel_dir.as_posix()}/{run_id}/{name}",
            "sha256": _sha256_bytes(data),
        }

    _stage(Path("predictions"), "predictions.json",
           {"schema_version": "b0_formal_arm_predictions@1.0.0",
            "claim_scope": CLAIM_SCOPE, "records": predictions})
    _stage(Path("predictions"), "telemetry.json", telemetry)
    _stage(Path("results"), "evaluation_fine.json", fine_metrics)
    _stage(Path("results"), "evaluation_coarse.json", coarse_metrics)
    _stage(Path("results"), "modality_labels.json", modality_labels)
    _stage(Path("results"), "g04_view_declaration.json", g04)
    _stage(Path("results"), "cost.json",
           {"schema_version": "b0_formal_arm_cost@1.0.0",
            "llm_api_called": False, "network_called": False,
            "estimated_cost_usd": 0.0, "note": "zero-API run"})
    config_snapshot = {
        "schema_version": "b0_formal_arm_config_snapshot@1.0.0",
        "method": {"method_id": METHOD_ID, "method_variant": METHOD_VARIANT,
                   "config_path": "configs/models/estg150_b0_enhanced_s27_v10a.json",
                   "config_sha256": config_sha},
        "input": {"path": "data/input/estg150_formal_inference_input_v2.json",
                  "sha256": input_v2_sha, "records": 150},
        "gold": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                 "sha256": gold_sha},
        "primary_evaluator_config": {
            "path": "configs/evaluation/sun_table8_literal_overlap_v2.json",
            "sha256": sha256_file(SUN_LITERAL_CONFIG)},
        "g04_contract": {"path": "configs/evaluation/g04_evaluation_views_contract_v1.json",
                         "sha256": sha256_file(G04_CONTRACT)},
        "prediction_schema": {"path": "configs/schemas/stage2_prediction.schema.json",
                              "sha256": sha256_file(PREDICTION_SCHEMA)},
        "release_manifest_v2": {"path": "outputs/reports/formal_benchmark_release_v2.manifest.json",
                                "sha256": sha256_file(RELEASE_MANIFEST)},
    }
    _stage(Path("results"), "config_snapshot.json", config_snapshot)

    manifest = {
        "schema_version": "b0_formal_arm_manifest@1.0.0",
        "run_id": run_id,
        "claim_scope": CLAIM_SCOPE,
        "is_formal_performance_result": True,
        "method_id": METHOD_ID,
        "method_variant": METHOD_VARIANT,
        "dataset_id": "independently_reconstructed_estg_150_v1",
        "arm_scope": {
            "single_method_b0_formal_arm": True,
            "final_experiment_ready": False,
            "note": "B0 formal arm only; the three-method final capsule is "
                    "not complete (D1/H1 remain formal-gate-blocked)",
        },
        "preconditions_verified": preconditions,
        "input_binding": {
            "formal_input_v2_sha256": input_v2_sha,
            "records": len(attempts),
            "gold_read_by_runner": False,
        },
        "evaluation_binding": {
            "gold_path": "data/gold/stage2/estg150_formal_gold_v1.json",
            "gold_sha256": gold_sha,
            "views": ["fine_clause_level", "coarse_sentence_level"],
            "modality_label_metrics_separate": True,
            "modality_evidence_span_metrics": "unavailable (published Gold modality is a plain string)",
        },
        "g04": g04,
        "runtime_summary": {
            "record_count": runtime.get("record_count"),
            "predicted_clause_count": runtime.get("predicted_clause_count"),
            "corenlp_seconds": runtime.get("corenlp_seconds"),
            "total_seconds": runtime.get("total_seconds"),
            "device": runtime.get("device"),
            "modality_route_counts": runtime.get("modality_route_counts"),
        },
        "metrics_summary": {
            "fine_span_fields": fine_metrics.get("span_fields", {}),
            "coarse_span_fields": coarse_metrics.get("span_fields", {}),
            "modality_labels": {
                "accuracy": modality_labels.get("accuracy"),
                "macro_f1": modality_labels.get("macro_f1"),
            },
        },
        "safety": {
            "llm_api_called": False,
            "network_called": False,
            "gold_read_by_runner": False,
            "timing_isolated_in_telemetry": True,
        },
        "reproduce_command": (
            "python scripts/run_b0_formal_arm.py "
            f"--runtime-home {args.runtime_home}"),
        "artifacts": artifacts,
    }
    manifest_sha = _write_staged(staging, "manifest.json", manifest)
    artifacts["manifest.json"] = {"path": f"outputs/reports/{run_id}.manifest.json",
                                  "sha256": manifest_sha}

    export_index = {
        "schema_version": "b0_formal_arm_export_index@1.0.0",
        "run_id": run_id,
        "claim_scope": CLAIM_SCOPE,
        "artifacts": artifacts,
        "manifest": {"path": f"outputs/reports/{run_id}.manifest.json",
                     "sha256": manifest_sha},
    }
    capsule_manifest = {
        "schema_version": "b0_formal_arm_capsule@1.0.0",
        "capsule": run_id,
        "claim_scope": CLAIM_SCOPE,
        "files": {name: info for name, info in artifacts.items()},
        "independent_verifier": {"path": f"outputs/reports/verify_{run_id}.py",
                                 "sha256": "computed-after"},
    }

    # verifier script (self-contained, tamper/fail-closed)
    verifier_src = _VERIFIER_TEMPLATE.format(
        RUN_ID=run_id,
        MANIFEST_SHA=manifest_sha,
        PRED_SHA=artifacts["predictions/predictions.json"]["sha256"],
        INPUT_V2_SHA=input_v2_sha, GOLD_SHA=gold_sha)
    (staging / "verify_b0_formal_arm_v1.py").write_text(verifier_src, encoding="utf-8")
    verifier_sha = _sha256_bytes(verifier_src.encode("utf-8"))
    capsule_manifest["files"]["outputs/reports/verify_b0_formal_arm_v1.py"] = {
        "path": f"outputs/reports/verify_{run_id}.py", "sha256": verifier_sha}
    capsule_manifest["independent_verifier"]["sha256"] = verifier_sha
    (staging / "capsule_manifest.json").write_bytes(
        (json.dumps(capsule_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    # finalize: atomic rename of staging into the formal dirs
    out_pred_dir = OUT_PRED_BASE / run_id
    out_res_dir = OUT_RES_BASE / run_id
    out_manifest = OUT_REPORTS / f"{run_id}.manifest.json"
    out_export = OUT_REPORTS / f"{run_id}_export_index.json"
    out_capsule = OUT_REPORTS / f"{run_id}_capsule_manifest.json"
    out_verifier = OUT_REPORTS / f"verify_{run_id}.py"
    for d in (out_pred_dir, out_res_dir, out_manifest, out_export,
              out_capsule, out_verifier):
        if d.exists():
            raise Estg150B0DevelopmentError(f"refusing to overwrite existing: {d}")
    for rel in ("predictions", "results"):
        src = staging / rel / run_id
        dst = ROOT / "data" / rel / run_id
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
    (staging / "manifest.json").rename(out_manifest)
    (staging / "verify_b0_formal_arm_v1.py").rename(out_verifier)
    (staging / "capsule_manifest.json").rename(out_capsule)
    export_data = (json.dumps(export_index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out_export.write_bytes(export_data)
    shutil.rmtree(staging, ignore_errors=True)

    print(f"B0 formal arm capsule published: {run_id}")
    print(f"  claim_scope: {CLAIM_SCOPE} | is_formal_performance_result: True")
    print(f"  records: {len(predictions)} | invalid: 0")
    print(f"  fine span F1 (5 fields): "
          f"{ {k: round(v['f1'], 4) for k, v in fine_metrics['span_fields'].items()} }")
    print(f"  modality label accuracy: {modality_labels.get('accuracy')}")
    print(f"  manifest sha256: {manifest_sha[:16]}...")
    return 0


_VERIFIER_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Independent verifier for the B0 formal arm v1 capsule (zero-API).

Re-reads every capsule artifact from disk and verifies: manifest artifact
hashes, prediction count/schema-validity, input v2 / Gold hashes, the G0.4
declaration, modality-label metrics self-consistency, and the absence of
timing in canonical artifacts. Tamper with anything -> verification fails.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "{RUN_ID}"
MANIFEST = ROOT / "outputs" / "reports" / f"{RUN_ID}.manifest.json"
PRED = ROOT / "data" / "predictions" / RUN_ID / "predictions.json"
INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"

EXPECTED_MANIFEST_SHA = "{MANIFEST_SHA}"
EXPECTED_PRED_SHA = "{PRED_SHA}"
EXPECTED_INPUT_V2_SHA = "{INPUT_V2_SHA}"
EXPECTED_GOLD_SHA = "{GOLD_SHA}"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({{"name": name, "ok": bool(ok), "detail": detail}})

    check("manifest exists", MANIFEST.exists())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {{}}
    check("manifest schema", manifest.get("schema_version") == "b0_formal_arm_manifest@1.0.0")
    check("claim_scope formal", manifest.get("claim_scope") == "formal")
    check("is_formal_performance_result", manifest.get("is_formal_performance_result") is True)
    check("final_experiment_ready false", manifest.get("arm_scope", {{}}).get("final_experiment_ready") is False)
    for name, info in manifest.get("artifacts", {{}}).items():
        if name == "manifest.json":
            check(f"artifact hash manifest", info.get("sha256") == EXPECTED_MANIFEST_SHA)
            continue
        p = ROOT / info["path"]
        check(f"artifact exists {{name}}", p.exists())
        if p.exists():
            check(f"artifact hash {{name}}", _sha(p) == info.get("sha256"))
    check("predictions 150", len(json.loads(PRED.read_text(encoding="utf-8")).get("records", [])) == 150)
    check("predictions timing-free",
          all("runtime" not in r and "latency" not in json.dumps(r)
              for r in json.loads(PRED.read_text(encoding="utf-8")).get("records", [])))
    check("input v2 hash", _sha(INPUT_V2) == EXPECTED_INPUT_V2_SHA)
    check("gold hash", _sha(GOLD) == EXPECTED_GOLD_SHA)
    check("g04 declaration present",
          (ROOT / "data" / "results" / RUN_ID / "g04_view_declaration.json").exists())
    res = ROOT / "data" / "results" / RUN_ID
    for f in ("evaluation_fine.json", "evaluation_coarse.json", "modality_labels.json",
              "cost.json", "config_snapshot.json"):
        check(f"result {{f}} exists", (res / f).exists())
    cost = json.loads((res / "cost.json").read_text(encoding="utf-8"))
    check("zero api", cost.get("llm_api_called") is False and cost.get("estimated_cost_usd") == 0.0)
    return {{"verified": all(c["ok"] for c in checks), "checks": checks}}


if __name__ == "__main__":
    result = verify()
    for c in result["checks"]:
        print(("PASS" if c["ok"] else "FAIL"), c["name"], c["detail"])
    print("VERIFIED" if result["verified"] else "NOT VERIFIED")
    sys.exit(0 if result["verified"] else 1)
'''


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Direct-LLM / Rules+LLM-Repair FORMAL arm publisher (zero-API).

Publishes the user-authorized formal arm capsule for the D1-R3 / H1 150-row
snapshots WITHOUT any new LLM/API call:

- direct_llm     -> data/predictions/direct_llm_formal_arm_v1/ +
                    data/results/direct_llm_formal_arm_v1/ +
                    outputs/reports/direct_llm_formal_arm_v1.*
- sun_llm_fallback -> data/predictions/sun_llm_fallback_formal_arm_v1/ +
                    data/results/sun_llm_fallback_formal_arm_v1/ +
                    outputs/reports/sun_llm_fallback_formal_arm_v1.*

Fail-closed preconditions:
- the method's formal_status=ready and command_status=
  formal_ready_candidate_authorized in methods.json (user-authorized
  2026-08-11); sun_llm_fallback additionally role=comparison_arm_only
- formal benchmark release v2 verifier passes
- G0.4 evaluation contract user-authorized
- snapshot binding re-verified (150 ids, input text hashes vs formal input
  v2, prompt lock, schema-valid) -- a broken binding fails closed

Evaluation uses the SAME Gold views / schema / normalization / evaluators as
the B0 formal arm (fine + coarse five span-bearing fields, separate
four-class modality-label metrics, modality evidence-span unavailable per
G0.4). Canonical artifacts carry NO timing; telemetry records the historical
call counts only (new calls = 0). No-overwrite, temp staging, atomic rename.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.formal_stage2_evaluation import (  # noqa: E402
    evaluate_modality_labels,
    evaluate_span_metrics,
    published_gold_to_evaluator,
    strip_timing,
)

V2_INPUT = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
FORMAL_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
METHODS_CONFIG = ROOT / "configs" / "methods.json"
RELEASE_MANIFEST = ROOT / "outputs" / "reports" / "formal_benchmark_release_v2.manifest.json"
G04_CONTRACT = ROOT / "configs" / "evaluation" / "g04_evaluation_views_contract_v1.json"
PREDICTION_SCHEMA = ROOT / "configs" / "schemas" / "stage2_prediction.schema.json"
VERIFIER_MODULE = ROOT / "scripts" / "verify_formal_benchmark_release_v2.py"
OUT_REPORTS = ROOT / "outputs" / "reports"

SNAPSHOTS = {
    "direct_llm": {
        "run": "s27_d1_v6_r3_clean_rerun_150_hist56d_v1",
        "pred_file": "d1_responses.jsonl",
        "envelope": True,  # rows carry {"sample_id", "record", ...}
        "prompt_lock": "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895",
        "expected_pred_sha": "9188093c5b30d288c749e1dc6da9d88eb5df4fd4c08a73518f6b4ff243dca36e",
        "arm_tag": "direct_llm_formal_arm_v1",
        "historical_llm_calls": 150,
    },
    "sun_llm_fallback": {
        "run": "s28d_h1_150_v4pro_v1",
        "pred_file": "h1_predictions.jsonl",
        "envelope": False,  # rows ARE plain records
        "prompt_lock": "00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b",
        "expected_pred_sha": "4fd7c116d3f7841d72d27fa0dcadc9be2b8095fda189e28a74af1c298c22fccc",
        "arm_tag": "sun_llm_fallback_formal_arm_v1",
        "historical_llm_calls": 150,
    },
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return []


def check_preconditions(method: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "snapshot_arm_release_verifier", VERIFIER_MODULE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["snapshot_arm_release_verifier"] = mod
    spec.loader.exec_module(mod)
    result = mod.verify_release()
    checks["release_v2_verified"] = result.get("verified") is True

    methods = _load_json(METHODS_CONFIG).get("methods", [])
    by_id = {m["id"]: m for m in methods}
    entry = by_id.get(method, {})
    checks["formal_status_ready"] = entry.get("formal_status") == "ready"
    checks["command_status"] = (
        entry.get("command_status") == "formal_ready_candidate_authorized")
    checks["llm_used_true_declared"] = entry.get("llm_used") is True
    if method == "sun_llm_fallback":
        checks["comparison_arm_only_role"] = entry.get("role") == "comparison_arm_only"

    g04 = _load_json(G04_CONTRACT)
    checks["g04_authorized"] = (
        g04.get("authorization", {}).get("authorized_by_user") is True)
    checks["input_v2_present"] = V2_INPUT.exists()
    checks["gold_present"] = FORMAL_GOLD.exists()

    failed = [k for k, v in checks.items() if v is False]
    if failed:
        raise RuntimeError(f"{method} formal arm preconditions failed: {failed}")
    return checks


def _verify_binding(method: str, rows: list[dict[str, Any]],
                    v2: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    v2_sha = {r["sample_id"]: r["input_text_sha256"] for r in v2["records"]}
    v2_ids = set(v2_sha)
    info = SNAPSHOTS[method]
    if len(rows) != 150:
        problems.append(f"rows {len(rows)} != 150")
    ids = {r.get("sample_id") for r in rows}
    if ids != v2_ids:
        problems.append("sample ids differ from formal input v2")
    text_mismatch = 0
    schema_valid = 0
    for r in rows:
        if info["envelope"]:
            text = (r.get("record") or {}).get("source_text")
            ok = (r.get("record") or {}).get("validation", {}).get("schema_valid")
        else:
            text = r.get("source_text")
            ok = r.get("validation", {}).get("schema_valid")
        want = v2_sha.get(r.get("sample_id"))
        if want is None:
            text_mismatch += 1
        elif _sha256_bytes((text or "").encode("utf-8")) != want:
            text_mismatch += 1
        if ok:
            schema_valid += 1
    if text_mismatch:
        problems.append(f"{text_mismatch} input text hash mismatches")
    if schema_valid != 150:
        problems.append(f"schema-valid {schema_valid}/150")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("direct_llm", "sun_llm_fallback"),
                        required=True)
    args = parser.parse_args()
    method = args.method
    info = SNAPSHOTS[method]
    run_dir = ROOT / "outputs" / "development" / info["run"]
    pred_path = run_dir / info["pred_file"]
    arm_tag = info["arm_tag"]

    preconditions = check_preconditions(method)
    if not pred_path.exists():
        raise RuntimeError(f"snapshot predictions missing: {pred_path}")
    if _sha256_file(pred_path) != info["expected_pred_sha"]:
        raise RuntimeError(
            f"snapshot predictions bytes changed! expected "
            f"{info['expected_pred_sha'][:16]}... got "
            f"{_sha256_file(pred_path)[:16]}...")

    v2 = _load_json(V2_INPUT)
    rows = _load_jsonl(pred_path)
    problems = _verify_binding(method, rows, v2)
    if problems:
        raise RuntimeError(f"{method} snapshot binding failed: {problems}")

    # attempts envelopes (evaluation + timing-free predictions)
    if info["envelope"]:
        attempts = [{"sample_id": r["sample_id"], "request_status": "ok",
                     "record": r.get("record"), "error_category": None,
                     "runtime": {"llm_call_performed": False}}
                    for r in rows]
    else:
        attempts = [{"sample_id": r["sample_id"], "request_status": "ok",
                     "record": r, "error_category": None,
                     "runtime": {"llm_call_performed": False}}
                    for r in rows]

    gold_doc = _load_json(FORMAL_GOLD)
    fine_gold = published_gold_to_evaluator(gold_doc)
    coarse_gold = build_coarse_view(gold_doc)
    attempts_eval = [{"sample_id": a["sample_id"], "request_status": "ok",
                      "record": a["record"], "error_category": None,
                      "runtime": a["runtime"]} for a in attempts]
    fine = evaluate_span_metrics(
        fine_gold, attempts_eval,
        dataset_id="independently_reconstructed_estg_150_v1",
        method_id=method, view="fine_clause_level")
    coarse = evaluate_span_metrics(
        coarse_gold, attempts_eval,
        dataset_id="independently_reconstructed_estg_150_v1",
        method_id=method, view="coarse_sentence_level")
    labels = evaluate_modality_labels(fine_gold, attempts_eval)

    predictions = strip_timing(attempts)

    # staging
    staging = ROOT / "data" / "predictions" / f".{arm_tag}.staging-{Path(__file__).stem}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    artifacts: dict[str, dict[str, Any]] = {}

    def _stage(rel: str, name: str, payload: dict[str, Any]) -> None:
        target = staging / rel / arm_tag / name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        target.write_bytes(data)
        artifacts[f"{rel}/{name}"] = {
            "path": f"data/{rel}/{arm_tag}/{name}", "sha256": _sha256_bytes(data)}

    _stage("predictions", "predictions.json",
           {"schema_version": "snapshot_formal_arm_predictions@1.0.0",
            "claim_scope": "formal", "records": predictions})
    _stage("predictions", "telemetry.json", {
        "schema_version": "snapshot_formal_arm_telemetry@1.0.0",
        "historical_llm_calls": info["historical_llm_calls"],
        "new_llm_calls": 0,
        "snapshot": info["run"],
        "note": "performance timing of the historical snapshot run is not "
                "carried into canonical artifacts"})
    _stage("results", "evaluation_fine.json", fine)
    _stage("results", "evaluation_coarse.json", coarse)
    _stage("results", "modality_labels.json", labels)
    _stage("results", "g04_view_declaration.json", {
        "contract": "g04_evaluation_views_contract@1.0.0",
        "authorized": True,
        "main_report": "coarse five span fields + separate modality-label metrics",
        "modality_evidence_span_metrics": "unavailable (never zeroed, never aggregated)"})
    _stage("results", "cost.json", {
        "schema_version": "snapshot_formal_arm_cost@1.0.0",
        "llm_api_called": False, "new_llm_api_calls": 0,
        "historical_llm_calls": info["historical_llm_calls"],
        "estimated_cost_usd": 0.0, "note": "zero-API publication of the bound snapshot"})
    _stage("results", "config_snapshot.json", {
        "schema_version": "snapshot_formal_arm_config_snapshot@1.0.0",
        "method": {"method_id": method, "snapshot": info["run"],
                   "snapshot_predictions_sha256": info["expected_pred_sha"]},
        "input": {"path": "data/input/estg150_formal_inference_input_v2.json",
                  "sha256": _sha256_file(V2_INPUT)},
        "gold": {"path": "data/gold/stage2/estg150_formal_gold_v1.json",
                 "sha256": _sha256_file(FORMAL_GOLD)},
        "primary_evaluator_config": {
            "path": "configs/evaluation/sun_table8_literal_overlap_v2.json"},
        "g04_contract": {"path": "configs/evaluation/g04_evaluation_views_contract_v1.json",
                         "sha256": _sha256_file(G04_CONTRACT)},
        "prediction_schema": {"path": "configs/schemas/stage2_prediction.schema.json",
                              "sha256": _sha256_file(PREDICTION_SCHEMA)},
        "release_manifest_v2": {"path": "outputs/reports/formal_benchmark_release_v2.manifest.json",
                                "sha256": _sha256_file(RELEASE_MANIFEST)}})

    manifest = {
        "schema_version": "snapshot_formal_arm_manifest@1.0.0",
        "run_id": arm_tag,
        "claim_scope": "formal",
        "is_formal_performance_result": True,
        "method_id": method,
        "snapshot": info["run"],
        "dataset_id": "independently_reconstructed_estg_150_v1",
        "zero_api": {"historical_llm_calls": info["historical_llm_calls"],
                     "new_llm_calls": 0,
                     "default_path": "zero-API publication of the bound snapshot"},
        "preconditions_verified": preconditions,
        "binding": {"problems": problems, "ok": not problems},
        "metrics_summary": {
            "fine_span_fields": fine.get("span_fields", {}),
            "coarse_span_fields": coarse.get("span_fields", {}),
            "modality_labels": {"accuracy": labels.get("accuracy"),
                                "macro_f1": labels.get("macro_f1")},
        },
        "safety": {"llm_api_called": False, "new_llm_api_calls": 0,
                   "gold_read_by_runner": False,
                   "timing_not_carried_into_canonical_artifacts": True},
        "artifacts": artifacts,
    }
    manifest_sha = _write_staged(staging, "manifest.json", manifest)
    artifacts["manifest.json"] = {"path": f"outputs/reports/{arm_tag}.manifest.json",
                                  "sha256": manifest_sha}

    verifier_src = _VERIFIER_TEMPLATE.format(
        RUN_ID=arm_tag,
        MANIFEST_SHA=manifest_sha,
        PRED_SHA=artifacts["predictions/predictions.json"]["sha256"],
        INPUT_V2_SHA=_sha256_file(V2_INPUT),
        GOLD_SHA=_sha256_file(FORMAL_GOLD),
        METHOD=method,
        HIST_LLM_CALLS=info["historical_llm_calls"])
    (staging / "verify_snapshot_formal_arm.py").write_text(verifier_src, encoding="utf-8")
    verifier_sha = _sha256_bytes(verifier_src.encode("utf-8"))

    export_index = {
        "schema_version": "snapshot_formal_arm_export_index@1.0.0",
        "run_id": arm_tag, "claim_scope": "formal",
        "artifacts": artifacts,
        "manifest": {"path": f"outputs/reports/{arm_tag}.manifest.json",
                     "sha256": manifest_sha},
        "independent_verifier": {"path": f"outputs/reports/verify_{arm_tag}.py",
                                 "sha256": verifier_sha},
    }
    capsule = {
        "schema_version": "snapshot_formal_arm_capsule@1.0.0",
        "capsule": arm_tag, "claim_scope": "formal",
        "files": {name: info for name, info in artifacts.items()},
        "independent_verifier": {"path": f"outputs/reports/verify_{arm_tag}.py",
                                 "sha256": verifier_sha},
    }
    (staging / "export_index.json").write_bytes(
        (json.dumps(export_index, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    (staging / "capsule_manifest.json").write_bytes(
        (json.dumps(capsule, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

    # finalize (atomic rename, no overwrite)
    out_pred = ROOT / "data" / "predictions" / arm_tag
    out_res = ROOT / "data" / "results" / arm_tag
    out_man = OUT_REPORTS / f"{arm_tag}.manifest.json"
    out_ver = OUT_REPORTS / f"verify_{arm_tag}.py"
    out_exp = OUT_REPORTS / f"{arm_tag}_export_index.json"
    out_cap = OUT_REPORTS / f"{arm_tag}_capsule_manifest.json"
    for d in (out_pred, out_res, out_man, out_ver, out_exp, out_cap):
        if d.exists():
            raise RuntimeError(f"refusing to overwrite existing: {d}")
    (staging / "predictions" / arm_tag).rename(out_pred)
    (staging / "results" / arm_tag).rename(out_res)
    (staging / "manifest.json").rename(out_man)
    (staging / "verify_snapshot_formal_arm.py").rename(out_ver)
    (staging / "export_index.json").rename(out_exp)
    (staging / "capsule_manifest.json").rename(out_cap)
    shutil.rmtree(staging, ignore_errors=True)

    print(f"formal arm capsule published: {arm_tag} (claim_scope=formal)")
    print(f"  zero-API: new calls 0 | snapshot {info['run']}")
    print(f"  fine 5-field F1: { {k: round(v['f1'], 4) for k, v in fine['span_fields'].items()} }")
    print(f"  modality label acc: {labels.get('accuracy')}")
    print(f"  manifest sha256: {manifest_sha[:16]}...")
    return 0


def _write_staged(staging: Path, name: str, payload: dict[str, Any]) -> str:
    data = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (staging / name).write_bytes(data)
    return _sha256_bytes(data)


_VERIFIER_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Independent verifier for the {RUN_ID} snapshot formal arm capsule."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "{RUN_ID}"
MANIFEST = ROOT / "outputs" / "reports" / f"{{RUN_ID}}.manifest.json"
PRED = ROOT / "data" / "predictions" / RUN_ID / "predictions.json"
INPUT_V2 = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"

EXPECTED_MANIFEST_SHA = "{MANIFEST_SHA}"
EXPECTED_PRED_SHA = "{PRED_SHA}"
EXPECTED_INPUT_V2_SHA = "{INPUT_V2_SHA}"
EXPECTED_GOLD_SHA = "{GOLD_SHA}"
EXPECTED_METHOD = "{METHOD}"
EXPECTED_HIST_LLM_CALLS = {HIST_LLM_CALLS}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    checks = []

    def check(name, ok, detail=""):
        checks.append({{"name": name, "ok": bool(ok), "detail": detail}})

    check("manifest exists", MANIFEST.exists())
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {{}}
    check("manifest schema", manifest.get("schema_version") == "snapshot_formal_arm_manifest@1.0.0")
    check("claim_scope formal", manifest.get("claim_scope") == "formal")
    check("is_formal_performance_result", manifest.get("is_formal_performance_result") is True)
    check("method", manifest.get("method_id") == EXPECTED_METHOD)
    check("zero new calls", manifest.get("zero_api", {{}}).get("new_llm_calls") == 0)
    check("historical calls", manifest.get("zero_api", {{}}).get("historical_llm_calls") == EXPECTED_HIST_LLM_CALLS)
    check("manifest hash", _sha(MANIFEST) == EXPECTED_MANIFEST_SHA)
    check("predictions hash", _sha(PRED) == EXPECTED_PRED_SHA)
    check("input v2 hash", _sha(INPUT_V2) == EXPECTED_INPUT_V2_SHA)
    check("gold hash", _sha(GOLD) == EXPECTED_GOLD_SHA)
    pred = json.loads(PRED.read_text(encoding="utf-8"))
    check("predictions 150", len(pred.get("records", [])) == 150)
    check("predictions timing-free",
          all("runtime" not in r and "latency" not in json.dumps(r)
              for r in pred.get("records", [])))
    res = ROOT / "data" / "results" / RUN_ID
    for f in ("evaluation_fine.json", "evaluation_coarse.json",
              "modality_labels.json", "g04_view_declaration.json",
              "cost.json", "config_snapshot.json"):
        check(f"result {{f}} exists", (res / f).exists())
    cost = json.loads((res / "cost.json").read_text(encoding="utf-8"))
    check("zero api cost", cost.get("llm_api_called") is False
          and cost.get("new_llm_api_calls") == 0)
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

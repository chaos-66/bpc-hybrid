# -*- coding: utf-8 -*-
"""Run the v4 scoped Table 3 matrix for Sun, Ours, and Winter.

The runner reads only the blinded inference view, the frozen Stage-2 input,
the method-specific rule extraction capsules, the current BPMN models, and the
v4 execution config.  It never reads ``construction_reference.json``.  Sun and
Ours share exactly one frozen ``SunScorer`` through a no-outer-gate checker.
Winter uses the existing independent native paragraph/model/pair path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from bpc_hybrid.stage3_sun_style_checker import winter_signals  # noqa: E402
from bpc_hybrid.sun_stage3.gdpr_capsule_converter import build_rule_records  # noqa: E402
from bpc_hybrid.sun_stage3.no_gate_checker_v1 import NoGateSunChecker  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.sun_stage3.temporal_projection_v1 import project_record_order_relations  # noqa: E402
from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph  # noqa: E402
from bpc_hybrid.winter_stage3.winter_model import REACHABILITY_CORRECTED, parse_bpmn_file_winter  # noqa: E402
from bpc_hybrid.winter_stage3.winter_pair import WinterPair  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

CONFIG = ROOT / "configs/stage3_table3_v4_execution_v1.json"
STAGE2_INPUT = ROOT / "data/development/stage3_reconstruction_v4/stage2_input.json"
INFERENCE_VIEW = ROOT / "data/development/stage3_reconstruction_v4/inference_view.json"
WINTER_CONFIG = ROOT / "configs/winter_stage3_development_v1.json"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
WINTER_LEXICON_DIR = ROOT.parent / "references/winter_2020_model_check/model_check/input/files"
OUT_DIR = ROOT / "outputs/development/stage3_table3_v4"
SCHEMA_VERSION = "stage3_table3_v4_predictions@1.0.0"
ALLOWED_INFERENCE_KEYS = ("case_id", "bpmn_path", "process_id")
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


def _git_state() -> dict[str, Any]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout.strip()
        return {"commit": commit, "dirty_paths": dirty.splitlines()[:50]}
    except Exception as exc:  # noqa: BLE001
        return {"commit": "unknown", "dirty_paths": [str(exc)]}

def load_inputs() -> dict[str, Any]:
    cfg = _load_json(CONFIG)
    for rel, expected in (cfg.get("hash_bindings") or {}).items():
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f"required input missing: {rel}")
        actual = _sha_file(path)
        if actual != expected:
            raise RuntimeError(f"input hash drift: {rel}: {actual} != {expected}")
    view = _load_json(INFERENCE_VIEW)
    safety = view.get("safety") or {}
    if safety.get("gold_labels_present") is not False or safety.get("rule_id_present") is not False:
        raise RuntimeError("inference view safety declaration drift")
    items: list[dict[str, Any]] = []
    for raw in view.get("items") or []:
        if set(raw) - set(ALLOWED_INFERENCE_KEYS):
            raise RuntimeError(f"forbidden inference fields: {sorted(set(raw) - set(ALLOWED_INFERENCE_KEYS))}")
        item = {key: raw.get(key) for key in ALLOWED_INFERENCE_KEYS}
        if not all(item.values()):
            raise RuntimeError(f"invalid inference item: {raw!r}")
        items.append(item)
    stage2 = _load_json(STAGE2_INPUT)
    if stage2.get("gold_visible") is not False or stage2.get("counts") != {"rules": 5, "sentences": 5}:
        raise RuntimeError("stage2 input scope drift")
    samples: dict[str, dict[str, Any]] = {}
    for rule in stage2["rules"]:
        for sentence in rule["sentences"]:
            sid = sentence["sample_id"]
            text = sentence["approved_text_en"]
            if _sha_text(text) != sentence["text_sha256"]:
                raise RuntimeError(f"source text hash drift: {sid}")
            samples[sid] = {
                "rule_id": rule["rule_id"],
                "sample_id": sid,
                "text": text,
                "char_span": sentence["char_span"],
            }
    if len(samples) != 5:
        raise RuntimeError("expected five source inputs")
    return {"config": cfg, "items": items, "stage2": stage2, "samples": samples}


def _project_rule_records(capsule_path: Path, expected_schema: str,
                          samples: Mapping[str, Mapping[str, Any]], nlp: Any) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any]]:
    capsule = _load_json(capsule_path)
    texts = {sid: sample["text"] for sid, sample in samples.items()}
    rule_ids = sorted({sample["rule_id"] for sample in samples.values()})
    records, converter_summary = build_rule_records(
        capsule, texts, rule_ids, expected_schema=expected_schema)
    projection_audits: dict[str, Any] = {}
    by_sample = {row.get("sample_id"): row for row in capsule.get("records") or []}
    sample_by_rule = {sample["rule_id"]: sample for sample in samples.values()}
    for rule_id, record in records.items():
        sample = sample_by_rule.get(rule_id)
        if sample is None:
            projection_audits[rule_id] = {"status": "missing_sample_mapping"}
            continue
        env = by_sample.get(sample["sample_id"]) or {}
        canonical = env.get("record") if env.get("request_status") == "ok" else None
        if not isinstance(canonical, Mapping):
            projection_audits[rule_id] = {
                "status": "skipped_no_canonical_record",
                "request_status": env.get("request_status"),
                "error_category": env.get("error_category"),
            }
            record["order_relations"] = []
            continue
        doc = nlp(sample["text"])
        edges, audit = project_record_order_relations(canonical, sample["text"], doc)
        record["order_relations"] = edges
        record["order_relation_projection"] = audit
        projection_audits[rule_id] = audit
    return records, converter_summary, projection_audits


def _failure_rule_records(samples: Mapping[str, Mapping[str, Any]], reason: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for rule_id in sorted({sample["rule_id"] for sample in samples.values()}):
        records[rule_id] = {
            "rule_id": rule_id,
            "schema_version": "sun_rule_record_capsule_v1@1.0.0",
            "modality": "obligation",
            "actions": [],
            "actors": [],
            "actor_action_pairs": [],
            "order_relations": [],
            "failed": True,
            "failure_reasons": [reason],
            "provenance": {"gold_fields_read": False, "failure_reason": reason},
        }
    return records

def _load_winter_lexicon() -> tuple[set[str], set[str], set[str]]:
    signalwords = set((WINTER_LEXICON_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    sequencemarkers = set((WINTER_LEXICON_DIR / "sequencemarkers.txt").read_text(encoding="utf-8").splitlines())
    stopwords = set((WINTER_LEXICON_DIR / "stopwords.txt").read_text(encoding="utf-8").splitlines())
    return signalwords, sequencemarkers, stopwords


def _winter_case_payload(item: Mapping[str, Any], samples: Mapping[str, Mapping[str, Any]],
                         winter_cfg: Mapping[str, Any], nlp: Any, sim: Any,
                         signalwords: set[str], sequencemarkers: set[str],
                         stopwords: set[str], paragraph_cache: dict[str, Any],
                         model_cache: dict[str, Any]) -> dict[str, Any]:
    path = str(item["bpmn_path"])
    if path not in model_cache:
        model_cache[path] = parse_bpmn_file_winter(
            ROOT / path, nlp, stopwords, reachability_mode=REACHABILITY_CORRECTED)
    model = model_cache[path]
    resources = {str(process.participant).lower() for process in model.processes
                 if str(getattr(process, "participant", "") or "").strip()}
    matching: list[dict[str, Any]] = []
    signals_by_rule: dict[str, Any] = {}
    violations: list[dict[str, Any]] = []
    for rule_id in sorted({sample["rule_id"] for sample in samples.values()}):
        text = next(sample["text"] for sample in samples.values() if sample["rule_id"] == rule_id)
        if rule_id not in paragraph_cache:
            paragraph_cache[rule_id] = parse_regulation_paragraph(
                rule_id, text, nlp, stopwords, signalwords, sequencemarkers,
                only_constraints=True)
        paragraph = paragraph_cache[rule_id]
        pair = WinterPair(nlp, sim, model, paragraph, resources,
                          float(winter_cfg["method"]["gamma"]),
                          float(winter_cfg["method"]["delta"]))
        signals = winter_signals(pair=pair, model=model, paragraph=paragraph,
                                 resource_set=resources)
        matching.append({
            "rule_id": rule_id,
            "matching_score": float(pair.fitness),
            "action_ratio": None,
            "actor_object_ratio": None,
            "relevant": float(pair.fitness) > 0.0,
            "rank": None,
        })
        signals_by_rule[rule_id] = signals
        for check_type, signal in signals.items():
            if signal.get("status") == "violated":
                violations.append({
                    "rule_id": rule_id,
                    "violation_type": check_type,
                    "raw_score": signal.get("raw_score"),
                    "denominator": signal.get("denominator"),
                    "observable": bool(signal.get("observable")),
                    "reason": signal.get("reason"),
                })
    matching.sort(key=lambda row: (-row["matching_score"], row["rule_id"]))
    for rank, row in enumerate(matching, start=1):
        row["rank"] = rank
    return {
        "matching": matching,
        "signals_by_rule": signals_by_rule,
        "violations": violations,
        "violated_types": sorted({v["violation_type"] for v in violations}),
        "method_evidence": {
            "winter_config_version": winter_cfg.get("config_version"),
            "gamma": float(winter_cfg["method"]["gamma"]),
            "delta": float(winter_cfg["method"]["delta"]),
            "reachability_mode": REACHABILITY_CORRECTED,
            "resource_set": sorted(resources),
            "rule_side_flow_counts": {
                rid: len(paragraph_cache[rid].flows or [])
                for rid in sorted(paragraph_cache)
            },
            "process_activities": [
                label
                for process in model.processes
                for label in list(getattr(process, "task_labels", []) or [])
            ],
            "visible_executors": sorted(resources),
        },
    }


def _sun_case_payload(item: Mapping[str, Any], rule_records: Mapping[str, Mapping[str, Any]],
                      checker: NoGateSunChecker, nlp: Any, contract: Any,
                      model_cache: dict[str, Any]) -> dict[str, Any]:
    path = str(item["bpmn_path"])
    if path not in model_cache:
        record = parse_bpmn_file(ROOT / path, contract=contract)
        model_cache[path] = {
            "record": record,
            "model": SunProcessModel(str(item["process_id"]), record, nlp),
        }
    model = model_cache[path]["model"]
    payload = checker.check(model, rule_records)
    payload = dict(payload)
    payload["method_evidence"] = {
        "rule_action_counts": {rid: len(rec.get("actions") or []) for rid, rec in rule_records.items()},
        "rule_actor_counts": {rid: len(rec.get("actors") or []) for rid, rec in rule_records.items()},
        "rule_order_relation_counts": {rid: len(rec.get("order_relations") or []) for rid, rec in rule_records.items()},
        "process_activities": [a["name"] for a in model.actions],
        "visible_executors": list(model.actors),
    }
    return payload

def run(*, out_dir: Path = OUT_DIR, nlp_model: str = "en_core_web_sm",
        overwrite: bool = False) -> dict[str, Any]:
    if out_dir.exists() and any(out_dir.iterdir()) and not overwrite:
        raise SystemExit(f"refusing to overwrite non-empty {out_dir}; pass --overwrite only for a deliberate rerun")
    started = time.perf_counter()
    loaded = load_inputs()
    cfg = loaded["config"]
    items = sorted(loaded["items"], key=lambda row: str(row["case_id"]))
    samples = loaded["samples"]
    rule_ids = sorted({sample["rule_id"] for sample in samples.values()})

    import spacy  # type: ignore
    nlp = spacy.load(nlp_model)
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    sim = WinterSimilarity(nlp)
    sun_cfg = _load_json(ROOT / "configs/sun_stage3_development_v1.json")
    thresholds = sun_cfg["method"]["thresholds"]
    scorer = SunScorer(sim, float(thresholds["tau"]), float(thresholds["gamma"]),
                       float(thresholds["theta"]), nlp=nlp)
    checker = NoGateSunChecker(scorer)

    methods: dict[str, dict[str, Any]] = {}
    sun_path = ROOT / cfg["methods"]["sun"]["predictions_path"]
    if not sun_path.is_file():
        raise RuntimeError(f"Sun B0 predictions missing: {sun_path}")
    sun_records, sun_converter, sun_projection = _project_rule_records(
        sun_path, cfg["methods"]["sun"]["expected_schema"], samples, nlp)
    methods["sun"] = {
        "row_method_id": "sun",
        "label": cfg["methods"]["sun"]["label"],
        "method_id": cfg["methods"]["sun"]["method_id"],
        "status": "available",
        "rule_records": sun_records,
        "converter_summary": sun_converter,
        "projection_audit": sun_projection,
    }

    ours_path = ROOT / cfg["methods"]["ours"]["predictions_path"]
    if ours_path.is_file():
        ours_records, ours_converter, ours_projection = _project_rule_records(
            ours_path, cfg["methods"]["ours"]["expected_schema"], samples, nlp)
        methods["ours"] = {
            "row_method_id": "ours",
            "label": cfg["methods"]["ours"]["label"],
            "method_id": cfg["methods"]["ours"]["method_id"],
            "status": "available",
            "rule_records": ours_records,
            "converter_summary": ours_converter,
            "projection_audit": ours_projection,
        }
    else:
        reason = "stage3_v4_d1_predictions_missing: no real D1 capsule at " + str(ours_path.relative_to(ROOT))
        methods["ours"] = {
            "row_method_id": "ours",
            "label": cfg["methods"]["ours"]["label"],
            "method_id": cfg["methods"]["ours"]["method_id"],
            "status": "blocked_missing_d1_predictions",
            "rule_records": _failure_rule_records(samples, reason),
            "converter_summary": {"status": "not_run", "reason": reason},
            "projection_audit": {"status": "not_run", "reason": reason},
            "blocker": reason,
        }

    winter_cfg = _load_json(WINTER_CONFIG)
    signalwords, sequencemarkers, stopwords = _load_winter_lexicon()
    methods["winter"] = {
        "row_method_id": "winter",
        "label": cfg["methods"]["winter"]["label"],
        "method_id": cfg["methods"]["winter"]["method_id"],
        "status": "available_native",
        "rule_records": None,
        "converter_summary": None,
        "projection_audit": None,
    }

    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    sun_model_cache: dict[str, Any] = {}
    winter_model_cache: dict[str, Any] = {}
    winter_paragraph_cache: dict[str, Any] = {}

    prediction_rows: list[dict[str, Any]] = []
    for item in items:
        case_id = str(item["case_id"])
        for row_method_id in ("sun", "ours", "winter"):
            method = methods[row_method_id]
            if row_method_id in ("sun", "ours"):
                payload = _sun_case_payload(item, method["rule_records"], checker, nlp,
                                            contract, sun_model_cache)
            else:
                payload = _winter_case_payload(item, samples, winter_cfg, nlp, sim,
                                               signalwords, sequencemarkers, stopwords,
                                               winter_paragraph_cache, winter_model_cache)
            prediction_rows.append({
                "schema_version": SCHEMA_VERSION,
                "row_method_id": row_method_id,
                "method_id": method["method_id"],
                "method_label": method["label"],
                "method_status": method["status"],
                "case_id": case_id,
                "bpmn_path": str(item["bpmn_path"]),
                "process_id": str(item["process_id"]),
                "matching": _jsonable(payload["matching"]),
                "violations": _jsonable(payload["violations"]),
                "violated_types": list(payload["violated_types"]),
                "signals_by_rule": _jsonable(payload["signals_by_rule"]),
                "checker_policy": _jsonable(payload.get("checker_policy")),
                "method_evidence": _jsonable(payload["method_evidence"]),
                "inference_inputs": {
                    "current_bpmn_only": True,
                    "full_rule_base": True,
                    "case_gold_read": False,
                    "pair_role_read": False,
                    "target_rule_id_read": False,
                    "target_violation_type_read": False,
                    "target_activity_id_read": False,
                    "mutation_type_read": False,
                    "control_reference_read": False,
                    "construction_reference_read": False,
                },
            })

    signals_matrix: list[dict[str, Any]] = []
    for row in prediction_rows:
        for rid, signals in row["signals_by_rule"].items():
            for check_type in TYPES:
                signal = signals.get(check_type) or {}
                signals_matrix.append({
                    "method": row["row_method_id"],
                    "method_id": row["method_id"],
                    "method_status": row["method_status"],
                    "case_id": row["case_id"],
                    "rule_id": rid,
                    "check_type": check_type,
                    "status": signal.get("status"),
                    "raw_score": signal.get("raw_score"),
                    "denominator": signal.get("denominator"),
                    "observable": signal.get("observable"),
                    "reason": signal.get("reason"),
                    "evidence": signal.get("evidence"),
                })
    if len(signals_matrix) != 900:
        raise RuntimeError(f"expected 900 signals, got {len(signals_matrix)}")

    out_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = out_dir / "predictions.json"
    _write_json(predictions_path, {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "stage3_scoped_gdpr_v4",
        "gold_read_by_runner": False,
        "construction_reference_read": False,
        "counts": {"cases": len(items), "methods": 3, "prediction_rows": len(prediction_rows),
                   "signals": len(signals_matrix)},
        "records": prediction_rows,
    })
    _write_json(out_dir / "signals_matrix.json", {
        "schema_version": "stage3_table3_v4_signals@1.0.0",
        "count": len(signals_matrix),
        "signals": signals_matrix,
    })
    _write_json(out_dir / "rule_records.json", {
        method_key: {
            "method_id": method["method_id"],
            "status": method["status"],
            "converter_summary": _jsonable(method["converter_summary"]),
            "projection_audit": _jsonable(method["projection_audit"]),
            "records": _jsonable(method["rule_records"]),
        }
        for method_key, method in methods.items()
    })
    manifest = {
        "schema_version": "stage3_table3_v4_run@1.0.0",
        "run_id": "stage3_table3_v4",
        "status": ("complete" if all(m["status"].startswith("available") for m in methods.values())
                   else "diagnostic_incomplete_d1_blocked"),
        "scope": cfg["scope"],
        "methods": {key: {"method_id": m["method_id"], "label": m["label"],
                          "status": m["status"], "blocker": m.get("blocker")}
                    for key, m in methods.items()},
        "inputs": {
            "execution_config": {"path": str(CONFIG.relative_to(ROOT)).replace("\\", "/"),
                                 "sha256": _sha_file(CONFIG)},
            "stage2_input": {"path": str(STAGE2_INPUT.relative_to(ROOT)).replace("\\", "/"),
                             "sha256": _sha_file(STAGE2_INPUT)},
            "inference_view": {"path": str(INFERENCE_VIEW.relative_to(ROOT)).replace("\\", "/"),
                               "sha256": _sha_file(INFERENCE_VIEW)},
            "sun_predictions": {"path": str(sun_path.relative_to(ROOT)).replace("\\", "/"),
                                "sha256": _sha_file(sun_path)},
            "ours_predictions": ({"path": str(ours_path.relative_to(ROOT)).replace("\\", "/"),
                                  "sha256": _sha_file(ours_path)} if ours_path.is_file() else None),
            "winter_config": {"path": str(WINTER_CONFIG.relative_to(ROOT)).replace("\\", "/"),
                              "sha256": _sha_file(WINTER_CONFIG)},
        },
        "configuration": {
            "sun_thresholds": {k: float(thresholds[k]) for k in ("tau", "gamma", "theta")},
            "outer_matching_gate_applied": False,
            "one_sun_checker_for_sun_and_ours": True,
            "winter_gamma": float(winter_cfg["method"]["gamma"]),
            "winter_delta": float(winter_cfg["method"]["delta"]),
            "winter_reachability_mode": REACHABILITY_CORRECTED,
            "temporal_projection": cfg["temporal_projection"],
        },
        "counts": {"cases": len(items), "methods": 3, "prediction_rows": len(prediction_rows),
                   "signals": len(signals_matrix)},
        "code_sha256": {
            str(path.relative_to(ROOT)).replace("\\", "/"): _sha_file(path)
            for path in [
                Path(__file__),
                ROOT / "src/bpc_hybrid/sun_stage3/temporal_projection_v1.py",
                ROOT / "src/bpc_hybrid/sun_stage3/no_gate_checker_v1.py",
                ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py",
                ROOT / "src/bpc_hybrid/sun_stage3/gdpr_capsule_converter.py",
                ROOT / "src/bpc_hybrid/stage3_sun_style_checker.py",
                ROOT / "src/bpc_hybrid/winter_stage3/winter_model.py",
                ROOT / "src/bpc_hybrid/winter_stage3/winter_clause.py",
                ROOT / "src/bpc_hybrid/winter_stage3/winter_pair.py",
                ROOT / "src/bpc_hybrid/winter_stage3/winter_similarity.py",
            ] if path.is_file()
        },
        "dependency_versions": {
            "python": sys.version.split()[0],
            "spacy": spacy.__version__,
            "spacy_model": nlp_model,
        },
        "git": _git_state(),
        "command": "python formal_experiment/scripts/run_stage3_table3_v4.py",
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "gold_read_by_runner": False,
        "construction_reference_read_by_runner": False,
        "llm_api_calls": 0,
        "network_calls": 0,
    }
    _write_json(out_dir / "run_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--nlp-model", default="en_core_web_sm")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    manifest = run(out_dir=args.out_dir, nlp_model=args.nlp_model, overwrite=args.overwrite)
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
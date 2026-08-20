# -*- coding: utf-8 -*-
"""Evaluate the already locked S2.12 zero-API prediction capsule.

This is a separate post-prediction phase.  It verifies the prediction lock,
then reads the frozen S2.11 Gold and applies the existing S2.12 evaluator v2
without changing the method, rules, prompts, thresholds, or predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s2_12_method_adapter import adapt_method_attempts  # noqa: E402
from bpc_hybrid.s2_12_stratified_evaluator_v2 import evaluate_stratified  # noqa: E402

PRED_DIR = ROOT / "data/predictions/s2_12_sun_rule_only_v1"
PREDICTIONS = PRED_DIR / "predictions.json"
RUN_MANIFEST = PRED_DIR / "manifest.json"
GOLD = ROOT / "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
LEVELS = ROOT / "outputs/reports/s2_11_proposal_report_v3.json"
OUTPUT_DIR = ROOT / "data/results/s2_12_sun_rule_only_v1"
EXPECTED_GOLD_SHA = "039ae8b2429826ae2b320667fb4a0dff96de6408b0a9637c1d9911565129c804"
EXPECTED_LEVELS_SHA = "0cd725b4e7e14c88a97ca005ec10dac3f7fc77c2ebf3955eb746abdc9479616a"
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")


class EvaluationFail(ValueError):
    """Fail-closed evaluation error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _verify_prediction_lock() -> dict[str, Any]:
    if not RUN_MANIFEST.is_file() or not PREDICTIONS.is_file():
        raise EvaluationFail("prediction capsule must exist before evaluation")
    manifest = json.loads(RUN_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("status") != "predictions_locked_before_gold_evaluation":
        raise EvaluationFail("prediction capsule is not locked-before-Gold")
    if manifest.get("gold_isolation", {}).get("gold_read_by_runner") is not False:
        raise EvaluationFail("runner Gold-isolation declaration invalid")
    for name, info in manifest.get("artifacts", {}).items():
        path = PRED_DIR / name
        if not path.is_file() or _sha(path) != info.get("sha256"):
            raise EvaluationFail(f"prediction artifact drift: {name}")
        if path.stat().st_size != info.get("byte_size"):
            raise EvaluationFail(f"prediction artifact size drift: {name}")
    return manifest


def _gold_records(gold_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in gold_doc.get("records", []):
        clauses = []
        canonical = record.get("canonical") or {}
        for clause in canonical.get("clauses", []):
            converted = {
                "clause_id": clause.get("clause_id"),
                "modality": {
                    "label": (clause.get("modality") or {}).get("label"),
                    "evidence": list((clause.get("modality") or {}).get("evidence") or []),
                },
            }
            for field in SPAN_FIELDS:
                converted[field + "s"] = list((clause.get(field) or {}).get("spans") or [])
            clauses.append(converted)
        output.append({"sample_id": record.get("sample_id"), "clauses": clauses})
    return output


def _levels() -> dict[str, str]:
    if _sha(LEVELS) != EXPECTED_LEVELS_SHA:
        raise EvaluationFail("frozen stratum source drift")
    document = json.loads(LEVELS.read_text(encoding="utf-8"))
    entries = document.get("entries")
    if not isinstance(entries, dict):
        raise EvaluationFail("frozen stratum source entries missing")
    values = {
        sample_id: row["g0_5_level"]
        for sample_id, row in entries.items()
    }
    counts = {level: list(values.values()).count(level) for level in ("L1", "L2", "L3")}
    if counts != {"L1": 31, "L2": 5, "L3": 0}:
        raise EvaluationFail(f"frozen stratum counts drift: {counts}")
    return values


def build_report() -> dict[str, Any]:
    run_manifest = _verify_prediction_lock()
    if _sha(GOLD) != EXPECTED_GOLD_SHA:
        raise EvaluationFail("frozen S2.11 Gold drift")
    prediction_doc = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    attempts = adapt_method_attempts(prediction_doc.get("records", []), "sun_rule_only")
    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    gold_records = _gold_records(gold_doc)
    levels = _levels()
    metrics = evaluate_stratified(
        gold_records,
        attempts,
        levels=levels,
        dataset_id="s2_11_barrientos_complex_corpus_36_v1",
        method_id="sun_rule_only",
    )
    return {
        "schema_version": "s2_12_sun_rule_only_evaluation@1.0.0",
        "status": "verified_zero_api_arm_complete",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "arm": "sun_rule_only",
        "scope_boundary": {
            "single_zero_api_arm_only": True,
            "three_method_comparison_complete": False,
            "direct_llm_pending_api_authorization": True,
            "sun_llm_fallback_pending_api_authorization": True,
            "post_result_tuning_performed": False,
            "no_method_rule_prompt_threshold_adjustment_from_gold_or_results": True,
        },
        "prediction_lock": {
            "manifest_path": "data/predictions/s2_12_sun_rule_only_v1/manifest.json",
            "manifest_sha256": _sha(RUN_MANIFEST),
            "predictions_path": "data/predictions/s2_12_sun_rule_only_v1/predictions.json",
            "predictions_sha256": _sha(PREDICTIONS),
            "status": run_manifest["status"],
            "gold_read_by_runner": False,
        },
        "gold_binding": {
            "path": "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json",
            "sha256": EXPECTED_GOLD_SHA,
            "read_only_after_prediction_lock": True,
        },
        "strata": {
            "source": "outputs/reports/s2_11_proposal_report_v3.json",
            "sha256": EXPECTED_LEVELS_SHA,
            "counts": {"L1": 31, "L2": 5, "L3": 0},
            "l3_policy": "no samples; no performance conclusion",
        },
        "evaluator": {
            "module": "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py",
            "module_sha256": _sha(ROOT / "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py"),
            "g0_4_parity_contract": "configs/stage2_evaluator_s210_v3.json",
            "g0_4_parity_contract_sha256": _sha(ROOT / "configs/stage2_evaluator_s210_v3.json"),
        },
        "metrics": metrics,
        "runtime": run_manifest.get("runtime_summary"),
        "cost": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "actual_cost_usd": 0.0,
        },
    }


def build_manifest(report_data: bytes) -> dict[str, Any]:
    implementation_paths = (
        "scripts/evaluate_s2_12_sun_rule_only_v1.py",
        "scripts/verify_s2_12_sun_rule_only_v1.py",
        "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py",
        "src/bpc_hybrid/s2_12_method_adapter.py",
        "configs/stage2_evaluator_s210_v3.json",
    )
    return {
        "schema_version": "s2_12_sun_rule_only_evaluation_manifest@1.0.0",
        "status": "verified_zero_api_arm_complete",
        "report": {
            "path": "data/results/s2_12_sun_rule_only_v1/evaluation.json",
            "sha256": hashlib.sha256(report_data).hexdigest(),
            "byte_size": len(report_data),
        },
        "bindings": {
            "prediction_manifest": {"path": str(RUN_MANIFEST.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha(RUN_MANIFEST)},
            "predictions": {"path": str(PREDICTIONS.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha(PREDICTIONS)},
            "gold": {"path": str(GOLD.relative_to(ROOT)).replace("\\", "/"), "sha256": EXPECTED_GOLD_SHA},
            "strata": {"path": str(LEVELS.relative_to(ROOT)).replace("\\", "/"), "sha256": EXPECTED_LEVELS_SHA},
        },
        "implementation": {
            rel: _sha(ROOT / rel) for rel in implementation_paths
        },
        "replay_command": "python formal_experiment/scripts/evaluate_s2_12_sun_rule_only_v1.py --check",
        "verification_command": "python formal_experiment/scripts/verify_s2_12_sun_rule_only_v1.py",
        "safety": {
            "llm_api_calls": 0,
            "single_arm_only": True,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--evaluate", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    report_data = _json_bytes(build_report())
    manifest_data = _json_bytes(build_manifest(report_data))
    expected = {"evaluation.json": report_data, "manifest.json": manifest_data}
    if args.check:
        for name, data in expected.items():
            path = OUTPUT_DIR / name
            if not path.is_file() or path.read_bytes() != data:
                raise EvaluationFail(f"evaluation replay differs: {name}")
        print("S2.12 SUN_RULE_ONLY EVALUATION REPLAY VERIFIED")
        return 0
    if OUTPUT_DIR.exists():
        raise EvaluationFail(f"refusing to overwrite existing evaluation: {OUTPUT_DIR}")
    stage = OUTPUT_DIR.parent / f".{OUTPUT_DIR.name}.staging-{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        for name, data in expected.items():
            (stage / name).write_bytes(data)
        stage.rename(OUTPUT_DIR)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print("S2.12 sun_rule_only evaluation published (single zero-API arm only)")
    print(f"report_sha256={hashlib.sha256(report_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

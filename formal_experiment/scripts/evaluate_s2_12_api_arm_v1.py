# -*- coding: utf-8 -*-
"""Evaluate an already locked S2.12 API-arm prediction capsule.

This is a separate post-prediction phase for the ``direct_llm`` /
``sun_llm_fallback`` arms.  It verifies the finalizer's prediction lock
(status literal, artifact hashes/sizes, capsule completeness), then reads the
frozen S2.11 Gold and applies the same S2.12 stratified evaluator v2 used by
the zero-API arm — without changing the method, rules, prompts, thresholds,
or predictions.

Refusal conditions (EvaluationFail, exit 2):

* the prediction capsule does not exist or its manifest status is not
  ``predictions_locked_before_gold_evaluation``;
* the capsule is ``complete_with_explicit_failures`` — explicit failures do
  not satisfy the evaluation condition;
* any committed prediction artifact hash/size drifted;
* predictions do not contain exactly 36 rows, all with
  ``request_status == "ok"``;
* Gold / frozen stratum drift, or attempt/gold membership mismatch.
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

ARM_DIRS = {
    "direct_llm": "s2_12_direct_llm_v1",
    "sun_llm_fallback": "s2_12_sun_llm_fallback_v1",
}
GOLD = ROOT / "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json"
LEVELS = ROOT / "outputs/reports/s2_11_proposal_report_v3.json"
EXPECTED_GOLD_SHA = "039ae8b2429826ae2b320667fb4a0dff96de6408b0a9637c1d9911565129c804"
EXPECTED_LEVELS_SHA = "0cd725b4e7e14c88a97ca005ec10dac3f7fc77c2ebf3955eb746abdc9479616a"
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")


class EvaluationFail(ValueError):
    """Fail-closed evaluation error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _verify_prediction_lock(arm: str) -> dict[str, Any]:
    pred_dir = ROOT / "data/predictions" / ARM_DIRS[arm]
    run_manifest_path = pred_dir / "manifest.json"
    if not run_manifest_path.is_file() or not (pred_dir / "predictions.json").is_file():
        raise EvaluationFail("prediction capsule must exist before evaluation")
    manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "predictions_locked_before_gold_evaluation":
        raise EvaluationFail("prediction capsule is not locked-before-Gold")
    if manifest.get("gold_isolation", {}).get("gold_read_by_runner") is not False:
        raise EvaluationFail("runner Gold-isolation declaration invalid")
    if manifest.get("capsule_status") != "complete":
        raise EvaluationFail(
            f"capsule status {manifest.get('capsule_status')!r}: explicit "
            "failures do not satisfy the evaluation condition")
    for name, info in manifest.get("artifacts", {}).items():
        path = pred_dir / name
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
    values = {sample_id: row["g0_5_level"] for sample_id, row in entries.items()}
    counts = {level: list(values.values()).count(level) for level in ("L1", "L2", "L3")}
    if counts != {"L1": 31, "L2": 5, "L3": 0}:
        raise EvaluationFail(f"frozen stratum counts drift: {counts}")
    return values


def _capsule_cost(arm: str) -> dict[str, Any]:
    path = ROOT / "data/predictions" / ARM_DIRS[arm] / "cost.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {
        "llm_api_calls": doc.get("llm_api_calls"),
        "network_calls": doc.get("network_calls"),
        "actual_cost_usd": doc.get("actual_cost_usd"),
    }


def build_report(arm: str) -> dict[str, Any]:
    run_manifest = _verify_prediction_lock(arm)
    if _sha(GOLD) != EXPECTED_GOLD_SHA:
        raise EvaluationFail("frozen S2.11 Gold drift")
    pred_dir = ROOT / "data/predictions" / ARM_DIRS[arm]
    predictions_path = pred_dir / "predictions.json"
    prediction_doc = json.loads(predictions_path.read_text(encoding="utf-8"))
    records = prediction_doc.get("records", [])
    if len(records) != 36:
        raise EvaluationFail(f"prediction rows {len(records)} != 36")
    bad = sorted({row["request_status"] for row in records} - {"ok"})
    if bad:
        raise EvaluationFail(f"prediction rows are not all ok: {bad}")
    attempts = adapt_method_attempts(records, arm)
    gold_doc = json.loads(GOLD.read_text(encoding="utf-8"))
    gold_records = _gold_records(gold_doc)
    levels = _levels()
    metrics = evaluate_stratified(
        gold_records, attempts, levels=levels,
        dataset_id="s2_11_barrientos_complex_corpus_36_v1", method_id=arm,
    )
    return {
        "schema_version": f"s2_12_{arm}_evaluation@1.0.0",
        "status": f"verified_{arm}_arm_complete",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "arm": arm,
        "scope_boundary": {
            "single_zero_api_arm_only": False,
            "three_method_comparison_complete": False,
            "direct_llm_pending": False,
            "sun_llm_fallback_pending": False,
            "post_result_tuning_performed": False,
            "no_method_rule_prompt_threshold_adjustment_from_gold_or_results": True,
        },
        "prediction_lock": {
            "manifest_path": f"data/predictions/{ARM_DIRS[arm]}/manifest.json",
            "manifest_sha256": _sha(pred_dir / "manifest.json"),
            "predictions_path": f"data/predictions/{ARM_DIRS[arm]}/predictions.json",
            "predictions_sha256": _sha(predictions_path),
            "status": run_manifest["status"],
            "capsule_status": run_manifest["capsule_status"],
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
        "cost": _capsule_cost(arm),
    }


def build_manifest(arm: str, report_data: bytes) -> dict[str, Any]:
    implementation_paths = (
        "scripts/finalize_s2_12_arm_v1.py",
        "scripts/evaluate_s2_12_api_arm_v1.py",
        "scripts/verify_s2_12_api_arm_v1.py",
        "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py",
        "src/bpc_hybrid/s2_12_method_adapter.py",
        "configs/stage2_evaluator_s210_v3.json",
    )
    pred_dir = ROOT / "data/predictions" / ARM_DIRS[arm]
    result_dir = ROOT / "data/results" / ARM_DIRS[arm]
    capsule_cost = _capsule_cost(arm)
    return {
        "schema_version": f"s2_12_{arm}_evaluation_manifest@1.0.0",
        "status": f"verified_{arm}_arm_complete",
        "report": {
            "path": f"data/results/{ARM_DIRS[arm]}/evaluation.json",
            "sha256": hashlib.sha256(report_data).hexdigest(),
            "byte_size": len(report_data),
        },
        "bindings": {
            "prediction_manifest": {
                "path": f"data/predictions/{ARM_DIRS[arm]}/manifest.json",
                "sha256": _sha(pred_dir / "manifest.json"),
            },
            "predictions": {
                "path": f"data/predictions/{ARM_DIRS[arm]}/predictions.json",
                "sha256": _sha(pred_dir / "predictions.json"),
            },
            "cost": {
                "path": f"data/predictions/{ARM_DIRS[arm]}/cost.json",
                "sha256": _sha(pred_dir / "cost.json"),
            },
            "gold": {
                "path": "data/gold/stage2/s2_11_complex_corpus_formal_gold_v1.json",
                "sha256": EXPECTED_GOLD_SHA,
            },
            "strata": {
                "path": "outputs/reports/s2_11_proposal_report_v3.json",
                "sha256": EXPECTED_LEVELS_SHA,
            },
        },
        "implementation": {
            rel: _sha(ROOT / rel) for rel in implementation_paths
        },
        "replay_command": (
            "python formal_experiment/scripts/evaluate_s2_12_api_arm_v1.py "
            f"--arm {arm} --check"),
        "verification_command": (
            "python formal_experiment/scripts/verify_s2_12_api_arm_v1.py "
            f"--arm {arm}"),
        "safety": {
            "llm_api_calls": capsule_cost["llm_api_calls"],
            "network_calls": capsule_cost["network_calls"],
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("direct_llm", "sun_llm_fallback"),
                        required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--evaluate", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    arm = args.arm
    result_dir = ROOT / "data/results" / ARM_DIRS[arm]
    try:
        report_data = _json_bytes(build_report(arm))
        manifest_data = _json_bytes(build_manifest(arm, report_data))
        expected = {"evaluation.json": report_data, "manifest.json": manifest_data}
        if args.check:
            for name, data in expected.items():
                path = result_dir / name
                if not path.is_file() or path.read_bytes() != data:
                    raise EvaluationFail(f"evaluation replay differs: {name}")
            print(f"S2.12 {arm} EVALUATION REPLAY VERIFIED")
            return 0
        if result_dir.exists():
            raise EvaluationFail(
                f"refusing to overwrite existing evaluation: {result_dir}")
        stage = result_dir.parent / f".{result_dir.name}.staging-{os.getpid()}"
        if stage.exists():
            shutil.rmtree(stage)
        stage.mkdir(parents=True)
        try:
            for name, data in expected.items():
                (stage / name).write_bytes(data)
            stage.rename(result_dir)
        except Exception:
            shutil.rmtree(stage, ignore_errors=True)
            raise
    except (EvaluationFail, OSError) as exc:
        print(f"S2.12 {arm} evaluation refused: {exc}")
        return 2
    print(f"S2.12 {arm} evaluation published")
    print(f"report_sha256={hashlib.sha256(report_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

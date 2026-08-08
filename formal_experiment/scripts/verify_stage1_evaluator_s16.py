"""Verify the S1.6 evaluator contract on synthetic constants only."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_evaluation import (  # noqa: E402
    Stage1EvaluationError,
    evaluate_stage1,
    sha256_file,
    validate_stage1_report,
)
from evaluate_stage1_s16 import build_evidence  # noqa: E402


CONFIG = ROOT / "configs" / "stage1_evaluator_s16.json"
SCHEMA = ROOT / "configs" / "schemas" / "stage1_evaluation_report.schema.json"
IMPLEMENTATION = ROOT / "src" / "bpc_hybrid" / "stage1_evaluation.py"
RUNNER = ROOT / "scripts" / "evaluate_stage1_s16.py"
VERIFIER = Path(__file__).resolve()
FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s16_synthetic_semantic_reference.json"
BPMN_FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"
LABEL_MANIFEST = ROOT / "outputs" / "reports" / "s13_stage1_label_semantics_synthetic_v1.manifest.json"
ANNOTATION_MANIFEST = ROOT / "outputs" / "reports" / "s15_stage1_annotation_protocol_synthetic_v1.manifest.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s16_stage1_evaluator_contract_synthetic_v1.manifest.json"


def _run(
    evaluator_contract: dict,
    label_contract: dict,
    process_record: dict,
    gold_semantics: dict,
    attempts: list[dict],
) -> dict:
    return evaluate_stage1(
        gold_process_records=[process_record],
        gold_semantics=gold_semantics,
        attempts=attempts,
        label_contract=label_contract,
        evaluator_contract=evaluator_contract,
        scope="synthetic_contract_verification",
    )


def verify() -> dict:
    evaluator_contract, label_contract, process_record, evidence = build_evidence()
    gold_semantics, attempts = evidence
    report = _run(
        evaluator_contract,
        label_contract,
        process_record,
        gold_semantics,
        attempts,
    )
    if not validate_stage1_report(report).valid:
        raise Stage1EvaluationError("S1.6 generated report failed schema validation")
    p0 = report["methods"]["P0"]
    p1 = report["methods"]["P1"]
    if (
        p0["structure"]["micro"] != {
            "tp": 8,
            "fp": 0,
            "fn": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
        }
        or p1["structure"]["micro"] != p0["structure"]["micro"]
    ):
        raise Stage1EvaluationError("S1.6 synthetic structure constants changed")
    if p0["semantics"]["micro"] != {
        "tp": 0,
        "fp": 0,
        "fn": 12,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tn": 6,
        "exact_value_accuracy": 1 / 3,
    } or p0["semantic_triple_exact_accuracy"] != 1 / 6:
        raise Stage1EvaluationError("S1.6 synthetic P0 constants changed")
    if p1["semantics"]["micro"] != {
        "tp": 10,
        "fp": 1,
        "fn": 2,
        "precision": 10 / 11,
        "recall": 10 / 12,
        "f1": 20 / 23,
        "tn": 5,
        "exact_value_accuracy": 15 / 18,
    } or p1["semantic_triple_exact_accuracy"] != 0.5:
        raise Stage1EvaluationError("S1.6 synthetic P1 constants changed")

    duplicate = attempts + [copy.deepcopy(attempts[0])]
    try:
        _run(evaluator_contract, label_contract, process_record, gold_semantics, duplicate)
    except Stage1EvaluationError as exc:
        if "duplicate attempt" not in str(exc):
            raise
    else:
        raise Stage1EvaluationError("duplicate attempt did not fail closed")
    terminal = copy.deepcopy(attempts)
    terminal[1]["process_record"] = None
    terminal[1]["label_record"] = None
    terminal[1]["error"] = "synthetic_timeout"
    terminal_report = _run(
        evaluator_contract, label_contract, process_record, gold_semantics, terminal
    )
    if (
        terminal_report["methods"]["P1"]["terminal_errors"] != 1
        or terminal_report["methods"]["P1"]["structure_record_coverage"] != 0.0
        or terminal_report["methods"]["P1"]["label_record_coverage"] != 0.0
    ):
        raise Stage1EvaluationError("terminal error denominator semantics changed")
    invalid = copy.deepcopy(attempts)
    invalid[1]["label_record"]["unexpected"] = True
    invalid_report = _run(
        evaluator_contract, label_contract, process_record, gold_semantics, invalid
    )
    if (
        invalid_report["methods"]["P1"]["invalid_predictions"] != 1
        or invalid_report["methods"]["P1"]["structure_record_coverage"] != 1.0
        or invalid_report["methods"]["P1"]["label_record_coverage"] != 0.0
    ):
        raise Stage1EvaluationError("invalid label denominator semantics changed")
    tampered_report = copy.deepcopy(report)
    tampered_report["unexpected"] = True
    if validate_stage1_report(tampered_report).valid:
        raise Stage1EvaluationError("report additional property did not fail closed")
    try:
        evaluate_stage1(
            gold_process_records=[process_record],
            gold_semantics=gold_semantics,
            attempts=attempts,
            label_contract=label_contract,
            evaluator_contract=evaluator_contract,
            scope="formal",
        )
    except Stage1EvaluationError as exc:
        if "formal S1.6 evaluation is blocked" not in str(exc):
            raise
    else:
        raise Stage1EvaluationError("formal evaluator gate did not fail closed")

    artifacts = {
        "config": CONFIG,
        "schema": SCHEMA,
        "implementation": IMPLEMENTATION,
        "runner": RUNNER,
        "verifier": VERIFIER,
        "fixture": FIXTURE,
        "bpmn_fixture": BPMN_FIXTURE,
        "label_manifest": LABEL_MANIFEST,
        "annotation_manifest": ANNOTATION_MANIFEST,
    }
    return {
        "schema_version": "stage1_evaluator_verification_manifest@1.0.0",
        "run_id": "s16_stage1_evaluator_contract_synthetic_v1",
        "task_ids": ["S1.6"],
        "status": "succeeded_contract_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version()},
        "claim_boundary": evaluator_contract["claim_boundary"],
        "artifacts": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items()
        },
        "synthetic_report": report,
        "verification": {
            "exact_membership_verified": True,
            "structure_components": 8,
            "semantic_fields": 3,
            "structure_micro_tp_each_method": 8,
            "p0_semantic_micro_counts": {"tp": 0, "fp": 0, "fn": 12, "tn": 6},
            "p1_semantic_micro_counts": {"tp": 10, "fp": 1, "fn": 2, "tn": 5},
            "duplicate_attempt_rejected": True,
            "terminal_error_retained": True,
            "invalid_label_retained": True,
            "report_extra_property_rejected": True,
            "formal_scope_refused": True,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "synthetic_reference_is_human_gold": False,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "formal_performance_evaluation": False,
            "formal_results_written": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    target = args.manifest_out.resolve()
    if target.exists():
        raise Stage1EvaluationError(f"refusing to overwrite: {target}")
    manifest = verify()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "succeeded_contract_only", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

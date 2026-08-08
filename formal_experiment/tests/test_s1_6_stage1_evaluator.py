"""Regression tests for the S1.6 unified Stage 1 evaluator contract."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_evaluation import (  # noqa: E402
    Stage1EvaluationError,
    evaluate_stage1,
    load_evaluator_contract,
    validate_stage1_report,
)
from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    load_label_contract,
    render_label_semantics,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from formal_experiment.s1_evaluator_gate import (  # noqa: E402
    STAGE1_EVALUATOR_EXPECTATIONS,
    verify_stage1_evaluator_gate,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


EVALUATOR_CONFIG = ROOT / "configs" / "stage1_evaluator_s16.json"
LABEL_CONFIG = ROOT / "configs" / "stage1_label_semantics_s13.json"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"
REFERENCE = ROOT / "tests" / "fixtures" / "stage1" / "s16_synthetic_semantic_reference.json"


def _inputs() -> tuple[dict, dict, dict, dict, list[dict]]:
    evaluator_contract = load_evaluator_contract(EVALUATOR_CONFIG)
    label_contract = load_label_contract(LABEL_CONFIG)
    process_record = parse_bpmn_file(
        BPMN,
        contract=load_stage1_contract(STRUCTURAL_CONFIG),
    )
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    gold_semantics = {
        process_record["process_id"]: {
            item["activity_id"]: {
                "actor": item["actor"],
                "action": item["action"],
                "business_object": item["business_object"],
            }
            for item in reference["activities"]
        }
    }
    attempts = [
        {
            "method": method,
            "process_id": process_record["process_id"],
            "process_record": process_record,
            "label_record": render_label_semantics(
                process_record,
                baseline=method,
                contract=label_contract,
            ),
            "error": None,
        }
        for method in ("P0", "P1")
    ]
    return evaluator_contract, label_contract, process_record, gold_semantics, attempts


def _evaluate(attempts: list[dict], *, scope: str = "synthetic_contract_verification") -> dict:
    evaluator_contract, label_contract, process_record, gold_semantics, _ = _inputs()
    return evaluate_stage1(
        gold_process_records=[process_record],
        gold_semantics=gold_semantics,
        attempts=attempts,
        label_contract=label_contract,
        evaluator_contract=evaluator_contract,
        scope=scope,
    )


def test_s16_contract_freezes_metrics_membership_and_safety() -> None:
    contract = load_evaluator_contract(EVALUATOR_CONFIG)
    assert contract["methods"] == ["P0", "P1"]
    assert len(contract["structure_components"]) == 8
    assert contract["semantic_fields"] == ["actor", "action", "business_object"]
    assert contract["metric_rules"]["wrong_nonnull_value"] == (
        "one_false_positive_and_one_false_negative"
    )
    assert contract["safety"]["synthetic_reference_is_human_gold"] is False
    assert contract["safety"]["formal_performance_evaluation"] is False


def test_s16_expected_synthetic_structure_and_semantic_counts() -> None:
    _, _, _, _, attempts = _inputs()
    report = _evaluate(attempts)
    assert validate_stage1_report(report).valid
    assert report["methods"]["P0"]["structure"]["micro"]["tp"] == 8
    assert report["methods"]["P1"]["structure"]["micro"]["f1"] == 1.0
    assert report["methods"]["P0"]["semantics"]["micro"] == {
        "tp": 0,
        "fp": 0,
        "fn": 12,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "tn": 6,
        "exact_value_accuracy": 1 / 3,
    }
    assert report["methods"]["P1"]["semantics"]["micro"]["tp"] == 10
    assert report["methods"]["P1"]["semantics"]["micro"]["fp"] == 1
    assert report["methods"]["P1"]["semantics"]["micro"]["fn"] == 2
    assert report["methods"]["P1"]["semantic_triple_exact_accuracy"] == 0.5


def test_exact_membership_duplicates_and_formal_scope_fail_closed() -> None:
    _, _, _, _, attempts = _inputs()
    with pytest.raises(Stage1EvaluationError, match="duplicate attempt"):
        _evaluate(attempts + [copy.deepcopy(attempts[0])])
    with pytest.raises(Stage1EvaluationError, match="exact method/process product"):
        _evaluate(attempts[:-1])
    with pytest.raises(Stage1EvaluationError, match="formal S1.6 evaluation is blocked"):
        _evaluate(attempts, scope="formal")


def test_terminal_and_invalid_attempts_remain_in_denominators() -> None:
    _, _, _, _, attempts = _inputs()
    terminal = copy.deepcopy(attempts)
    terminal[1].update(
        {"process_record": None, "label_record": None, "error": "synthetic_timeout"}
    )
    report = _evaluate(terminal)["methods"]["P1"]
    assert report["terminal_errors"] == 1
    assert report["structure_record_coverage"] == 0.0
    assert report["label_record_coverage"] == 0.0
    invalid = copy.deepcopy(attempts)
    invalid[1]["label_record"]["unexpected"] = True
    report = _evaluate(invalid)["methods"]["P1"]
    assert report["invalid_predictions"] == 1
    assert report["structure_record_coverage"] == 1.0
    assert report["label_record_coverage"] == 0.0


def test_report_schema_and_runner_contract() -> None:
    _, _, _, _, attempts = _inputs()
    report = _evaluate(attempts)
    extra = copy.deepcopy(report)
    extra["unexpected"] = True
    assert validate_stage1_report(extra).valid is False
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "evaluate_stage1_s16.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert '"schema_version": "stage1_evaluation_report@1.0.0"' in completed.stdout
    assert '"scope": "synthetic_contract_verification"' in completed.stdout


def test_s16_gate_status_and_audit_are_protocol_only() -> None:
    gate = verify_stage1_evaluator_gate(ROOT)
    assert gate["evaluator_ready"] is True
    assert gate["formal_results_ready"] is False
    failed = verify_stage1_evaluator_gate(
        ROOT,
        expectations=replace(STAGE1_EVALUATOR_EXPECTATIONS, config_sha256="0" * 64),
    )
    assert failed["evaluator_ready"] is False
    assert "stage1_evaluator_config_hash_mismatch" in failed["blockers"]
    status = collect_status()
    audit = collect_project_audit()
    passes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["stage1_evaluator_verified"] is True
    assert status["stage1_formal_results_ready"] is False
    assert "stage1_evaluator_contract_verified" in passes

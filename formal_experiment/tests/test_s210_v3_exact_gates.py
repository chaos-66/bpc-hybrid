"""Exact-lock tests for evaluator v3 and immutable B0 re-evaluation."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.s2_10_evaluator_v3_gate import (  # noqa: E402
    S210_V3_EXPECTATIONS,
    S27_B0_V3_EXPECTATIONS,
    verify_s2_10_evaluator_v3_gate,
    verify_s2_7_b0_v3_gate,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


def test_s210_v3_exact_gate_is_ready_and_paper_targeting_is_false() -> None:
    result = verify_s2_10_evaluator_v3_gate(ROOT)
    assert result["ready"] is True
    assert result["blockers"] == []
    assert result["paper_score_targeting_used"] is False
    assert result["main_data_results_ready"] is False


def test_s210_v3_exact_gate_rejects_hash_drift() -> None:
    wrong = replace(S210_V3_EXPECTATIONS, implementation_sha256="0" * 64)
    result = verify_s2_10_evaluator_v3_gate(ROOT, expectations=wrong)
    assert result["ready"] is False
    assert "s210_v3_implementation_hash_mismatch" in result["blockers"]


def test_b0_v3_exact_gate_locks_corrected_development_values() -> None:
    result = verify_s2_7_b0_v3_gate(ROOT)
    assert result["ready"] is True
    assert result["sample_count"] == 150
    assert result["modality_micro"] == {
        "precision": 0.39473684210526316,
        "recall": 0.45454545454545453,
        "f1": 0.4225352112676056,
    }
    assert result["modality_macro_f1"] == 0.4068011167509406
    assert result["formal_performance_result"] is False
    assert result["models_rerun"] is False


def test_b0_v3_exact_gate_rejects_result_hash_drift() -> None:
    wrong = replace(S27_B0_V3_EXPECTATIONS, all150_report_sha256="0" * 64)
    result = verify_s2_7_b0_v3_gate(ROOT, expectations=wrong)
    assert result["ready"] is False
    assert "s27_b0_v3_all150_report_hash_mismatch" in result["blockers"]


def test_status_and_audit_publish_v3_as_development_not_formal() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["s2_10_evaluator_v3_verified"] is True
    assert status["s2_7_b0_v3_development_verified"] is True
    assert status["formal_gold_publication_ready"] is False
    assert status["final_experiment_ready"] is False
    assert "s2_10_method_independent_alignment_and_b0_v3_verified" in pass_codes

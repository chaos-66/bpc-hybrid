from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bpc_hybrid.s212_analysis import (
    S212AnalysisError,
    analyze_primary_family,
    assign_error_categories,
    holm_adjust,
    load_analysis_protocol,
    select_qualitative_cases,
    summarize_strata,
    validate_observations,
)
from formal_experiment.s2_12_analysis_gate import verify_s2_12_analysis_gate


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "configs" / "s212_analysis_protocol.json"
FIXTURE = ROOT / "tests" / "fixtures" / "s212_analysis" / "s212_synthetic_counts.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_protocol_and_primary_family_are_frozen() -> None:
    protocol = load_analysis_protocol(PROTOCOL)
    fixture = _fixture()
    report = analyze_primary_family(
        fixture["observations"], protocol, dataset_id=fixture["dataset_id"]
    )
    assert report["sample_count"] == 6
    assert report["hypothesis_count"] == 12
    action = report["hypotheses"]["d1_minus_b0::action_strict_exact_f1"]
    assert action["candidate_point"] == 1.0
    assert action["reference_point"] == 0.25
    assert action["delta_ci_low"] <= action["delta"] <= action["delta_ci_high"]


def test_strata_small_n_and_leakage_fail_closed() -> None:
    protocol = load_analysis_protocol(PROTOCOL)
    fixture = _fixture()
    summary = summarize_strata(
        fixture["observations"],
        protocol,
        method="direct_llm",
        endpoint_id="action_strict_exact_f1",
    )
    assert all(item["sample_count"] == 2 for item in summary.values())
    assert all(item["interval_estimable"] is False and item["interval"] is None for item in summary.values())
    leaked = copy.deepcopy(fixture["observations"])
    leaked[0]["test_metric"] = 0.99
    with pytest.raises(S212AnalysisError, match="forbidden"):
        validate_observations(leaked, protocol)


def test_missing_method_and_unknown_error_fail_closed() -> None:
    protocol = load_analysis_protocol(PROTOCOL)
    fixture = _fixture()
    missing = copy.deepcopy(fixture["observations"])
    del missing[0]["methods"]["direct_llm"]
    with pytest.raises(S212AnalysisError, match="all three"):
        validate_observations(missing, protocol)
    with pytest.raises(S212AnalysisError, match="unknown error"):
        assign_error_categories(["invented_after_results"], protocol)


def test_error_priority_and_case_selection_are_deterministic() -> None:
    protocol = load_analysis_protocol(PROTOCOL)
    fixture = _fixture()
    assigned = assign_error_categories(
        ["exception_scope_or_omission", "runtime_api_error"], protocol
    )
    assert assigned == {
        "primary": "runtime_api_error",
        "all": ["runtime_api_error", "exception_scope_or_omission"],
    }
    selected = select_qualitative_cases(fixture["error_cases"], protocol)
    assert len(selected) == 3
    assert selected == select_qualitative_cases(list(reversed(fixture["error_cases"])), protocol)


def test_holm_adjustment_is_monotone_and_family_wide() -> None:
    adjusted = holm_adjust({"a": 0.001, "b": 0.01, "c": 0.2}, alpha=0.05)
    by_rank = sorted(adjusted.values(), key=lambda item: item["rank"])
    assert [item["holm_adjusted_p"] for item in by_rank] == [0.003, 0.02, 0.2]
    assert [item["reject_at_alpha"] for item in by_rank] == [True, True, False]


def test_exact_hash_gate_is_green() -> None:
    result = verify_s2_12_analysis_gate(ROOT)
    assert result["ready"] is True, result["errors"]
    assert result["formal_results_ready"] is False

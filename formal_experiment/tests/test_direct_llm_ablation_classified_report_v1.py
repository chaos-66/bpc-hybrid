# -*- coding: utf-8 -*-
"""Classification tests for the existing Barrientos D/E results (zero API)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_direct_llm_ablation_classified_report_v1 as builder


def test_existing_results_are_split_into_four_scientific_categories():
    report = builder.build_report()
    assert set(report["categories"]) == {
        "1_core_internal_one_factor_ablation",
        "2_multi_module_sensitivity_not_core_ablation",
        "3_module_replacement",
        "4_external_native_and_shared_target_comparison",
    }
    core = report["categories"]["1_core_internal_one_factor_ablation"]
    assert core["baseline"]["arm"] == "D-full-0813"
    assert core["single_removed_component"]["arm"] == \
        "D-no-fewshot-0813"
    assert core["status"] == "partially_complete"


def test_minimal_and_barrientos_style_are_not_mislabelled_as_core_ablation():
    report = builder.build_report()
    core_text = json.dumps(
        report["categories"]["1_core_internal_one_factor_ablation"])
    assert "D-minimal-0813" not in core_text
    assert "D-barrientos-style-0813" not in core_text
    assert report["categories"][
        "2_multi_module_sensitivity_not_core_ablation"]["arm"] == \
        "D-minimal-0813"
    replacement = report["categories"]["3_module_replacement"]
    assert replacement["estg150_prompt_contract_replacement"][
        "replacement_arm"] == "D-barrientos-style-0813"


def test_core_ablation_metrics_match_the_locked_table():
    report = builder.build_report()
    core = report["categories"]["1_core_internal_one_factor_ablation"]
    full = core["baseline"]["metrics"]
    removed = core["single_removed_component"]
    assert abs(full["overall"]["f1"] - 0.7719075848848173) < 1e-12
    assert full["nonempty_canonical_clause_rate"] == 0.986667
    assert removed["metrics"]["overall"]["f1"] == 0.0
    assert removed["metrics"]["parse_success_rate"] == 0.98
    assert removed["metrics"]["nonempty_canonical_clause_rate"] == 0.0
    assert removed["delta_vs_full"]["overall_f1"] == -0.772


def test_module_swap_and_shared_target_claims_keep_evaluators_separate():
    report = builder.build_report()
    replacement = report["categories"]["3_module_replacement"][
        "same_data_barrientos_module_swap"]
    assert replacement["full"]["overall_f1"] == {
        "mean": 0.874, "sd": 0.003, "min": 0.869, "max": 0.878}
    assert replacement["replacement"]["overall_f1"]["mean"] == 0.0
    external = report["categories"][
        "4_external_native_and_shared_target_comparison"]
    shared = external["shared_three_class_modality"]["arms"]
    assert shared["BARR-FULL"]["macro_f1"]["mean"] == 0.89
    assert shared["OURS-FULL"]["macro_f1"]["mean"] == 0.822
    assert "must never be directly ranked" in external[
        "comparability_limit"]
    assert report["bottom_line"]["global_winner_claim_allowed"] is False
    assert report["bottom_line"][
        "stage3_performance_claim_allowed_from_this_run"] is False
    assert report["scope"]["stage3_bpmn_evaluation_performed"] is False


def test_run_accounting_is_complete_and_classified_exactly_once():
    report = builder.build_report()
    accounting = report["run_accounting"]
    assert accounting["actual_calls"] == accounting["planned_calls"] == 1140
    assert sum(accounting["call_allocation"].values()) == 1140
    assert accounting["input_tokens"] == 2_428_816
    assert accounting["output_tokens"] == 732_374
    assert accounting["off_peak_estimate_usd"] == 3.05311908
    assert report["scope"]["new_api_calls_for_this_report"] == 0
    assert report["scope"]["gold_read_for_this_report"] is False


def test_pending_list_contains_only_explicitly_unrun_internal_removals():
    report = builder.build_report()
    pending = report["not_yet_run_core_internal_ablations"]
    names = {item["component_id"] for item in pending}
    assert names == {
        "field_definitions_and_six_element_schema",
        "span_evidence_anchoring",
        "strict_json_schema_discipline",
        "canonicalizer",
        "validator",
        "output_adapter",
    }
    assert all("not_run" in item["status"] for item in pending)


def test_checked_in_reports_are_byte_reproducible():
    report = builder.build_report()
    expected_json = json.dumps(
        report, ensure_ascii=False, indent=2) + "\n"
    expected_md = builder.to_markdown(report) + "\n"
    assert builder.REPORT_JSON.read_text(encoding="utf-8") == expected_json
    assert builder.REPORT_MD.read_text(encoding="utf-8") == expected_md
    assert "只有其中 Full vs 去 few-shot" in expected_md
    assert "不能把两边 native F1 强行排成总榜" in expected_md

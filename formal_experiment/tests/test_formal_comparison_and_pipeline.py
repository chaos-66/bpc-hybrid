"""Focused tests for the formal three-method comparison report, S2.12
descriptive error analysis, S2.11 qualification dry-run and S2.13 gap capsule.

Covers:
- comparison report structure (three methods, five-field main view,
  modality labels separate, zero new calls, no historical aggregate mixing)
- comparison report independent verifier passes
- S2.12 analysis marked retrospective/not-preregistered with correct
  dependency
- S2.11 dry-run: not applied, modality 3->4 boundary, no authorization
  sentence emitted, statuses unchanged
- S2.13 gap capsule: semantics clarification + S2.13/S1.7/S3.7 not complete
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str) -> dict:
    return json.loads((ROOT / "outputs" / "reports" / name)
                      .read_text(encoding="utf-8"))


def test_comparison_report_structure() -> None:
    report = _load("stage2_formal_three_method_comparison_v1.json")
    assert report["schema_version"] == \
        "stage2_formal_three_method_comparison@1.0.0"
    assert set(report["methods"]) == {"sun_rule_only", "direct_llm",
                                      "sun_llm_fallback"}
    for mid, info in report["methods"].items():
        assert set(info["main_view_coarse_five_fields"]) == {
            "actor", "action", "condition", "constraint", "exception"}
        assert "accuracy" in info["modality_labels"]
        assert "per_class" in info["modality_labels"]
        assert info["new_llm_calls"] == 0
        assert info["claim_scope"] == "formal"
    assert report["methods"]["sun_llm_fallback"]["role"] == "comparison_arm_only"
    assert report["zero_api"]["new_llm_api_calls"] == 0
    assert report["zero_api"]["historical_calls_total"] == 300
    assert "delta_matrix" in report
    assert "development provenance" in report["evaluation_contract"][
        "historical_six_field_aggregate"]
    assert "unavailable" in report["evaluation_contract"][
        "modality_evidence_span_metrics"]
    assert report["evaluation_contract"]["authorized"] is True
    assert "three_method_ready_not_pipeline_complete" in report["conclusions"]


def test_comparison_report_verifier_passes() -> None:
    verifier = ROOT / "outputs" / "reports" / "verify_stage2_formal_comparison_v1.py"
    assert verifier.exists()
    r = subprocess.run([sys.executable, str(verifier)], capture_output=True,
                       text=True)
    assert r.returncode == 0
    assert "VERIFIED" in r.stdout


def test_s2_12_analysis_retrospective_and_dependency() -> None:
    analysis = _load("s2_12_formal_descriptive_error_analysis_v1.json")
    assert analysis["retrospective"] is True
    assert analysis["preregistered"] is False
    assert "NOT preregistered" in analysis["note"]
    assert "S2.11" in analysis["dependency"]["full_doD_blocked_on"]
    assert analysis["zero_api"]["new_llm_api_calls"] == 0
    assert set(analysis["per_method"]) == {"sun_rule_only", "direct_llm",
                                           "sun_llm_fallback"}
    for mid, info in analysis["per_method"].items():
        assert set(info["fields"]) == {"actor", "action", "condition",
                                       "constraint", "exception"}
    assert "observations" in analysis


def test_s2_11_dry_run_not_applied() -> None:
    pkg = _load("s2_11_data_qualification_mapping_dry_run.json")
    assert pkg["status"] == "dry_run_not_applied"
    assert pkg["candidate_data"]["barrientos_2026"]["local_availability"] is True
    assert pkg["candidate_data"]["stage1_gdpr7"]["bpmn_count"] >= 1
    assert "3 classes" in pkg["schema_mapping"]["modality_incompatibility"]
    assert pkg["human_gold_required"] is True
    assert pkg["authorization_sentence"] is None
    assert "reached this round" in pkg["authorization_sentence_reason"].lower()
    assert pkg["complexity_definitions_candidates"]["status"].startswith(
        "CANDIDATES ONLY")
    assert any("never be treated as Sun-compatible Gold" in g
               for g in pkg["guards"])
    assert pkg["zero_api"]["new_llm_api_calls"] == 0


def test_s2_13_gap_capsule_semantics() -> None:
    gap = _load("s2_13_stage2_freeze_gap_capsule.json")
    assert "THREE-METHOD FORMAL" in gap["semantics_clarification"]
    assert "does NOT mean S2.13" in gap["semantics_clarification"]
    assert gap["remaining"]["s2_11"] == "blocked (complex legal corpus freeze + G0.5 + Barrientos adapter qualification)"
    assert "NOT complete" in gap["remaining"]["s2_13_full_DoD"]
    assert "blocked (true Gold Process Records)" == gap["remaining"]["s1_7"]
    assert "formal Oracle NOT started" in gap["remaining"]["s3_7"]
    assert gap["no_pseudo_oracle"] is True
    assert gap["zero_api"]["new_llm_api_calls"] == 0
    assert gap["completed"]["three_method_formal_capsules"]["sun_rule_only"]
    assert gap["completed"]["method_gates"]["direct_llm"] == "ready"


def test_s2_10_and_s2_12_rows_updated() -> None:
    src = (ROOT / "docs" / "MASTER_PIPELINE.md").read_text(encoding="utf-8")
    assert "| S2.10 | 主数据组件评价 | S2.2/S2.6-S2.9 | **verified（2026-08-11" in src
    assert "| S2.12 | 复杂度分层与误差分析 | S2.10/S2.11 | **partial；zero-API arm complete；两个 API arms pending explicit authorization（2026-08-18）" in src
    assert "direct_llm=36、sun_llm_fallback=27" in src
    assert "这是**单一 zero-API arm**，不是三方法比较" in src
    assert "| S2.13 | Stage 2 冻结 | S2.1-S2.12 | **blocked only on remaining S2.12 DoD**" in src

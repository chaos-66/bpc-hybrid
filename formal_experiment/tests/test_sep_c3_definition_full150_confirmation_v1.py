# -*- coding: utf-8 -*-
"""Focused offline tests for the frozen R_DEF full-150 confirmation artifacts.

No API call is made by these tests.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
for candidate in (SCRIPTS, SRC):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import prepare_sep_c3_definition_full150_confirmation_v1 as prep  # noqa: E402
import run_sep_c3_definition_full150_confirmation_v1 as runner  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_schedule_membership_and_single_arm():
    schedule = _read_json(prep.SCHEDULE_PATH)
    assert schedule["status"] == "FROZEN_BEFORE_NEW_API"
    assert schedule["arm"] == "R_DEF"
    assert schedule["planned_calls"] == 150
    assert len(schedule["entries"]) == 150
    assert [entry["sample_id"] for entry in schedule["entries"]] == schedule[
        "sample_membership_order"
    ]
    assert {entry["arm"] for entry in schedule["entries"]} == {"R_DEF"}
    assert len({entry["sample_id"] for entry in schedule["entries"]}) == 150


def test_prompt_budget_and_generation_config_are_frozen():
    budget = _read_json(prep.BUDGET_PATH)
    prompt = dr.render_definition_prompt("R_DEF")
    assert budget["planned_calls"] == 150
    assert budget["call_cap"] == 150
    assert budget["calls_per_arm"] == {"R_DEF": 150}
    assert budget["model"]["id"] == "deepseek-v4-pro"
    assert budget["model"]["documented_release"] == "DeepSeek-V4-Pro-0813"
    assert budget["inference"] == {
        "temperature": 0.0,
        "top_p": 1.0,
        "max_tokens": 4096,
        "retry": 0,
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": None,
    }
    assert budget["prompt_binding"]["system_sha256"] == prep._sha256_text(
        prompt.system_prompt
    )
    assert budget["prompt_binding"]["composition_sha256"] == prompt.composition_sha256


def test_current_contract_A_baseline_is_frozen_before_r_def():
    manifest = _read_json(prep.A_OUT_DIR / "manifest.json")
    assert manifest["status"] == "FROZEN_BEFORE_R_DEF_EVALUATION_INSPECTION"
    assert abs(
        manifest["current_contract"]["five_field_mean_f1"]
        - prep.EXPECTED_A_FIVE_FIELD_MEAN_F1
    ) < 1e-12
    assert manifest["legacy_label"]["must_not_be_directly_compared_to_r_def"] is True


def test_evaluator_dry_check_used_all_150_samples():
    dry = _read_json(prep.DRY_CHECK_PATH)
    assert dry["status"] == "PASS"
    assert dry["prediction_envelope_count"] == 150
    assert dry["unique_sample_ids"] == 150
    assert dry["membership_check"]["status"] == "pass"


def test_completed_execution_has_exactly_150_calls_and_no_transport_failure():
    summary = _read_json(runner.OUT_DIR / "execution_summary.json")
    assert summary["complete"] is True
    assert summary["actual_calls"] == 150
    assert summary["aborted"] is False
    assert summary["budget_gate"]["calls_made"] == 150
    assert summary["budget_gate"]["aborted"] is False
    raw = [
        json.loads(line)
        for line in (
            runner.OUT_DIR / "R_DEF" / "repeat-01" / "raw_responses.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(raw) == 150
    assert {row["request_status"] for row in raw} == {"ok"}

    assert summary["official_evaluation"]["denominator"] == 150
    assert summary["official_evaluation"]["failed_count"] == 14
    assert abs(
        summary["official_evaluation"]["coarse_five_field_mean_f1"]
        - 0.7246613248193036
    ) < 1e-12


def test_analysis_reports_comparable_baseline_and_non_heldout_scope():
    report = _read_json(
        ROOT / "outputs" / "reports"
        / "sep_c3_definition_full150_confirmation_v1_analysis.json"
    )
    assert report["sample_count"] == 150
    assert report["official_metrics"]["coarse_five_field_mean_f1"]["A"] == (
        prep.EXPECTED_A_FIVE_FIELD_MEAN_F1
    )
    assert "not independent held-out" in report["scope"]
    assert report["bootstrap"]["span"]["resamples"] == 10_000
    assert report["bootstrap"]["span"]["comparisons"][
        "coarse_five_field_mean_f1"
    ]["ci95_percentile"][0] < report["bootstrap"]["span"]["comparisons"][
        "coarse_five_field_mean_f1"
    ]["ci95_percentile"][1]

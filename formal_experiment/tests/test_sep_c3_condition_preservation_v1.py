# -*- coding: utf-8 -*-
"""Focused zero-API tests for SEP-C3 condition-preservation preparation."""

from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.modular_refinement_prompt as old_rp  # noqa: E402
import bpc_hybrid.sep_c3_condition_preservation_prompt as cp  # noqa: E402
import analyze_sep_c3_condition_preservation_bootstrap_v1 as bs  # noqa: E402
import prepare_sep_c3_condition_preservation_v1 as prep  # noqa: E402
import run_sep_c3_targeted_refinement_v1 as old_runtime  # noqa: E402


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_base_and_rc1_match_old_b_and_old_d_actual_prompts():
    old_b = old_rp.render_refinement_prompt("B")
    old_d = old_rp.render_refinement_prompt("D")
    base = cp.render_condition_preservation_prompt("BASE")
    rc1 = cp.render_condition_preservation_prompt("RC1")

    assert base.system_prompt == old_b.system_prompt
    assert base.user_prompt_template == old_b.user_prompt_template
    assert base.composition_sha256 == old_b.composition_sha256
    assert rc1.system_prompt == old_d.system_prompt
    assert rc1.user_prompt_template == old_d.user_prompt_template
    assert rc1.composition_sha256 == old_d.composition_sha256


def test_rc_keep_is_exactly_rc1_plus_one_sentence():
    rc1 = cp.render_condition_preservation_prompt("RC1")
    keep = cp.render_condition_preservation_prompt("RC_KEEP")
    expected_system = (
        rc1.system_prompt + "\n\n" + cp.CONDITION_PRESERVATION_TEXT
    )

    assert keep.system_prompt == expected_system
    assert keep.user_prompt_template == rc1.user_prompt_template
    assert keep.system_prompt.count(cp.CONDITION_PRESERVATION_TEXT) == 1
    assert keep.composition_sha256 == _sha256_text(
        keep.system_prompt
        + "\n\n<!--USER-->\n\n"
        + keep.user_prompt_template
    )


def test_base_and_rc1_request_bodies_match_old_b_and_old_d():
    sample = old_runtime.core.samples(150)[0]
    sid = str(sample["sample_id"])
    text = str(sample["text"])
    base = prep._request_body("BASE", sid, text)
    rc1 = prep._request_body("RC1", sid, text)
    old_b = old_runtime.request_body("B", sid, text)
    old_d = old_runtime.request_body("D", sid, text)

    assert prep._canonical_body_bytes(base) == prep._canonical_body_bytes(old_b)
    assert prep._canonical_body_bytes(rc1) == prep._canonical_body_bytes(old_d)


def test_old_r_a_and_r_c_source_text_hashes_are_unchanged():
    assert _sha256_text(old_rp.R_A_TEXT) == (
        "0d1a0b131c88394304ac22d510740694fed5069f9cc8b4b9612fd33285e789c9"
    )
    assert _sha256_text(old_rp.R_C_TEXT) == (
        "cfcbbc45e278ab3ad4fad8784c5a6bcc551c0b51a2e1833ac2c4e56d0571fcae"
    )


def test_generated_prompt_files_and_manifest_exist_if_prepared():
    for arm in cp.ARMS:
        path = cp.generated_path(arm)
        assert path.is_file(), path
        assert path.read_text(encoding="utf-8") == cp.render_condition_preservation_prompt(
            arm
        ).to_markdown()
    manifest_path = cp.generated_manifest_path()
    assert manifest_path.is_file()


def _field_counts(**values: int) -> dict[str, dict[str, int]]:
    field = {
        "ground_truth": 0,
        "extracted": 0,
        "matched_predictions": 0,
        "matched_ground_truth": 0,
    }
    field.update(values)
    return {
        name: dict(field)
        for name in bs.SPAN_FIELDS
    }


def test_metrics_from_field_counts_recompute_not_average():
    counts = _field_counts(
        ground_truth=2,
        extracted=3,
        matched_predictions=2,
        matched_ground_truth=1,
    )
    metrics = bs._metrics_from_field_counts(counts)

    # Precision=2/3, recall=1/2, F1=4/7 for every field.
    assert abs(float(metrics["condition_f1"]) - (4.0 / 7.0)) < 1e-12
    assert abs(float(metrics["condition_fp"]) - 1.0) < 1e-12
    assert abs(float(metrics["condition_missed"]) - 1.0) < 1e-12
    assert abs(float(metrics["coarse_five_field_mean_f1"]) - (4.0 / 7.0)) < 1e-12


def test_percentile_linear_interpolation():
    assert bs._percentile([0.0, 1.0], 0.5) == 0.5
    assert bs._percentile([0.0, 1.0], 0.0) == 0.0
    assert bs._percentile([0.0, 1.0], 1.0) == 1.0


def test_paired_bootstrap_uses_same_sample_ids_and_is_deterministic():
    sample_order = ["s1", "s2", "s3"]
    counts_by_arm: dict[str, dict[str, dict[str, dict[str, int]]]] = {
        arm: {sid: _field_counts() for sid in sample_order}
        for arm in bs.ARMS
    }
    # RC_KEEP has extra matched condition counts on every sample.
    for sid in sample_order:
        counts_by_arm["RC_KEEP"][sid]["condition"]["ground_truth"] = 1
        counts_by_arm["RC_KEEP"][sid]["condition"]["extracted"] = 1
        counts_by_arm["RC_KEEP"][sid]["condition"]["matched_predictions"] = 1
        counts_by_arm["RC_KEEP"][sid]["condition"][
            "matched_ground_truth"
        ] = 1
    result = bs.paired_bootstrap(
        sample_order, counts_by_arm, resamples=20, seed=20260919
    )
    assert result["seed"] == 20260919
    payload = result["comparisons"]["RC_KEEP-RC1_condition_f1"]
    assert payload["contains_zero"] is False
    assert len(payload["difference_values"]) == 20
    assert payload["ci95_percentile"][0] > 0.0


def test_processing_failure_counts_keep_separate_stages():
    rows = {
        "BASE": [
            {
                "request_status": "failed",
                "api_call_status": "ok",
                "output_parse_status": "failed",
                "input_binding_status": "not_attempted",
                "canonical_validation_status": "not_attempted",
            },
            {
                "request_status": "ok",
                "api_call_status": "ok",
                "output_parse_status": "passed",
                "input_binding_status": "passed",
                "canonical_validation_status": "passed",
            },
        ],
        "RC1": [],
        "RC_KEEP": [],
    }
    counts = bs._processing_failure_counts(rows)
    assert counts["BASE"]["transport_failures"] == 0
    assert counts["BASE"]["output_processing_failures"] == 1
    assert counts["BASE"]["status_counts"]["output_parse_status"] == {
        "failed": 1,
        "passed": 1,
    }


def test_prepare_contract_is_zero_api_and_not_authorized():
    assert prep.PLANNED_CALLS == 450
    assert prep.CALL_CAP == 450
    assert prep.SCHEDULE_SEED == 20260919
    assert prep.BOOTSTRAP_SEED == 20260919
    assert prep.BOOTSTRAP_RESAMPLES == 10000
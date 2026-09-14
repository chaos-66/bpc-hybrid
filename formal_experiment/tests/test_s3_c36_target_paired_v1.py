# -*- coding: utf-8 -*-
"""Focused tests for C36/Winter target-paired compatibility and comparison."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_c36_target_paired_v1 import (  # noqa: E402
    audit_c36_winter,
    compare_target_paired,
    control_check_from_scores,
    derive_target_paired_rows,
    read_json,
    read_jsonl,
    variant_check_from_scores_detail,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402

TYPES = list(EXTENDED_TYPES)


def _full_scores(**overrides):
    scores = {
        target: {"observable": True, "score": 0.9, "reason": None,
                 "exact_contradiction": None}
        for target in TYPES
    }
    scores.update(overrides)
    return scores


def _detail(**overrides):
    detail = {
        target: {"observable": True, "violation": False,
                 "reason": "test_negative"}
        for target in TYPES
    }
    detail.update(overrides)
    return detail


def test_variant_explicit_boolean_and_unobservable_unknown():
    detail = _detail()
    detail["required_condition_not_enforced"] = {
        "observable": True, "violation": True, "reason": "condition_absence"}
    detail["exception_not_handled"] = {"observable": False,
                                       "reason": "empty_rule_exception"}
    condition = variant_check_from_scores_detail(detail, "required_condition_not_enforced")
    exception = variant_check_from_scores_detail(detail, "exception_not_handled")
    assert condition["observable"] is True and condition["violation"] is True
    assert exception["observable"] is False and exception["violation"] is None
    assert exception["field_gap"] is False


def test_control_check_uses_frozen_rule_not_unified_label():
    scores = _full_scores()
    scores["prohibited_action_present"] = {
        "observable": True, "score": 0.9, "reason": None,
        "exact_contradiction": None,
    }
    scores["required_condition_not_enforced"] = {
        "observable": False, "score": None, "reason": "no_condition_candidates",
        "exact_contradiction": None,
    }
    check = control_check_from_scores(scores, "prohibited_action_present", 0.5)
    assert check["observable"] is True and check["violation"] is True
    unknown = control_check_from_scores(scores, "required_condition_not_enforced", 0.5)
    assert unknown["observable"] is False and unknown["violation"] is None
    # The unified single-label prediction is never an input to this function.
    assert "unified_predicted_raw" not in scores


def test_derive_target_paired_rows_expands_both_sides():
    row = {
        "item_id": "v1",
        "expected_violation": "constraint_violated",
        "gamma_ext": 0.5,
        "scores_detail": _detail(constraint_violated={
            "observable": True, "violation": True, "reason": "test"}),
        "control_scores": _full_scores(),
    }
    rows = derive_target_paired_rows([row])
    assert len(rows) == 2
    assert {r["side"] for r in rows} == {"variant", "control"}
    assert all(set(r["checks"]) == set(TYPES) for r in rows)
    control = next(r for r in rows if r["side"] == "control")
    assert control["expected_label"] in (None, "none")


def test_audit_detects_missing_fields_and_label_mismatch():
    panel = {
        "schema_version": "mini-panel",
        "variants": [
            {"variant_id": "v1", "expected_violation": "constraint_violated"},
            {"variant_id": "v2", "expected_violation": "exception_not_handled"},
        ],
    }
    c36_rows = [{
        "item_id": "v1",
        "expected_violation": "constraint_violated",
        "gold_visible": False,
        "gamma_ext": 0.5,
        "scores_detail": {
            **{t: {"observable": False, "reason": "empty"} for t in TYPES},
            "constraint_violated": {"observable": True, "reason": "missing_boolean"},
        },
        "control_scores": _full_scores(),
    }]
    audit = audit_c36_winter(c36_rows, panel)
    assert audit["sample_sets"]["missing_in_c36"] == ["v2"]
    assert audit["can_build_target_paired"] is False
    assert any(gap["scope"] == "variant" for gap in audit["field_gaps"])


def test_comparison_uses_target_paired_protocol_and_explicit_unknowns():
    panel = {
        "schema_version": "mini-panel",
        "variants": [
            {"variant_id": "v1", "expected_violation": "constraint_violated"},
        ],
    }
    c36_row = {
        "item_id": "v1",
        "expected_violation": "constraint_violated",
        "gamma_ext": 0.5,
        "scores_detail": _detail(constraint_violated={
            "observable": True, "violation": True, "reason": "test"}),
        "control_scores": _full_scores(),
    }
    c36_rows = derive_target_paired_rows([c36_row])
    current_rows = []
    for side, expected in (("variant", "constraint_violated"),
                           ("control", "none")):
        checks = {}
        for target in TYPES:
            checks[target] = {
                "observable": True,
                "violation": target == "constraint_violated" if side == "variant" else False,
                "status": "violated" if side == "variant" and target == "constraint_violated" else "negative",
            }
        current_rows.append({
            "item_id": "v1", "side": side, "expected_label": expected,
            "checks": checks,
        })
    comparison = compare_target_paired(c36_rows, current_rows, panel)
    assert comparison["evaluation_protocol"]["primary"] == "target_paired_causal"
    assert "c36_winter" in comparison and "current_v5" in comparison
    assert comparison["unknown_denominators"]["c36_winter"][
        "overall_unknown_denominator"] == "2 * 40 side checks"
    assert comparison["c36_winter"]["per_type"]["constraint_violated"]["variant"]["TP"] == 1


def test_frozen_c36_artifacts_are_compatible_with_current_panel():
    panel = read_json(
        ROOT / "data/development/stage3_synth/"
        "synthetic_controlled_error_extension_v2.json")
    c36_rows = read_jsonl(
        ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/"
        "reference/winter/predictions.jsonl")
    current_rows = read_jsonl(
        ROOT / "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl")
    manifest = read_json(
        ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json")
    manifest["_root"] = str(ROOT)
    audit = audit_c36_winter(
        c36_rows, panel, c36_manifest=manifest, current_rows=current_rows)
    assert audit["sample_sets"]["c36_item_ids_equal_panel"] is True
    assert audit["label_issues"] == []
    assert audit["process_issues"] == []
    assert audit["c36_variant_bpmn_hash_issues"] == []
    assert audit["c36_control_bpmn_hash_issues"] == []
    assert audit["can_build_target_paired"] is True
    assert audit["control_reconstruction_required"] is True
    c36_paired = derive_target_paired_rows(c36_rows)
    assert len(c36_paired) == 80
    comparison = compare_target_paired(c36_paired, current_rows, panel)
    assert comparison["c36_winter"]["pair_success_denominator"] == 40
    assert comparison["current_v5"]["pair_success_denominator"] == 40

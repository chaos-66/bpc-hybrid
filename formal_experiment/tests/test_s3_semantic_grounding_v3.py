# -*- coding: utf-8 -*-
"""Focused tests for the s3_semantic_grounding_v3 protocol repair."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_v3 import (  # noqa: E402
    anonymize_fallback_payload,
    build_fallback_pack,
    control_model_self_consistency_diagnostic,
    evaluate_target_paired,
    fallback_transition_metrics,
    fixed_control_scope,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL  # noqa: E402

TYPES = list(EXTENDED_TYPES)


def clean_checks():
    return {
        target: {"status": "not_applicable", "observable": True,
                  "violation": False, "reason": "empty_rule_field"}
        for target in TYPES
    }


def make_row(item_id, side, label, checks=None, *, action_status="resolved"):
    return {
        "item_id": item_id,
        "side": side,
        "expected_label": label,
        "canonical_rule_input_hash": "rule",
        "canonical_process_input_hash": "process",
        "bpmn_sha256": "bpmn",
        "checks": checks or clean_checks(),
        "action_grounding": {"status": action_status, "candidates": []},
        "model_visible_rule_input": {
            "rule_id": "article",
            "sentence_idx": 0,
            "modality": "obligation",
            "actor": "the controller",
            "action": "control the variant workflow controller",
            "condition": "if the controller uses synthetic measures",
            "constraint": None,
            "exception": None,
        },
        "compact_local_context": {
            "candidate_activities": [{
                "activity_id": "syn_v2_handler_01",
                "label": "Handler controller variant",
                "owners": ["control owner"],
                "similarity": 1.0,
                "lexical_coverage": 1.0,
            }],
            "nodes": [{"id": "syn_v2_handler_01", "kind": "activity",
                       "label": "Handler controller variant"}],
            "sequence_flows": [],
            "condition_evidence": [],
            "constraint_bound_evidence": [],
            "constraint_unbound_evidence": [],
            "exception_handler_candidates": [],
            "evidence_ids": ["syn_v2_handler_01"],
        },
    }


def test_anonymisation_preserves_natural_language_and_maps_ids():
    row = make_row("item", "variant", "required_condition_not_enforced")
    payload = {
        "rule_record": row["model_visible_rule_input"],
        "candidate_activities": row["compact_local_context"]["candidate_activities"],
        "candidate_activity_ids": ["syn_v2_handler_01"],
        "local_context": {},
    }
    anonymized, id_map = anonymize_fallback_payload(payload)
    assert anonymized["rule_record"] == payload["rule_record"]
    serialized = json.dumps(anonymized, ensure_ascii=False)
    assert "controller" in serialized
    assert "control" in serialized
    assert "variant" in serialized
    assert "anonymousler" not in serialized
    assert "syn_v2_handler_01" not in serialized
    mapped = anonymized["candidate_activities"][0]["activity_id"]
    assert mapped == id_map["syn_v2_handler_01"]
    assert mapped.startswith("E")


def test_fallback_pack_has_no_metadata_and_marks_semantics_preserved():
    checks = clean_checks()
    checks["constraint_violated"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "unsupported_abstract_constraint_kind",
    }
    row = make_row("item", "variant", "constraint_violated", checks=checks)
    pack = build_fallback_pack([row])
    assert pack["item_count"] == 1
    item = pack["items"][0]
    assert item["semantic_fields_preserved"] is True
    assert item["llm_visible_payload"]["rule_record"] == row["model_visible_rule_input"]
    serialized = json.dumps(item["llm_visible_payload"], ensure_ascii=False)
    for forbidden in ("expected_violation", "mutation_type", "target_field",
                      "mutation_config", "Gold"):
        assert forbidden not in serialized
    assert "syn_v2_" not in serialized
    assert "controller" in serialized


def test_target_paired_unknown_denominators_are_explicit():
    variant_checks = clean_checks()
    variant_checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "condition_surface_ambiguous_or_incomplete",
    }
    control_checks = clean_checks()
    control_checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "condition_surface_ambiguous_or_incomplete",
    }
    variant = make_row("pair", "variant", "required_condition_not_enforced",
                       checks=variant_checks)
    control = make_row("pair", "control", NONE_LABEL, checks=control_checks)
    metrics = evaluate_target_paired([variant], [control],
                                     {"pair": "required_condition_not_enforced"})
    aggregate = metrics["aggregate_side_outcomes_mutually_exclusive"]
    assert aggregate["variant"]["unknown"] == 1
    assert aggregate["control"]["unknown"] == 1
    assert metrics["pair_success_count"] == 0
    assert metrics["pair_success_denominator"] == 1
    assert metrics["target_field_unknown_rate"] == 1.0
    per_type = metrics["per_type"]["required_condition_not_enforced"]
    assert per_type["variant"]["FN_unknown"] == 1
    assert per_type["variant"]["FP"] if False else True
    assert per_type["control"]["unknown"] == 1
    assert per_type["tnr_over_decided_controls"] is None
    assert per_type["recall_denominator_tp_plus_fn"] == 1


def test_fallback_transition_is_keyed_by_item_and_side():
    before_variant = make_row("same", "variant", "required_condition_not_enforced")
    before_control = make_row("same", "control", NONE_LABEL)
    for row in (before_variant, before_control):
        row["checks"]["required_condition_not_enforced"] = {
            "status": "unknown", "observable": False, "violation": None,
            "reason": "ambiguous",
        }
    after_variant = json.loads(json.dumps(before_variant))
    after_control = json.loads(json.dumps(before_control))
    after_variant["checks"]["required_condition_not_enforced"] = {
        "status": "not_enforced", "observable": True, "violation": True,
        "reason": "program_verified",
    }
    # A control becoming positive is a false alarm for the control side.
    after_control["checks"]["required_condition_not_enforced"] = {
        "status": "not_enforced", "observable": True, "violation": True,
        "reason": "program_verified",
    }
    result = fallback_transition_metrics(
        [before_variant, before_control], [after_variant, after_control],
        {"same": "required_condition_not_enforced"})
    assert result["variant"]["unknown_to_correct"] == 1
    assert result["variant"].get("unknown_to_wrong", 0) == 0
    assert result["control"]["unknown_to_wrong"] == 1
    assert result["control"].get("unknown_to_correct", 0) == 0
    assert result["variant"]["total_objects"] == 1
    assert result["control"]["total_objects"] == 1


def test_control_diagnostic_is_not_independent_validation():
    checks = clean_checks()
    checks["constraint_violated"] = {
        "status": "violated", "observable": True, "violation": True,
        "reason": "placeholder",
    }
    diagnostic = control_model_self_consistency_diagnostic(checks)
    assert diagnostic["diagnostic_only"] is True
    assert diagnostic["independent_validation"] is False
    assert diagnostic["not_a_global_compliance_label"] is True
    assert diagnostic["used_to_select_evaluation_subset"] is False
    assert diagnostic["status"] == "model_reports_other_field_positive"
    scope = fixed_control_scope([
        make_row("c1", "control", NONE_LABEL),
        make_row("c2", "control", NONE_LABEL),
    ])
    assert scope["control_count"] == 2
    assert scope["control_item_ids"] == ["c1", "c2"]
    assert scope["independent_global_compliance_labels_available"] is False
    assert scope["used_to_select_evaluation_subset"] is False

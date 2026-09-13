# -*- coding: utf-8 -*-
"""Focused tests for the v5 action-anchor consistency guard."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_v5 import (  # noqa: E402
    REVISION,
    action_anchor_consistency,
    apply_action_anchor_guard,
    build_fallback_pack,
)

EXCEPTION_TEXT = ("unless the personal data breach is unlikely to result in a "
                  "risk to the rights and freedoms of natural persons")


def sentence():
    return {
        "rule_id": "r",
        "sentence_idx": 0,
        "modality": "obligation",
        "actor": "the controller",
        "action": "notify the personal data breach",
        "condition": "in the case of a personal data breach",
        "constraint": "not later than 72 hours",
        "exception": EXCEPTION_TEXT,
    }


def ground(label: str, *, status: str = "resolved") -> dict:
    return {
        "status": status,
        "activity_id": "syn_handler_1" if status == "resolved" else None,
        "candidate_activity_ids": ["syn_handler_1"] if status == "resolved" else [],
        "candidates": ([{"activity_id": "syn_handler_1", "label": label}]
                       if status == "resolved" else []),
        "alternatives": [],
    }


def clear_checks() -> dict:
    return {
        "prohibited_action_present": {
            "status": "not_applicable", "observable": True,
            "violation": False, "reason": "modality"},
        "required_condition_not_enforced": {
            "status": "not_enforced", "observable": True, "violation": True,
            "reason": "condition_absent_from_fully_enumerated_action_anchored_surface"},
        "constraint_violated": {
            "status": "violated", "observable": True, "violation": True,
            "reason": "explicit_time_bound_absent_from_closed_action_scope"},
        "exception_not_handled": {
            "status": "handled", "observable": True, "violation": False,
            "reason": "exception_handler_evidence_found"},
    }


def test_exception_label_anchor_guard_demotes_condition_and_constraint():
    checks, changes = apply_action_anchor_guard(
        sentence(), ground(EXCEPTION_TEXT), clear_checks())
    assert len(changes) == 2
    assert checks["constraint_violated"]["status"] == "unknown"
    assert checks["constraint_violated"]["violation"] is None
    assert checks["constraint_violated"]["previous_check"]["violation"] is True
    assert checks["required_condition_not_enforced"]["status"] == "unknown"
    # Exception handler checks are not part of the anchor guard.
    assert checks["exception_not_handled"]["status"] == "handled"


def test_real_action_label_anchor_is_unchanged():
    sentence_value = sentence()
    ground_value = ground("notify the personal data breach")
    consistency = action_anchor_consistency(sentence_value, ground_value)
    assert consistency["action_anchor_valid"] is True
    checks, changes = apply_action_anchor_guard(
        sentence_value, ground_value, clear_checks())
    assert changes == []
    assert checks["constraint_violated"]["violation"] is True


def test_unresolved_or_unknown_anchor_is_not_rewritten():
    checks, changes = apply_action_anchor_guard(
        sentence(), ground(EXCEPTION_TEXT, status="unresolved"), clear_checks())
    assert changes == []
    assert checks["constraint_violated"]["violation"] is True
    unknown_checks = clear_checks()
    for value in unknown_checks.values():
        value.update({"status": "unknown", "observable": False, "violation": None})
    checks2, changes2 = apply_action_anchor_guard(
        sentence(), ground(EXCEPTION_TEXT), unknown_checks)
    assert changes2 == []
    assert checks2["constraint_violated"]["status"] == "unknown"


def test_v5_fallback_pack_marks_revision_and_ids():
    row = {
        "item_id": "item",
        "side": "variant",
        "predicted_violation_type": None,
        "checks": {
            "prohibited_action_present": {"status": "unknown", "observable": False,
                                          "violation": None},
            "required_condition_not_enforced": {"status": "unknown", "observable": False,
                                                "violation": None,
                                                "reason": "action_grounding_unresolved"},
            "constraint_violated": {"status": "not_applicable", "observable": True,
                                    "violation": False},
            "exception_not_handled": {"status": "not_applicable", "observable": True,
                                      "violation": False},
        },
        "action_grounding": ground(EXCEPTION_TEXT),
        "model_visible_rule_input": sentence(),
        "canonical_rule_input_hash": "rule",
        "canonical_process_input_hash": "process",
        "compact_local_context": {
            "candidate_activities": [{"activity_id": "A", "label": "notify",
                                       "owners": [], "similarity": 0.9,
                                       "lexical_coverage": 0.9}],
            "nodes": [], "sequence_flows": [], "condition_evidence": [],
            "constraint_bound_evidence": [], "constraint_unbound_evidence": [],
            "exception_handler_candidates": [], "evidence_ids": [],
        },
    }
    pack = build_fallback_pack([row])
    assert pack["revision"] == REVISION
    if pack["item_count"]:
        assert pack["items"][0]["fallback_item_id"].startswith("fb_v5_")

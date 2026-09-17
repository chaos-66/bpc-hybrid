# -*- coding: utf-8 -*-
"""Focused regression tests for the SEP-C4 v6 anchor/scope candidate."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_v6 import (  # noqa: E402
    ACTION_STATUS_AMBIGUOUS,
    ACTION_STATUS_RESOLVED,
    action_anchor_consistency,
    apply_action_anchor_guard,
    check_constraint,
    check_exception,
    disambiguate_action_grounding,
    score_sentence,
)

EXCEPTION_TEXT = ("unless the personal data breach is unlikely to result in a "
                  "risk to the rights and freedoms of natural persons")


def candidate(activity_id: str, label: str, *, exact: bool = False,
              coverage: float = 0.0, similarity: float = 0.0,
              token_jaccard: float = 0.0) -> dict:
    return {
        "activity_id": activity_id,
        "label": label,
        "owners": [],
        "similarity": similarity,
        "lexical_coverage": coverage,
        "token_jaccard": token_jaccard,
        "actor_token_match": 0.0,
        "exact_normalized": exact,
    }


def ground(candidates: list[dict], *, status: str = "resolved",
           activity_id: str | None = None, content_token_count: int = 4) -> dict:
    ids = [row["activity_id"] for row in candidates]
    return {
        "status": status,
        "reason": "fixture_saved_grounding",
        "activity_id": activity_id,
        "candidate_activity_ids": ids,
        "candidates": candidates,
        "alternatives": candidates,
        "content_token_count": content_token_count,
    }


def sentence(**overrides) -> dict:
    value = {
        "rule_id": "r",
        "sentence_idx": 0,
        "modality": "obligation",
        "actor": "the controller",
        "action": "notify the personal data breach",
        "condition": None,
        "constraint": None,
        "exception": None,
    }
    value.update(overrides)
    return value


def base_record(*, a_bound_name: str | None = None,
                b_bound_name: str | None = None) -> dict:
    activities = [
        {"id": "A", "name": "Notify breach", "type": "task", "lane_ids": []},
        {"id": "B", "name": "Retrieve breached data", "type": "task", "lane_ids": []},
    ]
    events = [
        {"id": "S", "name": "start", "type": "startEvent", "lane_ids": []},
        {"id": "E", "name": "end", "type": "endEvent", "lane_ids": []},
    ]
    if a_bound_name is not None:
        events.append({"id": "BA", "name": a_bound_name,
                       "type": "boundaryEvent", "lane_ids": []})
    if b_bound_name is not None:
        events.append({"id": "BB", "name": b_bound_name,
                       "type": "boundaryEvent", "lane_ids": []})
    flows = [
        {"id": "f1", "name": "", "source_ref": "S", "target_ref": "A",
         "condition_expression": None, "is_default": False},
        {"id": "f2", "name": "", "source_ref": "A", "target_ref": "E",
         "condition_expression": None, "is_default": False},
    ]
    return {"process_id": "p", "activities": activities, "events": events,
            "gateways": [], "sequence_flows": flows, "pools": [], "lanes": []}


def xml_for(*, a_bound_name: str | None = None,
            b_bound_name: str | None = None) -> ET.Element:
    elements = ["<process>"]
    if a_bound_name is not None:
        elements.append(f'<boundaryEvent id="BA" name="{a_bound_name}" attachedToRef="A"/>')
    if b_bound_name is not None:
        elements.append(f'<boundaryEvent id="BB" name="{b_bound_name}" attachedToRef="B"/>')
    elements.append("</process>")
    return ET.fromstring("".join(elements))


def run_check(checker, *, rule_field: str, rule_text: str,
              a_bound_name: str | None = None,
              b_bound_name: str | None = None) -> dict:
    row = candidate("A", "Notify breach", exact=True)
    other = candidate("B", "Retrieve breached data", coverage=0.9, similarity=0.9)
    ground_value = disambiguate_action_grounding(ground([row, other]))
    record = base_record(a_bound_name=a_bound_name, b_bound_name=b_bound_name)
    xml_root = xml_for(a_bound_name=a_bound_name, b_bound_name=b_bound_name)
    sentence_value = sentence(**{rule_field: rule_text})
    return checker(sentence_value, record, xml_root, ground_value)


def test_unique_exact_match_is_not_disturbed_by_interfering_candidate():
    exact = candidate("A", "Notify breach", exact=True, coverage=0.4,
                      similarity=0.25)
    noisy = candidate("B", "Notify national authority", coverage=0.9,
                      similarity=0.99)
    result = disambiguate_action_grounding(ground([noisy, exact]))
    assert result["status"] == ACTION_STATUS_RESOLVED
    assert result["activity_id"] == "A"
    assert result["reason"] == "unique_exact_normalized_label"


def test_indistinguishable_strong_candidates_stay_ambiguous_under_order_and_id_replay():
    left = ground([
        candidate("A", "Notify breach", coverage=0.6, similarity=0.4),
        candidate("B", "Retrieve breached data", coverage=0.6, similarity=0.4),
    ])
    right = ground([
        candidate("Y", "Retrieve breached data", coverage=0.6, similarity=0.4),
        candidate("X", "Notify breach", coverage=0.6, similarity=0.4),
    ])
    first = disambiguate_action_grounding(left)
    second = disambiguate_action_grounding(right)
    assert first["status"] == ACTION_STATUS_AMBIGUOUS
    assert second["status"] == ACTION_STATUS_AMBIGUOUS
    assert first["activity_id"] is None and second["activity_id"] is None
    assert first["reason"] == second["reason"]


def test_lexical_and_semantic_winner_conflict_is_not_forced():
    # Same shape as the frozen notify -> "Retrieve breached data" failure.
    lexical_winner = candidate("A", "Retrieve breached data", coverage=0.5,
                               similarity=0.276)
    semantic_winner = candidate("B", "Notify national authority", coverage=0.25,
                                similarity=0.512)
    result = disambiguate_action_grounding(ground([lexical_winner, semantic_winner]))
    assert result["status"] == ACTION_STATUS_AMBIGUOUS
    assert result["activity_id"] is None
    assert result["reason"] == "lexical_and_semantic_winner_conflict"
    assert result["disambiguation"]["lexical_and_semantic_conflict"] is True


def test_unmatched_all_rule_fields_is_unconfirmed_not_action_consistent():
    value = ground([candidate("A", "Retrieve breached data", coverage=0.2, similarity=0.1)], activity_id="A")
    consistency = action_anchor_consistency(sentence(), value)
    assert consistency["action_match"] is False
    assert consistency["action_anchor_valid"] is None
    assert consistency["action_anchor_state"] == "unconfirmed"
    assert consistency["reason"] != "resolved_label_is_action_consistent"

    checks = {
        "required_condition_not_enforced": {
            "status": "not_enforced", "observable": True, "violation": True,
            "reason": "old_inference"},
        "constraint_violated": {
            "status": "violated", "observable": True, "violation": True,
            "reason": "old_inference"},
    }
    guarded, changes = apply_action_anchor_guard(sentence(), value, checks)
    assert len(changes) == 2
    assert guarded["constraint_violated"]["status"] == "unknown"
    assert guarded["required_condition_not_enforced"]["status"] == "unknown"


def test_unreachable_candidate_timer_does_not_pollute_resolved_constraint_scope():
    result = run_check(check_constraint, rule_field="constraint",
                       rule_text="within 72 hours",
                       a_bound_name="48 hours", b_bound_name="96 hours")
    assert result["status"] == "satisfied"
    assert result["violation"] is False
    assert result["anchor_scope"] == "resolved_single_action"
    assert all(item.get("evidence", {}).get("id") != "BB"
               for item in result.get("evidence", []))


def test_unreachable_candidate_handler_does_not_handle_resolved_exception_scope():
    row = candidate("A", "Notify breach", exact=True)
    other = candidate("B", "Retrieve breached data", coverage=0.9, similarity=0.9)
    ground_value = disambiguate_action_grounding(ground([row, other]))
    record = base_record(b_bound_name=EXCEPTION_TEXT)
    result = check_exception(
        sentence(exception=EXCEPTION_TEXT), record,
        xml_for(b_bound_name=EXCEPTION_TEXT), ground_value)
    assert result["status"] == "not_handled"
    assert result["violation"] is True
    assert result["anchor_scope"] == "resolved_single_action"


def test_attached_boundary_timer_and_handler_keep_original_structural_rules():
    timer_result = run_check(check_constraint, rule_field="constraint",
                             rule_text="within 72 hours",
                             a_bound_name="96 hours")
    assert timer_result["status"] == "violated"
    assert timer_result["violation"] is True

    row = candidate("A", "Notify breach", exact=True)
    ground_value = disambiguate_action_grounding(ground([row]))
    handler_result = check_exception(
        sentence(exception=EXCEPTION_TEXT),
        base_record(a_bound_name=EXCEPTION_TEXT),
        xml_for(a_bound_name=EXCEPTION_TEXT), ground_value)
    assert handler_result["status"] == "handled"
    assert handler_result["violation"] is False


def test_expected_label_mutation_target_and_sample_id_do_not_affect_decision():
    row = candidate("A", "Notify breach", exact=True)
    ground_value = disambiguate_action_grounding(ground([row]))
    record = base_record()
    xml_root = xml_for()
    sentence_value = sentence(condition="in the case of a personal data breach")
    baseline = score_sentence(sentence_value, record, xml_root, ground_value)
    polluted = score_sentence(
        sentence_value, record, xml_root, ground_value,
        metadata={
            "expected_label": "exception_not_handled",
            "mutation_config": {"target_activity_id": "B"},
            "target_activity_id": "B",
            "item_id": "syn_changed_id",
        })
    assert json.dumps(baseline, sort_keys=True) == json.dumps(polluted, sort_keys=True)


def test_global_margin_is_not_applied_to_nonleader_candidate():
    leader = candidate("A", "Notify breach", coverage=0.25, similarity=0.8)
    nonleader = candidate("B", "Retrieve breached data", coverage=0.25,
                          similarity=0.45)
    result = disambiguate_action_grounding(ground([leader, nonleader]))
    assert result["status"] == ACTION_STATUS_RESOLVED
    assert result["activity_id"] == "A"
    assert "B" not in result["disambiguation"]["effective_activity_ids"]

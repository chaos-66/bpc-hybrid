# -*- coding: utf-8 -*-
"""Focused regression tests for the SEP-C4 v7 evidence-eligible consensus fix.

The tests use semantic BPMN fixtures.  They assert that a missing handler or
missing local condition/time evidence is not promoted to a definite violation
when no retrieved action candidate has effective grounding support, while
evidence-eligible candidates can still reach a defined per-candidate verdict.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_v7 import (  # noqa: E402
    ACTION_STATUS_AMBIGUOUS,
    ACTION_STATUS_RESOLVED,
    check_condition,
    check_constraint,
    check_exception,
    disambiguate_action_grounding,
    eligible_candidate_ids,
    score_sentence,
)

EXCEPTION_TEXT = ("unless the personal data breach is unlikely to result in a "
                  "risk to the rights and freedoms of natural persons")


def candidate(activity_id: str, label: str, *, exact: bool = False,
              coverage: float = 0.0, similarity: float = 0.0) -> dict:
    return {
        "activity_id": activity_id,
        "label": label,
        "owners": [],
        "similarity": similarity,
        "lexical_coverage": coverage,
        "token_jaccard": 0.0,
        "actor_token_match": 0.0,
        "exact_normalized": exact,
    }


def saved_ground(candidates: list[dict]) -> dict:
    return {
        "status": "resolved",
        "reason": "fixture_saved_grounding",
        "activity_id": None,
        "candidate_activity_ids": [row["activity_id"] for row in candidates],
        "candidates": candidates,
        "alternatives": candidates,
        "content_token_count": 4,
    }


def weak_ambiguous_ground() -> dict:
    """Two weak retrieved candidates -> ambiguous with empty effective support."""
    return disambiguate_action_grounding(saved_ground([
        candidate("A", "Notify breach", coverage=0.25, similarity=0.25),
        candidate("B", "Retrieve breached data", coverage=0.25, similarity=0.25),
    ]))


def eligible_ambiguous_ground() -> dict:
    """Two evidence-supported candidates -> ambiguous but eligible consensus."""
    return disambiguate_action_grounding(saved_ground([
        candidate("A", "Notify breach", coverage=0.6, similarity=0.4),
        candidate("B", "Retrieve breached data", coverage=0.6, similarity=0.4),
    ]))


def branch_record(*, deep_chain: bool = False) -> dict:
    activities = [
        {"id": "A", "name": "Notify breach", "type": "task", "lane_ids": []},
        {"id": "B", "name": "Retrieve breached data", "type": "task", "lane_ids": []},
    ]
    flows = [
        {"id": "fa1", "name": "", "source_ref": "S", "target_ref": "A",
         "condition_expression": None, "is_default": False},
        {"id": "fb1", "name": "", "source_ref": "S", "target_ref": "B",
         "condition_expression": None, "is_default": False},
        {"id": "fa2", "name": "", "source_ref": "A", "target_ref": "E",
         "condition_expression": None, "is_default": False},
        {"id": "fb2", "name": "", "source_ref": "B", "target_ref": "E",
         "condition_expression": None, "is_default": False},
    ]
    events = [
        {"id": "S", "name": "start", "type": "startEvent", "lane_ids": []},
        {"id": "E", "name": "end", "type": "endEvent", "lane_ids": []},
    ]
    if deep_chain:
        previous = "A"
        for index in range(1, 13):
            node_id = f"C{index}"
            activities.append({"id": node_id, "name": f"step {index}",
                               "type": "task", "lane_ids": []})
            flows.append({"id": f"fc{index}", "name": "",
                          "source_ref": previous, "target_ref": node_id,
                          "condition_expression": None, "is_default": False})
            previous = node_id
        # A no longer flows directly to E; the deep chain makes its downstream
        # handler surface incomplete under the fixed max_depth=8 window.
        flows = [flow for flow in flows if not (flow["id"] == "fa2")]
        flows.append({"id": "fc13", "name": "", "source_ref": previous,
                      "target_ref": "E", "condition_expression": None,
                      "is_default": False})
    return {"process_id": "p", "activities": activities, "events": events,
            "gateways": [], "sequence_flows": flows, "pools": [], "lanes": []}


def branch_xml(*, handler_on_a: bool = False) -> ET.Element:
    element = "<process>"
    if handler_on_a:
        element += (f'<boundaryEvent id="BA" name="{EXCEPTION_TEXT}" '
                    f'attachedToRef="A"/>')
    element += "</process>"
    return ET.fromstring(element)


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


def assert_layer_consistency(check: dict, score: dict, target: str,
                             *, expected_observable: bool) -> None:
    assert check.get("action_grounding_status") == ACTION_STATUS_AMBIGUOUS
    assert (check.get("observable") is True) is expected_observable
    assert score["action_grounding"]["status"] == ACTION_STATUS_AMBIGUOUS
    assert score["observability"][target]["observable"] is expected_observable
    if expected_observable:
        assert score["scores"][target] == check.get("score")
    else:
        assert score["scores"][target] is None
        assert score["decision"]["decision"] == "abstention"


# ---------------------------------------------------------------------------
# 1. no effective support + no handler -> unknown, never a definite violation
# ---------------------------------------------------------------------------

def test_empty_support_no_handler_is_unknown_not_violation():
    ground = weak_ambiguous_ground()
    assert ground["status"] == ACTION_STATUS_AMBIGUOUS
    assert ground["disambiguation"]["effective_support"] == {}
    assert eligible_candidate_ids(ground) == []

    check = check_exception(sentence(exception=EXCEPTION_TEXT),
                            branch_record(), branch_xml(), ground)
    assert check["status"] == "unknown"
    assert check["observable"] is False
    assert check["violation"] is None
    assert check["reason"] == "ambiguous_no_evidence_supported_action_candidate"
    assert "resolved" not in json.dumps(check)

    score = score_sentence(sentence(exception=EXCEPTION_TEXT),
                           branch_record(), branch_xml(), ground)
    assert_layer_consistency(check, score, "exception_not_handled",
                             expected_observable=False)
    assert score["decision"]["predicted"] is None
    assert score["decision"]["decision"] == "abstention"


# ---------------------------------------------------------------------------
# 2. evidence-eligible consensus -> defined verdict, still ambiguous upstream
# ---------------------------------------------------------------------------

def test_eligible_candidates_with_consensus_make_defined_verdict():
    ground = eligible_ambiguous_ground()
    assert ground["status"] == ACTION_STATUS_AMBIGUOUS
    assert set(eligible_candidate_ids(ground)) == {"A", "B"}

    check = check_exception(sentence(exception=EXCEPTION_TEXT),
                            branch_record(), branch_xml(), ground)
    assert check["status"] == "not_handled"
    assert check["observable"] is True
    assert check["violation"] is True
    assert check["anchor_scope"] == "ambiguous_per_candidate_consensus"
    assert check["reason"].startswith("per_candidate_")

    score = score_sentence(sentence(exception=EXCEPTION_TEXT),
                           branch_record(), branch_xml(), ground)
    assert_layer_consistency(check, score, "exception_not_handled",
                             expected_observable=True)
    assert score["decision"]["predicted"] == "exception_not_handled"
    assert score["decision"]["decision"] == "violation"
    assert score["scores"]["exception_not_handled"] == 1.0


# ---------------------------------------------------------------------------
# 3. eligible candidates disagree -> unknown; no resolved fact is persisted
# ---------------------------------------------------------------------------

def test_conflicting_eligible_candidate_conclusions_stay_unknown():
    ground = eligible_ambiguous_ground()
    check = check_exception(sentence(exception=EXCEPTION_TEXT),
                            branch_record(), branch_xml(handler_on_a=True), ground)
    assert check["status"] == "unknown"
    assert check["observable"] is False
    assert check["violation"] is None
    assert check["reason"] == "per_candidate_action_scope_evidence_not_consensual"
    assert check["anchor_scope"] == "ambiguous_per_candidate_disagreement"
    scope = {item["activity_id"]: item for item in check["candidate_scope_checks"]}
    assert scope["A"]["violation"] is False
    assert scope["B"]["violation"] is True
    assert all(item["candidate_anchor_hypothesis"] is True for item in scope.values())
    assert "resolved" not in json.dumps(check)

    score = score_sentence(sentence(exception=EXCEPTION_TEXT),
                           branch_record(), branch_xml(handler_on_a=True), ground)
    assert_layer_consistency(check, score, "exception_not_handled",
                             expected_observable=False)


# ---------------------------------------------------------------------------
# 4. incomplete eligible surface -> unknown
# ---------------------------------------------------------------------------

def test_incomplete_eligible_surface_stays_unknown():
    ground = eligible_ambiguous_ground()
    check = check_exception(sentence(exception=EXCEPTION_TEXT),
                            branch_record(deep_chain=True), branch_xml(), ground)
    assert check["status"] == "unknown"
    assert check["observable"] is False
    assert check["violation"] is None
    assert check["anchor_scope"] == "ambiguous_per_candidate_disagreement"
    scope = {item["activity_id"]: item for item in check["candidate_scope_checks"]}
    assert scope["A"]["observable"] is False
    assert scope["B"]["observable"] is True


# ---------------------------------------------------------------------------
# 5. condition / constraint also cannot bypass the anchor eligibility gate
# ---------------------------------------------------------------------------

def test_ambiguous_condition_without_support_is_unknown():
    ground = weak_ambiguous_ground()
    check = check_condition(
        sentence(condition="if consent is withdrawn"), branch_record(), ground)
    assert check["status"] == "unknown"
    assert check["observable"] is False
    assert check["violation"] is None
    assert check["action_grounding_status"] == ACTION_STATUS_AMBIGUOUS

    eligible = eligible_ambiguous_ground()
    consensus = check_condition(
        sentence(condition="if consent is withdrawn"), branch_record(), eligible)
    assert consensus["status"] == "not_enforced"
    assert consensus["violation"] is True
    assert consensus["action_grounding_status"] == ACTION_STATUS_AMBIGUOUS


def test_ambiguous_constraint_without_support_is_unknown():
    ground = weak_ambiguous_ground()
    check = check_constraint(
        sentence(constraint="within 72 hours"), branch_record(),
        ET.fromstring("<process/>"), ground)
    assert check["status"] == "unknown"
    assert check["observable"] is False
    assert check["violation"] is None
    assert check["action_grounding_status"] == ACTION_STATUS_AMBIGUOUS

    eligible = eligible_ambiguous_ground()
    consensus = check_constraint(
        sentence(constraint="within 72 hours"), branch_record(),
        ET.fromstring("<process/>"), eligible)
    assert consensus["status"] == "violated"
    assert consensus["violation"] is True
    assert consensus["action_grounding_status"] == ACTION_STATUS_AMBIGUOUS


# ---------------------------------------------------------------------------
# 6. resolved single-anchor behaviour is not regressed
# ---------------------------------------------------------------------------

def test_resolved_unique_exact_handler_and_timer_still_work():
    exact = candidate("A", "Notify breach", exact=True)
    ground = disambiguate_action_grounding(saved_ground([exact]))
    assert ground["status"] == ACTION_STATUS_RESOLVED

    handled = check_exception(sentence(exception=EXCEPTION_TEXT),
                              branch_record(), branch_xml(handler_on_a=True), ground)
    assert handled["status"] == "handled"
    assert handled["violation"] is False
    assert handled["anchor_scope"] == "resolved_single_action"

    no_handler = check_exception(sentence(exception=EXCEPTION_TEXT),
                                 branch_record(), branch_xml(), ground)
    assert no_handler["status"] == "not_handled"
    assert no_handler["violation"] is True
    assert no_handler["anchor_scope"] == "resolved_single_action"

    timer = check_constraint(sentence(constraint="within 72 hours"),
                             branch_record(), ET.fromstring("<process/>"), ground)
    assert timer["status"] == "violated"
    assert timer["violation"] is True
    assert timer["anchor_scope"] == "resolved_single_action"


def test_metadata_and_expected_label_remain_blind():
    exact = candidate("A", "Notify breach", exact=True)
    ground = disambiguate_action_grounding(saved_ground([exact]))
    record = branch_record()
    xml_root = branch_xml()
    value = sentence(exception=EXCEPTION_TEXT)
    baseline = score_sentence(value, record, xml_root, ground)
    polluted = score_sentence(value, record, xml_root, ground, metadata={
        "expected_label": "exception_not_handled",
        "target_activity_id": "B",
        "mutation_config": {"target_activity_id": "B"},
        "item_id": "syn_changed_id",
    })
    assert json.dumps(baseline, sort_keys=True) == json.dumps(polluted, sort_keys=True)

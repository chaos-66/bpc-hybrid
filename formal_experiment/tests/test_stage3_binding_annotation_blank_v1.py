# -*- coding: utf-8 -*-
"""Guard tests for the Stage 3 blank binding-annotation surface.

The surface exists so a HUMAN can supply the rule-action -> BPMN-activity
binding the "Ours" detector needs. These tests enforce the governance rule from
the workspace contract: an agent must never fill in, infer, or copy a decision
value into it. They also pin the structure so a later edit cannot silently
shrink the annotation work or drop the recorded limits.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SURFACE = (ROOT / "data" / "development" / "stage3_synth"
           / "stage3_binding_annotation_blank_v1.json")
DECISION_FIELDS = (
    "decision_action_id",
    "decision_actor_id",
    "decision_expected_lane",
    "decision_order_before_action_id",
    "decision_order_after_action_id",
    "decision_note",
)


@pytest.fixture(scope="module")
def surface():
    if not SURFACE.is_file():
        pytest.skip("annotation surface not built")
    return json.loads(SURFACE.read_text(encoding="utf-8"))


def test_surface_is_blank(surface) -> None:
    """No decision may be pre-filled: that would be an agent-made Gold."""
    assert surface["status"] == "blank_awaiting_human_annotation"
    assert surface["counts"]["decisions_filled"] == 0
    assert surface["safety"]["decisions_inferred_by_agent"] is False
    assert surface["safety"]["llm_api_calls"] == 0
    for item in surface["items"]:
        for field in DECISION_FIELDS:
            assert item[field] is None, (item["pair_id"], field)
        assert item["review_state"] == "unreviewed"


def test_surface_is_pair_level_and_complete(surface) -> None:
    """One binding per pair, covering all 30 pairs (not 60 per-item rows)."""
    assert surface["counts"]["items"] == 30
    assert len(surface["items"]) == 30
    assert len({i["pair_id"] for i in surface["items"]}) == 30
    roles = surface["counts"]["by_role"]
    assert roles == {"control": 30, "variant": 30}
    for item in surface["items"]:
        assert set(item["immutable_context"]["roles"]) == {"control", "variant"}


def test_context_is_present_and_immutable_fields_populated(surface) -> None:
    """Each pair must carry enough read-only context to be annotatable."""
    for item in surface["items"]:
        ctx = item["immutable_context"]
        assert ctx["process_id"]
        assert ctx["rule_id"]
        assert ctx["target_activity_id"]
        assert ctx["target_activity_name"], item["pair_id"]
        assert ctx["target_violation_type"] in (
            "missing_action", "incorrect_actor", "out_of_order")
        rule_side = ctx["rule_side"]
        assert rule_side["actions"], item["pair_id"]
        assert isinstance(rule_side["clauses"], int)


def test_recorded_limits_are_not_silently_dropped(surface) -> None:
    """The two blockers the annotator must know about stay documented."""
    limits = surface["known_limits_recorded"]
    assert "order_relations_in_gold" in limits
    assert "ZERO order relations" in limits["order_relations_in_gold"]
    assert "actor_action_map_coverage" in limits
    assert "38 of 92" in limits["actor_action_map_coverage"]

# -*- coding: utf-8 -*-
from __future__ import annotations

import spacy

from bpc_hybrid.sun_stage3.temporal_projection_v1 import (
    project_clause_order_relations,
    project_record_order_relations,
)

nlp = spacy.load("en_core_web_sm")


def _span(text: str, needle: str, sid: str) -> dict:
    start = text.index(needle)
    return {"id": sid, "start": start, "end": start + len(needle)}


def _clause(text: str, actions: list[str], constraints: list[str],
            conditions: list[str] | None = None,
            exceptions: list[str] | None = None,
            relations: list[dict] | None = None) -> dict:
    return {
        "clause_id": "c1",
        "clause_span": {"start": 0, "end": len(text)},
        "modality": {"label": "obligation"},
        "actions": [_span(text, value, f"a{i+1}") for i, value in enumerate(actions)],
        "actors": [_span(text, "The controller", "actor1")],
        "conditions": [_span(text, value, f"cond{i+1}") for i, value in enumerate(conditions or [])],
        "constraints": [_span(text, value, f"con{i+1}") for i, value in enumerate(constraints)],
        "exceptions": [_span(text, value, f"exc{i+1}") for i, value in enumerate(exceptions or [])],
        "actor_action_map": [],
        "order_relations": relations or [],
    }


def test_before_direction_and_verbal_endpoint() -> None:
    text = "The controller shall provide the data subject before the processing starts."
    clause = _clause(text, ["provide the data subject"], ["before the processing starts"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "derived"
    assert len(result["edges"]) == 1
    before, after = result["edges"][0]
    assert "provide" in before
    assert "processing starts" in after


def test_after_direction_and_verbal_endpoint() -> None:
    text = "The controller shall process the data after the assessment is completed."
    clause = _clause(text, ["process the data"], ["after the assessment is completed"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "derived"
    assert len(result["edges"]) == 1
    before, after = result["edges"][0]
    assert "assessment is completed" in before
    assert "process the data" in after


def test_native_valid_edge_has_priority() -> None:
    text = "The controller shall process the data after the assessment is completed."
    action1 = _span(text, "process the data", "a1")
    action2 = _span(text, "assessment is completed", "a2")
    clause = _clause(text, ["process the data"], ["after the assessment is completed"])
    clause["actions"].append(action2)
    clause["order_relations"] = [{
        "before_action_id": action2["id"],
        "after_action_id": action1["id"],
    }]
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "native"
    assert result["edges"] == [("assessment is completed", "process the data")]


def test_action_inside_condition_is_excluded_and_no_edge_created() -> None:
    text = "The controller shall process the data before the assessment."
    clause = _clause(text, ["process the data"], ["before the assessment"])
    # Force the only action to be fully inside the constraint.
    clause["actions"] = [_span(text, "the assessment", "a1")]
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "no_edge"
    assert result["edges"] == []
    reasons = {row.get("reason") for row in result["audit"]["rejections"]}
    assert "no_single_main_action_endpoint" in reasons


def test_negated_marker_rejected() -> None:
    text = "The controller shall not provide the data before the processing starts."
    clause = _clause(text, ["provide the data"], ["before the processing starts"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["edges"] == []
    reasons = {row.get("reason") for row in result["audit"]["rejections"]}
    assert any("neg" in str(reason) for reason in reasons)


def test_selected_span_with_multiple_markers_rejected() -> None:
    text = "The controller shall process the data before the assessment after the review."
    clause = _clause(text, ["process the data"], ["before the assessment after the review"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["edges"] == []
    reasons = {row.get("reason") for row in result["audit"]["rejections"]}
    assert "selected_span_contains_multiple_markers" in reasons


def test_no_predicted_time_span_creates_no_edge() -> None:
    text = "The controller shall process the data."
    clause = _clause(text, ["process the data"], [])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["edges"] == []
    assert result["status"] == "no_edge"


def test_same_input_projection_is_deterministic() -> None:
    text = "The controller shall provide the data subject before the processing starts."
    clause = _clause(text, ["provide the data subject"], ["before the processing starts"])
    first = project_clause_order_relations(clause, text, nlp(text))
    second = project_clause_order_relations(clause, text, nlp(text))
    assert first == second


def test_record_level_projection_returns_edges_and_audit() -> None:
    text = "The controller shall provide the data subject before the processing starts."
    clause = _clause(text, ["provide the data subject"], ["before the processing starts"])
    edges, audit = project_record_order_relations({"clauses": [clause]}, text, nlp(text))
    assert len(edges) == 1
    assert audit["edge_count"] == 1
    assert audit["clause_audits"][0]["status"] == "derived"
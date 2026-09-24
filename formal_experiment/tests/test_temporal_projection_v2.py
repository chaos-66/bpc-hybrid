# -*- coding: utf-8 -*-
from __future__ import annotations

import spacy

from bpc_hybrid.sun_stage3.temporal_projection_v2 import (
    project_clause_order_relations,
    project_record_order_relations,
)

nlp = spacy.load("en_core_web_sm")


def _span(text: str, needle: str, sid: str) -> dict:
    start = text.index(needle)
    return {"id": sid, "start": start, "end": start + len(needle)}


def _clause(text: str, actions: list[str], constraints: list[str],
            exceptions: list[str] | None = None) -> dict:
    return {
        "clause_id": "c1",
        "clause_span": {"start": 0, "end": len(text)},
        "modality": {"label": "obligation"},
        "actions": [_span(text, value, f"a{i+1}") for i, value in enumerate(actions)],
        "actors": [_span(text, "controller", "actor1")],
        "conditions": [],
        "constraints": [_span(text, value, f"con{i+1}") for i, value in enumerate(constraints)],
        "exceptions": [_span(text, value, f"exc{i+1}") for i, value in enumerate(exceptions or [])],
        "actor_action_map": [],
        "order_relations": [],
    }


def test_before_direction_and_verbal_endpoint() -> None:
    text = "The controller shall provide the data subject before the processing starts."
    clause = _clause(text, ["provide the data subject"], ["before the processing starts"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "derived"
    before, after = result["edges"][0]
    assert "provide" in before
    assert "processing starts" in after


def test_after_direction_and_verbal_endpoint() -> None:
    text = "The controller shall process the data after the assessment is completed."
    clause = _clause(text, ["process the data"], ["after the assessment is completed"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "derived"
    before, after = result["edges"][0]
    assert "assessment is completed" in before
    assert "process the data" in after


def test_article18p3_post_marker_clausal_predicate_is_found() -> None:
    text = ("A data subject who has obtained restriction of processing pursuant to paragraph 1 "
            "shall be informed by the controller before the restriction of processing is lifted.")
    clause = _clause(text, ["informed"], ["before the restriction of processing is lifted"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "derived"
    before, after = result["edges"][0]
    assert "informed" in before
    assert "is lifted" in after
    marker = result["audit"]["markers"][0]
    assert marker["second_endpoint_audit"]["branch"] == "verbal"
    assert marker["second_endpoint_audit"]["selected_head"]["text"] == "lifted"


def test_prior_to_uses_bounded_nominal_and_preserves_of() -> None:
    text = "The controller shall consult the authority prior to the processing of personal data."
    clause = _clause(text, ["consult the authority"], ["prior to the processing of personal data"])
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["status"] == "derived"
    before, after = result["edges"][0]
    assert before == "consult the authority"
    assert after == "the processing of personal data"
    assert " of " in after


def test_nominal_endpoint_rejects_chunk_crossing_selected_span() -> None:
    text = "The controller shall consult the authority prior to the processing of personal data."
    clause = _clause(text, ["consult the authority"], ["prior to the processing of personal data"])
    start = text.index("prior to the processing")
    end = text.index("the processing") + len("the process")
    clause["constraints"] = [{"id": "con1", "start": start, "end": end}]
    result = project_clause_order_relations(clause, text, nlp(text))
    assert result["edges"] == []
    reasons = {row.get("reason") for row in result["audit"]["rejections"]}
    assert any("outside_selected_span" in str(reason) for reason in reasons)


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


def test_record_level_projection_returns_edges_and_audit() -> None:
    text = "The controller shall provide the data subject before the processing starts."
    clause = _clause(text, ["provide the data subject"], ["before the processing starts"])
    edges, audit = project_record_order_relations({"clauses": [clause]}, text, nlp(text))
    assert len(edges) == 1
    assert audit["edge_count"] == 1
    assert audit["clause_audits"][0]["status"] == "derived"

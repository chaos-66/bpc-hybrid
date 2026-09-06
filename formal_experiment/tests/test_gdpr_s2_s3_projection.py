# -*- coding: utf-8 -*-
"""Focused tests for the Stage-2 -> Stage-3 external-prediction projection
(``bpc_hybrid.gdpr_s2_s3_projection``)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr_s2_s3_projection import (  # noqa: E402
    PROJECTION_NAME,
    project_external_sentence,
    projection_summary,
)

TEXT = ("The data subject shall have the right not to be subject to a "
        "decision based solely on automated processing, including profiling, "
        "which produces legal effects concerning him or her or similarly "
        "significantly affects him or her.")


def _clause(start, end, label="obligation", actions=None, conditions=None,
            constraints=None, exceptions=None, actors=None) -> dict:
    return {
        "clause_id": f"c{start}",
        "clause_span": {"start": start, "end": end},
        "modality": {"label": label, "evidence": []},
        "actors": actors or [],
        "actions": actions or [],
        "conditions": conditions or [],
        "constraints": constraints or [],
        "exceptions": exceptions or [],
        "actor_action_map": [],
        "order_relations": [],
    }


def _span(start, end, sid="s1") -> dict:
    return {"start": start, "end": end, "id": sid}


def _pred(sample_id, clauses, status="ok", error=None) -> dict:
    return {
        "sample_id": sample_id,
        "request_status": status,
        "record": {"sample_id": sample_id, "clauses": clauses},
        "error_category": error,
    }


def test_projection_extracts_first_valid_span() -> None:
    # action spans [40:52] ("right not to") and [60:70]; condition [0:24]
    clauses = [_clause(0, len(TEXT),
                       actions=[_span(40, 52, "a1"), _span(60, 70, "a2")],
                       conditions=[_span(0, 24, "c1")])]
    out = project_external_sentence(_pred("g", clauses), TEXT, "g")
    assert out["ok"] is True
    assert out["sentence"]["action"] == TEXT[40:52]
    assert out["sentence"]["condition"] == TEXT[0:24]
    assert out["sentence"]["constraint"] is None
    assert out["sentence"]["modality"] == "obligation"
    assert out["sentence"]["projection"] == PROJECTION_NAME
    assert out["diagnostics"]["span_field_texts"]["action"] == [TEXT[40:52],
                                                                TEXT[60:70]]


def test_main_clause_wins_fields_and_modality() -> None:
    # first clause short (modality permission), second clause long with an
    # action; action must come from the LONG (main) clause.
    short = _clause(0, 10, label="permission", actions=[_span(1, 6)])
    long = _clause(20, len(TEXT), label="prohibition",
                   actions=[_span(30, 45)])
    out = project_external_sentence(
        _pred("g", [short, long]), TEXT, "g")
    assert out["ok"] is True
    assert out["sentence"]["modality"] == "prohibition"
    assert out["sentence"]["action"] == TEXT[30:45]
    assert out["diagnostics"]["main_clause_index"] == 1


def test_out_of_range_spans_never_used() -> None:
    clauses = [_clause(0, 10, actions=[_span(500, 600), _span(1, 5)])]
    out = project_external_sentence(_pred("g", clauses), TEXT, "g")
    assert out["ok"] is True
    assert out["sentence"]["action"] == TEXT[1:5]
    assert out["diagnostics"]["invalid_span_count"] == 1


def test_failure_and_empty_prediction() -> None:
    bad = {"sample_id": "g", "request_status": "error", "error_category": "x",
           "record": None}
    out = project_external_sentence(bad, TEXT, "g")
    assert out["ok"] is False and out["error"] == "prediction_failed"
    empty = _pred("g", [], status="ok")
    out2 = project_external_sentence(empty, TEXT, "g")
    assert out2["ok"] is False and out2["error"] == "empty_prediction"
    wrong = _pred("other", [_clause(0, 10)], TEXT[:10])
    out3 = project_external_sentence(wrong, TEXT, "g")
    assert out3["ok"] is False and out3["error"] == "sample_id_mismatch"


def test_multi_clause_field_fallback() -> None:
    # action absent from main clause but present in a secondary clause
    short = _clause(0, 10, label="obligation")
    long = _clause(20, 40, label="obligation", actions=[])
    third = _clause(50, 70, label="obligation", actions=[_span(55, 60)])
    out = project_external_sentence(
        _pred("g", [short, long, third]), TEXT, "g")
    assert out["ok"] is True
    assert out["sentence"]["action"] == TEXT[55:60]


def test_summary_counts() -> None:
    ps = [
        {"ok": False, "sample_id": "a", "error": "x"},
        {"ok": True, "sentence": {"action": "A", "modality": "prohibition"},
         "diagnostics": {"invalid_span_count": 2}},
        {"ok": True, "sentence": {"action": None, "modality": None},
         "diagnostics": {"invalid_span_count": 0}},
    ]
    s = projection_summary(ps)
    assert s["failed"] == ["a"]
    assert s["empty_action_sentences"] == 1
    assert s["empty_modality_sentences"] == 1
    assert s["total_invalid_spans"] == 2

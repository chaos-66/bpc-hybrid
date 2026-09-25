# -*- coding: utf-8 -*-
"""Synthetic fixtures for R2 strict temporal projection v3.

These tests do not use construction_reference, target rule/type labels, or
Gold data.  The synthetic sentences and fake token graph exercise only the
R1 section-3.2 contract being corrected in R2.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.sun_stage3 import temporal_projection_v3 as v3  # noqa: E402


@pytest.fixture(scope="module")
def nlp():
    import spacy
    return spacy.load("en_core_web_sm")


def _clause(text: str, action_text: str, constraint_text: str) -> dict:
    def span(sub: str) -> dict:
        start = text.index(sub)
        return {"id": "x", "start": start, "end": start + len(sub)}

    return {
        "clause_id": "synthetic_c1",
        "modality": {"label": "obligation"},
        "actions": [span(action_text)],
        "actors": [],
        "conditions": [],
        "constraints": [span(constraint_text)],
        "exceptions": [],
        "actor_action_pairs": [],
        "order_relations": [],
    }


class _FakeHead:
    def __init__(self, text: str = "root", pos_: str = "VERB"):
        self.text = text
        self.pos_ = pos_


class _FakeToken:
    def __init__(self, *, i: int, text: str, idx: int, pos_: str, dep_: str,
                 head: _FakeHead | None = None, children: list | None = None):
        self.i = i
        self.text = text
        self.idx = idx
        self.pos_ = pos_
        self.dep_ = dep_
        self.head = head or self
        self.children = list(children or [])


class _FakeDoc:
    def __init__(self, tokens: list[_FakeToken]):
        self.tokens = tokens

    def __iter__(self):
        return iter(self.tokens)


def test_mark_head_after_marker_is_adopted(nlp):
    text = "The controller shall act before the event is lifted."
    doc = nlp(text)
    record = {"clauses": [_clause(text, "act", "before the event is lifted.")]}
    edges, audit = v3.project_record_order_relations(record, text, doc)
    assert edges == [("act", "the event is lifted")]
    second = audit["clause_audits"][0]["markers"][0]["second_endpoint_audit"]
    assert second["branch"] == "verbal"
    assert second["strategy"] == "mark_head_after_marker_in_span"
    assert second["selected_head"]["text"] == "lifted"


def test_prep_one_direct_pcomp_child_is_adopted(nlp):
    text = "The controller shall act before starting the processing."
    doc = nlp(text)
    record = {"clauses": [_clause(text, "act", "before starting the processing.")]}
    edges, audit = v3.project_record_order_relations(record, text, doc)
    assert edges == [("act", "starting the processing")]
    second = audit["clause_audits"][0]["markers"][0]["second_endpoint_audit"]
    assert second["branch"] == "verbal"
    assert second["strategy"] == "direct_pcomp_children_only"
    assert second["selected_head"]["text"] == "starting"


def test_fake_prep_two_legal_pcomp_children_rejected():
    root = _FakeHead("root", "VERB")
    child1 = _FakeToken(i=1, text="first", idx=7, pos_="VERB", dep_="pcomp",
                        head=_FakeHead("before", "ADP"))
    child2 = _FakeToken(i=2, text="second", idx=20, pos_="VERB", dep_="pcomp",
                        head=_FakeHead("before", "ADP"))
    marker = _FakeToken(i=0, text="before", idx=0, pos_="ADP", dep_="prep",
                        head=root, children=[child1, child2])
    doc = _FakeDoc([marker])
    selected = {"start": 0, "end": 50}
    head, audit = v3._strict_verbal_head(doc, {"marker_start": 0, "marker_end": 6}, selected)
    assert head is None
    assert "multiple_legal_pcomp_children" in audit["reasons"]
    assert len(audit["legal_pcomp_children"]) == 2


def test_fake_mark_head_before_marker_rejected():
    root = _FakeHead("act", "VERB")
    earlier = _FakeToken(i=0, text="act", idx=0, pos_="VERB", dep_="ROOT", head=root)
    marker = _FakeToken(i=1, text="before", idx=10, pos_="SCONJ", dep_="mark",
                        head=earlier)
    doc = _FakeDoc([earlier, marker])
    selected = {"start": 0, "end": 40}
    head, audit = v3._strict_verbal_head(doc, {"marker_start": 10, "marker_end": 16}, selected)
    assert head is None
    assert "mark_head_outside_marker_after_selected_span" in audit["reasons"]


def test_fake_non_mark_non_prep_does_not_scan_clausal_predicate():
    root = _FakeHead("act", "VERB")
    marker = _FakeToken(i=0, text="before", idx=0, pos_="ADV", dep_="advmod",
                        head=root)
    doc = _FakeDoc([marker])
    head, audit = v3._strict_verbal_head(doc, {"marker_start": 0, "marker_end": 6},
                                         {"start": 0, "end": 50})
    assert head is None
    assert "marker_dep_not_mark_or_prep" in audit["reasons"]


def test_extra_clausal_predicate_is_not_scanned_when_no_legal_head(nlp):
    text = "The controller shall act before the restriction of processing is lifted."
    doc = nlp(text)
    record = {"clauses": [_clause(text, "act", "before the restriction of processing is lifted.")]}
    edges, audit = v3.project_record_order_relations(record, text, doc)
    assert edges
    assert edges[0][1] == "the restriction of processing"
    second = audit["clause_audits"][0]["markers"][0]["second_endpoint_audit"]
    assert second["branch"] == "nominal"
    assert "is lifted" not in edges[0][1]


def test_incomplete_of_chain_is_rejected(nlp):
    text = "The controller shall act before the processing of."
    doc = nlp(text)
    record = {"clauses": [_clause(text, "act", "before the processing of.")]}
    edges, audit = v3.project_record_order_relations(record, text, doc)
    assert edges == []
    marker = audit["clause_audits"][0]["markers"][0]
    assert marker["reason"].startswith("nominal_of_chain_")


def test_bounded_nominal_chunk_outside_selected_span_is_rejected(nlp):
    text = "The controller shall act before the processing of personal data."
    doc = nlp(text)
    start = text.index("before")
    end = text.index("processing") + 4  # cuts the noun chunk inside its span
    record = {"clauses": [{
        "clause_id": "synthetic_c1",
        "modality": {"label": "obligation"},
        "actions": [{"id": "a1", "start": text.index("act"), "end": text.index("act") + 3}],
        "actors": [],
        "conditions": [],
        "constraints": [{"id": "c1", "start": start, "end": end}],
        "exceptions": [],
        "actor_action_pairs": [],
        "order_relations": [],
    }]}
    edges, audit = v3.project_record_order_relations(record, text, doc)
    assert edges == []
    assert audit["clause_audits"][0]["markers"][0]["reason"] in {
        "nominal_chunk_outside_selected_span",
        "first_token_after_marker_does_not_start_noun_chunk",
    }

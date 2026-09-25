# -*- coding: utf-8 -*-
"""Focused R3 integration tests (implementation correctness only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.stage3_r3_p2_adapter_v1 import (  # noqa: E402
    R3P2Model,
    analyze_label_text,
    build_endpoint_view,
    build_rule_action_views,
)
from bpc_hybrid.sun_stage3 import temporal_projection_v4_r3 as v4  # noqa: E402
from bpc_hybrid.sun_stage3.r3_sun_scorer import R3SunScorer  # noqa: E402
from bpc_hybrid.sun_stage3.static_vector_similarity_v1 import StaticVectorSimilarity  # noqa: E402

FIXTURES = ROOT / "data/development/stage3_r3_synth/mechanism_fixtures_v1.json"
M1_CONFIG = ROOT / "configs/stage3_table3_r3_m1.json"
M2_CONFIG = ROOT / "configs/stage3_table3_r3_m2.json"


@pytest.fixture(scope="module")
def nlp():
    import spacy
    return spacy.load("en_core_web_sm")


def _span(text: str, sub: str, span_id: str = "x") -> dict:
    start = text.index(sub)
    return {"id": span_id, "start": start, "end": start + len(sub)}


def _clause(text: str, action: str, constraint: str) -> dict:
    return {
        "clause_id": "synthetic_c1",
        "modality": {"label": "obligation"},
        "actions": [_span(text, action)],
        "actors": [],
        "conditions": [],
        "constraints": [_span(text, constraint)],
        "exceptions": [],
        "actor_action_pairs": [],
        "order_relations": [],
    }


def test_v4_retains_passive_event_predicate(nlp):
    text = "The invoice must be approved before the payment is dispatched."
    record = {"clauses": [_clause(text, "be approved", "before the payment is dispatched.")]}
    edges, audit = v4.project_record_order_relations(record, text, nlp(text), nlp=nlp)
    assert edges == [("be approved", "the payment is dispatched")]
    second = audit["clause_audits"][0]["markers"][0]["second_endpoint_audit"]
    assert second["branch"] == "local_verbal_predicate"
    assert second["predicate"]["text"] == "dispatched"


def test_v4_offsets_are_source_substrings(nlp):
    text = "The controller must act before the parcel is dispatched."
    record = {"clauses": [_clause(text, "act", "before the parcel is dispatched.")]}
    edges, audit = v4.project_record_order_relations(record, text, nlp(text), nlp=nlp)
    edge = audit["clause_audits"][0]["derived_edges"][0]
    assert text[edge["before_offsets"][0]:edge["before_offsets"][1]] == edge["before_text"]
    assert text[edge["after_offsets"][0]:edge["after_offsets"][1]] == edge["after_text"]
    assert "dispatched" in edge["after_text"]


def test_v4_rejects_multiple_top_level_events(nlp):
    text = "The controller must act before the parcel is dispatched and the invoice is archived."
    record = {"clauses": [_clause(text, "act", "before the parcel is dispatched and the invoice is archived.")]}
    edges, audit = v4.project_record_order_relations(record, text, nlp(text), nlp=nlp)
    assert edges == []
    marker = audit["clause_audits"][0]["markers"][0]
    assert marker["second_endpoint_audit"]["reason"] == "multiple_top_level_event_predicates"


def test_v4_rejects_truncated_span(nlp):
    text = "The controller shall act before the parcel and"
    record = {"clauses": [_clause(text, "act", "before the parcel and")]}
    edges, audit = v4.project_record_order_relations(record, text, nlp(text), nlp=nlp)
    assert edges == []
    assert "truncated_selected_span" in str(audit)


class _FakeSim:
    def text_pair(self, left: str, right: str) -> float:
        left_tokens = set(str(left).split())
        right_tokens = set(str(right).split())
        return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def _fake_model():
    return SimpleNamespace(
        actions=[
            {"id": "N2", "name": "Approve the invoice", "kind": "activity",
             "match_source_text": "approve invoice"},
            {"id": "N1", "name": "Approve the invoice", "kind": "activity",
             "match_source_text": "approve invoice"},
        ],
        actors=["Controller"],
        actor_sources={"Controller": "pool"},
        action_actor_names={"N1": ["Controller"], "N2": ["Controller"]},
        business_objects=[],
        id_to_name={"N1": "Approve the invoice", "N2": "Approve the invoice"},
        reachable={},
    )


def test_r3_scorer_tie_breaks_by_node_id_and_records_ties():
    scorer = R3SunScorer(_FakeSim(), 0.4, 0.4, 0.6, nlp=None)
    view, _ = build_rule_action_views(None, ["approve the invoice"])
    best_id, score = scorer._best_action_match(view[0], _fake_model())
    assert best_id == "N1"
    assert score > 0.0
    rows = scorer.action_candidate_evidence(view[0], _fake_model())
    assert [row["node_id"] for row in rows] == ["N1", "N2"]
    assert all(row["tied"] for row in rows)
    assert [row["node_id"] for row in rows if row["selected"]] == ["N1"]


def test_adapter_event_extension_keeps_node_id_and_source():
    index = json.loads((ROOT / "outputs/development/stage3_table3_r3_p2_sidecars/index.json").read_text(encoding="utf-8"))
    sidecar = json.loads((ROOT / index["cases"][0]["sidecar_path"]).read_text(encoding="utf-8"))
    events = [n for n in sidecar["nodes"] if n["node_type"] == "event"]
    assert events
    assert all(n["parse_source"] == "r3_p2_event_extension" for n in events)
    assert any("original P2 activity" in sidecar["extension_note"] for _ in [0])


def test_static_vector_unavailable_is_fixed_non_match():
    class _FakeToken:
        is_punct = False
        is_space = False
        lemma_ = "orphan"
        lower_ = "orphan"
        text = "orphan"

    class _FakeDoc:
        vector_size = 3
        meta = {"version": "3.8.0"}
        def __iter__(self):
            return iter([_FakeToken()])

    class _FakeVocab:
        def get(self, key):
            return None

    class _FakeNlpVectors:
        vector_size = 3
        meta = {"version": "3.8.0"}
        vocab = _FakeVocab()

    class _FakeParser:
        def __call__(self, text):
            return _FakeDoc()

    sim = StaticVectorSimilarity(_FakeParser(), _FakeNlpVectors())
    evidence = sim.similarity_with_evidence("orphan", "orphan")
    assert evidence["available"] is False
    assert evidence["score"] == 0.0
    assert sim.text_pair("orphan", "orphan") == 0.0


def test_m1_m2_configs_share_frozen_inputs_and_differ_only_in_backend():
    m1 = json.loads(M1_CONFIG.read_text(encoding="utf-8"))
    m2 = json.loads(M2_CONFIG.read_text(encoding="utf-8"))
    assert m1["scope"] == m2["scope"]
    assert m1["methods"] == m2["methods"]
    assert set(m1["hash_bindings"]) == set(m2["hash_bindings"])
    assert m1["temporal_projection"] == m2["temporal_projection"]
    assert m1["similarity"]["backend"] != m2["similarity"]["backend"]
    assert m1["similarity"]["sm_parser_and_lemma_unchanged"] is True
    assert m2["similarity"]["lg_vectors_only"] is True

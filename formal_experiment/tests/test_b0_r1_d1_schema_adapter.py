"""D1 relay-schema adapter tests (D1-R1, option A).

The relay's deepseek-v4-flash returns nested per-field span containers; the
adapter maps them deterministically to canonical spans and fails closed on
anything non-deterministic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.d1_schema_adapter import (  # noqa: E402
    STATUS_ADAPTED,
    STATUS_FAILED,
    STATUS_UNCHANGED,
    adapt_relay_record,
)

SRC = "The controller shall notify the supervisory authority within 72 hours."


def relay_record(actors=None, actions=None, conditions=None):
    return {
        "schema_version": "1.0.0",
        "sample_id": "estg_demo",
        "source_id": "estg_demo",
        "source_text": SRC,
        "clauses": [
            {
                "clause_id": "estg_demo_c01",
                "clause_span": {"text": SRC, "start": 0, "end": len(SRC)},
                "modality": {"label": "obligation", "evidence": [{"text": "shall", "start": 15, "end": 20}]},
                "actors": actors or [],
                "actions": actions or [],
                "conditions": conditions or [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ],
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


def test_nested_actor_format_is_unfolded() -> None:
    r = relay_record(actors=[
        {"actor_id": "a1", "name": "The controller", "span": {"start": 0, "end": 14, "text": "The controller"}}
    ])
    out, audit = adapt_relay_record(r, SRC)
    assert audit["status"] == STATUS_ADAPTED
    a = out["clauses"][0]["actors"][0]
    assert a == {"id": "a1", "text": "The controller", "start": 0, "end": 14, "normalized": "the controller"}


def test_nested_action_drops_verb_and_object() -> None:
    r = relay_record(actions=[
        {"action_id": "act1", "verb": "notify", "object": "the authority", "span": {"start": 21, "end": 53, "text": "notify the supervisory authority"}}
    ])
    out, audit = adapt_relay_record(r, SRC)
    a = out["clauses"][0]["actions"][0]
    assert set(a) == {"id", "text", "start", "end", "normalized"}
    assert a["text"] == "notify the supervisory authority"
    assert a["start"] == 21 and a["end"] == 53


def test_flat_canonical_span_passes_through() -> None:
    r = relay_record(actors=[{"id": "a1", "text": "The controller", "start": 0, "end": 14, "normalized": "the controller"}])
    out, audit = adapt_relay_record(r, SRC)
    # the adapter re-emits every span in canonical shape; for an already
    # canonical span the output is identical (id/text/start/end/normalized).
    assert out["clauses"][0]["actors"][0] == r["clauses"][0]["actors"][0]
    assert out == r


def test_missing_id_gets_deterministic_id() -> None:
    r = relay_record(actors=[
        {"name": "The controller", "span": {"start": 0, "end": 14, "text": "The controller"}}
    ])
    out, audit = adapt_relay_record(r, SRC)
    assert out["clauses"][0]["actors"][0]["id"] == "estg_demo_c01.actor.1"


def test_missing_span_fails_closed() -> None:
    r = relay_record(actors=[{"actor_id": "a1", "name": "The controller"}])
    out, audit = adapt_relay_record(r, SRC)
    assert audit["status"] == STATUS_FAILED
    assert any("no_flat_or_nested_span" in reason for reason in audit["failed_reasons"])
    assert out == r


def test_text_not_in_source_fails_closed() -> None:
    r = relay_record(actors=[
        {"actor_id": "a1", "span": {"start": 0, "end": 14, "text": "The nonexistent party"}}
    ])
    out, audit = adapt_relay_record(r, SRC)
    assert audit["status"] == STATUS_FAILED
    assert any("text_not_in_source" in reason for reason in audit["failed_reasons"])


def test_non_integer_offsets_fail_closed() -> None:
    r = relay_record(actors=[
        {"actor_id": "a1", "span": {"start": "abc", "end": 14, "text": "The controller"}}
    ])
    out, audit = adapt_relay_record(r, SRC)
    assert audit["status"] == STATUS_FAILED


def test_numeric_string_offsets_coerce_deterministically() -> None:
    r = relay_record(actors=[
        {"actor_id": "a1", "span": {"start": "0", "end": "14", "text": "The controller"}}
    ])
    out, audit = adapt_relay_record(r, SRC)
    assert audit["status"] == STATUS_ADAPTED
    a = out["clauses"][0]["actors"][0]
    assert a["start"] == 0 and a["end"] == 14

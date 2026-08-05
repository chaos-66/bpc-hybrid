"""D1 span-coordinate canonicalizer tests (D1-R1).

Valid spans are untouched, off-by-N spans re-anchor to the unique exact
occurrence of their text, and (per user decision 2026-08-05: empty is legal,
elements may be absent) unrecoverable field spans and clauses are DROPPED
with an audit trail instead of failing the whole record; only record-level
structural violations fail closed.
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

from bpc_hybrid.d1_span_canonicalizer import (  # noqa: E402
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_REANCHORED,
    STATUS_UNCHANGED,
    canonicalize_record_coordinates,
)

SRC = "The taxpayer shall depreciate the acquisition costs in accordance with Section 11(1)."


def record(clause_span, actors=None, constraints=None):
    return {
        "schema_version": "1.0.0",
        "sample_id": "estg_demo",
        "source_id": "estg_demo",
        "source_text": SRC,
        "clauses": [
            {
                "clause_id": "c01",
                "clause_span": clause_span,
                "modality": {"label": "obligation", "evidence": [{"text": "shall", "start": 13, "end": 18}]},
                "actors": actors or [],
                "actions": [],
                "conditions": [],
                "constraints": constraints or [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ],
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


def test_valid_record_is_untouched() -> None:
    r = record(
        {"text": SRC, "start": 0, "end": len(SRC)},
        actors=[{"id": "a01", "text": "The taxpayer", "start": 0, "end": 12, "normalized": "taxpayer"}],
        constraints=[{"id": "c01", "text": "in accordance with Section 11(1)", "start": 52, "end": 84, "normalized": "x"}],
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_UNCHANGED
    assert audit["reanchored_count"] == 0
    assert out == r


def test_off_by_one_clause_span_reanchors() -> None:
    r = record({"text": SRC, "start": 1, "end": len(SRC) + 1})
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_REANCHORED
    assert out["clauses"][0]["clause_span"] == {"text": SRC, "start": 0, "end": len(SRC)}


def test_field_span_reanchors_inside_clause() -> None:
    r = record(
        {"text": SRC, "start": 0, "end": len(SRC)},
        constraints=[{"id": "c01", "text": "in accordance with Section 11(1)", "start": 53, "end": 85, "normalized": "x"}],
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_REANCHORED
    assert out["clauses"][0]["constraints"][0]["start"] == 52
    assert out["clauses"][0]["constraints"][0]["end"] == 84


def test_ambiguous_occurrence_drops_span_and_degrades() -> None:
    src = "the taxpayer and the taxpayer file."
    r = record(
        {"text": src, "start": 0, "end": len(src)},
        actors=[{"id": "a01", "text": "the taxpayer", "start": 99, "end": 111, "normalized": "x"}],
    )
    r["source_text"] = src
    r["clauses"][0]["clause_span"] = {"text": src, "start": 0, "end": len(src)}
    r["clauses"][0]["modality"]["evidence"] = [{"text": src, "start": 0, "end": len(src)}]
    out, audit = canonicalize_record_coordinates(r, src)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_spans"] == ["clauses[0].actors[0]"]
    assert out["clauses"][0]["actors"] == []
    assert out["clauses"][0]["clause_span"] == {"text": src, "start": 0, "end": len(src)}


def test_zero_occurrence_drops_span_and_degrades() -> None:
    r = record(
        {"text": SRC, "start": 0, "end": len(SRC)},
        constraints=[{"id": "c01", "text": "nonexistent phrase here", "start": 10, "end": 30, "normalized": "x"}],
    )
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_spans"] == ["clauses[0].constraints[0]"]
    assert out["clauses"][0]["constraints"] == []


def test_non_integer_offsets_drop_span_and_degrades() -> None:
    r = record({"text": SRC, "start": 0, "end": len(SRC)})
    r["clauses"][0]["constraints"] = [{"id": "c01", "text": "in accordance with Section 11(1)", "start": "52", "end": 84}]
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_spans"] == ["clauses[0].constraints[0]"]
    assert out["clauses"][0]["constraints"] == []


def test_bad_clause_span_drops_clause_and_degrades() -> None:
    r = record({"text": "completely invented clause text", "start": 0, "end": 30})
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_DEGRADED
    assert audit["dropped_clauses"] == [0]
    assert out["clauses"] == []


def test_missing_clauses_treated_as_empty() -> None:
    r = record({"text": SRC, "start": 0, "end": len(SRC)})
    del r["clauses"]
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_UNCHANGED
    assert out["clauses"] == []


def test_record_level_violations_still_fail_closed() -> None:
    r = record({"text": SRC, "start": 0, "end": len(SRC)})
    r["clauses"] = {"not": "a list"}
    out, audit = canonicalize_record_coordinates(r, SRC)
    assert audit["status"] == STATUS_FAILED
    assert audit["failed_reasons"] == ["clauses_not_list"]
    assert out == r

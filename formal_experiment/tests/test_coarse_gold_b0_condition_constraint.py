"""Focused tests for the coarse-gold convergence helper.

Verifies ``keep_span_by_sun_markers`` (word-boundary, case-insensitive,
Sun Table-4 marker matching) and ``converge_gold_record`` (condition/
constraint spans filtered, other fields untouched).  No real files are
touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.coarse_gold_b0_condition_constraint_v1 import (  # noqa: E402
    keep_span_by_sun_markers,
    converge_gold_record,
)


def test_keep_condition_markers() -> None:
    assert keep_span_by_sun_markers("if the business year ends", "condition")
    assert keep_span_by_sun_markers("in case of a transfer", "condition")
    assert keep_span_by_sun_markers("provided that the taxpayer agrees", "condition")
    assert keep_span_by_sun_markers("in the context of this section", "condition")
    assert keep_span_by_sun_markers("who is entitled", "condition")
    assert keep_span_by_sun_markers("the profit which is realized", "condition")


def test_keep_constraint_markers() -> None:
    assert keep_span_by_sun_markers("before the end of the year", "constraint")
    assert keep_span_by_sun_markers("after the transfer", "constraint")
    assert keep_span_by_sun_markers("at least five years", "constraint")
    assert keep_span_by_sun_markers("at most ten percent", "constraint")
    assert keep_span_by_sun_markers("equal to the acquisition costs", "constraint")
    assert keep_span_by_sun_markers("the greatest amount", "constraint")


def test_drop_plain_text_and_cross_field() -> None:
    # No marker at all -> dropped.
    assert not keep_span_by_sun_markers("the acquisition costs", "constraint")
    assert not keep_span_by_sun_markers("the acquisition costs", "condition")
    # Condition markers do not keep constraint spans and vice versa.
    assert not keep_span_by_sun_markers("if the business year ends", "constraint")
    assert not keep_span_by_sun_markers("at least five years", "condition")
    # "after" appears as a word inside longer words -> boundary matters.
    assert not keep_span_by_sun_markers("thereafter the sum", "constraint")


def test_case_insensitive() -> None:
    assert keep_span_by_sun_markers("IF the business year ends", "condition")
    assert keep_span_by_sun_markers("AT LEAST five years", "constraint")


def test_converge_record_filters_only_target_fields() -> None:
    record = {
        "sample_id": "estg_000002",
        "clauses": [
            {
                "clause_id": "estg_000002_c01",
                "conditions": [
                    {"text": "if the business year ends", "start": 0, "end": 10},
                    {"text": "the acquisition costs", "start": 20, "end": 30},
                ],
                "constraints": [
                    {"text": "at least five years", "start": 40, "end": 50},
                    {"text": "a shorter period", "start": 60, "end": 70},
                ],
                "actions": [{"text": "the profit shall be taken into account", "start": 80, "end": 100}],
                "modality": {"label": "obligation", "evidence": [{"text": "shall", "start": 90, "end": 95}]},
            }
        ],
    }
    out = converge_gold_record(record)
    cond = out["clauses"][0]["conditions"]
    cons = out["clauses"][0]["constraints"]
    assert [c["text"] for c in cond] == ["if the business year ends"]
    assert [c["text"] for c in cons] == ["at least five years"]
    # Untouched fields stay intact.
    assert out["clauses"][0]["actions"][0]["text"] == "the profit shall be taken into account"
    assert out["clauses"][0]["modality"]["evidence"][0]["text"] == "shall"
    assert out["sample_id"] == "estg_000002"


def test_converge_does_not_mutate_input() -> None:
    record = {
        "sample_id": "estg_000002",
        "clauses": [
            {
                "clause_id": "estg_000002_c01",
                "conditions": [
                    {"text": "if the business year ends", "start": 0, "end": 10},
                ],
            }
        ],
    }
    converge_gold_record(record)
    assert len(record["clauses"][0]["conditions"]) == 1

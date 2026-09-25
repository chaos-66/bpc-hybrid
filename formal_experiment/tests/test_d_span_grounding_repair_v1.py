"""Focused tests for the zero-API span-grounding repair replay.

These tests exercise the replay helpers on a synthetic one-row fixture; they do
not touch the frozen 150-record dataset or call the evaluator network path.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import run_d_span_grounding_repair_v1 as experiment  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import (  # noqa: E402
    COST_METRIC_START_END,
    POLICY_LEGACY,
    POLICY_REPAIR,
)

SRC = "the fund must pay and the fund must pay."


def _span(text, start, end, span_id):
    return {"id": span_id, "text": text, "start": start, "end": end,
            "normalized": " ".join(text.casefold().split())}


def _adapter_record():
    return {
        "schema_version": "1.0.0",
        "sample_id": "synthetic_000001",
        "source_id": "synthetic_000001",
        "source_text": SRC,
        "clauses": [{
            "clause_id": "c01",
            "clause_span": {"text": SRC, "start": 0, "end": len(SRC)},
            "modality": {"label": "obligation", "evidence": []},
            "actors": [
                _span("the fund", 1, 9, "a01"),
                _span("the fund", 20, 28, "a02"),
            ],
            "actions": [], "conditions": [], "constraints": [], "exceptions": [],
            "actor_action_map": [], "order_relations": [],
        }],
        "method": {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


def _fake_evaluator(rows):
    return {"metrics": {"overall": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
                        "per_field": {}}}


def _prepared():
    return [{"sample_id": "synthetic_000001", "adapter_record": _adapter_record(),
             "adapter_audit": {}, "failure": None}]


def test_old_arm_drops_repeated_actors_and_new_arm_recovers_them():
    old_rows, _old_audits, old_result = experiment._run_arm(
        _prepared(), {"synthetic_000001": SRC},
        policy=POLICY_LEGACY, cost_metric=COST_METRIC_START_END,
        evaluator=_fake_evaluator)
    new_rows, _new_audits, new_result = experiment._run_arm(
        _prepared(), {"synthetic_000001": SRC},
        policy=POLICY_REPAIR, cost_metric=COST_METRIC_START_END,
        evaluator=_fake_evaluator)
    assert old_result["telemetry"]["canonicalizer_spans_dropped"] == 2
    assert old_result["telemetry"]["dropped_by_field"] == {"actor": 2}
    assert old_rows[0]["record"]["clauses"][0]["actors"] == []
    assert new_result["telemetry"]["canonicalizer_spans_dropped"] == 0
    assert new_result["telemetry"]["recovered_by_field"] == {"actor": 2}
    actors = new_rows[0]["record"]["clauses"][0]["actors"]
    assert [(a["id"], a["start"], a["end"]) for a in actors] == [("a01", 0, 8), ("a02", 22, 30)]


def test_invariance_audit_explains_every_new_span_and_mutates_nothing():
    old_rows, old_audits, _ = experiment._run_arm(
        _prepared(), {"synthetic_000001": SRC}, policy=POLICY_LEGACY,
        cost_metric=COST_METRIC_START_END, evaluator=_fake_evaluator)
    new_rows, new_audits, _ = experiment._run_arm(
        _prepared(), {"synthetic_000001": SRC}, policy=POLICY_REPAIR,
        cost_metric=COST_METRIC_START_END, evaluator=_fake_evaluator)
    audit = experiment.semantic_invariance_audit(_prepared(), old_rows, new_rows)
    assert audit["invented_semantic_spans"] == 0
    assert audit["field_reclassification"] == 0
    assert audit["text_mutation"] == 0
    assert audit["normalized_mutation"] == 0
    assert audit["id_mutation"] == 0
    assert audit["old_only_spans"] == 0
    assert audit["new_only_spans"] == 2
    assert audit["new_only_spans_explained_by_old_drops"] == 2


def test_replay_is_deterministic():
    first_rows, first_audits, _ = experiment._run_arm(
        _prepared(), {"synthetic_000001": SRC}, policy=POLICY_REPAIR,
        cost_metric=COST_METRIC_START_END, evaluator=_fake_evaluator)
    second_rows, second_audits, _ = experiment._run_arm(
        _prepared(), {"synthetic_000001": SRC}, policy=POLICY_REPAIR,
        cost_metric=COST_METRIC_START_END, evaluator=_fake_evaluator)
    assert first_rows == second_rows
    assert first_audits == second_audits
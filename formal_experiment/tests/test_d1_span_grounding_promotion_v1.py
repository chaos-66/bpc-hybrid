# -*- coding: utf-8 -*-
"""Focused regression tests for the repair_v1 default promotion.

These tests pin the two public contracts introduced by the promotion:

* ordinary calls to ``canonicalize_record_coordinates`` use ``repair_v1``;
* historical frozen replays explicitly pin ``legacy`` and remain exact.

The full-artifact tests are skipped when the local-only EStG raw responses are
not available; the synthetic default/legacy tests always run.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from bpc_hybrid.d1_span_canonicalizer import (  # noqa: E402
    DEFAULT_POLICY,
    POLICY_LEGACY,
    POLICY_REPAIR,
    canonicalize_record_coordinates,
)


def _span(text, start, end, span_id):
    return {"id": span_id, "text": text, "start": start, "end": end,
            "normalized": " ".join(text.casefold().split())}


def _repeated_record():
    src = "the fund must pay and the fund must pay."
    first = src.index("the fund")
    second = src.index("the fund", first + 1)
    record = {
        "schema_version": "1.0.0",
        "sample_id": "synthetic_promotion_0001",
        "source_id": "synthetic_promotion_0001",
        "source_text": src,
        "clauses": [{
            "clause_id": "c01",
            "clause_span": {"text": src, "start": 0, "end": len(src)},
            "modality": {"label": "obligation", "evidence": []},
            "actors": [
                _span("the fund", first + 1, first + 9, "a01"),
                _span("the fund", second + 1, second + 9, "a02"),
            ],
            "actions": [], "conditions": [], "constraints": [],
            "exceptions": [], "actor_action_map": [], "order_relations": [],
        }],
        "method": {"name": "direct_llm",
                   "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True,
                       "errors": []},
        "unsupported_or_ambiguous": [],
    }
    return record, src


def test_p1_p4_default_call_is_repair_v1():
    record, source = _repeated_record()
    default_out, default_audit = canonicalize_record_coordinates(record, source)
    repair_out, repair_audit = canonicalize_record_coordinates(
        record, source, policy=POLICY_REPAIR)
    assert DEFAULT_POLICY == POLICY_REPAIR
    assert default_out == repair_out
    assert default_audit == repair_audit
    assert len(default_out["clauses"][0]["actors"]) == 2
    assert default_audit["reanchored_repeated_exact"] == 2


def test_explicit_legacy_still_fails_closed_on_repeated_occurrence():
    record, source = _repeated_record()
    legacy_out, legacy_audit = canonicalize_record_coordinates(
        record, source, policy=POLICY_LEGACY)
    assert legacy_out["clauses"][0]["actors"] == []
    assert legacy_audit["reanchored_repeated_exact"] == 0
    assert len(legacy_audit["dropped_spans"]) == 2


def _local_paths_available(*paths: Path) -> bool:
    return all(path.is_file() for path in paths)


def _require_local_or_skip(*paths: Path) -> None:
    if not _local_paths_available(*paths):
        pytest.skip("local-only frozen D-full-0813 artifacts are unavailable")


def test_p2_explicit_legacy_replays_locked_canonical_predictions_exactly():
    import run_barrientos_ablation_suite_v2 as runner
    from run_barrientos_ablation_suite_v2 import _prediction_row

    base = (ROOT / "outputs/development/barrientos_ablation_suite_v2/"
            "D-full-0813/repeat-01")
    _require_local_or_skip(base / "raw_responses.jsonl",
                           base / "canonical_predictions.jsonl")
    raw = [json.loads(line) for line in
           (base / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()
           if line.strip()]
    locked = [json.loads(line) for line in
              (base / "canonical_predictions.jsonl").read_text(
                  encoding="utf-8").splitlines() if line.strip()]
    source_by_id = {row["sample_id"]: row["text"]
                    for row in runner._estg_samples()}
    replayed = [
        _prediction_row(
            runner.parse_same_response(
                row, "D-full-0813", source_by_id[row["sample_id"]]),
            "D-full-0813")
        for row in raw
    ]
    assert len(locked) == len(replayed) == 150
    assert replayed == locked


def test_p3_historical_postprocessing_full_chain_replays_checked_in_metrics():
    import run_d_full_postprocessing_ablation_v1 as ablation
    import run_barrientos_ablation_suite_v2 as runner

    _require_local_or_skip(ablation.RAW_PATH, ablation.REPORT_JSON)
    raw = [json.loads(line) for line in
           ablation.RAW_PATH.read_text(encoding="utf-8").splitlines()
           if line.strip()]
    source_by_id = {row["sample_id"]: row["text"]
                    for row in runner._estg_samples()}
    rows, _telemetry = ablation.process_condition(
        raw, source_by_id, ablation.CONDITIONS["full_postprocessing"])
    evaluated = runner._make_evaluator("D-full-0813")(rows)
    checked_in = json.loads(ablation.REPORT_JSON.read_text(encoding="utf-8"))
    expected = checked_in["conditions"]["full_postprocessing"]["overall"]
    actual = evaluated["metrics"]["overall"]
    for key in ("precision", "recall", "f1"):
        assert abs(actual[key] - expected[key]) < 1e-12


def test_p5_frozen_replay_has_no_semantic_mutation():
    import run_d_span_grounding_repair_v1 as experiment
    import run_barrientos_ablation_suite_v2 as runner

    base = (ROOT / "outputs/development/barrientos_ablation_suite_v2/"
            "D-full-0813/repeat-01")
    _require_local_or_skip(base / "raw_responses.jsonl")
    raw = [json.loads(line) for line in
           (base / "raw_responses.jsonl").read_text(encoding="utf-8").splitlines()
           if line.strip()]
    source_by_id = {row["sample_id"]: row["text"]
                    for row in runner._estg_samples()}
    prepared, _ = experiment._prepare_rows(raw, source_by_id)

    def evaluator(_rows):
        return {"metrics": {"overall": {}, "per_field": {}}}

    old_rows, _old_audits, _ = experiment._run_arm(
        prepared, source_by_id, policy=POLICY_LEGACY,
        cost_metric=experiment.COST_METRIC_START_END, evaluator=evaluator)
    new_rows, _new_audits, _ = experiment._run_arm(
        prepared, source_by_id, policy=POLICY_REPAIR,
        cost_metric=experiment.COST_METRIC_START_END, evaluator=evaluator)
    audit = experiment.semantic_invariance_audit(prepared, old_rows, new_rows)
    assert audit["invented_semantic_spans"] == 0
    assert audit["field_reclassification"] == 0
    assert audit["text_mutation"] == 0
    assert audit["normalized_mutation"] == 0
    assert audit["id_mutation"] == 0

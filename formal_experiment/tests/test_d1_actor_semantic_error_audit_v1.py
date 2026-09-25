# -*- coding: utf-8 -*-
"""Focused tests for the read-only Actor semantic error audit."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import audit_d1_actor_semantic_error_v1 as audit  # noqa: E402


def _span(text, start, end, span_id=None):
    out = {"text": text, "start": start, "end": end,
           "normalized": " ".join(text.casefold().split())}
    if span_id is not None:
        out["id"] = span_id
    return out


def _record(source, actors=None, conditions=None, actions=None):
    return {
        "schema_version": "1.0.0",
        "sample_id": "synthetic",
        "source_id": "synthetic",
        "source_text": source,
        "clauses": [{
            "clause_id": "c1",
            "clause_span": {"text": source, "start": 0, "end": len(source)},
            "modality": {"label": "obligation", "evidence": []},
            "actors": actors or [],
            "actions": actions or [],
            "conditions": conditions or [],
            "constraints": [],
            "exceptions": [],
            "actor_action_map": [],
            "order_relations": [],
        }],
        "method": {"name": "direct_llm",
                   "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True,
                       "errors": []},
        "unsupported_or_ambiguous": [],
    }


def test_a1_gold_actor_fully_inside_condition_is_fn_b():
    source = "If the taxpayer claims, the spouse shall pay."
    start = source.index("the taxpayer")
    end = start + len("the taxpayer")
    gold_actor = _span("the taxpayer", start, end, "g1")
    gold = _record(source, actors=[gold_actor])
    pred = _record(source, conditions=[
        _span("If the taxpayer claims", 0, source.index(","), "c1")])
    case = audit.classify_fn_case(
        sample_id="synthetic", gold_record=gold, pred_record=pred,
        source_text=source, gold_actor=gold_actor)
    assert case["taxonomy"] == "FN-B_EMBEDDED_IN_CONDITION"
    assert case["condition_overlap"] is True


def test_a2_gold_actor_absent_from_all_emitted_spans_is_fn_a():
    source = "The taxpayer shall pay."
    gold_actor = _span("taxpayer", source.index("taxpayer"),
                       source.index("taxpayer") + len("taxpayer"), "g1")
    gold = _record(source, actors=[gold_actor])
    pred = _record(source, actions=[_span("shall pay", 16, 25, "p1")])
    case = audit.classify_fn_case(
        sample_id="synthetic", gold_record=gold, pred_record=pred,
        source_text=source, gold_actor=gold_actor)
    assert case["taxonomy"] == "FN-A_ABSENT_FROM_ALL_MODEL_SEMANTIC_SPANS"
    assert case["cross_field_overlap"] is False


def test_a3_duplicate_occurrence_is_fn_g():
    source = "The bank shall pay. The bank shall collect."
    second = source.rindex("The bank")
    gold = _record(source, actors=[
        _span("The bank", 0, 8, "g1"),
        _span("The bank", second, second + 8, "g2"),
    ])
    pred = _record(source, actors=[_span("The bank", 0, 8, "p1")])
    case = audit.classify_fn_case(
        sample_id="synthetic", gold_record=gold, pred_record=pred,
        source_text=source, gold_actor=_span("The bank", second, second + 8, "g2"))
    assert case["taxonomy"] == "FN-G_DUPLICATE_OCCURRENCE_COVERAGE"
    assert case["same_surface_predicted_elsewhere"] is True


def test_a4_pronoun_prediction_without_gold_is_fp_a():
    source = "It shall apply."
    gold = _record(source, actors=[])
    pred_actor = _span("It", 0, 2, "p1")
    case = audit.classify_fp_case(
        sample_id="synthetic", gold_record=gold,
        pred_record=_record(source, actors=[pred_actor]),
        source_text=source, pred_actor=pred_actor)
    assert case["taxonomy"] == "FP-A_PRONOUN_DEMONSTRATIVE"


def test_a5_legal_role_without_gold_is_not_automatically_pronoun_or_non_role():
    source = "The taxpayer shall pay."
    gold = _record(source, actors=[])
    pred_actor = _span("The taxpayer", 0, 12, "p1")
    case = audit.classify_fp_case(
        sample_id="synthetic", gold_record=gold,
        pred_record=_record(source, actors=[pred_actor]),
        source_text=source, pred_actor=pred_actor)
    assert case["taxonomy"] == "FP-C_LEGAL_NORMATIVE_ROLE_BUT_GOLD_UNANNOTATED"
    assert case["gold_review_candidate"] is True


def test_a6_overlap_detection_uses_character_intervals_not_text_search():
    source = "The bank shall pay. The bank shall collect."
    second = source.rindex("The bank")
    gold_actor = _span("The bank", second, second + 8, "g1")
    gold = _record(source, actors=[gold_actor])
    # The condition contains the same surface string at the first occurrence.
    pred = _record(source, conditions=[
        _span("The bank shall pay", 0, 18, "c1")])
    case = audit.classify_fn_case(
        sample_id="synthetic", gold_record=gold, pred_record=pred,
        source_text=source, gold_actor=gold_actor)
    assert case["taxonomy"] != "FN-B_EMBEDDED_IN_CONDITION"
    assert case["condition_overlap"] is False


def _tiny_inventory_inputs():
    source = "The taxpayer shall pay."
    gold_actor = _span("taxpayer", 4, 12, "g1")
    gold = _record(source, actors=[gold_actor])
    pred = _record(source, actors=[_span("taxpayer", 4, 12, "p1")])
    predictions = [{"sample_id": "synthetic", "request_status": "ok",
                    "record": pred}]
    gold_by_id = {"synthetic": gold}
    source_by_id = {"synthetic": source}
    return predictions, gold_by_id, source_by_id


def test_a7_build_is_deterministic():
    predictions, gold_by_id, source_by_id = _tiny_inventory_inputs()
    first = audit.build_actor_inventory(
        predictions, gold_by_id, source_by_id)
    second = audit.build_actor_inventory(
        predictions, gold_by_id, source_by_id)
    assert first == second
    assert first["tp_count"] == 1
    assert first["fp_count"] == 0
    assert first["fn_count"] == 0


def test_a8_build_does_not_mutate_inputs():
    predictions, gold_by_id, source_by_id = _tiny_inventory_inputs()
    before_predictions = copy.deepcopy(predictions)
    before_gold = copy.deepcopy(gold_by_id)
    audit.build_actor_inventory(predictions, gold_by_id, source_by_id)
    assert predictions == before_predictions
    assert gold_by_id == before_gold

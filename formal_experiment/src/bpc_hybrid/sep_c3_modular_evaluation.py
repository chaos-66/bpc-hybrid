# -*- coding: utf-8 -*-
"""Shared coarse sentence-level evaluation for the SEP-C3 E/S/J ablation.

The frozen project main view is the sentence-level coarse FIVE span-bearing
fields (actor/action/condition/constraint/exception).  The modality label is
reported separately; modality evidence spans are structurally unavailable in
the published decision-only Gold and are never folded into the span F1.

This module does not modify the frozen evaluator.  It calls the shared
``stage2_sun_literal_overlap`` implementation and exposes the five-field
summary (arithmetic mean of per-field F1, plus micro P/R/F1 as a diagnostic).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from bpc_hybrid.formal_stage2_evaluation import (
    evaluate_modality_labels,
    evaluate_span_metrics,
    published_gold_to_evaluator,
)
from bpc_hybrid.g04_coarse_view import build_coarse_view
from bpc_hybrid.stage2_sun_literal_overlap import evaluate_sun_literal_overlap


SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
PRIMARY_METRIC = "coarse_five_field_mean_f1"
DATASET_ID = "independently_reconstructed_estg_150_v1"


def _micro_prf(counts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    extracted = sum(int(v.get("extracted") or 0) for v in counts.values())
    ground_truth = sum(int(v.get("ground_truth") or 0) for v in counts.values())
    matched_predictions = sum(
        int(v.get("matched_predictions") or 0) for v in counts.values())
    matched_ground_truth = sum(
        int(v.get("matched_ground_truth") or 0) for v in counts.values())
    precision = matched_predictions / extracted if extracted else 0.0
    recall = matched_ground_truth / ground_truth if ground_truth else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "ground_truth": ground_truth,
        "extracted": extracted,
        "matched_predictions": matched_predictions,
        "matched_ground_truth": matched_ground_truth,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_coarse(gold_doc: dict[str, Any],
                    attempts: Sequence[Mapping[str, Any]],
                    *,
                    method_id: str) -> dict[str, Any]:
    """Evaluate attempts on the frozen coarse five-field main view.

    ``attempts`` must be canonical envelopes
    ``{sample_id, request_status, record: {...}}``.  Failed rows must remain
    present; the frozen evaluator counts them as empty predictions.
    """
    coarse_gold = build_coarse_view(gold_doc)

    # Official formal view wrapper: confirms the frozen five span fields and
    # keeps the unavailable modality-evidence declaration explicit.
    official = evaluate_span_metrics(
        coarse_gold,
        list(attempts),
        dataset_id=DATASET_ID,
        method_id=method_id,
        view="coarse_sentence_level",
    )

    raw = evaluate_sun_literal_overlap(
        coarse_gold,
        list(attempts),
        dataset_id=DATASET_ID,
        method_id=method_id,
    )
    per_field = raw.get("per_field") or {}
    five = {field: dict(per_field.get(field) or {}) for field in SPAN_FIELDS}
    for field in SPAN_FIELDS:
        official_field = (official.get("span_fields") or {}).get(field) or {}
        for key in ("ground_truth", "extracted", "precision", "recall", "f1"):
            if official_field.get(key) != five[field].get(key):
                raise RuntimeError(
                    f"frozen evaluator parity mismatch for {field}.{key}: "
                    f"official={official_field.get(key)!r} raw={five[field].get(key)!r}"
                )

    f1_values = [float(v.get("f1") or 0.0) for v in five.values()]
    mean_f1 = sum(f1_values) / len(f1_values) if f1_values else 0.0
    micro = _micro_prf(five)
    labels = evaluate_modality_labels(
        published_gold_to_evaluator(gold_doc), list(attempts))

    return {
        "schema_version": "sep_c3_coarse_five_field_evaluation@1.0.0",
        "dataset_id": DATASET_ID,
        "method_id": method_id,
        "view": "coarse_sentence_level",
        "primary_metric": PRIMARY_METRIC,
        "primary_metric_note": (
            "arithmetic mean of the five coarse span-field F1 values; the "
            "modality label is reported separately and is never mixed into "
            "this score"
        ),
        "match_rule": "independent_same_field_any_nonempty_character_span_intersection",
        "five_fields": five,
        "coarse_five_field_mean_f1": mean_f1,
        "coarse_five_field_micro": micro,
        "modality_labels": labels,
        "modality_evidence_span": {
            "available": False,
            "policy": "published decision-only Gold has no local modality evidence spans; never zeroed or aggregated into span F1",
        },
        "official_formal_view": official,
        "denominator": len(attempts),
        "failed_count": sum(
            1 for a in attempts if a.get("request_status") != "ok"),
    }


def attempt_rows(prediction_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Convert persisted prediction rows to evaluator attempt envelopes."""
    return [
        {
            "sample_id": row["sample_id"],
            "request_status": row.get("request_status", "failed"),
            "record": row.get("record") or {},
        }
        for row in prediction_rows
    ]

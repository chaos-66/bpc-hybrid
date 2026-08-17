# -*- coding: utf-8 -*-
"""Deterministic S2.12 complexity-stratified error evaluator (Checkpoint D).

Pure, fail-closed, ZERO LLM/API. Computes per-stratum (G0.5 frozen level
L1/L2/L3) per-field precision/recall/F1 and error-type counts from
method predictions vs a Gold view, on the SAME sample set:

  * predictions: {sample_id: {field: value|None}}  (one method arm)
  * gold:        {sample_id: {field: value|None}}  (user-adjudicated view)
  * levels:      {sample_id: "L1"|"L2"|"L3"}       (frozen G0.5 levels)

Fail-closed rules:
  * sample sets must match EXACTLY (missing / extra ids refuse)
  * all six decision fields must be present on both sides
  * values are compared by exact string equality (None means absent)
  * error types per field per sample:
      correct           pred == gold (both non-null)
      missed            gold non-null, pred is None
      misclassified     both non-null, pred != gold
      extra             pred non-null, gold is None
  * per stratum per field: P = correct / preds_non_null,
    R = correct / gold_non_null, F1 (0 when P+R == 0); plus counts
  * deterministic: sorted iteration, no wall clock, no randomness

This module never reads Gold or any corpus file itself; callers pass
plain dictionaries (the S2.12 runner is the gatekeeper).
"""

from __future__ import annotations

from typing import Any

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")


class EvaluatorFail(Exception):
    """Fail-closed evaluator abort."""


def evaluate(predictions: dict[str, dict[str, str | None]],
             gold: dict[str, dict[str, str | None]],
             levels: dict[str, str]) -> dict[str, Any]:
    """Stratified per-field evaluation. Returns a deterministic report."""
    pred_ids = set(predictions)
    gold_ids = set(gold)
    level_ids = set(levels)
    if pred_ids != gold_ids:
        raise EvaluatorFail(
            "predictions/gold sample mismatch: missing=" +
            str(sorted(gold_ids - pred_ids)) +
            " extra=" + str(sorted(pred_ids - gold_ids)))
    if level_ids != gold_ids:
        raise EvaluatorFail(
            "levels sample mismatch: missing=" +
            str(sorted(gold_ids - level_ids)) +
            " extra=" + str(sorted(level_ids - gold_ids)))
    if not gold_ids:
        raise EvaluatorFail("empty sample set")
    valid_levels = {"L1", "L2", "L3"}
    for sample_id in gold_ids:
        if levels[sample_id] not in valid_levels:
            raise EvaluatorFail(
                f"{sample_id}: level {levels[sample_id]!r} outside "
                f"{sorted(valid_levels)}")
        for field in DECISION_FIELDS:
            if field not in predictions[sample_id]:
                raise EvaluatorFail(f"{sample_id}: prediction missing field "
                                    f"{field!r}")
            if field not in gold[sample_id]:
                raise EvaluatorFail(f"{sample_id}: gold missing field "
                                    f"{field!r}")

    strata: dict[str, dict[str, Any]] = {}
    for level in sorted(valid_levels):
        members = sorted(sid for sid in gold_ids if levels[sid] == level)
        per_field: dict[str, Any] = {}
        for field in DECISION_FIELDS:
            tp = fp = fn = 0
            error_types = {"correct": 0, "missed": 0, "misclassified": 0,
                           "extra": 0}
            for sid in members:
                p = predictions[sid][field]
                g = gold[sid][field]
                if p is not None and g is not None:
                    if p == g:
                        tp += 1
                        error_types["correct"] += 1
                    else:
                        fp += 1
                        fn += 1
                        error_types["misclassified"] += 1
                elif g is not None:
                    fn += 1
                    error_types["missed"] += 1
                elif p is not None:
                    fp += 1
                    error_types["extra"] += 1
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = (2 * precision * recall / (precision + recall)
                  if (precision + recall) else 0.0)
            per_field[field] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "correct": tp,
                "misclassified": fp,
                "missed": fn,
                "extra": 0,  # computed below (pred non-null, gold null)
                "error_types": error_types,
            }
        # extra count = number of samples where pred non-null and gold null
        for field in DECISION_FIELDS:
            extra_count = sum(
                1 for sid in members
                if predictions[sid][field] is not None
                and gold[sid][field] is None)
            per_field[field]["extra"] = extra_count
        strata[level] = {
            "samples": len(members),
            "per_field": per_field,
        }
    return {
        "schema_version": "s2_12_stratified_evaluator@1.0.0",
        "sample_count": len(gold_ids),
        "strata": strata,
        "zero_api": {"new_llm_api_calls": 0},
    }

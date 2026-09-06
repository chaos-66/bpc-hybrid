# -*- coding: utf-8 -*-
"""Unified five-class decision for the S3.9-EXT four new-type extension.

Why
---
The original panel runner generated the *variant* prediction as "the
expected (preset) type or None" (``run_method`` read ``expected_violation``),
while the *control* side prediction was integrated from all four type
scores.  Those are two different decision rules, so neither the variant-only
table nor the paired five-class accuracy could serve as a classification
result.  This module applies ONE deterministic rule to BOTH sides:

- per type, a side score entry is rebuilt from the persisted row fields as
  ``{score, observable, reason, exact_contradiction}`` exactly like the
  control side of the original paired evaluation;
- the decision is ``control_prediction_from_scores`` (fixed
  ``EXTENDED_TYPES`` priority order, unobservable types skipped, prohibited
  ``score >= gamma_ext``, condition/constraint/exception ``score >
  gamma_ext`` or exact contradiction, ``none`` if no violation among the
  observable types, ``None`` if all four types are unobservable);
- the decision function never reads ``expected_violation``, gold labels or
  the sample id; gold enters only afterwards inside the evaluators.

Old per-sample predictions are preserved as ``predicted_conditional_old``
and the old style is labelled "conditional detection for the preset type",
not classification.
"""

from __future__ import annotations

from typing import Any, Mapping

from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    control_prediction_from_scores,
)

UNIFIED_DECISION_NAME = "unified_five_class_decision_v1"


def side_scores_from_row(row: Mapping[str, Any], side: str) -> dict[str, Any]:
    """Rebuild one side's per-type decision inputs from a persisted row.

    ``side="variant"`` uses row["scores"] + row["scores_detail"] +
    row["observability"]; ``side="control"`` uses row["control_scores"]
    directly (already in the clean shape).  Raises on missing fields so a
    stale row can never silently fall back to an old rule.
    """
    if side == "control":
        control = row.get("control_scores")
        if not isinstance(control, dict):
            raise ValueError("row lacks control_scores")
        out: dict[str, Any] = {}
        for t in EXTENDED_TYPES:
            entry = control.get(t)
            if not isinstance(entry, dict):
                raise ValueError(f"row lacks control_scores[{t}]")
            out[t] = {
                "score": entry.get("score"),
                "observable": bool(entry.get("observable", False)),
                "reason": entry.get("reason"),
                "exact_contradiction": entry.get("exact_contradiction"),
            }
        return out
    if side == "variant":
        scores = row.get("scores")
        detail = row.get("scores_detail")
        observability = row.get("observability")
        if not isinstance(scores, dict) or not isinstance(detail, dict) \
                or not isinstance(observability, dict):
            raise ValueError("row lacks variant scores/scores_detail/observability")
        out = {}
        for t in EXTENDED_TYPES:
            obs = observability.get(t)
            if not isinstance(obs, dict):
                raise ValueError(f"row lacks observability[{t}]")
            out[t] = {
                "score": scores.get(t),
                "observable": bool(obs.get("observable", False)),
                "reason": obs.get("reason"),
                "exact_contradiction": detail.get(t, {}).get("exact_contradiction")
                if isinstance(detail.get(t), dict) else None,
            }
        return out
    raise ValueError(f"unknown side {side!r}")


def unified_prediction(row: Mapping[str, Any], side: str,
                       gamma_ext: float = 0.5) -> dict[str, Any]:
    """Deterministic unified decision for one side of one sample.

    Never touches ``expected_violation`` / gold / item ids.
    """
    side_scores = side_scores_from_row(row, side)
    result = control_prediction_from_scores(side_scores, gamma_ext)
    return {
        "predicted": result["predicted"],
        "per_type": result["per_type"],
        "all_unobservable": result["all_unobservable"],
        "decision": UNIFIED_DECISION_NAME,
        "side": side,
    }


def unified_rows(rows: list[dict[str, Any]],
                 gamma_ext: float = 0.5) -> list[dict[str, Any]]:
    """Copy rows with a unified variant prediction; preserve everything else.

    The old conditional prediction is kept under
    ``predicted_conditional_old``; ``predicted_violation_type`` becomes the
    unified decision.  Rows with a persisted ``external_failure`` (missing /
    failed Stage-2 prediction) have all-unobservable scores, so the unified
    decision yields None and they stay counted as failures/unobservable.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        old = copy.get("predicted_violation_type")
        copy["predicted_conditional_old"] = old
        unified = unified_prediction(copy, "variant", gamma_ext)
        raw = unified["predicted"]
        # raw decision may be None (all four types unobservable), 'none'
        # (observable compliant), or one of the four violation types.  The
        # shared evaluators only accept None-or-violation-type for variants,
        # so an observable 'none' answer is mapped to None there (still an
        # error for a variant whose gold is a violation) while the raw
        # decision stays recorded for the confusion matrix.
        copy["unified_predicted_raw"] = raw
        copy["predicted_violation_type"] = (
            None if raw is None or raw == NONE_LABEL else raw)
        copy["prediction_rule"] = UNIFIED_DECISION_NAME
        copy["prediction_all_unobservable"] = unified["all_unobservable"]
        copy["prediction_observable_compliant"] = bool(raw == NONE_LABEL)
        out.append(copy)
    return out

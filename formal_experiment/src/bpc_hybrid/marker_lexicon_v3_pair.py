"""Exact paired metric gate for the source-reconstructed marker lexicon v3."""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping


FIELD_ORDER = ("modality", "actor", "action", "condition", "constraint", "exception")
TARGETS = (("condition", "precision"), ("constraint", "recall"))


class MarkerLexiconPairError(ValueError):
    """Raised when paired metrics cannot support the preregistered gate."""


def _ratio(item: Mapping[str, Any], metric: str) -> Fraction:
    if metric == "precision":
        numerator = item.get("matched_predictions")
        denominator = item.get("extracted")
    elif metric == "recall":
        numerator = item.get("matched_ground_truth")
        denominator = item.get("ground_truth")
    else:
        raise MarkerLexiconPairError(f"unknown metric: {metric}")
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise MarkerLexiconPairError(f"{metric} counts must be integers")
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise MarkerLexiconPairError(f"invalid {metric} counts")
    return Fraction(numerator, denominator) if denominator else Fraction(0, 1)


def _fraction_record(value: Fraction) -> dict[str, int | float]:
    return {
        "numerator": value.numerator,
        "denominator": value.denominator,
        "decimal": float(value),
    }


def _count_record(item: Mapping[str, Any]) -> dict[str, int]:
    required = (
        "ground_truth",
        "extracted",
        "matched_predictions",
        "matched_ground_truth",
        "misclassified",
        "missed",
    )
    result: dict[str, int] = {}
    for key in required:
        value = item.get(key)
        if not isinstance(value, int) or value < 0:
            raise MarkerLexiconPairError(f"invalid count: {key}")
        result[key] = value
    return result


def build_paired_comparison(
    baseline_metrics: Mapping[str, Any], candidate_metrics: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply exact P/R no-regression and targeted-improvement gates."""

    baseline_fields = baseline_metrics.get("per_field")
    candidate_fields = candidate_metrics.get("per_field")
    if not isinstance(baseline_fields, Mapping) or not isinstance(
        candidate_fields, Mapping
    ):
        raise MarkerLexiconPairError("paired metrics lack per_field objects")
    if not set(FIELD_ORDER).issubset(baseline_fields) or not set(FIELD_ORDER).issubset(
        candidate_fields
    ):
        raise MarkerLexiconPairError("paired metrics do not cover all six fields")

    per_field: dict[str, Any] = {}
    regressions: list[str] = []
    strict_improvements: list[str] = []
    for field in FIELD_ORDER:
        baseline_item = baseline_fields[field]
        candidate_item = candidate_fields[field]
        if not isinstance(baseline_item, Mapping) or not isinstance(
            candidate_item, Mapping
        ):
            raise MarkerLexiconPairError(f"invalid per-field metric object: {field}")
        baseline_counts = _count_record(baseline_item)
        candidate_counts = _count_record(candidate_item)
        metric_records: dict[str, Any] = {}
        for metric in ("precision", "recall"):
            baseline_ratio = _ratio(baseline_item, metric)
            candidate_ratio = _ratio(candidate_item, metric)
            delta = candidate_ratio - baseline_ratio
            no_regression = delta >= 0
            strict_improvement = delta > 0
            key = f"{field}.{metric}"
            if not no_regression:
                regressions.append(key)
            if strict_improvement:
                strict_improvements.append(key)
            metric_records[metric] = {
                "baseline": _fraction_record(baseline_ratio),
                "candidate": _fraction_record(candidate_ratio),
                "delta": _fraction_record(delta),
                "no_regression": no_regression,
                "strict_improvement": strict_improvement,
            }
        per_field[field] = {
            "baseline_counts": baseline_counts,
            "candidate_counts": candidate_counts,
            **metric_records,
        }

    target_improvements = [
        f"{field}.{metric}"
        for field, metric in TARGETS
        if per_field[field][metric]["strict_improvement"]
    ]
    zero_regression_passed = not regressions
    target_improvement_passed = bool(target_improvements)
    replacement_allowed = zero_regression_passed and target_improvement_passed
    return {
        "schema_version": "marker_lexicon_zero_regression_comparison@1.0.0",
        "field_order": list(FIELD_ORDER),
        "metric_semantics": {
            "precision": "matched_predictions / extracted",
            "recall": "matched_ground_truth / ground_truth",
            "comparison_arithmetic": "exact rational counts; decimals are presentation only",
        },
        "gate": {
            "required_no_regression_checks": 12,
            "regressions": regressions,
            "zero_regression_passed": zero_regression_passed,
            "target_metrics": [f"{field}.{metric}" for field, metric in TARGETS],
            "target_improvements": target_improvements,
            "target_improvement_passed": target_improvement_passed,
            "all_strict_improvements": strict_improvements,
            "replacement_allowed": replacement_allowed,
            "decision": (
                "promote_candidate_pointer"
                if replacement_allowed
                else "reject_candidate_keep_active_v2"
            ),
        },
        "per_field": per_field,
    }

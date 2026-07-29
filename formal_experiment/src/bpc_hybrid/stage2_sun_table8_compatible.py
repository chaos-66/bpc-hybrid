"""Sun Table 8-compatible phrase extraction evaluation.

Sun et al. (2024) count a predicted phrase as matched when its span has a
non-empty intersection with a ground-truth phrase of the same semantic type.
This module applies that rule at the statement level.  Maximum-cardinality
one-to-one matching keeps both Table 8 accounting identities true:

* extracted = matched + misclassified
* ground truth = matched + missed

The modality row evaluates modality evidence spans as the semantic concept;
four-class modality-label correctness remains a separate evaluation task.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


SCHEMA_VERSION = "sun_table8_compatible_evaluation@1.0.0"
LITERAL_SCHEMA_VERSION = "sun_table8_literal_overlap_evaluation@2.0.0"
FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
PLURAL_KEYS = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}


class SunTable8EvaluationError(ValueError):
    """Raised when the evaluation inputs do not satisfy the shared contract."""


def _validated_span(value: Mapping[str, Any], *, label: str) -> tuple[int, int]:
    start = value.get("start")
    end = value.get("end")
    if (
        isinstance(start, bool)
        or isinstance(end, bool)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or start < 0
        or end <= start
    ):
        raise SunTable8EvaluationError(f"{label} has an invalid [start,end) span")
    return start, end


def _field_spans(record: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    clauses = record.get("clauses") or []
    if not isinstance(clauses, list):
        raise SunTable8EvaluationError("record clauses must be an array")
    spans: list[Mapping[str, Any]] = []
    for clause_index, clause in enumerate(clauses):
        if not isinstance(clause, Mapping):
            raise SunTable8EvaluationError(f"clause {clause_index} is not an object")
        if field == "modality":
            modality = clause.get("modality") or {}
            values = modality.get("evidence") or [] if isinstance(modality, Mapping) else []
        else:
            values = clause.get(PLURAL_KEYS[field]) or []
        if not isinstance(values, list):
            raise SunTable8EvaluationError(
                f"clause {clause_index} field {field} must be an array"
            )
        for span_index, span in enumerate(values):
            if not isinstance(span, Mapping):
                raise SunTable8EvaluationError(
                    f"clause {clause_index} field {field} span {span_index} is not an object"
                )
            _validated_span(
                span,
                label=f"clause {clause_index} field {field} span {span_index}",
            )
            spans.append(span)
    return spans


def _intersects(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    left_start, left_end = _validated_span(left, label="left")
    right_start, right_end = _validated_span(right, label="right")
    return max(left_start, right_start) < min(left_end, right_end)


def _maximum_intersection_matches(
    gold_spans: Sequence[Mapping[str, Any]],
    predicted_spans: Sequence[Mapping[str, Any]],
) -> int:
    adjacency = [
        [
            predicted_index
            for predicted_index, predicted_span in enumerate(predicted_spans)
            if _intersects(gold_span, predicted_span)
        ]
        for gold_span in gold_spans
    ]
    predicted_owner: dict[int, int] = {}

    def augment(gold_index: int, seen: set[int]) -> bool:
        for predicted_index in adjacency[gold_index]:
            if predicted_index in seen:
                continue
            seen.add(predicted_index)
            owner = predicted_owner.get(predicted_index)
            if owner is None or augment(owner, seen):
                predicted_owner[predicted_index] = gold_index
                return True
        return False

    return sum(augment(index, set()) for index in range(len(gold_spans)))


def _prf(matched: int, misclassified: int, missed: int) -> dict[str, float | int]:
    precision = matched / (matched + misclassified) if matched + misclassified else 0.0
    recall = matched / (matched + missed) if matched + missed else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "matched": matched,
        "misclassified": misclassified,
        "missed": missed,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def evaluate_sun_table8_compatible(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    dataset_id: str,
    method_id: str,
) -> dict[str, Any]:
    """Evaluate six semantic phrase types using Sun Table 8 span matching."""

    gold_by_id: dict[str, Mapping[str, Any]] = {}
    for row in gold_records:
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in gold_by_id:
            raise SunTable8EvaluationError("Gold sample_ids must be unique non-empty strings")
        gold_by_id[sample_id] = row

    attempt_by_id: dict[str, Mapping[str, Any]] = {}
    for attempt in attempts:
        sample_id = attempt.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in attempt_by_id:
            raise SunTable8EvaluationError("attempt sample_ids must be unique non-empty strings")
        attempt_by_id[sample_id] = attempt
    if set(attempt_by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(attempt_by_id))[:5]
        extra = sorted(set(attempt_by_id) - set(gold_by_id))[:5]
        raise SunTable8EvaluationError(
            f"attempt membership differs from Gold: missing={missing}, extra={extra}"
        )

    counts = {
        field: {
            "ground_truth": 0,
            "extracted": 0,
            "matched": 0,
            "misclassified": 0,
            "missed": 0,
        }
        for field in FIELDS
    }
    invalid_attempt_count = 0
    for sample_id, gold in gold_by_id.items():
        attempt = attempt_by_id[sample_id]
        predicted = attempt.get("record")
        if attempt.get("request_status") != "ok" or not isinstance(predicted, Mapping):
            invalid_attempt_count += 1
            predicted = {"clauses": []}
        for field in FIELDS:
            gold_spans = _field_spans(gold, field)
            predicted_spans = _field_spans(predicted, field)
            matched = _maximum_intersection_matches(gold_spans, predicted_spans)
            counts[field]["ground_truth"] += len(gold_spans)
            counts[field]["extracted"] += len(predicted_spans)
            counts[field]["matched"] += matched
            counts[field]["misclassified"] += len(predicted_spans) - matched
            counts[field]["missed"] += len(gold_spans) - matched

    per_field: dict[str, dict[str, float | int]] = {}
    for field, values in counts.items():
        metrics = _prf(
            values["matched"], values["misclassified"], values["missed"]
        )
        per_field[field] = {
            "ground_truth": values["ground_truth"],
            "extracted": values["extracted"],
            **metrics,
        }

    overall_matched = sum(values["matched"] for values in counts.values())
    overall_misclassified = sum(values["misclassified"] for values in counts.values())
    overall_missed = sum(values["missed"] for values in counts.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "method_id": method_id,
        "sample_count": len(gold_by_id),
        "invalid_attempt_count": invalid_attempt_count,
        "evaluation_unit": "statement",
        "match_rule": "same_semantic_field_any_nonempty_character_span_intersection",
        "assignment": "maximum_cardinality_one_to_one",
        "clause_alignment_required": False,
        "modality_policy": "evidence_span_extraction_only_label_ignored",
        "per_field": per_field,
        "overall": {
            "ground_truth": sum(values["ground_truth"] for values in counts.values()),
            "extracted": sum(values["extracted"] for values in counts.values()),
            **_prf(overall_matched, overall_misclassified, overall_missed),
        },
    }


def evaluate_sun_table8_literal_overlap(
    gold_records: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    dataset_id: str,
    method_id: str,
) -> dict[str, Any]:
    """Apply Sun's literal independent any-overlap rule to all six fields.

    Precision counts every predicted phrase that intersects at least one Gold
    phrase of the same type. Recall counts every Gold phrase that intersects at
    least one predicted phrase of the same type. There is no clause alignment,
    overlap threshold, boundary penalty, or one-to-one assignment.
    """

    gold_by_id: dict[str, Mapping[str, Any]] = {}
    for row in gold_records:
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in gold_by_id:
            raise SunTable8EvaluationError("Gold sample_ids must be unique non-empty strings")
        gold_by_id[sample_id] = row

    attempt_by_id: dict[str, Mapping[str, Any]] = {}
    for attempt in attempts:
        sample_id = attempt.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in attempt_by_id:
            raise SunTable8EvaluationError("attempt sample_ids must be unique non-empty strings")
        attempt_by_id[sample_id] = attempt
    if set(attempt_by_id) != set(gold_by_id):
        missing = sorted(set(gold_by_id) - set(attempt_by_id))[:5]
        extra = sorted(set(attempt_by_id) - set(gold_by_id))[:5]
        raise SunTable8EvaluationError(
            f"attempt membership differs from Gold: missing={missing}, extra={extra}"
        )

    counts = {
        field: {
            "ground_truth": 0,
            "extracted": 0,
            "matched_predictions": 0,
            "matched_ground_truth": 0,
        }
        for field in FIELDS
    }
    invalid_attempt_count = 0
    for sample_id, gold in gold_by_id.items():
        attempt = attempt_by_id[sample_id]
        predicted = attempt.get("record")
        if attempt.get("request_status") != "ok" or not isinstance(predicted, Mapping):
            invalid_attempt_count += 1
            predicted = {"clauses": []}
        for field in FIELDS:
            gold_spans = _field_spans(gold, field)
            predicted_spans = _field_spans(predicted, field)
            counts[field]["ground_truth"] += len(gold_spans)
            counts[field]["extracted"] += len(predicted_spans)
            counts[field]["matched_predictions"] += sum(
                any(_intersects(predicted_span, gold_span) for gold_span in gold_spans)
                for predicted_span in predicted_spans
            )
            counts[field]["matched_ground_truth"] += sum(
                any(_intersects(gold_span, predicted_span) for predicted_span in predicted_spans)
                for gold_span in gold_spans
            )

    per_field: dict[str, dict[str, float | int]] = {}
    for field, values in counts.items():
        matched_predictions = values["matched_predictions"]
        matched_ground_truth = values["matched_ground_truth"]
        extracted = values["extracted"]
        ground_truth = values["ground_truth"]
        precision = matched_predictions / extracted if extracted else 0.0
        recall = matched_ground_truth / ground_truth if ground_truth else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_field[field] = {
            "ground_truth": ground_truth,
            "extracted": extracted,
            "matched_predictions": matched_predictions,
            "matched_ground_truth": matched_ground_truth,
            "misclassified": extracted - matched_predictions,
            "missed": ground_truth - matched_ground_truth,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    total_extracted = sum(values["extracted"] for values in counts.values())
    total_ground_truth = sum(values["ground_truth"] for values in counts.values())
    total_matched_predictions = sum(
        values["matched_predictions"] for values in counts.values()
    )
    total_matched_ground_truth = sum(
        values["matched_ground_truth"] for values in counts.values()
    )
    precision = total_matched_predictions / total_extracted if total_extracted else 0.0
    recall = total_matched_ground_truth / total_ground_truth if total_ground_truth else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "schema_version": LITERAL_SCHEMA_VERSION,
        "dataset_id": dataset_id,
        "method_id": method_id,
        "sample_count": len(gold_by_id),
        "invalid_attempt_count": invalid_attempt_count,
        "evaluation_unit": "statement",
        "match_rule": "independent_same_field_any_nonempty_character_span_intersection",
        "assignment": "none_independent_overlap_coverage",
        "clause_alignment_required": False,
        "modality_policy": "evidence_span_extraction_only_label_ignored",
        "per_field": per_field,
        "overall": {
            "ground_truth": total_ground_truth,
            "extracted": total_extracted,
            "matched_predictions": total_matched_predictions,
            "matched_ground_truth": total_matched_ground_truth,
            "misclassified": total_extracted - total_matched_predictions,
            "missed": total_ground_truth - total_matched_ground_truth,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
    }

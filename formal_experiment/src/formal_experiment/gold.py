"""Gold review loading and validation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
SUN_RECORD_ARRAYS = ("actions", "actors", "actor_action_map", "order_relations")


@dataclass
class GoldValidationResult:
    """Validation result for a gold review JSONL file."""

    path: str
    total_lines: int = 0
    valid_json: int = 0
    invalid_json: int = 0
    reviewed: int = 0
    needs_review: int = 0
    filled_gold_rows: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def format_valid(self) -> bool:
        return self.invalid_json == 0 and not self.errors

    @property
    def fully_reviewed(self) -> bool:
        return self.total_lines > 0 and self.reviewed == self.total_lines

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "total_lines": self.total_lines,
            "valid_json": self.valid_json,
            "invalid_json": self.invalid_json,
            "reviewed": self.reviewed,
            "needs_review": self.needs_review,
            "filled_gold_rows": self.filled_gold_rows,
            "format_valid": self.format_valid,
            "fully_reviewed": self.fully_reviewed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def _is_filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    if isinstance(value, dict):
        return bool(value)
    return True


def validate_gold_review(path: Path) -> GoldValidationResult:
    result = GoldValidationResult(path=str(path))

    if not path.exists():
        result.errors.append(f"missing file: {path}")
        return result

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            result.total_lines += 1
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                result.invalid_json += 1
                result.errors.append(f"line {line_number}: invalid JSON: {exc}")
                continue

            result.valid_json += 1
            _validate_row(row, line_number, result)

    return result


def _validate_row(
    row: dict[str, Any],
    line_number: int,
    result: GoldValidationResult,
) -> None:
    required_top = {
        "sample_id",
        "source_text",
        "reference_predictions",
        "gold_fields",
        "gold_sun_record",
        "human_review",
    }
    missing_top = sorted(required_top - set(row))
    if missing_top:
        result.errors.append(
            f"line {line_number}: missing top-level keys: {missing_top}"
        )
        return

    gold_fields = row.get("gold_fields")
    if not isinstance(gold_fields, dict):
        result.errors.append(f"line {line_number}: gold_fields must be an object")
        return

    missing_fields = [field for field in FIELDS if field not in gold_fields]
    if missing_fields:
        result.errors.append(
            f"line {line_number}: missing gold_fields keys: {missing_fields}"
        )

    if any(_is_filled(gold_fields.get(field)) for field in FIELDS):
        result.filled_gold_rows += 1

    sun_record = row.get("gold_sun_record")
    if not isinstance(sun_record, dict):
        result.errors.append(f"line {line_number}: gold_sun_record must be an object")
    else:
        for key in SUN_RECORD_ARRAYS:
            if key not in sun_record:
                result.errors.append(
                    f"line {line_number}: gold_sun_record missing {key}"
                )
            elif not isinstance(sun_record[key], list):
                result.errors.append(
                    f"line {line_number}: gold_sun_record.{key} must be an array"
                )

    review = row.get("human_review")
    if not isinstance(review, dict):
        result.errors.append(f"line {line_number}: human_review must be an object")
        return

    status = review.get("status")
    if status == "reviewed":
        result.reviewed += 1
        _validate_review_metadata(review, line_number, result)
    elif status == "needs_review":
        result.needs_review += 1
    else:
        result.warnings.append(
            f"line {line_number}: unexpected review status {status!r}"
        )


def _validate_review_metadata(
    review: dict[str, Any],
    line_number: int,
    result: GoldValidationResult,
) -> None:
    for key in ("reviewer", "reviewed_at", "confidence"):
        if not _is_filled(review.get(key)):
            result.errors.append(
                f"line {line_number}: reviewed row missing human_review.{key}"
            )

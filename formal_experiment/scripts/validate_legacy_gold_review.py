# -*- coding: utf-8 -*-
"""Validate the legacy development review format (no semantic checking).

Checks that a filled-in gold review JSONL file has correct structure.
Does NOT judge whether the gold values are semantically correct.

Usage:
    python scripts/validate_legacy_gold_review.py
    python scripts/validate_legacy_gold_review.py --input path/to/review.jsonl
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_INPUT = _PROJECT_ROOT / "data" / "development" / "gold_review" / "sun_stage2_gold_review_template.jsonl"

_VALID_MODALITIES = {"obligation", "prohibition", "permission", "definition", "unknown", ""}
_VALID_REVIEW_STATUSES = {"needs_review", "reviewed", "skip"}

_REQUIRED_TOP_KEYS = {"sample_id", "source_text", "gold_fields", "gold_sun_record", "human_review"}
_REQUIRED_GOLD_FIELDS = {"modality", "actor", "action", "condition", "constraint", "exception"}
_REQUIRED_GOLD_SUN_RECORD = {"actions", "actors", "actor_action_map", "order_relations"}
_REQUIRED_HUMAN_REVIEW = {"reviewer", "reviewed_at", "confidence", "notes", "status"}


def validate_record(rec: dict, line_num: int) -> list[dict]:
    """Validate a single gold review record. Returns list of issues."""
    issues = []

    # Check top-level keys
    for key in _REQUIRED_TOP_KEYS:
        if key not in rec:
            issues.append({
                "line": line_num,
                "type": "missing_key",
                "detail": f"Missing required key: {key}",
                "severity": "error",
            })

    # Check sample_id
    if not rec.get("sample_id"):
        issues.append({
            "line": line_num,
            "type": "empty_sample_id",
            "detail": "sample_id is empty",
            "severity": "error",
        })

    # Check source_text
    if not rec.get("source_text"):
        issues.append({
            "line": line_num,
            "type": "empty_source_text",
            "detail": "source_text is empty",
            "severity": "error",
        })

    # Check gold_fields
    gold_fields = rec.get("gold_fields", {})
    if not isinstance(gold_fields, dict):
        issues.append({
            "line": line_num,
            "type": "invalid_gold_fields",
            "detail": "gold_fields must be a dict",
            "severity": "error",
        })
    else:
        for field in _REQUIRED_GOLD_FIELDS:
            if field not in gold_fields:
                issues.append({
                    "line": line_num,
                    "type": "missing_gold_field",
                    "detail": f"gold_fields missing: {field}",
                    "severity": "error",
                })

        # Check modality value
        modality = gold_fields.get("modality")
        if modality is not None and modality not in _VALID_MODALITIES:
            issues.append({
                "line": line_num,
                "type": "invalid_modality",
                "detail": f"modality must be one of {_VALID_MODALITIES}, got: {modality!r}",
                "severity": "error",
            })

        # Check string fields
        for field in ["actor", "action", "condition", "constraint", "exception"]:
            val = gold_fields.get(field)
            if val is not None and not isinstance(val, str):
                issues.append({
                    "line": line_num,
                    "type": "invalid_field_type",
                    "detail": f"gold_fields.{field} must be string or null, got: {type(val).__name__}",
                    "severity": "error",
                })

    # Check gold_sun_record
    gold_sun = rec.get("gold_sun_record", {})
    if not isinstance(gold_sun, dict):
        issues.append({
            "line": line_num,
            "type": "invalid_gold_sun_record",
            "detail": "gold_sun_record must be a dict",
            "severity": "error",
        })
    else:
        for key in _REQUIRED_GOLD_SUN_RECORD:
            if key not in gold_sun:
                issues.append({
                    "line": line_num,
                    "type": "missing_gold_sun_key",
                    "detail": f"gold_sun_record missing: {key}",
                    "severity": "error",
                })
            elif not isinstance(gold_sun[key], list):
                issues.append({
                    "line": line_num,
                    "type": "invalid_gold_sun_type",
                    "detail": f"gold_sun_record.{key} must be an array, got: {type(gold_sun[key]).__name__}",
                    "severity": "error",
                })

    # Check human_review
    human_review = rec.get("human_review", {})
    if not isinstance(human_review, dict):
        issues.append({
            "line": line_num,
            "type": "invalid_human_review",
            "detail": "human_review must be a dict",
            "severity": "error",
        })
    else:
        for key in _REQUIRED_HUMAN_REVIEW:
            if key not in human_review:
                issues.append({
                    "line": line_num,
                    "type": "missing_human_review_key",
                    "detail": f"human_review missing: {key}",
                    "severity": "error",
                })

        status = human_review.get("status")
        if status not in _VALID_REVIEW_STATUSES:
            issues.append({
                "line": line_num,
                "type": "invalid_review_status",
                "detail": f"human_review.status must be one of {_VALID_REVIEW_STATUSES}, got: {status!r}",
                "severity": "error",
            })

        # If reviewed, check required fields
        if status == "reviewed":
            if not human_review.get("reviewer"):
                issues.append({
                    "line": line_num,
                    "type": "missing_reviewer",
                    "detail": "status=reviewed but reviewer is empty",
                    "severity": "error",
                })
            if not human_review.get("reviewed_at"):
                issues.append({
                    "line": line_num,
                    "type": "missing_reviewed_at",
                    "detail": "status=reviewed but reviewed_at is empty",
                    "severity": "error",
                })
            if human_review.get("confidence") is None:
                issues.append({
                    "line": line_num,
                    "type": "missing_confidence",
                    "detail": "status=reviewed but confidence is null",
                    "severity": "error",
                })

    return issues


def validate_file(path: Path) -> dict:
    """Validate an entire gold review JSONL file."""
    result = {
        "file": str(path),
        "exists": path.exists(),
        "total_lines": 0,
        "valid_json_lines": 0,
        "invalid_json_lines": 0,
        "issues": [],
        "summary": {},
    }

    if not path.exists():
        result["issues"].append({
            "line": 0,
            "type": "file_not_found",
            "detail": f"File not found: {path}",
            "severity": "error",
        })
        return result

    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            result["total_lines"] += 1
            line = line.strip()
            if not line:
                continue

            try:
                rec = json.loads(line)
                result["valid_json_lines"] += 1
            except json.JSONDecodeError as e:
                result["invalid_json_lines"] += 1
                result["issues"].append({
                    "line": i + 1,
                    "type": "invalid_json",
                    "detail": f"JSON parse error: {e}",
                    "severity": "error",
                })
                continue

            record_issues = validate_record(rec, i + 1)
            result["issues"].extend(record_issues)

    # Summary
    error_count = sum(1 for i in result["issues"] if i["severity"] == "error")
    warning_count = sum(1 for i in result["issues"] if i["severity"] == "warning")
    reviewed_count = 0
    needs_review_count = 0

    # Re-read to count statuses
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                status = rec.get("human_review", {}).get("status", "")
                if status == "reviewed":
                    reviewed_count += 1
                elif status == "needs_review":
                    needs_review_count += 1
            except json.JSONDecodeError:
                pass

    result["summary"] = {
        "total_lines": result["total_lines"],
        "valid_json": result["valid_json_lines"],
        "invalid_json": result["invalid_json_lines"],
        "errors": error_count,
        "warnings": warning_count,
        "reviewed": reviewed_count,
        "needs_review": needs_review_count,
        "format_valid": error_count == 0 and result["invalid_json_lines"] == 0,
    }

    return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Validate gold review file format")
    parser.add_argument("--input", type=str, default=str(_DEFAULT_INPUT),
                        help="Path to gold review JSONL file")
    args = parser.parse_args()

    path = Path(args.input)

    print("=" * 60)
    print("Gold Review File Validation")
    print("=" * 60)
    print(f"  File: {path}")
    print()

    result = validate_file(path)
    s = result["summary"]

    print(f"  Total lines: {s['total_lines']}")
    print(f"  Valid JSON: {s['valid_json']}")
    print(f"  Invalid JSON: {s['invalid_json']}")
    print(f"  Errors: {s['errors']}")
    print(f"  Warnings: {s['warnings']}")
    print(f"  Reviewed: {s['reviewed']}")
    print(f"  Needs review: {s['needs_review']}")
    print()

    if s["format_valid"]:
        print("  FORMAT VALID")
    else:
        print("  FORMAT INVALID")
        print()
        print("  Issues:")
        for issue in result["issues"][:20]:
            print(f"    Line {issue['line']}: [{issue['type']}] {issue['detail']}")
        if len(result["issues"]) > 20:
            print(f"    ... and {len(result['issues']) - 20} more issues")

    print()


if __name__ == "__main__":
    main()

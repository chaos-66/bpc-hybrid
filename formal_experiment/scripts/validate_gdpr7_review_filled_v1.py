# -*- coding: utf-8 -*-
"""Validate the GDPR7 six-element review EDITABLE document once filled (v1).

Checks the editable decisions document
(``data/development/human_review/gdpr7_six_element_review_decisions_v1.json``,
schema ``gdpr7_six_element_review_editable@1.0.0``) against the frozen blank
surface and the review rules:

* structural checks of the editable top level and of every rule/sentence;
* immutable identity vs the blank surface: dataset_id, counts, rule and
  sample_id census + order, per-sentence identity fields and the candidate
  object must equal the blank sentence-for-sentence;
* per-field review decisions: decision values ∈ {accepted, edited, rejected},
  edited requires a non-empty edited_value (modality ∈ the 4 controlled
  labels; text fields must be verbatim contiguous substrings of the sentence
  text), accepted/rejected require edited_value == null;
* review_state ∈ {unreviewed, reviewed}; ``reviewed`` is only legal when all
  six fields of the sentence are decided and every field is legal;
* advisory warnings are reported but never fatal (multi-modal-verb sentences,
  non-verbatim candidate values).

Exit codes: 0 = no errors (and, with ``--require-complete``, additionally
reviewed == total and decisions_total == fields_total); 1 = validation errors
(or ``--require-complete`` not satisfied); 2 = usage / file errors (missing
file or blank, unreadable JSON).

The validator never writes any file except the optional ``--report-json``
report. Zero LLM/API/network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    DEFAULT_BLANK_PATH,
    DEFAULT_EDITABLE_PATH,
    SCHEMA_EDITABLE,
    audit_filled_document,
    collect_stats,
    doc_json_bytes,
    load_json,
)


def check_filled(doc: dict[str, Any], blank_doc: dict[str, Any]) -> dict[str, Any]:
    """Pure full validation of a filled editable document.

    Returns ``{"errors": [...], "warnings": [...], "sample_errors": int,
    "stats": {...}, "complete": bool}``. ``complete`` means zero errors AND
    every sentence reviewed AND every one of the sentences_total*6 fields
    decided.
    """
    audit = audit_filled_document(doc, blank_doc, require_blank=True)
    stats = collect_stats(doc)
    complete = (
        not audit["errors"]
        and stats["reviewed"] == stats["sentences_total"]
        and stats["decisions_total"] == stats["fields_total"]
        and stats["sentences_total"] > 0
    )
    return {
        "errors": audit["errors"],
        "warnings": audit["warnings"],
        "sample_errors": audit["sample_errors"],
        "stats": stats,
        "complete": complete,
    }


def _load_or_exit(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"{label} 文件不存在: {path}")
    try:
        doc = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取 {label} 文件 {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise SystemExit(f"{label} 文件不是 JSON 对象: {path}")
    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_PATH,
                        help="filled editable document to validate")
    parser.add_argument("--blank", type=Path, default=DEFAULT_BLANK_PATH,
                        help="blank surface used for the identity comparison")
    parser.add_argument("--require-complete", action="store_true",
                        help="additionally require reviewed=total and "
                             "decisions_total=fields_total (exit 1 otherwise)")
    parser.add_argument("--report-json", type=Path, default=None,
                        help="write the JSON validation report to this path "
                             "(default: no file is written)")
    args = parser.parse_args()

    doc = _load_or_exit(args.file, "editable")
    blank_doc = _load_or_exit(args.blank, "blank")

    result = check_filled(doc, blank_doc)
    errors = result["errors"]
    warnings = result["warnings"]
    stats = result["stats"]
    complete = result["complete"]

    for msg in errors:
        print(f"  ERROR: {msg}")
    for msg in warnings:
        print(f"  WARN : {msg}")

    print(
        f"sentences={stats['sentences_total']} reviewed={stats['reviewed']} "
        f"unreviewed={stats['unreviewed']} "
        f"decisions={stats['decisions_total']}/{stats['fields_total']} "
        f"(accepted={stats['accepted']} edited={stats['edited']} "
        f"rejected={stats['rejected']}) errors={len(errors)} "
        f"warnings={len(warnings)}"
    )

    require_ok = True
    if args.require_complete and not complete:
        require_ok = False
        print(
            "  --require-complete 未满足：要求 reviewed==total 且 "
            "decisions_total==fields_total 且无 error"
        )

    if args.report_json is not None:
        report = {
            "schema_version": "gdpr7_review_filled_validation_report@1.0.0",
            "editable_schema_version": doc.get("schema_version"),
            "file": str(args.file),
            "blank": str(args.blank),
            "errors": errors,
            "warnings": warnings,
            "sample_errors": result["sample_errors"],
            "stats": stats,
            "complete": complete,
            "require_complete_ok": require_ok,
        }
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_bytes(doc_json_bytes(report))
        print(f"报告已写入: {args.report_json}")

    if errors:
        print(f"GDPR7 editable review validation FAILED: {len(errors)} error(s)")
        return 1
    if not require_ok:
        print("GDPR7 editable review validation PASSED but --require-complete 未满足")
        return 1
    print("GDPR7 editable review validation PASSED (no errors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

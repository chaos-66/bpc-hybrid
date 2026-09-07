# -*- coding: utf-8 -*-
"""Freeze-closure verification for the GDPR7 six-element review (v1).

Checks whether the formal editable decisions document
(``data/development/human_review/gdpr7_six_element_review_decisions_v1.json``)
is frozen-ready for the (separately authorized) Gold publication step:

* every sentence is ``reviewed`` (reviewed == total) and every one of the
  ``sentences_total * 6`` fields carries a legal decision
  (decisions_total == fields_total, 0 errors from the shared full audit
  against the blank surface);
* the document's immutable identity equals the blank surface
  (dataset_id, counts, rule/sample order, sentence identity fields, candidate
  objects);
* the import confirmation event JSON exists, carries a non-empty reviewer and
  event id, ``gold_created == false``, ``append_only == true``, its
  ``source_file_sha256`` matches the actual bytes of the user source file when
  ``--source`` is given (or is at least present otherwise), and its
  ``source_blank_sha256`` matches the current blank file bytes.

This verifier NEVER creates Gold and NEVER writes the editable file: the only
file it may create is the optional ``--report-json`` report. ``frozen=false``
exits 1.

Zero LLM/API/network.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_review_rules_v1 import (  # noqa: E402
    DEFAULT_BLANK_PATH,
    DEFAULT_EDITABLE_PATH,
    audit_filled_document,
    collect_stats,
    doc_json_bytes,
    load_json,
    sha256_file,
    validate_confirmation_event,
)


def check_frozen(file_doc: dict[str, Any],
                 blank_doc: dict[str, Any],
                 confirmation_doc: Any,
                 source_file_sha256: Optional[str] = None,
                 blank_file_sha256: Optional[str] = None) -> dict[str, Any]:
    """Pure freeze-closure check.

    Returns ``{"frozen": bool, "reasons": [...], "counts": {...},
    "stats": {...}, "warnings": [...], "confirmation_problems": [...]}``.
    ``frozen`` is true only when there are no reasons.
    """
    reasons: list[str] = []
    audit = audit_filled_document(file_doc, blank_doc, require_blank=True)
    stats = collect_stats(file_doc)
    for msg in audit["errors"]:
        reasons.append(msg)

    if stats["reviewed"] != stats["sentences_total"]:
        reasons.append(
            f"reviewed {stats['reviewed']} != sentences_total "
            f"{stats['sentences_total']}"
        )
    if stats["decisions_total"] != stats["fields_total"]:
        reasons.append(
            f"decisions_total {stats['decisions_total']} != fields_total "
            f"{stats['fields_total']}"
        )
    if stats["sentences_total"] == 0:
        reasons.append("document contains no sentences")

    conf_problems: list[str] = []
    if confirmation_doc is None:
        conf_problems.append("confirmation event not provided")
    else:
        conf_problems.extend(validate_confirmation_event(
            confirmation_doc,
            source_file_sha256=source_file_sha256,
            target_file_sha256=None,  # target may legitimately advance later
            blank_file_sha256=blank_file_sha256,
        ))
    if conf_problems:
        reasons.append("confirmation: " + "; ".join(conf_problems))

    counts = {
        "sentences_total": stats["sentences_total"],
        "reviewed": stats["reviewed"],
        "unreviewed": stats["unreviewed"],
        "decisions_total": stats["decisions_total"],
        "fields_total": stats["fields_total"],
    }
    return {
        "frozen": not reasons,
        "reasons": reasons,
        "counts": counts,
        "stats": stats,
        "warnings": audit["warnings"],
        "confirmation_problems": conf_problems,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_PATH,
                        help="filled editable document to verify")
    parser.add_argument("--blank", type=Path, default=DEFAULT_BLANK_PATH,
                        help="blank surface used for identity checks")
    parser.add_argument("--confirmation", type=Path, default=None,
                        help="import confirmation event JSON")
    parser.add_argument("--source", type=Path, default=None,
                        help="user source decisions file whose bytes must match "
                             "confirmation.source_file_sha256")
    parser.add_argument("--report-json", type=Path, default=None,
                        help="write the JSON freeze report to this path "
                             "(default: no file is written)")
    args = parser.parse_args()

    for label, path in (("editable", args.file), ("blank", args.blank)):
        if not path.is_file():
            raise SystemExit(f"{label} 文件不存在: {path}")
    if args.source is not None and not args.source.is_file():
        raise SystemExit(f"source 文件不存在: {args.source}")
    if args.confirmation is not None and not args.confirmation.is_file():
        raise SystemExit(f"confirmation 文件不存在: {args.confirmation}")

    try:
        file_doc = load_json(args.file)
        blank_doc = load_json(args.blank)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"无法读取输入文件: {exc}") from exc

    confirmation_doc = None
    if args.confirmation is not None:
        try:
            confirmation_doc = load_json(args.confirmation)
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"无法读取 confirmation 文件: {exc}") from exc

    source_sha = sha256_file(args.source) if args.source is not None else None
    blank_sha = sha256_file(args.blank)
    result = check_frozen(
        file_doc=file_doc,
        blank_doc=blank_doc,
        confirmation_doc=confirmation_doc,
        source_file_sha256=source_sha,
        blank_file_sha256=blank_sha,
    )

    for msg in result["reasons"]:
        print(f"  REASON: {msg}")
    for msg in result["warnings"]:
        print(f"  WARN  : {msg}")
    counts = result["counts"]
    print(
        f"frozen={result['frozen']} | reviewed={counts['reviewed']}/"
        f"{counts['sentences_total']} | "
        f"decisions={counts['decisions_total']}/{counts['fields_total']} | "
        f"reasons={len(result['reasons'])}"
    )

    if args.report_json is not None:
        report = {
            "schema_version": "gdpr7_review_freeze_report@1.0.0",
            "frozen": result["frozen"],
            "counts": result["counts"],
            "stats": result["stats"],
            "warnings": result["warnings"],
            "reasons": result["reasons"],
            "confirmation_problems": result["confirmation_problems"],
            "confirmation": {
                "path": str(args.confirmation) if args.confirmation else None,
                "event_id": (confirmation_doc or {}).get("event_id"),
                "reviewer": (confirmation_doc or {}).get("reviewer"),
                "schema_version": (confirmation_doc or {}).get("schema_version"),
            } if isinstance(confirmation_doc, dict) else None,
            "files": {
                "file": str(args.file),
                "blank": str(args.blank),
                "source": str(args.source) if args.source else None,
            },
        }
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_bytes(doc_json_bytes(report))
        print(f"冻结报告已写入: {args.report_json}")

    return 0 if result["frozen"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

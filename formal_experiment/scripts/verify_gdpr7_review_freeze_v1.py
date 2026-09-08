# -*- coding: utf-8 -*-
"""Freeze-closure verification for the GDPR7 six-element review (v1/v2).

Checks whether the formal editable decisions document is frozen-ready for the
(separately authorized) Gold publication step.  By default it verifies the v2
editable decisions document
(``data/development/human_review/gdpr7_six_element_review_decisions_v2.json``,
schema ``gdpr7_six_element_review_editable@1.1.0``); a v1 editable file passed
via ``--file`` is still verified with the original v1 rules (backward
compatible), and a hint to upgrade to the v2 file is printed.

For a v2 document the freeze conditions additionally include the v2 semantic
completeness: every sentence reviewed under the v2 rules (all legacy six
blocks decided and — for structured sentences — every rule_item block
decided), no validation error, and the import confirmation event valid.

This verifier NEVER creates Gold and NEVER writes the editable file: the only
file it may create is the optional ``--report-json`` report.  ``frozen=false``
exits 1.  Zero LLM/API/network.
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
    DEFAULT_EDITABLE_V2_PATH,
    SCHEMA_EDITABLE,
    SCHEMA_EDITABLE_V2,
    audit_filled_document,
    audit_filled_document_v2,
    collect_stats,
    collect_stats_v2,
    doc_json_bytes,
    load_json,
    sha256_file,
    validate_confirmation_event,
)


def _schema_version(doc: Any) -> Any:
    return doc.get("schema_version") if isinstance(doc, dict) else None


def _confirmation_reasons(confirmation_doc: Any,
                          source_file_sha256: Optional[str],
                          blank_file_sha256: Optional[str]) -> list[str]:
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
    return conf_problems


def check_frozen_v2(file_doc: dict[str, Any],
                    blank_doc: dict[str, Any],
                    confirmation_doc: Any,
                    source_file_sha256: Optional[str] = None,
                    blank_file_sha256: Optional[str] = None) -> dict[str, Any]:
    """Pure v2 freeze-closure check (schema 1.1.0).

    Returns ``{"frozen": bool, "reasons": [...], "counts": {...},
    "stats": {...}, "warnings": [...], "confirmation_problems": [...]}``.
    ``frozen`` is true only when there are no reasons.
    """
    reasons: list[str] = []
    audit = audit_filled_document_v2(file_doc, blank_doc, require_blank=True)
    stats = collect_stats_v2(file_doc)
    for msg in audit["errors"]:
        reasons.append(msg)

    if stats["reviewed"] != stats["sentences_total"]:
        reasons.append(
            f"reviewed {stats['reviewed']} != sentences_total "
            f"{stats['sentences_total']}"
        )
    if stats["items_total"] * 6 != stats["item_blocks_decided"]:
        reasons.append(
            f"items 六块未全决: item_blocks_decided "
            f"{stats['item_blocks_decided']} != items*6 "
            f"{stats['items_total'] * 6}"
        )
    if stats["sentences_total"] == 0:
        reasons.append("document contains no sentences")

    conf_problems = _confirmation_reasons(
        confirmation_doc, source_file_sha256, blank_file_sha256)
    if conf_problems:
        reasons.append("confirmation: " + "; ".join(conf_problems))

    counts = {
        "sentences_total": stats["sentences_total"],
        "reviewed": stats["reviewed"],
        "unreviewed": stats["unreviewed"],
        "decisions_total": stats["decisions_total"],
        "fields_total": stats["fields_total"],
        "items_total": stats["items_total"],
        "item_blocks_decided": stats["item_blocks_decided"],
        "actor_action_map_total": stats["actor_action_map_total"],
        "order_relations_total": stats["order_relations_total"],
    }
    return {
        "frozen": not reasons,
        "reasons": reasons,
        "counts": counts,
        "stats": stats,
        "warnings": audit["warnings"],
        "confirmation_problems": conf_problems,
    }


def check_frozen_v1(file_doc: dict[str, Any],
                    blank_doc: dict[str, Any],
                    confirmation_doc: Any,
                    source_file_sha256: Optional[str] = None,
                    blank_file_sha256: Optional[str] = None) -> dict[str, Any]:
    """Original v1 freeze-closure check (backward compatible)."""
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

    conf_problems = _confirmation_reasons(
        confirmation_doc, source_file_sha256, blank_file_sha256)
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


def check_frozen(file_doc: dict[str, Any],
                 blank_doc: dict[str, Any],
                 confirmation_doc: Any,
                 source_file_sha256: Optional[str] = None,
                 blank_file_sha256: Optional[str] = None) -> dict[str, Any]:
    """Dispatch by the editable schema version (v1 rules for 1.0.0, v2 for
    1.1.0)."""
    if _schema_version(file_doc) == SCHEMA_EDITABLE_V2:
        return check_frozen_v2(file_doc, blank_doc, confirmation_doc,
                               source_file_sha256, blank_file_sha256)
    return check_frozen_v1(file_doc, blank_doc, confirmation_doc,
                           source_file_sha256, blank_file_sha256)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_EDITABLE_V2_PATH,
                        help="filled editable document to verify "
                             "(default: v2 decisions file)")
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

    if _schema_version(file_doc) == SCHEMA_EDITABLE:
        print("提示: 当前文件为 v1 schema（gdpr7_six_element_review_editable@"
              "1.0.0），按 v1 规则校验；建议升级到 v2 文件后校验。")

    for msg in result["reasons"]:
        print(f"  REASON: {msg}")
    for msg in result["warnings"]:
        print(f"  WARN  : {msg}")
    counts = result["counts"]
    extra = ""
    if "items_total" in counts:
        extra = (f" | items={counts['items_total']} "
                 f"item_blocks_decided={counts['item_blocks_decided']} "
                 f"aam={counts['actor_action_map_total']} "
                 f"orders={counts['order_relations_total']}")
    print(
        f"frozen={result['frozen']} | reviewed={counts['reviewed']}/"
        f"{counts['sentences_total']} | "
        f"decisions={counts['decisions_total']}/{counts['fields_total']}"
        f"{extra} | reasons={len(result['reasons'])}"
    )

    if args.report_json is not None:
        report = {
            "schema_version": "gdpr7_review_freeze_report@1.0.0",
            "editable_schema_version": file_doc.get("schema_version"),
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

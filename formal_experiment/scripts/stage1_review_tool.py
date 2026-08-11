# -*- coding: utf-8 -*-
"""Stage 1 human Process Gold review tool (non-destructive, zero-API).

Operates ONLY on the user-editable correction file
(data/development/human_review/stage1_gdpr7_human_correction_v1.json).
The immutable blank template is never touched. Decisions are NEVER inferred:
the tool only displays candidates, imports decisions the user explicitly
provided, saves atomically with backups, and validates.

Commands:
    list                          print a paged summary of all 7 records
    show <process_id>             print one record with all label fields
    export <out.json>             export the current correction file
    import <decisions.json>       import user-provided decisions (atomic save)
    backup                        create a timestamped backup copy
    validate                      run validate_editable_annotation_pack
    undo                          restore the previous backup (if any)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")
BACKUP_DIR = (ROOT / "outputs" / "development" / "human_review"
              / "stage1_review_backups")

REVIEW_STATES = ("unreviewed", "reviewed", "adjudicated")
FIELD_STATES = ("unreviewed", "present", "absent", "needs_adjudication")
STRUCTURE_STATES = ("unreviewed", "accepted_candidate", "corrected",
                    "needs_adjudication")


def _load(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot load {path}: {exc}") from exc


def _atomic_save(doc: dict[str, Any]) -> None:
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    tmp = CORRECTION.with_suffix(".tmp")
    tmp.write_bytes(data)
    CORRECTION.write_bytes(data)
    tmp.unlink(missing_ok=True)


def _backup() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = BACKUP_DIR / f"stage1_correction.backup_{stamp}.json"
    shutil.copy2(CORRECTION, dest)
    return dest


def _validate(doc: dict[str, Any]) -> dict[str, Any]:
    from bpc_hybrid.stage1_formal_dataset import validate_editable_annotation_pack
    result = validate_editable_annotation_pack(CORRECTION, doc)
    return result


def _cmd_list(doc: dict[str, Any]) -> None:
    summary = doc.get("review_summary", {})
    print(f"schema: {doc.get('schema_version')} | dataset: "
          f"{doc.get('dataset', {}).get('dataset_id')}")
    print(f"review_summary: {json.dumps(summary, ensure_ascii=False)}")
    for rec in doc.get("records", []):
        print(f"- {rec['process_id']}: review_state={rec['review_state']} | "
              f"structure={rec['structure_annotation']['decision']} | "
              f"label_fields={len(rec['label_annotations'])}")


def _cmd_show(doc: dict[str, Any], process_id: str) -> None:
    for rec in doc.get("records", []):
        if rec["process_id"] == process_id:
            print(json.dumps(rec, ensure_ascii=False, indent=1))
            return
    raise SystemExit(f"unknown process_id: {process_id}")


def _cmd_import(doc: dict[str, Any], decisions_path: Path) -> None:
    """Import ONLY explicit user decisions; validate state values; atomic save
    with backup. Never infers a decision."""
    decisions = _load(decisions_path)
    by_id = {r["process_id"]: r for r in doc.get("records", [])}
    applied = 0
    for entry in decisions.get("records", []):
        pid = entry.get("process_id")
        rec = by_id.get(pid)
        if rec is None:
            raise SystemExit(f"unknown process_id in decisions: {pid}")
        rs = entry.get("review_state")
        if rs is not None:
            if rs not in REVIEW_STATES:
                raise SystemExit(f"invalid review_state {rs!r}")
            rec["review_state"] = rs
        sa = entry.get("structure_annotation")
        if sa is not None:
            dec = sa.get("decision")
            if dec not in STRUCTURE_STATES:
                raise SystemExit(f"invalid structure decision {dec!r}")
            rec["structure_annotation"]["decision"] = dec
            if "gold_process_record" in sa:
                rec["structure_annotation"]["gold_process_record"] = sa[
                    "gold_process_record"]
        for la in entry.get("label_annotations", []):
            activity_id = la.get("activity_id")
            target = next((x for x in rec["label_annotations"]
                           if x["activity_id"] == activity_id), None)
            if target is None:
                raise SystemExit(f"unknown activity_id {activity_id}")
            for field in ("actor", "action", "business_object"):
                if field in la:
                    st = la[field].get("status")
                    if st not in FIELD_STATES:
                        raise SystemExit(f"invalid {field} status {st!r}")
                    target[field]["status"] = st
                    target[field]["value"] = la[field].get("value")
        applied += 1
    backup = _backup()
    _atomic_save(doc)
    print(f"imported decisions for {applied} records (backup: {backup})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("process_id")
    export = sub.add_parser("export")
    export.add_argument("out")
    imp = sub.add_parser("import")
    imp.add_argument("decisions")
    sub.add_parser("backup")
    sub.add_parser("validate")
    sub.add_parser("undo")
    args = parser.parse_args()

    doc = _load(CORRECTION)
    if args.command == "list":
        _cmd_list(doc)
    elif args.command == "show":
        _cmd_show(doc, args.process_id)
    elif args.command == "export":
        Path(args.out).write_bytes(
            (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        print(f"exported to {args.out}")
    elif args.command == "import":
        _cmd_import(doc, Path(args.decisions))
    elif args.command == "backup":
        print(f"backup: {_backup()}")
    elif args.command == "validate":
        result = _validate(doc)
        print("valid:", result.get("valid") if isinstance(result, dict)
              else result)
        print(json.dumps(result, ensure_ascii=False)[:400])
    elif args.command == "undo":
        backups = sorted(BACKUP_DIR.glob("stage1_correction.backup_*.json"))
        if not backups:
            raise SystemExit("no backup to restore")
        shutil.copy2(backups[-1], CORRECTION)
        print(f"restored {backups[-1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

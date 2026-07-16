"""Generate USER_OVERRIDE-marked copy of legacy EStG-150 review pack.

This script DOES NOT modify the source file. It produces a new JSONL that
carries an explicit per-record override banner so the user's review work can
happen without contaminating the formal Gold pipeline.

Promotion to formal Gold is blocked at three levels:
  1. File name: estg150_review_pack_user_audit_v1.jsonl (not the legacy _v1).
  2. Per-record banner: user_override_audit.promotion_blocked = true.
  3. data/gold/ writers will refuse this file via promotion_blocked check
     in scripts/validate_gold.py (added in the same change batch).

Run from the workspace root:
  python formal_experiment/scripts/build_user_override_review_pack.py

Audit: see docs/AUDIT_LOG.md for the matching record_change event.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SOURCE = FORMAL_ROOT / "data" / "development" / "human_review" / "estg150_review_pack_v1.jsonl"
TARGET = FORMAL_ROOT / "data" / "development" / "human_review" / "estg150_review_pack_user_audit_v1.jsonl"
META_LINE = {
    "_type": "meta",
    "audit_session_id": "user_audit_2026_07_12",
    "source_file": "estg150_review_pack_v1.jsonl",
    "applied_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "purpose": (
        "USER OVERRIDE 2026-07-12: user familiarization audit on legacy development pack. "
        "Results stay in this file and do NOT enter data/gold/. "
        "Route v2 re-locking will require a fresh audit on clean OCR + clean translation data."
    ),
    "promotion_blocked": True,
    "promotion_blocked_reason": (
        "Legacy OCR + legacy LLM translation + un-locked span schema + un-locked multi-clause policy. "
        "Audit results from this file are non-formal by design."
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(SOURCE))
    parser.add_argument("--target", default=str(TARGET))
    args = parser.parse_args()

    source = Path(args.source)
    target = Path(args.target)

    if not source.exists():
        print(f"ERROR: source file missing: {source}", file=sys.stderr)
        return 1

    if target.exists():
        print(f"ERROR: target already exists, refusing to overwrite: {target}", file=sys.stderr)
        return 2

    n_records = 0
    with source.open("r", encoding="utf-8") as src, target.open("w", encoding="utf-8") as dst:
        dst.write(json.dumps(META_LINE, ensure_ascii=False, sort_keys=True) + "\n")
        for line in src:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            record["user_override_audit"] = {
                "applied_at_utc": META_LINE["applied_at_utc"],
                "applied_by": "user_with_ai_assistance",
                "session_id": META_LINE["audit_session_id"],
                "purpose": "familiarization and workflow rehearsal; NOT formal Gold",
                "promotion_blocked": True,
                "result_disposition": "stays in this file; never enters data/gold/",
            }
            dst.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            n_records += 1

    print(f"Override copy written: {target}")
    print(f"Records copied: {n_records}")
    print("Promotion to formal Gold is blocked at file name, banner, and validator level.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

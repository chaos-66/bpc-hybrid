# -*- coding: utf-8 -*-
"""S2.11 canonical review tool v2 (Checkpoint E1/E2).

Operates on the CANONICAL v2 decisions file
(data/development/human_review/s2_11_review_decisions_v2.json):

  --list        sample ids + review states + unresolved field counts
  --progress    summary counts
  --verify      full canonical + freeze-validator structure check
  --show <id>   one sample: state + field statuses + span coordinates
                (raw text loaded hash-verified read-only; not committed)

Final adjudication stays USER-ONLY: this tool only reports and verifies;
decisions are written by the batch importer v2 --apply path (which
requires the user confirmation event) or by user edits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s2_11_canonical_v2 import ALL_FIELDS, validate  # noqa: E402
import verify_s2_11_review_freeze_v2 as freeze_v2  # noqa: E402

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_decisions() -> dict[str, Any]:
    return _load_json(ROOT / DECISIONS_V2_REL)


def unresolved_count(entry: dict[str, Any]) -> int:
    count = 0
    for clause in (entry.get("canonical") or {}).get("clauses") or []:
        if (clause.get("modality") or {}).get("status") == "unresolved":
            count += 1
        for field in ALL_FIELDS[1:]:
            if (clause.get(field) or {}).get("status") == "unresolved":
                count += 1
    return count


def progress(doc: dict[str, Any]) -> dict[str, int]:
    counts = {"unreviewed": 0, "reviewed": 0, "adjudicated": 0}
    for entry in doc["records"].values():
        state = (entry.get("review_metadata") or {}).get("review_state",
                                                         "unreviewed")
        counts[state] = counts.get(state, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--show", metavar="SAMPLE_ID")
    args = parser.parse_args()
    try:
        if args.verify:
            result = freeze_v2.verify()
            print(json.dumps({"valid": result["verified"],
                              "frozen": result["frozen"],
                              "progress": result["progress"],
                              "problems": result["problems"]},
                             ensure_ascii=False, indent=2))
            return 0 if result["verified"] else 1
        doc = load_decisions()
        if args.list:
            for sid in sorted(doc["records"]):
                entry = doc["records"][sid]
                state = (entry.get("review_metadata") or {}).get(
                    "review_state")
                print(sid, state, "unresolved=" +
                      str(unresolved_count(entry)))
            return 0
        if args.progress:
            print(json.dumps(progress(doc)))
            return 0
        if args.show:
            sid = args.show
            if sid not in doc["records"]:
                print(f"error: unknown sample {sid!r}", file=sys.stderr)
                return 1
            membership = _load_json(ROOT / MEMBERSHIP_REL)
            rec = membership["records"][sid]
            src = ROOT.parent / rec["path"]
            raw = src.read_bytes()
            if hashlib.sha256(raw).hexdigest() != rec["file_sha256"]:
                print(f"error: source hash drift for {sid}",
                      file=sys.stderr)
                return 1
            print(f"=== {sid} ===")
            print("review_metadata:",
                  json.dumps(doc["records"][sid]["review_metadata"],
                             ensure_ascii=False))
            print("canonical:",
                  json.dumps(doc["records"][sid]["canonical"],
                             ensure_ascii=False, indent=1))
            return 0
        parser.print_help()
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

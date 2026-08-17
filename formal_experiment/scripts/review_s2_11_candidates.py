# -*- coding: utf-8 -*-
"""S2.11 candidate review tool (Checkpoint B, G5 applied).

The artifact license is UNKNOWN: this tool NEVER copies raw third-party
text into the decisions file. It loads the raw requirement text READ-ONLY
from references/ via the membership manifest and REFUSES on any hash
mismatch. Final Gold decisions are USER-ONLY: the tool records exactly
what the user types; the agent never fabricates decisions.

Subcommands:
  --list                 list sample ids + review states
  --next                 show the first unreviewed sample (text + candidate)
  --show <sample_id>     show one sample (text + candidate + decisions)
  --set <sample_id> <field> <value>
                         record one user decision (field in
                         modality/actor/action/condition/constraint/exception)
  --state <sample_id> <unreviewed|reviewed|adjudicated>
                         set the review state
  --reviewer <sample_id> <name>
                         set the reviewer (user) for one sample
  --undo <sample_id> <field>
                         reset one decision field to null
  --progress             summary counts
  --backup               copy the decisions file to a timestamped backup
  --verify               structural validation (used by tests)

The decisions file is written atomically; a backup is kept before each
write. Resume = re-run any command; state is read from the decisions file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
BLANK_REVIEW_REL = "data/development/human_review/s2_11_blank_review_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")
STATES = ("unreviewed", "reviewed", "adjudicated")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_text(sample_id: str) -> tuple[str, str]:
    """Load the raw requirement text for one sample from references
    (read-only), verifying the file hash AND the per-record text hash.
    Returns (text, text_sha256); raises on any mismatch."""
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    rec = membership["records"].get(sample_id)
    if rec is None:
        raise ValueError(f"sample {sample_id!r} not in the membership")
    file_path = ROOT.parent / rec["path"]
    raw = file_path.read_bytes()
    if _sha256_bytes(raw) != rec["file_sha256"]:
        raise ValueError(
            f"source file hash mismatch for {sample_id!r}: refusing to "
            "display")
    scenario, rid, version = sample_id.split("/")
    version = version[1:]
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and str(entry.get("version")) == version:
            text = str(entry.get("text", ""))
            if _sha256_bytes(text.encode("utf-8")) != rec["text_sha256"]:
                raise ValueError(
                    f"record text hash mismatch for {sample_id!r}: "
                    "refusing to display")
            return text, rec["text_sha256"]
    raise ValueError(f"record {sample_id!r} not found in its source file")


def load_decisions() -> dict[str, Any]:
    return _load_json(ROOT / DECISIONS_REL)


def load_blank_candidate(sample_id: str) -> dict[str, Any]:
    """Candidate review-aid info from the blank pack (modality + level +
    candidate_status; unavailable items carry the stable error code)."""
    pack = _load_json(ROOT / BLANK_REVIEW_REL)
    for sample in pack.get("samples", []):
        if sample.get("sample_id") == sample_id:
            info: dict[str, Any] = {}
            if sample.get("candidate") is not None:
                info.update(dict(sample["candidate"]))
            info["candidate_status"] = sample.get("candidate_status")
            if sample.get("candidate_error") is not None:
                info["candidate_error"] = sample["candidate_error"]
            return info
    return {}


def write_decisions(doc: dict[str, Any]) -> None:
    backup = ROOT / (DECISIONS_REL + ".bak")
    shutil.copy2(ROOT / DECISIONS_REL, backup)
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    tmp = ROOT / (DECISIONS_REL + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(ROOT / DECISIONS_REL)


def verify_decisions(doc: dict[str, Any]) -> list[str]:
    """Structural validation of the decisions file. Returns a list of
    problems (empty == valid)."""
    problems: list[str] = []
    records = doc.get("records") or {}
    if not isinstance(records, dict) or not records:
        problems.append("decisions file has no records")
        return problems
    for sample_id, entry in sorted(records.items()):
        if not isinstance(entry, dict):
            problems.append(f"{sample_id}: malformed entry")
            continue
        state = entry.get("review_state")
        if state not in STATES:
            problems.append(f"{sample_id}: bad review_state {state!r}")
        decision = entry.get("decision")
        if not isinstance(decision, dict):
            problems.append(f"{sample_id}: no decision object")
            continue
        for field in DECISION_FIELDS:
            if field not in decision:
                problems.append(f"{sample_id}: missing decision field "
                                f"{field!r}")
        if state == "adjudicated":
            missing = [f for f in DECISION_FIELDS
                       if decision.get(f) is None]
            if missing:
                problems.append(
                    f"{sample_id}: adjudicated with null fields {missing}")
            if not entry.get("reviewer"):
                problems.append(f"{sample_id}: adjudicated without reviewer")
    return problems


def progress(doc: dict[str, Any]) -> dict[str, int]:
    records = doc.get("records") or {}
    counts = {s: 0 for s in STATES}
    for entry in records.values():
        counts[entry.get("review_state", "unreviewed")] = \
            counts.get(entry.get("review_state", "unreviewed"), 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--show", metavar="SAMPLE_ID")
    parser.add_argument("--set", nargs=3,
                        metavar=("SAMPLE_ID", "FIELD", "VALUE"))
    parser.add_argument("--state", nargs=2,
                        metavar=("SAMPLE_ID", "STATE"))
    parser.add_argument("--reviewer", nargs=2,
                        metavar=("SAMPLE_ID", "NAME"))
    parser.add_argument("--undo", nargs=2,
                        metavar=("SAMPLE_ID", "FIELD"))
    parser.add_argument("--progress", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()

    try:
        if args.verify:
            doc = load_decisions()
            problems = verify_decisions(doc)
            counts = progress(doc)
            print(json.dumps({"valid": not problems, "problems": problems,
                              "progress": counts,
                              "gold_files_created": False},
                             ensure_ascii=False, indent=2))
            return 0 if not problems else 1

        if args.backup:
            backup = ROOT / (DECISIONS_REL + f".bak-{hashlib.sha256(
                (ROOT / DECISIONS_REL).read_bytes()).hexdigest()[:8]}")
            shutil.copy2(ROOT / DECISIONS_REL, backup)
            print(f"backup written: {backup}")
            return 0

        doc = load_decisions()
        records = doc["records"]

        if args.list:
            for sid in sorted(records):
                print(sid, records[sid]["review_state"])
            return 0

        if args.progress:
            counts = progress(doc)
            print(json.dumps(counts))
            print("total:", sum(counts.values()))
            return 0

        if args.next:
            for sid in sorted(records):
                if records[sid]["review_state"] == "unreviewed":
                    text, _ = load_source_text(sid)
                    cand = load_blank_candidate(sid)
                    print(f"=== {sid} ===")
                    print(text)
                    print("candidate (review aid only):", json.dumps(
                        cand, ensure_ascii=False))
                    return 0
            print("no unreviewed samples remain")
            return 0

        if args.show:
            text, sha = load_source_text(args.show)
            print(f"=== {args.show} ===")
            print(f"text_sha256: {sha}")
            print(text)
            print("candidate (review aid only):", json.dumps(
                load_blank_candidate(args.show), ensure_ascii=False))
            print("decisions:", json.dumps(
                records.get(args.show, {}), ensure_ascii=False))
            return 0

        if args.set:
            sid, field, value = args.set
            if sid not in records:
                print(f"error: unknown sample {sid!r}", file=sys.stderr)
                return 1
            if field not in DECISION_FIELDS:
                print(f"error: unknown field {field!r}", file=sys.stderr)
                return 1
            if field == "modality" and value not in (
                    "obligation", "permission", "prohibition", "definition"):
                print("error: modality must be one of obligation/"
                      "permission/prohibition/definition", file=sys.stderr)
                return 1
            records[sid]["decision"][field] = value
            if records[sid]["review_state"] == "unreviewed":
                records[sid]["review_state"] = "reviewed"
            write_decisions(doc)
            print(f"recorded decision: {sid} {field}={value!r}")
            return 0

        if args.state:
            sid, state = args.state
            if sid not in records:
                print(f"error: unknown sample {sid!r}", file=sys.stderr)
                return 1
            if state not in STATES:
                print(f"error: state must be one of {STATES}",
                      file=sys.stderr)
                return 1
            records[sid]["review_state"] = state
            write_decisions(doc)
            print(f"state set: {sid} -> {state}")
            return 0

        if args.reviewer:
            sid, name = args.reviewer
            if sid not in records:
                print(f"error: unknown sample {sid!r}", file=sys.stderr)
                return 1
            if not name.strip():
                print("error: reviewer name must be non-empty",
                      file=sys.stderr)
                return 1
            records[sid]["reviewer"] = name
            write_decisions(doc)
            print(f"reviewer set: {sid} -> {name!r}")
            return 0

        if args.undo:
            sid, field = args.undo
            if sid not in records or field not in DECISION_FIELDS:
                print("error: unknown sample or field", file=sys.stderr)
                return 1
            records[sid]["decision"][field] = None
            write_decisions(doc)
            print(f"undone: {sid} {field} -> null")
            return 0

        parser.print_help()
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""S2.11 review FREEZE validator (Checkpoint B).

Verifies the review-decisions file structure and reports progress. The
formal Gold Rule Record freeze requires the USER to adjudicate every
sample; this validator NEVER creates Gold and NEVER fabricates decisions.
It exits 0 when the decisions file is structurally valid and progress is
reported (frozen=false until the user completes adjudication); any
structural violation exits 1.

Also importable:
    from scripts.verify_s2_11_review_freeze import verify
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"
BLANK_REVIEW_REL = "data/development/human_review/s2_11_blank_review_v1.json"
DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify() -> dict[str, Any]:
    pack = _load_json(ROOT / BLANK_REVIEW_REL)
    expected_ids = [s["sample_id"] for s in pack.get("samples", [])]
    doc = _load_json(ROOT / DECISIONS_REL)
    records = doc.get("records") or {}
    problems: list[str] = []
    counts = {"unreviewed": 0, "reviewed": 0, "adjudicated": 0}

    # population invariants: review_population == nonempty_membership and
    # the decisions sample set matches the blank pack EXACTLY (missing,
    # duplicate or extra sample IDs refuse)
    pop = pack.get("population") or {}
    if pop.get("review_population") != pop.get("nonempty_membership"):
        problems.append("review_population != nonempty_membership")
    if pop.get("review_population") != len(expected_ids):
        problems.append("review_population != sample count in the pack")
    expected_set = set(expected_ids)
    actual_set = set(records)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    if missing:
        problems.append(f"missing sample ids: {missing}")
    if extra:
        problems.append(f"extra sample ids: {extra}")

    for sample_id in expected_ids:
        entry = records.get(sample_id)
        if not isinstance(entry, dict):
            problems.append(f"{sample_id}: missing decision entry")
            continue
        state = entry.get("review_state")
        if state not in counts:
            problems.append(f"{sample_id}: bad review_state {state!r}")
            continue
        counts[state] += 1
        decision = entry.get("decision") or {}
        for field in DECISION_FIELDS:
            if field not in decision:
                problems.append(f"{sample_id}: missing field {field!r}")
        if state == "adjudicated":
            missing_fields = [f for f in DECISION_FIELDS
                              if decision.get(f) is None]
            if missing_fields:
                problems.append(
                    f"{sample_id}: adjudicated with null fields "
                    f"{missing_fields}")
            if not entry.get("reviewer"):
                problems.append(f"{sample_id}: adjudicated without reviewer")
    total = len(expected_ids)
    frozen = bool(total and counts["adjudicated"] == total
                  and not problems)
    return {
        "verified": not problems,
        "frozen": frozen,
        "progress": counts,
        "total": total,
        "remaining_for_user": total - counts["adjudicated"],
        "gold_rule_records_created": False,
        "gold_creation_requires_user_authorization": True,
        "problems": problems,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("S2.11 review freeze validator")
        print(f"progress: {result['progress']}")
        print(f"remaining_for_user: {result['remaining_for_user']}")
        print(f"frozen: {result['frozen']}")
        print(f"gold_rule_records_created: "
              f"{result['gold_rule_records_created']}")
        for p in result["problems"]:
            print("PROBLEM:", p)
        print("S2.11 REVIEW FREEZE " +
              ("VALID" if result["verified"] else "NOT VALID"))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

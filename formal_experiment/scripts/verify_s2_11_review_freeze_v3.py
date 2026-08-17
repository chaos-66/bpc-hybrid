# -*- coding: utf-8 -*-
"""S2.11 review FREEZE validator v2 (Checkpoint E1/E2).

Validates the CANONICAL v2 decisions file
(data/development/human_review/s2_11_review_decisions_v2.json) against the
v2 blank pack and the canonical v3 model (Checkpoint F: unique span/clause ids, actor-action mapping coverage, order relations, list-based span collection):

  * review population closure 40/4/36 and exact sample set (missing /
    duplicate / extra ids refuse)
  * per record: review_metadata.review_state in
    {unreviewed, reviewed, adjudicated}; canonical payload validated with
    the canonical v2 validator (slice equality against the hash-bound
    source, span-id uniqueness, actor_action_map / order_relations refs,
    modality label vocabulary, evidence non-empty for present modality)
  * adjudicated records must have ZERO unresolved fields (absent is legal)
    and must carry reviewer + confirmation_event (the reviewer can only
    come from the user confirmation event via the batch importer --apply)
  * frozen = 36/36 adjudicated AND no unresolved AND no structural problems

This validator NEVER creates Gold and NEVER fabricates decisions. Exit 0
only when the structure is valid; any violation exits 1 (fail-closed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent  # references/ live next to formal_experiment
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s2_11_canonical_v3 import (  # noqa: E402
    ALL_FIELDS,
    validate,
)

DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
BLANK_REVIEW_V2_REL = "data/development/human_review/s2_11_blank_review_v2.json"
MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
STATES = ("unreviewed", "reviewed", "adjudicated")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_source_text(sample_id: str, rec: dict[str, Any]) -> str:
    src = PROJECT_ROOT / rec["path"]
    raw = src.read_bytes()
    if hashlib.sha256(raw).hexdigest() != rec["file_sha256"]:
        raise ValueError(f"source file hash drift for {sample_id}")
    scenario, rid, version = sample_id.split("/")
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and \
                str(entry.get("version")) == version.lstrip("v"):
            text = str(entry.get("text", ""))
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != \
                    rec["text_sha256"]:
                raise ValueError(f"text hash drift for {sample_id}")
            return text
    raise ValueError(f"record {sample_id} not found in source")


def _unresolved_fields(record: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for ci, clause in enumerate((record.get("canonical") or {})
                                .get("clauses") or []):
        prefix = f"c{ci + 1}"
        mod = clause.get("modality") or {}
        if mod.get("status") == "unresolved":
            out.append(f"{prefix}.modality")
        for field in ALL_FIELDS[1:]:
            entry = clause.get(field) or {}
            if entry.get("status") == "unresolved":
                out.append(f"{prefix}.{field}")
    return out


def verify() -> dict[str, Any]:
    pack = _load_json(ROOT / BLANK_REVIEW_V2_REL)
    expected_ids = [s["sample_id"] for s in pack.get("samples", [])]
    doc = _load_json(ROOT / DECISIONS_V2_REL)
    records = doc.get("records") or {}
    problems: list[str] = []
    counts = {"unreviewed": 0, "reviewed": 0, "adjudicated": 0}

    pop = pack.get("population") or {}
    if pop.get("review_population") != pop.get("nonempty_membership") or \
            pop.get("review_population") != len(expected_ids):
        problems.append("v2 pack population closure violated")
    if len(expected_ids) != 36:
        problems.append(f"v2 pack must have 36 samples, got "
                        f"{len(expected_ids)}")
    expected_set = set(expected_ids)
    actual_set = set(records)
    if sorted(expected_set - actual_set):
        problems.append("missing sample ids: " +
                        str(sorted(expected_set - actual_set)))
    if sorted(actual_set - expected_set):
        problems.append("extra sample ids: " +
                        str(sorted(actual_set - expected_set)))

    membership = _load_json(ROOT / MEMBERSHIP_REL)
    source_texts: dict[str, str] = {}
    for sample_id in expected_ids:
        try:
            source_texts[sample_id] = _load_source_text(
                sample_id, membership["records"][sample_id])
        except (ValueError, KeyError) as exc:
            problems.append(f"{sample_id}: {exc}")
            source_texts[sample_id] = ""

    for sample_id in expected_ids:
        entry = records.get(sample_id)
        if not isinstance(entry, dict):
            problems.append(f"{sample_id}: missing decision entry")
            continue
        meta = entry.get("review_metadata") or {}
        state = meta.get("review_state")
        if state not in STATES:
            problems.append(f"{sample_id}: bad review_state {state!r}")
            continue
        counts[state] += 1
        canonical = entry.get("canonical")
        if not isinstance(canonical, dict):
            problems.append(f"{sample_id}: no canonical payload")
            continue
        vres = validate(
            {sample_id: {"canonical": canonical}},
            {sample_id: source_texts.get(sample_id, "")},
            allow_unresolved=True)
        for p in vres["problems"]:
            problems.append(f"{sample_id}: {p}")
        if state == "adjudicated":
            unresolved = _unresolved_fields(entry)
            if unresolved:
                problems.append(f"{sample_id}: adjudicated with unresolved "
                                f"fields {unresolved}")
            if not (meta.get("reviewer") or "").strip():
                problems.append(f"{sample_id}: adjudicated without reviewer")
            if not meta.get("confirmation_event"):
                problems.append(
                    f"{sample_id}: adjudicated without confirmation_event "
                    "(reviewer must come from the user confirmation event)")

    total = len(expected_ids)
    frozen = bool(total and counts["adjudicated"] == total
                  and not problems)
    checks = [
        {"name": "population closure 40/4/36", "ok": bool(
            pop.get("review_population") == pop.get("nonempty_membership")
            == 36 and len(expected_ids) == 36)},
        {"name": "exact sample set (missing/extra ids)", "ok": bool(
            not sorted(expected_set - actual_set)
            and not sorted(actual_set - expected_set))},
        {"name": "canonical v3 payload validity", "ok": bool(
            not [p for p in problems if "slice" in p or
                 "duplicate span id" in p or "duplicate clause id" in p or
                 "actor_action_map" in p or "order_relations" in p])},
        {"name": "review states valid", "ok": bool(
            all(records.get(sid, {}).get("review_metadata", {}).get(
                "review_state") in STATES for sid in expected_ids) and
            counts["unreviewed"] + counts["reviewed"] +
            counts["adjudicated"] == total)},
        {"name": "adjudicated records have zero unresolved fields",
         "ok": not any("unresolved fields" in p for p in problems)},
        {"name": "adjudicated records carry reviewer + confirmation event",
         "ok": not any("without reviewer" in p or
                       "without confirmation_event" in p
                       for p in problems)},
        {"name": "frozen flag consistent", "ok": bool(
            frozen == (total and counts["adjudicated"] == total
                       and not problems))},
    ]
    return {
        "verified": not problems,
        "frozen": frozen,
        "progress": counts,
        "total": total,
        "remaining_for_user": total - counts["adjudicated"],
        "gold_rule_records_created": False,
        "gold_creation_requires_user_authorization": True,
        "problems": problems,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("S2.11 review freeze validator v3")
        print(f"progress: {result['progress']}")
        print(f"remaining_for_user: {result['remaining_for_user']}")
        print(f"frozen: {result['frozen']}")
        print(f"gold_rule_records_created: "
              f"{result['gold_rule_records_created']}")
        for p in result["problems"]:
            print("PROBLEM:", p)
        print("S2.11 REVIEW FREEZE V3 " +
              ("VALID" if result["verified"] else "NOT VALID"))
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

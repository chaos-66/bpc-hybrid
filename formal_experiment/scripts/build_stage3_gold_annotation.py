# -*- coding: utf-8 -*-
"""Build the Stage 3 Gold annotation blank pack (S3.2 matching + S3.3 violation).

The pack contains ONLY candidates. Every matching pair and every violation
item starts in ``review_state=unreviewed``; only the user may mark items
reviewed/adjudicated. No decision is inferred, no Gold is auto-filled, and
no BPMN is modified. The pack is deterministic: same inputs -> byte-identical
output (no timestamps, fixed ordering).

Inputs (both frozen):
- S3.1 membership contract ``configs/datasets/stage1_stage3_gdpr7_v1.json``
  (process identities) and its Process Records (activity names), and
- the Winter/agostinelli GDPR regulation texts under
  ``references/winter_2020_model_check/.../regulations/gdpr/`` (read-only),
  which the official Sun supplement hash-matches (57 effective Stage 3 files).

The candidate rule-process mapping below is GDPR-domain knowledge offered as
candidates for human adjudication; it is NOT Gold and must not be reported as
formal matching/violation Gold until the user freezes the pack.

Usage:
    python scripts/build_stage3_gold_annotation.py
    python scripts/build_stage3_gold_annotation.py --write
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

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    Stage1FormalDatasetError,
    build_formal_process_records,
    load_formal_membership_contract,
)

MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
DEFAULT_OUTPUT = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
REGULATION_DIR = (
    ROOT.parent
    / "references"
    / "winter_2020_model_check"
    / "model_check"
    / "input"
    / "regulations"
    / "gdpr"
)

RULE_REF = {
    "article6": "Article 6 - Lawfulness of processing",
    "article7": "Article 7 - Conditions for consent",
    "article15": "Article 15 - Right of access by the data subject",
    "article16": "Article 16 - Right to rectification",
    "article17": "Article 17 - Right to erasure ('right to be forgotten')",
    "article20": "Article 20 - Right to data portability",
    "article22": "Article 22 - Automated individual decision-making, including profiling",
    "article33": "Article 33 - Notification of a personal data breach to the supervisory authority",
    "article34": "Article 34 - Communication of a personal data breach to the data subject",
}

# Candidate rule-process relevance map (GDPR domain knowledge; candidates
# only, human-adjudicated). ``relevant`` rules are the primary obligations
# each BPMN process is expected to implement; ``negative`` rules are used to
# form irrelevant pairs so the matching Gold also covers negatives.
CANDIDATE_MATCHING = {
    "gdpr_1_data_breach": {"relevant": ["article33", "article34"], "negative": ["article15", "article17"]},
    "gdpr_2_consent_to_use_the_data": {"relevant": ["article7", "article6", "article22"], "negative": ["article33", "article34"]},
    "gdpr_3_right_to_access": {"relevant": ["article15"], "negative": ["article7", "article20"]},
    "gdpr_4_right_of_portability": {"relevant": ["article20"], "negative": ["article15", "article17"]},
    "gdpr_5_right_to_withdraw": {"relevant": ["article7", "article17"], "negative": ["article15", "article33"]},
    "gdpr_6_right_to_rectify": {"relevant": ["article16"], "negative": ["article15", "article20"]},
    "gdpr_7_right_to_be_forgotten": {"relevant": ["article17"], "negative": ["article15", "article33"]},
}

# Candidate violation injection points per (process, rule): one candidate of
# each violation type per relevant pair. evidence cites the expected duty;
# location names the BPMN activity the check targets (null when the duty has
# no direct activity counterpart).
CANDIDATE_VIOLATIONS: dict[str, dict[str, list[dict[str, str | None]]]] = {
    "gdpr_1_data_breach": {
        "article33": [
            {"type": "missing_action", "location": "Notify national authority",
             "evidence": "Art 33(1) obliges the controller to notify the supervisory authority without undue delay after becoming aware of a breach; candidate: is the notification activity present after breach detection?"},
            {"type": "incorrect_actor", "location": "Notify national authority",
             "evidence": "Art 33(1) assigns notification to the controller; candidate: is the notification performed by the controller lane and not by an external party?"},
            {"type": "out_of_order", "location": "Handle delay",
             "evidence": "Art 33(1)/(3) requires notification not later than 72 hours; candidate: does notification precede delay-handling that could postpone it past the deadline?"},
        ],
        "article34": [
            {"type": "missing_action", "location": "Communication with data subject",
             "evidence": "Art 34(1) obliges the controller to communicate a high-risk breach to the data subject without undue delay; candidate: is that communication activity present?"},
            {"type": "incorrect_actor", "location": "Communication with data subject",
             "evidence": "Art 34(1) assigns the communication duty to the controller; candidate: is the communication executed by the correct actor?"},
            {"type": "out_of_order", "location": "Handle delay",
             "evidence": "Art 34(1) requires communication without undue delay; candidate: does communication happen before the delay branch?"},
        ],
    },
    "gdpr_2_consent_to_use_the_data": {
        "article7": [
            {"type": "missing_action", "location": 'Add "existence of the right to withdraw"',
             "evidence": "Art 7(3) requires that the data subject can withdraw consent at any time and is informed of that right before giving consent; candidate: is the withdrawal-right information present?"},
            {"type": "incorrect_actor", "location": "Collect consent information",
             "evidence": "Art 7(1) requires consent to be obtained from the data subject by the controller; candidate: is consent collected from the correct party?"},
            {"type": "out_of_order", "location": "Collect consent information",
             "evidence": "Art 7(3) requires informing about the withdrawal right before consent is given; candidate: does the information precede the consent collection?"},
        ],
        "article6": [
            {"type": "missing_action", "location": "Retrieve processing legal basis",
             "evidence": "Art 6(1) requires a lawful basis for every processing; candidate: is the legal-basis determination activity present?"},
            {"type": "incorrect_actor", "location": "Retrieve processing legal basis",
             "evidence": "Art 6(1) places the lawfulness determination on the controller; candidate: is the determination performed by the controller?"},
            {"type": "out_of_order", "location": "Collect consent information",
             "evidence": "Art 6(1)(a) ties processing to consent; candidate: does the legal-basis check follow rather than precede consent collection?"},
        ],
        "article22": [
            {"type": "missing_action", "location": 'Add "profiling about logic involved, significance and envisaged consequences of processing"',
             "evidence": "Art 22(1)/(3) requires safeguards and information for automated decision-making including profiling; candidate: is the profiling information present?"},
            {"type": "incorrect_actor", "location": 'Add "profiling about logic involved, significance and envisaged consequences of processing"',
             "evidence": "Art 22(3) requires suitable measures by the controller; candidate: is the information supplied by the controller?"},
            {"type": "out_of_order", "location": "Collect consent information",
             "evidence": "Art 22(2)(a) allows automated decisions based on explicit consent; candidate: does profiling information follow rather than precede consent?"},
        ],
    },
    "gdpr_3_right_to_access": {
        "article15": [
            {"type": "missing_action", "location": "Communicate data and elaborations",
             "evidence": "Art 15(1) obliges the controller to provide access to the data subject; candidate: is the communication activity present?"},
            {"type": "incorrect_actor", "location": "Retrieve available data of the data subject",
             "evidence": "Art 15(1) gives the right to the data subject and imposes the duty on the controller; candidate: is the retrieval/communication performed by the controller?"},
            {"type": "out_of_order", "location": "Communicate data and elaborations",
             "evidence": "Art 12(3) requires acting on a request without undue delay and at the latest within one month; candidate: does communication precede any uncontrolled delay?"},
        ],
    },
    "gdpr_4_right_of_portability": {
        "article20": [
            {"type": "missing_action", "location": "Communicate data and elaborations",
             "evidence": "Art 20(1) requires the controller to provide the data in a structured, commonly used and machine-readable format; candidate: is the provision activity present?"},
            {"type": "incorrect_actor", "location": "Retrieve available data of the data subject",
             "evidence": "Art 20(1) gives portability to the data subject; candidate: is the data handed to the data subject (not a third party by default)?"},
            {"type": "out_of_order", "location": "Communicate data and elaborations",
             "evidence": "Art 12(3) applies the without-undue-delay duty; candidate: does the transfer follow the request without delay?"},
        ],
    },
    "gdpr_5_right_to_withdraw": {
        "article7": [
            {"type": "missing_action", "location": "Communicate the withdraw",
             "evidence": "Art 7(3) requires that withdrawal is as easy as giving consent; candidate: is a withdrawal-communication activity present?"},
            {"type": "incorrect_actor", "location": "Stop using withdrawn data",
             "evidence": "Art 7(3) requires the controller to stop processing on withdrawal; candidate: is the stop action executed by the controller?"},
            {"type": "out_of_order", "location": "Stop running BPs using withdrawn data",
             "evidence": "Art 7(3) requires cessation without undue delay after withdrawal; candidate: does the stop precede any further processing?"},
        ],
        "article17": [
            {"type": "missing_action", "location": "Stop using withdrawn data",
             "evidence": "Art 17(1)(b) requires erasure when consent is withdrawn and no other legal basis applies; candidate: is an erasure/stop activity present?"},
            {"type": "incorrect_actor", "location": "Inform the user that the withdraw will stop all running BPs",
             "evidence": "Art 17(1) duties rest with the controller; candidate: is the erasure executed by the controller?"},
            {"type": "out_of_order", "location": "Stop running BPs using withdrawn data",
             "evidence": "Art 17(1) requires erasure without undue delay; candidate: does the stop precede rather than follow continued processing?"},
        ],
    },
    "gdpr_6_right_to_rectify": {
        "article16": [
            {"type": "missing_action", "location": "Rectify data",
             "evidence": "Art 16 requires the controller to rectify inaccurate personal data without undue delay; candidate: is the rectification activity present?"},
            {"type": "incorrect_actor", "location": "Rectify data",
             "evidence": "Art 16 assigns the rectification duty to the controller; candidate: is the rectification performed by the controller?"},
            {"type": "out_of_order", "location": "Communicate the rectification",
             "evidence": "Art 16 with Art 12(3) requires acting without undue delay and communicating the rectification; candidate: does communication follow the rectification promptly?"},
        ],
    },
    "gdpr_7_right_to_be_forgotten": {
        "article17": [
            {"type": "missing_action", "location": "Retrieve data",
             "evidence": "Art 17(1) requires the controller to erase personal data without undue delay; candidate: is an erasure activity present?"},
            {"type": "incorrect_actor", "location": "Retrieve data",
             "evidence": "Art 17(1) imposes the erasure duty on the controller; candidate: is the erasure executed by the controller?"},
            {"type": "out_of_order", "location": "Communication with data subject",
             "evidence": "Art 17(1) requires erasure without undue delay and Art 19 requires informing about erasure; candidate: does erasure precede communication?"},
        ],
    },
}

CLAIM_BOUNDARY = (
    "This blank pack contains S3.2 rule-process relevance (matching) and S3.3 "
    "violation candidates for the frozen S3.1 all-seven GDPR BPMN extension and "
    "the Winter/agostinelli GDPR regulation texts. Every item is a candidate "
    "(review_state=unreviewed); only the user may adjudicate relevance, "
    "violation type/evidence, or negatives. The pack creates no Gold, modifies "
    "no BPMN, runs no matching or violation detection, and reports no Stage 3 "
    "performance. Formal matching/violation Gold requires the user's "
    "adjudication and a freeze event."
)


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1FormalDatasetError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1FormalDatasetError(f"{label} root must be an object")
    return value


def _activity_names(process_id: str, records: list[dict[str, Any]]) -> list[str]:
    for record in records:
        if record["process_id"] == process_id:
            return [a["name"].strip() for a in record["activities"] if a.get("name")]
    raise Stage1FormalDatasetError(f"missing Process Record for {process_id}")


def build_blank_pack() -> dict[str, Any]:
    contract = load_formal_membership_contract(MEMBERSHIP_CONTRACT)
    records = build_formal_process_records(contract)
    process_ids = [item["input_id"] for item in contract["membership"]["files"]]
    unknown = [pid for pid in CANDIDATE_MATCHING if pid not in process_ids]
    if unknown:
        raise Stage1FormalDatasetError(f"candidate map references unknown process: {unknown}")

    processes = []
    for process_id in process_ids:
        processes.append(
            {
                "process_id": process_id,
                "source_path": f"data/input/stage1_stage3/gdpr7/{process_id}.bpmn",
                "activity_names": _activity_names(process_id, records),
            }
        )

    matching_items = []
    violation_items = []
    m_seq = 0
    v_seq = 0
    for process_id in process_ids:
        activities = {pid: _activity_names(pid, records) for pid in process_ids}[process_id]
        candidates = CANDIDATE_MATCHING[process_id]
        # matching: relevant pairs first, then negative pairs (fixed order)
        for rule_id in candidates["relevant"] + candidates["negative"]:
            is_relevant = rule_id in candidates["relevant"]
            m_seq += 1
            evidence_activity = None
            if is_relevant:
                for viol in CANDIDATE_VIOLATIONS[process_id].get(rule_id, []):
                    loc = viol["location"]
                    if loc in activities:
                        evidence_activity = loc
                        break
            matching_items.append(
                {
                    "item_id": f"m{m_seq:03d}",
                    "process_id": process_id,
                    "rule_id": rule_id,
                    "rule_ref": RULE_REF[rule_id],
                    "candidate_relevant": is_relevant,
                    "evidence_activity": evidence_activity,
                    "review_state": "unreviewed",
                    "decision_relevant": None,
                }
            )
        # violation: one candidate of each type per relevant rule
        for rule_id in candidates["relevant"]:
            for viol in CANDIDATE_VIOLATIONS[process_id].get(rule_id, []):
                v_seq += 1
                violation_items.append(
                    {
                        "item_id": f"v{v_seq:03d}",
                        "process_id": process_id,
                        "rule_id": rule_id,
                        "candidate_violation_type": viol["type"],
                        "candidate_evidence": viol["evidence"],
                        "candidate_location": viol["location"],
                        "review_state": "unreviewed",
                        "decision_violation_type": None,
                        "decision_evidence": None,
                    }
                )

    pack = {
        "schema_version": "stage3_gold_annotation@1.0.0",
        "dataset_id": "stage3_gold_annotation_v1",
        "claim_boundary": CLAIM_BOUNDARY,
        "processes": processes,
        "matching_items": matching_items,
        "violation_items": violation_items,
    }
    return pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the blank pack (default: dry-run print)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    pack = build_blank_pack()
    payload = json.dumps(pack, ensure_ascii=False, indent=2) + "\n"
    print(
        f"stage3 gold blank pack: {len(pack['processes'])} processes, "
        f"{len(pack['matching_items'])} matching candidates, "
        f"{len(pack['violation_items'])} violation candidates"
    )
    if not args.write:
        print("dry-run (no file written); pass --write to create the blank pack")
        return 0
    output = args.output.resolve()
    if output.exists():
        print(f"refusing to overwrite: {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

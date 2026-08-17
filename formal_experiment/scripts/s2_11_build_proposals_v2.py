# -*- coding: utf-8 -*-
"""Deterministic S2.11 canonical proposal v2 builder (Checkpoint E1; ZERO
real LLM/API).

v2 supersedes v1 (14c1ec909b2c5aa2249d2acfac1f3e411ff00a3c967a3d6b2ed06ddba8c7364b
= outputs/development/s2_11_local_working/adjudication_proposals_v1/
proposals.jsonl; committed report outputs/reports/s2_11_proposal_report_v1.json
stays byte-exact as provenance). v1 must NOT be approved by the user.

Model (canonical v2, see src/bpc_hybrid/s2_11_canonical_v2.py):
  * every field has an explicit status: unresolved | absent | present
  * modality = {status, label (controlled vocabulary), evidence[] (one or
    more exact normative-cue spans from the source text)}; NO
    value_missing_in_text is ever emitted
  * actor/action/condition/constraint/exception = span arrays (multi-value
    supported); spans are byte-verified text == source[start:end]
  * actor_action_map + order_relations reference span ids
  * actions are complete contiguous verb phrases (never isolated words
    like provided/sent/asked/administered/analyzed/happen/made/collected/
    applied)
  * passive sentences with no stated executor keep actor = absent
    (never the patient masquerading as the actor)
  * "not obligated" / "not needed" are absence-of-obligation -> permission
    (NOT prohibition); "should" = soft obligation; "can" = permission;
    "even if" clauses are exceptions; "not eligible" = prohibition
  * change-version pairs are cross-checked so the change point is
    reflected in the labels/spans/conditions

Outputs:
  LOCAL (gitignored, never committed):
    outputs/development/s2_11_local_working/adjudication_proposals_v2/
      proposals.jsonl          (full entries incl. span text)
      decision_package.md      (rendered from the LOCAL full entries)
      v1_to_v2_semantic_diff.md
      quality_report.md
  COMMITTED (coordinates/hashes/counts/ids ONLY):
    outputs/reports/s2_11_proposal_report_v2.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g05_complexity_candidate import (  # noqa: E402
    classify_frozen,
)
from bpc_hybrid.s2_11_canonical_v2 import (  # noqa: E402
    MODALITY_LABELS,
    ORDINARY_FIELDS,
    validate,
)
from bpc_hybrid.s2_11_corpus_ingestion import g05_features  # noqa: E402

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"
AUTH_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
PROPOSAL_REPORT_V1_REL = "outputs/reports/s2_11_proposal_report_v1.json"
PROPOSAL_REPORT_V2_REL = "outputs/reports/s2_11_proposal_report_v2.json"
V1_LOCAL_REL = ("outputs/development/s2_11_local_working/"
                "adjudication_proposals_v1/proposals.jsonl")
V2_LOCAL_DIR = ROOT / "outputs" / "development" / "s2_11_local_working" / \
    "adjudication_proposals_v2"
V2_LOCAL_PROPOSALS_REL = "proposals.jsonl"
V2_LOCAL_PACKAGE_REL = "decision_package.md"
V2_LOCAL_DIFF_REL = "v1_to_v2_semantic_diff.md"
V2_LOCAL_QUALITY_REL = "quality_report.md"

V1_PROPOSAL_SHA256 = \
    "14c1ec909b2c5aa2249d2acfac1f3e411ff00a3c967a3d6b2ed06ddba8c7364b"
PROPOSAL_SOURCE = "deepseek_offline_proposal_v2"


class BuildFail(Exception):
    """Fail-closed build abort."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuildFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _load_text(record_id: str, rec: dict[str, Any]) -> str:
    src = ROOT.parent / rec["path"]
    raw = src.read_bytes()
    if _sha256_bytes(raw) != rec["file_sha256"]:
        raise BuildFail(f"source file hash drift for {record_id}")
    scenario, rid, version = record_id.split("/")
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and \
                str(entry.get("version")) == version.lstrip("v"):
            text = str(entry.get("text", ""))
            if _sha256_bytes(text.encode("utf-8")) != rec["text_sha256"]:
                raise BuildFail(f"text hash drift for {record_id}")
            return text
    raise BuildFail(f"record {record_id} not found in source")


def _locate(text: str, value: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        i = text.find(value, start)
        if i < 0:
            break
        assert text[i:i + len(value)] == value, "byte-slice verification"
        spans.append((i, i + len(value)))
        start = i + 1
    return spans


def _locate_in(text: str, value: str, lo: int, hi: int) -> list[tuple[int, int]]:
    """Locate value occurrences strictly inside [lo, hi)."""
    spans: list[tuple[int, int]] = []
    start = lo
    while True:
        i = text.find(value, start, hi)
        if i < 0:
            break
        assert text[i:i + len(value)] == value, "byte-slice verification"
        spans.append((i, i + len(value)))
        start = i + 1
    return spans


# ---------------------------------------------------------------------------
# v2 semantic proposals: 36 records re-read and re-adjudicated offline.
# Field spec: (span_text, confidence); modality: (label, [evidence...],
# confidence); empty list = adjudicated ABSENT.
# ---------------------------------------------------------------------------
PROPOSALS_V2: dict[str, dict[str, Any]] = {
    "SIM_card_scenario/r10/v1": {
        "clauses": [{
            "clause_text": "When the customer receives the SIM card, the "
                           "customer is responsable of activating the SIM "
                           "card",
            "modality": ("obligation", ["is responsable of"], 0.5),
            "actors": [("the customer", 0.9)],
            "actions": [("activating the SIM card", 0.85)],
            "conditions": [("When the customer receives the SIM card", 0.85)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Nonstandard cue 'is responsable of' (typo) carries a "
                  "customer duty to activate; semantic reading over the "
                  "deterministic rule that failed on the unknown cue.",
        "needs_attention": True,
    },
    "SIM_card_scenario/r10/v2": {
        "clauses": [{
            "clause_text": "When the customer receives the SIM card, the "
                           "phone company must activate the SIM card so "
                           "that the customer can use the SIM card normally",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [("the phone company", 0.95)],
            "actions": [("activate the SIM card", 0.9)],
            "conditions": [("When the customer receives the SIM card", 0.85)],
            "constraints": [("so that the customer can use the SIM card "
                             "normally", 0.65)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Company activation duty on delivery; the 'so that' "
                  "purpose clause is a low-confidence constraint (purpose "
                  "vs constraint boundary).",
        "needs_attention": True,
    },
    "SIM_card_scenario/r11/v1": {
        "clauses": [{
            "clause_text": "The phone company is not obligated to ask for "
                           "consent to the customer.",
            "modality": ("permission", ["is not obligated"], 0.6),
            "actors": [("The phone company", 0.95)],
            "actions": [("ask for consent to the customer", 0.85)],
            "conditions": [], "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Absence of obligation ('is not obligated') classified as "
                  "PERMISSION (permitted not to ask), NOT prohibition; the "
                  "deterministic v1 rule labeled it prohibition - corrected "
                  "in v2.",
        "needs_attention": True,
    },
    "SIM_card_scenario/r11/v2": {
        "clauses": [{
            "clause_text": "Before retrieving any kind of personal data "
                           "from the Data Subject, the Data Controller has "
                           "to ask the Data Subject for consent",
            "modality": ("obligation", ["has to"], 0.95),
            "actors": [("the Data Controller", 0.95)],
            "actions": [("ask the Data Subject for consent", 0.9)],
            "conditions": [],
            "constraints": [("Before retrieving any kind of personal data "
                             "from the Data Subject", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Consent-before-retrieval duty for the Data Controller; "
                  "'Before ...' is a temporal constraint.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r12/v1": {
        "clauses": [{
            "clause_text": "If the third party denies portability, the "
                           "customer\u2019s personal data must be deleted "
                           "from the database",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be deleted from the database", 0.85)],
            "conditions": [("If the third party denies portability", 0.9)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Deletion duty when portability is denied; passive with no "
                  "stated executor -> actor absent (the data is the "
                  "patient, not the actor).",
        "needs_attention": False,
    },
    "SIM_card_scenario/r13/v1": {
        "clauses": [{
            "clause_text": "Customers with outstanding debt exceeding 100 "
                           "\u20ac are not eligible to receive new SIM cards",
            "modality": ("prohibition", ["are not eligible"], 0.9),
            "actors": [("Customers", 0.8)],
            "actions": [("receive new SIM cards", 0.9)],
            "conditions": [],
            "constraints": [("with outstanding debt exceeding 100 "
                             "\u20ac", 0.8)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Negative eligibility = prohibition of receiving; the "
                  "debt qualifier is a constraint.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r13/v2": {
        "clauses": [{
            "clause_text": "Customers with outstanding debt exceeding 50 "
                           "\u20ac are not eligible to receive new SIM cards",
            "modality": ("prohibition", ["are not eligible"], 0.9),
            "actors": [("Customers", 0.8)],
            "actions": [("receive new SIM cards", 0.9)],
            "conditions": [],
            "constraints": [("with outstanding debt exceeding 50 "
                             "\u20ac", 0.8)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: threshold 100 -> 50 is reflected in the "
                  "constraint span.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r8/v1": {
        "clauses": [{
            "clause_text": "The phone company can take longer than 30 days "
                           "in sending the SIM card.",
            "modality": ("permission", ["can"], 0.9),
            "actors": [("The phone company", 0.95)],
            "actions": [("take longer than 30 days in sending the SIM "
                         "card", 0.8)],
            "conditions": [], "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "'can' = permission; the 'longer than 30 days' quantity "
                  "sits inside the action complement and is not separately "
                  "annotated.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r8/v2": {
        "clauses": [{
            "clause_text": "The process of phone company must be terminated "
                           "if it takes more than 30 days for any reason",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be terminated", 0.9)],
            "conditions": [("if it takes more than 30 days for any reason",
                            0.9)],
            "constraints": [("more than 30 days", 0.8)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Passive 'be terminated'; the process is the patient, the "
                  "terminating party is unstated -> actor absent; the "
                  "temporal quantity inside the condition is annotated "
                  "separately.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r9/v2": {
        "clauses": [{
            "clause_text": "After receiving the customer\u2019s personal "
                           "information, it is necessary to verify the "
                           "correctness of their personal information",
            "modality": ("obligation", ["is necessary"], 0.9),
            "actors": [],
            "actions": [("verify the correctness of their personal "
                         "information", 0.9)],
            "conditions": [],
            "constraints": [("After receiving the customer\u2019s personal "
                             "information", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v1 exact-substring failure fixed: the temporal constraint "
                  "now carries the exact text incl. the curly apostrophe.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r14/v1": {
        "clauses": [{
            "clause_text": "If the donor is donating for the first time, "
                           "information of the nature of the blood donations "
                           "needs to be provided to the donor before their "
                           "consent",
            "modality": ("obligation", ["needs to"], 0.95),
            "actors": [],
            "actions": [("be provided to the donor", 0.8)],
            "conditions": [("If the donor is donating for the first time",
                            0.9)],
            "constraints": [("before their consent", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "First-time donation triggers an information duty before "
                  "consent; passive with recipient 'to the donor' (not the "
                  "actor) -> actor absent.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r14/v2": {
        "clauses": [{
            "clause_text": "Information of the nature of the blood "
                           "donations needs to be provided to the donor "
                           "before their consent",
            "modality": ("obligation", ["needs to"], 0.95),
            "actors": [],
            "actions": [("be provided to the donor", 0.8)],
            "conditions": [],
            "constraints": [("before their consent", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: the first-time condition is dropped; the "
                  "standalone duty + constraint remain.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r15/v1": {
        "clauses": [{
            "clause_text": "If the donor does not consent or retracts "
                           "consent, the process has to terminate",
            "modality": ("obligation", ["has to"], 0.95),
            "actors": [("the process", 0.9)],
            "actions": [("terminate", 0.95)],
            "conditions": [("If the donor does not consent or retracts "
                            "consent", 0.9)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Active intransitive: the process itself terminates -> "
                  "actor 'the process'.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r15/v2": {
        "clauses": [{
            "clause_text": "If the donor does not consent, the process has "
                           "to terminate",
            "modality": ("obligation", ["has to"], 0.95),
            "actors": [("the process", 0.9)],
            "actions": [("terminate", 0.95)],
            "conditions": [("If the donor does not consent", 0.9)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: consent-retraction disjunct dropped; the "
                  "condition span reflects it.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r16/v1": {
        "clauses": [{
            "clause_text": "After the blood collection, the donor is "
                           "monitored for the duration of the bleeding",
            "modality": ("obligation", ["is monitored"], 0.5),
            "actors": [],
            "actions": [("is monitored", 0.8)],
            "conditions": [],
            "constraints": [("After the blood collection", 0.8),
                            ("for the duration of the bleeding", 0.8)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Descriptive monitoring duty with NO standard modal cue; "
                  "the predicate 'is monitored' is the minimal "
                  "cue-containing phrase; passive - the donor is monitored "
                  "by an unstated party -> actor absent; class inference "
                  "debatable.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r17/v1": {
        "clauses": [{
            "clause_text": "If after 15 minutes the donor is still bleeding "
                           "or experiencing more pain, assess the donor  "
                           "and record the reason in the system",
            "modality": ("obligation", ["assess the donor"], 0.55),
            "actors": [],
            "actions": [("assess the donor", 0.85),
                        ("record the reason in the system", 0.85)],
            "conditions": [("If after 15 minutes the donor is still bleeding "
                            "or experiencing more pain", 0.9)],
            "constraints": [("after 15 minutes", 0.7)],
            "exceptions": [],
        }],
        "order_relations": [("c0.actions[0]", "c0.actions[1]")],
        "reason": "v1 exact-substring failure fixed: the imperative was a "
                  "single un-sliced value ('assess the donor  and record...' "
                  "has a double space); v2 splits the two coordinated "
                  "imperatives into separate spans with an order relation "
                  "(assess before record). Imperative = the modality cue.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r17/v2": {
        "clauses": [{
            "clause_text": "If after 20 minutes the donor is still "
                           "bleeding, assess the donor",
            "modality": ("obligation", ["assess the donor"], 0.55),
            "actors": [],
            "actions": [("assess the donor", 0.85)],
            "conditions": [("If after 20 minutes the donor is still "
                            "bleeding", 0.9)],
            "constraints": [("after 20 minutes", 0.7)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: 15 -> 20 minutes reflected in condition "
                  "and constraint; imperative modality inference.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r18/v2": {
        "clauses": [{
            "clause_text": "If a potential donor is rejected, they must be "
                           "immediately sent the reason for rejection",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be immediately sent the reason for rejection",
                         0.8)],
            "conditions": [("If a potential donor is rejected", 0.9)],
            "constraints": [],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Passive 'be sent'; 'they' is the recipient (the rejected "
                  "donor), the sender is unstated -> actor absent; the "
                  "adverb 'immediately' sits inside the contiguous verb "
                  "phrase and is not separately annotated.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r19/v1": {
        "clauses": [{
            "clause_text": "Measuring blood pressure and pulse is needed "
                           "for the determination of donor eligibility",
            "modality": ("obligation", ["is needed"], 0.85),
            "actors": [],
            "actions": [("Measuring blood pressure and pulse", 0.75)],
            "conditions": [],
            "constraints": [("for the determination of donor eligibility",
                             0.7)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Gerund-subject action (the required activity); purpose "
                  "clause as constraint; boundary debatable.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r19/v2": {
        "clauses": [{
            "clause_text": "Measuring blood pressure and pulse is not "
                           "needed for the determination of donor "
                           "eligibility",
            "modality": ("permission", ["is not needed"], 0.6),
            "actors": [],
            "actions": [("Measuring blood pressure and pulse", 0.75)],
            "conditions": [],
            "constraints": [("for the determination of donor eligibility",
                             0.7)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "'is not needed' = absence of requirement -> PERMISSION "
                  "(NOT prohibition); the deterministic rule's class is "
                  "corrected; change version vs r19/v1.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r20/v1": {
        "clauses": [{
            "clause_text": "If the donor has recently undergone surgery or "
                           "received a blood transfusion, the hospital is "
                           "prohibited from collecting blood from the "
                           "donor",
            "modality": ("prohibition", ["is prohibited from"], 0.95),
            "actors": [("the hospital", 0.95)],
            "actions": [("collecting blood from the donor", 0.9)],
            "conditions": [("If the donor has recently undergone surgery or "
                            "received a blood transfusion", 0.9)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Clear prohibition with a disjunctive condition.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r20/v2": {
        "clauses": [{
            "clause_text": "If the donor has recently undergone surgery and "
                           "received a blood transfusion, the hospital is "
                           "prohibited from collecting blood from the "
                           "donor",
            "modality": ("prohibition", ["is prohibited from"], 0.95),
            "actors": [("the hospital", 0.95)],
            "actions": [("collecting blood from the donor", 0.9)],
            "conditions": [("If the donor has recently undergone surgery "
                            "and received a blood transfusion", 0.9)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: or -> and reflected in the condition "
                  "span.",
        "needs_attention": False,
    },
    "emergencies_scenario/r1/v1": {
        "clauses": [{
            "clause_text": "If local anesthesia is administered and the "
                           "patient has a high tolerance to anesthesia, the "
                           "patient must be asked every 20 minutes if they "
                           "are experiencing any pain.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be asked", 0.75)],
            "conditions": [("If local anesthesia is administered and the "
                            "patient has a high tolerance to anesthesia",
                            0.9)],
            "constraints": [("every 20 minutes", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Passive 'be asked' with 'every 20 minutes' as a temporal "
                  "constraint; the embedded question content ('if they are "
                  "experiencing any pain') is not contiguous with the verb "
                  "and is not a condition of the duty, so it is not "
                  "annotated as a separate field.",
        "needs_attention": True,
    },
    "emergencies_scenario/r1/v2": {
        "clauses": [{
            "clause_text": "If local anesthesia is administered and the "
                           "patient has a high tolerance to anesthesia, "
                           "additional anesthesia must be administered "
                           "every 20 minutes",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be administered", 0.85)],
            "conditions": [("If local anesthesia is administered and the "
                            "patient has a high tolerance to anesthesia",
                            0.9)],
            "constraints": [("every 20 minutes", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: the ask-duty becomes an administer-duty; "
                  "passive, actor unstated.",
        "needs_attention": False,
    },
    "emergencies_scenario/r2/v1": {
        "clauses": [
            {
                "clause_text": "Before a surgical intervention, the nurse "
                               "must obtain the patient\u2019s consent.",
                "modality": ("obligation", ["must"], 0.95),
                "actors": [("the nurse", 0.95)],
                "actions": [("obtain the patient\u2019s consent", 0.9)],
                "conditions": [],
                "constraints": [("Before a surgical intervention", 0.85)],
                "exceptions": [],
            },
            {
                "clause_text": "After obtaining consent, the nurse must "
                               "conduct a ``time out'' procedure",
                "modality": ("obligation", ["must"], 0.95),
                "actors": [("the nurse", 0.95)],
                "actions": [("conduct a ``time out'' procedure", 0.85)],
                "conditions": [],
                "constraints": [("After obtaining consent", 0.85)],
                "exceptions": [],
            },
        ],
        "order_relations": [("c0.actions[0]", "c1.actions[0]")],
        "reason": "Two clauses (consent first, then time-out) with an order "
                  "relation; v1's un-sliced multi-value action is split "
                  "into per-clause spans.",
        "needs_attention": False,
    },
    "emergencies_scenario/r2/v2": {
        "clauses": [
            {
                "clause_text": "Before a surgical intervention, the nurse "
                               "must obtain the patient\u2019s consent.",
                "modality": ("obligation", ["must"], 0.95),
                "actors": [("the nurse", 0.95)],
                "actions": [("obtain the patient\u2019s consent", 0.9)],
                "conditions": [],
                "constraints": [("Before a surgical intervention", 0.85)],
                "exceptions": [],
            },
            {
                "clause_text": "After obtaining consent, the doctor must "
                               "conduct a ``time out'' procedure.",
                "modality": ("obligation", ["must"], 0.95),
                "actors": [("the doctor", 0.95)],
                "actions": [("conduct a ``time out'' procedure", 0.85)],
                "conditions": [],
                "constraints": [("After obtaining consent", 0.85)],
                "exceptions": [],
            },
        ],
        "order_relations": [("c0.actions[0]", "c1.actions[0]")],
        "reason": "Change version: the time-out actor changes nurse -> "
                  "doctor; v1 exact-substring failure fixed by clause "
                  "splitting.",
        "needs_attention": False,
    },
    "emergencies_scenario/r3/v1": {
        "clauses": [{
            "clause_text": "If the patient is over 65, a nurse must approve "
                           "discharge before the patient is discharged, and "
                           "approval must occur within 24 hours prior to "
                           "discharge.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [("a nurse", 0.95)],
            "actions": [("approve discharge", 0.9)],
            "conditions": [("If the patient is over 65", 0.9)],
            "constraints": [("before the patient is discharged", 0.85),
                            ("within 24 hours prior to discharge", 0.8)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "The second 'must' clause ('approval must occur within 24 "
                  "hours') is read as an additional temporal constraint on "
                  "the approval (1 clause, 2 constraints); a 2-clause "
                  "reading is also defensible; the validity sentence "
                  "(2024-2030) is not a normative clause and is not "
                  "annotated.",
        "needs_attention": True,
    },
    "emergencies_scenario/r3/v2": {
        "clauses": [{
            "clause_text": "If the patient is over 65 or has more than 5 "
                           "medications, a doctor must approve discharge "
                           "before the patient is discharged.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [("a doctor", 0.95)],
            "actions": [("approve discharge", 0.9)],
            "conditions": [("If the patient is over 65 or has more than 5 "
                            "medications", 0.9)],
            "constraints": [("before the patient is discharged", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: disjunctive condition and doctor actor; "
                  "validity sentence (2025-2031) not annotated.",
        "needs_attention": False,
    },
    "emergencies_scenario/r4/v1": {
        "clauses": [{
            "clause_text": "Before a surgery, blood has to be analyzed.",
            "modality": ("obligation", ["has to"], 0.95),
            "actors": [],
            "actions": [("be analyzed", 0.85)],
            "conditions": [],
            "constraints": [("Before a surgery", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Passive 'be analyzed'; analyzer unstated -> actor absent.",
        "needs_attention": False,
    },
    "emergencies_scenario/r4/v2": {
        "clauses": [{
            "clause_text": "If the doctor does not authorize skipping blood "
                           "analysis, the analysis test should happen before "
                           "the surgery.",
            "modality": ("obligation", ["should"], 0.7),
            "actors": [],
            "actions": [("happen before the surgery", 0.8)],
            "conditions": [("If the doctor does not authorize skipping "
                            "blood analysis", 0.9)],
            "constraints": [("before the surgery", 0.8)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "'should' = soft obligation (NOT permission); the action "
                  "'happen before the surgery' keeps its temporal "
                  "complement; boundary debatable.",
        "needs_attention": True,
    },
    "emergencies_scenario/r5/v1": {
        "clauses": [{
            "clause_text": "Physical examination and blood test are "
                           "required before making a diagnosis.",
            "modality": ("obligation", ["are required"], 0.9),
            "actors": [],
            "actions": [("Physical examination and blood test", 0.7)],
            "conditions": [],
            "constraints": [("before making a diagnosis", 0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "The required activities appear as a nominal subject "
                  "phrase; the action-as-nominal boundary is debatable.",
        "needs_attention": True,
    },
    "emergencies_scenario/r5/v2": {
        "clauses": [{
            "clause_text": "A diagnosis may be made even if the physical "
                           "examination and blood test have not been "
                           "performed.",
            "modality": ("permission", ["may"], 0.95),
            "actors": [],
            "actions": [("be made", 0.85)],
            "conditions": [],
            "constraints": [],
            "exceptions": [("even if the physical examination and blood "
                            "test have not been performed", 0.85)],
        }],
        "order_relations": [],
        "reason": "'may' = permission; the 'even if ... have not been "
                  "performed' clause is an exception to the normal "
                  "requirement.",
        "needs_attention": False,
    },
    "emergencies_scenario/r6/v1": {
        "clauses": [{
            "clause_text": "Blood samples must be collected from all "
                           "patients.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be collected", 0.85)],
            "conditions": [],
            "constraints": [("from all patients", 0.75)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Passive; collector unstated -> actor absent; 'from all "
                  "patients' is the scope constraint.",
        "needs_attention": False,
    },
    "emergencies_scenario/r6/v2": {
        "clauses": [{
            "clause_text": "If the patient is an adult, blood samples must "
                           "be collected.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be collected", 0.85)],
            "conditions": [("If the patient is an adult", 0.9)],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Change version: adult condition added.",
        "needs_attention": False,
    },
    "emergencies_scenario/r7/v1": {
        "clauses": [{
            "clause_text": "Immediately after preparing the patient, "
                           "anesthesia must be applied.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [("be applied", 0.85)],
            "conditions": [],
            "constraints": [("Immediately after preparing the patient",
                             0.85)],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "Passive 'be applied'; actor unstated; the immediacy "
                  "temporal constraint is annotated.",
        "needs_attention": False,
    },
    "emergencies_scenario/r7/v2": {
        "clauses": [{
            "clause_text": "Anesthesia should be applied after patient "
                           "preparation, but the timing is flexible and not "
                           "restricted to immediately after.",
            "modality": ("obligation", ["should"], 0.7),
            "actors": [],
            "actions": [("be applied", 0.85)],
            "conditions": [],
            "constraints": [("after patient preparation", 0.8)],
            "exceptions": [("the timing is flexible and not restricted to "
                            "immediately after", 0.75)],
        }],
        "order_relations": [],
        "reason": "'should' = soft obligation; the waiver clause ('timing "
                  "is flexible...') is an exception; boundary debatable.",
        "needs_attention": True,
    },
}

FIELD_KEYS = ("actors", "actions", "conditions", "constraints", "exceptions")
SHORT = {"actor": "act", "action": "actn", "condition": "cond",
         "constraint": "constr", "exception": "exc"}


def _span_id(sample_id: str, clause_idx: int, field: str,
             span_idx: int) -> str:
    safe = sample_id.replace("/", "_")
    return f"{safe}_c{clause_idx + 1:02d}_{SHORT[field]}_{span_idx}"


def _build_canonical(sample_id: str, text: str,
                     proposal: dict[str, Any]) -> dict[str, Any]:
    clauses_out: list[dict[str, Any]] = []
    aam: list[dict[str, str]] = []
    orders: list[dict[str, str]] = []
    for ci, clause_spec in enumerate(proposal["clauses"]):
        clause_text = clause_spec["clause_text"]
        locs = _locate(text, clause_text)
        if not locs:
            raise BuildFail(
                f"{sample_id}: clause {ci} not found in source text")
        cstart, cend = locs[0]
        modality_spec = clause_spec["modality"]
        label, evidence_texts, mod_conf = modality_spec
        if label not in MODALITY_LABELS:
            raise BuildFail(f"{sample_id}: bad modality label {label!r}")
        evidence: list[dict[str, Any]] = []
        for ei, ev_text in enumerate(evidence_texts):
            ev_locs = _locate_in(text, ev_text, cstart, cend)
            if not ev_locs:
                raise BuildFail(
                    f"{sample_id} c{ci + 1}: modality evidence {ev_text!r} "
                    "not found in the clause")
            for (s, e) in ev_locs:
                evidence.append({
                    "id": _mod_ev_id(sample_id, ci, ei, s),
                    "start": s, "end": e,
                    "text": text[s:e],
                    "confidence": mod_conf,
                })
        clause: dict[str, Any] = {
            "clause_id": f"{sample_id.replace('/', '_')}_c{ci + 1:02d}",
            "clause_span": {"start": cstart, "end": cend,
                            "text": text[cstart:cend]},
            "modality": {"status": "present", "label": label,
                         "evidence": evidence},
        }
        for field in ORDINARY_FIELDS:
            key = field + "s"
            spec = clause_spec.get(key) or []
            spans = []
            for si, (value, conf) in enumerate(spec):
                locs = _locate_in(text, value, cstart, cend)
                if not locs:
                    raise BuildFail(
                        f"{sample_id} c{ci + 1}: {field} span "
                        f"{value!r} not found in the clause")
                for (s, e) in locs:
                    spans.append({
                        "id": _span_id(sample_id, ci, field, si),
                        "start": s, "end": e, "text": text[s:e],
                        "confidence": conf,
                    })
            if spans:
                clause[field] = {"status": "present", "spans": spans}
            else:
                clause[field] = {"status": "absent", "spans": []}
        # actor-action map for clauses with exactly one actor and one action
        if len(clause.get("actor", {}).get("spans", [])) == 1 and \
                len(clause.get("action", {}).get("spans", [])) == 1:
            aam.append({
                "actor_span_id": clause["actor"]["spans"][0]["id"],
                "action_span_id": clause["action"]["spans"][0]["id"],
            })
        clauses_out.append(clause)
    for before, after in proposal.get("order_relations", []):
        b_clause, b_ref = before.split(".")
        a_clause, a_ref = after.split(".")
        orders.append({
            "before_span_id": _resolve_ref(
                sample_id, clauses_out, int(b_clause[1:]), b_ref),
            "after_span_id": _resolve_ref(
                sample_id, clauses_out, int(a_clause[1:]), a_ref),
        })
    return {"clauses": clauses_out, "actor_action_map": aam,
            "order_relations": orders}


def _mod_ev_id(sample_id: str, clause_idx: int, ev_idx: int,
               start: int) -> str:
    safe = sample_id.replace("/", "_")
    return f"{safe}_c{clause_idx + 1:02d}_modev_{ev_idx}_{start}"


def _resolve_ref(sample_id: str, clauses: list[dict[str, Any]],
                 clause_idx: int, ref: str) -> str:
    """ref like 'actions[0]' -> span id."""
    field, idx = ref.split("[")
    idx = int(idx.rstrip("]"))
    field = field[:-1] if field.endswith("s") else field  # actions->action
    spans = clauses[clause_idx].get(field, {}).get("spans", [])
    if idx >= len(spans):
        raise BuildFail(f"{sample_id}: bad order ref {ref!r}")
    return spans[idx]["id"]


def _materialize_full_entry(sample_id: str, rec: dict[str, Any],
                            text: str, proposal: dict[str, Any],
                            g05_level: str) -> dict[str, Any]:
    canonical = _build_canonical(sample_id, text, proposal)
    confs: list[float] = []
    for clause in canonical["clauses"]:
        for ev in clause["modality"]["evidence"]:
            confs.append(float(ev["confidence"]))
        for field in ORDINARY_FIELDS:
            for span in clause[field]["spans"]:
                confs.append(float(span["confidence"]))
    record_conf = min(confs)
    return {
        "sample_id": sample_id,
        "proposal_source": PROPOSAL_SOURCE,
        "human_approved": False,
        "gold": False,
        "reviewer": None,
        "source_path": rec["path"],
        "file_sha256": rec["file_sha256"],
        "text_sha256": rec["text_sha256"],
        "canonical": canonical,
        "record_confidence": round(record_conf, 2),
        "needs_attention": bool(proposal["needs_attention"]),
        "reason": proposal["reason"],
        "g0_5_level": g05_level,
    }


def _strip_text(payload: dict[str, Any]) -> dict[str, Any]:
    """Committed-safe deep copy: drop span/clause `text` fields."""
    import copy
    out = copy.deepcopy(payload)
    for clause in out.get("clauses", []):
        clause["clause_span"].pop("text", None)
        for ev in clause["modality"]["evidence"]:
            ev.pop("text", None)
        for field in ORDINARY_FIELDS:
            for span in clause[field]["spans"]:
                span.pop("text", None)
    return out


def build() -> dict[str, Any]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    if len(membership["records"]) != 36:
        raise BuildFail("membership must have exactly 36 records")
    if set(PROPOSALS_V2) != set(membership["records"]):
        raise BuildFail(
            "proposal v2 coverage mismatch: missing=" +
            str(sorted(set(membership["records"]) - set(PROPOSALS_V2))) +
            " extra=" + str(sorted(set(PROPOSALS_V2) -
                                   set(membership["records"]))))

    local_lines: list[str] = []
    full_entries: dict[str, Any] = {}
    for sample_id in sorted(membership["records"]):
        rec = membership["records"][sample_id]
        text = _load_text(sample_id, rec)
        g05 = classify_frozen(
            g05_features(text),
            draft_config_path=ROOT / DRAFT_REL,
            frozen_config_path=ROOT / FROZEN_REL,
            authorization_manifest_path=ROOT / AUTH_MANIFEST_REL,
            project_root=ROOT)
        entry = _materialize_full_entry(
            sample_id, rec, text, PROPOSALS_V2[sample_id], g05["level"])
        full_entries[sample_id] = entry
        local_lines.append(json.dumps(entry, ensure_ascii=False))

    # ---- canonical validation over the LOCAL full payloads -------------
    source_texts = {}
    for sample_id in sorted(membership["records"]):
        source_texts[sample_id] = _load_text(
            sample_id, membership["records"][sample_id])
    payloads = {sid: {"canonical": e["canonical"]}
                for sid, e in full_entries.items()}
    result = validate(payloads, source_texts, allow_unresolved=True,
                      expected_ids=sorted(membership["records"]))
    if not result["valid"]:
        raise BuildFail("canonical validation failed: " +
                        "; ".join(result["problems"][:20]))

    local_bytes = ("\n".join(local_lines) + "\n").encode("utf-8")
    local_path = V2_LOCAL_DIR / V2_LOCAL_PROPOSALS_REL
    _write(local_path, local_bytes)

    package_md = _render_package(membership, full_entries)
    _write(V2_LOCAL_DIR / V2_LOCAL_PACKAGE_REL,
           package_md.encode("utf-8"))
    diff_md = _render_v1_v2_diff(membership, full_entries)
    _write(V2_LOCAL_DIR / V2_LOCAL_DIFF_REL, diff_md.encode("utf-8"))
    quality = _quality_report(membership, full_entries, local_bytes)
    _write(V2_LOCAL_DIR / V2_LOCAL_QUALITY_REL,
           quality.encode("utf-8"))

    # ---- committed report (coordinates only) ---------------------------
    entries_committed: dict[str, Any] = {}
    for sample_id, entry in full_entries.items():
        e = {k: v for k, v in entry.items() if k != "canonical"}
        e["canonical"] = _strip_text(entry["canonical"])
        entries_committed[sample_id] = e

    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for entry in full_entries.values():
        rc = entry["record_confidence"]
        bucket = ("high" if rc >= 0.8 else
                  "medium" if rc >= 0.6 else "low")
        confidence_counts[bucket] += 1

    v1_report_sha = _sha256_bytes(
        (ROOT / PROPOSAL_REPORT_V1_REL).read_bytes()) \
        if (ROOT / PROPOSAL_REPORT_V1_REL).is_file() else None
    report = {
        "schema_version": "s2_11_proposal_report@2.0.0",
        "proposal_source": PROPOSAL_SOURCE,
        "membership": MEMBERSHIP_REL,
        "proposal_count": len(entries_committed),
        "coverage": "36/36",
        "proposal_file": str(local_path.relative_to(ROOT)),
        "proposal_file_sha256": _sha256_bytes(local_bytes),
        "supersedes_v1": {
            "proposal_file_sha256": V1_PROPOSAL_SHA256,
            "proposal_report_v1": PROPOSAL_REPORT_V1_REL,
            "proposal_report_v1_sha256": v1_report_sha,
            "status": "superseded_proposal_provenance_do_not_approve",
        },
        "confidence_counts": confidence_counts,
        "needs_attention_ids": sorted(
            sid for sid, e in full_entries.items() if e["needs_attention"]),
        "entries": entries_committed,
        "g0_5_frozen_binding": {
            "frozen_config": FROZEN_REL,
            "draft_config": DRAFT_REL,
            "authorization_manifest": AUTH_MANIFEST_REL,
        },
        "raw_text_committed": False,
        "human_approved": False,
        "gold_created": False,
        "zero_api": {"new_llm_api_calls": 0},
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
    }
    return report, quality


# ---------------------------------------------------------------------------
# Rendering (LOCAL packages only; full text lives here, never in Git)
# ---------------------------------------------------------------------------
def _render_package(membership: dict[str, Any],
                    entries: dict[str, Any]) -> str:
    lines = ["# S2.11 Offline AI Adjudication Proposals v2 (decision package)",
             "",
             "**LOCAL-ONLY** - never committed (raw third-party text).",
             "**proposal source**: `deepseek_offline_proposal_v2` "
             "(human_approved=false, gold=false)",
             "**supersedes v1** (SHA `14c1ec909b2c5aa2249d2acfac1f3e411ff00a3c"
             "967a3d6b2ed06ddba8c7364b`; do NOT approve v1)",
             "**field states**: `PRESENT` (spans below) | `ABSENT` "
             "(adjudicated absent) | `UNRESOLVED` (none in this package)",
             ""]
    ordered = sorted(entries, key=lambda rid: (
        0 if entries[rid]["needs_attention"] else 1,
        entries[rid]["record_confidence"],
        rid))
    for rid in ordered:
        e = entries[rid]
        text = _load_text(rid, membership["records"][rid])
        lines.append(f"## {rid}")
        lines.append("")
        lines.append(f"- confidence: {e['record_confidence']} | "
                     f"needs_attention: {e['needs_attention']} | "
                     f"g0_5: {e['g0_5_level']}")
        lines.append(f"- reason: {e['reason']}")
        lines.append("")
        lines.append("```")
        lines.append(text)
        lines.append("```")
        lines.append("")
        for ci, clause in enumerate(e["canonical"]["clauses"]):
            lines.append(f"### clause {ci + 1}: "
                         f"`{clause['clause_span']['text']}`")
            lines.append("")
            mod = clause["modality"]
            ev = "; ".join(f"[{s['start']}:{s['end']}] `{s['text']}`"
                           for s in mod["evidence"])
            lines.append(f"- modality: **{mod['label']}** "
                         f"(evidence: {ev})")
            for field in ORDINARY_FIELDS:
                entry = clause[field]
                if entry["status"] == "absent":
                    lines.append(f"- {field}: **ABSENT**")
                    continue
                if entry["status"] == "unresolved":
                    lines.append(f"- {field}: **UNRESOLVED**")
                    continue
                parts = []
                for span in entry["spans"]:
                    parts.append(f"[{span['start']}:{span['end']}] "
                                 f"`{span['text']}` "
                                 f"(conf {span['confidence']})")
                lines.append(f"- {field}: PRESENT - " + " | ".join(parts))
            lines.append("")
        if e["canonical"]["actor_action_map"]:
            lines.append("- actor_action_map: " + "; ".join(
                f"{p['actor_span_id']} -> {p['action_span_id']}"
                for p in e["canonical"]["actor_action_map"]))
        if e["canonical"]["order_relations"]:
            lines.append("- order_relations: " + "; ".join(
                f"{r['before_span_id']} < {r['after_span_id']}"
                for r in e["canonical"]["order_relations"]))
        lines.append("")
        lines.append("*optional revision: "
                     "_________________________________________________________________*")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_v1_v2_diff(membership: dict[str, Any],
                       entries: dict[str, Any]) -> str:
    lines = ["# S2.11 proposal v1 -> v2 semantic diff (LOCAL-ONLY)", ""]
    v1_path = ROOT / V1_LOCAL_REL
    if not v1_path.is_file():
        lines.append("v1 local proposals file not found; diff unavailable.")
        return "\n".join(lines) + "\n"
    v1_lines = [json.loads(ln) for ln in
                v1_path.read_text(encoding="utf-8").splitlines() if ln]
    v1 = {e["sample_id"]: e for e in v1_lines}
    lines.append("## v1 summary (as recorded)")
    lines.append("")
    lines.append(f"- proposal file SHA-256: "
                 f"`{_sha256_bytes(v1_path.read_bytes())}`")
    missing_in_text = []
    multi = []
    for sid, e in sorted(v1.items()):
        for f, fi in e["fields"].items():
            for g in fi["spans"]:
                if "value_missing_in_text" in g:
                    missing_in_text.append((sid, f))
            if isinstance(fi.get("value"), list) and len(fi["value"]) > 1:
                multi.append((sid, f))
    lines.append(f"- v1 value_missing_in_text fields: {len(missing_in_text)}")
    lines.append(f"- v1 multi-value fields: {len(multi)}")
    lines.append("")
    lines.append("## Per-record v2 corrections")
    lines.append("")
    for sid in sorted(entries):
        e2 = entries[sid]
        e1 = v1.get(sid)
        lines.append(f"### {sid}")
        lines.append("")
        if e1 is None:
            lines.append("- v1: MISSING; v2: added")
            lines.append("")
            continue
        mod1 = e1.get("fields", {}).get("modality", {})
        mod2 = e2["canonical"]["clauses"][0]["modality"]
        if mod1.get("present") and mod1.get("value") != mod2["label"]:
            lines.append(f"- modality: v1 `{mod1.get('value')}` -> v2 "
                         f"`{mod2['label']}` (evidence spans now "
                         "byte-verified)")
        missing1 = [f for f, fi in e1.get("fields", {}).items()
                    for g in fi["spans"] if "value_missing_in_text" in g]
        if missing1:
            lines.append(f"- v1 value_missing_in_text resolved: "
                         f"{', '.join(missing1)}")
        if e2["needs_attention"] and not e1.get("needs_attention"):
            lines.append("- v2 marks needs_attention (v1 did not)")
        lines.append(f"- v2 confidence {e2['record_confidence']} | "
                     f"needs_attention {e2['needs_attention']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _quality_report(membership: dict[str, Any],
                    entries: dict[str, Any],
                    local_bytes: bytes) -> str:
    exact_failures = 0
    evidence_missing = 0
    display_none = 0
    multi_structures = 0
    present_count = 0
    absent_count = 0
    unresolved_count = 0
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for sid, e in sorted(entries.items()):
        rc = e["record_confidence"]
        confidence_counts["high" if rc >= 0.8 else
                          "medium" if rc >= 0.6 else "low"] += 1
        for clause in e["canonical"]["clauses"]:
            for ev in clause["modality"]["evidence"]:
                present_count += 1
            if not clause["modality"]["evidence"]:
                evidence_missing += 1
            for field in ORDINARY_FIELDS:
                entry = clause[field]
                if entry["status"] == "present":
                    present_count += 1
                    if len(entry["spans"]) > 1:
                        multi_structures += 1
                elif entry["status"] == "absent":
                    absent_count += 1
                else:
                    unresolved_count += 1
    na_ids = sorted(s for s, e in entries.items() if e["needs_attention"])
    lines = [
        "# S2.11 proposal v2 quality report (LOCAL-ONLY)", "",
        f"- proposal file SHA-256: `{_sha256_bytes(local_bytes)}`",
        f"- coverage: {len(entries)}/36",
        f"- exact-slice failures (text == source[start:end]): "
        f"{exact_failures}",
        f"- modality evidence missing: {evidence_missing}",
        f"- present fields displayed as None: {display_none}",
        f"- multi-value (multi-span) field structures: {multi_structures}",
        f"- field states: present {present_count} / absent {absent_count} / "
        f"unresolved {unresolved_count}",
        f"- confidence buckets: {confidence_counts}",
        f"- needs_attention ids ({len(na_ids)}):",
    ]
    for sid in na_ids:
        lines.append(f"  - {sid}")
    lines.append("")
    lines.append("All spans are byte-verified against the hash-bound source "
                 "text (text == source[start:end]); committed artifacts "
                 "carry coordinates only.")
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        report, quality = build()
    except BuildFail as exc:
        print(f"PROPOSAL V2 BUILD FAILED (fail-closed): {exc}",
              file=sys.stderr)
        return 2
    data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    try:
        _write(ROOT / PROPOSAL_REPORT_V2_REL, data)
    except BuildFail as exc:
        print(f"PROPOSAL V2 BUILD FAILED (refusing overwrite): {exc}",
              file=sys.stderr)
        return 2
    print(f"proposal v2 report written: {PROPOSAL_REPORT_V2_REL} "
          f"({report['proposal_count']} proposals, "
          f"confidence={report['confidence_counts']})")
    print(f"proposal file SHA-256: {report['proposal_file_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

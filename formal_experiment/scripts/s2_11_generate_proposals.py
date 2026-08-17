# -*- coding: utf-8 -*-
"""Deterministic S2.11 offline AI adjudication-PROPOSAL generator
(Checkpoint C; ZERO real LLM/API calls).

The proposals in this module were produced by the executing agent's
offline reading of the 36 hash-verified non-empty membership records
(deepseek_offline_proposal). They are AI SUGGESTIONS ONLY:
  * human_approved=false, gold=false;
  * reviewer is NEVER set to the user;
  * field values are located in the source text by exact substring search
    and every span is byte-verified (text[start:end] == value);
  * fields that are semantically absent stay null/absent — nothing is
    invented to fill the six fields;
  * the frozen G0.5 classifier level is computed for every record via the
    sealed v6 chain (classify_frozen).

Outputs:
  LOCAL (gitignored, never committed):
    outputs/development/s2_11_local_working/adjudication_proposals_v1/
      proposals.jsonl        (full text + proposals + spans)
      decision_package.md    (ordered review package)
  COMMITTED (coordinates/hashes/counts ONLY — no reconstructable raw
    third-party text):
    outputs/reports/s2_11_proposal_report_v1.json
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
from bpc_hybrid.s2_11_corpus_ingestion import g05_features  # noqa: E402

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"
AUTH_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
PROPOSAL_REPORT_REL = "outputs/reports/s2_11_proposal_report_v1.json"
LOCAL_DIR = ROOT / "outputs" / "development" / "s2_11_local_working" / \
    "adjudication_proposals_v1"
LOCAL_PROPOSALS_REL = "proposals.jsonl"
LOCAL_PACKAGE_REL = "decision_package.md"

PROPOSAL_SOURCE = "deepseek_offline_proposal"

# ---------------------------------------------------------------------------
# Per-record offline proposals: field -> (value | None, confidence).
# Values are EXACT substrings of the source text (the generator locates and
# byte-verifies the spans). Lists mean multiple values/spans. None means
# the field is semantically absent (never invented).
# ---------------------------------------------------------------------------
PROPOSALS: dict[str, dict[str, Any]] = {
    "blood_donation_scenario/r14/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("provided", 0.7),
        "condition": ("If the donor is donating for the first time", 0.9),
        "constraint": ("before their consent", 0.85),
        "exception": (None, 0.9),
        "reason": "First-time donation triggers an information duty before "
                  "consent; the acting provider is implicit.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r14/v2": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("provided", 0.75),
        "condition": (None, 0.9),
        "constraint": ("before their consent", 0.85),
        "exception": (None, 0.9),
        "reason": "Standalone information duty before consent (change "
                  "version without the first-time condition).",
        "needs_attention": False,
    },
    "blood_donation_scenario/r15/v1": {
        "modality": ("obligation", 0.95),
        "actor": ("the process", 0.9),
        "action": ("terminate", 0.95),
        "condition": ("If the donor does not consent or retracts consent",
                      0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Termination duty on non-consent or consent retraction.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r15/v2": {
        "modality": ("obligation", 0.95),
        "actor": ("the process", 0.9),
        "action": ("terminate", 0.95),
        "condition": ("If the donor does not consent", 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Termination duty on non-consent (change version).",
        "needs_attention": False,
    },
    "blood_donation_scenario/r16/v1": {
        "modality": ("obligation", 0.55),
        "actor": (None, 0.6),
        "action": ("is monitored", 0.8),
        "condition": (None, 0.9),
        "constraint": (["After the blood collection",
                        "for the duration of the bleeding"], 0.8),
        "exception": (None, 0.9),
        "reason": "No modal keyword; descriptive monitoring duty after "
                  "collection — modality and acting party need user "
                  "confirmation.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r17/v1": {
        "modality": ("obligation", 0.6),
        "actor": (None, 0.5),
        "action": ("assess the donor and record the reason in the system",
                   0.85),
        "condition": ("If after 15 minutes the donor is still bleeding or "
                      "experiencing more pain", 0.9),
        "constraint": ("after 15 minutes", 0.7),
        "exception": (None, 0.9),
        "reason": "Imperative conditional duty; the 15-minute trigger sits "
                  "inside the condition clause.",
        "needs_attention": True,
    },
    "blood_donation_scenario/r17/v2": {
        "modality": ("obligation", 0.6),
        "actor": (None, 0.5),
        "action": ("assess the donor", 0.85),
        "condition": ("If after 20 minutes the donor is still bleeding",
                      0.9),
        "constraint": ("after 20 minutes", 0.7),
        "exception": (None, 0.9),
        "reason": "Imperative conditional duty (change version; 20-minute "
                  "trigger).",
        "needs_attention": True,
    },
    "blood_donation_scenario/r18/v2": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("sent", 0.8),
        "condition": ("If a potential donor is rejected", 0.9),
        "constraint": ("immediately", 0.8),
        "exception": (None, 0.9),
        "reason": "Rejection notice must be sent immediately; sender "
                  "implicit.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r19/v1": {
        "modality": ("obligation", 0.9),
        "actor": (None, 0.7),
        "action": ("Measuring blood pressure and pulse", 0.85),
        "condition": (None, 0.9),
        "constraint": ("for the determination of donor eligibility", 0.8),
        "exception": (None, 0.9),
        "reason": "Measurements required for eligibility determination.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r19/v2": {
        "modality": ("prohibition", 0.9),
        "actor": (None, 0.7),
        "action": ("Measuring blood pressure and pulse", 0.85),
        "condition": (None, 0.9),
        "constraint": ("for the determination of donor eligibility", 0.8),
        "exception": (None, 0.9),
        "reason": "Negated need = the measurement duty is removed (change "
                  "version).",
        "needs_attention": False,
    },
    "blood_donation_scenario/r20/v1": {
        "modality": ("prohibition", 0.95),
        "actor": ("the hospital", 0.95),
        "action": ("collecting blood from the donor", 0.9),
        "condition": ("If the donor has recently undergone surgery or "
                      "received a blood transfusion", 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Collection prohibited after surgery or transfusion.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r20/v2": {
        "modality": ("prohibition", 0.95),
        "actor": ("the hospital", 0.95),
        "action": ("collecting blood from the donor", 0.9),
        "condition": ("If the donor has recently undergone surgery and "
                      "received a blood transfusion", 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Collection prohibited after surgery AND transfusion "
                  "(change version).",
        "needs_attention": False,
    },
    "emergencies_scenario/r1/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("asked", 0.8),
        "condition": ("If local anesthesia is administered and the patient "
                      "has a high tolerance to anesthesia", 0.9),
        "constraint": ("every 20 minutes", 0.85),
        "exception": (None, 0.9),
        "reason": "Pain check duty every 20 minutes under the anesthesia "
                  "condition; the trailing pain clause is a secondary "
                  "condition.",
        "needs_attention": False,
    },
    "emergencies_scenario/r1/v2": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("administered", 0.8),
        "condition": ("If local anesthesia is administered and the patient "
                      "has a high tolerance to anesthesia", 0.9),
        "constraint": ("every 20 minutes", 0.85),
        "exception": (None, 0.9),
        "reason": "Additional anesthesia duty every 20 minutes (change "
                  "version).",
        "needs_attention": False,
    },
    "emergencies_scenario/r2/v1": {
        "modality": ("obligation", 0.9),
        "actor": ("the nurse", 0.95),
        "action": (["obtain the patient's consent",
                    "conduct a ``time out'' procedure"], 0.9),
        "condition": (None, 0.9),
        "constraint": (["Before a surgical intervention",
                        "After obtaining consent"], 0.85),
        "exception": (None, 0.9),
        "reason": "Two 'must' occurrences make the deterministic candidate "
                  "span ambiguous; the duty is clearly an obligation with "
                  "two ordered actions.",
        "needs_attention": True,
    },
    "emergencies_scenario/r2/v2": {
        "modality": ("obligation", 0.9),
        "actor": (["the nurse", "the doctor"], 0.8),
        "action": (["obtain the patient's consent",
                    "conduct a ``time out'' procedure"], 0.9),
        "condition": (None, 0.9),
        "constraint": (["Before a surgical intervention",
                        "After obtaining consent"], 0.85),
        "exception": (None, 0.9),
        "reason": "Two actors (nurse then doctor) for the two duties; "
                  "dual 'must' span ambiguous for the deterministic "
                  "candidate.",
        "needs_attention": True,
    },
    "emergencies_scenario/r3/v1": {
        "modality": ("obligation", 0.9),
        "actor": ("a nurse", 0.85),
        "action": ("approve discharge", 0.9),
        "condition": ("If the patient is over 65", 0.9),
        "constraint": (["before the patient is discharged",
                        "within 24 hours prior to discharge",
                        "valid from 2024 to 2030"], 0.8),
        "exception": (None, 0.9),
        "reason": "Approval duty with two temporal constraints plus a "
                  "rule validity window; dual 'must' makes the "
                  "deterministic span ambiguous.",
        "needs_attention": True,
    },
    "emergencies_scenario/r3/v2": {
        "modality": ("obligation", 0.95),
        "actor": ("a doctor", 0.9),
        "action": ("approve discharge", 0.9),
        "condition": ("If the patient is over 65 or has more than 5 "
                      "medications", 0.9),
        "constraint": (["before the patient is discharged",
                        "valid from 2025 to 2031"], 0.8),
        "exception": (None, 0.9),
        "reason": "Doctor approval duty (change version) with a validity "
                  "window.",
        "needs_attention": False,
    },
    "emergencies_scenario/r4/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("analyzed", 0.85),
        "condition": (None, 0.9),
        "constraint": ("Before a surgery", 0.85),
        "exception": (None, 0.9),
        "reason": "Blood analysis duty before surgery.",
        "needs_attention": False,
    },
    "emergencies_scenario/r4/v2": {
        "modality": ("obligation", 0.8),
        "actor": (None, 0.6),
        "action": ("happen", 0.7),
        "condition": ("If the doctor does not authorize skipping blood "
                      "analysis", 0.9),
        "constraint": ("before the surgery", 0.85),
        "exception": (None, 0.9),
        "reason": "Soft duty ('should') — analysis before surgery unless "
                  "the doctor authorizes skipping it.",
        "needs_attention": False,
    },
    "emergencies_scenario/r5/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.7),
        "action": ("Physical examination and blood test", 0.85),
        "condition": (None, 0.9),
        "constraint": ("before making a diagnosis", 0.85),
        "exception": (None, 0.9),
        "reason": "Examination and blood test required pre-diagnosis.",
        "needs_attention": False,
    },
    "emergencies_scenario/r5/v2": {
        "modality": ("permission", 0.9),
        "actor": (None, 0.6),
        "action": ("made", 0.8),
        "condition": (None, 0.9),
        "constraint": (None, 0.9),
        "exception": ("even if the physical examination and blood test "
                      "have not been performed", 0.85),
        "reason": "Permission to diagnose with an explicit exception "
                  "clause.",
        "needs_attention": False,
    },
    "emergencies_scenario/r6/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("collected", 0.85),
        "condition": (None, 0.9),
        "constraint": ("from all patients", 0.8),
        "exception": (None, 0.9),
        "reason": "Universal collection duty; the patient scope is a "
                  "qualifier.",
        "needs_attention": False,
    },
    "emergencies_scenario/r6/v2": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("collected", 0.85),
        "condition": ("If the patient is an adult", 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Collection duty for adult patients (change version).",
        "needs_attention": False,
    },
    "emergencies_scenario/r7/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("applied", 0.85),
        "condition": (None, 0.9),
        "constraint": ("Immediately after preparing the patient", 0.85),
        "exception": (None, 0.9),
        "reason": "Anesthesia application duty immediately after "
                  "preparation.",
        "needs_attention": False,
    },
    "emergencies_scenario/r7/v2": {
        "modality": ("obligation", 0.75),
        "actor": (None, 0.6),
        "action": ("applied", 0.85),
        "condition": (None, 0.9),
        "constraint": ("after patient preparation", 0.8),
        "exception": ("but the timing is flexible and not restricted to "
                      "immediately after", 0.75),
        "reason": "Soft obligation with a flexibility carve-out "
                  "(exception) (change version).",
        "needs_attention": False,
    },
    "SIM_card_scenario/r8/v1": {
        "modality": ("permission", 0.9),
        "actor": ("The phone company", 0.95),
        "action": ("take longer than 30 days in sending the SIM card",
                   0.85),
        "condition": (None, 0.9),
        "constraint": ("longer than 30 days", 0.8),
        "exception": (None, 0.9),
        "reason": "Permission to exceed the 30-day sending window.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r8/v2": {
        "modality": ("obligation", 0.95),
        "actor": ("The process of phone company", 0.9),
        "action": ("terminated", 0.9),
        "condition": ("if it takes more than 30 days for any reason", 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Termination duty when the process exceeds 30 days "
                  "(change version).",
        "needs_attention": False,
    },
    "SIM_card_scenario/r9/v2": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("verify the correctness of their personal information",
                   0.9),
        "condition": (None, 0.9),
        "constraint": ("After receiving the customer's personal "
                       "information", 0.85),
        "exception": (None, 0.9),
        "reason": "Verification duty after receiving personal information.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r10/v1": {
        "modality": ("obligation", 0.55),
        "actor": ("the customer", 0.9),
        "action": ("activating the SIM card", 0.85),
        "condition": ("When the customer receives the SIM card", 0.85),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Duty marker 'is responsable of' (typo) — no standard "
                  "modal keyword; deterministic candidate failed; "
                  "semantic reading = customer must activate.",
        "needs_attention": True,
    },
    "SIM_card_scenario/r10/v2": {
        "modality": ("obligation", 0.95),
        "actor": ("the phone company", 0.95),
        "action": ("activate the SIM card", 0.9),
        "condition": ("When the customer receives the SIM card", 0.85),
        "constraint": ("so that the customer can use the SIM card "
                       "normally", 0.7),
        "exception": (None, 0.9),
        "reason": "Company activation duty on delivery; the purpose clause "
                  "is a low-confidence constraint.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r11/v1": {
        "modality": ("permission", 0.6),
        "actor": ("The phone company", 0.95),
        "action": ("ask for consent to the customer", 0.9),
        "condition": (None, 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "'not obligated' = absence of obligation (permission-"
                  "like); the deterministic rule labels it prohibition — "
                  "user should confirm the intended class.",
        "needs_attention": True,
    },
    "SIM_card_scenario/r11/v2": {
        "modality": ("obligation", 0.95),
        "actor": ("the Data Controller", 0.95),
        "action": ("ask the Data Subject for consent", 0.9),
        "condition": (None, 0.9),
        "constraint": ("Before retrieving any kind of personal data from "
                       "the Data Subject", 0.85),
        "exception": (None, 0.9),
        "reason": "Consent-before-retrieval duty for the Data Controller.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r12/v1": {
        "modality": ("obligation", 0.95),
        "actor": (None, 0.6),
        "action": ("deleted from the database", 0.85),
        "condition": ("If the third party denies portability", 0.9),
        "constraint": (None, 0.9),
        "exception": (None, 0.9),
        "reason": "Deletion duty when portability is denied.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r13/v1": {
        "modality": ("prohibition", 0.9),
        "actor": ("Customers", 0.8),
        "action": ("receive new SIM cards", 0.9),
        "condition": (None, 0.9),
        "constraint": ("with outstanding debt exceeding 100 €", 0.8),
        "exception": (None, 0.9),
        "reason": "Eligibility prohibition for customers with high debt; "
                  "the debt qualifier may read as a condition.",
        "needs_attention": False,
    },
    "SIM_card_scenario/r13/v2": {
        "modality": ("prohibition", 0.9),
        "actor": ("Customers", 0.8),
        "action": ("receive new SIM cards", 0.9),
        "condition": (None, 0.9),
        "constraint": ("with outstanding debt exceeding 50 €", 0.8),
        "exception": (None, 0.9),
        "reason": "Eligibility prohibition (change version; lower debt "
                  "threshold).",
        "needs_attention": False,
    },
}

FIELDS = ("modality", "actor", "action", "condition", "constraint",
          "exception")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise RuntimeError(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def locate_spans(text: str, value: str) -> list[dict[str, int]]:
    spans: list[dict[str, int]] = []
    start = 0
    while True:
        i = text.find(value, start)
        if i < 0:
            break
        assert text[i:i + len(value)] == value, "byte-slice verification"
        spans.append({"start": i, "end": i + len(value)})
        start = i + 1
    return spans


def generate() -> dict[str, Any]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    records = membership["records"]
    if len(records) != 36:
        raise RuntimeError("membership must contain exactly 36 non-empty "
                           f"records, got {len(records)}")
    expected_ids = set(PROPOSALS)
    if expected_ids != set(records):
        raise RuntimeError(
            "proposal coverage mismatch: missing=" +
            str(sorted(expected_ids - set(records))) +
            " extra=" + str(sorted(set(records) - expected_ids)))

    local_lines: list[str] = []
    entries: dict[str, Any] = {}
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    issue_counts: dict[str, int] = {}
    for record_id in sorted(records):
        rec = records[record_id]
        proposal = PROPOSALS[record_id]
        text = _load_text(record_id, rec)
        fields: dict[str, Any] = {}
        confs: list[float] = []
        for field in FIELDS:
            spec = proposal[field]
            if spec is None:
                raise RuntimeError(f"{record_id}: malformed proposal field")
            value, conf = spec
            confs.append(float(conf))
            if value is None:
                fields[field] = {"present": False, "value": None,
                                 "spans": [], "confidence": conf}
                continue
            values = value if isinstance(value, list) else [value]
            spans = []
            for v in values:
                located = locate_spans(text, v)
                if not located:
                    spans.append({"value_missing_in_text": True})
                else:
                    spans.append({"spans": located})
            fields[field] = {"present": True, "value": value,
                             "spans": spans, "confidence": conf}
        record_conf = min(confs)
        bucket = ("high" if record_conf >= 0.8 else
                  "medium" if record_conf >= 0.6 else "low")
        confidence_counts[bucket] += 1
        needs_attention = bool(proposal["needs_attention"])
        issue = "needs_attention" if needs_attention else "none"
        issue_counts[issue] = issue_counts.get(issue, 0) + 1
        g05 = classify_frozen(
            g05_features(text),
            draft_config_path=ROOT / DRAFT_REL,
            frozen_config_path=ROOT / FROZEN_REL,
            authorization_manifest_path=ROOT / AUTH_MANIFEST_REL,
            project_root=ROOT)
        entry = {
            "sample_id": record_id,
            "proposal_source": PROPOSAL_SOURCE,
            "human_approved": False,
            "gold": False,
            "reviewer": None,
            "source_path": rec["path"],
            "file_sha256": rec["file_sha256"],
            "text_sha256": rec["text_sha256"],
            "fields": fields,
            "record_confidence": round(record_conf, 2),
            "needs_attention": needs_attention,
            "reason": proposal["reason"],
            "g0_5": {"level": g05["level"]},
        }
        local_lines.append(json.dumps(entry, ensure_ascii=False))
        entries[record_id] = {
            "sample_id": record_id,
            "proposal_source": PROPOSAL_SOURCE,
            "human_approved": False,
            "gold": False,
            "reviewer": None,
            "text_sha256": rec["text_sha256"],
            "file_sha256": rec["file_sha256"],
            "fields": {
                f: {"present": fields[f]["present"],
                    "spans": fields[f]["spans"],
                    "confidence": fields[f]["confidence"]}
                for f in FIELDS
            },
            "record_confidence": round(record_conf, 2),
            "needs_attention": needs_attention,
            "issue_type": issue,
            "reason": proposal["reason"],
            "g0_5_level": g05["level"],
        }
    local_bytes = ("\n".join(local_lines) + "\n").encode("utf-8")
    local_path = LOCAL_DIR / LOCAL_PROPOSALS_REL
    _write(local_path, local_bytes)
    package_md = render_package(membership, entries, local_path)
    _write(LOCAL_DIR / LOCAL_PACKAGE_REL, package_md.encode("utf-8"))

    report = {
        "schema_version": "s2_11_proposal_report@1.0.0",
        "proposal_source": PROPOSAL_SOURCE,
        "membership": MEMBERSHIP_REL,
        "proposal_count": len(entries),
        "coverage": "36/36",
        "proposal_file": str(local_path.relative_to(ROOT)),
        "proposal_file_sha256": _sha256_bytes(local_bytes),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "issue_counts": dict(sorted(issue_counts.items())),
        "needs_attention_ids": sorted(
            rid for rid, e in entries.items() if e["needs_attention"]),
        "entries": entries,
        "g0_5_frozen_binding": {
            "frozen_config": FROZEN_REL,
            "draft_config": DRAFT_REL,
            "authorization_manifest": AUTH_MANIFEST_REL,
        },
        "raw_text_committed": False,
        "human_approved": False,
        "gold_created": False,
        "zero_api": {"new_llm_api_calls": 0},
    }
    return report


def _load_text(record_id: str, rec: dict[str, Any]) -> str:
    path = ROOT.parent / rec["path"]
    raw = path.read_bytes()
    if _sha256_bytes(raw) != rec["file_sha256"]:
        raise RuntimeError(f"source file hash drift for {record_id}")
    scenario, rid, version = record_id.split("/")
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and \
                str(entry.get("version")) == version.lstrip("v"):
            text = str(entry.get("text", ""))
            if _sha256_bytes(text.encode("utf-8")) != rec["text_sha256"]:
                raise RuntimeError(f"text hash drift for {record_id}")
            return text
    raise RuntimeError(f"record {record_id} not found in source")


def render_package(membership: dict[str, Any],
                   entries: dict[str, Any],
                   local_path: Path) -> str:
    lines: list[str] = []
    lines.append("# S2.11 Offline AI Adjudication Proposals (decision package)")
    lines.append("")
    lines.append("**LOCAL-ONLY** — never committed (raw third-party text).")
    lines.append(f"**proposal file**: `{local_path}`")
    lines.append("**proposal source**: `deepseek_offline_proposal` "
                 "(human_approved=false, gold=false)")
    lines.append("")
    ordered = sorted(entries, key=lambda rid: (
        0 if entries[rid]["needs_attention"] else 1,
        entries[rid]["record_confidence"],
        rid))
    for rid in ordered:
        e = entries[rid]
        rec = membership["records"][rid]
        text = _load_text(rid, rec)
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
        lines.append("| field | present | proposal value | spans | confidence |")
        lines.append("|---|---|---|---|---|")
        for f in FIELDS:
            fi = e["fields"][f]
            value = _field_value_text(fi)
            span_txt = _field_span_text(fi)
            lines.append(f"| {f} | {fi['present']} | {value} | "
                         f"{span_txt} | {fi['confidence']} |")
        lines.append("")
        lines.append("*optional revision: _________________________________________________________________*")
        lines.append("")
    return "\n".join(lines) + "\n"


def _field_value_text(fi: dict[str, Any]) -> str:
    if not fi["present"]:
        return "null/absent"
    value = fi.get("value")
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def _field_span_text(fi: dict[str, Any]) -> str:
    if not fi["present"]:
        return "-"
    parts = []
    for span_group in fi["spans"]:
        if "value_missing_in_text" in span_group:
            parts.append("NOT-IN-TEXT")
        else:
            parts.append(";".join(f"{s['start']}:{s['end']}"
                                  for s in span_group["spans"]))
    return " | ".join(parts)


def main() -> int:
    try:
        report = generate()
        data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n") \
            .encode("utf-8")
        _write(ROOT / PROPOSAL_REPORT_REL, data)
    except Exception as exc:  # noqa: BLE001 - fail-closed reporting
        print(f"PROPOSAL GENERATION FAILED (fail-closed): {exc}",
              file=sys.stderr)
        return 2
    print(f"proposal report written: {PROPOSAL_REPORT_REL} "
          f"({report['proposal_count']} proposals, "
          f"confidence={report['confidence_counts']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

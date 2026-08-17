# -*- coding: utf-8 -*-
"""Deterministic S2.11 canonical proposal v3 builder (Checkpoint F; ZERO
real LLM/API).

v3 carries the v2 canonical model forward with TARGETED, evidence-based
corrections (proposal v2 SHA
9386642738e73ac2296edb709bd1183b072cacca328b3359762551d0e2b2e5ac is
declared superseded_pending_targeted_correction_do_not_approve; v1/v2
files stay byte-identical as provenance). Corrections:

  1. SIM r10v1: actor = ONLY the main-clause "the customer" (explicit
     occurrence 1; the condition-internal customer stays inside the
     condition); actor-action mapping established; all ids unique.
  2. Canonical validator v3: duplicate ordinary span ids / duplicate
     clause ids refuse; actor_action_map edges must exist, stay within
     one clause and cover every action of any actor-bearing clause;
     order relations reference two DIFFERENT existing actions; span
     collection is list-based (no dict-overwrite hiding).
  3. emergencies r4v2: action = exact raw span "happen" with
     normalized "happen before the surgery"; constraint "before the
     surgery"; action/constraint overlap = 0.
  4. SIM r8v1: constraint "longer than 30 days"; action = exact raw
     span "sending the SIM card" (normalized full VP); actor-action
     mapping kept.
  5. blood r18v2: constraint "immediately"; action = exact raw span
     "sent the reason for rejection" (normalized full VP); passive
     executor stays absent.
  6. emergencies r3v1/r3v2: temporal-validity constraint
     "valid from 2024 to 2030" / "valid from 2025 to 2031" added; the
     normative clause span is extended to the full record (no fake
     clause is created; the existing condition/action/constraints are
     kept).

Generator rules (fail-closed):
  * every span spec must be exact and unambiguous: a spec may carry an
    explicit occurrence index; without one, multiple occurrences in the
    clause REFUSE the build (no automatic add-all)
  * every ordinary span id is unique across the record
  * all 36 records are re-validated with canonical v3 (acceptance
    counts are test-forced)

Outputs:
  LOCAL (gitignored):
    outputs/development/s2_11_local_working/adjudication_proposals_v3/
      proposals.jsonl / decision_package.md / v2_to_v3_semantic_diff.md /
      quality_report.md
  COMMITTED (coordinates/hashes/counts/ids only):
    outputs/reports/s2_11_proposal_report_v3.json
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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from bpc_hybrid.g05_complexity_candidate import (  # noqa: E402
    classify_frozen,
)
from bpc_hybrid.s2_11_canonical_v3 import (  # noqa: E402
    MODALITY_LABELS,
    ORDINARY_FIELDS,
    validate,
)
from bpc_hybrid.s2_11_corpus_ingestion import g05_features  # noqa: E402
from s2_11_build_proposals_v2 import PROPOSALS_V2  # noqa: E402

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"
AUTH_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
PROPOSAL_REPORT_V2_REL = "outputs/reports/s2_11_proposal_report_v2.json"
PROPOSAL_REPORT_V3_REL = "outputs/reports/s2_11_proposal_report_v3.json"
V2_LOCAL_REL = ("outputs/development/s2_11_local_working/"
                "adjudication_proposals_v2/proposals.jsonl")
V3_LOCAL_DIR = ROOT / "outputs" / "development" / "s2_11_local_working" / \
    "adjudication_proposals_v3"
V3_LOCAL_PROPOSALS_REL = "proposals.jsonl"
V3_LOCAL_PACKAGE_REL = "decision_package.md"
V3_LOCAL_DIFF_REL = "v2_to_v3_semantic_diff.md"
V3_LOCAL_QUALITY_REL = "quality_report.md"

V2_PROPOSAL_SHA256 = \
    "9386642738e73ac2296edb709bd1183b072cacca328b3359762551d0e2b2e5ac"
PROPOSAL_SOURCE = "deepseek_offline_proposal_v3"


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


def _locate_in(text: str, value: str, lo: int, hi: int) -> list[int]:
    starts: list[int] = []
    start = lo
    while True:
        i = text.find(value, start, hi)
        if i < 0:
            break
        assert text[i:i + len(value)] == value, "byte-slice verification"
        starts.append(i)
        start = i + 1
    return starts


def _resolve_spec(text: str, value: str, occurrence: int | None,
                  lo: int, hi: int, where: str) -> tuple[int, int]:
    """Resolve ONE span from an exact value inside [lo, hi). Ambiguous
    auto-occurrence (no explicit occurrence and multiple hits) refuses."""
    starts = _locate_in(text, value, lo, hi)
    if not starts:
        raise BuildFail(f"{where}: span {value!r} not found in the clause")
    if occurrence is None:
        if len(starts) > 1:
            raise BuildFail(
                f"{where}: span {value!r} occurs {len(starts)} times in "
                "the clause; an explicit occurrence index is required "
                "(ambiguous auto-occurrence refused)")
        idx = starts[0]
    else:
        if occurrence < 0 or occurrence >= len(starts):
            raise BuildFail(
                f"{where}: occurrence {occurrence} out of range for "
                f"{value!r} ({len(starts)} hits)")
        idx = starts[occurrence]
    return idx, idx + len(value)


# ---------------------------------------------------------------------------
# Targeted v3 corrections (everything else is carried over from v2).
# Spec format: {"text": str, "conf": float,
#               "occurrence": int|None, "normalized": str|None}
# ---------------------------------------------------------------------------
def _spec(text: str, conf: float, occurrence: int | None = None,
          normalized: str | None = None) -> dict[str, Any]:
    return {"text": text, "conf": conf, "occurrence": occurrence,
            "normalized": normalized}


CORRECTIONS_V3: dict[str, dict[str, Any]] = {
    "SIM_card_scenario/r10/v1": {
        "clauses": [{
            "clause_text": "When the customer receives the SIM card, the "
                           "customer is responsable of activating the SIM "
                           "card",
            "modality": ("obligation", ["is responsable of"], 0.5),
            "actors": [(_spec("the customer", 0.9, occurrence=1),
                        "main-clause executor only; the condition-internal "
                        "customer stays inside the condition")],
            "actions": [(_spec("activating the SIM card", 0.85),
                         "exact gerund complement")],
            "conditions": [(_spec("When the customer receives the SIM card",
                                  0.85), "condition content")],
            "constraints": [], "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v3 correction: the actor is ONLY the main-clause 'the "
                  "customer' (explicit occurrence 1; id unique); the "
                  "condition-internal customer belongs to the condition "
                  "content; the actor-action mapping to 'activating the "
                  "SIM card' is established.",
        "needs_attention": True,
    },
    "emergencies_scenario/r4/v2": {
        "clauses": [{
            "clause_text": "If the doctor does not authorize skipping blood "
                           "analysis, the analysis test should happen before "
                           "the surgery.",
            "modality": ("obligation", ["should"], 0.7),
            "actors": [],
            "actions": [(_spec("happen", 0.8, normalized="happen before "
                                                       "the surgery"),
                         "exact raw action span; normalized value carries "
                         "the full semantic verb phrase")],
            "conditions": [(_spec("If the doctor does not authorize "
                                  "skipping blood analysis", 0.9),
                            "condition")],
            "constraints": [(_spec("before the surgery", 0.8),
                             "temporal constraint, overlap-free")],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v3 correction: action/constraint overlap eliminated - "
                  "the action is the exact raw span 'happen' (normalized "
                  "'happen before the surgery'), the temporal constraint "
                  "'before the surgery' is separate; overlap = 0.",
        "needs_attention": True,
    },
    "SIM_card_scenario/r8/v1": {
        "clauses": [{
            "clause_text": "The phone company can take longer than 30 days "
                           "in sending the SIM card.",
            "modality": ("permission", ["can"], 0.9),
            "actors": [(_spec("The phone company", 0.95),
                        "sole actor")],
            "actions": [(_spec("sending the SIM card", 0.8,
                               normalized="take longer than 30 days in "
                                          "sending the SIM card"),
                         "exact action span without the quantity "
                         "constraint")],
            "conditions": [],
            "constraints": [(_spec("longer than 30 days", 0.85),
                             "quantity/temporal constraint")],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v3 correction: 'longer than 30 days' is annotated as a "
                  "quantity/temporal constraint; the action is the exact "
                  "span 'sending the SIM card' (normalized full verb "
                  "phrase); actor-action mapping kept.",
        "needs_attention": False,
    },
    "blood_donation_scenario/r18/v2": {
        "clauses": [{
            "clause_text": "If a potential donor is rejected, they must be "
                           "immediately sent the reason for rejection",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [],
            "actions": [(_spec("sent the reason for rejection", 0.8,
                               normalized="be immediately sent the reason "
                                          "for rejection"),
                         "exact action span without the temporal "
                         "constraint")],
            "conditions": [(_spec("If a potential donor is rejected", 0.9),
                            "condition")],
            "constraints": [(_spec("immediately", 0.85),
                             "temporal constraint")],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v3 correction: 'immediately' is annotated as a temporal "
                  "constraint; the action is the exact span 'sent the "
                  "reason for rejection' (normalized full passive verb "
                  "phrase); passive executor stays absent (the rejected "
                  "donor is the recipient, never the actor).",
        "needs_attention": True,
    },
    "emergencies_scenario/r3/v1": {
        "clauses": [{
            "clause_text": "If the patient is over 65, a nurse must approve "
                           "discharge before the patient is discharged, and "
                           "approval must occur within 24 hours prior to "
                           "discharge. The rule is valid from 2024 to 2030.",
            "modality": ("obligation", ["must"], 0.95, 0),
            "actors": [(_spec("a nurse", 0.95), "sole actor")],
            "actions": [(_spec("approve discharge", 0.9),
                         "approval action")],
            "conditions": [(_spec("If the patient is over 65", 0.9),
                            "condition")],
            "constraints": [
                (_spec("before the patient is discharged", 0.85),
                 "temporal constraint"),
                (_spec("within 24 hours prior to discharge", 0.8),
                 "temporal constraint"),
                (_spec("valid from 2024 to 2030", 0.9),
                 "temporal-validity constraint (v3 addition)"),
            ],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v3 correction: the normative clause span is extended to "
                  "the full record and the temporal-validity constraint "
                  "'valid from 2024 to 2030' is annotated per the frozen "
                  "constraint definition; the second 'must' cue is handled "
                  "by the explicit occurrence 0; existing condition, "
                  "approval action and the two temporal constraints are "
                  "kept; no fake clause is created.",
        "needs_attention": True,
    },
    "emergencies_scenario/r3/v2": {
        "clauses": [{
            "clause_text": "If the patient is over 65 or has more than 5 "
                           "medications, a doctor must approve discharge "
                           "before the patient is discharged. The rule is "
                           "valid from 2025 to 2031.",
            "modality": ("obligation", ["must"], 0.95),
            "actors": [(_spec("a doctor", 0.95), "sole actor")],
            "actions": [(_spec("approve discharge", 0.9),
                         "approval action")],
            "conditions": [(_spec("If the patient is over 65 or has more "
                                  "than 5 medications", 0.9),
                            "condition")],
            "constraints": [
                (_spec("before the patient is discharged", 0.85),
                 "temporal constraint"),
                (_spec("valid from 2025 to 2031", 0.9),
                 "temporal-validity constraint (v3 addition)"),
            ],
            "exceptions": [],
        }],
        "order_relations": [],
        "reason": "v3 correction: the normative clause span is extended to "
                  "the full record and the temporal-validity constraint "
                  "'valid from 2025 to 2031' is annotated; existing "
                  "condition/action/constraint are kept.",
        "needs_attention": False,
    },
}

SHORT = {"actor": "act", "action": "actn", "condition": "cond",
         "constraint": "constr", "exception": "exc"}


def _span_id(sample_id: str, clause_idx: int, field: str,
             span_idx: int) -> str:
    safe = sample_id.replace("/", "_")
    return f"{safe}_c{clause_idx + 1:02d}_{SHORT[field]}_{span_idx}"


def _mod_ev_id(sample_id: str, clause_idx: int, ev_idx: int,
               start: int) -> str:
    safe = sample_id.replace("/", "_")
    return f"{safe}_c{clause_idx + 1:02d}_modev_{ev_idx}_{start}"


def _normalize_specs(specs: list[Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in specs:
        if isinstance(spec, tuple) and isinstance(spec[0], dict):
            spec = spec[0]  # (spec_dict, annotation_note) form
        if isinstance(spec, dict):
            out.append(dict(spec))
        elif isinstance(spec, tuple):
            text, conf = spec[0], spec[1]
            occurrence = spec[2] if len(spec) > 2 else None
            normalized = spec[3] if len(spec) > 3 else None
            out.append({"text": text, "conf": conf,
                        "occurrence": occurrence, "normalized": normalized})
        else:
            raise BuildFail(f"bad span spec: {spec!r}")
    return out


def _build_canonical(sample_id: str, text: str,
                     proposal: dict[str, Any]) -> dict[str, Any]:
    clauses_out: list[dict[str, Any]] = []
    aam: list[dict[str, str]] = []
    orders: list[dict[str, str]] = []
    for ci, clause_spec in enumerate(proposal["clauses"]):
        clause_text = clause_spec["clause_text"]
        locs = _locate_in(text, clause_text, 0, len(text))
        if not locs:
            raise BuildFail(
                f"{sample_id}: clause {ci} not found in source text")
        cstart, cend = locs[0], locs[0] + len(clause_text)
        modality_spec = clause_spec["modality"]
        label = modality_spec[0]
        evidence_specs = modality_spec[1]
        mod_conf = modality_spec[2]
        mod_occurrence = modality_spec[3] if len(modality_spec) > 3 else None
        if label not in MODALITY_LABELS:
            raise BuildFail(f"{sample_id}: bad modality label {label!r}")
        if isinstance(evidence_specs, str):
            evidence_specs = [evidence_specs]
        evidence: list[dict[str, Any]] = []
        for ei, ev_text in enumerate(evidence_specs):
            if isinstance(ev_text, (list, tuple)):
                ev_text, ev_occ = ev_text[0], ev_text[1]
            else:
                ev_occ = mod_occurrence if ei == 0 else None
            s, e = _resolve_spec(
                text, ev_text, ev_occ, cstart, cend,
                f"{sample_id} c{ci + 1} modality evidence")
            evidence.append({
                "id": _mod_ev_id(sample_id, ci, ei, s),
                "start": s, "end": e, "text": text[s:e],
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
            raw_specs = clause_spec.get(key) or []
            spans = []
            for si, spec in enumerate(_normalize_specs(raw_specs)):
                s, e = _resolve_spec(
                    text, spec["text"], spec.get("occurrence"),
                    cstart, cend,
                    f"{sample_id} c{ci + 1} {field}")
                span: dict[str, Any] = {
                    "id": _span_id(sample_id, ci, field, si),
                    "start": s, "end": e, "text": text[s:e],
                    "confidence": spec["conf"],
                }
                if spec.get("normalized") is not None:
                    span["normalized"] = spec["normalized"]
                spans.append(span)
            if spans:
                clause[field] = {"status": "present", "spans": spans}
            else:
                clause[field] = {"status": "absent", "spans": []}
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


def _resolve_ref(sample_id: str, clauses: list[dict[str, Any]],
                 clause_idx: int, ref: str) -> str:
    field, idx = ref.split("[")
    idx = int(idx.rstrip("]"))
    field = field[:-1] if field.endswith("s") else field
    spans = clauses[clause_idx].get(field, {}).get("spans", [])
    if idx >= len(spans):
        raise BuildFail(f"{sample_id}: bad order ref {ref!r}")
    return spans[idx]["id"]


def _merge_proposals() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for sid, proposal in PROPOSALS_V2.items():
        merged[sid] = proposal
    for sid, correction in CORRECTIONS_V3.items():
        merged[sid] = correction
    return merged


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
    import copy
    out = copy.deepcopy(payload)
    for clause in out.get("clauses", []):
        clause["clause_span"].pop("text", None)
        for ev in clause["modality"]["evidence"]:
            ev.pop("text", None)
        for field in ORDINARY_FIELDS:
            for span in clause[field]["spans"]:
                span.pop("text", None)
                # normalized is a derived semantic value that is a
                # contiguous source phrase; it stays in the LOCAL package
                # only (containment: no >=40-char source fragments in
                # committed assets)
                span.pop("normalized", None)
    return out


def _quality_counts(entries: dict[str, Any]) -> dict[str, int]:
    counts = {
        "exact_slice_failures": 0,
        "duplicate_span_ids": 0,
        "duplicate_clause_ids": 0,
        "ambiguous_auto_occurrences": 0,
        "invalid_or_missing_actor_action_mappings": 0,
        "invalid_order_relations": 0,
        "action_constraint_overlaps": 0,
        "modality_evidence_missing": 0,
        "unresolved_fields": 0,
    }
    for e in entries.values():
        seen: dict[str, str] = {}
        clause_ids: set[str] = set()
        for ci, clause in enumerate(e["canonical"]["clauses"]):
            cid = clause.get("clause_id")
            if cid in clause_ids:
                counts["duplicate_clause_ids"] += 1
            clause_ids.add(cid)
            if not clause["modality"]["evidence"]:
                counts["modality_evidence_missing"] += 1
            for ev in clause["modality"]["evidence"]:
                _track(seen, ev["id"], counts)
            for field in ORDINARY_FIELDS:
                spans = clause[field]["spans"]
                if clause[field]["status"] == "unresolved":
                    counts["unresolved_fields"] += 1
                for span in spans:
                    _track(seen, span["id"], counts)
                if field == "action":
                    for a in spans:
                        for co in clause["constraint"]["spans"]:
                            if a["start"] < co["end"] and \
                                    co["start"] < a["end"]:
                                counts["action_constraint_overlaps"] += 1
        # aam / orders checks are enforced by canonical v3 validation;
        # count invalid refs defensively here as well
        action_ids = {sid for s in seen
                      for sid in []} or set()
        all_ids = set(seen)
        for edge in e["canonical"].get("actor_action_map") or []:
            if edge["actor_span_id"] not in all_ids or \
                    edge["action_span_id"] not in all_ids:
                counts["invalid_or_missing_actor_action_mappings"] += 1
        for rel in e["canonical"].get("order_relations") or []:
            if rel["before_span_id"] not in all_ids or \
                    rel["after_span_id"] not in all_ids or \
                    rel["before_span_id"] == rel["after_span_id"]:
                counts["invalid_order_relations"] += 1
    return counts


def _track(seen: dict[str, str], sid: str,
           counts: dict[str, int]) -> None:
    if sid in seen:
        counts["duplicate_span_ids"] += 1
    else:
        seen[sid] = sid


def build() -> tuple[dict[str, Any], str]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    if len(membership["records"]) != 36:
        raise BuildFail("membership must have exactly 36 records")
    proposals = _merge_proposals()
    if set(proposals) != set(membership["records"]):
        raise BuildFail("proposal v3 coverage mismatch")

    full_entries: dict[str, Any] = {}
    local_lines: list[str] = []
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
            sample_id, rec, text, proposals[sample_id], g05["level"])
        full_entries[sample_id] = entry
        local_lines.append(json.dumps(entry, ensure_ascii=False))

    # canonical v3 validation over the LOCAL full payloads
    source_texts = {sid: _load_text(sid, membership["records"][sid])
                    for sid in sorted(membership["records"])}
    payloads = {sid: {"canonical": e["canonical"]}
                for sid, e in full_entries.items()}
    result = validate(payloads, source_texts, allow_unresolved=True,
                      expected_ids=sorted(membership["records"]))
    if not result["valid"]:
        raise BuildFail("canonical v3 validation failed: " +
                        "; ".join(result["problems"][:30]))
    counts = _quality_counts(full_entries)
    if any(counts[k] != 0 for k in (
            "exact_slice_failures", "duplicate_span_ids",
            "duplicate_clause_ids", "ambiguous_auto_occurrences",
            "invalid_or_missing_actor_action_mappings",
            "invalid_order_relations", "action_constraint_overlaps",
            "modality_evidence_missing", "unresolved_fields")):
        raise BuildFail(f"acceptance counts violated: {counts}")

    local_bytes = ("\n".join(local_lines) + "\n").encode("utf-8")
    local_path = V3_LOCAL_DIR / V3_LOCAL_PROPOSALS_REL
    _write(local_path, local_bytes)
    _write(V3_LOCAL_DIR / V3_LOCAL_PACKAGE_REL,
           _render_package(membership, full_entries).encode("utf-8"))
    _write(V3_LOCAL_DIR / V3_LOCAL_DIFF_REL,
           _render_v2_v3_diff(membership, full_entries).encode("utf-8"))
    _write(V3_LOCAL_DIR / V3_LOCAL_QUALITY_REL,
           _render_quality(membership, full_entries, counts,
                           local_bytes).encode("utf-8"))

    entries_committed: dict[str, Any] = {}
    for sample_id, entry in full_entries.items():
        e = {k: v for k, v in entry.items() if k != "canonical"}
        e["canonical"] = _strip_text(entry["canonical"])
        entries_committed[sample_id] = e

    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for entry in full_entries.values():
        rc = entry["record_confidence"]
        confidence_counts["high" if rc >= 0.8 else
                          "medium" if rc >= 0.6 else "low"] += 1

    v2_report_sha = _sha256_bytes(
        (ROOT / PROPOSAL_REPORT_V2_REL).read_bytes()) \
        if (ROOT / PROPOSAL_REPORT_V2_REL).is_file() else None
    report = {
        "schema_version": "s2_11_proposal_report@3.0.0",
        "proposal_source": PROPOSAL_SOURCE,
        "membership": MEMBERSHIP_REL,
        "proposal_count": len(entries_committed),
        "coverage": "36/36",
        "proposal_file": str(local_path.relative_to(ROOT)),
        "proposal_file_sha256": _sha256_bytes(local_bytes),
        "supersedes_v2": {
            "proposal_file_sha256": V2_PROPOSAL_SHA256,
            "proposal_report_v2": PROPOSAL_REPORT_V2_REL,
            "proposal_report_v2_sha256": v2_report_sha,
            "status": "superseded_pending_targeted_correction_"
                      "do_not_approve",
        },
        "confidence_counts": confidence_counts,
        "needs_attention_ids": sorted(
            sid for sid, e in full_entries.items() if e["needs_attention"]),
        "acceptance_counts": counts,
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
    return report, counts


def _render_package(membership: dict[str, Any],
                    entries: dict[str, Any]) -> str:
    lines = ["# S2.11 Offline AI Adjudication Proposals v3 (decision "
             "package)",
             "",
             "**LOCAL-ONLY** - never committed (raw third-party text).",
             "**proposal source**: `deepseek_offline_proposal_v3` "
             "(human_approved=false, gold=false)",
             "**supersedes v2** (SHA `9386642738e73ac2296edb709bd1183b072cac"
             "ca328b3359762551d0e2b2e5ac`; do NOT approve v2)",
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
                parts = []
                for span in entry["spans"]:
                    norm = (f" (normalized: {span['normalized']})"
                            if span.get("normalized") else "")
                    parts.append(f"[{span['start']}:{span['end']}] "
                                 f"`{span['text']}`{norm} "
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


def _render_v2_v3_diff(membership: dict[str, Any],
                       entries: dict[str, Any]) -> str:
    lines = ["# S2.11 proposal v2 -> v3 semantic diff (LOCAL-ONLY)", ""]
    v2_path = ROOT / V2_LOCAL_REL
    if not v2_path.is_file():
        lines.append("v2 local proposals file not found; diff unavailable.")
        return "\n".join(lines) + "\n"
    v2 = {json.loads(ln)["sample_id"]: json.loads(ln)
          for ln in v2_path.read_text(encoding="utf-8").splitlines() if ln}
    lines.append(f"- v2 proposal file SHA-256: "
                 f"`{_sha256_bytes(v2_path.read_bytes())}`")
    lines.append("")
    lines.append("## Targeted corrections (evidence-based)")
    lines.append("")
    for sid in sorted(entries):
        e3 = entries[sid]
        e2 = v2.get(sid)
        lines.append(f"### {sid}")
        lines.append("")
        if e2 is None:
            lines.append("- v2: MISSING; v3: added")
            lines.append("")
            continue
        changes: list[str] = []
        c2 = e2["canonical"]["clauses"][0]
        c3 = e3["canonical"]["clauses"][0]
        a2 = c2.get("actor", {}).get("spans", [])
        a3 = c3.get("actor", {}).get("spans", [])
        if len(a2) != len(a3) or any(
                (s2["start"], s2["end"]) != (s3["start"], s3["end"])
                for s2, s3 in zip(a2, a3)):
            changes.append("actor spans changed: v2 " +
                           str([(s["start"], s["end"]) for s in a2]) +
                           " -> v3 " +
                           str([(s["start"], s["end"]) for s in a3]))
        act2 = c2.get("action", {}).get("spans", [])
        act3 = c3.get("action", {}).get("spans", [])
        if act2 and act3 and (act2[0]["text"], act2[0].get("end")) != \
                (act3[0]["text"], act3[0].get("end")):
            changes.append(f"action span: v2 `{act2[0]['text']}` -> v3 "
                           f"`{act3[0]['text']}`")
        co2 = [s["text"] for s in c2.get("constraint", {}).get("spans", [])]
        co3 = [s["text"] for s in c3.get("constraint", {}).get("spans", [])]
        if co2 != co3:
            changes.append(f"constraints: v2 {co2} -> v3 {co3}")
        aam2 = len(e2["canonical"].get("actor_action_map") or [])
        aam3 = len(e3["canonical"].get("actor_action_map") or [])
        if aam2 != aam3:
            changes.append(f"actor_action_map edges: {aam2} -> {aam3}")
        if c2.get("clause_span", {}).get("end") != \
                c3.get("clause_span", {}).get("end"):
            changes.append("clause span extended to the full record "
                           "(temporal-validity constraint)")
        if e3["needs_attention"] != e2.get("needs_attention"):
            changes.append(f"needs_attention: v2 {e2.get('needs_attention')}"
                           f" -> v3 {e3['needs_attention']}")
        if changes:
            for ch in changes:
                lines.append(f"- {ch}")
        else:
            lines.append("- no evidence-based change (mechanical "
                         "carryover, regression-checked)")
        lines.append("")
    return "\n".join(lines) + "\n"


def _render_quality(membership: dict[str, Any],
                    entries: dict[str, Any],
                    counts: dict[str, int],
                    local_bytes: bytes) -> str:
    na_ids = sorted(s for s, e in entries.items() if e["needs_attention"])
    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for e in entries.values():
        rc = e["record_confidence"]
        confidence_counts["high" if rc >= 0.8 else
                          "medium" if rc >= 0.6 else "low"] += 1
    lines = [
        "# S2.11 proposal v3 quality report (LOCAL-ONLY)", "",
        f"- proposal file SHA-256: `{_sha256_bytes(local_bytes)}`",
        f"- coverage: {len(entries)}/36",
        f"- exact slice failures: {counts['exact_slice_failures']}",
        f"- duplicate span IDs: {counts['duplicate_span_ids']}",
        f"- duplicate clause IDs: {counts['duplicate_clause_ids']}",
        f"- ambiguous auto-occurrences: "
        f"{counts['ambiguous_auto_occurrences']}",
        f"- invalid/missing actor-action mappings: "
        f"{counts['invalid_or_missing_actor_action_mappings']}",
        f"- invalid order relations: {counts['invalid_order_relations']}",
        f"- action/constraint overlaps: "
        f"{counts['action_constraint_overlaps']}",
        f"- modality evidence missing: {counts['modality_evidence_missing']}",
        f"- unresolved fields: {counts['unresolved_fields']}",
        f"- confidence buckets: {confidence_counts}",
        f"- needs_attention ids ({len(na_ids)}):",
    ]
    for sid in na_ids:
        lines.append(f"  - {sid}")
    lines.append("")
    lines.append("All spans are byte-verified against the hash-bound source "
                 "text; committed artifacts carry coordinates only.")
    return "\n".join(lines) + "\n"


def main() -> int:
    try:
        report, counts = build()
    except BuildFail as exc:
        print(f"PROPOSAL V3 BUILD FAILED (fail-closed): {exc}",
              file=sys.stderr)
        return 2
    data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    try:
        _write(ROOT / PROPOSAL_REPORT_V3_REL, data)
    except BuildFail as exc:
        print(f"PROPOSAL V3 BUILD FAILED (refusing overwrite): {exc}",
              file=sys.stderr)
        return 2
    print(f"proposal v3 report written: {PROPOSAL_REPORT_V3_REL} "
          f"({report['proposal_count']} proposals, acceptance={counts})")
    print(f"proposal file SHA-256: {report['proposal_file_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

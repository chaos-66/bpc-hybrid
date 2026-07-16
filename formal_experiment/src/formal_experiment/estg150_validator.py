"""Pure validators for the EStG-150 v2 human_correction workflow (Layer E).

Three orthogonal layers:

1. Per-record structural checks
   `validate_record_format(record, ctx)` — only the structure of a single
   record (span text vs. approved_text_en, span inside clause_span, IDs
   unique within a clause, modality value, etc.). Does NOT look at
   review_state and does NOT look at any other record. This is the
   **format gate** that a single record must clear to be eligible for
   *either* `reviewed` or `adjudicated`.

2. Per-record eligibility for the human review states
   `validate_record_for_review(record, ctx)` — runs the per-record
   structural checks, then evaluates whether the current record is
   eligible to be marked `reviewed` or `adjudicated`. The eligibility
   rule is intentionally **per-record only**: it does NOT look at the
   other 149 records. This is what makes the first record markable.

3. Global aggregator (workflow readiness)
   `validate_global(path)` — reads the full file, runs per-record
   structural checks across all 150 records, and then reports
   `format_valid`, `review_ready` (all 150 reviewed/adjudicated), and
   `freeze_ready` (all 150 adjudicated). This is what `audit_project.py`
   and the CLI `scripts/validate_human_correction.py` consume.

The per-record gates are pure functions on a single record. They never
touch the file system and never invoke a subprocess. The global
aggregator is the only function that reads a file; it can be invoked
**after** a save to produce the status bar report.

Layer E file format expectations (matching
`scripts/build_estg150_review_layers.py`):
  - `schema_version == "estg_150_review_workflow@1.0.0"`
  - `dataset.name == "independently_reconstructed_estg_150"`
  - `dataset.version == "v1"`
  - `dataset.membership_count == 150`
  - 150 records with unique `sample_id` and `legacy_record_id`
  - per-record `decisions.translation` ∈ {unreviewed, accepted, edited,
    rejected, needs_adjudication}
  - per-record `decisions.{modality,actor,action,condition,constraint,exception}`
    in the same enum
  - per-record `review_state.status` ∈
    {needs_review, in_progress, reviewed, adjudicated}
  - per-record `raw_text_de_sha256`, `candidate_text_en_sha256` match
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
SIX_ELEMENT_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")

DECISION_OK_FOR_REVIEW = ("accepted", "edited", "rejected", "needs_adjudication")
DECISION_OK_FOR_FREEZE = ("accepted", "edited", "rejected")

REVIEW_OK_FOR_REVIEW_READY = ("reviewed", "adjudicated")
REVIEW_OK_FOR_FREEZE_READY = ("adjudicated",)

REVIEW_STATES = ("needs_review", "in_progress", "reviewed", "adjudicated")
DECISION_STATES = ("unreviewed", "accepted", "edited", "rejected", "needs_adjudication")
MODALITY_VALUES = ("obligation", "prohibition", "permission", "definition")

EXPECTED_SCHEMA_VERSION = "estg_150_review_workflow@1.0.0"
EXPECTED_DATASET_NAME = "independently_reconstructed_estg_150"
EXPECTED_DATASET_VERSION = "v1"
EXPECTED_MEMBERSHIP_COUNT = 150


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def sha256_text(s: str | None) -> str | None:
    if s is None:
        return None
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Per-record structural checks
# ---------------------------------------------------------------------------

def validate_record_format(record: dict, ctx: dict | None = None) -> list[str]:
    """Per-record structural errors for a single record. Does NOT look
    at any other record. Does NOT look at review_state. Returns a list
    of human-readable error strings (empty list ⇒ format-valid for
    this record)."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record is not an object"]
    sid = record.get("sample_id")
    lid = record.get("legacy_record_id")
    if not isinstance(sid, str) or not sid.startswith("estg_"):
        errors.append(f"sample_id must be estg_NNNNNN, got {sid!r}")
    if not isinstance(lid, int):
        errors.append("legacy_record_id must be int")
    elif isinstance(sid, str) and sid.startswith("estg_"):
        expected = f"estg_{lid:06d}"
        if sid != expected:
            errors.append(f"sample_id {sid!r} != estg_{lid:06d}")
    if sha256_text(record.get("raw_text_de") or "") != record.get("raw_text_de_sha256"):
        errors.append("raw_text_de_sha256 mismatch")
    if sha256_text(record.get("candidate_text_en") or "") != record.get("candidate_text_en_sha256"):
        errors.append("candidate_text_en_sha256 mismatch")
    decisions = record.get("decisions") or {}
    for k, v in decisions.items():
        if v not in DECISION_STATES:
            errors.append(f"decisions.{k} invalid value: {v!r}")
    rs = record.get("review_state") or {}
    if rs.get("status") not in REVIEW_STATES:
        errors.append(f"review_state.status invalid: {rs.get('status')!r}")
    # Span checks
    ap = record.get("approved_text_en")
    for ci, c in enumerate(record.get("human_correction", {}).get("clauses", [])):
        cs = c.get("clause_span") or {}
        cs_start = cs.get("start", 0)
        cs_end = cs.get("end", 0)
        if ap is not None and cs:
            if cs.get("text") != ap[cs_start:cs_end]:
                errors.append(
                    f"clauses[{ci}].clause_span text != approved_text_en[start:end]"
                )
        for sf in SPAN_FIELDS:
            ids_seen: set[str] = set()
            for si, s in enumerate(c.get(sf, [])):
                sid_s = s.get("id")
                if sid_s in ids_seen:
                    errors.append(
                        f"clause {ci} {sf}[{si}].id {sid_s!r} is duplicate"
                    )
                ids_seen.add(sid_s)
                if ap is not None:
                    txt = s.get("text", "")
                    if txt != ap[s.get("start", 0):s.get("end", 0)]:
                        errors.append(
                            f"clause {ci} {sf}[{si}] text != approved_text_en[start:end]"
                        )
                    span_s = s.get("start", 0)
                    span_e = s.get("end", 0)
                    if span_s < cs_start or span_e > cs_end:
                        errors.append(
                            f"clause {ci} {sf}[{si}] span [{span_s},{span_e}) "
                            f"lies outside clause_span [{cs_start},{cs_end})"
                        )
        actor_ids = {a["id"] for a in c.get("actors", [])}
        action_ids = {a["id"] for a in c.get("actions", [])}
        for ei, e in enumerate(c.get("actor_action_map", [])):
            if e.get("actor_id") is not None and e["actor_id"] not in actor_ids:
                errors.append(
                    f"clause {ci} actor_action_map[{ei}].actor_id "
                    f"{e.get('actor_id')!r} unknown"
                )
            if e.get("action_id") not in action_ids:
                errors.append(
                    f"clause {ci} actor_action_map[{ei}].action_id "
                    f"{e.get('action_id')!r} unknown"
                )
        for oi, o in enumerate(c.get("order_relations", [])):
            if o.get("before_action_id") not in action_ids:
                errors.append(
                    f"clause {ci} order_relations[{oi}].before_action_id "
                    f"{o.get('before_action_id')!r} unknown"
                )
            if o.get("after_action_id") not in action_ids:
                errors.append(
                    f"clause {ci} order_relations[{oi}].after_action_id "
                    f"{o.get('after_action_id')!r} unknown"
                )
        mod = c.get("modality") or {}
        if not isinstance(mod, dict):
            errors.append(f"clause {ci} modality must be an object")
        else:
            v = mod.get("value")
            if v is not None and v not in MODALITY_VALUES:
                errors.append(
                    f"clause {ci} modality.value {v!r} not in 4-class set"
                )
    return errors


# ---------------------------------------------------------------------------
# Per-record eligibility for `reviewed` / `adjudicated`
# ---------------------------------------------------------------------------

def validate_record_for_review(record: dict, ctx: dict | None = None) -> dict[str, Any]:
    """Per-record eligibility for marking `reviewed` and `adjudicated`.

    This function intentionally only inspects `record` and ignores the
    other 149 records. The first record of a brand-new workflow can
    therefore be marked `reviewed` as soon as its own per-record
    structural checks pass, without waiting for the other 149 records.

    Returns a dict with:
      - `format_valid` (bool): no per-record structural errors
      - `format_errors` (list[str]): the structural errors
      - `eligible_for_reviewed` (bool): record can be marked `reviewed`
        (translation decided, approved_text_en filled or translation
        rejected, all 6 element decisions set, status is
        needs_review / in_progress)
      - `eligible_for_adjudicated` (bool): record can be marked
        `adjudicated` (status == reviewed, all 7 decisions in
        {accepted, edited, rejected}, per-clause modality decisions in
        the same set)
      - `errors` (list[str]): human-readable explanations
    """
    format_errors = validate_record_format(record, ctx)
    format_valid = len(format_errors) == 0

    errors: list[str] = []
    eligible_reviewed = True
    eligible_adjudicated = True

    if not format_valid:
        eligible_reviewed = False
        eligible_adjudicated = False
        errors.append("record has structural format errors")

    decisions = record.get("decisions") or {}
    rs = (record.get("review_state") or {}).get("status", "needs_review")
    ap = record.get("approved_text_en")

    # --- eligibility for reviewed ---
    if rs in ("reviewed", "adjudicated"):
        eligible_reviewed = False
        errors.append(
            f"review_state.status already {rs!r}; cannot mark reviewed again"
        )
    if decisions.get("translation") == "unreviewed":
        eligible_reviewed = False
        errors.append("decisions.translation is unreviewed")
    if not ap and decisions.get("translation") != "rejected":
        eligible_reviewed = False
        errors.append(
            "approved_text_en missing and translation decision is not rejected"
        )
    for fld in SIX_ELEMENT_FIELDS:
        if decisions.get(fld) == "unreviewed":
            eligible_reviewed = False
            errors.append(f"decisions.{fld} is unreviewed")

    # --- eligibility for adjudicated ---
    if rs == "adjudicated":
        eligible_adjudicated = False
        errors.append("review_state.status already adjudicated")
    elif rs != "reviewed":
        eligible_adjudicated = False
        errors.append(
            f"review_state.status is {rs!r}; must be 'reviewed' to adjudicate"
        )
    for k, v in decisions.items():
        if v not in DECISION_OK_FOR_FREEZE:
            eligible_adjudicated = False
            errors.append(
                f"decisions.{k} = {v!r} not in {DECISION_OK_FOR_FREEZE}"
            )
    for ci, c in enumerate(record.get("human_correction", {}).get("clauses", [])):
        mod = c.get("modality") or {}
        if mod.get("decision") not in DECISION_OK_FOR_FREEZE:
            eligible_adjudicated = False
            errors.append(
                f"clause {ci} modality.decision = {mod.get('decision')!r} "
                f"not in {DECISION_OK_FOR_FREEZE}"
            )
        for sf in SPAN_FIELDS:
            for si, s in enumerate(c.get(sf, [])):
                d = s.get("decision")
                if d not in DECISION_OK_FOR_FREEZE:
                    eligible_adjudicated = False
                    errors.append(
                        f"clause {ci} {sf}[{si}].decision = {d!r} "
                        f"not in {DECISION_OK_FOR_FREEZE}"
                    )

    return {
        "format_valid": format_valid,
        "format_errors": format_errors,
        "eligible_for_reviewed": eligible_reviewed,
        "eligible_for_adjudicated": eligible_adjudicated,
        "errors": errors,
        "review_state_status": rs,
    }


# ---------------------------------------------------------------------------
# Global aggregator (file-level)
# ---------------------------------------------------------------------------

def _schema_errors(doc: dict) -> list[tuple[Any, str]]:
    errors: list[tuple[Any, str]] = []
    if not isinstance(doc, dict):
        return [(None, "top-level must be an object")]
    if doc.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        errors.append((
            None,
            f"schema_version must be {EXPECTED_SCHEMA_VERSION}, got "
            f"{doc.get('schema_version')!r}",
        ))
    ds = doc.get("dataset", {})
    if ds.get("name") != EXPECTED_DATASET_NAME:
        errors.append((None, f"dataset.name must be {EXPECTED_DATASET_NAME}"))
    if ds.get("version") != EXPECTED_DATASET_VERSION:
        errors.append((None, f"dataset.version must be {EXPECTED_DATASET_VERSION}"))
    if ds.get("membership_count") != EXPECTED_MEMBERSHIP_COUNT:
        errors.append((
            None,
            f"dataset.membership_count must be {EXPECTED_MEMBERSHIP_COUNT}, "
            f"got {ds.get('membership_count')!r}",
        ))
    records = doc.get("records", [])
    if not isinstance(records, list):
        errors.append((None, "records must be a list"))
        return errors
    if len(records) != EXPECTED_MEMBERSHIP_COUNT:
        errors.append((
            None,
            f"records must have {EXPECTED_MEMBERSHIP_COUNT} items, "
            f"got {len(records)}",
        ))
    seen_sample: set[str] = set()
    seen_legacy: set[int] = set()
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            errors.append((i, "record is not an object"))
            continue
        sid = r.get("sample_id")
        if not isinstance(sid, str) or not sid.startswith("estg_"):
            errors.append((i, f"sample_id must be estg_NNNNNN, got {sid!r}"))
        elif sid in seen_sample:
            errors.append((i, f"duplicate sample_id: {sid}"))
        else:
            seen_sample.add(sid)
        lid = r.get("legacy_record_id")
        if not isinstance(lid, int):
            errors.append((i, "legacy_record_id must be int"))
        elif lid in seen_legacy:
            errors.append((i, f"duplicate legacy_record_id: {lid}"))
        else:
            seen_legacy.add(lid)
        if isinstance(sid, str) and isinstance(lid, int):
            expected = f"estg_{lid:06d}"
            if sid != expected:
                errors.append((i, f"sample_id {sid!r} != estg_{lid:06d}"))
    return errors


def _membership_errors(doc: dict, hashes: dict) -> list[tuple[Any, str]]:
    """Fail-closed membership identity check.

    Event 23: never raise an uncaught exception. A malformed hashes
    dict (missing ``selected_membership``, missing payload, missing
    sorted_legacy_record_ids) MUST surface as a structural error so
    the strict validator can report ``format_valid=False`` and the
    status module can report ``membership_ok=False``. The validator
    is the single source of truth; it must never let a malformed
    membership JSON crash the audit.
    """
    errors: list[tuple[Any, str]] = []
    if not isinstance(hashes, dict):
        return [(None, f"membership hashes file top-level must be an object, got {type(hashes).__name__}")]
    sel = hashes.get("selected_membership")
    if not isinstance(sel, dict):
        return [(None, "membership hashes file missing selected_membership object")]
    expected_payload = sel.get("membership_payload_sha256")
    if not isinstance(expected_payload, str):
        return [(None, "selected_membership.membership_payload_sha256 missing or not a string")]
    actual_payload = (doc.get("dataset") or {}).get("membership_payload_sha256")
    if actual_payload is not None and actual_payload != expected_payload:
        errors.append((None, "membership_payload_sha256 mismatch"))
    expected_ids_field = sel.get("sorted_legacy_record_ids")
    if not isinstance(expected_ids_field, list):
        return errors + [(None, "selected_membership.sorted_legacy_record_ids missing or not a list")]
    expected_ids = sorted(
        x for x in expected_ids_field if isinstance(x, int) and not isinstance(x, bool)
    )
    actual_ids = sorted(
        r.get("legacy_record_id") for r in doc.get("records", [])
        if isinstance(r, dict) and isinstance(r.get("legacy_record_id"), int)
        and not isinstance(r.get("legacy_record_id"), bool)
    )
    if expected_ids != actual_ids:
        errors.append((None, "membership identity broken: sorted legacy_record_ids differ"))
    return errors


def _resolve_hashes_path(human_correction_path: Path) -> Path:
    """Locate the membership hashes file relative to a human_correction
    file path. Tries the production path first, then a 1-level fallback."""
    p = human_correction_path.parent.parent.parent / "estg" / "estg_150_membership_hashes.json"
    if p.exists():
        return p
    return human_correction_path.parent.parent / "estg" / "estg_150_membership_hashes.json"


def validate_doc_dict(
    doc: dict[str, Any],
    hashes_path: Path,
) -> dict[str, Any]:
    """Run the global validator against an in-memory doc. Pure
    function: no file reads of the human_correction file. Only the
    membership hashes file is read. The caller is responsible for
    having the doc in memory (e.g. loaded by the service).

    `hashes_path` is the path to ``estg_150_membership_hashes.json``.
    It is read once per call; the caller may pass a tmp-path copy
    for fully isolated tests.

    The returned dict has the exact same shape as ``validate_global``
    except ``path`` is set to the string ``"<in-memory>"`` (since no
    on-disk file was read).

    Event 23: a missing or unparseable hashes file is treated as a
    structural error (format_valid=False) rather than an uncaught
    exception. The function never raises for I/O or JSON issues.
    """
    errors: list[tuple[Any, str]] = []
    try:
        hashes = json.loads(Path(hashes_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {
            "path": "<in-memory>",
            "format_valid": False,
            "review_ready": False,
            "freeze_ready": False,
            "n_records": 0,
            "n_approved_en": 0,
            "n_translation_unreviewed": 0,
            "n_field_decisions_total": 0,
            "n_field_decisions_unreviewed": 0,
            "n_field_decisions_resolved": 0,
            "n_records_incomplete": 0,
            "n_records_fully_decided": 0,
            "n_reviewed": 0,
            "n_adjudicated": 0,
            "review_state_counts": {},
            "format_errors": [[None, f"could not load membership hashes file: {exc!r}"]],
            "review_blockers": [],
            "freeze_blockers": [],
        }

    errors.extend(_schema_errors(doc))
    errors.extend(_membership_errors(doc, hashes))

    review_blockers: list[tuple[Any, str]] = []
    freeze_blockers: list[tuple[Any, str]] = []

    n_records = 0
    n_approved_en = 0
    n_translation_unreviewed = 0
    n_field_decisions_unreviewed = 0
    n_field_decisions_total = 0
    n_field_decisions_resolved = 0
    n_records_incomplete = 0  # any decision is still unreviewed
    n_records_fully_decided = 0
    n_reviewed = 0
    n_adjudicated = 0
    review_state_counts = {"needs_review": 0, "in_progress": 0, "reviewed": 0, "adjudicated": 0}

    records = doc.get("records", [])
    if not isinstance(records, list):
        records = []

    for idx, r in enumerate(records):
        if not isinstance(r, dict):
            continue
        n_records += 1
        if r.get("approved_text_en"):
            n_approved_en += 1
        decisions = r.get("decisions") or {}
        if decisions.get("translation") == "unreviewed":
            n_translation_unreviewed += 1
        any_unreviewed = False
        for k in SIX_ELEMENT_FIELDS:
            v = decisions.get(k)
            n_field_decisions_total += 1
            if v == "unreviewed":
                n_field_decisions_unreviewed += 1
                any_unreviewed = True
            elif v in DECISION_OK_FOR_REVIEW:
                n_field_decisions_resolved += 1
        if decisions.get("translation") == "unreviewed":
            any_unreviewed = True
        if any_unreviewed:
            n_records_incomplete += 1
        else:
            n_records_fully_decided += 1
        rs = (r.get("review_state") or {}).get("status", "needs_review")
        review_state_counts[rs] = review_state_counts.get(rs, 0) + 1
        if rs == "reviewed":
            n_reviewed += 1
        if rs == "adjudicated":
            n_adjudicated += 1

        # per-record structural errors
        per_rec_errors = validate_record_format(r, {"global": True})
        errors.extend([(idx, e) for e in per_rec_errors])

        # review readiness (per-record)
        if not r.get("approved_text_en") and decisions.get("translation") != "rejected":
            review_blockers.append((idx, "approved_text_en missing and translation not rejected"))
        if rs not in REVIEW_OK_FOR_REVIEW_READY:
            review_blockers.append((
                idx, f"review_state.status {rs!r} not in {REVIEW_OK_FOR_REVIEW_READY}"
            ))
        for k, v in decisions.items():
            if v not in DECISION_OK_FOR_REVIEW:
                review_blockers.append((
                    idx, f"decisions.{k} = {v!r} not in {DECISION_OK_FOR_REVIEW}"
                ))

        # freeze readiness (per-record)
        if rs not in REVIEW_OK_FOR_FREEZE_READY:
            freeze_blockers.append((
                idx, f"review_state.status {rs!r} != adjudicated"
            ))
        for k, v in decisions.items():
            if v not in DECISION_OK_FOR_FREEZE:
                freeze_blockers.append((
                    idx, f"decisions.{k} = {v!r} not in {DECISION_OK_FOR_FREEZE}"
                ))
        for ci, c in enumerate(r.get("human_correction", {}).get("clauses", [])):
            mod = c.get("modality") or {}
            if mod.get("decision") not in DECISION_OK_FOR_FREEZE:
                freeze_blockers.append((
                    idx, f"clause {ci} modality.decision = {mod.get('decision')!r}"
                ))
            for sf in SPAN_FIELDS:
                for si, s in enumerate(c.get(sf, [])):
                    d = s.get("decision")
                    if d not in DECISION_OK_FOR_FREEZE:
                        freeze_blockers.append((
                            idx,
                            f"clause {ci} {sf}[{si}].decision = {d!r}",
                        ))

    format_valid = len(errors) == 0
    review_ready = format_valid and len(review_blockers) == 0
    freeze_ready = review_ready and len(freeze_blockers) == 0

    return {
        "path": "<in-memory>",
        "format_valid": format_valid,
        "review_ready": review_ready,
        "freeze_ready": freeze_ready,
        "n_records": n_records,
        "n_approved_en": n_approved_en,
        "n_translation_unreviewed": n_translation_unreviewed,
        # field-level counters: 6 element fields × 150 records = 900 max
        "n_field_decisions_total": n_field_decisions_total,
        "n_field_decisions_unreviewed": n_field_decisions_unreviewed,
        "n_field_decisions_resolved": n_field_decisions_resolved,
        # record-level counter
        "n_records_incomplete": n_records_incomplete,
        "n_records_fully_decided": n_records_fully_decided,
        # review-state counters
        "n_reviewed": n_reviewed,
        "n_adjudicated": n_adjudicated,
        "review_state_counts": review_state_counts,
        "format_errors": [list(e) for e in errors],
        "review_blockers": [list(e) for e in review_blockers],
        "freeze_blockers": [list(e) for e in freeze_blockers],
    }


def validate_global(path: Path) -> dict[str, Any]:
    """Read the human_correction file and produce the full global
    validator report. This is the only validator that reads the
    human_correction file from disk; per-record eligibility is a
    pure function on a single record (see `validate_record_for_review`),
    and the in-memory version is `validate_doc_dict`.
    """
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    hashes_path = _resolve_hashes_path(path)
    report = validate_doc_dict(doc, hashes_path)
    # Override the in-memory placeholder path with the actual file path
    report["path"] = str(path)
    return report


__all__ = [
    "SPAN_FIELDS",
    "SIX_ELEMENT_FIELDS",
    "DECISION_OK_FOR_REVIEW",
    "DECISION_OK_FOR_FREEZE",
    "REVIEW_OK_FOR_REVIEW_READY",
    "REVIEW_OK_FOR_FREEZE_READY",
    "REVIEW_STATES",
    "DECISION_STATES",
    "MODALITY_VALUES",
    "EXPECTED_SCHEMA_VERSION",
    "EXPECTED_DATASET_NAME",
    "EXPECTED_DATASET_VERSION",
    "EXPECTED_MEMBERSHIP_COUNT",
    "sha256_text",
    "validate_record_format",
    "validate_record_for_review",
    "validate_doc_dict",
    "validate_global",
]

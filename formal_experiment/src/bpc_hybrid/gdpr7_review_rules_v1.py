# -*- coding: utf-8 -*-
"""Shared validation rules for the GDPR7 six-element human-review workflow (v1).

This module is the single shared source of truth for the *editing* layer of the
GDPR7 six-element review workflow (schema
``gdpr7_six_element_review_editable@1.0.0``), which sits on top of the frozen
blank surface (schema ``gdpr7_six_element_review_surface@1.0.0``,
``data/development/human_review/gdpr7_six_element_review_blank_v1.json``).
It is imported by:

* ``scripts/build_gdpr7_review_editable_v1.py`` (build the editable copy);
* ``scripts/gdpr7_review_tool_v1.py`` (interactive human-adjudication tool);
* ``scripts/validate_gdpr7_review_filled_v1.py`` (full fill validator);
* ``scripts/import_gdpr7_review_decisions_v1.py`` (explicit-decision import);
* ``scripts/verify_gdpr7_review_freeze_v1.py`` (freeze-closure verifier);
* ``tests/test_gdpr7_review_workflow_v1.py``.

Policy (hard boundaries, mirrored from the workflow guide
``data/development/human_review/GDPR7_SIX_ELEMENT_REVIEW_WORKFLOW_V1.md``):

* decision values are exactly ``accepted`` / ``edited`` / ``rejected`` (there is
  intentionally NO ``needs_adjudication``); ``edited`` REQUIRES a non-empty
  ``edited_value``; ``accepted`` / ``rejected`` REQUIRE ``edited_value is None``;
* modality ``edited_value`` must be one of the four controlled labels
  (definition / obligation / permission / prohibition);
* the five text fields (actor / action / condition / constraint / exception)
  must carry ``edited_value`` that is a VERBATIM CONTIGUOUS SUBSTRING of the
  sentence text (same case, same punctuation), so later span back-reference and
  Oracle consistency checks keep working;
* an ``accepted`` decision accepts whatever the candidate carries — including
  ``null`` (accepting "no such element"); a non-empty candidate that the human
  decides is not in the sentence is expressed as ``rejected``; nothing is ever
  fabricated;
* ``review_state`` is ``unreviewed`` until all six fields of the sentence are
  decided and legal, at which point it may become ``reviewed``; a
  ``reviewed`` state with any undecided or illegal field is an error;
* nothing in this module ever writes a decision or reads a real LLM/network;
  it only validates, explains, counts and (for the tool/importer) applies
  decisions that were explicitly supplied by a human reviewer.

JSON serialization used by every writer in this workflow is
``json.dumps(doc, ensure_ascii=False, indent=2) + "\\n"`` written as UTF-8 bytes
(LF line endings, single trailing newline) — see :func:`doc_json_bytes` /
:func:`write_doc_json` / :func:`atomic_save_json`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Repository / file location constants
# ---------------------------------------------------------------------------

# src/bpc_hybrid/<this file> -> formal_experiment/
ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BLANK_PATH = (
    ROOT / "data/development/human_review" / "gdpr7_six_element_review_blank_v1.json"
)
DEFAULT_EDITABLE_PATH = (
    ROOT / "data/development" / "human_review"
    / "gdpr7_six_element_review_decisions_v1.json"
)

# ---------------------------------------------------------------------------
# Schema / vocabulary constants
# ---------------------------------------------------------------------------

SCHEMA_BLANK = "gdpr7_six_element_review_surface@1.0.0"
SCHEMA_EDITABLE = "gdpr7_six_element_review_editable@1.0.0"
CONFIRMATION_SCHEMA = "gdpr7_review_import_confirmation_event@1.0.0"

DECISION_VALUES = ("accepted", "edited", "rejected")
REVIEW_STATES = ("unreviewed", "reviewed")
MODALITY_LABELS = ("definition", "obligation", "permission", "prohibition")
TEXT_FIELDS = ("actor", "action", "condition", "constraint", "exception")
ALL_FIELDS = ("modality",) + TEXT_FIELDS
FIELDS_PER_SENTENCE = len(ALL_FIELDS)  # 6

# review block: six per-field entries + review_state + notes
REVIEW_KEYS = frozenset(ALL_FIELDS) | frozenset({"review_state", "notes"})
FIELD_ENTRY_KEYS = frozenset({"decision", "edited_value"})

CANDIDATE_SOURCE = "deterministic_development_extraction_v1"
# single-value (string | null) slots carried by every candidate object
CANDIDATE_ELEMENT_FIELDS = ALL_FIELDS
CANDIDATE_KIND_FIELDS = ("constraint_kind", "exception_kind")

# editable top-level statuses maintained by the workflow (build/tool/importer);
# the field is validated only as a non-empty string, but these are the three
# values this workflow itself ever writes.
STATUS_EDITING_UNREVIEWED = "editing_unreviewed"
STATUS_EDITING_IN_PROGRESS = "editing_in_progress"
STATUS_EDITING_COMPLETE = "editing_complete"
STATUS_VALUES = (
    STATUS_EDITING_UNREVIEWED,
    STATUS_EDITING_IN_PROGRESS,
    STATUS_EDITING_COMPLETE,
)

# modal-verb warning trigger for multi-norm sentences
MODAL_VERB_RE = re.compile(r"\b(shall|must|may|should)\b", re.IGNORECASE)
MODAL_WARNING_TRIGGER = 2

# confirmation-event fields (schema gdpr7_review_import_confirmation_event@1.0.0)
CONFIRMATION_KEYS = frozenset({
    "schema_version",
    "event_id",
    "source_user_instruction_utf8",
    "source_user_instruction_utf8_sha256",
    "reviewer",
    "source_file_sha256",
    "target_file_sha256",
    "source_blank_sha256",
    "gold_created",
    "append_only",
    "created_at_utc",
})

# ---------------------------------------------------------------------------
# Byte / JSON helpers (UTF-8, LF, single trailing newline)
# ---------------------------------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    """sha256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """sha256 hex digest of the UTF-8 bytes of ``text``."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """sha256 hex digest of the raw bytes of the file at ``path``."""
    return sha256_bytes(Path(path).read_bytes())


def doc_json_bytes(doc: Any) -> bytes:
    """Serialize ``doc`` as UTF-8 bytes: ``json.dumps(ensure_ascii=False,
    indent=2) + "\\n"`` (LF endings, single trailing newline)."""
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_doc_json(path: Path, doc: Any) -> None:
    """Write ``doc`` to ``path`` with the workflow's canonical byte layout."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(doc_json_bytes(doc))


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON document (raises OSError / JSONDecodeError)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_save_json(path: Path, doc: Any, keep_backup: bool = True) -> Optional[Path]:
    """Atomically replace ``path`` with ``doc`` and return the backup path.

    Strategy (mirrors the repo's other review tools): the current file content
    is first copied to ``<path>.bak`` (previous ``.bak``, if any, is
    overwritten), the new payload is written to ``<path>.tmp``, and
    ``os.replace`` then swaps the temp file in place of ``path``. On any
    failure before ``os.replace`` the target file is left untouched.
    """
    path = Path(path)
    data = doc_json_bytes(doc)
    backup: Optional[Path] = None
    if keep_backup and path.exists():
        backup = path.with_name(path.name + ".bak")
        backup.write_bytes(path.read_bytes())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return backup


# ---------------------------------------------------------------------------
# Low-level per-field decision validation
# ---------------------------------------------------------------------------


def is_verbatim_substring(value: str, text: str) -> bool:
    """True iff ``value`` occurs in ``text`` as a verbatim contiguous substring.

    Every occurrence found by ``str.find`` is additionally length-checked
    against the corresponding slice of ``text`` (defensive: ``str.find`` can
    never return a mismatched span, but the check keeps the invariant explicit
    and guards future callers that might pass already-located offsets).
    Empty values are never verbatim substrings here: ``edited`` requires a
    non-empty string, and an empty string would trivially match everywhere.
    """
    if not isinstance(value, str) or not isinstance(text, str) or not value:
        return False
    start = 0
    found = False
    while True:
        idx = text.find(value, start)
        if idx < 0:
            break
        found = True
        if text[idx:idx + len(value)] != value:
            return False
        start = idx + 1
    return found


def validate_field_decision(field: str,
                            decision: Optional[str],
                            edited_value: Optional[str],
                            sentence_text: Optional[str],
                            notes: Optional[str] = None) -> Tuple[bool, list[str]]:
    """Validate one review-field decision.

    Returns ``(ok, errors)``.

    * unknown field -> error;
    * ``decision is None`` (undecided): legal only while ``edited_value`` is
      also None (nothing may be half-written);
    * ``decision`` must be one of accepted/edited/rejected;
    * ``edited`` requires a non-empty string ``edited_value``; for modality it
      must be one of the four controlled labels; for the five text fields it
      must be a verbatim contiguous substring of ``sentence_text``;
    * ``accepted`` / ``rejected`` require ``edited_value is None``.

    ``notes`` is accepted for interface symmetry and is NOT validated here
    (notes are sentence-level, see :func:`validate_sentence_review`).
    """
    errors: list[str] = []
    if field not in ALL_FIELDS:
        return (False, [f"unknown review field {field!r}"])
    if decision is None:
        if edited_value is not None:
            errors.append(f"{field}: undecided decision must keep edited_value null")
        return (not errors, errors)
    if decision not in DECISION_VALUES:
        return (False, [
            f"{field}: decision {decision!r} not in {DECISION_VALUES}",
        ])
    if decision == "edited":
        if not isinstance(edited_value, str) or not edited_value:
            errors.append(
                f"{field}: decision=edited requires a non-empty string edited_value"
            )
            return (False, errors)
        if field == "modality":
            if edited_value not in MODALITY_LABELS:
                errors.append(
                    f"modality: edited_value {edited_value!r} not in "
                    f"{MODALITY_LABELS}"
                )
        elif not is_verbatim_substring(edited_value, sentence_text or ""):
            errors.append(
                f"{field}: edited_value {edited_value!r} is not a verbatim "
                f"contiguous substring of sentence_text"
            )
    else:  # accepted / rejected
        if edited_value is not None:
            errors.append(
                f"{field}: decision={decision} must keep edited_value null"
            )
    return (not errors, errors)


def count_modal_verbs(text: str) -> int:
    """Count shall/must/may/should occurrences (case-insensitive, word-bounded)."""
    if not isinstance(text, str):
        return 0
    return len(MODAL_VERB_RE.findall(text))


def sentence_decided_fields(sentence: Mapping[str, Any]) -> list[str]:
    """Ordered list of the six review fields already decided on a sentence."""
    decided: list[str] = []
    review = sentence.get("review")
    if isinstance(review, dict):
        for field in ALL_FIELDS:
            entry = review.get(field)
            if isinstance(entry, dict) and entry.get("decision") in DECISION_VALUES:
                decided.append(field)
    return decided


def sentence_is_reviewed(sentence: Mapping[str, Any]) -> bool:
    """True iff every one of the six review fields is decided."""
    return len(sentence_decided_fields(sentence)) == FIELDS_PER_SENTENCE


def recompute_sentence_review_state(sentence: Mapping[str, Any]) -> str:
    """Recompute ``review.review_state`` from the decided fields in place.

    Returns the new state. This is pure aggregation over decisions that were
    explicitly supplied by a human; it never fabricates a decision.
    """
    review = sentence.get("review")
    if not isinstance(review, dict):
        return "unreviewed"
    state = "reviewed" if sentence_is_reviewed(sentence) else "unreviewed"
    review["review_state"] = state
    return state


# ---------------------------------------------------------------------------
# Per-sentence validation
# ---------------------------------------------------------------------------


def _review_block_errors(review: Any, prefix: str) -> list[str]:
    """Structural checks for one ``review`` block shared by every validator."""
    errors: list[str] = []
    if not isinstance(review, dict):
        return [f"{prefix}: review is not an object"]
    extra = set(review.keys()) - REVIEW_KEYS
    if extra:
        errors.append(f"{prefix}: review has extra keys {sorted(extra)}")
    missing = REVIEW_KEYS - set(review.keys())
    if missing:
        errors.append(f"{prefix}: review missing keys {sorted(missing)}")
    state = review.get("review_state")
    if state not in REVIEW_STATES:
        errors.append(f"{prefix}: review_state {state!r} not in {REVIEW_STATES}")
    notes = review.get("notes")
    if notes is not None and not isinstance(notes, str):
        errors.append(f"{prefix}: notes must be a string or null")
    for field in ALL_FIELDS:
        entry = review.get(field)
        if not isinstance(entry, dict):
            errors.append(f"{prefix}: review.{field} is not an object")
            continue
        if set(entry.keys()) != FIELD_ENTRY_KEYS:
            errors.append(
                f"{prefix}: review.{field} keys = {sorted(entry)}; expected "
                f"{sorted(FIELD_ENTRY_KEYS)}"
            )
            continue
        decision = entry.get("decision")
        edited_value = entry.get("edited_value")
        if decision is not None and decision not in DECISION_VALUES:
            errors.append(
                f"{prefix}: review.{field}.decision {decision!r} not in "
                f"{DECISION_VALUES}"
            )
        if edited_value is not None and not isinstance(edited_value, str):
            errors.append(
                f"{prefix}: review.{field}.edited_value must be a string or null"
            )
    return errors


def validate_sentence_review(sentence: Mapping[str, Any],
                             blank_identity: Optional[Mapping[str, Any]] = None
                             ) -> Tuple[bool, list[str], list[str]]:
    """Validate one sentence of an editable document.

    Returns ``(ok, errors, warnings)``.

    Structural + review checks (shared with the blank-surface invariant, the
    filled validator, the importer and the freeze verifier):

    * the sentence identity/evidence block is present and typed
      (sample_id / sentence_idx / char_span / text_sha256 / sentence_text);
    * ``text_sha256`` equals sha256 of the UTF-8 bytes of ``sentence_text``;
    * ``review`` has exactly the six per-field entries plus review_state and
      notes; every decided field passes :func:`validate_field_decision`;
    * ``review_state`` is one of unreviewed/reviewed; ``reviewed`` is allowed
      only when all six fields are decided and every field is legal (a
      ``reviewed`` state with any undecided or illegal field is an error);
    * when ``blank_identity`` (the matching sentence of the blank surface) is
      supplied, the immutable identity fields and the candidate object must
      match it exactly (an editable sentence may never drift from the blank).

    Warnings (advisory only, never fatal):

    * >=2 modal verbs (shall/must/may/should) in one sentence -> the sentence
      may contain several independent normative elements; the reviewer should
      explain in notes;
    * a non-null candidate value of a TEXT field that is not a verbatim
      substring of the sentence text -> after ``accepted`` the formal record
      would have no span coordinates; the reviewer should re-check the
      sentence.
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(sentence, dict):
        return (False, ["sentence entry is not an object"], [])
    sid = sentence.get("sample_id")
    prefix = sid if isinstance(sid, str) and sid else "<sentence>"

    # -- identity/evidence block -------------------------------------------
    text = sentence.get("sentence_text")
    if not isinstance(text, str) or not text:
        errors.append(f"{prefix}: sentence_text must be a non-empty string")
        text = ""
    for key, types in (
        ("sample_id", (str,)),
        ("sentence_idx", (int,)),
        ("char_span", (list, tuple)),
        ("text_sha256", (str,)),
    ):
        value = sentence.get(key)
        if value is None or not isinstance(value, types):
            errors.append(f"{prefix}: {key} missing or of wrong type")
    recorded_hash = sentence.get("text_sha256")
    if isinstance(text, str) and isinstance(recorded_hash, str):
        if recorded_hash != sha256_text(text):
            errors.append(
                f"{prefix}: text_sha256 {recorded_hash!r} does not match "
                f"sentence_text bytes"
            )

    candidate = sentence.get("candidate")
    if not isinstance(candidate, dict):
        errors.append(f"{prefix}: candidate is not an object")
    else:
        for field in CANDIDATE_ELEMENT_FIELDS:
            value = candidate.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(
                    f"{prefix}: candidate.{field} must be a string or null"
                )
        for field in CANDIDATE_KIND_FIELDS:
            value = candidate.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"{prefix}: candidate.{field} must be a string or null")

    review = sentence.get("review")
    errors.extend(_review_block_errors(review, prefix))

    # -- per-field decision semantics (verbatim spans etc.) ----------------
    field_errors: list[str] = []
    undecided: list[str] = []
    if isinstance(review, dict):
        for field in ALL_FIELDS:
            entry = review.get(field)
            if not isinstance(entry, dict):
                continue
            decision = entry.get("decision")
            edited_value = entry.get("edited_value")
            if decision is None:
                if edited_value is not None:
                    field_errors.append(
                        f"{prefix}: review.{field} undecided but edited_value "
                        f"is set"
                    )
                undecided.append(field)
                continue
            ok, ferr = validate_field_decision(
                field, decision, edited_value, text)
            if not ok:
                field_errors.extend(f"{prefix}: {m}" for m in ferr)
    errors.extend(field_errors)

    # -- review_state semantics ---------------------------------------------
    if isinstance(review, dict):
        state = review.get("review_state")
        if state == "reviewed":
            if undecided:
                errors.append(
                    f"{prefix}: review_state=reviewed but field(s) undecided: "
                    f"{', '.join(undecided)}"
                )
            # illegal decided fields are already reported in field_errors

    # -- immutable identity vs blank sentence -------------------------------
    if blank_identity is not None and isinstance(blank_identity, dict):
        for key in ("sample_id", "sentence_idx", "char_span", "text_sha256",
                    "sentence_text"):
            if sentence.get(key) != blank_identity.get(key):
                errors.append(
                    f"{prefix}: identity field {key} drifted from the blank "
                    f"surface"
                )
        if candidate is not None and isinstance(candidate, dict):
            blank_candidate = blank_identity.get("candidate")
            if candidate != blank_candidate:
                errors.append(f"{prefix}: candidate drifted from the blank surface")

    # -- advisory warnings ---------------------------------------------------
    modal_count = count_modal_verbs(text)
    if modal_count >= MODAL_WARNING_TRIGGER:
        warnings.append(
            f"{prefix}: 句中出现 {modal_count} 个情态动词（shall/must/may/should），"
            f"可能含多个独立规范元素，请在 notes 说明"
        )
    if isinstance(candidate, dict) and isinstance(text, str):
        for field in TEXT_FIELDS:
            cand_value = candidate.get(field)
            if isinstance(cand_value, str) and cand_value \
                    and not is_verbatim_substring(cand_value, text):
                warnings.append(
                    f"{prefix}: candidate.{field} 候选值 {cand_value!r} 非逐字子串，"
                    f"accepted 后正式记录将无坐标，请核对该句"
                )

    return (not errors, errors, warnings)


# ---------------------------------------------------------------------------
# Whole-document structural validators
# ---------------------------------------------------------------------------


def validate_blank_document(doc: Any) -> list[str]:
    """Structural + blank-invariant checks for a blank surface document.

    Fail-closed: every review decision must be null, every edited_value null,
    review_state ``unreviewed`` and notes null everywhere. Empty list == pass.
    """
    problems: list[str] = []
    if not isinstance(doc, dict):
        return ["blank surface document is not an object"]
    if doc.get("schema_version") != SCHEMA_BLANK:
        problems.append(
            f"schema_version {doc.get('schema_version')!r} != {SCHEMA_BLANK!r}"
        )
    if not isinstance(doc.get("dataset_id"), str) or not doc["dataset_id"]:
        problems.append("dataset_id must be a non-empty string")
    if not isinstance(doc.get("status"), str) or not doc["status"]:
        problems.append("status must be a non-empty string")
    counts = doc.get("counts")
    if not isinstance(counts, dict) or not isinstance(counts.get("rules"), int) \
            or not isinstance(counts.get("sentences"), int):
        problems.append("counts must carry integer rules/sentences")
    rules = doc.get("rules")
    if not isinstance(rules, list):
        return problems + ["rules must be a list"]
    seen_sids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            problems.append("rule entry is not an object")
            continue
        rid = rule.get("rule_id")
        prefix = rid if isinstance(rid, str) else "<rule>"
        if not isinstance(rid, str) or not rid:
            problems.append("rule_id must be a non-empty string")
        if not isinstance(rule.get("rule_text_sha256"), str) \
                or len(rule["rule_text_sha256"]) != 64:
            problems.append(f"rule {prefix}: rule_text_sha256 must be a 64-hex string")
        if not isinstance(rule.get("source_binding"), dict):
            problems.append(f"rule {prefix}: source_binding must be an object")
        sentences = rule.get("sentences")
        if not isinstance(sentences, list):
            problems.append(f"rule {prefix}: sentences must be a list")
            continue
        for s in sentences:
            if not isinstance(s, dict):
                problems.append(f"rule {prefix}: sentence entry is not an object")
                continue
            sid = s.get("sample_id")
            if not isinstance(sid, str) or not sid:
                problems.append(f"rule {prefix}: sentence sample_id missing")
                continue
            if sid in seen_sids:
                problems.append(f"duplicate sample_id {sid}")
            seen_sids.add(sid)
            for key in ("sentence_text", "text_sha256", "sample_id"):
                if key not in s:
                    problems.append(f"{sid}: missing {key}")
            text = s.get("sentence_text")
            if isinstance(text, str) and text \
                    and s.get("text_sha256") != sha256_text(text):
                problems.append(
                    f"{sid}: text_sha256 does not match sentence_text bytes"
                )
            review = s.get("review")
            problems.extend(_review_block_errors(review, sid))
            if isinstance(review, dict):
                if review.get("review_state") != "unreviewed":
                    problems.append(f"{sid}: review_state must be unreviewed in a blank")
                if review.get("notes") is not None:
                    problems.append(f"{sid}: notes must be null in a blank")
                for field in ALL_FIELDS:
                    entry = review.get(field)
                    if isinstance(entry, dict):
                        if entry.get("decision") is not None:
                            problems.append(
                                f"{sid}: review.{field}.decision must be null in a blank"
                            )
                        if entry.get("edited_value") is not None:
                            problems.append(
                                f"{sid}: review.{field}.edited_value must be null "
                                f"in a blank"
                            )
            candidate = s.get("candidate")
            if not isinstance(candidate, dict):
                problems.append(f"{sid}: candidate is not an object")
            else:
                for field in CANDIDATE_ELEMENT_FIELDS + CANDIDATE_KIND_FIELDS:
                    value = candidate.get(field)
                    if value is not None and not isinstance(value, str):
                        problems.append(
                            f"{sid}: candidate.{field} must be a string or null"
                        )
                if candidate.get("candidate_source") != CANDIDATE_SOURCE:
                    problems.append(
                        f"{sid}: candidate_source must be {CANDIDATE_SOURCE!r}"
                    )
                if candidate.get("is_gold") is not False:
                    problems.append(f"{sid}: candidate.is_gold must be false")
    return problems


def validate_editable_document(doc: Any) -> list[str]:
    """Structural checks for an editable document (schema_version etc.).

    Top-level layout: {schema_version, dataset_id, status, counts,
    source_blank_sha256, created_at_utc, rules[]}; the sentence blocks mirror
    the blank surface (identity + candidate + review), but review entries may
    carry legal human decisions and notes may be a string. Empty list == pass.
    """
    problems: list[str] = []
    if not isinstance(doc, dict):
        return ["editable document is not an object"]
    if doc.get("schema_version") != SCHEMA_EDITABLE:
        problems.append(
            f"schema_version {doc.get('schema_version')!r} != {SCHEMA_EDITABLE!r}"
        )
    top_keys = {
        "schema_version", "dataset_id", "status", "counts",
        "source_blank_sha256", "created_at_utc", "rules",
    }
    extra = set(doc.keys()) - top_keys
    if extra:
        problems.append(f"top-level extra keys {sorted(extra)}")
    missing = top_keys - set(doc.keys())
    if missing:
        problems.append(f"top-level missing keys {sorted(missing)}")
    if not isinstance(doc.get("dataset_id"), str) or not doc["dataset_id"]:
        problems.append("dataset_id must be a non-empty string")
    if not isinstance(doc.get("status"), str) or not doc["status"]:
        problems.append("status must be a non-empty string")
    sha = doc.get("source_blank_sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        problems.append("source_blank_sha256 must be a 64-hex string")
    if not isinstance(doc.get("created_at_utc"), str) \
            or not doc["created_at_utc"]:
        problems.append("created_at_utc must be a non-empty string")
    counts = doc.get("counts")
    if not isinstance(counts, dict) or not isinstance(counts.get("rules"), int) \
            or not isinstance(counts.get("sentences"), int):
        problems.append("counts must carry integer rules/sentences")
    rules = doc.get("rules")
    if not isinstance(rules, list):
        return problems + ["rules must be a list"]
    seen_sids: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            problems.append("rule entry is not an object")
            continue
        rid = rule.get("rule_id")
        if not isinstance(rid, str) or not rid:
            problems.append("rule_id must be a non-empty string")
        if not isinstance(rule.get("rule_text_sha256"), str) \
                or len(rule["rule_text_sha256"]) != 64:
            problems.append(f"rule {rid}: rule_text_sha256 must be a 64-hex string")
        sentences = rule.get("sentences")
        if not isinstance(sentences, list):
            problems.append(f"rule {rid}: sentences must be a list")
            continue
        for s in sentences:
            if not isinstance(s, dict):
                problems.append(f"rule {rid}: sentence entry is not an object")
                continue
            sid = s.get("sample_id")
            if not isinstance(sid, str) or not sid:
                problems.append(f"rule {rid}: sentence sample_id missing")
                continue
            if sid in seen_sids:
                problems.append(f"duplicate sample_id {sid}")
            seen_sids.add(sid)
            for key in ("sample_id", "sentence_idx", "char_span", "text_sha256",
                        "sentence_text", "candidate", "review"):
                if key not in s:
                    problems.append(f"{sid}: missing {key}")
            text = s.get("sentence_text")
            if isinstance(text, str) and text \
                    and s.get("text_sha256") != sha256_text(text):
                problems.append(f"{sid}: text_sha256 does not match sentence_text bytes")
            review = s.get("review")
            problems.extend(_review_block_errors(review, sid))
            if isinstance(review, dict):
                for field in ALL_FIELDS:
                    entry = review.get(field)
                    if not isinstance(entry, dict):
                        continue
                    decision = entry.get("decision")
                    edited_value = entry.get("edited_value")
                    if decision is not None and decision not in DECISION_VALUES:
                        problems.append(
                            f"{sid}: review.{field}.decision {decision!r} not in "
                            f"{DECISION_VALUES}"
                        )
                    if edited_value is not None and not isinstance(edited_value, str):
                        problems.append(
                            f"{sid}: review.{field}.edited_value must be a string "
                            f"or null"
                        )
            candidate = s.get("candidate")
            if not isinstance(candidate, dict):
                problems.append(f"{sid}: candidate is not an object")
            else:
                for field in CANDIDATE_ELEMENT_FIELDS + CANDIDATE_KIND_FIELDS:
                    value = candidate.get(field)
                    if value is not None and not isinstance(value, str):
                        problems.append(
                            f"{sid}: candidate.{field} must be a string or null"
                        )
                if candidate.get("candidate_source") != CANDIDATE_SOURCE:
                    problems.append(f"{sid}: candidate_source must be {CANDIDATE_SOURCE!r}")
                if candidate.get("is_gold") is not False:
                    problems.append(f"{sid}: candidate.is_gold must be false")
    return problems


# ---------------------------------------------------------------------------
# Whole-document helpers: flattening, identity, full audit, stats
# ---------------------------------------------------------------------------


def iter_flat_sentences(doc: Any):
    """Yield ``(rule_id, sentence)`` in document order (never crashes on a
    malformed doc; malformed blocks surface via the structural validators)."""
    if not isinstance(doc, dict):
        return
    rules = doc.get("rules")
    if not isinstance(rules, list):
        return
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rid = rule.get("rule_id")
        sentences = rule.get("sentences")
        if isinstance(sentences, list):
            for s in sentences:
                if isinstance(s, dict):
                    yield rid, s


def identity_drift_errors(doc: Any, blank_doc: Any) -> list[str]:
    """Compare the immutable identity of ``doc`` against ``blank_doc``.

    Covers rule census/order, sample_id census/order, the identity fields
    (sample_id/sentence_idx/char_span/text_sha256/sentence_text) and the
    candidate object of every sentence. Returns human-readable problems;
    empty list == identical.
    """
    problems: list[str] = []
    if not isinstance(doc, dict) or not isinstance(blank_doc, dict):
        return ["identity comparison requires two document objects"]
    if doc.get("dataset_id") != blank_doc.get("dataset_id"):
        problems.append(
            f"dataset_id {doc.get('dataset_id')!r} != blank "
            f"{blank_doc.get('dataset_id')!r}"
        )
    b_counts = blank_doc.get("counts")
    d_counts = doc.get("counts")
    if isinstance(b_counts, dict) and isinstance(d_counts, dict) \
            and b_counts != d_counts:
        problems.append(f"top-level counts {d_counts} != blank counts {b_counts}")

    d_flat = list(iter_flat_sentences(doc))
    b_flat = list(iter_flat_sentences(blank_doc))
    if len(d_flat) != len(b_flat):
        problems.append(
            f"sentence count {len(d_flat)} != blank sentence count {len(b_flat)}"
        )
    d_order = [(rid, s.get("sample_id")) for rid, s in d_flat]
    b_order = [(rid, s.get("sample_id")) for rid, s in b_flat]
    if d_order != b_order:
        problems.append("(rule_id, sample_id) order differs from the blank surface")
    for (rid, s), (brid, bs) in zip(d_flat, b_flat):
        sid = s.get("sample_id")
        if rid != brid:
            problems.append(
                f"{sid}: rule_id {rid!r} != blank rule_id {brid!r}"
            )
        for key in ("sample_id", "sentence_idx", "char_span", "text_sha256",
                    "sentence_text", "candidate"):
            if s.get(key) != bs.get(key):
                problems.append(f"{sid}: {key} differs from the blank surface")
    return problems


def audit_filled_document(doc: Any,
                          blank_doc: Any = None,
                          require_blank: bool = True) -> dict[str, Any]:
    """Full audit of a filled editable document.

    Returns ``{"errors": [...], "warnings": [...], "sample_errors": int}``.
    ``errors`` are fatal (structure, identity drift vs blank, illegal review
    decisions or illegal review states); ``warnings`` are advisory only.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(doc, dict):
        return {"errors": ["editable document is not an object"],
                "warnings": [], "sample_errors": 0}
    errors.extend(validate_editable_document(doc))

    if blank_doc is None:
        if require_blank:
            errors.append("blank surface document required for the "
                          "immutable-identity comparison")
    else:
        blank_problems = validate_blank_document(blank_doc)
        if blank_problems:
            errors.append("blank surface document is invalid:")
            errors.extend(f"  blank: {m}" for m in blank_problems)
        errors.extend(identity_drift_errors(doc, blank_doc))

    sample_errors = 0
    for _rid, sentence in iter_flat_sentences(doc):
        ok, errs, warns = validate_sentence_review(sentence)
        errors.extend(errs)
        warnings.extend(warns)
        if errs:
            sample_errors += 1
    return {"errors": errors, "warnings": warnings, "sample_errors": sample_errors}


def collect_stats(doc: Any) -> dict[str, Any]:
    """Aggregate progress statistics over an editable document.

    Returns ``{sentences_total, reviewed, unreviewed, decisions_total,
    fields_total, accepted, edited, rejected, per_field_decided,
    warnings_by_sample}`` where ``decisions_total`` counts decided fields and
    ``fields_total == sentences_total * 6`` (444 for the real 74-sentence
    document). ``warnings_by_sample`` maps sample_id -> list of advisory
    warnings produced by :func:`validate_sentence_review`.
    """
    sentences_total = 0
    reviewed = 0
    unreviewed = 0
    decisions_total = 0
    accepted = edited = rejected = 0
    per_field_decided = {field: 0 for field in ALL_FIELDS}
    warnings_by_sample: dict[str, list[str]] = {}
    for _rid, sentence in iter_flat_sentences(doc):
        sentences_total += 1
        review = sentence.get("review")
        state = review.get("review_state") if isinstance(review, dict) else None
        if state == "reviewed":
            reviewed += 1
        else:
            unreviewed += 1
        if isinstance(review, dict):
            for field in ALL_FIELDS:
                entry = review.get(field)
                if isinstance(entry, dict):
                    decision = entry.get("decision")
                    if decision in DECISION_VALUES:
                        decisions_total += 1
                        per_field_decided[field] += 1
                        if decision == "accepted":
                            accepted += 1
                        elif decision == "edited":
                            edited += 1
                        elif decision == "rejected":
                            rejected += 1
        ok, errs, warns = validate_sentence_review(sentence)
        if warns:
            sid = sentence.get("sample_id")
            if isinstance(sid, str) and sid:
                warnings_by_sample[sid] = warns
    fields_total = FIELDS_PER_SENTENCE * sentences_total
    return {
        "sentences_total": sentences_total,
        "reviewed": reviewed,
        "unreviewed": unreviewed,
        "decisions_total": decisions_total,
        "fields_total": fields_total,
        "accepted": accepted,
        "edited": edited,
        "rejected": rejected,
        "per_field_decided": per_field_decided,
        "warnings_by_sample": warnings_by_sample,
    }


def recompute_doc_status(doc: Any) -> str:
    """Recompute the editable top-level ``status`` from current content.

    Pure aggregation over already-written review decisions (never fabricates
    a decision): complete when every sentence is reviewed, in_progress once
    any decision exists, otherwise back to the build-time unreviewed status.
    """
    stats = collect_stats(doc)
    if stats["sentences_total"] and stats["reviewed"] == stats["sentences_total"]:
        status = STATUS_EDITING_COMPLETE
    elif stats["decisions_total"] > 0:
        status = STATUS_EDITING_IN_PROGRESS
    else:
        status = STATUS_EDITING_UNREVIEWED
    if isinstance(doc, dict):
        doc["status"] = status
    return status


# ---------------------------------------------------------------------------
# Confirmation event helpers
# ---------------------------------------------------------------------------


def validate_confirmation_event(conf: Any,
                                source_file_sha256: Optional[str] = None,
                                target_file_sha256: Optional[str] = None,
                                blank_file_sha256: Optional[str] = None
                                ) -> list[str]:
    """Validate a ``gdpr7_review_import_confirmation_event@1.0.0`` document.

    Semantic requirements (mirroring the workflow's append-only import rule):

    * exact schema_version; all twelve keys present with correct types;
    * ``event_id``, ``reviewer`` and ``created_at_utc`` non-empty strings
      (the reviewer is taken ONLY from the event);
    * ``source_user_instruction_utf8_sha256`` == sha256 of the UTF-8 bytes of
      ``source_user_instruction_utf8``;
    * ``gold_created`` is false and ``append_only`` is true;
    * when an expected sha is supplied, the matching field must equal it
      (hash-drift guard); otherwise the field must at least be a non-empty
      string.

    Empty list == valid.
    """
    problems: list[str] = []
    if not isinstance(conf, dict):
        return ["confirmation event is not an object"]
    if conf.get("schema_version") != CONFIRMATION_SCHEMA:
        problems.append(
            f"schema_version {conf.get('schema_version')!r} != "
            f"{CONFIRMATION_SCHEMA!r}"
        )
    extra = set(conf.keys()) - CONFIRMATION_KEYS
    if extra:
        problems.append(f"confirmation extra keys {sorted(extra)}")
    missing = CONFIRMATION_KEYS - set(conf.keys())
    if missing:
        problems.append(f"confirmation missing keys {sorted(missing)}")
    for key in ("event_id", "reviewer", "created_at_utc", "source_file_sha256",
                "target_file_sha256", "source_blank_sha256"):
        value = conf.get(key)
        if not isinstance(value, str) or not value:
            problems.append(f"confirmation.{key} must be a non-empty string")
    instruction = conf.get("source_user_instruction_utf8")
    if not isinstance(instruction, str):
        problems.append("confirmation.source_user_instruction_utf8 must be a string")
    instruction_sha = conf.get("source_user_instruction_utf8_sha256")
    if isinstance(instruction, str) and instruction:
        if not isinstance(instruction_sha, str) or len(instruction_sha) != 64:
            problems.append(
                "confirmation.source_user_instruction_utf8_sha256 must be a "
                "64-hex string"
            )
        elif instruction_sha != sha256_text(instruction):
            problems.append(
                "confirmation.source_user_instruction_utf8_sha256 does not "
                "match the instruction text"
            )
    if conf.get("gold_created") is not False:
        problems.append("confirmation.gold_created must be false")
    if conf.get("append_only") is not True:
        problems.append("confirmation.append_only must be true")
    for field, expected in (
        ("source_file_sha256", source_file_sha256),
        ("target_file_sha256", target_file_sha256),
        ("source_blank_sha256", blank_file_sha256),
    ):
        recorded = conf.get(field)
        if expected is not None:
            if recorded != expected:
                problems.append(
                    f"confirmation.{field} {recorded!r} != actual file sha256 "
                    f"{expected!r} (hash drift)"
                )
    return problems

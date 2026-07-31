"""S2.8D-R3: fail-closed unique exact-text span coordinate canonicalization.

Pure, offline, deterministic module for the H1 fallback pipeline.  It
consumes a parsed patch envelope, the record's full ``source_text``, and
the plan's immutable ``clause_span``, and re-anchors ONLY ``start``/``end``
of every proposed span to the unique exact occurrence of the proposed text
inside the original clause window.

Rules (all fail closed, no guesses):

* coordinates are Python/Unicode code points: 0-based, end-exclusive,
  relative to the FULL ``source_text``;
* the search window is strictly ``source_text[clause_start:clause_end]``;
* matching is EXACT (case, space, punctuation, Unicode identical); no
  strip, normalize, lower, token, fuzzy, or semantic matching is ever used;
* occurrence count == 1 inside the clause window -> ``unique_exact_reanchor``;
* occurrence count == 0 -> ``coordinate_canonicalization_zero_match``;
* occurrence count > 1 -> ``coordinate_canonicalization_ambiguous_match``
  (overlapping occurrences also count);
* structurally invalid span / clause_span / source_text /
  container -> ``coordinate_canonicalization_contract_violation``;
* ANY failure fails the WHOLE patch atomically: no partial correction is
  ever produced and the original envelope is returned untouched;
* relation fields (``actor_action_map``, ``order_relations``) are never
  examined or modified;
* only ``start`` and ``end`` may differ between input and output.

The audit dict contains hashes, lengths, offsets, and counts only -- never
span text, source text, prompt text, reasoning, or credentials.

This module never reads ``.env``, never touches Gold or Layer E, never
calls any LLM/API, and is deterministic (repeated runs are identical).
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_artifact import json_hash
from bpc_hybrid.h1_transport import sha256_text

STATUS_UNCHANGED = "unchanged"
STATUS_REANCHORED = "reanchored"
STATUS_FAILED = "failed"

CODE_ZERO_MATCH = "coordinate_canonicalization_zero_match"
CODE_AMBIGUOUS_MATCH = "coordinate_canonicalization_ambiguous_match"
CODE_CONTRACT_VIOLATION = "coordinate_canonicalization_contract_violation"

# Span-bearing patch fields (relations are intentionally excluded).
SPAN_CONTAINER_FIELDS = (
    "actors",
    "actions",
    "conditions",
    "constraints",
    "exceptions",
)

FAILED_REASON_CODES = (CODE_ZERO_MATCH, CODE_AMBIGUOUS_MATCH, CODE_CONTRACT_VIOLATION)


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_absent_marker(value: Any) -> bool:
    return isinstance(value, Mapping) and value.get("absent") is True


def _span_contract_error(span: Any) -> str | None:
    """Return a violation detail for a structurally invalid span, else None."""
    if not isinstance(span, Mapping):
        return "span is not an object"
    text = span.get("text")
    if not isinstance(text, str) or not text:
        return "span text is not a non-empty string"
    start = span.get("start")
    end = span.get("end")
    if not _is_plain_int(start) or not _is_plain_int(end):
        return "span start/end must be integers (bool rejected)"
    if start > end:
        return "span start > end"
    return None


def _clause_span_contract_error(clause_span: Any, source_text: str) -> str | None:
    """Return a violation detail for an invalid clause_span, else None."""
    if not isinstance(clause_span, Mapping):
        return "clause_span is not an object"
    start = clause_span.get("start")
    end = clause_span.get("end")
    if not _is_plain_int(start) or not _is_plain_int(end):
        return "clause_span start/end must be integers (bool rejected)"
    if start > end:
        return "clause_span start > end"
    if start < 0 or end > len(source_text):
        return "clause_span is outside source_text bounds"
    return None


def _occurrences_in_window(
    needle: str,
    source_text: str,
    clause_start: int,
    clause_end: int,
) -> list[int]:
    """All exact-match start indexes (GLOBAL coordinates) of ``needle`` that
    fit entirely inside ``source_text[clause_start:clause_end]``.

    Overlapping occurrences are counted (e.g. "aaa" occurs twice in "aaaa").
    """
    starts: list[int] = []
    index = clause_start
    while True:
        found = source_text.find(needle, index, clause_end)
        if found == -1 or found + len(needle) > clause_end:
            break
        starts.append(found)
        index = found + 1
    return starts


def _collect_span_entries(envelope: Mapping[str, Any]) -> tuple[list[tuple[str, Any]], str | None]:
    """Flatten ``(field_path, span)`` entries from the patch containers.

    Returns ``(entries, violation)``; ``violation`` is non-None when a
    span container has an illegal shape (contract violation).
    """
    entries: list[tuple[str, Any]] = []
    patches = envelope.get("patches")
    if not isinstance(patches, Mapping):
        return entries, "patches is not an object"

    modality = patches.get("modality")
    if modality is not None and not _is_absent_marker(modality):
        if not isinstance(modality, Mapping):
            return entries, "modality patch is not an object"
        evidence = modality.get("evidence")
        if evidence is not None:
            if not isinstance(evidence, list):
                return entries, "modality.evidence is not a list"
            for index, item in enumerate(evidence):
                entries.append((f"modality.evidence[{index}]", item))

    for field_name in SPAN_CONTAINER_FIELDS:
        value = patches.get(field_name)
        if value is None or _is_absent_marker(value):
            continue
        if not isinstance(value, list):
            return entries, f"{field_name} patch is not a list"
        for index, span in enumerate(value):
            entries.append((f"{field_name}[{index}]", span))
    return entries, None


def canonicalize_patch_coordinates(
    envelope: Any,
    source_text: Any,
    clause_span: Any,
) -> tuple[Any, dict[str, Any]]:
    """Canonicalize span coordinates in one patch envelope.

    Parameters
    ----------
    envelope : any
        The parsed LLM patch envelope (expected mapping).
    source_text : any
        The record's full source text (expected non-empty str).
    clause_span : any
        The plan clause's immutable span (expected mapping with int
        ``start``/``end``).

    Returns
    -------
    ``(canonicalized_envelope, audit)``.
    On success ``canonicalized_envelope`` is a deep copy with ONLY
    ``start``/``end`` corrections applied; on failure it is the ORIGINAL
    envelope object, unchanged, and ``audit["status"] == "failed"`` with
    stable reason codes.
    """
    audit: dict[str, Any] = {
        "attempted": True,
        "status": STATUS_UNCHANGED,
        "span_count": 0,
        "already_valid_count": 0,
        "reanchored_count": 0,
        "failed_count": 0,
        "zero_match_count": 0,
        "ambiguous_match_count": 0,
        "contract_violation_count": 0,
        "original_patch_sha256": None,
        "canonicalized_patch_sha256": None,
        "reason_codes": [],
        "corrections": [],
    }

    if not isinstance(envelope, Mapping):
        audit.update(
            status=STATUS_FAILED,
            failed_count=1,
            contract_violation_count=1,
            reason_codes=[CODE_CONTRACT_VIOLATION],
        )
        return envelope, audit

    audit["original_patch_sha256"] = json_hash(envelope)

    if not isinstance(source_text, str):
        audit.update(
            status=STATUS_FAILED,
            failed_count=1,
            contract_violation_count=1,
            reason_codes=[CODE_CONTRACT_VIOLATION],
        )
        return envelope, audit

    violation = _clause_span_contract_error(clause_span, source_text)
    if violation is not None:
        audit.update(
            status=STATUS_FAILED,
            failed_count=1,
            contract_violation_count=1,
            reason_codes=[CODE_CONTRACT_VIOLATION],
        )
        return envelope, audit

    entries, container_violation = _collect_span_entries(envelope)
    if container_violation is not None:
        audit.update(
            status=STATUS_FAILED,
            failed_count=1,
            contract_violation_count=1,
            reason_codes=[CODE_CONTRACT_VIOLATION],
        )
        return envelope, audit

    clause_start = int(clause_span["start"])
    clause_end = int(clause_span["end"])
    audit["span_count"] = len(entries)

    per_span_statuses: list[tuple[str, str | None, dict[str, Any] | None]] = []
    for path, span in entries:
        violation = _span_contract_error(span)
        if violation is not None:
            per_span_statuses.append((path, CODE_CONTRACT_VIOLATION, None))
            continue
        text = str(span["text"])
        start = int(span["start"])
        end = int(span["end"])
        if clause_start <= start and end <= clause_end and source_text[start:end] == text:
            per_span_statuses.append((path, None, None))  # already valid
            continue
        occurrences = _occurrences_in_window(text, source_text, clause_start, clause_end)
        if len(occurrences) == 0:
            per_span_statuses.append((path, CODE_ZERO_MATCH, None))
        elif len(occurrences) > 1:
            per_span_statuses.append((path, CODE_AMBIGUOUS_MATCH, None))
        else:
            corrected_start = occurrences[0]
            corrected_end = corrected_start + len(text)
            correction = {
                "field_path": path,
                "proposed_start": start,
                "proposed_end": end,
                "corrected_start": corrected_start,
                "corrected_end": corrected_end,
                "text_char_length": len(text),
                "text_utf8_length": len(text.encode("utf-8")),
                "text_sha256": sha256_text(text),
                "clause_start": clause_start,
                "clause_end": clause_end,
                "exact_occurrence_count": 1,
            }
            per_span_statuses.append((path, None, correction))

    failure_codes: list[str] = []
    for path, code, _ in per_span_statuses:
        if code is not None:
            failure_codes.append(code)
            if code == CODE_ZERO_MATCH:
                audit["zero_match_count"] += 1
            elif code == CODE_AMBIGUOUS_MATCH:
                audit["ambiguous_match_count"] += 1
            else:
                audit["contract_violation_count"] += 1

    if failure_codes:
        audit.update(
            status=STATUS_FAILED,
            failed_count=len(failure_codes),
            reason_codes=sorted(set(failure_codes)),
            corrections=[],
        )
        return envelope, audit

    for path, code, correction in per_span_statuses:
        if correction is not None:
            audit["reanchored_count"] += 1
            audit["corrections"].append(correction)
        else:
            audit["already_valid_count"] += 1

    if audit["reanchored_count"] == 0:
        audit["status"] = STATUS_UNCHANGED
        audit["canonicalized_patch_sha256"] = audit["original_patch_sha256"]
        return envelope, audit

    canonicalized = copy.deepcopy(dict(envelope))
    patches = canonicalized.get("patches")
    for path, code, correction in per_span_statuses:
        if correction is None:
            continue
        corrected_start = correction["corrected_start"]
        corrected_end = correction["corrected_end"]
        if path.startswith("modality.evidence["):
            index = int(path[len("modality.evidence["):-1])
            evidence = patches["modality"]["evidence"]
            evidence[index]["start"] = corrected_start
            evidence[index]["end"] = corrected_end
            continue
        for field_name in SPAN_CONTAINER_FIELDS:
            prefix = f"{field_name}["
            if not path.startswith(prefix):
                continue
            index = int(path[len(prefix):-1])
            patches[field_name][index]["start"] = corrected_start
            patches[field_name][index]["end"] = corrected_end
            break

    audit["status"] = STATUS_REANCHORED
    audit["canonicalized_patch_sha256"] = json_hash(canonicalized)
    return canonicalized, audit

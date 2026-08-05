"""D1 span-coordinate canonicalization (D1-R1, 2026-08-04).

The deepseek-v4-flash model on OpenAI-compatible relays returns spans whose
``text`` is exact but whose ``start``/``end`` offsets are frequently off by a
few characters on long multi-clause sentences, so the canonical validator
rejects otherwise correct records.  Following the S2.8D-R3 H1 precedent
(``h1_span_canonicalizer``), this module re-anchors a span to the UNIQUE
exact occurrence of its text:

* if ``text == source_text[start:end]`` the span is already valid and is
  left untouched (status ``unchanged``);
* otherwise the span's exact text must occur exactly once in the window
  (the clause for field spans, the whole source for clause spans) and the
  span is re-anchored there (status ``reanchored``);
* zero or multiple occurrences, or contract violations (non-integer
  offsets), fail closed for the whole record (status ``failed`` with a
  stable reason code).

Only ``start``/``end`` are ever modified; everything else is deep-copied.
Deterministic and Gold-blind; no normalization, fuzzy matching, or label
changes.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

STATUS_UNCHANGED = "unchanged"
STATUS_REANCHORED = "reanchored"
STATUS_FAILED = "failed"

SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")


class D1SpanCanonicalizationError(ValueError):
    """Raised for structural contract violations inside a record."""


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _occurrences(needle: str, source_text: str, window_start: int, window_end: int) -> list[int]:
    starts: list[int] = []
    index = window_start
    while True:
        found = source_text.find(needle, index, window_end)
        if found == -1 or found + len(needle) > window_end:
            break
        starts.append(found)
        index = found + 1
    return starts


def _reanchor_span(span: Mapping[str, Any], source_text: str, window_start: int, window_end: int) -> tuple[Mapping[str, Any], str]:
    """Return (fixed_span, outcome) for one span against a text window."""
    text = span.get("text")
    start = span.get("start")
    end = span.get("end")
    if not isinstance(text, str) or not text:
        return span, "empty_span_text"
    if not _is_plain_int(start) or not _is_plain_int(end):
        return span, "non_integer_offsets"
    if 0 <= start < end <= len(source_text) and source_text[start:end] == text:
        return span, STATUS_UNCHANGED
    starts = _occurrences(text, source_text, window_start, window_end)
    if len(starts) != 1:
        return span, ("zero_occurrence" if not starts else "ambiguous_occurrence")
    fixed = dict(span)
    fixed["start"] = starts[0]
    fixed["end"] = starts[0] + len(text)
    return fixed, STATUS_REANCHORED


def canonicalize_record_coordinates(
    record: Any,
    source_text: Any,
) -> tuple[Any, dict[str, Any]]:
    """Canonicalize every span coordinate in a direct-LLM canonical record.

    Parameters
    ----------
    record : any
        The parsed direct-LLM record (expected mapping with ``clauses``).
    source_text : any
        The record's full source text (expected non-empty str).

    Returns
    -------
    ``(canonicalized_record, audit)``.  On success the record is a deep copy
    with only ``start``/``end`` corrections applied; on failure the record is
    returned unchanged and ``audit["status"] == "failed"`` with stable
    reason codes.
    """
    audit: dict[str, Any] = {
        "attempted": True,
        "status": STATUS_UNCHANGED,
        "clause_span_count": 0,
        "field_span_count": 0,
        "reanchored_count": 0,
        "failed_reasons": [],
    }
    if not isinstance(record, Mapping):
        audit["status"] = STATUS_FAILED
        audit["failed_reasons"].append("record_not_object")
        return record, audit
    if not isinstance(source_text, str) or not source_text:
        audit["status"] = STATUS_FAILED
        audit["failed_reasons"].append("empty_source_text")
        return record, audit

    out = copy.deepcopy(record)
    clauses = out.get("clauses")
    if not isinstance(clauses, list):
        audit["status"] = STATUS_FAILED
        audit["failed_reasons"].append("clauses_not_list")
        return record, audit

    def fail(reason: str) -> None:
        audit["status"] = STATUS_FAILED
        audit["failed_reasons"].append(reason)

    for ci, clause in enumerate(clauses):
        if not isinstance(clause, Mapping):
            fail(f"clauses[{ci}]_not_object")
            return record, audit
        cs = clause.get("clause_span")
        if cs is not None:
            audit["clause_span_count"] += 1
            if not isinstance(cs, Mapping):
                fail(f"clauses[{ci}].clause_span_not_object")
                return record, audit
            fixed_cs, outcome = _reanchor_span(cs, source_text, 0, len(source_text))
            if outcome == STATUS_REANCHORED:
                audit["reanchored_count"] += 1
            elif outcome != STATUS_UNCHANGED:
                fail(f"clauses[{ci}].clause_span_{outcome}")
                return record, audit
            clause["clause_span"] = fixed_cs
            if not _is_plain_int(fixed_cs.get("start")) or not _is_plain_int(fixed_cs.get("end")):
                fail(f"clauses[{ci}].clause_span_bad_offsets")
                return record, audit
            window_start, window_end = int(fixed_cs["start"]), int(fixed_cs["end"])
        else:
            fail(f"clauses[{ci}]_missing_clause_span")
            return record, audit

        modality = clause.get("modality")
        if isinstance(modality, Mapping):
            evidence = modality.get("evidence")
            if isinstance(evidence, list):
                for ei, span in enumerate(evidence):
                    audit["field_span_count"] += 1
                    if not isinstance(span, Mapping):
                        fail(f"clauses[{ci}].modality.evidence[{ei}]_not_object")
                        return record, audit
                    fixed, outcome = _reanchor_span(span, source_text, window_start, window_end)
                    if outcome == STATUS_REANCHORED:
                        audit["reanchored_count"] += 1
                    elif outcome != STATUS_UNCHANGED:
                        fail(f"clauses[{ci}].modality.evidence[{ei}]_{outcome}")
                        return record, audit
                    evidence[ei] = fixed

        for field in SPAN_FIELDS:
            spans = clause.get(field)
            if spans is None:
                continue
            if not isinstance(spans, list):
                fail(f"clauses[{ci}].{field}_not_list")
                return record, audit
            for si, span in enumerate(spans):
                audit["field_span_count"] += 1
                if not isinstance(span, Mapping):
                    fail(f"clauses[{ci}].{field}[{si}]_not_object")
                    return record, audit
                fixed, outcome = _reanchor_span(span, source_text, window_start, window_end)
                if outcome == STATUS_REANCHORED:
                    audit["reanchored_count"] += 1
                elif outcome != STATUS_UNCHANGED:
                    fail(f"clauses[{ci}].{field}[{si}]_{outcome}")
                    return record, audit
                spans[si] = fixed

    if audit["status"] != STATUS_FAILED:
        audit["status"] = STATUS_REANCHORED if audit["reanchored_count"] else STATUS_UNCHANGED
    return out, audit

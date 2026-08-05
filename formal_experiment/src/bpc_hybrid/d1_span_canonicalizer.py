"""D1 span-coordinate canonicalization (D1-R1, 2026-08-05).

The deepseek-v4-pro model returns spans whose ``text`` is usually exact but
whose ``start``/``end`` offsets are frequently off by a few characters on long
multi-clause sentences, so the canonical validator rejects otherwise correct
records.  Following the S2.8D-R3 H1 precedent (``h1_span_canonicalizer``),
this module re-anchors a span to the UNIQUE exact occurrence of its text:

* if ``text == source_text[start:end]`` the span is already valid and is
  left untouched (status ``unchanged``);
* otherwise the span's exact text must occur exactly once in the window
  (the clause for field spans, the whole source for clause spans) and the
  span is re-anchored there (status ``reanchored``).

Empty-vs-error policy (user decision 2026-08-05: empty is legal; the six
semantic elements may be partially empty; Gold does not imply every element
is present):

* an unrecoverable FIELD span (zero/ambiguous occurrence, empty span text,
  non-integer offsets) is DROPPED from its array (treated as absent) and the
  record survives; the drop is recorded in the audit;
* an unrecoverable CLAUSE (missing/structurally invalid/unreanchorable
  clause_span, non-object clause) is DROPPED as a whole; the record survives;
* a record without ``clauses`` is treated as an empty (legal) record;
* only record-level structural violations (record not an object, empty
  source text, ``clauses`` present but not a list) still fail closed.

Only ``start``/``end`` are ever modified (or elements dropped); everything
else is deep-copied.  Deterministic and Gold-blind; no normalization, fuzzy
matching, or label changes.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

STATUS_UNCHANGED = "unchanged"
STATUS_REANCHORED = "reanchored"
STATUS_DEGRADED = "degraded"
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

    Returns ``(canonicalized_record, audit)``.  Field-span and clause-level
    problems degrade the record (elements dropped, audit records every drop);
    only record-level structural violations fail closed.
    """
    audit: dict[str, Any] = {
        "attempted": True,
        "status": STATUS_UNCHANGED,
        "clause_span_count": 0,
        "field_span_count": 0,
        "reanchored_count": 0,
        "dropped_spans": [],
        "dropped_clauses": [],
        "dropped_edges": [],
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
    if clauses is None:
        out["clauses"] = []
        return out, audit
    if not isinstance(clauses, list):
        audit["status"] = STATUS_FAILED
        audit["failed_reasons"].append("clauses_not_list")
        return record, audit

    def degraded() -> None:
        if audit["status"] != STATUS_FAILED and (
            audit["dropped_spans"] or audit["dropped_clauses"] or audit["dropped_edges"]
        ):
            audit["status"] = STATUS_DEGRADED

    kept: list[Any] = []
    for ci, clause in enumerate(clauses):
        if not isinstance(clause, Mapping):
            audit["dropped_clauses"].append(ci)
            degraded()
            continue
        cs = clause.get("clause_span")
        if cs is None:
            audit["dropped_clauses"].append(ci)
            degraded()
            continue
        if not isinstance(cs, Mapping):
            audit["dropped_clauses"].append(ci)
            degraded()
            continue
        fixed_cs, outcome = _reanchor_span(cs, source_text, 0, len(source_text))
        if outcome != STATUS_UNCHANGED and outcome != STATUS_REANCHORED:
            audit["dropped_clauses"].append(ci)
            degraded()
            continue
        audit["clause_span_count"] += 1
        if outcome == STATUS_REANCHORED:
            audit["reanchored_count"] += 1
        if not _is_plain_int(fixed_cs.get("start")) or not _is_plain_int(fixed_cs.get("end")):
            audit["dropped_clauses"].append(ci)
            degraded()
            continue
        clause["clause_span"] = fixed_cs
        window_start, window_end = int(fixed_cs["start"]), int(fixed_cs["end"])

        modality = clause.get("modality")
        if isinstance(modality, Mapping):
            evidence = modality.get("evidence")
            if isinstance(evidence, list):
                kept_evidence: list[Any] = []
                for ei, span in enumerate(evidence):
                    audit["field_span_count"] += 1
                    if not isinstance(span, Mapping):
                        audit["dropped_spans"].append(f"clauses[{ci}].modality.evidence[{ei}]")
                        degraded()
                        continue
                    fixed, outcome = _reanchor_span(span, source_text, window_start, window_end)
                    if outcome == STATUS_UNCHANGED:
                        kept_evidence.append(fixed)
                    elif outcome == STATUS_REANCHORED:
                        kept_evidence.append(fixed)
                        audit["reanchored_count"] += 1
                    else:
                        audit["dropped_spans"].append(f"clauses[{ci}].modality.evidence[{ei}]")
                        degraded()
                modality["evidence"] = kept_evidence

        for field in SPAN_FIELDS:
            spans = clause.get(field)
            if spans is None:
                continue
            if not isinstance(spans, list):
                audit["dropped_clauses"].append(ci)
                degraded()
                continue
            kept_spans: list[Any] = []
            for si, span in enumerate(spans):
                audit["field_span_count"] += 1
                if not isinstance(span, Mapping):
                    audit["dropped_spans"].append(f"clauses[{ci}].{field}[{si}]")
                    degraded()
                    continue
                fixed, outcome = _reanchor_span(span, source_text, window_start, window_end)
                if outcome == STATUS_UNCHANGED:
                    kept_spans.append(fixed)
                elif outcome == STATUS_REANCHORED:
                    kept_spans.append(fixed)
                    audit["reanchored_count"] += 1
                else:
                    audit["dropped_spans"].append(f"clauses[{ci}].{field}[{si}]")
                    degraded()
            clause[field] = kept_spans

        # Drop edges that reference ids removed by degradation (empty-vs-error
        # policy: a dangling reference must not kill the whole record).
        actor_ids = {s.get("id") for s in (clause.get("actors") or [])}
        action_ids = {s.get("id") for s in (clause.get("actions") or [])}
        kept_edges: list[Any] = []
        for ei, edge in enumerate(clause.get("actor_action_map") or []):
            if isinstance(edge, Mapping) and (
                edge.get("actor_id") is None or edge.get("actor_id") in actor_ids
            ) and edge.get("action_id") in action_ids:
                kept_edges.append(edge)
            else:
                audit["dropped_edges"].append(f"clauses[{ci}].actor_action_map[{ei}]")
                degraded()
        clause["actor_action_map"] = kept_edges
        kept_relations: list[Any] = []
        for oi, rel in enumerate(clause.get("order_relations") or []):
            if isinstance(rel, Mapping) and rel.get("before_action_id") in action_ids and rel.get("after_action_id") in action_ids:
                kept_relations.append(rel)
            else:
                audit["dropped_edges"].append(f"clauses[{ci}].order_relations[{oi}]")
                degraded()
        clause["order_relations"] = kept_relations
        kept.append(clause)

    out["clauses"] = kept
    if audit["status"] == STATUS_UNCHANGED and audit["reanchored_count"]:
        audit["status"] = STATUS_REANCHORED
    return out, audit

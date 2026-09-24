# -*- coding: utf-8 -*-
"""Gold-blind temporal projection for Sun/Ours Stage 3 order relations.

This module implements the frozen v4 order-relation supplement described in
docs/agent_prompts/STAGE3_TABLE3_V4.md section 4.  It is a pure
post-processing function over one canonical Stage-2 prediction record and the
same source sentence text.  It never reads the current BPMN, Gold, reference,
target rule/type/activity, mutation, control, or another BPMN.

The function returns (order_relations, audit) where order_relations is a list
of (before_text, after_text) pairs ready for the frozen Sun Definition-7
scorer.  Every source span, rejection reason, and native edge is retained in
audit.
"""

from __future__ import annotations

import re
import string
from typing import Any, Mapping

PROJECTION_NAME = "sun_stage3_temporal_projection_v1@1.0.0"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")

MARKER_RE = re.compile(r"\b(?:prior\s+to|before|after)\b", re.IGNORECASE)
_EXTRA_PUNCT = "\u201c\u201d\u2018\u2019\u2013\u2014\u2026"
PUNCTUATION = set(string.punctuation) | set(_EXTRA_PUNCT)


class ProjectionError(ValueError):
    """Raised only for invalid top-level input, not for clause-level rejects."""


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _valid_span(span: Any, text: str) -> bool:
    if not isinstance(span, Mapping):
        return False
    start = _as_int(span.get("start"))
    end = _as_int(span.get("end"))
    return start is not None and end is not None and 0 <= start < end <= len(text)


def _span_text(text: str, span: Mapping[str, Any]) -> str:
    return text[int(span["start"]):int(span["end"])]


def _span_contains(outer: Mapping[str, Any], inner: Mapping[str, Any]) -> bool:
    return (int(outer["start"]) <= int(inner["start"])
            and int(inner["end"]) <= int(outer["end"]))


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return max(a_start, b_start) < min(a_end, b_end)


def _trim_interval(text: str, start: int, end: int) -> tuple[int, int, str]:
    start = max(0, start)
    end = min(len(text), end)
    while start < end and (text[start].isspace() or text[start] in PUNCTUATION):
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in PUNCTUATION):
        end -= 1
    return start, end, text[start:end]


def _action_spans(clause: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [s for s in (clause.get("actions") or []) if isinstance(s, Mapping)]


def _field_spans(clause: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    return [s for s in (clause.get(field) or []) if isinstance(s, Mapping)]


def _all_exclusion_spans(clause: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    for field in ("conditions", "constraints", "exceptions"):
        out.extend(_field_spans(clause, field))
    return out

def _native_edges(clause: Mapping[str, Any], text: str) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    actions = {str(s.get("id")): s for s in _action_spans(clause) if s.get("id")}
    edges: list[tuple[str, str]] = []
    rejected: list[dict[str, Any]] = []
    for index, relation in enumerate(clause.get("order_relations") or []):
        before_id = after_id = None
        if isinstance(relation, Mapping):
            before_id = relation.get("before_action_id")
            after_id = relation.get("after_action_id")
        elif isinstance(relation, (list, tuple)) and len(relation) == 2:
            before_id, after_id = relation
        before = actions.get(str(before_id)) if before_id is not None else None
        after = actions.get(str(after_id)) if after_id is not None else None
        if before is None or after is None or not _valid_span(before, text) or not _valid_span(after, text):
            rejected.append({
                "index": index,
                "raw": relation if isinstance(relation, (dict, list, tuple)) else str(relation),
                "reason": "native_endpoint_not_resolvable_to_clause_action",
                "before_action_id": before_id,
                "after_action_id": after_id,
            })
            continue
        before_text = _span_text(text, before)
        after_text = _span_text(text, after)
        if not before_text.strip() or not after_text.strip():
            rejected.append({
                "index": index,
                "reason": "native_endpoint_empty_text",
                "before_action_id": before_id,
                "after_action_id": after_id,
            })
            continue
        edges.append((before_text, after_text))
    return edges, rejected


def _marker_spans(clause: Mapping[str, Any], text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    containers: list[tuple[str, Mapping[str, Any]]] = []
    for field in ("conditions", "constraints"):
        for span in _field_spans(clause, field):
            if _valid_span(span, text):
                containers.append((field, span))
    candidates: dict[tuple[int, int], dict[str, Any]] = {}
    for field, span in containers:
        s, e = int(span["start"]), int(span["end"])
        piece = text[s:e]
        for match in MARKER_RE.finditer(piece):
            marker_start = s + match.start()
            marker_end = s + match.end()
            key = (marker_start, marker_end)
            entry = {
                "marker": match.group(0),
                "marker_start": marker_start,
                "marker_end": marker_end,
                "field": field,
                "span_id": span.get("id"),
                "span_start": s,
                "span_end": e,
                "span_length": e - s,
            }
            previous = candidates.get(key)
            if previous is None or (
                entry["span_length"], entry["span_start"], entry["span_end"]
            ) < (
                previous["span_length"], previous["span_start"], previous["span_end"]
            ):
                candidates[key] = entry
    entries = sorted(candidates.values(), key=lambda x: (x["marker_start"], x["marker_end"]))
    rejected: list[dict[str, Any]] = []
    final: list[dict[str, Any]] = []
    for entry in entries:
        selected_piece = text[entry["span_start"]:entry["span_end"]]
        marker_count = len(list(MARKER_RE.finditer(selected_piece)))
        if marker_count > 1:
            rejected.append({**entry, "reason": "selected_span_contains_multiple_markers"})
            continue
        final.append(entry)
    return final, rejected


def _token_at(doc: Any, char_start: int) -> Any | None:
    for token in doc:
        if token.idx <= char_start < token.idx + len(token.text):
            return token
    return None


def _is_negated(doc: Any, marker_entry: Mapping[str, Any]) -> tuple[bool, str | None]:
    token = _token_at(doc, int(marker_entry["marker_start"]))
    if token is None:
        return True, "marker_token_not_found"
    if token.i > 0 and doc[token.i - 1].text.lower() in ("not", "never"):
        return True, "adjacent_negation"
    ancestors = set()
    current = token
    while current is not None:
        ancestors.add(current.i)
        if current.head.i == current.i:
            break
        current = current.head
    sent = token.sent
    for candidate in sent:
        if candidate.dep_ == "neg" and candidate.head.i in ancestors:
            return True, "dependency_neg_ancestor"
    return False, None


def _contains_verb_interval(doc: Any, start: int, end: int) -> int:
    count = 0
    for token in doc:
        token_start = token.idx
        token_end = token.idx + len(token.text)
        if token_start >= start and token_end <= end and token.pos_ in ("VERB", "AUX"):
            count += 1
    return count

def _main_action_endpoint(clause: Mapping[str, Any], text: str,
                          selected_time_span: Mapping[str, Any],
                          doc: Any) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    excluded = _all_exclusion_spans(clause)
    candidates: list[Mapping[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for span in _action_spans(clause):
        if not _valid_span(span, text):
            rejected.append({"reason": "invalid_action_span", "span": dict(span)})
            continue
        if any(_span_contains(excl, span) for excl in excluded if _valid_span(excl, text)):
            rejected.append({
                "reason": "action_fully_inside_condition_constraint_or_exception",
                "span_id": span.get("id"),
                "start": span.get("start"),
                "end": span.get("end"),
                "text": _span_text(text, span),
            })
            continue
        candidates.append(span)
    unique: dict[tuple[int, int], Mapping[str, Any]] = {}
    for span in candidates:
        key = (int(span["start"]), int(span["end"]))
        unique[key] = span
    candidates = list(unique.values())
    if len(candidates) != 1:
        rejected.append({
            "reason": "expected_exactly_one_main_action_candidate",
            "candidate_count": len(candidates),
            "candidates": [
                {"id": c.get("id"), "start": c.get("start"), "end": c.get("end"),
                 "text": _span_text(text, c)}
                for c in candidates
            ],
        })
        return None, rejected

    main = candidates[0]
    main_start, main_end = int(main["start"]), int(main["end"])
    time_start, time_end = int(selected_time_span["start"]), int(selected_time_span["end"])
    intervals: list[tuple[int, int]] = []
    if _overlaps(main_start, main_end, time_start, time_end):
        if main_start < time_start:
            intervals.append((main_start, min(main_end, time_start)))
        if time_end < main_end:
            intervals.append((max(main_start, time_end), main_end))
    else:
        intervals.append((main_start, main_end))

    trimmed: list[tuple[int, int, str, int]] = []
    for start, end in intervals:
        ts, te, value = _trim_interval(text, start, end)
        if ts < te:
            verb_count = _contains_verb_interval(doc, ts, te)
            trimmed.append((ts, te, value, verb_count))
    with_verb = [row for row in trimmed if row[3] > 0]
    if len(with_verb) != 1:
        rejected.append({
            "reason": "main_action_remaining_fragments_with_verb_not_exactly_one",
            "fragment_count": len(trimmed),
            "fragments": [
                {"start": s, "end": e, "text": v, "verb_count": c}
                for s, e, v, c in trimmed
            ],
        })
        return None, rejected
    s, e, value, _ = with_verb[0]
    return {
        "start": s,
        "end": e,
        "text": value,
        "source_span_id": main.get("id"),
        "raw_action_span": {"start": main_start, "end": main_end},
        "selected_time_span": {"start": time_start, "end": time_end},
        "fragments": [
            {"start": s, "end": e, "text": v, "verb_count": c}
            for s, e, v, c in trimmed
        ],
    }, rejected


def _subtree_interval(token: Any) -> tuple[int, int]:
    tokens = list(token.subtree)
    if not tokens:
        return token.idx, token.idx + len(token.text)
    start = min(t.idx for t in tokens)
    end = max(t.idx + len(t.text) for t in tokens)
    return start, end


def _verbal_endpoint(doc: Any, text: str, marker: Mapping[str, Any],
                     selected_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    marker_token = _token_at(doc, int(marker["marker_start"]))
    if marker_token is None:
        return None, {"reason": "marker_token_not_found"}
    marker_phrase_end = int(marker["marker_end"])
    last_token = None
    for token in doc:
        if marker_token.i <= token.i and token.idx + len(token.text) <= marker_phrase_end:
            last_token = token
    if last_token is None:
        last_token = marker_token
    head = last_token.head
    audit = {
        "marker_token": marker_token.text,
        "marker_last_token": last_token.text,
        "marker_head": head.text,
        "marker_head_pos": head.pos_,
        "marker_head_dep": head.dep_,
    }
    if head.pos_ not in ("VERB", "AUX"):
        return None, {**audit, "reason": "marker_head_not_verb_or_aux"}
    head_start, head_end = _subtree_interval(head)
    after_start = int(marker["marker_end"])
    after_end = int(selected_span["end"])
    truncate_at = after_end
    for token in doc:
        if token.idx < after_start:
            continue
        if token.dep_ in ("advcl", "relcl", "acl") and head not in token.subtree:
            sub_start, _ = _subtree_interval(token)
            if sub_start > after_start:
                truncate_at = min(truncate_at, sub_start)
            break
    start = max(after_start, head_start)
    end = min(after_end, head_end, truncate_at)
    ts, te, value = _trim_interval(text, start, end)
    audit.update({
        "head_subtree": {"start": head_start, "end": head_end,
                         "text": text[head_start:head_end]},
        "marker_after_span": {"start": after_start, "end": after_end},
        "truncate_at": truncate_at,
        "intersection": {"start": ts, "end": te, "text": value},
    })
    head_inside = (ts <= head.idx and head.idx + len(head.text) <= te)
    if not head_inside:
        return None, {**audit, "reason": "verbal_intersection_does_not_retain_head"}
    if not value.strip():
        return None, {**audit, "reason": "verbal_endpoint_empty"}
    return {"start": ts, "end": te, "text": value, "kind": "verbal"}, audit

def _noun_chunk_starts(doc: Any) -> dict[int, Any]:
    out: dict[int, Any] = {}
    for chunk in doc.noun_chunks:
        out.setdefault(chunk.start_char, chunk)
    return out


def _nominal_endpoint(doc: Any, text: str, marker: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    after_start = int(marker["marker_end"])
    tokens = [t for t in doc if t.idx >= after_start]
    if not tokens:
        return None, {"reason": "no_token_after_marker"}
    first = tokens[0]
    if text[after_start:first.idx].strip():
        return None, {"reason": "non_space_text_between_marker_and_first_token"}
    chunks_by_start = _noun_chunk_starts(doc)
    chunk = chunks_by_start.get(first.idx)
    if chunk is None:
        return None, {"reason": "first_token_after_marker_does_not_start_noun_chunk"}
    chunks = [chunk]
    cursor = chunk.end_char
    while True:
        following = [t for t in doc if t.idx >= cursor]
        if not following:
            break
        nxt = following[0]
        if text[cursor:nxt.idx].strip():
            break
        if nxt.text.lower() != "of":
            break
        after_of = [t for t in doc if t.idx >= nxt.idx + len(nxt.text)]
        if not after_of:
            break
        next_token = after_of[0]
        if text[nxt.idx + len(nxt.text):next_token.idx].strip():
            break
        next_chunk = chunks_by_start.get(next_token.idx)
        if next_chunk is None:
            break
        chunks.append(next_chunk)
        cursor = next_chunk.end_char
    start = chunks[0].start_char
    end = chunks[-1].end_char
    values = [text[c.start_char:c.end_char] for c in chunks]
    value = " ".join(values).strip()
    root = chunks[0].root
    root_text = root.text
    if root.pos_ == "NUM" or root_text.isdigit():
        return None, {"reason": "nominal_endpoint_numeric_root",
                      "root_text": root_text, "root_pos": root.pos_}
    if root.ent_type_ in ("DATE", "TIME", "QUANTITY"):
        return None, {"reason": "nominal_endpoint_date_time_quantity_root",
                      "root_text": root_text, "root_ent_type": root.ent_type_}
    if not value:
        return None, {"reason": "nominal_endpoint_empty"}
    return {"start": start, "end": end, "text": value, "kind": "nominal"}, {
        "chunks": [
            {"start": c.start_char, "end": c.end_char,
             "text": text[c.start_char:c.end_char], "root": c.root.text,
             "root_pos": c.root.pos_, "root_ent_type": c.root.ent_type_}
            for c in chunks
        ],
        "value": value,
    }


def _second_endpoint(doc: Any, text: str, marker: Mapping[str, Any],
                     selected_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    verbal, verbal_audit = _verbal_endpoint(doc, text, marker, selected_span)
    if verbal is not None:
        return verbal, {"branch": "verbal", **verbal_audit}
    if verbal_audit.get("reason") != "marker_head_not_verb_or_aux":
        return None, {"branch": "verbal_rejected", **verbal_audit}
    nominal, nominal_audit = _nominal_endpoint(doc, text, marker)
    return nominal, {"branch": "nominal", **nominal_audit}


def project_clause_order_relations(clause: Mapping[str, Any], text: str,
                                   doc: Any) -> dict[str, Any]:
    audit: dict[str, Any] = {
        "projection": PROJECTION_NAME,
        "clause_id": clause.get("clause_id"),
        "modality": (clause.get("modality") or {}).get("label"),
        "native": {"edges": [], "rejected": []},
        "markers": [],
        "derived_edges": [],
        "rejections": [],
    }
    if (clause.get("modality") or {}).get("label") != "obligation":
        return {"status": "not_obligation", "edges": [], "audit": audit}
    native_edges, native_rejected = _native_edges(clause, text)
    audit["native"] = {
        "edges": [
            {"before_text": b, "after_text": a} for b, a in native_edges
        ],
        "rejected": native_rejected,
    }
    if native_edges:
        return {"status": "native", "edges": native_edges, "audit": audit}
    markers, marker_rejects = _marker_spans(clause, text)
    audit["rejections"].extend(marker_rejects)
    for marker in markers:
        marker_audit = dict(marker)
        if any(_valid_span(exc, text) and
               int(exc["start"]) <= int(marker["marker_start"]) < int(exc["end"])
               for exc in _field_spans(clause, "exceptions")):
            marker_audit["reason"] = "marker_inside_predicted_exception"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        negated, neg_reason = _is_negated(doc, marker)
        if negated:
            marker_audit["reason"] = neg_reason or "negative_marker"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        selected_span = {"start": marker["span_start"], "end": marker["span_end"]}
        main, main_rejects = _main_action_endpoint(clause, text, selected_span, doc)
        marker_audit["main_action_rejections"] = main_rejects
        if main is None:
            marker_audit["reason"] = "no_single_main_action_endpoint"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        second, second_audit = _second_endpoint(doc, text, marker, selected_span)
        marker_audit["second_endpoint_audit"] = second_audit
        if second is None:
            marker_audit["reason"] = second_audit.get("reason", "no_second_endpoint")
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        if (main["start"], main["end"]) == (second["start"], second["end"]):
            marker_audit["reason"] = "endpoints_identical"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        marker_word = str(marker["marker"]).lower()
        if marker_word.startswith("after"):
            before, after = second, main
        else:
            before, after = main, second
        edge = {
            "before_text": before["text"],
            "after_text": after["text"],
            "before_offsets": [before["start"], before["end"]],
            "after_offsets": [after["start"], after["end"]],
            "marker": marker["marker"],
            "marker_offsets": [marker["marker_start"], marker["marker_end"]],
            "source": "derived",
        }
        marker_audit["edge"] = edge
        audit["markers"].append(marker_audit)
        audit["derived_edges"].append(edge)
    seen: set[tuple[Any, ...]] = set()
    edges: list[tuple[str, str]] = []
    deduped: list[dict[str, Any]] = []
    for edge in audit["derived_edges"]:
        key = (
            str(clause.get("clause_id")),
            tuple(edge["marker_offsets"]),
            tuple(edge["before_offsets"]),
            tuple(edge["after_offsets"]),
        )
        if key in seen:
            edge["deduplicated"] = True
            continue
        seen.add(key)
        edges.append((edge["before_text"], edge["after_text"]))
        deduped.append(edge)
    audit["derived_edges"] = deduped
    status = "derived" if edges else "no_edge"
    return {"status": status, "edges": edges, "audit": audit}


def project_record_order_relations(record: Mapping[str, Any], text: str,
                                   doc: Any) -> tuple[list[tuple[str, str]], dict[str, Any]]:
    if not isinstance(record, Mapping):
        raise ProjectionError("record_not_object")
    if not isinstance(text, str) or not text:
        raise ProjectionError("empty_source_text")
    if doc is None:
        raise ProjectionError("missing_spacy_doc")
    clauses = record.get("clauses")
    if not isinstance(clauses, list):
        raise ProjectionError("clauses_not_list")
    edges: list[tuple[str, str]] = []
    clause_audits: list[dict[str, Any]] = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            clause_audits.append({"status": "invalid_clause_not_object"})
            continue
        result = project_clause_order_relations(clause, text, doc)
        audit_row = {**result["audit"], "status": result["status"]}
        clause_audits.append(audit_row)
        edges.extend(result["edges"])
    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for pair in edges:
        if pair in seen:
            continue
        seen.add(pair)
        unique.append(pair)
    return unique, {
        "projection": PROJECTION_NAME,
        "clause_audits": clause_audits,
        "edge_count": len(unique),
        "derived_edge_count": sum(1 for c in clause_audits if c.get("status") == "derived"),
        "native_edge_count": sum(1 for c in clause_audits if c.get("status") == "native"),
    }


__all__ = [
    "PROJECTION_NAME",
    "ProjectionError",
    "project_clause_order_relations",
    "project_record_order_relations",
]
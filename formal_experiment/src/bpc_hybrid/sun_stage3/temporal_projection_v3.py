# -*- coding: utf-8 -*-
"""R2 strict temporal projection v3 for Sun/Ours Stage 3 order relations.

This module preserves ``temporal_projection_v1`` and ``v2`` byte-for-byte.
R2 replaces v2's permissive post-marker predicate scan with the exact R1
section-3.2 rule:

* a legal verbal head is selected only when the marker token has ``dep_ ==
  mark`` and its head is a VERB/AUX after the marker inside the selected
  predicted condition/constraint span; or
* when the marker token has ``dep_ == prep``, only its direct ``pcomp``
  children are considered, and exactly one legal VERB/AUX child is required.

No other token is scanned for a verbal complement.  If no legal verbal
complement exists, the bounded nominal branch is attempted.  The nominal
chunk and every completed ``of`` chain must lie entirely within the selected
span; an ``of`` chain that starts inside the span but cannot be completed is
rejected explicitly instead of returning a truncated noun.

The module remains pure post-processing over one canonical Stage-2 record and
the same source text.  It never reads the current BPMN, Gold, reference, a
target rule/type/activity, a mutation, a control, or another BPMN.
"""

from __future__ import annotations

from typing import Any, Mapping

from . import temporal_projection_v1 as v1

PROJECTION_NAME = "sun_stage3_temporal_projection_v3@1.0.0"
TYPES = v1.TYPES
_VERBAL_POS = {"VERB", "AUX"}


def _as_int(value: Any) -> int | None:
    return v1._as_int(value)


def _valid_span(span: Any, text: str) -> bool:
    return v1._valid_span(span, text)


def _selected_bounds(selected_span: Mapping[str, Any]) -> tuple[int, int] | None:
    if not isinstance(selected_span, Mapping):
        return None
    start = _as_int(selected_span.get("start"))
    end = _as_int(selected_span.get("end"))
    if start is None or end is None or start < 0 or end <= start:
        return None
    return start, end


def _token_in_span(token: Any, start: int, end: int) -> bool:
    return start <= token.idx and token.idx + len(token.text) <= end


def _token_audit(token: Any) -> dict[str, Any] | None:
    if token is None:
        return None
    return {
        "index": token.i,
        "text": token.text,
        "pos": token.pos_,
        "dep": token.dep_,
        "head": token.head.text,
        "head_pos": token.head.pos_,
    }


def _strict_verbal_head(doc: Any, marker: Mapping[str, Any],
                        selected_span: Mapping[str, Any]) -> tuple[Any | None, dict[str, Any]]:
    """Return the one legal verbal complement head, if the strict rule admits it.

    The returned head is ``None`` both when no legal head exists and when the
    marker dep is outside the mark/prep contract.  A direct pcomp ambiguity is
    reported with ``reason=multiple_legal_pcomp_children`` so the caller can
    reject without falling through to the nominal branch.
    """
    bounds = _selected_bounds(selected_span)
    if bounds is None:
        return None, {"branch": "verbal", "reason": "invalid_selected_span",
                      "candidates": [], "reasons": ["invalid_selected_span"]}
    span_start, span_end = bounds
    marker_token = v1._token_at(doc, int(marker["marker_start"]))
    audit: dict[str, Any] = {
        "branch": "verbal",
        "marker_token": (marker_token.text if marker_token is not None else None),
        "marker_dep": (marker_token.dep_ if marker_token is not None else None),
        "marker_head": (marker_token.head.text if marker_token is not None else None),
        "strategy": None,
        "post_marker_span": {
            "start": max(int(marker["marker_end"]), span_start),
            "end": span_end,
        },
        "candidates": [],
        "reasons": [],
    }
    if marker_token is None:
        audit["reasons"].append("marker_token_not_found")
        return None, audit
    after_start = max(int(marker["marker_end"]), span_start)

    if marker_token.dep_ == "mark":
        audit["strategy"] = "mark_head_after_marker_in_span"
        head = marker_token.head
        if head is marker_token:
            audit["reasons"].append("mark_head_is_self")
        elif head.pos_ not in _VERBAL_POS:
            audit["reasons"].append("mark_head_not_verb_or_aux")
            audit["head_candidate"] = _token_audit(head)
        elif not _token_in_span(head, after_start, span_end):
            audit["reasons"].append("mark_head_outside_marker_after_selected_span")
            audit["head_candidate"] = _token_audit(head)
        else:
            audit["candidates"].append(_token_audit(head))
            return head, audit
        return None, audit

    if marker_token.dep_ == "prep":
        audit["strategy"] = "direct_pcomp_children_only"
        direct = [child for child in marker_token.children if child.dep_ == "pcomp"]
        legal = [child for child in direct if child.pos_ in _VERBAL_POS
                 and _token_in_span(child, after_start, span_end)]
        audit["direct_pcomp_children"] = [_token_audit(child) for child in direct]
        audit["legal_pcomp_children"] = [_token_audit(child) for child in legal]
        if len(legal) == 1:
            audit["candidates"].append(_token_audit(legal[0]))
            return legal[0], audit
        if len(legal) > 1:
            audit["reasons"].append("multiple_legal_pcomp_children")
            return None, audit
        if direct:
            audit["reasons"].append("no_legal_pcomp_child")
            return None, audit
        audit["reasons"].append("no_pcomp_child")
        return None, audit

    audit["strategy"] = "marker_dep_not_mark_or_prep"
    audit["reasons"].append("marker_dep_not_mark_or_prep")
    return None, audit


def _nominal_endpoint_v3(doc: Any, text: str, marker: Mapping[str, Any],
                         selected_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    bounds = _selected_bounds(selected_span)
    if bounds is None:
        return None, {"branch": "nominal", "reason": "invalid_selected_span"}
    span_start, span_end = bounds
    after_start = int(marker["marker_end"])
    audit: dict[str, Any] = {
        "branch": "nominal",
        "selected_span": {"start": span_start, "end": span_end},
        "after_marker": after_start,
        "of_chain_started": False,
    }
    if not (span_start <= after_start < span_end):
        return None, {**audit, "reason": "marker_outside_selected_span"}
    tokens = [t for t in doc if t.idx >= after_start and t.idx < span_end]
    if not tokens:
        return None, {**audit, "reason": "no_token_after_marker"}
    first = tokens[0]
    if not _token_in_span(first, after_start, span_end):
        return None, {**audit, "reason": "first_token_exceeds_selected_span"}
    if text[after_start:first.idx].strip():
        return None, {**audit, "reason": "non_space_text_between_marker_and_first_token"}
    chunks_by_start = v1._noun_chunk_starts(doc)
    chunk = chunks_by_start.get(first.idx)
    if chunk is None:
        return None, {**audit, "reason": "first_token_after_marker_does_not_start_noun_chunk"}
    if chunk.start_char < span_start or chunk.end_char > span_end:
        return None, {**audit, "reason": "nominal_chunk_outside_selected_span",
                      "chunk": {"start": chunk.start_char, "end": chunk.end_char,
                                "text": text[chunk.start_char:chunk.end_char]}}
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
        if not (span_start <= nxt.idx and nxt.idx + len(nxt.text) <= span_end):
            # The chunk ended inside the selected span and the next token is
            # already outside it; no complete of-chain can be formed here.
            break
        audit["of_chain_started"] = True
        after_of = [t for t in doc if t.idx >= nxt.idx + len(nxt.text)]
        if not after_of:
            return None, {**audit, "reason": "nominal_of_chain_incomplete_after_of",
                          "of": {"start": nxt.idx, "end": nxt.idx + len(nxt.text)}}
        next_token = after_of[0]
        if next_token.idx + len(next_token.text) > span_end:
            return None, {**audit, "reason": "nominal_of_chain_incomplete_before_selected_span_end",
                          "of": {"start": nxt.idx, "end": nxt.idx + len(nxt.text)},
                          "next_token": _token_audit(next_token)}
        if text[nxt.idx + len(nxt.text):next_token.idx].strip():
            return None, {**audit, "reason": "nominal_of_chain_noncontiguous_after_of",
                          "of": {"start": nxt.idx, "end": nxt.idx + len(nxt.text)},
                          "next_token": _token_audit(next_token)}
        next_chunk = chunks_by_start.get(next_token.idx)
        if next_chunk is None:
            return None, {**audit, "reason": "nominal_of_chain_next_token_not_noun_chunk",
                          "of": {"start": nxt.idx, "end": nxt.idx + len(nxt.text)},
                          "next_token": _token_audit(next_token)}
        if next_chunk.start_char < span_start or next_chunk.end_char > span_end:
            return None, {**audit, "reason": "nominal_of_chain_outside_selected_span",
                          "chunks": [
                              {"start": c.start_char, "end": c.end_char,
                               "text": text[c.start_char:c.end_char]} for c in chunks
                          ],
                          "next_chunk": {"start": next_chunk.start_char,
                                         "end": next_chunk.end_char,
                                         "text": text[next_chunk.start_char:next_chunk.end_char]}}
        chunks.append(next_chunk)
        cursor = next_chunk.end_char
    start = chunks[0].start_char
    end = chunks[-1].end_char
    if not (span_start <= start < end <= span_end):
        return None, {**audit, "reason": "nominal_endpoint_outside_selected_span"}
    value = text[start:end]
    root = chunks[0].root
    root_text = root.text
    if root.pos_ == "NUM" or root_text.isdigit():
        return None, {**audit, "reason": "nominal_endpoint_numeric_root",
                      "root_text": root_text, "root_pos": root.pos_}
    if root.ent_type_ in ("DATE", "TIME", "QUANTITY"):
        return None, {**audit, "reason": "nominal_endpoint_date_time_quantity_root",
                      "root_text": root_text, "root_ent_type": root.ent_type_}
    if not value or value != text[start:end]:
        return None, {**audit, "reason": "nominal_endpoint_empty_or_mismatch"}
    return {"start": start, "end": end, "text": value, "kind": "nominal",
            "branch": "nominal"}, {
        **audit,
        "of_chain_complete": True,
        "chunks": [
            {"start": c.start_char, "end": c.end_char,
             "text": text[c.start_char:c.end_char], "root": c.root.text,
             "root_pos": c.root.pos_, "root_ent_type": c.root.ent_type_}
            for c in chunks
        ],
        "value": value,
        "source_substring_identity": value == text[start:end],
    }


def _verbal_endpoint_v3(doc: Any, text: str, marker: Mapping[str, Any],
                        selected_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    head, head_audit = _strict_verbal_head(doc, marker, selected_span)
    if head is None:
        return None, head_audit
    bounds = _selected_bounds(selected_span)
    if bounds is None:
        return None, {**head_audit, "reason": "invalid_selected_span"}
    span_start, span_end = bounds
    marker_end = int(marker["marker_end"])
    head_start, head_end = v1._subtree_interval(head)
    after_start = max(marker_end, span_start)
    after_end = min(span_end, int(selected_span["end"]))
    truncate_at = after_end
    for token in doc:
        if token.idx < after_start:
            continue
        if token.dep_ in ("advcl", "relcl", "acl") and head not in token.subtree:
            sub_start, _ = v1._subtree_interval(token)
            if sub_start > after_start:
                truncate_at = min(truncate_at, sub_start)
            break
    start = max(after_start, head_start)
    end = min(after_end, head_end, truncate_at)
    ts, te, value = v1._trim_interval(text, start, end)
    audit = {
        **head_audit,
        "selected_head": _token_audit(head),
        "head_subtree": {"start": head_start, "end": head_end,
                         "text": text[head_start:head_end]},
        "marker_after_span": {"start": after_start, "end": after_end},
        "truncate_at": truncate_at,
        "intersection": {"start": ts, "end": te, "text": value},
    }
    if not _valid_span({"start": ts, "end": te}, text):
        return None, {**audit, "reason": "verbal_intersection_invalid"}
    if not (ts <= head.idx and head.idx + len(head.text) <= te):
        return None, {**audit, "reason": "verbal_intersection_does_not_retain_head"}
    if ts < span_start or te > span_end:
        return None, {**audit, "reason": "verbal_endpoint_outside_selected_span"}
    if not value.strip():
        return None, {**audit, "reason": "verbal_endpoint_empty"}
    return {"start": ts, "end": te, "text": value, "kind": "verbal",
            "branch": "verbal"}, audit


def _second_endpoint_v3(doc: Any, text: str, marker: Mapping[str, Any],
                        selected_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    marker_word = str(marker.get("marker", "")).lower().strip()
    if marker_word.startswith("prior to"):
        nominal, nominal_audit = _nominal_endpoint_v3(doc, text, marker, selected_span)
        return nominal, {"branch": "nominal_prior_to", **nominal_audit}
    verbal, verbal_audit = _verbal_endpoint_v3(doc, text, marker, selected_span)
    if verbal is not None:
        return verbal, verbal_audit
    if verbal_audit.get("reason") == "multiple_legal_pcomp_children":
        return None, {"branch": "verbal_rejected", **verbal_audit}
    nominal, nominal_audit = _nominal_endpoint_v3(doc, text, marker, selected_span)
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
    native_edges, native_rejected = v1._native_edges(clause, text)
    audit["native"] = {
        "edges": [{"before_text": b, "after_text": a} for b, a in native_edges],
        "rejected": native_rejected,
    }
    if native_edges:
        return {"status": "native", "edges": native_edges, "audit": audit}
    markers, marker_rejects = v1._marker_spans(clause, text)
    audit["rejections"].extend(marker_rejects)
    for marker in markers:
        marker_audit = dict(marker)
        if any(_valid_span(exc, text) and
               int(exc["start"]) <= int(marker["marker_start"]) < int(exc["end"])
               for exc in v1._field_spans(clause, "exceptions")):
            marker_audit["reason"] = "marker_inside_predicted_exception"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        negated, neg_reason = v1._is_negated(doc, marker)
        if negated:
            marker_audit["reason"] = neg_reason or "negative_marker"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        selected_span = {"start": marker["span_start"], "end": marker["span_end"]}
        main, main_rejects = v1._main_action_endpoint(clause, text, selected_span, doc)
        marker_audit["main_action_rejections"] = main_rejects
        if main is None:
            marker_audit["reason"] = "no_single_main_action_endpoint"
            audit["markers"].append(marker_audit)
            audit["rejections"].append(marker_audit)
            continue
        second, second_audit = _second_endpoint_v3(doc, text, marker, selected_span)
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
            "second_endpoint_branch": second.get("branch"),
            "second_endpoint_kind": second.get("kind"),
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
        raise v1.ProjectionError("record_not_object")
    if not isinstance(text, str) or not text:
        raise v1.ProjectionError("empty_source_text")
    if doc is None:
        raise v1.ProjectionError("missing_spacy_doc")
    clauses = record.get("clauses")
    if not isinstance(clauses, list):
        raise v1.ProjectionError("clauses_not_list")
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

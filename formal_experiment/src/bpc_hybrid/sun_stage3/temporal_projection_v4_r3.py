# -*- coding: utf-8 -*-
"""R3 temporal/event projection v4.

This is a new versioned projection over the frozen v1/v2/v3 modules.  It keeps
the marker source, exception/negation rules, native-edge priority, main-action
selection, bounded nominal endpoint checks, and direction rules of v3.  The
single substantive change is that after a legal marker the selected complement
is *locally* parsed.  If the local parse has exactly one top-level event
predicate, the endpoint keeps that predicate and its event arguments.  A noun
phrase is accepted only when there is no unexplained event predicate.  This
prevents the R2 failure where ``... before the restriction of processing is
lifted`` was truncated to ``the restriction of processing`` and lost
``is lifted``.
"""

from __future__ import annotations

from typing import Any, Mapping

from . import temporal_projection_v1 as v1
from . import temporal_projection_v3 as v3

PROJECTION_NAME = "sun_stage3_temporal_projection_v4_r3@1.0.0"
ProjectionError = v1.ProjectionError
TYPES = v1.TYPES
_EVENT_DEPS = {"ROOT", "conj", "ccomp", "xcomp", "advcl", "acl", "relcl", "pcomp", "parataxis"}


def _nlp_or_default(nlp: Any) -> Any:
    if nlp is not None:
        return nlp
    import spacy  # type: ignore

    return spacy.load("en_core_web_sm")


def _valid_span(span: Any, text: str) -> bool:
    return v1._valid_span(span, text)


def _selected_bounds(selected_span: Mapping[str, Any]) -> tuple[int, int] | None:
    return v3._selected_bounds(selected_span)


def _token_audit(token: Any) -> dict[str, Any] | None:
    return v3._token_audit(token)


def _trim_local(text: str, start: int, end: int) -> tuple[int, int, str]:
    return v1._trim_interval(text, start, end)


def _event_predicates(doc: Any) -> list[Any]:
    """Top-level event predicates admitted by the local R3 rule."""
    out: list[Any] = []
    for token in doc:
        if token.pos_ != "VERB":
            continue
        if token.dep_ not in _EVENT_DEPS:
            continue
        if token.lemma_.lower() in ("be", "have", "do"):
            # A lexical event predicate must not be only a light verb.  Passive
            # and perfect constructions retain the lexical VERB root anyway.
            continue
        out.append(token)
    return out


def _looks_truncated(doc: Any) -> str | None:
    content = [t for t in doc if not t.is_space]
    if not content:
        return "empty_local_doc"
    last = content[-1]
    if last.text in {",", ";", ":", "-", "and", "or", "because", "since", "although", "while", "when", "if", "that", "which", "who", "of", "to", "by", "with", "for", "from", "prior"}:
        return f"trailing_incomplete_token:{last.text}"
    if last.dep_ in {"cc", "mark", "aux", "auxpass"}:
        return f"trailing_incomplete_dep:{last.dep_}"
    return None


def _local_verbal_endpoint(segment: str, local_doc: Any, pred: Any,
                           segment_global_start: int, selected_span: Mapping[str, Any],
                           marker: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    audit: dict[str, Any] = {
        "branch": "local_verbal_predicate",
        "predicate": _token_audit(pred),
        "segment_global_start": segment_global_start,
        "selected_span": dict(selected_span),
        "marker_end": int(marker["marker_end"]),
    }
    subtree = list(pred.subtree)
    head_subtree: list[Any] = []
    # Passive/relative/gerund event predicates may attach to a noun head
    # (dep acl/relcl) rather than being ROOT.  In that case the patient or
    # subject is the head's noun subtree, so keep it with the predicate.
    if (
        pred.dep_ in {"acl", "relcl", "advcl"}
        and pred.head is not None
        and pred.head is not pred
        and pred.head not in subtree
        and pred.head.pos_ in {"NOUN", "PROPN", "PRON"}
    ):
        head_subtree = list(pred.head.subtree)
        subtree = subtree + head_subtree
    if not subtree:
        return None, {**audit, "reason": "empty_predicate_subtree"}
    local_start = min(t.idx for t in subtree)
    local_end = max(t.idx + len(t.text) for t in subtree)
    ls, le, value = _trim_local(segment, local_start, local_end)
    if not value.strip():
        return None, {**audit, "reason": "local_verbal_span_empty", "local_span": [local_start, local_end]}
    g_start = segment_global_start + ls
    g_end = segment_global_start + le
    span_start = int(selected_span["start"])
    span_end = int(selected_span["end"])
    pred_g_start = segment_global_start + pred.idx
    pred_g_end = segment_global_start + pred.idx + len(pred.text)
    audit.update({
        "local_span": [ls, le, value],
        "global_span": [g_start, g_end],
        "predicate_global_span": [pred_g_start, pred_g_end],
        "subtree_token_count": len(subtree),
        "head_subtree_included": bool(head_subtree),
    })
    if g_start < span_start or g_end > span_end:
        return None, {**audit, "reason": "local_verbal_span_outside_selected_span"}
    if not (g_start <= pred_g_start and pred_g_end <= g_end):
        return None, {**audit, "reason": "local_verbal_span_does_not_retain_predicate"}
    if g_start >= g_end:
        return None, {**audit, "reason": "local_verbal_span_invalid"}
    return {
        "start": g_start,
        "end": g_end,
        "text": value,
        "kind": "verbal",
        "branch": "local_verbal_predicate",
        "endpoint_predicate": pred.text,
    }, audit


def _local_second_endpoint(nlp: Any, doc: Any, text: str, marker: Mapping[str, Any],
                           selected_span: Mapping[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    bounds = _selected_bounds(selected_span)
    if bounds is None:
        return None, {"branch": "local", "reason": "invalid_selected_span"}
    span_start, span_end = bounds
    after_start = max(int(marker["marker_end"]), span_start)
    if not (span_start <= after_start < span_end):
        return None, {"branch": "local", "reason": "marker_outside_selected_span"}
    segment = text[after_start:span_end]
    if not segment.strip():
        return None, {"branch": "local", "reason": "no_complement_after_marker"}
    local_doc = nlp(segment)
    truncated = _looks_truncated(local_doc)
    if truncated:
        return None, {"branch": "local_rejected", "reason": "truncated_selected_span",
                      "truncation": truncated, "segment": segment}
    predicates = _event_predicates(local_doc)
    audit: dict[str, Any] = {
        "branch": "local",
        "segment": segment,
        "segment_global_start": after_start,
        "local_predicate_count": len(predicates),
        "local_predicates": [_token_audit(t) for t in predicates],
    }
    if len(predicates) > 1:
        return None, {**audit, "branch": "local_rejected",
                      "reason": "multiple_top_level_event_predicates"}
    if len(predicates) == 1:
        endpoint, verbal_audit = _local_verbal_endpoint(
            segment, local_doc, predicates[0], after_start, selected_span, marker)
        return endpoint, {**audit, **verbal_audit}
    # No admitted local event predicate.  Reject if there is any unexplained
    # lexical VERB in the local complement; otherwise the bounded nominal
    # branch is legal.
    unexplained = [t for t in local_doc if t.pos_ == "VERB" and t.lemma_.lower() not in ("be", "have", "do")]
    if unexplained:
        return None, {
            **audit,
            "branch": "local_rejected",
            "reason": "unresolved_event_predicate_before_nominal_branch",
            "unexplained_verbs": [_token_audit(t) for t in unexplained],
        }
    nominal, nominal_audit = v3._nominal_endpoint_v3(doc, text, marker, selected_span)
    if nominal is None:
        return None, {**audit, "branch": "nominal_rejected", **nominal_audit}
    return nominal, {**audit, "branch": "nominal", **nominal_audit}


def project_clause_order_relations(clause: Mapping[str, Any], text: str,
                                   doc: Any, nlp: Any | None = None) -> dict[str, Any]:
    parser = _nlp_or_default(nlp)
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
        second, second_audit = _local_second_endpoint(parser, doc, text, marker, selected_span)
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
            "second_endpoint_predicate": second.get("endpoint_predicate"),
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
                                   doc: Any, nlp: Any | None = None) -> tuple[list[tuple[str, str]], dict[str, Any]]:
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
        result = project_clause_order_relations(clause, text, doc, nlp=nlp)
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

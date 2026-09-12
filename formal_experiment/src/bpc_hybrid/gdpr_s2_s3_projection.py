# -*- coding: utf-8 -*-
"""Deterministic projection of external Stage-2 predictions onto the
sentence-level six-element record consumed by the four new-type Stage-3
scorers (``stage3_extended_violations.ExtendedViolationScorer``).

Contract (documented, deterministic, Gold-blind)
------------------------------------------------
Input per sentence: one Stage-2 method prediction envelope
``{sample_id, request_status, record: {clauses: [...]}, error_category}``
(clause-level canonical shape produced by the locked Rules-Only runner and
by the Direct-LLM canonical predictions) plus the sentence text the
prediction was made over (the Gold-blind GDPR Stage-2 input pack).

Projection rules
- ``request_status != "ok"`` or non-null ``error_category`` -> failure.
- zero clauses -> ``empty_prediction`` failure (all fields None).
- main clause = clause with the largest ``clause_span`` (ties: first);
- sentence ``modality`` = the main clause's ``modality.label`` (labels
  outside the four-class vocabulary are kept and flagged);
- for each span field in (actor, action, condition, constraint, exception):
  value = the text of the FIRST valid span (0 <= start < end <= len(text))
  in the main clause, else the first valid span in any clause (clause
  order, then span order), else None.  All span texts are additionally
  collected under diagnostics (per-field lists) so downstream misses can be
  explained by the raw predicted spans;
- spans whose coordinates are out of range are counted as invalid and never
  used (the record's canonical validation already enforces text ==
  source[start:end]; the projection re-checks boundaries defensively).

No prediction text is fabricated: values are exact slices of the sentence
text at the predicted coordinates.  Nothing in this module reads Gold,
panel labels or expected violations.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
MODALITY_LABELS = ("definition", "obligation", "permission", "prohibition")
PROJECTION_NAME = "stage2_first_valid_span_projection_v1"


def _span_text(span: Mapping[str, Any], text: str) -> str | None:
    start = span.get("start")
    end = span.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return None
    if start < 0 or end > len(text) or start >= end:
        return None
    return text[start:end]


def _spans_by_id(clause: Mapping[str, Any], field: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index, span in enumerate(_clause_spans(clause, field)):
        if not isinstance(span, Mapping):
            continue
        span_id = str(span.get("id") or f"{field}_{index}")
        result[span_id] = span
    return result


def _actor_action_map_diagnostics(
    main_clause: Mapping[str, Any], sentence_text: str
) -> list[dict[str, Any]]:
    """Preserve the prediction's explicit actor-action links in diagnostics.

    The sentence projection itself still exposes one actor and one action, but
    the canonical downstream record must not invent a pair when the prediction
    supplied no valid actor-action link.  Invalid links (for example a null
    actor id) are kept with ``valid=false`` and an explicit reason.
    """
    actors = _spans_by_id(main_clause, "actor")
    actions = _spans_by_id(main_clause, "action")
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(main_clause.get("actor_action_map") or []):
        if not isinstance(entry, Mapping):
            entries.append({
                "index": index,
                "valid": False,
                "reason": "malformed_actor_action_map_entry",
                "raw": repr(entry),
            })
            continue
        actor_id = entry.get("actor_id")
        action_id = entry.get("action_id")
        actor_span = actors.get(str(actor_id)) if actor_id is not None else None
        action_span = actions.get(str(action_id)) if action_id is not None else None
        actor_text = _span_text(actor_span, sentence_text) if actor_span is not None else None
        action_text = _span_text(action_span, sentence_text) if action_span is not None else None
        reason = None
        if actor_id is None:
            reason = "actor_id_null"
        elif actor_span is None:
            reason = "actor_id_not_found"
        elif actor_text is None:
            reason = "actor_span_invalid"
        elif not action_text:
            reason = "action_span_missing_or_invalid"
        entries.append({
            "index": index,
            "valid": bool(actor_text and action_text),
            "reason": reason,
            "actor_id": actor_id,
            "action_id": action_id,
            "actor_text": actor_text,
            "action_text": action_text,
        })
    return entries


def _raw_order_relations_diagnostics(main_clause: Mapping[str, Any]) -> list[Any]:
    value = main_clause.get("order_relations") or []
    if not isinstance(value, list):
        return [repr(value)]
    result: list[Any] = []
    for entry in value:
        if isinstance(entry, Mapping):
            result.append(dict(entry))
        elif isinstance(entry, (list, tuple)):
            result.append(list(entry))
        else:
            result.append(entry)
    return result


def _clause_spans(clause: Mapping[str, Any], field: str) -> list[Any]:
    entry = clause.get(field)
    if isinstance(entry, dict) and isinstance(entry.get("spans"), list):
        return entry["spans"]
    if isinstance(entry, list):
        return entry
    return list(clause.get(field + "s") or [])


def project_external_sentence(
    pred: Mapping[str, Any],
    sentence_text: str,
    sample_id: str,
) -> dict[str, Any]:
    """Project one Stage-2 prediction envelope onto a six-element sentence
    record.  Returns ``{ok, error, sentence, diagnostics}``."""
    diagnostics: dict[str, Any] = {}
    if not isinstance(pred, dict) or pred.get("sample_id") != sample_id:
        return {"ok": False, "error": "sample_id_mismatch", "sentence": None,
                "diagnostics": diagnostics}
    if pred.get("request_status") != "ok" or pred.get("error_category"):
        return {"ok": False, "error": "prediction_failed", "sentence": None,
                "diagnostics": diagnostics}
    record = pred.get("record") or {}
    clauses = list(record.get("clauses") or [])
    if not clauses:
        return {"ok": False, "error": "empty_prediction", "sentence": None,
                "diagnostics": diagnostics}

    # main clause = largest clause_span (ties: first)
    main_idx = 0
    main_len = -1
    for i, clause in enumerate(clauses):
        span = clause.get("clause_span") or {}
        s, e = span.get("start"), span.get("end")
        length = (e - s) if isinstance(s, int) and isinstance(e, int) else -1
        if length > main_len:
            main_len = length
            main_idx = i

    label_detail = []
    for clause in clauses:
        modality = clause.get("modality") or {}
        span = clause.get("clause_span") or {}
        s, e = span.get("start"), span.get("end")
        length = (e - s) if isinstance(s, int) and isinstance(e, int) else None
        label_detail.append({
            "label": modality.get("label"),
            "clause_len": length,
        })
    modality_label = (clauses[main_idx].get("modality") or {}).get("label")
    if modality_label not in MODALITY_LABELS:
        diagnostics["modality_label_outside_vocabulary"] = modality_label

    sentence: dict[str, Any] = {
        "sentence_text": sentence_text,
        "modality": modality_label if modality_label in MODALITY_LABELS else modality_label,
        "external_sample_id": sample_id,
        "projection": PROJECTION_NAME,
        "diagnostics": diagnostics,
    }
    invalid_span_count = 0
    raw_counts: dict[str, int] = {}
    valid_counts: dict[str, int] = {}
    invalid_spans: list[dict[str, Any]] = []
    main_first: dict[str, list[str]] = {}
    for field in SPAN_FIELDS:
        value: str | None = None
        # value = text of the FIRST VALID span, main clause first, then the
        # remaining clauses in prediction order.  All valid texts are retained
        # below for diagnostics/traceability.
        clause_order = [clauses[main_idx]] + [
            c for i, c in enumerate(clauses) if i != main_idx
        ]
        texts: list[str] = []
        raw_count = 0
        for clause in clause_order:
            for span in _clause_spans(clause, field):
                raw_count += 1
                text = _span_text(span, sentence_text)
                if text is None:
                    invalid_span_count += 1
                    invalid_spans.append({
                        "field": field,
                        "reason": "out_of_range_or_empty_coordinates",
                    })
                    continue
                texts.append(text)
                if value is None:
                    value = text
        sentence[field] = value
        main_first[field] = texts
        raw_counts[field] = raw_count
        valid_counts[field] = len(texts)
    diagnostics["span_field_texts"] = main_first
    diagnostics["span_field_raw_counts"] = raw_counts
    diagnostics["span_field_valid_counts"] = valid_counts
    diagnostics["invalid_spans"] = invalid_spans
    diagnostics["projection_value_policy"] = (
        "first_valid_span_per_field_v1; all valid texts retained under diagnostics"
    )
    diagnostics["actor_action_map"] = _actor_action_map_diagnostics(
        clauses[main_idx], sentence_text
    )
    diagnostics["raw_order_relations"] = _raw_order_relations_diagnostics(
        clauses[main_idx]
    )
    diagnostics["main_clause_index"] = main_idx
    diagnostics["clause_modality_labels"] = label_detail
    diagnostics["invalid_span_count"] = invalid_span_count
    return {"ok": True, "error": None, "sentence": sentence,
            "diagnostics": diagnostics}


def projection_summary(
    projections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Aggregate diagnostics of one projection batch (40 variants)."""
    failed: list[str] = []
    empty_action = 0
    empty_modality = 0
    total_invalid_spans = 0
    for p in projections:
        if not p.get("ok"):
            failed.append(p.get("sample_id", "?"))
            continue
        s = p.get("sentence") or {}
        if not (s.get("action") or "").strip():
            empty_action += 1
        if not s.get("modality"):
            empty_modality += 1
        total_invalid_spans += (p.get("diagnostics") or {}).get(
            "invalid_span_count", 0)
    return {
        "projection": PROJECTION_NAME,
        "total": len(projections),
        "failed": failed,
        "empty_action_sentences": empty_action,
        "empty_modality_sentences": empty_modality,
        "total_invalid_spans": total_invalid_spans,
    }

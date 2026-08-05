"""D1 relay-schema adapter (D1-R1, 2026-08-04, user decision A).

The opencode.ai/zen relay's ``deepseek-v4-flash`` ignores the canonical
schema and returns spans in a nested per-field convention
(``actors=[{actor_id, name, span:{start,end,text}}]``,
``actions=[{action_id, verb, span, object}]``,
``conditions=[{condition_id, type, text, span}]``).  Following the
S2.8D-R3 H1 canonicalizer precedent, this module maps that format back to
the canonical ``{id, text, start, end, normalized}`` spans DETERMINISTICALLY:

* a span container with flat ``text``/``start``/``end`` passes through;
* a span container with a nested ``span`` mapping is unfolded;
* anything else (missing span, non-object containers, non-integer offsets)
  fails closed for the whole record with a stable reason;
* ``normalized`` is the project convention ``" ".join(text.casefold().split())``;
* a missing deterministic ``id`` is assigned ``<clause_id>.<field>.<rank>``;
* modality ``label``/``evidence`` and clause ``clause_span`` pass through
  (they are already canonical in the relay output);
* only structural mapping happens -- text, offsets, labels and content are
  never invented or modified.

The mapped record is then passed to the unique-exact-text span canonicalizer
and the strict canonical validator.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

STATUS_UNCHANGED = "unchanged"
STATUS_ADAPTED = "adapted"
STATUS_FAILED = "failed"

FIELD_TO_PLURAL = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}

MODEL_ID_KEYS = {
    "actors": ("actor_id", "id"),
    "actions": ("action_id", "id"),
    "conditions": ("condition_id", "id"),
    "constraints": ("constraint_id", "id"),
    "exceptions": ("exception_id", "id"),
}


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _unfold_span(container: Any, label: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (canonical span dict, None) or (None, reason)."""
    if not isinstance(container, Mapping):
        return None, f"{label}_not_object"
    text = container.get("text")
    start = container.get("start")
    end = container.get("end")
    if isinstance(text, str) and text and _is_plain_int(start) and _is_plain_int(end):
        return {
            "text": text,
            "start": start,
            "end": end,
            "normalized": _normalized(text),
        }, None
    nested = container.get("span")
    if isinstance(nested, Mapping):
        return _unfold_span(nested, f"{label}.span")
    return None, f"{label}_no_flat_or_nested_span"


def _adapt_field_spans(
    clause: Mapping[str, Any],
    field: str,
    source_text: str,
    failures: list[str],
) -> list[dict[str, Any]]:
    plural = FIELD_TO_PLURAL[field]
    spans = clause.get(plural)
    if spans is None:
        return []
    if not isinstance(spans, list):
        failures.append(f"clauses[].{plural}_not_list")
        return []
    out: list[dict[str, Any]] = []
    for index, item in enumerate(spans):
        span, reason = _unfold_span(item, f"{plural}[{index}]")
        if reason is not None:
            failures.append(reason)
            return []
        if span["text"] not in source_text:
            failures.append(f"{plural}[{index}]_text_not_in_source")
            return []
        span = dict(span)
        id_keys = MODEL_ID_KEYS[plural]
        span_id = next((item[k] for k in id_keys if isinstance(item.get(k), str) and item[k]), None)
        if span_id:
            span["id"] = span_id
        else:
            span["id"] = f"{clause.get('clause_id', 'clause')}.{field}.{index + 1}"
        out.append(span)
    return out


def adapt_relay_record(record: Any, source_text: Any) -> tuple[Any, dict[str, Any]]:
    """Map a relay-format direct-LLM record to the canonical shape.

    Returns ``(adapted_record, audit)``; on failure the original record is
    returned unchanged with ``audit["status"] == "failed"`` and stable
    reasons.
    """
    audit: dict[str, Any] = {
        "attempted": True,
        "status": STATUS_UNCHANGED,
        "spans_adapted": 0,
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

    for ci, clause in enumerate(clauses):
        if not isinstance(clause, Mapping):
            audit["status"] = STATUS_FAILED
            audit["failed_reasons"].append(f"clauses[{ci}]_not_object")
            return record, audit
        for field in FIELD_TO_PLURAL:
            adapted = _adapt_field_spans(clause, field, source_text, audit["failed_reasons"])
            if audit["failed_reasons"]:
                audit["status"] = STATUS_FAILED
                return record, audit
            if adapted:
                audit["spans_adapted"] += len(adapted)
                clause[FIELD_TO_PLURAL[field]] = adapted
        modality = clause.get("modality")
        if modality is not None and not isinstance(modality, Mapping):
            audit["status"] = STATUS_FAILED
            audit["failed_reasons"].append(f"clauses[{ci}]_modality_not_object")
            return record, audit

    audit["status"] = STATUS_ADAPTED if audit["spans_adapted"] else STATUS_UNCHANGED
    return out, audit

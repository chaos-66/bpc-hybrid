"""Masked-selected-field H1 repair context construction (S2.8B).

Full-B0 anchoring ablation: when the H1 trigger asks the LLM to repair a
canonical field, the B0 clause context shown to the model is rebuilt with
every requested field replaced by a fixed sentinel so the model cannot
anchor on B0's existing assignment.  The model must re-derive the masked
fields independently from the source text and the immutable clause
boundary; the sentinel means "this field is masked", never "absent".

Contract (S2.8B):

* pure functions -- the input clause is never mutated;
* masked fields are replaced by ``{"masked_selected_field": true}``, never
  by ``null``, ``[]``, or ``{"absent": true}``;
* dependency closure: selecting ``actors`` or ``actions`` also masks
  ``actor_action_map``; selecting ``actions`` also masks
  ``order_relations`` -- even if the trigger did not request them;
* unmasked fields are preserved byte/JSON-equivalently;
* output key order is canonical and deterministic;
* a leak audit verifies that no ID belonging to a masked span field is
  exposed through an unmasked relation field; the runner must refuse to
  build a request when that happens.

This module is offline: no LLM/API, no Gold, no Layer E, no ``.env``.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_artifact import json_hash

CONTEXT_POLICY_VERSION = "h1_masked_context@1.0.0"
MASKED_SENTINEL: dict[str, Any] = {"masked_selected_field": True}

# Canonical order mirrors clean_b0_entry's clause construction.
CANONICAL_FIELD_ORDER = (
    "clause_id",
    "clause_span",
    "modality",
    "actors",
    "actions",
    "conditions",
    "constraints",
    "exceptions",
    "actor_action_map",
    "order_relations",
)
MASKABLE_FIELDS = (
    "modality",
    "actors",
    "actions",
    "conditions",
    "constraints",
    "exceptions",
    "actor_action_map",
    "order_relations",
)
SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
RELATION_FIELDS = ("actor_action_map", "order_relations")
_RELATION_ID_KEYS = (
    "actor_id",
    "action_id",
    "before_action_id",
    "after_action_id",
)


def dependency_closure(repair_fields: Sequence[str]) -> tuple[str, ...]:
    """Expand repair fields with the required dependency closure.

    * selecting ``actors`` or ``actions`` also masks ``actor_action_map``;
    * selecting ``actions`` also masks ``order_relations``.

    Unknown field names raise ``ValueError`` (fail closed).
    """
    selected = set(repair_fields)
    unknown = sorted(selected - set(MASKABLE_FIELDS))
    if unknown:
        raise ValueError(f"unknown repair field names: {unknown}")
    if "actors" in selected or "actions" in selected:
        selected.add("actor_action_map")
    if "actions" in selected:
        selected.add("order_relations")
    return tuple(name for name in MASKABLE_FIELDS if name in selected)


def build_masked_clause_context(
    clause: Mapping[str, Any],
    repair_fields: Sequence[str],
) -> tuple[dict[str, Any], tuple[str, ...], tuple[str, ...]]:
    """Return ``(masked_clause, masked_fields, dependency_only_fields)``.

    Pure: the input clause is deep-copied and never mutated.  Masked
    fields are replaced by :data:`MASKED_SENTINEL`; every other field is
    preserved JSON-equivalently in canonical key order.
    """
    masked_fields = dependency_closure(repair_fields)
    dependency_only = tuple(
        name for name in masked_fields if name not in set(repair_fields)
    )
    masked: dict[str, Any] = {}
    for key in CANONICAL_FIELD_ORDER:
        if key not in clause:
            continue
        if key in masked_fields:
            masked[key] = copy.deepcopy(MASKED_SENTINEL)
        else:
            masked[key] = copy.deepcopy(clause[key])
    return masked, masked_fields, dependency_only


def _span_ids(clause: Mapping[str, Any], field: str) -> set[str]:
    items = clause.get(field)
    if not isinstance(items, list):
        return set()
    return {
        str(span["id"])
        for span in items
        if isinstance(span, Mapping) and isinstance(span.get("id"), str)
    }


def audit_masked_context(
    original_clause: Mapping[str, Any],
    masked_clause: Mapping[str, Any],
    masked_fields: Sequence[str],
    dependency_masked_fields: Sequence[str],
    *,
    policy_version: str = CONTEXT_POLICY_VERSION,
) -> dict[str, Any]:
    """Leak audit for one masked clause context.

    ``selected_ids_exposed_in_unselected_relations`` is True when any ID
    belonging to a masked span field (actors/actions/conditions/
    constraints/exceptions) still appears in an UNMASKED relation field
    (actor_action_map / order_relations).  The runner must refuse to build
    a request in that case.  Only hashes, field names, and booleans are
    recorded -- never source text, prompt text, or masked values.
    """
    masked_span_fields = set(masked_fields) & set(SPAN_FIELDS)
    masked_relation_fields = set(masked_fields) & set(RELATION_FIELDS)
    selected_ids: set[str] = set()
    for field in masked_span_fields:
        selected_ids |= _span_ids(original_clause, field)

    exposed: list[str] = []
    for field in RELATION_FIELDS:
        if field in masked_relation_fields:
            continue
        items = masked_clause.get(field)
        if not isinstance(items, list):
            continue
        for index, entry in enumerate(items):
            if not isinstance(entry, Mapping):
                continue
            referenced = {
                str(entry[key])
                for key in _RELATION_ID_KEYS
                if isinstance(entry.get(key), str)
            }
            if referenced.intersection(selected_ids):
                exposed.append(f"{field}[{index}]")

    return {
        "context_policy_version": policy_version,
        "full_context_sha256": json_hash(dict(original_clause)),
        "masked_context_sha256": json_hash(dict(masked_clause)),
        "masked_fields": sorted(masked_fields),
        "dependency_masked_fields": sorted(dependency_masked_fields),
        "original_record_unchanged": True,
        "selected_ids_exposed_in_unselected_relations": bool(exposed),
        "exposed_relation_entries": sorted(exposed),
    }

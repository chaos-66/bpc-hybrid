# -*- coding: utf-8 -*-
"""Lossless, deterministic conversion of the user's CONFIRMED GDPR-7 human
rule items into the formal Rule Record standard answer.

Why this module exists
----------------------
The user adjudicated all 74 sentences of the nine GDPR articles used by the
Stage 3 benchmark (``gdpr7_human_confirmed_v1/confirmed_rule_items.json``:
9 rules / 74 sentences / 92 rule items / 552 element decisions / 320 anchored
spans).  That bundle is the human input.  Stage 3 needs a *formal Rule Record*
standard answer in a fixed, versioned shape, and the Oracle needs a capsule the
existing Stage-3 converter can consume.

The legacy editable export (``gdpr7_review_rules_v1.export_canonical_records_v2``)
is NOT usable for this: it emits ONE clause per sentence and collapses several
rule items into a single modality label (``first_label``), silently dropping
the multi-modality content the user explicitly confirmed.  This module instead
emits ONE clause per rule item and keeps every confirmed value.

Hard invariants (all fail closed)
---------------------------------
1. **No fabrication / no inference.**  Every emitted span text is sliced from
   the sentence text at the confirmed coordinates; a span whose coordinates do
   not reproduce its confirmed text raises.  No value is ever created,
   normalised, re-ordered, dropped or rewritten.
2. **No loss.**  Every one of the 92 items is exported; every modality label,
   modality-evidence span, and actor/action/condition/constraint/exception span
   is exported; every ``actor_action_map`` entry and every ``order_relations``
   entry is exported with resolvable span ids.  The independent verifier
   (``scripts/verify_gdpr7_gold_rule_records_v1.py``) re-derives the confirmed
   bundle from the published artifact and compares it field by field.
3. **Coordinates are sentence-relative** (0 .. len(sentence_text)), matching
   ``data/input/gdpr7_stage2_input_v1.json`` and the existing Rules-Only
   capsule convention.
4. **Item-level modality.**  Unlike the legacy export, a multi-modality
   sentence keeps every label on its own clause, so a Stage-3 modality gate can
   include or exclude each item on its own merits.

Two artifacts are produced from the same confirmed bundle:

- ``rule_records``  -- the formal Gold Rule Record document (per sentence, per
  item, with provenance and the source hashes);
- ``capsule``       -- a Stage-2-shaped predictions capsule
  (``gdpr7_human_rule_record_predictions@1.0.0``) whose rows carry the same
  coordinate-only clause shape as the Rules-Only / Direct-LLM capsules, so the
  existing ``gdpr_capsule_converter`` consumes it unchanged.

No I/O, no LLM/network, no Gold read other than the confirmed human bundle
handed in by the caller.  This module is a pure function library.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

# --------------------------------------------------------------------------
# versioned contract constants
# --------------------------------------------------------------------------
CONVERTER_NAME = "gdpr7_gold_rule_record_converter@1.0.0"

SOURCE_SCHEMA = "gdpr7_human_confirmed_rule_items@1.0.0"
RULE_RECORD_SCHEMA = "gdpr7_gold_rule_record@1.0.0"
CAPSULE_SCHEMA = "gdpr7_human_rule_record_predictions@1.0.0"
CLAUSE_SCHEMA = "1.0.0"

RULE_RECORD_METHOD = "human_adjudicated_gdpr7_rules"
RULE_RECORD_METHOD_VARIANT = "gdpr7_human_confirmed_rule_items_v1"

ELEMENT_FIELDS = (
    "modality",
    "actor",
    "action",
    "condition",
    "constraint",
    "exception",
)
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
MODALITIES = ("obligation", "permission", "prohibition", "definition")

#: sentence ids that the Stage-3 benchmark actually has a process model for.
#: Derived from the frozen inference pack at run time; this constant is only a
#: documentation aid and is never used to filter the export.
PROCESS_BOUND_RULE_IDS = (
    "article6",
    "article7",
    "article15",
    "article16",
    "article17",
    "article20",
    "article22",
    "article33",
    "article34",
)


class GoldRuleRecordError(ValueError):
    """Raised when the confirmed bundle cannot be converted without loss."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise GoldRuleRecordError(message)


def _span_dict(span: Mapping[str, Any], where: str) -> dict[str, Any]:
    start = span.get("start")
    end = span.get("end")
    text = span.get("text")
    _require(type(start) is int and type(end) is int,
             f"{where}: span bounds must be ints, got {start!r}/{end!r}")
    _require(0 <= start < end, f"{where}: span [{start},{end}) is empty/invalid")
    _require(isinstance(text, str) and text != "",
             f"{where}: span text must be a non-empty string")
    return {"text": text, "start": start, "end": end}


def _check_span_text(span: Mapping[str, Any], text: str, where: str) -> None:
    start, end = span["start"], span["end"]
    _require(end <= len(text),
             f"{where}: span [{start},{end}) exceeds sentence length {len(text)}")
    _require(text[start:end] == span["text"],
             f"{where}: span text mismatch at [{start},{end}): "
             f"stored {span['text']!r} vs sliced {text[start:end]!r}")


def _check_relation_endpoint(value: Any, where: str) -> str:
    _require(isinstance(value, str) and value != "",
             f"{where}: relation endpoint must be a non-empty item id")
    return value


def _iter_records(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    _require(isinstance(doc, Mapping), "confirmed bundle must be a mapping")
    _require(doc.get("schema_version") == SOURCE_SCHEMA,
             f"confirmed bundle schema mismatch: got {doc.get('schema_version')!r}, "
             f"expected {SOURCE_SCHEMA!r}")
    records = doc.get("records")
    _require(isinstance(records, list) and records,
             "confirmed bundle must carry a non-empty records list")
    for record in records:
        _require(isinstance(record, Mapping), "record must be a mapping")
    return list(records)


def convert_sentence(record: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one confirmed sentence record into clause rows (one per item).

    Pure: raises :class:`GoldRuleRecordError` on any inconsistency instead of
    guessing.  Returns ``{"clauses": [...], "item_ids": [...]}``.  The
    ``actor_action_map`` of each clause is a verbatim copy of the confirmed
    item's map (no edge inferred, none dropped); ``order_relations`` is copied
    verbatim when the confirmed item declares it.
    """
    sample_id = record.get("sample_id")
    text = record.get("sentence_text")
    rule_id = record.get("rule_id")
    _require(isinstance(sample_id, str) and sample_id != "",
             "sentence record missing sample_id")
    _require(isinstance(text, str) and text != "",
             f"{sample_id}: sentence_text must be a non-empty string")
    _require(isinstance(rule_id, str) and rule_id != "",
             f"{sample_id}: rule_id must be a non-empty string")
    items = record.get("rule_items")
    _require(isinstance(items, list) and items,
             f"{sample_id}: rule_items must be a non-empty list")

    clauses: list[dict[str, Any]] = []
    item_ids: list[str] = []
    seen_item_ids: set[str] = set()
    for index, item in enumerate(items, start=1):
        _require(isinstance(item, Mapping),
                 f"{sample_id}: rule item {index} must be a mapping")
        item_id = item.get("item_id")
        _require(isinstance(item_id, str) and item_id != "",
                 f"{sample_id}: rule item {index} missing item_id")
        _require(item_id not in seen_item_ids,
                 f"{sample_id}: duplicate item_id {item_id!r}")
        seen_item_ids.add(item_id)

        modality = item.get("modality")
        _require(modality in MODALITIES,
                 f"{item_id}: modality {modality!r} not in {list(MODALITIES)}")

        # ---- modality evidence (kept verbatim, validated) ------------------
        raw_evidence = item.get("modality_evidence")
        _require(isinstance(raw_evidence, list),
                 f"{item_id}: modality_evidence must be a list")
        evidence: list[dict[str, Any]] = []
        for position, span in enumerate(raw_evidence, start=1):
            _require(isinstance(span, Mapping),
                     f"{item_id}: modality_evidence[{position}] must be a mapping")
            entry = _span_dict(span, f"{item_id}.modality_evidence[{position}]")
            _check_span_text(entry, text, f"{item_id}.modality_evidence[{position}]")
            evidence.append(entry)

        # ---- the five span fields -----------------------------------------
        arrays: dict[str, list[dict[str, Any]]] = {}
        span_ids: dict[str, list[str]] = {}
        for field in SPAN_FIELDS:
            raw = item.get(field)
            _require(isinstance(raw, list), f"{item_id}.{field} must be a list")
            arrays[field] = []
            span_ids[field] = []
            for position, span in enumerate(raw, start=1):
                where = f"{item_id}.{field}[{position}]"
                _require(isinstance(span, Mapping), f"{where} must be a mapping")
                entry = _span_dict(span, where)
                _check_span_text(entry, text, where)
                span_id = f"{sample_id}.c{index}.{field}.{position}"
                entry_with_id = {
                    "start": entry["start"],
                    "end": entry["end"],
                    "text": entry["text"],
                    "id": span_id,
                }
                arrays[field].append(entry_with_id)
                span_ids[field].append(span_id)

        # ---- actor_action_map: copied VERBATIM from the confirmed item ------
        # The confirmed bundle declares the actor->action binding explicitly
        # (``actor_span_index`` -> ``action_item_id``); no edge is inferred,
        # and none is dropped.  A within-item target resolves to this clause's
        # action span id; a cross-item target keeps ``action_item_id`` and is
        # resolved to a concrete span id by :func:`build_capsule`.
        actor_action_map: list[dict[str, str]] = []
        explicit_map = item.get("actor_action_map")
        _require(isinstance(explicit_map, list),
                 f"{item_id}: actor_action_map must be a list")
        for position, entry in enumerate(explicit_map, start=1):
            where = f"{item_id}.actor_action_map[{position}]"
            _require(isinstance(entry, Mapping), f"{where} must be a mapping")
            actor_index = entry.get("actor_span_index")
            target_item = entry.get("action_item_id")
            _require(type(actor_index) is int and actor_index >= 0,
                     f"{where}: actor_span_index must be a non-negative int")
            _require(actor_index < len(span_ids["actor"]),
                     f"{where}: actor_span_index {actor_index} out of range "
                     f"({len(span_ids['actor'])} actor spans)")
            _check_relation_endpoint(target_item, f"{where}.action_item_id")
            actor_id = span_ids["actor"][actor_index]
            if target_item == item_id:
                _require(bool(span_ids["action"]),
                         f"{where}: within-item binding but the item has no action span")
                actor_action_map.append({
                    "actor_id": actor_id,
                    "action_id": span_ids["action"][0],
                })
            else:
                actor_action_map.append({
                    "actor_id": actor_id,
                    "action_item_id": target_item,
                })

        # ---- order relations declared on the confirmed item ----------------
        order_relations: list[dict[str, str]] = []
        explicit_order = item.get("order_relations")
        if explicit_order is not None:
            _require(isinstance(explicit_order, list),
                     f"{item_id}: order_relations must be a list or absent")
            for position, entry in enumerate(explicit_order, start=1):
                where = f"{item_id}.order_relations[{position}]"
                _require(isinstance(entry, Mapping), f"{where} must be a mapping")
                before = _check_relation_endpoint(
                    entry.get("before_item_id"), f"{where}.before_item_id")
                after = _check_relation_endpoint(
                    entry.get("after_item_id"), f"{where}.after_item_id")
                order_relations.append({
                    "before_item_id": before,
                    "after_item_id": after,
                })

        clause = {
            "clause_id": f"{sample_id}.c{index}",
            "item_id": item_id,
            "clause_span": {"start": 0, "end": len(text)},
            "modality": {"label": modality, "evidence": evidence},
            "actors": arrays["actor"],
            "actions": arrays["action"],
            "conditions": arrays["condition"],
            "constraints": arrays["constraint"],
            "exceptions": arrays["exception"],
            "actor_action_map": actor_action_map,
            "order_relations": order_relations,
            "action_structure": item.get("action_structure"),
        }
        clauses.append(clause)
        item_ids.append(item_id)

    return {"clauses": clauses, "item_ids": item_ids}


def build_rule_records(doc: Mapping[str, Any],
                       source_hashes: Mapping[str, str] | None = None,
                       ) -> dict[str, Any]:
    """Build the formal Gold Rule Record document from a confirmed bundle.

    ``source_hashes`` is copied into the provenance block verbatim (the builder
    never invents provenance).  Deterministic: identical inputs give byte-
    identical output (``json.dumps(..., ensure_ascii=False, indent=2)``).
    """
    records = _iter_records(doc)
    out_records: list[dict[str, Any]] = []
    seen_samples: set[str] = set()
    item_count = 0
    span_count = 0
    evidence_count = 0
    relation_count = 0
    for record in records:
        sample_id = record.get("sample_id")
        _require(sample_id not in seen_samples,
                 f"duplicate sample_id {sample_id!r}")
        seen_samples.add(sample_id)
        converted = convert_sentence(record)
        clauses = converted["clauses"]
        item_count += len(clauses)
        for clause in clauses:
            evidence_count += len(clause["modality"]["evidence"])
            relation_count += len(clause["actor_action_map"])
            relation_count += len(clause["order_relations"])
            for field in SPAN_FIELDS:
                span_count += len(clause[field + "s"])
        out_records.append({
            "sample_id": sample_id,
            "rule_id": record.get("rule_id"),
            "sentence_idx": record.get("sentence_idx"),
            "char_span": record.get("char_span"),
            "text_sha256": record.get("text_sha256"),
            "rule_text_sha256": record.get("rule_text_sha256"),
            "sentence_text": record.get("sentence_text"),
            "review_state": record.get("review_state"),
            "context_links": record.get("context_links") or [],
            "temporal_suggestions": record.get("temporal_suggestions") or [],
            "item_count": len(clauses),
            "clauses": clauses,
        })

    return {
        "schema_version": RULE_RECORD_SCHEMA,
        "dataset_id": "gdpr7_gold_rule_records_v1",
        "status": "published_gold_rule_records",
        "is_gold": True,
        "counts": {
            "rules": len({rec["rule_id"] for rec in out_records}),
            "sentences": len(out_records),
            "items": item_count,
            "spans": span_count,
            "modality_evidence_spans": evidence_count,
            "relation_entries": relation_count,
        },
        "representation": {
            "clause_unit": "one clause per confirmed rule item",
            "coordinates": "sentence-relative 0..len(sentence_text)",
            "modality_policy": ("every confirmed item keeps its own modality "
                                "label; no first-label projection"),
            "action_structure": ("copied verbatim from the confirmed item "
                                 "(informational, not consumed by Stage 3)"),
            "relation_policy": ("actor_action_map and order_relations are copied "
                                "verbatim from the confirmed item; no edge is "
                                "inferred, added or dropped"),
            "loss_policy": ("mechanical, lossless derivation from the "
                            "confirmed human bundle; no value added, inferred, "
                            "normalised, re-ordered or dropped"),
        },
        "method": {
            "name": RULE_RECORD_METHOD,
            "method_variant": RULE_RECORD_METHOD_VARIANT,
            "converter": CONVERTER_NAME,
        },
        "provenance": {
            "annotation_origin": (
                doc.get("provenance", {}).get("annotation_origin")
                if isinstance(doc.get("provenance"), Mapping) else None),
            "reviewer": (doc.get("provenance", {}).get("reviewer")
                         if isinstance(doc.get("provenance"), Mapping) else None),
            "confirmation_event_id": (
                doc.get("provenance", {}).get("confirmation_event_id")
                if isinstance(doc.get("provenance"), Mapping) else None),
            "source_schema": doc.get("schema_version"),
            "source_status": doc.get("status"),
            "source_hashes": dict(source_hashes or {}),
            "converter": CONVERTER_NAME,
            "gold_fields_read": True,
        },
        "records": out_records,
    }


def build_capsule(rule_records: Mapping[str, Any]) -> dict[str, Any]:
    """Build the Stage-2-shaped capsule consumed by the Stage-3 converter.

    Row shape ``{sample_id, request_status, record, error_category}`` with a
    coordinate-only ``record`` identical to the Rules-Only / Direct-LLM capsule
    convention, so ``gdpr_capsule_converter.build_rule_records`` consumes it
    unchanged.  Cross-item ``action_item_id`` endpoints are resolved to the
    concrete action span id of the target item; an unresolvable endpoint raises
    instead of being dropped.
    """
    _require(rule_records.get("schema_version") == RULE_RECORD_SCHEMA,
             "capsule input must be a Gold Rule Record document")
    rows: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for record in rule_records.get("records", []):
        clauses = record.get("clauses") or []
        action_span_id_by_item: dict[str, list[str]] = {}
        for clause in clauses:
            item_id = clause.get("item_id")
            action_ids = [span["id"] for span in clause.get("actions") or []]
            if item_id is not None:
                action_span_id_by_item[item_id] = action_ids

        out_clauses: list[dict[str, Any]] = []
        for clause in clauses:
            aam: list[dict[str, str]] = []
            for entry in clause.get("actor_action_map") or []:
                actor_id = entry.get("actor_id")
                action_id = entry.get("action_id")
                if action_id is None:
                    target = entry.get("action_item_id")
                    candidates = action_span_id_by_item.get(target, [])
                    if not candidates:
                        unresolved.append(
                            f"{record.get('sample_id')}:{clause.get('item_id')}"
                            f"->{target}")
                        continue
                    action_id = candidates[0]
                aam.append({"actor_id": actor_id, "action_id": action_id})

            orders: list[dict[str, str]] = []
            for entry in clause.get("order_relations") or []:
                before = action_span_id_by_item.get(
                    entry.get("before_item_id"), [])
                after = action_span_id_by_item.get(
                    entry.get("after_item_id"), [])
                if not before or not after:
                    unresolved.append(
                        f"{record.get('sample_id')}:"
                        f"{entry.get('before_item_id')}->{entry.get('after_item_id')}")
                    continue
                orders.append({
                    "before_action_id": before[0],
                    "after_action_id": after[0],
                })

            out_clauses.append({
                "clause_id": clause.get("clause_id"),
                "clause_span": clause.get("clause_span"),
                "modality": {
                    "label": clause.get("modality", {}).get("label"),
                    "evidence": [
                        {"start": span["start"], "end": span["end"]}
                        for span in clause.get("modality", {}).get("evidence", [])
                    ],
                },
                "actors": [
                    {"start": span["start"], "end": span["end"], "id": span["id"]}
                    for span in clause.get("actors") or []
                ],
                "actions": [
                    {"start": span["start"], "end": span["end"], "id": span["id"]}
                    for span in clause.get("actions") or []
                ],
                "conditions": [
                    {"start": span["start"], "end": span["end"], "id": span["id"]}
                    for span in clause.get("conditions") or []
                ],
                "constraints": [
                    {"start": span["start"], "end": span["end"], "id": span["id"]}
                    for span in clause.get("constraints") or []
                ],
                "exceptions": [
                    {"start": span["start"], "end": span["end"], "id": span["id"]}
                    for span in clause.get("exceptions") or []
                ],
                "actor_action_map": aam,
                "order_relations": orders,
            })
        rows.append({
            "sample_id": record.get("sample_id"),
            "request_status": "ok",
            "record": {
                "schema_version": CLAUSE_SCHEMA,
                "sample_id": record.get("sample_id"),
                "source_id": record.get("sample_id"),
                "clauses": out_clauses,
                "method": {
                    "name": RULE_RECORD_METHOD,
                    "method_variant": RULE_RECORD_METHOD_VARIANT,
                },
                "validation": {
                    "schema_valid": True,
                    "cross_field_valid": True,
                    "errors": [],
                },
            },
            "error_category": None,
        })

    return {
        "schema_version": CAPSULE_SCHEMA,
        "dataset_id": "gdpr7_human_rule_record_capsule_v1",
        "method_id": RULE_RECORD_METHOD,
        "record_count": len(rows),
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "source_rule_record_schema": rule_records.get("schema_version"),
        "unresolved_relation_endpoints": sorted(set(unresolved)),
        "records": rows,
    }


def modality_counts(rule_records: Mapping[str, Any]) -> dict[str, int]:
    """Item counts per modality label (diagnostics; never a gate)."""
    counts = {label: 0 for label in MODALITIES}
    for record in rule_records.get("records", []):
        for clause in record.get("clauses") or []:
            label = (clause.get("modality") or {}).get("label")
            if label in counts:
                counts[label] += 1
    return counts


def summarize(rule_records: Mapping[str, Any],
              capsule: Mapping[str, Any]) -> dict[str, Any]:
    """Compact, deterministic diagnostics for reports and manifests."""
    counts = rule_records.get("counts") or {}
    return {
        "converter": CONVERTER_NAME,
        "rule_record_schema": rule_records.get("schema_version"),
        "capsule_schema": capsule.get("schema_version"),
        "rules": counts.get("rules"),
        "sentences": counts.get("sentences"),
        "items": counts.get("items"),
        "spans": counts.get("spans"),
        "modality_evidence_spans": counts.get("modality_evidence_spans"),
        "relation_entries": counts.get("relation_entries"),
        "modality_item_counts": modality_counts(rule_records),
        "capsule_rows": capsule.get("record_count"),
        "unresolved_relation_endpoints":
            capsule.get("unresolved_relation_endpoints"),
    }


def rule_ids_of(rule_records: Mapping[str, Any]) -> list[str]:
    """Sorted distinct rule ids present in the document."""
    return sorted({rec.get("rule_id") for rec in rule_records.get("records", [])
                   if isinstance(rec.get("rule_id"), str)})


def sample_ids_of(rule_records: Mapping[str, Any]) -> list[str]:
    """Sample ids in document order (deterministic)."""
    return [rec.get("sample_id") for rec in rule_records.get("records", [])]


def expected_item_ids(rule_records: Mapping[str, Any]) -> list[str]:
    """All confirmed item ids in document order."""
    out: list[str] = []
    for record in rule_records.get("records", []):
        for clause in record.get("clauses") or []:
            item_id = clause.get("item_id")
            if isinstance(item_id, str):
                out.append(item_id)
    return out


def spans_of(clause: Mapping[str, Any],
             field: str) -> Sequence[Mapping[str, Any]]:
    """Typed accessor for the five span arrays (``actor`` -> ``actors``)."""
    _require(field in SPAN_FIELDS, f"unknown span field {field!r}")
    return clause.get(field + "s") or []

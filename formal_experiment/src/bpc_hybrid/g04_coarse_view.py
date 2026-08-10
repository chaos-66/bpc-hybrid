# -*- coding: utf-8 -*-
"""G0.4 sentence-level coarse view transform (shared, zero-API).

Deterministically derives the sentence-level coarse Gold view from the
PUBLISHED formal Stage 2 Gold (data/gold/stage2/estg150_formal_gold_v1.json).
The same transform feeds the coarse-view evidence manifest, the B0 formal
arm evaluation and the D1/H1 zero-API candidate re-evaluations, so all
methods share one versioned normalization.

Rule (identical to the historical sentence-level coarse gold, 2026-08-07
user-confirmed main view): one synthetic clause per sentence over
[0, len(approved_text_en)); per field one span [min(start), max(end)) over
all annotated spans in the sentence; absent fields stay absent; text =
approved_text_en slice; modality label = first non-empty clause modality
string; modality evidence = merged clause spans (the published Gold carries
modality as a plain string, so local modality evidence spans are NOT
reproducible -- see the G0.4 contract for the publication gate).

IMPORTANT: the derived view does NOT match the historical coarse gold's
semantic hash (modality evidence differs on 147/150 records); per the G0.4
contract the coarse view is therefore evidence/diagnostic only, and the
formal coarse MAIN-view metrics are NOT published. The six-field span
metrics (5 fields) and modality-label metrics remain computable.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
PLURAL_KEYS = {"actor": "actors", "action": "actions", "condition": "conditions",
               "constraint": "constraints", "exception": "exceptions"}
# historical sentence-level coarse gold semantic hash (2026-08-07 decision)
HISTORICAL_COARSE_SEMANTIC_SHA = (
    "6e19cf3c684a26aa9e9fdc9f76c3529b5a4232aecb085fad4c206ceb177bcb26")


def semantic_hash_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _field_span_ranges(clause: dict[str, Any], field: str) -> list[tuple[int, int]]:
    if field == "modality":
        # published formal Gold carries modality as a plain string; evidence
        # falls back to the clause span (same semantics as the canonical
        # gold builder: modality span null -> clause span)
        cs = clause.get("clause_span") or {}
        if isinstance(cs.get("start"), int) and isinstance(cs.get("end"), int):
            return [(cs["start"], cs["end"])]
        return []
    items = clause.get(PLURAL_KEYS[field]) or []
    out = []
    for item in items:
        if isinstance(item.get("start"), int) and isinstance(item.get("end"), int):
            out.append((item["start"], item["end"]))
    return out


def coarse_record(gold_record: dict[str, Any]) -> dict[str, Any]:
    sample_id = gold_record.get("sample_id")
    source_text = gold_record.get("approved_text_en")
    if not isinstance(sample_id, str) or not isinstance(source_text, str) or not source_text:
        raise ValueError(f"record lacks sample_id or approved_text_en: {sample_id}")

    modality_label: str | None = None
    clause_ranges: dict[str, list[tuple[int, int]]] = {f: [] for f in FIELDS}
    for clause in gold_record.get("clauses") or []:
        if modality_label is None:
            label = clause.get("modality")
            if isinstance(label, str) and label:
                modality_label = label
        for field in FIELDS:
            clause_ranges[field].extend(_field_span_ranges(clause, field))

    merged: dict[str, list[dict[str, Any]]] = {}
    for field in FIELDS:
        ranges = clause_ranges[field]
        if not ranges:
            merged[field] = []
            continue
        start = min(r[0] for r in ranges)
        end = max(r[1] for r in ranges)
        if not (0 <= start < end <= len(source_text)):
            raise ValueError(f"{sample_id} {field} merged span outside sentence")
        text = source_text[start:end]
        span: dict[str, Any] = {"id": f"{sample_id}_sent_{field}",
                                "text": text, "start": start, "end": end}
        if field != "modality":
            span["normalized"] = _normalized(text)
        merged[field] = [span]

    sentence_clause: dict[str, Any] = {
        "clause_id": f"{sample_id}_sentence",
        "clause_span": {"text": source_text, "start": 0, "end": len(source_text)},
        "modality": {"label": modality_label, "evidence": merged["modality"]},
        "actor_action_map": [],
        "order_relations": [],
    }
    for field in ("actor", "action", "condition", "constraint", "exception"):
        sentence_clause[PLURAL_KEYS[field]] = merged[field]

    return {
        "schema_version": gold_record.get("schema_version", "1.0.0"),
        "sample_id": sample_id,
        "source_id": f"estg_legacy_{int(sample_id.rsplit('_', 1)[1])}",
        "source_text": source_text,
        "clauses": [sentence_clause],
        "method": {"name": "coarse_sentence_level_variant",
                   "schema_source": "b0_coarse_gold_sentence@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True,
                       "errors": []},
    }


def build_coarse_view(gold_doc: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    seen: set[str] = set()
    for rec in sorted(gold_doc["records"], key=lambda r: r["sample_id"]):
        if rec["sample_id"] in seen:
            raise ValueError(f"duplicate sample_id: {rec['sample_id']}")
        seen.add(rec["sample_id"])
        records.append(coarse_record(rec))
    if len(records) != 150:
        raise ValueError(f"coarse view must have 150 records, got {len(records)}")
    return records

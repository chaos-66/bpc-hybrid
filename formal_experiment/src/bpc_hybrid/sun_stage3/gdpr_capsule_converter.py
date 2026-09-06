# -*- coding: utf-8 -*-
"""Deterministic converter: EXTERNAL GDPR Rules-Only Stage-2 capsule -> the
Sun-rule-record shape consumed by the frozen Sun Stage-3 scorer.

Why this module exists
----------------------
The S3.5 development pipeline (``scripts/run_sun_stage3_development.py``)
feeds the frozen Sun scorer (Definitions 4-7, ``src/bpc_hybrid/sun_stage3/
sun_scorer.py``) with a Gold-blind **development Rule Record adapter**
(``src/bpc_hybrid/sun_stage3/sun_rule_extraction.py``: spaCy dependency
parsing + signalword lexicon over the whole rule text).  This converter is
the Stage-2 -> Stage-3 linkage experiment's substitute source: it builds the
SAME rule-record shape (``actions`` / ``actors`` / ``order_relations``) from
the EXTERNAL Rules-Only predictions capsule
(``data/predictions/gdpr7_sun_rule_only_v1/predictions.json``,
schema ``gdpr7_sun_rule_only_predictions@1.0.0``) that was produced by the
locked B0 v10a pipeline over the same 9 GDPR rule texts.

Shape contract (mirrors ``sun_rule_extraction.extract_rule_record`` output)
--------------------------------------------------------------------------
The scorer consumes exactly three rule fields:

- ``actions: list[str]``        -- Definition 4/5 rule actions (verb-phrase
  texts the rule requires to be executable);
- ``actors: list[str]``         -- Definition 4/6 rule actors;
- ``order_relations: list[(str, str)]`` -- Definition 7 order constraints
  ``(before_text, after_text)`` whose endpoints are matched against process
  actions by the scorer.

Modality gate (fixed v1 policy, documented)
-------------------------------------------
- The development adapter only keeps *obligation* sentences (it detects the
  signalwords ``shall/must/should/may`` and calls every such sentence
  ``modality=obligation``).  The capsule carries an explicit, validated
  per-clause modality label.  The converter therefore keeps **only clauses
  whose ``modality.label`` is ``"obligation"``** -- i.e. the rule actions and
  actors that the process is required to perform, which is the semantic
  content Definitions 5-6 compare against a process model.  Permission,
  prohibition and definition clauses are excluded and the exclusion is
  counted per rule in the diagnostics (never silently dropped).
- All other spans the capsule exposes (conditions / constraints / exceptions)
  are NOT consumed by the Sun scorer and are not converted.

Text reconstruction contract
----------------------------
Every clause span (actors/actions/etc.) is a character offset into the
sentence's ``approved_text_en`` (``data/input/gdpr7_stage2_input_v1.json``,
sample_id ``gdpr_articleNN_sNNN``).  The converter validates
``0 <= start < end <= len(sentence_text)`` for every span it slices and
reconstructs texts by slicing; it never uses a span's raw text (none is
stored) and never fabricates text.

Order relations in the frozen capsule
-------------------------------------
All 74 records are ``request_status == "ok"`` with valid records; however
every clause carries ``order_relations == []`` and the record-level field is
``null``.  The Definition-7 input therefore cannot be produced from this
capsule: the converter returns an empty ``order_relations`` list (never
fabricated) and reports ``order_relations_absent`` per rule.  A capsule that
did carry order relations with the same span contract would be converted the
same way (documented in ``provenance.mapping``), but no such rows exist in
the frozen capsule and the converter does not guess their shape.

Failure/empty envelopes
-----------------------
A sentence whose capsule envelope is missing, not ``ok``, or carries no
clauses is a per-rule failure: the sentence contributes nothing (no
fabricated fields) and the failure is counted in the summary.  If every
sentence of a rule fails, the rule record is returned with ``failed=True``
and ``failure_reasons`` populated; downstream item rows must carry an
explicit external-failure marker (see the linkage runner) instead of being
silently treated as compliant.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

CONVERTER_NAME = "gdpr_capsule_rule_record_converter@1.0.0"
CAPSULE_SCHEMA = "gdpr7_sun_rule_only_predictions@1.0.0"
DEFAULT_INCLUDE_MODALITIES = ("obligation",)
RECORD_SCHEMA = "sun_rule_record_capsule_v1@1.0.0"


def sentence_texts_by_sample(input_doc: Mapping[str, Any]) -> dict[str, str]:
    """sample_id -> approved_text_en from the frozen Stage-2 input pack."""
    out: dict[str, str] = {}
    for rule in input_doc.get("rules", []):
        for s in rule.get("sentences", []):
            sid = s.get("sample_id")
            text = s.get("approved_text_en")
            if sid is None or not isinstance(text, str):
                raise ValueError(f"input pack sentence missing sample_id/text: {s!r}")
            out[sid] = text
    return out


def _span_text(text: str, span: Mapping[str, Any], where: str, bad: list[str]) -> str | None:
    start, end = span.get("start"), span.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        bad.append(f"{where}: non-int span bounds {span!r}")
        return None
    if not (0 <= start < end <= len(text)):
        bad.append(f"{where}: span [{start},{end}) out of bounds for text len {len(text)}")
        return None
    return text[start:end]


def _dedupe(seq: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in seq:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _sample_rule_id(sample_id: str) -> str | None:
    # gdpr_article33_s001 -> article33
    if not sample_id.startswith("gdpr_"):
        return None
    rest = sample_id[len("gdpr_"):]
    if "_s" not in rest:
        return None
    return rest.split("_s", 1)[0]


def build_rule_records(
    capsule: Mapping[str, Any],
    texts_by_sample: Mapping[str, str],
    rule_ids: Sequence[str],
    include_modalities: Sequence[str] = DEFAULT_INCLUDE_MODALITIES,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Convert a Rules-Only capsule into per-rule Sun rule records.

    Returns ``(rule_records, summary)`` where ``rule_records`` maps each rule
    id in ``rule_ids`` to a rule-record dict whose ``actions``/``actors``/
    ``order_relations`` fields are consumed by the frozen Sun scorer.

    ``summary`` holds the envelope accounting: sentence/envelope failures,
    clause inclusion/exclusion counts, span validation, and the
    ``order_relations_absent`` diagnostic.
    """
    records: dict[str, dict[str, Any]] = {}
    schema_ok = capsule.get("schema_version") == CAPSULE_SCHEMA
    by_sample: dict[str, Mapping[str, Any]] = {}
    for rec in capsule.get("records", []):
        sid = rec.get("sample_id")
        if sid is not None:
            by_sample[sid] = rec

    summary: dict[str, Any] = {
        "converter": CONVERTER_NAME,
        "capsule_schema_ok": schema_ok,
        "capsule_records": len(capsule.get("records", [])),
        "sentence_texts_available": len(texts_by_sample),
        "include_modalities": list(include_modalities),
        "per_rule": {},
        "total_envelopes": 0,
        "total_envelopes_ok": 0,
        "total_envelopes_failed": 0,
        "failure_reasons": {},
        "order_relations_absent_rules": [],
        "total_invalid_spans": 0,
    }
    include = set(include_modalities)

    for rule_id in rule_ids:
        per_rule: dict[str, Any] = {
            "sentence_count": 0,
            "envelopes_ok": 0,
            "envelopes_failed": 0,
            "failure_reasons": {},
            "clause_count": 0,
            "included_clause_count": 0,
            "excluded_modality_counts": {},
            "actor_span_count": 0,
            "action_span_count": 0,
            "invalid_span_count": 0,
            "order_relations_count": 0,
        }
        actions: list[str] = []
        actors: list[str] = []
        order_relations: list[tuple[str, str]] = []
        failed_reasons: list[str] = []

        # iterate the rule's sentences in the input pack's own order
        samples = [sid for sid in texts_by_sample if _sample_rule_id(sid) == rule_id]
        samples.sort(key=lambda sid: int(sid.split("_s", 1)[1]))
        for sid in samples:
            text = texts_by_sample[sid]
            summary["total_envelopes"] += 1
            per_rule["sentence_count"] += 1
            env = by_sample.get(sid)
            if env is None:
                reason = f"stage2_prediction_missing:{sid}"
                summary["total_envelopes_failed"] += 1
                per_rule["envelopes_failed"] += 1
                per_rule["failure_reasons"][reason] = per_rule["failure_reasons"].get(reason, 0) + 1
                summary["failure_reasons"][reason] = summary["failure_reasons"].get(reason, 0) + 1
                failed_reasons.append(reason)
                continue
            status = env.get("request_status")
            if status != "ok":
                reason = f"stage2_prediction_failed:{status or 'unknown'}:{env.get('error_category') or 'no_error_category'}"
                summary["total_envelopes_failed"] += 1
                per_rule["envelopes_failed"] += 1
                per_rule["failure_reasons"][reason] = per_rule["failure_reasons"].get(reason, 0) + 1
                summary["failure_reasons"][reason] = summary["failure_reasons"].get(reason, 0) + 1
                failed_reasons.append(reason)
                continue
            record = env.get("record")
            clauses = (record or {}).get("clauses") or []
            if not clauses:
                reason = f"stage2_empty_envelope:{sid}"
                summary["total_envelopes_failed"] += 1
                per_rule["envelopes_failed"] += 1
                per_rule["failure_reasons"][reason] = per_rule["failure_reasons"].get(reason, 0) + 1
                summary["failure_reasons"][reason] = summary["failure_reasons"].get(reason, 0) + 1
                failed_reasons.append(reason)
                continue
            summary["total_envelopes_ok"] += 1
            per_rule["envelopes_ok"] += 1
            for clause in clauses:
                per_rule["clause_count"] += 1
                modality = (clause.get("modality") or {}).get("label")
                if modality not in include:
                    per_rule["excluded_modality_counts"][modality] = (
                        per_rule["excluded_modality_counts"].get(modality, 0) + 1
                    )
                    continue
                per_rule["included_clause_count"] += 1
                bad: list[str] = []
                for act_span in clause.get("actions") or []:
                    txt = _span_text(text, act_span, f"{sid}.actions", bad)
                    if txt is not None:
                        actions.append(txt)
                for actor_span in clause.get("actors") or []:
                    txt = _span_text(text, actor_span, f"{sid}.actors", bad)
                    if txt is not None:
                        actors.append(txt)
                # Definition-7 order constraints: the frozen capsule carries
                # none at clause level (and null at record level).  If a
                # clause ever carried order relations under the same
                # sentence-offset span contract, each relation's two
                # endpoints would be sliced here; because no rows exist the
                # field stays empty and the diagnostic is recorded.
                cl_or = clause.get("order_relations")
                if cl_or:
                    per_rule["order_relations_count"] += len(cl_or)
                per_rule["invalid_span_count"] += len(bad)
                summary["total_invalid_spans"] += len(bad)

        actions = _dedupe(actions)
        actors = _dedupe(actors)
        per_rule["action_count"] = len(actions)
        per_rule["actor_count"] = len(actors)
        per_rule["order_relations_absent"] = per_rule["order_relations_count"] == 0
        if per_rule["order_relations_absent"]:
            summary["order_relations_absent_rules"].append(rule_id)

        failed = bool(failed_reasons)
        rule_record: dict[str, Any] = {
            "rule_id": rule_id,
            "schema_version": RECORD_SCHEMA,
            "modality": "obligation",
            "actions": actions,
            "actors": actors,
            "order_relations": order_relations,
            "failed": failed,
            "failure_reasons": _dedupe(failed_reasons),
            "provenance": {
                "source": "EXTERNAL Rules-Only Stage-2 capsule "
                          "(data/predictions/gdpr7_sun_rule_only_v1)",
                "converter": CONVERTER_NAME,
                "mapping": (
                    "clause modality label == 'obligation' only; action/actor "
                    "texts reconstructed by slicing approved_text_en sentence "
                    "offsets (validated 0<=start<end<=len); conditions/"
                    "constraints/exceptions not consumed by the Sun scorer; "
                    "order_relations not present in the capsule (empty at every "
                    "clause, null at record level) so Definition-7 input is "
                    "absent by contract, never fabricated"
                ),
                "gold_fields_read": False,
            },
        }
        per_rule["rule_record_schema"] = RECORD_SCHEMA
        records[rule_id] = rule_record
        summary["per_rule"][rule_id] = per_rule

    return records, summary


def convert_rule_records_for_items(
    capsule: Mapping[str, Any],
    texts_by_sample: Mapping[str, str],
    item_rule_ids: Sequence[str],
    include_modalities: Sequence[str] = DEFAULT_INCLUDE_MODALITIES,
) -> dict[str, dict[str, Any]]:
    """Convenience wrapper returning only the rule-record map."""
    records, _ = build_rule_records(capsule, texts_by_sample, item_rule_ids,
                                    include_modalities)
    return records

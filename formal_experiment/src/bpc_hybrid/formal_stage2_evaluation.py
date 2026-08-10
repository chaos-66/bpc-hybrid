# -*- coding: utf-8 -*-
"""Shared formal Stage 2 evaluation over the PUBLISHED formal Gold
(zero-API, G0.4 evaluation-views contract).

The published Stage 2 Gold (data/gold/stage2/estg150_formal_gold_v1.json)
stores modality as a plain string: local modality evidence spans are NOT
carried by the decision-only Gold. Consequences (explicit, never silent):

- six-field span metrics: computed with the fixed Sun literal-overlap
  contract for the five span-bearing fields (actor/action/condition/
  constraint/exception); the modality field's span metrics are reported as
  unavailable with the reason
- modality-label metrics: four-class (obligation/permission/prohibition/
  definition) accuracy and macro-F1, reported separately
- fine (clause-level) and coarse (sentence-level) views share the same
  evaluator, schema and normalization; cross-view mixing is forbidden

The evaluation input for the evaluator is derived deterministically from
the published Gold records (modality string -> {"label": ..., "evidence": []}).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from bpc_hybrid.stage2_sun_literal_overlap import (
    evaluate_sun_literal_overlap,
)

MODALITY_CLASSES = ("obligation", "permission", "prohibition", "definition")
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")


def published_gold_to_evaluator(gold_doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert published Gold records to evaluator-compatible records.

    modality string -> {"label": str, "evidence": []} (evidence unavailable
    in the published decision-only Gold). All other clause fields pass
    through unchanged.
    """
    out = []
    for rec in sorted(gold_doc["records"], key=lambda r: r["sample_id"]):
        clauses = []
        for clause in rec.get("clauses") or []:
            c = dict(clause)
            modality = c.get("modality")
            c["modality"] = {
                "label": modality if isinstance(modality, str) else None,
                "evidence": [],
            }
            clauses.append(c)
        out.append({"sample_id": rec["sample_id"], "clauses": clauses})
    return out


def predictions_to_evaluator(attempts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """B0/D1/H1 attempts envelopes -> evaluator attempts (envelope shape kept:
    {sample_id, request_status, record, error_category, runtime})."""
    return list(attempts)


def evaluate_span_metrics(gold_eval_records: Sequence[Mapping[str, Any]],
                          attempts: Sequence[Mapping[str, Any]], *,
                          dataset_id: str, method_id: str,
                          view: str) -> dict[str, Any]:
    """Six-field Sun literal-overlap evaluation with explicit modality handling.

    Returns per-field metrics for the five span-bearing fields plus an
    explicit 'modality_span' availability declaration.
    """
    report = evaluate_sun_literal_overlap(
        gold_eval_records, list(attempts), dataset_id=dataset_id,
        method_id=method_id)
    per_field = report.get("per_field", {})
    span_fields = {}
    for field in SPAN_FIELDS:
        v = per_field.get(field, {})
        span_fields[field] = {
            "ground_truth": v.get("ground_truth"),
            "extracted": v.get("extracted"),
            "precision": v.get("precision"),
            "recall": v.get("recall"),
            "f1": v.get("f1"),
        }
    modality_field = per_field.get("modality", {})
    return {
        "schema_version": "formal_stage2_span_metrics@1.0.0",
        "view": view,
        "dataset_id": dataset_id,
        "method_id": method_id,
        "match_rule": "independent_same_field_any_nonempty_character_span_intersection",
        "overall": report.get("overall", {}),
        "span_fields": span_fields,
        "modality_span": {
            "available": False,
            "reason": ("published formal Gold stores modality as a plain "
                       "string; local modality evidence spans are not "
                       "carried by the decision-only Gold"),
            "ground_truth": modality_field.get("ground_truth", 0),
            "extracted": modality_field.get("extracted", 0),
        },
        "no_cross_view_mixing": True,
    }


def _gold_modality_label(gold_eval_records: Mapping[str, Mapping[str, Any]],
                         sample_id: str) -> str | None:
    rec = gold_eval_records.get(sample_id)
    for clause in (rec or {}).get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label:
            return label
    return None


def _pred_modality_label(attempt: Mapping[str, Any]) -> str | None:
    record = attempt.get("record") or {}
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label:
            return label
    return None


def evaluate_modality_labels(gold_eval_records: Sequence[Mapping[str, Any]],
                             attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Four-class modality label accuracy / macro-F1 (reported separately,
    never mixed into the six-field span table)."""
    gold_by_id = {r["sample_id"]: r for r in gold_eval_records}
    attempt_by_id = {a["sample_id"]: a for a in attempts}
    pairs = []
    for sid in sorted(gold_by_id):
        gold_label = _gold_modality_label(gold_by_id, sid)
        pred_label = _pred_modality_label(attempt_by_id.get(sid, {}))
        pairs.append({"sample_id": sid, "gold": gold_label, "predicted": pred_label})

    correct = sum(1 for p in pairs if p["gold"] == p["predicted"])
    n = len(pairs)
    accuracy = correct / n if n else None

    # macro-F1 over the four classes (gold class as reference)
    f1_scores = []
    for cls in MODALITY_CLASSES:
        tp = sum(1 for p in pairs if p["gold"] == cls and p["predicted"] == cls)
        fp = sum(1 for p in pairs if p["gold"] != cls and p["predicted"] == cls)
        fn = sum(1 for p in pairs if p["gold"] == cls and p["predicted"] != cls)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1_scores.append({"class": cls, "precision": prec, "recall": rec, "f1": f1})
    macro_f1 = sum(s["f1"] for s in f1_scores) / len(f1_scores) if f1_scores else None
    return {
        "schema_version": "formal_stage2_modality_labels@1.0.0",
        "classes": MODALITY_CLASSES,
        "records": n,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": f1_scores,
        "separate_from_span_metrics": True,
        "unlabeled_predictions": sum(1 for p in pairs if p["predicted"] is None),
    }


def strip_timing(attempts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Canonical prediction records WITHOUT unstable timing fields.

    Keeps {sample_id, request_status, record, error_category}; runtime timing
    (latency_ms etc.) is isolated into telemetry and never enters canonical
    artifacts.
    """
    out = []
    for a in attempts:
        out.append({
            "sample_id": a["sample_id"],
            "request_status": a.get("request_status"),
            "record": a.get("record"),
            "error_category": a.get("error_category"),
        })
    return out


def telemetry_only(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Isolated timing/cost telemetry (non-canonical)."""
    latencies = [a.get("runtime", {}).get("latency_ms") for a in attempts
                 if isinstance(a.get("runtime", {}).get("latency_ms"), (int, float))]
    total = sum(latencies)
    return {
        "schema_version": "formal_stage2_telemetry@1.0.0",
        "rows": len(attempts),
        "latency_ms_total": total,
        "latency_ms_mean": total / len(latencies) if latencies else None,
        "llm_call_performed_any": any(
            a.get("runtime", {}).get("llm_call_performed") for a in attempts),
        "note": "performance telemetry only; never part of canonical artifacts",
    }

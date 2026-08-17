# -*- coding: utf-8 -*-
"""S2.12 complexity-stratified evaluator v2 (Checkpoint E3).

Replaces the v1 whole-field string exact-equality evaluator. v2 reuses the
Stage 2 FORMAL evaluation contract exactly:

  * modality: clause-unit label accuracy, macro-F1 and per-class
    precision/recall/F1 (reported separately from span metrics, same
    missing-class policy as the formal evaluator: precision N/A, recall
    0.0, F1 0.0, included in macro)
  * actor/action/condition/constraint/exception: Sun literal-overlap span
    precision/recall/F1 (same fixed match rule, clause alignment by
    maximum total character-span IoU >= 0.5, global one-to-one
    assignment, safe-legal-v1 normalization) via the shared
    stage2_sun_literal_overlap module
  * multiple spans per sample and multiple clauses are supported by the
    underlying evaluator (never string-concatenated)
  * strata = frozen G0.5 levels L1/L2/L3 (caller supplies levels);
    a stratum with zero samples is reported with samples=0 and NO
    performance conclusion (no fabricated zeros)
  * overall (all samples) must equal the formal Stage 2 evaluator on the
    same fixture (parity anchor; verified by tests)

Gold shape: evaluator-compatible records
  {sample_id, clauses: [{clause_id, modality: {label, evidence[]},
   actors/actions/conditions/constraints/exceptions: [{id,text,start,end}]}]}
Attempts shape: canonical attempt envelopes
  {sample_id, request_status, record: {sample_id, clauses: [...]}}.

ZERO LLM/API; deterministic; fail-closed on sample-set mismatch.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from bpc_hybrid.stage2_sun_literal_overlap import (
    evaluate_sun_literal_overlap,
)

SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
MODALITY_CLASSES = ("obligation", "permission", "prohibition", "definition")
VALID_LEVELS = ("L1", "L2", "L3")


class EvaluatorFail(Exception):
    """Fail-closed evaluator abort."""


def _modality_label_from(record: Mapping[str, Any]) -> str | None:
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label:
            return label
    return None


def _attempt_modality_label(attempt: Mapping[str, Any]) -> str | None:
    record = attempt.get("record") or {}
    return _modality_label_from(record)


def modality_label_metrics(
        gold_by_id: Mapping[str, Mapping[str, Any]],
        attempts: Sequence[Mapping[str, Any]],
        sample_ids: Sequence[str]) -> dict[str, Any]:
    """Four-class modality label accuracy / macro-F1 / per-class (same
    computation as formal_stage2_evaluation.evaluate_modality_labels)."""
    attempt_by_id = {a.get("sample_id"): a for a in attempts}
    pairs = []
    for sid in sample_ids:
        gold = gold_by_id.get(sid) or {}
        pred = attempt_by_id.get(sid) or {}
        pairs.append({"sample_id": sid,
                      "gold": _modality_label_from(gold),
                      "predicted": _attempt_modality_label(pred)})
    correct = sum(1 for p in pairs if p["gold"] == p["predicted"])
    n = len(pairs)
    accuracy = correct / n if n else None
    f1_scores = []
    for cls in MODALITY_CLASSES:
        tp = sum(1 for p in pairs if p["gold"] == cls and
                 p["predicted"] == cls)
        fp = sum(1 for p in pairs if p["gold"] != cls and
                 p["predicted"] == cls)
        fn = sum(1 for p in pairs if p["gold"] == cls and
                 p["predicted"] != cls)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1_scores.append({"class": cls, "precision": prec, "recall": rec,
                          "f1": f1})
    macro_f1 = sum(s["f1"] for s in f1_scores) / len(f1_scores) \
        if f1_scores else None
    return {
        "classes": list(MODALITY_CLASSES),
        "records": n,
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "per_class": f1_scores,
        "separate_from_span_metrics": True,
    }


def _span_metrics(gold_records: Sequence[Mapping[str, Any]],
                  attempts: Sequence[Mapping[str, Any]], *,
                  dataset_id: str, method_id: str) -> dict[str, Any]:
    report = evaluate_sun_literal_overlap(
        gold_records, list(attempts), dataset_id=dataset_id,
        method_id=method_id)
    per_field = report.get("per_field", {})
    out = {}
    for field in SPAN_FIELDS:
        v = per_field.get(field, {})
        out[field] = {
            "ground_truth": v.get("ground_truth"),
            "extracted": v.get("extracted"),
            "precision": v.get("precision"),
            "recall": v.get("recall"),
            "f1": v.get("f1"),
        }
    return {
        "match_rule": ("independent_same_field_any_nonempty_character_"
                       "span_intersection"),
        "overall": report.get("overall", {}),
        "span_fields": out,
    }


def evaluate_stratified(gold_eval_records: Sequence[Mapping[str, Any]],
                        attempts: Sequence[Mapping[str, Any]], *,
                        levels: Mapping[str, str],
                        dataset_id: str, method_id: str) -> dict[str, Any]:
    """Per-stratum + overall evaluation aligned with the formal contract."""
    gold_by_id = {r["sample_id"]: r for r in gold_eval_records}
    attempt_by_id = {a["sample_id"]: a for a in attempts}
    sample_ids = sorted(gold_by_id)
    if set(attempt_by_id) != set(sample_ids):
        raise EvaluatorFail(
            "attempts/gold sample mismatch: missing=" +
            str(sorted(set(sample_ids) - set(attempt_by_id))) +
            " extra=" + str(sorted(set(attempt_by_id) - set(sample_ids))))
    if set(levels) != set(sample_ids):
        raise EvaluatorFail("levels sample mismatch")
    for sid in sample_ids:
        if levels[sid] not in VALID_LEVELS:
            raise EvaluatorFail(f"{sid}: bad level {levels[sid]!r}")

    strata: dict[str, Any] = {}
    for level in VALID_LEVELS:
        members = sorted(sid for sid in sample_ids if levels[sid] == level)
        if not members:
            strata[level] = {
                "samples": 0,
                "note": "no samples in this stratum; no performance "
                        "conclusion is reported",
                "span_fields": None,
                "modality_labels": None,
            }
            continue
        gold_sub = [gold_by_id[sid] for sid in members]
        attempts_sub = [attempt_by_id[sid] for sid in members]
        strata[level] = {
            "samples": len(members),
            "span_fields": _span_metrics(gold_sub, attempts_sub,
                                         dataset_id=dataset_id,
                                         method_id=method_id),
            "modality_labels": modality_label_metrics(
                gold_by_id, attempts_sub, members),
        }

    overall_span = _span_metrics(gold_eval_records, list(attempts),
                                 dataset_id=dataset_id,
                                 method_id=method_id)
    overall_mod = modality_label_metrics(gold_by_id, attempts, sample_ids)
    return {
        "schema_version": "s2_12_stratified_evaluator@2.0.0",
        "dataset_id": dataset_id,
        "method_id": method_id,
        "strata": strata,
        "overall": {
            "samples": len(sample_ids),
            "span_fields": overall_span,
            "modality_labels": overall_mod,
        },
        "parity_anchor": (
            "overall equals formal_stage2_evaluation on the same fixture "
            "(span metrics via evaluate_sun_literal_overlap; modality "
            "labels via the shared four-class computation)"),
        "zero_api": {"new_llm_api_calls": 0},
    }

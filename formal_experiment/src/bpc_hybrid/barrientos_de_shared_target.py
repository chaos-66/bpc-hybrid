# -*- coding: utf-8 -*-
"""Shared-target cross-method evaluation (Barrientos D/E, v1).

Why this module exists
----------------------
The Barrientos-native and Ours-native evaluators use DIFFERENT schemas, so
their F1 numbers MUST NOT be compared directly.  The only legitimate
cross-method surface is a pre-defined shared target that BOTH schemas can
express unambiguously, evaluated against the SAME gold with the SAME metric
function.  This module defines that surface.

Shared target v1
----------------
* Target A — sample-level 3-class modality
  (obligation / permission / prohibition):
  - Barrientos adapter: first ``norms[].modality`` (its schema enum is
    exactly the 3 classes).
  - Ours adapter: first ``clauses[].modality.label`` (4-class; a
    ``definition`` prediction is NOT expressible in the shared target and
    is projected to None).
  - Gold: first clause modality label of the frozen S2.11 gold (4-class);
    samples whose GOLD label is ``definition`` are excluded from the shared
    modality table and marked
    ``gold_label_not_expressible_in_barrientos_schema``.
  - Metric: pooled per-class P/R/F1 + macro-F1 across all expressible
    samples (same P/R/F1 definition as the artifact's analysis code:
    P = TP/(TP+FP), R = TP/(TP+FN), F1 = 2PR/(P+R)).
* Target B — adapter-defined norm count/type alignment (documented,
  secondary, NEVER merged into an overall F1):
  - Barrientos: len(norms); first norm.modality.
  - Ours: number of clauses whose modality label is in the 3 shared
    classes; first such label.
  - Gold: step_1_baseline.json per-version norm count/type.
  The clause<->norm mapping is an explicit adapter rule of this project and
  is disclosed as such.
* NOT strictly alignable (never hard-computed as 0):
  - precondition (Barrientos: AND/OR/NOT action lists; Ours: span-based
    condition fields — no equivalence).
  - actor / action / exception (not expressible in the Barrientos schema).
  - definition (not expressible in the Barrientos schema).

Nothing in this module synthesizes an overall F1 across schemas.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

SHARED_MODALITY_CLASSES = ("obligation", "permission", "prohibition")
GOLD_NOT_EXPRESSIBLE = "gold_label_not_expressible_in_barrientos_schema"
PRED_NOT_EXPRESSIBLE = "prediction_not_expressible_in_shared_target"
NOT_STRICTLY_ALIGNABLE = "not_strictly_alignable"


# ---------------------------------------------------------------------------
# Deterministic per-schema adapters
# ---------------------------------------------------------------------------


def barr_first_modality(tree: Any) -> str | None:
    """Barrientos tree -> first norm modality (schema enum is 3-class)."""
    if not isinstance(tree, Mapping):
        return None
    norms = tree.get("norms")
    if not isinstance(norms, list):
        return None
    for norm in norms:
        if not isinstance(norm, Mapping):
            continue
        m = norm.get("modality")
        if m in SHARED_MODALITY_CLASSES:
            return m
    return None


def barr_norm_count_and_type(tree: Any) -> tuple[int, str | None]:
    """Barrientos tree -> (number of norms, first norm modality)."""
    if not isinstance(tree, Mapping):
        return 0, None
    norms = tree.get("norms")
    if not isinstance(norms, list):
        return 0, None
    count = 0
    first = None
    for norm in norms:
        if not isinstance(norm, Mapping):
            continue
        m = norm.get("modality")
        if m in SHARED_MODALITY_CLASSES:
            count += 1
            if first is None:
                first = m
    return count, first


def ours_first_modality(record: Any) -> str | None:
    """Ours six-field canonical record -> first clause modality label
    (4-class).  ``definition`` is returned as-is; the shared-target layer
    projects it to None because the Barrientos schema cannot express it."""
    if not isinstance(record, Mapping):
        return None
    clauses = record.get("clauses")
    if not isinstance(clauses, list):
        return None
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        mod = clause.get("modality")
        label = mod.get("label") if isinstance(mod, Mapping) else None
        if isinstance(label, str) and label:
            return label
    return None


def ours_norm_count_and_type(record: Any) -> tuple[int, str | None]:
    """Ours record -> (number of 3-class-modal clauses, first such label).

    Adapter rule (disclosed): a clause whose modality label is one of the
    three shared classes is counted as one norm; the first such label is the
    norm type.  Definition clauses are NOT counted as norms here.
    """
    if not isinstance(record, Mapping):
        return 0, None
    clauses = record.get("clauses")
    if not isinstance(clauses, list):
        return 0, None
    count = 0
    first = None
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        mod = clause.get("modality")
        label = mod.get("label") if isinstance(mod, Mapping) else None
        if label in SHARED_MODALITY_CLASSES:
            count += 1
            if first is None:
                first = label
    return count, first


def gold_first_modality(gold_record: Any) -> str | None:
    """Frozen S2.11 gold record -> first clause modality label (4-class)."""
    return ours_first_modality(gold_record)


def shared_projection(label: str | None) -> str | None:
    """Project a 4-class Ours label onto the shared 3-class target.

    ``definition`` is not expressible in the Barrientos schema -> None
    (a miss for whatever class the gold has; never a hard zero)."""
    if label in SHARED_MODALITY_CLASSES:
        return label
    return None


# ---------------------------------------------------------------------------
# Same-gold, same-metric P/R/F1 for the shared target
# ---------------------------------------------------------------------------


def modality_prf(gold_labels: Sequence[str | None],
                 pred_labels: Sequence[str | None],
                 classes: Sequence[str] = SHARED_MODALITY_CLASSES,
                 ) -> dict[str, Any]:
    """Pooled per-class P/R/F1 over aligned gold/pred label sequences.

    Samples whose gold label is not in ``classes`` are excluded by the
    CALLER (see ``shared_modality_report``) so that inexpressible gold
    never pollutes the denominator.  A None prediction for an expressible
    gold sample counts as a miss (FN for the gold class, no FP)."""
    if len(gold_labels) != len(pred_labels):
        raise ValueError("gold/pred label sequences must be aligned")
    per_class: dict[str, dict[str, float | int]] = {}
    tp_total = fp_total = fn_total = 0
    for cls in classes:
        tp = sum(1 for g, p in zip(gold_labels, pred_labels)
                 if g == cls and p == cls)
        fp = sum(1 for g, p in zip(gold_labels, pred_labels)
                 if g != cls and p == cls)
        fn = sum(1 for g, p in zip(gold_labels, pred_labels)
                 if g == cls and p != cls)
        tp_total += tp
        fp_total += fp
        fn_total += fn
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        per_class[cls] = {"tp": tp, "fp": fp, "fn": fn,
                          "precision": round(precision, 6),
                          "recall": round(recall, 6), "f1": round(f1, 6)}
    macro_precision = (sum(v["precision"] for v in per_class.values())
                       / len(classes))
    macro_recall = (sum(v["recall"] for v in per_class.values())
                    / len(classes))
    macro_f1 = (2 * macro_precision * macro_recall
                / (macro_precision + macro_recall)
                if (macro_precision + macro_recall) else 0.0)
    return {
        "classes": list(classes),
        "samples_expressible": len(gold_labels),
        "per_class": per_class,
        "macro": {
            "precision": round(macro_precision, 6),
            "recall": round(macro_recall, 6),
            "f1": round(macro_f1, 6),
        },
        "pooled_tp": tp_total, "pooled_fp": fp_total, "pooled_fn": fn_total,
        "match_rule": "same_gold_same_metric_shared_3class_modality",
        "no_overall_f1_synthesized_across_schemas": True,
    }


def shared_modality_report(
    gold_records: Sequence[Mapping[str, Any]],
    arm_preds: Mapping[str, Sequence[str | None]],
) -> dict[str, Any]:
    """Per-arm shared 3-class modality P/R/F1 against the SAME gold.

    ``arm_preds[arm]`` must be aligned with ``gold_records`` (one projected
    prediction per gold record, in the same order).  Samples whose gold
    label is ``definition`` are excluded and reported per arm as
    ``excluded_gold_definition`` (never a hard zero)."""
    gold_labels = [gold_first_modality(g) for g in gold_records]
    expressible = [g in SHARED_MODALITY_CLASSES for g in gold_labels]
    gold_expr = [g for g, ok in zip(gold_labels, expressible) if ok]
    out: dict[str, Any] = {
        "target": "shared_3class_modality_v1",
        "gold_samples": len(gold_records),
        "gold_expressible_samples": len(gold_expr),
        "excluded_gold_definition_samples": (
            len(gold_records) - len(gold_expr)),
        "arms": {},
    }
    for arm, preds in arm_preds.items():
        if len(preds) != len(gold_records):
            raise ValueError(f"{arm}: preds not aligned with gold")
        pred_expr = [shared_projection(p) for p, ok
                     in zip(preds, expressible) if ok]
        out["arms"][arm] = modality_prf(gold_expr, pred_expr)
    return out


def norm_count_type_report(
    baseline_gold_by_sample: Mapping[str, Mapping[str, Any]],
    arm_trees: Mapping[str, Mapping[str, Any]],
    sample_ids: Sequence[str],
) -> dict[str, Any]:
    """Adapter-defined norm count/type alignment (secondary, documented).

    ``baseline_gold_by_sample[sample_id]`` is the per-sample gold node from
    step_1_baseline.json resolution (version-aware); ``arm_trees[arm]`` maps
    sample_id -> schema tree/record.  Reported per arm: pooled count
    TP/FP/FN (count), and first-type accuracy.  Never merged into an
    overall F1 across schemas."""
    out: dict[str, Any] = {
        "target": "adapter_defined_norm_count_type_v1",
        "adapter_rule": (
            "Barrientos: len(norms) and first norm.modality; Ours: count of "
            "clauses with 3-class modality label and first such label. "
            "Clause<->norm mapping is this project's explicit adapter rule, "
            "not a schema identity claim."),
        "precondition": {"status": NOT_STRICTLY_ALIGNABLE,
                         "reason": ("Barrientos precondition is an "
                                    "AND/OR/NOT action list; Ours condition "
                                    "is a span-based field; no equivalence")},
        "arms": {},
    }
    for arm, trees in arm_trees.items():
        tp = fp = fn = 0
        type_correct = 0
        type_total = 0
        for sid in sample_ids:
            gold = baseline_gold_by_sample.get(sid)
            if gold is None:
                continue
            g_count = int((gold.get("norm") or {}).get("count", 0) or 0)
            g_type = (gold.get("norm") or {}).get("type")
            tree = trees.get(sid)
            if tree is None:
                fn += g_count
                continue
            if arm.startswith("BARR-"):
                p_count, p_type = barr_norm_count_and_type(tree)
            else:
                p_count, p_type = ours_norm_count_and_type(tree)
            tp += min(p_count, g_count)
            fp += max(0, p_count - g_count)
            fn += max(0, g_count - p_count)
            if g_type is not None:
                type_total += 1
                type_correct += int(
                    p_type is not None and str(p_type).lower()
                    == str(g_type).lower())
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
        out["arms"][arm] = {
            "count_tp": tp, "count_fp": fp, "count_fn": fn,
            "count_precision": round(precision, 6),
            "count_recall": round(recall, 6),
            "count_f1": round(f1, 6),
            "first_type_accuracy": round(
                type_correct / type_total, 6) if type_total else None,
            "note": "adapter-defined; reported separately, never merged "
                    "with schema-native F1",
        }
    return out

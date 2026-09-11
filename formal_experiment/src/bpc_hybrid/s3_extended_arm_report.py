# -*- coding: utf-8 -*-
"""Shared A/B/C/D reporting for the S3 extended four-type panel arms.

Every arm of the four-type extension panel reports the SAME four metric views
and the SAME per-instance evidence, so two arms can be compared item by item
without re-deriving anything:

* **A** - the 40 mutated variants: per-type P/R/F1, four-type macro-F1, exact
  type hits, wrong types and abstentions;
* **B** - the 40 compliant controls: false positives, explicitly compliant
  answers, abstentions (a control abstention is NEVER a correct rejection);
* **C** - the 40 pairs: both sides correct;
* **D** - the merged 80 objects: five classes including ``none``, labelled as
  such and never presented as A.

Counts are always reported as a disjoint partition so the totals add up:

* variants (40) = correct + wrong_type + abstained + false_compliance
* controls (40) = explicitly_compliant + false_positive + abstained

``false_compliance`` is a variant whose process was reported explicitly
compliant (``none``) - a violated model that was cleared. It is NOT the same as
an abstention, and neither is the same as a wrong type.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from bpc_hybrid.stage3_extended_violations import (
    EXTENDED_TYPES,
    NONE_LABEL,
    evaluate_extended,
    evaluate_paired,
)

METRIC_SCHEMA = "s3_extended_arm_metrics@1.0.0"


def raw_label(row: Mapping[str, Any]) -> str | None:
    """The stored five-class decision of one variant row (None = abstention)."""
    raw = row.get("unified_predicted_raw")
    if raw is None:
        raw = row.get("predicted_violation_type")
    return raw


def variant_partition(rows: list[dict], gold: Mapping[str, Any],
                      expected_objects: int | None = None) -> dict[str, Any]:
    """Disjoint partition of the variants + the abstention reasons.

    Every row must carry a known gold entry; a row whose item is not in the gold
    mapping is a binding error and raises instead of being folded into a bucket.
    When ``expected_objects`` is given, a row set of the wrong size raises too,
    so a dropped sample can never look like a smaller clean denominator.
    """
    if expected_objects is not None and len(rows) != expected_objects:
        raise ValueError(f"expected {expected_objects} rows, got {len(rows)}")
    buckets: dict[str, list[str]] = {
        "correct": [], "wrong_type": [], "abstained": [], "false_compliance": [],
    }
    abstain_reasons = Counter()
    for row in rows:
        item = row["item_id"]
        if item not in gold:
            raise KeyError(f"row {item} has no gold entry")
        expected = gold[item]["expected_violation"]
        pred = raw_label(row)
        if pred == expected:
            buckets["correct"].append(item)
        elif pred is None:
            buckets["abstained"].append(item)
            abstain_reasons[row["observability"][expected].get("reason")
                            or "unspecified"] += 1
        elif pred == NONE_LABEL:
            buckets["false_compliance"].append(item)
        else:
            buckets["wrong_type"].append(item)
    total = sum(len(v) for v in buckets.values())
    if total != len(rows):
        raise RuntimeError(f"variant partition does not cover the rows: {total} != {len(rows)}")
    return {
        **{k: len(v) for k, v in buckets.items()},
        "objects": len(rows),
        "identity": "correct + wrong_type + abstained + false_compliance == objects",
        "items": buckets,
        "abstained_by_reason": dict(sorted(abstain_reasons.items())),
    }


def control_partition(paired: Mapping[str, Any]) -> dict[str, Any]:
    """Disjoint partition of the 40 controls from the paired evaluation."""
    total = paired["control_objects"]
    false_positives = len(paired["cases"]["control_false_positive"])
    abstained = paired["unobservable"]["control"]
    explicitly_compliant = total - false_positives - abstained
    if not (0 <= explicitly_compliant <= total):
        raise RuntimeError("control identities do not add up to the control objects")
    if round(false_positives / total, 4) != paired["control_false_positive_rate"]:
        raise RuntimeError("control false-positive count and rate disagree")
    by_reason = Counter()
    for case in paired["cases"]["control_unobservable"]:
        for reason in case["reasons"]:
            by_reason[reason] += 1
    return {
        "objects": total,
        "explicitly_compliant": explicitly_compliant,
        "false_positives": false_positives,
        "false_positive_rate": paired["control_false_positive_rate"],
        "abstained": abstained,
        "identity": "explicitly_compliant + false_positives + abstained == objects",
        "abstained_by_reason": dict(sorted(by_reason.items())),
        "false_positive_items": sorted(c["item_id"]
                                       for c in paired["cases"]["control_false_positive"]),
    }


def variant_type_detail(rows: list[dict], gold: Mapping[str, Any]) -> dict[str, Any]:
    """Per gold type: how many of its variants landed in each bucket."""
    out: dict[str, Any] = {}
    for t in EXTENDED_TYPES:
        subset = [r for r in rows if gold[r["item_id"]]["expected_violation"] == t]
        part = variant_partition(subset, gold)
        out[t] = {k: part[k] for k in
                  ("correct", "wrong_type", "abstained", "false_compliance", "objects")}
        out[t]["wrong_type_items"] = part["items"]["wrong_type"]
        out[t]["abstained_by_reason"] = part["abstained_by_reason"]
    return out


def arm_metrics(rows: list[dict], panel: Mapping[str, Any], gold: Mapping[str, Any],
                gamma_ext: float) -> dict[str, Any]:
    """All four metric views of one arm, from its stored rows only."""
    paired = evaluate_paired(rows, panel, gamma_ext)
    labels = [NONE_LABEL] + list(EXTENDED_TYPES)
    return {
        "schema_version": METRIC_SCHEMA,
        "A_variant_only_40": {
            "evaluation": evaluate_extended(rows, gold),
            "partition": variant_partition(rows, gold),
            "per_type_partition": variant_type_detail(rows, gold),
        },
        "B_control_40": control_partition(paired),
        "C_paired_40": {
            "pairs": paired["variant_objects"],
            "both_sides_correct": round(paired["paired_accuracy"] * paired["variant_objects"]),
            "paired_accuracy": paired["paired_accuracy"],
        },
        "D_merged_80": {
            "label": "merged_80_objects (40 variants + 40 controls)",
            "classes": labels,
            "denominator": paired["total_objects"],
            "five_class_accuracy": paired["five_class_accuracy"],
            "macro_f1_four_violation_types": paired["macro_f1_four_violation_types"],
            "macro_f1_five_classes": paired["macro_f1_five_classes"],
            "per_class": {label: paired["per_type"][label] for label in labels},
            "warning": ("the merged view is NOT the variant-only table A: it mixes 40 "
                        "violation objects with 40 compliant objects"),
        },
        "_paired_raw": paired,
    }


def per_item_evidence(row: Mapping[str, Any], gold: Mapping[str, Any],
                      rule_texts: Mapping[str, str]) -> dict[str, Any]:
    """Everything needed to audit one stored row without re-running the method."""
    item = row["item_id"]
    expected = gold[item]["expected_violation"]
    trace = row.get("action_localization") or {}
    variant_trace = trace.get("variant") if isinstance(trace, dict) else None
    return {
        "item_id": item,
        "process_id": row["process_id"],
        "rule_id": row["rule_id"],
        "rule_text": rule_texts.get(row["rule_id"]),
        "expected_violation": expected,
        "final_prediction": raw_label(row),
        "final_prediction_kind": (
            "abstention" if raw_label(row) is None else
            "explicitly_compliant" if raw_label(row) == NONE_LABEL else "violation_type"),
        "scores": row.get("scores"),
        "observability": row.get("observability"),
        "control_scores": row.get("control_scores"),
        "action_localization": variant_trace,
        "matched_activity_id": (row.get("matched_activity") or {}).get("variant")
        if isinstance(row.get("matched_activity"), dict) else None,
        "evidence_binding": (row.get("evidence_binding") or {}).get("variant")
        if isinstance(row.get("evidence_binding"), dict) else None,
        "thresholds": row.get("thresholds") or {"gamma_ext": row.get("gamma_ext"),
                                                "action_gamma": row.get("action_mapping_gamma")},
        "expected_type_observability": row["observability"][expected],
    }

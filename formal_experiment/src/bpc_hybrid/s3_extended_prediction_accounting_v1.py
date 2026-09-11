"""Offline accounting from one final decision per arm, item and side.

No BPMN parsing, matching, scoring or API calls. A/B retain their declared
frozen aggregation; C retains its declared comparison gate, on BOTH sides.
The policies themselves are not changed by this accounting repair.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite

from bpc_hybrid.stage3_extended_violations import (
    EXTENDED_TYPES, NONE_LABEL, control_prediction_from_scores,
)
from bpc_hybrid.s3_extended_v3_repair_v2 import aggregate_with_comparison_gate

POLICIES = {
    "A_v3_internal_0_4": "unified_five_class_decision_v1",
    "B_original_path_normalized": "unified_five_class_decision_v1",
    "C_v3_no_forced_resolution": "unified_five_class_decision_v1+comparison_gate",
}
LABELS = (NONE_LABEL,) + tuple(EXTENDED_TYPES)


def side_scores(row: dict, side: str) -> dict:
    if side == "control":
        scores = row["control_scores"]
    elif side == "variant":
        scores = {
            t: {
                **row["scores_detail"][t],
                "score": row["scores"][t],
                "observable": row["observability"][t]["observable"],
            }
            for t in EXTENDED_TYPES
        }
    else:
        raise ValueError(f"unknown side: {side}")
    if set(scores) != set(EXTENDED_TYPES):
        raise ValueError("all four check scores must be present")
    for entry in scores.values():
        if type(entry["observable"]) is not bool:
            raise ValueError("observable must be a boolean")
        value = entry["score"]
        if value is not None and (type(value) not in (int, float) or not isfinite(value)):
            raise ValueError("score must be finite or null")
        if entry["observable"] and value is None:
            raise ValueError("an observable check must have a stored score")
        if not entry["observable"] and value is not None:
            raise ValueError("an unobservable check cannot publish a score")
    return scores


def final_decision(scores: dict, policy: str, gamma_ext: float) -> dict:
    """Apply an already declared policy; this interface takes no labels/IDs."""
    if policy == "unified_five_class_decision_v1":
        return control_prediction_from_scores(scores, gamma_ext)
    if policy == "unified_five_class_decision_v1+comparison_gate":
        return aggregate_with_comparison_gate(scores, gamma_ext)
    raise ValueError(f"undeclared decision policy: {policy}")


def materialize_decisions(rows: list[dict]) -> list[dict]:
    """Reconstruct both sides without expected labels, preserving variant outputs."""
    result, seen = [], set()
    for source_row, row in enumerate(rows, 1):
        arm, item = row["arm"], row["item_id"]
        if arm not in POLICIES or row["prediction_rule"] != POLICIES[arm]:
            raise ValueError(f"undeclared arm/policy: {arm}")
        if (arm, item) in seen:
            raise ValueError(f"duplicate source row: {arm}/{item}")
        seen.add((arm, item))
        threshold = row["thresholds"]["gamma_ext"]
        if threshold != 0.5 or row["gamma_ext"] != threshold:
            raise ValueError("frozen extension threshold differs")
        for side in ("variant", "control"):
            decision = final_decision(side_scores(row, side), POLICIES[arm], threshold)
            predicted = decision["predicted"]
            if side == "variant" and predicted != row["unified_predicted_raw"]:
                raise ValueError(f"stored variant decision mismatch: {arm}/{item}")
            result.append({
                "arm": arm, "item_id": item, "side": side,
                "source_row": source_row, "decision_policy": POLICIES[arm],
                "gamma_ext": threshold, "predicted": predicted,
                "per_type_decisions": decision["per_type"],
                "final_unknown": predicted is None,
            })
    return result


def attach_expected(decisions: list[dict], rows: list[dict]) -> list[dict]:
    """Evaluation-only labels, read after every final decision is fixed."""
    expected = {(r["arm"], r["item_id"]): r["expected_violation"] for r in rows}
    if any(value not in EXTENDED_TYPES for value in expected.values()):
        raise ValueError("invalid expected violation type")
    return [dict(d, expected=(expected[d["arm"], d["item_id"]]
                             if d["side"] == "variant" else NONE_LABEL))
            for d in decisions]


def classification(records: list[dict], labels: tuple) -> dict:
    per_class = {}
    for label in labels:
        tp = sum(r["expected"] == label and r["predicted"] == label for r in records)
        fp = sum(r["expected"] != label and r["predicted"] == label for r in records)
        fn = sum(r["expected"] == label and r["predicted"] != label for r in records)
        per_class[label] = {
            "support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else 0.0,
            "recall": tp / (tp + fn) if tp + fn else 0.0,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        }
    tp, fp, fn = (sum(v[k] for v in per_class.values()) for k in ("tp", "fp", "fn"))
    return {
        "per_class": per_class,
        "macro_f1": sum(v["f1"] for v in per_class.values()) / len(labels),
        "micro_f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "accuracy": sum(r["predicted"] == r["expected"] for r in records) / len(records),
    }


def evaluate_instances(instances: list[dict], pairs_per_arm: int = 40) -> dict:
    """All metric views consume final labels ONLY, never re-decide from scores."""
    groups = defaultdict(dict)
    for r in instances:
        arm, item, side = r["arm"], r["item_id"], r["side"]
        if arm not in POLICIES or side not in ("variant", "control"):
            raise ValueError("invalid arm/side")
        if r["predicted"] not in (*LABELS, None) or r["expected"] not in LABELS:
            raise ValueError("invalid final label")
        if r["decision_policy"] != POLICIES[arm]:
            raise ValueError("policy mismatch")
        if (side == "control") != (r["expected"] == NONE_LABEL):
            raise ValueError("control/variant label mismatch")
        if (item, side) in groups[arm]:
            raise ValueError("duplicate final instance")
        groups[arm][item, side] = r
    if set(groups) != set(POLICIES):
        raise ValueError("missing arm")
    result, common_items, common_labels = {}, None, None
    for arm, group in sorted(groups.items()):
        variants = sorted((r for r in group.values() if r["side"] == "variant"),
                          key=lambda r: r["item_id"])
        controls = [r for r in group.values() if r["side"] == "control"]
        ids = {r["item_id"] for r in variants}
        labels = {r["item_id"]: r["expected"] for r in variants}
        if (len(variants) != pairs_per_arm or len(controls) != pairs_per_arm
                or ids != {r["item_id"] for r in controls}):
            raise ValueError("missing/unpaired instances")
        if common_items is not None and (ids != common_items or labels != common_labels):
            raise ValueError("arms do not share the same panel labels")
        common_items, common_labels = ids, labels
        vcounts = Counter()
        for r in variants:
            p = r["predicted"]
            vcounts["correct_type" if p == r["expected"] else
                    "final_unknown" if p is None else
                    "explicit_compliance" if p == NONE_LABEL else "wrong_type"] += 1
        ccounts = Counter("final_unknown" if r["predicted"] is None else
                          "explicit_compliance" if r["predicted"] == NONE_LABEL else
                          "false_positives" for r in controls)
        pairs = [{"item_id": r["item_id"],
                  "variant_correct": r["predicted"] == r["expected"],
                  "control_correct": group[r["item_id"], "control"]["predicted"] == NONE_LABEL}
                 for r in variants]
        paired = sum(p["variant_correct"] and p["control_correct"] for p in pairs)
        merged = classification(list(group.values()), LABELS)
        expected_correct = vcounts["correct_type"] + ccounts["explicit_compliance"]
        if paired > min(vcounts["correct_type"], ccounts["explicit_compliance"]):
            raise ValueError("paired accuracy exceeds a side's correct count")
        if abs(merged["accuracy"] - expected_correct / (2 * pairs_per_arm)) > 1e-12:
            raise ValueError("merged accuracy contradicts side counts")
        confusion = {label: {p: 0 for p in (*LABELS, "unknown")} for label in LABELS}
        for r in group.values():
            confusion[r["expected"]][r["predicted"] if r["predicted"] is not None else "unknown"] += 1
        result[arm] = {
            "decision_policy": POLICIES[arm],
            "A_variant_40": {
                "objects": pairs_per_arm,
                **{k: vcounts[k] for k in ("correct_type", "wrong_type", "explicit_compliance", "final_unknown")},
                "target_type_unobservable": sum(r["per_type_decisions"][r["expected"]] is None for r in variants),
                **classification(variants, tuple(EXTENDED_TYPES)),
            },
            "B_control_40": {"objects": pairs_per_arm,
                             **{k: ccounts[k] for k in ("false_positives", "explicit_compliance", "final_unknown")}},
            "C_paired_40": {"pairs": pairs_per_arm, "both_sides_correct": paired,
                            "paired_accuracy": paired / pairs_per_arm, "per_pair": pairs},
            "D_merged_80": {"objects": 2 * pairs_per_arm, "correct": expected_correct,
                            **merged, "confusion_matrix": confusion},
            "invariants": {"pair_bound": True, "accuracy_identity": True,
                           "all_instances_retained": True, "single_final_label_per_instance": True},
        }
    return result

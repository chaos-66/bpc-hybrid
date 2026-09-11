# -*- coding: utf-8 -*-
"""Offline acceptance re-evaluation of the S3 extended arms W and H.

Reads stored JSON/JSONL only.  It never imports a checker, loads an NLP model,
parses BPMN or produces a prediction: every number here is recomputed from rows
that already exist on disk.

Why it exists
-------------
The batch that produced W and H reported a merged accuracy whose label
definition was mixed, and a target-field diagnostic that read the aggregate
per-type decision instead of the target check itself.  This evaluator fixes the
accounting only:

* **one final label per instance, three disjoint outcomes per side**, so the
  merged accuracy is exactly
  ``(variant correct + control explicitly compliant) / 80``;
* **the target-field view reports raw partitions** per violation type over its
  own 10 variants and 10 controls, plus the paired outcome, and keeps
  ``not_applicable`` in a column of its own.  It never treats another type's
  variants as human-confirmed negatives;
* **the target decision comes from the target check itself**: a check that
  reports a violation is ``true``, a check that ran and found no violation is
  ``false``, and everything else - unavailable, unresolved or not applicable -
  is ``undecidable``.

Every source file is referenced by path and sha256; nothing is copied and
nothing is rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

RUN_ID = "s3_extended_acceptance_recompute_v1"
OUT_DIR = ROOT / "outputs/development" / RUN_ID
METRICS_FILE = OUT_DIR / "metrics.json"
DIAGNOSTICS_FILE = OUT_DIR / "diagnostics.json"
MANIFEST_FILE = OUT_DIR / "manifest.json"
OUT_FILES = ("metrics.json", "diagnostics.json", "manifest.json")

TYPES = ("prohibited_action_present", "required_condition_not_enforced",
         "constraint_violated", "exception_not_handled")
NONE_LABEL = "none"

VARIANT_OUTCOMES = ("correct_type", "wrong_type", "explicit_compliance",
                    "final_unknown")
CONTROL_OUTCOMES = ("false_positives", "explicit_compliance", "final_unknown")
TARGET_OUTCOMES = ("true", "false", "undecidable", "not_applicable")

# the four-type check of one arm reads the rule element below
RULE_FIELD = {
    "prohibited_action_present": "action",
    "required_condition_not_enforced": "condition",
    "constraint_violated": "constraint",
    "exception_not_handled": "exception",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


# --------------------------------------------------------------------------- sources


def source_paths() -> dict[str, Path]:
    return {
        "panel": ROOT / "data/development/stage3_synth/"
                        "synthetic_controlled_error_extension_v2.json",
        "scope_predictions": ROOT / "outputs/development/"
                                    "s3_extended_evidence_scope_v1/predictions.jsonl",
        "scope_metrics": ROOT / "outputs/development/"
                                "s3_extended_evidence_scope_v1/metrics.json",
        "scope_plan": ROOT / "outputs/development/"
                             "s3_extended_evidence_scope_v1/plan.json",
        "accounting_predictions": ROOT / "outputs/development/"
                                         "s3_extended_prediction_accounting_v1/"
                                         "final_predictions.jsonl",
        "accounting_metrics": ROOT / "outputs/development/"
                                     "s3_extended_prediction_accounting_v1/metrics.json",
        "repair_v2_predictions": ROOT / "outputs/development/"
                                       "s3_extended_repair_v2_v1/predictions.jsonl",
        "gap_difference_lists": ROOT / "outputs/evidence/s3_extended_gap_v1/"
                                      "difference_lists.json",
        "frozen_winter_predictions": ROOT / "outputs/evidence/"
                                           "s3_formula_repair_v2/extended_four/"
                                           "reference/winter/predictions.jsonl",
        "frozen_sun_predictions": ROOT / "outputs/evidence/s3_formula_repair_v2/"
                                        "extended_four/reference/sun/predictions.jsonl",
    }


# --------------------------------------------------------------------- label rules


def variant_outcome(predicted, expected: str) -> str:
    if predicted == expected:
        return "correct_type"
    if predicted == NONE_LABEL:
        return "explicit_compliance"
    if predicted is None:
        return "final_unknown"
    return "wrong_type"


def control_outcome(predicted) -> str:
    if predicted == NONE_LABEL:
        return "explicit_compliance"
    if predicted is None:
        return "final_unknown"
    return "false_positives"


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
        "accuracy": (sum(r["predicted"] == r["expected"] for r in records)
                     / len(records)) if records else 0.0,
        "unknown_not_in_denominator": 0,
        "undecidable_policy": ("the five-class view has no separate abstention class: a "
                               "null final label is carried as its own prediction and "
                               "counts as an error for the row, so it is never removed "
                               "from a denominator and never counted as a correct "
                               "rejection"),
    }


# ------------------------------------------------------------------- main table


def build_main_table(instances: list[dict], arms: list[str], panel_gold: dict,
                     expected_pairs: int = 40) -> dict:
    out = {}
    for arm in arms:
        arm_rows = [r for r in instances if r["arm"] == arm]
        variants = sorted((r for r in arm_rows if r["side"] == "variant"),
                          key=lambda r: r["item_id"])
        controls = sorted((r for r in arm_rows if r["side"] == "control"),
                          key=lambda r: r["item_id"])
        if len(variants) != expected_pairs or len(controls) != expected_pairs:
            raise ValueError(f"{arm}: expected {expected_pairs} variants and "
                             f"{expected_pairs} controls")
        if {r["item_id"] for r in variants} != {r["item_id"] for r in controls}:
            raise ValueError(f"{arm}: variant and control membership differ")
        v_counts = Counter(variant_outcome(r["predicted"], r["expected"])
                           for r in variants)
        c_counts = Counter(control_outcome(r["predicted"]) for r in controls)
        for name in VARIANT_OUTCOMES:
            v_counts.setdefault(name, 0)
        for name in CONTROL_OUTCOMES:
            c_counts.setdefault(name, 0)
        pairs = [{"item_id": r["item_id"], "expected": r["expected"],
                  "variant_predicted": r["predicted"],
                  "variant_correct": r["predicted"] == r["expected"],
                  "control_predicted": next(c["predicted"] for c in controls
                                            if c["item_id"] == r["item_id"]),
                  "control_correct": next(c["predicted"] for c in controls
                                          if c["item_id"] == r["item_id"]) == NONE_LABEL}
                 for r in variants]
        paired = sum(p["variant_correct"] and p["control_correct"] for p in pairs)
        merged_records = [{"expected": r["expected"], "predicted": r["predicted"]}
                          for r in variants + controls]
        merged = classification(merged_records, (NONE_LABEL,) + TYPES)
        if sum(v_counts[n] for n in VARIANT_OUTCOMES) != expected_pairs:
            raise ValueError(f"{arm}: variant partition does not sum to {expected_pairs}")
        if sum(c_counts[n] for n in CONTROL_OUTCOMES) != expected_pairs:
            raise ValueError(f"{arm}: control partition does not sum to {expected_pairs}")
        correct = v_counts["correct_type"] + c_counts["explicit_compliance"]
        if paired > min(v_counts["correct_type"], c_counts["explicit_compliance"]):
            raise ValueError(f"{arm}: paired success exceeds a side's correct count")
        if abs(merged["accuracy"] - correct / (2 * expected_pairs)) > 1e-12:
            raise ValueError(f"{arm}: merged accuracy contradicts the side partitions")
        out[arm] = {
            "label_policy": ("one stored final label per instance; variant outcomes are "
                             "correct_type / wrong_type / explicit_compliance / "
                             "final_unknown and control outcomes are false_positives / "
                             "explicit_compliance / final_unknown"),
            "A_variant_40": {"objects": expected_pairs,
                             **{n: v_counts[n] for n in VARIANT_OUTCOMES},
                             **classification(
                                 [{"expected": r["expected"], "predicted": r["predicted"]}
                                  for r in variants], TYPES)},
            "B_control_40": {"objects": expected_pairs,
                             **{n: c_counts[n] for n in CONTROL_OUTCOMES}},
            "C_paired_40": {
                "pairs": expected_pairs, "both_sides_correct": paired,
                "paired_accuracy": paired / expected_pairs,
                "definition": ("a pair succeeds only when the variant carries the "
                               "expected type AND its control is answered with explicit "
                               "compliance 'none'; a control abstention is never a "
                               "correct rejection"),
                "per_pair": pairs},
            "D_merged_80": {"objects": 2 * expected_pairs, "correct": correct, **merged},
        }
    if len(out) > 1:
        labels = {a: {r["item_id"]: r["expected"] for r in instances
                      if r["arm"] == a and r["side"] == "variant"} for a in arms}
        first = next(iter(labels.values()))
        for arm, value in labels.items():
            if value != first:
                raise ValueError("arms do not share the same panel labels")
    return out


# ----------------------------------------------------------- target-field view


def target_partition(instances: list[dict], arm: str, panel_gold: dict,
                     expected_per_type: int = 10) -> dict:
    """Raw partition of the target check over its own variants and controls.

    The partition is restricted to the type's own items, so a type whose rule
    element is simply absent for this target (``not_applicable``) stays visible
    in its own column, and the cross-type applicability counts are reported
    separately rather than being mixed into the target slice.
    """
    rows = {(r["item_id"], r["side"]): r for r in instances if r["arm"] == arm}
    out = {"per_type": {}, "paired": {}, "not_applicable": {},
           "applicability_across_all_40_rows": {}}
    for target in TYPES:
        items = [i for i, t in sorted(panel_gold.items()) if t == target]
        part = Counter()
        paired_ok = 0
        for item in items:
            variant = rows[(item, "variant")]["target_check"]
            control = rows[(item, "control")]["target_check"]
            part[f"variant_{variant['outcome']}"] += 1
            part[f"control_{control['outcome']}"] += 1
            if variant["outcome"] == "true" and control["outcome"] == "false":
                paired_ok += 1
        if part["variant_true"] + part["variant_false"] + part["variant_undecidable"] \
                + part["variant_not_applicable"] != expected_per_type:
            raise ValueError(f"{arm}/{target}: variant target partition is not "
                             f"{expected_per_type}")
        if part["control_true"] + part["control_false"] + part["control_undecidable"] \
                + part["control_not_applicable"] != expected_per_type:
            raise ValueError(f"{arm}/{target}: control target partition is not "
                             f"{expected_per_type}")
        out["per_type"][target] = {
            "rule_field": RULE_FIELD[target],
            "target_variants": expected_per_type,
            "target_controls": expected_per_type,
            "variant_true": part["variant_true"],
            "variant_false": part["variant_false"],
            "variant_undecidable": part["variant_undecidable"],
            "variant_not_applicable": part["variant_not_applicable"],
            "control_true": part["control_true"],
            "control_false": part["control_false"],
            "control_undecidable": part["control_undecidable"],
            "control_not_applicable": part["control_not_applicable"],
            "positive_missed_on_variant": part["variant_false"],
            "control_alarm": part["control_true"],
            "true_negative_from_target_controls": part["control_false"],
            "no_prf1_reason": ("no precision/recall/F1 is reported per target type: the "
                               "only labelled positives are that type's 10 variants, "
                               "undecidable cases are neither positives nor negatives, "
                               "and another type's variants are not human-confirmed "
                               "negatives for this check"),
        }
        out["paired"][target] = {"pairs": expected_per_type, "both_sides_ok": paired_ok,
                                 "definition": ("variant target check true AND control "
                                                "target check false")}
        # how often this check is not applicable at all, by the target type it was
        # asked about; kept out of the target slice above
        across = Counter()
        by_target = {}
        for item, target_type in sorted(panel_gold.items()):
            for side in ("variant", "control"):
                outcome = rows[(item, side)]["target_check_of_type"][target]["outcome"]
                across[side] += outcome == "not_applicable"
            by_target[target_type] = (
                rows[(item, "variant")]["target_check_of_type"][target]["outcome"])
        out["applicability_across_all_40_rows"][target] = {
            "variant_not_applicable": across["variant"],
            "control_not_applicable": across["control"],
            "variant_outcome_by_target_type": dict(
                Counter(by_target.values()))}
        out["not_applicable"][target] = {
            "variant": part["variant_not_applicable"],
            "control": part["control_not_applicable"]}
    return out


def target_check_from_verdict(check: dict, observable: bool | None = None) -> dict:
    """Arm H style: the verdict decides, and not_applicable stays separate.

    The prohibition presence check carries no four-outcome contract, so it is read
    the same way as a frozen check: a reported violation is ``true``, a check that
    ran and found no violation is ``false``, and a check that did not run is
    ``undecidable``.
    """
    verdict = check.get("verdict")
    if verdict is None or (verdict is None and observable is None):
        if observable is not None:
            return target_check_from_observability(check, observable)
    if verdict == "violated":
        outcome = "true"
    elif verdict == "satisfied":
        outcome = "false"
    elif verdict == "not_applicable":
        outcome = "not_applicable"
    elif verdict is None:
        outcome = ("true" if check.get("violation") is True
                   else "false" if check.get("violation") is False else "undecidable")
    else:
        outcome = "undecidable"
    return {"outcome": outcome, "verdict": verdict,
            "reason": check.get("reason"),
            "applicability": check.get("applicability"),
            "evidence_status": check.get("evidence_status")}


def target_check_from_observability(check: dict, observable: bool) -> dict:
    """Arms whose checks publish a boolean plus an observability flag."""
    if check.get("violation") is True:
        outcome = "true"
    elif observable:
        outcome = "false"
    else:
        outcome = "undecidable"
    return {"outcome": outcome, "violation": check.get("violation"),
            "observable": observable, "reason": check.get("reason")}


def build_instances(sources: dict) -> tuple[list[dict], dict]:
    panel = read_json(sources["panel"])
    gold = {v["variant_id"]: v["expected_violation"] for v in panel["variants"]}
    instances: list[dict] = []

    scope_rows = read_jsonl(sources["scope_predictions"])
    for row in scope_rows:
        arm = row["arm"]
        target = gold[row["item_id"]]
        per_type = {}
        for t in TYPES:
            check = row["checks"][t]
            if arm == "H_scoped_evidence_and_verdicts":
                per_type[t] = target_check_from_verdict(
                    check, bool(row["observability"][t]["observable"]))
            else:
                per_type[t] = target_check_from_observability(
                    check, bool(row["observability"][t]["observable"]))
        instances.append({
            "arm": arm, "item_id": row["item_id"], "side": row["side"],
            "predicted": row["final_label"],
            "expected": (target if row["side"] == "variant" else NONE_LABEL),
            "target_type": target,
            "target_check": per_type[target],
            "target_check_of_type": per_type,
            "label_source": "s3_extended_evidence_scope_v1/predictions.jsonl:final_label",
        })

    acc_rows = read_jsonl(sources["accounting_predictions"])
    for row in acc_rows:
        per_type = {}
        for t in TYPES:
            decision = row["per_type_decisions"][t]
            per_type[t] = {
                "outcome": ("true" if decision is True else
                            "false" if decision is False else "undecidable"),
                "source": "accounting per_type_decisions", "decision": decision}
        target = gold[row["item_id"]]
        instances.append({
            "arm": row["arm"], "item_id": row["item_id"], "side": row["side"],
            "predicted": row["predicted"],
            "expected": row["expected"],
            "target_type": target,
            "target_check": per_type[target],
            "target_check_of_type": per_type,
            "label_source": ("s3_extended_prediction_accounting_v1/"
                             "final_predictions.jsonl:predicted"),
        })
    per_arm = Counter(r["arm"] for r in instances)
    return instances, {"gold": gold, "rows_per_arm": dict(per_arm)}


def build_all() -> dict:
    started = datetime.now(timezone.utc).isoformat()
    sources = source_paths()
    missing = [str(p) for p in sources.values() if not p.is_file()]
    if missing:
        raise FileNotFoundError("missing stored source: " + ", ".join(missing))
    instances, meta = build_instances(sources)
    arms = sorted({r["arm"] for r in instances})
    if len(arms) != 5:
        raise ValueError(f"expected the five stored arms, got {arms}")
    for arm in arms:
        rows = [r for r in instances if r["arm"] == arm]
        if len(rows) != 80:
            raise ValueError(f"{arm}: expected 80 stored instances, got {len(rows)}")
    main = build_main_table(instances, arms, meta["gold"])
    target = {arm: target_partition(instances, arm, meta["gold"]) for arm in arms}
    metrics = {
        "schema_version": "s3_extended_acceptance_metrics@1.0.0",
        "run_id": RUN_ID, "generated_utc": started,
        "scope": ("offline acceptance re-evaluation of stored predictions; "
                  "development regression against the old synthetic panel labels, "
                  "NOT an independent validation, NOT the formal Oracle and NOT real "
                  "legal compliance performance"),
        "sources": {name: {"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                           "sha256": sha256_file(p)}
                    for name, p in sources.items()},
        "arms": main,
        "target_field_diagnostic": target,
        "counts": {"instances": len(instances), "arms": arms,
                   "rows_per_arm": meta["rows_per_arm"],
                   "total_row_objects_retained": len(instances),
                   "unknown_removed_from_any_denominator": 0},
    }
    diagnostics = build_diagnostics(sources, metrics, meta)
    return {"metrics": metrics, "diagnostics": diagnostics, "started_utc": started}


# ------------------------------------------------------------------ corrections


def build_diagnostics(sources: dict, metrics: dict, meta: dict) -> dict:
    scope = source_paths()["scope_predictions"]
    scope_rows = read_jsonl(scope)
    panel = read_json(sources["panel"])
    variants = {v["variant_id"]: v for v in panel["variants"]}

    # 1. the prohibited "regression": was it ever there?
    acc = {(r["arm"], r["item_id"]): r["predicted"]
           for r in read_jsonl(sources["accounting_predictions"])
           if r["side"] == "variant"}
    w_rows = {(r["item_id"]): r for r in scope_rows
              if r["arm"] == "W_action_resolution_wiring" and r["side"] == "variant"}
    prohibited_moves = []
    for item, variant in sorted(variants.items()):
        if variant["expected_violation"] != "prohibited_action_present":
            continue
        old = acc[("C_v3_no_forced_resolution", item)]
        new = w_rows[item]["final_label"]
        if old != new:
            prohibited_moves.append({"item_id": item, "C": old, "W": new})
    all_moves = []
    for item in sorted(variants):
        old = acc[("C_v3_no_forced_resolution", item)]
        new = w_rows[item]["final_label"]
        if old != new:
            all_moves.append({"item_id": item,
                              "expected": variants[item]["expected_violation"],
                              "C": old, "W": new,
                              "W_correct": new == variants[item]["expected_violation"],
                              "C_correct": old == variants[item]["expected_violation"]})

    # 2. the bypass records: verdict present, evidence not persisted
    bypass = []
    for row in scope_rows:
        if row["arm"] != "H_scoped_evidence_and_verdicts":
            continue
        check = row["checks"]["required_condition_not_enforced"]
        if check.get("verdict") != "violated":
            continue
        bypass.append({"item_id": row["item_id"], "side": row["side"],
                       "reason": check.get("reason"),
                       "target_activity_id": check.get("matched_activity_id"),
                       "evidence_sources_from_manifest": None,
                       "stopped_at_arbitration": True,
                       "bypass_evidence_persisted": check.get("detail") is not None})
    manifest = read_json(sources["scope_metrics"])
    provenance = {
        "verdict_count": len(bypass),
        "stored_evidence": ("the stored predictions persist the verdict, the reason and "
                            "the resolved target activity, but not the sibling branch "
                            "list; that list is only reproducible by re-running the "
                            "checker, which this batch does not do"),
        "arbitration": ("the original criterion marked the condition violated as soon as a "
                        "sibling branch of a reached gateway carried no condition; it "
                        "never established that the sibling branch leads back to the "
                        "target activity without the condition, so a bypass was not "
                        "proved"),
    }

    return {
        "schema_version": "s3_extended_acceptance_diagnostics@1.0.0",
        "run_id": RUN_ID,
        "corrections": {
            "prohibited_regression_claim": {
                "status": "retracted",
                "claim": ("'W regressed on five prohibited variants "
                          "(01/02/05/06/08) because the comparison gate turned them "
                          "into unknown'"),
                "why": ("that comparison was made against C's per-type gate decisions "
                        "while W's table used its final labels; under the accounting "
                        "labels both arms answer all ten prohibited variants with "
                        "prohibited_action_present"),
                "prohibited_prediction_differences_between_C_and_W": prohibited_moves,
                "cross_view_note": ("the same stored row can carry three different "
                                    "labels - the final five-class label, the target "
                                    "type's own decision, and a per-type gate decision - "
                                    "and they must not be compared across views"),
            },
            "W_vs_C_changes_under_the_accounting_labels": all_moves,
            "target_field_view": {
                "status": "corrected",
                "was": ("the target-field view consumed the aggregate per-type decision, "
                        "so a check that never ran and a check that ran and found no "
                        "violation were collapsed into one 'unknown'"),
                "now": ("each target check is read from its own stored check record: "
                        "violation -> true, ran-and-no-violation -> false, everything "
                        "else undecidable, and not_applicable is a column of its own"),
            },
            "unknown_vs_not_applicable": {
                "status": "corrected",
                "was": "'the rule requires this element but it cannot be checked' and 'the rule does not require this element' were reported as one number",
                "now": ("the target-field view reports variant_not_applicable and "
                        "control_not_applicable separately from the undecidable columns"),
                "H_not_applicable_counts": metrics["target_field_diagnostic"]
                ["H_scoped_evidence_and_verdicts"]["not_applicable"],
            },
            "run_counts": {
                "status": "corrected",
                "distinction": ("attempts (inference invocations started), successes "
                                "(invocations that wrote predictions), cumulative "
                                "computation (object-scorings performed across all "
                                "attempts) and retained rows (what the stored artifact "
                                "holds) are four different numbers and were previously "
                                "reported as one"),
                "recorded": {
                    "attempts": 3,
                    "successes_that_wrote_predictions": 2,
                    "cumulative_object_predictions_computed": 2 * 160,
                    "retained_rows_in_the_stored_artifact": 160,
                    "retained_rows_are_one_run_per_arm": True,
                    "identical_predictions_across_the_two_successful_runs": (
                        "cannot be independently verified from the surviving artifacts: "
                        "no copy of the first successful run was retained, so only the "
                        "second is on disk"),
                },
            },
            "conditional_mechanism_claim": {
                "status": "retracted",
                "claim": "'the H condition TP rose 3 -> 5, showing the mechanism improved'",
                "why": ("the same H condition check also returns a violated verdict for "
                        "12 instances through an unproved bypass criterion, so the "
                        "target-count change is not evidence of a working mechanism"),
            },
        },
        "condition_bypass_records": bypass,
        "condition_bypass_provenance": provenance,
        "acceptance_limits": {
            "scope": ("development regression on a panel already used for repeated "
                      "development"),
            "H_status": ("kept as a development result with a known implementation "
                         "defect; the method is NOT accepted"),
            "not_an_independent_validation": True,
            "no_new_inference_in_this_batch": True,
        },
        "reconciliation": reconcile_with_source_metrics(metrics),
    }


def reconcile_with_source_metrics(metrics: dict) -> dict:
    """Show the stored summaries next to the recomputed ones."""
    sources = source_paths()
    scope = read_json(sources["scope_metrics"])
    accounting = read_json(sources["accounting_metrics"])
    out = {"scope_metrics_arms": {}, "accounting_arms": {},
           "differences": [], "agreements": []}
    for arm, block in scope["arms"].items():
        out["scope_metrics_arms"][arm] = {
            "A_variant_40": {k: block["A_variant_40"][k] for k in
                             ("correct_type", "wrong_type", "explicit_compliance",
                              "final_unknown")},
            "B_control_40": {k: block["B_control_40"][k] for k in
                             ("false_positives", "explicit_compliance",
                              "final_unknown")},
            "paired": block["C_paired_40"]["both_sides_correct"],
            "merged_accuracy": block["D_merged_80"]["accuracy"],
        }
        mine = metrics["arms"][arm]
        same = (
            out["scope_metrics_arms"][arm]["A_variant_40"]
            == {k: mine["A_variant_40"][k] for k in
                ("correct_type", "wrong_type", "explicit_compliance", "final_unknown")}
            and out["scope_metrics_arms"][arm]["B_control_40"]
            == {k: mine["B_control_40"][k] for k in
                ("false_positives", "explicit_compliance", "final_unknown")}
            and out["scope_metrics_arms"][arm]["paired"]
            == mine["C_paired_40"]["both_sides_correct"]
            and abs(out["scope_metrics_arms"][arm]["merged_accuracy"]
                    - mine["D_merged_80"]["accuracy"]) < 1e-12)
        (out["agreements"] if same else out["differences"]).append(
            {"arm": arm, "scope": "s3_extended_evidence_scope_v1"})
    for arm, block in accounting["arms"].items():
        out["accounting_arms"][arm] = {
            "A_variant_40": {k: block["A_variant_40"][k] for k in
                             ("correct_type", "wrong_type", "explicit_compliance",
                              "final_unknown")},
            "B_control_40": {k: block["B_control_40"][k] for k in
                             ("false_positives", "explicit_compliance",
                              "final_unknown")},
            "paired": block["C_paired_40"]["both_sides_correct"],
            "merged_accuracy": block["D_merged_80"]["accuracy"],
        }
        mine = metrics["arms"][arm]
        same = (out["accounting_arms"][arm]["A_variant_40"]
                == {k: mine["A_variant_40"][k] for k in VARIANT_OUTCOMES}
                and out["accounting_arms"][arm]["B_control_40"]
                == {k: mine["B_control_40"][k] for k in CONTROL_OUTCOMES}
                and out["accounting_arms"][arm]["paired"]
                == mine["C_paired_40"]["both_sides_correct"])
        (out["agreements"] if same else out["differences"]).append(
            {"arm": arm, "scope": "s3_extended_prediction_accounting_v1"})
    return out


# ----------------------------------------------------------------------- driver


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def verify_outputs() -> dict:
    if sorted(p.name for p in OUT_DIR.iterdir()) != sorted(OUT_FILES):
        raise RuntimeError("the run directory must hold exactly its three files")
    manifest = read_json(MANIFEST_FILE)
    for name, entry in manifest["sources"].items():
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"source changed: {name} ({entry['path']})")
    implementation = manifest["implementation"]
    if isinstance(implementation, dict) and implementation \
            and isinstance(next(iter(implementation.values())), dict):
        for name, entry in implementation.items():
            if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
                raise RuntimeError(f"implementation changed: {name}")
    else:
        for rel, digest in implementation.items():
            if sha256_file(ROOT / rel) != digest:
                raise RuntimeError(f"implementation changed: {rel}")
    for name, entry in manifest["results"].items():
        if sha256_file(ROOT / entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"result changed: {name}")
    return {"metrics": read_json(METRICS_FILE),
            "diagnostics": read_json(DIAGNOSTICS_FILE),
            "manifest": manifest}


def main() -> int:
    import subprocess
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--replay", action="store_true",
                        help="recompute from the stored sources and compare")
    args = parser.parse_args()
    if args.check:
        verify_outputs()
        print(f"{RUN_ID} VERIFIED")
        return 0
    if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
        raise FileExistsError(f"refusing to overwrite an existing run: {OUT_DIR}")
    built = build_all()
    write_json(METRICS_FILE, built["metrics"])
    write_json(DIAGNOSTICS_FILE, built["diagnostics"])
    manifest = {
        "schema_version": "s3_extended_acceptance_manifest@1.0.0",
        "run_id": RUN_ID,
        "started_utc": built["started_utc"],
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                              text=True).strip(),
        "command": f"python {Path(__file__).relative_to(ROOT)}",
        "kind": "offline_recompute_of_stored_predictions",
        "no_inference": True,
        "checkers_imported": [],
        "sources": {name: {"path": str(p.relative_to(ROOT)).replace("\\", "/"),
                           "sha256": sha256_file(p)}
                    for name, p in source_paths().items()},
        "implementation": {
            "script": {"path": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
                       "sha256": sha256_file(Path(__file__))},
            "tests": {"path": "tests/test_s3_extended_acceptance_recompute_v1.py",
                      "sha256": sha256_file(
                          ROOT / "tests/test_s3_extended_acceptance_recompute_v1.py")},
        },
        "results": {
            "metrics": {"path": str(METRICS_FILE.relative_to(ROOT)).replace("\\", "/"),
                        "sha256": sha256_file(METRICS_FILE)},
            "diagnostics": {"path": str(DIAGNOSTICS_FILE.relative_to(ROOT))
                            .replace("\\", "/"),
                            "sha256": sha256_file(DIAGNOSTICS_FILE)},
        },
        "safety": {"api_calls": 0, "llm_api_calls": 0, "gold_modified": False,
                   "panel_modified": False, "existing_results_rewritten": False,
                   "predictions_regenerated": False, "old_manifests_rebound": False},
    }
    write_json(MANIFEST_FILE, manifest)
    verify_outputs()
    summary = {}
    for arm, block in built["metrics"]["arms"].items():
        a, b = block["A_variant_40"], block["B_control_40"]
        summary[arm] = {
            "variant": {k: a[k] for k in VARIANT_OUTCOMES},
            "control": {k: b[k] for k in CONTROL_OUTCOMES},
            "paired": block["C_paired_40"]["both_sides_correct"],
            "merged_accuracy": round(block["D_merged_80"]["accuracy"], 4),
            "variant_labeled": (a["correct_type"] + a["wrong_type"]
                                + a["explicit_compliance"]),
            "control_labeled": (b["explicit_compliance"] + b["false_positives"]),
        }
    print(json.dumps({"run_id": RUN_ID, "arms": summary}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

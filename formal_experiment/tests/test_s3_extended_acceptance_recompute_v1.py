# -*- coding: utf-8 -*-
"""Focused checks for the offline S3 extended acceptance re-evaluation.

Two halves, both offline and fast:

* **hand-computable tables** - tiny in-memory instances exercise the four
  outcomes, the target-field partition and the count identities, so every rule
  can be checked by hand without any panel data.
* **stored artifacts** - the recomputed numbers are compared with the previously
  stored summaries, and the corrected figures are asserted.

No checker is imported, no model is loaded and no prediction is regenerated.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

SCRIPT = ROOT / "scripts/recompute_s3_extended_acceptance_v1.py"
OUT = ROOT / "outputs/development/s3_extended_acceptance_recompute_v1"
TYPES = ("prohibited_action_present", "required_condition_not_enforced",
         "constraint_violated", "exception_not_handled")
NONE_LABEL = "none"


def _load():
    spec = importlib.util.spec_from_file_location("s3_extended_acceptance_recompute",
                                                  SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s3_extended_acceptance_recompute"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load()


# ------------------------------------------------------------------ hand tables


def test_variant_and_control_outcomes_are_disjoint_and_exhaustive(module):
    assert module.variant_outcome("constraint_violated", "constraint_violated") == "correct_type"
    assert module.variant_outcome("exception_not_handled", "constraint_violated") == "wrong_type"
    assert module.variant_outcome(NONE_LABEL, "constraint_violated") == "explicit_compliance"
    assert module.variant_outcome(None, "constraint_violated") == "final_unknown"
    assert module.control_outcome("constraint_violated") == "false_positives"
    assert module.control_outcome(NONE_LABEL) == "explicit_compliance"
    assert module.control_outcome(None) == "final_unknown"


def _instance(arm, item, side, predicted, expected, target, outcome,
              reason="r"):
    """One in-memory instance; the other three checks are undecidable here."""
    other = {"outcome": "undecidable", "reason": "not_exercised"}
    return {"arm": arm, "item_id": item, "side": side, "predicted": predicted,
            "expected": expected, "target_type": target,
            "target_check": {"outcome": outcome, "reason": reason},
            "target_check_of_type": {t: ({"outcome": outcome, "reason": reason}
                                         if t == target else dict(other))
                                     for t in TYPES}}


def test_merged_accuracy_is_the_sum_of_the_two_side_counts(module):
    """A four-item hand table: variant 1/2 correct, control 1/2 compliant."""
    rows = [
        _instance("X", "a", "variant", "constraint_violated", "constraint_violated",
                  "constraint_violated", "true"),
        _instance("X", "b", "variant", None, "constraint_violated",
                  "constraint_violated", "undecidable"),
        _instance("X", "a", "control", NONE_LABEL, NONE_LABEL, "constraint_violated",
                  "false"),
        _instance("X", "b", "control", "constraint_violated", NONE_LABEL,
                  "constraint_violated", "true"),
    ]
    gold = {"a": "constraint_violated", "b": "constraint_violated"}
    table = module.build_main_table(rows, ["X"], gold, expected_pairs=2)["X"]
    assert table["A_variant_40"]["objects"] == 2
    assert table["A_variant_40"]["correct_type"] == 1
    assert table["A_variant_40"]["final_unknown"] == 1
    assert table["B_control_40"]["explicit_compliance"] == 1
    assert table["B_control_40"]["false_positives"] == 1
    assert table["C_paired_40"]["both_sides_correct"] == 1
    assert table["D_merged_80"]["correct"] == 2
    assert table["D_merged_80"]["accuracy"] == pytest.approx(2 / 4)


def test_paired_never_exceeds_either_side(module):
    rows = []
    for i in range(3):
        rows.append(_instance("X", f"i{i}", "variant", "constraint_violated",
                              "constraint_violated", "constraint_violated", "true"))
        rows.append(_instance("X", f"i{i}", "control", None, NONE_LABEL,
                              "constraint_violated", "undecidable"))
    gold = {f"i{i}": "constraint_violated" for i in range(3)}
    table = module.build_main_table(rows, ["X"], gold, expected_pairs=3)["X"]
    assert table["A_variant_40"]["correct_type"] == 3
    assert table["B_control_40"]["final_unknown"] == 3
    assert table["B_control_40"]["explicit_compliance"] == 0
    assert table["C_paired_40"]["both_sides_correct"] == 0


def test_target_partition_counts_hand_checkable_table(module):
    """Every type gets two items; outcomes are set by a readable rule per type."""
    gold = {}
    rows = []
    # per type: first item true/false, second item false/undecidable, control varies
    variant_rule = {
        "prohibited_action_present": ("true", "false"),
        "required_condition_not_enforced": ("false", "undecidable"),
        "constraint_violated": ("true", "true"),
        "exception_not_handled": ("undecidable", "false"),
    }
    control_rule = {
        "prohibited_action_present": ("false", "false"),
        "required_condition_not_enforced": ("true", "undecidable"),
        "constraint_violated": ("undecidable", "false"),
        "exception_not_handled": ("false", "true"),
    }
    for target in TYPES:
        for index in (1, 2):
            item = f"{target}_{index}"
            gold[item] = target
            rows.append(_instance("X", item, "variant", "constraint_violated", target,
                                  target, variant_rule[target][index - 1]))
            rows.append(_instance("X", item, "control", NONE_LABEL, NONE_LABEL, target,
                                  control_rule[target][index - 1]))
    view = module.target_partition(rows, "X", gold, expected_per_type=2)

    cv = view["per_type"]["constraint_violated"]
    assert cv["variant_true"] == 2 and cv["control_false"] == 1
    assert cv["control_undecidable"] == 1
    assert view["paired"]["constraint_violated"]["both_sides_ok"] == 1

    pp = view["per_type"]["prohibited_action_present"]
    assert pp["variant_true"] == 1 and pp["variant_false"] == 1
    assert pp["control_true"] == 0 and pp["control_false"] == 2
    assert pp["control_alarm"] == 0
    assert view["paired"]["prohibited_action_present"]["both_sides_ok"] == 1

    ev = view["per_type"]["exception_not_handled"]
    assert ev["variant_undecidable"] == 1 and ev["variant_false"] == 1
    assert ev["control_true"] == 1 and ev["control_undecidable"] == 0
    assert view["paired"]["exception_not_handled"]["both_sides_ok"] == 0

    rc = view["per_type"]["required_condition_not_enforced"]
    assert rc["variant_false"] == 1 and rc["variant_undecidable"] == 1
    assert rc["control_true"] == 1 and rc["control_undecidable"] == 1
    assert view["paired"]["required_condition_not_enforced"]["both_sides_ok"] == 0
    for target in TYPES:
        block = view["per_type"][target]
        assert block["positive_missed_on_variant"] == block["variant_false"]
        assert block["control_alarm"] == block["control_true"]
        assert block["true_negative_from_target_controls"] == block["control_false"]


def test_target_partition_rejects_a_broken_table(module):
    gold = {"v1": "constraint_violated", "v2": "constraint_violated"}
    rows = [_instance("X", "v1", "variant", "constraint_violated",
                      "constraint_violated", "constraint_violated", "true"),
            _instance("X", "v2", "variant", "constraint_violated",
                      "constraint_violated", "constraint_violated", "true")]
    with pytest.raises(ValueError):
        module.target_partition(rows, "X", gold, expected_per_type=2)


def test_target_check_reads_the_check_not_the_aggregate(module):
    """not_applicable must not be folded into undecidable."""
    assert module.target_check_from_verdict(
        {"verdict": "violated", "reason": "x"})["outcome"] == "true"
    assert module.target_check_from_verdict(
        {"verdict": "satisfied", "reason": "x"})["outcome"] == "false"
    assert module.target_check_from_verdict(
        {"verdict": "unknown", "reason": "x"})["outcome"] == "undecidable"
    assert module.target_check_from_verdict(
        {"verdict": "not_applicable", "applicability": "not_required",
         "reason": "rule_has_no_condition"})["outcome"] == "not_applicable"
    # the prohibition presence check carries no verdict: the reported boolean decides
    assert module.target_check_from_verdict(
        {"violation": True}, True)["outcome"] == "true"
    assert module.target_check_from_verdict(
        {"violation": False}, True)["outcome"] == "false"
    assert module.target_check_from_verdict(
        {"violation": None}, False)["outcome"] == "undecidable"
    # the frozen-style helper behaves the same way
    assert module.target_check_from_observability(
        {"violation": True}, True)["outcome"] == "true"
    assert module.target_check_from_observability(
        {"violation": False}, True)["outcome"] == "false"
    assert module.target_check_from_observability(
        {"violation": None}, False)["outcome"] == "undecidable"


def test_classification_declares_the_undecidable_policy(module):
    records = [{"expected": "constraint_violated", "predicted": "constraint_violated"},
               {"expected": "constraint_violated", "predicted": None},
               {"expected": "exception_not_handled", "predicted": "exception_not_handled"},
               {"expected": "exception_not_handled", "predicted": "constraint_violated"}]
    result = module.classification(records, TYPES)
    assert result["unknown_not_in_denominator"] == 0
    assert "undecidable_policy" in result
    assert result["per_class"]["constraint_violated"]["tp"] == 1
    assert result["per_class"]["constraint_violated"]["fn"] == 1
    assert result["per_class"]["constraint_violated"]["fp"] == 1
    assert result["per_class"]["exception_not_handled"]["tp"] == 1
    assert result["per_class"]["exception_not_handled"]["fn"] == 1
    assert sum(v["support"] for v in result["per_class"].values()) == 4


# -------------------------------------------------------------- stored artifacts


@pytest.fixture(scope="module")
def stored(module):
    return module.verify_outputs()


def test_the_batch_is_read_only(stored):
    manifest = stored["manifest"]
    assert manifest["no_inference"] is True
    assert manifest["checkers_imported"] == []
    safety = manifest["safety"]
    assert safety["predictions_regenerated"] is False
    assert safety["existing_results_rewritten"] is False
    assert safety["old_manifests_rebound"] is False
    assert sorted(p.name for p in OUT.iterdir()) == \
        ["diagnostics.json", "manifest.json", "metrics.json"]


def test_every_stored_row_is_retained_twice_over(stored):
    counts = stored["metrics"]["counts"]
    assert counts["instances"] == 400          # five arms x 80 instances
    assert counts["total_row_objects_retained"] == 400
    assert counts["unknown_removed_from_any_denominator"] == 0
    assert set(counts["rows_per_arm"].values()) == {80}
    assert len(counts["arms"]) == 5


def test_w_and_h_reproduce_the_expected_counts(stored):
    arms = stored["metrics"]["arms"]
    w = arms["W_action_resolution_wiring"]
    h = arms["H_scoped_evidence_and_verdicts"]
    assert (w["A_variant_40"]["correct_type"], w["A_variant_40"]["wrong_type"],
            w["A_variant_40"]["explicit_compliance"],
            w["A_variant_40"]["final_unknown"]) == (19, 9, 0, 12)
    assert (w["B_control_40"]["false_positives"],
            w["B_control_40"]["explicit_compliance"],
            w["B_control_40"]["final_unknown"]) == (20, 7, 13)
    assert w["D_merged_80"]["correct"] == 26
    assert w["D_merged_80"]["accuracy"] == pytest.approx(26 / 80)
    assert (h["A_variant_40"]["correct_type"], h["A_variant_40"]["wrong_type"],
            h["A_variant_40"]["explicit_compliance"],
            h["A_variant_40"]["final_unknown"]) == (15, 8, 0, 17)
    assert (h["B_control_40"]["false_positives"],
            h["B_control_40"]["explicit_compliance"],
            h["B_control_40"]["final_unknown"]) == (19, 5, 16)
    assert h["D_merged_80"]["correct"] == 20
    assert h["D_merged_80"]["accuracy"] == pytest.approx(20 / 80)


def test_count_identities_hold_for_every_arm(stored):
    for arm, block in stored["metrics"]["arms"].items():
        a, b = block["A_variant_40"], block["B_control_40"]
        assert (a["correct_type"] + a["wrong_type"] + a["explicit_compliance"]
                + a["final_unknown"]) == 40, arm
        assert (b["false_positives"] + b["explicit_compliance"]
                + b["final_unknown"]) == 40, arm
        paired = block["C_paired_40"]["both_sides_correct"]
        assert paired <= min(a["correct_type"], b["explicit_compliance"]), arm
        assert abs(block["D_merged_80"]["accuracy"]
                   - (a["correct_type"] + b["explicit_compliance"]) / 80) < 1e-12, arm
        # the paired count is rebuilt from the same labels the table uses
        rebuilt = sum(p["variant_correct"] and p["control_correct"]
                      for p in block["C_paired_40"]["per_pair"])
        assert rebuilt == paired, arm


def test_one_final_label_per_instance_is_used_everywhere(stored):
    block = stored["metrics"]["arms"]["W_action_resolution_wiring"]
    labels = {p["item_id"]: (p["variant_predicted"], p["control_predicted"])
              for p in block["C_paired_40"]["per_pair"]}
    for pair in block["C_paired_40"]["per_pair"]:
        assert pair["variant_correct"] == (pair["variant_predicted"] == pair["expected"])
        assert pair["control_correct"] == (pair["control_predicted"] == NONE_LABEL)
    assert len(labels) == 40


def test_target_view_keeps_not_applicable_separate(stored):
    view = stored["metrics"]["target_field_diagnostic"]
    for arm in ("W_action_resolution_wiring", "H_scoped_evidence_and_verdicts"):
        for target, block in view[arm]["per_type"].items():
            assert block["variant_true"] + block["variant_false"] \
                + block["variant_undecidable"] + block["variant_not_applicable"] == 10
            assert block["control_true"] + block["control_false"] \
                + block["control_undecidable"] + block["control_not_applicable"] == 10
            assert "no_prf1_reason" in block
    h = view["H_scoped_evidence_and_verdicts"]["per_type"]
    # the target slice for a type holds only that type's own 20 objects, so a type
    # whose rule element is absent for those targets has no not_applicable here
    assert h["constraint_violated"]["variant_not_applicable"] == 0
    assert h["exception_not_handled"]["variant_not_applicable"] == 0
    # the cross-type applicability is reported separately
    across = view["H_scoped_evidence_and_verdicts"]["applicability_across_all_40_rows"]
    assert across["constraint_violated"]["variant_not_applicable"] == 20
    assert across["exception_not_handled"]["variant_not_applicable"] == 24
    assert across["required_condition_not_enforced"]["variant_not_applicable"] == 7
    assert across["prohibited_action_present"]["variant_not_applicable"] == 0
    # H's per-target conditions: 5 hit, 5 undecidable; the two typed checks never decide
    assert h["required_condition_not_enforced"]["variant_true"] == 5
    assert h["required_condition_not_enforced"]["variant_undecidable"] == 5
    assert h["constraint_violated"]["variant_true"] == 0
    assert h["constraint_violated"]["variant_false"] == 0
    assert h["constraint_violated"]["variant_undecidable"] == 10
    assert h["exception_not_handled"]["variant_true"] == 0
    assert h["exception_not_handled"]["variant_false"] == 0
    assert h["exception_not_handled"]["variant_undecidable"] == 10
    assert h["prohibited_action_present"]["variant_true"] == 10
    # H's condition control side fires on the same five items, so no pair succeeds
    assert h["required_condition_not_enforced"]["control_true"] == 5
    assert view["H_scoped_evidence_and_verdicts"]["paired"][
        "required_condition_not_enforced"]["both_sides_ok"] == 0


def test_c_target_decision_comes_from_accounting_not_the_final_class(stored):
    """The stored C cell is read through its per-type decisions."""
    view = stored["metrics"]["target_field_diagnostic"]["C_v3_no_forced_resolution"]
    assert view["per_type"]["prohibited_action_present"]["variant_true"] == 10
    assert view["per_type"]["required_condition_not_enforced"]["variant_true"] == 1
    assert view["per_type"]["constraint_violated"]["variant_true"] == 7
    assert view["per_type"]["exception_not_handled"]["variant_true"] == 3
    # C and W answer the two typed checks identically; the condition check differs
    w = stored["metrics"]["target_field_diagnostic"]["W_action_resolution_wiring"]
    for target in ("prohibited_action_present", "constraint_violated",
                   "exception_not_handled"):
        assert w["per_type"][target]["variant_true"] == \
            view["per_type"][target]["variant_true"], target
    assert w["per_type"]["required_condition_not_enforced"]["variant_true"] == 3 > \
        view["per_type"]["required_condition_not_enforced"]["variant_true"]


def test_corrections_are_recorded(stored):
    corrections = stored["diagnostics"]["corrections"]
    assert corrections["prohibited_regression_claim"]["status"] == "retracted"
    assert corrections["prohibited_regression_claim"][
        "prohibited_prediction_differences_between_C_and_W"] == []
    moves = corrections["W_vs_C_changes_under_the_accounting_labels"]
    assert len(moves) == 4
    assert all(m["expected"] != "prohibited_action_present" for m in moves)
    assert corrections["conditional_mechanism_claim"]["status"] == "retracted"
    assert corrections["target_field_view"]["status"] == "corrected"
    assert corrections["unknown_vs_not_applicable"]["status"] == "corrected"
    runs = corrections["run_counts"]["recorded"]
    assert runs["attempts"] == 3
    assert runs["successes_that_wrote_predictions"] == 2
    assert runs["cumulative_object_predictions_computed"] == 320
    assert runs["retained_rows_in_the_stored_artifact"] == 160
    assert "cannot be independently verified" in \
        runs["identical_predictions_across_the_two_successful_runs"]


def test_bypass_records_are_arbitrated_not_proved(stored):
    payload = stored["diagnostics"]["condition_bypass_records"]
    assert len(payload) == 27
    assert sum(1 for e in payload if e["side"] == "variant") == 12
    assert sum(1 for e in payload if e["side"] == "control") == 15
    for entry in payload:
        assert entry["reason"] == "unconditional_bypass_branch"
        assert entry["stopped_at_arbitration"] is True
        assert entry["bypass_evidence_persisted"] is False
        assert entry["target_activity_id"]
    provenance = stored["diagnostics"]["condition_bypass_provenance"]
    assert provenance["verdict_count"] == 27
    assert "was not" in provenance["arbitration"] or "not proved" in \
        provenance["arbitration"]


def test_reconciliation_agrees_with_both_stored_summaries(stored):
    recon = stored["diagnostics"]["reconciliation"]
    assert recon["differences"] == []
    assert {entry["arm"] for entry in recon["agreements"]} == {
        "A_v3_internal_0_4", "B_original_path_normalized",
        "C_v3_no_forced_resolution", "W_action_resolution_wiring",
        "H_scoped_evidence_and_verdicts"}
    # the previously stored W/H summaries already matched this recompute
    assert recon["scope_metrics_arms"]["W_action_resolution_wiring"]["paired"] == 6
    assert recon["scope_metrics_arms"]["H_scoped_evidence_and_verdicts"]["paired"] == 5
    assert recon["accounting_arms"]["C_v3_no_forced_resolution"]["paired"] == 7


def test_acceptance_limits_are_declared(stored):
    limits = stored["diagnostics"]["acceptance_limits"]
    assert limits["not_an_independent_validation"] is True
    assert "NOT accepted" in limits["H_status"]
    assert limits["no_new_inference_in_this_batch"] is True

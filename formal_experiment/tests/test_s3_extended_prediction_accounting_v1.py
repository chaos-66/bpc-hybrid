"""Accounting tests use stored scores only: no NLP/model/panel inference."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from bpc_hybrid.s3_extended_prediction_accounting_v1 import (
    EXTENDED_TYPES, POLICIES, attach_expected, classification, evaluate_instances,
    final_decision, materialize_decisions,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/development/s3_extended_repair_v2_v1"


@pytest.fixture(scope="module")
def rows():
    return [json.loads(s) for s in (SOURCE / "predictions.jsonl").read_text(
        encoding="utf-8").splitlines() if s.strip()]


def test_one_per_instance_and_no_source_mutation(rows):
    before = deepcopy(rows)
    objects = attach_expected(materialize_decisions(rows), rows)
    assert len(objects) == 240
    assert len({(r["arm"], r["item_id"], r["side"]) for r in objects}) == 240
    assert rows == before


def test_labels_and_mutation_metadata_cannot_change_decisions(rows):
    poisoned = deepcopy(rows)
    for r in poisoned:
        r["expected_violation"] = "poisoned"
        r["mutation_target"] = "pick_another_node"
    assert materialize_decisions(poisoned) == materialize_decisions(rows)


def test_native_policy_is_not_replaced_by_C_gate():
    scores = {t: {"score": None, "observable": False, "comparison_performed": False}
              for t in EXTENDED_TYPES}
    scores[EXTENDED_TYPES[0]] = {"score": .1, "observable": True, "comparison_performed": True}
    assert final_decision(scores, POLICIES["A_v3_internal_0_4"], .5)["predicted"] == "none"
    assert final_decision(scores, POLICIES["C_v3_no_forced_resolution"], .5)["predicted"] is None


def test_unknown_wrong_type_and_false_compliance_are_distinct():
    t, other = EXTENDED_TYPES[:2]
    objects = [{"expected": t, "predicted": p} for p in (t, other, None, "none")]
    scored = classification(objects, tuple(EXTENDED_TYPES))
    assert scored["per_class"][t]["tp"] == 1
    assert scored["per_class"][t]["fn"] == 3
    assert scored["per_class"][other]["fp"] == 1
    assert scored["per_class"][t]["f1"] == .4
    merged = classification(objects, ("none", *EXTENDED_TYPES))
    assert merged["per_class"]["none"]["fp"] == 1


def test_all_views_use_same_final_labels(rows):
    objects = attach_expected(materialize_decisions(rows), rows)
    metrics = evaluate_instances(objects)
    for arm, m in metrics.items():
        group = [r for r in objects if r["arm"] == arm]
        v, c = m["A_variant_40"], m["B_control_40"]
        p, d = m["C_paired_40"], m["D_merged_80"]
        assert sum(v[k] for k in ("correct_type", "wrong_type", "explicit_compliance", "final_unknown")) == 40
        assert sum(c[k] for k in ("false_positives", "explicit_compliance", "final_unknown")) == 40
        assert p["both_sides_correct"] <= min(v["correct_type"], c["explicit_compliance"])
        assert d["accuracy"] == (v["correct_type"] + c["explicit_compliance"]) / 80
        assert sum(sum(x.values()) for x in d["confusion_matrix"].values()) == 80
        correct_ids = [{r["item_id"] for r in group if r["side"] == side
                        and r["predicted"] == r["expected"]} for side in ("variant", "control")]
        assert p["both_sides_correct"] == len(correct_ids[0] & correct_ids[1])
    # Regression for the actual mixed-policy bug: B controls obey native policy.
    assert metrics["B_original_path_normalized"]["B_control_40"]["explicit_compliance"] == 14
    assert metrics["B_original_path_normalized"]["C_paired_40"]["both_sides_correct"] == 11


@pytest.mark.parametrize("damage", ["duplicate", "missing_side", "invalid_label", "policy", "different_gold"])
def test_bad_instance_binding_fails_closed(rows, damage):
    objects = attach_expected(materialize_decisions(rows), rows)
    if damage == "duplicate":
        objects.append(deepcopy(objects[0]))
    elif damage == "missing_side":
        objects.pop()
    elif damage == "invalid_label":
        objects[0]["predicted"] = "invalid"
    elif damage == "policy":
        objects[0]["decision_policy"] = "invented"
    else:
        objects[0]["expected"] = EXTENDED_TYPES[1]
    with pytest.raises(ValueError):
        evaluate_instances(objects)


def test_stored_variant_change_is_rejected(rows):
    broken = deepcopy(rows)
    broken[0]["unified_predicted_raw"] = "none"
    with pytest.raises(ValueError, match="stored variant decision mismatch"):
        materialize_decisions(broken)


def test_report_and_binding_replay_without_inference(monkeypatch):
    import spacy
    monkeypatch.setattr(spacy, "load", lambda *a, **k: pytest.fail("NLP must not run"))
    spec = importlib.util.spec_from_file_location("accounting_runner", ROOT / "scripts/reconcile_s3_extended_results_v1.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.verify_output()


def test_metrics_cannot_reenter_decision_logic(rows, monkeypatch):
    import bpc_hybrid.s3_extended_prediction_accounting_v1 as accounting
    objects = attach_expected(materialize_decisions(rows), rows)
    monkeypatch.setattr(accounting, "final_decision", lambda *a, **k: pytest.fail("must score final labels only"))
    evaluate_instances(objects)

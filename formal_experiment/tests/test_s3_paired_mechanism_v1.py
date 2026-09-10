# -*- coding: utf-8 -*-
"""Substantive checks for the S3 paired controlled mechanism experiment.

Covered requirements:

* the frozen panel membership and the original/variant byte bindings;
* the derived contract coverage (30 fixed / valid / unresolved, retained not dropped);
* expected labels and mutation prose never influence a prediction;
* both checkers receive identical inputs, models and configuration;
* unknown is never treated as a correct satisfaction (adapter and evaluator);
* the paired statistics are reconstructible from the stored per-item rows;
* the inputs and the previous round's artifacts are unchanged;
* the deterministic replay reproduces contracts and predictions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_s3_paired_mechanism_v1.py"
OUT = ROOT / "outputs/development/s3_paired_mechanism_v1"
PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v1.json"
PREVIOUS_ROUND_DIR = ROOT / "outputs/reports"


def _load_runner():
    spec = importlib.util.spec_from_file_location("paired_mechanism_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["paired_mechanism_runner"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


@pytest.fixture(scope="module")
def stored(runner):
    return runner.verify_manifest()


@pytest.fixture(scope="module")
def panel():
    return json.loads(PANEL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rebuilt(runner, stored):
    """One full deterministic rebuild, shared by the replay assertions."""
    return runner.replay_payload(stored["contracts"])


# --- fixed panel membership and bindings -----------------------------------


def test_fixed_panel_is_the_frozen_thirty_variants(panel, stored):
    assert len(panel["variants"]) == 30
    counts = {}
    for variant in panel["variants"]:
        counts[variant["mutation_type"]] = counts.get(variant["mutation_type"], 0) + 1
    assert counts == {"missing_action": 10, "incorrect_actor": 10, "out_of_order": 10}
    assert stored["contracts"]["counts"]["fixed_variants"] == 30
    assert len(stored["contracts"]["contracts"]) == 30


def test_every_variant_binds_to_the_frozen_source_and_variant_bytes(panel):
    for variant in panel["variants"]:
        source = (ROOT / variant["source_bpmn"]).read_bytes()
        mutated = (ROOT / variant["variant_bpmn"]).read_bytes()
        assert hashlib.sha256(source).hexdigest() == variant["source_bpmn_sha256"]
        assert hashlib.sha256(mutated).hexdigest() == variant["variant_bpmn_sha256"]
        assert source != mutated
    assert len({v["source_bpmn"] for v in panel["variants"]}) == 6


def test_no_fixed_variant_is_dropped_and_unresolved_ones_are_retained(stored):
    contracts = stored["contracts"]["contracts"]
    ids = [c["contract_id"] for c in contracts]
    assert len(ids) == len(set(ids)) == 30
    unresolved = [c for c in contracts if c["status"] != "valid"]
    assert len(unresolved) == stored["contracts"]["counts"]["unresolved"]
    for contract in unresolved:
        assert contract["reason"], contract["contract_id"]
        assert contract["validation"], "unresolved contracts keep their evidence"
        assert all(item["ok"] is False for item in contract["validation"]
                   if item["check"] == "ownership_changed_by_variant"
                   or item["check"] == "relation_broken_in_variant"
                   or item["check"] == "target_activity_absent_in_variant"
                   or item["check"] == "no_same_name_activity_left_in_variant")
    per_type = stored["contracts"]["per_type"]
    assert sum(v["fixed_variants"] for v in per_type.values()) == 30
    assert sum(v["valid_contracts"] for v in per_type.values()) == stored["contracts"]["counts"]["valid_contracts"]


def test_contracts_were_locked_before_inference_and_carry_only_requirements(stored):
    doc = stored["contracts"]
    assert doc["locked_before_inference"] is True
    for contract in doc["contracts"]:
        requirement = contract["requirement"]
        assert set(requirement) == {"actions", "actors", "actor_action_pairs", "order_relations"}
        assert "expected_violation" not in requirement
        assert "mutation_type" not in requirement
        assert "target_activity_id" not in requirement


# --- labels and prose never reach prediction -------------------------------


def test_expected_labels_and_mutation_prose_do_not_change_predictions(runner, stored, rebuilt):
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    for variant in panel["variants"]:
        variant["expected_violation"] = "out_of_order"
        variant["mutation_config"]["spec"] = ["POISONED", "POISONED", "POISONED"]
        variant["mutation_config"]["diff"] = {
            k: ("POISONED" if isinstance(v, str) else v)
            for k, v in variant["mutation_config"]["diff"].items()}
    records, reachability, models, scorers = runner.prepare(panel)
    poisoned_contracts = runner.build_contracts(panel, records, reachability)
    # neither the expected labels nor the mutation prose reach contract construction
    assert poisoned_contracts == stored["contracts"]
    poisoned_rows = runner.build_predictions(poisoned_contracts, models, scorers)
    assert len(poisoned_rows) == len(rebuilt["predictions"])
    for rebuilt_row, poisoned_row in zip(rebuilt["predictions"], poisoned_rows):
        assert rebuilt_row["pair_id"] == poisoned_row["pair_id"]
        assert rebuilt_row["signals"] == poisoned_row["signals"]
        # JSON round-trip: in-memory endpoint tuples are lists once serialised
        assert json.loads(json.dumps(rebuilt_row["raw"], sort_keys=True)) == \
            json.loads(json.dumps(poisoned_row["raw"], sort_keys=True))


def test_prediction_rows_carry_no_expected_answer_field(stored):
    for row in stored["predictions"]:
        assert "expected_violation" not in row
        assert "mutation_type" not in row
        assert row["target_check"] in {"missing_action", "incorrect_actor", "out_of_order"}


# --- identical inputs for both checkers ------------------------------------


def test_both_checkers_share_requirement_model_and_configuration(stored):
    rows = {(r["pair_id"], r["side"], r["checker"]): r for r in stored["predictions"]}
    pairs = {(r["pair_id"], r["side"]) for r in stored["predictions"]}
    assert len(rows) == 2 * len(pairs)
    for pair_id, side in pairs:
        left = rows[(pair_id, side, "sun_2024_frozen")]
        right = rows[(pair_id, side, "evidence_checks_v1")]
        assert left["requirement_sha256"] == right["requirement_sha256"]
        assert left["model_bpmn"] == right["model_bpmn"]
        assert left["model_bpmn_sha256"] == right["model_bpmn_sha256"]
        assert left["shared_binding"] == right["shared_binding"]
    thresholds = {json.dumps(r["shared_binding"]["thresholds"], sort_keys=True)
                  for r in stored["predictions"]}
    assert len(thresholds) == 1
    only = json.loads(thresholds.pop())
    configured = json.loads((ROOT / "configs/sun_stage3_development_v1.json")
                            .read_text(encoding="utf-8"))["method"]["thresholds"]
    assert only == {k: float(configured[k]) for k in ("tau", "gamma", "theta")}


def test_both_sides_of_a_pair_use_the_same_requirement(stored):
    by_pair: dict[str, set[str]] = {}
    for row in stored["predictions"]:
        by_pair.setdefault(row["pair_id"], set()).add(row["requirement_sha256"])
    assert all(len(values) == 1 for values in by_pair.values())


# --- unknown handling -------------------------------------------------------


def test_sun_zero_score_with_empty_denominator_becomes_unknown(runner):
    converted = runner.normalize_sun("out_of_order", {"score": 0.0, "denominator": 0})
    assert converted["status"] == "unknown"
    assert converted["raw_score"] == 0.0
    assert converted["reason"] == "zero_score_with_empty_denominator"
    assert converted["conversion"] == "sun_zero_score_empty_denominator"
    satisfied = runner.normalize_sun("out_of_order", {"score": 0.0, "denominator": 1})
    assert satisfied["status"] == "satisfied"
    unobservable = runner.normalize_sun("incorrect_actor",
                                        {"score": None, "denominator": 0, "observable": False,
                                         "reason": "no_matching_process_actor"})
    assert unobservable["status"] == "unknown"
    assert unobservable["conversion"] == "explicitly_unobservable"


def test_unknown_is_never_a_correct_satisfaction_in_the_evaluator(runner):
    contracts_doc = {"counts": {"fixed_variants": 1},
                     "contracts": [{"contract_id": "c1", "check_type": "out_of_order",
                                    "status": "valid"}]}
    rows = []
    for checker in runner.CHECKERS:
        for side, status in (("original", "unknown"), ("variant", "unknown")):
            rows.append({"pair_id": "c1", "side": side, "checker": checker,
                         "target_check": "out_of_order",
                         "signals": {"out_of_order": {"status": status}}})
    metrics = runner.evaluate(rows, contracts_doc)
    for checker in runner.CHECKERS:
        block = metrics["checkers"][checker]["per_type"]["out_of_order"]
        assert block["tn"] == 0, "a control unknown is not a correct rejection"
        assert block["fp"] == 0
        assert block["fn"] == 1, "a positive unknown is a miss"
        assert block["control_unknown"] == 1 and block["positive_unknown"] == 1
        assert block["recall"] == 0.0 and block["paired_success"] == 0


def test_every_unknown_row_records_a_conversion_or_native_reason(stored):
    for row in stored["predictions"]:
        for check, signal in row["signals"].items():
            if signal["status"] == "unknown":
                assert signal["reason"], (row["pair_id"], row["side"], row["checker"], check)
                assert signal["conversion"] in {
                    "none", "sun_zero_score_empty_denominator", "score_is_none",
                    "explicitly_unobservable", "empty_denominator_guard",
                    "unrecognised_status"}


# --- metrics reconstructible from stored rows ------------------------------


def test_metrics_are_recomputable_from_the_stored_predictions(runner, stored):
    recomputed = runner.evaluate(stored["predictions"], stored["contracts"])
    assert json.loads(json.dumps(recomputed, sort_keys=True)) == json.loads(
        json.dumps(stored["metrics"], sort_keys=True))


def test_paired_counts_are_consistent_with_the_per_item_statuses(stored):
    valid = {c["contract_id"] for c in stored["contracts"]["contracts"] if c["status"] == "valid"}
    for checker, block in stored["metrics"]["checkers"].items():
        for check in ("missing_action", "incorrect_actor", "out_of_order"):
            per_type = block["per_type"][check]
            rows = [r for r in stored["predictions"] if r["pair_id"] in valid
                    and r["checker"] == checker and r["target_check"] == check]
            assert len(rows) == 2 * per_type["valid_pairs"]
            control = [r for r in rows if r["side"] == "original"]
            positive = [r for r in rows if r["side"] == "variant"]
            statuses = lambda rs: [r["signals"][check]["status"] for r in rs]  # noqa: E731
            assert per_type["tp"] == statuses(positive).count("violation")
            assert per_type["fp"] == statuses(control).count("violation")
            assert per_type["tn"] == statuses(control).count("satisfied")
            assert per_type["fn"] == per_type["valid_pairs"] - per_type["tp"]
            assert per_type["positive_unknown"] == statuses(positive).count("unknown")
            assert per_type["control_unknown"] == statuses(control).count("unknown")
            assert per_type["paired_success"] == sum(
                1 for pair_id in per_type["per_pair"]
                if per_type["per_pair"][pair_id]["control"] == "satisfied"
                and per_type["per_pair"][pair_id]["variant"] == "violation")


def test_case_selection_follows_the_fixed_variant_id_rule(runner, stored):
    cases = runner.select_cases(stored["contracts"])
    assert [c["check_type"] for c in cases] == ["missing_action", "incorrect_actor", "out_of_order"]
    for case in cases:
        same_type = sorted((c["variant_id"] for c in stored["contracts"]["contracts"]
                            if c["check_type"] == case["check_type"] and c["status"] == "valid"))
        assert case["variant_id"] == same_type[0]


# --- inputs and previous artifacts unchanged -------------------------------


def test_frozen_inputs_and_previous_artifacts_are_unchanged(runner, stored):
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    for rel, binding in manifest["inputs"].items():
        assert runner.sha256_file(ROOT / rel) == binding["sha256_raw_working_tree"], rel
    previous = PREVIOUS_ROUND_DIR / "s3_evidence_repair_v1.manifest.json"
    previous_manifest = json.loads(previous.read_text(encoding="utf-8"))
    for section in ("implementation", "artifacts"):
        for rel, expected in previous_manifest[section].items():
            assert runner.sha256_file(ROOT / rel) == expected, f"{section}:{rel}"
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    for variant in panel["variants"]:
        assert runner.sha256_file(ROOT / variant["variant_bpmn"]) == variant["variant_bpmn_sha256"]


def test_manifest_declares_the_required_boundaries(stored):
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["declarations"] == {
        "development_only": True, "synthetic": True, "human_gold": False,
        "formal_oracle": False, "semantic_mapping_evaluated": False,
        "new_llm_api_calls": 0,
    }
    assert manifest["safety"]["llm_api_calls"] == 0
    assert manifest["safety"]["checkers_modified"] is False
    assert manifest["hash_conventions"]["scope"].startswith("this run pins only")


# --- deterministic replay ---------------------------------------------------


def test_replay_reproduces_contracts_and_predictions(rebuilt, stored):
    assert rebuilt["contracts"] == rebuilt["stored_contracts"]
    assert rebuilt["predictions"] == rebuilt["stored_predictions"]
    assert len(rebuilt["predictions"]) == 2 * 2 * stored["contracts"]["counts"]["valid_contracts"]


def test_replay_contract_lock_is_stable(runner, stored, rebuilt):
    lock_again = rebuilt["contracts"]
    for check, payload in stored["contracts"]["per_type"].items():
        assert lock_again["per_type"][check] == payload
    assert lock_again["counts"] == stored["contracts"]["counts"]
    assert lock_again["unresolved"] == stored["contracts"]["unresolved"]

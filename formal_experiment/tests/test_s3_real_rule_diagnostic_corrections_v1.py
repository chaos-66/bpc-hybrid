# -*- coding: utf-8 -*-
"""Focused checks for the real-rule diagnostic **correction** run.

Scope: this file only.  It runs no historical panel, no full suite and no batch
experiment.  Four native ``IncorrectActor`` invocations for v026/v032 are the only
checker calls it makes, and only once per session.

Covered requirements: every original item/method keeps an explicit corrected
evidence association; a corrected id is never a v1 id; ``mapped=false`` /
``violated=false`` actor evidence is never presented as judgment support; a
default false, an empty denominator and unknown ownership never turn into
satisfied evidence; one rule actor linked to two actions yields two correctly
bound evidences; different rule scopes and sources are not merged; repeated
references do not inflate the unique counts and both accounting bases are
conserved; an unmatched order endpoint is never typed as an event or as a
non-activity; a known node is typed by its real frozen-model kind and its order
support follows the model's representation and reachability rather than its node
kind; later-sentence conditions are aggregated over the whole rule and
applicability is recorded as ``not_evaluated``; the 66 original predictions are
byte- and field-identical; the summary is recomputable from the corrected
evidence and the stored predictions; the frozen Gold, BPMN, configuration,
checkers and historical artifacts are unchanged; and the corrected artifacts
replay deterministically offline.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/repair_s3_real_rule_diagnostics_v1.py"
V1_RUNNER = ROOT / "scripts/run_s3_real_rule_diagnostic_v1.py"
OUT = ROOT / "outputs/development/s3_real_rule_diagnostic_corrections_v1"
V1_OUT = ROOT / "outputs/development/s3_real_rule_diagnostic_v1"
SUN = "sun_2024_frozen"
V3 = "evidence_checks_v3_action_structure"
METHODS = (SUN, V3)
V1_RESULT_KEYS = {"predictions.jsonl": "predictions",
                  "mapping_evidence.jsonl": "mapping_evidence",
                  "scope_review.json": "scope_review", "summary.json": "summary"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load(RUNNER, "s3_real_rule_diagnostic_corrections_runner")


@pytest.fixture(scope="module")
def v1_runner():
    return _load(V1_RUNNER, "s3_real_rule_diagnostic_v1_runner_for_corrections")


@pytest.fixture(scope="module")
def verified(runner):
    return runner.verify_outputs()


@pytest.fixture(scope="module")
def evidence(verified):
    return verified["evidence"]


@pytest.fixture(scope="module")
def corrections(verified):
    return verified["corrections"]


@pytest.fixture(scope="module")
def summary(verified):
    return verified["summary"]


@pytest.fixture(scope="module")
def stored_predictions(v1_runner):
    return v1_runner.read_jsonl(V1_OUT / "predictions.jsonl")


@pytest.fixture(scope="module")
def rule_records(v1_runner):
    return v1_runner.build_rule_inputs()["records"]


@pytest.fixture(scope="module")
def live_recomputation(runner, v1_runner):
    """One live native recovery of the four authorised checker calls."""
    return runner.recompute_actor_pairs(runner.read_v1_artifacts(),
                                        v1_runner.build_rule_inputs())


def _units(evidence, family=None, method=None):
    return [row for row in evidence
            if (family is None or row["family"] == family)
            and (method is None or row["method"] == method)]


def _contexts(evidence, family, method):
    return [context for row in _units(evidence, family, method)
            for context in row["check_context_returns"]]


def _item_units(evidence, corrections, item_id, method, family):
    entry = next(row for row in corrections["prediction_evidence_map"]
                 if row["item_id"] == item_id and row["method"] == method)
    by_id = {row["evidence_id"]: row for row in evidence}
    return [by_id[eid] for eid in entry["corrected_evidence_ids"]
            if by_id[eid]["family"] == family]


# --- association and identity ----------------------------------------------


def test_every_original_item_and_method_has_a_corrected_association(
        verified, corrections, evidence):
    stored = verified["stored"]
    mapping = corrections["prediction_evidence_map"]
    assert len(mapping) == 66
    assert {(row["item_id"], row["method"]) for row in mapping} == \
        {(row["item_id"], row["method"]) for row in stored["predictions"]}
    known = {row["evidence_id"] for row in evidence}
    empty = 0
    for entry in mapping:
        for eid in entry["v1_evidence_ids"]:
            assert eid in stored["evidence_index"]
        for eid in entry["corrected_evidence_ids"]:
            assert eid in known
        assert len(entry["corrected_evidence_ids"]) == len(entry["v1_evidence_ids"])
        assert len(entry["v1_to_corrected"]) == len(set(entry["v1_evidence_ids"]))
        if not entry["v1_evidence_ids"]:
            # a rule side with no requirement for this check type keeps an empty
            # population in v1 and in the correction alike
            assert entry["reason"] in {"missing_rule_order_relations",
                                       "zero_score_with_empty_denominator",
                                       "empty_rule_action_set",
                                       "missing_rule_actor_action_map",
                                       "empty_rule_actor_denominator"}, entry["item_id"]
            empty += 1
    assert empty == 20


def test_corrected_evidence_uses_its_own_id_namespace(evidence, verified):
    v1_ids = set(verified["stored"]["evidence_index"])
    ids = [row["evidence_id"] for row in evidence]
    assert len(evidence) == 126
    assert len(ids) == len(set(ids))
    for eid in ids:
        assert eid.startswith("cev_") and eid not in v1_ids


def test_corrected_dedup_key_is_written_down_and_hashes_to_the_id(runner, evidence):
    for row in evidence:
        assert row["dedup_key_fields"] == runner.DEDUP_KEY_FIELDS[row["family"]]
        assert row["dedup_key_sha1"] == runner.sha1_text(runner.canonical(row["dedup_key"]))
        assert row["evidence_id"] == "cev_" + row["dedup_key_sha1"][:16]
        for field in row["dedup_key_fields"]:
            assert field in row["dedup_key"]


def test_different_scope_process_or_source_is_not_merged(evidence):
    endpoints = _units(evidence, "order_endpoint")
    scopes = defaultdict(set)
    for row in endpoints:
        scopes[row["requirement_text"]].add((row["dedup_key"]["rule_id"],
                                             row["dedup_key"]["process_id"]))
    assert len(scopes["giving consent"]) == 2, "the same endpoint text in two processes"
    assert len(scopes["be informed thereof"]) == 2
    actors = _units(evidence, "actor_action_pair")
    for row in actors:
        key = row["dedup_key"]
        assert key["rule_id"] and key["process_id"]
        assert key["actor_requirement"] == row["requirement_text"]
        assert key["linked_action_requirement"] == row["linked_action_requirement"]
    assert len({row["dedup_key_sha1"] for row in actors}) == len(actors)
    assert len({row["dedup_key_sha1"] for row in endpoints}) == len(endpoints)


def test_source_is_a_list_not_the_first_match(evidence):
    multi = [row for row in evidence if len(row["sources"]) > 1]
    assert multi, "shared requirements must keep every confirmed source span"
    for row in multi:
        assert row["source_note"].startswith(f"{len(row['sources'])} confirmed clause spans")
        for source in row["sources"]:
            assert source["span"]["start"] < source["span"]["end"]
            assert source["kind"] in {"action", "actor"}
    for row in evidence:
        assert row["source_state"] in {"clause_span", "projected_temporal_note", "not_located"}
        if row["source_state"] == "not_located":
            assert not row["sources"] and row["temporal_note"] is None
        if row["source_state"] == "projected_temporal_note":
            assert row["temporal_note"]["source"] == "confirmed_temporal_note"
            assert row["temporal_note"]["creates_mandatory_action"] is False
            assert any("not a modelled process action" in note
                       for note in row["capability_notes"])


# --- problem 1: unmapped is not evidence support ----------------------------


def test_unmapped_actor_evidence_is_never_evidence_support(evidence):
    actors = _units(evidence, "actor_action_pair")
    assert len(actors) == 26
    for row in actors:
        payload = row["native_evidence"]["payload"]
        assert payload["linked_action_mapped"] is False
        assert row["state"]["state"] == "linked_action_not_reliably_mapped"
        assert row["state"]["judgment_support"]["complete"] is False
        assert row["state"]["violated_is_positive_evidence"] is False
        assert row["state"]["judgment_support"]["missing"]


def test_no_method_reports_a_completed_executor_comparison(summary):
    for method in METHODS:
        block = summary["coverage"]["families"]["actor_action_pair"]["per_method"][method]
        assert block["unique_units"] == 13
        assert block["judgment_support_complete_units"] == 0
        assert block["state_counts"] == {"linked_action_not_reliably_mapped": 13}
    assert summary["coverage"]["families"]["actor_action_pair"]["per_method"][
        SUN]["clause_level_aggregate_units"] == 13


def test_default_false_and_empty_denominator_are_not_satisfaction(
        evidence, stored_predictions, corrections):
    by_row = {(row["item_id"], row["method"]): row for row in stored_predictions}
    by_id = {row["evidence_id"]: row for row in evidence}
    # a judgment-support claim is scoped to the check contexts that actually return
    # requirement-level information
    for row in evidence:
        available = {context["check_type"] for context in row["check_context_returns"]
                     if context["requirement_level_return_available"] is True}
        support = row["state"]["judgment_support"]
        assert set(support["complete_in_check_types"]) <= available, row["evidence_id"]
        assert support["complete"] is bool(support["requirement_observed"] and available)
    checked = 0
    for item in corrections["prediction_evidence_map"]:
        row = by_row[(item["item_id"], item["method"])]
        if row["denominator"] != 0 or row["status"] != "unknown":
            continue
        for eid in item["corrected_evidence_ids"]:
            unit = by_id[eid]
            checked += 1
            # the actor comparison and the order judgement are governed by the
            # observable denominator of this very check instance
            if unit["family"] in {"actor_action_pair", "order_endpoint"}:
                assert unit["state"]["judgment_support"]["complete"] is False, eid
                assert row["check_type"] not in unit["state"]["judgment_support"][
                    "complete_in_check_types"]
            for context in unit["check_context_returns"]:
                if context["requirement_level_return_available"] is False:
                    assert context["check_type"] not in unit["state"]["judgment_support"][
                        "complete_in_check_types"], eid
                else:
                    assert context["requirement_level_return_basis"]
    assert checked > 0
    # no corrected state reuses the retracted name, and no old value was "satisfied"
    assert all("evidence_supports_judgment" not in json.dumps(row["state"])
               for row in evidence)
    for entry in corrections["per_unit_corrections"]:
        for change in entry["corrections"]:
            if change["field"] == "mapping_state":
                assert change["old"].startswith("evidence_supports_judgment") or \
                    change["old"] == "order_endpoint_not_an_activity"
                assert not change["new"].startswith("evidence_supports_judgment")
                assert change["new"] != "order_endpoint_not_an_activity"
                assert change["reason"]


def test_violated_false_is_not_presented_as_a_satisfied_verdict(evidence):
    for row in _units(evidence, "actor_action_pair"):
        assert row["state"]["violated_field"] in {False, None}
        assert row["state"]["violated_is_positive_evidence"] is False
        payload = row["native_evidence"]["payload"]
        assert payload["executors_observed"] is not True or payload["linked_action_mapped"]
        assert "matched_activity_executors" not in payload
        assert "candidate_best_activity_executors" in payload
        if not payload["linked_action_mapped"]:
            assert payload["executors_of_matched_activity"] == []


def test_candidate_executors_are_not_named_matched_activity_executors(corrections):
    entry = next(item for item in corrections["corrections"]
                 if item["correction_id"] == "C1_unmapped_is_not_evidence_support")
    assert entry["old_value"]["class"] == "evidence_supports_judgment"
    assert entry["new_value"]["renamed_fields"]["v1"] == \
        "mapping.matched_activity_executors"
    assert entry["new_value"]["renamed_fields"]["corrected"].startswith(
        "candidate_best_activity_executors")
    assert entry["new_value"]["executor_comparison_performed"] == {SUN: 0, V3: 0}
    assert sorted(entry["new_value"]["rule_has_no_actor_requirement_items"]) == \
        ["v020", "v029"]
    assert entry["new_value"]["per_pair_field_absent_units"][SUN] == 13


# --- problem 2: actor-action pair identity ---------------------------------


def test_v026_and_v032_each_keep_two_bound_actor_action_pairs(
        evidence, corrections, rule_records):
    for item_id, process_id in (("v026", "gdpr_5_right_to_withdraw"),
                                ("v032", "gdpr_7_right_to_be_forgotten")):
        expected = rule_records["article17"]["actor_action_pairs"]
        assert [pair["action"] for pair in expected] == ["erase personal data",
                                                         "take reasonable steps"]
        for method in METHODS:
            units = _item_units(evidence, corrections, item_id, method, "actor_action_pair")
            assert len(units) == 2, (item_id, method)
            assert {row["linked_action_requirement"] for row in units} == \
                {pair["action"] for pair in expected}
            assert {row["requirement_text"] for row in units} == {"the controller"}
            assert len({row["dedup_key_sha1"] for row in units}) == 2
            for row in units:
                assert row["process_id"] == process_id
                assert row["requirement_text"] in rule_records["article17"]["actors"]
                assert row["linked_action_requirement"] in rule_records["article17"]["actions"]
    restored = corrections["associations_restored"]
    assert restored["restored"] is True
    assert (restored["native_calls_used"], restored["native_calls_allowed"]) == (4, 4)
    for item_id in ("v026", "v032"):
        assert restored["restored_pair_units"][item_id] == {SUN: 2, V3: 2}


def test_a_merged_v1_id_maps_to_both_corrected_units(corrections):
    splits = [entry for entry in corrections["prediction_evidence_map"]
              if entry["split_v1_evidence_ids"]]
    assert {entry["item_id"] for entry in splits} == {"v026", "v032"}
    for entry in splits:
        assert len(entry["split_v1_evidence_ids"]) == 1
        v1_id = entry["split_v1_evidence_ids"][0]
        mapped = next(change for change in entry["v1_to_corrected"]
                      if change["v1_evidence_id"] == v1_id)
        assert len(mapped["corrected_evidence_ids"]) == 2
        for eid in mapped["corrected_evidence_ids"]:
            assert eid in entry["corrected_evidence_ids"]
        assert entry["new_corrected_evidence_ids"]
        assert entry["v1_evidence_ids"].count(v1_id) == 2


def test_each_actor_pair_points_back_to_its_own_action_evidence(
        evidence, corrections):
    for method in METHODS:
        actors = _units(evidence, "actor_action_pair", method)
        for row in actors:
            linked = row["linked_action_requirement"]
            for context in row["check_context_returns"]:
                item_actions = {other["requirement_text"] for other in _item_units(
                    evidence, corrections, context["item_id"], method, "action_requirement")}
                assert linked in item_actions, (row["evidence_id"], context["item_id"])
            matching = {other["dedup_key_sha1"] for other in
                        _units(evidence, "action_requirement", method)
                        if other["process_id"] == row["process_id"]
                        and other["dedup_key"]["rule_id"] == row["dedup_key"]["rule_id"]
                        and other["requirement_text"] == linked}
            assert len(matching) == 1


# --- problem 3: reference counts vs unique counts ---------------------------


def test_reference_and_unique_counts_are_conserved_separately(evidence, summary):
    families = summary["coverage"]["families"]
    for method in METHODS:
        for family, refs, units in (("action_requirement", 84, 42),
                                    ("actor_action_pair", 13, 13),
                                    ("order_endpoint", 8, 8)):
            block = families[family]["per_method"][method]
            assert len(_contexts(evidence, family, method)) == refs
            assert block["requirement_references"] == refs
            assert len(_units(evidence, family, method)) == units
            assert block["unique_units"] == units
            assert block["dedup_reduction"] == refs - units
            assert sum(block["references_by_check_type"].values()) == refs
        for family in ("action_requirement", "actor_action_pair", "order_endpoint"):
            assert families[family]["dedup_key_fields"] == \
                summary["corrected_evidence"]["dedup_keys"][family]


def test_an_action_used_by_two_checks_counts_once_as_a_unit(evidence):
    for method in METHODS:
        actions = _units(evidence, "action_requirement", method)
        assert len(actions) == 42
        assert len({row["dedup_key_sha1"] for row in actions}) == 42
        for row in actions:
            contexts = row["check_context_returns"]
            assert {context["check_type"] for context in contexts} == {"missing_action",
                                                                      "incorrect_actor"}
            assert len({context["item_id"] for context in contexts}) == 2


def test_v3_action_support_is_limited_to_the_contexts_that_evaluate_it(evidence, rule_records):
    """The IncorrectActor check only evaluates the actions of its declared pairs."""
    paired_by_rule = {rule_id: {pair["action"] for pair in
                                (record.get("actor_action_pairs") or [])}
                      for rule_id, record in rule_records.items()}
    assert len(paired_by_rule["article17"]) == 2
    assert len(rule_records["article17"]["actions"]) == 3
    non_paired = 0
    for row in _units(evidence, "action_requirement", V3):
        rule_id = row["dedup_key"]["rule_id"]
        contexts = {context["check_type"]: context for context in row["check_context_returns"]}
        assert contexts["missing_action"]["requirement_level_return_available"] is True
        expected = row["requirement_text"] in paired_by_rule[rule_id]
        assert contexts["incorrect_actor"]["requirement_level_return_available"] is expected, row
        if not expected:
            non_paired += 1
            assert "never evaluates it" in \
                contexts["incorrect_actor"]["requirement_level_return_basis"]
            assert "incorrect_actor" not in \
                row["state"]["judgment_support"]["complete_in_check_types"]
    assert non_paired > 0


def test_check_context_returns_are_preserved_per_context(evidence):
    for row in _units(evidence, "action_requirement", SUN):
        contexts = {context["check_type"]: context for context in row["check_context_returns"]}
        assert contexts["missing_action"]["requirement_level_return_available"] is True
        assert contexts["incorrect_actor"]["requirement_level_return_available"] is False
        assert "Definition 6" in contexts["incorrect_actor"]["requirement_level_return_basis"]
        assert contexts["incorrect_actor"]["check_level_return"]["reason"] in {
            "action_mapping_below_gamma", "requirement_evidence_not_satisfied",
            "empty_rule_actor_denominator", "no_candidate_above_gamma"}
    for row in _units(evidence, "actor_action_pair", SUN):
        assert row["state"]["per_pair_native_field_present"] is False
        assert row["state"]["aggregation_level"] == "clause_level"
        for context in row["check_context_returns"]:
            assert context["requirement_level_return_available"] is False
    for row in evidence:
        provenance = row["v1_payload_provenance"]
        assert provenance["first_write_wins"] is True
        assert provenance["written_in_context"]["check_type"] in {
            "missing_action", "incorrect_actor", "out_of_order"}
        for context in provenance["reused_in_check_contexts"]:
            assert context["item_id"] and context["check_type"]


def test_no_mixed_overall_mapping_rate_is_reported(summary):
    coverage = summary["coverage"]
    assert set(coverage["families"]) == {"action_requirement", "actor_action_pair",
                                         "order_endpoint"}
    assert "overall_mapping_rate" not in json.dumps(coverage, ensure_ascii=False)
    for family, block in coverage["families"].items():
        assert set(block["per_method"]) == {SUN, V3}
        assert "unique_units" in block["per_method"][SUN]
        assert block["definition"]
    assert coverage["note"].startswith("reference counts and unique counts are reported "
                                       "separately")


# --- problem 4: order endpoint states --------------------------------------


def test_unmatched_endpoints_are_never_typed_as_event_or_non_activity(evidence):
    endpoints = _units(evidence, "order_endpoint")
    assert len(endpoints) == 16
    for row in endpoints:
        state = row["state"]
        payload = row["native_evidence"]["payload"]
        if payload["mapped"]:
            assert state["match_state"] in {"matched_to_activity", "matched_to_event"}
            assert state["node_kind_claimed"] in {"activity", "event"}
        else:
            assert state["match_state"] == "unmatched_kind_unknown"
            assert state["node_kind_claimed"] is None
            assert state["candidate_node_kind_recorded"] in {"activity", "event", None}
            assert state["candidate_is_not_the_endpoint"] is True
            assert "node kind" in state["match_state_basis"]
        assert "order_endpoint_not_an_activity" not in json.dumps(state)


def test_endpoint_states_report_match_and_source_axes_separately(summary, evidence):
    coverage = summary["coverage"]
    for key in ("order_endpoint_named_states", "order_endpoint_source_states",
                "order_endpoint_state_cross"):
        assert sum(coverage[key].values()) == 16
    assert coverage["order_endpoint_named_states"] == {
        "sun_2024_frozen|unmatched_kind_unknown": 8,
        "evidence_checks_v3_action_structure|matched_to_activity": 1,
        "evidence_checks_v3_action_structure|unmatched_kind_unknown": 7}
    sources = Counter(row["state"]["source_state"] for row in _units(evidence, "order_endpoint"))
    assert sources == {"projected_temporal_note": 10, "clause_span": 6}
    assert coverage["model_representation"]["events_are_match_candidates"] is True


def test_matched_endpoint_kind_agrees_with_the_frozen_model(runner, corrections, evidence):
    probe = corrections["frozen_model_probe"]["node_facts"]
    matched = [row for row in _units(evidence, "order_endpoint")
               if row["state"]["match_state"] == "matched_to_activity"]
    assert len(matched) == 1
    row = matched[0]
    node_id = row["native_evidence"]["payload"]["matched_node_id"]
    facts = probe[f"{row['process_id']}|{node_id}"]
    assert facts["node_kind"] == "activity"
    assert row["state"]["node_kind_claimed"] == facts["node_kind"]
    assert row["model_support"]["node_reachability_participation"] == {
        "has_outgoing_reachability": facts["has_outgoing_reachability"],
        "reachability_successors": facts["reachability_successors"],
        "appears_as_reachability_target": facts["appears_as_reachability_target"]}
    assert row["state"]["judgment_support"]["complete"] is False
    assert "both_endpoints_of_the_order_constraint_matched" in \
        row["state"]["judgment_support"]["missing"]


def test_event_nodes_are_real_candidates_and_typed_by_kind_not_by_failure(runner, corrections):
    probe = corrections["frozen_model_probe"]
    events = sorted((process, node_id) for process, block in probe["per_process"].items()
                    for node_id in block["event_node_ids"])
    assert events, "the frozen candidate list must contain events"
    assert "activities" in probe["declaration"] and "events" in probe["declaration"]
    process, node_id = events[0]
    facts = probe["node_facts"][f"{process}|{node_id}"]
    assert facts["node_kind"] == "event"
    for reachable in (True, False):
        state = runner.classify_endpoint(
            {"mapped": True, "node_kind": "event", "candidate_node_kind": "event",
             "can_support_order_judgement": reachable, "order_judgement_basis": "reachability",
             "judgment_missing": [] if reachable else ["frozen_reachability_evaluated_for_the_pair"]},
            "clause_span")
        assert state["match_state"] == "matched_to_event"
        assert state["node_kind_claimed"] == "event"
        assert state["judgment_support"]["complete"] is reachable
    unmatched = runner.classify_endpoint(
        {"mapped": False, "node_kind": None, "candidate_node_kind": "event"},
        "clause_span")
    assert unmatched["match_state"] == "unmatched_kind_unknown"
    assert unmatched["node_kind_claimed"] is None


def test_retraction_of_the_event_support_conclusion(corrections):
    entry = next(item for item in corrections["corrections"]
                 if item["correction_id"] == "C4_order_endpoint_states")
    assert entry["old_value"]["class"] == "order_endpoint_not_an_activity"
    assert entry["old_value"]["counts"] == {SUN: 8, V3: 7}
    assert entry["new_value"]["events_are_match_candidates"] is True
    for reasons in entry["new_value"]["blocking_reasons"].values():
        assert set(reasons) <= {"rule_carries_no_order_relation",
                                "order_endpoint_unmatched_in_this_method"}
    assert any("retracted" in line and "events" in line
               for line in corrections["capability_limits"])
    assert "event" in entry["reason"]


def test_order_item_blocking_reasons_match_the_recorded_check_returns(
        corrections, stored_predictions, rule_records):
    rows = {(row["item_id"], row["method"]): row for row in stored_predictions}
    order_items = [item for item in corrections["prediction_evidence_map"]
                   if item["check_type"] == "out_of_order"]
    assert len(order_items) == 22
    for item in order_items:
        relations = rule_records[item["rule_id"]]["order_relations"]
        row = rows[(item["item_id"], item["method"])]
        assert len(item["corrected_evidence_ids"]) == 2 * len(relations)
        if not relations:
            assert row["reason"] in {"missing_rule_order_relations",
                                     "zero_score_with_empty_denominator"}
        else:
            assert relations and item["item_id"] in {"v003", "v009", "v024"}


# --- problem 5: conditions over all sentences -------------------------------


def test_conditions_are_aggregated_over_every_sentence(v1_runner, summary, corrections):
    gold = v1_runner.read_json(v1_runner.GOLD_RULE_RECORDS)
    profile = summary["applicability"]["per_rule"]
    recount = defaultdict(Counter)
    sentences = Counter()
    for record in gold["records"]:
        sentences[record["rule_id"]] += 1
        for clause in record["clauses"]:
            recount[record["rule_id"]]["clauses"] += 1
            recount[record["rule_id"]]["conditions"] += bool(clause["conditions"])
            recount[record["rule_id"]]["constraints"] += bool(clause["constraints"])
            recount[record["rule_id"]]["exceptions"] += bool(clause["exceptions"])
    for rule_id, values in profile.items():
        assert values["sentence_count"] == sentences[rule_id]
        assert values["clause_count"] == recount[rule_id]["clauses"]
        assert values["clauses_with_conditions"] == recount[rule_id]["conditions"]
        assert values["clauses_with_constraints"] == recount[rule_id]["constraints"]
        assert values["clauses_with_exceptions"] == recount[rule_id]["exceptions"]
    assert profile["article17"]["sentence_count"] == 13
    assert profile["article17"]["clauses_with_conditions"] == 9
    assert summary["applicability"]["totals"]["clauses_with_conditions"] == 49
    entry = next(item for item in corrections["corrections"]
                 if item["correction_id"] == "C5_conditions_over_all_sentences")
    assert "returned after the first sentence" in entry["old_value"]["old_behaviour"]
    assert entry["old_value"]["aggregate_counts_reported"] is False
    assert entry["new_value"]["aggregation"] == "all sentences and all clauses of the rule"


def test_applicability_is_recorded_as_not_evaluated(summary):
    assert summary["applicability"]["evaluation"] == "not_evaluated"
    assert summary["applicability"]["evaluated_by_checkers"] is False
    assert "converter" in summary["applicability"]["reason"]
    assert set(summary["applicability"]["per_item_evaluation"].values()) == {"not_evaluated"}
    assert len(summary["applicability"]["per_item_evaluation"]) == 33
    assert len(summary["applicability"]["items_with_unconsumed_condition_context"]) == 33
    assert any("not_evaluated" in line for line in
               [json.dumps(summary["applicability"], ensure_ascii=False)])


# --- unchanged predictions --------------------------------------------------


def test_original_predictions_are_byte_and_field_identical(
        runner, verified, corrections, stored_predictions):
    v1_manifest = json.loads((V1_OUT / "manifest.json").read_text(encoding="utf-8"))
    bound = v1_manifest["results"]["predictions"]["sha256"]
    assert sha256(V1_OUT / "predictions.jsonl") == bound
    assert verified["stored"]["predictions_sha256"] == bound
    assert corrections["prediction_status"]["predictions_sha256"] == bound
    assert corrections["prediction_status"]["byte_identical"] is True
    assert corrections["prediction_status"]["rows_rewritten"] == 0
    assert len(stored_predictions) == 66
    for entry in corrections["prediction_evidence_map"]:
        row = next(item for item in stored_predictions
                   if item["item_id"] == entry["item_id"] and item["method"] == entry["method"])
        assert entry["row_sha256"] == runner.canonical_sha256(row)
        for field in ("status", "score", "denominator", "reason", "check_type", "process_id",
                      "rule_id"):
            assert entry[field] == row[field]
    assert verified["summary"]["predictions"]["modified"] is False


def test_summary_is_recomputable_from_corrected_evidence_and_predictions(
        summary, evidence, stored_predictions, corrections):
    for method in METHODS:
        assert summary["status_totals"][method] == dict(Counter(
            row["status"] for row in stored_predictions if row["method"] == method))
    families = summary["coverage"]["families"]
    for method in METHODS:
        for family in ("action_requirement", "actor_action_pair", "order_endpoint"):
            block = families[family]["per_method"][method]
            assert block["requirement_references"] == len(_contexts(evidence, family, method))
            assert block["unique_units"] == len(_units(evidence, family, method))
            states = Counter(row["state"].get("state") or row["state"]["combined_state"]
                             for row in _units(evidence, family, method))
            assert block["state_counts"] == dict(sorted(states.items()))
            assert block["judgment_support_complete_units"] == sum(
                1 for row in _units(evidence, family, method)
                if row["state"]["judgment_support"]["complete"])
    new = corrections["count_table"]["new"]
    old = corrections["count_table"]["old"]
    for method in METHODS:
        assert new["unique_counts"][method] == {"action_requirement": 42,
                                                "actor_action_pair": 13, "order_endpoint": 8}
        assert new["reference_counts"][method] == {"action_requirement": 84,
                                                   "actor_action_pair": 13, "order_endpoint": 8}
        assert old["unique_counts"][method]["actor_action_pair_units"] == 11
        assert old["reference_counts"][method]["action_requirement_references"] == 84
        assert old["denominators"][method]["required_actions_checked"] == 84
    assert old["class_counts"][V3]["evidence_supports_judgment"] == 14


# --- frozen assets and outputs ---------------------------------------------


def test_frozen_inputs_and_implementation_are_unchanged(verified):
    manifest = verified["manifest"]
    v1_manifest = json.loads((V1_OUT / "manifest.json").read_text(encoding="utf-8"))
    for section in ("inputs", "implementation"):
        assert set(manifest[section]) == set(v1_manifest[section])
        for rel, binding in manifest[section].items():
            assert binding["sha256_raw_working_tree"] == \
                v1_manifest[section][rel]["sha256_raw_working_tree"], rel
            assert sha256(ROOT / rel) == binding["sha256_raw_working_tree"], rel
    for name, key in V1_RESULT_KEYS.items():
        assert sha256(V1_OUT / name) == v1_manifest["results"][key]["sha256"], name
    for bpmn in sorted((ROOT / "data/input/stage1_stage3/gdpr7").glob("*.bpmn")):
        assert bpmn.stat().st_size > 0


def test_output_directory_holds_exactly_four_files_and_copies_nothing(verified):
    assert sorted(path.name for path in OUT.iterdir()) == [
        "corrections.json", "manifest.json", "mapping_evidence.jsonl", "summary.json"]
    assert not (OUT / "predictions.jsonl").exists()
    assert not (OUT / "scope_review.json").exists()
    for name, entry in verified["manifest"]["superseded_artifacts"].items():
        assert entry["copied_into_this_run"] is False
        assert entry["modified"] is False
        assert sha256(ROOT / entry["path"]) == entry["sha256"], name
    assert verified["summary"]["v1_reference"]["copied"] is False
    assert verified["summary"]["performance_claim_ready"] is False
    assert verified["corrections"]["declarations"]["predictions_modified"] is False


# --- native recomputation ---------------------------------------------------


def test_native_recomputation_is_four_calls_and_matches_the_record(
        runner, live_recomputation, corrections, stored_predictions):
    recorded = corrections["recomputation"]
    assert recorded["performed"] is True
    assert (recorded["call_count"], recorded["max_allowed_calls"]) == (4, 4)
    assert recorded["batch_rerun"] is False
    assert recorded["recoverable_from_stored_artifacts"] is False
    assert live_recomputation["call_count"] == 4
    assert runner.calls_signature(live_recomputation["calls"]) == \
        runner.calls_signature(recorded["calls"])
    assert live_recomputation["pairs_by_item"] == recorded["pairs_by_item"]
    rows = {(row["item_id"], row["method"]): row for row in stored_predictions}
    for call in recorded["calls"]:
        assert call["check_type"] == "incorrect_actor"
        assert call["item_id"] in {"v026", "v032"}
        assert call["matches_stored_prediction"] is True
        row = rows[(call["item_id"], call["method"])]
        assert (call["native_status"], call["native_score"], call["native_denominator"],
                call["native_reason"]) == (row["status"], row["score"], row["denominator"],
                                           row["reason"])
        assert call["pairs_returned"] == 2
    assert live_recomputation["frozen_model_probe"] == corrections["frozen_model_probe"]


def test_recomputed_pairs_are_labelled_as_new_measurements(evidence, corrections):
    for method in METHODS:
        for row in _units(evidence, "actor_action_pair", method):
            touched = any(context["item_id"] in {"v026", "v032"}
                          for context in row["check_context_returns"])
            assert row["native_evidence"]["basis"] == (
                "recomputed_native_repair" if touched else "stored_v1_payload")
    assert "not evidence the original v1 run saved" in \
        corrections["recomputation"]["new_evidence_note"]
    assert corrections["missing_evidence"]


def test_live_probe_reports_real_activity_and_event_nodes(live_recomputation):
    probe = live_recomputation["frozen_model_probe"]
    assert sum(block["event_count"] for block in probe["per_process"].values()) > 0
    assert sum(block["activity_count"] for block in probe["per_process"].values()) > 0
    for facts in probe["node_facts"].values():
        assert facts["node_kind"] in {"activity", "event"}
        assert isinstance(facts["has_outgoing_reachability"], bool)
        assert isinstance(facts["appears_as_reachability_target"], bool)


# --- determinism ------------------------------------------------------------


def test_offline_replay_reproduces_every_corrected_artifact(runner):
    payload = runner.replay_payload()
    assert payload["evidence"] == payload["stored_evidence"]
    assert payload["summary"] == payload["stored_summary"]
    assert payload["corrections"] == payload["stored_corrections"]
    assert len(payload["evidence"]) == 126

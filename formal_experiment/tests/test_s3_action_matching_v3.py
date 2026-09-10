# -*- coding: utf-8 -*-
"""Independent checks for the v3 structured action representation and matching.

Real-NLP behaviour tests use the installed ``en_core_web_sm`` model and the frozen
``WinterSimilarity`` backend on short, GDPR-unrelated actions.  Tests that need a
controlled similarity value use a stub backend and say so: they are isolated logic
tests, not model results.

Passing counts are not an experimental result; the panel numbers come from the
stored predictions of the run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.s3_action_matching_v3 import (  # noqa: E402
    METHOD, METHOD_ID, MODIFICATION_SCOPE, EvidenceChecksV3, match_policy,
)
from bpc_hybrid.s3_action_matching_v2 import EvidenceChecksV2  # noqa: E402

OUT = ROOT / "outputs/development/s3_action_matching_v3"
V2_OUT = ROOT / "outputs/development/s3_action_matching_v2"
RUNNER = ROOT / "scripts/run_s3_action_matching_v3.py"


class StubSimilarity:
    """Isolated logic stub: one configured pair is similar, everything else is not."""

    def __init__(self, pair, value):
        self.pair = {part.casefold() for part in pair}
        self.value = value

    def text_pair(self, left, right):
        if {left.casefold(), right.casefold()} == self.pair:
            return self.value
        return 0.0


@pytest.fixture(scope="module")
def nlp():
    import spacy
    return spacy.load("en_core_web_sm")


@pytest.fixture(scope="module")
def checker(nlp):
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    return EvidenceChecksV3(WinterSimilarity(nlp), 0.8, 0.8, 0.8, nlp=nlp)


def model(names):
    actions = [{"id": f"x{index}", "name": name} for index, name in enumerate(names)]
    return SimpleNamespace(actions=actions, record={"lanes": []},
                           action_actor_names={a["id"]: ["Clerk"] for a in actions},
                           business_objects=[], actors=["Clerk"],
                           is_reachable=lambda source, target: False)


def match(checker, requirement, names):
    return checker.action_match(requirement, model(names))


def reason_codes(result):
    return sorted({reason["code"] for reason in result.get("best", {}).get("reasons", [])})


# --- representation --------------------------------------------------------


def test_structure_record_keeps_nested_actions_roles_and_spans(checker):
    structure = checker._structure('Add "existence of the right to rectify of personal data"')
    assert structure["predicate"] == "add"
    assert [item["verb"] for item in structure["nested"]] == ["rectify"]
    assert structure["nested"][0]["objects"] == ["datum"]
    assert structure["nested"][0]["slot"] == "acl"
    assert structure["nested"][0]["span"][0] < structure["nested"][0]["span"][1]
    assert structure["text"] == 'Add "existence of the right to rectify of personal data"'
    roles = checker._structure("Transfer money from Alice to Bob")["roles"]
    assert roles == {"from": ["alice"], "to": ["bob"]}


def test_nested_action_difference_is_not_flattened(checker):
    result = match(checker, "Add the right to read a file", ["Add the right to delete a file"])
    assert result["mapped"] is False
    assert result["match_tier"] == "structure_not_satisfied"
    assert "nested_action_substituted" in reason_codes(result)
    requirement = checker._structure("Add the right to read a file")
    candidate = checker._structure("Add the right to delete a file")
    assert requirement["objects"] == candidate["objects"]
    assert [item["verb"] for item in requirement["nested"]] != \
        [item["verb"] for item in candidate["nested"]]


def test_relation_containment_keeps_the_structure_and_stays_undetermined(checker):
    result = match(checker, "Stop running the pump using coolant", ["Stop using coolant"])
    assert result["mapped"] is False
    assert result["match_tier"] == "structure_undetermined"
    codes = reason_codes(result)
    assert "nested_action_component_containment" in codes
    assert "required_object_content_absent" in codes
    narrower = checker._structure("Stop running the pump using coolant")["nested"]
    broader = checker._structure("Stop using coolant")["nested"]
    assert [item["verb"] for item in narrower] == ["run", "use"]
    assert [item["verb"] for item in broader] == ["use"]
    reverse = match(checker, "Stop using coolant", ["Stop running the pump using coolant"])
    assert reverse["mapped"] is True


def test_role_swap_is_detected(checker):
    result = match(checker, "Transfer money from Alice to Bob",
                   ["Transfer money from Bob to Alice"])
    assert result["mapped"] is False
    assert "role_content_difference" in reason_codes(result)
    paraphrase = match(checker, "Transfer money from Alice to Bob",
                       ["Transfer the money from Alice to Bob"])
    assert paraphrase["mapped"] is True


# --- candidate decision rules ----------------------------------------------


def test_unrelated_candidate_does_not_veto_a_supported_match(checker):
    assert match(checker, "Inspect package", ["Examine package"])["mapped"] is True
    with_distractor = match(checker, "Inspect package",
                            ["Examine package", "Inspect furniture"])
    assert with_distractor["mapped"] is True
    assert match(checker, "Approve invoice", ["Authorize invoice"])["mapped"] is True
    with_distractor = match(checker, "Approve invoice",
                            ["Authorize invoice", "Approve furniture"])
    assert with_distractor["mapped"] is True
    assert match(checker, "Inspect package", ["Inspect furniture"])["mapped"] is False


def test_identical_labels_on_two_activities_stay_unknown(checker):
    result = match(checker, "Collect signed forms",
                   ["Collect signed forms", "Collect signed forms"])
    assert result["mapped"] is False
    assert result["reason"] == "ambiguous_action_mapping"
    assert result["match_tier"] == "exact_label_tie"
    assert set(result["undetermined_activity_ids"]) == {"x0", "x1"}


def test_negation_and_number_differences_are_kept(checker):
    negation = match(checker, "Send report", ["Do not send report"])
    assert negation["mapped"] is False
    assert "negation_difference" in reason_codes(negation)
    numerals = match(checker, "Review 3 invoices", ["Review 5 invoices"])
    assert numerals["mapped"] is False
    assert "numeral_difference" in reason_codes(numerals)


def test_insufficient_evidence_keeps_unknown_and_names_the_component(checker):
    result = match(checker, "Verify identity", ["Verify"])
    assert result["mapped"] is False
    assert result["reason"] == "ambiguous_action_mapping"
    assert result["match_tier"] == "structure_undetermined"
    assert "required_object_content_absent" in reason_codes(result)
    assert "identity" in result["tier_reason"]


def test_lexical_variation_does_not_produce_a_conflict(checker):
    """Real backend: a lexically different but supported candidate still matches."""
    result = match(checker, "Inspect package", ["Examine package"])
    assert result["mapped"] is True
    assert result["match_tier"] == "similarity_satisfied"
    candidate = result["best"]
    assert candidate["verdict"] == "undetermined"
    assert [reason["code"] for reason in candidate["reasons"]] == ["predicate_not_equivalent"]


def test_similar_differing_terms_are_not_reported_as_explicit(nlp):
    """Isolated logic test with a stub backend, not a model result."""
    checker = EvidenceChecksV3(StubSimilarity(("record", "file"), 0.85), 0.8, 0.8, 0.8, nlp=nlp)
    result = match(checker, "Archive records", ["Archive files"])
    assert result["mapped"] is False
    assert "object_terms_possibly_equivalent" in reason_codes(result)
    assert "object_content_difference" not in reason_codes(result)
    assert result["match_tier"] == "structure_undetermined"
    low = EvidenceChecksV3(StubSimilarity(("record", "file"), 0.10), 0.8, 0.8, 0.8, nlp=nlp)
    strict = match(low, "Archive records", ["Archive files"])
    assert strict["match_tier"] == "structure_not_satisfied"
    assert "object_content_difference" in reason_codes(strict)


# --- scope guarantees -------------------------------------------------------


def test_only_representation_and_matching_are_overridden():
    for name in ("missing_action", "incorrect_actor", "out_of_order", "_result",
                 "_executors", "_same_role", "_surface", "_lemma", "matching_score",
                 "_label_evidence", "_compare", "_normalize"):
        if name == "_compare":
            continue
        assert getattr(EvidenceChecksV3, name) is getattr(EvidenceChecksV2, name), name
    assert EvidenceChecksV3.action_match is not EvidenceChecksV2.action_match
    assert issubclass(EvidenceChecksV3, EvidenceChecksV2)
    allowed = {"action_match", "_structure", "_head_token", "_nearest_verb_owner",
               "_nearest_clause_head", "_owned_objects", "_role_fillers", "_object_spans",
               "_verb_agrees", "_term_support", "_compare", "_nested_component_of",
               "_strongest", "_reason_summary", "_ranked", "_summary", "_mapped",
               "_undetermined", "__init__", "method_id"}
    extra = {name for name in set(EvidenceChecksV3.__dict__) - allowed
             if not name.startswith("__")}
    assert not extra, f"unexpected overrides: {sorted(extra)}"


def test_method_identity_and_policy_are_declared():
    assert METHOD == "s3_action_matching@3.0.0"
    assert METHOD_ID == "evidence_checks_v3_action_structure"
    assert MODIFICATION_SCOPE == "action representation and candidate matching only"
    policy = match_policy()
    assert policy["representation"]["nested_actions"]
    assert policy["representation"]["roles"]
    serialized = json.dumps(policy, ensure_ascii=False).lower()
    assert "rectify" not in serialized and "access" not in serialized.split("no rectification")[0]
    assert any("synonym list" in item for item in policy["forbidden"])


def test_previous_checker_and_frozen_inputs_are_unchanged():
    manifest = json.loads((V2_OUT / "manifest.json").read_text(encoding="utf-8"))
    import hashlib
    for section in ("implementation", "inputs"):
        for rel, binding in manifest[section].items():
            digest = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
            assert digest == binding["sha256_raw_working_tree"], f"{section}:{rel}"


# --- frozen experiment and stored artefacts ---------------------------------


def _load_runner():
    spec = importlib.util.spec_from_file_location("action_matching_v3_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["action_matching_v3_runner"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


@pytest.fixture(scope="module")
def stored(runner):
    return runner.verify_manifest()


@pytest.fixture(scope="module")
def rebuilt(runner, stored):
    return runner.replay_payload()


def test_frozen_contracts_and_denominator_are_unchanged(runner, stored):
    contracts = stored["contracts"]
    assert contracts["counts"] == {"fixed_variants": 30, "valid_contracts": 28,
                                   "unresolved": 2, "pairs": 28, "control_instances": 28,
                                   "variant_instances": 28, "total_check_instances": 56}
    assert len(stored["predictions"]) == 56
    assert {row["checker"] for row in stored["predictions"]} == {runner.V3_METHOD}
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["declarations"]["denominator_unchanged"] is True
    assert manifest["contracts"]["unresolved"] == 2


def test_reused_columns_are_verified_references_not_reruns(runner, stored):
    sources = stored["metrics"]["sources"]
    for method in (runner.SUN_METHOD, runner.V2_METHOD):
        entry = sources[method]
        assert entry["mode"] == "reused_verified_predictions"
        assert entry["sha256"] == entry["manifest_recorded_sha256"]
        assert entry["item_count"] == 56
        assert "items" in entry
    assert sources[runner.V3_METHOD]["mode"] == "newly_generated"
    assert all(stored["metrics"]["shared_evaluator_adapter"]
               ["faithfulness_check_against_stored_metrics"].values())


def test_v3_rows_use_the_frozen_requirement_and_models(runner, stored):
    contracts = {c["contract_id"]: c for c in stored["contracts"]["contracts"]}
    for row in stored["predictions"]:
        contract = contracts[row["pair_id"]]
        assert contract["status"] == "valid"
        assert row["requirement_sha256"] == runner.V1.canonical_sha256(contract["requirement"])
        expected_bpmn = contract["source_bpmn"] if row["side"] == "original" else contract["variant_bpmn"]
        assert row["model_bpmn"] == expected_bpmn
        assert row["shared_binding"]["thresholds"] == {"tau": 0.8, "gamma": 0.8, "theta": 0.8}
        assert row["shared_binding"]["shared_backend_object_with_reused_columns"] is True


def test_predictions_carry_no_expected_answer_fields(stored):
    for row in stored["predictions"]:
        assert "expected_violation" not in row
        assert "mutation_type" not in row
        assert "target_activity_id" not in row


def test_predictions_ignore_labels_and_mutation_markers(runner, stored, rebuilt):
    poisoned = json.loads((runner.CONTRACTS_FILE).read_text(encoding="utf-8"))
    for contract in poisoned["contracts"]:
        contract["evaluation"] = {"target_check": "out_of_order",
                                  "expected_original": "violation",
                                  "expected_variant": "satisfied"}
        contract["binding_evidence"] = {"poisoned": "ignore me"}
        contract["target_activity_id"] = "POISONED"
        contract["target_activity_name"] = "POISONED"
        contract["variant_id"] = "POISONED"
    rows = runner.build_v3_predictions(runner.prepare_context(), poisoned)
    assert len(rows) == len(stored["predictions"])
    for rebuilt_row, poisoned_row in zip(rebuilt["predictions"], rows):
        assert rebuilt_row["pair_id"] == poisoned_row["pair_id"]
        assert rebuilt_row["signals"] == poisoned_row["signals"]


def test_metrics_recomputable_from_stored_predictions(runner, stored):
    block = stored["metrics"]["methods"][runner.V3_METHOD]
    for check in ("missing_action", "incorrect_actor", "out_of_order"):
        per_type = block["per_type"][check]
        rows = [row for row in stored["predictions"] if row["target_check"] == check]
        assert len(rows) == 2 * per_type["valid_pairs"]
        control = [row for row in rows if row["side"] == "original"]
        positive = [row for row in rows if row["side"] == "variant"]
        statuses = lambda rs: [row["signals"][check]["status"] for row in rs]  # noqa: E731
        assert per_type["tp"] == statuses(positive).count("violation")
        assert per_type["fp"] == statuses(control).count("violation")
        assert per_type["tn"] == statuses(control).count("satisfied")
        assert per_type["fn"] == per_type["valid_pairs"] - per_type["tp"]
        assert per_type["paired_success"] == sum(
            1 for states in per_type["per_pair"].values()
            if states["control"] == "satisfied" and states["variant"] == "violation")
    assert block["valid_contracts"] == stored["contracts"]["counts"]["valid_contracts"]


def test_replay_reproduces_v3_outputs(rebuilt, stored):
    assert rebuilt["predictions"] == rebuilt["stored_predictions"]
    assert rebuilt["metrics"] == rebuilt["stored_metrics"]
    assert rebuilt["diagnostics"] == rebuilt["stored_diagnostics"]


def test_counter_examples_match_the_fixed_expectations(runner, stored):
    cases = stored["diagnostics"]["counter_examples"]
    assert len(cases) == len(runner.COUNTER_EXAMPLES)
    for case in cases:
        assert case["as_expected"] is True, case
    by_name = {case["name"]: case for case in cases}
    assert by_name["nested_action_substitution"]["mapped"] is False
    assert by_name["relation_containment_undetermined"]["mapped"] is False
    assert by_name["unrelated_candidate_does_not_veto"]["mapped"] is True
    assert by_name["role_swap_detected"]["mapped"] is False
    assert by_name["lexical_variation_not_a_conflict"]["mapped"] is True


def test_focus_items_record_root_cause_and_result(runner, stored):
    focus = {item["item_id"]: item for item in stored["diagnostics"]["focus_items"]}
    assert set(focus) == set(runner.FOCUS_ITEMS)
    nested = focus["syn_missing_action_04::variant"]
    assert nested["v2_status"] == "unknown"
    assert "nested_action_substituted" in nested["v3_reason_codes"]
    assert nested["checked_activity_ids"]
    assert any(candidate["verdict"] == "not_satisfied"
               for candidate in nested["candidate_evidence"])
    containment = focus["syn_missing_action_06::variant"]
    assert containment["v2_status"] == "unknown"
    assert "nested_action_component_containment" in containment["v3_reason_codes"]
    assert "run" in containment["v3_tier_reason"][0] or "run" in json.dumps(
        containment["v3_reason_codes"])
    assert containment["candidate_evidence"]


def test_contract_interpretation_is_recorded_and_not_switched(stored):
    block = stored["diagnostics"]["contract_interpretation"]
    assert "definition A" in block["finding"]
    assert block["decision"].startswith("definition not switched")
    assert block["minimum_question_for_coordinator"].startswith("should syn_missing_action_06")
    assert block["evidence"]["panel_expected_violation"] == "missing_action"


def test_new_and_fixed_errors_are_consistent(stored):
    diagnostics = stored["diagnostics"]
    changes = {entry["item_id"]: entry for entry in diagnostics["v2_to_v3_item_changes"]}
    assert len(changes) == 56
    for entry in diagnostics["new_errors"]:
        assert entry["v2_status"] == entry["expected"]
        assert entry["v3_status"] != entry["expected"]
    for entry in diagnostics["fixed_errors"]:
        assert entry["v2_status"] != entry["expected"]
        assert entry["v3_status"] == entry["expected"]
    assert sum(diagnostics["change_summary"].values()) == 56


def test_artifacts_are_lf_and_evidence_is_structured(stored):
    for name in ("predictions.jsonl", "metrics.json", "diagnostics.json", "manifest.json"):
        raw = (OUT / name).read_bytes()
        assert b"\r\n" not in raw, name
        assert raw.endswith(b"\n"), name
    for row in stored["predictions"]:
        check = row["target_check"]
        records = [[detail["match"] for detail in row["raw"][check].get("details", [])
                    if isinstance(detail.get("match"), dict)]][0] if check != "out_of_order" else []
        if check == "out_of_order":
            records = [detail[key] for detail in row["raw"][check].get("details", [])
                       for key in ("before", "after") if isinstance(detail.get(key), dict)]
        assert records, row["item_id"]
        for record in records:
            assert record.get("match_tier"), row["item_id"]
            assert record.get("tier_reason"), row["item_id"]
            assert record.get("required"), row["item_id"]

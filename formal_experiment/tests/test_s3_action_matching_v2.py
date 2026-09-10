# -*- coding: utf-8 -*-
"""Independent behaviour checks for the v2 action-matching successor.

These tests use short, GDPR-unrelated actions.  They verify general matching
behaviour (exact-match priority, object/recipient distinction, negation and
number preservation, ambiguity, order independence, unknown retention) and the
scope guarantee that only action matching was replaced.  One test reproduces the
confirmed defect pair as documented evidence; it is not a performance dataset.

Passing counts are not an experimental result.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.s3_action_matching_v2 import (  # noqa: E402
    METHOD, METHOD_ID, MODIFICATION_SCOPE, EvidenceChecksV2,
)
from bpc_hybrid.s3_evidence_checks_v1 import EvidenceChecks  # noqa: E402

V2_OUT = ROOT / "outputs/development/s3_action_matching_v2"
V1_OUT = ROOT / "outputs/development/s3_paired_mechanism_v1"
RUNNER = ROOT / "scripts/run_s3_action_matching_v2.py"


class FixedSimilarity:
    """Deterministic backend: 1.0 for equal text, a configured value otherwise."""

    def __init__(self, value: float = 0.0):
        self.value = value

    def text_pair(self, left: str, right: str) -> float:
        return 1.0 if left.casefold() == right.casefold() else self.value


@pytest.fixture(scope="module")
def nlp():
    import spacy
    return spacy.load("en_core_web_sm")


@pytest.fixture(scope="module")
def checker(nlp):
    return EvidenceChecksV2(FixedSimilarity(0.0), 0.8, 0.8, 0.8, nlp=nlp)


def high_similarity_checker(nlp, value: float = 0.95) -> EvidenceChecksV2:
    return EvidenceChecksV2(FixedSimilarity(value), 0.8, 0.8, 0.8, nlp=nlp)


def model(actions=None, owners=None, reachable=None, lanes=None, objects=None):
    actions = actions or [{"id": "a", "name": "Collect signed forms"},
                          {"id": "b", "name": "Collect signed invoices"}]
    return SimpleNamespace(
        actions=actions,
        record={"lanes": lanes or []},
        action_actor_names=owners or {a["id"]: ["Clerk"] for a in actions},
        business_objects=objects or [],
        actors=["Clerk"],
        is_reachable=lambda source, target: (source, target) in (reachable or []),
    )


# --- exact-match priority ---------------------------------------------------


def test_unique_exact_match_wins_over_a_similar_distractor(checker):
    result = checker.action_match("Collect signed forms", model())
    assert result["mapped"] is True
    assert result["match_tier"] == "exact_label"
    assert result["best"]["activity_id"] == "a"
    distractor = next(c for c in result["candidates"] if c["activity_id"] == "b")
    assert distractor["match_tier"] == "object_conflict"


def test_deleted_target_is_not_replaced_by_a_different_object_action(checker):
    without_target = model(actions=[{"id": "b", "name": "Collect signed invoices"}])
    result = checker.action_match("Collect signed forms", without_target)
    assert result["mapped"] is False
    assert result["match_tier"] == "object_conflict"
    assert result["reason"] == "object_conflict_evidence"
    assert result["best"]["activity_id"] == "b"


def test_same_verb_different_recipient_is_not_substituted(checker):
    result = checker.action_match("Notify the customer",
                                  model(actions=[{"id": "a", "name": "Notify the authority"}]))
    assert result["mapped"] is False
    assert result["match_tier"] == "object_conflict"
    assert result["best"]["object_evidence"]["shared_objects"] == []


def test_verb_only_overlap_does_not_imply_equivalence_even_at_high_similarity(nlp):
    checker = high_similarity_checker(nlp, 0.95)
    result = checker.action_match("Archive records",
                                  model(actions=[{"id": "a", "name": "Archive files"}]))
    assert result["mapped"] is False, "high similarity must not override explicit object evidence"
    assert result["match_tier"] == "object_conflict"


# --- ambiguity --------------------------------------------------------------


def test_two_identical_labels_stay_ambiguous_and_no_id_is_picked(checker):
    actions = [{"id": "z9", "name": "Collect signed forms"},
               {"id": "a1", "name": "Collect signed forms"}]
    result = checker.action_match("Collect signed forms", model(actions=actions))
    assert result["mapped"] is False
    assert result["match_tier"] == "exact_label_tie"
    assert result["reason"] == "ambiguous_action_mapping"
    assert set(result["undetermined_activity_ids"]) == {"a1", "z9"}


def test_insufficient_evidence_keeps_unknown(checker):
    partial = model(actions=[{"id": "a", "name": "Check parcel weight and volume"}])
    result = checker.action_match("Check parcel weight", partial)
    assert result["match_tier"] == "partial_object_overlap"
    assert result["mapped"] is False
    assert result["reason"] == "ambiguous_action_mapping"
    missing = checker.missing_action(["Check parcel weight"], partial)
    assert missing["status"] == "unknown"
    assert missing["score"] is None


# --- normalisation boundaries ----------------------------------------------


def test_negation_difference_is_not_normalised_away(checker):
    result = checker.action_match("Send report",
                                  model(actions=[{"id": "a", "name": "Do not send report"}]))
    required = checker._label_evidence("Send report")
    candidate = checker._label_evidence("Do not send report")
    assert required["negated"] is False and candidate["negated"] is True
    assert candidate["predicate"] == required["predicate"] == "send"
    assert candidate["objects"] == required["objects"] == frozenset({"report"})
    assert result["mapped"] is False and result["match_tier"] == "object_conflict"


def test_number_difference_is_not_normalised_away(checker):
    result = checker.action_match("Review 3 invoices",
                                  model(actions=[{"id": "a", "name": "Review 5 invoices"}]))
    assert checker._label_evidence("Review 3 invoices")["numerals"] == frozenset({"3"})
    assert checker._label_evidence("Review 5 invoices")["numerals"] == frozenset({"5"})
    assert result["mapped"] is False and result["match_tier"] == "object_conflict"


def test_exact_normalisation_is_fixed_and_keeps_distinguishing_words(checker):
    assert checker._normalize("  Collect   Signed Forms \n") == "collect signed forms"
    assert checker._normalize("Collect signed forms") != checker._normalize("Collect signed invoices")


# --- order independence -----------------------------------------------------


def test_candidate_order_does_not_change_a_unique_evidence_verdict(checker):
    forward = model(actions=[{"id": "a", "name": "Collect signed forms"},
                             {"id": "b", "name": "Collect signed invoices"}])
    backward = model(actions=[{"id": "b", "name": "Collect signed invoices"},
                              {"id": "a", "name": "Collect signed forms"}])
    first = checker.action_match("Collect signed forms", forward)
    second = checker.action_match("Collect signed forms", backward)
    assert (first["mapped"], first["match_tier"], first["best"]["activity_id"]) == \
           (second["mapped"], second["match_tier"], second["best"]["activity_id"])


def test_candidate_order_does_not_change_an_ambiguous_verdict(checker):
    forward = model(actions=[{"id": "a1", "name": "Collect signed forms"},
                             {"id": "z9", "name": "Collect signed forms"}])
    backward = model(actions=[{"id": "z9", "name": "Collect signed forms"},
                              {"id": "a1", "name": "Collect signed forms"}])
    assert (checker.action_match("Collect signed forms", forward)["undetermined_activity_ids"]
            == checker.action_match("Collect signed forms", backward)["undetermined_activity_ids"])


# --- confirmed defect reproduction and evidence recording --------------------


def test_action_word_cannot_masquerade_as_a_shared_object(checker):
    """Confirmed v1 defect: the head verb is tagged NOUN and faked object agreement."""
    evidence = checker._label_evidence("Retrieve breached subjects")
    assert evidence["objects"] == frozenset({"subject"}), "the action word must not be object evidence"
    result = checker.action_match(
        "Retrieve breached subjects",
        model(actions=[{"id": "a", "name": "Retrieve breached subjects"},
                       {"id": "b", "name": "Retrieve breached data"}]))
    assert result["mapped"] is True and result["best"]["activity_id"] == "a"
    distractor = next(c for c in result["candidates"] if c["activity_id"] == "b")
    assert distractor["object_evidence"]["shared_objects"] == []
    assert distractor["match_tier"] == "object_conflict"


def test_every_candidate_records_tier_similarity_evidence_and_decision(checker):
    result = checker.action_match("Collect signed forms", model())
    assert result["required"]["text"] == "Collect signed forms"
    for candidate in result["candidates"]:
        assert candidate["match_tier"]
        assert isinstance(candidate["raw_similarity"], float)
        assert "shared_objects" in candidate["object_evidence"]
        assert candidate["decision"]
        assert "score" not in candidate, "no fabricated decision score on candidates"
    assert "score" not in result


# --- scope guarantees -------------------------------------------------------


def test_only_action_matching_is_overridden():
    for name in ("missing_action", "incorrect_actor", "out_of_order", "_result",
                 "_executors", "_same_role", "_surface", "_lemma", "matching_score"):
        assert getattr(EvidenceChecksV2, name) is getattr(EvidenceChecks, name), name
    assert EvidenceChecksV2.action_match is not EvidenceChecks.action_match
    assert issubclass(EvidenceChecksV2, EvidenceChecks)
    allowed_own_names = {
        "action_match", "_best_action_match", "_label_evidence", "_candidate",
        "_decide_candidate", "_required_summary", "_ranked", "_mapped", "_undetermined",
        "_normalize", "__init__", "method_id", "__doc__", "__module__", "__dict__",
        "__weakref__", "__qualname__",
    }
    extra = {name for name in set(EvidenceChecksV2.__dict__) - allowed_own_names
             if not name.startswith("__")}
    assert not extra, f"unexpected overrides: {sorted(extra)}"


def test_method_identity_is_distinct_from_v1_and_scope_is_declared():
    assert METHOD == "s3_action_matching@2.0.0"
    assert METHOD_ID != "s3_evidence_checks@1.0.0"
    assert MODIFICATION_SCOPE == "action matching only"


def test_v1_checker_and_frozen_inputs_are_unchanged():
    v1_manifest = json.loads((ROOT / "outputs/reports/s3_evidence_repair_v1.manifest.json")
                             .read_text(encoding="utf-8"))
    for section in ("implementation", "artifacts"):
        for rel, expected in v1_manifest[section].items():
            assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == expected, rel
    paired_manifest = json.loads((V1_OUT / "manifest.json").read_text(encoding="utf-8"))
    for rel, binding in paired_manifest["inputs"].items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == \
            binding["sha256_raw_working_tree"], rel


# --- reuse and frozen-contract guarantees for the v2 run --------------------


def _load_runner():
    spec = importlib.util.spec_from_file_location("action_matching_v2_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["action_matching_v2_runner"] = module
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


def test_contracts_and_reused_predictions_are_bound_not_rerun(stored):
    contracts = stored["contracts"]
    assert contracts["counts"]["fixed_variants"] == 30
    assert contracts["counts"]["valid_contracts"] == 28
    assert contracts["counts"]["unresolved"] == 2
    assert contracts["counts"]["total_check_instances"] == 56
    assert len(stored["predictions"]) == 56
    assert {row["checker"] for row in stored["predictions"]} == {"evidence_checks_v2_action_matching"}
    reuse = stored["metrics"]["sources"]
    assert reuse["sun_2024_frozen"]["mode"] == "reused_verified_predictions"
    assert reuse["evidence_checks_v1"]["mode"] == "reused_verified_predictions"
    assert reuse["evidence_checks_v2_action_matching"]["mode"] == "newly_generated"


def test_reused_predictions_match_their_source_rows(stored):
    source_file = V1_OUT / "predictions.jsonl"
    source = [json.loads(line) for line in source_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    source_index = {(row["pair_id"], row["side"], row["checker"]): row for row in source}
    for method in ("sun_2024_frozen", "evidence_checks_v1"):
        source_entry = stored["metrics"]["sources"][method]
        # the reuse is a reference (path + hash), never a copy of the evidence
        assert source_entry["sha256"] == hashlib.sha256(source_file.read_bytes()).hexdigest()
        assert source_entry["path"].endswith("s3_paired_mechanism_v1/predictions.jsonl")
        items = source_entry["items"]
        assert len(items) == 56
        for reference in items:
            row = source_index[(reference["pair_id"], reference["side"], reference["checker"])]
            assert reference["item_id"] == row["item_id"]
            assert reference["status"] == row["signals"][row["target_check"]]["status"]
            assert reference["signals"] == {check: row["signals"][check]["status"]
                                            for check in ("missing_action", "incorrect_actor",
                                                          "out_of_order")}
            assert "raw" not in reference, "reused evidence must stay in the referenced file"


def test_v2_variant_uses_the_frozen_requirements_and_models(stored):
    contracts = {c["contract_id"]: c for c in stored["contracts"]["contracts"]}
    for row in stored["predictions"]:
        contract = contracts[row["pair_id"]]
        assert contract["status"] == "valid"
        assert row["requirement_sha256"] == runner_canonical_sha(contract["requirement"])
        expected_bpmn = contract["source_bpmn"] if row["side"] == "original" else contract["variant_bpmn"]
        assert row["model_bpmn"] == expected_bpmn
        assert row["model_bpmn_sha256"] == hashlib.sha256((ROOT / expected_bpmn).read_bytes()).hexdigest()
        assert row["shared_binding"]["thresholds"] == {"tau": 0.8, "gamma": 0.8, "theta": 0.8}
        assert row["shared_binding"]["shared_backend_object_with_v1"] is True
        assert row["shared_binding"]["shared_nlp_object_with_v1"] is True
        assert row["method_scope"] == "action matching only"


def runner_canonical_sha(value: object) -> str:
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location("_v1_runner_for_sha",
                                        ROOT / "scripts/run_s3_paired_mechanism_v1.py")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.canonical_sha256(value)


def test_predictions_do_not_read_labels_or_mutation_markers(runner, stored, rebuilt):
    poisoned = json.loads((V1_OUT / "contracts_locked.json").read_text(encoding="utf-8"))
    for contract in poisoned["contracts"]:
        contract["evaluation"] = {"target_check": "out_of_order",
                                  "expected_original": "violation",
                                  "expected_variant": "satisfied"}
        contract["binding_evidence"] = {"poisoned": "ignore me"}
        contract["target_activity_id"] = "POISONED"
        contract["target_activity_name"] = "POISONED"
        contract["variant_id"] = "POISONED"
    rows = runner.build_v2_predictions(runner.prepare_context(), poisoned)
    assert len(rows) == len(stored["predictions"])
    for rebuilt_row, poisoned_row in zip(rebuilt["predictions"], rows):
        assert rebuilt_row["pair_id"] == poisoned_row["pair_id"]
        assert rebuilt_row["signals"] == poisoned_row["signals"]


def test_metrics_are_recomputable_from_the_stored_v2_predictions(stored):
    block = stored["metrics"]["methods"]["evidence_checks_v2_action_matching"]
    for check in ("missing_action", "incorrect_actor", "out_of_order"):
        per_type = block["per_type"][check]
        rows = [r for r in stored["predictions"] if r["target_check"] == check]
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
            1 for pair_id, states in per_type["per_pair"].items()
            if states["control"] == "satisfied" and states["variant"] == "violation")
    assert block["valid_contracts"] == stored["contracts"]["counts"]["valid_contracts"]


def test_replay_reproduces_v2_predictions(rebuilt, stored):
    assert rebuilt["predictions"] == rebuilt["stored_predictions"]
    assert rebuilt["metrics"] == rebuilt["stored_metrics"]
    assert rebuilt["diagnostics"] == rebuilt["stored_diagnostics"]


def test_unknown_transitions_and_changes_are_derived_from_the_items(stored):
    diagnostics = stored["diagnostics"]
    transitions = diagnostics["unknown_transitions"]
    assert transitions["v1_unknown_total"] == 19
    assert (transitions["v1_unknown_now_correct"] + transitions["v1_unknown_now_wrong"]
            + transitions["v1_unknown_still_unknown"]) == 19
    changes = diagnostics["v1_v2_item_changes"]
    assert len(changes) == 56
    counted = sum(diagnostics["change_summary"].values())
    assert counted == 56
    unknown_items = [c for c in changes if c["v1_status"] == "unknown"]
    assert len(unknown_items) == 19
    for change in changes:
        expected = "satisfied" if change["side"] == "original" else "violation"
        assert change["expected"] == expected
        if change["change"] == "corrected":
            assert change["v2_status"] == expected and change["v1_status"] != expected
        if change["change"] == "regressed":
            assert change["v1_status"] == expected and change["v2_status"] != expected


def test_new_artifacts_are_lf_and_replace_the_matching_tier_evidence(stored, runner):
    for name in ("predictions.jsonl", "metrics.json", "diagnostics.json", "manifest.json"):
        raw = (V2_OUT / name).read_bytes()
        assert b"\r\n" not in raw, name
        assert raw.endswith(b"\n"), name
    for row in stored["predictions"]:
        check = row["target_check"]
        records = runner.match_records(row["raw"][check], check)
        assert records, row["item_id"]
        for record in records:
            assert record.get("match_tier"), row["item_id"]
            assert record.get("tier_reason"), row["item_id"]
            assert record.get("required"), row["item_id"]
            if record.get("mapped"):
                assert isinstance(record["best"]["raw_similarity"], float), row["item_id"]
            for candidate in record.get("candidates", []):
                assert candidate.get("match_tier"), row["item_id"]
                assert isinstance(candidate["raw_similarity"], float), row["item_id"]
                assert "object_evidence" in candidate, row["item_id"]
                assert candidate.get("decision"), row["item_id"]
                assert "score" not in candidate, "no fabricated decision score"


def test_manifest_declares_scope_and_byte_convention(stored):
    manifest = json.loads((V2_OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["declarations"]["modification_scope"] == "action matching only"
    assert manifest["declarations"]["development_only"] is True
    assert manifest["declarations"]["new_llm_api_calls"] == 0
    assert manifest["declarations"]["frozen_panel_reused_not_reselected"] is True
    assert manifest["hash_conventions"]["artifacts"].startswith("UTF-8, LF")
    assert manifest["contracts"]["valid_contracts"] == 28
    assert manifest["contracts"]["unresolved"] == 2
    assert manifest["source_predictions"]["mode"] == "reused_verified_predictions"
    assert all(value is False for key, value in manifest["safety"].items()
               if key.endswith("modified"))

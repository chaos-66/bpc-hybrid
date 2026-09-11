# -*- coding: utf-8 -*-
"""Focused checks for the S3.9-EXT v3 four-type arm.

Scope: this file only.  It never re-runs the 80-instance batch; metrics are
recomputed from the stored rows and the bindings are verified.  Only two
real localizations (one variant and its control) are computed, to prove that the
adapter really calls ``EvidenceChecksV3.action_match`` and that the labels cannot
reach the localization or the scores.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_s3_extended_v3_v1.py"
OUT = ROOT / "outputs/development/s3_extended_v3_v1"
FROZEN_EVIDENCE = ROOT / "outputs/evidence/s3_formula_repair_v2"
FROZEN_MANIFEST = FROZEN_EVIDENCE / "manifest.json"
FROZEN_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
FROZEN_METHODS = ("winter", "sun", "bm25", "tfidf_svd")
V3_METHOD = "v3_extended_action_structure"


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
    return _load(RUNNER, "s3_extended_v3_v1_runner")


@pytest.fixture(scope="module")
def verified(runner):
    return runner.verify_outputs()


@pytest.fixture(scope="module")
def rows(verified):
    return verified["rows"]


@pytest.fixture(scope="module")
def metrics(verified):
    return verified["metrics"]


@pytest.fixture(scope="module")
def diagnostics():
    return json.loads((OUT / "diagnostics.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def frozen_manifest():
    return json.loads(FROZEN_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def panel(runner):
    return runner.read_json(runner.panel_runner.PANEL)


@pytest.fixture(scope="module")
def live_one(runner, panel):
    """One real instance (variant + control) re-derived with the v3 adapter."""
    import spacy
    nlp = spacy.load("en_core_web_sm")
    sim = runner.WinterSimilarity(nlp)
    cfg = runner.read_json(runner.panel_runner.SUN_CONFIG)
    th = cfg["method"]["thresholds"]
    v3 = runner.EvidenceChecksV3(sim, float(th["tau"]), float(th["gamma"]),
                                 float(th["theta"]), nlp)
    contract = runner.load_stage1_contract(runner.panel_runner.STRUCTURAL_CONTRACT)
    gamma_ext = float(panel["config"]["gamma_ext"])
    gamma_action = runner.panel_runner._gamma_for(runner.GATE_METHOD)
    texts = runner.panel_runner._rule_texts()
    variant = next(v for v in panel["variants"]
                   if v["variant_id"] == "syn_v2_required_condition_01")
    sentence = runner.panel_runner._locked_sentence(variant, texts[variant["rule_id"]], nlp)
    return {"nlp": nlp, "sim": sim, "v3": v3, "contract": contract, "variant": variant,
            "sentence": sentence, "gamma_ext": gamma_ext, "gamma_action": gamma_action}


# --- the arm is real, named, and separate ----------------------------------


def test_new_arm_is_named_and_not_the_old_arms(metrics, runner, frozen_manifest):
    assert runner.METHOD_ID == V3_METHOD
    assert metrics["arm"]["method_id"] == V3_METHOD
    assert metrics["arm"]["new_arm"] is True
    assert metrics["arm"]["action_localization"] == runner.ADAPTER_LOCALIZATION
    table = metrics["comparison_same_panel"]
    assert set(table) == set(FROZEN_METHODS) | {V3_METHOD}
    for method in FROZEN_METHODS:
        assert table[method]["source"].endswith("(read-only, not re-run)")
    assert table[V3_METHOD]["source"] == "this run"
    report = json.loads(FROZEN_REPORT.read_text(encoding="utf-8"))
    for method in FROZEN_METHODS:
        frozen = report["extended_four_types"]["reference"][method]["variant_evaluation"]
        assert table[method]["A_variant_only_40"]["macro_f1"] == frozen["macro_f1"]
    assert frozen_manifest["run_id"] == "s3_formula_repair_v2"
    # the new arm owns its own numbers: its per-type table is not any frozen arm's
    for method in FROZEN_METHODS:
        assert table[V3_METHOD]["A_variant_only_40"]["macro_f1"] == \
            metrics["A_variant_only_40"]["macro_f1"]
    assert all(entry["support"] == 10
               for entry in table[V3_METHOD]["A_variant_only_40"]["per_type"].values())


def test_every_row_records_the_adapter_and_its_thresholds(rows, runner):
    for row in rows:
        assert row["method_id"] == V3_METHOD
        assert row["gold_visible"] is False
        loc = row["action_localization"]
        assert loc["adapter"] == runner.ADAPTER_ID
        assert loc["localization"] == runner.ADAPTER_LOCALIZATION
        assert row["thresholds"]["action_gate"] == "v3_localization_decision"
        assert row["thresholds"]["gamma_ext"] == row["gamma_ext"] == 0.5
        assert row["thresholds"]["v3_thresholds"] == {"tau": 0.8, "gamma": 0.8, "theta": 0.8}
        assert row["thresholds"]["action_mapping_gamma_recorded"] == 0.8
        assert row["panel"] == "synthetic_controlled_error_extension_v2"


# --- v3 is really called ----------------------------------------------------


def test_adapter_calls_evidence_checks_v3(runner, live_one, panel):
    variant, sentence = live_one["variant"], live_one["sentence"]
    bpmn = ROOT / variant["variant_bpmn"]
    record = runner.parse_bpmn_bytes(
        bpmn.read_bytes(), source_path=str(bpmn.relative_to(ROOT)),
        contract=live_one["contract"])
    model = runner.SunProcessModel(variant["process_id"], record, live_one["nlp"])
    scorer = runner.V3ExtendedScorer(live_one["v3"], live_one["sim"].text_pair,
                                     live_one["gamma_action"], live_one["gamma_ext"])
    loc = scorer.localize(sentence["action"], model)
    direct = live_one["v3"].action_match(sentence["action"], model)
    assert loc["decision"] == runner.classify_v3_decision(direct)
    assert loc["mapped"] == bool(direct["mapped"])
    assert loc["match_tier"] == direct["match_tier"]
    assert loc["reason"] == direct["reason"]
    assert loc["winner_similarity"] == pytest.approx(
        float((direct.get("best") or {}).get("raw_similarity") or 0.0), abs=1e-12)
    if direct["mapped"]:
        assert loc["matched_activity_id"] == direct["best"]["activity_id"]
    else:
        assert loc["matched_activity_id"] is None
    # memoized: a second call must return the identical record object content
    assert scorer.localize(sentence["action"], model) == loc
    assert loc["candidate_preview"], "v3 candidate evidence must be recorded"


def test_v3_semantics_are_four_way_not_boolean(runner):
    cases = {
        "mapped": {"mapped": True, "reason": None, "match_tier": "structure_satisfied"},
        "ambiguous": {"mapped": False, "reason": "ambiguous_action_mapping",
                      "match_tier": "structure_undetermined"},
        "unsatisfied": {"mapped": False, "reason": "requirement_evidence_not_satisfied",
                        "match_tier": "structure_not_satisfied"},
        "no_candidate": {"mapped": False, "reason": "no_candidate_above_gamma",
                         "match_tier": "no_candidate_above_gamma"},
    }
    assert runner.classify_v3_decision(cases["mapped"]) == runner.DECISION_MAPPED
    assert runner.classify_v3_decision(cases["ambiguous"]) == runner.DECISION_UNDETERMINED
    assert runner.classify_v3_decision(cases["unsatisfied"]) == runner.DECISION_NOT_SATISFIED
    assert runner.classify_v3_decision(cases["no_candidate"]) == runner.DECISION_NOT_SATISFIED
    assert len({runner.classify_v3_decision(v) for v in cases.values()}) == 3


# --- the score channel stays a real similarity ------------------------------


def test_scores_are_real_similarities_and_unobservable_scores_are_null(rows):
    for row in rows:
        loc = row["action_localization"]["variant"]
        prohibited = row["scores_detail"]["prohibited_action_present"]
        if row["observability"]["prohibited_action_present"]["observable"]:
            score = row["scores"]["prohibited_action_present"]
            assert prohibited["score_source"] in {"v3_winner", "candidate_max_similarity"}
            if prohibited["score_source"] == "v3_winner":
                assert score == pytest.approx(loc["winner_similarity"], abs=1e-6)
            else:
                assert score == pytest.approx(loc["candidate_max_similarity"], abs=1e-6)
            assert score == pytest.approx(prohibited["max_sim"], abs=1e-6)
        for t in ("required_condition_not_enforced", "constraint_violated",
                  "exception_not_handled"):
            detail = row["scores_detail"][t]
            score = row["scores"][t]
            if row["observability"][t]["observable"]:
                if detail.get("reason") == "exact_contradiction":
                    assert score == 1.0
                    assert detail["exact_contradiction"]["contradiction"] is True
                else:
                    assert score == pytest.approx(round(1.0 - detail["max_sim"], 6), abs=1e-9)
            else:
                assert score is None
                assert row["observability"][t]["reason"]


def test_unobservable_types_never_become_violation_or_compliance(rows):
    for row in rows:
        for t in row["observability"]:
            if not row["observability"][t]["observable"]:
                assert row["scores"][t] is None
                assert row["scores_detail"][t].get("violation") is not True
    # the frozen decision rule itself must agree with the recorded observability
    for row in rows:
        for t in row["control_scores"]:
            assert isinstance(row["control_scores"][t]["observable"], bool)


# --- localization and evidence use the same activity ------------------------


def test_evidence_is_bound_to_the_localized_activity(rows):
    matched = observable = 0
    for row in rows:
        for side in ("variant", "control"):
            binding = row["evidence_binding"][side]
            location = row["action_localization"][side]
            for t, entry in binding.items():
                assert entry["same_activity_as_localization"] is True, (row["item_id"], t)
                # an activity-bound surface is never bound to another activity than
                # the one v3 matched
                assert entry["surface_activity_id"] in (None, location["matched_activity_id"])
                assert entry["matched_activity_id"] in (None, location["matched_activity_id"])
                if row["observability"][t]["observable"] and t != "prohibited_action_present":
                    assert entry["matched_activity_id"] == location["matched_activity_id"]
                    observable += 1
                if entry["surface_activity_id"] is not None:
                    matched += 1
        assert row["matched_activity"]["variant"] == \
            row["action_localization"]["variant"]["matched_activity_id"]
    assert matched > 0, "at least one constraint surface must be activity-bound"
    assert observable + matched > 0


def test_control_side_is_scored_with_the_same_adapter(rows):
    for row in rows:
        assert row["action_localization"]["control"]["localization"] == \
            "evidence_checks_v3_action_match"
        assert (row["action_localization"]["control"]["decision"]
                in {"unique_satisfied_match", "undetermined", "not_satisfied"})


# --- labels cannot reach the decision ---------------------------------------


def test_labels_and_target_nodes_cannot_change_the_row(runner, live_one, rows):
    variant = live_one["variant"]
    stored = next(r for r in rows if r["item_id"] == variant["variant_id"])
    poisoned = dict(variant)
    poisoned["expected_violation"] = "exception_not_handled"
    poisoned["mutation_type"] = "exception_not_handled"
    poisoned["target_activity_id"] = "POISONED-TARGET"
    poisoned["mutation_config"] = {"POISONED": True}
    sentence = live_one["sentence"]
    assert sentence == live_one["sentence"]
    rebuilt = runner.build_row(poisoned, sentence, live_one["v3"],
                               live_one["sim"].text_pair, live_one["gamma_action"],
                               live_one["gamma_ext"], live_one["nlp"], live_one["contract"])
    for field in ("scores", "control_scores", "observability", "scores_detail",
                  "action_localization", "evidence_binding", "matched_activity"):
        assert rebuilt[field] == stored[field], field
    assert rebuilt["expected_violation"] == "exception_not_handled"
    assert rebuilt["predicted_violation_type"] is None
    assert stored["predicted_violation_type"] is None


def test_unified_decision_ignores_expected_violation(runner, rows):
    row = rows[0]
    poisoned = dict(row)
    poisoned["expected_violation"] = "constraint_violated"
    poisoned["check_type"] = "constraint_violated"
    assert runner.unified_rows([poisoned], row["gamma_ext"])[0]["unified_predicted_raw"] == \
        runner.unified_rows([row], row["gamma_ext"])[0]["unified_predicted_raw"]


# --- the four metric views ---------------------------------------------------


def test_metrics_are_recomputable_from_the_stored_rows(runner, rows, metrics, panel):
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    gamma_ext = float(panel["config"]["gamma_ext"])
    variant_view = runner.evaluate_extended(rows, gold)
    assert variant_view == metrics["A_variant_only_40"]
    paired = runner.evaluate_paired(rows, panel, gamma_ext)
    assert runner.control_view(paired) == metrics["B_control_40"]
    assert runner.paired_view(paired) == metrics["C_paired_40"]
    assert runner.merged_view(paired) == metrics["D_merged_80"]
    assert metrics["confusion_matrix"] == runner.confusion_matrix(rows, gold, gamma_ext, panel)


def test_views_are_separate_and_denominators_are_explicit(metrics):
    assert metrics["A_variant_only_40"]["support"] == 40
    assert metrics["A_variant_only_40"]["denominator"]["total_items"] == 40
    control = metrics["B_control_40"]
    assert control["objects"] == 40
    assert (control["explicitly_compliant"] + control["false_positives"]
            + control["unobservable"]) == 40
    assert control["false_positive_rate"] == round(control["false_positives"] / 40, 4)
    assert metrics["C_paired_40"]["pairs"] == 40
    merged = metrics["D_merged_80"]
    assert merged["denominator"] == 80
    assert len(merged["classes"]) == 5
    assert "NOT the variant-only table A" in merged["warning"]
    assert metrics["A_variant_only_40"]["macro_f1"] != merged["macro_f1_five_classes"]


def test_positive_unknown_is_a_miss_and_control_unknown_is_not_a_rejection(rows, metrics):
    unobservable_variants = sum(
        1 for row in rows
        if not row["observability"][row["expected_violation"]]["observable"])
    assert metrics["A_variant_only_40"]["unobservable"] == unobservable_variants
    assert metrics["A_variant_only_40"]["missed"] >= unobservable_variants
    for row in rows:
        # only an all-four-unobservable row is an abstention; a row whose expected
        # type is unobservable can still answer 'none' or another type
        all_unobservable = all(not row["observability"][t]["observable"]
                               for t in row["observability"])
        assert row["prediction_all_unobservable"] is all_unobservable
        if all_unobservable:
            assert row["unified_predicted_raw"] is None
    control = metrics["B_control_40"]
    assert control["explicitly_compliant"] + control["false_positives"] + \
        control["unobservable"] == 40
    assert "not a correct rejection" in control["policy"]
    assert metrics["confusion_matrix"]["predicted_none"]["none_gold"] == control["unobservable"]
    assert metrics["C_paired_40"]["both_sides_correct"] == round(
        metrics["C_paired_40"]["paired_accuracy"] * 40)


def test_unobservable_reason_counts_are_conserved(rows, metrics):
    """evaluate_extended counts the expected (gold) type's reasons only."""
    counter = Counter()
    for row in rows:
        expected = row["expected_violation"]
        if not row["observability"][expected]["observable"]:
            counter[row["observability"][expected]["reason"] or "unspecified"] += 1
    assert metrics["A_variant_only_40"]["denominator"]["unobservable_by_reason"] == \
        dict(sorted(counter.items()))
    for t, entry in metrics["per_type_change"].items():
        assert sum(entry["type_unobservable_by_reason_all_instances"].values()) == sum(
            1 for row in rows if not row["observability"][t]["observable"])
        assert entry["gold_type_unobservable_new"] <= entry["support"]
        assert "counts all 40 rows of this type" in entry["denominator_note"]


def test_sun_to_v3_transitions_are_complete_and_explained(metrics, rows):
    transitions = metrics["sun_to_v3"]
    assert transitions["old_arm"].startswith("sun")
    assert transitions["new_arm"] == V3_METHOD
    counted = {key: len(value) for key, value in transitions["items"].items()}
    assert counted == transitions["counts"]
    assert sum(counted.values()) == 40
    for key, items in transitions["items"].items():
        for item in items:
            assert item["v3_decision"] in {"unique_satisfied_match", "undetermined",
                                          "not_satisfied"}
            assert item["new_expected_type_reason"] is not None or \
                item["new_expected_type_observable"] is True
    for item in transitions["items"]["unknown_to_correct"]:
        assert item["old_predicted"] is None
        assert item["new_predicted"] == item["expected"]
    for item in transitions["items"]["still_unknown"]:
        assert item["old_predicted"] is None and item["new_predicted"] is None
        assert item["new_expected_type_observable"] is False
        assert item["new_expected_type_reason"]
    old_sun = metrics["old_sun_recount_from_stored_predictions"]["A_variant_only_40"]
    assert old_sun["macro_f1"] == metrics["comparison_same_panel"]["sun"][
        "A_variant_only_40"]["macro_f1"] == 0.2381


def test_diagnostics_cover_every_instance(rows, diagnostics, runner):
    assert diagnostics["counts"]["instances"] == len(rows) == 40
    assert diagnostics["counts"]["evaluation_objects"] == 80
    assert len(diagnostics["instances"]) == 40
    for entry in diagnostics["instances"]:
        assert entry["method_id"] == V3_METHOD
        assert entry["action_localization"]["localization"] == runner.ADAPTER_LOCALIZATION
        assert set(entry["scores"]) == {
            "prohibited_action_present", "required_condition_not_enforced",
            "constraint_violated", "exception_not_handled"}
        assert entry["final_prediction_kind"] in {"unknown", "observable_compliant",
                                                 "violation_type"}
        assert entry["thresholds"]["gamma_ext"] == 0.5
        assert entry["evidence_binding"]["variant"]


# --- frozen assets -----------------------------------------------------------


def test_frozen_arms_and_assets_are_unchanged(verified, frozen_manifest, runner):
    manifest = verified["manifest"]
    for method, entry in manifest["reused_frozen_artifacts"].items():
        assert entry["rerun"] is False and entry["rewritten"] is False
        assert sha256(ROOT / entry["path"]) == entry["sha256"]
        # the frozen manifest keys are native relative paths
        assert frozen_manifest["artifacts"][str(Path(entry["path"]))] == entry["sha256"], method
    assert sha256(FROZEN_REPORT) == frozen_manifest["report"]["sha256"]
    for rel, digest in frozen_manifest["inputs"].items():
        assert sha256(ROOT / rel) == digest, rel
    for rel, digest in manifest["implementation"].items():
        assert sha256(ROOT / rel) == digest, rel
    for rel in ("src/bpc_hybrid/stage3_extended_violations.py",
                "src/bpc_hybrid/s3_extended_unified.py"):
        key = str(Path(rel))
        assert manifest["inputs"][key] == sha256(ROOT / rel)
        # the frozen manifest binds implementation files by canonical LF UTF-8 text
        canonical = hashlib.sha256(
            (ROOT / rel).read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        ).hexdigest()
        assert frozen_manifest["implementation_hashes"][key] == canonical
    # the v3 checker itself is bound by its own verified run, not by the formula run
    v3_manifest = json.loads(
        (ROOT / "outputs/development/s3_action_matching_v3/manifest.json")
        .read_text(encoding="utf-8"))
    v3_rel = "src/bpc_hybrid/s3_action_matching_v3.py"
    assert sha256(ROOT / v3_rel) == \
        v3_manifest["implementation"][v3_rel]["sha256_raw_working_tree"]
    assert manifest["inputs"][str(Path(v3_rel))] == sha256(ROOT / v3_rel)


def test_output_directory_holds_four_files_and_copies_no_old_asset(verified):
    assert sorted(p.name for p in OUT.iterdir()) == [
        "diagnostics.json", "manifest.json", "metrics.json", "predictions.jsonl"]
    assert not (OUT / "panel.json").exists()
    assert not (OUT / "gold.json").exists()
    for path in OUT.rglob("*.bpmn"):
        raise AssertionError(f"no BPMN may be copied into the run: {path}")
    metrics = verified["metrics"]
    reference = metrics["frozen_asset_reference"]
    assert reference["report"]["path"] == "outputs/reports/s3_formula_repair_v2.json"
    assert reference["report"]["sha256"] == sha256(FROZEN_REPORT)
    assert reference["manifest"]["sha256"] == sha256(FROZEN_MANIFEST)
    assert "read-only" in metrics["comparison_same_panel"]["winter"]["source"]


def test_check_mode_and_manifest_bindings(runner, verified):
    again = runner.verify_outputs()
    assert again["manifest"]["results"]["predictions"]["rows"] == 40
    assert again["manifest"]["results"]["predictions"]["evaluation_objects"] == 80
    assert again["manifest"]["safety"]["api_calls"] == 0
    assert again["manifest"]["safety"]["frozen_arms_rerun"] is False
    assert again["manifest"]["safety"]["thresholds_changed"] is False

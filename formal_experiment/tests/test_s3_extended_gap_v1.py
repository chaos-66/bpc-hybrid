# -*- coding: utf-8 -*-
"""Focused checks for the S3.9-EXT v3 gap analysis and the D1/D2/D3 repair.

Scope: this file only.  Nothing here re-runs the 80-instance panel; the stored
arms are read from disk and the metric identities are recomputed.  The repair
logic is exercised with small synthetic doubles so the checks stay fast and
independent of the panel, and three small general-rule cases use the real
spaCy backend on short phrases only.

Covered behaviours:

* input isolation - no label field changes a decision;
* similarity scale - the prohibited score and its threshold live on one scale;
* localization / decision consistency - one action resolution feeds every check;
* activity-bound evidence - an observable evidence score is bound to it;
* ambiguity - under-determined stays distinct from not-satisfied and from
  unobservable;
* metric conservation - every partition adds up to its denominator;
* general rules - same verb / different object, same object / different
  recipient, and a duration inside an applicability condition.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid.s3_extended_arm_report import (  # noqa: E402
    arm_metrics, control_partition, variant_partition,
)
from bpc_hybrid.s3_extended_v3_adapter import (  # noqa: E402
    DECISION_MAPPED, DECISION_NOT_SATISFIED, DECISION_UNDETERMINED,
)
from bpc_hybrid.s3_extended_v3_repair import (  # noqa: E402
    REPAIR_ID, RESOLVED_BY_ACTION_GAMMA, RESOLVED_BY_V3_MATCH, RESOLVED_NONE,
    RepairedExtendedScorer,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, ConstraintSurface,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
GAP_DIR = ROOT / "outputs/evidence/s3_extended_gap_v1"
ARM_DIRS = {
    "orig_04": ROOT / "outputs/development/s3_extended_baseline_04_v1",
    "v3_08": ROOT / "outputs/development/s3_extended_v3_v1",
    "v3_04": ROOT / "outputs/development/s3_extended_v3_gamma04_v1",
    "v3_04_repaired": ROOT / "outputs/development/s3_extended_v3_repair_v1",
}


# --------------------------------------------------------------------------- doubles


class _Action:
    def __init__(self, activity_id, name):
        self._row = {"id": activity_id, "name": name}

    def get(self, key, default=None):
        return self._row.get(key, default)

    def __getitem__(self, key):
        return self._row[key]


class _Model:
    def __init__(self, labels):
        self.actions = [_Action(f"a{i}", name) for i, name in enumerate(labels)]


class _FakeV3:
    """A v3 double with a fixed localization verdict and lemmatised similarity."""

    method_id = "fake_evidence_checks_v3"
    tau = gamma = theta = 0.8

    _REASON = {DECISION_NOT_SATISFIED: "requirement_evidence_not_satisfied",
               DECISION_UNDETERMINED: "ambiguous_action_mapping"}

    def __init__(self, verdict, lemmatised_similarity: float = 0.9):
        self.verdict = verdict
        self.lemmatised_similarity = lemmatised_similarity

    def action_match(self, rule_action, model):
        candidates = [{"activity_id": a["id"], "label": a["name"],
                       "raw_similarity": self.lemmatised_similarity}
                      for a in model.actions]
        best = candidates[0] if candidates else {}
        if self.verdict == DECISION_MAPPED:
            return {"mapped": True, "reason": None, "match_tier": "exact_label",
                    "best": best, "candidates": candidates}
        return {"mapped": False, "reason": self._REASON[self.verdict],
                "match_tier": self.verdict, "best": best, "candidates": candidates}


def _raw_similarity(rule_action: str, label: str) -> float:
    """Deterministic stand-in for the arm's raw label similarity."""
    return 1.0 if rule_action.strip().lower() == label.strip().lower() else 0.5


def _scorer(verdict=DECISION_NOT_SATISFIED, lemmatised_similarity=0.9, gamma_action=0.4,
            gamma_ext=0.5):
    return RepairedExtendedScorer(_FakeV3(verdict, lemmatised_similarity),
                                  _raw_similarity, gamma_action, gamma_ext)


# --------------------------------------------------------------- stored-arm checks


@pytest.fixture(scope="module")
def panel():
    return json.loads(PANEL.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gold(panel):
    return {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}


def _rows(key):
    path = ARM_DIRS[key] / "predictions.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_repaired_arm_carries_its_own_named_method():
    rows = _rows("v3_04_repaired")
    assert len(rows) == 40
    assert {r["method_id"] for r in rows} == {"v3_localization_repaired"}
    assert {r["thresholds"]["repair_id"] for r in rows} == {REPAIR_ID}


def test_rederived_original_path_cell_reproduces_the_frozen_winter_arm():
    """The current code state must still produce the frozen Winter-style decisions.

    Only the decision-relevant fields are compared, each row against its own
    stored ``unified_predicted_raw``; the diagnostic
    ``exact_contradiction.reason`` wording is not a decision.

    Note: ``outputs/development/s3_extended_violation_panel_v2_winter`` is the
    ORIGINAL pre-formula-repair panel run and is deliberately NOT the binding
    reference (the formula repair supersedes its constraint scores).  The frozen
    ``s3_formula_repair_v2`` arm is the binding one.
    """
    def decision(row):
        predicted = row.get("unified_predicted_raw", row.get("predicted_violation_type"))
        return {
            "scores": row["scores"],
            "observable": {t: row["observability"][t]["observable"]
                           for t in EXTENDED_TYPES},
            "reasons": {t: row["observability"][t]["reason"] for t in EXTENDED_TYPES},
            "control": {
                t: {
                    "score": row["control_scores"][t]["score"],
                    "observable": row["control_scores"][t]["observable"],
                    "reason": row["control_scores"][t]["reason"],
                    "contradiction": bool(
                        (row["control_scores"][t].get("exact_contradiction") or {})
                        .get("contradiction")),
                } for t in EXTENDED_TYPES},
            "predicted": predicted,
        }

    rederived = {r["item_id"]: r for r in _rows("orig_04")}
    frozen_path = (ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/"
                   "reference/winter/predictions.jsonl")
    frozen = {json.loads(line)["item_id"]: json.loads(line) for line in
              frozen_path.read_text(encoding="utf-8").splitlines() if line.strip()}
    assert set(rederived) == set(frozen)
    for item in rederived:
        assert decision(rederived[item]) == decision(frozen[item]), item


def test_threshold_migration_changes_nothing_in_the_v3_path():
    """The 0.4 diagnostic arm is decision-identical to the existing 0.8 v3 arm."""
    a = {r["item_id"]: r for r in _rows("v3_08")}
    b = {r["item_id"]: r for r in _rows("v3_04")}
    assert set(a) == set(b)
    for item in a:
        assert a[item]["scores"] == b[item]["scores"], item
        assert a[item]["observability"] == b[item]["observability"], item
        assert a[item]["control_scores"] == b[item]["control_scores"], item
        assert a[item]["unified_predicted_raw"] == b[item]["unified_predicted_raw"], item
        loc_a = a[item]["action_localization"]["variant"]
        loc_b = b[item]["action_localization"]["variant"]
        for field in ("decision", "match_tier", "reason", "candidate_max_similarity",
                      "winner_similarity"):
            assert loc_a[field] == loc_b[field], (item, field)


def test_metric_partitions_are_exhaustive_and_disjoint(panel, gold):
    gamma_ext = float(panel["config"]["gamma_ext"])
    for key in ARM_DIRS:
        rows = _rows(key)
        metrics = arm_metrics(rows, panel, gold, gamma_ext)
        part = metrics["A_variant_only_40"]["partition"]
        assert (part["correct"] + part["wrong_type"] + part["abstained"]
                + part["false_compliance"]) == part["objects"] == 40
        control = metrics["B_control_40"]
        assert (control["explicitly_compliant"] + control["false_positives"]
                + control["abstained"]) == control["objects"] == 40
        assert metrics["C_paired_40"]["both_sides_correct"] <= 40
        assert metrics["D_merged_80"]["denominator"] == 80
        # every item appears exactly once on each side
        listed = (part["items"]["correct"] + part["items"]["wrong_type"]
                  + part["items"]["abstained"] + part["items"]["false_compliance"])
        assert sorted(listed) == sorted(r["item_id"] for r in rows)
        assert len(set(listed)) == 40


def test_repaired_arm_has_no_regression_against_winter_on_the_variant_side(panel, gold):
    gamma_ext = float(panel["config"]["gamma_ext"])
    winter = {r["item_id"]: r for r in _rows("orig_04")}
    repaired = {r["item_id"]: r for r in _rows("v3_04_repaired")}
    expected = {v: g["expected_violation"] for v, g in gold.items()}

    def correct(row):
        return row.get("unified_predicted_raw") == expected[row["item_id"]]

    assert all(not correct(winter[i]) or correct(repaired[i]) for i in winter)
    gains = [i for i in winter if not correct(winter[i]) and correct(repaired[i])]
    assert sorted(gains) == ["syn_v2_constraint_violated_03",
                             "syn_v2_required_condition_10"]
    # the gains are accounted for: Winter abstained on both, the repair resolved them
    for item in gains:
        assert winter[item]["observability"][expected[item]]["observable"] is False
        assert repaired[item]["observability"][expected[item]]["observable"] is True
        assert repaired[item]["action_localization"]["variant"]["resolved_by"] in (
            RESOLVED_BY_V3_MATCH, RESOLVED_BY_ACTION_GAMMA)


def test_every_observable_evidence_score_is_bound_to_the_resolved_activity():
    """The three evidence types must consume evidence of the resolved activity.

    ``prohibited_action_present`` scores the action label itself, so it has no
    candidate surface and is checked only for the activity identity it reports.
    """
    rows = _rows("v3_04_repaired")
    seen = 0
    evidence_types = ("required_condition_not_enforced", "constraint_violated",
                      "exception_not_handled")
    for row in rows:
        for side in ("variant", "control"):
            resolved = row["action_localization"][side]["resolved_activity_id"]
            binding = row["evidence_binding"][side]
            for t in evidence_types:
                entry = binding[t]
                if entry["consumed_score"] is None:
                    continue
                seen += 1
                assert entry["same_activity_as_localization"], (row["item_id"], side, t)
                assert entry["matched_activity_id"] == resolved, (row["item_id"], t)
                if t == "constraint_violated":
                    # only the constraint surface carries an activity binding
                    assert entry["surface_activity_id_equals_resolution"], (row["item_id"], t)
                else:
                    assert entry["surface_activity_id"] is None, (row["item_id"], t)
            prohibited = binding["prohibited_action_present"]
            if prohibited["consumed_score"] is not None:
                assert prohibited["matched_activity_id"] is None
    assert seen > 0


def test_gap_evidence_lists_are_regenerable_and_conserved():
    data = json.loads((GAP_DIR / "difference_lists.json").read_text(encoding="utf-8"))
    lists = data["lists"]
    assert lists["A_winter_correct_v3_wrong"]["counts"]["total"] == 7
    assert lists["C_v3_correct_winter_wrong"]["counts"]["total"] == 0
    assert lists["A2_winter_correct_repaired_wrong"]["counts"]["total"] == 0
    assert lists["D_threshold_migration_only_changes"]["counts"]["total"] == 0
    assert lists["D2_same_threshold_factor_on_original_path"]["counts"]["total"] > 0
    for key, entry in lists.items():
        assert entry["counts"]["total"] == len(entry["items"]), key
        for item in entry["items"]:
            assert item["mutation_metadata_read"] is False
            assert item["cause_class"] in (
                "proved_by_record", "needs_experiment") or \
                item["cause_class"].startswith(("proved_by_record:", "needs_experiment:"))


def test_comparison_artifact_reproduces_from_the_cells():
    data = json.loads((GAP_DIR / "comparison_v1.json").read_text(encoding="utf-8"))
    arms = data["arms"]
    assert set(arms) == {"winter_frozen", "sun_frozen", "orig_04_rederived",
                         "v3_08_existing", "v3_04_diagnostic", "v3_04_repaired"}
    repaired = arms["v3_04_repaired"]["A_variant_only_40"]
    p = repaired["partition"]
    assert (p["correct"], p["wrong_type"], p["abstained"], p["false_compliance"]) == \
        (19, 9, 10, 2)
    c = arms["v3_04_repaired"]["B_control_40"]
    assert (c["explicitly_compliant"], c["false_positives"], c["abstained"]) == (14, 20, 6)
    # the re-derived cell and the frozen Winter-style block agree on the A metrics
    assert arms["orig_04_rederived"]["A_variant_only_40"]["evaluation"]["macro_f1"] == \
        arms["winter_frozen"]["A_variant_only_40"]["evaluation"]["macro_f1"]


# ------------------------------------------------------------- repair behaviour


def test_prohibited_score_is_the_raw_label_formula_not_the_lemmatised_value():
    scorer = _scorer(verdict="mapped", lemmatised_similarity=0.51)
    model = _Model(["erase personal data", "notify national authority"])
    sentence = {"modality": "prohibition", "action": "erase personal data"}
    result = scorer.prohibited_action(sentence, model)
    assert result["observable"] is True
    # the raw formula gives an exact match here; the lemmatised value is 0.51
    assert result["score"] == 1.0
    assert result["score"] != 0.51
    assert result["violation"] is True
    assert result["score_source"] == "max_raw_label_similarity_over_process_activities"


def test_prohibited_decision_and_reported_boolean_cannot_disagree():
    scorer = _scorer(lemmatised_similarity=0.99)
    model = _Model(["apply", "notify national authority"])
    sentence = {"modality": "prohibition", "action": "erase personal data"}
    result = scorer.prohibited_action(sentence, model)
    assert result["observable"] is True
    assert result["score"] == 0.5
    assert result["violation"] == (result["score"] >= scorer.gamma_ext)


def test_prohibited_is_unobservable_only_when_there_is_nothing_to_compare():
    scorer = _scorer()
    sentence = {"modality": "prohibition", "action": "erase personal data"}
    empty = scorer.prohibited_action(sentence, _Model([]))
    assert empty["observable"] is False
    assert empty["reason"] == "no_process_actions"
    assert scorer.prohibited_action({"modality": "obligation", "action": "x"},
                                    _Model(["x"]))["reason"] == "rule_modality_not_prohibition"
    assert scorer.prohibited_action({"modality": "prohibition", "action": ""},
                                    _Model(["x"]))["reason"] == "empty_rule_action"


def test_one_resolution_is_used_by_every_check():
    scorer = _scorer(verdict=DECISION_NOT_SATISFIED)
    model = _Model(["Communication with data subject", "erase personal data"])
    sentence = {"modality": "obligation", "action": "erase personal data",
                "condition": "where one of the grounds applies", "constraint": None,
                "exception": None}
    resolution = scorer.resolve_action(sentence["action"], model)
    assert resolution["resolved_by"] == RESOLVED_BY_ACTION_GAMMA
    assert resolution["resolved_activity_id"] == "a1"
    for check, field in ((scorer.required_condition, "condition"),
                         (scorer.exception_not_handled, "exception")):
        result = check(dict(sentence, **{field: "some required evidence"}), model,
                       ["visible condition text"])
        assert result["matched_activity_id"] == resolution["resolved_activity_id"]
        assert result["resolved_by"] == resolution["resolved_by"]


def test_unresolvable_action_keeps_evidence_unobservable_and_unscored():
    scorer = _scorer(gamma_action=0.9)
    model = _Model(["Communication with data subject"])
    sentence = {"modality": "obligation", "action": "erase personal data",
                "condition": "where one of the grounds applies"}
    resolution = scorer.resolve_action(sentence["action"], model)
    assert resolution["resolved_by"] == RESOLVED_NONE
    assert resolution["resolved_activity_id"] is None
    result = scorer.required_condition(sentence, model, ["visible condition text"])
    assert result["observable"] is False
    assert result["score"] is None
    assert result["reason"] == "action_not_resolvable_to_activity"


def test_v3_satisfied_match_still_wins_over_the_label_argmax():
    scorer = _scorer(verdict=DECISION_MAPPED)
    model = _Model(["notify national authority", "erase personal data"])
    resolution = scorer.resolve_action("erase personal data", model)
    assert resolution["resolved_by"] == RESOLVED_BY_V3_MATCH
    assert resolution["resolved_activity_id"] == "a0"  # the fake v3 always picks a0


def test_undetermined_localization_is_not_an_unresolvable_action():
    """v3's under-determined verdict must not silently become 'no violation'.

    The action is still resolvable, so the evidence is compared and the verdict
    follows the evidence: a visible matching condition is not a violation, a
    missing one is.
    """
    scorer = _scorer(verdict=DECISION_UNDETERMINED)
    model = _Model(["erase personal data", "notify the authority"])
    sentence = {"modality": "obligation", "action": "erase personal data",
                "condition": "where the grounds apply"}
    resolution = scorer.resolve_action(sentence["action"], model)
    assert resolution["v3_decision"] == DECISION_UNDETERMINED
    assert resolution["resolved_by"] == RESOLVED_BY_ACTION_GAMMA
    visible = scorer.required_condition(sentence, model, ["where the grounds apply"])
    assert visible["observable"] is True
    assert visible["score"] == 0.0
    assert visible["violation"] is False
    missing = scorer.required_condition(sentence, model, ["an unrelated gateway label"])
    assert missing["observable"] is True
    assert missing["score"] == 1.0 - missing["max_sim"]
    assert missing["violation"] == (missing["score"] > scorer.gamma_ext)
    assert missing["matched_activity_id"] == resolution["resolved_activity_id"]


def test_not_satisfied_localization_is_not_a_violation_by_itself():
    scorer = _scorer(verdict=DECISION_NOT_SATISFIED)
    model = _Model(["erase personal data"])
    sentence = {"modality": "obligation", "action": "erase personal data",
                "condition": "where the grounds apply"}
    result = scorer.required_condition(sentence, model, ["where the grounds apply"])
    assert result["observable"] is True
    assert result["violation"] is False  # the evidence is visible: no violation


def test_contradiction_branch_needs_the_same_resolution():
    scorer = _scorer(verdict=DECISION_NOT_SATISFIED)
    model = _Model(["notify the breach"])
    sentence = {"modality": "obligation", "action": "notify the breach",
                "condition": None, "constraint": "within 72 hours"}
    surface = ConstraintSurface(["notify the breach", "within 30 days"],
                                ["within 30 days"], "a0")
    result = scorer.constraint_violated(sentence, model, surface)
    assert result["exact_contradiction"]["contradiction"] is True
    assert result["violation"] is True

    other_surface = ConstraintSurface(["notify the breach", "within 30 days"],
                                      ["within 30 days"], "a1")
    result = scorer.constraint_violated(sentence, model, other_surface)
    assert result["exact_contradiction"]["contradiction"] is False


def test_duration_inside_the_applicability_condition_is_not_a_deadline():
    scorer = _scorer()
    model = _Model(["erase personal data"])
    sentence = {"modality": "obligation", "action": "erase personal data",
                "condition": "without undue delay where one of the grounds applies",
                "constraint": "without undue delay"}
    surface = ConstraintSurface(["erase personal data"], ["within 30 days"], "a0")
    result = scorer.constraint_violated(sentence, model, surface)
    assert result["exact_contradiction"]["contradiction"] is False
    assert result["exact_contradiction"]["reason"] == "time_bound_inside_condition"


def test_repair_reads_no_label_field():
    """Changing every forbidden input must not change a single decision."""
    scorer = _scorer(verdict=DECISION_NOT_SATISFIED)
    model = _Model(["notify national authority", "erase personal data"])
    sentence = {"modality": "prohibition", "action": "erase personal data",
                "condition": "where the grounds apply", "constraint": "within 72 hours",
                "exception": "unless the data subject objects"}
    base = {
        "prohibited": scorer.prohibited_action(sentence, model),
        "condition": scorer.required_condition(sentence, model, ["gateway label"]),
        "constraint": scorer.constraint_violated(
            sentence, model, ConstraintSurface(["gateway label"], [], "a1")),
        "exception": scorer.exception_not_handled(sentence, model, ["boundary label"]),
    }
    tampered = dict(sentence)
    tampered.update({"expected_violation": "prohibited_action_present",
                     "target_activity_id": "a1", "mutation_type": "prohibited_action_present",
                     "variant_id": "syn_v2_prohibited_action_01"})
    scorer2 = _scorer(verdict=DECISION_NOT_SATISFIED)
    again = {
        "prohibited": scorer2.prohibited_action(tampered, model),
        "condition": scorer2.required_condition(tampered, model, ["gateway label"]),
        "constraint": scorer2.constraint_violated(
            tampered, model, ConstraintSurface(["gateway label"], [], "a1")),
        "exception": scorer2.exception_not_handled(tampered, model, ["boundary label"]),
    }
    assert base == again


# ------------------------------------------------------- small real-backend cases


@pytest.fixture(scope="module")
def real_backend():
    spacy = pytest.importorskip("spacy")
    from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    v3 = EvidenceChecksV3(sim, 0.8, 0.8, 0.8, nlp)
    return sim, v3


def test_general_rule_same_verb_different_object_is_not_the_same_action(real_backend):
    """'notify the controller' must not be read as the process's 'Notify authority'."""
    sim, v3 = real_backend
    scorer = RepairedExtendedScorer(v3, sim.text_pair, 0.4, 0.5)
    model = _Model(["Notify national authority", "Erase personal data"])
    exact = scorer.prohibited_action(
        {"modality": "prohibition", "action": "notify the controller"}, model)
    unrelated = scorer.prohibited_action(
        {"modality": "prohibition", "action": "Erase personal data"}, model)
    assert unrelated["score"] > exact["score"]
    assert unrelated["violation"] is True
    assert exact["violation"] is False


def test_general_rule_same_object_different_recipient_keeps_the_activity_but_not_the_score(
        real_backend):
    """Reversed recipients must not be treated as the same prohibition score."""
    sim, v3 = real_backend
    scorer = RepairedExtendedScorer(v3, sim.text_pair, 0.4, 0.5)
    model = _Model(["Transfer money to Bob"])
    to_bob = scorer.prohibited_action(
        {"modality": "prohibition", "action": "transfer money to Bob"}, model)
    to_alice = scorer.prohibited_action(
        {"modality": "prohibition", "action": "transfer money to Alice"}, model)
    assert to_bob["score"] > to_alice["score"]
    assert to_alice["best_candidate"] == "Transfer money to Bob"


def test_general_rule_condition_deadline_differs_from_the_action_deadline(real_backend):
    """A duration in the applicability condition is not the main action's limit."""
    sim, v3 = real_backend
    scorer = RepairedExtendedScorer(v3, sim.text_pair, 0.4, 0.5)
    model = _Model(["Erase personal data"])
    inside_condition = scorer.constraint_violated(
        {"modality": "obligation", "action": "erase personal data",
         "condition": "without undue delay where the grounds apply",
         "constraint": "without undue delay"},
        model, ConstraintSurface(["erase personal data"], ["within 30 days"], "a0"))
    assert inside_condition["exact_contradiction"]["reason"] == "time_bound_inside_condition"
    as_deadline = scorer.constraint_violated(
        {"modality": "obligation", "action": "erase personal data",
         "condition": None, "constraint": "within 72 hours"},
        model, ConstraintSurface(["erase personal data"], ["within 30 days"], "a0"))
    assert as_deadline["exact_contradiction"]["contradiction"] is True
    assert as_deadline["exact_contradiction"]["reason"] == "candidate_time_limit_exceeds_rule_limit"
    no_conflict = scorer.constraint_violated(
        {"modality": "obligation", "action": "erase personal data",
         "condition": None, "constraint": "within 72 hours"},
        model, ConstraintSurface(["erase personal data"], ["within 24 hours"], "a0"))
    assert no_conflict["exact_contradiction"]["contradiction"] is False
    assert no_conflict["exact_contradiction"]["reason"] == "no_conflicting_value_found"


def test_variant_partition_rejects_an_incomplete_row_set(panel, gold):
    rows = _rows("v3_04_repaired")[:39]
    with pytest.raises(ValueError):
        variant_partition(rows, gold, expected_objects=40)


def test_variant_partition_rejects_a_row_without_gold(panel, gold):
    rows = copy.deepcopy(_rows("v3_04_repaired"))
    rows[0]["item_id"] = "not_in_the_panel"
    with pytest.raises(KeyError):
        variant_partition(rows, gold, expected_objects=40)

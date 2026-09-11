# -*- coding: utf-8 -*-
"""Focused checks for the S3.9-EXT limited repair v2.

Two halves, both fast:

* **behaviour verification** - small non-panel examples that prove the three
  fixed mechanisms really act: v3's own threshold, the whitespace fold, and the
  refusal to resolve an action to one activity.  These run before any panel
  inference and never touch the 80-instance panel.
* **artifact verification** - the stored three-arm run is recomputed from its own
  rows; no arm is re-run.

What this file deliberately does NOT do: assert that a field still contains the
string ``undetermined``.  The ambiguity checks assert the observable consequence -
that no evidence is consumed for a check that needs one activity.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid.s3_action_matching_v3 import EvidenceChecksV3  # noqa: E402
from bpc_hybrid.s3_extended_v3_adapter import (  # noqa: E402
    DECISION_MAPPED, DECISION_UNDETERMINED, V3ExtendedScorer,
)
from bpc_hybrid.s3_extended_v3_repair_v2 import (  # noqa: E402
    NORMALIZER_ID, REPAIR_V2_ID, UNRESOLVED_RAW_TIE, UNRESOLVED_V3_UNDETERMINED,
    ConsistentRawScorer, RepairedExtendedScorerV2, fold_whitespace, repair_v2_policy,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES, ConstraintSurface,
)

RUNNER = ROOT / "scripts/run_s3_extended_repair_v2_v1.py"
OUT = ROOT / "outputs/development/s3_extended_repair_v2_v1"
PREVIOUS_INVALID = ROOT / "outputs/development/s3_extended_v3_gamma04_v1"
PREVIOUS_REPAIR = ROOT / "outputs/development/s3_extended_v3_repair_v1"
WINTER = (ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/reference/winter/"
          "predictions.jsonl")


# --------------------------------------------------------------------------- doubles


class _Action:
    def __init__(self, activity_id, name):
        self._row = {"id": activity_id, "name": name}

    def get(self, key, default=None):
        return self._row.get(key, default)

    def __getitem__(self, key):
        return self._row[key]


class _Model:
    def __init__(self, labels, process_id="p"):
        self.process_id = process_id
        self.actions = [_Action(f"a{i}", name) for i, name in enumerate(labels)]


class _Sim:
    """A similarity double: the pair table decides every score."""

    def __init__(self, table, default=0.0):
        self.table = table
        self.default = default

    def text_pair(self, left, right):
        return self.table.get((left, right), self.default)


def _require_spacy():
    spacy = pytest.importorskip("spacy")
    return spacy.load("en_core_web_sm")


# ------------------------------------------------------- 1. threshold really acts


def test_v3_internal_gamma_changes_a_similarity_tier_decision():
    """A candidate that only passes through the similarity tier must flip at 0.4 / 0.8.

    The double gives every candidate the same score 0.55, so no exact label match
    and no structural agreement can decide the outcome: only the tier comparison
    with ``self.gamma`` can.  0.4 < 0.55 <= 0.8.
    """
    nlp = _require_spacy()
    sim = _Sim({}, default=0.55)
    # predicates differ from the rule action, so the structural tier cannot engage
    model = _Model(["Release the record", "Archive the record"])
    at_04 = EvidenceChecksV3(sim, 0.8, 0.4, 0.8, nlp)
    at_08 = EvidenceChecksV3(sim, 0.8, 0.8, 0.8, nlp)
    r04 = at_04.action_match("transmit the file", model)
    r08 = at_08.action_match("transmit the file", model)
    assert r04["mapped"] is True
    assert r04["match_tier"] == "similarity_satisfied"
    assert r08["mapped"] is False
    assert r08["match_tier"] == "no_candidate_above_gamma"
    assert r04["best"]["raw_similarity"] == pytest.approx(0.55)
    assert r04 != r08


def test_v3_internal_gamma_is_not_read_from_the_wrong_config():
    """The guard must fail on exactly the previous batch's configuration.

    The previous batch built its checker with the Sun config gamma 0.8 while
    declaring 0.4; the guard has to reject that pair.
    """
    runner = _load_runner()
    declared = runner.ARMS["A_v3_internal_0_4"]["v3_internal_gamma"]
    assert declared == 0.4
    nlp = _require_spacy()
    sim = _Sim({}, default=0.6)
    good = EvidenceChecksV3(sim, 0.8, declared, 0.8, nlp)
    wrong = EvidenceChecksV3(sim, 0.8, 0.8, 0.8, nlp)  # the previous batch's mistake
    with pytest.raises(RuntimeError):
        runner.assert_thresholds_in_force(good, good)   # C requires 0.8
    with pytest.raises(RuntimeError):
        runner.assert_thresholds_in_force(wrong, wrong)  # A requires 0.4
    runner.assert_thresholds_in_force(good, wrong)
    # and the guard also refuses a wrong tau / theta
    with pytest.raises(RuntimeError):
        runner.assert_thresholds_in_force(good, EvidenceChecksV3(sim, 0.5, 0.8, 0.8, nlp))


def test_exact_label_match_is_not_a_gamma_test():
    """An exact label match must win at every gamma, so it cannot show the effect."""
    nlp = _require_spacy()
    sim = _Sim({}, default=0.0)
    model = _Model(["release the record"])
    for gamma in (0.4, 0.8):
        result = EvidenceChecksV3(sim, 0.8, gamma, 0.8, nlp).action_match(
            "release the record", model)
        assert result["mapped"] is True
        assert result["match_tier"] == "exact_label"


# ------------------------------------------------------- 2. whitespace normalisation


def test_fold_whitespace_only_removes_whitespace():
    samples = ["Communicate the rectification\n", "  spaced   out  ", "tab\there",
               "line\r\nbreak", "no-change"]
    for text in samples:
        folded = fold_whitespace(text)
        assert folded.split() == text.split()
        assert folded == folded.strip()
        assert "\n" not in folded and "\t" not in folded and "\r" not in folded
        assert len("".join(folded.split())) == len("".join(text.split()))


def test_fold_whitespace_does_not_change_identity_or_meaning():
    original = "Communicate the rectification\n"
    folded = fold_whitespace(original)
    assert original != folded
    assert folded == "Communicate the rectification"
    assert original.strip() == folded
    # the raw label is still what is stored and reported
    sim = _Sim({("rule", folded): 0.9, ("rule", original): 0.1})
    scorer = ConsistentRawScorer(sim.text_pair, sim.text_pair, 0.4, 0.5)
    model = _Model([original])
    evidence = scorer.folded_evidence("rule", model)
    assert evidence["rule_action_folded"] == "rule"
    assert evidence["candidates"][0]["label"] == original
    assert evidence["candidates"][0]["label_folded"] == folded
    assert evidence["candidates"][0]["score"] == pytest.approx(0.9)


def test_whitespace_fold_alone_can_cross_the_action_gamma():
    """The measured trailing-newline effect, reproduced off-panel."""
    action = "have the right to obtain the rectification"
    raw_label = "Communicate the rectification\n"
    folded_label = fold_whitespace(raw_label)
    sim = _Sim({(action, raw_label): 0.282807, (action, folded_label): 0.483290})
    model = _Model([raw_label])

    frozen = ConsistentRawScorer(lambda a, b: sim.text_pair(a, b), sim.text_pair,
                                 0.4, 0.5)
    # the previous repair folded only the rule action, not the label
    previous = RepairedExtendedScorerV2(_MappedV3(), sim.text_pair, 0.4, 0.5)
    previous._raw_best_action = lambda a, m: {  # type: ignore[assignment]
        "score": sim.text_pair(fold_whitespace(a), raw_label), "label": raw_label,
        "activity_id": "a0", "tied_activity_ids": ["a0"], "candidate_count": 1,
        "rule_action_folded": fold_whitespace(a), "candidates": []}
    prev_score = previous._raw_best_action(action, model)["score"]
    new_score = frozen.folded_evidence(action, model)["candidates"][0]["score"]
    assert prev_score == pytest.approx(0.282807)
    assert new_score == pytest.approx(0.483290)
    assert prev_score < 0.4 <= new_score


class _MappedV3:
    method_id = "double"
    tau = gamma = theta = 0.8

    def action_match(self, rule_action, model):
        return {"mapped": True, "reason": None, "match_tier": "exact_label",
                "best": {"activity_id": "a0", "label": "x", "raw_similarity": 1.0},
                "candidates": []}


# ------------------------------------------------------- 3. ambiguity handling


class _VerdictV3:
    method_id = "verdict_double"
    tau = gamma = theta = 0.8

    def __init__(self, verdict, reason, winner_id="a0", score=0.9):
        self.verdict = verdict
        self.reason = reason
        self.winner_id = winner_id
        self.score = score

    def action_match(self, rule_action, model):
        best = {"activity_id": self.winner_id, "label": "x", "raw_similarity": self.score}
        return {"mapped": False, "reason": self.reason, "match_tier": self.verdict,
                "best": best, "candidates": [best]}


def test_v3_undetermined_does_not_get_a_forced_activity():
    """v3 refuses to choose; the fallback must not choose for it."""
    sim = _Sim({}, default=0.9)  # a high raw score that would otherwise resolve
    v3 = _VerdictV3(DECISION_UNDETERMINED, "ambiguous_action_mapping")
    scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
    model = _Model(["one", "two"])
    sentence = {"modality": "obligation", "action": "notify the controller",
                "condition": "where the grounds apply"}
    resolution = scorer.resolve_action(sentence["action"], model)
    assert resolution["resolved_activity_id"] is None
    assert resolution["unresolved_reason"] == UNRESOLVED_V3_UNDETERMINED
    result = scorer.required_condition(sentence, model, ["some visible condition"])
    # the observable consequence, not the stored string
    assert result["observable"] is False
    assert result["score"] is None
    assert result.get("violation") is not True
    assert result["matched_activity_id"] is None
    assert result["reason"] == UNRESOLVED_V3_UNDETERMINED


def test_not_satisfied_verdict_still_allows_the_raw_fallback():
    """The refusal is about undetermined, not about every non-satisfying verdict."""
    sim = _Sim({("notify the controller", "one"): 0.9,
                ("notify the controller", "another"): 0.3})
    v3 = _VerdictV3("structure_not_satisfied", "requirement_evidence_not_satisfied")
    scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
    model = _Model(["one", "another"])
    resolution = scorer.resolve_action("notify the controller", model)
    assert resolution["resolved_activity_id"] == "a0"
    assert resolution["resolved_by"] == "label_argmax_at_or_above_action_gamma"
    assert resolution["unresolved_reason"] is None
    result = scorer.required_condition(
        {"modality": "obligation", "action": "notify the controller",
         "condition": "where the grounds apply"}, model, ["some visible condition"])
    assert result["observable"] is True
    assert result["comparison_performed"] is True


def test_raw_argmax_tie_on_different_nodes_is_not_resolved():
    """Two activities with equal top scores: no evidence separates them."""
    action = "notify the controller"
    label = "Notify the controller"
    sim = _Sim({(action, label): 0.7})
    v3 = _VerdictV3("no_candidate_above_gamma", "no_candidate_above_gamma")
    scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
    model = _Model([label, label])  # identical labels on two ids
    resolution = scorer.resolve_action(action, model)
    assert resolution["resolved_activity_id"] is None
    assert resolution["unresolved_reason"] == UNRESOLVED_RAW_TIE
    assert resolution["raw_tie_activity_ids"] == ["a0", "a1"]
    result = scorer.exception_not_handled(
        {"modality": "obligation", "action": action, "exception": "unless it applies"},
        model, ["some boundary label"])
    assert result["observable"] is False
    assert result["score"] is None


def test_a_single_winner_is_still_resolved_and_consumed():
    """The tie rule must not block the ordinary single-winner case."""
    action = "notify the controller"
    label = "Notify the controller"
    sim = _Sim({(action, label): 0.7}, default=0.1)
    v3 = _VerdictV3("no_candidate_above_gamma", "no_candidate_above_gamma")
    scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
    model = _Model([label, "Unrelated task"])
    resolution = scorer.resolve_action(action, model)
    assert resolution["resolved_activity_id"] == "a0"
    assert resolution["raw_tie_activity_ids"] == ["a0"]
    result = scorer.required_condition(
        {"modality": "obligation", "action": action, "condition": "where it applies"},
        model, ["some visible condition"])
    assert result["observable"] is True
    assert result["matched_activity_id"] == "a0"


def test_prohibition_presence_is_not_gated_by_resolution_and_says_so():
    """The presence check never needed one activity, and reports that explicitly."""
    action = "notify the controller"
    label = "Notify the controller"
    sim = _Sim({(action, label): 0.7})
    v3 = _VerdictV3(DECISION_UNDETERMINED, "ambiguous_action_mapping")
    scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
    model = _Model([label, label])
    sentence = {"modality": "prohibition", "action": action}
    result = scorer.prohibited_action(sentence, model)
    resolution = scorer.resolve_action(action, model)
    assert resolution["resolved_activity_id"] is None
    assert result["observable"] is True
    assert result["resolution_required"] is False
    assert result["score"] == pytest.approx(0.7)
    assert result["violation"] == (result["score"] >= scorer.gamma_ext)


def test_ambiguity_never_becomes_compliance_or_violation():
    sim = _Sim({}, default=0.95)
    v3 = _VerdictV3(DECISION_UNDETERMINED, "ambiguous_action_mapping")
    scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
    model = _Model(["one", "two"])
    sentence = {"modality": "obligation", "action": "erase personal data",
                "condition": "where it applies", "constraint": "within 72 hours",
                "exception": "unless it applies"}
    surface = ConstraintSurface(["one"], ["within 30 days"], None)
    for result in (scorer.required_condition(sentence, model, ["one"]),
                   scorer.constraint_violated(sentence, model, surface),
                   scorer.exception_not_handled(sentence, model, ["one"])):
        assert result["observable"] is False
        assert result["score"] is None
        assert result.get("violation") is not True


def test_repair_v2_reads_no_label_field():
    sim = _Sim({}, default=0.9)
    v3 = _VerdictV3("no_candidate_above_gamma", "no_candidate_above_gamma")
    sentence = {"modality": "prohibition", "action": "erase personal data",
                "condition": "where it applies", "constraint": "within 72 hours",
                "exception": "unless the subject objects"}
    model = _Model(["Erase personal data", "Erase personal data"])
    surface = ConstraintSurface(["Erase personal data"], ["within 30 days"], "a0")
    base = None
    for extra in ({}, {"expected_violation": "prohibited_action_present",
                       "target_activity_id": "a0", "variant_id": "syn_x"}):
        scorer = RepairedExtendedScorerV2(v3, sim.text_pair, 0.4, 0.5)
        current = {
            "prohibited": scorer.prohibited_action(dict(sentence, **extra), model),
            "condition": scorer.required_condition(dict(sentence, **extra), model, ["one"]),
            "constraint": scorer.constraint_violated(dict(sentence, **extra), model, surface),
            "exception": scorer.exception_not_handled(dict(sentence, **extra), model, ["one"]),
        }
        if base is None:
            base = current
        else:
            assert current == base


# --------------------------------------------------------------- stored artifacts


def _load_runner():
    spec = importlib.util.spec_from_file_location("s3_extended_repair_v2_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s3_extended_repair_v2_runner"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def stored():
    return _load_runner().verify_outputs()


def test_plan_is_pre_registered_with_three_arms():
    plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
    assert plan["arm_count"] == 3
    assert plan["runs_per_arm"] == 1
    assert set(plan["arms"]) == {"A_v3_internal_0_4", "B_original_path_normalized",
                                 "C_v3_no_forced_resolution"}
    assert plan["arms"]["A_v3_internal_0_4"]["v3_internal_gamma"] == 0.4
    assert plan["arms"]["C_v3_no_forced_resolution"]["v3_internal_gamma"] == 0.8
    assert plan["arms"]["C_v3_no_forced_resolution"]["label_fallback_gamma"] == 0.4
    assert plan["previous_claims"]["withdrawn"]
    assert plan["implementation"] and plan["inputs"]


def test_every_row_records_the_parameters_that_were_in_force(stored):
    for row in stored["rows"]:
        arm = row["arm"]
        declared = stored["plan"]["arms"][arm]
        assert row["thresholds"]["v3_internal_gamma"] == declared["v3_internal_gamma"]
        assert row["thresholds"]["label_fallback_gamma"] == declared["label_fallback_gamma"]
        assert row["thresholds"]["gamma_ext"] == declared["gamma_ext"]
        expected_level = ("single_level"
                          if declared["v3_internal_gamma"] == declared["label_fallback_gamma"]
                          else "two_level")
        assert row["thresholds"]["configuration_levels"] == expected_level


def test_the_invalid_previous_arm_is_flagged_as_such():
    plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
    entry = plan["reference_cells_read_only"]["v3_04_invalid_threshold_record"]
    assert "INVALID" in entry["status"]
    previous = [json.loads(l) for l in (PREVIOUS_INVALID / "predictions.jsonl")
                .read_text(encoding="utf-8").splitlines() if l.strip()]
    first = previous[0]
    # the record itself proves the mismatch the correction is about
    assert first["action_mapping_gamma"] == 0.4
    assert first["thresholds"]["v3_thresholds"]["gamma"] == 0.8


def test_metric_partitions_are_exhaustive(panel_and_gold):
    panel, gold = panel_and_gold
    data = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
    for arm, block in data["arms"].items():
        part = block["A_variant_40"]["partition"]
        assert (part["correct_type"] + part["wrong_type"] + part["explicit_compliance"]
                + part["final_unknown"]) == part["objects"] == 40
        assert part["target_type_unobservable_is_separate"] is True
        assert 0 <= part["target_type_unobservable"] <= 40
        control = block["B_control_40"]
        assert (control["false_positives"] + control["explicit_compliance"]
                + control["final_unknown"]) == control["objects"] == 40
        assert block["C_paired_40"]["both_sides_correct"] <= 40
        assert block["D_merged_80"]["denominator"] == 80


@pytest.fixture(scope="module")
def panel_and_gold():
    panel = json.loads((ROOT / "data/development/stage3_synth/"
                        "synthetic_controlled_error_extension_v2.json")
                       .read_text(encoding="utf-8"))
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    return panel, gold


def test_arm_b_shares_the_frozen_path_so_the_whitespace_factor_is_readable(stored):
    """Arm B differs from the frozen Winter cell only by the fold and the threshold."""
    arm_b = {r["item_id"]: r for r in stored["rows"]
             if r["arm"] == "B_original_path_normalized"}
    winter = {json.loads(l)["item_id"]: json.loads(l)
              for l in WINTER.read_text(encoding="utf-8").splitlines() if l.strip()}
    assert set(arm_b) == set(winter)
    for item in arm_b:
        assert arm_b[item]["scores_detail"].keys() == winter[item]["scores_detail"].keys()
    # the whitespace factor is recorded per instance for every arm
    diag = json.loads((OUT / "diagnostics.json").read_text(encoding="utf-8"))
    factor = diag["whitespace_factor_evidence"]
    assert len(factor) == 40
    for vid, entry in factor.items():
        assert entry["rule_action_folded"] == fold_whitespace(entry["rule_action"])
        for cand in entry["candidates"]:
            assert cand["fold_removes_only_whitespace"] is True
            assert cand["label_folded"] == fold_whitespace(cand["label"])


def test_whitespace_factor_explains_the_two_previous_extra_hits():
    """The two hits of the previous batch are decided by the fold, not by v3."""
    diag = json.loads((OUT / "diagnostics.json").read_text(encoding="utf-8"))
    factor = diag["whitespace_factor_evidence"]
    for vid in ("syn_v2_constraint_violated_03", "syn_v2_required_condition_10"):
        entry = factor[vid]
        assert entry["crosses_label_gamma_raw"] is False
        assert entry["crosses_label_gamma_folded"] is True
        changed = [c for c in entry["candidates"] if c["label_changed_by_fold"]]
        assert changed, vid
        assert all(c["fold_removes_only_whitespace"] for c in changed)


def _resolved_id(record):
    """The resolved activity of one side, in either stored record shape.

    Arms A and B store the adapter's localization, whose ``matched_activity_id``
    is set exactly when a satisfying match exists (``None`` when not localized).
    Arm C stores the resolution record, which carries ``resolved_activity_id``.
    """
    if "matched_activity_id" in record:
        return record["matched_activity_id"]
    return record.get("resolved_activity_id")


def test_resolution_never_consumes_evidence_without_one_activity(stored):
    """Stored-arm check: an observable evidence score always has one resolved activity.

    The frozen original path (arm B) does not store an activity id in its evidence
    blocks, so for that arm the equivalent evidence is its own action gate record
    (``action_max_sim`` >= the arm's action gamma).
    """
    evidence_types = ("required_condition_not_enforced", "constraint_violated",
                      "exception_not_handled")
    for row in stored["rows"]:
        for side in ("variant", "control"):
            binding = row["evidence_binding"][side]
            resolved = _resolved_id(row["action_localization"][side])
            arm = row["arm"]
            for t in evidence_types:
                entry = binding[t]
                if entry["consumed_score"] is None:
                    continue
                if arm == "B_original_path_normalized":
                    consumed = entry.get("action_max_sim", entry.get("consumed_similarity"))
                    assert consumed is not None and consumed >= 0.4, (row["item_id"], t)
                    assert (entry.get("action_best_candidate")
                            or entry.get("consumed_candidate")), (row["item_id"], t)
                    continue
                # the invariant is about the activity the evidence was taken from:
                # whenever a score was published, the binding must name the
                # activity it came from and the check must have compared evidence
                assert entry["matched_activity_id"] is not None, (arm, row["item_id"],
                                                                  side, t)
                assert entry["consumed_similarity"] is not None, (row["item_id"], t)
                if entry["localization_was_resolved"]:
                    assert entry["same_activity_as_resolution"] is True, (row["item_id"], t)


def test_no_stored_row_resolved_through_an_undetermined_verdict(stored):
    for row in stored["rows"]:
        for side in ("variant", "control"):
            loc = row["action_localization"][side]
            verdict = loc.get("v3_decision", loc.get("decision"))
            resolved = _resolved_id(loc)
            if verdict == DECISION_UNDETERMINED:
                assert resolved is None, (row["item_id"], side)
                assert loc["unresolved_reason"] == UNRESOLVED_V3_UNDETERMINED
            if loc.get("resolved_by"):
                assert len(loc.get("raw_tie_activity_ids") or []) <= 1, (row["item_id"], side)


def test_old_artifacts_are_untouched(stored):
    for path in (PREVIOUS_INVALID, PREVIOUS_REPAIR):
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["safety"]["existing_results_rewritten"] is False
    # the old manifests are not rebound: their recorded hashes must not name the
    # new module
    for path in (PREVIOUS_INVALID, PREVIOUS_REPAIR):
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        assert "s3_extended_v3_repair_v2.py" not in json.dumps(manifest)


def test_policy_declares_the_boundary():
    policy = repair_v2_policy()
    assert policy["module"] == REPAIR_V2_ID
    assert policy["normalizer"] == NORMALIZER_ID
    assert set(policy["changes"]) == {"R1_real_v3_gamma", "R2_consistent_whitespace",
                                      "R3_no_forced_resolution",
                                      "R4_explicit_compliance_requires_a_comparison"}
    assert policy["not_claimed"]


def test_explicit_compliance_requires_an_evidence_comparison():
    """The aggregate 'none' needs condition/constraint/exception to have compared."""
    from bpc_hybrid.s3_extended_v3_repair_v2 import aggregate_with_comparison_gate

    prohibition_only = {
        "prohibited_action_present": {"observable": True, "score": 0.2,
                                      "comparison_performed": True},
        "required_condition_not_enforced": {"observable": False, "score": None,
                                            "comparison_performed": False},
        "constraint_violated": {"observable": False, "score": None,
                                "comparison_performed": False},
        "exception_not_handled": {"observable": False, "score": None,
                                  "comparison_performed": False},
    }
    assert aggregate_with_comparison_gate(prohibition_only, 0.5)["predicted"] is None

    with_one_evidence_check = dict(prohibition_only)
    with_one_evidence_check["required_condition_not_enforced"] = {
        "observable": True, "score": 0.0, "comparison_performed": True}
    assert aggregate_with_comparison_gate(
        with_one_evidence_check, 0.5)["predicted"] == "none"

    violating = dict(with_one_evidence_check)
    violating["required_condition_not_enforced"] = {"observable": True, "score": 1.0,
                                                    "comparison_performed": True}
    assert aggregate_with_comparison_gate(
        violating, 0.5)["predicted"] == "required_condition_not_enforced"


def test_policy_declares_no_relaxation():
    """The three pre-specified thresholds must appear unchanged in the plan."""
    plan = json.loads((OUT / "plan.json").read_text(encoding="utf-8"))
    a = plan["arms"]["A_v3_internal_0_4"]
    c = plan["arms"]["C_v3_no_forced_resolution"]
    assert (a["v3_internal_gamma"], a["label_fallback_gamma"], a["gamma_ext"]) == (0.4, 0.4, 0.5)
    assert (c["v3_internal_gamma"], c["label_fallback_gamma"], c["gamma_ext"]) == (0.8, 0.4, 0.5)
    assert plan["panel"]["gamma_ext"] == 0.5
    assert plan["runs_per_arm"] == 1

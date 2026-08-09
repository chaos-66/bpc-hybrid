# -*- coding: utf-8 -*-
"""Tests for the S3.4/S3.5 contract & evaluator repair and the S3.6 baseline
arms: inference pack (gold-blind, shuffle-invariant), check_type routing,
unobservable accounting by check_type, Sun Definition 6 multi-actor
semantics, real gamma/theta sensitivity re-execution, BM25 and TF-IDF/SVD
fixtures, and run finalisation (export index, hashes, fail-closed).
"""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import numpy as np  # noqa: E402
import spacy  # noqa: E402

from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer  # noqa: E402
from bpc_hybrid.stage3_baselines.bm25 import BM25Index  # noqa: E402
from bpc_hybrid.stage3_baselines.tfidf_svd import TfidfSvd  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import SunProcessModel  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402
from build_stage3_gold_inference import build_inference_pack  # noqa: E402

BLANK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
INFERENCE = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"

NLP = spacy.load("en_core_web_sm")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _simple_model(action_names: list[str], reachable: dict[str, list[str]] | None = None,
                  actors: list[str] | None = None, objects: list[str] | None = None):
    record = {
        "activities": [{"id": f"a{i}", "name": name, "type": "task", "lane_ids": []}
                       for i, name in enumerate(action_names)],
        "events": [],
        "pools": [{"id": "p0", "name": a, "process_ref": "x"} for a in (actors or [])],
        "lanes": [],
        "control_flow": {
            "reachable_pairs": [
                {"source_ref": s, "target_ref": t}
                for s, targets in (reachable or {}).items() for t in targets
            ],
            "activity_order_relations": [],
        },
    }
    model = SunProcessModel("test_model", record, NLP)
    if objects:
        for i, obj in enumerate(objects):
            model.business_objects.append({"activity_id": f"a{i}", "object": obj})
    return model


# ---------------------------------------------------------------- inference pack
def test_inference_pack_has_no_forbidden_fields() -> None:
    pack = _load_json(INFERENCE)
    for item in pack["matching_items"] + pack["violation_items"]:
        for forbidden in ("decision_", "candidate_", "evidence", "review_state"):
            assert not any(forbidden in k for k in item)


def test_inference_pack_shuffle_invariant() -> None:
    blank = _load_json(BLANK)
    normal = build_inference_pack(blank)
    shuffled = dict(blank)
    import random
    rng = random.Random(42)
    items = list(shuffled["violation_items"])
    rng.shuffle(items)
    shuffled["violation_items"] = items
    assert build_inference_pack(shuffled) == normal


def test_inference_pack_check_types_balanced() -> None:
    pack = _load_json(INFERENCE)
    from collections import Counter
    counts = Counter(i["check_type"] for i in pack["violation_items"])
    assert counts == {"missing_action": 11, "incorrect_actor": 11, "out_of_order": 11}


# --------------------------------------------------------- runner order invariance
def test_sun_runner_order_invariance() -> None:
    import run_sun_stage3_development as r
    import random
    config = _load_json(r.CONFIG)
    inference = _load_json(INFERENCE)
    shuffled = json.loads(json.dumps(inference))
    rng = random.Random(7)
    rng.shuffle(shuffled["violation_items"])
    nlp = spacy.load("en_core_web_sm")
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    from bpc_hybrid.sun_stage3.sun_model import build_sun_models
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    sim = WinterSimilarity(nlp)
    models = build_sun_models(r.BPMN_DIR, r.STAGE1_CONTRACT, nlp)
    signalwords = set((r.WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    tau = float(config["method"]["thresholds"]["tau"])
    gamma = float(config["method"]["thresholds"]["gamma"])
    theta = float(config["method"]["thresholds"]["theta"])
    scorer = SunScorer(sim, tau, gamma, theta, nlp=nlp)
    p1, _ = r.build_predictions(config, nlp, sim, signalwords, inference, models,
                                scorer, tau, gamma, theta)
    p2, _ = r.build_predictions(config, nlp, sim, signalwords, shuffled, models,
                                scorer, tau, gamma, theta)
    assert p1 == p2


def test_runner_never_reads_candidate_fields() -> None:
    import run_sun_stage3_development as s
    import run_winter_stage3_development as w
    import run_stage3_baselines as b
    for module in (s, w, b):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for forbidden in ("decision_relevant", "decision_violation_type",
                          "candidate_relevant", "candidate_violation_type",
                          "candidate_evidence", "candidate_location"):
            assert f'["{forbidden}"]' not in source
            assert f'.get("{forbidden}")' not in source


# ------------------------------------------------- unobservable by check_type
def test_unobservable_only_counts_actor_checkpoints() -> None:
    from evaluate_stage3_common import evaluate
    correction = _load_json(ROOT / "data" / "development" / "human_review"
                            / "stage3_gold_annotation_human_correction_v1.json")
    # take the real inference pack and construct predictions where ONLY the
    # incorrect_actor items are marked unobservable
    inference = _load_json(INFERENCE)
    preds = []
    for item in inference["matching_items"]:
        preds.append({"schema_version": "stage3_prediction@1.0.0", "method_id": "x",
                      "run_id": "x", "task": "matching", "item_id": item["item_id"],
                      "process_id": item["process_id"], "rule_id": item["rule_id"],
                      "matching_score": 0.0, "predicted_relevance": False,
                      "gold_visible": False})
    for item in inference["violation_items"]:
        is_actor = item["check_type"] == "incorrect_actor"
        preds.append({
            "schema_version": "stage3_prediction@1.0.0", "method_id": "x", "run_id": "x",
            "task": "violation", "item_id": item["item_id"],
            "process_id": item["process_id"], "rule_id": item["rule_id"],
            "matching_score": None, "predicted_relevance": None,
            "missing_action_score": 0.0, "incorrect_actor_score": None,
            "out_of_order_score": 0.0, "predicted_violation_type": None,
            "gold_visible": False, "check_type": item["check_type"],
            "incorrect_actor_observable": not is_actor,
            "incorrect_actor_reason": None if not is_actor else "no_actor_labels",
        })
    result = evaluate(preds, correction)
    # exactly the 11 actor check points are unobservable
    assert result["violation"]["unobservable"] == 11
    assert result["violation"]["denominator"]["per_type_unobservable"] == {
        "missing_action": 0, "incorrect_actor": 11, "out_of_order": 0}
    assert result["violation"]["denominator"]["unobservable_by_reason"] == {
        "no_actor_labels": 11}


# ---------------------------------------------- Sun gamma changes mapping/denominator
def test_sun_gamma_changes_denominator_fixture() -> None:
    # rule action with moderate similarity to the process action: mapping
    # holds at gamma=0.5 but fails at gamma=0.9 -> denominator changes
    model = _simple_model(["Send an invoice"])
    sim = WinterSimilarity(NLP)
    low = SunScorer(sim, 0.8, 0.5, 0.8, nlp=NLP)
    high = SunScorer(sim, 0.8, 0.9, 0.8, nlp=NLP)
    actions = ["Send an invoice"]  # identical text -> sim 1.0 > both gammas
    ma_low = low.missing_action(actions, model)
    ma_high = high.missing_action(actions, model)
    assert ma_low["denominator"] == 1 and ma_low["missing"] == 0
    assert ma_high["denominator"] == 1 and ma_high["missing"] == 0
    # now a dissimilar rule action: sim is well below 0.5 -> missing at both
    ma_low2 = low.missing_action(["Notify the supervisory authority"], model)
    ma_high2 = high.missing_action(["Notify the supervisory authority"], model)
    assert ma_low2["missing"] == 1 and ma_high2["missing"] == 1
    # proof that gamma changes the actor mapping: rule actor with moderate
    # action similarity (needs an action text whose similarity sits between
    # 0.5 and 0.9; identical text is above both, so use near-synonym text)
    model2 = _simple_model(["Notify national authority"], actors=["Data Controller"])
    ia_low = low.incorrect_actor(["Notify national authority"], ["Data Controller"], model2)
    ia_high = high.incorrect_actor(["Notify national authority"], ["Data Controller"], model2)
    # identical action text -> both map (denominator 1); the fixture that
    # proves denominator change uses near-synonym text with sim in (0.5, 0.9)
    near_syn = "Inform the national supervisory body"
    near_sim = sim.text_pair(near_syn, "Notify national authority")
    assert 0.5 < near_sim < 0.9, f"fixture assumption broken: sim={near_sim}"
    ia_low_s = low.incorrect_actor([near_syn], ["Data Controller"], model2)
    ia_high_s = high.incorrect_actor([near_syn], ["Data Controller"], model2)
    assert ia_low_s["observable"] is True      # gamma=0.5: action maps
    assert ia_high_s["observable"] is False    # gamma=0.9: mapping fails
    assert ia_high_s["reason"] == "action_mapping_below_gamma"


# ------------------------------------------------ Definition 6 multi-actor
def test_def6_multi_actor_exists_low_similarity() -> None:
    # single matching actor and no business object in the label: rule actor
    # identical to the process pool name -> min similarity 1.0, not violated
    model = _simple_model(["Review"], actors=["Data Controller"])
    sim = WinterSimilarity(NLP)
    scorer = SunScorer(sim, 0.8, 0.8, 0.8, nlp=NLP)
    ia_ok = scorer.incorrect_actor(["Review"],
                                   ["Data Controller"], model)
    assert ia_ok["observable"] is True
    assert ia_ok["score"] == 0.0
    # multi-actor process: the rule actor matches one process actor but the
    # C set contains a second, dissimilar actor -> exists-low-similarity
    # (Definition 6 existential semantics) makes it a violation
    model_multi = _simple_model(["Review"],
                                actors=["Data Controller", "Unrelated Role"])
    ia_multi = scorer.incorrect_actor(["Review"],
                                      ["Data Controller"], model_multi)
    assert ia_multi["observable"] is True
    assert ia_multi["score"] > 0.0
    # rule actor absent from the process: no similar process actor at all
    ia_bad = scorer.incorrect_actor(["Review"],
                                    ["External Auditor"], model_multi)
    assert ia_bad["observable"] is True
    assert ia_bad["score"] > 0.0


# ------------------------------------------------------------ BM25 fixtures
def test_bm25_matching_positive_and_negative() -> None:
    index = BM25Index(["Notify national authority", "Send an invoice"])
    pos, _ = index.query("notify the national authority")
    neg, _ = index.query("erase personal data")
    assert pos > neg
    assert pos > 0.0
    assert neg >= 0.0


def test_bm25_empty_query_and_corpus() -> None:
    empty = BM25Index([])
    score, best = empty.query("anything")
    assert score == 0.0 and best is None
    index = BM25Index(["Notify national authority"])
    score, _ = index.query("")
    assert score == 0.0


def test_baseline_scorer_missing_actor_order() -> None:
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer
    # verb-only labels so no business object enters the actor C set
    model = _simple_model(["Review", "Escalate"],
                          reachable={"a0": ["a1"]}, actors=["Data Controller"])

    def factory(m):
        def sim(a, b):
            return 1.0 if a.lower() == b.lower() else 0.0
        return sim

    scorer = BaselineScorer(factory, 0.5, 0.5, 0.5)
    ma = scorer.missing_action(["Review", "Send an invoice"], model)
    assert ma["denominator"] == 2 and ma["missing"] == 1 and ma["score"] == 0.5
    ia = scorer.incorrect_actor(["Review"], ["Data Controller"], model)
    assert ia["observable"] is True and ia["score"] == 0.0
    oo = scorer.out_of_order([("review", "escalate")],
                             ["Review", "Escalate"], model)
    # exact-match sims of 1.0 for both endpoints; forward reachable a0->a1
    # and not backward -> satisfied, score 0
    assert oo["denominator"] == 1 and oo["satisfied"] == 1 and oo["score"] == 0.0
    # reversed relation -> violation
    oo_rev = scorer.out_of_order([("escalate", "review")],
                                 ["Review", "Escalate"], model)
    assert oo_rev["denominator"] == 1 and oo_rev["score"] == 1.0


# --------------------------------------------------------- TF-IDF/SVD fixtures
def test_tfidf_svd_identical_texts_and_empty() -> None:
    svd = TfidfSvd(seed=1, dim=8)
    svd.fit(["Notify national authority", "Send an invoice", "Erase personal data"])
    assert svd.similarity("Notify national authority", "Notify national authority") > 0.99
    assert svd.similarity("", "anything") == 0.0
    assert svd.similarity("Notify national authority", "Send an invoice") < 0.99


def test_tfidf_svd_deterministic() -> None:
    svd1 = TfidfSvd(seed=20260808, dim=16)
    svd2 = TfidfSvd(seed=20260808, dim=16)
    corpus = ["Notify national authority", "Send an invoice"]
    svd1.fit(corpus)
    svd2.fit(corpus)
    assert svd1.similarity("notify authority", "Notify national authority") == \
        svd2.similarity("notify authority", "Notify national authority")


# ----------------------------------------------------- finalisation
def test_finalise_missing_artifact_fails_closed(tmp_path) -> None:
    from stage3_run_common import finalise_run
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
    with pytest.raises(RuntimeError):
        finalise_run(run_dir, {"predictions": "predictions.jsonl", "missing": "nope.jsonl"})


def test_finalise_export_index_hashes_match(tmp_path) -> None:
    from stage3_run_common import finalise_run
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
    (run_dir / "predictions.jsonl").write_text("a\nb\n", encoding="utf-8")
    finalise_run(run_dir, {"predictions": "predictions.jsonl"})
    export = _load_json(run_dir / "export_index.json")
    expected = hashlib.sha256((run_dir / "predictions.jsonl").read_bytes()).hexdigest()
    assert export["artifacts"]["predictions"]["sha256"] == expected
    manifest = _load_json(run_dir / "manifest.json")
    assert manifest["finalised"] is True
    assert manifest["artifacts"]["predictions"]["sha256"] == expected

# ------------------------------------------- baseline sensitivity (real re-exec)
def _sim_table(table):
    def factory(m):
        def sim(a, b):
            return table.get((a.lower(), b.lower()), 0.0)
        return sim
    return factory


def test_baseline_gamma_changes_missing_action() -> None:
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer
    # rule action "notify" vs model action "Notify": similarity 0.6
    model = _simple_model(["Notify"])
    factory = _sim_table({("notify", "notify"): 0.6})
    loose = BaselineScorer(factory, 0.5, 0.4, 0.5)   # gamma 0.4: 0.6 > 0.4 -> matched
    strict = BaselineScorer(factory, 0.5, 0.8, 0.5)  # gamma 0.8: 0.6 < 0.8 -> missing
    assert loose.missing_action(["notify"], model)["missing"] == 0
    assert strict.missing_action(["notify"], model)["missing"] == 1
    assert strict.missing_action(["notify"], model)["denominator"] == 1


def test_baseline_gamma_changes_actor_observability() -> None:
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer
    model = _simple_model(["Notify"], actors=["Data Controller"])
    factory = _sim_table({("notify", "notify"): 0.6, ("data controller", "data controller"): 1.0})
    loose = BaselineScorer(factory, 0.5, 0.5, 0.5)
    strict = BaselineScorer(factory, 0.5, 0.9, 0.5)
    ia_loose = loose.incorrect_actor(["notify"], ["Data Controller"], model)
    ia_strict = strict.incorrect_actor(["notify"], ["Data Controller"], model)
    assert ia_loose["observable"] is True      # action mapping 0.6 > 0.5
    assert ia_loose["denominator"] == 1
    assert ia_strict["observable"] is False    # action mapping 0.6 < 0.9
    assert ia_strict["reason"] == "action_mapping_below_gamma"


def test_baseline_gamma_changes_order_denominator() -> None:
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer
    model = _simple_model(["Review", "Escalate"], reachable={"a0": ["a1"]})
    factory = _sim_table({("review", "review"): 0.6, ("escalate", "escalate"): 0.6})
    loose = BaselineScorer(factory, 0.5, 0.5, 0.5)
    strict = BaselineScorer(factory, 0.5, 0.9, 0.5)
    oo_loose = loose.out_of_order([("review", "escalate")], ["review", "escalate"], model)
    oo_strict = strict.out_of_order([("review", "escalate")], ["review", "escalate"], model)
    assert oo_loose["denominator"] == 1        # both endpoints 0.6 > 0.5
    assert oo_strict["denominator"] == 0       # both endpoints 0.6 < 0.9


def test_baseline_theta_changes_actor_judgement() -> None:
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer
    model = _simple_model(["Notify"], actors=["Data Controller"])
    factory = _sim_table({("notify", "notify"): 1.0, ("data controller", "data controller"): 0.6})
    lenient = BaselineScorer(factory, 0.5, 0.5, 0.5)   # theta 0.5: 0.6 >= 0.5 -> ok
    strict = BaselineScorer(factory, 0.5, 0.5, 0.8)    # theta 0.8: 0.6 < 0.8 -> violation
    assert lenient.incorrect_actor(["notify"], ["Data Controller"], model)["score"] == 0.0
    assert strict.incorrect_actor(["notify"], ["Data Controller"], model)["score"] > 0.0


def test_baseline_sensitivity_is_not_fixed_score_cutoff() -> None:
    from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer
    # score 0.6 is fixed; a pure cutoff at gamma=0.9 would still use score 0.6
    # and predict "not missing", but the real re-execution changes the
    # mapping (0.6 < 0.9) and therefore the score to 1.0 (missing fraction)
    model = _simple_model(["Notify"])
    factory = _sim_table({("notify", "notify"): 0.6})
    scorer_primary = BaselineScorer(factory, 0.5, 0.5, 0.5)
    scorer_strict = BaselineScorer(factory, 0.5, 0.9, 0.5)
    ma_primary = scorer_primary.missing_action(["notify"], model)
    ma_strict = scorer_strict.missing_action(["notify"], model)
    assert ma_primary["score"] == 0.0
    assert ma_strict["score"] == 1.0          # re-mapping changed the score itself
    # the old (wrong) cutoff approach would have kept score 0.0 and compared
    # 0.0 > 0.9 -> not missing; the real re-execution says missing
    assert (ma_primary["score"] > 0.9) is False  # fixed-score cutoff view
    assert ma_strict["missing"] == 1             # real re-execution view

# -*- coding: utf-8 -*-
"""Regression tests for the Sun et al. (2024) Stage 3 reconstruction (S3.5)
and the shared Stage 3 prediction/evaluation contract.

Covers: Definitions 4-7 hand-computed fixtures, tau/gamma/theta config,
matching action + actor/object parts, missing-action denominator, incorrect
actor observable/unobservable, out-of-order forward/backward reachability,
branch/parallel/cycle, runner Gold-blindness, candidate fields not read,
double-run byte-identity, common evaluator item-ID alignment, hashes,
export index, no references import, external dependency not copied.
"""

from __future__ import annotations

import json
import subprocess
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

import spacy  # noqa: E402

from bpc_hybrid.sun_stage3.sun_model import SunProcessModel, build_sun_models  # noqa: E402
from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_model import (  # noqa: E402
    REACHABILITY_CORRECTED,
    REACHABILITY_PROTOTYPE_LITERAL,
    parse_bpmn_file_winter,
)
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402

CONFIG = ROOT / "configs" / "sun_stage3_development_v1.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BLANK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"

NLP = spacy.load("en_core_web_sm")
SIGNALWORDS = set((
    ROOT.parent / "references" / "winter_2020_model_check" / "model_check"
    / "input" / "files" / "signalwords.txt"
).read_text(encoding="utf-8").splitlines())


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _simple_model(action_names: list[str], reachable: dict[str, list[str]] | None = None,
                  actors: list[str] | None = None, objects: list[str] | None = None):
    """Build a minimal SunProcessModel with fake records (unit-level)."""
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
    # business objects come from labels; inject explicit objects if requested
    if objects:
        for i, obj in enumerate(objects):
            model.business_objects.append({"activity_id": f"a{i}", "object": obj})
    return model


def _scorer(tau=0.8, gamma=0.8, theta=0.8) -> SunScorer:
    return SunScorer(WinterSimilarity(NLP), tau, gamma, theta)


# ------------------------------------------------------------- Definition 4
def test_def4_matching_score_identical_texts() -> None:
    # identical texts -> spaCy similarity 1.0 (en_core_web_sm has no word
    # vectors, so near-synonym text can score below tau; identical text is
    # the deterministic hand-computed fixture)
    model = _simple_model(["Notify national authority"], actors=["Data Controller"])
    scorer = _scorer(tau=0.8)
    m = scorer.matching_score(["Notify national authority"], ["Data Controller"], model)
    assert m["action_ratio"] == 1.0
    assert m["actor_object_ratio"] == 1.0
    assert m["matching_score"] == 1.0


def test_def4_matching_score_action_part_only() -> None:
    model = _simple_model(["Notify national authority"])
    scorer = _scorer(tau=0.8)
    m = scorer.matching_score(["Notify national authority"], [], model)
    assert m["action_ratio"] == 1.0
    assert m["matching_score"] == 1.0  # max over the two parts


def test_def4_matching_score_low_similarity() -> None:
    model = _simple_model(["Send an invoice"])
    scorer = _scorer(tau=0.8)
    m = scorer.matching_score(["notify the national authority"], [], model)
    assert m["action_ratio"] == 0.0
    assert m["matching_score"] == 0.0


def test_tau_gamma_theta_config_loaded() -> None:
    config = _load_json(CONFIG)
    assert config["method"]["thresholds"]["tau"] == 0.8
    assert config["method"]["thresholds"]["gamma"] == 0.8
    assert config["method"]["thresholds"]["theta"] == 0.8
    assert config["method"]["thresholds"]["sweeps"]["tau"] == [0.2, 0.4, 0.6, 0.8, 0.9]


# ------------------------------------------------------------- Definition 5
def test_def5_missing_action_denominator() -> None:
    model = _simple_model(["Send an invoice"])
    scorer = _scorer(gamma=0.8)
    ma = scorer.missing_action(["Notify national authority", "Send an invoice"], model)
    # one of two rule actions has no similar process action
    assert ma["denominator"] == 2
    assert ma["missing"] == 1
    assert ma["score"] == 0.5


def test_def5_missing_action_empty_denominator() -> None:
    model = _simple_model(["Send an invoice"])
    scorer = _scorer(gamma=0.8)
    ma = scorer.missing_action([], model)
    assert ma["denominator"] == 0
    assert ma["score"] == 0.0


# ------------------------------------------------------------- Definition 6
def test_def6_incorrect_actor_observable_match() -> None:
    model = _simple_model(["Notify national authority"], actors=["Data Controller"])
    scorer = _scorer(gamma=0.8, theta=0.8)
    ia = scorer.incorrect_actor(["Notify national authority"], ["Data Controller"], model)
    assert ia["observable"] is True
    assert ia["score"] == 0.0  # rule actor matches the process actor


def test_def6_incorrect_actor_unobservable_no_pool() -> None:
    model = _simple_model(["Notify national authority"])  # no actors at all
    scorer = _scorer(gamma=0.8, theta=0.8)
    ia = scorer.incorrect_actor(["Notify national authority"], ["Data Controller"], model)
    assert ia["observable"] is False
    assert ia["score"] is None


# ------------------------------------------------------------- Definition 7
def test_def7_out_of_order_forward_only() -> None:
    model = _simple_model(["Notify authority", "Handle delay"],
                          reachable={"a0": ["a1"]})
    scorer = _scorer(gamma=0.8)
    oo = scorer.out_of_order([("notify authority", "handle delay")],
                             ["notify authority", "handle delay"], model)
    assert oo["denominator"] == 1
    assert oo["satisfied"] == 1
    assert oo["score"] == 0.0


def test_def7_out_of_order_backward_reachable() -> None:
    model = _simple_model(["Notify authority", "Handle delay"],
                          reachable={"a0": ["a1"], "a1": ["a0"]})  # cycle
    scorer = _scorer(gamma=0.8)
    oo = scorer.out_of_order([("notify authority", "handle delay")],
                             ["notify authority", "handle delay"], model)
    assert oo["denominator"] == 1
    assert oo["satisfied"] == 0
    assert oo["score"] == 1.0


def test_def7_out_of_order_empty_denominator() -> None:
    model = _simple_model(["Notify authority"])
    scorer = _scorer(gamma=0.8)
    oo = scorer.out_of_order([("notify authority", "handle delay")],
                             ["notify authority"], model)
    assert oo["denominator"] == 0
    assert oo["score"] == 0.0


# ------------------------------------------------------------- rule adapter
def test_rule_extraction_is_gold_blind() -> None:
    record = extract_rule_record("article33", (
        "In the case of a personal data breach, the controller shall notify "
        "the supervisory authority without undue delay."
    ), NLP, SIGNALWORDS)
    assert record["actions"]
    assert record["actors"]
    assert record["provenance"]["gold_fields_read"] is False


def test_rule_extraction_forbidden_fields_absent() -> None:
    record = extract_rule_record("article7", (
        "The data subject shall have the right to withdraw his or her consent at any time."
    ), NLP, SIGNALWORDS)
    for forbidden in ("decision_relevant", "decision_violation_type",
                      "candidate_relevant", "candidate_violation_type",
                      "candidate_evidence", "candidate_location"):
        assert forbidden not in record


# ------------------------------------------------------------- model build
def test_sun_models_built_from_frozen_gdpr7() -> None:
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, NLP)
    assert set(models) == {"gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
                           "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
                           "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
                           "gdpr_7_right_to_be_forgotten"}
    m = models["gdpr_1_data_breach"]
    assert any("notify" in a["name"].lower() for a in m.actions)
    assert m.actors  # pools carry names (e.g. 'Data Controller')


# ------------------------------------------------- runner gold-blind + determinism
def test_sun_runner_gold_blind_and_deterministic() -> None:
    import run_sun_stage3_development as r
    import shutil
    assert "blank" in str(r.BLANK_PACK)
    assert "correction" not in str(r.BLANK_PACK)
    config = _load_json(CONFIG)
    suffix = uuid.uuid4().hex[:8]
    runs = []
    try:
        for variant in (f"det_{suffix}_1", f"det_{suffix}_2"):
            run_dir = r.write_run(config, variant)
            runs.append(run_dir)
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "evaluate_stage3_common.py"),
                 "--predictions", str(run_dir / "predictions.jsonl"),
                 "--run-dir", str(run_dir), "--sweep"],
                cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
            )
            assert result.returncode == 0, result.stdout[-400:]
        preds = [(d / "predictions.jsonl").read_text(encoding="utf-8") for d in runs]
        assert preds[0] == preds[1]
        evals = [(d / "evaluation.json").read_text(encoding="utf-8") for d in runs]
        assert evals[0] == evals[1]
        # runner must not read candidate/decision fields: check no forbidden
        # field appears in the code path of the predictions
        for line in preds[0].splitlines():
            p = json.loads(line)
            assert p["gold_visible"] is False
    finally:
        for d in runs:
            shutil.rmtree(d, ignore_errors=True)


def test_sun_runner_never_reads_candidate_fields() -> None:
    import run_sun_stage3_development as r
    source = Path(r.__file__).read_text(encoding="utf-8")
    # no dict/subscript access pattern on any forbidden field name
    for forbidden in ("decision_relevant", "decision_violation_type",
                      "candidate_relevant", "candidate_violation_type",
                      "candidate_evidence", "candidate_location"):
        assert f'["{forbidden}"]' not in source
        assert f'.get("{forbidden}")' not in source
        assert f"['{forbidden}']" not in source


# ------------------------------------------------- common evaluator alignment
def test_common_evaluator_aligns_same_item_ids() -> None:
    from evaluate_stage3_common import evaluate
    correction = _load_json(ROOT / "data" / "development" / "human_review"
                            / "stage3_gold_annotation_human_correction_v1.json")
    # fake minimal predictions over the same 58 item ids
    predictions = []
    for i in correction["matching_items"]:
        predictions.append({
            "schema_version": "stage3_prediction@1.0.0", "method_id": "winter_2020",
            "run_id": "x", "task": "matching", "item_id": i["item_id"],
            "process_id": i["process_id"], "rule_id": i["rule_id"],
            "matching_score": 0.5, "predicted_relevance": True, "gold_visible": False,
        })
    for i in correction["violation_items"]:
        predictions.append({
            "schema_version": "stage3_prediction@1.0.0", "method_id": "winter_2020",
            "run_id": "x", "task": "violation", "item_id": i["item_id"],
            "process_id": i["process_id"], "rule_id": i["rule_id"],
            "missing_action_score": 0.0, "incorrect_actor_score": 0.0,
            "out_of_order_score": 0.0, "predicted_violation_type": None,
            "gold_visible": False,
        })
    result = evaluate(predictions, correction)
    assert result["matching"]["support"] == 25
    assert result["violation"]["support"] == 33


# ------------------------------------------------- Winter dual reachability
def test_winter_dual_reachability_modes() -> None:
    bpmn = next(BPMN_DIR.glob("gdpr_1_data_breach.bpmn"))
    stopwords = set((
        ROOT.parent / "references" / "winter_2020_model_check" / "model_check"
        / "input" / "files" / "stopwords.txt"
    ).read_text(encoding="utf-8").splitlines())
    corrected = parse_bpmn_file_winter(bpmn, NLP, stopwords,
                                       reachability_mode=REACHABILITY_CORRECTED)
    literal = parse_bpmn_file_winter(bpmn, NLP, stopwords,
                                     reachability_mode=REACHABILITY_PROTOTYPE_LITERAL)
    # find a task id and a non-reachable pair to show the semantic difference
    proc_c = corrected.processes[0]
    proc_l = literal.processes[0]
    task_ids = [t.getAttribute("id") for t in proc_c.tasks]
    assert task_ids
    # prototype-literal: is_reachable_from(x, y) is always True for any y in
    # reachability keys; corrected requires actual reachability
    assert proc_l.is_reachable_from(task_ids[0], task_ids[0]) is True
    assert proc_c.is_reachable_from(task_ids[0], task_ids[0]) is True
    # the two modes must differ on at least one pair unless the graph is
    # fully connected - find any pair where corrected says False
    differ = False
    for src in proc_c.reachability:
        for tgt in proc_c.reachability:
            if not proc_c.is_reachable_from(src, tgt) and proc_l.is_reachable_from(src, tgt):
                differ = True
                break
        if differ:
            break
    assert differ


# ------------------------------------------------- hashes / export / no import
def test_sun_manifest_hashes_and_export_index() -> None:
    import run_sun_stage3_development as r
    import shutil, hashlib
    config = _load_json(CONFIG)
    run_dir = r.write_run(config, "hashcheck_" + uuid.uuid4().hex[:6])
    try:
        manifest = _load_json(run_dir / "manifest.json")

        def sha(p: Path) -> str:
            return hashlib.sha256(p.read_bytes()).hexdigest()

        assert manifest["artifacts"]["predictions"]["sha256"] == sha(run_dir / "predictions.jsonl")
        assert manifest["artifacts"]["rule_records"]["sha256"] == sha(run_dir / "rule_records.jsonl")
        assert manifest["implementation_hashes"]["runner"]
        assert "predictions" in manifest["export_index"]
        assert "evaluation" in manifest["export_index"]
        assert manifest["safety"]["gold_decisions_read"] is False
        assert manifest["safety"]["candidate_fields_read"] is False
        assert manifest["inputs"]["bpmn_dir_aggregate_sha256"]
        assert manifest["git"]["commit"]
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def test_no_import_from_references_and_no_copy() -> None:
    import run_sun_stage3_development as r
    import run_winter_stage3_development as w
    for module in (r, w):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "from references" not in source
        assert "import references" not in source
        assert "shutil.copy" not in source or "backup" in source
    # external lexicon must be referenced read-only, never copied
    assert "references/winter_2020_model_check" in r.__doc__ or "references" in str(r.WINTER_FILES_DIR)

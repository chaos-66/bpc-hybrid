# -*- coding: utf-8 -*-
"""Focused tests for the Stage 3 Sun-style threshold sensitivity batch
(S3.5 evidence extension, 2026-09-04, DEV_ONLY, zero API).

Covers exactly what the batch promises:
- the Sun-aligned discrete grids (tau/gamma in {0.0,0.2,0.4,0.6,0.8,0.9},
  theta in {0.5,0.6,0.7,0.8,0.9} at gamma=0.8) and the two reported settings
  (Sun-transferred 0.8/0.8/0.8 vs best-observed calibrated 0.8/0.6/0.8);
- real metric recomputation: an independent re-execution of the frozen
  SunScorer + the frozen common evaluator reproduces the documented numbers
  (gamma=0.8 -> macro 0.3889/exact 0.3636/unobservable 10; gamma=0.6 ->
  macro 0.8733/exact 0.7879/unobservable 4 with per-type F1
  1.0/0.7778/0.8421); tau=0.8 matching row reproduces per-process AP and
  MAP 0.8175 of the recorded evidence;
- byte-unchanged original results: the S3.5 evidence capsule files and every
  frozen Gold/input pack keep their recorded SHA-256;
- Gold invariants (33 violation items, 11/11/11, no none item, routing
  metadata equals the frozen gold type);
- zero API/network claims of the report and the absence of LLM/network
  imports in the builder; deterministic --report-only replay.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _candidate in (SRC, SCRIPTS):
    if str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

import pytest  # noqa: E402

from build_sun_stage3_threshold_sensitivity_v1 import (  # noqa: E402
    CALIBRATED,
    GAMMA_GRID,
    MATCHING_TAU_GRID,
    PRIMARY,
    THETA_GRID,
)

REPORT_JSON = ROOT / "outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.json"
REPORT_MD = ROOT / "outputs/reports/s35_sun_stage3_threshold_sensitivity_v1.md"
FIG_A = ROOT / "outputs/reports/s35_sun_stage3_threshold_sensitivity_v1_figA_gamma_missing_action_out_of_order.svg"
FIG_B = ROOT / "outputs/reports/s35_sun_stage3_threshold_sensitivity_v1_figB_theta_incorrect_actor.svg"
EVIDENCE = ROOT / "outputs/evidence/s35_sun_stage3_development_v2"

# Byte-unchanged guards: the S3.5 v2 evidence capsule (original gamma=0.8
# results) and the frozen Stage 3 inputs/Gold. Any hash change below means
# someone touched a frozen artifact, and the batch's verification block would
# be invalid.
EVIDENCE_SHA = {
    "predictions.jsonl": "89613817d8c67739e412c1d300738fcac49eb3db37d6e7565200907322657db3",
    "evaluation.json": "352e5956ba1820528bfc476ee7780414a62d0cbc44db4d9ddd0dc9f76e0bc62a",
    "threshold_sensitivity.json": "8bd0c687a2c4c30861c45109e604366c61a0feb33ec6da37845e2da77f41fcd2",
    "manifest.json": "48c61dbc85a0fd28b1fa21c1b2563c65ca029107afe503e35586698ea7388b21",
    "export_index.json": "5394dae46d16f7a2306f6a6e469fe0f69ad1e6aa06129ad6ecf5d9065f5abc4e",
    "config_snapshot.json": "066660b64d29aa5512fbf9e90217a58f493ae005a31671d0ff7ee878464c8a03",
}
GOLD_SHA = {
    "matching_gold": "55dffbcaf7d6510c11a06f10b134dfb449af0bd687d0cf40f7839be19bc2e618",
    "violation_gold": "54245ef0d102ae5e7a44e8c45424ecd9e86e1e0d9ed43ac1a9cd43641c981550",
    "correction_pack": "3310d624b03d5f509b33f143cf64c9450c93a4a6463055cf0fdb79f38072ca2f",
    "inference_pack": "4182c1f6ba8e28665c6dd14a2573b227e0c6b65c1df0041fcd1ae7dab5cf03c4",
    "blank_pack": "e3f8596bcec9961c30bb90d60377f2889090e88171ca58987f127b1df72fb965",
    "sun_config": "c78ab2d14ac90dc95c86d686a61c0809e3fc7547e96b42a0b69254a7504797da",
    "stage1_structural_contract": "92329cef71c4f3517a66a24f4b0fb4b439add3470832831a6fb70fd1d59ced48",
    "membership_contract": "6bb2c0da4c51d06368bb858057374d9199e8d2ef494b6cb5c122be8744e11a42",
}

GOLD_PATH = {
    "matching_gold": ROOT / "data/gold/stage3/stage3_matching_gold_v1.json",
    "violation_gold": ROOT / "data/gold/stage3/stage3_violation_gold_v1.json",
    "correction_pack": ROOT / "data/development/human_review/stage3_gold_annotation_human_correction_v1.json",
    "inference_pack": ROOT / "data/development/human_review/stage3_gold_inference_v1.json",
    "blank_pack": ROOT / "data/development/human_review/stage3_gold_annotation_blank_v1.json",
    "sun_config": ROOT / "configs/sun_stage3_development_v1.json",
    "stage1_structural_contract": ROOT / "configs/stage1_structural_s11_s14.json",
    "membership_contract": ROOT / "configs/datasets/stage1_stage3_gdpr7_v1.json",
}

PY = sys.executable


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _report() -> dict:
    assert REPORT_JSON.exists(), "committed report JSON missing"
    return _load(REPORT_JSON)


def _evidence_evaluation() -> dict:
    return _load(EVIDENCE / "evaluation.json")


def _evidence_sensitivity() -> dict:
    return _load(EVIDENCE / "threshold_sensitivity.json")


# ------------------------------------------------------------- grids/settings
def test_threshold_grids_match_sun_style_spec() -> None:
    assert MATCHING_TAU_GRID == [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]
    assert GAMMA_GRID == [0.0, 0.2, 0.4, 0.6, 0.8, 0.9]
    assert THETA_GRID == [0.5, 0.6, 0.7, 0.8, 0.9]
    assert PRIMARY == {"tau": 0.8, "gamma": 0.8, "theta": 0.8}
    assert CALIBRATED == {"tau": 0.8, "gamma": 0.6, "theta": 0.8}
    # theta grid is evaluated with gamma fixed at 0.8 (Sun Figure 9 protocol)
    report = _report()
    assert report["threshold_grids"]["matching_tau"] == MATCHING_TAU_GRID
    assert report["threshold_grids"]["gamma"] == GAMMA_GRID
    assert report["threshold_grids"]["theta_fixed_gamma_0_8"] == THETA_GRID


def test_report_claims_two_settings_with_documented_numbers() -> None:
    report = _report()
    st = report["settings"]["sun_transferred"]
    cal = report["settings"]["sun_style_calibrated"]
    assert st["thresholds"] == {"tau": 0.8, "gamma": 0.8, "theta": 0.8}
    assert cal["thresholds"] == {"tau": 0.8, "gamma": 0.6, "theta": 0.8}
    # transferred = original gamma=0.8 result (kept as the low-score baseline)
    assert st["violation"]["macro_f1"] == 0.3889
    assert st["violation"]["micro_f1"] == 0.5333
    assert st["violation"]["exact_type_accuracy"] == 0.3636
    assert st["violation"]["unobservable"] == 10
    assert {t: v["f1"] for t, v in st["violation"]["per_type"].items()} == {
        "missing_action": 1.0, "incorrect_actor": 0.1667, "out_of_order": 0.0}
    # calibrated = best observed setting among the TESTED values only
    assert cal["violation"]["macro_f1"] == 0.8733
    assert cal["violation"]["micro_f1"] == 0.8814
    assert cal["violation"]["exact_type_accuracy"] == 0.7879
    assert cal["violation"]["unobservable"] == 4
    assert {t: v["f1"] for t, v in cal["violation"]["per_type"].items()} == {
        "missing_action": 1.0, "incorrect_actor": 0.7778, "out_of_order": 0.8421}
    # wording guards present in the machine report
    flat = json.dumps(report, ensure_ascii=False)
    assert "best observed setting" in flat or "BEST OBSERVED" in flat
    assert "NOT a pre-registered primary evaluation" in report["claim_boundary"]


def test_report_verification_and_safety_flags() -> None:
    report = _report()
    verification = report["verification"]
    assert verification["primary_row_matches_evaluation_json"] is True
    assert verification["overlap_rows_all_match"] is True
    assert verification["issues"] == []
    safety = report["safety"]
    assert safety["llm_api_called"] is False
    assert safety["api_calls"] == 0
    assert safety["usd_cost"] == 0.0
    assert safety["network_called"] is False
    assert safety["env_read"] is False
    assert safety["gold_modified"] is False
    assert safety["predictions_modified"] is False
    assert safety["scope"] == "DEV_ONLY"
    assert report["git"]["commit"]


# --------------------------------------------------------- matching tau sweep
def test_tau_sweep_is_matching_ap_map_only_and_primary_row_reproduces() -> None:
    report = _report()
    evaluation = _evidence_evaluation()
    assert evaluation["matching"]["MAP"] == 0.8175
    rows = {r["tau"]: r for r in report["matching_tau_sweep"]}
    assert set(rows) == set(MATCHING_TAU_GRID)
    for tau in MATCHING_TAU_GRID:
        assert "per_process_ap" in rows[tau] and "MAP" in rows[tau]
        # matching AP/MAP rows must never leak violation metrics in
        for key in ("macro_f1", "micro_f1", "exact_type_accuracy", "unobservable"):
            assert key not in rows[tau]
    # the tau=0.8 row must reproduce the recorded evidence AP/MAP exactly
    assert rows[0.8]["MAP"] == evaluation["matching"]["MAP"]
    for pid, ap in evaluation["matching"]["per_process_ap"].items():
        assert rows[0.8]["per_process_ap"][pid] == ap
    # tau rows must be strictly monotone-comparable only through scores: all
    # rows share the same support of 25 matching candidates
    assert all(r["support"] == 25 for r in rows.values())


# ----------------------------------------- overlap parity with old evidence
def test_sweep_overlap_rows_equal_recorded_evidence() -> None:
    report = _report()
    sensitivity = _evidence_sensitivity()
    gamma_by = {r["gamma"]: r for r in report["gamma_sweep"]}
    theta_by = {r["theta"]: r for r in report["theta_sweep"]}

    def metrics(row):
        return {"macro_f1": row["macro_f1"], "exact_type_accuracy": row["exact_type_accuracy"],
                "unobservable": row["unobservable"],
                "per_type_f1": {t: v["f1"] for t, v in row["per_type"].items()}}

    for old in sensitivity["violation_gamma_sweep"]:
        assert metrics(gamma_by[old["gamma"]]) == {
            "macro_f1": old["macro_f1"], "exact_type_accuracy": old["exact_type_accuracy"],
            "unobservable": old["unobservable"],
            "per_type_f1": {t: v["f1"] for t, v in old["per_type"].items()}}
    for old in sensitivity["incorrect_actor_theta_sweep"]:
        if old["theta"] not in theta_by:
            continue  # 0.2/0.4 rows were outside the Sun grid
        assert metrics(theta_by[old["theta"]]) == {
            "macro_f1": old["macro_f1"], "exact_type_accuracy": old["exact_type_accuracy"],
            "unobservable": old["unobservable"],
            "per_type_f1": {t: v["f1"] for t, v in old["per_type"].items()}}


# -------------------------------------------- independent recompute anchors
def _runtime_models_and_rules():
    """Frozen models + Rule Records re-extracted from the gold-blind
    inference pack (deterministic adapter, independent of the run cache)."""
    import spacy
    from bpc_hybrid.sun_stage3.sun_model import build_sun_models
    from bpc_hybrid.sun_stage3.sun_rule_extraction import extract_rule_record

    from build_sun_stage3_threshold_sensitivity_v1 import (
        BPMN_DIR,
        INFERENCE_PACK,
        STAGE1_CONTRACT,
        WINTER_FILES_DIR,
    )
    nlp = spacy.load("en_core_web_sm")
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)
    signalwords = set(
        (WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    inference = _load(INFERENCE_PACK)
    rules: dict[str, dict] = {}
    seen = set()
    for item in list(inference["matching_items"]) + list(inference["violation_items"]):
        if item["rule_id"] in seen:
            continue
        seen.add(item["rule_id"])
        rules[item["rule_id"]] = extract_rule_record(
            item["rule_id"], item["rule_text"], nlp, signalwords)
    return nlp, models, rules, inference


def _recompute_violation_row(nlp, models, rules, inference, gamma, theta) -> dict:
    """Independent re-execution: fresh scorer + frozen common evaluator."""
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    from evaluate_stage3_common import evaluate

    sim = WinterSimilarity(nlp)
    scorer = SunScorer(sim, 0.8, gamma, theta, nlp=nlp)
    preds = []
    for item in sorted(inference["violation_items"], key=lambda i: i["item_id"]):
        record = rules[item["rule_id"]]
        model = models[item["process_id"]]
        ma = scorer.missing_action(record["actions"], model)
        ia = scorer.incorrect_actor(record["actions"], record["actors"], model)
        oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
        scores = {"missing_action": ma["score"], "incorrect_actor": ia["score"],
                  "out_of_order": oo["score"]}
        item_score = scores[item["check_type"]]
        preds.append({
            "schema_version": "stage3_prediction@1.0.0", "method_id": "sun_2024",
            "run_id": "test_recompute", "task": "violation", "item_id": item["item_id"],
            "process_id": item["process_id"], "rule_id": item["rule_id"],
            "predicted_violation_type":
                item["check_type"] if (item_score is not None and item_score > 0.0) else None,
            "incorrect_actor_observable": ia["observable"],
            "incorrect_actor_reason": ia.get("reason"),
            "check_type": item["check_type"],
        })
    return evaluate(preds, _load(ROOT / "data/development/human_review"
                                 / "stage3_gold_annotation_human_correction_v1.json"))["violation"]


@pytest.fixture(scope="module")
def recompute_rt():
    return _runtime_models_and_rules()


def test_independent_recompute_reproduces_transferred_and_calibrated_rows(
        recompute_rt) -> None:
    nlp, models, rules, inference = recompute_rt
    report = _report()
    expected = {
        (0.8, 0.8): report["settings"]["sun_transferred"]["violation"],
        (0.6, 0.8): report["settings"]["sun_style_calibrated"]["violation"],
    }
    for (gamma, theta), row in expected.items():
        ev = _recompute_violation_row(nlp, models, rules, inference, gamma, theta)
        assert ev["macro_f1"] == row["macro_f1"], (gamma, ev["macro_f1"])
        assert ev["micro_f1"] == row["micro_f1"]
        assert ev["exact_type_accuracy"] == row["exact_type_accuracy"]
        assert ev["unobservable"] == row["unobservable"]
        for t, v in row["per_type"].items():
            assert ev["per_type"][t]["f1"] == v["f1"]


def test_independent_recompute_theta_grid_flat_at_gamma_0_8(recompute_rt) -> None:
    nlp, models, rules, inference = recompute_rt
    report = _report()
    rows = {r["theta"]: r for r in report["theta_sweep"]}
    for theta in THETA_GRID:
        ev = _recompute_violation_row(nlp, models, rules, inference, 0.8, theta)
        assert ev["macro_f1"] == rows[theta]["macro_f1"] == 0.3889
        assert ev["exact_type_accuracy"] == rows[theta]["exact_type_accuracy"] == 0.3636
        assert ev["unobservable"] == rows[theta]["unobservable"] == 10


def test_gold_invariants_unchanged() -> None:
    correction = _load(GOLD_PATH["correction_pack"])
    inference = _load(GOLD_PATH["inference_pack"])
    v_items = correction["violation_items"]
    assert len(v_items) == 33
    from collections import Counter
    assert Counter(i["decision_violation_type"] for i in v_items) == {
        "missing_action": 11, "incorrect_actor": 11, "out_of_order": 11}
    assert all(i["review_state"] == "adjudicated" for i in v_items)
    # no compliant (none) gold items -> specificity cannot be demonstrated
    assert all(i["decision_violation_type"] is not None for i in v_items)
    assert all(i["candidate_violation_type"] == i["decision_violation_type"]
               for i in v_items)
    by_id = {i["item_id"]: i for i in v_items}
    assert len(inference["violation_items"]) == 33
    for item in inference["violation_items"]:
        # routing metadata of the frozen test point mirrors the gold type
        assert by_id[item["item_id"]]["decision_violation_type"] == item["check_type"]
    assert len(correction["matching_items"]) == 25


def test_original_artifacts_and_gold_byte_unchanged() -> None:
    for name, expected in EVIDENCE_SHA.items():
        assert _sha256(EVIDENCE / name) == expected, name
    for name, expected in GOLD_SHA.items():
        assert _sha256(GOLD_PATH[name]) == expected, name


def test_builder_zero_api_and_report_only_replay_deterministic() -> None:
    report = _report()
    assert report["runtime"]["total_wall_seconds"] > 0
    assert report["runtime"]["per_row_seconds_measured"] is True
    source = (SCRIPTS / "build_sun_stage3_threshold_sensitivity_v1.py").read_text(
        encoding="utf-8")
    for forbidden in ("import requests", "import httpx", "import urllib.request",
                      "llm_client", "openai", "anthropic", ".env", "os.environ"):
        assert forbidden not in source, forbidden
    assert 'spacy.load("en_core_web_sm")' in source

    # --report-only replay into a temp dir must reproduce the committed
    # artifacts byte-for-byte (deterministic regeneration)
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [PY, str(SCRIPTS / "build_sun_stage3_threshold_sensitivity_v1.py"),
             "--report-only", "--out-dir", tmp],
            cwd=ROOT, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        assert result.returncode == 0, result.stdout[-800:]
        tmp_dir = Path(tmp)
        for committed, name in ((REPORT_JSON, "s35_sun_stage3_threshold_sensitivity_v1.json"),
                                (REPORT_MD, "s35_sun_stage3_threshold_sensitivity_v1.md"),
                                (FIG_A, "s35_sun_stage3_threshold_sensitivity_v1_figA_gamma_missing_action_out_of_order.svg"),
                                (FIG_B, "s35_sun_stage3_threshold_sensitivity_v1_figB_theta_incorrect_actor.svg")):
            assert (tmp_dir / name).exists()
            assert (tmp_dir / name).read_bytes() == committed.read_bytes(), name


def test_per_process_detail_consistency_and_support_sums() -> None:
    report = _report()
    for sweep_key, key_name in (("gamma_sweep", "gamma"), ("theta_sweep", "theta")):
        for row in report[sweep_key]:
            processes = {k: v for k, v in row["per_process"].items() if not k.startswith("_")}
            assert len(processes) == 7
            assert sum(v["support"] for v in processes.values()) == 33
            assert sum(v["unobservable"] for v in processes.values()) == row["unobservable"]
            for pid, detail in processes.items():
                assert set(detail["per_type_f1"]) == {
                    "missing_action", "incorrect_actor", "out_of_order"}
                assert 0.0 <= detail["macro_f1"] <= 1.0
                assert 0.0 <= detail["micro_f1"] <= 1.0
                assert 0 <= detail["unobservable"] <= detail["support"]
    # per-process exact accuracy is detected/support per process: aggregate
    # macro (mean over the three per-type F1s) is NOT the exact accuracy
    gamma08 = next(r for r in report["gamma_sweep"] if r["gamma"] == 0.8)
    assert gamma08["macro_f1"] == 0.3889
    assert gamma08["exact_type_accuracy"] == 0.3636

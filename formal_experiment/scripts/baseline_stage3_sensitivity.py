# -*- coding: utf-8 -*-
"""S3.6 baseline gamma/theta sensitivity with REAL scorer re-execution.

The BaselineScorer's gamma and theta are NOT pure cutoffs: gamma changes the
missing-action judgement, the incorrect-actor R set (action mapping above
gamma), and the out-of-order endpoint mapping / denominator; theta changes
the actor violation judgement. A sweep therefore must re-instantiate the
scorer and recompute mappings, R/C sets, denominators, observability, scores
and predictions for every (gamma, theta) combination. The text representations
(BM25 index / TF-IDF+SVD fit) and the Rule/Process Records and inference pack
stay fixed; matching tau remains a score cutoff over the fixed matching
scores. This script reads Gold only for evaluation (the runner/scorer never
read Gold). Diagnostic only: primary thresholds stay at the v1 fixed values
(0.5) and are never selected from the sweep.

Usage:
    python scripts/baseline_stage3_sensitivity.py --run-dir <baseline run dir> --arm bm25
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import spacy  # noqa: E402

from bpc_hybrid.stage3_baselines.baseline_stage3 import BaselineScorer  # noqa: E402
from bpc_hybrid.stage3_baselines.bm25 import BM25Index  # noqa: E402
from bpc_hybrid.stage3_baselines.tfidf_svd import TfidfSvd  # noqa: E402
from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from evaluate_stage3_common import MATCHING_SWEEP_TAUS, _p_r_f1, evaluate  # noqa: E402

CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
CONFIGS = {
    "bm25": ROOT / "configs" / "bm25_stage3_development_v1.json",
    "tfidf_svd": ROOT / "configs" / "tfidf_svd_stage3_development_v1.json",
}

GAMMA_SWEEP = [0.2, 0.4, 0.6, 0.8, 0.9]
THETA_SWEEP = [0.2, 0.4, 0.6, 0.7, 0.8, 0.9]


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _build_factory(arm: str, config: dict[str, Any], models, nlp):
    """Same fixed text representations as the v3 runner (identical code path):
    per-model, per-domain factory returning {"action": fn, "actor": fn}."""
    if arm == "bm25":
        k1 = float(config["method"]["bm25"]["k1"])
        b = float(config["method"]["bm25"]["b"])
        action_indices: dict[str, Any] = {}
        actor_indices: dict[str, Any] = {}
        for pid, model in models.items():
            action_indices[pid] = BM25Index(
                [a["name"] for a in model.actions if a["name"]], k1=k1, b=b)
            actor_docs = list(model.actors)
            actor_docs.extend(bo["object"] for bo in model.business_objects)
            actor_indices[pid] = BM25Index(actor_docs, k1=k1, b=b)

        def factory(model: Any) -> Any:
            a_index = action_indices[model.process_id]
            ac_index = actor_indices[model.process_id]

            def action_sim(a: str, b: str) -> float:
                return a_index.score(a, b)

            def actor_sim(a: str, b: str) -> float:
                return ac_index.score(a, b)
            return {"action": action_sim, "actor": actor_sim}
        return factory
    seed = int(config["method"]["svd"]["seed"])
    dim = int(config["method"]["svd"]["dim"])
    svd = TfidfSvd(seed=seed, dim=dim,
                   word_ngram=int(config["method"]["features"]["word_ngram"]),
                   char_ngram=int(config["method"]["features"]["char_ngram"]),
                   sublinear_tf=bool(config["method"]["features"]["sublinear_tf"]))
    inference = _load_json(INFERENCE_PACK, "inference pack")
    corpus = list(dict.fromkeys(i["rule_text"] for i in inference["matching_items"]))
    for model in models.values():
        corpus.extend(a["name"] for a in model.actions if a["name"])
        corpus.extend(model.actors)
    svd.fit(corpus)

    def factory(model: Any) -> Any:
        return {"action": svd.similarity, "actor": svd.similarity}
    return factory


def rebuild_violations(arm: str, config: dict[str, Any], factory, models, nlp,
                       inference: dict[str, Any], rules_by_id: dict[str, dict],
                       tau: float, gamma: float, theta: float) -> list[dict[str, Any]]:
    """Re-instantiate the scorer and recompute every violation prediction
    (mapping, R/C sets, denominators and observability all depend on gamma)."""
    scorer = BaselineScorer(factory, tau, gamma, theta)
    preds = []
    for item in sorted(inference["violation_items"], key=lambda i: i["item_id"]):
        record = rules_by_id[item["rule_id"]]
        model = models[item["process_id"]]
        ma = scorer.missing_action(record["actions"], model)
        ia = scorer.incorrect_actor(record["actions"], record["actors"], model)
        oo = scorer.out_of_order(record["order_relations"], record["actions"], model)
        scores = {"missing_action": ma["score"], "incorrect_actor": ia["score"],
                  "out_of_order": oo["score"]}
        item_score = scores[item["check_type"]]
        predicted = item["check_type"] if (item_score is not None and item_score > 0.0) else None
        preds.append({
            "schema_version": "stage3_prediction@1.0.0",
            "method_id": f"s36_{arm}",
            "run_id": "sensitivity",
            "task": "violation",
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "matching_score": None,
            "predicted_relevance": None,
            "missing_action_score": round(ma["score"], 6),
            "incorrect_actor_score": round(ia["score"], 6) if ia["score"] is not None else None,
            "out_of_order_score": round(oo["score"], 6),
            "predicted_violation_type": predicted,
            "evidence": None,
            "threshold": gamma,
            "config_version": config["config_version"],
            "source_hashes": {"rule_record": item["rule_id"], "process_record": item["process_id"]},
            "method_provenance": f"s36_{arm} sensitivity gamma={gamma} theta={theta}",
            "gold_visible": False,
            "check_type": item["check_type"],
            "incorrect_actor_observable": ia["observable"],
            "incorrect_actor_reason": ia.get("reason"),
        })
    return preds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--arm", required=True, choices=sorted(CONFIGS))
    parser.add_argument("--correction", type=Path, default=CORRECTION_PACK)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()

    config = _load_json(CONFIGS[args.arm], f"{args.arm} config")
    inference = _load_json(INFERENCE_PACK, "inference pack")
    correction = _load_json(args.correction, "correction pack")
    run_predictions = [
        json.loads(line)
        for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matching_preds = [p for p in run_predictions if p["task"] == "matching"]
    rules_by_id = {
        json.loads(line)["rule_id"]: json.loads(line)
        for line in (run_dir / "rule_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    nlp = spacy.load("en_core_web_sm")
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)
    factory = _build_factory(args.arm, config, models, nlp)

    tau0 = float(config["thresholds"]["tau"])
    gamma0 = float(config["thresholds"]["gamma"])
    theta0 = float(config["thresholds"]["theta"])

    result: dict[str, Any] = {
        "note": "gamma/theta sweeps RE-INSTANTIATE the BaselineScorer and recompute "
                "mappings, R/C sets, order denominators, observability, scores and "
                "predictions (gamma is not a pure score cutoff for baseline either). "
                "Text representations, Rule/Process Records and the inference pack "
                "stay fixed; matching tau is a score cutoff over the fixed matching "
                "scores. Diagnostic only; primary thresholds stay at the v1 fixed "
                "values (0.5) and are never selected from this data.",
        "matching_tau_sweep": [],
        "violation_gamma_sweep": [],
        "incorrect_actor_theta_sweep": [],
    }

    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    for tau in MATCHING_SWEEP_TAUS:
        tp = fp = fn = tn = 0
        for p in matching_preds:
            g = gold_m[p["item_id"]]["decision_relevant"]
            pred = (p.get("matching_score") or 0.0) > tau
            if pred and g:
                tp += 1
            elif pred and not g:
                fp += 1
            elif not pred and g:
                fn += 1
            else:
                tn += 1
        result["matching_tau_sweep"].append(
            {"tau": tau, "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
             **_p_r_f1(tp, fp, fn)})

    for gamma in GAMMA_SWEEP:
        preds = rebuild_violations(args.arm, config, factory, models, nlp, inference,
                                   rules_by_id, tau0, gamma, theta0)
        ev = evaluate(matching_preds + preds, correction)["violation"]
        result["violation_gamma_sweep"].append(
            {"gamma": gamma, "macro_f1": ev["macro_f1"],
             "exact_type_accuracy": ev["exact_type_accuracy"],
             "unobservable": ev["unobservable"],
             "per_type_f1": {k: v["f1"] for k, v in ev["per_type"].items()},
             "denominator": ev["denominator"]})
    for theta in THETA_SWEEP:
        preds = rebuild_violations(args.arm, config, factory, models, nlp, inference,
                                   rules_by_id, tau0, gamma0, theta)
        ev = evaluate(matching_preds + preds, correction)["violation"]
        result["incorrect_actor_theta_sweep"].append(
            {"theta": theta, "macro_f1": ev["macro_f1"],
             "exact_type_accuracy": ev["exact_type_accuracy"],
             "unobservable": ev["unobservable"],
             "per_type_f1": {k: v["f1"] for k, v in ev["per_type"].items()}})

    out_path = run_dir / "threshold_sensitivity.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

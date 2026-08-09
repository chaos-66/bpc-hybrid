# -*- coding: utf-8 -*-
"""Sun Stage 3 (S3.5) threshold sensitivity with REAL scorer re-execution.

gamma and theta change the action mapping, the actor sets and the
denominators of Definitions 5-7, so a sensitivity sweep cannot re-threshold
the fixed scores. This script re-runs the SunScorer with cached Rule Records
(from the run's rule_records.jsonl) and the canonical Process Records, then
evaluates each parameter setting with the common evaluator.

Matching tau is a score cutoff over the FIXED matching scores and is
re-derived directly (no scorer re-run needed).

Primary parameters stay pre-registered (tau=gamma=theta=0.8); the sweep is
diagnostic only and never selects primary values from this data.

Usage:
    python scripts/sun_stage3_sensitivity.py --run-dir <sun run dir>
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

from bpc_hybrid.sun_stage3.sun_model import build_sun_models  # noqa: E402
from bpc_hybrid.sun_stage3.sun_scorer import SunScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402
from evaluate_stage3_common import (  # noqa: E402
    MATCHING_SWEEP_TAUS,
    _p_r_f1,
    evaluate,
)

STAGE1_CONTRACT = ROOT / "configs" / "stage1_structural_s11_s14.json"
BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
CONFIG = ROOT / "configs" / "sun_stage3_development_v1.json"

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


def _violation_metrics(predictions, correction) -> dict[str, Any]:
    ev = evaluate(predictions, correction)
    v = ev["violation"]
    return {
        "macro_f1": v["macro_f1"],
        "exact_type_accuracy": v["exact_type_accuracy"],
        "unobservable": v["unobservable"],
        "per_type": v["per_type"],
        "denominator": v["denominator"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--correction", type=Path, default=CORRECTION_PACK)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()

    config = _load_json(CONFIG, "sun config")
    inference = _load_json(INFERENCE_PACK, "inference pack")
    correction = _load_json(args.correction, "correction pack")
    run_predictions = [
        json.loads(line)
        for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matching_preds = [p for p in run_predictions if p["task"] == "matching"]

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    models = build_sun_models(BPMN_DIR, STAGE1_CONTRACT, nlp)
    # cached rule records from the run (identical to a fresh extraction)
    rule_records = [
        json.loads(line)
        for line in (run_dir / "rule_records.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rules_by_id = {r["rule_id"]: r for r in rule_records}

    tau0 = float(config["method"]["thresholds"]["tau"])
    gamma0 = float(config["method"]["thresholds"]["gamma"])
    theta0 = float(config["method"]["thresholds"]["theta"])

    def rebuild(preds_with_scores, gamma: float, theta: float) -> list[dict[str, Any]]:
        scorer = SunScorer(sim, tau0, gamma, theta, nlp=nlp)
        out = []
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
            out.append({
                "schema_version": "stage3_prediction@1.0.0",
                "method_id": "sun_2024",
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
                "method_provenance": f"sun_2024 sensitivity gamma={gamma} theta={theta}",
                "gold_visible": False,
                "check_type": item["check_type"],
                "incorrect_actor_observable": ia["observable"],
                "incorrect_actor_reason": ia.get("reason"),
            })
        return out

    result: dict[str, Any] = {
        "note": "gamma/theta sweeps re-execute the SunScorer (mappings/denominators change); "
                "matching tau is a score cutoff over fixed matching scores. Diagnostic only; "
                "primary thresholds stay pre-registered (tau=gamma=theta=0.8).",
        "matching_tau_sweep": [],
        "violation_gamma_sweep": [],
        "incorrect_actor_theta_sweep": [],
    }

    # matching tau sweep over the fixed matching scores
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
             **_p_r_f1(tp, fp, fn)}
        )

    # gamma sweep (theta fixed at primary 0.8)
    for gamma in GAMMA_SWEEP:
        preds = rebuild(matching_preds, gamma, theta0)
        result["violation_gamma_sweep"].append(
            {"gamma": gamma, **_violation_metrics(preds, correction)}
        )
    # theta sweep (gamma fixed at primary 0.8)
    for theta in THETA_SWEEP:
        preds = rebuild(matching_preds, gamma0, theta)
        result["incorrect_actor_theta_sweep"].append(
            {"theta": theta, **_violation_metrics(preds, correction)}
        )

    out_path = run_dir / "threshold_sensitivity.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

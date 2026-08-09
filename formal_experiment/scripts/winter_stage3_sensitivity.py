# -*- coding: utf-8 -*-
"""Winter Stage 3 (S3.4) threshold sensitivity with REAL Pair re-execution.

Winter's gamma changes fitness and all three costs (the mapping threshold),
so a sweep must re-run the WinterPair. This script rebuilds the Winter
predictions with the corrected reachability mode for each gamma in the
diagnostic sweep (delta fixed at the primary 0.8) and evaluates with the
common evaluator. Diagnostic only; the primary gamma stays 0.4.

Usage:
    python scripts/winter_stage3_sensitivity.py --run-dir <winter run dir>
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

from bpc_hybrid.winter_stage3.winter_model import (  # noqa: E402
    REACHABILITY_CORRECTED,
    parse_bpmn_file_winter,
)
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402
from evaluate_stage3_common import evaluate  # noqa: E402

BPMN_DIR = ROOT / "data" / "input" / "stage1_stage3" / "gdpr7"
INFERENCE_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"
CONFIG = ROOT / "configs" / "winter_stage3_development_v1.json"
WINTER_FILES_DIR = ROOT.parent / "references" / "winter_2020_model_check" / "model_check" / "input" / "files"

GAMMA_SWEEP = [0.2, 0.4, 0.6, 0.8, 0.9]


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
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--correction", type=Path, default=CORRECTION_PACK)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()

    config = _load_json(CONFIG, "winter config")
    inference = _load_json(INFERENCE_PACK, "inference pack")
    correction = _load_json(args.correction, "correction pack")
    delta0 = float(config["method"]["delta"])

    nlp = spacy.load("en_core_web_sm")
    sim = WinterSimilarity(nlp)
    signalwords = set((WINTER_FILES_DIR / "signalwords.txt").read_text(encoding="utf-8").splitlines())
    sequencemarkers = set((WINTER_FILES_DIR / "sequencemarkers.txt").read_text(encoding="utf-8").splitlines())
    stopwords = set((WINTER_FILES_DIR / "stopwords.txt").read_text(encoding="utf-8").splitlines())
    models = {
        bpmn.stem: parse_bpmn_file_winter(bpmn, nlp, stopwords,
                                          reachability_mode=REACHABILITY_CORRECTED)
        for bpmn in sorted(BPMN_DIR.glob("*.bpmn"))
    }
    resource_set = set()
    for model in models.values():
        for proc in model.processes:
            resource_set.add(proc.participant.lower())

    # rebuild Winter predictions for a given gamma (matching + violation)
    def rebuild(gamma: float) -> list[dict[str, Any]]:
        from bpc_hybrid.winter_stage3.winter_clause import parse_regulation_paragraph
        from bpc_hybrid.winter_stage3.winter_pair import WinterPair
        rule_texts = {i["rule_id"]: i["rule_text"] for i in inference["matching_items"]}
        preds = []
        for item in sorted(inference["matching_items"], key=lambda i: i["item_id"]):
            paragraph = parse_regulation_paragraph(
                item["rule_id"], rule_texts[item["rule_id"]], nlp, stopwords,
                signalwords, sequencemarkers, only_constraints=True)
            pair = WinterPair(nlp, sim, models[item["process_id"]], paragraph,
                              resource_set, gamma, delta0)
            preds.append({
                "schema_version": "stage3_prediction@1.0.0", "method_id": "winter_2020",
                "run_id": "sensitivity", "task": "matching", "item_id": item["item_id"],
                "process_id": item["process_id"], "rule_id": item["rule_id"],
                "matching_score": round(pair.fitness, 6),
                "predicted_relevance": pair.fitness > 0.0,
                "missing_action_score": round(pair.cost_obligation, 6),
                "incorrect_actor_score": round(pair.cost_resource, 6),
                "out_of_order_score": round(pair.cost_so, 6),
                "predicted_violation_type": None, "evidence": None,
                "threshold": gamma, "config_version": config["config_version"],
                "source_hashes": {"rule_record": None, "process_record": None},
                "method_provenance": f"winter_2020 sensitivity gamma={gamma} delta={delta0}",
                "gold_visible": False,
            })
        for item in sorted(inference["violation_items"], key=lambda i: i["item_id"]):
            paragraph = parse_regulation_paragraph(
                item["rule_id"], rule_texts[item["rule_id"]], nlp, stopwords,
                signalwords, sequencemarkers, only_constraints=True)
            pair = WinterPair(nlp, sim, models[item["process_id"]], paragraph,
                              resource_set, gamma, delta0)
            costs = {"missing_action": pair.cost_obligation,
                     "incorrect_actor": pair.cost_resource,
                     "out_of_order": pair.cost_so}
            predicted = item["check_type"] if costs[item["check_type"]] > 0.0 else None
            preds.append({
                "schema_version": "stage3_prediction@1.0.0", "method_id": "winter_2020",
                "run_id": "sensitivity", "task": "violation", "item_id": item["item_id"],
                "process_id": item["process_id"], "rule_id": item["rule_id"],
                "matching_score": None, "predicted_relevance": None,
                "missing_action_score": round(pair.cost_obligation, 6),
                "incorrect_actor_score": round(pair.cost_resource, 6),
                "out_of_order_score": round(pair.cost_so, 6),
                "predicted_violation_type": predicted, "evidence": None,
                "threshold": gamma, "config_version": config["config_version"],
                "source_hashes": {"rule_record": None, "process_record": None},
                "method_provenance": f"winter_2020 sensitivity gamma={gamma} delta={delta0}",
                "gold_visible": False, "check_type": item["check_type"],
            })
        return preds

    result: dict[str, Any] = {
        "note": "Winter gamma sweep re-runs WinterPair (fitness and all costs depend on "
                "gamma; delta fixed at primary 0.8). Diagnostic only; primary gamma stays 0.4.",
        "violation_gamma_sweep": [],
        "matching_gamma_sweep": [],
    }
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    from evaluate_stage3_common import _p_r_f1
    for gamma in GAMMA_SWEEP:
        preds = rebuild(gamma)
        v = _violation_metrics(preds, correction)
        tp = fp = fn = tn = 0
        for p in [q for q in preds if q["task"] == "matching"]:
            g = gold_m[p["item_id"]]["decision_relevant"]
            pred = p["predicted_relevance"]
            if pred and g:
                tp += 1
            elif pred and not g:
                fp += 1
            elif not pred and g:
                fn += 1
            else:
                tn += 1
        result["matching_gamma_sweep"].append(
            {"gamma": gamma, "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
             **_p_r_f1(tp, fp, fn)}
        )
        result["violation_gamma_sweep"].append({"gamma": gamma, **v})

    out_path = run_dir / "threshold_sensitivity.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""S3.6 baseline gamma/theta cutoff sensitivity (evaluation-side script).

Baseline mappings are parameter-free (fixed BM25/TF-IDF similarity), so
gamma/theta only act as decision cutoffs over the fixed scores; re-thresholding
is therefore a legitimate sensitivity here (documented difference vs Sun,
whose gamma changes the mapping sets and denominators). Matching tau is also a
score cutoff. This script reads the run's predictions and the correction pack
(evaluation role; the runner itself never reads Gold).

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

from evaluate_stage3_common import MATCHING_SWEEP_TAUS, _p_r_f1, evaluate  # noqa: E402

CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--correction", type=Path, default=CORRECTION_PACK)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    correction = _load_json(args.correction, "correction pack")
    predictions = [
        json.loads(line)
        for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matching_preds = [p for p in predictions if p["task"] == "matching"]
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}

    result: dict[str, Any] = {
        "note": "baseline mappings are parameter-free (fixed BM25/TF-IDF similarity); "
                "gamma/theta sweeps re-threshold the fixed scores, which is legitimate here "
                "(documented difference vs Sun, where gamma changes the mapping sets). "
                "Diagnostic only; primary thresholds stay pre-registered.",
        "matching_tau_sweep": [],
        "violation_gamma_sweep": [],
        "incorrect_actor_theta_sweep": [],
    }
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
        preds = []
        for p in [q for q in predictions if q["task"] == "violation"]:
            pp = dict(p)
            ct = pp["check_type"]
            if ct in ("missing_action", "out_of_order"):
                score = pp.get(f"{ct}_score")
                pp["predicted_violation_type"] = ct if (score or 0.0) > gamma else None
            preds.append(pp)
        ev = evaluate(matching_preds + preds, correction)["violation"]
        result["violation_gamma_sweep"].append(
            {"gamma": gamma, "macro_f1": ev["macro_f1"],
             "exact_type_accuracy": ev["exact_type_accuracy"],
             "unobservable": ev["unobservable"]})

    for theta in THETA_SWEEP:
        preds = []
        for p in [q for q in predictions if q["task"] == "violation"]:
            pp = dict(p)
            if pp["check_type"] == "incorrect_actor":
                score = pp.get("incorrect_actor_score")
                pp["predicted_violation_type"] = "incorrect_actor" if (score or 0.0) > theta else None
            preds.append(pp)
        ev = evaluate(matching_preds + preds, correction)["violation"]
        result["incorrect_actor_theta_sweep"].append(
            {"theta": theta, "macro_f1": ev["macro_f1"],
             "exact_type_accuracy": ev["exact_type_accuracy"],
             "unobservable": ev["unobservable"]})

    out_path = run_dir / "threshold_sensitivity.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

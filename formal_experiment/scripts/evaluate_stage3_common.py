# -*- coding: utf-8 -*-
"""Common Stage 3 evaluator shared by the Winter baseline (S3.4) and the Sun
reconstruction (S3.5).

Consumes predictions in the common ``stage3_prediction@1.0.0`` schema
(configs/schemas/stage3_prediction.schema.json) against the frozen S3.2/S3.3
correction pack. This is the ONLY component allowed to read Gold decisions.

Metrics (DEV_ONLY):
- matching: per-process AP and MAP over the continuous matching score
  (ranking), plus binary P/R/F1 + confusion when predicted_relevance is not
  null (pre-registered rule only);
- violation: per-type support and P/R/F1, macro/micro F1, exact type
  accuracy, detected/missed/wrong-type counts, unobservable counts and
  denominator detail; specificity stays N/A because the frozen pack has no
  compliant (none) gold items.

Threshold sensitivity is a pure re-scoring of the same predictions with
different tau/gamma/theta values (no re-similarity, no re-run).

Usage:
    python scripts/evaluate_stage3_common.py --predictions <predictions.jsonl> [--run-dir <dir>]
    python scripts/evaluate_stage3_common.py --sweep --predictions <predictions.jsonl> [--run-dir <dir>]
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"

TYPES = ["missing_action", "incorrect_actor", "out_of_order"]
MATCHING_SWEEP_TAUS = [0.2, 0.4, 0.6, 0.8, 0.9]
VIOLATION_SWEEP_GAMMAS = [0.2, 0.4, 0.6, 0.8, 0.9]
ACTOR_SWEEP_THETAS = [0.2, 0.4, 0.6, 0.8, 0.9]


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def _p_r_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def _average_precision(ranked: list[tuple[float, bool]]) -> float:
    """AP over a relevance-ranked list (descending score)."""
    hits = 0
    precisions = []
    for rank, (_, rel) in enumerate(ranked, start=1):
        if rel:
            hits += 1
            precisions.append(hits / rank)
    return statistics.mean(precisions) if precisions else 0.0


def evaluate_matching(preds: list[dict[str, Any]],
                      gold: dict[str, Any]) -> dict[str, Any]:
    by_process: dict[str, list[tuple[float, bool]]] = {}
    tp = fp = fn = tn = 0
    binary_supported = all(p.get("predicted_relevance") is not None for p in preds)
    for p in preds:
        g = gold[p["item_id"]]["decision_relevant"]
        score = p.get("matching_score")
        if score is None:
            score = 0.0
        by_process.setdefault(p["process_id"], []).append((float(score), bool(g)))
        if binary_supported:
            pred = bool(p["predicted_relevance"])
            if pred and g:
                tp += 1
            elif pred and not g:
                fp += 1
            elif not pred and g:
                fn += 1
            else:
                tn += 1
    aps = [_average_precision(sorted(v, key=lambda x: x[0], reverse=True))
           for v in by_process.values()]
    result: dict[str, Any] = {
        "support": len(preds),
        "per_process_ap": {
            pid: round(_average_precision(sorted(v, key=lambda x: x[0], reverse=True)), 4)
            for pid, v in sorted(by_process.items())
        },
        "MAP": round(statistics.mean(aps), 4) if aps else None,
        "ap_note": "per-process AP over 2-5 rule candidates per process; small query sets, interpret with care",
    }
    if binary_supported:
        result["binary"] = {
            "rule": "fitness > 0 (Winter) or pre-registered binary rule",
            "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
            **_p_r_f1(tp, fp, fn),
        }
    else:
        result["binary"] = {
            "rule": None,
            "note": "ranking-only; no pre-registered binary rule for this method",
        }
    return result


def evaluate_violation(preds: list[dict[str, Any]],
                       gold: dict[str, Any]) -> dict[str, Any]:
    per_type: dict[str, dict[str, int]] = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
    unobservable = 0
    detected = missed = wrong_type = 0
    denominator_detail: dict[str, Any] = {}
    for p in preds:
        g = gold[p["item_id"]]["decision_violation_type"]
        pred = p.get("predicted_violation_type")
        if p.get("incorrect_actor_observable") is False:
            unobservable += 1
        if pred == g:
            detected += 1
            per_type[g]["tp"] += 1
        elif g is None:
            per_type["none"] = per_type.get("none", {"tp": 0, "fp": 0, "fn": 0})
            per_type["none"]["fp"] += 1
        else:
            missed += 1
            per_type[g]["fn"] += 1
            if pred is not None:
                wrong_type += 1
                per_type[pred] = per_type.get(pred, {"tp": 0, "fp": 0, "fn": 0})
                per_type[pred]["fp"] += 1
    per_type_results = {}
    for t in TYPES:
        per_type_results[t] = {
            "support": per_type[t]["tp"] + per_type[t]["fn"],
            **_p_r_f1(per_type[t]["tp"], per_type[t]["fp"], per_type[t]["fn"]),
        }
    total_tp = sum(per_type[t]["tp"] for t in TYPES)
    total_fp = sum(per_type[t]["fp"] for t in TYPES)
    total_fn = sum(per_type[t]["fn"] for t in TYPES)
    micro = _p_r_f1(total_tp, total_fp, total_fn)
    denominator_detail = {
        "total_items": len(preds),
        "per_type_support": {t: per_type[t]["tp"] + per_type[t]["fn"] for t in TYPES},
        "unobservable": unobservable,
        "none_gold_items": sum(1 for p in preds if gold[p["item_id"]]["decision_violation_type"] is None),
        "compliant_specificity_note": (
            "N/A: the frozen violation pack contains no compliant (none) gold "
            "items, so specificity / compliant accuracy has no denominator"
        ),
    }
    return {
        "support": len(preds),
        "per_type": per_type_results,
        "macro_f1": round(statistics.mean([v["f1"] for v in per_type_results.values()]), 4),
        "micro_f1": micro["f1"],
        "exact_type_accuracy": round(detected / len(preds), 4) if preds else 0.0,
        "detected": detected,
        "missed": missed,
        "wrong_type": wrong_type,
        "unobservable": unobservable,
        "denominator": denominator_detail,
    }


def evaluate(predictions: list[dict[str, Any]],
             correction: dict[str, Any]) -> dict[str, Any]:
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    gold_v = {i["item_id"]: i for i in correction["violation_items"]}
    m_preds = [p for p in predictions if p["task"] == "matching"]
    v_preds = [p for p in predictions if p["task"] == "violation"]
    return {
        "method_id": predictions[0]["method_id"] if predictions else None,
        "run_id": predictions[0]["run_id"] if predictions else None,
        "matching": evaluate_matching(m_preds, gold_m),
        "violation": evaluate_violation(v_preds, gold_v),
    }


def threshold_sensitivity(predictions: list[dict[str, Any]],
                          correction: dict[str, Any]) -> dict[str, Any]:
    """Pure re-scoring: same scores, different tau/gamma/theta. Uses only the
    score fields, never Gold, to re-derive binary decisions."""
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    gold_v = {i["item_id"]: i for i in correction["violation_items"]}
    result: dict[str, Any] = {"note": "fixed diagnostic sweep; primary thresholds are NOT chosen from this data"}
    # matching tau sweep: binary rule = matching_score > tau
    m_rows = []
    for tau in MATCHING_SWEEP_TAUS:
        tp = fp = fn = tn = 0
        for p in [q for q in predictions if q["task"] == "matching"]:
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
        m_rows.append({"tau": tau, "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
                       **_p_r_f1(tp, fp, fn)})
    result["matching_tau_sweep"] = m_rows
    # violation gamma sweep: missing_action = missing_action_score > gamma;
    # out_of_order = out_of_order_score > gamma
    v_rows = []
    for gamma in VIOLATION_SWEEP_GAMMAS:
        row: dict[str, Any] = {"gamma": gamma}
        for vtype, score_key in (("missing_action", "missing_action_score"),
                                 ("out_of_order", "out_of_order_score")):
            tp = fp = fn = 0
            for p in [q for q in predictions if q["task"] == "violation"
                      and q.get("candidate_violation_type") == vtype]:
                g = gold_v[p["item_id"]]["decision_violation_type"]
                pred = (p.get(score_key) or 0.0) > gamma
                if pred and g == vtype:
                    tp += 1
                elif pred and g != vtype:
                    fp += 1
                elif not pred and g == vtype:
                    fn += 1
            row[vtype] = _p_r_f1(tp, fp, fn)
        v_rows.append(row)
    result["violation_gamma_sweep"] = v_rows
    # incorrect-actor theta sweep: actor_score > theta (only where observable)
    a_rows = []
    for theta in ACTOR_SWEEP_THETAS:
        tp = fp = fn = 0
        for p in [q for q in predictions if q["task"] == "violation"
                  and q.get("candidate_violation_type") == "incorrect_actor"]:
            score = p.get("incorrect_actor_score")
            if score is None:
                continue  # unobservable stays out of the sweep denominator
            g = gold_v[p["item_id"]]["decision_violation_type"]
            pred = score > theta
            if pred and g == "incorrect_actor":
                tp += 1
            elif pred and g != "incorrect_actor":
                fp += 1
            elif not pred and g == "incorrect_actor":
                fn += 1
        a_rows.append({"theta": theta, **_p_r_f1(tp, fp, fn)})
    result["incorrect_actor_theta_sweep"] = a_rows
    return result


def write_error_analysis(run_dir: Path, predictions: list[dict[str, Any]],
                         evaluation: dict[str, Any],
                         correction: dict[str, Any]) -> None:
    """Method-agnostic error analysis derived from predictions + evaluation
    (no Gold inference; deviations are reported against the frozen Gold only
    in the evaluator, which is allowed to read it)."""
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    gold_v = {i["item_id"]: i for i in correction["violation_items"]}
    method = predictions[0].get("method_id", "?") if predictions else "?"
    lines = [
        f"# Stage 3 development error analysis - {method} (DEV_ONLY)",
        "",
        "## matching FP/FN (binary rule) or ranking notes",
        "",
    ]
    for p in [q for q in predictions if q["task"] == "matching"]:
        gold = gold_m[p["item_id"]]["decision_relevant"]
        pred = p.get("predicted_relevance")
        if pred is not None and pred != gold:
            lines.append(
                f"- {p['item_id']} {p['process_id']} x {p['rule_id']}: "
                f"gold={gold} pred={pred} matching_score={p.get('matching_score')}"
            )
    if not any(q.get("predicted_relevance") is not None for q in predictions if q["task"] == "matching"):
        lines.append("- ranking-only (no binary rule); see per-process AP/MAP in evaluation.json")
    lines += ["", "## violation missed / wrong-type / unobservable", ""]
    for p in [q for q in predictions if q["task"] == "violation"]:
        gold = gold_v[p["item_id"]]["decision_violation_type"]
        pred = p.get("predicted_violation_type")
        scores = p.get("scores") or {
            "missing_action": p.get("missing_action_score"),
            "incorrect_actor": p.get("incorrect_actor_score"),
            "out_of_order": p.get("out_of_order_score"),
        }
        note = ""
        if p.get("incorrect_actor_observable") is False:
            note = " [actor unobservable]"
        if pred != gold:
            lines.append(
                f"- {p['item_id']} {p['process_id']} x {p['rule_id']}: "
                f"gold={gold} pred={pred} scores={scores}{note}"
            )
    lines += [
        "",
        "## threshold sensitivity",
        "",
        "- primary thresholds are pre-registered (Winter gamma 0.4/delta 0.8;",
        "  Sun tau/gamma/theta 0.8); sweep values are sensitivity reports only",
        "  and are NOT used to pick primary thresholds (see threshold_sensitivity.json).",
        "",
        "## error attribution",
        "",
        "- method differences (Winter clause-bag vs Sun Rule Record action/actor",
        "  separation and order relations), actor observability (empty lane names;",
        "  pool names present), rule extraction quality of the development adapter,",
        "  and similarity backend limits (en_core_web_sm, no word vectors) are the",
        "  expected error sources; no Gold/sample/threshold adjustment was performed.",
    ]
    (run_dir / "error_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--sweep", action="store_true",
                        help="also compute threshold sensitivity and write threshold_sensitivity.json")
    parser.add_argument("--error-analysis", action="store_true",
                        help="also write error_analysis.md into the run dir")
    parser.add_argument("--correction", type=Path, default=CORRECTION_PACK)
    args = parser.parse_args()

    try:
        predictions = [
            json.loads(line)
            for line in args.predictions.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not predictions:
            raise RuntimeError("empty predictions file")
        correction = _load_json(args.correction, "correction pack")
        evaluation = evaluate(predictions, correction)
        print(json.dumps(evaluation, ensure_ascii=False, indent=2))
        if args.run_dir is not None:
            run_dir = args.run_dir.resolve()
            (run_dir / "evaluation.json").write_text(
                json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            if args.sweep:
                sweep = threshold_sensitivity(predictions, correction)
                (run_dir / "threshold_sensitivity.json").write_text(
                    json.dumps(sweep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            if args.error_analysis:
                write_error_analysis(run_dir, predictions, evaluation, correction)
        return 0
    except Exception as exc:
        print(f"common stage3 evaluation failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

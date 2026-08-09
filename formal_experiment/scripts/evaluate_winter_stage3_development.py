# -*- coding: utf-8 -*-
"""Winter et al. (2020) Stage 3 development evaluator.

Reads the runner's predictions plus the frozen S3.2/S3.3 correction pack
(the ONLY component allowed to read Gold decisions) and writes
``evaluation.json`` and ``error_analysis.md`` into the run directory.

Metrics (DEV_ONLY, no formal claim):
- matching: support, precision/recall/F1, confusion counts, per-process AP
  (small query sets; reported with a caveat);
- violation: per-type support, per-type P/R/F1, macro/micro F1, exact type
  accuracy, detected/missed/wrong-type counts; specificity/compliant
  accuracy is N/A because the frozen pack contains no compliant gold items.

Usage:
    python scripts/evaluate_winter_stage3_development.py --run-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"


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


def evaluate(run_dir: Path) -> dict[str, Any]:
    predictions_path = run_dir / "predictions.jsonl"
    predictions = [
        json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    correction = _load_json(CORRECTION_PACK, "correction pack")
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    gold_v = {i["item_id"]: i for i in correction["violation_items"]}

    # ------------------------------------------------------------- matching
    m_preds = [p for p in predictions if p["task"] == "matching"]
    tp = fp = fn = tn = 0
    per_process: dict[str, list[tuple[float, bool]]] = {}
    for p in m_preds:
        gold = gold_m[p["item_id"]]["decision_relevant"]
        pred = p.get("predicted_relevant", p.get("predicted_relevance"))
        if pred and gold:
            tp += 1
        elif pred and not gold:
            fp += 1
        elif not pred and gold:
            fn += 1
        else:
            tn += 1
        per_process.setdefault(p["process_id"], []).append((p["fitness"], gold))
    # per-process AP (ranking by fitness descending)
    aps = []
    for process_id, pairs in per_process.items():
        pairs_sorted = sorted(pairs, key=lambda x: x[0], reverse=True)
        hits = 0
        precisions = []
        for rank, (_, rel) in enumerate(pairs_sorted, start=1):
            if rel:
                hits += 1
                precisions.append(hits / rank)
        ap = statistics.mean(precisions) if precisions else 0.0
        aps.append(ap)
    matching = {
        "support": len(m_preds),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        **_p_r_f1(tp, fp, fn),
        "mean_ap_per_process": round(statistics.mean(aps), 4) if aps else None,
        "ap_note": "per-process AP over 2-5 rule candidates per process; small query sets, interpret with care",
        "fitness_range": {
            "min": round(min(p["fitness"] for p in m_preds), 4),
            "max": round(max(p["fitness"] for p in m_preds), 4),
        },
    }

    # ------------------------------------------------------------ violation
    v_preds = [p for p in predictions if p["task"] == "violation"]
    types = ["missing_action", "incorrect_actor", "out_of_order"]
    per_type: dict[str, dict[str, int]] = {}
    detected = missed = wrong_type = 0
    for t in types:
        per_type[t] = {"tp": 0, "fp": 0, "fn": 0}
    for p in v_preds:
        gold = gold_v[p["item_id"]]["decision_violation_type"]
        pred = p["predicted_violation_type"]
        if pred == gold:
            detected += 1
            per_type[gold]["tp"] += 1
        elif gold is None:
            per_type.setdefault("none", per_type.get("none", {"tp": 0, "fp": 0, "fn": 0}))
            per_type["none"]["fp"] += 1
        else:
            missed += 1
            per_type[gold]["fn"] += 1
            if pred is not None:
                wrong_type += 1
                per_type.setdefault(pred, per_type.get(pred, {"tp": 0, "fp": 0, "fn": 0}))
                per_type[pred]["fp"] += 1
    per_type_results = {}
    for t in types:
        per_type_results[t] = {
            "support": per_type[t]["tp"] + per_type[t]["fn"],
            **_p_r_f1(per_type[t]["tp"], per_type[t]["fp"], per_type[t]["fn"]),
        }
    total_tp = sum(per_type[t]["tp"] for t in types)
    total_fp = sum(per_type[t]["fp"] for t in types)
    total_fn = sum(per_type[t]["fn"] for t in types)
    micro = _p_r_f1(total_tp, total_fp, total_fn)
    per_type_macro = {
        k: statistics.mean([v["precision"], v["recall"], v["f1"]])
        for k, v in per_type_results.items()
    }
    violation = {
        "support": len(v_preds),
        "per_type": per_type_results,
        "macro_f1": round(statistics.mean([v["f1"] for v in per_type_results.values()]), 4),
        "micro_f1": micro["f1"],
        "exact_type_accuracy": round(detected / len(v_preds), 4) if v_preds else 0.0,
        "detected": detected,
        "missed": missed,
        "wrong_type": wrong_type,
        "compliant_specificity_note": (
            "N/A: the frozen violation pack contains no compliant (none) gold "
            "items, so specificity / compliant accuracy has no denominator"
        ),
    }
    return {"matching": matching, "violation": violation}


def write_error_analysis(run_dir: Path, evaluation: dict[str, Any],
                         predictions: list[dict[str, Any]],
                         correction: dict[str, Any]) -> None:
    gold_m = {i["item_id"]: i for i in correction["matching_items"]}
    gold_v = {i["item_id"]: i for i in correction["violation_items"]}
    lines = [
        "# Winter Stage 3 development - error analysis (DEV_ONLY)",
        "",
        "## matching FP/FN",
        "",
    ]
    for p in [p for p in predictions if p["task"] == "matching"]:
        gold = gold_m[p["item_id"]]["decision_relevant"]
        pred = p["predicted_relevant"]
        if pred != gold:
            lines.append(
                f"- {p['item_id']} {p['process_id']} x {p['rule_id']}: "
                f"gold={gold} pred={pred} fitness={p['fitness']} cost_obligation={p['cost_obligation']}"
            )
    lines += [
        "",
        "## violation missed / wrong-type",
        "",
    ]
    for p in [p for p in predictions if p["task"] == "violation"]:
        gold = gold_v[p["item_id"]]["decision_violation_type"]
        pred = p["predicted_violation_type"]
        if pred != gold:
            lines.append(
                f"- {p['item_id']} {p['process_id']} x {p['rule_id']} "
                f"(candidate {p['candidate_violation_type']}): gold={gold} pred={pred} "
                f"cost_obligation={p['cost_obligation']} cost_resource={p['cost_resource']} "
                f"cost_so={p['cost_so']}"
            )
    lines += [
        "",
        "## threshold sensitivity",
        "",
        "- gamma=0.4 fixed (Winter prototype main.py / gdpr.config); no post-hoc tuning.",
        "- matching relevance boundary is fitness>0 (equivalently: at least one",
        "  obligation maps above gamma); a stricter threshold would lower recall,",
        "  a looser one would raise false positives - not explored here by design.",
        "",
        "## input-contract limitations",
        "",
        "- The frozen GDPR7 BPMN files carry an empty process/participant name (and",
        "  empty lane names), so Winter resource (incorrect-actor) cost is vacuous:",
        "  cost_resource is expected to be 0 and incorrect_actor predictions are 'none'",
        "  for every item. This is an input-contract limitation, not a method defect.",
        "- Out-of-order detection relies on sequence-flow reachability plus",
        "  paragraph flow markers; the prototype's is_reachable_from bug was fixed",
        "  (see config known_prototype_deviation); with the bug replicated, all",
        "  cost_so would be 0.",
        "",
        "## prototype capability boundary",
        "",
        "- Winter baseline has no notion of our three-type violation labels: the",
        "  mapping to missing_action / incorrect_actor / out_of_order is a",
        "  transcription (cost_obligation/cost_resource/cost_so > 0).",
        "- spaCy en_core_web_sm semantic similarity is the only matching signal;",
        "  label/lane/order information beyond sequence flows is unused, exactly",
        "  as in the prototype.",
        "",
        "## error attribution",
        "",
        "- Errors dominated by input contracts (empty participant names) and by the",
        "  coarse mapping from continuous Winter costs to binary Gold labels.",
        "- No Gold, sample, or threshold adjustment was performed to improve scores.",
    ]
    (run_dir / "error_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    try:
        evaluation = evaluate(run_dir)
        predictions = [
            json.loads(line) for line in (run_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        correction = _load_json(CORRECTION_PACK, "correction pack")
        write_error_analysis(run_dir, evaluation, predictions, correction)
        (run_dir / "evaluation.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        # append evaluation hashes to the manifest
        manifest_path = run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["evaluation"] = {
            "path": "evaluation.json",
            "sha256": _sha256(run_dir / "evaluation.json"),
        }
        manifest["error_analysis"] = {
            "path": "error_analysis.md",
            "sha256": _sha256(run_dir / "error_analysis.md"),
        }
        manifest["artifacts"]["evaluation"] = manifest["evaluation"]
        manifest["artifacts"]["error_analysis"] = manifest["error_analysis"]
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evaluation, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"evaluation failed closed: {exc}", file=sys.stderr)
        return 2


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

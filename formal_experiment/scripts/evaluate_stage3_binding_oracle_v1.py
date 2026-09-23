# -*- coding: utf-8 -*-
"""Evaluate Stage-3 supplied-binding oracle predictions against the paired benchmark.

Outputs per-type precision/recall/F1, Macro-F1 over the three violation types,
Micro-F1, compliant specificity, and exact-type accuracy.  It never writes Gold.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"


def prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1}


def evaluate_predictions(
    benchmark: Mapping[str, Any],
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gold_by_id = {
        str(item["item_id"]): str(item.get("gold_violation_type", COMPLIANT))
        for item in benchmark.get("items") or []
    }
    pred_by_id = {
        str(row["item_id"]): row.get("predicted")
        for row in predictions
    }
    missing = sorted(set(gold_by_id) - set(pred_by_id))
    extra = sorted(set(pred_by_id) - set(gold_by_id))
    rows: list[dict[str, Any]] = []
    for item_id, gold in gold_by_id.items():
        pred = pred_by_id.get(item_id)
        rows.append({"item_id": item_id, "gold": gold, "predicted": pred})

    per_type: dict[str, Any] = {}
    for t in TYPES:
        tp = sum(1 for r in rows if r["predicted"] == t and r["gold"] == t)
        fp = sum(1 for r in rows if r["predicted"] == t and r["gold"] != t)
        fn = sum(1 for r in rows if r["predicted"] != t and r["gold"] == t)
        per_type[t] = prf(tp, fp, fn)

    controls = [r for r in rows if r["gold"] == COMPLIANT]
    variants = [r for r in rows if r["gold"] != COMPLIANT]
    correct_controls = sum(1 for r in controls if r["predicted"] == COMPLIANT)
    specificity = correct_controls / len(controls) if controls else 0.0

    micro_tp = sum(1 for r in rows
                   if r["gold"] != COMPLIANT and r["predicted"] == r["gold"])
    micro_fp = sum(1 for r in rows
                   if r["gold"] == COMPLIANT and r["predicted"] != COMPLIANT)
    micro_fn = sum(1 for r in rows
                   if r["gold"] != COMPLIANT and r["predicted"] != r["gold"])
    micro = prf(micro_tp, micro_fp, micro_fn)
    macro_f1 = sum(per_type[t]["f1"] for t in TYPES) / len(TYPES)
    exact = sum(1 for r in variants if r["predicted"] == r["gold"])

    return {
        "schema_version": "stage3_binding_oracle_evaluation@1.0.0",
        "claim_scope": "development_oracle_diagnostic",
        "end_to_end_ours_claim_allowed": False,
        "benchmark_id": benchmark.get("benchmark_id"),
        "items": len(rows),
        "missing_predictions": missing,
        "extra_predictions": extra,
        "per_type": per_type,
        "macro_f1": macro_f1,
        "micro_f1": micro,
        "compliant_specificity": specificity,
        "compliant_false_positive_rate": 1.0 - specificity,
        "variant_exact_type_accuracy": exact / len(variants) if variants else None,
        "variant_exact_type_correct": exact,
        "variants": len(variants),
        "controls": len(controls),
        "unobservable": sum(1 for r in rows if r["predicted"] is None),
        "rows": rows,
    }


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    benchmark = _load(args.benchmark)
    predictions = [
        json.loads(line) for line in
        args.predictions.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    report = evaluate_predictions(benchmark, predictions)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

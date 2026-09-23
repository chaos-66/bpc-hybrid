# -*- coding: utf-8 -*-
"""Evaluate the frozen Ours predictions on the eligibility-audited subset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / "outputs/development/stage3_ours_v1/predictions.jsonl"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
ELIGIBILITY = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json"
OUT_JSON = ROOT / "outputs/reports/stage3_ours_v1_evaluation.json"
OUT_MD = ROOT / "outputs/reports/stage3_ours_v1_evaluation.md"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def _prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision,
            "recall": recall, "f1": f1}


def _metrics(rows: list[dict[str, Any]], eligible_type: str | None = None
             ) -> dict[str, Any]:
    scoped = [r for r in rows if eligible_type is None
              or r.get("target_type") == eligible_type]
    per_type: dict[str, Any] = {}
    for type_name in TYPES:
        type_rows = [r for r in scoped if r.get("target_type") == type_name]
        tp = sum(1 for r in type_rows
                 if r.get("predicted") == type_name
                 and r.get("gold") == type_name)
        fp = sum(1 for r in type_rows
                 if r.get("predicted") == type_name
                 and r.get("gold") != type_name)
        fn = sum(1 for r in type_rows
                 if r.get("predicted") != type_name
                 and r.get("gold") == type_name)
        per_type[type_name] = _prf(tp, fp, fn)
    controls = [r for r in scoped if r.get("role") == "control"]
    variants = [r for r in scoped if r.get("role") == "variant"]
    correct_compliant = sum(
        1 for r in controls if r.get("predicted") == COMPLIANT)
    micro_tp = sum(1 for r in scoped
                   if r.get("gold") != COMPLIANT
                   and r.get("predicted") == r.get("gold"))
    micro_fp = sum(1 for r in scoped
                   if r.get("gold") == COMPLIANT
                   and r.get("predicted") != COMPLIANT)
    micro_fn = sum(1 for r in scoped
                   if r.get("gold") != COMPLIANT
                   and r.get("predicted") != r.get("gold"))
    exact = sum(1 for r in variants if r.get("predicted") == r.get("gold"))
    supported = [t for t in TYPES if any(
        r.get("target_type") == t for r in scoped)]
    macro_values = [per_type[t]["f1"] for t in supported]
    return {
        "items": len(scoped),
        "per_type": per_type,
        "macro_f1": (sum(macro_values) / len(macro_values)
                     if macro_values else None),
        "macro_f1_supported_types": supported,
        "micro_f1": _prf(micro_tp, micro_fp, micro_fn),
        "compliant_specificity": (
            correct_compliant / len(controls) if controls else None),
        "compliant_false_positive_rate": (
            1.0 - correct_compliant / len(controls) if controls else None),
        "variant_exact_type_accuracy": exact / len(variants)
        if variants else None,
        "variant_exact_type_correct": exact,
        "variants": len(variants),
        "controls_correct": correct_compliant,
        "controls": len(controls),
        "unobservable": sum(1 for r in scoped
                            if r.get("predicted") in (None, "unobservable")),
    }


def build() -> dict[str, Any]:
    benchmark = _load(BENCHMARK)
    eligibility_rows = _load(ELIGIBILITY)["records"]
    eligibility = {
        (str(r["pair_id"]), str(r["violation_type"])): bool(r["eligible"])
        for r in eligibility_rows
    }
    preds = {str(r["item_id"]): r for r in _load_jsonl(PREDICTIONS)}
    rows: list[dict[str, Any]] = []
    for item in benchmark["items"]:
        pair_id = str(item["pair_id"])
        target_type = str(item["target_violation_type"])
        eligible = eligibility.get((pair_id, target_type), False)
        if not eligible:
            continue
        pred = preds.get(str(item["item_id"])) or {}
        rows.append({
            "item_id": item["item_id"],
            "pair_id": pair_id,
            "role": item["role"],
            "target_type": target_type,
            "gold": item["gold_violation_type"],
            "predicted": pred.get("predicted"),
        })
    report = {
        "schema_version": "stage3_ours_evaluation@1.0.0",
        "method_id": "ours_automatic_grounding_detector_v1",
        "status": "complete",
        "eligibility_protocol": "stage3_paired_benchmark_eligibility_v1",
        "overall_eligible": _metrics(rows),
        "per_violation_type_eligible": {
            t: _metrics(rows, t) for t in TYPES
        },
        "rows": rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    lines = [
        "# Ours Stage-3 evaluation (eligibility-audited)",
        "",
        f"- eligible items: {report['overall_eligible']['items']}",
        f"- macro-F1 (supported types): {report['overall_eligible']['macro_f1']}",
        f"- micro-F1: {report['overall_eligible']['micro_f1']['f1']}",
        f"- compliant specificity: {report['overall_eligible']['compliant_specificity']}",
        f"- exact type accuracy: {report['overall_eligible']['variant_exact_type_accuracy']}",
        f"- unobservable: {report['overall_eligible']['unobservable']}",
        "",
        "| Type | eligible items | P | R | F1 |",
        "|---|---:|---:|---:|---:|",
    ]
    for t in TYPES:
        m = report["per_violation_type_eligible"][t]
        lines.append(f"| {t} | {m['items']} | "
                     f"{m['per_type'][t]['precision']:.4f} | "
                     f"{m['per_type'][t]['recall']:.4f} | "
                     f"{m['per_type'][t]['f1']:.4f} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report = build()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

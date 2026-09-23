# -*- coding: utf-8 -*-
"""Build the final Stage-3 Table 3 on the eligibility-audited paired benchmark.

Methods are compared on exactly the same eligible item set.  The supplied-
binding grounded checker is reported separately as an Oracle/upper bound; it is
never labelled Ours.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
ELIGIBILITY = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json"
PREDECESSORS = ROOT / "outputs/reports/stage3_predecessors_paired_v1.json"
GROUNDED = ROOT / "outputs/reports/stage3_grounded_checker_v1.json"
OURS_PREDICTIONS = ROOT / "outputs/development/stage3_ours_v1/predictions.jsonl"
OUT_JSON = ROOT / "outputs/reports/stage3_table3_v1.json"
OUT_MD = ROOT / "outputs/reports/stage3_table3_v1.md"
OUT_INSERT = ROOT / "outputs/reports/stage3_table3_v1_paper_insert.md"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
COMPLIANT = "compliant"
UNOBSERVABLE = (None, "unobservable")


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


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_type: dict[str, Any] = {}
    for type_name in TYPES:
        type_rows = [r for r in rows if r.get("target_type") == type_name]
        if not type_rows:
            per_type[type_name] = {
                "support": 0, "precision": None, "recall": None, "f1": None,
                "tp": 0, "fp": 0, "fn": 0,
            }
            continue
        tp = sum(1 for r in type_rows
                 if r.get("predicted") == type_name
                 and r.get("gold") == type_name)
        fp = sum(1 for r in type_rows
                 if r.get("predicted") == type_name
                 and r.get("gold") != type_name)
        fn = sum(1 for r in type_rows
                 if r.get("predicted") != type_name
                 and r.get("gold") == type_name)
        row = _prf(tp, fp, fn)
        row["support"] = len(type_rows)
        per_type[type_name] = row
    controls = [r for r in rows if r.get("role") == "control"]
    variants = [r for r in rows if r.get("role") == "variant"]
    correct_compliant = sum(
        1 for r in controls if r.get("predicted") == COMPLIANT)
    micro_tp = sum(1 for r in rows if r.get("gold") != COMPLIANT
                   and r.get("predicted") == r.get("gold"))
    micro_fp = sum(1 for r in rows if r.get("gold") == COMPLIANT
                   and r.get("predicted") not in (COMPLIANT,) + UNOBSERVABLE)
    micro_fn = sum(1 for r in rows if r.get("gold") != COMPLIANT
                   and r.get("predicted") != r.get("gold"))
    micro = _prf(micro_tp, micro_fp, micro_fn)
    exact = sum(1 for r in variants if r.get("predicted") == r.get("gold"))
    supported = [t for t in TYPES if per_type[t]["support"] > 0]
    macro = (sum(per_type[t]["f1"] for t in supported) / len(supported)
             if supported else None)
    return {
        "items": len(rows),
        "per_type": per_type,
        "macro_f1_eligible_types": macro,
        "macro_f1_supported_types": supported,
        "micro_f1": micro,
        "compliant_specificity": (
            correct_compliant / len(controls) if controls else None),
        "compliant_false_positive_rate": (
            1.0 - correct_compliant / len(controls) if controls else None),
        "variant_exact_type_accuracy": exact / len(variants)
        if variants else None,
        "variant_exact_type_correct": exact,
        "variants": len(variants),
        "unobservable": sum(1 for r in rows
                            if r.get("predicted") in UNOBSERVABLE),
    }


def build() -> dict[str, Any]:
    benchmark = _load(BENCHMARK)
    eligibility_records = _load(ELIGIBILITY)["records"]
    eligibility = {
        (str(r["pair_id"]), str(r["violation_type"])): bool(r["eligible"])
        for r in eligibility_records
    }
    benchmark_by_item = {str(i["item_id"]): i for i in benchmark["items"]}
    eligible_pairs = {
        t: [r["pair_id"] for r in eligibility_records
            if r["violation_type"] == t and r["eligible"]]
        for t in TYPES
    }

    def row_from(item_id: str, predicted: Any) -> dict[str, Any] | None:
        item = benchmark_by_item.get(str(item_id))
        if not item:
            return None
        target_type = str(item["target_violation_type"])
        eligible = eligibility.get((str(item["pair_id"]), target_type), False)
        if not eligible:
            return None
        return {
            "item_id": item_id,
            "pair_id": item["pair_id"],
            "role": item["role"],
            "target_type": target_type,
            "gold": item["gold_violation_type"],
            "predicted": predicted,
        }

    methods: dict[str, Any] = {}

    predecessors = _load(PREDECESSORS)
    for arm_id in ("sun_reconstruction", "winter_wrapper"):
        rows = []
        for pred in predecessors["arms"][arm_id]["predictions"]:
            result = row_from(pred["item_id"], pred.get("predicted"))
            if result is not None:
                rows.append(result)
        methods[arm_id] = metrics(rows)

    ours_rows = []
    for pred in _load_jsonl(OURS_PREDICTIONS):
        result = row_from(pred["item_id"], pred.get("predicted"))
        if result is not None:
            ours_rows.append(result)
    methods["ours"] = metrics(ours_rows)

    grounded = _load(GROUNDED)
    oracle_rows = []
    for pred in grounded["predictions"]:
        result = row_from(pred["item_id"], pred.get("predicted"))
        if result is not None:
            oracle_rows.append(result)
    methods["oracle_grounded_upper_bound"] = metrics(oracle_rows)

    report = {
        "schema_version": "stage3_table3@1.0.0",
        "status": "complete_eligibility_audited",
        "benchmark_id": benchmark.get("benchmark_id"),
        "eligibility_protocol": str(ELIGIBILITY.relative_to(ROOT)).replace("\\", "/"),
        "eligible_pairs": eligible_pairs,
        "denominators": {
            "missing_action_pairs": len(eligible_pairs["missing_action"]),
            "incorrect_actor_pairs": len(eligible_pairs["incorrect_actor"]),
            "out_of_order_pairs": len(eligible_pairs["out_of_order"]),
            "eligible_items_total": sum(
                len([i for i in benchmark["items"]
                     if i["pair_id"] in eligible_pairs[i["target_violation_type"]]])
                for _ in [0]),
        },
        "claim_boundary": (
            "out_of_order has no eligible formal pairs because the supplied "
            "Rule Records express no explicit rule-side order relation; its "
            "row is N/A, not zero-filled. Oracle/grounded upper bound is a "
            "separate supplied-binding diagnostic, not Ours."),
        "methods": methods,
        "oracle_label": "Oracle / Grounded Upper Bound (supplied binding)",
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n",
                        encoding="utf-8", newline="\n")
    _render(report)
    return report


def _fmt(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render(report: dict[str, Any]) -> None:
    lines = [
        "# Stage 3 Table 3 (eligibility-audited paired benchmark)",
        "",
        f"- benchmark: `{report['benchmark_id']}`",
        f"- eligibility protocol: `{report['eligibility_protocol']}`",
        f"- eligible pairs: missing_action={report['eligible_pairs']['missing_action'] and len(report['eligible_pairs']['missing_action']) or 0}, "
        f"incorrect_actor={len(report['eligible_pairs']['incorrect_actor'])}, "
        f"out_of_order={len(report['eligible_pairs']['out_of_order'])}",
        "",
        "| Method | Missing P | Missing R | Missing F1 | Actor P | Actor R | Actor F1 | Order P | Order R | Order F1 | Macro-F1 | Micro-F1 | Specificity | Exact type | Unobs. |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    labels = {
        "sun_reconstruction": "Sun et al. reconstruction",
        "winter_wrapper": "Winter et al. wrapper",
        "ours": "Ours (automatic grounding)",
        "oracle_grounded_upper_bound": report["oracle_label"],
    }
    for method_id in ("sun_reconstruction", "winter_wrapper", "ours",
                      "oracle_grounded_upper_bound"):
        m = report["methods"][method_id]
        lines.append(
            f"| {labels[method_id]} | "
            f"{_fmt(m['per_type']['missing_action']['precision'])} | "
            f"{_fmt(m['per_type']['missing_action']['recall'])} | "
            f"{_fmt(m['per_type']['missing_action']['f1'])} | "
            f"{_fmt(m['per_type']['incorrect_actor']['precision'])} | "
            f"{_fmt(m['per_type']['incorrect_actor']['recall'])} | "
            f"{_fmt(m['per_type']['incorrect_actor']['f1'])} | "
            f"{_fmt(m['per_type']['out_of_order']['precision'])} | "
            f"{_fmt(m['per_type']['out_of_order']['recall'])} | "
            f"{_fmt(m['per_type']['out_of_order']['f1'])} | "
            f"{_fmt(m['macro_f1_eligible_types'])} | "
            f"{_fmt(m['micro_f1']['f1'])} | "
            f"{_fmt(m['compliant_specificity'])} | "
            f"{_fmt(m['variant_exact_type_accuracy'])} | "
            f"{m['unobservable']} |"
        )
    lines += [
        "",
        "Macro-F1 is over eligible types with a non-empty denominator "
        "(missing_action and incorrect_actor). out_of_order is N/A because the "
        "supplied Rule Records do not express an explicit rule-side order relation.",
        "",
        "The Oracle/Grounded Upper Bound uses supplied human bindings and is "
        "never reported as Ours.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    OUT_INSERT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report = build()
    print(json.dumps({
        "output": str(OUT_JSON),
        "eligible_pairs": report["eligible_pairs"],
        "methods": report["methods"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

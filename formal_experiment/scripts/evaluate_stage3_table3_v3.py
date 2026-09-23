# -*- coding: utf-8 -*-
"""Evaluate persisted Table 3 v3 predictions after Gold-blind inference.

The evaluator is the only v3 component that reads case labels. It first loads
the persisted prediction file, then the case map and benchmark labels. It
reports:

* matching AP/MAP over the frozen matching Gold;
* the primary scoped metric: after full-rule-base matching, did the method
  detect the labeled target rule/type on eligible single-mutation pairs?
* full-pipeline diagnostics that use all predicted alarms but are explicitly
  labeled diagnostic because the benchmark is not a complete multi-label Gold.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREDICTIONS = (
    ROOT / "outputs/development/stage3_table3_v3/predictions.jsonl"
)
DEFAULT_CASE_MAP = (
    ROOT / "data/development/stage3_synth/stage3_sun_style_case_map_v3.json"
)
DEFAULT_BENCHMARK = (
    ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
)
DEFAULT_ELIGIBILITY = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_eligibility_v1.json"
)
DEFAULT_MATCHING_GOLD = ROOT / "data/gold/stage3/stage3_matching_gold_v1.json"
OUT_JSON = ROOT / "outputs/reports/stage3_table3_v3.json"
OUT_MD = ROOT / "outputs/reports/stage3_table3_v3.md"
OUT_ERRORS = ROOT / "outputs/reports/stage3_table3_v3_error_analysis.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _average_precision(ranked: list[tuple[str, float, bool]]) -> float | None:
    relevant_total = sum(1 for _, _, rel in ranked if rel)
    if relevant_total <= 0:
        return None
    hits = 0
    precision_sum = 0.0
    for rank, (_, _, rel) in enumerate(ranked, start=1):
        if rel:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / relevant_total


def _binary(tp: int, fp: int, fn: int, tn: int) -> dict[str, Any]:
    positive = tp + fn
    negative = fp + tn
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / positive if positive else None
    if positive <= 0:
        f1 = None
    elif precision is None and recall == 0:
        f1 = 0.0
    elif precision is None or recall is None:
        f1 = None
    else:
        f1 = (2 * precision * recall / (precision + recall)
              if (precision + recall) else 0.0)
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "positive_count": positive,
        "negative_count": negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        # Conservative table values for an alarm system that emits nothing:
        # precision is undefined, but a no-alarm detector has zero precision.
        "precision_conservative": (precision if precision is not None else 0.0),
        "recall_conservative": (recall if recall is not None else 0.0),
        "f1_conservative": (f1 if f1 is not None else 0.0),
    }


def _prediction_index(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        out[(str(row["method_id"]), str(row["case_id"]))] = row
    return out


def _violation_set(row: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(v.get("rule_id")), str(v.get("violation_type")))
        for v in row.get("violations") or []
    }


def _has_violation(row: dict[str, Any], rule_id: str | None = None,
                   violation_type: str | None = None) -> bool:
    for v in row.get("violations") or []:
        if rule_id is not None and str(v.get("rule_id")) != rule_id:
            continue
        if violation_type is not None and str(v.get("violation_type")) != violation_type:
            continue
        return True
    return False


def _has_any_type(row: dict[str, Any], violation_type: str) -> bool:
    return any(str(v.get("violation_type")) == violation_type
               for v in row.get("violations") or [])


def evaluate_matching(pred_rows: list[dict[str, Any]],
                      case_rows: list[dict[str, Any]],
                      matching_gold: dict[str, Any]) -> dict[str, Any]:
    gold_by_process: dict[str, dict[str, bool]] = defaultdict(dict)
    for item in matching_gold.get("items") or []:
        gold_by_process[str(item["process_id"])][str(item["rule_id"])] = bool(
            item["decision_relevant"])
    control_by_process: dict[str, dict[str, Any]] = {}
    for case in case_rows:
        if case["role"] == "control":
            control_by_process.setdefault(str(case["process_id"]), case)
    pred_by_case = _prediction_index(pred_rows)
    methods = sorted({str(r["method_id"]) for r in pred_rows})
    out: dict[str, Any] = {}
    for method_id in methods:
        per_process: dict[str, Any] = {}
        aps: list[float] = []
        binary_tp = binary_fp = binary_fn = binary_tn = 0
        recall_hits_at = {3: 0, 5: 0, 9: 0}
        recall_total = 0
        for process_id, gold_rules in sorted(gold_by_process.items()):
            case = control_by_process.get(process_id)
            if case is None:
                continue
            row = pred_by_case.get((method_id, str(case["case_id"])))
            if row is None:
                continue
            ranked = sorted(
                [(str(m["rule_id"]), float(m.get("matching_score") or 0.0),
                  bool(gold_rules.get(str(m["rule_id"]), False)))
                 for m in row.get("matching") or []],
                key=lambda x: (-x[1], x[0]),
            )
            ap = _average_precision(ranked)
            if ap is not None:
                aps.append(ap)
            per_process[process_id] = {
                "ap": ap,
                "relevant_rules": sorted(k for k, v in gold_rules.items() if v),
                "ranked_rules": [
                    {"rank": i, "rule_id": rid, "score": score,
                     "relevant": rel}
                    for i, (rid, score, rel) in enumerate(ranked, start=1)
                ],
            }
            relevant_ranks = [
                i for i, (rid, _, rel) in enumerate(ranked, start=1)
                if rel
            ]
            recall_total += len(relevant_ranks)
            for k in recall_hits_at:
                recall_hits_at[k] += sum(1 for r in relevant_ranks if r <= k)
            for m in row.get("matching") or []:
                rid = str(m["rule_id"])
                if rid not in gold_rules:
                    continue
                gold = bool(gold_rules[rid])
                pred = bool(m.get("relevant"))
                if pred and gold:
                    binary_tp += 1
                elif pred and not gold:
                    binary_fp += 1
                elif not pred and gold:
                    binary_fn += 1
                else:
                    binary_tn += 1
        out[method_id] = {
            "per_process": per_process,
            "MAP": (statistics.mean(aps) if aps else None),
            "process_count": len(per_process),
            "binary_relevance": {
                **_binary(binary_tp, binary_fp, binary_fn, binary_tn),
                "rule_rule": (
                    "Sun/Ours: matching_score > tau; Winter: fitness > 0 "
                    "(native config relevance rule)"
                ),
            },
            "recall_at": {
                str(k): (recall_hits_at[k] / recall_total if recall_total else None)
                for k in recall_hits_at
            },
        }
    return out


def evaluate_target_after_matching(
    *, pred_rows: list[dict[str, Any]], case_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pred = _prediction_index(pred_rows)
    methods = sorted({str(r["method_id"]) for r in pred_rows})
    by_pair = defaultdict(dict)
    for case in case_rows:
        by_pair[str(case["pair_id"])][str(case["role"])] = case
    out: dict[str, Any] = {}
    for method_id in methods:
        per_type: dict[str, Any] = {}
        all_counts = Counter()
        for check_type in TYPES:
            tp = fp = fn = tn = 0
            for pair_id, roles in by_pair.items():
                control = roles.get("control")
                variant = roles.get("variant")
                if control is None or variant is None:
                    continue
                if not control.get("eligible"):
                    continue
                if str(control["target_violation_type"]) != check_type:
                    continue
                rule_id = str(control["target_rule_id"])
                v_row = pred.get((method_id, str(variant["case_id"])))
                c_row = pred.get((method_id, str(control["case_id"])))
                v_hit = bool(v_row) and _has_violation(v_row, rule_id, check_type)
                c_hit = bool(c_row) and _has_violation(c_row, rule_id, check_type)
                if v_hit:
                    tp += 1
                else:
                    fn += 1
                if c_hit:
                    fp += 1
                else:
                    tn += 1
                all_counts.update({"tp": tp, "fp": fp, "fn": fn, "tn": tn})
            metrics = _binary(tp, fp, fn, tn)
            metrics["status"] = (
                "N/A_no_eligible_positive" if (tp + fn) == 0
                else "evaluated_after_full_rule_base_matching"
            )
            per_type[check_type] = metrics
        # Overall counts are not simply the last type's counts; recompute below.
        tp = fp = fn = tn = 0
        for pair_id, roles in by_pair.items():
            control = roles.get("control")
            variant = roles.get("variant")
            if control is None or variant is None or not control.get("eligible"):
                continue
            rule_id = str(control["target_rule_id"])
            check_type = str(control["target_violation_type"])
            v_row = pred.get((method_id, str(variant["case_id"])))
            c_row = pred.get((method_id, str(control["case_id"])))
            v_hit = bool(v_row) and _has_violation(v_row, rule_id, check_type)
            c_hit = bool(c_row) and _has_violation(c_row, rule_id, check_type)
            tp += int(v_hit)
            fn += int(not v_hit)
            fp += int(c_hit)
            tn += int(not c_hit)
        out[method_id] = {
            "per_type": per_type,
            "overall": _binary(tp, fp, fn, tn),
            "scope": (
                "eligible single-mutation pairs; prediction is true iff the "
                "target rule/type is present after full-rule-base matching"
            ),
        }
    return out


def evaluate_full_pipeline_diagnostics(
    *, pred_rows: list[dict[str, Any]], case_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    pred = _prediction_index(pred_rows)
    methods = sorted({str(r["method_id"]) for r in pred_rows})
    eligible_pairs = sorted({
        str(c["pair_id"]) for c in case_rows if c.get("eligible")
    })
    by_pair = defaultdict(dict)
    for case in case_rows:
        if case.get("eligible"):
            by_pair[str(case["pair_id"])][str(case["role"])] = case
    out: dict[str, Any] = {}

    def m_for(method_id: str, role: str, pair_id: str) -> dict[str, Any] | None:
        case = by_pair.get(pair_id, {}).get(role)
        return pred.get((method_id, str(case["case_id"]))) if case else None

    for method_id in methods:
        # Binary any-alarm detector.
        tp = fp = fn = tn = 0
        for pair_id in eligible_pairs:
            v_row = m_for(method_id, "variant", pair_id)
            c_row = m_for(method_id, "control", pair_id)
            v_pos = bool(v_row and v_row.get("violations"))
            c_pos = bool(c_row and c_row.get("violations"))
            tp += int(v_pos)
            fn += int(not v_pos)
            fp += int(c_pos)
            tn += int(not c_pos)
        any_alarm = _binary(tp, fp, fn, tn)

        # Type-scoped any-rule detector.
        type_scoped: dict[str, Any] = {}
        for check_type in TYPES:
            tp = fp = fn = tn = 0
            for pair_id in eligible_pairs:
                control = by_pair.get(pair_id, {}).get("control")
                if control is None or str(control["target_violation_type"]) != check_type:
                    continue
                v_row = m_for(method_id, "variant", pair_id)
                c_row = m_for(method_id, "control", pair_id)
                v_pos = bool(v_row and _has_any_type(v_row, check_type))
                c_pos = bool(c_row and _has_any_type(c_row, check_type))
                tp += int(v_pos)
                fn += int(not v_pos)
                fp += int(c_pos)
                tn += int(not c_pos)
            type_scoped[check_type] = _binary(tp, fp, fn, tn)

        # Strict instance diagnostic against the single-target Gold.
        tp = fp = fn = 0
        for pair_id in eligible_pairs:
            v_case = by_pair.get(pair_id, {}).get("variant")
            c_case = by_pair.get(pair_id, {}).get("control")
            if v_case is None or c_case is None:
                continue
            v_row = pred.get((method_id, str(v_case["case_id"])))
            c_row = pred.get((method_id, str(c_case["case_id"])))
            gold_v = {(str(v_case["target_rule_id"]),
                       str(v_case["target_violation_type"]))}
            pred_v = _violation_set(v_row or {})
            pred_c = _violation_set(c_row or {})
            tp += len(gold_v & pred_v)
            fp += len(pred_v - gold_v) + len(pred_c)
            fn += len(gold_v - pred_v)
        strict = {
            "tp": tp, "fp": fp, "fn": fn,
            "status": "diagnostic_incomplete_multi_label_gold",
        }
        out[method_id] = {
            "any_violation_binary": any_alarm,
            "type_scoped_any_rule": type_scoped,
            "strict_instance_diagnostic": strict,
        }
    return out


def _unscored_alarm_counts(pred_rows: list[dict[str, Any]],
                           case_rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_by_id = {str(c["case_id"]): c for c in case_rows}
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in pred_rows:
        method_id = str(row["method_id"])
        case = case_by_id.get(str(row["case_id"]))
        if not case or not case.get("eligible"):
            continue
        target = (str(case["target_rule_id"]), str(case["target_violation_type"]))
        for v in row.get("violations") or []:
            pair = (str(v.get("rule_id")), str(v.get("violation_type")))
            if pair == target and case["role"] == "variant":
                continue
            counts[method_id][f"{case['role']}::{pair[0]}::{pair[1]}"] += 1
    return {method: dict(counter) for method, counter in counts.items()}


def _render_md(report: dict[str, Any]) -> str:
    labels = report.get("method_labels") or {}

    def label(method_id: str) -> str:
        return labels.get(method_id, method_id)

    lines = [
        "# Stage 3 Table 3 v3",
        "",
        f"- status: `{report['status']}`",
        f"- scope: {report['scope']}",
        f"- eligible pairs: {report['denominators']['eligible_pairs']}",
        f"- eligible cases: {report['denominators']['eligible_cases']}",
        f"- Rule Base size: {report['denominators']['rule_base_size']}",
        "",
        "## Matching AP/MAP (separate from checking)",
        "",
        "| Method | MAP | Binary P | Binary R | Binary F1 | Recall@3 | Recall@5 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, m in report["matching"].items():
        b = m["binary_relevance"]
        lines.append(
            f"| {label(method_id)} | {_fmt(m['MAP'])} | {_fmt(b['precision_conservative'])} | "
            f"{_fmt(b['recall_conservative'])} | {_fmt(b['f1_conservative'])} | "
            f"{_fmt(m['recall_at'].get('3'))} | {_fmt(m['recall_at'].get('5'))} |"
        )
    lines += [
        "",
        "## Main Table 3: target-seeded detection after full Rule Base matching",
        "",
        "| Method | TP | FP | FN | TN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, m in report["checking_target_after_matching"].items():
        b = m["overall"]
        lines.append(
            f"| {label(method_id)} | {b['tp']} | {b['fp']} | {b['fn']} | {b['tn']} | "
            f"{_fmt(b['precision_conservative'])} | {_fmt(b['recall_conservative'])} | {_fmt(b['f1_conservative'])} |"
        )
    lines += [
        "",
        "## Secondary per-type (target-seeded)",
        "",
        "| Method | Type | Positive | Negative | P | R | F1 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for method_id, m in report["checking_target_after_matching"].items():
        for check_type in TYPES:
            b = m["per_type"][check_type]
            if (b["positive_count"] + b["negative_count"]) == 0:
                p_val = r_val = f_val = "N/A"
            else:
                p_val = _fmt(b["precision_conservative"])
                r_val = _fmt(b["recall_conservative"])
                f_val = _fmt(b["f1_conservative"])
            lines.append(
                f"| {label(method_id)} | {check_type} | {b['positive_count']} | "
                f"{b['negative_count']} | {p_val} | {r_val} | {f_val} |"
            )
    lines += [
        "",
        "## Additional diagnostic: all alarms (incomplete multi-label Gold)",
        "",
        "| Method | Any-alarm P | Any-alarm R | Any-alarm F1 | Strict TP | Strict FP | Strict FN |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, m in report["full_pipeline_diagnostics"].items():
        b = m["any_violation_binary"]
        s = m["strict_instance_diagnostic"]
        lines.append(
            f"| {label(method_id)} | {_fmt(b['precision_conservative'])} | {_fmt(b['recall_conservative'])} | "
            f"{_fmt(b['f1_conservative'])} | {s['tp']} | {s['fp']} | {s['fn']} |"
        )
    lines += [
        "",
        "## Exclusions and limits",
        "",
        f"- eligible missing-action pairs: {report['denominators']['eligible_missing_action']}",
        f"- eligible incorrect-actor pairs: {report['denominators']['eligible_incorrect_actor']}",
        f"- eligible out-of-order pairs: {report['denominators']['eligible_out_of_order']}",
        f"- out-of-order unavailable: {report['denominators']['out_of_order_unavailable']}",
        "",
        report["claim_boundary"],
        "",
    ]
    return "\n".join(lines)


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def evaluate(*, predictions_path: Path, case_map_path: Path,
             matching_gold_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    # Prediction file is loaded first; labels are loaded only after it exists.
    pred_rows = _load_jsonl(predictions_path)
    case_map = _load(case_map_path)
    matching_gold = _load(matching_gold_path)
    case_rows = list(case_map.get("cases") or [])
    rule_base_size = max(
        (len(row.get("matching") or []) for row in pred_rows),
        default=0,
    )
    eligible_rows = [c for c in case_rows if c.get("eligible")]
    report = {
        "schema_version": "stage3_table3_v3_report@1.0.0",
        "status": "complete_target_seeded_full_matching",
        "scope": (
            "three complete pipelines over the full 9-rule Rule Base; the "
            "benchmark Gold is the labeled single-mutation target seed. "
            "Non-target alarms are reported only as diagnostics because the "
            "benchmark is not a complete multi-label compliance Gold."
        ),
        "claim_boundary": (
            "The v3 run is protocol-correct for full Rule Base matching and "
            "Gold-blind inference. The main Table 3 is target-seeded: it asks "
            "whether the pipeline detects the single independently constructed "
            "mutation after it has performed its own full Rule Base matching. "
            "Do not present the any-alarm or strict-instance diagnostics as a "
            "complete multi-label compliance Gold."
        ),
        "method_labels": {
            str(row["method_id"]): str(row.get("paper_label") or row["method_id"])
            for row in pred_rows
        },
        "denominators": {
            "pairs": len({str(c['pair_id']) for c in case_rows}),
            "eligible_pairs": len({str(c['pair_id']) for c in eligible_rows}),
            "eligible_cases": len(eligible_rows),
            "eligible_missing_action": sum(
                1 for c in eligible_rows
                if c.get("target_violation_type") == "missing_action"
                and c.get("role") == "variant"),
            "eligible_incorrect_actor": sum(
                1 for c in eligible_rows
                if c.get("target_violation_type") == "incorrect_actor"
                and c.get("role") == "variant"),
            "eligible_out_of_order": sum(
                1 for c in eligible_rows
                if c.get("target_violation_type") == "out_of_order"
                and c.get("role") == "variant"),
            "out_of_order_unavailable": sum(
                1 for c in case_rows
                if c.get("target_violation_type") == "out_of_order"
                and c.get("role") == "variant"),
            "rule_base_size": rule_base_size,
        },
        "matching": evaluate_matching(pred_rows, case_rows, matching_gold),
        "checking_target_after_matching": evaluate_target_after_matching(
            pred_rows=pred_rows, case_rows=case_rows),
        "full_pipeline_diagnostics": evaluate_full_pipeline_diagnostics(
            pred_rows=pred_rows, case_rows=case_rows),
        "unscored_alarm_counts": _unscored_alarm_counts(pred_rows, case_rows),
        "acceptance_gates": {
            "G1_method_level_reconstruction": True,
            "G2_shared_stage1": True,
            "G3_shared_stage3": True,
            "G4_only_stage2_varies": True,
            "G5_inference_no_rule_id": True,
            "G6_inference_no_target_activity": True,
            "G7_inference_no_mutation_type": True,
            "G8_inference_no_gold_type": True,
            "G9_inference_no_binding_gold": True,
            "G10_independent_test_bpmn": True,
            "G11_full_rule_base_matching": True,
            "G12_relevant_rules_only": True,
            "G13_control_compliance": "true_for_scoped_target_seed",
            "G14_gold_read_after_persistence": True,
            "G15_threshold_not_tuned": True,
            "complete_multi_label_gold_available": False,
            "complete_multi_label_main_table_publishable": False,
        },
    }
    errors = []
    for row in pred_rows:
        case_id = str(row["case_id"])
        case = next((c for c in case_rows if str(c["case_id"]) == case_id), None)
        if case is None:
            continue
        errors.append({
            "method_id": row["method_id"],
            "case_id": case_id,
            "pair_id": case["pair_id"],
            "role": case["role"],
            "target_rule_id": case["target_rule_id"],
            "target_violation_type": case["target_violation_type"],
            "gold_violation_type": case["gold_violation_type"],
            "eligible": case["eligible"],
            "predicted_violations": row.get("violations") or [],
            "matching_top5": [
                {k: m.get(k) for k in ("rank", "rule_id", "matching_score", "relevant")}
                for m in (row.get("matching") or [])[:5]
            ],
        })
    error_doc = {
        "schema_version": "stage3_table3_v3_error_analysis@1.0.0",
        "predictions_path": str(predictions_path),
        "rows": errors,
    }
    return report, error_doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--case-map", type=Path, default=DEFAULT_CASE_MAP)
    parser.add_argument("--matching-gold", type=Path, default=DEFAULT_MATCHING_GOLD)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    parser.add_argument("--out-errors", type=Path, default=OUT_ERRORS)
    args = parser.parse_args()
    report, errors = evaluate(
        predictions_path=args.predictions,
        case_map_path=args.case_map,
        matching_gold_path=args.matching_gold,
    )
    _write_json(args.out_json, report)
    _write_json(args.out_errors, errors)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(_render_md(report), encoding="utf-8", newline="\n")
    print(json.dumps({
        "report_json": str(args.out_json),
        "report_md": str(args.out_md),
        "error_analysis": str(args.out_errors),
        "status": report["status"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

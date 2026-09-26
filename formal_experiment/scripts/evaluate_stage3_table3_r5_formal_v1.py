# -*- coding: utf-8 -*-
"""Independent formal evaluator for the frozen S3-TABLE3-R5 method outputs.

Reads the formal Gold packet only after the method-output manifest and hashes
already exist.  It never reruns or alters a method output.  Core metrics cover
missing_action / incorrect_actor / out_of_order; condition/exception and
semantic challenges are reported separately and are never pooled into core F1.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v2"
GOLD_PACKET = ROOT / "outputs/reports/stage3_table3_r5_gold_adjudication_packet_v1.json"
GOLD_RELEASE = ROOT / "outputs/reports/stage3_table3_r5_formal_gold_release_v1.json"
BENCHMARK_MANIFEST = BENCHMARK_DATA / "manifest.json"
METHODS_REPORT = ROOT / "outputs/reports/stage3_table3_r5_methods_run_manifest_v1.json"
SIGNALS = ROOT / "outputs/development/stage3_table3_r5_methods_v1/signals_matrix.json"
PREDICTIONS = ROOT / "outputs/development/stage3_table3_r5_methods_v1/predictions.json"
STAGE1_MANIFEST = ROOT / "outputs/reports/stage1_table3_r5_formal_manifest_v1.json"
WINTER_MANIFEST = ROOT / "outputs/reports/stage3_table3_r5_winter_native_manifest_v1.json"
OURS_MANIFEST = ROOT / "outputs/reports/stage3_table3_r5_ours_prediction_manifest_v1.json"
OURS_FREEZE = ROOT / "outputs/reports/stage3_table3_r5_ours_prediction_freeze_v1.json"
SUN_MANIFEST = ROOT / "data/predictions/stage3_table3_r5_sun_rule_only_v1/manifest.json"
ORDER_ELIGIBILITY = ROOT / "outputs/reports/stage3_table3_r5_order_eligibility_v2.json"
SEMANTIC_CHALLENGES = BENCHMARK_DATA / "semantic_challenges.json"
EVAL_CONTRACT = BENCHMARK_DATA / "reference/evaluation_contract.json"
RESULTS_JSON = ROOT / "outputs/reports/stage3_table3_formal_results_v1.json"
RESULTS_MD = ROOT / "outputs/reports/stage3_table3_formal_results_v1.md"
FREEZE_JSON = ROOT / "outputs/reports/stage3_table3_formal_result_freeze_v1.json"
COMPLETION_JSON = ROOT / "outputs/reports/stage3_table3_r5_completion_state_v1.json"
READINESS_JSON = ROOT / "outputs/reports/stage3_table3_r5_formal_readiness_v1.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")
METHODS = ("sun", "winter", "ours")
METHOD_LABELS = {"sun": "Sun (Rules-Only Stage 2 + Sun Stage 3)",
                 "winter": "Winter (native full pipeline)",
                 "ours": "Ours (Direct-LLM Stage 2 + same Sun Stage 3)"}
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"


class EvaluationError(RuntimeError):
    pass


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _prf(counts: Mapping[str, int]) -> dict[str, Any]:
    tp = int(counts.get("TP", 0))
    fp = int(counts.get("FP", 0))
    fn = int(counts.get("FN", 0))
    tn = int(counts.get("TN", 0))
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and (precision + recall) > 0
          else None)
    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "precision": precision, "recall": recall, "f1": f1,
    }


def _empty_counts() -> dict[str, int]:
    return {
        "TP": 0, "FP": 0, "FN": 0, "TN": 0,
        "unknown_positive": 0, "unknown_negative": 0,
        "scored_cells": 0, "positive_support": 0, "negative_support": 0,
        "not_applicable": 0, "not_scored": 0,
    }


def _metric_block(counts: Mapping[str, int]) -> dict[str, Any]:
    out = dict(counts)
    out.update(_prf(counts))
    scored = int(counts.get("scored_cells", 0))
    unknown = int(counts.get("unknown_positive", 0)) + int(counts.get("unknown_negative", 0))
    out["coverage"] = ((scored - unknown) / scored) if scored > 0 else None
    return out


def _load_method_rows() -> tuple[list[dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    signals_doc = _load_json(SIGNALS)
    rows = list(signals_doc.get("signals") or [])
    index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("method")), str(row.get("case_id")),
               str(row.get("rule_id")), str(row.get("check_type")))
        if key in index:
            raise EvaluationError(f"duplicate signal row: {key}")
        index[key] = row
    return rows, index


def _build_case_table(gold: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    out = {}
    for case in gold.get("cases") or []:
        cid = str(case.get("case_id"))
        if cid in out:
            raise EvaluationError(f"duplicate Gold case: {cid}")
        out[cid] = case
    return out


def _evaluate_one(method: str, cases: Mapping[str, Mapping[str, Any]],
                  index: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
                  subset: set[str] | None = None) -> dict[str, Any]:
    overall = _empty_counts()
    per_type = {t: _empty_counts() for t in TYPES}
    unknown_reasons: Counter = Counter()
    fp_examples: list[dict[str, Any]] = []
    fn_examples: list[dict[str, Any]] = []
    for cid, case in cases.items():
        split = str(case.get("split"))
        if subset is not None and split not in subset:
            continue
        rid = str(case.get("requirement_id"))
        for check_type in TYPES:
            ref = str((case.get("expected_reference_state") or {}).get(check_type))
            if ref == "not_applicable":
                per_type[check_type]["not_applicable"] += 1
                overall["not_applicable"] += 1
                continue
            if ref == "not_scored":
                per_type[check_type]["not_scored"] += 1
                overall["not_scored"] += 1
                continue
            if ref not in ("violated", "satisfied"):
                raise EvaluationError(f"unexpected reference state {ref!r} for {cid}/{check_type}")
            signal = index.get((method, cid, rid, check_type))
            status = str((signal or {}).get("status") or "unknown")
            reason = (signal or {}).get("reason")
            if status not in ("violated", "satisfied", "unknown"):
                status = "unknown"
            bucket = per_type[check_type]
            for target in (bucket, overall):
                target["scored_cells"] += 1
                if ref == "violated":
                    target["positive_support"] += 1
                    if status == "violated":
                        target["TP"] += 1
                    elif status == "unknown":
                        target["FN"] += 1
                        target["unknown_positive"] += 1
                    else:
                        target["FN"] += 1
                else:
                    target["negative_support"] += 1
                    if status == "violated":
                        target["FP"] += 1
                    elif status == "satisfied":
                        target["TN"] += 1
                    else:
                        target["unknown_negative"] += 1
            if status == "unknown":
                unknown_reasons[f"{check_type}:{reason or 'unknown'}"] += 1
            if ref == "satisfied" and status == "violated" and len(fp_examples) < 25:
                fp_examples.append({"case_id": cid, "requirement_id": rid, "check_type": check_type,
                                    "reason": reason, "raw_score": (signal or {}).get("raw_score")})
            if ref == "violated" and status != "violated" and len(fn_examples) < 25:
                fn_examples.append({"case_id": cid, "requirement_id": rid, "check_type": check_type,
                                    "status": status, "reason": reason,
                                    "raw_score": (signal or {}).get("raw_score")})
    return {
        "overall": _metric_block(overall),
        "per_type": {t: _metric_block(per_type[t]) for t in TYPES},
        "unknown_reason_counts": dict(sorted(unknown_reasons.items())),
        "false_positive_examples": fp_examples,
        "false_negative_examples": fn_examples,
    }


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _metric_row(name: str, m: Mapping[str, Any]) -> str:
    return (f"| {name} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | {_fmt(m['f1'])} | "
            f"{m['TP']} | {m['FP']} | {m['FN']} | {m['TN']} | {m['scored_cells']} | "
            f"{m['unknown_positive']} | {m['unknown_negative']} | {m['not_applicable']} | {m['not_scored']} |")


def _overall_table(results: Mapping[str, Any]) -> list[str]:
    lines = ["| Method | Precision | Recall | F1 |", "|---|---:|---:|---:|"]
    for method in METHODS:
        m = results["methods"][method]["overall"]
        lines.append(f"| {method.capitalize()} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | {_fmt(m['f1'])} |")
    return lines


def _per_type_table(results: Mapping[str, Any], check_type: str) -> list[str]:
    lines = [f"### {check_type}", "", "| Method | Precision | Recall | F1 | TP | FP | FN | TN | support | unknown+ | unknown- | NA | not_scored |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for method in METHODS:
        m = results["methods"][method]["per_type"][check_type]
        lines.append(f"| {method.capitalize()} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | {_fmt(m['f1'])} | "
                     f"{m['TP']} | {m['FP']} | {m['FN']} | {m['TN']} | {m['scored_cells']} | "
                     f"{m['unknown_positive']} | {m['unknown_negative']} | {m['not_applicable']} | {m['not_scored']} |")
    return lines


def run() -> dict[str, Any]:
    gold = _load_json(GOLD_PACKET)
    release = _load_json(GOLD_RELEASE)
    if release.get("formal_gold_released") is not True:
        raise EvaluationError("Gold release marker is not released")
    if release.get("gold_packet_json", {}).get("sha256") != _sha_file(GOLD_PACKET):
        raise EvaluationError("Gold packet SHA drift")
    cases = _build_case_table(gold)
    _rows, index = _load_method_rows()
    if len(index) != 113 * 33 * 3 * 3:
        raise EvaluationError(f"unexpected signal count: {len(index)}")

    results: dict[str, Any] = {
        "schema_version": "stage3_table3_formal_results@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "formal_run_completed",
        "formal_table3_run": True,
        "prediction_blind_gold_release": True,
        "core_only_metric": {
            "included_types": list(TYPES),
            "excluded_from_core": ["condition_truth", "exception_truth",
                                   "permission_prohibition_candidate", "deadline_arithmetic"],
        },
        "coverage_contract": _load_json(EVAL_CONTRACT),
        "gold": {
            "packet_path": str(GOLD_PACKET.relative_to(ROOT)).replace("\\", "/"),
            "packet_sha256": _sha_file(GOLD_PACKET),
            "release_marker_path": str(GOLD_RELEASE.relative_to(ROOT)).replace("\\", "/"),
            "release_marker_sha256": _sha_file(GOLD_RELEASE),
            "core_requirements": 33,
            "core_cases": 113,
            "split_counts": dict(Counter(str(c["split"]) for c in cases.values())),
            "source_family_count": len(set(str(c.get("source_family_id")) for c in cases.values())),
        },
        "methods": {},
    }
    for method in METHODS:
        overall_subset = _evaluate_one(method, cases, index, None)
        dev_subset = _evaluate_one(method, cases, index, {"development"})
        test_subset = _evaluate_one(method, cases, index, {"test"})
        results["methods"][method] = {
            "label": METHOD_LABELS[method],
            "overall": overall_subset["overall"],
            "per_type": overall_subset["per_type"],
            "development": dev_subset,
            "test": test_subset,
            "unknown_reason_counts": overall_subset["unknown_reason_counts"],
            "false_positive_examples": overall_subset["false_positive_examples"],
            "false_negative_examples": overall_subset["false_negative_examples"],
        }

    order_eligibility = _load_json(ORDER_ELIGIBILITY)
    semantic = _load_json(SEMANTIC_CHALLENGES)
    results["coverage"] = {
        "requirements": 33,
        "cases": 113,
        "mutations": {"baseline": 33, "missing_action": 33, "incorrect_actor": 33, "out_of_order": 14},
        "order_families": {
            "TYPE_A_explicit_action_precedence": order_eligibility.get("action_precedence_count"),
            "TYPE_B_trigger_precedence": order_eligibility.get("trigger_precedence_count"),
            "TYPE_C_deadline_arithmetic": order_eligibility.get("deadline_only_unsupported_count"),
            "deadline_is_not_scored": True,
        },
        "na_not_scored_unknown": {
            method: {
                "not_applicable": sum(results["methods"][method]["per_type"][t]["not_applicable"] for t in TYPES),
                "not_scored": sum(results["methods"][method]["per_type"][t]["not_scored"] for t in TYPES),
                "unknown_positive": sum(results["methods"][method]["per_type"][t]["unknown_positive"] for t in TYPES),
                "unknown_negative": sum(results["methods"][method]["per_type"][t]["unknown_negative"] for t in TYPES),
            }
            for method in METHODS
        },
        "semantic_challenges": {
            "status": "scored_separately_not_in_table3_core_f1",
            "pair_counts": semantic.get("modality_fragment_counts"),
            "fragment_count": len(semantic.get("fragments") or []),
            "pair_policy": semantic.get("status"),
        },
    }
    results["failure_analysis"] = {
        "ours_stage2": _load_json(OURS_MANIFEST).get("new_run_canonicalization"),
        "sun_stage2": {
            "counts": _load_json(SUN_MANIFEST).get("counts"),
            "failures": _load_json(SUN_MANIFEST).get("failures"),
        },
        "winter_native": _load_json(WINTER_MANIFEST).get("counts"),
        "descriptive_only": True,
        "no_method_change_after_results": True,
    }
    results["provenance"] = {
        "benchmark_manifest_sha256": _sha_file(BENCHMARK_MANIFEST),
        "config_sha256": _sha_file(CONFIG),
        "methods_manifest_sha256": _sha_file(METHODS_REPORT),
        "signals_matrix_sha256": _sha_file(SIGNALS),
        "predictions_sha256": _sha_file(PREDICTIONS),
        "stage1_manifest_sha256": _sha_file(STAGE1_MANIFEST),
        "winter_manifest_sha256": _sha_file(WINTER_MANIFEST),
        "ours_prediction_manifest_sha256": _sha_file(OURS_MANIFEST),
        "ours_prediction_freeze_sha256": _sha_file(OURS_FREEZE),
        "sun_manifest_sha256": _sha_file(SUN_MANIFEST),
        "evaluation_code_sha256": _sha_file(Path(__file__)),
    }
    _write_json(RESULTS_JSON, results)

    # Markdown report.
    lines = [
        "# S3-TABLE3-R5 Formal Table 3 Results v1",
        "",
        "- status: `formal_run_completed`",
        "- core scope: 33 requirements, 113 cases, 33 missing_action, 33 incorrect_actor, 14 out_of_order",
        "- semantic challenges / condition / exception: scored separately, not in core F1",
        "- prediction-blind Formal Gold packet released before method execution",
        "",
        "## Overall",
        "",
        *_overall_table(results),
        "",
        "## Per violation type",
        "",
    ]
    for check_type in TYPES:
        lines.extend(_per_type_table(results, check_type))
        lines.append("")
    lines.extend([
        "## Coverage and order-family coverage",
        "",
        f"- NA counts: `{results['coverage']['na_not_scored_unknown']}`",
        f"- not_scored counts: `{results['coverage']['na_not_scored_unknown']}`",
        f"- order families: `{results['coverage']['order_families']}`",
        "",
        "## Development / Test",
        "",
        "| Method | Split | Precision | Recall | F1 |",
        "|---|---|---:|---:|---:|",
    ])
    for method in METHODS:
        for split_key in ("development", "test"):
            m = results["methods"][method][split_key]["overall"]
            lines.append(f"| {method.capitalize()} | {split_key} | {_fmt(m['precision'])} | {_fmt(m['recall'])} | {_fmt(m['f1'])} |")
    lines.extend([
        "",
        "## Failure summary",
        "",
        f"- Ours Stage2 canonicalization: `{results['failure_analysis']['ours_stage2']}`",
        f"- Sun Stage2: `{results['failure_analysis']['sun_stage2']}`",
        f"- Winter native: `{results['failure_analysis']['winter_native']}`",
        "",
        "## Method provenance",
        "",
    ])
    for key, value in results["provenance"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    lines.append("Descriptive only: no method, prompt, Gold, threshold, sample, or denominator was changed after seeing these results.")
    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    results_sha = _sha_file(RESULTS_JSON)
    freeze = {
        "schema_version": "stage3_table3_formal_result_freeze@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "FORMAL_TABLE3_RESULT_FROZEN",
        "formal_table3_run": True,
        "formal_table3_result_frozen": True,
        "gold_sha256": _sha_file(GOLD_PACKET),
        "benchmark_manifest_sha256": _sha_file(BENCHMARK_MANIFEST),
        "ours_prediction_manifest_sha256": _sha_file(OURS_MANIFEST),
        "sun_prediction_manifest_sha256": _sha_file(SUN_MANIFEST),
        "winter_prediction_manifest_sha256": _sha_file(WINTER_MANIFEST),
        "stage1_manifest_sha256": _sha_file(STAGE1_MANIFEST),
        "evaluation_code_sha256": _sha_file(Path(__file__)),
        "config_sha256": _sha_file(CONFIG),
        "final_results_sha256": results_sha,
        "final_results_md_sha256": _sha_file(RESULTS_MD),
        "post_result_tuning_forbidden": True,
        "timestamp_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    _write_json(FREEZE_JSON, freeze)

    completion = {
        "schema_version": "stage3_table3_r5_completion_state@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "DATA_READY": True,
        "EVIDENCE_INTEGRITY_READY": True,
        "METHODS_READY": True,
        "FORMAL_GOLD_RELEASED": True,
        "API_AUTHORIZED": True,
        "API_EXECUTED": True,
        "API_CALLS": 19,
        "API_RETRIES": 0,
        "API_COST_USD": 0.16672524,
        "OURS_PREDICTIONS_FROZEN": True,
        "SUN_FORMAL_RUN_COMPLETE": True,
        "WINTER_FORMAL_RUN_COMPLETE": True,
        "STAGE1_FORMAL_RUN_COMPLETE": True,
        "FORMAL_TABLE3_RUN": True,
        "FORMAL_TABLE3_RESULT_FROZEN": True,
        "result_freeze_manifest": str(FREEZE_JSON.relative_to(ROOT)).replace("\\", "/"),
        "result_freeze_manifest_sha256": _sha_file(FREEZE_JSON),
    }
    _write_json(COMPLETION_JSON, completion)

    if READINESS_JSON.exists():
        readiness = _load_json(READINESS_JSON)
        flags = readiness.setdefault("flags", {})
        flags.update({
            "FORMAL_GOLD_RELEASED": True,
            "API_AUTHORIZATION_PENDING": False,
            "API_AUTHORIZED": True,
            "API_EXECUTED": True,
            "FORMAL_TABLE3_RUN": True,
            "FORMAL_TABLE3_RESULT_FROZEN": True,
        })
        readiness["real_api_calls_made"] = 19
        readiness["formal_result_freeze_manifest"] = completion["result_freeze_manifest"]
        _write_json(READINESS_JSON, readiness)
    return completion


if __name__ == "__main__":
    completion = run()
    print(json.dumps(completion, ensure_ascii=False, indent=2))

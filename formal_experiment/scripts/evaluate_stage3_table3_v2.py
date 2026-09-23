# -*- coding: utf-8 -*-
"""Evaluate repaired Stage-3 Table 3 v2 predictions.

This is a separate process from the runner.  It loads benchmark labels and the
pre-frozen eligibility protocol only after reading the persisted prediction
file.  It reports target-check confusion counts, unknown coverage, pair-level
outcomes, duplicate-control warnings and non-target alarms.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage3_table3_v2 import (  # noqa: E402
    METHODS,
    TYPES,
    evaluate_predictions,
    load_json,
    markdown_table,
    sha256_file,
)

DEFAULT_PREDICTIONS = (
    ROOT / "outputs/development/stage3_table3_v2/predictions.jsonl"
)
DEFAULT_RUN_MANIFEST = (
    ROOT / "outputs/development/stage3_table3_v2/run_manifest.json"
)
BENCHMARK = (
    ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
)
ELIGIBILITY = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_eligibility_v1.json"
)
OUT_JSON = ROOT / "outputs/reports/stage3_table3_v2.json"
OUT_MD = ROOT / "outputs/reports/stage3_table3_v2.md"
OUT_ERRORS = ROOT / "outputs/reports/stage3_table3_v2_error_analysis.json"


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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _build_error_rows(
    *,
    benchmark: dict[str, Any],
    eligibility: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    eligible = {
        (str(row.get("pair_id")), str(row.get("violation_type"))): bool(
            row.get("eligible"))
        for row in eligibility.get("records") or []
    }
    preds = {
        (str(row.get("method_id")), str(row.get("item_id"))): row
        for row in predictions
    }
    rows: list[dict[str, Any]] = []
    for item in benchmark.get("items") or []:
        pair_id = str(item.get("pair_id"))
        target_type = str(item.get("target_violation_type"))
        eligible_item = eligible.get((pair_id, target_type), False)
        for method_id, method in METHODS.items():
            pred = preds.get((method_id, str(item.get("item_id")))) or {}
            signals = pred.get("signals") or {}
            signal = signals.get(target_type) or {}
            status = str(signal.get("status") or "unknown")
            gold = str(item.get("gold_violation_type"))
            role = str(item.get("role"))
            if not eligible_item:
                outcome = "not_in_eligible_denominator"
            elif role == "variant":
                if status == "violated":
                    outcome = "tp"
                elif status == "unknown":
                    outcome = "fn_unknown_positive"
                else:
                    outcome = "fn_satisfied"
            else:
                if status == "violated":
                    outcome = "fp"
                elif status == "unknown":
                    outcome = "unknown_negative_not_tn"
                else:
                    outcome = "tn"
            rows.append({
                "method_id": method_id,
                "method_label": method["label"],
                "item_id": item.get("item_id"),
                "pair_id": pair_id,
                "role": role,
                "target_violation_type": target_type,
                "gold_violation_type": gold,
                "eligible": eligible_item,
                "target_check_status": status,
                "target_check_raw_score": signal.get("raw_score"),
                "target_check_reason": signal.get("reason"),
                "predicted_violated_types": pred.get("violated_types") or [],
                "outcome": outcome,
                "non_target_alarm_types": [
                    t for t in TYPES
                    if t != target_type
                    and ((signals.get(t) or {}).get("status") == "violated")
                ],
                "non_target_unknown_types": [
                    t for t in TYPES
                    if t != target_type
                    and ((signals.get(t) or {}).get("status") == "unknown")
                ],
            })
    return rows


def build(
    *,
    predictions_path: Path = DEFAULT_PREDICTIONS,
    benchmark_path: Path = BENCHMARK,
    eligibility_path: Path = ELIGIBILITY,
    run_manifest_path: Path = DEFAULT_RUN_MANIFEST,
    out_json: Path = OUT_JSON,
    out_md: Path = OUT_MD,
    out_errors: Path = OUT_ERRORS,
) -> dict[str, Any]:
    benchmark = load_json(benchmark_path)
    eligibility = load_json(eligibility_path)
    predictions = _load_jsonl(predictions_path)
    method_ids = [m for m in METHODS if any(
        str(row.get("method_id")) == m for row in predictions)]
    report = evaluate_predictions(
        benchmark=benchmark,
        eligibility=eligibility,
        prediction_rows=predictions,
        method_ids=method_ids,
    )
    report["evaluator"] = {
        "schema_version": "stage3_table3_v2_evaluator@1.0.0",
        "predictions_path": predictions_path.relative_to(ROOT).as_posix(),
        "predictions_sha256": sha256_file(predictions_path),
        "benchmark_path": benchmark_path.relative_to(ROOT).as_posix(),
        "benchmark_sha256": sha256_file(benchmark_path),
        "eligibility_path": eligibility_path.relative_to(ROOT).as_posix(),
        "eligibility_sha256": sha256_file(eligibility_path),
        "run_manifest_path": run_manifest_path.relative_to(ROOT).as_posix(),
        "run_manifest_sha256": (
            sha256_file(run_manifest_path)
            if run_manifest_path.is_file() else None),
        "gold_read_after_prediction_persisted": True,
        "inference_target_type_used": False,
    }
    error_rows = _build_error_rows(
        benchmark=benchmark,
        eligibility=eligibility,
        predictions=predictions,
    )
    report["error_analysis_rows"] = len(error_rows)
    _write_json(out_json, report)
    _write_json(out_errors, {
        "schema_version": "stage3_table3_v2_error_analysis@1.0.0",
        "note": (
            "Rows outside the pre-frozen eligibility denominator are retained "
            "but marked not_in_eligible_denominator. Non-target alarms are "
            "retained without a complete-label false-positive judgment."
        ),
        "rows": error_rows,
    })
    md = markdown_table(report)
    md += "\n## Error analysis\n\n"
    md += (
        f"Per-item outcomes are in "
        f"`{out_errors.relative_to(ROOT).as_posix()}` "
        f"({len(error_rows)} rows). "
        "Rows no longer use `target_violation_type` to select a detector "
        "output; the evaluator joins labels only after prediction persistence. "
        "The old automatic-grounding Ours row is not used here: it consumed "
        "the paired control as reference and detected control-to-current "
        "structural changes. The repaired main comparison above uses only the "
        "current BPMN and the frozen, method-specific Stage-2 rule records.\n"
    )
    _write_text(out_md, md)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK)
    parser.add_argument("--eligibility", type=Path, default=ELIGIBILITY)
    parser.add_argument("--run-manifest", type=Path,
                        default=DEFAULT_RUN_MANIFEST)
    parser.add_argument("--out-json", type=Path, default=OUT_JSON)
    parser.add_argument("--out-md", type=Path, default=OUT_MD)
    parser.add_argument("--out-errors", type=Path, default=OUT_ERRORS)
    args = parser.parse_args()
    report = build(
        predictions_path=args.predictions,
        benchmark_path=args.benchmark,
        eligibility_path=args.eligibility,
        run_manifest_path=args.run_manifest,
        out_json=args.out_json,
        out_md=args.out_md,
        out_errors=args.out_errors,
    )
    print(json.dumps({
        "status": report["status"],
        "methods": {
            mid: {
                "macro_f1": block["macro_f1"],
                "micro_f1": block["micro_f1"]["f1"],
                "per_type": {
                    t: {
                        "f1": block["per_type"][t]["f1"],
                        "positive": block["per_type"][t]["positive_count"],
                        "negative": block["per_type"][t]["negative_count"],
                        "unknown_positive": block["per_type"][t]["unknown_positive"],
                        "unknown_negative": block["per_type"][t]["unknown_negative"],
                    }
                    for t in TYPES
                },
            }
            for mid, block in report["methods"].items()
        },
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
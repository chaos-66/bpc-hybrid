# -*- coding: utf-8 -*-
"""Build the same-evaluator D1 prompt-factor ablation table.

Refuses to run until the dedicated 450-call execution is complete.  The table
compares every new arm only with the already completed same-release
D-full-0813 baseline on the same EStG-150 Gold and literal-overlap evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NEW_DIR = ROOT / "outputs" / "development" / "d1_prompt_factorial_ablation_v2"
BASE_DIR = (
    ROOT / "outputs" / "development" / "barrientos_ablation_suite_v2"
    / "D-full-0813" / "repeat-01"
)
OUT_JSON = ROOT / "outputs" / "reports" / "d1_prompt_factorial_results_v1.json"
OUT_MD = ROOT / "outputs" / "reports" / "d1_prompt_factorial_results_v1.md"
ARMS = (
    "D-full-0813",
    "D-no-semantic-examples-0813",
    "D-no-semantic-guidance-0813",
    "D-no-explicit-json-contract-0813",
)
DISPLAY = {
    "D-full-0813": "完整方法（六个合成示例）",
    "D-no-semantic-examples-0813": "语义示例→纯结构模板",
    "D-no-semantic-guidance-0813": "去掉详细语义规则",
    "D-no-explicit-json-contract-0813": "去掉显式 JSON 纪律",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_dir(arm: str) -> Path:
    return BASE_DIR if arm == "D-full-0813" else NEW_DIR / arm / "repeat-01"


def _metrics(arm: str) -> dict[str, Any]:
    run_dir = _run_dir(arm)
    evaluation_path = run_dir / "evaluation.json"
    manifest_path = run_dir / "manifest.json"
    if not evaluation_path.is_file() or not manifest_path.is_file():
        raise RuntimeError(f"missing completed artifacts for {arm}")
    evaluation = _read(evaluation_path)
    manifest = _read(manifest_path)
    payload = evaluation.get("evaluation") or {}
    if payload.get("evaluator") != "sun_literal_overlap@2.0.0":
        raise RuntimeError(f"evaluator mismatch for {arm}")
    metrics = payload.get("metrics") or {}
    if metrics.get("sample_count") != 150 or evaluation.get("denominator") != 150:
        raise RuntimeError(f"denominator mismatch for {arm}")
    overall = metrics.get("overall") or {}
    per_field = metrics.get("per_field") or {}
    return {
        "arm": arm,
        "display_name": DISPLAY[arm],
        "overall": {
            key: overall.get(key) for key in ("precision", "recall", "f1")
        },
        "per_field": {
            field: {key: row.get(key) for key in ("precision", "recall", "f1")}
            for field, row in per_field.items()
        },
        "failure_rate": float(payload.get("failed_count", 0)) / 150,
        "valid_output_rate": 1.0 - float(payload.get("failed_count", 0)) / 150,
        "evaluation_sha256": _sha(evaluation_path),
        "manifest_sha256": _sha(manifest_path),
    }


def build(*, overwrite: bool = False) -> dict[str, Any]:
    summary_path = NEW_DIR / "execution_summary.json"
    if not summary_path.is_file():
        raise RuntimeError("450-call execution has not run")
    summary = _read(summary_path)
    if summary.get("complete") is not True \
            or summary.get("completed_samples") != 450 \
            or summary.get("aborted") is True:
        raise RuntimeError("450-call execution is incomplete or aborted")
    if (OUT_JSON.exists() or OUT_MD.exists()) and not overwrite:
        raise RuntimeError("refusing to overwrite prompt-factor result table")

    rows = [_metrics(arm) for arm in ARMS]
    baseline = rows[0]
    for row in rows:
        row["delta_vs_full"] = {
            key: (row["overall"][key] - baseline["overall"][key])
            for key in ("precision", "recall", "f1")
        }
        row["per_field_delta_f1_vs_full"] = {
            field: values["f1"] - baseline["per_field"][field]["f1"]
            for field, values in row["per_field"].items()
        }

    report = {
        "schema_version": "d1_prompt_factorial_results@1.0.0",
        "status": "complete_real_execution",
        "comparison_scope": {
            "input": "same EStG-150 records",
            "model_release": "DeepSeek-V4-Pro-0813",
            "sampling": "temperature=0, top_p=1, retry=0",
            "gold": "same frozen EStG-150 Gold",
            "evaluator": "sun_literal_overlap@2.0.0",
            "baseline": "D-full-0813",
        },
        "rows": rows,
        "interpretation": (
            "negative delta means the removed/replaced module contributed "
            "to end-to-end extraction on this dataset; zero delta means no "
            "measurable score contribution under this arm, not universal "
            "uselessness"
        ),
    }
    OUT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    lines = [
        "# Direct-LLM 提示模块单因素消融",
        "",
        "同一模型版本、同一 150 条输入、同一 Gold、同一 evaluator；所有差值均相对完整方法。",
        "",
        "| 条件 | P | R | F1 | ΔF1 | 合法输出率 | 失败率 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {name} | {p:.4f} | {r:.4f} | {f:.4f} | {d:+.4f} | "
            "{valid:.4f} | {fail:.4f} |".format(
                name=row["display_name"],
                p=row["overall"]["precision"],
                r=row["overall"]["recall"],
                f=row["overall"]["f1"],
                d=row["delta_vs_full"]["f1"],
                valid=row["valid_output_rate"],
                fail=row["failure_rate"],
            ))
    lines += [
        "",
        "逐字段差值保存在 JSON 报告中。该表只回答本文提示模块在 EStG-150 上的贡献，"
        "不与 Barrientos-native evaluator 的 F1 跨表比较。",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    report = build(overwrite=args.overwrite)
    print(f"Built prompt-factor result table: {len(report['rows'])} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Run one-factor Direct-LLM post-processing ablations on persisted raw output.

All conditions reuse the exact D-full-0813 responses from the completed
1140-call run.  No model request is made.  The baseline is the production
post-processing chain: relay adapter -> span canonicalizer -> canonical
validator.  Each removal arm disables exactly one of those modules while all
other inputs and the evaluator remain fixed.

The result is retrospective development evidence.  It measures the modules'
contribution to *post-processing the fixed model responses*, not their effect
on what the model itself generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bpc_hybrid.d1_schema_adapter import adapt_relay_record
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates
from bpc_hybrid.stage2_canonical import validate_canonical
from analyze_d_no_fewshot_interface_failure_v1 import (
    DiagnosisError,
    _load_jsonl,
    _parse_raw_content,
)

SOURCE_DIR = (
    ROOT / "outputs/development/barrientos_ablation_suite_v2/"
    "D-full-0813/repeat-01"
)
RAW_PATH = SOURCE_DIR / "raw_responses.jsonl"
LOCKED_EVALUATION_PATH = SOURCE_DIR / "evaluation.json"
LOCAL_OUTPUT_DIR = ROOT / "outputs/development/d_full_postprocessing_ablation_v1"
REPORT_JSON = ROOT / "outputs/reports/d_full_postprocessing_ablation_v1.json"
REPORT_MD = ROOT / "outputs/reports/d_full_postprocessing_ablation_v1.md"

CONDITIONS = {
    "full_postprocessing": {
        "display_name": "完整后处理链",
        "adapter": True,
        "canonicalizer": True,
        "validator": True,
        "removed_module": None,
    },
    "no_output_adapter": {
        "display_name": "去掉输出适配器",
        "adapter": False,
        "canonicalizer": True,
        "validator": True,
        "removed_module": "relay_schema_adapter",
    },
    "no_span_canonicalizer": {
        "display_name": "去掉坐标重锚器",
        "adapter": True,
        "canonicalizer": False,
        "validator": True,
        "removed_module": "span_coordinate_canonicalizer",
    },
    "no_canonical_validator": {
        "display_name": "去掉 canonical validator",
        "adapter": True,
        "canonicalizer": True,
        "validator": False,
        "removed_module": "canonical_schema_and_cross_field_validator",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        .encode("utf-8")
        for row in rows
    )


def _failure(sid: str, stage: str, error: str) -> dict[str, Any]:
    return {
        "sample_id": sid,
        "request_status": "failed",
        "error": f"{stage}: {error}",
        "record": {},
    }


def process_condition(
    raw_rows: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, str],
    condition: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply one fixed module configuration to every persisted response."""
    predictions: list[dict[str, Any]] = []
    telemetry: dict[str, Any] = {
        "sample_count": len(raw_rows),
        "json_parse_failures": 0,
        "source_text_mismatch_records": 0,
        "adapter_failures": 0,
        "adapter_degraded_records": 0,
        "adapter_spans_adapted": 0,
        "adapter_spans_dropped": 0,
        "canonicalizer_failures": 0,
        "canonicalizer_reanchored": 0,
        "canonicalizer_spans_dropped": 0,
        "canonicalizer_clauses_dropped": 0,
        "canonicalizer_edges_dropped": 0,
        "validator_invalid_records_observed": 0,
        "validator_rejected_records": 0,
        "nonempty_output_records": 0,
        "output_clause_count": 0,
        "failure_examples": [],
    }
    for raw_row in raw_rows:
        sid = raw_row.get("sample_id")
        if not isinstance(sid, str) or sid not in source_by_id:
            raise DiagnosisError(f"unknown sample_id: {sid!r}")
        source_text = source_by_id[sid]
        try:
            payload = _parse_raw_content(raw_row.get("raw_response_content"))
        except (ValueError, json.JSONDecodeError) as exc:
            telemetry["json_parse_failures"] += 1
            row = _failure(sid, "json_parse", str(exc))
            predictions.append(row)
            if len(telemetry["failure_examples"]) < 10:
                telemetry["failure_examples"].append(row)
            continue
        # The locked suite canonicalized coordinates against the authoritative
        # frozen input text but preserved the model-emitted source_text field.
        # Mirror that behavior exactly so the baseline can reproduce the
        # locked result; report mismatches instead of silently hiding them.
        if payload.get("source_text") != source_text:
            telemetry["source_text_mismatch_records"] += 1
        record: Any = payload
        if condition["adapter"]:
            record, audit = adapt_relay_record(record, source_text)
            telemetry["adapter_spans_adapted"] += int(
                audit.get("spans_adapted", 0))
            telemetry["adapter_spans_dropped"] += len(
                audit.get("dropped_spans", []))
            if audit.get("status") == "degraded":
                telemetry["adapter_degraded_records"] += 1
            if audit.get("status") == "failed":
                telemetry["adapter_failures"] += 1
                row = _failure(
                    sid, "adapter", "; ".join(audit.get("failed_reasons", [])))
                predictions.append(row)
                if len(telemetry["failure_examples"]) < 10:
                    telemetry["failure_examples"].append(row)
                continue
        if condition["canonicalizer"]:
            record, audit = canonicalize_record_coordinates(record, source_text)
            telemetry["canonicalizer_reanchored"] += int(
                audit.get("reanchored_count", 0))
            telemetry["canonicalizer_spans_dropped"] += len(
                audit.get("dropped_spans", []))
            telemetry["canonicalizer_clauses_dropped"] += len(
                audit.get("dropped_clauses", []))
            telemetry["canonicalizer_edges_dropped"] += len(
                audit.get("dropped_edges", []))
            if audit.get("status") == "failed":
                telemetry["canonicalizer_failures"] += 1
                row = _failure(
                    sid, "canonicalizer",
                    "; ".join(audit.get("failed_reasons", [])))
                predictions.append(row)
                if len(telemetry["failure_examples"]) < 10:
                    telemetry["failure_examples"].append(row)
                continue
        validation = validate_canonical(record)
        valid = validation.schema_valid and validation.cross_field_valid
        if not valid:
            telemetry["validator_invalid_records_observed"] += 1
            if condition["validator"]:
                telemetry["validator_rejected_records"] += 1
                row = _failure(sid, "validator", "; ".join(validation.errors))
                predictions.append(row)
                if len(telemetry["failure_examples"]) < 10:
                    telemetry["failure_examples"].append(row)
                continue
        clauses = record.get("clauses") if isinstance(record, Mapping) else []
        if isinstance(clauses, list) and clauses:
            telemetry["nonempty_output_records"] += 1
            telemetry["output_clause_count"] += len(clauses)
        predictions.append({
            "sample_id": sid,
            "request_status": "ok",
            "response_sha256": raw_row.get("response_sha256"),
            "request_id": raw_row.get("request_id"),
            "record": record,
            "diagnostic_validation": {
                "schema_valid": validation.schema_valid,
                "cross_field_valid": validation.cross_field_valid,
                "errors": list(validation.errors),
                "gate_enabled": bool(condition["validator"]),
            },
        })
    if len(predictions) != len(raw_rows):
        raise DiagnosisError("condition changed the fixed denominator")
    telemetry["failed_records"] = sum(
        1 for row in predictions if row["request_status"] != "ok")
    telemetry["successful_records"] = len(predictions) - telemetry["failed_records"]
    return predictions, telemetry


def _overall(evaluation: Mapping[str, Any]) -> dict[str, float]:
    metrics = evaluation.get("metrics") or {}
    overall = metrics.get("overall") or {}
    return {
        "precision": float(overall.get("precision", 0.0)),
        "recall": float(overall.get("recall", 0.0)),
        "f1": float(overall.get("f1", 0.0)),
    }


def build_report(
    raw_path: Path = RAW_PATH,
    locked_evaluation_path: Path = LOCKED_EVALUATION_PATH,
    evaluator: Callable[[Sequence[Mapping[str, Any]]], dict[str, Any]] | None = None,
    source_by_id: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    if not raw_path.is_file() or not locked_evaluation_path.is_file():
        raise DiagnosisError("persisted D-full-0813 artifacts are unavailable")
    raw_rows = _load_jsonl(raw_path)
    if len(raw_rows) != 150:
        raise DiagnosisError("post-processing ablation requires 150 raw rows")
    if source_by_id is None or evaluator is None:
        import run_barrientos_ablation_suite_v2 as runner
        if source_by_id is None:
            source_by_id = {
                row["sample_id"]: row["text"] for row in runner._estg_samples()
            }
        if evaluator is None:
            evaluator = runner._make_evaluator("D-full-0813")
    condition_rows: dict[str, list[dict[str, Any]]] = {}
    evaluations: dict[str, dict[str, Any]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    for condition_id, condition in CONDITIONS.items():
        rows, telemetry = process_condition(raw_rows, source_by_id, condition)
        evaluation = evaluator(rows)
        condition_rows[condition_id] = rows
        evaluations[condition_id] = evaluation
        summaries[condition_id] = {
            **condition,
            "telemetry": telemetry,
            "overall": _overall(evaluation),
            "per_field": (evaluation.get("metrics") or {}).get("per_field", {}),
            "prediction_payload_sha256": hashlib.sha256(
                _jsonl_bytes(rows)).hexdigest(),
        }
    full = summaries["full_postprocessing"]["overall"]
    locked = json.loads(locked_evaluation_path.read_text(encoding="utf-8"))
    locked_overall = _overall(locked["evaluation"])
    if any(abs(full[key] - locked_overall[key]) > 1e-12
           for key in ("precision", "recall", "f1")):
        raise DiagnosisError(
            "production post-processing baseline does not reproduce the "
            "locked D-full-0813 evaluation")
    for condition_id, summary in summaries.items():
        summary["delta_vs_full"] = {
            key: summary["overall"][key] - full[key]
            for key in ("precision", "recall", "f1")
        }
    report = {
        "schema_version": "d_full_postprocessing_ablation@1.0.0",
        "status": "retrospective_development_one_factor_ablation",
        "scope": {
            "source_arm": "D-full-0813",
            "source_run": "barrientos-de-0813-1140-v1",
            "sample_count": 150,
            "model_responses_fixed_across_conditions": True,
            "new_api_calls": 0,
            "same_gold_and_evaluator": True,
            "measured_layer": "postprocessing_only",
            "model_generation_effect_claim_allowed": False,
            "formal_confirmatory_claim_allowed": False,
        },
        "provenance": {
            "raw_responses_path": str(raw_path.relative_to(ROOT)).replace("\\", "/"),
            "raw_responses_sha256": _sha256(raw_path),
            "raw_responses_distribution": "local_only_not_redistributed",
            "locked_evaluation_path": str(
                locked_evaluation_path.relative_to(ROOT)).replace("\\", "/"),
            "locked_evaluation_sha256": _sha256(locked_evaluation_path),
            "baseline_exactly_reproduces_locked_evaluation": True,
        },
        "one_factor_contract": {
            "full_chain": [
                "relay_schema_adapter",
                "span_coordinate_canonicalizer",
                "canonical_schema_and_cross_field_validator",
            ],
            "rule": "each removal arm disables exactly one module",
            "denominator_policy": "all 150 samples; rejected/failed records are empty predictions",
        },
        "conditions": summaries,
        "scientific_interpretation": {
            "adapter": (
                "Measures whether relay-shape normalization adds extraction "
                "value for the fixed full-prompt responses."),
            "canonicalizer": (
                "Measures the recovery attributable to deterministic exact-text "
                "coordinate re-anchoring while the validator remains fixed."),
            "validator": (
                "Measures acceptance-gate impact and reports invalid records "
                "that would pass downstream when the gate is removed. No score "
                "change does not imply the safety check is useless."),
            "boundary": (
                "These arms cannot measure whether prompting the model about "
                "these modules changes generation, because every arm reuses the "
                "same raw responses."),
        },
    }
    return report, condition_rows, evaluations


def to_markdown(report: Mapping[str, Any]) -> str:
    rows = report["conditions"]
    lines = [
        "# Direct-LLM 后处理模块单因素消融 v1",
        "",
        "> 同一批 D-full-0813 原始响应离线重放；新增 API 调用为0。每个条件"
        "只关闭一个后处理模块，所有150条样本均进入分母。结果属于回顾性开发证据。",
        "",
        "## 结果",
        "",
        "| 条件 | 移除模块 | P | R | F1 | ΔF1 | 成功记录 | 非空记录 | validator观察到无效 |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    order = (
        "full_postprocessing", "no_output_adapter",
        "no_span_canonicalizer", "no_canonical_validator")
    for condition_id in order:
        row = rows[condition_id]
        telemetry = row["telemetry"]
        removed = row["removed_module"] or "—"
        lines.append(
            f"| {row['display_name']} | {removed} | "
            f"{row['overall']['precision']:.3f} | "
            f"{row['overall']['recall']:.3f} | "
            f"{row['overall']['f1']:.3f} | "
            f"{row['delta_vs_full']['f1']:+.3f} | "
            f"{telemetry['successful_records']}/150 | "
            f"{telemetry['nonempty_output_records']}/150 | "
            f"{telemetry['validator_invalid_records_observed']} |")
    adapter = rows["no_output_adapter"]
    canonicalizer = rows["no_span_canonicalizer"]
    validator = rows["no_canonical_validator"]
    lines += [
        "",
        "## 可以怎样解释",
        "",
        f"- 输出适配器移除后的 ΔF1 为 {adapter['delta_vs_full']['f1']:+.3f}；"
        "这反映它对当前完整 Prompt 原始响应的实际增量。",
        f"- 坐标重锚器移除后的 ΔF1 为 {canonicalizer['delta_vs_full']['f1']:+.3f}；"
        "validator仍保持开启，因此坐标错误导致的无效记录会作为失败进入分母。",
        f"- validator移除后的 ΔF1 为 {validator['delta_vs_full']['f1']:+.3f}；"
        f"有 {validator['telemetry']['validator_invalid_records_observed']} 条无效记录被"
        "观察到。若分数不变，只能说明上游在这批响应上已产生合法记录，不能说明"
        "validator没有安全价值。",
        "",
        "## 边界",
        "",
        "这些实验只评价固定模型响应之后的模块贡献，不评价模块说明是否改变模型生成。"
        "原始响应仍为本地受限证据，报告仅绑定其SHA-256。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    targets = [REPORT_JSON, REPORT_MD]
    for condition_id in CONDITIONS:
        out = LOCAL_OUTPUT_DIR / condition_id
        targets.extend((out / "predictions.jsonl", out / "evaluation.json"))
    targets.append(LOCAL_OUTPUT_DIR / "manifest.json")
    if not args.overwrite and any(path.exists() for path in targets):
        print("refusing to overwrite existing post-processing ablation v1")
        return 2
    try:
        report, rows_by_condition, evaluations = build_report()
        LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        artifacts: dict[str, Any] = {}
        for condition_id in CONDITIONS:
            out = LOCAL_OUTPUT_DIR / condition_id
            out.mkdir(parents=True, exist_ok=True)
            pred_path = out / "predictions.jsonl"
            eval_path = out / "evaluation.json"
            pred_path.write_bytes(_jsonl_bytes(rows_by_condition[condition_id]))
            eval_path.write_text(
                json.dumps(evaluations[condition_id], ensure_ascii=False, indent=2)
                + "\n", encoding="utf-8")
            artifacts[condition_id] = {
                "predictions_sha256": _sha256(pred_path),
                "evaluation_sha256": _sha256(eval_path),
            }
        (LOCAL_OUTPUT_DIR / "manifest.json").write_text(
            json.dumps({
                "schema_version": "d_full_postprocessing_ablation_manifest@1.0.0",
                "status": report["status"],
                "new_api_calls": 0,
                "source_raw_sha256": report["provenance"]["raw_responses_sha256"],
                "conditions": artifacts,
                "redistribution": "local_predictions_not_committed",
            }, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        REPORT_JSON.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        REPORT_MD.write_text(to_markdown(report), encoding="utf-8")
        print("post-processing ablation written; zero API calls")
        return 0
    except (DiagnosisError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

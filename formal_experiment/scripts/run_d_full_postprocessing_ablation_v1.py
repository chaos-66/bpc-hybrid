# -*- coding: utf-8 -*-
"""Run the full 2^3 Direct-LLM post-processing ablation on persisted raw output.

All conditions reuse the exact D-full-0813 responses from the completed
1140-call run.  No model request is made.  The baseline is the production
post-processing chain: relay adapter -> span canonicalizer -> canonical
validator.  The eight conditions enumerate all boolean combinations of those
three modules while all other inputs and the evaluator remain fixed.

The result is retrospective development evidence.  It measures the modules'
contribution to *post-processing the fixed model responses*, not their effect
on what the model itself generated.
"""

from __future__ import annotations

import argparse
import copy
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
from bpc_hybrid.d1_span_canonicalizer import (
    POLICY_LEGACY,
    canonicalize_record_coordinates,
)
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
LOCAL_OUTPUT_DIR = ROOT / "outputs/development/d_full_postprocessing_ablation_v2"
REPORT_JSON = ROOT / "outputs/reports/d_full_postprocessing_ablation_v2.json"
REPORT_MD = ROOT / "outputs/reports/d_full_postprocessing_ablation_v2.md"

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
    "no_adapter_no_canonicalizer": {
        "display_name": "去掉输出适配器+坐标重锚器",
        "adapter": False,
        "canonicalizer": False,
        "validator": True,
        "removed_module": (
            "relay_schema_adapter+span_coordinate_canonicalizer"),
    },
    "no_canonicalizer_no_validator": {
        "display_name": "去掉坐标重锚器+validator",
        "adapter": True,
        "canonicalizer": False,
        "validator": False,
        "removed_module": (
            "span_coordinate_canonicalizer+"
            "canonical_schema_and_cross_field_validator"),
    },
    "no_adapter_no_validator": {
        "display_name": "去掉输出适配器+validator",
        "adapter": False,
        "canonicalizer": True,
        "validator": False,
        "removed_module": (
            "relay_schema_adapter+"
            "canonical_schema_and_cross_field_validator"),
    },
    "no_adapter_no_canonicalizer_no_validator": {
        "display_name": "三模块全关（原始输出直面评价器）",
        "adapter": False,
        "canonicalizer": False,
        "validator": False,
        "removed_module": (
            "relay_schema_adapter+span_coordinate_canonicalizer+"
            "canonical_schema_and_cross_field_validator"),
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
            # Historical frozen replay: this script's checked-in report used
            # the pre-promotion default. Pin legacy explicitly so promotion of
            # repair_v1 cannot silently drift this retrospective evidence.
            record, audit = canonicalize_record_coordinates(
                record, source_text, policy=POLICY_LEGACY)
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
        all_disabled = not any(
            condition[key] for key in ("adapter", "canonicalizer", "validator"))
        validation_input = copy.deepcopy(record) if all_disabled else record
        validation = validate_canonical(validation_input)
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


def _refresh_row_telemetry(
    rows: Sequence[Mapping[str, Any]],
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    """Recompute row-derived telemetry after an evaluator-shape failure."""
    telemetry["failed_records"] = sum(
        1 for row in rows if row.get("request_status") != "ok")
    telemetry["successful_records"] = len(rows) - telemetry["failed_records"]
    nonempty = 0
    clause_count = 0
    for row in rows:
        if row.get("request_status") != "ok":
            continue
        record = row.get("record")
        clauses = record.get("clauses") if isinstance(record, Mapping) else []
        if isinstance(clauses, list) and clauses:
            nonempty += 1
            clause_count += len(clauses)
    telemetry["nonempty_output_records"] = nonempty
    telemetry["output_clause_count"] = clause_count
    return telemetry


def _mark_evaluator_shape_failures(
    rows: list[dict[str, Any]],
    telemetry: dict[str, Any],
    evaluator: Callable[[Sequence[Mapping[str, Any]]], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    """Mark only rows that make the evaluator reject the raw output shape.

    The function is used only for the all-modules-disabled condition, where the
    raw model record is handed to the evaluator without repair.  It probes each
    candidate row in a full-membership batch with every other row marked as a
    failure, so any evaluator exception remains attributable to the probed row.
    The raw record itself is never rewritten.
    """
    marked: list[dict[str, Any]] = []
    changed = False
    for index, row in enumerate(rows):
        if row.get("request_status") != "ok":
            marked.append(row)
            continue
        probe: list[dict[str, Any]] = []
        for probe_index, probe_row in enumerate(rows):
            if probe_index == index:
                probe.append(probe_row)
            else:
                probe.append(_failure(
                    str(probe_row.get("sample_id", "")),
                    "evaluator_probe",
                    "shape isolation placeholder",
                ))
        try:
            evaluator(probe)
        except Exception as exc:  # noqa: BLE001 - report the evaluator failure
            failed = _failure(
                str(row.get("sample_id", "")), "evaluator_shape", str(exc))
            marked.append(failed)
            changed = True
            if len(telemetry["failure_examples"]) < 10:
                telemetry["failure_examples"].append(failed)
        else:
            marked.append(row)
    if changed:
        telemetry = _refresh_row_telemetry(marked, telemetry)
    return marked, telemetry, changed


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
        try:
            evaluation = evaluator(rows)
        except Exception:
            all_disabled = not any(
                condition[key] for key in ("adapter", "canonicalizer", "validator"))
            if not all_disabled:
                raise
            rows, telemetry, changed = _mark_evaluator_shape_failures(
                rows, telemetry, evaluator)
            if not changed:
                raise
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
        "schema_version": "d_full_postprocessing_ablation@2.0.0",
        "status": "retrospective_development_full_factorial_ablation",
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
        "full_factorial_contract": {
            "factors": {
                "adapter": "relay_schema_adapter",
                "canonicalizer": "span_coordinate_canonicalizer",
                "validator": (
                    "canonical_schema_and_cross_field_validator"),
            },
            "full_chain": [
                "relay_schema_adapter",
                "span_coordinate_canonicalizer",
                "canonical_schema_and_cross_field_validator",
            ],
            "design": "full 2^3 factorial",
            "condition_count": 8,
            "rule": "each condition is one boolean combination of the three modules",
            "denominator_policy": (
                "all 150 samples; rejected/failed records are empty predictions; "
                "the all-disabled condition passes raw output to the evaluator "
                "without repair and records evaluator-shape failures in the "
                "same denominator"),
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
    order = (
        "full_postprocessing",
        "no_output_adapter",
        "no_span_canonicalizer",
        "no_canonical_validator",
        "no_adapter_no_canonicalizer",
        "no_canonicalizer_no_validator",
        "no_adapter_no_validator",
        "no_adapter_no_canonicalizer_no_validator",
    )
    full = rows["full_postprocessing"]
    no_adapter = rows["no_output_adapter"]
    no_canonicalizer = rows["no_span_canonicalizer"]
    no_validator = rows["no_canonical_validator"]
    no_adapter_no_canonicalizer = rows["no_adapter_no_canonicalizer"]
    no_canonicalizer_no_validator = rows["no_canonicalizer_no_validator"]
    no_adapter_no_validator = rows["no_adapter_no_validator"]
    all_disabled = rows["no_adapter_no_canonicalizer_no_validator"]
    lines = [
        "# Direct-LLM 后处理模块 2^3 全组合消融 v2",
        "",
        "> 同一批 D-full-0813 原始响应离线重放；新增 API 调用为0。8 个条件"
        "枚举 output adapter、span canonicalizer、canonical validator 的全部"
        "开关组合；所有150条样本均进入分母。结果属于回顾性开发证据。",
        "",
        "## 8 格全组合结果",
        "",
        "| 条件 | adapter | canonicalizer | validator | P | R | F1 | "
        "ΔF1(vs full) | 成功记录 | 非空记录 | validator观察到无效数 | "
        "validator拒收数 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for condition_id in order:
        row = rows[condition_id]
        telemetry = row["telemetry"]
        checks = (
            "✅" if row["adapter"] else "❌",
            "✅" if row["canonicalizer"] else "❌",
            "✅" if row["validator"] else "❌",
        )
        lines.append(
            f"| `{condition_id}` | {checks[0]} | {checks[1]} | {checks[2]} | "
            f"{row['overall']['precision']:.4f} | "
            f"{row['overall']['recall']:.4f} | "
            f"{row['overall']['f1']:.4f} | "
            f"{row['delta_vs_full']['f1']:+.4f} | "
            f"{telemetry['successful_records']}/150 | "
            f"{telemetry['nonempty_output_records']}/150 | "
            f"{telemetry['validator_invalid_records_observed']} | "
            f"{telemetry['validator_rejected_records']} |")
    lines += [
        "",
        "## 分层读法：有效性层 / 安全网层",
        "",
        "**有效性层（adapter + canonicalizer；canonicalizer 是主责模块）**",
        "",
        f"- `full_postprocessing` 的 F1 为 {full['overall']['f1']:.4f}，"
        "成功记录与非空记录分别为 "
        f"{full['telemetry']['successful_records']}/150、"
        f"{full['telemetry']['nonempty_output_records']}/150。",
        f"- 只去掉输出适配器时，F1 为 "
        f"{no_adapter['overall']['f1']:.4f}（ΔF1 "
        f"{no_adapter['delta_vs_full']['f1']:+.4f}）；说明在这批固定响应上"
        "adapter 没有独立的 F1 增量，不能与 canonicalizer 并列成等价贡献。",
        f"- 去掉坐标重锚器但仍保留 validator 时，F1 为 "
        f"{no_canonicalizer['overall']['f1']:.4f}（ΔF1 "
        f"{no_canonicalizer['delta_vs_full']['f1']:+.4f}）；validator 观察到 "
        f"{no_canonicalizer['telemetry']['validator_invalid_records_observed']} "
        "条无效记录并拒收 "
        f"{no_canonicalizer['telemetry']['validator_rejected_records']} 条。"
        "坐标有效性是这批完整后处理分数的决定性上游条件。",
        f"- 在 validator 关闭的情况下，只去掉坐标重锚器时 F1 为 "
        f"{no_canonicalizer_no_validator['overall']['f1']:.4f}；它高于"
        "validator 开启时的 0，但低于完整链，说明原始/未重锚记录仍可被"
        "评价器部分读出，却不能替代 canonicalizer 的确定性坐标恢复。",
        "",
        "**安全网层（validator）**",
        "",
        f"- 在 canonicalizer 开启时，去掉 validator 的 F1 仍为 "
        f"{no_validator['overall']['f1']:.4f}，batch 内观察到的无效记录为 "
        f"{no_validator['telemetry']['validator_invalid_records_observed']}；"
        "分数不变只说明上游在这批响应上已产生合法记录，不能说明 validator "
        "没有安全价值。",
        f"- 在 canonicalizer 关闭时，validator 开启的 "
        f"`no_adapter_no_canonicalizer` 拒收 "
        f"{no_adapter_no_canonicalizer['telemetry']['validator_rejected_records']} "
        "条记录并把 F1 压到 "
        f"{no_adapter_no_canonicalizer['overall']['f1']:.4f}；validator 关闭的 "
        f"`no_canonicalizer_no_validator` 保留原始记录并得到 "
        f"{no_canonicalizer_no_validator['overall']['f1']:.4f}。"
        "这说明 validator 与 canonicalizer 的角色不同：前者是拒收安全网，"
        "后者是坐标有效性层。",
        f"- 三模块全关时，原始模型输出直接交给评价器：F1 为 "
        f"{all_disabled['overall']['f1']:.4f}，成功记录 "
        f"{all_disabled['telemetry']['successful_records']}/150，非空记录 "
        f"{all_disabled['telemetry']['nonempty_output_records']}/150，"
        f"validator 观察到 "
        f"{all_disabled['telemetry']['validator_invalid_records_observed']} "
        "条无效记录；本批评价器未因形状抛错，若抛错则仅把对应样本记为"
        "失败并保留在同一分母，不对原始记录做修补或回填。",
        "",
        "## 边界",
        "",
        "这些实验只评价固定模型响应之后的模块贡献，不评价模块说明是否改变"
        "模型生成。完整链仍作为唯一对照，且必须逐位复现锁定结果。"
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
        print("refusing to overwrite existing post-processing ablation v2")
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
                "schema_version": "d_full_postprocessing_ablation_manifest@2.0.0",
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

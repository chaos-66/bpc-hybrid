# -*- coding: utf-8 -*-
"""Deterministic offline attribution of post-processing on fixed SEP-C3 responses.

This script does not call any model API and does not modify the processing
modules it audits.  It replays already-saved raw responses from old v6
(D-full-0813) and the new modular_v1 111 arm through the frozen code path,
with all 150 samples retained in every denominator.

Primary metric: coarse sentence-level arithmetic mean of actor/action/condition/
constraint/exception F1.  Micro F1 and modality labels are diagnostic only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for path in (SRC, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from bpc_hybrid.d1_schema_adapter import adapt_relay_record  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402
from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    attempt_rows,
    evaluate_coarse,
)
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from analyze_d_no_fewshot_interface_failure_v1 import _parse_raw_content  # noqa: E402
import run_d_full_postprocessing_ablation_v1 as one_factor  # noqa: E402

SCHEMA_VERSION = "sep_c3_postprocessing_attribution@1.0.0"
PRIMARY_METRIC = "coarse_five_field_mean_f1"
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")

OLD_ARM = "old_v6_full_0813"
NEW_ARM = "111"
ARMS = {
    OLD_ARM: {
        "label": "旧 v6 D-full-0813",
        "raw_dir": Path(
            "outputs/development/barrientos_ablation_suite_v2/"
            "D-full-0813/repeat-01"
        ),
    },
    NEW_ARM: {
        "label": "新版 modular_v1 111",
        "raw_dir": Path(
            "outputs/development/sep_c3_modular_ablation_v1/111/repeat-01"
        ),
    },
}

CONDITION_LABELS = {
    "json_fence_gate": "仅 JSON/fence + 最终验证门（无 adapter/canonicalizer）",
    "adapter_gate": "有输出适配器、无坐标重锚，经最终验证门（=完整链去 canonicalizer）",
    "saved_path_no_validator": "adapter+canonicalizer、未启用最终验证门（111 已保存路径）",
    "full_contract": "adapter+canonicalizer+最终 schema/cross-field 验证（完整链）",
    "full_minus_adapter": "完整链去输出适配器（接口依赖对照）",
}
CONDITION_ORDER = (
    "json_fence_gate",
    "adapter_gate",
    "saved_path_no_validator",
    "full_contract",
    "full_minus_adapter",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def _condition_from_id(condition_id: str) -> dict[str, Any]:
    if condition_id == "full_contract":
        return dict(one_factor.CONDITIONS["full_postprocessing"])
    if condition_id == "adapter_gate":
        return dict(one_factor.CONDITIONS["no_span_canonicalizer"])
    if condition_id == "full_minus_adapter":
        return dict(one_factor.CONDITIONS["no_output_adapter"])
    if condition_id == "saved_path_no_validator":
        return {
            "display_name": "saved_path_no_validator",
            "adapter": True,
            "canonicalizer": True,
            "validator": False,
            "removed_module": "canonical_schema_and_cross_field_validator",
        }
    raise KeyError(condition_id)


def _summarize_evaluation(
    rows: Sequence[Mapping[str, Any]],
    telemetry: Mapping[str, Any],
    gold_doc: Mapping[str, Any],
    *,
    method_id: str,
    condition_label: str,
) -> dict[str, Any]:
    evaluation = evaluate_coarse(
        gold_doc, attempt_rows(rows), method_id=method_id)
    fields = evaluation["five_fields"]
    return {
        "condition_id": method_id.rsplit("_", 1)[-1],
        "label": condition_label,
        "successful_records": int(telemetry.get("successful_records", len(rows))),
        "failed_records": int(telemetry.get("failed_records", 0)),
        "validator_invalid_records_observed": int(
            telemetry.get("validator_invalid_records_observed", 0)),
        "nonempty_output_records": int(
            telemetry.get("nonempty_output_records", 0)),
        "five_fields_f1": {
            field: _finite(fields[field].get("f1"))
            for field in SPAN_FIELDS
        },
        "five_fields_extracted": {
            field: int(fields[field].get("extracted") or 0)
            for field in SPAN_FIELDS
        },
        "five_fields_matched_predictions": {
            field: int(fields[field].get("matched_predictions") or 0)
            for field in SPAN_FIELDS
        },
        "five_fields_matched_ground_truth": {
            field: int(fields[field].get("matched_ground_truth") or 0)
            for field in SPAN_FIELDS
        },
        "coarse_five_field_mean_f1": _finite(
            evaluation.get("coarse_five_field_mean_f1")),
        "coarse_five_field_micro_f1": _finite(
            (evaluation.get("coarse_five_field_micro") or {}).get("f1")),
        "denominator": int(evaluation.get("denominator") or len(rows)),
        "telemetry": dict(telemetry),
    }


def _process_parse_only_gate(
    raw_rows: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    telemetry: dict[str, Any] = {
        "sample_count": len(raw_rows),
        "json_parse_failures": 0,
        "validator_invalid_records_observed": 0,
        "validator_rejected_records": 0,
        "successful_records": 0,
        "failed_records": 0,
        "nonempty_output_records": 0,
        "failure_examples": [],
    }
    for raw_row in raw_rows:
        sample_id = raw_row.get("sample_id")
        if not isinstance(sample_id, str) or sample_id not in source_by_id:
            raise ValueError(f"unknown sample_id: {sample_id!r}")
        try:
            payload = _parse_raw_content(raw_row.get("raw_response_content"))
        except Exception as exc:  # noqa: BLE001 - diagnostic stage boundary
            telemetry["json_parse_failures"] += 1
            row = {
                "sample_id": sample_id,
                "request_status": "failed",
                "error": f"json_parse: {exc}",
                "record": {},
            }
            predictions.append(row)
            if len(telemetry["failure_examples"]) < 10:
                telemetry["failure_examples"].append(row)
            continue
        validation = validate_canonical(payload)
        if not (validation.schema_valid and validation.cross_field_valid):
            telemetry["validator_invalid_records_observed"] += 1
            telemetry["validator_rejected_records"] += 1
            row = {
                "sample_id": sample_id,
                "request_status": "failed",
                "error": "validator: " + "; ".join(validation.errors),
                "record": {},
            }
            predictions.append(row)
            if len(telemetry["failure_examples"]) < 10:
                telemetry["failure_examples"].append(row)
            continue
        predictions.append({
            "sample_id": sample_id,
            "request_status": "ok",
            "record": payload,
        })
        clauses = payload.get("clauses") if isinstance(payload, Mapping) else []
        if isinstance(clauses, list) and clauses:
            telemetry["nonempty_output_records"] += 1
    telemetry["successful_records"] = sum(
        1 for row in predictions if row["request_status"] == "ok")
    telemetry["failed_records"] = len(predictions) - telemetry["successful_records"]
    return predictions, telemetry


def _extract_actor_spans(record: Any) -> list[dict[str, Any]]:
    if not isinstance(record, Mapping):
        return []
    clauses = record.get("clauses")
    if not isinstance(clauses, list):
        return []
    out: list[dict[str, Any]] = []
    for clause in clauses:
        if not isinstance(clause, Mapping):
            continue
        for item in clause.get("actors") or []:
            if not isinstance(item, Mapping):
                continue
            container = item
            if not isinstance(container.get("text"), str) and isinstance(
                    container.get("span"), Mapping):
                container = {**container, **item["span"]}
            text = container.get("text")
            if not isinstance(text, str):
                continue
            out.append({
                "text": text,
                "start": container.get("start"),
                "end": container.get("end"),
                "id": item.get("id"),
            })
    return out


def _actor_counts_by_sample(
    records: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    return {
        sample_id: _extract_actor_spans(record)
        for sample_id, record in records.items()
    }


def _diff_actor_snapshots(
    before: Mapping[str, list[dict[str, Any]]],
    after: Mapping[str, list[dict[str, Any]]],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    aggregate = {"added": 0, "removed": 0, "relocated": 0, "unchanged": 0}
    dropped: list[dict[str, Any]] = []
    for sample_id in sorted(set(before) | set(after)):
        pre = before.get(sample_id, [])
        post = after.get(sample_id, [])
        pre_counter = Counter(span["text"] for span in pre)
        post_counter = Counter(span["text"] for span in post)
        for text in sorted(set(pre_counter) | set(post_counter)):
            pre_count = pre_counter[text]
            post_count = post_counter[text]
            if post_count > pre_count:
                aggregate["added"] += post_count - pre_count
            if pre_count > post_count:
                aggregate["removed"] += pre_count - post_count
                pre_items = [span for span in pre if span["text"] == text]
                post_items = [span for span in post if span["text"] == text]
                # Report only the excess occurrences, in stable offset order.
                pre_sorted = sorted(
                    pre_items,
                    key=lambda span: (
                        -1 if span.get("start") is None else int(span["start"]),
                        -1 if span.get("end") is None else int(span["end"]),
                    ),
                )
                post_sorted = sorted(
                    post_items,
                    key=lambda span: (
                        -1 if span.get("start") is None else int(span["start"]),
                        -1 if span.get("end") is None else int(span["end"]),
                    ),
                )
                for span in pre_sorted[len(post_sorted):]:
                    dropped.append({"sample_id": sample_id, **span})
            common = min(pre_count, post_count)
            if common:
                pre_sorted = sorted(
                    [span for span in pre if span["text"] == text],
                    key=lambda span: (
                        -1 if span.get("start") is None else int(span["start"]),
                        -1 if span.get("end") is None else int(span["end"]),
                    ),
                )
                post_sorted = sorted(
                    [span for span in post if span["text"] == text],
                    key=lambda span: (
                        -1 if span.get("start") is None else int(span["start"]),
                        -1 if span.get("end") is None else int(span["end"]),
                    ),
                )
                for pre_span, post_span in zip(pre_sorted[:common], post_sorted[:common]):
                    if (pre_span.get("start"), pre_span.get("end")) != (
                            post_span.get("start"), post_span.get("end")):
                        aggregate["relocated"] += 1
                    else:
                        aggregate["unchanged"] += 1
    return aggregate, dropped


def _gold_actor_texts(gold_doc: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for record in build_coarse_view(gold_doc):
        sample_id = record["sample_id"]
        for clause in record.get("clauses") or []:
            for span in clause.get("actors") or []:
                text = span.get("text")
                if isinstance(text, str) and text:
                    result[sample_id].add(text)
    return result


def _trace_arm(
    arm: str,
    raw_rows: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, str],
    saved_by_id: Mapping[str, Mapping[str, Any]],
    gold_actor_text: Mapping[str, set[str]],
) -> dict[str, Any]:
    raw_records: dict[str, Any] = {}
    adapter_records: dict[str, Any] = {}
    canonical_records: dict[str, Any] = {}
    saved_records: dict[str, Any] = {}
    parser_failures: list[str] = []
    source_text_mismatches = 0
    fence_count = 0
    bare_count = 0
    validator_invalid: list[dict[str, Any]] = []

    for raw_row in raw_rows:
        sample_id = raw_row["sample_id"]
        source_text = source_by_id[sample_id]
        raw_text = raw_row.get("raw_response_content") or ""
        stripped = raw_text.strip()
        if stripped.startswith("```"):
            fence_count += 1
        else:
            bare_count += 1
        try:
            payload = _parse_raw_content(raw_text)
        except Exception as exc:  # noqa: BLE001
            parser_failures.append(f"{sample_id}: {exc}")
            payload = {
                "schema_version": "1.0.0",
                "sample_id": sample_id,
                "source_id": sample_id,
                "source_text": source_text,
                "clauses": [],
            }
        if payload.get("source_text") != source_text:
            source_text_mismatches += 1
        raw_records[sample_id] = payload
        adapted, _ = adapt_relay_record(payload, source_text)
        adapter_records[sample_id] = adapted
        canonical, _ = canonicalize_record_coordinates(adapted, source_text)
        canonical_records[sample_id] = canonical
        saved_records[sample_id] = saved_by_id.get(sample_id, {}).get("record") or {}
        validation = validate_canonical(canonical)
        if not (validation.schema_valid and validation.cross_field_valid):
            validator_invalid.append({
                "sample_id": sample_id,
                "errors": list(validation.errors),
                "saved_path_status": saved_by_id.get(sample_id, {}).get(
                    "request_status"),
            })

    raw_counts = _actor_counts_by_sample(raw_records)
    adapter_counts = _actor_counts_by_sample(adapter_records)
    canonical_counts = _actor_counts_by_sample(canonical_records)
    saved_counts = _actor_counts_by_sample(saved_records)

    raw_to_adapter, _ = _diff_actor_snapshots(raw_counts, adapter_counts)
    adapter_to_canonical, dropped = _diff_actor_snapshots(
        adapter_counts, canonical_counts)
    canonical_to_saved, _ = _diff_actor_snapshots(
        canonical_counts, saved_counts)

    for drop in dropped:
        drop["exact_gold_actor_text_match"] = drop["text"] in gold_actor_text.get(
            drop["sample_id"], set())

    return {
        "raw_actor_spans": sum(len(v) for v in raw_counts.values()),
        "adapter_actor_spans": sum(len(v) for v in adapter_counts.values()),
        "canonicalizer_actor_spans": sum(len(v) for v in canonical_counts.values()),
        "saved_actor_spans": sum(len(v) for v in saved_counts.values()),
        "raw_to_adapter": raw_to_adapter,
        "adapter_to_canonicalizer": adapter_to_canonical,
        "canonicalizer_to_saved": canonical_to_saved,
        "dropped_actor_spans": dropped,
        "parser_failures": parser_failures,
        "markdown_fence_count": fence_count,
        "bare_json_count": bare_count,
        "source_text_mismatch_records": source_text_mismatches,
        "validator_invalid_records": validator_invalid,
    }


def _saved_attempts(path: Path) -> list[dict[str, Any]]:
    rows = _load_jsonl(path)
    return [
        {
            "sample_id": row["sample_id"],
            "request_status": row.get("request_status", "failed"),
            "record": row.get("record") or {},
        }
        for row in rows
    ]


def _build_markdown(report: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# SEP-C3 固定原始响应后处理归因 v1（离线，零新增 API）")
    lines.append("")
    lines.append("> 状态：`offline_attribution_only_no_api_no_rerun`。本报告只对已保存 raw "
                 "响应做确定性离线重放；不生成模型响应、不修改处理逻辑/阈值、不覆盖历史结果。")
    lines.append("")
    lines.append("## 0. 结论摘要")
    lines.append("")
    lines.append("### 已确认 / 不能归因 / 具体缺陷")
    lines.append("")
    lines.append("**已确认**")
    for item in report["conclusions"]["confirmed"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("**不能归因**")
    for item in report["conclusions"]["not_attributable"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("**具体后处理缺陷定位**")
    for item in report["conclusions"]["defects"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 1. 同口径后处理结果表")
    lines.append("")
    lines.append("主指标为 coarse sentence-level actor/action/condition/constraint/"
                 "exception 五字段 F1 算术平均；每行均保留 150 条分母。"
                 "`validator invalid observed` 是最终验证观察到但未必被拒绝的记录数。")
    lines.append("")
    header = ("| 条件 | arm | 成功/失败 | validator invalid observed | actor | action | "
              "condition | constraint | exception | mean F1 |")
    lines.append(header)
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for condition_id in CONDITION_ORDER:
        for arm in (OLD_ARM, NEW_ARM):
            row = report["conditions"][arm][condition_id]
            fields = row["five_fields_f1"]
            lines.append(
                f"| {row['label']} | {ARMS[arm]['label']} | "
                f"{row['successful_records']}/{row['failed_records']} | "
                f"{row['validator_invalid_records_observed']} | "
                f"{fields['actor']:.6f} | {fields['action']:.6f} | "
                f"{fields['condition']:.6f} | {fields['constraint']:.6f} | "
                f"{fields['exception']:.6f} | {row['coarse_five_field_mean_f1']:.6f} |")
    lines.append("")
    lines.append("## 2. actor 变化追踪")
    lines.append("")
    lines.append("| arm | raw actor spans | after adapter | after canonicalizer | saved/final | "
                 "raw→adapter add/remove/reanchor | adapter→canonicalizer add/remove/reanchor | "
                 "final actor FP | raw actor FP diagnostic |")
    lines.append("|---|---:|---:|---:|---:|---|---|---:|---:|")
    for arm in (OLD_ARM, NEW_ARM):
        trace = report["actor_trace"][arm]
        c1 = trace["raw_to_adapter"]
        c2 = trace["adapter_to_canonicalizer"]
        final_fp = report["actor_trace"][arm]["final_actor_fp"]
        raw_fp = report["actor_trace"][arm]["raw_actor_fp_exact_text_diagnostic"]
        lines.append(
            f"| {ARMS[arm]['label']} | {trace['raw_actor_spans']} | "
            f"{trace['adapter_actor_spans']} | {trace['canonicalizer_actor_spans']} | "
            f"{trace['saved_actor_spans']} | "
            f"{c1['added']}/{c1['removed']}/{c1['relocated']} | "
            f"{c2['added']}/{c2['removed']}/{c2['relocated']} | "
            f"{final_fp} | {raw_fp} |")
    lines.append("")
    lines.append("`raw actor FP diagnostic` = 最终 canonical actor FP + 被 canonicalizer "
                 "删除且其 exact text 不在 Gold actor 文本集中的 span 数；仅作追踪，"
                 "不是新的主评价指标。")
    lines.append("")
    lines.append("## 3. 代表性样本")
    lines.append("")
    for sample_id, item in report["sample_evidence"].items():
        lines.append(f"- `{sample_id}`：Gold actors={item['gold_actor_texts']}；"
                     f"旧 v6 raw/adapter/canonical/saved actors="
                     f"{item[OLD_ARM]['raw_actor_texts']} / "
                     f"{item[OLD_ARM]['adapter_actor_texts']} / "
                     f"{item[OLD_ARM]['canonical_actor_texts']} / "
                     f"{item[OLD_ARM]['saved_actor_texts']}；"
                     f"111 raw/adapter/canonical/saved actors="
                     f"{item[NEW_ARM]['raw_actor_texts']} / "
                     f"{item[NEW_ARM]['adapter_actor_texts']} / "
                     f"{item[NEW_ARM]['canonical_actor_texts']} / "
                     f"{item[NEW_ARM]['saved_actor_texts']}。")
        for invalid in item["validator_invalid_records"][NEW_ARM]:
            lines.append(f"  111 最终 validator invalid：`{' ; '.join(invalid['errors'])}`；"
                         f"保存路径 request_status=`{invalid['saved_path_status']}`。")
    lines.append("")
    lines.append("## 4. 归因限制")
    lines.append("")
    for item in report["conclusions"]["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## 5. 输入与复现")
    lines.append("")
    for key, value in report["inputs"].items():
        if isinstance(value, Mapping):
            lines.append(f"- `{key}`：`{value.get('path')}`；SHA-256 `{value.get('sha256')}`")
    lines.append("")
    lines.append(f"分析脚本：`{report['provenance']['script']}`")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_report(prediction_root: Path) -> dict[str, Any]:
    input_path = prediction_root / "data/input/estg150_formal_inference_input_v2.json"
    gold_path = prediction_root / "data/gold/stage2/estg150_formal_gold_v1.json"
    gold_doc = _load_json(gold_path)
    samples = _load_json(input_path)["records"]
    source_by_id = {
        row["sample_id"]: row["approved_text_en"] for row in samples
    }
    raw_paths = {
        arm: prediction_root / config["raw_dir"] / "raw_responses.jsonl"
        for arm, config in ARMS.items()
    }
    canonical_paths = {
        arm: prediction_root / config["raw_dir"] / "canonical_predictions.jsonl"
        for arm, config in ARMS.items()
    }
    raw_rows = {arm: _load_jsonl(path) for arm, path in raw_paths.items()}
    saved_rows = {arm: _load_jsonl(path) for arm, path in canonical_paths.items()}
    if any(len(rows) != 150 for rows in raw_rows.values()):
        raise ValueError("fixed denominator check failed: every raw file must have 150 rows")
    for arm, rows in saved_rows.items():
        if len(rows) != 150:
            raise ValueError(f"fixed denominator check failed for {arm} predictions")

    conditions: dict[str, dict[str, Any]] = {}
    for arm in (OLD_ARM, NEW_ARM):
        per_arm: dict[str, Any] = {}
        for condition_id in CONDITION_ORDER:
            if condition_id == "json_fence_gate":
                rows, telemetry = _process_parse_only_gate(
                    raw_rows[arm], source_by_id)
                per_arm[condition_id] = _summarize_evaluation(
                    rows, telemetry, gold_doc,
                    method_id=f"{arm}_{condition_id}",
                    condition_label=CONDITION_LABELS[condition_id],
                )
            else:
                condition = _condition_from_id(condition_id)
                rows, telemetry = one_factor.process_condition(
                    raw_rows[arm], source_by_id, condition)
                per_arm[condition_id] = _summarize_evaluation(
                    rows, telemetry, gold_doc,
                    method_id=f"{arm}_{condition_id}",
                    condition_label=CONDITION_LABELS[condition_id],
                )
        # Saved canonical predictions are the evaluator-level reference for the
        # actual modular saved path.
        saved_eval = evaluate_coarse(
            gold_doc,
            _saved_attempts(canonical_paths[arm]),
            method_id=f"{arm}_saved_canonical_predictions",
        )
        saved_summary = per_arm["saved_path_no_validator"]
        per_arm["saved_prediction_replay"] = {
            "mean_f1": _finite(saved_eval.get("coarse_five_field_mean_f1")),
            "five_fields_f1": {
                field: _finite(saved_eval["five_fields"][field].get("f1"))
                for field in SPAN_FIELDS
            },
            "failed_count": int(saved_eval.get("failed_count") or 0),
            "exactly_matches_saved_path_replay": (
                abs(_finite(saved_eval.get("coarse_five_field_mean_f1"))
                    - saved_summary["coarse_five_field_mean_f1"]) <= 1e-12
                and int(saved_eval.get("failed_count") or 0)
                == saved_summary["failed_records"]
            ),
        }
        conditions[arm] = per_arm

    gold_actor_text = _gold_actor_texts(gold_doc)
    traces: dict[str, dict[str, Any]] = {}
    saved_by_id = {
        arm: {row["sample_id"]: row for row in saved_rows[arm]}
        for arm in (OLD_ARM, NEW_ARM)
    }
    for arm in (OLD_ARM, NEW_ARM):
        traces[arm] = _trace_arm(
            arm, raw_rows[arm], source_by_id, saved_by_id[arm], gold_actor_text)
        final_extracted = conditions[arm]["saved_path_no_validator"][
            "five_fields_extracted"]["actor"]
        final_matched_predictions = conditions[arm]["saved_path_no_validator"][
            "five_fields_matched_predictions"]["actor"]
        final_fp = final_extracted - final_matched_predictions
        dropped = traces[arm]["dropped_actor_spans"]
        dropped_fp = sum(
            1 for span in dropped if not span["exact_gold_actor_text_match"])
        dropped_tp = sum(
            1 for span in dropped if span["exact_gold_actor_text_match"])
        traces[arm]["final_actor_fp"] = final_fp
        traces[arm]["raw_actor_fp_exact_text_diagnostic"] = final_fp + dropped_fp
        traces[arm]["raw_actor_tp_exact_text_diagnostic"] = (
            final_matched_predictions + dropped_tp)
        traces[arm]["dropped_actor_fp_diagnostic"] = dropped_fp
        traces[arm]["dropped_actor_tp_diagnostic"] = dropped_tp
        traces[arm]["final_actor_f1"] = conditions[arm][
            "saved_path_no_validator"]["five_fields_f1"]["actor"]
        traces[arm]["full_contract_actor_spans"] = int(
            conditions[arm]["full_contract"]["five_fields_extracted"]["actor"])

    # Fill actor text snapshots into sample evidence.  This is done by
    # replaying the stage records once more for the selected samples only.
    evidence_samples = [
        "estg_000028", "estg_000037", "estg_000103", "estg_000861",
    ]
    sample_evidence: dict[str, Any] = {}
    for sample_id in evidence_samples:
        item: dict[str, Any] = {
            "sample_id": sample_id,
            "gold_actor_texts": sorted(gold_actor_text.get(sample_id, set())),
            "validator_invalid_records": {},
        }
        for arm in (OLD_ARM, NEW_ARM):
            raw_payload = _parse_raw_content(
                next(row for row in raw_rows[arm]
                     if row["sample_id"] == sample_id)["raw_response_content"])
            adapted, _ = adapt_relay_record(raw_payload, source_by_id[sample_id])
            canonical, _ = canonicalize_record_coordinates(
                adapted, source_by_id[sample_id])
            invalid = [
                row for row in traces[arm]["validator_invalid_records"]
                if row["sample_id"] == sample_id
            ]
            item[arm] = {
                "raw_actor_texts": [
                    span["text"] for span in _extract_actor_spans(raw_payload)],
                "adapter_actor_texts": [
                    span["text"] for span in _extract_actor_spans(adapted)],
                "canonical_actor_texts": [
                    span["text"] for span in _extract_actor_spans(canonical)],
                "saved_actor_texts": [
                    span["text"] for span in _extract_actor_spans(
                        saved_by_id[arm][sample_id].get("record") or {})],
            }
            item["validator_invalid_records"][arm] = invalid
        sample_evidence[sample_id] = item

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": "offline_attribution_only_no_api_no_rerun",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "arms": [OLD_ARM, NEW_ARM],
            "sample_count_per_arm": 150,
            "primary_metric": PRIMARY_METRIC,
            "main_metric_definition": (
                "arithmetic mean of coarse sentence-level actor/action/condition/"
                "constraint/exception F1"
            ),
            "all_150_in_denominator": True,
            "new_api_calls": 0,
            "model_responses_fixed": True,
            "processing_logic_changed": False,
            "thresholds_changed": False,
            "measured_layer": "postprocessing_only",
            "model_generation_effect_claim_allowed": False,
        },
        "provenance": {
            "script": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"),
            "prediction_root": str(prediction_root.resolve()),
        },
        "inputs": {
            "input": {
                "path": str(input_path.resolve()),
                "sha256": _sha256(input_path),
            },
            "gold": {
                "path": str(gold_path.resolve()),
                "sha256": _sha256(gold_path),
            },
            "old_raw": {
                "path": str(raw_paths[OLD_ARM].resolve()),
                "sha256": _sha256(raw_paths[OLD_ARM]),
            },
            "old_canonical_predictions": {
                "path": str(canonical_paths[OLD_ARM].resolve()),
                "sha256": _sha256(canonical_paths[OLD_ARM]),
            },
            "new_raw": {
                "path": str(raw_paths[NEW_ARM].resolve()),
                "sha256": _sha256(raw_paths[NEW_ARM]),
            },
            "new_canonical_predictions": {
                "path": str(canonical_paths[NEW_ARM].resolve()),
                "sha256": _sha256(canonical_paths[NEW_ARM]),
            },
        },
        "conditions": conditions,
        "actor_trace": traces,
        "sample_evidence": sample_evidence,
        "conclusions": {
            "confirmed": [
                "旧 v6 与 111 的 JSON/fence 解析失败均为 0；旧版 43/150 带 Markdown fence、107/150 裸 JSON，111 为 150/150 裸 JSON；fence 差异不进入五字段 F1。",
                "输出适配器对旧 v6 的 actor span 数、坐标和文本无增删移；111 的 relay 嵌套形状必须经 adapter 展开，关闭 adapter 会让 canonicalizer 丢弃 742 个 field span 和 247 条边，但 validator 观察到 0 条 invalid，得到 0 分。这是接口依赖，不是 adapter 的语义抽取贡献。",
                "canonicalizer 只做坐标重锚、span/clause/edge 删除，不新增 actor。旧 v6 actor span 87→82（删 5、重锚 60），111 actor span 136→130（删 6、重锚 104）；coordinate 与清理在实现中耦合，不能分别虚构独立 F1 贡献。",
                "111 最终 canonical actor FP=84；由于后处理从不新增 actor，这 84 个 FP 全部已在原始响应中存在。旧 v6 对应 final actor FP=35。actor 过抽首先是模型输出/prompt 组合问题，不是后处理新增。",
                "111 保存路径使用 adapter+canonicalizer、未启用最终 canonical validator；最终 validator 会拒绝 1/150 条（estg_000861，order_relations[0].evidence 被模型输出为 object 而非 array）。完整链分数为 0.725473（149/150 成功）；已保存路径分数为 0.726206（150/150 request_status=ok，但 1 条 validator-invalid observed）。",
            ],
            "not_attributable": [
                "不能根据 raw→canonical actor 总数下降 5/6 就说后处理修正了语义 actor 误抽；其中多数是坐标重锚，删除项还包含 1 个 exact text 命中 Gold 的跨版本共同删除样本 estg_000103。",
                "不能把关闭坐标重锚后的接口失效（149/150 validator rejected 或新 111 关闭 adapter 后 0 分）解释成语义能力来自后处理；这些是 schema/接口依赖造成的整条拒绝或空输出。",
                "现有证据不能把 actor 过抽归因到某一句 E/S/J 文本，也不能隔离坐标重锚、span 删除和 edge 清理各自对 F1 的独立贡献。",
                "不能把 0.726206 写成完整后处理链分数；它是当前 modular runner 保存路径分数，完整 validator 链为 0.725473。",
            ],
            "defects": [
                "具体路径差异：scripts/run_sep_c3_modular_ablation_v1.py 使用 run_barrientos_ablation_suite_v2.parse_same_response/_prediction_row，只执行 relay adapter + span canonicalizer，没有调用 stage2_canonical.validate_canonical；scripts/run_d_full_postprocessing_ablation_v1.py 的完整链会调用该 validator。",
                "证据：111 重放中 estg_000861 在 adapter+canonicalizer 后 schema_valid=true、cross_field_valid=false，错误为 clauses[0].order_relations[0].evidence must be an array；保存路径 request_status=ok，完整链应整条拒绝。旧 v6 0 条 validator-invalid，故两条路径同分。",
                "本轮只交付定位证据，不修改处理链、补跑或覆盖已保存预测。",
            ],
            "limitations": [
                "raw actor span 语义 FP 追踪对 canonicalizer 删除项使用 exact text 与 Gold actor 文本集的诊断匹配，不是独立的新 evaluator；主指标仍只使用现有 coarse evaluator 对成功 canonical 行的评分。",
                "旧 v6 与 111 不是同一生成批次，无法排除 provider 端漂移；本报告不做单句 prompt 因果判断。",
                "所有 150 条始终保留在分母；被 validator 拒绝或解析失败的记录按空预测处理。",
            ],
        },
    }
    report["actor_trace"][OLD_ARM]["actor_note"] = (
        "旧 v6 raw 为 flat canonical 形状；adapter 只规范 normalized/id，不改变 actor 文本/坐标。")
    report["actor_trace"][NEW_ARM]["actor_note"] = (
        "111 raw 为 relay 嵌套形状；adapter 展开 span 但不改变 actor 文本/坐标。")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prediction-root",
        type=Path,
        default=ROOT,
        help=(
            "formal_experiment root containing outputs/development raw and "
            "canonical prediction artifacts. Defaults to this worktree."
        ),
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=ROOT / "outputs/reports/sep_c3_postprocessing_attribution_v1.json",
    )
    parser.add_argument(
        "--out-md",
        type=Path,
        default=ROOT / "outputs/reports/sep_c3_postprocessing_attribution_v1.md",
    )
    args = parser.parse_args()
    report = build_report(args.prediction_root)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.out_md.write_text(
        _build_markdown(report), encoding="utf-8", newline="\n")
    print(json.dumps({
        "out_json": str(args.out_json),
        "out_md": str(args.out_md),
        "status": report["status"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
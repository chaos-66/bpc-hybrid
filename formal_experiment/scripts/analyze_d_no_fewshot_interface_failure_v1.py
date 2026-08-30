# -*- coding: utf-8 -*-
"""Diagnose the completed D-no-fewshot-0813 zero score offline.

This script never sends a model request.  It reads the locally retained raw
responses from the completed 1140-call run, measures the emitted coordinate
shape, and performs a *retrospective diagnostic replay* with a deterministic
compatibility bridge for ``[start, end]`` coordinate pairs.  The replay is not
a replacement formal result and must not be presented as a preregistered
ablation arm; it exists to distinguish semantic emptiness from an output-
interface mismatch.

The original raw responses live under ``outputs/development`` and are ignored
by Git because the EStG source material is not redistributable.  The checked-in
report therefore binds them by SHA-256 and records that local-only boundary.
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

from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates
from bpc_hybrid.stage2_canonical import validate_canonical

SOURCE_DIR = (
    ROOT / "outputs/development/barrientos_ablation_suite_v2/"
    "D-no-fewshot-0813/repeat-01"
)
RAW_PATH = SOURCE_DIR / "raw_responses.jsonl"
CURRENT_CANONICAL_PATH = SOURCE_DIR / "canonical_predictions.jsonl"
CURRENT_EVALUATION_PATH = SOURCE_DIR / "evaluation.json"
LOCAL_OUTPUT_DIR = (
    ROOT / "outputs/development/d_no_fewshot_interface_diagnosis_v1"
)
REPORT_JSON = ROOT / "outputs/reports/d_no_fewshot_interface_diagnosis_v1.json"
REPORT_MD = ROOT / "outputs/reports/d_no_fewshot_interface_diagnosis_v1.md"

FIELD_ID_KEYS = {
    "actors": ("id", "actor_id"),
    "actions": ("id", "action_id"),
    "conditions": ("id", "condition_id"),
    "constraints": ("id", "constraint_id"),
    "exceptions": ("id", "exception_id"),
}


class DiagnosisError(RuntimeError):
    """Raised when the persisted run cannot support a safe diagnosis."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise DiagnosisError(f"{path}:{line_number}: row is not an object")
        rows.append(value)
    return rows


def _parse_raw_content(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        raise ValueError("raw_response_content_not_string")
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("payload_not_object")
    return payload


def _pair(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, list) or len(value) != 2:
        return None
    start, end = value
    if (not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)):
        return None
    return start, end


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _coordinates(item: Mapping[str, Any]) -> tuple[int, int] | None:
    start, end = item.get("start"), item.get("end")
    if (isinstance(start, int) and not isinstance(start, bool)
            and isinstance(end, int) and not isinstance(end, bool)):
        return start, end
    pair = _pair(item.get("span"))
    if pair is not None:
        return pair
    nested = item.get("span")
    if isinstance(nested, Mapping):
        return _coordinates(nested)
    return None


def _plain_span(
    item: Any,
    source_text: str,
    audit: dict[str, int],
    counter_key: str,
) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        audit["unrecoverable_spans"] += 1
        return None
    coords = _coordinates(item)
    if coords is None:
        audit["unrecoverable_spans"] += 1
        return None
    start, end = coords
    if not (0 <= start < end <= len(source_text)):
        audit["unrecoverable_spans"] += 1
        return None
    text = item.get("text")
    if not isinstance(text, str) or not text:
        text = source_text[start:end]
        audit["texts_filled_from_source"] += 1
    if _pair(item.get("span")) is not None:
        audit[counter_key] += 1
    return {"text": text, "start": start, "end": end}


def _supported_span(
    item: Any,
    source_text: str,
    field: str,
    index: int,
    clause_id: str,
    audit: dict[str, int],
) -> dict[str, Any] | None:
    plain = _plain_span(
        item, source_text, audit, "field_coordinate_pairs_converted")
    if plain is None or not isinstance(item, Mapping):
        return None
    span_id = next(
        (item.get(key) for key in FIELD_ID_KEYS[field]
         if isinstance(item.get(key), str) and item.get(key)),
        None,
    )
    if span_id is None:
        singular = field[:-1]
        span_id = f"{clause_id}.{singular}.{index + 1}"
        audit["ids_filled_deterministically"] += 1
    return {
        "id": span_id,
        **plain,
        "normalized": (
            item.get("normalized")
            if isinstance(item.get("normalized"), str)
            and item.get("normalized")
            else _normalized(plain["text"])
        ),
    }


def bridge_coordinate_pair_record(
    payload: Mapping[str, Any],
    source_text: str,
) -> tuple[dict[str, Any], dict[str, int]]:
    """Convert the observed no-fewshot relay shape to canonical coordinates.

    Only representational operations are allowed: list-pair coordinates become
    named offsets, ``modality.type`` becomes the canonical ``label`` key,
    field-specific ID keys become ``id``, and missing normalized strings are
    deterministically derived.  No span text, modality value, field membership,
    clause split, or relation is selected using Gold.
    """
    audit = {
        "records": 1,
        "clause_coordinate_pairs_converted": 0,
        "field_coordinate_pairs_converted": 0,
        "modality_type_keys_converted": 0,
        "ids_filled_deterministically": 0,
        "texts_filled_from_source": 0,
        "unrecoverable_spans": 0,
        "unrecoverable_clauses": 0,
    }
    clauses = payload.get("clauses")
    if not isinstance(clauses, list):
        raise DiagnosisError("payload clauses is not an array")
    rebuilt_clauses: list[dict[str, Any]] = []
    for ci, raw_clause in enumerate(clauses):
        if not isinstance(raw_clause, Mapping):
            audit["unrecoverable_clauses"] += 1
            continue
        clause_id = raw_clause.get("clause_id")
        if not isinstance(clause_id, str) or not clause_id:
            clause_id = f"clause_{ci + 1}"
        clause_span = _plain_span(
            {"span": raw_clause.get("clause_span")}
            if _pair(raw_clause.get("clause_span")) is not None
            else raw_clause.get("clause_span"),
            source_text,
            audit,
            "clause_coordinate_pairs_converted",
        )
        if clause_span is None:
            audit["unrecoverable_clauses"] += 1
            continue
        modality = raw_clause.get("modality")
        if not isinstance(modality, Mapping):
            modality = {}
        label = modality.get("label")
        if not isinstance(label, str):
            label = modality.get("type")
            if isinstance(label, str):
                audit["modality_type_keys_converted"] += 1
        evidence: list[dict[str, Any]] = []
        raw_evidence = modality.get("evidence")
        if isinstance(raw_evidence, list):
            for item in raw_evidence:
                span = _plain_span(
                    item, source_text, audit,
                    "field_coordinate_pairs_converted")
                if span is not None:
                    evidence.append(span)
        clause: dict[str, Any] = {
            "clause_id": clause_id,
            "clause_span": clause_span,
            "modality": {"label": label, "evidence": evidence},
        }
        for field in FIELD_ID_KEYS:
            output: list[dict[str, Any]] = []
            values = raw_clause.get(field)
            if isinstance(values, list):
                for index, item in enumerate(values):
                    span = _supported_span(
                        item, source_text, field, index, clause_id, audit)
                    if span is not None:
                        output.append(span)
            clause[field] = output
        clause["actor_action_map"] = copy.deepcopy(
            raw_clause.get("actor_action_map")
            if isinstance(raw_clause.get("actor_action_map"), list) else [])
        relations: list[dict[str, Any]] = []
        raw_relations = raw_clause.get("order_relations")
        if isinstance(raw_relations, list):
            for relation in raw_relations:
                if not isinstance(relation, Mapping):
                    continue
                converted = {
                    "before_action_id": relation.get("before_action_id"),
                    "after_action_id": relation.get("after_action_id"),
                    "evidence": [],
                }
                raw_relation_evidence = relation.get("evidence")
                if isinstance(raw_relation_evidence, list):
                    for item in raw_relation_evidence:
                        span = _plain_span(
                            item, source_text, audit,
                            "field_coordinate_pairs_converted")
                        if span is not None:
                            converted["evidence"].append(span)
                relations.append(converted)
        clause["order_relations"] = relations
        rebuilt_clauses.append(clause)

    unsupported = payload.get("unsupported_or_ambiguous")
    if not isinstance(unsupported, list):
        unsupported = []
    record = {
        "schema_version": "1.0.0",
        "sample_id": payload.get("sample_id"),
        "source_id": payload.get("source_id") or payload.get("sample_id"),
        "source_text": source_text,
        "clauses": rebuilt_clauses,
        "method": {
            "name": "direct_llm",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {
            "schema_valid": True,
            "cross_field_valid": True,
            "errors": [],
        },
        "unsupported_or_ambiguous": copy.deepcopy(unsupported),
    }
    canonical, span_audit = canonicalize_record_coordinates(
        record, source_text)
    audit["canonicalizer_reanchored"] = span_audit["reanchored_count"]
    audit["canonicalizer_dropped_spans"] = len(
        span_audit.get("dropped_spans", []))
    audit["canonicalizer_dropped_clauses"] = len(
        span_audit.get("dropped_clauses", []))
    return canonical, audit


def _sum_audits(total: dict[str, int], row: Mapping[str, int]) -> None:
    for key, value in row.items():
        total[key] = total.get(key, 0) + int(value)


def replay_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    source_by_id: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    predictions: list[dict[str, Any]] = []
    stats: dict[str, Any] = {
        "sample_count": len(raw_rows),
        "json_parse_success": 0,
        "json_parse_failure": 0,
        "raw_nonempty_clause_records": 0,
        "raw_clause_count": 0,
        "raw_clause_span_array_count": 0,
        "raw_clause_span_object_count": 0,
        "raw_field_span_count": 0,
        "raw_field_span_array_coordinate_count": 0,
        "raw_field_span_flat_coordinate_count": 0,
        "recovered_valid_record_count": 0,
        "recovered_nonempty_clause_records": 0,
        "recovered_clause_count": 0,
        "bridge_operations": {},
        "failures": [],
        "examples": [],
    }
    for raw_row in raw_rows:
        sid = raw_row.get("sample_id")
        if not isinstance(sid, str) or sid not in source_by_id:
            raise DiagnosisError(f"unknown sample_id in raw rows: {sid!r}")
        source_text = source_by_id[sid]
        try:
            payload = _parse_raw_content(raw_row.get("raw_response_content"))
            stats["json_parse_success"] += 1
        except (ValueError, json.JSONDecodeError) as exc:
            stats["json_parse_failure"] += 1
            stats["failures"].append(
                {"sample_id": sid, "stage": "json_parse", "error": str(exc)})
            predictions.append({
                "sample_id": sid,
                "request_status": "failed",
                "error": f"non-json: {exc}",
                "record": {},
            })
            continue
        if payload.get("source_text") != source_text:
            raise DiagnosisError(f"{sid}: raw source_text differs from frozen input")
        clauses = payload.get("clauses")
        if not isinstance(clauses, list):
            clauses = []
        if clauses:
            stats["raw_nonempty_clause_records"] += 1
        stats["raw_clause_count"] += len(clauses)
        for clause in clauses:
            if not isinstance(clause, Mapping):
                continue
            if _pair(clause.get("clause_span")) is not None:
                stats["raw_clause_span_array_count"] += 1
            elif isinstance(clause.get("clause_span"), Mapping):
                stats["raw_clause_span_object_count"] += 1
            modality = clause.get("modality")
            span_groups: list[Any] = [clause.get(field) for field in FIELD_ID_KEYS]
            if isinstance(modality, Mapping):
                span_groups.append(modality.get("evidence"))
            for group in span_groups:
                if not isinstance(group, list):
                    continue
                for item in group:
                    stats["raw_field_span_count"] += 1
                    if isinstance(item, Mapping) and _pair(item.get("span")):
                        stats["raw_field_span_array_coordinate_count"] += 1
                    elif (isinstance(item, Mapping)
                          and isinstance(item.get("start"), int)
                          and isinstance(item.get("end"), int)):
                        stats["raw_field_span_flat_coordinate_count"] += 1
        try:
            record, audit = bridge_coordinate_pair_record(payload, source_text)
            report = validate_canonical(record)
            if not (report.schema_valid and report.cross_field_valid):
                raise DiagnosisError("; ".join(report.errors))
            stats["recovered_valid_record_count"] += 1
            if record.get("clauses"):
                stats["recovered_nonempty_clause_records"] += 1
            stats["recovered_clause_count"] += len(record.get("clauses") or [])
            _sum_audits(stats["bridge_operations"], audit)
            predictions.append({
                "sample_id": sid,
                "request_status": "ok",
                "response_sha256": raw_row.get("response_sha256"),
                "request_id": raw_row.get("request_id"),
                "record": record,
            })
            if len(stats["examples"]) < 5:
                stats["examples"].append({
                    "sample_id": sid,
                    "raw_clause_count": len(clauses),
                    "recovered_clause_count": len(record.get("clauses") or []),
                    "response_sha256": raw_row.get("response_sha256"),
                })
        except (DiagnosisError, KeyError, TypeError, ValueError) as exc:
            stats["failures"].append({
                "sample_id": sid,
                "stage": "diagnostic_bridge_or_validation",
                "error": str(exc),
            })
            predictions.append({
                "sample_id": sid,
                "request_status": "failed",
                "error": f"diagnostic bridge: {exc}",
                "record": {},
            })
    if len(predictions) != len(raw_rows):
        raise DiagnosisError("diagnostic replay changed the denominator")
    return predictions, stats


def _jsonl_bytes(rows: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        .encode("utf-8")
        for row in rows
    )


def build_diagnosis(
    raw_path: Path = RAW_PATH,
    current_canonical_path: Path = CURRENT_CANONICAL_PATH,
    current_evaluation_path: Path = CURRENT_EVALUATION_PATH,
    evaluator: Callable[[Sequence[Mapping[str, Any]]], dict[str, Any]] | None = None,
    source_by_id: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    for path in (raw_path, current_canonical_path, current_evaluation_path):
        if not path.is_file():
            raise DiagnosisError(f"required local artifact missing: {path}")
    raw_rows = _load_jsonl(raw_path)
    current_rows = _load_jsonl(current_canonical_path)
    current_eval = json.loads(current_evaluation_path.read_text(encoding="utf-8"))
    if len(raw_rows) != 150 or len(current_rows) != 150:
        raise DiagnosisError("diagnosis requires the complete 150-row arm")
    if source_by_id is None:
        import run_barrientos_ablation_suite_v2 as runner
        source_by_id = {
            row["sample_id"]: row["text"] for row in runner._estg_samples()
        }
    predictions, stats = replay_rows(raw_rows, source_by_id)
    current_nonempty = sum(
        1 for row in current_rows
        if ((row.get("record") or {}).get("clauses") or []))
    current_clause_count = sum(
        len(((row.get("record") or {}).get("clauses") or []))
        for row in current_rows)
    if evaluator is None:
        import run_barrientos_ablation_suite_v2 as runner
        evaluator = runner._make_evaluator("D-no-fewshot-0813")
    recovered_evaluation = evaluator(predictions)
    metrics = recovered_evaluation.get("metrics") or {}
    overall = metrics.get("overall") or {}
    report = {
        "schema_version": "d_no_fewshot_interface_diagnosis@1.0.0",
        "status": "retrospective_development_diagnostic_not_formal_ablation",
        "scope": {
            "source_arm": "D-no-fewshot-0813",
            "source_run": "barrientos-de-0813-1140-v1",
            "sample_count": 150,
            "new_api_calls": 0,
            "gold_read": True,
            "gold_use": "evaluation_only_after_fixed_deterministic_bridge",
            "post_hoc_adapter_designed_after_observing_output_shape": True,
            "confirmatory_claim_allowed": False,
        },
        "provenance": {
            "raw_responses_path": str(raw_path.relative_to(ROOT)).replace("\\", "/"),
            "raw_responses_sha256": _sha256(raw_path),
            "raw_responses_distribution": "local_only_not_redistributed",
            "current_canonical_path": str(
                current_canonical_path.relative_to(ROOT)).replace("\\", "/"),
            "current_canonical_sha256": _sha256(current_canonical_path),
            "current_evaluation_path": str(
                current_evaluation_path.relative_to(ROOT)).replace("\\", "/"),
            "current_evaluation_sha256": _sha256(current_evaluation_path),
        },
        "observed_failure_mechanism": {
            "json_parse_success": stats["json_parse_success"],
            "json_parse_failure": stats["json_parse_failure"],
            "raw_nonempty_clause_records": stats["raw_nonempty_clause_records"],
            "raw_clause_count": stats["raw_clause_count"],
            "raw_clause_span_array_count": stats[
                "raw_clause_span_array_count"],
            "raw_clause_span_object_count": stats[
                "raw_clause_span_object_count"],
            "raw_field_span_count": stats["raw_field_span_count"],
            "raw_field_span_array_coordinate_count": stats[
                "raw_field_span_array_coordinate_count"],
            "raw_field_span_flat_coordinate_count": stats[
                "raw_field_span_flat_coordinate_count"],
            "current_canonical_nonempty_records": current_nonempty,
            "current_canonical_clause_count": current_clause_count,
            "root_cause": (
                "The no-fewshot response used [start,end] arrays for all 247 "
                "clause spans and most field spans. The locked adapter expected "
                "named or nested object offsets; the canonicalizer then treated "
                "every array-shaped clause_span as structurally invalid and "
                "dropped every clause."),
        },
        "retrospective_coordinate_bridge": {
            "allowed_operations": [
                "[start,end] -> {start,end}",
                "source_text[start:end] -> missing span text",
                "modality.type -> modality.label",
                "field-specific id key -> id",
                "casefold-whitespace normalized value when missing",
                "existing unique-exact-text canonicalizer",
                "existing canonical validator",
            ],
            "forbidden_operations": [
                "Gold-based span selection",
                "field reassignment",
                "modality relabeling",
                "fuzzy semantic recovery",
                "new model request",
            ],
            "operation_counts": stats["bridge_operations"],
            "valid_records": stats["recovered_valid_record_count"],
            "nonempty_clause_records": stats[
                "recovered_nonempty_clause_records"],
            "clause_count": stats["recovered_clause_count"],
            "failed_records": len(stats["failures"]),
            "evaluation": recovered_evaluation,
            "overall_precision": overall.get("precision"),
            "overall_recall": overall.get("recall"),
            "overall_f1": overall.get("f1"),
            "prediction_payload_sha256": _sha256_bytes(
                _jsonl_bytes(predictions)),
        },
        "current_locked_evaluation": current_eval,
        "examples": stats["examples"],
        "failure_examples": stats["failures"][:10],
        "scientific_interpretation": {
            "what_the_zero_score_shows": (
                "Removing the few-shot block broke end-to-end adherence to "
                "the locked six-field coordinate contract."),
            "what_the_zero_score_does_not_show": (
                "It does not show that the model extracted no semantic "
                "content: 146 records contained clauses before post-processing."),
            "few_shot_semantic_contribution_isolated": False,
            "reason": (
                "The observed effect mixes semantic prompting with output-"
                "format demonstration. A future clean arm must keep a "
                "machine-readable coordinate example or force the schema "
                "while removing only semantic examples."),
        },
    }
    return report, predictions, recovered_evaluation


def to_markdown(report: Mapping[str, Any]) -> str:
    observed = report["observed_failure_mechanism"]
    replay = report["retrospective_coordinate_bridge"]
    current = report["current_locked_evaluation"]["evaluation"]["metrics"]["overall"]
    lines = [
        "# D-no-fewshot-0813 F1=0 根因诊断 v1",
        "",
        "> 这是基于已完成响应的回顾性开发诊断：新增 API 调用为0。兼容桥是在"
        "看到输出形状后建立的，因此恢复分数不能作为预注册正式消融结果。",
        "",
        "## 结论",
        "",
        "`no-fewshot` 并不是没有抽取语义内容。150条中，"
        f"{observed['json_parse_success']}条可解析为 JSON，"
        f"{observed['raw_nonempty_clause_records']}条在原始响应中包含非空 clauses；"
        "F1=0 的直接原因是坐标表示与锁定后处理接口不兼容。",
        "",
        "## 失败发生在哪里",
        "",
        "| 检查项 | 数量 |",
        "|---|---:|",
        f"| JSON 可解析记录 | {observed['json_parse_success']}/150 |",
        f"| 原始非空 clause 记录 | {observed['raw_nonempty_clause_records']}/150 |",
        f"| 原始 clauses | {observed['raw_clause_count']} |",
        f"| clause_span 使用 `[start,end]` | {observed['raw_clause_span_array_count']} |",
        f"| clause_span 使用对象 | {observed['raw_clause_span_object_count']} |",
        f"| 原始字段/模态 spans | {observed['raw_field_span_count']} |",
        f"| 字段 span 使用 `[start,end]` | {observed['raw_field_span_array_coordinate_count']} |",
        f"| 当前 canonical 非空记录 | {observed['current_canonical_nonempty_records']}/150 |",
        f"| 当前 canonical clauses | {observed['current_canonical_clause_count']} |",
        "",
        "锁定适配器只接受命名坐标对象；规范化器随后把数组形态的247个"
        "clause_span全部判为不可用并删除，所以评价器看到的是空记录。",
        "",
        "## 回顾性兼容桥检查",
        "",
        "兼容桥只做坐标键名、模态键名和ID键名转换，不使用 Gold 选择或改写语义。"
        "转换后仍经过原有重锚和 canonical validator。",
        "",
        "| 条件 | 有效记录 | 非空记录 | Overall P | Overall R | Overall F1 |",
        "|---|---:|---:|---:|---:|---:|",
        f"| 当前锁定后处理 | {150 - report['current_locked_evaluation']['evaluation']['failed_count']} | "
        f"{observed['current_canonical_nonempty_records']} | "
        f"{current['precision']:.3f} | {current['recall']:.3f} | {current['f1']:.3f} |",
        f"| 回顾性坐标兼容桥 | {replay['valid_records']} | "
        f"{replay['nonempty_clause_records']} | "
        f"{replay['overall_precision']:.3f} | {replay['overall_recall']:.3f} | "
        f"{replay['overall_f1']:.3f} |",
        "",
        "恢复分数只用于证明零分主要来自接口失配，不能取代原始端到端结果，也不能"
        "被写成正式方法分数。",
        "",
        "## 对消融结论的修正",
        "",
        "- 可以说：删除 few-shot 后，模型不再稳定遵守本文锁定的坐标输出合同，"
        "端到端系统失效。",
        "- 不能说：删除 few-shot 后模型完全失去语义抽取能力。",
        "- 目前不能单独归因“few-shot 提升语义理解”，因为示例同时演示了字段语义"
        "和精确 JSON/坐标格式。",
        "- 后续干净消融应保留机器可读的坐标格式示例或强制 schema，只删除语义"
        "示例，从而把格式遵循与语义贡献拆开。",
        "",
        "## 证据边界",
        "",
        "原始响应包含受限 EStG 文本，只在本地保留；本报告通过 SHA-256 绑定来源，"
        "不重新分发原始响应。Gold 仅在固定兼容桥完成后用于评价。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    targets = (
        LOCAL_OUTPUT_DIR / "recovered_predictions.jsonl",
        LOCAL_OUTPUT_DIR / "evaluation.json",
        LOCAL_OUTPUT_DIR / "manifest.json",
        REPORT_JSON,
        REPORT_MD,
    )
    if not args.overwrite and any(path.exists() for path in targets):
        print("refusing to overwrite existing diagnosis v1")
        return 2
    try:
        report, predictions, evaluation = build_diagnosis()
        LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        prediction_bytes = _jsonl_bytes(predictions)
        (LOCAL_OUTPUT_DIR / "recovered_predictions.jsonl").write_bytes(
            prediction_bytes)
        (LOCAL_OUTPUT_DIR / "evaluation.json").write_text(
            json.dumps(evaluation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        manifest = {
            "schema_version": "d_no_fewshot_interface_diagnosis_manifest@1.0.0",
            "status": report["status"],
            "new_api_calls": 0,
            "sample_count": 150,
            "source_raw_sha256": report["provenance"]["raw_responses_sha256"],
            "recovered_predictions_sha256": _sha256_bytes(prediction_bytes),
            "evaluation_sha256": _sha256(
                LOCAL_OUTPUT_DIR / "evaluation.json"),
            "report_scope": "retrospective_development_diagnostic",
            "redistribution": "local_predictions_not_committed",
        }
        (LOCAL_OUTPUT_DIR / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        REPORT_JSON.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        REPORT_MD.write_text(to_markdown(report), encoding="utf-8")
        print(
            "diagnosis written; zero API calls; "
            f"recovered diagnostic F1={report['retrospective_coordinate_bridge']['overall_f1']:.6f}")
        return 0
    except (DiagnosisError, KeyError, OSError, TypeError, ValueError) as exc:
        print(f"refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

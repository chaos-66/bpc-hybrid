# -*- coding: utf-8 -*-
"""SEP-C4 v6 candidate: action-anchor disambiguation and evidence scope.

Zero real API, zero new model inference.  The script reuses the frozen v2
predictions (candidate labels, stored similarity values, stored lexical
coverage) and the frozen BPMN files under the panel paths.  It re-decides the
saved candidates with ``s3_semantic_grounding_v6``, recomputes every affected
check and the final decision, and writes new candidate artifacts only.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (SRC, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_v3 import evaluate_target_paired  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_v6 import (  # noqa: E402
    REVISION,
    disambiguate_action_grounding,
    score_sentence,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
V2_PREDICTIONS = ROOT / "outputs/evidence/s3_semantic_grounding_v2/predictions.jsonl"
V2_ARTIFACT_HASHES = ROOT / "outputs/evidence/s3_semantic_grounding_v2/artifact_hashes.json"
V5_PREDICTIONS = ROOT / "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl"
V5_ARTIFACT_HASHES = ROOT / "outputs/evidence/s3_semantic_grounding_v5/artifact_hashes.json"

EVIDENCE_DIR = ROOT / "outputs/evidence/sep_c4_action_anchor_scope_v1"
DEVELOPMENT_DIR = ROOT / "outputs/development/sep_c4_action_anchor_scope_v1"
REPORT_JSON = ROOT / "outputs/reports/sep_c4_action_anchor_scope_v1.json"
REPORT_MD = ROOT / "outputs/reports/sep_c4_action_anchor_scope_v1.md"
RUN_ID = "sep_c4_action_anchor_scope_v1"

_ACTIVITY_TYPES = {
    "task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
    "businessRuleTask", "scriptTask", "subProcess", "callActivity",
}
_EVENT_TYPES = {
    "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent",
    "boundaryEvent",
}
_GATEWAY_TYPES = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway", "complexGateway",
    "eventBasedGateway",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def _local(tag: Any) -> str:
    text = str(tag)
    return text.rsplit("}", 1)[-1] if "}" in text else text


def _node_type(element: Any) -> str:
    return _local(element.tag)


def _element_name(element: Any) -> str:
    return str(element.get("name") or "")


def read_bpmn(path: Path) -> tuple[dict[str, Any], ET.Element, bytes]:
    """Read the frozen BPMN surface with the same direct-child node model used
    by the Stage 1 parser, avoiding a line-ending-sensitive schema re-hash."""
    payload = path.read_bytes()
    root = ET.fromstring(payload)
    processes = [element for element in root.iter()
                 if _local(element.tag) == "process"]
    if len(processes) != 1:
        raise RuntimeError(f"{path}: expected exactly one process")
    process = processes[0]
    process_id = str(process.get("id") or "")
    direct_children = list(process)

    def nodes_of(types: set[str]) -> list[dict[str, Any]]:
        result = []
        for element in direct_children:
            node_type = _node_type(element)
            if node_type not in types:
                continue
            node_id = str(element.get("id") or "")
            if not node_id:
                continue
            result.append({
                "id": node_id,
                "name": _element_name(element),
                "type": node_type,
                "lane_ids": [],
            })
        return sorted(result, key=lambda item: item["id"])

    activities = nodes_of(_ACTIVITY_TYPES)
    events = nodes_of(_EVENT_TYPES)
    gateways = nodes_of(_GATEWAY_TYPES)
    node_ids = {item["id"] for item in activities + events + gateways}
    source_defaults = {
        str(element.get("id")): str(element.get("default") or "")
        for element in direct_children if element.get("id")
    }
    flows: list[dict[str, Any]] = []
    for element in direct_children:
        if _node_type(element) != "sequenceFlow":
            continue
        flow_id = str(element.get("id") or "")
        source_ref = str(element.get("sourceRef") or "").strip()
        target_ref = str(element.get("targetRef") or "").strip()
        if not flow_id or source_ref not in node_ids or target_ref not in node_ids:
            continue
        conditions = [
            " ".join("".join(child.itertext()).split())
            for child in list(element)
            if _local(child.tag) == "conditionExpression"
        ]
        condition = conditions[0] if conditions and conditions[0] else None
        flows.append({
            "id": flow_id,
            "name": _element_name(element),
            "source_ref": source_ref,
            "target_ref": target_ref,
            "condition_expression": condition,
            "is_default": source_defaults.get(source_ref) == flow_id,
        })
    flows.sort(key=lambda item: item["id"])
    record = {
        "process_id": process_id,
        "activities": activities,
        "events": events,
        "gateways": gateways,
        "sequence_flows": flows,
        "pools": [],
        "lanes": [],
    }
    return record, root, payload


def verify_v2_predictions() -> dict[str, Any]:
    expected = (read_json(V2_ARTIFACT_HASHES).get("artifacts") or {}).get(
        "outputs/evidence/s3_semantic_grounding_v2/predictions.jsonl")
    raw = sha256_file(V2_PREDICTIONS)
    canonical_lf = hashlib.sha256(
        V2_PREDICTIONS.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return {
        "path": "outputs/evidence/s3_semantic_grounding_v2/predictions.jsonl",
        "expected_sha256": expected,
        "actual_raw_sha256": raw,
        "actual_canonical_lf_sha256": canonical_lf,
        "match": bool(expected) and expected in {raw, canonical_lf},
    }


def _verify_optional_v5_predictions() -> dict[str, Any]:
    if not V5_PREDICTIONS.is_file() or not V5_ARTIFACT_HASHES.is_file():
        return {"available": False, "match": False}
    expected = (read_json(V5_ARTIFACT_HASHES).get("artifacts") or {}).get(
        "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl")
    raw = sha256_file(V5_PREDICTIONS)
    canonical_lf = hashlib.sha256(
        V5_PREDICTIONS.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    return {
        "available": True,
        "path": "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl",
        "expected_sha256": expected,
        "actual_raw_sha256": raw,
        "actual_canonical_lf_sha256": canonical_lf,
        "match": bool(expected) and expected in {raw, canonical_lf},
    }


def _row_check_snapshot(row: Mapping[str, Any], target: str) -> dict[str, Any]:
    check = (row.get("checks") or {}).get(target) or {}
    return {
        "status": check.get("status"),
        "observable": check.get("observable"),
        "violation": check.get("violation"),
    }


def _row_check_reason_snapshot(row: Mapping[str, Any], target: str) -> dict[str, Any]:
    check = (row.get("checks") or {}).get(target) or {}
    return {"reason": check.get("reason")}


def _action_snapshot(row: Mapping[str, Any]) -> dict[str, Any]:
    ground = row.get("action_grounding") or {}
    return {
        "status": ground.get("status"),
        "reason": ground.get("reason"),
        "activity_id": ground.get("activity_id"),
        "strong_activity_ids": ground.get("strong_activity_ids"),
    }


def build_change_record(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    before_action = _action_snapshot(before)
    after_action = _action_snapshot(after)
    action_identity_changed = (
        (before_action["status"], before_action["activity_id"])
        != (after_action["status"], after_action["activity_id"]))
    action_reason_changed = before_action["reason"] != after_action["reason"]
    check_changes: dict[str, Any] = {}
    check_reason_changes: dict[str, Any] = {}
    for target in EXTENDED_TYPES:
        old_reason = _row_check_reason_snapshot(before, target)
        new_reason = _row_check_reason_snapshot(after, target)
        old = _row_check_snapshot(before, target)
        new = _row_check_snapshot(after, target)
        if old != new:
            check_changes[target] = {
                "before": {**old, **old_reason},
                "after": {**new, **new_reason},
            }
        elif old_reason != new_reason:
            check_reason_changes[target] = {
                "before": old_reason, "after": new_reason}
    check_changes_with_reasons = {
        **check_changes,
        **check_reason_changes,
    }
    return {
        "item_id": before.get("item_id"),
        "side": before.get("side"),
        "expected_label": before.get("expected_label"),
        "action_grounding": {
            "before": before_action,
            "after": after_action,
            "identity_changed": action_identity_changed,
            "reason_changed": action_reason_changed,
        },
        "checks": check_changes_with_reasons,
        "check_reason_only_changes": check_reason_changes,
        "changed": bool(action_identity_changed or check_changes),
    }


def build_rows(panel: Mapping[str, Any], base_rows: Sequence[Mapping[str, Any]]
               ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    by_item = {item["variant_id"]: item for item in panel["variants"]}
    bpmn_cache: dict[Path, tuple[dict[str, Any], ET.Element, bytes]] = {}
    output: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    verified_bpmn: set[str] = set()
    for row in base_rows:
        item_id = str(row.get("item_id") or "")
        side = str(row.get("side") or "")
        variant = by_item.get(item_id)
        if variant is None:
            raise RuntimeError(f"row item_id not present in panel: {item_id}")
        rel_path = str(variant.get(f"{side}_bpmn") or "")
        if not rel_path:
            raise RuntimeError(f"{item_id}:{side} has no BPMN path")
        path = ROOT / rel_path
        expected_hash = str(variant.get(f"{side}_bpmn_sha256") or "")
        raw_hash = sha256_file(path)
        canonical_lf_hash = hashlib.sha256(
            path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if expected_hash and expected_hash not in {raw_hash, canonical_lf_hash}:
            raise RuntimeError(f"BPMN hash mismatch: {rel_path}")
        verified_bpmn.add(rel_path)
        if path not in bpmn_cache:
            bpmn_cache[path] = read_bpmn(path)
        record, xml_root, _ = bpmn_cache[path]

        old_ground = row.get("action_grounding") or {}
        new_ground = disambiguate_action_grounding(old_ground)
        score = score_sentence(row.get("model_visible_rule_input") or {},
                               record, xml_root, new_ground)
        new_row = copy.deepcopy(dict(row))
        new_row.update({
            "schema_version": "s3_semantic_grounding_v6_prediction@1.0.0",
            "revision": REVISION,
            "action_grounding": new_ground,
            "action_anchor_consistency": score.get("action_anchor_consistency"),
            "anchor_guard_changes": score.get("anchor_guard_changes"),
            "checks": score.get("checks"),
            "decision": score.get("decision"),
            "predicted_violation_type": (score.get("decision") or {}).get("predicted"),
            "scores": score.get("scores"),
            "observability": score.get("observability"),
        })
        output.append(new_row)
        change = build_change_record(row, new_row)
        changes.append(change)
    coverage = {
        "panel_variants": len(panel["variants"]),
        "base_rows": len(base_rows),
        "variant_rows": sum(1 for row in base_rows if row.get("side") == "variant"),
        "control_rows": sum(1 for row in base_rows if row.get("side") == "control"),
        "unique_bpmn_paths_verified": len(verified_bpmn),
        "model_similarity_recomputed": False,
        "model_inference_calls": 0,
        "real_api_calls": 0,
        "network_calls": 0,
        "saved_candidates_reused": True,
    }
    return output, changes, coverage


def _flatten_paired(paired: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "macro_f1_four_types": paired.get("macro_f1_four_types"),
        "pair_success_count": paired.get("pair_success_count"),
        "pair_success_rate": paired.get("pair_success_rate"),
        "target_field_unknown_rate": paired.get("target_field_unknown_rate"),
        "control_target_false_positive_rate": paired.get("control_target_false_positive_rate"),
        "per_type": {
            target: {
                "pairs": paired["per_type"][target]["pairs"],
                "f1": paired["per_type"][target]["f1"],
                "variant": paired["per_type"][target]["variant"],
                "control": paired["per_type"][target]["control"],
                "pair_success": paired["per_type"][target]["pair_success"],
                "pair_success_rate": paired["per_type"][target]["pair_success_rate"],
                "unknown_rate_variant": paired["per_type"][target]["unknown_rate_variant"],
                "unknown_rate_control": paired["per_type"][target]["unknown_rate_control"],
                "control_fpr_over_all_pairs": paired["per_type"][target][
                    "control_fpr_over_all_pairs"],
            }
            for target in EXTENDED_TYPES
        },
    }


def _paired_from_rows(rows: Sequence[Mapping[str, Any]],
                      expected_by_item: Mapping[str, str]) -> dict[str, Any]:
    return evaluate_target_paired(
        [row for row in rows if row.get("side") == "variant"],
        [row for row in rows if row.get("side") == "control"],
        expected_by_item,
    )


def _outcomes(rows: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, str]]:
    outcomes: dict[str, dict[str, str]] = {}
    for target in EXTENDED_TYPES:
        per_item: dict[str, str] = {}
        for row in rows:
            check = (row.get("checks") or {}).get(target) or {}
            if check.get("violation") is True:
                outcome = "positive"
            elif check.get("observable") is True and check.get("violation") is False:
                outcome = "negative"
            else:
                outcome = "unknown"
            per_item[f"{row.get('item_id')}:{row.get('side')}"] = outcome
        outcomes[target] = per_item
    return outcomes


def outcome_deltas(before_rows: Sequence[Mapping[str, Any]],
                   after_rows: Sequence[Mapping[str, Any]],
                   expected_by_item: Mapping[str, str]) -> dict[str, Any]:
    before = _outcomes(before_rows)
    after = _outcomes(after_rows)

    def pair_target(key: str) -> str | None:
        return expected_by_item.get(key.rsplit(":", 1)[0])

    result: dict[str, Any] = {}
    for target in EXTENDED_TYPES:
        before_positive = {
            key for key, value in before[target].items()
            if value == "positive" and pair_target(key) == target}
        after_positive = {
            key for key, value in after[target].items()
            if value == "positive" and pair_target(key) == target}
        result[target] = {
            "variant_tp_before": sum(1 for key in before_positive
                                     if key.endswith(":variant")),
            "variant_tp_after": sum(1 for key in after_positive
                                    if key.endswith(":variant")),
            "variant_tp_lost_items": sorted(key for key in before_positive - after_positive
                                            if key.endswith(":variant")),
            "variant_tp_gained_items": sorted(key for key in after_positive - before_positive
                                              if key.endswith(":variant")),
            "variant_unknown_before": sum(
                1 for key, value in before[target].items()
                if key.endswith(":variant") and pair_target(key) == target
                and value == "unknown"),
            "variant_unknown_after": sum(
                1 for key, value in after[target].items()
                if key.endswith(":variant") and pair_target(key) == target
                and value == "unknown"),
            "control_fp_before": sum(1 for key in before_positive
                                     if key.endswith(":control")),
            "control_fp_after": sum(1 for key in after_positive
                                    if key.endswith(":control")),
            "control_unknown_before": sum(
                1 for key, value in before[target].items()
                if key.endswith(":control") and pair_target(key) == target
                and value == "unknown"),
            "control_unknown_after": sum(
                1 for key, value in after[target].items()
                if key.endswith(":control") and pair_target(key) == target
                and value == "unknown"),
        }
    return result


def build_summary(paired: Mapping[str, Any]) -> dict[str, Any]:
    flat = _flatten_paired(paired)
    return {
        "macro_f1_four_types": flat["macro_f1_four_types"],
        "pair_success": flat["pair_success_count"],
        "pair_success_count": flat["pair_success_count"],
        "pair_success_rate": flat["pair_success_rate"],
        "target_field_unknown_rate": flat["target_field_unknown_rate"],
        "unknown_rate_variant": flat["target_field_unknown_rate"],
        "control_target_false_positive_rate": flat["control_target_false_positive_rate"],
        "control_false_positive_rate": flat["control_target_false_positive_rate"],
        "per_type": flat["per_type"],
    }


def render_markdown(metrics: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    before = metrics["baseline_v2"]
    after = metrics["candidate_v6"]
    v5 = metrics.get("baseline_v5") or {}
    lines = [
        "# SEP-C4 动作锚点消歧与证据作用范围最小离线修复候选 v1",
        "",
        "本候选（`s3_semantic_grounding_v6`）只复用冻结 v2 predictions 中已保存的"
        "候选标签、相似度和词面覆盖度，以及 panel 中冻结 BPMN 流程输入；"
        "真实 API=0，未启动模型推理，未重算相似度。所有检查与最终 decision 均由"
        "新锚点重新计算，历史 v2/v5/C36 产物未被覆盖。",
        "",
        "## 四类 target-paired 结果（40 对 / 80 条，分母完整）",
        "",
        "| Type | V6 variant TP/FN_obs/FN_unknown | V6 control TN/FP/unknown | V6 F1 | V2 F1 | V5 F1 | Pair success |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for target in EXTENDED_TYPES:
        row = after["per_type"][target]
        row_v2 = before["per_type"][target]
        row_v5 = (v5.get("per_type") or {}).get(target) or {}
        lines.append(
            f"| {target} | {row['variant']['TP']}/{row['variant']['FN_observed_negative']}/"
            f"{row['variant']['FN_unknown']} | {row['control']['TN']}/{row['control']['FP']}/"
            f"{row['control']['unknown']} | {row['f1']} | {row_v2['f1']} | "
            f"{row_v5.get('f1', '-')} | {row['pair_success']}/{row['pairs']} |"
        )
    lines += [
        "",
        f"- V6 target-paired macro-F1: **{after['macro_f1_four_types']}**",
        f"- V2 baseline macro-F1: **{before['macro_f1_four_types']}**",
        f"- V6 pair success: **{after['pair_success']}/40** "
        f"({after['pair_success_rate']})",
        f"- V6 target-field unknown rate: **{after['target_field_unknown_rate']}**",
        f"- V6 control target-field FP rate: **{after['control_target_false_positive_rate']}**",
        "",
        "## TP / unknown / control FP 变化",
        "",
    ]
    for target in EXTENDED_TYPES:
        delta = metrics["outcome_deltas"][target]
        lines.append(
            f"- {target}: variant TP {delta['variant_tp_before']}->"
            f"{delta['variant_tp_after']}; lost {delta['variant_tp_lost_items']}; "
            f"gained {delta['variant_tp_gained_items']}; variant unknown "
            f"{delta['variant_unknown_before']}->{delta['variant_unknown_after']}; "
            f"control FP {delta['control_fp_before']}->{delta['control_fp_after']}; "
            f"control unknown {delta['control_unknown_before']}->"
            f"{delta['control_unknown_after']}")
    lines += [
        "",
        "## 逐条变化",
        "",
        f"- Changed rows: **{metrics['changes']['changed_row_count']}** / "
        f"**{metrics['changes']['total_rows']}**",
        f"- Action-grounding status/id changes: "
        f"**{metrics['changes']['action_change_count']}**",
        f"- Action-grounding reason-only changes: "
        f"**{metrics['changes']['action_reason_change_count']}**",
        f"- Check behavior changes by target: "
        f"`{json.dumps(metrics['changes']['check_change_count_by_target'], ensure_ascii=False)}`",
        f"- Check reason-only changes by target: "
        f"`{json.dumps(metrics['changes']['check_reason_only_change_count_by_target'], ensure_ascii=False)}`",
        "",
        "变化条目保留 before/after 的 action grounding、各检查 status/observable/"
        "violation/reason；完整列表在 `change_report.changed_rows`。",
        "",
        "## 边界",
        "",
        "- 唯一精确匹配仍优先；词面 winner 与 semantic winner 冲突时保留 ambiguous。",
        "- 缺少 action/field 支持时 anchor 为 `unconfirmed`，不再写"
        " `resolved_label_is_action_consistent`。",
        "- resolved 时 constraint/exception 只从锚点动作和允许的局部结构取证据；"
        "ambiguous 时按候选逐一评估，非一致证据不做确定结论。",
        "- 抽象约束仍为 unsupported/unknown；上游 action 抽取问题本轮不改。",
        "- 这不是形式 Oracle，不要求 F1 上升；论文结论只能引用本 manifest 中"
        "已冻结的离线范围。",
        "",
        "## 来源",
        "",
        f"- v2 predictions SHA-256: `{manifest['inputs']['v2_predictions']['actual_raw_sha256']}`",
        f"- panel SHA-256: `{manifest['inputs']['panel']}`",
        f"- implementation: `{manifest['implementation']}`",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (EVIDENCE_DIR, DEVELOPMENT_DIR, REPORT_JSON,
                                      REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing SEP-C4 v6 candidate outputs")
    reuse = verify_v2_predictions()
    if not reuse["match"]:
        raise RuntimeError("v2 predictions hash mismatch; refusing to reuse")
    v5_reuse = _verify_optional_v5_predictions()
    panel = read_json(PANEL)
    base_rows = read_rows(V2_PREDICTIONS)
    expected_by_item = {item["variant_id"]: item["expected_violation"]
                        for item in panel["variants"]}
    candidate_rows, changes, coverage = build_rows(panel, base_rows)
    candidate_paired = _paired_from_rows(candidate_rows, expected_by_item)
    base_paired = _paired_from_rows(base_rows, expected_by_item)
    baseline_v5 = None
    if v5_reuse.get("available") and v5_reuse.get("match"):
        v5_rows = read_rows(V5_PREDICTIONS)
        baseline_v5 = build_summary(_paired_from_rows(v5_rows, expected_by_item))

    changed_rows = [change for change in changes if change.get("changed")]
    action_change_count = sum(1 for change in changed_rows
                              if change["action_grounding"]["identity_changed"])
    action_reason_change_count = sum(
        1 for change in changes
        if change["action_grounding"]["reason_changed"])
    check_change_count: dict[str, int] = {}
    check_reason_change_count: dict[str, int] = {}
    for change in changes:
        for target in change.get("checks", {}):
            if target in change.get("check_reason_only_changes", {}):
                check_reason_change_count[target] = (
                    check_reason_change_count.get(target, 0) + 1)
                continue
            check_change_count[target] = check_change_count.get(target, 0) + 1

    manifest = {
        "schema_version": "sep_c4_action_anchor_scope_manifest@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only_candidate",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "v2_predictions": reuse,
            "panel": sha256_file(PANEL),
            "v5_predictions_for_comparison": v5_reuse,
        },
        "implementation": {
            "module": "src/bpc_hybrid/s3_semantic_grounding_v6.py",
            "module_sha256": sha256_file(ROOT / "src/bpc_hybrid/s3_semantic_grounding_v6.py"),
            "runner": "scripts/run_sep_c4_action_anchor_scope_v1.py",
            "runner_sha256": sha256_file(Path(__file__)),
            "tests": "tests/test_s3_semantic_grounding_v6.py",
            "tests_sha256": sha256_file(ROOT / "tests/test_s3_semantic_grounding_v6.py"),
        },
        "coverage": coverage,
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "model_inference_calls": 0,
            "model_similarity_recomputed": False,
            "historical_predictions_overwritten": False,
            "thresholds_changed": False,
            "gold_modified": False,
            "panel_modified": False,
        },
        "new_output_paths": {
            "evidence": EVIDENCE_DIR.relative_to(ROOT).as_posix(),
            "development": DEVELOPMENT_DIR.relative_to(ROOT).as_posix(),
            "report_json": REPORT_JSON.relative_to(ROOT).as_posix(),
            "report_md": REPORT_MD.relative_to(ROOT).as_posix(),
        },
    }
    metrics = {
        "schema_version": "sep_c4_action_anchor_scope_metrics@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only_candidate",
        "read_only_reuse": reuse,
        "real_api_calls": 0,
        "network_calls": 0,
        "model_inference_calls": 0,
        "candidate_v6": build_summary(candidate_paired),
        "baseline_v2": build_summary(base_paired),
        "baseline_v5": baseline_v5,
        "target_paired_candidate_v6": candidate_paired,
        "target_paired_baseline_v2": base_paired,
        "outcome_deltas": outcome_deltas(base_rows, candidate_rows,
                                                expected_by_item),
        "changes": {
            "total_rows": len(changes),
            "changed_row_count": len(changed_rows),
            "action_change_count": action_change_count,
            "action_reason_change_count": action_reason_change_count,
            "check_change_count_by_target": check_change_count,
            "check_reason_only_change_count_by_target": check_reason_change_count,
            "changed_rows": changed_rows,
        },
    }
    report = {
        "schema_version": "sep_c4_action_anchor_scope_report@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "status": "CANDIDATE_OFFLINE_REPLAY_VERIFIED",
        "claim_boundary": (
            "Development-only frozen-panel replay. Candidate disambiguation and "
            "anchor-scoped evidence checks are code-verified; F1 is not required "
            "to increase. No real API/model inference/similarity recomputation."),
        "manifest": manifest,
        "metrics": metrics,
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    DEVELOPMENT_DIR.mkdir(parents=True, exist_ok=True)
    write_rows(EVIDENCE_DIR / "predictions.jsonl", candidate_rows)
    write_rows(DEVELOPMENT_DIR / "predictions.jsonl", candidate_rows)
    write_json(EVIDENCE_DIR / "change_report.json", metrics["changes"])
    write_json(DEVELOPMENT_DIR / "change_report.json", metrics["changes"])
    write_json(EVIDENCE_DIR / "metrics.json", metrics)
    write_json(DEVELOPMENT_DIR / "metrics.json", metrics)
    write_json(EVIDENCE_DIR / "manifest.json", manifest)
    write_json(DEVELOPMENT_DIR / "manifest.json", manifest)
    write_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_markdown(metrics, manifest), encoding="utf-8",
                         newline="\n")

    artifact_paths = [
        EVIDENCE_DIR / "predictions.jsonl", EVIDENCE_DIR / "change_report.json",
        EVIDENCE_DIR / "metrics.json", EVIDENCE_DIR / "manifest.json",
        DEVELOPMENT_DIR / "predictions.jsonl", DEVELOPMENT_DIR / "change_report.json",
        DEVELOPMENT_DIR / "metrics.json", DEVELOPMENT_DIR / "manifest.json",
        REPORT_JSON, REPORT_MD,
    ]
    write_json(EVIDENCE_DIR / "artifact_hashes.json", {
        "schema_version": "sep_c4_action_anchor_scope_artifact_hashes@1.0.0",
        "run_id": RUN_ID,
        "artifacts": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                      for path in artifact_paths},
    })
    return {"metrics": metrics, "manifest": manifest, "report": report}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    metrics = result["metrics"]
    after = metrics["candidate_v6"]
    print(json.dumps({
        "revision": REVISION,
        "target_paired_macro_f1": after["macro_f1_four_types"],
        "pair_success": f"{after['pair_success']}/40",
        "target_field_unknown_rate": after["unknown_rate_variant"],
        "control_target_fp_rate": after["control_false_positive_rate"],
        "changed_rows": metrics["changes"]["changed_row_count"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

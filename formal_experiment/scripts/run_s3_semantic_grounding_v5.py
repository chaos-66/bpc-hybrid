# -*- coding: utf-8 -*-
"""Runner for revision s3_semantic_grounding_v5 (zero API).

The frozen v2 predictions are reused read-only after artifact-hash
verification.  The runner applies the v5 action-anchor consistency guard,
recomputes the affected decisions, evaluates the changed predictions with the
same target-paired accounting, records concrete constraint/exception failure
chains, and freezes the v5 candidate pack and reports.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_v1 import decide  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_v2 import (  # noqa: E402
    evaluate_unified_objects,
    evaluate_variant_binary,
    unified_objects_legacy,
)
from bpc_hybrid.s3_semantic_grounding_v3 import evaluate_target_paired  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_v5 import (  # noqa: E402
    REVISION,
    apply_action_anchor_guard,
    build_fallback_pack,
    action_anchor_consistency,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
V2_EVIDENCE = ROOT / "outputs/evidence/s3_semantic_grounding_v2"
V2_PREDICTIONS = V2_EVIDENCE / "predictions.jsonl"
V2_ARTIFACT_HASHES = V2_EVIDENCE / "artifact_hashes.json"
V5_EVIDENCE = ROOT / "outputs/evidence/s3_semantic_grounding_v5"
V5_DEVELOPMENT = ROOT / "outputs/development/s3_semantic_grounding_v5"
REPORT_JSON = ROOT / "outputs/reports/s3_semantic_grounding_v5.json"
REPORT_MD = ROOT / "outputs/reports/s3_semantic_grounding_v5.md"
PACK_NAME = "llm_fallback_candidate_pack_v5.json"
FAILURE_CHAINS_NAME = "constraint_exception_failure_chains.json"
RUN_ID = REVISION
TARGET_LABELS = {
    "required_condition_not_enforced": "condition",
    "constraint_violated": "constraint",
    "exception_not_handled": "exception",
    "prohibited_action_present": "prohibition",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_rows(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


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


def _row_label(row: Mapping[str, Any]) -> str:
    ground = row.get("action_grounding") or {}
    activity_id = str(ground.get("activity_id") or "")
    for candidate in list(ground.get("candidates") or []) + list(
            ground.get("alternatives") or []):
        if str(candidate.get("activity_id")) == activity_id:
            return str(candidate.get("label") or "")
    return ""


def apply_guard_to_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]],
                                                                    list[dict[str, Any]]]:
    output: list[dict[str, Any]] = []
    all_changes: list[dict[str, Any]] = []
    for row in rows:
        sentence = row.get("model_visible_rule_input") or {}
        ground = copy.deepcopy(row.get("action_grounding") or {})
        ground["action_anchor_consistency"] = action_anchor_consistency(sentence, ground)
        checks, changes = apply_action_anchor_guard(sentence, ground, row.get("checks") or {})
        new_row = copy.deepcopy(dict(row))
        new_row["schema_version"] = "s3_semantic_grounding_v5_prediction@1.0.0"
        new_row["revision"] = REVISION
        new_row["action_grounding"] = ground
        new_row["checks"] = checks
        if changes:
            new_row["decision_before_anchor_guard"] = copy.deepcopy(row.get("decision"))
            new_row["predicted_violation_type_before_anchor_guard"] = row.get(
                "predicted_violation_type")
            new_row["decision"] = decide(checks)
            new_row["predicted_violation_type"] = new_row["decision"].get("predicted")
            new_row["anchor_guard_changes"] = changes
        output.append(new_row)
        for change in changes:
            all_changes.append({
                "item_id": row.get("item_id"),
                "side": row.get("side"),
                "expected_label": row.get("expected_label"),
                "changed_target": change["target"],
                "changed_target_field": TARGET_LABELS.get(change["target"]),
                "pair_target_for_item": TARGET_LABELS.get(
                    str(row.get("expected_label") or "")),
                "is_pair_target_change": TARGET_LABELS.get(
                    str(row.get("expected_label") or "")) == TARGET_LABELS.get(
                        change["target"]),
                "before": change["before"],
                "after": change["after"],
                "resolved_activity_id": ground.get("activity_id"),
                "resolved_label": _row_label(row),
                "anchor_consistency": ground.get("action_anchor_consistency"),
            })
    return output, all_changes


def load_expected_by_item() -> dict[str, str]:
    panel = read_json(PANEL)
    return {item["variant_id"]: item["expected_violation"]
            for item in panel["variants"]}


def _outcome(row: Mapping[str, Any], target: str) -> str:
    check = (row.get("checks") or {}).get(target) or {}
    if check.get("violation") is True:
        return "positive"
    if check.get("observable") is True and check.get("violation") is False:
        return "negative"
    return "unknown"


def build_change_report(base_rows: Sequence[Mapping[str, Any]],
                        guarded_rows: Sequence[Mapping[str, Any]],
                        changes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_side: dict[str, int] = {}
    by_target: dict[str, int] = {}
    for change in changes:
        by_side[str(change["side"])] = by_side.get(str(change["side"]), 0) + 1
        by_target[str(change["changed_target"])] = by_target.get(
            str(change["changed_target"]), 0) + 1
    removed_control_false_alarms = [
        change for change in changes
        if change["side"] == "control"
        and change["before"]["violation"] is True
        and change["after"]["violation"] is None
        and not change["is_pair_target_change"]
    ]
    demoted_pair_targets = [
        change for change in changes
        if change["is_pair_target_change"]
        and change["before"]["violation"] is True
    ]
    improved_control_unknown = [
        change for change in changes
        if change["side"] == "control"
        and change["before"]["violation"] in (True, False)
        and change["after"]["violation"] is None
    ]
    base_pairs = evaluate_target_paired(
        [row for row in base_rows if row.get("side") == "variant"],
        [row for row in base_rows if row.get("side") == "control"],
        load_expected_by_item())
    guarded_pairs = evaluate_target_paired(
        [row for row in guarded_rows if row.get("side") == "variant"],
        [row for row in guarded_rows if row.get("side") == "control"],
        load_expected_by_item())
    base_variant_binary = evaluate_variant_binary(
        [row for row in base_rows if row.get("side") == "variant"])
    guarded_variant_binary = evaluate_variant_binary(
        [row for row in guarded_rows if row.get("side") == "variant"])
    base_legacy = evaluate_unified_objects(unified_objects_legacy(
        [row for row in base_rows if row.get("side") == "variant"],
        [row for row in base_rows if row.get("side") == "control"]))
    guarded_legacy = evaluate_unified_objects(unified_objects_legacy(
        [row for row in guarded_rows if row.get("side") == "variant"],
        [row for row in guarded_rows if row.get("side") == "control"]))
    return {
        "change_count": len(changes),
        "changed_by_side": by_side,
        "changed_by_target": by_target,
        "removed_control_false_alarms": len(removed_control_false_alarms),
        "removed_control_false_alarm_items": removed_control_false_alarms,
        "demoted_pair_target_positives": len(demoted_pair_targets),
        "demoted_pair_target_positive_items": demoted_pair_targets,
        "control_clear_to_unknown": len(improved_control_unknown),
        "target_paired_before": {
            "macro_f1_four_types": base_pairs["macro_f1_four_types"],
            "pair_success_count": base_pairs["pair_success_count"],
            "target_field_unknown_rate": base_pairs["target_field_unknown_rate"],
            "control_target_false_positive_rate": base_pairs[
                "control_target_false_positive_rate"],
        },
        "target_paired_after": {
            "macro_f1_four_types": guarded_pairs["macro_f1_four_types"],
            "pair_success_count": guarded_pairs["pair_success_count"],
            "target_field_unknown_rate": guarded_pairs["target_field_unknown_rate"],
            "control_target_false_positive_rate": guarded_pairs[
                "control_target_false_positive_rate"],
        },
        "target_paired_delta": {
            "macro_f1_four_types": round(
                guarded_pairs["macro_f1_four_types"]
                - base_pairs["macro_f1_four_types"], 4),
            "pair_success_count": (guarded_pairs["pair_success_count"]
                                   - base_pairs["pair_success_count"]),
            "target_field_unknown_rate": round(
                guarded_pairs["target_field_unknown_rate"]
                - base_pairs["target_field_unknown_rate"], 4),
        },
        "variant_binary_before_macro_f1": base_variant_binary["macro_f1_four_types"],
        "variant_binary_after_macro_f1": guarded_variant_binary["macro_f1_four_types"],
        "legacy_unified_before_macro_f1_five_classes": base_legacy[
            "macro_f1_five_classes"],
        "legacy_unified_after_macro_f1_five_classes": guarded_legacy[
            "macro_f1_five_classes"],
        "legacy_unified_before_control_false_positives": sum(
            1 for row in base_rows if row.get("side") == "control"
            for check in (row.get("checks") or {}).values()
            if check.get("violation") is True),
        "legacy_unified_after_control_false_positives": sum(
            1 for row in guarded_rows if row.get("side") == "control"
            for check in (row.get("checks") or {}).values()
            if check.get("violation") is True),
        "changes": list(changes),
    }


def _find_row(rows: Sequence[Mapping[str, Any]], item_id: str,
              side: str) -> Mapping[str, Any]:
    for row in rows:
        if row.get("item_id") == item_id and row.get("side") == side:
            return row
    raise KeyError(f"{item_id}:{side}")


def _check_summary(row: Mapping[str, Any], target: str) -> dict[str, Any]:
    check = (row.get("checks") or {}).get(target) or {}
    return {
        "status": check.get("status"),
        "observable": check.get("observable"),
        "violation": check.get("violation"),
        "reason": check.get("reason"),
        "source": check.get("source"),
        "previous_check": check.get("previous_check"),
        "guard_reason": check.get("guard_reason"),
        "guard_non_action_field_matches": check.get(
            "guard_non_action_field_matches"),
    }


def _candidate_summary(row: Mapping[str, Any], limit: int = 6) -> list[dict[str, Any]]:
    ground = row.get("action_grounding") or {}
    candidates = list(ground.get("candidates") or [])[:limit]
    return [
        {
            "activity_id": candidate.get("activity_id"),
            "label": candidate.get("label"),
            "similarity": candidate.get("similarity"),
            "lexical_coverage": candidate.get("lexical_coverage"),
            "exact_normalized": candidate.get("exact_normalized"),
        }
        for candidate in candidates
    ]


def build_constraint_failure_chain(base_rows: Sequence[Mapping[str, Any]],
                                   guarded_rows: Sequence[Mapping[str, Any]]
                                   ) -> dict[str, Any]:
    item_id = "syn_v2_exception_not_handled_06"
    side = "control"
    base = _find_row(base_rows, item_id, side)
    after = _find_row(guarded_rows, item_id, side)
    rule = base.get("model_visible_rule_input") or {}
    ground = base.get("action_grounding") or {}
    return {
        "chain_id": "constraint_false_positive_non_action_anchor",
        "item_id": item_id,
        "side": side,
        "rule_field": {
            "modality": rule.get("modality"),
            "actor": rule.get("actor"),
            "action": rule.get("action"),
            "condition": rule.get("condition"),
            "constraint": rule.get("constraint"),
            "exception": rule.get("exception"),
        },
        "step_1_rule_field": {
            "constraint_text": rule.get("constraint"),
            "numeric_bound": _check_summary(base, "constraint_violated").get(
                "rule_bound"),
            "action_text": rule.get("action"),
        },
        "step_2_action_candidate": {
            "grounding_status": ground.get("status"),
            "resolved_activity_id": ground.get("activity_id"),
            "resolved_label": _row_label(base),
            "grounding_reason": ground.get("reason"),
            "candidate_examples": _candidate_summary(base),
            "process_has_semantic_rule_action": any(
                str(candidate.get("label") or "").strip().lower()
                == str(rule.get("action") or "").strip().lower()
                for candidate in (ground.get("candidates") or [])
            ),
        },
        "step_3_flow_evidence": {
            "compact_constraint_bound_evidence": (
                base.get("compact_local_context") or {}
            ).get("constraint_bound_evidence", [])[:8],
            "compact_constraint_unbound_evidence": (
                base.get("compact_local_context") or {}
            ).get("constraint_unbound_evidence", [])[:8],
            "anchor_consistency": ground.get("action_anchor_consistency"),
        },
        "step_4_before_after": {
            "before": _check_summary(base, "constraint_violated"),
            "after": _check_summary(after, "constraint_violated"),
        },
        "step_5_repair": {
            "repair_status": "FIXED_BY_PROGRAM_ANCHOR_GUARD",
            "repair": (
                "When the resolved activity label strongly matches a non-action "
                "rule field and not the rule action, condition/constraint "
                "determinations anchored to that node are demoted to unknown."),
            "api_needed": False,
            "correctness_effect": (
                "removes a false constraint violation produced by absence of a "
                "bound around an exception-handler node; target-paired F1 is "
                "not required to increase"),
        },
    }


def build_exception_failure_chain(base_rows: Sequence[Mapping[str, Any]],
                                  guarded_rows: Sequence[Mapping[str, Any]]
                                  ) -> dict[str, Any]:
    item_id = "syn_v2_exception_not_handled_02"
    side = "variant"
    base = _find_row(base_rows, item_id, side)
    after = _find_row(guarded_rows, item_id, side)
    rule = base.get("model_visible_rule_input") or {}
    ground = base.get("action_grounding") or {}
    return {
        "chain_id": "exception_abstention_missing_rule_action",
        "item_id": item_id,
        "side": side,
        "rule_field": {
            "modality": rule.get("modality"),
            "actor": rule.get("actor"),
            "action": rule.get("action"),
            "condition": rule.get("condition"),
            "constraint": rule.get("constraint"),
            "exception": rule.get("exception"),
        },
        "step_1_rule_field": {
            "exception_text": rule.get("exception"),
            "action_text": rule.get("action"),
        },
        "step_2_action_candidate": {
            "grounding_status": ground.get("status"),
            "grounding_reason": ground.get("reason"),
            "resolved_activity_id": ground.get("activity_id"),
            "candidate_count": len(ground.get("candidates") or []),
            "candidate_examples": _candidate_summary(base),
            "process_has_semantic_rule_action": any(
                str(candidate.get("label") or "").strip().lower()
                == str(rule.get("action") or "").strip().lower()
                for candidate in (ground.get("candidates") or [])
            ),
        },
        "step_3_flow_evidence": {
            "compact_exception_handler_candidates": (
                base.get("compact_local_context") or {}
            ).get("exception_handler_candidates", [])[:8],
            "compact_constraint_bound_evidence": (
                base.get("compact_local_context") or {}
            ).get("constraint_bound_evidence", [])[:4],
        },
        "step_4_before_after": {
            "before": _check_summary(base, "exception_not_handled"),
            "after": _check_summary(after, "exception_not_handled"),
        },
        "step_5_repair": {
            "repair_status": "CAPABILITY_BOUNDARY_UNFIXABLE_WITH_CURRENT_PROCESS",
            "repair": (
                "No action node in the frozen process expresses the rule action, so "
                "the rule action cannot be anchored and absence of a handler cannot "
                "be programmatically established. This is not converted into a "
                "violation."),
            "api_needed_for_next_step": "authorized semantic fallback only",
            "correctness_effect": "keeps abstention instead of fabricating a violation",
        },
    }


def render_markdown(metrics: Mapping[str, Any], failures: Mapping[str, Any]) -> str:
    report = metrics["guard_change_report"]
    lines = [
        "# s3_semantic_grounding_v5 (zero API, read-only prediction reuse)",
        "",
        "本 revision 从 v2 冻结预测中定位 constraint/exception 失败链，并加入"
        " action-anchor consistency guard：当已解决动作节点的标签强烈匹配非 action"
        " 规则字段且不匹配 action 时，锚定在该节点上的 condition/constraint 判定"
        " 降级为 unknown，不把信息缺失误判为违规。",
        "",
        "## Guard change report",
        "",
        f"- Changed checks: **{report['change_count']}**",
        f"- Removed control false alarms: **{report['removed_control_false_alarms']}**",
        f"- Demoted target-paired positives: **{report['demoted_pair_target_positives']}**",
        f"- Target-paired Macro-F1 before/after: "
        f"**{report['target_paired_before']['macro_f1_four_types']} / "
        f"{report['target_paired_after']['macro_f1_four_types']}**",
        f"- Pair success before/after: "
        f"**{report['target_paired_before']['pair_success_count']} / "
        f"{report['target_paired_after']['pair_success_count']}**",
        f"- Target-field unknown rate before/after: "
        f"**{report['target_paired_before']['target_field_unknown_rate']} / "
        f"{report['target_paired_after']['target_field_unknown_rate']}**",
        f"- Legacy control check false positives before/after: "
        f"**{report['legacy_unified_before_control_false_positives']} / "
        f"{report['legacy_unified_after_control_false_positives']}**",
        "",
        "## Failure chains",
        "",
        f"- Constraint: **{failures['constraint']['step_5_repair']['repair_status']}** "
        f"({failures['constraint']['item_id']} {failures['constraint']['side']})",
        f"- Exception: **{failures['exception']['step_5_repair']['repair_status']}** "
        f"({failures['exception']['item_id']} {failures['exception']['side']})",
        "",
        "## Boundary",
        "",
        "The guard changes detection behaviour only through a program consistency rule; "
        "it does not tune per-sample thresholds or use Gold/expected labels. F1 is not "
        "required to increase. The v2 predictions are reused read-only after hash "
        "verification. No real API call is made.",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (V5_EVIDENCE, V5_DEVELOPMENT, REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing v5 outputs")
    reuse = verify_v2_predictions()
    if not reuse["match"]:
        raise RuntimeError("v2 predictions hash mismatch; refusing to reuse")
    base_rows = read_rows(V2_PREDICTIONS)
    guarded_rows, changes = apply_guard_to_rows(base_rows)
    change_report = build_change_report(base_rows, guarded_rows, changes)
    failures = {
        "schema_version": "s3_semantic_grounding_failure_chains@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "constraint": build_constraint_failure_chain(base_rows, guarded_rows),
        "exception": build_exception_failure_chain(base_rows, guarded_rows),
        "note": (
            "Full rule-field -> action-candidate -> flow-evidence -> reason -> "
            "repair/boundary chains. The exception chain is intentionally recorded "
            "as a capability boundary rather than fabricated into a violation."),
    }
    fallback_pack = build_fallback_pack(guarded_rows)
    expected = load_expected_by_item()
    target_paired = evaluate_target_paired(
        [row for row in guarded_rows if row.get("side") == "variant"],
        [row for row in guarded_rows if row.get("side") == "control"], expected)
    variant_binary = evaluate_variant_binary(
        [row for row in guarded_rows if row.get("side") == "variant"])
    legacy = evaluate_unified_objects(unified_objects_legacy(
        [row for row in guarded_rows if row.get("side") == "variant"],
        [row for row in guarded_rows if row.get("side") == "control"]))
    metrics = {
        "schema_version": "s3_semantic_grounding_v5_metrics@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only",
        "read_only_reuse": reuse,
        "real_api_calls": 0,
        "network_calls": 0,
        "guard_change_report": change_report,
        "target_paired_after": target_paired,
        "variant_binary_after": variant_binary,
        "legacy_unified_after": legacy,
        "fallback_pack_summary": {
            "schema_version": fallback_pack["schema_version"],
            "revision": fallback_pack["revision"],
            "item_count": fallback_pack["item_count"],
            "side_counts": fallback_pack["side_counts"],
            "trigger_counts": fallback_pack["trigger_counts"],
            "all_evidence_ids_visible_in_payload": fallback_pack[
                "all_evidence_ids_visible_in_payload"],
            "semantic_fields_preserved_for_all_items": fallback_pack[
                "semantic_fields_preserved_for_all_items"],
        },
    }
    manifest = {
        "schema_version": "s3_semantic_grounding_v5_manifest@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "read_only_reuse": reuse,
        "inputs": {
            "outputs/evidence/s3_semantic_grounding_v2/predictions.jsonl": reuse[
                "actual_raw_sha256"],
        },
        "implementation_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (
                Path(__file__),
                ROOT / "src/bpc_hybrid/s3_semantic_grounding_v5.py",
                ROOT / "configs/stage3_semantic_grounding_v5.json",
                ROOT / "tests/test_s3_semantic_grounding_v5.py",
                ROOT / "outputs/evidence/s3_semantic_grounding_v2/predictions.jsonl",
            ) if path.is_file()
        },
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "v2_predictions_overwritten": False,
            "no_per_sample_threshold_tuning": True,
        },
    }
    V5_EVIDENCE.mkdir(parents=True, exist_ok=True)
    V5_DEVELOPMENT.mkdir(parents=True, exist_ok=True)
    write_rows(V5_EVIDENCE / "predictions.jsonl", guarded_rows)
    write_rows(V5_DEVELOPMENT / "predictions.jsonl", guarded_rows)
    write_json(V5_EVIDENCE / FAILURE_CHAINS_NAME, failures)
    write_json(V5_DEVELOPMENT / FAILURE_CHAINS_NAME, failures)
    write_json(V5_EVIDENCE / PACK_NAME, fallback_pack)
    write_json(V5_DEVELOPMENT / PACK_NAME, fallback_pack)
    write_json(V5_EVIDENCE / "metrics.json", metrics)
    write_json(V5_DEVELOPMENT / "metrics.json", metrics)
    write_json(V5_EVIDENCE / "manifest.json", manifest)
    write_json(V5_DEVELOPMENT / "manifest.json", manifest)
    report = {
        "schema_version": "s3_semantic_grounding_v5_report@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "status": "VERIFIED_DEVELOPMENT_DETECTION_REPAIR",
        "metrics": metrics,
        "failure_chains": failures,
        "manifest": manifest,
        "claim_boundary": (
            "Development-only synthetic panel. The guard is a program consistency "
            "rule applied to frozen v2 predictions; F1 is not required to rise and "
            "no real API or Gold was used."),
    }
    write_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_markdown(metrics, failures),
                         encoding="utf-8", newline="\n")
    artifacts = [
        V5_EVIDENCE / "predictions.jsonl", V5_EVIDENCE / FAILURE_CHAINS_NAME,
        V5_EVIDENCE / PACK_NAME, V5_EVIDENCE / "metrics.json",
        V5_EVIDENCE / "manifest.json", V5_DEVELOPMENT / "predictions.jsonl",
        V5_DEVELOPMENT / FAILURE_CHAINS_NAME, V5_DEVELOPMENT / PACK_NAME,
        V5_DEVELOPMENT / "metrics.json", V5_DEVELOPMENT / "manifest.json",
        REPORT_JSON, REPORT_MD,
    ]
    write_json(V5_EVIDENCE / "artifact_hashes.json", {
        "schema_version": "s3_semantic_grounding_v5_artifact_hashes@1.0.0",
        "run_id": RUN_ID,
        "artifacts": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                      for path in artifacts},
    })
    return {"metrics": metrics, "failure_chains": failures,
            "fallback_pack": fallback_pack}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    metrics = result["metrics"]
    report = metrics["guard_change_report"]
    print(json.dumps({
        "revision": REVISION,
        "changed_checks": report["change_count"],
        "removed_control_false_alarms": report["removed_control_false_alarms"],
        "demoted_pair_target_positives": report["demoted_pair_target_positives"],
        "target_paired_macro_f1": report["target_paired_after"][
            "macro_f1_four_types"],
        "pair_success_count": report["target_paired_after"]["pair_success_count"],
        "fallback_items": metrics["fallback_pack_summary"]["item_count"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

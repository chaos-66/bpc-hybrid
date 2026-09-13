# -*- coding: utf-8 -*-
"""Runner for revision s3_semantic_grounding_v3 (zero real API).

The deterministic predictions of v2 are reused only after their frozen
artifact hash matches the historical v2 record.  This runner repairs the
evaluation protocol and the fallback candidate pack around those identical
predictions; it never overwrites v1/v2 artifacts.

No real LLM/API call is made by this module.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
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
from bpc_hybrid.s3_semantic_grounding_v2 import (  # noqa: E402
    audit_composite_collisions,
    evaluate_unified_objects,
    evaluate_variant_binary,
    unified_objects_legacy,
)
from bpc_hybrid.s3_semantic_grounding_v3 import (  # noqa: E402
    EVALUATOR_VERSION,
    REVISION,
    build_fallback_pack,
    evaluate_target_paired,
    fixed_control_scope,
)

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
V2_DIR = ROOT / "outputs/evidence/s3_semantic_grounding_v2"
V2_PREDICTIONS = V2_DIR / "predictions.jsonl"
V2_ARTIFACT_HASHES = V2_DIR / "artifact_hashes.json"
V2_MANIFEST = V2_DIR / "manifest.json"
V2_REPORT = ROOT / "outputs/reports/s3_semantic_grounding_v2.json"
C36_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
C36_PREDICTIONS = ROOT / "outputs/evidence/s3_formula_repair_v2/extended_four/reference/winter/predictions.jsonl"
V3_CONFIG = ROOT / "configs/stage3_semantic_grounding_v3.json"
V3_TEST = ROOT / "tests/test_s3_semantic_grounding_v3.py"

OUT_DIR = ROOT / "outputs/development/s3_semantic_grounding_v3"
EVIDENCE_DIR = ROOT / "outputs/evidence/s3_semantic_grounding_v3"
REPORT_JSON = ROOT / "outputs/reports/s3_semantic_grounding_v3.json"
REPORT_MD = ROOT / "outputs/reports/s3_semantic_grounding_v3.md"
PACK_NAME = "llm_fallback_candidate_pack_v3.json"
RUN_ID = "s3_semantic_grounding_v3"

_FORBIDDEN_KEYS = frozenset({
    "expected_violation", "mutation_type", "target_field", "mutation_config",
    "target_activity_id", "gold", "Gold",
})
_GENERATED_ID_TOKEN_RE = re.compile(r"\bsyn_[A-Za-z0-9_\-.:]+\b")
_ANON_ID_RE = re.compile(r"\bE\d{4}\b")
_SKIP_PRESERVATION_KEYS = frozenset({
    "id", "activity_id", "candidate_activity_ids", "source_ref", "target_ref",
    "source_id", "target_id", "flow_id", "boundary_event_id", "handler_task_id",
    "annotation_id", "association_id", "data_object_id", "event_id",
    "attached_to", "bound_activity_id", "handler_of", "branch_target_ids",
})


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                            for row in rows), encoding="utf-8", newline="\n")


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def verify_reused_v2_predictions() -> dict[str, Any]:
    hashes = read_json(V2_ARTIFACT_HASHES)
    key = "outputs/evidence/s3_semantic_grounding_v2/predictions.jsonl"
    expected = (hashes.get("artifacts") or {}).get(key)
    actual_raw = sha256_file(V2_PREDICTIONS)
    actual_canonical_lf = hashlib.sha256(
        V2_PREDICTIONS.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    manifest = read_json(V2_MANIFEST)
    return {
        "source_path": key,
        "expected_sha256": expected,
        "actual_raw_sha256": actual_raw,
        "actual_canonical_lf_sha256": actual_canonical_lf,
        "match": bool(expected) and expected in {actual_raw, actual_canonical_lf},
        "hash_mode": "raw_or_canonical_lf",
        "v2_real_api_calls": ((manifest.get("llm_fallback") or {}).get("real_api_calls")),
        "v2_network_calls": ((manifest.get("safety") or {}).get("network_calls")),
        "reuse_policy": (
            "byte-identical deterministic predictions; the scorer, panel and sentence "
            "view are not re-run or modified by v3"),
    }


def _normalise_string_tokens(value: str) -> str:
    value = _GENERATED_ID_TOKEN_RE.sub("<ID>", value)
    value = _ANON_ID_RE.sub("<ID>", value)
    return value


def _preservation_mismatches(original: Any, anonymized: Any, path: str = "") -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    if isinstance(original, Mapping) and isinstance(anonymized, Mapping):
        for key in sorted(set(original) | set(anonymized)):
            child_path = f"{path}/{key}"
            if key in _FORBIDDEN_KEYS or key in _SKIP_PRESERVATION_KEYS:
                continue
            mismatches.extend(_preservation_mismatches(original.get(key),
                                                       anonymized.get(key),
                                                       child_path))
    elif isinstance(original, list) and isinstance(anonymized, list):
        if len(original) != len(anonymized):
            mismatches.append({"path": path, "kind": "length_mismatch",
                               "original": len(original), "anonymized": len(anonymized)})
        for index, (left, right) in enumerate(zip(original, anonymized)):
            mismatches.extend(_preservation_mismatches(left, right, f"{path}[{index}]"))
    elif isinstance(original, str) or isinstance(anonymized, str):
        left = "" if original is None else str(original)
        right = "" if anonymized is None else str(anonymized)
        if left != right and _normalise_string_tokens(left) != _normalise_string_tokens(right):
            mismatches.append({"path": path, "kind": "string_changed",
                               "original": left, "anonymized": right})
    elif original != anonymized:
        mismatches.append({"path": path, "kind": "value_changed",
                           "original": original, "anonymized": anonymized})
    return mismatches


def _visible_payload_paths(value: Any, path: str = "") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}/{key}"
            if str(key) in _FORBIDDEN_KEYS:
                found.append((child, "forbidden_metadata_key"))
            found.extend(_visible_payload_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_visible_payload_paths(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        if _GENERATED_ID_TOKEN_RE.search(value):
            found.append((path, "generated_id_token"))
        for target in EXTENDED_TYPES:
            if target in value:
                found.append((path, f"target_label:{target}"))
    return found


def audit_fallback_pack(pack: Mapping[str, Any],
                        source_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    leaks: list[dict[str, Any]] = []
    preservation_mismatches: list[dict[str, Any]] = []
    for item in pack.get("items", []):
        source_index = item.get("source_index")
        source = source_rows[source_index] if isinstance(source_index, int) else {}
        if not isinstance(source_index, int) or source_index < 0 \
                or source_index >= len(source_rows):
            leaks.append({"fallback_item_id": item.get("fallback_item_id"),
                          "kind": "invalid_source_index"})
            continue
        for path, kind in _visible_payload_paths(item.get("llm_visible_payload") or {}):
            leaks.append({"fallback_item_id": item.get("fallback_item_id"),
                          "path": path, "kind": kind})
        original_payload = {
            "rule_record": source.get("model_visible_rule_input") or {},
            "candidate_activities": ((source.get("compact_local_context") or {})
                                     .get("candidate_activities") or []),
            "candidate_activity_ids": [
                activity.get("activity_id")
                for activity in ((source.get("compact_local_context") or {})
                                 .get("candidate_activities") or [])
                if activity.get("activity_id")
            ],
            "local_context": {
                key: ((source.get("compact_local_context") or {}).get(key) or [])
                for key in (
                    "nodes", "sequence_flows", "condition_evidence",
                    "constraint_bound_evidence", "constraint_unbound_evidence",
                    "exception_handler_candidates", "evidence_ids",
                )
            },
        }
        mismatches = _preservation_mismatches(
            original_payload, item.get("llm_visible_payload") or {})
        for mismatch in mismatches:
            mismatch["fallback_item_id"] = item.get("fallback_item_id")
        preservation_mismatches.extend(mismatches)
    return {
        "schema_version": "s3_fallback_pack_integrity_audit@1.0.0",
        "item_count": pack.get("item_count"),
        "forbidden_or_generated_hits": leaks,
        "forbidden_or_generated_hit_count": len(leaks),
        "semantic_preservation_mismatch_count": len(preservation_mismatches),
        "semantic_preservation_mismatches": preservation_mismatches,
        "semantic_fields_preserved_for_all_items": pack.get(
            "semantic_fields_preserved_for_all_items"),
        "anonymisation_ok": not leaks and not preservation_mismatches,
    }


def c36_comparison_gap() -> dict[str, Any]:
    report = read_json(C36_REPORT) if C36_REPORT.is_file() else {}
    rows = read_rows(C36_PREDICTIONS) if C36_PREDICTIONS.is_file() else []
    first_keys = sorted(rows[0].keys()) if rows else []
    has_same_protocol_fields = bool(
        rows and {"checks", "side", "canonical_rule_input_hash",
                  "canonical_process_input_hash"} <= set(rows[0])
    )
    return {
        "schema_version": "s3_c36_target_paired_comparison_gap@1.0.0",
        "status": "GAP_DOCUMENTED_NOT_COMPUTED",
        "c36_report_available": bool(report),
        "c36_prediction_rows": len(rows),
        "c36_prediction_row_keys": first_keys,
        "same_target_paired_protocol_available": has_same_protocol_fields,
        "missing_required_fields": [
            "per-side checks[target_field].observable and .violation for both variant and control",
            "frozen composite input identity hashes",
            "single common fixed-control denominator under the corrected evaluator",
        ],
        "reason": (
            "C36 predictions contain variant-side unified outputs and some control "
            "scores, but not the v3 per-side target-field determination/coverage "
            "structure. Recomputing or splicing C36 old metrics into the v3 table "
            "would be an incomparable combination; the gap is recorded instead."
        ),
        "prohibited_use": "do not cite a C36-versus-v3 target-paired delta from this file",
    }


def load_expected_by_item() -> dict[str, str]:
    panel = read_json(PANEL)
    return {item["variant_id"]: item["expected_violation"]
            for item in panel["variants"]}


def render_markdown(metrics: Mapping[str, Any]) -> str:
    target = metrics["target_paired"]
    pack = metrics["fallback_pack_summary"]
    audit = metrics["anonymisation_audit"]
    gap = metrics["c36_comparison_gap"]
    lines = [
        "# s3_semantic_grounding_v3 (development-only, zero API)",
        "",
        "本 revision 重用 v2 的逐项确定性预测（hash 校验后 byte-identical），只修复评价口径、",
        "输入匿名化和 fallback 候选包；不覆盖 v1/v2 证据，不调用真实 API。",
        "",
        "## 目标字段配对评价（primary）",
        "",
        "| 类型 | variant TP / observed-wrong / unknown | control TN / FP / unknown | P | R | F1 | pair success |",
        "|---|---|---|---|---|---|---|",
    ]
    for target_type in EXTENDED_TYPES:
        row = target["per_type"][target_type]
        lines.append(
            f"| {target_type} | "
            f"{row['variant']['TP']} / {row['variant']['FN_observed_negative']} / "
            f"{row['variant']['unknown']} | "
            f"{row['control']['TN']} / {row['control']['FP']} / "
            f"{row['control']['unknown']} | "
            f"{row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} | "
            f"{row['pair_success']}/{row['pairs']} |"
        )
    side = target["aggregate_side_outcomes_mutually_exclusive"]
    lines += [
        "",
        f"- Target-paired Macro-F1: **{target['macro_f1_four_types']:.4f}**",
        f"- Pair success: **{target['pair_success_count']}/{target['pair_success_denominator']} = "
        f"{target['pair_success_rate']:.4f}**",
        f"- Variant outcomes (mutually exclusive): positive **{side['variant']['positive']}**, "
        f"observed negative/wrong **{side['variant']['negative_observed_wrong']}**, "
        f"unknown **{side['variant']['unknown']}**; coverage "
        f"**{side['variant']['coverage']}**.",
        f"- Control outcomes (mutually exclusive): negative **{side['control']['negative']}**, "
        f"false alarm **{side['control']['positive_false_alarm']}**, unknown "
        f"**{side['control']['unknown']}**; coverage **{side['control']['coverage']}**.",
        f"- Control target FP rate over all pairs: **{target['control_target_false_positive_rate']:.4f}**; "
        f"over decided controls: **{target['control_target_false_positive_rate_over_decided_controls']:.4f}**.",
        f"- Unknown rate over all target-field side checks: **{target['target_field_unknown_rate']:.4f}**.",
        "",
        "Unknown 处理：variant unknown 计入 FN 但单独列出；control unknown 单独计数，不进入 decided TNR 分母；",
        "不把 unknown 当作合规或违规；pair success 以全体 pair 为分母，只有 variant positive 且 control negative 才算成功。",
        "",
        "## 匿名化修复",
        "",
        f"- Fallback items: **{pack['item_count']}**",
        f"- Semantic field preservation mismatches: **{audit['semantic_preservation_mismatch_count']}**",
        f"- Forbidden/generated leaks in model-visible payload: **{audit['forbidden_or_generated_hit_count']}**",
        f"- Anonymisation audit passed: **{audit['anonymisation_ok']}**",
        "",
        "## Control 自洽诊断（不是独立验证）",
        "",
        "- Control 状态由同一批待评价 checker 产生，只能称为模型诊断；没有独立全局合规标签，"
        "不报告 clean-unified 全局性能，也不按方法自身输出改变测试子集。所有 40 个 control 均保留在固定评价分母中。",
        "",
        "## C36 可比性缺口",
        "",
        f"- Status: **{gap['status']}**",
        f"- Reason: {gap['reason']}",
        "",
        "## Boundary",
        "",
        "Development-only synthetic controlled panel. Not formal Oracle and not human Gold. "
        "Predictions are byte-identical to the frozen v2 deterministic artifacts; v3 changes "
        "only the input pack and evaluation accounting. No real LLM result is claimed.",
        "",
    ]
    return "\n".join(lines)


def run(*, overwrite: bool = False) -> dict[str, Any]:
    if any(path.exists() for path in (OUT_DIR, EVIDENCE_DIR, REPORT_JSON, REPORT_MD)):
        if not overwrite:
            raise RuntimeError("refusing to overwrite existing s3_semantic_grounding_v3 outputs")

    reuse = verify_reused_v2_predictions()
    if not reuse["match"]:
        raise RuntimeError("v2 prediction artifact hash mismatch; refusing to reuse")

    rows = read_rows(V2_PREDICTIONS)
    expected_by_item = load_expected_by_item()
    variants = [row for row in rows if row.get("side") == "variant"]
    controls = [row for row in rows if row.get("side") == "control"]
    if len(rows) != 80 or len(variants) != 40 or len(controls) != 40:
        raise RuntimeError("unexpected v2 prediction shape; expected 80 rows / 40 + 40")

    target_paired = evaluate_target_paired(variants, controls, expected_by_item)
    variant_binary = evaluate_variant_binary(variants)
    legacy_unified = evaluate_unified_objects(
        unified_objects_legacy(variants, controls))
    control_diagnostic = fixed_control_scope(controls)
    collision_audit = audit_composite_collisions(rows)
    fallback_pack = build_fallback_pack(rows)
    pack_audit = audit_fallback_pack(fallback_pack, rows)
    comparison_gap = c36_comparison_gap()

    pack_summary = {
        "schema_version": fallback_pack["schema_version"],
        "revision": fallback_pack["revision"],
        "item_count": fallback_pack["item_count"],
        "side_counts": fallback_pack["side_counts"],
        "trigger_counts": fallback_pack["trigger_counts"],
        "semantic_fields_preserved_for_all_items": fallback_pack[
            "semantic_fields_preserved_for_all_items"],
        "anonymisation_ok": pack_audit["anonymisation_ok"],
        "contains_expected_labels": fallback_pack["contains_expected_labels"],
    }
    metrics = {
        "schema_version": "s3_semantic_grounding_v3_metrics@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only_synthetic_controlled_panel",
        "evaluator_version": EVALUATOR_VERSION,
        "deterministic_predictions_reused": reuse,
        "evaluation_protocol": {
            "primary": "target_paired_causal_fixed_panel",
            "secondary": ["legacy_fixed_control_diagnostic"],
            "control_scope": (
                "all 40 frozen target-field controls for every method; the same "
                "denominator is used for each method"),
            "control_self_consistency": (
                "diagnostic only; not an independent global-compliance label and "
                "never used to select a different evaluation subset"),
            "clean_unified_status": "NOT_REPORTED_NO_INDEPENDENT_GLOBAL_LABELS",
            "unknown_policy": (
                "variant unknown is FN but reported separately; control unknown is "
                "reported outside the decided TNR denominator; unknown is never a "
                "compliant prediction; pair success uses all pairs as denominator"),
        },
        "target_paired": target_paired,
        "variant_binary": variant_binary,
        "legacy_fixed_control_diagnostic": {
            "metrics": legacy_unified,
            "control_objects": len(controls),
            "not_a_pure_none_gold_benchmark": True,
            "all_frozen_controls_kept_fixed": True,
            "source_control_scope": "all 40 target-field controls",
            "reason": (
                "controls only guarantee their mutated target field, and the 20 "
                "fallback subset is not representative of all controls; retained "
                "only as continuity diagnostic, not as primary comparison"),
        },
        "control_model_diagnostic": {
            "diagnostic_status_counts": control_diagnostic["diagnostic_status_counts"],
            "diagnostic_status_by_item": control_diagnostic["diagnostic_status_by_item"],
            "diagnostic_only": True,
            "independent_global_compliance_labels_available": False,
            "used_to_select_evaluation_subset": False,
        },
        "fallback_pack_summary": pack_summary,
        "anonymisation_audit": pack_audit,
        "collision_audit": collision_audit,
        "c36_comparison_gap": comparison_gap,
    }
    manifest = {
        "schema_version": "s3_semantic_grounding_v3_manifest@1.0.0",
        "run_id": RUN_ID,
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "evaluator_version": EVALUATOR_VERSION,
        "deterministic_predictions_reused": reuse,
        "sample_count": {"variants": len(variants), "controls": len(controls),
                         "objects": len(rows)},
        "inputs": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (PANEL, V2_PREDICTIONS, V2_ARTIFACT_HASHES, V2_MANIFEST,
                         V2_REPORT, C36_REPORT, C36_PREDICTIONS)
            if path.is_file()
        },
        "implementation_hashes": {
            path.relative_to(ROOT).as_posix(): sha256_file(path)
            for path in (Path(__file__), ROOT / "src/bpc_hybrid/s3_semantic_grounding_v3.py",
                         V3_CONFIG, V3_TEST)
            if path.is_file()
        },
        "evaluation_protocol": metrics["evaluation_protocol"],
        "fallback_pack": {
            "schema_version": fallback_pack["schema_version"],
            "item_count": fallback_pack["item_count"],
            "semantic_fields_preserved_for_all_items": fallback_pack[
                "semantic_fields_preserved_for_all_items"],
            "anonymisation_ok": pack_audit["anonymisation_ok"],
            "real_api_calls": 0,
            "network_calls": 0,
        },
        "safety": {
            "human_gold_read": False,
            "human_gold_modified": False,
            "frozen_panel_modified": False,
            "c36_modified": False,
            "v2_outputs_overwritten": False,
            "v1_outputs_overwritten": False,
            "real_api_calls": 0,
            "network_calls": 0,
            "development_only_not_formal_oracle": True,
        },
    }
    report = {
        "schema_version": "s3_semantic_grounding_v3_report@1.0.0",
        "revision": REVISION,
        "scope": "development_only",
        "generated_utc": manifest["generated_utc"],
        "status": "VERIFIED_DEVELOPMENT_PROTOCOL_REPAIR",
        "metrics": metrics,
        "manifest": manifest,
        "claim_boundary": (
            "Development-only synthetic controlled panel. Predictions are "
            "byte-identical to frozen v2 deterministic artifacts. This revision "
            "corrects anonymisation and evaluation accounting; it is not formal "
            "Oracle, not human Gold, and contains no real LLM result."),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    # Copy the reused deterministic predictions byte-for-byte into the new
    # revision; the hash and provenance are checked above.
    normalized_prediction_bytes = V2_PREDICTIONS.read_bytes().replace(b"\r\n", b"\n")
    for destination in (OUT_DIR / "predictions.jsonl",
                        EVIDENCE_DIR / "predictions.jsonl"):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(normalized_prediction_bytes)
    write_json(OUT_DIR / "control_diagnostic.json", control_diagnostic)
    write_json(EVIDENCE_DIR / "control_diagnostic.json", control_diagnostic)
    write_json(OUT_DIR / "input_integrity_checks.json", {
        "schema_version": "s3_semantic_grounding_v3_input_integrity@1.0.0",
        "deterministic_prediction_reuse": reuse,
        "anonymisation_audit": pack_audit,
        "collision_audit": collision_audit,
    })
    write_json(EVIDENCE_DIR / "input_integrity_checks.json", {
        "schema_version": "s3_semantic_grounding_v3_input_integrity@1.0.0",
        "deterministic_prediction_reuse": reuse,
        "anonymisation_audit": pack_audit,
        "collision_audit": collision_audit,
    })
    write_json(OUT_DIR / PACK_NAME, fallback_pack)
    write_json(EVIDENCE_DIR / PACK_NAME, fallback_pack)
    write_json(OUT_DIR / "metrics.json", metrics)
    write_json(EVIDENCE_DIR / "metrics.json", metrics)
    write_json(OUT_DIR / "manifest.json", manifest)
    write_json(EVIDENCE_DIR / "manifest.json", manifest)
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    write_json(REPORT_JSON, report)
    REPORT_MD.write_text(render_markdown(metrics), encoding="utf-8", newline="\n")

    artifact_paths = [
        OUT_DIR / "predictions.jsonl", OUT_DIR / "control_diagnostic.json",
        OUT_DIR / "input_integrity_checks.json", OUT_DIR / PACK_NAME,
        OUT_DIR / "metrics.json", OUT_DIR / "manifest.json",
        EVIDENCE_DIR / "predictions.jsonl", EVIDENCE_DIR / "control_diagnostic.json",
        EVIDENCE_DIR / "input_integrity_checks.json", EVIDENCE_DIR / PACK_NAME,
        EVIDENCE_DIR / "metrics.json", EVIDENCE_DIR / "manifest.json",
        REPORT_JSON, REPORT_MD,
    ]
    write_json(EVIDENCE_DIR / "artifact_hashes.json", {
        "schema_version": "s3_semantic_grounding_v3_artifact_hashes@1.0.0",
        "run_id": RUN_ID,
        "artifacts": {path.relative_to(ROOT).as_posix(): sha256_file(path)
                      for path in artifact_paths},
    })
    return {"metrics": metrics, "manifest": manifest,
            "fallback_pack": fallback_pack, "report_json": str(REPORT_JSON)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    result = run(overwrite=args.overwrite)
    metrics = result["metrics"]
    print(json.dumps({
        "revision": REVISION,
        "target_paired_macro_f1": metrics["target_paired"]["macro_f1_four_types"],
        "pair_success_count": metrics["target_paired"]["pair_success_count"],
        "pair_success_rate": metrics["target_paired"]["pair_success_rate"],
        "variant_unknown": metrics["target_paired"][
            "aggregate_side_outcomes_mutually_exclusive"]["variant"]["unknown"],
        "control_unknown": metrics["target_paired"][
            "aggregate_side_outcomes_mutually_exclusive"]["control"]["unknown"],
        "control_fp": metrics["target_paired"][
            "aggregate_side_outcomes_mutually_exclusive"]["control"]["positive_false_alarm"],
        "fallback_items": metrics["fallback_pack_summary"]["item_count"],
        "anonymisation_ok": metrics["fallback_pack_summary"]["anonymisation_ok"],
        "real_api_calls": 0,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

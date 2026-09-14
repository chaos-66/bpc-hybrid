# -*- coding: utf-8 -*-
"""C36/Winter target-paired compatibility audit and comparison (zero API).

The frozen C36/Winter prediction file stores one variant row per synthetic
panel item.  Each row contains:

* explicit per-type variant checks in ``scores_detail``
  (``observable`` + ``violation`` when observable);
* per-type control scores in ``control_scores``
  (``observable`` + ``score`` + ``reason`` + ``exact_contradiction``).

The control side does not persist a final boolean ``violation``.  The frozen
project function ``stage3_extended_violations.control_prediction_from_scores``
defines the exact per-type decision rule from those saved fields, so the
target-paired comparison can be reconstructed without using a unified
single-label prediction or any Gold/target label.  The reconstruction and its
dependency are recorded explicitly in the audit manifest.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage3_extended_violations import (
    EXTENDED_TYPES,
    NONE_LABEL,
    control_prediction_from_scores,
)
from bpc_hybrid.s3_semantic_grounding_v3 import evaluate_target_paired

REVISION = "s3_c36_target_paired_v1"
EVALUATOR_VERSION = "s3_c36_target_paired_evaluator@1.0.0"
C36_CONTROL_RECONSTRUCTION_RULE = (
    "stage3_extended_violations.control_prediction_from_scores("
    "control_scores, gamma_ext)"
)
TYPES = list(EXTENDED_TYPES)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def sha256_file_canonical_lf(path: Path) -> str:
    return sha256_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _unknown(reason: str, **extra: Any) -> dict[str, Any]:
    return {
        "status": "unknown",
        "observable": False,
        "violation": None,
        "score": None,
        "reason": reason,
        **extra,
    }


def variant_check_from_scores_detail(
    scores_detail: Mapping[str, Any], target: str
) -> dict[str, Any]:
    """Read the explicit variant-side check.

    An observable entry without a boolean ``violation`` is treated as a field
    gap, never as a negative or positive result.
    """
    entry = scores_detail.get(target)
    if not isinstance(entry, Mapping):
        return _unknown("c36_variant_check_missing", field_gap=True)
    if entry.get("observable") is not True:
        return _unknown(
            str(entry.get("reason") or "c36_variant_unobservable"),
            field_gap=False,
        )
    violation = entry.get("violation")
    if not isinstance(violation, bool):
        return _unknown(
            "c36_variant_observable_but_violation_missing",
            field_gap=True,
        )
    return {
        "status": "violated" if violation else "negative",
        "observable": True,
        "violation": violation,
        "score": entry.get("max_sim", entry.get("score")),
        "reason": entry.get("reason"),
        "source": "c36_variant_scores_detail_explicit",
        "field_gap": False,
    }


def control_check_from_scores(
    control_scores: Mapping[str, Any], target: str, gamma_ext: float
) -> dict[str, Any]:
    """Reconstruct the control-side check with the frozen project rule."""
    entry = control_scores.get(target)
    if not isinstance(entry, Mapping):
        return _unknown("c36_control_check_missing",
                        reconstruction_rule=C36_CONTROL_RECONSTRUCTION_RULE,
                        field_gap=True)
    decision = control_prediction_from_scores(control_scores, gamma_ext)
    value = decision["per_type"].get(target)
    if entry.get("observable") is not True:
        return _unknown(
            str(entry.get("reason") or "c36_control_unobservable"),
            reconstruction_rule=C36_CONTROL_RECONSTRUCTION_RULE,
            field_gap=False,
        )
    if not isinstance(value, bool):
        return _unknown(
            "c36_control_observable_but_frozen_rule_missing_boolean",
            reconstruction_rule=C36_CONTROL_RECONSTRUCTION_RULE,
            field_gap=True,
        )
    return {
        "status": "violated" if value else "negative",
        "observable": True,
        "violation": value,
        "score": entry.get("score"),
        "reason": entry.get("reason"),
        "exact_contradiction": entry.get("exact_contradiction"),
        "source": "c36_control_score_reconstructed_by_frozen_rule",
        "reconstruction_rule": C36_CONTROL_RECONSTRUCTION_RULE,
        "field_gap": False,
    }


def derive_target_paired_rows(
    c36_rows: Sequence[Mapping[str, Any]], *, gamma_ext_default: float = 0.5
) -> list[dict[str, Any]]:
    """Expand each C36 row into explicit variant and control check rows."""
    result: list[dict[str, Any]] = []
    for row in c36_rows:
        gamma_ext = float(row.get("gamma_ext") or gamma_ext_default)
        variant_checks = {
            target: variant_check_from_scores_detail(
                row.get("scores_detail") or {}, target)
            for target in TYPES
        }
        control_checks = {
            target: control_check_from_scores(
                row.get("control_scores") or {}, target, gamma_ext)
            for target in TYPES
        }
        result.append({
            "item_id": row.get("item_id"),
            "side": "variant",
            "expected_label": row.get("expected_violation"),
            "checks": variant_checks,
            "gamma_ext": gamma_ext,
        })
        result.append({
            "item_id": row.get("item_id"),
            "side": "control",
            "expected_label": NONE_LABEL,
            "checks": control_checks,
            "gamma_ext": gamma_ext,
        })
    return result


def _manifest_input_rows(manifest: Mapping[str, Any],
                         needles: Sequence[str]) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for key, value in (manifest.get("inputs") or {}).items():
        normalized = str(key).replace("\\", "/")
        if any(needle in normalized for needle in needles):
            rows[normalized] = value
    return rows


def audit_c36_winter(
    c36_rows: Sequence[Mapping[str, Any]],
    panel: Mapping[str, Any],
    *,
    c36_manifest: Mapping[str, Any] | None = None,
    current_rows: Sequence[Mapping[str, Any]] | None = None,
    c36_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Item-, label-, hash- and field-level compatibility audit."""
    panel_by_id = {item["variant_id"]: item for item in panel.get("variants", [])}
    c36_by_id = {row.get("item_id"): row for row in c36_rows}
    current_by_side: dict[tuple[str, str], Mapping[str, Any]] = {}
    if current_rows:
        current_by_side = {
            (str(row.get("item_id")), str(row.get("side"))): row
            for row in current_rows
        }

    sample_sets = {
        "c36_rows": len(c36_rows),
        "panel_variant_rows": len(panel_by_id),
        "c36_item_ids_equal_panel": sorted(c36_by_id) == sorted(panel_by_id),
        "missing_in_c36": sorted(set(panel_by_id) - set(c36_by_id)),
        "extra_in_c36": sorted(set(c36_by_id) - set(panel_by_id)),
    }

    label_issues: list[dict[str, Any]] = []
    process_issues: list[dict[str, Any]] = []
    variant_hash_issues: list[dict[str, Any]] = []
    control_hash_issues: list[dict[str, Any]] = []
    current_variant_hash_issues: list[dict[str, Any]] = []
    current_control_hash_issues: list[dict[str, Any]] = []
    gold_visible_values: set[Any] = set()
    for item_id, panel_item in panel_by_id.items():
        row = c36_by_id.get(item_id)
        if row is None:
            continue
        if row.get("expected_violation") != panel_item.get("expected_violation"):
            label_issues.append({
                "item_id": item_id,
                "c36": row.get("expected_violation"),
                "panel": panel_item.get("expected_violation"),
            })
        if row.get("process_id") != panel_item.get("process_id") \
                or row.get("rule_id") != panel_item.get("rule_id"):
            process_issues.append({
                "item_id": item_id,
                "c36": [row.get("process_id"), row.get("rule_id")],
                "panel": [panel_item.get("process_id"), panel_item.get("rule_id")],
            })
        source_hashes = row.get("source_hashes") or {}
        if source_hashes.get("variant_bpmn_sha256") \
                != panel_item.get("variant_bpmn_sha256"):
            variant_hash_issues.append({
                "item_id": item_id,
                "c36": source_hashes.get("variant_bpmn_sha256"),
                "panel": panel_item.get("variant_bpmn_sha256"),
            })
        if source_hashes.get("control_bpmn_sha256") \
                != panel_item.get("control_bpmn_sha256"):
            control_hash_issues.append({
                "item_id": item_id,
                "c36": source_hashes.get("control_bpmn_sha256"),
                "panel": panel_item.get("control_bpmn_sha256"),
            })
        current_variant = current_by_side.get((item_id, "variant"))
        current_control = current_by_side.get((item_id, "control"))
        if current_variant is not None and current_variant.get("bpmn_sha256") \
                != source_hashes.get("variant_bpmn_sha256"):
            current_variant_hash_issues.append({
                "item_id": item_id,
                "c36": source_hashes.get("variant_bpmn_sha256"),
                "current": current_variant.get("bpmn_sha256"),
            })
        if current_control is not None and current_control.get("bpmn_sha256") \
                != source_hashes.get("control_bpmn_sha256"):
            current_control_hash_issues.append({
                "item_id": item_id,
                "c36": source_hashes.get("control_bpmn_sha256"),
                "current": current_control.get("bpmn_sha256"),
            })
        gold_visible_values.add(row.get("gold_visible"))

    manifest_inputs: list[dict[str, Any]] = []
    if c36_manifest is not None:
        # Manifest paths are relative to the formal_experiment root; the caller
        # passes a resolver through c36_manifest["_root"] if needed.
        root = Path(c36_manifest.get("_root", "."))
        for key, expected in _manifest_input_rows(
                c36_manifest,
                ("stage3_gold_inference_v1.json",
                 "synthetic_controlled_error_extension_v2.json",
                 "stage1_structural_s11_s14.json")).items():
            path = root / key
            entry: dict[str, Any] = {
                "path": key,
                "c36_manifest_sha256": expected,
            }
            if path.is_file():
                entry["current_raw_sha256"] = sha256_file(path)
                entry["current_canonical_lf_sha256"] = sha256_file_canonical_lf(path)
                entry["raw_match"] = entry["current_raw_sha256"] == expected
                entry["canonical_lf_match"] = (
                    entry["current_canonical_lf_sha256"] == expected)
            else:
                entry["exists"] = False
            manifest_inputs.append(entry)

    variant_field_stats: dict[str, dict[str, int]] = {}
    for target in TYPES:
        stats = Counter()
        for row in c36_rows:
            entry = (row.get("scores_detail") or {}).get(target)
            if not isinstance(entry, Mapping):
                stats["missing_entry"] += 1
                continue
            observable = entry.get("observable") is True
            violation = entry.get("violation")
            stats["rows"] += 1
            stats["observable_true" if observable else "observable_false"] += 1
            if isinstance(violation, bool):
                stats["explicit_violation_boolean"] += 1
            if observable and not isinstance(violation, bool):
                stats["observable_true_violation_missing"] += 1
        variant_field_stats[target] = dict(stats)

    control_field_stats: dict[str, dict[str, int]] = {}
    for target in TYPES:
        stats = Counter()
        for row in c36_rows:
            entry = (row.get("control_scores") or {}).get(target)
            if not isinstance(entry, Mapping):
                stats["missing_entry"] += 1
                continue
            observable = entry.get("observable") is True
            stats["rows"] += 1
            stats["observable_true" if observable else "observable_false"] += 1
            if entry.get("score") is not None:
                stats["score_present"] += 1
            if entry.get("reason") is not None:
                stats["reason_present"] += 1
            if entry.get("exact_contradiction") is not None:
                stats["exact_contradiction_present"] += 1
            if isinstance(entry.get("violation"), bool):
                stats["explicit_violation_boolean"] += 1
            if observable and not isinstance(
                    control_prediction_from_scores(
                        row.get("control_scores") or {},
                        float(row.get("gamma_ext") or 0.5)
                    )["per_type"].get(target), bool):
                stats["frozen_rule_boolean_missing"] += 1
        control_field_stats[target] = dict(stats)

    field_gaps: list[dict[str, Any]] = []
    if any(stats.get("observable_true_violation_missing", 0)
           for stats in variant_field_stats.values()):
        field_gaps.append({
            "scope": "variant",
            "field": "scores_detail[*].violation",
            "severity": "blocking",
            "reason": "observable variant check has no boolean violation",
            "affected_samples": 40,
        })
    if any(stats.get("rows", 0) != 40 for stats in variant_field_stats.values()):
        field_gaps.append({
            "scope": "variant",
            "field": "scores_detail",
            "severity": "blocking",
            "reason": "one or more of the four checks is missing for some rows",
        })
    if all(stats.get("observable_true", 0) == 0
           and stats.get("observable_false", 0) == 40
           for stats in control_field_stats.values()):
        field_gaps.append({
            "scope": "control",
            "field": "control_scores[*]",
            "severity": "blocking",
            "reason": "control checks are entirely unobservable",
        })

    return {
        "schema_version": "s3_c36_target_paired_audit@1.0.0",
        "revision": REVISION,
        "scope": "development_only_synthetic_panel",
        "panel": panel.get("panel_id") or panel.get("schema_version"),
        "sample_sets": sample_sets,
        "label_issues": label_issues,
        "process_issues": process_issues,
        "c36_variant_bpmn_hash_issues": variant_hash_issues,
        "c36_control_bpmn_hash_issues": control_hash_issues,
        "current_variant_bpmn_hash_issues": current_variant_hash_issues,
        "current_control_bpmn_hash_issues": current_control_hash_issues,
        "gold_visible_values": sorted(str(value) for value in gold_visible_values),
        "manifest_input_checks": manifest_inputs,
        "variant_field_stats": variant_field_stats,
        "control_field_stats": control_field_stats,
        "control_reconstruction_rule": C36_CONTROL_RECONSTRUCTION_RULE,
        "control_reconstruction_required": True,
        "affected_control_samples": 40,
        "affected_control_checks": 160,
        "field_gaps": field_gaps,
        "can_build_target_paired": not field_gaps
        and sample_sets["c36_item_ids_equal_panel"]
        and not label_issues
        and not process_issues
        and not variant_hash_issues
        and not control_hash_issues,
        "unified_single_label_ignored_for_derivation": True,
        "expected_label_used_only_for_evaluation_grouping": True,
        "c36_report_available": bool(c36_report),
    }


def _comparison_row(metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_paired_macro_f1_four_types": metrics["macro_f1_four_types"],
        "pair_success_count": metrics["pair_success_count"],
        "pair_success_rate": metrics["pair_success_rate"],
        "pair_success_denominator": metrics["pair_success_denominator"],
        "control_target_false_positive_rate_all_pairs": (
            metrics["control_target_false_positive_rate"]),
        "control_target_false_positive_rate_decided_controls": (
            metrics["control_target_false_positive_rate_over_decided_controls"]),
        "target_field_unknown_rate_all_side_checks": (
            metrics["target_field_unknown_rate"]),
        "per_type": {
            target: {
                "variant": metrics["per_type"][target]["variant"],
                "control": metrics["per_type"][target]["control"],
                "precision": metrics["per_type"][target]["precision"],
                "recall": metrics["per_type"][target]["recall"],
                "f1": metrics["per_type"][target]["f1"],
                "pair_success": metrics["per_type"][target]["pair_success"],
                "pair_success_denominator": metrics["per_type"][target]["pairs"],
            }
            for target in TYPES
        },
    }


def compare_target_paired(
    c36_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
    panel: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare C36/Winter and the current method under one protocol."""
    expected_by_item = {
        item["variant_id"]: item["expected_violation"]
        for item in panel.get("variants", [])
    }
    c36_metrics = evaluate_target_paired(
        [row for row in c36_rows if row.get("side") == "variant"],
        [row for row in c36_rows if row.get("side") == "control"],
        expected_by_item,
    )
    current_metrics = evaluate_target_paired(
        [row for row in current_rows if row.get("side") == "variant"],
        [row for row in current_rows if row.get("side") == "control"],
        expected_by_item,
    )
    c36_variant_unknown = sum(
        c36_metrics["per_type"][target]["variant"]["unknown"] for target in TYPES)
    c36_control_unknown = sum(
        c36_metrics["per_type"][target]["control"]["unknown"] for target in TYPES)
    current_variant_unknown = sum(
        current_metrics["per_type"][target]["variant"]["unknown"] for target in TYPES)
    current_control_unknown = sum(
        current_metrics["per_type"][target]["control"]["unknown"] for target in TYPES)
    return {
        "schema_version": "s3_c36_target_paired_comparison@1.0.0",
        "revision": REVISION,
        "scope": "development_only_synthetic_panel",
        "evaluation_protocol": {
            "primary": "target_paired_causal",
            "denominator": "all 40 frozen pairs; variant unknown is FN but reported separately; control unknown is outside the decided TNR denominator and reported separately; pair success requires variant positive and control negative",
            "expected_labels_used_only_for_grouping": True,
        },
        "c36_winter": _comparison_row(c36_metrics),
        "current_v5": _comparison_row(current_metrics),
        "delta_current_minus_c36": {
            "macro_f1_four_types": round(
                current_metrics["macro_f1_four_types"]
                - c36_metrics["macro_f1_four_types"], 4),
            "pair_success_count": (
                current_metrics["pair_success_count"]
                - c36_metrics["pair_success_count"]),
            "target_field_unknown_rate": round(
                current_metrics["target_field_unknown_rate"]
                - c36_metrics["target_field_unknown_rate"], 4),
        },
        "unknown_denominators": {
            "c36_winter": {
                "variant_unknown_count": c36_variant_unknown,
                "control_unknown_count": c36_control_unknown,
                "variant_unknown_rate": c36_metrics["variant_unknown_rate"],
                "control_unknown_rate": c36_metrics["control_unknown_rate"],
                "overall_unknown_denominator": "2 * 40 side checks",
            },
            "current_v5": {
                "variant_unknown_count": current_variant_unknown,
                "control_unknown_count": current_control_unknown,
                "variant_unknown_rate": current_metrics["variant_unknown_rate"],
                "control_unknown_rate": current_metrics["control_unknown_rate"],
                "overall_unknown_denominator": "2 * 40 side checks",
            },
        },
        "c36_metrics_full": c36_metrics,
        "current_metrics_full": current_metrics,
    }


__all__ = [
    "REVISION",
    "EVALUATOR_VERSION",
    "C36_CONTROL_RECONSTRUCTION_RULE",
    "TYPES",
    "read_json",
    "read_jsonl",
    "sha256_file",
    "sha256_file_canonical_lf",
    "variant_check_from_scores_detail",
    "control_check_from_scores",
    "derive_target_paired_rows",
    "audit_c36_winter",
    "compare_target_paired",
]

# -*- coding: utf-8 -*-
"""C36/Winter target-paired compatibility gate v2.

This successor revision keeps the frozen-prediction comparison from v1 but
makes compatibility a real execution gate:

* every blocking condition (sample identity, both-side uniqueness/completeness,
  input and prediction hash identity, field legality, reconstruction fields,
  threshold binding, dependency identity) must pass before any comparison is
  produced;
* the control reconstruction dependency is verified against the historical
  C36 manifest hash using the manifest's declared hash mode;
* a failed audit writes only a blocked audit/report and no valid comparison;
* the baseline is named "Winter-style four-type extension baseline", not a
  direct Winter paper result.

No Gold is modified and no real API is called.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage3_extended_violations import (
    EXTENDED_TYPES,
    NONE_LABEL,
    control_prediction_from_scores,
)
from bpc_hybrid.s3_c36_target_paired_v1 import (
    C36_CONTROL_RECONSTRUCTION_RULE,
    TYPES,
    derive_target_paired_rows,
    read_json,
    read_jsonl,
    sha256_file,
    sha256_file_canonical_lf,
)
from bpc_hybrid.s3_semantic_grounding_v3 import evaluate_target_paired

REVISION = "s3_c36_target_paired_v2"
BASE_REVISION = "s3_c36_target_paired_v1"
EVALUATOR_VERSION = "s3_c36_target_paired_gate@2.0.0"
BASELINE_NAME = "Winter-style four-type extension baseline"
RECONSTRUCTION_DEPENDENCY_PATH = "src/bpc_hybrid/stage3_extended_violations.py"
RECONSTRUCTION_DEPENDENCY_FUNCTION = "control_prediction_from_scores"
TARGET_EVALUATOR_PATH = "src/bpc_hybrid/s3_semantic_grounding_v3.py"
TARGET_EVALUATOR_FUNCTION = "evaluate_target_paired"
REQUIRED_MANIFEST_INPUTS = (
    "data/development/human_review/stage3_gold_inference_v1.json",
    "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json",
)


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(float(value))


def _issue(code: str, scope: str, detail: str, *, item_id: str | None = None,
           target: str | None = None) -> dict[str, Any]:
    issue = {"code": code, "scope": scope, "detail": detail,
             "blocking": True}
    if item_id is not None:
        issue["item_id"] = item_id
    if target is not None:
        issue["target"] = target
    return issue


def _normalise(path: Any) -> str:
    return str(path).replace("\\", "/")


def _manifest_hashes(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        _normalise(key): value
        for key, value in (manifest.get("implementation_hashes") or {}).items()
    }


def _manifest_artifacts(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        _normalise(key): value
        for key, value in (manifest.get("artifacts") or {}).items()
    }


def _find_best_key(keys: Sequence[str], needle: str) -> str | None:
    for key in keys:
        if needle in key:
            return key
    return None


def _hash_pair(path: Path) -> tuple[str, str]:
    return sha256_file(path), sha256_file_canonical_lf(path)


def dependency_bindings(root: Path,
                        c36_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Verify frozen reconstruction dependency and record current evaluator."""
    issues: list[dict[str, Any]] = []
    implementation_hashes = _manifest_hashes(c36_manifest)
    hash_mode = str(c36_manifest.get("implementation_hash_mode") or "")
    dep_path = root / RECONSTRUCTION_DEPENDENCY_PATH
    dep_raw, dep_lf = _hash_pair(dep_path)
    dep_key = _find_best_key(list(implementation_hashes),
                             "stage3_extended_violations.py")
    expected_dep = implementation_hashes.get(dep_key) if dep_key else None
    if dep_key is None or not expected_dep:
        issues.append(_issue(
            "missing_frozen_reconstruction_dependency_hash",
            "dependency",
            "C36 manifest has no implementation hash for "
            "stage3_extended_violations.py"))
        dep_verified = False
    elif hash_mode == "canonical_lf_utf8_text":
        dep_verified = dep_lf == expected_dep
        if not dep_verified:
            issues.append(_issue(
                "reconstruction_dependency_mismatch",
                "dependency",
                "current canonical-LF hash of stage3_extended_violations.py "
                "does not match the C36 manifest frozen hash"))
    else:
        dep_verified = dep_raw == expected_dep
        if not dep_verified:
            issues.append(_issue(
                "reconstruction_dependency_mismatch",
                "dependency",
                "current raw hash of stage3_extended_violations.py does not "
                "match the C36 manifest hash mode"))
    evaluator_path = root / TARGET_EVALUATOR_PATH
    evaluator_raw, evaluator_lf = _hash_pair(evaluator_path)
    return {
        "schema_version": "s3_c36_target_paired_dependencies@2.0.0",
        "control_reconstruction": {
            "path": RECONSTRUCTION_DEPENDENCY_PATH,
            "function": RECONSTRUCTION_DEPENDENCY_FUNCTION,
            "rule": C36_CONTROL_RECONSTRUCTION_RULE,
            "c36_manifest_hash_mode": hash_mode,
            "c36_manifest_expected_sha256": expected_dep,
            "current_raw_sha256": dep_raw,
            "current_canonical_lf_sha256": dep_lf,
            "verified_frozen_match": dep_verified,
            "verification_basis": (
                "canonical_lf_utf8_text hash match"
                if hash_mode == "canonical_lf_utf8_text" and dep_verified
                else "raw hash match"
                if dep_verified else "not verified"),
        },
        "target_paired_evaluator": {
            "path": TARGET_EVALUATOR_PATH,
            "function": TARGET_EVALUATOR_FUNCTION,
            "current_raw_sha256": evaluator_raw,
            "current_canonical_lf_sha256": evaluator_lf,
            "verified_frozen_match": None,
            "verification_basis": (
                "recorded current implementation; this evaluator is the "
                "current target-paired protocol and is not stored in the "
                "historical C36 manifest"),
        },
        "blocking_issues": issues,
    }


def threshold_binding(c36_rows: Sequence[Mapping[str, Any]],
                      c36_manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Bind row gamma_ext values to the C36 frozen extension threshold."""
    issues: list[dict[str, Any]] = []
    expected = (c36_manifest.get("extension_thresholds") or {}).get("gamma_ext")
    if expected is None or not _is_finite_number(expected):
        issues.append(_issue(
            "missing_frozen_gamma_ext_threshold",
            "threshold",
            "C36 manifest has no finite extension_thresholds.gamma_ext"))
        expected_value = None
    else:
        expected_value = float(expected)
    values: list[float] = []
    for row in c36_rows:
        item_id = row.get("item_id")
        value = row.get("gamma_ext")
        if not _is_finite_number(value):
            issues.append(_issue(
                "invalid_row_gamma_ext",
                "threshold",
                "row gamma_ext is missing or non-finite",
                item_id=str(item_id)))
            continue
        value_float = float(value)
        values.append(value_float)
        if expected_value is not None and value_float != expected_value:
            issues.append(_issue(
                "row_gamma_ext_threshold_mismatch",
                "threshold",
                f"row gamma_ext={value_float} != frozen {expected_value}",
                item_id=str(item_id)))
    return {
        "frozen_manifest_gamma_ext": expected_value,
        "row_gamma_ext_values": sorted(set(values)),
        "all_rows_match_frozen_threshold": (
            expected_value is not None
            and not issues
            and values
            and all(value == expected_value for value in values)),
        "blocking_issues": issues,
    }


def _field_audit(c36_rows: Sequence[Mapping[str, Any]],
                 expected_gamma_ext: float | None) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    variant_stats: dict[str, dict[str, int]] = {}
    control_stats: dict[str, dict[str, int]] = {}
    for target in TYPES:
        variant_stats[target] = dict(Counter())
        control_stats[target] = dict(Counter())
    for row in c36_rows:
        item_id = str(row.get("item_id") or "")
        gamma = row.get("gamma_ext")
        gamma_value = float(gamma) if _is_finite_number(gamma) else None
        scores_detail = row.get("scores_detail")
        if not isinstance(scores_detail, Mapping):
            issues.append(_issue(
                "missing_scores_detail",
                "field", "scores_detail is not an object", item_id=item_id))
            continue
        control_scores = row.get("control_scores")
        if not isinstance(control_scores, Mapping):
            issues.append(_issue(
                "missing_control_scores",
                "field", "control_scores is not an object", item_id=item_id))
            continue
        for target in TYPES:
            variant_entry = scores_detail.get(target)
            control_entry = control_scores.get(target)
            if not isinstance(variant_entry, Mapping):
                issues.append(_issue(
                    "missing_variant_check",
                    "variant", "scores_detail target entry missing",
                    item_id=item_id, target=target))
                variant_stats[target]["missing_entry"] = \
                    variant_stats[target].get("missing_entry", 0) + 1
            else:
                observable = variant_entry.get("observable")
                violation = variant_entry.get("violation")
                if not isinstance(observable, bool):
                    issues.append(_issue(
                        "variant_observable_not_boolean",
                        "variant", "observable is not boolean",
                        item_id=item_id, target=target))
                elif observable and not isinstance(violation, bool):
                    issues.append(_issue(
                        "variant_violation_missing",
                        "variant", "observable=true but violation is not boolean",
                        item_id=item_id, target=target))
                elif not observable and isinstance(violation, bool):
                    issues.append(_issue(
                        "variant_unobservable_with_boolean_violation",
                        "variant",
                        "observable=false but a boolean violation is present",
                        item_id=item_id, target=target))
                variant_stats[target]["rows"] = \
                    variant_stats[target].get("rows", 0) + 1
                variant_stats[target][
                    "observable_true" if observable is True else "observable_false"
                ] = variant_stats[target].get(
                    "observable_true" if observable is True else "observable_false",
                    0) + 1
            if not isinstance(control_entry, Mapping):
                issues.append(_issue(
                    "missing_control_check",
                    "control", "control_scores target entry missing",
                    item_id=item_id, target=target))
                control_stats[target]["missing_entry"] = \
                    control_stats[target].get("missing_entry", 0) + 1
                continue
            observable = control_entry.get("observable")
            score = control_entry.get("score")
            violation = control_entry.get("violation")
            if not isinstance(observable, bool):
                issues.append(_issue(
                    "control_observable_not_boolean",
                    "control", "observable is not boolean",
                    item_id=item_id, target=target))
            if isinstance(violation, bool):
                issues.append(_issue(
                    "control_unexpected_explicit_boolean",
                    "control",
                    "control_scores should not carry a final boolean violation",
                    item_id=item_id, target=target))
            if observable is True:
                if not _is_finite_number(score):
                    issues.append(_issue(
                        "control_score_missing_or_invalid",
                        "control", "observable=true but score is not finite",
                        item_id=item_id, target=target))
                if target == "constraint_violated" \
                        and "exact_contradiction" not in control_entry:
                    issues.append(_issue(
                        "control_constraint_exact_contradiction_missing",
                        "control",
                        "observable constraint needs exact_contradiction field",
                        item_id=item_id, target=target))
                if gamma_value is None:
                    issues.append(_issue(
                        "control_reconstruction_threshold_missing",
                        "control",
                        "observable control needs a finite gamma_ext",
                        item_id=item_id, target=target))
                else:
                    try:
                        derived = control_prediction_from_scores(
                            control_scores, gamma_value)["per_type"].get(target)
                    except Exception as exc:  # noqa: BLE001
                        issues.append(_issue(
                            "control_reconstruction_failed",
                            "control", f"frozen rule raised {type(exc).__name__}",
                            item_id=item_id, target=target))
                        derived = None
                    if not isinstance(derived, bool):
                        issues.append(_issue(
                            "control_reconstruction_not_boolean",
                            "control",
                            "frozen rule did not return a boolean for "
                            "observable control check",
                            item_id=item_id, target=target))
            else:
                if score is not None:
                    issues.append(_issue(
                        "control_unobservable_with_score",
                        "control", "observable=false but score is present",
                        item_id=item_id, target=target))
            control_stats[target]["rows"] = \
                control_stats[target].get("rows", 0) + 1
            control_stats[target][
                "observable_true" if observable is True else "observable_false"
            ] = control_stats[target].get(
                "observable_true" if observable is True else "observable_false",
                0) + 1
            if observable is True and _is_finite_number(score):
                control_stats[target]["observable_score_present"] = \
                    control_stats[target].get("observable_score_present", 0) + 1
    return {
        "variant_field_stats": variant_stats,
        "control_field_stats": control_stats,
        "blocking_issues": issues,
    }


def _current_rows_audit(current_rows: Sequence[Mapping[str, Any]],
                        panel_by_id: Mapping[str, Mapping[str, Any]],
                        c36_by_id: Mapping[str, Mapping[str, Any]]
                        ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    rows_by_key: dict[tuple[str, str], Mapping[str, Any]] = {}
    duplicate_keys: list[list[str]] = []
    for row in current_rows:
        key = (str(row.get("item_id")), str(row.get("side")))
        if key in rows_by_key:
            duplicate_keys.append([key[0], key[1]])
        rows_by_key[key] = row
    variant_ids = [str(row.get("item_id")) for row in current_rows
                   if row.get("side") == "variant"]
    control_ids = [str(row.get("item_id")) for row in current_rows
                   if row.get("side") == "control"]
    if duplicate_keys:
        issues.append(_issue(
            "duplicate_current_objects",
            "current",
            f"duplicate (item_id, side) keys: {duplicate_keys[:5]}"))
    if len(variant_ids) != 40 or len(control_ids) != 40:
        issues.append(_issue(
            "incomplete_current_objects",
            "current",
            f"expected 40 variant + 40 control current rows, got "
            f"{len(variant_ids)} + {len(control_ids)}"))
    if sorted(variant_ids) != sorted(panel_by_id):
        issues.append(_issue(
            "current_variant_sample_mismatch",
            "current",
            "current variant item ids do not equal panel variant ids"))
    if sorted(control_ids) != sorted(panel_by_id):
        issues.append(_issue(
            "current_control_sample_mismatch",
            "current",
            "current control item ids do not equal panel variant ids"))
    for item_id, panel_item in panel_by_id.items():
        for side in ("variant", "control"):
            row = rows_by_key.get((item_id, side))
            if row is None:
                continue
            if row.get("process_id") != panel_item.get("process_id") \
                    or row.get("rule_id") != panel_item.get("rule_id"):
                issues.append(_issue(
                    "current_process_rule_mismatch",
                    "current",
                    "current process_id/rule_id differs from panel",
                    item_id=item_id))
            expected = panel_item.get("expected_violation") \
                if side == "variant" else NONE_LABEL
            if row.get("expected_label") != expected:
                issues.append(_issue(
                    "current_expected_label_mismatch",
                    "current",
                    f"current {side} expected_label="
                    f"{row.get('expected_label')!r} != {expected!r}",
                    item_id=item_id))
            c36_row = c36_by_id.get(item_id)
            if c36_row is not None:
                source_hashes = c36_row.get("source_hashes") or {}
                expected_bpmn = source_hashes.get(
                    "variant_bpmn_sha256" if side == "variant"
                    else "control_bpmn_sha256")
                if row.get("bpmn_sha256") != expected_bpmn:
                    issues.append(_issue(
                        "current_bpmn_hash_mismatch",
                        "current",
                        f"current {side} bpmn_sha256 differs from C36 source",
                        item_id=item_id))
            checks = row.get("checks")
            if not isinstance(checks, Mapping):
                issues.append(_issue(
                    "current_checks_missing",
                    "current", "current prediction has no checks object",
                    item_id=item_id))
                continue
            for target in TYPES:
                check = checks.get(target)
                if not isinstance(check, Mapping):
                    issues.append(_issue(
                        "current_check_missing",
                        "current", "current check entry missing",
                        item_id=item_id, target=target))
                    continue
                observable = check.get("observable")
                violation = check.get("violation")
                if not isinstance(observable, bool):
                    issues.append(_issue(
                        "current_observable_not_boolean",
                        "current", "observable is not boolean",
                        item_id=item_id, target=target))
                elif observable and not isinstance(violation, bool):
                    issues.append(_issue(
                        "current_violation_missing",
                        "current",
                        "observable=true but violation is not boolean",
                        item_id=item_id, target=target))
                elif not observable and isinstance(violation, bool):
                    issues.append(_issue(
                        "current_unobservable_with_boolean_violation",
                        "current",
                        "observable=false but violation is boolean",
                        item_id=item_id, target=target))
    return rows_by_key, issues


def audit_gate(*, c36_rows: Sequence[Mapping[str, Any]],
               panel: Mapping[str, Any],
               current_rows: Sequence[Mapping[str, Any]],
               c36_manifest: Mapping[str, Any],
               current_artifact_hashes: Mapping[str, Any],
               current_predictions_path: Path,
               c36_predictions_path: Path,
               c36_report: Mapping[str, Any] | None = None,
               root: Path) -> dict[str, Any]:
    """Full compatibility gate.  Any blocking issue prevents comparison."""
    blocking: list[dict[str, Any]] = []
    panel_variants = list(panel.get("variants") or [])
    panel_ids = [str(item.get("variant_id")) for item in panel_variants]
    panel_by_id = {str(item["variant_id"]): item for item in panel_variants}
    c36_ids = [str(row.get("item_id")) for row in c36_rows]
    c36_by_id = {str(row.get("item_id")): row for row in c36_rows}
    if len(set(panel_ids)) != len(panel_ids):
        blocking.append(_issue("duplicate_panel_ids", "panel",
                               "panel variant ids are not unique"))
    if len(c36_ids) != 40 or len(c36_by_id) != 40:
        blocking.append(_issue(
            "incomplete_c36_rows", "c36",
            f"expected 40 unique C36 rows, got {len(c36_ids)} raw / "
            f"{len(c36_by_id)} unique"))
    if len(set(c36_ids)) != len(c36_ids):
        blocking.append(_issue("duplicate_c36_ids", "c36",
                               "C36 item ids are not unique"))
    if sorted(c36_ids) != sorted(panel_ids):
        blocking.append(_issue(
            "c36_sample_mismatch", "c36",
            "C36 item ids do not equal the current panel variant ids"))
    current_rows_audit, current_issues = _current_rows_audit(
        current_rows, panel_by_id, c36_by_id)
    blocking.extend(current_issues)

    label_issues: list[dict[str, Any]] = []
    process_issues: list[dict[str, Any]] = []
    c36_variant_hash_issues: list[dict[str, Any]] = []
    c36_control_hash_issues: list[dict[str, Any]] = []
    variant_expected = set(EXTENDED_TYPES)
    for item_id, panel_item in panel_by_id.items():
        row = c36_by_id.get(item_id)
        if row is None:
            continue
        expected = row.get("expected_violation")
        if expected not in variant_expected:
            label_issues.append({
                "item_id": item_id, "c36": expected,
                "reason": "expected label not in four extension types"})
        elif expected != panel_item.get("expected_violation"):
            label_issues.append({
                "item_id": item_id, "c36": expected,
                "panel": panel_item.get("expected_violation")})
        if row.get("process_id") != panel_item.get("process_id") \
                or row.get("rule_id") != panel_item.get("rule_id"):
            process_issues.append({
                "item_id": item_id,
                "c36": [row.get("process_id"), row.get("rule_id")],
                "panel": [panel_item.get("process_id"),
                          panel_item.get("rule_id")]})
        source_hashes = row.get("source_hashes") or {}
        if source_hashes.get("variant_bpmn_sha256") \
                != panel_item.get("variant_bpmn_sha256"):
            c36_variant_hash_issues.append({"item_id": item_id})
        if source_hashes.get("control_bpmn_sha256") \
                != panel_item.get("control_bpmn_sha256"):
            c36_control_hash_issues.append({"item_id": item_id})
    if label_issues:
        blocking.append(_issue("c36_label_mismatch", "c36",
                               f"{len(label_issues)} label issues"))
    if process_issues:
        blocking.append(_issue("c36_process_rule_mismatch", "c36",
                               f"{len(process_issues)} process/rule issues"))
    if c36_variant_hash_issues or c36_control_hash_issues:
        blocking.append(_issue(
            "c36_bpmn_hash_mismatch", "c36",
            "variant/control BPMN hash mismatch against panel"))

    dependencies = dependency_bindings(root, c36_manifest)
    blocking.extend(dependencies["blocking_issues"])
    thresholds = threshold_binding(c36_rows, c36_manifest)
    blocking.extend(thresholds["blocking_issues"])
    expected_gamma = thresholds.get("frozen_manifest_gamma_ext")
    fields = _field_audit(c36_rows, expected_gamma)
    blocking.extend(fields["blocking_issues"])

    manifest_inputs: list[dict[str, Any]] = []
    manifest_input_map = {
        _normalise(key): value
        for key, value in (c36_manifest.get("inputs") or {}).items()
    }
    for required in REQUIRED_MANIFEST_INPUTS:
        match_key = _find_best_key(list(manifest_input_map), required)
        if match_key is None:
            manifest_inputs.append({
                "path": required, "present_in_c36_manifest": False,
                "match": False})
            blocking.append(_issue(
                "required_c36_manifest_input_missing", "input",
                f"C36 manifest has no input hash for {required}"))
            continue
        expected = manifest_input_map[match_key]
        path = root / match_key
        entry: dict[str, Any] = {
            "path": required, "manifest_key": match_key,
            "present_in_c36_manifest": True,
            "expected_sha256": expected,
        }
        if not path.is_file():
            entry["exists"] = False
            entry["match"] = False
            blocking.append(_issue(
                "required_input_missing", "input",
                f"required input file is missing: {required}"))
        else:
            raw, lf = _hash_pair(path)
            entry.update({
                "exists": True,
                "current_raw_sha256": raw,
                "current_canonical_lf_sha256": lf,
                "raw_match": raw == expected,
                "canonical_lf_match": lf == expected,
                "match": raw == expected or lf == expected,
            })
            if not entry["match"]:
                blocking.append(_issue(
                    "required_input_hash_mismatch", "input",
                    f"current input hash mismatch for {required}"))
        manifest_inputs.append(entry)

    artifacts = _manifest_artifacts(c36_manifest)
    c36_prediction_key = _find_best_key(
        list(artifacts), "extended_four/reference/winter/predictions.jsonl")
    c36_prediction_identity: dict[str, Any] = {
        "path": _normalise(c36_predictions_path.relative_to(root))
        if c36_predictions_path.is_absolute() else _normalise(c36_predictions_path),
        "manifest_key": c36_prediction_key,
        "expected_sha256": artifacts.get(c36_prediction_key)
        if c36_prediction_key else None,
    }
    if c36_prediction_key is None:
        c36_prediction_identity["match"] = False
        blocking.append(_issue(
            "c36_prediction_hash_missing", "prediction",
            "C36 manifest has no artifact hash for Winter predictions"))
    else:
        raw, lf = _hash_pair(c36_predictions_path)
        c36_prediction_identity.update({
            "current_raw_sha256": raw,
            "current_canonical_lf_sha256": lf,
            "raw_match": raw == artifacts[c36_prediction_key],
            "canonical_lf_match": lf == artifacts[c36_prediction_key],
            "match": (raw == artifacts[c36_prediction_key]
                      or lf == artifacts[c36_prediction_key]),
        })
        if not c36_prediction_identity["match"]:
            blocking.append(_issue(
                "c36_prediction_hash_mismatch", "prediction",
                "current C36/Winter predictions do not match the historical "
                "C36 manifest artifact hash"))

    current_key = "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl"
    expected_current = _normalise(
        (current_artifact_hashes.get("artifacts") or {}).get(current_key)
        or current_artifact_hashes.get(current_key) or "")
    current_identity: dict[str, Any] = {
        "path": current_key,
        "expected_sha256": expected_current or None,
    }
    if not expected_current:
        current_identity["match"] = False
        blocking.append(_issue(
            "current_prediction_hash_missing", "prediction",
            "v5 artifact_hashes has no predictions.jsonl hash"))
    else:
        raw, lf = _hash_pair(current_predictions_path)
        current_identity.update({
            "current_raw_sha256": raw,
            "current_canonical_lf_sha256": lf,
            "raw_match": raw == expected_current,
            "canonical_lf_match": lf == expected_current,
            "match": raw == expected_current or lf == expected_current,
        })
        if not current_identity["match"]:
            blocking.append(_issue(
                "current_prediction_hash_mismatch", "prediction",
                "current v5 predictions do not match the v5 artifact hash"))

    sample_sets = {
        "c36_rows": len(c36_rows),
        "c36_unique_item_ids": len(set(c36_ids)),
        "panel_variant_rows": len(panel_ids),
        "current_variant_rows": len([r for r in current_rows
                                     if r.get("side") == "variant"]),
        "current_control_rows": len([r for r in current_rows
                                     if r.get("side") == "control"]),
        "c36_item_ids_equal_panel": sorted(c36_ids) == sorted(panel_ids),
        "missing_in_c36": sorted(set(panel_ids) - set(c36_ids)),
        "extra_in_c36": sorted(set(c36_ids) - set(panel_ids)),
    }
    blocking_codes = sorted({issue["code"] for issue in blocking})
    return {
        "schema_version": "s3_c36_target_paired_audit@2.0.0",
        "revision": REVISION,
        "base_revision": BASE_REVISION,
        "scope": "development_only_synthetic_panel",
        "baseline_name": BASELINE_NAME,
        "panel": panel.get("panel_id") or panel.get("schema_version"),
        "gate_status": "blocked" if blocking else "pass",
        "can_build_target_paired": not blocking,
        "blocking_issue_count": len(blocking),
        "blocking_issue_codes": blocking_codes,
        "blocking_issues": blocking,
        "sample_sets": sample_sets,
        "label_issues": label_issues,
        "process_issues": process_issues,
        "c36_variant_bpmn_hash_issues": c36_variant_hash_issues,
        "c36_control_bpmn_hash_issues": c36_control_hash_issues,
        "current_rows_audit_summary": {
            "row_count": len(current_rows_audit),
            "blocking_issue_count": len(current_issues),
        },
        "manifest_input_checks": manifest_inputs,
        "c36_prediction_identity": c36_prediction_identity,
        "current_prediction_identity": current_identity,
        "dependency_bindings": dependencies,
        "threshold_binding": thresholds,
        "field_audit": fields,
        "control_reconstruction_rule": C36_CONTROL_RECONSTRUCTION_RULE,
        "control_reconstruction_required": True,
        "affected_control_samples": 40,
        "affected_control_checks": 160,
        "control_booleans_persisted_in_output_rows": True,
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
        "control_target_false_positive_rate_all_pairs": metrics[
            "control_target_false_positive_rate"],
        "control_target_false_positive_rate_decided_controls": metrics[
            "control_target_false_positive_rate_over_decided_controls"],
        "target_field_unknown_rate_all_side_checks": metrics[
            "target_field_unknown_rate"],
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


def compare_target_paired_gated(
    c36_rows: Sequence[Mapping[str, Any]],
    current_rows: Sequence[Mapping[str, Any]],
    panel: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute the target-paired comparison after the audit gate passed."""
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
    return {
        "schema_version": "s3_c36_target_paired_comparison@2.0.0",
        "revision": REVISION,
        "base_revision": BASE_REVISION,
        "scope": "development_only_synthetic_panel",
        "baseline_name": BASELINE_NAME,
        "evaluation_protocol": {
            "primary": "target_paired_causal",
            "denominator": (
                "all 40 frozen pairs; variant unknown is FN but reported "
                "separately; control unknown is outside the decided TNR "
                "denominator and reported separately; pair success requires "
                "variant positive and control negative"),
            "expected_labels_used_only_for_grouping": True,
        },
        "c36_winter_style_baseline": _comparison_row(c36_metrics),
        "current_v5": _comparison_row(current_metrics),
        "delta_current_minus_baseline": {
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
            "baseline": {
                "variant_unknown_count": sum(
                    c36_metrics["per_type"][target]["variant"]["unknown"]
                    for target in TYPES),
                "control_unknown_count": sum(
                    c36_metrics["per_type"][target]["control"]["unknown"]
                    for target in TYPES),
                "variant_unknown_rate": c36_metrics["variant_unknown_rate"],
                "control_unknown_rate": c36_metrics["control_unknown_rate"],
                "overall_unknown_denominator": "2 * 40 side checks",
            },
            "current_v5": {
                "variant_unknown_count": sum(
                    current_metrics["per_type"][target]["variant"]["unknown"]
                    for target in TYPES),
                "control_unknown_count": sum(
                    current_metrics["per_type"][target]["control"]["unknown"]
                    for target in TYPES),
                "variant_unknown_rate": current_metrics["variant_unknown_rate"],
                "control_unknown_rate": current_metrics["control_unknown_rate"],
                "overall_unknown_denominator": "2 * 40 side checks",
            },
        },
        "baseline_metrics_full": c36_metrics,
        "current_metrics_full": current_metrics,
    }


__all__ = [
    "REVISION",
    "BASE_REVISION",
    "EVALUATOR_VERSION",
    "BASELINE_NAME",
    "RECONSTRUCTION_DEPENDENCY_PATH",
    "RECONSTRUCTION_DEPENDENCY_FUNCTION",
    "TARGET_EVALUATOR_PATH",
    "TARGET_EVALUATOR_FUNCTION",
    "REQUIRED_MANIFEST_INPUTS",
    "dependency_bindings",
    "threshold_binding",
    "audit_gate",
    "derive_target_paired_rows",
    "compare_target_paired_gated",
]

# -*- coding: utf-8 -*-
"""Stage 3 semantic-grounding revision v3 (evaluation-protocol repair).

This thin revision reuses the frozen v1 deterministic scorer and the frozen
v2 predictions but fixes the input-pack anonymisation, the target-paired
metric accounting, and the fallback transition accounting.  It creates new
artifacts only; v1/v2 evidence is read-only provenance.

No real LLM/API call is made by this module.
"""

from __future__ import annotations

import copy
import re
from collections import defaultdict
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL
from bpc_hybrid.s3_semantic_grounding_v2 import (
    FALLBACK_PACK_SCHEMA,
    audit_composite_collisions,
    evaluate_unified_objects,
    evaluate_variant_binary,
    input_identity,
    unified_objects_legacy,
)
from bpc_hybrid.s3_semantic_grounding_v2 import (
    fallback_triggers as _v2_fallback_triggers,
)

REVISION = "s3_semantic_grounding_v3"
EVALUATOR_VERSION = "s3_semantic_grounding_v3_evaluator@1.0.0"
REUSED_DETERMINISTIC_REVISION = "s3_semantic_grounding_v2"

# ---------------------------------------------------------------------------
# Anonymisation: identifiers and explicit generator metadata only
# ---------------------------------------------------------------------------

_STRICT_ID_KEYS = frozenset({
    "id", "activity_id", "candidate_activity_ids", "source_ref", "target_ref",
    "source_id", "target_id", "flow_id", "boundary_event_id", "handler_task_id",
    "annotation_id", "association_id", "data_object_id", "event_id",
    "attached_to", "bound_activity_id", "handler_of", "branch_target_ids",
})
_FORBIDDEN_METADATA_KEYS = frozenset({
    "expected_violation", "mutation_type", "target_field", "mutation_config",
    "target_activity_id", "gold", "Gold", "side", "variant_id",
    "synthetic_type_name", "control_variant_difference",
    "paired_counterpart_prediction",
})
_GENERATED_ID_TOKEN_RE = re.compile(r"\bsyn_[A-Za-z0-9_\-.:]+\b")


def _collect_ids_from_value(value: Any, out: set[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            out.add(value.strip())
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_ids_from_value(item, out)


def _collect_generated_tokens(value: Any, out: set[str]) -> None:
    if isinstance(value, str):
        for match in _GENERATED_ID_TOKEN_RE.finditer(value):
            out.add(match.group(0))
    elif isinstance(value, Mapping):
        for item in value.values():
            _collect_generated_tokens(item, out)
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_generated_tokens(item, out)


def _collect_payload_ids(payload: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()

    def walk(value: Any, parent_key: str | None = None) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_string = str(key)
                if key_string in _STRICT_ID_KEYS:
                    _collect_ids_from_value(item, ids)
                else:
                    walk(item, key_string)
        elif isinstance(value, list):
            for item in value:
                walk(item, parent_key)
        elif isinstance(value, str) and parent_key in _STRICT_ID_KEYS:
            if value.strip():
                ids.add(value.strip())

    walk(payload, None)
    generated: set[str] = set()
    _collect_generated_tokens(payload, generated)
    ids.update(generated)
    return ids


def _replace_known_tokens(text: str, id_map: Mapping[str, str],
                          *, generated_only: bool) -> str:
    if generated_only:
        def replace_generated(match: re.Match[str]) -> str:
            token = match.group(0)
            return id_map.get(token, token)
        return _GENERATED_ID_TOKEN_RE.sub(replace_generated, text)
    for original in sorted(id_map, key=len, reverse=True):
        if len(original) < 3 and "_" not in original:
            continue
        text = text.replace(original, id_map[original])
    return text


def _map_id_value(value: Any, id_map: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in id_map:
            return id_map[stripped]
        return _replace_known_tokens(value, id_map, generated_only=False)
    if isinstance(value, list):
        return [_map_id_value(item, id_map) for item in value]
    if isinstance(value, tuple):
        return [_map_id_value(item, id_map) for item in value]
    return value


def _anonymize_node(value: Any, id_map: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_string = str(key)
            if key_string in _FORBIDDEN_METADATA_KEYS:
                continue
            if key_string in _STRICT_ID_KEYS:
                result[key_string] = _map_id_value(item, id_map)
            elif key_string == "owner":
                if isinstance(item, str):
                    result[key_string] = _replace_known_tokens(
                        item, id_map, generated_only=True)
                else:
                    result[key_string] = _anonymize_node(item, id_map)
            else:
                result[key_string] = _anonymize_node(item, id_map)
        return result
    if isinstance(value, list):
        return [_anonymize_node(item, id_map) for item in value]
    if isinstance(value, tuple):
        return [_anonymize_node(item, id_map) for item in value]
    if isinstance(value, str):
        # Preserve natural-language semantics.  Only generated identifier
        # tokens are replaced, never corpus words such as "controller".
        return _replace_known_tokens(value, id_map, generated_only=True)
    return value


def anonymize_fallback_payload(
    payload: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """Anonymise identifiers and generator metadata, preserving semantics.

    Human-readable rule text, activity labels, condition/constraint/exception
    text, and other natural-language values are copied unchanged except when a
    value is itself a generated synthetic identifier token.
    """
    ids = _collect_payload_ids(payload)
    id_map = {
        original: f"E{index:04d}"
        for index, original in enumerate(sorted(ids), start=1)
    }
    anonymized = _anonymize_node(copy.deepcopy(dict(payload)), id_map)
    return anonymized, id_map


def _semantic_rule_fields(rule_record: Mapping[str, Any]) -> dict[str, str]:
    return {
        "actor": str(rule_record.get("actor") or ""),
        "action": str(rule_record.get("action") or ""),
        "condition": str(rule_record.get("condition") or ""),
        "constraint": str(rule_record.get("constraint") or ""),
        "exception": str(rule_record.get("exception") or ""),
    }


def build_fallback_pack(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Freeze deterministic abstentions with a semantics-preserving pack."""
    items: list[dict[str, Any]] = []
    trigger_counts: dict[str, int] = defaultdict(int)
    side_counts: dict[str, int] = defaultdict(int)
    for source_index, row in enumerate(rows):
        if row.get("predicted_violation_type") is not None:
            continue
        triggers = _v2_fallback_triggers(row)
        if not triggers:
            continue
        rule_record = dict(row.get("model_visible_rule_input") or {})
        raw_context = dict(row.get("compact_local_context") or {})
        visible_payload = {
            "rule_record": rule_record,
            "candidate_activities": raw_context.get("candidate_activities", []),
            "candidate_activity_ids": [
                item.get("activity_id")
                for item in raw_context.get("candidate_activities", [])
                if item.get("activity_id")
            ],
            "local_context": {
                "nodes": raw_context.get("nodes", []),
                "sequence_flows": raw_context.get("sequence_flows", []),
                "condition_evidence": raw_context.get("condition_evidence", []),
                "constraint_bound_evidence": raw_context.get("constraint_bound_evidence", []),
                "constraint_unbound_evidence": raw_context.get("constraint_unbound_evidence", []),
                "exception_handler_candidates": raw_context.get("exception_handler_candidates", []),
                "evidence_ids": raw_context.get("evidence_ids", []),
            },
        }
        anonymized, id_map = anonymize_fallback_payload(visible_payload)
        anonymized_rule = dict(anonymized.get("rule_record") or {})
        original_rule = _semantic_rule_fields(rule_record)
        preserved = {
            key: {
                "before": original_rule[key],
                "after": str(anonymized_rule.get(key) or ""),
                "preserved": original_rule[key] == str(anonymized_rule.get(key) or ""),
            }
            for key in original_rule
        }
        items.append({
            "fallback_item_id": f"fb_v3_{len(items) + 1:04d}",
            "side": row.get("side"),
            "source_index": source_index,
            "canonical_rule_input_hash": row.get("canonical_rule_input_hash"),
            "canonical_process_input_hash": row.get("canonical_process_input_hash"),
            "deterministic_status": {
                target: {
                    "status": (row.get("checks") or {}).get(target, {}).get("status"),
                    "violation": (row.get("checks") or {}).get(target, {}).get("violation"),
                    "reason": (row.get("checks") or {}).get(target, {}).get("reason"),
                    "observable": (row.get("checks") or {}).get(target, {}).get("observable"),
                }
                for target in EXTENDED_TYPES
            },
            "action_grounding_status": (row.get("action_grounding") or {}).get("status"),
            "trigger_reasons": triggers,
            "llm_visible_payload": anonymized,
            "anonymized_id_map": id_map,
            "semantic_field_preservation": preserved,
            "semantic_fields_preserved": all(
                entry["preserved"] for entry in preserved.values()
            ),
        })
        for trigger in triggers:
            trigger_counts[trigger] += 1
        side_counts[str(row.get("side"))] += 1
    return {
        "schema_version": FALLBACK_PACK_SCHEMA,
        "revision": REVISION,
        "scope": "development_only",
        "candidate_policy": (
            "only final deterministic abstentions (predicted_violation_type=None) "
            "with at least one documented semantic ambiguity/unresolved trigger; "
            "deterministic clear compliant/violation objects are excluded; "
            "expected/mutation/target metadata is not included"
        ),
        "anonymisation_policy": (
            "identifiers and generated synthetic tokens are mapped; natural-language "
            "rule/activity/condition/constraint/exception text is preserved verbatim"
        ),
        "semantic_fields_preserved_for_all_items": all(
            item["semantic_fields_preserved"] for item in items
        ),
        "item_count": len(items),
        "side_counts": dict(side_counts),
        "trigger_counts": dict(trigger_counts),
        "items": items,
        "contains_expected_labels": False,
        "llm_payload_excludes_forbidden_fields": True,
        "id_reverse_mapping_available": True,
    }


# ---------------------------------------------------------------------------
# Corrected target-paired evaluation
# ---------------------------------------------------------------------------


def _p_r_f1(tp: int, fp: int, fn: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "precision_denominator_tp_plus_fp": tp + fp,
        "recall_denominator_tp_plus_fn": tp + fn,
    }


def _outcome(row: Mapping[str, Any], target_type: str) -> str:
    check = (row.get("checks") or {}).get(target_type) or {}
    if check.get("violation") is True:
        return "positive"
    if check.get("observable") is True and check.get("violation") is False:
        return "negative"
    return "unknown"


def _side_class(row: Mapping[str, Any], target_type: str) -> str:
    check = (row.get("checks") or {}).get(target_type) or {}
    outcome = _outcome(row, target_type)
    if outcome == "positive":
        return "determined_positive"
    if outcome == "negative":
        return "determined_negative"
    status = str(check.get("status") or "unknown")
    return "ambiguous" if status == "ambiguous" else "unknown"


def evaluate_target_paired(variant_rows: Sequence[Mapping[str, Any]],
                           control_rows: Sequence[Mapping[str, Any]],
                           expected_by_item: Mapping[str, str]) -> dict[str, Any]:
    """Target-paired causal evaluation with explicit unknown accounting.

    Every denominator below is explicit:

    * variant side: one check per pair (the mutated target field).  A variant
      positive is TP; an observable negative or an abstention is an FN, but
      the two failure modes are reported separately.
    * control side: one check per pair (the same target field).  Only
      observable negatives and positives enter the decided TNR denominator;
      abstentions are reported separately and do not silently disappear.
    * pair success = variant positive AND control negative, over all pairs.
    """
    controls = {row["item_id"]: row for row in control_rows}
    per_type: dict[str, Any] = {}
    aggregate = {
        "variant": {"positive": 0, "negative_observed_wrong": 0, "unknown": 0,
                    "total": 0},
        "control": {"negative": 0, "positive_false_alarm": 0, "unknown": 0,
                    "total": 0},
    }
    total_tp = total_fp = total_fn = total_tn = 0
    total_variant_unknown = total_control_unknown = 0
    total_variant_negative_wrong = 0
    total_pairs = total_pair_ok = 0
    pair_breakdown: dict[str, int] = defaultdict(int)
    for target in EXTENDED_TYPES:
        tp = fn = variant_negative_wrong = variant_unknown = 0
        tn = fp = control_unknown = 0
        pair_ok = pair_count = 0
        for variant in variant_rows:
            if variant.get("item_id") not in expected_by_item:
                continue
            if expected_by_item[variant["item_id"]] != target:
                continue
            if variant["item_id"] not in controls:
                continue
            control = controls[variant["item_id"]]
            variant_outcome = _outcome(variant, target)
            control_outcome = _outcome(control, target)
            pair_count += 1
            if variant_outcome == "positive":
                tp += 1
            else:
                fn += 1
                if variant_outcome == "negative":
                    variant_negative_wrong += 1
                else:
                    variant_unknown += 1
            if control_outcome == "negative":
                tn += 1
            elif control_outcome == "positive":
                fp += 1
            else:
                control_unknown += 1
            if variant_outcome == "positive" and control_outcome == "negative":
                pair_ok += 1
            if variant_outcome == "positive" and control_outcome == "negative":
                pair_breakdown["both_correct"] += 1
            elif variant_outcome == "unknown" and control_outcome == "unknown":
                pair_breakdown["both_unknown"] += 1
            elif variant_outcome == "unknown":
                pair_breakdown["variant_unknown"] += 1
            elif control_outcome == "unknown":
                pair_breakdown["control_unknown"] += 1
            elif variant_outcome == "positive" and control_outcome == "positive":
                pair_breakdown["control_false_alarm"] += 1
            elif variant_outcome == "negative" and control_outcome == "negative":
                pair_breakdown["variant_observed_wrong"] += 1
            else:
                pair_breakdown["other_mixed_failure"] += 1
        metrics = _p_r_f1(tp, fp, fn)
        variant_decided = tp + variant_negative_wrong
        control_decided = tn + fp
        per_type[target] = {
            "pairs": pair_count,
            "variant": {
                "TP": tp,
                "FN_observed_negative": variant_negative_wrong,
                "FN_unknown": variant_unknown,
                "FN": fn,
                "decided": variant_decided,
                "unknown": variant_unknown,
                "coverage": round(variant_decided / pair_count, 4) if pair_count else None,
                "denominator_pairs": pair_count,
            },
            "control": {
                "TN": tn,
                "FP": fp,
                "unknown": control_unknown,
                "decided": control_decided,
                "coverage": round(control_decided / pair_count, 4) if pair_count else None,
                "denominator_pairs": pair_count,
            },
            **metrics,
            "tpr_over_all_pairs": round(tp / pair_count, 4) if pair_count else None,
            "tnr_over_decided_controls": (
                round(tn / control_decided, 4) if control_decided else None),
            "control_fpr_over_decided_controls": (
                round(fp / control_decided, 4) if control_decided else None),
            "control_fpr_over_all_pairs": (
                round(fp / pair_count, 4) if pair_count else None),
            "pair_success": pair_ok,
            "pair_success_rate": round(pair_ok / pair_count, 4) if pair_count else None,
            "unknown_rate_variant": (
                round(variant_unknown / pair_count, 4) if pair_count else None),
            "unknown_rate_control": (
                round(control_unknown / pair_count, 4) if pair_count else None),
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_tn += tn
        total_variant_unknown += variant_unknown
        total_control_unknown += control_unknown
        total_variant_negative_wrong += variant_negative_wrong
        total_pairs += pair_count
        total_pair_ok += pair_ok
        aggregate["variant"]["positive"] += tp
        aggregate["variant"]["negative_observed_wrong"] += variant_negative_wrong
        aggregate["variant"]["unknown"] += variant_unknown
        aggregate["variant"]["total"] += pair_count
        aggregate["control"]["negative"] += tn
        aggregate["control"]["positive_false_alarm"] += fp
        aggregate["control"]["unknown"] += control_unknown
        aggregate["control"]["total"] += pair_count
    macro_f1 = round(
        sum(per_type[t]["f1"] for t in EXTENDED_TYPES) / len(EXTENDED_TYPES), 4
    )
    variant_total = aggregate["variant"]["total"]
    control_total = aggregate["control"]["total"]
    control_false_alarms = aggregate["control"]["positive_false_alarm"]
    control_decided_total = (aggregate["control"]["negative"]
                             + aggregate["control"]["positive_false_alarm"])
    all_side_checks = variant_total + control_total
    return {
        "schema_version": "s3_target_paired_evaluator@3.0.0",
        "evaluation_kind": "target_paired_causal",
        "primary": True,
        "total_pairs": total_pairs,
        "per_type": per_type,
        "aggregate_side_outcomes_mutually_exclusive": {
            "variant": {
                **aggregate["variant"],
                "coverage": round((total_tp + total_variant_negative_wrong)
                                   / variant_total, 4) if variant_total else None,
                "unknown_rate": round(aggregate["variant"]["unknown"] / variant_total, 4)
                if variant_total else None,
            },
            "control": {
                **aggregate["control"],
                "coverage": round(control_decided_total / control_total, 4)
                if control_total else None,
                "unknown_rate": round(aggregate["control"]["unknown"] / control_total, 4)
                if control_total else None,
                "false_positive_rate_over_decided_controls": (
                    round(control_false_alarms / control_decided_total, 4)
                    if control_decided_total else None),
                "false_positive_rate_over_all_pairs": (
                    round(control_false_alarms / control_total, 4)
                    if control_total else None),
            },
        },
        "pair_level_outcomes_mutually_exclusive": dict(pair_breakdown),
        "macro_f1_four_types": macro_f1,
        "control_target_false_positive_rate": (
            round(total_fp / total_pairs, 4) if total_pairs else None
        ),
        "control_target_false_positive_rate_over_decided_controls": (
            round(total_fp / (total_tn + total_fp), 4)
            if (total_tn + total_fp) else None
        ),
        "target_field_unknown_rate": (
            round((total_variant_unknown + total_control_unknown)
                  / all_side_checks, 4)
            if all_side_checks else None
        ),
        "variant_unknown_rate": (
            round(total_variant_unknown / total_pairs, 4) if total_pairs else None
        ),
        "control_unknown_rate": (
            round(total_control_unknown / total_pairs, 4) if total_pairs else None
        ),
        "variant_coverage": (
            round((total_tp + total_variant_negative_wrong) / total_pairs, 4)
            if total_pairs else None
        ),
        "control_coverage": (
            round(control_decided_total / total_pairs, 4) if total_pairs else None
        ),
        "pair_success_rate": (
            round(total_pair_ok / total_pairs, 4) if total_pairs else None
        ),
        "pair_success_count": total_pair_ok,
        "pair_success_denominator": total_pairs,
        "explicit_denominators": {
            "variant_positive_tp_denominator": "all scored variant checks",
            "variant_failure_fn_denominator": "all scored variant checks",
            "recall_includes_unknown_as_fn": True,
            "control_tnr_denominator": "decided controls (TN+FP) only",
            "control_unknown_denominator": "all scored control checks",
            "pair_success_denominator": "all paired variant/control checks",
            "unknown_is_not_a_compliant_prediction": True,
            "all_side_checks_denominator_for_overall_unknown_rate": (
                "all four target-type checks across both sides"),
        },
        "uses_expected_only_for_evaluation_grouping": True,
        "does_not_mutate_predictions": True,
    }


# ---------------------------------------------------------------------------
# Control diagnostics and fallback transitions
# ---------------------------------------------------------------------------


def control_model_self_consistency_diagnostic(
    checks: Mapping[str, Any]
) -> dict[str, Any]:
    """Model-internal diagnostic, NOT an independent compliance label.

    The control outcome is produced by the same checkers under evaluation.
    It therefore cannot serve as an independent global-compliance target and
    must not be used to choose a per-method evaluation subset.
    """
    violated: list[str] = []
    unknown: list[str] = []
    all_clear: list[str] = []
    for target in EXTENDED_TYPES:
        check = checks.get(target) or {}
        status = check.get("status")
        if status == "not_applicable":
            all_clear.append(target)
            continue
        if check.get("violation") is True:
            violated.append(target)
        elif check.get("observable") is True and check.get("violation") is False:
            all_clear.append(target)
        else:
            unknown.append(target)
    if violated:
        status = "model_reports_other_field_positive"
    elif unknown:
        status = "model_undetermined"
    else:
        status = "model_internal_all_clear"
    return {
        "status": status,
        "all_clear_types": all_clear,
        "violated_types": violated,
        "unknown_types": unknown,
        "diagnostic_only": True,
        "independent_validation": False,
        "not_a_global_compliance_label": True,
        "used_to_select_evaluation_subset": False,
        "definition": (
            "same-checker diagnostic over the four extended checks; it is not an "
            "independent global-compliance Gold label and is never used to "
            "filter controls out of the cross-method comparison"
        ),
    }


def fixed_control_scope(control_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the full fixed control scope and model diagnostics.

    The evaluation subset is all frozen controls for every method.  The
    diagnostic status is reported for transparency but never used to choose a
    different subset per method.
    """
    diagnostics = {
        row["item_id"]: control_model_self_consistency_diagnostic(
            row.get("checks") or {})
        for row in control_rows
    }
    counts: dict[str, int] = defaultdict(int)
    for info in diagnostics.values():
        counts[info["status"]] += 1
    return {
        "schema_version": "s3_fixed_control_scope@1.0.0",
        "evaluation_subset_policy": (
            "all frozen target-field controls are kept for every method; no "
            "method output is used to select a different test subset"),
        "control_item_ids": [row["item_id"] for row in control_rows],
        "control_count": len(control_rows),
        "diagnostic_status_by_item": diagnostics,
        "diagnostic_status_counts": dict(counts),
        "diagnostic_only": True,
        "independent_global_compliance_labels_available": False,
        "used_to_select_evaluation_subset": False,
    }


def _transition_class(row: Mapping[str, Any], target: str) -> str:
    outcome = _outcome(row, target)
    if outcome == "positive":
        return "determined_positive"
    if outcome == "negative":
        return "determined_negative"
    status = ((row.get("checks") or {}).get(target) or {}).get("status")
    return "ambiguous" if status == "ambiguous" else "unknown"


def fallback_transition_metrics(before_rows: Sequence[Mapping[str, Any]],
                                after_rows: Sequence[Mapping[str, Any]],
                                expected_by_item: Mapping[str, str]
                                ) -> dict[str, Any]:
    """Per-side (item_id, side) transition counts.

    Correct/wrong is side-specific:

    * variant target field: a positive determination is correct, an observable
      negative determination is wrong (observed miss/false negative);
    * control target field: a negative determination is correct (true
      negative), an observable positive determination is wrong (false alarm).

    Unknown/ambiguous objects that never resolve are reported separately; they
    are not merged into the opposite side's counters.
    """
    before = {(row.get("item_id"), row.get("side")): row for row in before_rows}
    after = {(row.get("item_id"), row.get("side")): row for row in after_rows}
    result: dict[str, Any] = {
        "schema_version": "s3_fallback_transition_metrics@2.0.0",
        "object_key": ["item_id", "side"],
        "variant": defaultdict(int),
        "control": defaultdict(int),
        "transitions": [],
        "missing_before_keys": [],
        "missing_after_keys": [],
        "target_field_by_item": dict(expected_by_item),
    }
    for key in sorted(set(before) | set(after), key=lambda value: (str(value[0]), str(value[1]))):
        item_id, side = key
        before_row = before.get(key)
        after_row = after.get(key)
        if before_row is None:
            result["missing_before_keys"].append([item_id, side])
            continue
        if after_row is None:
            result["missing_after_keys"].append([item_id, side])
            continue
        target = expected_by_item.get(str(item_id))
        if not target:
            continue
        before_class = _transition_class(before_row, target)
        after_class = _transition_class(after_row, target)
        side_bucket = result[side]
        if side_bucket is None:
            continue
        if before_class in {"unknown", "ambiguous"} and after_class in {
                "determined_positive", "determined_negative"}:
            if side == "variant":
                correct = after_class == "determined_positive"
            elif side == "control":
                correct = after_class == "determined_negative"
            else:
                correct = False
            transition_key = f"{before_class}_to_{'correct' if correct else 'wrong'}"
            side_bucket[transition_key] += 1
            side_bucket["resolved"] += 1
            result["transitions"].append({
                "item_id": item_id,
                "side": side,
                "target": target,
                "before": before_class,
                "after": after_class,
                "correct_for_side": correct,
            })
        elif before_class in {"unknown", "ambiguous"}:
            side_bucket[f"still_{before_class}"] += 1
            side_bucket["still_undetermined"] += 1
        else:
            side_bucket["already_determined_unchanged"] += 1
            if after_class != before_class:
                side_bucket["determined_but_changed_verdict"] += 1
        side_bucket["total_objects"] += 1
    for side_name in ("variant", "control"):
        result[side_name] = dict(result[side_name])
    return result


__all__ = [
    "REVISION",
    "EVALUATOR_VERSION",
    "REUSED_DETERMINISTIC_REVISION",
    "anonymize_fallback_payload",
    "build_fallback_pack",
    "evaluate_target_paired",
    "control_model_self_consistency_diagnostic",
    "fixed_control_scope",
    "fallback_transition_metrics",
    "evaluate_variant_binary",
    "evaluate_unified_objects",
    "unified_objects_legacy",
    "audit_composite_collisions",
    "input_identity",
]

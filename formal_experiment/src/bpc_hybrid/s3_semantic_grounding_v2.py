# -*- coding: utf-8 -*-
"""Stage 3 semantic-grounding revision v2.

This revision keeps the deterministic scorer of ``s3_semantic_grounding_v1``
unchanged and repairs the evaluation protocol around it:

* true input non-identifiability is defined on the composite model-visible
  identity (canonical Rule Input hash + canonical Process Input hash), not on
  BPMN bytes alone;
* target-paired causal evaluation scores only the mutated target field;
* controls are assigned an offline global-compliance status derived from the
  four structural checks, without reading Gold or expected labels;
* fallback candidates are locked to deterministic semantic ambiguity and are
  serialized in an anonymized, Gold-blind payload.

No real LLM/API call is made by this module.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL
from bpc_hybrid.s3_semantic_grounding_v1 import (  # noqa: E402
    ACTION_STATUS_AMBIGUOUS,
    ACTION_STATUS_RESOLVED,
    ACTION_STATUS_UNRESOLVED,
    VIOLATION_PRIORITY,
    _element_by_id,
    _graph,
    _local,
    _node_maps,
    collect_condition_surface,
    collect_constraint_surface,
    collect_exception_surface,
    decide,
    fold_whitespace,
    ground_action,
    normalize_text,
)

REVISION = "s3_semantic_grounding_v2"
EVALUATOR_VERSION = "s3_semantic_grounding_v2_evaluator@1.0.0"
COMPOSITE_IDENTITY_SCHEMA = "s3_input_identity@1.0.0"
FALLBACK_PACK_SCHEMA = "s3_semantic_grounding_fallback_candidate_pack@1.0.0"

CONTROL_GLOBAL_VERIFIED = "verified_compliant"
CONTROL_GLOBAL_VIOLATED = "violated_other_field"
CONTROL_GLOBAL_UNKNOWN = "unknown"

TRIGGER_ACTION_AMBIGUOUS = "action_grounding_ambiguous"
TRIGGER_ACTION_UNRESOLVED = "action_grounding_unresolved"
TRIGGER_CONDITION_AMBIGUOUS = "condition_semantic_ambiguous"
TRIGGER_CONSTRAINT_UNSUPPORTED = "unsupported_abstract_constraint"
TRIGGER_CONSTRAINT_AMBIGUOUS = "constraint_semantic_ambiguous"
TRIGGER_CONSTRAINT_ACTION_AMBIGUOUS = "constraint_evidence_action_grounding_ambiguous"
TRIGGER_EXCEPTION_HANDLER_AMBIGUOUS = "exception_handler_semantic_ambiguous"
TRIGGER_EXCEPTION_SEMANTIC_AMBIGUOUS = "exception_semantic_ambiguous"
TRIGGER_OTHER = "other_documented_semantic_ambiguity"

CANONICAL_RULE_KEYS = (
    "rule_id",
    "sentence_idx",
    "modality",
    "actor",
    "action",
    "condition",
    "constraint",
    "exception",
)


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_rule_input(rule_view: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical model-visible Rule Input.

    Expected labels, mutation metadata and target-field hints are never read
    here even if they happen to be present in the source mapping.
    """
    return {key: rule_view.get(key) for key in CANONICAL_RULE_KEYS}


def canonical_process_input(record: Mapping[str, Any], xml_root: Any) -> dict[str, Any]:
    """Canonical model-visible Process Input.

    The canonical record omits source-path/provenance fields.  The raw XML
    surface is retained as a deterministic tag/attribute/text sequence because
    the deterministic checks consume boundary events, annotations, data
    objects, timers, error/escalation definitions and associations from the
    raw XML.
    """
    record_subset = {
        "process_id": record.get("process_id"),
        "pools": record.get("pools", []),
        "lanes": record.get("lanes", []),
        "activities": record.get("activities", []),
        "events": record.get("events", []),
        "gateways": record.get("gateways", []),
        "sequence_flows": record.get("sequence_flows", []),
        "control_flow": record.get("control_flow", {}),
    }
    xml_evidence = []
    for element in xml_root.iter():
        attrs = {str(key): str(value) for key, value in sorted(element.attrib.items())}
        text = fold_whitespace("".join(element.itertext()))
        xml_evidence.append([_local(element.tag), attrs, text])
    return {
        "schema": COMPOSITE_IDENTITY_SCHEMA,
        "record": record_subset,
        "xml_evidence": xml_evidence,
    }


def input_identity(rule_view: Mapping[str, Any], record: Mapping[str, Any],
                   xml_root: Any, bpmn_sha256: str | None = None) -> dict[str, Any]:
    rule_input = canonical_rule_input(rule_view)
    process_input = canonical_process_input(record, xml_root)
    return {
        "canonical_rule_input": rule_input,
        "canonical_process_input": process_input,
        "canonical_rule_input_hash": json_sha256(rule_input),
        "canonical_process_input_hash": json_sha256(process_input),
        "bpmn_sha256": bpmn_sha256,
    }


def _collision_groups(rows: Sequence[Mapping[str, Any]], key_fields: Sequence[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field) for field in key_fields)
        grouped[key].append(row)
    return [
        {
            "group_key": list(key),
            "members": [
                {
                    "item_id": row.get("item_id"),
                    "side": row.get("side"),
                    "expected_label": row.get("expected_label"),
                    "canonical_rule_input_hash": row.get("canonical_rule_input_hash"),
                    "canonical_process_input_hash": row.get("canonical_process_input_hash"),
                    "bpmn_sha256": row.get("bpmn_sha256"),
                }
                for row in members
            ],
        }
        for key, members in grouped.items()
        if len(members) > 1
    ]


def _true_collision_groups(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups = _collision_groups(rows, ("canonical_rule_input_hash",
                                      "canonical_process_input_hash"))
    return [group for group in groups
            if len({member["expected_label"] for member in group["members"]}) > 1]


def _old_bpmn_collision_groups(rows: Sequence[Mapping[str, Any]],
                               only_variants: bool = True) -> list[dict[str, Any]]:
    selected = [row for row in rows
                if not only_variants or row.get("side") == "variant"]
    groups = _collision_groups(selected, ("bpmn_sha256",))
    return [group for group in groups
            if len({member["expected_label"] for member in group["members"]}) > 1]


def audit_composite_collisions(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Correct v1 collision audit.

    True collision = identical canonical Rule Input + identical canonical
    Process Input + different expected labels.  BPMN-only groups are retained
    as the historical over-estimate for direct comparison.
    """
    true_groups = _true_collision_groups(rows)
    old_variant_groups = _old_bpmn_collision_groups(rows, only_variants=True)
    old_all_groups = _old_bpmn_collision_groups(rows, only_variants=False)
    true_items = {member["item_id"] for group in true_groups
                  for member in group["members"]}
    old_variant_items = {member["item_id"] for group in old_variant_groups
                         for member in group["members"]}
    old_all_items = {member["item_id"] for group in old_all_groups
                     for member in group["members"]}
    return {
        "schema_version": "s3_composite_input_identifiability@2.0.0",
        "identity_definition": (
            "canonical_rule_input_hash (model-visible Rule Input) + "
            "canonical_process_input_hash (model-visible Process Record/XML) + "
            "different expected labels"
        ),
        "true_collision_group_count": len(true_groups),
        "true_collision_item_count": len(true_items),
        "true_collision_groups": true_groups,
        "old_bpmn_only_variant_collision_group_count": len(old_variant_groups),
        "old_bpmn_only_variant_item_count": len(old_variant_items),
        "old_bpmn_only_all_side_collision_group_count": len(old_all_groups),
        "old_bpmn_only_all_side_item_count": len(old_all_items),
        "old_audit_overestimate_reason": (
            "The v1 audit grouped only by variant BPMN bytes.  The Stage 3 "
            "input also contains the Rule Input; two byte-identical BPMN files "
            "with different model-visible rule fields are distinguishable and "
            "therefore are not true input collisions.  The v1 audit also "
            "counted only the variant scope, while the corrected audit checks "
            "both variant and control side objects and requires different "
            "expected labels only after the identity grouping is fixed."
        ),
        "no_expected_label_in_identity": True,
    }


# ---------------------------------------------------------------------------
# corrected evaluations
# ---------------------------------------------------------------------------


def _p_r_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4)}


def _outcome(row: Mapping[str, Any], target_type: str) -> str:
    check = (row.get("checks") or {}).get(target_type) or {}
    if check.get("violation") is True:
        return "positive"
    if check.get("observable") is True and check.get("violation") is False:
        return "negative"
    return "unknown"


def evaluate_target_paired(variant_rows: Sequence[Mapping[str, Any]],
                           control_rows: Sequence[Mapping[str, Any]],
                           expected_by_item: Mapping[str, str]) -> dict[str, Any]:
    """Target-paired causal evaluation.

    For each pair only ``checks[target_type]`` is consumed.  The expected
    target type is used exclusively after predictions/checks are fixed, for
    grouping and metric accounting; it is never passed to the scorer.
    """
    controls = {row["item_id"]: row for row in control_rows}
    per_type: dict[str, Any] = {}
    total_tp = total_fp = total_fn = total_tn = total_unknown = 0
    total_variant_unknown = total_control_unknown = 0
    total_pairs = 0
    total_pair_ok = 0
    for target in EXTENDED_TYPES:
        tp = fn = variant_unknown = 0
        tn = fp = control_unknown = 0
        pair_ok = 0
        pair_count = 0
        for variant in variant_rows:
            if variant["item_id"] not in expected_by_item:
                continue
            if expected_by_item[variant["item_id"]] != target:
                continue
            control = controls[variant["item_id"]]
            variant_outcome = _outcome(variant, target)
            control_outcome = _outcome(control, target)
            pair_count += 1
            if variant_outcome == "positive":
                tp += 1
            elif variant_outcome == "unknown":
                fn += 1
                variant_unknown += 1
            else:
                fn += 1
            if control_outcome == "negative":
                tn += 1
            elif control_outcome == "positive":
                fp += 1
            else:
                control_unknown += 1
            if variant_outcome == "positive" and control_outcome == "negative":
                pair_ok += 1
        metrics = _p_r_f1(tp, fp, fn)
        tpr = tp / (tp + fn) if (tp + fn) else 0.0
        tnr = tn / (tn + fp) if (tn + fp) else 0.0
        balanced = (tpr + tnr) / 2 if ((tp + fn) and (tn + fp)) else None
        per_type[target] = {
            "pairs": pair_count,
            "variant": {"TP": tp, "FN": fn, "unknown": variant_unknown},
            "control": {"TN": tn, "FP": fp, "unknown": control_unknown},
            **metrics,
            "balanced_accuracy": round(balanced, 4) if balanced is not None else None,
            "pair_success": pair_ok,
            "pair_success_rate": round(pair_ok / pair_count, 4) if pair_count else None,
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn
        total_tn += tn
        total_variant_unknown += variant_unknown
        total_control_unknown += control_unknown
        total_unknown += variant_unknown + control_unknown
        total_pairs += pair_count
        total_pair_ok += pair_ok
    macro_f1 = round(
        sum(per_type[t]["f1"] for t in EXTENDED_TYPES) / len(EXTENDED_TYPES), 4
    )
    return {
        "schema_version": "s3_target_paired_evaluator@2.0.0",
        "evaluation_kind": "target_paired_causal",
        "primary": True,
        "total_pairs": total_pairs,
        "per_type": per_type,
        "macro_f1_four_types": macro_f1,
        "control_target_false_positive_rate": round(
            total_fp / total_pairs, 4) if total_pairs else None,
        "target_field_unknown_rate": round(
            total_unknown / (2 * total_pairs), 4) if total_pairs else None,
        "pair_success_rate": round(total_pair_ok / total_pairs, 4) if total_pairs else None,
        "pair_success_count": total_pair_ok,
        "variant_unknown_count": total_variant_unknown,
        "control_unknown_count": total_control_unknown,
        "uses_expected_only_for_evaluation_grouping": True,
        "does_not_mutate_predictions": True,
    }


def evaluate_variant_binary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    per_type = {t: {"tp": 0, "fp": 0, "fn": 0} for t in EXTENDED_TYPES}
    for row in rows:
        expected = row.get("expected_label")
        for target in EXTENDED_TYPES:
            check = (row.get("checks") or {}).get(target) or {}
            detected = check.get("violation") is True
            if expected == target and detected:
                per_type[target]["tp"] += 1
            elif expected == target:
                per_type[target]["fn"] += 1
            elif detected:
                per_type[target]["fp"] += 1
    return {
        "per_type": {
            target: {
                "support": per_type[target]["tp"] + per_type[target]["fn"],
                **_p_r_f1(per_type[target]["tp"], per_type[target]["fp"],
                          per_type[target]["fn"]),
            }
            for target in EXTENDED_TYPES
        },
        "macro_f1_four_types": round(
            sum(_p_r_f1(per_type[t]["tp"], per_type[t]["fp"], per_type[t]["fn"])["f1"]
                for t in EXTENDED_TYPES) / len(EXTENDED_TYPES), 4),
    }


def evaluate_unified_objects(objects: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    labels = [NONE_LABEL] + list(EXTENDED_TYPES)
    per_class = {label: {"tp": 0, "fp": 0, "fn": 0} for label in labels}
    correct = 0
    for obj in objects:
        gold = obj["gold"]
        pred = obj.get("prediction")
        if pred == gold:
            correct += 1
            per_class[gold]["tp"] += 1
        else:
            per_class[gold]["fn"] += 1
            if pred in per_class:
                per_class[pred]["fp"] += 1
    per_class_results = {
        label: {
            "support": per_class[label]["tp"] + per_class[label]["fn"],
            **_p_r_f1(per_class[label]["tp"], per_class[label]["fp"],
                      per_class[label]["fn"]),
        }
        for label in labels
    }
    return {
        "schema_version": "s3_unified_evaluator@2.0.0",
        "total_objects": len(objects),
        "control_objects": sum(1 for obj in objects if obj.get("gold") == NONE_LABEL),
        "variant_objects": sum(1 for obj in objects if obj.get("gold") in EXTENDED_TYPES),
        "five_class_accuracy": round(correct / len(objects), 4) if objects else None,
        "per_class": per_class_results,
        "macro_f1_four_violation_types": round(
            sum(per_class_results[t]["f1"] for t in EXTENDED_TYPES)
            / len(EXTENDED_TYPES), 4),
        "macro_f1_five_classes": round(
            sum(per_class_results[label]["f1"] for label in labels)
            / len(labels), 4),
        "abstentions": sum(1 for obj in objects if obj.get("prediction") is None),
        "denominator_policy": (
            "None is an abstention and counts as an error for the Gold class; "
            "it is never counted as a compliant or violating prediction."
        ),
    }


def control_global_compliance_status(checks: Mapping[str, Any]) -> dict[str, Any]:
    """Offline global-control status without expected labels.

    A control is ``verified_compliant`` only when every applicable structural
    check reports a clean negative (or is not applicable).  A positive check
    makes it ``violated_other_field``; any unknown/ambiguous check makes it
    ``unknown``.
    """
    violated: list[str] = []
    unknown: list[str] = []
    clean: list[str] = []
    for target in EXTENDED_TYPES:
        check = checks.get(target) or {}
        status = check.get("status")
        if status == "not_applicable":
            clean.append(target)
            continue
        if check.get("violation") is True:
            violated.append(target)
        elif check.get("observable") is True and check.get("violation") is False:
            clean.append(target)
        else:
            unknown.append(target)
    if violated:
        status = CONTROL_GLOBAL_VIOLATED
    elif unknown:
        status = CONTROL_GLOBAL_UNKNOWN
    else:
        status = CONTROL_GLOBAL_VERIFIED
    return {
        "status": status,
        "clean_types": clean,
        "violated_types": violated,
        "unknown_types": unknown,
        "reads_expected_label": False,
        "definition": (
            "all applicable checks negative/not_applicable => verified_compliant; "
            "any positive check => violated_other_field; otherwise unknown"
        ),
    }


def build_clean_control_set(control_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    statuses = {}
    for row in control_rows:
        statuses[row["item_id"]] = control_global_compliance_status(row.get("checks") or {})
    counts: dict[str, int] = defaultdict(int)
    for info in statuses.values():
        counts[info["status"]] += 1
    return {
        "control_status_by_item": statuses,
        "counts": dict(counts),
        "verified_compliant_item_ids": sorted(
            item_id for item_id, info in statuses.items()
            if info["status"] == CONTROL_GLOBAL_VERIFIED
        ),
        "violated_other_field_item_ids": sorted(
            item_id for item_id, info in statuses.items()
            if info["status"] == CONTROL_GLOBAL_VIOLATED
        ),
        "unknown_item_ids": sorted(
            item_id for item_id, info in statuses.items()
            if info["status"] == CONTROL_GLOBAL_UNKNOWN
        ),
        "reads_expected_label": False,
    }


def unified_objects_legacy(variant_rows: Sequence[Mapping[str, Any]],
                           control_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    objects = [
        {"item_id": row["item_id"], "gold": row.get("expected_label"),
         "prediction": row.get("predicted_violation_type")}
        for row in variant_rows
    ]
    objects += [
        {"item_id": row["item_id"], "gold": NONE_LABEL,
         "prediction": row.get("predicted_violation_type")}
        for row in control_rows
    ]
    return objects


def unified_objects_clean(variant_rows: Sequence[Mapping[str, Any]],
                          control_rows: Sequence[Mapping[str, Any]],
                          clean_status: Mapping[str, Any]) -> list[dict[str, Any]]:
    verified = set(clean_status.get("verified_compliant_item_ids", []))
    objects = [
        {"item_id": row["item_id"], "gold": row.get("expected_label"),
         "prediction": row.get("predicted_violation_type")}
        for row in variant_rows
    ]
    objects += [
        {"item_id": row["item_id"], "gold": NONE_LABEL,
         "prediction": row.get("predicted_violation_type")}
        for row in control_rows if row["item_id"] in verified
    ]
    return objects


# ---------------------------------------------------------------------------
# compact local context and fallback candidate pack
# ---------------------------------------------------------------------------


def build_compact_local_context(record: Mapping[str, Any], xml_root: Any,
                                ground: Mapping[str, Any], checks: Mapping[str, Any],
                                max_nodes: int = 60,
                                max_flows: int = 80) -> dict[str, Any]:
    candidates = list(ground.get("candidates") or [])[:5]
    candidate_ids = [c["activity_id"] for c in candidates if c.get("activity_id")]
    node_maps = _node_maps(record)
    successors, predecessors = _graph(record)
    node_ids: set[str] = set()
    flow_ids: set[str] = set()
    for activity_id in candidate_ids:
        node_ids.add(activity_id)
        for flow in predecessors.get(activity_id, []):
            flow_ids.add(str(flow.get("id")))
            node_ids.add(str(flow.get("source_ref")))
        for flow in successors.get(activity_id, []):
            flow_ids.add(str(flow.get("id")))
            node_ids.add(str(flow.get("target_ref")))
    for node_id in list(node_ids):
        if len(node_ids) >= max_nodes:
            break
        for flow in list(successors.get(node_id, []))[:6]:
            flow_ids.add(str(flow.get("id")))
            node_ids.add(str(flow.get("target_ref")))
        for flow in list(predecessors.get(node_id, []))[:6]:
            flow_ids.add(str(flow.get("id")))
            node_ids.add(str(flow.get("source_ref")))
    selected_nodes = sorted(node_ids)[:max_nodes]
    selected_flows = sorted(flow_ids)[:max_flows]
    flows = []
    for flow_id in selected_flows:
        for flow in record.get("sequence_flows", []):
            if str(flow.get("id")) == flow_id:
                flows.append({
                    "id": str(flow.get("id")),
                    "name": fold_whitespace(flow.get("name")),
                    "source_ref": str(flow.get("source_ref")),
                    "target_ref": str(flow.get("target_ref")),
                    "condition_expression": fold_whitespace(flow.get("condition_expression")),
                })
                break
    nodes = []
    for node_id in selected_nodes:
        node = node_maps.get(node_id)
        if node:
            nodes.append({"id": node_id, "kind": node["kind"],
                          "label": node["name"]})
    condition_evidence = []
    for activity_id in candidate_ids[:5]:
        surface = collect_condition_surface(record, activity_id)
        condition_evidence.extend(surface["direct_evidence"])
        condition_evidence.extend(surface["weak_context"])
    try:
        constraint_surface = collect_constraint_surface(record, xml_root, candidate_ids)
    except Exception:
        constraint_surface = {"bound": [], "unbound": []}
    try:
        exception_surface = collect_exception_surface(record, xml_root, candidate_ids)
    except Exception:
        exception_surface = {"handler_candidates": []}
    evidence_ids: set[str] = set()
    for item in condition_evidence:
        if item.get("id"):
            evidence_ids.add(str(item["id"]))
    for item in constraint_surface.get("bound", []) + constraint_surface.get("unbound", []):
        if item.get("id"):
            evidence_ids.add(str(item["id"]))
    for item in exception_surface.get("handler_candidates", []):
        if item.get("id"):
            evidence_ids.add(str(item["id"]))
    return {
        "candidate_activities": [
            {
                "activity_id": c.get("activity_id"),
                "label": c.get("label"),
                "owners": c.get("owners") or [],
                "similarity": c.get("similarity"),
                "lexical_coverage": c.get("lexical_coverage"),
            }
            for c in candidates
        ],
        "nodes": nodes,
        "sequence_flows": flows,
        "condition_evidence": condition_evidence[:20],
        "constraint_bound_evidence": list(constraint_surface.get("bound", []))[:20],
        "constraint_unbound_evidence": list(constraint_surface.get("unbound", []))[:20],
        "exception_handler_candidates": list(exception_surface.get("handler_candidates", []))[:20],
        "evidence_ids": sorted(evidence_ids),
    }

def _dedup_triggers(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def fallback_triggers(row: Mapping[str, Any]) -> list[str]:
    """Return the documented semantic ambiguity triggers for one side object."""
    triggers: list[str] = []
    checks = row.get("checks") or {}
    applicable_targets = [
        target for target in EXTENDED_TYPES
        if (checks.get(target) or {}).get("status") != "not_applicable"
    ]
    ground = row.get("action_grounding") or {}
    action_status = ground.get("status")
    action_needed = bool(applicable_targets)
    if action_needed:
        if action_status == ACTION_STATUS_UNRESOLVED:
            triggers.append(TRIGGER_ACTION_UNRESOLVED)
        elif action_status == ACTION_STATUS_AMBIGUOUS:
            triggers.append(TRIGGER_ACTION_AMBIGUOUS)
    for target in EXTENDED_TYPES:
        check = checks.get(target) or {}
        status = check.get("status")
        reason = str(check.get("reason") or "")
        if status == "not_applicable":
            continue
        if check.get("violation") is True or check.get("violation") is False:
            continue
        if target == "prohibited_action_present":
            if action_status == ACTION_STATUS_UNRESOLVED:
                triggers.append(TRIGGER_ACTION_UNRESOLVED)
            else:
                triggers.append(TRIGGER_ACTION_AMBIGUOUS)
        elif target == "required_condition_not_enforced":
            triggers.append(TRIGGER_CONDITION_AMBIGUOUS)
        elif target == "constraint_violated":
            if reason == "unsupported_abstract_constraint_kind":
                triggers.append(TRIGGER_CONSTRAINT_UNSUPPORTED)
            elif reason == "numeric_time_evidence_found_but_action_grounding_ambiguous":
                triggers.append(TRIGGER_CONSTRAINT_ACTION_AMBIGUOUS)
            elif reason == "unbound_global_constraint_evidence_requires_semantic_grounding":
                triggers.append(TRIGGER_CONSTRAINT_AMBIGUOUS)
            else:
                triggers.append(TRIGGER_OTHER)
        elif target == "exception_not_handled":
            if reason == "dedicated_handler_candidate_exists_but_semantics_ambiguous":
                triggers.append(TRIGGER_EXCEPTION_HANDLER_AMBIGUOUS)
            elif reason in {"action_grounding_unresolved", "action_grounding_ambiguous"}:
                triggers.append(TRIGGER_ACTION_UNRESOLVED
                                if reason == "action_grounding_unresolved"
                                else TRIGGER_ACTION_AMBIGUOUS)
            else:
                triggers.append(TRIGGER_EXCEPTION_SEMANTIC_AMBIGUOUS)
    return _dedup_triggers(triggers)


_ID_KEYS = {
    "id", "activity_id", "candidate_activity_ids", "evidence_ids",
    "source_ref", "target_ref", "source_id", "target_id", "flow_id",
    "boundary_event_id", "handler_task_id", "annotation_id", "association_id",
    "data_object_id", "event_id", "attached_to", "bound_activity_id",
    "owner", "handler_of", "branch_target_ids",
}
_FORBIDDEN_ID_TERMS = set(EXTENDED_TYPES) | {"syn_v2_", "synthetic", "control", "variant"}


def _walk_collect_ids(value: Any, out: set[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in _ID_KEYS:
                if isinstance(item, str):
                    out.add(item)
                elif isinstance(item, list):
                    out.update(str(v) for v in item if isinstance(v, (str, int)))
            else:
                _walk_collect_ids(item, out)
    elif isinstance(value, list):
        for item in value:
            _walk_collect_ids(item, out)


def _scrub_string(value: str) -> str:
    text = value
    for term in _FORBIDDEN_ID_TERMS:
        text = text.replace(term, "anonymous")
    return text


def _anonymize_deep(value: Any, id_map: Mapping[str, str]) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _anonymize_deep(item, id_map)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_anonymize_deep(item, id_map) for item in value]
    if isinstance(value, str):
        if value in id_map:
            return id_map[value]
        return _scrub_string(value)
    return value


def anonymize_fallback_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    ids: set[str] = set()
    _walk_collect_ids(payload, ids)
    id_map = {
        original: f"E{index:04d}"
        for index, original in enumerate(sorted(ids), start=1)
    }
    return _anonymize_deep(payload, id_map), id_map


def build_fallback_pack(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Freeze the deterministic ambiguity subset with anonymized LLM payloads."""
    items: list[dict[str, Any]] = []
    trigger_counts: dict[str, int] = defaultdict(int)
    side_counts: dict[str, int] = defaultdict(int)
    for source_index, row in enumerate(rows):
        # Deterministic final decisions are frozen and are not sent to the LLM.
        # Only final abstentions (predicted None) are eligible for fallback.
        if row.get("predicted_violation_type") is not None:
            continue
        triggers = fallback_triggers(row)
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
        item = {
            "fallback_item_id": f"fb_v2_{len(items) + 1:04d}",
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
        }
        items.append(item)
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
        "item_count": len(items),
        "side_counts": dict(side_counts),
        "trigger_counts": dict(trigger_counts),
        "items": items,
        "contains_expected_labels": False,
        "llm_payload_excludes_forbidden_fields": True,
    }


def apply_llm_grounding(rows: Sequence[Mapping[str, Any]],
                        results: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Programmatically apply validated LLM grounding to deterministic rows.

    Only checks that were deterministic-unknown/ambiguous can be replaced.
    The final violation type is still generated by ``decide``.
    """
    updated = copy.deepcopy(list(rows))
    status_to_check = {
        "condition": "required_condition_not_enforced",
        "constraint": "constraint_violated",
        "exception": "exception_not_handled",
    }
    violation_by_status = {
        "condition": {"enforced": False, "not_enforced": True},
        "constraint": {"satisfied": False, "violated": True},
        "exception": {"handled": False, "not_handled": True},
    }
    for result in results:
        source_index = result.get("source_index")
        if not isinstance(source_index, int) or source_index < 0 or source_index >= len(updated):
            continue
        if result.get("status") != "resolved":
            continue
        response = result.get("response") or {}
        row = updated[source_index]
        checks = row.setdefault("checks", {})
        action = response.get("action_grounding") or {}
        if action.get("status") == "matched" and action.get("activity_id"):
            row.setdefault("action_grounding", {})["status"] = "resolved_by_llm"
            row["action_grounding"]["activity_id"] = action["activity_id"]
        for key, target in status_to_check.items():
            block = response.get(key) or {}
            status = block.get("status")
            original = checks.get(target) or {}
            if original.get("status") not in {"unknown", "ambiguous", "unresolved"}:
                continue
            if status in violation_by_status[key]:
                checks[target] = {
                    **original,
                    "status": status,
                    "observable": True,
                    "violation": violation_by_status[key][status],
                    "score": 1.0 if violation_by_status[key][status] else 0.0,
                    "reason": f"llm_semantic_grounding:{status}",
                }
            elif status == "not_applicable":
                checks[target] = {
                    **original,
                    "status": "not_applicable",
                    "observable": True,
                    "violation": False,
                    "score": 0.0,
                    "reason": "llm_semantic_grounding:not_applicable",
                }
            elif status == "ambiguous":
                checks[target] = {
                    **original,
                    "status": "ambiguous",
                    "observable": False,
                    "violation": None,
                    "score": None,
                    "reason": "llm_semantic_grounding:ambiguous",
                }
        row["decision"] = decide(checks)
        row["predicted_violation_type"] = row["decision"].get("predicted")
    return updated


def fallback_transition_metrics(before_rows: Sequence[Mapping[str, Any]],
                                after_rows: Sequence[Mapping[str, Any]],
                                expected_by_item: Mapping[str, str]) -> dict[str, Any]:
    """Report unknown->correct/wrong and ambiguous->correct/wrong transitions."""
    before = {row["item_id"]: row for row in before_rows}
    after = {row["item_id"]: row for row in after_rows}
    counts = {
        "unknown_to_correct": 0,
        "unknown_to_wrong": 0,
        "ambiguous_to_correct": 0,
        "ambiguous_to_wrong": 0,
        "unchanged_unknown": 0,
        "unchanged_ambiguous": 0,
    }
    transitions = []
    for item_id, target in expected_by_item.items():
        before_row = before.get(item_id)
        after_row = after.get(item_id)
        if before_row is None or after_row is None:
            continue
        before_check = (before_row.get("checks") or {}).get(target) or {}
        after_check = (after_row.get("checks") or {}).get(target) or {}
        before_status = before_check.get("status")
        after_status = after_check.get("status")
        if before_status not in {"unknown", "ambiguous"}:
            continue
        if after_status not in {"unknown", "ambiguous"} and after_check.get("observable") is True:
            correct = (after_check.get("violation") is True)
            key = f"{before_status}_to_{'correct' if correct else 'wrong'}"
            counts[key] += 1
            transitions.append({"item_id": item_id, "target": target,
                                "before": before_status, "after": after_status,
                                "correct": correct})
        else:
            counts[f"unchanged_{before_status}"] += 1
    return {"counts": counts, "transitions": transitions}


__all__ = [
    "REVISION", "EVALUATOR_VERSION", "COMPOSITE_IDENTITY_SCHEMA",
    "FALLBACK_PACK_SCHEMA", "CANONICAL_RULE_KEYS", "CONTROL_GLOBAL_VERIFIED",
    "CONTROL_GLOBAL_VIOLATED", "CONTROL_GLOBAL_UNKNOWN",
    "canonical_rule_input", "canonical_process_input", "input_identity",
    "audit_composite_collisions", "evaluate_target_paired",
    "evaluate_variant_binary", "evaluate_unified_objects",
    "control_global_compliance_status", "build_clean_control_set",
    "unified_objects_legacy", "unified_objects_clean",
    "build_compact_local_context", "fallback_triggers", "build_fallback_pack",
    "anonymize_fallback_payload", "apply_llm_grounding",
    "fallback_transition_metrics",
]

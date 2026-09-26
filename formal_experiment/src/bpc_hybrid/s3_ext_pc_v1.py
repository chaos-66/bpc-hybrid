# -*- coding: utf-8 -*-
"""Bounded S3.9-EXT-PC-V1 checker.

This module implements only the two v1 semantics frozen for
``s3_ext_pc_v1``:

* ``direct_unconditional_action_prohibition``: a reachable executable
  activity that exactly matches the canonical prohibited action;
* ``necessary_precondition``: ``A only if C``, checked by removing all
  C-enforcing sequence-flow edges and testing whether the target action remains
  reachable from a start node.

It intentionally does not implement conditional prohibition, exception
semantics, constraint arithmetic, full BPMN semantics, or semantic span
extraction.  It consumes already-structured RuleSpecs and Process Records.

The module is standalone and imports only the frozen Stage 1 BPMN parser for
tests/case construction; it does not read Gold, expected labels, pair metadata,
or mutation metadata.
"""

from __future__ import annotations

import re
import unicodedata
from collections import deque
from typing import Any, Iterable, Mapping, Sequence

REL_DIRECT_PROHIBITION = "direct_unconditional_action_prohibition"
REL_NECESSARY_PRECONDITION = "necessary_precondition"
REL_ABSENCE = "absence_of_obligation"
REL_PERMISSION = "permission"
REL_RULE_APPLICABILITY = "rule_applicability"
REL_LEGAL_EFFECT = "legal_effect_or_state"
REL_TRIGGER_OBLIGATION = "trigger_obligation_C_implies_OA"
REL_CONDITIONAL_PROHIBITION = "conditional_action_prohibition"
REL_AMBIGUOUS = "ambiguous"
REL_OTHER = "other"

CHECK_PROHIBITION = "prohibition"
CHECK_NECESSARY_PRECONDITION = "necessary_precondition"

TARGET_PROHIBITION = "prohibited_action_present"
TARGET_NECESSARY_PRECONDITION = "required_condition_not_enforced"

ACTION_CONTRACT_EXACT = "exact_normalized_complete_enumeration"
CONDITION_CONTRACT_EXACT = "exact_canonical_condition_surface_complete"

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(value: Any) -> str:
    """Case/width/whitespace normalization used only for exact matching."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.casefold().strip()
    text = _WHITESPACE_RE.sub(" ", text)
    return text


def normalize_action(value: Any) -> str:
    return normalize_text(value)


def normalize_condition(value: Any) -> str:
    text = normalize_text(value)
    # Accept an explicit ${...} wrapper in a flow conditionExpression while
    # keeping the matching bounded to the canonical surface.
    if text.startswith("${") and text.endswith("}"):
        text = normalize_text(text[2:-1])
    return text


def infer_check_family(relation_type: str | None) -> str:
    if relation_type in {REL_NECESSARY_PRECONDITION, REL_TRIGGER_OBLIGATION}:
        return CHECK_NECESSARY_PRECONDITION
    return CHECK_PROHIBITION


def classify_applicability(rule_spec: Mapping[str, Any], check_family: str) -> dict[str, Any]:
    relation = rule_spec.get("relation_type")
    if check_family == CHECK_PROHIBITION:
        if relation == REL_DIRECT_PROHIBITION:
            return {"applicability": "applicable", "reason": "direct_unconditional_action_prohibition"}
        if relation == REL_CONDITIONAL_PROHIBITION:
            return {"applicability": "unsupported", "reason": "conditional_prohibition_outside_v1"}
        if relation == REL_ABSENCE:
            return {"applicability": "not_applicable", "reason": "absence_of_obligation_not_prohibition"}
        if relation == REL_PERMISSION:
            return {"applicability": "not_applicable", "reason": "permission_not_prohibition"}
        if relation == REL_RULE_APPLICABILITY:
            return {"applicability": "not_applicable", "reason": "rule_applicability_not_process_action_prohibition"}
        if relation == REL_LEGAL_EFFECT:
            return {"applicability": "not_applicable", "reason": "legal_effect_or_state_not_process_action_prohibition"}
        if relation == REL_TRIGGER_OBLIGATION:
            return {"applicability": "not_applicable", "reason": "trigger_obligation_not_prohibition"}
        if relation == REL_NECESSARY_PRECONDITION:
            return {"applicability": "not_applicable", "reason": "necessary_precondition_not_prohibition"}
        if relation == REL_AMBIGUOUS:
            return {"applicability": "unsupported", "reason": "ambiguous_relation_outside_v1"}
        return {"applicability": "unsupported", "reason": "other_relation_outside_v1"}

    # necessary-precondition check target
    if relation == REL_NECESSARY_PRECONDITION:
        return {"applicability": "applicable", "reason": "necessary_precondition_v1"}
    if relation == REL_TRIGGER_OBLIGATION:
        return {"applicability": "not_applicable", "reason": "trigger_obligation_not_necessary_precondition"}
    if relation == REL_DIRECT_PROHIBITION:
        return {"applicability": "not_applicable", "reason": "direct_prohibition_not_necessary_precondition"}
    if relation == REL_ABSENCE:
        return {"applicability": "not_applicable", "reason": "absence_of_obligation_not_necessary_precondition"}
    if relation == REL_PERMISSION:
        return {"applicability": "not_applicable", "reason": "permission_not_necessary_precondition"}
    if relation == REL_RULE_APPLICABILITY:
        return {"applicability": "not_applicable", "reason": "rule_applicability_not_necessary_precondition"}
    if relation == REL_LEGAL_EFFECT:
        return {"applicability": "not_applicable", "reason": "legal_effect_or_state_not_necessary_precondition"}
    if relation == REL_CONDITIONAL_PROHIBITION:
        return {"applicability": "unsupported", "reason": "conditional_prohibition_outside_v1"}
    return {"applicability": "unsupported", "reason": "other_relation_outside_v1"}


def supported_bpmn_fragment(process_record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a bounded-scope decision for the flat XOR/DAG fragment."""

    unsupported: list[str] = []
    control = process_record.get("control_flow") or {}
    if control.get("cycle_detected"):
        unsupported.append("cycle")
    for activity in process_record.get("activities") or []:
        activity_type = activity.get("type")
        if activity_type == "subProcess":
            unsupported.append("subProcess")
        elif activity_type == "callActivity":
            unsupported.append("callActivity")
    for event in process_record.get("events") or []:
        event_type = event.get("type")
        if event_type in {"boundaryEvent", "intermediateCatchEvent", "intermediateThrowEvent"}:
            unsupported.append(str(event_type))
    for gateway in process_record.get("gateways") or []:
        gateway_type = gateway.get("type")
        if gateway_type != "exclusiveGateway":
            unsupported.append(str(gateway_type))
    start_ids = list(control.get("start_event_ids") or [])
    if not start_ids:
        unsupported.append("missing_start_event")
    if unsupported:
        return {
            "supported": False,
            "reason": "unsupported_bpmn_fragment:" + ",".join(sorted(set(unsupported))),
            "unsupported_features": sorted(set(unsupported)),
        }
    return {
        "supported": True,
        "reason": "supported_flat_acyclic_xor_fragment",
        "unsupported_features": [],
    }


def _activity_rows(process_record: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for activity in process_record.get("activities") or []:
        if activity.get("id"):
            rows.append({
                "activity_id": activity["id"],
                "activity_type": activity.get("type"),
                "label": activity.get("name") or "",
                "normalized_label": normalize_action(activity.get("name") or ""),
            })
    return sorted(rows, key=lambda row: row["activity_id"])


def bind_action(
    rule_action: Any,
    process_record: Mapping[str, Any],
    *,
    vocabulary: Sequence[str] | None = None,
    contract: str = ACTION_CONTRACT_EXACT,
) -> dict[str, Any]:
    """Bind a rule action to executable activity nodes by exact normalization."""

    normalized = normalize_action(rule_action)
    if not normalized:
        return {"status": "unresolved", "reason": "empty_rule_action", "normalized_action": normalized, "matches": []}
    vocabulary_normalized: set[str] | None = None
    if vocabulary is not None:
        vocabulary_normalized = {normalize_action(item) for item in vocabulary if normalize_action(item)}
        if normalized not in vocabulary_normalized:
            return {
                "status": "unresolved",
                "reason": "rule_action_not_in_frozen_canonical_vocabulary",
                "normalized_action": normalized,
                "canonical_vocabulary": sorted(vocabulary_normalized),
                "matches": [],
            }
    matches = [row for row in _activity_rows(process_record) if row["normalized_label"] == normalized]
    if not matches:
        if contract == ACTION_CONTRACT_EXACT:
            return {
                "status": "absent_confirmed",
                "reason": "canonical_action_absent_from_complete_enumeration",
                "normalized_action": normalized,
                "canonical_vocabulary": sorted(vocabulary_normalized) if vocabulary_normalized else None,
                "matches": [],
            }
        return {
            "status": "unresolved",
            "reason": "no_matching_executable_activity",
            "normalized_action": normalized,
            "matches": [],
        }
    return {
        "status": "resolved",
        "reason": "exact_normalized_canonical_action_match",
        "normalized_action": normalized,
        "matches": matches,
        "activity_ids": [row["activity_id"] for row in matches],
    }


def bind_condition_edges(
    rule_condition: Any,
    process_record: Mapping[str, Any],
    *,
    contract: str | None = CONDITION_CONTRACT_EXACT,
) -> dict[str, Any]:
    """Bind C to sequence-flow conditionExpression or explicit flow-label guards.

    Gateway names, task labels and annotations are deliberately not inspected
    here; they are allowed as surface text but never as enforcement evidence.
    """

    normalized = normalize_condition(rule_condition)
    if not normalized:
        return {"status": "unresolved", "reason": "empty_rule_condition", "normalized_condition": normalized, "edges": []}
    edges: list[dict[str, Any]] = []
    for flow in process_record.get("sequence_flows") or []:
        candidates: list[tuple[str, str]] = []
        condition_expression = flow.get("condition_expression")
        if condition_expression:
            candidates.append(("condition_expression", str(condition_expression)))
        flow_name = flow.get("name")
        if flow_name:
            candidates.append(("flow_name", str(flow_name)))
        for kind, text in candidates:
            if normalize_condition(text) == normalized:
                edges.append({
                    "edge_id": flow.get("id"),
                    "kind": kind,
                    "text": text,
                    "source_ref": flow.get("source_ref"),
                    "target_ref": flow.get("target_ref"),
                })
    if edges:
        return {
            "status": "resolved",
            "reason": "exact_canonical_condition_guard_edge_match",
            "normalized_condition": normalized,
            "edges": sorted(edges, key=lambda item: (str(item["edge_id"]), item["kind"])),
        }
    if contract == CONDITION_CONTRACT_EXACT:
        return {
            "status": "absent_confirmed",
            "reason": "no_condition_enforcing_edge_matches_complete_canonical_surface",
            "normalized_condition": normalized,
            "edges": [],
        }
    return {
        "status": "unresolved",
        "reason": "condition_binding_unresolved_or_ambiguous",
        "normalized_condition": normalized,
        "edges": [],
    }


def _start_ids(process_record: Mapping[str, Any]) -> list[str]:
    control = process_record.get("control_flow") or {}
    return sorted(str(item) for item in (control.get("start_event_ids") or []))


def _edge_map(process_record: Mapping[str, Any]) -> dict[str, list[tuple[str, str]]]:
    successors: dict[str, list[tuple[str, str]]] = {}
    for flow in process_record.get("sequence_flows") or []:
        source = str(flow.get("source_ref") or "")
        target = str(flow.get("target_ref") or "")
        edge_id = str(flow.get("id") or "")
        if source and target and edge_id:
            successors.setdefault(source, []).append((target, edge_id))
    for source in successors:
        successors[source].sort(key=lambda item: (item[0], item[1]))
    return successors


def reachable_nodes(
    process_record: Mapping[str, Any],
    *,
    start_ids: Iterable[str] | None = None,
    removed_edge_ids: Iterable[str] | None = None,
) -> set[str]:
    starts = list(start_ids) if start_ids is not None else _start_ids(process_record)
    removed = set(removed_edge_ids or ())
    successors = _edge_map(process_record)
    reachable = set(starts)
    queue = deque(sorted(starts))
    while queue:
        node = queue.popleft()
        for target, edge_id in successors.get(node, []):
            if edge_id in removed or target in reachable:
                continue
            reachable.add(target)
            queue.append(target)
    return reachable


def build_evidence_path(
    process_record: Mapping[str, Any],
    target_id: str,
    *,
    removed_edge_ids: Iterable[str] | None = None,
    start_ids: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    starts = list(start_ids) if start_ids is not None else _start_ids(process_record)
    removed = set(removed_edge_ids or ())
    successors = _edge_map(process_record)
    queue: deque[tuple[str, list[str], list[str]]] = deque()
    for start in sorted(starts):
        queue.append((start, [start], []))
    seen = set()
    while queue:
        node, node_path, edge_path = queue.popleft()
        if node == target_id:
            return {
                "start_node_id": node_path[0],
                "node_ids": node_path,
                "edge_ids": edge_path,
                "target_node_id": target_id,
            }
        if node in seen:
            continue
        seen.add(node)
        for child, edge_id in successors.get(node, []):
            if edge_id in removed:
                continue
            queue.append((child, node_path + [child], edge_path + [edge_id]))
    return None


def _base_result(rule_spec: Mapping[str, Any], check_family: str) -> dict[str, Any]:
    if check_family == CHECK_NECESSARY_PRECONDITION:
        target_type = TARGET_NECESSARY_PRECONDITION
        semantic_subtype = "necessary_precondition_bypass_v1"
    else:
        target_type = TARGET_PROHIBITION
        semantic_subtype = (
            "direct_unconditional_action_prohibition"
            if rule_spec.get("relation_type") == REL_DIRECT_PROHIBITION
            else str(rule_spec.get("relation_type"))
        )
    return {
        "check_family": check_family,
        "target_type_legacy": target_type,
        "semantic_subtype": semantic_subtype,
        "relation_type": rule_spec.get("relation_type"),
        "rule_action": rule_spec.get("action"),
        "rule_condition": rule_spec.get("condition"),
    }


def _not_applicable_or_unsupported(rule_spec: Mapping[str, Any], check_family: str,
                                   applicability: Mapping[str, Any]) -> dict[str, Any]:
    result = _base_result(rule_spec, check_family)
    result.update({
        "applicability": applicability["applicability"],
        "decision": None,
        "reason": applicability["reason"],
        "evidence": {},
    })
    return result


def _unknown(rule_spec: Mapping[str, Any], check_family: str, reason: str,
             evidence_mapping: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = _base_result(rule_spec, check_family)
    result.update({
        "applicability": "applicable",
        "decision": "unknown",
        "reason": reason,
        "evidence": dict(evidence_mapping or {}),
    })
    return result


def _decide(rule_spec: Mapping[str, Any], check_family: str, decision: str, reason: str,
            evidence_mapping: Mapping[str, Any]) -> dict[str, Any]:
    result = _base_result(rule_spec, check_family)
    result.update({
        "applicability": "applicable",
        "decision": decision,
        "reason": reason,
        "evidence": dict(evidence_mapping),
    })
    return result


def check_unconditional_prohibition(rule_spec: Mapping[str, Any],
                                    process_record: Mapping[str, Any]) -> dict[str, Any]:
    check_family = CHECK_PROHIBITION
    applicability = classify_applicability(rule_spec, check_family)
    if applicability["applicability"] != "applicable":
        return _not_applicable_or_unsupported(rule_spec, check_family, applicability)

    fragment = supported_bpmn_fragment(process_record)
    if not fragment["supported"]:
        result = _base_result(rule_spec, check_family)
        result.update({
            "applicability": "unsupported",
            "decision": None,
            "reason": fragment["reason"],
            "evidence": {"supported_bpmn_fragment": fragment},
        })
        return result

    action_binding = bind_action(
        rule_spec.get("action"),
        process_record,
        vocabulary=rule_spec.get("canonical_action_vocabulary"),
        contract=rule_spec.get("action_binding_contract") or ACTION_CONTRACT_EXACT,
    )
    if action_binding["status"] == "unresolved":
        return _unknown(rule_spec, check_family, "action_binding_unresolved_or_ambiguous",
                        {"action_binding": action_binding, "supported_bpmn_fragment": fragment})
    if action_binding["status"] == "absent_confirmed":
        return _decide(
            rule_spec, check_family, "satisfied",
            "prohibited_action_absent_under_complete_canonical_enumeration",
            {"action_binding": action_binding, "supported_bpmn_fragment": fragment, "reachable_action_ids": []},
        )

    starts = _start_ids(process_record)
    reachable = reachable_nodes(process_record, start_ids=starts)
    reachable_matches = [row for row in action_binding["matches"] if row["activity_id"] in reachable]
    if reachable_matches:
        target_id = sorted(row["activity_id"] for row in reachable_matches)[0]
        path = build_evidence_path(process_record, target_id, start_ids=starts)
        return _decide(
            rule_spec, check_family, "violation",
            "reachable_executable_prohibited_action_present",
            {
                "action_binding": action_binding,
                "supported_bpmn_fragment": fragment,
                "matched_reachable_activity_ids": sorted(row["activity_id"] for row in reachable_matches),
                "reachable_path": path,
            },
        )

    return _decide(
        rule_spec, check_family, "satisfied",
        "prohibited_action_nodes_unreachable_from_any_start",
        {
            "action_binding": action_binding,
            "supported_bpmn_fragment": fragment,
            "matched_activity_ids": sorted(row["activity_id"] for row in action_binding["matches"]),
            "reachable_action_ids": [],
        },
    )


def check_necessary_precondition(rule_spec: Mapping[str, Any],
                                 process_record: Mapping[str, Any]) -> dict[str, Any]:
    check_family = CHECK_NECESSARY_PRECONDITION
    applicability = classify_applicability(rule_spec, check_family)
    if applicability["applicability"] != "applicable":
        return _not_applicable_or_unsupported(rule_spec, check_family, applicability)

    fragment = supported_bpmn_fragment(process_record)
    if not fragment["supported"]:
        result = _base_result(rule_spec, check_family)
        result.update({
            "applicability": "unsupported",
            "decision": None,
            "reason": fragment["reason"],
            "evidence": {"supported_bpmn_fragment": fragment},
        })
        return result

    action_binding = bind_action(
        rule_spec.get("action"),
        process_record,
        vocabulary=rule_spec.get("canonical_action_vocabulary"),
        contract=rule_spec.get("action_binding_contract") or ACTION_CONTRACT_EXACT,
    )
    if action_binding["status"] == "unresolved":
        return _unknown(rule_spec, check_family, "action_binding_unresolved_or_ambiguous",
                        {"action_binding": action_binding, "supported_bpmn_fragment": fragment})
    if action_binding["status"] == "absent_confirmed":
        return _unknown(
            rule_spec, check_family, "target_action_absent_under_necessary_precondition_v1",
            {"action_binding": action_binding, "supported_bpmn_fragment": fragment},
        )

    starts = _start_ids(process_record)
    original_reachable = reachable_nodes(process_record, start_ids=starts)
    target_matches = action_binding["matches"]
    reachable_targets = [row for row in target_matches if row["activity_id"] in original_reachable]
    if not reachable_targets:
        return _unknown(
            rule_spec, check_family, "target_action_not_reachable_in_original_graph",
            {
                "action_binding": action_binding,
                "supported_bpmn_fragment": fragment,
                "target_action_ids": sorted(row["activity_id"] for row in target_matches),
                "original_reachable_action_ids": [],
            },
        )

    condition_binding = bind_condition_edges(
        rule_spec.get("condition"),
        process_record,
        contract=rule_spec.get("condition_binding_contract") or CONDITION_CONTRACT_EXACT,
    )
    if condition_binding["status"] == "unresolved":
        return _unknown(
            rule_spec, check_family, "condition_binding_unresolved_or_ambiguous",
            {
                "action_binding": action_binding,
                "condition_binding": condition_binding,
                "supported_bpmn_fragment": fragment,
            },
        )

    if condition_binding["status"] == "absent_confirmed":
        removed_edge_ids: list[str] = []
    else:
        removed_edge_ids = sorted({str(edge["edge_id"]) for edge in condition_binding["edges"]})
    reachable_without_c = reachable_nodes(
        process_record,
        start_ids=starts,
        removed_edge_ids=removed_edge_ids,
    )
    bypass_targets = [row for row in reachable_targets if row["activity_id"] in reachable_without_c]
    if bypass_targets:
        target_id = sorted(row["activity_id"] for row in bypass_targets)[0]
        path = build_evidence_path(
            process_record,
            target_id,
            start_ids=starts,
            removed_edge_ids=removed_edge_ids,
        )
        return _decide(
            rule_spec, check_family, "violation",
            "necessary_precondition_bypassed",
            {
                "action_binding": action_binding,
                "condition_binding": condition_binding,
                "supported_bpmn_fragment": fragment,
                "removed_condition_edge_ids": removed_edge_ids,
                "bypass_evidence_path": path,
                "bypass_target_activity_ids": sorted(row["activity_id"] for row in bypass_targets),
            },
        )

    return _decide(
        rule_spec, check_family, "satisfied",
        "necessary_precondition_enforced_across_bounded_graph",
        {
            "action_binding": action_binding,
            "condition_binding": condition_binding,
            "supported_bpmn_fragment": fragment,
            "target_action_ids": sorted(row["activity_id"] for row in reachable_targets),
            "removed_condition_edge_ids": removed_edge_ids,
            "original_action_reachable": True,
            "reachable_target_action_ids_after_removal": [],
            "proof": {
                "method": "remove_E_C_then_reachability",
                "start_node_ids": sorted(starts),
                "all_target_actions_unreachable_after_removal": True,
            },
        },
    )


def check_object(rule_spec: Mapping[str, Any], process_record: Mapping[str, Any]) -> dict[str, Any]:
    check_family = infer_check_family(rule_spec.get("relation_type"))
    if check_family == CHECK_NECESSARY_PRECONDITION:
        return check_necessary_precondition(rule_spec, process_record)
    return check_unconditional_prohibition(rule_spec, process_record)


__all__ = [
    "REL_DIRECT_PROHIBITION",
    "REL_NECESSARY_PRECONDITION",
    "REL_ABSENCE",
    "REL_PERMISSION",
    "REL_RULE_APPLICABILITY",
    "REL_LEGAL_EFFECT",
    "REL_TRIGGER_OBLIGATION",
    "REL_CONDITIONAL_PROHIBITION",
    "REL_AMBIGUOUS",
    "REL_OTHER",
    "CHECK_PROHIBITION",
    "CHECK_NECESSARY_PRECONDITION",
    "TARGET_PROHIBITION",
    "TARGET_NECESSARY_PRECONDITION",
    "normalize_text",
    "normalize_action",
    "normalize_condition",
    "infer_check_family",
    "classify_applicability",
    "supported_bpmn_fragment",
    "bind_action",
    "bind_condition_edges",
    "reachable_nodes",
    "build_evidence_path",
    "check_unconditional_prohibition",
    "check_necessary_precondition",
    "check_object",
]

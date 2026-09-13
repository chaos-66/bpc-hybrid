# -*- coding: utf-8 -*-
"""Stage 3 semantic-grounding revision v4 (field-wise LLM application).

The v3 evaluator remains the accounting layer.  This revision corrects the
consumption of validated LLM responses:

* one ambiguous field no longer discards another resolved field;
* an anonymous activity id is mapped back to the real process node and the
  affected local checks are re-executed on that node;
* resolved field claims require program-side evidence/scope binding before a
  final determination is written; otherwise the deterministic unknown stays;
* the candidate context derives allowed evidence ids from the actually
  visible (truncated) evidence lists.

The final decision remains produced by ``decide`` over program checks.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL
from bpc_hybrid.s3_semantic_grounding_v1 import (
    ACTION_STATUS_AMBIGUOUS,
    ACTION_STATUS_RESOLVED,
    ACTION_STATUS_UNRESOLVED,
    _node_maps,
    _time_values,
    check_condition,
    check_constraint,
    check_exception,
    check_prohibited,
    collect_condition_surface,
    collect_constraint_surface,
    collect_exception_surface,
    decide,
    numeric_upper_bound,
    text_equivalent,
    token_coverage,
)
from bpc_hybrid.s3_semantic_grounding_v2 import fallback_triggers
from bpc_hybrid.s3_semantic_grounding_v3 import (
    FALLBACK_PACK_SCHEMA,
    anonymize_fallback_payload as _v3_anonymize_fallback_payload,
)

REVISION = "s3_semantic_grounding_v4"
EVALUATOR_VERSION = "s3_semantic_grounding_v4_applicator@1.0.0"
BASE_REVISION = "s3_semantic_grounding_v3"

_FIELD_TARGETS = {
    "condition": "required_condition_not_enforced",
    "constraint": "constraint_violated",
    "exception": "exception_not_handled",
}
_TARGET_FIELDS = {value: key for key, value in _FIELD_TARGETS.items()}
_DETERMINATE_FIELD_STATUSES = {
    "enforced", "not_enforced", "satisfied", "violated", "handled", "not_handled",
    "not_applicable",
}


def normalize_llm_status(validated_response: Mapping[str, Any]) -> str:
    """Summarise a validated response without discarding partial progress."""
    field_statuses = [
        (validated_response.get(field) or {}).get("status")
        for field in ("condition", "constraint", "exception")
    ]
    action = validated_response.get("action_grounding") or {}
    if action.get("status") == "matched":
        return "resolved"
    if any(status in _DETERMINATE_FIELD_STATUSES for status in field_statuses):
        return "resolved"
    if any(status == "ambiguous" for status in field_statuses):
        return "ambiguous"
    return "unknown"


def _is_clear(check: Mapping[str, Any] | None) -> bool:
    # ``not_applicable`` is a scope statement, not a substantive compliance
    # determination; an action-resolution re-check may legitimately change
    # applicability (for example after a prohibition action is grounded).
    return bool(check) and check.get("observable") is True \
        and check.get("violation") in (True, False) \
        and check.get("status") != "not_applicable"


def _applicable(check_name: str, status: str, reason: str, *,
                violation: bool, **extra: Any) -> dict[str, Any]:
    return {
        "check": check_name,
        "status": status,
        "observable": True,
        "violation": violation,
        "reason": reason,
        "score": 1.0 if violation else 0.0,
        **extra,
    }


def _node_label(record: Mapping[str, Any], activity_id: str) -> str:
    node = _node_maps(record).get(str(activity_id)) or {}
    return str(node.get("name") or "")


def _candidate_for_id(ground: Mapping[str, Any], activity_id: str) -> dict[str, Any] | None:
    for candidate in list(ground.get("candidates") or []) + list(ground.get("alternatives") or []):
        if str(candidate.get("activity_id")) == str(activity_id):
            return dict(candidate)
    return None


def _resolved_ground(original_ground: Mapping[str, Any], activity_id: str,
                     record: Mapping[str, Any] | None = None) -> dict[str, Any]:
    candidate = _candidate_for_id(original_ground, activity_id)
    if candidate is None:
        candidate = {
            "activity_id": str(activity_id),
            "label": _node_label(record or {}, activity_id),
            "owners": [],
            "similarity": 1.0,
            "lexical_coverage": 1.0,
        }
    return {
        **dict(original_ground),
        "status": ACTION_STATUS_RESOLVED,
        "reason": "llm_activity_mapping_resolved_by_program",
        "activity_id": str(activity_id),
        "candidate_activity_ids": [str(activity_id)],
        "candidates": [candidate],
        "source": "llm_semantic_grounding_then_program_binding",
        "previous_action_grounding": copy.deepcopy(dict(original_ground)),
        "no_forced_resolution": False,
    }


def _recheck_after_action(sentence: Mapping[str, Any], record: Mapping[str, Any],
                          xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "prohibited_action_present": check_prohibited(sentence, ground),
        "required_condition_not_enforced": check_condition(sentence, record, ground),
        "constraint_violated": check_constraint(sentence, record, xml_root, ground),
        "exception_not_handled": check_exception(sentence, record, xml_root, ground),
    }


def _surface_maps(field_name: str, record: Mapping[str, Any], xml_root: Any,
                  candidate_ids: Sequence[str]) -> dict[str, dict[str, Any]]:
    surface: dict[str, dict[str, Any]] = {}
    if field_name == "condition":
        for activity_id in candidate_ids:
            try:
                collected = collect_condition_surface(record, activity_id)
            except Exception:
                continue
            for item in collected.get("direct_evidence", []) + collected.get("weak_context", []):
                if item.get("id"):
                    surface[str(item["id"])] = dict(item)
    elif field_name == "constraint":
        try:
            collected = collect_constraint_surface(record, xml_root, list(candidate_ids))
        except Exception:
            collected = {"bound": [], "unbound": []}
        for item in collected.get("bound", []) + collected.get("unbound", []):
            if item.get("id"):
                surface[str(item["id"])] = dict(item)
    elif field_name == "exception":
        try:
            collected = collect_exception_surface(record, xml_root, list(candidate_ids))
        except Exception:
            collected = {"handler_candidates": []}
        for item in collected.get("handler_candidates", []):
            if item.get("id"):
                surface[str(item["id"])] = dict(item)
    return surface


def _text_supports(rule_text: Any, evidence_text: Any) -> bool:
    rule = str(rule_text or "").strip()
    evidence = str(evidence_text or "").strip()
    if not rule or not evidence:
        return False
    return (
        text_equivalent(rule, evidence)
        or token_coverage(rule, evidence) >= 0.5
        or token_coverage(evidence, rule) >= 0.5
    )


def _program_constraint_decision(rule_text: Any,
                                 evidence_items: Sequence[Mapping[str, Any]]
                                 ) -> str | None:
    bound = numeric_upper_bound(rule_text)
    if bound is None:
        return None
    observations: list[float] = []
    for item in evidence_items:
        for value in _time_values(item.get("text")):
            if value.get("hours") is not None:
                observations.append(float(value["hours"]))
    if not observations:
        return None
    if any(hours > float(bound["hours"]) for hours in observations):
        return "violated"
    if any(hours <= float(bound["hours"]) for hours in observations):
        return "satisfied"
    return None


def _apply_field_evidence(field_name: str, rule_text: Any,
                          block: Mapping[str, Any],
                          evidence_items: Sequence[Mapping[str, Any]],
                          evidence_ids: Sequence[str]) -> dict[str, Any] | None:
    """Return a program-bound check only when the evidence supports it.

    Missing/irrelevant evidence returns ``None``; the caller then keeps the
    deterministic unknown instead of translating an LLM claim into a final
    determination.
    """
    status = block.get("status")
    target = _FIELD_TARGETS[field_name]
    if status == "not_applicable":
        if str(rule_text or "").strip():
            return None
        return _applicable(target, "not_applicable", "llm_evidence_not_applicable_empty_rule",
                          violation=False, evidence=[])
    if status == "ambiguous" or status is None:
        return None
    if not evidence_ids or not evidence_items:
        return None
    if field_name == "condition":
        if status == "enforced" and any(
                _text_supports(rule_text, item.get("text")) for item in evidence_items):
            return _applicable(target, "enforced", "llm_claim_supported_by_bound_condition_evidence",
                               violation=False, evidence=list(evidence_items),
                               bound_evidence_ids=list(evidence_ids))
        return None
    if field_name == "exception":
        if status == "handled" and any(
                _text_supports(rule_text, item.get("text")) for item in evidence_items):
            return _applicable(target, "handled", "llm_claim_supported_by_bound_exception_evidence",
                               violation=False, evidence=list(evidence_items),
                               bound_evidence_ids=list(evidence_ids))
        return None
    if field_name == "constraint":
        decision = _program_constraint_decision(rule_text, evidence_items)
        if decision == status:
            return _applicable(target, decision,
                               f"llm_claim_confirmed_by_programmatic_time_comparison:{decision}",
                               violation=(decision == "violated"),
                               evidence=list(evidence_items),
                               bound_evidence_ids=list(evidence_ids))
        return None
    return None


def strip_grounding_context(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Remove runtime-only context objects before publishing rows."""
    return [
        {key: value for key, value in row.items() if not str(key).startswith("_")}
        for row in rows
    ]


_GENERATED_TOKEN_RE = re.compile(r"\bsyn_[A-Za-z0-9_\-.:]+\b")


def _generated_only_transform(text: str, id_map: Mapping[str, str]) -> str:
    return _GENERATED_TOKEN_RE.sub(
        lambda match: id_map.get(match.group(0), match.group(0)), text)


def anonymize_fallback_payload(
    payload: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, str]]:
    """v4 wrapper: keep evidence-id references consistent with mapped ids.

    The v3 helper already maps each evidence item's ``id`` field.  Its
    ``local_context.evidence_ids`` list predates that key being treated as an
    identifier list, so this wrapper remaps the references with the same
    deterministic forward map.  Composite ids such as
    ``handler_of:syn_boundary_...`` are handled by reproducing the v3
    generated-token pass and mapping the resulting alias to the mapped full
    id.  Without this, the pack would advertise an id that is not present in
    any visible evidence item.
    """
    anonymized, id_map = _v3_anonymize_fallback_payload(payload)
    alias: dict[str, str] = {str(key): str(value) for key, value in id_map.items()}
    for original, mapped in id_map.items():
        alias[_generated_only_transform(str(original), id_map)] = str(mapped)
    local = anonymized.get("local_context")
    if isinstance(local, Mapping):
        local["evidence_ids"] = [
            alias.get(str(value), str(value))
            for value in (local.get("evidence_ids") or [])
        ]
    return anonymized, id_map


def _reverse_id_map(item: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(anonymous): str(real)
        for real, anonymous in (item.get("anonymized_id_map") or {}).items()
    }


def _find_pack_item(result: Mapping[str, Any],
                    pack: Mapping[str, Any] | None) -> dict[str, Any]:
    if not pack:
        return {}
    fallback_id = result.get("fallback_item_id")
    source_index = result.get("source_index")
    for item in pack.get("items", []):
        if fallback_id is not None and item.get("fallback_item_id") == fallback_id:
            return dict(item)
    if isinstance(source_index, int):
        for item in pack.get("items", []):
            if item.get("source_index") == source_index:
                return dict(item)
    return {}


def _context_for(updated: Sequence[Mapping[str, Any]], source_index: int,
                 contexts: Mapping[Any, Any] | None) -> Mapping[str, Any] | None:
    row = updated[source_index]
    if contexts:
        context = contexts.get((source_index, row.get("side")))
        if context is None:
            context = contexts.get(source_index)
        if context is not None:
            return context
    return row.get("_grounding_context")


def apply_llm_grounding(rows: Sequence[Mapping[str, Any]],
                        results: Sequence[Mapping[str, Any]],
                        *, pack: Mapping[str, Any] | None = None,
                        contexts: Mapping[Any, Any] | None = None
                        ) -> list[dict[str, Any]]:
    """Apply one validated response field-by-field.

    All replacements are program-bound: an action id must reverse-map into the
    original candidate scope; an evidence id must exist in the target field's
    action-anchored surface; an absence claim is only written when the
    re-executed program check closes the local scope.  A clear deterministic
    check is never overwritten.
    """
    updated: list[dict[str, Any]] = []
    for row in rows:
        clone = copy.deepcopy({key: value for key, value in row.items()
                               if key != "_grounding_context"})
        if "_grounding_context" in row:
            clone["_grounding_context"] = row["_grounding_context"]
        updated.append(clone)

    for result in results:
        status = str(result.get("status") or "")
        if status == "failed":
            continue
        source_index = result.get("source_index")
        if not isinstance(source_index, int) or source_index < 0 \
                or source_index >= len(updated):
            continue
        response = result.get("response") or {}
        if not isinstance(response, Mapping):
            continue
        row = updated[source_index]
        checks = row.setdefault("checks", {})
        pack_item = _find_pack_item(result, pack)
        reverse_ids = _reverse_id_map(pack_item)
        context = _context_for(updated, source_index, contexts) or {}
        sentence = context.get("sentence") or {}
        record = context.get("record") or {}
        xml_root = context.get("xml_root")
        old_decision = copy.deepcopy(row.get("decision"))
        old_prediction = row.get("predicted_violation_type")
        old_ground = copy.deepcopy(row.get("action_grounding") or {})
        effective_ground = old_ground
        application: dict[str, Any] = {
            "response_status": status,
            "action_grounding_applied": False,
            "action_real_activity_id": None,
            "action_anonymous_activity_id": None,
            "fields_applied": [],
            "fields_abstained": [],
            "fields_preserved_clear": [],
            "evidence_binding_failures": [],
        }

        action = response.get("action_grounding") or {}
        raw_activity_id = action.get("activity_id")
        if action.get("status") == "matched" and raw_activity_id is not None:
            real_activity_id = reverse_ids.get(str(raw_activity_id), str(raw_activity_id))
            candidate_scope = {
                str(value) for value in (old_ground.get("candidate_activity_ids") or [])
            }
            if candidate_scope and real_activity_id not in candidate_scope:
                application["action_rejected_reason"] = (
                    "resolved_real_activity_id_not_in_original_candidate_scope")
                application["evidence_binding_failures"].append({
                    "kind": "action_id_not_in_candidate_scope",
                    "anonymous_activity_id": str(raw_activity_id),
                    "real_activity_id": real_activity_id,
                })
            else:
                effective_ground = _resolved_ground(old_ground, real_activity_id, record)
                row["action_grounding_before_llm"] = copy.deepcopy(old_ground)
                row["action_grounding"] = effective_ground
                application["action_grounding_applied"] = True
                application["action_real_activity_id"] = real_activity_id
                application["action_anonymous_activity_id"] = str(raw_activity_id)

        if effective_ground.get("status") == ACTION_STATUS_RESOLVED and context:
            rechecks = _recheck_after_action(sentence, record, xml_root, effective_ground)
            row["rechecks_after_llm_action"] = {}
            for target in EXTENDED_TYPES:
                old_check = checks.get(target) or {}
                recheck = rechecks.get(target) or {}
                if _is_clear(old_check):
                    row["rechecks_after_llm_action"][target] = {
                        "applied": False,
                        "reason": "preserved_clear_deterministic_check",
                        "recheck_status": recheck.get("status"),
                        "recheck_violation": recheck.get("violation"),
                    }
                    continue
                if _is_clear(recheck):
                    merged = copy.deepcopy(recheck)
                    merged["previous_check"] = copy.deepcopy(old_check)
                    merged["source"] = "program_recheck_after_llm_action"
                    merged["llm_action_activity_id"] = effective_ground.get("activity_id")
                    checks[target] = merged
                    row["rechecks_after_llm_action"][target] = {
                        "applied": True,
                        "status": merged.get("status"),
                        "violation": merged.get("violation"),
                        "reason": merged.get("reason"),
                    }
                else:
                    row["rechecks_after_llm_action"][target] = {
                        "applied": False,
                        "reason": "program_recheck_remained_undetermined",
                        "recheck_status": recheck.get("status"),
                        "recheck_violation": recheck.get("violation"),
                    }

        candidate_ids = [
            str(value) for value in (effective_ground.get("candidate_activity_ids") or [])
        ]
        for field_name, target in _FIELD_TARGETS.items():
            block = response.get(field_name)
            if not isinstance(block, Mapping):
                continue
            old_check = checks.get(target) or {}
            if _is_clear(old_check):
                application["fields_preserved_clear"].append(field_name)
                continue
            raw_evidence_ids = block.get("evidence_ids")
            if not isinstance(raw_evidence_ids, list):
                raw_evidence_ids = []
            resolved_evidence_ids: list[str] = []
            unresolved: list[str] = []
            for evidence_id in raw_evidence_ids:
                if not isinstance(evidence_id, str):
                    unresolved.append(str(evidence_id))
                    continue
                if evidence_id in reverse_ids:
                    resolved_evidence_ids.append(reverse_ids[evidence_id])
                else:
                    # Strictly fail closed: the visible payload advertised
                    # anonymous ids, not original ids.
                    unresolved.append(evidence_id)
            if unresolved:
                old_check["llm_evidence_binding"] = {
                    "applied": False,
                    "reason": "evidence_id_not_reversible_to_original_id",
                    "unresolved_evidence_ids": unresolved,
                }
                checks[target] = old_check
                application["fields_abstained"].append(field_name)
                application["evidence_binding_failures"].append({
                    "kind": "evidence_id_not_reversible",
                    "field": field_name,
                    "unresolved_evidence_ids": unresolved,
                })
                continue
            surface = _surface_maps(field_name, record, xml_root, candidate_ids) \
                if context else {}
            evidence_items: list[dict[str, Any]] = []
            out_of_surface: list[str] = []
            for evidence_id in resolved_evidence_ids:
                if evidence_id in surface:
                    evidence_items.append(surface[evidence_id])
                else:
                    out_of_surface.append(evidence_id)
            if out_of_surface:
                old_check["llm_evidence_binding"] = {
                    "applied": False,
                    "reason": "evidence_id_not_in_target_action_surface",
                    "out_of_surface_evidence_ids": out_of_surface,
                }
                checks[target] = old_check
                application["fields_abstained"].append(field_name)
                application["evidence_binding_failures"].append({
                    "kind": "evidence_id_out_of_surface",
                    "field": field_name,
                    "evidence_ids": out_of_surface,
                })
                continue
            new_check = _apply_field_evidence(
                field_name, sentence.get(field_name), block, evidence_items,
                resolved_evidence_ids)
            if new_check is not None:
                new_check["previous_check"] = copy.deepcopy(old_check)
                new_check["source"] = "program_verified_llm_evidence"
                new_check["llm_evidence_ids"] = list(resolved_evidence_ids)
                new_check["llm_field_status"] = block.get("status")
                checks[target] = new_check
                application["fields_applied"].append(field_name)
            else:
                old_check["llm_field_status"] = block.get("status")
                old_check["llm_evidence_binding"] = {
                    "applied": False,
                    "reason": "program_evidence_check_did_not_confirm_determination",
                    "resolved_evidence_ids": list(resolved_evidence_ids),
                }
                checks[target] = old_check
                application["fields_abstained"].append(field_name)

        row["decision_before_llm"] = old_decision
        row["predicted_violation_type_before_llm"] = old_prediction
        row["decision"] = decide(checks)
        row["predicted_violation_type"] = row["decision"].get("predicted")
        row["llm_application"] = application
    return updated


def _visible_local_context(raw_context: Mapping[str, Any]) -> dict[str, Any]:
    visible_condition = list(raw_context.get("condition_evidence") or [])[:20]
    visible_constraint_bound = list(raw_context.get("constraint_bound_evidence") or [])[:20]
    visible_constraint_unbound = list(raw_context.get("constraint_unbound_evidence") or [])[:20]
    visible_exception = list(raw_context.get("exception_handler_candidates") or [])[:20]
    visible_ids = {
        str(item.get("id"))
        for item in (visible_condition + visible_constraint_bound
                     + visible_constraint_unbound + visible_exception)
        if item.get("id")
    }
    raw_evidence_ids = [
        str(value) for value in (raw_context.get("evidence_ids") or [])
        if str(value) in visible_ids
    ]
    candidate_activities = list(raw_context.get("candidate_activities") or [])
    candidate_activity_ids = [
        activity.get("activity_id") for activity in candidate_activities
        if activity.get("activity_id")
    ]
    return {
        "candidate_activities": candidate_activities,
        "candidate_activity_ids": candidate_activity_ids,
        "nodes": list(raw_context.get("nodes") or []),
        "sequence_flows": list(raw_context.get("sequence_flows") or []),
        "condition_evidence": visible_condition,
        "constraint_bound_evidence": visible_constraint_bound,
        "constraint_unbound_evidence": visible_constraint_unbound,
        "exception_handler_candidates": visible_exception,
        "evidence_ids": raw_evidence_ids,
    }


def _semantic_fields_preserved(source_rule: Mapping[str, Any],
                               anonymized_rule: Mapping[str, Any]) -> dict[str, Any]:
    fields = ("actor", "action", "condition", "constraint", "exception")
    preserved = {
        field: str(source_rule.get(field) or "") == str(anonymized_rule.get(field) or "")
        for field in fields
    }
    return {"preserved": preserved, "all_preserved": all(preserved.values())}


def build_fallback_pack(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Build the v4 pack with only actually-visible evidence ids."""
    items: list[dict[str, Any]] = []
    trigger_counts: dict[str, int] = {}
    side_counts: dict[str, int] = {}
    for source_index, row in enumerate(rows):
        if row.get("predicted_violation_type") is not None:
            continue
        triggers = fallback_triggers(row)
        if not triggers:
            continue
        raw_rule = dict(row.get("model_visible_rule_input") or {})
        raw_context = dict(row.get("compact_local_context") or {})
        visible_local = _visible_local_context(raw_context)
        visible_payload = {
            "rule_record": raw_rule,
            "candidate_activities": visible_local["candidate_activities"],
            "candidate_activity_ids": visible_local["candidate_activity_ids"],
            "local_context": {
                "nodes": visible_local["nodes"],
                "sequence_flows": visible_local["sequence_flows"],
                "condition_evidence": visible_local["condition_evidence"],
                "constraint_bound_evidence": visible_local["constraint_bound_evidence"],
                "constraint_unbound_evidence": visible_local["constraint_unbound_evidence"],
                "exception_handler_candidates": visible_local["exception_handler_candidates"],
                "evidence_ids": visible_local["evidence_ids"],
            },
        }
        anonymized, id_map = anonymize_fallback_payload(visible_payload)
        anonymized_local = anonymized.get("local_context") or {}
        visible_after = []
        for key in ("condition_evidence", "constraint_bound_evidence",
                    "constraint_unbound_evidence", "exception_handler_candidates"):
            visible_after.extend(anonymized_local.get(key) or [])
        visible_ids_after = {
            str(item.get("id")) for item in visible_after if item.get("id")
        }
        advertised_ids = {str(value) for value in (anonymized_local.get("evidence_ids") or [])}
        semantic = _semantic_fields_preserved(raw_rule, anonymized.get("rule_record") or {})
        item = {
            "fallback_item_id": f"fb_v4_{len(items) + 1:04d}",
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
            "semantic_field_preservation": semantic,
            "semantic_fields_preserved": semantic["all_preserved"],
            "evidence_ids_visible_in_payload": advertised_ids <= visible_ids_after,
        }
        items.append(item)
        for trigger in triggers:
            trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1
        side = str(row.get("side"))
        side_counts[side] = side_counts.get(side, 0) + 1
    return {
        "schema_version": FALLBACK_PACK_SCHEMA,
        "revision": REVISION,
        "base_revision": BASE_REVISION,
        "scope": "development_only",
        "candidate_policy": (
            "only final deterministic abstentions (predicted_violation_type=None) "
            "with at least one documented semantic ambiguity/unresolved trigger"),
        "anonymisation_policy": (
            "only identifiers and generated synthetic tokens are mapped; natural-language "
            "rule text and evidence text are preserved verbatim"),
        "evidence_id_policy": (
            "the advertised evidence-id set is derived from the actually visible "
            "(post-truncation) evidence lists"),
        "item_count": len(items),
        "side_counts": side_counts,
        "trigger_counts": trigger_counts,
        "items": items,
        "contains_expected_labels": False,
        "llm_payload_excludes_forbidden_fields": True,
        "id_reverse_mapping_available": True,
        "all_evidence_ids_visible_in_payload": all(
            item["evidence_ids_visible_in_payload"] for item in items),
        "semantic_fields_preserved_for_all_items": all(
            item["semantic_fields_preserved"] for item in items),
    }


__all__ = [
    "REVISION",
    "EVALUATOR_VERSION",
    "BASE_REVISION",
    "normalize_llm_status",
    "apply_llm_grounding",
    "build_fallback_pack",
    "strip_grounding_context",
    "_FIELD_TARGETS",
]

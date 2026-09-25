# -*- coding: utf-8 -*-
"""R2 order-signal failure diagnostics.

This module is evidence-only.  It does not choose or alter an order relation,
a candidate, a threshold, a similarity, or a reachability decision.  It calls
the same frozen ``SunScorer`` helpers that produced the signal and records the
actual endpoint strings, candidate task IDs/text, similarity values, threshold,
mapping outcome, and reachability outcome.

The diagnostic categories separate the R1 failure modes that were previously
collapsed into one denominator-zero reason:

* no_rule_order_relation
* projection_rejected_range
* projection_rejected_ambiguity
* projection_rejected_syntax
* endpoint_unmapped
* endpoint_similarity_below_gamma
* reachability_satisfied
* reachability_violated
* stage2_rule_record_failed

It is pure post-processing and never reads Gold, construction_reference,
control/mutation fields, or another process model.
"""

from __future__ import annotations

from typing import Any, Mapping

PROJECTION_RANGE_REASONS = {
    "invalid_selected_span",
    "marker_outside_selected_span",
    "first_token_exceeds_selected_span",
    "nominal_chunk_outside_selected_span",
    "nominal_of_chain_outside_selected_span",
    "nominal_of_chain_incomplete_before_selected_span_end",
    "nominal_endpoint_outside_selected_span",
    "marker_inside_predicted_exception",
    "action_fully_inside_condition_constraint_or_exception",
}
PROJECTION_AMBIGUITY_REASONS = {
    "selected_span_contains_multiple_markers",
    "multiple_legal_pcomp_children",
    "multiple_verbal_predicates_after_marker",
    "endpoints_identical",
}
PROJECTION_SYNTAX_REASONS = {
    "no_single_main_action_endpoint",
    "expected_exactly_one_main_action_candidate",
    "main_action_remaining_fragments_with_verb_not_exactly_one",
    "no_legal_pcomp_child",
    "no_pcomp_child",
    "marker_dep_not_mark_or_prep",
    "mark_head_is_self",
    "mark_head_not_verb_or_aux",
    "mark_head_outside_marker_after_selected_span",
    "no_token_after_marker",
    "non_space_text_between_marker_and_first_token",
    "first_token_after_marker_does_not_start_noun_chunk",
    "nominal_of_chain_incomplete_after_of",
    "nominal_of_chain_noncontiguous_after_of",
    "nominal_of_chain_next_token_not_noun_chunk",
    "nominal_endpoint_numeric_root",
    "nominal_endpoint_date_time_quantity_root",
    "nominal_endpoint_empty_or_mismatch",
    "verbal_intersection_invalid",
    "verbal_intersection_does_not_retain_head",
    "verbal_endpoint_outside_selected_span",
    "verbal_endpoint_empty",
    "no_second_endpoint",
    "native_endpoint_not_resolvable_to_clause_action",
    "native_endpoint_empty_text",
}
CATEGORIES = (
    "no_rule_order_relation",
    "projection_rejected_range",
    "projection_rejected_ambiguity",
    "projection_rejected_syntax",
    "endpoint_unmapped",
    "endpoint_similarity_below_gamma",
    "reachability_satisfied",
    "reachability_violated",
    "stage2_rule_record_failed",
)


def _reason_category(reason: str | None) -> str:
    if reason in PROJECTION_RANGE_REASONS:
        return "projection_rejected_range"
    if reason in PROJECTION_AMBIGUITY_REASONS:
        return "projection_rejected_ambiguity"
    return "projection_rejected_syntax"


def _projection_reasons(projection: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(projection, Mapping):
        return []
    out: list[dict[str, Any]] = []
    for clause in projection.get("clause_audits") or []:
        for rejection in (clause or {}).get("rejections") or []:
            if isinstance(rejection, Mapping):
                reason = rejection.get("reason")
                if reason:
                    out.append({"clause_id": clause.get("clause_id"), "reason": reason,
                                "category": _reason_category(str(reason)),
                                "detail": dict(rejection)})
        for marker in (clause or {}).get("markers") or []:
            if isinstance(marker, Mapping) and marker.get("reason"):
                reason = str(marker.get("reason"))
                out.append({"clause_id": clause.get("clause_id"), "reason": reason,
                            "category": _reason_category(reason),
                            "detail": dict(marker)})
            for main_reject in (marker or {}).get("main_action_rejections") or []:
                if isinstance(main_reject, Mapping) and main_reject.get("reason"):
                    reason = str(main_reject.get("reason"))
                    out.append({"clause_id": clause.get("clause_id"), "reason": reason,
                                "category": _reason_category(reason),
                                "detail": dict(main_reject)})
    return out


def _action_id_by_name(model: Any, name: str | None) -> str | None:
    if not name:
        return None
    for action in getattr(model, "actions", []) or []:
        if action.get("name") == name:
            return action.get("id")
    return None


def _endpoint_evidence(text: str, candidate: str | None, similarity: float,
                       scorer: Any, model: Any, gamma: float) -> dict[str, Any]:
    task = None
    if candidate:
        for action in getattr(model, "actions", []) or []:
            if action.get("name") == candidate:
                task = action
                break
    return {
        "rule_endpoint_text": text,
        "rule_endpoint_lemma": scorer._lemma(text),
        "candidate_task_id": (task or {}).get("id"),
        "candidate_task_text": candidate,
        "candidate_task_kind": (task or {}).get("kind"),
        "candidate_task_lemma": scorer._lemma(candidate) if candidate else None,
        "similarity": float(similarity or 0.0),
        "gamma": float(gamma),
        "similarity_above_gamma": bool(candidate is not None and float(similarity or 0.0) > float(gamma)),
        "mapped": candidate is not None,
    }


def relation_evidence(relations: list[Any], model: Any, scorer: Any) -> list[dict[str, Any]]:
    gamma = float(getattr(scorer, "gamma"))
    evidence: list[dict[str, Any]] = []
    for relation in relations or []:
        if not isinstance(relation, (list, tuple)) or len(relation) != 2:
            evidence.append({
                "constraint": [str(relation)],
                "before": None,
                "after": None,
                "both_endpoints_mapped": False,
                "failure_category": "endpoint_unmapped",
                "parse_error": "relation_not_before_after_pair",
            })
            continue
        before_text, after_text = str(relation[0]), str(relation[1])
        before_name, before_score = scorer._best_action_match(before_text, model)
        after_name, after_score = scorer._best_action_match(after_text, model)
        before = _endpoint_evidence(before_text, before_name, before_score, scorer, model, gamma)
        after = _endpoint_evidence(after_text, after_name, after_score, scorer, model, gamma)
        both_mapped = bool(before["similarity_above_gamma"] and after["similarity_above_gamma"])
        category: str
        reachability = None
        if not (before["mapped"] and after["mapped"]):
            category = "endpoint_unmapped"
        elif not both_mapped:
            category = "endpoint_similarity_below_gamma"
        else:
            before_id = _action_id_by_name(model, before_name)
            after_id = _action_id_by_name(model, after_name)
            forward = None
            backward = None
            satisfied = None
            if before_id is not None and after_id is not None:
                forward = bool(model.is_reachable(before_id, after_id))
                backward = bool(model.is_reachable(after_id, before_id))
                satisfied = bool(forward and not backward)
            reachability = {
                "before_task_id": before_id,
                "after_task_id": after_id,
                "forward_reachable": forward,
                "backward_reachable": backward,
                "satisfied": satisfied,
            }
            category = "reachability_satisfied" if satisfied else "reachability_violated"
        evidence.append({
            "constraint": [before_text, after_text],
            "before": before,
            "after": after,
            "both_endpoints_mapped": both_mapped,
            "failure_category": category,
            "reachability": reachability,
        })
    return evidence


def build_sun_order_diagnostic(record: Mapping[str, Any] | None,
                               signal: Mapping[str, Any] | None,
                               model: Any, scorer: Any) -> dict[str, Any]:
    record = record or {}
    signal = signal or {}
    projection = record.get("order_relation_projection")
    relations = list(record.get("order_relations") or [])
    relation_ev = relation_evidence(relations, model, scorer)
    projection_reasons = _projection_reasons(projection)
    denominator = int(signal.get("denominator") or 0)
    status = str(signal.get("status") or "unknown")
    if record.get("failed"):
        category = "stage2_rule_record_failed"
    elif not relations:
        categories_in_order = [p["category"] for p in projection_reasons]
        if "projection_rejected_ambiguity" in categories_in_order:
            category = "projection_rejected_ambiguity"
        elif "projection_rejected_range" in categories_in_order:
            category = "projection_rejected_range"
        elif "projection_rejected_syntax" in categories_in_order:
            category = "projection_rejected_syntax"
        else:
            category = "no_rule_order_relation"
    elif denominator == 0:
        relation_categories = [r.get("failure_category") for r in relation_ev]
        if any(c == "endpoint_unmapped" for c in relation_categories):
            category = "endpoint_unmapped"
        elif any(c == "endpoint_similarity_below_gamma" for c in relation_categories):
            category = "endpoint_similarity_below_gamma"
        else:
            category = "endpoint_unmapped"
    else:
        category = "reachability_violated" if status == "violated" else "reachability_satisfied"
    return {
        "category": category,
        "status": status,
        "denominator": denominator,
        "order_relation_count": len(relations),
        "relation_evidence": relation_ev,
        "projection_reason_count": len(projection_reasons),
        "projection_reasons": projection_reasons,
        "projection": projection,
    }


def build_winter_order_diagnostic(signal: Mapping[str, Any] | None) -> dict[str, Any]:
    signal = signal or {}
    denominator = int(signal.get("denominator") or 0)
    status = str(signal.get("status") or "unknown")
    reason = str(signal.get("reason") or "")
    if denominator > 0:
        category = "reachability_violated" if status == "violated" else "reachability_satisfied"
    elif reason in ("no_rule_side_flow_relations", "no_rule_order_endpoints", "no_rule_order_relation"):
        category = "no_rule_order_relation"
    elif reason == "no_rule_obligations":
        category = "stage2_rule_record_failed"
    else:
        category = "no_rule_order_relation"
    return {
        "category": category,
        "status": status,
        "denominator": denominator,
        "native_reason": signal.get("reason"),
        "evidence": signal.get("evidence"),
    }


__all__ = [
    "CATEGORIES",
    "build_sun_order_diagnostic",
    "build_winter_order_diagnostic",
    "relation_evidence",
]

# -*- coding: utf-8 -*-
"""Stage 3 semantic-grounding revision v6 (anchor disambiguation + evidence scope).

This is a development-only candidate revision.  It does not replace the
frozen v1/v5 defaults and it performs no model/API inference.  It reuses the
saved v2 candidate rows (labels, similarity values and lexical coverages) and
the frozen local BPMN inputs.

The revision separates three questions that were previously conflated:

1. *Action ambiguity*: a resolved action is emitted only when a unique exact
   normalized label exists, or when the effective support evidence identifies
   exactly one candidate.  Lexical and semantic winners that disagree are
   effective competition and remain ambiguous.
2. *Anchor status*: ``action_match`` is only a lexical check.  A resolved
   node may still be semantically supported; a node without action match and
   without a non-action conflict is ``unconfirmed``, not "consistent".
3. *Evidence scope*: once an action is reliably resolved, constraint and
   exception evidence is collected only from that action and its allowed local
   structural surface.  Under ambiguity, evidence remains candidate-local and
   a definite verdict requires per-candidate consensus.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from bpc_hybrid.s3_semantic_grounding_v1 import (
    ACTION_STATUS_AMBIGUOUS,
    ACTION_STATUS_RESOLVED,
    ACTION_STATUS_UNRESOLVED,
    check_condition as _v1_check_condition,
    check_constraint as _v1_check_constraint,
    check_exception as _v1_check_exception,
    check_prohibited as _v1_check_prohibited,
    decide,
    fold_whitespace,
    text_equivalent,
    token_coverage,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES

REVISION = "s3_semantic_grounding_v6"
BASE_REVISION = "s3_semantic_grounding_v5"
SCORE_SCHEMA = "s3_semantic_grounding_score@6.0.0"
EVALUATOR_VERSION = "s3_semantic_grounding_v6_anchor_scope@1.0.0"

_STRONG_MATCH_COVERAGE = 0.8
_LEXICAL_STRONG = 0.5
_LEXICAL_SUPPORTED = 0.3
_SIMILARITY_SUPPORTED = 0.3
_SIMILARITY_GAMMA = 0.4
_RESOLVED_SIMILARITY_MARGIN = 0.15
_LEXICAL_LEADER_MARGIN = 0.15
_SEMANTIC_HIGH = 0.5
_SEMANTIC_HIGH_MARGIN = 0.1
_EXPLICIT_TIME_ABSENT_REASON = "explicit_time_bound_absent_from_closed_action_scope"

_GUARD_TARGETS = ("required_condition_not_enforced", "constraint_violated")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candidate_rows(ground: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in (ground.get("candidates") or [], ground.get("alternatives") or []):
        for candidate in source:
            if not isinstance(candidate, Mapping):
                continue
            activity_id = str(candidate.get("activity_id") or "").strip()
            if not activity_id or activity_id in seen:
                continue
            seen.add(activity_id)
            rows.append(dict(candidate))
    return rows


def _candidate_by_id(ground: Mapping[str, Any], activity_id: Any) -> dict[str, Any]:
    wanted = str(activity_id or "")
    for candidate in _candidate_rows(ground):
        if str(candidate.get("activity_id")) == wanted:
            return candidate
    return {}


def _candidate_label(ground: Mapping[str, Any], activity_id: Any) -> str:
    candidate = _candidate_by_id(ground, activity_id)
    return fold_whitespace(candidate.get("label"))


def _strong_text_match(left: Any, right: Any) -> bool:
    left_text = fold_whitespace(left)
    right_text = fold_whitespace(right)
    if not left_text or not right_text:
        return False
    return (
        text_equivalent(left_text, right_text)
        or token_coverage(left_text, right_text) >= _STRONG_MATCH_COVERAGE
        or token_coverage(right_text, left_text) >= _STRONG_MATCH_COVERAGE
    )


def _support_dimensions_for_candidate(candidate: Mapping[str, Any], ground: Mapping[str, Any],
                                      support_map: Mapping[str, set[str]]) -> list[str]:
    activity_id = str(candidate.get("activity_id") or "")
    explicit = support_map.get(activity_id)
    if explicit:
        return sorted(explicit)
    dimensions: list[str] = []
    if candidate.get("exact_normalized"):
        dimensions.append("exact_normalized")
    if _number(candidate.get("lexical_coverage")) >= _LEXICAL_STRONG:
        dimensions.append("lexical_strong")
    if (_number(candidate.get("lexical_coverage")) >= _LEXICAL_SUPPORTED
            and _number(candidate.get("similarity")) >= _SIMILARITY_SUPPORTED):
        dimensions.append("combined_supported")
    if _number(candidate.get("similarity")) >= _SIMILARITY_GAMMA:
        dimensions.append("semantic_supported")
    return dimensions


def disambiguate_action_grounding(
    ground: Mapping[str, Any],
    *,
    lexical_strong: float = _LEXICAL_STRONG,
    lexical_supported: float = _LEXICAL_SUPPORTED,
    similarity_supported: float = _SIMILARITY_SUPPORTED,
    gamma: float = _SIMILARITY_GAMMA,
    resolved_margin: float = _RESOLVED_SIMILARITY_MARGIN,
) -> dict[str, Any]:
    """Re-decide a saved action-grounding row without recomputing scores.

    The function intentionally consumes only the stored candidate rows.  The
    candidate set is a superset of top lexical / top semantic candidates from
    the frozen retrieval step.  Order and activity id are never used as
    evidence; they only identify rows in diagnostics.
    """
    result = copy.deepcopy(dict(ground))
    rows = _candidate_rows(result)
    retrieval_ids = list(dict.fromkeys(
        str(value) for value in (result.get("candidate_activity_ids") or [])
        if str(value or "").strip()
    ))
    result["retrieval_candidate_activity_ids"] = retrieval_ids or [
        str(row["activity_id"]) for row in rows
    ]
    result["schema"] = "s3_semantic_grounding_action@2.0.0"
    result["revision"] = REVISION
    result["disambiguation_scope"] = "saved_candidates_only_no_recomputed_similarity"
    result["global_leading_margin_applied_to"] = "leader_pair_only"
    result["anchor_activity_id"] = None
    result["anchor_activity_ids"] = []

    if not rows:
        result.update({
            "status": ACTION_STATUS_UNRESOLVED,
            "reason": "no_process_activities",
            "activity_id": None,
            "strong_activity_ids": [],
            "disambiguation": {"effective_activity_ids": [],
                               "effective_support": {},
                               "support_dimensions": []},
            "no_forced_resolution": True,
        })
        return result

    exact_ids = [str(row["activity_id"]) for row in rows
                 if row.get("exact_normalized") is True]
    if len(exact_ids) == 1:
        activity_id = exact_ids[0]
        result.update({
            "status": ACTION_STATUS_RESOLVED,
            "reason": "unique_exact_normalized_label",
            "activity_id": activity_id,
            "anchor_activity_id": activity_id,
            "anchor_activity_ids": [activity_id],
            "strong_activity_ids": [activity_id],
            "disambiguation": {
                "effective_activity_ids": [activity_id],
                "effective_support": {activity_id: ["exact_normalized"]},
                "support_dimensions": ["exact_normalized"],
                "lexical_leader_activity_ids": [],
                "semantic_leader_activity_ids": [],
                "lexical_and_semantic_conflict": False,
            },
            "no_forced_resolution": True,
        })
        return result

    any_signal = any(
        _number(row.get("similarity")) >= 0.2
        or _number(row.get("lexical_coverage")) >= 0.2
        for row in rows
    )
    if not any_signal:
        result.update({
            "status": ACTION_STATUS_UNRESOLVED,
            "reason": "no_activity_with_semantic_or_lexical_signal",
            "activity_id": None,
            "strong_activity_ids": [],
            "disambiguation": {"effective_activity_ids": [],
                               "effective_support": {},
                               "support_dimensions": []},
            "no_forced_resolution": True,
        })
        return result

    content_count = int(result.get("content_token_count") or 0)
    lexical_values = sorted((_number(row.get("lexical_coverage")) for row in rows),
                            reverse=True)
    semantic_values = sorted((_number(row.get("similarity")) for row in rows),
                             reverse=True)
    top_coverage = lexical_values[0]
    second_coverage = lexical_values[1] if len(lexical_values) > 1 else 0.0
    lexical_margin = top_coverage - second_coverage
    top_similarity = semantic_values[0]
    second_similarity = semantic_values[1] if len(semantic_values) > 1 else 0.0
    similarity_margin = top_similarity - second_similarity

    lexical_leaders = [row for row in rows
                       if abs(_number(row.get("lexical_coverage")) - top_coverage) < 1e-12]
    semantic_leaders = [row for row in rows
                        if abs(_number(row.get("similarity")) - top_similarity) < 1e-12]

    support_map: dict[str, set[str]] = {}

    def add_support(activity_id: str, dimension: str) -> None:
        support_map.setdefault(activity_id, set()).add(dimension)

    for row in rows:
        activity_id = str(row["activity_id"])
        coverage = _number(row.get("lexical_coverage"))
        similarity = _number(row.get("similarity"))
        if row.get("exact_normalized") is True:
            add_support(activity_id, "exact_normalized")
        if coverage >= lexical_strong:
            add_support(activity_id, "lexical_strong")
        if coverage >= lexical_supported and similarity >= similarity_supported:
            add_support(activity_id, "combined_supported")

    if len(lexical_leaders) == 1:
        leader = lexical_leaders[0]
        if (top_coverage >= lexical_supported and lexical_margin >= _LEXICAL_LEADER_MARGIN):
            add_support(str(leader["activity_id"]), "lexical_leader_margin")

    if len(semantic_leaders) == 1:
        leader = semantic_leaders[0]
        if (top_similarity >= gamma and similarity_margin >= resolved_margin
                and content_count >= 2):
            add_support(str(leader["activity_id"]), "semantic_leader_margin")
        if (top_similarity >= _SEMANTIC_HIGH and similarity_margin >= _SEMANTIC_HIGH_MARGIN
                and _number(leader.get("lexical_coverage")) >= 0.2):
            add_support(str(leader["activity_id"]), "semantic_high_margin")

    lexical_competitor = (
        str(lexical_leaders[0]["activity_id"])
        if len(lexical_leaders) == 1 and top_coverage >= lexical_strong
        else None
    )
    semantic_competitor = (
        str(semantic_leaders[0]["activity_id"])
        if (len(semantic_leaders) == 1 and top_similarity >= gamma
            and content_count >= 2)
        else None
    )
    conflict = bool(
        lexical_competitor
        and semantic_competitor
        and lexical_competitor != semantic_competitor
    )

    effective_ids = set(support_map)
    if conflict:
        status = ACTION_STATUS_AMBIGUOUS
        reason = "lexical_and_semantic_winner_conflict"
        resolved_id = None
        support_dimensions: list[str] = []
    elif len(effective_ids) == 1:
        resolved_id = next(iter(effective_ids))
        status = ACTION_STATUS_RESOLVED
        reason = "unique_supported_action_candidate"
        support_dimensions = sorted(support_map.get(resolved_id, set()))
    elif len(effective_ids) > 1:
        status = ACTION_STATUS_AMBIGUOUS
        reason = "multiple_effective_action_candidates_without_disambiguating_evidence"
        resolved_id = None
        support_dimensions = []
    else:
        status = ACTION_STATUS_AMBIGUOUS
        reason = "multiple_or_weak_activity_candidates"
        resolved_id = None
        support_dimensions = []

    result.update({
        "status": status,
        "reason": reason,
        "activity_id": resolved_id,
        "anchor_activity_id": resolved_id,
        "anchor_activity_ids": [resolved_id] if resolved_id else [],
        "strong_activity_ids": sorted(effective_ids),
        "disambiguation": {
            "effective_activity_ids": sorted(effective_ids),
            "effective_support": {
                activity_id: sorted(dimensions)
                for activity_id, dimensions in sorted(support_map.items())
                if activity_id in effective_ids
            },
            "support_dimensions": support_dimensions,
            "lexical_leader_activity_ids": [str(row["activity_id"])
                                            for row in lexical_leaders],
            "semantic_leader_activity_ids": [str(row["activity_id"])
                                             for row in semantic_leaders],
            "lexical_leader_coverage": round(top_coverage, 6),
            "lexical_runner_up_coverage": round(second_coverage, 6),
            "lexical_margin": round(lexical_margin, 6),
            "semantic_leader_similarity": round(top_similarity, 6),
            "semantic_runner_up_similarity": round(second_similarity, 6),
            "semantic_margin": round(similarity_margin, 6),
            "content_token_count": content_count,
            "lexical_and_semantic_conflict": conflict,
        },
        "no_forced_resolution": True,
    })
    return result


def _inferred_support_dimensions(ground: Mapping[str, Any], activity_id: str) -> list[str]:
    disambiguation = ground.get("disambiguation") or {}
    explicit = disambiguation.get("support_dimensions")
    if isinstance(explicit, list) and explicit:
        return [str(value) for value in explicit]
    effective_support = disambiguation.get("effective_support") or {}
    if isinstance(effective_support, Mapping):
        value = effective_support.get(activity_id)
        if isinstance(value, list) and value:
            return [str(item) for item in value]
    candidate = _candidate_by_id(ground, activity_id)
    dimensions: list[str] = []
    if candidate.get("exact_normalized"):
        dimensions.append("exact_normalized")
    if _number(candidate.get("lexical_coverage")) >= _LEXICAL_STRONG:
        dimensions.append("lexical_strong")
    if _number(candidate.get("similarity")) >= _SIMILARITY_GAMMA:
        dimensions.append("semantic_supported")
    return dimensions


def action_anchor_consistency(sentence: Mapping[str, Any],
                               ground: Mapping[str, Any]) -> dict[str, Any]:
    """Return the status of the resolved action anchor.

    ``action_match`` is only the word-level action check.  A false value is
    not by itself an error: a candidate with independent semantic grounding
    support is reported as ``supported``; a candidate with neither action nor
    non-action field match is ``unconfirmed`` rather than "consistent".
    """
    status = ground.get("status")
    activity_id = ground.get("anchor_activity_id") or ground.get("activity_id")
    if status != ACTION_STATUS_RESOLVED or not activity_id:
        return {
            "action_anchor_valid": None,
            "action_anchor_state": "not_resolved",
            "reason": "action_grounding_not_resolved",
            "resolved_activity_id": None,
            "resolved_label": "",
            "action_match": False,
            "non_action_field_matches": {},
            "support_dimensions": [],
        }

    activity_id = str(activity_id)
    label = _candidate_label(ground, activity_id)
    action_text = sentence.get("action")
    action_match = _strong_text_match(action_text, label)
    field_matches = {
        field: _strong_text_match(sentence.get(field), label)
        for field in ("condition", "constraint", "exception")
        if fold_whitespace(sentence.get(field))
    }
    support_dimensions = _inferred_support_dimensions(ground, activity_id)

    if action_match:
        state = "supported"
        valid: bool | None = True
        reason = "resolved_label_matches_action"
    elif any(field_matches.values()):
        state = "conflict"
        valid = False
        reason = "resolved_label_matches_non_action_rule_field"
    elif support_dimensions:
        state = "supported"
        valid = True
        reason = "resolved_label_has_action_grounding_support"
    else:
        state = "unconfirmed"
        valid = None
        reason = "resolved_label_action_support_unconfirmed"

    return {
        "action_anchor_valid": valid,
        "action_anchor_state": state,
        "reason": reason,
        "resolved_activity_id": activity_id,
        "resolved_label": label,
        "action_match": action_match,
        "non_action_field_matches": field_matches,
        "support_dimensions": support_dimensions,
    }


def apply_action_anchor_guard(
    sentence: Mapping[str, Any],
    ground: Mapping[str, Any],
    checks: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Demote condition/constraint determinations from an unsafe anchor.

    ``conflict`` and ``unconfirmed`` anchors are not valid action anchors.
    A ``not_resolved`` ground is left as-is because its checks already carry
    their own ambiguity/unknown state.
    """
    guarded = copy.deepcopy(dict(checks))
    consistency = action_anchor_consistency(sentence, ground)
    state = consistency.get("action_anchor_state")
    if state not in {"conflict", "unconfirmed"}:
        return guarded, []
    changes: list[dict[str, Any]] = []
    for target in _GUARD_TARGETS:
        old = guarded.get(target)
        if not isinstance(old, Mapping):
            continue
        if old.get("observable") is not True or old.get("violation") not in (True, False):
            continue
        new = dict(old)
        new.update({
            "status": "unknown",
            "observable": False,
            "violation": None,
            "score": None,
            "reason": "unconfirmed_or_conflicting_action_anchor_guard",
            "previous_check": copy.deepcopy(dict(old)),
            "source": "program_guard_v6_action_anchor",
            "anchor_state": state,
            "anchor_guard_reason": consistency.get("reason"),
            "anchor_support_dimensions": consistency.get("support_dimensions"),
        })
        guarded[target] = new
        changes.append({
            "target": target,
            "before": {
                "status": old.get("status"),
                "observable": old.get("observable"),
                "violation": old.get("violation"),
                "reason": old.get("reason"),
            },
            "after": {
                "status": "unknown",
                "observable": False,
                "violation": None,
                "reason": "unconfirmed_or_conflicting_action_anchor_guard",
            },
            "anchor_state": state,
        })
    return guarded, changes


def _narrow_ground(ground: Mapping[str, Any], activity_id: str,
                   status: str | None = None) -> dict[str, Any]:
    narrowed = dict(ground)
    narrowed["candidate_activity_ids"] = [str(activity_id)]
    narrowed["activity_id"] = str(activity_id)
    narrowed["anchor_activity_id"] = str(activity_id)
    narrowed["anchor_activity_ids"] = [str(activity_id)]
    if status is not None:
        narrowed["status"] = status
    return narrowed


def _scope_signature(check: Mapping[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (check.get("status"), check.get("observable"),
            check.get("violation"), check.get("reason"))


def _combine_candidate_scope_checks(check_name: str,
                                    checks: Sequence[Mapping[str, Any]],
                                    candidate_ids: Sequence[str]
                                    ) -> dict[str, Any]:
    if not checks:
        return {"check": check_name, "status": "unknown", "observable": False,
                "violation": None, "reason": "no_candidate_scope_check",
                "score": None, "anchor_scope": "ambiguous"}
    signatures = {_scope_signature(check) for check in checks}
    scope_checks = [
        {
            "activity_id": str(activity_id),
            "status": check.get("status"),
            "observable": check.get("observable"),
            "violation": check.get("violation"),
            "reason": check.get("reason"),
            "evidence": check.get("evidence"),
        }
        for activity_id, check in zip(candidate_ids, checks)
    ]
    if len(signatures) == 1 and checks[0].get("observable") is True:
        merged = copy.deepcopy(dict(checks[0]))
        merged["candidate_scope_checks"] = scope_checks
        merged["anchor_scope"] = "ambiguous_per_candidate_consensus"
        merged["consensus_candidate_activity_ids"] = [str(value)
                                                      for value in candidate_ids]
        return merged
    return {
        "check": check_name,
        "status": "unknown",
        "observable": False,
        "violation": None,
        "score": None,
        "reason": "per_candidate_action_scope_evidence_not_consensual",
        "anchor_scope": "ambiguous_per_candidate_disagreement",
        "candidate_scope_checks": scope_checks,
        "candidate_activity_ids": [str(value) for value in candidate_ids],
    }


def check_constraint(sentence: Mapping[str, Any], record: Mapping[str, Any],
                     xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    """Constraint check with anchor-scoped evidence collection."""
    status = ground.get("status")
    if status == ACTION_STATUS_UNRESOLVED:
        check = _v1_check_constraint(sentence, record, xml_root, ground)
        check["anchor_scope"] = "unresolved"
        return check
    if status == ACTION_STATUS_RESOLVED:
        activity_id = ground.get("anchor_activity_id") or ground.get("activity_id")
        if not activity_id:
            return {
                "check": "constraint_violated", "status": "unknown",
                "observable": False, "violation": None, "score": None,
                "reason": "resolved_action_without_anchor_activity_id",
                "anchor_scope": "resolved_missing_anchor",
            }
        check = _v1_check_constraint(
            sentence, record, xml_root,
            _narrow_ground(ground, str(activity_id), ACTION_STATUS_RESOLVED))
        check["anchor_scope"] = "resolved_single_action"
        check["anchor_activity_id"] = str(activity_id)
        return check

    candidates = list(ground.get("candidate_activity_ids") or [])
    if not candidates:
        return {
            "check": "constraint_violated", "status": "unknown",
            "observable": False, "violation": None, "score": None,
            "reason": "no_candidate_activity", "anchor_scope": "ambiguous",
        }
    probe = _v1_check_constraint(sentence, record, xml_root, ground)
    if probe.get("reason") in {
        "empty_rule_constraint",
        "unsupported_abstract_constraint_kind",
        "rule_bound_not_explicit_upper_limit",
        "calendar_duration_not_deterministically_comparable",
    }:
        probe["anchor_scope"] = "ambiguous_non_numeric_constraint"
        return probe
    candidate_checks = [
        _v1_check_constraint(
            sentence, record, xml_root,
            _narrow_ground(ground, str(activity_id), ACTION_STATUS_RESOLVED))
        for activity_id in candidates
    ]
    combined = _combine_candidate_scope_checks(
        "constraint_violated", candidate_checks, candidates)
    if combined.get("observable") is True:
        combined["reason"] = "per_candidate_" + str(combined.get("reason"))
    return combined


def check_exception(sentence: Mapping[str, Any], record: Mapping[str, Any],
                    xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    """Exception check with anchor-scoped evidence collection."""
    status = ground.get("status")
    if status == ACTION_STATUS_UNRESOLVED:
        check = _v1_check_exception(sentence, record, xml_root, ground)
        check["anchor_scope"] = "unresolved"
        return check
    if status == ACTION_STATUS_RESOLVED:
        activity_id = ground.get("anchor_activity_id") or ground.get("activity_id")
        if not activity_id:
            return {
                "check": "exception_not_handled", "status": "unknown",
                "observable": False, "violation": None, "score": None,
                "reason": "resolved_action_without_anchor_activity_id",
                "anchor_scope": "resolved_missing_anchor",
            }
        check = _v1_check_exception(
            sentence, record, xml_root,
            _narrow_ground(ground, str(activity_id), ACTION_STATUS_RESOLVED))
        check["anchor_scope"] = "resolved_single_action"
        check["anchor_activity_id"] = str(activity_id)
        return check

    candidates = list(ground.get("candidate_activity_ids") or [])
    if not candidates:
        return {
            "check": "exception_not_handled", "status": "unknown",
            "observable": False, "violation": None, "score": None,
            "reason": "no_candidate_activity", "anchor_scope": "ambiguous",
        }
    probe = _v1_check_exception(sentence, record, xml_root, ground)
    if probe.get("reason") == "empty_rule_exception":
        probe["anchor_scope"] = "ambiguous_not_applicable"
        return probe
    candidate_checks = [
        _v1_check_exception(
            sentence, record, xml_root,
            _narrow_ground(ground, str(activity_id), ACTION_STATUS_RESOLVED))
        for activity_id in candidates
    ]
    combined = _combine_candidate_scope_checks(
        "exception_not_handled", candidate_checks, candidates)
    if combined.get("observable") is True:
        combined["reason"] = "per_candidate_" + str(combined.get("reason"))
    return combined


def recompute_checks(sentence: Mapping[str, Any], record: Mapping[str, Any],
                     xml_root: Any, ground: Mapping[str, Any]
                     ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Recompute all four checks from the supplied anchor and local inputs."""
    checks = {
        "prohibited_action_present": _v1_check_prohibited(sentence, ground),
        "required_condition_not_enforced": _v1_check_condition(sentence, record, ground),
        "constraint_violated": check_constraint(sentence, record, xml_root, ground),
        "exception_not_handled": check_exception(sentence, record, xml_root, ground),
    }
    return apply_action_anchor_guard(sentence, ground, checks)


def score_sentence(sentence: Mapping[str, Any], record: Mapping[str, Any],
                   xml_root: Any, ground: Mapping[str, Any], *,
                   metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a v6 score object; metadata is accepted only to document blindness."""
    _ = metadata  # intentionally ignored (expected labels / ids / mutations)
    checks, guard_changes = recompute_checks(sentence, record, xml_root, ground)
    decision = decide(checks)
    return {
        "schema_version": SCORE_SCHEMA,
        "revision": REVISION,
        "action_grounding": ground,
        "action_anchor_consistency": action_anchor_consistency(sentence, ground),
        "anchor_guard_changes": guard_changes,
        "checks": checks,
        "decision": decision,
        "scores": {
            violation_type: (checks[violation_type].get("score")
                             if checks[violation_type].get("observable") else None)
            for violation_type in EXTENDED_TYPES
        },
        "observability": {
            violation_type: {
                "observable": bool(checks[violation_type].get("observable")),
                "reason": checks[violation_type].get("reason"),
                "status": checks[violation_type].get("status"),
            }
            for violation_type in EXTENDED_TYPES
        },
    }


__all__ = [
    "REVISION",
    "BASE_REVISION",
    "SCORE_SCHEMA",
    "EVALUATOR_VERSION",
    "ACTION_STATUS_RESOLVED",
    "ACTION_STATUS_AMBIGUOUS",
    "ACTION_STATUS_UNRESOLVED",
    "disambiguate_action_grounding",
    "action_anchor_consistency",
    "apply_action_anchor_guard",
    "check_constraint",
    "check_exception",
    "recompute_checks",
    "score_sentence",
]

# -*- coding: utf-8 -*-
"""Stage 3 semantic-grounding revision v7 (evidence-eligible candidate consensus).

Development-only successor of ``s3_semantic_grounding_v6``.  It keeps the v6
action-grounding disambiguation untouched and repairs one consistency bug in
the ambiguous-evidence branch:

* v6 probed every *retrieved* candidate after temporarily relabelling it as
  resolved.  When every retrieved candidate lacked an exception handler, the
  shared missing handler was merged into a definite violation even when the
  candidates had no effective grounding support at all.

v7 separates retrieval candidates from candidates with non-empty
``disambiguation.effective_support`` evidence.  Only evidence-eligible
candidates are probed, and each probe is kept as a conditional hypothesis.
The merged check stays ``unknown`` when the eligible set is empty, when a
candidate scope is incomplete/not observable, or when eligible candidates
disagree.  A merged verdict records the real ambiguous grounding status rather
than promoting the hypothesis to ``resolved``.

Zero real API/model inference.  No sample id, Gold, mutation target or
expected label is read.
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
)
from bpc_hybrid.s3_semantic_grounding_v6 import (
    action_anchor_consistency,
    apply_action_anchor_guard,
    check_constraint as _v6_check_constraint,
    check_exception as _v6_check_exception,
    disambiguate_action_grounding,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES

BASE_REVISION = "s3_semantic_grounding_v6"
REVISION = "s3_semantic_grounding_v7"
SCORE_SCHEMA = "s3_semantic_grounding_score@7.0.0"
EVALUATOR_VERSION = "s3_semantic_grounding_v7_eligible_consensus@1.0.0"

_NO_ELIGIBLE_REASON = "ambiguous_no_evidence_supported_action_candidate"
_DISAGREEMENT_REASON = "per_candidate_action_scope_evidence_not_consensual"


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


def _retrieval_candidate_ids(ground: Mapping[str, Any],
                             rows: Sequence[Mapping[str, Any]]) -> list[str]:
    ids = [str(value) for value in (ground.get("candidate_activity_ids") or [])
           if str(value or "").strip()]
    if not ids:
        ids = [str(row["activity_id"]) for row in rows]
    deduped: list[str] = []
    seen: set[str] = set()
    for activity_id in ids:
        if activity_id not in seen:
            seen.add(activity_id)
            deduped.append(activity_id)
    return deduped


def _effective_support_map(ground: Mapping[str, Any]) -> dict[str, list[str]]:
    """Return only non-empty per-candidate support evidence.

    An absent or empty ``effective_support`` is the signal that no candidate
    can serve as an evidentially valid anchor.
    """
    disambiguation = ground.get("disambiguation") or {}
    effective = disambiguation.get("effective_support") or {}
    if not isinstance(effective, Mapping):
        return {}
    result: dict[str, list[str]] = {}
    for activity_id, dimensions in effective.items():
        if isinstance(dimensions, list) and dimensions:
            result[str(activity_id)] = [str(value) for value in dimensions]
    return result


def eligible_candidate_ids(ground: Mapping[str, Any]) -> list[str]:
    """Retrieved candidates that also carry non-empty grounding evidence."""
    rows = _candidate_rows(ground)
    known = {str(row["activity_id"]) for row in rows}
    support = _effective_support_map(ground)
    return [activity_id for activity_id in _retrieval_candidate_ids(ground, rows)
            if activity_id in known and activity_id in support]


def _effective_support_public(ground: Mapping[str, Any]) -> dict[str, list[str]]:
    support = _effective_support_map(ground)
    return {activity_id: sorted(dimensions)
            for activity_id, dimensions in sorted(support.items())}


def _anchor_hypothesis_ground(ground: Mapping[str, Any],
                              activity_id: str) -> dict[str, Any]:
    """Internal conditional probe ground.

    The ``resolved`` status here is a local hypothesis used only so the v1
    checker can enumerate the candidate's own surface.  The assumption is
    never copied into the merged output as a resolved fact.
    """
    probe = dict(ground)
    probe["candidate_activity_ids"] = [str(activity_id)]
    probe["activity_id"] = str(activity_id)
    probe["anchor_activity_id"] = str(activity_id)
    probe["anchor_activity_ids"] = [str(activity_id)]
    probe["status"] = ACTION_STATUS_RESOLVED
    probe["conditional_anchor_hypothesis"] = True
    return probe


def _scope_signature(check: Mapping[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (check.get("status"), check.get("observable"),
            check.get("violation"), check.get("reason"))


def _no_eligible_check(check_name: str, ground: Mapping[str, Any]) -> dict[str, Any]:
    rows = _candidate_rows(ground)
    return {
        "check": check_name,
        "status": "unknown",
        "observable": False,
        "violation": None,
        "score": None,
        "reason": _NO_ELIGIBLE_REASON,
        "anchor_scope": "ambiguous_no_evidence_supported_candidate",
        "action_grounding_status": ground.get("status"),
        "retrieval_candidate_activity_ids": _retrieval_candidate_ids(ground, rows),
        "eligible_candidate_activity_ids": [],
        "effective_support": _effective_support_public(ground),
    }


def _candidate_scope_entry(activity_id: str, check: Mapping[str, Any],
                           support_dimensions: Sequence[str]) -> dict[str, Any]:
    return {
        "activity_id": str(activity_id),
        "candidate_anchor_hypothesis": True,
        "candidate_support_dimensions": list(support_dimensions),
        "status": check.get("status"),
        "observable": check.get("observable"),
        "violation": check.get("violation"),
        "reason": check.get("reason"),
        "evidence": check.get("evidence"),
    }


def _combine_eligible_checks(check_name: str,
                             checks: Sequence[Mapping[str, Any]],
                             eligible_ids: Sequence[str],
                             support: Mapping[str, Sequence[str]],
                             ground: Mapping[str, Any]) -> dict[str, Any]:
    rows = _candidate_rows(ground)
    scope_checks = [
        _candidate_scope_entry(activity_id, check, support.get(activity_id, []))
        for activity_id, check in zip(eligible_ids, checks)
    ]
    common = {
        "eligible_candidate_activity_ids": [str(value) for value in eligible_ids],
        "retrieval_candidate_activity_ids": _retrieval_candidate_ids(ground, rows),
        "effective_support": _effective_support_public(ground),
        "action_grounding_status": ground.get("status"),
        "conditional_anchor_hypothesis": True,
    }
    signatures = {_scope_signature(check) for check in checks}
    if len(signatures) == 1 and checks and checks[0].get("observable") is True:
        merged = copy.deepcopy(dict(checks[0]))
        merged.pop("candidate_activity_id", None)
        merged.pop("candidate_support_dimensions", None)
        merged["action_grounding_status"] = ground.get("status")
        merged["anchor_scope"] = "ambiguous_per_candidate_consensus"
        merged["consensus_candidate_activity_ids"] = [str(value) for value in eligible_ids]
        merged["candidate_scope_checks"] = scope_checks
        merged.update(common)
        return merged
    return {
        "check": check_name,
        "status": "unknown",
        "observable": False,
        "violation": None,
        "score": None,
        "reason": _DISAGREEMENT_REASON,
        "anchor_scope": "ambiguous_per_candidate_disagreement",
        "candidate_scope_checks": scope_checks,
        **common,
    }


def _conditional_candidate_checks(checker: Any, sentence: Mapping[str, Any],
                                  record: Mapping[str, Any], xml_root: Any,
                                  ground: Mapping[str, Any],
                                  eligible: Sequence[str],
                                  support: Mapping[str, Sequence[str]]
                                  ) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for activity_id in eligible:
        if checker is _v1_check_condition:
            check = checker(sentence, record,
                            _anchor_hypothesis_ground(ground, activity_id))
        else:
            check = checker(sentence, record, xml_root,
                            _anchor_hypothesis_ground(ground, activity_id))
        check = dict(check)
        check["action_grounding_status"] = ground.get("status")
        check["candidate_anchor_hypothesis"] = True
        check["candidate_activity_id"] = str(activity_id)
        check["candidate_support_dimensions"] = list(support.get(activity_id, []))
        checks.append(check)
    return checks


def check_condition(sentence: Mapping[str, Any], record: Mapping[str, Any],
                    ground: Mapping[str, Any]) -> dict[str, Any]:
    """Condition check with evidence-eligible anchor consensus."""
    if ground.get("status") != ACTION_STATUS_AMBIGUOUS:
        return _v1_check_condition(sentence, record, ground)
    eligible = eligible_candidate_ids(ground)
    if not eligible:
        return _no_eligible_check("required_condition_not_enforced", ground)
    support = _effective_support_map(ground)
    candidate_checks = _conditional_candidate_checks(
        _v1_check_condition, sentence, record, None, ground, eligible, support)
    combined = _combine_eligible_checks(
        "required_condition_not_enforced", candidate_checks, eligible, support, ground)
    if combined.get("observable") is True:
        combined["reason"] = "per_candidate_" + str(combined.get("reason"))
    return combined


def check_constraint(sentence: Mapping[str, Any], record: Mapping[str, Any],
                     xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    """Constraint check with evidence-eligible anchor consensus."""
    if ground.get("status") != ACTION_STATUS_AMBIGUOUS:
        return _v6_check_constraint(sentence, record, xml_root, ground)
    probe = _v1_check_constraint(sentence, record, xml_root, ground)
    if probe.get("reason") in {
        "empty_rule_constraint",
        "unsupported_abstract_constraint_kind",
        "rule_bound_not_explicit_upper_limit",
        "calendar_duration_not_deterministically_comparable",
    }:
        probe["anchor_scope"] = "ambiguous_non_numeric_constraint"
        probe["action_grounding_status"] = ground.get("status")
        return probe
    eligible = eligible_candidate_ids(ground)
    if not eligible:
        return _no_eligible_check("constraint_violated", ground)
    support = _effective_support_map(ground)
    candidate_checks = _conditional_candidate_checks(
        _v1_check_constraint, sentence, record, xml_root, ground, eligible, support)
    combined = _combine_eligible_checks(
        "constraint_violated", candidate_checks, eligible, support, ground)
    if combined.get("observable") is True:
        combined["reason"] = "per_candidate_" + str(combined.get("reason"))
    return combined


def check_exception(sentence: Mapping[str, Any], record: Mapping[str, Any],
                    xml_root: Any, ground: Mapping[str, Any]) -> dict[str, Any]:
    """Exception check with evidence-eligible anchor consensus."""
    if ground.get("status") != ACTION_STATUS_AMBIGUOUS:
        return _v6_check_exception(sentence, record, xml_root, ground)
    probe = _v1_check_exception(sentence, record, xml_root, ground)
    if probe.get("reason") == "empty_rule_exception":
        probe["anchor_scope"] = "ambiguous_not_applicable"
        probe["action_grounding_status"] = ground.get("status")
        return probe
    eligible = eligible_candidate_ids(ground)
    if not eligible:
        return _no_eligible_check("exception_not_handled", ground)
    support = _effective_support_map(ground)
    candidate_checks = _conditional_candidate_checks(
        _v1_check_exception, sentence, record, xml_root, ground, eligible, support)
    combined = _combine_eligible_checks(
        "exception_not_handled", candidate_checks, eligible, support, ground)
    if combined.get("observable") is True:
        combined["reason"] = "per_candidate_" + str(combined.get("reason"))
    return combined


def recompute_checks(sentence: Mapping[str, Any], record: Mapping[str, Any],
                     xml_root: Any, ground: Mapping[str, Any]
                     ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Recompute all four checks; the prohibited existence check is unchanged."""
    checks = {
        "prohibited_action_present": _v1_check_prohibited(sentence, ground),
        "required_condition_not_enforced": check_condition(sentence, record, ground),
        "constraint_violated": check_constraint(sentence, record, xml_root, ground),
        "exception_not_handled": check_exception(sentence, record, xml_root, ground),
    }
    return apply_action_anchor_guard(sentence, ground, checks)


def score_sentence(sentence: Mapping[str, Any], record: Mapping[str, Any],
                   xml_root: Any, ground: Mapping[str, Any], *,
                   metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a v7 score object; metadata is accepted only to document blindness."""
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
    "eligible_candidate_ids",
    "disambiguate_action_grounding",
    "action_anchor_consistency",
    "apply_action_anchor_guard",
    "check_condition",
    "check_constraint",
    "check_exception",
    "recompute_checks",
    "score_sentence",
]

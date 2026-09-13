# -*- coding: utf-8 -*-
"""Stage 3 semantic-grounding revision v5 (action-anchor consistency guard).

A concrete failure chain in the frozen v2 predictions showed that action
grounding can resolve to a node whose label is actually the rule's condition,
constraint or exception text (for example a generator-inserted exception
handler).  Subsequent local checks then treat the absence of a condition or
time bound around that non-action node as a substantive violation.

This revision adds a general consistency guard: when the resolved activity
label strongly matches a non-action rule field and does not match the rule
action, condition/constraint determinations anchored to that node are
demoted to ``unknown`` instead of being reported as compliance/violation.
The action fields themselves and exception-handler checks are not rewritten.
No API call is made.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from bpc_hybrid.s3_semantic_grounding_v1 import (
    ACTION_STATUS_RESOLVED,
    decide,
    fold_whitespace,
    text_equivalent,
    token_coverage,
)
from bpc_hybrid.s3_semantic_grounding_v4 import (
    strip_grounding_context,
)
from bpc_hybrid.s3_semantic_grounding_v4 import (
    build_fallback_pack as _v4_build_fallback_pack,
)

REVISION = "s3_semantic_grounding_v5"
BASE_REVISION = "s3_semantic_grounding_v4"
EVALUATOR_VERSION = "s3_semantic_grounding_v5_guard@1.0.0"

_ANCHOR_GUARD_TARGETS = (
    "required_condition_not_enforced",
    "constraint_violated",
)
_STRONG_MATCH_COVERAGE = 0.8


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


def _resolved_candidate_label(ground: Mapping[str, Any]) -> str:
    activity_id = str(ground.get("activity_id") or "")
    if not activity_id:
        return ""
    for candidate in list(ground.get("candidates") or []) + list(
            ground.get("alternatives") or []):
        if str(candidate.get("activity_id")) == activity_id:
            return fold_whitespace(candidate.get("label"))
    return ""


def action_anchor_consistency(sentence: Mapping[str, Any],
                               ground: Mapping[str, Any]) -> dict[str, Any]:
    """Return whether the resolved node is a plausible rule-action anchor."""
    if ground.get("status") != ACTION_STATUS_RESOLVED or not ground.get("activity_id"):
        return {
            "action_anchor_valid": None,
            "reason": "action_grounding_not_resolved",
            "resolved_activity_id": ground.get("activity_id"),
            "resolved_label": "",
            "action_match": False,
            "non_action_field_matches": {},
        }
    label = _resolved_candidate_label(ground)
    action_text = sentence.get("action")
    action_match = _strong_text_match(action_text, label)
    field_matches = {
        field: _strong_text_match(sentence.get(field), label)
        for field in ("condition", "constraint", "exception")
        if fold_whitespace(sentence.get(field))
    }
    invalid = bool(any(field_matches.values())) and not action_match
    return {
        "action_anchor_valid": not invalid,
        "reason": (
            "resolved_label_matches_non_action_rule_field"
            if invalid else "resolved_label_is_action_consistent"),
        "resolved_activity_id": ground.get("activity_id"),
        "resolved_label": label,
        "action_match": action_match,
        "non_action_field_matches": field_matches,
    }


def apply_action_anchor_guard(
    sentence: Mapping[str, Any],
    ground: Mapping[str, Any],
    checks: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Demote unsafe condition/constraint determinations to unknown."""
    guarded = copy.deepcopy(dict(checks))
    consistency = action_anchor_consistency(sentence, ground)
    changes: list[dict[str, Any]] = []
    if consistency.get("action_anchor_valid") is not False:
        return guarded, changes
    for target in _ANCHOR_GUARD_TARGETS:
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
            "reason": "non_action_rule_field_anchor_guard",
            "previous_check": copy.deepcopy(dict(old)),
            "source": "program_guard_non_action_anchor",
            "guard_reason": consistency["reason"],
            "guard_non_action_field_matches": consistency[
                "non_action_field_matches"],
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
                "reason": "non_action_rule_field_anchor_guard",
            },
        })
    return guarded, changes


def build_fallback_pack(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pack = _v4_build_fallback_pack(rows)
    pack["revision"] = REVISION
    pack["base_revision"] = BASE_REVISION
    for index, item in enumerate(pack.get("items", []), start=1):
        item["fallback_item_id"] = f"fb_v5_{index:04d}"
    return pack


__all__ = [
    "REVISION",
    "BASE_REVISION",
    "EVALUATOR_VERSION",
    "action_anchor_consistency",
    "apply_action_anchor_guard",
    "build_fallback_pack",
    "decide",
    "strip_grounding_context",
]

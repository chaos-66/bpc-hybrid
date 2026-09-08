# -*- coding: utf-8 -*-
"""Stable machine classification of per-sample change reasons for the
GDPR Stage-2 -> Stage-3 linkage arms.

Purpose
-------
The linkage experiments substitute the rule-record *source* of a frozen
Stage-3 detector (``run_gdpr_3type_linkage_v1.py`` for the ORIGINAL three
violation types; ``run_gdpr_s2_s3_linkage_v1.py`` for the FOUR new synthetic
types) with external Stage-2 prediction capsules.  When a source's verdict /
scores / observability differ from the reference (deterministic dev
extraction), downstream consumers need a STABLE, machine-readable reason
label for where the change came from -- extraction, adaptation (projection /
conversion) or detection.  This module provides pure functions that produce
such labels from already-built prediction rows (plus optional per-rule rule
records and the capsule conversion summary).  Nothing here reads Gold, and no
function performs similarity scoring or writes files.

Reason enumeration (fixed vocabulary, aligned with the 8853edd repair
semantics -- actor-action association, time-constraint applicability and the
unified five-class statistics):

* ``modality_flip_to_unobservable`` -- the reference adapter treated a
  sentence/clause as obligation (signalword gate) while the external capsule
  labels it with a non-obligation modality (prohibition/permission/definition
  or none), so the obligation-only gate drops its actions/actors and a check
  that the reference could score becomes unobservable or loses content.
* ``span_absent`` -- the capsule envelope is ok and the clause passes the
  modality gate, but it carries no (valid) action/actor/... spans where the
  reference extraction found text content, so fields shrink.
* ``first_valid_projection_changed`` -- both sides are observable but the
  six-element projection / conversion resolved different surface text
  (first-valid span choice, main clause choice), changing the score/verdict.
* ``action_mapping_below_gamma`` -- the action text that survived conversion
  no longer maps to any process action above the frozen gamma, so the check
  turns unobservable (repair semantics: nothing is hard-filled).
* ``time_constraint_applicability_changed`` -- a time/quantity constraint is
  present in both sides but its applicability changed (inside a condition,
  bound to a different/absent action, no action-bound time evidence), per the
  action-bound constraint-contradiction repair semantics.
* ``order_relations_missing`` -- the external capsule provides no Definition-7
  order relations while the reference record had some, so the out-of-order
  denominator collapses (relations are never fabricated).
* ``other`` -- envelope failure (missing/failed/empty), multiple concurrent
  signals without a dominant one, or anything the deterministic cascade does
  not attribute.

The labels are deterministic best-effort attributions from row/record
signals -- an audit aid, NOT a causal proof claim.
"""

from __future__ import annotations

from typing import Any, Mapping

CHANGE_REASONS: tuple[str, ...] = (
    "modality_flip_to_unobservable",
    "span_absent",
    "first_valid_projection_changed",
    "action_mapping_below_gamma",
    "time_constraint_applicability_changed",
    "order_relations_missing",
    "other",
)

CHANGE_REASON_NOTES: dict[str, str] = {
    "modality_flip_to_unobservable": (
        "external capsule modality label outside the obligation-only gate "
        "drops sentence content that the reference signalword adapter kept"),
    "span_absent": (
        "gate-passing capsule clause carries no valid action/actor spans "
        "where the reference extraction found text"),
    "first_valid_projection_changed": (
        "observable verdict changed because the six-element projection/"
        "conversion resolved different first-valid/main surface text"),
    "action_mapping_below_gamma": (
        "surviving action text maps below the frozen gamma; check unobservable "
        "instead of hard-filled (8853edd repair semantics)"),
    "time_constraint_applicability_changed": (
        "time/quantity constraint applicability changed (inside condition / "
        "different or absent action binding / no action-bound evidence)"),
    "order_relations_missing": (
        "external capsule has no Definition-7 order relations; never fabricated"),
    "other": (
        "envelope failure or concurrent signals without a dominant cause"),
}

_REASONS_SET = frozenset(CHANGE_REASONS)


def assert_reason(value: str) -> str:
    """Validate a reason against the stable enum (raises on unknown values)."""
    if value not in _REASONS_SET:
        raise ValueError(
            f"unknown change reason {value!r}; expected one of {list(CHANGE_REASONS)}")
    return value


def _non_empty(seq: Any) -> bool:
    return bool(seq)


def _per_rule_conversion(arm_conversion: Mapping[str, Any] | None,
                         rule_id: str) -> Mapping[str, Any]:
    if not arm_conversion:
        return {}
    per_rule = arm_conversion.get("per_rule") or {}
    entry = per_rule.get(rule_id) if isinstance(per_rule, Mapping) else None
    return entry if isinstance(entry, Mapping) else {}


def _excluded_modality_flip(per_rule: Mapping[str, Any]) -> bool:
    """True when the converter's obligation-only gate excluded clauses with a
    non-obligation modality (including a None/unknown label) for this rule."""
    excluded = per_rule.get("excluded_modality_counts") or {}
    if not isinstance(excluded, Mapping):
        return False
    return any(label != "obligation" for label in excluded)


# ---------------------------------------------------------------------------
# ORIGINAL three violation types (run_gdpr_3type_linkage_v1)
# ---------------------------------------------------------------------------


def classify_three_type_item(
    ref_row: Mapping[str, Any],
    arm_row: Mapping[str, Any],
    *,
    reference_records: Mapping[str, Mapping[str, Any]] | None = None,
    arm_records: Mapping[str, Mapping[str, Any]] | None = None,
    arm_conversion: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify why one 33-item row changed between the reference arm and an
    external-capsule arm.

    Returns ``{"item_id", "reason", "detail"}`` with ``reason`` always in
    :data:`CHANGE_REASONS`.  ``reference_records`` / ``arm_records`` are
    optional ``rule_id -> rule-record`` maps; ``arm_conversion`` is the
    converter summary dict returned by ``build_rule_records`` (whose
    ``per_rule`` section explains exclusions).  All inputs are already-built
    artifacts -- the classifier never scores and never reads Gold.
    """
    item_id = arm_row.get("item_id") or ref_row.get("item_id")
    rule_id = arm_row.get("rule_id") or ref_row.get("rule_id")
    detail: dict[str, Any] = {}

    def verdict_or_score_change() -> bool:
        if ref_row.get("predicted_violation_type") != arm_row.get(
                "predicted_violation_type"):
            return True
        ref_scores = ref_row.get("scores") or {}
        arm_scores = arm_row.get("scores") or {}
        for key in ("missing_action", "incorrect_actor", "out_of_order",
                    "missing_action_denominator", "incorrect_actor_denominator",
                    "out_of_order_denominator"):
            if ref_scores.get(key) != arm_scores.get(key):
                return True
        return (ref_row.get("incorrect_actor_observable")
                != arm_row.get("incorrect_actor_observable")
                or ref_row.get("incorrect_actor_reason")
                != arm_row.get("incorrect_actor_reason"))

    # 1) explicit external envelope failure -> other
    if arm_row.get("rule_record_failed"):
        detail.update({
            "class": "external_envelope_failure",
            "external_failure": arm_row.get("external_failure"),
        })
        return {"item_id": item_id, "reason": assert_reason("other"),
                "detail": detail}

    # No factual change at all: caller should normally filter these first,
    # but the classifier stays total and reports 'other' with a marker.
    if not verdict_or_score_change():
        detail.update({"class": "no_observable_change"})
        return {"item_id": item_id, "reason": assert_reason("other"),
                "detail": detail}

    ref_rec = (reference_records or {}).get(rule_id) or {}
    arm_rec = (arm_records or {}).get(rule_id) or {}
    per_rule = _per_rule_conversion(arm_conversion, rule_id)

    ref_actions = list(ref_rec.get("actions") or [])
    arm_actions = list(arm_rec.get("actions") or [])
    ref_actors = list(ref_rec.get("actors") or [])
    arm_actors = list(arm_rec.get("actors") or [])
    ref_pairs = list(ref_rec.get("actor_action_pairs") or [])
    arm_pairs = list(arm_rec.get("actor_action_pairs") or [])
    ref_relations = list(ref_rec.get("order_relations") or [])
    arm_relations = list(arm_rec.get("order_relations") or [])

    actor_flip_lost = (
        arm_row.get("check_type") == "incorrect_actor"
        and ref_row.get("incorrect_actor_observable") is True
        and arm_row.get("incorrect_actor_observable") is False
    )
    arm_actor_reason = arm_row.get("incorrect_actor_reason") or ""
    arm_external_failure = arm_row.get("external_failure")

    # 2) action mapping dropped below gamma (8853edd detection-side reason)
    if actor_flip_lost and "action_mapping_below_gamma" in arm_actor_reason:
        detail.update({
            "class": "detection",
            "actor_reason": arm_actor_reason,
            "source": "scorer_unobservable_reason",
        })
        return {"item_id": item_id,
                "reason": assert_reason("action_mapping_below_gamma"),
                "detail": detail}

    # 3) Definition-7 relations lost (never fabricated; endpoints cannot map)
    if ref_relations and not arm_relations:
        detail.update({
            "class": "extraction",
            "source": "order_relations",
            "reference_relation_count": len(ref_relations),
            "arm_relation_count": len(arm_relations),
        })
        return {"item_id": item_id,
                "reason": assert_reason("order_relations_missing"),
                "detail": detail}

    # 4) content lost at the rule-record level (adaptation side)
    actions_lost = bool(ref_actions) and not bool(arm_actions)
    actors_lost = bool(ref_actors) and not bool(arm_actors)
    pairs_lost = bool(ref_pairs) and not bool(arm_pairs)
    if actor_flip_lost or actions_lost or actors_lost or pairs_lost:
        flipped = _excluded_modality_flip(per_rule)
        envelopes_failed = bool(per_rule.get("envelopes_failed"))
        included_clauses = int(per_rule.get("included_clause_count") or 0)
        invalid_spans = int(per_rule.get("invalid_span_count") or 0)
        if flipped and not actions_lost:
            # Content survived via some clause but actor association vanished
            # because the modality flip removed the actor-bearing clause.
            reason = "modality_flip_to_unobservable"
            detail.update({
                "class": "adaptation",
                "source": "modality_gate",
                "excluded_modality_counts":
                    dict(per_rule.get("excluded_modality_counts") or {}),
            })
        elif flipped and envelopes_failed == 0:
            # All content for the rule came from clauses the capsule labelled
            # outside the obligation-only gate.
            reason = "modality_flip_to_unobservable"
            detail.update({
                "class": "adaptation",
                "source": "modality_gate",
                "excluded_modality_counts":
                    dict(per_rule.get("excluded_modality_counts") or {}),
            })
        elif invalid_spans > 0 or (included_clauses and not arm_actions):
            reason = "span_absent"
            detail.update({
                "class": "adaptation",
                "source": "span_absence",
                "included_clause_count": included_clauses,
                "invalid_span_count": invalid_spans,
            })
        elif actors_lost and not actions_lost and not arm_pairs and not arm_actors:
            reason = "span_absent"
            detail.update({
                "class": "adaptation",
                "source": "actor_span_absence",
            })
        else:
            reason = "other"
            detail.update({
                "class": "adaptation",
                "source": "content_loss_mixed_signals",
                "envelopes_failed": envelopes_failed,
                "excluded_modality_counts":
                    dict(per_rule.get("excluded_modality_counts") or {}),
                "invalid_span_count": invalid_spans,
            })
        detail.update({
            "reference_action_count": len(ref_actions),
            "arm_action_count": len(arm_actions),
            "reference_actor_count": len(ref_actors),
            "arm_actor_count": len(arm_actors),
            "reference_pair_count": len(ref_pairs),
            "arm_pair_count": len(arm_pairs),
            "arm_external_failure": arm_external_failure,
        })
        return {"item_id": item_id, "reason": assert_reason(reason),
                "detail": detail}

    # 5) score-level change without record-level loss -> other (mixed/unknown)
    detail.update({
        "class": "detection_or_other",
        "reference_prediction": ref_row.get("predicted_violation_type"),
        "arm_prediction": arm_row.get("predicted_violation_type"),
        "arm_external_failure": arm_external_failure,
    })
    return {"item_id": item_id, "reason": assert_reason("other"),
            "detail": detail}


# ---------------------------------------------------------------------------
# FOUR new synthetic violation types (run_gdpr_s2_s3_linkage_v1)
# ---------------------------------------------------------------------------

_CONSTRAINT_APPLICABILITY_REASONS = {
    "time_bound_inside_condition",
    "action_mapping_below_gamma",
    "no_action_bound_time_evidence",
}


def classify_extended_item(
    ref_row: Mapping[str, Any],
    arm_row: Mapping[str, Any],
) -> dict[str, Any]:
    """Classify one four-new-type sample whose prediction changed between the
    reference (locked deterministic extraction) panel row and an external
    Stage-2 arm row.

    Both rows use the ``stage3_extended_prediction@1.0.0`` shape (scores /
    observability / control_scores / external_failure).  The classifier is
    deterministic and row-signal based; extended arm rows additionally carry
    ``external_diagnostics`` from the first-valid-span projection when they
    were produced by ``run_gdpr_s2_s3_linkage_v1``.
    """
    item_id = arm_row.get("item_id") or ref_row.get("item_id")
    detail: dict[str, Any] = {}
    expected = arm_row.get("expected_violation") or ref_row.get("expected_violation")

    if arm_row.get("external_failure"):
        detail.update({
            "class": "external_envelope_failure",
            "external_failure": arm_row.get("external_failure"),
        })
        return {"item_id": item_id, "reason": assert_reason("other"),
                "detail": detail}

    arm_obs = arm_row.get("observability") or {}
    expected_arm_obs = arm_obs.get(expected) or {} if expected else {}
    arm_obs_reason = str(expected_arm_obs.get("reason") or "")
    ref_obs = ref_row.get("observability") or {}
    expected_ref_obs = ref_obs.get(expected) or {} if expected else {}
    ref_obs_reason = str(expected_ref_obs.get("reason") or "")
    arm_unobservable = expected_arm_obs.get("observable") is False
    ref_unobservable = expected_ref_obs.get("observable") is False

    # 1) detection-side mapping loss
    if arm_unobservable and "action_mapping_below_gamma" in arm_obs_reason:
        detail.update({
            "class": "detection",
            "source": "scorer_unobservable_reason",
            "reason": arm_obs_reason,
        })
        return {"item_id": item_id,
                "reason": assert_reason("action_mapping_below_gamma"),
                "detail": detail}

    # 2) modality gate flip on the external side
    if arm_unobservable and ("modality_not_prohibition" in arm_obs_reason
                             or arm_obs_reason.startswith("empty_rule_")):
        detail.update({
            "class": "adaptation",
            "source": "modality_or_empty_element",
            "arm_reason": arm_obs_reason,
            "reference_reason": ref_obs_reason,
        })
        return {"item_id": item_id,
                "reason": assert_reason("modality_flip_to_unobservable"),
                "detail": detail}

    # 3) time-constraint applicability change (constraint_violated only)
    if expected == "constraint_violated":
        arm_detail = arm_row.get("scores_detail") or {}
        ref_detail = ref_row.get("scores_detail") or {}
        arm_exact = (arm_detail.get("constraint_violated") or {}).get(
            "exact_contradiction") or {}
        ref_exact = (ref_detail.get("constraint_violated") or {}).get(
            "exact_contradiction") or {}
        arm_ec_reason = arm_exact.get("reason")
        ref_ec_reason = ref_exact.get("reason")
        contrad_changed = bool(arm_exact.get("contradiction")) != bool(
            ref_exact.get("contradiction"))
        if (arm_ec_reason in _CONSTRAINT_APPLICABILITY_REASONS
                and (contrad_changed or arm_ec_reason != ref_ec_reason)):
            detail.update({
                "class": "detection_or_adaptation",
                "source": "time_constraint_applicability",
                "arm_exact_contradiction": dict(arm_exact),
                "reference_exact_contradiction": dict(ref_exact),
            })
            return {"item_id": item_id,
                    "reason": assert_reason("time_constraint_applicability_changed"),
                    "detail": detail}

    # 4) observable verdict flip -> the substitution projection changed the
    #    first-valid/main surface (documented default for observable flips)
    if not arm_unobservable and not ref_unobservable:
        detail.update({
            "class": "adaptation",
            "source": "first_valid_span_projection",
            "reference_prediction": ref_row.get("predicted_violation_type"),
            "arm_prediction": arm_row.get("predicted_violation_type"),
            "arm_projection_error": None,
        })
        return {"item_id": item_id,
                "reason": assert_reason("first_valid_projection_changed"),
                "detail": detail}

    detail.update({
        "class": "other",
        "reference_prediction": ref_row.get("predicted_violation_type"),
        "arm_prediction": arm_row.get("predicted_violation_type"),
        "reference_unobservable": ref_unobservable,
        "arm_unobservable": arm_unobservable,
    })
    return {"item_id": item_id, "reason": assert_reason("other"),
            "detail": detail}

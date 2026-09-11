# -*- coding: utf-8 -*-
"""Thin adapter: wire the v3 structured action matcher into the frozen
four-type extension checks (S3.9-EXT v2).

What is replaced
----------------
``ExtendedViolationScorer`` (``src/bpc_hybrid/stage3_extended_violations.py``)
localizes the checked sentence's main action with a pure label-similarity
argmax: ``_best_action`` = max ``sim_action(rule action, activity label)``.
Every one of the four new types consumes that localization:

* ``prohibited_action`` scores the best action similarity directly;
* ``required_condition`` / ``exception_not_handled`` (via
  ``_missing_evidence``) refuse to compare anything when
  ``action_best < gamma`` and abort with ``action_mapping_below_gamma``;
* ``constraint_violated`` uses the same argmax id for the exact
  time-limit-contradiction gate;
* the panel runner passes the same argmax id into
  ``condition_candidates`` / ``constraint_candidates`` /
  ``exception_candidates``.

The adapter replaces **only** that localization with
``EvidenceChecksV3.action_match`` and keeps the four frozen formulas, the
frozen ``gamma_ext`` decision rule and the frozen evaluators untouched.

Semantics preserved
-------------------
v3's four outcomes are kept as four outcomes, never collapsed into a score:

* ``unique_satisfied_match`` (``mapped`` True: exact label / structure /
  similarity tier) -> the check may proceed, bound to **that** activity id;
* ``undetermined`` (``ambiguous_action_mapping``) -> the type stays
  unobservable; it is never turned into a violation or into a compliance;
* ``not_satisfied`` (``structure_not_satisfied`` / ``no_candidate_above_gamma``
  / ``no_process_actions``) -> the action gate stays closed and the type stays
  unobservable, with v3's own reason recorded;
* the scores that are reported are real similarities (the v3-selected
  candidate's ``raw_similarity`` for ``prohibited_action``, and
  ``1 - text similarity`` for the three evidence-comparison types).  A boolean
  verdict is never written as ``1.0`` / ``0.0``, and no threshold is changed.

The single matched activity of one localization is reused by the score gate,
the exact-contradiction gate and the candidate surfaces, so the evidence of a
type can never come from a different activity than the one v3 matched.

The adapter never reads ``expected_violation``, ``mutation_config``,
``target_activity_id``, gold labels or the item id.
"""

from __future__ import annotations

from typing import Any

from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    ConstraintSurface,
    ExtendedViolationScorer,
    detect_exact_constraint_contradiction,
)

ADAPTER_ID = "s3_extended_v3_adapter@1.0.0"
ADAPTER_LOCALIZATION = "evidence_checks_v3_action_match"

# v3's own outcomes, reported verbatim.
DECISION_MAPPED = "unique_satisfied_match"
DECISION_UNDETERMINED = "undetermined"
DECISION_NOT_SATISFIED = "not_satisfied"

V3_AMBIGUOUS_REASON = "ambiguous_action_mapping"

# Tiers that establish a definite (non-ambiguous) "the requirement is not
# satisfied by any candidate" answer.
V3_DEFINITE_TIERS = frozenset({
    "structure_not_satisfied", "no_candidate_above_gamma", "no_process_actions",
})


def classify_v3_decision(match: dict[str, Any]) -> str:
    """Map one ``action_match`` result onto v3's three reportable outcomes."""
    if match.get("mapped"):
        return DECISION_MAPPED
    if match.get("reason") == V3_AMBIGUOUS_REASON:
        return DECISION_UNDETERMINED
    return DECISION_NOT_SATISFIED


class V3ExtendedScorer(ExtendedViolationScorer):
    """Four-type extension checks with v3 action localization.

    ``sim_text`` is the arm's frozen text-similarity backend (the same callable
    the sun-style arm uses); ``gamma`` is that arm's frozen action-mapping
    threshold, recorded for provenance only - the action gate of this adapter
    is v3's own localization decision, exactly as the three-type v3 arm used
    it.  ``gamma_ext`` is the frozen extension decision threshold.
    """

    method_id = ADAPTER_ID

    def __init__(self, v3, sim_text, gamma: float, gamma_ext: float):
        super().__init__(sim_action=None, sim_text=sim_text, gamma=gamma,
                         gamma_ext=gamma_ext)
        self.v3 = v3
        self._localizations: dict[tuple[int, str], dict[str, Any]] = {}

    # ------------------------------------------------------------ localization
    def localize(self, action_text: str, model: Any) -> dict[str, Any]:
        """One memoized v3 localization for ``(model, rule action text)``."""
        text = " ".join((action_text or "").split())
        key = (id(model), text)
        cached = self._localizations.get(key)
        if cached is None:
            cached = self._localize(text, model)
            self._localizations[key] = cached
        return cached

    def _localize(self, text: str, model: Any) -> dict[str, Any]:
        match = self.v3.action_match(text, model)
        best = match.get("best") or {}
        candidates = list(match.get("candidates") or [])
        similarities = [float(c.get("raw_similarity") or 0.0) for c in candidates]
        return {
            "localization": ADAPTER_LOCALIZATION,
            "rule_action_text": text,
            "decision": classify_v3_decision(match),
            "mapped": bool(match.get("mapped")),
            "reason": match.get("reason"),
            "match_tier": match.get("match_tier"),
            "tier_reason": match.get("tier_reason"),
            "matched_activity_id": best.get("activity_id") if match.get("mapped") else None,
            "matched_activity_label": best.get("label") if match.get("mapped") else None,
            "winner_activity_id": best.get("activity_id"),
            "winner_label": best.get("label"),
            "winner_similarity": float(best.get("raw_similarity") or 0.0),
            "candidate_max_similarity": max(similarities) if similarities else 0.0,
            "candidate_count": len(model.actions),
            "candidate_preview": [
                {"activity_id": c.get("activity_id"), "label": c.get("label"),
                 "raw_similarity": float(c.get("raw_similarity") or 0.0),
                 "predicate_agrees": c.get("predicate_agrees"),
                 "verdict": c.get("verdict")}
                for c in candidates],
        }

    def _v3_trace(self, loc: dict[str, Any]) -> dict[str, Any]:
        """v3 provenance attached to every type's detail block."""
        return {
            "localization": loc["localization"],
            "v3_decision": loc["decision"],
            "v3_match_tier": loc["match_tier"],
            "v3_reason": loc["reason"],
            "v3_tier_reason": loc["tier_reason"],
            "v3_winner_activity_id": loc["winner_activity_id"],
            "v3_winner_similarity": round(loc["winner_similarity"], 6),
            "v3_candidate_count": loc["candidate_count"],
            "action_gate": "v3_localization_decision",
        }

    # ------------------------------------------------------------ the 4 checks
    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        if sentence.get("modality") != "prohibition":
            return {"score": None, "observable": False,
                    "reason": "rule_modality_not_prohibition"}
        action_text = (sentence.get("action") or "").strip()
        if not action_text:
            return {"score": None, "observable": False, "reason": "empty_rule_action"}
        loc = self.localize(action_text, model)
        if loc["decision"] == DECISION_UNDETERMINED:
            return {"score": None, "observable": False,
                    "reason": loc["reason"] or V3_AMBIGUOUS_REASON,
                    "action_max_sim": round(loc["candidate_max_similarity"], 6),
                    **self._v3_trace(loc)}
        if loc["decision"] == DECISION_MAPPED:
            score = loc["winner_similarity"]
            best_name = loc["winner_label"]
            selected_by = "v3_winner"
        else:
            score = loc["candidate_max_similarity"]
            best_name = (loc["candidate_preview"][0]["label"]
                         if loc["candidate_preview"] else None)
            selected_by = "candidate_max_similarity"
        return {
            "score": round(score, 6),
            "max_sim": round(score, 6),
            "best_candidate": best_name,
            "score_source": selected_by,
            "observable": True,
            "violation": score >= self.gamma_ext,
            **self._v3_trace(loc),
        }

    def _missing_evidence(self, field: str, sentence: dict[str, Any], model: Any,
                          candidates: list[str], violation_type: str) -> dict[str, Any]:
        rule_value = (sentence.get(field) or "").strip()
        if not rule_value:
            return {"score": None, "observable": False, "reason": f"empty_rule_{field}"}
        loc = self.localize((sentence.get("action") or "").strip(), model)
        if loc["decision"] != DECISION_MAPPED:
            return {
                "score": None,
                "observable": False,
                "reason": loc["reason"] or "v3_action_not_localized",
                "action_max_sim": round(loc["candidate_max_similarity"], 6),
                "action_best_candidate": loc["winner_label"],
                **self._v3_trace(loc),
            }
        if not candidates:
            return {"score": None, "observable": False,
                    "reason": f"no_{field}_candidates",
                    "action_max_sim": round(loc["winner_similarity"], 6),
                    "matched_activity_id": loc["matched_activity_id"],
                    **self._v3_trace(loc)}
        best, best_name = self._best(rule_value, candidates, self.sim_text)
        score = 1.0 - best
        return {
            "score": round(score, 6),
            "max_sim": round(best, 6),
            "best_candidate": best_name,
            "action_max_sim": round(loc["winner_similarity"], 6),
            "matched_activity_id": loc["matched_activity_id"],
            "observable": True,
            "violation": score > self.gamma_ext,
            "violation_type": violation_type,
            **self._v3_trace(loc),
        }

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        base = self._missing_evidence("constraint", sentence, model, candidates,
                                      "constraint_violated")
        constraint = " ".join((sentence.get("constraint") or "").lower().split())
        condition = " ".join((sentence.get("condition") or "").lower().split())
        loc = self.localize((sentence.get("action") or "").strip(), model)
        contradiction = {"contradiction": False, "reason": "no_action_bound_time_evidence"}
        if loc["decision"] != DECISION_MAPPED or not loc["matched_activity_id"]:
            contradiction["reason"] = "v3_action_not_localized"
        elif constraint and constraint in condition:
            contradiction["reason"] = "time_bound_inside_condition"
        elif isinstance(candidates, ConstraintSurface) \
                and candidates.activity_id == loc["matched_activity_id"]:
            contradiction = detect_exact_constraint_contradiction(
                sentence.get("constraint") or "", candidates.bound_texts)
        base["exact_contradiction"] = contradiction
        if contradiction.get("contradiction"):
            # inherited frozen behaviour: a detected numeric contradiction is
            # itself the evidence, so the type becomes observable
            base["observable"] = True
            base["reason"] = "exact_contradiction"
            base["score"] = 1.0
            base["violation"] = True
        return base

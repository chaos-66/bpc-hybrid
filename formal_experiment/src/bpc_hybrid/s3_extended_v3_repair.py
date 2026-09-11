# -*- coding: utf-8 -*-
"""S3.9-EXT v3-adapter repair (D1/D2/D3) - evidence-backed fixes only.

The 0.4 diagnostic arm showed that the Winter-vs-v3 gap is not a threshold
effect: migrating Winter's frozen ``gamma = 0.4`` into the v3 path changed no
metric at all, because v3's structured action match rejected 30/40 rule actions
that the label-argmax path maps at the same gamma.  The gate that consumes the
localization verdict is therefore the defect.  Three defects were confirmed from
the stored per-item artefacts (see ``outputs/evidence/s3_extended_gap_v1/
method_change_note.md``):

* **D1 - threshold applied to a score that is not on its scale.**
  ``V3ExtendedScorer.prohibited_action`` reports v3's *lemmatised*
  ``candidate_max_similarity``, while the frozen formula and the frozen
  ``gamma_ext`` were locked on the *raw* label similarity of the arm's backend.
  On this panel the same 0.5 cut falls on opposite sides of the two scales
  (``prohibited_action_04``: 1.0000 raw vs 0.5040 lemmatised).
* **D2 - two different answers to "what does this action refer to".**
  ``prohibited_action`` scored even when v3 did not localize, while
  ``_missing_evidence`` abstained; the score boolean and the reported evidence
  could disagree, and the exact-contradiction gate compared the activity id
  chosen by a *different* reference than the one the surfaces were built from.
* **D3 - a verification verdict used as a hard localization gate.**  v3's
  ``structure_not_satisfied`` answers "is the required action present".  As an
  anchor gate for the four-type evidence checks it removes every downstream
  comparison whenever the rule action and the process label differ in object
  content - the normal case for a legal sentence against a process label.

What this module does NOT change
--------------------------------
The panel, the rule binding, the six-element extractor, the four candidate
surfaces, the four frozen formulas, ``gamma_ext``, the unified five-class
decision with its fixed type order, the evaluators and the observability policy
are all inherited unchanged.  No threshold is lowered, searched or selected per
item; no sample id, rule id, target activity id, mutation text or expected label
is read; no legal vocabulary, synonym list or whitelist is added.

Inheritance
-----------
``RepairedExtendedScorer`` subclasses ``V3ExtendedScorer`` (which subclasses
``ExtendedViolationScorer``) and overrides only the action-resolution entry
points, so the frozen ``stage3_extended_violations`` module and the existing
``s3_extended_v3_adapter`` arm stay byte-identical.
"""

from __future__ import annotations

from typing import Any

from bpc_hybrid.s3_extended_v3_adapter import (  # noqa: E402
    DECISION_MAPPED,
    DECISION_NOT_SATISFIED,
    DECISION_UNDETERMINED,
    V3ExtendedScorer,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    ConstraintSurface,
    detect_exact_constraint_contradiction,
)

REPAIR_ID = "s3_extended_v3_repair@1.0.0"
REPAIR_SCOPE = "prohibited score scale, single action resolution, contradiction gate"

# How the one action resolution of a row was obtained.
RESOLVED_BY_V3_MATCH = "v3_satisfied_match"
RESOLVED_BY_ACTION_GAMMA = "label_argmax_at_or_above_action_gamma"
RESOLVED_NONE = "no_activity_resolvable"

REPAIR_NOTES = {
    "D1_prohibited_score_scale": (
        "prohibited_action_present is scored with the arm's declared raw-label "
        "formula max sim(rule_action, process_activity), the same scale the "
        "frozen gamma_ext 0.5 was locked on; the reported violation boolean is "
        "the score decision itself"
    ),
    "D2_single_action_resolution": (
        "one resolution (satisfying v3 match, else the arm's own label argmax at "
        "or above the arm's action gamma) feeds the score decision, the candidate "
        "surfaces, the evidence scores and the exact-contradiction gate"
    ),
    "D3_verification_is_not_a_localization_gate": (
        "v3's structure_not_satisfied verdict still decides whether the required "
        "action is present, but no longer decides whether the condition, "
        "constraint and exception evidence can be compared at all; only an "
        "action that cannot be resolved to any process activity keeps them "
        "unobservable"
    ),
}


def _model_identity(model: Any) -> tuple:
    """A stable identity for one process model.

    The repair keys its memo tables by model content (process id plus the ordered
    ``(activity_id, label)`` pairs the comparison consumes) instead of by
    ``id(model)``.  A Python object id is only unique while the object is alive,
    and the inherited v3 localization memo is keyed that way; a fresh scorer per
    model side keeps that harmless today, but a content key cannot be recycled
    and makes the "one resolution per row" guarantee independent of instantiation
    order.
    """
    actions = tuple((a.get("id"), (a.get("name") or "").strip())
                    for a in getattr(model, "actions", []))
    return (getattr(model, "process_id", None), actions)


class RepairedExtendedScorer(V3ExtendedScorer):
    """The v3 four-type extension with one action resolution and a coherent score scale."""

    method_id = REPAIR_ID

    def __init__(self, v3, sim_text, gamma_action: float, gamma_ext: float):
        super().__init__(v3, sim_text, gamma_action, gamma_ext)
        self._raw_cache: dict[tuple, dict[str, Any]] = {}
        self._resolution_cache: dict[tuple, dict[str, Any]] = {}

    # ------------------------------------------------------- action resolution
    def _raw_best_action(self, action_text: str, model: Any) -> dict[str, Any]:
        """The arm's own action-matching rule: best raw-label similarity candidate.

        Identical formula to ``ExtendedViolationScorer._best_action`` (the frozen
        label-argmax path): ``max sim(rule_action, activity_label)`` over the
        process activities, on the arm's backend and on the raw label text.
        """
        text = " ".join((action_text or "").split())
        key = (_model_identity(model), text)
        cached = self._raw_cache.get(key)
        if cached is not None:
            return cached
        best = 0.0
        best_name: str | None = None
        best_id: str | None = None
        for act in model.actions:
            name = (act.get("name") or "").strip()
            if not name:
                continue
            score = float(self.sim_text(text, name))
            if score > best or (score == best and best_id is None):
                best = score
                best_name = name
                best_id = act["id"]
        result = {
            "score": best,
            "label": best_name,
            "activity_id": best_id,
            "candidate_count": sum(1 for a in model.actions if (a.get("name") or "").strip()),
        }
        self._raw_cache[key] = result
        return result

    def resolve_action(self, action_text: str, model: Any) -> dict[str, Any]:
        """The one reference activity of this row, with its provenance.

        Memoized by model content, so two calls for the same model inside one
        row always return the very same resolution.
        """
        key = (_model_identity(model), " ".join((action_text or "").split()))
        cached = self._resolution_cache.get(key)
        if cached is not None:
            return cached
        loc = self.localize(action_text, model)
        raw = self._raw_best_action(action_text, model)
        resolved_id = None
        resolved_label = None
        resolved_by = RESOLVED_NONE
        if loc["decision"] == DECISION_MAPPED and loc["matched_activity_id"]:
            resolved_id = loc["matched_activity_id"]
            resolved_label = loc["matched_activity_label"]
            resolved_by = RESOLVED_BY_V3_MATCH
        elif raw["activity_id"] is not None and raw["score"] >= self.gamma:
            resolved_id = raw["activity_id"]
            resolved_label = raw["label"]
            resolved_by = RESOLVED_BY_ACTION_GAMMA
        result = {
            "action_resolution": REPAIR_ID,
            "rule_action_text": " ".join((action_text or "").split()),
            "resolved_activity_id": resolved_id,
            "resolved_activity_label": resolved_label,
            "resolved_by": resolved_by,
            "resolved_score": round(raw["score"], 6),
            "resolved_gate": "orig_raw_label_argmax_at_or_above_action_gamma",
            "action_gamma": self.gamma,
            "candidate_count": raw["candidate_count"],
            "v3_decision": loc["decision"],
            "v3_match_tier": loc["match_tier"],
            "v3_reason": loc["reason"],
            "v3_matched_activity_id": loc["matched_activity_id"],
            "v3_winner_activity_id": loc["winner_activity_id"],
            "v3_winner_similarity": round(loc["winner_similarity"], 6),
            "v3_candidate_max_similarity": round(loc["candidate_max_similarity"], 6),
            "raw_winner_activity_id": raw["activity_id"],
            "raw_winner_label": raw["label"],
            "raw_winner_similarity": round(raw["score"], 6),
        }
        self._resolution_cache[key] = result
        return result

    # ------------------------------------------------------------ the 4 checks
    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        """D1: the frozen formula's own score, on the frozen formula's own scale.

        ``score_prohibited = max sim(rule_action, process_activity)``.  The
        decision is ``score >= gamma_ext`` and the reported ``violation`` field
        is that same decision, so the score and the evidence can never disagree
        (D2).  Observability only requires that the comparison exists at all; it
        says nothing about the legal classification.
        """
        if sentence.get("modality") != "prohibition":
            return {"score": None, "observable": False,
                    "reason": "rule_modality_not_prohibition"}
        action_text = (sentence.get("action") or "").strip()
        if not action_text:
            return {"score": None, "observable": False, "reason": "empty_rule_action"}
        raw = self._raw_best_action(action_text, model)
        if raw["activity_id"] is None:
            return {"score": None, "observable": False,
                    "reason": "no_process_actions",
                    "action_resolution": REPAIR_ID,
                    "score_source": "max_raw_label_similarity_over_process_activities",
                    "candidate_count": raw["candidate_count"]}
        score = raw["score"]
        return {
            "score": round(score, 6),
            "max_sim": round(score, 6),
            "best_candidate": raw["label"],
            "best_candidate_activity_id": raw["activity_id"],
            "score_source": "max_raw_label_similarity_over_process_activities",
            "observable": True,
            "violation": score >= self.gamma_ext,
            "action_resolution": REPAIR_ID,
            "candidate_count": raw["candidate_count"],
        }

    def _missing_evidence(self, field: str, sentence: dict[str, Any], model: Any,
                          candidates: list[str], violation_type: str) -> dict[str, Any]:
        """D2/D3: evidence is compared only against the row's resolved activity."""
        rule_value = (sentence.get(field) or "").strip()
        if not rule_value:
            return {"score": None, "observable": False, "reason": f"empty_rule_{field}"}
        res = self.resolve_action((sentence.get("action") or "").strip(), model)
        if res["resolved_activity_id"] is None:
            return {
                "score": None,
                "observable": False,
                "reason": "action_not_resolvable_to_activity",
                "action_max_sim": res["resolved_score"],
                "action_best_candidate": res["raw_winner_label"],
                "matched_activity_id": None,
                "action_resolution": REPAIR_ID,
                **self._resolution_trace(res),
            }
        if not candidates:
            return {"score": None, "observable": False,
                    "reason": f"no_{field}_candidates",
                    "action_max_sim": res["resolved_score"],
                    "best_candidate": None,
                    "matched_activity_id": res["resolved_activity_id"],
                    "action_resolution": REPAIR_ID,
                    **self._resolution_trace(res)}
        best, best_name = self._best(rule_value, candidates, self.sim_text)
        score = 1.0 - best
        return {
            "score": round(score, 6),
            "max_sim": round(best, 6),
            "best_candidate": best_name,
            "action_max_sim": res["resolved_score"],
            "matched_activity_id": res["resolved_activity_id"],
            "observable": True,
            "violation": score > self.gamma_ext,
            "violation_type": violation_type,
            "action_resolution": REPAIR_ID,
            **self._resolution_trace(res),
        }

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        """The numeric contradiction branch passes through the same resolution."""
        base = self._missing_evidence("constraint", sentence, model, candidates,
                                      "constraint_violated")
        constraint = " ".join((sentence.get("constraint") or "").lower().split())
        condition = " ".join((sentence.get("condition") or "").lower().split())
        res = self.resolve_action((sentence.get("action") or "").strip(), model)
        contradiction = {"contradiction": False, "reason": "no_action_bound_time_evidence"}
        if res["resolved_activity_id"] is None:
            contradiction["reason"] = "action_not_resolvable_to_activity"
        elif constraint and constraint in condition:
            contradiction["reason"] = "time_bound_inside_condition"
        elif isinstance(candidates, ConstraintSurface) \
                and candidates.activity_id == res["resolved_activity_id"]:
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

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _resolution_trace(res: dict[str, Any]) -> dict[str, Any]:
        return {
            "resolved_by": res["resolved_by"],
            "resolved_activity_label": res["resolved_activity_label"],
            "resolved_score": res["resolved_score"],
            "v3_decision": res["v3_decision"],
            "v3_match_tier": res["v3_match_tier"],
            "v3_reason": res["v3_reason"],
            "v3_matched_activity_id": res["v3_matched_activity_id"],
            "raw_winner_activity_id": res["raw_winner_activity_id"],
            "raw_winner_similarity": res["raw_winner_similarity"],
        }


def repair_policy() -> dict[str, Any]:
    """The frozen repair policy, for the manifest and diagnostics."""
    return {
        "repair_id": REPAIR_ID,
        "scope": REPAIR_SCOPE,
        "base_method": "s3_extended_v3_adapter.V3ExtendedScorer",
        "defects": REPAIR_NOTES,
        "unchanged": [
            "frozen panel and rule binding",
            "six-element extractor",
            "four candidate surfaces",
            "four frozen formulas and gamma_ext = 0.5",
            "unified five-class decision and its fixed EXTENDED_TYPES order",
            "evaluators and the observability policy",
            "v3 structured action representation (exact label, nested actions, roles, "
            "numerals, negation) as the first-choice matcher",
        ],
        "forbidden": [
            "no threshold lowered, searched or selected per item",
            "no sample id, rule id, target activity id, mutation text or expected label read",
            "no legal vocabulary, synonym list or whitelist",
            "no decision that a missing candidate means compliant or violated",
        ],
        "extended_types": list(EXTENDED_TYPES),
        "outcomes": [DECISION_MAPPED, DECISION_UNDETERMINED, DECISION_NOT_SATISFIED,
                     RESOLVED_BY_ACTION_GAMMA],
    }

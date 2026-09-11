# -*- coding: utf-8 -*-
"""S3.9-EXT limited repair (v2): consistent whitespace, real v3 gamma, no forced resolution.

Three confirmed problems of the previous batch drive this module:

**R1 - the "v3 + 0.4" arm never changed v3's threshold.**
``scripts/run_s3_extended_v3_gamma04_v1.py`` read ``gamma = 0.8`` from the Sun
config and constructed ``EvidenceChecksV3(sim, tau=0.8, gamma=0.8, theta=0.8)``;
``ACTION_GAMMA = 0.4`` reached only the outer adapter.  The stored rows say so
themselves (``action_mapping_gamma=0.4`` next to
``v3_thresholds={"gamma": 0.8, ...}``).  Nothing in that artifact can support a
claim about v3's own threshold, and the conclusion "the threshold is inert" is
withdrawn.  :class:`ConsistentRawScorer` therefore takes the v3 instance as an
argument, and the runner asserts that the instance's own ``gamma`` equals the
arm's declared gamma **before any scoring happens**.

**R2 - whitespace asymmetry between the two sides of a comparison.**
``RepairedExtendedScorer._raw_best_action`` folded the rule action
(``" ".join(text.split())``) but passed the **raw** activity label.  The frozen
GDPR-7 models contain labels with a trailing newline
(``'Communicate the rectification\\n'``).  Measured on the frozen panel:

===========================  ====================  ====================
pair                          raw label             folded label
===========================  ====================  ====================
``constraint_violated_03``    0.282807              0.483290
``required_condition_10``     0.266066              0.466753
===========================  ====================  ====================

0.4 sits between the two values, so the trailing newline decided two hits that
the previous batch attributed to the new action resolution.  This module folds
**both** sides through one function and records the before/after strings, so the
whitespace effect is measurable in isolation
(:class:`NormalizedRawScorer` is exactly the frozen label-argmax path plus that
folding).

**R3 - no forced resolution when the matcher is undetermined, and no arbitrary
winner among equal scores.**  ``RepairedExtendedScorer.resolve_action`` fell
back to the raw label argmax whenever v3 did not return a *satisfying* match,
which includes v3's ``undetermined`` verdict, and ``max()`` silently picked the
first activity among equal top scores.  Here:

* v3 ``undetermined`` (``ambiguous_action_mapping``) -> the action is **not**
  resolved; every check that needs one activity stays unobservable;
* the raw fallback returns the full tie set; a tie spanning **different**
  activity ids is not resolved either;
* the prohibition **presence** check stays separate: it compares the rule action
  against the process activity labels and never needed one specific activity, so
  it is not gated by resolution (its score is still the raw-label maximum).

Nothing else is changed: the frozen panel, the rule binding, the six-element
extractor, the four candidate surfaces, the four formulas, ``gamma_ext``, the
unified five-class decision and its fixed type order, the evaluators and the
observability policy are all inherited.
"""

from __future__ import annotations

from typing import Any

from bpc_hybrid.s3_extended_v3_adapter import (  # noqa: E402
    ADAPTER_ID,
    DECISION_MAPPED,
    DECISION_UNDETERMINED,
    V3ExtendedScorer,
)
from bpc_hybrid.s3_extended_v3_repair import (  # noqa: E402
    REPAIR_ID,
    RESOLVED_BY_ACTION_GAMMA,
    RESOLVED_BY_V3_MATCH,
    RESOLVED_NONE,
    RepairedExtendedScorer,
    _model_identity,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    NONE_LABEL,
    ConstraintSurface,
    ExtendedViolationScorer,
    detect_exact_constraint_contradiction,
)

REPAIR_V2_ID = "s3_extended_v3_repair@2.0.0"
NORMALIZER_ID = "s3_extended_original_path_normalized@1.0.0"
REPAIR_V2_SCOPE = "consistent whitespace, real v3 gamma, no forced resolution"

# why an action could not be resolved to exactly one activity
UNRESOLVED_V3_UNDETERMINED = "v3_localization_undetermined"
UNRESOLVED_RAW_TIE = "label_argmax_tie_on_different_activities"
UNRESOLVED_BELOW_GAMMA = "label_argmax_below_action_gamma"
UNRESOLVED_EMPTY = "no_labelled_process_activity"


def fold_whitespace(text: str) -> str:
    """The one normalisation this batch applies: collapse runs, strip the ends.

    It never removes, adds, reorders or rewrites a character other than
    whitespace, so token identity, node ids and candidate identity are unchanged.
    """
    return " ".join((text or "").split())


def repair_v2_policy() -> dict[str, Any]:
    """The frozen policy of this limited repair, for the plan and the manifest."""
    return {
        "module": REPAIR_V2_ID,
        "normalizer": NORMALIZER_ID,
        "scope": REPAIR_V2_SCOPE,
        "changes": {
            "R1_real_v3_gamma": (
                "the v3 instance is constructed with the arm's declared gamma and the "
                "runner asserts instance gamma == declared gamma == outer adapter gamma "
                "before any scoring"
            ),
            "R2_consistent_whitespace": (
                "rule action and activity label both pass through fold_whitespace() "
                "before the similarity call; the before/after strings and scores are "
                "recorded per candidate"
            ),
            "R3_no_forced_resolution": (
                "v3 undetermined, a raw-argmax tie across different activity ids, and a "
                "raw-argmax below the action gamma all leave the action unresolved; "
                "checks that need one activity stay unobservable"
            ),
            "R4_explicit_compliance_requires_a_comparison": (
                "a check that abstains must not license the aggregate answer 'explicitly "
                "compliant': the aggregate returns 'none' only when at least one check "
                "actually compared the rule element against process evidence, and an "
                "abstention when none did"
            ),
        },
        "unchanged": [
            "frozen panel, rule binding and six-element extractor",
            "four candidate surfaces",
            "four frozen formulas and gamma_ext = 0.5",
            "unified five-class decision and its fixed EXTENDED_TYPES order",
            "evaluators and the observability policy",
            "v3 structured action representation as the first-choice matcher",
        ],
        "not_claimed": [
            "no threshold other than the pre-specified ones is introduced",
            "the prohibition presence check is not gated by resolution and this is "
            "reported separately from the checks that need one activity",
            "an unresolvable action is never written as compliant or violated",
        ],
    }


# how a type abstained; only ABSTAIN_RULE_ELEMENT_EMPTY means the check had nothing
# to check, both reasons block the aggregate 'explicitly compliant' answer
ABSTAIN_ACTION_NOT_RESOLVED = "action_not_resolved_to_one_activity"
ABSTAIN_RULE_ELEMENT_EMPTY = "rule_element_empty"


def aggregate_with_comparison_gate(side_scores: dict[str, Any],
                                   gamma_ext: float) -> dict[str, Any]:
    """The five-class decision, with 'none' reserved for a real comparison.

    ``control_prediction_from_scores`` answers ``none`` as soon as no observed
    type violated.  On this panel that answer is produced even when *no* check
    could compare anything - for example a row whose only observed type is the
    prohibition presence check, which never needed a resolved activity.  Such a
    row was reported as "explicitly compliant" although nothing was examined.

    Required here: the aggregate ``none`` needs at least one performed comparison
    **of a check that verifies a specific rule element against process evidence**,
    i.e. condition, constraint or exception.  The prohibition presence check is
    excluded from that licence: it answers "is this forbidden action present" and
    is silent about whether a given requirement is enforced, so it cannot carry a
    compliance statement on its own.  A row where every evidence check abstained
    stays an abstention, whatever the prohibition score says.
    """
    per_type: dict[str, Any] = {}
    for t in EXTENDED_TYPES:
        entry = dict(side_scores.get(t) or {})
        if not entry.get("observable"):
            per_type[t] = None
            continue
        score = entry.get("score")
        if t == "prohibited_action_present":
            per_type[t] = score is not None and score >= gamma_ext
        elif t == "constraint_violated":
            contradiction = bool((entry.get("exact_contradiction") or {})
                                 .get("contradiction"))
            per_type[t] = (score is not None and score > gamma_ext) or contradiction
        else:
            per_type[t] = score is not None and score > gamma_ext
    any_observable = any(v is not None for v in per_type.values())
    evidence_checks = tuple(t for t in EXTENDED_TYPES
                            if t != "prohibited_action_present")
    comparisons = sum(1 for t in evidence_checks
                      if side_scores.get(t, {}).get("comparison_performed"))
    predicted = next((t for t in EXTENDED_TYPES if per_type.get(t) is True), None)
    if predicted is None:
        predicted = NONE_LABEL if (any_observable and comparisons > 0) else None
    return {
        "predicted": predicted,
        "per_type": per_type,
        "all_unobservable": not any_observable,
        "evidence_comparisons_performed": comparisons,
        "prohibition_comparison_performed": bool(
            side_scores.get("prohibited_action_present", {})
            .get("comparison_performed")),
        "explicit_compliance_requires_an_evidence_comparison": True,
    }


class ArmAScorer(V3ExtendedScorer):
    """Arm A: the existing v3 adapter, only with the comparison flag recorded.

    No behaviour is changed.  The flag lets the shared reporting layer tell "this
    check compared the rule element against process evidence and found nothing"
    apart from "this check never ran", for every arm by the same rule.
    """

    method_id = ADAPTER_ID + "+comparison_flag"

    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        result = dict(super().prohibited_action(sentence, model))
        result["comparison_performed"] = bool(result.get("observable"))
        return result

    def _missing_evidence(self, field: str, sentence: dict[str, Any], model: Any,
                          candidates: list[str], violation_type: str) -> dict[str, Any]:
        result = dict(super()._missing_evidence(field, sentence, model, candidates,
                                                violation_type))
        result["comparison_performed"] = bool(result.get("observable"))
        return result

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        result = dict(super().constraint_violated(sentence, model, candidates))
        result["comparison_performed"] = bool(result.get("observable"))
        return result


class ConsistentRawScorer(ExtendedViolationScorer):
    """The frozen original label-argmax path with one whitespace fold on both sides.

    Used as arm B to isolate the whitespace factor with v3 switched off.  The
    formulas, the candidate surfaces, ``gamma_ext`` and the decision rule are the
    frozen ones; ``_best_action`` is the frozen argmax, except that the compared
    strings are folded first.
    """

    method_id = NORMALIZER_ID

    def __init__(self, sim_action, sim_text, gamma: float, gamma_ext: float = 0.5):
        super().__init__(sim_action, sim_text, gamma, gamma_ext)
        self._fold_cache: dict[tuple, dict[str, Any]] = {}

    def _best_action(self, action_text: str, model: Any) -> tuple[float, str | None, str | None]:
        folded_action = fold_whitespace(action_text)
        key = (_model_identity(model), folded_action)
        cached = self._fold_cache.get(key)
        if cached is None:
            best = 0.0
            best_name: str | None = None
            best_id: str | None = None
            tied: set[str] = set()
            rows: list[dict[str, Any]] = []
            for act in model.actions:
                name = act.get("name") or ""
                if not name.strip():
                    continue
                folded = fold_whitespace(name)
                score = float(self.sim_action(folded_action, folded))
                rows.append({"activity_id": act["id"], "label": name,
                             "label_folded": folded, "score": score})
                if score > best:
                    best, best_name, best_id = score, name, act["id"]
                    tied = {act["id"]}
                elif score == best and best_name is not None:
                    tied.add(act["id"])
            cached = {"score": best, "label": best_name, "activity_id": best_id,
                      "tied_activity_ids": sorted(tied), "candidates": rows}
            self._fold_cache[key] = cached
        return cached["score"], cached["label"], cached["activity_id"]

    def _missing_evidence(self, field: str, sentence: dict[str, Any], model: Any,
                          candidates: list[str], violation_type: str) -> dict[str, Any]:
        """The frozen code path, with the comparison flag recorded beside it."""
        result = dict(super()._missing_evidence(field, sentence, model, candidates,
                                                violation_type))
        result["comparison_performed"] = bool(result.get("observable"))
        return result

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        result = dict(super().constraint_violated(sentence, model, candidates))
        result["comparison_performed"] = bool(result.get("observable"))
        return result

    def folded_evidence(self, action_text: str, model: Any) -> dict[str, Any]:
        """The recorded comparison strings and scores (diagnostics only)."""
        folded_action = fold_whitespace(action_text)
        key = (_model_identity(model), folded_action)
        if key not in self._fold_cache:
            self._best_action(action_text, model)
        record = self._fold_cache[key]
        return {"rule_action_folded": folded_action,
                "candidates": record["candidates"],
                "winner_activity_id": record["activity_id"],
                "tied_activity_ids": record["tied_activity_ids"]}


class RepairedExtendedScorerV2(RepairedExtendedScorer):
    """The previous repair with the whitespace asymmetry and the forced fallback removed.

    Inheritance chain: ``V3ExtendedScorer`` -> ``RepairedExtendedScorer`` -> here.
    Only the raw-label fallback and the resolution rule are overridden.
    """

    method_id = REPAIR_V2_ID

    def __init__(self, v3, sim_text, gamma_action: float, gamma_ext: float = 0.5):
        super().__init__(v3, sim_text, gamma_action, gamma_ext)
        self._fold_cache: dict[tuple, dict[str, Any]] = {}

    # ------------------------------------------------------- raw label fallback
    def _raw_best_action(self, action_text: str, model: Any) -> dict[str, Any]:
        """Frozen argmax formula on folded strings, with its full tie set.

        The previous version folded the rule action but not the label, which made
        a trailing newline in an activity label change the compared text and the
        score.  Both sides are folded here, and the recorded candidate table keeps
        the raw label, the folded label and the score so the difference is
        auditable.
        """
        folded_action = fold_whitespace(action_text)
        key = (_model_identity(model), folded_action)
        cached = self._fold_cache.get(key)
        if cached is not None:
            return cached
        best = 0.0
        best_name: str | None = None
        best_id: str | None = None
        tied: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for act in model.actions:
            name = act.get("name") or ""
            if not name.strip():
                continue
            folded = fold_whitespace(name)
            score = float(self.sim_text(folded_action, folded))
            candidates.append({"activity_id": act["id"], "label": name,
                               "label_folded": folded, "score": score})
            if score > best:
                best, best_name, best_id = score, name, act["id"]
                tied = {act["id"]}
            elif score == best and best_name is not None:
                tied.add(act["id"])
        result = {
            "score": best,
            "label": best_name,
            "activity_id": best_id,
            "tied_activity_ids": sorted(tied),
            "candidate_count": len(candidates),
            "rule_action_folded": folded_action,
            "whitespace_normalised": True,
            "candidates": candidates,
        }
        self._fold_cache[key] = result
        return result

    # ------------------------------------------------------- action resolution
    def resolve_action(self, action_text: str, model: Any) -> dict[str, Any]:
        """One reference activity, or an explicit refusal to choose one."""
        key = (_model_identity(model), fold_whitespace(action_text))
        cached = self._resolution_cache.get(key)
        if cached is not None:
            return cached
        loc = self.localize(action_text, model)
        raw = self._raw_best_action(action_text, model)
        resolved_id = None
        resolved_label = None
        resolved_by = RESOLVED_NONE
        unresolved_reason = None
        if loc["decision"] == DECISION_MAPPED and loc["matched_activity_id"]:
            resolved_id = loc["matched_activity_id"]
            resolved_label = loc["matched_activity_label"]
            resolved_by = RESOLVED_BY_V3_MATCH
        elif loc["decision"] == DECISION_UNDETERMINED:
            # v3 says it cannot tell which activity is meant; an argmax must not
            # manufacture the certainty v3 refused to give.
            unresolved_reason = UNRESOLVED_V3_UNDETERMINED
        elif len(raw["tied_activity_ids"]) > 1:
            # several activities share the top score: no evidence separates them
            unresolved_reason = UNRESOLVED_RAW_TIE
        elif raw["activity_id"] is None:
            unresolved_reason = UNRESOLVED_EMPTY
        elif raw["score"] < self.gamma:
            unresolved_reason = UNRESOLVED_BELOW_GAMMA
        else:
            resolved_id = raw["activity_id"]
            resolved_label = raw["label"]
            resolved_by = RESOLVED_BY_ACTION_GAMMA
        result = {
            "action_resolution": REPAIR_V2_ID,
            "based_on": REPAIR_ID,
            "rule_action_text": " ".join((action_text or "").split()),
            "rule_action_folded": raw["rule_action_folded"],
            "whitespace_normalised": True,
            "resolved_activity_id": resolved_id,
            "resolved_activity_label": resolved_label,
            "resolved_by": resolved_by,
            "unresolved_reason": unresolved_reason,
            "resolved_score": round(raw["score"], 6),
            "resolved_score_is_action_bound": True,
            "resolved_gate": "orig_raw_label_argmax_at_or_above_action_gamma",
            "action_gamma": self.gamma,
            "v3_internal_gamma": getattr(self.v3, "gamma", None),
            "candidate_count": raw["candidate_count"],
            "raw_tie_activity_ids": raw["tied_activity_ids"],
            "raw_winner_activity_id": raw["activity_id"],
            "raw_winner_label": raw["label"],
            "raw_winner_similarity": round(raw["score"], 6),
            "v3_decision": loc["decision"],
            "v3_match_tier": loc["match_tier"],
            "v3_reason": loc["reason"],
            "v3_matched_activity_id": loc["matched_activity_id"],
            "v3_winner_activity_id": loc["winner_activity_id"],
            "v3_winner_similarity": round(loc["winner_similarity"], 6),
            "v3_candidate_max_similarity": round(loc["candidate_max_similarity"], 6),
        }
        self._resolution_cache[key] = result
        return result

    # ------------------------------------------------------------ the 4 checks
    def _missing_evidence(self, field: str, sentence: dict[str, Any], model: Any,
                          candidates: list[str], violation_type: str) -> dict[str, Any]:
        """Evidence is consumed only for an action resolved to exactly one activity."""
        rule_value = (sentence.get(field) or "").strip()
        if not rule_value:
            return {"score": None, "observable": False, "reason": f"empty_rule_{field}",
                    "comparison_performed": False,
                    "abstention_kind": ABSTAIN_RULE_ELEMENT_EMPTY}
        res = self.resolve_action(sentence.get("action") or "", model)
        if res["resolved_activity_id"] is None:
            return {
                "score": None,
                "observable": False,
                "reason": res["unresolved_reason"] or "action_not_resolvable_to_activity",
                "action_max_sim": res["resolved_score"],
                "action_best_candidate": res["raw_winner_label"],
                "matched_activity_id": None,
                "comparison_performed": False,
                "abstention_kind": ABSTAIN_ACTION_NOT_RESOLVED,
                "action_resolution": REPAIR_V2_ID,
                **self._resolution_trace(res),
            }
        if not candidates:
            return {"score": None, "observable": False,
                    "reason": f"no_{field}_candidates",
                    "action_max_sim": res["resolved_score"],
                    "best_candidate": None,
                    "matched_activity_id": res["resolved_activity_id"],
                    "comparison_performed": False,
                    "abstention_kind": f"no_{field}_candidates",
                    "action_resolution": REPAIR_V2_ID,
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
            "comparison_performed": True,
            "violation": score > self.gamma_ext,
            "violation_type": violation_type,
            "action_resolution": REPAIR_V2_ID,
            **self._resolution_trace(res),
        }

    def prohibited_action(self, sentence: dict[str, Any], model: Any) -> dict[str, Any]:
        """Presence check: no single-activity resolution is needed, and it is not gated.

        The frozen formula is ``max sim(rule_action, process_activity)`` over the
        process activities.  Whether one of them is *the* action the rule means is
        a different question, answered by the resolution record; this check only
        reports whether a prohibited action is present in the process and how
        similar the closest activity label is.
        """
        if sentence.get("modality") != "prohibition":
            return {"score": None, "observable": False,
                    "reason": "rule_modality_not_prohibition",
                    "comparison_performed": False}
        action_text = (sentence.get("action") or "").strip()
        if not action_text:
            return {"score": None, "observable": False, "reason": "empty_rule_action",
                    "comparison_performed": False}
        raw = self._raw_best_action(action_text, model)
        if raw["activity_id"] is None:
            return {"score": None, "observable": False,
                    "reason": "no_process_actions",
                    "action_resolution": REPAIR_V2_ID,
                    "resolution_required": False,
                    "comparison_performed": False,
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
            "action_resolution": REPAIR_V2_ID,
            "resolution_required": False,
            "comparison_performed": True,
            "raw_tie_activity_ids": raw["tied_activity_ids"],
            "rule_action_folded": raw["rule_action_folded"],
            "candidate_count": raw["candidate_count"],
        }

    def constraint_violated(self, sentence: dict[str, Any], model: Any,
                            candidates: list[str]) -> dict[str, Any]:
        base = self._missing_evidence("constraint", sentence, model, candidates,
                                      "constraint_violated")
        constraint = fold_whitespace((sentence.get("constraint") or "").lower())
        condition = fold_whitespace((sentence.get("condition") or "").lower())
        res = self.resolve_action(sentence.get("action") or "", model)
        contradiction = {"contradiction": False, "reason": "no_action_bound_time_evidence"}
        if res["resolved_activity_id"] is None:
            contradiction["reason"] = res["unresolved_reason"] or "action_not_resolvable"
        elif constraint and constraint in condition:
            contradiction["reason"] = "time_bound_inside_condition"
        elif isinstance(candidates, ConstraintSurface) \
                and candidates.activity_id == res["resolved_activity_id"]:
            contradiction = detect_exact_constraint_contradiction(
                sentence.get("constraint") or "", candidates.bound_texts)
        base["exact_contradiction"] = contradiction
        if contradiction.get("contradiction"):
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
            "unresolved_reason": res["unresolved_reason"],
            "raw_tie_activity_ids": res["raw_tie_activity_ids"],
            "v3_decision": res["v3_decision"],
            "v3_match_tier": res["v3_match_tier"],
            "v3_reason": res["v3_reason"],
            "v3_matched_activity_id": res["v3_matched_activity_id"],
            "raw_winner_activity_id": res["raw_winner_activity_id"],
            "raw_winner_similarity": res["raw_winner_similarity"],
        }

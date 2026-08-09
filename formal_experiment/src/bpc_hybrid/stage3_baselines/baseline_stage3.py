# -*- coding: utf-8 -*-
"""Shared S3.6 non-LLM baseline scoring over the canonical Stage 3 inputs.

Both arms (BM25 lexical, TF-IDF/SVD dense) share this scorer; the injected
similarity factory provides TWO candidate-domain functions per model:
``action_sim(query, action_label)`` and ``actor_sim(query, actor_or_bo)``.
This is required because BM25 action retrieval and actor/business-object
retrieval use different candidate pools (the v1/v2 defect was a single
corpus-blind function). Mapping semantics mirror the Sun Definitions 4-7
structure with the arm's similarity backend:

- matching score = max(avg best rule-action similarity, avg best rule-actor
  similarity) (pre-registered formula; binary = score > tau);
- missing_action = fraction of rule actions with best similarity < gamma;
- incorrect_actor = Definition-6-style exists-low-similarity over R/C sets;
- out_of_order = Definition-7-style forward/backward reachability over
  mapped order relations, using the TRUE mapped action ids.

Best-match resolution is deterministic: iterate the model's actions in their
stable parsed order, keep the first candidate at the maximum score
(tie-breaking: score desc, first-seen order). Duplicate labels therefore map
to the first parsed id deterministically. The scorer's gamma/theta affect
mappings, R/C sets, denominators and observability (see the sensitivity
scripts: sweeps must re-instantiate the scorer).
"""

from __future__ import annotations

from typing import Any, Callable

SimFn = Callable[[str, str], float]
SimsFactory = Callable[[Any], dict[str, SimFn]]


class BaselineScorer:
    def __init__(self, sims_factory: SimsFactory, tau: float, gamma: float, theta: float):
        self.sims_factory = sims_factory
        self.tau = tau
        self.gamma = gamma
        self.theta = theta

    def _sims(self, model: Any) -> dict[str, SimFn]:
        sims = self.sims_factory(model)
        if "action" not in sims or "actor" not in sims:
            raise RuntimeError("sims_factory must return {'action': fn, 'actor': fn}")
        return sims

    def _best_action(self, text: str, model: Any) -> tuple[str | None, str | None, float]:
        """Return (action_id, action_label, score) of the best-matching
        action candidate. Deterministic tie-breaking: score desc, first-seen
        in the model's stable parsed action order."""
        sim = self._sims(model)["action"]
        best_id, best_label, best_score = None, None, 0.0
        for act in model.actions:
            if not act["name"]:
                continue
            s = sim(text, act["name"])
            if s > best_score:
                best_score, best_id, best_label = s, act["id"], act["name"]
        return best_id, best_label, best_score

    def _best_actor(self, text: str, model: Any) -> tuple[str | None, float, str | None]:
        """Return (label, score, kind) over actor/pool/lane and business-object
        candidates (the actor domain, independent of the action domain)."""
        sim = self._sims(model)["actor"]
        best, best_score, best_kind = None, 0.0, None
        for actor in model.actors:
            s = sim(text, actor)
            if s > best_score:
                best_score, best = s, actor
                best_kind = model.actor_sources.get(actor, "actor")
        for bo in model.business_objects:
            s = sim(text, bo["object"])
            if s > best_score:
                best_score, best = s, bo["object"]
                best_kind = "business_object"
        return best, best_score, best_kind

    def matching_score(self, rule_actions: list[str], rule_actors: list[str],
                       model: Any) -> dict[str, Any]:
        action_sims = [self._best_action(a, model)[2] for a in rule_actions]
        actor_sims = [self._best_actor(a, model)[1] for a in rule_actors]
        avg_a = sum(action_sims) / len(action_sims) if action_sims else 0.0
        avg_o = sum(actor_sims) / len(actor_sims) if actor_sims else 0.0
        score = max(avg_a, avg_o) if (action_sims or actor_sims) else 0.0
        return {"matching_score": score, "action_sim": avg_a, "actor_sim": avg_o,
                "predicted_relevance": score > self.tau}

    def missing_action(self, rule_actions: list[str], model: Any) -> dict[str, Any]:
        denominator = len(rule_actions)
        missing = sum(1 for a in rule_actions if self._best_action(a, model)[2] < self.gamma)
        return {"score": (missing / denominator) if denominator else 0.0,
                "denominator": denominator, "missing": missing}

    def incorrect_actor(self, rule_actions: list[str], rule_actors: list[str],
                        model: Any) -> dict[str, Any]:
        if not rule_actors:
            return {"score": None, "denominator": 0, "observable": False,
                    "reason": "empty_rule_actor_denominator"}
        if not model.actors and not model.business_objects:
            return {"score": None, "denominator": 0, "observable": False,
                    "reason": "no_actor_labels"}
        sim = self._sims(model)["actor"]
        r_set = []
        for ra in rule_actors:
            best_action_score = max(
                (self._best_action(a, model)[2] for a in rule_actions), default=0.0)
            if best_action_score > self.gamma:
                r_set.append(ra)
        if not r_set:
            return {"score": 0.0, "denominator": 0, "observable": False,
                    "reason": "action_mapping_below_gamma"}
        # C: Definition 6's process actors/business objects performing the
        # matched action; development approximation = process-level actor set
        # (pool + non-empty lane names) plus business objects (disclosed).
        c_set = list(model.actors)
        c_set.extend(bo["object"] for bo in model.business_objects)
        if not c_set:
            return {"score": None, "denominator": len(r_set), "observable": False,
                    "reason": "no_matching_process_actor"}
        violations = 0
        for ra in r_set:
            min_sim = min((sim(ra, c) for c in c_set), default=1.0)
            if min_sim < self.theta:
                violations += 1
        return {"score": (violations / len(r_set)) if r_set else 0.0,
                "denominator": len(r_set), "observable": True,
                "violations": violations}

    def out_of_order(self, order_relations: list[tuple[str, str]],
                     rule_actions: list[str], model: Any) -> dict[str, Any]:
        denominator = 0
        satisfied = 0
        for before_text, after_text in order_relations:
            before_id, before_label, before_score = self._best_action(before_text, model)
            after_id, after_label, after_score = self._best_action(after_text, model)
            if before_id is None or after_id is None:
                continue
            if before_score <= self.gamma or after_score <= self.gamma:
                continue
            denominator += 1
            forward = model.is_reachable(before_id, after_id)
            backward = model.is_reachable(after_id, before_id)
            if forward and not backward:
                satisfied += 1
        return {"score": ((denominator - satisfied) / denominator) if denominator else 0.0,
                "denominator": denominator, "satisfied": satisfied,
                "violations": denominator - satisfied}

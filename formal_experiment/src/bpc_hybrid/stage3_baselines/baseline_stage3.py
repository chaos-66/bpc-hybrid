# -*- coding: utf-8 -*-
"""Shared S3.6 non-LLM baseline scoring over the canonical Stage 3 inputs.

Both arms (BM25 lexical, TF-IDF/SVD dense) share this scorer: the only
difference is the injected text-similarity function. Mapping semantics mirror
the Sun Definitions 4-7 structure but with the arm's similarity backend:

- matching score = max(avg best rule-action similarity, avg best rule-actor
  similarity) (pre-registered formula; binary = score > tau);
- missing_action = fraction of rule actions with best similarity < gamma;
- incorrect_actor = Definition-6-style exists-low-similarity over R/C sets;
- out_of_order = Definition-7-style forward/backward reachability over
  mapped order relations.

Unlike Sun (whose gamma changes the mapping sets), the baseline mappings do
NOT depend on gamma/theta, so gamma/theta sensitivity can re-threshold the
fixed scores legitimately (documented in the sensitivity note).
"""

from __future__ import annotations

from typing import Any, Callable

SimFn = Callable[[str, str], float]
ModelSimFactory = Callable[[Any], SimFn]


class BaselineScorer:
    def __init__(self, model_sim_factory: ModelSimFactory, tau: float, gamma: float, theta: float):
        self.model_sim_factory = model_sim_factory
        self.tau = tau
        self.gamma = gamma
        self.theta = theta

    def _sim(self, model: Any) -> SimFn:
        return self.model_sim_factory(model)

    def _best_action(self, text: str, model: Any) -> tuple[str | None, float]:
        sim = self._sim(model)
        best, best_score = None, 0.0
        for act in model.actions:
            if not act["name"]:
                continue
            s = sim(text, act["name"])
            if s > best_score:
                best_score, best = s, act["name"]
        return best, best_score

    def _best_actor(self, text: str, model: Any) -> tuple[str | None, float]:
        sim = self._sim(model)
        best, best_score, = None, 0.0
        for actor in model.actors:
            s = sim(text, actor)
            if s > best_score:
                best_score, best = s, actor
        for bo in model.business_objects:
            s = sim(text, bo["object"])
            if s > best_score:
                best_score, best = s, bo["object"]
        return best, best_score

    def matching_score(self, rule_actions: list[str], rule_actors: list[str],
                       model: Any) -> dict[str, Any]:
        action_sims = [self._best_action(a, model)[1] for a in rule_actions]
        actor_sims = [self._best_actor(a, model)[1] for a in rule_actors]
        avg_a = sum(action_sims) / len(action_sims) if action_sims else 0.0
        avg_o = sum(actor_sims) / len(actor_sims) if actor_sims else 0.0
        score = max(avg_a, avg_o) if (action_sims or actor_sims) else 0.0
        return {"matching_score": score, "action_sim": avg_a, "actor_sim": avg_o,
                "predicted_relevance": score > self.tau}

    def missing_action(self, rule_actions: list[str], model: Any) -> dict[str, Any]:
        denominator = len(rule_actions)
        missing = sum(1 for a in rule_actions if self._best_action(a, model)[1] < self.gamma)
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
        r_set = []
        for ra in rule_actors:
            best_action_score = max(
                (self._best_action(a, model)[1] for a in rule_actions), default=0.0)
            if best_action_score > self.gamma:
                r_set.append(ra)
        if not r_set:
            return {"score": 0.0, "denominator": 0, "observable": False,
                    "reason": "action_mapping_below_gamma"}
        c_set = list(model.actors)
        c_set.extend(bo["object"] for bo in model.business_objects)
        if not c_set:
            return {"score": None, "denominator": len(r_set), "observable": False,
                    "reason": "no_matching_process_actor"}
        violations = 0
        for ra in r_set:
            min_sim = min((self._sim(model)(ra, c) for c in c_set), default=1.0)
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
            before_name, before_score = self._best_action(before_text, model)
            after_name, after_score = self._best_action(after_text, model)
            if before_name is None or after_name is None:
                continue
            if before_score <= self.gamma or after_score <= self.gamma:
                continue
            denominator += 1
            before_id = self._action_id(model, before_name)
            after_id = self._action_id(model, after_name)
            forward = model.is_reachable(before_id, after_id) if before_id and after_id else False
            backward = model.is_reachable(after_id, before_id) if before_id and after_id else False
            if forward and not backward:
                satisfied += 1
        return {"score": ((denominator - satisfied) / denominator) if denominator else 0.0,
                "denominator": denominator, "satisfied": satisfied,
                "violations": denominator - satisfied}

    def _action_id(self, model: Any, name: str) -> str | None:
        for act in model.actions:
            if act["name"] == name:
                return act["id"]
        return None

# -*- coding: utf-8 -*-
"""Sun et al. (2024) Stage 3: matching score and the three violation scores
(paper section 4.3 Definitions 4-7). Method-level independent reconstruction;
thresholds (tau/gamma/theta) live in the versioned config, never tuned on
this project's Gold.
"""

from __future__ import annotations

from typing import Any


class SunScorer:
    def __init__(self, sim, tau: float, gamma: float, theta: float, nlp=None):
        self.sim = sim
        self.tau = tau
        self.gamma = gamma
        self.theta = theta
        self.nlp = nlp
        self._lemma_cache: dict[str, str] = {}

    def _lemma(self, text: str) -> str:
        """Lemmatized text for similarity comparisons, aligned with the
        Winter baseline (same spaCy backend, controlled comparison)."""
        if self.nlp is None:
            return text
        cached = self._lemma_cache.get(text)
        if cached is None:
            cached = " ".join(
                w.lemma_ if w.lemma_ != "-PRON-" else w.text
                for w in self.nlp(text)
                if not w.is_punct and not w.is_space
            )
            self._lemma_cache[text] = cached
        return cached

    # ------------------------------------------------------------- Definition 4
    def matching_score(self, rule_actions: list[str], rule_actors: list[str],
                       model: Any) -> dict[str, Any]:
        """matching(r,m,tau) = max( fraction of Dr,m with sim>tau,
        fraction of Or,m with sim>tau )."""
        d_count = len(rule_actions)
        o_count = len(rule_actors)
        d_over = 0
        d_best: list[tuple[str, str, float]] = []
        for ra in rule_actions:
            best, best_score = self._best_action_match(ra, model)
            d_best.append((ra, best, best_score))
            if best is not None and best_score > self.tau:
                d_over += 1
        o_over = 0
        o_best: list[tuple[str, str, float, str]] = []
        for ra in rule_actors:
            best, best_score, kind = self._best_actor_match(ra, model)
            o_best.append((ra, best, best_score, kind))
            if best is not None and best_score > self.tau:
                o_over += 1
        d_ratio = (d_over / d_count) if d_count else 0.0
        o_ratio = (o_over / o_count) if o_count else 0.0
        score = max(d_ratio, o_ratio) if (d_count or o_count) else 0.0
        return {
            "matching_score": score,
            "action_ratio": d_ratio,
            "actor_object_ratio": o_ratio,
            "action_map": d_best,
            "actor_object_map": o_best,
        }

    def _best_action_match(self, rule_action: str, model: Any):
        best_score = 0.0
        best_name = None
        rule_lemma = self._lemma(rule_action)
        for act in model.actions:
            if not act["name"]:
                continue
            score = self.sim.text_pair(rule_lemma, self._lemma(act["name"]))
            if score > best_score:
                best_score = score
                best_name = act["name"]
        return best_name, best_score

    def _best_actor_match(self, rule_actor: str, model: Any):
        best_score = 0.0
        best_name = None
        best_kind = None
        rule_lemma = self._lemma(rule_actor)
        # actors first (pool/lane names), then business objects
        for actor in model.actors:
            score = self.sim.text_pair(rule_lemma, self._lemma(actor))
            if score > best_score:
                best_score = score
                best_name = actor
                best_kind = model.actor_sources.get(actor, "actor")
        for bo in model.business_objects:
            score = self.sim.text_pair(rule_lemma, self._lemma(bo["object"]))
            if score > best_score:
                best_score = score
                best_name = bo["object"]
                best_kind = "business_object"
        return best_name, best_score, best_kind

    # ------------------------------------------------------------ Definition 5
    def missing_action(self, rule_actions: list[str], model: Any) -> dict[str, Any]:
        """action violation = |{(ar,am) in Dr,m | sim(ar,am)<gamma}| / |Ar|"""
        denominator = len(rule_actions)
        missing = 0
        details = []
        for ra in rule_actions:
            best, best_score = self._best_action_match(ra, model)
            is_missing = best is None or best_score < self.gamma
            if is_missing:
                missing += 1
            details.append({
                "rule_action": ra,
                "best_model_action": best,
                "similarity": round(best_score, 4),
                "missing": is_missing,
            })
        score = (missing / denominator) if denominator else 0.0
        return {
            "score": score,
            "missing": missing,
            "denominator": denominator,
            "details": details,
        }

    # ------------------------------------------------------------ Definition 6
    def incorrect_actor(self, rule_actions: list[str], rule_actors: list[str],
                        model: Any) -> dict[str, Any]:
        """actor violation = |{r in R | exists r' in C, sim(r,r')<theta}| / |R|
        with R = rule actors whose action matched a process action (sim>gamma),
        C = process actors/business objects performing that action."""
        # R: rule actors assigned to a matched activity
        r_set = []
        matched_actions: dict[str, str] = {}  # rule actor -> matched process action
        for ra in rule_actors:
            best_action = None
            best_action_score = 0.0
            for act in model.actions:
                if not act["name"]:
                    continue
                score = self.sim.text_pair(
                    self._lemma(rule_actions[0] if rule_actions else ""),
                    self._lemma(act["name"]),
                )
                if score > best_action_score:
                    best_action_score = score
                    best_action = act["name"]
            # Definition 6 matches the actor's action; approximate with the
            # best action similarity over all rule actions when actors are
            # not tied to a single action in the development adapter
            actor_action_score = 0.0
            for rule_action in rule_actions:
                for act in model.actions:
                    if not act["name"]:
                        continue
                    score = self.sim.text_pair(
                        self._lemma(rule_action), self._lemma(act["name"])
                    )
                    if score > actor_action_score:
                        actor_action_score = score
            if actor_action_score > self.gamma:
                r_set.append(ra)
                matched_actions[ra] = best_action or ""
        if not r_set:
            return {
                "score": 0.0,
                "denominator": 0,
                "observable": False,
                "note": "no rule actor matched a process action above gamma; denominator 0 (N/A)",
                "details": [],
            }
        # C: process actors/business objects
        c_set = []
        for actor in model.actors:
            for ra in r_set:
                if self.sim.text_pair(self._lemma(ra), self._lemma(actor)) > self.gamma:
                    c_set.append(actor)
                    break
        for bo in model.business_objects:
            for ra in r_set:
                if self.sim.text_pair(self._lemma(ra), self._lemma(bo["object"])) > self.gamma:
                    c_set.append(bo["object"])
                    break
        violations = 0
        details = []
        if not c_set:
            # Definition 6 needs a process actor/object set to compare
            # against; without any observable process actor the check is
            # unobservable, never silently counted as compliant or violated
            return {
                "score": None,
                "denominator": len(r_set),
                "observable": False,
                "note": "rule actors matched a process action but no process actor/business-object is observable (empty pool/lane names); reported as unobservable",
                "details": [{"rule_actor": ra, "observable": False} for ra in r_set],
            }
        for ra in r_set:
            worst = 1.0
            for c in c_set:
                score = self.sim.text_pair(self._lemma(ra), self._lemma(c))
                if score < worst:
                    worst = score
            violated = worst < self.theta
            if violated:
                violations += 1
            details.append({
                "rule_actor": ra,
                "closest_process_actor_similarity": round(worst, 4),
                "violated": violated,
                "process_actor_set": c_set,
            })
        score = (violations / len(r_set)) if r_set else 0.0
        return {
            "score": score,
            "denominator": len(r_set),
            "observable": True,
            "violations": violations,
            "details": details,
        }

    # ------------------------------------------------------------ Definition 7
    def out_of_order(self, rule_order_relations: list[tuple[str, str]],
                     rule_actions: list[str], model: Any) -> dict[str, Any]:
        """order violation = (|Ur,m,gamma| - satisfied) / |Ur,m,gamma| with
        Ur,m,gamma = order constraints whose both endpoints map with sim>gamma,
        satisfied = forward reachable and not backward reachable."""
        denominator = 0
        satisfied = 0
        details = []
        for before_text, after_text in rule_order_relations:
            before_map = self._best_action_match(before_text, model)
            after_map = self._best_action_match(after_text, model)
            before_name, before_score = before_map
            after_name, after_score = after_map
            if before_name is None or after_name is None:
                details.append({
                    "constraint": (before_text, after_text),
                    "mapped": False,
                    "reason": "endpoint without a process action match",
                })
                continue
            if before_score <= self.gamma or after_score <= self.gamma:
                details.append({
                    "constraint": (before_text, after_text),
                    "mapped": False,
                    "reason": "endpoint similarity below gamma",
                })
                continue
            denominator += 1
            before_id = self._action_id_by_name(model, before_name)
            after_id = self._action_id_by_name(model, after_name)
            forward = model.is_reachable(before_id, after_id) if before_id and after_id else False
            backward = model.is_reachable(after_id, before_id) if before_id and after_id else False
            ok = forward and not backward
            if ok:
                satisfied += 1
            details.append({
                "constraint": (before_text, after_text),
                "mapped": True,
                "before_activity": before_name,
                "after_activity": after_name,
                "forward_reachable": forward,
                "backward_reachable": backward,
                "satisfied": ok,
            })
        score = ((denominator - satisfied) / denominator) if denominator else 0.0
        return {
            "score": score,
            "denominator": denominator,
            "satisfied": satisfied,
            "violations": denominator - satisfied,
            "details": details,
        }

    def _action_id_by_name(self, model: Any, name: str) -> str | None:
        for act in model.actions:
            if act["name"] == name:
                return act["id"]
        return None

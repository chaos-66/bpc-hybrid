# -*- coding: utf-8 -*-
"""R3 Sun scorer adapter.

Definitions 4-7 and all thresholds are inherited unchanged from the frozen
``SunScorer``.  Only the representation/mapping helpers are overridden:

* rule actions/endpoints carry an R3 P2 matching view;
* model actions use the model sidecar's P2 matching view;
* action candidates are returned as stable node IDs;
* equal scores are resolved by ascending node ID and all tied candidates are
  retained in the candidate evidence.
"""

from __future__ import annotations

from typing import Any, Mapping

from .sun_scorer import SunScorer


def _view_source(value: Any, attr: str = "match_source_text") -> str | None:
    if value is None:
        return None
    if hasattr(value, attr):
        source = getattr(value, attr)
        if isinstance(source, str) and source.strip():
            return source
        return None
    if isinstance(value, str) and value.strip():
        return value
    return None


class R3SunScorer(SunScorer):
    """SunScorer with P2 matching views and node-ID stable mapping."""

    def _model_action_source(self, action: Mapping[str, Any]) -> str | None:
        source = action.get("match_source_text")
        if isinstance(source, str) and source.strip():
            return source
        return None

    def _model_actor_source(self, model: Any, actor: str) -> str | None:
        source_map = getattr(model, "actor_match_sources", None) or {}
        if actor in source_map and str(source_map[actor]).strip():
            return str(source_map[actor])
        return actor if isinstance(actor, str) and actor.strip() else None

    def _rule_action_source(self, rule_action: Any) -> str | None:
        return _view_source(rule_action)

    def _rule_endpoint_source(self, endpoint: Any) -> str | None:
        return _view_source(endpoint)

    # --------------------------------------------------------- Definition 4
    def _best_action_match(self, rule_action: Any, model: Any) -> tuple[str | None, float]:
        source = self._rule_action_source(rule_action)
        if not source:
            return None, 0.0
        rule_text = self._lemma(source)
        candidates: list[tuple[float, str, Mapping[str, Any]]] = []
        for action in model.actions:
            model_source = self._model_action_source(action)
            if not model_source:
                continue
            score = float(self.sim.text_pair(rule_text, self._lemma(model_source)))
            candidates.append((score, str(action.get("id")), action))
        if not candidates:
            return None, 0.0
        best_score = max(row[0] for row in candidates)
        tied = [row for row in candidates if row[0] == best_score]
        best = min(tied, key=lambda row: row[1])
        return best[1], float(best_score)

    def action_candidate_evidence(self, rule_action: Any, model: Any) -> list[dict[str, Any]]:
        source = self._rule_action_source(rule_action)
        rows: list[dict[str, Any]] = []
        if not source:
            return [{
                "node_id": None,
                "node_type": None,
                "original_label": None,
                "match_source_text": None,
                "similarity": 0.0,
                "tied": False,
                "selected": False,
                "reason": "rule_action_has_no_p2_matching_source",
            }]
        rule_text = self._lemma(source)
        for action in model.actions:
            model_source = self._model_action_source(action)
            if not model_source:
                continue
            score = float(self.sim.text_pair(rule_text, self._lemma(model_source)))
            rows.append({
                "node_id": str(action.get("id")),
                "node_type": action.get("kind"),
                "original_label": action.get("name"),
                "match_source_text": model_source,
                "similarity": score,
                "tied": False,
                "selected": False,
                "reason": None,
            })
        if not rows:
            return []
        rows.sort(key=lambda row: (-float(row["similarity"]), str(row["node_id"])))
        best_score = float(rows[0]["similarity"])
        tied_rows = [row for row in rows if float(row["similarity"]) == best_score]
        for row in tied_rows:
            row["tied"] = True
        selected_id = min(str(row["node_id"]) for row in tied_rows)
        for row in rows:
            if str(row["node_id"]) == selected_id:
                row["selected"] = True
                break
        return rows

    def _best_actor_match(self, rule_actor: str, model: Any):
        rule_text = self._lemma(str(rule_actor))
        best_score = 0.0
        best_name = None
        best_kind = None
        for actor in getattr(model, "actors", []) or []:
            source = self._model_actor_source(model, actor)
            if not source:
                continue
            score = float(self.sim.text_pair(rule_text, self._lemma(source)))
            if score > best_score:
                best_score = score
                best_name = actor
                best_kind = model.actor_sources.get(actor, "actor")
        for bo in getattr(model, "business_objects", []) or []:
            source = str(bo.get("match_source_text") or "").strip()
            if not source:
                continue
            score = float(self.sim.text_pair(rule_text, self._lemma(source)))
            if score > best_score:
                best_score = score
                best_name = bo.get("object")
                best_kind = "business_object"
        return best_name, best_score, best_kind

    # --------------------------------------------------------- Definition 6
    def incorrect_actor(self, rule_actions: list[Any], rule_actors: list[str],
                        model: Any, actor_action_pairs=None) -> dict[str, Any]:
        """Definition 6 formula inherited semantically; matching uses P2 views."""

        def unavailable(reason, denominator=0):
            return {"score": None, "denominator": denominator,
                    "observable": False, "reason": reason, "details": [],
                    "actor_scope_policy": "sun_def6_action_bound_v2_r3_p2_view"}

        if not rule_actors:
            return unavailable("empty_rule_actor_denominator")
        if not getattr(model, "actors", None) and not getattr(model, "business_objects", None):
            return unavailable("no_actor_labels")
        pairs = actor_action_pairs
        if pairs is None and len(rule_actors) == len(rule_actions) == 1:
            pairs = [{"actor": rule_actors[0], "action": rule_actions[0]}]
        if not pairs:
            return unavailable("missing_rule_actor_action_map")
        valid = [p for p in pairs if p.get("actor") in rule_actors
                 and p.get("action") in rule_actions]
        unmapped = sorted(set(rule_actors) - {p["actor"] for p in valid})
        if unmapped:
            result = unavailable("incomplete_rule_actor_action_map")
            result["unmapped_rule_actors"] = unmapped
            return result

        r_set: list[str] = []
        matched_rule_actions: list[Any] = []
        for pair in valid:
            _, score = self._best_action_match(pair["action"], model)
            if score > self.gamma:
                r_set.append(pair["actor"])
                matched_rule_actions.append(pair["action"])
        r_set = list(dict.fromkeys(r_set))
        if not r_set:
            return unavailable("action_mapping_below_gamma")

        def rule_action_similarity(rule_action: Any, action: Mapping[str, Any]) -> float:
            rule_source = self._rule_action_source(rule_action)
            model_source = self._model_action_source(action)
            if not rule_source or not model_source:
                return 0.0
            return float(self.sim.text_pair(self._lemma(rule_source), self._lemma(model_source)))

        c_candidates: list[dict[str, Any]] = []
        matched_ids: list[str] = []
        for action in model.actions:
            action_id = str(action.get("id"))
            if not self._model_action_source(action):
                continue
            if any(rule_action_similarity(ra, action) > self.gamma
                   for ra in matched_rule_actions):
                matched_ids.append(action_id)
                for actor in model.action_actor_names.get(action_id, []):
                    source = self._model_actor_source(model, actor)
                    c_candidates.append({
                        "text": actor,
                        "matching_text": source,
                        "kind": model.actor_sources.get(actor, "actor"),
                        "node_id": action_id,
                    })
                for bo in model.business_objects:
                    if str(bo.get("activity_id")) == action_id:
                        c_candidates.append({
                            "text": bo.get("object"),
                            "matching_text": bo.get("match_source_text"),
                            "kind": "business_object",
                            "node_id": action_id,
                        })
        deduped_c: list[dict[str, Any]] = []
        seen_c: set[tuple[Any, Any, Any, Any]] = set()
        for row in c_candidates:
            key = (row.get("kind"), row.get("text"), row.get("node_id"), row.get("matching_text"))
            if key in seen_c:
                continue
            seen_c.add(key)
            deduped_c.append(row)
        c_candidates = deduped_c
        if not c_candidates:
            return unavailable("no_matching_process_actor", len(r_set))
        details = []
        for actor in r_set:
            values = []
            for candidate in c_candidates:
                source = candidate.get("matching_text")
                if not source:
                    values.append(0.0)
                else:
                    values.append(float(self.sim.text_pair(
                        self._lemma(actor), self._lemma(str(source)))))
            minimum = min(values) if values else 0.0
            details.append({
                "rule_actor": actor,
                "min_process_actor_similarity": round(minimum, 4),
                "exists_low_similarity": minimum < self.theta,
                "violated": minimum < self.theta,
            })
        violations = sum(d["violated"] for d in details)
        return {
            "score": violations / len(r_set),
            "violations": violations,
            "denominator": len(r_set),
            "observable": True,
            "reason": None,
            "details": details,
            "process_actor_candidates": c_candidates,
            "matched_process_action_ids": matched_ids,
            "actor_scope_policy": "sun_def6_action_bound_v2_r3_p2_view",
        }

    # --------------------------------------------------------- stable mapping
    def _action_id_by_name(self, model: Any, name: str) -> str | None:
        if name is None:
            return None
        for action in model.actions:
            if str(action.get("id")) == str(name):
                return str(action.get("id"))
        # Defensive compatibility only for already-resolved IDs; never a
        # name->first-node fallback for R3 scoring.
        return str(name) if any(str(a.get("id")) == str(name) for a in model.actions) else None


__all__ = ["R3SunScorer"]

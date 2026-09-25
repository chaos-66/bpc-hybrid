# -*- coding: utf-8 -*-
"""R4 targeted action-surface scorer.

The R4 task changes one input only relative to R3/M1: Definition 4, 5, 6
internal action gating, and Definition 7 all compare the rule-side
``action_surface`` with the model-side ``action_surface``.  The legacy
``match_source_text`` join (action + business object) is retained for evidence
and for the separate object-related paths, but it is never used as an action
fallback here.

This module subclasses the frozen R3 scorer so all formulas, thresholds,
candidate scopes, tie-breaking, and business-object handling remain inherited.
"""

from __future__ import annotations

from typing import Any, Mapping

from .r3_sun_scorer import R3SunScorer


R4_ACTION_MATCH_POLICY = "r4_action_surface_only_frozen_lemma"


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _nonempty_text(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _action_surface(value: Any) -> str | None:
    """Return the P2 action surface only; never the old joined fallback."""
    return _nonempty_text(_field(value, "action_surface"))


def _legacy_match_source(value: Any) -> str | None:
    return _nonempty_text(_field(value, "match_source_text"))


class R4ActionSurfaceScorer(R3SunScorer):
    """R3 SunScorer with an action-surface-only comparison source."""

    action_match_policy = R4_ACTION_MATCH_POLICY

    # ------------------------------------------------------------- source API
    def _model_action_source(self, action: Mapping[str, Any]) -> str | None:
        return _action_surface(action)

    def _rule_action_source(self, rule_action: Any) -> str | None:
        return _action_surface(rule_action)

    def _rule_endpoint_source(self, endpoint: Any) -> str | None:
        return _action_surface(endpoint)

    # ------------------------------------------------------------ evidence
    def action_candidate_evidence(self, rule_action: Any, model: Any) -> list[dict[str, Any]]:
        """Return one row per model node plus explicit missing-field rows.

        The scorer itself ignores rows whose ``similarity`` is ``None``.  The
        evidence keeps them so a missing action field is diagnosable instead of
        silently becoming "no candidate".
        """
        rule_source = self._rule_action_source(rule_action)
        legacy_rule_source = _legacy_match_source(rule_action)
        rows: list[dict[str, Any]] = []
        for action in model.actions:
            node_id = str(action.get("id"))
            model_source = self._model_action_source(action)
            row = {
                "node_id": node_id,
                "node_type": action.get("kind"),
                "original_label": action.get("name"),
                "rule_action_surface": rule_source,
                "rule_legacy_match_source_text": legacy_rule_source,
                "candidate_action_surface": model_source,
                "candidate_legacy_match_source_text": _legacy_match_source(action),
                "candidate_business_object_surface": _nonempty_text(action.get("business_object_surface")),
                "candidate_action_match_text": model_source,
                "candidate_matching_text": self._lemma(model_source) if model_source else None,
                "similarity": None,
                "tied": False,
                "selected": False,
                "reason": None,
            }
            if rule_source is None:
                row["reason"] = "rule_action_missing_action_surface"
            elif model_source is None:
                row["reason"] = "model_action_missing_action_surface"
            else:
                row["similarity"] = float(
                    self.sim.text_pair(self._lemma(rule_source), self._lemma(model_source))
                )
            rows.append(row)

        if rule_source is None and not rows:
            return [{
                "node_id": None,
                "node_type": None,
                "original_label": None,
                "rule_action_surface": None,
                "rule_legacy_match_source_text": legacy_rule_source,
                "candidate_action_surface": None,
                "candidate_legacy_match_source_text": None,
                "candidate_business_object_surface": None,
                "candidate_action_match_text": None,
                "candidate_matching_text": None,
                "similarity": None,
                "tied": False,
                "selected": False,
                "reason": "rule_action_missing_action_surface",
            }]

        valid = [row for row in rows if row.get("similarity") is not None]
        if not valid:
            return rows
        valid.sort(key=lambda row: (-float(row["similarity"]), str(row["node_id"])))
        best_score = float(valid[0]["similarity"])
        tied_rows = [row for row in valid if float(row["similarity"]) == best_score]
        for row in tied_rows:
            row["tied"] = True
        selected_id = min(str(row["node_id"]) for row in tied_rows)
        for row in rows:
            if str(row.get("node_id")) == selected_id:
                row["selected"] = True
                break
        return rows

    # -------------------------------------------------------- Definition 6
    def incorrect_actor(self, rule_actions: list[Any], rule_actors: list[str],
                        model: Any, actor_action_pairs=None) -> dict[str, Any]:
        """Definition 6 with per-candidate action/actor evidence.

        The mathematical comparison is the inherited R3 formula.  The returned
        details are expanded only for diagnosis; ``gamma`` and ``theta`` are
        never altered.
        """

        def unavailable(reason: str, denominator: int = 0) -> dict[str, Any]:
            return {
                "score": None,
                "denominator": denominator,
                "observable": False,
                "reason": reason,
                "details": [],
                "process_actor_candidates": [],
                "matched_process_action_ids": [],
                "actor_scope_policy": "sun_def6_action_bound_r4_action_surface",
            }

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
        matched_pairs: list[dict[str, Any]] = []
        for pair in valid:
            model_action_id, score = self._best_action_match(pair["action"], model)
            if score > self.gamma:
                if pair["actor"] not in r_set:
                    r_set.append(pair["actor"])
                matched_pairs.append({
                    "actor": pair["actor"],
                    "rule_action": pair["action"],
                    "rule_action_original_text": str(pair["action"]),
                    "rule_action_surface": self._rule_action_source(pair["action"]),
                    "selected_model_action_id": model_action_id,
                    "selected_action_similarity": float(score),
                })
        if not r_set:
            return unavailable("action_mapping_below_gamma")

        c_candidates: list[dict[str, Any]] = []
        matched_ids: list[str] = []
        for action in model.actions:
            action_id = str(action.get("id"))
            model_action_source = self._model_action_source(action)
            if not model_action_source:
                continue
            entry_evidence: list[dict[str, Any]] = []
            for pair in matched_pairs:
                rule_source = self._rule_action_source(pair["rule_action"])
                if not rule_source:
                    continue
                score = float(self.sim.text_pair(
                    self._lemma(rule_source), self._lemma(model_action_source)))
                if score > self.gamma:
                    entry_evidence.append({
                        "rule_actor": pair["actor"],
                        "rule_action_original_text": pair["rule_action_original_text"],
                        "rule_action_surface": rule_source,
                        "action_similarity_raw": score,
                    })
            if not entry_evidence:
                continue
            matched_ids.append(action_id)
            best_entry = max(entry_evidence, key=lambda row: float(row["action_similarity_raw"]))
            common = {
                "node_id": action_id,
                "node_type": action.get("kind"),
                "model_action_original_label": action.get("name"),
                "model_action_surface": model_action_source,
                "entry_action_gate": "similarity_above_gamma",
                "entry_rule_actor": best_entry["rule_actor"],
                "entry_rule_action_original_text": best_entry["rule_action_original_text"],
                "entry_rule_action_surface": best_entry["rule_action_surface"],
                "entry_action_similarity_raw": float(best_entry["action_similarity_raw"]),
                "entry_action_evidence": entry_evidence,
                "gamma": float(self.gamma),
                "theta": float(self.theta),
            }
            for actor in model.action_actor_names.get(action_id, []):
                source = self._model_actor_source(model, actor)
                c_candidates.append({
                    **common,
                    "candidate_original_text": actor,
                    "candidate_actual_comparison_text": source,
                    "candidate_actual_comparison_lemma": self._lemma(str(source)) if source else None,
                    "kind": model.actor_sources.get(actor, "actor"),
                })
            for bo in model.business_objects:
                if str(bo.get("activity_id")) != action_id:
                    continue
                source = _nonempty_text(bo.get("match_source_text"))
                c_candidates.append({
                    **common,
                    "candidate_original_text": bo.get("object"),
                    "candidate_actual_comparison_text": source,
                    "candidate_actual_comparison_lemma": self._lemma(source) if source else None,
                    "kind": "business_object",
                })

        # Stable de-duplication, preserving insertion order.
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[Any, Any, Any, Any]] = set()
        for row in c_candidates:
            key = (row.get("kind"), row.get("candidate_original_text"),
                   row.get("node_id"), row.get("candidate_actual_comparison_text"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        c_candidates = deduped
        if not c_candidates:
            return unavailable("no_matching_process_actor", len(r_set))

        actor_to_actions: dict[str, list[str]] = {}
        for pair in matched_pairs:
            actor_to_actions.setdefault(pair["actor"], [])
            if pair["rule_action_original_text"] not in actor_to_actions[pair["actor"]]:
                actor_to_actions[pair["actor"]].append(pair["rule_action_original_text"])

        details: list[dict[str, Any]] = []
        for actor in r_set:
            values: list[float] = []
            scored_candidates: list[dict[str, Any]] = []
            for candidate in c_candidates:
                source = candidate.get("candidate_actual_comparison_text")
                score = 0.0 if not source else float(self.sim.text_pair(
                    self._lemma(str(actor)), self._lemma(str(source))))
                values.append(score)
                row = dict(candidate)
                row["rule_actor_similarity_raw"] = score
                row["rule_actor_similarity"] = round(score, 4)
                row["violates_theta"] = bool(score < self.theta)
                scored_candidates.append(row)
            minimum = min(values) if values else 0.0
            tied = [row for row in scored_candidates
                    if float(row["rule_actor_similarity_raw"]) == float(minimum)]
            details.append({
                "rule_actor": actor,
                "rule_actor_original_text": actor,
                "rule_actor_actual_comparison_text": actor,
                "rule_actor_matching_text": self._lemma(str(actor)),
                "associated_rule_actions": actor_to_actions.get(actor, []),
                "candidate_count": len(scored_candidates),
                "minimum_process_actor_similarity_raw": float(minimum),
                "min_process_actor_similarity": round(float(minimum), 4),
                "exists_low_similarity": bool(minimum < self.theta),
                "violated": bool(minimum < self.theta),
                "minimum_candidate_count": len(tied),
                "all_minimum_tied": len(tied) > 1,
                "minimum_candidates": [{
                    "kind": row.get("kind"),
                    "candidate_original_text": row.get("candidate_original_text"),
                    "candidate_actual_comparison_text": row.get("candidate_actual_comparison_text"),
                    "candidate_actual_comparison_lemma": row.get("candidate_actual_comparison_lemma"),
                    "node_id": row.get("node_id"),
                    "entry_rule_actor": row.get("entry_rule_actor"),
                    "entry_rule_action_original_text": row.get("entry_rule_action_original_text"),
                    "entry_rule_action_surface": row.get("entry_rule_action_surface"),
                    "entry_action_similarity_raw": row.get("entry_action_similarity_raw"),
                    "rule_actor_similarity_raw": row.get("rule_actor_similarity_raw"),
                    "rule_actor_similarity": row.get("rule_actor_similarity"),
                    "violates_theta": row.get("violates_theta"),
                } for row in tied],
                "process_actor_candidates": scored_candidates,
                "gamma": float(self.gamma),
                "theta": float(self.theta),
            })
        violations = sum(1 for row in details if row["violated"])
        return {
            "score": violations / len(r_set),
            "violations": violations,
            "denominator": len(r_set),
            "observable": True,
            "reason": None,
            "details": details,
            "process_actor_candidates": c_candidates,
            "matched_process_action_ids": matched_ids,
            "matched_rule_action_gate": matched_pairs,
            "actor_scope_policy": "sun_def6_action_bound_r4_action_surface",
            "action_match_policy": R4_ACTION_MATCH_POLICY,
        }


__all__ = ["R4ActionSurfaceScorer", "R4_ACTION_MATCH_POLICY"]



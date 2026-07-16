"""Stage3Adapter: development scaffold for Stage 3 compliance checking.

This adapter is a **development approximation / fixture scaffold**
that composes the current SimilarityEngine with simple
missing-obligation / incorrect-actor / out-of-order detection. It
is **not** a replication of Sun's Pair.py or Paragraph.py.

The current scaffold does not implement:
  * Sun's Pair.fitness_score with proper gamma calibration
  * Sun's Pair.cost_resource with the full BPMN lane model
  * Sun's Paragraph-level flow ordering
  * BPMN gate / event / sub-process traversal

When the paper-faithful Stage 3 is implemented, this module must be
rewritten against the real Sun Stage 3 logic. Until then, it is
useful for development fixtures and unit tests but must NOT be
advertised as replicating Sun's Stage 3.
"""

from __future__ import annotations

from typing import Any

from bpc_hybrid.sun_compat.schema import (
    SunRuleRecord,
    ObligationRecord,
    ActorActionMap,
    OrderRelation,
)
from bpc_hybrid.sun_compat.similarity_engine import SimilarityEngine


class Stage3Adapter:
    """Stage 3 compliance checking adapter.

    Takes Sun-compatible rule records and BPMN task labels, then performs:
    1. Obligation matching (text ↔ model)
    2. Fitness scoring
    3. Obligation cost (missing obligations)
    4. Resource cost (incorrect actors)
    5. Order relation checking (out-of-order execution)

    Usage::

        >>> adapter = Stage3Adapter(similarity_engine)
        >>> result = adapter.check_compliance(
        ...     rules=[sun_rule_record_1, sun_rule_record_2],
        ...     model_obligations={"Controller": [["notify", "authority"]]},
        ... )
        >>> print(result["fitness_score"])
        0.85
        >>> print(result["obligation_cost"])
        0.15
    """

    def __init__(
        self,
        similarity_engine: SimilarityEngine | None = None,
        gamma: float = 0.4,
        delta: float = 0.8,
    ) -> None:
        self._engine = similarity_engine or SimilarityEngine()
        self._gamma = gamma  # obligation matching threshold
        self._delta = delta  # resource matching threshold

    def check_compliance(
        self,
        rules: list[SunRuleRecord],
        model_obligations: dict[str, list[list[str]]],
    ) -> dict[str, Any]:
        """Run Stage 3 compliance checking.

        Args:
            rules: List of SunRuleRecord from Stage 2.
            model_obligations: Dict of participant → list of lemmatized token lists
                from BPMN task labels (e.g., {"Data Controller": [["notify", "authority"]]}).

        Returns:
            Dict with:
            - fitness_score: float [0.0, 1.0]
            - obligation_cost: float [0.0, 1.0]
            - resource_cost: float [0.0, 1.0]
            - order_cost: float [0.0, 1.0]
            - total_obligations: int
            - matched_obligations: int
            - violation_details: list of dicts
        """
        # Collect all obligations
        all_obligations: list[ObligationRecord] = []
        for rule in rules:
            all_obligations.extend(rule.obligations)

        if not all_obligations:
            return self._empty_result()

        # Extract text obligations and actors
        text_obligations = [o.obligation_lemmatized for o in all_obligations]
        text_actors = [o.actor_canonical for o in all_obligations]

        # Compute scores
        fitness_score = self._engine.compute_fitness_score(
            text_obligations, model_obligations, self._gamma
        )
        obligation_cost = self._engine.compute_obligation_cost(
            text_obligations, model_obligations, self._gamma
        )
        resource_cost = self._engine.compute_resource_cost(
            text_obligations, text_actors, model_obligations,
            self._gamma, self._delta
        )

        # Compute order cost
        order_cost = self._compute_order_cost(rules, model_obligations)

        # Collect violation details
        violation_details = self._collect_violations(
            all_obligations, model_obligations
        )

        return {
            "fitness_score": fitness_score,
            "obligation_cost": obligation_cost,
            "resource_cost": resource_cost,
            "order_cost": order_cost,
            "total_obligations": len(all_obligations),
            "matched_obligations": sum(
                1 for o in text_obligations
                if self._engine.find_best_match(o, model_obligations, self._gamma)
            ),
            "violation_details": violation_details,
        }

    def check_fixture(
        self,
        rules: list[SunRuleRecord],
        model_obligations: dict[str, list[list[str]]],
        fixture_type: str,
    ) -> dict[str, Any]:
        """Run compliance checking for a specific fixture type.

        Args:
            rules: List of SunRuleRecord from Stage 2.
            model_obligations: BPMN obligations.
            fixture_type: One of "missing_action", "incorrect_actor", "out_of_order".

        Returns:
            Dict with compliance results and fixture-specific analysis.
        """
        result = self.check_compliance(rules, model_obligations)
        result["fixture_type"] = fixture_type

        if fixture_type == "missing_action":
            # Check if action_cost is high
            result["detected"] = result["obligation_cost"] > 0.5
        elif fixture_type == "incorrect_actor":
            # Check if resource_cost is high
            result["detected"] = result["resource_cost"] > 0.5
        elif fixture_type == "out_of_order":
            # Check if order_cost is high (>= to catch boundary cases like 1/2)
            result["detected"] = result["order_cost"] >= 0.5
        else:
            result["detected"] = False

        return result

    def _compute_order_cost(
        self,
        rules: list[SunRuleRecord],
        model_obligations: dict[str, list[list[str]]],
    ) -> float:
        """Compute order cost (out-of-order execution).

        This checks if the order relations in the regulation text
        are consistent with the order implied by the BPMN model.
        """
        # Collect all order relations
        all_relations = []
        for rule in rules:
            all_relations.extend(rule.order_relations)

        if not all_relations:
            return 0.0

        # Stopwords to remove (same as ClauseAdapter)
        _STOPWORDS = frozenset({
            "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "shall", "must", "can", "need", "dare",
            "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "out", "off", "over", "under", "again", "further",
            "then", "once", "here", "there", "when", "where", "why", "how", "all",
            "each", "every", "both", "few", "more", "most", "other", "some", "such",
            "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
            "it", "its", "and", "or", "but", "if", "this", "that", "these", "those",
        })

        def _lemmatize_for_matching(text: str) -> str:
            """Lemmatize and clean text for matching (removes stopwords)."""
            doc = self._engine._nlp(text)  # type: ignore
            tokens = []
            for t in doc:
                if t.is_punct or t.is_space or t.like_num:
                    continue
                lemma = t.lemma_.lower()
                if lemma in _STOPWORDS:
                    continue
                # Fix spaCy's data → datum
                if lemma == "datum":
                    lemma = "data"
                tokens.append(lemma)
            return " ".join(tokens)

        # For each order relation, check if the model preserves the order
        violations = 0
        for rel in all_relations:
            first_lem = _lemmatize_for_matching(rel.first_action)
            second_lem = _lemmatize_for_matching(rel.second_action)

            # Find which model obligations match each action
            # Use require_overlap=False for short order segments
            first_match = self._engine.find_best_match(
                first_lem,
                model_obligations,
                self._gamma,
                require_overlap=False,
            )
            second_match = self._engine.find_best_match(
                second_lem,
                model_obligations,
                self._gamma,
                require_overlap=False,
            )

            if first_match and second_match:
                # Both actions matched. Check if order is preserved.
                # Find the index of each matched obligation in the flat model list.
                all_model_obls = []
                for participant, obligations in model_obligations.items():
                    for obl in obligations:
                        all_model_obls.append((participant, obl))

                first_idx = -1
                second_idx = -1
                for idx, (participant, obl) in enumerate(all_model_obls):
                    if obl == first_match[1]:
                        first_idx = idx
                    if obl == second_match[1]:
                        second_idx = idx

                # If both found and order is reversed, it's a violation
                if first_idx >= 0 and second_idx >= 0 and first_idx > second_idx:
                    violations += 1

        return violations / len(all_relations) if all_relations else 0.0

    def _collect_violations(
        self,
        obligations: list[ObligationRecord],
        model_obligations: dict[str, list[list[str]]],
    ) -> list[dict[str, Any]]:
        """Collect detailed violation information."""
        violations = []

        for obl in obligations:
            match = self._engine.find_best_match(
                obl.obligation_lemmatized, model_obligations, self._gamma
            )

            if match is None:
                violations.append({
                    "type": "missing_obligation",
                    "obligation_id": obl.obligation_id,
                    "text": obl.source_text,
                    "actor": obl.actor,
                    "action": obl.action,
                    "modality": obl.modality,
                })
            else:
                # Check resource match using combined approach
                participant = match[0]
                if obl.actor_canonical:
                    actor_lower = obl.actor_canonical.lower().strip()
                    participant_lower = participant.lower().strip()

                    is_substring = (
                        actor_lower in participant_lower
                        or participant_lower in actor_lower
                    )

                    if not is_substring:
                        actor_doc = self._engine._nlp(actor_lower)  # type: ignore
                        participant_doc = self._engine._nlp(participant_lower)  # type: ignore
                        if actor_doc.has_vector and participant_doc.has_vector:
                            resource_sim = actor_doc.similarity(participant_doc)
                            if resource_sim < self._delta:
                                violations.append({
                                    "type": "incorrect_actor",
                                    "obligation_id": obl.obligation_id,
                                    "text": obl.source_text,
                                    "actor": obl.actor,
                                    "expected_actor": participant,
                                    "resource_similarity": resource_sim,
                                })

        return violations

    def _empty_result(self) -> dict[str, Any]:
        """Return empty compliance result."""
        return {
            "fitness_score": 0.0,
            "obligation_cost": 0.0,
            "resource_cost": 0.0,
            "order_cost": 0.0,
            "total_obligations": 0,
            "matched_obligations": 0,
            "violation_details": [],
        }

"""ClauseAdapter: converts 6-field extraction to Sun Clause-compatible format.

Sun's Clause object has:
- clause: list[Token] (full clause span)
- subject: list[Token] (nsubj dependency)
- verb: list[Token] (ROOT + aux)
- object: list[Token] (dobj/pobj/attr)
- rest: list[Token] (remaining)
- lemmatized: str (bag-of-words, stopwords removed)

Our output has:
- actor: str
- action: str
- condition: str
- constraint: str
- exception: str
- modality: str

This adapter converts our output to Sun-compatible format by:
1. Combining actor + action + condition + constraint + exception into a single string
2. Lemmatizing using spaCy
3. Removing stopwords
4. Producing the "obligation_lemmatized" string for similarity matching
"""

from __future__ import annotations

import re
from typing import Any

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from bpc_hybrid.sun_compat.schema import (
    SunRuleRecord,
    ObligationRecord,
    ActorActionMap,
    OrderRelation,
)

# Default stopwords (same as Sun's stopwords.txt)
_DEFAULT_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "must", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "s", "t", "just", "don", "now",
}

# Sequential order markers (same as Sun's sequencemarkers.txt)
_ORDER_MARKERS = {
    "then", "after", "afterward", "afterwards", "subsequently",
    "based on this", "thus",
}

# Passive voice patterns
_PASSIVE_PATTERN = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(\w+ed)\b", re.IGNORECASE
)


class ClauseAdapter:
    """Converts 6-field extraction to Sun Clause-compatible format.

    Usage::

        >>> adapter = ClauseAdapter()
        >>> record = adapter.convert(
        ...     rule_id="S001",
        ...     source_text="The controller shall notify the authority.",
        ...     modality="obligation",
        ...     actor="the controller",
        ...     action="notify the authority",
        ... )
        >>> print(record.obligations[0].obligation_lemmatized)
        "controller notify authority"
    """

    def __init__(
        self,
        nlp: Any | None = None,
        stopwords: set[str] | None = None,
        model_name: str = "en_core_web_md",
    ) -> None:
        if not SPACY_AVAILABLE:
            raise ImportError("spaCy is required for ClauseAdapter")
        self._nlp = nlp or spacy.load(model_name)
        self._stopwords = stopwords or _DEFAULT_STOPWORDS

    def convert(
        self,
        rule_id: str,
        source_text: str,
        modality: str,
        actor: str | None = None,
        action: str | None = None,
        condition: str | None = None,
        constraint: str | None = None,
        exception: str | None = None,
        provenance: str = "rule",
        confidence: float = 1.0,
    ) -> SunRuleRecord:
        """Convert 6-field extraction to Sun-compatible rule record.

        Args:
            rule_id: Unique identifier for this rule.
            source_text: The original regulatory sentence.
            modality: Modality type (obligation/prohibition/permission/definition).
            actor: Actor text (e.g., "the controller").
            action: Action text (e.g., "notify the authority").
            condition: Condition text (e.g., "if there is a breach").
            constraint: Constraint text (e.g., "within 72 hours").
            exception: Exception text (e.g., "unless required by law").
            provenance: Source of extraction (rule/llm/merged).
            confidence: Confidence score [0.0, 1.0].

        Returns:
            SunRuleRecord with one ObligationRecord.
        """
        # Build validation flags
        validation_flags = self._validate_fields(
            actor, action, condition, constraint, exception
        )

        # Build obligation lemmatized string
        obligation_lemmatized = self._build_obligation_lemmatized(
            actor, action, condition, constraint, exception
        )

        # Build canonical forms
        actor_canonical = self._canonicalize_actor(actor) if actor else ""
        action_canonical = self._canonicalize_action(action) if action else ""

        # Build actor-action map
        actor_action_maps = []
        if actor and action:
            actor_action_maps.append(ActorActionMap(
                actor=actor,
                action=action,
                actor_canonical=actor_canonical,
                action_canonical=action_canonical,
                confidence=confidence,
                inferred=False,
            ))

        # Build order relations from action text
        order_relations = self._extract_order_relations(action) if action else []

        # Build obligation record
        obligation = ObligationRecord(
            obligation_id=f"{rule_id}_obl0",
            source_text=source_text,
            obligation_lemmatized=obligation_lemmatized,
            modality=modality,
            actor=actor or "",
            actor_canonical=actor_canonical,
            action=action or "",
            action_canonical=action_canonical,
            condition=condition or "",
            constraint=constraint or "",
            exception=exception or "",
            actor_action_maps=actor_action_maps,
            order_relations=order_relations,
            confidence=confidence,
            provenance=provenance,
            validation_flags=validation_flags,
        )

        # Build rule record
        return SunRuleRecord(
            rule_id=rule_id,
            source_text=source_text,
            modality_type=modality,
            obligations=[obligation],
            actors=[actor] if actor else [],
            actions=[action] if action else [],
            conditions=[condition] if condition else [],
            constraints=[constraint] if constraint else [],
            exceptions=[exception] if exception else [],
            order_relations=order_relations,
            actor_action_maps=actor_action_maps,
            provenance=provenance,
            confidence=confidence,
            validation_flags=validation_flags,
        )

    def _build_obligation_lemmatized(
        self,
        actor: str | None,
        action: str | None,
        condition: str | None,
        constraint: str | None,
        exception: str | None,
    ) -> str:
        """Build the lemmatized bag-of-words string for similarity matching.

        This is the KEY field that Stage 3 uses for matching with BPMN task labels.
        It combines actor + action (the core obligation), excluding condition/constraint/exception
        to avoid diluting the similarity score.
        """
        # Core obligation: actor + action
        parts = []
        if actor:
            parts.append(actor)
        if action:
            parts.append(action)

        if not parts:
            return ""

        combined = " ".join(parts)
        return self._lemmatize_and_clean(combined)

    def _lemmatize_and_clean(self, text: str) -> str:
        """Lemmatize text and remove stopwords/punctuation/numbers."""
        doc = self._nlp(text)
        tokens = []
        for token in doc:
            if token.is_punct or token.is_space or token.like_num:
                continue
            if token.text.lower() in self._stopwords:
                continue
            # Use lemma, but keep pronouns as-is (same as Sun)
            if token.lemma_ == "-PRON-":
                tokens.append(token.text.lower())
            else:
                lemma = token.lemma_.lower()
                # Fix spaCy's "datum" → "data" (common GDPR term)
                if lemma == "datum":
                    lemma = "data"
                tokens.append(lemma)
        return " ".join(tokens)

    def _canonicalize_actor(self, actor: str) -> str:
        """Normalize actor for matching.

        Strips articles, converts to lowercase, keeps core noun phrase.
        """
        if not actor:
            return ""
        doc = self._nlp(actor)
        # Keep nouns and proper nouns, drop articles/determiners
        tokens = []
        for token in doc:
            if token.pos_ in ("NOUN", "PROPN", "ADJ"):
                tokens.append(token.lemma_.lower())
        return " ".join(tokens) if tokens else actor.lower().strip()

    def _canonicalize_action(self, action: str) -> str:
        """Normalize action for matching.

        Lemmatizes verbs, keeps noun phrases, removes stopwords.
        """
        if not action:
            return ""
        return self._lemmatize_and_clean(action)

    def _extract_order_relations(self, action: str) -> list[OrderRelation]:
        """Extract sequential order relations from action text.

        Looks for patterns like "X then Y", "after X, Y", "X before Y".
        Handles multiple sequential markers (A then B then C).
        """
        if not action:
            return []

        relations = []
        action_lower = action.lower()

        # First try to split on all "then"-style markers to get segments
        # e.g. "collect data, then process it, then store it" → 3 segments
        segments = self._split_on_order_markers(action_lower)
        if len(segments) >= 2:
            # Create pairwise order relations between consecutive segments
            for i in range(len(segments) - 1):
                relations.append(OrderRelation(
                    first_action=segments[i].strip(),
                    second_action=segments[i + 1].strip(),
                    marker="then",
                    confidence=0.8,
                ))
        return relations

    def _split_on_order_markers(self, text: str) -> list[str]:
        """Split text on order markers like 'then', 'after', etc.

        Handles 'and then', ', then', '. then', standalone 'then'.
        Returns ordered list of action segments.
        """
        import re

        # Build pattern for all order markers with optional leading punctuation/conjunction
        # Match: optional comma/period + optional 'and' + marker word
        marker_pattern = r"(?:[,;.\s]+)?(?:and\s+)?(?:" + "|".join(
            re.escape(m) for m in _ORDER_MARKERS
        ) + r")\b"

        parts = re.split(marker_pattern, text)
        # Filter empty strings
        return [p.strip() for p in parts if p.strip()]

    def _validate_fields(
        self,
        actor: str | None,
        action: str | None,
        condition: str | None,
        constraint: str | None,
        exception: str | None,
    ) -> dict[str, bool]:
        """Validate extraction fields and return flags."""
        flags = {
            "has_actor": bool(actor and actor.strip()),
            "has_action": bool(action and action.strip()),
            "has_condition": bool(condition and condition.strip()),
            "has_constraint": bool(constraint and constraint.strip()),
            "has_exception": bool(exception and exception.strip()),
            "action_not_empty": bool(action and action.strip()),
            "actor_not_empty": bool(actor and actor.strip()),
        }

        # Check if action is too long (>200 chars may indicate condition/constraint leaked in)
        if action and len(action) > 200:
            flags["action_too_long"] = True
        else:
            flags["action_too_long"] = False

        # Check if action contains condition/constraint/exception markers
        if action:
            action_lower = action.lower()
            flags["action_contains_condition"] = any(
                m in action_lower
                for m in ["if ", "when ", "where ", "unless "]
            )
            flags["action_contains_constraint"] = any(
                m in action_lower
                for m in ["within ", "at least ", "no later than "]
            )
        else:
            flags["action_contains_condition"] = False
            flags["action_contains_constraint"] = False

        return flags

    def convert_batch(
        self, extractions: list[dict[str, Any]]
    ) -> list[SunRuleRecord]:
        """Convert a batch of 6-field extractions to Sun-compatible records.

        Each extraction dict must have keys:
        - sample_id or rule_id
        - source_text or text
        - modality
        - actor (optional)
        - action (optional)
        - condition (optional)
        - constraint (optional)
        - exception (optional)
        """
        results = []
        for ext in extractions:
            rule_id = ext.get("rule_id") or ext.get("sample_id", f"R{len(results):04d}")
            source_text = ext.get("source_text") or ext.get("text", "")
            modality = ext.get("modality", "unknown")

            # Handle nested fields structure (from run_estg_extract.py output)
            fields = ext.get("fields", ext)
            actor = fields.get("actor", "")
            action = fields.get("action", "")
            condition = fields.get("condition", "")
            constraint = fields.get("constraint", "")
            exception = fields.get("exception", "")

            results.append(self.convert(
                rule_id=rule_id,
                source_text=source_text,
                modality=modality,
                actor=actor,
                action=action,
                condition=condition,
                constraint=constraint,
                exception=exception,
                provenance=ext.get("provenance", ext.get("method", "rule")),
            ))

        return results

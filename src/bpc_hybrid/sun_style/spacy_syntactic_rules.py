"""spaCy-enhanced syntactic rule engine for Sun-style extraction.

Uses spaCy's dependency parsing to implement rules closer to Sun et al.'s
constituency/dependency tree patterns:

- **Modality**: MD node dominated by VP
- **Actor**: subject dependency + NP containing actor marker
- **Condition**: SBAR/PP containing condition marker
- **Constraint**: NP/PP containing constraint marker
- **Exception**: SBAR/PP/NP containing exception marker
- **Action**: VP after removing modality/condition/constraint/exception spans
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

try:
    import spacy
    from spacy.tokens import Doc, Token
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon
from bpc_hybrid.sun_style.syntactic_rules import TextSpan, ExtractionSpans, RuleApplication


# ---------------------------------------------------------------------------
# spaCy-enhanced rule engine
# ---------------------------------------------------------------------------


class SpacySyntacticRuleEngine:
    """Syntactic rule engine using spaCy dependency parsing.

    This is a more faithful implementation of Sun's tree pattern rules,
    using actual dependency parsing instead of marker-position heuristics.
    """

    def __init__(
        self,
        lexicon: MarkerLexicon | None = None,
        model_name: str = "en_core_web_sm",
    ) -> None:
        self._lexicon = lexicon or MarkerLexicon.from_default()
        if not SPACY_AVAILABLE:
            raise ImportError("spaCy is required for SpacySyntacticRuleEngine")
        self._nlp = spacy.load(model_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_all(
        self,
        text: str,
        modality_start: int,
        modality_end: int,
    ) -> ExtractionSpans:
        """Extract all semantic spans using spaCy dependency parsing.

        Args:
            text: The input sentence.
            modality_start: Start offset of the modality marker.
            modality_end: End offset of the modality marker.

        Returns:
            ExtractionSpans with all extracted fields.
        """
        doc = self._nlp(text)
        spans = ExtractionSpans()

        # Record modality span
        spans.modality = TextSpan(
            text=text[modality_start:modality_end],
            start=modality_start,
            end=modality_end,
        )

        # Extract condition spans
        spans.condition = self._extract_condition(doc, text)
        spans.constraint = self._extract_constraint(doc, text)
        spans.exception = self._extract_exception(doc, text)
        spans.actor = self._extract_actor(doc, text, modality_start)
        spans.action = self._extract_action(doc, text, modality_start, modality_end, spans)

        return spans

    # ------------------------------------------------------------------
    # Condition extraction
    # Sun: SBAR << (condition marker); PP << (condition marker)
    # ------------------------------------------------------------------

    def _extract_condition(self, doc: Doc, text: str) -> TextSpan | None:
        """Extract condition span using dependency parsing."""
        text_lower = text.lower()
        for marker in self._lexicon.condition_markers:
            # Find marker in text
            idx = text_lower.find(marker)
            if idx == -1:
                continue

            # Find the token at this position
            token = self._find_token_at(doc, idx)
            if token is None:
                continue

            # Walk up to find the clause root
            # Sun's rule: SBAR << condition marker
            # In dependency parsing, look for advcl, prep, or mark relations
            clause_token = token
            while clause_token.head != clause_token:
                if clause_token.dep_ in ("advcl", "mark", "prep", "relcl"):
                    break
                clause_token = clause_token.head

            # Get the full clause span
            clause_span = self._get_clause_span(doc, clause_token)
            if clause_span and len(clause_span.text) > len(marker) + 5:
                return clause_span

        return None

    # ------------------------------------------------------------------
    # Constraint extraction
    # Sun: NP < (constraint marker); PP < (IN < constraint marker) $ NP
    # ------------------------------------------------------------------

    def _extract_constraint(self, doc: Doc, text: str) -> TextSpan | None:
        """Extract constraint span using dependency parsing."""
        text_lower = text.lower()
        for marker in self._lexicon.constraint_markers:
            idx = text_lower.find(marker)
            if idx == -1:
                continue

            token = self._find_token_at(doc, idx)
            if token is None:
                continue

            # Walk up to find NP or PP
            parent = token
            while parent.head != parent:
                if parent.pos_ in ("NOUN", "PROPN", "NP") or parent.dep_ in ("pobj", "attr"):
                    break
                parent = parent.head

            # Get the phrase span
            phrase_span = self._get_phrase_span(doc, parent)
            if phrase_span and len(phrase_span.text) > len(marker) + 3:
                return phrase_span

        return None

    # ------------------------------------------------------------------
    # Exception extraction
    # Sun: SBAR/PP/NP with exception marker
    # ------------------------------------------------------------------

    def _extract_exception(self, doc: Doc, text: str) -> TextSpan | None:
        """Extract exception span using dependency parsing."""
        text_lower = text.lower()
        for marker in self._lexicon.exception_markers:
            idx = text_lower.find(marker)
            if idx == -1:
                continue

            token = self._find_token_at(doc, idx)
            if token is None:
                continue

            # Walk up to find clause or phrase
            clause_token = token
            while clause_token.head != clause_token:
                if clause_token.dep_ in ("prep", "mark", "advcl"):
                    break
                clause_token = clause_token.head

            clause_span = self._get_clause_span(doc, clause_token)
            if clause_span and len(clause_span.text) > len(marker) + 5:
                return clause_span

        return None

    # ------------------------------------------------------------------
    # Actor extraction
    # Sun: subject dependency + NP containing actor marker
    # ------------------------------------------------------------------

    def _extract_actor(self, doc: Doc, text: str, modality_start: int) -> TextSpan | None:
        """Extract actor using dependency parsing."""
        # Strategy 1: Find subject of the main verb
        for token in doc:
            if token.dep_ in ("nsubj", "nsubjpass") and token.i < len(doc) // 2:
                # Get the full NP span
                np_span = self._get_np_span(doc, token)
                if np_span:
                    return np_span

        # Strategy 2: Look for actor markers
        text_lower = text.lower()
        for marker in self._lexicon.actor_markers:
            idx = text_lower.find(marker)
            if idx == -1:
                continue

            token = self._find_token_at(doc, idx)
            if token is None:
                continue

            np_span = self._get_np_span(doc, token)
            if np_span:
                return np_span

        return None

    # ------------------------------------------------------------------
    # Action extraction
    # Sun: VP after removing modality/condition/constraint/exception
    # ------------------------------------------------------------------

    def _extract_action(
        self,
        doc: Doc,
        text: str,
        modality_start: int,
        modality_end: int,
        spans: ExtractionSpans,
    ) -> TextSpan | None:
        """Extract action VP after removing other spans."""
        # Find the main verb
        main_verb = None
        for token in doc:
            if token.pos_ == "VERB" and token.dep_ == "ROOT":
                main_verb = token
                break

        if main_verb is None:
            # Fallback: find first VERB after modality
            for token in doc:
                if token.pos_ == "VERB" and token.idx >= modality_end:
                    main_verb = token
                    break

        if main_verb is None:
            return None

        # Get VP span
        vp_start = main_verb.idx
        vp_end = main_verb.idx + len(main_verb.text)

        # Extend to include children
        for child in main_verb.children:
            if child.dep_ in ("dobj", "attr", "prep", "advmod", "prt", "acomp"):
                child_end = child.idx + len(child.text)
                if child_end > vp_end:
                    vp_end = child_end
                # Also include grandchildren
                for grandchild in child.children:
                    gc_end = grandchild.idx + len(grandchild.text)
                    if gc_end > vp_end:
                        vp_end = gc_end

        # Remove spans that overlap with condition/constraint/exception
        action_text = text[vp_start:vp_end]
        for span in [spans.condition, spans.constraint, spans.exception]:
            if span and span.start >= vp_start and span.end <= vp_end:
                # Remove the span from action
                action_text = action_text[:span.start - vp_start] + action_text[span.end - vp_start:]

        action_text = action_text.strip()
        if not action_text:
            return None

        return TextSpan(text=action_text, start=vp_start, end=vp_end)

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _find_token_at(self, doc: Doc, char_offset: int) -> Token | None:
        """Find the token at the given character offset."""
        for token in doc:
            if token.idx <= char_offset < token.idx + len(token.text):
                return token
        return None

    def _get_clause_span(self, doc: Doc, token: Token) -> TextSpan | None:
        """Get the full clause span around a token."""
        # Find clause boundaries
        start = token.idx
        end = token.idx + len(token.text)

        # Extend left
        for i in range(token.i - 1, -1, -1):
            t = doc[i]
            if t.text in ".;":
                break
            start = t.idx

        # Extend right
        for i in range(token.i + 1, len(doc)):
            t = doc[i]
            if t.text in ".;":
                break
            end = t.idx + len(t.text)

        text = doc.text[start:end].strip()
        if text:
            return TextSpan(text=text, start=start, end=end)
        return None

    def _get_phrase_span(self, doc: Doc, token: Token) -> TextSpan | None:
        """Get the full phrase span around a token."""
        start = token.idx
        end = token.idx + len(token.text)

        # Extend to include modifiers
        for child in token.children:
            if child.dep_ in ("det", "amod", "compound", "nummod"):
                if child.idx < start:
                    start = child.idx
                child_end = child.idx + len(child.text)
                if child_end > end:
                    end = child_end

        text = doc.text[start:end].strip()
        if text:
            return TextSpan(text=text, start=start, end=end)
        return None

    def _get_np_span(self, doc: Doc, token: Token) -> TextSpan | None:
        """Get the full NP span around a token."""
        # Use spaCy's noun chunks if available
        for chunk in doc.noun_chunks:
            if token.i >= chunk.start and token.i < chunk.end:
                return TextSpan(
                    text=chunk.text,
                    start=chunk.start_char,
                    end=chunk.end_char,
                )

        # Fallback: manual NP extraction
        return self._get_phrase_span(doc, token)

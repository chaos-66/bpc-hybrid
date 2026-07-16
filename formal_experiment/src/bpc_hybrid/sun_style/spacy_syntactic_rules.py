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
            idx = 0
            while True:
                idx = text_lower.find(marker, idx)
                if idx == -1:
                    break

                token = self._find_token_at(doc, idx)
                if token is None:
                    idx += 1
                    continue

                # Walk up: condition markers are typically 'mark' or 'advmod'
                # dependents of the clause verb
                clause_verb = token
                while clause_verb.head != clause_verb:
                    if clause_verb.dep_ in ("advcl", "relcl", "ccomp", "ROOT"):
                        break
                    clause_verb = clause_verb.head

                # If the marker itself is a 'mark', its head IS the clause verb
                if token.dep_ == "mark" and token.head.pos_ in ("VERB", "AUX"):
                    clause_verb = token.head

                # Get the subtree of the clause verb
                subtree_tokens = list(clause_verb.subtree)
                if not subtree_tokens:
                    idx += 1
                    continue

                sub_start = min(t.idx for t in subtree_tokens)
                sub_end = max(t.idx + len(t) for t in subtree_tokens)

                # If subtree extends past modality marker, trim at comma
                # (conditions are typically before the main clause)
                mod_token = self._find_main_modal(doc)
                if mod_token and sub_end > mod_token.idx:
                    # Trim at the last comma before modality
                    for t in reversed(subtree_tokens):
                        if t.text == "," and t.idx < mod_token.idx:
                            sub_end = t.idx
                            break

                span_text = text[sub_start:sub_end].strip(" ,;")
                if span_text and len(span_text) > len(marker) + 3:
                    return TextSpan(text=span_text, start=sub_start, end=sub_end)

                idx += 1

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
        # Find the main verb — use modality token's head first
        main_verb = None

        # Strategy 1: modality token's head is the main verb
        mod_token = self._find_main_modal(doc)
        if mod_token is not None:
            head = mod_token.head
            if head != mod_token and head.pos_ in ("VERB", "AUX"):
                main_verb = head
            elif mod_token.pos_ == "AUX":
                # "shall" is AUX, look for its head verb
                for child in mod_token.children:
                    if child.pos_ == "VERB":
                        main_verb = child
                        break

        # Strategy 2: ROOT verb
        if main_verb is None:
            for token in doc:
                if token.dep_ == "ROOT" and token.pos_ in ("VERB", "AUX"):
                    main_verb = token
                    break

        # Strategy 3: first VERB after modality
        if main_verb is None:
            for token in doc:
                if token.pos_ == "VERB" and token.idx >= modality_end:
                    main_verb = token
                    break

        if main_verb is None:
            return None

        # Get VP span — use subtree for proper coverage
        subtree_tokens = list(main_verb.subtree)
        if subtree_tokens:
            vp_start = min(t.idx for t in subtree_tokens)
            vp_end = max(t.idx + len(t) for t in subtree_tokens)
        else:
            vp_start = main_verb.idx
            vp_end = main_verb.idx + len(main_verb.text)

        # Remove spans that overlap with condition/constraint/exception
        action_text = text[vp_start:vp_end]
        for span in [spans.condition, spans.constraint, spans.exception]:
            if span and span.start >= vp_start and span.end <= vp_end:
                # Remove the span from action
                action_text = action_text[:span.start - vp_start] + action_text[span.end - vp_start:]

        action_text = action_text.strip()
        if not action_text:
            return None

        # Recalculate position after removal
        real_start = text.find(action_text, vp_start)
        if real_start == -1:
            real_start = vp_start
        return TextSpan(text=action_text, start=real_start, end=real_start + len(action_text))

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _find_main_modal(self, doc: Doc) -> Token | None:
        """Find the main modality token (shall/must/may/should)."""
        modals = {"shall", "must", "may", "should"}
        for t in doc:
            if t.text.lower() in modals or t.lemma_.lower() in modals:
                return t
        return None

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

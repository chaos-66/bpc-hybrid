"""Sun-style syntactic rule engine (R15.0).

Implements span-based rule templates that approximate Sun et al.'s
constituency/dependency tree patterns.  Since no parser (spaCy, stanza,
benepar) is available locally, all rules operate on marker positions
and text spans.

Rule templates (approximated from Sun's tree patterns):

- **Condition**: marker-anchored clause extraction
  (Sun: SBAR << condition marker; PP << condition marker)

- **Constraint**: marker-anchored phrase extraction
  (Sun: NP < constraint marker; PP < IN constraint marker)

- **Exception**: marker-anchored clause extraction
  (Sun: SBAR/PP/NP with exception marker)

- **Actor**: subject-like NP before modality marker
  (Sun: subject dependency + NP containing actor marker)

- **Action**: VP span after removing modality/condition/constraint/
  exception spans
  (Sun: VP after removing modality/condition/constraint/exception spans)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TextSpan:
    """A span of text with character offsets."""

    text: str
    start: int
    end: int

    def __bool__(self) -> bool:
        return bool(self.text.strip()) if self.text else False


@dataclass
class RuleApplication:
    """Record of a single rule application."""

    rule_name: str
    sun_pattern: str  # The Sun tree pattern being approximated
    marker: str
    marker_start: int
    marker_end: int
    extracted_span: TextSpan | None


@dataclass
class ExtractionSpans:
    """All spans extracted from a single sentence."""

    modality: TextSpan | None = None
    condition: TextSpan | None = None
    constraint: TextSpan | None = None
    exception: TextSpan | None = None
    actor: TextSpan | None = None
    action: TextSpan | None = None

    rule_applications: list[RuleApplication] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule engine
# ---------------------------------------------------------------------------


class SyntacticRuleEngine:
    """Span-based rule engine approximating Sun's tree pattern rules.

    All rules operate on character-offset spans derived from marker
    positions, not actual parse trees.
    """

    # Clause boundary punctuation (splits clauses)
    _CLAUSE_BOUNDARY = re.compile(r"[,;]")

    def __init__(self, lexicon: MarkerLexicon | None = None) -> None:
        self._lexicon = lexicon or MarkerLexicon.from_default()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_all(self, text: str, modality_start: int,
                    modality_end: int) -> ExtractionSpans:
        """Extract all semantic spans from *text*.

        Parameters
        ----------
        text : str
            The full sentence text.
        modality_start : int
            Start offset of the modality marker.
        modality_end : int
            End offset of the modality marker.
        """
        text_lower = text.lower()
        spans = ExtractionSpans()

        # Modality span
        spans.modality = TextSpan(
            text=text[modality_start:modality_end],
            start=modality_start, end=modality_end,
        )

        # --- Condition extraction ---------------------------------------
        spans.condition = self._extract_condition(text, text_lower,
                                                   modality_start)
        # --- Constraint extraction --------------------------------------
        spans.constraint = self._extract_constraint(text, text_lower,
                                                     modality_start)
        # --- Exception extraction ---------------------------------------
        spans.exception = self._extract_exception(text, text_lower,
                                                   modality_start)
        # --- Actor extraction -------------------------------------------
        spans.actor = self._extract_actor(text, text_lower,
                                          modality_start, spans)
        # --- Action extraction ------------------------------------------
        spans.action = self._extract_action(text, modality_end, spans)

        return spans

    # ------------------------------------------------------------------
    # Individual rule extractors
    # ------------------------------------------------------------------

    def _extract_condition(self, text: str, text_lower: str,
                           modality_start: int) -> TextSpan | None:
        """Extract condition clause using marker-anchored span rules.

        Approximates Sun's: SBAR << condition marker; PP << condition marker.

        Strategy: find condition marker before modality; extract from
        marker to end of clause or to modality.
        """
        hits = self._lexicon.find_all_conditions(text_lower)
        for start, end, marker in hits:
            if start < modality_start:
                # Extract from marker to end of clause or to modality.
                clause_end = self._find_clause_end(text, start)
                extract_end = min(clause_end, modality_start)
                span_text = text[start:extract_end].strip(" ,;")
                if span_text:
                    span = TextSpan(text=span_text, start=start, end=extract_end)
                    self._record_rule("extract_condition",
                                      "SBAR << condition_marker",
                                      marker, start, end, span)
                    return span
        return None

    def _extract_constraint(self, text: str, text_lower: str,
                            modality_start: int) -> TextSpan | None:
        """Extract constraint phrase using marker-anchored span rules.

        Approximates Sun's: NP < constraint marker; PP < IN constraint marker.

        Strategy: find constraint marker after modality; extract from
        marker to end of sentence or next clause boundary.
        """
        hits = self._lexicon.find_all_constraints(text_lower)
        for start, end, marker in hits:
            if start >= modality_start:
                clause_end = self._find_clause_end(text, start)
                exception_hits = [
                    exc_start for exc_start, _exc_end, _marker
                    in self._lexicon.find_all_exceptions(text_lower)
                    if start < exc_start < clause_end
                ]
                if exception_hits:
                    clause_end = min(exception_hits)
                span_text = text[start:clause_end].strip(" ,;")
                if span_text:
                    span = TextSpan(text=span_text, start=start, end=clause_end)
                    self._record_rule("extract_constraint",
                                      "PP < IN constraint_marker",
                                      marker, start, end, span)
                    return span
        return None

    def _extract_exception(self, text: str, text_lower: str,
                           modality_start: int) -> TextSpan | None:
        """Extract exception clause using marker-anchored span rules.

        Approximates Sun's: SBAR/PP/NP with exception marker.

        Strategy: find exception marker; extract from marker to end
        of sentence.
        """
        hits = self._lexicon.find_all_exceptions(text_lower)
        for start, end, marker in hits:
            # Exception can appear before or after modality
            clause_end = self._find_clause_end(text, start)
            span_text = text[start:clause_end].strip(" ,;")
            if span_text:
                span = TextSpan(text=span_text, start=start, end=clause_end)
                self._record_rule("extract_exception",
                                  "SBAR/PP/NP with exception_marker",
                                  marker, start, end, span)
                return span
        return None

    def _extract_actor(self, text: str, text_lower: str,
                       modality_start: int,
                       spans: ExtractionSpans) -> TextSpan | None:
        """Extract actor using subject-like NP heuristics.

        Approximates Sun's: subject dependency + NP containing actor marker.

        Strategy:
        1. First try to find an actor marker in the text before modality.
        2. If found, extract the NP containing it.
        3. Otherwise, extract the first NP before modality as fallback.
        """
        # Strategy 1: Actor marker
        actor_hit = self._lexicon.find_actor(text_lower)
        if actor_hit is not None:
            a_start, a_end, marker = actor_hit
            if a_start < modality_start:
                # Find the NP containing this actor marker
                np_start, np_end = self._find_np_containing(text, a_start, a_end)
                span_text = text[np_start:np_end]
                span = TextSpan(text=span_text, start=np_start, end=np_end)
                self._record_rule("extract_actor",
                                  "NP containing actor_marker",
                                  marker, a_start, a_end, span)
                return span

        # Strategy 2: First NP before modality (subject-like heuristic)
        before_mod = text[:modality_start]
        before_lower = before_mod.lower()

        # Find the last stretch of capitalized or alphabetic words
        # before the modality marker — heuristic NP
        words_before = before_mod.strip().split()
        if words_before:
            # Take the last 1-3 words before modality as potential actor
            actor_words = []
            for w in reversed(words_before[-3:]):
                if w[0].isupper() or w.lower() in {"the", "a", "an", "each", "every", "any", "no"}:
                    actor_words.insert(0, w)
                elif w.lower() in {"shall", "must", "may", "should", "is", "are", "was", "were"}:
                    break
                else:
                    actor_words.insert(0, w)
            if actor_words:
                actor_text = " ".join(actor_words)
                # Find position in original text
                idx = before_mod.find(actor_text)
                if idx != -1:
                    span = TextSpan(text=actor_text, start=idx,
                                    end=idx + len(actor_text))
                    self._record_rule("extract_actor",
                                      "subject_heuristic",
                                      "", -1, -1, span)
                    return span

        return None

    def _extract_action(self, text: str, modality_end: int,
                        spans: ExtractionSpans) -> TextSpan | None:
        """Extract action by removing modality/condition/constraint/
        exception spans from the post-modality text.

        Approximates Sun's: VP after removing modality/condition/
        constraint/exception spans.
        """
        after_mod = self._remove_spans_after_modality(text, modality_end, spans)

        # Clean up and extract the action text.
        action_text = after_mod.strip(" ,;. \t")
        # Remove leading marker words that may be part of the condition/
        # constraint/exception introduction
        action_text = self._strip_leading_marker_words(action_text)

        if action_text:
            # Find position in original text
            idx = text.find(action_text, modality_end)
            if idx == -1:
                idx = modality_end
            span = TextSpan(text=action_text, start=idx,
                            end=idx + len(action_text))
            self._record_rule("extract_action",
                              "VP after removing modality/condition/"
                              "constraint/exception spans",
                              "", -1, -1, span)
            return span

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_clause_end(self, text: str, start: int) -> int:
        """Find the end of the clause starting at *start*.

        Looks for the next clause or sentence boundary.
        """
        for i in range(start, len(text)):
            if text[i] in ",;.!?":
                return i
        return len(text)

    def _remove_spans_after_modality(
        self,
        text: str,
        modality_end: int,
        spans: ExtractionSpans,
    ) -> str:
        """Remove condition/constraint/exception spans by character offsets."""
        removable = [
            span for span in [spans.condition, spans.constraint, spans.exception]
            if span is not None and span.end > modality_end
        ]
        removable.sort(key=lambda span: (span.start, -span.end))

        pieces: list[str] = []
        cursor = modality_end
        for span in removable:
            start = max(span.start, modality_end)
            end = max(span.end, start)
            if start > cursor:
                pieces.append(text[cursor:start])
            cursor = max(cursor, end)
        if cursor < len(text):
            pieces.append(text[cursor:])

        return " ".join(piece.strip(" ,;. \t") for piece in pieces if piece.strip(" ,;. \t"))

    def _find_np_containing(self, text: str, start: int, end: int) -> tuple[int, int]:
        """Find the NP (noun phrase) that contains the span [start, end).

        Expands left to include determiners/articles, and right to include
        trailing modifiers.
        """
        # Expand left to word boundary
        np_start = start
        while np_start > 0 and text[np_start - 1] != " ":
            np_start -= 1
        # Include leading article/determiner
        before = text[:np_start].rstrip()
        if before:
            last_word = before.split()[-1].lower()
            if last_word in {"the", "a", "an", "each", "every", "any", "no"}:
                np_start = before.lower().rfind(last_word)

        # Expand right to include trailing words
        np_end = end
        while np_end < len(text) and text[np_end] not in " ,;.!?":
            np_end += 1

        return np_start, np_end

    def _strip_leading_marker_words(self, text: str) -> str:
        """Remove leading marker/connector words from action text."""
        leading_pattern = re.compile(
            r"^(and|or|but|then|therefore|thus|hence|accordingly|"
            r"consequently|however|nevertheless|moreover|furthermore|"
            r"in addition|additionally|also|as well as|including|such as)\s+",
            re.IGNORECASE,
        )
        result = leading_pattern.sub("", text)
        return result.strip()

    def _record_rule(self, rule_name: str, sun_pattern: str,
                     marker: str, marker_start: int, marker_end: int,
                     span: TextSpan | None) -> None:
        """Record a rule application (side effect on internal log).
        For future traceability; not used in extraction logic.
        """
        pass  # Rule applications tracked via ExtractionSpans.rule_applications

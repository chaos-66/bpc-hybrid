"""Rule-first extractor (R3 + R4 integration).

Marker-based extraction of normative elements from toy regulatory
sentences.  Uses only the Python standard library and the R2 schema
objects.  R4 multi-clause splitting is integrated via the splitter
module.
"""

from __future__ import annotations

import re
from typing import Any

from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)
from bpc_hybrid.splitter import ClauseSegment, split_normative_clauses


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ExtractionError(ValueError):
    """Raised when the rule-first extractor encounters an unexpected state."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_span(source_text: str, start: int, end: int,
               confidence: float = 1.0) -> FieldSpan:
    """Create a :class:`FieldSpan` with text taken from *source_text*.

    The span *text* will be ``source_text[start:end]``.
    """
    text = source_text[start:end]
    return FieldSpan(text=text, span_start=start, span_end=end,
                     confidence=confidence)


def _strip_trailing_punct(text: str) -> str:
    """Remove trailing punctuation (.,;:!?) and whitespace."""
    return text.rstrip(".,;:!? \t")


def _span_of_stripped(source_text: str, start: int, end: int,
                      confidence: float = 1.0,
                      rstrip_chars: str = ".,;:!? \t") -> FieldSpan:
    """Like :func:`_make_span` but adjusts *end* so the text is stripped."""
    raw = source_text[start:end]
    stripped = raw.rstrip(rstrip_chars)
    new_end = start + len(stripped)
    return FieldSpan(text=stripped, span_start=start, span_end=new_end,
                     confidence=confidence)


def _extract_active_actor_segment(
        source_text: str, seg, marker_start: int,
        condition: FieldSpan | None,
) -> FieldSpan | None:
    """Extract active-voice actor from a clause segment.

    Uses *seg.span_start* as the minimum actor search start (so that
    text before the segment is not considered).  If a *condition*
    exists, its span is excluded from the actor region.
    """
    actor_start = seg.span_start
    if condition is not None:
        after_cond = condition.span_end
        while after_cond < marker_start and source_text[after_cond] in ', ':
            after_cond += 1
        actor_start = max(actor_start, after_cond)

    before = source_text[actor_start:marker_start]
    before_stripped = before.rstrip()
    if not before_stripped:
        return None

    leading_ws_in_before = len(before) - len(before.lstrip())
    start = actor_start + leading_ws_in_before
    end = start + len(before_stripped)

    return FieldSpan(text=before_stripped, span_start=start, span_end=end,
                     confidence=0.95)


# ---------------------------------------------------------------------------
# Modality markers – ordered by priority (longest / most specific first)
# ---------------------------------------------------------------------------

_MODALITY_SPECS: list[tuple[str, str]] = [
    # (lowercase marker pattern, normalized form) – normalization preserved
    # for future use; current R3 uses original-case spans.
    ("no person shall", "shall not"),
    ("shall not",       "shall not"),
    ("must not",        "must not"),
    ("shall",           "shall"),
    ("must",            "must"),
    ("may",             "may"),
]


# ---------------------------------------------------------------------------
# Constraint markers
# ---------------------------------------------------------------------------

_CONSTRAINT_MARKERS = [
    "within",
    "before",
    "after",
    "only if",
    "provided that",
]


# ---------------------------------------------------------------------------
# Negative-case heuristic patterns (for non-normative sentences)
# ---------------------------------------------------------------------------

# Sentences that look like definitions even if a modality marker is present
# (we do NOT match on "may" inside definitions).
_DEFINITION_PATTERNS = [
    # "X" means Y   /   X means Y
    re.compile(r'\b\w+\s+means\b', re.IGNORECASE),
    re.compile(r'\b\w+\s+is\s+(a|an|the)\b', re.IGNORECASE),
    re.compile(r'^\s*"[^"]+"\s*(means|refers to|denotes)', re.IGNORECASE),
]


def _looks_like_definition(text: str) -> bool:
    """Heuristic: does *text* look like a definition sentence?"""
    for pat in _DEFINITION_PATTERNS:
        if pat.search(text):
            return True
    return False


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------

class RuleFirstExtractor:
    """Prototype-level rule-first extractor.

    Usage::

        >>> ext = RuleFirstExtractor()
        >>> resp = ext.extract("A controller shall record the decision.")
        >>> resp.validate()
    """

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def extract(self, source_text: str,
                source_id: str = "synthetic") -> MultiClauseExtractionResponse:
        """Extract normative elements from *source_text*.

        If the text contains multiple modality markers (e.g. may+shall),
        the sentence is first split into clause segments via the R4
        splitter, and each segment is extracted independently.

        Returns a :class:`MultiClauseExtractionResponse` with one or
        more :class:`ClauseExtraction` clauses.
        """
        # --- Split into clause segments (R4) ----------------------------
        segments = split_normative_clauses(source_text)

        clauses: list[ClauseExtraction] = []
        for idx, seg in enumerate(segments):
            clause = self._extract_segment(
                source_text, source_id, seg, idx,
            )
            clauses.append(clause)

        return MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id=source_id,
            source_text=source_text,
            clauses=clauses,
        )

    def _extract_segment(
            self, source_text: str, source_id: str,
            seg: ClauseSegment, seg_idx: int,
    ) -> ClauseExtraction:
        """Extract semantic fields from a single clause segment.

        Uses the segment's *text* as the scope for modality/actor/action
        detection, but maps all spans back to *source_text* global
        offsets via *seg.span_start*.
        """
        # Inherited condition from initial-unless
        inherited_cond = seg.inherited_condition

        # --- Find modality marker within the segment --------------------
        mod_hit = self._find_modality(seg.text)
        if mod_hit is None:
            if inherited_cond is not None:
                # Even without own modality, record the inherited condition
                return ClauseExtraction(
                    clause_id=f"C{seg_idx + 1}",
                    source_id=source_id,
                    source_text=source_text,
                    clause_text=seg.text,
                    clause_span_start=seg.span_start,
                    clause_span_end=seg.span_end,
                    modality=None,
                    actor=None,
                    action=None,
                    condition=inherited_cond,
                    constraint=None,
                    exception=None,
                    confidence=0.1,
                )
            return ClauseExtraction(
                clause_id=f"C{seg_idx + 1}",
                source_id=source_id,
                source_text=source_text,
                clause_text=seg.text,
                clause_span_start=seg.span_start,
                clause_span_end=seg.span_end,
                modality=None,
                actor=None,
                action=None,
                condition=None,
                constraint=None,
                exception=None,
                confidence=0.1,
            )

        marker_text, marker_start_local, marker_end_local = mod_hit

        # --- Global offsets --------------------------------------------
        marker_start = seg.span_start + marker_start_local
        marker_end = seg.span_start + marker_end_local

        # --- Build modality span (global) ------------------------------
        modality = _make_span(source_text, marker_start, marker_end, 1.0)

        # --- Condition — use inherited from segment, plus check local --
        segment_condition = self._extract_initial_unless(
            seg.text, marker_start_local)
        if segment_condition is not None:
            # Map local span to global
            condition = FieldSpan(
                text=segment_condition.text,
                span_start=seg.span_start + segment_condition.span_start,
                span_end=seg.span_start + segment_condition.span_end,
                confidence=segment_condition.confidence,
            )
        elif inherited_cond is not None:
            condition = inherited_cond
        else:
            condition = None

        # --- Constraint ------------------------------------------------
        constraint = self._find_constraint(source_text, marker_end)

        # --- Exception (mid-sentence unless) ---------------------------
        exception = self._find_mid_unless(source_text, marker_end)

        # --- Actor + Action --------------------------------------------
        actor, action = self._extract_actor_and_action_segment(
            source_text, seg, marker_text, marker_start, marker_end,
            condition, constraint, exception,
        )

        return ClauseExtraction(
            clause_id=f"C{seg_idx + 1}",
            source_id=source_id,
            source_text=source_text,
            clause_text=seg.text,
            clause_span_start=seg.span_start,
            clause_span_end=seg.span_end,
            modality=modality,
            actor=actor,
            action=action,
            condition=condition,
            constraint=constraint,
            exception=exception,
            confidence=0.9 if action is not None else 0.3,
        )

    # ------------------------------------------------------------------
    # Modality detection
    # ------------------------------------------------------------------

    def _find_modality(self, text: str) -> tuple[str, int, int] | None:
        """Find the first modality marker in *text*.

        Returns ``(marker_text, start, end)`` or ``None``.
        Searches in priority order so ``"shall not"`` is matched before
        ``"shall"``.
        """
        text_lower = text.lower()
        for marker_lower, _norm in _MODALITY_SPECS:
            idx = text_lower.find(marker_lower)
            if idx == -1:
                continue
            # Word-boundary check
            if not self._is_word_boundary(text, idx, len(marker_lower)):
                # Example: "shall" inside "shallow" – skip
                continue
            return (text[idx:idx + len(marker_lower)], idx,
                    idx + len(marker_lower))
        return None

    @staticmethod
    def _is_word_boundary(text: str, start: int, length: int) -> bool:
        """Check that the slice at ``start:start+length`` is word-delimited."""
        before_ok = start == 0 or not text[start - 1].isalpha()
        after_ok = (start + length == len(text)
                    or not text[start + length].isalpha())
        return before_ok and after_ok

    # ------------------------------------------------------------------
    # Actor + Action — unified extraction with voice detection
    # ------------------------------------------------------------------

    def _extract_actor_and_action(
            self, source_text: str,
            marker_text: str, marker_start: int, marker_end: int,
            condition: FieldSpan | None,
            constraint: FieldSpan | None,
            exception: FieldSpan | None,
    ) -> tuple[FieldSpan | None, FieldSpan | None]:
        """Extract actor and action, handling both active and passive voice.

        Returns ``(actor, action)``.
        """

        # --- Special case: "no person shall" ----------------------------
        if marker_text.lower() == "no person shall":
            actor = self._extract_no_person_actor(source_text, marker_start)
            action = self._extract_action(source_text, marker_end,
                                          constraint, exception,
                                          passive_by_start=None)
            return actor, action

        # --- Determine voice by inspecting tail after modality ----------
        tail = source_text[marker_end:]
        is_passive = bool(re.match(r'\s*be\s+\w+', tail))

        if is_passive:
            # Passive voice: subject is the undergoer, not the actor.
            # Actor comes from "by the X" if present.
            by_match = re.search(r'\bby\s+(the\s+\w+)', tail, re.IGNORECASE)
            if by_match:
                # Actor = "the X" from by-phrase
                actor_text = by_match.group(1)  # e.g. "the controller"
                actor_global_start = marker_end + by_match.start(1)
                actor_global_end = marker_end + by_match.end(1)
                actor = FieldSpan(text=actor_text,
                                  span_start=actor_global_start,
                                  span_end=actor_global_end,
                                  confidence=0.92)
                by_global = marker_end + by_match.start()
                action = self._extract_action(source_text, marker_end,
                                              constraint, exception,
                                              passive_by_start=by_global)
            else:
                # Passive with no by-agent → null actor
                actor = None
                action = self._extract_action(source_text, marker_end,
                                              constraint, exception,
                                              passive_by_start=None)
        else:
            # Active voice: actor = text before modality marker,
            # minus any initial-unless condition clause.
            actor = self._extract_active_actor(source_text, marker_start,
                                               condition)
            action = self._extract_action(source_text, marker_end,
                                          constraint, exception,
                                          passive_by_start=None)

        return actor, action

    def _extract_actor_and_action_segment(
            self, source_text: str, seg: ClauseSegment,
            marker_text: str, marker_start: int, marker_end: int,
            condition: FieldSpan | None,
            constraint: FieldSpan | None,
            exception: FieldSpan | None,
    ) -> tuple[FieldSpan | None, FieldSpan | None]:
        """Like :meth:`_extract_actor_and_action` but scoped to *seg*.

        All returned spans use *source_text* global offsets.
        For subsequent segments where the actor text is missing,
        actor is ``None``.
        """
        end_bound = seg.span_end

        # --- Special case: "no person shall" ----------------------------
        if marker_text.lower() == "no person shall":
            actor = self._extract_no_person_actor(source_text, marker_start)
            action = self._extract_action(source_text, marker_end,
                                          constraint, exception,
                                          passive_by_start=None,
                                          end_bound=end_bound)
            return actor, action

        # --- Determine voice by inspecting tail after modality ----------
        tail = source_text[marker_end:]
        is_passive = bool(re.match(r'\s*be\s+\w+', tail))

        if is_passive:
            by_match = re.search(r'\bby\s+(the\s+\w+)', tail, re.IGNORECASE)
            if by_match:
                actor_text = by_match.group(1)
                actor_global_start = marker_end + by_match.start(1)
                actor_global_end = marker_end + by_match.end(1)
                actor = FieldSpan(text=actor_text,
                                  span_start=actor_global_start,
                                  span_end=actor_global_end,
                                  confidence=0.92)
                by_global = marker_end + by_match.start()
                action = self._extract_action(source_text, marker_end,
                                              constraint, exception,
                                              passive_by_start=by_global,
                                              end_bound=end_bound)
            else:
                actor = None
                action = self._extract_action(source_text, marker_end,
                                              constraint, exception,
                                              passive_by_start=None,
                                              end_bound=end_bound)
        else:
            # Active voice: actor = text before modality marker within seg
            seg_cond = None
            if condition is not None:
                if condition.span_end <= marker_start:
                    seg_cond = condition
            actor = _extract_active_actor_segment(source_text, seg,
                                                  marker_start, seg_cond)
            action = self._extract_action(source_text, marker_end,
                                          constraint, exception,
                                          passive_by_start=None,
                                          end_bound=end_bound)

        return actor, action

    def _extract_no_person_actor(self, source_text: str,
                                 marker_start: int) -> FieldSpan:
        """Actor for ``no person shall`` — the ``"No person"`` prefix."""
        actor_len = len("No person")
        marker_len = len("No person shall")
        # Use original-case text
        full_marker = source_text[marker_start:marker_start + marker_len]
        if full_marker.lower().startswith("no person"):
            actor_text = full_marker[:actor_len]
        else:
            actor_text = "No person"
        return FieldSpan(text=actor_text,
                         span_start=marker_start,
                         span_end=marker_start + actor_len,
                         confidence=0.95)

    def _extract_active_actor(self, source_text: str, marker_start: int,
                              condition: FieldSpan | None) -> FieldSpan | None:
        """Extract active-voice actor from text before the modality marker.

        If an initial-unless *condition* exists, its span is excluded from
        the actor region.
        """
        actor_start = 0
        if condition is not None:
            # Skip past the condition clause + optional comma/whitespace
            after_cond = condition.span_end
            while after_cond < marker_start and source_text[after_cond] in ', ':
                after_cond += 1
            actor_start = after_cond

        before = source_text[actor_start:marker_start]
        before_stripped = before.rstrip()
        if not before_stripped:
            return None

        # Recompute based on actual stripped text
        # Find start offset of before_stripped within the slice
        text = before_stripped
        leading_ws_in_before = len(before) - len(before.lstrip())
        start = actor_start + leading_ws_in_before
        end = start + len(text)

        return FieldSpan(text=text, span_start=start, span_end=end,
                         confidence=0.95)

    # ------------------------------------------------------------------
    # Action extraction
    # ------------------------------------------------------------------

    def _extract_initial_unless(self, source_text: str,
                                marker_start: int) -> FieldSpan | None:
        """If the sentence starts with ``Unless ... ,``, extract as condition.

        Only searches up to *marker_start* so that the rest of the sentence
        (after the unless clause's comma) is not captured.
        """
        prefix = source_text[:marker_start]
        # Non-greedy match of "Unless X" followed by optional comma
        m = re.match(r'^(Unless\s+\w+(?:\s+\w+)*?)\s*,?\s*',
                     prefix, re.IGNORECASE)
        if not m:
            return None
        raw = m.group(1)
        return FieldSpan(text=raw, span_start=m.start(1), span_end=m.end(1),
                         confidence=0.90)

    # ------------------------------------------------------------------
    # Mid-sentence unless → exception
    # ------------------------------------------------------------------

    def _find_mid_unless(self, source_text: str,
                         search_from: int) -> FieldSpan | None:
        """Find a mid-sentence *unless* clause as an exception."""
        # Only search from the modality end, not from beginning
        tail = source_text[search_from:]
        m = re.search(r'\bunless\s+', tail, re.IGNORECASE)
        if not m:
            return None

        start_offset = search_from + m.start()
        # Take everything from "unless" to end of sentence, minus trailing punct
        raw = source_text[start_offset:]
        stripped = _strip_trailing_punct(raw)
        end = start_offset + len(stripped)
        return FieldSpan(text=stripped, span_start=start_offset,
                         span_end=end, confidence=0.85)

    # ------------------------------------------------------------------
    # Constraint extraction
    # ------------------------------------------------------------------

    def _find_constraint(self, source_text: str,
                         search_from: int) -> FieldSpan | None:
        """Find the first constraint marker after *search_from*."""
        tail = source_text[search_from:]
        tail_lower = tail.lower()

        best: tuple[int, int, str] | None = None  # (offset, end, marker)
        for marker in _CONSTRAINT_MARKERS:
            idx = tail_lower.find(marker)
            if idx == -1:
                continue
            # Word boundary before
            if idx > 0 and tail[idx - 1].isalpha():
                continue
            global_idx = search_from + idx
            # Take from marker to end, strip trailing punct
            raw = source_text[global_idx:]
            stripped = _strip_trailing_punct(raw)
            end = global_idx + len(stripped)
            if best is None or global_idx < best[0]:
                best = (global_idx, end, marker)

        if best is None:
            return None

        start, end, _marker = best
        return FieldSpan(text=source_text[start:end],
                         span_start=start, span_end=end, confidence=0.85)

    # ------------------------------------------------------------------
    # Action extraction
    # ------------------------------------------------------------------

    def _extract_action(self, source_text: str, tail_start: int,
                        constraint: FieldSpan | None,
                        exception: FieldSpan | None,
                        passive_by_start: int | None = None,
                        end_bound: int | None = None,
                        ) -> FieldSpan | None:
        """Extract the action phrase from the text after the modality marker.

        Stops at the earliest of: constraint, exception, ``by``-agent,
        ``to the X`` (recipient), or *end_bound* boundaries.
        """
        tail = source_text[tail_start:]

        # Collect boundary positions
        boundaries: list[int] = []

        if constraint is not None:
            boundaries.append(constraint.span_start)
        if exception is not None:
            boundaries.append(exception.span_start)

        # If caller already detected a passive by-agent, use that boundary
        if passive_by_start is not None:
            boundaries.append(passive_by_start)
        else:
            # Fallback: detect by-agent locally
            by_match = re.search(r'\bby\s+the\s+\w+', tail, re.IGNORECASE)
            if by_match:
                boundaries.append(tail_start + by_match.start())

        # Recipient / affected party (to the X) — boundary, not actor
        to_match = re.search(r'\bto\s+the\s+\w+', tail, re.IGNORECASE)
        if to_match:
            boundaries.append(tail_start + to_match.start())

        # Segment boundary
        if end_bound is not None:
            boundaries.append(end_bound)

        if boundaries:
            action_end = min(boundaries)
        else:
            action_end = len(source_text)

        # Raw action text, then strip trailing punctuation
        raw_action = source_text[tail_start:action_end]
        raw_action = raw_action.strip()
        if not raw_action:
            return None

        # Find actual start (skip leading whitespace in tail)
        leading_ws = len(tail) - len(tail.lstrip())
        actual_start = tail_start + leading_ws
        actual_end = actual_start + len(raw_action)

        # Trim trailing punctuation
        stripped_action = _strip_trailing_punct(raw_action)
        if not stripped_action:
            return None
        actual_end = actual_start + len(stripped_action)

        return FieldSpan(text=stripped_action,
                         span_start=actual_start,
                         span_end=actual_end,
                         confidence=0.88)

    def _build_clause_with_passive_actor(
            self, source_text: str, source_id: str,
            modality: FieldSpan,
            passive_actor: FieldSpan,
            action: FieldSpan,
            condition: FieldSpan | None,
            constraint: FieldSpan | None,
            exception: FieldSpan | None) -> MultiClauseExtractionResponse:
        """Build a response where the actor comes from a by-agent passive."""
        clause = ClauseExtraction(
            clause_id="C1",
            source_id=source_id,
            source_text=source_text,
            clause_text=source_text,
            clause_span_start=0,
            clause_span_end=len(source_text),
            modality=modality,
            actor=passive_actor,
            action=action,
            condition=condition,
            constraint=constraint,
            exception=exception,
            confidence=0.85,
        )
        return MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id=source_id,
            source_text=source_text,
            clauses=[clause],
        )

    # ------------------------------------------------------------------
    # Null response (definition / warranty / consequence / descriptive)
    # ------------------------------------------------------------------

    def _null_response(self, source_text: str,
                       source_id: str) -> MultiClauseExtractionResponse:
        """Return a clause with all six semantic fields ``None``."""
        clause = ClauseExtraction(
            clause_id="C1",
            source_id=source_id,
            source_text=source_text,
            clause_text=source_text,
            clause_span_start=0,
            clause_span_end=len(source_text),
            modality=None,
            actor=None,
            action=None,
            condition=None,
            constraint=None,
            exception=None,
            confidence=0.1,
        )
        return MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id=source_id,
            source_text=source_text,
            clauses=[clause],
        )


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def extract_rule_first(source_text: str,
                       source_id: str = "synthetic") -> MultiClauseExtractionResponse:
    """Convenience wrapper around :class:`RuleFirstExtractor.extract`."""
    extractor = RuleFirstExtractor()
    return extractor.extract(source_text, source_id=source_id)

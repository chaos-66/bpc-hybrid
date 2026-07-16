"""Multi-clause splitter (R4).

Deterministic, rule-based decomposition of synthetic toy normative
sentences that contain multiple modality markers into individual
clause segments.  Uses only the Python standard library.

This module does NOT perform field extraction (R3), LLM fallback
(R5), or deterministic normalization (R6).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bpc_hybrid.schema import FieldSpan


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SplitError(ValueError):
    """Raised when the rule-based splitter encounters an unexpected state."""


# ---------------------------------------------------------------------------
# Clause segment representation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClauseSegment:
    """A single clause segment extracted from a compound sentence.

    Attributes:
        text: The clause text (equals ``source_text[span_start:span_end]``).
        span_start: Byte offset of the clause start in *source_text*.
        span_end: Byte offset of the clause end in *source_text*.
        inherited_condition: If the segment inherits a condition from an
            initial-unless clause, this holds the ``FieldSpan`` of that
            condition in *source_text*; otherwise ``None``.
    """

    text: str
    span_start: int
    span_end: int
    inherited_condition: object = None  # FieldSpan | None — lazy import

    def __post_init__(self) -> None:
        if self.span_start < 0:
            raise SplitError("span_start must be >= 0")
        if self.span_end < self.span_start:
            raise SplitError("span_end must be >= span_start")
        if not isinstance(self.text, str):
            raise SplitError("text must be a str")


# ---------------------------------------------------------------------------
# Modality marker specs (mirrors extractor for consistency)
# ---------------------------------------------------------------------------

_MODALITY_SPECS: list[tuple[str, str]] = [
    ("no person shall", "shall not"),
    ("shall not", "shall not"),
    ("must not", "must not"),
    ("shall", "shall"),
    ("must", "must"),
    ("may", "may"),
]

# Constraint markers that contain "and"-like conjunctions — these
# should NOT trigger a split even if they appear between modalities.
_CONSTRAINT_MARKERS: list[str] = [
    "within",
    "before",
    "after",
    "only if",
    "provided that",
]

# Patterns that signal a constraint region (text after one of these
# markers should not be split on "and").
_CONSTRAINT_REGEX = re.compile(
    r'\b(?:within|before|after|only\s+if|provided\s+that)\b',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Splitter
# ---------------------------------------------------------------------------

class RuleBasedClauseSplitter:
    """Deterministic multi-clause splitter for toy normative sentences.

    Usage::

        >>> splitter = RuleBasedClauseSplitter()
        >>> segments = splitter.split("A reviewer may inspect "
        ...                           "the file and shall record "
        ...                           "the decision.")
        >>> for s in segments:
        ...     print(s.text)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(self, source_text: str) -> list[ClauseSegment]:
        """Split *source_text* into one or more :class:`ClauseSegment` objects.

        If the text contains a single modality marker (or none), a
        single-element list is returned.
        """
        if not source_text.strip():
            return [
                ClauseSegment(text=source_text, span_start=0,
                              span_end=len(source_text))
            ]

        # --- Detect initial-unless condition ----------------------------
        initial_condition = self._detect_initial_unless(source_text)

        # --- Compute the effective start of normative content -----------
        # Skip past the initial-unless clause if present
        if initial_condition is not None:
            from bpc_hybrid.schema import FieldSpan
            cond_end = initial_condition.span_end  # type: ignore[union-attr]
            # Skip optional comma + whitespace after the condition
            while cond_end < len(source_text) and source_text[cond_end] in ', ':
                cond_end += 1
            content_start = cond_end
        else:
            content_start = 0

        # --- Detect mid-sentence unless position (never split across) ---
        mid_unless_pos = self._detect_mid_unless(source_text)

        # --- Find ALL modality markers (not just the first) -------------
        mod_positions = self._find_all_modalities(source_text, mid_unless_pos)

        if len(mod_positions) <= 1:
            # Single modality (or none) → single segment
            raw = source_text[content_start:]
            stripped = raw.strip()
            leading_ws = len(raw) - len(raw.lstrip())
            actual_start = content_start + leading_ws
            actual_end = actual_start + len(stripped)
            return [
                ClauseSegment(text=stripped, span_start=actual_start,
                              span_end=actual_end,
                              inherited_condition=initial_condition)
            ]

        # --- Determine split points (positions of clause-boundary "and") -
        # split_points[i] = (and_start, and_end) between mod i and mod i+1,
        # or None if no split
        split_points: list[tuple[int, int] | None] = []
        for i in range(len(mod_positions) - 1):
            _m_text, _m_start, m_end = mod_positions[i]
            next_m_text, next_m_start, _next_m_end = mod_positions[i + 1]
            sp = self._find_clause_boundary_and(
                source_text, m_end, next_m_start, mid_unless_pos)
            split_points.append(sp)

        # --- Build segments ---------------------------------------------
        segments: list[ClauseSegment] = []

        for i, (m_text, m_start, m_end) in enumerate(mod_positions):
            # Determine segment start
            if i == 0:
                seg_start = content_start
            else:
                prev_sp = split_points[i - 1]
                if prev_sp is not None:
                    and_end = prev_sp[1]
                    # Skip whitespace after "and"
                    while and_end < len(source_text) and source_text[and_end] == ' ':
                        and_end += 1
                    seg_start = and_end
                else:
                    # No split point → shouldn't happen
                    seg_start = m_start

            # Determine segment end
            if i < len(mod_positions) - 1:
                sp = split_points[i]
                if sp is not None:
                    seg_end = sp[0]  # start of "and"
                else:
                    # No split point — extend to end
                    seg_end = len(source_text)
            else:
                seg_end = len(source_text)

            # Extract and trim segment text
            raw = source_text[seg_start:seg_end]
            stripped = raw.strip()
            if not stripped:
                continue

            leading_ws = len(raw) - len(raw.lstrip())
            actual_start = seg_start + leading_ws
            actual_end = actual_start + len(stripped)

            seg = ClauseSegment(
                text=stripped,
                span_start=actual_start,
                span_end=actual_end,
                inherited_condition=initial_condition,
            )
            segments.append(seg)

        if not segments:
            raw = source_text[content_start:]
            stripped = raw.strip()
            leading_ws = len(raw) - len(raw.lstrip())
            actual_start = content_start + leading_ws
            actual_end = actual_start + len(stripped)
            return [
                ClauseSegment(text=stripped, span_start=actual_start,
                              span_end=actual_end,
                              inherited_condition=initial_condition)
            ]

        return segments

    # ------------------------------------------------------------------
    # Modality detection (all occurrences)
    # ------------------------------------------------------------------

    def _find_all_modalities(
            self, text: str, mid_unless_pos: int | None
    ) -> list[tuple[str, int, int]]:
        """Find all modality marker positions in *text*.

        Returns a list of ``(marker_text, start, end)`` tuples in
        ascending offset order.  Stops searching before a mid-sentence
        unless position if one exists.
        """
        results: list[tuple[str, int, int]] = []

        # Search region: up to mid_unless_pos if present
        search_end = mid_unless_pos if mid_unless_pos is not None else len(text)

        pos = 0
        while pos < search_end:
            best: tuple[str, int, int] | None = None
            for marker_lower, _norm in _MODALITY_SPECS:
                idx = text.lower().find(marker_lower, pos)
                if idx == -1 or idx >= search_end:
                    continue
                # Word-boundary check
                if not self._is_word_boundary(text, idx, len(marker_lower)):
                    continue
                if best is None or idx < best[1]:
                    best = (text[idx:idx + len(marker_lower)], idx,
                            idx + len(marker_lower))

            if best is None:
                break

            results.append(best)
            # Advance past this marker
            pos = best[2]

        return results

    @staticmethod
    def _is_word_boundary(text: str, start: int, length: int) -> bool:
        """Check that the slice is word-delimited."""
        before_ok = start == 0 or not text[start - 1].isalpha()
        after_ok = (start + length == len(text)
                    or not text[start + length].isalpha())
        return before_ok and after_ok

    # ------------------------------------------------------------------
    # Clause-boundary "and" detection
    # ------------------------------------------------------------------

    def _find_clause_boundary_and(
            self, source_text: str,
            left_end: int, right_start: int,
            mid_unless_pos: int | None,
    ) -> tuple[int, int] | None:
        """Find an "and" word that separates two modality clauses.

        Returns ``(and_start, and_end)`` or ``None`` if no boundary
        "and" exists between *left_end* and *right_start*.

        An "and" is NOT a clause boundary if it falls inside a
        constraint region (e.g. "only if X and Y").
        """
        between = source_text[left_end:right_start]

        # Find all "and" words in the between region
        candidates: list[tuple[int, int]] = []
        for m in re.finditer(r'\band\b', between, re.IGNORECASE):
            and_global_start = left_end + m.start()
            and_global_end = left_end + m.end()
            # Check if this "and" is inside a constraint region
            if self._is_inside_constraint(source_text, and_global_start):
                continue
            candidates.append((and_global_start, and_global_end))

        if not candidates:
            return None

        # Return the last candidate (closest to the right modality)
        return candidates[-1]

    def _is_inside_constraint(self, source_text: str, pos: int) -> bool:
        """Check if *pos* falls inside a constraint marker region.

        A constraint region starts at a constraint marker and runs
        to the end of the sentence (or until a mid-sentence unless).
        """
        # Find the nearest constraint marker before pos
        for m in _CONSTRAINT_REGEX.finditer(source_text):
            if m.start() <= pos:
                # pos is after (or at) this constraint marker
                # Check that pos isn't past a mid-sentence unless
                # (which would end the constraint region)
                continue
            else:
                # This marker is after pos — irrelevant
                continue

        # Check all constraint markers before pos
        for m in _CONSTRAINT_REGEX.finditer(source_text):
            if m.start() >= pos:
                break
            # pos is after this constraint marker start
            # The region from marker start to end-of-sentence or mid-unless
            # is a constraint region.
            # But we need to make sure pos isn't before the marker.
            # Actually: if pos comes after a constraint marker, and
            # no modality or mid-unless intervenes, it's inside.
            region_start = m.start()
            # Check what comes between region_start and pos
            between_marker_and_pos = source_text[region_start:pos]
            # If there's no modality marker and no mid-unless in between,
            # pos is inside the constraint region
            if not self._has_modality_in_range(source_text, region_start, pos):
                # Also check for mid-unless
                unless_in_between = re.search(
                    r'\bunless\b', between_marker_and_pos, re.IGNORECASE)
                if not unless_in_between:
                    return True

        return False

    def _has_modality_in_range(self, text: str, start: int, end: int) -> bool:
        """Check if any modality marker appears in text[start:end]."""
        region = text[start:end]
        region_lower = region.lower()
        for marker_lower, _norm in _MODALITY_SPECS:
            idx = region_lower.find(marker_lower)
            if idx == -1:
                continue
            if self._is_word_boundary(region, idx, len(marker_lower)):
                return True
        return False

    # ------------------------------------------------------------------
    # Initial unless detection
    # ------------------------------------------------------------------

    def _detect_initial_unless(self, source_text: str) -> object | None:
        """Detect an initial 'Unless X,' clause and return it as a
        ``FieldSpan`` (if the schema module is available), or ``None``.
        """
        from bpc_hybrid.schema import FieldSpan

        m = re.match(
            r'^(Unless\s+\w+(?:\s+\w+)*?)\s*,?\s+',
            source_text, re.IGNORECASE,
        )
        if not m:
            return None
        raw = m.group(1)
        return FieldSpan(text=raw, span_start=m.start(1), span_end=m.end(1),
                         confidence=0.90)

    # ------------------------------------------------------------------
    # Mid-sentence unless detection
    # ------------------------------------------------------------------

    def _detect_mid_unless(self, source_text: str) -> int | None:
        """Return the start offset of a mid-sentence 'unless', or None."""
        # Search from position 1 to avoid matching initial unless
        unless_re = re.compile(r'\bunless\b', re.IGNORECASE)
        m = unless_re.search(source_text)
        if not m:
            return None
        # If "unless" is at position 0, it's initial, not mid
        if m.start() == 0:
            # Look for a second occurrence
            m = unless_re.search(source_text, m.end())
            if not m:
                return None
        return m.start()


# ---------------------------------------------------------------------------
# Module-level convenience function
# ---------------------------------------------------------------------------

def split_normative_clauses(source_text: str) -> list[ClauseSegment]:
    """Split a normative sentence into clause segments.

    Convenience wrapper around :class:`RuleBasedClauseSplitter`.
    """
    return RuleBasedClauseSplitter().split(source_text)

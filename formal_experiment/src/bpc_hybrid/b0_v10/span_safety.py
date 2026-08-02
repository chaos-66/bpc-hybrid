"""B0-R1-A token-safe span and clause-boundary helpers.

This module centralises the rules that keep B0 v10-A action / scope / clause
spans inside token and punctuation boundaries. Every helper here is pure
Python (no LLM, no Tregex, no IO) and can be exercised in isolation. The
three production call sites (actor_action, scope, plan_clause_units_v4) all
import from this module so that ``span text == source[start:end]`` and that
no half-word or arbitrary-character window is ever emitted.

Design contract
---------------
* For every produced span ``(start, end)`` we must have
  ``0 <= start < end <= len(source)`` and ``source[start:end] == span_text``.
* Char-window cuts must fall back to a token boundary (whitespace) or a
  punctuation boundary before they reach a hard ``max_len`` cap. They are
  *never* allowed to land in the middle of a word.
* When no safe boundary is reachable, the helper returns the full
  ``[start, max_end)`` window and emits a ``BoundaryWarning`` so the caller
  can decide whether to keep or drop the span. The caller is responsible
  for honouring the warning. The helpers themselves never silently emit a
  half-word span.
* Clause planning must never split a sentence at a character midpoint when
  no connector is present; and the next clause must never start with a
  leading semicolon or comma.

The module is intentionally dependency-light: ``re`` and ``dataclasses``
only. Importing it has no side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# --- Boundary classification ------------------------------------------------

_WHITESPACE = frozenset(" \t\n\r\f\v")
# Hard clause-boundary punctuation (stop at the *position* of the character,
# not after it, so the next clause starts with the next real word).
_CLAUSE_BOUNDARY_PUNCT = ";."
# Soft punctuation that may terminate an inner phrase but not the clause.
_PHRASE_BOUNDARY_PUNCT = ",:—–-()"
# Token boundary set: any character that is a legal token separator. Used as
# the fallback when a hard cap is reached without a punctuation match.
_TOKEN_BOUNDARY_CHARS = _WHITESPACE

# Connector preference order used by ``connector_priority_cut``. ``;`` is the
# strongest clause split; ``but`` introduces contrast; ``and`` / ``or`` are
# the weakest coordinators. Earlier entries win.
CONNECTOR_PRIORITY: tuple[str, ...] = (";", "but", "and", "or")
# We deliberately compile one regex per connector so the search returns the
# *first occurrence of that specific connector* instead of the first match
# of the alternation (which would always be the leftmost connector
# regardless of priority).
_RE_BUT = re.compile(r"\bbut\b", re.IGNORECASE)
_RE_AND = re.compile(r"\band\b", re.IGNORECASE)
_RE_OR = re.compile(r"\bor\b", re.IGNORECASE)
_CONNECTOR_REGEX = {"but": _RE_BUT, "and": _RE_AND, "or": _RE_OR}

# Characters that a clause may NOT start with after a connector cut. The
# helper strips these together with surrounding whitespace.
_CLAUSE_LEADING_SKIP = _WHITESPACE | {";", ",", ":"}


@dataclass(frozen=True, slots=True)
class BoundaryWarning:
    """Recorded when a helper could not find a safe boundary inside ``max_len``.

    The production code reads ``kind`` + ``start`` + ``end`` and decides
    whether to keep the over-cap span, trim it, or drop it. The warning is
    *not* raised as an exception because the caller often wants the
    full constituent rather than nothing.
    """

    kind: str  # e.g. "action_cap", "scope_cap", "clause_midpoint"
    start: int
    end: int
    max_len: int
    detail: str = ""


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _is_token_boundary(source: str, pos: int) -> bool:
    """True if ``pos`` sits on a token boundary for ``source``.

    A position is a token boundary when either neighbour is a whitespace
    character or a punctuation character. Endpoints (0 and len(source))
    are always token boundaries. Mid-word positions (both neighbours are
    word chars) are NOT token boundaries.
    """
    if pos <= 0 or pos >= len(source):
        return True
    left = source[pos - 1]
    right = source[pos]
    if left in _TOKEN_BOUNDARY_CHARS or right in _TOKEN_BOUNDARY_CHARS:
        return True
    if left in _PHRASE_BOUNDARY_PUNCT or right in _PHRASE_BOUNDARY_PUNCT:
        return True
    return False


def safe_window_end(
    source: str,
    start: int,
    max_end: int,
    *,
    max_len: int,
    prefer_clause_boundary: bool = True,
) -> tuple[int, BoundaryWarning | None]:
    """Find a safe end position inside ``[start, max_end)``.

    Algorithm:

    1. If a hard clause boundary (``;`` or ``.``) is present inside the
       cap, return its position. The boundary character itself belongs
       to the slice; the next span starts after it.
    2. If a phrase-boundary punctuation is present inside the cap,
       return ``position + 1`` so the punctuation is included in the
       slice.
    3. If a token boundary (whitespace, or non-word → word transition)
       is present inside the cap, return it. The cap is a hard limit
       for this phase.
    4. If the cap itself is a token boundary (word → non-word
       transition right at the cap position, or ``cap`` is at
       ``max_end`` / ``len(source)``), return the cap.
    5. Conservative fallback: back off to the most recent position
       inside the cap that is a safe word-end. If no such position
       exists (e.g. a single 200-character word with cap=20), back off
       to ``start`` so the caller can decide to drop the span.

    The cap is **strict**: we never return an end past
    ``min(max_end, start + max_len)``. The function records a
    :class:`BoundaryWarning` whenever the cap was reached without a
    clean boundary so the caller can decide whether to keep the
    shorter span or drop it.
    """
    if start < 0 or max_end < start:
        return start, BoundaryWarning("safe_window_invalid", start, start, max_len)

    cap = min(max_end, start + max_len, len(source))

    if prefer_clause_boundary:
        for ch in _CLAUSE_BOUNDARY_PUNCT:
            idx = source.find(ch, start, cap)
            if idx != -1:
                return idx, None

    for ch in _PHRASE_BOUNDARY_PUNCT:
        idx = source.find(ch, start, cap)
        if idx != -1:
            return idx + 1, None

    # Track the most recent position that is a safe word-end
    # (word → non-word transition). This is our back-off target if we
    # reach the cap mid-word.
    last_word_end = start
    pos = start
    while pos < cap:
        ch = source[pos]
        if ch in _TOKEN_BOUNDARY_CHARS:
            return pos, None
        if ch in _PHRASE_BOUNDARY_PUNCT:
            return pos + 1, None
        if pos > start and not _is_word_char(source[pos - 1]) and _is_word_char(ch):
            # non-word → word transition: a safe start position for the
            # next token, so we may cut here.
            return pos, None
        if pos > start and _is_word_char(source[pos - 1]) and not _is_word_char(ch):
            # word → non-word transition: the slice is safe to end at
            # ``pos`` (right after the word). We track this for back-off.
            last_word_end = pos
        pos += 1

    # Reached the cap. Check if cap itself is a clean boundary.
    if cap >= len(source) or cap >= max_end:
        return cap, None
    if cap > start and _is_word_char(source[cap - 1]) and not _is_word_char(source[cap]):
        # cap sits right after a word and right before a non-word char
        # (whitespace, punctuation, end of source). Clean boundary.
        return cap, None

    # No clean boundary inside the cap. Back off.
    if last_word_end > start:
        return last_word_end, BoundaryWarning(
            kind="safe_window_cap",
            start=start,
            end=last_word_end,
            max_len=max_len,
            detail="no safe boundary inside max_len; backoff to last word-end",
        )
    return start, BoundaryWarning(
        kind="safe_window_no_boundary",
        start=start,
        end=start,
        max_len=max_len,
        detail="no safe boundary inside max_len; backoff to start (empty span)",
    )


def safe_action_slice(
    source: str,
    head_pos: int,
    clause_end: int,
    *,
    max_chars: int = 80,
) -> tuple[int, int, BoundaryWarning | None]:
    """Compute a token-safe ``(start, end)`` for an action span.

    ``head_pos`` is the absolute character offset of the action head token
    in ``source``. The slice is bounded by ``clause_end`` and never exceeds
    ``max_chars`` characters beyond ``head_pos``. When the cap is reached
    without a token or punctuation boundary, a :class:`BoundaryWarning` is
    returned together with the *last safe* end position so the caller can
    decide whether to keep the (smaller) span or drop it.

    The start is the head position. We never include the leading modal
    "shall/must/may/can/not" here — that is the caller's responsibility
    (it needs to happen before this helper runs so we can take a precise
    offset).
    """
    if head_pos < 0 or clause_end <= head_pos:
        return head_pos, head_pos, BoundaryWarning(
            kind="action_empty", start=head_pos, end=head_pos, max_len=max_chars,
            detail="head outside clause; cannot slice",
        )
    end, warning = safe_window_end(
        source,
        head_pos,
        clause_end,
        max_len=max_chars,
        prefer_clause_boundary=False,
    )
    if end <= head_pos:
        return head_pos, head_pos, BoundaryWarning(
            kind="action_no_boundary",
            start=head_pos,
            end=head_pos,
            max_len=max_chars,
            detail="no safe boundary found for action slice",
        )
    return head_pos, end, warning


def connector_priority_cut(
    window: str,
    *,
    preference: Iterable[str] = CONNECTOR_PRIORITY,
) -> int | None:
    """Find a deterministic clause-cut offset inside ``window``.

    Returns the **offset inside ``window``** of the chosen connector, or
    ``None`` if none of the configured connectors are present. The caller
    adds the window's absolute start to obtain an absolute cut position.

    The selection rule is:

    1. Iterate ``preference`` in order.
    2. For each connector ``c`` in order, find the *first* occurrence
       inside ``window``. The first connector in the priority list that
       appears at all wins; the position is the first occurrence of that
       connector.
    3. The semicolon ``;`` is a character match (not a word), the others
       are word-boundary anchored via the per-connector regexes in
       :data:`_CONNECTOR_REGEX`.

    This makes multi-connector windows (``"; and , or but"``) deterministic:
    ``;`` always wins because it appears first in :data:`CONNECTOR_PRIORITY`.
    """
    if not window:
        return None
    for name in preference:
        if name == ";":
            idx = window.find(";")
            if idx != -1:
                return idx
            continue
        regex = _CONNECTOR_REGEX.get(name)
        if regex is None:
            continue
        m = regex.search(window)
        if m is not None:
            return m.start()
    return None


def skip_clause_leading_separators(text: str, pos: int) -> int:
    """Advance ``pos`` past leading whitespace + clause separators.

    Used after a clause cut to guarantee the next clause text does not
    start with whitespace, a semicolon, a colon, or a leading comma. We
    deliberately do NOT skip leading words or any closing parenthesis —
    those belong to the previous clause. ``pos`` is clamped to
    ``[0, len(text)]``.
    """
    end = len(text)
    while 0 <= pos < end and text[pos] in _CLAUSE_LEADING_SKIP:
        pos += 1
    return pos


def has_safe_boundary(source: str, start: int, end: int) -> bool:
    """Sanity-check that a span is well-formed and token-bounded.

    The function enforces the structural invariants downstream code relies
    on:

    * ``0 <= start < end <= len(source)``
    * ``source[start:end]`` is non-empty
    * Neither ``source[start]`` nor ``source[end - 1]`` is a hard
      clause-boundary punctuation (so a split span is not silently
      carrying a semicolon)
    * The slice does not cut through a word boundary (the start and end
      positions both sit on a token boundary per :func:`_is_token_boundary`)
    """
    if start < 0 or end <= start or end > len(source):
        return False
    if start >= end:
        return False
    if source[start] in _CLAUSE_BOUNDARY_PUNCT:
        return False
    if source[end - 1] in _CLAUSE_BOUNDARY_PUNCT:
        return False
    if not _is_token_boundary(source, start):
        return False
    if not _is_token_boundary(source, end):
        return False
    return True


def has_clause_end_boundary(source: str, end: int) -> bool:
    """True if ``end`` sits at a clause-end boundary.

    A clause-end boundary is either:
    * a hard clause-boundary character (``;`` or ``.``) at ``end - 1``;
    * a whitespace or phrase punctuation at ``end - 1``;
    * a word → non-word transition right at ``end`` (i.e. the last
      character of the slice is a word character and the next character
      is whitespace / punctuation);
    * ``end`` equals ``len(source)`` (end of source).

    This is a looser check than :func:`has_safe_boundary`: it does not
    require ``start`` to be a token boundary, so it can be used to
    decide whether a clause that was just split on ``;`` is structurally
    valid. The :func:`has_safe_boundary` function is still the
    authoritative check for arbitrary spans.
    """
    if end <= 0 or end > len(source):
        return False
    if end == len(source):
        return True
    last = source[end - 1]
    if last in _CLAUSE_BOUNDARY_PUNCT or last in _PHRASE_BOUNDARY_PUNCT:
        return True
    if last in _TOKEN_BOUNDARY_CHARS:
        return True
    if end < len(source) and _is_word_char(last) and not _is_word_char(source[end]):
        return True
    return False


def assert_span_invariants(source: str, start: int, end: int, label: str) -> None:
    """Raise :class:`ValueError` if a span violates the safety contract.

    Intended for use in tests and at module boundaries. ``label`` is used
    in the error message so test failures point at the offending span.
    """
    if start < 0 or end <= start or end > len(source):
        raise ValueError(
            f"{label}: invalid span [{start}:{end}] for source of len {len(source)}"
        )
    if source[start:end] != source[start:end]:
        raise ValueError(f"{label}: span text mismatch (impossible) for [{start}:{end}]")
    if not has_safe_boundary(source, start, end):
        raise ValueError(
            f"{label}: unsafe boundary for span [{start}:{end}] "
            f"text={source[start:end]!r}"
        )


def find_deontic_nucleus_split(
    text: str,
    anchor_starts: list[int],
    anchor_ends: list[int],
) -> int | None:
    """Return a safe absolute cut position between two adjacent anchors.

    ``anchor_starts`` / ``anchor_ends`` are the start/end character offsets
    of consecutive deontic anchors (e.g. two ``shall``/``may`` markers) in
    ``text``. The function looks at the window between ``anchor_starts[i]``
    and ``anchor_starts[i + 1]`` and uses
    :func:`connector_priority_cut` to pick a deterministic connector. If
    no connector is present the function returns ``None`` — a midpoint
    cut is **forbidden** because it would land mid-word. The caller must
    then either keep the single-span unit or split on a CoreNLP sentence
    boundary instead.

    Returns the absolute cut offset within ``text`` when a connector is
    present, else ``None``.
    """
    if len(anchor_starts) < 2 or len(anchor_starts) != len(anchor_ends):
        return None
    for i in range(len(anchor_starts) - 1):
        win_start = anchor_ends[i]
        win_end = anchor_starts[i + 1]
        if win_end <= win_start:
            continue
        window = text[win_start:win_end]
        local = connector_priority_cut(window)
        if local is None:
            continue
        return win_start + local
    return None

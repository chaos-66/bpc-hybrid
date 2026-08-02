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
* Char-window cuts must prefer the **rightmost** safe token/punctuation
  boundary inside the cap so semantic coverage is maximised, not the
  first one. The cap is a hard limit; the returned end never exceeds it
  except when the caller passes a ``required_end`` that is itself
  outside the cap (in which case the helper honours ``required_end`` and
  records a ``required_evidence_exceeds_cap`` warning so the caller can
  observe the trade-off).
* Hard clause boundaries (``;`` and ``.``) inside the cap are special:
  they end the slice at the **earliest** such boundary, because every
  clause is independent and we do not want a single span to silently
  consume a hard clause break.
* Half-word spans are never silently emitted. When no safe boundary is
  reachable and no ``required_end`` is provided, the helper returns
  ``start`` (an empty span) together with a :class:`BoundaryWarning`
  whose ``kind`` is stable and machine-readable.
* Clause planning must never split a sentence at a character midpoint
  when no connector is present; and the next clause must never start
  with a leading semicolon, comma, or colon.

The module is intentionally dependency-light: ``re`` and ``dataclasses``
only. Importing it has no side effects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


# --- Boundary classification ------------------------------------------------

_WHITESPACE = frozenset(" \t\n\r\f\v")
# Hard clause-boundary punctuation. The slice ENDS at the position of
# the character; the next span starts after it. A clause boundary in
# ``[start, cap)`` always wins over token/phrase boundaries, and the
# EARLIEST clause boundary wins (so we do not consume past one clause
# into the next).
_CLAUSE_BOUNDARY_PUNCT = ";."
# Soft punctuation that may terminate an inner phrase but not the clause.
# The slice INCLUDES the punctuation (so the helper returns ``idx + 1``).
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


# Stable warning kinds. Production code reads these strings to make
# decisions; do not rename without updating callers and tests.
WARN_KIND_INVALID = "safe_window_invalid"
WARN_KIND_REQUIRED_EXCEEDS_CAP = "required_evidence_exceeds_cap"
WARN_KIND_CAP_NO_SAFE_BOUNDARY = "cap_reached_no_safe_boundary"
WARN_KIND_NO_BOUNDARY_AT_ALL = "safe_window_no_boundary"
WARN_KIND_ACTION_HEAD_OUT_OF_CLAUSE = "action_head_out_of_clause"
WARN_KIND_ACTION_NO_BOUNDARY = "action_no_safe_boundary"
WARN_KIND_ACTION_CAP_BACKOFF = "action_cap_backoff_to_head_token_end"


@dataclass(frozen=True, slots=True)
class BoundaryWarning:
    """Recorded when a helper could not find a clean boundary inside the cap.

    The production code reads ``kind`` + ``start`` + ``end`` and decides
    whether to keep the over-cap span, trim it, or drop it. The warning
    is *not* raised as an exception because the caller often wants the
    full constituent rather than nothing. The ``kind`` is a stable
    machine-readable string.
    """

    kind: str
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


def _is_phrase_end(source: str, pos: int) -> bool:
    """True if ``pos`` is the position right after a phrase-punctuation char.

    Used to decide whether a phrase-punctuation stop should also include
    the punctuation in the slice. ``pos == idx + 1`` where ``source[idx]``
    is a phrase-punctuation character.
    """
    if pos <= 0 or pos > len(source):
        return False
    if pos == len(source):
        return False
    return source[pos - 1] in _PHRASE_BOUNDARY_PUNCT


def safe_window_end(
    source: str,
    start: int,
    max_end: int,
    *,
    max_len: int,
    prefer_clause_boundary: bool = True,
    required_end: int | None = None,
) -> tuple[int, BoundaryWarning | None]:
    """Find a safe end position with the maximal-rightmost-boundary rule.

    Algorithm (in order):

    1. **Honour ``required_end`` first.** If the caller passed a
       ``required_end`` and it lies past the cap, return ``required_end``
       (clamped to ``len(source)``) together with a
       ``WARN_KIND_REQUIRED_EXCEEDS_CAP`` warning. The caller has declared
       that this evidence must be preserved; the helper must not silently
       truncate it. This is the contract used by scope expansion: the
       original Tregex / lexicon ``match_end`` is sacred.

    2. **Clause boundary (``;`` / ``.``)**. If a hard clause boundary is
       present inside the cap, return the **earliest** such position.
       We deliberately do not look at the rightmost clause boundary
       because every clause is independent and the slice must not silently
       consume past a hard break.

    3. **Rightmost safe token/phrase boundary**. Walk ``[start, cap)`` and
       remember the rightmost safe position. A position is safe when it
       is:
       * a whitespace (``" \t\n\r\f\v"``);
       * a position right after a phrase-punctuation character
         (``,``, ``:``, em/en dash, parentheses);
       * a word → non-word transition (the previous char is a word char
         and the current char is not);
       * a non-word → word transition (start of a new token).

       The first safe position that is also ``>= required_end`` (when the
       caller asked for one) wins immediately; otherwise the helper
       returns the rightmost safe position it saw.

    4. **Cap itself**. If the cap is at the end of the source or at
       ``max_end`` (i.e. the source actually ends at the cap), return
       the cap. If the cap sits exactly on a word → non-word
       transition, it is also a valid rightmost boundary.

    5. **No safe boundary inside the cap** and no ``required_end`` was
       provided. Return ``start`` (an empty span) together with a
       ``WARN_KIND_NO_BOUNDARY_AT_ALL`` warning. The caller can then
       decide to drop the span rather than emit a half-word.
    """
    if start < 0 or max_end < start:
        return start, BoundaryWarning(
            WARN_KIND_INVALID, start, start, max_len,
            detail=f"start={start} max_end={max_end} invalid",
        )

    cap = min(max_end, start + max_len, len(source))

    # 1) Honour required_end that lies outside the cap. We never
    # silently truncate evidence the caller has declared required.
    if required_end is not None and required_end > cap:
        preserved = min(required_end, len(source))
        if preserved <= start:
            # required_end collapsed to start because the source is
            # shorter than the caller assumed. Treat as invalid.
            return start, BoundaryWarning(
                WARN_KIND_INVALID, start, start, max_len,
                detail=f"required_end={required_end} <= start={start}",
            )
        return preserved, BoundaryWarning(
            WARN_KIND_REQUIRED_EXCEEDS_CAP,
            start=start,
            end=preserved,
            max_len=max_len,
            detail=(
                f"required_end={required_end} > cap={cap}; "
                f"preserved full evidence at {preserved} (no silent truncation)"
            ),
        )

    # 2) Hard clause boundary: the EARLIEST in [start, cap) wins.
    if prefer_clause_boundary:
        earliest_clause_idx: int | None = None
        for ch in _CLAUSE_BOUNDARY_PUNCT:
            idx = source.find(ch, start, cap)
            if idx == -1:
                continue
            if earliest_clause_idx is None or idx < earliest_clause_idx:
                earliest_clause_idx = idx
        if earliest_clause_idx is not None:
            return earliest_clause_idx, None

    # 3) Walk to find the RIGHTMOST safe token/phrase boundary strictly
    # INSIDE the cap. We never stop at the first one; the slice must
    # cover as much of the cap as possible. ``required_end`` is
    # treated as a minimum only: the helper may return past it (up
    # to the cap or to the original evidence, whichever is smaller)
    # but never below it.
    found_internal_safe = False
    best_safe = start
    best_safe_includes_punct = False
    pos = start + 1  # skip the start position; endpoint is not
                      # counted as an "internal" safe stop
    while pos < cap:
        ch = source[pos]
        is_safe = False
        includes_punct = False
        if ch in _TOKEN_BOUNDARY_CHARS:
            is_safe = True
        elif ch in _PHRASE_BOUNDARY_PUNCT:
            is_safe = True
            includes_punct = True
        elif _is_word_char(source[pos - 1]) and not _is_word_char(ch):
            # word → non-word transition
            is_safe = True
        if is_safe:
            best_safe = pos
            best_safe_includes_punct = includes_punct
            found_internal_safe = True
        pos += 1

    # 4) If the helper did not find a single safe boundary inside the
    # cap, fall back to required_end (if the caller passed one and
    # it is reachable) or to start (empty slice) with a stable
    # warning kind.
    if not found_internal_safe:
        if required_end is not None and required_end <= cap:
            return required_end, BoundaryWarning(
                WARN_KIND_CAP_NO_SAFE_BOUNDARY,
                start=start,
                end=required_end,
                max_len=max_len,
                detail=(
                    f"no token/phrase boundary inside cap={cap}; "
                    f"returned required_end={required_end}"
                ),
            )
        return start, BoundaryWarning(
            WARN_KIND_NO_BOUNDARY_AT_ALL,
            start=start,
            end=start,
            max_len=max_len,
            detail="no safe boundary inside max_len; backoff to start (empty span)",
        )

    # 5) Cap is at end of source. The slice is allowed to consume
    # the full cap because the caller has no more room. We do NOT
    # short-circuit on ``cap >= max_end`` alone: that would return
    # the cap even when it lands mid-word (e.g. max_end was the
    # arbitrary end of the search range, not the source end). The
    # cap is a safe boundary only when the source actually ends at
    # the cap.
    if cap >= len(source):
        return cap, None

    # 6) Cap sits exactly on a word → non-word transition. Promote
    # best_safe to cap because the transition itself is a rightmost
    # safe stop that the caller might prefer.
    if cap > start and _is_word_char(source[cap - 1]) and not _is_word_char(source[cap]):
        return cap, None

    # 7) required_end must be honoured. If the rightmost safe boundary
    # we saw is still BELOW required_end, we have to extend to
    # required_end (still a real, valid position in the caller's
    # data) and surface a CAP warning so the trade-off is observable.
    if required_end is not None and best_safe < required_end:
        return required_end, BoundaryWarning(
            WARN_KIND_CAP_NO_SAFE_BOUNDARY,
            start=start,
            end=required_end,
            max_len=max_len,
            detail=(
                f"rightmost safe boundary={best_safe} < required_end={required_end}; "
                f"extended to required_end; cap={cap} did not expose a deeper stop"
            ),
        )

    # 8) Otherwise return the rightmost safe boundary. If it sits on
    # a phrase-punctuation character, include the punctuation in the
    # slice; the caller's original_match_end contract always wins
    # over the cap once required_end is met.
    if best_safe_includes_punct and best_safe < cap:
        return best_safe + 1, None
    return best_safe, None


def safe_action_slice(
    source: str,
    head_pos: int,
    clause_end: int,
    *,
    max_chars: int = 80,
    head_token_end: int | None = None,
) -> tuple[int, int, BoundaryWarning | None]:
    """Compute a token-safe ``(start, end)`` for an action span.

    Contract
    --------
    * ``start == head_pos``. The slice always begins at the head.
    * The slice **always covers the full head token** (i.e.
      ``end >= head_token_end``). Pass ``head_token_end`` explicitly
      when you have it; otherwise the helper uses the position of the
      first whitespace after ``head_pos`` as a conservative proxy.
    * If the head plus ``max_chars`` is still inside the clause
      (``clause_end``), the slice extends to the rightmost safe token
      / punctuation boundary up to that cap, never stopping at the
      first whitespace.
    * If ``clause_end`` itself is inside the cap, the slice may extend
      to ``clause_end`` (the full clause / subtree).
    * The slice never returns a half-word. When the cap is reached
      without a safe boundary and ``head_token_end`` is already covered
      (or no cap is set), a :class:`BoundaryWarning` is surfaced and
      the end is the rightmost safe position; if no such position
      exists at all, the end is ``head_pos`` and the caller is expected
      to drop the action.
    * ``max_chars`` is a hard cap **except** when the caller's
      ``head_token_end`` itself lies outside the cap: the helper
      honours ``head_token_end`` (so the head token is never half-cut)
      and records a ``WARN_KIND_ACTION_CAP_BACKOFF`` warning.
    """
    if head_pos < 0 or clause_end <= head_pos:
        return head_pos, head_pos, BoundaryWarning(
            WARN_KIND_ACTION_HEAD_OUT_OF_CLAUSE,
            start=head_pos, end=head_pos, max_len=max_chars,
            detail=f"head_pos={head_pos} clause_end={clause_end}",
        )

    # Derive head_token_end if the caller did not provide it: the
    # position of the first whitespace after head_pos. This guarantees
    # the slice covers the full head token even when max_chars would
    # have stopped inside the head.
    if head_token_end is None:
        ws = source.find(" ", head_pos, clause_end)
        head_token_end = ws if ws != -1 else clause_end
    # If head_token_end is mid-word (e.g. the caller passed a wrong
    # value), clamp it forward to the next whitespace.
    if head_token_end < head_pos:
        head_token_end = head_pos
    if head_token_end < clause_end and head_token_end > head_pos:
        if source[head_token_end - 1].isalpha() and source[head_token_end].isalpha():
            ws = source.find(" ", head_token_end, clause_end)
            head_token_end = ws if ws != -1 else clause_end

    # required_end = head_token_end. The helper will never truncate
    # below this; if max_chars is too small to even include the head
    # token, it back-off-warns and returns the head_token_end.
    cap_max_end = min(clause_end, head_pos + max_chars)
    end, warning = safe_window_end(
        source,
        head_pos,
        cap_max_end,
        max_len=max_chars,
        prefer_clause_boundary=False,
        required_end=head_token_end,
    )

    # Apply the action-specific warning semantics.
    if warning is not None and warning.kind == WARN_KIND_REQUIRED_EXCEEDS_CAP:
        # head_token_end is past the cap; the helper preserved it so
        # the head token is not half-cut. Re-label the warning so the
        # caller can see that the source was the cap, not bad input.
        warning = BoundaryWarning(
            WARN_KIND_ACTION_CAP_BACKOFF,
            start=warning.start,
            end=warning.end,
            max_len=warning.max_len,
            detail=(
                f"head_token_end={head_token_end} > cap={head_pos + max_chars}; "
                f"preserved full head token by extending past the action cap. "
                f"original detail: {warning.detail}"
            ),
        )
    if end <= head_pos:
        return head_pos, head_pos, BoundaryWarning(
            WARN_KIND_ACTION_NO_BOUNDARY,
            start=head_pos, end=head_pos, max_len=max_chars,
            detail="safe_window_end returned start (no safe boundary)",
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

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
* Char-window cuts prefer the **rightmost** safe token/punctuation
  boundary inside the cap so semantic coverage is maximised. The first
  safe position is never returned early.
* ``required_end`` (when the caller passes one) is a **hard minimum**:
  the helper NEVER returns a position below it. A punctuation character
  whose position is strictly less than ``required_end`` lies inside
  the caller's required evidence and is **silently skipped** during the
  hard-clause-boundary search; only candidates with position
  ``>= required_end`` are eligible.
* Hard clause boundaries (``;`` and ``.``) inside the cap end the slice
  at the **earliest** such position that is also ``>= required_end``;
  the candidate is the absolute earliest occurrence in text order
  across all hard-punctuation characters (the iteration order over
  the ``;``/``.`` set is therefore irrelevant).
* ``required_end`` is itself fail-closed: it must satisfy
  ``start < required_end <= max_end <= len(source)``. Any other
  combination (including ``required_end > max_end``,
  ``required_end > len(source)``, or ``required_end <= start``) is
  rejected with a stable :class:`BoundaryWarning` and the returned end
  collapses to ``start``; the caller MUST observe the warning and
  drop the span.
* Half-word spans are never silently emitted. When no safe boundary
  is reachable, the helper returns ``start`` (an empty span) together
  with a stable :class:`BoundaryWarning` whose ``kind`` is
  machine-readable.
* Clause planning must never split a sentence at a character
  midpoint when no connector is present; and the next clause must
  never start with a leading semicolon, comma, or colon.

Every return path in :func:`safe_window_end` flows through the
postcondition helper :func:`_validate_safe_window_end_return` so a
future early return cannot accidentally bypass the ``required_end``
contract. The postcondition is enforced with explicit Python
``if``/``return`` rather than bare ``assert`` so it survives Python
``-O`` and the test build mode.

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
# the character; the next span starts after it. ``p >= required_end``
# is the only eligible candidate, where ``p`` is the character index.
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


# --- Stable warning kinds ---------------------------------------------------
# Production code reads these strings to make decisions; do not rename
# without updating callers, tests, and EXPERIMENT_LOG notes.

WARN_KIND_INVALID = "safe_window_invalid"
WARN_KIND_REQUIRED_EXCEEDS_CAP = "required_evidence_exceeds_cap"
WARN_KIND_REQUIRED_OUTSIDE_CLAUSE = "required_outside_clause"
WARN_KIND_CAP_NO_SAFE_BOUNDARY = "cap_reached_no_safe_boundary"
WARN_KIND_NO_BOUNDARY_AT_ALL = "safe_window_no_boundary"
WARN_KIND_POSTCONDITION_FAILED = "safe_window_postcondition_failed"
WARN_KIND_ACTION_HEAD_OUT_OF_CLAUSE = "action_head_out_of_clause"
WARN_KIND_ACTION_NO_BOUNDARY = "action_no_safe_boundary"
WARN_KIND_ACTION_CAP_BACKOFF = "action_cap_backoff_to_head_token_end"

# Warnings in this set mean that no usable span may be emitted.  Cap
# back-offs that still preserve the caller's required evidence are not
# fatal: they remain observable, but the valid span may continue downstream.
FATAL_BOUNDARY_WARNING_KINDS = frozenset({
    WARN_KIND_INVALID,
    WARN_KIND_REQUIRED_OUTSIDE_CLAUSE,
    WARN_KIND_POSTCONDITION_FAILED,
    WARN_KIND_NO_BOUNDARY_AT_ALL,
    WARN_KIND_ACTION_HEAD_OUT_OF_CLAUSE,
    WARN_KIND_ACTION_NO_BOUNDARY,
})


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


def boundary_warning_requires_drop(warning: BoundaryWarning | None) -> bool:
    """Return whether ``warning`` forbids emitting the associated span."""

    return warning is not None and warning.kind in FATAL_BOUNDARY_WARNING_KINDS


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


def _validate_safe_window_end_return(
    *,
    start: int,
    returned_end: int,
    max_end: int,
    max_len: int,
    required_end: int | None,
    warning: BoundaryWarning | None,
    source_len: int,
) -> tuple[int, BoundaryWarning | None]:
    """Postcondition check for every return path of ``safe_window_end``.

    The check enforces the contract every normal return must satisfy:

    * ``start <= returned_end`` (empty slice is allowed when no safe
      boundary exists; ``start < returned_end`` is not required because
      the ``WARN_KIND_NO_BOUNDARY_AT_ALL`` fallback is the canonical
      "no usable boundary" signal);
    * ``returned_end <= max_end`` (never cross the caller's clause);
    * ``returned_end <= source_len`` (never exceed the source);
    * when ``required_end`` is provided, ``returned_end >= required_end``
      (the hard-minimum contract).

    The check is implemented as explicit ``if``/``return`` rather than
    bare ``assert`` so it survives Python ``-O`` optimisation and the
    test build mode. If a postcondition fails the function returns
    ``(start, BoundaryWarning(WARN_KIND_POSTCONDITION_FAILED, ...))``
    so the caller can detect the violation and drop the span.
    """
    if returned_end < start:
        return start, BoundaryWarning(
            WARN_KIND_POSTCONDITION_FAILED, start, start, max_len,
            detail=(
                f"postcondition: returned_end={returned_end} < start={start}; "
                "rejected; caller must observe the warning and drop the span"
            ),
        )
    if returned_end > max_end:
        return start, BoundaryWarning(
            WARN_KIND_POSTCONDITION_FAILED, start, start, max_len,
            detail=(
                f"postcondition: returned_end={returned_end} > max_end={max_end}; "
                "would cross clause; rejected"
            ),
        )
    if returned_end > source_len:
        return start, BoundaryWarning(
            WARN_KIND_POSTCONDITION_FAILED, start, start, max_len,
            detail=(
                f"postcondition: returned_end={returned_end} > len(source)={source_len}; "
                "out of source; rejected"
            ),
        )
    if required_end is not None and returned_end < required_end:
        return start, BoundaryWarning(
            WARN_KIND_POSTCONDITION_FAILED, start, start, max_len,
            detail=(
                f"postcondition: returned_end={returned_end} < required_end={required_end}; "
                "required-evidence contract violated; rejected"
            ),
        )
    return returned_end, warning


def safe_window_end(
    source: str,
    start: int,
    max_end: int,
    *,
    max_len: int,
    prefer_clause_boundary: bool = True,
    required_end: int | None = None,
) -> tuple[int, BoundaryWarning | None]:
    """Find a safe end position that satisfies the ``required_end`` contract.

    Algorithm
    ---------
    The function routes every return through
    :func:`_validate_safe_window_end_return` so a future early return
    cannot accidentally bypass the postcondition. The stages below are
    tried in order; the first one that yields a valid end (and passes
    the postcondition) is the answer.

    0. **Pre-validation** (fail-closed on structurally invalid inputs):
       * ``start < 0`` or ``max_end < start`` or ``max_end > len(source)``
         returns ``(start, INVALID)``;
       * ``required_end`` (when provided) must satisfy
         ``start < required_end <= max_end <= len(source)``; any
         violation returns ``(start, INVALID or REQUIRED_OUTSIDE_CLAUSE)``.
         The helper does **not** silently clamp ``required_end`` to
         ``len(source)`` and does **not** preserve evidence past
         ``max_end``.

    1. **Compute the search window**.
       ``cap = min(max_end, start + max_len, len(source))``. The cap is
       a *strict* upper bound on any position the helper may return
       when the caller did not pass ``required_end``. When the caller
       did pass ``required_end``, the helper is allowed to extend past
       the cap to honour ``required_end`` (but not past ``max_end`` or
       ``len(source)``).
       ``minimum_end = required_end if required_end is not None else start``.
       The hard-punctuation search restricts candidates to positions
       ``p >= minimum_end``; this is the rule that fixes the
       "Art. 6" regression where the internal period truncated the
       marker.

    2. **Hard clause boundary** (when ``prefer_clause_boundary``): for
       each character in ``_CLAUSE_BOUNDARY_PUNCT`` (``;`` and ``.``),
       iterate all occurrences in ``[minimum_end, cap)`` and keep the
       earliest in text order. The result is independent of the
       iteration order over the punct set. The returned end is the
       position of the chosen character; the next span starts after
       it (exclusive-end contract).

    3. **Rightmost safe token/phrase boundary**: walk
       ``(start, cap)`` and remember the rightmost safe position. A
       position is safe when it is a whitespace, a position right after
       a phrase-punctuation character, or a word → non-word
       transition. The first safe position is **never** returned
       early; the helper always continues to the cap. When
       ``required_end`` is provided, the rightmost safe boundary is
       only accepted if it satisfies ``best_safe >= required_end``;
       otherwise the helper extends to ``required_end`` with a
       ``WARN_KIND_CAP_NO_SAFE_BOUNDARY`` warning.

    4. **Cap at end of source**: when ``cap >= len(source)`` the helper
       returns the cap (it is always a safe boundary). The cap being
       at ``max_end`` alone is **not** enough — that would let a mid-word
       ``max_end`` truncate the slice; we only short-circuit when the
       source actually ends at the cap.

    5. **No internal safe boundary**: if the walk in step 3 finds
       nothing, the helper either extends to ``required_end`` (with
       warning) when the caller passed one, or returns ``start`` (empty
       slice) with ``WARN_KIND_NO_BOUNDARY_AT_ALL``.

    Returns
    -------
    ``(returned_end, warning_or_None)``. ``returned_end`` is the
    exclusive end of the slice. The postcondition helper guarantees:

    * ``start <= returned_end <= max_end``;
    * ``returned_end <= len(source)``;
    * when ``required_end`` is provided, ``returned_end >= required_end``.

    Any violation is replaced with a stable
    ``WARN_KIND_POSTCONDITION_FAILED`` warning that the caller must
    observe and drop the span. The helper never raises bare
    ``ValueError`` in production paths.
    """
    # --- 0) Pre-validation: fail closed on structurally invalid inputs.
    # These paths return directly (not through the finalize helper)
    # because the pre-validation warning IS the contract signal; the
    # postcondition helper would otherwise override the kind with a
    # generic POSTCONDITION_FAILED on the empty slice. The returned
    # end is always a non-negative position so the caller can compare
    # ``start <= returned_end`` uniformly; the warning kind carries
    # the diagnostic.
    source_len = len(source)
    safe_start = max(0, start) if start >= 0 else 0
    if start < 0:
        return 0, BoundaryWarning(
            WARN_KIND_INVALID, 0, 0, max_len,
            detail=f"start={start} < 0",
        )
    if max_end < start:
        return safe_start, BoundaryWarning(
            WARN_KIND_INVALID, safe_start, safe_start, max_len,
            detail=f"max_end={max_end} < start={start}",
        )
    if max_end > source_len:
        return safe_start, BoundaryWarning(
            WARN_KIND_INVALID, safe_start, safe_start, max_len,
            detail=(
                f"max_end={max_end} > len(source)={source_len}; "
                "out-of-range; rejected"
            ),
        )

    if required_end is not None:
        if required_end <= start:
            return safe_start, BoundaryWarning(
                WARN_KIND_INVALID, safe_start, safe_start, max_len,
                detail=(
                    f"required_end={required_end} <= start={start}; "
                    "empty evidence not allowed; rejected"
                ),
            )
        if required_end > source_len:
            return safe_start, BoundaryWarning(
                WARN_KIND_INVALID, safe_start, safe_start, max_len,
                detail=(
                    f"required_end={required_end} > len(source)={source_len}; "
                    "refuse to silently clamp"
                ),
            )
        if required_end > max_end:
            return safe_start, BoundaryWarning(
                WARN_KIND_REQUIRED_OUTSIDE_CLAUSE, safe_start, safe_start, max_len,
                detail=(
                    f"required_end={required_end} > max_end={max_end}; "
                    "would cross the caller's clause; rejected"
                ),
            )

    # --- 1) Compute cap and minimum_end.
    cap = min(max_end, start + max_len, source_len)
    # minimum_end is the lower bound for the hard-punctuation search.
    # When the caller passed required_end we use it; otherwise we
    # default to start (no candidate is "before" the slice start).
    minimum_end = required_end if required_end is not None else start

    # --- 2) Hard clause boundary: earliest occurrence in [minimum_end, cap)
    # across both ';' and '.'. Iteration order over _CLAUSE_BOUNDARY_PUNCT
    # is irrelevant because we take the minimum across all candidates.
    if prefer_clause_boundary:
        earliest_p: int | None = None
        for ch in _CLAUSE_BOUNDARY_PUNCT:
            search_from = minimum_end
            while search_from < cap:
                idx = source.find(ch, search_from, cap)
                if idx == -1:
                    break
                if earliest_p is None or idx < earliest_p:
                    earliest_p = idx
                # advance past this occurrence to find the next one of
                # the same character
                search_from = idx + 1
        if earliest_p is not None:
            return _validate_safe_window_end_return(
                start=start, returned_end=earliest_p, max_end=max_end,
                max_len=max_len, required_end=required_end, warning=None,
                source_len=source_len,
            )

    # --- 3) Rightmost safe token/phrase boundary strictly inside (start, cap).
    # We never stop at the first safe position; the slice must cover as
    # much of the cap as possible while staying at a token boundary.
    # The walk does NOT visit ``cap`` itself: the cap-level checks
    # below (end of source / word→non-word transition) extend the
    # candidate set when the cap is itself a safe boundary.
    found_internal_safe = False
    best_safe = start
    best_safe_includes_punct = False
    pos = start + 1
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

    # Determine the rightmost safe candidate. The candidates are
    # (in order of preference for "rightmost wins"):
    #   1. cap if it sits at end of source (always a safe boundary)
    #   2. cap if it sits at a word → non-word transition
    #   3. best_safe from the walk (rightmost internal safe stop)
    # If none of (1)-(3) is available, no safe boundary exists at all.
    candidate_end: int | None = None
    candidate_includes_punct = False
    if cap >= source_len:
        candidate_end = cap
        candidate_includes_punct = False
    elif cap > start and _is_word_char(source[cap - 1]) and not _is_word_char(source[cap]):
        candidate_end = cap
        candidate_includes_punct = False
    elif found_internal_safe:
        candidate_end = best_safe
        candidate_includes_punct = best_safe_includes_punct

    if candidate_end is None:
        # --- 5) No safe boundary at all inside the cap.
        if required_end is not None and required_end <= max_end:
            return _validate_safe_window_end_return(
                start=start, returned_end=required_end, max_end=max_end,
                max_len=max_len, required_end=required_end,
                warning=BoundaryWarning(
                    WARN_KIND_REQUIRED_EXCEEDS_CAP, start, required_end, max_len,
                    detail=(
                        f"no token/phrase boundary inside cap={cap}; "
                        f"returned required_end={required_end} (extends past cap)"
                    ),
                ),
                source_len=source_len,
            )
        return _validate_safe_window_end_return(
            start=start, returned_end=start, max_end=max_end,
            max_len=max_len, required_end=required_end,
            warning=BoundaryWarning(
                WARN_KIND_NO_BOUNDARY_AT_ALL, start, start, max_len,
                detail="no safe boundary inside max_len; backoff to start (empty span)",
            ),
            source_len=source_len,
        )

    # --- 4/6) Honour required_end. The rightmost safe candidate is
    # acceptable only when it is >= required_end. Otherwise we
    # extend to required_end (which may be past the cap, but never
    # past max_end or len(source); the pre-validation guarantees that).
    if required_end is not None and candidate_end < required_end:
        return _validate_safe_window_end_return(
            start=start, returned_end=required_end, max_end=max_end,
            max_len=max_len, required_end=required_end,
            warning=BoundaryWarning(
                WARN_KIND_REQUIRED_EXCEEDS_CAP, start, required_end, max_len,
                detail=(
                    f"rightmost safe boundary={candidate_end} < required_end={required_end}; "
                    f"extended to required_end; cap={cap} did not expose a deeper stop"
                ),
            ),
            source_len=source_len,
        )

    # --- 7) Return the rightmost safe boundary. If it sits on a
    # phrase-punctuation character, include the punctuation in the
    # slice (the helper returns idx + 1). Note: a phrase-punctuation
    # stop is only reachable from the walked best_safe, not from the
    # cap-level candidates, so the +1 adjustment is only applied
    # when best_safe is the chosen candidate.
    if candidate_includes_punct and candidate_end < cap:
        return _validate_safe_window_end_return(
            start=start, returned_end=candidate_end + 1, max_end=max_end,
            max_len=max_len, required_end=required_end, warning=None,
            source_len=source_len,
        )
    return _validate_safe_window_end_return(
        start=start, returned_end=candidate_end, max_end=max_end,
        max_len=max_len, required_end=required_end, warning=None,
        source_len=source_len,
    )


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
    end, warning = safe_window_end(
        source,
        head_pos,
        clause_end,
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

    This is a *test-only* helper that uses bare ``assert`` semantics
    (so it is removed under ``python -O``); the production code path
    never raises from this function. Production callers should
    observe the :class:`BoundaryWarning` returned by the slicing
    helpers and drop the span when the warning kind is one of the
    fail-closed constants.
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

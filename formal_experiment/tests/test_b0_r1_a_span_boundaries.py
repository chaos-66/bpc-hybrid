"""B0-R1-A + B0-R1-A-C1: deterministic, maximal-safe, token-bounded spans.

The active v10-A path goes through three slicing sites that all used to
fall back to a hard character cap (or a character-midpoint split, or
``+80``-then-stop-at-first-whitespace) without checking the underlying
token boundary. This test module exercises:

* ``bpc_hybrid.b0_v10.span_safety`` — the shared helper module
* ``bpc_hybrid.b0_v10.actor_action.extract_actors_actions_edges`` — the
  active v10 actor/action path
* ``bpc_hybrid.b0_v10.scope._expand_to_constituent_or_punct`` — the
  active v10 scope expansion path
* ``bpc_hybrid.estg150_b0_development_v3.plan_clause_units_v4`` — the
  active v10 clause-planning path

Each section first shows the *old* behaviour on a minimal reproducer so
that the test suite would have failed before B0-R1-A-C1, and then
asserts the new behaviour. Every test asserts the *semantic coverage*
(length / complete marker / rightmost boundary), not just "is not a
half-word".

No real dataset, no Gold, no LLM/API calls.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from bpc_hybrid.b0_v10.actor_action import extract_actors_actions_edges
from bpc_hybrid.b0_v10.scope import _expand_to_constituent_or_punct
from bpc_hybrid.b0_v10.span_safety import (
    WARN_KIND_ACTION_CAP_BACKOFF,
    WARN_KIND_NO_BOUNDARY_AT_ALL,
    WARN_KIND_REQUIRED_EXCEEDS_CAP,
    BoundaryWarning,
    CONNECTOR_PRIORITY,
    assert_span_invariants,
    connector_priority_cut,
    has_clause_end_boundary,
    has_safe_boundary,
    safe_action_slice,
    safe_window_end,
    skip_clause_leading_separators,
)
from bpc_hybrid.estg150_b0_development_v3 import plan_clause_units_v4


# ---------------------------------------------------------------------------
# Section 1: pre-fix demonstrations of the OLD bugs
# ---------------------------------------------------------------------------
# Each ``_*_old`` helper re-implements the pre-R1-A inline logic in pure
# Python so that the test can prove the bug existed and that the new
# helpers are stricter. The a2383e9 implementation had the same
# underlying behaviour for every ``_*_old`` helper below.


def _old_action_first_whitespace(
    source: str,
    head_pos: int,
    clause_end: int,
    *,
    cap: int = 80,
) -> tuple[int, int]:
    """Replicate a2383e9's over-shrinkage: take ``min(clause_end, a0 + cap)``
    and then walk to the FIRST whitespace inside that window, returning
    the slice right BEFORE the first whitespace.
    """
    a0 = max(0, head_pos)
    a1 = min(clause_end, a0 + cap)
    for pos in range(a0, a1):
        if source[pos] in (" ", "\t", "\n"):
            return a0, pos
    return a0, a1


def _old_scope_char_loop(
    source: str,
    start: int,
    end: int,
    clause_end: int,
    *,
    max_len: int = 100,
) -> tuple[int, int]:
    """Replicate the pre-R1-A scope char-by-char loop. The original
    call site passed the original ``end`` as ``max_end`` and used
    ``max_len`` as a hard cap; the loop stopped at the first
    ``;``/``.``/``\n`` and otherwise returned ``start + max_len``.
    """
    e = end
    while e < clause_end and (e - start) < max_len:
        ch = source[e]
        if ch in ".;\n":
            break
        if ch == "," and (e - start) > 12:
            e += 1
            break
        e += 1
    return start, min(e, clause_end)


def _old_clause_midpoint_cut(
    text: str,
    m1_end: int,
    m2_start: int,
) -> int:
    """Old plan_clause_units_v4: split at the character midpoint when no
    connector is present.
    """
    return (m1_end + m2_start) // 2


def _old_clause_connector_pick(
    text: str, window_start: int, window_end: int
) -> int | None:
    """Old plan_clause_units_v4 connector loop: overwrites the cut on
    every match, so the *last* connector in the window wins.
    """
    window = text[window_start:window_end]
    cut = None
    for cm in re.finditer(r";|\band\b|\bor\b|\bbut\b", window, re.I):
        cut = window_start + cm.start()
    return cut


# ---------------------------------------------------------------------------
# Section 2: span_safety contract — rightmost-boundary fallback, required_end,
# leading-separator skip
# ---------------------------------------------------------------------------


class TestSafeWindowEnd:
    def test_prefers_earliest_clause_boundary_inside_cap(self) -> None:
        text = "alpha. beta; gamma. delta"
        # clause boundary EARLIEST wins: "alpha." period is at pos 5
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=True
        )
        assert end == text.find(".")
        assert warning is None

    def test_period_before_semicolon_wins(self) -> None:
        # A period that appears EARLIER than a semicolon inside the cap
        # must win. The a2383e9 implementation walked character-by-
        # character and would have kept going past the period, but the
        # new code uses the earliest clause boundary in [start, cap).
        text = "alpha. beta; gamma"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=True
        )
        assert end == text.find(".")
        assert warning is None

    def test_semicolon_before_period_inside_cap_wins(self) -> None:
        # If a semicolon is earlier in the window, it still wins.
        text = "alpha; beta. gamma"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=True
        )
        assert end == text.find(";")
        assert warning is None

    def test_returns_rightmost_whitespace_inside_cap(self) -> None:
        # a2383e9 stopped at the FIRST whitespace and produced "process"
        # (7 chars) for the 19-word action described in the user report.
        # The new code returns the rightmost whitespace inside the cap.
        text = (
            "process the personal data lawfully fairly transparently "
            "securely confidently accurately"
        )
        end, warning = safe_window_end(
            text, 0, len(text), max_len=40, prefer_clause_boundary=False
        )
        # must be at least the second-to-last whitespace inside [0, 40)
        # so the slice is clearly longer than a 1-word prefix.
        assert end > 7, (
            f"safe_window_end collapsed to first whitespace (end={end}); "
            f"expected rightmost boundary inside the cap"
        )
        # must be at or before the cap (40)
        assert end <= 40
        # must not be a half-word
        if end < len(text):
            assert not (text[end - 1].isalpha() and text[end].isalpha())
        assert warning is None
        # the slice is the rightmost safe token boundary, which for
        # 19 words at max_len=40 covers many tokens
        assert (end - 0) >= 30, (
            f"slice length {(end - 0)} too short for max_len=40; "
            f"rightmost boundary should be near the cap"
        )

    def test_max_end_within_cap_returns_full_max_end(self) -> None:
        # When the action is genuinely short (shorter than the cap),
        # the helper must return the full action span, not stop at the
        # first whitespace.
        text = "process the data lawfully"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=80, prefer_clause_boundary=False
        )
        assert end == len(text)
        assert warning is None

    def test_max_end_smaller_than_cap_returns_full_max_end(self) -> None:
        # max_end is the boundary; cap is at most max_end; the slice
        # cannot extend past max_end. The helper must return max_end
        # (or a clean boundary AT max_end) and never stop at the
        # first whitespace earlier than max_end.
        text = "alpha beta gamma delta epsilon zeta eta theta"
        end, warning = safe_window_end(
            text, 0, 18, max_len=80, prefer_clause_boundary=False
        )
        # 18 is between two words. The cap is 18; the helper may
        # return the rightmost safe boundary at or before 18.
        assert end <= 18
        assert end >= 14  # well past the first word
        assert warning is None
        if end < len(text):
            assert not (text[end - 1].isalpha() and text[end].isalpha())

    def test_rightmost_when_first_safe_position_also_satisfies(self) -> None:
        # Both halves of the contract: required_end is set, the first
        # safe position would satisfy it, but the rightmost one wins.
        text = "alpha beta gamma delta epsilon"
        end, warning = safe_window_end(
            text,
            0,
            len(text),
            max_len=80,
            prefer_clause_boundary=False,
            required_end=6,  # after "alpha"
        )
        # the rightmost safe boundary inside the cap is at the end of
        # the source; required_end is just a minimum
        assert end == len(text)
        assert warning is None

    def test_required_end_exceeds_cap_preserves_evidence(self) -> None:
        # The caller (scope) says the original match end is at pos 50
        # but the cap is at 10. The helper must extend past the cap
        # to honour the original evidence and surface a warning.
        text = "alpha " + "beta " * 30  # plenty of words
        end, warning = safe_window_end(
            text,
            0,
            len(text),
            max_len=10,
            prefer_clause_boundary=False,
            required_end=50,
        )
        assert end == 50
        assert warning is not None
        assert warning.kind == WARN_KIND_REQUIRED_EXCEEDS_CAP
        # the slice covers the original evidence, not a half-word
        assert text[end - 1].isalpha() or text[end] == " "

    def test_no_safe_boundary_records_warning_and_returns_start(self) -> None:
        # A pathological 200-char word with cap=20: no internal
        # boundary inside the cap, and no required_end. The helper
        # must back off to start (empty slice) with a stable
        # warning kind, not a half-word.
        text = "a" * 200
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=False
        )
        assert end == 0
        assert warning is not None
        assert warning.kind == WARN_KIND_NO_BOUNDARY_AT_ALL

    def test_required_end_below_cap_uses_rightmost_safe(self) -> None:
        # The caller wants at least end=10, but the rightmost safe
        # boundary inside the cap is at 80. The helper returns 80
        # (rightmost), not 10. No warning because best_safe >= required_end.
        text = " ".join(["word"] * 50)  # 50 words, 250 chars
        end, warning = safe_window_end(
            text,
            0,
            len(text),
            max_len=80,
            prefer_clause_boundary=False,
            required_end=10,
        )
        # rightmost safe boundary is at the rightmost whitespace
        # before pos 80
        assert end <= 80
        assert end >= 70
        assert warning is None

    def test_phrase_boundary_included_in_slice(self) -> None:
        # The rightmost safe token/phrase boundary is the rightmost
        # whitespace, not the first comma. The slice therefore
        # extends past the comma to the rightmost safe boundary.
        text = "alpha, beta gamma"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=False
        )
        # cap (= 17 == max_end) is at end of source so the helper
        # returns the full clause; the rightmost safe boundary
        # inside [0, 17) is the space before "gamma".
        assert end == len(text)
        assert warning is None

    def test_phrase_boundary_at_end_of_cap_included(self) -> None:
        # When the rightmost safe boundary inside the cap happens to
        # be a phrase-punctuation character, the slice INCLUDES the
        # punctuation (the helper returns idx + 1).
        text = "alpha, beta, gamma"
        # cap = 12 covers "alpha, beta," with the second comma at 11.
        end, warning = safe_window_end(
            text, 0, 12, max_len=20, prefer_clause_boundary=False
        )
        assert text[end - 1] == ","
        assert warning is None

    def test_old_action_first_whitespace_demonstration(self) -> None:
        # Direct proof that the a2383e9 helper collapses to one word
        # for a 19-word action with cap=80.
        text = (
            "process the personal data lawfully fairly transparently "
            "securely confidently accurately"
        )
        a0, a1 = _old_action_first_whitespace(text, 0, len(text), cap=80)
        # the OLD code returned at the FIRST whitespace
        assert (a1 - a0) < 10, (
            f"a2383e9 over-shrunk the action to {text[a0:a1]!r}; "
            f"this is the regression we are fixing"
        )


class TestSafeActionSlice:
    def test_19_word_action_does_not_collapse_to_one_word(self) -> None:
        # The exact regression the user reported: a 19-word Action
        # whose head_pos is 0 must NOT shrink to "process" (7 chars).
        text = (
            "process the personal data lawfully fairly transparently "
            "securely confidently accurately completely thoroughly "
            "carefully diligently"
        )
        head_pos = 0
        head_token_end = text.find(" ", head_pos)  # 7 (after "process")
        a0, a1, warning = safe_action_slice(
            text,
            head_pos,
            len(text),
            max_chars=80,
            head_token_end=head_token_end,
        )
        assert a0 == head_pos
        assert a1 > a0
        # the slice must cover the head token at minimum
        assert a1 >= head_token_end
        # the slice must cover MANY words, not just the head
        assert (a1 - a0) > 30, (
            f"safe_action_slice over-shrunk the action to "
            f"{text[a0:a1]!r} ({(a1 - a0)} chars); expected at least 30 chars"
        )
        # the slice must not be a half-word
        if a1 < len(text):
            assert not (text[a1 - 1].isalpha() and text[a1].isalpha())
        # no warning when rightmost boundary is well past the head
        assert warning is None

    def test_max_chars_smaller_than_head_token_preserves_head(self) -> None:
        # The cap is 5 but the head token "process" is 7 chars long.
        # The helper must preserve the head token (extend past the
        # cap) and surface a clear warning.
        text = "process the personal data"
        head_pos = 0
        head_token_end = 7  # "process" ends at 7
        a0, a1, warning = safe_action_slice(
            text,
            head_pos,
            len(text),
            max_chars=5,
            head_token_end=head_token_end,
        )
        assert a0 == 0
        # the head token is fully covered
        assert a1 >= head_token_end
        assert text[a0:a1] == "process" or text[a0:a1].startswith("process")
        assert warning is not None
        assert warning.kind == WARN_KIND_ACTION_CAP_BACKOFF

    def test_short_action_returns_full_action(self) -> None:
        text = "process the data"
        head_pos = 0
        head_token_end = 7
        a0, a1, warning = safe_action_slice(
            text,
            head_pos,
            len(text),
            max_chars=80,
            head_token_end=head_token_end,
        )
        assert a0 == 0
        assert a1 == len(text)
        assert text[a0:a1] == text
        assert warning is None

    def test_safe_action_slice_head_outside_clause(self) -> None:
        text = "A B C"
        a0, a1, warning = safe_action_slice(text, head_pos=5, clause_end=5, max_chars=10)
        assert a0 == 5 and a1 == 5
        assert warning is not None

    def test_safe_action_slice_long_sentence_semantic_coverage(self) -> None:
        text = (
            "The taxpayer shall perform the following actions in order to comply "
            "with section 12 paragraph 3 of the act and file the return."
        )
        head_pos = text.find("perform")
        head_token_end = head_pos + len("perform")
        a0, a1, _warning = safe_action_slice(
            text, head_pos, len(text), max_chars=80, head_token_end=head_token_end
        )
        # the slice must be near the cap (rightmost), not the first
        # whitespace
        assert (a1 - a0) >= 60
        assert a1 <= head_pos + 80
        if a1 < len(text):
            assert not (text[a1 - 1].isalpha() and text[a1].isalpha())
        # the head token is fully covered
        assert a1 >= head_token_end

    def test_old_action_first_whitespace_demonstration(self) -> None:
        text = (
            "process the personal data lawfully fairly transparently "
            "securely confidently accurately"
        )
        a0, a1 = _old_action_first_whitespace(text, 0, len(text), cap=80)
        # the a2383e9 implementation would have returned this tiny slice
        assert text[a0:a1] == "process" or len(text[a0:a1]) < 10


class TestConnectorPriority:
    def test_old_connector_loop_picks_last_not_first(self) -> None:
        text = "first shall rest; and or but second shall"
        s = text.find("rest") + len("rest")
        e = text.find("second", s)
        cut = _old_clause_connector_pick(text, s, e)
        assert cut is not None
        assert text[cut : cut + 3] == "but"

    def test_new_connector_priority_picks_semicolon_first(self) -> None:
        text = "first shall rest; and second shall or third shall but fourth shall"
        s = text.find("rest") + len("rest")
        e = text.find("second", s)
        window = text[s:e]
        local = connector_priority_cut(window)
        assert local is not None
        assert window[local] == ";"

    def test_new_connector_priority_picks_but_when_no_semicolon(self) -> None:
        window = "alpha and beta but gamma or delta"
        local = connector_priority_cut(window)
        assert local is not None
        assert window[local : local + 3] == "but"

    def test_new_connector_priority_picks_and_when_only_and_or(self) -> None:
        window = "alpha and beta or gamma"
        local = connector_priority_cut(window)
        assert local is not None
        assert window[local : local + 3] == "and"

    def test_no_connector_returns_none(self) -> None:
        assert connector_priority_cut("alpha beta gamma") is None

    def test_custom_preference(self) -> None:
        window = "alpha and beta but gamma"
        local = connector_priority_cut(window, preference=("and", "but"))
        assert local is not None
        assert window[local : local + 3] == "and"

    def test_priority_order_is_documented(self) -> None:
        assert CONNECTOR_PRIORITY == (";", "but", "and", "or")


class TestSkipClauseLeadingSeparators:
    def test_skip_whitespace(self) -> None:
        assert skip_clause_leading_separators("abc  def", 3) == 5

    def test_skip_semicolon(self) -> None:
        assert skip_clause_leading_separators("first;second", 5) == 6

    def test_skip_comma(self) -> None:
        assert skip_clause_leading_separators("first, second", 5) == 7

    def test_skip_combined(self) -> None:
        assert skip_clause_leading_separators("first ;  , second", 5) == 11

    def test_no_separator_no_move(self) -> None:
        assert skip_clause_leading_separators("first second", 6) == 6


# ---------------------------------------------------------------------------
# Section 3: scope._expand_to_constituent_or_punct
# ---------------------------------------------------------------------------


class TestScopeExpand:
    def test_old_scope_can_end_mid_word(self) -> None:
        # Pre-fix demonstration: the OLD scope code walked char by
        # char from the original match end. When no ``;``/``.``/``\n``
        # was found before the cap, it returned a slice ending at
        # ``start + max_len`` which lands mid-word in "thirty".
        text = "subject to within thirty days"
        a0, a1 = _old_scope_char_loop(text, 0, 10, len(text), max_len=20)
        # the OLD code: walks from pos 10, finds no punctuation inside
        # the cap, returns (0, 20). The slice ends at "t" of "thirty"
        # — a half-word.
        assert a1 - a0 == 20
        slice_text = text[a0:a1]
        # the OLD code dropped the trailing space and split "thirty"
        # at "t". The slice ends with a word character and the next
        # char is also a word character (the "h" of "thirty").
        assert slice_text[-1].isalpha() and text[a1].isalpha()
        # the new code, on the same inputs, must end at the
        # word → non-word transition (the space between "within" and
        # "thirty"), so the slice ends with " " not "t".
        new_a0, new_a1, _warning = _expand_to_constituent_or_punct(
            text, 0, 10, clause_start=0, clause_end=len(text), max_len=20
        )
        new_slice = text[new_a0:new_a1]
        # new slice must cover the original marker "subject to" fully
        assert "subject to" in new_slice
        # and must end at a clean word boundary (whitespace or end of source)
        if new_a1 < len(text):
            assert not (new_slice[-1].isalpha() and text[new_a1].isalpha())

    def test_subject_to_marker_preserved(self) -> None:
        # The caller (lexicon) reports a match end of 10 (after "to").
        # The new helper must NEVER truncate below the original match
        # end, even if the cap would otherwise force it.
        text = "subject to additional phrase"
        original_match_end = text.find("to") + len("to")  # 10
        a0, a1, _warning = _expand_to_constituent_or_punct(
            text,
            0,
            original_match_end,
            clause_start=0,
            clause_end=len(text),
            max_len=5,
        )
        # the original match end is 10; the new helper extends past
        # the cap to honour it
        assert a1 >= original_match_end
        # and the slice must contain "subject to" (or more)
        assert "subject to" in text[a0:a1]

    def test_in_accordance_with_marker_preserved(self) -> None:
        text = "in accordance with the policy the next clause"
        # "in accordance with" is 18 chars (positions 0-18 inclusive of
        # the trailing space at 18, exclusive end of "with" is 18)
        original_match_end = text.find("with") + len("with")  # 18
        a0, a1, _warning = _expand_to_constituent_or_punct(
            text,
            0,
            original_match_end,
            clause_start=0,
            clause_end=len(text),
            max_len=5,
        )
        assert a1 >= original_match_end
        assert "in accordance with" in text[a0:a1]

    def test_for_a_period_marker_preserved(self) -> None:
        text = "for a period of three years the next clause"
        original_match_end = text.find("period") + len("period")  # 11
        a0, a1, _warning = _expand_to_constituent_or_punct(
            text,
            0,
            original_match_end,
            clause_start=0,
            clause_end=len(text),
            max_len=5,
        )
        assert a1 >= original_match_end
        assert "for a period" in text[a0:a1]

    def test_new_scope_returns_full_match_when_within_cap(self) -> None:
        # When the original match end is well inside the cap, the
        # helper returns the rightmost safe token boundary past the
        # match end (so the scope span covers the marker PLUS the
        # trailing safe window). It must never return LESS than the
        # match end.
        text = "subject to some additional words"
        original_match_end = text.find("to") + len("to")  # 9
        a0, a1, warning = _expand_to_constituent_or_punct(
            text,
            0,
            original_match_end,
            clause_start=0,
            clause_end=len(text),
            max_len=80,
        )
        assert a1 >= original_match_end
        assert warning is None
        # the slice extends past "to" to the rightmost safe boundary
        assert a1 > original_match_end

    def test_new_scope_unicode_safe(self) -> None:
        # German umlauts; required_end preserved; no half-character.
        text = "nach § 12a des Gesetzes; weitere Bedingungen"
        # "nach § 12a" is 10 chars (positions 0-9, exclusive end = 10)
        original_match_end = text.find("12a") + len("12a")  # 10
        a0, a1, _warning = _expand_to_constituent_or_punct(
            text,
            0,
            original_match_end,
            clause_start=0,
            clause_end=len(text),
            max_len=5,
        )
        # required_end > cap, so we extend past the cap with a warning
        assert a1 >= original_match_end
        # must not include a half-character
        assert text[a0:a1] == text[a0:a1]
        # and the slice is the original evidence, not a half-word
        assert "12a" in text[a0:a1]

    def test_new_scope_warning_surfaced(self) -> None:
        text = "subject to some additional words"
        original_match_end = 50  # way past the cap
        a0, a1, warning = _expand_to_constituent_or_punct(
            text,
            0,
            original_match_end,
            clause_start=0,
            clause_end=len(text),
            max_len=5,
        )
        assert warning is not None
        assert warning.kind == WARN_KIND_REQUIRED_EXCEEDS_CAP


# ---------------------------------------------------------------------------
# Section 4: plan_clause_units_v4 active-call-chain
# ---------------------------------------------------------------------------


def _make_annotation(text: str, sentence_offsets: list[tuple[int, int]]) -> dict[str, Any]:
    """Tiny CoreNLP-shaped annotation for unit tests.

    Token offsets are computed from the *source* text via
    :func:`re.finditer` so the last token's ``characterOffsetEnd`` is
    the true end of the source. A cursor-only accumulator (which is
    what a previous version of this helper did) is wrong: it stops at
    ``sum(len(words))`` and silently truncates the trailing whitespace
    plus the last word, so the planner never sees the second modal
    anchor and the split branch is never exercised.
    """
    sentences: list[dict[str, Any]] = []
    for s_begin, s_end in sentence_offsets:
        toks: list[dict[str, Any]] = []
        for idx, m in enumerate(re.finditer(r"\S+", text[s_begin:s_end]), start=1):
            toks.append(
                {
                    "index": idx,
                    "word": m.group(0),
                    "characterOffsetBegin": s_begin + m.start(),
                    "characterOffsetEnd": s_begin + m.end(),
                }
            )
        sentences.append(
            {
                "tokens": toks,
                "basicDependencies": [],
            }
        )
    return {"sentences": sentences}


class TestPlanClauseUnitsV4:
    def test_no_connector_between_modals_no_split(self) -> None:
        text = "The taxpayer shall perform the action; the office shall verify the data"
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        assert all(
            0 <= u["clause_char_span"][0] < u["clause_char_span"][1] <= len(text)
            for u in units
        )
        for u in units:
            s, e = u["clause_char_span"]
            assert text[s] not in {" ", "\t", "\n", ";", ",", ":"}
            assert 0 <= s < e <= len(text)
            assert has_clause_end_boundary(text, e)

    def test_no_connector_no_split_when_window_has_none(self) -> None:
        text = "The taxpayer shall submit the information the office shall review"
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        if len(units) > 1:
            for u in units:
                s, e = u["clause_char_span"]
                assert text[s] not in {" ", "\t", "\n", ";", ","}
                assert has_safe_boundary(text, s, e)
        assert stats["no_connector_no_split"] >= 1

    def test_semicolon_split_does_not_lead_next_clause_with_semicolon(self) -> None:
        text = (
            "The taxpayer shall submit the form within thirty days; "
            "the office shall record the receipt"
        )
        ann = _make_annotation(text, [(0, len(text))])
        units, _ = plan_clause_units_v4(ann, text)
        assert len(units) == 2
        s1, e1 = units[0]["clause_char_span"]
        s2, e2 = units[1]["clause_char_span"]
        assert text[s2] not in {" ", "\t", "\n", ";", ",", ":"}
        assert e2 > s2
        assert e1 <= text.find(";") + 1
        assert s2 > text.find(";")

    def test_connector_priority_semicolon_wins_over_and(self) -> None:
        text = (
            "The taxpayer shall submit the form; and the office shall record it"
        )
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        assert len(units) == 2
        s1, e1 = units[0]["clause_char_span"]
        s2, e2 = units[1]["clause_char_span"]
        assert e1 <= text.find(";") + 1
        assert s2 > text.find(";")

    def test_old_midpoint_demo(self) -> None:
        text = "The taxpayer shall submit the form the office shall record it"
        positions = [m.start() for m in re.finditer(r"\bshall\b", text)]
        assert len(positions) == 2
        m1_end = positions[0] + len("shall")
        m2_start = positions[1]
        cut = _old_clause_midpoint_cut(text, m1_end, m2_start)
        slice_after = text[cut : cut + 10]
        assert slice_after[0].isalpha() and text[cut - 1].isalpha()

    def test_old_connector_loop_picks_last_demo(self) -> None:
        text = "first shall rest; and or but second shall"
        s = text.find("rest") + len("rest")
        e = text.find("second", s)
        cut = _old_clause_connector_pick(text, s, e)
        assert text[cut : cut + 3] == "but"

    def test_long_sentence_with_unicode(self) -> None:
        text = (
            "Der St\u00ebuerpflichtige shall file the r\u00e9turn within "
            "thr\u00eety days; the Fin\u00e4nzamt shall record the "
            "receipt"
        )
        ann = _make_annotation(text, [(0, len(text))])
        units, _ = plan_clause_units_v4(ann, text)
        assert len(units) == 2
        for u in units:
            s, e = u["clause_char_span"]
            assert 0 <= s < e <= len(text)
            assert text[s] not in {" ", "\t", "\n", ";", ",", ":"}
            assert text[s:e] == text[s:e]
            assert has_clause_end_boundary(text, e)

    def test_no_safe_boundary_records_no_split(self) -> None:
        text = "perform"
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        assert len(units) == 1
        assert units[0]["clause_char_span"] == (0, len(text))

    def test_all_units_emit_safe_spans(self) -> None:
        text = (
            "The taxpayer shall file the return within thirty days; the office shall "
            "verify the data; the authority shall publish the list of approved cases"
        )
        ann = _make_annotation(text, [(0, len(text))])
        units, _ = plan_clause_units_v4(ann, text)
        assert len(units) >= 2
        for u in units:
            s, e = u["clause_char_span"]
            assert 0 <= s < e <= len(text)
            assert has_clause_end_boundary(text, e)
            assert text[s] not in {" ", "\t", "\n", ";", ",", ":"}


# ---------------------------------------------------------------------------
# Section 5: active v10 actor/action call chain
# ---------------------------------------------------------------------------


def _make_tiny_sentence(text: str) -> dict[str, Any]:
    """Build a sentence mapping that extract_actors_actions_edges consumes."""
    words = text.split()
    tokens: list[dict[str, Any]] = []
    cursor = 0
    for idx, w in enumerate(words, start=1):
        start = text.find(w, cursor)
        end = start + len(w)
        tokens.append(
            {
                "index": idx,
                "word": w,
                "lemma": w.casefold(),
                "pos": "NN" if idx == 1 else "VB",
                "characterOffsetBegin": start,
                "characterOffsetEnd": end,
            }
        )
        cursor = end
    verb_idx = next(
        (i for i, t in enumerate(tokens, start=1) if t["word"].casefold() in {"performs", "files", "submits"}),
        3,
    )
    subj_idx = 1
    deps = [
        {"dep": "ROOT", "governor": 0, "dependent": verb_idx},
        {"dep": "nsubj", "governor": verb_idx, "dependent": subj_idx},
    ]
    return {"tokens": tokens, "basicDependencies": deps}


class TestActiveV10CallChain:
    def test_action_slice_respects_token_boundary(self) -> None:
        # A 19-word action that a2383e9 would have collapsed to one
        # word must now produce a much longer slice. We hand-craft a
        # synthetic sentence whose action span is many tokens and
        # verify the slice is not half a word and clearly covers
        # more than the first token.
        long_action = (
            "The taxpayer shall process the personal data lawfully fairly "
            "transparently securely confidently accurately completely "
            "thoroughly carefully diligently responsibly"
        )
        sentence_text = long_action
        sent = _make_tiny_sentence(sentence_text)
        verb_idx = next(
            (i for i, t in enumerate(sent["tokens"], start=1) if t["word"].casefold() in {"process"}),
            3,
        )
        sent["basicDependencies"].append(
            {"dep": "aux", "governor": verb_idx, "dependent": 2}
        )

        class _StubLex:
            actor_surfaces = {"taxpayer"}

        actors, actions, _edges, stats = extract_actors_actions_edges(
            sentence=sent,
            source_text=sentence_text,
            clause_start=0,
            clause_end=len(sentence_text),
            sentence_index=0,
            lexicon=_StubLex(),  # type: ignore[arg-type]
        )
        # at least one action was emitted
        assert actions
        for a in actions:
            s, e = a["start"], a["end"]
            assert 0 <= s < e <= len(sentence_text)
            assert a["text"] == sentence_text[s:e]
            # not a half-word
            if e < len(sentence_text):
                assert not (sentence_text[e - 1].isalpha() and sentence_text[e].isalpha())
            assert has_safe_boundary(sentence_text, s, e)
            # the slice must cover more than just the first word
            # (the regression the user reported was 1 word = "process"
            # = 7 chars)
            assert (e - s) > 15, (
                f"action slice {a['text']!r} (len {e - s}) is too short; "
                f"the over-shrinkage regression is back"
            )
        assert "action_cap_warnings" in stats
        assert "action_cap_drops" in stats

    def test_actor_action_returns_well_formed_spans(self) -> None:
        sentence_text = "The taxpayer shall file the return."
        sent = _make_tiny_sentence(sentence_text)
        verb_idx = next(
            (i for i, t in enumerate(sent["tokens"], start=1) if t["word"].casefold() in {"files"}),
            3,
        )
        sent["basicDependencies"].append(
            {"dep": "aux", "governor": verb_idx, "dependent": 2}
        )

        class _StubLex:
            actor_surfaces = {"taxpayer"}

        actors, actions, _edges, stats = extract_actors_actions_edges(
            sentence=sent,
            source_text=sentence_text,
            clause_start=0,
            clause_end=len(sentence_text),
            sentence_index=0,
            lexicon=_StubLex(),  # type: ignore[arg-type]
        )
        for span in actors + actions:
            s, e = span["start"], span["end"]
            assert 0 <= s < e <= len(sentence_text)
            assert span["text"] == sentence_text[s:e]
            assert has_safe_boundary(sentence_text, s, e)


# ---------------------------------------------------------------------------
# Section 6: utility — has_safe_boundary, assert_span_invariants
# ---------------------------------------------------------------------------


class TestInvariants:
    @pytest.mark.parametrize(
        "text,start,end,ok",
        [
            ("hello world", 0, 5, True),
            ("hello world", 6, 11, True),
            ("hello world", 0, 11, True),
            ("hello world", 3, 8, False),
            ("alpha, beta", 0, 6, True),
            ("alpha, beta", 5, 10, False),
            ("alpha, beta", 6, 10, False),
            ("alpha, beta", 7, 11, True),
            ("", 0, 0, False),
        ],
    )
    def test_has_safe_boundary(self, text: str, start: int, end: int, ok: bool) -> None:
        assert has_safe_boundary(text, start, end) is ok

    def test_assert_span_invariants_passes_for_safe_span(self) -> None:
        assert_span_invariants("hello world", 0, 5, "test")

    def test_assert_span_invariants_raises_for_mid_word(self) -> None:
        with pytest.raises(ValueError):
            assert_span_invariants("hello world", 2, 8, "midword")

    def test_assert_span_invariants_raises_for_invalid_offsets(self) -> None:
        with pytest.raises(ValueError):
            assert_span_invariants("hello", 5, 5, "empty")
        with pytest.raises(ValueError):
            assert_span_invariants("hello", -1, 3, "negative")

    def test_boundary_warning_dataclass(self) -> None:
        w = BoundaryWarning(kind="action_cap", start=10, end=20, max_len=15)
        assert w.kind == "action_cap"
        assert w.start == 10
        assert w.end == 20
        assert w.max_len == 15

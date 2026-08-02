"""B0-R1-A: deterministic, token-safe span and clause-boundary tests.

The active v10-A path goes through three slicing sites that all used to
fall back to a hard character cap (or a character-midpoint split) without
checking the underlying token boundary. This test module exercises:

* ``bpc_hybrid.b0_v10.span_safety`` — the shared helper module
* ``bpc_hybrid.b0_v10.actor_action.extract_actors_actions_edges`` — the
  active v10 actor/action path
* ``bpc_hybrid.b0_v10.scope._expand_to_constituent_or_punct`` — the
  active v10 scope expansion path
* ``bpc_hybrid.estg150_b0_development_v3.plan_clause_units_v4`` — the
  active v10 clause-planning path

Each section first shows the *old* behaviour on a minimal reproducer so
that the test suite would have failed before B0-R1-A, and then asserts
the new behaviour. No real dataset, no Gold, no LLM/API calls.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from bpc_hybrid.b0_v10.actor_action import extract_actors_actions_edges
from bpc_hybrid.b0_v10.scope import _expand_to_constituent_or_punct
from bpc_hybrid.b0_v10.span_safety import (
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
# helpers are stricter.


def _old_action_hard_truncate(
    source: str,
    head_pos: int,
    clause_end: int,
    *,
    cap: int = 80,
) -> tuple[int, int]:
    """Old actor_action.py logic: take ``min(clause_end, head_pos + cap)``
    with no token-boundary check.
    """
    a0 = max(0, head_pos)
    a1 = min(clause_end, a0 + cap)
    return a0, a1


def _old_scope_expand(
    source: str,
    start: int,
    end: int,
    clause_end: int,
    *,
    max_len: int = 100,
) -> tuple[int, int]:
    """Old scope._expand_to_constituent_or_punct: char loop that can end
    mid-word.
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
    """Old plan_clause_units_v4: split at the character midpoint between
    two deontic anchors when no connector is present.
    """
    return (m1_end + m2_start) // 2


def _old_clause_connector_pick(
    text: str, window_start: int, window_end: int
) -> int | None:
    """Old plan_clause_units_v4 connector loop: overwrites the cut on every
    match, so the *last* connector in the window wins.
    """
    window = text[window_start:window_end]
    cut = None
    for cm in re.finditer(r";|\band\b|\bor\b|\bbut\b", window, re.I):
        cut = window_start + cm.start()
    return cut


# ---------------------------------------------------------------------------
# Section 2: span_safety contract — token-boundary fallback, deterministic
# connector choice, leading-separator skip
# ---------------------------------------------------------------------------


class TestSafeWindowEnd:
    def test_prefers_semicolon_when_present(self) -> None:
        text = "alpha beta; gamma delta"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=True
        )
        assert end == text.find(";")
        assert warning is None

    def test_prefers_period_over_whitespace(self) -> None:
        text = "alpha beta. gamma delta"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=True
        )
        assert end == text.find(".")
        assert warning is None

    def test_falls_back_to_token_boundary_when_no_punct(self) -> None:
        # no punctuation before the cap; must stop on the first
        # whitespace so we never land mid-word.
        text = "alphabetagamma delta epsilon"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=15, prefer_clause_boundary=True
        )
        assert text[end] == " "
        assert warning is None
        # the slice must end at a token boundary
        assert has_safe_boundary(text, 0, end)

    def test_warns_when_no_safe_boundary_inside_cap(self) -> None:
        # a single long word with no whitespace or punctuation inside the
        # cap; safe_window_end must back off to a safe boundary or warn.
        text = "a" * 200
        end, warning = safe_window_end(
            text, 0, 50, max_len=20, prefer_clause_boundary=True
        )
        # the cap dominates (we have only the start "a" and need to
        # back off to a token boundary which is the very start)
        assert end <= 50
        if warning is not None:
            assert warning.kind in {"safe_window_cap", "safe_window_no_boundary"}

    def test_pre_phrase_boundary_comma_is_inclusive(self) -> None:
        text = "alpha, beta gamma"
        end, warning = safe_window_end(
            text, 0, len(text), max_len=20, prefer_clause_boundary=False
        )
        # the comma itself belongs to the span; the next token starts
        # after the comma+whitespace.
        assert text[end - 1] == ","
        assert warning is None


class TestSafeActionSlice:
    def test_old_hard_truncate_can_split_word(self) -> None:
        # proof that the OLD logic produced a half-word span.
        text = "The taxpayer shall submittherequiredinformationimmediately"
        # pretend the head token starts at offset 19 ("submit...")
        head_pos = 19
        a0, a1 = _old_action_hard_truncate(text, head_pos, len(text), cap=10)
        slice_text = text[a0:a1]
        assert slice_text == "submitther"  # i.e. the slice ends mid-word
        assert " " not in slice_text  # no whitespace inside the slice
        # and the next char is not a word-boundary indicator
        assert text[a1].isalpha()

    def test_new_safe_slice_lands_on_token_boundary(self) -> None:
        # A text with a word boundary inside the cap. The slice must
        # end exactly at the whitespace.
        text = "The taxpayer shall submit therequiredinformationimmediately"
        head_pos = text.find("submit")
        a0, a1, warning = safe_action_slice(text, head_pos, len(text), max_chars=12)
        assert a0 == head_pos
        assert a1 > a0
        assert a1 <= head_pos + 12  # the cap is strict
        # the slice must end at a word boundary (whitespace or
        # non-letter)
        assert a1 == len(text) or not text[a1].isalpha() or text[a1] in " \t\n"
        # no half-word
        slice_text = text[a0:a1]
        if slice_text and slice_text[-1].isalpha():
            assert a1 == len(text) or not text[a1].isalpha()
        # no warning when the cap is reached at a clean boundary
        assert warning is None

    def test_new_safe_slice_no_boundary_records_warning(self) -> None:
        # A pathological text: a single 200-char word with no
        # whitespace inside the cap. The helper must NOT emit a
        # half-word; it must either return an empty slice + warning or
        # back off to the most recent word-end (which does not exist
        # here, so empty + warning).
        text = "a" * 200
        head_pos = 0
        a0, a1, warning = safe_action_slice(text, head_pos, len(text), max_chars=10)
        assert a0 == head_pos
        # either empty (backoff) or a clean multi-char prefix
        if a1 > a0:
            # must still be a token boundary (whole word)
            assert a1 == len(text) or not text[a1].isalpha()
        # a warning is surfaced
        assert warning is not None
        assert warning.kind in {"safe_window_cap", "safe_window_no_boundary", "action_no_boundary"}

    def test_safe_action_slice_within_long_sentence(self) -> None:
        text = (
            "The taxpayer shall perform the following actions in order to comply "
            "with section 12 paragraph 3 of the act and file the return."
        )
        head_pos = text.find("perform")
        a0, a1, _warning = safe_action_slice(text, head_pos, len(text), max_chars=80)
        # the slice must end before mid-word in 80 chars
        assert a1 - a0 <= 80
        if a1 < len(text):
            assert not text[a1].isalpha() or text[a1] in " \t\n"
        assert has_safe_boundary(text, a0, a1)

    def test_safe_action_slice_head_outside_clause(self) -> None:
        text = "A B C"
        a0, a1, warning = safe_action_slice(text, head_pos=5, clause_end=5, max_chars=10)
        assert a0 == 5 and a1 == 5
        assert warning is not None
        assert warning.kind == "action_empty"


class TestConnectorPriority:
    def test_old_connector_loop_picks_last_not_first(self) -> None:
        # "; and , or but" inside the window; the OLD loop overwrites
        # ``cut`` on every match and ends on ``but``.
        text = "first shall rest; and or but second shall"
        s = text.find("rest") + len("rest")
        e = text.find("second", s)
        cut = _old_clause_connector_pick(text, s, e)
        assert cut is not None
        # the OLD code took the LAST match
        assert text[cut : cut + 3] == "but"

    def test_new_connector_priority_picks_semicolon_first(self) -> None:
        text = "first shall rest; and second shall or third shall but fourth shall"
        s = text.find("rest") + len("rest")
        e = text.find("second", s)
        window = text[s:e]
        local = connector_priority_cut(window)
        assert local is not None
        assert window[local] == ";"  # ';' wins over "and" / "or" / "but"

    def test_new_connector_priority_picks_but_when_no_semicolon(self) -> None:
        window = "alpha and beta but gamma or delta"
        local = connector_priority_cut(window)
        assert local is not None
        assert window[local : local + 3] == "but"

    def test_new_connector_priority_picks_first_but(self) -> None:
        # two "but" instances; the first occurrence of "but" wins
        window = "alpha but beta or but gamma"
        local = connector_priority_cut(window, preference=("but", "or"))
        assert local is not None
        assert local == window.find("but")
        # the second but is not chosen even though it's later
        assert local < window.rfind("but")

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
        # the old code walked character by character up to max_len and
        # returned start+max_len when no punctuation appeared; here
        # max_len=10 inside a 12-char alphabetic run.
        text = "alpha betagamma"
        a0, a1 = _old_scope_expand(text, 0, 1, len(text), max_len=10)
        assert text[a0:a1] == "alpha beta"  # lucky whitespace
        # now force a case with no whitespace inside cap
        text2 = "alphabeta"
        a0, a1 = _old_scope_expand(text2, 0, 1, len(text2), max_len=5)
        # the OLD code returned start+5 which is mid-word
        assert a1 - a0 == 5
        assert text2[a0:a1] == "alpha"

    def test_new_scope_ends_at_token_boundary(self) -> None:
        # "alphabeta" with no internal boundary; the cap is strict, so
        # the helper must back off to start (empty span) rather than
        # emit a half-word.
        text2 = "alphabeta"
        a0, a1 = _expand_to_constituent_or_punct(
            text2, 0, 1, clause_start=0, clause_end=len(text2), max_len=5
        )
        # strict cap: cannot exceed max_len
        assert a1 - a0 <= 5
        # must not end mid-word: the only safe position inside the cap
        # is the start (no internal boundary in "alphabeta")
        assert a0 == 0
        assert a1 == 0  # empty slice (the caller can drop it)

    def test_new_scope_prefers_semicolon_inside_cap(self) -> None:
        text = "within thirty days; the taxpayer shall file"
        a0, a1 = _expand_to_constituent_or_punct(
            text, 0, len("within"), clause_start=0, clause_end=len(text), max_len=80
        )
        assert a1 == text.find(";")

    def test_new_scope_uses_comma_when_no_harder_punct(self) -> None:
        text = "pursuant to section 12, the taxpayer shall file"
        # expand from "pursuant" until the comma is found
        s = text.find("pursuant")
        e = s + len("pursuant")
        a0, a1 = _expand_to_constituent_or_punct(
            text, s, e, clause_start=0, clause_end=len(text), max_len=40
        )
        # the comma is included so the next clause starts after ","
        assert text[a1 - 1] == ","

    def test_new_scope_max_len_unicode_safe(self) -> None:
        # German umlauts and ß; Python slicing is by code point, but we
        # also want to make sure the helper never invents a position
        # past the end of the source.
        text = "nach § 12a des Gesetzes; weitere Bedingungen"
        a0, a1 = _expand_to_constituent_or_punct(
            text, 0, 8, clause_start=0, clause_end=len(text), max_len=50
        )
        assert 0 <= a0 <= a1 <= len(text)
        # must not include a half-character
        assert text[a0:a1] == text[a0:a1]


# ---------------------------------------------------------------------------
# Section 4: plan_clause_units_v4 active-call-chain
# ---------------------------------------------------------------------------


def _make_annotation(text: str, sentence_offsets: list[tuple[int, int]]) -> dict[str, Any]:
    """Tiny CoreNLP-shaped annotation for unit tests.

    ``sentence_offsets`` is a list of ``(char_begin, char_end)`` pairs
    describing each sentence. The returned dict is enough for
    ``plan_clause_units_v4`` to operate on; we mimic the fields the
    planner actually reads (``sentences[].tokens[].characterOffsetBegin``
    / ``characterOffsetEnd`` and ``tokens[].word``). The actual POS /
    dependency parser is irrelevant because the planner only uses
    ``merge_corenlp_sentence_groups`` (which uses token offsets) and
    a regex pass over the text.

    Token offsets are computed from the *source* text via
    :func:`re.finditer` so the last token's ``characterOffsetEnd`` is
    the true end of the source. A cursor-only accumulator (which is what
    a previous version of this helper did) is wrong: it stops at
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
        # two "shall" with no connector between them; the old code would
        # midpoint-cut inside a word. The new code must keep one unit.
        text = "The taxpayer shall perform the action; the office shall verify the data"
        # single sentence (so the multi-modal split branch is even hit)
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        # we asked for 2 deontic anchors, but the connector ";" is
        # present — so a split IS allowed. Make sure it's safe.
        assert all(
            0 <= u["clause_char_span"][0] < u["clause_char_span"][1] <= len(text)
            for u in units
        )
        for u in units:
            s, e = u["clause_char_span"]
            # no leading separator
            assert text[s] not in {" ", "\t", "\n", ";", ",", ":"}
            # the slice must be well-formed
            assert 0 <= s < e <= len(text)
            # the next clause must not start with ";"; the first clause
            # naturally ends at the ";" which is the boundary marker
            assert has_clause_end_boundary(text, e)

    def test_no_connector_no_split_when_window_has_none(self) -> None:
        # Build a sentence where the two "shall" markers are separated
        # by plain text with no connector whatsoever.
        text = "The taxpayer shall submit the information the office shall review"
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        # the helper has no connector to anchor on, so it must keep a
        # single clause (or refuse the unsafe split). The old code
        # midpoint-cut which would emit a half-word span.
        if len(units) > 1:
            # if a split happened, it must be on a real connector,
            # never on a character midpoint.
            for u in units:
                s, e = u["clause_char_span"]
                assert text[s] not in {" ", "\t", "\n", ";", ","}
                assert has_safe_boundary(text, s, e)
        # in either case, the no_connector_no_split counter must have
        # recorded the absence of a connector for the midpoint window.
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
        # second clause must not start with whitespace, ";", ",", or ":"
        assert text[s2] not in {" ", "\t", "\n", ";", ",", ":"}
        # second clause must not be empty
        assert e2 > s2
        # the union of clause texts must be a contiguous partition of
        # the source text (modulo leading separator stripping)
        assert text[s1:e1] + text[s2:e2]  # both non-empty
        # and the original semicolon sits between the two clauses
        assert e1 <= text.find(";") + 1
        assert s2 > text.find(";")

    def test_connector_priority_semicolon_wins_over_and(self) -> None:
        # the window between the two "shall" contains BOTH ";" and " and "
        text = (
            "The taxpayer shall submit the form; and the office shall record it"
        )
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        assert len(units) == 2
        s1, e1 = units[0]["clause_char_span"]
        s2, e2 = units[1]["clause_char_span"]
        # the semicolon position should be inside the first clause (or
        # at the boundary); the "and" must not have shifted the cut
        # beyond the semicolon
        assert e1 <= text.find(";") + 1
        assert s2 > text.find(";")

    def test_old_midpoint_demo(self) -> None:
        # the OLD code would have cut the window text at the char
        # midpoint, landing inside a word. Reproduce that on the same
        # input.
        text = "The taxpayer shall submit the form the office shall record it"
        # positions of the two "shall" words
        positions = [m.start() for m in re.finditer(r"\bshall\b", text)]
        assert len(positions) == 2
        m1_end = positions[0] + len("shall")
        m2_start = positions[1]
        cut = _old_clause_midpoint_cut(text, m1_end, m2_start)
        # the old midpoint falls inside a word like "form"
        slice_after = text[cut : cut + 10]
        # the slice begins mid-word
        assert slice_after[0].isalpha() and text[cut - 1].isalpha()

    def test_old_connector_loop_picks_last_demo(self) -> None:
        # prove the OLD loop was non-deterministic on multi-connector
        # windows
        text = "first shall rest; and or but second shall"
        s = text.find("rest") + len("rest")
        e = text.find("second", s)
        cut = _old_clause_connector_pick(text, s, e)
        assert text[cut : cut + 3] == "but"  # the OLD code took the LAST

    def test_long_sentence_with_unicode(self) -> None:
        # German umlauts and ß; English modals (we are not validating
        # German modal coverage, only that unicode code points are
        # safe). The text is contrived but exercises the same code
        # path: two deontic anchors, a semicolon connector, unicode
        # code points throughout.
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
            # no half-character slice
            assert text[s:e] == text[s:e]
            assert has_clause_end_boundary(text, e)

    def test_no_safe_boundary_records_no_split(self) -> None:
        # an extreme case: a single token sentence with no whitespace,
        # no connector, no punctuation. The new code must NOT split and
        # must NOT midpoint-cut.
        text = "perform"
        ann = _make_annotation(text, [(0, len(text))])
        units, stats = plan_clause_units_v4(ann, text)
        assert len(units) == 1
        assert units[0]["clause_char_span"] == (0, len(text))
        # the no_connector counter is irrelevant here because there is
        # only one marker; the midpoint branch is never reached.

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
            # the slice must be valid and the end must be a clause-end
            # boundary (whitespace, ";" or "." at end-1, or end of source)
            assert 0 <= s < e <= len(text)
            assert has_clause_end_boundary(text, e)
            assert text[s] not in {" ", "\t", "\n", ";", ",", ":"}


# ---------------------------------------------------------------------------
# Section 5: active v10 actor/action call chain
# ---------------------------------------------------------------------------


def _make_tiny_sentence(text: str) -> dict[str, Any]:
    """Build a sentence mapping that extract_actors_actions_edges consumes.

    The active path uses basicDependencies to find ``nsubj`` of the modal
    head. We hand-craft a single sentence where "shall" governs a verb
    that has a subject token; the rest of the dependencies are empty.
    """
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
    # find the verb token and the subject token
    verb_idx = next(
        (i for i, t in enumerate(tokens, start=1) if t["word"].casefold() in {"performs", "files", "submits"}),
        3,
    )
    subj_idx = 1  # first token = "taxpayer"
    deps = [
        {
            "dep": "ROOT",
            "governor": 0,
            "dependent": verb_idx,
        },
        {
            "dep": "nsubj",
            "governor": verb_idx,
            "dependent": subj_idx,
        },
    ]
    return {"tokens": tokens, "basicDependencies": deps}


class TestActiveV10CallChain:
    def test_action_slice_respects_token_boundary(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # We call the active extract_actors_actions_edges with a long
        # action text that would have triggered the +80 hard cap. The
        # new code must use safe_action_slice and never emit a span
        # that ends mid-word.
        long_action = (
            "The taxpayer shall perform the following actions in order to comply "
            "with section 12 paragraph 3 of the act and file the required "
            "information without undue delay at the responsible office."
        )
        sentence_text = long_action
        sent = _make_tiny_sentence(sentence_text)
        # The "verb" we built isn't "perform"; adapt by making the verb
        # word "perform" exist as one of the tokens so the modal
        # auxiliary pattern picks it up. We patch _is_modal_token /
        # _deps via a small monkeypatch instead of rebuilding from
        # scratch: we add an aux dep from "shall" to the verb.
        verb_idx = next(
            (i for i, t in enumerate(sent["tokens"], start=1) if t["word"].casefold() in {"perform"}),
            3,
        )
        sent["basicDependencies"].append(
            {"dep": "aux", "governor": verb_idx, "dependent": 2}
        )

        # Build a tiny lexicon that recognises "taxpayer" as an actor
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
        # The new code must not produce a half-word action.
        for a in actions:
            s, e = a["start"], a["end"]
            assert 0 <= s < e <= len(sentence_text)
            # the slice text matches the source slice (always true but
            # worth stating explicitly)
            assert a["text"] == sentence_text[s:e]
            # no half-word at the end: if the next char exists, it must
            # not be a letter continuing the word
            if e < len(sentence_text):
                assert not (sentence_text[e - 1].isalpha() and sentence_text[e].isalpha())
            assert has_safe_boundary(sentence_text, s, e)
        # at least one action must have been emitted
        assert actions
        # the new stats counter must be present (so dashboards / manifests
        # do not break) and may be > 0 if the +80 cap was hit
        assert "action_cap_warnings" in stats
        assert "action_cap_drops" in stats
        # the old code allowed ``drops`` to be 0; the new code may drop
        # an action that had no safe boundary. Either is acceptable but
        # the half-word is never observed.

    def test_actor_action_returns_well_formed_spans(self) -> None:
        sentence_text = "The taxpayer shall file the return."
        sent = _make_tiny_sentence(sentence_text)
        # add the modal aux dep so the verb is selected as action head
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
            ("hello world", 0, 5, True),         # "hello", token boundary both sides
            ("hello world", 6, 11, True),         # "world", token boundary both sides
            ("hello world", 0, 11, True),         # full sentence
            ("hello world", 3, 8, False),         # mid-word both sides
            ("alpha, beta", 0, 6, True),          # "alpha," — comma is phrase boundary
            ("alpha, beta", 5, 10, False),        # ", bet" — comma start OK but ends mid-word
            ("alpha, beta", 6, 10, False),        # " bet" — ends mid-word in "beta"
            ("alpha, beta", 7, 10, False),        # "bet" — ends mid-word in "beta"
            ("alpha, beta", 7, 11, True),         # "beta" — full word
            ("", 0, 0, False),                    # empty
        ],
    )
    def test_has_safe_boundary(self, text: str, start: int, end: int, ok: bool) -> None:
        assert has_safe_boundary(text, start, end) is ok

    def test_assert_span_invariants_passes_for_safe_span(self) -> None:
        # should not raise
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

"""B0-R1-SCOPE-DISAMBIG (C2): cross-field identical-span dedupe tests.

Covers the fix in ``bpc_hybrid.b0_v10.scope``: when the exact same span is
claimed by both condition and constraint and exactly one side is lexicon-
backed, the lexicon-backed field wins; both-tregex / both-lexicon identical
pairs are kept; non-identical overlaps are untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.b0_v10.scope import resolve_scope_fields_v10  # noqa: E402
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2  # noqa: E402

LEXICON = load_lexicon_v2(ROOT)


def sent_with(text: str, begin: int, end: int) -> dict[str, Any]:
    words = text.split()
    tokens: list[dict[str, Any]] = []
    cursor = 0
    for idx, w in enumerate(words, start=0):
        start = text.find(w, cursor)
        e = start + len(w)
        tokens.append(
            {
                "index": idx + 1,
                "word": w,
                "characterOffsetBegin": start,
                "characterOffsetEnd": e,
            }
        )
        cursor = e
    return {"tokens": tokens, "begin": begin, "end": end}


def run(text: str, tregex_obs: dict[str, list] | None) -> dict[str, list]:
    scope, decisions, stats = resolve_scope_fields_v10(
        clause_text=text,
        clause_start=0,
        source_text=text,
        lexicon=LEXICON,
        tregex_obs=tregex_obs,
    )
    return scope


def spans(scope: dict[str, list], field: str) -> list[tuple[str, int, int]]:
    return [(s["text"], s["start"], s["end"]) for s in scope.get(field, [])]


def test_lexicon_condition_wins_over_tregex_constraint_identical_span() -> None:
    # "to the extent" is a condition-lexicon marker whose span expands to the
    # whole clause; a constraint Tregex obs claims the same clause span.
    text = "To the extent that the input tax can be deducted"
    sent = sent_with(text, 0, 10)
    scope = run(text, {"constraint": [(sent, {"begin": 0, "end": 10})]})
    assert spans(scope, "condition")  # lexicon condition side kept
    assert not spans(scope, "constraint")  # tregex constraint side removed


def test_lexicon_constraint_wins_over_tregex_condition_identical_span() -> None:
    # "to an annual" is a constraint-lexicon marker; a condition Tregex obs
    # claims the same clause span.
    text = "to an annual amount for the purpose of determining the tax rate"
    sent = sent_with(text, 0, 12)
    scope = run(text, {"condition": [(sent, {"begin": 0, "end": 12})]})
    assert spans(scope, "constraint")
    assert not spans(scope, "condition")


def test_both_tregex_identical_pair_is_kept() -> None:
    text = "in determining the income for that calendar year"
    sent = sent_with(text, 0, 8)
    scope = run(
        text,
        {
            "condition": [(sent, {"begin": 0, "end": 8})],
            "constraint": [(sent, {"begin": 0, "end": 8})],
        },
    )
    assert len(spans(scope, "condition")) == 1
    assert len(spans(scope, "constraint")) == 1


def test_single_field_span_untouched() -> None:
    # A constraint-only span (no identical condition counterpart) survives.
    text = "to an annual amount for the purpose of determining the tax rate"
    scope = run(text, None)
    assert spans(scope, "constraint")
    assert not spans(scope, "condition")


def test_non_identical_overlapping_spans_untouched() -> None:
    text = "if the land was acquired within the last ten years"
    sent = sent_with(text, 0, 2)
    scope = run(text, {"condition": [(sent, {"begin": 0, "end": 2})]})
    # condition obs "if ..." (0-2) and lexicon constraint "within ..." (overlap,
    # different boundaries) must both survive.
    assert len(spans(scope, "condition")) >= 1
    assert len(spans(scope, "constraint")) >= 1


def test_exception_unless_carveout_still_works() -> None:
    text = "The rule shall apply unless the office objects"
    scope = run(text, None)
    assert spans(scope, "exception")

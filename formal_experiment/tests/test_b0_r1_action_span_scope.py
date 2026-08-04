"""B0-R1-ACTION: action-span scope regression tests.

Covers the C1 fix in ``bpc_hybrid.b0_v10.actor_action``: the action span must
exclude the subject NP and clausal tails (nsubj/agent/advcl/ccomp/mark/
discourse/cc/conj) while keeping VP content (aux, dobj, PP modifiers), and
multi-word actors must be extracted end-to-end through the production path
with a well-formed dependency tree.
"""

from __future__ import annotations

import sys
from typing import Any

import pytest

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.b0_v10.actor_action import (  # noqa: E402
    extract_actors_actions_edges,
)


class _StubLex:
    actor_surfaces = {"taxpayer", "minister", "employee", "authority"}


def make_sentence(text: str, deps: list[tuple[int, int, str]]) -> dict[str, Any]:
    """Build a token/dependency sentence mapping from index-1 based arcs."""
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
    basic_dependencies = [
        {"dep": rel, "governor": gov, "dependent": dep} for gov, dep, rel in deps
    ]
    return {"tokens": tokens, "basicDependencies": basic_dependencies}


def run(text: str, deps: list[tuple[int, int, str]]) -> tuple[list, list, list, dict]:
    sent = make_sentence(text, deps)
    return extract_actors_actions_edges(
        sentence=sent,
        source_text=text,
        clause_start=0,
        clause_end=len(text),
        sentence_index=0,
        lexicon=_StubLex(),
    )


def _span(text: str, a0: int, a1: int) -> str:
    return text[a0:a1]


def test_action_excludes_subject_np() -> None:
    text = "The taxpayer shall file the return."
    # tokens: 1 The, 2 taxpayer, 3 shall, 4 file, 5 the, 6 return.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 4, "ROOT"),
            (4, 2, "nsubj"),
            (2, 1, "det"),
            (4, 3, "aux"),
            (4, 6, "dobj"),
            (6, 5, "det"),
        ],
    )
    assert len(actors) == 1
    assert actors[0]["text"] == "The taxpayer"
    assert len(actions) == 1
    assert actions[0]["text"] == "file the return."
    assert len(edges) == 1


def test_action_excludes_advcl_and_mark_tail() -> None:
    text = "It may cover a shorter period if 1."
    # 1 It, 2 may, 3 cover, 4 a, 5 shorter, 6 period, 7 if, 8 1.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 3, "ROOT"),
            (3, 2, "aux"),
            (3, 1, "nsubj"),
            (3, 6, "dobj"),
            (6, 4, "det"),
            (6, 5, "amod"),
            (3, 8, "advcl"),
            (8, 7, "mark"),
        ],
    )
    assert len(actions) == 1
    span_text = actions[0]["text"]
    assert "if" not in span_text
    assert "1." not in span_text
    assert "It" not in span_text
    assert "period" in span_text


def test_action_keeps_pp_modifier_content() -> None:
    text = "It shall be depreciated at the rates."
    # 1 It, 2 shall, 3 be, 4 depreciated, 5 at, 6 the, 7 rates.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 4, "ROOT"),
            (4, 2, "aux"),
            (4, 3, "aux:pass"),
            (4, 1, "nsubj:pass"),
            (4, 7, "obl"),
            (7, 5, "case"),
            (7, 6, "det"),
        ],
    )
    assert len(actions) == 1
    assert "rates" in actions[0]["text"]
    assert "depreciated" in actions[0]["text"]
    assert "It" not in actions[0]["text"]


def test_multiword_actor_extracted_end_to_end() -> None:
    text = "The Federal Minister for Science and Research shall issue the order."
    # 1 The, 2 Federal, 3 Minister, 4 for, 5 Science, 6 and, 7 Research,
    # 8 shall, 9 issue, 10 the, 11 order.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 9, "ROOT"),
            (9, 3, "nsubj"),
            (3, 1, "det"),
            (3, 2, "amod"),
            (3, 5, "nmod"),
            (5, 4, "case"),
            (5, 7, "conj"),
            (7, 6, "cc"),
            (9, 8, "aux"),
            (9, 11, "dobj"),
            (11, 10, "det"),
        ],
    )
    assert len(actors) == 1
    assert actors[0]["text"] == "The Federal Minister for Science and Research"
    assert len(actions) == 1
    assert actions[0]["text"] == "issue the order."
    assert len(edges) == 1


def test_conjoined_second_verb_not_swallowed_into_first_action() -> None:
    text = "The authority may decide and execute the transfer."
    # 1 The, 2 authority, 3 may, 4 decide, 5 and, 6 execute, 7 the, 8 transfer.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 4, "ROOT"),
            (4, 2, "nsubj"),
            (2, 1, "det"),
            (4, 3, "aux"),
            (4, 6, "conj"),
            (6, 5, "cc"),
            (6, 8, "dobj"),
            (8, 7, "det"),
        ],
    )
    assert len(actions) == 1
    assert "execute" not in actions[0]["text"]


def test_action_emitted_without_any_actor() -> None:
    text = "The return shall be filed."
    # 1 The, 2 return, 3 shall, 4 be, 5 filed.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 5, "ROOT"),
            (5, 4, "aux:pass"),
            (5, 3, "aux"),
            (5, 2, "nsubj:pass"),
            (2, 1, "det"),
        ],
    )
    assert len(actions) == 1
    assert "filed" in actions[0]["text"]
    assert len(edges) == 0


def test_passive_by_agent_obl_is_actor_with_edge() -> None:
    # CoreNLP 4.5.10 basicDependencies labels "sold by the employee" as
    # obl + case "by", not obl:agent.
    text = "It may be sold by the employee."
    # 1 It, 2 may, 3 be, 4 sold, 5 by, 6 the, 7 employee.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 4, "ROOT"),
            (4, 2, "aux"),
            (4, 3, "aux:pass"),
            (4, 1, "nsubj:pass"),
            (4, 7, "obl"),
            (7, 5, "case"),
            (7, 6, "det"),
        ],
    )
    assert len(actors) == 1
    assert actors[0]["text"] == "the employee"
    assert len(edges) == 1


def test_dative_to_obl_is_actor() -> None:
    text = "It is left to the employee."
    # 1 It, 2 is, 3 left, 4 to, 5 the, 6 employee.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 3, "ROOT"),
            (3, 2, "aux:pass"),
            (3, 1, "nsubj:pass"),
            (3, 6, "obl"),
            (6, 4, "case"),
            (6, 5, "det"),
        ],
    )
    assert len(actors) == 1
    assert actors[0]["text"] == "the employee"


def test_plain_verb_nsubj_actor_without_action_head() -> None:
    # "the taxpayer has claimed": "claimed" has no modal and is not the ROOT
    # verb, so no action head exists; the nsubj arc alone must yield the actor.
    text = "If the taxpayer has claimed the amount."
    # 1 If, 2 the, 3 taxpayer, 4 has, 5 claimed, 6 the, 7 amount.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 1, "ROOT"),
            (5, 3, "nsubj"),
            (3, 2, "det"),
            (5, 4, "aux"),
            (5, 7, "dobj"),
            (7, 6, "det"),
        ],
    )
    assert len(actions) == 0
    assert len(actors) == 1
    assert actors[0]["text"] == "the taxpayer"
    assert len(edges) == 0


def test_plain_verb_scan_skips_action_head_governors() -> None:
    # the action-head nsubj path already emitted "the taxpayer"; the
    # clause-wide scan must not duplicate it.
    text = "The taxpayer shall file the return."
    # 1 The, 2 taxpayer, 3 shall, 4 file, 5 the, 6 return.
    actors, actions, edges, _ = run(
        text,
        [
            (0, 4, "ROOT"),
            (4, 2, "nsubj"),
            (2, 1, "det"),
            (4, 3, "aux"),
            (4, 6, "dobj"),
            (6, 5, "det"),
        ],
    )
    assert len(actors) == 1
    assert actors[0]["text"] == "The taxpayer"

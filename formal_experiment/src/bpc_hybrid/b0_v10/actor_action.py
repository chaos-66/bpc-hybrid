"""Actor/action ownership edges with evidence only (no singleton guess)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime


@dataclass(frozen=True, slots=True)
class EdgeEvidence:
    ownership_relation: str
    governor_index: int
    dependent_index: int
    actor_span: dict[str, Any]
    action_span: dict[str, Any]
    sentence_index: int
    confidence: float


_NON_ACTOR = frozenset({
    "it", "this", "these", "those", "they", "he", "she", "we", "i", "which", "that",
    "profit", "income", "difference", "amount", "period", "year", "tax", "section",
})


def _token_abs(sentence: Mapping[str, Any], idx_1: int) -> tuple[int, int]:
    tok = sentence["tokens"][idx_1 - 1]
    return int(tok["characterOffsetBegin"]), int(tok["characterOffsetEnd"])


def _deps(sentence: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [d for d in (sentence.get("basicDependencies") or []) if isinstance(d, Mapping)]


def _subtree_span(sentence: Mapping[str, Any], head_idx: int) -> tuple[int, int]:
    kids = {head_idx}
    changed = True
    deps = _deps(sentence)
    while changed:
        changed = False
        for d in deps:
            g = int(d.get("governor", -1))
            dep = int(d.get("dependent", -1))
            if g in kids and dep not in kids and d.get("dep") != "ROOT":
                kids.add(dep)
                changed = True
    tokens = sentence["tokens"]
    begins = [tokens[i - 1]["characterOffsetBegin"] for i in kids]
    ends = [tokens[i - 1]["characterOffsetEnd"] for i in kids]
    return min(begins), max(ends)


def filter_actor_span(
    text: str,
    start: int,
    end: int,
    lexicon: LexiconV2Runtime,
) -> dict[str, Any] | None:
    span_text = text[start:end].strip()
    if not span_text:
        return None
    words = re.findall(r"[A-Za-z\u00c0-\u024f]+", span_text.casefold())
    if not words:
        return None
    if len(words) == 1 and words[0] in _NON_ACTOR:
        return None
    # lexicon surfaces are the sole positive actor lexicon source
    if not any(w in lexicon.actor_surfaces for w in words):
        # allow short title-case legal roles even without lexicon? NO: single source
        return None
    if len(span_text.split()) > 14:
        return None
    return {
        "text": span_text,
        "start": start,
        "end": end,
        "normalized": " ".join(span_text.casefold().split()),
    }


def extract_actors_actions_edges(
    *,
    sentence: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
    sentence_index: int,
    lexicon: LexiconV2Runtime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    tokens = sentence["tokens"]
    actors: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    stats = {"owner_pairs": 0, "edges_emitted": 0, "actors_rejected_non_subject": 0}

    def in_clause(idx: int) -> bool:
        a, b = _token_abs(sentence, idx)
        return not (b <= clause_start or a >= clause_end)

    action_heads: list[int] = []
    for d in _deps(sentence):
        if d.get("dep") in {"aux", "aux:pass"}:
            dep_i = int(d["dependent"])
            w = (tokens[dep_i - 1].get("word") or "").casefold()
            if w in {"shall", "must", "may", "can", "need"}:
                gov = int(d["governor"])
                if in_clause(gov):
                    action_heads.append(gov)
    for d in _deps(sentence):
        if d.get("dep") == "ROOT":
            r = int(d["dependent"])
            if in_clause(r) and r not in action_heads:
                if (tokens[r - 1].get("pos") or "").startswith("VB"):
                    action_heads.append(r)
    action_heads = sorted(set(action_heads))

    for head in action_heads:
        a0, a1 = _subtree_span(sentence, head)
        a0, a1 = max(a0, clause_start), min(a1, clause_end)
        if a1 <= a0:
            continue
        # trim leading modals
        text = source_text[a0:a1]
        text2 = re.sub(r"^(?:shall|must|may|can|not)\s+", "", text, flags=re.I)
        if text2 != text:
            pos = source_text.find(text2, a0, a1)
            if pos >= 0:
                a0, a1 = pos, pos + len(text2)
                text = text2
        if len(text.split()) > 15:
            head_pos = tokens[head - 1]["characterOffsetBegin"]
            a0 = max(clause_start, head_pos)
            a1 = min(clause_end, a0 + 80)
            text = source_text[a0:a1]
        action = {
            "text": text,
            "start": a0,
            "end": a1,
            "normalized": " ".join(text.casefold().split()),
            "head": head,
        }
        actions.append(action)
        action_idx = len(actions) - 1

        actor_idx_tok = None
        rel = None
        for d in _deps(sentence):
            if int(d.get("governor", -1)) == head and d.get("dep") in {"nsubj", "nsubj:pass"}:
                actor_idx_tok = int(d["dependent"])
                rel = d.get("dep")
                break
        if actor_idx_tok is None:
            for d in _deps(sentence):
                if int(d.get("governor", -1)) == head and d.get("dep") in {"obl:agent", "nmod:agent"}:
                    actor_idx_tok = int(d["dependent"])
                    rel = d.get("dep")
                    break
        if actor_idx_tok is None or not in_clause(actor_idx_tok):
            continue
        s0, s1 = _subtree_span(sentence, actor_idx_tok)
        s0, s1 = max(s0, clause_start), min(s1, clause_end)
        filtered = filter_actor_span(source_text, s0, s1, lexicon)
        if filtered is None:
            stats["actors_rejected_non_subject"] += 1
            continue
        # dedupe actors
        ai = None
        for j, existing in enumerate(actors):
            if not (filtered["end"] <= existing["start"] or filtered["start"] >= existing["end"]):
                ai = j
                break
        if ai is None:
            actors.append(filtered)
            ai = len(actors) - 1
        stats["owner_pairs"] += 1
        edges.append(
            {
                "actor_index": ai,
                "action_index": action_idx,
                "ownership_relation": rel or "nsubj",
                "governor_index": head,
                "dependent_index": actor_idx_tok,
                "sentence_index": sentence_index,
                "confidence": 0.9,
            }
        )
        stats["edges_emitted"] += 1
    return actors, actions, edges, stats

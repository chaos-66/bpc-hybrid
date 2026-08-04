"""Actor/action ownership edges with evidence only (no singleton guess)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v10.span_safety import safe_action_slice
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

# B0-R1-ACTION (2026-08-04): dependency relations that must NOT contribute
# to the ACTION span even though they are dominated by the verb head.
# BasicDependencies makes the subject and agent dependents of the verb, so a
# naive full subtree swallows the subject NP ("The taxpayer shall ...") and
# clausal tails ("... if 1.", "... whether he treats ...") into the action
# span.  The error analysis (docs/B0_ERROR_ANALYSIS.md C1) measured 192 of 212
# matched action Gold spans as over-extended by a median of 54 characters.
# The actor span keeps the FULL subtree (its subject NP is the actor itself).
_NON_ACTION_DEPS = frozenset({
    "nsubj", "nsubj:pass", "csubj", "csubj:pass",
    "obl:agent", "nmod:agent",
    "advcl", "ccomp", "mark", "discourse", "parataxis",
    "cc", "conj",
})


def _token_abs(sentence: Mapping[str, Any], idx_1: int) -> tuple[int, int]:
    tok = sentence["tokens"][idx_1 - 1]
    return int(tok["characterOffsetBegin"]), int(tok["characterOffsetEnd"])


def _deps(sentence: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [d for d in (sentence.get("basicDependencies") or []) if isinstance(d, Mapping)]


def _subtree_span(
    sentence: Mapping[str, Any],
    head_idx: int,
    *,
    exclude_deps: frozenset[str] = frozenset(),
    exclude_own_case: bool = False,
) -> tuple[int, int]:
    kids = {head_idx}
    changed = True
    deps = _deps(sentence)
    while changed:
        changed = False
        for d in deps:
            g = int(d.get("governor", -1))
            dep = int(d.get("dependent", -1))
            rel = d.get("dep") or ""
            if (
                g in kids
                and dep not in kids
                and rel != "ROOT"
                and rel not in exclude_deps
                and not (exclude_own_case and rel == "case" and g == head_idx)
            ):
                kids.add(dep)
                changed = True
    tokens = sentence["tokens"]
    begins = [tokens[i - 1]["characterOffsetBegin"] for i in kids]
    ends = [tokens[i - 1]["characterOffsetEnd"] for i in kids]
    return min(begins), max(ends)


def _trim_trailing_punct(text: str, s1: int) -> int:
    """Trim trailing whitespace and one trailing punctuation token."""
    while s1 > 0 and text[s1 - 1] in " \t\n":
        s1 -= 1
    if s1 > 0 and text[s1 - 1] in ".,;:!?":
        s1 -= 1
        while s1 > 0 and text[s1 - 1] in " \t\n":
            s1 -= 1
    return s1


def filter_actor_span(
    text: str,
    start: int,
    end: int,
    lexicon: LexiconV2Runtime,
    *,
    head_word: str | None = None,
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
    # B0-R1-ACTOR: when the NP head token is known (the nsubj/obl dependent),
    # the head itself must be a lexicon surface.  This rejects modifier-only
    # matches such as "the business year of a bookkeeping farmer" (head
    # "year") while keeping "the Federal Minister for Science and Research"
    # (head "minister").
    if head_word is not None and head_word.casefold() not in lexicon.actor_surfaces:
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
    stats = {
        "owner_pairs": 0,
        "edges_emitted": 0,
        "actors_rejected_non_subject": 0,
        "action_cap_warnings": 0,
        "action_cap_drops": 0,
    }

    def in_clause(idx: int) -> bool:
        a, b = _token_abs(sentence, idx)
        return not (b <= clause_start or a >= clause_end)

    def case_word(dep_idx: int) -> str | None:
        # the preposition of an obl/nmod NP ("by", "to", ...)
        for d in _deps(sentence):
            if int(d.get("governor", -1)) == dep_idx and d.get("dep") == "case":
                ci = int(d["dependent"])
                if 1 <= ci <= len(tokens):
                    return (tokens[ci - 1].get("word") or "").casefold()
        return None

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
        # B0-R1-ACTION: exclude subject/agent NPs and clausal tails from the
        # action span; keep PP modifiers and complements (VP content).
        a0, a1 = _subtree_span(sentence, head, exclude_deps=_NON_ACTION_DEPS)
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
            head_token_end = tokens[head - 1]["characterOffsetEnd"]
            a0 = max(clause_start, head_pos)
            # B0-R1-A: token-safe action slice. The old a2383e9
            # implementation delegated to ``safe_window_end`` which
            # returned at the *first* whitespace inside the cap. For
            # long actions that meant the slice collapsed to a single
            # word ("process" instead of the full action). The new
            # helper walks to the RIGHTMOST safe token/punctuation
            # boundary inside the cap and never falls below the head
            # token's own end. We pass ``head_token_end`` explicitly
            # so the helper always covers the full action head token,
            # even when the cap is too small. When no safe boundary
            # exists at all, the helper returns start (empty) and a
            # BoundaryWarning, and we drop the action rather than emit
            # a half-word.
            new_a0, new_a1, warning = safe_action_slice(
                source_text,
                a0,
                clause_end,
                max_chars=80,
                head_token_end=head_token_end,
            )
            if warning is not None:
                stats["action_cap_warnings"] += 1
            if new_a1 <= new_a0:
                # safe slice produced an empty window: skip this action
                stats["action_cap_drops"] += 1
                continue
            a0, a1 = new_a0, new_a1
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

        # B0-R1-ACTOR: collect every subject/agent candidate of the action
        # head (nsubj, obl:agent/nmod:agent, and plain obl/nmod with a
        # "by"/"to" case -- CoreNLP 4.5.10 labels passive by-agents and
        # dative recipients this way) and take the first candidate that
        # passes the actor filter.  Previously the first arc won outright,
        # so a non-lexicon subject (e.g. "the free drink allowance") could
        # shadow the by-agent ("by the employee").
        actor_candidates: list[tuple[int, str]] = []
        for d in _deps(sentence):
            if int(d.get("governor", -1)) == head and d.get("dep") in {"nsubj", "nsubj:pass"}:
                actor_candidates.append((int(d["dependent"]), d.get("dep")))
        for d in _deps(sentence):
            if int(d.get("governor", -1)) == head and d.get("dep") in {"obl:agent", "nmod:agent"}:
                actor_candidates.append((int(d["dependent"]), d.get("dep")))
        for d in _deps(sentence):
            if (
                int(d.get("governor", -1)) == head
                and d.get("dep") in {"obl", "nmod"}
                and case_word(int(d["dependent"])) in {"by", "to"}
            ):
                actor_candidates.append((int(d["dependent"]), d.get("dep")))
        actor_idx_tok = None
        rel = None
        for cand_idx, cand_rel in actor_candidates:
            if not in_clause(cand_idx):
                continue
            cand_s0, cand_s1 = _subtree_span(
                sentence, cand_idx, exclude_own_case=True
            )
            cand_s0, cand_s1 = max(cand_s0, clause_start), min(cand_s1, clause_end)
            cand_s1 = _trim_trailing_punct(source_text, cand_s1)
            if cand_s1 <= cand_s0:
                continue
            if (
                filter_actor_span(
                    source_text,
                    cand_s0,
                    cand_s1,
                    lexicon,
                    head_word=tokens[cand_idx - 1].get("word"),
                )
                is None
            ):
                stats["actors_rejected_non_subject"] += 1
                continue
            actor_idx_tok = cand_idx
            rel = cand_rel
            break
        if actor_idx_tok is None:
            continue
        s0, s1 = _subtree_span(sentence, actor_idx_tok, exclude_own_case=True)
        s0, s1 = max(s0, clause_start), min(s1, clause_end)
        s1 = _trim_trailing_punct(source_text, s1)
        if s1 <= s0:
            continue
        filtered = filter_actor_span(
            source_text,
            s0,
            s1,
            lexicon,
            head_word=tokens[actor_idx_tok - 1].get("word"),
        )
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

    # B0-R1-ACTOR: gold actors often attach to verbs that are NOT action
    # heads -- participles ("the person performing the activity"), plain
    # verbs in subordinate clauses ("If the taxpayer has claimed ...",
    # "when an employee leaves ..."), and passive predicates without a modal
    # ("the recipient is obliged to accept").  Every nsubj/nsubj:pass arc
    # whose governor lies in the clause yields an actor candidate (no edge:
    # the ownership edge requires an action head).
    for d in _deps(sentence):
        if d.get("dep") not in {"nsubj", "nsubj:pass"}:
            continue
        gov = int(d.get("governor", -1))
        dep_i = int(d["dependent"])
        if gov in action_heads or not in_clause(gov) or not in_clause(dep_i):
            continue
        s0, s1 = _subtree_span(sentence, dep_i, exclude_own_case=True)
        s0, s1 = max(s0, clause_start), min(s1, clause_end)
        s1 = _trim_trailing_punct(source_text, s1)
        if s1 <= s0:
            continue
        filtered = filter_actor_span(
            source_text,
            s0,
            s1,
            lexicon,
            head_word=tokens[dep_i - 1].get("word"),
        )
        if filtered is None:
            stats["actors_rejected_non_subject"] += 1
            continue
        ai = None
        for j, existing in enumerate(actors):
            if not (filtered["end"] <= existing["start"] or filtered["start"] >= existing["end"]):
                ai = j
                break
        if ai is None:
            actors.append(filtered)
    return actors, actions, edges, stats

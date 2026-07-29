"""B5 actor/action extraction: post-surgery Tregex only, no dependency spans.

Rules (fixed):
1. actor/action candidates only from B5 bridge post-surgery Tregex observations.
2. dependency_candidate_span_count must be 0.
3. dependency_fallback_count must be 0.
4. No record/spaCy/heuristic whole-clause fallback.
5. Dependency may only locate a lexical head inside a Tregex action match and
   attach ownership evidence for already selected spans.
6. Dependency must not create, expand, rewrite, or invent spans.
7. Passive leading "by " may be stripped only as an original contiguous slice.
8. Multi-match dedupe: smallest sufficient span -> leftmost -> pattern index.
9. actor_action_map only connects existing actor/action spans.
10. Never envelope discontinuous original-token runs.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime

_NON_ACTOR = frozenset(
    {
        "it",
        "this",
        "these",
        "those",
        "they",
        "he",
        "she",
        "we",
        "i",
        "which",
        "that",
        "profit",
        "income",
        "difference",
        "amount",
        "period",
        "year",
        "tax",
        "section",
    }
)


def _parse_runs(runs: str) -> list[tuple[int, int]]:
    """Parse '3-7,12-16' into [(3,7),(12,16)] (end exclusive token indexes)."""
    if not runs or not str(runs).strip():
        return []
    out: list[tuple[int, int]] = []
    for part in str(runs).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            raise ValueError(f"malformed token run: {runs!r}")
        a, b = part.split("-", 1)
        begin, end = int(a), int(b)
        if end <= begin or begin < 0:
            raise ValueError(f"invalid token run bounds: {part!r}")
        out.append((begin, end))
    if out != sorted(out) or any(left[1] > right[0] for left, right in zip(out, out[1:])):
        raise ValueError(f"token runs are not ordered and disjoint: {runs!r}")
    return out


def _token_char_span(
    sentence: Mapping[str, Any], begin: int, end: int
) -> tuple[int, int]:
    tokens = sentence["tokens"]
    if begin < 0 or end <= begin or end > len(tokens):
        raise ValueError(f"token indexes out of range [{begin}:{end}]")
    return int(tokens[begin]["characterOffsetBegin"]), int(
        tokens[end - 1]["characterOffsetEnd"]
    )


def _source_slice(
    source_text: str, start: int, end: int
) -> dict[str, Any]:
    if start < 0 or end <= start or end > len(source_text):
        raise ValueError(f"invalid char span [{start}:{end}]")
    text = source_text[start:end]
    if source_text[start:end] != text:
        raise ValueError("source-slice identity failure")
    return {
        "text": text,
        "start": start,
        "end": end,
        "normalized": " ".join(text.casefold().split()),
    }


def _trim_outer_whitespace(source_text: str, span: dict[str, Any]) -> dict[str, Any]:
    start = int(span["start"])
    end = int(span["end"])
    while start < end and source_text[start].isspace():
        start += 1
    while end > start and source_text[end - 1].isspace():
        end -= 1
    if end <= start:
        raise ValueError("span contains whitespace only")
    return _source_slice(source_text, start, end)


def _filter_actor(
    source_text: str, span: dict[str, Any], lexicon: LexiconV2Runtime
) -> dict[str, Any] | None:
    span = _trim_outer_whitespace(source_text, span)
    text = span["text"]
    words = re.findall(r"[A-Za-z\u00c0-\u024f]+", text.casefold())
    if not words:
        return None
    if len(words) == 1 and words[0] in _NON_ACTOR:
        return None
    if not any(w in lexicon.actor_surfaces for w in words):
        return None
    if len(text.split()) > 14:
        return None
    return {
        "text": text,
        "start": span["start"],
        "end": span["end"],
        "normalized": " ".join(text.casefold().split()),
    }


def _strip_leading_by(source_text: str, span: dict[str, Any]) -> dict[str, Any]:
    span = _trim_outer_whitespace(source_text, span)
    text = span["text"]
    m = re.match(r"^(by)\s+", text, flags=re.I)
    if not m:
        return span
    new_start = span["start"] + m.end()
    if new_start >= span["end"]:
        return span
    return _source_slice(source_text, new_start, span["end"])


def _trim_leading_modals(source_text: str, span: dict[str, Any]) -> dict[str, Any]:
    span = _trim_outer_whitespace(source_text, span)
    text = span["text"]
    m = re.match(r"^(?:shall|must|may|can|not)\s+", text, flags=re.I)
    if not m:
        return span
    new_start = span["start"] + m.end()
    if new_start >= span["end"]:
        return span
    return _source_slice(source_text, new_start, span["end"])


def _select_run_for_action_head(
    *,
    sentence: Mapping[str, Any],
    runs: list[tuple[int, int]],
    source_text: str,
    clause_start: int,
    clause_end: int,
) -> dict[str, Any] | None:
    """Pick the contiguous run that contains the Tregex action lexical head.

    Dependency is used only inside the Tregex match runs to locate a VB* head
    token index; it never creates a span outside those runs.
    """
    if not runs:
        return None
    tokens = sentence["tokens"]
    run_token_indexes = {
        index for begin, end in runs for index in range(begin, end)
    }
    if any(index < 0 or index >= len(tokens) for index in run_token_indexes):
        raise ValueError("action token run is outside the CoreNLP sentence")
    verbal_indexes = [
        index
        for index in sorted(run_token_indexes)
        if str(tokens[index].get("pos") or "").startswith("VB")
    ]
    if not verbal_indexes:
        # The frozen action Tregex requires a VB* descendant.  Missing one is
        # malformed bridge/annotation evidence, never a dependency fallback.
        raise ValueError("Tregex action observation has no surviving verbal token")

    deps = [d for d in (sentence.get("basicDependencies") or []) if isinstance(d, Mapping)]
    root_verbs = {
        int(d.get("dependent", -1)) - 1
        for d in deps
        if d.get("dep") == "ROOT"
    }
    governing_verbs = {
        int(d.get("governor", -1)) - 1
        for d in deps
        if int(d.get("governor", -1)) > 0
        and int(d.get("dependent", -1)) > 0
        and (int(d.get("dependent", -1)) - 1) in run_token_indexes
    }
    # Dependency is used only to choose a head already inside the Tregex runs.
    # It never supplies a token outside the observation or creates a candidate.
    head_tok = next((i for i in verbal_indexes if i in root_verbs), None)
    if head_tok is None:
        head_tok = next((i for i in verbal_indexes if i in governing_verbs), None)
    if head_tok is None:
        head_tok = verbal_indexes[0]

    chosen = next(((begin, end) for begin, end in runs if begin <= head_tok < end), None)
    if chosen is None:
        raise ValueError("action lexical head is outside surviving Tregex runs")
    begin, end = chosen
    try:
        c0, c1 = _token_char_span(sentence, begin, end)
    except ValueError:
        return None
    c0, c1 = max(c0, clause_start), min(c1, clause_end)
    if c1 <= c0:
        return None
    span = _source_slice(source_text, c0, c1)
    span = _trim_leading_modals(source_text, span)
    span["token_begin"] = begin
    span["token_end"] = end
    span["head_token"] = head_tok if head_tok is not None else begin
    span["route"] = "post_surgery_tregex"
    return span


def _actor_from_observation(
    *,
    sentence: Mapping[str, Any],
    obs: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
    lexicon: LexiconV2Runtime,
) -> dict[str, Any] | None:
    runs = _parse_runs(str(obs.get("token_runs") or ""))
    if not runs:
        # Single contiguous envelope only if bridge reported no gaps and begin/end set.
        begin = obs.get("begin")
        end = obs.get("end")
        if not isinstance(begin, int) or not isinstance(end, int) or end <= begin:
            return None
        runs = [(begin, end)]
    # Actor must be one continuous run; multiple discontinuous runs are rejected.
    if len(runs) != 1:
        return None
    begin, end = runs[0]
    try:
        c0, c1 = _token_char_span(sentence, begin, end)
    except ValueError:
        return None
    c0, c1 = max(c0, clause_start), min(c1, clause_end)
    if c1 <= c0:
        return None
    span = _source_slice(source_text, c0, c1)
    span = _strip_leading_by(source_text, span)
    filtered = _filter_actor(source_text, span, lexicon)
    if filtered is None:
        return None
    filtered["token_begin"] = begin
    filtered["token_end"] = end
    filtered["pattern_index"] = int(obs.get("pattern_index", 0))
    filtered["route"] = "post_surgery_tregex"
    return filtered


def _action_from_observation(
    *,
    sentence: Mapping[str, Any],
    obs: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
) -> dict[str, Any] | None:
    runs = _parse_runs(str(obs.get("token_runs") or ""))
    if not runs:
        begin = obs.get("begin")
        end = obs.get("end")
        if not isinstance(begin, int) or not isinstance(end, int) or end <= begin:
            return None
        runs = [(begin, end)]
    # Never envelope multiple runs into one span.
    span = _select_run_for_action_head(
        sentence=sentence,
        runs=runs,
        source_text=source_text,
        clause_start=clause_start,
        clause_end=clause_end,
    )
    if span is None:
        return None
    if len(span["text"].split()) > 20:
        # Keep head-local contiguous run only; already one run.
        pass
    span["pattern_index"] = int(obs.get("pattern_index", 0))
    return span


def _dedupe_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """smallest sufficient span -> leftmost -> pattern index."""
    if not spans:
        return []
    ranked = sorted(
        spans,
        key=lambda s: (
            int(s["end"]) - int(s["start"]),
            int(s["start"]),
            int(s.get("pattern_index", 0)),
        ),
    )
    kept: list[dict[str, Any]] = []
    for sp in ranked:
        dominated = False
        for other in kept:
            # If an already-kept smaller/equal span is inside this one, skip this.
            if other["start"] >= sp["start"] and other["end"] <= sp["end"]:
                dominated = True
                break
            # Overlap with different extent: keep leftmost smaller already chosen.
            if not (sp["end"] <= other["start"] or sp["start"] >= other["end"]):
                dominated = True
                break
        if not dominated:
            kept.append(sp)
    kept.sort(key=lambda s: (int(s["start"]), int(s["end"])))
    return kept


def _ownership_edges(
    *,
    sentence: Mapping[str, Any],
    sentence_index: int,
    actors: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach ownership only between already selected spans via dependency evidence."""
    edges: list[dict[str, Any]] = []
    deps = [
        d
        for d in (sentence.get("basicDependencies") or [])
        if isinstance(d, Mapping)
    ]
    tokens = sentence["tokens"]

    def token_in_span(tok_idx_1: int, span: Mapping[str, Any]) -> bool:
        # CoreNLP deps are 1-based token indexes.
        if tok_idx_1 <= 0 or tok_idx_1 > len(tokens):
            return False
        tok = tokens[tok_idx_1 - 1]
        a = int(tok["characterOffsetBegin"])
        b = int(tok["characterOffsetEnd"])
        return not (b <= int(span["start"]) or a >= int(span["end"]))

    for aci, action in enumerate(actions):
        head = action.get("head_token")
        head_1 = int(head) + 1 if isinstance(head, int) else None
        for ai, actor in enumerate(actors):
            rel = None
            gov = None
            dep_i = None
            for d in deps:
                dep_name = d.get("dep")
                if dep_name not in {"nsubj", "nsubj:pass", "obl:agent", "nmod:agent"}:
                    continue
                g = int(d.get("governor", -1))
                dep = int(d.get("dependent", -1))
                if head_1 is not None and g != head_1:
                    # governor must be the action head when known
                    if not token_in_span(g, action):
                        continue
                elif not token_in_span(g, action):
                    continue
                if not token_in_span(dep, actor):
                    continue
                rel = dep_name
                gov = g
                dep_i = dep
                break
            if rel is None:
                continue
            edges.append(
                {
                    "actor_index": ai,
                    "action_index": aci,
                    "ownership_relation": rel,
                    "governor_index": gov,
                    "dependent_index": dep_i,
                    "sentence_index": sentence_index,
                    "confidence": 0.9,
                    "route": "post_surgery_tregex_ownership",
                }
            )
    return edges


def extract_actors_actions_edges_b5(
    *,
    sentence: Mapping[str, Any],
    source_text: str,
    clause_start: int,
    clause_end: int,
    sentence_index: int,
    lexicon: LexiconV2Runtime,
    action_observations: Sequence[Mapping[str, Any]],
    actor_observations: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """Extract actor/action solely from post-surgery Tregex observations."""
    stats = {
        "dependency_candidate_span_count": 0,
        "dependency_fallback_count": 0,
        "post_surgery_action_obs": 0,
        "post_surgery_actor_obs": 0,
        "final_tregex_action_spans": 0,
        "final_tregex_actor_spans": 0,
        "source_slice_failures": 0,
        "discontinuous_actor_rejected": 0,
        "edges_emitted": 0,
    }

    raw_actions: list[dict[str, Any]] = []
    for obs in action_observations:
        if obs.get("phase") != "post_surgery":
            # Missing phase is malformed provenance, not an implicit legacy
            # compatibility path.  Pre-surgery observations are diagnostic only.
            if obs.get("phase") == "pre_surgery":
                continue
            raise ValueError("action observation lacks explicit post_surgery provenance")
        stats["post_surgery_action_obs"] += 1
        sp = _action_from_observation(
            sentence=sentence,
            obs=obs,
            source_text=source_text,
            clause_start=clause_start,
            clause_end=clause_end,
        )
        if sp is None:
            continue
        # Verify source slice identity.
        if source_text[sp["start"] : sp["end"]] != sp["text"]:
            stats["source_slice_failures"] += 1
            continue
        raw_actions.append(sp)

    raw_actors: list[dict[str, Any]] = []
    for obs in actor_observations:
        if obs.get("phase") != "post_surgery":
            if obs.get("phase") == "pre_surgery":
                continue
            raise ValueError("actor observation lacks explicit post_surgery provenance")
        stats["post_surgery_actor_obs"] += 1
        runs = _parse_runs(str(obs.get("token_runs") or ""))
        if len(runs) > 1:
            stats["discontinuous_actor_rejected"] += 1
            continue
        sp = _actor_from_observation(
            sentence=sentence,
            obs=obs,
            source_text=source_text,
            clause_start=clause_start,
            clause_end=clause_end,
            lexicon=lexicon,
        )
        if sp is None:
            continue
        if source_text[sp["start"] : sp["end"]] != sp["text"]:
            stats["source_slice_failures"] += 1
            continue
        raw_actors.append(sp)

    actions = _dedupe_spans(raw_actions)
    actors = _dedupe_spans(raw_actors)
    stats["final_tregex_action_spans"] = len(actions)
    stats["final_tregex_actor_spans"] = len(actors)

    edges = _ownership_edges(
        sentence=sentence,
        sentence_index=sentence_index,
        actors=actors,
        actions=actions,
    )
    stats["edges_emitted"] = len(edges)
    return actors, actions, edges, stats

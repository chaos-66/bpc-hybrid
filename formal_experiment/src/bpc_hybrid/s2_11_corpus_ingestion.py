# -*- coding: utf-8 -*-
"""Deterministic S2.11 corpus ingestion primitives (Checkpoint B).

These functions turn ONE membership requirement record into the hardened
adapter input with verifiable field-level provenance:
  * extract_modality: documented keyword rules with EXACT span offsets
    into the source text (first matched rule in pattern order; ties break
    by earliest position); returns None when no rule matches;
  * g05_features: deterministic G0.5 feature extraction with conservative
    floors (no structure invented under the applied S0 structural policy).

The artifact license is UNKNOWN: this module never copies raw text into
committed assets; the runner writes full candidates to the gitignored
local working directory only.
"""

from __future__ import annotations

import re
from typing import Any

# Deterministic modality keyword rules: (pattern, class). Prohibition is
# checked first so "must not" beats "must"; permission before obligation
# so "may"/"can" never fall through to obligation.
MODALITY_RULES: tuple[tuple[str, str], ...] = (
    (r"\bprohibited\b", "prohibition"),
    (r"\bmust not\b", "prohibition"),
    (r"\bnot allowed\b", "prohibition"),
    (r"\bnot eligible\b", "prohibition"),
    (r"\b(?:is|are) not obligated\b", "prohibition"),
    (r"\bis not needed\b", "prohibition"),
    (r"\bmay not\b", "prohibition"),
    (r"\bcan\b", "permission"),
    (r"\bmay\b", "permission"),
    (r"\bis allowed\b", "permission"),
    (r"\bpermitted\b", "permission"),
    (r"\bmust\b", "obligation"),
    (r"\bhas to\b", "obligation"),
    (r"\bhave to\b", "obligation"),
    (r"\bneeds to\b", "obligation"),
    (r"\bneed to\b", "obligation"),
    (r"\bshall\b", "obligation"),
    (r"\bshould\b", "obligation"),
    (r"\brequired\b", "obligation"),
    (r"\bneeded\b", "obligation"),
    (r"\bit is necessary\b", "obligation"),
    (r"\bnecessary to\b", "obligation"),
)

_MODALITY_RE = [(re.compile(pat), cls) for pat, cls in MODALITY_RULES]


def extract_modality(text: str) -> tuple[str, int, int] | None:
    """Return (modality_class, start, end) of the FIRST matched rule
    occurrence, or None when no rule matches."""
    best: tuple[int, int, str] | None = None  # (position, rule_index, cls)
    for rule_index, (rx, cls) in enumerate(_MODALITY_RE):
        for match in rx.finditer(text):
            pos = match.start()
            if best is None or pos < best[0] or (
                    pos == best[0] and rule_index < best[1]):
                best = (pos, rule_index, cls)
    if best is None:
        return None
    rx, _cls = _MODALITY_RE[best[1]]
    match = rx.search(text, best[0])
    assert match is not None
    return best[2], match.start(), match.end()


def g05_features(text: str) -> dict[str, Any]:
    """Deterministic G0.5 feature extraction (conservative floors; no
    structure invented under the S0 policy)."""
    clause_count = 1 + text.count(",") + text.count(";") \
        + text.count(". ") + text.count(" and ") + text.count(" or ")
    return {
        "text_length": len(text),
        "clause_count": max(1, clause_count),
        "dependency_depth": 1,
        "actor_count": 0,
        "action_count": 0,
        "condition_count": 1 if re.search(r"\bif\b", text, re.IGNORECASE)
        else 0,
        "constraint_count": 1 if re.search(
            r"\b(?:before|after|within|prior to)\b|valid from", text,
            re.IGNORECASE)
        else 0,
        "exception_count": 0,
        "nesting_depth": 1,
        "passive_voice_count": 0,
        "implicit_actor_count": 0,
        "cross_reference_count": 0,
        "language_markers": "original",
        "bpmn_activities": 0,
        "bpmn_gateways": 0,
        "bpmn_flows": 0,
        "bpmn_pools_lanes": 0,
        "bpmn_parallel_branches": 0,
        "bpmn_cycles": 0,
    }

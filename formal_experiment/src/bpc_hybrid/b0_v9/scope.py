"""Scope resolution with whitelist scope_test execution (no string eval)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from bpc_hybrid.sun_style.lexicon_v2_runtime import (
    LexiconV2Runtime,
    match_field_markers,
)


class ScopeTest(str, Enum):
    CONDITION_SUBORDINATOR = "condition_subordinator"
    EXCEPTION_CARVEOUT = "exception_carveout"
    TEMPORAL_CONSTRAINT = "temporal_constraint"
    QUANTITATIVE_CONSTRAINT = "quantitative_constraint"
    APPLICABILITY_CONDITION = "applicability_condition"
    DEFINITION_COPULAR = "definition_copular"
    ACTOR_SUBJECT_HEAD = "actor_subject_head"
    ACTOR_BY_AGENT = "actor_by_agent"


_KNOWN_SCOPE_ALIASES = {
    "condition_subordinator": ScopeTest.CONDITION_SUBORDINATOR,
    "exception_carveout": ScopeTest.EXCEPTION_CARVEOUT,
    "temporal_constraint": ScopeTest.TEMPORAL_CONSTRAINT,
    "quantitative_constraint": ScopeTest.QUANTITATIVE_CONSTRAINT,
    "applicability_condition": ScopeTest.APPLICABILITY_CONDITION,
    "definition_copular": ScopeTest.DEFINITION_COPULAR,
    "actor_subject_head": ScopeTest.ACTOR_SUBJECT_HEAD,
    "actor_by_agent": ScopeTest.ACTOR_BY_AGENT,
    # lexicon v2 free-text scope / syntactic_scope values mapped into whitelist
    "main_vp_anchor": ScopeTest.DEFINITION_COPULAR,
    "aux_or_main_vp_anchor": ScopeTest.DEFINITION_COPULAR,
    "vp_anchor": ScopeTest.DEFINITION_COPULAR,
    "subject_or_by_agent_or_nsubj": ScopeTest.ACTOR_SUBJECT_HEAD,
    "subject_or_nsubj_only": ScopeTest.ACTOR_SUBJECT_HEAD,
    "performance_limit_only": ScopeTest.QUANTITATIVE_CONSTRAINT,
    "pp_or_sbar": ScopeTest.CONDITION_SUBORDINATOR,
    "sbar_or_pp": ScopeTest.CONDITION_SUBORDINATOR,
    "sbar_or_advp": ScopeTest.CONDITION_SUBORDINATOR,
    "pp_only": ScopeTest.TEMPORAL_CONSTRAINT,
    "pp_or_advp": ScopeTest.TEMPORAL_CONSTRAINT,
    "sbar": ScopeTest.CONDITION_SUBORDINATOR,
    "sbar_marker_or_relative": ScopeTest.CONDITION_SUBORDINATOR,
    "relative_clause_only": ScopeTest.CONDITION_SUBORDINATOR,
}


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    marker_surface: str
    requested_field: str
    accepted_field: str | None
    scope_test: str
    evidence: dict[str, Any]
    accepted: bool
    rejection_reason: str | None


class ScopeTestError(ValueError):
    """Unknown or fail-closed scope_test."""


def parse_scope_test(raw: str | None) -> ScopeTest | None:
    if raw is None or not str(raw).strip():
        return None
    key = str(raw).strip()
    if key in _KNOWN_SCOPE_ALIASES:
        return _KNOWN_SCOPE_ALIASES[key]
    # allow enum value directly
    try:
        return ScopeTest(key)
    except ValueError as exc:
        raise ScopeTestError(f"unknown scope_test fail-closed: {raw!r}") from exc


def _clause_window(text: str, start: int, end: int, pad: int = 40) -> str:
    a = max(0, start - pad)
    b = min(len(text), end + pad)
    return text[a:b]


def apply_scope_test(
    *,
    field: str,
    surface: str,
    scope_test_raw: str | None,
    clause_text: str,
    match_start: int,
    match_end: int,
) -> ScopeDecision:
    st = parse_scope_test(scope_test_raw)
    window = _clause_window(clause_text, match_start, match_end)
    surface_cf = surface.casefold()
    evidence = {
        "window": window[:120],
        "match_start": match_start,
        "match_end": match_end,
    }
    if st is None:
        # no scope_test: accept requested field with low rigor note
        return ScopeDecision(
            surface, field, field, "none", evidence, True, None
        )

    # unless: condition vs exception
    if surface_cf == "unless" or st in {
        ScopeTest.CONDITION_SUBORDINATOR,
        ScopeTest.EXCEPTION_CARVEOUT,
    }:
        if surface_cf == "unless":
            # carve-out if introduces exclusion of rule application
            carve = bool(
                re.search(
                    r"\bunless\b.{0,40}\b(?:otherwise|excepted|excluded|does\s+not\s+apply)\b",
                    clause_text,
                    re.I,
                )
            )
            if field == "exception" or carve:
                ok = field == "exception" or carve
                accepted = "exception" if carve or field == "exception" else "condition"
                # never dual-accept: pick one
                if field == "condition" and carve:
                    return ScopeDecision(
                        surface, field, "exception", st.value, evidence, True, None
                    )
                if field == "exception" and not carve:
                    # still allow exception for unless carve-out default
                    return ScopeDecision(
                        surface, field, "exception", st.value, evidence, True, None
                    )
                return ScopeDecision(
                    surface, field, accepted, st.value, evidence, True, None
                )
            if field == "condition":
                return ScopeDecision(
                    surface, field, "condition", st.value, evidence, True, None
                )
            return ScopeDecision(
                surface, field, None, st.value, evidence, False, "unless_field_mismatch"
            )

    # after/before/until temporal
    if surface_cf in {"after", "before", "until"} or st == ScopeTest.TEMPORAL_CONSTRAINT:
        # if attaches as event condition
        if re.search(rf"\b{re.escape(surface_cf)}\b.{{0,30}}\b(?:if|when|whenever)\b", clause_text, re.I):
            if field == "condition":
                return ScopeDecision(surface, field, "condition", st.value, evidence, True, None)
            return ScopeDecision(surface, field, None, st.value, evidence, False, "temporal_as_condition")
        if field == "constraint":
            return ScopeDecision(surface, field, "constraint", st.value, evidence, True, None)
        if field == "condition":
            return ScopeDecision(surface, field, "condition", st.value, evidence, True, None)

    if surface_cf == "subject to" or st == ScopeTest.APPLICABILITY_CONDITION:
        if field in {"condition", "constraint"}:
            # default applicability -> condition
            accepted = "condition" if field == "condition" else "constraint"
            return ScopeDecision(surface, field, accepted, st.value, evidence, True, None)

    if surface_cf == "only" or st == ScopeTest.QUANTITATIVE_CONSTRAINT:
        if field == "constraint" and re.search(
            r"\bonly\b.{0,40}\b(?:if|when|for|to|within|after|before)\b", clause_text, re.I
        ):
            return ScopeDecision(surface, field, "constraint", st.value, evidence, True, None)
        if field == "constraint":
            return ScopeDecision(
                surface, field, None, st.value, evidence, False, "only_without_limit_scope"
            )

    if st == ScopeTest.DEFINITION_COPULAR:
        if re.search(
            r"\b(?:shall\s+mean|means|refers\s+to|is\s+defined|denotes)\b",
            clause_text,
            re.I,
        ):
            return ScopeDecision(surface, field, field, st.value, evidence, True, None)
        return ScopeDecision(
            surface, field, None, st.value, evidence, False, "no_copular_definition_structure"
        )

    if st in {ScopeTest.ACTOR_SUBJECT_HEAD, ScopeTest.ACTOR_BY_AGENT}:
        # syntactic check deferred to actor_action; here accept candidate for further filter
        return ScopeDecision(surface, field, field, st.value, evidence, True, None)

    # default: accept if field matches enum family loosely
    return ScopeDecision(surface, field, field, st.value, evidence, True, None)


def resolve_scope_fields_v9(
    clause_text: str,
    clause_start: int,
    source_text: str,
    lexicon: LexiconV2Runtime,
    tregex_obs: Mapping[str, Sequence[tuple[Any, Mapping[str, Any]]]] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[ScopeDecision], dict[str, int]]:
    """Return field spans, decisions, and stats. No legacy hardcode primary path."""
    result: dict[str, list[dict[str, Any]]] = {
        "condition": [],
        "constraint": [],
        "exception": [],
    }
    decisions: list[ScopeDecision] = []
    stats = {
        "lexicon_invocations": 0,
        "raw_matches": 0,
        "scope_accepted": 0,
        "scope_rejected": 0,
        "legacy_fallback": 0,
    }
    # entry-level scope_test from lexicon entries when available
    entry_scope: dict[tuple[str, str], str | None] = {}
    for field in ("condition", "constraint", "exception"):
        for e in lexicon.entries_by_field.get(field, ()):
            if e.activation:
                entry_scope[(field, e.surface.casefold())] = (
                    e.scope_test or e.syntactic_scope
                )

    for field in ("condition", "constraint", "exception"):
        stats["lexicon_invocations"] += 1
        for hit in match_field_markers(clause_text, field, lexicon):
            stats["raw_matches"] += 1
            st_raw = entry_scope.get((field, hit["surface"].casefold()))
            dec = apply_scope_test(
                field=field,
                surface=hit["surface"],
                scope_test_raw=st_raw,
                clause_text=clause_text,
                match_start=hit["start"],
                match_end=hit["end"],
            )
            decisions.append(dec)
            if not dec.accepted or not dec.accepted_field:
                stats["scope_rejected"] += 1
                continue
            stats["scope_accepted"] += 1
            abs_s = clause_start + hit["start"]
            abs_e = clause_start + hit["end"]
            # light expand
            e = abs_e
            while e < clause_start + len(clause_text) and e - abs_s < 90:
                ch = source_text[e] if e < len(source_text) else "."
                if ch in ".;\n":
                    break
                e += 1
            frag = source_text[abs_s:e].strip()
            if not frag:
                continue
            target = dec.accepted_field
            if target not in result:
                continue
            # prevent dual condition+exception same unless span
            if target in {"condition", "exception"}:
                rival = "exception" if target == "condition" else "condition"
                result[rival] = [
                    sp
                    for sp in result[rival]
                    if not (sp["start"] < abs_s + len(frag) and abs_s < sp["end"])
                ]
            result[target].append(
                {
                    "text": frag,
                    "start": abs_s,
                    "end": abs_s + len(frag),
                    "normalized": " ".join(frag.casefold().split()),
                    "source": "lexicon_v2_scope_accepted",
                    "marker_surface": hit["surface"],
                }
            )
    # dedupe per field shortest
    for field in result:
        kept: list[dict[str, Any]] = []
        for sp in sorted(result[field], key=lambda s: (s["start"], s["end"] - s["start"])):
            if any(not (sp["end"] <= k["start"] or sp["start"] >= k["end"]) for k in kept):
                continue
            if sp["end"] - sp["start"] > 160:
                continue
            kept.append(sp)
        result[field] = kept[:4]
    return result, decisions, stats

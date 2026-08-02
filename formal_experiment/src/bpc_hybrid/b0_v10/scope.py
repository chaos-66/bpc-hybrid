"""Typed scope resolution for v10: real constraint taxonomy + Tregex-first spans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from bpc_hybrid.b0_v10.span_safety import (
    BoundaryWarning,
    boundary_warning_requires_drop,
    safe_window_end,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime, match_field_markers


class ScopeType(str, Enum):
    TEMPORAL_LIMIT = "temporal_limit"
    QUANTITATIVE_COMPARATOR = "quantitative_comparator"
    DURATION_LIMIT = "duration_limit"
    LEGAL_REFERENCE = "legal_reference"
    PURPOSE_SCOPE = "purpose_scope"
    MANNER_SCOPE = "manner_scope"
    EXCLUSIVITY_SCOPE = "exclusivity_scope"
    DEFINITION_REFERENCE = "definition_reference"
    APPLICABILITY_CONDITION = "applicability_condition"
    EXCEPTION_CARVEOUT = "exception_carveout"
    CONDITION_SUBORDINATOR = "condition_subordinator"


class ScopeTestError(ValueError):
    pass


# surface/keyword -> typed scope (not everything is exclusivity!)
_SURFACE_SCOPE: list[tuple[re.Pattern[str], ScopeType]] = [
    (re.compile(r"^(?:only|solely|exclusively)$", re.I), ScopeType.EXCLUSIVITY_SCOPE),
    (re.compile(r"^(?:within|before|after|until|prior\s+to|no\s+later\s+than|no\s+earlier\s+than|during|throughout)$", re.I), ScopeType.TEMPORAL_LIMIT),
    (re.compile(r"^(?:for\s+a\s+period|for\s+the\s+duration|lasting)$", re.I), ScopeType.DURATION_LIMIT),
    (re.compile(r"^(?:at\s+least|at\s+most|no\s+more(?:\s+than)?|no\s+less(?:\s+than)?|not\s+to\s+exceed|exceeds|minimum|maximum|exactly|up\s+to)$", re.I), ScopeType.QUANTITATIVE_COMPARATOR),
    (re.compile(r"^(?:pursuant\s+to|under\s+section|in\s+accordance\s+with|as\s+defined\s+in|within\s+the\s+meaning|under|according\s+to)$", re.I), ScopeType.LEGAL_REFERENCE),
    (re.compile(r"^(?:for\s+the\s+purpose(?:s)?\s+of|for\s+purposes\s+of)$", re.I), ScopeType.PURPOSE_SCOPE),
    (re.compile(r"^(?:by\s+means\s+of|by\s+way\s+of|in\s+writing|electronically)$", re.I), ScopeType.MANNER_SCOPE),
    (re.compile(r"^(?:as\s+defined\s+in|within\s+the\s+meaning)$", re.I), ScopeType.DEFINITION_REFERENCE),
    (re.compile(r"^(?:subject\s+to|provided\s+that|insofar\s+as|to\s+the\s+extent)$", re.I), ScopeType.APPLICABILITY_CONDITION),
    (re.compile(r"^(?:unless|except|excluding|notwithstanding|other\s+than|apart\s+from|shall\s+not\s+apply)$", re.I), ScopeType.EXCEPTION_CARVEOUT),
    (re.compile(r"^(?:if|when|whenever|where|once|in\s+case)$", re.I), ScopeType.CONDITION_SUBORDINATOR),
]

# legacy broken label from v2 lexicon — reclassify by surface
_LEGACY_ONLY_LABEL = "performance_limit_only"


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    marker_surface: str
    requested_field: str
    accepted_field: str | None
    scope_type: str
    evidence: dict[str, Any]
    accepted: bool
    rejection_reason: str | None
    source: str  # tregex|lexicon


def classify_surface_scope(surface: str, requested_field: str) -> ScopeType:
    s = surface.strip()
    for pat, st in _SURFACE_SCOPE:
        if pat.match(s):
            return st
    # field defaults
    if requested_field == "exception":
        return ScopeType.EXCEPTION_CARVEOUT
    if requested_field == "condition":
        return ScopeType.CONDITION_SUBORDINATOR
    if requested_field == "constraint":
        # unknown constraint marker: quantitative/temporal-ish default legal_reference if section-like
        if re.search(r"section|paragraph|item", s, re.I):
            return ScopeType.LEGAL_REFERENCE
        return ScopeType.TEMPORAL_LIMIT
    raise ScopeTestError(f"cannot classify scope for surface={surface!r} field={requested_field}")


def apply_typed_scope(
    *,
    field: str,
    surface: str,
    scope_hint: str | None,
    clause_text: str,
    match_start: int,
    match_end: int,
    source: str,
) -> ScopeDecision:
    # Ignore broken lexicon scope_test=performance_limit_only unless surface is exclusivity
    hint = (scope_hint or "").strip()
    if hint == _LEGACY_ONLY_LABEL:
        hint = None
    if hint and hint in {e.value for e in ScopeType}:
        st = ScopeType(hint)
    else:
        st = classify_surface_scope(surface, field)

    evidence = {
        "match_start": match_start,
        "match_end": match_end,
        "scope_type": st.value,
        "surface": surface,
    }
    scf = surface.casefold()

    # exclusivity only for only/solely/exclusively
    if st == ScopeType.EXCLUSIVITY_SCOPE:
        if scf not in {"only", "solely", "exclusively"}:
            return ScopeDecision(surface, field, None, st.value, evidence, False, "exclusivity_requires_only_surface", source)
        if field != "constraint":
            return ScopeDecision(surface, field, None, st.value, evidence, False, "exclusivity_not_constraint_field", source)
        # require limit-like continuation
        tail = clause_text[match_end : match_end + 50]
        if not re.search(r"\b(?:if|when|for|to|within|after|before|under|pursuant)\b", tail, re.I):
            return ScopeDecision(surface, field, None, st.value, evidence, False, "only_without_limit_scope", source)
        return ScopeDecision(surface, field, "constraint", st.value, evidence, True, None, source)

    if st in {ScopeType.TEMPORAL_LIMIT, ScopeType.DURATION_LIMIT, ScopeType.QUANTITATIVE_COMPARATOR,
              ScopeType.LEGAL_REFERENCE, ScopeType.PURPOSE_SCOPE, ScopeType.MANNER_SCOPE, ScopeType.DEFINITION_REFERENCE}:
        if field != "constraint":
            # allow if lexicon hit constraint field only
            if field == "condition" and st == ScopeType.APPLICABILITY_CONDITION:
                pass
            else:
                return ScopeDecision(surface, field, "constraint", st.value, evidence, True, None, source)
        return ScopeDecision(surface, field, "constraint", st.value, evidence, True, None, source)

    if st == ScopeType.APPLICABILITY_CONDITION:
        # subject to / provided that -> condition preferred
        accepted = "condition" if field in {"condition", "constraint"} else field
        if accepted not in {"condition", "constraint"}:
            return ScopeDecision(surface, field, None, st.value, evidence, False, "applicability_field", source)
        return ScopeDecision(surface, field, accepted, st.value, evidence, True, None, source)

    if st == ScopeType.EXCEPTION_CARVEOUT:
        # unless default exception; if clearly condition-like "unless and until" keep exception
        return ScopeDecision(surface, field, "exception", st.value, evidence, True, None, source)

    if st == ScopeType.CONDITION_SUBORDINATOR:
        return ScopeDecision(surface, field, "condition", st.value, evidence, True, None, source)

    raise ScopeTestError(f"unhandled scope type {st}")


def _expand_to_constituent_or_punct(
    source_text: str,
    start: int,
    end: int,
    clause_start: int,
    clause_end: int,
    max_len: int = 100,
) -> tuple[int, int, BoundaryWarning | None]:
    """Prefer punctuation-bounded expansion; no blind +90 always.

    B0-R1-A contract:

    * ``start`` is the left-clip (clipped to ``clause_start``).
    * ``end`` is the *original* match end (Tregex/lexicon observation).
      This is the contract the helper must preserve: ``new_end >=
      original end`` whenever possible. The helper will *extend past
      the cap* to honour the original match end, and it surfaces a
      ``required_evidence_exceeds_cap`` warning so the trade-off is
      observable.
    * Clause boundary (``;`` or ``.``) inside ``[start, cap)`` ends
      the slice at the **earliest** such boundary.
    * If the rightmost token/phrase boundary inside the cap is past
      the original match end, the helper still returns the rightmost
      boundary so the scope span covers as much of the cap as
      possible without ever truncating the original evidence.
    * When the cap is too small to even include the original match
      end, the helper extends past the cap to honour the original
      evidence and emits the ``required_evidence_exceeds_cap`` warning.

    The returned ``BoundaryWarning`` is surfaced to the caller so it
    can be recorded in the scope stats / decision evidence rather
    than being silently discarded.
    """
    original_match_end = min(end, clause_end)
    start = max(start, clause_start)
    e, warning = safe_window_end(
        source_text,
        start,
        clause_end,
        max_len=max_len,
        prefer_clause_boundary=True,
        required_end=original_match_end,
    )
    # safe_window_end never returns less than required_end; the cap
    # here is purely defensive in case the helper produced something
    # outside the clause.
    return start, min(e, clause_end), warning


def resolve_scope_fields_v10(
    *,
    clause_text: str,
    clause_start: int,
    source_text: str,
    lexicon: LexiconV2Runtime,
    tregex_obs: Mapping[str, Sequence[tuple[Any, Mapping[str, Any]]]] | None = None,
    sentence_tokens_for_tregex: Sequence[tuple[Any, Mapping[str, Any]]] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[ScopeDecision], dict[str, int]]:
    result: dict[str, list[dict[str, Any]]] = {
        "condition": [],
        "constraint": [],
        "exception": [],
    }
    decisions: list[ScopeDecision] = []
    stats = {
        "lexicon_invoked": 0,
        "lexicon_raw_matched": 0,
        "tregex_candidates": 0,
        "tregex_accepted": 0,
        "tregex_final_affected": 0,
        "scope_expand_warnings": 0,
        "scope_accepted": 0,
        "scope_rejected": 0,
        "final_affected_spans": 0,
        "legacy_broken_only_label_ignored": 0,
    }

    # 1) Tregex observations first (true constituent candidates)
    if tregex_obs:
        from bpc_hybrid.estg150_b0_development_v3 import _token_span

        for field in ("condition", "constraint", "exception"):
            for sent, obs in tregex_obs.get(field) or []:
                stats["tregex_candidates"] += 1
                try:
                    span = _token_span(source_text, sent, obs)
                except Exception:
                    continue
                if span["end"] <= clause_start or span["start"] >= clause_start + len(clause_text):
                    continue
                s = max(span["start"], clause_start)
                e = min(span["end"], clause_start + len(clause_text))
                if e <= s:
                    continue
                raw = source_text[s:e]
                frag = raw.strip()
                if not frag or len(frag) > 160:
                    continue
                # realign offsets after strip
                lead = len(raw) - len(raw.lstrip())
                trail = len(raw) - len(raw.rstrip())
                s2, e2 = s + lead, e - trail
                if source_text[s2:e2] != frag:
                    continue
                # accept tregex as high-precision for requested field
                stats["tregex_accepted"] += 1
                stats["tregex_final_affected"] += 1
                result[field].append(
                    {
                        "text": frag,
                        "start": s2,
                        "end": e2,
                        "normalized": " ".join(frag.casefold().split()),
                        "source": "tregex",
                        "pattern_field": field,
                    }
                )
                decisions.append(
                    ScopeDecision(
                        frag[:40],
                        field,
                        field,
                        "tregex_constituent",
                        {"start": s, "end": e},
                        True,
                        None,
                        "tregex",
                    )
                )

    # 2) Lexicon markers with typed scope
    entry_meta: dict[tuple[str, str], dict[str, Any]] = {}
    for field in ("condition", "constraint", "exception"):
        for e in lexicon.entries_by_field.get(field, ()):
            if e.activation:
                entry_meta[(field, e.surface.casefold())] = {
                    "scope_test": e.scope_test,
                    "syntactic_scope": e.syntactic_scope,
                }

    for field in ("condition", "constraint", "exception"):
        stats["lexicon_invoked"] += 1
        for hit in match_field_markers(clause_text, field, lexicon):
            stats["lexicon_raw_matched"] += 1
            meta = entry_meta.get((field, hit["surface"].casefold()), {})
            hint = meta.get("scope_test") or meta.get("syntactic_scope")
            if (meta.get("scope_test") or "") == _LEGACY_ONLY_LABEL:
                stats["legacy_broken_only_label_ignored"] += 1
                hint = None
            try:
                dec = apply_typed_scope(
                    field=field,
                    surface=hit["surface"],
                    scope_hint=hint,
                    clause_text=clause_text,
                    match_start=hit["start"],
                    match_end=hit["end"],
                    source="lexicon",
                )
            except ScopeTestError:
                stats["scope_rejected"] += 1
                continue
            if not dec.accepted or not dec.accepted_field:
                decisions.append(dec)
                stats["scope_rejected"] += 1
                continue
            abs_s = clause_start + hit["start"]
            abs_e = clause_start + hit["end"]
            abs_s, abs_e, expand_warning = _expand_to_constituent_or_punct(
                source_text, abs_s, abs_e, clause_start, clause_start + len(clause_text)
            )
            if expand_warning is not None:
                # Record the trade-off in the scope stats and on the
                # decision so the caller (and downstream manifests) can
                # see how often the cap was too small to include the
                # original evidence. We must never silently drop the
                # warning.
                kind = expand_warning.kind
                stats["scope_expand_warnings"] = (
                    stats.get("scope_expand_warnings", 0) + 1
                )
                key = f"scope_expand_warning_{kind}"
                stats[key] = stats.get(key, 0) + 1
                requires_drop = boundary_warning_requires_drop(expand_warning)
                decisions.append(
                    ScopeDecision(
                        hit["surface"],
                        field,
                        None if requires_drop else dec.accepted_field,
                        dec.scope_type,
                        {
                            "match_start": expand_warning.start,
                            "match_end": expand_warning.end,
                            "warning_kind": kind,
                            "warning_detail": expand_warning.detail,
                        },
                        not requires_drop,
                        f"scope_expand_{kind}" if requires_drop else None,
                        "lexicon_expand_warning",
                    )
                )
                if requires_drop:
                    stats["scope_rejected"] += 1
                    continue
            raw = source_text[abs_s:abs_e]
            frag = raw.strip()
            if not frag:
                stats["scope_rejected"] += 1
                decisions.append(
                    ScopeDecision(
                        hit["surface"], field, None, dec.scope_type,
                        {"match_start": abs_s, "match_end": abs_e},
                        False, "scope_expand_empty_span", "lexicon_expand_rejection",
                    )
                )
                continue
            lead = len(raw) - len(raw.lstrip())
            trail = len(raw) - len(raw.rstrip())
            abs_s, abs_e = abs_s + lead, abs_e - trail
            if source_text[abs_s:abs_e] != frag:
                stats["scope_rejected"] += 1
                decisions.append(
                    ScopeDecision(
                        hit["surface"], field, None, dec.scope_type,
                        {"match_start": abs_s, "match_end": abs_e},
                        False, "scope_expand_source_mismatch", "lexicon_expand_rejection",
                    )
                )
                continue
            decisions.append(dec)
            stats["scope_accepted"] += 1
            target = dec.accepted_field
            # prevent dual unless condition+exception overlap: exception wins for carveout
            if target == "exception":
                result["condition"] = [
                    sp
                    for sp in result["condition"]
                    if not (sp["start"] < abs_e and abs_s < sp["end"] and "unless" in sp["text"].casefold())
                ]
            result[target].append(
                {
                    "text": frag,
                    "start": abs_s,
                    "end": abs_e,
                    "normalized": " ".join(frag.casefold().split()),
                    "source": "lexicon_v2_typed_scope",
                    "marker_surface": hit["surface"],
                    "scope_type": dec.scope_type,
                }
            )

    # dedupe: prefer tregex over lexicon; then shortest sufficient
    for field in result:
        spans = result[field]
        spans = sorted(
            spans,
            key=lambda s: (
                0 if s.get("source") == "tregex" else 1,
                s["start"],
                s["end"] - s["start"],
            ),
        )
        kept: list[dict[str, Any]] = []
        for sp in spans:
            if sp["end"] - sp["start"] > 160:
                continue
            if any(not (sp["end"] <= k["start"] or sp["start"] >= k["end"]) for k in kept):
                continue
            kept.append(sp)
        result[field] = kept[:6]
        stats["final_affected_spans"] += len(result[field])

    return result, decisions, stats

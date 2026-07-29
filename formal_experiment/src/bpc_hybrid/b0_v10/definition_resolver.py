"""B2a definition modality disambiguation (single fixed rule set).

Does not change segmentation, scope, Tregex, lexicon files, actor/edge, or BERT.
Parent modality pipeline is v10-A; this module only rewrites the final label/route
when definition-related conditions fire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from bpc_hybrid.b0_v10.alignment import AlignmentResult, AlignmentStatus
from bpc_hybrid.b0_v10.modality import ModalityDecision, ModalityRoute, resolve_modality_v10
from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction

# Pre-registered once: minimum confidence for classifier-only definition acceptance.
# Source: S2.4 candidate-B test report is exploratory-only; use mid-high band
# below typical overconfident errors while above weak noise (fixed a priori).
CLASSIFIER_ONLY_DEFINITION_MIN_CONF = 0.55

_EN_STRONG_DEF = re.compile(
    r"\b(?:shall\s+mean|means|is\s+defined\s+as|are\s+defined\s+as|"
    r"refers\s+to|denotes|is\s+deemed|are\s+deemed|is\s+understood\s+as)\b",
    re.IGNORECASE,
)
_DE_DEF = re.compile(
    r"\b(?:bedeutet|bezeichnet|gilt\s+als|ist\s+definiert|sind\s+definiert)\b",
    re.IGNORECASE,
)
_EN_PROH = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|is\s+not\s+permitted|is\s+prohibited)\b",
    re.IGNORECASE,
)
_EN_PERM = re.compile(
    r"\b(?:\bmay\b|is\s+permitted\s+to|is\s+allowed\s+to)\b",
    re.IGNORECASE,
)
_EN_OBL = re.compile(
    r"\b(?:shall|must|is\s+required\s+to|is\s+obliged\s+to)\b",
    re.IGNORECASE,
)
_COPULAR_DEF_SYNTAX = re.compile(
    r"\b(?:shall\s+mean|means|is\s+defined|are\s+defined|refers\s+to|denotes|"
    r"is\s+deemed|is\s+the\s+(?:difference|sum|total|amount)|"
    r"are\s+the\s+(?:difference|sum))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class DefinitionEvidence:
    en_strong_def: bool
    de_def: bool
    en_proh: bool
    en_perm: bool
    en_obl_not_mean: bool
    copular_def_syntax: bool
    validated_align: bool


def collect_definition_evidence(
    english_clause: str,
    *,
    german_clause: str | None,
    alignment: AlignmentResult,
) -> DefinitionEvidence:
    en = english_clause or ""
    de = german_clause or ""
    strong = bool(_EN_STRONG_DEF.search(en))
    # shall/must as obligation only when not part of shall mean / definition structure
    obl = bool(_EN_OBL.search(en)) and not strong
    perm = bool(_EN_PERM.search(en)) and not bool(_EN_PROH.search(en))
    # bare "may" inside "may not" is prohibition handled separately
    return DefinitionEvidence(
        en_strong_def=strong,
        de_def=bool(_DE_DEF.search(de)),
        en_proh=bool(_EN_PROH.search(en)),
        en_perm=perm,
        en_obl_not_mean=obl,
        copular_def_syntax=bool(_COPULAR_DEF_SYNTAX.search(en)),
        validated_align=alignment.validated,
    )


def resolve_modality_b2a(
    *,
    english_clause: str,
    german_clause: str | None,
    alignment: AlignmentResult,
    clause_classifier: ModalityPrediction | None,
    record_classifier: ModalityPrediction,
    lexicon: LexiconV2Runtime,
) -> ModalityDecision:
    """v10 resolve then apply fixed definition priority rules."""
    base = resolve_modality_v10(
        english_clause=english_clause,
        alignment=alignment,
        clause_classifier=clause_classifier,
        record_classifier=record_classifier,
        lexicon=lexicon,
    )
    ev = collect_definition_evidence(
        english_clause, german_clause=german_clause, alignment=alignment
    )
    diag = {
        **base.diagnostic,
        "b2a_definition_evidence": {
            "en_strong_def": ev.en_strong_def,
            "de_def": ev.de_def,
            "en_proh": ev.en_proh,
            "en_perm": ev.en_perm,
            "en_obl_not_mean": ev.en_obl_not_mean,
            "copular_def_syntax": ev.copular_def_syntax,
            "validated_align": ev.validated_align,
            "classifier_only_min_conf": CLASSIFIER_ONLY_DEFINITION_MIN_CONF,
        },
        "b2a_parent_label": base.label,
        "b2a_parent_route": base.route.value,
    }

    # 1) strong English definition structure
    if ev.en_strong_def:
        return ModalityDecision(
            "definition",
            max(base.confidence, 0.72),
            ModalityRoute.DEFINITION_STRUCTURE,
            {**diag, "b2a_rule": "en_strong_definition_structure"},
            False,
        )

    # 2) validated alignment + German definition anchor
    if ev.validated_align and ev.de_def:
        return ModalityDecision(
            "definition",
            max(base.confidence, 0.68),
            ModalityRoute.DEFINITION_STRUCTURE,
            {**diag, "b2a_rule": "validated_align_german_definition_anchor"},
            False,
        )

    # 3) shall mean already covered by strong def; keep explicit note path
    # 4) clear non-definition markers must not be overridden by classifier-only definition
    if ev.en_proh:
        return ModalityDecision(
            "prohibition",
            max(base.confidence, 0.7),
            ModalityRoute.PROHIBITION_NEGATION,
            {**diag, "b2a_rule": "block_definition_clear_prohibition_marker"},
            False,
        )
    if ev.en_perm and not ev.en_strong_def:
        # permission marker beats classifier-only definition
        if base.label == "definition" or (
            clause_classifier is not None and clause_classifier.label == "definition"
        ):
            return ModalityDecision(
                "permission",
                max(base.confidence, 0.6),
                ModalityRoute.MARKER_PERMISSION,
                {**diag, "b2a_rule": "block_definition_clear_permission_marker"},
                False,
            )
    if ev.en_obl_not_mean and not ev.en_strong_def:
        if base.label == "definition" or (
            clause_classifier is not None and clause_classifier.label == "definition"
        ):
            return ModalityDecision(
                "obligation",
                max(base.confidence, 0.6),
                ModalityRoute.MARKER_OBLIGATION,
                {**diag, "b2a_rule": "block_definition_clear_obligation_marker"},
                False,
            )

    # 5) classifier-only definition: validated + copular + confidence
    clf_def = clause_classifier is not None and clause_classifier.label == "definition"
    if clf_def or base.label == "definition":
        conf = (
            clause_classifier.confidence
            if clause_classifier is not None and clause_classifier.label == "definition"
            else base.confidence
        )
        if (
            ev.validated_align
            and ev.copular_def_syntax
            and conf >= CLASSIFIER_ONLY_DEFINITION_MIN_CONF
            and not ev.en_proh
            and not ev.en_perm
            and not ev.en_obl_not_mean
        ):
            return ModalityDecision(
                "definition",
                conf,
                ModalityRoute.VALIDATED_ALIGNED_CLASSIFIER
                if base.uses_clause_classifier
                else ModalityRoute.DEFINITION_STRUCTURE,
                {**diag, "b2a_rule": "classifier_only_definition_strict"},
                True,
            )
        # reject loose classifier definition
        if base.label == "definition" and not ev.en_strong_def and not (ev.validated_align and ev.de_def):
            # fall back to non-definition: prefer clause classifier if non-def, else record
            if clause_classifier is not None and clause_classifier.label != "definition":
                route = (
                    ModalityRoute.VALIDATED_ALIGNED_CLASSIFIER
                    if alignment.validated
                    else ModalityRoute.HEURISTIC_ALIGNED_CLASSIFIER
                )
                return ModalityDecision(
                    clause_classifier.label,
                    clause_classifier.confidence,
                    route,
                    {**diag, "b2a_rule": "reject_loose_classifier_definition_use_clause_clf"},
                    True,
                )
            if record_classifier.label != "definition":
                return ModalityDecision(
                    record_classifier.label,
                    record_classifier.confidence,
                    ModalityRoute.RECORD_LEVEL_FALLBACK,
                    {**diag, "b2a_rule": "reject_loose_classifier_definition_use_record"},
                    False,
                )
            # both say definition but failed strict tests: keep heuristic obligation-safe? use record still
            return ModalityDecision(
                record_classifier.label,
                record_classifier.confidence,
                ModalityRoute.RECORD_LEVEL_FALLBACK,
                {**diag, "b2a_rule": "reject_loose_definition_record_even_if_def"},
                False,
            )

    # 6) default: parent decision
    return ModalityDecision(
        base.label,
        base.confidence,
        base.route,
        {**diag, "b2a_rule": "parent_unchanged"},
        base.uses_clause_classifier,
    )

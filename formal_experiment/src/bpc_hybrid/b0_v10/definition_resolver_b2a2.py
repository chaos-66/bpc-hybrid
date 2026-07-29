"""B2a2 definition-constrained clause-local decoding.

This version calls the unchanged v10-A parent decision first.  It preserves
the pre-registered B2a definition evidence/priority, but when a supported
clause's classifier definition is rejected it decodes only among obligation,
permission, and prohibition using that same clause's probability vector.
Record-level labels are never used in that branch.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping

from bpc_hybrid.b0_v10.alignment import AlignmentResult
from bpc_hybrid.b0_v10.clause_probability_adapter_b2a2 import (
    ClauseProbabilityAdapterError,
    validate_probability_mapping,
)
from bpc_hybrid.b0_v10.definition_resolver import (
    CLASSIFIER_ONLY_DEFINITION_MIN_CONF,
    collect_definition_evidence,
)
from bpc_hybrid.b0_v10.modality import ModalityDecision, ModalityRoute, resolve_modality_v10
from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction


class B2a2ModalityRoute(str, Enum):
    DEFINITION_REJECTED_CLAUSE_LOCAL_CONSTRAINED = (
        "definition_rejected_clause_local_constrained"
    )


def _decision(
    *,
    label: str,
    confidence: float,
    route: ModalityRoute | B2a2ModalityRoute,
    diagnostic: dict[str, Any],
    uses_clause_classifier: bool,
) -> ModalityDecision:
    return ModalityDecision(  # type: ignore[arg-type]
        label,
        confidence,
        route,
        diagnostic,
        uses_clause_classifier,
    )


def resolve_modality_b2a2(
    *,
    english_clause: str,
    german_clause: str | None,
    alignment: AlignmentResult,
    clause_classifier: ModalityPrediction | None,
    clause_probabilities: Mapping[str, Any] | None,
    record_classifier: ModalityPrediction,
    lexicon: LexiconV2Runtime,
) -> ModalityDecision:
    """Apply the single pre-registered B2a2 decoding rule."""

    base = resolve_modality_v10(
        english_clause=english_clause,
        alignment=alignment,
        clause_classifier=clause_classifier,
        record_classifier=record_classifier,
        lexicon=lexicon,
    )
    evidence = collect_definition_evidence(
        english_clause,
        german_clause=german_clause,
        alignment=alignment,
    )
    diagnostic = {
        **base.diagnostic,
        "b2a2_parent_label": base.label,
        "b2a2_parent_route": base.route.value,
        "b2a2_definition_evidence": {
            "en_strong_def": evidence.en_strong_def,
            "de_def": evidence.de_def,
            "en_proh": evidence.en_proh,
            "en_perm": evidence.en_perm,
            "en_obl_not_mean": evidence.en_obl_not_mean,
            "copular_def_syntax": evidence.copular_def_syntax,
            "validated_align": evidence.validated_align,
            "classifier_only_min_conf": CLASSIFIER_ONLY_DEFINITION_MIN_CONF,
        },
        "uses_clause_classifier": base.uses_clause_classifier,
        "record_classifier_used_for_final_label": base.route
        == ModalityRoute.RECORD_LEVEL_FALLBACK,
    }

    # Unsupported clauses do not have a clause-local probability vector.  A
    # missing vector is therefore an explicit request to keep the parent
    # decision byte-for-byte at the decision-field level (label/route/confidence).
    if clause_classifier is None or clause_probabilities is None:
        return _decision(
            label=base.label,
            confidence=base.confidence,
            route=base.route,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "parent_unchanged_no_legal_clause_probabilities",
                "uses_clause_classifier": base.uses_clause_classifier,
                "record_classifier_used_for_final_label": base.route
                == ModalityRoute.RECORD_LEVEL_FALLBACK,
            },
            uses_clause_classifier=base.uses_clause_classifier,
        )

    # Once a vector is supplied it must be a complete legal four-class
    # distribution, even when the parent label ultimately remains unchanged.
    probabilities = validate_probability_mapping(clause_probabilities)

    # Existing strong definition evidence is preserved.
    if evidence.en_strong_def:
        return _decision(
            label="definition",
            confidence=max(base.confidence, 0.72),
            route=ModalityRoute.DEFINITION_STRUCTURE,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "en_strong_definition_structure",
                "uses_clause_classifier": False,
                "record_classifier_used_for_final_label": False,
            },
            uses_clause_classifier=False,
        )

    # Existing validated DE-EN + German definition anchor is preserved.
    if evidence.validated_align and evidence.de_def:
        return _decision(
            label="definition",
            confidence=max(base.confidence, 0.68),
            route=ModalityRoute.DEFINITION_STRUCTURE,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "validated_align_german_definition_anchor",
                "uses_clause_classifier": False,
                "record_classifier_used_for_final_label": False,
            },
            uses_clause_classifier=False,
        )

    # Existing explicit non-definition priorities remain unchanged.
    if evidence.en_proh:
        return _decision(
            label="prohibition",
            confidence=max(base.confidence, 0.7),
            route=ModalityRoute.PROHIBITION_NEGATION,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "preserve_explicit_prohibition",
                "uses_clause_classifier": False,
                "record_classifier_used_for_final_label": False,
            },
            uses_clause_classifier=False,
        )
    if evidence.en_perm and (
        base.label == "definition" or clause_classifier.label == "definition"
    ):
        return _decision(
            label="permission",
            confidence=max(base.confidence, 0.6),
            route=ModalityRoute.MARKER_PERMISSION,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "preserve_explicit_permission",
                "uses_clause_classifier": False,
                "record_classifier_used_for_final_label": False,
            },
            uses_clause_classifier=False,
        )
    if evidence.en_obl_not_mean and (
        base.label == "definition" or clause_classifier.label == "definition"
    ):
        return _decision(
            label="obligation",
            confidence=max(base.confidence, 0.6),
            route=ModalityRoute.MARKER_OBLIGATION,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "preserve_explicit_obligation",
                "uses_clause_classifier": False,
                "record_classifier_used_for_final_label": False,
            },
            uses_clause_classifier=False,
        )

    classifier_definition = (
        clause_classifier is not None and clause_classifier.label == "definition"
    )
    if classifier_definition:
        confidence = clause_classifier.confidence
        if (
            evidence.validated_align
            and evidence.copular_def_syntax
            and confidence >= CLASSIFIER_ONLY_DEFINITION_MIN_CONF
        ):
            route = (
                ModalityRoute.VALIDATED_ALIGNED_CLASSIFIER
                if alignment.validated
                else ModalityRoute.HEURISTIC_ALIGNED_CLASSIFIER
            )
            return _decision(
                label="definition",
                confidence=confidence,
                route=route,
                diagnostic={
                    **diagnostic,
                    "b2a2_rule": "classifier_only_definition_strict",
                    "uses_clause_classifier": True,
                    "record_classifier_used_for_final_label": False,
                },
                uses_clause_classifier=True,
            )

        # The sole B2a2 change: decode among non-definition classes from the
        # same clause vector.  There is no additional confidence threshold.
        non_definition_labels = ("obligation", "permission", "prohibition")
        label = max(non_definition_labels, key=lambda item: probabilities[item])
        return _decision(
            label=label,
            confidence=probabilities[label],
            route=B2a2ModalityRoute.DEFINITION_REJECTED_CLAUSE_LOCAL_CONSTRAINED,
            diagnostic={
                **diagnostic,
                "b2a2_rule": "definition_rejected_clause_local_constrained",
                "b2a2_clause_probabilities": probabilities,
                "b2a2_probability_input": "same_aligned_german_clause_text",
                "uses_clause_classifier": True,
                "record_classifier_used_for_final_label": False,
            },
            uses_clause_classifier=True,
        )

    # Unsupported clauses (or a missing legal vector) retain the exact v10-A
    # label, route, confidence, and uses-clause-classifier semantics.
    return _decision(
        label=base.label,
        confidence=base.confidence,
        route=base.route,
        diagnostic={
            **diagnostic,
            "b2a2_rule": "parent_unchanged",
            "uses_clause_classifier": base.uses_clause_classifier,
            "record_classifier_used_for_final_label": base.route
            == ModalityRoute.RECORD_LEVEL_FALLBACK,
        },
        uses_clause_classifier=base.uses_clause_classifier,
    )


__all__ = [
    "B2a2ModalityRoute",
    "ClauseProbabilityAdapterError",
    "resolve_modality_b2a2",
]

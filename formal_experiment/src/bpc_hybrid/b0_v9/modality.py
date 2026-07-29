"""Modality routing for v9: no placeholder classifier inputs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from bpc_hybrid.b0_v9.alignment import AlignmentResult, AlignmentStatus
from bpc_hybrid.sun_style.lexicon_v2_runtime import (
    LexiconV2Runtime,
    match_modality_from_lexicon,
)
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction


class ModalityRoute(str, Enum):
    ALIGNED_CLASSIFIER = "aligned_classifier"
    MARKER = "marker"
    RECORD_LEVEL_CLASSIFIER_FALLBACK = "record_level_classifier_fallback"
    ALIGNMENT_UNSUPPORTED_ABSTENTION = "alignment_unsupported_abstention_diagnostic"
    MARKER_UNSUPPORTED = "marker_unsupported"


@dataclass(frozen=True, slots=True)
class ModalityDecision:
    label: str
    confidence: float
    route: ModalityRoute
    diagnostic: dict[str, Any]
    uses_clause_classifier: bool
    abstention: bool

    def as_prediction(self) -> ModalityPrediction:
        return ModalityPrediction(self.label, self.confidence)


def resolve_modality_v9(
    *,
    english_clause: str,
    alignment: AlignmentResult,
    clause_classifier: ModalityPrediction | None,
    record_classifier: ModalityPrediction,
    lexicon: LexiconV2Runtime,
) -> ModalityDecision:
    marker_label, marker_surface = match_modality_from_lexicon(english_clause, lexicon)
    base_diag = {
        "alignment_status": alignment.status.value,
        "alignment_supported": alignment.supported,
        "marker_label": marker_label,
        "marker_surface": marker_surface,
        "clause_classifier_label": None if clause_classifier is None else clause_classifier.label,
        "clause_classifier_confidence": None
        if clause_classifier is None
        else clause_classifier.confidence,
        "record_classifier_label": record_classifier.label,
        "placeholder_classifier_input": False,
    }
    if alignment.supported and clause_classifier is not None:
        if marker_label == "definition":
            return ModalityDecision(
                "definition",
                max(clause_classifier.confidence, 0.62),
                ModalityRoute.MARKER,
                {**base_diag, "note": "definition_marker_priority"},
                True,
                False,
            )
        if marker_label == "prohibition":
            return ModalityDecision(
                "prohibition",
                max(clause_classifier.confidence, 0.65),
                ModalityRoute.MARKER,
                {**base_diag, "note": "prohibition_marker_priority"},
                True,
                False,
            )
        if marker_label in {"obligation", "permission"}:
            if clause_classifier.label == marker_label and clause_classifier.confidence >= 0.55:
                return ModalityDecision(
                    clause_classifier.label,
                    clause_classifier.confidence,
                    ModalityRoute.ALIGNED_CLASSIFIER,
                    {**base_diag, "note": "aligned_agree_marker"},
                    True,
                    False,
                )
            return ModalityDecision(
                marker_label,
                max(clause_classifier.confidence, 0.55),
                ModalityRoute.MARKER,
                {**base_diag, "note": "en_marker"},
                True,
                False,
            )
        return ModalityDecision(
            clause_classifier.label,
            clause_classifier.confidence,
            ModalityRoute.ALIGNED_CLASSIFIER,
            {**base_diag, "note": "aligned_classifier_no_marker"},
            True,
            False,
        )

    # unsupported alignment: never use clause classifier / placeholder
    if marker_label is not None:
        return ModalityDecision(
            marker_label,
            0.55 if marker_label != "prohibition" else 0.65,
            ModalityRoute.MARKER,
            {**base_diag, "note": "unsupported_alignment_marker_only"},
            False,
            False,
        )
    # schema-safe record-level fallback (honest naming)
    return ModalityDecision(
        record_classifier.label,
        record_classifier.confidence,
        ModalityRoute.RECORD_LEVEL_CLASSIFIER_FALLBACK,
        {
            **base_diag,
            "note": "alignment_unsupported_uses_record_level_not_clause_classifier",
            "abstention_diagnostic": True,
        },
        False,
        True,
    )

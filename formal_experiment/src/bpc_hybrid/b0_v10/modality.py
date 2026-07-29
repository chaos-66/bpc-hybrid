"""v10 modality routing with honest route names."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from bpc_hybrid.b0_v10.alignment import AlignmentResult, AlignmentStatus
from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime, match_modality_from_lexicon
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction


class ModalityRoute(str, Enum):
    DEFINITION_STRUCTURE = "definition_structure"
    PROHIBITION_NEGATION = "prohibition_negation"
    MARKER_PERMISSION = "marker_permission"
    MARKER_OBLIGATION = "marker_obligation"
    VALIDATED_ALIGNED_CLASSIFIER = "validated_aligned_classifier"
    HEURISTIC_ALIGNED_CLASSIFIER = "heuristic_aligned_classifier"
    RECORD_LEVEL_FALLBACK = "record_level_classifier_fallback"


@dataclass(frozen=True, slots=True)
class ModalityDecision:
    label: str
    confidence: float
    route: ModalityRoute
    diagnostic: dict[str, Any]
    uses_clause_classifier: bool

    def as_prediction(self) -> ModalityPrediction:
        return ModalityPrediction(self.label, self.confidence)


def resolve_modality_v10(
    *,
    english_clause: str,
    alignment: AlignmentResult,
    clause_classifier: ModalityPrediction | None,
    record_classifier: ModalityPrediction,
    lexicon: LexiconV2Runtime,
) -> ModalityDecision:
    marker, surface = match_modality_from_lexicon(english_clause, lexicon)
    diag: dict[str, Any] = {
        "alignment_status": alignment.status.value,
        "validated_alignment": alignment.validated,
        "marker_label": marker,
        "marker_surface": surface,
        "clause_classifier_label": None if clause_classifier is None else clause_classifier.label,
        "record_classifier_label": record_classifier.label,
        "placeholder_classifier_input": False,
    }
    # 1 definition structure
    if marker == "definition":
        return ModalityDecision("definition", 0.7, ModalityRoute.DEFINITION_STRUCTURE, diag, False)
    # 2 prohibition with negation
    if marker == "prohibition":
        return ModalityDecision("prohibition", 0.7, ModalityRoute.PROHIBITION_NEGATION, diag, False)
    # 3 permission
    if marker == "permission":
        return ModalityDecision("permission", 0.6, ModalityRoute.MARKER_PERMISSION, diag, False)
    # 4 obligation marker
    if marker == "obligation":
        return ModalityDecision("obligation", 0.6, ModalityRoute.MARKER_OBLIGATION, diag, False)

    # 5/6 classifier if alignment heuristic-supported and clause clf present
    if alignment.heuristic_supported and clause_classifier is not None:
        route = (
            ModalityRoute.VALIDATED_ALIGNED_CLASSIFIER
            if alignment.validated
            else ModalityRoute.HEURISTIC_ALIGNED_CLASSIFIER
        )
        return ModalityDecision(
            clause_classifier.label,
            clause_classifier.confidence,
            route,
            diag,
            True,
        )

    # 7 record-level fallback
    return ModalityDecision(
        record_classifier.label,
        record_classifier.confidence,
        ModalityRoute.RECORD_LEVEL_FALLBACK,
        {**diag, "note": "no_marker_and_no_clause_classifier"},
        False,
    )

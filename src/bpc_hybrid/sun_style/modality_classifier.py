"""Sun-style modality classifier (R15.0).

Implements a Sun-compatible classifier interface for modality
classification (obligation / prohibition / permission / definition).

**BERT status**: FALLBACK — no pre-trained BERT model available locally.
This module uses a deterministic rule-based classifier built on the
Sun-style marker lexicon.  The interface is compatible with what a
BERT-based classifier would expose, but the implementation is
purely rule-driven.

This is explicitly documented.  No claim of exact Sun BERT reproduction
is made.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from bpc_hybrid.sun_style.marker_lexicon import (
    MarkerLexicon,
    ModalityCategory,
)


class ModalityClass(str, Enum):
    """Modality classification labels (Sun-compatible)."""

    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    DEFINITION = "definition"


@dataclass
class ModalityResult:
    """Result of modality classification."""

    modality_class: ModalityClass
    marker_text: str
    marker_start: int
    marker_end: int
    confidence: float
    bert_used: bool = False  # Always False in fallback mode


class ModalityClassifier:
    """Sun-style modality classifier.

    Uses deterministic marker-lexicon rules as a fallback for the
    BERT + classification layer described in Sun et al.

    The public interface (``classify``) returns a ``ModalityResult``
    compatible with what a BERT-based classifier would produce.
    """

    def __init__(self, lexicon: MarkerLexicon | None = None) -> None:
        self._lexicon = lexicon or MarkerLexicon.from_default()
        self._bert_available = False  # No transformers/torch locally

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> ModalityResult | None:
        """Classify the modality of *text*.

        Returns ``None`` if no modality marker is found.
        """
        text_lower = text.lower()
        hit = self._lexicon.find_modality(text_lower)
        if hit is None:
            return None

        marker_text, category_str = hit
        idx = text_lower.find(marker_text)
        if idx == -1:
            return None

        category = ModalityClass(category_str)
        return ModalityResult(
            modality_class=category,
            marker_text=marker_text,
            marker_start=idx,
            marker_end=idx + len(marker_text),
            confidence=self._confidence(category, marker_text),
            bert_used=False,
        )

    def classify_or_default(self, text: str) -> ModalityResult:
        """Classify, returning ``OBLIGATION`` as default if no marker found."""
        result = self.classify(text)
        if result is not None:
            return result
        return ModalityResult(
            modality_class=ModalityClass.OBLIGATION,
            marker_text="",
            marker_start=-1,
            marker_end=-1,
            confidence=0.1,
            bert_used=False,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _confidence(category: ModalityClass, marker: str) -> float:
        """Heuristic confidence based on marker specificity."""
        # Longer markers tend to be more specific
        base = min(1.0, len(marker) / 15.0)
        if category in (ModalityClass.PROHIBITION, ModalityClass.OBLIGATION):
            base = max(base, 0.85)
        elif category == ModalityClass.DEFINITION:
            base = max(base, 0.6)
        return round(base, 4)

    @property
    def bert_status(self) -> str:
        """Return the BERT status string."""
        return "fallback" if not self._bert_available else "available"

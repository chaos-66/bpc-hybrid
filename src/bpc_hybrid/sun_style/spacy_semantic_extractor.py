"""spaCy-enhanced Sun-style semantic extractor.

Uses spaCy dependency parsing for more accurate syntactic analysis,
closer to Sun et al.'s original constituency/dependency tree approach.

Usage::

    >>> extractor = SpacySemanticExtractor()
    >>> result = extractor.extract("S001", "A controller shall notify.")
    >>> print(result.modality)  # "obligation"
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon
from bpc_hybrid.sun_style.modality_classifier import (
    ModalityClassifier,
)
from bpc_hybrid.sun_style.semantic_extractor import SemanticExtraction
from bpc_hybrid.sun_style.spacy_syntactic_rules import SpacySyntacticRuleEngine
from bpc_hybrid.sun_style.rule_record import SunAlignmentMeta


class SpacySemanticExtractor:
    """spaCy-enhanced Sun-style semantic extractor.

    Uses actual dependency parsing instead of marker-position heuristics.
    """

    def __init__(
        self,
        lexicon: MarkerLexicon | None = None,
        classifier: ModalityClassifier | None = None,
        rules: SpacySyntacticRuleEngine | None = None,
        model_name: str = "en_core_web_sm",
    ) -> None:
        self._lexicon = lexicon or MarkerLexicon.from_default()
        self._classifier = classifier or ModalityClassifier(self._lexicon)
        self._rules = rules or SpacySyntacticRuleEngine(self._lexicon, model_name)

    def extract(self, sample_id: str, text: str) -> SemanticExtraction:
        """Extract all six semantic fields using spaCy-enhanced rules."""
        # Step 1: Modality classification
        mod_result = self._classifier.classify(text)

        # Step 2: Build alignment metadata
        alignment = SunAlignmentMeta(
            bert_modality=self._classifier.bert_status,
            syntactic_tree_rules="spacy_dependency_parsing",
            domain_marker_lexicon=True,
            rule_template_extraction=True,
        )

        if mod_result is None:
            return SemanticExtraction(
                sample_id=sample_id,
                source_text=text,
                sun_alignment=alignment,
            )

        # Step 3: Extract all spans using spaCy rules
        spans = self._rules.extract_all(
            text,
            mod_result.marker_start,
            mod_result.marker_end,
        )

        # Step 4: Build extraction result
        extraction = SemanticExtraction(
            sample_id=sample_id,
            source_text=text,
            sun_alignment=alignment,
            modality=mod_result.modality_class.value,
            modality_span=(mod_result.marker_start, mod_result.marker_end)
            if mod_result.marker_start >= 0
            else None,
            actor=spans.actor.text if spans.actor else None,
            actor_span=(spans.actor.start, spans.actor.end)
            if spans.actor else None,
            action=spans.action.text if spans.action else None,
            action_span=(spans.action.start, spans.action.end)
            if spans.action else None,
            condition=spans.condition.text if spans.condition else None,
            condition_span=(spans.condition.start, spans.condition.end)
            if spans.condition else None,
            constraint=spans.constraint.text if spans.constraint else None,
            constraint_span=(spans.constraint.start, spans.constraint.end)
            if spans.constraint else None,
            exception=spans.exception.text if spans.exception else None,
            exception_span=(spans.exception.start, spans.exception.end)
            if spans.exception else None,
        )

        return extraction

    def extract_batch(self, samples: list[dict]) -> list[SemanticExtraction]:
        """Extract from a batch of samples."""
        return [
            self.extract(s["sample_id"], s["text"])
            for s in samples
        ]

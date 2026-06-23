"""Sun-style semantic extractor (R15.0).

Implements the full Sun-style extraction pipeline:

    input sentence
    -> modality classification
    -> parse/chunk/heuristic tree representation
    -> condition extraction
    -> constraint extraction
    -> exception extraction
    -> actor extraction
    -> action extraction after removing modality/condition/constraint/
       exception spans
    -> rule record

This is a deterministic, stdlib-only implementation.
No LLM, no API, no external parser.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon
from bpc_hybrid.sun_style.modality_classifier import (
    ModalityClass,
    ModalityClassifier,
    ModalityResult,
)
from bpc_hybrid.sun_style.syntactic_rules import (
    ExtractionSpans,
    SyntacticRuleEngine,
    TextSpan,
)
from bpc_hybrid.sun_style.rule_record import RuleRecord, SunAlignmentMeta


# ---------------------------------------------------------------------------
# Extraction result
# ---------------------------------------------------------------------------


@dataclass
class SemanticExtraction:
    """Result of extracting all six semantic fields from one sentence."""

    sample_id: str
    source_text: str
    method: str = "sun_style_rule_template"

    # Sun alignment metadata
    sun_alignment: SunAlignmentMeta = field(default_factory=SunAlignmentMeta)

    # Predicted fields
    modality: str | None = None
    actor: str | None = None
    action: str | None = None
    condition: str | None = None
    constraint: str | None = None
    exception: str | None = None

    # Span details (for provenance)
    modality_span: tuple[int, int] | None = None
    actor_span: tuple[int, int] | None = None
    action_span: tuple[int, int] | None = None
    condition_span: tuple[int, int] | None = None
    constraint_span: tuple[int, int] | None = None
    exception_span: tuple[int, int] | None = None

    def to_rule_record(self) -> RuleRecord:
        """Convert to a Sun-style rule record."""
        return RuleRecord(
            sample_id=self.sample_id,
            source_text=self.source_text,
            method=self.method,
            sun_alignment=self.sun_alignment,
            prediction_fields={
                "modality": {"value": self.modality or ""},
                "actor": {"value": self.actor or ""},
                "action": {"value": self.action or ""},
                "condition": {"value": self.condition or ""},
                "constraint": {"value": self.constraint or ""},
                "exception": {"value": self.exception or ""},
            },
        )

    def to_dict(self) -> dict:
        """Serialize to dict for JSONL output."""
        return {
            "sample_id": self.sample_id,
            "method": self.method,
            "sun_alignment": {
                "bert_modality": self.sun_alignment.bert_modality,
                "syntactic_tree_rules": self.sun_alignment.syntactic_tree_rules,
                "domain_marker_lexicon": self.sun_alignment.domain_marker_lexicon,
                "rule_template_extraction": self.sun_alignment.rule_template_extraction,
            },
            "prediction_fields": {
                "modality": {"value": self.modality or ""},
                "actor": {"value": self.actor or ""},
                "action": {"value": self.action or ""},
                "condition": {"value": self.condition or ""},
                "constraint": {"value": self.constraint or ""},
                "exception": {"value": self.exception or ""},
            },
        }


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class SemanticExtractor:
    """Sun-style semantic extractor for normative sentences.

    Usage::

        >>> extractor = SemanticExtractor()
        >>> result = extractor.extract("S001", "A controller shall notify.")
        >>> print(result.modality)  # "obligation"
    """

    def __init__(
        self,
        lexicon: MarkerLexicon | None = None,
        classifier: ModalityClassifier | None = None,
        rules: SyntacticRuleEngine | None = None,
    ) -> None:
        self._lexicon = lexicon or MarkerLexicon.from_default()
        self._classifier = classifier or ModalityClassifier(self._lexicon)
        self._rules = rules or SyntacticRuleEngine(self._lexicon)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, sample_id: str, text: str) -> SemanticExtraction:
        """Extract all six semantic fields from *text*.

        Implements the full Sun-style pipeline.
        """
        # Step 1: Modality classification
        mod_result = self._classifier.classify(text)

        # Step 2: Build sun_alignment metadata
        alignment = SunAlignmentMeta(
            bert_modality=self._classifier.bert_status,
            syntactic_tree_rules=(
                "approximated"  # No parser available
            ),
            domain_marker_lexicon=True,
            rule_template_extraction=True,
        )

        if mod_result is None:
            # No modality found — return empty extraction
            return SemanticExtraction(
                sample_id=sample_id,
                source_text=text,
                sun_alignment=alignment,
            )

        # Step 3: Extract all spans using syntactic rule engine
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
        """Extract from a batch of samples.

        Each sample dict must have ``sample_id`` and ``text`` keys.
        """
        results: list[SemanticExtraction] = []
        for sample in samples:
            sid = sample.get("sample_id", f"S{len(results):04d}")
            text = sample.get("text", sample.get("sentence", ""))
            results.append(self.extract(sid, text))
        return results

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def bert_status(self) -> str:
        return self._classifier.bert_status

    @property
    def parser_status(self) -> str:
        return "unavailable"

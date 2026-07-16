"""Sun-style semantic extractor (R15.0) \u2014 development heuristic.

Implements a **development heuristic** for Sun et al.'s Stage 2
regulatory document parsing. The current implementation uses:

  * Keyword-based modality markers (shall / must / may / ...) with a
    simple ``MarkerLexicon``.
  * spaCy-based dependency parsing for actor / action / condition /
    constraint / exception extraction.
  * A hand-rolled ``SyntacticRuleEngine`` for tree-pattern matching.

It does **not** contain:
  * A trained BERT-TextCNN modality classifier (only keyword
    fallback)
  * Stanford CoreNLP constituency parsing
  * Tregex / Tsurgeon tree patterns
  * The full Sun / Sleimi marker lexicon
  * The proper Sun-extraction-order constraint (modality \u2192 condition \u2192
    constraint \u2192 exception \u2192 action; actors last)

This file must NOT be advertised as a "Sun paper-faithful
reconstruction". It is a development heuristic that produces
``SemanticExtraction`` records close enough in shape to the target
schema to let the surrounding pipeline (ClauseAdapter,
Stage3Adapter) be exercised end-to-end.

The deterministic and offline nature is preserved: no LLM, no remote
API, no ``.env``, no API keys.
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
    method: str = "sun_paper_rule_template_reconstruction"

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
        """Convert to a Sun paper-aligned rule record."""
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
        payload = self.to_rule_record().to_dict()
        payload["spans"] = {
            "modality": self.modality_span,
            "actor": self.actor_span,
            "action": self.action_span,
            "condition": self.condition_span,
            "constraint": self.constraint_span,
            "exception": self.exception_span,
        }
        return payload


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


class SemanticExtractor:
    """Sun paper-aligned semantic extractor for normative sentences.

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

        This follows Sun's Stage 2 structure with local replacements for
        unavailable BERT and Tregex/Tsurgeon components.
        """
        # Step 1: Modality classification
        mod_result = self._classifier.classify(text)

        # Step 2: Build sun_alignment metadata
        alignment = SunAlignmentMeta(
            bert_modality=self._classifier.bert_status,
            syntactic_tree_rules=(
                "approximated"  # Stanford CoreNLP/Tregex unavailable locally.
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

"""bpc_hybrid package.

Prototype-level rule-first LLM-assisted hybrid framework for
design-time business process compliance assessment.

This package currently contains R1 scaffold + R2 core multi-clause schema
+ R3 rule-first extractor + R4 multi-clause splitter + R5 prototype evaluation
+ R6 mock fallback and normalization foundation.
"""

from bpc_hybrid.evaluator import (
    EvaluationError,
    EvaluationReport,
    FieldMetrics,
    evaluate_responses,
    load_gold_responses,
    load_jsonl,
    load_predicted_responses,
)
from bpc_hybrid.extractor import ExtractionError, RuleFirstExtractor, extract_rule_first
from bpc_hybrid.fallback import (
    DecisionReason,
    FallbackDecision,
    FallbackError,
    FallbackResult,
    MockLLMFallbackClient,
    extract_hybrid,
    should_trigger_fallback,
)
from bpc_hybrid.normalization import (
    NormalizationError,
    normalize_field_text,
    normalize_modality_text,
    repair_field_span,
    repair_response_spans,
)
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)
from bpc_hybrid.splitter import (
    ClauseSegment,
    RuleBasedClauseSplitter,
    SplitError,
    split_normative_clauses,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ClauseExtraction",
    "ClauseSegment",
    "DecisionReason",
    "EvaluationError",
    "EvaluationReport",
    "ExtractionError",
    "FallbackDecision",
    "FallbackError",
    "FallbackResult",
    "FieldMetrics",
    "FieldSpan",
    "MockLLMFallbackClient",
    "MultiClauseExtractionResponse",
    "NormalizationError",
    "RuleBasedClauseSplitter",
    "RuleFirstExtractor",
    "SchemaValidationError",
    "SplitError",
    "evaluate_responses",
    "extract_hybrid",
    "extract_rule_first",
    "load_gold_responses",
    "load_jsonl",
    "load_predicted_responses",
    "normalize_field_text",
    "normalize_modality_text",
    "repair_field_span",
    "repair_response_spans",
    "should_trigger_fallback",
    "split_normative_clauses",
]

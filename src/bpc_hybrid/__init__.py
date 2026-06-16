"""bpc_hybrid package.

Prototype-level rule-first LLM-assisted hybrid framework for
design-time business process compliance assessment.

This package currently contains R1 scaffold + R2 core multi-clause schema
+ R3 rule-first extractor + R4 multi-clause splitter + R5 prototype evaluation
+ R6 mock fallback and normalization foundation + R7 safe LLM adapter scaffold.
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
    FallbackRequest,
    FallbackResult,
    MockLLMFallbackClient,
    extract_hybrid,
    should_trigger_fallback,
)
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMFallbackAdapter,
    LLMRequest,
    LLMResponse,
    LLMTransport,
    MockLLMTransport,
    OpenAICompatibleRequestBuilder,
    make_schema_valid_mock_response_json,
    parse_llm_json_response,
    validate_llm_extraction_response,
)
from bpc_hybrid.llm_config import (
    LLMConfig,
    LLMConfigError,
    LLMProvider,
    redact_mapping,
    redact_secret,
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
    "FallbackRequest",
    "FallbackResult",
    "FieldMetrics",
    "FieldSpan",
    "LLMClientError",
    "LLMConfig",
    "LLMConfigError",
    "LLMFallbackAdapter",
    "LLMProvider",
    "LLMRequest",
    "LLMResponse",
    "LLMTransport",
    "MockLLMFallbackClient",
    "MockLLMTransport",
    "MultiClauseExtractionResponse",
    "NormalizationError",
    "OpenAICompatibleRequestBuilder",
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
    "make_schema_valid_mock_response_json",
    "normalize_field_text",
    "normalize_modality_text",
    "parse_llm_json_response",
    "redact_mapping",
    "redact_secret",
    "repair_field_span",
    "repair_response_spans",
    "should_trigger_fallback",
    "split_normative_clauses",
    "validate_llm_extraction_response",
]

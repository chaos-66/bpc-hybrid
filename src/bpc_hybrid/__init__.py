"""bpc_hybrid package.

Prototype-level rule-first LLM-assisted hybrid framework for
design-time business process compliance assessment.

This package currently contains R1 scaffold + R2 core multi-clause schema
+ R3 rule-first extractor.
"""

from bpc_hybrid.extractor import ExtractionError, RuleFirstExtractor, extract_rule_first
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ClauseExtraction",
    "ExtractionError",
    "FieldSpan",
    "MultiClauseExtractionResponse",
    "RuleFirstExtractor",
    "SchemaValidationError",
    "extract_rule_first",
]

"""bpc_hybrid package.

Prototype-level rule-first LLM-assisted hybrid framework for
design-time business process compliance assessment.

This package currently contains R1 scaffold + R2 core multi-clause schema
+ R3 rule-first extractor + R4 multi-clause splitter.
"""

from bpc_hybrid.extractor import ExtractionError, RuleFirstExtractor, extract_rule_first
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
    "ExtractionError",
    "FieldSpan",
    "MultiClauseExtractionResponse",
    "RuleBasedClauseSplitter",
    "RuleFirstExtractor",
    "SchemaValidationError",
    "SplitError",
    "extract_rule_first",
    "split_normative_clauses",
]

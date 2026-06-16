"""bpc_hybrid package.

Prototype-level rule-first LLM-assisted hybrid framework for
design-time business process compliance assessment.

This package currently contains R1 scaffold + R2 core multi-clause schema.
"""

from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)

__version__ = "0.1.0"

__all__ = [
    "ClauseExtraction",
    "FieldSpan",
    "MultiClauseExtractionResponse",
    "SchemaValidationError",
]

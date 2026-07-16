"""Sun-compatible Stage 2 output schema and adapters.

This module provides:
- SunRuleRecord: Sun-compatible rule record schema
- ClauseAdapter: converts 6-field extraction to Sun Clause-compatible format
- SimilarityEngine: spaCy vector similarity matching (like Pair.py)
- ParagraphAdapter: aggregates sentences into paragraphs
- Stage3Adapter: full adapter for Stage 3 compliance checking
"""

from bpc_hybrid.sun_compat.schema import (
    SunRuleRecord,
    ActorActionMap,
    OrderRelation,
    ObligationRecord,
)
from bpc_hybrid.sun_compat.clause_adapter import ClauseAdapter
from bpc_hybrid.sun_compat.similarity_engine import SimilarityEngine
from bpc_hybrid.sun_compat.stage3_adapter import Stage3Adapter

__all__ = [
    "SunRuleRecord",
    "ActorActionMap",
    "OrderRelation",
    "ObligationRecord",
    "ClauseAdapter",
    "SimilarityEngine",
    "Stage3Adapter",
]

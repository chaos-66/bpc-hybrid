"""Sun-style semantic extraction package (R15.0).

Implements a local Sun-aligned rule-template extraction pipeline for
normative texts.  All components use only the Python standard library.

Key limitations (documented, not hidden):
- BERT modality classifier: interface-compatible deterministic fallback
  (no pre-trained model available locally)
- Syntactic parsing: approximated by marker-span heuristics
  (no constituency/dependency parser available locally)
- Dependency parsing: subject-like positional heuristics
  (no dependency parser available locally)

This is a best-effort local Sun-style approximation.
It does NOT constitute exact Sun et al. reproduction.
"""

from bpc_hybrid.sun_style.marker_lexicon import (
    ActorCategory,
    ConditionCategory,
    ConstraintCategory,
    ExceptionCategory,
    MarkerLexicon,
    ModalityCategory,
)
from bpc_hybrid.sun_style.modality_classifier import (
    ModalityClass,
    ModalityClassifier,
)
from bpc_hybrid.sun_style.syntactic_rules import (
    RuleApplication,
    SyntacticRuleEngine,
)
from bpc_hybrid.sun_style.semantic_extractor import (
    SemanticExtraction,
    SemanticExtractor,
)
from bpc_hybrid.sun_style.rule_record import (
    RuleRecord,
    SunAlignmentMeta,
)
from bpc_hybrid.sun_style.bpmn_semantics import (
    BPMNActivity,
    BPMNEvent,
    BPMNGateway,
    BPMNLane,
    BPMNSequenceFlow,
    BPMNSemanticParser,
    ProcessSemanticRecord,
)
from bpc_hybrid.sun_style.violation_detection import (
    Violation,
    ViolationDetector,
    ViolationReport,
    ViolationType,
)

__all__ = [
    "MarkerLexicon",
    "ModalityCategory",
    "ConditionCategory",
    "ConstraintCategory",
    "ExceptionCategory",
    "ActorCategory",
    "ModalityClass",
    "ModalityClassifier",
    "SyntacticRuleEngine",
    "RuleApplication",
    "SemanticExtractor",
    "SemanticExtraction",
    "RuleRecord",
    "SunAlignmentMeta",
    "BPMNSemanticParser",
    "ProcessSemanticRecord",
    "BPMNActivity",
    "BPMNEvent",
    "BPMNGateway",
    "BPMNLane",
    "BPMNSequenceFlow",
    "ViolationDetector",
    "ViolationReport",
    "Violation",
    "ViolationType",
]

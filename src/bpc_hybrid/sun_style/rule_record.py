"""Sun-style rule record (R15.0).

Defines the structured rule record data model for Sun-style
semantic extraction outputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Sun alignment metadata
# ---------------------------------------------------------------------------


@dataclass
class SunAlignmentMeta:
    """Metadata tracking alignment with Sun et al. method components."""

    bert_modality: str = "fallback"
    syntactic_tree_rules: str = "approximated"
    domain_marker_lexicon: bool = True
    rule_template_extraction: bool = True

    def to_dict(self) -> dict:
        return {
            "bert_modality": self.bert_modality,
            "syntactic_tree_rules": self.syntactic_tree_rules,
            "domain_marker_lexicon": self.domain_marker_lexicon,
            "rule_template_extraction": self.rule_template_extraction,
        }


# ---------------------------------------------------------------------------
# Rule record
# ---------------------------------------------------------------------------


@dataclass
class RuleRecord:
    """A single rule record extracted from a normative sentence.

    Corresponds to Sun et al.'s rule record with six semantic fields.
    """

    sample_id: str
    source_text: str
    method: str = "sun_style_rule_template"
    sun_alignment: SunAlignmentMeta = field(default_factory=SunAlignmentMeta)

    prediction_fields: dict[str, dict[str, str]] = field(default_factory=lambda: {
        "modality": {"value": ""},
        "actor": {"value": ""},
        "action": {"value": ""},
        "condition": {"value": ""},
        "constraint": {"value": ""},
        "exception": {"value": ""},
    })

    def to_dict(self) -> dict:
        """Serialize to dict matching the Sun-style output format."""
        return {
            "sample_id": self.sample_id,
            "method": self.method,
            "sun_alignment": self.sun_alignment.to_dict(),
            "prediction_fields": self.prediction_fields,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

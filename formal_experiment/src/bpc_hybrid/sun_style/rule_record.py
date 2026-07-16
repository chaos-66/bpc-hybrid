"""Sun paper-aligned rule record (R15.0).

Sun et al. define each regulatory rule record as
``r = (tr, Ar, Pr, Cr, Or, Er, Ur, fr)``.  The six concept fields used
for concept-level evaluation are kept as ``prediction_fields`` because
the existing evaluation scripts consume that representation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


_RULE_TYPE_BY_MODALITY = {
    "obligation": "Obligation",
    "prohibition": "Prohibition",
    "permission": "Permission",
    "definition": "Definition",
}


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
    exact_sun_reproduction: bool = False

    def to_dict(self) -> dict:
        return {
            "bert_modality": self.bert_modality,
            "syntactic_tree_rules": self.syntactic_tree_rules,
            "domain_marker_lexicon": self.domain_marker_lexicon,
            "rule_template_extraction": self.rule_template_extraction,
            "exact_sun_reproduction": self.exact_sun_reproduction,
        }


# ---------------------------------------------------------------------------
# Sun paper tuple
# ---------------------------------------------------------------------------


@dataclass
class SunPaperRuleTuple:
    """Sun et al. rule record tuple.

    Fields follow Definition 3 in the paper:
    - ``tr``: rule type
    - ``Ar``: actions
    - ``Pr``: actors
    - ``Cr``: conditions
    - ``Or``: constraints
    - ``Er``: exceptions
    - ``Ur``: sequential action relations
    - ``fr``: actor-to-action partial function
    """

    tr: str
    Ar: list[str] = field(default_factory=list)
    Pr: list[str] = field(default_factory=list)
    Cr: list[str] = field(default_factory=list)
    Or: list[str] = field(default_factory=list)
    Er: list[str] = field(default_factory=list)
    Ur: list[dict[str, str]] = field(default_factory=list)
    fr: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tr": self.tr,
            "Ar": self.Ar,
            "Pr": self.Pr,
            "Cr": self.Cr,
            "Or": self.Or,
            "Er": self.Er,
            "Ur": self.Ur,
            "fr": self.fr,
        }


# ---------------------------------------------------------------------------
# Rule record
# ---------------------------------------------------------------------------


@dataclass
class RuleRecord:
    """A single rule record extracted from a normative sentence.

    ``prediction_fields`` stores the six semantic concepts evaluated in
    Sun's Table 8.  ``to_sun_paper_tuple`` converts those fields to the
    Definition 3 tuple used by the compliance checking phase.
    """

    sample_id: str
    source_text: str
    method: str = "sun_paper_rule_template_reconstruction"
    sun_alignment: SunAlignmentMeta = field(default_factory=SunAlignmentMeta)

    prediction_fields: dict[str, dict[str, str]] = field(default_factory=lambda: {
        "modality": {"value": ""},
        "actor": {"value": ""},
        "action": {"value": ""},
        "condition": {"value": ""},
        "constraint": {"value": ""},
        "exception": {"value": ""},
    })

    def to_sun_paper_tuple(self) -> SunPaperRuleTuple:
        """Convert six concept fields to Sun's formal rule tuple."""
        modality = self._field_value("modality").lower()
        actor = self._field_value("actor")
        action = self._field_value("action")
        condition = self._field_value("condition")
        constraint = self._field_value("constraint")
        exception = self._field_value("exception")

        return SunPaperRuleTuple(
            tr=_RULE_TYPE_BY_MODALITY.get(modality, ""),
            Ar=self._list_if_value(action),
            Pr=self._list_if_value(actor),
            Cr=self._list_if_value(condition),
            Or=self._list_if_value(constraint),
            Er=self._list_if_value(exception),
            Ur=[],
            fr=self._actor_action_function(actor, action),
        )

    def to_dict(self) -> dict:
        """Serialize to the formal experiment output format."""
        return {
            "sample_id": self.sample_id,
            "source_text": self.source_text,
            "method": self.method,
            "sun_alignment": self.sun_alignment.to_dict(),
            "prediction_fields": self.prediction_fields,
            "sun_rule_record": self.to_sun_paper_tuple().to_dict(),
            "sun_rule_record_definition": "r=(tr,Ar,Pr,Cr,Or,Er,Ur,fr)",
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def _field_value(self, name: str) -> str:
        value = self.prediction_fields.get(name, {}).get("value", "")
        return str(value or "").strip()

    @staticmethod
    def _list_if_value(value: str) -> list[str]:
        cleaned = str(value or "").strip()
        return [cleaned] if cleaned else []

    @staticmethod
    def _actor_action_function(actor: str, action: str) -> list[dict[str, str]]:
        if actor and action:
            return [{"actor": actor, "action": action}]
        return []

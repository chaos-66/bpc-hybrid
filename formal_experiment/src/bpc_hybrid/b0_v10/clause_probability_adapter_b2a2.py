"""Read-only four-class probability adapter for B2a2 clause inference.

The locked parent inference API intentionally exposes only the top-1 label and
confidence.  B2a2 needs the complete probability vector for the *same clause
text* so that a rejected definition can be decoded among the three non-
definition labels.  This adapter does not mutate or replace the parent model,
tokenizer, checkpoint, label order, or training configuration.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import torch

from bpc_hybrid.sun_style.bert_textcnn import LABELS
from bpc_hybrid.sun_style.sun_b0 import LockedBertTextCNNInference, SunB0CompositionError


EXPECTED_LABELS = ("definition", "obligation", "permission", "prohibition")


class ClauseProbabilityAdapterError(ValueError):
    """Raised when clause-local probability inference cannot be trusted."""


@dataclass(frozen=True, slots=True)
class ClauseProbabilityVector:
    """Validated four-class probabilities produced from one real clause text."""

    text: str
    probabilities: Mapping[str, float]
    top_label: str
    top_confidence: float

    def non_definition_argmax(self) -> tuple[str, float]:
        candidates = ("obligation", "permission", "prohibition")
        label = max(candidates, key=lambda item: self.probabilities[item])
        return label, float(self.probabilities[label])


def _validate_texts(texts: Sequence[str]) -> list[str]:
    if not texts:
        raise ClauseProbabilityAdapterError("clause probability inference requires texts")
    checked: list[str] = []
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            raise ClauseProbabilityAdapterError("clause probability input must be real non-empty text")
        if text.strip() == ".":
            raise ClauseProbabilityAdapterError("placeholder classifier input is forbidden")
        checked.append(text)
    return checked


def _validate_probability_row(text: str, values: Sequence[float]) -> ClauseProbabilityVector:
    if tuple(LABELS) != EXPECTED_LABELS:
        raise ClauseProbabilityAdapterError("locked classifier label order changed")
    if len(values) != len(EXPECTED_LABELS):
        raise ClauseProbabilityAdapterError("four-class probability vector is incomplete")
    if any(not math.isfinite(value) or value < 0.0 or value > 1.0 for value in values):
        raise ClauseProbabilityAdapterError("probability vector contains an invalid value")
    total = math.fsum(values)
    if not math.isclose(total, 1.0, rel_tol=1e-6, abs_tol=1e-6):
        raise ClauseProbabilityAdapterError("probability vector does not sum to one")
    probabilities = dict(zip(EXPECTED_LABELS, (float(value) for value in values), strict=True))
    top_label = max(EXPECTED_LABELS, key=lambda label: probabilities[label])
    return ClauseProbabilityVector(
        text=text,
        probabilities=probabilities,
        top_label=top_label,
        top_confidence=probabilities[top_label],
    )


@torch.no_grad()
def predict_clause_probability_vectors(
    inference: LockedBertTextCNNInference,
    texts: Sequence[str],
) -> list[ClauseProbabilityVector]:
    """Return one validated probability vector per supplied clause text.

    The batching/tokenization/model call is the same read-only path as the
    parent ``LockedBertTextCNNInference.predict`` method; only the complete
    softmax row is retained instead of discarding the non-argmax classes.
    """

    checked = _validate_texts(texts)
    try:
        encoded = inference.tokenizer(
            checked,
            padding=True,
            truncation=True,
            max_length=inference.max_length,
            return_tensors="pt",
        )
        logits = inference.model(
            input_ids=encoded["input_ids"].to(inference.device),
            attention_mask=encoded["attention_mask"].to(inference.device),
        )
        probabilities = torch.softmax(logits, dim=1).cpu()
    except (KeyError, RuntimeError, TypeError, ValueError, SunB0CompositionError) as exc:
        raise ClauseProbabilityAdapterError("locked clause probability inference failed") from exc
    if probabilities.ndim != 2 or probabilities.shape != (len(checked), len(EXPECTED_LABELS)):
        raise ClauseProbabilityAdapterError("classifier returned an unexpected probability shape")
    return [
        _validate_probability_row(text, [float(value.item()) for value in row])
        for text, row in zip(checked, probabilities, strict=True)
    ]


def validate_probability_mapping(probabilities: Mapping[str, Any]) -> dict[str, float]:
    """Validate an externally carried vector before constrained decoding."""

    if not isinstance(probabilities, Mapping) or set(probabilities) != set(EXPECTED_LABELS):
        raise ClauseProbabilityAdapterError("probability mapping must contain exactly four labels")
    try:
        values = [float(probabilities[label]) for label in EXPECTED_LABELS]
    except (TypeError, ValueError) as exc:
        raise ClauseProbabilityAdapterError("probability mapping values must be numeric") from exc
    return dict(_validate_probability_row("validated_mapping", values).probabilities)

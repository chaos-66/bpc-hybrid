"""Core multi-clause schema for rule-first LLM-assisted extraction.

This module defines the data structures used to represent regulatory clause
extractions at design time.  All types use only the Python standard library
(dataclasses, typing, json).

Schema version: 0.1.0
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields as dc_fields
from typing import Any


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SchemaValidationError(ValueError):
    """Raised when a schema object fails validation."""


# ---------------------------------------------------------------------------
# FieldSpan
# ---------------------------------------------------------------------------

_FIELDSPAN_KEYS = frozenset({"text", "span_start", "span_end", "confidence"})


@dataclass
class FieldSpan:
    """A span of text with positional offsets and a confidence score.

    Parameters
    ----------
    text : str
        The extracted text.  Must be a non-empty string.
    span_start : int
        Start character offset (0-indexed).  Must be >= 0.
    span_end : int
        End character offset (0-indexed, exclusive).  Must be >= span_start.
    confidence : float
        Confidence in [0.0, 1.0].
    """

    text: str
    span_start: int
    span_end: int
    confidence: float

    def validate(self, *, source_text: str | None = None) -> None:
        """Raise :class:`SchemaValidationError` if this span is invalid.

        Optionally cross-checks against *source_text* when provided.
        """
        # -- text -----------------------------------------------------------
        if not isinstance(self.text, str) or self.text == "":
            raise SchemaValidationError(
                f"FieldSpan.text must be a non-empty str, got {self.text!r}"
            )

        # -- offsets --------------------------------------------------------
        for name, val in (("span_start", self.span_start), ("span_end", self.span_end)):
            if not isinstance(val, int):
                raise SchemaValidationError(
                    f"FieldSpan.{name} must be int, got {type(val).__name__}"
                )
        if self.span_start < 0:
            raise SchemaValidationError(
                f"FieldSpan.span_start must be >= 0, got {self.span_start}"
            )
        if self.span_end < self.span_start:
            raise SchemaValidationError(
                f"FieldSpan.span_end ({self.span_end}) must be >= "
                f"span_start ({self.span_start})"
            )

        # -- confidence -----------------------------------------------------
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise SchemaValidationError(
                f"FieldSpan.confidence must be float, got {type(self.confidence).__name__}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise SchemaValidationError(
                f"FieldSpan.confidence must be in [0.0, 1.0], got {self.confidence}"
            )

        # -- optional source_text cross-check -------------------------------
        if source_text is not None:
            if self.span_end > len(source_text):
                raise SchemaValidationError(
                    f"FieldSpan.span_end ({self.span_end}) exceeds "
                    f"source_text length ({len(source_text)})"
                )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "text": self.text,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FieldSpan:
        """Construct a :class:`FieldSpan` from a dict.

        Extra keys are silently ignored.
        """
        return cls(
            text=d["text"],
            span_start=d["span_start"],
            span_end=d["span_end"],
            confidence=d["confidence"],
        )


# ---------------------------------------------------------------------------
# ClauseExtraction
# ---------------------------------------------------------------------------

# Allowed top-level keys for ClauseExtraction.  Unknown keys must raise.
_CLAUSE_KEYS = frozenset({
    "clause_id",
    "source_id",
    "source_text",
    "clause_text",
    "clause_span_start",
    "clause_span_end",
    "modality",
    "actor",
    "action",
    "condition",
    "constraint",
    "exception",
    "confidence",
})

_SEMANTIC_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")


def _coerce_fieldspan(value: object) -> FieldSpan | None:
    """Coerce *value* to ``FieldSpan | None``.

    ``None`` is kept as-is; a ``dict`` is converted via ``FieldSpan.from_dict()``.
    """
    if value is None:
        return None
    if isinstance(value, FieldSpan):
        return value
    if isinstance(value, dict):
        return FieldSpan.from_dict(value)
    raise SchemaValidationError(
        f"Expected FieldSpan, dict, or None, got {type(value).__name__}"
    )


@dataclass
class ClauseExtraction:
    """A single regulatory clause with six optional semantic field spans.

    Parameters
    ----------
    clause_id : str
        Unique identifier for this clause.
    source_id : str | None
        Identifier of the source document (optional).
    source_text : str
        The full source text the clause was extracted from.
    clause_text : str
        The sub-string of *source_text* corresponding to this clause.
    clause_span_start : int
        Start offset of *clause_text* in *source_text*.
    clause_span_end : int
        End offset of *clause_text* in *source_text* (exclusive).
    modality : FieldSpan | None
    actor : FieldSpan | None
    action : FieldSpan | None
    condition : FieldSpan | None
    constraint : FieldSpan | None
    exception : FieldSpan | None
    confidence : float
        Overall extraction confidence in [0.0, 1.0].
    """

    clause_id: str
    source_id: str | None
    source_text: str
    clause_text: str
    clause_span_start: int
    clause_span_end: int
    modality: FieldSpan | None = None
    actor: FieldSpan | None = None
    action: FieldSpan | None = None
    condition: FieldSpan | None = None
    constraint: FieldSpan | None = None
    exception: FieldSpan | None = None
    confidence: float = 1.0

    def validate(self) -> None:
        """Raise :class:`SchemaValidationError` if this clause is invalid."""
        # -- clause_id -------------------------------------------------------
        if not isinstance(self.clause_id, str) or self.clause_id == "":
            raise SchemaValidationError(
                f"ClauseExtraction.clause_id must be a non-empty str, "
                f"got {self.clause_id!r}"
            )

        # -- source_text ----------------------------------------------------
        if not isinstance(self.source_text, str) or self.source_text == "":
            raise SchemaValidationError(
                "ClauseExtraction.source_text must be a non-empty str"
            )

        # -- clause_text ----------------------------------------------------
        if not isinstance(self.clause_text, str) or self.clause_text == "":
            raise SchemaValidationError(
                "ClauseExtraction.clause_text must be a non-empty str"
            )

        # -- clause offsets -------------------------------------------------
        for name in ("clause_span_start", "clause_span_end"):
            val = getattr(self, name)
            if not isinstance(val, int):
                raise SchemaValidationError(
                    f"ClauseExtraction.{name} must be int, got {type(val).__name__}"
                )
        if self.clause_span_start < 0:
            raise SchemaValidationError(
                f"ClauseExtraction.clause_span_start must be >= 0, "
                f"got {self.clause_span_start}"
            )
        if self.clause_span_end < self.clause_span_start:
            raise SchemaValidationError(
                f"ClauseExtraction.clause_span_end ({self.clause_span_end}) "
                f"must be >= clause_span_start ({self.clause_span_start})"
            )

        # -- confidence -----------------------------------------------------
        if not isinstance(self.confidence, (int, float)) or isinstance(self.confidence, bool):
            raise SchemaValidationError(
                f"ClauseExtraction.confidence must be float, "
                f"got {type(self.confidence).__name__}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise SchemaValidationError(
                f"ClauseExtraction.confidence must be in [0.0, 1.0], "
                f"got {self.confidence}"
            )

        # -- six semantic fields (may be FieldSpan or None) -----------------
        for field_name in _SEMANTIC_FIELDS:
            val = getattr(self, field_name)
            if val is not None:
                if not isinstance(val, FieldSpan):
                    raise SchemaValidationError(
                        f"ClauseExtraction.{field_name} must be FieldSpan or None, "
                        f"got {type(val).__name__}"
                    )
                val.validate(source_text=self.source_text)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "clause_id": self.clause_id,
            "source_id": self.source_id,
            "source_text": self.source_text,
            "clause_text": self.clause_text,
            "clause_span_start": self.clause_span_start,
            "clause_span_end": self.clause_span_end,
            "modality": self.modality.to_dict() if self.modality is not None else None,
            "actor": self.actor.to_dict() if self.actor is not None else None,
            "action": self.action.to_dict() if self.action is not None else None,
            "condition": self.condition.to_dict() if self.condition is not None else None,
            "constraint": self.constraint.to_dict() if self.constraint is not None else None,
            "exception": self.exception.to_dict() if self.exception is not None else None,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ClauseExtraction:
        """Construct a :class:`ClauseExtraction` from a dict.

        Raises :class:`SchemaValidationError` when unknown keys are present
        or required keys are missing.
        """
        # -- unknown key check -----------------------------------------------
        unknown = set(d.keys()) - _CLAUSE_KEYS
        if unknown:
            raise SchemaValidationError(
                f"Unknown keys in ClauseExtraction dict: {sorted(unknown)}"
            )

        # -- required key check ----------------------------------------------
        for key in _CLAUSE_KEYS:
            if key not in d:
                raise SchemaValidationError(
                    f"Missing required key '{key}' in ClauseExtraction dict"
                )

        return cls(
            clause_id=d["clause_id"],
            source_id=d["source_id"],
            source_text=d["source_text"],
            clause_text=d["clause_text"],
            clause_span_start=d["clause_span_start"],
            clause_span_end=d["clause_span_end"],
            modality=_coerce_fieldspan(d["modality"]),
            actor=_coerce_fieldspan(d["actor"]),
            action=_coerce_fieldspan(d["action"]),
            condition=_coerce_fieldspan(d["condition"]),
            constraint=_coerce_fieldspan(d["constraint"]),
            exception=_coerce_fieldspan(d["exception"]),
            confidence=d["confidence"],
        )


# ---------------------------------------------------------------------------
# MultiClauseExtractionResponse
# ---------------------------------------------------------------------------

_MULTI_CLAUSE_KEYS = frozenset({
    "schema_version",
    "source_id",
    "source_text",
    "clauses",
})


@dataclass
class MultiClauseExtractionResponse:
    """Top-level response wrapping multiple :class:`ClauseExtraction` objects.

    Parameters
    ----------
    schema_version : str
        Version of the extraction schema.  Default ``"0.1.0"``.
    source_id : str
        Identifier of the regulatory source document.
    source_text : str
        The full regulatory text that was processed.
    clauses : list[ClauseExtraction]
        One or more extracted clauses (may be empty).
    """

    schema_version: str = "0.1.0"
    source_id: str = ""
    source_text: str = ""
    clauses: list[ClauseExtraction] = field(default_factory=list)

    def validate(self) -> None:
        """Raise :class:`SchemaValidationError` if the response is invalid."""
        if not isinstance(self.schema_version, str) or self.schema_version == "":
            raise SchemaValidationError(
                "MultiClauseExtractionResponse.schema_version must be a non-empty str"
            )
        if not isinstance(self.source_id, str) or self.source_id == "":
            raise SchemaValidationError(
                "MultiClauseExtractionResponse.source_id must be a non-empty str"
            )
        if not isinstance(self.source_text, str) or self.source_text == "":
            raise SchemaValidationError(
                "MultiClauseExtractionResponse.source_text must be a non-empty str"
            )
        if not isinstance(self.clauses, list):
            raise SchemaValidationError(
                f"MultiClauseExtractionResponse.clauses must be a list, "
                f"got {type(self.clauses).__name__}"
            )
        for i, clause in enumerate(self.clauses):
            if not isinstance(clause, ClauseExtraction):
                raise SchemaValidationError(
                    f"MultiClauseExtractionResponse.clauses[{i}] must be "
                    f"ClauseExtraction, got {type(clause).__name__}"
                )
            clause.validate()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "schema_version": self.schema_version,
            "source_id": self.source_id,
            "source_text": self.source_text,
            "clauses": [c.to_dict() for c in self.clauses],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MultiClauseExtractionResponse:
        """Construct a :class:`MultiClauseExtractionResponse` from a dict."""
        unknown = set(d.keys()) - _MULTI_CLAUSE_KEYS
        if unknown:
            raise SchemaValidationError(
                f"Unknown keys in MultiClauseExtractionResponse dict: {sorted(unknown)}"
            )

        clauses_raw = d.get("clauses", [])
        if not isinstance(clauses_raw, list):
            raise SchemaValidationError(
                f"MultiClauseExtractionResponse.clauses must be a list, "
                f"got {type(clauses_raw).__name__}"
            )

        clauses: list[ClauseExtraction] = []
        for i, c in enumerate(clauses_raw):
            if not isinstance(c, dict):
                raise SchemaValidationError(
                    f"MultiClauseExtractionResponse.clauses[{i}] must be a dict, "
                    f"got {type(c).__name__}"
                )
            try:
                clauses.append(ClauseExtraction.from_dict(c))
            except SchemaValidationError as exc:
                raise SchemaValidationError(
                    f"MultiClauseExtractionResponse.clauses[{i}]: {exc}"
                ) from exc

        return cls(
            schema_version=d.get("schema_version", "0.1.0"),
            source_id=d.get("source_id", ""),
            source_text=d.get("source_text", ""),
            clauses=clauses,
        )

    def to_json(self, *, indent: int | None = 2, **kwargs: Any) -> str:
        """Serialize to a JSON string.

        All extra keyword arguments are forwarded to :func:`json.dumps`.
        """
        return json.dumps(self.to_dict(), indent=indent, **kwargs)

    @classmethod
    def from_json(cls, s: str) -> MultiClauseExtractionResponse:
        """Deserialize from a JSON string."""
        try:
            d = json.loads(s)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(f"Invalid JSON: {exc}") from exc
        return cls.from_dict(d)

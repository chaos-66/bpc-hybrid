"""Deterministic normalization and span-repair helpers (R6).

Pure-Python, no LLM, no network — only deterministic text cleaning
and exact-match span correction.
"""

from __future__ import annotations

import re
from typing import Any

from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class NormalizationError(ValueError):
    """Raised when normalization/repair cannot complete deterministically."""


# ---------------------------------------------------------------------------
# Text-level normalisation
# ---------------------------------------------------------------------------

_WHITESPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"^[.,;:!?'\"]+|[.,;:!?'\"]+$")


def normalize_field_text(
    text: str,
    *,
    lowercase: bool = False,
    strip_punctuation: bool = True,
) -> str:
    """Deterministically clean a field text string.

    Parameters
    ----------
    text : str
        Raw field text.
    lowercase : bool
        If *True*, fold to lower-case (default *False* — case is
        preserved by default).
    strip_punctuation : bool
        If *True*, strip leading/trailing punctuation (default *True*).
    """
    result = _WHITESPACE_RE.sub(" ", text).strip()
    if lowercase:
        result = result.lower()
    if strip_punctuation:
        # Remove leading and trailing punctuation while preserving
        # internal punctuation.
        result = _PUNCT_RE.sub("", result)
    return result


# Canonical modality forms.
_MODALITY_CANONICAL: dict[str, str] = {
    "may": "may",
    "shall": "shall",
    "shall not": "shall not",
    "must": "must",
    "must not": "must not",
    "no person shall": "shall not",
    "no person must": "must not",
}


def normalize_modality_text(text: str) -> str:
    """Return the *canonical* modality label for *text*.

    >>> normalize_modality_text("  Shall   ")
    'shall'

    >>> normalize_modality_text("No person shall")
    'shall not'

    If no canonical form matches, the cleaned text is returned as-is.
    """
    cleaned = normalize_field_text(text, lowercase=True, strip_punctuation=True)
    return _MODALITY_CANONICAL.get(cleaned, cleaned)


# ---------------------------------------------------------------------------
# Span repair
# ---------------------------------------------------------------------------

def repair_field_span(
    source_text: str,
    field: FieldSpan,
) -> FieldSpan:
    """Repair *field*'s span offsets against *source_text* if possible.

    Rules (applied in order):

    1. If the span already points to the correct text in *source_text*,
       return *field* unchanged.
    2. If ``field.text`` occurs exactly once in *source_text*, fix the
       span to match that occurrence.
    3. If ``field.text`` does **not** appear in *source_text*, raise
       :class:`NormalizationError`.
    4. If ``field.text`` appears multiple times and cannot be uniquely
       resolved, raise :class:`NormalizationError`.

    This is a **deterministic** repair — no fuzzy matching, no LLM.
    """
    current = source_text[field.span_start:field.span_end]
    if current == field.text:
        return field  # already correct

    # Try exact unique match in the whole source_text.
    pos = _find_unique(source_text, field.text)
    if pos is not None:
        return FieldSpan(
            text=field.text,
            span_start=pos,
            span_end=pos + len(field.text),
            confidence=field.confidence,
        )

    # Cannot repair.
    count = source_text.count(field.text)
    if count == 0:
        raise NormalizationError(
            f"FieldSpan.text {field.text!r} not found in source_text "
            f"{source_text[:80]!r}..."
        )
    else:
        raise NormalizationError(
            f"FieldSpan.text {field.text!r} occurs {count} times in "
            f"source_text — cannot uniquely repair"
        )


def _find_unique(source_text: str, needle: str) -> int | None:
    """Return the start offset of *needle* in *source_text* if it
    occurs exactly once; otherwise return ``None``."""
    idx = source_text.find(needle)
    if idx == -1:
        return None
    if source_text.find(needle, idx + 1) == -1:
        return idx
    return None


_SEMANTIC_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")


def repair_response_spans(
    response: MultiClauseExtractionResponse,
) -> MultiClauseExtractionResponse:
    """Repair all field spans in *response*, then validate.

    Returns a new :class:`MultiClauseExtractionResponse` with repaired
    spans (the original is not mutated).

    Raises :class:`NormalizationError` if any span cannot be repaired.
    """
    repaired_clauses: list[ClauseExtraction] = []
    for clause in response.clauses:
        repaired_fields: dict[str, FieldSpan | None] = {}
        for fname in _SEMANTIC_FIELDS:
            fs = getattr(clause, fname)
            if fs is None:
                repaired_fields[fname] = None
                continue
            repaired_fields[fname] = repair_field_span(clause.source_text, fs)

        repaired_clauses.append(
            ClauseExtraction(
                clause_id=clause.clause_id,
                source_id=clause.source_id,
                source_text=clause.source_text,
                clause_text=clause.clause_text,
                clause_span_start=clause.clause_span_start,
                clause_span_end=clause.clause_span_end,
                modality=repaired_fields["modality"],
                actor=repaired_fields["actor"],
                action=repaired_fields["action"],
                condition=repaired_fields["condition"],
                constraint=repaired_fields["constraint"],
                exception=repaired_fields["exception"],
                confidence=clause.confidence,
            )
        )

    result = MultiClauseExtractionResponse(
        schema_version=response.schema_version,
        source_id=response.source_id,
        source_text=response.source_text,
        clauses=repaired_clauses,
    )

    # Validate the repaired response.
    try:
        result.validate()
    except SchemaValidationError as exc:
        raise NormalizationError(
            f"Repaired response failed validation: {exc}"
        ) from exc

    return result

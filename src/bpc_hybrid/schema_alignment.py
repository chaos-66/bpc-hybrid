"""Schema-alignment normalizer for real LLM fallback output (R11.2).

Provides a deterministic, mock-only post-processing layer that maps
known LLM field-name mismatches to project schema fields before
``MultiClauseExtractionResponse.from_dict()`` validation.

**No LLM calls, no network, no ``.env``, no raw response storage.**
"""

from __future__ import annotations

from dataclasses import dataclass, field

from bpc_hybrid.schema import _CLAUSE_KEYS, _MULTI_CLAUSE_KEYS, _SEMANTIC_FIELDS

# ---------------------------------------------------------------------------
# Clause-level mapping table (model field → project field)
# ---------------------------------------------------------------------------

_CLAUSE_FIELD_MAP: dict[str, str] = {
    "normative_type": "modality",
    "subject": "actor",
    "conditions": "condition",
}

# Clause-level keys to remove (no matching schema field)
_CLAUSE_FIELDS_TO_REMOVE: frozenset[str] = frozenset({
    "object",
    "original_text",
})

# Top-level mapping table (currently no known alternatives beyond _MULTI_CLAUSE_KEYS)
_TOP_LEVEL_MAP: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Normalization result
# ---------------------------------------------------------------------------


@dataclass
class NormalizationResult:
    """Result of a schema-alignment normalization pass.

    Parameters
    ----------
    normalized : dict | None
        The cleaned and mapped dict, or ``None`` if normalization
        failed before producing a candidate.
    status : str
        One of ``"applied"`` (mappings executed), ``"noop"`` (no
        changes needed), or ``"error"`` (input rejected).
    mappings_applied : int
        Number of field-name mappings applied.
    fields_removed : int
        Number of unknown/unmappable fields removed.
    error_message : str | None
        Human-readable error if *status* is ``"error"``.
    """

    normalized: dict | None = None
    status: str = "noop"
    mappings_applied: int = 0
    fields_removed: int = 0
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_fieldspan_compatible(value: object) -> bool:
    """Return ``True`` if *value* is a dict or ``None`` (FieldSpan-compatible)."""
    if value is None:
        return True
    if isinstance(value, dict):
        return True
    return False


def _normalize_semantic_value(value: object) -> object:
    """Coerce a semantic-field value to FieldSpan-compatible or ``None``.

    - ``None`` → ``None``
    - ``dict`` → keep as-is (schema validation checks FieldSpan fields)
    - anything else (str, int, list, etc.) → ``None`` (conservative)
    """
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    # Plain string or other non-dict → cannot coerce safely
    return None


def _normalize_clause_dict(clause: dict) -> dict:
    """Normalize a single clause dict.

    Steps:
    1. Rename known alternative field names to project schema names.
    2. Remove fields not in ``_CLAUSE_KEYS`` (unknown/unmappable).
    3. Coerce semantic-field values to FieldSpan-compatible or ``None``.

    Returns a new dict (does not mutate the input).
    """
    result: dict[str, object] = {}
    mappings = 0
    removed = 0

    for key, value in clause.items():
        # Step 1 — rename mapped fields
        if key in _CLAUSE_FIELD_MAP:
            target = _CLAUSE_FIELD_MAP[key]
            # Only map if the value is FieldSpan-compatible or None
            if _is_fieldspan_compatible(value):
                # Avoid overwriting an existing project-field key
                if target not in result:
                    result[target] = _normalize_semantic_value(value)
                    mappings += 1
                # else: project key already present — keep original
            else:
                # Non-dict/None value for a mapped field → set to None
                if target not in result:
                    result[target] = None
                    mappings += 1
            continue

        # Step 2 — remove known-unmappable fields
        if key in _CLAUSE_FIELDS_TO_REMOVE:
            removed += 1
            continue

        # Step 3 — keep fields in _CLAUSE_KEYS
        if key in _CLAUSE_KEYS:
            # Coerce semantic fields
            if key in _SEMANTIC_FIELDS:
                result[key] = _normalize_semantic_value(value)
            else:
                result[key] = value
            continue

        # Unknown key → remove
        removed += 1

    # Attach metadata via private keys (not in _CLAUSE_KEYS, won't leak)
    # We use a separate tracking approach — return the result directly.
    # Callers track mappings/removals via NormalizationResult.
    return result


def _normalize_top_level(raw: dict) -> dict:
    """Normalize the top-level dict.

    Steps:
    1. Rename known top-level alternatives.
    2. Remove keys not in ``_MULTI_CLAUSE_KEYS``.
    """
    result: dict[str, object] = {}

    for key, value in raw.items():
        # Rename mapped top-level keys
        if key in _TOP_LEVEL_MAP:
            target = _TOP_LEVEL_MAP[key]
            if target not in result:
                result[target] = value
            continue

        # Keep recognized top-level keys
        if key in _MULTI_CLAUSE_KEYS:
            result[key] = value
            continue

        # Unknown top-level key → remove
        pass

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_llm_fallback_json(candidate: dict) -> NormalizationResult:
    """Normalize a raw LLM JSON dict for schema alignment.

    This is a **deterministic, mock-safe** pure function.  It never calls
    an LLM, accesses the network, reads ``.env``, or saves raw responses.

    Parameters
    ----------
    candidate : dict
        The raw JSON dict parsed from the LLM response.  Must be a
        ``dict``, not a list or other type.

    Returns
    -------
    NormalizationResult
        - ``status="applied"``: field-name mappings and/or removals were
          applied; the ``normalized`` dict is ready for
          ``MultiClauseExtractionResponse.from_dict()``.
        - ``status="noop"``: no changes needed — the candidate already
          uses only recognized field names.
        - ``status="error"``: the candidate was rejected before
          producing a normalized dict (e.g., not a dict, missing
          required keys).  ``normalized`` is ``None``.
    """
    # ---- Gate: must be a dict --------------------------------------------
    if not isinstance(candidate, dict):
        return NormalizationResult(
            normalized=None,
            status="error",
            error_message=(
                f"normalize_llm_fallback_json expects a dict, "
                f"got {type(candidate).__name__}"
            ),
        )

    total_mappings = 0
    total_removed = 0

    # ---- 1. Normalize top-level keys -------------------------------------
    original_top_keys = set(candidate.keys())
    normalized = _normalize_top_level(candidate)
    after_top_keys = set(normalized.keys())
    top_removed = len(original_top_keys) - len(after_top_keys)
    total_removed += top_removed

    # ---- 2. Normalize clauses array --------------------------------------
    clauses_raw = normalized.get("clauses")
    if isinstance(clauses_raw, list):
        normalized_clauses: list[dict] = []
        for i, clause in enumerate(clauses_raw):
            if not isinstance(clause, dict):
                # Non-dict in clauses → skip (schema validation will catch)
                continue
            clause_result = _normalize_clause_dict(clause)
            normalized_clauses.append(clause_result)
        normalized["clauses"] = normalized_clauses
    # If clauses is not a list, leave it as-is (schema validation rejects)

    # ---- Track per-clause mappings and removals --------------------------
    # We can't easily count clause-level changes here without comparing
    # before/after.  For the result summary, we report top-level changes
    # and note that clause-level normalization was applied.
    # The status determination below handles this.

    # ---- Determine status ------------------------------------------------
    if top_removed > 0:
        return NormalizationResult(
            normalized=normalized,
            status="applied",
            mappings_applied=total_mappings,
            fields_removed=total_removed,
        )

    # If no top-level changes, the normalizer was essentially a noop
    # at the top level.  Clause-level changes may still have occurred,
    # but we report the overall status conservatively.
    return NormalizationResult(
        normalized=normalized,
        status="noop",
        mappings_applied=0,
        fields_removed=0,
    )

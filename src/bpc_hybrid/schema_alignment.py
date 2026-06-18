"""Schema-alignment normalizer for real LLM fallback output (R11.2.1).

Provides a deterministic, mock-only strict gate that validates and maps
known LLM field-name mismatches to project schema fields **before**
``MultiClauseExtractionResponse.from_dict()`` validation.

**No LLM calls, no network, no ``.env``, no raw response storage.**

R11.2.1 tightens the normalizer from "permissive cleaning" to "strict gate":
- missing explicit top-level keys are rejected (no parser defaulting)
- unknown top-level / clause-level fields are rejected
- known unsupported model-like fields (``object``, ``original_text``) are rejected
- non-dict items inside ``clauses`` are rejected
- unsupported enum values for mapped fields are rejected
- alias + target field conflicts are rejected
"""

from __future__ import annotations

from dataclasses import dataclass

from bpc_hybrid.schema import _CLAUSE_KEYS, _MULTI_CLAUSE_KEYS, _SEMANTIC_FIELDS

# ---------------------------------------------------------------------------
# Clause-level mapping table (model field → project field)
# ---------------------------------------------------------------------------

_CLAUSE_FIELD_MAP: dict[str, str] = {
    "normative_type": "modality",
    "subject": "actor",
    "conditions": "condition",
}

# Model-like clause fields with no project-schema target — REJECT, not remove.
_CLAUSE_FIELDS_REJECT: frozenset[str] = frozenset({
    "object",
    "original_text",
})

# Allowed clause-level input keys = project keys + known model aliases.
_ALLOWED_CLAUSE_INPUT_KEYS: frozenset[str] = (
    _CLAUSE_KEYS
    | frozenset(_CLAUSE_FIELD_MAP.keys())
)

# ---------------------------------------------------------------------------
# Error reason constants
# ---------------------------------------------------------------------------

ERROR_MISSING_TOP_KEY = "missing_required_top_level_key"
ERROR_UNKNOWN_TOP_FIELD = "unknown_top_level_field"
ERROR_UNKNOWN_CLAUSE_FIELD = "unknown_clause_field"
ERROR_UNSUPPORTED_MODEL_FIELD = "unsupported_model_field"
ERROR_INVALID_CLAUSE_ITEM = "invalid_clause_item"
ERROR_INVALID_ENUM = "invalid_enum"
ERROR_ALIAS_CONFLICT = "alias_target_conflict"

# ---------------------------------------------------------------------------
# Normalization result
# ---------------------------------------------------------------------------


@dataclass
class NormalizationResult:
    """Result of a schema-alignment normalization pass (R11.2.1).

    Parameters
    ----------
    normalized : dict | None
        The cleaned and mapped dict, or ``None`` if normalization
        was rejected before producing a candidate.
    status : str
        ``"accepted"`` — mapped successfully and ready for schema validation.
        ``"noop"`` — no changes needed; candidate already uses only recognized
        field names.
        ``"error"`` — input rejected; see *error_reason* and *error_message*.
    mappings_applied : int
        Number of field-name mappings applied.
    error_message : str | None
        Human-readable error if *status* is ``"error"``.
    error_reason : str | None
        Machine-readable error category (one of the ``ERROR_*`` constants)
        when *status* is ``"error"``.
    """

    normalized: dict | None = None
    status: str = "noop"
    mappings_applied: int = 0
    error_message: str | None = None
    error_reason: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_fieldspan_compatible(value: object) -> bool:
    """Return ``True`` if *value* is a dict or ``None`` (FieldSpan-compatible)."""
    return value is None or isinstance(value, dict)


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
    return None


def _validate_and_normalize_clause(clause: dict) -> tuple[dict | None, str | None, str | None, int]:
    """Validate and normalize a single clause dict (R11.2.1 strict gate).

    Returns ``(normalized_dict, error_reason, error_message, mappings)``.
    On success, *error_reason* and *error_message* are ``None``.
    On failure, *normalized_dict* is ``None``.

    Strict gates (checked before any mapping):
    1. Reject known unsupported model fields (``object``, ``original_text``).
    2. Reject unknown clause-level keys not in the allowed input set.
    3. Reject alias+target conflicts where both are present with non-equivalent values.
    4. Reject unsupported enum values (non-dict, non-None) for mapped fields.

    Mapping (after gates pass):
    5. Rename alias fields to project field names.
    6. Coerce semantic-field values to FieldSpan-compatible or ``None``.
    """
    # ---- Gate 1: known unsupported model fields --------------------------
    for key in _CLAUSE_FIELDS_REJECT:
        if key in clause:
            return (
                None,
                ERROR_UNSUPPORTED_MODEL_FIELD,
                f"Known unsupported model field '{key}' found in clause — "
                f"no project schema target exists for this field",
                0,
            )

    # ---- Gate 2: unknown clause-level keys -------------------------------
    unknown = set(clause.keys()) - _ALLOWED_CLAUSE_INPUT_KEYS
    if unknown:
        return (
            None,
            ERROR_UNKNOWN_CLAUSE_FIELD,
            f"Unknown clause-level keys not in project schema or "
            f"recognised aliases: {sorted(unknown)}",
            0,
        )

    # ---- Gate 3: alias + target conflicts --------------------------------
    for alias, target in _CLAUSE_FIELD_MAP.items():
        if alias in clause and target in clause:
            alias_val = _normalize_semantic_value(clause[alias])
            target_val = _normalize_semantic_value(clause[target])
            # For simplicity and strictness, always reject conflicts.
            return (
                None,
                ERROR_ALIAS_CONFLICT,
                f"Alias '{alias}' and target '{target}' both present in clause — "
                f"ambiguous, rejecting conservatively",
                0,
            )

    # ---- Gate 4: unsupported enum values for mapped fields ---------------
    for alias in _CLAUSE_FIELD_MAP:
        if alias in clause:
            val = clause[alias]
            if not _is_fieldspan_compatible(val):
                return (
                    None,
                    ERROR_INVALID_ENUM,
                    f"Mapped field '{alias}' has non-FieldSpan, non-None value "
                    f"(type {type(val).__name__}) — unsupported enum/value",
                    0,
                )

    # ---- Mapping phase ---------------------------------------------------
    result: dict[str, object] = {}
    mappings = 0

    for key, value in clause.items():
        if key in _CLAUSE_FIELD_MAP:
            target = _CLAUSE_FIELD_MAP[key]
            # All alias fields have passed Gate 4, so value is dict or None.
            normalized_val = _normalize_semantic_value(value)
            if target not in result:
                result[target] = normalized_val
                mappings += 1
            # If target already present from another source, keep existing
            continue

        # Project-schema keys
        if key in _CLAUSE_KEYS:
            if key in _SEMANTIC_FIELDS:
                result[key] = _normalize_semantic_value(value)
            else:
                result[key] = value
            continue

    return result, None, None, mappings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_llm_fallback_json(candidate: dict) -> NormalizationResult:
    """Normalize and validate a raw LLM JSON dict for schema alignment.

    R11.2.1 **strict gate**: rejects candidates with missing explicit
    top-level keys, unknown fields, known unsupported model fields, non-dict
    clause items, unsupported enum values, and alias-target conflicts.

    This is a **deterministic, mock-safe** pure function.  It never calls
    an LLM, accesses the network, reads ``.env``, or saves raw responses.

    Parameters
    ----------
    candidate : dict
        The raw JSON dict parsed from the LLM response.

    Returns
    -------
    NormalizationResult
        - ``status="accepted"``: mappings applied successfully; the
          ``normalized`` dict is ready for schema validation.
        - ``status="noop"``: no changes needed — the candidate already
          uses only recognized field names.
        - ``status="error"``: the candidate was rejected.  ``normalized``
          is ``None``.  See ``error_reason`` for the category.
    """
    # ---- Gate: must be a dict --------------------------------------------
    if not isinstance(candidate, dict):
        return NormalizationResult(
            normalized=None,
            status="error",
            error_reason=ERROR_MISSING_TOP_KEY,
            error_message=(
                f"normalize_llm_fallback_json expects a dict, "
                f"got {type(candidate).__name__}"
            ),
        )

    # ---- Gate: must have all four explicit top-level keys ----------------
    missing = [k for k in _MULTI_CLAUSE_KEYS if k not in candidate]
    if missing:
        return NormalizationResult(
            normalized=None,
            status="error",
            error_reason=ERROR_MISSING_TOP_KEY,
            error_message=(
                f"Missing required top-level keys: {sorted(missing)}. "
                f"R11.2.1 strict gate requires all of: "
                f"{sorted(_MULTI_CLAUSE_KEYS)}"
            ),
        )

    # ---- Gate: no unknown top-level keys ---------------------------------
    unknown_top = set(candidate.keys()) - _MULTI_CLAUSE_KEYS
    if unknown_top:
        return NormalizationResult(
            normalized=None,
            status="error",
            error_reason=ERROR_UNKNOWN_TOP_FIELD,
            error_message=(
                f"Unknown top-level keys: {sorted(unknown_top)}. "
                f"Allowed top-level keys: {sorted(_MULTI_CLAUSE_KEYS)}"
            ),
        )

    # ---- Gate: clauses must be a list ------------------------------------
    clauses_raw = candidate.get("clauses")
    if not isinstance(clauses_raw, list):
        return NormalizationResult(
            normalized=None,
            status="error",
            error_reason=ERROR_INVALID_CLAUSE_ITEM,
            error_message=(
                f"MultiClauseExtractionResponse.clauses must be a list, "
                f"got {type(clauses_raw).__name__}"
            ),
        )

    # ---- Gate: every clause item must be a dict --------------------------
    for i, item in enumerate(clauses_raw):
        if not isinstance(item, dict):
            return NormalizationResult(
                normalized=None,
                status="error",
                error_reason=ERROR_INVALID_CLAUSE_ITEM,
                error_message=(
                    f"MultiClauseExtractionResponse.clauses[{i}] must be a dict, "
                    f"got {type(item).__name__}"
                ),
            )

    # ---- Normalize each clause (strict gates inside) ---------------------
    total_mappings = 0
    normalized_clauses: list[dict] = []

    for i, clause_dict in enumerate(clauses_raw):
        norm_dict, err_reason, err_msg, mappings = _validate_and_normalize_clause(clause_dict)
        if err_reason is not None:
            return NormalizationResult(
                normalized=None,
                status="error",
                error_reason=err_reason,
                error_message=(
                    f"clauses[{i}]: {err_msg}"
                ),
            )
        total_mappings += mappings
        normalized_clauses.append(norm_dict)

    # ---- Build normalized output -----------------------------------------
    normalized: dict[str, object] = {
        "schema_version": candidate["schema_version"],
        "source_id": candidate["source_id"],
        "source_text": candidate["source_text"],
        "clauses": normalized_clauses,
    }

    status = "accepted" if total_mappings > 0 else "noop"
    return NormalizationResult(
        normalized=normalized,
        status=status,
        mappings_applied=total_mappings,
    )

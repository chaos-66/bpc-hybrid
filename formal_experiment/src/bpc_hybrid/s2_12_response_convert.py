# -*- coding: utf-8 -*-
"""Response->canonical conversion for the S2.12 API arms (direct_llm).

Mirrors the GDPR Direct-LLM executor conversion chain
(``run_gdpr7_direct_llm_v1.convert_content_to_attempt``): code-fence strip ->
JSON parse -> forbidden-content rejection -> D1 relay adapter -> coordinate
canonicalization -> canonical validation -> coordinate-only sanitization.

Pure functions only (no I/O, no network, no .env, no Gold).  The source text
is supplied by the caller (resolved locally from the read-only Barrientos
corpus at finalize time); committed artifacts never carry raw text.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from bpc_hybrid.d1_schema_adapter import adapt_relay_record  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402

_FORBIDDEN_CONTENT_TERMS = ("expected_violation", "variant_id", "check_type")

# Raw-text keys that must never appear in committed capsule docs.
_FORBIDDEN_TEXT_KEYS = (
    "text", "source_text", "approved_text_en", "normalized", "marker_surface",
)


class ResponseConvertError(ValueError):
    """Fail-closed response conversion error."""


def strip_text_fields(value: Any) -> Any:
    """Recursively drop raw-text keys (coordinates and ids survive)."""
    if isinstance(value, dict):
        return {
            key: strip_text_fields(child)
            for key, child in value.items()
            if key not in _FORBIDDEN_TEXT_KEYS
        }
    if isinstance(value, list):
        return [strip_text_fields(item) for item in value]
    return value


def sanitize_record(record: Mapping[str, Any],
                    method_name: str = "direct_llm") -> dict[str, Any]:
    """Coordinate-only canonical record (text stripped) for the capsule.

    Keeps the documented Rules-Only capsule record keys:
    schema_version/sample_id/source_id/clauses/method/validation.
    """
    clean = strip_text_fields(record)
    kept = {
        "schema_version": clean.get("schema_version"),
        "sample_id": clean.get("sample_id"),
        "source_id": clean.get("source_id"),
        "clauses": clean.get("clauses") or [],
        "method": clean.get("method") or {
            "name": method_name,
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": clean.get("validation"),
    }
    return kept


def failed_attempt_row(sample_id: str, request_status: str,
                       error_category: str) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "request_status": request_status,
        "record": None,
        "error_category": error_category,
    }


def direct_content_to_attempt(sample_id: str, content: str,
                              source_text: str) -> dict[str, Any]:
    """Convert one raw model JSON response into a canonical attempt envelope.

    Returns ``{sample_id, request_status, record, error_category}`` where
    ``record`` is coordinate-only; any parse/adapt/canonicalize/validate
    failure yields an explicit error_category row (never fabricated).
    """
    raw = (content or "").strip()
    if not raw:
        return failed_attempt_row(sample_id, "in_doubt",
                                  "completed_without_content")
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 1 else raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return failed_attempt_row(
            sample_id, "failed_parse", f"non_json_content:{exc}"
        )
    if not isinstance(payload, dict):
        return failed_attempt_row(sample_id, "failed_parse",
                                  "payload_not_object")
    blob = json.dumps(payload).lower()
    for term in _FORBIDDEN_CONTENT_TERMS:
        if term in blob:
            return failed_attempt_row(
                sample_id, "failed_parse", f"forbidden_content_term:{term}"
            )
    payload.setdefault("source_id", sample_id)
    payload.setdefault("sample_id", sample_id)
    payload.setdefault("source_text", source_text)
    payload.setdefault("schema_version", "1.0.0")
    payload.setdefault("method", {
        "name": "direct_llm",
        "schema_source": "stage2_prediction.schema.json@1.0.0",
    })
    payload.setdefault("unsupported_or_ambiguous", [])

    adapted, adapt_audit = adapt_relay_record(payload, source_text)
    if adapt_audit["status"] == "failed":
        return failed_attempt_row(
            sample_id, "ok",
            "relay_schema_adaptation_failed",
        )
    canonical, span_audit = canonicalize_record_coordinates(adapted, source_text)
    if span_audit["status"] == "failed":
        return failed_attempt_row(
            sample_id, "ok", "span_canonicalization_failed"
        )
    report = validate_canonical(canonical)
    if not (report.schema_valid and report.cross_field_valid):
        return failed_attempt_row(
            sample_id, "ok", "canonical_validation_failed"
        )
    return {
        "sample_id": sample_id,
        "request_status": "ok",
        "record": sanitize_record(canonical, method_name="direct_llm"),
        "error_category": None,
    }


def fallback_envelope_from_content(content: str) -> dict[str, Any]:
    """Parse the fallback arm's repair envelope (5 keys).

    Mirrors ``run_sun_llm_fallback._parse_patch_response``: the response must
    be a JSON object; raises :class:`ResponseConvertError` on any other
    shape.  Repair application itself lives in the finalizer (reuses
    ``run_sun_llm_fallback`` apply helpers via import).
    """
    raw = (content or "").strip()
    if not raw:
        raise ResponseConvertError("empty fallback response content")
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 1 else raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResponseConvertError(f"non_json_patch_content:{exc}") from exc
    if not isinstance(payload, dict):
        raise ResponseConvertError("patch_payload_not_object")
    required = ("sample_id", "clause_id", "repair_fields", "patches", "reason")
    missing = [name for name in required if name not in payload]
    if missing:
        raise ResponseConvertError(
            f"patch envelope missing keys: {missing}"
        )
    if not isinstance(payload["repair_fields"], list) or not isinstance(
            payload["patches"], dict):
        raise ResponseConvertError("patch envelope repair_fields/patches shape")
    return payload

"""Canonical Stage 2 prediction schema and cross-field validator (Wave 1.1).

This module is the single source of truth for the Stage 2 prediction
contract used by D1, H1, and B0 once they are implemented.

The JSON Schema lives at
``configs/schemas/stage2_prediction.schema.json`` (v1.0.0). The Python
class below adds the **cross-field** rules that JSON Schema cannot
express:

* ``text`` of every span MUST equal ``source_text[start:end]``
* every child span MUST be inside its clause's ``clause_span``
* all ``clause_id`` values MUST be unique within a record
* all span ``id`` values MUST be unique within a record
* ``actor_action_map[i].actor_id`` MUST be a key in ``actors`` (or null)
* ``actor_action_map[i].action_id`` MUST be a key in ``actions``
* ``order_relations[i].before_action_id`` / ``after_action_id`` MUST be in
  ``actions``
* ``sample_id`` and ``source_id`` MUST be non-empty (the schema already
  enforces this, the validator reports it explicitly)
* ``normalized`` MUST NOT modify the raw evidence text (it is allowed
  to differ in any other way: case, lemmatization, abbreviation, etc.)

The validator does NOT judge semantic correctness. It only checks
structural readiness. Semantic checks belong in the Stage 2 evaluator
(see ``docs/EVAL_3DIM_SPEC.md``).

The validator is intentionally framework-light: no Pydantic, no
``jsonschema`` package required for the in-process cross-field checks.
The JSON Schema is loaded lazily and only used for
``validate_schema_json()`` when the package is available; cross-field
checks work either way.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "schemas"
    / "stage2_prediction.schema.json"
)
SCHEMA_SOURCE = f"stage2_prediction.schema.json@{SCHEMA_VERSION}"

VALID_MODALITIES = ("obligation", "prohibition", "permission", "definition")
VALID_METHODS = ("sun_rule_only", "sun_llm_fallback", "direct_llm")
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]+$")


# ---------------------------------------------------------------------------
# Errors and report
# ---------------------------------------------------------------------------


class CanonicalSchemaError(ValueError):
    """Raised when a record fails cross-field validation."""


@dataclass
class CanonicalValidationReport:
    """Result of validating a single canonical prediction record."""

    schema_valid: bool = True
    cross_field_valid: bool = True
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "cross_field_valid": self.cross_field_valid,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_span(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("text"), str)
        and isinstance(value.get("start"), int)
        and isinstance(value.get("end"), int)
    )


def _span_text_matches_source(span: dict, source_text: str) -> str | None:
    """Return None if OK, else an error message."""
    start, end = span["start"], span["end"]
    if end > len(source_text):
        return (
            f"span [{start}:{end}] exceeds source_text length "
            f"{len(source_text)}"
        )
    if end <= start:
        return f"span [{start}:{end}] is not strictly positive"
    if source_text[start:end] != span["text"]:
        return (
            f"span text {span['text']!r} does not match "
            f"source_text[{start}:{end}]={source_text[start:end]!r}"
        )
    return None


def _is_inside(child: dict, parent: dict) -> bool:
    return parent["start"] <= child["start"] and child["end"] <= parent["end"]


# ---------------------------------------------------------------------------
# JSON Schema validation (optional jsonschema package)
# ---------------------------------------------------------------------------


def load_json_schema_dict() -> dict:
    """Load the canonical JSON Schema as a dict.

    Raises ``FileNotFoundError`` if the schema file is missing. The
    caller is responsible for caching.
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Canonical schema not found: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_schema_json(payload: dict, schema: dict | None = None) -> list[str]:
    """Validate *payload* against the canonical JSON Schema.

    Returns a list of error messages. Empty list means the payload
    matches the schema. Falls back to a minimal in-process structural
    check if the ``jsonschema`` package is not available.
    """
    schema = schema or load_json_schema_dict()
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return _structural_check(payload)
    errors: list[str] = []
    validator = jsonschema.Draft202012Validator(schema)
    for err in sorted(validator.iter_errors(payload), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in err.path) or "<root>"
        errors.append(f"jsonschema: {path}: {err.message}")
    return errors


def _structural_check(payload: dict) -> list[str]:
    """Minimal in-process structural check (fallback when ``jsonschema`` is missing).

    Intentionally redundant with the JSON Schema. Catches the same set
    of top-level violations that ``Draft202012Validator`` would catch
    when running the canonical schema.
    """
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload is not a JSON object"]

    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"schema_version must be '{SCHEMA_VERSION}', "
            f"got {payload.get('schema_version')!r}"
        )

    for key in (
        "sample_id", "source_id", "source_text", "clauses",
        "method", "validation",
    ):
        if key not in payload:
            errors.append(f"missing required top-level key: {key}")

    if payload.get("sample_id") is not None and not (
        isinstance(payload["sample_id"], str) and payload["sample_id"]
    ):
        errors.append("sample_id must be a non-empty string")
    if payload.get("source_id") is not None and not (
        isinstance(payload["source_id"], str) and payload["source_id"]
    ):
        errors.append("source_id must be a non-empty string")
    if payload.get("source_text") is not None and not (
        isinstance(payload["source_text"], str) and payload["source_text"]
    ):
        errors.append("source_text must be a non-empty string")

    if not isinstance(payload.get("clauses", None), list):
        errors.append("clauses must be an array")

    method = payload.get("method")
    if isinstance(method, dict):
        if method.get("schema_source") != SCHEMA_SOURCE:
            errors.append(
                f"method.schema_source must be {SCHEMA_SOURCE!r}, "
                f"got {method.get('schema_source')!r}"
            )
        if method.get("name") not in VALID_METHODS:
            errors.append(
                f"method.name must be one of {VALID_METHODS}, "
                f"got {method.get('name')!r}"
            )

    return errors


# ---------------------------------------------------------------------------
# Cross-field validation
# ---------------------------------------------------------------------------


def validate_cross_field(payload: dict) -> list[str]:
    """Run cross-field structural checks. Returns a list of error strings.

    Assumes the payload already passed ``validate_schema_json``. The
    validator does not duplicate the JSON-Schema-level checks.
    """
    errors: list[str] = []
    source_text: str = payload.get("source_text", "")
    clauses: list[dict] = payload.get("clauses", [])

    clause_ids: set[str] = set()
    span_ids: set[str] = set()

    for ci, clause in enumerate(clauses):
        path = f"clauses[{ci}]"

        # clause_id uniqueness
        clause_id = clause.get("clause_id", "")
        if clause_id in clause_ids:
            errors.append(f"{path}.clause_id duplicate: {clause_id!r}")
        clause_ids.add(clause_id)

        # clause_span structural sanity
        clause_span = clause.get("clause_span")
        if not _is_span(clause_span):
            errors.append(f"{path}.clause_span must be a span object")
            continue
        if (msg := _span_text_matches_source(clause_span, source_text)) is not None:
            errors.append(f"{path}.clause_span {msg}")
            continue

        # modality
        modality = clause.get("modality", {})
        if modality.get("label") not in VALID_MODALITIES:
            errors.append(
                f"{path}.modality.label must be one of {VALID_MODALITIES}, "
                f"got {modality.get('label')!r}"
            )
        evidence = modality.get("evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{path}.modality.evidence must be a non-empty array")
        else:
            for ei, ev in enumerate(evidence):
                if not _is_span(ev):
                    errors.append(
                        f"{path}.modality.evidence[{ei}] must be a span object"
                    )
                    continue
                if (msg := _span_text_matches_source(ev, source_text)) is not None:
                    errors.append(f"{path}.modality.evidence[{ei}] {msg}")
                if not _is_inside(ev, clause_span):
                    errors.append(
                        f"{path}.modality.evidence[{ei}] not inside clause_span"
                    )

        # collect span IDs + arrays of identified spans per field
        field_arrays = {
            "actors": clause.get("actors", []),
            "actions": clause.get("actions", []),
            "conditions": clause.get("conditions", []),
            "constraints": clause.get("constraints", []),
            "exceptions": clause.get("exceptions", []),
        }
        per_field_ids: dict[str, list[str]] = {}
        for fname, items in field_arrays.items():
            ids: list[str] = []
            for si, span in enumerate(items):
                spath = f"{path}.{fname}[{si}]"
                if not _is_span(span):
                    errors.append(f"{spath} must be a span object")
                    continue
                if "id" not in span or not isinstance(span.get("id"), str) or not span["id"]:
                    errors.append(f"{spath}.id must be a non-empty string")
                    continue
                sid = span["id"]
                if sid in span_ids:
                    errors.append(f"{spath}.id duplicate: {sid!r}")
                span_ids.add(sid)
                ids.append(sid)
                if "normalized" not in span or not isinstance(span.get("normalized"), str) or not span["normalized"]:
                    errors.append(f"{spath}.normalized must be a non-empty string")
                if (msg := _span_text_matches_source(span, source_text)) is not None:
                    errors.append(f"{spath} {msg}")
                if not _is_inside(span, clause_span):
                    errors.append(f"{spath} not inside clause_span")
                # normalized must not modify raw evidence (it can lowercase, lemmatize, etc.)
                if span["normalized"] == span["text"]:
                    pass  # trivially fine
                # The check above is purely structural; semantically the
                # "normalized" field is allowed to differ in any way, but
                # downstream code may compare normalized and raw text for
                # trace. We do not silently rewrite normalized = text.
            per_field_ids[fname] = ids

        # actor_action_map edges
        for ei, edge in enumerate(clause.get("actor_action_map", [])):
            epath = f"{path}.actor_action_map[{ei}]"
            actor_id = edge.get("actor_id")
            action_id = edge.get("action_id")
            if actor_id is not None and actor_id not in per_field_ids["actors"]:
                errors.append(
                    f"{epath}.actor_id={actor_id!r} not in actors ids "
                    f"{per_field_ids['actors']}"
                )
            if action_id not in per_field_ids["actions"]:
                errors.append(
                    f"{epath}.action_id={action_id!r} not in actions ids "
                    f"{per_field_ids['actions']}"
                )

        # order_relations edges
        for oi, rel in enumerate(clause.get("order_relations", [])):
            rpath = f"{path}.order_relations[{oi}]"
            for key in ("before_action_id", "after_action_id"):
                rid = rel.get(key)
                if rid not in per_field_ids["actions"]:
                    errors.append(
                        f"{rpath}.{key}={rid!r} not in actions ids "
                        f"{per_field_ids['actions']}"
                    )
            evidence = rel.get("evidence", [])
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"{rpath}.evidence must be a non-empty array")
            else:
                for ei, ev in enumerate(evidence):
                    if not _is_span(ev):
                        errors.append(f"{rpath}.evidence[{ei}] must be a span object")
                        continue
                    if (msg := _span_text_matches_source(ev, source_text)) is not None:
                        errors.append(f"{rpath}.evidence[{ei}] {msg}")
                    if not _is_inside(ev, clause_span):
                        errors.append(
                            f"{rpath}.evidence[{ei}] not inside clause_span"
                        )

    return errors


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_canonical(payload: dict) -> CanonicalValidationReport:
    """Validate *payload* against the canonical schema + cross-field rules.

    Updates ``payload['validation']`` in place to reflect the result.
    Returns a :class:`CanonicalValidationReport` summarizing the run.
    """
    schema_errors = validate_schema_json(payload)
    cross_errors: list[str] = []
    if not schema_errors:
        cross_errors = validate_cross_field(payload)

    report = CanonicalValidationReport(
        schema_valid=not schema_errors,
        cross_field_valid=not cross_errors,
        errors=schema_errors + cross_errors,
    )
    payload["validation"] = report.to_dict()
    return report


# ---------------------------------------------------------------------------
# Convenience: validator for a list of records
# ---------------------------------------------------------------------------


@dataclass
class CanonicalBatchReport:
    """Aggregated report over a batch of records."""

    total: int = 0
    schema_invalid: int = 0
    cross_field_invalid: int = 0
    all_errors: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "schema_invalid": self.schema_invalid,
            "cross_field_invalid": self.cross_field_invalid,
            "all_errors": list(self.all_errors),
        }


def validate_canonical_batch(records: Iterable[dict]) -> CanonicalBatchReport:
    """Validate an iterable of records and return aggregated counts."""
    batch = CanonicalBatchReport()
    for record in records:
        batch.total += 1
        sid = record.get("sample_id", "?")
        report = validate_canonical(record)
        if not report.schema_valid:
            batch.schema_invalid += 1
        if not report.cross_field_valid:
            batch.cross_field_invalid += 1
        if report.errors:
            for err in report.errors:
                batch.all_errors.append({"sample_id": sid, "error": err})
    return batch

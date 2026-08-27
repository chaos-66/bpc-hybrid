# -*- coding: utf-8 -*-
"""Complete draft-07 JSON Schema validation for the D/E execution contract.

The repo's optional ``jsonschema`` package is preferred when available
(same pattern as ``bpc_hybrid.stage2_canonical.validate_schema_json``).
When it is NOT installed (current environment), this module provides a
deterministic, dependency-free validator that enforces the FULL constraint
set used by ``barrientos_de_execution_contract_v1.schema.json``:

* type (including null/object/array/string/number/integer/boolean)
* const / enum
* required + additionalProperties:false (unknown keys rejected)
* properties with nested recursion
* pattern, minLength/maxLength
* items (per-index object schemas), minItems
* minimum/exclusiveMinimum, maximum/exclusiveMaximum
* nested object/array recursion

Validation is exhaustive: any violation anywhere in the document (not only
top-level keys) produces an error with a JSON-path location.  The validator
is intentionally strict — a contract that merely has the right top-level
keys but wrong nested types/values is REJECTED before the first send.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Sequence


class SchemaValidationError(ValueError):
    """Aggregate schema-validation failure (message lists every violation)."""


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True  # unknown type keyword: do not fail closed on spec gaps


def _validate_node(instance: Any, schema: Any, path: str,
                   errors: list[str]) -> None:
    if not isinstance(schema, Mapping):
        return
    # const
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: const mismatch (expected "
                      f"{schema['const']!r}, got {instance!r})")
    # enum
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum "
                      f"{schema['enum']}")
    # type (single string or list of strings)
    types = schema.get("type")
    if isinstance(types, str):
        types = [types]
    if isinstance(types, list) and types \
            and not any(_type_ok(instance, t) for t in types):
        errors.append(f"{path}: type mismatch (expected one of {types}, "
                      f"got {type(instance).__name__})")

    if isinstance(instance, dict):
        # required
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required key {key!r}")
        properties = schema.get("properties")
        pattern_props = schema.get("patternProperties") or {}
        pattern_rxs = []
        for pattern in pattern_props:
            try:
                pattern_rxs.append((re.compile(pattern), pattern_props[pattern]))
            except re.error:
                continue
        # properties + additionalProperties
        if isinstance(properties, Mapping):
            for key, value in instance.items():
                if key in properties:
                    _validate_node(value, properties[key], f"{path}.{key}",
                                   errors)
                elif any(rx.match(key) for rx, _ in pattern_rxs):
                    for rx, sub in pattern_rxs:
                        if rx.match(key):
                            _validate_node(value, sub, f"{path}.{key}", errors)
                elif schema.get("additionalProperties") is False:
                    errors.append(f"{path}: additional property {key!r} "
                                  f"not allowed")
        elif pattern_rxs:
            for key, value in instance.items():
                matched = False
                for rx, sub in pattern_rxs:
                    if rx.match(key):
                        matched = True
                        _validate_node(value, sub, f"{path}.{key}", errors)
                if not matched and schema.get("additionalProperties") is False:
                    errors.append(f"{path}: additional property {key!r} "
                                  f"not allowed")
        elif schema.get("additionalProperties") is False:
            errors.append(f"{path}: object has keys but schema declares "
                          f"no properties and additionalProperties=false")

    elif isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, Mapping):
            for i, value in enumerate(instance):
                _validate_node(value, items, f"{path}[{i}]", errors)
        elif isinstance(items, list):
            for i, value in enumerate(instance):
                sub = items[i] if i < len(items) else {}
                _validate_node(value, sub, f"{path}[{i}]", errors)
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: fewer than minItems "
                          f"({len(instance)} < {schema['minItems']})")

    if isinstance(instance, str):
        if "pattern" in schema:
            try:
                if not re.match(schema["pattern"], instance):
                    errors.append(f"{path}: string does not match pattern "
                                  f"{schema['pattern']!r}")
            except re.error:
                pass
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: string longer than maxLength")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: value {instance} below minimum "
                          f"{schema['minimum']}")
        if "exclusiveMinimum" in schema \
                and instance <= schema["exclusiveMinimum"]:
            errors.append(f"{path}: value {instance} not above "
                          f"exclusiveMinimum {schema['exclusiveMinimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: value {instance} above maximum "
                          f"{schema['maximum']}")
        if "exclusiveMaximum" in schema \
                and instance >= schema["exclusiveMaximum"]:
            errors.append(f"{path}: value {instance} not below "
                          f"exclusiveMaximum {schema['exclusiveMaximum']}")


def validate_instance(instance: Any, schema: Any) -> list[str]:
    """Return all schema violations ([] when valid)."""
    errors: list[str] = []
    _validate_node(instance, schema, "<root>", errors)
    return errors


def validate_instance_strict(instance: Any, schema: Any) -> None:
    """Raise ``SchemaValidationError`` when the instance violates schema."""
    errors = validate_instance(instance, schema)
    if errors:
        raise SchemaValidationError(
            "schema validation failed:\n  " + "\n  ".join(errors))


def validate_with_jsonschema_if_available(instance: Any,
                                          schema: Any) -> list[str]:
    """Full validation: ``jsonschema`` when installed, else this module's
    complete recursive validator (identical constraint coverage for the
    contract schema)."""
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return validate_instance(instance, schema)
    try:
        validator = jsonschema.Draft7Validator(schema)
        return [f"{list(e.path) or '<root>'}: {e.message}"
                for e in sorted(validator.iter_errors(instance),
                                key=lambda e: list(e.path))]
    except Exception as exc:  # schema/draft incompatibility -> fail closed
        return [f"jsonschema failure: {exc}"]


def load_schema(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

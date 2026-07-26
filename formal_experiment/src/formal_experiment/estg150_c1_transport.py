"""Versioned candidate transport adaptation and offline capability preflight.

The canonical semantic request and output schema remain immutable. This module
derives a transport-only schema, validates the OpenAI Structured Outputs subset,
and packages the same semantic contract for explicit provider/model capability
profiles before credentials or network access are possible.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from formal_experiment.estg150_candidate_protocol import (
    ProtocolError,
    ProtocolIncompatible,
    ProviderAdapter,
    RESPONSE_COORDINATE_MODE_REJECT_INVALID,
    RESPONSE_COORDINATE_MODE_UNIQUE_EXACT,
    canonical_json_bytes,
    json_type_matches,
    sha256_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
TRANSPORT_ADAPTER_CONFIG_PATH = (
    ROOT / "configs" / "estg150_openai_strict_transport_schema_adapter_v1_1.json"
)
PORTABLE_TRANSPORT_ADAPTER_CONFIG_PATH = (
    ROOT / "configs" / "estg150_openai_strict_transport_schema_adapter_v1_5.json"
)
PORTABLE_TRANSPORT_ADAPTER_V1_4_CONFIG_PATH = (
    ROOT / "configs" / "estg150_openai_strict_transport_schema_adapter_v1_4.json"
)
PORTABLE_TRANSPORT_ADAPTER_V1_3_CONFIG_PATH = (
    ROOT / "configs" / "estg150_openai_strict_transport_schema_adapter_v1_3.json"
)
PORTABLE_TRANSPORT_ADAPTER_V1_2_CONFIG_PATH = (
    ROOT / "configs" / "estg150_openai_strict_transport_schema_adapter_v1_2.json"
)
EXPECTED_CANONICAL_SCHEMA_SHA256 = (
    "fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9"
)
EXPECTED_STRING_TYPE_PATCHES = (
    "/properties/schema_version",
    "/properties/context_sufficiency",
    "/properties/translation/properties/decision",
    "/$defs/modality/properties/label",
    "/properties/confidence",
    "/$defs/ambiguity/properties/field",
)
READY_PROFILE_STATUSES = {
    "offline_ready",
    "offline_request_ready_runtime_503_unresolved",
    "offline_ready_capability_adapted",
    "offline_ready_json_mode_local_schema_validation",
}
JSON_SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
SPAN_TEXT_GUARD_MODE = "append_transport_exact_span_self_check"
SPAN_TEXT_GUARD_V1_4_INSTRUCTION = (
    "[BEGIN EXACT SPAN OUTPUT INVARIANT]\n"
    "Before emitting JSON, freeze translation.proposed_text_en. For every clause_span and "
    "every modality.evidence, actor, action, condition, constraint, exception, and "
    "order_relations.evidence span: (1) copy text verbatim as one contiguous substring of "
    "proposed_text_en; never paraphrase text, normalize it, delete internal words, or join "
    "discontiguous fragments; normalized may summarize but text may not; (2) ensure every "
    "child text occurs completely inside its own clause_span; (3) compute start/end from the "
    "exact Python half-open slice so text == proposed_text_en[start:end]; and (4) make "
    "modality.evidence contain the visible normative cue that supports the label, such as "
    "shall, must, may, prohibited, means, or deemed, rather than an actor or object. For "
    "optional semantic collections, if no exact contiguous source span exists, use an empty "
    "array and record the uncertainty in unsupported_or_ambiguous instead of fabricating a "
    "span. Internally verify every slice before returning. Output JSON only.\n"
    "[END EXACT SPAN OUTPUT INVARIANT]"
)
SPAN_TEXT_GUARD_INSTRUCTION = (
    "[BEGIN EXACT SPAN OUTPUT INVARIANT]\n"
    "Before emitting JSON, first make translation.decision consistent with the exact English "
    "candidate supplied for this review: if translation.proposed_text_en is character-for-character "
    "unchanged, translation.decision must be accepted; use edited only when proposed_text_en actually "
    "differs by at least one character. Never label unchanged text as edited. Then freeze "
    "translation.proposed_text_en. For every clause_span and every modality.evidence, actor, action, "
    "condition, constraint, exception, and order_relations.evidence span: (1) copy text verbatim as "
    "one contiguous substring of proposed_text_en; never paraphrase text, normalize it, delete internal "
    "words, or join discontiguous fragments; normalized may summarize but text may not; (2) ensure "
    "every child text occurs completely inside its own clause_span; (3) compute start/end from the exact "
    "Python half-open slice so text == proposed_text_en[start:end]; and (4) make modality.evidence "
    "contain the visible normative cue that supports the label, such as shall, must, may, prohibited, "
    "means, or deemed, rather than an actor or object. For optional semantic collections, if no exact "
    "contiguous source span exists, use an empty array and record the uncertainty in "
    "unsupported_or_ambiguous instead of fabricating a span. Internally verify the decision/text pair "
    "and every slice before returning. Output JSON only.\n"
    "[END EXACT SPAN OUTPUT INVARIANT]"
)
EXPECTED_PROFILE_CONTRACT = {
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-5.6-luna"): {
        "profile_id": "estg150_chatanywhere_modern_strict_profile",
        "profile_version": "1.0.0",
        "status": "offline_ready",
        "transport_schema_adapter_identity": "estg150_openai_strict_transport_schema_adapter@1.1.0",
        "blocking_paths": (),
        "reason_codes": (),
    },
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-5.4-nano"): {
        "profile_id": "estg150_chatanywhere_modern_strict_profile",
        "profile_version": "1.0.0",
        "status": "offline_ready",
        "transport_schema_adapter_identity": "estg150_openai_strict_transport_schema_adapter@1.1.0",
        "blocking_paths": (),
        "reason_codes": (),
    },
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-5-nano"): {
        "profile_id": "estg150_chatanywhere_modern_strict_profile",
        "profile_version": "1.0.0",
        "status": "offline_request_ready_runtime_503_unresolved",
        "transport_schema_adapter_identity": "estg150_openai_strict_transport_schema_adapter@1.1.0",
        "blocking_paths": (),
        "reason_codes": (),
    },
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-4.1-nano"): {
        "profile_id": "estg150_c1_observed_incompatibility",
        "profile_version": "1.0.0",
        "status": "blocked_requires_separately_approved_versioned_provider_profile",
        "transport_schema_adapter_identity": None,
        "blocking_paths": ("$.reasoning_effort",),
        "reason_codes": ("reasoning_effort_unsupported",),
    },
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-4o"): {
        "profile_id": "estg150_c1_observed_incompatibility",
        "profile_version": "1.0.0",
        "status": "blocked_pending_separately_approved_versioned_provider_profile",
        "transport_schema_adapter_identity": None,
        "blocking_paths": ("$.reasoning_effort",),
        "reason_codes": (
            "reasoning_effort_acceptance_unverified_after_remote_disconnect",
            "field_removal_requires_separate_explicit_approval",
        ),
    },
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-3.5-turbo"): {
        "profile_id": "estg150_c1_observed_incompatibility",
        "profile_version": "1.0.0",
        "status": "canonical_protocol_incompatible",
        "transport_schema_adapter_identity": None,
        "blocking_paths": ("$.reasoning_effort", "$.response_format.type"),
        "reason_codes": (
            "reasoning_effort_unsupported",
            "strict_json_schema_not_supported_without_forbidden_json_object_downgrade",
        ),
    },
    ("deepseek_official", "api.deepseek.com", "deepseek-v4-pro"): {
        "profile_id": "estg150_c1_observed_incompatibility",
        "profile_version": "1.0.0",
        "status": "canonical_protocol_incompatible",
        "transport_schema_adapter_identity": None,
        "blocking_paths": ("$.messages[1].role", "$.response_format.type"),
        "reason_codes": ("developer_role_unsupported", "strict_response_format_unsupported"),
    },
}

EXPECTED_PORTABLE_PROFILE_POLICIES = {
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-5.6-luna"): (
        "offline_ready",
        "preserve",
        "preserve",
        "max_completion_tokens",
        "json_schema_strict",
        False,
    ),
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-5.4-nano"): (
        "offline_ready",
        "preserve",
        "preserve",
        "max_completion_tokens",
        "json_schema_strict",
        False,
    ),
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-5-nano"): (
        "offline_request_ready_runtime_503_unresolved",
        "preserve",
        "preserve",
        "max_completion_tokens",
        "json_schema_strict",
        False,
    ),
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-4.1-nano"): (
        "offline_ready_capability_adapted",
        "merge_system_developer",
        "omit",
        "max_tokens",
        "json_schema_strict",
        False,
    ),
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-4o"): (
        "offline_ready_capability_adapted",
        "merge_system_developer",
        "omit",
        "max_tokens",
        "json_schema_strict",
        False,
    ),
    ("relay_openai_compatible", "api.chatanywhere.tech", "gpt-3.5-turbo"): (
        "offline_ready_json_mode_local_schema_validation",
        "merge_system_developer_with_canonical_schema",
        "omit",
        "max_tokens",
        "json_object",
        True,
    ),
    ("deepseek_official", "api.deepseek.com", "deepseek-v4-pro"): (
        "offline_ready_json_mode_local_schema_validation",
        "merge_system_developer_with_canonical_schema",
        "omit",
        "max_tokens",
        "json_object",
        True,
    ),
}
EXPECTED_PORTABLE_V1_3_PROFILE_POLICIES = {
    key: (*policy, RESPONSE_COORDINATE_MODE_UNIQUE_EXACT)
    for key, policy in EXPECTED_PORTABLE_PROFILE_POLICIES.items()
}


class StructuredOutputsPreflightError(ProtocolIncompatible):
    """A schema is outside the locked OpenAI strict transport subset."""

    def __init__(self, path: str, code: str, detail: str) -> None:
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.code = code


class CapabilityPreflightError(ProtocolIncompatible):
    """A provider/model cannot carry the unchanged canonical envelope."""

    def __init__(
        self,
        path: str,
        detail: str,
        *,
        profile_status: str,
        reason_codes: tuple[str, ...],
    ) -> None:
        super().__init__(f"{path}: {detail}")
        self.path = path
        self.profile_status = profile_status
        self.reason_codes = reason_codes


@dataclass(frozen=True)
class StrictTransportAdapter:
    config: dict[str, Any]
    config_sha256: str
    adapter_id: str
    adapter_version: str
    adapter_identity: str
    canonical_protocol_version: str
    canonical_schema_path: str
    canonical_schema_sha256: str
    transport_schema_path: str
    transport_schema_sha256: str
    canonical_schema: dict[str, Any]
    transport_schema: dict[str, Any]
    canonical_preflight_error: dict[str, str]
    transport_preflight: dict[str, Any]


@dataclass(frozen=True)
class PreparedTransportRequest:
    body: dict[str, Any]
    strict_adapter: StrictTransportAdapter
    capability_profile: dict[str, Any]


def _load_json_object(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"{path} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ProtocolError(f"{path} must contain a JSON object")
    return value, raw


def _project_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ProtocolError(f"transport adapter path escapes formal_experiment: {relative_path}") from exc
    return candidate


def _json_pointer_parts(pointer: str) -> tuple[str, ...]:
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise ProtocolError(f"JSON pointer must be absolute: {pointer!r}")
    return tuple(part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/"))


def _resolve_pointer(document: dict[str, Any], pointer: str) -> Any:
    current: Any = document
    for part in _json_pointer_parts(pointer):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError as exc:
                raise ProtocolError(f"JSON pointer does not resolve: {pointer!r}") from exc
            if 0 <= index < len(current):
                current = current[index]
                continue
            raise ProtocolError(f"JSON pointer does not resolve: {pointer!r}")
        raise ProtocolError(f"JSON pointer does not resolve: {pointer!r}")
    return current


def derive_strict_transport_schema(canonical_schema: dict[str, Any]) -> dict[str, Any]:
    """Return the only permitted v1.1 derivation without mutating its source."""
    derived = copy.deepcopy(canonical_schema)
    for pointer in EXPECTED_STRING_TYPE_PATCHES:
        node = _resolve_pointer(derived, pointer)
        if not isinstance(node, dict):
            raise ProtocolError(f"transport patch target is not an object: {pointer}")
        if "type" in node:
            raise ProtocolError(f"canonical transport patch target already has type: {pointer}")
        values: list[Any]
        if "const" in node:
            values = [node["const"]]
        elif "enum" in node and isinstance(node["enum"], list) and node["enum"]:
            values = list(node["enum"])
        else:
            raise ProtocolError(f"transport patch target is not a non-empty const/enum: {pointer}")
        if any(not isinstance(value, str) for value in values):
            raise ProtocolError(f"transport patch target is not homogeneously string-valued: {pointer}")
        node["type"] = "string"
    return derived


def _schema_types(node: dict[str, Any], path: str) -> tuple[str, ...]:
    raw = node.get("type")
    if raw is None:
        return ()
    values = (raw,) if isinstance(raw, str) else tuple(raw) if isinstance(raw, list) else ()
    if not values or any(not isinstance(value, str) or value not in JSON_SCHEMA_TYPES for value in values):
        raise StructuredOutputsPreflightError(
            f"{path}.type", "invalid_explicit_type", "type must name one or more JSON Schema primitive types"
        )
    if len(set(values)) != len(values):
        raise StructuredOutputsPreflightError(
            f"{path}.type", "duplicate_explicit_type", "type entries must be unique"
        )
    return values


def _validate_typed_values(node: dict[str, Any], path: str, types: tuple[str, ...]) -> None:
    if "const" in node and not any(json_type_matches(node["const"], item) for item in types):
        raise StructuredOutputsPreflightError(
            path, "const_type_mismatch", "const value does not match the explicit type"
        )
    if "enum" in node:
        enum = node["enum"]
        if not isinstance(enum, list) or not enum:
            raise StructuredOutputsPreflightError(path, "invalid_enum", "enum must be a non-empty array")
        for index, value in enumerate(enum):
            if not any(json_type_matches(value, item) for item in types):
                raise StructuredOutputsPreflightError(
                    f"{path}.enum[{index}]",
                    "enum_type_mismatch",
                    "enum value does not match the explicit type",
                )


def preflight_openai_structured_outputs_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Validate the locked strict subset and return deterministic check counts."""
    if not isinstance(schema, dict):
        raise StructuredOutputsPreflightError("$", "root_not_schema_object", "schema root must be an object")
    if "anyOf" in schema:
        raise StructuredOutputsPreflightError("$.anyOf", "root_any_of_forbidden", "root schema cannot use anyOf")
    if schema.get("type") != "object":
        raise StructuredOutputsPreflightError("$.type", "root_not_object", "root schema type must be object")

    counts = {"schema_nodes": 0, "object_nodes": 0, "ref_nodes": 0, "any_of_nodes": 0}
    visited_nodes: set[int] = set()

    def walk(node: dict[str, Any], path: str) -> None:
        if not isinstance(node, dict):
            raise StructuredOutputsPreflightError(path, "schema_node_not_object", "schema node must be an object")
        node_identity = id(node)
        if node_identity in visited_nodes:
            return
        visited_nodes.add(node_identity)
        counts["schema_nodes"] += 1

        for keyword in ("allOf", "oneOf", "not"):
            if keyword in node:
                raise StructuredOutputsPreflightError(
                    f"{path}.{keyword}", "unsupported_combinator", f"{keyword} is outside this strict subset"
                )

        if "$ref" in node:
            reference = node["$ref"]
            if not isinstance(reference, str) or not (reference == "#" or reference.startswith("#/")):
                raise StructuredOutputsPreflightError(
                    f"{path}.$ref", "unsupported_ref", "only local JSON Pointer references are allowed"
                )
            try:
                target = _resolve_pointer(schema, reference[1:])
            except ProtocolError as exc:
                raise StructuredOutputsPreflightError(
                    f"{path}.$ref", "unresolved_ref", f"reference does not resolve: {reference}"
                ) from exc
            if not isinstance(target, dict):
                raise StructuredOutputsPreflightError(
                    f"{path}.$ref", "invalid_ref_target", "reference target must be a schema object"
                )
            counts["ref_nodes"] += 1
            walk(target, f"{path}.$ref({reference})")

        if "anyOf" in node:
            branches = node["anyOf"]
            if not isinstance(branches, list) or not branches:
                raise StructuredOutputsPreflightError(
                    f"{path}.anyOf", "invalid_any_of", "nested anyOf must contain schema branches"
                )
            counts["any_of_nodes"] += 1
            for index, branch in enumerate(branches):
                walk(branch, f"{path}.anyOf[{index}]")

        types = _schema_types(node, path)
        if ("const" in node or "enum" in node) and not types:
            raise StructuredOutputsPreflightError(
                path,
                "const_or_enum_missing_explicit_type",
                "const/enum schema requires a determinable explicit type",
            )
        if not types and "$ref" not in node and "anyOf" not in node:
            raise StructuredOutputsPreflightError(
                path,
                "schema_node_missing_explicit_type",
                "schema node requires an explicit type, local $ref, or nested anyOf",
            )
        if types:
            _validate_typed_values(node, path, types)

        object_keywords = any(key in node for key in ("properties", "required", "additionalProperties"))
        if "object" in types or object_keywords:
            if "object" not in types:
                raise StructuredOutputsPreflightError(path, "object_missing_type", "object schema requires type=object")
            properties = node.get("properties")
            if not isinstance(properties, dict):
                raise StructuredOutputsPreflightError(
                    f"{path}.properties", "invalid_properties", "object schema requires a properties object"
                )
            if node.get("additionalProperties") is not False:
                raise StructuredOutputsPreflightError(
                    f"{path}.additionalProperties",
                    "additional_properties_not_false",
                    "every object must set additionalProperties=false",
                )
            required = node.get("required")
            if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
                raise StructuredOutputsPreflightError(
                    f"{path}.required", "invalid_required", "every object requires an explicit required array"
                )
            if len(set(required)) != len(required):
                raise StructuredOutputsPreflightError(
                    f"{path}.required", "duplicate_required", "required entries must be unique"
                )
            missing = [key for key in properties if key not in required]
            extras = [key for key in required if key not in properties]
            if missing or extras:
                raise StructuredOutputsPreflightError(
                    f"{path}.required",
                    "required_not_complete",
                    f"required must equal properties; missing={missing!r}, extras={extras!r}",
                )
            counts["object_nodes"] += 1
            for key, child in properties.items():
                walk(child, f"{path}.properties.{key}")

        array_keywords = any(key in node for key in ("items", "minItems"))
        if "array" in types or array_keywords:
            if "array" not in types:
                raise StructuredOutputsPreflightError(path, "array_missing_type", "array schema requires type=array")
            items = node.get("items")
            if not isinstance(items, dict):
                raise StructuredOutputsPreflightError(
                    f"{path}.items", "invalid_items", "array schema requires one items schema object"
                )
            walk(items, f"{path}.items")

        if "minLength" in node:
            value = node["minLength"]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or "string" not in types:
                raise StructuredOutputsPreflightError(
                    f"{path}.minLength", "invalid_min_length", "minLength requires a non-negative integer and string type"
                )
        if "minimum" in node:
            value = node["minimum"]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not ({"integer", "number"} & set(types))
            ):
                raise StructuredOutputsPreflightError(
                    f"{path}.minimum", "invalid_minimum", "minimum requires a numeric value and integer/number type"
                )
        if "minItems" in node:
            value = node["minItems"]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or "array" not in types:
                raise StructuredOutputsPreflightError(
                    f"{path}.minItems", "invalid_min_items", "minItems requires a non-negative integer and array type"
                )

        definitions = node.get("$defs")
        if definitions is not None:
            if not isinstance(definitions, dict):
                raise StructuredOutputsPreflightError(
                    f"{path}.$defs", "invalid_defs", "$defs must be an object"
                )
            for key, child in definitions.items():
                walk(child, f"{path}.$defs.{key}")

    walk(schema, "$")
    return {
        "passed": True,
        **counts,
        "first_error_path": None,
    }


def _validate_capability_profiles(config: dict[str, Any]) -> None:
    profiles = config.get("capability_profiles")
    if not isinstance(profiles, list) or len(profiles) != len(EXPECTED_PROFILE_CONTRACT):
        raise ProtocolError("transport adapter must contain exactly the seven locked C1 capability profiles")
    observed: dict[tuple[str, str, str], dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ProtocolError("capability profile must be an object")
        hosts = profile.get("endpoint_hosts")
        if not isinstance(hosts, list) or len(hosts) != 1 or not isinstance(hosts[0], str):
            raise ProtocolError("each locked C1 capability profile must name exactly one endpoint host")
        key = (profile.get("provider_adapter", ""), hosts[0], profile.get("model", ""))
        if key in observed:
            raise ProtocolError(f"duplicate transport capability profile: {key!r}")
        if profile.get("request_downgrade_allowed") is not False:
            raise ProtocolError("all C1 capability profiles must forbid request downgrade")
        observed[key] = {
            "profile_id": profile.get("profile_id"),
            "profile_version": profile.get("profile_version"),
            "status": profile.get("status"),
            "transport_schema_adapter_identity": profile.get("transport_schema_adapter_identity"),
            "blocking_paths": tuple(profile.get("blocking_paths", ())),
            "reason_codes": tuple(profile.get("reason_codes", ())),
        }
    if observed != EXPECTED_PROFILE_CONTRACT:
        raise ProtocolError("locked seven-model C1 capability profile contract drifted")


def _validate_portable_capability_profiles(config: dict[str, Any]) -> None:
    version = config.get("adapter_version")
    expected_policies = (
        EXPECTED_PORTABLE_PROFILE_POLICIES
        if version == "1.2.0"
        else EXPECTED_PORTABLE_V1_3_PROFILE_POLICIES
        if version in {"1.3.0", "1.4.0", "1.5.0"}
        else None
    )
    if expected_policies is None:
        raise ProtocolError("unsupported portable transport adapter version")
    profiles = config.get("capability_profiles")
    if not isinstance(profiles, list) or len(profiles) != len(expected_policies):
        raise ProtocolError("portable transport adapter must contain exactly seven capability profiles")
    observed: dict[tuple[str, str, str], tuple[Any, ...]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            raise ProtocolError("portable capability profile must be an object")
        hosts = profile.get("endpoint_hosts")
        if not isinstance(hosts, list) or len(hosts) != 1 or not isinstance(hosts[0], str):
            raise ProtocolError("each portable capability profile must name exactly one endpoint host")
        key = (profile.get("provider_adapter", ""), hosts[0], profile.get("model", ""))
        if key in observed:
            raise ProtocolError(f"duplicate portable transport capability profile: {key!r}")
        if profile.get("transport_schema_adapter_identity") != config.get("adapter_identity"):
            raise ProtocolError("portable capability profile adapter identity drifted")
        policy = profile.get("envelope_policy")
        if not isinstance(policy, dict):
            raise ProtocolError("portable capability profile requires an envelope_policy object")
        downgrade = profile.get("request_downgrade_applied")
        if not isinstance(downgrade, bool):
            raise ProtocolError("portable capability profile requires a boolean downgrade receipt")
        details = profile.get("request_downgrade_details")
        if not isinstance(details, list) or any(not isinstance(item, str) for item in details):
            raise ProtocolError("portable capability profile downgrade details must be strings")
        if bool(details) != downgrade:
            raise ProtocolError("portable capability profile downgrade receipt/details disagree")
        if profile.get("local_canonical_validation_required") is not True:
            raise ProtocolError("portable capability profile must require local canonical validation")
        response_mode = policy.get("response_format_mode")
        expected_enforcement = (
            "strict_json_schema" if response_mode == "json_schema_strict" else "json_syntax_only"
        )
        if profile.get("server_output_enforcement") != expected_enforcement:
            raise ProtocolError("portable capability profile server enforcement receipt drifted")
        observed_policy = (
            profile.get("status"),
            policy.get("message_mode"),
            policy.get("reasoning_effort_mode"),
            policy.get("token_limit_field"),
            response_mode,
            downgrade,
        )
        if version in {"1.3.0", "1.4.0", "1.5.0"}:
            coordinate_mode = profile.get("response_coordinate_mode")
            if coordinate_mode != RESPONSE_COORDINATE_MODE_UNIQUE_EXACT:
                raise ProtocolError(
                    "portable v1.3 profiles must use deterministic exact-text coordinate canonicalization"
                )
            observed_policy = (*observed_policy, coordinate_mode)
        elif "response_coordinate_mode" in profile:
            raise ProtocolError("portable v1.2 profiles cannot declare a response coordinate mode")
        observed[key] = observed_policy
    if observed != expected_policies:
        raise ProtocolError("locked seven-model portable capability profile contract drifted")
    guard = config.get("response_span_text_guard")
    if version in {"1.4.0", "1.5.0"}:
        expected_instruction = (
            SPAN_TEXT_GUARD_V1_4_INSTRUCTION
            if version == "1.4.0"
            else SPAN_TEXT_GUARD_INSTRUCTION
        )
        if guard != {
            "mode": SPAN_TEXT_GUARD_MODE,
            "instruction": expected_instruction,
            "canonical_semantic_request_unchanged": True,
            "canonical_prompt_assets_unchanged": True,
            "response_repair": "forbidden",
            "content_retry": "forbidden",
        }:
            raise ProtocolError(
                f"portable v{version.removesuffix('.0')} output guard contract drifted"
            )
    elif guard is not None:
        raise ProtocolError("portable adapters before v1.4 cannot declare a span-text guard")


def _validate_adapter_profiles(config: dict[str, Any]) -> None:
    version = config.get("adapter_version")
    if version == "1.1.0":
        _validate_capability_profiles(config)
    elif version in {"1.2.0", "1.3.0", "1.4.0", "1.5.0"}:
        _validate_portable_capability_profiles(config)
    else:
        raise ProtocolError("unsupported transport adapter version")


def _load_transport_adapter(config_path: Path, *, expected_version: str) -> StrictTransportAdapter:
    config, config_raw = _load_json_object(config_path)
    if config.get("schema_version") != (
        f"estg150_openai_strict_transport_schema_adapter_config@{expected_version}"
    ):
        raise ProtocolError("strict transport adapter config schema_version drifted")
    if config.get("adapter_id") != "estg150_openai_strict_transport_schema_adapter":
        raise ProtocolError("strict transport adapter ID drifted")
    if config.get("adapter_version") != expected_version:
        raise ProtocolError("strict transport adapter version drifted")
    if config.get("canonical_protocol_version") != "estg150_canonical_external_candidate_protocol@1.0.0":
        raise ProtocolError("strict transport adapter canonical protocol version drifted")
    expected_identity = f"{config.get('adapter_id')}@{config.get('adapter_version')}"
    if config.get("adapter_identity") != expected_identity:
        raise ProtocolError("strict transport adapter identity/version mismatch")
    pointers = tuple(config.get("transformation", {}).get("allowed_json_pointers", ()))
    if pointers != EXPECTED_STRING_TYPE_PATCHES:
        raise ProtocolError("strict transport adapter patch allowlist drifted")

    canonical_spec = config.get("canonical_schema", {})
    transport_spec = config.get("transport_schema", {})
    if canonical_spec.get("path") != "configs/schemas/estg150_ai_review_model_output.schema.json":
        raise ProtocolError("strict transport adapter canonical schema path drifted")
    if transport_spec.get("path") != (
        "configs/schemas/estg150_ai_review_model_output_openai_strict_transport_v1_1.schema.json"
    ):
        raise ProtocolError("strict transport adapter transport schema path drifted")
    canonical_path = _project_path(canonical_spec.get("path", ""))
    transport_path = _project_path(transport_spec.get("path", ""))
    canonical_schema, canonical_raw = _load_json_object(canonical_path)
    transport_schema, transport_raw = _load_json_object(transport_path)
    canonical_sha256 = sha256_bytes(canonical_raw)
    transport_sha256 = sha256_bytes(transport_raw)
    if canonical_sha256 != EXPECTED_CANONICAL_SCHEMA_SHA256 or canonical_sha256 != canonical_spec.get("sha256"):
        raise ProtocolError("canonical v1 output schema hash drifted")
    if transport_sha256 != transport_spec.get("sha256"):
        raise ProtocolError("strict transport schema hash drifted")
    if derive_strict_transport_schema(canonical_schema) != transport_schema:
        raise ProtocolError("strict transport schema contains changes outside the six allowed type additions")
    canonical_version = _resolve_pointer(canonical_schema, "/properties/schema_version").get("const")
    transport_version = _resolve_pointer(transport_schema, "/properties/schema_version").get("const")
    if canonical_version != transport_version or canonical_version != canonical_spec.get("output_schema_version"):
        raise ProtocolError("transport adaptation changed the model output schema_version const")
    if transport_spec.get("output_schema_version") != canonical_version:
        raise ProtocolError("transport schema metadata changed the model output schema version")

    try:
        preflight_openai_structured_outputs_schema(canonical_schema)
    except StructuredOutputsPreflightError as exc:
        canonical_error = {"path": exc.path, "code": exc.code, "error": str(exc)}
    else:
        raise ProtocolError("canonical schema unexpectedly passes the v1.1 strict transport preflight")
    if canonical_error["path"] != "$.properties.schema_version":
        raise ProtocolError("canonical schema first strict preflight error drifted")
    transport_preflight = preflight_openai_structured_outputs_schema(transport_schema)

    _validate_adapter_profiles(config)

    return StrictTransportAdapter(
        config=config,
        config_sha256=sha256_bytes(config_raw),
        adapter_id=config["adapter_id"],
        adapter_version=config["adapter_version"],
        adapter_identity=config["adapter_identity"],
        canonical_protocol_version=config["canonical_protocol_version"],
        canonical_schema_path=canonical_spec["path"],
        canonical_schema_sha256=canonical_sha256,
        transport_schema_path=transport_spec["path"],
        transport_schema_sha256=transport_sha256,
        canonical_schema=canonical_schema,
        transport_schema=transport_schema,
        canonical_preflight_error=canonical_error,
        transport_preflight=transport_preflight,
    )


def load_strict_transport_adapter() -> StrictTransportAdapter:
    """Load frozen v1.1 for verification of immutable historical receipts."""
    return _load_transport_adapter(TRANSPORT_ADAPTER_CONFIG_PATH, expected_version="1.1.0")


def load_portable_transport_adapter() -> StrictTransportAdapter:
    """Load v1.5 for new dry-runs and separately authorized API calls."""
    return _load_transport_adapter(PORTABLE_TRANSPORT_ADAPTER_CONFIG_PATH, expected_version="1.5.0")


def load_portable_transport_adapter_v1_4() -> StrictTransportAdapter:
    """Load immutable v1.4 for verification of historical guarded receipts."""
    return _load_transport_adapter(
        PORTABLE_TRANSPORT_ADAPTER_V1_4_CONFIG_PATH,
        expected_version="1.4.0",
    )


def load_portable_transport_adapter_v1_3() -> StrictTransportAdapter:
    """Load immutable v1.3 for verification of historical coordinate-portable receipts."""
    return _load_transport_adapter(
        PORTABLE_TRANSPORT_ADAPTER_V1_3_CONFIG_PATH,
        expected_version="1.3.0",
    )


def load_portable_transport_adapter_v1_2() -> StrictTransportAdapter:
    """Load immutable v1.2 for verification of historical portable receipts."""
    return _load_transport_adapter(
        PORTABLE_TRANSPORT_ADAPTER_V1_2_CONFIG_PATH,
        expected_version="1.2.0",
    )


def select_capability_profile(
    strict_adapter: StrictTransportAdapter,
    *,
    provider_adapter: str,
    endpoint_host: str,
    model: str,
) -> dict[str, Any]:
    _validate_adapter_profiles(strict_adapter.config)
    selected = None
    for profile in strict_adapter.config["capability_profiles"]:
        if (
            profile["provider_adapter"] == provider_adapter
            and profile["model"] == model.strip()
            and endpoint_host in profile["endpoint_hosts"]
        ):
            selected = profile
            break
    if selected is None:
        raise CapabilityPreflightError(
            "$.model",
            "no explicit offline capability profile exists for this provider/endpoint/model",
            profile_status="undeclared",
            reason_codes=("explicit_capability_profile_required",),
        )
    status = selected["status"]
    if status not in READY_PROFILE_STATUSES:
        paths = tuple(selected.get("blocking_paths") or ("$.model",))
        reasons = tuple(selected.get("reason_codes") or ("canonical_envelope_incompatible",))
        raise CapabilityPreflightError(
            paths[0],
            f"capability profile status={status}; reasons={list(reasons)!r}; request downgrade is forbidden",
            profile_status=status,
            reason_codes=reasons,
        )
    if selected.get("transport_schema_adapter_identity") != strict_adapter.adapter_identity:
        raise ProtocolError("ready capability profile does not bind the strict transport adapter")
    return copy.deepcopy(selected)


def _adapt_transport_messages(
    messages: Any,
    *,
    mode: str,
    canonical_schema_text: str,
    span_text_guard_instruction: str | None,
) -> list[dict[str, str]]:
    if not isinstance(messages, list) or len(messages) != 3:
        raise ProtocolError("canonical semantic request must contain exactly three messages")
    if [message.get("role") for message in messages if isinstance(message, dict)] != [
        "system",
        "developer",
        "user",
    ]:
        raise ProtocolError("canonical semantic request message roles drifted")
    if any(
        not isinstance(message, dict) or not isinstance(message.get("content"), str)
        for message in messages
    ):
        raise ProtocolError("canonical semantic request message content drifted")
    if mode == "preserve":
        adapted = copy.deepcopy(messages)
        if span_text_guard_instruction is not None:
            adapted[1]["content"] += "\n\n" + span_text_guard_instruction
        return adapted
    if mode not in {
        "merge_system_developer",
        "merge_system_developer_with_canonical_schema",
    }:
        raise ProtocolError(f"unsupported portable message mode: {mode!r}")
    merged = (
        messages[0]["content"]
        + "\n\n[BEGIN DEVELOPER INSTRUCTIONS]\n"
        + messages[1]["content"]
        + "\n[END DEVELOPER INSTRUCTIONS]"
    )
    if span_text_guard_instruction is not None:
        merged += "\n\n" + span_text_guard_instruction
    if mode == "merge_system_developer_with_canonical_schema":
        merged += (
            "\n\n[BEGIN CANONICAL JSON OUTPUT SCHEMA]\n"
            "Return exactly one JSON object matching this schema. "
            "Do not omit required semantic fields.\n"
            + canonical_schema_text
            + "[END CANONICAL JSON OUTPUT SCHEMA]"
        )
    return [
        {"role": "system", "content": merged},
        copy.deepcopy(messages[2]),
    ]


def prepare_transport_request(
    semantic_request: dict[str, Any],
    *,
    provider: ProviderAdapter,
    endpoint_host: str,
    model: str,
    strict_adapter: StrictTransportAdapter,
) -> PreparedTransportRequest:
    if derive_strict_transport_schema(strict_adapter.canonical_schema) != strict_adapter.transport_schema:
        raise ProtocolError("in-memory strict transport schema drifted after adapter load")
    preflight_openai_structured_outputs_schema(strict_adapter.transport_schema)
    if semantic_request.get("protocol_version") != strict_adapter.canonical_protocol_version:
        raise ProtocolError("strict transport adapter canonical protocol version mismatch")
    schema_text = semantic_request.get("output_schema_text")
    if not isinstance(schema_text, str):
        raise ProtocolError("canonical semantic request has no output_schema_text")
    if sha256_bytes(schema_text.encode("utf-8")) != strict_adapter.canonical_schema_sha256:
        raise ProtocolError("canonical semantic request schema bytes drifted before transport adaptation")
    if json.loads(schema_text) != strict_adapter.canonical_schema:
        raise ProtocolError("canonical semantic request schema object drifted before transport adaptation")

    profile = select_capability_profile(
        strict_adapter,
        provider_adapter=provider.adapter_id,
        endpoint_host=endpoint_host,
        model=model,
    )
    body = provider.build_transport_body(semantic_request, model=model)
    controls = semantic_request["generation_controls"]
    canonical_top_level_keys = {
        "model",
        "messages",
        "reasoning_effort",
        "max_completion_tokens",
        "response_format",
    }
    if set(body) != canonical_top_level_keys:
        raise ProtocolError(
            f"canonical provider envelope top-level keys drifted: "
            f"{sorted(set(body) - canonical_top_level_keys)!r}"
        )
    if body.get("model") != model:
        raise ProtocolError("transport envelope model differs from the capability-profile model")
    if body["messages"] != semantic_request["messages"]:
        raise ProtocolError("provider changed canonical messages before transport adaptation")
    if body.get("reasoning_effort") != controls["reasoning_effort"]:
        raise ProtocolError("provider changed canonical reasoning_effort before transport adaptation")
    if body.get("max_completion_tokens") != controls["max_completion_tokens"]:
        raise ProtocolError("provider changed canonical max_completion_tokens before transport adaptation")
    canonical_response_format = body.get("response_format", {})
    if set(canonical_response_format) != {"type", "json_schema"}:
        raise ProtocolError("provider changed canonical response_format members before adaptation")
    json_schema_envelope = canonical_response_format.get("json_schema", {})
    if set(json_schema_envelope) != {"name", "strict", "schema"}:
        raise ProtocolError("provider changed canonical json_schema members before adaptation")
    if (
        canonical_response_format.get("type") != "json_schema"
        or json_schema_envelope.get("name") != "estg150_ai_review_candidate"
        or json_schema_envelope.get("strict") is not True
    ):
        raise ProtocolError("provider changed canonical strict json_schema before adaptation")

    policy = profile.get("envelope_policy")
    if not isinstance(policy, dict):
        # Frozen v1.1 profiles predate explicit envelope policies and preserve
        # the original request byte-for-byte except for the strict schema patch.
        policy = {
            "message_mode": "preserve",
            "reasoning_effort_mode": "preserve",
            "token_limit_field": "max_completion_tokens",
            "response_format_mode": "json_schema_strict",
        }
    body["messages"] = _adapt_transport_messages(
        semantic_request["messages"],
        mode=policy["message_mode"],
        canonical_schema_text=schema_text,
        span_text_guard_instruction=(
            strict_adapter.config["response_span_text_guard"]["instruction"]
            if "response_span_text_guard" in strict_adapter.config
            else None
        ),
    )
    reasoning_mode = policy["reasoning_effort_mode"]
    if reasoning_mode == "omit":
        body.pop("reasoning_effort")
    elif reasoning_mode != "preserve":
        raise ProtocolError(f"unsupported reasoning_effort mode: {reasoning_mode!r}")

    token_limit_field = policy["token_limit_field"]
    if token_limit_field == "max_tokens":
        body["max_tokens"] = body.pop("max_completion_tokens")
    elif token_limit_field != "max_completion_tokens":
        raise ProtocolError(f"unsupported token limit field: {token_limit_field!r}")

    response_mode = policy["response_format_mode"]
    if response_mode == "json_schema_strict":
        body["response_format"]["json_schema"]["schema"] = copy.deepcopy(
            strict_adapter.transport_schema
        )
        preflight_openai_structured_outputs_schema(
            body["response_format"]["json_schema"]["schema"]
        )
    elif response_mode == "json_object":
        body["response_format"] = {"type": "json_object"}
    else:
        raise ProtocolError(f"unsupported response format mode: {response_mode!r}")

    expected_top_level_keys = {"model", "messages", token_limit_field, "response_format"}
    if reasoning_mode == "preserve":
        expected_top_level_keys.add("reasoning_effort")
    if set(body) != expected_top_level_keys:
        raise ProtocolError(f"adapted transport envelope keys drifted: {sorted(body)!r}")
    if body[token_limit_field] != controls["max_completion_tokens"]:
        raise ProtocolError("transport token ceiling changed during capability adaptation")
    if response_mode == "json_schema_strict":
        adapted_format = body["response_format"]
        adapted_schema_envelope = adapted_format.get("json_schema", {})
        if (
            adapted_format.get("type") != "json_schema"
            or adapted_schema_envelope.get("name") != "estg150_ai_review_candidate"
            or adapted_schema_envelope.get("strict") is not True
            or adapted_schema_envelope.get("schema") != strict_adapter.transport_schema
        ):
            raise ProtocolError("strict json_schema transport adaptation drifted")
    elif body["response_format"] != {"type": "json_object"}:
        raise ProtocolError("JSON-mode transport adaptation drifted")
    return PreparedTransportRequest(body=body, strict_adapter=strict_adapter, capability_profile=profile)


def transport_provenance(
    prepared: PreparedTransportRequest,
    *,
    canonical_serializer_sha256: str,
    transport_request_sha256: str | None,
    local_canonical_validation: dict[str, Any] | None,
) -> dict[str, Any]:
    strict_adapter = prepared.strict_adapter
    profile = prepared.capability_profile
    policy = profile.get("envelope_policy") or {
        "message_mode": "preserve",
        "reasoning_effort_mode": "preserve",
        "token_limit_field": "max_completion_tokens",
        "response_format_mode": "json_schema_strict",
    }
    request_downgrade_applied = bool(profile.get("request_downgrade_applied", False))
    request_downgrade_details = copy.deepcopy(profile.get("request_downgrade_details", []))
    response_coordinate_mode = profile.get(
        "response_coordinate_mode", RESPONSE_COORDINATE_MODE_REJECT_INVALID
    )
    guard_config = strict_adapter.config.get("response_span_text_guard")
    guard_receipt = (
        {
            "mode": guard_config["mode"],
            "applied": True,
            "instruction_sha256": sha256_bytes(guard_config["instruction"].encode("utf-8")),
            "canonical_semantic_request_unchanged": guard_config[
                "canonical_semantic_request_unchanged"
            ],
            "canonical_prompt_assets_unchanged": guard_config[
                "canonical_prompt_assets_unchanged"
            ],
            "response_repair": guard_config["response_repair"],
            "content_retry": guard_config["content_retry"],
        }
        if guard_config is not None
        else {"mode": "none", "applied": False}
    )
    return {
        "canonical_protocol_version": strict_adapter.canonical_protocol_version,
        "canonical_schema_path": strict_adapter.canonical_schema_path,
        "canonical_schema_sha256": strict_adapter.canonical_schema_sha256,
        "transport_adapter_id": strict_adapter.adapter_id,
        "transport_adapter_version": strict_adapter.adapter_version,
        "transport_adapter_config_sha256": strict_adapter.config_sha256,
        "transport_schema_path": strict_adapter.transport_schema_path,
        "transport_schema_sha256": strict_adapter.transport_schema_sha256,
        "canonical_serializer_sha256": canonical_serializer_sha256,
        "transport_request_sha256": transport_request_sha256,
        "capability_profile_id": profile["profile_id"],
        "capability_profile_version": profile["profile_version"],
        "capability_profile_status": profile["status"],
        "structured_outputs_preflight": copy.deepcopy(strict_adapter.transport_preflight),
        "transport_envelope_policy": copy.deepcopy(policy),
        "server_output_enforcement": profile.get(
            "server_output_enforcement", "strict_json_schema"
        ),
        "local_canonical_validation_required": profile.get(
            "local_canonical_validation_required", True
        ),
        "local_canonical_validation": copy.deepcopy(local_canonical_validation),
        "transport_schema_adaptation_applied": True,
        "transport_capability_adaptation_applied": (
            policy
            != {
                "message_mode": "preserve",
                "reasoning_effort_mode": "preserve",
                "token_limit_field": "max_completion_tokens",
                "response_format_mode": "json_schema_strict",
            }
            or guard_receipt["applied"]
        ),
        "semantic_contract_downgrade_applied": False,
        "response_coordinate_mode": response_coordinate_mode,
        "response_span_text_guard": guard_receipt,
        "request_downgrade_applied": request_downgrade_applied,
        "request_downgrade_details": request_downgrade_details,
    }


def serialized_transport_sha256(prepared: PreparedTransportRequest) -> str:
    return sha256_bytes(canonical_json_bytes(prepared.body))

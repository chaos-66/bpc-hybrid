"""Canonical external EStG-150 candidate protocol and provider adapters.

The archived internal Sol run did not preserve its hidden system prompt or API
envelope.  This module therefore binds the visible historical assets and
routing while defining one new external serializer for every future provider.
It never loads Layer D, Layer E, Gold, or evaluation-derived sidecars.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import http.client
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "estg150_candidate_protocol_v1.json"
LOCK_PATH = ROOT / "configs" / "estg150_candidate_protocol_v1.lock.json"
SYNTHETIC_FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "estg150_candidate_protocol" / "synthetic_record_v1.json"
)
SEMANTIC_FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "estg150_candidate_protocol"
    / "canonical_semantic_request_v1.json"
)
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")
NORMATIVE_CUE_RE = re.compile(
    r"\b(?:shall|must|may|is\s+required\s+to|are\s+required\s+to|"
    r"is\s+prohibited|are\s+prohibited|forbidden|means|is\s+defined\s+as)\b",
    re.IGNORECASE,
)


class ProtocolError(RuntimeError):
    """A locked protocol invariant failed."""


class ProviderHTTPError(ProtocolError):
    """A terminal provider HTTP response, with bounded diagnostics attached."""

    def __init__(
        self,
        message: str,
        *,
        http_status: int | None = None,
        response_body: bytes | None = None,
        response_body_truncated: bool = False,
        provider_request_id: str | None = None,
        retry_reasons: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.response_body = response_body
        self.response_body_truncated = response_body_truncated
        self.provider_request_id = provider_request_id
        self.retry_reasons = retry_reasons


class ProtocolIncompatible(ProviderHTTPError):
    """A provider cannot honor the strict protocol."""


class CandidateValidationError(ProtocolError):
    """A provider response is not a valid candidate."""


class RetryableTransportError(ProtocolError):
    """A network timeout or explicitly retryable HTTP status occurred."""

    def __init__(
        self,
        message: str,
        *,
        retry_reasons: tuple[str, ...] = (),
        terminal_network_error_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_reasons = retry_reasons
        self.terminal_network_error_type = terminal_network_error_type


@dataclass(frozen=True)
class ProtocolAssets:
    config: dict[str, Any]
    schema: dict[str, Any]
    schema_text: str
    prompts: dict[str, str]
    samples: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ProviderAdapter:
    adapter_id: str
    transport_family: str
    allowed_endpoint_hosts: tuple[str, ...]
    endpoint_host_policy: str
    provider_identity_attestation: str

    def validate_endpoint(self, endpoint: str) -> tuple[str, str]:
        parsed = urllib.parse.urlsplit(endpoint.strip())
        if parsed.scheme.lower() != "https":
            raise ProtocolIncompatible("provider endpoint must use HTTPS")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ProtocolIncompatible("endpoint userinfo, query strings, and fragments are forbidden")
        host = (parsed.hostname or "").lower()
        if not host:
            raise ProtocolIncompatible("provider endpoint has no host")
        if self.allowed_endpoint_hosts and host not in self.allowed_endpoint_hosts:
            raise ProtocolIncompatible(
                f"adapter {self.adapter_id} requires one of {self.allowed_endpoint_hosts!r}; got {host!r}"
            )
        normalized = urllib.parse.urlunsplit(("https", parsed.netloc, parsed.path or "/", "", ""))
        return normalized, host

    def build_transport_body(self, semantic_request: dict[str, Any], *, model: str) -> dict[str, Any]:
        if self.transport_family != "openai_chat_completions":
            raise ProtocolIncompatible(f"unsupported transport family: {self.transport_family}")
        if not model.strip():
            raise ProtocolIncompatible("model ID must be explicit")
        schema = json.loads(semantic_request["output_schema_text"])
        controls = semantic_request["generation_controls"]
        if controls.get("strict_json_schema") is not True:
            raise ProtocolIncompatible("strict JSON Schema is mandatory")
        return {
            "model": model,
            "messages": semantic_request["messages"],
            "reasoning_effort": controls["reasoning_effort"],
            "max_completion_tokens": controls["max_completion_tokens"],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "estg150_ai_review_candidate",
                    "strict": True,
                    "schema": schema,
                },
            },
        }


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def load_json_bytes(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(value, dict):
        raise ProtocolError(f"{path} must contain a JSON object")
    return value


def load_jsonl_bytes(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_bytes().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ProtocolError(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def _locked_bytes(config: dict[str, Any], asset_name: str) -> tuple[Path, bytes]:
    spec = config["assets"][asset_name]
    path = ROOT / spec["path"]
    raw = path.read_bytes()
    actual = sha256_bytes(raw)
    if actual != spec["sha256"]:
        raise ProtocolError(
            f"locked asset hash mismatch for {asset_name}: expected={spec['sha256']}, actual={actual}"
        )
    return path, raw


def compact_legacy_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """Use the archived visible Layer-C projection; it remains fallible advice."""
    clauses: list[dict[str, Any]] = []
    for clause in row.get("clauses") or []:
        compact: dict[str, Any] = {"clause_id": clause.get("clause_id")}
        for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
            value = clause.get(field)
            compact[field] = value.get("value") if isinstance(value, dict) else value
        clauses.append(compact)
    return {"clauses": clauses}


def load_protocol_assets() -> ProtocolAssets:
    config = load_json_bytes(CONFIG_PATH)
    membership_spec = config["assets"]["membership"]
    membership = load_json_bytes(ROOT / membership_spec["path"])
    actual_membership = membership["selected_membership"]["membership_payload_sha256"]
    if actual_membership != membership_spec["payload_sha256"]:
        raise ProtocolError(
            "membership payload hash mismatch: "
            f"expected={membership_spec['payload_sha256']}, actual={actual_membership}"
        )

    layer_paths: dict[str, Path] = {}
    layer_raw: dict[str, bytes] = {}
    for name in ("layer_a", "layer_b", "layer_c", "output_schema", "full_extract_prompt", "pass_a_prompt", "pass_b_prompt"):
        layer_paths[name], layer_raw[name] = _locked_bytes(config, name)

    a_rows = load_jsonl_bytes(layer_paths["layer_a"])
    b_rows = load_jsonl_bytes(layer_paths["layer_b"])
    c_rows = load_jsonl_bytes(layer_paths["layer_c"])
    if len(a_rows) != 150 or len(b_rows) != 150 or len(c_rows) != 150:
        raise ProtocolError("Layer A/B/C must each contain exactly 150 records")
    b_by_legacy = {str(row["legacy_record_id"]): row for row in b_rows}
    c_by_sample = {row["sample_id"]: row for row in c_rows}
    a_ids = [str(row["id"]) for row in a_rows]
    if len(set(a_ids)) != 150 or set(a_ids) != set(b_by_legacy):
        raise ProtocolError("Layer A/B membership mismatch")
    if {row["sample_id"] for row in b_rows} != set(c_by_sample):
        raise ProtocolError("Layer B/C membership mismatch")

    samples: list[dict[str, Any]] = []
    for sample_index, source in enumerate(a_rows):
        translation = b_by_legacy[str(source["id"])]
        sample_id = translation["sample_id"]
        samples.append(
            {
                "sample_index": sample_index,
                "sample_id": sample_id,
                "legacy_record_id": source["id"],
                "raw_text_de": source.get("raw_text_de", source.get("text")),
                "frozen_candidate_text_en": translation["candidate_text_en"],
                "legacy_six_element_draft": compact_legacy_candidate(c_by_sample[sample_id]),
            }
        )
    if any(not row["raw_text_de"] or not row["frozen_candidate_text_en"] for row in samples):
        raise ProtocolError("Layer A/B contains an empty locked text")

    schema_text = layer_raw["output_schema"].decode("utf-8")
    schema = json.loads(schema_text)
    prompts = {
        "full_extract": layer_raw["full_extract_prompt"].decode("utf-8"),
        "pass_a": layer_raw["pass_a_prompt"].decode("utf-8"),
        "pass_b": layer_raw["pass_b_prompt"].decode("utf-8"),
    }
    return ProtocolAssets(config, schema, schema_text, prompts, tuple(samples))


def route_for_index(sample_index: int) -> tuple[str, ...]:
    if 0 <= sample_index <= 2:
        return ("pass_a", "pass_b")
    if 3 <= sample_index <= 149:
        return ("full_extract",)
    raise ProtocolError("sample index must be in [0, 150)")


def build_user_object(
    sample: dict[str, Any], *, route: str, pass_a_candidate: dict[str, Any] | None = None
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "sample_id": sample["sample_id"],
        "raw_text_de": sample["raw_text_de"],
        "frozen_candidate_text_en": sample["frozen_candidate_text_en"],
    }
    if route == "pass_a":
        if pass_a_candidate is not None:
            raise ProtocolError("pass_a cannot receive a prior candidate")
    elif route == "pass_b":
        if pass_a_candidate is None:
            raise ProtocolError("pass_b requires the complete validated pass_a output")
        value["pass_a_candidate"] = pass_a_candidate
        value["legacy_six_element_draft"] = sample["legacy_six_element_draft"]
    elif route == "full_extract":
        if pass_a_candidate is not None:
            raise ProtocolError("full_extract cannot receive a pass_a candidate")
        value["legacy_six_element_draft"] = sample["legacy_six_element_draft"]
    else:
        raise ProtocolError(f"unknown route: {route}")
    return value


def build_semantic_request(
    assets: ProtocolAssets,
    sample: dict[str, Any],
    *,
    route: str,
    pass_a_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if route not in route_for_index(int(sample["sample_index"])):
        raise ProtocolError(f"route {route!r} is not permitted for index {sample['sample_index']}")
    user_object = build_user_object(sample, route=route, pass_a_candidate=pass_a_candidate)
    user_content = canonical_json_bytes(user_object).decode("utf-8")[:-1]
    message_contract = assets.config["message_contract"]
    messages = [
        {"role": "system", "content": message_contract["system_message"]},
        {"role": "developer", "content": assets.prompts[route]},
        {"role": "user", "content": user_content},
    ]
    if [message["role"] for message in messages] != message_contract["role_order"]:
        raise ProtocolError("canonical message role order drifted")
    return {
        "schema_version": "estg150_canonical_semantic_request@1.0.0",
        "protocol_version": assets.config["protocol_version"],
        "serializer_version": assets.config["serializer_version"],
        "route": route,
        "sample_index": sample["sample_index"],
        "sample_id": sample["sample_id"],
        "messages": messages,
        "output_schema_name": "estg150_ai_review_candidate",
        "output_schema_text": assets.schema_text,
        "generation_controls": assets.config["generation_controls"],
        "response_contract": assets.config["response_contract"],
        "validation_contract": assets.config["validation_contract"],
    }


def serialize_semantic_request(value: dict[str, Any]) -> bytes:
    return canonical_json_bytes(value)


def serializer_identity(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "serializer_version": config["serializer_version"],
        "message_contract": config["message_contract"],
        "route_contract": config["route_contract"],
        "serialization": config["serialization"],
        "generation_controls": config["generation_controls"],
        "response_contract": config["response_contract"],
        "validation_contract": config["validation_contract"],
        "asset_hashes": {
            name: spec["sha256"]
            for name, spec in config["assets"].items()
            if isinstance(spec, dict) and "sha256" in spec
        },
        "membership_payload_sha256": config["assets"]["membership"]["payload_sha256"],
    }


def serializer_sha256(config: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(serializer_identity(config)))


def adapter_from_config(config: dict[str, Any], adapter_id: str) -> ProviderAdapter:
    try:
        spec = config["provider_adapters"][adapter_id]
    except KeyError as exc:
        raise ProtocolIncompatible(f"unknown provider adapter: {adapter_id}") from exc
    return ProviderAdapter(
        adapter_id=adapter_id,
        transport_family=spec["transport_family"],
        allowed_endpoint_hosts=tuple(spec["allowed_endpoint_hosts"]),
        endpoint_host_policy=spec["endpoint_host_policy"],
        provider_identity_attestation=spec["provider_identity_attestation"],
    )


def validate_candidate(
    value: dict[str, Any], *, expected_sample_id: str, frozen_candidate_text_en: str,
    schema: dict[str, Any]
) -> dict[str, bool]:
    validate_schema_subset(value, schema, root_schema=schema, path="$model_output")
    if value["sample_id"] != expected_sample_id:
        raise CandidateValidationError("sample_id mismatch")
    text = value["translation"]["proposed_text_en"]
    decision = value["translation"]["decision"]
    if decision == "accepted" and text != frozen_candidate_text_en:
        raise CandidateValidationError("accepted translation differs from frozen candidate")
    if decision == "edited" and text == frozen_candidate_text_en:
        raise CandidateValidationError("edited translation is unchanged")
    if value["context_sufficiency"] == "insufficient" and not any(
        item["field"] == "context" for item in value["unsupported_or_ambiguous"]
    ):
        raise CandidateValidationError("insufficient context requires a context ambiguity")

    clause_ids: set[str] = set()
    clause_ranges: list[tuple[int, int]] = []
    for clause_index, clause in enumerate(value["clauses"]):
        clause_path = f"clauses[{clause_index}]"
        if clause["clause_id"] in clause_ids:
            raise CandidateValidationError(f"{clause_path}.clause_id is duplicated")
        clause_ids.add(clause["clause_id"])
        c_start, c_end = validate_span(clause["clause_span"], text, f"{clause_path}.clause_span")
        clause_ranges.append((c_start, c_end))
        for evidence_index, span in enumerate(clause["modality"]["evidence"]):
            start, end = validate_span(span, text, f"{clause_path}.modality.evidence[{evidence_index}]")
            require_inside_clause(start, end, c_start, c_end, f"{clause_path}.modality.evidence[{evidence_index}]")
        ids_by_field: dict[str, set[str]] = {}
        all_ids: set[str] = set()
        for field in ("actors", "actions", "conditions", "constraints", "exceptions"):
            ids_by_field[field] = set()
            for item_index, span in enumerate(clause[field]):
                path = f"{clause_path}.{field}[{item_index}]"
                start, end = validate_span(span, text, path)
                require_inside_clause(start, end, c_start, c_end, path)
                if span["id"] in all_ids:
                    raise CandidateValidationError(f"{path}.id is duplicated within the clause")
                all_ids.add(span["id"])
                ids_by_field[field].add(span["id"])
        for edge_index, edge in enumerate(clause["actor_action_map"]):
            path = f"{clause_path}.actor_action_map[{edge_index}]"
            if edge["actor_id"] is not None and edge["actor_id"] not in ids_by_field["actors"]:
                raise CandidateValidationError(f"{path}.actor_id references an unknown actor")
            if edge["action_id"] not in ids_by_field["actions"]:
                raise CandidateValidationError(f"{path}.action_id references an unknown action")
        for relation_index, relation in enumerate(clause["order_relations"]):
            path = f"{clause_path}.order_relations[{relation_index}]"
            if relation["before_action_id"] not in ids_by_field["actions"]:
                raise CandidateValidationError(f"{path}.before_action_id references an unknown action")
            if relation["after_action_id"] not in ids_by_field["actions"]:
                raise CandidateValidationError(f"{path}.after_action_id references an unknown action")
            for evidence_index, span in enumerate(relation["evidence"]):
                start, end = validate_span(span, text, f"{path}.evidence[{evidence_index}]")
                require_inside_clause(start, end, c_start, c_end, f"{path}.evidence[{evidence_index}]")

    uncovered = [
        match.group(0)
        for match in NORMATIVE_CUE_RE.finditer(text)
        if not any(start <= match.start() and match.end() <= end for start, end in clause_ranges)
    ]
    if uncovered:
        raise CandidateValidationError(f"obvious normative cues fall outside every clause: {uncovered!r}")
    return {"schema_valid": True, "exact_span_valid": True, "normative_cue_coverage_valid": True}


def validate_schema_subset(value: Any, schema: dict[str, Any], *, root_schema: dict[str, Any], path: str) -> None:
    if "$ref" in schema:
        reference = schema["$ref"]
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ProtocolError(f"unsupported schema reference: {reference}")
        validate_schema_subset(
            value, root_schema["$defs"][reference[len(prefix):]], root_schema=root_schema, path=path
        )
        return
    if "const" in schema and value != schema["const"]:
        raise CandidateValidationError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise CandidateValidationError(f"{path} must be one of {schema['enum']!r}")
    expected_type = schema.get("type")
    if expected_type is not None:
        allowed = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(json_type_matches(value, item) for item in allowed):
            raise CandidateValidationError(f"{path} must have JSON type {expected_type!r}")
    if isinstance(value, dict):
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            raise CandidateValidationError(f"{path} is missing required properties {missing!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise CandidateValidationError(f"{path} has additional properties {extras!r}")
        for key, child in value.items():
            if key in properties:
                validate_schema_subset(child, properties[key], root_schema=root_schema, path=f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            raise CandidateValidationError(f"{path} has fewer than {schema['minItems']} items")
        if isinstance(schema.get("items"), dict):
            for index, child in enumerate(value):
                validate_schema_subset(
                    child, schema["items"], root_schema=root_schema, path=f"{path}[{index}]"
                )
    if isinstance(value, str) and len(value) < int(schema.get("minLength", 0)):
        raise CandidateValidationError(f"{path} is shorter than minLength={schema['minLength']}")
    if isinstance(value, int) and not isinstance(value, bool) and "minimum" in schema:
        if value < schema["minimum"]:
            raise CandidateValidationError(f"{path} is below minimum={schema['minimum']}")


def json_type_matches(value: Any, expected_type: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected_type, False)


def validate_span(span: dict[str, Any], source: str, path: str) -> tuple[int, int]:
    start, end = span["start"], span["end"]
    if not (0 <= start < end <= len(source)):
        raise CandidateValidationError(f"{path} is outside proposed_text_en")
    if source[start:end] != span["text"]:
        raise CandidateValidationError(f"{path}.text does not match proposed_text_en[start:end]")
    return start, end


def require_inside_clause(start: int, end: int, clause_start: int, clause_end: int, path: str) -> None:
    if start < clause_start or end > clause_end:
        raise CandidateValidationError(f"{path} is outside its clause_span")


def extract_provider_response_envelope(
    response_bytes: bytes,
    *,
    adapter: ProviderAdapter,
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """Parse provider envelope and usage before candidate validation.

    Provider usage is billable transport evidence even when the structured
    candidate later fails the canonical validator.
    """
    try:
        response = json.loads(response_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolIncompatible("provider response is not UTF-8 JSON") from exc
    if not isinstance(response, dict):
        raise ProtocolIncompatible("provider response outer value is not an object")
    try:
        choice = response["choices"][0]
        content = choice["message"]["content"]
        finish_reason = choice["finish_reason"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProtocolIncompatible("provider response lacks choices[0].message.content") from exc
    if finish_reason != "stop":
        raise ProtocolIncompatible(f"provider finish_reason is {finish_reason!r}, not 'stop'")
    if not isinstance(content, str):
        raise ProtocolIncompatible("provider structured-output content is not a JSON string")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ProtocolIncompatible("provider response omitted token usage")
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        raise ProtocolIncompatible("provider response token usage is incomplete")
    metadata = {
        "provider_reported_model": response.get("model"),
        "provider_response_id": response.get("id"),
        "provider_identity_attestation": adapter.provider_identity_attestation,
        "finish_reason": finish_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "response_sha256": sha256_bytes(response_bytes),
    }
    return response, content, metadata


def extract_provider_response(
    response_bytes: bytes,
    *,
    adapter: ProviderAdapter,
    expected_sample_id: str,
    frozen_candidate_text_en: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _response, content, metadata = extract_provider_response_envelope(
        response_bytes, adapter=adapter
    )
    try:
        candidate = json.loads(content)
    except json.JSONDecodeError as exc:
        raise CandidateValidationError("structured-output content is invalid JSON; repair is forbidden") from exc
    if not isinstance(candidate, dict):
        raise CandidateValidationError("structured-output content is not an object")
    validation = validate_candidate(
        candidate,
        expected_sample_id=expected_sample_id,
        frozen_candidate_text_en=frozen_candidate_text_en,
        schema=schema,
    )
    metadata["validation"] = validation
    return candidate, metadata


def post_identical_request_with_retries(
    *, endpoint: str, api_key: str, request_bytes: bytes, timeout_seconds: int,
    max_network_retries: int, retryable_statuses: set[int]
) -> tuple[bytes, list[str]]:
    """Retry only transport failures and always resend identical request bytes."""
    error_body_limit = 1024 * 1024
    reasons: list[str] = []
    for attempt in range(max_network_retries + 1):
        request = urllib.request.Request(
            endpoint,
            data=request_bytes,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return response.read(), reasons
        except urllib.error.HTTPError as exc:
            if exc.code not in retryable_statuses or attempt >= max_network_retries:
                response_body = exc.read(error_body_limit + 1)
                response_body_truncated = len(response_body) > error_body_limit
                response_body = response_body[:error_body_limit]
                request_id = None
                for header_name in ("x-request-id", "request-id", "x-trace-id", "cf-ray"):
                    header_value = exc.headers.get(header_name) if exc.headers is not None else None
                    if header_value:
                        request_id = re.sub(r"[\x00-\x1f\x7f]", "?", str(header_value))[:512]
                        break
                exc.close()
                if exc.code in {400, 404, 409, 415, 422}:
                    raise ProtocolIncompatible(
                        f"provider rejected the fixed strict request envelope with HTTP {exc.code}",
                        http_status=exc.code,
                        response_body=response_body,
                        response_body_truncated=response_body_truncated,
                        provider_request_id=request_id,
                        retry_reasons=tuple(reasons),
                    ) from exc
                raise ProviderHTTPError(
                    f"non-retryable or exhausted HTTP status: {exc.code}",
                    http_status=exc.code,
                    response_body=response_body,
                    response_body_truncated=response_body_truncated,
                    provider_request_id=request_id,
                    retry_reasons=tuple(reasons),
                ) from exc
            reasons.append(f"http_{exc.code}")
            exc.close()
        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            http.client.RemoteDisconnected,
        ) as exc:
            if attempt >= max_network_retries:
                raise RetryableTransportError(
                    "network timeout/error retry budget exhausted",
                    retry_reasons=tuple(reasons),
                    terminal_network_error_type=type(exc).__name__,
                ) from exc
            reasons.append("network_timeout_or_url_error")
    raise AssertionError("unreachable")


def generate_c0_lock_payload(assets: ProtocolAssets, semantic_fixture_bytes: bytes) -> dict[str, Any]:
    return {
        "schema_version": "estg150_candidate_protocol_lock@1.0.0",
        "protocol_version": assets.config["protocol_version"],
        "serializer_version": assets.config["serializer_version"],
        "config_sha256": sha256_path(CONFIG_PATH),
        "serializer_sha256": serializer_sha256(assets.config),
        "serializer_fixture_path": str(SEMANTIC_FIXTURE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "serializer_fixture_sha256": sha256_bytes(semantic_fixture_bytes),
        "historical_hidden_transport_payload_not_archived": True,
        "asset_hashes": {
            "membership_payload_sha256": assets.config["assets"]["membership"]["payload_sha256"],
            **{
                name: spec["sha256"]
                for name, spec in assets.config["assets"].items()
                if isinstance(spec, dict) and "sha256" in spec
            },
        },
    }


def verify_c0_lock(assets: ProtocolAssets) -> dict[str, Any]:
    if not LOCK_PATH.exists() or not SEMANTIC_FIXTURE_PATH.exists():
        raise ProtocolError("C0 lock or serializer fixture is missing")
    fixture_bytes = SEMANTIC_FIXTURE_PATH.read_bytes()
    expected = generate_c0_lock_payload(assets, fixture_bytes)
    actual = load_json_bytes(LOCK_PATH)
    if actual != expected:
        raise ProtocolError("C0 lock payload drifted")
    synthetic = load_json_bytes(SYNTHETIC_FIXTURE_PATH)
    semantic = build_semantic_request(assets, synthetic, route="full_extract")
    if serialize_semantic_request(semantic) != fixture_bytes:
        raise ProtocolError("canonical semantic serializer fixture drifted")
    return actual


def safe_run_dir(config: dict[str, Any], run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ProtocolError("run_id must match [A-Za-z0-9][A-Za-z0-9._-]{0,95}")
    root = (ROOT / config["output"]["root"]).resolve()
    target = (root / run_id).resolve()
    if target.parent != root:
        raise ProtocolError("unsafe run directory")
    return target

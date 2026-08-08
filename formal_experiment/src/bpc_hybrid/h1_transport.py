"""H1 DeepSeek transport contract: request policy, envelope decoding,
sanitized capture, and offline replay support (S2.8D-R1).

Pure, offline functions only -- no network, no ``.env``, no API keys.
The real transport and the offline fixture replay both call the same
:func:`decode_chat_completion_envelope`, so extraction behavior is
identical on both paths.

Key rules:

* The H1 pinned deepseek-v4-pro request policy is explicit:
  ``stream=false``, ``thinking={"type": "disabled"}``,
  ``response_format={"type": "json_object"}``; ``tools`` are never sent.
* Only a non-empty ``message.content`` string may feed the H1 JSON patch
  parser.  ``reasoning_content`` is used for presence/length/hash
  diagnostics ONLY; tool-call arguments and Responses-API output blocks
  are NEVER extracted as patches; SSE bodies fail closed.
* Extraction failures map to stable status codes, never a generic
  "other".
* Capture sanitization redacts exact sensitive keys recursively while
  preserving numeric usage fields (prompt_tokens, completion_tokens,
  total_tokens, reasoning_tokens).
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlsplit

# ---------------------------------------------------------------------------
# Extraction status codes (stable, testable)
# ---------------------------------------------------------------------------

STATUS_OK = "ok_message_content"
STATUS_EMPTY = "empty_final_content"
STATUS_MISSING = "missing_final_content"
STATUS_INVALID_TYPE = "invalid_final_content_type"
STATUS_EMPTY_WITH_REASONING = "empty_final_content_with_reasoning"
STATUS_TOOL_CALLS_ONLY = "tool_calls_without_final_content"
STATUS_RESPONSES_API = "unexpected_responses_api_envelope"
STATUS_STREAMING = "unexpected_streaming_envelope"
STATUS_INVALID_JSON = "invalid_json_envelope"
STATUS_NO_CHOICES = "missing_choices_or_message"

FAILED_STATUSES: frozenset[str] = frozenset(
    {
        STATUS_EMPTY,
        STATUS_MISSING,
        STATUS_INVALID_TYPE,
        STATUS_EMPTY_WITH_REASONING,
        STATUS_TOOL_CALLS_ONLY,
        STATUS_RESPONSES_API,
        STATUS_STREAMING,
        STATUS_INVALID_JSON,
        STATUS_NO_CHOICES,
    }
)

REDACTED = "***REDACTED***"

# Exact sensitive keys redacted recursively in captures (case-insensitive
# exact match).  Numeric usage fields such as prompt_tokens /
# completion_tokens / total_tokens / reasoning_tokens are NOT in this set
# and survive redaction.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "authorization",
        "access_token",
        "refresh_token",
        "cookie",
        "cookies",
        "password",
        "secret",
        "secrets",
        "client_secret",
    }
)

_NUMERIC_USAGE_KEYS = (
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "reasoning_tokens",
)


# ---------------------------------------------------------------------------
# H1 request policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class H1RequestPolicy:
    """Explicit transport request policy for the H1 pinned model.

    Only ``run_sun_llm_fallback.py`` instantiates this; the generic
    ``OpenAICompatibleRequestBuilder`` default behavior is unchanged.
    """

    stream: bool = False
    thinking: dict[str, Any] | None = field(
        default_factory=lambda: {"type": "disabled"}
    )
    response_format: dict[str, Any] | None = field(
        default_factory=lambda: {"type": "json_object"}
    )
    tools: tuple[Any, ...] = ()  # never sent; documented for audit only

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream": self.stream,
            "thinking": copy.deepcopy(self.thinking),
            "response_format": copy.deepcopy(self.response_format),
            "tools_sent": False,
        }

    def apply_to_body(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Return a NEW body with the policy applied; never mutates input."""
        out = dict(body)
        out["stream"] = self.stream
        if self.thinking is not None:
            out["thinking"] = copy.deepcopy(self.thinking)
        if self.response_format is not None:
            out["response_format"] = copy.deepcopy(self.response_format)
        # tools are intentionally NOT added to the body.
        return out


DEEPSEEK_V4_PRO_H1_POLICY = H1RequestPolicy()


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


# ---------------------------------------------------------------------------
# Pure response-envelope decoder
# ---------------------------------------------------------------------------


def _normalized_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", 1)[0].strip().lower()


def _looks_like_sse(raw: bytes) -> bool:
    head = raw[:256].lstrip()
    lowered = head.lower()
    return lowered.startswith(b"data:") or lowered.startswith(b"event:")


def _numeric(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _extract_usage(data: Mapping[str, Any]) -> dict[str, int | float]:
    usage: dict[str, int | float] = {}
    raw_usage = data.get("usage")
    if not isinstance(raw_usage, Mapping):
        return usage
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = _numeric(raw_usage.get(key))
        if value is not None:
            usage[key] = value
    details = raw_usage.get("completion_tokens_details")
    if isinstance(details, Mapping):
        reasoning = _numeric(details.get("reasoning_tokens"))
        if reasoning is not None:
            usage["reasoning_tokens"] = reasoning
    return usage


def _summarize_tool_calls(message: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_calls = message.get("tool_calls")
    if not isinstance(raw_calls, list):
        return []
    summaries: list[dict[str, Any]] = []
    for index, call in enumerate(raw_calls):
        if not isinstance(call, Mapping):
            continue
        function = call.get("function")
        if not isinstance(function, Mapping):
            continue
        name = function.get("name")
        arguments = function.get("arguments")
        arguments_text = (
            arguments
            if isinstance(arguments, str)
            else (
                json.dumps(arguments, sort_keys=True, ensure_ascii=False)
                if arguments is not None
                else ""
            )
        )
        summaries.append(
            {
                "index": index,
                "name": name if isinstance(name, str) else None,
                "arguments_utf8_length": len(arguments_text.encode("utf-8")),
                "arguments_sha256": sha256_text(arguments_text),
            }
        )
    return summaries


def decode_chat_completion_envelope(
    raw_body: str | bytes,
    content_type: str | None = None,
) -> dict[str, Any]:
    """Decode one HTTP response body into a stable, sanitized audit dict.

    This is the SINGLE extraction function used by the real transport and
    by offline transport replay.  It never raises for envelope-level
    problems and never returns patch content except via the non-empty
    ``content`` field when ``status == ok_message_content``.

    Returns a dict with: status, content, model, response_id,
    response_object, finish_reason, usage, response_body_sha256,
    response_content_sha256, body_utf8_length, content_type_normalized,
    extraction_source, reasoning_present, reasoning_utf8_length,
    reasoning_sha256, tool_call_count, tool_call_summaries,
    transport_audit, error_detail.
    """
    raw = raw_body if isinstance(raw_body, bytes) else raw_body.encode("utf-8")
    normalized_ct = _normalized_content_type(content_type)
    audit: dict[str, Any] = {
        "status": STATUS_INVALID_JSON,
        "content": "",
        "model": None,
        "response_id": None,
        "response_object": None,
        "finish_reason": None,
        "usage": {},
        "response_body_sha256": sha256_bytes(raw),
        "response_content_sha256": sha256_bytes(b""),
        "body_utf8_length": len(raw),
        "content_type_normalized": normalized_ct,
        "extraction_source": "none",
        "reasoning_present": False,
        "reasoning_utf8_length": None,
        "reasoning_sha256": None,
        "tool_call_count": 0,
        "tool_call_summaries": [],
        "transport_audit": {
            "raw_body_saved": False,
            "decoder": "bpc_hybrid.h1_transport.decode_chat_completion_envelope",
        },
        "error_detail": None,
    }

    # SSE bodies fail closed: stream=false is the only H1 policy, and
    # delta/event chunks must never be concatenated into a patch.
    if normalized_ct == "text/event-stream" or _looks_like_sse(raw):
        audit["status"] = STATUS_STREAMING
        audit["error_detail"] = "SSE/event-stream body received although stream=false"
        return audit

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        audit["status"] = STATUS_INVALID_JSON
        audit["error_detail"] = f"body is not valid UTF-8 ({exc})"
        return audit

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        audit["status"] = STATUS_INVALID_JSON
        # JSONDecodeError messages contain positions, never body content.
        audit["error_detail"] = str(exc)
        return audit
    if not isinstance(data, dict):
        audit["status"] = STATUS_INVALID_JSON
        audit["error_detail"] = f"top-level JSON is {type(data).__name__}, not an object"
        return audit

    audit["response_body_sha256"] = sha256_bytes(raw)
    audit["response_id"] = data.get("id") if isinstance(data.get("id"), str) else None
    audit["response_object"] = (
        data.get("object") if isinstance(data.get("object"), str) else None
    )
    audit["model"] = data.get("model") if isinstance(data.get("model"), str) else None
    audit["usage"] = _extract_usage(data)

    # Responses-API-style envelope: output blocks, no choices.
    if "output" in data and "choices" not in data:
        audit["status"] = STATUS_RESPONSES_API
        audit["error_detail"] = (
            "Responses-API output blocks are not accepted on the "
            "/chat/completions path; no automatic patch extraction"
        )
        return audit

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        audit["status"] = STATUS_NO_CHOICES
        audit["error_detail"] = "missing or empty choices array"
        return audit
    choice = choices[0]
    if not isinstance(choice, Mapping) or "message" not in choice:
        audit["status"] = STATUS_NO_CHOICES
        audit["error_detail"] = "choices[0] has no message object"
        return audit

    finish_reason = choice.get("finish_reason")
    audit["finish_reason"] = (
        finish_reason if isinstance(finish_reason, str) else None
    )
    message = choice["message"]
    if not isinstance(message, Mapping):
        audit["status"] = STATUS_NO_CHOICES
        audit["error_detail"] = "choices[0].message is not an object"
        return audit

    # reasoning_content: presence/length/hash diagnostics ONLY.
    reasoning = message.get("reasoning_content")
    if isinstance(reasoning, str) and reasoning != "":
        audit["reasoning_present"] = True
        audit["reasoning_utf8_length"] = len(reasoning.encode("utf-8"))
        audit["reasoning_sha256"] = sha256_text(reasoning)

    audit["tool_call_count"] = (
        len(message["tool_calls"])
        if isinstance(message.get("tool_calls"), list)
        else 0
    )
    audit["tool_call_summaries"] = _summarize_tool_calls(message)

    has_content = "content" in message
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        audit["status"] = STATUS_OK
        audit["content"] = content
        audit["response_content_sha256"] = sha256_text(content)
        audit["extraction_source"] = "message.content"
        return audit

    audit["response_content_sha256"] = sha256_bytes(b"")
    if has_content and not isinstance(content, str):
        audit["status"] = STATUS_INVALID_TYPE
        audit["error_detail"] = (
            f"message.content is {type(content).__name__}, not a string"
        )
    elif audit["reasoning_present"]:
        audit["status"] = STATUS_EMPTY_WITH_REASONING
        audit["error_detail"] = (
            "final message.content is empty although reasoning_content is "
            "present; reasoning is diagnostic-only and never used as a patch"
        )
    elif audit["tool_call_count"] > 0:
        audit["status"] = STATUS_TOOL_CALLS_ONLY
        audit["error_detail"] = (
            "tool_calls present without final content; tool arguments are "
            "never used as a patch"
        )
    elif has_content:
        audit["status"] = STATUS_EMPTY
        audit["error_detail"] = "final message.content is empty"
    else:
        audit["status"] = STATUS_MISSING
        audit["error_detail"] = "message.content key is missing"
    return audit


# ---------------------------------------------------------------------------
# Capture sanitization
# ---------------------------------------------------------------------------


def sanitize_for_capture(value: Any) -> Any:
    """Recursively redact exact sensitive keys; preserve numeric usage."""
    if isinstance(value, Mapping):
        return {
            str(key): (
                REDACTED
                if str(key).lower() in SENSITIVE_KEYS
                else sanitize_for_capture(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_for_capture(item) for item in value]
    return value


def strip_envelope_for_capture(value: Any) -> Any:
    """Remove reasoning text and tool-call arguments from an envelope copy.

    ``reasoning_content`` (any nesting) is dropped; ``tool_calls[*]
    .function.arguments`` are replaced by length/hash summaries.  Runs
    BEFORE :func:`sanitize_for_capture` so capture never contains
    reasoning text or tool arguments.
    """
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in ("reasoning_content", "reasoning"):
                continue
            if lowered == "tool_calls" and isinstance(item, list):
                calls: list[Any] = []
                for call in item:
                    if not isinstance(call, Mapping):
                        calls.append(strip_envelope_for_capture(call))
                        continue
                    call = dict(call)
                    function = call.get("function")
                    if isinstance(function, Mapping):
                        function = dict(function)
                        arguments = function.get("arguments")
                        arguments_text = (
                            arguments
                            if isinstance(arguments, str)
                            else (
                                json.dumps(arguments, sort_keys=True, ensure_ascii=False)
                                if arguments is not None
                                else ""
                            )
                        )
                        function["arguments"] = {
                            "utf8_length": len(arguments_text.encode("utf-8")),
                            "sha256": sha256_text(arguments_text),
                        }
                        call["function"] = function
                    calls.append(strip_envelope_for_capture(call))
                out[key] = calls
                continue
            out[key] = strip_envelope_for_capture(item)
        return out
    if isinstance(value, list):
        return [strip_envelope_for_capture(item) for item in value]
    return value


def describe_endpoint_safe(url: str) -> dict[str, Any]:
    """Return a safe scheme/host/path descriptor for an already-validated
    endpoint URL (never contains credentials; the caller must only pass
    URLs that passed the secret-material check)."""
    parts = urlsplit(url)
    return {
        "scheme": parts.scheme or None,
        "host": parts.hostname or None,
        "port": parts.port,
        "path": parts.path or None,
    }


def build_transport_capture_row(
    *,
    request_id: str,
    sample_id: str,
    clause_id: str,
    clause_index: int,
    prompt_sha256: str,
    prompt_variant: str,
    b0_prediction_sha256: str,
    request_body_sha256: str,
    request_policy: Mapping[str, Any],
    http_status: int | None,
    endpoint_descriptor: Mapping[str, Any],
    requested_model: str,
    resolved_model: str,
    decode: Mapping[str, Any],
    sanitized_response_envelope: Any,
) -> dict[str, Any]:
    """Assemble one sanitized transport capture line (S2.8D-R1).

    The capture deliberately excludes: request headers, Authorization,
    API keys, cookies, reasoning text, and tool-call arguments.  Only
    ``message.content`` is retained (needed for exact future replay of a
    real patch); every other diagnostic is a hash, length, or boolean.
    """
    return {
        "request_id": request_id,
        "sample_id": sample_id,
        "clause_id": clause_id,
        "clause_index": clause_index,
        "prompt_sha256": prompt_sha256,
        "prompt_variant": prompt_variant,
        "b0_prediction_sha256": b0_prediction_sha256,
        "request_body_sha256": request_body_sha256,
        "response_body_sha256": decode.get("response_body_sha256"),
        "http_status": http_status,
        "content_type": decode.get("content_type_normalized"),
        "endpoint": dict(endpoint_descriptor),
        "models": {
            "requested": requested_model,
            "resolved": resolved_model,
            "returned": decode.get("model"),
        },
        "request_policy": dict(request_policy),
        "extraction_status": decode.get("status"),
        "extraction_source": decode.get("extraction_source"),
        "finish_reason": decode.get("finish_reason"),
        "response_id": decode.get("response_id"),
        "response_object": decode.get("response_object"),
        "usage": dict(decode.get("usage") or {}),
        "reasoning": {
            "present": decode.get("reasoning_present"),
            "utf8_length": decode.get("reasoning_utf8_length"),
            "sha256": decode.get("reasoning_sha256"),
        },
        "tool_calls": {
            "count": decode.get("tool_call_count"),
            "summaries": list(decode.get("tool_call_summaries") or []),
        },
        "message_content_sha256": decode.get("response_content_sha256"),
        "sanitized_response_envelope": sanitize_for_capture(
            strip_envelope_for_capture(sanitized_response_envelope)
        ),
        "safety": {
            "raw_response_saved": False,
            "headers_saved": False,
            "authorization_saved": False,
            "reasoning_content_saved": False,
            "tool_call_arguments_saved": False,
            "sanitized": True,
        },
    }

"""LLM transport, parsing, and fallback adapter (R7 + R9).

Provides provider-independent request/response structures, a mock
transport, a real API transport (R9), an OpenAI-compatible request
builder, a JSON response parser, and an LLM fallback adapter that
plugs into the R6 fallback interface.

R9 adds ``RealAPITransport`` which uses only Python standard library
(``urllib.request``) to make a single real API call under explicit
opt-in gates.  No ``requests``, ``httpx``, or ``openai`` SDK.
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from bpc_hybrid.fallback import FallbackRequest, FallbackResult
from bpc_hybrid.llm_config import (
    LLMConfig,
    LLMConfigError,
    LLMProvider,
    _base_url_has_secrets,
    redact_mapping,
)
from bpc_hybrid.schema import (
    MultiClauseExtractionResponse,
    SchemaValidationError,
)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class LLMClientError(ValueError):
    """Raised when the LLM client encounters an unrecoverable error."""


# ---------------------------------------------------------------------------
# LLMRequest / LLMResponse
# ---------------------------------------------------------------------------

@dataclass
class LLMRequest:
    """Provider-independent LLM request payload.

    **Does not contain an API key** — that is managed by the transport
    layer.
    """

    source_id: str
    source_text: str
    system_prompt: str
    user_prompt: str
    schema_name: str = "MultiClauseExtractionResponse"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_text": self.source_text,
            "system_prompt": self.system_prompt,
            "user_prompt": self.user_prompt,
            "schema_name": self.schema_name,
        }


@dataclass
class LLMResponse:
    """Provider-independent LLM response payload.

    **Does not contain an API key.**
    """

    content: str
    provider: str = "mock"
    model: str = "mock"
    finish_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "provider": self.provider,
            "model": self.model,
            "finish_reason": self.finish_reason,
        }


# ---------------------------------------------------------------------------
# LLMTransport (abstract protocol)
# ---------------------------------------------------------------------------

class LLMTransport:
    """Abstract transport protocol for sending LLM requests.

    Subclasses implement :meth:`send` and must not leak API keys in
    repr/str.
    """

    def send(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("subclass must implement send()")


# ---------------------------------------------------------------------------
# MockLLMTransport
# ---------------------------------------------------------------------------

@dataclass
class MockLLMTransport(LLMTransport):
    """Deterministic mock transport — no network, no ``.env``, no API keys.

    Parameters
    ----------
    fixed_response : LLMResponse | None
        The response to return for every ``send()`` call.  If ``None``,
        ``send()`` raises :class:`LLMClientError` (simulates a transport
        failure).
    simulate_invalid_json : bool
        If *True*, return a response with non-JSON content.
    simulate_invalid_schema : bool
        If *True*, return valid JSON that does **not** conform to the
        expected schema.
    """

    fixed_response: LLMResponse | None = None
    simulate_invalid_json: bool = False
    simulate_invalid_schema: bool = False

    def send(self, request: LLMRequest) -> LLMResponse:
        if self.simulate_invalid_json:
            return LLMResponse(
                content="not-valid-json {{{",
                provider="mock",
                model="mock",
                finish_reason="stop",
            )

        if self.simulate_invalid_schema:
            return LLMResponse(
                content=json.dumps({"wrong_key": 42, "not_a_schema": True}),
                provider="mock",
                model="mock",
                finish_reason="stop",
            )

        if self.fixed_response is None:
            raise LLMClientError(
                "MockLLMTransport: no fixed_response configured "
                "(simulates transport error)"
            )

        return self.fixed_response

    def __repr__(self) -> str:
        return (
            f"MockLLMTransport(fixed_response={'set' if self.fixed_response else 'None'}, "
            f"simulate_invalid_json={self.simulate_invalid_json}, "
            f"simulate_invalid_schema={self.simulate_invalid_schema})"
        )


# ---------------------------------------------------------------------------
# OpenAI-compatible request builder
# ---------------------------------------------------------------------------

@dataclass
class OpenAICompatibleRequestBuilder:
    """Builds OpenAI-compatible HTTP request payloads **without** sending them.

    Does not import ``openai``, ``requests``, ``httpx``, or any real
    HTTP library.  This is a pure payload builder for later use.

    Raises :class:`LLMClientError` if *config.base_url* contains secret
    material (query parameters or ``user:password@`` authorities).
    """

    config: LLMConfig

    def __post_init__(self) -> None:
        if self.config.base_url and _base_url_has_secrets(self.config.base_url):
            raise LLMClientError(
                "Request builder rejected: base_url contains secret "
                "material. Use headers/Authorization for credentials."
            )

    def build_url(self) -> str:
        """Return the chat-completions endpoint URL.

        Handles several common base-url shapes:

        * ``https://api.example.com/v1`` → ``.../v1/chat/completions``
        * ``https://api.example.com/v1/`` → ``.../v1/chat/completions``
        * ``https://api.example.com`` → ``.../chat/completions``
        * ``https://api.example.com/v1/chat/completions`` → unchanged
        * ``https://api.example.com/chat/completions`` → unchanged
        """
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def build_headers(self) -> dict[str, str]:
        """Return HTTP headers for the request.

        **API key is redacted** — callers must inject the real key
        themselves.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer ***REDACTED***",
        }
        return headers

    def build_body(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Return the JSON request body.

        **Does not include an API key** — that goes in headers.
        """
        return {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

    def build_payload(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        """Return a dict with ``url``, ``headers``, and ``body`` for
        the complete request.
        """
        return {
            "url": self.build_url(),
            "headers": self.build_headers(),
            "body": self.build_body(system_prompt, user_prompt),
        }

    def __repr__(self) -> str:
        return (
            f"OpenAICompatibleRequestBuilder("
            f"provider={self.config.provider!r}, "
            f"model={self.config.model!r}, "
            f"base_url={self.config.base_url!r})"
        )


# ---------------------------------------------------------------------------
# RealAPITransport (R9)
# ---------------------------------------------------------------------------

class RealAPITransport(LLMTransport):
    """Real HTTP transport for a single OpenAI-compatible API call (R9).

    Uses **only** Python standard library (``urllib.request``).  No
    ``requests``, ``httpx``, or ``openai`` SDK.

    Parameters
    ----------
    config : LLMConfig
        Must have ``api_key``, ``base_url``, and ``model`` populated.
    timeout_seconds : float
        HTTP timeout in seconds.

    Safety guarantees:

    * API key goes **only** in the ``Authorization`` header — never in
      URL query params, request body, stdout, stderr, logs, or repr.
    * Network errors are redacted — the exception message never
      contains the API key or base URL.
    * No raw response is written to disk.
    * Each instance is single-use by convention; the caller must ensure
      only one request is sent.
    """

    def __init__(self, config: LLMConfig, timeout_seconds: float = 30.0) -> None:
        self._config = config
        self._timeout = timeout_seconds
        self._builder = OpenAICompatibleRequestBuilder(config)

    def send(self, request: LLMRequest) -> LLMResponse:
        """Execute a single real API call via ``urllib.request``.

        Returns an :class:`LLMResponse` on success (HTTP 200 with valid
        JSON body).  Raises :class:`LLMClientError` on any failure.
        """
        payload = self._builder.build_payload(
            system_prompt=request.system_prompt,
            user_prompt=request.user_prompt,
        )

        # Inject real API key into headers (redacted by builder)
        headers = dict(payload["headers"])
        headers["Authorization"] = f"Bearer {self._config.api_key}"

        body_bytes = json.dumps(payload["body"]).encode("utf-8")

        http_req = urllib.request.Request(
            payload["url"],
            data=body_bytes,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(http_req, timeout=self._timeout) as resp:
                raw_body = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as exc:
            # HTTP 4xx/5xx — status redacted, body not saved
            raise LLMClientError(
                "Real API HTTP status error (details redacted)"
            ) from exc
        except socket.timeout as exc:
            # Connect or read timeout
            raise LLMClientError(
                "Real API timeout (details redacted)"
            ) from exc
        except ssl.SSLError as exc:
            # SSL/TLS handshake failure
            raise LLMClientError(
                "Real API SSL error (details redacted)"
            ) from exc
        except urllib.error.URLError as exc:
            # DNS resolution or connection refused
            raise LLMClientError(
                "Real API DNS/connection error (details redacted)"
            ) from exc
        except OSError as exc:
            # Other OS-level network errors
            raise LLMClientError(
                "Real API network error (details redacted)"
            ) from exc
        except Exception as exc:
            raise LLMClientError(
                "Real API unexpected error (details redacted)"
            ) from exc

        if status != 200:
            raise LLMClientError(
                f"Real API returned non-200 status (details redacted)"
            )

        # Parse the OpenAI chat-completions response
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LLMClientError(
                "Real API response is not valid JSON"
            ) from exc

        # Extract content from choices[0].message.content
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(
                "Real API response missing choices[0].message.content"
            ) from exc

        finish_reason = None
        try:
            finish_reason = data["choices"][0].get("finish_reason")
        except (KeyError, IndexError, TypeError):
            pass

        model_used = data.get("model", self._config.model)

        return LLMResponse(
            content=content,
            provider=self._config.provider,
            model=model_used,
            finish_reason=finish_reason,
        )

    def __repr__(self) -> str:
        return (
            f"RealAPITransport(provider={self._config.provider!r}, "
            f"model={self._config.model!r})"
        )


# ---------------------------------------------------------------------------
# JSON response parser
# ---------------------------------------------------------------------------

def _extract_json_from_content(content: str) -> str:
    """Extract raw JSON text from potentially markdown-wrapped LLM output.

    If *content* starts with `` ```json `` or `` ``` `` and ends with
    `` ``` ``, strip the fences and return the inner text.  Otherwise
    return *content* unchanged.
    """
    stripped = content.strip()
    # Markdown code fence: ```json ... ```
    if stripped.startswith("```"):
        # Find end of opening fence line
        nl = stripped.find("\n")
        if nl == -1:
            return stripped  # single line of fences — no content
        body = stripped[nl + 1:]
        # Strip trailing ```
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3].rstrip()
        return body
    return stripped


def parse_llm_json_response(content: str) -> MultiClauseExtractionResponse:
    """Parse an LLM text response into a validated schema object.

    1. Strip optional Markdown code fences.
    2. Parse JSON.
    3. Must be a ``dict`` (not a list).
    4. Convert to ``MultiClauseExtractionResponse`` via ``from_dict()``.
    5. Validate the result.

    Raises :class:`LLMClientError` on any failure.
    """
    clean = _extract_json_from_content(content)

    try:
        data = json.loads(clean)
    except json.JSONDecodeError as exc:
        raise LLMClientError(
            f"LLM response is not valid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise LLMClientError(
            f"LLM response must be a JSON object, got {type(data).__name__}"
        )

    try:
        result = MultiClauseExtractionResponse.from_dict(data)
    except Exception as exc:
        raise LLMClientError(
            f"Cannot convert LLM response to MultiClauseExtractionResponse: {exc}"
        ) from exc

    try:
        result.validate()
    except SchemaValidationError as exc:
        raise LLMClientError(
            f"LLM extraction response failed schema validation: {exc}"
        ) from exc

    return result


def validate_llm_extraction_response(data: dict[str, Any]) -> None:
    """Validate that *data* can become a valid ``MultiClauseExtractionResponse``.

    Thin wrapper — mainly used for fast sanity checks.
    """
    parsed = parse_llm_json_response(json.dumps(data))
    # If we got here, it's valid.
    del parsed  # not needed


# ---------------------------------------------------------------------------
# LLM fallback adapter
# ---------------------------------------------------------------------------
# Schema-prompt skeleton builder (R9.7)
# ---------------------------------------------------------------------------

def build_schema_json_skeleton(
    source_text: str = "A controller shall record the decision.",
    source_id: str = "sample-001",
) -> dict:
    """Return a prompt-friendly JSON skeleton for the current project schema.

    The skeleton uses the exact field names from
    ``MultiClauseExtractionResponse`` and ``ClauseExtraction`` as defined
    in ``src/bpc_hybrid/schema.py``.  Values are illustrative examples
    that pass schema validation.

    **No network, no ``.env``, no API keys.**
    """
    txt = source_text.strip()
    length = len(txt)
    return {
        "schema_version": "0.1.0",
        "source_id": source_id,
        "source_text": txt,
        "clauses": [
            {
                "clause_id": f"{source_id}-c1",
                "source_id": source_id,
                "source_text": txt,
                "clause_text": txt,
                "clause_span_start": 0,
                "clause_span_end": length,
                "modality": {
                    "text": "shall",
                    "span_start": 13,
                    "span_end": 18,
                    "confidence": 0.95,
                },
                "actor": {
                    "text": "A controller",
                    "span_start": 0,
                    "span_end": 12,
                    "confidence": 0.90,
                },
                "action": {
                    "text": "record the decision",
                    "span_start": 19,
                    "span_end": length,
                    "confidence": 0.90,
                },
                "condition": None,
                "constraint": None,
                "exception": None,
                "confidence": 0.90,
            }
        ],
    }


# Schema instruction text reused by the adapter prompt and by tests.
_SCHEMA_PROMPT_INSTRUCTIONS = (
    "Your response MUST be a single JSON object. "
    "Do NOT wrap the JSON in markdown code fences (```json ... ```). "
    "Do NOT include any explanation, preamble, or postscript — "
    "output ONLY the JSON object on a single line or compact form. "
    "The JSON object MUST use exactly the field names shown in the "
    "skeleton above. "
    "Do NOT add extra fields. "
    "Do NOT rename fields. "
    "For fields you cannot determine, use null (not omitted). "
    "Every clause object MUST include ALL 13 fields: "
    "clause_id, source_id, source_text, clause_text, "
    "clause_span_start, clause_span_end, "
    "modality, actor, action, condition, constraint, exception, "
    "confidence. "
    "Every FieldSpan object (modality/actor/action/condition/"
    "constraint/exception when not null) MUST include ALL 4 fields: "
    "text, span_start, span_end, confidence. "
    "span_start and span_end MUST be integer character offsets "
    "(0-indexed) into source_text. "
    "span_end MUST be exclusive. "
    "confidence MUST be a float in [0.0, 1.0]."
)


# ---------------------------------------------------------------------------

@dataclass
class LLMFallbackAdapter:
    """Bridges the provider-independent LLM path into the R6 fallback
    interface.

    Implements ``.complete(FallbackRequest) -> FallbackResult`` so it
    can be used wherever R6's ``MockLLMFallbackClient`` is used.
    """

    config: LLMConfig
    transport: LLMTransport | None = None
    system_prompt: str = (
        "You are a regulatory compliance extraction system. "
        "Your ONLY task is to output a single JSON object that "
        "matches the MultiClauseExtractionResponse schema exactly. "
        "Never output markdown, code fences, explanations, or any "
        "text outside the JSON object. "
        "Use only the exact field names from the provided JSON skeleton. "
        "Never add extra fields. "
        "Use null for fields you cannot determine."
    )

    def complete(self, request: FallbackRequest) -> FallbackResult:
        """Execute fallback via the configured LLM path (or error)."""
        # Gate: config must be enabled
        if not self.config.enabled:
            return FallbackResult(
                error="LLM fallback is disabled (config.enabled=False)"
            )

        # Gate: must have transport
        transport = self.transport
        if transport is None:
            if self.config.provider == LLMProvider.MOCK:
                transport = MockLLMTransport()
            else:
                return FallbackResult(
                    error=(
                        f"Provider {self.config.provider!r} requires a "
                        f"transport, but none was provided"
                    )
                )

        # Build the LLM request with schema-aware prompt
        skeleton_json = json.dumps(
            build_schema_json_skeleton(
                source_text=request.source_text,
                source_id=request.source_id,
            ),
            indent=2,
        )
        llm_req = LLMRequest(
            source_id=request.source_id,
            source_text=request.source_text,
            system_prompt=self.system_prompt,
            user_prompt=(
                f"Extract normative clauses from the following text "
                f"as a MultiClauseExtractionResponse.\n\n"
                f"Required JSON skeleton (fill in with actual spans "
                f"from the source text):\n{skeleton_json}\n\n"
                f"{_SCHEMA_PROMPT_INSTRUCTIONS}\n\n"
                f"Source text:\n{request.source_text}"
            ),
        )

        try:
            llm_resp = transport.send(llm_req)
        except Exception as exc:
            return FallbackResult(
                error=f"LLM transport error: {exc}"
            )

        # Parse → validate → convert
        try:
            parsed = parse_llm_json_response(llm_resp.content)
        except LLMClientError as exc:
            return FallbackResult(
                error=f"LLM response parse error: {exc}",
                raw_dict={"content": llm_resp.content} if llm_resp else {},
            )

        # Ensure source_id matches the original request
        parsed.source_id = request.source_id
        parsed.source_text = request.source_text

        return FallbackResult(response=parsed)

    def __repr__(self) -> str:
        return (
            f"LLMFallbackAdapter(enabled={self.config.enabled}, "
            f"provider={self.config.provider!r}, "
            f"model={self.config.model!r})"
        )


# ---------------------------------------------------------------------------
# Schema-valid mock response helper (R8)
# ---------------------------------------------------------------------------

def make_schema_valid_mock_response_json(
    source_text: str,
    source_id: str = "dry-run-sample",
) -> str:
    """Return a schema-valid JSON string for *source_text*.

    Generates a ``MultiClauseExtractionResponse`` as a JSON string that
    will pass ``parse_llm_json_response()`` validation.  The response
    wraps the full *source_text* as a single clause with heuristic
    modality/actor/action spans.

    **No network, no ``.env``, no API keys.**
    """
    txt = source_text.strip()
    length = len(txt)

    # Heuristic modality span
    modality_span = None
    for marker in ("shall", "must", "may", "should", "shall not", "must not"):
        idx = txt.lower().find(marker)
        if idx != -1:
            modality_span = {
                "text": txt[idx : idx + len(marker)],
                "span_start": idx,
                "span_end": idx + len(marker),
                "confidence": 0.95,
            }
            break

    # Use full text as clause_text
    response: dict = {
        "schema_version": "0.1.0",
        "source_id": source_id,
        "source_text": txt,
        "clauses": [
            {
                "clause_id": f"{source_id}-c1",
                "source_id": source_id,
                "source_text": txt,
                "clause_text": txt,
                "clause_span_start": 0,
                "clause_span_end": length,
                "modality": modality_span,
                "actor": {
                    "text": txt,
                    "span_start": 0,
                    "span_end": length,
                    "confidence": 0.9,
                },
                "action": {
                    "text": txt,
                    "span_start": 0,
                    "span_end": length,
                    "confidence": 0.9,
                },
                "condition": None,
                "constraint": None,
                "exception": None,
                "confidence": 0.9,
            }
        ],
    }
    return json.dumps(response)

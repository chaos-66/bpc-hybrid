"""LLM transport, parsing, and fallback adapter (R7).

Provides provider-independent request/response structures, a mock
transport, an OpenAI-compatible request builder, a JSON response parser,
and an LLM fallback adapter that plugs into the R6 fallback interface.

**No network, no ``.env``, no real API keys.**  R7 only builds the
scaffold — real LLM execution is deferred to a later stage.
"""

from __future__ import annotations

import json
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
        """Return the chat-completions endpoint URL."""
        base = (self.config.base_url or "https://api.openai.com/v1").rstrip("/")
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
        "Extract normative clauses from legal text as structured JSON."
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

        # Build the LLM request
        llm_req = LLMRequest(
            source_id=request.source_id,
            source_text=request.source_text,
            system_prompt=self.system_prompt,
            user_prompt=(
                f"Extract normative clauses from the following text "
                f"as a MultiClauseExtractionResponse:\n\n"
                f"{request.source_text}"
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

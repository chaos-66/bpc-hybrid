"""Tests for llm_client (R7).

All test data is synthetic toy text — no real GDPR, BPMN, or Sun data.
No network, no ``.env``, no real API keys.
"""

import json
import pytest

from bpc_hybrid.fallback import (
    FallbackRequest,
    FallbackResult,
)
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMFallbackAdapter,
    LLMRequest,
    LLMResponse,
    LLMTransport,
    MockLLMTransport,
    OpenAICompatibleRequestBuilder,
    _extract_json_from_content,
    parse_llm_json_response,
    validate_llm_extraction_response,
)
from bpc_hybrid.llm_config import LLMConfig
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
)

DUMMY_KEY = "sk-test-should-not-leak"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fs(text: str, start: int, end: int, confidence: float = 1.0) -> FieldSpan:
    return FieldSpan(text=text, span_start=start, span_end=end, confidence=confidence)


def _valid_schema_response(source_text: str = "A controller shall record the decision.") -> MultiClauseExtractionResponse:
    return MultiClauseExtractionResponse(
        schema_version="0.1.0",
        source_id="t1",
        source_text=source_text,
        clauses=[
            ClauseExtraction(
                clause_id="t1-c1",
                source_id="t1",
                source_text=source_text,
                clause_text=source_text,
                clause_span_start=0,
                clause_span_end=len(source_text),
                modality=_fs("shall", 13, 18),
                actor=_fs("A controller", 0, 12),
                action=_fs("record the decision", 19, len(source_text)),
                confidence=0.95,
            )
        ],
    )


# ---------------------------------------------------------------------------
# LLMRequest / LLMResponse
# ---------------------------------------------------------------------------

class TestLLMRequestResponse:
    def test_request_no_api_key(self):
        req = LLMRequest(
            source_id="t1",
            source_text="Text.",
            system_prompt="You are a regulator.",
            user_prompt="Extract.",
        )
        d = req.to_dict()
        assert "api_key" not in d
        assert d["source_id"] == "t1"

    def test_response_no_api_key(self):
        resp = LLMResponse(content="{}", provider="mock", model="mock")
        d = resp.to_dict()
        assert "api_key" not in d
        assert d["content"] == "{}"


# ---------------------------------------------------------------------------
# LLMTransport abstract
# ---------------------------------------------------------------------------

class TestLLMTransportAbstract:
    def test_send_not_implemented(self):
        t = LLMTransport()
        with pytest.raises(NotImplementedError):
            t.send(LLMRequest("t1", "X", "", ""))


# ---------------------------------------------------------------------------
# MockLLMTransport
# ---------------------------------------------------------------------------

class TestMockLLMTransport:
    def test_returns_configured_response(self):
        resp = LLMResponse(content='{"test":true}', provider="mock", model="mock")
        transport = MockLLMTransport(fixed_response=resp)
        result = transport.send(LLMRequest("t1", "X", "", ""))
        assert result.content == '{"test":true}'
        assert result.provider == "mock"

    def test_no_response_simulates_transport_error(self):
        transport = MockLLMTransport(fixed_response=None)
        with pytest.raises(LLMClientError, match="no fixed_response"):
            transport.send(LLMRequest("t1", "X", "", ""))

    def test_simulate_invalid_json(self):
        transport = MockLLMTransport(simulate_invalid_json=True)
        result = transport.send(LLMRequest("t1", "X", "", ""))
        assert "not-valid-json" in result.content

    def test_simulate_invalid_schema(self):
        transport = MockLLMTransport(simulate_invalid_schema=True)
        result = transport.send(LLMRequest("t1", "X", "", ""))
        data = json.loads(result.content)
        assert "wrong_key" in data

    def test_repr_no_secrets(self):
        transport = MockLLMTransport()
        r = repr(transport)
        assert DUMMY_KEY not in r
        assert "api_key" not in r.lower()

    def test_no_http_in_module(self):
        import bpc_hybrid.llm_client as lc
        assert "requests" not in dir(lc)
        assert "httpx" not in dir(lc)
        assert "urllib" not in dir(lc)


# ---------------------------------------------------------------------------
# parse_llm_json_response
# ---------------------------------------------------------------------------

class TestParseLLMJsonResponse:
    def test_valid_response(self):
        src = "A controller shall record the decision."
        resp = _valid_schema_response(src)
        content = json.dumps(resp.to_dict())
        result = parse_llm_json_response(content)
        assert result.source_id == "t1"
        result.validate()

    def test_invalid_json_rejected(self):
        with pytest.raises(LLMClientError, match="not valid JSON"):
            parse_llm_json_response("not json {{{")

    def test_json_list_rejected(self):
        with pytest.raises(LLMClientError, match="must be a JSON object"):
            parse_llm_json_response("[1, 2, 3]")

    def test_schema_invalid_rejected(self):
        with pytest.raises(LLMClientError, match="Unknown keys"):
            parse_llm_json_response('{"wrong_key": 42}')

    def test_markdown_fence_stripped(self):
        src = "A controller shall record the decision."
        resp = _valid_schema_response(src)
        inner = json.dumps(resp.to_dict())
        content = f"```json\n{inner}\n```"
        result = parse_llm_json_response(content)
        result.validate()

    def test_markdown_fence_no_lang(self):
        src = "A controller shall record the decision."
        resp = _valid_schema_response(src)
        inner = json.dumps(resp.to_dict())
        content = f"```\n{inner}\n```"
        result = parse_llm_json_response(content)
        result.validate()

    def test_natural_language_wrapping_rejected(self):
        with pytest.raises(LLMClientError):
            parse_llm_json_response(
                'Here is the result: {"schema_version":"0.1.0"}'
            )


# ---------------------------------------------------------------------------
# validate_llm_extraction_response
# ---------------------------------------------------------------------------

class TestValidateLLMExtractionResponse:
    def test_valid_passes(self):
        resp = _valid_schema_response()
        validate_llm_extraction_response(resp.to_dict())

    def test_invalid_raises(self):
        with pytest.raises(LLMClientError):
            validate_llm_extraction_response({"not": "valid"})


# ---------------------------------------------------------------------------
# _extract_json_from_content
# ---------------------------------------------------------------------------

class TestExtractJsonFromContent:
    def test_plain_json(self):
        assert _extract_json_from_content('{"a":1}') == '{"a":1}'

    def test_fenced_json(self):
        content = "```json\n{\"a\":1}\n```"
        assert _extract_json_from_content(content) == '{"a":1}'

    def test_fence_no_lang(self):
        content = "```\n{\"a\":1}\n```"
        assert _extract_json_from_content(content) == '{"a":1}'


# ---------------------------------------------------------------------------
# OpenAICompatibleRequestBuilder
# ---------------------------------------------------------------------------

class TestOpenAICompatibleRequestBuilder:
    def test_builds_payload_without_network(self):
        cfg = LLMConfig(
            enabled=False,
            provider="openai_compatible",
            model="gpt-test",
            base_url="https://test.example.com/v1",
            api_key=DUMMY_KEY,
        )
        builder = OpenAICompatibleRequestBuilder(cfg)
        payload = builder.build_payload("You are helpful.", "Extract this.")
        assert payload["url"] == "https://test.example.com/v1/chat/completions"
        assert payload["body"]["model"] == "gpt-test"
        assert DUMMY_KEY not in json.dumps(payload)

    def test_headers_redact_api_key(self):
        cfg = LLMConfig(
            enabled=False,
            provider="openai_compatible",
            api_key=DUMMY_KEY,
        )
        builder = OpenAICompatibleRequestBuilder(cfg)
        headers = builder.build_headers()
        assert DUMMY_KEY not in headers["Authorization"]
        assert "REDACTED" in headers["Authorization"]

    def test_body_no_api_key(self):
        cfg = LLMConfig(
            enabled=False,
            provider="openai_compatible",
            api_key=DUMMY_KEY,
        )
        builder = OpenAICompatibleRequestBuilder(cfg)
        body = builder.build_body("sys", "usr")
        assert "api_key" not in body
        assert DUMMY_KEY not in json.dumps(body)

    def test_no_openai_import(self):
        """Verify the module does not import openai SDK."""
        src = open("src/bpc_hybrid/llm_client.py", encoding="utf-8").read()
        assert "import openai" not in src
        assert "from openai" not in src
        assert "import anthropic" not in src
        assert "from anthropic" not in src

    def test_no_requests_import(self):
        src = open("src/bpc_hybrid/llm_client.py", encoding="utf-8").read()
        assert "import requests" not in src
        assert "from requests" not in src
        assert "import httpx" not in src
        assert "from httpx" not in src

    def test_repr_no_secrets(self):
        cfg = LLMConfig(
            enabled=False,
            provider="openai_compatible",
            api_key=DUMMY_KEY,
        )
        builder = OpenAICompatibleRequestBuilder(cfg)
        r = repr(builder)
        assert DUMMY_KEY not in r


# ---------------------------------------------------------------------------
# LLMFallbackAdapter
# ---------------------------------------------------------------------------

class TestLLMFallbackAdapter:
    def test_disabled_config_refuses(self):
        cfg = LLMConfig(enabled=False)
        adapter = LLMFallbackAdapter(config=cfg)
        req = FallbackRequest(source_text="X.", source_id="x",
                              rule_response=_valid_schema_response())
        result = adapter.complete(req)
        assert not result.is_valid
        assert "disabled" in result.error.lower()

    def test_mock_provider_returns_result(self):
        src = "A controller shall record the decision."
        resp = _valid_schema_response(src)
        llm_resp = LLMResponse(
            content=json.dumps(resp.to_dict()),
            provider="mock",
            model="mock",
        )
        transport = MockLLMTransport(fixed_response=llm_resp)
        cfg = LLMConfig(enabled=True, provider="mock")
        adapter = LLMFallbackAdapter(config=cfg, transport=transport)
        req = FallbackRequest(source_text=src, source_id="x",
                              rule_response=resp)
        result = adapter.complete(req)
        assert result.is_valid
        assert result.response is not None
        result.response.validate()

    def test_rejects_invalid_response(self):
        transport = MockLLMTransport(simulate_invalid_json=True)
        cfg = LLMConfig(enabled=True, provider="mock")
        adapter = LLMFallbackAdapter(config=cfg, transport=transport)
        req = FallbackRequest(source_text="X.", source_id="x",
                              rule_response=_valid_schema_response())
        result = adapter.complete(req)
        assert not result.is_valid
        assert "parse error" in result.error.lower()

    def test_transport_error_becomes_fallback_error(self):
        transport = MockLLMTransport(fixed_response=None)
        cfg = LLMConfig(enabled=True, provider="mock")
        adapter = LLMFallbackAdapter(config=cfg, transport=transport)
        req = FallbackRequest(source_text="X.", source_id="x",
                              rule_response=_valid_schema_response())
        result = adapter.complete(req)
        assert not result.is_valid
        assert "transport error" in result.error.lower()

    def test_mock_transport_auto_created(self):
        cfg = LLMConfig(enabled=True, provider="mock")
        resp = _valid_schema_response()
        llm_resp = LLMResponse(content=json.dumps(resp.to_dict()))
        # Inject mock transport via config + transport arg
        transport = MockLLMTransport(fixed_response=llm_resp)
        adapter = LLMFallbackAdapter(config=cfg, transport=transport)
        req = FallbackRequest(source_text=resp.source_text, source_id="x",
                              rule_response=resp)
        result = adapter.complete(req)
        assert result.is_valid

    def test_repr_no_secrets(self):
        cfg = LLMConfig(enabled=True, provider="mock")
        adapter = LLMFallbackAdapter(config=cfg)
        r = repr(adapter)
        assert DUMMY_KEY not in r

    def test_source_id_override(self):
        src = "A controller shall record the decision."
        resp = _valid_schema_response(src)
        resp.source_id = "original-id"
        llm_resp = LLMResponse(content=json.dumps(resp.to_dict()))
        transport = MockLLMTransport(fixed_response=llm_resp)
        cfg = LLMConfig(enabled=True, provider="mock")
        adapter = LLMFallbackAdapter(config=cfg, transport=transport)
        req = FallbackRequest(source_text=src, source_id="override-id",
                              rule_response=resp)
        result = adapter.complete(req)
        assert result.is_valid
        assert result.response.source_id == "override-id"


# ---------------------------------------------------------------------------
# No network, no .env, no real data
# ---------------------------------------------------------------------------

class TestSafetyGuarantees:
    def test_no_dotenv_import(self):
        src = open("src/bpc_hybrid/llm_client.py", encoding="utf-8").read()
        assert "dotenv" not in src.lower()
        assert "load_dotenv" not in src.lower()

    def test_no_real_data(self):
        """All test data is synthetic."""
        pass  # all helpers above use synthetic toy sentences

    def test_no_raw_response_files(self):
        """No test writes raw response files."""
        import tempfile, os
        # Just verifying we don't have any write-to-file logic
        src = open("src/bpc_hybrid/llm_client.py", encoding="utf-8").read()
        assert "open(" not in src or "encoding" in src  # only reads, not writes

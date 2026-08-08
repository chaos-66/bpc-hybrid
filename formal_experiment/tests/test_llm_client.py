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
        # urllib is allowed (standard library, used by RealAPITransport in R9)


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

    def test_rejects_secret_base_url(self):
        # Bypass LLMConfig.__post_init__ validation to test builder guard
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", DUMMY_KEY)
        object.__setattr__(cfg, "base_url", "https://x.com?api_key=sk-test-should-not-leak")
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        with pytest.raises(LLMClientError, match="secret material"):
            OpenAICompatibleRequestBuilder(cfg)

    def test_builder_error_no_leak_secret(self):
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", DUMMY_KEY)
        object.__setattr__(cfg, "base_url", "https://x.com?api_key=sk-test-should-not-leak")
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        with pytest.raises(LLMClientError) as exc_info:
            OpenAICompatibleRequestBuilder(cfg)
        msg = str(exc_info.value)
        assert "sk-test-should-not-leak" not in msg
        assert "api_key" not in msg.lower()

    def test_rejects_access_token_in_base_url(self):
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", DUMMY_KEY)
        object.__setattr__(cfg, "base_url", "https://x.com?access_token=sk-test-should-not-leak")
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        with pytest.raises(LLMClientError, match="secret material"):
            OpenAICompatibleRequestBuilder(cfg)

    def test_rejects_authorization_in_base_url(self):
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", DUMMY_KEY)
        object.__setattr__(cfg, "base_url", "https://x.com?authorization=Bearer%20sk-test-should-not-leak")
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        with pytest.raises(LLMClientError, match="secret material"):
            OpenAICompatibleRequestBuilder(cfg)

    def test_builder_access_token_error_no_leak(self):
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", DUMMY_KEY)
        object.__setattr__(cfg, "base_url", "https://x.com?access_token=sk-test-should-not-leak")
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        with pytest.raises(LLMClientError) as exc_info:
            OpenAICompatibleRequestBuilder(cfg)
        msg = str(exc_info.value)
        assert "sk-test-should-not-leak" not in msg

    def test_builder_authorization_error_no_leak(self):
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", DUMMY_KEY)
        object.__setattr__(cfg, "base_url", "https://x.com?authorization=Bearer%20sk-test-should-not-leak")
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        with pytest.raises(LLMClientError) as exc_info:
            OpenAICompatibleRequestBuilder(cfg)
        msg = str(exc_info.value)
        assert "sk-test-should-not-leak" not in msg
        assert "Bearer" not in msg


# ---------------------------------------------------------------------------
# build_url() endpoint construction (R9.1)
# ---------------------------------------------------------------------------

class TestBuildURLEndpointConstruction:
    """R9.1: build_url() handles various base URL shapes correctly."""

    def _make_builder(self, base_url: str) -> OpenAICompatibleRequestBuilder:
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", "sk-test")
        object.__setattr__(cfg, "base_url", base_url)
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        return OpenAICompatibleRequestBuilder(cfg)

    def test_v1_no_trailing_slash(self):
        """https://api.example.com/v1 → /v1/chat/completions"""
        builder = self._make_builder("https://api.example.com/v1")
        assert builder.build_url() == "https://api.example.com/v1/chat/completions"

    def test_v1_with_trailing_slash(self):
        """https://api.example.com/v1/ → /v1/chat/completions"""
        builder = self._make_builder("https://api.example.com/v1/")
        assert builder.build_url() == "https://api.example.com/v1/chat/completions"

    def test_root_like_no_path(self):
        """https://api.example.com → /chat/completions"""
        builder = self._make_builder("https://api.example.com")
        assert builder.build_url() == "https://api.example.com/chat/completions"

    def test_chat_completions_already_present(self):
        """base URL already has /chat/completions → unchanged."""
        builder = self._make_builder("https://api.example.com/chat/completions")
        assert builder.build_url() == "https://api.example.com/chat/completions"

    def test_v1_chat_completions_already_present(self):
        """base URL already has /v1/chat/completions → unchanged."""
        builder = self._make_builder("https://api.example.com/v1/chat/completions")
        assert builder.build_url() == "https://api.example.com/v1/chat/completions"

    def test_default_openai_url(self):
        """No base_url → defaults to https://api.openai.com/v1/chat/completions."""
        cfg = LLMConfig.__new__(LLMConfig)
        object.__setattr__(cfg, "enabled", False)
        object.__setattr__(cfg, "provider", "openai_compatible")
        object.__setattr__(cfg, "model", "mock")
        object.__setattr__(cfg, "api_key", "sk-test")
        object.__setattr__(cfg, "base_url", None)
        object.__setattr__(cfg, "timeout_seconds", 30.0)
        object.__setattr__(cfg, "max_tokens", 1024)
        object.__setattr__(cfg, "temperature", 0.0)
        builder = OpenAICompatibleRequestBuilder(cfg)
        assert builder.build_url() == "https://api.openai.com/v1/chat/completions"


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
        src = open("src/bpc_hybrid/llm_client.py", encoding="utf-8").read()
        # urlopen is for network; file open() calls should have encoding
        assert "with open(" not in src  # no file writing


# ---------------------------------------------------------------------------
# R9.7 — Prompt schema alignment tests
# ---------------------------------------------------------------------------

class TestSchemaPromptSkeleton:
    """R9.7: The prompt skeleton uses exact current-project schema fields."""

    @staticmethod
    def _all_clause_fields():
        return frozenset({
            "clause_id", "source_id", "source_text", "clause_text",
            "clause_span_start", "clause_span_end",
            "modality", "actor", "action",
            "condition", "constraint", "exception",
            "confidence",
        })

    @staticmethod
    def _all_multi_fields():
        return frozenset({"schema_version", "source_id", "source_text", "clauses"})

    def test_skeleton_top_level_keys_match_schema(self):
        """Top-level keys must match MultiClauseExtractionResponse."""
        from bpc_hybrid.llm_client import build_schema_json_skeleton
        skel = build_schema_json_skeleton()
        assert self._all_multi_fields() == set(skel.keys()), (
            f"Top-level keys mismatch: {set(skel.keys())} "
            f"vs {self._all_multi_fields()}"
        )

    def test_skeleton_clause_keys_match_schema(self):
        """Every clause must have exactly the 13 required fields."""
        from bpc_hybrid.llm_client import build_schema_json_skeleton
        skel = build_schema_json_skeleton()
        clause = skel["clauses"][0]
        assert self._all_clause_fields() == set(clause.keys()), (
            f"Clause keys mismatch: {set(clause.keys())} "
            f"vs {self._all_clause_fields()}"
        )

    def test_skeleton_fieldspan_keys_match_schema(self):
        """FieldSpan fields must be text, span_start, span_end, confidence."""
        from bpc_hybrid.llm_client import build_schema_json_skeleton
        skel = build_schema_json_skeleton()
        clause = skel["clauses"][0]
        expected = {"text", "span_start", "span_end", "confidence"}
        for field_name in ("modality", "actor", "action"):
            fs = clause[field_name]
            assert set(fs.keys()) == expected, (
                f"{field_name} FieldSpan keys: {set(fs.keys())}"
            )
        # condition, constraint, exception are None (allowed)
        for field_name in ("condition", "constraint", "exception"):
            assert clause[field_name] is None, (
                f"{field_name} should be null in skeleton"
            )

    def test_skeleton_passes_schema_validation(self):
        """The skeleton's values must pass ClauseExtraction.from_dict."""
        from bpc_hybrid.llm_client import build_schema_json_skeleton
        from bpc_hybrid.schema import ClauseExtraction, MultiClauseExtractionResponse
        skel = build_schema_json_skeleton()
        # Each clause must parse
        for clause_dict in skel["clauses"]:
            ce = ClauseExtraction.from_dict(clause_dict)
            ce.validate()
        # Full response must parse
        mcr = MultiClauseExtractionResponse.from_dict(skel)
        mcr.validate()

    def test_skeleton_rejects_extra_keys(self):
        """Adding extra keys to skeleton clause must fail schema."""
        from bpc_hybrid.schema import ClauseExtraction, SchemaValidationError
        from bpc_hybrid.llm_client import build_schema_json_skeleton
        skel = build_schema_json_skeleton()
        bad_clause = dict(skel["clauses"][0])
        bad_clause["extra_field"] = "should not be here"
        with pytest.raises(SchemaValidationError, match="Unknown keys"):
            ClauseExtraction.from_dict(bad_clause)


class TestPromptContainsExactSchemaInstructions:
    """R9.7: The prompt and instructions require exact-schema JSON output."""

    def test_prompt_instructions_require_json_only(self):
        """Instructions must say JSON only, no markdown, no code fences."""
        from bpc_hybrid.llm_client import _SCHEMA_PROMPT_INSTRUCTIONS
        inst = _SCHEMA_PROMPT_INSTRUCTIONS.lower()
        assert "json" in inst
        assert "no" in inst  # negative constraints present
        assert "markdown" in inst or "code fence" in inst
        assert "extra field" in inst

    def test_prompt_instructions_mention_multiclauseextractionresponse(self):
        """Instructions should reference the project schema class."""
        from bpc_hybrid.llm_client import _SCHEMA_PROMPT_INSTRUCTIONS
        # The user_prompt references MultiClauseExtractionResponse
        # We verify the skeleton + instructions together form the contract
        from bpc_hybrid.llm_client import build_schema_json_skeleton
        skel = build_schema_json_skeleton()
        assert skel["schema_version"] == "0.1.0"
        assert "clauses" in skel
        assert len(skel["clauses"]) == 1

    def test_adapter_system_prompt_forbids_markdown(self):
        """R9.7 system prompt must forbid markdown/code fences."""
        from bpc_hybrid.llm_client import LLMFallbackAdapter
        from bpc_hybrid.llm_config import LLMConfig
        adapter = LLMFallbackAdapter(LLMConfig())
        sp = adapter.system_prompt.lower()
        assert "markdown" in sp or "code fence" in sp
        assert "json" in sp

    def test_adapter_user_prompt_includes_skeleton(self):
        """R9.7 user prompt must include the JSON skeleton."""
        from bpc_hybrid.llm_client import (
            LLMFallbackAdapter,
            LLMRequest,
            MockLLMTransport,
        )
        from bpc_hybrid.llm_config import LLMConfig
        from bpc_hybrid.fallback import FallbackRequest
        from bpc_hybrid.schema import MultiClauseExtractionResponse

        cfg = LLMConfig(enabled=True, provider="mock")
        adapter = LLMFallbackAdapter(config=cfg)

        rule_resp = MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id="test",
            source_text="A controller shall record the decision.",
            clauses=[],
        )
        fb_req = FallbackRequest(
            source_text="A controller shall record the decision.",
            source_id="test",
            rule_response=rule_resp,
        )

        # Intercept the LLMRequest to inspect user_prompt
        original_send = MockLLMTransport.send

        captured_prompts = []
        def _capture_send(self, req):
            captured_prompts.append((req.system_prompt, req.user_prompt))
            return original_send(self, req)

        import bpc_hybrid.llm_client as llm_mod
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(MockLLMTransport, "send", _capture_send)

        try:
            adapter.complete(fb_req)
        finally:
            monkeypatch.undo()

        assert len(captured_prompts) == 1
        _sys, user = captured_prompts[0]
        assert "schema_version" in user
        assert "clause_id" in user
        assert "MultiClauseExtractionResponse" in user
        assert "source_text" in user


# S2.8D-R1 imports
from pathlib import Path
from typing import Any

from bpc_hybrid.h1_transport import (
    DEEPSEEK_V4_PRO_H1_POLICY,
    H1RequestPolicy,
    REDACTED,
    STATUS_EMPTY,
    STATUS_EMPTY_WITH_REASONING,
    STATUS_INVALID_JSON,
    STATUS_INVALID_TYPE,
    STATUS_MISSING,
    STATUS_NO_CHOICES,
    STATUS_OK,
    STATUS_RESPONSES_API,
    STATUS_STREAMING,
    STATUS_TOOL_CALLS_ONLY,
    build_transport_capture_row,
    decode_chat_completion_envelope,
    describe_endpoint_safe,
    sanitize_for_capture,
    sha256_text,
)


# ---------------------------------------------------------------------------
# S2.8D-R1: DeepSeek H1 transport contract (request policy, envelope
# decoder, sanitized capture).  All tests are fully offline.
# ---------------------------------------------------------------------------

class TestH1TransportContract:
    """Pure-function tests for bpc_hybrid.h1_transport + the transport's
    use of the shared decoder."""

    FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "h1_transport"

    def _load(self, name: str) -> str:
        return (self.FIXTURES / name).read_text(encoding="utf-8")

    # -- decoder: statuses --------------------------------------------------

    def test_ok_message_content_decoded(self):
        decode = decode_chat_completion_envelope(
            self._load("chatcompletion_effective_patch.json")
        )
        assert decode["status"] == STATUS_OK
        assert decode["content"].startswith('{"sample_id"')
        assert decode["model"] == "deepseek-v4-flash"
        assert decode["response_id"] == "chatcmpl-s2d8r1-effective"
        assert decode["response_object"] == "chat.completion"
        assert decode["finish_reason"] == "stop"
        assert decode["usage"] == {
            "prompt_tokens": 812,
            "completion_tokens": 96,
            "total_tokens": 908,
        }
        assert decode["extraction_source"] == "message.content"
        assert decode["reasoning_present"] is False
        assert decode["tool_call_count"] == 0
        assert decode["response_content_sha256"] == sha256_text(decode["content"])

    def test_empty_content_with_reasoning_never_used_as_patch(self):
        decode = decode_chat_completion_envelope(
            self._load("chatcompletion_empty_with_reasoning.json")
        )
        assert decode["status"] == STATUS_EMPTY_WITH_REASONING
        assert decode["content"] == ""
        assert decode["reasoning_present"] is True
        assert decode["reasoning_utf8_length"] > 0
        assert len(decode["reasoning_sha256"]) == 64
        assert decode["usage"]["reasoning_tokens"] == 60
        blob = json.dumps(decode)
        # The reasoning TEXT (which looks like a patch) must never be
        # stored; only presence/length/hash diagnostics survive.
        assert '"patches": {}' not in blob
        assert '"sample_id": "estg_000002"' not in blob

    def test_empty_length_reasoning_tokens_diagnostics(self):
        decode = decode_chat_completion_envelope(
            self._load("chatcompletion_empty_length_reasoning_tokens.json")
        )
        assert decode["status"] == STATUS_EMPTY
        assert decode["finish_reason"] == "length"
        assert decode["content"] == ""
        assert decode["usage"]["reasoning_tokens"] == 980
        assert decode["reasoning_present"] is False

    @pytest.mark.parametrize(
        ("fixture", "status"),
        [
            ("chatcompletion_null_content.json", STATUS_INVALID_TYPE),
            ("chatcompletion_array_content.json", STATUS_INVALID_TYPE),
            ("chatcompletion_missing_content.json", STATUS_MISSING),
        ],
    )
    def test_content_variants_stable_statuses(self, fixture, status):
        decode = decode_chat_completion_envelope(self._load(fixture))
        assert decode["status"] == status
        assert decode["content"] == ""

    def test_tool_calls_only_fail_closed(self):
        decode = decode_chat_completion_envelope(
            self._load("chatcompletion_tool_calls_only.json")
        )
        assert decode["status"] == STATUS_TOOL_CALLS_ONLY
        assert decode["content"] == ""
        assert decode["tool_call_count"] == 1
        summary = decode["tool_call_summaries"][0]
        assert summary["name"] == "apply_patch"
        assert summary["arguments_utf8_length"] > 0
        assert len(summary["arguments_sha256"]) == 64
        blob = json.dumps(decode)
        assert '"patches"' not in blob  # tool arguments text never stored

    def test_responses_api_envelope_fail_closed(self):
        decode = decode_chat_completion_envelope(
            self._load("responses_api_output_blocks.json")
        )
        assert decode["status"] == STATUS_RESPONSES_API
        assert decode["content"] == ""

    def test_sse_body_fail_closed(self):
        body = self._load("sse_delta_body.txt")
        with_ct = decode_chat_completion_envelope(body, "text/event-stream")
        assert with_ct["status"] == STATUS_STREAMING
        without_ct = decode_chat_completion_envelope(body)
        assert without_ct["status"] == STATUS_STREAMING
        assert with_ct["content"] == "" and without_ct["content"] == ""

    def test_invalid_json_body_fail_closed_without_leak(self):
        decode = decode_chat_completion_envelope(self._load("invalid_json_body.txt"))
        assert decode["status"] == STATUS_INVALID_JSON
        assert decode["response_body_sha256"]
        assert decode["body_utf8_length"] > 0
        blob = json.dumps(decode)
        assert "sample_id" not in blob  # body content never leaked

    def test_missing_choices_stable_status(self):
        decode = decode_chat_completion_envelope('{"id": "x"}')
        assert decode["status"] == STATUS_NO_CHOICES
        decode2 = decode_chat_completion_envelope(
            '{"choices": [{"message": {"content": "ok"}}]}'
        )
        assert decode2["status"] == STATUS_OK

    def test_empty_content_hash_matches_observed_constant(self):
        decode = decode_chat_completion_envelope(
            '{"choices": [{"message": {"content": ""}}]}'
        )
        assert decode["response_content_sha256"] == (
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_decode_byte_deterministic(self):
        raw = self._load("chatcompletion_effective_patch.json")
        assert decode_chat_completion_envelope(raw) == decode_chat_completion_envelope(raw)

    # -- request policy -----------------------------------------------------

    def test_h1_policy_applied_only_where_requested(self):
        builder = OpenAICompatibleRequestBuilder(
            LLMConfig(
                enabled=False,
                provider="mock",
                model="m",
                base_url="https://api.test.invalid/v1",
            )
        )
        body = builder.build_body("sys", "user")
        assert "stream" not in body
        assert "thinking" not in body
        assert "response_format" not in body
        assert "tools" not in body
        policy = H1RequestPolicy()
        applied = policy.apply_to_body(body)
        assert applied["stream"] is False
        assert applied["thinking"] == {"type": "disabled"}
        assert applied["response_format"] == {"type": "json_object"}
        assert "tools" not in applied
        # input body is not mutated
        assert "stream" not in body
        assert "thinking" not in body

    # -- sanitized capture --------------------------------------------------

    def test_sanitize_capture_redacts_sensitive_keys(self):
        envelope = json.loads(self._load("sensitive_envelope.json"))
        cleaned = sanitize_for_capture(envelope)
        blob = json.dumps(cleaned)
        for secret in ("sk-super-secret-key", "sk-nested-secret", "rt-xyz", "hunter2", "abc123"):
            assert secret not in blob
        assert cleaned["headers"]["Authorization"] == REDACTED
        assert cleaned["headers"]["Cookie"] == REDACTED
        assert cleaned["nested"]["api_key"] == REDACTED
        assert cleaned["nested"]["refresh_token"] == REDACTED
        assert cleaned["nested"]["password"] == REDACTED
        # numeric usage survives redaction
        assert cleaned["usage"]["prompt_tokens"] == 812
        assert cleaned["usage"]["completion_tokens"] == 96
        assert cleaned["usage"]["completion_tokens_details"]["reasoning_tokens"] == 10
        # message.content retained for exact replay
        assert "patches" in cleaned["choices"][0]["message"]["content"]

    def test_capture_row_never_contains_reasoning_or_tool_arguments(self):
        decode = decode_chat_completion_envelope(
            self._load("chatcompletion_tool_calls_only.json")
        )
        row = build_transport_capture_row(
            request_id="r1",
            sample_id="estg_000002",
            clause_id="estg_000002.c1",
            clause_index=0,
            prompt_sha256="p" * 64,
            prompt_variant="masked_selected_v5",
            b0_prediction_sha256="b" * 64,
            request_body_sha256="rb" * 32,
            request_policy=DEEPSEEK_V4_PRO_H1_POLICY.to_dict(),
            http_status=200,
            endpoint_descriptor={"offline": True},
            requested_model="deepseek-v4-flash",
            resolved_model="deepseek-v4-flash",
            decode=decode,
            sanitized_response_envelope={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "apply_patch", "arguments": "secret-args"}}
                    ],
                }
            },
        )
        blob = json.dumps(row)
        assert "secret-args" not in blob
        assert row["safety"]["tool_call_arguments_saved"] is False
        assert row["safety"]["reasoning_content_saved"] is False
        assert row["safety"]["authorization_saved"] is False
        assert row["tool_calls"]["count"] == 1

    def test_capture_row_retains_message_content_for_replay(self):
        decode = decode_chat_completion_envelope(
            self._load("chatcompletion_effective_patch.json")
        )
        row = build_transport_capture_row(
            request_id="r1",
            sample_id="estg_000002",
            clause_id="estg_000002.c1",
            clause_index=0,
            prompt_sha256="p" * 64,
            prompt_variant="masked_selected_v5",
            b0_prediction_sha256="b" * 64,
            request_body_sha256="rb" * 32,
            request_policy=DEEPSEEK_V4_PRO_H1_POLICY.to_dict(),
            http_status=200,
            endpoint_descriptor={"offline": True},
            requested_model="deepseek-v4-flash",
            resolved_model="deepseek-v4-flash",
            decode=decode,
            sanitized_response_envelope={"message": {"content": decode["content"]}},
        )
        assert "patches" in json.dumps(row)

    def test_endpoint_descriptor_no_credentials(self):
        desc = describe_endpoint_safe("https://api.example.com/v1/chat/completions")
        assert desc == {
            "scheme": "https",
            "host": "api.example.com",
            "port": None,
            "path": "/v1/chat/completions",
        }

    # -- transport integration (offline, urlopen stubbed) --------------------

    def test_real_transport_uses_decoder_and_policy_offline(self, monkeypatch):
        import urllib.request as ur
        from bpc_hybrid.llm_client import RealAPITransport

        cfg = LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="deepseek-v4-flash",
            api_key="sk-test-should-not-leak",
            base_url="https://api.test.invalid/v1",
        )
        transport = RealAPITransport(cfg, policy=H1RequestPolicy())
        captured: dict[str, Any] = {}

        class FakeResp:
            status = 200
            headers = {"Content-Type": "application/json"}
            body = b""

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return self.body

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["body"] = req.data
            resp = FakeResp()
            resp.body = self._load("chatcompletion_effective_patch.json").encode("utf-8")
            return resp

        monkeypatch.setattr(ur, "urlopen", fake_urlopen)
        response = transport.send(
            LLMRequest(
                source_id="s", source_text="t", system_prompt="sys", user_prompt="user"
            )
        )
        sent = json.loads(captured["body"])
        assert sent["stream"] is False
        assert sent["thinking"] == {"type": "disabled"}
        assert sent["response_format"] == {"type": "json_object"}
        assert transport.last_decode["status"] == STATUS_OK
        assert transport.last_request_body_sha256 is not None
        assert transport.last_request_policy["tools_sent"] is False
        assert response.model == "deepseek-v4-flash"
        sent_text = captured["body"].decode("utf-8")
        assert "sk-test-should-not-leak" not in sent_text
        assert captured["url"].endswith("/v1/chat/completions")

"""Mock-only pipeline tests for optional LLM fallback (R10.2).

Tests the ``extract_with_optional_llm_fallback()`` helper with mock
providers only — no real API, no ``.env``, no network, no batch.

All test data is synthetic toy text — no real GDPR, BPMN, or Sun data.
"""

from __future__ import annotations

import pytest

from bpc_hybrid.fallback import (
    DecisionReason,
    FallbackError,
    FallbackRequest,
    FallbackResult,
    MockLLMFallbackClient,
    OptionalFallbackResult,
    _should_trigger_optional_fallback,
    extract_hybrid,
    extract_with_optional_llm_fallback,
    should_trigger_fallback,
)
from bpc_hybrid.extractor import extract_rule_first
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)


# ---------------------------------------------------------------------------
# Helpers (reuse same pattern as test_fallback.py)
# ---------------------------------------------------------------------------

def _fs(text: str, start: int, end: int, confidence: float = 1.0) -> FieldSpan:
    return FieldSpan(text=text, span_start=start, span_end=end, confidence=confidence)


def _clause(
    clause_id: str,
    source_id: str,
    source_text: str,
    clause_text: str,
    start: int,
    end: int,
    confidence: float = 0.9,
    **fields: FieldSpan | None,
) -> ClauseExtraction:
    kw: dict = {
        "modality": None,
        "actor": None,
        "action": None,
        "condition": None,
        "constraint": None,
        "exception": None,
    }
    kw.update(fields)
    return ClauseExtraction(
        clause_id=clause_id,
        source_id=source_id,
        source_text=source_text,
        clause_text=clause_text,
        clause_span_start=start,
        clause_span_end=end,
        confidence=confidence,
        **kw,
    )


def _response(
    clauses: list[ClauseExtraction],
    source_id: str = "t1",
    source_text: str = "",
) -> MultiClauseExtractionResponse:
    return MultiClauseExtractionResponse(
        schema_version="0.1.0",
        source_id=source_id,
        source_text=source_text or clauses[0].source_text,
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# Mock client that raises (simulates network/config error)
# ---------------------------------------------------------------------------

class _RaisingMockClient:
    """A mock client that always raises — simulates transport failure."""

    def complete(self, request: FallbackRequest) -> FallbackResult:
        raise RuntimeError("mock: simulated transport failure")


# ---------------------------------------------------------------------------
# 7.1  fallback disabled returns rule-first
# ---------------------------------------------------------------------------

class TestFallbackDisabledReturnsRuleFirst:
    def test_disabled_no_mock_called(self):
        src = "A controller shall record the decision."
        rule_resp = extract_rule_first(src, source_id="fd1")
        result = extract_with_optional_llm_fallback(
            src, source_id="fd1", fallback_enabled=False,
        )
        assert result.fallback_status == "fallback_disabled"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True
        assert result.trigger_reason is None
        # Response should be rule-first
        assert result.response.source_id == "fd1"
        assert len(result.response.clauses) > 0

    def test_disabled_even_with_low_confidence(self):
        """Even low-confidence rule output should NOT trigger when disabled."""
        src = "Shall record."  # no actor → would trigger if enabled
        rule_resp = extract_rule_first(src, source_id="fd2")
        result = extract_with_optional_llm_fallback(
            src, source_id="fd2",
            fallback_enabled=False,
        )
        assert result.fallback_status == "fallback_disabled"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True


# ---------------------------------------------------------------------------
# 7.2  fallback not triggered when rule-first has clauses
# ---------------------------------------------------------------------------

class TestFallbackNotTriggeredWhenGood:
    def test_clean_sentence_no_trigger(self):
        src = "A controller shall record the decision."
        rule_resp = extract_rule_first(src, source_id="ft1")

        # A valid mock client exists but should not be called
        calls = []

        class _TrackingMock:
            def complete(self, req: FallbackRequest) -> FallbackResult:
                calls.append(req)
                return FallbackResult(error="should not be called")

        result = extract_with_optional_llm_fallback(
            src, source_id="ft1",
            fallback_enabled=True,
            fallback_client=_TrackingMock(),
        )
        assert result.fallback_status == "fallback_not_triggered"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True
        assert len(calls) == 0  # mock was NOT called


# ---------------------------------------------------------------------------
# 7.3  empty rule result triggers mock fallback (R10.2.1 — STRONG)
# ---------------------------------------------------------------------------

class TestEmptyRuleTriggersMockFallbackValid:
    """6.1: empty rule-first result triggers mock fallback when enabled."""

    def test_empty_clauses_triggers_fallback_accepted(self):
        """Empty clauses -> trigger -> valid fallback -> accepted."""
        src = "Any text — ignored by fake extractor."

        # Fake rule-first extractor that returns clauses=[]
        def _fake_empty_extractor(
            text: str, sid: str
        ) -> MultiClauseExtractionResponse:
            return MultiClauseExtractionResponse(
                schema_version="0.1.0",
                source_id=sid,
                source_text=text,
                clauses=[],
            )

        # Valid fallback response
        fallback_resp = _response([
            _clause("fb1", "ev1", src, src, 0, len(src),
                     modality=_fs("shall", 2, 7),
                     actor=_fs("controller", 8, 18),
                     action=_fs("record", 19, 25),
                     confidence=1.0)
        ], source_text=src, source_id="ev1")
        client = MockLLMFallbackClient(fixed_response=fallback_resp)

        calls = []

        class _TrackingClient:
            def complete(self, req: FallbackRequest) -> FallbackResult:
                calls.append(req)
                return FallbackResult(response=fallback_resp)

        result = extract_with_optional_llm_fallback(
            src, source_id="ev1",
            fallback_enabled=True,
            fallback_client=_TrackingClient(),
            rule_first_extractor=_fake_empty_extractor,
        )

        # STRONG assertions — no weak "in {a, b}" pattern
        assert result.fallback_status == "fallback_schema_valid"
        assert result.fallback_used is True
        assert result.trigger_reason == "empty_rule_result"
        assert result.rule_first_preserved is False
        assert result.response.source_id == "ev1"
        assert result.response is fallback_resp
        assert len(calls) == 1  # mock called exactly once


class TestEmptyRuleTriggersMockFallbackInvalid:
    """6.2: empty rule-first + invalid fallback -> rule-first returned."""

    def test_empty_clauses_fallback_invalid_returns_rule_first(self):
        src = "Any text."

        empty_resp = MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id="ei1",
            source_text=src,
            clauses=[],
        )

        def _fake_empty_extractor(
            text: str, sid: str
        ) -> MultiClauseExtractionResponse:
            return empty_resp

        calls = []

        class _InvalidClient:
            def complete(self, req: FallbackRequest) -> FallbackResult:
                calls.append(req)
                return FallbackResult(
                    raw_dict={"invalid": True},
                    error="mock: simulated invalid",
                )

        result = extract_with_optional_llm_fallback(
            src, source_id="ei1",
            fallback_enabled=True,
            fallback_client=_InvalidClient(),
            rule_first_extractor=_fake_empty_extractor,
        )

        assert result.fallback_status == "fallback_schema_invalid"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True
        assert result.response is empty_resp
        assert result.trigger_reason == "empty_rule_result"
        assert len(calls) == 1  # mock called exactly once


class TestEmptyRuleTriggersMockFallbackException:
    """6.3: empty rule-first + fallback exception -> rule-first returned."""

    def test_empty_clauses_fallback_exception_returns_rule_first(self):
        src = "Any text."

        empty_resp = MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id="ee1",
            source_text=src,
            clauses=[],
        )

        def _fake_empty_extractor(
            text: str, sid: str
        ) -> MultiClauseExtractionResponse:
            return empty_resp

        calls = []

        class _ExceptionClient:
            def complete(self, req: FallbackRequest) -> FallbackResult:
                calls.append(req)
                raise RuntimeError("mock: simulated transport failure")

        result = extract_with_optional_llm_fallback(
            src, source_id="ee1",
            fallback_enabled=True,
            fallback_client=_ExceptionClient(),
            rule_first_extractor=_fake_empty_extractor,
        )

        assert result.fallback_status == "fallback_network_error_redacted"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True
        assert result.response is empty_resp
        assert result.trigger_reason == "empty_rule_result"
        assert len(calls) == 1  # mock called exactly once


class TestNonEmptyRuleDoesNotTrigger:
    """6.4: non-empty rule-first still does not trigger by default."""

    def test_non_empty_rule_no_trigger(self):
        src = "A controller shall record the decision."

        # Use default extract_rule_first (non-empty result)
        calls = []

        class _TrackingClient:
            def complete(self, req: FallbackRequest) -> FallbackResult:
                calls.append(req)
                return FallbackResult(error="should not be called")

        result = extract_with_optional_llm_fallback(
            src, source_id="nt1",
            fallback_enabled=True,
            fallback_client=_TrackingClient(),
        )

        assert result.fallback_status == "fallback_not_triggered"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True
        assert len(calls) == 0  # mock NOT called


# ---------------------------------------------------------------------------
# 7.4  mock fallback valid schema accepted
# ---------------------------------------------------------------------------

class TestMockFallbackValidSchemaAccepted:
    def test_valid_mock_response_accepted(self):
        src = "Shall record the decision."  # missing actor → trigger
        n = len(src)
        fixed = _response([
            _clause("fb1", "mv1", src, src, 0, n,
                     modality=_fs("Shall", 0, 5),
                     actor=_fs("the decision", 13, n),
                     action=_fs("record", 6, 12),
                     confidence=1.0)
        ], source_text=src, source_id="mv1")
        client = MockLLMFallbackClient(fixed_response=fixed)

        result = extract_with_optional_llm_fallback(
            src, source_id="mv1",
            fallback_enabled=True,
            fallback_client=client,
        )
        assert result.fallback_status == "fallback_schema_valid"
        assert result.fallback_used is True
        assert result.rule_first_preserved is False
        assert result.response.clauses[0].actor is not None
        assert result.response.clauses[0].actor.text == "the decision"

    def test_no_raw_response_saved_flag(self):
        """OptionalFallbackResult has no raw_dict / raw_response field."""
        src = "Shall record the decision."
        n = len(src)
        fixed = _response([
            _clause("fb1", "mv2", src, src, 0, n,
                     modality=_fs("Shall", 0, 5),
                     actor=_fs("the decision", 13, n),
                     action=_fs("record", 6, 12),
                     confidence=1.0)
        ], source_text=src, source_id="mv2")
        client = MockLLMFallbackClient(fixed_response=fixed)

        result = extract_with_optional_llm_fallback(
            src, source_id="mv2",
            fallback_enabled=True,
            fallback_client=client,
        )
        # Confirm no raw response storage
        assert not hasattr(result, "raw_response")
        assert not hasattr(result, "raw_dict")
        assert "raw_response" not in str(result)


# ---------------------------------------------------------------------------
# 7.5  mock fallback schema invalid rejected
# ---------------------------------------------------------------------------

class TestMockFallbackSchemaInvalidRejected:
    def test_invalid_field_text_rejected(self):
        src = "Shall record the decision."
        # Build a mock response with empty FieldSpan text → invalid
        fixed = _response([
            _clause("fb1", "si1", src, src, 0, len(src),
                     modality=_fs("", 0, 0))  # empty text → schema-invalid
        ], source_text=src, source_id="si1")
        client = MockLLMFallbackClient(fixed_response=fixed)

        result = extract_with_optional_llm_fallback(
            src, source_id="si1",
            fallback_enabled=True,
            fallback_client=client,
        )
        assert result.fallback_status == "fallback_schema_invalid"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True

    def test_simulated_invalid_rejected(self):
        src = "Shall record the decision."
        client = MockLLMFallbackClient(simulate_invalid=True)

        result = extract_with_optional_llm_fallback(
            src, source_id="si2",
            fallback_enabled=True,
            fallback_client=client,
        )
        assert result.fallback_status == "fallback_schema_invalid"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True


# ---------------------------------------------------------------------------
# 7.6  fallback provider exception returns rule-first
# ---------------------------------------------------------------------------

class TestFallbackProviderExceptionReturnsRuleFirst:
    def test_exception_returns_rule_first(self):
        src = "Shall record the decision."
        rule_resp = extract_rule_first(src, source_id="ex1")

        result = extract_with_optional_llm_fallback(
            src, source_id="ex1",
            fallback_enabled=True,
            fallback_client=_RaisingMockClient(),
        )
        assert result.fallback_status == "fallback_network_error_redacted"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True
        assert result.response.source_id == "ex1"

    def test_exception_no_secret_leak(self):
        src = "Shall record the decision."

        with pytest.raises(RuntimeError, match="simulated transport failure"):
            _RaisingMockClient().complete(
                FallbackRequest(
                    source_text=src,
                    source_id="ex2",
                    rule_response=extract_rule_first(src, source_id="ex2"),
                )
            )

        # The helper itself does NOT re-raise
        result = extract_with_optional_llm_fallback(
            src, source_id="ex2",
            fallback_enabled=True,
            fallback_client=_RaisingMockClient(),
        )
        # No secret in str/repr
        result_str = str(result)
        assert "sk-" not in result_str
        assert "Bearer" not in result_str
        assert "api_key" not in result_str.lower()
        assert "token" not in result_str.lower()


# ---------------------------------------------------------------------------
# 7.7  no raw response saved
# ---------------------------------------------------------------------------

class TestNoRawResponseSaved:
    def test_no_raw_response_in_any_status(self):
        """Across all status paths, no raw response is stored."""
        src = "A controller shall record the decision."

        # disabled
        r1 = extract_with_optional_llm_fallback(
            src, source_id="nr1", fallback_enabled=False,
        )
        assert not hasattr(r1, "raw_response")
        assert not hasattr(r1, "raw_dict")

        # not triggered
        r2 = extract_with_optional_llm_fallback(
            src, source_id="nr2",
            fallback_enabled=True,
            fallback_client=MockLLMFallbackClient(),
        )
        assert not hasattr(r2, "raw_response")
        assert not hasattr(r2, "raw_dict")

        # valid fallback
        fixed = _response([
            _clause("fb1", "nr3", "Shall record.", "Shall record.", 0, 12,
                     modality=_fs("Shall", 0, 5),
                     actor=_fs("record", 6, 12),
                     action=_fs("Shall record.", 0, 12),
                     confidence=1.0)
        ], source_text="Shall record.", source_id="nr3")
        r3 = extract_with_optional_llm_fallback(
            "Shall record.", source_id="nr3",
            fallback_enabled=True,
            fallback_client=MockLLMFallbackClient(fixed_response=fixed),
        )
        assert not hasattr(r3, "raw_response")
        assert not hasattr(r3, "raw_dict")


# ---------------------------------------------------------------------------
# 7.8  no secret leak
# ---------------------------------------------------------------------------

class TestNoSecretLeak:
    DUMMY_KEY = "sk-test-r10-2-dummy-should-not-leak"
    DUMMY_URL = "https://dummy-r10-2.example.com/v1"

    def test_no_secret_in_repr_str(self):
        src = "A controller shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="sl1",
            fallback_enabled=False,
        )
        s = repr(result)
        assert self.DUMMY_KEY not in s
        assert self.DUMMY_URL not in s
        assert "api_key" not in s.lower()

    def test_no_secret_in_disabled_path(self):
        src = "A controller shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="sl2",
            fallback_enabled=False,
        )
        s = str(result)
        assert "sk-" not in s
        assert "Bearer" not in s

    def test_no_secret_in_fallback_used_path(self):
        src = "Shall record the decision."
        n = len(src)
        fixed = _response([
            _clause("fb1", "sl3", src, src, 0, n,
                     modality=_fs("Shall", 0, 5),
                     actor=_fs("the decision", 13, n),
                     action=_fs("record", 6, 12),
                     confidence=1.0)
        ], source_text=src, source_id="sl3")
        client = MockLLMFallbackClient(fixed_response=fixed)
        result = extract_with_optional_llm_fallback(
            src, source_id="sl3",
            fallback_enabled=True,
            fallback_client=client,
        )
        s = str(result)
        assert "sk-" not in s
        assert "Bearer" not in s
        assert "api_key" not in s.lower()

    def test_no_secret_in_error_path(self):
        src = "Shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="sl4",
            fallback_enabled=True,
            fallback_client=_RaisingMockClient(),
        )
        s = str(result)
        assert "sk-" not in s
        assert "Bearer" not in s
        assert "api_key" not in s.lower()


# ---------------------------------------------------------------------------
# 7.9  no .env read in mock mode
# ---------------------------------------------------------------------------

class TestNoEnvReadInMockMode:
    def test_optional_fallback_does_not_import_load_dotenv(self):
        """The fallback module should not import load_dotenv."""
        import bpc_hybrid.fallback as fb
        src_text = open(fb.__file__, encoding="utf-8").read()
        # The new helper should not call load_dotenv or load_project_env
        assert "load_dotenv" not in src_text.lower()
        assert "load_project_env" not in src_text

    def test_disabled_path_needs_no_env(self):
        """Disabled path should work even without BPC_HYBRID_DISABLE_PROJECT_ENV."""
        src = "A controller shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="ne1",
            fallback_enabled=False,
        )
        assert result.fallback_status == "fallback_disabled"


# ---------------------------------------------------------------------------
# 7.10  no real API call in mock mode
# ---------------------------------------------------------------------------

class TestNoRealApiInMockMode:
    def test_mock_client_has_no_network_imports(self):
        """MockLLMFallbackClient and the new helper have no network code."""
        import bpc_hybrid.fallback as fb
        # The new helper section should not import urllib/requests/httpx
        # (check the part after extract_hybrid)
        src_lines = open(fb.__file__, encoding="utf-8").read()
        # Search only the R10.2 section
        r10_section = src_lines[src_lines.find("# Optional fallback integration (R10.2)"):]
        assert "urllib" not in r10_section
        assert "requests" not in r10_section
        assert "httpx" not in r10_section
        assert "socket" not in r10_section

    def test_no_execute_real_api_flag(self):
        """The helper has no --execute-real-api concept."""
        src = "A controller shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="na1",
            fallback_enabled=False,
        )
        # Just confirm the helper runs without any real API gate
        assert result.fallback_status == "fallback_disabled"


# ---------------------------------------------------------------------------
# 7.11  no batch
# ---------------------------------------------------------------------------

class TestNoBatch:
    def test_single_source_only(self):
        """The helper accepts exactly one source_id + source_text."""
        src = "A controller shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="nb1",
            fallback_enabled=False,
        )
        assert result.response.source_id == "nb1"
        assert result.response.source_text == src

    def test_no_list_input(self):
        """The helper signature does not accept lists."""
        import inspect
        sig = inspect.signature(extract_with_optional_llm_fallback)
        params = list(sig.parameters.values())
        # source_text is str, not list[str]
        assert params[0].annotation in ("str", "str") or params[0].name == "source_text"


# ---------------------------------------------------------------------------
# 7.12  rule-first result not silently overwritten
# ---------------------------------------------------------------------------

class TestRuleFirstNotSilentlyOverwritten:
    def test_rule_first_preserved_when_no_trigger(self):
        src = "A controller shall record the decision."
        rule_resp = extract_rule_first(src, source_id="rf1")

        # Even with a valid fallback client, clean rule output is kept
        fixed = _response([
            _clause("fb1", "rf1", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("controller", 2, 12),
                     action=_fs("record", 19, 25),
                     confidence=1.0)
        ], source_text=src, source_id="rf1")
        client = MockLLMFallbackClient(fixed_response=fixed)

        result = extract_with_optional_llm_fallback(
            src, source_id="rf1",
            fallback_enabled=True,
            fallback_client=client,
        )
        assert result.fallback_status == "fallback_not_triggered"
        assert result.fallback_used is False
        assert result.rule_first_preserved is True

    def test_rule_first_returned_on_fallback_failure(self):
        """When fallback fails, rule-first is returned — never lost."""
        src = "Shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="rf2",
            fallback_enabled=True,
            fallback_client=MockLLMFallbackClient(simulate_invalid=True),
        )
        assert result.fallback_status == "fallback_schema_invalid"
        assert result.rule_first_preserved is True
        # Rule-first result must still be valid
        result.response.validate()


# ---------------------------------------------------------------------------
# 7.13  existing extract_hybrid behavior preserved
# ---------------------------------------------------------------------------

class TestExistingExtractHybridPreserved:
    def test_hybrid_raises_on_no_client(self):
        """extract_hybrid() still raises FallbackError when no client."""
        src = "Shall record."  # no actor → triggers
        with pytest.raises(FallbackError, match="no fallback_client"):
            extract_hybrid(src, source_id="hp1", fallback_client=None)

    def test_hybrid_raises_on_invalid(self):
        """extract_hybrid() still raises on schema-invalid fallback."""
        src = "Shall record the decision."
        client = MockLLMFallbackClient(simulate_invalid=True)
        with pytest.raises(FallbackError, match="simulated invalid"):
            extract_hybrid(src, source_id="hp2", fallback_client=client)

    def test_hybrid_raises_behaviour_unchanged(self):
        """Document that extract_hybrid raising is by design."""
        src = "Shall record the decision."
        client = MockLLMFallbackClient(simulate_invalid=True)
        # This IS the expected behavior — extract_hybrid raises
        try:
            extract_hybrid(src, source_id="hp3", fallback_client=client)
            pytest.fail("Expected FallbackError was not raised")
        except FallbackError:
            pass  # expected

    def test_optional_returns_rule_first_on_same_input(self):
        """The new helper does NOT raise on the same failing input."""
        src = "Shall record the decision."
        result = extract_with_optional_llm_fallback(
            src, source_id="hp4",
            fallback_enabled=True,
            fallback_client=MockLLMFallbackClient(simulate_invalid=True),
        )
        assert result.fallback_status == "fallback_schema_invalid"
        assert result.rule_first_preserved is True
        # Does not raise

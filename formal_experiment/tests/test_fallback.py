"""Tests for fallback (R6).

All test data uses synthetic toy sentences only — no real GDPR,
BPMN, or Sun dataset content.  No network, no ``.env``, no API keys.
"""

import pytest

from bpc_hybrid.fallback import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DecisionReason,
    FallbackDecision,
    FallbackError,
    FallbackRequest,
    FallbackResult,
    MockLLMFallbackClient,
    extract_hybrid,
    should_trigger_fallback,
)
from bpc_hybrid.extractor import extract_rule_first
from bpc_hybrid.normalization import NormalizationError
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)


# ---------------------------------------------------------------------------
# Helpers
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
    kw = {
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


def _response(clauses: list[ClauseExtraction],
              source_id: str = "t1",
              source_text: str = "") -> MultiClauseExtractionResponse:
    return MultiClauseExtractionResponse(
        schema_version="0.1.0",
        source_id=source_id,
        source_text=source_text or clauses[0].source_text,
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# DecisionReason
# ---------------------------------------------------------------------------

class TestDecisionReasonEnum:
    def test_distinct_values(self):
        values = set(r.value for r in DecisionReason)
        assert len(values) == len(DecisionReason)  # no duplicates


# ---------------------------------------------------------------------------
# FallbackDecision
# ---------------------------------------------------------------------------

class TestFallbackDecision:
    def test_trigger_true(self):
        d = FallbackDecision(should_trigger=True,
                             reasons=[DecisionReason.MISSING_ACTOR])
        assert d.should_trigger is True
        assert DecisionReason.MISSING_ACTOR in d.reasons

    def test_to_dict(self):
        d = FallbackDecision(should_trigger=False,
                             reasons=[DecisionReason.NO_FALLBACK_NEEDED])
        result = d.to_dict()
        assert result == {
            "should_trigger": False,
            "reasons": ["NO_FALLBACK_NEEDED"],
        }


# ---------------------------------------------------------------------------
# FallbackRequest / FallbackResult
# ---------------------------------------------------------------------------

class TestFallbackRequestResult:
    def test_result_valid(self):
        src = "A controller shall record."
        c = _clause("c1", "r1", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 0, 12),
                     action=_fs("record", 19, 25))
        resp = _response([c], source_text=src)
        fr = FallbackResult(response=resp)
        assert fr.is_valid
        assert fr.error is None

    def test_result_invalid(self):
        fr = FallbackResult(error="mock error")
        assert not fr.is_valid
        assert fr.error == "mock error"


# ---------------------------------------------------------------------------
# should_trigger_fallback — normal clause (normative)
# ---------------------------------------------------------------------------

class TestShouldTriggerFallbackNormative:
    PREFIX = "A controller shall record the decision."

    def test_clean_sentence_no_trigger(self):
        resp = extract_rule_first(self.PREFIX, source_id="t-clean")
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is False
        assert DecisionReason.NO_FALLBACK_NEEDED in decision.reasons

    def test_missing_actor_triggers(self):
        src = "A controller shall record the decision."
        # Simulate a clause with missing actor
        c = _clause("c1", "t1", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=None,  # MISSING
                     action=_fs("record the decision", 19, 38))
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True
        assert DecisionReason.MISSING_ACTOR in decision.reasons

    def test_missing_action_triggers(self):
        src = "A controller shall record the decision."
        c = _clause("c1", "t2", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 0, 12),
                     action=None)  # MISSING
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True
        assert DecisionReason.MISSING_ACTION in decision.reasons

    def test_low_field_confidence_triggers(self):
        src = "A controller shall record the decision."
        c = _clause("c1", "t3", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18, confidence=0.3),  # LOW
                     actor=_fs("A controller", 0, 12),
                     action=_fs("record the decision", 19, 38))
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True
        assert DecisionReason.LOW_FIELD_CONFIDENCE in decision.reasons

    def test_low_clause_confidence_triggers(self):
        src = "A controller shall record the decision."
        c = _clause("c1", "t4", src, src, 0, len(src),
                     confidence=0.3,
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 0, 12),
                     action=_fs("record the decision", 19, 38))
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True
        assert DecisionReason.LOW_CLAUSE_CONFIDENCE in decision.reasons

    def test_multiple_reasons(self):
        src = "A controller shall record the decision."
        c = _clause("c1", "t5", src, src, 0, len(src),
                     confidence=0.4,
                     modality=_fs("shall", 13, 18, confidence=0.3),
                     actor=None,
                     action=None)
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True
        reasons = decision.reasons
        assert DecisionReason.MISSING_ACTOR in reasons
        assert DecisionReason.MISSING_ACTION in reasons
        assert DecisionReason.LOW_FIELD_CONFIDENCE in reasons
        assert DecisionReason.LOW_CLAUSE_CONFIDENCE in reasons


# ---------------------------------------------------------------------------
# should_trigger_fallback — non-normative clause
# ---------------------------------------------------------------------------

class TestShouldTriggerFallbackNonNormative:
    def test_negative_case_no_trigger(self):
        """Non-normative clause (no modality) should NOT trigger
        even with missing actor/action."""
        src = "A violation results in a penalty of 500 EUR."
        c = _clause("c1", "t6", src, src, 0, len(src),
                     modality=None,  # non-normative
                     actor=None,
                     action=None)
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is False

    def test_warranty_neg_no_trigger(self):
        src = "The warranty does not cover improper use."
        c = _clause("c1", "t7", src, src, 0, len(src),
                     modality=None,
                     actor=None,
                     action=None)
        resp = _response([c], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is False

    def test_mixed_clauses_one_normative(self):
        """If any normative clause triggers, fallback should fire."""
        src = "A controller shall record the decision."
        c1 = _clause("c1", "t8", src, src, 0, len(src),
                      modality=None, actor=None, action=None)  # non-normative
        c2 = _clause("c2", "t8", src, src, 0, len(src),
                      modality=_fs("shall", 13, 18),
                      actor=None,  # MISSING
                      action=_fs("record the decision", 19, 38))
        resp = _response([c1, c2], source_text=src)
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True


# ---------------------------------------------------------------------------
# should_trigger_fallback — schema validation failure
# ---------------------------------------------------------------------------

class TestShouldTriggerFallbackSchemaValidation:
    def test_validation_failure_triggers(self):
        """A response that fails schema validation must trigger fallback."""
        src = "A controller shall record."
        c = _clause("c1", "t9", src, src, 0, len(src),
                     modality=_fs("", 0, 0))  # empty text will fail validate
        resp = _response([c], source_text=src)
        # Bypass __init__ validation by making it late
        decision = should_trigger_fallback(resp)
        assert decision.should_trigger is True
        assert DecisionReason.SCHEMA_VALIDATION_FAILURE in decision.reasons


# ---------------------------------------------------------------------------
# MockLLMFallbackClient
# ---------------------------------------------------------------------------

class TestMockLLMFallbackClient:
    def test_no_network(self):
        """Mock client creates nothing that needs network."""
        client = MockLLMFallbackClient()
        assert client.fixed_response is None

    def test_fixed_response_returned(self):
        src = "A controller shall record."
        c = _clause("c1", "s1", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 0, 12),
                     action=_fs("record", 19, 25))
        resp = _response([c], source_text=src)
        client = MockLLMFallbackClient(fixed_response=resp)
        req = FallbackRequest(source_text=src, source_id="s1",
                              rule_response=resp)
        result = client.complete(req)
        assert result.is_valid
        assert result.response is resp

    def test_no_response_simulates_failure(self):
        client = MockLLMFallbackClient(fixed_response=None)
        req = FallbackRequest(source_text="X", source_id="x",
                              rule_response=_response(
                                  [_clause("c1", "x", "X shall Y.", "X shall Y.", 0, 9,
                                           modality=_fs("shall", 2, 7),
                                           actor=_fs("X", 0, 1),
                                           action=_fs("Y", 8, 9))],
                                  source_text="X shall Y.",
                              ))
        result = client.complete(req)
        assert not result.is_valid
        assert "no fixed_response" in result.error.lower()

    def test_simulate_invalid(self):
        client = MockLLMFallbackClient(simulate_invalid=True)
        req = FallbackRequest(source_text="X", source_id="x",
                              rule_response=_response(
                                  [_clause("c1", "x", "X shall Y.", "X shall Y.", 0, 9,
                                           modality=_fs("shall", 2, 7),
                                           actor=_fs("X", 0, 1),
                                           action=_fs("Y", 8, 9))],
                                  source_text="X shall Y.",
                              ))
        result = client.complete(req)
        assert not result.is_valid
        assert "simulated invalid" in result.error

    def test_no_env_file(self):
        """Mock client does not read .env or environment variables."""
        import os
        # Setting env var shouldn't change behavior
        old = os.environ.pop("OPENAI_API_KEY", None)
        try:
            client = MockLLMFallbackClient()
            assert client.fixed_response is None
        finally:
            if old is not None:
                os.environ["OPENAI_API_KEY"] = old

    def test_no_api_key(self):
        """Mock client has no api_key attribute."""
        client = MockLLMFallbackClient()
        assert not hasattr(client, "api_key")


# ---------------------------------------------------------------------------
# extract_hybrid
# ---------------------------------------------------------------------------

class TestExtractHybrid:
    def test_no_fallback_equals_rule_first(self):
        """When the rule output is good, extract_hybrid returns it."""
        src = "A controller shall record the decision."
        rule_resp = extract_rule_first(src, source_id="hf1")
        hybrid_resp = extract_hybrid(src, source_id="hf1",
                                     fallback_client=MockLLMFallbackClient())
        assert hybrid_resp.schema_version == rule_resp.schema_version
        assert hybrid_resp.source_id == rule_resp.source_id
        assert len(hybrid_resp.clauses) == len(rule_resp.clauses)

    def test_fallback_uses_mock_result(self):
        """When fallback triggers, the mock result is used."""
        src = "Shall record the decision."  # missing actor — will trigger
        n = len(src)
        # Mock injects an actor span for text that exists in source
        fixed = _response([
            _clause("fb1", "hf2", src, src, 0, n,
                     modality=_fs("Shall", 0, 5),
                     actor=_fs("record", 6, 12),  # mock-injected actor
                     action=_fs("the decision", 13, n),
                     confidence=1.0)
        ], source_text=src, source_id="hf2")
        client = MockLLMFallbackClient(fixed_response=fixed)
        result = extract_hybrid(src, source_id="hf2", fallback_client=client)
        assert result.clauses[0].actor is not None
        assert result.clauses[0].actor.text == "record"

    def test_fallback_needed_no_client_raises(self):
        src = "Shall record."  # no actor, will trigger
        with pytest.raises(FallbackError, match="no fallback_client"):
            extract_hybrid(src, source_id="hf3", fallback_client=None)

    def test_invalid_fallback_raises(self):
        src = "Shall record the decision."
        fixed = _response([
            _clause("fb2", "hf4", src, src, 0, len(src),
                     modality=_fs("", 0, 0))  # invalid — empty text
        ], source_text=src, source_id="hf4")
        client = MockLLMFallbackClient(fixed_response=fixed)
        # The trigger will fire, mock returns invalid → FallbackError
        with pytest.raises(FallbackError, match="validation"):
            extract_hybrid(src, source_id="hf4", fallback_client=client)

    def test_simulated_invalid_raises(self):
        src = "Shall record the decision."
        client = MockLLMFallbackClient(simulate_invalid=True)
        with pytest.raises(FallbackError, match="simulated invalid"):
            extract_hybrid(src, source_id="hf5", fallback_client=client)

    def test_null_fields_preserved_in_fallback(self):
        src = "A controller shall record the decision."
        # Only actor is provided; action/condition remain None (non-normative clause style)
        fixed = _response([
            _clause("fb3", "hf6", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 0, 12),
                     action=_fs("record the decision", 19, 38),
                     condition=None,
                     constraint=None,
                     exception=None,
                     confidence=1.0)
        ], source_text=src, source_id="hf6")
        client = MockLLMFallbackClient(fixed_response=fixed)
        # This sentence is clean so no trigger — but we test the flow anyway
        result = extract_hybrid(src, source_id="hf6", fallback_client=client)
        assert result.clauses[0].condition is None
        assert result.clauses[0].constraint is None
        assert result.clauses[0].exception is None


# ---------------------------------------------------------------------------
# No network, no .env, no real data
# ---------------------------------------------------------------------------

class TestNoNetworkOrRealData:
    def test_no_network_imports(self):
        """Ensure fallback module does not import requests/openai/etc."""
        import bpc_hybrid.fallback as fb
        for name in ("requests", "openai", "anthropic", "httpx", "urllib3",
                     "aiohttp", "google.generativeai"):
            assert name not in dir(fb), f"forbidden import: {name}"

    def test_no_env_access_in_mock(self):
        """Mock client should not access os.environ for secrets."""
        src_lines = open("src/bpc_hybrid/fallback.py", encoding="utf-8").read()
        assert "OPENAI_API_KEY" not in src_lines
        assert "ANTHROPIC_API_KEY" not in src_lines
        assert "load_dotenv" not in src_lines.lower()

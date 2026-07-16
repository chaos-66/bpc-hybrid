"""Mock-only schema alignment tests (R11.2.1 — strict gate).

Tests the schema-alignment normalizer under the strict R11.2.1 gate policy:
missing top-level keys → rejected, unknown fields → rejected,
known unsupported model fields → rejected, non-dict clause items → rejected,
unsupported enum values → rejected, alias+target conflicts → rejected.

No real API, no ``.env``, no network, no raw response storage, no batch.
All test data is synthetic toy text — no real GDPR, BPMN, or Sun data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bpc_hybrid.fallback import (
    FallbackRequest,
    extract_with_optional_llm_fallback,
)
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMFallbackAdapter,
    LLMResponse,
    MockLLMTransport,
    _parse_and_align_llm_json_response,
)
from bpc_hybrid.llm_config import LLMConfig, LLMProvider
from bpc_hybrid.schema import (
    MultiClauseExtractionResponse,
    SchemaValidationError,
)
from bpc_hybrid.schema_alignment import (
    ERROR_ALIAS_CONFLICT,
    ERROR_INVALID_CLAUSE_ITEM,
    ERROR_INVALID_ENUM,
    ERROR_MISSING_TOP_KEY,
    ERROR_UNKNOWN_CLAUSE_FIELD,
    ERROR_UNKNOWN_TOP_FIELD,
    ERROR_UNSUPPORTED_MODEL_FIELD,
    normalize_llm_fallback_json,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TEXT = "A controller shall record the decision."
SAMPLE_LEN = len(SAMPLE_TEXT)


def _schema_valid_raw() -> dict:
    """Return a schema-valid raw dict (passes from_dict without normalizer)."""
    return {
        "schema_version": "0.1.0",
        "source_id": "sample-001",
        "source_text": SAMPLE_TEXT,
        "clauses": [
            {
                "clause_id": "sample-001-c1",
                "source_id": "sample-001",
                "source_text": SAMPLE_TEXT,
                "clause_text": SAMPLE_TEXT,
                "clause_span_start": 0,
                "clause_span_end": SAMPLE_LEN,
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
                    "span_end": SAMPLE_LEN,
                    "confidence": 0.90,
                },
                "condition": None,
                "constraint": None,
                "exception": None,
                "confidence": 0.90,
            }
        ],
    }


def _model_like_raw() -> dict:
    """Return a model-like raw dict using alias fields (NO object/original_text)."""
    return {
        "schema_version": "0.1.0",
        "source_id": "sample-001",
        "source_text": SAMPLE_TEXT,
        "clauses": [
            {
                "clause_id": "sample-001-c1",
                "source_id": "sample-001",
                "source_text": SAMPLE_TEXT,
                "clause_text": SAMPLE_TEXT,
                "clause_span_start": 0,
                "clause_span_end": SAMPLE_LEN,
                "normative_type": {
                    "text": "shall",
                    "span_start": 13,
                    "span_end": 18,
                    "confidence": 0.95,
                },
                "subject": {
                    "text": "A controller",
                    "span_start": 0,
                    "span_end": 12,
                    "confidence": 0.90,
                },
                "action": {
                    "text": "record the decision",
                    "span_start": 19,
                    "span_end": SAMPLE_LEN,
                    "confidence": 0.90,
                },
                "conditions": {
                    "text": "if applicable",
                    "span_start": 0,
                    "span_end": 13,
                    "confidence": 0.85,
                },
                "constraint": None,
                "exception": None,
                "confidence": 0.90,
            }
        ],
    }


def _make_config(enabled: bool = True) -> LLMConfig:
    return LLMConfig(provider=LLMProvider.MOCK, model="mock-model", enabled=enabled)


# ===========================================================================
# 1. Top-level explicit-key gate
# ===========================================================================


class TestTopLevelExplicitKeys:
    """Missing explicit top-level keys → rejected (no parser defaulting)."""

    def test_missing_schema_version_rejected(self):
        raw = {"source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": []}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_MISSING_TOP_KEY
        assert "schema_version" in result.error_message

    def test_missing_source_id_rejected(self):
        raw = {"schema_version": "0.1.0", "source_text": SAMPLE_TEXT, "clauses": []}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_MISSING_TOP_KEY
        assert "source_id" in result.error_message

    def test_missing_source_text_rejected(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "clauses": []}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_MISSING_TOP_KEY
        assert "source_text" in result.error_message

    def test_missing_clauses_rejected(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_MISSING_TOP_KEY
        assert "clauses" in result.error_message

    def test_all_four_keys_present_accepted(self):
        result = normalize_llm_fallback_json(_schema_valid_raw())
        assert result.status in ("noop", "accepted")
        assert result.normalized is not None


# ===========================================================================
# 2. Unknown field rejection
# ===========================================================================


class TestUnknownFieldRejection:
    """Unknown top-level and clause-level fields → rejected."""

    def test_unknown_top_level_field_rejected(self):
        raw = dict(_schema_valid_raw())
        raw["extra_top_key"] = 42
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_UNKNOWN_TOP_FIELD
        assert "extra_top_key" in result.error_message

    def test_unknown_clause_field_rejected(self):
        raw = _schema_valid_raw()
        raw["clauses"][0]["made_up_field"] = "nonsense"
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_UNKNOWN_CLAUSE_FIELD
        assert "made_up_field" in result.error_message

    def test_object_rejected_as_unsupported_model_field(self):
        raw = _schema_valid_raw()
        raw["clauses"][0]["object"] = "some object text"
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_UNSUPPORTED_MODEL_FIELD
        assert "object" in result.error_message

    def test_original_text_rejected_as_unsupported_model_field(self):
        raw = _schema_valid_raw()
        raw["clauses"][0]["original_text"] = SAMPLE_TEXT
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_UNSUPPORTED_MODEL_FIELD
        assert "original_text" in result.error_message


# ===========================================================================
# 3. Clause item integrity
# ===========================================================================


class TestClauseItemIntegrity:
    """Non-dict items in clauses → rejected."""

    def test_string_item_in_clauses_rejected(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": ["bad"]}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_INVALID_CLAUSE_ITEM

    def test_none_item_in_clauses_rejected(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": [None]}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_INVALID_CLAUSE_ITEM

    def test_numeric_item_in_clauses_rejected(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": [123]}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_INVALID_CLAUSE_ITEM

    def test_mixed_valid_and_invalid_rejected(self):
        raw = _schema_valid_raw()
        raw["clauses"].append("not-a-dict")
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_INVALID_CLAUSE_ITEM

    def test_non_list_clauses_rejected(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": "not a list"}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_INVALID_CLAUSE_ITEM


# ===========================================================================
# 4. Mapping rules
# ===========================================================================


class TestMappingRules:
    """Supported alias mappings accepted; unsupported cases rejected."""

    def test_normative_type_to_modality_accepted(self):
        result = normalize_llm_fallback_json(_model_like_raw())
        assert result.status == "accepted"
        c = result.normalized["clauses"][0]
        assert "normative_type" not in c
        assert c["modality"]["text"] == "shall"
        assert result.mappings_applied >= 1

    def test_subject_to_actor_accepted(self):
        result = normalize_llm_fallback_json(_model_like_raw())
        c = result.normalized["clauses"][0]
        assert "subject" not in c
        assert c["actor"]["text"] == "A controller"

    def test_conditions_to_condition_accepted(self):
        result = normalize_llm_fallback_json(_model_like_raw())
        c = result.normalized["clauses"][0]
        assert "conditions" not in c
        assert c["condition"]["text"] == "if applicable"

    def test_unsupported_normative_type_enum_rejected(self):
        raw = _model_like_raw()
        raw["clauses"][0]["normative_type"] = "obligation"
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_INVALID_ENUM

    def test_alias_target_conflict_rejected(self):
        raw = _model_like_raw()
        raw["clauses"][0]["modality"] = {"text": "must", "span_start": 0, "span_end": 4, "confidence": 1.0}
        result = normalize_llm_fallback_json(raw)
        assert result.status == "error"
        assert result.error_reason == ERROR_ALIAS_CONFLICT


# ===========================================================================
# 5. Schema gate
# ===========================================================================


class TestSchemaGate:
    """Valid candidates accepted; invalid candidates rejected."""

    def test_valid_project_schema_accepted(self):
        result = normalize_llm_fallback_json(_schema_valid_raw())
        assert result.status == "noop"
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()

    def test_normalized_model_like_accepted(self):
        result = normalize_llm_fallback_json(_model_like_raw())
        assert result.status == "accepted"
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()
        c = response.clauses[0]
        assert c.modality is not None
        assert c.actor is not None
        assert c.condition is not None

    def test_normalized_schema_invalid_rejected_by_from_dict(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": [{"clause_id": "c1"}]}
        result = normalize_llm_fallback_json(raw)
        assert result.status in ("noop", "accepted")
        with pytest.raises(SchemaValidationError, match="Missing required key"):
            MultiClauseExtractionResponse.from_dict(result.normalized)

    def test_missing_required_clause_field_rejected_by_from_dict(self):
        result = normalize_llm_fallback_json(_model_like_raw())
        del result.normalized["clauses"][0]["clause_id"]
        with pytest.raises(SchemaValidationError, match="Missing required key"):
            MultiClauseExtractionResponse.from_dict(result.normalized)

    def test_invalid_fieldspan_shape_rejected_by_validate(self):
        raw = _schema_valid_raw()
        raw["clauses"][0]["modality"] = {"text": "", "span_start": 0, "span_end": 5, "confidence": 0.9}
        result = normalize_llm_fallback_json(raw)
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        with pytest.raises(SchemaValidationError, match="non-empty"):
            response.validate()

    def test_non_dict_candidate_rejected(self):
        result = normalize_llm_fallback_json([1, 2, 3])
        assert result.status == "error"
        assert result.normalized is None

    def test_empty_clauses_accepted(self):
        raw = {"schema_version": "0.1.0", "source_id": "s1", "source_text": SAMPLE_TEXT, "clauses": []}
        result = normalize_llm_fallback_json(raw)
        assert result.status in ("noop", "accepted")
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()


# ===========================================================================
# 6. Adapter integration
# ===========================================================================


class TestAdapterIntegration:
    """LLMFallbackAdapter integration with strict normalizer gate."""

    def test_schema_valid_normalized_accepted(self):
        config = _make_config()
        transport = MockLLMTransport(fixed_response=LLMResponse(
            content=json.dumps(_model_like_raw()), provider="mock", model="mock-model"))
        adapter = LLMFallbackAdapter(config=config, transport=transport, enable_schema_alignment=True)
        result = adapter.complete(FallbackRequest(
            source_text=SAMPLE_TEXT, source_id="sample-001",
            rule_response=MultiClauseExtractionResponse(source_id="sample-001", source_text=SAMPLE_TEXT, clauses=[])))
        assert result.is_valid
        assert result.response.clauses[0].modality.text == "shall"

    def test_schema_invalid_normalized_returns_rule_first(self):
        config = _make_config()
        transport = MockLLMTransport(fixed_response=LLMResponse(
            content=json.dumps({"wrong_shape": [1, 2, 3]}), provider="mock", model="mock-model"))
        adapter = LLMFallbackAdapter(config=config, transport=transport, enable_schema_alignment=True)
        result = extract_with_optional_llm_fallback(
            source_text=SAMPLE_TEXT, source_id="sample-001", fallback_enabled=True,
            fallback_client=adapter, explicit_controlled_smoke=True)
        assert not result.fallback_used
        assert result.fallback_status == "fallback_schema_invalid"

    def test_normalizer_rejection_returns_rule_first(self):
        config = _make_config()
        raw = _schema_valid_raw()
        raw["clauses"][0]["object"] = "consent"
        transport = MockLLMTransport(fixed_response=LLMResponse(
            content=json.dumps(raw), provider="mock", model="mock-model"))
        adapter = LLMFallbackAdapter(config=config, transport=transport, enable_schema_alignment=True)
        result = extract_with_optional_llm_fallback(
            source_text=SAMPLE_TEXT, source_id="sample-001", fallback_enabled=True,
            fallback_client=adapter, explicit_controlled_smoke=True)
        assert not result.fallback_used

    def test_fallback_disabled_returns_rule_first(self):
        config = LLMConfig(provider=LLMProvider.MOCK, model="mock-model", enabled=False)
        adapter = LLMFallbackAdapter(config=config, enable_schema_alignment=True)
        result = adapter.complete(FallbackRequest(
            source_text=SAMPLE_TEXT, source_id="sample-001",
            rule_response=MultiClauseExtractionResponse(source_id="sample-001", source_text=SAMPLE_TEXT, clauses=[])))
        assert not result.is_valid
        assert "disabled" in result.error.lower()

    def test_fallback_exception_returns_rule_first(self):
        config = _make_config()
        transport = MockLLMTransport(fixed_response=None)
        adapter = LLMFallbackAdapter(config=config, transport=transport, enable_schema_alignment=True)
        result = adapter.complete(FallbackRequest(
            source_text=SAMPLE_TEXT, source_id="sample-001",
            rule_response=MultiClauseExtractionResponse(source_id="sample-001", source_text=SAMPLE_TEXT, clauses=[])))
        assert not result.is_valid
        assert "transport error" in result.error.lower()


# ===========================================================================
# 7. Parse-and-align function
# ===========================================================================


class TestParseAndAlign:
    """Tests for _parse_and_align_llm_json_response."""

    def test_model_like_succeeds(self):
        response = _parse_and_align_llm_json_response(json.dumps(_model_like_raw()))
        assert isinstance(response, MultiClauseExtractionResponse)
        assert response.clauses[0].modality is not None

    def test_schema_valid_passthrough(self):
        response = _parse_and_align_llm_json_response(json.dumps(_schema_valid_raw()))
        assert isinstance(response, MultiClauseExtractionResponse)
        response.validate()

    def test_invalid_json_raises(self):
        with pytest.raises(LLMClientError, match="not valid JSON"):
            _parse_and_align_llm_json_response("not json {{{")

    def test_non_dict_raises(self):
        with pytest.raises(LLMClientError, match="JSON object"):
            _parse_and_align_llm_json_response("[1, 2, 3]")

    def test_normalizer_rejected_raises(self):
        with pytest.raises(LLMClientError, match="normalizer failed"):
            _parse_and_align_llm_json_response(json.dumps({"wrong_shape": True}))

    def test_markdown_wrapped(self):
        content = "```json\n" + json.dumps(_model_like_raw()) + "\n```"
        response = _parse_and_align_llm_json_response(content)
        assert isinstance(response, MultiClauseExtractionResponse)


# ===========================================================================
# 8. Safety tests
# ===========================================================================


class TestNormalizerSafety:
    """Safety and constraint tests (no env, no network, no file write, no batch)."""

    def test_no_env_read(self):
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        assert "dotenv" not in src.lower()
        assert "os.environ" not in src
        assert "load_dotenv" not in src

    def test_no_network(self):
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        for token in ("urllib", "socket", "http", "requests", "httpx", "urlopen"):
            assert token not in src.lower(), f"Network token '{token}' found"

    def test_no_raw_response_saved(self):
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        for token in ("open(", "write(", "writelines", "json.dump"):
            assert token not in src, f"File-write token '{token}' found"

    def test_no_real_api_in_normalizer(self):
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        assert "RealAPI" not in src
        assert "openai" not in src.lower()

    def test_no_batch(self):
        src_n = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        src_l = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "llm_client.py").read_text(encoding="utf-8")
        for s in (src_n, src_l):
            assert "batch" not in s.lower() or "no batch" in s.lower()

    def test_deterministic(self):
        raw = _model_like_raw()
        r1 = normalize_llm_fallback_json(raw)
        r2 = normalize_llm_fallback_json(raw)
        assert r1.status == r2.status
        assert r1.error_reason == r2.error_reason
        assert r1.mappings_applied == r2.mappings_applied

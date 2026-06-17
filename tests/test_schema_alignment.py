"""Mock-only schema alignment tests (R11.2).

Tests the schema-alignment normalizer and its integration into
``LLMFallbackAdapter`` and ``extract_with_optional_llm_fallback()``.

No real API, no ``.env``, no network, no raw response storage, no batch.
All test data is synthetic toy text — no real GDPR, BPMN, or Sun data.
"""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest

from bpc_hybrid.fallback import (
    FallbackRequest,
    FallbackResult,
    MockLLMFallbackClient,
    extract_with_optional_llm_fallback,
)
from bpc_hybrid.llm_client import (
    LLMClientError,
    LLMFallbackAdapter,
    LLMResponse,
    MockLLMTransport,
    _parse_and_align_llm_json_response,
    parse_llm_json_response,
)
from bpc_hybrid.llm_config import LLMConfig, LLMProvider
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)
from bpc_hybrid.schema_alignment import (
    NormalizationResult,
    normalize_llm_fallback_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TEXT = "A controller shall record the decision."


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
                "clause_span_end": len(SAMPLE_TEXT),
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
                    "span_end": len(SAMPLE_TEXT),
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
    """Return a model-like raw dict using fields from R10.3 mismatch."""
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
                "clause_span_end": len(SAMPLE_TEXT),
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
                    "span_end": len(SAMPLE_TEXT),
                    "confidence": 0.90,
                },
                "conditions": {
                    "text": "if applicable",
                    "span_start": 0,
                    "span_end": 13,
                    "confidence": 0.85,
                },
                "object": "some object text",
                "original_text": SAMPLE_TEXT,
                "constraint": None,
                "exception": None,
                "confidence": 0.90,
            }
        ],
    }


def _model_like_with_extra_top_level() -> dict:
    """Model-like with extra unknown top-level key."""
    d = _model_like_raw()
    d["unknown_top_key"] = 42
    return d


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


# ===========================================================================
# 8.1 Normalizer Unit Tests
# ===========================================================================


class TestNormalizerTopLevel:
    """Tests for top-level key normalization."""

    def test_top_level_clean_passthrough(self):
        """Top-level keys already matching pass through unchanged."""
        raw = _schema_valid_raw()
        result = normalize_llm_fallback_json(raw)
        assert result.status in ("noop", "applied")
        assert result.normalized is not None
        assert result.normalized["schema_version"] == "0.1.0"
        assert result.normalized["source_id"] == "sample-001"
        assert result.normalized["source_text"] == SAMPLE_TEXT
        assert isinstance(result.normalized["clauses"], list)

    def test_top_level_unknown_removed(self):
        """Unknown top-level keys are removed."""
        raw = dict(_schema_valid_raw())
        raw["extra_field"] = "should-be-removed"
        raw["another_unknown"] = 123
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        assert "extra_field" not in result.normalized
        assert "another_unknown" not in result.normalized
        assert result.normalized["schema_version"] == "0.1.0"

    def test_top_level_unknown_in_model_like(self):
        """Model-like dict with extra top-level key has it removed."""
        raw = _model_like_with_extra_top_level()
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        assert "unknown_top_key" not in result.normalized
        assert result.status == "applied"
        assert result.fields_removed >= 1


class TestNormalizerClauseMapping:
    """Tests for clause-level field-name mapping."""

    def test_normative_type_to_modality(self):
        """``normative_type`` dict → ``modality`` FieldSpan."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        clause = result.normalized["clauses"][0]
        assert "normative_type" not in clause
        assert "modality" in clause
        assert clause["modality"]["text"] == "shall"

    def test_subject_to_actor(self):
        """``subject`` dict → ``actor`` FieldSpan."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert "subject" not in clause
        assert "actor" in clause
        assert clause["actor"]["text"] == "A controller"

    def test_conditions_to_condition(self):
        """``conditions`` dict → ``condition`` FieldSpan."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert "conditions" not in clause
        assert "condition" in clause
        assert clause["condition"]["text"] == "if applicable"

    def test_object_removed(self):
        """``object`` key removed (no schema target)."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert "object" not in clause

    def test_original_text_removed(self):
        """``original_text`` key removed (no schema target)."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert "original_text" not in clause


class TestNormalizerTypeCoercion:
    """Tests for field-level type coercion."""

    def test_string_value_to_null(self):
        """Plain string where FieldSpan expected → ``null``."""
        raw = _model_like_raw()
        # Change normative_type from dict to string
        raw["clauses"][0]["normative_type"] = "obligation"
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert clause["modality"] is None

    def test_string_subject_to_null(self):
        """Plain string ``subject`` → ``null`` for actor."""
        raw = _model_like_raw()
        raw["clauses"][0]["subject"] = "controller"
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert clause["actor"] is None

    def test_string_conditions_to_null(self):
        """Plain string ``conditions`` → ``null`` for condition."""
        raw = _model_like_raw()
        raw["clauses"][0]["conditions"] = "if applicable"
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert clause["condition"] is None

    def test_preserves_null_fields(self):
        """``null`` semantic fields remain ``null``."""
        raw = _schema_valid_raw()
        raw["clauses"][0]["constraint"] = None
        raw["clauses"][0]["exception"] = None
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert clause["constraint"] is None
        assert clause["exception"] is None

    def test_preserves_valid_clause(self):
        """Schema-valid clause passes through normalizer unchanged."""
        raw = _schema_valid_raw()
        result = normalize_llm_fallback_json(raw)
        # Should be importable into schema
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()

    def test_preserves_non_semantic_fields(self):
        """Non-semantic fields pass through unchanged."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert clause["clause_id"] == "sample-001-c1"
        assert clause["source_id"] == "sample-001"
        assert clause["source_text"] == SAMPLE_TEXT
        assert clause["clause_text"] == SAMPLE_TEXT
        assert clause["clause_span_start"] == 0
        assert clause["clause_span_end"] == len(SAMPLE_TEXT)
        assert clause["confidence"] == 0.90

    def test_unknown_clause_key_removed(self):
        """Unknown clause-level keys are removed."""
        raw = _schema_valid_raw()
        raw["clauses"][0]["made_up_field"] = "nonsense"
        raw["clauses"][0]["extra_number"] = 99
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert "made_up_field" not in clause
        assert "extra_number" not in clause

    def test_keeps_existing_project_key(self):
        """When model key maps to an existing project key, the project key wins."""
        raw = _model_like_raw()
        # Already has 'action' as a native field; 'subject' maps to 'actor'
        result = normalize_llm_fallback_json(raw)
        clause = result.normalized["clauses"][0]
        assert "action" in clause
        assert clause["action"]["text"] == "record the decision"


class TestNormalizerEdgeCases:
    """Edge-case and error-handling tests."""

    def test_non_dict_rejected(self):
        """Non-dict input returns error status."""
        result = normalize_llm_fallback_json([1, 2, 3])
        assert result.status == "error"
        assert result.normalized is None
        assert result.error_message is not None

    def test_non_dict_string_rejected(self):
        """String input returns error status."""
        result = normalize_llm_fallback_json("not a dict")
        assert result.status == "error"
        assert result.normalized is None

    def test_non_dict_clause_skipped(self):
        """Non-dict item in clauses is skipped (not crashed)."""
        raw = _schema_valid_raw()
        raw["clauses"].append("not-a-dict")
        raw["clauses"].append(42)
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        # The non-dict items should be removed by normalizer
        assert len(result.normalized["clauses"]) == 1  # only the valid one

    def test_empty_clauses(self):
        """Empty clauses array passes through."""
        raw = {
            "schema_version": "0.1.0",
            "source_id": "sample-001",
            "source_text": SAMPLE_TEXT,
            "clauses": [],
        }
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        assert result.normalized["clauses"] == []

    def test_model_output_to_valid(self):
        """Full model-like dict normalizes to schema-valid dict."""
        raw = _model_like_raw()
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        # Should be importable into schema
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()
        assert response.clauses[0].modality is not None
        assert response.clauses[0].modality.text == "shall"
        assert response.clauses[0].actor is not None
        assert response.clauses[0].actor.text == "A controller"

    def test_full_realistic_model_output(self):
        """Comprehensive model-like output with mixed types normalizes correctly."""
        raw = {
            "schema_version": "0.1.0",
            "source_id": "doc-001",
            "source_text": "The data subject shall provide consent before processing.",
            "extra_top_level": "remove-me",
            "clauses": [
                {
                    "clause_id": "doc-001-c1",
                    "source_id": "doc-001",
                    "source_text": "The data subject shall provide consent before processing.",
                    "clause_text": "The data subject shall provide consent before processing.",
                    "clause_span_start": 0,
                    "clause_span_end": 62,
                    "normative_type": {
                        "text": "shall",
                        "span_start": 18,
                        "span_end": 23,
                        "confidence": 0.95,
                    },
                    "subject": {
                        "text": "The data subject",
                        "span_start": 0,
                        "span_end": 16,
                        "confidence": 0.90,
                    },
                    "action": {
                        "text": "provide consent",
                        "span_start": 24,
                        "span_end": 39,
                        "confidence": 0.88,
                    },
                    "object": "consent",  # should be removed
                    "original_text": "The data subject shall provide consent before processing.",  # removed
                    "conditions": {
                        "text": "before processing",
                        "span_start": 40,
                        "span_end": 57,
                        "confidence": 0.85,
                    },
                    "constraint": None,
                    "exception": None,
                    "confidence": 0.90,
                    "extra_clause_field": "remove-me-too",
                }
            ],
        }
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        assert "extra_top_level" not in result.normalized
        clause = result.normalized["clauses"][0]
        assert "normative_type" not in clause
        assert clause["modality"]["text"] == "shall"
        assert "subject" not in clause
        assert clause["actor"]["text"] == "The data subject"
        assert "conditions" not in clause
        assert clause["condition"]["text"] == "before processing"
        assert "object" not in clause
        assert "original_text" not in clause
        assert "extra_clause_field" not in clause
        # Verify schema import
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()


# ===========================================================================
# 8.2 Adapter Integration Tests
# ===========================================================================


class TestAdapterIntegration:
    """Tests for LLMFallbackAdapter with normalizer."""

    @staticmethod
    def _make_config(enabled: bool = True) -> LLMConfig:
        return LLMConfig(
            provider=LLMProvider.MOCK,
            model="mock-model",
            enabled=enabled,
        )

    def test_adapter_with_normalizer_accepts_mapped(self):
        """Mock LLM returns model-like output → normalizer maps → valid."""
        config = self._make_config()
        transport = MockLLMTransport(
            fixed_response=LLMResponse(
                content=json.dumps(_model_like_raw()),
                provider="mock",
                model="mock-model",
            )
        )
        adapter = LLMFallbackAdapter(
            config=config,
            transport=transport,
            enable_schema_alignment=True,
        )
        result = adapter.complete(
            FallbackRequest(
                source_text=SAMPLE_TEXT,
                source_id="sample-001",
                rule_response=MultiClauseExtractionResponse(
                    source_id="sample-001",
                    source_text=SAMPLE_TEXT,
                    clauses=[],
                ),
            )
        )
        assert result.is_valid
        assert result.response is not None
        assert result.response.clauses[0].modality is not None
        assert result.response.clauses[0].modality.text == "shall"
        assert result.response.clauses[0].actor is not None
        assert result.response.clauses[0].actor.text == "A controller"

    def test_adapter_with_normalizer_rejects_unmappable(self):
        """Output with no mappable fields → schema validation fails → error."""
        config = self._make_config()
        transport = MockLLMTransport(
            fixed_response=LLMResponse(
                content=json.dumps({
                    "schema_version": "0.1.0",
                    "source_id": "sample-001",
                    "source_text": SAMPLE_TEXT,
                    "clauses": [
                        {
                            "unknown_a": 1,
                            "unknown_b": "text",
                        }
                    ],
                }),
                provider="mock",
                model="mock-model",
            )
        )
        adapter = LLMFallbackAdapter(
            config=config,
            transport=transport,
            enable_schema_alignment=True,
        )
        result = adapter.complete(
            FallbackRequest(
                source_text=SAMPLE_TEXT,
                source_id="sample-001",
                rule_response=MultiClauseExtractionResponse(
                    source_id="sample-001",
                    source_text=SAMPLE_TEXT,
                    clauses=[],
                ),
            )
        )
        assert not result.is_valid
        assert result.error is not None

    def test_adapter_no_normalizer_still_rejects(self):
        """Without normalizer, model-like output still rejected (baseline)."""
        config = self._make_config()
        transport = MockLLMTransport(
            fixed_response=LLMResponse(
                content=json.dumps(_model_like_raw()),
                provider="mock",
                model="mock-model",
            )
        )
        adapter = LLMFallbackAdapter(
            config=config,
            transport=transport,
            enable_schema_alignment=False,
        )
        result = adapter.complete(
            FallbackRequest(
                source_text=SAMPLE_TEXT,
                source_id="sample-001",
                rule_response=MultiClauseExtractionResponse(
                    source_id="sample-001",
                    source_text=SAMPLE_TEXT,
                    clauses=[],
                ),
            )
        )
        # Without normalizer, model-like fields (normative_type, subject, etc.)
        # produce unknown-key errors in ClauseExtraction.from_dict()
        assert not result.is_valid
        assert result.error is not None

    def test_optional_fallback_accepts_normalized(self):
        """``extract_with_optional_llm_fallback()`` — normalizer → valid."""
        config = self._make_config()
        transport = MockLLMTransport(
            fixed_response=LLMResponse(
                content=json.dumps(_model_like_raw()),
                provider="mock",
                model="mock-model",
            )
        )
        adapter = LLMFallbackAdapter(
            config=config,
            transport=transport,
            enable_schema_alignment=True,
        )

        result = extract_with_optional_llm_fallback(
            source_text=SAMPLE_TEXT,
            source_id="sample-001",
            fallback_enabled=True,
            fallback_client=adapter,
            explicit_controlled_smoke=True,  # force trigger
        )
        assert result.fallback_used
        assert result.fallback_status == "fallback_schema_valid"
        assert result.response.clauses[0].modality is not None

    def test_optional_fallback_returns_rule_first_on_normalized_invalid(self):
        """Normalized output still invalid → rule-first preserved."""
        config = self._make_config()
        transport = MockLLMTransport(
            fixed_response=LLMResponse(
                content=json.dumps({
                    "wrong_shape": [1, 2, 3],
                }),
                provider="mock",
                model="mock-model",
            )
        )
        adapter = LLMFallbackAdapter(
            config=config,
            transport=transport,
            enable_schema_alignment=True,
        )

        result = extract_with_optional_llm_fallback(
            source_text=SAMPLE_TEXT,
            source_id="sample-001",
            fallback_enabled=True,
            fallback_client=adapter,
            explicit_controlled_smoke=True,
        )
        assert not result.fallback_used
        assert result.rule_first_preserved
        assert result.fallback_status == "fallback_schema_invalid"


# ===========================================================================
# 8.3 Safety Tests
# ===========================================================================


class TestNormalizerSafety:
    """Safety and constraint tests."""

    def test_no_env_read(self):
        """Normalizer does not access ``.env``."""
        # Verify the normalizer source code has no os.environ / dotenv references
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        assert "dotenv" not in src.lower()
        assert "os.environ" not in src
        assert "load_dotenv" not in src

    def test_no_network(self):
        """Normalizer does not make network calls."""
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        for token in ("urllib", "socket", "http", "requests", "httpx", "urlopen"):
            assert token not in src.lower(), f"Network token '{token}' found in normalizer source"

    def test_no_raw_response_saved(self):
        """Normalizer does not write files."""
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        for token in ("open(", "write(", "writelines", "json.dump", "json.dumps"):
            assert token not in src, f"File-write token '{token}' found in normalizer source"

    def test_no_real_api_in_normalizer(self):
        """Normalizer code has no real provider import/usage."""
        src = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        assert "RealAPI" not in src
        assert "real_api" not in src
        assert "openai" not in src.lower()

    def test_fallback_disabled_returns_rule_first(self):
        """``config.enabled=False`` → rule-first regardless of normalizer."""
        config = LLMConfig(
            provider=LLMProvider.MOCK,
            model="mock-model",
            enabled=False,
        )
        adapter = LLMFallbackAdapter(
            config=config,
            enable_schema_alignment=True,
        )
        result = adapter.complete(
            FallbackRequest(
                source_text=SAMPLE_TEXT,
                source_id="sample-001",
                rule_response=MultiClauseExtractionResponse(
                    source_id="sample-001",
                    source_text=SAMPLE_TEXT,
                    clauses=[],
                ),
            )
        )
        assert not result.is_valid
        assert "disabled" in result.error.lower()

    def test_no_batch(self):
        """No batch mode in normalizer or adapter."""
        src_normalizer = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "schema_alignment.py").read_text(encoding="utf-8")
        src_llm = (Path(__file__).parents[1] / "src" / "bpc_hybrid" / "llm_client.py").read_text(encoding="utf-8")
        for src in (src_normalizer, src_llm):
            assert "batch" not in src.lower() or "no batch" in src.lower(), \
                "Batch language found without explicit denial"


# ===========================================================================
# 8.4 Top-level Parser / Normalizer Tests
# ===========================================================================


class TestTopLevelParserNuance:
    """Tests for top-level parser defaulting behavior and normalizer enforcement."""

    def test_missing_schema_version_defaults_in_parser(self):
        """Missing ``schema_version`` defaults to ``\"0.1.0\"`` in current parser."""
        # This test confirms CURRENT parser behavior, not normalizer behavior
        raw = {
            "source_id": "sample-001",
            "source_text": SAMPLE_TEXT,
            "clauses": [],
        }
        # Current parser defaults schema_version to "0.1.0"
        response = MultiClauseExtractionResponse.from_dict(raw)
        assert response.schema_version == "0.1.0"

    def test_missing_clauses_defaults_in_parser(self):
        """Missing ``clauses`` defaults to ``[]`` in current parser."""
        raw = {
            "schema_version": "0.1.0",
            "source_id": "sample-001",
            "source_text": SAMPLE_TEXT,
        }
        response = MultiClauseExtractionResponse.from_dict(raw)
        assert response.clauses == []

    def test_normalizer_preserves_schema_version(self):
        """Normalizer preserves explicit ``schema_version`` when present."""
        raw = _schema_valid_raw()
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        assert result.normalized["schema_version"] == "0.1.0"

    def test_normalizer_does_not_add_missing_keys(self):
        """Normalizer does not fabricate missing required keys."""
        # Input missing schema_version entirely
        raw: dict = {
            "source_id": "sample-001",
            "source_text": SAMPLE_TEXT,
            "clauses": [],
        }
        result = normalize_llm_fallback_json(raw)
        assert result.normalized is not None
        # Normalizer passes through — does NOT add schema_version
        assert "schema_version" not in result.normalized
        # from_dict() will default it to "0.1.0" — current parser behavior
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        assert response.schema_version == "0.1.0"

    def test_parser_defaulting_preserved(self):
        """Current parser defaulting behavior is preserved (documented)."""
        # Verify that from_dict() still defaults missing top-level keys
        raw = {
            "source_id": "sample-001",
            "source_text": SAMPLE_TEXT,
            "clauses": [
                {
                    "clause_id": "c1",
                    "source_id": "sample-001",
                    "source_text": SAMPLE_TEXT,
                    "clause_text": SAMPLE_TEXT,
                    "clause_span_start": 0,
                    "clause_span_end": len(SAMPLE_TEXT),
                    "modality": None,
                    "actor": None,
                    "action": None,
                    "condition": None,
                    "constraint": None,
                    "exception": None,
                    "confidence": 0.9,
                }
            ],
        }
        # Missing schema_version — defaults to "0.1.0"
        response = MultiClauseExtractionResponse.from_dict(raw)
        assert response.schema_version == "0.1.0"
        response.validate()

    def test_normalizer_result_is_importable(self):
        """The normalized dict can be imported into schema (integration)."""
        result = normalize_llm_fallback_json(_model_like_raw())
        response = MultiClauseExtractionResponse.from_dict(result.normalized)
        response.validate()
        assert len(response.clauses) == 1
        c = response.clauses[0]
        assert c.modality is not None
        assert c.actor is not None
        assert c.action is not None


# ===========================================================================
# 8.5 _parse_and_align_llm_json_response Tests
# ===========================================================================


class TestParseAndAlign:
    """Tests for the aligned parse function in llm_client.py."""

    def test_parse_model_like_succeeds(self):
        """Model-like JSON with normalizer produces valid response."""
        content = json.dumps(_model_like_raw())
        response = _parse_and_align_llm_json_response(content)
        assert isinstance(response, MultiClauseExtractionResponse)
        assert response.clauses[0].modality is not None

    def test_parse_schema_valid_passthrough(self):
        """Schema-valid JSON passes through normalizer unchanged."""
        content = json.dumps(_schema_valid_raw())
        response = _parse_and_align_llm_json_response(content)
        assert isinstance(response, MultiClauseExtractionResponse)
        response.validate()

    def test_parse_invalid_json_raises(self):
        """Invalid JSON raises LLMClientError."""
        with pytest.raises(LLMClientError, match="not valid JSON"):
            _parse_and_align_llm_json_response("not json {{{")

    def test_parse_non_dict_raises(self):
        """Non-dict JSON raises LLMClientError."""
        with pytest.raises(LLMClientError, match="JSON object"):
            _parse_and_align_llm_json_response("[1, 2, 3]")

    def test_parse_unmappable_raises(self):
        """Totally unmappable output raises LLMClientError."""
        content = json.dumps({"wrong_shape": True})
        # Normalizer removes unknown keys, leaving empty dict
        # from_dict() then rejects missing required keys
        with pytest.raises(LLMClientError):
            _parse_and_align_llm_json_response(content)

    def test_parse_markdown_wrapped(self):
        """Markdown-wrapped JSON is extracted and parsed."""
        content = "```json\n" + json.dumps(_model_like_raw()) + "\n```"
        response = _parse_and_align_llm_json_response(content)
        assert isinstance(response, MultiClauseExtractionResponse)

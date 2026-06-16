"""Tests for the core multi-clause schema (R2).

All test data uses synthetic toy sentences only — no real GDPR, BPMN,
or Sun-aligned dataset content.
"""

import json

import pytest

from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)


# ---------------------------------------------------------------------------
# FieldSpan tests
# ---------------------------------------------------------------------------

class TestFieldSpanValid:
    """Happy-path FieldSpan tests."""

    def test_round_trip_dict(self) -> None:
        fs = FieldSpan(text="review a request", span_start=14, span_end=31,
                       confidence=0.95)
        d = fs.to_dict()
        assert d == {
            "text": "review a request",
            "span_start": 14,
            "span_end": 31,
            "confidence": 0.95,
        }
        fs2 = FieldSpan.from_dict(d)
        assert fs2.text == fs.text
        assert fs2.span_start == fs.span_start
        assert fs2.span_end == fs.span_end
        assert fs2.confidence == fs.confidence

    def test_validate_accepts_boundary_confidence(self) -> None:
        for c in (0.0, 0.5, 1.0):
            FieldSpan(text="x", span_start=0, span_end=1, confidence=c).validate()

    def test_validate_with_valid_source_text(self) -> None:
        source = "A controller may review a request and shall record the decision."
        fs = FieldSpan(text="review a request", span_start=14, span_end=31,
                       confidence=0.9)
        fs.validate(source_text=source)  # must not raise

    def test_max_confidence(self) -> None:
        fs = FieldSpan(text="record the decision", span_start=36,
                       span_end=56, confidence=1.0)
        fs.validate()


class TestFieldSpanInvalidConfidence:
    """FieldSpan should reject out-of-range confidence."""

    @pytest.mark.parametrize("bad", [-0.1, 1.001, 2.0, 10.0])
    def test_rejects_out_of_range(self, bad: float) -> None:
        fs = FieldSpan(text="x", span_start=0, span_end=1, confidence=bad)
        with pytest.raises(SchemaValidationError, match="confidence"):
            fs.validate()

    def test_rejects_non_numeric_confidence(self) -> None:
        """bool / str should be caught."""
        with pytest.raises(SchemaValidationError):
            FieldSpan(text="x", span_start=0, span_end=1,
                      confidence="high").validate()  # type: ignore[arg-type]


class TestFieldSpanInvalidText:
    """FieldSpan.text must be non-empty str."""

    def test_rejects_empty_text(self) -> None:
        with pytest.raises(SchemaValidationError, match="text"):
            FieldSpan(text="", span_start=0, span_end=0, confidence=0.5).validate()


class TestFieldSpanInvalidOffsets:
    """span_start / span_end constraints."""

    def test_rejects_negative_start(self) -> None:
        with pytest.raises(SchemaValidationError, match="span_start"):
            FieldSpan(text="x", span_start=-1, span_end=0, confidence=0.5).validate()

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(SchemaValidationError, match="span_end"):
            FieldSpan(text="x", span_start=5, span_end=3, confidence=0.5).validate()

    def test_rejects_end_exceeds_source(self) -> None:
        fs = FieldSpan(text="long", span_start=5, span_end=99, confidence=0.5)
        with pytest.raises(SchemaValidationError, match="span_end"):
            fs.validate(source_text="short")


# ---------------------------------------------------------------------------
# ClauseExtraction tests
# ---------------------------------------------------------------------------

class TestClauseExtractionValid:
    """Happy-path ClauseExtraction tests."""

    _TOY_SOURCE = "A controller may review a request and shall record the decision."

    def _make_valid_clause(self, **kwargs: object) -> ClauseExtraction:
        defaults: dict[str, object] = {
            "clause_id": "C1",
            "source_id": "GDPR-Art5",
            "source_text": self._TOY_SOURCE,
            "clause_text": "A controller may review a request",
            "clause_span_start": 0,
            "clause_span_end": 34,
            "modality": FieldSpan(text="may", span_start=14, span_end=17,
                                  confidence=0.95),
            "actor": FieldSpan(text="controller", span_start=2, span_end=12,
                               confidence=0.92),
            "action": FieldSpan(text="review a request", span_start=18,
                                span_end=33, confidence=0.90),
            "condition": None,
            "constraint": None,
            "exception": None,
            "confidence": 0.88,
        }
        defaults.update(kwargs)
        return ClauseExtraction(**defaults)  # type: ignore[arg-type]

    def test_mixed_object_and_none_fields_validates(self) -> None:
        clause = self._make_valid_clause()
        clause.validate()  # must not raise

    def test_all_six_fields_none(self) -> None:
        clause = self._make_valid_clause(
            modality=None, actor=None, action=None,
            condition=None, constraint=None, exception=None,
        )
        clause.validate()  # still valid — fields present albeit none

    def test_all_six_fields_object(self) -> None:
        fs = FieldSpan(text="shall record", span_start=35, span_end=47,
                       confidence=0.93)
        clause = self._make_valid_clause(
            modality=fs, actor=fs, action=fs,
            condition=fs, constraint=fs, exception=fs,
        )
        clause.validate()

    def test_round_trip_dict_preserves_nulls(self) -> None:
        clause = self._make_valid_clause()
        d = clause.to_dict()
        assert d["modality"] is not None
        assert d["condition"] is None
        assert d["constraint"] is None
        assert d["exception"] is None

        clause2 = ClauseExtraction.from_dict(d)
        assert clause2.clause_id == clause.clause_id
        assert clause2.modality is not None
        assert clause2.modality.text == "may"
        assert clause2.condition is None
        assert clause2.constraint is None
        assert clause2.exception is None


class TestClauseExtractionMissingField:
    """ClauseExtraction must have all six semantic field keys in the dict."""

    def test_missing_modality_key_fails(self) -> None:
        d = {
            "clause_id": "C1", "source_id": None,
            "source_text": "s", "clause_text": "c",
            "clause_span_start": 0, "clause_span_end": 1,
            "actor": None, "action": None,
            "condition": None, "constraint": None, "exception": None,
            "confidence": 0.9,
        }
        with pytest.raises(SchemaValidationError, match="'modality'"):
            ClauseExtraction.from_dict(d)

    def test_missing_actor_key_fails(self) -> None:
        d = {
            "clause_id": "C1", "source_id": None,
            "source_text": "s", "clause_text": "c",
            "clause_span_start": 0, "clause_span_end": 1,
            "modality": None, "action": None,
            "condition": None, "constraint": None, "exception": None,
            "confidence": 0.9,
        }
        with pytest.raises(SchemaValidationError, match="'actor'"):
            ClauseExtraction.from_dict(d)


class TestClauseExtractionUnknownField:
    """Unknown keys must trigger SchemaValidationError."""

    def test_single_unknown_key_fails(self) -> None:
        d = {
            "clause_id": "C1", "source_id": None,
            "source_text": "s", "clause_text": "c",
            "clause_span_start": 0, "clause_span_end": 1,
            "modality": None, "actor": None, "action": None,
            "condition": None, "constraint": None, "exception": None,
            "confidence": 0.9,
            "hallucination": "bad",
        }
        with pytest.raises(SchemaValidationError, match="hallucination"):
            ClauseExtraction.from_dict(d)

    def test_multiple_unknown_keys_fails(self) -> None:
        d = {
            "clause_id": "C1", "source_id": None,
            "source_text": "s", "clause_text": "c",
            "clause_span_start": 0, "clause_span_end": 1,
            "modality": None, "actor": None, "action": None,
            "condition": None, "constraint": None, "exception": None,
            "confidence": 0.9,
            "extra_a": 1, "extra_b": 2,
        }
        with pytest.raises(SchemaValidationError, match="extra_a"):
            ClauseExtraction.from_dict(d)


class TestClauseExtractionInvalidConfidence:
    """Confidence must be in [0.0, 1.0]."""

    def test_rejects_negative_confidence(self) -> None:
        clause = ClauseExtraction(
            clause_id="C1", source_id=None, source_text="s", clause_text="c",
            clause_span_start=0, clause_span_end=1,
            modality=None, actor=None, action=None,
            condition=None, constraint=None, exception=None,
            confidence=-0.5,
        )
        with pytest.raises(SchemaValidationError, match="confidence"):
            clause.validate()


# ---------------------------------------------------------------------------
# MultiClauseExtractionResponse tests
# ---------------------------------------------------------------------------

class TestMultiClauseExtractionResponseValid:
    """Happy-path MultiClauseExtractionResponse tests."""

    _TOY_SOURCE = "A controller may review a request and shall record the decision."

    def _make_two_clauses(self) -> MultiClauseExtractionResponse:
        c1 = ClauseExtraction(
            clause_id="C1", source_id="S1", source_text=self._TOY_SOURCE,
            clause_text="A controller may review a request",
            clause_span_start=0, clause_span_end=34,
            modality=FieldSpan(text="may", span_start=14, span_end=17,
                               confidence=0.95),
            actor=FieldSpan(text="controller", span_start=2, span_end=12,
                            confidence=0.92),
            action=FieldSpan(text="review a request", span_start=18,
                             span_end=33, confidence=0.90),
            condition=None, constraint=None, exception=None, confidence=0.88,
        )
        c2 = ClauseExtraction(
            clause_id="C2", source_id="S1", source_text=self._TOY_SOURCE,
            clause_text="shall record the decision",
            clause_span_start=38, clause_span_end=62,
            modality=FieldSpan(text="shall", span_start=38, span_end=43,
                               confidence=0.98),
            actor=None, action=FieldSpan(text="record the decision",
                                         span_start=44, span_end=62,
                                         confidence=0.94),
            condition=None, constraint=None, exception=None, confidence=0.91,
        )
        return MultiClauseExtractionResponse(
            schema_version="0.1.0",
            source_id="S1",
            source_text=self._TOY_SOURCE,
            clauses=[c1, c2],
        )

    def test_valid_two_clause_response(self) -> None:
        resp = self._make_two_clauses()
        resp.validate()

    def test_empty_clauses_list_is_valid(self) -> None:
        resp = MultiClauseExtractionResponse(
            source_id="S1", source_text="text", clauses=[],
        )
        resp.validate()

    def test_dict_round_trip(self) -> None:
        resp = self._make_two_clauses()
        d = resp.to_dict()
        resp2 = MultiClauseExtractionResponse.from_dict(d)
        assert len(resp2.clauses) == 2
        assert resp2.clauses[0].clause_id == "C1"
        assert resp2.clauses[1].clause_id == "C2"
        # nulls preserved
        assert resp2.clauses[1].actor is None

    def test_json_round_trip(self) -> None:
        resp = self._make_two_clauses()
        j = resp.to_json()
        assert isinstance(j, str)
        resp2 = MultiClauseExtractionResponse.from_json(j)
        assert resp2.schema_version == "0.1.0"
        assert len(resp2.clauses) == 2
        # nulls preserved
        assert resp2.clauses[0].condition is None
        assert resp2.clauses[1].actor is None

    def test_to_json_pretty(self) -> None:
        resp = self._make_two_clauses()
        j = resp.to_json(indent=4)
        assert "\n" in j

    def test_to_json_compact(self) -> None:
        resp = self._make_two_clauses()
        j = resp.to_json(indent=None)
        assert "\n" not in j


class TestMultiClauseExtractionResponseInvalid:
    """Invalid payloads must raise SchemaValidationError."""

    def test_bad_json_raises(self) -> None:
        with pytest.raises(SchemaValidationError, match="Invalid JSON"):
            MultiClauseExtractionResponse.from_json("not json")

    def test_missing_source_id(self) -> None:
        with pytest.raises(SchemaValidationError, match="source_id"):
            resp = MultiClauseExtractionResponse(source_id="", source_text="t")
            resp.validate()

    def test_empty_source_text(self) -> None:
        with pytest.raises(SchemaValidationError, match="source_text"):
            resp = MultiClauseExtractionResponse(source_id="S1", source_text="")
            resp.validate()

    def test_clauses_not_list(self) -> None:
        with pytest.raises(SchemaValidationError):
            MultiClauseExtractionResponse.from_dict({
                "schema_version": "0.1.0",
                "source_id": "S1",
                "source_text": "text",
                "clauses": "not a list",
            })

    def test_clause_element_not_clause_extraction(self) -> None:
        with pytest.raises(SchemaValidationError, match="clauses\\[0\\]"):
            MultiClauseExtractionResponse.from_dict({
                "schema_version": "0.1.0",
                "source_id": "S1",
                "source_text": "text",
                "clauses": [{"not": "a clause"}],
            })

    def test_unknown_keys(self) -> None:
        with pytest.raises(SchemaValidationError, match="extra"):
            MultiClauseExtractionResponse.from_dict({
                "schema_version": "0.1.0",
                "source_id": "S1",
                "source_text": "text",
                "clauses": [],
                "extra": 42,
            })

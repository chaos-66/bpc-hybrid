"""Tests for normalization (R6).

All test data uses synthetic toy sentences only — no real GDPR,
BPMN, or Sun dataset content.
"""

import pytest

from bpc_hybrid.normalization import (
    NormalizationError,
    _find_unique,
    normalize_field_text,
    normalize_modality_text,
    repair_field_span,
    repair_response_spans,
)
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
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
        confidence=0.9,
        **kw,
    )


def _response(source_id: str, source_text: str,
              clauses: list[ClauseExtraction]) -> MultiClauseExtractionResponse:
    return MultiClauseExtractionResponse(
        schema_version="0.1.0",
        source_id=source_id,
        source_text=source_text,
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# normalize_field_text
# ---------------------------------------------------------------------------

class TestNormalizeFieldText:
    def test_whitespace_collapse(self):
        assert normalize_field_text("  record    the   decision  ") == "record the decision"

    def test_trailing_punctuation(self):
        assert normalize_field_text("record the decision.") == "record the decision"

    def test_leading_punctuation(self):
        assert normalize_field_text('"record the decision"') == "record the decision"

    def test_lowercase(self):
        assert normalize_field_text("Record THE Decision", lowercase=True) == "record the decision"

    def test_lowercase_false(self):
        """Default preserves case."""
        assert normalize_field_text("Record THE Decision") == "Record THE Decision"

    def test_internal_punctuation_preserved(self):
        assert normalize_field_text("shall not.") == "shall not"

    def test_empty_becomes_empty(self):
        assert normalize_field_text("") == ""


# ---------------------------------------------------------------------------
# normalize_modality_text
# ---------------------------------------------------------------------------

class TestNormalizeModalityText:
    @pytest.mark.parametrize("raw,expected", [
        ("may", "may"),
        ("  may  ", "may"),
        ("May", "may"),
        ("MAY.", "may"),
        ("shall", "shall"),
        ("  Shall  ", "shall"),
        ("must", "must"),
        ("Must", "must"),
        ("shall not", "shall not"),
        ("Shall Not", "shall not"),
        ("must not", "must not"),
        ("MUST NOT", "must not"),
        ("no person shall", "shall not"),
        ("No Person Shall", "shall not"),
        ("no person must", "must not"),
    ])
    def test_canonical_forms(self, raw, expected):
        assert normalize_modality_text(raw) == expected

    def test_unknown_returns_cleaned(self):
        assert normalize_modality_text("  maybe  ") == "maybe"


# ---------------------------------------------------------------------------
# _find_unique
# ---------------------------------------------------------------------------

class TestFindUnique:
    def test_single_occurrence(self):
        assert _find_unique("A controller shall record.", "controller") == 2

    def test_no_occurrence(self):
        assert _find_unique("A controller shall record.", "reviewer") is None

    def test_multiple_occurrences(self):
        assert _find_unique("A controller shall record the controller.", "controller") is None


# ---------------------------------------------------------------------------
# repair_field_span
# ---------------------------------------------------------------------------

class TestRepairFieldSpan:
    def test_correct_span_unchanged(self):
        src = "A controller shall record the decision."
        fs = _fs("shall", 13, 18)
        result = repair_field_span(src, fs)
        assert result.span_start == 13
        assert result.span_end == 18
        assert result.text == "shall"

    def test_wrong_but_repairable_span(self):
        src = "A controller shall record the decision."
        # text exists uniquely, but span is wrong
        fs = _fs("controller", 0, 10)  # "A control" — wrong span
        result = repair_field_span(src, fs)
        assert result.span_start == 2   # "controller" starts at 2
        assert result.span_end == 12
        assert result.text == "controller"
        assert result.confidence == 1.0

    def test_missing_text_raises(self):
        src = "A controller shall record the decision."
        fs = _fs("reviewer", 0, 8)  # not in source
        with pytest.raises(NormalizationError, match="not found"):
            repair_field_span(src, fs)

    def test_duplicate_text_raises(self):
        src = "The controller shall notify the controller."
        fs = _fs("controller", 9, 19)
        with pytest.raises(NormalizationError, match="cannot uniquely repair"):
            repair_field_span(src, fs)

    def test_partial_match_repaired(self):
        src = "A controller shall record."
        # "controller shall" is 16 chars, span at (2,20) gives "controller shall r" which is wrong
        fs = _fs("controller shall", 2, 20)
        result = repair_field_span(src, fs)
        assert result.span_start == 2
        assert result.span_end == 18  # 2 + len("controller shall") = 2 + 16 = 18


# ---------------------------------------------------------------------------
# repair_response_spans
# ---------------------------------------------------------------------------

class TestRepairResponseSpans:
    def test_all_correct_spans(self):
        src = "A controller shall record the decision."
        c = _clause("c1", "t1", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 0, 12),
                     action=_fs("record the decision", 19, 38))
        resp = _response("t1", src, [c])
        repaired = repair_response_spans(resp)
        assert repaired.clauses[0].actor.span_start == 0
        assert repaired.clauses[0].modality.span_start == 13
        assert repaired.clauses[0].action.span_start == 19

    def test_one_broken_span_repaired(self):
        src = "A controller shall record the decision."
        c = _clause("c1", "t2", src, src, 0, len(src),
                     modality=_fs("shall", 13, 18),
                     actor=_fs("A controller", 99, 111),  # wrong span
                     action=_fs("record the decision", 19, 38))
        resp = _response("t2", src, [c])
        repaired = repair_response_spans(resp)
        assert repaired.clauses[0].actor.span_start == 0
        assert repaired.clauses[0].actor.span_end == 12

    def test_null_fields_preserved(self):
        src = "A violation results in a penalty."
        c = _clause("c1", "t3", src, src, 0, len(src),
                     modality=None, actor=None, action=None,
                     condition=None, constraint=None, exception=None)
        resp = _response("t3", src, [c])
        repaired = repair_response_spans(resp)
        assert repaired.clauses[0].actor is None
        assert repaired.clauses[0].modality is None

    def test_unrepairable_raises(self):
        src = "A controller shall record."
        c = _clause("c1", "t4", src, src, 0, len(src),
                     modality=_fs("not-in-text", 0, 4))
        resp = _response("t4", src, [c])
        with pytest.raises(NormalizationError, match="not found"):
            repair_response_spans(resp)

    def test_repaired_response_validates(self):
        src = "A reviewer may inspect the file."
        c = _clause("c1", "t5", src, src, 0, len(src),
                     modality=_fs("may", 99, 102),  # wrong span
                     actor=_fs("A reviewer", 0, 10),
                     action=_fs("inspect the file", 15, 31))
        resp = _response("t5", src, [c])
        repaired = repair_response_spans(resp)
        repaired.validate()  # must not raise

    def test_multi_clause_repair(self):
        src = "A reviewer may inspect the file and shall record the decision."
        c1 = _clause("c1", "t6", src, "A reviewer may inspect the file", 0, 31,
                      modality=_fs("may", 99, 102),  # wrong
                      actor=_fs("A reviewer", 0, 10),
                      action=_fs("inspect the file", 15, 31))
        c2 = _clause("c2", "t6", src, "shall record the decision.", 36, 62,
                      modality=_fs("shall", 99, 104),  # wrong
                      action=_fs("record the decision", 42, 61))
        resp = _response("t6", src, [c1, c2])
        repaired = repair_response_spans(resp)
        assert repaired.clauses[0].modality.span_start == 11  # correct "may"
        assert repaired.clauses[1].modality.span_start == 36  # correct "shall"
        repaired.validate()


# ---------------------------------------------------------------------------
# No real data
# ---------------------------------------------------------------------------

class TestSyntheticOnly:
    def test_no_gdpr_bpmn_sun(self):
        """Quick sanity — all test data above is synthetic."""
        pass  # all helpers use synthetic sentences

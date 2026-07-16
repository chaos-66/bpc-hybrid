"""Tests for the rule-first extractor (R3).

All test data uses synthetic toy sentences only — no real GDPR, BPMN,
or Sun-aligned dataset content.
"""

import pytest

from bpc_hybrid.extractor import ExtractionError, RuleFirstExtractor, extract_rule_first
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _extract(text: str, source_id: str = "toy") -> MultiClauseExtractionResponse:
    return extract_rule_first(text, source_id=source_id)


def _only_clause(resp: MultiClauseExtractionResponse) -> ClauseExtraction:
    assert len(resp.clauses) == 1
    return resp.clauses[0]


def _assert_field(resp: MultiClauseExtractionResponse, field: str,
                  expected_text: str | None) -> None:
    clause = _only_clause(resp)
    fs = getattr(clause, field)
    if expected_text is None:
        assert fs is None, f"{field} expected None, got {fs}"
    else:
        assert fs is not None, f"{field} expected {expected_text!r}, got None"
        assert fs.text == expected_text, (
            f"{field}.text expected {expected_text!r}, got {fs.text!r}"
        )


def _span_in_source(fs: FieldSpan, source_text: str) -> bool:
    """Check that span is within source_text and matches the slice."""
    return (
        fs.span_start >= 0
        and fs.span_end <= len(source_text)
        and fs.span_start <= fs.span_end
        and source_text[fs.span_start:fs.span_end] == fs.text
    )


def _assert_all_spans_valid(resp: MultiClauseExtractionResponse) -> None:
    """Validate all spans against source_text and R2 schema."""
    resp.validate()
    for clause in resp.clauses:
        src = clause.source_text
        for field_name in ("modality", "actor", "action",
                           "condition", "constraint", "exception"):
            fs = getattr(clause, field_name)
            if fs is not None:
                assert _span_in_source(fs, src), (
                    f"{field_name} span mismatch: "
                    f"text={fs.text!r}, span=[{fs.span_start}:{fs.span_end}], "
                    f"slice={src[fs.span_start:fs.span_end]!r}"
                )


# ===================================================================
# Positive cases — modality markers
# ===================================================================

class TestShallObligation:
    """shall obligation, active voice."""

    def test_basic_shall(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src)
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "actor", "A controller")
        _assert_field(resp, "action", "record the decision")
        _assert_field(resp, "condition", None)
        _assert_field(resp, "constraint", None)
        _assert_field(resp, "exception", None)
        _assert_all_spans_valid(resp)


class TestMayPermission:
    """may permission, active voice."""

    def test_basic_may(self) -> None:
        src = "A reviewer may inspect the file."
        resp = _extract(src)
        _assert_field(resp, "modality", "may")
        _assert_field(resp, "actor", "A reviewer")
        _assert_field(resp, "action", "inspect the file")
        _assert_all_spans_valid(resp)


class TestMustObligation:
    """must obligation, active voice."""

    def test_basic_must(self) -> None:
        src = "A service provider must retain the log."
        resp = _extract(src)
        _assert_field(resp, "modality", "must")
        _assert_field(resp, "actor", "A service provider")
        _assert_field(resp, "action", "retain the log")
        _assert_all_spans_valid(resp)


class TestShallNotProhibition:
    """shall not prohibition."""

    def test_shall_not(self) -> None:
        src = "A user shall not disclose the token."
        resp = _extract(src)
        _assert_field(resp, "modality", "shall not")
        _assert_field(resp, "actor", "A user")
        _assert_field(resp, "action", "disclose the token")
        _assert_all_spans_valid(resp)


class TestMustNotProhibition:
    """must not prohibition."""

    def test_must_not(self) -> None:
        src = "A user must not delete the archive."
        resp = _extract(src)
        _assert_field(resp, "modality", "must not")
        _assert_field(resp, "actor", "A user")
        _assert_field(resp, "action", "delete the archive")
        _assert_all_spans_valid(resp)


class TestNoPersonShall:
    """no person shall prohibition."""

    def test_no_person_shall(self) -> None:
        src = "No person shall alter the record."
        resp = _extract(src)
        _assert_field(resp, "modality", "No person shall")
        _assert_field(resp, "actor", "No person")
        _assert_field(resp, "action", "alter the record")
        _assert_all_spans_valid(resp)

    def test_no_person_shall_with_article(self) -> None:
        src = "No person shall disclose the information."
        resp = _extract(src)
        _assert_field(resp, "modality", "No person shall")
        _assert_field(resp, "actor", "No person")
        _assert_field(resp, "action", "disclose the information")
        _assert_all_spans_valid(resp)


# ===================================================================
# Condition — initial unless
# ===================================================================

class TestInitialUnless:
    """initial unless → condition."""

    def test_initial_unless_condition(self) -> None:
        src = "Unless approved, a controller shall record the decision."
        resp = _extract(src)
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "actor", "a controller")
        _assert_field(resp, "action", "record the decision")
        _assert_field(resp, "condition", "Unless approved")
        _assert_field(resp, "exception", None)
        _assert_all_spans_valid(resp)

    def test_initial_unless_no_comma(self) -> None:
        src = "Unless authorized a controller may proceed."
        resp = _extract(src)
        _assert_field(resp, "modality", "may")
        _assert_field(resp, "condition", "Unless authorized")
        _assert_all_spans_valid(resp)


# ===================================================================
# Exception — mid-sentence unless
# ===================================================================

class TestMidUnless:
    """mid-sentence unless → exception."""

    def test_mid_unless_exception(self) -> None:
        src = "A controller shall record the decision unless an exception applies."
        resp = _extract(src)
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "actor", "A controller")
        _assert_field(resp, "action", "record the decision")
        _assert_field(resp, "condition", None)
        _assert_field(resp, "exception", "unless an exception applies")
        _assert_all_spans_valid(resp)


# ===================================================================
# By-agent passive actor
# ===================================================================

class TestPassiveActor:
    """by-agent passive actor extraction."""

    def test_by_agent_passive(self) -> None:
        src = "The request shall be reviewed by the controller."
        resp = _extract(src)
        # Actor should come from "by the controller"
        clause = _only_clause(resp)
        assert clause.actor is not None, "Expected by-agent passive actor"
        assert clause.actor.text == "the controller", (
            f"Expected 'the controller', got {clause.actor.text!r}"
        )
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "action", "be reviewed")
        _assert_all_spans_valid(resp)

    def test_passive_must(self) -> None:
        src = "The form must be signed by the officer."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.actor is not None
        assert clause.actor.text == "the officer"
        _assert_field(resp, "modality", "must")
        _assert_field(resp, "action", "be signed")
        _assert_all_spans_valid(resp)


# ===================================================================
# Recipient / affected party NOT actor
# ===================================================================

class TestRecipientNotActor:
    """recipient / affected party should NOT be treated as actor."""

    def test_recipient_not_actor(self) -> None:
        src = "A notice shall be sent to the recipient."
        resp = _extract(src)
        clause = _only_clause(resp)
        # Actor should be None (no explicit by-agent, recipient is not actor)
        assert clause.actor is None, (
            f"Expected actor=None (recipient not actor), got {clause.actor}"
        )
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "action", "be sent")
        _assert_all_spans_valid(resp)


# ===================================================================
# Constraint extraction
# ===================================================================

class TestConstraint:
    """constraint markers."""

    def test_within_constraint(self) -> None:
        src = "A controller shall respond within 30 days."
        resp = _extract(src)
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "actor", "A controller")
        _assert_field(resp, "action", "respond")
        _assert_field(resp, "constraint", "within 30 days")
        _assert_all_spans_valid(resp)

    def test_only_if_constraint(self) -> None:
        src = "A controller may disclose the record only if authorized."
        resp = _extract(src)
        _assert_field(resp, "modality", "may")
        _assert_field(resp, "actor", "A controller")
        _assert_field(resp, "action", "disclose the record")
        _assert_field(resp, "constraint", "only if authorized")
        _assert_all_spans_valid(resp)

    def test_provided_that_constraint(self) -> None:
        src = "A controller shall process data provided that consent is given."
        resp = _extract(src)
        _assert_field(resp, "modality", "shall")
        _assert_field(resp, "actor", "A controller")
        _assert_field(resp, "action", "process data")
        _assert_field(resp, "constraint", "provided that consent is given")
        _assert_all_spans_valid(resp)


# ===================================================================
# Negative cases — null semantic fields
# ===================================================================

class TestNegativeCases:
    """Definition / warranty / legal consequence / descriptive → null fields."""

    def test_definition_quoted(self) -> None:
        src = '"Controller" means an entity that determines purposes.'
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is None
        assert clause.actor is None
        assert clause.action is None
        assert clause.condition is None
        assert clause.constraint is None
        assert clause.exception is None
        _assert_all_spans_valid(resp)

    def test_definition_is(self) -> None:
        src = "A record is information stored by a system."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is None
        assert clause.actor is None
        assert clause.action is None
        _assert_all_spans_valid(resp)

    def test_warranty(self) -> None:
        src = "The provider warrants that the service is available."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is None
        assert clause.actor is None
        assert clause.action is None
        _assert_all_spans_valid(resp)

    def test_legal_consequence(self) -> None:
        src = "A violation results in a penalty."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is None
        assert clause.actor is None
        assert clause.action is None
        _assert_all_spans_valid(resp)

    def test_descriptive(self) -> None:
        src = "The system stores a record."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is None
        assert clause.actor is None
        assert clause.action is None
        _assert_all_spans_valid(resp)

    def test_simple_present(self) -> None:
        src = "An operator processes information daily."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is None
        _assert_all_spans_valid(resp)


# ===================================================================
# Output format & schema validation
# ===================================================================

class TestOutputFormat:
    """Output must be MultiClauseExtractionResponse and pass R2 validation."""

    def test_output_type(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src)
        assert isinstance(resp, MultiClauseExtractionResponse)
        assert isinstance(resp.clauses, list)
        assert len(resp.clauses) == 1
        assert isinstance(resp.clauses[0], ClauseExtraction)

    def test_output_validates(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src)
        resp.validate()  # must not raise

    def test_null_response_validates(self) -> None:
        src = "The system stores a record."
        resp = _extract(src)
        resp.validate()

    def test_json_round_trip(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src)
        j = resp.to_json()
        resp2 = MultiClauseExtractionResponse.from_json(j)
        _assert_field(resp2, "modality", "shall")
        _assert_field(resp2, "actor", "A controller")
        _assert_field(resp2, "action", "record the decision")

    def test_dict_round_trip(self) -> None:
        src = "A reviewer may inspect the file."
        resp = _extract(src)
        d = resp.to_dict()
        resp2 = MultiClauseExtractionResponse.from_dict(d)
        assert resp2.clauses[0].modality is not None
        assert resp2.clauses[0].modality.text == "may"


# ===================================================================
# Span integrity
# ===================================================================

class TestSpanIntegrity:
    """All spans must be within source_text and match the slice."""

    def test_all_spans_for_shall(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src)
        clause = _only_clause(resp)
        for field_name in ("modality", "actor", "action"):
            fs = getattr(clause, field_name)
            assert fs is not None, f"{field_name} should not be None"
            assert src[fs.span_start:fs.span_end] == fs.text, (
                f"{field_name} span mismatch"
            )

    def test_all_spans_for_no_person(self) -> None:
        src = "No person shall alter the record."
        resp = _extract(src)
        clause = _only_clause(resp)
        assert clause.modality is not None
        assert clause.actor is not None
        assert clause.action is not None
        assert src[clause.modality.span_start:clause.modality.span_end] == clause.modality.text
        assert src[clause.actor.span_start:clause.actor.span_end] == clause.actor.text
        assert src[clause.action.span_start:clause.action.span_end] == clause.action.text

    def test_confidence_in_range(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src)
        clause = _only_clause(resp)
        fs = clause.modality
        assert fs is not None
        assert 0.0 <= fs.confidence <= 1.0


# ===================================================================
# Edge cases
# ===================================================================

class TestEdgeCases:
    """Edge-case behaviour."""

    def test_may_not_is_not_shall_not(self) -> None:
        """'may not' should be treated as 'may' + negation, not 'shall not'."""
        src = "A user may not access restricted data."
        resp = _extract(src)
        _assert_field(resp, "modality", "may")
        _assert_all_spans_valid(resp)

    def test_no_spurious_matches(self) -> None:
        """'shall' inside a longer word should not match."""
        src = "The shallow water shall not be crossed."
        resp = _extract(src)
        # "shallow" contains "shall" but word boundary should prevent match
        _assert_field(resp, "modality", "shall not")
        _assert_all_spans_valid(resp)

    def test_source_id_preserved(self) -> None:
        src = "A controller shall record the decision."
        resp = _extract(src, source_id="GDPR-Art5-toy")
        assert resp.source_id == "GDPR-Art5-toy"
        assert resp.clauses[0].source_id == "GDPR-Art5-toy"


# ===================================================================
# Convenience function
# ===================================================================

class TestConvenienceFunction:
    """The module-level extract_rule_first should work."""

    def test_convenience(self) -> None:
        resp = extract_rule_first("A controller shall act.", source_id="X")
        assert resp.source_id == "X"
        _assert_field(resp, "modality", "shall")
        resp.validate()

"""Tests for the evaluator (R5).

All test data uses synthetic toy sentences only — no real GDPR,
BPMN, or Sun dataset content.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from bpc_hybrid.evaluator import (
    EvaluationError,
    EvaluationReport,
    FieldMetrics,
    _normalize,
    _SEMANTIC_FIELDS,
    evaluate_responses,
    load_gold_responses,
    load_jsonl,
    load_predicted_responses,
)
from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT = Path(__file__).resolve().parent.parent
_PYTHON = _PROJECT / ".venv" / "Scripts" / "python.exe"
_LEGAL_JSONL = _PROJECT / "data" / "prototype" / "legal_sentences.jsonl"
_GOLD_JSONL = _PROJECT / "data" / "prototype" / "gold_multiclause.jsonl"
_RUN_BASELINE = _PROJECT / "scripts" / "run_rule_baseline.py"
_EVALUATE_SCRIPT = _PROJECT / "scripts" / "evaluate_multi_clause.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_span(text: str, start: int, end: int,
               confidence: float = 1.0) -> FieldSpan:
    return FieldSpan(text=text, span_start=start, span_end=end, confidence=confidence)


def _make_clause(
    clause_id: str,
    source_id: str,
    source_text: str,
    clause_text: str,
    clause_span_start: int,
    clause_span_end: int,
    modality: FieldSpan | None = None,
    actor: FieldSpan | None = None,
    action: FieldSpan | None = None,
    condition: FieldSpan | None = None,
    constraint: FieldSpan | None = None,
    exception: FieldSpan | None = None,
    confidence: float = 0.9,
) -> ClauseExtraction:
    return ClauseExtraction(
        clause_id=clause_id,
        source_id=source_id,
        source_text=source_text,
        clause_text=clause_text,
        clause_span_start=clause_span_start,
        clause_span_end=clause_span_end,
        modality=modality,
        actor=actor,
        action=action,
        condition=condition,
        constraint=constraint,
        exception=exception,
        confidence=confidence,
    )


def _make_response(
    source_id: str,
    source_text: str,
    clauses: list[ClauseExtraction],
) -> MultiClauseExtractionResponse:
    return MultiClauseExtractionResponse(
        schema_version="0.1.0",
        source_id=source_id,
        source_text=source_text,
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# FieldMetrics
# ---------------------------------------------------------------------------

class TestFieldMetrics:
    def test_perfect(self):
        fm = FieldMetrics(field="modality", tp=5, fp=0, fn=0)
        assert fm.precision == 1.0
        assert fm.recall == 1.0
        assert fm.f1 == 1.0

    def test_zero_tp(self):
        fm = FieldMetrics(field="action", tp=0, fp=3, fn=3)
        assert fm.precision == 0.0
        assert fm.recall == 0.0
        assert fm.f1 == 0.0

    def test_mixed(self):
        fm = FieldMetrics(field="actor", tp=7, fp=2, fn=3)
        assert fm.precision == pytest.approx(7 / 9)
        assert fm.recall == pytest.approx(7 / 10)

    def test_to_dict(self):
        fm = FieldMetrics(field="exception", tp=1, fp=2, fn=3)
        d = fm.to_dict()
        assert d["field"] == "exception"
        assert d["tp"] == 1
        assert d["fp"] == 2
        assert d["fn"] == 3

    def test_no_denominator_zero_division(self):
        fm = FieldMetrics(field="constraint", tp=0, fp=0, fn=0)
        assert fm.precision == 0.0
        assert fm.recall == 0.0
        assert fm.f1 == 0.0


# ---------------------------------------------------------------------------
# EvaluationReport
# ---------------------------------------------------------------------------

class TestEvaluationReport:
    def test_defaults(self):
        r = EvaluationReport()
        assert r.dataset_type == "synthetic_prototype"
        assert r.is_formal_benchmark is False
        assert r.compares_against_sun is False

    def test_to_dict(self):
        r = EvaluationReport()
        d = r.to_dict()
        assert d["dataset_type"] == "synthetic_prototype"
        assert d["is_formal_benchmark"] is False
        assert d["compares_against_sun"] is False
        assert "clause_precision" in d
        assert "field_micro_f1" in d
        assert "per_field" in d


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_lowercase(self):
        assert _normalize("Record THE Decision") == "record the decision"

    def test_punctuation_removed(self):
        assert _normalize("record the decision.") == "record the decision"

    def test_whitespace_collapse(self):
        assert _normalize("  record    the   decision  ") == "record the decision"


# ---------------------------------------------------------------------------
# load_jsonl
# ---------------------------------------------------------------------------

class TestLoadJsonl:
    def test_load_sentences(self):
        records = load_jsonl(_LEGAL_JSONL)
        assert len(records) >= 10
        assert all("id" in r and "text" in r for r in records)

    def test_load_gold(self):
        records = load_jsonl(_GOLD_JSONL)
        assert len(records) >= 10
        assert all("schema_version" in r for r in records)


# ---------------------------------------------------------------------------
# Gold validation
# ---------------------------------------------------------------------------

class TestGoldValidation:
    def test_all_gold_validate(self):
        gold = load_gold_responses(_GOLD_JSONL)
        assert len(gold) >= 10
        for g in gold:
            g.validate()
        # All passed — no exception

    def test_gold_ids_match_sentences(self):
        gold = load_gold_responses(_GOLD_JSONL)
        sentences = {r["id"] for r in load_jsonl(_LEGAL_JSONL)}
        gold_ids = {g.source_id for g in gold}
        assert gold_ids == sentences, f"Missing: {sentences - gold_ids}, Extra: {gold_ids - sentences}"


# ---------------------------------------------------------------------------
# evaluate_responses — perfect prediction
# ---------------------------------------------------------------------------

class TestPerfectPrediction:
    def test_f1_is_one(self):
        src = "The committee shall approve the request."
        action = _make_span("approve the request", 20, 39, 1.0)
        c = _make_clause("c1", "t1", src, src, 0, len(src),
                         modality=_make_span("shall", 14, 19, 1.0),
                         actor=_make_span("The committee", 0, 13, 0.95),
                         action=action)
        gold = [_make_response("t1", src, [c])]
        pred = [_make_response("t1", src, [c])]
        report = evaluate_responses(gold, pred)
        assert report.clause_precision == 1.0
        assert report.clause_recall == 1.0
        assert report.clause_f1 == 1.0
        assert report.field_micro_precision == 1.0
        assert report.field_micro_recall == 1.0
        assert report.field_micro_f1 == 1.0

    def test_single_field_f1_one(self):
        src = "X shall Y."
        c = _make_clause("c1", "t2", src, src, 0, len(src),
                         modality=_make_span("shall", 2, 7, 1.0))
        gold = [_make_response("t2", src, [c])]
        pred = [_make_response("t2", src, [c])]
        report = evaluate_responses(gold, pred)
        assert report.per_field["modality"].f1 == 1.0


# ---------------------------------------------------------------------------
# evaluate_responses — field errors
# ---------------------------------------------------------------------------

class TestFieldErrors:
    def test_missing_field_creates_fn(self):
        """Gold has action, prediction does not → FN."""
        src = "X shall Y."
        gold_c = _make_clause("c1", "t3", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              action=_make_span("Y", 8, 9, 1.0))
        pred_c = _make_clause("c1", "t3", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              action=None)
        gold = [_make_response("t3", src, [gold_c])]
        pred = [_make_response("t3", src, [pred_c])]
        report = evaluate_responses(gold, pred)
        assert report.per_field["action"].fn == 1
        assert report.per_field["action"].fp == 0
        assert report.per_field["action"].tp == 0

    def test_extra_field_creates_fp(self):
        """Gold has no action, prediction has action → FP."""
        src = "X shall Y."
        gold_c = _make_clause("c1", "t4", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              action=None)
        pred_c = _make_clause("c1", "t4", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              action=_make_span("Y", 8, 9, 1.0))
        gold = [_make_response("t4", src, [gold_c])]
        pred = [_make_response("t4", src, [pred_c])]
        report = evaluate_responses(gold, pred)
        assert report.per_field["action"].fp == 1
        assert report.per_field["action"].fn == 0
        assert report.per_field["action"].tp == 0

    def test_wrong_text_creates_fp_and_fn(self):
        """Gold action ≠ predicted action → FP + FN."""
        src = "X shall inspect the file."
        gold_c = _make_clause("c1", "t5", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              action=_make_span("inspect the file", 8, 24, 1.0))
        pred_c = _make_clause("c1", "t5", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              action=_make_span("review the file", 8, 24, 1.0))
        gold = [_make_response("t5", src, [gold_c])]
        pred = [_make_response("t5", src, [pred_c])]
        report = evaluate_responses(gold, pred)
        assert report.per_field["action"].fp == 1
        assert report.per_field["action"].fn == 1
        assert report.per_field["action"].tp == 0

    def test_both_null_not_counted(self):
        """Both gold and pred have null for a field → not counted."""
        src = "X shall Y."
        gold_c = _make_clause("c1", "t6", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0))
        pred_c = _make_clause("c1", "t6", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0))
        gold = [_make_response("t6", src, [gold_c])]
        pred = [_make_response("t6", src, [pred_c])]
        report = evaluate_responses(gold, pred)
        # Both null for action → TN, not counted
        assert report.per_field["action"].tp == 0
        assert report.per_field["action"].fp == 0
        assert report.per_field["action"].fn == 0


# ---------------------------------------------------------------------------
# Clause count mismatch
# ---------------------------------------------------------------------------

class TestClauseCountMismatch:
    def test_pred_has_more_clauses(self):
        src = "A may inspect the file and shall record the decision."
        gold_c1 = _make_clause("c1", "t7", src, "A may inspect the file", 0, 24,
                               modality=_make_span("may", 2, 5, 1.0),
                               action=_make_span("inspect the file", 6, 24, 1.0))
        pred_c1 = _make_clause("c1", "t7", src, "A may inspect the file", 0, 24,
                               modality=_make_span("may", 2, 5, 1.0),
                               action=_make_span("inspect the file", 6, 24, 1.0))
        pred_c2 = _make_clause("c2", "t7", src, "shall record", 29, 42,
                               modality=_make_span("shall", 29, 34, 1.0))
        gold = [_make_response("t7", src, [gold_c1])]
        pred = [_make_response("t7", src, [pred_c1, pred_c2])]
        report = evaluate_responses(gold, pred)
        assert report.total_gold_clauses == 1
        assert report.total_predicted_clauses == 2
        assert report.matched_clauses == 1
        assert report.clause_precision == 0.5
        assert report.clause_recall == 1.0

    def test_pred_has_fewer_clauses(self):
        src = "A may inspect and shall record."
        gold_c1 = _make_clause("c1", "t8", src, "A may inspect", 0, 13,
                               modality=_make_span("may", 2, 5, 1.0))
        gold_c2 = _make_clause("c2", "t8", src, "shall record", 18, 31,
                               modality=_make_span("shall", 18, 23, 1.0))
        pred_c1 = _make_clause("c1", "t8", src, "A may inspect", 0, 13,
                               modality=_make_span("may", 2, 5, 1.0))
        gold = [_make_response("t8", src, [gold_c1, gold_c2])]
        pred = [_make_response("t8", src, [pred_c1])]
        report = evaluate_responses(gold, pred)
        assert report.total_gold_clauses == 2
        assert report.total_predicted_clauses == 1
        assert report.clause_precision == 1.0
        assert report.clause_recall == 0.5


# ---------------------------------------------------------------------------
# Per-field and micro metrics
# ---------------------------------------------------------------------------

class TestPerFieldAndMicro:
    def test_all_six_fields_present(self):
        report = EvaluationReport()
        report.per_field = {
            f: FieldMetrics(field=f) for f in _SEMANTIC_FIELDS
        }
        d = report.to_dict()
        for f in _SEMANTIC_FIELDS:
            assert f in d["per_field"], f"Missing field {f}"

    def test_micro_sum(self):
        """Micro metrics are sums across all fields."""
        src = "X shall Y."
        gold_c = _make_clause("c1", "t9", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              actor=_make_span("X", 0, 1, 1.0),
                              action=_make_span("Y", 8, 9, 1.0))
        pred_c = _make_clause("c1", "t9", src, src, 0, len(src),
                              modality=_make_span("shall", 2, 7, 1.0),
                              actor=_make_span("X", 0, 1, 1.0),
                              action=_make_span("Y", 8, 9, 1.0))
        gold = [_make_response("t9", src, [gold_c])]
        pred = [_make_response("t9", src, [pred_c])]
        report = evaluate_responses(gold, pred)
        assert report.field_micro_f1 == 1.0


# ---------------------------------------------------------------------------
# Duplicate source_id
# ---------------------------------------------------------------------------

class TestDuplicateSourceId:
    def test_duplicate_gold_raises(self):
        src = "X shall Y."
        c = _make_clause("c1", "dup", src, src, 0, len(src),
                         modality=_make_span("shall", 2, 7, 1.0))
        gold = [
            _make_response("dup", src, [c]),
            _make_response("dup", src, [c]),
        ]
        pred = [_make_response("dup", src, [c])]
        with pytest.raises(EvaluationError, match="Duplicate"):
            evaluate_responses(gold, pred)


# ---------------------------------------------------------------------------
# run_rule_baseline.py
# ---------------------------------------------------------------------------

class TestRunRuleBaseline:
    def test_script_runs(self):
        result = subprocess.run(
            [str(_PYTHON), str(_RUN_BASELINE), "--input", str(_LEGAL_JSONL)],
            capture_output=True, text=True, cwd=str(_PROJECT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
        assert len(lines) == 14  # 14 sentences
        for line in lines:
            rec = json.loads(line)
            assert "schema_version" in rec
            assert "clauses" in rec


# ---------------------------------------------------------------------------
# evaluate_multi_clause.py
# ---------------------------------------------------------------------------

class TestEvaluateMultiClause:
    def test_script_runs_and_outputs_valid_json(self):
        result = subprocess.run(
            [
                str(_PYTHON), str(_EVALUATE_SCRIPT),
                "--gold", str(_GOLD_JSONL),
                "--input", str(_LEGAL_JSONL),
            ],
            capture_output=True, text=True, cwd=str(_PROJECT),
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        report = json.loads(result.stdout)
        assert report["dataset_type"] == "synthetic_prototype"
        assert report["is_formal_benchmark"] is False
        assert report["compares_against_sun"] is False
        assert "clause_precision" in report
        assert "clause_recall" in report
        assert "clause_f1" in report
        assert "field_micro_precision" in report
        assert "field_micro_recall" in report
        assert "field_micro_f1" in report
        assert "per_field" in report
        for f in _SEMANTIC_FIELDS:
            assert f in report["per_field"], f"Missing per_field.{f}"

    def test_perfect_on_gold(self):
        """When predicted = gold, all scores should be 1.0."""
        result = subprocess.run(
            [
                str(_PYTHON), str(_EVALUATE_SCRIPT),
                "--gold", str(_GOLD_JSONL),
                "--pred", str(_GOLD_JSONL),
            ],
            capture_output=True, text=True, cwd=str(_PROJECT),
        )
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["clause_f1"] == 1.0
        assert report["field_micro_f1"] == 1.0


# ---------------------------------------------------------------------------
# No real data in tests
# ---------------------------------------------------------------------------

class TestSyntheticOnly:
    def test_all_sentences_are_synthetic(self):
        records = load_jsonl(_LEGAL_JSONL)
        for r in records:
            assert "GDPR" not in r["text"].upper(), f"Real GDPR text: {r['text']}"
            assert "REGULATION" not in r["text"].upper()
            assert "ARTICLE" not in r["text"].upper()
            assert "EU" not in r["text"]

    def test_all_gold_ids_are_synthetic(self):
        gold = load_gold_responses(_GOLD_JSONL)
        for g in gold:
            for c in g.clauses:
                src = c.source_text
                assert "GDPR" not in src.upper()
                assert "ARTICLE" not in src.upper()

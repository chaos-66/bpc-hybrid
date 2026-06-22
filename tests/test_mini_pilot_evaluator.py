"""
R13.4.1 Tests for local mini-pilot evaluator.

These tests:
  - Do NOT call any real API.
  - Do NOT read .env.
  - Do NOT access the network.
  - Do NOT use raw PDF/HTML.
"""
import json
import sys
from pathlib import Path

import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bpc_hybrid.mini_pilot_evaluator import (  # noqa: E402
    _normalize_text,
    _token_overlap_ratio,
    evaluate_predictions,
    load_jsonl,
    score_modality,
    score_prediction,
    score_text_field,
    validate_prediction_record,
    write_json,
    write_jsonl,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gold_records():
    return [
        {"sample_id": "r13_3_candidate_001", "modality": "obligation",
         "actor": "entity processing personal data",
         "action": "process personal data",
         "condition": None,
         "constraint": "Personal data must be processed lawfully, fairly, and in a transparent manner in relation to the data subject.",
         "exception": None},
        {"sample_id": "r13_3_candidate_002", "modality": "obligation",
         "actor": "entity collecting or further processing personal data",
         "action": "collect and further process personal data",
         "condition": None,
         "constraint": "Personal data must be collected for specified, explicit, and legitimate purposes, and must not be further processed in a manner incompatible with those purposes.",
         "exception": None},
    ]


@pytest.fixture
def mock_predictions():
    return [
        {"sample_id": "r13_3_candidate_001", "source_id": "gdpr_eurlex",
         "predicted": {"modality": "obligation",
                        "actor": "entity processing personal data",
                        "action": "process personal data",
                        "condition": None,
                        "constraint": "Personal data must be processed lawfully, fairly, and transparently.",
                        "exception": None},
         "runtime": {"provider": "mock", "model": "mock", "real_api_call_performed": False,
                      "raw_response_saved": False, "attempt_count": 1, "duration_ms": 0,
                      "error_category": None},
         "schema_valid": True},
        {"sample_id": "r13_3_candidate_002", "source_id": "gdpr_eurlex",
         "predicted": {"modality": "obligation",
                        "actor": "data controller",
                        "action": "collect personal data for specified purposes",
                        "condition": None,
                        "constraint": "Personal data must be collected for specified, explicit, and legitimate purposes.",
                        "exception": None},
         "runtime": {"provider": "mock", "model": "mock", "real_api_call_performed": False,
                      "raw_response_saved": False, "attempt_count": 1, "duration_ms": 0,
                      "error_category": None},
         "schema_valid": True},
    ]


# ---------------------------------------------------------------------------
# 1. load_jsonl
# ---------------------------------------------------------------------------

def test_load_jsonl_loads_8_records():
    """load_jsonl should load exactly 8 records from the mock predictions file."""
    path = Path(__file__).resolve().parent.parent / "data" / "formal" / "predictions" / "r13_4_1_mock_predictions.jsonl"
    records = load_jsonl(str(path))
    assert len(records) == 8
    for r in records:
        assert "sample_id" in r


# ---------------------------------------------------------------------------
# 2. score_modality
# ---------------------------------------------------------------------------

def test_modality_exact():
    assert score_modality("obligation", "obligation") == "exact"


def test_modality_wrong():
    assert score_modality("prohibition", "obligation") == "wrong"


def test_modality_missing():
    assert score_modality(None, "obligation") == "missing"
    assert score_modality("", "obligation") == "missing"


# ---------------------------------------------------------------------------
# 3. score_text_field (null/null, null/nonnull, etc.)
# ---------------------------------------------------------------------------

def test_text_not_applicable():
    """Both gold and pred null => not_applicable."""
    assert score_text_field(None, None) == "not_applicable"
    assert score_text_field("", "") == "not_applicable"
    assert score_text_field(None, None) == "not_applicable"


def test_text_null_gold_pred_nonempty():
    """Gold null, pred non-empty => wrong (hallucination)."""
    assert score_text_field("some value", None) == "wrong"


def test_text_nonnull_gold_pred_empty():
    """Gold non-null, pred empty => missing."""
    assert score_text_field(None, "must comply") == "missing"
    assert score_text_field("", "must comply") == "missing"


def test_text_exact_match():
    assert score_text_field("data subject", "data subject") == "exact"


def test_text_exact_match_case_insensitive():
    assert score_text_field("DATA SUBJECT", "data subject") == "exact"


def test_text_exact_match_punctuation():
    assert score_text_field("data subject.", "data subject") == "exact"


def test_text_partial_containment():
    """Pred contained in gold => partial."""
    assert score_text_field("must be processed", "personal data must be processed lawfully") == "partial"


def test_text_partial_token_overlap():
    """Token overlap >= 0.5 => partial."""
    # "collect personal data specified" vs "collect and process personal data"
    # tokens: {collect, personal, data, specified} vs {collect, and, process, personal, data}
    # intersection: {collect, personal, data} = 3, union: 6 -> 3/6 = 0.5
    assert score_text_field("collect personal data specified", "collect and process personal data") == "partial"


def test_text_wrong():
    """Token overlap < 0.5 => wrong."""
    assert score_text_field("banana apple", "orange grape") == "wrong"


# ---------------------------------------------------------------------------
# 4. validate_prediction_record
# ---------------------------------------------------------------------------

def test_schema_valid_complete():
    rec = {"sample_id": "x", "predicted": {"modality": "o", "actor": "a", "action": "ac",
             "condition": None, "constraint": "c", "exception": None},
           "runtime": {}, "schema_valid": True}
    assert validate_prediction_record(rec) is True


def test_schema_invalid_missing_sample_id():
    rec = {"predicted": {"modality": "o", "actor": "a", "action": "ac",
             "condition": None, "constraint": "c", "exception": None},
           "runtime": {}, "schema_valid": True}
    assert validate_prediction_record(rec) is False


def test_schema_invalid_missing_predicted_field():
    rec = {"sample_id": "x",
           "predicted": {"modality": "o", "actor": "a",
                          "condition": None, "constraint": "c", "exception": None},
           "runtime": {}, "schema_valid": True}
    assert validate_prediction_record(rec) is False


def test_schema_invalid_predicted_not_dict():
    rec = {"sample_id": "x", "predicted": "not-a-dict",
           "runtime": {}, "schema_valid": True}
    assert validate_prediction_record(rec) is False


# ---------------------------------------------------------------------------
# 5. score_prediction
# ---------------------------------------------------------------------------

def test_score_prediction_returns_all_fields(gold_records, mock_predictions):
    candidate = {}
    detail = score_prediction(candidate, gold_records[0], mock_predictions[0])
    assert detail["sample_id"] == "r13_3_candidate_001"
    assert "field_scores" in detail
    assert "failure_categories" in detail
    assert detail["schema_valid"] is True
    for dim in ["modality", "actor", "action", "condition", "constraint", "exception"]:
        assert dim in detail["field_scores"]


def test_score_prediction_schema_invalid_when_self_declared():
    """When prediction has schema_valid=false, it should be reflected."""
    gold = {"sample_id": "001", "modality": "obligation", "actor": "a", "action": "ac",
            "condition": None, "constraint": "c", "exception": None}
    pred = {"sample_id": "001", "source_id": "s",
            "predicted": {"modality": "obligation", "actor": "a", "action": "ac",
                          "condition": None, "constraint": "c", "exception": None},
            "runtime": {}, "schema_valid": False}
    detail = score_prediction({}, gold, pred)
    assert detail["schema_valid"] is False
    assert "schema_invalid" in detail["failure_categories"]


# ---------------------------------------------------------------------------
# 6. evaluate_predictions — sample_id mismatch
# ---------------------------------------------------------------------------

def test_sample_id_mismatch_raises():
    gold = [{"sample_id": "001", "modality": "obligation", "actor": "a", "action": "ac",
             "condition": None, "constraint": "c", "exception": None}]
    pred = [{"sample_id": "002", "source_id": "s",
             "predicted": {"modality": "obligation", "actor": "a", "action": "ac",
                           "condition": None, "constraint": "c", "exception": None},
             "runtime": {}, "schema_valid": True}]
    with pytest.raises(ValueError, match="sample_id mismatch"):
        evaluate_predictions([], gold, pred)


# ---------------------------------------------------------------------------
# 7. evaluate_predictions — summary
# ---------------------------------------------------------------------------

def test_evaluator_summary_contains_field_score_counts(mock_predictions):
    gold = [
        {"sample_id": "r13_3_candidate_001", "modality": "obligation",
         "actor": "entity processing personal data", "action": "process personal data",
         "condition": None,
         "constraint": "Personal data must be processed lawfully, fairly, and in a transparent manner in relation to the data subject.",
         "exception": None},
        {"sample_id": "r13_3_candidate_002", "modality": "obligation",
         "actor": "entity collecting or further processing personal data",
         "action": "collect and further process personal data",
         "condition": None,
         "constraint": "Personal data must be collected for specified purposes.",
         "exception": None},
    ]
    summary, details = evaluate_predictions([], gold, mock_predictions)
    assert summary["sample_count"] == 2
    assert "field_score_counts" in summary
    for dim in ["modality", "actor", "action", "condition", "constraint", "exception"]:
        assert dim in summary["field_score_counts"]


def test_evaluator_summary_no_overclaim():
    """Summary must not contain benchmark/method_validation/sun_reproduction claims."""
    gold = [
        {"sample_id": "r13_3_candidate_001", "modality": "obligation",
         "actor": "a", "action": "ac", "condition": None, "constraint": "c", "exception": None},
    ]
    pred = [
        {"sample_id": "r13_3_candidate_001", "source_id": "s",
         "predicted": {"modality": "obligation", "actor": "a", "action": "ac",
                       "condition": None, "constraint": "c", "exception": None},
         "runtime": {}, "schema_valid": True},
    ]
    summary, _ = evaluate_predictions([], gold, pred)
    assert summary["benchmark"] is False
    assert summary["method_validation"] is False
    assert summary["sun_reproduction"] is False
    assert summary["real_api_call"] is False


# ---------------------------------------------------------------------------
# 8. write_json / write_jsonl roundtrip
# ---------------------------------------------------------------------------

def test_write_json_roundtrip(tmp_path):
    obj = {"key": "value", "nested": {"a": 1}}
    p = tmp_path / "test.json"
    write_json(str(p), obj)
    loaded = json.loads(p.read_text(encoding="utf-8"))
    assert loaded == obj


def test_write_jsonl_roundtrip(tmp_path):
    recs = [{"a": 1}, {"b": 2}]
    p = tmp_path / "test.jsonl"
    write_jsonl(str(p), recs)
    loaded = load_jsonl(str(p))
    assert loaded == recs


# ---------------------------------------------------------------------------
# 9. Normalisation helpers
# ---------------------------------------------------------------------------

def test_normalize_text_lowercase():
    assert _normalize_text("Hello World") == "hello world"


def test_normalize_text_collapse_whitespace():
    assert _normalize_text("hello    world") == "hello world"


def test_normalize_text_strip():
    assert _normalize_text("  hello  ") == "hello"


def test_normalize_text_remove_punctuation():
    assert _normalize_text("hello, world!") == "hello world"


def test_normalize_text_none():
    assert _normalize_text(None) is None


def test_token_overlap_identical():
    assert _token_overlap_ratio("a b c", "a b c") == 1.0


def test_token_overlap_none():
    assert _token_overlap_ratio("x y", "a b") == 0.0


def test_token_overlap_half():
    assert _token_overlap_ratio("a b c", "c d e") == 0.2


# ---------------------------------------------------------------------------
# 10. CLI creates summary and details outputs (mock predictions)
# ---------------------------------------------------------------------------

def test_cli_creates_outputs():
    """Run the CLI script with mock predictions and verify output files exist."""
    import subprocess
    import tempfile
    import os

    project_root = Path(__file__).resolve().parent.parent
    candidates_path = project_root / "data" / "formal" / "processed" / "r13_3_candidate_samples.jsonl"
    gold_path = project_root / "data" / "formal" / "gold" / "r13_3_manual_gold_template.jsonl"
    pred_path = project_root / "data" / "formal" / "predictions" / "r13_4_1_mock_predictions.jsonl"

    with tempfile.TemporaryDirectory() as tmpdir:
        summary_out = os.path.join(tmpdir, "summary.json")
        details_out = os.path.join(tmpdir, "details.jsonl")
        cmd = [
            sys.executable,
            str(project_root / "scripts" / "evaluate_mini_pilot_predictions.py"),
            "--candidates", str(candidates_path),
            "--gold", str(gold_path),
            "--predictions", str(pred_path),
            "--summary-out", summary_out,
            "--details-out", details_out,
        ]
        env = os.environ.copy()
        env["BPC_HYBRID_DISABLE_PROJECT_ENV"] = "1"
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(project_root))
        assert result.returncode == 0, f"CLI failed: {result.stderr}"

        # Verify outputs
        assert os.path.isfile(summary_out), "summary_out not created"
        assert os.path.isfile(details_out), "details_out not created"

        summary = json.loads(Path(summary_out).read_text(encoding="utf-8"))
        assert summary["sample_count"] == 8
        assert summary["real_api_call"] is False
        assert summary["benchmark"] is False

        details = load_jsonl(details_out)
        assert len(details) == 8
        for d in details:
            assert "field_scores" in d


# ---------------------------------------------------------------------------
# 11. Mock summary has no real_api_call
# ---------------------------------------------------------------------------

def test_mock_summary_no_real_api_call(mock_predictions):
    gold = [
        {"sample_id": "r13_3_candidate_001", "modality": "obligation",
         "actor": "a", "action": "ac", "condition": None, "constraint": "c", "exception": None},
    ]
    pred = mock_predictions[:1]
    summary, _ = evaluate_predictions([], gold, pred)
    assert summary["real_api_call"] is False


# ---------------------------------------------------------------------------
# 12. Runtime error_category propagates
# ---------------------------------------------------------------------------

def test_runtime_error_category_propagates():
    gold = [{"sample_id": "001", "modality": "obligation", "actor": "a", "action": "ac",
             "condition": None, "constraint": "c", "exception": None}]
    pred = [{"sample_id": "001", "source_id": "s",
             "predicted": {"modality": "obligation", "actor": "a", "action": "ac",
                           "condition": None, "constraint": "c", "exception": None},
             "runtime": {"error_category": "api_timeout", "attempt_count": 1},
             "schema_valid": True}]
    _, details = evaluate_predictions([], gold, pred)
    assert "api_timeout" in details[0]["failure_categories"]

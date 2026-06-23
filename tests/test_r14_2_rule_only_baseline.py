"""
R14.2 Rule-only Baseline Tests
==============================
Tests for the rule-only baseline predictor and field-level evaluator.
No LLM, no API, no network.
"""
import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Import the evaluator functions directly
from scripts.evaluate_r14_field_metrics import (
    score_modality,
    score_text_field,
    evaluate,
    _normalize,
    _token_jaccard,
)

# ---------------------------------------------------------------------------
# Test data paths
# ---------------------------------------------------------------------------
PREDICTIONS_PATH = _PROJECT_ROOT / "data" / "formal" / "predictions" / "r14_2_rule_only_predictions.jsonl"
GOLD_PATH = _PROJECT_ROOT / "data" / "formal" / "r14_controlled" / "r14_1_mini_gold.jsonl"
SUMMARY_PATH = _PROJECT_ROOT / "data" / "formal" / "results" / "r14_2_rule_only_evaluation_summary.json"
MANIFEST_PATH = _PROJECT_ROOT / "data" / "formal" / "metadata" / "r14_2_rule_only_manifest.json"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


# ---------------------------------------------------------------------------
# Test 1: Predictor does not use LLM/API
# ---------------------------------------------------------------------------

class TestPredictorNoLLM:
    def test_predictions_exist(self):
        assert PREDICTIONS_PATH.exists(), "Predictions file missing"

    def test_all_predictions_no_llm(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        for p in preds:
            exec_info = p.get("execution", {})
            assert exec_info.get("llm_used") is False, f"LLM used for {p.get('sample_id')}"
            assert exec_info.get("api_used") is False, f"API used for {p.get('sample_id')}"
            assert exec_info.get("network_used") is False, f"Network used for {p.get('sample_id')}"

    def test_all_method_is_rule_only(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        for p in preds:
            assert p.get("method") == "rule_only", f"Method not rule_only: {p.get('method')}"


# ---------------------------------------------------------------------------
# Test 2: Prediction output has 24 rows
# ---------------------------------------------------------------------------

class TestPredictionStructure:
    def test_24_predictions(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        assert len(preds) == 24, f"Expected 24 predictions, got {len(preds)}"

    def test_unique_sample_ids(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        ids = [p["sample_id"] for p in preds]
        assert len(ids) == len(set(ids)), "Duplicate sample IDs in predictions"


# ---------------------------------------------------------------------------
# Test 3: Prediction sample IDs match R14.1 samples
# ---------------------------------------------------------------------------

class TestSampleIdAlignment:
    def test_ids_match_gold(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        gold = _load_jsonl(GOLD_PATH)
        pred_ids = {p["sample_id"] for p in preds}
        gold_ids = {g["sample_id"] for g in gold}
        assert pred_ids == gold_ids, f"Mismatch: {pred_ids ^ gold_ids}"


# ---------------------------------------------------------------------------
# Test 4: Each prediction has six fields
# ---------------------------------------------------------------------------

class TestPredictionFields:
    _REQUIRED_FIELDS = {"modality", "actor", "action", "condition", "constraint", "exception"}

    def test_all_have_six_fields(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        for p in preds:
            fields = p.get("prediction_fields", {})
            field_keys = set(fields.keys())
            assert field_keys == self._REQUIRED_FIELDS, (
                f"{p['sample_id']}: got {sorted(field_keys)}, expected {sorted(self._REQUIRED_FIELDS)}"
            )

    def test_each_field_has_value_key(self):
        preds = _load_jsonl(PREDICTIONS_PATH)
        for p in preds:
            fields = p.get("prediction_fields", {})
            for fname in self._REQUIRED_FIELDS:
                fobj = fields.get(fname)
                assert isinstance(fobj, dict), f"{p['sample_id']}.{fname}: not a dict"
                assert "value" in fobj, f"{p['sample_id']}.{fname}: missing 'value' key"


# ---------------------------------------------------------------------------
# Test 5: Evaluator respects Jaccard = 1.0 exact
# ---------------------------------------------------------------------------

class TestJaccardExact:
    def test_jaccard_1_0_is_exact(self):
        result = score_text_field("the controller shall record", "record controller shall the")
        assert result == "exact", f"Expected exact, got {result}"

    def test_normalized_equality_is_exact(self):
        result = score_text_field("  The Controller  ", "the controller")
        assert result == "exact", f"Expected exact, got {result}"

    def test_jaccard_1p0_same_tokens(self):
        result = score_text_field("data personal", "personal data")
        assert result == "exact", f"Expected exact, got {result}"


# ---------------------------------------------------------------------------
# Test 6: Evaluator respects Jaccard = 0.5 partial
# ---------------------------------------------------------------------------

class TestJaccardPartial:
    def test_jaccard_0_5_is_partial(self):
        # "the controller" vs "controller" → {the,controller} ∩ {controller} = 1, union = 2
        result = score_text_field("the controller", "controller")
        assert result == "partial", f"Expected partial, got {result}"

    def test_jaccard_between_0_5_and_1_is_partial(self):
        # "collect and further process personal data" vs "collect and process personal data"
        result = score_text_field(
            "collect and further process personal data",
            "collect and process personal data"
        )
        assert result == "partial", f"Expected partial, got {result}"


# ---------------------------------------------------------------------------
# Test 7: Evaluator respects Jaccard < 0.5 wrong
# ---------------------------------------------------------------------------

class TestJaccardWrong:
    def test_jaccard_lt_0_5_is_wrong(self):
        result = score_text_field("the controller shall record", "the data subject may request")
        assert result == "wrong", f"Expected wrong, got {result}"

    def test_completely_different_is_wrong(self):
        result = score_text_field("hello world", "goodbye universe")
        assert result == "wrong", f"Expected wrong, got {result}"


# ---------------------------------------------------------------------------
# Test 8: Summary contains overall and field-level metrics
# ---------------------------------------------------------------------------

class TestSummaryStructure:
    def test_summary_exists(self):
        assert SUMMARY_PATH.exists(), "Summary file missing"

    def test_summary_has_required_keys(self):
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        required = [
            "stage", "method", "sample_count",
            "overall_field_exact_accuracy",
            "strict_precision", "strict_recall", "strict_f1",
            "lenient_partial_precision", "lenient_partial_recall", "lenient_partial_f1",
            "macro_strict_f1", "micro_strict_f1",
            "macro_lenient_f1", "micro_lenient_f1",
            "field_level_summary",
        ]
        for key in required:
            assert key in summary, f"Summary missing key: {key}"

    def test_summary_llm_superiority_boundary(self):
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        assert "llm_superiority_claim" in summary, "Summary missing llm_superiority_claim"
        assert summary["llm_superiority_claim"] is False, (
            f"llm_superiority_claim must be False, got {summary['llm_superiority_claim']}"
        )

    def test_field_level_summary_has_six_fields(self):
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        fls = summary.get("field_level_summary", {})
        expected_fields = {"modality", "actor", "action", "condition", "constraint", "exception"}
        assert set(fls.keys()) == expected_fields, f"Fields: {set(fls.keys())}"

    def test_each_field_has_required_stats(self):
        summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        fls = summary.get("field_level_summary", {})
        required_stats = {
            "applicable_gold_count", "exact_count", "partial_count",
            "missing_count", "wrong_count", "not_applicable_count",
            "strict_precision", "strict_recall", "strict_f1",
            "lenient_precision", "lenient_recall", "lenient_f1",
        }
        for fname, fstats in fls.items():
            missing = required_stats - set(fstats.keys())
            assert not missing, f"{fname}: missing stats {missing}"


# ---------------------------------------------------------------------------
# Test 9: Manifest flags no real API / no LLM / no Rule+LLM
# ---------------------------------------------------------------------------

class TestManifest:
    def test_manifest_exists(self):
        assert MANIFEST_PATH.exists(), "Manifest file missing"

    def test_manifest_safety_flags(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert manifest["real_api_call_performed"] is False
        assert manifest["llm_call_performed"] is False
        assert manifest["rule_plus_llm_experiment_run"] is False
        assert manifest["rule_only_experiment_run"] is True
        assert manifest["benchmark"] is False
        assert manifest["method_validation"] is False
        assert manifest["sun_reproduction"] is False
        assert manifest["llm_superiority_claim"] is False

    def test_manifest_method_is_rule_only(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        assert manifest["method"] == "rule_only"
        assert manifest["stage"] == "R14.2"


# ---------------------------------------------------------------------------
# Test: NA scoring
# ---------------------------------------------------------------------------

class TestNAScoring:
    def test_both_null_is_na(self):
        result = score_text_field(None, None)
        assert result == "not_applicable"

    def test_gold_null_pred_not_null_is_wrong(self):
        result = score_text_field("something", None)
        assert result == "wrong"

    def test_gold_not_null_pred_null_is_missing(self):
        result = score_text_field(None, "something")
        assert result == "missing"

    def test_modality_na(self):
        result = score_modality(None, None)
        assert result == "not_applicable"


# ---------------------------------------------------------------------------
# Test: Modality scoring
# ---------------------------------------------------------------------------

class TestModalityScoring:
    def test_exact_obligation(self):
        assert score_modality("obligation", "obligation") == "exact"

    def test_wrong_modality(self):
        assert score_modality("prohibition", "obligation") == "wrong"

    def test_missing_modality(self):
        assert score_modality(None, "obligation") == "missing"

    def test_false_positive_modality(self):
        assert score_modality("obligation", None) == "wrong"

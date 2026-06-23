"""R14.5 Descriptive Comparison Tests.

Validates that the R14.5 comparison outputs conform to the contract:
- All safety flags negative
- No overclaim language
- Six field coverage
- Sample count = 24
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_COMPARISON_SUMMARY_PATH = _PROJECT_ROOT / "data" / "formal" / "results" / "r14_5_rule_only_vs_rule_plus_llm_comparison_summary.json"
_FIELD_COMPARISON_PATH = _PROJECT_ROOT / "data" / "formal" / "results" / "r14_5_rule_only_vs_rule_plus_llm_field_comparison.jsonl"
_MANIFEST_PATH = _PROJECT_ROOT / "data" / "formal" / "metadata" / "r14_5_descriptive_comparison_manifest.json"
_REPORT_PATH = _PROJECT_ROOT / "docs" / "r14_5_descriptive_comparison_report.md"
_PPT_TABLE_PATH = _PROJECT_ROOT / "docs" / "r14_5_ppt_safe_result_table.md"

REQUIRED_FIELDS = {"modality", "actor", "action", "condition", "constraint", "exception"}

FORBIDDEN_OVERTLAIM_WORDS = [
    "better", "winner", "validated", "proved",
    "benchmark completed", "method validated", "outperformed Sun",
    "LLM is better", "LLM proves better", "LLM superiority",
    "Rule+LLM wins", "validated method", "production-ready GDPR",
    "production GDPR compliance checker", "formal conclusion",
]


def _read_summary() -> dict:
    return json.loads(_COMPARISON_SUMMARY_PATH.read_text(encoding="utf-8"))


def _read_field_rows() -> list[dict]:
    rows: list[dict] = []
    with _FIELD_COMPARISON_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


class TestComparisonSummary:
    """Tests for the R14.5 comparison summary JSON."""

    def test_1_comparison_summary_exists(self):
        assert _COMPARISON_SUMMARY_PATH.exists(), "Comparison summary missing"

    def test_2_stage_is_r14_5(self):
        s = _read_summary()
        assert s["stage"] == "R14.5"

    def test_3_type_is_descriptive_comparison(self):
        s = _read_summary()
        assert s["type"] == "descriptive_comparison"

    def test_4_sample_count_is_24(self):
        s = _read_summary()
        assert s["sample_count"] == 24

    def test_5_real_api_call_performed_false(self):
        s = _read_summary()
        assert s["real_api_call_performed"] is False

    def test_6_llm_call_performed_false(self):
        s = _read_summary()
        assert s["llm_call_performed"] is False

    def test_7_runner_rerun_false(self):
        s = _read_summary()
        assert s["runner_rerun"] is False

    def test_8_evaluator_rerun_false(self):
        s = _read_summary()
        assert s["evaluator_rerun"] is False

    def test_9_metrics_recomputed_false(self):
        s = _read_summary()
        assert s["metrics_recomputed"] is False

    def test_10_benchmark_false(self):
        s = _read_summary()
        assert s["benchmark"] is False

    def test_11_method_validation_false(self):
        s = _read_summary()
        assert s["method_validation"] is False

    def test_12_sun_reproduction_false(self):
        s = _read_summary()
        assert s["sun_reproduction"] is False

    def test_13_llm_superiority_claim_false(self):
        s = _read_summary()
        assert s["llm_superiority_claim"] is False

    def test_14_all_overall_deltas_computed(self):
        s = _read_summary()
        deltas = s.get("overall_deltas", {})
        expected_keys = [
            "overall_field_exact_accuracy_delta",
            "macro_strict_f1_delta",
            "micro_strict_f1_delta",
            "macro_lenient_f1_delta",
            "micro_lenient_f1_delta",
        ]
        for key in expected_keys:
            assert key in deltas, f"Missing delta key: {key}"
            assert deltas[key] is not None, f"Delta {key} is None"


class TestFieldComparison:
    """Tests for the R14.5 field comparison JSONL."""

    def test_15_field_comparison_exists(self):
        assert _FIELD_COMPARISON_PATH.exists(), "Field comparison missing"

    def test_16_six_fields_present(self):
        rows = _read_field_rows()
        assert len(rows) == 6, f"Expected 6 fields, got {len(rows)}"

    def test_17_all_required_fields_covered(self):
        rows = _read_field_rows()
        fields = {r["field"] for r in rows}
        assert fields == REQUIRED_FIELDS

    def test_18_all_rows_have_claim_boundary(self):
        rows = _read_field_rows()
        for r in rows:
            assert "claim_boundary" in r

    def test_19_all_rows_have_rule_only_metrics(self):
        rows = _read_field_rows()
        for r in rows:
            ro = r["rule_only"]
            assert "exact_accuracy" in ro
            assert "strict_f1" in ro
            assert "lenient_f1" in ro

    def test_20_all_rows_have_rule_plus_llm_metrics(self):
        rows = _read_field_rows()
        for r in rows:
            rl = r["rule_plus_llm"]
            assert "exact_accuracy" in rl
            assert "strict_f1" in rl
            assert "lenient_f1" in rl


class TestNoOverclaimLanguage:
    """Scan R14.5 outputs for forbidden overclaim language."""

    def test_21_summary_no_overclaim(self):
        text = _COMPARISON_SUMMARY_PATH.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_OVERTLAIM_WORDS:
            assert word.lower() not in text, (
                f"Forbidden word '{word}' found in comparison summary"
            )

    def test_22_field_comparison_no_overclaim(self):
        text = _FIELD_COMPARISON_PATH.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_OVERTLAIM_WORDS:
            assert word.lower() not in text, (
                f"Forbidden word '{word}' found in field comparison"
            )

    def test_23_report_no_overclaim(self):
        if not _REPORT_PATH.exists():
            pytest.skip("Report not yet created")
        text = _REPORT_PATH.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_OVERTLAIM_WORDS:
            assert word.lower() not in text, (
                f"Forbidden word '{word}' found in report"
            )

    def test_24_ppt_table_no_overclaim(self):
        if not _PPT_TABLE_PATH.exists():
            pytest.skip("PPT table not yet created")
        text = _PPT_TABLE_PATH.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_OVERTLAIM_WORDS:
            assert word.lower() not in text, (
                f"Forbidden word '{word}' found in PPT table"
            )


class TestManifest:
    """Tests for the R14.5 manifest."""

    def test_25_manifest_exists(self):
        assert _MANIFEST_PATH.exists(), "Manifest missing"

    def test_26_manifest_stage(self):
        m = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
        assert m["stage"] == "R14.5"
        assert m["type"] == "descriptive_comparison_manifest"
        assert m["benchmark"] is False
        assert m["method_validation"] is False
        assert m["sun_reproduction"] is False
        assert m["llm_superiority_claim"] is False

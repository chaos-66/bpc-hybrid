"""R14.4 Rule+LLM Real Pilot Safety Tests.

Covers 15 test items for the R14.4 bounded real API pilot:
  1. No API calls without --execute-real-api
  2. Max API calls ceiling enforced
  3. Prompt snapshot SHA256 verification
  4. Prompt snapshot size verification
  5. Prediction output has correct format
  6. Each prediction has all 6 required fields with "value" keys
  7. method always equals "rule_plus_llm_assisted"
  8. selected_prompt_id always equals "r13_6_prompt_B"
  9. execution metadata contains required keys
  10. raw_response_saved always False
  11. retry_used always False
  12. repair_call_used always False
  13. batch_used always False
  14. attempt_index always 1
  15. No more than 24 predictions in output
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CANDIDATES_PATH = _PROJECT_ROOT / "data" / "formal" / "r14_controlled" / "r14_1_candidate_samples.jsonl"
_PREDICTIONS_PATH = _PROJECT_ROOT / "data" / "formal" / "predictions" / "r14_4_rule_plus_llm_predictions.jsonl"
_PROMPT_SNAPSHOT_PATH = _PROJECT_ROOT / "data" / "formal" / "metadata" / "r14_3_prompt_snapshot.json"
_PROMPT_B_PATH = _PROJECT_ROOT / "prompts" / "r13_6" / "few_shot_extraction_prompt.md"
_RUNNER_SCRIPT = _PROJECT_ROOT / "scripts" / "run_r14_4_rule_plus_llm_real_pilot.py"

REQUIRED_PRED_KEYS = {"modality", "actor", "action", "condition", "constraint", "exception"}
REQUIRED_EXECUTION_KEYS = {
    "llm_used", "api_used", "network_used", "attempt_index",
    "retry_used", "repair_call_used", "batch_used", "raw_response_saved",
    "error_category", "provider", "model", "duration_ms",
}


# ---------------------------------------------------------------------------
# Runner CLI tests (no network needed)
# ---------------------------------------------------------------------------

class TestRunnerGate:
    """Tests for the authorization gate and CLI safety."""

    def test_1_no_api_calls_without_execute_real_api(self):
        """R14.4-T1: Without --execute-real-api, no API calls should occur."""
        result = subprocess.run(
            [sys.executable, str(_RUNNER_SCRIPT)],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
            env={**__import__("os").environ, "BPC_HYBRID_LLM_ENABLED": "true"},
        )
        # Should exit with error and not make any API calls
        assert result.returncode != 0, "Should exit non-zero without --execute-real-api"
        # sys.exit(str) writes to stderr
        output = (result.stderr or result.stdout).strip()
        assert output, "Expected error output"
        data = json.loads(output)
        assert data.get("real_api_call_performed") is False
        assert "REAL_API_NOT_ENABLED" in data.get("status", "")

    def test_2_max_api_calls_ceiling_enforced(self):
        """R14.4-T2: --max-api-calls > 24 should be rejected."""
        result = subprocess.run(
            [sys.executable, str(_RUNNER_SCRIPT), "--execute-real-api", "--max-api-calls", "25"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
        )
        assert result.returncode != 0
        output = (result.stderr or result.stdout).strip()
        assert output, "Expected error output"
        data = json.loads(output)
        assert "TOO_MANY_CALLS" in data.get("status", "")

    def test_3_max_api_calls_boundary_24_ok(self):
        """R14.4-T2b: --max-api-calls 24 should pass the ceiling check."""
        result = subprocess.run(
            [sys.executable, str(_RUNNER_SCRIPT), "--execute-real-api", "--max-api-calls", "24"],
            capture_output=True, text=True, cwd=str(_PROJECT_ROOT),
            env={**__import__("os").environ, "BPC_HYBRID_LLM_ENABLED": "true"},
        )
        # It may fail on missing config/auth, but should NOT fail with TOO_MANY_CALLS
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            if output:
                try:
                    data = json.loads(output)
                    assert "TOO_MANY_CALLS" not in data.get("status", "")
                except json.JSONDecodeError:
                    pass


class TestPromptSnapshot:
    """Tests for prompt snapshot verification."""

    def test_4_prompt_sha256_matches_snapshot(self):
        """R14.4-T4: Prompt B SHA256 must match R14.3 snapshot."""
        snapshot = json.loads(_PROMPT_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        expected_sha256 = snapshot["prompt_sha256"]
        actual_sha256 = hashlib.sha256(_PROMPT_B_PATH.read_bytes()).hexdigest()
        assert actual_sha256 == expected_sha256, (
            f"Prompt SHA256 mismatch: {actual_sha256} != {expected_sha256}"
        )

    def test_5_prompt_size_matches_snapshot(self):
        """R14.4-T5: Prompt B size must match R14.3 snapshot."""
        snapshot = json.loads(_PROMPT_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        expected_size = snapshot["prompt_size_bytes"]
        actual_size = len(_PROMPT_B_PATH.read_bytes())
        assert actual_size == expected_size, (
            f"Prompt size mismatch: {actual_size} != {expected_size}"
        )


class TestPredictionsOutputFormat:
    """Tests for predictions output file format."""

    @pytest.fixture(autouse=True)
    def _skip_if_no_predictions(self):
        if not _PREDICTIONS_PATH.exists():
            pytest.skip("No predictions file yet — run R14.4 pilot first")

    def _read_predictions(self) -> list[dict]:
        records = []
        with open(_PREDICTIONS_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                records.append(json.loads(stripped))
        return records

    def test_6_predictions_have_correct_fields(self):
        """R14.4-T6: Each prediction has sample_id, method, selected_prompt_id, prediction_fields, execution."""
        records = self._read_predictions()
        assert len(records) > 0
        for rec in records:
            assert "sample_id" in rec
            assert "method" in rec
            assert "selected_prompt_id" in rec
            assert "prediction_fields" in rec
            assert "execution" in rec

    def test_7_all_six_fields_present_with_value_key(self):
        """R14.4-T7: prediction_fields has all 6 fields, each with 'value' key."""
        records = self._read_predictions()
        for rec in records:
            pf = rec["prediction_fields"]
            for key in REQUIRED_PRED_KEYS:
                assert key in pf, f"Missing field {key} in {rec['sample_id']}"
                assert "value" in pf[key], f"Missing 'value' key in {key} for {rec['sample_id']}"

    def test_8_method_is_rule_plus_llm_assisted(self):
        """R14.4-T8: method always equals 'rule_plus_llm_assisted'."""
        records = self._read_predictions()
        for rec in records:
            assert rec["method"] == "rule_plus_llm_assisted"

    def test_9_selected_prompt_id_is_r13_6_prompt_B(self):
        """R14.4-T9: selected_prompt_id always equals 'r13_6_prompt_B'."""
        records = self._read_predictions()
        for rec in records:
            assert rec["selected_prompt_id"] == "r13_6_prompt_B"

    def test_10_execution_has_all_required_keys(self):
        """R14.4-T10: execution metadata contains all required keys."""
        records = self._read_predictions()
        for rec in records:
            exec_meta = rec["execution"]
            for key in REQUIRED_EXECUTION_KEYS:
                assert key in exec_meta, f"Missing execution key {key} in {rec['sample_id']}"

    def test_11_raw_response_saved_always_false(self):
        """R14.4-T11: raw_response_saved is always False."""
        records = self._read_predictions()
        for rec in records:
            assert rec["execution"]["raw_response_saved"] is False, (
                f"raw_response_saved is True for {rec['sample_id']}"
            )

    def test_12_retry_used_always_false(self):
        """R14.4-T12: retry_used is always False."""
        records = self._read_predictions()
        for rec in records:
            assert rec["execution"]["retry_used"] is False

    def test_13_repair_call_used_always_false(self):
        """R14.4-T13: repair_call_used is always False."""
        records = self._read_predictions()
        for rec in records:
            assert rec["execution"]["repair_call_used"] is False

    def test_14_batch_used_always_false(self):
        """R14.4-T14: batch_used is always False."""
        records = self._read_predictions()
        for rec in records:
            assert rec["execution"]["batch_used"] is False

    def test_15_attempt_index_always_1(self):
        """R14.4-T15: attempt_index is always 1 (no retries)."""
        records = self._read_predictions()
        for rec in records:
            assert rec["execution"]["attempt_index"] == 1

    def test_16_no_more_than_24_predictions(self):
        """R14.4-T16: Output has at most 24 predictions."""
        records = self._read_predictions()
        assert len(records) <= 24


class TestCandidatesIntegrity:
    """Tests for candidate sample integrity."""

    def test_candidates_24_samples(self):
        """Candidates file has exactly 24 samples."""
        records = []
        with open(_CANDIDATES_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                records.append(json.loads(stripped))
        assert len(records) == 24

    def test_candidates_no_duplicate_ids(self):
        """Candidates have no duplicate sample IDs."""
        records = []
        with open(_CANDIDATES_PATH, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                records.append(json.loads(stripped))
        ids = [r["sample_id"] for r in records]
        assert len(ids) == len(set(ids))

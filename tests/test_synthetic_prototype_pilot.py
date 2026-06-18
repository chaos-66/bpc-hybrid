"""R12.1 Synthetic Prototype Pilot Tests (mock-only).

All tests are mock-only — no real API calls, no .env reading, no
network access.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_jsonl() -> str:
    """Create a temp JSONL with 3 synthetic prototype sentences."""
    content = (
        '{"id":"d01","text":"A controller shall record the decision."}\n'
        '{"id":"d02","text":"A reviewer may inspect the file."}\n'
        '{"id":"d03","text":"A service provider must retain the log."}\n'
    )
    return content


@pytest.fixture
def sample_jsonl_path(sample_jsonl) -> Path:
    """Write sample JSONL to a temp file."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(sample_jsonl)
        return Path(fh.name)


@pytest.fixture
def sample_output_dir() -> Path:
    """Create a temp output directory."""
    return Path(tempfile.mkdtemp(suffix="_r12_1_test"))


# ---------------------------------------------------------------------------
# Test: runner reads synthetic prototype input
# ---------------------------------------------------------------------------


def test_runner_reads_input(sample_jsonl_path, sample_output_dir):
    """Runner successfully reads JSONL input and produces results + summary."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        provider="mock",
    )

    assert len(results) == 3
    assert summary["sample_count"] == 3
    assert summary["formal_benchmark"] is False
    assert summary["method_validation"] is False
    assert summary["dataset_type"] == "synthetic_prototype"
    assert summary["batch"] is False
    assert summary["retry"] is False
    assert summary["repair_call"] is False
    assert summary["raw_response_saved"] is False

    # Check output files exist
    results_path = sample_output_dir / "results.jsonl"
    summary_path = sample_output_dir / "summary.json"
    assert results_path.exists()
    assert summary_path.exists()


# ---------------------------------------------------------------------------
# Test: --max-samples limit
# ---------------------------------------------------------------------------


def test_max_samples_limit(sample_jsonl_path, sample_output_dir):
    """Runner respects --max-samples limit (processes only N items)."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        provider="mock",
    )

    assert len(results) == 2
    assert summary["sample_count"] == 2


# ---------------------------------------------------------------------------
# Test: default mode does not execute real API
# ---------------------------------------------------------------------------


def test_default_mode_no_real_api(sample_jsonl_path, sample_output_dir):
    """Default mode (no --execute-real-api) does not execute real API."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
    )

    meta = results[0]
    assert meta["real_api_call_performed"] is False


# ---------------------------------------------------------------------------
# Test: real provider requires --execute-real-api
# ---------------------------------------------------------------------------


def test_real_provider_without_flag_refuses(sample_jsonl_path, sample_output_dir):
    """Non-mock provider without --execute-real-api is refused."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        provider="openai_compatible",
    )

    meta = results[0]
    assert meta["error"] is not None
    assert meta["real_api_call_performed"] is False
    assert "execute-real-api" in str(meta["error"]).lower()


# ---------------------------------------------------------------------------
# Test: real execution path can be replaced by mock transport
# ---------------------------------------------------------------------------


def test_real_execution_path_mocked(sample_jsonl_path, sample_output_dir, monkeypatch):
    """When --execute-real-api is used, config gate can be mocked."""
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )

    # Also mock RealAPITransport.send to return a valid response
    from bpc_hybrid.llm_client import LLMResponse

    def _fake_send(self, request):
        import json as _json
        from bpc_hybrid.llm_client import make_schema_valid_mock_response_json

        mock_json = make_schema_valid_mock_response_json(
            request.source_text, request.source_id
        )
        return LLMResponse(
            content=mock_json,
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    assert len(results) == 2
    for meta in results:
        assert meta["real_api_call_performed"] is True
        assert meta["attempted_call_count"] == 1
        assert meta["successful_call_count"] == 1
        assert meta["status"] == "schema_valid"


# ---------------------------------------------------------------------------
# Test: each sample gets exactly 1 call
# ---------------------------------------------------------------------------


def test_one_call_per_sample(sample_jsonl_path, sample_output_dir, monkeypatch):
    """Each sample triggers exactly 1 API call."""
    from bpc_hybrid.llm_config import LLMConfig

    call_counts: dict[str, int] = {}

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_client import make_schema_valid_mock_response_json

    def _fake_send(self, request):
        sid = request.source_id
        call_counts[sid] = call_counts.get(sid, 0) + 1
        mock_json = make_schema_valid_mock_response_json(
            request.source_text, request.source_id
        )
        return LLMResponse(
            content=mock_json,
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["attempted_call_count"] == 1
        assert meta["successful_call_count"] == 1

    # Each source_id called exactly once
    for sid, count in call_counts.items():
        assert count == 1, f"source_id={sid} called {count} times, expected 1"


# ---------------------------------------------------------------------------
# Test: no retry
# ---------------------------------------------------------------------------


def test_no_retry(sample_jsonl_path, sample_output_dir, monkeypatch):
    """If a sample fails, no retry is attempted."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
    )

    for meta in results:
        assert meta.get("retry", False) is False
        assert meta.get("repair_call", False) is False


# ---------------------------------------------------------------------------
# Test: no repair call
# ---------------------------------------------------------------------------


def test_no_repair_call(sample_jsonl_path, sample_output_dir):
    """All results have repair_call=False."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
    )

    for meta in results:
        assert meta.get("repair_call", False) is False


# ---------------------------------------------------------------------------
# Test: no raw response saved
# ---------------------------------------------------------------------------


def test_no_raw_response_saved(sample_jsonl_path, sample_output_dir):
    """All results have raw_response_saved=False."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
    )

    for meta in results:
        assert meta.get("raw_response_saved", True) is False


# ---------------------------------------------------------------------------
# Test: no API batch endpoint
# ---------------------------------------------------------------------------


def test_no_batch_endpoint(sample_jsonl_path, sample_output_dir):
    """All results have batch=False."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
    )

    for meta in results:
        assert meta.get("batch", True) is False


# ---------------------------------------------------------------------------
# Test: results.jsonl does not contain raw response field
# ---------------------------------------------------------------------------


def test_results_jsonl_no_raw_response_field(sample_jsonl_path, sample_output_dir):
    """results.jsonl does not contain a raw_response field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
    )

    results_path = sample_output_dir / "results.jsonl"
    with results_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            record = json.loads(line)
            assert "raw_response" not in record, (
                f"raw_response field should not exist in results.jsonl"
            )


# ---------------------------------------------------------------------------
# Test: summary.json declares formal_benchmark=false
# ---------------------------------------------------------------------------


def test_summary_declares_no_benchmark(sample_jsonl_path, sample_output_dir):
    """summary.json states formal_benchmark=false."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
    )

    assert summary["formal_benchmark"] is False


# ---------------------------------------------------------------------------
# Test: summary.json declares method_validation=false
# ---------------------------------------------------------------------------


def test_summary_declares_no_method_validation(sample_jsonl_path, sample_output_dir):
    """summary.json states method_validation=false."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
    )

    assert summary["method_validation"] is False


# ---------------------------------------------------------------------------
# Test: config blocked stops execution
# ---------------------------------------------------------------------------


def test_config_blocked_stops_per_sample(sample_jsonl_path, sample_output_dir, monkeypatch):
    """When config is blocked for a sample, status=config_blocked."""
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=False,
            provider="openai_compatible",
            model="test-model",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "config_blocked"
        assert meta["real_api_call_performed"] is False

    assert summary["config_blocked_count"] == 2


# ---------------------------------------------------------------------------
# Test: API error recorded as api_error, no retry
# ---------------------------------------------------------------------------


def test_api_error_recorded_no_retry(sample_jsonl_path, sample_output_dir, monkeypatch):
    """When API transport fails, status=api_error, no retry."""
    from bpc_hybrid.llm_client import LLMClientError
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        raise LLMClientError("Real API DNS/connection error (details redacted)")

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "api_error"
        assert meta["attempted_call_count"] == 1
        assert meta["successful_call_count"] == 0
        assert meta.get("retry", True) is False

    assert summary["api_error_count"] == 2


# ---------------------------------------------------------------------------
# Test: schema invalid recorded as schema_invalid, no retry
# ---------------------------------------------------------------------------


def test_schema_invalid_recorded_no_retry(sample_jsonl_path, sample_output_dir, monkeypatch):
    """When response is schema-invalid, status=schema_invalid, no retry."""
    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    # Return a response that will NOT be schema-valid
    # Send malformed JSON that normalizer rejects (not a valid MultiClauseExtractionResponse)
    def _fake_send(self, request):
        return LLMResponse(
            content='{"not_a_clause_field": 42, "random_garbage": true}',
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "schema_invalid"
        assert meta.get("schema_valid", True) is False
        assert meta.get("retry", True) is False
        assert meta["attempted_call_count"] == 1
        assert meta["real_api_call_performed"] is True
        assert meta["successful_call_count"] == 0

    assert summary["schema_invalid_count"] == 2


# ============================================================================
# R12.3.0 — Timing / error category metadata tests
# ============================================================================


# ---------------------------------------------------------------------------
# Test: result record contains duration_ms
# ---------------------------------------------------------------------------


def test_result_contains_duration_ms(sample_jsonl_path, sample_output_dir):
    """Each result record has a duration_ms field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
    )

    for meta in results:
        assert "duration_ms" in meta, f"missing duration_ms in {meta.get('source_id')}"
        assert isinstance(meta["duration_ms"], (int, float)), (
            f"duration_ms must be numeric, got {type(meta['duration_ms'])}"
        )
        assert meta["duration_ms"] >= 0, (
            f"duration_ms must be non-negative, got {meta['duration_ms']}"
        )


# ---------------------------------------------------------------------------
# Test: result record contains timeout_seconds_configured
# ---------------------------------------------------------------------------


def test_result_contains_timeout_seconds_configured(sample_jsonl_path, sample_output_dir):
    """Each result record has a timeout_seconds_configured field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
    )

    for meta in results:
        assert "timeout_seconds_configured" in meta
        assert isinstance(meta["timeout_seconds_configured"], (int, float))
        assert meta["timeout_seconds_configured"] > 0


# ---------------------------------------------------------------------------
# Test: result record contains error_category
# ---------------------------------------------------------------------------


def test_result_contains_error_category(sample_jsonl_path, sample_output_dir):
    """Each result record has an error_category field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
    )

    valid_categories = {"none", "timeout", "transport_error", "schema_invalid",
                        "config_blocked", "unknown"}

    for meta in results:
        assert "error_category" in meta
        assert meta["error_category"] in valid_categories, (
            f"invalid error_category: {meta['error_category']}"
        )


# ---------------------------------------------------------------------------
# Test: summary contains duration_ms_total
# ---------------------------------------------------------------------------


def test_summary_contains_duration_ms_total(sample_jsonl_path, sample_output_dir):
    """summary.json has duration_ms_total field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
    )

    assert "duration_ms_total" in summary
    assert isinstance(summary["duration_ms_total"], (int, float))
    assert summary["duration_ms_total"] >= 0


# ---------------------------------------------------------------------------
# Test: summary contains duration_ms_avg
# ---------------------------------------------------------------------------


def test_summary_contains_duration_ms_avg(sample_jsonl_path, sample_output_dir):
    """summary.json has duration_ms_avg field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
    )

    assert "duration_ms_avg" in summary
    assert isinstance(summary["duration_ms_avg"], (int, float))
    assert summary["duration_ms_avg"] >= 0


# ---------------------------------------------------------------------------
# Test: summary contains timeout_error_count
# ---------------------------------------------------------------------------


def test_summary_contains_timeout_error_count(sample_jsonl_path, sample_output_dir):
    """summary.json has timeout_error_count field."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
    )

    assert "timeout_error_count" in summary
    assert isinstance(summary["timeout_error_count"], int)
    assert summary["timeout_error_count"] >= 0


# ---------------------------------------------------------------------------
# Test: timeout error classified as timeout
# ---------------------------------------------------------------------------


def test_timeout_error_classified_as_timeout(sample_jsonl_path, sample_output_dir, monkeypatch):
    """socket.timeout errors produce error_category='timeout'."""
    from bpc_hybrid.llm_client import LLMClientError
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        raise LLMClientError("LLM transport error: Real API timeout (details redacted)")

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "api_error"
        assert meta["error_category"] == "timeout", (
            f"expected timeout, got {meta['error_category']}"
        )

    assert summary["timeout_error_count"] == 2


# ---------------------------------------------------------------------------
# Test: non-timeout transport error classified as transport_error
# ---------------------------------------------------------------------------


def test_non_timeout_transport_error_classified_transport_error(
    sample_jsonl_path, sample_output_dir, monkeypatch
):
    """DNS/connection errors produce error_category='transport_error'."""
    from bpc_hybrid.llm_client import LLMClientError
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        raise LLMClientError("LLM transport error: Real API DNS/connection error (details redacted)")

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "api_error"
        assert meta["error_category"] == "transport_error", (
            f"expected transport_error, got {meta['error_category']}"
        )

    assert summary["transport_error_count"] == 2


# ---------------------------------------------------------------------------
# Test: schema_invalid classified as schema_invalid
# ---------------------------------------------------------------------------


def test_schema_invalid_classified_as_schema_invalid(
    sample_jsonl_path, sample_output_dir, monkeypatch
):
    """Schema-invalid responses produce error_category='schema_invalid'."""
    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        return LLMResponse(
            content='{"not_a_clause_field": 99}',
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "schema_invalid"
        assert meta["error_category"] == "schema_invalid"


# ---------------------------------------------------------------------------
# Test: config_blocked classified as config_blocked
# ---------------------------------------------------------------------------


def test_config_blocked_classified_as_config_blocked(
    sample_jsonl_path, sample_output_dir, monkeypatch
):
    """Config-blocked results produce error_category='config_blocked'."""
    from bpc_hybrid.llm_config import LLMConfig

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=False,
            provider="openai_compatible",
            model="test-model",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "config_blocked"
        assert meta["error_category"] == "config_blocked"


# ---------------------------------------------------------------------------
# Test: schema_valid has error_category=none
# ---------------------------------------------------------------------------


def test_schema_valid_error_category_none(sample_jsonl_path, sample_output_dir, monkeypatch):
    """Schema-valid results produce error_category='none'."""
    from bpc_hybrid.llm_config import LLMConfig
    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_client import make_schema_valid_mock_response_json

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        mock_json = make_schema_valid_mock_response_json(
            request.source_text, request.source_id
        )
        return LLMResponse(
            content=mock_json,
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
    )

    for meta in results:
        assert meta["status"] == "schema_valid"
        assert meta["error_category"] == "none", (
            f"expected none, got {meta['error_category']}"
        )


# ---------------------------------------------------------------------------
# Test: --timeout-seconds 60 stored in metadata
# ---------------------------------------------------------------------------


def test_timeout_seconds_cli_stored_in_metadata(sample_jsonl_path, sample_output_dir, monkeypatch):
    """--timeout-seconds 60 sets timeout_seconds_configured=60 in metadata."""
    from bpc_hybrid.llm_config import LLMConfig
    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_client import make_schema_valid_mock_response_json

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        mock_json = make_schema_valid_mock_response_json(
            request.source_text, request.source_id
        )
        return LLMResponse(
            content=mock_json,
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta["timeout_seconds_configured"] == 60.0, (
            f"expected 60.0, got {meta['timeout_seconds_configured']}"
        )

    assert summary["timeout_seconds_configured"] == 60.0


# ---------------------------------------------------------------------------
# Test: timeout_seconds=None does not crash runner
# ---------------------------------------------------------------------------


def test_timeout_seconds_none_ok(sample_jsonl_path, sample_output_dir):
    """timeout_seconds=None (default) does not crash the runner."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        timeout_seconds=None,
    )

    for meta in results:
        assert meta["timeout_seconds_configured"] > 0
        assert "duration_ms" in meta
        assert "error_category" in meta

    assert "timeout_error_count" in summary


# ---------------------------------------------------------------------------
# Test: env var BPC_HYBRID_LLM_TIMEOUT_SECONDS passes through to metadata
# ---------------------------------------------------------------------------


def test_env_timeout_passes_to_metadata(sample_jsonl_path, sample_output_dir, monkeypatch):
    """When BPC_HYBRID_LLM_TIMEOUT_SECONDS is set, it flows to metadata."""
    monkeypatch.setenv("BPC_HYBRID_LLM_TIMEOUT_SECONDS", "45.5")

    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
    )

    assert results[0]["timeout_seconds_configured"] == 45.5


# ---------------------------------------------------------------------------
# Test: env var restored after run_pilot with timeout_seconds override
# ---------------------------------------------------------------------------


def test_env_var_restored_after_timeout_override(sample_jsonl_path, sample_output_dir, monkeypatch):
    """After run_pilot with timeout_seconds, original env var is restored."""
    import os
    from bpc_hybrid.llm_config import LLMConfig
    from bpc_hybrid.llm_client import LLMResponse
    from bpc_hybrid.llm_client import make_schema_valid_mock_response_json

    monkeypatch.setenv("BPC_HYBRID_LLM_TIMEOUT_SECONDS", "25.0")
    original = os.environ.get("BPC_HYBRID_LLM_TIMEOUT_SECONDS")

    def _fake_from_env(project_root=None, load_project_env=True):
        return LLMConfig(
            enabled=True,
            provider="openai_compatible",
            model="test-model",
            api_key="redacted-test-key",
            base_url="https://test.example.com/v1",
        )

    def _fake_send(self, request):
        mock_json = make_schema_valid_mock_response_json(
            request.source_text, request.source_id
        )
        return LLMResponse(
            content=mock_json,
            provider="openai_compatible",
            model="test-model",
            finish_reason="stop",
        )

    monkeypatch.setattr(
        "scripts.run_single_call_schema_smoke.LLMConfig.from_env",
        _fake_from_env,
    )
    monkeypatch.setattr(
        "bpc_hybrid.llm_client.RealAPITransport.send",
        _fake_send,
    )

    from scripts.run_synthetic_prototype_pilot import run_pilot

    run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=1,
        output_dir=str(sample_output_dir),
        execute_real_api=True,
        provider="openai_compatible",
        timeout_seconds=60.0,
    )

    # After run_pilot, original env var should be restored
    restored = os.environ.get("BPC_HYBRID_LLM_TIMEOUT_SECONDS")
    assert restored == original, (
        f"env var not restored: original={original}, restored={restored}"
    )


# ---------------------------------------------------------------------------
# Test: duration_ms_total equals sum of per-sample durations
# ---------------------------------------------------------------------------


def test_duration_ms_total_equals_sum(sample_jsonl_path, sample_output_dir):
    """summary.duration_ms_total equals sum of per-sample duration_ms values."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=3,
        output_dir=str(sample_output_dir),
    )

    expected_total = sum(r.get("duration_ms", 0) for r in results)
    assert summary["duration_ms_total"] == expected_total, (
        f"duration_ms_total={summary['duration_ms_total']}, "
        f"expected={expected_total}"
    )


# ============================================================================
# R12.3.0.1 — Dry-run timeout metadata propagation tests
# ============================================================================


# ---------------------------------------------------------------------------
# Test: safe dry-run with --timeout-seconds 60 writes summary
#        timeout_seconds_configured=60.0
# ---------------------------------------------------------------------------


def test_dryrun_timeout_seconds_summary_60(sample_jsonl_path, sample_output_dir):
    """safe dry-run with --timeout-seconds 60: summary timeout_seconds_configured=60.0."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    assert summary["timeout_seconds_configured"] == 60.0, (
        f"expected 60.0, got {summary['timeout_seconds_configured']}"
    )


# ---------------------------------------------------------------------------
# Test: safe dry-run with --timeout-seconds 60 writes every result
#        timeout_seconds_configured=60.0
# ---------------------------------------------------------------------------


def test_dryrun_timeout_seconds_per_result_60(sample_jsonl_path, sample_output_dir):
    """safe dry-run with --timeout-seconds 60: every result record has 60.0."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta["timeout_seconds_configured"] == 60.0, (
            f"expected 60.0, got {meta['timeout_seconds_configured']}"
        )


# ---------------------------------------------------------------------------
# Test: safe dry-run attempted_call_count_total=0
# ---------------------------------------------------------------------------


def test_dryrun_attempted_call_count_zero(sample_jsonl_path, sample_output_dir):
    """safe dry-run has attempted_call_count_total=0."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    _, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    assert summary["attempted_call_count_total"] == 0, (
        f"expected 0, got {summary['attempted_call_count_total']}"
    )


# ---------------------------------------------------------------------------
# Test: safe dry-run real_api_call_performed=false
# ---------------------------------------------------------------------------


def test_dryrun_real_api_call_performed_false(sample_jsonl_path, sample_output_dir):
    """safe dry-run has real_api_call_performed=false on every result."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta["real_api_call_performed"] is False, (
            f"expected False, got {meta['real_api_call_performed']}"
        )


# ---------------------------------------------------------------------------
# Test: safe dry-run raw_response_saved=false
# ---------------------------------------------------------------------------


def test_dryrun_raw_response_saved_false(sample_jsonl_path, sample_output_dir):
    """safe dry-run has raw_response_saved=false on every result."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta.get("raw_response_saved", True) is False


# ---------------------------------------------------------------------------
# Test: safe dry-run batch=false
# ---------------------------------------------------------------------------


def test_dryrun_batch_false(sample_jsonl_path, sample_output_dir):
    """safe dry-run has batch=false on every result."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta.get("batch", True) is False


# ---------------------------------------------------------------------------
# Test: safe dry-run retry=false
# ---------------------------------------------------------------------------


def test_dryrun_retry_false(sample_jsonl_path, sample_output_dir):
    """safe dry-run has retry=false on every result."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta.get("retry", True) is False


# ---------------------------------------------------------------------------
# Test: safe dry-run repair_call=false
# ---------------------------------------------------------------------------


def test_dryrun_repair_call_false(sample_jsonl_path, sample_output_dir):
    """safe dry-run has repair_call=false on every result."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, _ = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    for meta in results:
        assert meta.get("repair_call", True) is False


# ---------------------------------------------------------------------------
# Test: --timeout-seconds does not trigger real API without --execute-real-api
# ---------------------------------------------------------------------------


def test_timeout_seconds_does_not_trigger_real_api(
    sample_jsonl_path, sample_output_dir,
):
    """--timeout-seconds alone does not trigger real API without --execute-real-api."""
    from scripts.run_synthetic_prototype_pilot import run_pilot

    results, summary = run_pilot(
        input_file=str(sample_jsonl_path),
        max_samples=2,
        output_dir=str(sample_output_dir),
        execute_real_api=False,
        timeout_seconds=60.0,
    )

    assert summary["attempted_call_count_total"] == 0
    for meta in results:
        assert meta["real_api_call_performed"] is False

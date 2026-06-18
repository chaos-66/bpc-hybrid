"""Tests for R11.3 single-call entrypoint scaffold (test_single_call_entrypoint.py).

Covers:
- Mock default path (succeeds with schema-valid output)
- Non-mock provider refused without --execute-real-api
- --execute-real-api scaffold refusal
- Metadata structure completeness
- Error handling
- Safety constraints (.env, network, raw response, batch)
- Programmatic API (run_single_call)

**No real API, no .env read, no raw response storage, no network.**
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _PROJECT_ROOT / "scripts"
_ENTRYPOINT = _SCRIPTS_DIR / "run_single_call_schema_smoke.py"

# Ensure src is importable
_SRC = str(_PROJECT_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from scripts.run_single_call_schema_smoke import (  # noqa: E402
    _METADATA_TEMPLATE,
    _R11_3_REAL_REFUSAL_MSG,
    _build_metadata,
    run_single_call,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_source_id() -> str:
    return "r11_3_test_001"


@pytest.fixture
def sample_text() -> str:
    return "A controller shall record the decision."


# ===========================================================================
# TestMetadataStructure
# ===========================================================================


class TestMetadataStructure:
    """Verify that the metadata template contains all required fields."""

    REQUIRED_KEYS: set[str] = {
        "source_id",
        "input_text",
        "provider",
        "model",
        "entrypoint",
        "real_api_call_performed",
        "attempted_call_count",
        "successful_call_count",
        "fallback_status",
        "schema_valid",
        "normalizer_used",
        "normalizer_status",
        "raw_response_saved",
        "secret_redacted",
        "batch",
        "error",
        "output",
    }

    def test_template_has_all_required_keys(self):
        missing = self.REQUIRED_KEYS - set(_METADATA_TEMPLATE.keys())
        assert not missing, f"Missing metadata keys: {sorted(missing)}"

    def test_build_metadata_includes_all_keys(self, sample_source_id, sample_text):
        meta = _build_metadata(
            source_id=sample_source_id,
            input_text=sample_text,
        )
        missing = self.REQUIRED_KEYS - set(meta.keys())
        assert not missing, f"Missing metadata keys in build output: {sorted(missing)}"

    def test_entrypoint_value(self):
        assert _METADATA_TEMPLATE["entrypoint"] == "scripts/run_single_call_schema_smoke.py"

    def test_safety_flags_default_false(self):
        assert _METADATA_TEMPLATE["real_api_call_performed"] is False
        assert _METADATA_TEMPLATE["raw_response_saved"] is False
        assert _METADATA_TEMPLATE["batch"] is False

    def test_secret_redacted_true(self):
        assert _METADATA_TEMPLATE["secret_redacted"] is True


# ===========================================================================
# TestMockDefaultPath
# ===========================================================================


class TestMockDefaultPath:
    """Mock default behavior: no --execute-real-api, mock provider → success."""

    def test_mock_default_succeeds(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["error"] is None
        assert meta["fallback_status"] == "success"
        assert meta["schema_valid"] is True
        assert meta["real_api_call_performed"] is False
        assert meta["attempted_call_count"] == 1
        assert meta["successful_call_count"] == 1
        assert meta["raw_response_saved"] is False
        assert meta["batch"] is False

    def test_mock_default_output_contains_clauses(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        output = meta["output"]
        assert output is not None
        assert "clauses" in output
        assert isinstance(output["clauses"], list)
        assert len(output["clauses"]) >= 1

    def test_mock_default_normalizer_used(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["normalizer_used"] is True
        assert meta["normalizer_status"] == "accepted"

    def test_mock_default_source_id_preserved(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["source_id"] == sample_source_id
        assert meta["input_text"] == sample_text

    def test_mock_default_provider_model(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["provider"] == "mock"
        assert meta["model"] == "mock"


# ===========================================================================
# TestNonMockRefusal
# ===========================================================================


class TestNonMockRefusal:
    """Non-mock provider without --execute-real-api must be refused."""

    def test_openai_compatible_refused(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
            provider="openai_compatible",
            execute_real_api=False,
        )
        assert meta["error"] is not None
        assert "openai_compatible" in str(meta["error"])
        assert "requires --execute-real-api" in str(meta["error"])
        assert meta["real_api_call_performed"] is False
        assert meta["attempted_call_count"] == 0
        assert meta["successful_call_count"] == 0
        assert meta["raw_response_saved"] is False

    def test_unknown_provider_refused(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
            provider="unknown_provider",
            execute_real_api=False,
        )
        assert meta["error"] is not None
        assert meta["real_api_call_performed"] is False

    def test_disabled_provider_refused(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
            provider="disabled",
            execute_real_api=False,
        )
        assert meta["error"] is not None
        assert meta["real_api_call_performed"] is False


# ===========================================================================
# TestExecuteRealApiScaffoldRefusal
# ===========================================================================


class TestExecuteRealApiScaffoldRefusal:
    """--execute-real-api is accepted but refuses real execution (R11.3 scaffold)."""

    def test_execute_real_api_refused_with_mock(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
            provider="mock",
            execute_real_api=True,
        )
        assert meta["error"] is not None
        assert "R11.3 scaffold does not execute real API" in str(meta["error"])
        assert meta["real_api_call_performed"] is False
        assert meta["attempted_call_count"] == 0
        assert meta["successful_call_count"] == 0
        assert meta["raw_response_saved"] is False

    def test_execute_real_api_refused_with_openai_compatible(
        self, sample_source_id, sample_text
    ):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
            provider="openai_compatible",
            execute_real_api=True,
        )
        assert meta["error"] is not None
        assert "R11.3 scaffold does not execute real API" in str(meta["error"])
        assert meta["real_api_call_performed"] is False


# ===========================================================================
# TestErrorHandling
# ===========================================================================


class TestErrorHandling:
    """Error paths produce correct metadata."""

    def test_empty_text_rejected_by_schema(self, sample_source_id):
        """Empty text is rejected by schema validation (source_text must be non-empty)."""
        meta = run_single_call(
            source_id=sample_source_id,
            text="",
        )
        # Schema validation rejects empty source_text — this is correct behavior
        assert meta["error"] is not None
        assert meta["schema_valid"] is False
        assert meta["real_api_call_performed"] is False

    def test_very_long_text(self, sample_source_id):
        """Very long text should still work."""
        long_text = "The data controller shall " + "and shall ".join(
            f"do thing {i}" for i in range(100)
        )
        meta = run_single_call(
            source_id=sample_source_id,
            text=long_text,
        )
        assert meta["error"] is None

    def test_special_characters_in_text(self, sample_source_id):
        """Special characters in source_id and text should be handled."""
        meta = run_single_call(
            source_id="test-001_special",
            text='{"json": "like"} text with \\"quotes\\"',
        )
        assert meta["error"] is None
        assert meta["schema_valid"] is True


# ===========================================================================
# TestSafetyConstraints
# ===========================================================================


class TestSafetyConstraints:
    """Verify R11.3 safety constraints: no .env, no network, no raw response, no batch."""

    def test_no_env_read(self, sample_source_id, sample_text, monkeypatch):
        """Ensure run_single_call does not read .env."""
        env_read_count = [0]

        def _fake_load(*args, **kwargs):
            env_read_count[0] += 1
            return {}

        # Patch project env loading paths
        monkeypatch.setattr(
            "bpc_hybrid.llm_config.load_project_env_file", _fake_load
        )

        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        # The function should succeed without calling load_project_env_file
        assert meta["error"] is None
        # env_read_count should be 0 since we don't load .env in run_single_call
        assert env_read_count[0] == 0

    def test_no_raw_response_saved(self, sample_source_id, sample_text):
        """Metadata must assert raw_response_saved is False."""
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["raw_response_saved"] is False

    def test_no_batch(self, sample_source_id, sample_text):
        """Metadata must assert batch is False."""
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["batch"] is False

    def test_no_real_api_performed(self, sample_source_id, sample_text):
        """Metadata must assert real_api_call_performed is False."""
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["real_api_call_performed"] is False

    def test_no_network_import_side_effect(self, sample_source_id, sample_text, monkeypatch):
        """Ensure run_single_call does not cause network activity."""
        # Patch socket to detect any socket operations
        socket_operations = []

        original_socket = socket.socket

        def _tracking_socket(*args, **kwargs):
            socket_operations.append(("socket_create", args, kwargs))
            return original_socket(*args, **kwargs)

        monkeypatch.setattr(socket, "socket", _tracking_socket)

        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert meta["error"] is None
        # Mock transport should not touch socket
        assert len(socket_operations) == 0, (
            f"Unexpected socket operations: {socket_operations}"
        )


# ===========================================================================
# TestProgrammaticAPI
# ===========================================================================


class TestProgrammaticAPI:
    """run_single_call() is importable and callable directly."""

    def test_returns_dict(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        assert isinstance(meta, dict)

    def test_all_keys_present_in_success(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )
        required = [
            "source_id",
            "input_text",
            "provider",
            "model",
            "entrypoint",
            "real_api_call_performed",
            "attempted_call_count",
            "successful_call_count",
            "fallback_status",
            "schema_valid",
            "normalizer_used",
            "normalizer_status",
            "raw_response_saved",
            "secret_redacted",
            "batch",
        ]
        for key in required:
            assert key in meta, f"Missing key: {key}"

    def test_explicit_provider_model(self, sample_source_id, sample_text):
        meta = run_single_call(
            source_id=sample_source_id,
            text=sample_text,
            provider="mock",
            model="mock",
        )
        assert meta["provider"] == "mock"
        assert meta["model"] == "mock"

    def test_no_argument_side_effects(self, sample_source_id, sample_text):
        """Calling run_single_call should not mutate global state."""
        # Import a known constant and check it hasn't changed
        from scripts.run_single_call_schema_smoke import _METADATA_TEMPLATE as tmpl_before

        entrypoint_before = tmpl_before["entrypoint"]

        run_single_call(
            source_id=sample_source_id,
            text=sample_text,
        )

        from scripts.run_single_call_schema_smoke import _METADATA_TEMPLATE as tmpl_after

        assert tmpl_after["entrypoint"] == entrypoint_before
        assert tmpl_after["real_api_call_performed"] is False
        assert tmpl_after["batch"] is False


# ===========================================================================
# TestCLIIntegration
# ===========================================================================


class TestCLIIntegration:
    """CLI integration tests via subprocess (no real API)."""

    @staticmethod
    def _run_cli(*args: str) -> tuple[int, dict]:
        """Run the entrypoint script and return (exit_code, parsed_json).

        Tries stdout first, then stderr (argparse errors go to stderr).
        """
        cmd = [
            sys.executable,
            str(_ENTRYPOINT),
            *args,
        ]
        env = os.environ.copy()
        env["BPC_HYBRID_DISABLE_PROJECT_ENV"] = "1"

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        # Try stdout first, then stderr (argparse errors go to stderr)
        for stream in (proc.stdout, proc.stderr):
            stripped = stream.strip()
            if stripped:
                try:
                    data = json.loads(stripped)
                    return proc.returncode, data
                except json.JSONDecodeError:
                    continue
        return proc.returncode, {"stdout": proc.stdout, "stderr": proc.stderr}

    def test_cli_mock_default(self):
        exit_code, data = self._run_cli(
            "--source-id", "r11_3_cli_001",
            "--text", "A controller shall record the decision.",
        )
        assert exit_code == 0
        assert data.get("error") is None
        assert data.get("fallback_status") == "success"
        assert data.get("schema_valid") is True

    def test_cli_non_mock_refused(self):
        exit_code, data = self._run_cli(
            "--source-id", "r11_3_cli_002",
            "--text", "A controller shall record the decision.",
            "--provider", "openai_compatible",
        )
        assert exit_code == 1
        assert data.get("error") is not None
        assert "requires --execute-real-api" in str(data.get("error", ""))

    def test_cli_execute_real_api_refused(self):
        exit_code, data = self._run_cli(
            "--source-id", "r11_3_cli_003",
            "--text", "A controller shall record the decision.",
            "--execute-real-api",
        )
        assert exit_code == 1
        assert data.get("error") is not None
        assert "R11.3 scaffold does not execute real API" in str(data.get("error", ""))

    def test_cli_missing_source_id(self):
        exit_code, data = self._run_cli(
            "--text", "A controller shall record the decision.",
        )
        assert exit_code == 2
        # argparse error should be JSON
        assert "error" in data

    def test_cli_missing_text(self):
        exit_code, data = self._run_cli(
            "--source-id", "r11_3_cli_004",
        )
        assert exit_code == 2
        assert "error" in data

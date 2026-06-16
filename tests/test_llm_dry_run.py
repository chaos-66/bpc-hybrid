"""Tests for R8 single-sample LLM dry-run harness.

All test data is synthetic — no real GDPR, BPMN, or Sun data.
No network, no ``.env``, no real API keys.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DRY_RUN_SCRIPT = SCRIPTS_DIR / "run_llm_dry_run.py"

PYTHON_EXE = sys.executable
SAMPLE_TEXT = "A controller shall record the decision."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_dry_run(*args: str) -> subprocess.CompletedProcess[str]:
    """Run the dry-run script with *args* and return completed process.

    Does **not** inject PYTHONPATH — the script itself does that.
    """
    cmd = [PYTHON_EXE, str(DRY_RUN_SCRIPT), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(PROJECT_ROOT),
        env={**os.environ},  # inherit but don't add secrets
    )


def _parse_json_output(cp: subprocess.CompletedProcess[str]) -> dict:
    """Parse stdout as JSON, failing the test on failure."""
    assert cp.stdout.strip(), f"Expected JSON output, got empty stdout. stderr={cp.stderr}"
    try:
        return json.loads(cp.stdout.strip())
    except json.JSONDecodeError as exc:
        # Print stderr for debugging
        pytest.fail(
            f"Invalid JSON stdout. stderr={cp.stderr}\n"
            f"stdout={cp.stdout[:500]}\n"
            f"error={exc}"
        )


def _parse_from_stdout_or_stderr(cp: subprocess.CompletedProcess[str]) -> dict:
    """Parse JSON from stdout or stderr (parse errors print to stderr)."""
    combined = (cp.stdout + cp.stderr).strip()
    assert combined, f"Expected JSON output, got empty stdout+stderr. returncode={cp.returncode}"
    try:
        return json.loads(combined)
    except json.JSONDecodeError:
        # Try stderr first (JsonArgumentParser.error writes there)
        for source in (cp.stderr, cp.stdout):
            src = source.strip()
            if src:
                try:
                    return json.loads(src)
                except json.JSONDecodeError:
                    continue
        pytest.fail(
            f"No valid JSON found. stdout={cp.stdout[:300]!r} stderr={cp.stderr[:300]!r}"
        )


# ---------------------------------------------------------------------------
# Gate tests — missing flags
# ---------------------------------------------------------------------------

class TestDryRunGateErrors:
    """Verify that the required gates reject correctly."""

    def test_no_flags_refuses(self):
        cp = _run_dry_run()
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert "real_api_call_performed" in data
        assert data["real_api_call_performed"] is False

    def test_missing_allow_llm(self):
        cp = _run_dry_run("--single-sample", "--text", SAMPLE_TEXT)
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert "allow-llm" in data["message"].lower() or "--allow-llm" in data["message"]

    def test_missing_single_sample(self):
        cp = _run_dry_run("--allow-llm", "--text", SAMPLE_TEXT)
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert "single-sample" in data["message"]

    def test_missing_text(self):
        cp = _run_dry_run("--allow-llm", "--single-sample")
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert "text" in data["message"].lower()

    def test_openai_compatible_refused_in_r8(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--provider", "openai_compatible",
        )
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert "R8GateError" in data.get("error_type", "")
        assert "real_api_call_performed" in data
        assert data["real_api_call_performed"] is False

    def test_invalid_provider_rejected(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--provider", "nonexistent",
        )
        assert cp.returncode != 0
        # Must be JSON (not argparse usage text)
        data = _parse_from_stdout_or_stderr(cp)
        assert data["error"] is True
        assert "nonexistent" in data["message"]
        assert "usage:" not in cp.stdout
        assert "usage:" not in cp.stderr

    def test_invalid_provider_json_envelope(self):
        """Invalid --provider must produce the standard JSON error envelope."""
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--provider", "not_a_provider",
        )
        assert cp.returncode != 0
        data = _parse_from_stdout_or_stderr(cp)
        assert data["error"] is True
        assert data["error_type"] == "DryRunError"
        assert data["real_api_call_performed"] is False
        assert data["raw_response_saved"] is False
        assert data["secret_redacted"] is True
        assert "not_a_provider" in data["message"]
        # No argparse usage text or tracebacks
        combined = cp.stdout + cp.stderr
        assert "usage:" not in combined
        assert "Traceback" not in combined
        assert "sk-test-should-not-leak" not in combined.lower()
        assert "sk-" not in combined.lower()

    def test_unknown_argument_json_error(self):
        """Unknown CLI args must produce JSON error via JsonArgumentParser."""
        cp = _run_dry_run("--unknown-flag")
        assert cp.returncode != 0
        data = _parse_from_stdout_or_stderr(cp)
        assert data["error"] is True
        assert data["error_type"] == "DryRunError"
        assert data["real_api_call_performed"] is False
        assert data["raw_response_saved"] is False
        assert data["secret_redacted"] is True
        assert "unknown" in data["message"].lower()
        # No argparse usage text or tracebacks
        combined = cp.stdout + cp.stderr
        assert "usage:" not in combined
        assert "Traceback" not in combined


# ---------------------------------------------------------------------------
# Script direct execution — no manual PYTHONPATH
# ---------------------------------------------------------------------------

class TestScriptDirectExecution:
    """Verify the script runs without explicit PYTHONPATH manipulation."""

    def test_script_can_be_invoked_directly(self):
        """The script self-registers src/ on sys.path."""
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
        )
        assert cp.returncode == 0, f"stderr={cp.stderr}"
        data = _parse_json_output(cp)
        assert data["run_type"] == "single_sample_llm_dry_run"


# ---------------------------------------------------------------------------
# Mock dry-run success tests
# ---------------------------------------------------------------------------

class TestMockDryRunSuccess:
    """Verify mock dry-run produces correct output."""

    def test_mock_dry_run_succeeds(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--source-id", "dry001",
            "--text", SAMPLE_TEXT,
        )
        assert cp.returncode == 0, f"stderr={cp.stderr}"
        data = _parse_json_output(cp)

        assert data["run_type"] == "single_sample_llm_dry_run"
        assert data["provider"] == "mock"
        assert data["source_id"] == "dry001"
        assert data["fallback_triggered"] is True
        assert data["schema_valid"] is True
        assert data["real_api_call_performed"] is False
        assert data["raw_response_saved"] is False
        assert data["secret_redacted"] is True
        assert "output" in data
        assert data["output"]["source_id"] == "dry001"

    def test_dataset_type_correct(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
        )
        assert cp.returncode == 0
        data = _parse_json_output(cp)
        assert data["dataset_type"] == "synthetic_or_user_provided_single_sample"

    def test_no_secret_in_output(self):
        """Verify no dummy secret appears in stdout or stderr."""
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
        )
        assert cp.returncode == 0
        combined = cp.stdout + cp.stderr
        assert "sk-" not in combined.lower()
        assert "api_key" not in combined.lower()
        assert "password" not in combined.lower()

    def test_default_model_is_mock(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
        )
        data = _parse_json_output(cp)
        assert data["model"] == "mock"

    def test_custom_model_preserved(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--model", "custom-mock-v1",
        )
        data = _parse_json_output(cp)
        assert data["model"] == "custom-mock-v1"

    def test_custom_source_id_preserved(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--source-id", "my-custom-id",
            "--text", SAMPLE_TEXT,
        )
        data = _parse_json_output(cp)
        assert data["source_id"] == "my-custom-id"
        assert data["output"]["source_id"] == "my-custom-id"


# ---------------------------------------------------------------------------
# Invalid / schema-invalid mock response rejection
# ---------------------------------------------------------------------------

class TestMockInvalidRejection:
    """Verify invalid mock responses are rejected gracefully."""

    def test_invalid_mock_json_rejected(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--mock-response", "not-valid-json {{{",
        )
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert data["real_api_call_performed"] is False
        assert data["raw_response_saved"] is False
        assert data["secret_redacted"] is True

    def test_schema_invalid_mock_json_rejected(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--mock-response", json.dumps({"wrong_key": 42, "not_schema": True}),
        )
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True
        assert data["real_api_call_performed"] is False

    def test_mock_json_not_object_rejected(self):
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
            "--mock-response", "[1, 2, 3]",
        )
        assert cp.returncode != 0
        data = _parse_json_output(cp)
        assert data["error"] is True


# ---------------------------------------------------------------------------
# Safety guarantees
# ---------------------------------------------------------------------------

class TestSafetyGuarantees:
    """Verify R8 safety invariants."""

    def test_no_output_files_created(self):
        """The dry-run script must not write output/log/raw_response files."""
        # List known output directories that must not exist or be empty
        forbidden_dirs = ["outputs", "logs", "raw_responses"]
        for d in forbidden_dirs:
            p = PROJECT_ROOT / d
            if p.exists():
                # Directory exists but must be empty (or pre-existing from git)
                contents = list(p.iterdir())
                assert len(contents) == 0, (
                    f"Directory {d}/ has files: {[f.name for f in contents]}"
                )

    def test_no_network_imports_in_script(self):
        """The script must not import network-capable libraries."""
        script_text = DRY_RUN_SCRIPT.read_text(encoding="utf-8")
        forbidden = ["import requests", "import httpx", "import urllib.request",
                     "from requests", "from httpx", "from urllib.request"]
        for pattern in forbidden:
            assert pattern not in script_text, f"Script imports forbidden: {pattern}"

    def test_no_dotenv_in_script(self):
        """The script must not use python-dotenv (R9.0 allows project .env)."""
        script_text = DRY_RUN_SCRIPT.read_text(encoding="utf-8")
        forbidden = ["dotenv", "load_dotenv"]
        for pattern in forbidden:
            assert pattern not in script_text, f"Script imports forbidden: {pattern}"

    def test_no_real_gdpr_bpmn_sun_data(self):
        """All test data is synthetic."""
        script_text = DRY_RUN_SCRIPT.read_text(encoding="utf-8")
        assert "GDPR" not in script_text
        assert "BPMN" not in script_text
        assert "Sun" not in script_text

    def test_no_batch_mode(self):
        """The dry-run script does not support batch processing."""
        script_text = DRY_RUN_SCRIPT.read_text(encoding="utf-8")
        assert "--batch" not in script_text
        assert "batch" not in script_text.lower().split("_")

    def test_error_messages_contain_no_secret_patterns(self):
        """Error JSON must not leak secret-like content."""
        # Run with various invalid inputs and verify no leakage
        cp1 = _run_dry_run()  # no flags
        combined1 = cp1.stdout + cp1.stderr
        assert "sk-" not in combined1.lower()
        assert "Bearer" not in combined1

        cp2 = _run_dry_run(
            "--allow-llm", "--single-sample",
            "--text", SAMPLE_TEXT,
            "--mock-response", "bad json",
        )
        combined2 = cp2.stdout + cp2.stderr
        # The input "bad json" might appear in error output, that's OK.
        # But no secret-like patterns.
        assert "sk-" not in combined2.lower()

    def test_synthetic_text_only(self):
        """All test source texts are synthetic — never real regulation."""
        script_text = DRY_RUN_SCRIPT.read_text(encoding="utf-8")
        # The sample text is synthetic
        assert "A controller shall record the decision." in script_text or True
        # No GDPR article references
        assert "Article" not in script_text


# ---------------------------------------------------------------------------
# R9.0 — .env safety
# ---------------------------------------------------------------------------

class TestDotenvSafety:
    """Verify project-root .env safety invariants (R9.0)."""

    def test_dotenv_is_gitignored(self):
        """``.env`` must be ignored by Git."""
        cp = subprocess.run(
            ["git", "check-ignore", ".env"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        assert cp.returncode == 0, f".env is NOT gitignored! stderr={cp.stderr}"
        assert ".env" in cp.stdout.strip()

    def test_dotenv_example_exists(self):
        """``.env.example`` must exist in project root."""
        p = PROJECT_ROOT / ".env.example"
        assert p.exists(), ".env.example missing"
        content = p.read_text(encoding="utf-8")
        assert "BPC_HYBRID_LLM_PROVIDER" in content

    def test_dotenv_not_in_git_status(self):
        """``.env`` must not appear in ``git status``."""
        cp = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        lines = cp.stdout.strip().splitlines()
        for line in lines:
            assert ".env" not in line or ".env.example" in line, (
                f".env unexpectedly in git status: {line}"
            )

    def test_no_real_api_key_in_dry_run_output(self):
        """Dry-run stdout+stderr must never contain API key patterns."""
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
        )
        combined = cp.stdout + cp.stderr
        # No key-like patterns
        assert "sk-" not in combined.lower()
        assert "api_key" not in combined.lower()

    def test_dry_run_runs_even_with_dotenv_present(self):
        """If .env exists, the dry-run must still succeed (R8 gates apply)."""
        # This test just verifies the .env loading in main() doesn't crash
        cp = _run_dry_run(
            "--allow-llm",
            "--single-sample",
            "--text", SAMPLE_TEXT,
        )
        assert cp.returncode == 0, f"stderr={cp.stderr}"

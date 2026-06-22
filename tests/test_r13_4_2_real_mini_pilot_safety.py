"""
R13.4.2.3 Safety regressions for real mini-pilot runner gates.

Tests verify the runner enforces:
  1. Canonical closed metadata rejects --execute-real-api (no path override)
  2. --execution-contract is NOT accepted by CLI
  3. --authorization-checklist is NOT accepted by CLI
  4. _check_authorization_gate() can be unit-tested directly with fixture paths
  5. No bypass / force / ignore-authorization flags
  6. --max-calls > 8 rejected
  7. Missing --execute-real-api rejected
  8. Candidate count > 8 rejected (_validate_inputs unit test)
  9. sample_id mismatch rejected (_validate_inputs unit test)
  10. Non-reviewed_gold rejected (_validate_inputs unit test)
  11. Duplicate sample_ids rejected (_validate_inputs unit test)

CONSTRAINTS (R13.4.2.3):
  - NO network access
  - NO .env read
  - NO real API call
  - Subprocess calls for CLI-level tests
  - Direct function calls for internal gate / input validation tests
  - Fixture metadata ONLY for direct internal function calls (NOT via CLI)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Import internal runner functions for direct unit testing
# ---------------------------------------------------------------------------

_RUNNER_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(_RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(_RUNNER_DIR))

# Import from the runner module (safe -- no side effects on import)
from run_r13_4_2_real_mini_pilot import (  # noqa: E402
    _check_authorization_gate,
    _validate_inputs,
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _PROJECT_ROOT / "scripts" / "run_r13_4_2_real_mini_pilot.py"
_CANDIDATES = _PROJECT_ROOT / "data" / "formal" / "processed" / "r13_3_candidate_samples.jsonl"
_GOLD = _PROJECT_ROOT / "data" / "formal" / "gold" / "r13_3_manual_gold_template.jsonl"
_PYTHON = sys.executable


def _runner_cmd(*extra_args: str, predictions_out: str = "NUL") -> list[str]:
    """Build a runner subprocess arg list (no default input paths)."""
    return [
        _PYTHON,
        str(_RUNNER),
        "--predictions-out", predictions_out,
        *extra_args,
    ]


def _run(*extra_args: str) -> subprocess.CompletedProcess:
    """Run the runner in a subprocess with BPC_HYBRID_DISABLE_PROJECT_ENV=1.

    Default --candidates and --gold point to real 8-sample input files.
    Callers can override them by passing their own --candidates/--gold.
    """
    run_env = {
        "BPC_HYBRID_DISABLE_PROJECT_ENV": "1",
        "PATH": str(_PROJECT_ROOT / ".venv" / "Scripts"),
        "SYSTEMROOT": "C:\\Windows",
    }
    # Always include defaults — if caller overrides, argparse takes the last value
    all_args = [
        "--candidates", str(_CANDIDATES),
        "--gold", str(_GOLD),
        *extra_args,
    ]
    return subprocess.run(
        _runner_cmd(*all_args),
        capture_output=True,
        text=True,
        env=run_env,
        cwd=str(_PROJECT_ROOT),
    )


# ---------------------------------------------------------------------------
# JSON fixture helpers
# ---------------------------------------------------------------------------


def _write_contract(path: Path, overrides: dict | None = None) -> Path:
    """Write an execution contract JSON fixture."""
    data: dict = {
        "stage": "R13.4.2",
        "type": "real_mini_pilot_execution_contract",
        "status": "executed_single_bounded_run",
        "authorization_status": "authorized_for_single_bounded_run",
        "real_api_call_allowed_now": False,
        "requires_explicit_user_authorization_for_future_runs": True,
        "real_api_call_performed": True,
        "max_real_api_calls": 8,
        "attempted_call_count": 8,
        "one_attempt_per_sample": True,
        "retry_allowed": False,
        "repair_call_allowed": False,
        "batch_allowed": False,
        "raw_response_saved": False,
        "benchmark": False,
        "method_validation": False,
        "sun_reproduction": False,
        "input_candidates": str(_CANDIDATES),
        "input_gold": str(_GOLD),
    }
    if overrides:
        data.update(overrides)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _write_checklist(path: Path, overrides: dict | None = None) -> Path:
    """Write an authorization checklist JSON fixture."""
    data: dict = {
        "stage": "R13.4.2",
        "real_api_call_performed": True,
        "authorization_status": "authorized_for_single_bounded_run_completed",
        "authorized_now": False,
        "future_real_api_runs_require_new_authorization": True,
        "authorized_constraints": {
            "max_real_api_calls": 8,
            "one_attempt_per_sample": True,
            "retry_allowed": False,
            "repair_call_allowed": False,
            "batch_allowed": False,
            "raw_response_saved": False,
            "benchmark": False,
            "method_validation": False,
            "sun_reproduction": False,
        },
    }
    if overrides:
        data.update(overrides)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# ===========================================================================
# CLI-level tests (no metadata path overrides -- canonical only)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 1: canonical closed metadata rejects --execute-real-api
# ---------------------------------------------------------------------------


def test_canonical_closed_metadata_rejects_execute_real_api() -> None:
    """Runner exits 1 with AUTHORIZATION_GATE_CLOSED using canonical metadata."""
    result = _run("--execute-real-api")
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "AUTHORIZATION_GATE_CLOSED" in result.stderr


# ---------------------------------------------------------------------------
# Test 2: --execution-contract is NOT accepted by CLI
# ---------------------------------------------------------------------------


def test_cli_rejects_execution_contract_arg() -> None:
    """Runner exits with 'unrecognized arguments' for --execution-contract."""
    result = _run("--execution-contract", "fake.json")
    assert result.returncode != 0, f"stdout: {result.stdout} | stderr: {result.stderr}"
    assert "unrecognized arguments" in result.stderr.lower() or result.returncode == 2


# ---------------------------------------------------------------------------
# Test 3: --authorization-checklist is NOT accepted by CLI
# ---------------------------------------------------------------------------


def test_cli_rejects_authorization_checklist_arg() -> None:
    """Runner exits with 'unrecognized arguments' for --authorization-checklist."""
    result = _run("--authorization-checklist", "fake.json")
    assert result.returncode != 0, f"stdout: {result.stdout} | stderr: {result.stderr}"
    assert "unrecognized arguments" in result.stderr.lower() or result.returncode == 2


# ---------------------------------------------------------------------------
# Test 4: --max-calls > 8 rejected
# ---------------------------------------------------------------------------


def test_max_calls_exceeds_8() -> None:
    """Runner exits 1 when --max-calls > 8."""
    result = _run("--max-calls", "9", "--execute-real-api")
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "exceeds maximum 8" in result.stderr


# ---------------------------------------------------------------------------
# Test 5: missing --execute-real-api
# ---------------------------------------------------------------------------


def test_missing_execute_real_api() -> None:
    """Runner exits 1 when --execute-real-api not provided."""
    result = _run()
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "requires --execute-real-api" in result.stderr


# ---------------------------------------------------------------------------
# Test 6: no bypass / force / ignore-authorization flags
# ---------------------------------------------------------------------------


def test_no_bypass_flag() -> None:
    """Runner must have no bypass, force, or ignore-authorization flags."""
    source = _RUNNER.read_text(encoding="utf-8")
    assert "--bypass-auth" not in source
    assert "--bypass-authorization" not in source
    assert "--skip-authorization" not in source
    assert "--skip-gate" not in source
    assert "--force" not in source
    assert "--ignore-authorization" not in source
    assert "--ignore-authorization-contract" not in source
    # Ensure no "bypass" used as a flag
    bypass_lines = [l for l in source.lower().splitlines() if "bypass" in l]
    # "bypass" may appear only in test assertions / comments, not in argparse
    for line in bypass_lines:
        # Allow in comments and docstrings
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
            continue
        if "add_argument" in stripped and "bypass" in stripped:
            pytest.fail(f"Runner argparse appears to have a bypass flag: {stripped}")


# ===========================================================================
# Direct _check_authorization_gate() unit tests (fixture paths)
# ===========================================================================


# ---------------------------------------------------------------------------
# Gate test: both closed
# ---------------------------------------------------------------------------


def test_gate_direct_both_closed(tmp_path: Path) -> None:
    """_check_authorization_gate exits 1 when both contract+checklist closed."""
    contract = _write_contract(tmp_path / "c.json")
    checklist = _write_checklist(tmp_path / "ch.json")

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: contract real_api_call_allowed_now=false
# ---------------------------------------------------------------------------


def test_gate_direct_contract_not_allowed(tmp_path: Path) -> None:
    """_check_authorization_gate exits when contract is closed."""
    contract = _write_contract(
        tmp_path / "c.json",
        {"real_api_call_allowed_now": False},
    )
    checklist = _write_checklist(
        tmp_path / "ch.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: checklist authorized_now=false
# ---------------------------------------------------------------------------


def test_gate_direct_checklist_not_authorized(tmp_path: Path) -> None:
    """_check_authorization_gate exits when checklist is closed."""
    contract = _write_contract(
        tmp_path / "c.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "ch.json",
        {"authorized_now": False, "authorization_status": "authorized_for_single_bounded_run"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: retry_allowed=true rejected
# ---------------------------------------------------------------------------


def test_gate_direct_retry_allowed_true(tmp_path: Path) -> None:
    """_check_authorization_gate exits when retry_allowed is true."""
    contract = _write_contract(
        tmp_path / "c.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "retry_allowed": True,
        },
    )
    checklist = _write_checklist(
        tmp_path / "ch.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: benchmark=true rejected
# ---------------------------------------------------------------------------


def test_gate_direct_benchmark_true(tmp_path: Path) -> None:
    """_check_authorization_gate exits when benchmark is true."""
    contract = _write_contract(
        tmp_path / "c.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "benchmark": True,
        },
    )
    checklist = _write_checklist(
        tmp_path / "ch.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: raw_response_saved=true rejected
# ---------------------------------------------------------------------------


def test_gate_direct_raw_response_saved_true(tmp_path: Path) -> None:
    """_check_authorization_gate exits when raw_response_saved is true."""
    contract = _write_contract(
        tmp_path / "c.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "raw_response_saved": True,
        },
    )
    checklist = _write_checklist(
        tmp_path / "ch.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: missing contract file → AUTHORIZATION_GATE_BLOCKED
# ---------------------------------------------------------------------------


def test_gate_direct_missing_contract(tmp_path: Path) -> None:
    """_check_authorization_gate exits when contract file missing."""
    missing = tmp_path / "missing.json"
    checklist = _write_checklist(
        tmp_path / "ch.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(missing, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: missing checklist file → AUTHORIZATION_GATE_BLOCKED
# ---------------------------------------------------------------------------


def test_gate_direct_missing_checklist(tmp_path: Path) -> None:
    """_check_authorization_gate exits when checklist file missing."""
    contract = _write_contract(
        tmp_path / "c.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    missing = tmp_path / "missing.json"

    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, missing)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Gate test: canonical defaults work (production path)
# ---------------------------------------------------------------------------


def test_gate_no_args_uses_canonical() -> None:
    """_check_authorization_gate() with no args uses canonical closed metadata."""
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate()
    assert exc_info.value.code == 1


# ===========================================================================
# Direct _validate_inputs() unit tests
# ===========================================================================


# ---------------------------------------------------------------------------
# validate_inputs: candidate count > 8
# ---------------------------------------------------------------------------


def test_validate_inputs_candidate_count_exceeds_8() -> None:
    """_validate_inputs raises ValueError when candidates exceed 8."""
    candidates = [{"sample_id": f"extra_{i:03d}", "text": "t"} for i in range(9)]
    gold = [{"sample_id": f"extra_{i:03d}", "annotation_status": "reviewed_gold"}
            for i in range(9)]

    with pytest.raises(ValueError, match="exceeds max"):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# validate_inputs: sample_id mismatch
# ---------------------------------------------------------------------------


def test_validate_inputs_sample_id_mismatch() -> None:
    """_validate_inputs raises ValueError when IDs don't match."""
    candidates = [{"sample_id": "a_001", "source_id": "test", "text": "t"}]
    gold = [{"sample_id": "z_999", "annotation_status": "reviewed_gold"}]

    with pytest.raises(ValueError, match="do not match"):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# validate_inputs: non-reviewed_gold
# ---------------------------------------------------------------------------


def test_validate_inputs_non_reviewed_gold() -> None:
    """_validate_inputs raises ValueError for non-reviewed_gold."""
    candidates = [{"sample_id": "a_001", "source_id": "test", "text": "t"}]
    gold = [{"sample_id": "a_001", "annotation_status": "draft"}]

    with pytest.raises(ValueError, match="not reviewed_gold"):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# validate_inputs: duplicate sample_ids
# ---------------------------------------------------------------------------


def test_validate_inputs_duplicate_sample_ids() -> None:
    """_validate_inputs raises ValueError for duplicate sample_ids."""
    candidates = [
        {"sample_id": "dup_001", "source_id": "test", "text": "A"},
        {"sample_id": "dup_001", "source_id": "test", "text": "B"},
    ]
    gold = [
        {"sample_id": "dup_001", "annotation_status": "reviewed_gold"},
        {"sample_id": "dup_001", "annotation_status": "reviewed_gold"},
    ]

    with pytest.raises(ValueError, match="Duplicate"):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# validate_inputs: zero samples
# ---------------------------------------------------------------------------


def test_validate_inputs_zero_samples() -> None:
    """_validate_inputs raises ValueError for empty candidates."""
    with pytest.raises(ValueError, match="No samples"):
        _validate_inputs([], [])


# ---------------------------------------------------------------------------
# validate_inputs: gold count != candidate count
# ---------------------------------------------------------------------------


def test_validate_inputs_count_mismatch() -> None:
    """_validate_inputs raises ValueError when counts differ."""
    candidates = [
        {"sample_id": "a_001", "source_id": "test", "text": "A"},
        {"sample_id": "a_002", "source_id": "test", "text": "B"},
    ]
    gold = [{"sample_id": "a_001", "annotation_status": "reviewed_gold"}]

    with pytest.raises(ValueError, match="!="):
        _validate_inputs(candidates, gold)

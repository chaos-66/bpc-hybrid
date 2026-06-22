"""
R13.7.1 Safety regressions for Prompt B real mini-pilot runner gates.

Tests verify the runner enforces:
  1. Canonical closed metadata rejects --execute-real-api (no path override)
  2. --execution-contract is NOT accepted by CLI
  3. --authorization-checklist is NOT accepted by CLI
  4. _check_authorization_gate() unit-testable with fixture paths
  5. No bypass / force / ignore-authorization flags
  6. --max-calls > 8 rejected
  7. Missing --execute-real-api rejected
  8. Candidate count > 8 rejected (_validate_inputs unit test)
  9. sample_id mismatch rejected (_validate_inputs unit test)
  10. Non-reviewed_gold rejected (_validate_inputs unit test)
  11. Duplicate sample_ids rejected (_validate_inputs unit test)
  12. selected_prompt_id mismatch rejected (gate unit test)
  13. one_attempt_per_sample must be True (gate unit test)

CONSTRAINTS (R13.7.1):
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

from run_r13_7_prompt_b_real_mini_pilot import (  # noqa: E402
    _check_authorization_gate,
    _validate_inputs,
    MAX_CALLS,
    PROMPT_ID,
    STAGE,
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_RUNNER = _PROJECT_ROOT / "scripts" / "run_r13_7_prompt_b_real_mini_pilot.py"
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
    """Write an R13.7 execution contract JSON fixture."""
    data: dict = {
        "stage": STAGE,
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
        "selected_prompt_id": PROMPT_ID,
        "input_candidates": str(_CANDIDATES),
        "input_gold": str(_GOLD),
    }
    if overrides:
        data.update(overrides)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _write_checklist(path: Path, overrides: dict | None = None) -> Path:
    """Write an R13.7 authorization checklist JSON fixture."""
    data: dict = {
        "stage": STAGE,
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
            "selected_prompt_id": PROMPT_ID,
        },
        "max_8_calls_confirmed": True,
        "one_attempt_per_sample_confirmed": True,
        "no_retry_confirmed": True,
        "no_repair_call_confirmed": True,
        "no_batch_confirmed": True,
        "no_raw_response_saving_confirmed": True,
        "no_benchmark_claim_confirmed": True,
        "no_method_validation_claim_confirmed": True,
        "no_sun_reproduction_claim_confirmed": True,
        "selected_prompt_confirmed": True,
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
    assert result.returncode != 0, \
        f"stdout: {result.stdout} | stderr: {result.stderr}"
    assert "unrecognized arguments" in result.stderr.lower() \
        or result.returncode == 2


# ---------------------------------------------------------------------------
# Test 3: --authorization-checklist is NOT accepted by CLI
# ---------------------------------------------------------------------------


def test_cli_rejects_authorization_checklist_arg() -> None:
    """Runner exits with 'unrecognized arguments' for --authorization-checklist."""
    result = _run("--authorization-checklist", "fake.json")
    assert result.returncode != 0, \
        f"stdout: {result.stdout} | stderr: {result.stderr}"
    assert "unrecognized arguments" in result.stderr.lower() \
        or result.returncode == 2


# ---------------------------------------------------------------------------
# Test 4: --max-calls > 8 rejected
# ---------------------------------------------------------------------------


def test_cli_rejects_max_calls_exceeding_limit() -> None:
    """Runner rejects --max-calls > MAX_CALLS."""
    result = _run("--max-calls", "9")
    assert result.returncode != 0, f"stdout: {result.stdout} | stderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Test 5: missing --execute-real-api rejected
# ---------------------------------------------------------------------------


def test_cli_missing_execute_real_api_rejected() -> None:
    """Runner exits 1 without --execute-real-api."""
    result = _run("--max-calls", "8")
    assert result.returncode == 1, f"stdout: {result.stdout} | stderr: {result.stderr}"


# ---------------------------------------------------------------------------
# Test 6: no bypass / force / ignore-authorization flags exist
# ---------------------------------------------------------------------------


def test_cli_no_bypass_flag_accepted() -> None:
    """Runner rejects --bypass-authorization."""
    result = _run("--bypass-authorization")
    assert result.returncode != 0, \
        f"stdout: {result.stdout} | stderr: {result.stderr}"


def test_cli_no_force_flag_accepted() -> None:
    """Runner rejects --force."""
    result = _run("--force")
    assert result.returncode != 0, \
        f"stdout: {result.stdout} | stderr: {result.stderr}"


def test_cli_no_ignore_authorization_flag_accepted() -> None:
    """Runner rejects --ignore-authorization."""
    result = _run("--ignore-authorization")
    assert result.returncode != 0, \
        f"stdout: {result.stdout} | stderr: {result.stderr}"


# ===========================================================================
# Internal gate unit tests (with fixture metadata)
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 7: open contract + checklist passes gate
# ---------------------------------------------------------------------------


def test_gate_open_contract_and_open_checklist_passes(tmp_path: Path) -> None:
    """Gate passes when contract + checklist are both in authorized state."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    # Should not raise
    _check_authorization_gate(contract, checklist)


# ---------------------------------------------------------------------------
# Test 8: closed contract (executed) fails gate
# ---------------------------------------------------------------------------


def test_gate_executed_contract_fails(tmp_path: Path) -> None:
    """Gate fails when contract has status=executed_single_bounded_run and
    real_api_call_allowed_now=False."""
    contract = _write_contract(tmp_path / "contract.json")  # defaults = executed
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 9: closed checklist (completed) fails gate
# ---------------------------------------------------------------------------


def test_gate_completed_checklist_fails(tmp_path: Path) -> None:
    """Gate fails when checklist.authorization_status is completed."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(tmp_path / "checklist.json")  # defaults = completed
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 10: authorized_now=False fails gate
# ---------------------------------------------------------------------------


def test_gate_not_authorized_now_fails(tmp_path: Path) -> None:
    """Gate fails when checklist.authorized_now is False."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": False, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 11: max_real_api_calls > MAX_CALLS fails gate
# ---------------------------------------------------------------------------


def test_gate_max_calls_exceeds_limit_fails(tmp_path: Path) -> None:
    """Gate fails when contract.max_real_api_calls > MAX_CALLS."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "max_real_api_calls": 9,
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 12: selected_prompt_id mismatch fails gate
# ---------------------------------------------------------------------------


def test_gate_wrong_selected_prompt_id_fails(tmp_path: Path) -> None:
    """Gate fails when contract.selected_prompt_id != PROMPT_ID."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "selected_prompt_id": "r13_6_prompt_A",
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 13: missing selected_prompt_id fails gate
# ---------------------------------------------------------------------------


def test_gate_missing_selected_prompt_id_fails(tmp_path: Path) -> None:
    """Gate fails when contract has no selected_prompt_id field."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
        },
    )
    # Explicitly remove selected_prompt_id
    data = json.loads(contract.read_text(encoding="utf-8"))
    data.pop("selected_prompt_id", None)
    contract.write_text(json.dumps(data, indent=2), encoding="utf-8")
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 14: one_attempt_per_sample not True fails gate
# ---------------------------------------------------------------------------


def test_gate_one_attempt_per_sample_false_fails(tmp_path: Path) -> None:
    """Gate fails when contract.one_attempt_per_sample is not True."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "one_attempt_per_sample": False,
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Test 15: one_attempt_per_sample missing fails gate
# ---------------------------------------------------------------------------


def test_gate_missing_one_attempt_per_sample_fails(tmp_path: Path) -> None:
    """Gate fails when contract has no one_attempt_per_sample field."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
        },
    )
    data = json.loads(contract.read_text(encoding="utf-8"))
    data.pop("one_attempt_per_sample", None)
    contract.write_text(json.dumps(data, indent=2), encoding="utf-8")
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )
    with pytest.raises(SystemExit) as exc_info:
        _check_authorization_gate(contract, checklist)
    assert exc_info.value.code == 1


# ===========================================================================
# _validate_inputs unit tests
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 16: sample count > MAX_SAMPLES rejected
# ---------------------------------------------------------------------------


def test_validate_inputs_too_many_candidates() -> None:
    """_validate_inputs rejects > 8 candidates."""
    candidates = [{"sample_id": f"s{i:03d}"} for i in range(1, 10)]
    gold = [{"sample_id": f"s{i:03d}"} for i in range(1, 10)]
    with pytest.raises(ValueError):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# Test 17: sample_id mismatch rejected
# ---------------------------------------------------------------------------


def test_validate_inputs_sample_id_mismatch() -> None:
    """_validate_inputs rejects candidates/gold with mismatched sample_ids."""
    candidates = [{"sample_id": "s001"}, {"sample_id": "s002"}]
    gold = [{"sample_id": "s001"}, {"sample_id": "s003"}]
    with pytest.raises(ValueError):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# Test 18: non-reviewed_gold rejected
# ---------------------------------------------------------------------------


def test_validate_inputs_non_reviewed_gold() -> None:
    """_validate_inputs rejects gold items without review_status."""
    candidates = [{"sample_id": "s001", "review_status": "reviewed_gold"}]
    gold = [{"sample_id": "s001"}]  # missing review_status
    with pytest.raises(ValueError):
        _validate_inputs(candidates, gold)


# ---------------------------------------------------------------------------
# Test 19: duplicate sample_ids rejected
# ---------------------------------------------------------------------------


def test_validate_inputs_duplicate_samples() -> None:
    """_validate_inputs rejects duplicate sample_ids in candidates."""
    candidates = [
        {"sample_id": "s001", "review_status": "reviewed_gold"},
        {"sample_id": "s001", "review_status": "reviewed_gold"},
    ]
    gold = [
        {"sample_id": "s001", "review_status": "reviewed_gold"},
    ]
    with pytest.raises(ValueError):
        _validate_inputs(candidates, gold)

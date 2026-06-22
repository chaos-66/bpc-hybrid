"""
R13.4.2.2 Safety regressions for real mini-pilot runner gates.

Tests verify the runner enforces:
  1. Authorization contract gate (closed contract rejected)
  2. Authorization checklist gate (closed checklist rejected)
  3. Both closed → AUTHORIZATION_GATE_CLOSED
  4. --max-calls > 8 rejected
  5. Missing --execute-real-api rejected
  6. Candidate count > 8 rejected
  7. sample_id mismatch rejected
  8. Non-reviewed_gold rejected
  9. Duplicate sample_ids rejected
  10. No bypass flag exists

CONSTRAINTS (R13.4.2.2):
  - NO network access
  - NO .env read
  - NO real API call
  - Subprocess calls ONLY (no mutable import)
  - Temp JSON files for contract/checklist fixtures
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


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
    """Write a closed-gate execution contract JSON."""
    data = {
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
    """Write a closed-gate authorization checklist JSON."""
    data = {
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


# ---------------------------------------------------------------------------
# Test 1: closed-gate contract + checklist → AUTHORIZATION_GATE_CLOSED
# ---------------------------------------------------------------------------


def test_authorization_gate_closed_both(
    tmp_path: Path,
) -> None:
    """Runner exits 1 with AUTHORIZATION_GATE_CLOSED when both closed."""
    contract = _write_contract(tmp_path / "contract.json")
    checklist = _write_checklist(tmp_path / "checklist.json")

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "AUTHORIZATION_GATE_CLOSED" in result.stderr


# ---------------------------------------------------------------------------
# Test 2: contract authorized_now=false / real_api_call_allowed_now=false
# ---------------------------------------------------------------------------


def test_authorization_gate_contract_not_authorized(
    tmp_path: Path,
) -> None:
    """Runner exits 1 when contract.real_api_call_allowed_now is false."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": False},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "real_api_call_allowed_now is not true" in result.stderr


# ---------------------------------------------------------------------------
# Test 3: checklist authorized_now=false
# ---------------------------------------------------------------------------


def test_authorization_gate_checklist_not_authorized(
    tmp_path: Path,
) -> None:
    """Runner exits 1 when checklist.authorized_now is false."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": False, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "authorized_now is not true" in result.stderr


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
# Test 6: candidate count > 8 rejected (uses existing input validation)
# ---------------------------------------------------------------------------


def test_candidate_count_exceeds_8(tmp_path: Path) -> None:
    """Runner exits 1 when candidates exceed 8."""
    # Create 9 fake candidates
    cand_path = tmp_path / "candidates.jsonl"
    gold_path = tmp_path / "gold.jsonl"
    records = []
    for i in range(9):
        records.append({"sample_id": f"extra_{i:03d}", "source_id": "test", "text": "test"})
    cand_path.write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8"
    )
    gold_records = [
        {"sample_id": f"extra_{i:03d}", "annotation_status": "reviewed_gold"}
        for i in range(9)
    ]
    gold_path.write_text(
        "\n".join(json.dumps(r) for r in gold_records), encoding="utf-8"
    )

    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--candidates", str(cand_path),
        "--gold", str(gold_path),
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "exceeds max" in result.stderr


# ---------------------------------------------------------------------------
# Test 7: sample_id mismatch
# ---------------------------------------------------------------------------


def test_sample_id_mismatch(tmp_path: Path) -> None:
    """Runner exits 1 when candidate and gold sample_ids don't match."""
    cand_path = tmp_path / "candidates_mismatch.jsonl"
    gold_path = tmp_path / "gold_mismatch.jsonl"

    cand_path.write_text(
        json.dumps({"sample_id": "r13_3_candidate_001", "source_id": "gdpr_eurlex",
                     "text": "test"}) + "\n",
        encoding="utf-8",
    )
    gold_path.write_text(
        json.dumps({"sample_id": "r13_3_candidate_999", "annotation_status": "reviewed_gold"}) + "\n",
        encoding="utf-8",
    )

    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--candidates", str(cand_path),
        "--gold", str(gold_path),
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "do not match" in result.stderr


# ---------------------------------------------------------------------------
# Test 8: non-reviewed_gold rejected
# ---------------------------------------------------------------------------


def test_non_reviewed_gold(tmp_path: Path) -> None:
    """Runner exits 1 when gold annotation_status is not reviewed_gold."""
    cand_path = tmp_path / "candidates_nonreviewed.jsonl"
    gold_path = tmp_path / "gold_nonreviewed.jsonl"

    cand_path.write_text(
        json.dumps({"sample_id": "r13_3_candidate_001", "source_id": "gdpr_eurlex",
                     "text": "test"}) + "\n",
        encoding="utf-8",
    )
    gold_path.write_text(
        json.dumps({"sample_id": "r13_3_candidate_001", "annotation_status": "draft"}) + "\n",
        encoding="utf-8",
    )

    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--candidates", str(cand_path),
        "--gold", str(gold_path),
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "not reviewed_gold" in result.stderr


# ---------------------------------------------------------------------------
# Test 9: duplicate sample_ids
# ---------------------------------------------------------------------------


def test_duplicate_sample_ids(tmp_path: Path) -> None:
    """Runner exits 1 when candidates have duplicate sample_ids."""
    cand_path = tmp_path / "candidates_dup.jsonl"
    gold_path = tmp_path / "gold_dup.jsonl"

    lines = [
        json.dumps({"sample_id": "dup_001", "source_id": "test", "text": "A"}),
        json.dumps({"sample_id": "dup_001", "source_id": "test", "text": "B"}),
    ]
    cand_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    gold_lines = [
        json.dumps({"sample_id": "dup_001", "annotation_status": "reviewed_gold"}),
        json.dumps({"sample_id": "dup_001", "annotation_status": "reviewed_gold"}),
    ]
    gold_path.write_text("\n".join(gold_lines) + "\n", encoding="utf-8")

    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--candidates", str(cand_path),
        "--gold", str(gold_path),
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "Duplicate" in result.stderr


# ---------------------------------------------------------------------------
# Test 10: no bypass flag — runner has no hidden --bypass-auth flag
# ---------------------------------------------------------------------------


def test_no_bypass_flag() -> None:
    """Runner must not have a --bypass-auth or similar bypass flag."""
    source = _RUNNER.read_text(encoding="utf-8")
    assert "--bypass-auth" not in source
    assert "--skip-authorization" not in source
    assert "--skip-gate" not in source
    assert "bypass" not in source.lower().split()


# ---------------------------------------------------------------------------
# Test 11: contract constraints — retry_allowed=true rejected
# ---------------------------------------------------------------------------


def test_contract_retry_allowed_true_rejected(tmp_path: Path) -> None:
    """Runner exits 1 when contract.retry_allowed is true."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "retry_allowed": True,
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "retry_allowed must be false" in result.stderr


# ---------------------------------------------------------------------------
# Test 12: contract constraints — benchmark=true rejected
# ---------------------------------------------------------------------------


def test_contract_benchmark_true_rejected(tmp_path: Path) -> None:
    """Runner exits 1 when contract.benchmark is true."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "benchmark": True,
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "benchmark must be false" in result.stderr


# ---------------------------------------------------------------------------
# Test 13: contract constraints — raw_response_saved=true rejected
# ---------------------------------------------------------------------------


def test_contract_raw_response_saved_true_rejected(tmp_path: Path) -> None:
    """Runner exits 1 when contract.raw_response_saved is true."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {
            "real_api_call_allowed_now": True,
            "status": "authorized_for_single_bounded_run",
            "raw_response_saved": True,
        },
    )
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "raw_response_saved must be false" in result.stderr


# ---------------------------------------------------------------------------
# Test 14: missing contract file → AUTHORIZATION_GATE_BLOCKED
# ---------------------------------------------------------------------------


def test_missing_contract_file(tmp_path: Path) -> None:
    """Runner exits 1 when execution contract file is missing."""
    missing = tmp_path / "missing.json"
    checklist = _write_checklist(
        tmp_path / "checklist.json",
        {"authorized_now": True, "authorization_status": "authorized_for_single_bounded_run"},
    )

    result = _run(
        "--execution-contract", str(missing),
        "--authorization-checklist", str(checklist),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "AUTHORIZATION_GATE_BLOCKED" in result.stderr


# ---------------------------------------------------------------------------
# Test 15: missing checklist file → AUTHORIZATION_GATE_BLOCKED
# ---------------------------------------------------------------------------


def test_missing_checklist_file(tmp_path: Path) -> None:
    """Runner exits 1 when authorization checklist file is missing."""
    contract = _write_contract(
        tmp_path / "contract.json",
        {"real_api_call_allowed_now": True, "status": "authorized_for_single_bounded_run"},
    )
    missing = tmp_path / "missing.json"

    result = _run(
        "--execution-contract", str(contract),
        "--authorization-checklist", str(missing),
        "--execute-real-api",
    )
    assert result.returncode == 1, f"stderr: {result.stderr}"
    assert "AUTHORIZATION_GATE_BLOCKED" in result.stderr

"""Tests for reusing an exact-state full-test receipt."""

from __future__ import annotations

from types import SimpleNamespace

import audit_project


def test_receipt_matches_only_the_verified_active_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_project, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        audit_project,
        "VERIFICATION_RECEIPT",
        tmp_path / ".tmp" / "last_verified_tests.json",
    )
    active = tmp_path / "active.py"
    active.write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=first\n", encoding="utf-8")
    result = {
        "command": ["python", "-m", "pytest", "-q"],
        "returncode": 0,
        "passed": True,
        "output": "9 passed in 0.3s\n",
    }

    audit_project._write_verification_receipt(result)
    receipt = audit_project.load_matching_verification_receipt()

    assert receipt is not None
    assert receipt["source"] == "verified_receipt"
    assert receipt["output"] == "9 passed in 0.3s"

    # Secrets are deliberately excluded from the fingerprint and never loaded
    # by the check/log workflow.
    (tmp_path / ".env").write_text("SECRET=second\n", encoding="utf-8")
    assert audit_project.load_matching_verification_receipt() is not None

    active.write_text("VALUE = 2\n", encoding="utf-8")
    assert audit_project.load_matching_verification_receipt() is None


def test_failed_tests_do_not_leave_a_reusable_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_project, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(
        audit_project,
        "VERIFICATION_RECEIPT",
        tmp_path / ".tmp" / "last_verified_tests.json",
    )
    audit_project.VERIFICATION_RECEIPT.parent.mkdir(parents=True)
    audit_project.VERIFICATION_RECEIPT.write_text("{}\n", encoding="utf-8")

    audit_project._write_verification_receipt(
        {"command": [], "returncode": 1, "passed": False, "output": "1 failed"}
    )

    assert not audit_project.VERIFICATION_RECEIPT.exists()


def test_test_harness_forces_utf8_for_nested_windows_processes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(audit_project, "PROJECT_ROOT", tmp_path)
    observed = {}

    def fake_run(command, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="1 passed\n")

    monkeypatch.setattr(audit_project.subprocess, "run", fake_run)
    result = audit_project._run_tests()

    assert result["passed"] is True
    assert observed["encoding"] == "utf-8"
    assert observed["env"]["PYTHONUTF8"] == "1"

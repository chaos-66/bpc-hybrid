"""Tests for the append-only experiment-provenance recorder."""

from __future__ import annotations

import argparse
import json

import record_change


def _args() -> argparse.Namespace:
    return argparse.Namespace(
        purpose="test governance change",
        gold="audit_read_only",
        llm_api="not_called",
        artifacts="not_created_or_overwritten",
        notes="unit test",
        event_type="change",
        run_id="",
        stage="",
        method="",
        run_command="",
        manifest=[],
        result_summary="",
        run_status="not_applicable",
    )


def test_summary_extracts_pytest_terminal_line() -> None:
    output = "progress\n504 passed, 22 skipped in 30.38s\n"
    assert record_change._test_summary(output) == "504 passed, 22 skipped in 30.38s"


def test_build_event_captures_safety_and_blockers(monkeypatch) -> None:
    monkeypatch.setattr(record_change, "_changed_paths", lambda: [" M formal_experiment/README.md"])
    monkeypatch.setattr(record_change, "_git", lambda args: "abc123")
    audit = {
        "integrity_pass": True,
        "final_experiment_ready": False,
        "findings": {
            "blockers": [{"code": "route_not_locked"}],
            "warnings": [{"code": "development_only"}],
        },
    }
    tests = {"passed": True, "returncode": 0, "output": "2 passed in 0.1s"}

    event = record_change.build_event(_args(), audit, tests)

    assert event["integrity_pass"] is True
    assert event["final_experiment_ready"] is False
    assert event["blocker_codes"] == ["route_not_locked"]
    assert event["safety"]["gold"] == "audit_read_only"
    assert event["safety"]["llm_api"] == "not_called"
    assert event["git_dirty"] is True
    assert event["test_source"] == "fresh_run"


def test_append_event_writes_jsonl_and_human_log(tmp_path, monkeypatch) -> None:
    event_log = tmp_path / "EXPERIMENT_EVENTS.jsonl"
    human_log = tmp_path / "EXPERIMENT_LOG.md"
    human_log.write_text("# 实验日志\n", encoding="utf-8")
    monkeypatch.setattr(record_change, "EVENT_LOG", event_log)
    monkeypatch.setattr(record_change, "HUMAN_LOG", human_log)

    audit = {
        "integrity_pass": True,
        "final_experiment_ready": False,
        "findings": {"blockers": [], "warnings": []},
    }
    tests = {"passed": True, "returncode": 0, "output": "3 passed in 0.1s"}
    monkeypatch.setattr(record_change, "_changed_paths", lambda: [])
    monkeypatch.setattr(record_change, "_git", lambda args: "abc123")
    event = record_change.build_event(_args(), audit, tests)

    record_change.append_event(event)

    stored = json.loads(event_log.read_text(encoding="utf-8").strip())
    assert stored["purpose"] == "test governance change"
    human = human_log.read_text(encoding="utf-8")
    assert "test governance change" in human
    assert "3 passed in 0.1s" in human
    assert "事件类型：变更" in human
    assert "完整性通过：是" in human


def test_main_reuses_matching_receipt_without_duplicate_tests(monkeypatch) -> None:
    receipt = {
        "passed": True,
        "returncode": 0,
        "output": "7 passed in 0.2s",
        "source": "verified_receipt",
    }
    monkeypatch.setattr(record_change, "load_matching_verification_receipt", lambda: receipt)
    monkeypatch.setattr(
        record_change,
        "_run_tests",
        lambda: (_ for _ in ()).throw(AssertionError("tests must not run twice")),
    )
    monkeypatch.setattr(
        record_change,
        "collect_project_audit",
        lambda: {
            "integrity_pass": True,
            "final_experiment_ready": False,
            "findings": {"blockers": [], "warnings": []},
        },
    )
    monkeypatch.setattr(record_change, "append_event", lambda event: None)
    monkeypatch.setattr(
        record_change.argparse.ArgumentParser,
        "parse_args",
        lambda self: _args(),
    )

    assert record_change.main() == 0


def test_experiment_run_event_captures_reproducibility_fields(monkeypatch) -> None:
    args = _args()
    args.event_type = "experiment_run"
    args.run_id = "s2-b0-seed13"
    args.stage = "stage2"
    args.method = "sun_rule_only"
    args.run_status = "succeeded"
    args.run_command = "python scripts/run_sun_rule_only.py --seed 13"
    args.manifest = ["data/results/s2-b0-seed13/manifest.json"]
    args.result_summary = "macro_f1=0.71"
    monkeypatch.setattr(record_change, "_changed_paths", lambda: [])
    monkeypatch.setattr(record_change, "_git", lambda values: "abc123")
    audit = {
        "integrity_pass": True,
        "final_experiment_ready": False,
        "findings": {"blockers": [], "warnings": []},
    }
    tests = {"passed": True, "returncode": 0, "output": "2 passed in 0.1s"}

    event = record_change.build_event(args, audit, tests)

    assert event["event_type"] == "experiment_run"
    assert event["experiment"]["run_id"] == "s2-b0-seed13"
    assert event["experiment"]["method"] == "sun_rule_only"
    assert event["experiment"]["manifests"] == [
        "data/results/s2-b0-seed13/manifest.json"
    ]

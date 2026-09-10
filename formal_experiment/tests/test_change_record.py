"""Tests for the append-only experiment-provenance recorder."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

import record_change


def _args(**overrides) -> argparse.Namespace:
    ns = argparse.Namespace(
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
        fail_on_unexpected_dirty=False,
        expected_dirty_path=[],
        test_target=[],
        test_timeout_seconds=180,
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def test_summary_extracts_pytest_terminal_line() -> None:
    output = "progress\n504 passed, 22 skipped in 30.38s\n"
    assert record_change._test_summary(output) == "504 passed, 22 skipped in 30.38s"


def test_git_chinese_paths_survive_non_utf8_host_locale(tmp_path, monkeypatch) -> None:
    subprocess = record_change.subprocess
    subprocess.run(["git", "init", str(tmp_path)], check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    subprocess.run(["git", "-C", str(tmp_path), "config", "core.quotepath", "false"],
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    reviewed = tmp_path / "formal_experiment" / "人工确认结果.md"
    reviewed.parent.mkdir()
    reviewed.write_text("已确认\n", encoding="utf-8")
    monkeypatch.setattr(record_change, "WORKSPACE_ROOT", tmp_path)
    # Exercise real Git bytes while reproducing the Windows GBK default.
    monkeypatch.setattr(subprocess, "_text_encoding", lambda: "gbk")
    assert record_change._changed_paths() == ["?? formal_experiment/人工确认结果.md"]


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
        "_run_focused_tests",
        lambda *args: (_ for _ in ()).throw(AssertionError("tests must not run twice")),
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


def test_missing_receipt_refuses_without_tests_audit_or_log(monkeypatch, capsys):
    monkeypatch.setattr(record_change, "load_matching_verification_receipt", lambda: None)
    monkeypatch.setattr(record_change.argparse.ArgumentParser, "parse_args", lambda self: _args())
    def unexpected(*args, **kwargs):
        raise AssertionError("Missing receipt must not start work or write logs")
    for name in ("_run_focused_tests", "collect_project_audit", "append_event"):
        monkeypatch.setattr(record_change, name, unexpected)
    assert record_change.main() == 3
    assert "No tests were started" in capsys.readouterr().err


@pytest.mark.parametrize("target", ["tests", ".", "../test_escape.py", "--help", "tests/*.py"])
def test_focused_targets_reject_broad_or_escaping_selection(tmp_path, monkeypatch, target):
    monkeypatch.setattr(record_change, "FORMAL_ROOT", tmp_path)
    (tmp_path / "tests").mkdir()
    with pytest.raises(ValueError):
        record_change._focused_targets([target])


def test_focused_runner_uses_only_named_nodes_and_bounded_time(tmp_path, monkeypatch):
    monkeypatch.setattr(record_change, "FORMAL_ROOT", tmp_path)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_small.py").write_text("", encoding="utf-8")
    captured = {}
    def run(command, **kwargs):
        captured.update(command=command, **kwargs)
        return argparse.Namespace(returncode=0, stdout="1 passed in 0.01s")
    monkeypatch.setattr(record_change.subprocess, "run", run)
    result = record_change._run_focused_tests(["tests/test_small.py::test_one"])
    assert captured["command"][-1] == "tests/test_small.py::test_one"
    assert "tests" not in captured["command"]
    assert captured["timeout"] == 180
    assert result["scope"] == "focused"
    assert result["passed"] is True


def test_focused_timeout_is_recorded_as_failure_without_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(record_change, "FORMAL_ROOT", tmp_path)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_small.py").write_text("", encoding="utf-8")
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        raise record_change.subprocess.TimeoutExpired(command, kwargs["timeout"])
    monkeypatch.setattr(record_change.subprocess, "run", run)
    result = record_change._run_focused_tests(["tests/test_small.py"], 1)
    assert len(calls) == 1
    assert result["passed"] is False and result["returncode"] == 124
    assert "timed out" in record_change._test_summary(result["output"])


def test_focused_event_does_not_claim_full_suite(monkeypatch, tmp_path):
    selected = ["tests/test_change_record.py"]
    monkeypatch.setattr(record_change.argparse.ArgumentParser, "parse_args",
                        lambda self: _args(test_target=selected))
    monkeypatch.setattr(record_change, "_focused_targets", lambda values: values)
    monkeypatch.setattr(record_change, "_run_focused_tests", lambda targets, timeout: {
        "scope": "focused", "targets": targets, "command": ["pytest", *targets],
        "source": "fresh_run", "passed": True, "returncode": 0, "output": "1 passed",
    })
    monkeypatch.setattr(record_change, "load_matching_verification_receipt",
                        lambda: pytest.fail("Explicit focused selection must not load a full receipt"))
    monkeypatch.setattr(record_change, "collect_project_audit", lambda: {
        "integrity_pass": True, "final_experiment_ready": False,
        "findings": {"blockers": [], "warnings": []},
    })
    monkeypatch.setattr(record_change, "_changed_paths", lambda: [])
    monkeypatch.setattr(record_change, "_git", lambda args: "abc123")
    monkeypatch.setattr(record_change, "EVENT_LOG", tmp_path / "events.jsonl")
    monkeypatch.setattr(record_change, "HUMAN_LOG", tmp_path / "events.md")
    assert record_change.main() == 0
    event = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert event["test_scope"] == "focused" and event["test_targets"] == selected
    assert "相关测试（非全量）" in (tmp_path / "events.md").read_text(encoding="utf-8")


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


# ---------------------------------------------------------------------------
# B0-R1-A-C3 (2026-08-03): strict dirty-path gate tests.
# ---------------------------------------------------------------------------


def test_parse_porcelain_renames_and_unmerged(tmp_path) -> None:
    """Porcelain parser handles modified / untracked / renamed / unmerged
    lines and returns repo-relative paths without leaking content."""
    out = (
        " M formal_experiment/src/foo.py\n"
        "?? formal_experiment/docs/new.md\n"
        'R  formal_experiment/old/name.py -> formal_experiment/new/name.py\n'
        'R  "formal_experiment/with space/old.py" -> "formal_experiment/with space/new.py"\n'
        'UU formal_experiment/src/conflict.py\n'
    )
    paths = record_change._parse_porcelain_to_paths(out)
    assert "formal_experiment/src/foo.py" in paths
    assert "formal_experiment/docs/new.md" in paths
    assert "formal_experiment/new/name.py" in paths
    assert "formal_experiment/with space/new.py" in paths
    assert "formal_experiment/src/conflict.py" in paths


def test_enforce_expected_dirty_clean_and_exact() -> None:
    ok, msg = record_change._enforce_expected_dirty([], [])
    assert ok is True
    assert msg == "ok"
    ok, msg = record_change._enforce_expected_dirty(
        ["a.py", "b.py"], ["a.py", "b.py"]
    )
    assert ok is True


def test_enforce_expected_dirty_extra_rejected() -> None:
    ok, msg = record_change._enforce_expected_dirty(
        ["a.py", "b.py"], ["a.py"]
    )
    assert ok is False
    assert "extra=" in msg
    assert "b.py" in msg


def test_enforce_expected_dirty_missing_rejected() -> None:
    ok, msg = record_change._enforce_expected_dirty(
        ["a.py"], ["a.py", "b.py"]
    )
    assert ok is False
    assert "missing=" in msg
    assert "b.py" in msg


def test_strict_dirty_gate_clean_passes(
    monkeypatch, tmp_path: Path
) -> None:
    """When the tree is clean and the expected list is empty, the gate
    must allow the record to proceed and not write any forbidden state
    (no appended event)."""
    monkeypatch.setattr(record_change, "_git", lambda args: "")
    event_log = tmp_path / "EXPERIMENT_EVENTS.jsonl"
    human_log = tmp_path / "EXPERIMENT_LOG.md"
    human_log.write_text("# 实验日志\n", encoding="utf-8")
    monkeypatch.setattr(record_change, "EVENT_LOG", event_log)
    monkeypatch.setattr(record_change, "HUMAN_LOG", human_log)
    captured = {}
    monkeypatch.setattr(
        record_change,
        "append_event",
        lambda event: captured.setdefault("called", True),
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
    receipt = {
        "passed": True,
        "returncode": 0,
        "output": "1 passed in 0.1s",
        "source": "verified_receipt",
    }
    monkeypatch.setattr(record_change, "load_matching_verification_receipt", lambda: receipt)
    args = _args(
        purpose="c3 strict gate clean",
        fail_on_unexpected_dirty=True,
        expected_dirty_path=[],
    )
    monkeypatch.setattr(
        record_change.argparse.ArgumentParser,
        "parse_args",
        lambda self: args,
    )
    rc = record_change.main()
    assert rc == 0
    assert captured.get("called") is True
    # The strict gate must not have touched the log file in the
    # refusal path, but here we *did* record. We only assert that the
    # strict gate did not block.


def test_strict_dirty_gate_extra_rejected_no_log_write(
    monkeypatch, tmp_path: Path
) -> None:
    """When an unexpected extra path is dirty, the gate must refuse
    (exit non-zero) and must NOT have written to the log files."""
    monkeypatch.setattr(
        record_change, "_git", lambda args: " M unexpected.py\n"
    )
    event_log = tmp_path / "EXPERIMENT_EVENTS.jsonl"
    human_log = tmp_path / "EXPERIMENT_LOG.md"
    human_log.write_text("# 实验日志\n", encoding="utf-8")
    monkeypatch.setattr(record_change, "EVENT_LOG", event_log)
    monkeypatch.setattr(record_change, "HUMAN_LOG", human_log)
    append_called = {"value": False}
    monkeypatch.setattr(
        record_change,
        "append_event",
        lambda event: append_called.__setitem__("value", True),
    )
    args = _args(
        purpose="c3 strict gate extra",
        fail_on_unexpected_dirty=True,
        expected_dirty_path=["formal_experiment/.gitattributes"],
    )
    monkeypatch.setattr(
        record_change.argparse.ArgumentParser,
        "parse_args",
        lambda self: args,
    )
    rc = record_change.main()
    assert rc == 3
    assert append_called["value"] is False
    assert not event_log.exists() or event_log.read_text(encoding="utf-8") == ""
    # The human log must not have been touched either.
    assert human_log.read_text(encoding="utf-8") == "# 实验日志\n"


def test_strict_dirty_gate_missing_rejected_no_log_write(
    monkeypatch, tmp_path: Path
) -> None:
    """When a required expected path is not dirty, the gate must refuse
    (exit non-zero) without writing the log."""
    monkeypatch.setattr(
        record_change, "_git", lambda args: " M formal_experiment/.gitattributes\n"
    )
    event_log = tmp_path / "EXPERIMENT_EVENTS.jsonl"
    human_log = tmp_path / "EXPERIMENT_LOG.md"
    human_log.write_text("# 实验日志\n", encoding="utf-8")
    monkeypatch.setattr(record_change, "EVENT_LOG", event_log)
    monkeypatch.setattr(record_change, "HUMAN_LOG", human_log)
    append_called = {"value": False}
    monkeypatch.setattr(
        record_change,
        "append_event",
        lambda event: append_called.__setitem__("value", True),
    )
    args = _args(
        purpose="c3 strict gate missing",
        fail_on_unexpected_dirty=True,
        expected_dirty_path=[
            "formal_experiment/.gitattributes",
            "formal_experiment/src/formal_experiment/audit.py",
        ],
    )
    monkeypatch.setattr(
        record_change.argparse.ArgumentParser,
        "parse_args",
        lambda self: args,
    )
    rc = record_change.main()
    assert rc == 3
    assert append_called["value"] is False
    assert human_log.read_text(encoding="utf-8") == "# 实验日志\n"

"""Append an immutable experiment-provenance log event.

This command is offline.  It never loads ``.env``, calls an LLM, or edits Gold.
It records the caller's declared safety status together with verified test
evidence, blockers, Git commit, and relevant dirty paths.  When the exact active
state has already passed ``audit_project.py --with-tests``, its receipt can be
reused. Otherwise the caller must name focused test files explicitly. Missing
or stale receipts NEVER cause this command to launch the full suite.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


FORMAL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = FORMAL_ROOT.parent
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.audit import collect_project_audit
from audit_project import load_matching_verification_receipt


EVENT_LOG = FORMAL_ROOT / "docs" / "EXPERIMENT_EVENTS.jsonl"
HUMAN_LOG = FORMAL_ROOT / "docs" / "EXPERIMENT_LOG.md"

EVENT_TYPE_ZH = {
    "change": "变更",
    "experiment_run": "实验运行",
    "milestone": "里程碑",
}
TEST_SOURCE_ZH = {
    "fresh_run": "本次新运行",
    "verified_receipt": "同一文件状态的已验证凭证",
}
SAFETY_ZH = {
    "not_read_or_modified": "未读取或修改",
    "audit_read_only": "仅完整性检查读取",
    "authorized_format_only": "仅按授权调整格式",
    "authorized_human_review_import": "按授权导入人工审核",
    "not_called": "未调用",
    "authorized_called": "已授权调用",
    "not_created_or_overwritten": "未创建或覆盖",
    "created_no_overwrite": "新建且未覆盖",
    "authorized_overwrite": "已授权覆盖",
}
RUN_STATUS_ZH = {
    "succeeded": "成功",
    "failed": "失败",
    "partial": "部分完成",
    "not_applicable": "不适用",
}


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=WORKSPACE_ROOT,
        text=True,
        # Git emits UTF-8 paths when core.quotepath=false, including on a
        # Windows host whose default text codec is GBK.
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    # Strip only the trailing newline so leading spaces inside
    # porcelain status lines are preserved. Stripping the entire
    # output (as a previous version did) silently corrupted the
    # first line's status column.
    return completed.stdout.rstrip("\r\n") if completed.returncode == 0 else "unavailable"


def _changed_paths() -> list[str]:
    output = _git(
        [
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            "formal_experiment",
            "AGENTS.md",
            "README.md",
            ".gitignore",
        ]
    )
    if output == "unavailable":
        return []
    return [line for line in output.splitlines() if line.strip()]


def _parse_porcelain_to_paths(porcelain_output: str) -> list[str]:
    """Convert ``git status --porcelain=v1`` lines into repo-relative paths.

    The two-character status column is split off; for renames/copies the
    *destination* path is returned (after the ``->`` arrow). Whitespace
    inside paths is preserved; the result is a list of paths relative to
    the repository root, with the leading ``"`` / ``"`` markers of
    unmerged entries stripped.
    """
    paths: list[str] = []
    for line in porcelain_output.splitlines():
        if not line.strip():
            continue
        # Format: XY<space>PATH   (or XY<space>"OLD" -> "NEW" for renames)
        if len(line) < 4:
            continue
        path_field = line[3:]
        if " -> " in path_field:
            path_field = path_field.split(" -> ", 1)[1]
        path_field = path_field.strip().strip('"')
        if path_field:
            paths.append(path_field)
    return paths


def _enforce_expected_dirty(
    actual_paths: list[str], expected_paths: list[str]
) -> tuple[bool, str]:
    """Compare the actual dirty-path set against the expected set.

    Returns ``(ok, message)``. ``ok`` is False whenever the two sets
    differ; the message describes the missing / extra paths in a way that
    never reveals file contents.
    """
    actual_set = set(actual_paths)
    expected_set = set(expected_paths)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    if not missing and not extra:
        return True, "ok"
    parts: list[str] = []
    if missing:
        parts.append(f"missing={missing}")
    if extra:
        parts.append(f"extra={extra}")
    return False, "; ".join(parts)


def _test_summary(output: str) -> str:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if re.search(r"\b(passed|failed|error|errors)\b", stripped, re.IGNORECASE):
            return stripped
    return "test summary unavailable"


def _focused_targets(targets: list[str]) -> list[str]:
    """Allow explicit test files/node IDs, never directories, options or globs."""
    test_root = (FORMAL_ROOT / "tests").resolve()
    selected = []
    for target in targets:
        file_name, separator, node_id = target.partition("::")
        path = (FORMAL_ROOT / file_name).resolve()
        if (not path.is_relative_to(test_root) or not path.is_file()
                or path.suffix != ".py" or not path.name.startswith("test_")):
            raise ValueError(f"Name a test file under formal_experiment/tests: {target}")
        selected.append(path.relative_to(FORMAL_ROOT.resolve()).as_posix()
                        + (separator + node_id if separator else ""))
    if not selected:
        raise ValueError("At least one explicit test file or node ID is required")
    return list(dict.fromkeys(selected))


def _run_focused_tests(targets: list[str], timeout_seconds: int = 180) -> dict:
    selected = _focused_targets(targets)
    if timeout_seconds <= 0:
        raise ValueError("Test timeout must be positive")
    temporary_root = FORMAL_ROOT / ".tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="record-focused-", dir=temporary_root,
                                     ignore_cleanup_errors=True) as temporary:
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   "--basetemp", str(Path(temporary) / "pytest"), *selected]
        try:
            result = subprocess.run(command, cwd=FORMAL_ROOT, text=True,
                                    encoding="utf-8", errors="replace",
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    check=False, timeout=timeout_seconds)
            returncode, output = result.returncode, result.stdout
        except subprocess.TimeoutExpired:
            returncode = 124
            output = f"ERROR: focused tests timed out after {timeout_seconds}s; no wider tests started"
    return {"command": command, "targets": selected, "scope": "focused",
            "source": "fresh_run", "returncode": returncode,
            "passed": returncode == 0, "output": output}


def build_event(args: argparse.Namespace, audit: dict, tests: dict) -> dict:
    changed = _changed_paths()
    event_type = getattr(args, "event_type", "change")
    event = {
        "schema_version": "1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "purpose": args.purpose,
        "command": "python formal_experiment/scripts/record_change.py",
        "integrity_pass": bool(audit["integrity_pass"] and tests["passed"]),
        "final_experiment_ready": bool(audit["final_experiment_ready"]),
        "test_returncode": tests["returncode"],
        "test_summary": _test_summary(str(tests["output"])),
        "test_source": tests.get("source", "fresh_run"),
        "test_scope": tests.get("scope", "full"),
        "test_command": tests.get("command", []),
        "test_targets": tests.get("targets", []),
        "blocker_codes": [item["code"] for item in audit["findings"]["blockers"]],
        "warning_codes": [item["code"] for item in audit["findings"]["warnings"]],
        "git_commit": _git(["rev-parse", "HEAD"]),
        "git_dirty": bool(changed),
        "changed_paths": changed,
        "safety": {
            "gold": args.gold,
            "llm_api": args.llm_api,
            "artifacts": args.artifacts,
        },
        "notes": args.notes,
    }
    if event_type == "experiment_run":
        event["experiment"] = {
            "run_id": args.run_id,
            "stage": args.stage,
            "method": args.method,
            "status": args.run_status,
            "run_command": args.run_command,
            "manifests": list(args.manifest),
            "result_summary": args.result_summary,
        }
    return event


def append_event(event: dict) -> None:
    EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    blockers = "、".join(event["blocker_codes"]) or "无"
    event_type = event.get("event_type", "change")
    test_source = event.get("test_source", "fresh_run")
    yes_no = lambda value: "是" if value else "否"
    safety = event["safety"]
    entry = [
        "",
        f"## {event['timestamp_utc']} - {event['purpose']}",
        "",
        f"- 事件类型：{EVENT_TYPE_ZH.get(event_type, event_type)}（`{event_type}`）",
        f"- 命令：`{event['command']}`",
        f"- 完整性通过：{yes_no(event['integrity_pass'])}；正式实验就绪：{yes_no(event['final_experiment_ready'])}",
        f"- 测试：{event['test_summary']}",
        f"- 测试范围：{'相关测试（非全量）' if event.get('test_scope') == 'focused' else '全量测试'}",
        f"- 测试证据：{TEST_SOURCE_ZH.get(test_source, test_source)}（`{test_source}`）",
        f"- Git：`{event['git_commit']}`；相关未提交路径：{len(event['changed_paths'])} 个",
        f"- Gold：{SAFETY_ZH.get(safety['gold'], safety['gold'])}（`{safety['gold']}`）；"
        f"LLM/API：{SAFETY_ZH.get(safety['llm_api'], safety['llm_api'])}（`{safety['llm_api']}`）；"
        f"产物：{SAFETY_ZH.get(safety['artifacts'], safety['artifacts'])}（`{safety['artifacts']}`）",
        f"- 仍存在 blocker：{blockers}",
        f"- 备注：{event['notes'] or '无'}",
        "- 机器实验事件：`docs/EXPERIMENT_EVENTS.jsonl`",
    ]
    if event.get("event_type") == "experiment_run":
        experiment = event["experiment"]
        entry[4:4] = [
            f"- 实验：run_id={experiment['run_id']}；阶段={experiment['stage']}；方法={experiment['method']}；"
            f"状态={RUN_STATUS_ZH.get(experiment['status'], experiment['status'])}（`{experiment['status']}`）",
            f"- 实际运行命令：`{experiment['run_command']}`",
            f"- manifest：{', '.join(experiment['manifests']) or '无'}",
            f"- 结果摘要：{experiment['result_summary'] or '无'}",
        ]
    with HUMAN_LOG.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purpose", required=True, help="Short description of the completed change")
    parser.add_argument(
        "--gold",
        required=True,
        choices=("not_read_or_modified", "audit_read_only", "authorized_format_only", "authorized_human_review_import"),
    )
    parser.add_argument(
        "--llm-api",
        required=True,
        choices=("not_called", "authorized_called"),
    )
    parser.add_argument(
        "--artifacts",
        required=True,
        choices=("not_created_or_overwritten", "created_no_overwrite", "authorized_overwrite"),
    )
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--test-target", action="append", default=[],
        help="Run only this explicit tests/test_*.py file or node ID, relative to formal_experiment; repeatable. Never runs directories or the full suite.",
    )
    parser.add_argument(
        "--test-timeout-seconds", type=int, default=180,
        help="Total focused-test timeout (default 180s); no automatic retries or expansion.",
    )
    parser.add_argument(
        "--event-type",
        choices=("change", "experiment_run", "milestone"),
        default="change",
        help="Log a code/design change, an actual experiment run, or a milestone.",
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument("--stage", default="")
    parser.add_argument("--method", default="")
    parser.add_argument("--run-command", default="")
    parser.add_argument("--manifest", action="append", default=[])
    parser.add_argument("--result-summary", default="")
    parser.add_argument(
        "--run-status",
        choices=("succeeded", "failed", "partial", "not_applicable"),
        default="not_applicable",
    )
    # Strict dirty-path gate (B0-R1-A-C3, 2026-08-03). When enabled,
    # the recorder refuses to append a new event unless the current
    # ``git status --porcelain`` path set exactly matches the
    # ``--expected-dirty-path`` allowlist. Any extra path or any
    # missing path causes an immediate non-zero exit *before* any
    # log file is touched. Default behavior is unchanged.
    parser.add_argument(
        "--fail-on-unexpected-dirty",
        action="store_true",
        help="Require the porcelain dirty-path set to match --expected-dirty-path exactly.",
    )
    parser.add_argument(
        "--expected-dirty-path",
        action="append",
        default=None,
        help="Repo-relative path that MUST be dirty. Repeatable. Only meaningful with --fail-on-unexpected-dirty. "
        "An empty list means 'clean tree'.",
    )
    args = parser.parse_args()
    if args.expected_dirty_path is None:
        args.expected_dirty_path = []
    # Drop any empty-string entries the user may have used as a
    # placeholder; they are not valid repo-relative paths.
    args.expected_dirty_path = [p for p in args.expected_dirty_path if p]
    if args.event_type == "experiment_run":
        missing = [
            name
            for name, value in (
                ("--run-id", args.run_id),
                ("--stage", args.stage),
                ("--method", args.method),
                ("--run-command", args.run_command),
            )
            if not value
        ]
        if args.run_status == "not_applicable":
            missing.append("--run-status")
        if missing:
            parser.error(
                "experiment_run requires " + ", ".join(missing)
            )

    # Strict dirty-path gate is enforced BEFORE the audit / tests run
    # so the strict refusal is observable even if the audit itself
    # would otherwise pass.
    if args.fail_on_unexpected_dirty:
        porcelain = _git(
            [
                "status",
                "--porcelain=v1",
                "--untracked-files=all",
                "--",
                "formal_experiment",
                "AGENTS.md",
                "README.md",
                ".gitignore",
            ]
        )
        if porcelain == "unavailable":
            print("strict dirty-path gate: git status unavailable; refusing to record", file=sys.stderr)
            return 3
        actual_paths = _parse_porcelain_to_paths(porcelain)
        ok, diff_message = _enforce_expected_dirty(actual_paths, args.expected_dirty_path)
        if not ok:
            print(
                f"strict dirty-path gate failed: {diff_message}",
                file=sys.stderr,
            )
            return 3

    targets = getattr(args, "test_target", [])
    if targets:
        try:
            # Validate before launching tests or writing the event.
            targets = _focused_targets(targets)
            timeout = getattr(args, "test_timeout_seconds", 180)
            if timeout <= 0:
                raise ValueError("Test timeout must be positive")
        except ValueError as exc:
            parser.error(str(exc))
        tests = _run_focused_tests(targets, timeout)
    else:
        tests = load_matching_verification_receipt()
        if tests is None:
            print("No matching test receipt. No tests were started and no event was written. "
                  "For experiment code, specify --test-target tests/test_example.py. "
                  "For artifact/document-only work, use the scoped Git commit. "
                  "Full tests require separate explicit user authorization.", file=sys.stderr)
            return 3
        tests = {**tests, "scope": "full"}
        print("Reusing matching full-test receipt; no tests started.")
    audit = collect_project_audit()
    event = build_event(args, audit, tests)
    append_event(event)

    print(f"Recorded experiment-provenance event: {EVENT_LOG}")
    print(f"Integrity pass: {event['integrity_pass']}")
    print(f"Final experiment ready: {event['final_experiment_ready']}")
    print(f"Tests: {event['test_summary']}")
    print(f"Test scope: {event['test_scope']}")
    if not tests["passed"]:
        print(str(tests["output"]).rstrip(), file=sys.stderr)
    return 0 if event["integrity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Append an immutable experiment-provenance log event.

This command is offline.  It never loads ``.env``, calls an LLM, or edits Gold.
It records the caller's declared safety status together with verified test
evidence, blockers, Git commit, and relevant dirty paths.  When the exact active
state has already passed ``audit_project.py --with-tests``, the matching receipt
is reused instead of running the same suite twice.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


FORMAL_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = FORMAL_ROOT.parent
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.audit import collect_project_audit
from audit_project import _run_tests, load_matching_verification_receipt


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
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unavailable"


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


def _test_summary(output: str) -> str:
    for line in reversed(output.splitlines()):
        stripped = line.strip()
        if re.search(r"\b(passed|failed|error|errors)\b", stripped):
            return stripped
    return "test summary unavailable"


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
    args = parser.parse_args()
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

    audit = collect_project_audit()
    tests = load_matching_verification_receipt()
    if tests is None:
        print("No matching verification receipt; running the offline tests once.")
        tests = _run_tests()
        tests["source"] = "fresh_run"
    else:
        print("Reusing the matching verified-test receipt; no duplicate test run.")
    event = build_event(args, audit, tests)
    append_event(event)

    print(f"Recorded experiment-provenance event: {EVENT_LOG}")
    print(f"Integrity pass: {event['integrity_pass']}")
    print(f"Final experiment ready: {event['final_experiment_ready']}")
    print(f"Tests: {event['test_summary']}")
    return 0 if event["integrity_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

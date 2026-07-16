"""目录整理、中文日志和退役边界的离线回归测试。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chinese_navigation_and_logs_are_canonical() -> None:
    required = (
        ROOT / "docs/DIRECTORY_GUIDE.md",
        ROOT / "docs/AGENT_RUNBOOK.md",
        ROOT / "docs/FILE_CATALOG.md",
        ROOT / "docs/EXPERIMENT_LOG.md",
        ROOT / "docs/EXPERIMENT_EVENTS.jsonl",
        ROOT / "_retired/README.md",
        ROOT / "_retired/MANIFEST.md",
        ROOT / "paper/README.md",
        ROOT / "paper/THESIS_DRAFT.md",
        ROOT / "paper/CLAIM_EVIDENCE_MATRIX.md",
    )
    assert all(path.is_file() for path in required)
    assert not (ROOT / "docs/AUDIT_LOG.md").exists()
    assert not (ROOT / "docs/AUDIT_EVENTS.jsonl").exists()


def test_machine_event_history_was_not_lost() -> None:
    events = ROOT / "docs/EXPERIMENT_EVENTS.jsonl"
    assert len([line for line in events.read_text(encoding="utf-8").splitlines() if line]) >= 29
    legacy_human = ROOT / "_retired/logs/AUDIT_LOG_legacy_through_event_29.md"
    assert legacy_human.is_file()


def test_retired_material_is_not_imported_by_active_python() -> None:
    for base in (ROOT / "src", ROOT / "scripts"):
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "from _retired" not in text
            assert "import _retired" not in text


def test_catalog_does_not_expose_secret_or_cache_paths() -> None:
    catalog = (ROOT / "docs/FILE_CATALOG.md").read_text(encoding="utf-8")
    assert "docs/FILE_CATALOG.md" in catalog
    assert "| `.env` |" not in catalog
    assert "| `.pytest_cache/" not in catalog
    assert "| `__pycache__/" not in catalog
    assert "| `.tmp/" not in catalog


def test_retired_manifest_covers_every_retired_file() -> None:
    manifest = (ROOT / "_retired/MANIFEST.md").read_text(encoding="utf-8")
    unlisted = []
    for path in (ROOT / "_retired").rglob("*"):
        if not path.is_file() or path.name in {"README.md", "MANIFEST.md"}:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if relative not in manifest:
            unlisted.append(relative)
    assert unlisted == []


def test_generated_file_catalog_matches_current_file_set() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/generate_file_catalog.py"), "--check"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout


def test_agent_prompts_preserve_stage_and_human_gold_boundaries() -> None:
    runbook = (ROOT / "docs/AGENT_RUNBOOK.md").read_text(encoding="utf-8")
    assert "S2.1-A" in runbook
    assert "S2.1-B" in runbook
    assert "S2.1-C" in runbook
    assert "S2.1-D" in runbook
    assert "一次只推进一个最小任务 ID" in runbook
    assert "人工审核 S2.2 由用户独占" in runbook
    assert "不得调用真实 LLM/API" in runbook
    assert "Agent-P1" in runbook


def test_paper_draft_has_claim_gates_and_no_fabricated_result_rows() -> None:
    draft = (ROOT / "paper/THESIS_DRAFT.md").read_text(encoding="utf-8")
    claims = (ROOT / "paper/CLAIM_EVIDENCE_MATRIX.md").read_text(encoding="utf-8")
    assert "DRAFT — 已启动写作，但无正式实验结果" in draft
    assert "[[TODO-RESULT:S2.10" in draft
    assert "| B0 | TEMPLATE | —" in draft
    assert "BLOCKED_RESULT" in claims
    assert "PROHIBITED_CLAIM" in claims
    assert "当前正式实验结果**：0" in claims


def test_external_chatgpt_entry_reuses_canonical_project_sources() -> None:
    readme = (ROOT / "paper/README.md").read_text(encoding="utf-8")
    required = (
        "外部 ChatGPT 的 GitHub 入口",
        "formal_experiment/AGENTS.md",
        "formal_experiment/configs/experiment_contract.json",
        "formal_experiment/docs/MASTER_PIPELINE.md",
        "formal_experiment/docs/PROJECT_AUDIT.md",
        "formal_experiment/docs/EXPERIMENT_LOG.md",
        "formal_experiment/paper/CLAIM_EVIDENCE_MATRIX.md",
        "formal_experiment/paper/THESIS_DRAFT.md",
        "commit SHA",
        "尚未完成仓库同步",
        "不是秒级实时共享",
    )
    for marker in required:
        assert marker in readme, marker
    assert "paper_handoff" not in readme.lower()
    assert "不得把历史对话记忆当作项目现状" in readme
    assert "没有 `experiment_run` 事件和 formal manifest" in readme


def test_active_review_route_descriptions_point_to_v2_and_exact_whitelist() -> None:
    paths = (ROOT / "configs/paths.json").read_text(encoding="utf-8")
    annotation = (ROOT / "docs/ANNOTATION_PROTOCOL.md").read_text(encoding="utf-8")
    data_map = (ROOT / "docs/ESTG150_DATA_MAP.md").read_text(encoding="utf-8")
    route = (ROOT / "docs/ROUTE_LOCK.md").read_text(encoding="utf-8")
    assert '"active_human_correction"' in paths
    assert '"legacy_human_review_pack"' in paths
    assert "v2 Layer E 输入门已就绪" in annotation
    assert "estg_150_human_correction_v1.json" in data_map
    assert "allowed_publication_statuses" in route
    assert "不以 `blocked_` 开头" not in route

"""Governance checks for the single roadmap and the cleaned document layout.

The test is offline and only reads repository files.  It prevents future agents
from silently reintroducing competing status/pipeline documents at docs/ root.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


def test_master_pipeline_is_agent_required_and_machine_required() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    audit_source = (ROOT / "src/formal_experiment/audit.py").read_text(
        encoding="utf-8"
    )

    assert "1. `docs/MASTER_PIPELINE.md`" in agents
    assert 'REPO_ROOT / "docs/MASTER_PIPELINE.md"' in audit_source
    assert 'REPO_ROOT / "docs/INDEX.md"' in audit_source
    assert 'REPO_ROOT / "docs/AGENT_RUNBOOK.md"' in audit_source


def test_master_pipeline_covers_the_complete_three_stage_wbs() -> None:
    pipeline = (DOCS / "MASTER_PIPELINE.md").read_text(encoding="utf-8")

    required_markers = (
        "```mermaid",
        "Stage 1",
        "Stage 2",
        "Stage 3",
        "S1.7",
        "S2.13",
        "S3.11",
        "B0 / `sun_rule_only`",
        "H1 / `sun_llm_fallback`",
        "D1 / `direct_llm`",
        "Oracle Stage 3",
        "end-to-end",
        "Definition of Done",
    )
    for marker in required_markers:
        assert marker in pipeline, marker


def test_docs_root_has_no_competing_pipeline_status_or_handoff() -> None:
    assert [path.name for path in DOCS.glob("*PIPELINE*.md")] == [
        "MASTER_PIPELINE.md"
    ]
    assert not list(DOCS.glob("*STATUS*.md"))
    assert not list(DOCS.glob("*HANDOFF*.md"))


def test_superseded_docs_are_preserved_in_retired_archive() -> None:
    history = ROOT / "_retired/docs/2026-07"
    expected = {
        "CURRENT_HANDOFF_2026-07-12.md",
        "STATUS_REPORT.md",
        "STATUS_SNAPSHOT_2026-07-12.md",
        "REORGANIZATION_PLAN.md",
        "SUN2024_FINAL_GAP_AND_ROADMAP.md",
    }

    assert expected <= {path.name for path in history.iterdir() if path.is_file()}
    assert all(not (DOCS / name).exists() for name in expected)
    assert not (DOCS / "history").exists()
    assert not (DOCS / "changes").exists()


def test_research_evidence_has_a_dedicated_directory() -> None:
    research = DOCS / "research"
    expected = {
        "SUN_BASELINE_AUDIT.md",
        "SUN_FINAL_VERSION_AND_DATA_AUDIT.md",
        "SUN_WINTER_CODE_SEPARATION_AUDIT.md",
        "BARRIENTOS_BORROWING_AUDIT_2026-07-12.md",
    }

    assert expected <= {path.name for path in research.iterdir() if path.is_file()}


def test_governance_is_log_first_and_does_not_duplicate_full_tests() -> None:
    protocol = (DOCS / "AI_CHANGE_PROTOCOL.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "实验日志（主制度）" in protocol
    assert "自动完整性检查（护栏）" in protocol
    assert "正式里程碑复核" in protocol
    assert "正常流程只跑一遍全量" in protocol
    assert "not institutional or" in agents
    assert "the full suite is not run twice" in agents
    assert "docs/EXPERIMENT_LOG.md" in agents
    assert "docs/DIRECTORY_GUIDE.md" in agents
    assert "docs/AGENT_RUNBOOK.md" in agents


def test_paper_writing_track_starts_without_unlocking_results() -> None:
    pipeline = (DOCS / "MASTER_PIPELINE.md").read_text(encoding="utf-8")
    project = (DOCS / "PROJECT_AUDIT.md").read_text(encoding="utf-8")

    for marker in ("PW0", "PW1", "PW9", "论文并行轨道", "结果/结论 blocked"):
        assert marker in pipeline
    assert "Agent-E1" in project
    assert "Agent-P1" in project
    assert "S2.1-A" in project

# -*- coding: utf-8 -*-
"""Regression tests for the Stage 3 Gold review tool and the blank pack
context embedding (rule_text).

Covers: rule_text embedded from the read-only Winter regulations, correction
pack creation, full stdin adjudication reaching freeze_ready, skip/quit
behavior, and the verifier's rule_text check.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bpc_hybrid.stage1_formal_dataset import Stage1FormalDatasetError  # noqa: E402
from verify_stage3_gold_annotation import verify_pack  # noqa: E402

BLANK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
WINTER_ARTICLE33 = (
    ROOT.parent / "references" / "winter_2020_model_check" / "model_check"
    / "input" / "regulations" / "gdpr" / "article33.txt"
)


def _blank() -> dict:
    return json.loads(BLANK.read_text(encoding="utf-8"))


def _run_tool(editable: Path, stdin: str, backup_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "review_stage3_gold_annotation.py"),
         "--editable", str(editable), "--backup-dir", str(backup_dir)],
        cwd=ROOT,
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def test_blank_embeds_full_rule_text_from_winter_regulations() -> None:
    pack = _blank()
    for item in pack["matching_items"] + pack["violation_items"]:
        assert len(item["rule_text"]) >= 20
    m001 = next(i for i in pack["matching_items"] if i["item_id"] == "m001")
    assert m001["rule_id"] == "article33"
    source = WINTER_ARTICLE33.read_text(encoding="utf-8-sig").strip()
    normalized = "\n".join(line.strip() for line in source.splitlines() if line.strip())
    assert m001["rule_text"] == normalized


def test_verify_pack_accepts_rule_text_and_rejects_missing() -> None:
    pack = _blank()
    summary = verify_pack(pack)
    assert summary["matching_candidate_count"] == 25
    assert summary["violation_candidate_count"] == 33
    tampered = json.loads(BLANK.read_text(encoding="utf-8"))
    tampered["matching_items"][0]["rule_text"] = "short"
    with pytest.raises(Stage1FormalDatasetError):
        verify_pack(tampered)


def test_review_tool_full_adjudication_reaches_freeze_ready(tmp_path) -> None:
    editable = tmp_path / "correction.json"
    backup_dir = tmp_path / "backups"
    # 25 matching items: y for the first 25 questions, then 33 violation
    # items answered "none" (compliant) -> freeze_ready True, exit 0
    answers = "\n".join(["y"] * 25 + ["none"] * 33) + "\n"
    completed = _run_tool(editable, answers, backup_dir)
    assert completed.returncode == 0, completed.stdout[-500:]
    assert "freeze_ready    : True" in completed.stdout
    pack = json.loads(editable.read_text(encoding="utf-8"))
    items = pack["matching_items"] + pack["violation_items"]
    assert len(items) == 58
    assert all(i["review_state"] == "adjudicated" for i in items)
    assert all(i["decision_relevant"] is True for i in pack["matching_items"])
    assert all(i["decision_violation_type"] is None for i in pack["violation_items"])


def test_review_tool_skip_and_quit_keeps_items_unreviewed(tmp_path) -> None:
    editable = tmp_path / "correction.json"
    backup_dir = tmp_path / "backups"
    completed = _run_tool(editable, "s\nq\n", backup_dir)
    assert completed.returncode == 1  # not freeze-ready
    assert "freeze_ready    : False" in completed.stdout
    pack = json.loads(editable.read_text(encoding="utf-8"))
    items = pack["matching_items"] + pack["violation_items"]
    assert all(i["review_state"] == "unreviewed" for i in items)


def test_review_tool_undo_and_resume(tmp_path) -> None:
    editable = tmp_path / "correction.json"
    backup_dir = tmp_path / "backups"
    # adjudicate m001, undo it, then quit: m001 must be unreviewed again
    completed = _run_tool(editable, "y\nu\nq\n", backup_dir)
    pack = json.loads(editable.read_text(encoding="utf-8"))
    m001 = next(i for i in pack["matching_items"] if i["item_id"] == "m001")
    assert m001["review_state"] == "unreviewed"
    assert m001["decision_relevant"] is None
    # resume: adjudicate m001 and m002, quit -> those two adjudicated
    completed = _run_tool(editable, "y\ny\nq\n", backup_dir)
    pack = json.loads(editable.read_text(encoding="utf-8"))
    m001 = next(i for i in pack["matching_items"] if i["item_id"] == "m001")
    m002 = next(i for i in pack["matching_items"] if i["item_id"] == "m002")
    assert m001["review_state"] == "adjudicated" and m001["decision_relevant"] is True
    assert m002["review_state"] == "adjudicated" and m002["decision_relevant"] is True


def test_review_tool_creates_backup_before_overwrite(tmp_path) -> None:
    editable = tmp_path / "correction.json"
    backup_dir = tmp_path / "backups"
    _run_tool(editable, "y\nq\n", backup_dir)
    assert any(backup_dir.glob("stage3_gold_correction_backup_*.json"))

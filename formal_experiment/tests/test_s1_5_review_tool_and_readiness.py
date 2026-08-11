"""Focused tests for the S1.5 review tool + S1.5/S1.6/S1.7/S3.7 readiness.

Covers:
- review tool: list/show/export work; import applies ONLY explicit user
  decisions with atomic save + backup; invalid states fail closed; the tool
  never infers a decision
- readiness dry-runs: S1.5 surface counts (7 records/45 activities/135 label
  fields), all unreviewed proof, authorization sentence present but gate not
  applied; S1.6 synthetic-only; S1.7 checklist; S3.7 readiness v2 (no true
  Gold Rule/Process Records, candidates only, Oracle not started)
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts" / "stage1_review_tool.py"
CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")


def _run_tool(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          capture_output=True, text=True)


def _load_report(name: str) -> dict:
    return json.loads((ROOT / "outputs" / "reports" / name)
                      .read_text(encoding="utf-8"))


def test_tool_list_and_show() -> None:
    r = _run_tool("list")
    assert r.returncode == 0, r.stderr
    assert "gdpr_1_data_breach" in r.stdout
    assert "review_state=unreviewed" in r.stdout
    r2 = _run_tool("show", "gdpr_1_data_breach")
    assert r2.returncode == 0
    assert '"process_id": "gdpr_1_data_breach"' in r2.stdout


def test_tool_import_applies_only_explicit_decisions(tmp_path: Path) -> None:
    orig = CORRECTION.read_bytes()
    backup_dir = ROOT / "outputs" / "development" / "human_review" / "stage1_review_backups"
    before = sorted(backup_dir.glob("*.json"))
    decisions = {
        "records": [{
            "process_id": "gdpr_1_data_breach",
            "review_state": "reviewed",
            "structure_annotation": {"decision": "accepted_candidate"},
            "label_annotations": [{
                "activity_id": "sid-0F3D7191-F96A-45A1-B616-EC78A870BACF",
                "actor": {"status": "present", "value": "Data Controller"},
                "action": {"status": "present", "value": "Notify national authority"},
                "business_object": {"status": "absent", "value": None},
            }],
        }],
    }
    dec_path = tmp_path / "decisions.json"
    dec_path.write_text(json.dumps(decisions), encoding="utf-8")
    try:
        r = _run_tool("import", str(dec_path))
        assert r.returncode == 0, r.stderr
        doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
        rec = doc["records"][0]
        assert rec["review_state"] == "reviewed"
        assert rec["structure_annotation"]["decision"] == "accepted_candidate"
        la = rec["label_annotations"][0]
        assert la["actor"]["status"] == "present"
        assert la["actor"]["value"] == "Data Controller"
        assert la["business_object"]["status"] == "absent"
        # untouched records stay unreviewed
        assert doc["records"][1]["review_state"] == "unreviewed"
        # a backup was created
        after = sorted(backup_dir.glob("*.json"))
        assert len(after) == len(before) + 1
    finally:
        CORRECTION.write_bytes(orig)
        # restore validation consistency
        _run_tool("validate")


def test_tool_rejects_invalid_states(tmp_path: Path) -> None:
    orig = CORRECTION.read_bytes()
    decisions = {"records": [{
        "process_id": "gdpr_1_data_breach",
        "review_state": "not_a_state",
    }]}
    dec_path = tmp_path / "bad.json"
    dec_path.write_text(json.dumps(decisions), encoding="utf-8")
    try:
        r = _run_tool("import", str(dec_path))
        assert r.returncode != 0
        assert "invalid review_state" in r.stderr
        # file unchanged after rejection
        assert CORRECTION.read_bytes() == orig
    finally:
        CORRECTION.write_bytes(orig)


def test_s1_5_readiness_counts_and_unreviewed_proof() -> None:
    s15 = _load_report("s1_5_input_readiness_dry_run.json")
    assert s15["status"] == "dry_run_not_applied"
    surface = s15["review_surface"]
    assert surface["records"] == 7
    assert surface["activities"] == 45
    assert surface["label_fields"] == 135
    proof = s15["blank_template_unreviewed_proof"]
    assert proof["all_records_unreviewed"] is True
    assert proof["all_label_fields_unresolved"] is True
    assert proof["no_gold_prefilled"] is True
    assert s15["authorization_sentence"].startswith("I authorize the S1.5")
    assert s15["before_after"]["before"]["S1.5"] == "blocked"
    assert s15["zero_api"]["new_llm_api_calls"] == 0


def test_s1_5_review_surface_authorization_applied() -> None:
    """2026-08-11 user authorization: S1.5 input-ready recorded; audit pass
    present; freeze NOT authorized."""
    man = json.loads((ROOT / "outputs" / "reports"
                      / "s1_5_review_surface_authorization_v1.manifest.json")
                     .read_text(encoding="utf-8"))
    assert man["authorized_by_user"] is True
    assert man["authorization_scope"]["gold_freeze_authorized"] is False
    assert man["authorization_scope"]["tool_must_not_infer_or_prefill"] is True
    assert man["membership"]["payload_sha256"] == (
        "e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d")
    assert all(man["checks"].values())
    assert man["status"] == "input_ready_freeze_blocked"
    from formal_experiment.audit import collect_project_audit
    audit = collect_project_audit()
    passes = {item["code"] for item in audit["findings"]["passes"]}
    # after batch-1 import the audit reports adjudication-in-progress
    assert "stage1_human_adjudication_in_progress" in passes
    assert audit["final_experiment_ready"] is True  # Stage 2 gate unaffected


def test_s1_6_s1_7_s3_7_readiness() -> None:
    s16 = _load_report("s1_6_evaluator_synthetic_verification_v1.json")
    assert s16["status"] == "synthetic_verification_only"
    assert "blocked until human Process Gold" in s16["formal_run"]
    s17 = _load_report("s1_7_freeze_checklist_v1.json")
    assert s17["checklist"]["output"].startswith("human Process Gold")
    assert "NOT YET EXISTING" in s17["checklist"]["output"]
    s37 = _load_report("s3_7_oracle_readiness_v2.json")
    assert s37["gold_rule_records"]["exist"] is False
    assert s37["gold_process_records"]["exist"] is False
    assert s37["oracle_started"] is False
    assert any("as Gold Rule Records" in f for f in s37["forbidden"])
    assert any("as Gold Process Records" in f for f in s37["forbidden"])
    assert s37["zero_api"]["new_llm_api_calls"] == 0

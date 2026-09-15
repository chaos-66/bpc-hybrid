# -*- coding: utf-8 -*-
"""Transition readiness v10: two-method condition, cancelled repair arm.

Offline; no LLM/API; v9 and all older capsules stay byte-exact.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_s2_13_s3_7_transition_readiness_v10.py"
VERIFIER = ROOT / "scripts/verify_s2_13_s3_7_transition_readiness_v10.py"
REPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10.json"
MANIFEST = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10.manifest.json"
EXPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10_export_index.json"
MARKDOWN = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10.md"
SCHEMA = ROOT / "configs/schemas/s2_13_s3_7_transition_readiness_v10.schema.json"
CONTRACT = ROOT / "outputs/reports/s2_12_two_method_contract_v1.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          cwd=ROOT.parent, capture_output=True, text=True,
                          timeout=900)


def test_verifier_verifies():
    proc = _run(VERIFIER)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "TRANSITION READINESS V10 VERIFIED" in proc.stdout


def test_builder_replay_is_byte_identical():
    proc = _run(BUILDER, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_builder_refuses_to_overwrite():
    proc = _run(BUILDER, "--publish")
    assert proc.returncode == 2
    assert "refusing to overwrite" in proc.stdout


def test_state_is_derived_from_current_two_method_contract():
    report = _read(REPORT)
    contract = _read(CONTRACT)
    complete = contract["comparison"]["complete"] is True
    assert report["s2_12"]["comparison_complete"] is complete
    assert report["s2_12"]["active_methods"] == ["sun_rule_only", "direct_llm"]
    assert report["s2_12"]["remaining_calls"] == contract["call_plan"]["remaining_calls"]
    if complete:
        assert report["s2_13"]["status"] == "ready_for_separate_freeze_checkpoint"
    else:
        assert report["s2_13"]["status"] == "blocked_only_on_two_method_contract"
        assert report["s2_13"]["blockers"] == contract["comparison"]["blockers"]


def test_cancelled_repair_arm_is_not_a_dependency():
    report = _read(REPORT)
    assert "sun_llm_fallback" in report["s2_12"]["cancelled_methods"]
    assert "sun_llm_fallback" not in report["s2_12"]["active_methods"]
    assert report["s2_12"]["cancelled_repair_arm"]["required_for_completion"] is False
    assert report["safety"]["cancelled_repair_arm_used"] is False
    assert not any("sun_llm_fallback" in blocker
                   for blocker in report["s2_13"]["blockers"])


def test_historical_v9_is_superseded_not_modified():
    report = _read(REPORT)
    assert len(report["supersedes"]) == 8
    for entry in report["supersedes"]:
        path = ROOT / entry["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_manifest_and_export_bind_every_artifact():
    manifest = _read(MANIFEST)
    export = _read(EXPORT)
    for item in manifest["artifacts"].values():
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    for rel, item in export["files"].items():
        path = ROOT / rel
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


def test_markdown_and_schema_are_present():
    assert MARKDOWN.is_file()
    schema = _read(SCHEMA)
    assert schema["properties"]["schema_version"]["const"] == \
        "s2_13_s3_7_transition_readiness@10.0.0"

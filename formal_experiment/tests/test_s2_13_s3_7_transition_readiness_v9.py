"""Transition readiness v9: Gold Rule Records present, Oracle isolation, gates.

Offline; no LLM/API; historical capsules stay byte-exact.
"""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_s2_13_s3_7_transition_readiness_v9.py"
VERIFIER = ROOT / "scripts/verify_s2_13_s3_7_transition_readiness_v9.py"
REPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v9.json"
MANIFEST = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v9.manifest.json"
EXPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v9_export_index.json"
MARKDOWN = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v9.md"
SCHEMA = ROOT / "configs/schemas/s2_13_s3_7_transition_readiness_v9.schema.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          cwd=ROOT.parent, capture_output=True, text=True,
                          timeout=900)


def test_verifier_verifies():
    proc = _run(VERIFIER)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "TRANSITION READINESS V9 VERIFIED" in proc.stdout


def test_builder_replay_is_byte_identical():
    proc = _run(BUILDER, "--check")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_builder_refuses_to_overwrite():
    proc = _run(BUILDER, "--publish")
    assert proc.returncode == 2
    assert "refusing to overwrite" in proc.stdout


def test_gold_rule_records_are_present_and_counted():
    report = _read(REPORT)
    gold = report["gold_rule_records"]
    assert gold["exist"] is True
    assert gold["verifier_verified"] is True
    assert gold["counts"] == {"rules": 9, "sentences": 74, "items": 92,
                              "spans": 235, "modality_evidence_spans": 85,
                              "relation_entries": 38}
    assert len(gold["covered_rule_ids"]) == 9


def test_gates_are_not_flipped_by_this_checkpoint():
    report = _read(REPORT)
    assert report["s2_13"]["status"] == "blocked"
    assert report["stage3"]["S3.7"]["authorized"] is False
    assert report["safety"]["new_llm_api_calls"] == 0
    assert report["safety"]["oracle_started"] is False
    assert report["safety"]["gold_rule_records_created"] is False
    assert report["safety"]["historical_transition_assets_modified"] is False


def test_historical_capsules_are_superseded_not_modified():
    report = _read(REPORT)
    assert len(report["supersedes"]) == 8
    import hashlib
    for entry in report["supersedes"]:
        path = ROOT / entry["path"]
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_oracle_isolation_run_is_recorded_with_its_boundary():
    report = _read(REPORT)
    oracle = report["oracle_isolation_run"]
    assert oracle["started"] is True
    assert "NOT the formal S3.7 main table" in oracle["claim_status"]
    assert set(oracle["original_three_types"]) == {"oracle",
                                                  "oracle_obligation_only",
                                                  "reference"}
    assert oracle["original_three_types"]["oracle"]["macro_f1"] == 0.3333


def test_manifest_and_export_bind_every_artifact():
    import hashlib
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
        "s2_13_s3_7_transition_readiness@9.0.0"

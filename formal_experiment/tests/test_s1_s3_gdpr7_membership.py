"""Regression tests for the frozen shared GDPR7 Stage 1/Stage 3 membership."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    build_formal_blank_annotation_pack,
    build_formal_process_records,
    load_formal_membership_contract,
    validate_editable_annotation_pack,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.s1_membership_gate import (  # noqa: E402
    STAGE1_MEMBERSHIP_EXPECTATIONS,
    verify_stage1_membership_gate,
)
from formal_experiment.status import collect_status  # noqa: E402


CONFIG = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
EDITABLE = ROOT / "data" / "development" / "human_review" / "stage1_gdpr7_human_correction_v1.json"


def test_gdpr7_membership_is_byte_locked_and_claimed_as_extension() -> None:
    contract = load_formal_membership_contract(CONFIG)
    assert contract["membership"]["count"] == 7
    assert contract["claim_label"] == "all-seven GDPR BPMN extension"
    assert contract["user_authorization"]["status"] == "approved"
    assert contract["provenance"]["source_files_modified"] is False
    assert contract["provenance"]["source_files_deleted"] is False


def test_formal_parse_uses_unique_dataset_ids_for_duplicate_raw_ids() -> None:
    contract = load_formal_membership_contract(CONFIG)
    records = build_formal_process_records(contract)
    assert len(records) == 7
    assert len({item["process_id"] for item in records}) == 7
    raw_ids = [item["raw_process_id"] for item in contract["membership"]["files"]]
    assert len(set(raw_ids)) == 6
    assert sum(len(item["activities"]) for item in records) == 45
    assert all(
        pool["process_ref"] == record["process_id"]
        for record in records
        for pool in record["pools"]
    )


def test_blank_and_editable_annotation_inputs_have_no_auto_gold() -> None:
    contract = load_formal_membership_contract(CONFIG)
    records = build_formal_process_records(contract)
    blank = build_formal_blank_annotation_pack(records, contract)
    assert blank["dataset"] == {
        "dataset_id": "stage1_stage3_gdpr7_extension_v1",
        "scope": "formal",
        "membership_status": "frozen",
    }
    assert blank["review_summary"] == {
        "records": 7,
        "adjudicated_records": 0,
        "label_fields": 135,
        "resolved_label_fields": 0,
        "freeze_ready": False,
    }
    assert all(
        record["structure_annotation"]["gold_process_record"] is None
        and record["review_state"] == "unreviewed"
        for record in blank["records"]
    )
    editable = json.loads(EDITABLE.read_text(encoding="utf-8"))
    report = validate_editable_annotation_pack(editable, records, contract)
    assert report["valid"] is True
    assert report["freeze_ready"] is False
    invalid = copy.deepcopy(editable)
    invalid["records"][0]["source"]["sha256"] = "0" * 64
    assert validate_editable_annotation_pack(invalid, records, contract)["valid"] is False


def test_builder_is_no_overwrite_and_verifier_manifest_exists() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_stage1_gdpr7.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert '"process_records": 7' in completed.stdout
    refused = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_stage1_gdpr7.py"), "--write"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert refused.returncode == 2
    assert "refusing to overwrite" in refused.stdout
    manifest = json.loads(
        (ROOT / "outputs" / "reports" / "s15_s31_gdpr7_membership_v1.manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "succeeded_membership_and_blank_review_ready"
    assert manifest["annotation"]["freeze_ready"] is False


def test_exact_gate_status_and_audit_report_membership_ready() -> None:
    gate = verify_stage1_membership_gate(ROOT)
    assert gate["membership_ready"] is True
    assert gate["active_formal_bpmn_count"] == 7
    assert gate["human_gold_freeze_ready"] is False
    failed = verify_stage1_membership_gate(
        ROOT,
        expectations=replace(STAGE1_MEMBERSHIP_EXPECTATIONS, config_sha256="0" * 64),
    )
    assert failed["membership_ready"] is False
    assert "stage1_membership_config_hash_mismatch" in failed["blockers"]
    status = collect_status()
    audit = collect_project_audit()
    passes = {item["code"] for item in audit["findings"]["passes"]}
    blockers = {item["code"] for item in audit["findings"]["blockers"]}
    assert status["stage1_formal_membership_ready"] is True
    assert "stage1_formal_bpmn_membership_locked" in passes
    assert "stage1_formal_bpmn_membership_not_promoted" not in blockers


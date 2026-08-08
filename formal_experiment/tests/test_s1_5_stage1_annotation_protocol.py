"""Regression tests for the S1.5 blank human-annotation protocol."""

from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_human_annotation import (  # noqa: E402
    build_blank_annotation_pack,
    load_annotation_contract,
    validate_annotation_pack,
)
from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402
from formal_experiment.s1_annotation_gate import (  # noqa: E402
    STAGE1_ANNOTATION_EXPECTATIONS,
    verify_stage1_annotation_gate,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


CONFIG = ROOT / "configs" / "stage1_annotation_protocol_s15.json"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"


def _inputs() -> tuple[dict, dict]:
    contract = load_annotation_contract(CONFIG)
    structural = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(FIXTURE, contract=structural)
    return contract, process_record


def _pack() -> tuple[dict, dict, dict]:
    contract, process_record = _inputs()
    pack = build_blank_annotation_pack(
        [process_record],
        dataset_id="s15_synthetic_protocol_fixture_v1",
        contract=contract,
    )
    return contract, process_record, pack


def test_s15_contract_keeps_formal_membership_and_gold_blocked() -> None:
    contract, _ = _inputs()
    assert contract["task_ids"] == ["S1.5"]
    assert contract["formal_membership"]["active_bpmn_count"] == 0
    assert contract["formal_membership"]["provenance_candidate_count"] == 57
    assert contract["formal_membership"][
        "promotion_from_references_or_archive_requires_user_approval"
    ] is True
    assert contract["safety"]["gold_auto_filled"] is False
    assert contract["safety"]["performance_evaluation"] is False


def test_blank_pack_has_no_gold_or_human_decisions() -> None:
    contract, process_record, pack = _pack()
    report = validate_annotation_pack(
        pack, process_records=[process_record], contract=contract
    )
    assert report.valid is True
    assert report.freeze_ready is False
    assert pack["review_summary"] == {
        "records": 1,
        "adjudicated_records": 0,
        "label_fields": 18,
        "resolved_label_fields": 0,
        "freeze_ready": False,
    }
    record = pack["records"][0]
    assert record["review_state"] == "unreviewed"
    assert record["structure_annotation"]["gold_process_record"] is None
    assert all(
        item[field] == {"status": "unreviewed", "value": None}
        for item in record["label_annotations"]
        for field in ("actor", "action", "business_object")
    )


def test_source_context_summary_and_field_inconsistency_fail_closed() -> None:
    contract, process_record, pack = _pack()
    extra = copy.deepcopy(pack)
    extra["unexpected"] = True
    assert validate_annotation_pack(
        extra, process_records=[process_record], contract=contract
    ).schema_valid is False
    source = copy.deepcopy(pack)
    source["records"][0]["source"]["sha256"] = "0" * 64
    assert validate_annotation_pack(
        source, process_records=[process_record], contract=contract
    ).cross_field_valid is False
    context = copy.deepcopy(pack)
    context["records"][0]["label_annotations"][0]["raw_label"] = "Changed"
    assert validate_annotation_pack(
        context, process_records=[process_record], contract=contract
    ).cross_field_valid is False
    summary = copy.deepcopy(pack)
    summary["review_summary"]["freeze_ready"] = True
    assert validate_annotation_pack(
        summary, process_records=[process_record], contract=contract
    ).cross_field_valid is False
    field = copy.deepcopy(pack)
    field["records"][0]["label_annotations"][0]["actor"] = {
        "status": "present",
        "value": None,
    }
    assert validate_annotation_pack(
        field, process_records=[process_record], contract=contract
    ).cross_field_valid is False


def test_s15_runner_is_fixture_only_and_does_not_write_gold() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_stage1_annotation_protocol.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert '"freeze_ready": false' in completed.stdout
    assert '"gold_process_record": null' in completed.stdout
    refused = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "build_stage1_annotation_protocol.py"),
            "--bpmn",
            str(ROOT / "configs" / "stage1_annotation_protocol_s15.json"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert refused.returncode == 2
    assert "restricted to synthetic Stage 1 fixtures" in refused.stdout


def test_s15_exact_hash_gate_verifies_protocol_but_not_formal_gold() -> None:
    gate = verify_stage1_annotation_gate(ROOT)
    assert gate["protocol_ready"] is True
    assert gate["formal_membership_ready"] is False
    assert gate["human_gold_freeze_ready"] is False
    assert "stage1_formal_bpmn_membership_not_promoted" in gate["blockers"]
    failed = verify_stage1_annotation_gate(
        ROOT,
        expectations=replace(STAGE1_ANNOTATION_EXPECTATIONS, config_sha256="0" * 64),
    )
    assert failed["protocol_ready"] is False
    assert "stage1_annotation_config_hash_mismatch" in failed["blockers"]


def test_status_and_audit_combine_protocol_with_separate_formal_membership() -> None:
    status = collect_status()
    audit = collect_project_audit()
    passes = {item["code"] for item in audit["findings"]["passes"]}
    blockers = {item["code"] for item in audit["findings"]["blockers"]}
    assert status["stage1_annotation_protocol_verified"] is True
    assert status["stage1_formal_membership_ready"] is True
    assert status["stage1_human_gold_freeze_ready"] is False
    assert "stage1_annotation_protocol_verified" in passes
    assert "stage1_formal_bpmn_membership_locked" in passes
    assert "stage1_formal_bpmn_membership_not_promoted" not in blockers

"""Regression tests for S1.1/S1.2/S1.4 structural Process Records."""

from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    Stage1ProcessError,
    load_stage1_contract,
    parse_bpmn_bytes,
    parse_bpmn_file,
    validate_process_record,
)
from formal_experiment.s1_structural_gate import (  # noqa: E402
    STAGE1_STRUCTURAL_EXPECTATIONS,
    verify_stage1_structural_gate,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
BRANCH = ROOT / "tests" / "fixtures" / "stage1" / "s11_branch_parallel.bpmn"
CYCLE = ROOT / "tests" / "fixtures" / "stage1" / "s14_cycle_unreachable.bpmn"


def _contract() -> dict:
    return load_stage1_contract(CONFIG)


def test_stage1_contract_freezes_schema_parser_and_safety_boundary() -> None:
    contract = _contract()
    assert contract["task_ids"] == ["S1.1", "S1.2", "S1.4"]
    assert contract["process_record_schema"]["schema_version"] == "process_record@1.0.0"
    assert contract["parser"]["parser_version"] == "stage1_bpmn_parser@1.0.0"
    assert contract["parser"]["subprocess_handling"] == "opaque_activity_no_internal_flattening"
    assert contract["determinism"]["xml_sibling_order_affects_output"] is False
    assert contract["safety"]["formal_bpmn_read"] is False
    assert contract["safety"]["performance_evaluation"] is False


def test_branch_parallel_fixture_builds_canonical_process_record() -> None:
    record = parse_bpmn_file(BRANCH, contract=_contract())
    assert validate_process_record(record).valid is True
    assert record["schema_version"] == "process_record@1.0.0"
    assert record["process_id"] == "Process_Claims"
    assert [item["id"] for item in record["activities"]] == sorted(
        item["id"] for item in record["activities"]
    )
    assert len(record["activities"]) == 5
    assert len(record["events"]) == 2
    assert len(record["gateways"]) == 4
    assert len(record["sequence_flows"]) == 12
    assert record["control_flow"]["branching_gateway_ids"] == [
        "Gateway_Decide",
        "Gateway_ParallelSplit",
    ]
    assert record["control_flow"]["parallel_split_gateway_ids"] == [
        "Gateway_ParallelSplit"
    ]
    assert record["control_flow"]["parallel_join_gateway_ids"] == [
        "Gateway_ParallelJoin"
    ]
    assert record["control_flow"]["unreachable_node_ids"] == []


def test_lane_default_condition_and_parallel_non_order_are_preserved() -> None:
    record = parse_bpmn_file(BRANCH, contract=_contract())
    activities = {item["id"]: item for item in record["activities"]}
    flows = {item["id"]: item for item in record["sequence_flows"]}
    assert activities["Task_Approve"]["lane_ids"] == ["Lane_Supervisor"]
    assert activities["Task_Reject"]["lane_ids"] == ["Lane_Clerk"]
    assert flows["Flow_Decide_Approve"]["condition_expression"] == "approved = true"
    assert flows["Flow_Decide_Reject"]["is_default"] is True
    order = {
        (item["before_activity_id"], item["after_activity_id"])
        for item in record["control_flow"]["activity_order_relations"]
    }
    assert ("Task_Receive", "Task_Approve") in order
    assert ("Task_Archive", "Task_Notify") not in order
    assert ("Task_Notify", "Task_Archive") not in order


def test_cycle_and_unreachable_nodes_are_explicit() -> None:
    record = parse_bpmn_file(CYCLE, contract=_contract())
    assert record["control_flow"]["cycle_detected"] is True
    assert record["control_flow"]["cyclic_node_ids"] == ["Task_A", "Task_B"]
    assert record["control_flow"]["unreachable_node_ids"] == ["Task_Orphan"]
    order = {
        (item["before_activity_id"], item["after_activity_id"])
        for item in record["control_flow"]["activity_order_relations"]
    }
    assert ("Task_A", "Task_B") in order
    assert ("Task_B", "Task_A") in order


def test_schema_and_derived_relations_fail_closed_when_tampered() -> None:
    record = parse_bpmn_file(BRANCH, contract=_contract())
    extra = copy.deepcopy(record)
    extra["unexpected"] = True
    assert validate_process_record(extra).schema_valid is False
    bad_reachability = copy.deepcopy(record)
    bad_reachability["control_flow"]["reachable_pairs"].pop()
    report = validate_process_record(bad_reachability)
    assert report.schema_valid is True
    assert report.cross_field_valid is False
    bad_lane = copy.deepcopy(record)
    bad_lane["activities"][0]["lane_ids"] = ["Unknown_Lane"]
    assert validate_process_record(bad_lane).cross_field_valid is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda payload: payload.replace(b'targetRef="End_1"', b'targetRef="Missing"'), "unknown node"),
        (lambda payload: payload.replace(b'id="Task_Notify"', b'id="Task_Archive"'), "globally unique"),
        (lambda payload: b'<!DOCTYPE definitions [<!ENTITY x "bad">]>' + payload, "DOCTYPE/entity"),
    ],
)
def test_malformed_or_unsafe_bpmn_is_rejected(mutation, message: str) -> None:
    with pytest.raises(Stage1ProcessError, match=message):
        parse_bpmn_bytes(
            mutation(BRANCH.read_bytes()),
            source_path="tests/fixtures/stage1/mutated.bpmn",
            contract=_contract(),
        )


def test_stage1_runner_is_offline_fixture_only() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_stage1_structural.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert '"schema_version": "process_record@1.0.0"' in completed.stdout
    refused = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_stage1_structural.py"),
            "--bpmn",
            str(ROOT / "configs" / "stage1_structural_s11_s14.json"),
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


def test_stage1_exact_hash_gate_is_ready_and_wrong_hash_fails() -> None:
    gate = verify_stage1_structural_gate(ROOT)
    assert gate["ready"] is True
    assert gate["synthetic_fixture_only"] is True
    assert gate["performance_evaluation"] is False
    failed = verify_stage1_structural_gate(
        ROOT,
        expectations=replace(STAGE1_STRUCTURAL_EXPECTATIONS, config_sha256="0" * 64),
    )
    assert failed["ready"] is False
    assert "stage1_structural_config_hash_mismatch" in failed["blockers"]


def test_status_and_audit_surface_verified_stage1_without_formal_claim() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["stage1_structural_verified"] is True
    assert "stage1_structural_process_record_verified" in pass_codes
    assert status["final_experiment_ready"] is False

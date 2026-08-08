"""Verify S1.1/S1.2/S1.4 on synthetic BPMN only."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    Stage1ProcessError,
    load_stage1_contract,
    parse_bpmn_bytes,
    parse_bpmn_file,
    sha256_file,
    validate_process_record,
)


CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
SCHEMA = ROOT / "configs" / "schemas" / "process_record.schema.json"
IMPLEMENTATION = ROOT / "src" / "bpc_hybrid" / "stage1_process.py"
RUNNER = ROOT / "scripts" / "run_stage1_structural.py"
VERIFIER = Path(__file__).resolve()
BRANCH_FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s11_branch_parallel.bpmn"
CYCLE_FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s14_cycle_unreachable.bpmn"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s11_s14_stage1_structural_synthetic_v1.manifest.json"


def _expect_error(callback: Any, text: str) -> None:
    try:
        callback()
    except Stage1ProcessError as exc:
        if text not in str(exc):
            raise Stage1ProcessError(f"unexpected fail-closed error: {exc}") from exc
        return
    raise Stage1ProcessError(f"expected fail-closed error containing: {text}")


def _reorder_process_children(payload: bytes) -> bytes:
    root = ET.fromstring(payload)
    process = next(
        element for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "process"
    )
    process[:] = list(reversed(list(process)))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _semantic_projection(record: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(record)
    value["source"].pop("sha256")
    value["source"].pop("byte_size")
    return value


def verify() -> dict[str, Any]:
    contract = load_stage1_contract(CONFIG)
    branch = parse_bpmn_file(BRANCH_FIXTURE, contract=contract)
    cycle = parse_bpmn_file(CYCLE_FIXTURE, contract=contract)
    if not validate_process_record(branch).valid or not validate_process_record(cycle).valid:
        raise Stage1ProcessError("synthetic Process Record failed canonical validation")

    if (
        branch["process_id"] != "Process_Claims"
        or len(branch["pools"]) != 1
        or len(branch["lanes"]) != 2
        or len(branch["activities"]) != 5
        or len(branch["events"]) != 2
        or len(branch["gateways"]) != 4
        or len(branch["sequence_flows"]) != 12
    ):
        raise Stage1ProcessError("S1.1/S1.2 structural counts changed")
    activities = {item["id"]: item for item in branch["activities"]}
    flows = {item["id"]: item for item in branch["sequence_flows"]}
    if (
        activities["Task_Approve"]["lane_ids"] != ["Lane_Supervisor"]
        or activities["Task_Reject"]["lane_ids"] != ["Lane_Clerk"]
        or flows["Flow_Decide_Approve"]["condition_expression"] != "approved = true"
        or flows["Flow_Decide_Reject"]["is_default"] is not True
    ):
        raise Stage1ProcessError("lane, condition, or default-flow binding changed")
    control = branch["control_flow"]
    if (
        control["branching_gateway_ids"]
        != ["Gateway_Decide", "Gateway_ParallelSplit"]
        or control["parallel_gateway_ids"]
        != ["Gateway_ParallelJoin", "Gateway_ParallelSplit"]
        or control["parallel_split_gateway_ids"] != ["Gateway_ParallelSplit"]
        or control["parallel_join_gateway_ids"] != ["Gateway_ParallelJoin"]
        or control["cycle_detected"] is not False
        or control["unreachable_node_ids"] != []
    ):
        raise Stage1ProcessError("S1.4 branch/parallel/reachability classification changed")
    order_pairs = {
        (item["before_activity_id"], item["after_activity_id"])
        for item in control["activity_order_relations"]
    }
    if (
        ("Task_Receive", "Task_Approve") not in order_pairs
        or ("Task_Approve", "Task_Archive") not in order_pairs
        or ("Task_Archive", "Task_Notify") in order_pairs
        or ("Task_Notify", "Task_Archive") in order_pairs
    ):
        raise Stage1ProcessError("activity reachability/order semantics changed")
    cycle_control = cycle["control_flow"]
    if (
        cycle_control["cyclic_node_ids"] != ["Task_A", "Task_B"]
        or cycle_control["cycle_detected"] is not True
        or cycle_control["unreachable_node_ids"] != ["Task_Orphan"]
    ):
        raise Stage1ProcessError("cycle or unreachable-node semantics changed")

    branch_payload = BRANCH_FIXTURE.read_bytes()
    reordered = parse_bpmn_bytes(
        _reorder_process_children(branch_payload),
        source_path="tests/fixtures/stage1/s11_branch_parallel.bpmn",
        contract=contract,
    )
    if _semantic_projection(reordered) != _semantic_projection(branch):
        raise Stage1ProcessError("Process Record semantics depend on XML sibling order")

    tampered = copy.deepcopy(branch)
    tampered["control_flow"]["reachable_pairs"] = tampered["control_flow"]["reachable_pairs"][:-1]
    tampered_report = validate_process_record(tampered)
    if tampered_report.schema_valid is not True or tampered_report.cross_field_valid is not False:
        raise Stage1ProcessError("cross-field tampering did not fail closed")
    extra = copy.deepcopy(branch)
    extra["unexpected"] = True
    if validate_process_record(extra).schema_valid is not False:
        raise Stage1ProcessError("schema additionalProperties did not fail closed")

    unknown_flow = branch_payload.replace(b'targetRef="End_1"', b'targetRef="Missing_Node"')
    _expect_error(
        lambda: parse_bpmn_bytes(
            unknown_flow,
            source_path="tests/fixtures/stage1/unknown_flow.bpmn",
            contract=contract,
        ),
        "unknown node",
    )
    duplicate_node = branch_payload.replace(b'id="Task_Notify"', b'id="Task_Archive"')
    _expect_error(
        lambda: parse_bpmn_bytes(
            duplicate_node,
            source_path="tests/fixtures/stage1/duplicate_node.bpmn",
            contract=contract,
        ),
        "globally unique",
    )
    _expect_error(
        lambda: parse_bpmn_bytes(
            b'<!DOCTYPE definitions [<!ENTITY x "forbidden">]>' + branch_payload,
            source_path="tests/fixtures/stage1/doctype.bpmn",
            contract=contract,
        ),
        "DOCTYPE/entity",
    )

    artifacts = {
        "config": CONFIG,
        "schema": SCHEMA,
        "implementation": IMPLEMENTATION,
        "runner": RUNNER,
        "verifier": VERIFIER,
        "branch_fixture": BRANCH_FIXTURE,
        "cycle_fixture": CYCLE_FIXTURE,
    }
    return {
        "schema_version": "stage1_structural_verification_manifest@1.0.0",
        "run_id": "s11_s14_stage1_structural_synthetic_v1",
        "task_ids": ["S1.1", "S1.2", "S1.4"],
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version()},
        "claim_boundary": contract["claim_boundary"],
        "artifacts": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items()
        },
        "branch_parallel_verification": {
            "record": branch,
            "counts": {
                "pools": len(branch["pools"]),
                "lanes": len(branch["lanes"]),
                "activities": len(branch["activities"]),
                "events": len(branch["events"]),
                "gateways": len(branch["gateways"]),
                "sequence_flows": len(branch["sequence_flows"]),
                "direct_edges": len(control["direct_edges"]),
                "reachable_pairs": len(control["reachable_pairs"]),
                "activity_order_relations": len(control["activity_order_relations"]),
            },
            "lane_binding_verified": True,
            "condition_and_default_flow_verified": True,
            "branch_and_parallel_verified": True,
            "parallel_branches_not_falsely_ordered": True,
        },
        "cycle_unreachable_verification": {
            "record": cycle,
            "cyclic_node_ids": cycle_control["cyclic_node_ids"],
            "unreachable_node_ids": cycle_control["unreachable_node_ids"],
        },
        "determinism_and_failure_verification": {
            "xml_sibling_order_invariant": True,
            "unknown_flow_reference_rejected": True,
            "duplicate_node_id_rejected": True,
            "doctype_and_entity_rejected": True,
            "schema_additional_property_rejected": True,
            "tampered_reachability_rejected": True,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
            "formal_process_records_written": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    target = args.manifest_out.resolve()
    if target.exists():
        raise Stage1ProcessError(f"refusing to overwrite: {target}")
    manifest = verify()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

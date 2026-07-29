"""Verify the S1.3 P0/P1 label-semantics contract on synthetic BPMN."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    Stage1LabelError,
    load_label_contract,
    render_label_semantics,
    validate_label_semantics,
)
from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
    sha256_file,
)


CONFIG = ROOT / "configs" / "stage1_label_semantics_s13.json"
SCHEMA = ROOT / "configs" / "schemas" / "stage1_label_semantics.schema.json"
IMPLEMENTATION = ROOT / "src" / "bpc_hybrid" / "stage1_label_semantics.py"
RUNNER = ROOT / "scripts" / "run_stage1_label_semantics.py"
VERIFIER = Path(__file__).resolve()
FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
STRUCTURAL_MANIFEST = ROOT / "outputs" / "reports" / "s11_s14_stage1_structural_synthetic_v1.manifest.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s13_stage1_label_semantics_synthetic_v1.manifest.json"


def _by_id(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["activity_id"]: item for item in record["activities"]}


def verify() -> dict[str, Any]:
    contract = load_label_contract(CONFIG)
    structural_contract = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(FIXTURE, contract=structural_contract)
    p0 = render_label_semantics(process_record, baseline="P0", contract=contract)
    p1 = render_label_semantics(process_record, baseline="P1", contract=contract)
    if not validate_label_semantics(
        p0, process_record=process_record, contract=contract
    ).valid:
        raise Stage1LabelError("P0 sidecar failed deterministic validation")
    if not validate_label_semantics(
        p1, process_record=process_record, contract=contract
    ).valid:
        raise Stage1LabelError("P1 sidecar failed deterministic validation")
    p0_by_id = _by_id(p0)
    p1_by_id = _by_id(p1)
    if len(p0_by_id) != 6 or len(p1_by_id) != 6:
        raise Stage1LabelError("S1.3 synthetic activity membership changed")
    if not all(
        item["actor_surface"] is None
        and item["action_surface"] is None
        and item["business_object_surface"] is None
        and item["actor_status"] == "p0_not_inferred"
        and item["label_status"] == "raw_only"
        for item in p0_by_id.values()
    ):
        raise Stage1LabelError("P0 performed semantic inference")
    expected_p1 = {
        "Task_Ambiguous": {
            "lane_labels": ["Claims Clerk", "Risk Manager"],
            "actor_surface": None,
            "actor_status": "ambiguous_lane_labels",
            "action_surface": "Review",
            "business_object_surface": "disputed claim",
            "label_status": "parsed_action_object",
        },
        "Task_Empty": {
            "lane_labels": ["Claims Clerk"],
            "actor_surface": "Claims Clerk",
            "actor_status": "single_lane_label",
            "action_surface": None,
            "business_object_surface": None,
            "label_status": "empty_label",
        },
        "Task_NoLane": {
            "lane_labels": [],
            "actor_surface": None,
            "actor_status": "no_lane_label",
            "action_surface": "Archive",
            "business_object_surface": "decision",
            "label_status": "parsed_action_object",
        },
        "Task_Punct": {
            "lane_labels": ["Claims Clerk"],
            "actor_surface": "Claims Clerk",
            "actor_status": "single_lane_label",
            "action_surface": "Approve",
            "business_object_surface": "claim request",
            "label_status": "parsed_action_object",
        },
        "Task_Single": {
            "lane_labels": ["Risk Manager"],
            "actor_surface": "Risk Manager",
            "actor_status": "single_lane_label",
            "action_surface": "Escalate",
            "business_object_surface": None,
            "label_status": "parsed_action_only",
        },
        "Task_Unparseable": {
            "lane_labels": ["Claims Clerk"],
            "actor_surface": "Claims Clerk",
            "actor_status": "single_lane_label",
            "action_surface": None,
            "business_object_surface": None,
            "label_status": "unparsed_label",
        },
    }
    for activity_id, expected in expected_p1.items():
        actual = {key: p1_by_id[activity_id][key] for key in expected}
        if actual != expected:
            raise Stage1LabelError(f"P1 edge-case semantics changed for {activity_id}")

    extra = copy.deepcopy(p1)
    extra["unexpected"] = True
    if validate_label_semantics(
        extra, process_record=process_record, contract=contract
    ).schema_valid is not False:
        raise Stage1LabelError("S1.3 schema additionalProperties did not fail closed")
    tampered = copy.deepcopy(p1)
    _by_id(tampered)["Task_Punct"]["action_surface"] = "Reject"
    report = validate_label_semantics(
        tampered, process_record=process_record, contract=contract
    )
    if report.schema_valid is not True or report.cross_field_valid is not False:
        raise Stage1LabelError("tampered P1 surface did not fail closed")
    try:
        render_label_semantics(process_record, baseline="P2", contract=contract)
    except Stage1LabelError as exc:
        if "unknown S1.3 baseline" not in str(exc):
            raise
    else:
        raise Stage1LabelError("unknown S1.3 baseline did not fail closed")

    artifacts = {
        "config": CONFIG,
        "schema": SCHEMA,
        "implementation": IMPLEMENTATION,
        "runner": RUNNER,
        "verifier": VERIFIER,
        "fixture": FIXTURE,
        "structural_manifest": STRUCTURAL_MANIFEST,
    }
    return {
        "schema_version": "stage1_label_semantics_verification_manifest@1.0.0",
        "run_id": "s13_stage1_label_semantics_synthetic_v1",
        "task_ids": ["S1.3"],
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version()},
        "claim_boundary": contract["claim_boundary"],
        "artifacts": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items()
        },
        "input_process_record": process_record,
        "p0_verification": {
            "record": p0,
            "activity_count": len(p0_by_id),
            "semantic_inference_count": 0,
            "raw_only_count": sum(
                item["label_status"] == "raw_only" for item in p0["activities"]
            ),
        },
        "p1_verification": {
            "record": p1,
            "activity_count": len(p1_by_id),
            "actor_status_counts": {
                status: sum(item["actor_status"] == status for item in p1["activities"])
                for status in ("single_lane_label", "no_lane_label", "ambiguous_lane_labels")
            },
            "label_status_counts": {
                status: sum(item["label_status"] == status for item in p1["activities"])
                for status in (
                    "empty_label",
                    "unparsed_label",
                    "parsed_action_only",
                    "parsed_action_object",
                )
            },
        },
        "failure_semantics": {
            "unknown_baseline_rejected": True,
            "schema_additional_property_rejected": True,
            "tampered_surface_rejected": True,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "learned_model_used": False,
            "performance_evaluation": False,
            "formal_label_records_written": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    target = args.manifest_out.resolve()
    if target.exists():
        raise Stage1LabelError(f"refusing to overwrite: {target}")
    manifest = verify()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

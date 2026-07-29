"""Verify S1.5 blank annotation and freeze semantics on synthetic BPMN."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_human_annotation import (  # noqa: E402
    Stage1AnnotationError,
    build_blank_annotation_pack,
    load_annotation_contract,
    validate_annotation_pack,
)
from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
    sha256_file,
)


CONFIG = ROOT / "configs" / "stage1_annotation_protocol_s15.json"
SCHEMA = ROOT / "configs" / "schemas" / "stage1_human_annotation.schema.json"
IMPLEMENTATION = ROOT / "src" / "bpc_hybrid" / "stage1_human_annotation.py"
RUNNER = ROOT / "scripts" / "build_stage1_annotation_protocol.py"
VERIFIER = Path(__file__).resolve()
GUIDE = ROOT / "docs" / "STAGE1_HUMAN_GOLD_GUIDE.md"
FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
STRUCTURAL_MANIFEST = ROOT / "outputs" / "reports" / "s11_s14_stage1_structural_synthetic_v1.manifest.json"
LABEL_MANIFEST = ROOT / "outputs" / "reports" / "s13_stage1_label_semantics_synthetic_v1.manifest.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s15_stage1_annotation_protocol_synthetic_v1.manifest.json"


def verify() -> dict:
    contract = load_annotation_contract(CONFIG)
    structural_contract = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(FIXTURE, contract=structural_contract)
    pack = build_blank_annotation_pack(
        [process_record],
        dataset_id="s15_synthetic_protocol_fixture_v1",
        contract=contract,
    )
    report = validate_annotation_pack(
        pack,
        process_records=[process_record],
        contract=contract,
    )
    if not report.valid or report.freeze_ready:
        raise Stage1AnnotationError("blank synthetic pack validation changed")
    summary = pack["review_summary"]
    if summary != {
        "records": 1,
        "adjudicated_records": 0,
        "label_fields": 18,
        "resolved_label_fields": 0,
        "freeze_ready": False,
    }:
        raise Stage1AnnotationError("blank S1.5 summary changed")
    record = pack["records"][0]
    if (
        record["review_state"] != "unreviewed"
        or record["structure_annotation"]
        != {"decision": "unreviewed", "gold_process_record": None}
        or any(
            annotation[field] != {"status": "unreviewed", "value": None}
            for annotation in record["label_annotations"]
            for field in ("actor", "action", "business_object")
        )
    ):
        raise Stage1AnnotationError("blank pack auto-filled Gold or review state")

    extra = copy.deepcopy(pack)
    extra["unexpected"] = True
    if validate_annotation_pack(
        extra, process_records=[process_record], contract=contract
    ).schema_valid is not False:
        raise Stage1AnnotationError("annotation schema extra property did not fail closed")
    source_tampered = copy.deepcopy(pack)
    source_tampered["records"][0]["source"]["sha256"] = "0" * 64
    if validate_annotation_pack(
        source_tampered, process_records=[process_record], contract=contract
    ).cross_field_valid is not False:
        raise Stage1AnnotationError("source-binding tamper did not fail closed")
    summary_tampered = copy.deepcopy(pack)
    summary_tampered["review_summary"]["freeze_ready"] = True
    if validate_annotation_pack(
        summary_tampered, process_records=[process_record], contract=contract
    ).cross_field_valid is not False:
        raise Stage1AnnotationError("false freeze-ready claim did not fail closed")
    inconsistent = copy.deepcopy(pack)
    inconsistent["records"][0]["label_annotations"][0]["actor"] = {
        "status": "present",
        "value": None,
    }
    if validate_annotation_pack(
        inconsistent, process_records=[process_record], contract=contract
    ).cross_field_valid is not False:
        raise Stage1AnnotationError("present/null field inconsistency did not fail closed")

    artifacts = {
        "config": CONFIG,
        "schema": SCHEMA,
        "implementation": IMPLEMENTATION,
        "runner": RUNNER,
        "verifier": VERIFIER,
        "guide": GUIDE,
        "fixture": FIXTURE,
        "structural_manifest": STRUCTURAL_MANIFEST,
        "label_manifest": LABEL_MANIFEST,
    }
    return {
        "schema_version": "stage1_annotation_protocol_verification_manifest@1.0.0",
        "run_id": "s15_stage1_annotation_protocol_synthetic_v1",
        "task_ids": ["S1.5"],
        "status": "succeeded_protocol_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version()},
        "claim_boundary": contract["claim_boundary"],
        "artifacts": {
            name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items()
        },
        "blank_pack": pack,
        "verification": {
            "schema_valid": True,
            "cross_field_valid": True,
            "record_count": 1,
            "activity_count": 6,
            "label_field_count": 18,
            "resolved_label_field_count": 0,
            "adjudicated_record_count": 0,
            "gold_process_record_count": 0,
            "freeze_ready": False,
            "p0_or_p1_values_auto_filled": False,
        },
        "failure_semantics": {
            "schema_additional_property_rejected": True,
            "source_binding_tamper_rejected": True,
            "false_freeze_claim_rejected": True,
            "present_null_inconsistency_rejected": True,
        },
        "formal_blocker": {
            "code": "stage1_formal_bpmn_membership_not_promoted",
            "active_bpmn_count": 0,
            "provenance_candidate_count": 57,
            "requires_user_approval": True,
            "human_gold_records": 0,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "gold_auto_filled": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
            "formal_artifacts_written": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    target = args.manifest_out.resolve()
    if target.exists():
        raise Stage1AnnotationError(f"refusing to overwrite: {target}")
    manifest = verify()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "succeeded_protocol_only", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

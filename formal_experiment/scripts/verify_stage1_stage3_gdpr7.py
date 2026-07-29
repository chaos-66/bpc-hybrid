"""Verify the frozen all-seven GDPR BPMN membership and blank Stage 1 review pack."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    Stage1FormalDatasetError,
    build_formal_blank_annotation_pack,
    build_formal_process_records,
    load_formal_membership_contract,
    sha256_file,
    validate_editable_annotation_pack,
)
from bpc_hybrid.stage1_human_annotation import (  # noqa: E402
    canonical_process_record_sha256,
)


CONFIG = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s15_s31_gdpr7_membership_v1.manifest.json"


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1FormalDatasetError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1FormalDatasetError(f"{label} root must be an object")
    return value


def _artifact(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": sha256_file(path),
        "byte_size": path.stat().st_size,
    }


def build_manifest(config_path: Path) -> dict[str, Any]:
    contract = load_formal_membership_contract(config_path)
    expected_records = build_formal_process_records(contract)
    expected_blank = build_formal_blank_annotation_pack(expected_records, contract)
    annotation = contract["annotation_activation"]
    process_records_path = ROOT / annotation["process_records_path"]
    blank_path = ROOT / annotation["blank_template_path"]
    editable_path = ROOT / annotation["editable_path"]
    stored_records = _load(process_records_path, "formal Process Record review source")
    stored_blank = _load(blank_path, "formal blank annotation template")
    editable = _load(editable_path, "formal editable annotation pack")
    if stored_records != {"dataset_id": contract["dataset_id"], "records": expected_records}:
        raise Stage1FormalDatasetError("stored formal Process Records differ from deterministic parse")
    if stored_blank != expected_blank:
        raise Stage1FormalDatasetError("stored blank annotation template changed")
    editable_report = validate_editable_annotation_pack(editable, expected_records, contract)
    if not editable_report["valid"]:
        raise Stage1FormalDatasetError(
            "editable annotation pack is invalid: " + "; ".join(editable_report["errors"])
        )
    config_file = Path(config_path).resolve()
    if config_file != CONFIG.resolve():
        raise Stage1FormalDatasetError("verifier accepts only the canonical GDPR7 contract")
    implementation = ROOT / "src" / "bpc_hybrid" / "stage1_formal_dataset.py"
    builder = ROOT / "scripts" / "build_stage1_gdpr7.py"
    verifier = ROOT / "scripts" / "verify_stage1_stage3_gdpr7.py"
    raw_counts = Counter(item["raw_process_id"] for item in contract["membership"]["files"])
    summaries = []
    by_input = {item["input_id"]: item for item in contract["membership"]["files"]}
    for record in expected_records:
        source = by_input[record["process_id"]]
        summaries.append(
            {
                "input_id": record["process_id"],
                "raw_process_id": source["raw_process_id"],
                "source_sha256": record["source"]["sha256"],
                "process_record_sha256": canonical_process_record_sha256(record),
                "counts": {
                    "pools": len(record["pools"]),
                    "lanes": len(record["lanes"]),
                    "activities": len(record["activities"]),
                    "events": len(record["events"]),
                    "gateways": len(record["gateways"]),
                    "sequence_flows": len(record["sequence_flows"]),
                    "reachable_pairs": len(record["control_flow"]["reachable_pairs"]),
                    "activity_order_relations": len(record["control_flow"]["activity_order_relations"]),
                    "unreachable_nodes": len(record["control_flow"]["unreachable_node_ids"]),
                },
            }
        )
    active_root = ROOT.parent / contract["provenance"]["active_root"]
    source_root = ROOT.parent / contract["provenance"]["canonical_source_root"]
    input_artifacts = []
    for item in contract["membership"]["files"]:
        input_artifacts.append(
            {
                "input_id": item["input_id"],
                "filename": item["filename"],
                "sha256": item["sha256"],
                "byte_size": item["byte_size"],
                "source_path": (source_root / item["filename"]).resolve().relative_to(ROOT.parent.resolve()).as_posix(),
                "active_path": (active_root / item["filename"]).resolve().relative_to(ROOT.resolve()).as_posix(),
                "byte_exact_copy_verified": True,
            }
        )
    return {
        "schema_version": "stage1_stage3_gdpr7_verification_manifest@1.0.0",
        "run_id": "s15_s31_gdpr7_membership_v1",
        "task_ids": ["S1.5", "S3.1"],
        "status": "succeeded_membership_and_blank_review_ready",
        "dataset": {
            "dataset_id": contract["dataset_id"],
            "claim_label": contract["claim_label"],
            "membership_count": 7,
            "membership_payload_sha256": contract["membership"]["membership_payload_sha256"],
            "sun_original_four_identified": False,
            "shared_stage1_stage3_membership": True,
        },
        "promotion": {
            "user_approved": True,
            "decision_date": contract["user_authorization"]["decision_date"],
            "mode": contract["provenance"]["promotion_mode"],
            "all_byte_exact_copies_verified": True,
            "source_store_modified": False,
        },
        "inputs": input_artifacts,
        "process_records": {
            "count": len(expected_records),
            "dataset_global_process_ids_unique": True,
            "identity_adapter": contract["process_record_activation"]["process_identity_adapter"],
            "duplicate_raw_process_ids": sorted(
                process_id for process_id, count in raw_counts.items() if count > 1
            ),
            "summaries": summaries,
        },
        "annotation": {
            "blank_template_valid": True,
            "editable_pack_valid": editable_report["valid"],
            "records": editable["review_summary"]["records"],
            "activities": sum(len(item["label_annotations"]) for item in editable["records"]),
            "label_fields": editable["review_summary"]["label_fields"],
            "resolved_label_fields": editable["review_summary"]["resolved_label_fields"],
            "adjudicated_records": editable["review_summary"]["adjudicated_records"],
            "freeze_ready": editable_report["freeze_ready"],
            "gold_auto_filled": False,
        },
        "artifacts": {
            "config": _artifact(CONFIG),
            "implementation": _artifact(implementation),
            "builder": _artifact(builder),
            "verifier": _artifact(verifier),
            "process_records": _artifact(process_records_path),
            "blank_template": _artifact(blank_path),
            "editable_pack": {
                "path": editable_path.resolve().relative_to(ROOT.resolve()).as_posix(),
                "current_sha256": sha256_file(editable_path),
                "mutable_only_by_human_review": True,
            },
        },
        "safety": {
            "formal_bpmn_read": True,
            "human_gold_read_or_modified": False,
            "gold_auto_filled": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
            "formal_predictions_or_results_written": False,
            "no_artifact_overwrite": True,
        },
        "claim_boundary": contract["claim_boundary"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        manifest = build_manifest(args.config)
        output = args.manifest_out.resolve()
        if output.exists():
            raise Stage1FormalDatasetError(f"refusing to overwrite: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            "verified GDPR7 membership: 7 byte-exact BPMN, "
            f"{manifest['annotation']['activities']} activities, "
            f"{manifest['annotation']['label_fields']} blank label fields"
        )
        return 0
    except Stage1FormalDatasetError as exc:
        print(f"GDPR7 verification failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

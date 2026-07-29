"""Frozen all-seven GDPR BPMN membership and blank Stage 1 review material."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
from xml.etree import ElementTree as ET

from bpc_hybrid.stage1_human_annotation import (
    build_blank_annotation_pack,
    load_annotation_contract,
    validate_annotation_pack,
)
from bpc_hybrid.stage1_process import (
    load_stage1_contract,
    parse_bpmn_file,
    validate_process_record,
)


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = ROOT.parent
CONTRACT_VERSION = "stage1_stage3_bpmn_membership@1.0.0"
DATASET_ID = "stage1_stage3_gdpr7_extension_v1"
IDENTITY_ADAPTER = "stage1_formal_input_id_adapter@1.0.0"
MODEL_NAMESPACE = "http://www.omg.org/spec/BPMN/20100524/MODEL"


class Stage1FormalDatasetError(ValueError):
    """Raised when the formal BPMN membership fails closed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1FormalDatasetError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1FormalDatasetError(f"{label} root must be an object")
    return value


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _raw_process_id(path: Path) -> str:
    try:
        root = ET.fromstring(path.read_bytes())
    except (OSError, ET.ParseError) as exc:
        raise Stage1FormalDatasetError(f"invalid BPMN XML: {path}") from exc
    processes = [item for item in root.iter() if item.tag.rsplit("}", 1)[-1] == "process"]
    if len(processes) != 1:
        raise Stage1FormalDatasetError(f"expected exactly one process: {path}")
    process_id = (processes[0].get("id") or "").strip()
    if not process_id:
        raise Stage1FormalDatasetError(f"missing BPMN process id: {path}")
    namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
    if namespace != MODEL_NAMESPACE:
        raise Stage1FormalDatasetError(f"unexpected BPMN namespace: {path}")
    return process_id


def membership_payload(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    provenance = contract["provenance"]
    source_root = provenance["canonical_source_root"]
    active_root = provenance["active_root"]
    return [
        {
            "input_id": item["input_id"],
            "filename": item["filename"],
            "raw_process_id": item["raw_process_id"],
            "byte_size": item["byte_size"],
            "sha256": item["sha256"],
            "source_path": f"{source_root}/{item['filename']}",
            "active_path": f"{active_root}/{item['filename']}",
        }
        for item in contract["membership"]["files"]
    ]


def load_formal_membership_contract(path: Path) -> dict[str, Any]:
    contract = _load_json(path, "Stage 1/Stage 3 GDPR7 membership contract")
    if (
        contract.get("schema_version") != CONTRACT_VERSION
        or contract.get("dataset_id") != DATASET_ID
        or contract.get("task_ids") != ["S1.5", "S3.1"]
        or contract.get("status") != "frozen_all_seven_extension_membership"
        or contract.get("claim_label") != "all-seven GDPR BPMN extension"
    ):
        raise Stage1FormalDatasetError("formal membership contract identity changed")
    authorization = contract.get("user_authorization", {})
    if authorization.get("status") != "approved" or authorization.get("decision_date") != "2026-07-18":
        raise Stage1FormalDatasetError("formal membership lacks the recorded user approval")
    provenance = contract.get("provenance", {})
    if provenance != {
        "canonical_source_root": "references/winter_2020_model_check/model_check/input/models/gdpr",
        "active_root": "formal_experiment/data/input/stage1_stage3/gdpr7",
        "promotion_mode": "byte_exact_copy_keep_source_read_only",
        "source_files_modified": False,
        "source_files_deleted": False,
    }:
        raise Stage1FormalDatasetError("formal membership provenance policy changed")
    membership = contract.get("membership", {})
    files = membership.get("files", [])
    if (
        membership.get("count") != 7
        or not isinstance(files, list)
        or len(files) != 7
        or [item.get("filename") for item in files]
        != sorted(item.get("filename") for item in files)
        or len({item.get("input_id") for item in files}) != 7
    ):
        raise Stage1FormalDatasetError("formal membership must contain seven unique sorted files")
    payload = membership_payload(contract)
    if canonical_sha256(payload) != membership.get("membership_payload_sha256"):
        raise Stage1FormalDatasetError("formal membership payload hash changed")

    source_base = WORKSPACE_ROOT / provenance["canonical_source_root"]
    active_base = WORKSPACE_ROOT / provenance["active_root"]
    references_root = WORKSPACE_ROOT / "references"
    formal_input_root = ROOT / "data" / "input"
    if not _under(source_base, references_root) or not _under(active_base, formal_input_root):
        raise Stage1FormalDatasetError("formal membership root escaped its allowed boundary")
    for item in files:
        source = source_base / item["filename"]
        active = active_base / item["filename"]
        if not source.is_file() or not active.is_file():
            raise Stage1FormalDatasetError(f"missing source or active BPMN: {item['filename']}")
        for candidate in (source, active):
            if candidate.stat().st_size != item["byte_size"] or sha256_file(candidate) != item["sha256"]:
                raise Stage1FormalDatasetError(f"BPMN bytes changed: {candidate}")
        if _raw_process_id(active) != item["raw_process_id"]:
            raise Stage1FormalDatasetError(f"raw process id changed: {item['filename']}")

    activation = contract.get("process_record_activation", {})
    expected_artifacts = (
        ("structural_contract_path", "structural_contract_sha256"),
        ("parser_implementation_path", "parser_implementation_sha256"),
        ("process_record_schema_path", "process_record_schema_sha256"),
    )
    for path_key, hash_key in expected_artifacts:
        artifact = ROOT / activation.get(path_key, "")
        if not artifact.is_file() or sha256_file(artifact) != activation.get(hash_key):
            raise Stage1FormalDatasetError(f"process-record activation binding changed: {path_key}")
    if (
        activation.get("process_identity_adapter") != IDENTITY_ADAPTER
        or activation.get("process_identity_rule")
        != "use membership input_id as dataset-global process_id and update matching pool process_ref; retain raw_process_id in this membership contract"
    ):
        raise Stage1FormalDatasetError("formal process identity policy changed")
    annotation = contract.get("annotation_activation", {})
    for path_key, hash_key in (
        ("protocol_path", "protocol_sha256"),
        ("implementation_path", "implementation_sha256"),
        ("schema_path", "schema_sha256"),
    ):
        artifact = ROOT / annotation.get(path_key, "")
        if not artifact.is_file() or sha256_file(artifact) != annotation.get(hash_key):
            raise Stage1FormalDatasetError(f"annotation activation binding changed: {path_key}")
    if annotation.get("automatic_gold_fill") is not False or annotation.get("human_only_review_state_changes") is not True:
        raise Stage1FormalDatasetError("formal annotation safety policy changed")
    if contract.get("safety") != {
        "human_gold_read_or_modified": False,
        "gold_auto_filled": False,
        "llm_api_called": False,
        "network_called": False,
        "performance_evaluation": False,
        "no_overwrite": True,
    }:
        raise Stage1FormalDatasetError("formal membership safety boundary changed")
    return contract


def build_formal_process_records(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    structural_path = ROOT / contract["process_record_activation"]["structural_contract_path"]
    structural_contract = load_stage1_contract(structural_path)
    active_root = WORKSPACE_ROOT / contract["provenance"]["active_root"]
    records: list[dict[str, Any]] = []
    for item in contract["membership"]["files"]:
        record = parse_bpmn_file(active_root / item["filename"], contract=structural_contract)
        if record["process_id"] != item["raw_process_id"]:
            raise Stage1FormalDatasetError(f"parser/raw process id mismatch: {item['filename']}")
        record["process_id"] = item["input_id"]
        for pool in record["pools"]:
            pool["process_ref"] = item["input_id"]
        report = validate_process_record(record)
        if not report.valid:
            raise Stage1FormalDatasetError(
                f"invalid adapted Process Record {item['input_id']}: " + "; ".join(report.errors)
            )
        records.append(record)
    if [item["process_id"] for item in records] != sorted(item["process_id"] for item in records):
        raise Stage1FormalDatasetError("formal Process Records are not sorted")
    return copy.deepcopy(records)


def build_formal_blank_annotation_pack(
    process_records: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]
) -> dict[str, Any]:
    annotation_contract = load_annotation_contract(
        ROOT / contract["annotation_activation"]["protocol_path"]
    )
    pack = build_blank_annotation_pack(
        process_records,
        dataset_id=contract["dataset_id"],
        contract=annotation_contract,
    )
    pack["dataset"] = {
        "dataset_id": contract["dataset_id"],
        "scope": "formal",
        "membership_status": "frozen",
    }
    report = validate_annotation_pack(
        pack, process_records=process_records, contract=annotation_contract
    )
    if not report.valid or report.freeze_ready:
        raise Stage1FormalDatasetError(
            "formal blank annotation pack must be valid and not frozen: "
            + "; ".join(report.errors)
        )
    return copy.deepcopy(pack)


def validate_editable_annotation_pack(
    pack: Mapping[str, Any],
    process_records: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    annotation_contract = load_annotation_contract(
        ROOT / contract["annotation_activation"]["protocol_path"]
    )
    report = validate_annotation_pack(
        pack, process_records=process_records, contract=annotation_contract
    )
    result = report.to_dict()
    result["valid"] = report.valid
    return result

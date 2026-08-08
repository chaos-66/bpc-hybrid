"""S1.5 blank human-annotation protocol and fail-closed validator."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.stage1_label_semantics import canonical_process_record_sha256
from bpc_hybrid.stage1_process import sha256_file, validate_process_record


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_VERSION = "stage1_annotation_protocol@1.0.0"
SCHEMA_VERSION = "stage1_human_annotation_pack@1.0.0"
FIELD_STATUSES = {"unreviewed", "present", "absent", "needs_adjudication"}
STRUCTURE_DECISIONS = {
    "unreviewed",
    "accepted_candidate",
    "corrected",
    "needs_adjudication",
}
REVIEW_STATES = {"unreviewed", "reviewed", "adjudicated"}
RESOLVED_FIELD_STATUSES = {"present", "absent"}
FINAL_STRUCTURE_DECISIONS = {"accepted_candidate", "corrected"}


class Stage1AnnotationError(ValueError):
    """Raised when the S1.5 annotation protocol fails closed."""


@dataclass(frozen=True)
class AnnotationValidationReport:
    schema_valid: bool
    cross_field_valid: bool
    freeze_ready: bool
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.schema_valid and self.cross_field_valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "cross_field_valid": self.cross_field_valid,
            "freeze_ready": self.freeze_ready,
            "errors": list(self.errors),
        }


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1AnnotationError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1AnnotationError(f"{label} root must be an object")
    return value


def load_annotation_contract(path: Path) -> dict[str, Any]:
    contract = _load_json(path, "S1.5 annotation contract")
    if (
        contract.get("schema_version") != CONTRACT_VERSION
        or contract.get("task_ids") != ["S1.5"]
        or contract.get("status")
        != "verified_offline_blank_protocol_pending_formal_bpmn_membership_and_human_annotation"
    ):
        raise Stage1AnnotationError("S1.5 contract identity changed")
    schema = contract.get("annotation_schema", {})
    schema_path = _project_path(str(schema.get("path", "")))
    if (
        schema.get("schema_version") != SCHEMA_VERSION
        or not schema_path.is_file()
        or sha256_file(schema_path) != schema.get("sha256")
    ):
        raise Stage1AnnotationError("S1.5 annotation schema binding changed")
    upstream = contract.get("upstream", {})
    structural = _project_path(str(upstream.get("structural_manifest_path", "")))
    labels = _project_path(str(upstream.get("label_manifest_path", "")))
    if (
        upstream.get("process_record_schema") != "process_record@1.0.0"
        or not structural.is_file()
        or sha256_file(structural) != upstream.get("structural_manifest_sha256")
        or not labels.is_file()
        or sha256_file(labels) != upstream.get("label_manifest_sha256")
    ):
        raise Stage1AnnotationError("S1.5 upstream gate binding changed")
    blank = contract.get("blank_pack", {})
    if blank != {
        "allowed_scope": "synthetic_protocol_only",
        "initial_review_state": "unreviewed",
        "initial_structure_decision": "unreviewed",
        "initial_gold_process_record": None,
        "initial_label_field_status": "unreviewed",
        "initial_label_field_value": None,
        "p0_or_p1_candidate_values_copied_into_gold": False,
    }:
        raise Stage1AnnotationError("S1.5 blank-pack semantics changed")
    formal = contract.get("formal_membership", {})
    if (
        formal.get("status")
        != "blocked_pending_user_approved_promotion_and_stage3_subset_lock"
        or formal.get("active_bpmn_count") != 0
        or formal.get("provenance_candidate_count") != 57
        or formal.get("promotion_from_references_or_archive_requires_user_approval")
        is not True
    ):
        raise Stage1AnnotationError("S1.5 formal-membership boundary changed")
    freeze = contract.get("freeze_policy", {})
    if freeze != {
        "scope_must_equal": "formal",
        "membership_status_must_equal": "frozen",
        "all_records_review_state": "adjudicated",
        "allowed_final_structure_decisions": ["accepted_candidate", "corrected"],
        "gold_process_record_required": True,
        "allowed_final_label_statuses": ["present", "absent"],
        "present_requires_nonempty_value": True,
        "absent_requires_null_value": True,
        "human_only_state_changes": True,
    }:
        raise Stage1AnnotationError("S1.5 freeze policy changed")
    safety = contract.get("safety", {})
    if safety != {
        "synthetic_fixture_only": True,
        "formal_bpmn_read": False,
        "human_gold_read_or_modified": False,
        "gold_auto_filled": False,
        "llm_api_called": False,
        "network_called": False,
        "performance_evaluation": False,
        "formal_artifacts_written": False,
        "no_overwrite": True,
    }:
        raise Stage1AnnotationError("S1.5 safety boundary changed")
    return contract


def _lane_labels(process_record: Mapping[str, Any], lane_ids: Sequence[str]) -> list[str]:
    lane_names = {item["id"]: item["name"] for item in process_record["lanes"]}
    return sorted(
        {lane_names[lane_id] for lane_id in lane_ids if lane_names[lane_id].strip()}
    )


def _blank_field() -> dict[str, Any]:
    return {"status": "unreviewed", "value": None}


def build_blank_annotation_pack(
    process_records: Sequence[Mapping[str, Any]],
    *,
    dataset_id: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(dataset_id, str) or not dataset_id:
        raise Stage1AnnotationError("dataset_id must be non-empty")
    if contract.get("blank_pack", {}).get("allowed_scope") != "synthetic_protocol_only":
        raise Stage1AnnotationError("blank-pack scope changed")
    by_id: dict[str, Mapping[str, Any]] = {}
    for record in process_records:
        report = validate_process_record(record)
        if not report.valid:
            raise Stage1AnnotationError(
                "invalid upstream Process Record: " + "; ".join(report.errors)
            )
        process_id = record["process_id"]
        if process_id in by_id:
            raise Stage1AnnotationError(f"duplicate process_id: {process_id}")
        by_id[process_id] = record
    records: list[dict[str, Any]] = []
    for process_id in sorted(by_id):
        process_record = by_id[process_id]
        labels = []
        for activity in process_record["activities"]:
            labels.append(
                {
                    "activity_id": activity["id"],
                    "raw_label": activity["name"],
                    "lane_labels": _lane_labels(process_record, activity["lane_ids"]),
                    "actor": _blank_field(),
                    "action": _blank_field(),
                    "business_object": _blank_field(),
                }
            )
        records.append(
            {
                "process_id": process_id,
                "source": {
                    "path": process_record["source"]["path"],
                    "sha256": process_record["source"]["sha256"],
                    "process_record_sha256": canonical_process_record_sha256(
                        process_record
                    ),
                },
                "review_state": "unreviewed",
                "structure_annotation": {
                    "decision": "unreviewed",
                    "gold_process_record": None,
                },
                "label_annotations": labels,
            }
        )
    label_fields = sum(len(item["label_annotations"]) * 3 for item in records)
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "dataset_id": dataset_id,
            "scope": "synthetic_protocol_only",
            "membership_status": "synthetic_fixture_only",
        },
        "records": records,
        "review_summary": {
            "records": len(records),
            "adjudicated_records": 0,
            "label_fields": label_fields,
            "resolved_label_fields": 0,
            "freeze_ready": False,
        },
    }


def _exact_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be an object")
        return False
    if set(value) != expected:
        errors.append(f"{label} properties changed")
        return False
    return True


def _is_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _manual_schema_errors(pack: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _exact_keys(
        pack, {"schema_version", "dataset", "records", "review_summary"}, "pack", errors
    ):
        return errors
    if pack.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version changed")
    dataset = pack.get("dataset")
    if _exact_keys(dataset, {"dataset_id", "scope", "membership_status"}, "dataset", errors):
        if not isinstance(dataset.get("dataset_id"), str) or not dataset["dataset_id"]:
            errors.append("dataset.dataset_id must be non-empty")
        if dataset.get("scope") not in {"synthetic_protocol_only", "formal"}:
            errors.append("dataset.scope changed")
        if dataset.get("membership_status") not in {"synthetic_fixture_only", "frozen"}:
            errors.append("dataset.membership_status changed")
    records = pack.get("records")
    if not isinstance(records, list):
        errors.append("records must be an array")
        return errors
    record_keys = {
        "process_id",
        "source",
        "review_state",
        "structure_annotation",
        "label_annotations",
    }
    label_keys = {
        "activity_id",
        "raw_label",
        "lane_labels",
        "actor",
        "action",
        "business_object",
    }
    for index, record in enumerate(records):
        label = f"records[{index}]"
        if not _exact_keys(record, record_keys, label, errors):
            continue
        if not isinstance(record.get("process_id"), str) or not record["process_id"]:
            errors.append(f"{label}.process_id must be non-empty")
        source = record.get("source")
        if _exact_keys(source, {"path", "sha256", "process_record_sha256"}, f"{label}.source", errors):
            if not isinstance(source.get("path"), str) or not source["path"]:
                errors.append(f"{label}.source.path must be non-empty")
            if not _is_digest(source.get("sha256")) or not _is_digest(
                source.get("process_record_sha256")
            ):
                errors.append(f"{label}.source hashes must be lowercase SHA-256")
        if record.get("review_state") not in REVIEW_STATES:
            errors.append(f"{label}.review_state changed")
        structure = record.get("structure_annotation")
        if _exact_keys(structure, {"decision", "gold_process_record"}, f"{label}.structure_annotation", errors):
            if structure.get("decision") not in STRUCTURE_DECISIONS:
                errors.append(f"{label}.structure decision changed")
            if structure.get("gold_process_record") is not None and not isinstance(
                structure.get("gold_process_record"), Mapping
            ):
                errors.append(f"{label}.gold_process_record must be object or null")
        annotations = record.get("label_annotations")
        if not isinstance(annotations, list):
            errors.append(f"{label}.label_annotations must be an array")
            continue
        for item_index, item in enumerate(annotations):
            item_label = f"{label}.label_annotations[{item_index}]"
            if not _exact_keys(item, label_keys, item_label, errors):
                continue
            if not isinstance(item.get("activity_id"), str) or not item["activity_id"]:
                errors.append(f"{item_label}.activity_id must be non-empty")
            if not isinstance(item.get("raw_label"), str):
                errors.append(f"{item_label}.raw_label must be a string")
            lanes = item.get("lane_labels")
            if (
                not isinstance(lanes, list)
                or any(not isinstance(value, str) for value in lanes)
                or len(lanes) != len(set(lanes))
            ):
                errors.append(f"{item_label}.lane_labels must contain unique strings")
            for field in ("actor", "action", "business_object"):
                decision = item.get(field)
                if not _exact_keys(decision, {"status", "value"}, f"{item_label}.{field}", errors):
                    continue
                if decision.get("status") not in FIELD_STATUSES:
                    errors.append(f"{item_label}.{field}.status changed")
                value = decision.get("value")
                if value is not None and not isinstance(value, str):
                    errors.append(f"{item_label}.{field}.value must be string or null")
    summary = pack.get("review_summary")
    summary_keys = {
        "records",
        "adjudicated_records",
        "label_fields",
        "resolved_label_fields",
        "freeze_ready",
    }
    if _exact_keys(summary, summary_keys, "review_summary", errors):
        for key in summary_keys - {"freeze_ready"}:
            if not isinstance(summary.get(key), int) or isinstance(summary.get(key), bool) or summary[key] < 0:
                errors.append(f"review_summary.{key} must be a nonnegative integer")
        if not isinstance(summary.get("freeze_ready"), bool):
            errors.append("review_summary.freeze_ready must be boolean")
    return errors


def validate_annotation_pack(
    pack: Mapping[str, Any],
    *,
    process_records: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> AnnotationValidationReport:
    del contract
    if not isinstance(pack, Mapping):
        return AnnotationValidationReport(False, False, False, ("pack must be an object",))
    schema_errors = _manual_schema_errors(pack)
    if schema_errors:
        return AnnotationValidationReport(False, False, False, tuple(schema_errors))
    errors: list[str] = []
    source_by_id: dict[str, Mapping[str, Any]] = {}
    for process_record in process_records:
        report = validate_process_record(process_record)
        if not report.valid:
            errors.append("invalid upstream Process Record")
            continue
        process_id = process_record["process_id"]
        if process_id in source_by_id:
            errors.append(f"duplicate upstream process_id: {process_id}")
        source_by_id[process_id] = process_record
    records = pack["records"]
    process_ids = [record["process_id"] for record in records]
    if process_ids != sorted(process_ids) or len(process_ids) != len(set(process_ids)):
        errors.append("annotation records must have unique ascending process_id values")
    if set(process_ids) != set(source_by_id):
        errors.append("annotation membership differs from supplied Process Records")
    resolved_fields = 0
    total_fields = 0
    adjudicated = 0
    structures_final = True
    gold_records_valid = True
    for record in records:
        source = source_by_id.get(record["process_id"])
        if source is None:
            continue
        expected_source = {
            "path": source["source"]["path"],
            "sha256": source["source"]["sha256"],
            "process_record_sha256": canonical_process_record_sha256(source),
        }
        if record["source"] != expected_source:
            errors.append(f"source binding changed for {record['process_id']}")
        expected_context = [
            {
                "activity_id": activity["id"],
                "raw_label": activity["name"],
                "lane_labels": _lane_labels(source, activity["lane_ids"]),
            }
            for activity in source["activities"]
        ]
        actual_context = [
            {
                "activity_id": item["activity_id"],
                "raw_label": item["raw_label"],
                "lane_labels": item["lane_labels"],
            }
            for item in record["label_annotations"]
        ]
        if actual_context != expected_context:
            errors.append(f"activity context changed for {record['process_id']}")
        if record["review_state"] == "adjudicated":
            adjudicated += 1
        structure = record["structure_annotation"]
        structure_final = structure["decision"] in FINAL_STRUCTURE_DECISIONS
        gold_record = structure["gold_process_record"]
        if gold_record is None:
            gold_valid = False
        else:
            gold_report = validate_process_record(gold_record)
            gold_valid = gold_report.valid and gold_record.get("process_id") == record["process_id"]
            if not gold_valid:
                errors.append(f"invalid Gold Process Record for {record['process_id']}")
        structures_final = structures_final and structure_final
        gold_records_valid = gold_records_valid and gold_valid
        for annotation in record["label_annotations"]:
            for field in ("actor", "action", "business_object"):
                total_fields += 1
                decision = annotation[field]
                status = decision["status"]
                value = decision["value"]
                if status == "present":
                    if not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"present {field} requires non-empty value: {record['process_id']}/{annotation['activity_id']}"
                        )
                    else:
                        resolved_fields += 1
                elif status == "absent":
                    if value is not None:
                        errors.append(
                            f"absent {field} requires null value: {record['process_id']}/{annotation['activity_id']}"
                        )
                    else:
                        resolved_fields += 1
                elif value is not None:
                    errors.append(
                        f"unresolved {field} requires null value: {record['process_id']}/{annotation['activity_id']}"
                    )
    dataset = pack["dataset"]
    freeze_ready = bool(
        records
        and dataset["scope"] == "formal"
        and dataset["membership_status"] == "frozen"
        and adjudicated == len(records)
        and structures_final
        and gold_records_valid
        and resolved_fields == total_fields
        and not errors
    )
    expected_summary = {
        "records": len(records),
        "adjudicated_records": adjudicated,
        "label_fields": total_fields,
        "resolved_label_fields": resolved_fields,
        "freeze_ready": freeze_ready,
    }
    if pack["review_summary"] != expected_summary:
        errors.append("review_summary disagrees with annotation content")
    return AnnotationValidationReport(True, not errors, freeze_ready, tuple(errors))


def clone_pack(pack: Mapping[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(dict(pack))

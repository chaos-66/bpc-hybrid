"""Deterministic S1.3 P0/P1 label-semantics sidecars.

P0 preserves the structural parser's activity and lane labels without semantic
inference. P1 is intentionally small: an unambiguous non-empty lane label is
used as the actor surface, the first whitespace-delimited label token is the
action surface, and the remaining text is the business-object surface. No
learned model, linguistic tagger, Gold, network, or LLM is involved.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage1_process import sha256_file, validate_process_record


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_VERSION = "stage1_label_semantics_contract@1.0.0"
SCHEMA_VERSION = "stage1_label_semantics@1.0.0"
PROCESS_RECORD_VERSION = "process_record@1.0.0"
BASELINE_IDENTITIES = {
    "P0": ("stage1_label_p0_raw", "stage1_label_p0@1.0.0"),
    "P1": ("stage1_label_p1_surface_split", "stage1_label_p1@1.0.0"),
}
ACTION_BOUNDARY_CHARACTERS = ".,;:!?()[]{}<>\"'`~@#$%^&*+=|\\/-_"
ACTOR_STATUSES = {
    "p0_not_inferred",
    "single_lane_label",
    "no_lane_label",
    "ambiguous_lane_labels",
}
LABEL_STATUSES = {
    "raw_only",
    "empty_label",
    "unparsed_label",
    "parsed_action_only",
    "parsed_action_object",
}


class Stage1LabelError(ValueError):
    """Raised when the S1.3 label contract fails closed."""


@dataclass(frozen=True)
class LabelValidationReport:
    schema_valid: bool
    cross_field_valid: bool
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return self.schema_valid and self.cross_field_valid

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_valid": self.schema_valid,
            "cross_field_valid": self.cross_field_valid,
            "errors": list(self.errors),
        }


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1LabelError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1LabelError(f"{label} root must be an object")
    return value


def load_label_contract(path: Path) -> dict[str, Any]:
    contract = _load_json(path, "S1.3 label contract")
    if (
        contract.get("schema_version") != CONTRACT_VERSION
        or contract.get("task_ids") != ["S1.3"]
        or contract.get("status")
        != "verified_offline_p0_p1_contract_pending_formal_bpmn_and_gold"
    ):
        raise Stage1LabelError("S1.3 label contract identity changed")
    schema = contract.get("output_schema", {})
    schema_path = _project_path(str(schema.get("path", "")))
    if (
        schema.get("schema_version") != SCHEMA_VERSION
        or not schema_path.is_file()
        or sha256_file(schema_path) != schema.get("sha256")
    ):
        raise Stage1LabelError("S1.3 output schema binding changed")
    upstream = contract.get("upstream_process_record", {})
    process_schema_path = _project_path(str(upstream.get("schema_path", "")))
    structural_manifest_path = _project_path(
        str(upstream.get("structural_manifest_path", ""))
    )
    if (
        upstream.get("schema_version") != PROCESS_RECORD_VERSION
        or not process_schema_path.is_file()
        or sha256_file(process_schema_path) != upstream.get("schema_sha256")
        or not structural_manifest_path.is_file()
        or sha256_file(structural_manifest_path)
        != upstream.get("structural_manifest_sha256")
    ):
        raise Stage1LabelError("S1.3 upstream Process Record binding changed")
    baselines = contract.get("baselines", {})
    if set(baselines) != set(BASELINE_IDENTITIES):
        raise Stage1LabelError("S1.3 baseline set changed")
    for baseline, (name, version) in BASELINE_IDENTITIES.items():
        if (
            baselines[baseline].get("method_name") != name
            or baselines[baseline].get("method_version") != version
        ):
            raise Stage1LabelError(f"S1.3 {baseline} identity changed")
    p1 = baselines["P1"]
    if (
        p1.get("whitespace_normalization") != "collapse_unicode_whitespace"
        or p1.get("action_boundary_characters") != ACTION_BOUNDARY_CHARACTERS
        or p1.get("case_normalization") != "none"
        or p1.get("lemmatization") is not False
        or p1.get("part_of_speech_tagging") is not False
        or p1.get("controlled_vocabulary") is not False
    ):
        raise Stage1LabelError("S1.3 P1 surface-split semantics changed")
    determinism = contract.get("determinism", {})
    if determinism != {
        "activity_records": "ascending_activity_id",
        "lane_labels": "unique_nonempty_labels_ascending_codepoint",
        "process_record_hash": "canonical_json_utf8_sort_keys_compact",
        "unknown_baseline": "reject",
        "invalid_process_record": "reject",
        "output_tampering": "reject",
    }:
        raise Stage1LabelError("S1.3 determinism contract changed")
    safety = contract.get("safety", {})
    if safety != {
        "fixture_scope": "synthetic_only",
        "formal_bpmn_read": False,
        "human_gold_read_or_modified": False,
        "llm_api_called": False,
        "network_called": False,
        "learned_model_used": False,
        "performance_evaluation": False,
        "formal_label_records_written": False,
        "no_overwrite": True,
    }:
        raise Stage1LabelError("S1.3 safety boundary changed")
    return contract


def canonical_process_record_sha256(process_record: Mapping[str, Any]) -> str:
    payload = json.dumps(
        process_record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _lane_labels(process_record: Mapping[str, Any], lane_ids: list[str]) -> list[str]:
    lane_names = {item["id"]: item["name"] for item in process_record["lanes"]}
    return sorted(
        {
            lane_names[lane_id]
            for lane_id in lane_ids
            if lane_names[lane_id].strip()
        }
    )


def _p1_label_fields(raw_label: str) -> tuple[str | None, str | None, str]:
    normalized = " ".join(raw_label.split())
    if not normalized:
        return None, None, "empty_label"
    first, separator, remainder = normalized.partition(" ")
    action = first.strip(ACTION_BOUNDARY_CHARACTERS)
    if not action:
        return None, None, "unparsed_label"
    business_object = remainder.strip() if separator else ""
    if business_object:
        return action, business_object, "parsed_action_object"
    return action, None, "parsed_action_only"


def render_label_semantics(
    process_record: Mapping[str, Any],
    *,
    baseline: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    process_report = validate_process_record(process_record)
    if not process_report.valid:
        raise Stage1LabelError(
            "invalid upstream Process Record: " + "; ".join(process_report.errors)
        )
    if baseline not in BASELINE_IDENTITIES or baseline not in contract.get("baselines", {}):
        raise Stage1LabelError(f"unknown S1.3 baseline: {baseline}")
    method_name, method_version = BASELINE_IDENTITIES[baseline]
    activities: list[dict[str, Any]] = []
    for activity in process_record["activities"]:
        lane_labels = _lane_labels(process_record, activity["lane_ids"])
        raw_label = activity["name"]
        if baseline == "P0":
            actor_surface = None
            actor_status = "p0_not_inferred"
            action_surface = None
            business_object_surface = None
            label_status = "raw_only"
        else:
            if len(lane_labels) == 1:
                actor_surface = lane_labels[0]
                actor_status = "single_lane_label"
            elif lane_labels:
                actor_surface = None
                actor_status = "ambiguous_lane_labels"
            else:
                actor_surface = None
                actor_status = "no_lane_label"
            action_surface, business_object_surface, label_status = _p1_label_fields(
                raw_label
            )
        activities.append(
            {
                "activity_id": activity["id"],
                "raw_label": raw_label,
                "lane_labels": lane_labels,
                "actor_surface": actor_surface,
                "actor_status": actor_status,
                "action_surface": action_surface,
                "business_object_surface": business_object_surface,
                "label_status": label_status,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "process_record": {
            "schema_version": process_record["schema_version"],
            "process_id": process_record["process_id"],
            "sha256": canonical_process_record_sha256(process_record),
        },
        "method": {
            "name": method_name,
            "version": method_version,
            "baseline": baseline,
            "language": "en",
            "learned_model": False,
        },
        "activities": activities,
    }


def _exact_keys(value: Any, expected: set[str], label: str, errors: list[str]) -> bool:
    if not isinstance(value, Mapping):
        errors.append(f"{label} must be an object")
        return False
    if set(value) != expected:
        errors.append(f"{label} properties changed")
        return False
    return True


def _manual_schema_errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _exact_keys(
        record, {"schema_version", "process_record", "method", "activities"}, "record", errors
    ):
        return errors
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version changed")
    process = record.get("process_record")
    if _exact_keys(process, {"schema_version", "process_id", "sha256"}, "process_record", errors):
        if process.get("schema_version") != PROCESS_RECORD_VERSION:
            errors.append("process_record.schema_version changed")
        if not isinstance(process.get("process_id"), str) or not process["process_id"]:
            errors.append("process_record.process_id must be non-empty")
        digest = process.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            errors.append("process_record.sha256 must be lowercase SHA-256")
    method = record.get("method")
    method_keys = {"name", "version", "baseline", "language", "learned_model"}
    if _exact_keys(method, method_keys, "method", errors):
        if method.get("baseline") not in BASELINE_IDENTITIES:
            errors.append("method.baseline changed")
        else:
            expected_name, expected_version = BASELINE_IDENTITIES[method["baseline"]]
            if method.get("name") != expected_name or method.get("version") != expected_version:
                errors.append("method identity disagrees with baseline")
        if method.get("language") != "en" or method.get("learned_model") is not False:
            errors.append("method language/model boundary changed")
    activities = record.get("activities")
    if not isinstance(activities, list):
        errors.append("activities must be an array")
        return errors
    activity_keys = {
        "activity_id",
        "raw_label",
        "lane_labels",
        "actor_surface",
        "actor_status",
        "action_surface",
        "business_object_surface",
        "label_status",
    }
    for index, activity in enumerate(activities):
        label = f"activities[{index}]"
        if not _exact_keys(activity, activity_keys, label, errors):
            continue
        if not isinstance(activity.get("activity_id"), str) or not activity["activity_id"]:
            errors.append(f"{label}.activity_id must be non-empty")
        if not isinstance(activity.get("raw_label"), str):
            errors.append(f"{label}.raw_label must be a string")
        lanes = activity.get("lane_labels")
        if (
            not isinstance(lanes, list)
            or any(not isinstance(item, str) for item in lanes)
            or len(lanes) != len(set(lanes))
        ):
            errors.append(f"{label}.lane_labels must contain unique strings")
        for field in ("actor_surface", "action_surface", "business_object_surface"):
            if activity.get(field) is not None and not isinstance(activity.get(field), str):
                errors.append(f"{label}.{field} must be string or null")
        if activity.get("actor_status") not in ACTOR_STATUSES:
            errors.append(f"{label}.actor_status changed")
        if activity.get("label_status") not in LABEL_STATUSES:
            errors.append(f"{label}.label_status changed")
    return errors


def validate_label_semantics(
    record: Mapping[str, Any],
    *,
    process_record: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> LabelValidationReport:
    if not isinstance(record, Mapping):
        return LabelValidationReport(False, False, ("record must be an object",))
    schema_errors = _manual_schema_errors(record)
    if schema_errors:
        return LabelValidationReport(False, False, tuple(schema_errors))
    try:
        expected = render_label_semantics(
            process_record,
            baseline=record["method"]["baseline"],
            contract=contract,
        )
    except Stage1LabelError as exc:
        return LabelValidationReport(True, False, (str(exc),))
    if record != expected:
        return LabelValidationReport(
            True,
            False,
            ("label sidecar disagrees with deterministic Process Record derivation",),
        )
    return LabelValidationReport(True, True, ())


def clone_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deep copy for callers that need isolated sidecars."""

    return copy.deepcopy(dict(record))

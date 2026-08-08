"""Exact membership gate for the shared Stage 1/Stage 3 GDPR7 extension."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage1_formal_dataset import (
    Stage1FormalDatasetError,
    build_formal_blank_annotation_pack,
    build_formal_process_records,
    load_formal_membership_contract,
    validate_editable_annotation_pack,
)


CONFIG_REL = "configs/datasets/stage1_stage3_gdpr7_v1.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/stage1_formal_dataset.py"
BUILDER_REL = "scripts/build_stage1_gdpr7.py"
VERIFIER_REL = "scripts/verify_stage1_stage3_gdpr7.py"
PROCESS_RECORDS_REL = "data/development/human_review/stage1_gdpr7_process_records_v1.json"
BLANK_REL = "data/development/human_review/stage1_gdpr7_annotation_blank_v1.json"
EDITABLE_REL = "data/development/human_review/stage1_gdpr7_human_correction_v1.json"
MANIFEST_REL = "outputs/reports/s15_s31_gdpr7_membership_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class Stage1MembershipExpectations:
    config_sha256: str = "6bb2c0da4c51d06368bb858057374d9199e8d2ef494b6cb5c122be8744e11a42"
    implementation_sha256: str = "86a33bc6f4da6cd40feda9ea7ec65a74cbae1b5c09366c5bdcdf65e59d7e8486"
    builder_sha256: str = "a542a0062166e90edfa6d1059f486b9f9952eecef7ba03f0f7c2f62ba736426c"
    verifier_sha256: str = "74f06c2ea7d58b263a0ebddb304494fa2ad7c24510861b2a9d63491936dfcfd0"
    process_records_sha256: str = "d4d61f46091a4063e8db2d405f893df6c3951ed4ee77b62deebe27fa35d48487"
    blank_sha256: str = "b5fdf7ce323527d5992bcef3d7a7e3a3fd1ee1ecaf149de4b941e89882c7f43b"
    manifest_sha256: str = "697bb8bfa34a944e0105606ae9ced75b4290e425dc7e209cfb0a37132388634c"


STAGE1_MEMBERSHIP_EXPECTATIONS = Stage1MembershipExpectations()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1FormalDatasetError(f"invalid GDPR7 gate JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1FormalDatasetError(f"GDPR7 gate JSON root must be an object: {path}")
    return value


def verify_stage1_membership_gate(
    project_root: Path,
    *,
    expectations: Stage1MembershipExpectations = STAGE1_MEMBERSHIP_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "config": root / CONFIG_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "builder": root / BUILDER_REL,
        "verifier": root / VERIFIER_REL,
        "process_records": root / PROCESS_RECORDS_REL,
        "blank": root / BLANK_REL,
        "editable": root / EDITABLE_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "stage1_membership_artifact_missing", f"Missing {name}: {path}")
    if errors:
        return {
            "membership_ready": False,
            "errors": errors,
            "blockers": [item["code"] for item in errors],
        }
    hashes = {
        name: _sha256(path)
        for name, path in paths.items()
        if name not in {"editable", "contract"}
    }
    for name, expected in (
        ("config", expectations.config_sha256),
        ("implementation", expectations.implementation_sha256),
        ("builder", expectations.builder_sha256),
        ("verifier", expectations.verifier_sha256),
        ("process_records", expectations.process_records_sha256),
        ("blank", expectations.blank_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"stage1_membership_{name}_hash_mismatch",
            f"Stage 1/Stage 3 GDPR7 {name} SHA-256 changed",
        )
    try:
        config = load_formal_membership_contract(paths["config"])
        manifest = _load(paths["manifest"])
        process_document = _load(paths["process_records"])
        blank = _load(paths["blank"])
        editable = _load(paths["editable"])
        experiment_contract = _load(paths["contract"])
        expected_records = build_formal_process_records(config)
        expected_blank = build_formal_blank_annotation_pack(expected_records, config)
        editable_report = validate_editable_annotation_pack(editable, expected_records, config)
    except Stage1FormalDatasetError as exc:
        require(False, "stage1_membership_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        process_document = {}
        blank = {}
        experiment_contract = {}
        expected_records = []
        expected_blank = {}
        editable = {}
        editable_report = {"valid": False, "freeze_ready": False, "errors": [str(exc)]}
    require(
        process_document
        == {"dataset_id": "stage1_stage3_gdpr7_extension_v1", "records": expected_records},
        "stage1_membership_process_records_mismatch",
        "Stored formal Process Records differ from the deterministic seven-file parse",
    )
    require(
        blank == expected_blank,
        "stage1_membership_blank_template_mismatch",
        "Immutable GDPR7 blank annotation template changed",
    )
    require(
        editable_report.get("valid") is True,
        "stage1_membership_editable_pack_invalid",
        f"Editable GDPR7 annotation pack is invalid: {editable_report.get('errors', [])[:6]}",
    )
    artifacts = manifest.get("artifacts", {}) if isinstance(manifest, Mapping) else {}
    require(
        manifest.get("schema_version") == "stage1_stage3_gdpr7_verification_manifest@1.0.0"
        and manifest.get("run_id") == "s15_s31_gdpr7_membership_v1"
        and manifest.get("task_ids") == ["S1.5", "S3.1"]
        and manifest.get("status") == "succeeded_membership_and_blank_review_ready"
        and manifest.get("dataset")
        == {
            "dataset_id": "stage1_stage3_gdpr7_extension_v1",
            "claim_label": "all-seven GDPR BPMN extension",
            "membership_count": 7,
            "membership_payload_sha256": "e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d",
            "sun_original_four_identified": False,
            "shared_stage1_stage3_membership": True,
        }
        and all(
            artifacts.get(artifact_name, {}).get("path") == relative
            and artifacts.get(artifact_name, {}).get("sha256") == hashes[hash_name]
            for artifact_name, relative, hash_name in (
                ("config", CONFIG_REL, "config"),
                ("implementation", IMPLEMENTATION_REL, "implementation"),
                ("builder", BUILDER_REL, "builder"),
                ("verifier", VERIFIER_REL, "verifier"),
                ("process_records", PROCESS_RECORDS_REL, "process_records"),
                ("blank_template", BLANK_REL, "blank"),
            )
        )
        and artifacts.get("editable_pack", {}).get("path") == EDITABLE_REL
        and artifacts.get("editable_pack", {}).get("mutable_only_by_human_review") is True,
        "stage1_membership_manifest_identity_mismatch",
        "GDPR7 verification manifest identity or artifact locks changed",
    )
    inputs = manifest.get("inputs", []) if isinstance(manifest, Mapping) else []
    require(
        len(inputs) == 7
        and all(item.get("byte_exact_copy_verified") is True for item in inputs)
        and [item.get("input_id") for item in inputs]
        == [item.get("input_id") for item in config.get("membership", {}).get("files", [])]
        and manifest.get("promotion", {}).get("user_approved") is True
        and manifest.get("promotion", {}).get("source_store_modified") is False,
        "stage1_membership_promotion_evidence_mismatch",
        "GDPR7 byte-exact promotion evidence changed",
    )
    process_summary = manifest.get("process_records", {}) if isinstance(manifest, Mapping) else {}
    annotation_summary = manifest.get("annotation", {}) if isinstance(manifest, Mapping) else {}
    require(
        process_summary.get("count") == 7
        and process_summary.get("dataset_global_process_ids_unique") is True
        and process_summary.get("identity_adapter") == "stage1_formal_input_id_adapter@1.0.0"
        and process_summary.get("duplicate_raw_process_ids")
        == ["sid-C2A304F9-1DE1-4882-B3BE-60ACE45FABE7"]
        and annotation_summary.get("records") == 7
        and annotation_summary.get("activities") == 45
        and annotation_summary.get("label_fields") == 135
        and annotation_summary.get("gold_auto_filled") is False,
        "stage1_membership_parse_or_annotation_summary_mismatch",
        "GDPR7 parse or blank annotation summary changed",
    )
    safety = manifest.get("safety", {}) if isinstance(manifest, Mapping) else {}
    require(
        safety
        == {
            "formal_bpmn_read": True,
            "human_gold_read_or_modified": False,
            "gold_auto_filled": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
            "formal_predictions_or_results_written": False,
            "no_artifact_overwrite": True,
        },
        "stage1_membership_safety_mismatch",
        "GDPR7 membership safety boundary changed",
    )
    gate = experiment_contract.get("stage1_formal_membership_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "builder": (BUILDER_REL, hashes["builder"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "process_records": (PROCESS_RECORDS_REL, hashes["process_records"]),
        "blank_template": (BLANK_REL, hashes["blank"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_ids") == ["S1.5", "S3.1"]
        and gate.get("status") == "locked_all_seven_extension_membership"
        and gate.get("formal_membership_ready") is True
        and gate.get("active_formal_bpmn_count") == 7
        and gate.get("shared_stage1_stage3_membership") is True
        and gate.get("claim_label") == "all-seven GDPR BPMN extension"
        and gate.get("sun_original_four_identified") is False
        and gate.get("user_approval_recorded") is True
        and gate.get("human_gold_freeze_ready") is False
        and gate.get("editable_annotation_path") == EDITABLE_REL
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == digest
            for name, (path, digest) in expected_lock.items()
        ),
        "stage1_membership_experiment_contract_mismatch",
        "Experiment contract disagrees with the frozen GDPR7 membership",
    )
    return {
        "membership_ready": not errors,
        "process_records_ready": not errors,
        "annotation_input_ready": not errors,
        "human_gold_freeze_ready": bool(editable_report.get("freeze_ready")) and not errors,
        "active_formal_bpmn_count": 7 if not errors else 0,
        "dataset_id": config.get("dataset_id"),
        "claim_label": config.get("claim_label"),
        "editable_annotation_path": EDITABLE_REL,
        "annotation_summary": editable.get("review_summary", {}) if isinstance(editable, Mapping) else {},
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        IMPLEMENTATION_REL,
        BUILDER_REL,
        VERIFIER_REL,
        PROCESS_RECORDS_REL,
        BLANK_REL,
        EDITABLE_REL,
        MANIFEST_REL,
        CONTRACT_REL,
    ):
        path = root / relative
        try:
            stat = path.stat()
            result.append((relative, stat.st_size, stat.st_mtime_ns))
        except OSError:
            result.append((relative, -1, -1))
    return tuple(result)


@lru_cache(maxsize=8)
def _cached(root: str, fingerprint: tuple[tuple[str, int, int], ...]) -> dict[str, Any]:
    del fingerprint
    return verify_stage1_membership_gate(Path(root))


def get_cached_stage1_membership_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

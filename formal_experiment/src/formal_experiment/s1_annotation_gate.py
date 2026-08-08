"""Exact-hash gate for the S1.5 blank human-annotation protocol."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage1_human_annotation import (
    Stage1AnnotationError,
    load_annotation_contract,
    validate_annotation_pack,
)


CONFIG_REL = "configs/stage1_annotation_protocol_s15.json"
SCHEMA_REL = "configs/schemas/stage1_human_annotation.schema.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/stage1_human_annotation.py"
RUNNER_REL = "scripts/build_stage1_annotation_protocol.py"
VERIFIER_REL = "scripts/verify_stage1_annotation_protocol_s15.py"
GUIDE_REL = "docs/STAGE1_HUMAN_GOLD_GUIDE.md"
FIXTURE_REL = "tests/fixtures/stage1/s13_label_edge_cases.bpmn"
STRUCTURAL_MANIFEST_REL = "outputs/reports/s11_s14_stage1_structural_synthetic_v1.manifest.json"
LABEL_MANIFEST_REL = "outputs/reports/s13_stage1_label_semantics_synthetic_v1.manifest.json"
MANIFEST_REL = "outputs/reports/s15_stage1_annotation_protocol_synthetic_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class Stage1AnnotationExpectations:
    config_sha256: str = "fd13d47108ca9e0962e5791050ce614c1ca67b418ad02e6cfb4d17647bb62305"
    schema_sha256: str = "4d97de0430cce10c5f28c038447472db599b8efccec191801db7aabde1b59744"
    implementation_sha256: str = "33cc64895c3bcb085262138f345640f8a26cd8ae43ae82d25248e1164551f52b"
    runner_sha256: str = "0b98177b62cb032d8f140b603d081a7637fd27c6e0935b8666f478b0cf714bbd"
    verifier_sha256: str = "bd2cb320312263d229438afc896398bf43b5e0b67fb0f50052bdce85265a8359"
    guide_sha256: str = "37b9eb045872084489c82ad186874df3712ba2e58568a7924b92ffd6ac0d9924"
    fixture_sha256: str = "95076fbcd21bd3d9619dcace6f3ddec8fceaa97d9dee887e7dfd9b86924dcc43"
    structural_manifest_sha256: str = "09732e4085386c69f01cde30ef0fce74b8f9e906c7df0e7d8bbffc1f2f881541"
    label_manifest_sha256: str = "c1487f6bb4b149612df4da7375b17747965f43c52a8547b5aefe94318037c5ef"
    manifest_sha256: str = "461bce6d8b78d775bb1f45c8ab9fc15edf4ddb26b9935624fa4f02bc60c3e836"


STAGE1_ANNOTATION_EXPECTATIONS = Stage1AnnotationExpectations()


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
        raise Stage1AnnotationError(f"invalid S1.5 gate JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1AnnotationError(f"S1.5 gate JSON root must be an object: {path}")
    return value


def verify_stage1_annotation_gate(
    project_root: Path,
    *,
    expectations: Stage1AnnotationExpectations = STAGE1_ANNOTATION_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "config": root / CONFIG_REL,
        "schema": root / SCHEMA_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "runner": root / RUNNER_REL,
        "verifier": root / VERIFIER_REL,
        "guide": root / GUIDE_REL,
        "fixture": root / FIXTURE_REL,
        "structural_manifest": root / STRUCTURAL_MANIFEST_REL,
        "label_manifest": root / LABEL_MANIFEST_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "stage1_annotation_artifact_missing", f"Missing {name}: {path}")
    if errors:
        return {"protocol_ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}
    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("schema", expectations.schema_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("guide", expectations.guide_sha256),
        ("fixture", expectations.fixture_sha256),
        ("structural_manifest", expectations.structural_manifest_sha256),
        ("label_manifest", expectations.label_manifest_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"stage1_annotation_{name}_hash_mismatch",
            f"S1.5 annotation {name} SHA-256 changed",
        )
    try:
        config = load_annotation_contract(paths["config"])
        manifest = _load(paths["manifest"])
        label_manifest = _load(paths["label_manifest"])
        experiment_contract = _load(paths["contract"])
    except Stage1AnnotationError as exc:
        require(False, "stage1_annotation_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        label_manifest = {}
        experiment_contract = {}
    artifacts = manifest.get("artifacts", {})
    expected_artifacts = {
        "config": CONFIG_REL,
        "schema": SCHEMA_REL,
        "implementation": IMPLEMENTATION_REL,
        "runner": RUNNER_REL,
        "verifier": VERIFIER_REL,
        "guide": GUIDE_REL,
        "fixture": FIXTURE_REL,
        "structural_manifest": STRUCTURAL_MANIFEST_REL,
        "label_manifest": LABEL_MANIFEST_REL,
    }
    require(
        manifest.get("schema_version")
        == "stage1_annotation_protocol_verification_manifest@1.0.0"
        and manifest.get("run_id") == "s15_stage1_annotation_protocol_synthetic_v1"
        and manifest.get("task_ids") == ["S1.5"]
        and manifest.get("status") == "succeeded_protocol_only"
        and isinstance(artifacts, Mapping)
        and all(
            artifacts.get(name, {}).get("path") == relative
            and artifacts.get(name, {}).get("sha256") == hashes[name]
            for name, relative in expected_artifacts.items()
        ),
        "stage1_annotation_manifest_identity_mismatch",
        "S1.5 manifest identity or artifact lock changed",
    )
    blank_pack = manifest.get("blank_pack", {})
    process_record = label_manifest.get("input_process_record", {})
    report = (
        validate_annotation_pack(
            blank_pack,
            process_records=[process_record],
            contract=config,
        )
        if blank_pack and process_record and config
        else None
    )
    require(
        report is not None
        and report.valid
        and report.freeze_ready is False
        and manifest.get("verification")
        == {
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
        "stage1_annotation_blank_protocol_mismatch",
        "S1.5 blank-pack or review-state evidence changed",
    )
    require(
        manifest.get("failure_semantics")
        == {
            "schema_additional_property_rejected": True,
            "source_binding_tamper_rejected": True,
            "false_freeze_claim_rejected": True,
            "present_null_inconsistency_rejected": True,
        },
        "stage1_annotation_failure_semantics_mismatch",
        "S1.5 fail-closed evidence changed",
    )
    formal_blocker = manifest.get("formal_blocker", {})
    require(
        formal_blocker
        == {
            "code": "stage1_formal_bpmn_membership_not_promoted",
            "active_bpmn_count": 0,
            "provenance_candidate_count": 57,
            "requires_user_approval": True,
            "human_gold_records": 0,
        },
        "stage1_annotation_formal_blocker_mismatch",
        "S1.5 formal membership/Gold blocker changed",
    )
    safety = manifest.get("safety", {})
    require(
        safety
        == {
            "synthetic_fixture_only": True,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "gold_auto_filled": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
            "formal_artifacts_written": False,
        },
        "stage1_annotation_safety_mismatch",
        "S1.5 safety boundary changed",
    )
    gate = experiment_contract.get("stage1_annotation_protocol_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "schema": (SCHEMA_REL, hashes["schema"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "guide": (GUIDE_REL, hashes["guide"]),
        "fixture": (FIXTURE_REL, hashes["fixture"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_ids") == ["S1.5"]
        and gate.get("status") == "verified_offline_protocol_formal_membership_blocked"
        and gate.get("protocol_ready") is True
        and gate.get("formal_membership_ready") is False
        and gate.get("human_gold_freeze_ready") is False
        and gate.get("active_formal_bpmn_count") == 0
        and gate.get("formal_bpmn_read") is False
        and gate.get("human_gold_read_or_modified") is False
        and gate.get("gold_auto_filled") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == digest
            for name, (path, digest) in expected_lock.items()
        ),
        "stage1_annotation_experiment_contract_mismatch",
        "Experiment contract disagrees with S1.5 protocol or blocker boundary",
    )
    protocol_ready = not errors
    return {
        "protocol_ready": protocol_ready,
        "formal_membership_ready": False,
        "human_gold_freeze_ready": False,
        "errors": errors,
        "blockers": [item["code"] for item in errors]
        + (["stage1_formal_bpmn_membership_not_promoted"] if protocol_ready else []),
        "hashes": hashes,
        "active_formal_bpmn_count": 0,
        "human_gold_records": 0,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        SCHEMA_REL,
        IMPLEMENTATION_REL,
        RUNNER_REL,
        VERIFIER_REL,
        GUIDE_REL,
        FIXTURE_REL,
        STRUCTURAL_MANIFEST_REL,
        LABEL_MANIFEST_REL,
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
    return verify_stage1_annotation_gate(Path(root))


def get_cached_stage1_annotation_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

"""Exact-hash gate for the verified synthetic S1.3 P0/P1 contract."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage1_label_semantics import (
    Stage1LabelError,
    load_label_contract,
    validate_label_semantics,
)


CONFIG_REL = "configs/stage1_label_semantics_s13.json"
SCHEMA_REL = "configs/schemas/stage1_label_semantics.schema.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/stage1_label_semantics.py"
RUNNER_REL = "scripts/run_stage1_label_semantics.py"
VERIFIER_REL = "scripts/verify_stage1_label_semantics_s13.py"
FIXTURE_REL = "tests/fixtures/stage1/s13_label_edge_cases.bpmn"
STRUCTURAL_MANIFEST_REL = "outputs/reports/s11_s14_stage1_structural_synthetic_v1.manifest.json"
MANIFEST_REL = "outputs/reports/s13_stage1_label_semantics_synthetic_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class Stage1LabelExpectations:
    config_sha256: str = "94a76a365b6662a2051ed1fe0d0e9a08bb9582055475b5b6cb796489917d2a88"
    schema_sha256: str = "32b7f6685c3931dce677924456618231563f253c39b2a6a7441acc63e55feda6"
    implementation_sha256: str = "069e005731b1481656be05c8e38a6bfdaafe7fbaa20caae081607f73d9d271ca"
    runner_sha256: str = "b11e670fbcf9e22378025677a6f532dc0bbc21181e4e9eace9cc09d6cf2c9697"
    verifier_sha256: str = "573f48189b2d288b64f22ae458c8c9e9ca2ecacead6224d121c316b2b6eeac39"
    fixture_sha256: str = "95076fbcd21bd3d9619dcace6f3ddec8fceaa97d9dee887e7dfd9b86924dcc43"
    structural_manifest_sha256: str = "4f0121b621c0fe648dc93d743ef11f8be93367b18db35c7a430c95cf6950366e"
    manifest_sha256: str = "21df677087988a63454e572f994899674ee9eacf63352d2d063b103ad668bb69"


STAGE1_LABEL_EXPECTATIONS = Stage1LabelExpectations()


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
        raise Stage1LabelError(f"invalid S1.3 gate JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1LabelError(f"S1.3 gate JSON root must be an object: {path}")
    return value


def verify_stage1_label_semantics_gate(
    project_root: Path,
    *,
    expectations: Stage1LabelExpectations = STAGE1_LABEL_EXPECTATIONS,
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
        "fixture": root / FIXTURE_REL,
        "structural_manifest": root / STRUCTURAL_MANIFEST_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "stage1_label_artifact_missing", f"Missing {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("schema", expectations.schema_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("fixture", expectations.fixture_sha256),
        ("structural_manifest", expectations.structural_manifest_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"stage1_label_{name}_hash_mismatch",
            f"S1.3 label {name} SHA-256 changed",
        )

    try:
        config = load_label_contract(paths["config"])
        manifest = _load(paths["manifest"])
        experiment_contract = _load(paths["contract"])
    except Stage1LabelError as exc:
        require(False, "stage1_label_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        experiment_contract = {}

    artifacts = manifest.get("artifacts", {})
    expected_artifacts = {
        "config": CONFIG_REL,
        "schema": SCHEMA_REL,
        "implementation": IMPLEMENTATION_REL,
        "runner": RUNNER_REL,
        "verifier": VERIFIER_REL,
        "fixture": FIXTURE_REL,
        "structural_manifest": STRUCTURAL_MANIFEST_REL,
    }
    require(
        manifest.get("schema_version")
        == "stage1_label_semantics_verification_manifest@1.0.0"
        and manifest.get("run_id") == "s13_stage1_label_semantics_synthetic_v1"
        and manifest.get("task_ids") == ["S1.3"]
        and manifest.get("status") == "succeeded"
        and isinstance(artifacts, Mapping)
        and all(
            artifacts.get(name, {}).get("path") == relative
            and artifacts.get(name, {}).get("sha256") == hashes[name]
            for name, relative in expected_artifacts.items()
        ),
        "stage1_label_manifest_identity_mismatch",
        "S1.3 manifest identity or artifact lock changed",
    )
    process_record = manifest.get("input_process_record", {})
    p0 = manifest.get("p0_verification", {})
    p1 = manifest.get("p1_verification", {})
    p0_record = p0.get("record", {}) if isinstance(p0, Mapping) else {}
    p1_record = p1.get("record", {}) if isinstance(p1, Mapping) else {}
    p0_report = (
        validate_label_semantics(p0_record, process_record=process_record, contract=config)
        if p0_record and process_record and config
        else None
    )
    p1_report = (
        validate_label_semantics(p1_record, process_record=process_record, contract=config)
        if p1_record and process_record and config
        else None
    )
    require(
        p0.get("activity_count") == 6
        and p0.get("semantic_inference_count") == 0
        and p0.get("raw_only_count") == 6
        and p0_report is not None
        and p0_report.valid,
        "stage1_label_p0_verification_mismatch",
        "S1.3 P0 no-inference evidence changed",
    )
    require(
        p1.get("activity_count") == 6
        and p1.get("actor_status_counts")
        == {
            "single_lane_label": 4,
            "no_lane_label": 1,
            "ambiguous_lane_labels": 1,
        }
        and p1.get("label_status_counts")
        == {
            "empty_label": 1,
            "unparsed_label": 1,
            "parsed_action_only": 1,
            "parsed_action_object": 3,
        }
        and p1_report is not None
        and p1_report.valid,
        "stage1_label_p1_verification_mismatch",
        "S1.3 P1 surface-split evidence changed",
    )
    require(
        manifest.get("failure_semantics")
        == {
            "unknown_baseline_rejected": True,
            "schema_additional_property_rejected": True,
            "tampered_surface_rejected": True,
        },
        "stage1_label_failure_semantics_mismatch",
        "S1.3 fail-closed evidence changed",
    )
    safety = manifest.get("safety", {})
    require(
        safety
        == {
            "synthetic_fixture_only": True,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "learned_model_used": False,
            "performance_evaluation": False,
            "formal_label_records_written": False,
        },
        "stage1_label_safety_mismatch",
        "S1.3 safety boundary changed",
    )

    gate = experiment_contract.get("stage1_label_semantics_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "schema": (SCHEMA_REL, hashes["schema"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "fixture": (FIXTURE_REL, hashes["fixture"]),
        "upstream_structural_manifest": (
            STRUCTURAL_MANIFEST_REL,
            hashes["structural_manifest"],
        ),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_ids") == ["S1.3"]
        and gate.get("status") == "verified_offline_p0_p1_contract"
        and gate.get("ready") is True
        and gate.get("output_schema_version") == "stage1_label_semantics@1.0.0"
        and gate.get("p0_raw_no_inference_verified") is True
        and gate.get("p1_deterministic_surface_split_verified") is True
        and gate.get("formal_bpmn_read") is False
        and gate.get("human_gold_read_or_modified") is False
        and gate.get("learned_model_used") is False
        and gate.get("performance_evaluation") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == digest
            for name, (path, digest) in expected_lock.items()
        ),
        "stage1_label_experiment_contract_mismatch",
        "Experiment contract disagrees with S1.3 artifacts or boundary",
    )
    return {
        "ready": not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "synthetic_fixture_only": safety.get("synthetic_fixture_only")
        if isinstance(safety, Mapping)
        else None,
        "performance_evaluation": safety.get("performance_evaluation")
        if isinstance(safety, Mapping)
        else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        SCHEMA_REL,
        IMPLEMENTATION_REL,
        RUNNER_REL,
        VERIFIER_REL,
        FIXTURE_REL,
        STRUCTURAL_MANIFEST_REL,
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
    return verify_stage1_label_semantics_gate(Path(root))


def get_cached_stage1_label_semantics_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

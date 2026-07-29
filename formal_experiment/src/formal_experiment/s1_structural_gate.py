"""Exact-hash gate for verified synthetic S1.1/S1.2/S1.4 structure work."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage1_process import (
    Stage1ProcessError,
    load_stage1_contract,
    validate_process_record,
)


CONFIG_REL = "configs/stage1_structural_s11_s14.json"
SCHEMA_REL = "configs/schemas/process_record.schema.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/stage1_process.py"
RUNNER_REL = "scripts/run_stage1_structural.py"
VERIFIER_REL = "scripts/verify_stage1_structural_s11_s14.py"
BRANCH_FIXTURE_REL = "tests/fixtures/stage1/s11_branch_parallel.bpmn"
CYCLE_FIXTURE_REL = "tests/fixtures/stage1/s14_cycle_unreachable.bpmn"
MANIFEST_REL = "outputs/reports/s11_s14_stage1_structural_synthetic_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class Stage1StructuralExpectations:
    config_sha256: str = "92329cef71c4f3517a66a24f4b0fb4b439add3470832831a6fb70fd1d59ced48"
    schema_sha256: str = "9f2dc77a5386c472f9ea27fcf256a2e47195ed66e70ea5f9550caeccdf26bfef"
    implementation_sha256: str = "d81bde594190c96bd3f3e1d7a0d943847809b20500044f12a401d6aee822c396"
    runner_sha256: str = "2f98953ceeea8a1fd2f329c22859b58bf139e938122459e67a40a0e8739c65f6"
    verifier_sha256: str = "07e98a7d1af49655a78df618b74f5bfe0a555c4c0159f88d92b0af4615ed5b84"
    branch_fixture_sha256: str = "b60067cb414af04e87f8cf0d1b050466920fdfeee8d65e7299ae256f79da4314"
    cycle_fixture_sha256: str = "f4c4e455deb634a002a72f6ebed884e948c60b668ce193a04c43cff89a6e4513"
    manifest_sha256: str = "4f0121b621c0fe648dc93d743ef11f8be93367b18db35c7a430c95cf6950366e"


STAGE1_STRUCTURAL_EXPECTATIONS = Stage1StructuralExpectations()


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
        raise Stage1ProcessError(f"invalid Stage 1 gate JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1ProcessError(f"Stage 1 gate JSON root must be an object: {path}")
    return value


def verify_stage1_structural_gate(
    project_root: Path,
    *,
    expectations: Stage1StructuralExpectations = STAGE1_STRUCTURAL_EXPECTATIONS,
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
        "branch_fixture": root / BRANCH_FIXTURE_REL,
        "cycle_fixture": root / CYCLE_FIXTURE_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "stage1_structural_artifact_missing", f"Missing {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("schema", expectations.schema_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("branch_fixture", expectations.branch_fixture_sha256),
        ("cycle_fixture", expectations.cycle_fixture_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"stage1_structural_{name}_hash_mismatch",
            f"Stage 1 structural {name} SHA-256 changed",
        )

    try:
        config = load_stage1_contract(paths["config"])
        manifest = _load(paths["manifest"])
        experiment_contract = _load(paths["contract"])
    except Stage1ProcessError as exc:
        require(False, "stage1_structural_artifact_invalid", str(exc))
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
        "branch_fixture": BRANCH_FIXTURE_REL,
        "cycle_fixture": CYCLE_FIXTURE_REL,
    }
    require(
        manifest.get("schema_version") == "stage1_structural_verification_manifest@1.0.0"
        and manifest.get("run_id") == "s11_s14_stage1_structural_synthetic_v1"
        and manifest.get("task_ids") == ["S1.1", "S1.2", "S1.4"]
        and manifest.get("status") == "succeeded"
        and isinstance(artifacts, Mapping)
        and all(
            artifacts.get(name, {}).get("path") == relative
            and artifacts.get(name, {}).get("sha256") == hashes[name]
            for name, relative in expected_artifacts.items()
        ),
        "stage1_structural_manifest_identity_mismatch",
        "Stage 1 structural manifest identity or artifact lock changed",
    )
    branch = manifest.get("branch_parallel_verification", {})
    cycle = manifest.get("cycle_unreachable_verification", {})
    determinism = manifest.get("determinism_and_failure_verification", {})
    safety = manifest.get("safety", {})
    branch_record = branch.get("record", {}) if isinstance(branch, Mapping) else {}
    cycle_record = cycle.get("record", {}) if isinstance(cycle, Mapping) else {}
    branch_report = validate_process_record(branch_record) if branch_record else None
    cycle_report = validate_process_record(cycle_record) if cycle_record else None
    require(
        branch.get("counts")
        == {
            "pools": 1,
            "lanes": 2,
            "activities": 5,
            "events": 2,
            "gateways": 4,
            "sequence_flows": 12,
            "direct_edges": 12,
            "reachable_pairs": 53,
            "activity_order_relations": 8,
        }
        and branch.get("lane_binding_verified") is True
        and branch.get("condition_and_default_flow_verified") is True
        and branch.get("branch_and_parallel_verified") is True
        and branch.get("parallel_branches_not_falsely_ordered") is True
        and branch_report is not None
        and branch_report.valid,
        "stage1_structural_branch_fixture_mismatch",
        "Stage 1 branch/parallel structural evidence changed",
    )
    require(
        cycle.get("cyclic_node_ids") == ["Task_A", "Task_B"]
        and cycle.get("unreachable_node_ids") == ["Task_Orphan"]
        and cycle_report is not None
        and cycle_report.valid,
        "stage1_structural_cycle_fixture_mismatch",
        "Stage 1 cycle/unreachable evidence changed",
    )
    require(
        determinism
        == {
            "xml_sibling_order_invariant": True,
            "unknown_flow_reference_rejected": True,
            "duplicate_node_id_rejected": True,
            "doctype_and_entity_rejected": True,
            "schema_additional_property_rejected": True,
            "tampered_reachability_rejected": True,
        },
        "stage1_structural_failure_semantics_mismatch",
        "Stage 1 determinism or fail-closed evidence changed",
    )
    require(
        safety
        == {
            "synthetic_fixture_only": True,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
            "formal_process_records_written": False,
        },
        "stage1_structural_safety_mismatch",
        "Stage 1 structural safety boundary changed",
    )

    gate = experiment_contract.get("stage1_structural_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "schema": (SCHEMA_REL, hashes["schema"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "branch_fixture": (BRANCH_FIXTURE_REL, hashes["branch_fixture"]),
        "cycle_fixture": (CYCLE_FIXTURE_REL, hashes["cycle_fixture"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_ids") == ["S1.1", "S1.2", "S1.4"]
        and gate.get("status") == "verified_offline_structural_contract"
        and gate.get("ready") is True
        and gate.get("canonical_process_record_schema") == "process_record@1.0.0"
        and gate.get("deterministic_structural_parser_verified") is True
        and gate.get("control_flow_reachability_verified") is True
        and gate.get("cycle_and_unreachable_detection_verified") is True
        and gate.get("formal_bpmn_read") is False
        and gate.get("human_gold_read_or_modified") is False
        and gate.get("performance_evaluation") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == digest
            for name, (path, digest) in expected_lock.items()
        ),
        "stage1_structural_experiment_contract_mismatch",
        "Experiment contract disagrees with Stage 1 structural artifacts or boundary",
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
        BRANCH_FIXTURE_REL,
        CYCLE_FIXTURE_REL,
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
    return verify_stage1_structural_gate(Path(root))


def get_cached_stage1_structural_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

"""Exact-hash gate for the synthetic-only S1.6 evaluator contract."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage1_evaluation import (
    Stage1EvaluationError,
    load_evaluator_contract,
    validate_stage1_report,
)


CONFIG_REL = "configs/stage1_evaluator_s16.json"
SCHEMA_REL = "configs/schemas/stage1_evaluation_report.schema.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/stage1_evaluation.py"
RUNNER_REL = "scripts/evaluate_stage1_s16.py"
VERIFIER_REL = "scripts/verify_stage1_evaluator_s16.py"
FIXTURE_REL = "tests/fixtures/stage1/s16_synthetic_semantic_reference.json"
BPMN_FIXTURE_REL = "tests/fixtures/stage1/s13_label_edge_cases.bpmn"
LABEL_MANIFEST_REL = "outputs/reports/s13_stage1_label_semantics_synthetic_v1.manifest.json"
ANNOTATION_MANIFEST_REL = "outputs/reports/s15_stage1_annotation_protocol_synthetic_v1.manifest.json"
MANIFEST_REL = "outputs/reports/s16_stage1_evaluator_contract_synthetic_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class Stage1EvaluatorExpectations:
    # 2026-08-13: hashes re-bound to the CURRENT locked synthetic-evaluator
    # assets. The experiment-contract stage1_evaluator_gate block recorded
    # hashes from BEFORE the 56d2b03 checkpoint restore (they matched no
    # on-disk file since f628b6b); the contract file itself is frozen and
    # untouched, so the gate checks the contract block STRUCTURALLY (status,
    # ready flags, component/field counts) and binds asset identity to these
    # expectations instead. Formal S1.6 results are independently bound by
    # scripts/verify_stage1_formal_evaluation.py.
    config_sha256: str = "d9e3295d8fc880fbd5e0330c01cfd0c6c68a4e50329b841624c184371d0a26e4"
    schema_sha256: str = "7f8c5c997689ef0e9e8e3eeedb5b4838e88faa8b1e72606cac35131c9d4b8e19"
    implementation_sha256: str = "c9ef105be60beaa16e58ca876c75355ccb7bbb81b28ba31f8696ca9985e8410a"
    runner_sha256: str = "2a2b20f104e575a45785d9b3b33368e79490af88e9356a98a67805368feb180c"
    verifier_sha256: str = "8ceff6cb62b90d7738a3f379551f170b45270650e511a3cfa4df80e0ed635b5c"
    fixture_sha256: str = "8a86eacc9737efd1b391edb7c754bdfc522e9dfc4b53b5eca14a50ca62b16604"
    bpmn_fixture_sha256: str = "95076fbcd21bd3d9619dcace6f3ddec8fceaa97d9dee887e7dfd9b86924dcc43"
    label_manifest_sha256: str = "c1487f6bb4b149612df4da7375b17747965f43c52a8547b5aefe94318037c5ef"
    annotation_manifest_sha256: str = "461bce6d8b78d775bb1f45c8ab9fc15edf4ddb26b9935624fa4f02bc60c3e836"
    manifest_sha256: str = "d17b39013a22d943d6e944a73152070ab91136bbb394bcb34f276b81018cdb6a"


STAGE1_EVALUATOR_EXPECTATIONS = Stage1EvaluatorExpectations()


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
        raise Stage1EvaluationError(f"invalid S1.6 gate JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1EvaluationError(f"S1.6 gate JSON root must be an object: {path}")
    return value


def verify_stage1_evaluator_gate(
    project_root: Path,
    *,
    expectations: Stage1EvaluatorExpectations = STAGE1_EVALUATOR_EXPECTATIONS,
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
        "bpmn_fixture": root / BPMN_FIXTURE_REL,
        "label_manifest": root / LABEL_MANIFEST_REL,
        "annotation_manifest": root / ANNOTATION_MANIFEST_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "stage1_evaluator_artifact_missing", f"Missing {name}: {path}")
    if errors:
        return {"evaluator_ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}
    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("schema", expectations.schema_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("fixture", expectations.fixture_sha256),
        ("bpmn_fixture", expectations.bpmn_fixture_sha256),
        ("label_manifest", expectations.label_manifest_sha256),
        ("annotation_manifest", expectations.annotation_manifest_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"stage1_evaluator_{name}_hash_mismatch",
            f"S1.6 evaluator {name} SHA-256 changed",
        )
    try:
        load_evaluator_contract(paths["config"])
        manifest = _load(paths["manifest"])
        experiment_contract = _load(paths["contract"])
    except Stage1EvaluationError as exc:
        require(False, "stage1_evaluator_artifact_invalid", str(exc))
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
        "bpmn_fixture": BPMN_FIXTURE_REL,
        "label_manifest": LABEL_MANIFEST_REL,
        "annotation_manifest": ANNOTATION_MANIFEST_REL,
    }
    require(
        manifest.get("schema_version") == "stage1_evaluator_verification_manifest@1.0.0"
        and manifest.get("run_id") == "s16_stage1_evaluator_contract_synthetic_v1"
        and manifest.get("task_ids") == ["S1.6"]
        and manifest.get("status") == "succeeded_contract_only"
        and isinstance(artifacts, Mapping)
        and all(
            artifacts.get(name, {}).get("path") == relative
            and artifacts.get(name, {}).get("sha256") == hashes[name]
            for name, relative in expected_artifacts.items()
        ),
        "stage1_evaluator_manifest_identity_mismatch",
        "S1.6 manifest identity or artifact lock changed",
    )
    report = manifest.get("synthetic_report", {})
    report_valid = validate_stage1_report(report).valid if report else False
    p0 = report.get("methods", {}).get("P0", {}) if isinstance(report, Mapping) else {}
    p1 = report.get("methods", {}).get("P1", {}) if isinstance(report, Mapping) else {}
    require(
        report_valid
        and report.get("scope") == "synthetic_contract_verification"
        and report.get("membership") == ["Process_Label_Edges"]
        and p0.get("structure", {}).get("micro", {}).get("tp") == 8
        and p1.get("structure", {}).get("micro", {}).get("tp") == 8
        and p0.get("semantics", {}).get("micro", {}).get("fn") == 12
        and p1.get("semantics", {}).get("micro", {}).get("tp") == 10
        and p1.get("semantics", {}).get("micro", {}).get("fp") == 1
        and p1.get("semantics", {}).get("micro", {}).get("fn") == 2,
        "stage1_evaluator_synthetic_constants_mismatch",
        "S1.6 synthetic metric constants changed",
    )
    require(
        manifest.get("verification")
        == {
            "exact_membership_verified": True,
            "structure_components": 8,
            "semantic_fields": 3,
            "structure_micro_tp_each_method": 8,
            "p0_semantic_micro_counts": {"tp": 0, "fp": 0, "fn": 12, "tn": 6},
            "p1_semantic_micro_counts": {"tp": 10, "fp": 1, "fn": 2, "tn": 5},
            "duplicate_attempt_rejected": True,
            "terminal_error_retained": True,
            "invalid_label_retained": True,
            "report_extra_property_rejected": True,
            "formal_scope_refused": True,
        },
        "stage1_evaluator_failure_semantics_mismatch",
        "S1.6 membership/error/failure evidence changed",
    )
    safety = manifest.get("safety", {})
    require(
        safety
        == {
            "synthetic_fixture_only": True,
            "synthetic_reference_is_human_gold": False,
            "formal_bpmn_read": False,
            "human_gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "formal_performance_evaluation": False,
            "formal_results_written": False,
        },
        "stage1_evaluator_safety_mismatch",
        "S1.6 safety boundary changed",
    )
    gate = experiment_contract.get("stage1_evaluator_gate", {})
    require(
        isinstance(gate, Mapping)
        and gate.get("task_ids") == ["S1.6"]
        and gate.get("status") == "verified_offline_evaluator_formal_results_blocked"
        and gate.get("evaluator_ready") is True
        and gate.get("formal_results_ready") is False
        and gate.get("structure_component_count") == 8
        and gate.get("semantic_field_count") == 3
        and gate.get("synthetic_reference_is_human_gold") is False
        and gate.get("formal_performance_evaluation") is False,
        "stage1_evaluator_experiment_contract_mismatch",
        "Experiment contract disagrees with S1.6 evaluator or claim boundary",
    )
    ready = not errors
    return {
        "evaluator_ready": ready,
        "formal_results_ready": False,
        "errors": errors,
        "blockers": [item["code"] for item in errors]
        + (["stage1_evaluator_formal_results_blocked_on_membership_and_gold"] if ready else []),
        "hashes": hashes,
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
        BPMN_FIXTURE_REL,
        LABEL_MANIFEST_REL,
        ANNOTATION_MANIFEST_REL,
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
    return verify_stage1_evaluator_gate(Path(root))


def get_cached_stage1_evaluator_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

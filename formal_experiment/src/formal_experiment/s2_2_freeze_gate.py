"""Fail-closed machine gate for the EStG-150 S2.2 annotation freeze receipt.

This gate verifies a human-owned annotation snapshot.  It does not publish
formal Gold and it does not authorize any formal method run.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping


SOURCE_REL = "data/development/human_review/estg_150_human_correction_v1.json"
MEMBERSHIP_REL = "data/development/estg/estg_150_membership_hashes.json"
SCHEMA_REL = "configs/schemas/human_gold_review.schema.json"
VALIDATOR_REL = "src/formal_experiment/estg150_validator.py"
VERIFIER_REL = "scripts/verify_estg150_s22_freeze.py"
MANIFEST_REL = "outputs/reports/s22_estg150_human_annotation_freeze_v1.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S22FreezeExpectations:
    source_sha256: str = "7fd55f98a7dd6aeef58a93be825465c767f00feeab84c6d4215afc434a135b1c"
    membership_sha256: str = "0f9065523a57900b22a8a04ae9109d37c72abbe514f3cde60bcd7652cfa1417b"
    schema_sha256: str = "abcccdb420bdf4304279270b8971cdd785d89e14c551842d305033314e128503"
    validator_sha256: str = "68a2aa6de3c04256ca91c5e164d4644a47f2a0d992ca7a78b33ee9758b14d2c4"
    verifier_sha256: str = "2d0bd1a03c7d9bc56978bca666bcfd5107994d3e9b5017cc8accc264bc4fe8c3"
    manifest_sha256: str = "aa316ed71751192cada9c3077ab1ebbba76081b20d102e9873c66ac315146961"


S22_FREEZE_EXPECTATIONS = S22FreezeExpectations()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _load_verifier(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location("_s22_freeze_verifier", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import S2.2 verifier: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_s2_2_freeze_gate(
    project_root: Path,
    *,
    expectations: S22FreezeExpectations = S22_FREEZE_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "source": root / SOURCE_REL,
        "membership": root / MEMBERSHIP_REL,
        "schema": root / SCHEMA_REL,
        "validator": root / VALIDATOR_REL,
        "verifier": root / VERIFIER_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s2_2_freeze_artifact_missing", f"Missing S2.2 {name}: {path}")
    if errors:
        return {
            "ready": False,
            "annotation_frozen": False,
            "formal_gold_published": False,
            "errors": errors,
            "blockers": [item["code"] for item in errors],
        }

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("source", expectations.source_sha256),
        ("membership", expectations.membership_sha256),
        ("schema", expectations.schema_sha256),
        ("validator", expectations.validator_sha256),
        ("verifier", expectations.verifier_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"s2_2_freeze_{name}_hash_mismatch",
            f"S2.2 {name} SHA-256 changed",
        )

    try:
        manifest = _load(paths["manifest"])
        contract = _load(paths["contract"])
        verifier = _load_verifier(paths["verifier"])
        regenerated = verifier.build_manifest(
            paths["source"], paths["membership"], paths["schema"]
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        require(False, "s2_2_freeze_artifact_invalid", str(exc))
        manifest = {}
        contract = {}
        regenerated = None
    except Exception as exc:  # verifier owns its domain-specific exception class
        require(False, "s2_2_freeze_revalidation_failed", str(exc))
        manifest = {}
        contract = {}
        regenerated = None

    require(
        regenerated == manifest,
        "s2_2_freeze_receipt_not_reproducible",
        "S2.2 receipt does not exactly match a fresh strict-validator reconstruction",
    )

    dataset = manifest.get("dataset", {})
    validation = manifest.get("validation", {})
    summary = manifest.get("annotation_summary", {})
    boundaries = manifest.get("route_boundaries", {})
    safety = manifest.get("safety", {})
    require(
        manifest.get("schema_version") == "estg150_s22_annotation_freeze_receipt@1.0.0"
        and manifest.get("run_id") == "s22_estg150_human_annotation_freeze_v1"
        and manifest.get("task_id") == "S2.2"
        and manifest.get("status") == "succeeded_annotation_frozen_not_formal_gold_published"
        and isinstance(dataset, Mapping)
        and dataset.get("dataset_id") == "independently_reconstructed_estg_150_v1"
        and dataset.get("membership_count") == 150
        and dataset.get("sun_original_150") is False
        and dataset.get("exact_reproduction") is False,
        "s2_2_freeze_manifest_identity_mismatch",
        "S2.2 receipt identity or non-exact claim boundary changed",
    )
    require(
        isinstance(validation, Mapping)
        and validation.get("format_valid") is True
        and validation.get("review_ready") is True
        and validation.get("freeze_ready") is True
        and validation.get("n_records") == 150
        and validation.get("n_approved_en") == 150
        and validation.get("n_field_decisions_total") == 900
        and validation.get("n_field_decisions_resolved") == 900
        and validation.get("n_field_decisions_unreviewed") == 0
        and validation.get("n_records_fully_decided") == 150
        and validation.get("n_adjudicated") == 150
        and validation.get("format_errors") == []
        and validation.get("review_blockers") == []
        and validation.get("freeze_blockers") == [],
        "s2_2_freeze_validation_mismatch",
        "S2.2 receipt no longer proves 150/150 adjudication and 900/900 resolved decisions",
    )
    require(
        isinstance(summary, Mapping) and summary.get("clause_count") == 231,
        "s2_2_freeze_annotation_summary_mismatch",
        "S2.2 frozen clause count changed",
    )
    require(
        isinstance(boundaries, Mapping)
        and boundaries.get("annotation_scope") == "sentence_only_approved_english_working_text"
        and boundaries.get("german_to_english_fidelity_human_verified") is False
        and boundaries.get("context_sidecar_used") is False
        and boundaries.get("open_issue_ids") == ["RWI-0001", "RWI-0007"]
        and boundaries.get("formal_gold_publication_ready") is False
        and boundaries.get("formal_stage2_method_run_authorized") is False,
        "s2_2_freeze_route_boundary_relaxed",
        "S2.2 route, language, context, publication, or method boundary was relaxed",
    )
    require(
        safety == {
            "human_correction_read_only": True,
            "human_decisions_modified": False,
            "data_gold_written": False,
            "data_input_written": False,
            "method_predictions_or_results_written": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
        },
        "s2_2_freeze_safety_boundary_mismatch",
        "S2.2 safety boundary changed",
    )

    artifacts = manifest.get("artifacts", {})
    expected_manifest_artifacts = {
        "human_correction_layer_e": (SOURCE_REL, hashes["source"]),
        "membership_hashes": (MEMBERSHIP_REL, hashes["membership"]),
        "human_review_schema": (SCHEMA_REL, hashes["schema"]),
    }
    require(
        isinstance(artifacts, Mapping)
        and all(
            artifacts.get(name, {}).get("path") == path
            and artifacts.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_manifest_artifacts.items()
        ),
        "s2_2_freeze_manifest_artifact_mismatch",
        "S2.2 receipt artifact paths or hashes changed",
    )

    gate = contract.get("stage2_annotation_freeze_gate", {})
    expected_contract_artifacts = {
        "human_correction_layer_e": (SOURCE_REL, hashes["source"]),
        "membership_hashes": (MEMBERSHIP_REL, hashes["membership"]),
        "human_review_schema": (SCHEMA_REL, hashes["schema"]),
        "validator": (VALIDATOR_REL, hashes["validator"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.2"
        and gate.get("status") == "verified_annotation_frozen_route_qa_pending"
        and gate.get("ready") is True
        and gate.get("annotation_frozen") is True
        and gate.get("formal_gold_published") is False
        and gate.get("formal_stage2_method_run_authorized") is False
        and gate.get("dataset_id") == "independently_reconstructed_estg_150_v1"
        and gate.get("records") == 150
        and gate.get("approved_text_en") == 150
        and gate.get("resolved_field_decisions") == 900
        and gate.get("adjudicated") == 150
        and gate.get("clause_count") == 231
        and gate.get("open_route_issues") == ["RWI-0001", "RWI-0007"]
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_contract_artifacts.items()
        ),
        "s2_2_freeze_experiment_contract_mismatch",
        "Experiment contract disagrees with the S2.2 receipt or its boundaries",
    )

    ready = not errors
    return {
        "ready": ready,
        "annotation_frozen": ready,
        "formal_gold_published": False,
        "formal_stage2_method_run_authorized": False,
        "records": validation.get("n_records") if isinstance(validation, Mapping) else None,
        "resolved_field_decisions": validation.get("n_field_decisions_resolved") if isinstance(validation, Mapping) else None,
        "adjudicated": validation.get("n_adjudicated") if isinstance(validation, Mapping) else None,
        "clause_count": summary.get("clause_count") if isinstance(summary, Mapping) else None,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        SOURCE_REL,
        MEMBERSHIP_REL,
        SCHEMA_REL,
        VALIDATOR_REL,
        VERIFIER_REL,
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
    return verify_s2_2_freeze_gate(Path(root))


def get_cached_s2_2_freeze_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

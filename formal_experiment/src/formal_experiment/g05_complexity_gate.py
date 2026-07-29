"""Exact-hash gate for the G0.5 pre-result complexity contract."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.complexity import (
    ComplexityContractError,
    load_complexity_contract,
    validate_complexity_profile,
)


CONTRACT_CONFIG_REL = "configs/complexity_contract.json"
PROFILE_SCHEMA_REL = "configs/schemas/complexity_profile.schema.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/complexity.py"
VERIFIER_REL = "scripts/verify_complexity_contract_g05.py"
TEXT_FIXTURE_REL = "tests/fixtures/complexity/text_two_sentence_fixture.json"
BPMN_FIXTURE_REL = "tests/fixtures/complexity/bpmn_cycle_fixture.bpmn"
MANIFEST_REL = "outputs/reports/g05_complexity_contract_synthetic_v1.manifest.json"
EXPERIMENT_CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class G05Expectations:
    contract_config_sha256: str = "0a0e4f809897f22179b752c3c92ddcbf208aced1176c9ac77fb27816c9ac3b7a"
    profile_schema_sha256: str = "1cbe678bef8833ef331816d5d08e3f897c368766a393e7a25a008684946cb615"
    implementation_sha256: str = "eec0cebc2784346e4b11eb3ac2649fde0013ab986a06db5350ded282bdd8aaa4"
    verifier_sha256: str = "1028bb033f45282505b755b73fc9d68ccabdf189c99ca78475f26265fcfe7b42"
    text_fixture_sha256: str = "6aee616ccccd2ddaf4923c5770f3cada3b7be932c3c2122c3e311b4b117fd252"
    bpmn_fixture_sha256: str = "dc0c6e6db0e0c98ce353ccc4a652ac780d68333561daff763e10ead0f51453cc"
    manifest_sha256: str = "e1494f64bbf413a5eb9c4e2414d5fe9b0678733e25b34f2e8be29aaea9fb5cc3"


G05_EXPECTATIONS = G05Expectations()


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
        raise ComplexityContractError(f"invalid G0.5 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ComplexityContractError(f"G0.5 JSON root must be an object: {path}")
    return value


def verify_g05_complexity_gate(
    project_root: Path,
    *,
    expectations: G05Expectations = G05_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "contract_config": root / CONTRACT_CONFIG_REL,
        "profile_schema": root / PROFILE_SCHEMA_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "verifier": root / VERIFIER_REL,
        "text_fixture": root / TEXT_FIXTURE_REL,
        "bpmn_fixture": root / BPMN_FIXTURE_REL,
        "manifest": root / MANIFEST_REL,
        "experiment_contract": root / EXPERIMENT_CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "g05_artifact_missing", f"Missing G0.5 {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "experiment_contract"}
    for name, expected in (
        ("contract_config", expectations.contract_config_sha256),
        ("profile_schema", expectations.profile_schema_sha256),
        ("implementation", expectations.implementation_sha256),
        ("verifier", expectations.verifier_sha256),
        ("text_fixture", expectations.text_fixture_sha256),
        ("bpmn_fixture", expectations.bpmn_fixture_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"g05_{name}_hash_mismatch", f"G0.5 {name} SHA-256 changed")

    try:
        config = load_complexity_contract(paths["contract_config"])
        manifest = _load(paths["manifest"])
        experiment_contract = _load(paths["experiment_contract"])
    except ComplexityContractError as exc:
        require(False, "g05_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        experiment_contract = {}

    verification = manifest.get("verification", {})
    safety = manifest.get("safety", {})
    text_profile = verification.get("text_profile", {}) if isinstance(verification, Mapping) else {}
    bpmn_profile = verification.get("bpmn_profile", {}) if isinstance(verification, Mapping) else {}
    text_schema_errors = validate_complexity_profile(text_profile, paths["profile_schema"]) if text_profile else ["missing"]
    bpmn_schema_errors = validate_complexity_profile(bpmn_profile, paths["profile_schema"]) if bpmn_profile else ["missing"]
    require(
        manifest.get("schema_version") == "complexity_g05_verification_manifest@1.0.0"
        and manifest.get("task_id") == "G0.5"
        and manifest.get("status") == "succeeded"
        and manifest.get("artifacts", {}).get("contract", {}).get("sha256") == hashes["contract_config"],
        "g05_manifest_identity_mismatch",
        "G0.5 verification manifest identity changed",
    )
    require(
        isinstance(verification, Mapping)
        and verification.get("text_profile_schema_valid") is True
        and verification.get("bpmn_profile_schema_valid") is True
        and verification.get("text_indicator_count") == 11
        and verification.get("bpmn_indicator_count") == 12
        and verification.get("strata") == ["low", "medium", "high"]
        and verification.get("method_output_used") is False
        and verification.get("test_result_used") is False
        and not text_schema_errors
        and not bpmn_schema_errors,
        "g05_profile_contract_mismatch",
        "G0.5 profile schema, indicators, or leakage evidence changed",
    )
    require(
        text_profile.get("domain") == "text"
        and text_profile.get("complexity_score") == 4
        and text_profile.get("complexity_stratum") == "medium"
        and text_profile.get("metrics", {}).get("max_dependency_depth") == 3
        and text_profile.get("metrics", {}).get("cross_sentence_reference_count") == 1,
        "g05_text_fixture_mismatch",
        "G0.5 text fixture profile changed",
    )
    require(
        bpmn_profile.get("domain") == "bpmn"
        and bpmn_profile.get("complexity_score") == 1
        and bpmn_profile.get("complexity_stratum") == "low"
        and bpmn_profile.get("metrics", {}).get("cycle_present") is True
        and bpmn_profile.get("metrics", {}).get("cyclomatic_complexity") == 2
        and bpmn_profile.get("metrics", {}).get("condensation_dag_depth") == 4,
        "g05_bpmn_fixture_mismatch",
        "G0.5 BPMN fixture profile changed",
    )
    require(
        safety == {
            "synthetic_fixtures_only": True,
            "complex_dataset_selected_or_read": False,
            "formal_profiles_generated": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "performance_evaluation": False,
        },
        "g05_safety_boundary_mismatch",
        "G0.5 safety boundary changed",
    )

    gate = experiment_contract.get("complexity_gate", {})
    expected_lock = {
        "contract": (CONTRACT_CONFIG_REL, hashes["contract_config"]),
        "profile_schema": (PROFILE_SCHEMA_REL, hashes["profile_schema"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "text_fixture": (TEXT_FIXTURE_REL, hashes["text_fixture"]),
        "bpmn_fixture": (BPMN_FIXTURE_REL, hashes["bpmn_fixture"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "G0.5"
        and gate.get("status") == "verified_pre_result_complexity_contract"
        and gate.get("ready") is True
        and gate.get("text_indicator_count") == 11
        and gate.get("bpmn_indicator_count") == 12
        and gate.get("method_outputs_used") is False
        and gate.get("test_results_used") is False
        and gate.get("complex_dataset_selected") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_lock.items()
        ),
        "g05_experiment_contract_mismatch",
        "Experiment contract disagrees with G0.5 artifacts or boundaries",
    )
    return {
        "ready": not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "text_indicator_count": len(config.get("text", {}).get("score_indicators", [])) if isinstance(config, Mapping) else None,
        "bpmn_indicator_count": len(config.get("bpmn", {}).get("score_indicators", [])) if isinstance(config, Mapping) else None,
        "complex_dataset_selected": safety.get("complex_dataset_selected_or_read") if isinstance(safety, Mapping) else None,
        "performance_evaluation": safety.get("performance_evaluation") if isinstance(safety, Mapping) else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONTRACT_CONFIG_REL,
        PROFILE_SCHEMA_REL,
        IMPLEMENTATION_REL,
        VERIFIER_REL,
        TEXT_FIXTURE_REL,
        BPMN_FIXTURE_REL,
        MANIFEST_REL,
        EXPERIMENT_CONTRACT_REL,
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
    return verify_g05_complexity_gate(Path(root))


def get_cached_g05_complexity_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))


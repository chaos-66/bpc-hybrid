"""Fail-closed machine gate for the verified S2.6 canonical B0 composition."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage2_canonical import validate_canonical
from bpc_hybrid.sun_style.sun_b0 import SunB0CompositionError, load_s26_config


CONFIG_REL = "configs/models/sun_b0_s26.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/sun_style/sun_b0.py"
RUNNER_REL = "scripts/run_sun_rule_only.py"
VERIFIER_REL = "scripts/verify_sun_b0_s26.py"
MANIFEST_REL = "outputs/reports/s26_sun_b0_canonical_composition_v3.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S26Expectations:
    config_sha256: str = "47566def9b7f8e403fd784b23c9cec0c55a64d4b5d10cd62c60dd4ab87442d46"
    implementation_sha256: str = "51df4f86359ecbc8a6f156371c62f115dfe4952e2e17c8cdc7a72aef77187b66"
    runner_sha256: str = "1a3d0d4116e2f3d80d6e7bb03f74d6fd795bfa075551cc83691e4e1381f72232"
    verifier_sha256: str = "64a79636cfefc9e6799f060ff17e9d61d1fdeec46604123fc500b303b02b44c7"
    manifest_sha256: str = "30a19e8a6476f35eff8561ca35f72a3b3a772067c0128ff4c22ce6b6ddd2fb20"


S26_EXPECTATIONS = S26Expectations()


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
        raise SunB0CompositionError(f"invalid S2.6 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise SunB0CompositionError(f"S2.6 JSON root must be an object: {path}")
    return value


def verify_s2_6_gate(
    project_root: Path,
    *,
    expectations: S26Expectations = S26_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "config": root / CONFIG_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "runner": root / RUNNER_REL,
        "verifier": root / VERIFIER_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s2_6_artifact_missing", f"Missing S2.6 {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(
            hashes[name] == expected,
            f"s2_6_{name}_hash_mismatch",
            f"S2.6 {name} SHA-256 changed",
        )

    try:
        config = load_s26_config(paths["config"])
        manifest = _load(paths["manifest"])
        contract = _load(paths["contract"])
    except SunB0CompositionError as exc:
        require(False, "s2_6_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        contract = {}

    composition = manifest.get("composition", {})
    safety = manifest.get("safety", {})
    predictions = composition.get("predicted_modalities", []) if isinstance(composition, Mapping) else []
    record = composition.get("synthetic_canonical_record", {}) if isinstance(composition, Mapping) else {}
    report = validate_canonical(record) if isinstance(record, dict) and record else None
    require(
        manifest.get("schema_version") == "sun_b0_s26_verification_manifest@1.0.0"
        and manifest.get("task_id") == "S2.6"
        and manifest.get("status") == "succeeded"
        and manifest.get("method") == "sun_rule_only"
        and manifest.get("config", {}).get("sha256") == hashes["config"],
        "s2_6_manifest_identity_mismatch",
        "S2.6 verification manifest identity changed",
    )
    require(
        isinstance(composition, Mapping)
        and composition.get("actual_s2_4_checkpoint_loaded") is True
        and composition.get("s2_4_test_re_evaluated") is False
        and composition.get("s2_5_attested_live_observation_consumed") is True
        and composition.get("classifier_input_language") == "de"
        and composition.get("phrase_and_canonical_source_language") == "en"
        and composition.get("parallel_synthetic_text_alignment") is True
        and composition.get("record_count") == 1
        and composition.get("clause_count") == 1
        and composition.get("schema_invalid") == 0
        and composition.get("cross_field_invalid") == 0,
        "s2_6_composition_mismatch",
        "S2.6 classifier/extractor/canonical composition evidence changed",
    )
    require(
        isinstance(predictions, list)
        and len(predictions) == 1
        and predictions[0].get("label") in {"definition", "obligation", "permission", "prohibition"}
        and isinstance(predictions[0].get("confidence"), (int, float))
        and 0.0 <= predictions[0]["confidence"] <= 1.0,
        "s2_6_prediction_evidence_invalid",
        "S2.6 synthetic classifier prediction evidence is invalid",
    )
    require(
        report is not None and report.schema_valid and report.cross_field_valid
        and record.get("method", {}).get("name") == "sun_rule_only"
        and record.get("source_id") == "s25_locked_live_fixture",
        "s2_6_canonical_record_invalid",
        "S2.6 synthetic canonical record is invalid",
    )
    require(
        safety == {
            "synthetic_fixture_only": True,
            "performance_evaluation": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "test_split_read_or_evaluated": False,
            "row_level_real_data_predictions_persisted": False,
        },
        "s2_6_safety_boundary_mismatch",
        "S2.6 safety boundary changed",
    )

    gate = contract.get("sun_stage2_method", {}).get("baseline_composition_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.6"
        and gate.get("status") == "verified_classifier_extractor_canonical_composition"
        and gate.get("ready") is True
        and gate.get("classifier_verified") is True
        and gate.get("phrase_extractor_verified") is True
        and gate.get("canonical_composition_verified") is True
        and gate.get("actual_s2_4_checkpoint_loaded") is True
        and gate.get("s2_4_test_re_evaluated") is False
        and gate.get("synthetic_fixture_only") is True
        and gate.get("formal_performance_evaluation") is False
        and gate.get("llm_api_called") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_lock.items()
        ),
        "s2_6_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.6 artifacts or boundaries",
    )
    return {
        "ready": not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "record_count": composition.get("record_count") if isinstance(composition, Mapping) else None,
        "schema_invalid": composition.get("schema_invalid") if isinstance(composition, Mapping) else None,
        "cross_field_invalid": composition.get("cross_field_invalid") if isinstance(composition, Mapping) else None,
        "classifier_input_language": composition.get("classifier_input_language") if isinstance(composition, Mapping) else None,
        "canonical_source_language": composition.get("phrase_and_canonical_source_language") if isinstance(composition, Mapping) else None,
        "performance_evaluation": safety.get("performance_evaluation") if isinstance(safety, Mapping) else None,
        "llm_api_called": safety.get("llm_api_called") if isinstance(safety, Mapping) else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (CONFIG_REL, IMPLEMENTATION_REL, RUNNER_REL, VERIFIER_REL, MANIFEST_REL, CONTRACT_REL):
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
    return verify_s2_6_gate(Path(root))


def get_cached_s2_6_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

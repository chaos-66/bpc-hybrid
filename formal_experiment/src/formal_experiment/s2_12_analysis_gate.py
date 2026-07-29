"""Exact-hash gate for the S2.12-P pre-result analysis protocol."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.s212_analysis import S212AnalysisError, load_analysis_protocol


PROTOCOL_REL = "configs/s212_analysis_protocol.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/s212_analysis.py"
VERIFIER_REL = "scripts/verify_s212_analysis_protocol.py"
FIXTURE_REL = "tests/fixtures/s212_analysis/s212_synthetic_counts.json"
MANIFEST_REL = "outputs/reports/s212_analysis_protocol_synthetic_v2.manifest.json"
GATE_REL = "src/formal_experiment/s2_12_analysis_gate.py"
EXPERIMENT_CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S212Expectations:
    protocol_sha256: str = "d3e2d7e38d97e71d60ffc07cc3cae18335881b0d00d3ab8b4dc4fb3f25cfc860"
    implementation_sha256: str = "efbc068e0d90facedd7e39069a9f6db0ab5d46afe785a82c7b99a4328a42b788"
    verifier_sha256: str = "566b447bf75945c5683bfe3aef86544c66e7cdebaa230e41acf08dabce7230df"
    fixture_sha256: str = "0e75e6b52b995dda85fcdff2726ea786defdb83d1b766b0a3d6518bf277e2d47"
    manifest_sha256: str = "46f73c07ba7e3f86459787985d53775dc187390c55960254978c8e1a50dc3cbd"


S212_EXPECTATIONS = S212Expectations()


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
        raise S212AnalysisError(f"invalid S2.12-P JSON: {path}") from exc
    if not isinstance(value, dict):
        raise S212AnalysisError("S2.12-P JSON root must be an object")
    return value


def verify_s2_12_analysis_gate(
    project_root: Path,
    *,
    expectations: S212Expectations = S212_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "protocol": root / PROTOCOL_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "verifier": root / VERIFIER_REL,
        "fixture": root / FIXTURE_REL,
        "manifest": root / MANIFEST_REL,
        "gate_module": root / GATE_REL,
        "experiment_contract": root / EXPERIMENT_CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s212_artifact_missing", f"Missing S2.12-P {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "experiment_contract"}
    for name, expected in (
        ("protocol", expectations.protocol_sha256),
        ("implementation", expectations.implementation_sha256),
        ("verifier", expectations.verifier_sha256),
        ("fixture", expectations.fixture_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"s212_{name}_hash_mismatch", f"S2.12-P {name} SHA-256 changed")

    try:
        protocol = load_analysis_protocol(paths["protocol"])
        manifest = _load(paths["manifest"])
        experiment_contract = _load(paths["experiment_contract"])
    except S212AnalysisError as exc:
        require(False, "s212_artifact_invalid", str(exc))
        protocol = {}
        manifest = {}
        experiment_contract = {}

    artifacts = manifest.get("artifacts", {})
    require(
        manifest.get("schema_version") == "s212_analysis_verification_manifest@1.1.0"
        and manifest.get("task_id") == "S2.12-P"
        and manifest.get("run_id") == "s212_analysis_protocol_synthetic_v2"
        and manifest.get("status") == "succeeded"
        and all(
            isinstance(artifacts.get(manifest_name), Mapping)
            and artifacts[manifest_name].get("sha256") == hashes[hash_name]
            for manifest_name, hash_name in (
                ("protocol", "protocol"),
                ("implementation", "implementation"),
                ("verifier", "verifier"),
                ("synthetic_fixture", "fixture"),
            )
        ),
        "s212_manifest_identity_mismatch",
        "S2.12-P manifest identity or artifact binding changed",
    )
    verification = manifest.get("verification", {})
    require(
        isinstance(verification, Mapping)
        and verification.get("primary_endpoint_count") == 6
        and verification.get("contrast_count") == 2
        and verification.get("hypotheses_per_dataset_family") == 12
        and verification.get("bootstrap_iterations") == 10000
        and verification.get("randomization_iterations") == 10000
        and verification.get("holm_family_size") == 12
        and verification.get("sample_array_order_invariant") is True
        and verification.get("small_stratum_interval_suppressed") is True
        and verification.get("unknown_error_category_fails_closed") is True
        and verification.get("qualitative_case_cap_verified") == 3,
        "s212_verification_mismatch",
        "S2.12-P statistical or deterministic verification changed",
    )
    require(
        manifest.get("safety")
        == {
            "synthetic_fixture_only": True,
            "formal_gold_read_or_modified": False,
            "formal_predictions_read_or_created": False,
            "formal_complexity_profiles_generated": False,
            "formal_performance_evaluation": False,
            "method_comparison_claim_generated": False,
            "llm_api_called": False,
            "network_called": False,
        },
        "s212_safety_boundary_mismatch",
        "S2.12-P safety boundary changed",
    )
    gate = experiment_contract.get("stage2_analysis_gate", {})
    expected_lock = {
        "protocol": (PROTOCOL_REL, hashes["protocol"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "synthetic_fixture": (FIXTURE_REL, hashes["fixture"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
        "gate_module": (GATE_REL, hashes["gate_module"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.12-P"
        and gate.get("status") == "verified_pre_result_analysis_protocol"
        and gate.get("ready") is True
        and gate.get("formal_results_ready") is False
        and gate.get("formal_gold_read_or_modified") is False
        and gate.get("formal_predictions_read_or_created") is False
        and gate.get("llm_api_called") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == digest
            for name, (path, digest) in expected_lock.items()
        ),
        "s212_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.12-P artifacts or boundaries",
    )
    upstream = protocol.get("upstream_bindings", {})
    require(
        isinstance(upstream, Mapping)
        and all(
            (root / binding.get("path", "")).is_file()
            and _sha256(root / binding["path"]) == binding.get("sha256")
            for binding in upstream.values()
            if isinstance(binding, Mapping)
        )
        and len(upstream) == 6,
        "s212_upstream_binding_mismatch",
        "S2.12-P upstream G0.5/S2.10/S2.11 binding changed",
    )
    return {
        "ready": not errors,
        "formal_results_ready": False,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "hypotheses_per_dataset_family": verification.get("hypotheses_per_dataset_family"),
        "formal_gold_read_or_modified": False,
        "formal_predictions_read_or_created": False,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        PROTOCOL_REL,
        IMPLEMENTATION_REL,
        VERIFIER_REL,
        FIXTURE_REL,
        MANIFEST_REL,
        GATE_REL,
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
    return verify_s2_12_analysis_gate(Path(root))


def get_cached_s2_12_analysis_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

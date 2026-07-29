"""Exact-hash gate for the S2.11 complex legal input and Gold protocol."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.complex_legal import ComplexLegalContractError


CONFIG_REL = "configs/datasets/gdpr_articles_5_50_s211.json"
METADATA_REL = (
    "data/development/complex_legal/gdpr_2016_679_oj_en/source/DOC_1_metadata.xml"
)
BODY_REL = "data/development/complex_legal/gdpr_2016_679_oj_en/source/DOC_2_body.xml"
REUSE_REL = "configs/datasets/gdpr_eurlex_reuse_evidence_s211.json"
DATASET_REL = (
    "data/development/complex_legal/gdpr_2016_679_oj_en/"
    "gdpr_articles_5_50_seeded50_v1.jsonl"
)
MEMBERSHIP_REL = DATASET_REL.removesuffix(".jsonl") + ".membership.json"
REVIEW_REL = (
    "data/development/complex_legal/gdpr_2016_679_oj_en/"
    "gdpr_articles_5_50_seeded50_human_gold_v1.json"
)
SCHEMA_REL = "configs/schemas/complex_legal_human_gold.schema.json"
GUIDE_REL = "docs/COMPLEX_LEGAL_GOLD_GUIDE.md"
IMPLEMENTATION_REL = "src/bpc_hybrid/complex_legal.py"
BUILDER_REL = "scripts/build_complex_legal_s211.py"
VALIDATOR_REL = "scripts/validate_complex_legal_human_gold.py"
VERIFIER_REL = "scripts/verify_complex_legal_s211.py"
GATE_REL = "src/formal_experiment/s2_11_gate.py"
G05_REL = "configs/complexity_contract.json"
MANIFEST_REL = "outputs/reports/s211_gdpr_complex_dataset_freeze_v1.manifest.json"
EXPERIMENT_CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S211Expectations:
    config_sha256: str = "041b6269f3da6bdf67b3d06408d9664be5c4fe84e0c9ff4576726a460a6a563c"
    metadata_sha256: str = "3c13d7d5dc2012e9a290575405639aba1d56cd09b47be6b3f8f4297c11c2af72"
    body_sha256: str = "fce6e6ea8724e66a1c4f98c584cafdc9dfbae26aa83c44b43423b8c7f6aa0295"
    reuse_sha256: str = "95a20a93b5f90c2282c9c9db760747ac1caa57833f51673d74e6877b0eccb8af"
    dataset_sha256: str = "f6093f37e1e716a5edf07dd0653d2904f11c0fe3945de1e3b083ecc761e6d1e4"
    membership_sha256: str = "adbbb4d0556c0542597d43295f8e5e4531ccbec5005ca725d6020af827e4f6c7"
    review_sha256: str = "9476947d8bcd460249a7ddab73599d18d9b2d59ee479f94360e1c3e7c2c9dab8"
    schema_sha256: str = "a98b6196626e990472b71d1d514929ab37ca8a85a417f6fd3279d5224d63a88a"
    guide_sha256: str = "ef9f557ccd3b56e3f86c6520c40dc1b7676892e010dbf47bdf0bfab066a18237"
    implementation_sha256: str = "0de00566c0bd9e0ed685ceed4f72e99bcb3214a9228f16876a2ee2f60e0d1fa6"
    builder_sha256: str = "d577a5027d57c049e67f04aa2960b845075ca1503d83c6353eca0877a19f8f3a"
    validator_sha256: str = "02f76b027c3c27a6c1c29678d6298d231f8fe05b00c1ad98a2f029dc9cd08faa"
    verifier_sha256: str = "8b2fa44723587b1eac50207bf729109297e42f6174c016dd3caabe2dd485b9ec"
    g05_sha256: str = "0a0e4f809897f22179b752c3c92ddcbf208aced1176c9ac77fb27816c9ac3b7a"
    manifest_sha256: str = "215dae3ebe0378652337d2839f62ea4dbf9787f921cdbbae3ac394c36f5c486b"


S211_EXPECTATIONS = S211Expectations()


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
        raise ComplexLegalContractError(f"invalid S2.11 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ComplexLegalContractError(f"S2.11 JSON root must be an object: {path}")
    return value


def verify_s2_11_gate(
    project_root: Path,
    *,
    expectations: S211Expectations = S211_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "config": root / CONFIG_REL,
        "metadata": root / METADATA_REL,
        "body": root / BODY_REL,
        "reuse": root / REUSE_REL,
        "dataset": root / DATASET_REL,
        "membership": root / MEMBERSHIP_REL,
        "review": root / REVIEW_REL,
        "schema": root / SCHEMA_REL,
        "guide": root / GUIDE_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "builder": root / BUILDER_REL,
        "validator": root / VALIDATOR_REL,
        "verifier": root / VERIFIER_REL,
        "gate_module": root / GATE_REL,
        "g05": root / G05_REL,
        "manifest": root / MANIFEST_REL,
        "experiment_contract": root / EXPERIMENT_CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s211_artifact_missing", f"Missing S2.11 {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "experiment_contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("metadata", expectations.metadata_sha256),
        ("body", expectations.body_sha256),
        ("reuse", expectations.reuse_sha256),
        ("dataset", expectations.dataset_sha256),
        ("membership", expectations.membership_sha256),
        ("review", expectations.review_sha256),
        ("schema", expectations.schema_sha256),
        ("guide", expectations.guide_sha256),
        ("implementation", expectations.implementation_sha256),
        ("builder", expectations.builder_sha256),
        ("validator", expectations.validator_sha256),
        ("verifier", expectations.verifier_sha256),
        ("g05", expectations.g05_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"s211_{name}_hash_mismatch", f"S2.11 {name} SHA-256 changed")

    try:
        manifest = _load(paths["manifest"])
        spec = importlib.util.spec_from_file_location("_s211_verifier", paths["verifier"])
        if spec is None or spec.loader is None:
            raise ComplexLegalContractError("cannot load S2.11 verifier")
        verifier_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(verifier_module)
        rebuilt = verifier_module.run(paths["config"])
        rebuilt["created_at"] = manifest.get("created_at")
        require(rebuilt == manifest, "s211_manifest_rebuild_mismatch", "S2.11 manifest does not match offline rebuild")
        experiment_contract = _load(paths["experiment_contract"])
    except (ComplexLegalContractError, KeyError, TypeError) as exc:
        require(False, "s211_artifact_invalid", str(exc))
        manifest = {}
        experiment_contract = {}

    verification = manifest.get("verification", {})
    human_review = verification.get("human_review", {}) if isinstance(verification, Mapping) else {}
    safety = manifest.get("safety", {})
    require(
        manifest.get("schema_version") == "complex_legal_s211_verification_manifest@1.0.0"
        and manifest.get("task_id") == "S2.11"
        and manifest.get("status") == "succeeded"
        and manifest.get("dataset_id") == "gdpr_2016_679_articles_5_50_seeded50_v1",
        "s211_manifest_identity_mismatch",
        "S2.11 manifest identity changed",
    )
    require(
        verification.get("source_unit_count") == 200
        and verification.get("selected_count") == 50
        and verification.get("unique_sample_ids") == 50
        and verification.get("unique_source_text_hashes") == 50
        and verification.get("article_coverage") == list(range(5, 51))
        and verification.get("article_coverage_count") == 46
        and verification.get("coverage_supplement_count") == 4
        and verification.get("membership_sha256")
        == "9a6a2c892e6e9ef86877066fb3c88ad03d06ca999c41ecbd91c6df35d09c28b9"
        and verification.get("legacy_gdpr50_imported") is False
        and verification.get("formal_complexity_profiles_generated") is False,
        "s211_membership_verification_mismatch",
        "S2.11 source counts, membership, or pre-result boundary changed",
    )
    require(
        human_review == {
            "format_valid": True,
            "input_ready": True,
            "freeze_ready": False,
            "reviewed": 0,
            "adjudicated": 0,
            "canonical_rule_present": 0,
            "errors": [],
        },
        "s211_human_gold_protocol_mismatch",
        "S2.11 blank human-Gold protocol changed",
    )
    require(
        safety == {
            "method_outputs_read": False,
            "test_results_read": False,
            "formal_gold_created": False,
            "human_gold_modified": False,
            "source_acquisition_network_used": True,
            "offline_verification_network_called": False,
            "llm_api_called": False,
            "performance_evaluation": False,
        },
        "s211_safety_boundary_mismatch",
        "S2.11 safety boundary changed",
    )

    gate = experiment_contract.get("complex_legal_dataset_gate", {})
    artifact_map = {
        "config": (CONFIG_REL, hashes["config"]),
        "source_metadata": (METADATA_REL, hashes["metadata"]),
        "source_body": (BODY_REL, hashes["body"]),
        "reuse_evidence": (REUSE_REL, hashes["reuse"]),
        "dataset": (DATASET_REL, hashes["dataset"]),
        "membership": (MEMBERSHIP_REL, hashes["membership"]),
        "blank_human_gold": (REVIEW_REL, hashes["review"]),
        "human_gold_schema": (SCHEMA_REL, hashes["schema"]),
        "mapping_guide": (GUIDE_REL, hashes["guide"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "builder": (BUILDER_REL, hashes["builder"]),
        "validator": (VALIDATOR_REL, hashes["validator"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "gate_module": (GATE_REL, hashes["gate_module"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.11"
        and gate.get("status") == "verified_source_membership_and_gold_protocol"
        and gate.get("ready") is True
        and gate.get("input_ready") is True
        and gate.get("human_gold_freeze_ready") is False
        and gate.get("selected_count") == 50
        and gate.get("article_coverage_count") == 46
        and gate.get("membership_sha256")
        == "9a6a2c892e6e9ef86877066fb3c88ad03d06ca999c41ecbd91c6df35d09c28b9"
        and gate.get("method_outputs_used") is False
        and gate.get("test_results_used") is False
        and gate.get("formal_complexity_profiles_generated") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == digest
            for name, (path, digest) in artifact_map.items()
        ),
        "s211_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.11 artifacts or boundaries",
    )
    require(
        experiment_contract.get("complexity_gate", {}).get("status")
        == "verified_pre_result_complexity_contract",
        "s211_g05_dependency_mismatch",
        "S2.11 requires the verified G0.5 pre-result complexity contract",
    )
    return {
        "ready": not errors,
        "input_ready": human_review.get("input_ready") is True and not errors,
        "human_gold_freeze_ready": human_review.get("freeze_ready") is True and not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "selected_count": verification.get("selected_count"),
        "article_coverage_count": verification.get("article_coverage_count"),
        "membership_sha256": verification.get("membership_sha256"),
        "reviewed": human_review.get("reviewed"),
        "adjudicated": human_review.get("adjudicated"),
        "formal_complexity_profiles_generated": verification.get("formal_complexity_profiles_generated"),
        "performance_evaluation": safety.get("performance_evaluation") if isinstance(safety, Mapping) else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        METADATA_REL,
        BODY_REL,
        REUSE_REL,
        DATASET_REL,
        MEMBERSHIP_REL,
        REVIEW_REL,
        SCHEMA_REL,
        GUIDE_REL,
        IMPLEMENTATION_REL,
        BUILDER_REL,
        VALIDATOR_REL,
        VERIFIER_REL,
        GATE_REL,
        G05_REL,
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
    return verify_s2_11_gate(Path(root))


def get_cached_s2_11_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

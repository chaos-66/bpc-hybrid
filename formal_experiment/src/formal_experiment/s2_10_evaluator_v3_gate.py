"""Exact gates for the S2.10-E v1.2 evaluator and B0 re-evaluation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class S210V3Expectations:
    contract_sha256: str = "28ce332564c5d10da08dea515aefe31cc2aacd91b6c6877aa1bfebe44f39ae7f"
    report_schema_sha256: str = "004ed6946fb372d52236cf6a952f40efe6a66153a4592752db6fb181b1e7a603"
    implementation_sha256: str = "d7df11f86908b68424ed36afe3386a5c4d8a24f93dfb5cdb1d60333f48d7a9db"
    verifier_sha256: str = "6dbaa726058cc64c58416bc8fa943b22a3f070aa06bd5bccbd3091fad174d022"
    tests_sha256: str = "490dd2504987b5f8c980e3a7aba2ed6bf8f0a6a2ec167d3cc90a6953a838abe0"
    receipt_sha256: str = "974a0e7e06a864b57ee6636f6c62ad940559e0b0af2b18c6dbfe123c0545c34a"


@dataclass(frozen=True)
class S27B0V3Expectations:
    source_manifest_sha256: str = "7ab968a5da3fb482e8135977cc323828c8c682db0379bd95c1dacabdc6af8746"
    attempts_sha256: str = "0ab15cdaeba1cfc3e1e9f702586152521e6532ca2fc21e6192fb887ef8cb4278"
    reevaluator_sha256: str = "55c4bfc4a41806eef5dab3188a716054c2f6cc0a371a3ec3f62c11bf929b9574"
    manifest_sha256: str = "5a26bc7c11661427aa0bdbcd240a01c94ee642ceb0da4e9b85ee52f1ad97c491"
    all150_report_sha256: str = "0ecd96c8c82db35f49b54c4a159948b2c8624f4ce32b7edf7449df6f3bed1839"
    independent82_report_sha256: str = "7d86d9318dbe4221273ba706662e374662a2901612cf3c9e7c80ed23ebdcc758"


S210_V3_EXPECTATIONS = S210V3Expectations()
S27_B0_V3_EXPECTATIONS = S27B0V3Expectations()


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


def verify_s2_10_evaluator_v3_gate(
    root: Path,
    *,
    expectations: S210V3Expectations = S210_V3_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(root)
    paths = {
        "contract": root / "configs/stage2_evaluator_s210_v3.json",
        "report_schema": root / "configs/schemas/stage2_evaluation_report_v3.schema.json",
        "implementation": root / "src/bpc_hybrid/stage2_evaluation_v3.py",
        "verifier": root / "scripts/verify_stage2_evaluator_s210_v3.py",
        "tests": root / "tests/test_s2_10_stage2_evaluation_v3.py",
        "receipt": root / "outputs/reports/s210_stage2_evaluator_contract_synthetic_v3.manifest.json",
    }
    expected_hashes = {
        "contract": expectations.contract_sha256,
        "report_schema": expectations.report_schema_sha256,
        "implementation": expectations.implementation_sha256,
        "verifier": expectations.verifier_sha256,
        "tests": expectations.tests_sha256,
        "receipt": expectations.receipt_sha256,
    }
    blockers: list[str] = []
    hashes: dict[str, str | None] = {}
    for name, path in paths.items():
        if not path.is_file():
            blockers.append(f"s210_v3_{name}_missing")
            hashes[name] = None
            continue
        hashes[name] = _sha256(path)
        if hashes[name] != expected_hashes[name]:
            blockers.append(f"s210_v3_{name}_hash_mismatch")
    receipt: dict[str, Any] = {}
    if paths["receipt"].is_file():
        try:
            receipt = _load(paths["receipt"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            blockers.append("s210_v3_receipt_invalid_json")
    if receipt:
        if (
            receipt.get("schema_version") != "s210_evaluator_verification_manifest@1.2.0"
            or receipt.get("status") != "succeeded_candidate_for_future_development"
        ):
            blockers.append("s210_v3_receipt_identity_mismatch")
        safety = receipt.get("safety", {})
        if safety.get("paper_score_targeting_used") is not False:
            blockers.append("s210_v3_paper_score_targeting_not_false")
        if safety.get("threshold_search_used") is not False:
            blockers.append("s210_v3_threshold_search_not_false")
        if safety.get("llm_api_called") is not False or safety.get("network_called") is not False:
            blockers.append("s210_v3_offline_safety_mismatch")
    return {
        "ready": not blockers,
        "task_id": "S2.10-E",
        "contract_version": "stage2_evaluator_contract@1.2.0",
        "blockers": sorted(set(blockers)),
        "hashes": hashes,
        "paper_score_targeting_used": False if receipt else None,
        "main_data_results_ready": False,
    }


def verify_s2_7_b0_v3_gate(
    root: Path,
    *,
    expectations: S27B0V3Expectations = S27_B0_V3_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(root)
    paths = {
        "source_manifest": root / "outputs/development/s27_estg150_b0_development_v1/manifest.json",
        "attempts": root / "outputs/development/s27_estg150_b0_development_v1/b0_attempts.json",
        "reevaluator": root / "scripts/reevaluate_estg150_b0_v3.py",
        "manifest": root / "outputs/development/s27_estg150_b0_v3_evaluation_v1/manifest.json",
        "all150_report": root / "outputs/development/s27_estg150_b0_v3_evaluation_v1/evaluation_all150.json",
        "independent82_report": root / "outputs/development/s27_estg150_b0_v3_evaluation_v1/evaluation_independent82.json",
    }
    expected_hashes = {
        "source_manifest": expectations.source_manifest_sha256,
        "attempts": expectations.attempts_sha256,
        "reevaluator": expectations.reevaluator_sha256,
        "manifest": expectations.manifest_sha256,
        "all150_report": expectations.all150_report_sha256,
        "independent82_report": expectations.independent82_report_sha256,
    }
    blockers: list[str] = []
    hashes: dict[str, str | None] = {}
    for name, path in paths.items():
        if not path.is_file():
            blockers.append(f"s27_b0_v3_{name}_missing")
            hashes[name] = None
            continue
        hashes[name] = _sha256(path)
        if hashes[name] != expected_hashes[name]:
            blockers.append(f"s27_b0_v3_{name}_hash_mismatch")
    manifest: dict[str, Any] = {}
    if paths["manifest"].is_file():
        try:
            manifest = _load(paths["manifest"])
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            blockers.append("s27_b0_v3_manifest_invalid_json")
    if manifest:
        if (
            manifest.get("schema_version") != "estg150_b0_v3_reevaluation_manifest@1.0.0"
            or manifest.get("status") != "succeeded_development_not_formal"
            or manifest.get("models_rerun") is not False
        ):
            blockers.append("s27_b0_v3_manifest_identity_mismatch")
        safety = manifest.get("safety", {})
        if (
            safety.get("paper_score_targeting_used") is not False
            or safety.get("threshold_search_used") is not False
            or safety.get("llm_api_called") is not False
            or safety.get("network_called") is not False
        ):
            blockers.append("s27_b0_v3_safety_mismatch")
        comparison = manifest.get("literature_comparison", {})
        if (
            comparison.get("direct_numeric_comparison_valid") is not False
            or comparison.get("within_10_percentage_points_requirement_evaluated") is not False
        ):
            blockers.append("s27_b0_v3_literature_boundary_mismatch")
    return {
        "ready": not blockers,
        "task_id": "S2.7-B0-DEV-REEVAL",
        "blockers": sorted(set(blockers)),
        "hashes": hashes,
        "sample_count": manifest.get("tracks", {}).get("all150", {}).get("sample_count"),
        "modality_micro": manifest.get("tracks", {}).get("all150", {}).get("modality_micro"),
        "modality_macro_f1": manifest.get("tracks", {}).get("all150", {}).get("modality_macro_f1"),
        "formal_performance_result": False,
        "models_rerun": False,
    }


@lru_cache(maxsize=4)
def get_cached_s2_10_evaluator_v3_gate(root: Path) -> dict[str, Any]:
    return verify_s2_10_evaluator_v3_gate(root)


@lru_cache(maxsize=4)
def get_cached_s2_7_b0_v3_gate(root: Path) -> dict[str, Any]:
    return verify_s2_7_b0_v3_gate(root)

"""Exact-hash gate for the S2.10-E unified Stage 2 evaluator contract."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage2_evaluation import Stage2EvaluationError, load_evaluator_contract


CONTRACT_REL = "configs/stage2_evaluator_s210.json"
REPORT_SCHEMA_REL = "configs/schemas/stage2_evaluation_report.schema.json"
STYLE_SCHEMA_REL = "configs/schemas/style_equivalent_review.schema.json"
CANONICAL_SCHEMA_REL = "configs/schemas/stage2_prediction.schema.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/stage2_evaluation.py"
RUNNER_REL = "scripts/evaluate_stage2_s210.py"
VERIFIER_REL = "scripts/verify_stage2_evaluator_s210.py"
FIXTURE_REL = "tests/fixtures/stage2_evaluator/s210_contract_fixture.json"
MANIFEST_REL = "outputs/reports/s210_stage2_evaluator_contract_synthetic_v2.manifest.json"
EXPERIMENT_CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S210Expectations:
    contract_sha256: str = "2b6f7bd4269e475dc4b7bb0561a767a70baba49965c16c7f6b34b8a455badc16"
    report_schema_sha256: str = "9906dce85eaf72995e2a3381eed0e33a0c32f5cbf75d35425f7b97c50ea79c5a"
    style_schema_sha256: str = "9348a8a267137306b700f88b0f56c03db792c41bc7815ea85ee9969a1211d499"
    canonical_schema_sha256: str = "7485ac4a3a42b976d87e63a7d2ead88cc3df1f810b14dd066bc1f63c15599d1b"
    implementation_sha256: str = "86be001f6eb956fbb1e743eb4efc9c571f8da30208628c6683934157cf359938"
    runner_sha256: str = "92104261557dd9655d477af42ab88d2ef56345e9c6d388751554faad27062316"
    verifier_sha256: str = "4724f614b37e5422c72ea48ec9945251f401ee7f5362e71bb52f3431d5eb42e0"
    fixture_sha256: str = "549c11ce259ed1a754e7ae99845a09318bcbdefd48426784880cd11fe8164c62"
    manifest_sha256: str = "58d65b256225942593b853b0b5f1777de56caca4b9059a28d128e001a933f89b"


S210_EXPECTATIONS = S210Expectations()


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
        raise Stage2EvaluationError(f"invalid S2.10 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise Stage2EvaluationError(f"S2.10 JSON root must be an object: {path}")
    return value


def verify_s2_10_evaluator_gate(
    project_root: Path,
    *,
    expectations: S210Expectations = S210_EXPECTATIONS,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    errors: list[dict[str, str]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition and code not in {item["code"] for item in errors}:
            errors.append({"code": code, "message": message})

    paths = {
        "contract": root / CONTRACT_REL,
        "report_schema": root / REPORT_SCHEMA_REL,
        "style_schema": root / STYLE_SCHEMA_REL,
        "canonical_schema": root / CANONICAL_SCHEMA_REL,
        "implementation": root / IMPLEMENTATION_REL,
        "runner": root / RUNNER_REL,
        "verifier": root / VERIFIER_REL,
        "fixture": root / FIXTURE_REL,
        "manifest": root / MANIFEST_REL,
        "experiment_contract": root / EXPERIMENT_CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s210_artifact_missing", f"Missing S2.10 {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "experiment_contract"}
    for name, expected in (
        ("contract", expectations.contract_sha256),
        ("report_schema", expectations.report_schema_sha256),
        ("style_schema", expectations.style_schema_sha256),
        ("canonical_schema", expectations.canonical_schema_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("fixture", expectations.fixture_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"s210_{name}_hash_mismatch", f"S2.10 {name} SHA-256 changed")

    try:
        contract = load_evaluator_contract(paths["contract"])
        manifest = _load(paths["manifest"])
        experiment_contract = _load(paths["experiment_contract"])
    except Stage2EvaluationError as exc:
        require(False, "s210_artifact_invalid", str(exc))
        contract = {}
        manifest = {}
        experiment_contract = {}

    artifact_map = manifest.get("artifacts", {})
    require(
        manifest.get("schema_version") == "s210_evaluator_verification_manifest@1.1.0"
        and manifest.get("task_id") == "S2.10-E"
        and manifest.get("run_id") == "s210_stage2_evaluator_contract_synthetic_v2"
        and manifest.get("status") == "succeeded"
        and all(
            isinstance(artifact_map.get(manifest_name), Mapping)
            and artifact_map[manifest_name].get("sha256") == hashes[hash_name]
            for manifest_name, hash_name in (
                ("contract", "contract"),
                ("report_schema", "report_schema"),
                ("style_review_schema", "style_schema"),
                ("canonical_schema", "canonical_schema"),
                ("implementation", "implementation"),
                ("runner", "runner"),
                ("verifier", "verifier"),
                ("fixture", "fixture"),
            )
        ),
        "s210_manifest_identity_mismatch",
        "S2.10 manifest identity or artifact binding changed",
    )
    verification = manifest.get("verification", {})
    require(
        isinstance(verification, Mapping)
        and verification.get("membership_payload_sha256")
        == "f74be514b6ffed61cb196feb730ec6db29ca0c8e2ffd6a00cf248a6187e5af47"
        and verification.get("sample_count") == 5
        and verification.get("report_schema_valid") is True
        and verification.get("style_review_schema_valid") is True
        and verification.get("style_review_human_decisions_filled") == 0
        and verification.get("array_order_invariant") is True
        and verification.get("missing_attempt_fail_closed") is True
        and verification.get("formal_scope_fail_closed") is True
        and verification.get("action_strict_f1_synthetic") == 0.25
        and verification.get("action_safe_f1_synthetic") == 0.5
        and verification.get("schema_valid_rate_synthetic") == 0.6
        and verification.get("api_error_rate_synthetic") == 0.2
        and verification.get("recovered_api_error_rate_synthetic") == 0.2
        and verification.get("any_api_error_rate_synthetic") == 0.4,
        "s210_verification_mismatch",
        "S2.10 synthetic evaluator constants or fail-closed checks changed",
    )
    require(
        manifest.get("safety")
        == {
            "synthetic_fixture_only": True,
            "formal_gold_read_or_modified": False,
            "formal_predictions_read_or_created": False,
            "formal_performance_evaluation": False,
            "method_comparison": False,
            "llm_api_called": False,
            "network_called": False,
            "row_level_predictions_persisted": False,
        },
        "s210_safety_boundary_mismatch",
        "S2.10 synthetic-only safety boundary changed",
    )
    require(
        contract.get("methods") == ["sun_rule_only", "sun_llm_fallback", "direct_llm"]
        and contract.get("attempt_envelope", {}).get("api_errors_remain_in_denominator") is True
        and contract.get("attempt_envelope", {}).get("invalid_records_remain_in_denominator") is True
        and contract.get("style_equivalent_review", {}).get("human_only") is True
        and contract.get("style_equivalent_review", {}).get("auto_fill_forbidden") is True,
        "s210_contract_semantics_mismatch",
        "S2.10 method, denominator, or human-review semantics changed",
    )

    gate = experiment_contract.get("stage2_evaluator_gate", {})
    expected_lock = {
        "contract": (CONTRACT_REL, hashes["contract"]),
        "report_schema": (REPORT_SCHEMA_REL, hashes["report_schema"]),
        "style_review_schema": (STYLE_SCHEMA_REL, hashes["style_schema"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "synthetic_fixture": (FIXTURE_REL, hashes["fixture"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.10-E"
        and gate.get("status") == "verified_offline_unified_evaluator_contract"
        and gate.get("ready") is True
        and gate.get("main_data_results_ready") is False
        and gate.get("formal_performance_evaluation_run") is False
        and gate.get("formal_gold_read_or_modified") is False
        and gate.get("llm_api_called") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_lock.items()
        ),
        "s210_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.10 evaluator artifacts or boundaries",
    )
    return {
        "ready": not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "main_data_results_ready": False,
        "formal_performance_evaluation_run": False,
        "sample_count": verification.get("sample_count") if isinstance(verification, Mapping) else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONTRACT_REL,
        REPORT_SCHEMA_REL,
        STYLE_SCHEMA_REL,
        CANONICAL_SCHEMA_REL,
        IMPLEMENTATION_REL,
        RUNNER_REL,
        VERIFIER_REL,
        FIXTURE_REL,
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
    return verify_s2_10_evaluator_gate(Path(root))


def get_cached_s2_10_evaluator_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

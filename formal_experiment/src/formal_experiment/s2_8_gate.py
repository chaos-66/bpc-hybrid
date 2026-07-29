"""Fail-closed machine gate for the verified S2.8 H1 preregistration."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.stage2_canonical import validate_canonical
from bpc_hybrid.sun_style.h1_selective import H1ContractError, load_s28_config


CONFIG_REL = "configs/models/sun_h1_s28.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/sun_style/h1_selective.py"
RUNNER_REL = "scripts/run_sun_llm_fallback.py"
VERIFIER_REL = "scripts/verify_sun_h1_s28.py"
PROMPT_REL = "prompts/sun_compat/rule_first_llm_fallback_prompt.md"
EXTRACTION_REL = "configs/stage2_extraction_contract_v1.json"
BUNDLE_REL = "configs/stage2_extraction_bundle_v1.json"
MANIFEST_REL = "outputs/reports/s28_sun_h1_selective_dry_run_v6.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S28Expectations:
    config_sha256: str = "dd99e8c5b6ba3c858d505705bdf6144d57e462651c4d8be7c521007c2afd1bef"
    implementation_sha256: str = "f8c647c9d4fb1c701319746ee09437f30147cb6955b68bb70bbff28a496269f3"
    runner_sha256: str = "d491c0a80357c76dd4b3cdec9bf5d706f5f31a916d5999976c9c305ee71f5167"
    verifier_sha256: str = "f9d63ea57bcb9624032476abca3c02e1222ede6392dda231e4c300d573b64382"
    prompt_sha256: str = "54e56c4bc52d0e5a83c2b45c3762a36ffb1356bd8190a1cd10d2b5dbd304b40c"
    extraction_contract_sha256: str = "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46"
    bundle_sha256: str = "9de618048c45fa2d591acdfe1e6aaa5f16915c85df54ecb6e958e9b4310416b2"
    manifest_sha256: str = "f50d89297a5547beb7d4a65526568724419d475af6b829c6bb209082c39d085c"


S28_EXPECTATIONS = S28Expectations()


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
        raise H1ContractError(f"invalid S2.8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise H1ContractError(f"S2.8 JSON root must be an object: {path}")
    return value


def verify_s2_8_gate(
    project_root: Path,
    *,
    expectations: S28Expectations = S28_EXPECTATIONS,
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
        "prompt": root / PROMPT_REL,
        "extraction_contract": root / EXTRACTION_REL,
        "bundle": root / BUNDLE_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s2_8_artifact_missing", f"Missing S2.8 {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("prompt", expectations.prompt_sha256),
        ("extraction_contract", expectations.extraction_contract_sha256),
        ("bundle", expectations.bundle_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"s2_8_{name}_hash_mismatch", f"S2.8 {name} SHA-256 changed")

    try:
        config = load_s28_config(paths["config"])
        manifest = _load(paths["manifest"])
        contract = _load(paths["contract"])
    except H1ContractError as exc:
        require(False, "s2_8_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        contract = {}

    selection = manifest.get("selection", {})
    merge = manifest.get("merge_verification", {})
    budget = manifest.get("budget_verification", {})
    request = manifest.get("request_verification", {})
    allocation = manifest.get("allocation_verification", {})
    fallback = manifest.get("fallback_attempt_verification", {})
    safety = manifest.get("safety", {})
    accepted_record = merge.get("accepted_record", {}) if isinstance(merge, Mapping) else {}
    report = validate_canonical(accepted_record) if isinstance(accepted_record, dict) and accepted_record else None
    require(
        manifest.get("schema_version") == "sun_h1_s28_verification_manifest@1.2.0"
        and manifest.get("task_id") == "S2.8"
        and manifest.get("status") == "succeeded"
        and manifest.get("method") == "sun_llm_fallback"
        and manifest.get("artifacts", {}).get("config", {}).get("sha256") == hashes["config"]
        and manifest.get("artifacts", {}).get("extraction_contract", {}).get("sha256")
        == hashes["extraction_contract"],
        "s2_8_manifest_identity_mismatch",
        "S2.8 verification manifest identity changed",
    )
    require(
        manifest.get("baseline_binding", {}).get("s2_6_gate_ready") is True
        and manifest.get("baseline_binding", {}).get("legacy_front_end_used") is False
        and manifest.get("baseline_binding", {}).get("record_method") == "sun_rule_only",
        "s2_8_baseline_binding_mismatch",
        "S2.8 no longer binds the verified S2.6 B0 record",
    )
    require(
        isinstance(selection, Mapping)
        and selection.get("evidence_boundary") == "inference_time_observations_only_no_gold_or_test_distribution"
        and selection.get("gold_or_test_derived_trigger_used") is False
        and selection.get("clean_plan", {}).get("fallback_triggered") is False
        and selection.get("triggered_plan", {}).get("trigger_codes") == ["tregex_field_conflict"]
        and selection.get("triggered_plan", {}).get("repair_fields")
        == ["actions", "actor_action_map", "order_relations"],
        "s2_8_selection_mismatch",
        "S2.8 inference-visible trigger or dependency closure changed",
    )
    require(
        isinstance(merge, Mapping)
        and merge.get("accepted_patch", {}).get("accepted") is True
        and merge.get("unrequested_fields_preserved") is True
        and merge.get("same_field_id_preserved") is True
        and merge.get("unauthorized_patch", {}).get("accepted") is False
        and merge.get("rejected_patch_returned_original_b0") is True
        and merge.get("controlled_uncertainty_metadata_preserved") is True
        and report is not None
        and report.schema_valid
        and report.cross_field_valid
        and accepted_record.get("method", {}).get("name") == "sun_llm_fallback",
        "s2_8_merge_mismatch",
        "S2.8 field-level merge or fail-closed fallback evidence changed",
    )
    require(
        isinstance(request, Mapping)
        and request.get("exact_model_id") == "gpt-4.1-2025-04-14"
        and request.get("sampling") == config.get("sampling")
        and request.get("prompt_file_sha256_matches") is True
        and request.get("unrendered_placeholder_detected") is False
        and request.get("rendered_request", {}).get("model") == "gpt-4.1-2025-04-14",
        "s2_8_request_mismatch",
        "S2.8 exact model, sampling, or rendered request evidence changed",
    )
    require(
        isinstance(allocation, Mapping)
        and allocation.get("candidate_order") == "ascending_sample_id_then_clause_id"
        and allocation.get("input_array_order_invariant") is True
        and allocation.get("reserved_call_count") == 45
        and allocation.get("call_46_and_later_rejected") is True
        and allocation.get("duplicate_sample_rejected") is True,
        "s2_8_allocation_mismatch",
        "S2.8 deterministic allocation evidence changed",
    )
    require(
        isinstance(budget, Mapping)
        and budget.get("target_dataset_size") == 150
        and budget.get("max_call_fraction") == 0.3
        and budget.get("hard_call_limit") == 45
        and budget.get("input_token_ceiling_per_request") == 8192
        and budget.get("output_token_ceiling_per_request") == 2048
        and budget.get("total_token_ceiling") == 460800
        and budget.get("estimated_worst_case_cost_usd") == 1.47456
        and budget.get("hard_cost_ceiling_usd") == 1.5
        and budget.get("max_retries") == 0,
        "s2_8_budget_mismatch",
        "S2.8 call, token, or cost budget evidence changed",
    )
    require(
        isinstance(fallback, Mapping)
        and fallback.get("request_status") == "ok"
        and fallback.get("record_method") == "sun_llm_fallback"
        and fallback.get("semantic_b0_content_preserved") is True
        and fallback.get("recovered_runtime_error_category") == "timeout"
        and fallback.get("schema_valid_rate") == 1.0
        and fallback.get("terminal_api_error_rate") == 0.0
        and fallback.get("recovered_api_error_rate") == 1.0
        and fallback.get("any_api_error_rate") == 1.0
        and fallback.get("scored_as_h1") is True,
        "s2_8_fallback_attempt_mismatch",
        "S2.8 recovered-provider-error fallback is no longer scorable as H1",
    )
    require(
        safety == {
            "synthetic_fixture_only": True,
            "performance_evaluation": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "test_split_read_or_evaluated": False,
            "formal_predictions_written": False,
        },
        "s2_8_safety_boundary_mismatch",
        "S2.8 safety boundary changed",
    )

    gate = contract.get("sun_stage2_method", {}).get("h1_preregistration_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "prompt": (PROMPT_REL, hashes["prompt"]),
        "extraction_contract": (EXTRACTION_REL, hashes["extraction_contract"]),
        "extraction_bundle": (BUNDLE_REL, hashes["bundle"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.8"
        and gate.get("status") == "verified_offline_preregistration_no_real_llm"
        and gate.get("ready") is True
        and gate.get("s2_6_baseline_bound") is True
        and gate.get("inference_visible_triggers_only") is True
        and gate.get("field_level_merge_verified") is True
        and gate.get("fail_closed_to_original_b0") is True
        and gate.get("exact_model_id") == "gpt-4.1-2025-04-14"
        and gate.get("deterministic_allocation_verified") is True
        and gate.get("recovered_provider_error_scorable") is True
        and gate.get("hard_call_limit") == 45
        and gate.get("total_token_ceiling") == 460800
        and gate.get("hard_cost_ceiling_usd") == 1.5
        and gate.get("real_llm_authorized") is False
        and gate.get("llm_api_called") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_lock.items()
        ),
        "s2_8_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.8 artifacts or boundaries",
    )
    return {
        "ready": not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "hard_call_limit": budget.get("hard_call_limit") if isinstance(budget, Mapping) else None,
        "real_llm_authorized": config.get("budget", {}).get("real_api_authorized") if isinstance(config, Mapping) else None,
        "llm_api_called": safety.get("llm_api_called") if isinstance(safety, Mapping) else None,
        "performance_evaluation": safety.get("performance_evaluation") if isinstance(safety, Mapping) else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        IMPLEMENTATION_REL,
        RUNNER_REL,
        VERIFIER_REL,
        PROMPT_REL,
        EXTRACTION_REL,
        BUNDLE_REL,
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
    return verify_s2_8_gate(Path(root))


def get_cached_s2_8_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

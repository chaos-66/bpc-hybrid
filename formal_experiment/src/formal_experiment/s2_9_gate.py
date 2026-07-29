"""Fail-closed machine gate for the verified offline S2.9 D1 preregistration."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from bpc_hybrid.prompt_loader import load_prompt
from bpc_hybrid.sun_style.d1_direct import D1ContractError, load_s29_config
from formal_experiment.s2_10_evaluator_gate import verify_s2_10_evaluator_gate


CONFIG_REL = "configs/models/sun_d1_s29.json"
IMPLEMENTATION_REL = "src/bpc_hybrid/sun_style/d1_direct.py"
RUNNER_REL = "scripts/run_direct_llm.py"
VERIFIER_REL = "scripts/verify_sun_d1_s29.py"
PROMPT_REL = "prompts/sun_compat/direct_llm_sun_record_prompt.md"
FIXTURE_REL = "tests/fixtures/d1_s29/s29_offline_contract_fixture.json"
EXTRACTION_REL = "configs/stage2_extraction_contract_v1.json"
BUNDLE_REL = "configs/stage2_extraction_bundle_v1.json"
MANIFEST_REL = "outputs/reports/s29_sun_d1_offline_prereg_v5.manifest.json"
CONTRACT_REL = "configs/experiment_contract.json"


@dataclass(frozen=True)
class S29Expectations:
    config_sha256: str = "c891e8a0e64a5c60a5bf7e8d0e7330a656e9535f3e069737e5d7ee657066178f"
    implementation_sha256: str = "0fb1861b09766cade085cd74cf2a3a726d817a0557a4dbe2b6d203752fa396db"
    runner_sha256: str = "3d65c305eafbcfcdd5c62a1ec6e95a9f3ca7792dbaa4c59ff74941c826d43ec3"
    verifier_sha256: str = "72ba22c7eccb6c98d49f40702a71a54394c7c22e69b39f6a1999f7baaf8a3f63"
    prompt_file_sha256: str = "79f6f76fc9779abb87fc919e4384386ac812d40fcedaf73df0ea8ea1377af62e"
    prompt_render_sha256: str = "79f6f76fc9779abb87fc919e4384386ac812d40fcedaf73df0ea8ea1377af62e"
    extraction_contract_sha256: str = "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46"
    bundle_sha256: str = "9de618048c45fa2d591acdfe1e6aaa5f16915c85df54ecb6e958e9b4310416b2"
    fixture_sha256: str = "729ccc98d83c128d1feed7f9cc86a05befeb89ef2da4dd95dc1dc6ced588f4d9"
    manifest_sha256: str = "a9c4fa7f25f9d566bb1b8d06ac8f272269de20c439eaf5946c0e985794e066c3"


S29_EXPECTATIONS = S29Expectations()


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
        raise D1ContractError(f"invalid S2.9 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise D1ContractError(f"S2.9 JSON root must be an object: {path}")
    return value


def verify_s2_9_gate(
    project_root: Path,
    *,
    expectations: S29Expectations = S29_EXPECTATIONS,
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
        "fixture": root / FIXTURE_REL,
        "extraction_contract": root / EXTRACTION_REL,
        "bundle": root / BUNDLE_REL,
        "manifest": root / MANIFEST_REL,
        "contract": root / CONTRACT_REL,
    }
    for name, path in paths.items():
        require(path.is_file(), "s2_9_artifact_missing", f"Missing S2.9 {name}: {path}")
    if errors:
        return {"ready": False, "errors": errors, "blockers": [item["code"] for item in errors]}

    hashes = {name: _sha256(path) for name, path in paths.items() if name != "contract"}
    for name, expected in (
        ("config", expectations.config_sha256),
        ("implementation", expectations.implementation_sha256),
        ("runner", expectations.runner_sha256),
        ("verifier", expectations.verifier_sha256),
        ("prompt", expectations.prompt_file_sha256),
        ("fixture", expectations.fixture_sha256),
        ("extraction_contract", expectations.extraction_contract_sha256),
        ("bundle", expectations.bundle_sha256),
        ("manifest", expectations.manifest_sha256),
    ):
        require(hashes[name] == expected, f"s2_9_{name}_hash_mismatch", f"S2.9 {name} SHA-256 changed")

    try:
        config = load_s29_config(paths["config"])
        manifest = _load(paths["manifest"])
        contract = _load(paths["contract"])
        prompt = load_prompt(config["prompt"]["name"])
    except (D1ContractError, OSError, ValueError) as exc:
        require(False, "s2_9_artifact_invalid", str(exc))
        config = {}
        manifest = {}
        contract = {}
        prompt = None

    require(
        prompt is not None
        and prompt.sha256 == expectations.prompt_render_sha256
        and len(prompt.few_shot_examples) == 4
        and "{few_shot_block}" in prompt.user_prompt_template,
        "s2_9_prompt_contract_mismatch",
        "S2.9 actual prompt rendering source or four-shot insertion changed",
    )
    require(
        manifest.get("schema_version") == "sun_d1_s29_verification_manifest@1.1.0"
        and manifest.get("task_id") == "S2.9"
        and manifest.get("status") == "succeeded"
        and manifest.get("method") == "direct_llm"
        and all(
            manifest.get("artifacts", {}).get(name, {}).get("sha256") == hashes[name]
            for name in (
                "config",
                "implementation",
                "runner",
                "verifier",
                "prompt",
                "fixture",
                "extraction_contract",
            )
        ),
        "s2_9_manifest_identity_mismatch",
        "S2.9 verification manifest identity or artifact lock changed",
    )
    model = manifest.get("model_and_sampling", {})
    require(
        isinstance(model, Mapping)
        and model.get("provider") == "openai_compatible"
        and model.get("exact_model_id") == "gpt-4.1-2025-04-14"
        and model.get("pin_type") == "dated_snapshot"
        and model.get("sampling") == config.get("sampling")
        and model.get("real_api_authorized") is False,
        "s2_9_model_sampling_mismatch",
        "S2.9 pinned model or deterministic sampling changed",
    )
    rendering = manifest.get("prompt_rendering", {})
    require(
        isinstance(rendering, Mapping)
        and rendering.get("prompt_sha256") == expectations.prompt_render_sha256
        and rendering.get("few_shot_count_parsed") == 4
        and rendering.get("few_shot_count_in_actual_request") == 4
        and rendering.get("unresolved_template_placeholder") is False,
        "s2_9_rendering_evidence_mismatch",
        "S2.9 actual-request four-shot rendering evidence changed",
    )
    plan = manifest.get("request_plan", {})
    require(
        isinstance(plan, Mapping)
        and plan.get("input_count") == 3
        and plan.get("repeat_count") == 5
        and plan.get("request_count") == 15
        and plan.get("unique_request_count") == 15
        and plan.get("primary_repeat_index") == 1
        and plan.get("all_requests_have_four_few_shots") is True,
        "s2_9_request_plan_mismatch",
        "S2.9 five-repeat request plan changed",
    )
    attempts = manifest.get("attempt_envelope_verification", {})
    require(
        isinstance(attempts, Mapping)
        and attempts.get("attempt_count") == 3
        and attempts.get("canonical_valid_count") == 1
        and attempts.get("schema_or_cross_field_invalid_count") == 1
        and attempts.get("api_error_count") == 1
        and attempts.get("membership_exact") is True
        and attempts.get("dropped_attempt_count") == 0
        and attempts.get("raw_response_persisted") is False
        and attempts.get("invalid_and_api_attempts_retained") is True
        and attempts.get("s2_10_evaluator_gate_ready") is True,
        "s2_9_attempt_envelope_mismatch",
        "S2.9 failure-preserving S2.10-E attempt envelope changed",
    )
    budget = manifest.get("budget_verification", {})
    require(
        isinstance(budget, Mapping)
        and budget.get("target_dataset_size") == 150
        and budget.get("repeat_count") == 5
        and budget.get("hard_call_limit") == 750
        and budget.get("max_retries") == 0
        and budget.get("total_token_ceiling") == 9_216_000
        and budget.get("estimated_worst_case_cost_usd") == 36.864
        and budget.get("hard_cost_ceiling_usd") == 37.0,
        "s2_9_budget_mismatch",
        "S2.9 call/token/cost ceiling changed",
    )
    require(
        manifest.get("input_isolation") == {
            "gold_visible_to_method": False,
            "b0_or_h1_prediction_visible": False,
            "rule_front_end_used": False,
            "same_future_frozen_input_required": True,
        },
        "s2_9_input_isolation_mismatch",
        "S2.9 no-Gold/no-B0 input isolation changed",
    )
    require(
        manifest.get("safety") == {
            "synthetic_fixture_only": True,
            "performance_evaluation": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "env_file_read": False,
            "test_split_read_or_evaluated": False,
            "formal_predictions_written": False,
        },
        "s2_9_safety_boundary_mismatch",
        "S2.9 offline safety boundary changed",
    )
    s210_gate = verify_s2_10_evaluator_gate(root)
    require(
        s210_gate.get("ready") is True,
        "s2_9_evaluator_binding_mismatch",
        "S2.9 no longer binds a ready S2.10-E evaluator",
    )

    gate = contract.get("sun_stage2_method", {}).get("d1_preregistration_gate", {})
    expected_lock = {
        "config": (CONFIG_REL, hashes["config"]),
        "implementation": (IMPLEMENTATION_REL, hashes["implementation"]),
        "runner": (RUNNER_REL, hashes["runner"]),
        "verifier": (VERIFIER_REL, hashes["verifier"]),
        "prompt": (PROMPT_REL, hashes["prompt"]),
        "fixture": (FIXTURE_REL, hashes["fixture"]),
        "extraction_contract": (EXTRACTION_REL, hashes["extraction_contract"]),
        "extraction_bundle": (BUNDLE_REL, hashes["bundle"]),
        "verification_manifest": (MANIFEST_REL, hashes["manifest"]),
    }
    require(
        isinstance(gate, Mapping)
        and gate.get("task_id") == "S2.9"
        and gate.get("status") == "verified_offline_preregistration_no_real_llm"
        and gate.get("ready") is True
        and gate.get("exact_model_id") == "gpt-4.1-2025-04-14"
        and gate.get("few_shot_count") == 4
        and gate.get("repeat_count") == 5
        and gate.get("hard_call_limit") == 750
        and gate.get("max_retries") == 0
        and gate.get("failed_attempts_retained") is True
        and gate.get("s2_10_evaluator_bound") is True
        and gate.get("real_llm_authorized") is False
        and gate.get("llm_api_called") is False
        and gate.get("env_file_read") is False
        and all(
            gate.get(name, {}).get("path") == path
            and gate.get(name, {}).get("sha256") == sha
            for name, (path, sha) in expected_lock.items()
        ),
        "s2_9_experiment_contract_mismatch",
        "Experiment contract disagrees with S2.9 artifacts or boundaries",
    )
    return {
        "ready": not errors,
        "errors": errors,
        "blockers": [item["code"] for item in errors],
        "hashes": hashes,
        "exact_model_id": model.get("exact_model_id") if isinstance(model, Mapping) else None,
        "repeat_count": plan.get("repeat_count") if isinstance(plan, Mapping) else None,
        "hard_call_limit": budget.get("hard_call_limit") if isinstance(budget, Mapping) else None,
        "real_llm_authorized": config.get("model", {}).get("real_api_authorized")
        if isinstance(config, Mapping)
        else None,
        "llm_api_called": manifest.get("safety", {}).get("llm_api_called")
        if isinstance(manifest, Mapping)
        else None,
        "performance_evaluation": manifest.get("safety", {}).get("performance_evaluation")
        if isinstance(manifest, Mapping)
        else None,
    }


def _fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    result: list[tuple[str, int, int]] = []
    for relative in (
        CONFIG_REL,
        IMPLEMENTATION_REL,
        RUNNER_REL,
        VERIFIER_REL,
        PROMPT_REL,
        FIXTURE_REL,
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
    return verify_s2_9_gate(Path(root))


def get_cached_s2_9_gate(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    return copy.deepcopy(_cached(str(root), _fingerprint(root)))

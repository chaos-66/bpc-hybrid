"""Canonical EStG-150 candidate-protocol runner (C0-C4).

C0 is offline.  C1-C4 remain fail-closed unless the user has explicitly
authorized provider, call, token, and cost ceilings and passes matching CLI
flags.  No generation stage reads Layer D, Layer E, or Gold.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from formal_experiment.estg150_candidate_protocol import (  # noqa: E402
    CONFIG_PATH,
    LOCK_PATH,
    SEMANTIC_FIXTURE_PATH,
    SYNTHETIC_FIXTURE_PATH,
    CandidateValidationError,
    ProtocolError,
    ProtocolIncompatible,
    ProviderHTTPError,
    RetryableTransportError,
    adapter_from_config,
    build_semantic_request,
    canonical_json_bytes,
    extract_provider_response,
    extract_provider_response_envelope,
    generate_c0_lock_payload,
    load_json_bytes,
    load_protocol_assets,
    now_utc,
    post_identical_request_with_retries,
    route_for_index,
    safe_run_dir,
    serialize_semantic_request,
    sha256_bytes,
    sha256_path,
    validate_candidate,
    verify_c0_lock,
)
from formal_experiment.estg150_c1_transport import (  # noqa: E402
    load_portable_transport_adapter,
    load_strict_transport_adapter,
    prepare_transport_request,
    serialized_transport_sha256,
    transport_provenance,
)


PREREG_TEMPLATE_PATH = ROOT / "configs" / "estg150_candidate_preregistration_template_v1_1.json"
C1_RUNTIME_MANIFEST_PATH = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "c1_relay_gpt56_luna_strict_v1_1_pilot_v1"
    / "manifest.json"
)
C2_OFFLINE_PASS_A_RUN_DIR = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "codex_internal_gpt56sol_pilot3_v1"
)
C2_OFFLINE_PASS_A_CONFIG_PATH = C2_OFFLINE_PASS_A_RUN_DIR / "run_config.json"
C2_OFFLINE_PASS_A_PATH = C2_OFFLINE_PASS_A_RUN_DIR / "pass_a_candidates.json"


def write_bytes_no_overwrite(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(value)


def write_json_no_overwrite(path: Path, value: Any) -> None:
    write_bytes_no_overwrite(path, json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")


def reviewed_candidate_text_en(
    sample: dict[str, Any], route: str, pass_a_candidate: dict[str, Any] | None
) -> str:
    """Return the exact English candidate whose translation decision is being reviewed."""
    if route in {"pass_a", "full_extract"}:
        return sample["frozen_candidate_text_en"]
    if route != "pass_b":
        raise ProtocolError(f"unsupported review route: {route!r}")
    if pass_a_candidate is None:
        raise ProtocolError("Pass B requires the validated same-run Pass A candidate")
    try:
        text = pass_a_candidate["translation"]["proposed_text_en"]
    except (KeyError, TypeError) as exc:
        raise ProtocolError("Pass B dependency has no proposed English candidate") from exc
    if not isinstance(text, str) or not text:
        raise ProtocolError("Pass B dependency proposed English candidate must be non-empty")
    return text


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    with path.open("ab") as handle:
        handle.write(canonical_json_bytes(value))


def archive_provider_http_error(
    run_dir: Path, stem: str, exc: ProviderHTTPError, *, api_key: str
) -> dict[str, Any]:
    """Archive bounded raw provider error bytes unless they echo the credential."""
    request_id_echo_detected = bool(
        exc.provider_request_id and api_key and api_key in exc.provider_request_id
    )
    diagnostic: dict[str, Any] = {
        "http_status": exc.http_status,
        "provider_request_id": None if request_id_echo_detected else exc.provider_request_id,
        "retry_reasons": list(exc.retry_reasons),
        "provider_error_response_truncated": exc.response_body_truncated,
    }
    if exc.response_body is None:
        diagnostic["provider_error_response_archived"] = False
        diagnostic["provider_error_response_bytes"] = None
        diagnostic["provider_error_response_sha256"] = None
        diagnostic["credential_echo_detected"] = request_id_echo_detected
        return diagnostic

    response_body = exc.response_body
    diagnostic["provider_error_response_bytes"] = len(response_body)
    diagnostic["provider_error_response_sha256"] = sha256_bytes(response_body)
    credential_echo_detected = request_id_echo_detected or api_key.encode("utf-8") in response_body
    diagnostic["credential_echo_detected"] = credential_echo_detected
    if credential_echo_detected:
        diagnostic["provider_error_response_archived"] = False
        return diagnostic

    relative_path = Path("responses") / f"{stem}.http_error.body"
    write_bytes_no_overwrite(run_dir / relative_path, response_body)
    diagnostic["provider_error_response_archived"] = True
    diagnostic["provider_error_response_path"] = relative_path.as_posix()
    return diagnostic


def planned_samples(assets: Any, stage: str) -> tuple[dict[str, Any], ...]:
    if stage == "c1":
        return (load_json_bytes(SYNTHETIC_FIXTURE_PATH),)
    if stage == "c2":
        return assets.samples[:3]
    if stage in {"c3", "c4"}:
        return assets.samples
    raise ProtocolError(f"stage {stage!r} has no provider request plan")


def expected_request_count(samples: tuple[dict[str, Any], ...]) -> int:
    return sum(len(route_for_index(int(sample["sample_index"]))) for sample in samples)


def enforce_stage_provider(stage: str, provider_adapter: str) -> None:
    allowed = {
        "c1": {"relay_openai_compatible", "deepseek_official", "qwen_official", "xai_official"},
        "c2": {"relay_openai_compatible"},
        "c3": {"deepseek_official", "qwen_official"},
        "c4": {"xai_official"},
    }[stage]
    if provider_adapter not in allowed:
        raise ProtocolError(f"stage {stage} permits provider adapters {sorted(allowed)!r}")


def c0_write_or_verify() -> dict[str, Any]:
    assets = load_protocol_assets()
    synthetic = load_json_bytes(SYNTHETIC_FIXTURE_PATH)
    semantic = build_semantic_request(assets, synthetic, route="full_extract")
    fixture_bytes = serialize_semantic_request(semantic)
    lock_payload = generate_c0_lock_payload(assets, fixture_bytes)
    if SEMANTIC_FIXTURE_PATH.exists():
        if SEMANTIC_FIXTURE_PATH.read_bytes() != fixture_bytes:
            raise ProtocolError("existing serializer fixture drifted; refusing overwrite")
    else:
        write_bytes_no_overwrite(SEMANTIC_FIXTURE_PATH, fixture_bytes)
    if LOCK_PATH.exists():
        if load_json_bytes(LOCK_PATH) != lock_payload:
            raise ProtocolError("existing C0 lock drifted; refusing overwrite")
    else:
        write_json_no_overwrite(LOCK_PATH, lock_payload)
    return verify_c0_lock(assets)


def dry_run(args: argparse.Namespace, assets: Any, lock: dict[str, Any]) -> int:
    if args.stage == "c0":
        print("C0 dry-run verified; no network/API call was made.")
        print(f"protocol_version={assets.config['protocol_version']}")
        print(f"serializer_sha256={lock['serializer_sha256']}")
        print(f"serializer_fixture_sha256={lock['serializer_fixture_sha256']}")
        print("historical_hidden_transport_payload_not_archived=true")
        print("sample_order=Layer A byte order; routes=0-2 Pass A+Pass B, 3-149 full_extract")
        print("planned_all150_requests=153")
        print("Layer D/E/Gold reads=0")
        return 0
    if not args.provider_adapter or not args.model or not args.endpoint:
        raise ProtocolError("C1-C4 dry-run requires --provider-adapter, --model, and --endpoint")
    enforce_stage_provider(args.stage, args.provider_adapter)
    adapter = adapter_from_config(assets.config, args.provider_adapter)
    endpoint, host = adapter.validate_endpoint(args.endpoint)
    samples = planned_samples(assets, args.stage)
    request_count = expected_request_count(samples)
    first_route = route_for_index(int(samples[0]["sample_index"]))[0]
    semantic = build_semantic_request(assets, samples[0], route=first_route)
    strict_adapter = load_portable_transport_adapter()
    prepared = prepare_transport_request(
        semantic,
        provider=adapter,
        endpoint_host=host,
        model=args.model,
        strict_adapter=strict_adapter,
    )
    transport_sha256 = serialized_transport_sha256(prepared)
    print(f"{args.stage.upper()} dry-run verified; no network/API call was made.")
    print(f"provider_adapter={args.provider_adapter}")
    print(f"endpoint_host={host}")
    print(f"model={args.model}")
    print(f"request_count={request_count}")
    print(f"first_semantic_request_sha256={sha256_bytes(serialize_semantic_request(semantic))}")
    print(f"canonical_protocol_version={strict_adapter.canonical_protocol_version}")
    print(f"canonical_schema_path={strict_adapter.canonical_schema_path}")
    print(f"canonical_schema_sha256={strict_adapter.canonical_schema_sha256}")
    print(f"transport_adapter_id={strict_adapter.adapter_id}")
    print(f"transport_adapter_version={strict_adapter.adapter_version}")
    print(f"transport_schema_path={strict_adapter.transport_schema_path}")
    print(f"transport_schema_sha256={strict_adapter.transport_schema_sha256}")
    print(f"canonical_serializer_sha256={lock['serializer_sha256']}")
    print(f"capability_profile_status={prepared.capability_profile['status']}")
    print(
        "response_coordinate_mode="
        f"{prepared.capability_profile.get('response_coordinate_mode', 'reject_invalid')}"
    )
    span_guard = strict_adapter.config.get("response_span_text_guard")
    print(
        "response_span_text_guard_mode="
        f"{span_guard['mode'] if span_guard is not None else 'none'}"
    )
    print(f"structured_outputs_preflight_passed={str(strict_adapter.transport_preflight['passed']).lower()}")
    print(f"first_transport_request_sha256={transport_sha256}")
    print(
        "request_downgrade_applied="
        f"{str(bool(prepared.capability_profile.get('request_downgrade_applied', False))).lower()}"
    )
    print(f"normalized_endpoint={endpoint}")
    print("Layer D/E/Gold reads=0")
    return 0


def verify_c1_runtime_prerequisite(lock: dict[str, Any], strict_adapter: Any) -> dict[str, Any]:
    """Verify the minimum frozen C1 facts needed to prepare (not start) C2."""
    manifest = load_json_bytes(C1_RUNTIME_MANIFEST_PATH)
    expected = {
        "status": "succeeded_frozen",
        "stage": "c1",
        "provider_adapter": "relay_openai_compatible",
        "model": "gpt-5.6-luna",
        "canonical_schema_sha256": strict_adapter.canonical_schema_sha256,
        "transport_adapter_id": strict_adapter.adapter_id,
        "transport_adapter_version": strict_adapter.adapter_version,
        "transport_adapter_config_sha256": strict_adapter.config_sha256,
        "transport_schema_sha256": strict_adapter.transport_schema_sha256,
        "canonical_serializer_sha256": lock["serializer_sha256"],
        "request_count": 1,
        "candidate_count": 1,
        "evaluation_count": 0,
        "precision": None,
        "recall": None,
        "c1_passed": True,
        "c2_started": False,
    }
    drift = {
        key: {"expected": value, "actual": manifest.get(key)}
        for key, value in expected.items()
        if manifest.get(key) != value
    }
    if drift:
        raise ProtocolError(f"frozen C1 prerequisite drifted: {drift}")
    return manifest


def load_c2_offline_pass_a_fixtures(assets: Any, lock: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    """Load historical validated Pass-A outputs only as offline Pass-B preflight fixtures.

    A future real C2 run must still use its own live Pass-A output. These fixtures
    make all six envelope variants preflightable without pretending that the
    three future Pass-B byte hashes are knowable before those responses exist.
    """
    config = load_json_bytes(C2_OFFLINE_PASS_A_CONFIG_PATH)
    if sha256_path(C2_OFFLINE_PASS_A_PATH) != config.get("pass_a_file_sha256"):
        raise ProtocolError("historical Pass-A offline fixture file hash drifted")
    expected_bindings = {
        "membership_payload_sha256": lock["asset_hashes"]["membership_payload_sha256"],
        "layer_a_sha256": lock["asset_hashes"]["layer_a"],
        "layer_b_sha256": lock["asset_hashes"]["layer_b"],
        "layer_c_sha256": lock["asset_hashes"]["layer_c"],
        "schema_sha256": lock["asset_hashes"]["output_schema"],
        "pass_a_prompt_sha256": lock["asset_hashes"]["pass_a_prompt"],
        "pass_b_prompt_sha256": lock["asset_hashes"]["pass_b_prompt"],
    }
    drift = {
        key: {"expected": value, "actual": config.get(key)}
        for key, value in expected_bindings.items()
        if config.get(key) != value
    }
    if drift:
        raise ProtocolError(f"historical Pass-A offline fixture bindings drifted: {drift}")

    payload = load_json_bytes(C2_OFFLINE_PASS_A_PATH)
    records = payload.get("records")
    if not isinstance(records, list) or len(records) != 3 or any(
        not isinstance(record, dict) for record in records
    ):
        raise ProtocolError("historical Pass-A offline fixture must contain exactly three records")
    samples = assets.samples[:3]
    if [record.get("sample_id") for record in records] != [sample["sample_id"] for sample in samples]:
        raise ProtocolError("historical Pass-A offline fixture order/membership drifted")
    for sample, record in zip(samples, records, strict=True):
        validate_candidate(
            record,
            expected_sample_id=sample["sample_id"],
            frozen_candidate_text_en=sample["frozen_candidate_text_en"],
            schema=assets.schema,
        )
    return tuple(records)


def require_offline_preparation_budget(args: argparse.Namespace, request_count: int) -> None:
    """Validate a proposed fail-closed budget without treating it as API authorization."""
    if args.confirm_authorized_provider_budget:
        raise ProtocolError("offline preparation must not claim provider/budget authorization")
    if not args.run_id:
        raise ProtocolError("offline C2 preparation requires --run-id")
    if args.max_calls != request_count:
        raise ProtocolError(f"--max-calls must equal the fixed C2 request count {request_count}")
    if args.max_total_tokens is None or args.max_total_tokens <= 0:
        raise ProtocolError("offline C2 preparation requires --max-total-tokens > 0")
    if (
        args.max_cost is None
        or not args.max_cost.is_finite()
        or args.max_cost <= 0
        or not args.cost_currency
    ):
        raise ProtocolError("offline C2 preparation requires positive --max-cost and --cost-currency")
    if args.input_price_per_million is None or args.output_price_per_million is None:
        raise ProtocolError("offline C2 preparation requires proposed input/output token prices")
    if not args.input_price_per_million.is_finite() or not args.output_price_per_million.is_finite():
        raise ProtocolError("proposed token prices must be finite")
    if args.input_price_per_million < 0 or args.output_price_per_million < 0:
        raise ProtocolError("proposed token prices cannot be negative")


def prepare_c2_offline(args: argparse.Namespace, assets: Any, lock: dict[str, Any]) -> int:
    """Freeze a no-network six-request C2 preflight in a new dry-run directory."""
    if args.stage != "c2" or args.execute_api:
        raise ProtocolError("--write-offline-preparation is available only for offline C2")
    if not args.provider_adapter or not args.model or not args.endpoint:
        raise ProtocolError("offline C2 preparation requires provider adapter, model, and endpoint")
    enforce_stage_provider(args.stage, args.provider_adapter)
    adapter = adapter_from_config(assets.config, args.provider_adapter)
    normalized_endpoint, endpoint_host = adapter.validate_endpoint(args.endpoint)
    samples = planned_samples(assets, "c2")
    request_count = expected_request_count(samples)
    require_offline_preparation_budget(args, request_count)

    run_dir = safe_run_dir(assets.config, args.run_id)
    if run_dir.exists():
        raise ProtocolError("offline preparation directory already exists; never overwrite a run ID")

    frozen_c1_adapter = load_strict_transport_adapter()
    c1_manifest = verify_c1_runtime_prerequisite(lock, frozen_c1_adapter)
    strict_adapter = load_portable_transport_adapter()
    span_guard = strict_adapter.config.get("response_span_text_guard")
    span_guard_receipt = (
        {
            "mode": span_guard["mode"],
            "applied": True,
            "instruction_sha256": sha256_bytes(span_guard["instruction"].encode("utf-8")),
            "canonical_semantic_request_unchanged": span_guard[
                "canonical_semantic_request_unchanged"
            ],
            "canonical_prompt_assets_unchanged": span_guard[
                "canonical_prompt_assets_unchanged"
            ],
            "response_repair": span_guard["response_repair"],
            "content_retry": span_guard["content_retry"],
        }
        if span_guard is not None
        else {"mode": "none", "applied": False}
    )
    pass_a_fixtures = load_c2_offline_pass_a_fixtures(assets, lock)
    pass_a_by_sample = {record["sample_id"]: record for record in pass_a_fixtures}

    artifacts: list[tuple[str, bytes, bytes, dict[str, Any]]] = []
    for sample in samples:
        for route in route_for_index(int(sample["sample_index"])):
            fixture = pass_a_by_sample[sample["sample_id"]] if route == "pass_b" else None
            semantic = build_semantic_request(
                assets,
                sample,
                route=route,
                pass_a_candidate=fixture,
            )
            prepared = prepare_transport_request(
                semantic,
                provider=adapter,
                endpoint_host=endpoint_host,
                model=args.model,
                strict_adapter=strict_adapter,
            )
            semantic_bytes = serialize_semantic_request(semantic)
            transport_bytes = canonical_json_bytes(prepared.body)
            sequence = len(artifacts) + 1
            stem = f"{sequence:03d}_{sample['sample_id']}_{route}"
            dependency: dict[str, Any] | None = None
            if fixture is not None:
                dependency = {
                    "source": "historical_validated_pass_a_fixture_for_offline_preflight_only",
                    "source_path": C2_OFFLINE_PASS_A_PATH.relative_to(ROOT).as_posix(),
                    "source_file_sha256": sha256_path(C2_OFFLINE_PASS_A_PATH),
                    "record_sha256": sha256_bytes(canonical_json_bytes(fixture)),
                    "canonical_validation_passed": True,
                    "future_live_pass_a_output_required": True,
                    "future_live_transport_request_sha256_deferred": True,
                }
            record = {
                "sequence": sequence,
                "sample_index": sample["sample_index"],
                "sample_id": sample["sample_id"],
                "route": route,
                "semantic_request_sha256": sha256_bytes(semantic_bytes),
                "transport_request_sha256": sha256_bytes(transport_bytes),
                "transport_request_hash_scope": (
                    "exact_for_same_locked_inputs_model_and_profile"
                    if route == "pass_a"
                    else "offline_preflight_fixture_only_live_pass_a_dependent"
                ),
                "pass_a_dependency": dependency,
                "capability_profile_id": prepared.capability_profile["profile_id"],
                "capability_profile_version": prepared.capability_profile["profile_version"],
                "capability_profile_status": prepared.capability_profile["status"],
                "structured_outputs_preflight": strict_adapter.transport_preflight,
                "server_output_enforcement": prepared.capability_profile[
                    "server_output_enforcement"
                ],
                "response_coordinate_mode": prepared.capability_profile[
                    "response_coordinate_mode"
                ],
                "response_span_text_guard": span_guard_receipt,
                "request_downgrade_applied": prepared.capability_profile[
                    "request_downgrade_applied"
                ],
                "request_downgrade_details": prepared.capability_profile[
                    "request_downgrade_details"
                ],
            }
            artifacts.append((stem, semantic_bytes, transport_bytes, record))

    if len(artifacts) != 6 or any(
        record["structured_outputs_preflight"].get("passed") is not True
        for _, _, _, record in artifacts
    ):
        raise ProtocolError("C2 offline preparation did not produce six passing preflight requests")
    transport_sha256s = [record["transport_request_sha256"] for _, _, _, record in artifacts]
    if len(set(transport_sha256s)) != 6:
        raise ProtocolError("C2 offline transport request hashes must be six distinct values")

    max_completion_tokens = int(assets.config["generation_controls"]["max_completion_tokens"])
    max_output_tokens = request_count * max_completion_tokens
    max_input_tokens_at_max_output = max(args.max_total_tokens - max_output_tokens, 0)
    combined_guard_worst_cost = actual_cost(
        max_input_tokens_at_max_output,
        min(max_output_tokens, args.max_total_tokens),
        args,
    )
    if combined_guard_worst_cost > args.max_cost:
        raise ProtocolError("proposed cost ceiling is below the combined token/output guard envelope")

    first_prepared = prepare_transport_request(
        build_semantic_request(assets, samples[0], route="pass_a"),
        provider=adapter,
        endpoint_host=endpoint_host,
        model=args.model,
        strict_adapter=strict_adapter,
    )
    provenance = transport_provenance(
        first_prepared,
        canonical_serializer_sha256=lock["serializer_sha256"],
        transport_request_sha256=transport_sha256s[0],
        local_canonical_validation=None,
    )
    provenance["first_transport_request_sha256"] = provenance.pop("transport_request_sha256")
    created_at = now_utc()
    prereg = load_json_bytes(PREREG_TEMPLATE_PATH)
    prereg.update(
        {
            "run_id": args.run_id,
            "stage": "c2",
            "provider_adapter": args.provider_adapter,
            "provider": args.provider_adapter,
            "model": args.model,
            "endpoint_host": endpoint_host,
            "provider_identity_attestation": adapter.provider_identity_attestation,
            "created_at_utc": created_at,
            **provenance,
        }
    )
    prereg["authorization"] = {
        "provider_authorized": False,
        "maximum_calls": args.max_calls,
        "maximum_total_tokens": args.max_total_tokens,
        "maximum_cost": str(args.max_cost),
        "cost_currency": args.cost_currency,
    }
    prereg["request_plan"].update(
        {
            "sample_start_index": 0,
            "sample_end_index_exclusive": 3,
            "expected_request_count": 6,
            "offline_transport_request_sha256s": transport_sha256s,
            "pass_b_live_request_sha256s_deferred": True,
        }
    )
    prereg["stage_transition"].update({"c1_passed": True, "c2_started": False})
    prereg["safety"].update(
        {
            "layer_d_read_during_generation": False,
            "layer_e_read_during_generation": False,
            "gold_visible_during_generation": False,
            "real_api_call": False,
        }
    )
    prereg["offline_preparation"] = {
        "status": "offline_preflight_frozen_real_api_unauthorized_c2_not_started",
        "all_six_transport_preflights_passed": True,
        "offline_request_hash_count": 6,
        "pass_a_exact_request_hash_count": 3,
        "pass_b_fixture_only_request_hash_count": 3,
        "future_real_c2_requires_new_run_id": True,
        "future_real_c2_requires_new_explicit_authorization": True,
        "c1_manifest_path": C1_RUNTIME_MANIFEST_PATH.relative_to(ROOT).as_posix(),
        "c1_manifest_sha256": sha256_path(C1_RUNTIME_MANIFEST_PATH),
    }

    plan = {
        "schema_version": "estg150_candidate_c2_offline_preparation@1.0.0",
        "run_id": args.run_id,
        "status": "offline_preflight_frozen_real_api_unauthorized_c2_not_started",
        "stage": "c2",
        "provider_adapter": args.provider_adapter,
        "model": args.model,
        "endpoint_host": endpoint_host,
        "normalized_endpoint": normalized_endpoint,
        "provider_identity_attestation": adapter.provider_identity_attestation,
        "canonical_protocol_version": strict_adapter.canonical_protocol_version,
        "canonical_schema_sha256": strict_adapter.canonical_schema_sha256,
        "canonical_serializer_sha256": lock["serializer_sha256"],
        "transport_adapter_id": strict_adapter.adapter_id,
        "transport_adapter_version": strict_adapter.adapter_version,
        "transport_adapter_config_sha256": strict_adapter.config_sha256,
        "transport_schema_sha256": strict_adapter.transport_schema_sha256,
        "asset_hashes": lock["asset_hashes"],
        "request_count": 6,
        "requests": [record for _, _, _, record in artifacts],
        "request_downgrade_applied": bool(
            first_prepared.capability_profile["request_downgrade_applied"]
        ),
        "response_coordinate_mode": first_prepared.capability_profile[
            "response_coordinate_mode"
        ],
        "response_span_text_guard": span_guard_receipt,
        "budget": {
            "authorization_status": "offline_configuration_only_not_api_authorization",
            "maximum_calls": args.max_calls,
            "maximum_total_tokens": args.max_total_tokens,
            "maximum_cost": str(args.max_cost),
            "cost_currency": args.cost_currency,
            "input_price_per_million": str(args.input_price_per_million),
            "output_price_per_million": str(args.output_price_per_million),
            "max_completion_tokens_per_call": max_completion_tokens,
            "maximum_output_tokens_across_six_calls": max_output_tokens,
            "combined_token_output_guard_worst_cost": str(combined_guard_worst_cost),
            "hard_guard_checks_passed": True,
            "user_planning_estimate_total_tokens": 12000,
            "user_planning_estimate_cost": "0.26",
            "planning_estimate_is_hard_limit": False,
        },
        "safety": {
            "real_api_call": False,
            "billed_tokens": 0,
            "billed_cost": "0",
            "layer_d_read_during_generation": False,
            "layer_e_read_during_generation": False,
            "gold_visible_during_generation": False,
            "evaluation_count": 0,
            "precision": None,
            "recall": None,
            "c1_passed": c1_manifest["c1_passed"],
            "c2_started": False,
            "c3_started": False,
            "c4_started": False,
        },
        "hash_scope_note": (
            "All six hashes bind the frozen offline request bytes. The three Pass-A hashes are exact for the "
            "same locked inputs/model/profile. Each real Pass-B request must contain that run's newly validated "
            "Pass-A output, so its live transport hash is necessarily recorded only after Pass A and must not be "
            "misrepresented by the historical-fixture dry-run hash."
        ),
        "created_at_utc": created_at,
    }

    run_dir.mkdir(parents=True, exist_ok=False)
    write_json_no_overwrite(run_dir / "preregistration.json", prereg)
    for stem, semantic_bytes, transport_bytes, _ in artifacts:
        write_bytes_no_overwrite(
            run_dir / "offline_requests" / f"{stem}.semantic.json", semantic_bytes
        )
        write_bytes_no_overwrite(
            run_dir / "offline_requests" / f"{stem}.transport.json", transport_bytes
        )
    write_json_no_overwrite(run_dir / "offline_preparation.json", plan)
    print(f"C2 offline preparation frozen: {args.run_id}")
    print("real_api_called=false")
    print("billed_tokens=0")
    print("c2_started=false")
    print("request_count=6")
    print("all_six_transport_preflights_passed=true")
    print(
        "request_downgrade_applied="
        f"{str(bool(first_prepared.capability_profile['request_downgrade_applied'])).lower()}"
    )
    for _, _, _, record in artifacts:
        print(
            f"request_{record['sequence']}_sha256={record['transport_request_sha256']} "
            f"scope={record['transport_request_hash_scope']}"
        )
    return 0


def acquire_api_key(env_name: str | None) -> str:
    if env_name:
        if not env_name.replace("_", "A").isalnum() or env_name[0].isdigit():
            raise ProtocolError("--api-key-env-name is not a valid environment variable name")
        value = os.environ.get(env_name, "")
        if not value:
            raise ProtocolError(f"environment variable {env_name!r} is missing or empty")
    else:
        value = getpass.getpass("Provider API key (hidden; never stored): ")
    if not value.strip():
        raise ProtocolError("API key is empty")
    return value


def require_execution_authorization(args: argparse.Namespace, request_count: int) -> None:
    if not args.confirm_authorized_provider_budget:
        raise ProtocolError("API execution requires --confirm-authorized-provider-budget")
    if not args.run_id:
        raise ProtocolError("API execution requires --run-id")
    if args.max_calls is None or args.max_calls != request_count:
        raise ProtocolError(f"--max-calls must equal the fixed stage request count {request_count}")
    if args.max_total_tokens is None or args.max_total_tokens <= 0:
        raise ProtocolError("API execution requires --max-total-tokens > 0")
    if (
        args.max_cost is None
        or not args.max_cost.is_finite()
        or args.max_cost <= 0
        or not args.cost_currency
    ):
        raise ProtocolError("API execution requires positive --max-cost and --cost-currency")
    if args.input_price_per_million is None or args.output_price_per_million is None:
        raise ProtocolError("API execution requires confirmed input/output prices per million tokens")
    if not args.input_price_per_million.is_finite() or not args.output_price_per_million.is_finite():
        raise ProtocolError("token prices must be finite")
    if args.input_price_per_million < 0 or args.output_price_per_million < 0:
        raise ProtocolError("token prices cannot be negative")


def actual_cost(input_tokens: int, output_tokens: int, args: argparse.Namespace) -> Decimal:
    return (
        Decimal(input_tokens) * args.input_price_per_million
        + Decimal(output_tokens) * args.output_price_per_million
    ) / Decimal(1_000_000)


def build_prereg(
    args: argparse.Namespace, *, endpoint_host: str, request_count: int,
    adapter: Any, lock: dict[str, Any], prepared: Any,
    first_transport_request_sha256: str,
) -> dict[str, Any]:
    prereg = load_json_bytes(PREREG_TEMPLATE_PATH)
    provenance = transport_provenance(
        prepared,
        canonical_serializer_sha256=lock["serializer_sha256"],
        transport_request_sha256=first_transport_request_sha256,
        local_canonical_validation=None,
    )
    provenance["first_transport_request_sha256"] = provenance.pop("transport_request_sha256")
    prereg.update(
        {
            "run_id": args.run_id,
            "stage": args.stage,
            "provider_adapter": args.provider_adapter,
            "provider": args.provider_adapter,
            "model": args.model,
            "endpoint_host": endpoint_host,
            "provider_identity_attestation": adapter.provider_identity_attestation,
            "created_at_utc": now_utc(),
            **provenance,
        }
    )
    prereg["authorization"] = {
        "provider_authorized": True,
        "maximum_calls": args.max_calls,
        "maximum_total_tokens": args.max_total_tokens,
        "maximum_cost": str(args.max_cost),
        "cost_currency": args.cost_currency,
    }
    sample_range = {"c1": (3, 4), "c2": (0, 3), "c3": (0, 150), "c4": (0, 150)}[args.stage]
    prereg["request_plan"].update(
        {
            "sample_start_index": sample_range[0],
            "sample_end_index_exclusive": sample_range[1],
            "expected_request_count": request_count,
        }
    )
    prereg["stage_transition"]["c2_started"] = args.stage == "c2"
    return prereg


def execute(args: argparse.Namespace, assets: Any, lock: dict[str, Any]) -> int:
    if args.stage == "c0":
        raise ProtocolError("C0 is offline and cannot use --execute-api")
    if not args.provider_adapter or not args.model or not args.endpoint:
        raise ProtocolError("API execution requires provider adapter, model, and endpoint")
    enforce_stage_provider(args.stage, args.provider_adapter)
    adapter = adapter_from_config(assets.config, args.provider_adapter)
    endpoint, endpoint_host = adapter.validate_endpoint(args.endpoint)
    samples = planned_samples(assets, args.stage)
    request_count = expected_request_count(samples)
    strict_adapter = load_portable_transport_adapter()
    first_route = route_for_index(int(samples[0]["sample_index"]))[0]
    first_semantic = build_semantic_request(assets, samples[0], route=first_route)
    first_prepared = prepare_transport_request(
        first_semantic,
        provider=adapter,
        endpoint_host=endpoint_host,
        model=args.model,
        strict_adapter=strict_adapter,
    )
    first_transport_request_sha256 = serialized_transport_sha256(first_prepared)
    require_execution_authorization(args, request_count)
    run_dir = safe_run_dir(assets.config, args.run_id)
    if run_dir.exists():
        raise ProtocolError("run directory already exists; use a new run_id and never overwrite")

    # All preflight checks happen before the run directory or API key exists.
    prereg = build_prereg(
        args,
        endpoint_host=endpoint_host,
        request_count=request_count,
        adapter=adapter,
        lock=lock,
        prepared=first_prepared,
        first_transport_request_sha256=first_transport_request_sha256,
    )
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json_no_overwrite(run_dir / "preregistration.json", prereg)
    api_key = ""
    manifest_path = run_dir / "request_manifest.jsonl"
    totals = {"requests": 0, "retries": 0, "input_tokens": 0, "output_tokens": 0}
    usage_response_count = 0
    total_cost = Decimal("0")
    final_records: list[dict[str, Any]] = []
    transport_request_sha256s: list[str] = []
    canonical_validation_passes = 0
    coordinate_canonicalization_applied_count = 0
    active_stem: str | None = None
    active_prepared: Any = first_prepared
    active_transport_request_sha256: str | None = None
    active_local_canonical_validation: dict[str, Any] | None = None
    active_provider_metadata: dict[str, Any] | None = None
    active_credential_echo_detected = False

    try:
        api_key = acquire_api_key(args.api_key_env_name)
        for sample in samples:
            pass_a_candidate: dict[str, Any] | None = None
            for route in route_for_index(int(sample["sample_index"])):
                semantic = build_semantic_request(
                    assets, sample, route=route, pass_a_candidate=pass_a_candidate
                )
                prepared = prepare_transport_request(
                    semantic,
                    provider=adapter,
                    endpoint_host=endpoint_host,
                    model=args.model,
                    strict_adapter=strict_adapter,
                )
                body = prepared.body
                semantic_bytes = serialize_semantic_request(semantic)
                request_bytes = canonical_json_bytes(body)
                request_sha256 = sha256_bytes(request_bytes)
                conservative_token_reservation = len(request_bytes) + int(
                    assets.config["generation_controls"]["max_completion_tokens"]
                )
                if totals["requests"] >= args.max_calls:
                    raise ProtocolError("fixed call ceiling reached")
                if (
                    totals["input_tokens"]
                    + totals["output_tokens"]
                    + conservative_token_reservation
                    > args.max_total_tokens
                ):
                    raise ProtocolError("token budget reservation would exceed authorization")
                conservative_cost_reservation = actual_cost(
                    len(request_bytes),
                    int(assets.config["generation_controls"]["max_completion_tokens"]),
                    args,
                )
                if total_cost + conservative_cost_reservation > args.max_cost:
                    raise ProtocolError("cost reservation would exceed authorization")

                sequence = totals["requests"] + 1
                stem = f"{sequence:03d}_{sample['sample_id']}_{route}"
                active_stem = stem
                active_prepared = prepared
                active_transport_request_sha256 = request_sha256
                active_local_canonical_validation = None
                active_provider_metadata = None
                active_credential_echo_detected = False
                write_bytes_no_overwrite(run_dir / "requests" / f"{stem}.semantic.json", semantic_bytes)
                write_bytes_no_overwrite(run_dir / "requests" / f"{stem}.transport.json", request_bytes)
                totals["requests"] += 1
                transport_request_sha256s.append(request_sha256)
                response_bytes, retry_reasons = post_identical_request_with_retries(
                    endpoint=endpoint,
                    api_key=api_key,
                    request_bytes=request_bytes,
                    timeout_seconds=args.timeout_seconds,
                    max_network_retries=assets.config["response_contract"]["max_network_retries"],
                    retryable_statuses=set(assets.config["response_contract"]["network_retry_statuses"]),
                )
                totals["retries"] += len(retry_reasons)
                if api_key.encode("utf-8") in response_bytes:
                    active_credential_echo_detected = True
                    raise ProtocolError("provider response echoed the API credential; raw response archive refused")
                write_bytes_no_overwrite(run_dir / "responses" / f"{stem}.json", response_bytes)
                _response, _content, active_provider_metadata = extract_provider_response_envelope(
                    response_bytes, adapter=adapter
                )
                cost = actual_cost(
                    active_provider_metadata["input_tokens"],
                    active_provider_metadata["output_tokens"],
                    args,
                )
                totals["input_tokens"] += active_provider_metadata["input_tokens"]
                totals["output_tokens"] += active_provider_metadata["output_tokens"]
                usage_response_count += 1
                total_cost += cost
                if totals["input_tokens"] + totals["output_tokens"] > args.max_total_tokens:
                    raise ProtocolError("provider-reported usage exceeds authorized token ceiling")
                if total_cost > args.max_cost:
                    raise ProtocolError("provider-reported usage exceeds authorized cost ceiling")
                candidate, metadata = extract_provider_response(
                    response_bytes,
                    adapter=adapter,
                    expected_sample_id=sample["sample_id"],
                    frozen_candidate_text_en=reviewed_candidate_text_en(
                        sample, route, pass_a_candidate
                    ),
                    schema=assets.schema,
                    response_coordinate_mode=prepared.capability_profile.get(
                        "response_coordinate_mode", "reject_invalid"
                    ),
                )
                coordinate_receipt = metadata["response_coordinate_canonicalization"]
                active_local_canonical_validation = {
                    "performed": True,
                    "passed": True,
                    "schema_path": strict_adapter.canonical_schema_path,
                    "schema_sha256": strict_adapter.canonical_schema_sha256,
                    "checks": metadata["validation"],
                    "response_coordinate_canonicalization": coordinate_receipt,
                }
                canonical_validation_passes += 1
                if coordinate_receipt["applied"]:
                    coordinate_canonicalization_applied_count += 1
                append_jsonl(
                    manifest_path,
                    {
                        "sequence": sequence,
                        "sample_index": sample["sample_index"],
                        "sample_id": sample["sample_id"],
                        "route": route,
                        "semantic_request_sha256": sha256_bytes(semantic_bytes),
                        "retry_count": len(retry_reasons),
                        "retry_reasons": retry_reasons,
                        "cost": str(cost),
                        "cost_currency": args.cost_currency,
                        **transport_provenance(
                            prepared,
                            canonical_serializer_sha256=lock["serializer_sha256"],
                            transport_request_sha256=request_sha256,
                            local_canonical_validation=active_local_canonical_validation,
                        ),
                        **metadata,
                    },
                )
                if route == "pass_a":
                    pass_a_candidate = candidate
                else:
                    final_records.append(candidate)

        expected_final = 1 if args.stage == "c1" else len(samples)
        if totals["requests"] != request_count or len(final_records) != expected_final:
            raise ProtocolError("run did not complete the fixed request/final-record membership")
        write_json_no_overwrite(
            run_dir / "candidates.json",
            {
                "schema_version": "estg150_candidate_run_output@1.0.0",
                "run_id": args.run_id,
                "records": final_records,
            },
        )
        completed = now_utc()
        summary_validation = {
            "performed_count": canonical_validation_passes,
            "passed_count": canonical_validation_passes,
            "all_passed": canonical_validation_passes == request_count,
            "schema_path": strict_adapter.canonical_schema_path,
            "schema_sha256": strict_adapter.canonical_schema_sha256,
            "coordinate_canonicalization_applied_count": (
                coordinate_canonicalization_applied_count
            ),
        }
        summary_provenance = transport_provenance(
            first_prepared,
            canonical_serializer_sha256=lock["serializer_sha256"],
            transport_request_sha256=(
                transport_request_sha256s[0] if len(transport_request_sha256s) == 1 else None
            ),
            local_canonical_validation=summary_validation,
        )
        summary = {
            "schema_version": "estg150_candidate_run_manifest@1.1.0",
            "run_id": args.run_id,
            "status": "succeeded_frozen",
            "stage": args.stage,
            "provider_adapter": args.provider_adapter,
            "model": args.model,
            "endpoint_host": endpoint_host,
            "serializer_sha256": lock["serializer_sha256"],
            "asset_hashes": lock["asset_hashes"],
            **summary_provenance,
            "transport_request_sha256s": transport_request_sha256s,
            "request_count": totals["requests"],
            "retry_count": totals["retries"],
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "total_cost": str(total_cost),
            "cost_currency": args.cost_currency,
            "real_api_call": True,
            "layer_d_read_during_generation": False,
            "layer_e_read_during_generation": False,
            "gold_visible_during_generation": False,
            "generation_completed_at_utc": completed,
            "evaluation_started_at_utc": None,
            "candidate_count": len(final_records),
            "evaluation_count": 0,
            "precision": None,
            "recall": None,
            "c1_passed": args.stage == "c1",
            "c2_started": args.stage == "c2",
            "automatic_c2_forbidden": True,
        }
        write_json_no_overwrite(run_dir / "manifest.json", summary)
        print(f"frozen run complete: {args.run_id}; requests={totals['requests']}; candidates={len(final_records)}")
        return 0
    except Exception as exc:
        provider_diagnostic: dict[str, Any] = {}
        if isinstance(exc, ProviderHTTPError):
            totals["retries"] += len(exc.retry_reasons)
            if active_stem is not None:
                provider_diagnostic = archive_provider_http_error(
                    run_dir, active_stem, exc, api_key=api_key
                )
        elif isinstance(exc, RetryableTransportError):
            totals["retries"] += len(exc.retry_reasons)
            provider_diagnostic = {
                "retry_reasons": list(exc.retry_reasons),
                "terminal_network_error_type": exc.terminal_network_error_type,
            }
        if active_local_canonical_validation is not None:
            local_canonical_validation = active_local_canonical_validation
        elif isinstance(exc, CandidateValidationError):
            local_canonical_validation: dict[str, Any] | None = {
                "performed": True,
                "passed": False,
                "schema_path": strict_adapter.canonical_schema_path,
                "schema_sha256": strict_adapter.canonical_schema_sha256,
                "error_type": type(exc).__name__,
                "error": str(exc)[:1200],
            }
        elif active_transport_request_sha256 is not None:
            local_canonical_validation = {
                "performed": False,
                "passed": None,
                "schema_path": strict_adapter.canonical_schema_path,
                "schema_sha256": strict_adapter.canonical_schema_sha256,
            }
        else:
            local_canonical_validation = None
        failure_provenance = transport_provenance(
            active_prepared,
            canonical_serializer_sha256=lock["serializer_sha256"],
            transport_request_sha256=active_transport_request_sha256,
            local_canonical_validation=local_canonical_validation,
        )
        failure_error = str(exc)
        if api_key:
            failure_error = failure_error.replace(api_key, "***")
        provider_response_receipt = {}
        if active_provider_metadata is not None:
            provider_response_receipt = {
                key: active_provider_metadata[key]
                for key in (
                    "provider_reported_model",
                    "provider_response_id",
                    "provider_identity_attestation",
                    "finish_reason",
                    "response_sha256",
                )
            }
        failure = {
            "schema_version": "estg150_candidate_run_failure@1.1.0",
            "run_id": args.run_id,
            "stage": args.stage,
            "provider_adapter": args.provider_adapter,
            "model": args.model,
            "endpoint_host": endpoint_host,
            "status": "protocol_incompatible" if isinstance(exc, ProtocolIncompatible) else "failed_closed",
            "error_type": type(exc).__name__,
            "error": failure_error[:1200],
            **provider_response_receipt,
            **failure_provenance,
            "transport_request_sha256s": transport_request_sha256s,
            "request_count": totals["requests"],
            "retry_count": totals["retries"],
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "provider_reported_tokens_available": usage_response_count > 0,
            "total_cost": str(total_cost),
            "cost_currency": args.cost_currency,
            "valid_candidate_count": len(final_records),
            "evaluation_count": 0,
            "precision": None,
            "recall": None,
            "c1_passed": False,
            "c2_started": args.stage == "c2",
            "automatic_c2_forbidden": True,
            "real_api_call": totals["requests"] > 0,
            "credential_echo_detected": active_credential_echo_detected,
            "layer_d_read_during_generation": False,
            "layer_e_read_during_generation": False,
            "gold_visible_during_generation": False,
            "failed_at_utc": now_utc(),
            **provider_diagnostic,
        }
        write_json_no_overwrite(run_dir / "failure.json", failure)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("c0", "c1", "c2", "c3", "c4"), default="c0")
    parser.add_argument("--write-c0-lock", action="store_true")
    parser.add_argument("--write-offline-preparation", action="store_true")
    parser.add_argument("--execute-api", action="store_true")
    parser.add_argument("--confirm-authorized-provider-budget", action="store_true")
    parser.add_argument("--provider-adapter")
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--run-id")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-total-tokens", type=int)
    parser.add_argument("--max-cost", type=Decimal)
    parser.add_argument("--cost-currency")
    parser.add_argument("--input-price-per-million", type=Decimal)
    parser.add_argument("--output-price-per-million", type=Decimal)
    parser.add_argument("--api-key-env-name")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write_c0_lock:
        if args.stage != "c0" or args.execute_api or args.write_offline_preparation:
            raise ProtocolError("--write-c0-lock is available only for offline C0")
        lock = c0_write_or_verify()
        print(f"C0 lock verified: serializer_sha256={lock['serializer_sha256']}")
        return 0
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    if args.write_offline_preparation:
        return prepare_c2_offline(args, assets, lock)
    if args.execute_api:
        return execute(args, assets, lock)
    return dry_run(args, assets, lock)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ProtocolError, ValueError) as exc:
        raise SystemExit(f"candidate protocol stopped safely: {exc}") from exc

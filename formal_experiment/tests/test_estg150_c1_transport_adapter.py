"""Offline gates for the versioned C1 strict transport adapter."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from formal_experiment.estg150_candidate_protocol import (  # noqa: E402
    CandidateValidationError,
    adapter_from_config,
    build_semantic_request,
    canonical_json_bytes,
    load_json_bytes,
    load_protocol_assets,
    serialize_semantic_request,
    sha256_path,
    validate_candidate,
    verify_c0_lock,
)
import formal_experiment.estg150_candidate_protocol as candidate_protocol  # noqa: E402
from formal_experiment.estg150_c1_transport import (  # noqa: E402
    CapabilityPreflightError,
    EXPECTED_CANONICAL_SCHEMA_SHA256,
    EXPECTED_STRING_TYPE_PATCHES,
    StructuredOutputsPreflightError,
    derive_strict_transport_schema,
    load_strict_transport_adapter,
    preflight_openai_structured_outputs_schema,
    prepare_transport_request,
    serialized_transport_sha256,
)


RUNNER = ROOT / "scripts" / "run_estg150_candidate_protocol.py"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "estg150_candidate_protocol"
VALID_CANDIDATE = FIXTURE_ROOT / "strict_transport_valid_candidate_v1.json"
INVALID_CANDIDATE = FIXTURE_ROOT / "strict_transport_invalid_candidate_v1.json"
MATRIX_MANIFEST = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "c1_transport_compatibility_matrix_20260725_v1"
    / "manifest.json"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("estg150_candidate_runner_transport_test", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


def _prepared(model: str = "gpt-5.6-luna"):
    assets = load_protocol_assets()
    provider = adapter_from_config(assets.config, "relay_openai_compatible")
    synthetic = load_json_bytes(FIXTURE_ROOT / "synthetic_record_v1.json")
    semantic = build_semantic_request(assets, synthetic, route="full_extract")
    prepared = prepare_transport_request(
        semantic,
        provider=provider,
        endpoint_host="api.chatanywhere.tech",
        model=model,
        strict_adapter=load_strict_transport_adapter(),
    )
    return assets, semantic, prepared


def _structural_diff(left, right, path: str = "$") -> list[tuple[str, str, object]]:
    differences: list[tuple[str, str, object]] = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in left:
            child_path = f"{path}.{key}"
            if key not in right:
                differences.append((child_path, "removed", left[key]))
            else:
                differences.extend(_structural_diff(left[key], right[key], child_path))
        for key in right:
            if key not in left:
                differences.append((f"{path}.{key}", "added", right[key]))
        return differences
    if isinstance(left, list) and isinstance(right, list):
        if left != right:
            differences.append((path, "changed", right))
        return differences
    if left != right:
        differences.append((path, "changed", right))
    return differences


def _assert_strict_objects(node: dict) -> None:
    types = node.get("type")
    allowed = {types} if isinstance(types, str) else set(types or [])
    if "object" in allowed or any(key in node for key in ("properties", "required", "additionalProperties")):
        assert node["type"] == "object"
        assert node["additionalProperties"] is False
        assert set(node["required"]) == set(node["properties"])
    for child in node.get("properties", {}).values():
        _assert_strict_objects(child)
    for child in node.get("$defs", {}).values():
        _assert_strict_objects(child)
    if isinstance(node.get("items"), dict):
        _assert_strict_objects(node["items"])
    for child in node.get("anyOf", []):
        _assert_strict_objects(child)


def test_canonical_v1_schema_and_serializer_hashes_remain_frozen() -> None:
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    canonical_path = ROOT / assets.config["assets"]["output_schema"]["path"]
    assert sha256_path(canonical_path) == EXPECTED_CANONICAL_SCHEMA_SHA256
    assert lock["asset_hashes"]["output_schema"] == EXPECTED_CANONICAL_SCHEMA_SHA256
    assert lock["serializer_sha256"] == "d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef"
    assert lock["serializer_fixture_sha256"] == "eb074081cc52d22025e263e3f94b2165f95493f511ddc454b9ea5f5923c085e1"


def test_transport_schema_is_exactly_the_six_allowed_type_additions() -> None:
    strict_adapter = load_strict_transport_adapter()
    assert derive_strict_transport_schema(strict_adapter.canonical_schema) == strict_adapter.transport_schema
    differences = _structural_diff(strict_adapter.canonical_schema, strict_adapter.transport_schema)
    expected_paths = {
        "$.properties.schema_version.type",
        "$.properties.context_sufficiency.type",
        "$.properties.translation.properties.decision.type",
        "$.$defs.modality.properties.label.type",
        "$.properties.confidence.type",
        "$.$defs.ambiguity.properties.field.type",
    }
    assert differences == [(path, "added", "string") for path in [
        "$.properties.schema_version.type",
        "$.properties.context_sufficiency.type",
        "$.properties.translation.properties.decision.type",
        "$.properties.confidence.type",
        "$.$defs.modality.properties.label.type",
        "$.$defs.ambiguity.properties.field.type",
    ]]
    assert {path for path, operation, value in differences} == expected_paths
    assert all(operation == "added" and value == "string" for _, operation, value in differences)
    assert strict_adapter.transport_schema["properties"]["schema_version"]["const"] == (
        "estg150_ai_review_model_output@1.0.0"
    )
    assert tuple(strict_adapter.config["transformation"]["allowed_json_pointers"]) == EXPECTED_STRING_TYPE_PATCHES


def test_canonical_and_transport_schema_are_validation_equivalent_on_fixtures() -> None:
    strict_adapter = load_strict_transport_adapter()
    valid = load_json_bytes(VALID_CANDIDATE)
    invalid = load_json_bytes(INVALID_CANDIDATE)
    text = valid["translation"]["proposed_text_en"]
    assert len(text) == 58
    for schema in (strict_adapter.canonical_schema, strict_adapter.transport_schema):
        assert validate_candidate(
            valid,
            expected_sample_id="synthetic_c1_utf8",
            frozen_candidate_text_en=text,
            schema=schema,
        )["schema_valid"] is True
        with pytest.raises(CandidateValidationError):
            validate_candidate(
                invalid,
                expected_sample_id="synthetic_c1_utf8",
                frozen_candidate_text_en=text,
                schema=schema,
            )


def test_preflight_reports_original_first_missing_type_and_adapter_passes() -> None:
    strict_adapter = load_strict_transport_adapter()
    with pytest.raises(StructuredOutputsPreflightError) as raised:
        preflight_openai_structured_outputs_schema(strict_adapter.canonical_schema)
    assert raised.value.path == "$.properties.schema_version"
    assert raised.value.code == "const_or_enum_missing_explicit_type"
    assert strict_adapter.canonical_preflight_error["path"] == "$.properties.schema_version"
    assert strict_adapter.transport_preflight["passed"] is True
    assert strict_adapter.transport_preflight["object_nodes"] == 9
    _assert_strict_objects(strict_adapter.transport_schema)


def test_ref_and_nested_anyof_do_not_require_a_parent_type() -> None:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["item", "nullable"],
        "properties": {
            "item": {"$ref": "#/$defs/item"},
            "nullable": {"anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]},
        },
        "$defs": {
            "item": {
                "type": "object",
                "additionalProperties": False,
                "required": ["value"],
                "properties": {"value": {"type": "integer", "minimum": 0}},
            }
        },
    }
    result = preflight_openai_structured_outputs_schema(schema)
    assert result["passed"] is True
    assert result["ref_nodes"] == 1
    assert result["any_of_nodes"] == 1
    with pytest.raises(StructuredOutputsPreflightError) as raised:
        preflight_openai_structured_outputs_schema({"anyOf": [schema]})
    assert raised.value.path == "$.anyOf"


def test_preflight_recurses_through_refs_and_rejects_untyped_anyof_branches() -> None:
    hidden_invalid_object = {
        "type": "object",
        "additionalProperties": False,
        "required": ["item"],
        "properties": {"item": {"$ref": "#/$defs/item"}},
        "$defs": {
            "item": {
                "type": "object",
                "additionalProperties": True,
                "required": ["value"],
                "properties": {"value": {"type": "string"}},
            }
        },
    }
    with pytest.raises(StructuredOutputsPreflightError) as raised:
        preflight_openai_structured_outputs_schema(hidden_invalid_object)
    assert raised.value.code == "additional_properties_not_false"
    assert raised.value.path.endswith(".additionalProperties")

    untyped_branch = {
        "type": "object",
        "additionalProperties": False,
        "required": ["value"],
        "properties": {"value": {"anyOf": [{}]}},
    }
    with pytest.raises(StructuredOutputsPreflightError) as raised:
        preflight_openai_structured_outputs_schema(untyped_branch)
    assert raised.value.path == "$.properties.value.anyOf[0]"
    assert raised.value.code == "schema_node_missing_explicit_type"

    recursive_local_ref = {
        "type": "object",
        "additionalProperties": False,
        "required": ["child"],
        "properties": {"child": {"$ref": "#"}},
    }
    assert preflight_openai_structured_outputs_schema(recursive_local_ref)["passed"] is True


@pytest.mark.parametrize(
    ("model", "status"),
    [
        ("gpt-5.6-luna", "offline_ready"),
        ("gpt-5.4-nano", "offline_ready"),
        ("gpt-5-nano", "offline_request_ready_runtime_503_unresolved"),
    ],
)
def test_modern_chatanywhere_models_use_the_explicit_transport_adapter(model: str, status: str) -> None:
    assets, semantic, prepared = _prepared(model)
    body = prepared.body
    assert prepared.capability_profile["status"] == status
    assert body["messages"] == semantic["messages"]
    assert body["reasoning_effort"] == "high"
    assert body["max_completion_tokens"] == 6500
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["response_format"]["json_schema"]["schema"] == prepared.strict_adapter.transport_schema
    assert body["response_format"]["json_schema"]["schema"] != assets.schema
    assert "temperature" not in body
    assert set(body) == {
        "model",
        "messages",
        "reasoning_effort",
        "max_completion_tokens",
        "response_format",
    }


@pytest.mark.parametrize("tamper", ["model", "tools"])
def test_transport_preparation_rejects_model_or_tool_envelope_drift(tamper: str) -> None:
    assets = load_protocol_assets()
    base_provider = adapter_from_config(assets.config, "relay_openai_compatible")
    synthetic = load_json_bytes(FIXTURE_ROOT / "synthetic_record_v1.json")
    semantic = build_semantic_request(assets, synthetic, route="full_extract")

    class TamperedProvider:
        adapter_id = "relay_openai_compatible"

        def build_transport_body(self, semantic_request, *, model):
            body = base_provider.build_transport_body(semantic_request, model=model)
            if tamper == "model":
                body["model"] = "different-model"
            else:
                body["tools"] = [{"type": "function", "function": {"name": "forbidden"}}]
            return body

    with pytest.raises(candidate_protocol.ProtocolError):
        prepare_transport_request(
            semantic,
            provider=TamperedProvider(),
            endpoint_host="api.chatanywhere.tech",
            model="gpt-5.6-luna",
            strict_adapter=load_strict_transport_adapter(),
        )


def test_capability_profile_allowlist_is_exactly_the_seven_observed_models() -> None:
    strict_adapter = load_strict_transport_adapter()
    assert len(strict_adapter.config["capability_profiles"]) == 7
    strict_adapter.config["capability_profiles"].append(
        {
            "profile_id": "unapproved",
            "profile_version": "1.0.0",
            "provider_adapter": "relay_openai_compatible",
            "endpoint_hosts": ["api.chatanywhere.tech"],
            "model": "unapproved-model",
            "status": "offline_ready",
            "transport_schema_adapter_identity": strict_adapter.adapter_identity,
            "request_downgrade_allowed": False,
        }
    )
    assets = load_protocol_assets()
    semantic = build_semantic_request(
        assets, load_json_bytes(FIXTURE_ROOT / "synthetic_record_v1.json"), route="full_extract"
    )
    with pytest.raises(candidate_protocol.ProtocolError, match="exactly the seven"):
        prepare_transport_request(
            semantic,
            provider=adapter_from_config(assets.config, "relay_openai_compatible"),
            endpoint_host="api.chatanywhere.tech",
            model="unapproved-model",
            strict_adapter=strict_adapter,
        )


@pytest.mark.parametrize(
    ("provider_id", "host", "model", "path", "status", "reason"),
    [
        (
            "relay_openai_compatible",
            "api.chatanywhere.tech",
            "gpt-4.1-nano",
            "$.reasoning_effort",
            "blocked_requires_separately_approved_versioned_provider_profile",
            "reasoning_effort_unsupported",
        ),
        (
            "relay_openai_compatible",
            "api.chatanywhere.tech",
            "gpt-4o",
            "$.reasoning_effort",
            "blocked_pending_separately_approved_versioned_provider_profile",
            "field_removal_requires_separate_explicit_approval",
        ),
        (
            "relay_openai_compatible",
            "api.chatanywhere.tech",
            "gpt-3.5-turbo",
            "$.reasoning_effort",
            "canonical_protocol_incompatible",
            "strict_json_schema_not_supported_without_forbidden_json_object_downgrade",
        ),
        (
            "deepseek_official",
            "api.deepseek.com",
            "deepseek-v4-pro",
            "$.messages[1].role",
            "canonical_protocol_incompatible",
            "developer_role_unsupported",
        ),
    ],
)
def test_incompatible_models_fail_capability_preflight_without_downgrade(
    provider_id: str, host: str, model: str, path: str, status: str, reason: str
) -> None:
    assets = load_protocol_assets()
    provider = adapter_from_config(assets.config, provider_id)
    synthetic = load_json_bytes(FIXTURE_ROOT / "synthetic_record_v1.json")
    semantic = build_semantic_request(assets, synthetic, route="full_extract")
    strict_adapter = load_strict_transport_adapter()
    with pytest.raises(CapabilityPreflightError) as raised:
        prepare_transport_request(
            semantic,
            provider=provider,
            endpoint_host=host,
            model=model,
            strict_adapter=strict_adapter,
        )
    assert raised.value.path == path
    assert raised.value.profile_status == status
    assert reason in raised.value.reason_codes
    assert set(strict_adapter.config["downgrade_policy"].values()) == {
        "forbidden_without_separate_explicitly_approved_versioned_provider_profile",
        "forbidden",
    }


def test_c1_dry_run_reads_no_key_sends_no_network_and_creates_no_run(monkeypatch, capsys) -> None:
    runner = _load_runner()
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    monkeypatch.setenv("CHATANYWHERE_API_KEY", "must-not-be-read")
    monkeypatch.setattr(
        runner,
        "acquire_api_key",
        lambda env_name: (_ for _ in ()).throw(AssertionError("dry-run read API key")),
    )
    monkeypatch.setattr(
        runner,
        "post_identical_request_with_retries",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("dry-run sent network request")),
    )
    before = set((ROOT / assets.config["output"]["root"]).iterdir())
    args = argparse.Namespace(
        stage="c1",
        provider_adapter="relay_openai_compatible",
        model="gpt-5.6-luna",
        endpoint="https://api.chatanywhere.tech/v1/chat/completions",
    )
    assert runner.dry_run(args, assets, lock) == 0
    output = capsys.readouterr().out
    assert "no network/API call was made" in output
    assert "structured_outputs_preflight_passed=true" in output
    assert "request_downgrade_applied=false" in output
    assert set((ROOT / assets.config["output"]["root"]).iterdir()) == before


def test_execution_authorization_rejects_non_finite_costs_and_prices() -> None:
    runner = _load_runner()
    args = argparse.Namespace(
        confirm_authorized_provider_budget=True,
        run_id="finite_budget_test",
        max_calls=1,
        max_total_tokens=13000,
        max_cost=Decimal("Infinity"),
        cost_currency="TEST",
        input_price_per_million=Decimal("0"),
        output_price_per_million=Decimal("0"),
    )
    with pytest.raises(candidate_protocol.ProtocolError, match="positive --max-cost"):
        runner.require_execution_authorization(args, 1)
    args.max_cost = Decimal("1")
    args.input_price_per_million = Decimal("Infinity")
    with pytest.raises(candidate_protocol.ProtocolError, match="prices must be finite"):
        runner.require_execution_authorization(args, 1)


def test_missing_key_writes_fail_closed_receipt_without_network(monkeypatch) -> None:
    runner = _load_runner()
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    with tempfile.TemporaryDirectory(prefix="estg150_c1_missing_key_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        monkeypatch.setattr(
            runner,
            "acquire_api_key",
            lambda env_name: (_ for _ in ()).throw(candidate_protocol.ProtocolError("missing key")),
        )
        monkeypatch.setattr(
            runner,
            "post_identical_request_with_retries",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("network must not run")),
        )
        args = argparse.Namespace(
            stage="c1",
            provider_adapter="relay_openai_compatible",
            model="gpt-5.6-luna",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=True,
            run_id="offline_missing_key",
            max_calls=1,
            max_total_tokens=100_000,
            max_cost=Decimal("100"),
            cost_currency="TEST",
            input_price_per_million=Decimal("0"),
            output_price_per_million=Decimal("0"),
            api_key_env_name="UNSET_OFFLINE_TEST_KEY",
            timeout_seconds=17,
        )
        with pytest.raises(candidate_protocol.ProtocolError, match="missing key"):
            runner.execute(args, test_assets, lock)
        run_dir = temporary_root / args.run_id
        prereg = load_json_bytes(run_dir / "preregistration.json")
        failure = load_json_bytes(run_dir / "failure.json")
        assert prereg["safety"]["real_api_call"] is False
        assert failure["real_api_call"] is False
        assert failure["request_count"] == 0
        assert failure["transport_request_sha256"] is None
        assert failure["local_canonical_validation"] is None


def test_success_response_credential_echo_is_not_archived(monkeypatch) -> None:
    runner = _load_runner()
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    with tempfile.TemporaryDirectory(prefix="estg150_c1_key_echo_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        monkeypatch.setattr(runner, "acquire_api_key", lambda env_name: "offline-mock-key")
        monkeypatch.setattr(
            runner,
            "post_identical_request_with_retries",
            lambda **kwargs: (b'{"debug":"offline-mock-key"}', []),
        )
        args = argparse.Namespace(
            stage="c1",
            provider_adapter="relay_openai_compatible",
            model="gpt-5.6-luna",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=True,
            run_id="offline_key_echo",
            max_calls=1,
            max_total_tokens=100_000,
            max_cost=Decimal("100"),
            cost_currency="TEST",
            input_price_per_million=Decimal("0"),
            output_price_per_million=Decimal("0"),
            api_key_env_name=None,
            timeout_seconds=17,
        )
        with pytest.raises(candidate_protocol.ProtocolError, match="credential"):
            runner.execute(args, test_assets, lock)
        run_dir = temporary_root / args.run_id
        failure = load_json_bytes(run_dir / "failure.json")
        assert failure["credential_echo_detected"] is True
        assert not tuple((run_dir / "responses").glob("*.json"))


def test_preregistration_records_both_contracts_null_metrics_and_no_c2() -> None:
    runner = _load_runner()
    assets, _semantic, prepared = _prepared()
    lock = verify_c0_lock(assets)
    request_sha256 = serialized_transport_sha256(prepared)
    args = argparse.Namespace(
        run_id="synthetic_c1_prereg",
        stage="c1",
        provider_adapter="relay_openai_compatible",
        model="gpt-5.6-luna",
        max_calls=1,
        max_total_tokens=13000,
        max_cost=Decimal("1"),
        cost_currency="TEST",
    )
    prereg = runner.build_prereg(
        args,
        endpoint_host="api.chatanywhere.tech",
        request_count=1,
        adapter=adapter_from_config(assets.config, "relay_openai_compatible"),
        lock=lock,
        prepared=prepared,
        first_transport_request_sha256=request_sha256,
    )
    assert prereg["canonical_protocol_version"] == assets.config["protocol_version"]
    assert prereg["canonical_schema_sha256"] == EXPECTED_CANONICAL_SCHEMA_SHA256
    assert prereg["transport_adapter_id"] == "estg150_openai_strict_transport_schema_adapter"
    assert prereg["transport_adapter_version"] == "1.1.0"
    assert prereg["transport_schema_sha256"] == prepared.strict_adapter.transport_schema_sha256
    assert prereg["canonical_serializer_sha256"] == lock["serializer_sha256"]
    assert prereg["first_transport_request_sha256"] == request_sha256
    assert prereg["local_canonical_validation"] is None
    assert prereg["request_downgrade_applied"] is False
    assert prereg["evaluation"] == {
        "valid_candidate_count": 0,
        "evaluation_count": 0,
        "precision": None,
        "recall": None,
    }
    assert prereg["stage_transition"] == {
        "c1_passed": False,
        "c2_started": False,
        "automatic_c2_forbidden": True,
    }
    matrix = load_json_bytes(MATRIX_MANIFEST)
    assert matrix["totals"]["precision"] is None
    assert matrix["totals"]["recall"] is None
    assert matrix["conclusions"]["c1_passed"] is False
    assert matrix["conclusions"]["c2_started"] is False


def test_mocked_success_receipts_record_actual_transport_and_canonical_validation(
    monkeypatch,
) -> None:
    runner = _load_runner()
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    candidate = load_json_bytes(VALID_CANDIDATE)
    response = canonical_json_bytes(
        {
            "id": "offline-mock-response",
            "model": "offline-mock-provider-report",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(candidate, ensure_ascii=False)},
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
    )
    with tempfile.TemporaryDirectory(prefix="estg150_c1_success_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        monkeypatch.setattr(runner, "acquire_api_key", lambda env_name: "offline-mock-key")
        monkeypatch.setattr(
            runner,
            "post_identical_request_with_retries",
            lambda **kwargs: (response, []),
        )
        args = argparse.Namespace(
            stage="c1",
            provider_adapter="relay_openai_compatible",
            model="gpt-5.6-luna",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=True,
            run_id="offline_mock_success",
            max_calls=1,
            max_total_tokens=100_000,
            max_cost=Decimal("100"),
            cost_currency="TEST",
            input_price_per_million=Decimal("0"),
            output_price_per_million=Decimal("0"),
            api_key_env_name=None,
            timeout_seconds=17,
        )
        assert runner.execute(args, test_assets, lock) == 0
        run_dir = temporary_root / args.run_id
        manifest = load_json_bytes(run_dir / "manifest.json")
        receipt = json.loads((run_dir / "request_manifest.jsonl").read_text(encoding="utf-8"))
        assert manifest["schema_version"] == "estg150_candidate_run_manifest@1.1.0"
        assert manifest["canonical_schema_sha256"] == EXPECTED_CANONICAL_SCHEMA_SHA256
        assert manifest["transport_request_sha256"] == manifest["transport_request_sha256s"][0]
        assert manifest["local_canonical_validation"]["all_passed"] is True
        assert manifest["local_canonical_validation"]["passed_count"] == 1
        assert manifest["request_downgrade_applied"] is False
        assert manifest["evaluation_count"] == 0
        assert manifest["precision"] is None and manifest["recall"] is None
        assert manifest["c2_started"] is False
        assert receipt["transport_request_sha256"] == manifest["transport_request_sha256"]
        assert receipt["local_canonical_validation"]["passed"] is True
        assert receipt["local_canonical_validation"]["schema_sha256"] == (
            EXPECTED_CANONICAL_SCHEMA_SHA256
        )
        assert receipt["request_downgrade_applied"] is False


def test_mocked_invalid_candidate_still_records_provider_usage_and_cost(monkeypatch) -> None:
    runner = _load_runner()
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    candidate = json.loads(json.dumps(load_json_bytes(VALID_CANDIDATE)))
    candidate["clauses"][0]["clause_span"]["end"] = (
        len(candidate["translation"]["proposed_text_en"]) + 1
    )
    response = canonical_json_bytes(
        {
            "id": "offline-invalid-response",
            "model": "offline-invalid-provider-report",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(candidate, ensure_ascii=False)},
                }
            ],
            "usage": {"prompt_tokens": 1167, "completion_tokens": 1789},
        }
    )
    with tempfile.TemporaryDirectory(prefix="estg150_c1_invalid_usage_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        monkeypatch.setattr(runner, "acquire_api_key", lambda env_name: "offline-mock-key")
        monkeypatch.setattr(
            runner,
            "post_identical_request_with_retries",
            lambda **kwargs: (response, []),
        )
        args = argparse.Namespace(
            stage="c1",
            provider_adapter="relay_openai_compatible",
            model="gpt-5.4-nano",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=True,
            run_id="offline_mock_invalid_usage",
            max_calls=1,
            max_total_tokens=100_000,
            max_cost=Decimal("100"),
            cost_currency="CA",
            input_price_per_million=Decimal("1.4"),
            output_price_per_million=Decimal("8.75"),
            api_key_env_name=None,
            timeout_seconds=17,
        )
        with pytest.raises(CandidateValidationError, match="outside proposed_text_en"):
            runner.execute(args, test_assets, lock)
        run_dir = temporary_root / args.run_id
        failure = load_json_bytes(run_dir / "failure.json")
        assert failure["input_tokens"] == 1167
        assert failure["output_tokens"] == 1789
        assert failure["provider_reported_tokens_available"] is True
        assert failure["total_cost"] == "0.01728755"
        assert failure["provider_reported_model"] == "offline-invalid-provider-report"
        assert failure["provider_response_id"] == "offline-invalid-response"
        assert failure["response_sha256"] == sha256_path(
            run_dir / "responses" / "001_synthetic_c1_utf8_full_extract.json"
        )
        assert failure["local_canonical_validation"]["passed"] is False
        assert failure["valid_candidate_count"] == 0
        assert failure["c1_passed"] is False and failure["c2_started"] is False
        assert not (run_dir / "manifest.json").exists()
        assert not (run_dir / "candidates.json").exists()


def test_mocked_length_completion_still_records_provider_usage_and_cost(monkeypatch) -> None:
    runner = _load_runner()
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    response = canonical_json_bytes(
        {
            "id": "offline-length-response",
            "model": "offline-length-provider-report",
            "choices": [{"finish_reason": "length", "message": {"content": ""}}],
            "usage": {"prompt_tokens": 1339, "completion_tokens": 6500},
        }
    )
    with tempfile.TemporaryDirectory(prefix="estg150_c1_length_usage_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        monkeypatch.setattr(runner, "acquire_api_key", lambda env_name: "offline-mock-key")
        monkeypatch.setattr(
            runner,
            "post_identical_request_with_retries",
            lambda **kwargs: (response, []),
        )
        args = argparse.Namespace(
            stage="c1",
            provider_adapter="relay_openai_compatible",
            model="gpt-5.6-luna",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=True,
            run_id="offline_mock_length_usage",
            max_calls=1,
            max_total_tokens=100_000,
            max_cost=Decimal("100"),
            cost_currency="CA",
            input_price_per_million=Decimal("7"),
            output_price_per_million=Decimal("42"),
            api_key_env_name=None,
            timeout_seconds=17,
        )
        with pytest.raises(
            candidate_protocol.ProtocolIncompatible, match="finish_reason is 'length'"
        ):
            runner.execute(args, test_assets, lock)
        run_dir = temporary_root / args.run_id
        failure = load_json_bytes(run_dir / "failure.json")
        assert failure["input_tokens"] == 1339
        assert failure["output_tokens"] == 6500
        assert failure["provider_reported_tokens_available"] is True
        assert failure["total_cost"] == "0.282373"
        assert failure["provider_reported_model"] == "offline-length-provider-report"
        assert failure["provider_response_id"] == "offline-length-response"
        assert failure["finish_reason"] == "length"
        assert failure["response_sha256"] == sha256_path(
            run_dir / "responses" / "001_synthetic_c1_utf8_full_extract.json"
        )
        assert failure["local_canonical_validation"]["performed"] is False
        assert failure["valid_candidate_count"] == 0
        assert not (run_dir / "manifest.json").exists()
        assert not (run_dir / "candidates.json").exists()


def test_c2_length_failure_accounting_correction_is_hash_bound() -> None:
    run_dir = (
        ROOT
        / "data"
        / "development"
        / "estg"
        / "llm_candidate_runs"
        / "c2_relay_gpt56_luna_strict_v1_1_pilot3_live_v1"
    )
    correction = load_json_bytes(run_dir / "accounting_correction.json")
    failure = load_json_bytes(run_dir / "failure.json")
    assert sha256_path(run_dir / "failure.json") == correction["original_failure_sha256"]
    assert sha256_path(run_dir / "preregistration.json") == correction["preregistration_sha256"]
    assert sha256_path(run_dir / "responses" / "001_estg_000080_pass_a.json") == (
        correction["raw_response_sha256"]
    )
    assert sha256_path(run_dir / "requests" / "001_estg_000080_pass_a.transport.json") == (
        correction["transport_request_sha256"]
    )
    assert failure["request_count"] == 1 and failure["retry_count"] == 0
    assert failure["input_tokens"] == failure["output_tokens"] == 0
    assert correction["usage"] == {
        "input_tokens": 1339,
        "output_tokens": 6500,
        "reasoning_tokens": 6500,
        "total_tokens": 7839,
        "provider_reported_tokens_available": True,
    }
    assert correction["pricing"]["recorded_cost_from_provider_usage"] == "0.282373"
    assert correction["pricing"]["within_authorized_limits"] is True
    assert correction["finish_reason"] == "length"
    assert correction["completion_validation"]["valid_candidate_count"] == 0
    assert correction["safety"]["c2_started"] is True
    assert correction["safety"]["c2_completed"] is False
    assert correction["safety"]["evaluation_count"] == 0
    assert correction["safety"]["precision"] is None
    assert correction["safety"]["recall"] is None
    assert not (run_dir / "manifest.json").exists()
    assert not (run_dir / "candidates.json").exists()


def test_gpt56_transport_hash_is_versioned_and_not_the_canonical_request_hash() -> None:
    _assets, semantic, prepared = _prepared()
    semantic_sha256 = hashlib.sha256(serialize_semantic_request(semantic)).hexdigest()
    transport_sha256 = serialized_transport_sha256(prepared)
    assert semantic_sha256 == "eb074081cc52d22025e263e3f94b2165f95493f511ddc454b9ea5f5923c085e1"
    assert transport_sha256 == "ac24297d027074b147bc41ddc08bbbaa55b232be337838a6d6180aa47fbc282f"
    assert transport_sha256 != semantic_sha256
    assert canonical_json_bytes(prepared.body).endswith(b"\n")

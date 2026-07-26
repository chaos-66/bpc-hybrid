"""C0 gates for the sole canonical EStG-150 candidate protocol."""
from __future__ import annotations

import argparse
import http.client
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import urllib.error
from decimal import Decimal
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from formal_experiment.estg150_candidate_protocol import (  # noqa: E402
    CONFIG_PATH,
    SEMANTIC_FIXTURE_PATH,
    SYNTHETIC_FIXTURE_PATH,
    CandidateValidationError,
    ProtocolError,
    ProtocolIncompatible,
    adapter_from_config,
    build_semantic_request,
    build_user_object,
    canonical_json_bytes,
    extract_provider_response,
    load_json_bytes,
    load_protocol_assets,
    post_identical_request_with_retries,
    route_for_index,
    serialize_semantic_request,
    sha256_path,
    validate_candidate,
    verify_c0_lock,
)
import formal_experiment.estg150_candidate_protocol as candidate_protocol  # noqa: E402


RUNNER = ROOT / "scripts" / "run_estg150_candidate_protocol.py"
LEGACY_RUNNER = ROOT / "scripts" / "run_estg150_ai_review.py"
MATRIX_MANIFEST = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "c1_transport_compatibility_matrix_20260725_v1"
    / "manifest.json"
)


def valid_synthetic_candidate() -> dict:
    fixture = load_json_bytes(SYNTHETIC_FIXTURE_PATH)
    text = fixture["frozen_candidate_text_en"]
    actor = "The authority"
    action = "check"
    cue = "must"
    condition = "whether transfers are permitted"
    return {
        "schema_version": "estg150_ai_review_model_output@1.0.0",
        "sample_id": fixture["sample_id"],
        "context_sufficiency": "sufficient",
        "translation": {"decision": "accepted", "proposed_text_en": text, "issues": []},
        "clauses": [
            {
                "clause_id": "synthetic_c01",
                "clause_span": {"text": text, "start": 0, "end": len(text)},
                "modality": {
                    "label": "obligation",
                    "evidence": [{"text": cue, "start": text.index(cue), "end": text.index(cue) + len(cue)}],
                },
                "actors": [
                    {
                        "id": "actor_1",
                        "text": actor,
                        "start": text.index(actor),
                        "end": text.index(actor) + len(actor),
                        "normalized": "authority",
                    }
                ],
                "actions": [
                    {
                        "id": "action_1",
                        "text": action,
                        "start": text.index(action),
                        "end": text.index(action) + len(action),
                        "normalized": "check",
                    }
                ],
                "conditions": [
                    {
                        "id": "condition_1",
                        "text": condition,
                        "start": text.index(condition),
                        "end": text.index(condition) + len(condition),
                        "normalized": condition,
                    }
                ],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [{"actor_id": "actor_1", "action_id": "action_1"}],
                "order_relations": [],
            }
        ],
        "unsupported_or_ambiguous": [],
        "confidence": "high",
        "rationale_summary": "Synthetic UTF-8 transport fixture.",
    }


def test_locked_assets_and_serializer_fixture_match_c0_lock():
    assets = load_protocol_assets()
    lock = verify_c0_lock(assets)
    assert len(assets.samples) == 150
    assert lock["historical_hidden_transport_payload_not_archived"] is True
    assert lock["serializer_fixture_sha256"] == sha256_path(SEMANTIC_FIXTURE_PATH)
    assert lock["asset_hashes"] == {
        "membership_payload_sha256": "8573e105d2bc167c6aa0a92c16f79a3aaf725baadfea86f0b5d2b1ea68b1e0d7",
        "layer_a": "55b64598dedfa0c0038084ee62c0928bddfa4bf17f19db80d461da2cb7bf26a3",
        "layer_b": "f65e929bf1fe498ffce6f08d30f95d1c4de53592457352cce915cfbf8ee91da3",
        "layer_c": "9476945ca387fb7efad5c1405cca59a6ef24ff50a23e22ba2c46ad6847290b8b",
        "output_schema": "fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9",
        "full_extract_prompt": "9ad65ce8921d76afc3cc3bfe50b1c2f447cae8155cc40041fc32d60f6a63ae0b",
        "pass_a_prompt": "9d6127e3457c05d96d52d339701e41d104b11f1128a98853a4a24b650c4d1fec",
        "pass_b_prompt": "3ff3c8fd4e22c62ed5e0fedb656a3c290c64e5969b1cc85faea61008449e9fcd",
    }


def test_historical_membership_order_and_routes_are_exact():
    assets = load_protocol_assets()
    assert assets.samples[0]["sample_id"] == "estg_000080"
    assert assets.samples[2]["sample_id"] == "estg_000062"
    assert assets.samples[-1]["sample_id"] == "estg_000148"
    assert route_for_index(0) == ("pass_a", "pass_b")
    assert route_for_index(2) == ("pass_a", "pass_b")
    assert route_for_index(3) == ("full_extract",)
    assert route_for_index(149) == ("full_extract",)
    assert sum(len(route_for_index(i)) for i in range(150)) == 153


def test_route_visibility_and_user_field_order_fail_closed():
    assets = load_protocol_assets()
    sample0 = assets.samples[0]
    pass_a = build_user_object(sample0, route="pass_a")
    assert list(pass_a) == ["sample_id", "raw_text_de", "frozen_candidate_text_en"]
    assert "legacy_six_element_draft" not in pass_a
    pass_b_candidate = valid_synthetic_candidate()
    pass_b_candidate["sample_id"] = sample0["sample_id"]
    pass_b_candidate["translation"]["proposed_text_en"] = sample0["frozen_candidate_text_en"]
    pass_b_candidate["translation"]["decision"] = "accepted"
    pass_b_candidate["clauses"] = []
    pass_b = build_user_object(sample0, route="pass_b", pass_a_candidate=pass_b_candidate)
    assert list(pass_b) == [
        "sample_id",
        "raw_text_de",
        "frozen_candidate_text_en",
        "pass_a_candidate",
        "legacy_six_element_draft",
    ]
    full = build_user_object(assets.samples[3], route="full_extract")
    assert list(full) == [
        "sample_id",
        "raw_text_de",
        "frozen_candidate_text_en",
        "legacy_six_element_draft",
    ]
    with pytest.raises(ProtocolError):
        build_semantic_request(assets, sample0, route="full_extract")


def test_provider_adapters_share_identical_semantic_payload_and_schema():
    assets = load_protocol_assets()
    synthetic = load_json_bytes(SYNTHETIC_FIXTURE_PATH)
    semantic = build_semantic_request(assets, synthetic, route="full_extract")
    expected_bytes = serialize_semantic_request(semantic)
    assert expected_bytes == SEMANTIC_FIXTURE_PATH.read_bytes()
    assert [message["role"] for message in semantic["messages"]] == ["system", "developer", "user"]
    assert semantic["messages"][1]["content"].encode("utf-8") == (
        ROOT / assets.config["assets"]["full_extract_prompt"]["path"]
    ).read_bytes()
    assert semantic["output_schema_text"].encode("utf-8") == (
        ROOT / assets.config["assets"]["output_schema"]["path"]
    ).read_bytes()

    bodies = []
    for adapter_id in assets.config["provider_adapters"]:
        adapter = adapter_from_config(assets.config, adapter_id)
        bodies.append(adapter.build_transport_body(semantic, model="provider-model"))
    assert all(body == bodies[0] for body in bodies[1:])
    assert bodies[0]["response_format"]["json_schema"]["schema"]["$id"] == (
        "estg150_ai_review_model_output.schema.json"
    )
    assert "temperature" not in bodies[0]


def test_layer_d_layer_e_and_gold_cannot_enter_semantic_request():
    assets = load_protocol_assets()
    semantic = build_semantic_request(
        assets, load_json_bytes(SYNTHETIC_FIXTURE_PATH), route="full_extract"
    )
    user = json.loads(semantic["messages"][2]["content"])
    assert set(user) == {
        "sample_id",
        "raw_text_de",
        "frozen_candidate_text_en",
        "legacy_six_element_draft",
    }
    serialized = semantic["messages"][2]["content"].lower()
    for forbidden in ("text_zh", "back_translation_en", "human_correction", "layer_e", "gold"):
        assert forbidden not in serialized
    config_text = CONFIG_PATH.read_text(encoding="utf-8")
    assert "estg_150_review_aids" not in config_text
    assert "estg_150_human_correction" not in config_text


def test_utf8_newline_and_python_offsets_do_not_drift():
    assets = load_protocol_assets()
    semantic = build_semantic_request(
        assets, load_json_bytes(SYNTHETIC_FIXTURE_PATH), route="full_extract"
    )
    raw = serialize_semantic_request(semantic)
    assert "Übermittlungen".encode("utf-8") in raw
    assert raw.endswith(b"\n")
    user = json.loads(semantic["messages"][2]["content"])
    assert "\n" in user["raw_text_de"]
    validation = validate_candidate(
        valid_synthetic_candidate(),
        expected_sample_id="synthetic_c1_utf8",
        frozen_candidate_text_en=user["frozen_candidate_text_en"],
        schema=assets.schema,
    )
    assert validation == {
        "schema_valid": True,
        "exact_span_valid": True,
        "normative_cue_coverage_valid": True,
    }


def test_normative_cue_outside_all_clauses_is_invalid_without_repair():
    assets = load_protocol_assets()
    candidate = valid_synthetic_candidate()
    text = candidate["translation"]["proposed_text_en"]
    candidate["clauses"][0]["clause_span"] = {
        "text": text[text.index("whether"):],
        "start": text.index("whether"),
        "end": len(text),
    }
    candidate["clauses"][0]["modality"]["evidence"] = [
        {"text": "permitted", "start": text.index("permitted"), "end": text.index("permitted") + 9}
    ]
    candidate["clauses"][0]["actors"] = []
    candidate["clauses"][0]["actions"] = []
    candidate["clauses"][0]["actor_action_map"] = []
    with pytest.raises(CandidateValidationError, match="normative cues"):
        validate_candidate(
            candidate,
            expected_sample_id="synthetic_c1_utf8",
            frozen_candidate_text_en=text,
            schema=assets.schema,
        )


def test_response_extraction_records_identity_usage_hash_and_validation():
    assets = load_protocol_assets()
    adapter = adapter_from_config(assets.config, "relay_openai_compatible")
    candidate = valid_synthetic_candidate()
    response = canonical_json_bytes(
        {
            "id": "synthetic-response",
            "model": "relay-reported-model",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(candidate, ensure_ascii=False)},
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
    )
    extracted, metadata = extract_provider_response(
        response,
        adapter=adapter,
        expected_sample_id="synthetic_c1_utf8",
        frozen_candidate_text_en=candidate["translation"]["proposed_text_en"],
        schema=assets.schema,
    )
    assert extracted == candidate
    assert metadata["provider_identity_attestation"] == "unverified_relay_report"
    assert metadata["provider_reported_model"] == "relay-reported-model"
    assert metadata["validation"]["schema_valid"] is True


def test_network_retry_resends_byte_identical_request(monkeypatch):
    request_bytes = b'{"fixed":"request"}\n'
    observed_payloads = []

    class SyntheticResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"fixed":"response"}'

    def synthetic_urlopen(request, timeout):
        assert timeout == 17
        observed_payloads.append(request.data)
        if len(observed_payloads) == 1:
            raise urllib.error.URLError("synthetic timeout")
        return SyntheticResponse()

    monkeypatch.setattr(candidate_protocol.urllib.request, "urlopen", synthetic_urlopen)
    response_bytes, reasons = post_identical_request_with_retries(
        endpoint="https://relay.invalid/v1/chat/completions",
        api_key="synthetic-key",
        request_bytes=request_bytes,
        timeout_seconds=17,
        max_network_retries=2,
        retryable_statuses={429, 500, 502, 503, 504},
    )
    assert observed_payloads == [request_bytes, request_bytes]
    assert response_bytes == b'{"fixed":"response"}'
    assert reasons == ["network_timeout_or_url_error"]


def test_remote_disconnect_is_a_retryable_identical_transport_failure(monkeypatch):
    request_bytes = b'{"fixed":"request"}\n'
    observed_payloads = []

    class SyntheticResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"fixed":"response"}'

    def synthetic_urlopen(request, timeout):
        observed_payloads.append(request.data)
        if len(observed_payloads) == 1:
            raise http.client.RemoteDisconnected("synthetic relay disconnect")
        return SyntheticResponse()

    monkeypatch.setattr(candidate_protocol.urllib.request, "urlopen", synthetic_urlopen)
    response_bytes, reasons = post_identical_request_with_retries(
        endpoint="https://relay.invalid/v1/chat/completions",
        api_key="synthetic-key",
        request_bytes=request_bytes,
        timeout_seconds=17,
        max_network_retries=2,
        retryable_statuses={429, 500, 502, 503, 504},
    )
    assert observed_payloads == [request_bytes, request_bytes]
    assert response_bytes == b'{"fixed":"response"}'
    assert reasons == ["network_timeout_or_url_error"]


def test_terminal_http_error_preserves_bounded_provider_diagnostics(monkeypatch):
    error_body = b'{"error":{"message":"Unsupported parameter: reasoning_effort"}}'
    request_bytes = b'{"fixed":"request"}\n'

    def synthetic_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            400,
            "Bad Request",
            {"x-request-id": "req-synthetic-400"},
            io.BytesIO(error_body),
        )

    monkeypatch.setattr(candidate_protocol.urllib.request, "urlopen", synthetic_urlopen)
    with pytest.raises(ProtocolIncompatible) as raised:
        post_identical_request_with_retries(
            endpoint="https://relay.invalid/v1/chat/completions",
            api_key="synthetic-key",
            request_bytes=request_bytes,
            timeout_seconds=17,
            max_network_retries=2,
            retryable_statuses={429, 500, 502, 503, 504},
        )

    assert raised.value.http_status == 400
    assert raised.value.response_body == error_body
    assert raised.value.response_body_truncated is False
    assert raised.value.provider_request_id == "req-synthetic-400"
    assert raised.value.retry_reasons == ()


def test_provider_error_archive_is_exact_and_blocks_credential_echo():
    spec = importlib.util.spec_from_file_location("estg150_candidate_runner_for_test", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    with tempfile.TemporaryDirectory(prefix="estg150_http_error_", dir=ROOT) as temporary:
        run_dir = Path(temporary)
        body = b'{"error":{"message":"synthetic transport rejection"}}'
        diagnostic = runner.archive_provider_http_error(
            run_dir,
            "001_synthetic_full_extract",
            ProtocolIncompatible(
                "synthetic failure",
                http_status=400,
                response_body=body,
                provider_request_id="req-archive-test",
                retry_reasons=("http_429",),
            ),
            api_key="synthetic-secret",
        )
        archived = run_dir / diagnostic["provider_error_response_path"]
        assert archived.read_bytes() == body
        assert diagnostic["provider_error_response_archived"] is True
        assert diagnostic["provider_error_response_sha256"] == candidate_protocol.sha256_bytes(body)
        assert diagnostic["retry_reasons"] == ["http_429"]

        blocked = runner.archive_provider_http_error(
            run_dir,
            "002_synthetic_full_extract",
            ProtocolIncompatible(
                "synthetic credential echo",
                http_status=400,
                response_body=b'{"debug":"Bearer synthetic-secret"}',
            ),
            api_key="synthetic-secret",
        )
        assert blocked["credential_echo_detected"] is True
        assert blocked["provider_error_response_archived"] is False
        assert not (run_dir / "responses" / "002_synthetic_full_extract.http_error.body").exists()

        blocked_request_id = runner.archive_provider_http_error(
            run_dir,
            "003_synthetic_full_extract",
            ProtocolIncompatible(
                "synthetic credential echo in request ID",
                http_status=400,
                provider_request_id="trace-synthetic-secret",
            ),
            api_key="synthetic-secret",
        )
        assert blocked_request_id["credential_echo_detected"] is True
        assert blocked_request_id["provider_request_id"] is None


def test_execute_failure_manifest_links_archived_http_error(monkeypatch):
    spec = importlib.util.spec_from_file_location("estg150_candidate_runner_execute_test", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    with tempfile.TemporaryDirectory(prefix="estg150_execute_error_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        assets = load_protocol_assets()
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        lock = verify_c0_lock(assets)
        error_body = b'{"error":{"param":"reasoning_effort","code":"unsupported_parameter"}}'

        monkeypatch.setattr(runner, "acquire_api_key", lambda env_name: "synthetic-secret")

        def reject_request(**kwargs):
            raise ProtocolIncompatible(
                "synthetic HTTP 400",
                http_status=400,
                response_body=error_body,
                provider_request_id="req-execute-test",
            )

        monkeypatch.setattr(runner, "post_identical_request_with_retries", reject_request)
        args = argparse.Namespace(
            stage="c1",
            provider_adapter="relay_openai_compatible",
            model="gpt-5.6-luna",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=True,
            run_id="synthetic_http_error_run",
            max_calls=1,
            max_total_tokens=100_000,
            max_cost=Decimal("100"),
            cost_currency="TEST",
            input_price_per_million=Decimal("0"),
            output_price_per_million=Decimal("0"),
            api_key_env_name=None,
            timeout_seconds=17,
        )

        with pytest.raises(ProtocolIncompatible):
            runner.execute(args, test_assets, lock)

        run_dir = temporary_root / args.run_id
        failure = load_json_bytes(run_dir / "failure.json")
        assert failure["status"] == "protocol_incompatible"
        assert failure["http_status"] == 400
        assert failure["provider_request_id"] == "req-execute-test"
        assert failure["provider_error_response_archived"] is True
        assert failure["provider_error_response_sha256"] == candidate_protocol.sha256_bytes(error_body)
        assert failure["canonical_schema_sha256"] == (
            "fbbb628ad0f25639958c6d02db9bac90ed06865e634bd4e8eeb7b50ac7108ca9"
        )
        assert failure["transport_adapter_version"] == "1.2.0"
        assert failure["transport_schema_sha256"] == (
            "ef8c684b2456196eac14cc7748bb687aef5ef32fd8a405c3003bd831ad380af7"
        )
        assert failure["canonical_serializer_sha256"] == (
            "d20ae560a627c4d3faa88439908c517e7726aabb1121128af7b9013f5512edef"
        )
        assert failure["transport_request_sha256"] == failure["transport_request_sha256s"][0]
        assert failure["local_canonical_validation"]["performed"] is False
        assert failure["request_downgrade_applied"] is False
        assert failure["precision"] is None and failure["recall"] is None
        assert failure["c1_passed"] is False and failure["c2_started"] is False
        assert (run_dir / failure["provider_error_response_path"]).read_bytes() == error_body


def test_c1_transport_matrix_binds_all_failure_and_request_artifacts():
    matrix = load_json_bytes(MATRIX_MANIFEST)
    assert matrix["status"] == "completed_no_valid_candidate"
    assert matrix["totals"] == {
        "models": 7,
        "logical_request_count": 7,
        "transport_retry_count": 2,
        "derived_http_attempt_count": 9,
        "valid_candidate_count": 0,
        "evaluation_count": 0,
        "precision": None,
        "recall": None,
        "provider_reported_tokens_available": False,
        "actual_billed_cost_observed": False,
    }
    assert len({row["run_id"] for row in matrix["runs"]}) == 7
    assert len({row["model"] for row in matrix["runs"]}) == 7
    run_root = MATRIX_MANIFEST.parent.parent
    for row in matrix["runs"]:
        run_dir = run_root / row["run_id"]
        failure_path = run_dir / "failure.json"
        assert sha256_path(failure_path) == row["failure_sha256"]
        failure = load_json_bytes(failure_path)
        assert failure["status"] == row["status"]
        transport_paths = tuple((run_dir / "requests").glob("*.transport.json"))
        semantic_paths = tuple((run_dir / "requests").glob("*.semantic.json"))
        assert len(transport_paths) == len(semantic_paths) == 1
        assert sha256_path(transport_paths[0]) == row["transport_request_sha256"]
        assert sha256_path(semantic_paths[0]) == matrix["semantic_request_sha256"]
        if row["provider_error_response_sha256"] is not None:
            error_path = run_dir / failure["provider_error_response_path"]
            assert sha256_path(error_path) == row["provider_error_response_sha256"]
        assert not (run_dir / "candidates.json").exists()
        assert not (run_dir / "manifest.json").exists()

    assert matrix["conclusions"]["model_safety_refusal_observed"] is False
    assert matrix["conclusions"]["c1_passed"] is False
    assert matrix["conclusions"]["c2_started"] is False


def test_c0_dry_run_is_offline_and_does_not_create_run_directory():
    before = set((ROOT / "data" / "development" / "estg" / "llm_candidate_runs").iterdir())
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--stage", "c0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "no network/API call was made" in completed.stdout
    assert "planned_all150_requests=153" in completed.stdout
    assert "Layer D/E/Gold reads=0" in completed.stdout
    after = set((ROOT / "data" / "development" / "estg" / "llm_candidate_runs").iterdir())
    assert after == before


def test_c1_execute_without_full_authorization_stops_before_run_dir_or_key():
    run_id = "test_c1_missing_authorization_never_created"
    run_dir = ROOT / "data" / "development" / "estg" / "llm_candidate_runs" / run_id
    assert not run_dir.exists()
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--stage",
            "c1",
            "--execute-api",
            "--provider-adapter",
            "relay_openai_compatible",
            "--model",
            "gpt-5.6-luna",
            "--endpoint",
            "https://api.chatanywhere.tech/v1/chat/completions",
            "--run-id",
            run_id,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode != 0
    assert "--confirm-authorized-provider-budget" in completed.stdout + completed.stderr
    assert "Provider API key" not in completed.stdout + completed.stderr
    assert not run_dir.exists()


def test_c2_offline_preparation_freezes_six_preflights_without_starting_c2(monkeypatch):
    spec = importlib.util.spec_from_file_location("estg150_candidate_runner_c2_offline_test", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

    with tempfile.TemporaryDirectory(prefix="estg150_c2_offline_", dir=ROOT) as temporary:
        temporary_root = Path(temporary)
        assets = load_protocol_assets()
        config = dict(assets.config)
        config["output"] = dict(config["output"])
        config["output"]["root"] = temporary_root.relative_to(ROOT).as_posix()
        test_assets = candidate_protocol.ProtocolAssets(
            config, assets.schema, assets.schema_text, assets.prompts, assets.samples
        )
        lock = verify_c0_lock(assets)
        monkeypatch.setattr(
            runner,
            "acquire_api_key",
            lambda env_name: (_ for _ in ()).throw(AssertionError("offline prep read API key")),
        )
        monkeypatch.setattr(
            runner,
            "post_identical_request_with_retries",
            lambda **kwargs: (_ for _ in ()).throw(AssertionError("offline prep sent network request")),
        )
        args = argparse.Namespace(
            stage="c2",
            write_offline_preparation=True,
            execute_api=False,
            provider_adapter="relay_openai_compatible",
            model="gpt-5.6-luna",
            endpoint="https://api.chatanywhere.tech/v1/chat/completions",
            confirm_authorized_provider_budget=False,
            run_id="c2_offline_unit_test_v1",
            max_calls=6,
            max_total_tokens=78_000,
            max_cost=Decimal("1.92"),
            cost_currency="CA",
            input_price_per_million=Decimal("7"),
            output_price_per_million=Decimal("42"),
            api_key_env_name=None,
            timeout_seconds=17,
        )

        assert runner.prepare_c2_offline(args, test_assets, lock) == 0
        run_dir = temporary_root / args.run_id
        prereg = load_json_bytes(run_dir / "preregistration.json")
        plan = load_json_bytes(run_dir / "offline_preparation.json")
        assert prereg["authorization"] == {
            "provider_authorized": False,
            "maximum_calls": 6,
            "maximum_total_tokens": 78_000,
            "maximum_cost": "1.92",
            "cost_currency": "CA",
        }
        assert prereg["stage_transition"]["c1_passed"] is True
        assert prereg["stage_transition"]["c2_started"] is False
        assert prereg["request_plan"]["expected_request_count"] == 6
        assert prereg["request_plan"]["pass_b_live_request_sha256s_deferred"] is True
        assert plan["status"] == "offline_preflight_frozen_real_api_unauthorized_c2_not_started"
        assert plan["request_count"] == 6
        assert [record["route"] for record in plan["requests"]] == [
            "pass_a",
            "pass_b",
            "pass_a",
            "pass_b",
            "pass_a",
            "pass_b",
        ]
        assert all(
            record["structured_outputs_preflight"]["passed"] is True
            and record["request_downgrade_applied"] is False
            for record in plan["requests"]
        )
        assert len({record["transport_request_sha256"] for record in plan["requests"]}) == 6
        for record in plan["requests"]:
            stem = f"{record['sequence']:03d}_{record['sample_id']}_{record['route']}"
            transport_path = run_dir / "offline_requests" / f"{stem}.transport.json"
            semantic_path = run_dir / "offline_requests" / f"{stem}.semantic.json"
            assert candidate_protocol.sha256_path(transport_path) == record["transport_request_sha256"]
            assert candidate_protocol.sha256_path(semantic_path) == record["semantic_request_sha256"]
            if record["route"] == "pass_b":
                assert record["pass_a_dependency"]["canonical_validation_passed"] is True
                assert record["pass_a_dependency"]["future_live_transport_request_sha256_deferred"] is True
                assert record["transport_request_hash_scope"] == (
                    "offline_preflight_fixture_only_live_pass_a_dependent"
                )
            else:
                assert record["pass_a_dependency"] is None
                assert record["transport_request_hash_scope"] == (
                    "exact_for_same_locked_inputs_model_and_profile"
                )
        assert plan["budget"]["hard_guard_checks_passed"] is True
        assert plan["budget"]["combined_token_output_guard_worst_cost"] == "1.911"
        assert plan["safety"] == {
            "real_api_call": False,
            "billed_tokens": 0,
            "billed_cost": "0",
            "layer_d_read_during_generation": False,
            "layer_e_read_during_generation": False,
            "gold_visible_during_generation": False,
            "evaluation_count": 0,
            "precision": None,
            "recall": None,
            "c1_passed": True,
            "c2_started": False,
            "c3_started": False,
            "c4_started": False,
        }
        assert not (run_dir / "manifest.json").exists()
        assert not (run_dir / "candidates.json").exists()
        with pytest.raises(ProtocolError, match="never overwrite"):
            runner.prepare_c2_offline(args, test_assets, lock)


def test_legacy_relay_entry_is_not_an_active_real_runner():
    source = LEGACY_RUNNER.read_text(encoding="utf-8")
    assert "legacy relay execution is retired" in source
    assert "run_estg150_candidate_protocol.py" in source

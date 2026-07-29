"""Offline safety and contract tests for the GPT-5.6 Sol AI review path."""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "run_estg150_ai_review.py"
CONTRACT_PATH = ROOT / "configs" / "estg150_ai_review_gpt56sol_v1.json"
INTERNAL_PILOT_DIR = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "codex_internal_gpt56sol_pilot3_v1"
)

SPEC = importlib.util.spec_from_file_location("run_estg150_ai_review", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def valid_candidate() -> dict:
    text = "The taxpayer shall file the return."
    return {
        "schema_version": "estg150_ai_review_model_output@1.0.0",
        "sample_id": "estg_test",
        "context_sufficiency": "sufficient",
        "translation": {
            "decision": "accepted",
            "proposed_text_en": text,
            "issues": [],
        },
        "clauses": [
            {
                "clause_id": "c1",
                "clause_span": {"text": text, "start": 0, "end": len(text)},
                "modality": {
                    "label": "obligation",
                    "evidence": [{"text": "shall", "start": 13, "end": 18}],
                },
                "actors": [
                    {"id": "a1", "text": "taxpayer", "start": 4, "end": 12, "normalized": "taxpayer"}
                ],
                "actions": [
                    {"id": "v1", "text": "file", "start": 19, "end": 23, "normalized": "file"}
                ],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [{"actor_id": "a1", "action_id": "v1"}],
                "order_relations": [],
            }
        ],
        "unsupported_or_ambiguous": [],
        "confidence": "high",
        "rationale_summary": "The translation and extraction are direct.",
    }


def test_contract_locks_sol_high_strict_and_development_only():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["model"]["request_model_id"] == "gpt-5.6-sol"
    assert contract["model"]["reasoning_effort"] == "high"
    assert contract["model"]["structured_output"] == "strict_json_schema"
    assert contract["model"]["temperature_field_policy"] == "omit"
    assert contract["gold_policy"] == {
        "layer_e_read": False,
        "layer_e_write": False,
        "human_review_state_write": False,
        "output_class": "development_ai_adjudication_candidate_not_human_gold",
    }
    assert contract["passes"]["deepseek_layer_d_allowed_as_input"] is False
    assert contract["pilot_policy"]["automatic_pilot_to_full_continuation"] is False
    assert contract["pricing_snapshot_from_user_screenshot"]["price_unit"].startswith("unverified")


@pytest.mark.parametrize(
    "value",
    [
        "https://api.chatanywhere.tech/v1",
        "https://api.chatanywhere.tech/v1/",
        "https://api.chatanywhere.tech/v1/chat/completions",
        "https://api.chatanywhere.tech/v1/chat/completions/",
    ],
)
def test_endpoint_normalizes_base_and_full_shapes_without_double_append(value: str):
    assert runner.normalize_chat_completions_endpoint(value) == (
        "https://api.chatanywhere.tech/v1/chat/completions"
    )


@pytest.mark.parametrize(
    "value",
    [
        "http://api.chatanywhere.tech/v1",
        "https://other.example/v1",
        "https://api.chatanywhere.tech/v1/models",
        "https://api.chatanywhere.tech/v1?key=secret",
        "https://user:pass@api.chatanywhere.tech/v1",
    ],
)
def test_endpoint_rejects_unsafe_or_unlocked_shapes(value: str):
    with pytest.raises(ValueError):
        runner.normalize_chat_completions_endpoint(value)


def test_request_body_uses_reasoning_and_strict_schema_without_temperature():
    _, schema, prompt_a, _ = runner.load_contract()
    body = runner.build_request_body(
        model="gpt-5.6-sol",
        reasoning_effort="high",
        max_completion_tokens=6500,
        system_prompt=prompt_a,
        user_payload="{}",
        schema=schema,
    )
    assert body["model"] == "gpt-5.6-sol"
    assert body["reasoning_effort"] == "high"
    assert body["max_completion_tokens"] == 6500
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert "$schema" not in body["response_format"]["json_schema"]["schema"]
    assert "$id" not in body["response_format"]["json_schema"]["schema"]
    assert "temperature" not in body
    assert "max_tokens" not in body
    assert "thinking" not in body


def test_fixed_input_join_maps_layer_a_legacy_id_to_layer_b_sample_id():
    samples = runner.load_fixed_inputs()
    assert len(samples) == 150
    assert len({row["sample_id"] for row in samples}) == 150
    assert all(row["raw_text_de"] and row["candidate_text_en"] for row in samples)
    assert all("text_zh" not in row for row in samples)
    assert all("back_translation_en" not in row for row in samples)


def test_dry_run_never_requests_key_or_writes_run_directory():
    before = set(runner.OUTPUT_ROOT.glob("codex_test_dry_run_*"))
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "--pilot",
            "3",
            "--start-index",
            "0",
            "--end-index",
            "3",
            "--run-id",
            "codex_test_dry_run_never_created",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0
    assert "no LLM/API call will be made" in completed.stdout
    assert "no API key requested" in completed.stdout
    assert "planned calls  : 6" in completed.stdout
    assert "Layer E access : none" in completed.stdout
    assert "ChatAnywhere API key" not in completed.stdout + completed.stderr
    after = set(runner.OUTPUT_ROOT.glob("codex_test_dry_run_*"))
    assert after == before


def test_real_run_missing_relay_confirmation_fails_before_key_prompt():
    completed = subprocess.run(
        [
            sys.executable,
            str(RUNNER_PATH),
            "--allow-llm",
            "--pilot",
            "1",
            "--start-index",
            "0",
            "--end-index",
            "1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = completed.stdout + completed.stderr
    assert completed.returncode != 0
    assert "--confirm-third-party-relay-risk" in combined
    assert "ChatAnywhere API key" not in combined


def test_candidate_cross_field_validator_accepts_exact_spans():
    _, schema, _, _ = runner.load_contract()
    candidate = valid_candidate()
    runner.validate_candidate(
        candidate,
        expected_sample_id="estg_test",
        frozen_candidate_text_en=candidate["translation"]["proposed_text_en"],
        schema=schema,
    )


@pytest.mark.parametrize("mutation", ["bad_span", "bad_edge", "accepted_changed", "missing_context_reason"])
def test_candidate_cross_field_validator_rejects_semantic_inconsistency(mutation: str):
    _, schema, _, _ = runner.load_contract()
    candidate = deepcopy(valid_candidate())
    frozen = candidate["translation"]["proposed_text_en"]
    if mutation == "bad_span":
        candidate["clauses"][0]["actions"][0]["text"] = "files"
    elif mutation == "bad_edge":
        candidate["clauses"][0]["actor_action_map"][0]["action_id"] = "missing"
    elif mutation == "accepted_changed":
        frozen = "A different frozen translation."
    elif mutation == "missing_context_reason":
        candidate["context_sufficiency"] = "insufficient"
    with pytest.raises(runner.CandidateValidationError):
        runner.validate_candidate(
            candidate,
            expected_sample_id="estg_test",
            frozen_candidate_text_en=frozen,
            schema=schema,
        )


def test_runner_source_has_no_layer_e_data_path_or_api_key_value_flag():
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "estg_150_human_correction_v1.json" not in source
    assert 'add_argument("--api-key"' not in source
    assert "LAYER_D" not in source


def test_internal_sol_pilot_is_hash_locked_valid_and_not_human_gold():
    config = json.loads((INTERNAL_PILOT_DIR / "run_config.json").read_text(encoding="utf-8"))
    pass_a_path = INTERNAL_PILOT_DIR / "pass_a_candidates.json"
    pass_b_path = INTERNAL_PILOT_DIR / "pass_b_candidates.json"
    pass_a = json.loads(pass_a_path.read_text(encoding="utf-8"))
    pass_b = json.loads(pass_b_path.read_text(encoding="utf-8"))
    summary = json.loads((INTERNAL_PILOT_DIR / "run_summary.json").read_text(encoding="utf-8"))
    manifest = runner.load_jsonl(INTERNAL_PILOT_DIR / "manifest.jsonl")

    assert config["execution_surface"] == "codex_internal_subagents"
    assert config["model"] == "gpt-5.6-sol"
    assert config["external_api_called"] is False
    assert config["api_key_requested_or_read"] is False
    assert config["external_relay_cost_cny"] == 0
    assert config["layer_e_read"] is False
    assert config["layer_e_write"] is False
    assert config["human_review_state_write"] is False
    assert config["automatic_promotion"] is False
    assert config["pass_a_file_sha256"] == hashlib.sha256(pass_a_path.read_bytes()).hexdigest()
    assert config["pass_b_file_sha256"] == hashlib.sha256(pass_b_path.read_bytes()).hexdigest()
    assert pass_b["pass_a_sha256"] == config["pass_a_file_sha256"]

    expected_ids = ["estg_000080", "estg_000070", "estg_000062"]
    assert [record["sample_id"] for record in pass_a["records"]] == expected_ids
    assert [record["sample_id"] for record in pass_b["records"]] == expected_ids
    assert [record["sample_id"] for record in manifest] == expected_ids
    assert summary["sample_ids"] == expected_ids
    assert summary["status"] == "succeeded_development_pilot"
    assert summary["output_class"] == "development_ai_adjudication_candidate_not_human_gold"
    assert summary["full_batch_authorized"] is False

    _, schema, _, _ = runner.load_contract()
    sample_index = {row["sample_id"]: row for row in runner.load_fixed_inputs()}
    manifest_index = {row["sample_id"]: row for row in manifest}
    for pass_a_record, pass_b_record in zip(pass_a["records"], pass_b["records"]):
        sample_id = pass_b_record["sample_id"]
        frozen_text = sample_index[sample_id]["candidate_text_en"]
        runner.validate_candidate(
            pass_a_record,
            expected_sample_id=sample_id,
            frozen_candidate_text_en=frozen_text,
            schema=schema,
        )
        runner.validate_candidate(
            pass_b_record,
            expected_sample_id=sample_id,
            frozen_candidate_text_en=frozen_text,
            schema=schema,
        )
        canonical = json.dumps(
            pass_b_record,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        assert manifest_index[sample_id]["pass_b_record_sha256"] == hashlib.sha256(canonical).hexdigest()

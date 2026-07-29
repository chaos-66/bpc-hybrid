"""Regression tests for the locked offline S2.9 D1 preregistration."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.sun_style.d1_direct import (  # noqa: E402
    D1ContractError,
    assert_input_path_allowed,
    build_request_plan,
    load_s29_config,
    make_attempt,
    render_d1_request,
    summarize_attempts,
    validate_input_rows,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.s2_9_gate import S29_EXPECTATIONS, verify_s2_9_gate  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


CONFIG_PATH = ROOT / "configs" / "models" / "sun_d1_s29.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "d1_s29" / "s29_offline_contract_fixture.json"
RUNNER_PATH = ROOT / "scripts" / "run_direct_llm.py"
VERIFIER_PATH = ROOT / "scripts" / "verify_sun_d1_s29.py"


def _config() -> dict:
    return load_s29_config(CONFIG_PATH)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _runtime() -> dict:
    return {
        "llm_call_performed": False,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "latency_ms": 1,
    }


def _valid_content() -> str:
    return json.dumps(_fixture()["primary_mock_responses"][0]["payload"], ensure_ascii=False)


def _verifier_module():
    spec = importlib.util.spec_from_file_location("verify_s29_test", VERIFIER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_s29_config_freezes_model_sampling_stability_and_budget() -> None:
    config = _config()
    assert config["model"]["exact_model_id"] == "gpt-4.1-2025-04-14"
    assert config["model"]["real_api_authorized"] is False
    assert config["sampling"] == {
        "temperature": 0,
        "top_p": 1,
        "seed": None,
        "seed_policy": "unsupported_or_omitted",
        "max_output_tokens": 4096,
        "response_format": "json_object",
        "max_retries": 0,
    }
    assert config["stability"]["repeat_count"] == 5
    assert config["budget"]["absolute_max_calls"] == 750
    assert config["budget"]["estimated_worst_case_cost_usd"] == pytest.approx(36.864)
    assert config["budget"]["hard_cost_ceiling_usd"] == 37.0


def test_s29_actual_rendered_request_contains_all_four_few_shots() -> None:
    config = _config()
    prompt = load_prompt(config["prompt"]["name"])
    assert prompt.sha256 == config["prompt"]["sha256"]
    assert len(prompt.few_shot_examples) == 4
    rendered = render_d1_request(_fixture()["rows"][0], prompt, config)
    assert rendered["few_shot_count"] == 4
    assert "{few_shot_block}" not in rendered["user_prompt"]
    assert rendered["user_prompt"].count('"schema_version": "1.0.0"') >= 4
    assert "d1_syn_001" in rendered["user_prompt"]


def test_s29_plan_is_five_repeat_exact_and_unique() -> None:
    config = _config()
    prompt = load_prompt(config["prompt"]["name"])
    plan = build_request_plan(_fixture()["rows"], prompt, config)
    assert plan["input_count"] == 3
    assert plan["repeat_count"] == 5
    assert plan["request_count"] == 15
    assert len({item["request_id"] for item in plan["requests"]}) == 15
    assert [item["repeat_index"] for item in plan["requests"]] == [1] * 3 + [2] * 3 + [3] * 3 + [4] * 3 + [5] * 3
    assert all(item["few_shot_count"] == 4 for item in plan["requests"])
    assert plan["safety"]["llm_api_called"] is False
    assert plan["safety"]["env_file_read"] is False


def test_s29_rejects_gold_prediction_keys_and_gold_paths() -> None:
    config = _config()
    row = copy.deepcopy(_fixture()["rows"][0])
    row["gold_label"] = "obligation"
    with pytest.raises(D1ContractError, match="forbidden evidence"):
        validate_input_rows([row], config)
    with pytest.raises(D1ContractError, match="Gold/human-review"):
        assert_input_path_allowed(ROOT / "outputs" / "development" / "gold" / "input.jsonl", config)
    with pytest.raises(D1ContractError, match="Gold/human-review"):
        assert_input_path_allowed(ROOT / "outputs" / "development" / "human_review" / "input.jsonl", config)


def test_s29_rejects_unregistered_input_keys_and_more_than_750_calls() -> None:
    config = _config()
    prompt = load_prompt(config["prompt"]["name"])
    row = copy.deepcopy(_fixture()["rows"][0])
    row["categories"] = ["obligation"]
    with pytest.raises(D1ContractError, match="unregistered keys"):
        validate_input_rows([row], config)
    rows = [
        {
            "sample_id": f"overflow_{index:03d}",
            "source_id": f"synthetic:overflow:{index:03d}",
            "source_text": "The actor shall act.",
            "data_role": "synthetic",
        }
        for index in range(151)
    ]
    with pytest.raises(D1ContractError, match="750-call ceiling"):
        build_request_plan(rows, prompt, config)


def test_s29_valid_non_json_and_api_attempts_are_all_retained() -> None:
    rows = validate_input_rows(_fixture()["rows"], _config())
    attempts = [
        make_attempt(rows[0], repeat_index=1, runtime=_runtime(), response_content=_valid_content()),
        make_attempt(rows[1], repeat_index=1, runtime=_runtime(), response_content="not json"),
        make_attempt(
            rows[2],
            repeat_index=1,
            runtime=_runtime(),
            api_error_category="synthetic_transport_error",
        ),
    ]
    summary = summarize_attempts(attempts, rows, repeat_index=1)
    assert summary == {
        "repeat_index": 1,
        "attempt_count": 3,
        "canonical_valid_count": 1,
        "schema_or_cross_field_invalid_count": 1,
        "api_error_count": 1,
        "membership_exact": True,
        "dropped_attempt_count": 0,
    }
    assert attempts[1]["error_category"] == "non_json"
    assert attempts[1]["record"]["sample_id"] == rows[1]["sample_id"]
    assert "not json" not in json.dumps(attempts[1], ensure_ascii=False)
    assert attempts[2]["record"] is None


def test_s29_identity_mismatch_becomes_invalid_instead_of_corrupting_membership() -> None:
    row = validate_input_rows([_fixture()["rows"][0]], _config())[0]
    payload = json.loads(_valid_content())
    payload["sample_id"] = "wrong-id"
    attempt = make_attempt(
        row,
        repeat_index=1,
        runtime=_runtime(),
        response_content=json.dumps(payload),
    )
    assert attempt["request_status"] == "ok"
    assert attempt["error_category"] == "identity_mismatch"
    assert attempt["record"]["sample_id"] == row["sample_id"]
    assert attempt["record"]["schema_version"] == "invalid_response"
    payload = json.loads(_valid_content())
    payload["method"] = "direct_llm"
    malformed_method = make_attempt(
        row,
        repeat_index=1,
        runtime=_runtime(),
        response_content=json.dumps(payload),
    )
    assert malformed_method["error_category"] == "identity_mismatch"


def test_s29_runtime_and_repeat_accounting_fail_closed() -> None:
    row = validate_input_rows([_fixture()["rows"][0]], _config())[0]
    runtime = _runtime()
    runtime["total_tokens"] = 1
    with pytest.raises(D1ContractError, match="token totals disagree"):
        make_attempt(row, repeat_index=1, runtime=runtime, response_content=_valid_content())
    with pytest.raises(D1ContractError, match="1..5"):
        make_attempt(row, repeat_index=6, runtime=_runtime(), response_content=_valid_content())


def test_s29_runner_refuses_real_llm_and_does_not_import_env_loader() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--allow-llm"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "Refusing real LLM use" in completed.stdout
    source = RUNNER_PATH.read_text(encoding="utf-8")
    assert "LLMConfig.from_env" not in source
    assert "RealAPITransport" not in source


def test_s29_runner_prints_plan_without_writing_artifacts() -> None:
    completed = subprocess.run(
        [sys.executable, str(RUNNER_PATH)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    plan = json.loads(completed.stdout)
    assert plan["request_count"] == 15
    assert plan["prompt"]["few_shot_count"] == 4
    assert plan["safety"]["formal_predictions_written"] is False
    refused = subprocess.run(
        [sys.executable, str(RUNNER_PATH), "--max-calls", "14"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert refused.returncode == 2
    assert "exceeding --max-calls=14" in refused.stdout


def test_s29_verifier_contract_is_deterministic_except_timestamp() -> None:
    module = _verifier_module()
    first = module.run(CONFIG_PATH, FIXTURE_PATH)
    second = module.run(CONFIG_PATH, FIXTURE_PATH)
    first.pop("created_at")
    second.pop("created_at")
    assert first == second
    assert first["request_plan"]["request_count"] == 15
    assert first["attempt_envelope_verification"]["dropped_attempt_count"] == 0
    assert first["prompt_rendering"]["unresolved_template_placeholder"] is False
    assert first["safety"]["llm_api_called"] is False
    assert first["safety"]["env_file_read"] is False


def test_s29_attempt_membership_mismatch_fails_closed() -> None:
    rows = validate_input_rows(_fixture()["rows"], _config())
    attempts = [
        make_attempt(rows[0], repeat_index=1, runtime=_runtime(), response_content=_valid_content())
    ]
    with pytest.raises(D1ContractError, match="membership"):
        summarize_attempts(attempts, rows, repeat_index=1)


def test_s29_exact_hash_gate_status_and_audit_are_ready() -> None:
    gate = verify_s2_9_gate(ROOT)
    assert gate["ready"] is True
    assert gate["hashes"]["config"] == S29_EXPECTATIONS.config_sha256
    assert gate["hashes"]["manifest"] == S29_EXPECTATIONS.manifest_sha256
    assert gate["exact_model_id"] == "gpt-4.1-2025-04-14"
    assert gate["repeat_count"] == 5
    assert gate["hard_call_limit"] == 750
    assert gate["real_llm_authorized"] is False
    status = collect_status()
    assert status["s2_9_verified"] is True
    audit = collect_project_audit()
    assert audit["s2_9_verified"] is True
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert "s2_9_d1_preregistration_verified" in pass_codes

# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


runner = _load(
    "run_d1_prompt_factorial_ablation_v2_test",
    SCRIPTS / "run_d1_prompt_factorial_ablation_v2.py",
)
builder = _load(
    "build_d1_prompt_factorial_arms_v2_test",
    SCRIPTS / "build_d1_prompt_factorial_arms_v2.py",
)
results_builder = _load(
    "build_d1_prompt_factorial_results_v1_test",
    SCRIPTS / "build_d1_prompt_factorial_results_v1.py",
)


def _source_examples() -> str:
    raw = builder.SOURCE.read_text(encoding="utf-8")
    return raw[raw.index("## Examples"):raw.index("## Notes")]


def test_three_clean_arms_and_fixed_450_plan():
    assert runner.ARMS == (
        "D-no-semantic-examples-0813",
        "D-no-semantic-guidance-0813",
        "D-no-explicit-json-contract-0813",
    )
    plan = runner.build_execution_plan()
    assert len(plan) == 3
    assert sum(row["calls"] for row in plan) == 450
    assert all(row["baseline_reused"] == "D-full-0813" for row in plan)


def test_prompt_manifest_binds_frozen_parent_and_six_examples():
    manifest = json.loads(runner.PROMPT_MANIFEST.read_text(encoding="utf-8"))
    source_sha = hashlib.sha256(builder.SOURCE.read_bytes()).hexdigest()
    assert manifest["baseline"] == {
        "arm": "D-full-0813",
        "path": (
            "prompts/sun_compat/"
            "direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md"
        ),
        "sha256": source_sha,
        "semantic_example_count": 6,
    }
    assert set(manifest["arms"]) == set(runner.ARMS)
    assert all(row["source_prompt_sha256"] == source_sha
               for row in manifest["arms"].values())


def test_no_semantic_examples_keeps_interface_without_semantic_pairs():
    from bpc_hybrid.prompt_loader import load_prompt
    prompt = load_prompt(runner.PROMPT_NAMES[
        "D-no-semantic-examples-0813"])
    assert prompt.few_shot_examples == []
    assert "Structural output template (no semantic examples)" in (
        prompt.system_prompt)
    assert '"clause_span": {"text": "<exact substring>"' in (
        prompt.system_prompt)
    assert "Example 1" not in prompt.system_prompt
    assert "There are no semantic input-output" in prompt.user_prompt_template
    # Full semantic guidance remains.
    assert "9. modality is one of" in prompt.system_prompt
    assert "27. condition covers" in prompt.system_prompt


def test_no_semantic_guidance_removes_only_declared_rule_family():
    from bpc_hybrid.prompt_loader import load_prompt
    prompt = load_prompt(runner.PROMPT_NAMES[
        "D-no-semantic-guidance-0813"])
    assert len(prompt.few_shot_examples) == 6
    for number in list(range(9, 20)) + [25, 26, 27]:
        assert f"{number}. " not in prompt.system_prompt
    for number in list(range(1, 9)) + list(range(20, 25)):
        assert f"{number}. " in prompt.system_prompt
    assert "Six-element semantics:" not in prompt.system_prompt
    assert "Missing, uncertain, passive" not in prompt.system_prompt
    assert "Field-typing precision" not in prompt.system_prompt
    raw = runner.prompt_path("D-no-semantic-guidance-0813").read_text(
        encoding="utf-8")
    assert _source_examples() in raw


def test_no_explicit_json_contract_retains_semantics_and_examples():
    from bpc_hybrid.prompt_loader import load_prompt
    prompt = load_prompt(runner.PROMPT_NAMES[
        "D-no-explicit-json-contract-0813"])
    assert len(prompt.few_shot_examples) == 6
    assert "Return ONLY one valid JSON object" not in prompt.system_prompt
    assert "Use exactly these top-level keys" not in prompt.system_prompt
    assert "stage2_prediction.schema.json@1.0.0" not in (
        prompt.system_prompt.split("Input and inference boundary:", 1)[0])
    assert "9. modality is one of" in prompt.system_prompt
    assert "25. constraint covers" in prompt.system_prompt
    raw = runner.prompt_path("D-no-explicit-json-contract-0813").read_text(
        encoding="utf-8")
    assert _source_examples() in raw
    assert "Return the extraction result." in prompt.user_prompt_template


def test_rendered_arms_use_same_sample_envelope():
    sid = "sample-x"
    text = "The controller shall act."
    rendered = {arm: runner.render_prompt(arm, sid, text)
                for arm in runner.ARMS}
    for system, user in rendered.values():
        assert sid in user
        assert text in user
        assert system
    assert "Structural output template" in rendered[
        "D-no-semantic-examples-0813"][0]
    assert "Example 1" not in rendered[
        "D-no-semantic-examples-0813"][1]
    assert "Example 1" in rendered[
        "D-no-semantic-guidance-0813"][1]
    assert "Example 1" in rendered[
        "D-no-explicit-json-contract-0813"][1]


def test_dry_run_is_zero_network_and_derived_counts():
    report = runner.dry_run()
    assert report["planned_calls"] == 450
    assert report["llm_api_calls"] == 0
    assert report["network_calls"] == 0
    assert sum(row["sample_count"] for row in report["arms"].values()) == 450
    total, per_arm = runner.estimate_rendered_input_tokens()
    assert report["estimated_input_tokens"] == total
    assert {arm: row["estimated_input_tokens"]
            for arm, row in report["arms"].items()} == per_arm


def test_contract_is_valid_but_unauthorized_and_hash_bound():
    contract = runner.validate_contract(allow_unauthorized=True)
    assert contract["authorization"] is None
    assert contract["execution_plan"]["total_calls"] == 450
    assert contract["budget"]["planned_calls"] == 450
    assert contract["budget"]["usd_cost_cap"] == pytest.approx(13.430)
    assert contract["budget"]["cny_off_peak_envelope"] == pytest.approx(45.79)
    with pytest.raises(runner.ContractError, match="450-call batch"):
        runner.validate_contract()


def test_nested_contract_drift_rejected_before_execution(tmp_path):
    contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))
    broken = copy.deepcopy(contract)
    broken["execution_plan"]["arms"][0]["calls"] = 149
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    with pytest.raises(runner.ContractError, match="schema validation"):
        runner.validate_contract(path, allow_unauthorized=True)


class _OneShotTransport:
    def __init__(self):
        self.calls = 0
        self.last_decode = {}

    def send(self, request):
        from bpc_hybrid.llm_client import LLMResponse
        self.calls += 1
        self.last_decode = {
            "status": "ok_message_content",
            "request_id": "fake-request-1",
            "model": "deepseek-v4-pro",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        return LLMResponse(content="{}")


def test_call_once_sends_exactly_once_and_binds_returned_usage():
    contract = runner.validate_contract(allow_unauthorized=True)
    gate = runner.base.DeBudgetGate(contract)
    transport = _OneShotTransport()
    row = runner._call_once(
        runner.ARMS[0],
        {"sample_id": "s1", "text": "A must act."},
        transport,
        lambda usage: 0.01,
        gate,
    )
    assert transport.calls == 1
    assert gate.calls_made == 1
    assert row["network_call"] == 1
    assert row["request_id"] == "fake-request-1"
    assert row["returned_model"] == "deepseek-v4-pro"
    assert row["usage"]["total_tokens"] == 15


def test_schema_rejects_authorized_event_shape_with_extra_key(tmp_path):
    contract = json.loads(runner.CONTRACT_PATH.read_text(encoding="utf-8"))
    contract["authorization"] = {
        "authorization_sentence_utf8_sha256": "0" * 64,
        "authorization_event_file": "outputs/reports/x.json",
        "authorization_event_file_sha256": "0" * 64,
        "authorized_at_utc": "2026-08-30T00:00:00Z",
        "execution_window": "beijing_off_peak_only",
        "unexpected": True,
    }
    path = tmp_path / "bad-auth.json"
    path.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(runner.ContractError, match="schema validation"):
        runner.validate_contract(path, allow_unauthorized=True)


def test_result_table_refuses_missing_or_incomplete_execution(
        tmp_path, monkeypatch):
    monkeypatch.setattr(results_builder, "NEW_DIR", tmp_path)
    monkeypatch.setattr(results_builder, "OUT_JSON", tmp_path / "report.json")
    monkeypatch.setattr(results_builder, "OUT_MD", tmp_path / "report.md")
    with pytest.raises(RuntimeError, match="has not run"):
        results_builder.build()
    (tmp_path / "execution_summary.json").write_text(
        json.dumps({"complete": False, "completed_samples": 449,
                    "aborted": False}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="incomplete or aborted"):
        results_builder.build()

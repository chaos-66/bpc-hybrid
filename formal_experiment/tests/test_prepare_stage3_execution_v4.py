"""Frozen request/input checks; never make API calls or launch the B0 runtime."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_stage3_v4", ROOT / "scripts/prepare_stage3_execution_v4.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


def test_frozen_requests_contain_only_source_and_original_recipe():
    requests = prepare.request_bodies()
    assert len(requests) == 5
    for source, body in requests:
        assert body["model"] == "deepseek-v4-pro"
        assert body["temperature"] == 0
        assert body["top_p"] == 1
        assert body["max_tokens"] == 4096
        assert body["stream"] is False
        assert body["thinking"] == {"type": "disabled"}
        assert "tools" not in body and "response_format" not in body
        assert source["approved_text_en"] in body["messages"][1]["content"]
        assert source["sample_id"] in body["messages"][1]["content"]
        for forbidden in ("case_", "reference_states", "wrong_executor", "mandatory_task_index"):
            assert forbidden not in json.dumps(body)


def test_input_drift_refused_before_runtime(monkeypatch, tmp_path):
    changed = tmp_path / "changed.json"
    changed.write_text('{}', encoding="utf-8")
    monkeypatch.setattr(prepare, "INPUT", changed)
    with pytest.raises(ValueError, match="input hash drift"):
        prepare.load_inputs()


def test_existing_prediction_directory_refused_before_launch(monkeypatch, tmp_path):
    monkeypatch.setattr(prepare, "B0_OUT", tmp_path)
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        prepare.run_b0()


def test_preflight_is_not_authorization_and_distinguishes_proxy_budget():
    preflight = prepare.build_preflight()
    assert preflight["authorized"] is False
    assert preflight["calls_made"] == 0 and preflight["retry_cap"] == 0
    assert preflight["recommended_authorization_hard_caps"] == {
        "calls": 5, "retries": 0, "total_input_tokens": 5_000_000,
        "total_output_tokens": 20_480, "usd_peak_including_20_percent_margin": 8.02}
    assert preflight["planning_estimate"]["not_actual_bill_or_provider_tokenizer"]
    assert preflight["execution_blockers"]

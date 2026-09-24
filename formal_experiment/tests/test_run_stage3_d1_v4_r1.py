# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_stage3_d1_v4_r1 as runner


def test_preflight_body_encoding_is_default_json_dumps() -> None:
    body = {"model": "m", "messages": [{"role": "user", "content": "caf\u00e9"}]}
    encoded = runner._encode_preflight_body(body)
    assert encoded == json.dumps(body).encode("utf-8")
    assert b"caf\\u00e9" in encoded


def test_transport_request_data_uses_preflight_bytes(monkeypatch) -> None:
    body = {"model": "m", "messages": [{"role": "user", "content": "caf\u00e9"}]}
    expected = runner._encode_preflight_body(body)
    seen: dict[str, bytes] = {}
    response_raw = json.dumps({
        "id": "x", "object": "chat.completion", "model": runner.MODEL,
        "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }).encode("utf-8")

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return response_raw

    def fake_urlopen(request, timeout=None):
        seen["data"] = bytes(request.data)
        return FakeResponse()

    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)
    transport = runner.FrozenBodyHttpTransport(api_key="test-key")
    result = transport.send(body, runner._sha_bytes(expected), len(expected))
    assert seen["data"] == expected
    assert result["http_status"] == 200


def test_api_key_alias_priority(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-key")
    monkeypatch.setenv("BPC_HYBRID_DeepSeek_API_KEY", "bpc-deepseek-key")
    monkeypatch.setenv("BPC_HYBRID_LLM_API_KEY", "bpc-llm-key")
    assert runner._env_api_key() == "deepseek-key"


def test_body_hash_intercept_before_network() -> None:
    transport = runner.FrozenBodyHttpTransport(api_key="test-key")
    with pytest.raises(runner.D1RunError):
        transport.send({"model": runner.MODEL}, "0" * 64)


def test_r1_inference_load_inputs_does_not_open_construction_reference(monkeypatch) -> None:
    import run_stage3_table3_v4_r1 as matrix_runner

    original_sha = matrix_runner._sha_file
    original_load = matrix_runner._load_json
    touched: list[str] = []

    def spy_sha(path):
        touched.append(Path(path).resolve().as_posix())
        if Path(path).name == "construction_reference.json":
            raise AssertionError("inference hash loop opened construction_reference.json")
        return original_sha(path)

    def spy_load(path):
        touched.append(Path(path).resolve().as_posix())
        if Path(path).name == "construction_reference.json":
            raise AssertionError("inference loader opened construction_reference.json")
        return original_load(path)

    monkeypatch.setattr(matrix_runner, "_sha_file", spy_sha)
    monkeypatch.setattr(matrix_runner, "_load_json", spy_load)
    loaded = matrix_runner.load_inputs()
    assert len(loaded["items"]) == 20
    assert all(not path.endswith("construction_reference.json") for path in touched)

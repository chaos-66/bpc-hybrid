# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_stage3_d1_v4 as runner
from bpc_hybrid.h1_transport import decode_chat_completion_envelope


def _rows() -> list[dict]:
    rows = []
    for index, sample_id in enumerate(runner.SAMPLE_IDS, start=1):
        body = {
            "model": runner.MODEL,
            "messages": [{"role": "user", "content": sample_id}],
            "max_tokens": runner.MAX_OUTPUT_TOKENS,
            "temperature": 0,
            "top_p": 1,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        raw = json.dumps(body).encode("utf-8")
        rows.append({
            "index": index,
            "sample_id": sample_id,
            "source_text": f"source {sample_id}",
            "source_text_sha256": hashlib.sha256(f"source {sample_id}".encode("utf-8")).hexdigest(),
            "body": body,
            "body_sha256": hashlib.sha256(raw).hexdigest(),
            "body_bytes": len(raw),
        })
    return rows


def _preflight() -> dict:
    return {
        "planned_calls": 5,
        "retry_cap": 0,
        "method": {"model": runner.MODEL},
        "price_snapshot": {"source": "test"},
    }


class _SuccessTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, body, expected_body_sha256, expected_body_bytes):
        self.calls += 1
        raw = json.dumps({
            "id": "x", "object": "chat.completion", "model": runner.MODEL,
            "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
        }).encode("utf-8")
        return {
            "http_status": 200,
            "content_type": "application/json",
            "raw_response_body": raw,
            "decode": decode_chat_completion_envelope(raw, "application/json"),
            "elapsed_seconds": 0.01,
        }


class _FailOnceTransport:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, body, expected_body_sha256, expected_body_bytes):
        self.calls += 1
        raise runner.D1RunError("simulated transport failure")


def _patch_preconditions(monkeypatch, rows) -> None:
    monkeypatch.setattr(runner, "verify_authorization", lambda: {"status": "authorized"})
    monkeypatch.setattr(runner, "verify_preflight_and_bodies", lambda: (_preflight(), rows))
    monkeypatch.setattr(runner, "convert_response_content",
                        lambda **kwargs: {"sample_id": kwargs["sample_id"],
                                          "request_status": "ok", "record": {},
                                          "error_category": None})


def test_five_call_cap_happy_path(tmp_path, monkeypatch) -> None:
    rows = _rows()
    _patch_preconditions(monkeypatch, rows)
    transport = _SuccessTransport()
    manifest = runner.execute(out_dir=tmp_path / "run", transport=transport)
    assert transport.calls == 5
    assert manifest["counts"]["attempted"] == 5
    assert manifest["counts"]["completed"] == 5
    assert manifest["status"] == "complete"


def test_failure_does_not_retry_or_resend_after_restart(tmp_path, monkeypatch) -> None:
    rows = _rows()
    _patch_preconditions(monkeypatch, rows)
    transport = _FailOnceTransport()
    manifest = runner.execute(out_dir=tmp_path / "run", transport=transport)
    assert transport.calls == 1
    assert manifest["counts"]["failed"] == 1
    with pytest.raises(runner.D1RunError):
        runner.execute(out_dir=tmp_path / "run", transport=_SuccessTransport())


def test_over_budget_pre_dispatch_does_not_call_transport(tmp_path, monkeypatch) -> None:
    rows = _rows()
    _patch_preconditions(monkeypatch, rows)
    monkeypatch.setattr(runner, "TOTAL_BUDGET_USD", 0.0)
    transport = _SuccessTransport()
    manifest = runner.execute(out_dir=tmp_path / "run", transport=transport)
    assert transport.calls == 0
    assert manifest["counts"]["failed"] == 1


def test_body_hash_intercept_before_network() -> None:
    transport = runner.FrozenBodyHttpTransport(api_key="test-key")
    with pytest.raises(runner.D1RunError):
        transport.send({"model": runner.MODEL}, "0" * 64)


def test_response_identity_binding_failure() -> None:
    content = json.dumps({"sample_id": "wrong", "source_id": "expected", "source_text": "abc"})
    result = runner.convert_response_content(
        sample_id="expected", source_text="abc", content=content, call_meta={})
    assert result["request_status"] == "failed"
    assert result["failure_stage"] == "input_binding"
    assert result["error_category"] == "input_binding_failed"
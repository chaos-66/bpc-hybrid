# -*- coding: utf-8 -*-
"""Focused zero-API recovery tests for SEP-C3 condition preservation."""

from __future__ import annotations

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

import analyze_sep_c3_condition_preservation_bootstrap_v1 as bs  # noqa: E402
import run_sep_c3_condition_preservation_v1 as runner  # noqa: E402
from bpc_hybrid.llm_client import LLMResponse  # noqa: E402


class RecordingFakeTransport:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.last_decode = None

    def send(self, request):
        self.sent.append((request.source_id, request.source_text))
        payload = {
            "schema_version": "1.0.0",
            "sample_id": request.source_id,
            "source_id": request.source_id,
            "source_text": request.source_text,
            "clauses": [],
            "method": {
                "name": "direct_llm",
                "schema_source": "stage2_prediction.schema.json@1.0.0",
            },
            "validation": {
                "schema_valid": True,
                "cross_field_valid": True,
                "errors": [],
            },
            "unsupported_or_ambiguous": [],
        }
        self.last_decode = {
            "status": "ok_message_content",
            "usage": {
                "prompt_tokens": 40,
                "completion_tokens": 8,
                "total_tokens": 48,
            },
            "model": "deepseek-v4-pro",
            "response_id": f"fake-recovery-{len(self.sent)}",
            "finish_reason": "stop",
        }
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            provider="mock",
            model="deepseek-v4-pro",
            finish_reason="stop",
        )


def _fake_content(sid: str, text: str) -> str:
    return json.dumps({
        "schema_version": "1.0.0",
        "sample_id": sid,
        "source_id": sid,
        "source_text": text,
        "clauses": [],
        "method": {
            "name": "direct_llm",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {
            "schema_valid": True,
            "cross_field_valid": True,
            "errors": [],
        },
        "unsupported_or_ambiguous": [],
    }, ensure_ascii=False)


def _raw_row(entry: dict, text: str) -> dict:
    content = _fake_content(str(entry["sample_id"]), text)
    return {
        "suite_id": runner.SUITE_ID,
        "sample_id": entry["sample_id"],
        "arm": entry["arm"],
        "repeat_id": runner.REPEAT_ID,
        "execution_index": entry["execution_index"],
        "arm_order_within_sample": entry["arm_order_within_sample"],
        "attempt_index": entry["execution_index"] + 1,
        "timestamp_utc": "2026-09-19T12:54:00+00:00",
        "completed_at_utc": "2026-09-19T12:54:01+00:00",
        "request_id": f"fake-{entry['execution_index']}",
        "request_body_sha256": "fake-body-sha",
        "transport_request_body_sha256": None,
        "raw_response_content": content,
        "raw_model_output": content,
        "response_sha256": runner._sha256_text(content),
        "raw_output_sha256": runner._sha256_text(content),
        "bare_json_status": "bare_json_object",
        "usage": {
            "prompt_tokens": 40,
            "completion_tokens": 8,
            "total_tokens": 48,
        },
        "cost": {
            "input_tokens": 40,
            "output_tokens": 8,
            "cache_hit_tokens": 0,
            "cache_miss_tokens": 40,
            "cost_usd": 0.00005808,
            "basis": "conservative_all_input_cache_miss",
        },
        "cost_usd": 0.00005808,
        "rate_window": "off_peak",
        "transport_status": "ok",
        "api_call_status": "ok",
        "request_status": "ok",
        "decode_status": "ok_message_content",
        "finish_reason": "stop",
        "returned_model": "deepseek-v4-pro",
        "model": "deepseek-v4-pro",
        "documented_release": runner.MODEL_RELEASE,
        "sampling_parameters": {
            "temperature": 0.0,
            "top_p": 1.0,
            "max_tokens": 4096,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "error": None,
        "gate_error": None,
        "network_call": 1,
    }


def _write_synthetic_recovery_state(out_dir: Path) -> None:
    schedule = runner._load_schedule(runner.SCHEDULE_PATH)
    input_rows = runner._input_rows()
    text_by_id = {str(row["sample_id"]): str(row["text"]) for row in input_rows}
    for entry in schedule["entries"][:96]:
        arm = str(entry["arm"])
        sid = str(entry["sample_id"])
        run_dir = out_dir / arm / runner.REPEAT_ID
        run_dir.mkdir(parents=True, exist_ok=True)
        body = runner._request_body(arm, sid, text_by_id[sid])
        attempt = {
            "suite_id": runner.SUITE_ID,
            "sample_id": sid,
            "arm": arm,
            "repeat_id": runner.REPEAT_ID,
            "execution_index": entry["execution_index"],
            "arm_order_within_sample": entry["arm_order_within_sample"],
            "attempt_index": entry["execution_index"] + 1,
            "state": "attempt_started",
            "timestamp_utc": "2026-09-19T12:54:00+00:00",
            "request_body_sha256": runner._body_sha256(body),
            "expected_transport_request_body_sha256": None,
            "system_prompt_sha256": runner._sha256_text(
                runner._prompt(arm).system_prompt
            ),
            "user_prompt_sha256": runner._sha256_text(
                runner._prompt(arm).render_user(sid, text_by_id[sid])
            ),
            "prompt_composition_sha256": runner._prompt(arm).composition_sha256,
            "estimated_input_tokens_bytes_div_3": runner._estimated_input_tokens(
                body
            ),
            "max_tokens": 4096,
            "model": runner.MODEL_ALIAS,
            "documented_release": runner.MODEL_RELEASE,
        }
        _append = (run_dir / "attempts.jsonl").open("a", encoding="utf-8", newline="\n")
        with _append:
            _append.write(json.dumps(attempt, ensure_ascii=False) + "\n")
        if not (arm == "RC1" and sid == "estg_000074"):
            with (run_dir / "raw_responses.jsonl").open(
                "a", encoding="utf-8", newline="\n"
            ) as handle:
                handle.write(
                    json.dumps(_raw_row(entry, text_by_id[sid]), ensure_ascii=False)
                    + "\n"
                )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_unregistered_in_doubt_refuses_before_transport(tmp_path: Path):
    out = tmp_path / "unregistered"
    _write_synthetic_recovery_state(out)
    called = {"count": 0}

    def forbidden():
        called["count"] += 1
        raise AssertionError("transport must not be created without recovery registration")

    with pytest.raises(runner.ConditionPreservationRunError, match="in_doubt"):
        runner.execute(
            transport_factory=forbidden,
            out_dir=out,
            enforce_off_peak=False,
        )
    assert called["count"] == 0


def test_registered_recovery_sends_only_remaining_and_builds_150_envelopes(
    tmp_path: Path,
):
    out = tmp_path / "recovered"
    _write_synthetic_recovery_state(out)
    transport = RecordingFakeTransport()
    result = runner.execute(
        transport_factory=lambda: transport,
        out_dir=out,
        recovery_contract_path=runner.RECOVERY_CONTRACT_PATH,
        recovery_ledger_path=runner.RECOVERY_LEDGER_PATH,
        result_writer=lambda _: None,
        enforce_off_peak=False,
    )
    assert result["complete"] is True
    assert result["completion_state"] == "completed_with_unresolved_response"
    assert result["actual_calls"] == 450
    assert result["known_responses"] == 449
    assert result["unknown_response_count"] == 1
    assert len(transport.sent) == 354
    schedule = runner._load_schedule(runner.SCHEDULE_PATH)
    attempted_keys = {
        (str(e["arm"]), str(e["sample_id"]))
        for e in schedule["entries"][:96]
    }
    sent_ids = {sid for sid, _text in transport.sent}
    attempted_sids = {sid for (_arm, sid) in attempted_keys}
    assert sent_ids.isdisjoint(attempted_sids)
    assert result["budget_gate"]["calls_attempted"] == 450
    assert result["budget_gate"]["reserved_output_tokens"] == 450 * 4096
    for arm in runner.ARMS:
        rows = _read_jsonl(
            out / arm / runner.REPEAT_ID / "canonical_predictions.jsonl"
        )
        assert len(rows) == 150
    rc1_rows = _read_jsonl(out / "RC1" / runner.REPEAT_ID / "canonical_predictions.jsonl")
    unknown = [
        row for row in rc1_rows if row["sample_id"] == "estg_000074"
    ][0]
    assert unknown["request_status"] == "failed"
    assert unknown["api_call_status"] == "unknown"
    assert unknown["record"] == {}
    assert unknown["response_unknown"] is True

    bootstrap = bs.analyze(
        base_path=out / "BASE" / runner.REPEAT_ID / "canonical_predictions.jsonl",
        rc1_path=out / "RC1" / runner.REPEAT_ID / "canonical_predictions.jsonl",
        rc_keep_path=out / "RC_KEEP" / runner.REPEAT_ID / "canonical_predictions.jsonl",
        output_path=out / "bootstrap.json",
    )
    assert bootstrap["denominator_per_arm"] == {
        "BASE": 150,
        "RC1": 150,
        "RC_KEEP": 150,
    }
    sensitivity = bs.analyze_missing_sensitivity(
        base_path=out / "BASE" / runner.REPEAT_ID / "canonical_predictions.jsonl",
        rc1_path=out / "RC1" / runner.REPEAT_ID / "canonical_predictions.jsonl",
        rc_keep_path=out / "RC_KEEP" / runner.REPEAT_ID / "canonical_predictions.jsonl",
        excluded_sample_id="estg_000074",
        output_path=out / "sensitivity.json",
    )
    assert sensitivity["denominator_per_arm"] == {
        "BASE": 149,
        "RC1": 149,
        "RC_KEEP": 149,
    }
    assert all(
        len(comparison["difference_values"]) == 10000
        for comparison in sensitivity["bootstrap"]["comparisons"].values()
    )

    # A second execution after completion must not send anything.
    no_send = RecordingFakeTransport()
    second = runner.execute(
        transport_factory=lambda: no_send,
        out_dir=out,
        recovery_contract_path=runner.RECOVERY_CONTRACT_PATH,
        recovery_ledger_path=runner.RECOVERY_LEDGER_PATH,
        result_writer=lambda _: None,
        enforce_off_peak=False,
    )
    assert second["complete"] is True
    assert len(no_send.sent) == 0
    assert second["new_sends_per_arm"] == {"BASE": 0, "RC1": 0, "RC_KEEP": 0}


def test_stale_lock_is_removed_only_for_dead_pid(tmp_path: Path):
    lock_path = tmp_path / ".run.lock"
    lock_path.write_text(
        json.dumps({"pid": 99999999, "suite_id": runner.SUITE_ID}),
        encoding="utf-8",
    )
    with runner.RunLock(lock_path):
        assert lock_path.is_file()
        content = json.loads(lock_path.read_text(encoding="utf-8"))
        assert content["pid"] != 99999999
    assert not lock_path.exists()

    lock_path.write_text(
        json.dumps({"pid": __import__("os").getpid(), "suite_id": runner.SUITE_ID}),
        encoding="utf-8",
    )
    with pytest.raises(runner.ConditionPreservationRunError, match="live PID"):
        with runner.RunLock(lock_path):
            pass


def test_recovery_contract_budget_drift_is_rejected(tmp_path: Path):
    contract = json.loads(
        runner.RECOVERY_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract["usd_cost_cap"] = 11.0
    bad = tmp_path / "bad_recovery_contract.json"
    bad.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
    schedule = runner._load_schedule(runner.SCHEDULE_PATH)
    report = runner.validate_recovery_contract(
        recovery_contract_path=bad,
        recovery_ledger_path=runner.RECOVERY_LEDGER_PATH,
        schedule=schedule,
    )
    assert report["status"] == "fail"
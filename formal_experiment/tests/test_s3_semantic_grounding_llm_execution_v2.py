# -*- coding: utf-8 -*-
"""Focused offline tests for the resumable v2 LLM execution state machine."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    LLMGroundingExecutionError,
    PreSendTransportError,
    build_request_set,
    execute_fallback,
)
from bpc_hybrid.s3_semantic_grounding_v4 import build_fallback_pack  # noqa: E402

TYPES = [
    "prohibited_action_present",
    "required_condition_not_enforced",
    "constraint_violated",
    "exception_not_handled",
]


def _temp_root() -> Path:
    base = ROOT / ".tmp_execution_tests" / uuid.uuid4().hex
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _row(index: int) -> dict:
    checks = {
        target: {"status": "not_applicable", "observable": True,
                  "violation": False, "reason": "empty_rule_field"}
        for target in TYPES
    }
    checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "action_grounding_unresolved",
    }
    return {
        "item_id": f"item-{index}",
        "side": "variant",
        "process_id": "p",
        "rule_id": "r",
        "expected_label": "required_condition_not_enforced",
        "predicted_violation_type": None,
        "decision": {"predicted": None, "decision": "abstention"},
        "checks": checks,
        "action_grounding": {
            "schema": "s3_semantic_grounding_action@1.0.0",
            "status": "unresolved", "reason": "test_stub",
            "activity_id": None, "candidate_activity_ids": ["A2"],
            "candidates": [{"activity_id": "A2", "label": f"notify subject {index}",
                             "owners": [], "similarity": 0.9,
                             "lexical_coverage": 0.9}],
            "alternatives": [],
        },
        "model_visible_rule_input": {
            "rule_id": "r", "sentence_idx": 0, "modality": "obligation",
            "actor": "controller", "action": f"notify subject {index}",
            "condition": f"consent obtained {index}", "constraint": None,
            "exception": None,
        },
        "canonical_rule_input_hash": "rule",
        "canonical_process_input_hash": "process",
        "bpmn_sha256": "bpmn",
        "compact_local_context": {
            "candidate_activities": [
                {"activity_id": "A2", "label": f"notify subject {index}", "owners": [],
                 "similarity": 0.9, "lexical_coverage": 0.9},
            ],
            "nodes": [{"id": "A2", "kind": "activity", "label": f"notify subject {index}"}],
            "sequence_flows": [],
            "condition_evidence": [],
            "constraint_bound_evidence": [],
            "constraint_unbound_evidence": [],
            "exception_handler_candidates": [],
            "evidence_ids": [],
        },
        "control_global_compliance": None,
        "fallback_triggers": [],
    }


def _setup(count: int = 1) -> tuple[dict, dict, dict]:
    pack = build_fallback_pack([_row(index) for index in range(count)])
    config = {"model": "fake-model", "max_output_tokens_per_call": 64,
              "temperature": 0.0, "top_p": 1.0}
    return pack, build_request_set(pack, config), config


def _valid_response(item: dict) -> str:
    candidate_ids = item["llm_visible_payload"].get("candidate_activity_ids") or []
    action_id = candidate_ids[0] if candidate_ids else None
    response = {
        "action_grounding": {
            "status": "matched" if action_id else "ambiguous",
            "activity_id": action_id,
            "confidence": 0.9,
        },
        "condition": {"status": "ambiguous", "evidence_ids": [], "confidence": 0.0},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    return json.dumps(response, ensure_ascii=False)


def _raw(content: str, *, usage: dict | None = None) -> dict:
    raw = {"content": content, "provider": "fake", "model": "fake",
           "finish_reason": "stop"}
    if usage is not None:
        raw["usage"] = usage
    return raw


class ScriptedTransport:
    def __init__(self, scripts: list):
        self.scripts = list(scripts)
        self.calls: list[str] = []

    def complete(self, request):
        self.calls.append(str(request.get("request_sha256")))
        if not self.scripts:
            raise RuntimeError("scripted transport exhausted")
        script = self.scripts.pop(0)
        if isinstance(script, BaseException):
            raise script
        if callable(script):
            return script(request)
        return script


class ForbiddenTransport:
    def __init__(self):
        self.calls: list[str] = []

    def complete(self, request):
        self.calls.append(str(request.get("request_sha256")))
        raise AssertionError("transport must not be called")


def test_complete_run_then_resume_loads_all_history():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(2)
        first = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock",
            transport=ScriptedTransport([
                _raw(_valid_response(pack["items"][0])),
                _raw(_valid_response(pack["items"][1])),
            ]))
        assert first["run_status"] == "complete"
        assert first["counts"]["succeeded"] == 2
        assert len(first["results"]) == 2
        assert first["total_input_tokens_actual"] > 0

        second_transport = ForbiddenTransport()
        second = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=second_transport)
        assert second_transport.calls == []
        assert second["run_status"] == "complete"
        assert second["counts"]["skipped_resume_protected"] == 2
        assert second["counts"]["resumed_from_store"] == 2
        assert len(second["results"]) == 2
        assert all(result["recovered_from_store"] for result in second["results"])
        assert second["total_input_tokens_actual"] > 0
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_malformed_and_rejected_are_terminal_and_not_resent():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(2)
        first = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock",
            transport=ScriptedTransport([
                _raw("{not json"),
                _raw(json.dumps({"unexpected": -1})),
            ]))
        # The second response is valid JSON but the wrong schema.
        assert first["counts"]["malformed"] == 1
        assert first["counts"]["rejected_by_validator"] == 1
        assert first["run_status"] == "failed"

        second_transport = ForbiddenTransport()
        second = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=second_transport)
        assert second_transport.calls == []
        assert second["counts"]["skipped_resume_protected"] == 2
        assert second["counts"]["malformed"] == 1
        assert second["counts"]["rejected_by_validator"] == 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_generic_transport_failure_is_in_doubt_and_halts_remaining_sends():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(3)
        transport = ScriptedTransport([RuntimeError("network lost")])
        first = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=transport)
        assert len(transport.calls) == 1
        assert first["counts"]["in_doubt"] == 1
        assert first["counts"]["send_attempts"] == 1
        assert first["run_status"] == "failed"

        second_transport = ForbiddenTransport()
        second = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=second_transport)
        assert second_transport.calls == []
        assert second["counts"]["in_doubt"] == 1
        assert second["counts"]["pre_send_blocked"] == 2
        assert second["known_usage_complete"] is False
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_pre_send_failure_is_retried_on_a_later_run_only_when_not_sent():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(1)
        first_transport = ScriptedTransport([PreSendTransportError("local gate")])
        first = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=first_transport)
        assert len(first_transport.calls) == 1
        assert first["counts"]["pre_send_failed"] == 1
        assert first["run_status"] == "blocked"

        retry_transport = ScriptedTransport([_raw(_valid_response(pack["items"][0]))])
        second = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=retry_transport)
        assert len(retry_transport.calls) == 1
        assert second["run_status"] == "complete"
        assert second["counts"]["succeeded"] == 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_max_calls_and_off_peak_windows_block_before_send():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(1)
        config_max_calls = {**config, "max_calls": 0}
        transport = ForbiddenTransport()
        result = execute_fallback(
            pack=pack, request_set=request_set, config=config_max_calls,
            output_root=base, mode="mock", transport=transport)
        assert transport.calls == []
        assert result["run_status"] == "blocked"
        assert result["counts"]["pre_send_blocked"] == 1

        base2 = _temp_root()
        try:
            config_off_peak = {
                **config,
                "off_peak_only": True,
                "off_peak_start_hour_utc": 0,
                "off_peak_end_hour_utc": 6,
            }
            transport2 = ForbiddenTransport()
            result2 = execute_fallback(
                pack=pack, request_set=request_set, config=config_off_peak,
                output_root=base2, mode="mock", transport=transport2,
                now_utc_fn=lambda: datetime(2026, 1, 1, 12, 0,
                                            tzinfo=timezone.utc))
            assert transport2.calls == []
            assert result2["run_status"] == "blocked"
            assert result2["counts"]["pre_send_blocked"] == 1
        finally:
            shutil.rmtree(base2, ignore_errors=True)
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_actual_usage_is_saved_and_reused_on_resume():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(1)
        transport = ScriptedTransport([
            _raw(_valid_response(pack["items"][0]),
                 usage={"prompt_tokens": 123, "completion_tokens": 45}),
        ])
        first = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=transport)
        assert first["total_input_tokens_actual"] == 123
        assert first["total_output_tokens_actual"] == 45
        assert first["known_usage_complete"] is True

        second_transport = ForbiddenTransport()
        second = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock", transport=second_transport)
        assert second_transport.calls == []
        assert second["total_input_tokens_actual"] == 123
        assert second["total_output_tokens_actual"] == 45
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_tampered_ledger_fails_closed_without_sending():
    base = _temp_root()
    try:
        pack, request_set, config = _setup(1)
        first = execute_fallback(
            pack=pack, request_set=request_set, config=config,
            output_root=base, mode="mock",
            transport=ScriptedTransport([_raw(_valid_response(pack["items"][0]))]))
        ledger = Path(first["ledger_path"])
        lines = ledger.read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[-1])
        record["state"] = "tampered"
        lines[-1] = json.dumps(record, ensure_ascii=False, sort_keys=True)
        ledger.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        with pytest.raises(LLMGroundingExecutionError):
            execute_fallback(
                pack=pack, request_set=request_set, config=config,
                output_root=base, mode="mock", transport=ForbiddenTransport())
    finally:
        shutil.rmtree(base, ignore_errors=True)

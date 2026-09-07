# -*- coding: utf-8 -*-
"""S2.12 API-arm finalization tests (zero network, zero LLM, zero Gold).

Covers:

* the shared conversion chain ``direct_content_to_attempt``
  (ok / code fence / non-JSON / forbidden content / empty content) and the
  fallback envelope parser shape contract;
* strict coordinate-only capsule records that never contain raw-text keys;
* finalizer validation semantics for an incomplete ledger and for missing /
  mis-laid-out raw response directories (pure helpers, no B0 replay);
* one full end-to-end fake ``direct_llm`` D-CAL -> D-REST chain (payload
  locked fake transport, live ledger + resume, raw capture) finalized into a
  temporary directory.  NOTE on the fixture: the payload-locked fake
  transport emits ``make_schema_valid_mock_response_json`` output, which is
  schema-valid for the *extraction* JSON schema (``schema_version 0.1.0``)
  but is NOT convertible by the canonical D1 relay chain the finalizer uses
  (it carries ``schema_version 0.1.0``, no top-level ``validation`` key and
  no ``clause_span``), so those rows come out as explicit
  ``canonical_validation_failed`` failures.  To exercise the full
  ok-conversion path end to end without changing shared code, the E2E test
  substitutes a transport that emits canonical-shape content
  (``schema_version 1.0.0``, ``clause_span``, top-level ``validation``) and
  asserts 36 all-ok text-free predictions; the explicit-failure behaviour of
  the stock mock is asserted separately at unit level.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
for entry in (str(WORKSPACE), str(ROOT), str(ROOT / "src"), str(ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import bpc_hybrid.s2_12_response_convert as rc  # noqa: E402
from bpc_hybrid.llm_client import (  # noqa: E402
    LLMClientError,
    LLMResponse,
    make_schema_valid_mock_response_json,
)
from bpc_hybrid.s2_12_execution import (  # noqa: E402
    REQUIRED_MODEL,
    ExecutionLedger,
    PayloadLockedFakeTransport,
    ledger_record,
)

RUNTIME_HOME = Path("D:/environment/stanford-corenlp-4.5.10")
RULES_ONLY_ORDER = [row["sample_id"] for row in json.loads(
    (ROOT / "data/predictions/s2_12_sun_rule_only_v1/predictions.json")
    .read_text(encoding="utf-8"))["records"]]
FORBIDDEN_TEXT_KEYS = {
    "text", "source_text", "approved_text_en", "normalized", "marker_surface",
}


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses with future annotations resolve
    spec.loader.exec_module(module)  #     against sys.modules[module.__name__]
    return module


def _scan_text_keys(value, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            here = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_TEXT_KEYS:
                hits.append(here)
            hits.extend(_scan_text_keys(child, here))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_scan_text_keys(item, f"{path}[{index}]"))
    return hits


def _fixture_content(source_id: str, source_text: str) -> str:
    """Deterministic canonical-shape direct content (schema 1.0.0)."""
    txt = source_text or ""
    record = {
        "schema_version": "1.0.0",
        "sample_id": source_id,
        "source_id": source_id,
        "source_text": txt,
        "clauses": [{
            "clause_id": "fixture.c1",
            "clause_span": {"text": txt, "start": 0, "end": len(txt)},
            "modality": {"label": "definition", "evidence": []},
            "actors": [], "actions": [], "conditions": [], "constraints": [],
            "exceptions": [], "actor_action_map": [], "order_relations": [],
        }],
        "method": {"name": "direct_llm",
                   "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True,
                       "errors": []},
    }
    return json.dumps(record)


class CanonicalContentFakeTransport(PayloadLockedFakeTransport):
    """Payload-locked fake transport emitting canonical-shaped content."""

    def send(self, request, *, ordinal: int = 1, clause_id=None):
        try:
            self._lock.verify(request, ordinal, clause_id=clause_id)
        except Exception as exc:  # S212ExecutionError -> LLMClientError
            raise LLMClientError(str(exc)) from exc
        usage = {"prompt_tokens": 120, "completion_tokens": 64,
                 "total_tokens": 184, "reasoning_tokens": 0}
        self.last_decode = {
            "status": "ok_message_content", "model": REQUIRED_MODEL,
            "usage": usage, "finish_reason": "stop",
        }
        content = _fixture_content(request.source_id, request.source_text)
        return LLMResponse(content=content, provider="fake",
                           model=REQUIRED_MODEL, finish_reason="stop")


# ---------------------------------------------------------------------------
# Unit: conversion chain
# ---------------------------------------------------------------------------


def test_direct_content_to_attempt_ok_and_fenced() -> None:
    source_id = "SIM_card_scenario/r10/v1"
    source_text = ("A subscriber may request a replacement SIM card at any "
                   "time during the billing cycle.")
    content = _fixture_content(source_id, source_text)
    ok = rc.direct_content_to_attempt(source_id, content, source_text)
    assert ok["request_status"] == "ok"
    assert ok["error_category"] is None
    assert ok["record"] is not None
    fenced = "```json\n" + content + "\n```"
    fenced_ok = rc.direct_content_to_attempt(source_id, fenced, source_text)
    assert fenced_ok["request_status"] == "ok"
    assert fenced_ok["error_category"] is None


def test_direct_content_to_attempt_failure_classes() -> None:
    source_id = "SIM_card_scenario/r10/v1"
    source_text = "A subscriber may request a replacement SIM card."
    bad = rc.direct_content_to_attempt(source_id, "not json at all", source_text)
    assert bad["request_status"] == "failed_parse"
    assert "non_json_content" in bad["error_category"]
    forbidden = rc.direct_content_to_attempt(
        source_id, json.dumps({"variant_id": "x", "note": "n"}), source_text)
    assert forbidden["request_status"] == "failed_parse"
    assert "forbidden_content_term" in forbidden["error_category"]
    empty = rc.direct_content_to_attempt(source_id, "   \n ", source_text)
    assert empty["request_status"] == "in_doubt"
    assert empty["error_category"] == "completed_without_content"


def test_mock_extraction_content_is_explicit_failure() -> None:
    """The stock schema-valid mock is 0.1.0-extraction-shaped and therefore
    converts to an explicit (never fabricated) failure row."""
    source_id = "SIM_card_scenario/r10/v1"
    source_text = "A subscriber may request a replacement SIM card."
    content = make_schema_valid_mock_response_json(source_text, source_id)
    attempt = rc.direct_content_to_attempt(source_id, content, source_text)
    assert attempt["request_status"] == "ok"      # response received
    assert attempt["record"] is None              # not convertible
    assert attempt["error_category"] == "canonical_validation_failed"


def test_sanitized_record_has_no_text_keys() -> None:
    source_id = "SIM_card_scenario/r10/v1"
    source_text = "A subscriber may request a replacement SIM card."
    content = _fixture_content(source_id, source_text)
    attempt = rc.direct_content_to_attempt(source_id, content, source_text)
    assert attempt["record"] is not None
    assert _scan_text_keys(attempt["record"]) == []


def test_fallback_envelope_shape_contract() -> None:
    with pytest.raises(rc.ResponseConvertError):
        rc.fallback_envelope_from_content("")
    with pytest.raises(rc.ResponseConvertError):
        rc.fallback_envelope_from_content("{not json")
    with pytest.raises(rc.ResponseConvertError):
        rc.fallback_envelope_from_content(json.dumps({"sample_id": "x"}))
    with pytest.raises(rc.ResponseConvertError):
        rc.fallback_envelope_from_content(
            json.dumps({"sample_id": "s", "clause_id": "c", "repair_fields": [],
                        "patches": "nope", "reason": "r"}))
    envelope = rc.fallback_envelope_from_content(json.dumps(
        {"sample_id": "s", "clause_id": "c", "repair_fields": ["modality"],
         "patches": {}, "reason": "r"}))
    assert envelope["sample_id"] == "s"


# ---------------------------------------------------------------------------
# Unit: finalizer validation helpers (no B0 replay)
# ---------------------------------------------------------------------------


def test_finalize_coverage_errors_on_incomplete_ledger(tmp_path) -> None:
    fin = _load("s212_finalize_direct", "scripts/finalize_s2_12_arm_v1.py")
    ledger_path = tmp_path / "ledger.jsonl"
    rec = ledger_record(
        stage_id="D-CAL", request_id="s1/-", payload_sha="a" * 64, ordinal=1,
        request_time_utc="2026-09-07T00:00:00+00:00", returned_model="deepseek-v4-pro",
        usage={"prompt_tokens": 120, "completion_tokens": 64, "total_tokens": 184},
        cumulative_usage={"input_tokens": 120, "output_tokens": 64,
                          "cache_hit_tokens": 0, "cache_miss_tokens": 120},
        per_call_cost={"cost_usd": 0.0}, cumulative_cost=0.0,
        response_content_sha="", decode_status="ok_message_content",
        accepted=None, prev_hash="",
    )
    ledger_path.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True)
                           + "\n", encoding="utf-8")
    ledger = ExecutionLedger(ledger_path)
    arm_rows = [{"request_body_sha256": "a" * 64},
                {"request_body_sha256": "b" * 64}]
    errors = fin.coverage_errors(arm_rows, ledger)
    assert errors and "arm incomplete" in errors[0]
    assert fin.coverage_errors([{"request_body_sha256": "a" * 64}], ledger) == []


def test_finalize_layout_errors_for_raw_dirs(tmp_path) -> None:
    fin = _load("s212_finalize_direct", "scripts/finalize_s2_12_arm_v1.py")
    errors = fin.layout_errors("direct_llm", [])
    assert errors and "raw directory count" in errors[0]
    cal = tmp_path / "cal"
    rest = tmp_path / "rest"
    cal.mkdir()
    rest.mkdir()
    (cal / "D-CAL.jsonl").write_text("", encoding="utf-8")
    errors = fin.layout_errors("direct_llm", [cal, rest])
    assert any("D-REST" in error for error in errors)
    (rest / "D-REST.jsonl").write_text("", encoding="utf-8")
    assert fin.layout_errors("direct_llm", [cal, rest]) == []


def test_finalize_missing_raw_row_yields_in_doubt() -> None:
    fin = _load("s212_finalize_direct", "scripts/finalize_s2_12_arm_v1.py")
    arm_row = {"sample_id": "SIM_card_scenario/r10/v1",
               "request_body_sha256": "c" * 64}
    attempt = fin.direct_attempt_from_raw(arm_row, None, {})
    assert attempt["request_status"] == "in_doubt"
    assert attempt["error_category"] == "raw_response_missing"
    decode_row = {"decode_status": "transport_error:boom", "content": "",
                  "content_sha256": ""}
    attempt = fin.direct_attempt_from_raw(arm_row, decode_row, {})
    assert attempt["request_status"] == "in_doubt"
    assert attempt["error_category"].startswith("transport_error")


def test_finalize_refuses_overwrite_and_scan(tmp_path) -> None:
    fin = _load("s212_finalize_direct", "scripts/finalize_s2_12_arm_v1.py")
    with pytest.raises(ValueError):
        fin.collect_stage_files("direct_llm", [tmp_path])
    hit = fin._scan_forbidden("predictions", {
        "record": {"clauses": [{"text": "raw"}]}})
    assert any("text" in h for h in hit)
    hit = fin._scan_forbidden("manifest", {"gold_read_by_runner": False})
    assert hit == []  # declaration keys are not Gold content keys


def test_fallback_plan_event_statuses() -> None:
    """Fallback plan-event builder: unresolved / rejected / accepted paths."""
    fin = _load("s212_finalize_direct", "scripts/finalize_s2_12_arm_v1.py")
    plan = {"execution_order": 1, "sample_id": "S1", "clause_id": "c1",
            "clause_index": 0, "repair_fields": ["actions"],
            "reasons": ["non_definition_missing_action"], "risk_score": 100,
            "request_body_sha256": "x" * 64}
    record = {
        "schema_version": "1.0.0",
        "sample_id": "S1", "source_id": "S1", "source_text": "Must do it.",
        "method": {"name": "sun_llm_fallback",
                   "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {"schema_valid": True, "cross_field_valid": True,
                       "errors": []},
        "clauses": [{
            "clause_id": "c1",
            "clause_span": {"text": "Must do it.", "start": 0, "end": 11},
            "modality": {"label": "obligation",
                         "evidence": [{"text": "Must", "start": 0, "end": 4}]},
            "actors": [], "actions": [], "conditions": [], "constraints": [],
            "exceptions": [], "actor_action_map": [], "order_relations": [],
        }],
    }
    src = "Must do it."
    event, merged = fin.fallback_event_for_plan(plan, record, src, None)
    assert event["status"] == "unresolved_raw_missing" and merged is None
    event, merged = fin.fallback_event_for_plan(
        plan, record, src, {"decode_status": "ok_message_content", "content": "{oops"})
    assert event["status"] == "unresolved_malformed_envelope" and merged is None
    rejected_env = {"sample_id": "S1", "clause_id": "c1",
                    "repair_fields": ["actions"], "patches": {"actions": []},
                    "reason": "no change"}
    event, merged = fin.fallback_event_for_plan(
        plan, record, src,
        {"decode_status": "ok_message_content", "content": json.dumps(rejected_env)})
    assert event["status"] == "rejected" and merged is None
    assert event["rejection_reasons"]
    accepted_env = {"sample_id": "S1", "clause_id": "c1",
                    "repair_fields": ["actions"],
                    "patches": {"actions": [{
                        "id": "c1.action.1", "text": "do it.",
                        "start": 5, "end": 11, "normalized": "do it."}]},
                    "reason": "add missing action"}
    event, merged = fin.fallback_event_for_plan(
        plan, record, src,
        {"decode_status": "ok_message_content", "content": json.dumps(accepted_env)})
    assert event["status"] == "accepted" and merged is not None
    assert merged["clauses"][0]["actions"][0]["id"] == "c1.action.1"
    assert len(event["field_diff_summary"]) == 1
    assert event["field_diff_summary"][0]["field"] == "actions"
    assert (event["field_diff_summary"][0]["before_sha256"]
            != event["field_diff_summary"][0]["after_sha256"])


# ---------------------------------------------------------------------------
# E2E: fake direct_llm D-CAL -> D-REST chain + finalize
# ---------------------------------------------------------------------------


def test_direct_fake_chain_finalizes_36_ok_records(monkeypatch) -> None:
    from bpc_hybrid import s2_12_execution
    monkeypatch.setattr(s2_12_execution, "is_beijing_peak",
                        lambda *a, **k: False)
    runner = _load("s212_direct_runner", "scripts/run_s2_12_direct_llm_v1.py")
    monkeypatch.setattr(runner, "PayloadLockedFakeTransport",
                        CanonicalContentFakeTransport)
    fin = _load("s212_finalize_direct", "scripts/finalize_s2_12_arm_v1.py")

    with tempfile.TemporaryDirectory(prefix="s212-final-e2e-",
                                     dir=ROOT / ".tmp") as base:
        base = Path(base)
        cal_out = base / "stages" / "cal"
        cal_raw = base / "raws" / "cal"
        cal_ns = SimpleNamespace(
            runtime_home=RUNTIME_HOME, output_dir=cal_out,
            transport="fake", allow_llm=False, auth_file=None,
            stage_id="D-CAL", resume_from_ledger=None, raw_dir=cal_raw,
            transport_timeout=180.0)
        runner.run(cal_ns)
        cal_ledger = cal_out.parent / f"{cal_out.name}.ledger.jsonl"
        assert cal_ledger.is_file()

        rest_out = base / "stages" / "rest"
        rest_raw = base / "raws" / "rest"
        rest_ns = SimpleNamespace(
            runtime_home=RUNTIME_HOME, output_dir=rest_out,
            transport="fake", allow_llm=False, auth_file=None,
            stage_id="D-REST", resume_from_ledger=cal_ledger,
            raw_dir=rest_raw, transport_timeout=180.0)
        runner.run(rest_ns)
        rest_ledger = rest_out.parent / f"{rest_out.name}.ledger.jsonl"
        assert rest_ledger.is_file()

        final_out = base / "capsule"
        final_ns = SimpleNamespace(arm="direct_llm",
                                   runtime_home=RUNTIME_HOME,
                                   raw_dir=[cal_raw, rest_raw],
                                   ledger=rest_ledger,
                                   output_dir=final_out)
        result = fin.run(final_ns)
        assert result["capsule_status"] == "complete"
        assert result["ok_rows"] == 36
        assert result["in_doubt"] == 0 and result["failed"] == 0

        for name in ("predictions.json", "telemetry.json", "cost.json",
                     "manifest.json"):
            path = final_out / name
            assert path.is_file(), name
            doc = json.loads(path.read_text(encoding="utf-8"))
            assert _scan_text_keys(doc) == [], name

        manifest = json.loads((final_out / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["status"] == "predictions_locked_before_gold_evaluation"
        assert manifest["capsule_status"] == "complete"
        assert manifest["record_count"] == 36
        for name, info in manifest["artifacts"].items():
            data = (final_out / name).read_bytes()
            assert info["sha256"] == hashlib.sha256(data).hexdigest()
            assert info["byte_size"] == len(data)

        predictions = json.loads((final_out / "predictions.json").read_text(encoding="utf-8"))
        assert len(predictions["records"]) == 36
        assert [row["sample_id"] for row in predictions["records"]] == RULES_ONLY_ORDER
        for row in predictions["records"]:
            assert row["request_status"] == "ok"
            assert row["error_category"] is None
            assert row["record"] is not None

        telemetry = json.loads((final_out / "telemetry.json").read_text(encoding="utf-8"))
        assert telemetry["ok_prediction_rows"] == 36
        cost = json.loads((final_out / "cost.json").read_text(encoding="utf-8"))
        assert cost["llm_calls"] == 36
        assert cost["actual_cost_usd"] > 0
        # Recompute the official off-peak cost from the billed token counts.
        price = cost["billing"]["official_off_peak_per_million_tokens"]
        expected = (
            cost["input_tokens_billed"] * price["input_cache_miss"]
            + cost["output_tokens_billed"] * price["output"]
        ) / 1_000_000
        assert abs(cost["actual_cost_usd"] - expected) < 1e-6

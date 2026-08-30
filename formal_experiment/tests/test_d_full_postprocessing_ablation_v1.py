# -*- coding: utf-8 -*-
"""Tests for the fixed-response post-processing module ablation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_d_full_postprocessing_ablation_v1 as ablation


def _raw_row() -> tuple[dict, str]:
    text = "The controller shall retain records."
    payload = {
        "schema_version": "1.0.0",
        "sample_id": "s1",
        "source_id": "s1",
        "source_text": text,
        "clauses": [{
            "clause_id": "c1",
            "clause_span": {"text": text, "start": 0, "end": len(text)},
            "modality": {"label": "obligation", "evidence": [
                {"text": "shall", "start": 14, "end": 19}]},
            "actors": [{
                "actor_id": "a1",
                "span": {"text": "controller", "start": 4, "end": 14}}],
            "actions": [{
                "action_id": "p1",
                "span": {"text": "retain records", "start": 20, "end": 34}}],
            "conditions": [], "constraints": [], "exceptions": [],
            "actor_action_map": [{"actor_id": "a1", "action_id": "p1"}],
            "order_relations": [],
        }],
        "method": {
            "name": "direct_llm",
            "schema_source": "stage2_prediction.schema.json@1.0.0"},
        "validation": {
            "schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }
    row = {
        "sample_id": "s1", "raw_response_content": json.dumps(payload),
        "response_sha256": "a" * 64, "request_id": "r1",
    }
    return row, text


def test_each_condition_removes_exactly_one_named_module():
    full = ablation.CONDITIONS["full_postprocessing"]
    active = ("adapter", "canonicalizer", "validator")
    assert all(full[key] for key in active)
    for condition_id in (
            "no_output_adapter", "no_span_canonicalizer",
            "no_canonical_validator"):
        condition = ablation.CONDITIONS[condition_id]
        disabled = [key for key in active if not condition[key]]
        assert len(disabled) == 1
        assert condition["removed_module"] is not None


def test_adapter_removal_drops_nested_relay_spans_but_keeps_denominator():
    row, text = _raw_row()
    full_rows, full_stats = ablation.process_condition(
        [row], {"s1": text}, ablation.CONDITIONS["full_postprocessing"])
    no_rows, no_stats = ablation.process_condition(
        [row], {"s1": text}, ablation.CONDITIONS["no_output_adapter"])
    assert len(full_rows) == len(no_rows) == 1
    assert len(full_rows[0]["record"]["clauses"][0]["actors"]) == 1
    assert len(full_rows[0]["record"]["clauses"][0]["actions"]) == 1
    assert no_rows[0]["record"]["clauses"][0]["actors"] == []
    assert no_rows[0]["record"]["clauses"][0]["actions"] == []
    assert full_stats["successful_records"] == no_stats["successful_records"] == 1


def test_validator_gate_rejects_unreanchored_invalid_offsets():
    row, text = _raw_row()
    payload = json.loads(row["raw_response_content"])
    payload["clauses"][0]["clause_span"]["start"] = 1
    payload["clauses"][0]["clause_span"]["end"] = len(text) + 1
    row["raw_response_content"] = json.dumps(payload)
    rows, stats = ablation.process_condition(
        [row], {"s1": text},
        ablation.CONDITIONS["no_span_canonicalizer"])
    assert rows[0]["request_status"] == "failed"
    assert stats["validator_invalid_records_observed"] == 1
    assert stats["validator_rejected_records"] == 1


def test_checked_in_report_is_zero_api_and_baseline_matches_locked_result():
    report = json.loads(ablation.REPORT_JSON.read_text(encoding="utf-8"))
    assert report["scope"]["new_api_calls"] == 0
    assert report["scope"]["model_responses_fixed_across_conditions"] is True
    assert report["scope"]["measured_layer"] == "postprocessing_only"
    assert report["provenance"][
        "baseline_exactly_reproduces_locked_evaluation"] is True
    conditions = report["conditions"]
    assert set(conditions) == set(ablation.CONDITIONS)
    assert abs(conditions["full_postprocessing"]["overall"]["f1"]
               - 0.7719075848848173) < 1e-12
    assert report["scope"]["model_generation_effect_claim_allowed"] is False


def test_markdown_keeps_safety_and_generation_boundaries():
    report = json.loads(ablation.REPORT_JSON.read_text(encoding="utf-8"))
    text = ablation.to_markdown(report)
    assert "每个条件只关闭一个后处理模块" in text
    assert "不能说明validator没有安全价值" in text
    assert "不评价模块说明是否改变模型生成" in text

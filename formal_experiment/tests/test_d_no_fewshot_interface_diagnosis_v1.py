# -*- coding: utf-8 -*-
"""Tests for the zero-API D-no-fewshot interface diagnosis."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_d_no_fewshot_interface_failure_v1 as diagnosis


def _payload() -> dict:
    text = "The controller shall retain records."
    return {
        "schema_version": "1.0.0",
        "sample_id": "s1",
        "source_id": "s1",
        "source_text": text,
        "clauses": [{
            "clause_id": "cl_0",
            "clause_span": [0, len(text)],
            "modality": {
                "type": "obligation",
                "evidence": [{"span": [15, 20], "text": "shall"}],
            },
            "actors": [{
                "actor_id": "a1", "span": [4, 14], "text": "controller"}],
            "actions": [{
                "action_id": "p1", "span": [21, 35],
                "text": "retain records"}],
            "conditions": [],
            "constraints": [],
            "exceptions": [],
            "actor_action_map": [{"actor_id": "a1", "action_id": "p1"}],
            "order_relations": [],
        }],
        "method": {"name": "direct_llm"},
        "validation": {
            "schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }


def test_coordinate_pair_bridge_changes_representation_not_semantics():
    payload = _payload()
    record, audit = diagnosis.bridge_coordinate_pair_record(
        payload, payload["source_text"])
    validation = diagnosis.validate_canonical(record)
    assert validation.schema_valid and validation.cross_field_valid
    clause = record["clauses"][0]
    assert clause["clause_span"] == {
        "text": payload["source_text"], "start": 0,
        "end": len(payload["source_text"])}
    assert clause["modality"]["label"] == "obligation"
    assert clause["actors"][0]["text"] == "controller"
    assert clause["actions"][0]["text"] == "retain records"
    assert clause["actor_action_map"] == [
        {"actor_id": "a1", "action_id": "p1"}]
    assert audit["clause_coordinate_pairs_converted"] == 1
    assert audit["field_coordinate_pairs_converted"] == 3
    assert audit["modality_type_keys_converted"] == 1


def test_replay_keeps_failed_json_in_the_denominator():
    payload = _payload()
    raw_rows = [{
        "sample_id": "s1", "raw_response_content": json.dumps(payload),
        "response_sha256": "a" * 64, "request_id": "r1",
    }, {
        "sample_id": "s2", "raw_response_content": "{bad",
        "response_sha256": "b" * 64, "request_id": "r2",
    }]
    preds, stats = diagnosis.replay_rows(
        raw_rows,
        {"s1": payload["source_text"], "s2": "Another source."},
    )
    assert len(preds) == 2
    assert preds[0]["request_status"] == "ok"
    assert preds[1]["request_status"] == "failed"
    assert stats["json_parse_success"] == 1
    assert stats["json_parse_failure"] == 1
    assert stats["raw_nonempty_clause_records"] == 1


def test_checked_in_diagnosis_has_the_observed_150_row_evidence():
    report = json.loads(diagnosis.REPORT_JSON.read_text(encoding="utf-8"))
    observed = report["observed_failure_mechanism"]
    assert report["status"] == \
        "retrospective_development_diagnostic_not_formal_ablation"
    assert report["scope"]["new_api_calls"] == 0
    assert report["scope"]["confirmatory_claim_allowed"] is False
    assert observed["json_parse_success"] == 147
    assert observed["json_parse_failure"] == 3
    assert observed["raw_nonempty_clause_records"] == 146
    assert observed["raw_clause_count"] == 247
    assert observed["raw_clause_span_array_count"] == 247
    assert observed["raw_clause_span_object_count"] == 0
    assert observed["current_canonical_nonempty_records"] == 0
    assert report["scientific_interpretation"][
        "few_shot_semantic_contribution_isolated"] is False


def test_markdown_forbids_the_false_no_semantics_claim():
    report = json.loads(diagnosis.REPORT_JSON.read_text(encoding="utf-8"))
    rendered = diagnosis.to_markdown(report)
    assert "并不是没有抽取语义内容" in rendered
    assert "不能说：删除 few-shot 后模型完全失去语义抽取能力" in rendered
    assert "新增 API 调用为0" in rendered

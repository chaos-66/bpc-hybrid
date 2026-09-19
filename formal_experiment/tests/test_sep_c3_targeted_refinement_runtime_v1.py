# -*- coding: utf-8 -*-
"""Focused runtime tests for the SEP-C3 targeted-refinement conversion path.

The tests exercise the actual runner entry (``_prediction_with_provenance`` and
``_build_arm_outputs``), not a detached helper.  No network/API call is made.
"""

from __future__ import annotations

import copy
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

import bpc_hybrid.d1_schema_adapter as d1_adapter  # noqa: E402
import run_sep_c3_targeted_refinement_v1 as runtime  # noqa: E402


SAMPLE = runtime.core.samples(150)[0]
SAMPLE_ID = str(SAMPLE["sample_id"])
SOURCE_TEXT = str(SAMPLE["text"])
ARM = "A"
VALIDATION_PATH_VERSION = runtime.OUTPUT_VALIDATION_PATH_VERSION


def _valid_payload(
    *,
    sample_id: str = SAMPLE_ID,
    source_id: str = SAMPLE_ID,
    source_text: str = SOURCE_TEXT,
) -> dict:
    """A minimal payload that passes the existing canonical validator."""
    return {
        "schema_version": "1.0.0",
        "sample_id": sample_id,
        "source_id": source_id,
        "source_text": source_text,
        "clauses": [
            {
                "clause_id": "clause_1",
                "clause_span": {
                    "text": source_text,
                    "start": 0,
                    "end": len(source_text),
                },
                "modality": {"label": "obligation", "evidence": []},
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ],
        "method": {
            "name": "direct_llm",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {
            "schema_valid": True,
            "cross_field_valid": True,
            "errors": [],
        },
    }


def _raw(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _call_for_payload(payload: object) -> dict:
    raw = _raw(payload)
    return {
        "sample_id": SAMPLE_ID,
        "arm": ARM,
        "request_id": f"{ARM}:{SAMPLE_ID}:unit-test",
        "response_sha256": runtime.core._sha256_text(raw),
        "raw_model_output": raw,
        "raw_response_content": raw,
        "raw_output_sha256": runtime.core._sha256_text(raw),
        "bare_json_status": "bare_json_object",
        "request_status": "ok",
        "error": None,
    }


def _predict(payload: object, *, source_text: str = SOURCE_TEXT) -> dict:
    return runtime._prediction_with_provenance(
        _call_for_payload(payload), ARM, source_text)


def _action_payload(bad_evidence: object) -> dict:
    payload = _valid_payload()
    clause = payload["clauses"][0]
    action_text = SOURCE_TEXT[:4]
    clause["actions"] = [{
        "id": "action_1",
        "text": action_text,
        "start": 0,
        "end": len(action_text),
        "normalized": action_text.casefold(),
    }]
    clause["order_relations"] = [{
        "before_action_id": "action_1",
        "after_action_id": "action_1",
        "evidence": bad_evidence,
    }]
    return payload


def test_normal_output_passes_and_validation_is_recomputed_by_runtime():
    payload = _valid_payload()
    payload["validation"] = {
        "schema_valid": False,
        "cross_field_valid": False,
        "errors": ["stale model self-report; must not decide"],
    }

    row = _predict(payload)

    assert row["request_status"] == "ok"
    assert row["api_call_status"] == "ok"
    assert row["output_parse_status"] == "passed"
    assert row["input_binding_status"] == "passed"
    assert row["canonical_validation_status"] == "passed"
    assert row["validation_backend"] == "lightweight"
    assert row["record"]["validation"] == {
        "schema_valid": True,
        "cross_field_valid": True,
        "errors": [],
    }
    assert row["record"]["validation"] is not payload["validation"]
    assert row["provenance"]["output_validation_path_version"] == (
        VALIDATION_PATH_VERSION
    )
    assert row["provenance"]["validation_backend"] == "lightweight"


def test_source_text_with_appended_example_is_rejected_before_adapter(
    monkeypatch,
):
    payload = _valid_payload(source_text=SOURCE_TEXT + " E")
    adapter_called = {"value": False}

    def _must_not_be_called(*args, **kwargs):  # noqa: ANN002, ANN003
        adapter_called["value"] = True
        raise AssertionError("adapter must not run after binding failure")

    monkeypatch.setattr(
        d1_adapter, "adapt_relay_record", _must_not_be_called)

    row = _predict(payload, source_text=SOURCE_TEXT)

    assert adapter_called["value"] is False
    assert row["request_status"] == "failed"
    assert row["failure_stage"] == "input_binding"
    assert row["input_binding_status"] == "failed"
    assert "source_text_mismatch" in row["input_binding"]["errors"]
    assert row["record"] == {}
    assert row["parsed_output"]["source_text"] == SOURCE_TEXT + " E"
    assert row["canonical_output"] is None


def test_sample_id_and_source_id_errors_or_missing_are_rejected():
    cases = [
        ("sample_id_mismatch", "sample_id", "wrong-sample-id"),
        ("source_id_mismatch", "source_id", "wrong-source-id"),
        ("sample_id_missing", "sample_id", None),
        ("source_id_missing", "source_id", None),
    ]
    for expected_error, field, value in cases:
        payload = _valid_payload()
        if value is None:
            del payload[field]
        else:
            payload[field] = value

        row = _predict(payload)

        assert row["request_status"] == "failed", expected_error
        assert row["failure_stage"] == "input_binding", expected_error
        assert row["input_binding_status"] == "failed", expected_error
        assert expected_error in row["input_binding"]["errors"], (
            expected_error,
            row["input_binding"],
        )
        assert row["record"] == {}, expected_error


def test_model_self_reported_validation_true_but_illegal_modality_rejected():
    payload = _valid_payload()
    payload["clauses"][0]["modality"]["label"] = "limitation"
    payload["validation"] = {
        "schema_valid": True,
        "cross_field_valid": True,
        "errors": [],
    }

    row = _predict(payload)

    assert row["request_status"] == "failed"
    assert row["failure_stage"] == "canonical_validation"
    assert row["canonical_validation_status"] == "failed"
    assert row["record"] == {}
    assert row["runtime_validation"]["schema_valid"] is True
    assert row["runtime_validation"]["cross_field_valid"] is False
    assert "modality.label" in row["error"]
    assert "limitation" in row["error"]


@pytest.mark.parametrize(
    "bad_evidence",
    [
        "not-an-array",
        [{"text": "zzzz", "start": 0, "end": 4}],
    ],
    ids=["evidence_type", "evidence_coordinate"],
)
def test_order_relation_bad_evidence_is_found_by_runtime_validation(
    bad_evidence,
):
    row = _predict(_action_payload(bad_evidence))

    assert row["request_status"] == "failed"
    assert row["failure_stage"] == "canonical_validation"
    assert row["record"] == {}
    assert row["runtime_validation"]["cross_field_valid"] is False
    assert any(
        "order_relations[0].evidence" in error
        for error in row["runtime_validation"]["errors"]
    )


def test_failed_envelope_keeps_trace_and_sample_stays_in_denominator(
    tmp_path, monkeypatch,
):
    payload = _valid_payload()
    payload["clauses"][0]["modality"]["label"] = "limitation"
    call = _call_for_payload(payload)
    attempts_seen: list[dict] = []

    def _fake_evaluate(gold_doc, attempts, method_id):  # noqa: ANN001
        attempts_seen.extend(list(attempts))
        return {
            "method_id": method_id,
            "view": "coarse_sentence_level",
            "primary_metric": "coarse_five_field_mean_f1",
            "coarse_five_field_mean_f1": 0.0,
            "coarse_five_field_micro": {"f1": 0.0},
            "modality_labels": {"macro_f1": 0.0},
        }

    monkeypatch.setattr(runtime, "evaluate_coarse", _fake_evaluate)
    monkeypatch.setattr(
        runtime, "_relative", lambda path: Path(path).as_posix())

    result = runtime._build_arm_outputs(
        ARM,
        {SAMPLE_ID: call},
        [{"sample_id": SAMPLE_ID, "text": SOURCE_TEXT}],
        {},
        tmp_path,
        "unit-test-schedule-sha256",
        actual_call_count=1,
        resumed_completed_count=0,
    )

    assert len(attempts_seen) == 1
    assert attempts_seen[0]["request_status"] == "failed"
    assert attempts_seen[0]["record"] == {}
    assert result["manifest"]["evaluation_denominator"] == 1
    assert result["manifest"]["failed_count"] == 1
    assert result["manifest"]["output_validation_path"]["version"] == (
        VALIDATION_PATH_VERSION
    )
    assert result["manifest"]["processing_status_counts"][
        "canonical_validation_status"
    ] == {"failed": 1}

    failed_rows = [
        json.loads(line)
        for line in (
            tmp_path / ARM / "repeat-01" / "failed_samples.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(failed_rows) == 1
    row = failed_rows[0]
    assert row["sample_id"] == SAMPLE_ID
    assert row["request_id"] == call["request_id"]
    assert row["response_sha256"] == call["response_sha256"]
    assert row["raw_model_output"] == call["raw_model_output"]
    assert row["failure_stage"] == "canonical_validation"
    assert row["error"]
    assert row["record"] == {}
    assert row["input_binding_status"] == "passed"
    assert row["canonical_validation_status"] == "failed"


def test_actual_entry_does_not_mutate_parsed_payload(monkeypatch):
    payload = _valid_payload()
    original = copy.deepcopy(payload)
    call = _call_for_payload(payload)
    real_convert = runtime.convert_response_payload
    observed: dict = {}

    def _wrapper(payload_arg, **kwargs):  # noqa: ANN001
        observed["before"] = copy.deepcopy(payload_arg)
        row = real_convert(payload_arg, **kwargs)
        observed["after"] = copy.deepcopy(payload_arg)
        return row

    monkeypatch.setattr(runtime, "convert_response_payload", _wrapper)

    row = runtime._prediction_with_provenance(call, ARM, SOURCE_TEXT)

    assert row["request_status"] == "ok"
    assert observed["before"] == original
    assert observed["after"] == original
    assert payload == original
    assert row["parsed_output"] == original


def test_actual_build_entry_uses_fixed_conversion_path(tmp_path, monkeypatch):
    payload = _valid_payload()
    call = _call_for_payload(payload)
    conversion_calls = {"count": 0}
    real_convert = runtime.convert_response_payload

    def _spy(payload_arg, **kwargs):  # noqa: ANN001
        conversion_calls["count"] += 1
        return real_convert(payload_arg, **kwargs)

    def _fake_evaluate(gold_doc, attempts, method_id):  # noqa: ANN001
        return {
            "method_id": method_id,
            "view": "coarse_sentence_level",
            "primary_metric": "coarse_five_field_mean_f1",
            "coarse_five_field_mean_f1": 0.0,
            "coarse_five_field_micro": {"f1": 0.0},
            "modality_labels": {"macro_f1": 0.0},
        }

    monkeypatch.setattr(runtime, "convert_response_payload", _spy)
    monkeypatch.setattr(runtime, "evaluate_coarse", _fake_evaluate)
    monkeypatch.setattr(
        runtime, "_relative", lambda path: Path(path).as_posix())

    runtime._build_arm_outputs(
        ARM,
        {SAMPLE_ID: call},
        [{"sample_id": SAMPLE_ID, "text": SOURCE_TEXT}],
        {},
        tmp_path,
        "unit-test-schedule-sha256",
        actual_call_count=1,
        resumed_completed_count=0,
    )

    assert conversion_calls["count"] == 1
    predictions = [
        json.loads(line)
        for line in (
            tmp_path / ARM / "repeat-01" / "canonical_predictions.jsonl"
        ).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(predictions) == 1
    row = predictions[0]
    assert row["request_status"] == "ok"
    assert row["input_binding_status"] == "passed"
    assert row["canonical_validation_status"] == "passed"
    assert row["validation_backend"] == "lightweight"
    assert row["output_validation_path_version"] == VALIDATION_PATH_VERSION
    assert row["record"]["validation"] == {
        "schema_valid": True,
        "cross_field_valid": True,
        "errors": [],
    }

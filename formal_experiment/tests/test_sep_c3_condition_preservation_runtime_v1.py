# -*- coding: utf-8 -*-
"""Focused zero-API acceptance tests for the condition-preservation executor."""

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


class FakeTransport:
    """Deterministic zero-network transport returning FAKE synthetic objects."""

    def __init__(self) -> None:
        self.calls = 0
        self.last_decode = None

    def send(self, request):
        self.calls += 1
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
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
            },
            "model": "deepseek-v4-pro",
            "response_id": f"fake-{self.calls}",
            "finish_reason": "stop",
        }
        return LLMResponse(
            content=json.dumps(payload, ensure_ascii=False),
            provider="mock",
            model="deepseek-v4-pro",
            finish_reason="stop",
        )


def _call(content: str, *, sid: str = "estg_000002") -> dict:
    return {
        "sample_id": sid,
        "api_call_status": "ok",
        "transport_status": "ok",
        "decode_status": "ok_message_content",
        "raw_response_content": content,
        "raw_model_output": content,
        "response_sha256": runner._sha256_text(content),
        "request_id": "fake-request",
    }


def _payload(*, sid: str, text: str, source_text: str | None = None) -> str:
    return json.dumps({
        "schema_version": "1.0.0",
        "sample_id": sid,
        "source_id": sid,
        "source_text": source_text if source_text is not None else text,
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


def test_missing_authorization_or_budget_creates_no_transport(tmp_path: Path):
    called = {"count": 0}

    def forbidden_transport():
        called["count"] += 1
        raise AssertionError("transport must not be created")

    with pytest.raises(runner.ConditionPreservationRunError):
        runner.execute(
            transport_factory=forbidden_transport,
            auth_path=tmp_path / "missing_authorization.json",
        )
    with pytest.raises(runner.ConditionPreservationRunError):
        runner.execute(
            transport_factory=forbidden_transport,
            prepared_budget_path=tmp_path / "missing_budget.json",
        )
    assert called["count"] == 0


def test_hash_mismatch_creates_no_transport(tmp_path: Path):
    contract = json.loads(
        runner.EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8")
    )
    contract["authorization_sha256"] = "deadbeef"
    bad_contract = tmp_path / "bad_contract.json"
    bad_contract.write_text(
        json.dumps(contract, ensure_ascii=False), encoding="utf-8"
    )
    called = {"count": 0}

    def forbidden_transport():
        called["count"] += 1
        raise AssertionError("transport must not be created")

    with pytest.raises(runner.ConditionPreservationRunError):
        runner.execute(
            transport_factory=forbidden_transport,
            contract_path=bad_contract,
        )
    assert called["count"] == 0


def test_parse_input_binding_and_structure_failures_stay_in_denominator():
    sid = "estg_000002"
    text = "Bookkeeping farmers may use a different business year."

    parse_row = runner._convert_call_to_prediction(
        _call("not-json {{{", sid=sid),
        arm="BASE",
        expected_sample_id=sid,
        expected_source_id=sid,
        expected_source_text=text,
    )
    assert parse_row["request_status"] == "failed"
    assert parse_row["output_parse_status"] == "failed"

    appended = runner._convert_call_to_prediction(
        _call(_payload(sid=sid, text=text, source_text=text + "\nExample appended")),
        arm="BASE",
        expected_sample_id=sid,
        expected_source_id=sid,
        expected_source_text=text,
    )
    assert appended["request_status"] == "failed"
    assert appended["input_binding_status"] == "failed"

    bad_structure = json.dumps({
        "schema_version": "1.0.0",
        "sample_id": sid,
        "source_id": sid,
        "source_text": text,
        "clauses": {"not": "a list"},
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
    })
    structure_row = runner._convert_call_to_prediction(
        _call(bad_structure),
        arm="BASE",
        expected_sample_id=sid,
        expected_source_id=sid,
        expected_source_text=text,
    )
    assert structure_row["request_status"] == "failed"
    assert structure_row["adapter_status"] == "failed"

    rows = [parse_row, appended, structure_row]
    attempts = bs.attempt_rows(rows)
    assert len(attempts) == 3
    assert all(row["sample_id"] == sid for row in attempts)


def test_call_cap_and_budget_checks_are_fail_closed():
    contract = {
        "model": {"id": MODEL_ALIAS if False else "deepseek-v4-pro"},
        "call_cap": 1,
        "input_token_cap": 1000,
        "output_token_cap": 4096,
        "usd_cost_cap": 10.0,
        "price_snapshot": {
            "peak": {
                "input_cache_hit_per_million": 0.044,
                "input_cache_miss_per_million": 1.32,
                "output_per_million": 3.96,
            },
            "off_peak": {
                "input_cache_hit_per_million": 0.022,
                "input_cache_miss_per_million": 0.66,
                "output_per_million": 1.98,
            },
        },
    }
    gate = runner.ReservationBudgetGate(contract)
    gate.check_before_send(10)
    gate.register_attempt(10)
    with pytest.raises(runner.ConditionPreservationRunError):
        gate.check_before_send(10)

    tight = runner.ReservationBudgetGate({
        **contract,
        "call_cap": 10,
        "input_token_cap": 5,
    })
    with pytest.raises(runner.ConditionPreservationRunError):
        tight.check_before_send(10)

    expensive = runner.ReservationBudgetGate({
        **contract,
        "call_cap": 10,
        "usd_cost_cap": 0.000001,
    })
    with pytest.raises(runner.ConditionPreservationRunError):
        expensive.check_before_send(10)


def _read_prediction_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_full_450_fake_schedule_persists_converts_evaluates_and_analyzes(
    tmp_path: Path,
):
    fake_dir = tmp_path / "FAKE_ACCEPTANCE"
    fake_dir.mkdir()
    (fake_dir / "FAKE_ONLY.txt").write_text(
        "FAKE synthetic responses; not real model output\n", encoding="utf-8"
    )
    transport = FakeTransport()
    result = runner.execute(
        transport_factory=lambda: transport,
        out_dir=fake_dir,
        result_writer=lambda _: None,
        enforce_off_peak=False,
    )
    assert result["complete"] is True
    assert transport.calls == 450
    assert result["actual_calls"] == 450
    assert result["completed_samples"] == 450
    assert all(v == 150 for v in result["attempt_counts_per_arm"].values())

    paths = {}
    for arm in runner.ARMS:
        run_dir = fake_dir / arm / runner.REPEAT_ID
        assert (run_dir / "attempts.jsonl").is_file()
        assert (run_dir / "raw_responses.jsonl").is_file()
        assert (run_dir / "canonical_predictions.jsonl").is_file()
        rows = _read_prediction_rows(run_dir / "canonical_predictions.jsonl")
        assert len(rows) == 150
        assert all(row["request_status"] == "ok" for row in rows)
        paths[arm] = run_dir / "canonical_predictions.jsonl"

    bootstrap = bs.analyze(
        base_path=paths["BASE"],
        rc1_path=paths["RC1"],
        rc_keep_path=paths["RC_KEEP"],
        output_path=fake_dir / "bootstrap.json",
    )
    assert bootstrap["denominator_per_arm"] == {
        "BASE": 150,
        "RC1": 150,
        "RC_KEEP": 150,
    }
    for comparison in bootstrap["bootstrap"]["comparisons"].values():
        assert "point_difference" in comparison
        assert "bootstrap_mean_difference" in comparison
        assert len(comparison["difference_values"]) == 10000

    # A second execution must not resend any completed request.
    class NoSendTransport(FakeTransport):
        def send(self, request):  # pragma: no cover - should never be called
            raise AssertionError(f"completed request was resent: {request.source_id}")

    second = runner.execute(
        transport_factory=lambda: NoSendTransport(),
        out_dir=fake_dir,
        result_writer=lambda _: None,
        enforce_off_peak=False,
    )
    assert second["complete"] is True
    assert second["new_sends_per_arm"] == {"BASE": 0, "RC1": 0, "RC_KEEP": 0}


def test_in_doubt_attempt_stops_before_transport_creation(tmp_path: Path):
    out = tmp_path / "in_doubt"
    run_dir = out / "BASE" / runner.REPEAT_ID
    run_dir.mkdir(parents=True)
    (run_dir / "attempts.jsonl").write_text(
        json.dumps({
            "sample_id": "estg_000002",
            "arm": "BASE",
            "estimated_input_tokens_bytes_div_3": 10,
            "request_body_sha256": "x",
        }, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    called = {"count": 0}

    def forbidden_transport():
        called["count"] += 1
        raise AssertionError("transport must not be created after in_doubt")

    with pytest.raises(runner.ConditionPreservationRunError, match="in_doubt"):
        runner.execute(
            transport_factory=forbidden_transport,
            out_dir=out,
            enforce_off_peak=False,
        )
    assert called["count"] == 0


def test_analyzer_rejects_three_arms_all_missing_the_same_sample(tmp_path: Path):
    input_doc = json.loads(
        bs.DEFAULT_INPUT.read_text(encoding="utf-8")
    )
    all_ids = [str(rec["sample_id"]) for rec in input_doc["records"]]
    missing_one = set(all_ids[1:])
    paths = {}
    for arm in bs.ARMS:
        path = tmp_path / f"{arm}.jsonl"
        path.write_text(
            "".join(
                json.dumps({"sample_id": sid, "request_status": "ok", "record": {}})
                + "\n"
                for sid in all_ids
                if sid in missing_one
            ),
            encoding="utf-8",
        )
        paths[arm] = path
    with pytest.raises(bs.BootstrapError, match="frozen 150"):
        bs.analyze(
            base_path=paths["BASE"],
            rc1_path=paths["RC1"],
            rc_keep_path=paths["RC_KEEP"],
            output_path=tmp_path / "should_not_write.json",
        )


def test_point_difference_is_actual_full_sample_difference():
    sample_order = ["s1", "s2", "s3"]
    counts_by_arm = {
        arm: {sid: bs._zero_counts() for sid in sample_order}
        for arm in bs.ARMS
    }
    # Make RC_KEEP improve only on one of three samples.
    counts_by_arm["RC_KEEP"]["s1"]["condition"]["ground_truth"] = 1
    counts_by_arm["RC_KEEP"]["s1"]["condition"]["extracted"] = 1
    counts_by_arm["RC_KEEP"]["s1"]["condition"]["matched_predictions"] = 1
    counts_by_arm["RC_KEEP"]["s1"]["condition"]["matched_ground_truth"] = 1
    result = bs.paired_bootstrap(
        sample_order, counts_by_arm, resamples=50, seed=20260919
    )
    payload = result["comparisons"]["RC_KEEP-RC1_condition_f1"]
    point_counts = bs._zero_counts()
    for sid in sample_order:
        bs._add_counts(point_counts, counts_by_arm["RC_KEEP"][sid])
    point_metrics = bs._metrics_from_field_counts(point_counts)
    rc1_counts = bs._zero_counts()
    for sid in sample_order:
        bs._add_counts(rc1_counts, counts_by_arm["RC1"][sid])
    rc1_metrics = bs._metrics_from_field_counts(rc1_counts)
    expected = float(point_metrics["condition_f1"]) - float(
        rc1_metrics["condition_f1"]
    )
    assert abs(payload["point_difference"] - expected) < 1e-12
    assert abs(
        payload["bootstrap_mean_difference"]
        - sum(payload["difference_values"]) / len(payload["difference_values"])
    ) < 1e-12
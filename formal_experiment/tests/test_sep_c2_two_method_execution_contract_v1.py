# -*- coding: utf-8 -*-
"""SEP-C2 focused tests: cancellation enforcement and two-method contract.

These tests are intentionally narrow and zero-API.  They assert the machine
rules the user asked for:

* the cancelled ``sun_llm_fallback`` entry refuses before transport/output;
* missing Direct-LLM evidence keeps S2.12/S2.13 incomplete;
* the active Direct path does not depend on the cancelled repair ledger/results.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

RUNTIME_HOME = Path("D:/environment/stanford-corenlp-4.5.10")


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_cancelled_repair_runner_refuses_before_transport_or_output(tmp_path, monkeypatch):
    import bpc_hybrid.s2_12_execution as ex
    runner = _load("sep_c2_fallback_runner",
                   "scripts/run_s2_12_sun_llm_fallback_v1.py")

    def _must_not_construct(*args, **kwargs):
        raise AssertionError("cancelled arm constructed a transport/executor")

    monkeypatch.setattr(runner, "PayloadLockedFakeTransport", _must_not_construct)
    monkeypatch.setattr(runner, "PayloadLockedRealTransport", _must_not_construct)
    monkeypatch.setattr(runner, "StageExecutor", _must_not_construct)
    out = tmp_path / "cancelled-fallback"
    args = SimpleNamespace(
        runtime_home=RUNTIME_HOME, output_dir=out, transport="fake",
        allow_llm=False, auth_file=None, stage_id="F-1",
        resume_from_ledger=None, raw_dir=None, transport_timeout=180.0,
    )
    with pytest.raises(ex.S212ExecutionError, match="cancelled"):
        runner.run(args)
    assert not out.exists()


def test_finalizer_and_evaluator_reject_cancelled_arm(tmp_path) -> None:
    import bpc_hybrid.s2_12_execution as ex
    finalizer = _load("sep_c2_finalizer_reject",
                      "scripts/finalize_s2_12_arm_v1.py")
    evaluator = _load("sep_c2_evaluator_reject",
                      "scripts/evaluate_s2_12_api_arm_v1.py")
    args = SimpleNamespace(
        arm="sun_llm_fallback", runtime_home=RUNTIME_HOME, raw_dir=[],
        ledger=tmp_path / "never-created.ledger.jsonl",
        output_dir=tmp_path / "never-created",
    )
    with pytest.raises((ex.S212ExecutionError, finalizer.FinalizeFail),
                       match="cancelled"):
        finalizer.run(args)
    with pytest.raises(Exception, match="cancelled"):
        evaluator.build_report("sun_llm_fallback")
    assert not args.output_dir.exists()


def test_contract_keeps_direct_pending_and_s213_incomplete() -> None:
    contract = json.loads(
        (ROOT / "outputs/reports/s2_12_two_method_contract_v1.json"
         ).read_text(encoding="utf-8"))
    assert contract["active_methods"] == ["sun_rule_only", "direct_llm"]
    assert "sun_llm_fallback" in contract["cancelled_methods"]
    assert contract["status"] == "partial_two_method_contract_pending_direct_llm"
    assert contract["comparison"]["complete"] is False
    assert contract["comparison"]["fallback_results_or_ledger_required"] is False
    assert contract["comparison"]["three_method_requirement_removed"] is True
    assert contract["freeze"]["s2_12_complete"] is False
    assert contract["freeze"]["s2_13_complete"] is False
    assert contract["freeze"]["cancelled_repair_arm_required"] is False
    assert contract["call_plan"]["remaining_calls"] == {
        "s2_12_direct": 36, "gdpr7_direct": 74, "total": 110}
    assert contract["call_plan"]["cancelled_repair_calls"] == 27
    assert contract["call_plan"]["cancelled_repair_calls_reassigned"] is False
    assert contract["call_plan"]["real_api_calls_made"] == 0
    assert any("Direct-LLM" in item
               for item in contract["zero_api_continuation"]["real_results_missing"])
    assert contract["gdpr7_boundary"]["fake_is_not_real_prediction_or_promotion_source"] is True


def test_comparison_requires_direct_not_repair() -> None:
    module = _load("sep_c2_contract_builder",
                   "scripts/build_s2_12_two_method_contract_v1.py")
    rules = {
        "status": "verified_zero_api_arm_complete",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "metrics": {"overall": {"span_fields": {"overall": {}},
                                "modality_labels": {}}},
    }
    pending = module.compare_two_methods(rules, None)
    assert pending["complete"] is False
    assert "direct_llm_evaluation_missing_or_not_complete" in pending["blockers"]
    assert pending["fallback_results_or_ledger_required"] is False

    direct = {
        "status": "verified_direct_llm_arm_complete",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "metrics": {"overall": {"span_fields": {"overall": {}},
                                "modality_labels": {}}},
    }
    complete = module.compare_two_methods(rules, direct)
    assert complete["complete"] is True
    assert complete["blockers"] == []
    assert "sun_llm_fallback" in complete["cancelled_methods"]


def test_published_contract_is_current_replay() -> None:
    module = _load("sep_c2_contract_replay",
                   "scripts/build_s2_12_two_method_contract_v1.py")
    artifacts = module.build_artifacts()
    for path, expected in artifacts.items():
        assert path.is_file(), path
        assert path.read_bytes() == expected, path


def test_active_direct_payloads_rebuild_without_fallback() -> None:
    import bpc_hybrid.s2_12_execution as ex
    lock = ex.load_lock(scope="active")
    report = ex.load_report(scope="active")
    assert set(lock["arms"]) == {"direct_llm"}
    assert set(report["arms"]) == {"direct_llm"}
    assert "sun_llm_fallback" not in lock["arms"]
    assert "sun_llm_fallback" not in report["arms"]
    rows = ex.rebuild_and_verify_payloads(
        lock, report, RUNTIME_HOME, arms=("direct_llm",))
    assert set(rows) == {"direct_llm"}
    assert len(rows["direct_llm"]) == 36
    assert all(row["request_body_sha256"] for row in rows["direct_llm"])

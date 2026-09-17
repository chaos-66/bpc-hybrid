# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
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

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import run_sep_c3_modular_ablation_v2 as v2  # noqa: E402
from bpc_hybrid import modular_prompt as mp  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import evaluate_coarse  # noqa: E402


def test_v2_budget_and_esj_bit_semantics():
    budget = v2.validate_suite_config()
    assert budget["planned_arms_esj"] == ["000", "001", "010", "100"]
    assert v2.NEW_ARMS == ("000", "001", "010", "100")
    assert v2.FULL_FACTORIAL_ARMS == (
        "111", "011", "101", "110", "100", "010", "001", "000")
    for arm in v2.FULL_FACTORIAL_ARMS:
        prompt = core._prompt(arm)
        assert dict(prompt.flags) == {
            "E": arm[0] == "1",
            "S": arm[1] == "1",
            "J": arm[2] == "1",
        }


def test_v2_all_eight_offline_check_passes_without_network(tmp_path):
    report = core.offline_check(
        arms=v2.FULL_FACTORIAL_ARMS,
        execution_arms=v2.NEW_ARMS,
        planned_calls=600,
        call_cap=750,
        samples_per_arm=150,
        output_path=tmp_path / "offline.json",
    )
    assert report["status"] == "pass"
    assert set(report["arms"]) == set(v2.FULL_FACTORIAL_ARMS)
    assert report["execution_arms"] == list(v2.NEW_ARMS)
    assert report["planned_calls"] == 600
    assert report["estimated_execution_input_tokens"] > 0
    for arm in v2.FULL_FACTORIAL_ARMS:
        assert report["arms"][arm]["loader_matches_composer"] is True
        assert report["arms"][arm]["errors"] == []


def test_v2_disabled_modules_absent_and_enabled_modules_match_source():
    texts = mp.load_module_texts()
    for arm in v2.FULL_FACTORIAL_ARMS:
        prompt = core._prompt(arm)
        expected = {
            "E": arm[0] == "1",
            "S": arm[1] == "1",
            "J": arm[2] == "1",
        }
        combined = prompt.system_prompt + "\n" + prompt.user_prompt_template
        if expected["E"]:
            assert texts["E"].strip() in prompt.user_prompt_template
        else:
            assert texts["E"].strip() not in prompt.user_prompt_template
            assert core.MODULE_MARKERS["E"] not in combined
        if expected["S"]:
            assert texts["S"].strip() in prompt.system_prompt
        else:
            assert texts["S"].strip() not in prompt.system_prompt
            assert core.MODULE_MARKERS["S"] not in combined
        if expected["J"]:
            assert texts["J"].strip() in prompt.system_prompt
        else:
            assert texts["J"].strip() not in prompt.system_prompt
            assert core.MODULE_MARKERS["J"] not in combined


def test_v2_outputs_and_reports_do_not_overwrite_v1():
    assert v2.OUT_DIR != core.OUT_DIR
    assert v2.OFFLINE_REPORT != core.OFFLINE_REPORT
    assert v2.RESULT_REPORT != core.RESULT_REPORT
    assert v2.RESULT_MD != core.RESULT_MD
    assert "sep_c3_modular_ablation_v2" in str(v2.OUT_DIR)
    assert "sep_c3_modular_ablation_v2" in v2.OFFLINE_REPORT.name


def test_v2_protocol_audit_builds_pass_without_network():
    script = ROOT / "scripts" / "build_sep_c3_modular_full8_protocol_audit_v1.py"
    spec = importlib.util.spec_from_file_location("full8_protocol_audit_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    report = module.build_report()
    assert report["status"] == "pass"
    assert report["network_calls"] == 0
    assert report["consistency"]["checks"]["all_prompt_audits_clean"] is True


class _MockTransport:
    def __init__(self, content: str, usage: dict, model: str) -> None:
        self.content = content
        self.usage = usage
        self.model = model
        self.last_decode: dict = {}

    def send(self, request):  # noqa: ANN001 - test double
        self.last_decode = {
            "status": "ok_message_content",
            "usage": self.usage,
            "model": self.model,
        }
        return type("MockResponse", (), {"content": self.content})()


class _FailIfCalledTransport:
    def send(self, request):  # noqa: ANN001 - test double
        raise AssertionError("resume path must not send a duplicate request")


def _valid_existing_row_for_sample(sample_id: str) -> dict:
    raw_path = (
        v2.V1_EVIDENCE_DIR / "arms" / "111" / "raw_responses.jsonl"
    )
    rows = core._read_jsonl(raw_path)
    for row in rows:
        if str(row.get("sample_id")) == sample_id:
            return row
    raise AssertionError(f"no existing v1 row for sample {sample_id}")


def test_v2_resume_does_not_resend_completed_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(core.base, "_require_beijing_off_peak", lambda: None)
    monkeypatch.setattr(
        core,
        "evaluate_coarse",
        lambda gold, attempts, method_id: {
            "primary_metric": "coarse_five_field_mean_f1",
            "coarse_five_field_mean_f1": 0.0,
            "coarse_five_field_micro": {"f1": 0.0},
            "modality_labels": {"macro_f1": 0.0},
            "denominator": len(attempts),
            "failed_count": 0,
        },
    )
    rows = core.samples(150)
    sample = rows[0]
    persisted = _valid_existing_row_for_sample(sample["sample_id"])
    budget = core._load_budget(
        v2.BUDGET_PATH, planned_calls=600, call_cap=750)
    gold_doc = core._read_json(core.FORMAL_GOLD)
    out_dir = tmp_path / "dev"

    gate1 = core.AblationBudgetGate(budget, core.MODEL_ALIAS)
    transport = _MockTransport(
        persisted["raw_response_content"],
        persisted.get("usage") or {"prompt_tokens": 1, "completion_tokens": 1},
        persisted.get("returned_model") or core.MODEL_ALIAS,
    )
    first = core._run_arm(
        "000", [sample], transport, gate1, budget, gold_doc, out_dir=out_dir)
    assert first["manifest"]["actual_call_count"] == 1
    assert first["manifest"]["resumed_completed_count"] == 0

    gate2 = core.AblationBudgetGate(budget, core.MODEL_ALIAS)
    second = core._run_arm(
        "000", [sample], _FailIfCalledTransport(), gate2, budget, gold_doc,
        out_dir=out_dir)
    assert second["manifest"]["actual_call_count"] == 0
    assert second["manifest"]["resumed_completed_count"] == 1
    assert gate2.calls_made == 0


def test_v2_evaluator_accepts_future_failed_rows_and_keeps_denominator():
    rows = core.samples(150)
    gold_doc = core._read_json(core.FORMAL_GOLD)
    attempts = [{
        "sample_id": row["sample_id"],
        "request_status": "failed",
        "record": {},
    } for row in rows]
    result = evaluate_coarse(
        gold_doc,
        attempts,
        method_id="offline_future_failure_test",
    )
    assert result["denominator"] == 150
    assert result["failed_count"] == 150
    assert result["primary_metric"] == "coarse_five_field_mean_f1"

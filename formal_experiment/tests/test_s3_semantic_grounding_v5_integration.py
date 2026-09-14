"""Offline integration regressions for the production v5 entry point."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (
    LLMGroundingExecutionError, MockSemanticGroundingTransport, append_ledger,
    build_request_set, execute_fallback,
)
from bpc_hybrid.s3_semantic_grounding_v5 import build_fallback_pack
from bpc_hybrid.s3_semantic_grounding_v5_integration import (
    apply_execution, bind_execution_directory, evaluate_rows, prepare_inputs,
)
from test_s3_semantic_grounding_v4 import make_record, make_row, unknown_condition_checks


def runner_module():
    spec = importlib.util.spec_from_file_location(
        "s3_v5_integration_runner", ROOT / "scripts/run_s3_semantic_grounding_llm_v2.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pair_fixture():
    rows, contexts = [], {}
    for side, condition in (("variant", None), ("control", "consent obtained")):
        checks = unknown_condition_checks()
        checks["constraint_violated"] = {
            "status": "unknown", "observable": False, "violation": None,
            "reason": "unsupported_abstract_constraint_kind"}
        row = make_row(checks=checks, constraint="without undue delay",
                       record=make_record(condition=condition))
        row.update({"item_id": "pair", "side": side})
        if condition is None:
            row["compact_local_context"]["condition_evidence"] = []
            row["compact_local_context"]["evidence_ids"] = []
        contexts[len(rows)] = row.pop("_grounding_context")
        rows.append(row)
    pack = build_fallback_pack(rows)
    config = {"model": "fake-model", "max_output_tokens_per_call": 512,
              "run_root_name": "isolated_mock"}
    request_set = build_request_set(pack, config)
    prepared = {"rows": rows, "contexts": contexts, "panel": {"variants": [{
        "variant_id": "pair", "expected_violation": "required_condition_not_enforced"}]}}
    return prepared, pack, request_set, config


def test_production_config_separates_modes_and_binding_refuses_contamination(tmp_path):
    runner = runner_module()
    assert runner._llm_config("mock")["run_root_name"] != runner._llm_config("real")["run_root_name"]
    prepared, pack, requests, config = pair_fixture()
    bind_execution_directory(tmp_path, config, "mock", pack, requests, "predictions")
    with pytest.raises(LLMGroundingExecutionError, match="mode_or_inputs_mismatch"):
        bind_execution_directory(tmp_path, config, "real", pack, requests, "predictions")
    with pytest.raises(LLMGroundingExecutionError, match="mode_or_inputs_mismatch"):
        bind_execution_directory(tmp_path, config, "mock", pack, requests, "changed")


def test_existing_unbound_execution_directory_is_not_adopted(tmp_path):
    _, pack, requests, config = pair_fixture()
    run_root = tmp_path / config["run_root_name"]
    run_root.mkdir()
    (run_root / "normalized_grounding.jsonl").write_text("old evidence", encoding="utf-8")
    with pytest.raises(LLMGroundingExecutionError, match="legacy_execution_directory_unbound"):
        bind_execution_directory(tmp_path, config, "real", pack, requests, "predictions")


def test_responses_reach_program_checks_both_pair_sides_and_resume(tmp_path):
    prepared, pack, requests, config = pair_fixture()
    before = copy.deepcopy(prepared["rows"])
    first = execute_fallback(pack=pack, request_set=requests, config=config,
                             output_root=tmp_path, mode="mock")
    after = apply_execution(prepared, pack, requests, first)
    metrics = evaluate_rows(before, after, prepared["panel"])
    assert after[0]["checks"]["required_condition_not_enforced"]["violation"] is True
    assert after[1]["checks"]["required_condition_not_enforced"]["violation"] is False
    assert all(r["action_grounding"]["activity_id"] == "A2" for r in after)
    assert all("llm_application" in r for r in after)
    assert all(r["checks"]["constraint_violated"]["violation"] is None for r in after)
    assert metrics["after"]["pair_success_count"] == 1
    assert metrics["transitions"]["variant"]["unknown_to_correct"] == 1
    assert metrics["transitions"]["control"]["unknown_to_correct"] == 1
    assert before == prepared["rows"]

    transport = MockSemanticGroundingTransport()
    resumed = execute_fallback(pack=pack, request_set=requests, config=config,
                               output_root=tmp_path, mode="mock", transport=transport)
    assert transport.seen == 0
    assert apply_execution(prepared, pack, requests, resumed) == after
    drift = copy.deepcopy(resumed)
    drift["results"][0]["source_index"] = 1
    with pytest.raises(LLMGroundingExecutionError, match="result_binding_mismatch"):
        apply_execution(prepared, pack, requests, drift)


def test_shared_body_is_sent_charged_once_and_restored_to_each_object(tmp_path):
    prepared, _, _, config = pair_fixture()
    # Identical model inputs on different evaluation sides must share a response,
    # while their source indices and evaluation identities stay distinct.
    row = copy.deepcopy(prepared["rows"][0])
    second = copy.deepcopy(row)
    second["side"] = "control"
    pack = build_fallback_pack([row, second])
    requests = build_request_set(pack, config)
    assert requests["request_count"] == 2
    transport = MockSemanticGroundingTransport()
    first = execute_fallback(pack=pack, request_set=requests, config=config,
                             output_root=tmp_path, mode="mock", transport=transport)
    assert transport.seen == 1
    assert first["requested_object_count"] == 2
    assert first["unique_request_count"] == 1
    assert first["no_double_send"] is True
    assert [r["source_index"] for r in first["results"]] == [0, 1]
    assert len({r["fallback_item_id"] for r in first["results"]}) == 2
    transport2 = MockSemanticGroundingTransport()
    resumed = execute_fallback(pack=pack, request_set=requests, config=config,
                               output_root=tmp_path, mode="mock", transport=transport2)
    assert transport2.seen == 0
    assert resumed["total_input_tokens_actual"] == first["total_input_tokens_actual"]
    assert resumed["total_usd_actual"] == first["total_usd_actual"]
    assert [r["source_index"] for r in resumed["results"]] == [0, 1]


def test_interruption_after_send_started_is_never_retried(tmp_path):
    _, pack, requests, config = pair_fixture()
    ledger = tmp_path / config["run_root_name"] / "execution_ledger.jsonl"
    first_request = requests["requests"][0]
    append_ledger(ledger, {"state": "send_started",
                          "request_sha256": first_request["request_sha256"]})
    transport = MockSemanticGroundingTransport()
    summary = execute_fallback(pack=pack, request_set=requests, config=config,
                               output_root=tmp_path, mode="mock", transport=transport)
    assert transport.seen == 0
    assert summary["counts"]["in_doubt"] == 1
    assert summary["known_usage_complete"] is False
    assert summary["run_status"] != "complete"


def test_final_valid_response_with_unknown_usage_cannot_complete(tmp_path, monkeypatch):
    prepared, _, _, config = pair_fixture()
    pack = build_fallback_pack(prepared["rows"][:1])
    requests = build_request_set(pack, config)
    import bpc_hybrid.s3_semantic_grounding_llm_v1 as executor
    monkeypatch.setattr(executor, "_usage_from_raw",
                        lambda *args: (None, None, False, "missing_usage"))
    summary = execute_fallback(pack=pack, request_set=requests, config=config,
                               output_root=tmp_path, mode="mock")
    assert summary["counts"]["succeeded"] == 1
    assert summary["known_usage_complete"] is False
    assert summary["run_status"] == "partial"


def test_v5_anchor_guard_survives_llm_action_recheck(tmp_path):
    prepared, _, _, config = pair_fixture()
    row = prepared["rows"][0]
    context = prepared["contexts"][0]
    handler_text = "unless a high risk to the rights and freedoms is unlikely"
    context["sentence"].update({"exception": handler_text,
                                "constraint": "not later than 72 hours"})
    row["model_visible_rule_input"] = copy.deepcopy(context["sentence"])
    context["record"]["activities"][1]["name"] = handler_text
    row["action_grounding"]["candidates"][0]["label"] = handler_text
    row["compact_local_context"]["candidate_activities"][0]["label"] = handler_text
    row["compact_local_context"]["nodes"][0]["label"] = handler_text
    prepared["rows"] = [row]
    prepared["contexts"] = {0: context}
    pack = build_fallback_pack([row])
    requests = build_request_set(pack, config)
    summary = execute_fallback(pack=pack, request_set=requests, config=config,
                               output_root=tmp_path, mode="mock")
    after = apply_execution(prepared, pack, requests, summary)
    assert after[0]["checks"]["required_condition_not_enforced"]["violation"] is None
    assert after[0]["checks"]["constraint_violated"]["violation"] is None
    assert after[0]["post_llm_anchor_guard"]


def test_frozen_pack_context_and_request_identity_are_reconstructible():
    runner = runner_module()
    pack = runner.read_json(runner.V5_PACK)
    requests = build_request_set(pack, runner._llm_config("mock"))
    prepared = prepare_inputs(ROOT, pack, requests)
    assert len(prepared["rows"]) == 80
    assert len(prepared["contexts"]) == 22
    assert len({r["request_sha256"] for r in requests["requests"]}) == 18
    drift = copy.deepcopy(pack)
    drift["items"][0]["llm_visible_payload"]["rule_record"]["action"] = "altered"
    with pytest.raises(LLMGroundingExecutionError, match="frozen_pack_mismatch"):
        prepare_inputs(ROOT, drift, requests)


def test_latest_runner_publishes_predictions_before_evaluation(tmp_path, monkeypatch):
    runner = runner_module()
    monkeypatch.setattr(runner, "OUT_ROOT", tmp_path / "runs")
    monkeypatch.setattr(runner, "REPORT_ROOT", tmp_path / "reports")
    # Keep this runner test tiny; the separate frozen-input test covers all 22 contexts.
    prepared, pack, _, _ = pair_fixture()
    original_read = runner.read_json
    monkeypatch.setattr(runner, "read_json", lambda p: pack if p == runner.V5_PACK else original_read(p))
    monkeypatch.setattr(runner, "prepare_inputs", lambda *args: {
        **prepared, "input_hashes": {runner.PREDICTIONS: "fixture"}})
    original_publish = runner.publish_results
    monkeypatch.setattr(runner, "publish_results", lambda *args: original_publish(
        *args, publication_root=tmp_path / "evidence"))
    import bpc_hybrid.s3_semantic_grounding_v5_integration as integration
    original_evaluate = integration.evaluate_rows
    def evaluate_after_save(*args):
        assert (tmp_path / "evidence/attempt_001/predictions.jsonl").is_file()
        return original_evaluate(*args)
    monkeypatch.setattr(integration, "evaluate_rows", evaluate_after_save)
    monkeypatch.setattr(sys, "argv", ["runner", "--mock"])
    assert runner.main() == 0
    files = list((tmp_path / "evidence").glob("attempt_001/predictions.jsonl"))
    assert len(files) == 1
    rows = [json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    report = json.loads(files[0].with_name("comparison.json").read_text(encoding="utf-8"))
    assert report["mock_only_not_experimental"] is True
    assert report["after"]["pair_success_count"] == 1
    assert report["response_object_count"] == 2
    assert not (tmp_path / "runs" / "s3_semantic_grounding_llm_v2_real_run").exists()

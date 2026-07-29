"""Regression tests for the exact S2.8 H1 preregistration gate."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bpc_hybrid.sun_style.h1_selective import (  # noqa: E402
    CallBudget,
    H1ContractError,
    RepairPlan,
    allocate_repair_calls,
    apply_repair_patch,
    detect_repair_plan,
    load_s28_config,
    make_h1_attempt,
    render_h1_request,
)
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.stage2_evaluation import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.s2_8_gate import (  # noqa: E402
    S28_EXPECTATIONS,
    verify_s2_8_gate,
)
from formal_experiment.status import collect_status  # noqa: E402
from run_sun_llm_fallback import build_plans  # noqa: E402


CONFIG_PATH = ROOT / "configs" / "models" / "sun_h1_s28.json"
MANIFEST_PATH = ROOT / "outputs" / "reports" / "s26_sun_b0_canonical_composition_v3.manifest.json"


def _config() -> dict:
    return load_s28_config(CONFIG_PATH)


def _record() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["composition"]["synthetic_canonical_record"]


def test_s2_8_config_freezes_no_gold_and_hard_budget() -> None:
    config = _config()
    assert config["baseline_binding"]["legacy_front_end_allowed"] is False
    assert config["trigger_policy"]["evidence_boundary"] == "inference_time_observations_only_no_gold_or_test_distribution"
    assert config["budget"]["derived_max_calls"] == 45
    assert config["budget"]["max_requests_per_sample"] == 1
    assert config["budget"]["max_retries"] == 0
    assert config["budget"]["real_api_authorized"] is False
    assert config["model"]["exact_model_id"] == "gpt-4.1-2025-04-14"
    assert config["sampling"]["max_output_tokens"] == 2048
    assert config["budget"]["total_token_ceiling"] == 460800
    assert config["budget"]["hard_cost_ceiling_usd"] == 1.5


def test_clean_s2_6_record_does_not_trigger() -> None:
    plan = detect_repair_plan(
        _record(),
        {"parser_status": "ok", "modality_confidence": 0.97, "modality_margin": 0.8},
        _config(),
    )
    assert plan.fallback_triggered is False
    assert plan.repair_fields == ()


def test_action_trigger_adds_reference_dependency_closure() -> None:
    plan = detect_repair_plan(
        _record(),
        {"tregex_conflict_fields": ["actions"]},
        _config(),
    )
    assert plan.trigger_codes == ("tregex_field_conflict",)
    assert plan.repair_fields == ("actions", "actor_action_map", "order_relations")


def test_modality_thresholds_are_strictly_below() -> None:
    at_threshold = detect_repair_plan(
        _record(),
        {"modality_confidence": 0.6, "modality_margin": 0.15},
        _config(),
    )
    below = detect_repair_plan(
        _record(),
        {"modality_confidence": 0.599, "modality_margin": 0.149},
        _config(),
    )
    assert at_threshold.fallback_triggered is False
    assert below.trigger_codes == ("low_modality_confidence", "low_modality_margin")
    assert below.repair_fields == ("modality",)


@pytest.mark.parametrize("forbidden", ["gold_labels", "gold_spans", "test_metrics", "test_error_distribution"])
def test_gold_and_test_telemetry_is_rejected(forbidden: str) -> None:
    with pytest.raises(H1ContractError, match="forbidden"):
        detect_repair_plan(_record(), {forbidden: {}}, _config())


def test_unauthorized_patch_returns_original_b0_exactly() -> None:
    record = _record()
    plan = RepairPlan(
        sample_id=record["sample_id"],
        clause_id=record["clauses"][0]["clause_id"],
        trigger_codes=("tregex_field_conflict",),
        repair_fields=("actions", "actor_action_map", "order_relations"),
    )
    envelope = {
        "sample_id": plan.sample_id,
        "clause_id": plan.clause_id,
        "repair_fields": list(plan.repair_fields),
        "patches": {"modality": copy.deepcopy(record["clauses"][0]["modality"])},
        "unsupported_or_ambiguous": copy.deepcopy(
            record.get("unsupported_or_ambiguous", [])
        ),
        "reason": "unauthorized test",
    }
    result = apply_repair_patch(record, envelope, plan)
    assert result.accepted is False
    assert result.status == "rejected_unauthorized_field"
    assert result.record == record


def test_call_budget_accepts_45_then_fails_closed() -> None:
    budget = CallBudget(_config())
    assert all(budget.reserve(f"sample_{index:03d}")[0] for index in range(45))
    assert budget.reserve("sample_046") == (False, "global_budget_exhausted")
    assert budget.reserve("sample_000") == (False, "per_sample_limit_reached")


def test_allocation_and_request_rendering_are_order_invariant_and_exact() -> None:
    config = _config()
    record = _record()
    clause_id = record["clauses"][0]["clause_id"]
    real_plan = RepairPlan(
        sample_id=record["sample_id"],
        clause_id=clause_id,
        trigger_codes=("tregex_field_conflict",),
        repair_fields=("actions", "actor_action_map", "order_relations"),
    )
    request = render_h1_request(record, real_plan, load_prompt(config["prompt"]["name"]), config)
    assert request["model"] == "gpt-4.1-2025-04-14"
    assert request["sampling_contract"] == config["sampling"]
    assert request["api_request"]["model"] == "gpt-4.1-2025-04-14"
    assert request["api_request"]["max_completion_tokens"] == 2048
    assert request["api_request"]["response_format"] == {"type": "json_object"}
    assert [item["role"] for item in request["api_request"]["messages"]] == ["system", "user"]
    assert all(item["content"] for item in request["api_request"]["messages"])
    assert request["system_prompt_char_count"] > 0
    assert request["user_prompt_char_count"] > 0

    plans = [
        RepairPlan(
            sample_id=f"sample_{index:03d}",
            clause_id="c01",
            trigger_codes=("tregex_field_conflict",),
            repair_fields=("actions",),
        )
        for index in range(47)
    ]
    plans.append(
        RepairPlan(
            sample_id="sample_000",
            clause_id="c02",
            trigger_codes=("tregex_field_conflict",),
            repair_fields=("actions",),
        )
    )
    allocated = allocate_repair_calls(plans, config)
    assert allocated == allocate_repair_calls(list(reversed(plans)), config)
    assert sum(item["call_reserved"] for item in allocated) == 45
    by_key = {(item["sample_id"], item["clause_id"]): item for item in allocated}
    assert by_key[("sample_000", "c02")]["allocation_status"] == "per_sample_limit_reached"
    assert by_key[("sample_045", "c01")]["allocation_status"] == "global_budget_exhausted"


def test_recovered_provider_error_preserves_b0_and_remains_scorable_as_h1() -> None:
    record = _record()
    attempt = make_h1_attempt(
        record,
        runtime={
            "llm_call_performed": True,
            "prompt_tokens": 100,
            "completion_tokens": 0,
            "total_tokens": 100,
            "estimated_cost_usd": 0.0002,
            "latency_ms": 500,
        },
        recovered_runtime_error_category="timeout",
    )
    assert attempt["request_status"] == "ok"
    assert attempt["record"]["method"]["name"] == "sun_llm_fallback"
    assert {k: v for k, v in attempt["record"].items() if k != "method"} == {
        k: v for k, v in record.items() if k != "method"
    }
    report = evaluate_stage2(
        [record],
        [attempt],
        contract=load_evaluator_contract(ROOT / "configs" / "stage2_evaluator_s210.json"),
        dataset_id="s28_synthetic_fallback_test",
        method_id="sun_llm_fallback",
        expected_membership_sha256=membership_sha256([record]),
    )
    assert report["semantic_coverage"]["schema_valid_rate"] == 1.0
    assert report["semantic_coverage"]["api_error_rate"] == 0.0
    assert report["semantic_coverage"]["recovered_api_error_rate"] == 1.0


def test_offline_runner_rejects_duplicate_records_and_orphan_telemetry() -> None:
    record = _record()
    with pytest.raises(H1ContractError, match="duplicate B0 sample_id"):
        build_plans([record, copy.deepcopy(record)], {}, _config())
    with pytest.raises(H1ContractError, match="unknown B0 clauses"):
        build_plans(
            [record],
            {("unknown_sample", "c01"): {"parser_status": "ok"}},
            _config(),
        )


def test_s2_8_exact_hash_gate_is_ready() -> None:
    gate = verify_s2_8_gate(ROOT)
    assert gate["ready"] is True
    assert gate["hard_call_limit"] == 45
    assert gate["real_llm_authorized"] is False
    assert gate["llm_api_called"] is False


def test_s2_8_wrong_expected_hash_fails_closed() -> None:
    wrong = replace(S28_EXPECTATIONS, config_sha256="0" * 64)
    gate = verify_s2_8_gate(ROOT, expectations=wrong)
    assert gate["ready"] is False
    assert "s2_8_config_hash_mismatch" in gate["blockers"]


def test_status_and_audit_report_verified_s2_8_without_formal_readiness() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    warning_codes = {item["code"] for item in audit["findings"]["warnings"]}
    assert status["s2_8_verified"] is True
    assert status["final_experiment_ready"] is False
    assert "s2_8_h1_preregistration_verified" in pass_codes
    assert "h1_uses_verified_s2_6_front_end" in pass_codes
    assert "h1_still_uses_legacy_front_end" not in warning_codes

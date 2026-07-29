"""Verify the locked S2.8 H1 contract without a real LLM or network call."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import build_manifest_entry, load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from bpc_hybrid.stage2_evaluation import (  # noqa: E402
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)
from bpc_hybrid.sun_style.h1_selective import (  # noqa: E402
    H1ContractError,
    RepairPlan,
    allocate_repair_calls,
    apply_repair_patch,
    detect_repair_plan,
    load_s28_config,
    make_h1_attempt,
    render_h1_request,
    sha256_file,
)
from formal_experiment.s2_6_gate import verify_s2_6_gate  # noqa: E402


DEFAULT_CONFIG = ROOT / "configs" / "models" / "sun_h1_s28.json"
EVALUATOR_CONFIG = ROOT / "configs" / "stage2_evaluator_s210.json"
EVALUATOR_REPORT_SCHEMA = ROOT / "configs" / "schemas" / "stage2_evaluation_report.schema.json"


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise H1ContractError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise H1ContractError(f"JSON root must be an object: {path}")
    return value


def _locked_b0_record(config: Mapping[str, Any]) -> dict[str, Any]:
    spec = config["baseline_binding"]["verification_manifest"]
    path = _project_path(spec["path"])
    if not path.is_file() or sha256_file(path) != spec["sha256"]:
        raise H1ContractError("locked S2.6 manifest is missing or hash-mismatched")
    record = _load_object(path).get("composition", {}).get("synthetic_canonical_record")
    if not isinstance(record, dict):
        raise H1ContractError("locked S2.6 record is missing")
    return record


def _mock_action_patch(record: Mapping[str, Any], repair_fields: list[str]) -> dict[str, Any]:
    clause = record["clauses"][0]
    action_id = clause["actions"][0]["id"]
    actor_id = clause["actors"][0]["id"]
    return {
        "sample_id": record["sample_id"],
        "clause_id": clause["clause_id"],
        "repair_fields": repair_fields,
        "patches": {
            "actions": [
                {
                    "id": action_id,
                    "text": "file within 30 days",
                    "start": 41,
                    "end": 60,
                    "normalized": "file within 30 days",
                }
            ],
            "actor_action_map": [
                {"actor_id": actor_id, "action_id": action_id}
            ],
            "order_relations": [],
        },
        "unsupported_or_ambiguous": copy.deepcopy(
            record.get("unsupported_or_ambiguous", [])
        ),
        "reason": "Deterministic mock expands the conflicted action span.",
    }


def run(config_path: Path) -> dict[str, Any]:
    config = load_s28_config(config_path)
    s26_gate = verify_s2_6_gate(ROOT)
    if s26_gate.get("ready") is not True:
        raise H1ContractError("verified S2.6 B0 gate is not ready")
    prompt = load_prompt(config["prompt"]["name"])
    if prompt.sha256 != config["prompt"]["sha256"]:
        raise H1ContractError("locked H1 prompt hash mismatch")
    extraction_spec = config["extraction_contract"]
    extraction_path = _project_path(extraction_spec["path"])
    if (
        not extraction_path.is_file()
        or sha256_file(extraction_path) != extraction_spec["sha256"]
    ):
        raise H1ContractError("locked Stage 2 extraction contract is hash-mismatched")
    baseline_config = config["baseline_binding"]["config"]
    baseline_path = _project_path(baseline_config["path"])
    if not baseline_path.is_file() or sha256_file(baseline_path) != baseline_config["sha256"]:
        raise H1ContractError("locked S2.6 config hash mismatch")
    record = _locked_b0_record(config)

    clean_plan = detect_repair_plan(
        record,
        {
            "parser_status": "ok",
            "modality_confidence": 0.97,
            "modality_margin": 0.8,
        },
        config,
    )
    if clean_plan.fallback_triggered:
        raise H1ContractError("clean locked B0 record unexpectedly triggered H1")

    triggered_plan = detect_repair_plan(
        record,
        {
            "parser_status": "ok",
            "tregex_conflict_fields": ["actions"],
            "modality_confidence": 0.97,
            "modality_margin": 0.8,
        },
        config,
    )
    expected_fields = ("actions", "actor_action_map", "order_relations")
    if triggered_plan.trigger_codes != ("tregex_field_conflict",):
        raise H1ContractError("trigger code is not deterministic")
    if triggered_plan.repair_fields != expected_fields:
        raise H1ContractError("action dependency closure changed")
    rendered_request = render_h1_request(record, triggered_plan, prompt, config)
    api_request = rendered_request["api_request"]
    messages = api_request.get("messages")
    messages_valid = (
        isinstance(messages, list)
        and len(messages) == 2
        and messages[0] == {"role": "system", "content": prompt.system_prompt}
        and isinstance(messages[1], Mapping)
        and messages[1].get("role") == "user"
        and isinstance(messages[1].get("content"), str)
        and bool(messages[1]["content"])
    )
    user_message = messages[1]["content"] if messages_valid else ""
    if (
        rendered_request["model"] != "gpt-4.1-2025-04-14"
        or rendered_request["sampling_contract"] != config["sampling"]
        or api_request.get("model") != "gpt-4.1-2025-04-14"
        or not messages_valid
        or api_request.get("temperature") != 0
        or api_request.get("top_p") != 1
        or api_request.get("max_completion_tokens") != 2048
        or api_request.get("response_format") != {"type": "json_object"}
        or "seed" in api_request
        or "max_tokens" in api_request
        or rendered_request["system_prompt_char_count"] <= 0
        or rendered_request["user_prompt_char_count"] <= 0
        or rendered_request["system_prompt_sha256"]
        != hashlib.sha256(prompt.system_prompt.encode("utf-8")).hexdigest()
        or rendered_request["user_prompt_sha256"]
        != hashlib.sha256(user_message.encode("utf-8")).hexdigest()
    ):
        raise H1ContractError("exact H1 request rendering changed")

    accepted = apply_repair_patch(
        record,
        _mock_action_patch(record, list(triggered_plan.repair_fields)),
        triggered_plan,
    )
    if not accepted.accepted:
        raise H1ContractError(f"deterministic mock patch was rejected: {accepted.errors}")
    report = validate_canonical(accepted.record)
    if not (report.schema_valid and report.cross_field_valid):
        raise H1ContractError("accepted mock patch is not canonical")
    for field in ("modality", "actors", "conditions", "constraints", "exceptions"):
        if accepted.record["clauses"][0][field] != record["clauses"][0][field]:
            raise H1ContractError(f"unrequested field changed: {field}")
    if accepted.record.get("unsupported_or_ambiguous", []) != record.get(
        "unsupported_or_ambiguous", []
    ):
        raise H1ContractError("controlled uncertainty metadata changed unexpectedly")

    rejected_envelope = _mock_action_patch(record, list(triggered_plan.repair_fields))
    rejected_envelope["patches"] = copy.deepcopy(rejected_envelope["patches"])
    rejected_envelope["patches"]["modality"] = copy.deepcopy(record["clauses"][0]["modality"])
    rejected = apply_repair_patch(record, rejected_envelope, triggered_plan)
    if rejected.accepted or rejected.record != record:
        raise H1ContractError("unauthorized patch did not preserve the original B0 record")

    allocation_plans = [
        RepairPlan(
            sample_id=f"allocation_{index:03d}",
            clause_id="c01",
            trigger_codes=("tregex_field_conflict",),
            repair_fields=expected_fields,
        )
        for index in range(47)
    ]
    allocation_plans.append(
        RepairPlan(
            sample_id="allocation_000",
            clause_id="c02",
            trigger_codes=("tregex_field_conflict",),
            repair_fields=expected_fields,
        )
    )
    allocations = allocate_repair_calls(allocation_plans, config)
    reversed_allocations = allocate_repair_calls(list(reversed(allocation_plans)), config)
    if allocations != reversed_allocations:
        raise H1ContractError("H1 allocation depends on input array order")
    reserved = [item for item in allocations if item["call_reserved"]]
    by_key = {(item["sample_id"], item["clause_id"]): item for item in allocations}
    if (
        len(reserved) != 45
        or by_key[("allocation_000", "c02")]["allocation_status"] != "per_sample_limit_reached"
        or by_key[("allocation_045", "c01")]["allocation_status"] != "global_budget_exhausted"
        or by_key[("allocation_046", "c01")]["allocation_status"] != "global_budget_exhausted"
    ):
        raise H1ContractError("deterministic hard-budget allocation changed")

    recovered_attempt = make_h1_attempt(
        record,
        runtime={
            "llm_call_performed": True,
            "prompt_tokens": 128,
            "completion_tokens": 0,
            "total_tokens": 128,
            "estimated_cost_usd": 0.000256,
            "latency_ms": 1000,
        },
        recovered_runtime_error_category="timeout",
    )
    evaluator_contract = load_evaluator_contract(EVALUATOR_CONFIG)
    fallback_report = evaluate_stage2(
        [record],
        [recovered_attempt],
        contract=evaluator_contract,
        dataset_id="s28_synthetic_fallback_contract_v1",
        method_id="sun_llm_fallback",
        expected_membership_sha256=membership_sha256([record]),
    )
    report_errors = validate_evaluation_report(fallback_report)
    fallback_coverage = fallback_report["semantic_coverage"]
    if (
        report_errors
        or fallback_coverage["schema_valid_rate"] != 1.0
        or fallback_coverage["api_error_rate"] != 0.0
        or fallback_coverage["recovered_api_error_rate"] != 1.0
        or fallback_coverage["any_api_error_rate"] != 1.0
        or fallback_report["primary_metrics"]["modality"]["per_class"]
        [record["clauses"][0]["modality"]["label"]]["f1"]
        != 1.0
    ):
        raise H1ContractError("recovered-provider-error B0 fallback is not scorable")

    implementation_paths = {
        "config": config_path,
        "implementation": ROOT / "src" / "bpc_hybrid" / "sun_style" / "h1_selective.py",
        "runner": ROOT / "scripts" / "run_sun_llm_fallback.py",
        "verifier": ROOT / "scripts" / "verify_sun_h1_s28.py",
        "prompt": _project_path(config["prompt"]["path"]),
        "extraction_contract": extraction_path,
        "evaluator_config": EVALUATOR_CONFIG,
        "evaluator_report_schema": EVALUATOR_REPORT_SCHEMA,
    }
    return {
        "schema_version": "sun_h1_s28_verification_manifest@1.2.0",
        "task_id": "S2.8",
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "sun_llm_fallback",
        "claim_boundary": config["claim_boundary"],
        "runtime": {"python": platform.python_version()},
        "artifacts": {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in implementation_paths.items()
        },
        "baseline_binding": {
            "s2_6_gate_ready": True,
            "legacy_front_end_used": False,
            "record_method": record["method"]["name"],
            "verification_manifest": config["baseline_binding"]["verification_manifest"],
        },
        "selection": {
            "evidence_boundary": config["trigger_policy"]["evidence_boundary"],
            "clean_plan": clean_plan.to_dict(),
            "triggered_plan": triggered_plan.to_dict(),
            "gold_or_test_derived_trigger_used": False,
        },
        "merge_verification": {
            "accepted_patch": accepted.to_summary(),
            "accepted_record": accepted.record,
            "unrequested_fields_preserved": True,
            "same_field_id_preserved": True,
            "unauthorized_patch": rejected.to_summary(),
            "rejected_patch_returned_original_b0": rejected.record == record,
            "controlled_uncertainty_metadata_preserved": True,
        },
        "request_verification": {
            "exact_model_id": config["model"]["exact_model_id"],
            "sampling": config["sampling"],
            "rendered_request": rendered_request,
            "prompt_file_sha256_matches": True,
            "unrendered_placeholder_detected": False,
        },
        "allocation_verification": {
            "candidate_order": config["allocation_policy"]["candidate_order"],
            "input_array_order_invariant": True,
            "candidate_count": len(allocations),
            "reserved_call_count": len(reserved),
            "first_45_unique_reserved": True,
            "call_46_and_later_rejected": True,
            "duplicate_sample_rejected": True,
        },
        "budget_verification": {
            "target_dataset_size": 150,
            "max_call_fraction": 0.3,
            "hard_call_limit": config["budget"]["derived_max_calls"],
            "input_token_ceiling_per_request": config["budget"]["input_token_ceiling_per_request"],
            "output_token_ceiling_per_request": config["budget"]["output_token_ceiling_per_request"],
            "total_token_ceiling": config["budget"]["total_token_ceiling"],
            "estimated_worst_case_cost_usd": config["budget"]["estimated_worst_case_cost_usd"],
            "hard_cost_ceiling_usd": config["budget"]["hard_cost_ceiling_usd"],
            "max_retries": 0,
        },
        "fallback_attempt_verification": {
            "request_status": recovered_attempt["request_status"],
            "record_method": recovered_attempt["record"]["method"]["name"],
            "semantic_b0_content_preserved": {
                key: value
                for key, value in recovered_attempt["record"].items()
                if key != "method"
            }
            == {key: value for key, value in record.items() if key != "method"},
            "recovered_runtime_error_category": recovered_attempt[
                "recovered_runtime_error_category"
            ],
            "schema_valid_rate": fallback_coverage["schema_valid_rate"],
            "terminal_api_error_rate": fallback_coverage["api_error_rate"],
            "recovered_api_error_rate": fallback_coverage["recovered_api_error_rate"],
            "any_api_error_rate": fallback_coverage["any_api_error_rate"],
            "scored_as_h1": True,
        },
        "prompt": build_manifest_entry(prompt, role="repair_patch"),
        "safety": {
            "synthetic_fixture_only": True,
            "performance_evaluation": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "test_split_read_or_evaluated": False,
            "formal_predictions_written": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()
    config_path = args.config.resolve()
    target = args.manifest_out.resolve()
    if target.exists():
        raise H1ContractError(f"refusing to overwrite: {target}")
    manifest = run(config_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

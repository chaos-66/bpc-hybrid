"""Verify the locked S2.9 D1 contract without an API, network, or ``.env``."""

from __future__ import annotations

import argparse
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

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.sun_style.d1_direct import (  # noqa: E402
    D1ContractError,
    build_request_plan,
    load_s29_config,
    make_attempt,
    render_d1_request,
    sha256_file,
    sha256_text,
    summarize_attempts,
    validate_input_rows,
)
from formal_experiment.s2_10_evaluator_gate import verify_s2_10_evaluator_gate  # noqa: E402


DEFAULT_CONFIG = ROOT / "configs" / "models" / "sun_d1_s29.json"
DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "d1_s29" / "s29_offline_contract_fixture.json"


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise D1ContractError(f"invalid S2.9 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise D1ContractError(f"S2.9 JSON root must be an object: {path}")
    return value


def _canonical_json_sha256(value: Any) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _mock_attempts(
    fixture: Mapping[str, Any], rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    by_id = {row["sample_id"]: row for row in rows}
    attempts: list[dict[str, Any]] = []
    responses = fixture.get("primary_mock_responses")
    if not isinstance(responses, list):
        raise D1ContractError("S2.9 fixture has no primary_mock_responses")
    for response in responses:
        if not isinstance(response, Mapping):
            raise D1ContractError("S2.9 mock response must be an object")
        sample_id = response.get("sample_id")
        row = by_id.get(sample_id)
        if row is None:
            raise D1ContractError(f"mock response sample is not in fixture rows: {sample_id}")
        runtime = response.get("runtime")
        kind = response.get("kind")
        if kind == "canonical_json":
            content = json.dumps(response.get("payload"), ensure_ascii=False)
            attempt = make_attempt(
                row,
                repeat_index=1,
                runtime=runtime,
                response_content=content,
            )
        elif kind == "non_json":
            attempt = make_attempt(
                row,
                repeat_index=1,
                runtime=runtime,
                response_content=response.get("content"),
            )
        elif kind == "api_error":
            attempt = make_attempt(
                row,
                repeat_index=1,
                runtime=runtime,
                api_error_category=response.get("error_category"),
            )
        else:
            raise D1ContractError(f"unknown S2.9 mock response kind: {kind!r}")
        attempts.append(attempt)
    return attempts


def run(config_path: Path, fixture_path: Path) -> dict[str, Any]:
    config = load_s29_config(config_path)
    fixture = _load_object(fixture_path)
    if fixture.get("schema_version") != "s29_offline_contract_fixture@1.0.0":
        raise D1ContractError("S2.9 fixture identity mismatch")
    if fixture.get("safety") != {
        "synthetic_only": True,
        "fixture_is_gold": False,
        "fixture_is_performance_evaluation": False,
        "llm_api_called": False,
        "network_called": False,
    }:
        raise D1ContractError("S2.9 fixture safety boundary changed")

    prompt = load_prompt(config["prompt"]["name"])
    if prompt.sha256 != config["prompt"]["sha256"]:
        raise D1ContractError("locked D1 prompt hash mismatch")
    if len(prompt.few_shot_examples) != config["prompt"]["few_shot_count"]:
        raise D1ContractError("locked D1 few-shot count mismatch")
    rows = validate_input_rows(fixture.get("rows"), config)
    rendered = render_d1_request(rows[0], prompt, config)
    plan = build_request_plan(rows, prompt, config)
    verification = config["verification"]
    if (
        plan["input_count"] != verification["expected_input_count"]
        or plan["request_count"] != verification["expected_request_count"]
        or any(
            item["few_shot_count"] != verification["expected_few_shot_count_in_every_request"]
            for item in plan["requests"]
        )
    ):
        raise D1ContractError("D1 request plan does not match preregistered fixture expectations")
    request_ids = [item["request_id"] for item in plan["requests"]]
    if len(request_ids) != len(set(request_ids)):
        raise D1ContractError("D1 request IDs are not unique")

    attempts = _mock_attempts(fixture, rows)
    summary = summarize_attempts(attempts, rows, repeat_index=1)
    if (
        summary["canonical_valid_count"] != verification["expected_primary_valid_count"]
        or summary["schema_or_cross_field_invalid_count"]
        != verification["expected_primary_schema_invalid_count"]
        or summary["api_error_count"] != verification["expected_primary_api_error_count"]
        or summary["dropped_attempt_count"] != 0
    ):
        raise D1ContractError("D1 failure-preserving attempt contract changed")
    invalid_attempt = next(item for item in attempts if item.get("error_category") == "non_json")
    if "not valid json" in json.dumps(invalid_attempt, ensure_ascii=False):
        raise D1ContractError("raw D1 response leaked into an attempt envelope")

    s210_gate = verify_s2_10_evaluator_gate(ROOT)
    if s210_gate.get("ready") is not True:
        raise D1ContractError("S2.10-E evaluator gate is not ready")
    for spec_name in ("config", "report_schema", "verification_manifest"):
        spec = config["evaluator_binding"][spec_name]
        path = _project_path(spec["path"])
        if not path.is_file() or sha256_file(path) != spec["sha256"]:
            raise D1ContractError(f"locked S2.10-E {spec_name} is missing or hash-mismatched")
    schema_spec = config["canonical_contract"]["schema"]
    schema_path = _project_path(schema_spec["path"])
    if not schema_path.is_file() or sha256_file(schema_path) != schema_spec["sha256"]:
        raise D1ContractError("locked canonical schema is missing or hash-mismatched")
    extraction_spec = config["extraction_contract"]
    extraction_path = _project_path(extraction_spec["path"])
    if (
        not extraction_path.is_file()
        or sha256_file(extraction_path) != extraction_spec["sha256"]
    ):
        raise D1ContractError("locked Stage 2 extraction contract is hash-mismatched")

    implementation_paths = {
        "config": config_path,
        "implementation": ROOT / "src" / "bpc_hybrid" / "sun_style" / "d1_direct.py",
        "runner": ROOT / "scripts" / "run_direct_llm.py",
        "verifier": ROOT / "scripts" / "verify_sun_d1_s29.py",
        "prompt": prompt.path,
        "extraction_contract": extraction_path,
        "fixture": fixture_path,
    }
    return {
        "schema_version": "sun_d1_s29_verification_manifest@1.1.0",
        "task_id": "S2.9",
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "direct_llm",
        "claim_boundary": config["claim_boundary"],
        "runtime": {"python": platform.python_version()},
        "artifacts": {
            name: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path),
            }
            for name, path in implementation_paths.items()
        },
        "model_and_sampling": {
            "provider": config["model"]["provider"],
            "exact_model_id": config["model"]["exact_model_id"],
            "pin_type": config["model"]["pin_type"],
            "sampling": config["sampling"],
            "real_api_authorized": False,
        },
        "prompt_rendering": {
            "prompt_sha256": prompt.sha256,
            "few_shot_count_parsed": len(prompt.few_shot_examples),
            "few_shot_count_in_actual_request": rendered["few_shot_count"],
            "system_prompt_sha256": rendered["system_prompt_sha256"],
            "first_user_prompt_sha256": rendered["user_prompt_sha256"],
            "first_user_prompt_char_count": len(rendered["user_prompt"]),
            "unresolved_template_placeholder": "{few_shot_block}" in rendered["user_prompt"],
        },
        "request_plan": {
            "input_count": plan["input_count"],
            "repeat_count": plan["repeat_count"],
            "request_count": plan["request_count"],
            "unique_request_count": len(set(request_ids)),
            "primary_repeat_index": plan["primary_repeat_index"],
            "plan_sha256": _canonical_json_sha256(plan),
            "all_requests_have_four_few_shots": all(
                item["few_shot_count"] == 4 for item in plan["requests"]
            ),
        },
        "attempt_envelope_verification": {
            **summary,
            "attempts_sha256": _canonical_json_sha256(attempts),
            "raw_response_persisted": False,
            "invalid_and_api_attempts_retained": True,
            "s2_10_evaluator_gate_ready": True,
        },
        "budget_verification": {
            "target_dataset_size": config["budget"]["target_dataset_size"],
            "repeat_count": config["budget"]["repeat_count"],
            "hard_call_limit": config["budget"]["absolute_max_calls"],
            "max_retries": config["budget"]["max_retries"],
            "total_token_ceiling": config["budget"]["total_token_ceiling"],
            "estimated_worst_case_cost_usd": config["budget"]["estimated_worst_case_cost_usd"],
            "hard_cost_ceiling_usd": config["budget"]["hard_cost_ceiling_usd"],
        },
        "input_isolation": {
            "gold_visible_to_method": False,
            "b0_or_h1_prediction_visible": False,
            "rule_front_end_used": False,
            "same_future_frozen_input_required": True,
        },
        "safety": {
            "synthetic_fixture_only": True,
            "performance_evaluation": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "env_file_read": False,
            "test_split_read_or_evaluated": False,
            "formal_predictions_written": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--manifest-out", type=Path, required=True)
    args = parser.parse_args()
    target = args.manifest_out.resolve()
    if target.exists():
        raise D1ContractError(f"refusing to overwrite: {target}")
    manifest = run(args.config.resolve(), args.fixture.resolve())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "succeeded", "manifest": str(target)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

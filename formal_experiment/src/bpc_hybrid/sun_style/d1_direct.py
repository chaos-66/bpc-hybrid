"""Locked offline S2.9 contract for the direct-LLM (D1) method.

The module renders the exact prompt that a future authorized request would
send, builds the five-repeat request plan, and converts supplied responses to
the attempt envelope consumed by S2.10-E.  It never reads ``.env`` and has no
network transport.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.prompt_loader import LoadedPrompt, render_user_prompt
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, validate_canonical


S29_CONFIG_SCHEMA = "sun_d1_s29@1.1.0"
EXTRACTION_CONTRACT_ID = "stage2_extraction_contract@1.0.0"
EXTRACTION_CONTRACT_SHA256 = "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46"
ALLOWED_ROW_KEYS = frozenset({"sample_id", "source_id", "source_text", "data_role"})


class D1ContractError(ValueError):
    """Raised when the preregistered D1 boundary is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_s29_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise D1ContractError(f"invalid S2.9 config: {path}") from exc
    if not isinstance(config, dict):
        raise D1ContractError("S2.9 config root must be an object")
    if (
        config.get("schema_version") != S29_CONFIG_SCHEMA
        or config.get("task_id") != "S2.9"
        or config.get("method_id") != "direct_llm"
    ):
        raise D1ContractError("S2.9 config identity mismatch")

    boundary = config.get("input_boundary", {})
    if (
        boundary.get("same_future_frozen_input_as_b0_h1") is not True
        or boundary.get("rule_front_end_used") is not False
        or boundary.get("gold_visible_to_method") is not False
    ):
        raise D1ContractError("D1 input isolation changed")
    prompt = config.get("prompt", {})
    if (
        prompt.get("version") != 5
        or prompt.get("few_shot_count") != 4
        or prompt.get("few_shot_insertion")
        != "render_all_parsed_examples_into_few_shot_block"
    ):
        raise D1ContractError("D1 prompt/few-shot contract changed")
    extraction = config.get("extraction_contract", {})
    if (
        extraction.get("contract_id") != EXTRACTION_CONTRACT_ID
        or extraction.get("sha256") != EXTRACTION_CONTRACT_SHA256
        or extraction.get("input_policy") != "target_text_only"
    ):
        raise D1ContractError("D1 Stage 2 extraction contract binding changed")
    model = config.get("model", {})
    if (
        model.get("provider") != "openai_compatible"
        or model.get("api_family") != "chat_completions"
        or model.get("exact_model_id") != "gpt-4.1-2025-04-14"
        or model.get("pin_type") != "dated_snapshot"
        or model.get("real_api_authorized") is not False
    ):
        raise D1ContractError("D1 model snapshot changed or real API was enabled")
    sampling = config.get("sampling", {})
    if sampling != {
        "temperature": 0,
        "top_p": 1,
        "seed": None,
        "seed_policy": "unsupported_or_omitted",
        "max_output_tokens": 4096,
        "response_format": "json_object",
        "max_retries": 0,
    }:
        raise D1ContractError("D1 sampling contract changed")
    stability = config.get("stability", {})
    if (
        stability.get("repeat_count") != 5
        or stability.get("primary_repeat_index") != 1
        or stability.get("independent_requests") is not True
        or stability.get("each_repeat_evaluated_as_exact_membership_batch") is not True
    ):
        raise D1ContractError("D1 five-repeat stability contract changed")
    budget = config.get("budget", {})
    derived_calls = budget.get("target_dataset_size", -1) * stability.get("repeat_count", -1)
    derived_input = derived_calls * budget.get("input_token_ceiling_per_request", -1)
    derived_output = derived_calls * budget.get("output_token_ceiling_per_request", -1)
    price = budget.get("price_snapshot_usd_per_million", {})
    derived_cost = (
        derived_input * price.get("input", math.nan)
        + derived_output * price.get("output", math.nan)
    ) / 1_000_000
    if (
        budget.get("absolute_max_calls") != 750
        or budget.get("max_requests_per_sample_per_repeat") != 1
        or budget.get("max_retries") != 0
        or budget.get("total_input_token_ceiling") != derived_input
        or budget.get("total_output_token_ceiling") != derived_output
        or budget.get("total_token_ceiling") != derived_input + derived_output
        or not math.isclose(budget.get("estimated_worst_case_cost_usd", -1), derived_cost)
        or budget.get("hard_cost_ceiling_usd", -1) < derived_cost
        or budget.get("real_api_authorized") is not False
    ):
        raise D1ContractError("D1 call/token/cost budget changed or is inconsistent")
    canonical = config.get("canonical_contract", {})
    if (
        canonical.get("schema_source") != SCHEMA_SOURCE
        or canonical.get("method_name") != "direct_llm"
        or canonical.get("missing_or_invalid_attempts_may_not_be_dropped") is not True
    ):
        raise D1ContractError("D1 canonical/failure-preservation contract changed")
    return config


def assert_input_path_allowed(path: Path, config: Mapping[str, Any]) -> None:
    tokens = tuple(str(item).lower() for item in config["input_boundary"]["forbidden_path_tokens"])
    parts = tuple(part.lower() for part in Path(path).resolve().parts)
    matched = sorted({token for token in tokens if any(token in part for part in parts)})
    if matched:
        raise D1ContractError(f"D1 refuses Gold/human-review input paths: {matched}")


def validate_input_rows(
    rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> list[dict[str, str]]:
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows:
        raise D1ContractError("D1 input rows must be a non-empty sequence")
    allowed_roles = set(config["input_boundary"]["allowed_data_roles"])
    forbidden_keys = set(config["input_boundary"]["forbidden_row_keys"])
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, raw in enumerate(rows):
        if not isinstance(raw, Mapping):
            raise D1ContractError(f"input row {index} must be an object")
        row = dict(raw)
        forbidden = forbidden_keys & set(row)
        unknown = set(row) - ALLOWED_ROW_KEYS
        if forbidden:
            raise D1ContractError(f"input row {index} exposes forbidden evidence: {sorted(forbidden)}")
        if unknown:
            raise D1ContractError(f"input row {index} has unregistered keys: {sorted(unknown)}")
        sample_id = row.get("sample_id")
        source_id = row.get("source_id")
        source_text = row.get("source_text")
        data_role = row.get("data_role")
        if not all(isinstance(value, str) and value for value in (sample_id, source_id, source_text)):
            raise D1ContractError(f"input row {index} needs non-empty sample_id/source_id/source_text")
        if data_role not in allowed_roles:
            raise D1ContractError(f"input row {index} has forbidden data_role: {data_role!r}")
        if sample_id in seen:
            raise D1ContractError(f"duplicate D1 sample_id: {sample_id}")
        seen.add(sample_id)
        result.append(
            {
                "sample_id": sample_id,
                "source_id": source_id,
                "source_text": source_text,
                "data_role": data_role,
            }
        )
    return result


def render_few_shot_block(prompt: LoadedPrompt) -> str:
    if len(prompt.few_shot_examples) != 4:
        raise D1ContractError("D1 requires exactly four parsed few-shot examples")
    rendered: list[str] = []
    for index, example in enumerate(prompt.few_shot_examples, start=1):
        description = str(example.get("description") or f"Example {index}").strip()
        input_text = str(example.get("input") or "").strip()
        output = example.get("output")
        if not isinstance(output, dict):
            raise D1ContractError(f"few-shot example {index} has no JSON object output")
        rendered.extend(
            [
                description,
                f"Input: {input_text}",
                "Output:",
                json.dumps(output, ensure_ascii=False, indent=2),
            ]
        )
    return "\n\n".join(rendered)


def render_d1_request(
    row: Mapping[str, str], prompt: LoadedPrompt, config: Mapping[str, Any]
) -> dict[str, Any]:
    if prompt.sha256 != config["prompt"]["sha256"]:
        raise D1ContractError("D1 prompt SHA-256 changed")
    few_shot_block = render_few_shot_block(prompt)
    user_prompt = render_user_prompt(
        prompt.user_prompt_template,
        sample_id=row["sample_id"],
        source_id=row["source_id"],
        source_text=row["source_text"],
        few_shot_block=few_shot_block,
    )
    if "{few_shot_block}" in user_prompt or user_prompt.count('"schema_version": "1.0.0"') < 4:
        raise D1ContractError("actual D1 user prompt does not contain all four rendered examples")
    return {
        "system_prompt": prompt.system_prompt,
        "user_prompt": user_prompt,
        "system_prompt_sha256": sha256_text(prompt.system_prompt),
        "user_prompt_sha256": sha256_text(user_prompt),
        "few_shot_count": 4,
    }


def build_request_plan(
    rows: Sequence[Mapping[str, Any]], prompt: LoadedPrompt, config: Mapping[str, Any]
) -> dict[str, Any]:
    inputs = validate_input_rows(rows, config)
    repeat_count = int(config["stability"]["repeat_count"])
    expected_calls = len(inputs) * repeat_count
    if expected_calls > config["budget"]["absolute_max_calls"]:
        raise D1ContractError("D1 request plan exceeds the 750-call ceiling")
    requests: list[dict[str, Any]] = []
    seen_request_ids: set[str] = set()
    for repeat_index in range(1, repeat_count + 1):
        for row in inputs:
            rendered = render_d1_request(row, prompt, config)
            request_id = f"{row['sample_id']}:r{repeat_index:02d}"
            if request_id in seen_request_ids:
                raise D1ContractError(f"duplicate D1 request_id: {request_id}")
            seen_request_ids.add(request_id)
            requests.append(
                {
                    "request_id": request_id,
                    "sample_id": row["sample_id"],
                    "source_id": row["source_id"],
                    "source_text_sha256": sha256_text(row["source_text"]),
                    "data_role": row["data_role"],
                    "repeat_index": repeat_index,
                    "model": config["model"]["exact_model_id"],
                    "sampling": copy.deepcopy(config["sampling"]),
                    "system_prompt_sha256": rendered["system_prompt_sha256"],
                    "user_prompt_sha256": rendered["user_prompt_sha256"],
                    "user_prompt_char_count": len(rendered["user_prompt"]),
                    "few_shot_count": rendered["few_shot_count"],
                }
            )
    return {
        "schema_version": "sun_d1_s29_request_plan@1.0.0",
        "task_id": "S2.9",
        "method_id": "direct_llm",
        "mode": "offline_plan_only",
        "input_count": len(inputs),
        "repeat_count": repeat_count,
        "request_count": len(requests),
        "primary_repeat_index": config["stability"]["primary_repeat_index"],
        "requests": requests,
        "safety": {
            "gold_visible_to_method": False,
            "rule_front_end_used": False,
            "env_file_read": False,
            "llm_api_called": False,
            "network_called": False,
            "formal_predictions_written": False,
        },
    }


def _runtime(runtime: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "llm_call_performed",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "estimated_cost_usd",
        "latency_ms",
    )
    if not isinstance(runtime, Mapping) or any(key not in runtime for key in required):
        raise D1ContractError("D1 runtime accounting is incomplete")
    result = {key: runtime[key] for key in required}
    if result["llm_call_performed"] not in (True, False):
        raise D1ContractError("runtime.llm_call_performed must be boolean")
    for key in required[1:]:
        value = result[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise D1ContractError(f"runtime.{key} must be a non-negative number")
    if result["total_tokens"] != result["prompt_tokens"] + result["completion_tokens"]:
        raise D1ContractError("D1 runtime token totals disagree")
    return result


def _invalid_record(row: Mapping[str, str], category: str, response_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": "invalid_response",
        "sample_id": row["sample_id"],
        "source_id": row["source_id"],
        "source_text": row["source_text"],
        "clauses": [],
        "method": {"name": "direct_llm", "schema_source": SCHEMA_SOURCE},
        "validation": {"schema_valid": False, "cross_field_valid": False, "errors": [category]},
        "unsupported_or_ambiguous": [],
        "rejected_response": {"category": category, "sha256": response_sha256},
    }


def make_attempt(
    row: Mapping[str, str],
    *,
    repeat_index: int,
    runtime: Mapping[str, Any],
    response_content: str | None = None,
    api_error_category: str | None = None,
) -> dict[str, Any]:
    """Convert one supplied response to an S2.10-E-compatible attempt.

    Raw response text is never persisted.  Non-JSON, non-object, or identity
    mismatches become an explicitly schema-invalid sentinel record so they stay
    in the evaluator denominator without corrupting batch membership.
    """

    runtime_record = _runtime(runtime)
    if not isinstance(repeat_index, int) or not 1 <= repeat_index <= 5:
        raise D1ContractError("repeat_index must be in 1..5")
    if api_error_category is not None:
        if response_content is not None or not api_error_category.strip():
            raise D1ContractError("API-error attempt must have no response content and a category")
        return {
            "sample_id": row["sample_id"],
            "repeat_index": repeat_index,
            "request_status": "api_error",
            "record": None,
            "error_category": api_error_category,
            "response_sha256": None,
            "runtime": runtime_record,
        }
    if not isinstance(response_content, str):
        raise D1ContractError("successful transport attempt requires string response_content")
    response_sha = sha256_text(response_content)
    category: str | None = None
    try:
        payload = json.loads(response_content)
    except json.JSONDecodeError:
        payload = None
        category = "non_json"
    if not isinstance(payload, dict):
        category = category or "non_object_json"
        record = _invalid_record(row, category, response_sha)
    elif (
        payload.get("sample_id") != row["sample_id"]
        or payload.get("source_id") != row["source_id"]
        or payload.get("source_text") != row["source_text"]
        or not isinstance(payload.get("method"), Mapping)
        or payload["method"].get("name") != "direct_llm"
    ):
        category = "identity_mismatch"
        record = _invalid_record(row, category, response_sha)
    else:
        record = copy.deepcopy(payload)
        report = validate_canonical(record)
        if not report.schema_valid:
            category = "schema_invalid"
        elif not report.cross_field_valid:
            category = "cross_field_invalid"
    return {
        "sample_id": row["sample_id"],
        "repeat_index": repeat_index,
        "request_status": "ok",
        "record": record,
        "error_category": category,
        "response_sha256": response_sha,
        "runtime": runtime_record,
    }


def summarize_attempts(
    attempts: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, str]], repeat_index: int
) -> dict[str, Any]:
    selected = [dict(item) for item in attempts if item.get("repeat_index") == repeat_index]
    expected_ids = {row["sample_id"] for row in rows}
    actual_ids = [item.get("sample_id") for item in selected]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != expected_ids:
        raise D1ContractError("D1 attempt membership is not exact for the selected repeat")
    valid = 0
    invalid = 0
    api_errors = 0
    for attempt in selected:
        if attempt.get("request_status") == "api_error":
            api_errors += 1
            continue
        record = copy.deepcopy(attempt.get("record"))
        if not isinstance(record, dict):
            raise D1ContractError("ok D1 attempt has no record")
        report = validate_canonical(record)
        if report.schema_valid and report.cross_field_valid:
            valid += 1
        else:
            invalid += 1
    return {
        "repeat_index": repeat_index,
        "attempt_count": len(selected),
        "canonical_valid_count": valid,
        "schema_or_cross_field_invalid_count": invalid,
        "api_error_count": api_errors,
        "membership_exact": True,
        "dropped_attempt_count": 0,
    }

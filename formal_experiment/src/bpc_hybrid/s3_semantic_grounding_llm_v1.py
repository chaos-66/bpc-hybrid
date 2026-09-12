# -*- coding: utf-8 -*-
"""Offline-ready LLM semantic-grounding executor for fallback candidate packs.

The executor is deliberately separate from the final decision:

* it builds a canonical request per frozen fallback item;
* it validates strict JSON and evidence IDs with fail-closed unknown;
* it can run a full mock execution offline;
* a real API call is possible only with an explicit, scope-matching,
  unconsumed authorization file and an API key available in the process
  environment (never read from ``.env`` by this module);
* no retry is performed by default, and an in-doubt send is never resent.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from bpc_hybrid.s3_semantic_grounding_v2 import (
    REVISION as V2_REVISION,
    json_sha256,
)

LLM_RUNNER_REVISION = "s3_semantic_grounding_llm_v1"
RESPONSE_SCHEMA_VERSION = "s3_semantic_grounding_llm_response@2.0.0"
AUTHORIZATION_SCHEMA_VERSION = "s3_semantic_grounding_llm_authorization@1.0.0"
AUTHORIZATION_SCOPE = "S3-SEMANTIC-GROUNDING-V2-FALLBACK"
REQUEST_SET_SCHEMA_VERSION = "s3_semantic_grounding_llm_request_set@1.0.0"

DEFAULT_PROVIDER = "openai_compatible"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_BASE_URL_ENV = "BPC_HYBRID_DeepSeek_BASE_URL"
DEFAULT_API_KEY_ENV = "BPC_HYBRID_DeepSeek_API_KEY"
DEFAULT_MAX_OUTPUT_TOKENS = 512
DEFAULT_CONFIDENCE_THRESHOLD = 0.8


class LLMGroundingExecutionError(ValueError):
    """Raised for fail-closed execution errors."""


def estimate_tokens(text: Any) -> int:
    """Conservative deterministic token proxy: ceil(utf8_bytes / 3)."""
    raw = str(text or "").encode("utf-8")
    return max(1, math.ceil(len(raw) / 3))


def build_system_prompt() -> str:
    return (
        "You are a semantic grounding component, not the final decision maker. "
        "Return one strict JSON object only. Do not output markdown, code fences, "
        "explanations, or chain-of-thought. Use only the provided candidate "
        "activity ids and evidence ids. If a field cannot be grounded, return "
        "status ambiguous/unmatched and confidence <= 0.5. Never invent ids. "
        "The required top-level keys are exactly: action_grounding, condition, "
        "constraint, exception."
    )


def _json_for_prompt(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def build_user_prompt(item: Mapping[str, Any]) -> str:
    payload = item.get("llm_visible_payload") or {}
    instruction = (
        "Ground the rule record against the candidate activities and local BPMN "
        "evidence. Schema:\n"
        '{"action_grounding":{"status":"matched|ambiguous|unmatched",'
        '"activity_id":null,"confidence":0.0},'
        '"condition":{"status":"enforced|not_enforced|ambiguous|not_applicable",'
        '"evidence_ids":[],"confidence":0.0},'
        '"constraint":{"status":"satisfied|violated|ambiguous|not_applicable",'
        '"evidence_ids":[],"confidence":0.0},'
        '"exception":{"status":"handled|not_handled|ambiguous|not_applicable",'
        '"evidence_ids":[],"confidence":0.0}}'
    )
    return instruction + "\n\nInput:\n" + _json_for_prompt(payload)


def build_request_set(pack: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    model = str(config.get("model") or DEFAULT_MODEL)
    max_tokens = int(config.get("max_output_tokens_per_call") or DEFAULT_MAX_OUTPUT_TOKENS)
    temperature = float(config.get("temperature", 0.0))
    top_p = float(config.get("top_p", 1.0))
    system_prompt = build_system_prompt()
    requests = []
    total_input_tokens = 0
    for item in pack.get("items", []):
        user_prompt = build_user_prompt(item)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        request_sha = json_sha256(body)
        input_tokens = estimate_tokens(system_prompt) + estimate_tokens(user_prompt)
        total_input_tokens += input_tokens
        requests.append({
            "fallback_item_id": item.get("fallback_item_id"),
            "source_index": item.get("source_index"),
            "side": item.get("side"),
            "request_sha256": request_sha,
            "input_tokens_estimate": input_tokens,
            "body": body,
            "input_payload": item.get("llm_visible_payload") or {},
        })
    output_cap = len(requests) * max_tokens
    required_peak_cap = round(
        estimate_usd_cost(max(total_input_tokens, 1), output_cap, config,
                          off_peak=False) * 1.5, 2)
    required_off_peak_cap = round(
        estimate_usd_cost(max(total_input_tokens, 1), output_cap, config,
                          off_peak=True) * 1.5, 2)
    return {
        "schema_version": REQUEST_SET_SCHEMA_VERSION,
        "runner_revision": LLM_RUNNER_REVISION,
        "base_revision": V2_REVISION,
        "model": model,
        "temperature": temperature,
        "top_p": top_p,
        "max_output_tokens_per_call": max_tokens,
        "request_count": len(requests),
        "total_input_tokens_estimate": total_input_tokens,
        "total_output_token_cap": output_cap,
        "required_peak_usd_cap": required_peak_cap,
        "required_off_peak_usd_cap": required_off_peak_cap,
        "request_set_sha256": json_sha256([r["body"] for r in requests]),
        "requests": requests,
    }


def _strict_json_object(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise LLMGroundingExecutionError("response_is_not_text")
    try:
        value = json.loads(raw.strip())
    except json.JSONDecodeError as exc:
        raise LLMGroundingExecutionError(f"invalid_json:{exc.msg}") from exc
    if not isinstance(value, dict):
        raise LLMGroundingExecutionError("response_root_not_object")
    return value


def _exact_keys(mapping: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(mapping.keys())
    if actual != expected:
        raise LLMGroundingExecutionError(
            f"{label}_keys:{sorted(actual)}_expected:{sorted(expected)}")


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMGroundingExecutionError("confidence_not_numeric")
    number = float(value)
    if number < 0.0 or number > 1.0:
        raise LLMGroundingExecutionError("confidence_out_of_range")
    return number


def validate_semantic_grounding_response(raw: Any, request: Mapping[str, Any],
                                         confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
                                         ) -> dict[str, Any]:
    """Strict, fail-closed validator for the LLM semantic-grounding schema."""
    try:
        data = _strict_json_object(raw)
        _exact_keys(data, {"action_grounding", "condition", "constraint", "exception"},
                    "top_level")
        payload = request.get("input_payload") or {}
        rule_record = payload.get("rule_record") or {}
        candidate_ids = {str(v) for v in (payload.get("candidate_activity_ids") or [])}
        allowed_evidence = {
            str(v) for v in
            ((payload.get("local_context") or {}).get("evidence_ids") or [])
        }

        action = data["action_grounding"]
        _exact_keys(action, {"status", "activity_id", "confidence"}, "action_grounding")
        if action["status"] not in {"matched", "ambiguous", "unmatched"}:
            raise LLMGroundingExecutionError("action_status_invalid")
        action_confidence = _confidence(action.get("confidence"))
        if action["status"] == "matched":
            if str(action.get("activity_id")) not in candidate_ids:
                raise LLMGroundingExecutionError("action_activity_id_not_candidate")
            if action_confidence < float(confidence_threshold):
                raise LLMGroundingExecutionError("action_confidence_below_threshold")
        else:
            if action.get("activity_id") is not None:
                raise LLMGroundingExecutionError("nonmatched_action_must_have_null_activity_id")

        rule_field_by_block = {
            "condition": "condition",
            "constraint": "constraint",
            "exception": "exception",
        }
        allowed_status = {
            "condition": {"enforced", "not_enforced", "ambiguous", "not_applicable"},
            "constraint": {"satisfied", "violated", "ambiguous", "not_applicable"},
            "exception": {"handled", "not_handled", "ambiguous", "not_applicable"},
        }
        for block_name in ("condition", "constraint", "exception"):
            block = data[block_name]
            _exact_keys(block, {"status", "evidence_ids", "confidence"}, block_name)
            if block["status"] not in allowed_status[block_name]:
                raise LLMGroundingExecutionError(f"{block_name}_status_invalid")
            confidence = _confidence(block.get("confidence"))
            if block["status"] not in {"ambiguous", "not_applicable"} \
                    and confidence < float(confidence_threshold):
                raise LLMGroundingExecutionError(f"{block_name}_confidence_below_threshold")
            evidence_ids = block.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not all(
                    isinstance(value, str) for value in evidence_ids):
                raise LLMGroundingExecutionError(f"{block_name}_evidence_ids_not_string_list")
            if any(value not in allowed_evidence for value in evidence_ids):
                raise LLMGroundingExecutionError(f"{block_name}_hallucinated_evidence_id")
            rule_present = bool(str(rule_record.get(rule_field_by_block[block_name]) or "").strip())
            if block["status"] == "not_applicable" and rule_present:
                raise LLMGroundingExecutionError(f"{block_name}_not_applicable_but_rule_field_present")
            if block["status"] != "not_applicable" and not rule_present:
                raise LLMGroundingExecutionError(f"{block_name}_missing_rule_field_but_applicable")
            if block["status"] == "not_applicable" and evidence_ids:
                raise LLMGroundingExecutionError(f"{block_name}_not_applicable_with_evidence")
        return {"status": "valid", "response": data}
    except LLMGroundingExecutionError as exc:
        return {"status": "failed", "error": str(exc)}


def _price_snapshot(config: Mapping[str, Any]) -> dict[str, Any]:
    return dict(config.get("price_snapshot") or {
        "peak": {"input_cache_miss_per_million": 1.32,
                 "output_per_million": 3.96},
        "off_peak": {"input_cache_miss_per_million": 0.66,
                     "output_per_million": 1.98},
    })


def estimate_usd_cost(input_tokens: int, output_tokens: int,
                      config: Mapping[str, Any], *, off_peak: bool = False) -> float:
    prices = _price_snapshot(config)
    rate = prices["off_peak"] if off_peak else prices["peak"]
    usd = (
        input_tokens * float(rate["input_cache_miss_per_million"]) / 1_000_000.0
        + output_tokens * float(rate["output_per_million"]) / 1_000_000.0
    )
    return round(usd, 6)


def build_authorization_request(request_set: Mapping[str, Any],
                                pack: Mapping[str, Any],
                                config: Mapping[str, Any]) -> dict[str, Any]:
    count = int(request_set.get("request_count") or 0)
    input_tokens = int(request_set.get("total_input_tokens_estimate") or 0)
    output_cap = int(request_set.get("total_output_token_cap") or 0)
    peak_usd = estimate_usd_cost(max(input_tokens, 1), output_cap, config, off_peak=False)
    off_peak_usd = estimate_usd_cost(max(input_tokens, 1), output_cap, config, off_peak=True)
    peak_cap = round(peak_usd * 1.5, 2)
    off_peak_cap = round(off_peak_usd * 1.5, 2)
    scope = str(config.get("scope") or AUTHORIZATION_SCOPE)
    model = str(config.get("model") or DEFAULT_MODEL)
    provider = str(config.get("provider") or DEFAULT_PROVIDER)
    base_url_env = str(config.get("base_url_env_var") or DEFAULT_BASE_URL_ENV)
    api_key_env = str(config.get("api_key_env_var") or DEFAULT_API_KEY_ENV)
    sentence = (
        f"我授权在 {scope} 范围内使用 {provider}/{model} 对已冻结的 "
        f"{count} 个 fallback items 执行真实 API 调用；retry=0，仅低峰运行，"
        f"总费用上限 USD {peak_cap:.2f} / RMB {peak_cap * 7.2:.2f}，"
        f"输入 token 上限 {int(input_tokens * 2)}，输出总 token 上限 {output_cap}，"
        f"请求集 hash={request_set.get('request_set_sha256')}，"
        f"候选 pack hash={json_sha256(pack)}。"
    )
    return {
        "schema_version": "s3_semantic_grounding_llm_authorization_request@1.0.0",
        "revision": LLM_RUNNER_REVISION,
        "base_revision": V2_REVISION,
        "scope": scope,
        "provider": provider,
        "model": model,
        "base_url_env_var": base_url_env,
        "api_key_env_var": api_key_env,
        "fallback_item_count": count,
        "calls": count,
        "retry": 0,
        "off_peak_only": True,
        "expected_input_tokens": input_tokens,
        "max_input_tokens_cap": int(input_tokens * 2),
        "max_output_tokens_per_call": int(request_set.get("max_output_tokens_per_call") or DEFAULT_MAX_OUTPUT_TOKENS),
        "total_output_token_cap": output_cap,
        "peak_estimated_usd": peak_usd,
        "off_peak_estimated_usd": off_peak_usd,
        "usd_cap": peak_cap,
        "required_usd_cap": peak_cap,
        "rmb_cap_at_7.2": round(peak_cap * 7.2, 2),
        "request_set_sha256": request_set.get("request_set_sha256"),
        "candidate_pack_sha256": json_sha256(pack),
        "price_snapshot": _price_snapshot(config),
        "suggested_authorization_sentence": sentence,
        "suggested_authorization_sentence_sha256": hashlib.sha256(
            sentence.encode("utf-8")).hexdigest(),
        "execution_command": (
            "python formal_experiment/scripts/run_s3_semantic_grounding_llm_v1.py "
            "--real --authorization outputs/reports/s3_semantic_grounding_v2_llm_authorization.json"
        ),
        "decision": "BLOCKED_NO_MATCHING_AUTHORIZATION" if count else "NOT_APPLICABLE_NO_CANDIDATES",
    }


def validate_authorization(authorization: Mapping[str, Any],
                           pack: Mapping[str, Any],
                           request_set: Mapping[str, Any],
                           config: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    scope = str(config.get("scope") or AUTHORIZATION_SCOPE)
    if authorization.get("scope") != scope:
        errors.append("scope_mismatch")
    if authorization.get("model") != str(config.get("model") or DEFAULT_MODEL):
        errors.append("model_mismatch")
    if int(authorization.get("max_calls", 0)) < int(request_set.get("request_count", 0)):
        errors.append("max_calls_insufficient")
    if int(authorization.get("retry", -1)) != 0:
        errors.append("retry_not_zero")
    if authorization.get("off_peak_only") is not True:
        errors.append("off_peak_not_required")
    if authorization.get("candidate_pack_sha256") != json_sha256(pack):
        errors.append("candidate_pack_hash_mismatch")
    if authorization.get("request_set_sha256") != request_set.get("request_set_sha256"):
        errors.append("request_set_hash_mismatch")
    if authorization.get("status") != "authorized_unconsumed":
        errors.append("authorization_not_unconsumed")
    required_cap = float(request_set.get("required_peak_usd_cap", 10**9))
    if float(authorization.get("usd_cap", 0.0)) < required_cap:
        errors.append("usd_cap_insufficient")
    if not str(authorization.get("authorization_sentence_sha256") or "").strip():
        errors.append("missing_authorization_sentence_hash")
    return {"valid": not errors, "errors": errors}


def build_authorization_event_from_sentence(authorization_sentence: str,
                                           request_set: Mapping[str, Any],
                                           pack: Mapping[str, Any],
                                           config: Mapping[str, Any],
                                           output_path: Path | None = None
                                           ) -> dict[str, Any]:
    """Create the scope-specific authorization file after the user's exact reply."""
    request = build_authorization_request(request_set, pack, config)
    expected_sentence = str(request["suggested_authorization_sentence"])
    if authorization_sentence.strip() != expected_sentence:
        raise LLMGroundingExecutionError("authorization_sentence_does_not_match_request")
    event = {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "scope": request["scope"],
        "provider": request["provider"],
        "model": request["model"],
        "max_calls": int(request["calls"]),
        "retry": 0,
        "off_peak_only": True,
        "candidate_pack_sha256": request["candidate_pack_sha256"],
        "request_set_sha256": request["request_set_sha256"],
        "usd_cap": float(request["usd_cap"]),
        "required_usd_cap": float(request["required_usd_cap"]),
        "status": "authorized_unconsumed",
        "authorization_sentence": authorization_sentence,
        "authorization_sentence_sha256": hashlib.sha256(
            authorization_sentence.encode("utf-8")).hexdigest(),
        "issued_at_utc": _utc_now(),
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    return event


__all__ = [
    "LLM_RUNNER_REVISION", "RESPONSE_SCHEMA_VERSION", "AUTHORIZATION_SCHEMA_VERSION",
    "AUTHORIZATION_SCOPE", "REQUEST_SET_SCHEMA_VERSION", "DEFAULT_PROVIDER",
    "DEFAULT_MODEL", "DEFAULT_BASE_URL_ENV", "DEFAULT_API_KEY_ENV",
    "LLMGroundingExecutionError", "estimate_tokens", "build_system_prompt",
    "build_user_prompt", "build_request_set", "validate_semantic_grounding_response",
    "estimate_usd_cost", "build_authorization_request", "validate_authorization",
    "build_authorization_event_from_sentence", "append_ledger", "execute_fallback",
]

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            entries.append({"state": "corrupt_ledger_line", "raw": line})
    return entries


def append_ledger(ledger_path: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    entries = _read_ledger(ledger_path)
    prev_hash = entries[-1].get("record_hash") if entries else "GENESIS"
    payload = dict(record)
    payload["prev_hash"] = prev_hash
    payload["timestamp_utc"] = _utc_now()
    payload["record_hash"] = json_sha256({key: value for key, value in payload.items()
                                          if key != "record_hash"})
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    return payload


def _state_by_request(ledger_entries: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    states: dict[str, str] = {}
    for entry in ledger_entries:
        request_sha = entry.get("request_sha256")
        if request_sha and entry.get("state"):
            states[str(request_sha)] = str(entry["state"])
    return states


class MockSemanticGroundingTransport:
    """Deterministic offline transport used only for plumbing/mock runs."""

    def __init__(self, responses: Mapping[str, str] | Callable[[Mapping[str, Any]], str] | None = None):
        self.responses = responses
        self.seen = 0

    def _default_response(self, request: Mapping[str, Any]) -> str:
        payload = request.get("input_payload") or {}
        rule = payload.get("rule_record") or {}
        def block(field: str) -> dict[str, Any]:
            return {
                "status": "not_applicable" if not str(rule.get(field) or "").strip() else "ambiguous",
                "evidence_ids": [],
                "confidence": 0.0,
            }
        return json.dumps({
            "action_grounding": {
                "status": "matched" if (payload.get("candidate_activity_ids") or []) else "ambiguous",
                "activity_id": (payload.get("candidate_activity_ids") or [None])[0],
                "confidence": 0.9 if (payload.get("candidate_activity_ids") or []) else 0.0,
            },
            "condition": block("condition"),
            "constraint": block("constraint"),
            "exception": block("exception"),
        }, ensure_ascii=False, sort_keys=True)

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        self.seen += 1
        if callable(self.responses):
            content = self.responses(request)
        elif isinstance(self.responses, Mapping):
            content = self.responses.get(str(request.get("request_sha256")),
                                         self.responses.get(str(request.get("fallback_item_id"))))
            if content is None:
                content = self._default_response(request)
        else:
            content = self._default_response(request)
        return {"content": content, "provider": "mock", "model": "mock",
                "finish_reason": "mock", "request_body_sha256": request.get("request_sha256")}


class RealSemanticGroundingTransport:
    """Thin adapter over the existing RealAPITransport; no key logging."""

    def __init__(self, config: Mapping[str, Any]) -> None:
        from bpc_hybrid.llm_client import (  # local import: offline-safe
            LLMRequest,
            OpenAICompatibleRequestBuilder,
            RealAPITransport,
        )
        from bpc_hybrid.llm_config import LLMConfig

        base_url = os.environ.get(str(config.get("base_url_env_var")
                                      or DEFAULT_BASE_URL_ENV), "")
        api_key = os.environ.get(str(config.get("api_key_env_var")
                                     or DEFAULT_API_KEY_ENV), "")
        if not base_url or not api_key:
            raise LLMGroundingExecutionError("missing_real_api_credentials_in_environment")
        llm_config = LLMConfig(
            enabled=True,
            provider=DEFAULT_PROVIDER,
            model=str(config.get("model") or DEFAULT_MODEL),
            api_key=api_key,
            base_url=base_url,
            max_tokens=int(config.get("max_output_tokens_per_call")
                           or DEFAULT_MAX_OUTPUT_TOKENS),
            temperature=float(config.get("temperature", 0.0)),
            top_p=float(config.get("top_p", 1.0)),
            timeout_seconds=float(config.get("timeout_seconds", 60.0)),
        )
        self._builder = OpenAICompatibleRequestBuilder(llm_config)
        self._transport = RealAPITransport(llm_config,
                                           timeout_seconds=float(config.get("timeout_seconds", 60.0)))
        self._LLMRequest = LLMRequest

    def complete(self, request: Mapping[str, Any]) -> dict[str, Any]:
        body = request.get("body") or {}
        messages = body.get("messages") or []
        system_prompt = messages[0]["content"] if messages else ""
        user_prompt = messages[1]["content"] if len(messages) > 1 else ""
        payload = self._builder.build_payload(system_prompt=system_prompt,
                                              user_prompt=user_prompt)
        if json.loads(json.dumps(payload["body"])) != json.loads(json.dumps(body)):
            raise LLMGroundingExecutionError("request_body_drift_before_real_send")
        llm_request = self._LLMRequest(
            source_id=str(request.get("fallback_item_id") or "fallback"),
            source_text="",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        response = self._transport.send(llm_request)
        return {
            "content": response.content,
            "provider": response.provider,
            "model": response.model,
            "finish_reason": response.finish_reason,
            "request_body_sha256": self._transport.last_request_body_sha256,
            "decode": self._transport.last_decode,
        }


def _normalize_llm_status(validated_response: Mapping[str, Any]) -> str:
    statuses = [
        validated_response.get("condition", {}).get("status"),
        validated_response.get("constraint", {}).get("status"),
        validated_response.get("exception", {}).get("status"),
    ]
    if "ambiguous" in statuses:
        return "ambiguous"
    return "resolved"


def execute_fallback(*, pack: Mapping[str, Any], request_set: Mapping[str, Any],
                     config: Mapping[str, Any], output_root: Path,
                     mode: str, authorization: Mapping[str, Any] | None = None,
                     transport: Any | None = None,
                     confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
                     ) -> dict[str, Any]:
    """Execute the frozen pack in mock or real mode with ledger protection.

    ``mode='real'`` additionally requires a valid scope-matching authorization
    and environment credentials; there is no automatic retry.
    """
    if mode not in {"mock", "real"}:
        raise LLMGroundingExecutionError(f"unknown_mode:{mode}")
    if mode == "real":
        if authorization is None:
            raise LLMGroundingExecutionError("real_mode_requires_authorization")
        validation = validate_authorization(authorization, pack, request_set, config)
        if not validation["valid"]:
            raise LLMGroundingExecutionError("authorization_invalid:" + ",".join(validation["errors"]))
        if transport is None:
            transport = RealSemanticGroundingTransport(config)
    else:
        if transport is None:
            transport = MockSemanticGroundingTransport()

    run_root = output_root / (f"s3_semantic_grounding_llm_v1_{mode}_run")
    raw_dir = run_root / "raw_responses"
    normalized_path = run_root / "normalized_grounding.jsonl"
    ledger_path = run_root / "execution_ledger.jsonl"
    raw_dir.mkdir(parents=True, exist_ok=True)
    ledger_entries = _read_ledger(ledger_path)
    states = _state_by_request(ledger_entries)

    results: list[dict[str, Any]] = []
    counts = {
        "item_count": int(request_set.get("request_count") or 0),
        "attempted": 0,
        "succeeded": 0,
        "malformed": 0,
        "rejected_by_validator": 0,
        "ambiguous": 0,
        "resolved": 0,
        "skipped_resume_protected": 0,
        "in_doubt": 0,
        "failed": 0,
    }
    total_input_estimate = 0
    downstream_lines: list[dict[str, Any]] = []

    for request in request_set.get("requests", []):
        request_sha = str(request.get("request_sha256"))
        if states.get(request_sha) in {"sent", "succeeded", "in_doubt"}:
            counts["skipped_resume_protected"] += 1
            continue
        counts["attempted"] += 1
        total_input_estimate += int(request.get("input_tokens_estimate") or 0)
        append_ledger(ledger_path, {
            "state": "sent",
            "request_sha256": request_sha,
            "fallback_item_id": request.get("fallback_item_id"),
            "source_index": request.get("source_index"),
            "input_tokens_estimate": request.get("input_tokens_estimate"),
        })
        try:
            raw = transport.complete(request)
        except Exception as exc:  # noqa: BLE001 - any transport failure is in-doubt
            counts["in_doubt"] += 1
            append_ledger(ledger_path, {
                "state": "in_doubt",
                "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
                "error_type": type(exc).__name__,
            })
            results.append({"source_index": request.get("source_index"),
                            "fallback_item_id": request.get("fallback_item_id"),
                            "status": "failed", "error": "in_doubt"})
            continue
        content = str(raw.get("content") or "")
        response_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        raw_path = raw_dir / f"{request_sha}.json"
        raw_path.write_text(json.dumps({
            "fallback_item_id": request.get("fallback_item_id"),
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "provider": raw.get("provider"),
            "model": raw.get("model"),
            "finish_reason": raw.get("finish_reason"),
            "content": content,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        validated = validate_semantic_grounding_response(content, request,
                                                         confidence_threshold)
        if validated["status"] == "failed":
            malformed = "invalid_json" in str(validated.get("error"))
            counts["malformed" if malformed else "rejected_by_validator"] += 1
            append_ledger(ledger_path, {
                "state": "rejected" if not malformed else "malformed",
                "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
                "error": validated.get("error"),
                "response_sha256": response_sha,
            })
            results.append({"source_index": request.get("source_index"),
                            "fallback_item_id": request.get("fallback_item_id"),
                            "status": "failed", "error": validated.get("error"),
                            "response_sha256": response_sha})
            continue
        response = validated["response"]
        normalized_status = _normalize_llm_status(response)
        counts["ambiguous" if normalized_status == "ambiguous" else "resolved"] += 1
        counts["succeeded"] += 1
        normalized_record = {
            "fallback_item_id": request.get("fallback_item_id"),
            "source_index": request.get("source_index"),
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "semantic_status": normalized_status,
            "response": response,
        }
        downstream_lines.append(normalized_record)
        append_ledger(ledger_path, {
            "state": "succeeded",
            "request_sha256": request_sha,
            "fallback_item_id": request.get("fallback_item_id"),
            "semantic_status": normalized_status,
            "response_sha256": response_sha,
        })
        results.append({"source_index": request.get("source_index"),
                        "fallback_item_id": request.get("fallback_item_id"),
                        "status": normalized_status, "response": response,
                        "response_sha256": response_sha})
    if downstream_lines:
        with normalized_path.open("a", encoding="utf-8", newline="\n") as handle:
            for line in downstream_lines:
                handle.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
    summary = {
        "schema_version": "s3_semantic_grounding_llm_execution@1.0.0",
        "runner_revision": LLM_RUNNER_REVISION,
        "base_revision": V2_REVISION,
        "mode": mode,
        "counts": counts,
        "total_input_tokens_estimate": total_input_estimate,
        "results": results,
        "ledger_path": str(ledger_path),
        "normalized_path": str(normalized_path),
        "raw_response_dir": str(raw_dir),
        "retry": 0,
        "no_double_send": True,
    }
    (run_root / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return summary

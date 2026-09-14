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
    if not isinstance(mapping, Mapping):
        raise LLMGroundingExecutionError(f"{label}_not_object")
    actual = set(mapping.keys())
    if actual != expected:
        raise LLMGroundingExecutionError(
            f"{label}_keys:{sorted(actual)}_expected:{sorted(expected)}")


def _confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LLMGroundingExecutionError("confidence_not_numeric")
    number = float(value)
    if not math.isfinite(number):
        raise LLMGroundingExecutionError("confidence_not_finite")
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


def _ledger_entry_hash(entry: Mapping[str, Any]) -> str:
    return json_sha256({key: value for key, value in entry.items()
                        if key != "record_hash"})


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    """Read and validate the append-only ledger hash chain.

    A malformed JSON line, a missing/extra hash, a hash mismatch, or a broken
    ``prev_hash`` chain raises before any new request can be sent.  This is
    intentionally fail-closed: an unreadable ledger may hide an in-doubt
    request and must never cause a duplicate send.
    """
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    previous_hash = "GENESIS"
    for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LLMGroundingExecutionError(
                f"ledger_integrity_error:line_{line_number}_invalid_json") from exc
        if not isinstance(entry, Mapping):
            raise LLMGroundingExecutionError(
                f"ledger_integrity_error:line_{line_number}_not_object")
        entry = dict(entry)
        if entry.get("prev_hash") != previous_hash:
            raise LLMGroundingExecutionError(
                f"ledger_integrity_error:line_{line_number}_prev_hash_mismatch")
        expected = entry.get("record_hash")
        if not isinstance(expected, str) or not expected:
            raise LLMGroundingExecutionError(
                f"ledger_integrity_error:line_{line_number}_missing_record_hash")
        actual = _ledger_entry_hash(entry)
        if actual != expected:
            raise LLMGroundingExecutionError(
                f"ledger_integrity_error:line_{line_number}_record_hash_mismatch")
        previous_hash = expected
        entries.append(entry)
    return entries


def append_ledger(ledger_path: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    entries = _read_ledger(ledger_path)
    prev_hash = entries[-1].get("record_hash") if entries else "GENESIS"
    payload = dict(record)
    payload["prev_hash"] = prev_hash
    payload["timestamp_utc"] = _utc_now()
    payload["record_hash"] = _ledger_entry_hash(payload)
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
    """Return whether at least one field can make independent progress.

    A single ``ambiguous`` field must never discard another field whose
    status is already resolved.  The caller applies fields independently;
    this summary is retained only for metrics/backward compatibility.
    """
    field_statuses = [
        (validated_response.get(field) or {}).get("status")
        for field in ("condition", "constraint", "exception")
    ]
    action = validated_response.get("action_grounding") or {}
    determinate = {
        "enforced", "not_enforced", "satisfied", "violated",
        "handled", "not_handled",
    }
    if action.get("status") == "matched":
        return "resolved"
    if any(status in determinate for status in field_statuses):
        return "resolved"
    if any(status == "ambiguous" for status in field_statuses):
        return "ambiguous"
    return "unknown"


def _legacy_execute_fallback(*, pack: Mapping[str, Any], request_set: Mapping[str, Any],
                            config: Mapping[str, Any], output_root: Path,
                            mode: str, authorization: Mapping[str, Any] | None = None,
                            transport: Any | None = None,
                            confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
                            ) -> dict[str, Any]:
    """Historical v1 execution body retained for provenance.

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
        field_statuses = {
            field: ((response.get(field) or {}).get("status"))
            for field in ("condition", "constraint", "exception")
        }
        action_status = (response.get("action_grounding") or {}).get("status")
        counts["ambiguous" if normalized_status == "ambiguous" else "resolved"] += 1
        counts["succeeded"] += 1
        normalized_record = {
            "fallback_item_id": request.get("fallback_item_id"),
            "source_index": request.get("source_index"),
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "semantic_status": normalized_status,
            "action_status": action_status,
            "field_statuses": field_statuses,
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
                        "status": normalized_status,
                        "action_status": action_status,
                        "field_statuses": field_statuses,
                        "response": response,
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


# ---------------------------------------------------------------------------
# v2 execution state machine: no-double-send, resumable storage, budgets
# ---------------------------------------------------------------------------

_SENT_TERMINAL_STATES = frozenset({
    "send_started", "sent", "succeeded", "malformed", "rejected", "in_doubt", "usage_unknown",
})
_PRE_SEND_RETRYABLE_STATES = frozenset({
    "pre_send_failed", "blocked_pre_send", "blocked_off_peak", "blocked_budget",
    "blocked_usage_unknown", "blocked_after_in_doubt",
})


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LLMGroundingExecutionError(
                f"normalized_store_invalid_json:line_{line_number}") from exc
        if not isinstance(record, Mapping) or not record.get("request_sha256"):
            raise LLMGroundingExecutionError(
                f"normalized_store_invalid_record:line_{line_number}")
        request_sha = str(record["request_sha256"])
        if request_sha in seen:
            raise LLMGroundingExecutionError(
                f"normalized_store_duplicate_request:line_{line_number}")
        seen.add(request_sha)
        records.append(dict(record))
    return records


def _append_jsonl(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _append_normalized_once(path: Path, by_request: dict[str, dict[str, Any]],
                            record: Mapping[str, Any]) -> dict[str, Any]:
    request_sha = str(record.get("request_sha256"))
    if request_sha in by_request:
        return by_request[request_sha]
    materialized = dict(record)
    _append_jsonl(path, materialized)
    by_request[request_sha] = materialized
    return materialized


def _write_raw_once(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(existing, Mapping) \
                and existing.get("content") == payload.get("content"):
            return dict(existing)
        raise LLMGroundingExecutionError("raw_response_store_conflict")
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    return dict(payload)


def _numeric_token(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        return None
    return int(number)


def _usage_from_raw(raw: Mapping[str, Any], request: Mapping[str, Any],
                    mode: str) -> tuple[int | None, int | None, bool, str]:
    candidates: list[Mapping[str, Any]] = []
    if isinstance(raw.get("usage"), Mapping):
        candidates.append(raw["usage"])
    decode = raw.get("decode")
    if isinstance(decode, Mapping) and isinstance(decode.get("usage"), Mapping):
        candidates.append(decode["usage"])
    for usage in candidates:
        input_tokens = _numeric_token(
            usage.get("prompt_tokens", usage.get("input_tokens")))
        output_tokens = _numeric_token(
            usage.get("completion_tokens", usage.get("output_tokens")))
        if input_tokens is not None and output_tokens is not None:
            return input_tokens, output_tokens, True, "provider_usage"
    if mode == "mock":
        content = str(raw.get("content") or "")
        return (int(request.get("input_tokens_estimate") or 0),
                estimate_tokens(content), True, "mock_estimate")
    return None, None, False, "missing_usage"


def _storage_usage(record: Mapping[str, Any]) -> tuple[int | None, int | None, float | None]:
    input_tokens = _numeric_token(record.get("input_tokens"))
    output_tokens = _numeric_token(record.get("output_tokens"))
    usd = record.get("usd_cost")
    if isinstance(usd, bool) or not isinstance(usd, (int, float)):
        usd_value = None
    else:
        usd_value = float(usd)
    return input_tokens, output_tokens, usd_value


def _off_peak_allowed(config: Mapping[str, Any],
                      now_utc: Any) -> bool:
    if not config.get("off_peak_only"):
        return True
    windows = config.get("off_peak_windows_utc")
    hour = now_utc.hour + now_utc.minute / 60.0
    if isinstance(windows, list) and windows:
        for window in windows:
            if not isinstance(window, (list, tuple)) or len(window) != 2:
                continue
            start, end = float(window[0]), float(window[1])
            if start <= hour < end:
                return True
        return False
    start = config.get("off_peak_start_hour_utc")
    end = config.get("off_peak_end_hour_utc")
    if start is None or end is None:
        # The contract requires off-peak execution; an undeclared window is
        # not permission to send at an unknown time.
        return False
    start_value, end_value = float(start), float(end)
    if start_value <= end_value:
        return start_value <= hour < end_value
    return hour >= start_value or hour < end_value


def _authorization_value(config: Mapping[str, Any],
                         authorization: Mapping[str, Any] | None,
                         field: str, default: Any = None) -> Any:
    if authorization is not None and authorization.get(field) is not None:
        return authorization.get(field)
    return config.get(field, default)


def _normalized_result(record: Mapping[str, Any],
                       *, recovered: bool) -> dict[str, Any]:
    status = str(record.get("status") or "failed")
    if status == "succeeded":
        result_status = "validated"
    else:
        result_status = "failed"
    return {
        "source_index": record.get("source_index"),
        "fallback_item_id": record.get("fallback_item_id"),
        "status": result_status,
        "semantic_status": record.get("semantic_status"),
        "action_status": record.get("action_status"),
        "field_statuses": record.get("field_statuses") or {},
        "response": record.get("response") if status == "succeeded" else None,
        "response_sha256": record.get("response_sha256"),
        "terminal_state": status,
        "error": record.get("error"),
        "recovered_from_store": recovered,
        "request_sha256": record.get("request_sha256"),
    }


def _recover_request_from_raw(request: Mapping[str, Any], raw_dir: Path,
                              mode: str, confidence_threshold: float
                              ) -> dict[str, Any] | None:
    raw_path = raw_dir / f"{request.get('request_sha256')}.json"
    if not raw_path.is_file():
        return None
    try:
        stored = json.loads(raw_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    content = str(stored.get("content") or "")
    request_sha = str(request.get("request_sha256"))
    response_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
    validated = validate_semantic_grounding_response(
        content, request, confidence_threshold)
    semantic_status = None
    action_status = None
    field_statuses: dict[str, Any] = {}
    response_value = None
    if validated["status"] == "valid":
        response_value = validated["response"]
        semantic_status = _normalize_llm_status(response_value)
        action_status = (response_value.get("action_grounding") or {}).get("status")
        field_statuses = {
            field: ((response_value.get(field) or {}).get("status"))
            for field in ("condition", "constraint", "exception")
        }
        state = "succeeded"
        error = None
    else:
        error_text = str(validated.get("error"))
        state = "malformed" if "invalid_json" in error_text else "rejected"
        error = error_text
    input_tokens = _numeric_token(stored.get("input_tokens"))
    output_tokens = _numeric_token(stored.get("output_tokens"))
    usage_known = input_tokens is not None and output_tokens is not None
    usd_cost = (estimate_usd_cost(input_tokens, output_tokens,
                                  {"price_snapshot": stored.get("price_snapshot")},
                                  off_peak=bool(stored.get("off_peak")))
                if usage_known else None)
    return {
        "fallback_item_id": request.get("fallback_item_id"),
        "source_index": request.get("source_index"),
        "request_sha256": request_sha,
        "response_sha256": response_sha,
        "status": state,
        "semantic_status": semantic_status,
        "action_status": action_status,
        "field_statuses": field_statuses,
        "response": response_value,
        "error": error,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "usd_cost": usd_cost,
        "usage_source": "recovered_from_raw",
        "usage_known": usage_known,
        "source": "recovered_from_raw",
    }


class PreSendTransportError(LLMGroundingExecutionError):
    """Signal that a transport failed before any request was transmitted.

    Transports can raise this when they can decide locally that no send
    happened (for example, a fake transport configured to fail closed).  A
    generic transport exception is treated as in-doubt instead, because the
    request may already have reached the provider.
    """


def _budget_block_reason(*, config: Mapping[str, Any],
                         authorization: Mapping[str, Any] | None,
                         request: Mapping[str, Any], request_set: Mapping[str, Any],
                         sent_count: int, known_input_tokens: int,
                         known_output_tokens: int, known_usd: float,
                         known_usage_unknown: bool) -> str | None:
    if known_usage_unknown:
        return "usage_unknown_previous_request"
    max_calls = _authorization_value(config, authorization, "max_calls")
    if max_calls is not None and sent_count + 1 > int(max_calls):
        return "max_calls"
    input_cap = _authorization_value(config, authorization, "max_input_tokens_cap")
    next_input = int(request.get("input_tokens_estimate") or 0)
    if input_cap is not None and known_input_tokens + next_input > int(input_cap):
        return "max_input_tokens_cap"
    max_output = int(request_set.get("max_output_tokens_per_call") or 0)
    output_cap = _authorization_value(config, authorization, "total_output_token_cap")
    if output_cap is not None and known_output_tokens + max_output > int(output_cap):
        return "total_output_token_cap"
    usd_cap = _authorization_value(config, authorization, "usd_cap")
    if usd_cap is not None:
        projected = known_usd + estimate_usd_cost(
            max(next_input, 1), max(max_output, 1), config,
            off_peak=bool(config.get("off_peak_only")))
        if projected > float(usd_cap):
            return "usd_cap"
    return None


def _classify_run_status(counts: Mapping[str, int], total: int) -> str:
    valid = int(counts.get("succeeded", 0))
    other_terminal = (int(counts.get("malformed", 0))
                      + int(counts.get("rejected_by_validator", 0))
                      + int(counts.get("in_doubt", 0)))
    blocked = (int(counts.get("pre_send_blocked", 0))
               + int(counts.get("pre_send_failed", 0)))
    if total == 0:
        return "blocked" if blocked else "complete"
    if valid == total and other_terminal == 0 and blocked == 0:
        return "complete"
    send_attempts = int(counts.get("send_attempts", 0))
    if valid > 0:
        return "partial"
    if send_attempts > 0 \
            and int(counts.get("pre_send_failed", 0)) >= send_attempts:
        return "blocked"
    if send_attempts > 0 \
            or int(counts.get("resumed_from_store", 0)) > 0:
        return "failed"
    return "blocked"


def execute_fallback(*, pack: Mapping[str, Any], request_set: Mapping[str, Any],
                     config: Mapping[str, Any], output_root: Path,
                     mode: str, authorization: Mapping[str, Any] | None = None,
                     transport: Any | None = None,
                     confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
                     now_utc_fn: Any | None = None) -> dict[str, Any]:
    """Resumable append-only executor with fail-closed budget/time gates.

    Terminal states and their evidence are appended before the next request is
    considered.  A request whose ledger state says it was sent is never sent
    again, even if validation failed or the process stopped mid-run.
    """
    if mode not in {"mock", "real"}:
        raise LLMGroundingExecutionError(f"unknown_mode:{mode}")
    if mode == "real":
        if authorization is None:
            raise LLMGroundingExecutionError("real_mode_requires_authorization")
        validation = validate_authorization(authorization, pack, request_set, config)
        if not validation["valid"]:
            raise LLMGroundingExecutionError(
                "authorization_invalid:" + ",".join(validation["errors"]))
        if transport is None:
            transport = RealSemanticGroundingTransport(config)
    else:
        if transport is None:
            transport = MockSemanticGroundingTransport()

    run_root_name = str(config.get("run_root_name")
                        or f"{LLM_RUNNER_REVISION}_{mode}_run")
    run_root = output_root / run_root_name
    raw_dir = run_root / "raw_responses"
    normalized_path = run_root / "normalized_grounding.jsonl"
    ledger_path = run_root / "execution_ledger.jsonl"
    raw_dir.mkdir(parents=True, exist_ok=True)

    ledger_entries = _read_ledger(ledger_path)
    states = _state_by_request(ledger_entries)
    by_request_records = {
        str(record["request_sha256"]): record
        for record in _read_jsonl_records(normalized_path)
    }
    object_requests = list(request_set.get("requests", []))
    unique_requests: dict[str, dict[str, Any]] = {}
    for request in object_requests:
        digest = request.get("request_sha256")
        if digest != json_sha256(request.get("body")):
            raise LLMGroundingExecutionError("request_body_hash_mismatch")
        unique_requests.setdefault(str(digest), request)
    # One persisted/charged response per identical body. Fan it back out to
    # every object below, retaining each object's own source index and side.
    requests = list(unique_requests.values())
    counts = {
        "item_count": len(requests),
        "attempted": 0,
        "send_attempts": 0,
        "succeeded": 0,
        "malformed": 0,
        "rejected_by_validator": 0,
        "ambiguous": 0,
        "resolved": 0,
        "skipped_resume_protected": 0,
        "resumed_from_store": 0,
        "pre_send_failed": 0,
        "pre_send_blocked": 0,
        "in_doubt": 0,
        "usage_unknown": 0,
        "failed": 0,
    }
    known_input_tokens = 0
    known_output_tokens = 0
    known_usd = 0.0
    historical_usage_unknown = False
    for record in by_request_records.values():
        input_tokens, output_tokens, _ = _storage_usage(record)
        if not (record.get("usage_known") and input_tokens is not None
                and output_tokens is not None) \
                and record.get("status") in _SENT_TERMINAL_STATES:
            historical_usage_unknown = True
    known_usage_unknown = historical_usage_unknown

    sent_count = sum(
        1 for request in requests
        if states.get(str(request.get("request_sha256"))) in _SENT_TERMINAL_STATES
        or str(request.get("request_sha256")) in by_request_records
    )
    attempted_request_shas: list[str] = []
    resumed_sent_shas: set[str] = set()
    results_by_request: dict[str, dict[str, Any]] = {}
    halt_sending = False
    now_utc = now_utc_fn or (lambda: datetime.now(timezone.utc))

    def blocked_result(request: Mapping[str, Any], reason: str) -> dict[str, Any]:
        return {
            "source_index": request.get("source_index"),
            "fallback_item_id": request.get("fallback_item_id"),
            "status": "blocked",
            "error": reason,
            "terminal_state": reason,
            "response": None,
            "recovered_from_store": False,
            "request_sha256": request.get("request_sha256"),
        }

    for request in requests:
        request_sha = str(request.get("request_sha256"))
        state = states.get(request_sha)
        existing = by_request_records.get(request_sha)

        if state in _SENT_TERMINAL_STATES or existing is not None:
            if existing is None:
                recovered = _recover_request_from_raw(
                    request, raw_dir, mode, confidence_threshold)
                if recovered is not None:
                    existing = _append_normalized_once(
                        normalized_path, by_request_records, recovered)
            if existing is None:
                existing = _append_normalized_once(normalized_path, by_request_records, {
                    "fallback_item_id": request.get("fallback_item_id"),
                    "source_index": request.get("source_index"),
                    "request_sha256": request_sha,
                    "response_sha256": None,
                    "status": "in_doubt",
                    "semantic_status": None,
                    "action_status": None,
                    "field_statuses": {},
                    "response": None,
                    "error": "sent_state_without_saved_response",
                    "input_tokens": None,
                    "output_tokens": None,
                    "usd_cost": None,
                    "usage_source": "unknown",
                    "usage_known": False,
                    "source": "recovered_placeholder",
                })
            result = _normalized_result(existing, recovered=True)
            results_by_request[request_sha] = result
            resumed_sent_shas.add(request_sha)
            counts["skipped_resume_protected"] += 1
            counts["resumed_from_store"] += 1
            if result["terminal_state"] == "succeeded":
                counts["succeeded"] += 1
                if result.get("semantic_status") == "ambiguous":
                    counts["ambiguous"] += 1
                else:
                    counts["resolved"] += 1
            elif result["terminal_state"] == "malformed":
                counts["malformed"] += 1
                counts["failed"] += 1
            elif result["terminal_state"] == "rejected":
                counts["rejected_by_validator"] += 1
                counts["failed"] += 1
            else:
                counts["in_doubt"] += 1
                counts["failed"] += 1
            input_tokens, output_tokens, usd_cost = _storage_usage(existing)
            if existing.get("usage_known") and input_tokens is not None \
                    and output_tokens is not None:
                known_input_tokens += input_tokens
                known_output_tokens += output_tokens
                known_usd += usd_cost or 0.0
            elif existing.get("status") in _SENT_TERMINAL_STATES:
                known_usage_unknown = True
                if existing.get("status") == "in_doubt":
                    halt_sending = True
            continue

        if halt_sending:
            reason = "blocked_after_in_doubt"
            append_ledger(ledger_path, {
                "state": reason, "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
            })
            counts["pre_send_blocked"] += 1
            results_by_request[request_sha] = blocked_result(request, reason)
            continue

        if not _off_peak_allowed(config, now_utc()):
            reason = "blocked_off_peak"
            append_ledger(ledger_path, {
                "state": reason, "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
            })
            counts["pre_send_blocked"] += 1
            results_by_request[request_sha] = blocked_result(request, reason)
            continue

        budget_reason = _budget_block_reason(
            config=config, authorization=authorization, request=request,
            request_set=request_set, sent_count=sent_count,
            known_input_tokens=known_input_tokens,
            known_output_tokens=known_output_tokens, known_usd=known_usd,
            known_usage_unknown=known_usage_unknown)
        if budget_reason is not None:
            reason = ("blocked_usage_unknown"
                      if budget_reason == "usage_unknown_previous_request"
                      else "blocked_budget")
            append_ledger(ledger_path, {
                "state": reason, "reason": budget_reason,
                "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
            })
            counts["pre_send_blocked"] += 1
            result = blocked_result(request, reason)
            result["budget_reason"] = budget_reason
            results_by_request[request_sha] = result
            continue

        # After this append, a crash leaves an explicit sent state; the same
        # request is never auto-resent on resume.
        append_ledger(ledger_path, {
            "state": "send_started",
            "request_sha256": request_sha,
            "fallback_item_id": request.get("fallback_item_id"),
            "source_index": request.get("source_index"),
            "input_tokens_estimate": request.get("input_tokens_estimate"),
        })
        counts["attempted"] += 1
        counts["send_attempts"] += 1
        sent_count += 1
        attempted_request_shas.append(request_sha)
        try:
            raw = transport.complete(request)
        except PreSendTransportError as exc:
            append_ledger(ledger_path, {
                "state": "pre_send_failed",
                "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
                "error_type": type(exc).__name__,
            })
            counts["pre_send_failed"] += 1
            results_by_request[request_sha] = blocked_result(request, "pre_send_failed")
            continue
        except Exception as exc:  # noqa: BLE001 - any transport failure is in-doubt
            append_ledger(ledger_path, {
                "state": "in_doubt",
                "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
                "error_type": type(exc).__name__,
            })
            counts["in_doubt"] += 1
            counts["failed"] += 1
            known_usage_unknown = True
            halt_sending = True
            _append_normalized_once(normalized_path, by_request_records, {
                "fallback_item_id": request.get("fallback_item_id"),
                "source_index": request.get("source_index"),
                "request_sha256": request_sha,
                "response_sha256": None,
                "status": "in_doubt",
                "semantic_status": None,
                "action_status": None,
                "field_statuses": {},
                "response": None,
                "error": "in_doubt",
                "input_tokens": None,
                "output_tokens": None,
                "usd_cost": None,
                "usage_source": "unknown",
                "usage_known": False,
                "source": "fresh_run",
            })
            results_by_request[request_sha] = {
                "source_index": request.get("source_index"),
                "fallback_item_id": request.get("fallback_item_id"),
                "status": "failed",
                "error": "in_doubt",
                "terminal_state": "in_doubt",
                "response": None,
                "recovered_from_store": False,
                "request_sha256": request_sha,
            }
            continue

        content = str(raw.get("content") or "")
        response_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        input_tokens, output_tokens, usage_known, usage_source = _usage_from_raw(
            raw, request, mode)
        off_peak_used = bool(config.get("off_peak_only"))
        usd_cost = (estimate_usd_cost(input_tokens, output_tokens, config,
                                      off_peak=off_peak_used)
                    if usage_known else None)
        _write_raw_once(raw_dir / f"{request_sha}.json", {
            "fallback_item_id": request.get("fallback_item_id"),
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "provider": raw.get("provider"),
            "model": raw.get("model"),
            "finish_reason": raw.get("finish_reason"),
            "usage": raw.get("usage"),
            "decode_usage": ((raw.get("decode") or {}).get("usage")
                             if isinstance(raw.get("decode"), Mapping) else None),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd_cost": usd_cost,
            "usage_source": usage_source,
            "usage_known": usage_known,
            "price_snapshot": _price_snapshot(config),
            "off_peak": off_peak_used,
            "content": content,
        })
        validated = validate_semantic_grounding_response(
            content, request, confidence_threshold)
        if validated["status"] == "failed":
            error_text = str(validated.get("error"))
            terminal_state = ("malformed"
                              if ("invalid_json" in error_text
                                  or "not_text" in error_text
                                  or "root_not_object" in error_text)
                              else "rejected")
            record = {
                "fallback_item_id": request.get("fallback_item_id"),
                "source_index": request.get("source_index"),
                "request_sha256": request_sha,
                "response_sha256": response_sha,
                "status": terminal_state,
                "semantic_status": None,
                "action_status": None,
                "field_statuses": {},
                "response": None,
                "error": error_text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "usd_cost": usd_cost,
                "usage_source": usage_source,
                "usage_known": usage_known,
                "source": "fresh_run",
            }
            _append_normalized_once(normalized_path, by_request_records, record)
            append_ledger(ledger_path, {
                "state": terminal_state,
                "request_sha256": request_sha,
                "fallback_item_id": request.get("fallback_item_id"),
                "error": error_text,
                "response_sha256": response_sha,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "usd_cost": usd_cost,
                "usage_known": usage_known,
            })
            if terminal_state == "malformed":
                counts["malformed"] += 1
            else:
                counts["rejected_by_validator"] += 1
            counts["failed"] += 1
            results_by_request[request_sha] = {
                "source_index": request.get("source_index"),
                "fallback_item_id": request.get("fallback_item_id"),
                "status": "failed",
                "error": error_text,
                "terminal_state": terminal_state,
                "response": None,
                "recovered_from_store": False,
                "request_sha256": request_sha,
            }
            if usage_known:
                known_input_tokens += int(input_tokens or 0)
                known_output_tokens += int(output_tokens or 0)
                known_usd += float(usd_cost or 0.0)
            else:
                known_usage_unknown = True
                halt_sending = True
                counts["usage_unknown"] += 1
                append_ledger(ledger_path, {
                    "state": "usage_unknown",
                    "request_sha256": request_sha,
                    "reason": "provider_usage_missing_after_response",
                })
            continue

        response = validated["response"]
        semantic_status = _normalize_llm_status(response)
        action_status = (response.get("action_grounding") or {}).get("status")
        field_statuses = {
            field: ((response.get(field) or {}).get("status"))
            for field in ("condition", "constraint", "exception")
        }
        record = {
            "fallback_item_id": request.get("fallback_item_id"),
            "source_index": request.get("source_index"),
            "request_sha256": request_sha,
            "response_sha256": response_sha,
            "status": "succeeded",
            "semantic_status": semantic_status,
            "action_status": action_status,
            "field_statuses": field_statuses,
            "response": response,
            "error": None,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd_cost": usd_cost,
            "usage_source": usage_source,
            "usage_known": usage_known,
            "source": "fresh_run",
        }
        _append_normalized_once(normalized_path, by_request_records, record)
        append_ledger(ledger_path, {
            "state": "succeeded",
            "request_sha256": request_sha,
            "fallback_item_id": request.get("fallback_item_id"),
            "semantic_status": semantic_status,
            "response_sha256": response_sha,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "usd_cost": usd_cost,
            "usage_known": usage_known,
        })
        counts["succeeded"] += 1
        counts["resolved" if semantic_status == "resolved" else "ambiguous"] += 1
        results_by_request[request_sha] = {
            "source_index": request.get("source_index"),
            "fallback_item_id": request.get("fallback_item_id"),
            "status": "validated",
            "semantic_status": semantic_status,
            "action_status": action_status,
            "field_statuses": field_statuses,
            "response": response,
            "response_sha256": response_sha,
            "recovered_from_store": False,
            "request_sha256": request_sha,
        }
        if usage_known:
            known_input_tokens += int(input_tokens or 0)
            known_output_tokens += int(output_tokens or 0)
            known_usd += float(usd_cost or 0.0)
        else:
            known_usage_unknown = True
            halt_sending = True
            counts["usage_unknown"] += 1
            append_ledger(ledger_path, {
                "state": "usage_unknown",
                "request_sha256": request_sha,
                "reason": "provider_usage_missing_after_response",
            })

    ordered_results = [
        {**(results_by_request.get(str(request.get("request_sha256")))
            or blocked_result(request, "not_processed")),
         "fallback_item_id": request.get("fallback_item_id"),
         "source_index": request.get("source_index"),
         "side": request.get("side")}
        for request in object_requests
    ]
    no_double_send = not (set(attempted_request_shas) & resumed_sent_shas)
    run_status = _classify_run_status(counts, counts["item_count"])
    if known_usage_unknown and run_status == "complete":
        run_status = "partial"
    total_estimate = sum(int(request.get("input_tokens_estimate") or 0)
                         for request in requests)
    summary = {
        "schema_version": "s3_semantic_grounding_llm_execution@2.0.0",
        "runner_revision": LLM_RUNNER_REVISION,
        "base_revision": V2_REVISION,
        "mode": mode,
        "run_status": run_status,
        "counts": counts,
        "coverage": (round(counts["succeeded"] / counts["item_count"], 4)
                     if counts["item_count"] else None),
        "total_input_tokens_estimate": total_estimate,
        "total_input_tokens_actual": known_input_tokens,
        "total_output_tokens_actual": known_output_tokens,
        "total_usd_actual": round(known_usd, 6),
        "known_usage_complete": not known_usage_unknown,
        "requested_object_count": len(object_requests),
        "unique_request_count": len(requests),
        "shared_response_object_count": len(object_requests) - len(requests),
        "results": ordered_results,
        "ledger_path": str(ledger_path),
        "normalized_path": str(normalized_path),
        "raw_response_dir": str(raw_dir),
        "ledger_integrity": "ok",
        "retry": 0,
        "no_double_send": no_double_send,
        "resume_policy": (
            "sent states and persisted normalized records are terminal; only "
            "pre-send failures/blocks are retried on a later invocation"),
    }
    (run_root / "run_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")
    return summary

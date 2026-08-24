# -*- coding: utf-8 -*-
"""S2.12 complex-corpus execution wiring v2 — real-execution safety contract.

v2 hardening (2026-08-22, zero API, API BLOCKED / ZERO CALLS):

1. **Real payload lock (per call, not just at startup).**  Every transport
   call — fake or real — rebuilds the final HTTP body from the current
   prompts plus the *arm's locked policy*, serializes to UTF-8, computes
   SHA-256, and compares against the locked per-request body hash AND the
   sample/clause IDs and execution order.  Only an exact match may reach
   the network ("PayloadLockedRealTransport" / "PayloadLockedFakeTransport").
2. **Usage & cost capture.**  After every real response the runner reads
   ``transport.last_decode["usage"]`` (prompt/completion/total tokens;
   reasoning tokens are diagnostic only).  Cumulative USD cost is computed
   with the price snapshot bound in the authorization file:
   ``cost = input_cap_hit*hit_price + input_cap_miss*miss_price +
   output*output_price``; when the provider does not split cache hit/miss,
   the *conservative cache-miss price* mandated by the authorization
   contract is applied to ALL input tokens.  ``cost_usd`` is never hardcoded
   to zero on the real path.
3. **Real caps enforcement (per call).**  Before each call: Beijing-time
   window check, stage-payload-subset membership, call count, cumulative
   tokens/cost, conservative upper bound of the current request, price
   snapshot/runner-hash freshness.  After each response: accumulate provider
   usage, compute real cost, re-check input/output/USD caps, append the
   ledger, and refuse any further call once a stop boundary is reached.
4. **Append-only execution ledger + resume.**  After every successful HTTP
   response a hash-chained, never-overwritten ledger record is written
   (stage id, request id, payload sha, ordinal, request time, returned
   model, usage, cumulative usage, per-call cost, cumulative cost, response
   content hash, decode status, prev/current record hash).  Resume consumes
   the ledger, verifies the hash chain, refuses to re-call any already
   recorded payload, and continues from the next pre-registered payload.
   Partial runs are published as explicitly partial (never "succeeded").
5. **Staged execution.**  Pre-registered stage ids: Direct D-CAL (1 call),
   D-REST (35 calls); fallback F-1/F-2/F-3 (fixed subsets partitioning the
   27 locked calls).  CLI ``--stage-id``, ``--auth-file``,
   ``--resume-from-ledger``; arbitrary ``--start``/ID lists are rejected.
6. **No project .env.**  Real transport config is built with
   ``LLMConfig.from_env(project_root=ROOT, load_project_env=False)`` —
   only the process environment is consulted; a project ``.env`` file is
   never opened.  Secrets never enter outputs.
7. **Per-arm runner hash binding.**  The authorization contract binds the
   direct runner hash, the fallback runner hash, the shared execution
   module hash, and the transport/policy implementation hashes separately;
   each arm validates only its own runner hash.
8. **D-CAL calibration contract** is implemented as schema/builder/tests
   only (no real D-CAL authorization file is created this round).

This batch is ZERO API: real calls remain blocked pending user authorization.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Sequence

ROOT = Path(__file__).resolve().parents[2]          # formal_experiment/
PROJECT_ROOT = ROOT.parent                           # workspace root
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.llm_client import (  # noqa: E402
    LLMClientError,
    LLMRequest,
    LLMResponse,
    LLMTransport,
    OpenAICompatibleRequestBuilder,
    RealAPITransport,
)
from bpc_hybrid.h1_transport import (  # noqa: E402
    DEEPSEEK_V4_PRO_H1_POLICY,
    H1RequestPolicy,
)
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402

# Reuse the exact preflight reconstruction paths (byte-identical bodies).
from build_s2_12_api_preflight_v1 import (  # noqa: E402
    _config,
    _rerun_b0,
    _verify_file_bindings,
)
from run_direct_llm import _few_shot_block  # noqa: E402
from run_s2_12_sun_rule_only_v1 import _resolve_records  # noqa: E402
from run_sun_llm_fallback import (  # noqa: E402
    _build_context_audit,
    _build_user_prompt,
    allocate_repair_calls,
    build_repair_plans,
    build_transport_capture_row,
)

INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
PREFLIGHT_LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"
PREFLIGHT_REPORT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"

OUTPUT_DIRS = {
    "direct_llm": ROOT / "data/predictions/s2_12_direct_llm_v1",
    "sun_llm_fallback": ROOT / "data/predictions/s2_12_sun_llm_fallback_v1",
}

EXPECTED_INPUT_SHA = "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e"
REQUIRED_MODEL = "deepseek-v4-pro"

# Beijing-time off-peak window: peak 09:00-12:00 and 14:00-18:00 (UTC+8).
_BJ_OFFSET = timedelta(hours=8)

# Undesired keys that must never appear in committed outputs.
_FORBIDDEN_TEXT_KEYS = ("text", "source_text", "normalized", "marker_surface")
_FORBIDDEN_SECRET_KEYS = (
    "api_key", "apikey", "authorization", "access_token", "refresh_token",
    "cookie", "password", "secret", "client_secret",
)

PRICE_SNAPSHOT_SCHEMA = "s2_12_price_snapshot@1.0.0"


class S212ExecutionError(ValueError):
    """Fail-closed S2.12 execution error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _strip_text_fields(value: Any) -> Any:
    """Recursively drop raw-text keys from a committed prediction record."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            if key in ("source_text", "text", "normalized", "marker_surface"):
                continue
            out[key] = _strip_text_fields(child)
        return out
    if isinstance(value, list):
        return [_strip_text_fields(item) for item in value]
    return value


def _contains_forbidden(value: Any, keys: Sequence[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in keys:
                return True
            if _contains_forbidden(child, keys):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden(item, keys) for item in value)
    return False


def _usage_int(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


# ---------------------------------------------------------------------------
# Lock / input verification
# ---------------------------------------------------------------------------


def load_lock() -> dict[str, Any]:
    if _sha(INPUT) != EXPECTED_INPUT_SHA:
        raise S212ExecutionError("Gold-blind input drift")
    lock = json.loads(PREFLIGHT_LOCK.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "s2_12_api_arms_preflight_lock@1.0.0":
        raise S212ExecutionError("preflight lock schema identity drift")
    if lock.get("status") != "locked_without_api_authorization":
        raise S212ExecutionError("preflight lock status drift")
    if lock.get("authorization", {}).get("real_api_calls_allowed_by_this_lock") is not False:
        raise S212ExecutionError("preflight lock must not authorize API calls")
    _verify_file_bindings(lock["implementation_bindings"])
    return lock


def load_report() -> dict[str, Any]:
    report = json.loads(PREFLIGHT_REPORT.read_text(encoding="utf-8"))
    if report.get("schema_version") != "s2_12_api_preflight_report@1.0.0":
        raise S212ExecutionError("preflight report schema identity drift")
    if report.get("status") != "payloads_locked_zero_api_authorization_pending":
        raise S212ExecutionError("preflight report status drift")
    if report["input"]["sha256"] != EXPECTED_INPUT_SHA:
        raise S212ExecutionError("preflight report input binding drift")
    return report


def rebuild_and_verify_payloads(
    lock: Mapping[str, Any],
    report: Mapping[str, Any],
    runtime_home: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Rebuild the 63 request bodies with the exact preflight paths and
    verify every SHA-256, ID, and byte size against the locked report.

    Returns ``{"direct_llm": [...36...], "sun_llm_fallback": [...27...]}``
    where each row carries ``call_index/sample_id/clause_id/
    request_body_sha256/request_body_utf8_bytes/system_prompt/user_prompt``
    and (for the fallback arm) ``plan``/``plan_record``.
    """
    _adapted, batch = _rerun_b0(runtime_home)               # diagnostic replay
    config = _config(lock)
    builder = OpenAICompatibleRequestBuilder(config)

    direct_spec = lock["arms"]["direct_llm"]
    direct_prompt = load_prompt(direct_spec["prompt_name"])
    if direct_prompt.sha256 != direct_spec["prompt_sha256"]:
        raise S212ExecutionError("direct prompt drift")
    direct_policy = H1RequestPolicy(
        stream=False, thinking={"type": "disabled"}, response_format=None
    )
    few_shot = _few_shot_block(direct_prompt)
    locked_direct = {row["call_index"]: row for row in report["arms"]["direct_llm"]["calls"]}

    direct_rows: list[dict[str, Any]] = []
    for index, item in enumerate(batch, 1):
        record = item.record
        user_prompt = direct_prompt.user_prompt_template.format(
            sample_id=record["sample_id"],
            source_id=record["sample_id"],
            source_text=record["source_text"],
            few_shot_block=few_shot,
        )
        body = direct_policy.apply_to_body(
            builder.build_body(direct_prompt.system_prompt, user_prompt)
        )
        body_bytes = json.dumps(body).encode("utf-8")
        row = {
            "call_index": index,
            "sample_id": record["sample_id"],
            "clause_id": None,
            "request_body_sha256": _sha_bytes(body_bytes),
            "request_body_utf8_bytes": len(body_bytes),
            "system_prompt": direct_prompt.system_prompt,
            "user_prompt": user_prompt,
            "body": body,
        }
        expected = locked_direct.get(index)
        if expected is None or expected["sample_id"] != row["sample_id"]:
            raise S212ExecutionError(f"direct call {index}: locked report order/ID drift")
        if expected["request_body_sha256"] != row["request_body_sha256"]:
            raise S212ExecutionError(
                f"direct call {index} ({row['sample_id']}): rebuilt payload SHA "
                f"{row['request_body_sha256'][:12]} != locked "
                f"{expected['request_body_sha256'][:12]}"
            )
        if expected["request_body_utf8_bytes"] != row["request_body_utf8_bytes"]:
            raise S212ExecutionError(f"direct call {index}: body byte size drift")
        direct_rows.append(row)
    if len(direct_rows) != len(locked_direct):
        raise S212ExecutionError("direct call count != 36")

    h1_spec = lock["arms"]["sun_llm_fallback"]
    h1_prompt = load_prompt(h1_spec["prompt_name"])
    if h1_prompt.sha256 != h1_spec["prompt_sha256"]:
        raise S212ExecutionError("H1 prompt drift")
    plans = allocate_repair_calls(
        build_repair_plans(batch), h1_spec["max_calls"]
    )
    records = {item.record["sample_id"]: item.record for item in batch}
    locked_h1 = {row["call_index"]: row for row in report["arms"]["sun_llm_fallback"]["calls"]}
    h1_rows: list[dict[str, Any]] = []
    for index, plan in enumerate(plans, 1):
        record = records[plan.sample_id]
        clause = record["clauses"][plan.clause_index]
        context_clause, audit = _build_context_audit(clause, plan, "full_b0_v4")
        if not audit.get("original_record_unchanged"):
            raise S212ExecutionError(
                f"H1 context mutated B0 record: {plan.sample_id}/{plan.clause_id}"
            )
        user_prompt = _build_user_prompt(h1_prompt, record, plan, context_clause)
        body = DEEPSEEK_V4_PRO_H1_POLICY.apply_to_body(
            builder.build_body(h1_prompt.system_prompt, user_prompt)
        )
        body_bytes = json.dumps(body).encode("utf-8")
        row = {
            "call_index": index,
            "sample_id": plan.sample_id,
            "clause_id": plan.clause_id,
            "clause_index": plan.clause_index,
            "plan": plan,
            "plan_record": record,
            "request_body_sha256": _sha_bytes(body_bytes),
            "request_body_utf8_bytes": len(body_bytes),
            "system_prompt": h1_prompt.system_prompt,
            "user_prompt": user_prompt,
            "body": body,
        }
        expected = locked_h1.get(index)
        if expected is None or (
            expected["sample_id"], expected.get("clause_id"),
        ) != (row["sample_id"], row["clause_id"]):
            raise S212ExecutionError(f"fallback call {index}: locked report order/ID drift")
        if expected["request_body_sha256"] != row["request_body_sha256"]:
            raise S212ExecutionError(
                f"fallback call {index} ({row['sample_id']}/{row['clause_id']}): "
                f"rebuilt payload SHA {row['request_body_sha256'][:12]} != locked "
                f"{expected['request_body_sha256'][:12]}"
            )
        if expected["request_body_utf8_bytes"] != row["request_body_utf8_bytes"]:
            raise S212ExecutionError(f"fallback call {index}: body byte size drift")
        h1_rows.append(row)
    if len(h1_rows) != len(locked_h1):
        raise S212ExecutionError("fallback call count != 27")

    return {"direct_llm": direct_rows, "sun_llm_fallback": h1_rows}


# ---------------------------------------------------------------------------
# Arm policies (MUST match the preflight lock exactly)
# ---------------------------------------------------------------------------


def arm_policy(arm: str) -> H1RequestPolicy:
    if arm == "direct_llm":
        return H1RequestPolicy(
            stream=False, thinking={"type": "disabled"}, response_format=None
        )
    if arm == "sun_llm_fallback":
        return DEEPSEEK_V4_PRO_H1_POLICY  # stream=False, thinking disabled,
        # response_format={"type": "json_object"}, tools_sent=False
    raise S212ExecutionError(f"unknown arm {arm!r}")


def arm_sampling(lock: Mapping[str, Any]) -> dict[str, Any]:
    common = lock["common_sampling"]
    return {
        "temperature": common["temperature"],
        "top_p": common["top_p"],
        "max_tokens": common["max_output_tokens_per_call"],
        "seed": common["seed"],
        "seed_supported": common["seed_supported"],
    }


# ---------------------------------------------------------------------------
# Payload lock (per call; shared by fake and real transports)
# ---------------------------------------------------------------------------


class PayloadLock:
    """Per-call payload lock: rebuild the final body and verify SHA/IDs/order.

    An instance is created per arm.  ``verify(request, ordinal)`` rebuilds
    the body exactly as the transport would (locked policy + model +
    sampling), hashes it, and requires:

    * the body SHA to equal the locked per-request hash for ``ordinal``,
    * ``sample_id`` (and ``clause_id`` for the fallback arm) to match,
    * ``ordinal`` to match the locked execution order.

    No network call may happen unless ``verify`` returns True.
    """

    def __init__(
        self,
        arm: str,
        locked_rows: Sequence[Mapping[str, Any]],
        builder: OpenAICompatibleRequestBuilder,
        policy: H1RequestPolicy,
    ) -> None:
        self._arm = arm
        self._policy = policy
        self._rows_by_ordinal = {
            int(row["call_index"]): dict(row) for row in locked_rows
        }
        self._builder = builder

    def rebuild_body_bytes(self, request: LLMRequest) -> bytes:
        base = self._builder.build_body(
            request.system_prompt, request.user_prompt
        )
        body = self._policy.apply_to_body(base)
        return json.dumps(body).encode("utf-8")

    def verify(
        self, request: LLMRequest, ordinal: int, clause_id: str | None = None
    ) -> dict[str, Any]:
        expected = self._rows_by_ordinal.get(int(ordinal))
        if expected is None:
            raise S212ExecutionError(
                f"payload lock: no locked row for ordinal {ordinal}"
            )
        body_bytes = self.rebuild_body_bytes(request)
        body_sha = _sha_bytes(body_bytes)
        if body_sha != expected["request_body_sha256"]:
            raise S212ExecutionError(
                f"payload lock: ordinal {ordinal} body SHA "
                f"{body_sha[:12]} != locked {expected['request_body_sha256'][:12]}"
            )
        if expected.get("sample_id") != request.source_id:
            raise S212ExecutionError(
                f"payload lock: ordinal {ordinal} sample mismatch "
                f"{expected.get('sample_id')!r} != {request.source_id!r}"
            )
        expected_clause = expected.get("clause_id")
        if (expected_clause or None) != (clause_id or None):
            raise S212ExecutionError(
                f"payload lock: ordinal {ordinal} clause mismatch "
                f"{expected_clause!r} != {clause_id!r}"
            )
        if int(expected["call_index"]) != int(ordinal):
            raise S212ExecutionError(
                f"payload lock: ordinal {ordinal} order drift "
                f"(locked call_index {expected['call_index']})"
            )
        return {
            "request_body_sha256": body_sha,
            "request_body_utf8_bytes": len(body_bytes),
            "sample_id": request.source_id,
            "clause_id": clause_id,
            "call_index": int(ordinal),
        }


class PayloadLockedFakeTransport(LLMTransport):
    """Payload-locked deterministic fake transport (no network, no .env).

    Exposes a synthetic ``last_decode`` with deterministic usage so the
    runner's usage/cost/ledger path is exercised identically to the real
    path (usage is fixture data; no billing occurs).
    """

    def __init__(self, payload_lock: PayloadLock, arm: str) -> None:
        self._lock = payload_lock
        self._arm = arm
        self.last_decode: dict[str, Any] | None = None

    def send(
        self, request: LLMRequest, *, ordinal: int = 1,
        clause_id: str | None = None,
    ) -> LLMResponse:
        try:
            self._lock.verify(request, ordinal, clause_id=clause_id)
        except S212ExecutionError as exc:
            raise LLMClientError(str(exc)) from exc
        usage = {
            "prompt_tokens": 120,
            "completion_tokens": 64,
            "total_tokens": 184,
            "reasoning_tokens": 0,
        }
        self.last_decode = {
            "status": "ok_message_content",
            "model": REQUIRED_MODEL,
            "usage": usage,
            "finish_reason": "stop",
        }
        if self._arm == "direct_llm":
            from bpc_hybrid.llm_client import make_schema_valid_mock_response_json
            content = make_schema_valid_mock_response_json(
                source_text=request.source_text, source_id=request.source_id
            )
            return LLMResponse(
                content=content, provider="fake", model=REQUIRED_MODEL,
                finish_reason="stop",
            )
        return LLMResponse(
            content=json.dumps({
                "sample_id": request.source_id,
                "clause_id": clause_id or "synthetic-fake-clause",
                "repair_fields": [],
                "patches": {},
                "reason": "synthetic fake transport fixture (no-op)",
            }),
            provider="fake", model=REQUIRED_MODEL, finish_reason="stop",
        )


class PayloadLockedRealTransport(LLMTransport):
    """Real HTTP transport with a per-call payload lock.

    Before ANY network request is made, the final body is rebuilt with the
    arm's locked policy and model/sampling, hashed, and verified against the
    locked per-request hash, sample/clause ID, and execution order.  Only an
    exact match may reach ``RealAPITransport.send``.

    The real transport is created with ``LLMConfig.from_env(project_root,
    load_project_env=False)`` so a project ``.env`` is never opened.
    """

    def __init__(
        self,
        payload_lock: PayloadLock,
        config: Any,
        timeout_seconds: float = 180.0,
    ) -> None:
        self._lock = payload_lock
        self._real = RealAPITransport(config, timeout_seconds=timeout_seconds)

    @property
    def last_decode(self) -> dict[str, Any] | None:
        return self._real.last_decode

    @property
    def last_request_body_sha256(self) -> str | None:
        return self._real.last_request_body_sha256

    def send(
        self, request: LLMRequest, *, ordinal: int = 1,
        clause_id: str | None = None,
    ) -> LLMResponse:
        try:
            self._lock.verify(request, ordinal, clause_id=clause_id)
        except S212ExecutionError as exc:
            raise LLMClientError(str(exc)) from exc
        return self._real.send(request)


# ---------------------------------------------------------------------------
# Authorization gate (v2: per-arm runner hash + stage contract)
# ---------------------------------------------------------------------------

AUTHORIZATION_REQUIRED_FIELDS = (
    "schema_version",
    "authorization_sentence_utf8_sha256",
    "authorization_event_file",
    "authorization_event_file_sha256",
    "model",
    "calls",
    "stage_id",
    "stage_payload_hashes",
    "stage_call_cap",
    "global_input_token_cap",
    "global_output_token_cap",
    "global_usd_cost_cap",
    "allowed_windows",
    "price_snapshot",
    "price_checked_at_utc",
    "runner_implementation_hashes",
    "input_config_prompt_hashes",
    "prev_stage_ledger_hash",
    "final_63_payload_hashes",
    "retry",
    "gold_isolation",
)


def _validate_price_snapshot(auth: Mapping[str, Any]) -> None:
    snapshot = auth["price_snapshot"]
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != PRICE_SNAPSHOT_SCHEMA:
        raise S212ExecutionError("authorization price snapshot schema drift")
    for key in ("input_cache_hit_per_million", "input_cache_miss_per_million",
                "output_per_million", "currency"):
        if key not in snapshot:
            raise S212ExecutionError(f"price snapshot missing {key!r}")
    if snapshot["currency"] != "USD":
        raise S212ExecutionError("price snapshot currency must be USD")
    for key in ("input_cache_hit_per_million", "input_cache_miss_per_million",
                "output_per_million"):
        if not isinstance(snapshot[key], (int, float)) or snapshot[key] < 0:
            raise S212ExecutionError(f"price snapshot {key} invalid")


def validate_authorization(
    auth: Mapping[str, Any],
    lock: Mapping[str, Any],
    report: Mapping[str, Any],
    arm: str,
    runner_hash: str,
    implementation_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Validate an authorization file against the lock/report contract.

    ``arm`` selects the runner hash that MUST be bound to this authorization;
    the shared module and transport/policy implementation hashes are checked
    for every arm.  Missing/mismatched fields raise BEFORE any transport
    call.
    """
    missing = [name for name in AUTHORIZATION_REQUIRED_FIELDS if name not in auth]
    if missing:
        raise S212ExecutionError(
            f"authorization file missing required fields: {missing}"
        )
    if auth["schema_version"] != "s2_12_api_authorization@1.1.0":
        raise S212ExecutionError("authorization schema identity drift")
    if auth["model"] != REQUIRED_MODEL:
        raise S212ExecutionError(f"authorization model {auth['model']!r} != {REQUIRED_MODEL!r}")
    if auth["retry"] != 0:
        raise S212ExecutionError("authorization retry must be 0")
    if auth["stage_call_cap"] <= 0:
        raise S212ExecutionError("stage call cap must be positive")
    for key in ("global_input_token_cap", "global_output_token_cap",
                "global_usd_cost_cap"):
        if auth[key] <= 0:
            raise S212ExecutionError(f"authorization {key} must be positive")
    if auth.get("gold_isolation", {}).get("api_arms_must_not_read_gold") is not True:
        raise S212ExecutionError("authorization Gold isolation declaration invalid")
    if auth["allowed_windows"] not in ("any_time", "off_peak_only"):
        raise S212ExecutionError("authorization allowed_windows invalid")
    _validate_price_snapshot(auth)

    # --- runner/implementation hash binding --------------------------------
    runner_map = auth["runner_implementation_hashes"]
    required_keys = {
        "run_s2_12_direct_llm_v1",
        "run_s2_12_sun_llm_fallback_v1",
        "s2_12_execution",
        "llm_client",
        "h1_transport",
    }
    if not required_keys.issubset(runner_map):
        raise S212ExecutionError(
            "authorization runner_implementation_hashes missing keys: "
            f"{sorted(required_keys - set(runner_map))}"
        )
    arm_runner_key = {
        "direct_llm": "run_s2_12_direct_llm_v1",
        "sun_llm_fallback": "run_s2_12_sun_llm_fallback_v1",
    }[arm]
    if runner_map[arm_runner_key] != runner_hash:
        raise S212ExecutionError(
            f"authorization runner hash mismatch for {arm}: "
            f"authorized {runner_map[arm_runner_key][:12]} != current {runner_hash[:12]}"
        )
    for impl_key, current_hash in implementation_hashes.items():
        if impl_key in runner_map and runner_map[impl_key] != current_hash:
            raise S212ExecutionError(
                f"authorization implementation hash mismatch for {impl_key}"
            )

    # --- payload binding (stage subset + final 63 commitment) -------------
    expected_63 = {
        row["request_body_sha256"]
        for arm_name in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm_name]["calls"]
    }
    final = set(auth["final_63_payload_hashes"])
    if final != expected_63:
        raise S212ExecutionError(
            "authorization final 63 payload hash set != locked 63 bodies"
        )
    stage_hashes = set(auth["stage_payload_hashes"])
    if not stage_hashes:
        raise S212ExecutionError("authorization stage payload hashes empty")
    if not stage_hashes.issubset(expected_63):
        raise S212ExecutionError("authorization stage payloads not in the locked 63")
    if len(stage_hashes) > auth["stage_call_cap"]:
        raise S212ExecutionError(
            "authorization stage call cap smaller than stage payload count"
        )

    if auth["input_config_prompt_hashes"]["input_sha256"] != EXPECTED_INPUT_SHA:
        raise S212ExecutionError("authorization input hash mismatch")
    if auth["input_config_prompt_hashes"]["lock_sha256"] != _sha(PREFLIGHT_LOCK):
        raise S212ExecutionError("authorization lock hash mismatch")
    if auth["input_config_prompt_hashes"]["prompt_direct_sha256"] != \
            lock["arms"]["direct_llm"]["prompt_sha256"]:
        raise S212ExecutionError("authorization direct prompt hash mismatch")
    if auth["input_config_prompt_hashes"]["prompt_fallback_sha256"] != \
            lock["arms"]["sun_llm_fallback"]["prompt_sha256"]:
        raise S212ExecutionError("authorization fallback prompt hash mismatch")
    return dict(auth)


def load_and_validate_authorization(
    auth_path: Path,
    lock: Mapping[str, Any],
    report: Mapping[str, Any],
    arm: str,
    runner_hash: str,
    implementation_hashes: Mapping[str, str],
) -> dict[str, Any]:
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S212ExecutionError(f"invalid authorization file: {exc}") from exc
    if not isinstance(auth, dict):
        raise S212ExecutionError("authorization file must be a JSON object")
    return validate_authorization(auth, lock, report, arm, runner_hash,
                                  implementation_hashes)


# ---------------------------------------------------------------------------
# Beijing-time off-peak window (UTC+8)
# ---------------------------------------------------------------------------


def beijing_time(now_utc: datetime | None = None) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(timezone.utc) + _BJ_OFFSET


def is_beijing_peak(now_utc: datetime | None = None) -> bool:
    bj = beijing_time(now_utc)
    minutes = bj.hour * 60 + bj.minute
    return (9 * 60 <= minutes < 12 * 60) or (14 * 60 <= minutes < 18 * 60)


def check_off_peak_only(auth: Mapping[str, Any], now_utc: datetime | None = None) -> None:
    if auth.get("allowed_windows") != "off_peak_only":
        return
    if is_beijing_peak(now_utc):
        raise S212ExecutionError(
            "off-peak-only authorization refuses to run during a Beijing peak window"
        )


# ---------------------------------------------------------------------------
# Stage contract (pre-registered subsets; no arbitrary --start / ID lists)
# ---------------------------------------------------------------------------

STAGE_CONTRACT: dict[str, Any] = {
    "schema_version": "s2_12_stage_contract@1.0.0",
    "arms": {
        "direct_llm": {
            "stages": {
                "D-CAL": {"ordinals": [1], "off_peak_only": True,
                          "label": "single-request billing calibration"},
                "D-REST": {"ordinals": list(range(2, 37)),
                           "off_peak_only": False,
                           "label": "remaining 35 locked direct payloads"},
            },
        },
        "sun_llm_fallback": {
            "stages": {
                "F-1": {"ordinals": list(range(1, 10)), "off_peak_only": False},
                "F-2": {"ordinals": list(range(10, 19)), "off_peak_only": False},
                "F-3": {"ordinals": list(range(19, 28)), "off_peak_only": False},
            },
        },
    },
}


def stage_ordinals(arm: str, stage_id: str) -> list[int]:
    arm_contract = STAGE_CONTRACT["arms"].get(arm)
    if arm_contract is None:
        raise S212ExecutionError(f"unknown arm {arm!r} in stage contract")
    stage = arm_contract["stages"].get(stage_id)
    if stage is None:
        raise S212ExecutionError(
            f"unknown stage {stage_id!r} for {arm}; allowed: "
            f"{sorted(arm_contract['stages'])}"
        )
    return list(stage["ordinals"])


def stage_requires_off_peak(arm: str, stage_id: str) -> bool:
    return bool(
        STAGE_CONTRACT["arms"][arm]["stages"][stage_id].get("off_peak_only", False)
    )


# ---------------------------------------------------------------------------
# Cost accounting
# ---------------------------------------------------------------------------


def per_call_cost(
    usage: Mapping[str, Any],
    price: Mapping[str, Any],
) -> dict[str, Any]:
    """Compute input/output token counts and USD cost for one response.

    Cache hit/miss split: if the provider returns
    ``prompt_cache_hit_tokens``/``prompt_cache_miss_tokens`` we use them;
    otherwise ALL input tokens are billed at the conservative cache-miss
    price (the authorization contract's mandated fallback).
    """
    prompt = _usage_int(usage, "prompt_tokens")
    completion = _usage_int(usage, "completion_tokens")
    cache_hit = _usage_int(usage, "prompt_cache_hit_tokens")
    cache_miss = _usage_int(usage, "prompt_cache_miss_tokens")
    if cache_hit + cache_miss == 0 and prompt > 0:
        # provider did not split -> conservative cache-miss for all input
        cache_hit, cache_miss = 0, prompt
    hit_price = float(price["input_cache_hit_per_million"])
    miss_price = float(price["input_cache_miss_per_million"])
    out_price = float(price["output_per_million"])
    cost = (
        cache_hit * hit_price / 1_000_000
        + cache_miss * miss_price / 1_000_000
        + completion * out_price / 1_000_000
    )
    return {
        "input_tokens": prompt,
        "output_tokens": completion,
        "cache_hit_tokens": cache_hit,
        "cache_miss_tokens": cache_miss,
        "cost_usd": round(cost, 8),
    }


# ---------------------------------------------------------------------------
# Append-only execution ledger
# ---------------------------------------------------------------------------

LEDGER_SCHEMA = "s2_12_execution_ledger@1.0.0"


def ledger_record(
    *,
    stage_id: str,
    request_id: str,
    payload_sha: str,
    ordinal: int,
    request_time_utc: str,
    returned_model: str | None,
    usage: Mapping[str, Any],
    cumulative_usage: Mapping[str, int],
    per_call_cost: Mapping[str, Any],
    cumulative_cost: float,
    response_content_sha: str,
    decode_status: str,
    accepted: bool | None,
    prev_hash: str,
) -> dict[str, Any]:
    record = {
        "schema_version": LEDGER_SCHEMA,
        "stage_id": stage_id,
        "request_id": request_id,
        "payload_sha": payload_sha,
        "ordinal": ordinal,
        "request_time_utc": request_time_utc,
        "returned_model": returned_model,
        "usage": dict(usage),
        "cumulative_usage": dict(cumulative_usage),
        "per_call_cost_usd": per_call_cost["cost_usd"],
        "cumulative_cost_usd": round(cumulative_cost, 8),
        "response_content_sha": response_content_sha,
        "decode_status": decode_status,
        "patch_accepted": accepted,
        "prev_hash": prev_hash,
    }
    record["record_hash"] = _sha_text(json.dumps(
        {k: v for k, v in record.items() if k != "record_hash"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ))
    return record


class ExecutionLedger:
    """Append-only, hash-chained execution ledger with resume support.

    Every record is appended atomically (write temp + replace, no
    overwrite of history).  Resume verifies the chain and refuses to
    re-call any payload already recorded for this stage.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        lines = self.path.read_text(encoding="utf-8").splitlines()
        prev = ""
        for line in lines:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("schema_version") != LEDGER_SCHEMA:
                raise S212ExecutionError("ledger schema drift")
            if record.get("prev_hash", "") != prev:
                raise S212ExecutionError(
                    "ledger hash chain broken (tamper or corruption)"
                )
            recomputed = _sha_text(json.dumps(
                {k: v for k, v in record.items() if k not in ("record_hash", "prev_hash")},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ))
            # recompute including prev_hash: the record hash covers prev_hash
            inner = {k: v for k, v in record.items() if k != "record_hash"}
            recomputed = _sha_text(json.dumps(
                inner, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ))
            if recomputed != record.get("record_hash"):
                raise S212ExecutionError("ledger record hash mismatch")
            self._records.append(record)
            prev = record["record_hash"]

    @property
    def records(self) -> list[dict[str, Any]]:
        return list(self._records)

    @property
    def last_hash(self) -> str:
        if not self._records:
            return ""
        return self._records[-1]["record_hash"]

    def called_payloads(self, stage_id: str | None = None) -> set[str]:
        return {
            rec["payload_sha"]
            for rec in self._records
            if stage_id is None or rec["stage_id"] == stage_id
        }

    def append(self, record: Mapping[str, Any]) -> None:
        if record.get("schema_version") != LEDGER_SCHEMA:
            raise S212ExecutionError("ledger record schema drift")
        self._records.append(dict(record))
        self._flush()

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            json.dumps(rec, ensure_ascii=False, sort_keys=True)
            for rec in self._records
        ]
        payload = ("\n".join(lines) + "\n").encode("utf-8")
        staged = self.path.with_suffix(".tmp")                       # noqa: F841
        # atomic replace: write to a sibling temp then rename over the ledger
        temp = self.path.parent / f".{self.path.name}.staging-{os.getpid()}"
        temp.write_bytes(payload)
        temp.replace(self.path)


# ---------------------------------------------------------------------------
# Per-call cap & time gating
# ---------------------------------------------------------------------------


@dataclass
class CumulativeState:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    cost_usd: float = 0.0

    def add_usage(self, usage: Mapping[str, Any],
                  price: Mapping[str, Any]) -> dict[str, Any]:
        cost_info = per_call_cost(usage, price)
        self.calls += 1
        self.input_tokens += cost_info["input_tokens"]
        self.output_tokens += cost_info["output_tokens"]
        self.cache_hit_tokens += cost_info["cache_hit_tokens"]
        self.cache_miss_tokens += cost_info["cache_miss_tokens"]
        self.cost_usd += cost_info["cost_usd"]
        return cost_info

    def snapshot(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_hit_tokens": self.cache_hit_tokens,
            "cache_miss_tokens": self.cache_miss_tokens,
            "cost_usd": round(self.cost_usd, 8),
        }


def check_pre_call(
    *,
    auth: Mapping[str, Any],
    lock: Mapping[str, Any],
    report: Mapping[str, Any],
    arm: str,
    stage_id: str,
    stage_rows: Sequence[Mapping[str, Any]],
    ordinal: int,
    state: CumulativeState,
    now_utc: datetime | None = None,
) -> None:
    """Fail-closed checks immediately before a transport call."""
    # 1) Beijing-time window (checked EVERY call for off-peak-only auth)
    check_off_peak_only(auth, now_utc)
    # D-CAL is additionally always off-peak by stage contract
    if stage_requires_off_peak(arm, stage_id):
        if is_beijing_peak(now_utc):
            raise S212ExecutionError(
                f"stage {stage_id} is off-peak-only; peak window refused (Beijing time)"
            )
    # 2) call count
    if state.calls + 1 > auth["stage_call_cap"]:
        raise S212ExecutionError("stage call cap would be exceeded")
    # 3) ordinal must exist in the pre-registered stage subset
    stage_ord = stage_ordinals(arm, stage_id)
    if ordinal not in stage_ord:
        raise S212ExecutionError(
            f"ordinal {ordinal} not in pre-registered stage {stage_id} subset"
        )
    # 4) cumulative caps
    if state.input_tokens >= auth["global_input_token_cap"]:
        raise S212ExecutionError("global input-token cap reached")
    if state.output_tokens >= auth["global_output_token_cap"]:
        raise S212ExecutionError("global output-token cap reached")
    if state.cost_usd >= auth["global_usd_cost_cap"]:
        raise S212ExecutionError("global USD cap reached")
    # 5) conservative upper bound of this request must not exceed caps
    price = auth["price_snapshot"]
    usage_bound = {"prompt_tokens": 200000, "completion_tokens": 4096}
    bound_cost = per_call_cost(usage_bound, price)["cost_usd"]
    if state.input_tokens + 200000 > auth["global_input_token_cap"]:
        raise S212ExecutionError(
            "conservative input upper bound would exceed the global input cap"
        )
    if state.output_tokens + 4096 > auth["global_output_token_cap"]:
        raise S212ExecutionError(
            "conservative output upper bound would exceed the global output cap"
        )
    if state.cost_usd + bound_cost > auth["global_usd_cost_cap"]:
        raise S212ExecutionError(
            "conservative USD upper bound would exceed the global USD cap"
        )
    # 6) price snapshot / runner hash validity (static binding re-checked)
    _validate_price_snapshot(auth)


def check_post_call(
    *,
    auth: Mapping[str, Any],
    state: CumulativeState,
) -> None:
    if state.input_tokens > auth["global_input_token_cap"]:
        raise S212ExecutionError("input-token cap exceeded after response")
    if state.output_tokens > auth["global_output_token_cap"]:
        raise S212ExecutionError("output-token cap exceeded after response")
    if state.cost_usd > auth["global_usd_cost_cap"]:
        raise S212ExecutionError("USD cap exceeded after response")


# ---------------------------------------------------------------------------
# Atomic output publishing
# ---------------------------------------------------------------------------


def atomic_publish_directory(output_dir: Path, files: Mapping[str, bytes]) -> None:
    if output_dir.exists():
        raise S212ExecutionError(f"refusing to overwrite existing run: {output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = output_dir.parent / f".{output_dir.name}.staging-{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        for name, data in files.items():
            (stage / name).write_bytes(data)
        stage.rename(output_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def manifest_capsule(artifacts: Mapping[str, bytes]) -> dict[str, Any]:
    return {
        name: {
            "sha256": _sha_bytes(data),
            "byte_size": len(data),
        }
        for name, data in artifacts.items()
    }


def build_cost_doc(
    *,
    llm_calls: int,
    max_calls: int,
    input_tokens_billed: int,
    output_tokens_billed: int,
    actual_cost_usd: float,
    fake: bool,
    price_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "s2_12_arm_cost@1.1.0",
        "llm_calls": llm_calls,
        "max_calls": max_calls,
        "input_tokens_billed": input_tokens_billed,
        "output_tokens_billed": output_tokens_billed,
        "actual_cost_usd": round(actual_cost_usd, 8),
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "billing_source": "response_usage" if not fake else "fixture_zero",
        "price_snapshot": dict(price_snapshot) if price_snapshot else None,
    }


# ---------------------------------------------------------------------------
# Stage executor (per-call loop with ledger, caps, off-peak, resume)
# ---------------------------------------------------------------------------


class StageExecutor:
    """Execute one pre-registered stage with full per-call safety contract.

    The executor owns per-call payload verification (via ``PayloadLock``),
    pre/post-call cap and time checks, usage/cost accumulation, the
    append-only ledger, and resume-from-ledger semantics.  It never writes
    the final predictions capsule itself (the runner publishes only after
    the whole arm completes); partial state is recorded in the ledger and a
    partial manifest.
    """

    def __init__(
        self,
        *,
        arm: str,
        stage_id: str,
        auth: Mapping[str, Any],
        lock: Mapping[str, Any],
        report: Mapping[str, Any],
        rows_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
        payload_lock: PayloadLock,
        transport: LLMTransport,
        ledger_path: Path,
        source_by_id: Mapping[str, str] | None = None,
        now_provider: Any = None,
    ) -> None:
        self.arm = arm
        self.stage_id = stage_id
        self.auth = auth
        self.lock = lock
        self.report = report
        self.rows = list(rows_by_arm[arm])
        self.payload_lock = payload_lock
        self.transport = transport
        self.ledger = ExecutionLedger(ledger_path)
        self.source_by_id = dict(source_by_id or {})
        self.now_provider = now_provider or datetime.now
        self.response_records: list[dict[str, Any]] = []
        self.state = CumulativeState()
        # Rebuild cumulative state from the ledger (resume support).
        for rec in self.ledger.records:
            usage = rec.get("usage", {})
            price = auth["price_snapshot"]
            self.state.add_usage(usage, price)
        # Called payloads for this stage (no duplicate calls on resume).
        self._called = self.ledger.called_payloads(stage_id)

    def _stage_rows_in_order(self) -> list[Mapping[str, Any]]:
        ordinals = stage_ordinals(self.arm, self.stage_id)
        by_ordinal = {int(row["call_index"]): row for row in self.rows}
        rows: list[Mapping[str, Any]] = []
        for ordinal in ordinals:
            row = by_ordinal.get(ordinal)
            if row is None:
                raise S212ExecutionError(
                    f"stage {self.stage_id} ordinal {ordinal} missing from locked rows"
                )
            rows.append(row)
        return rows

    def run(self) -> dict[str, Any]:
        """Execute the stage; returns the ledger + cumulative state + status."""
        rows = self._stage_rows_in_order()
        for row in rows:
            ordinal = int(row["call_index"])
            payload_sha = row["request_body_sha256"]
            if payload_sha in self._called:
                # Resume: already recorded -> skip (never re-call).
                continue
            clause_id = row.get("clause_id")
            source_text = self.source_by_id.get(row["sample_id"], "")
            request = LLMRequest(
                source_id=row["sample_id"],
                source_text=source_text,
                system_prompt=row["system_prompt"],
                user_prompt=row["user_prompt"],
            )
            check_pre_call(
                auth=self.auth, lock=self.lock, report=self.report,
                arm=self.arm, stage_id=self.stage_id, stage_rows=rows,
                ordinal=ordinal, state=self.state,
                now_utc=self.now_provider(),
            )
            try:
                response = self.transport.send(
                    request, ordinal=ordinal, clause_id=clause_id
                )
            except LLMClientError as exc:
                raise S212ExecutionError(
                    f"transport failure on {row['sample_id']} "
                    f"(ordinal {ordinal}): {exc}"
                ) from exc
            returned = getattr(response, "model", None)
            if returned and str(returned) != REQUIRED_MODEL:
                raise S212ExecutionError(
                    f"returned model {returned!r} != {REQUIRED_MODEL!r} "
                    f"(ordinal {ordinal})"
                )
            usage: dict[str, Any] = {}
            decode_status = "n/a"
            decode = getattr(self.transport, "last_decode", None)
            if decode is not None:
                decode_status = str(decode.get("status", "n/a"))
                usage = dict(decode.get("usage") or {})
            if not usage:
                raise S212ExecutionError(
                    f"provider usage missing for ordinal {ordinal} "
                    f"(decode status {decode_status})"
                )
            per_call = self.state.add_usage(usage, self.auth["price_snapshot"])
            check_post_call(auth=self.auth, state=self.state)
            record = ledger_record(
                stage_id=self.stage_id,
                request_id=f"{row['sample_id']}/{row.get('clause_id') or '-'}",
                payload_sha=payload_sha,
                ordinal=ordinal,
                request_time_utc=datetime.now(timezone.utc).isoformat(),
                returned_model=str(returned) if returned else None,
                usage=usage,
                cumulative_usage={
                    "input_tokens": self.state.input_tokens,
                    "output_tokens": self.state.output_tokens,
                    "cache_hit_tokens": self.state.cache_hit_tokens,
                    "cache_miss_tokens": self.state.cache_miss_tokens,
                },
                per_call_cost=per_call,
                cumulative_cost=self.state.cost_usd,
                response_content_sha=_sha_text(response.content),
                decode_status=decode_status,
                accepted=None,
                prev_hash=self.ledger.last_hash,
            )
            self.ledger.append(record)
            self._called.add(payload_sha)
            self.response_records.append({
                "ordinal": ordinal,
                "sample_id": row["sample_id"],
                "clause_id": row.get("clause_id"),
                "payload_sha": payload_sha,
                "returned_model": str(returned) if returned else None,
                "usage": dict(usage),
                "decode_status": decode_status,
                "per_call_cost_usd": per_call["cost_usd"],
                "response_content_sha": _sha_text(response.content),
            })
        status = "stage_complete" if not self._remaining(rows) else "partial"
        return {
            "ledger": self.ledger,
            "state": self.state.snapshot(),
            "status": status,
            "completed_ordinals": sorted(
                int(rec["ordinal"]) for rec in self.ledger.records
                if rec["stage_id"] == self.stage_id
            ),
        }

    def _remaining(self, rows: Sequence[Mapping[str, Any]]) -> bool:
        remaining = [
            row for row in rows
            if row["request_body_sha256"] not in self._called
        ]
        return bool(remaining)


def all_arm_payloads_called(
    ledger: ExecutionLedger,
    arm: str,
    rows_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> bool:
    """Return True when every locked payload of the arm is in the ledger."""
    arm_payloads = {row["request_body_sha256"] for row in rows_by_arm[arm]}
    called = ledger.called_payloads()
    return arm_payloads.issubset(called)


def publish_stage_capsule(
    *,
    arm: str,
    stage_id: str,
    output_dir: Path,
    ledger: ExecutionLedger,
    state: Mapping[str, Any],
    response_records: Sequence[Mapping[str, Any]],
    auth: Mapping[str, Any],
    fake: bool,
    arm_complete: bool,
    input_sha: str = EXPECTED_INPUT_SHA,
    lock: Mapping[str, Any] | None = None,
    report: Mapping[str, Any] | None = None,
    source_id_map: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Atomically publish the stage capsule.

    A stage capsule contains manifest/telemetry/cost/ledger; **final
    predictions** are only published when ``arm_complete`` is True (all
    locked payloads of the arm are in the ledger).  Partial runs publish
    an explicit ``partial`` manifest and never claim completion.
    """
    files: dict[str, bytes] = {}

    status = "complete" if arm_complete else "partial"
    telemetry = {
        "schema_version": "s2_12_arm_telemetry@1.1.0",
        "arm": arm,
        "stage_id": stage_id,
        "status": status,
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "cumulative": state,
        "response_records": list(response_records),
        "ledger_path": str(output_dir / "ledger.jsonl"),
        "final_predictions_published": bool(arm_complete),
        "text_or_gold_payload_committed": False,
    }
    cost = {
        "schema_version": "s2_12_arm_cost@1.1.0",
        "arm": arm,
        "stage_id": stage_id,
        "status": status,
        "cumulative_cost_usd": state["cost_usd"],
        "cumulative_input_tokens": state["input_tokens"],
        "cumulative_output_tokens": state["output_tokens"],
        "cumulative_cache_hit_tokens": state["cache_hit_tokens"],
        "cumulative_cache_miss_tokens": state["cache_miss_tokens"],
        "price_snapshot": auth["price_snapshot"],
        "billing_source": "response_usage" if not fake else "fixture_zero",
        "transport": "fake_payload_locked" if fake else "real_authorized",
    }
    files["telemetry.json"] = _json_bytes(telemetry)
    files["cost.json"] = _json_bytes(cost)
    files["ledger.jsonl"] = "".join(
        json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"
        for rec in ledger.records
    ).encode("utf-8")

    if arm_complete:
        # Final predictions only after the whole arm completed.
        records: list[dict[str, Any]] = []
        for row in response_records:
            records.append({
                "ordinal": row["ordinal"],
                "sample_id": row["sample_id"],
                "clause_id": row.get("clause_id"),
            })
        predictions = {
            "schema_version": "s2_12_final_predictions@1.0.0",
            "arm": arm,
            "record_count": len(records),
            "gold_read_by_runner": False,
            "raw_text_committed": False,
            "records": records,
        }
        files["predictions.json"] = _json_bytes(predictions)

    manifest = {
        "schema_version": "s2_12_arm_manifest@1.1.0",
        "arm": arm,
        "stage_id": stage_id,
        "status": status,          # partial | complete
        "ledger": {
            "path": str(output_dir / "ledger.jsonl"),
            "records": len(ledger.records),
            "last_hash": ledger.last_hash,
        },
        "input_binding": {"sha256": input_sha, "records": 36},
        "preflight_bindings": {
            "lock_sha256": _sha(PREFLIGHT_LOCK) if lock is None
                           else (lock.get("_sha") or _sha(PREFLIGHT_LOCK)),
            "report_sha256": _sha(PREFLIGHT_REPORT) if report is None
                             else (report.get("_sha") or _sha(PREFLIGHT_REPORT)),
        },
        "stage_contract": {
            "arm": arm,
            "stage_id": stage_id,
            "ordinals": stage_ordinals(arm, stage_id),
        },
        "gold_isolation": {
            "gold_read_by_runner": False,
            "predictions_locked_before_evaluation": True,
            "post_result_tuning_forbidden": True,
        },
        "artifacts": manifest_capsule(files),
        "safety": {
            "llm_api_calls": int(state["calls"]),
            "network_calls": int(state["calls"]) if not fake else 0,
            "cost_usd": state["cost_usd"],
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
    }
    files["manifest.json"] = _json_bytes(manifest)
    atomic_publish_directory(output_dir, files)
    return manifest
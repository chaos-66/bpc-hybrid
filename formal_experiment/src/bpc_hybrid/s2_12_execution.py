# -*- coding: utf-8 -*-
"""S2.12 complex-corpus execution wiring (zero-API contract + fake transport).

This module is the shared fail-closed contract for the two S2.12 real-API
arms (``direct_llm`` and ``sun_llm_fallback``).  It is deliberately
offline-first:

* It never reads ``.env``, never imports an HTTP client, and never opens a
  network socket.
* It rebuilds every request body with the exact preflight-builder paths
  (``build_s2_12_api_preflight_v1``) so the 63 locked request-body SHA-256
  values must match byte-for-byte before any transport call is allowed.
* Real transport requires BOTH ``--allow-llm`` AND a valid authorization
  file whose schema binds the sentence hash, event hash, model, call counts,
  63 payload hashes, retry=0, input/output/USD caps, price snapshot, and the
  target runner implementation hash.  Missing any field -> refuse before
  the first transport call.
* The default transport is a *payload-locked fake transport*: it only
  accepts request bodies whose SHA-256 matches the locked preflight list and
  returns deterministic synthetic responses (no network, no API key).
* No real authorization file is created by this repo; tests use fixtures
  explicitly marked synthetic.

This batch is ZERO API: real calls are still pending user authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

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
B0_MANIFEST = ROOT / "data/predictions/s2_12_sun_rule_only_v1/manifest.json"
B0_PREDICTIONS = ROOT / "data/predictions/s2_12_sun_rule_only_v1/predictions.json"

OUTPUT_DIRS = {
    "direct_llm": ROOT / "data/predictions/s2_12_direct_llm_v1",
    "sun_llm_fallback": ROOT / "data/predictions/s2_12_sun_llm_fallback_v1",
}

EXPECTED_INPUT_SHA = "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e"
REQUIRED_MODEL = "deepseek-v4-pro"

# Undesired keys that must never appear in committed outputs.
_FORBIDDEN_TEXT_KEYS = ("text", "source_text", "normalized", "marker_surface")
_FORBIDDEN_SECRET_KEYS = (
    "api_key", "apikey", "authorization", "access_token", "refresh_token",
    "cookie", "password", "secret", "client_secret",
)

# Beijing-time off-peak window: peak 09:00-12:00 and 14:00-18:00 (UTC+8).
_BJ_OFFSET = timedelta(hours=8)


class S212ExecutionError(ValueError):
    """Fail-closed S2.12 execution error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _strip_text_fields(value: Any) -> Any:
    """Recursively drop raw-text keys from a committed prediction record.

    Removes ``source_text`` and span ``text`` plus the matching-normalization
    metadata keys (``normalized``/``marker_surface``) so the committed capsule
    stays text-free.  Coordinates, ids and labels are kept.
    """
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
    tokenizer: Any = None,
) -> dict[str, list[dict[str, Any]]]:
    """Rebuild the 63 request bodies with preflight paths and verify every
    SHA-256 against the locked report.

    ``tokenizer`` is accepted for API symmetry with the preflight report's
    proxy-token measurement but is NOT used for the runner's SHA/byte checks
    (the locked report already fixes byte counts and hashes).

    Returns ``{"direct_llm": [...36...], "sun_llm_fallback": [...27...]}``
    where every row carries ``call_index/sample_id/clause_id/
    request_body_sha256/request_body_utf8_bytes/call`` (the rebuilt request
    body dict) and ``system_prompt/user_prompt`` for transport use.
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
    # The preflight builder iterates ``batch`` (the LoadedB0 diagnostic
    # replay list) in order; reuse the same iteration.
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
            raise S212ExecutionError(
                f"direct call {index}: locked report order/ID drift"
            )
        if expected["request_body_sha256"] != row["request_body_sha256"]:
            raise S212ExecutionError(
                f"direct call {index} ({row['sample_id']}): rebuilt payload SHA "
                f"{row['request_body_sha256'][:12]} != locked "
                f"{expected['request_body_sha256'][:12]}"
            )
        if expected["request_body_utf8_bytes"] != row["request_body_utf8_bytes"]:
            raise S212ExecutionError(
                f"direct call {index}: rebuilt body byte size drift"
            )
        direct_rows.append(row)
    if len(direct_rows) != len(locked_direct):
        raise S212ExecutionError("direct call count != 36")

    # ---- fallback arm (27 triggered clause-level repairs) ----
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
            raise S212ExecutionError(
                f"fallback call {index}: locked report order/ID drift"
            )
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


def verify_63_count(rows: Mapping[str, Sequence[Any]]) -> None:
    if len(rows["direct_llm"]) != 36 or len(rows["sun_llm_fallback"]) != 27:
        raise S212ExecutionError(
            f"payload count drift: direct={len(rows['direct_llm'])} "
            f"fallback={len(rows['sun_llm_fallback'])}"
        )


# ---------------------------------------------------------------------------
# Authorization gate
# ---------------------------------------------------------------------------

AUTHORIZATION_REQUIRED_FIELDS = (
    "schema_version",
    "authorization_sentence_utf8_sha256",
    "authorization_event_file",
    "authorization_event_file_sha256",
    "model",
    "calls",
    "payload_hashes",
    "retry",
    "input_token_cap",
    "output_token_cap",
    "usd_cost_cap",
    "allowed_windows",
    "price_snapshot",
    "price_checked_at_utc",
    "runner_implementation_hashes",
    "input_config_prompt_hashes",
    "gold_isolation",
)


def validate_authorization(
    auth: Mapping[str, Any],
    lock: Mapping[str, Any],
    report: Mapping[str, Any],
    runner_hash: str,
) -> dict[str, Any]:
    """Validate a loaded authorization file against the lock/report contract.

    Missing or mismatched fields raise :class:`S212ExecutionError` BEFORE any
    transport call.  Returns the validated auth mapping.
    """
    missing = [name for name in AUTHORIZATION_REQUIRED_FIELDS if name not in auth]
    if missing:
        raise S212ExecutionError(
            f"authorization file missing required fields: {missing}"
        )
    if auth["schema_version"] != "s2_12_api_authorization@1.0.0":
        raise S212ExecutionError("authorization schema identity drift")
    if auth["model"] != REQUIRED_MODEL:
        raise S212ExecutionError(
            f"authorization model {auth['model']!r} != {REQUIRED_MODEL!r}"
        )
    if auth["calls"] != {"direct_llm": 36, "sun_llm_fallback": 27}:
        raise S212ExecutionError("authorization call counts must be 36/27")
    if auth["retry"] != 0:
        raise S212ExecutionError("authorization retry must be 0")
    if auth["input_token_cap"] <= 0 or auth["output_token_cap"] <= 0 or auth["usd_cost_cap"] <= 0:
        raise S212ExecutionError("authorization caps must be positive")
    if auth.get("gold_isolation", {}).get("api_arms_must_not_read_gold") is not True:
        raise S212ExecutionError("authorization Gold isolation declaration invalid")

    if auth["runner_implementation_hashes"].get("run_s2_12_direct_llm_v1") != runner_hash:
        raise S212ExecutionError("authorization runner hash mismatch")

    expected_payload_hashes = {
        row["request_body_sha256"]
        for arm in ("direct_llm", "sun_llm_fallback")
        for row in report["arms"][arm]["calls"]
    }
    auth_payloads = set(auth["payload_hashes"])
    if auth_payloads != expected_payload_hashes:
        raise S212ExecutionError(
            "authorization payload hash set does not match the locked 63 bodies"
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
    runner_hash: str,
) -> dict[str, Any]:
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise S212ExecutionError(f"invalid authorization file: {exc}") from exc
    if not isinstance(auth, dict):
        raise S212ExecutionError("authorization file must be a JSON object")
    return validate_authorization(auth, lock, report, runner_hash)


# ---------------------------------------------------------------------------
# Beijing-time off-peak window (UTC+8)
# ---------------------------------------------------------------------------


def beijing_time(now_utc: datetime | None = None) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(timezone.utc) + _BJ_OFFSET


def is_beijing_peak(now_utc: datetime | None = None) -> bool:
    """Return True when the current Beijing time is inside a peak window.

    Peak windows: 09:00-12:00 and 14:00-18:00 Beijing (UTC+8); everything
    else is off-peak.
    """
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
# Payload-locked fake transport
# ---------------------------------------------------------------------------


def build_fake_direct_response_json(
    source_text: str, source_id: str, sample_id: str
) -> str:
    """Build a deterministic canonical-format fake Direct-LLM response.

    The emitted record uses empty field arrays (legal per the D1-R1 empty-is-
    absent policy) plus a minimal modality evidence span anchored to the
    first modal cue of the source text.  It passes the canonical validator
    chain (schema + cross-field) deterministically and contains no Gold.
    """
    lower = source_text.lower()
    marker = next(
        (m for m in ("shall", "must", "may", "should", "shall not", "must not")
         if m in lower),
        None,
    )
    if marker is not None:
        ev_start = source_text.lower().find(marker)
        ev_text = source_text[ev_start : ev_start + len(marker)]
        ev_end = ev_start + len(marker)
    else:
        ev_start, ev_end = 0, min(8, len(source_text))
        ev_text = source_text[ev_start:ev_end]
    payload = {
        "schema_version": "1.0.0",
        "sample_id": sample_id,
        "source_id": source_id,
        "source_text": source_text,
        "clauses": [
            {
                "clause_id": f"{sample_id}-c1",
                "clause_span": {"start": 0, "end": len(source_text), "text": source_text},
                "modality": {
                    "label": "obligation",
                    "evidence": [{"text": ev_text, "start": ev_start, "end": ev_end}],
                },
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ],
        "method": {
            "name": "direct_llm",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        "unsupported_or_ambiguous": [],
    }
    return json.dumps(payload, ensure_ascii=False)


class PayloadLockedFakeTransport(LLMTransport):
    """Deterministic fake transport that ONLY accepts locked payloads.

    * Independently rebuilds the request body from the request prompts with
      the exact locked policy/model/sampling and verifies its SHA-256
      against the locked preflight list before returning a response.
    * Never touches network, ``.env``, or API keys.
    * Returns a deterministic schema-valid response per sample for
      Direct-LLM, and a deterministic no-op patch envelope for
      Rules+LLM-Repair (fixture semantics are explicit).
    """

    def __init__(
        self,
        locked: Mapping[str, dict[str, Any]],
        arm: str,
        policy: H1RequestPolicy | None = None,
    ) -> None:
        # locked is keyed by request_body_sha256 -> locked row; this is the
        # clause-agnostic, strongest possible acceptance check.
        self._locked = dict(locked)
        self._arm = arm
        self._policy = policy

    def _rebuild_body(self, request: LLMRequest) -> bytes:
        body: dict[str, Any] = {
            "model": REQUIRED_MODEL,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "max_tokens": 4096,
            "temperature": 0.0,
            "top_p": 1.0,
        }
        if self._policy is not None:
            body = self._policy.apply_to_body(body)
        return json.dumps(body).encode("utf-8")

    def send(self, request: LLMRequest) -> LLMResponse:
        body_bytes = self._rebuild_body(request)
        body_sha = _sha_bytes(body_bytes)
        locked_row = self._locked.get(body_sha)
        if locked_row is None:
            raise LLMClientError(
                f"fake transport rejected payload not in the locked set "
                f"(sha {body_sha[:12]}); no call was made"
            )
        if self._arm == "direct_llm":
            content = build_fake_direct_response_json(
                source_text=request.source_text,
                source_id=request.source_id,
                sample_id=request.source_id,
            )
            return LLMResponse(
                content=content, provider="fake", model=REQUIRED_MODEL,
                finish_reason="stop",
            )
        return LLMResponse(
            content=json.dumps({
                "sample_id": request.source_id,
                "clause_id": "synthetic-fake-clause",
                "repair_fields": [],
                "patches": {},
                "reason": "synthetic fake transport fixture (no-op)",
            }),
            provider="fake", model=REQUIRED_MODEL, finish_reason="stop",
        )


# ---------------------------------------------------------------------------
# Atomic output publishing
# ---------------------------------------------------------------------------


def atomic_publish_directory(output_dir: Path, files: Mapping[str, bytes]) -> None:
    """Atomically publish a prediction capsule (stage dir + rename).

    Refuses to overwrite an existing run and never leaves a partially
    written capsule under the final name.
    """
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
    """Build the artifacts hash map (name -> sha256+bytes)."""
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
) -> dict[str, Any]:
    return {
        "schema_version": "s2_12_arm_cost@1.0.0",
        "llm_calls": llm_calls,
        "max_calls": max_calls,
        "input_tokens_billed": input_tokens_billed,
        "output_tokens_billed": output_tokens_billed,
        "actual_cost_usd": actual_cost_usd,
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "billing_source": "response_usage" if not fake else "fixture_zero",
    }
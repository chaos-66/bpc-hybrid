# -*- coding: utf-8 -*-
"""Real-executor chain for the GDPR Stage-2 Direct-LLM (Stage-2 arm) batch.

This runner executes the frozen 74-sentence ``direct_llm`` batch of
``outputs/reports/gdpr7_direct_llm_preflight_v1.json`` with the S2.12-style
real-execution safety contract, fully offline by default:

* the preflight builder's render path is REUSED (imported as
  ``build_gdpr7_direct_llm_preflight_v1``): registry + config + request
  policy + prompt are rebuilt exactly as the preflight did, every final
  request body is re-serialized (default ``json.dumps``, UTF-8) and its
  SHA-256 / byte size must equal the committed per-request values, otherwise
  the run refuses BEFORE the first send (fail closed);
* a per-call ``PayloadLock`` re-verifies the final body hash + sample id +
  execution order inside EVERY transport call (fake or real);
* before EVERY real send the executor enforces: an authorization event file
  (user sentence + exact scope ``gdpr7_direct_llm_v1:74`` + SHA bindings;
  absent -> hard refuse), the model pin ``deepseek-v4-pro`` (published alias
  ``DeepSeek-V4-Pro-0813``), temperature 0 / top_p 1 / max_tokens 4096 /
  retry 0 / stream false / thinking disabled / response_format None (all
  subsumed by the locked body SHA), Beijing off-peak window checks
  (off-peak-only authorizations), per-call and global caps:
  input <= 74,000,000 (proxy-equivalent conservative bound documented in the
  preflight), output <= 4,096 per call and <= 303,104 total, USD <= 2.61
  (peak) / 1.31 (off-peak), implemented in code; planning tokens are a
  planning proxy, NOT billing tokens -- official prices are re-verified and
  bound in the authorization event before a real run;
* usage capture with ``returned_model`` verification; a missing/damaged
  provider usage or non-``ok_message_content`` decode is recorded as an
  ``in_doubt`` ledger entry and NEVER auto-resent;
* append-only hash-chained ledger + raw-response JSONL under
  ``outputs/development/gdpr7_direct_llm_raw_v1/``; ``--resume`` re-sends
  ONLY never-attempted requests in the original (report) order; partial/
  aborted runs keep everything and exit non-zero without claiming complete;
* after the batch, raw responses are converted to canonical prediction rows
  with the doc-level schema ``gdpr7_direct_llm_predictions@1.0.0`` using the
  SAME canonical clause/span coordinate convention as the Rules-Only capsule
  (``data/predictions/gdpr7_sun_rule_only_v1``) -- text is never committed,
  only coordinates -- so the linkage runner's first-valid-span projection
  (``run_gdpr_s2_s3_linkage_v1`` / ``bpc_hybrid.gdpr_s2_s3_projection``) can
  consume the capsule unchanged.  Request failures are recorded as rows with
  ``request_status != "ok"`` / ``error_category``, never dropped.

CLI::

    # full 74-call fake verification (zero network, zero API)
    python scripts/run_gdpr7_direct_llm_v1.py --fake-transport

    # real run AFTER user authorization (authorization event file required)
    python scripts/run_gdpr7_direct_llm_v1.py --contract-file <path> \\
        --authorization-file <path>

    # resume a partial/aborted run (never re-sends completed or in_doubt)
    python scripts/run_gdpr7_direct_llm_v1.py --fake-transport --resume

    # resume a real run
    python scripts/run_gdpr7_direct_llm_v1.py --contract-file <path> \\
        --authorization-file <path> --resume

Zero LLM/API/network/.env unless the user has authorized a real batch: fake
mode never opens ``.env`` and never touches the network; the real transport
is created with ``LLMConfig.from_env(project_root=ROOT,
load_project_env=False)`` (only the process environment).  No Gold is read;
only coordinates and hashes are committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]          # formal_experiment/
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.d1_schema_adapter import adapt_relay_record  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402
from bpc_hybrid.llm_client import (  # noqa: E402
    LLMClientError,
    LLMRequest,
    LLMResponse,
    LLMTransport,
    OpenAICompatibleRequestBuilder,
    RealAPITransport,
)
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from run_direct_llm import _few_shot_block  # noqa: E402

# Reuse the exact preflight reconstruction paths (byte-identical bodies) and
# the frozen report/caps constants.
from build_gdpr7_direct_llm_preflight_v1 import (  # noqa: E402
    BASE_URL,
    EXPECTED_INPUT_SHA256,
    EXPECTED_PROMPT_SHA256,
    EXPECTED_REGISTRY_SHA256,
    EXPECTED_RULE_COUNT,
    EXPECTED_SENTENCE_COUNT,
    INPUT,
    MAX_OUTPUT_TOKENS_PER_CALL,
    OUTPUT,                       # committed preflight report path
    PRICE_OFF_PEAK_PER_MILLION,
    PRICE_PEAK_PER_MILLION,
    PROMPT_NAME,
    PUBLISHED_ALIAS,
    REGISTRY,
    REQUIRED_MODEL,
    SCHEMA_VERSION,               # preflight report schema version
    _config,                      # locked LLMConfig
    _policy,                      # locked H1RequestPolicy
    _verify_registry,
)

# ---------------------------------------------------------------------------
# Public schema / run identifiers
# ---------------------------------------------------------------------------

PREDICTION_SCHEMA = "gdpr7_direct_llm_predictions@1.0.0"
TELEMETRY_SCHEMA = "gdpr7_direct_llm_telemetry@1.0.0"
COST_SCHEMA = "gdpr7_direct_llm_cost@1.0.0"
MANIFEST_SCHEMA = "gdpr7_direct_llm_manifest@1.0.0"
LEDGER_SCHEMA = "gdpr7_direct_llm_ledger@1.0.0"
PRICE_SNAPSHOT_SCHEMA = "gdpr7_direct_llm_price_snapshot@1.0.0"
AUTHORIZATION_EVENT_SCHEMA = "gdpr7_direct_llm_authorization_event@1.0.0"
CONTRACT_SCHEMA = "gdpr7_direct_llm_execution_contract@1.0.0"

DATASET_ID = "gdpr7_stage2_sentences_v1"
METHOD_ID = "direct_llm"
AUTHORIZATION_SCOPE = "gdpr7_direct_llm_v1:74"

# Canonical arm capsule home referenced by the linkage runner
# (``run_gdpr_s2_s3_linkage_v1.ARM_PATHS["direct_llm"]``).  This executor only
# publishes to development paths; the formal arm capsule is promoted by a
# separate, user-authorized step.
ARM_CAPSULE_PATH = ROOT / "data/predictions/gdpr7_direct_llm_v1"

# Default development output locations (never formal capsule dirs).
DEFAULT_RAW_DIR = ROOT / "outputs/development/gdpr7_direct_llm_raw_v1"
DEFAULT_CAPSULE_DIR = ROOT / "outputs/development/gdpr7_direct_llm_v1"

# Default locked preflight report (committed path).
REPORT_DEFAULT = OUTPUT

# In-code hard caps (mirrors preflight ``recommended_hard_limits``; implemented
# here, not only documented).
MAX_CALLS = EXPECTED_SENTENCE_COUNT                        # 74
INPUT_TOKEN_CAP = EXPECTED_SENTENCE_COUNT * 1_000_000      # 74,000,000
OUTPUT_TOKENS_PER_CALL = MAX_OUTPUT_TOKENS_PER_CALL        # 4,096
OUTPUT_TOKEN_TOTAL_CAP = EXPECTED_SENTENCE_COUNT * MAX_OUTPUT_TOKENS_PER_CALL  # 303,104
USD_CAP_PEAK = 2.61     # planning-bound peak cost + 1.2x margin (preflight)
USD_CAP_OFF_PEAK = 1.31  # off-peak half-price alternative

# Official prices recorded/verified in ``docs/API_AUTHORIZATION_REQUEST.md``
# (2026-08-19/20 deepseek-v4-pro peak pricing; off-peak documented as half).
PEAK_PRICES = {
    "input_cache_hit_per_million": PRICE_PEAK_PER_MILLION["input_cache_hit"],
    "input_cache_miss_per_million": PRICE_PEAK_PER_MILLION["input_cache_miss"],
    "output_per_million": PRICE_PEAK_PER_MILLION["output"],
}
OFF_PEAK_PRICES = {
    "input_cache_hit_per_million": PRICE_OFF_PEAK_PER_MILLION["input_cache_hit"],
    "input_cache_miss_per_million": PRICE_OFF_PEAK_PER_MILLION["input_cache_miss"],
    "output_per_million": PRICE_OFF_PEAK_PER_MILLION["output"],
}

# Beijing-time peak window (UTC+8); weekends are entirely off-peak.
_BJ_OFFSET = timedelta(hours=8)

# Raw-text keys that must never appear in the committed capsule docs.
_FORBIDDEN_TEXT_KEYS = (
    "text", "source_text", "approved_text_en", "normalized", "marker_surface",
)
# Decision / Gold / evaluation keys that must never appear anywhere.
_FORBIDDEN_DECISION_KEYS = (
    "expected", "decision", "gold", "ground_truth", "oracle",
    "expected_violation", "human_correction", "adjudicat", "gold_rule",
)


class Gdpr7ExecutionError(ValueError):
    """Fail-closed GDPR Direct-LLM execution error."""


# ---------------------------------------------------------------------------
# Hashes / serialization
# ---------------------------------------------------------------------------


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _jsonl_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def _usage_int(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def _contains_keys(value: Any, keys: Sequence[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key) in keys:
                return True
            if _contains_keys(child, keys):
                return True
    elif isinstance(value, list):
        return any(_contains_keys(item, keys) for item in value)
    return False


def _strip_text_fields(value: Any) -> Any:
    """Recursively drop raw-text keys from a committed record (coordinates
    and identifiers survive; text never does)."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, child in value.items():
            if key in _FORBIDDEN_TEXT_KEYS:
                continue
            out[key] = _strip_text_fields(child)
        return out
    if isinstance(value, list):
        return [_strip_text_fields(item) for item in value]
    return value


def _is_plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ---------------------------------------------------------------------------
# Beijing-time off-peak window (UTC+8)
# ---------------------------------------------------------------------------


def beijing_time(now_utc: datetime | None = None) -> datetime:
    now_utc = now_utc or datetime.now(timezone.utc)
    return now_utc.astimezone(timezone.utc) + _BJ_OFFSET


def is_beijing_peak(now_utc: datetime | None = None) -> bool:
    bj = beijing_time(now_utc)
    if bj.weekday() >= 5:
        return False
    minutes = bj.hour * 60 + bj.minute
    return (9 * 60 <= minutes < 12 * 60) or (14 * 60 <= minutes < 18 * 60)


# ---------------------------------------------------------------------------
# Price snapshot + cumulative accounting
# ---------------------------------------------------------------------------


def price_snapshot(off_peak: bool) -> dict[str, Any]:
    prices = OFF_PEAK_PRICES if off_peak else PEAK_PRICES
    return {
        "schema_version": PRICE_SNAPSHOT_SCHEMA,
        "currency": "USD",
        "input_cache_hit_per_million": prices["input_cache_hit_per_million"],
        "input_cache_miss_per_million": prices["input_cache_miss_per_million"],
        "output_per_million": prices["output_per_million"],
    }


def per_call_cost(usage: Mapping[str, Any], price: Mapping[str, Any]) -> dict[str, Any]:
    """Compute input/output token counts and USD cost for one response.

    Cache hit/miss split: if the provider returns
    ``prompt_cache_hit_tokens``/``prompt_cache_miss_tokens`` we use them;
    otherwise ALL input tokens are billed at the conservative cache-miss
    price (the authorization contract's mandated fallback).  The USD cap
    includes the 20% (1.2x) safety margin; costs are round-tripped to
    micro-dollar precision only for reporting, never for cap checks.
    """
    prompt = _usage_int(usage, "prompt_tokens")
    completion = _usage_int(usage, "completion_tokens")
    cache_hit = _usage_int(usage, "prompt_cache_hit_tokens")
    cache_miss = _usage_int(usage, "prompt_cache_miss_tokens")
    if cache_hit + cache_miss == 0 and prompt > 0:
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


# ---------------------------------------------------------------------------
# Input / report / plan verification (fail closed before any send)
# ---------------------------------------------------------------------------


def load_report(report_path: Path) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("schema_version") != SCHEMA_VERSION:
        raise Gdpr7ExecutionError("preflight report schema identity drift")
    if report.get("status") != "payloads_locked_zero_api_authorization_pending":
        raise Gdpr7ExecutionError("preflight report status drift")
    if report["input"]["sha256"] != EXPECTED_INPUT_SHA256:
        raise Gdpr7ExecutionError("preflight report input binding drift")
    if report["input"]["records"] != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError("preflight report sentence-count drift")
    calls = report.get("arms", {}).get("direct_llm", {}).get("calls")
    if not isinstance(calls, list) or len(calls) != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError("preflight report direct_llm call rows drift")
    return report


def load_input_doc() -> dict[str, Any]:
    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    if _sha(INPUT) != EXPECTED_INPUT_SHA256:
        raise Gdpr7ExecutionError("GDPR Stage-2 input drift")
    if input_doc.get("schema_version") != "gdpr7_stage2_input@1.0.0":
        raise Gdpr7ExecutionError("GDPR Stage-2 input schema identity drift")
    if input_doc.get("gold_visible") is not False:
        raise Gdpr7ExecutionError("GDPR Stage-2 input must be Gold-blind")
    if input_doc.get("counts") != {"rules": EXPECTED_RULE_COUNT,
                                   "sentences": EXPECTED_SENTENCE_COUNT}:
        raise Gdpr7ExecutionError("GDPR Stage-2 input counts drift")
    return input_doc


def resolve_sentence_texts(input_doc: Mapping[str, Any]) -> dict[str, str]:
    """Return {sample_id: approved_text_en}; also binds each sentence's own
    SHA-256 (the exact ``_resolve_sentences`` discipline of the preflight)."""
    out: dict[str, str] = {}
    seen: set[str] = set()
    for rule in input_doc.get("rules") or []:
        rule_id = rule.get("rule_id")
        for s in rule.get("sentences") or []:
            sample_id = s.get("sample_id")
            text = s.get("approved_text_en")
            if not isinstance(sample_id, str) or sample_id in seen:
                raise Gdpr7ExecutionError("sentence sample IDs missing or duplicated")
            if not isinstance(text, str) or not text.strip():
                raise Gdpr7ExecutionError(f"empty sentence text: {sample_id}")
            if _sha_text(text) != s.get("text_sha256"):
                raise Gdpr7ExecutionError(f"sentence text hash drift: {sample_id}")
            seen.add(sample_id)
            out[sample_id] = text
    if len(out) != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError(
            f"expected {EXPECTED_SENTENCE_COUNT} sentences, got {len(out)}"
        )
    return out


def build_plan_rows(report: Mapping[str, Any],
                    sentence_texts: Mapping[str, str]) -> list[dict[str, Any]]:
    """Rebuild every locked request body with the exact preflight render path
    and verify SHA-256, byte size, order and sample ids against the report.
    Any drift raises BEFORE the first send."""
    _verify_registry()
    prompt = load_prompt(PROMPT_NAME)
    if prompt.sha256 != EXPECTED_PROMPT_SHA256:
        raise Gdpr7ExecutionError("D1 direct prompt drift")
    few_shot = _few_shot_block(prompt)
    config = _config()
    builder = OpenAICompatibleRequestBuilder(config)
    policy = _policy()

    rows: list[dict[str, Any]] = []
    for row in report["arms"]["direct_llm"]["calls"]:
        index = int(row["call_index"])
        sample_id = row["sample_id"]
        text = sentence_texts.get(sample_id)
        if text is None:
            raise Gdpr7ExecutionError(
                f"locked row {index} sample {sample_id} missing from input pack"
            )
        if _sha_text(text) != row.get("sentence_text_sha256"):
            raise Gdpr7ExecutionError(
                f"locked row {index} sentence-text hash drift"
            )
        user_prompt = prompt.user_prompt_template.format(
            sample_id=sample_id,
            source_id=sample_id,
            source_text=text,
            few_shot_block=few_shot,
        )
        body = policy.apply_to_body(
            builder.build_body(prompt.system_prompt, user_prompt)
        )
        # Exact convention of the S2.12 payload lock / preflight: default
        # json.dumps, UTF-8.
        body_bytes = json.dumps(body).encode("utf-8")
        body_sha = _sha_bytes(body_bytes)
        if body_sha != row["request_body_sha256"]:
            raise Gdpr7ExecutionError(
                f"call {index} ({sample_id}): rebuilt payload SHA "
                f"{body_sha[:12]} != locked {row['request_body_sha256'][:12]}"
            )
        if len(body_bytes) != int(row["request_body_utf8_bytes"]):
            raise Gdpr7ExecutionError(
                f"call {index} ({sample_id}): body byte size drift"
            )
        rows.append({
            "call_index": index,
            "sample_id": sample_id,
            "rule_id": row.get("rule_id"),
            "sentence_idx": row.get("sentence_idx"),
            "request_body_sha256": body_sha,
            "request_body_utf8_bytes": len(body_bytes),
            "local_proxy_tokens": int(row.get("local_proxy_tokens") or 0),
            "system_prompt": prompt.system_prompt,
            "user_prompt": user_prompt,
            "source_text": text,
            "body": body,
        })
    if len(rows) != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError("plan row count != 74")
    return rows


# ---------------------------------------------------------------------------
# Per-call payload lock (shared by fake and real transports)
# ---------------------------------------------------------------------------


class PayloadLock:
    """Per-call payload lock: rebuild the final body and verify SHA/IDs/order.

    No network call may happen unless ``verify`` returns True.  The rebuild
    uses the SAME locked policy/model/sampling, so temperature 0 / top_p 1 /
    max_tokens 4096 / stream false / thinking disabled / response_format None
    are all enforced through body equality with the locked report rows.
    """

    def __init__(
        self,
        locked_rows: Sequence[Mapping[str, Any]],
        builder: OpenAICompatibleRequestBuilder,
        policy: Any,
    ) -> None:
        self._policy = policy
        self._builder = builder
        self._rows_by_ordinal = {
            int(row["call_index"]): dict(row) for row in locked_rows
        }

    def rebuild_body_bytes(self, request: LLMRequest) -> bytes:
        base = self._builder.build_body(
            request.system_prompt, request.user_prompt
        )
        body = self._policy.apply_to_body(base)
        return json.dumps(body).encode("utf-8")

    def verify(self, request: LLMRequest, ordinal: int) -> dict[str, Any]:
        expected = self._rows_by_ordinal.get(int(ordinal))
        if expected is None:
            raise Gdpr7ExecutionError(
                f"payload lock: no locked row for ordinal {ordinal}"
            )
        body_bytes = self.rebuild_body_bytes(request)
        body_sha = _sha_bytes(body_bytes)
        if body_sha != expected["request_body_sha256"]:
            raise Gdpr7ExecutionError(
                f"payload lock: ordinal {ordinal} body SHA "
                f"{body_sha[:12]} != locked {expected['request_body_sha256'][:12]}"
            )
        if expected.get("sample_id") != request.source_id:
            raise Gdpr7ExecutionError(
                f"payload lock: ordinal {ordinal} sample mismatch "
                f"{expected.get('sample_id')!r} != {request.source_id!r}"
            )
        if len(body_bytes) != int(expected["request_body_utf8_bytes"]):
            raise Gdpr7ExecutionError(
                f"payload lock: ordinal {ordinal} body byte size drift"
            )
        if int(expected["call_index"]) != int(ordinal):
            raise Gdpr7ExecutionError(
                f"payload lock: ordinal {ordinal} order drift"
            )
        return {
            "request_body_sha256": body_sha,
            "request_body_utf8_bytes": len(body_bytes),
            "sample_id": request.source_id,
            "call_index": int(ordinal),
        }


# ---------------------------------------------------------------------------
# Deterministic fake canonical content (fixture, never a real response)
# ---------------------------------------------------------------------------

_MODALITY_MARKERS: tuple[tuple[str, str], ...] = (
    ("shall not", "prohibition"),
    ("must not", "prohibition"),
    ("may not", "prohibition"),
    ("shall", "obligation"),
    ("must", "obligation"),
    ("should", "obligation"),
    ("may", "permission"),
)


def fake_canonical_content(sample_id: str, source_text: str) -> str:
    """Deterministic schema-valid canonical-stage JSON fixture for one
    sentence (program verification only; not an experimental result).  The
    output shape mirrors the v6 D1 prompt examples so the D1 canonical
    adapter/canonicalizer/validator path is exercised identically."""
    import re as _re
    text = source_text.strip()
    length = len(text)
    best: tuple[int, str, str] | None = None
    for token, label in _MODALITY_MARKERS:
        for m in _re.finditer(rf"\b{_re.escape(token)}\b", text,
                              _re.IGNORECASE):
            found = m.start()
            if best is None or found < best[0]:
                best = (found, token, label)
            break  # first occurrence of this marker wins
    modality: dict[str, Any] = {"label": "definition", "evidence": []}
    if best is not None:
        idx, token, label = best
        modality = {
            "label": label,
            "evidence": [{
                "text": text[idx:idx + len(token)],
                "start": idx,
                "end": idx + len(token),
            }],
        }
    record = {
        "schema_version": "1.0.0",
        "sample_id": sample_id,
        "source_id": sample_id,
        "source_text": text,
        "clauses": [
            {
                "clause_id": f"{sample_id}_c01",
                "clause_span": {
                    "text": text, "start": 0, "end": length,
                },
                "modality": modality,
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
        "validation": {
            "schema_valid": True, "cross_field_valid": True, "errors": [],
        },
        "unsupported_or_ambiguous": [],
    }
    return json.dumps(record)


class PayloadLockedFakeTransport(LLMTransport):
    """Payload-locked deterministic fake transport (no network, no .env).

    Exposes a synthetic ``last_decode`` so the runner's usage/cost/ledger
    path is exercised identically to the real path.  Default usage is all
    zeros so a fake run's ``cost_usd`` is exactly 0.00 (fixture data, no
    billing).  Fault injection knobs are used ONLY by offline tests.
    """

    def __init__(
        self,
        payload_lock: PayloadLock,
        *,
        usage: Mapping[str, Any] | None = None,
        usage_provider: Callable[[int], Mapping[str, Any]] | None = None,
        model: str = REQUIRED_MODEL,
        decode_status: str = "ok_message_content",
        transport_error_at: int | None = None,
    ) -> None:
        self._lock = payload_lock
        self._usage = dict(usage) if usage is not None else {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "reasoning_tokens": 0,
        }
        self._usage_provider = usage_provider
        self._model = model
        self._decode_status = decode_status
        self._transport_error_at = transport_error_at
        self.last_decode: dict[str, Any] | None = None
        self.sent_ordinals: list[int] = []

    def send(self, request: LLMRequest, *, ordinal: int = 1) -> LLMResponse:
        try:
            self._lock.verify(request, ordinal)
        except Gdpr7ExecutionError as exc:
            raise LLMClientError(str(exc)) from exc
        self.sent_ordinals.append(int(ordinal))
        if self._transport_error_at == int(ordinal):
            raise LLMClientError(
                f"simulated transport failure at ordinal {ordinal}"
            )
        usage = (
            dict(self._usage_provider(int(ordinal)))
            if self._usage_provider is not None
            else dict(self._usage)
        )
        self.last_decode = {
            "status": self._decode_status,
            "model": self._model,
            "usage": dict(usage),
            "finish_reason": "stop",
        }
        content = fake_canonical_content(request.source_id, request.source_text)
        return LLMResponse(
            content=content,
            provider="fake",
            model=self._model,
            finish_reason="stop",
        )


class PayloadLockedRealTransport(LLMTransport):
    """Real HTTP transport with a per-call payload lock.

    Before ANY network request the final body is rebuilt with the locked
    policy/model/sampling, hashed and verified against the locked per-request
    hash, sample id, and execution order.  Only an exact match may reach
    ``RealAPITransport.send``.  The real transport is created with
    ``LLMConfig.from_env(project_root=ROOT, load_project_env=False)`` so a
    project ``.env`` is never opened.
    """

    def __init__(self, payload_lock: PayloadLock, config: Any,
                 timeout_seconds: float = 180.0) -> None:
        self._lock = payload_lock
        self._real = RealAPITransport(config, timeout_seconds=timeout_seconds)

    @property
    def last_decode(self) -> dict[str, Any] | None:
        return self._real.last_decode

    def send(self, request: LLMRequest, *, ordinal: int = 1) -> LLMResponse:
        try:
            self._lock.verify(request, ordinal)
        except Gdpr7ExecutionError as exc:
            raise LLMClientError(str(exc)) from exc
        return self._real.send(request)


# ---------------------------------------------------------------------------
# Append-only hash-chained execution ledger
# ---------------------------------------------------------------------------


def ledger_record(
    *,
    prev_hash: str,
    call_index: int,
    sample_id: str,
    rule_id: str | None,
    request_body_sha256: str,
    status: str,                       # completed | in_doubt | failed
    usage: Mapping[str, Any],
    returned_model: str | None,
    cost_usd: float | None,
    error: str | None,
    request_time_utc: str,
) -> dict[str, Any]:
    if status not in ("completed", "in_doubt", "failed"):
        raise Gdpr7ExecutionError(f"invalid ledger status {status!r}")
    record = {
        "schema_version": LEDGER_SCHEMA,
        "prev_hash": prev_hash,
        "call_index": int(call_index),
        "sample_id": sample_id,
        "rule_id": rule_id,
        "request_body_sha256": request_body_sha256,
        "status": status,
        "usage": dict(usage),
        "returned_model": returned_model,
        "cost_usd": cost_usd,
        "error": error,
        "request_time_utc": request_time_utc,
    }
    record["record_hash"] = _sha_text(json.dumps(
        {k: v for k, v in record.items() if k != "record_hash"},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ))
    return record


class ExecutionLedger:
    """Append-only, hash-chained execution ledger with resume support."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._records: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        prev = ""
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("schema_version") != LEDGER_SCHEMA:
                raise Gdpr7ExecutionError("ledger schema drift")
            if record.get("prev_hash", "") != prev:
                raise Gdpr7ExecutionError(
                    "ledger hash chain broken (tamper or corruption)"
                )
            inner = {k: v for k, v in record.items() if k != "record_hash"}
            recomputed = _sha_text(json.dumps(
                inner, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ))
            if recomputed != record.get("record_hash"):
                raise Gdpr7ExecutionError("ledger record hash mismatch")
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

    def called_payloads(self) -> set[str]:
        return {rec["request_body_sha256"] for rec in self._records}

    def append(self, record: Mapping[str, Any]) -> None:
        if record.get("schema_version") != LEDGER_SCHEMA:
            raise Gdpr7ExecutionError("ledger record schema drift")
        self._records.append(dict(record))
        self._flush()

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = "".join(
            _jsonl_line(rec) for rec in self._records
        ).encode("utf-8")
        temp = self.path.parent / f".{self.path.name}.staging-{os.getpid()}"
        temp.write_bytes(payload)
        temp.replace(self.path)


# ---------------------------------------------------------------------------
# Raw-response JSONL store (append-only)
# ---------------------------------------------------------------------------


class RawResponseStore:
    """Append-only raw response log.  Each line is flushed right after a
    transport outcome so a crash loses at most the in-flight line."""

    def __init__(self, path: Path, *, resume: bool) -> None:
        self.path = path
        if path.exists() and not resume:
            raise Gdpr7ExecutionError(
                f"refusing to overwrite existing raw store (use --resume): {path}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("a", encoding="utf-8", newline="\n")

    def append(self, entry: Mapping[str, Any]) -> None:
        self._handle.write(_jsonl_line(entry))
        self._handle.flush()

    def close(self) -> None:
        try:
            self._handle.close()
        except Exception:  # pragma: no cover - defensive
            pass


def load_raw_lines(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # tolerate an interrupted final line after a crash
            continue
    return out


# ---------------------------------------------------------------------------
# Per-call cap & time gating
# ---------------------------------------------------------------------------


def caps_for(auth: Mapping[str, Any]) -> dict[str, Any]:
    caps = auth.get("caps") or {}
    if not caps:
        raise Gdpr7ExecutionError("auth caps missing")
    return {
        "max_calls": int(caps["max_calls"]),
        "input_token_cap": int(caps["global_input_token_cap"]),
        "output_token_total_cap": int(caps["global_output_token_cap"]),
        "output_token_per_call": int(caps["max_output_tokens_per_call"]),
        "usd_cost_cap": float(caps["global_usd_cost_cap"]),
    }


def row_planning_input_bound(row: Mapping[str, Any]) -> int:
    """Per-call conservative planning upper bound documented in the preflight
    (formula applied per row): max(2 x local proxy tokens, body bytes / 1.8).
    Planning proxy only -- never a billing count."""
    return max(
        2 * int(row.get("local_proxy_tokens") or 0),
        int(math.ceil(int(row.get("request_body_utf8_bytes") or 0) / 1.8)),
    )


def check_pre_call(
    *,
    auth: Mapping[str, Any],
    row: Mapping[str, Any],
    state: CumulativeState,
    now_utc: datetime | None = None,
) -> None:
    """Fail-closed checks immediately before a transport call."""
    caps = caps_for(auth)
    # 1) Beijing-time window (checked EVERY call for off-peak-only auth)
    if auth.get("allowed_windows") == "off_peak_only" and is_beijing_peak(now_utc):
        raise Gdpr7ExecutionError(
            "off-peak-only authorization refuses to run during a Beijing peak window"
        )
    # 2) call count
    if state.calls + 1 > caps["max_calls"]:
        raise Gdpr7ExecutionError("call cap would be exceeded")
    # 3) cumulative caps already reached
    if state.input_tokens >= caps["input_token_cap"]:
        raise Gdpr7ExecutionError("global input-token cap reached")
    if state.output_tokens >= caps["output_token_total_cap"]:
        raise Gdpr7ExecutionError("global output-token cap reached")
    if state.cost_usd >= caps["usd_cost_cap"]:
        raise Gdpr7ExecutionError("global USD cap reached")
    # 4) conservative upper bound of THIS request must not exceed the caps.
    #    The input bound is the per-row planning proxy bound (planning tokens
    #    are a proxy, NOT billing tokens; the authoritative post-response
    #    check uses real provider usage).
    bound_in = row_planning_input_bound(row)
    bound_out = caps["output_token_per_call"]
    price = auth["price_snapshot"]
    bound_cost = per_call_cost(
        {"prompt_tokens": bound_in, "completion_tokens": bound_out}, price
    )["cost_usd"]
    if state.input_tokens + bound_in > caps["input_token_cap"]:
        raise Gdpr7ExecutionError(
            "conservative input upper bound would exceed the global input cap"
        )
    if state.output_tokens + bound_out > caps["output_token_total_cap"]:
        raise Gdpr7ExecutionError(
            "conservative output upper bound would exceed the global output cap"
        )
    if state.cost_usd + bound_cost > caps["usd_cost_cap"]:
        raise Gdpr7ExecutionError(
            "conservative USD upper bound would exceed the global USD cap "
            "(refused before this send)"
        )


def check_post_call(*, auth: Mapping[str, Any], state: CumulativeState) -> None:
    caps = caps_for(auth)
    if state.input_tokens > caps["input_token_cap"]:
        raise Gdpr7ExecutionError("input-token cap exceeded after response")
    if state.output_tokens > caps["output_token_total_cap"]:
        raise Gdpr7ExecutionError("output-token cap exceeded after response")
    if state.cost_usd > caps["usd_cost_cap"]:
        raise Gdpr7ExecutionError("USD cap exceeded after response")


# ---------------------------------------------------------------------------
# Authorization event + execution contract validation (real runs only)
# ---------------------------------------------------------------------------


def _current_bindings(report_path: Path) -> dict[str, str]:
    prompt_path = ROOT / "prompts" / "sun_compat" / f"{PROMPT_NAME}.md"
    return {
        "data/input/gdpr7_stage2_input_v1.json": _sha(INPUT),
        "outputs/reports/gdpr7_direct_llm_preflight_v1.json": _sha(report_path),
        "configs/models/estg150_d1_active_registry_v1.json": _sha(REGISTRY),
        "scripts/run_gdpr7_direct_llm_v1.py": _sha(Path(__file__).resolve()),
        "prompts/sun_compat/direct_llm_sun_record_prompt_v6_d1r1_2026_08_05.md": _sha(prompt_path),
    }


def validate_contract(contract_path: Path, report_path: Path) -> dict[str, Any]:
    if not contract_path.is_file():
        raise Gdpr7ExecutionError(
            f"--contract-file is required for a real run; not found: {contract_path}"
        )
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Gdpr7ExecutionError(f"invalid execution contract: {exc}") from exc
    if not isinstance(contract, dict):
        raise Gdpr7ExecutionError("execution contract must be a JSON object")
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise Gdpr7ExecutionError("execution contract schema identity drift")
    if contract.get("status") != "payloads_locked_real_execution_refuses_until_authorization":
        raise Gdpr7ExecutionError("execution contract status drift")
    if contract.get("authorization") is not None:
        raise Gdpr7ExecutionError(
            "execution contract must carry authorization: null"
        )
    if contract.get("authorization_scope") != AUTHORIZATION_SCOPE:
        raise Gdpr7ExecutionError("execution contract authorization scope drift")
    if contract.get("planned_calls") != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError("execution contract planned-call drift")
    if contract.get("model") != REQUIRED_MODEL:
        raise Gdpr7ExecutionError(f"contract model {contract.get('model')!r} != {REQUIRED_MODEL!r}")

    # Binding hash set must match the current disk state (fail closed).
    current = _current_bindings(report_path)
    contract_hashes = contract.get("hash_set") or {}
    if contract_hashes.get("executor_script_sha256") != current[
            "scripts/run_gdpr7_direct_llm_v1.py"]:
        raise Gdpr7ExecutionError(
            "executor script hash mismatch against execution contract"
        )
    if contract_hashes.get("input_sha256") != EXPECTED_INPUT_SHA256:
        raise Gdpr7ExecutionError("contract input hash mismatch")
    if contract_hashes.get("preflight_report_sha256") != _sha(report_path):
        raise Gdpr7ExecutionError("contract preflight-report hash mismatch")
    if contract_hashes.get("registry_sha256") != EXPECTED_REGISTRY_SHA256:
        raise Gdpr7ExecutionError("contract registry hash mismatch")
    if contract_hashes.get("prompt_sha256") != EXPECTED_PROMPT_SHA256:
        raise Gdpr7ExecutionError("contract prompt hash mismatch")
    return dict(contract)


_AUTH_EVENT_REQUIRED_FIELDS = (
    "schema_version",
    "scope",
    "authorization_sentence",
    "authorization_sentence_utf8_sha256",
    "model",
    "published_alias",
    "calls",
    "retry",
    "allowed_windows",
    "price_snapshot",
    "official_price_reverified_at_utc",
    "caps",
    "hash_set",
    "gold_isolation",
    "statement",
)


def validate_authorization_event(event_path: Path | None,
                                 contract_path: Path,
                                 report_path: Path) -> dict[str, Any]:
    """Validate the user's authorization event file BEFORE any send.

    The event must carry the user's authorization sentence, the exact scope
    ``gdpr7_direct_llm_v1:74``, the price snapshot with a re-verification
    timestamp, the same hash bindings as the execution contract, and the
    hard caps.  Any missing/mismatched field -> hard refuse.
    """
    if event_path is None or not event_path.is_file():
        raise Gdpr7ExecutionError(
            "authorization event file missing: real execution refuses until an "
            f"authorization event file with scope {AUTHORIZATION_SCOPE!r} exists "
            "and is validated"
        )
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Gdpr7ExecutionError(f"invalid authorization event file: {exc}") from exc
    if not isinstance(event, dict):
        raise Gdpr7ExecutionError("authorization event must be a JSON object")
    missing = [name for name in _AUTH_EVENT_REQUIRED_FIELDS if name not in event]
    if missing:
        raise Gdpr7ExecutionError(
            f"authorization event missing required fields: {missing}"
        )
    if event["schema_version"] != AUTHORIZATION_EVENT_SCHEMA:
        raise Gdpr7ExecutionError("authorization event schema identity drift")
    if event["scope"] != AUTHORIZATION_SCOPE:
        raise Gdpr7ExecutionError(
            f"authorization event scope {event['scope']!r} != {AUTHORIZATION_SCOPE!r}"
        )
    sentence = event["authorization_sentence"]
    if not isinstance(sentence, str) or not sentence.strip():
        raise Gdpr7ExecutionError("authorization sentence empty")
    if _sha_text(sentence) != event["authorization_sentence_utf8_sha256"]:
        raise Gdpr7ExecutionError("authorization sentence hash drift")
    if event["model"] != REQUIRED_MODEL or event["published_alias"] != PUBLISHED_ALIAS:
        raise Gdpr7ExecutionError("authorization model/alias mismatch")
    if event["retry"] != 0:
        raise Gdpr7ExecutionError("authorization retry must be 0")
    if event["calls"] != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError("authorization calls must be 74")
    if event["allowed_windows"] != "off_peak_only":
        raise Gdpr7ExecutionError(
            "GDPR direct-LLM batch is off-peak-only; event must declare "
            "allowed_windows=off_peak_only"
        )

    # Price snapshot: exact official numbers (off-peak-only run); the
    # re-verification timestamp must be present.
    snapshot = event["price_snapshot"]
    if not isinstance(snapshot, Mapping) or snapshot.get("schema_version") != PRICE_SNAPSHOT_SCHEMA:
        raise Gdpr7ExecutionError("authorization price snapshot schema drift")
    expected_snapshot = price_snapshot(off_peak=True)   # off-peak-only run
    for key in ("input_cache_hit_per_million", "input_cache_miss_per_million",
                "output_per_million"):
        if float(snapshot[key]) != float(expected_snapshot[key]):
            raise Gdpr7ExecutionError(
                f"authorization price snapshot {key} != officially recorded value"
            )
    reverified = event.get("official_price_reverified_at_utc")
    if not isinstance(reverified, str) or not reverified:
        raise Gdpr7ExecutionError(
            "official prices must be re-verified and timestamped in the event"
        )

    caps = event.get("caps") or {}
    if caps.get("global_input_token_cap") != INPUT_TOKEN_CAP:
        raise Gdpr7ExecutionError("authorization input cap mismatch")
    if caps.get("global_output_token_cap") != OUTPUT_TOKEN_TOTAL_CAP:
        raise Gdpr7ExecutionError("authorization output cap mismatch")
    if caps.get("max_output_tokens_per_call") != OUTPUT_TOKENS_PER_CALL:
        raise Gdpr7ExecutionError("authorization per-call output cap mismatch")
    if float(caps.get("global_usd_cost_cap")) != float(USD_CAP_OFF_PEAK):
        raise Gdpr7ExecutionError("authorization USD cap mismatch")

    # Hash bindings of the event must equal the current disk state AND bind
    # the exact execution contract file the executor was given.
    current = _current_bindings(report_path)
    event_hashes = event.get("hash_set") or {}
    for key, value in current.items():
        if event_hashes.get(key) != value:
            raise Gdpr7ExecutionError(
                f"authorization event binding mismatch for {key}"
            )
    declared_contract = event_hashes.get("contract_sha256")
    if not isinstance(declared_contract, str) or len(declared_contract) != 64:
        raise Gdpr7ExecutionError(
            "authorization event must bind contract_sha256"
        )
    if declared_contract != _sha(contract_path):
        raise Gdpr7ExecutionError(
            "authorization event contract binding mismatch"
        )
    gi = event.get("gold_isolation") or {}
    if gi.get("api_arms_must_not_read_gold") is not True:
        raise Gdpr7ExecutionError("authorization Gold isolation declaration invalid")
    return dict(event)


# ---------------------------------------------------------------------------
# Canonical conversion of raw responses into doc-level prediction rows
# ---------------------------------------------------------------------------

_FORBIDDEN_CONTENT_TERMS = ("expected_violation", "variant_id", "check_type")


def convert_content_to_attempt(sample_id: str, content: str,
                               source_text: str) -> dict[str, Any]:
    """Convert one raw model JSON response into the canonical attempt
    envelope consumed by the linkage projection (mirror of the
    ``run_direct_llm`` D1 canonical path: adapt -> canonicalize -> validate).

    Returns ``{sample_id, request_status, record, error_category}`` where
    ``record`` is the coordinate-only canonical record (raw text removed).
    """
    raw = content.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1]) if len(lines) > 1 else raw
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "sample_id": sample_id,
            "request_status": "failed_parse",
            "record": None,
            "error_category": f"non_json_content:{exc}",
        }
    if not isinstance(payload, dict):
        return {
            "sample_id": sample_id,
            "request_status": "failed_parse",
            "record": None,
            "error_category": "payload_not_object",
        }
    blob = json.dumps(payload).lower()
    for term in _FORBIDDEN_CONTENT_TERMS:
        if term in blob:
            return {
                "sample_id": sample_id,
                "request_status": "failed_parse",
                "record": None,
                "error_category": f"forbidden_content_term:{term}",
            }
    # Mirror run_direct_llm defaults (D1 canonical record contract).
    payload.setdefault("source_id", sample_id)
    payload.setdefault("sample_id", sample_id)
    payload.setdefault("source_text", source_text)
    payload.setdefault("schema_version", "1.0.0")
    payload.setdefault("method", {
        "name": "direct_llm",
        "schema_source": "stage2_prediction.schema.json@1.0.0",
    })
    payload.setdefault("unsupported_or_ambiguous", [])

    adapted, adapt_audit = adapt_relay_record(payload, source_text)
    if adapt_audit["status"] == "failed":
        return {
            "sample_id": sample_id,
            "request_status": "ok",
            "record": _sanitize_record(adapted) if isinstance(adapted, dict) else None,
            "error_category": "relay_schema_adaptation_failed",
        }
    canonical, span_audit = canonicalize_record_coordinates(adapted, source_text)
    if span_audit["status"] == "failed":
        return {
            "sample_id": sample_id,
            "request_status": "ok",
            "record": _sanitize_record(canonical) if isinstance(canonical, dict) else None,
            "error_category": "span_canonicalization_failed",
        }
    report = validate_canonical(canonical)
    if not (report.schema_valid and report.cross_field_valid):
        return {
            "sample_id": sample_id,
            "request_status": "ok",
            "record": _sanitize_record(canonical),
            "error_category": "canonical_validation_failed",
        }
    return {
        "sample_id": sample_id,
        "request_status": "ok",
        "record": _sanitize_record(canonical),
        "error_category": None,
    }


def _sanitize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Coordinate-only canonical record for the capsule (mirrors the
    Rules-Only capsule's clause/span coordinate convention: clause_span
    {start,end}, modality {label,evidence:[{start,end}]}, field spans
    {start,end,id}).  Raw text keys are removed recursively."""
    clean = _strip_text_fields(record)
    # Keep only the documented record keys of the Rules-Only capsule.
    kept = {
        "schema_version": clean.get("schema_version"),
        "sample_id": clean.get("sample_id"),
        "source_id": clean.get("source_id"),
        "clauses": clean.get("clauses") or [],
        "method": clean.get("method"),
        "validation": clean.get("validation"),
    }
    return kept


def failed_attempt_row(sample_id: str, request_status: str,
                       error_category: str) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "request_status": request_status,
        "record": None,
        "error_category": error_category,
    }


# ---------------------------------------------------------------------------
# Capsule publishing
# ---------------------------------------------------------------------------


def atomic_publish_directory(output_dir: Path, files: Mapping[str, bytes]) -> None:
    if output_dir.exists():
        raise Gdpr7ExecutionError(f"refusing to overwrite existing run: {output_dir}")
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


def build_manifest_capsule(files: Mapping[str, bytes]) -> dict[str, Any]:
    return {
        name: {"sha256": _sha_bytes(data), "byte_size": len(data)}
        for name, data in files.items()
    }


# ---------------------------------------------------------------------------
# Batch execution
# ---------------------------------------------------------------------------


def synthetic_auth_for_fake(report: Mapping[str, Any]) -> dict[str, Any]:
    """Dry-run-only auth shape for the fake transport (no authorization
    event is created; caps come from the preflight's recommended hard
    limits; cost stays 0 because fake usage is zero)."""
    limits = report["authorization"]["recommended_hard_limits"]
    return {
        "schema_version": AUTHORIZATION_EVENT_SCHEMA,
        "scope": AUTHORIZATION_SCOPE,
        "authorization_sentence": "synthetic-fake-no-authorization",
        "authorization_sentence_utf8_sha256": "synthetic-fake",
        "model": REQUIRED_MODEL,
        "published_alias": PUBLISHED_ALIAS,
        "calls": EXPECTED_SENTENCE_COUNT,
        "retry": 0,
        "allowed_windows": "any_time",
        "price_snapshot": price_snapshot(off_peak=False),
        "official_price_reverified_at_utc": "synthetic-fake",
        "caps": {
            "max_calls": MAX_CALLS,
            "global_input_token_cap": INPUT_TOKEN_CAP,
            "global_output_token_cap": OUTPUT_TOKEN_TOTAL_CAP,
            "max_output_tokens_per_call": OUTPUT_TOKENS_PER_CALL,
            "global_usd_cost_cap": USD_CAP_PEAK,
        },
        "hash_set": {},
        "gold_isolation": {
            "api_arms_must_not_read_gold": True,
            "evaluation_only_after_predictions_are_locked": True,
        },
        "statement": "synthetic fake verification auth shape; no user authorization",
    }


def build_capsule_docs(
    *,
    plan_rows: Sequence[Mapping[str, Any]],
    ledger: ExecutionLedger,
    state: Mapping[str, Any],
    raw_lines: Sequence[Mapping[str, Any]],
    fake: bool,
    auth: Mapping[str, Any],
    price: Mapping[str, Any],
    runtime_seconds: float,
    output_dir: Path,
    raw_dir: Path,
    arm_capsule_rel: str,
    report_rel: str,
    report_sha: str,
    reproduce_fake: str,
    reproduce_real: str,
    reproduce_resume_fake: str,
    reproduce_resume_real: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build predictions/telemetry/cost docs and the manifest (no writes)."""
    by_payload: dict[str, Mapping[str, Any]] = {
        row["request_body_sha256"]: row for row in plan_rows
    }
    raw_by_call: dict[int, Mapping[str, Any]] = {}
    for line in raw_lines:
        ci = line.get("call_index")
        if isinstance(ci, int):
            raw_by_call[ci] = line

    predictions: list[dict[str, Any]] = []
    for rec in ledger.records:
        ci = int(rec["call_index"])
        row = by_payload.get(rec["request_body_sha256"])
        sample_id = row["sample_id"] if row else rec["sample_id"]
        status = rec["status"]
        if status == "completed":
            raw_entry = raw_by_call.get(ci)
            content = (raw_entry or {}).get("content")
            if isinstance(content, str) and content.strip():
                source_text = row["source_text"] if row else ""
                predictions.append(convert_content_to_attempt(
                    sample_id, content, source_text
                ))
            else:
                predictions.append(failed_attempt_row(
                    sample_id, "in_doubt", "completed_without_content"
                ))
        elif status == "in_doubt":
            predictions.append(failed_attempt_row(
                sample_id, "in_doubt",
                rec.get("error") or "decode_or_usage_missing",
            ))
        elif status == "failed":
            predictions.append(failed_attempt_row(
                sample_id, "failed",
                rec.get("error") or "transport_failed",
            ))
        else:  # pragma: no cover - guarded at append time
            raise Gdpr7ExecutionError(f"unexpected ledger status {status!r}")
    # Rows must cover every locked sentence in call order (never dropped).
    by_sample: dict[str, dict[str, Any]] = {}
    for p in predictions:
        by_sample[p["sample_id"]] = p
    ordered: list[dict[str, Any]] = []
    for row in plan_rows:
        attempt = by_sample.get(row["sample_id"])
        if attempt is None:
            raise Gdpr7ExecutionError(
                f"missing prediction row for {row['sample_id']}"
            )
        ordered.append(attempt)
    if len(ordered) != EXPECTED_SENTENCE_COUNT:
        raise Gdpr7ExecutionError(
            f"prediction row count {len(ordered)} != {EXPECTED_SENTENCE_COUNT}"
        )

    completed = sum(1 for r in ledger.records if r["status"] == "completed")
    in_doubt = sum(1 for r in ledger.records if r["status"] == "in_doubt")
    failed = sum(1 for r in ledger.records if r["status"] == "failed")
    ok_rows = sum(1 for p in ordered if p.get("request_status") == "ok"
                  and not p.get("error_category"))

    prediction_doc = {
        "schema_version": PREDICTION_SCHEMA,
        "dataset_id": DATASET_ID,
        "method_id": METHOD_ID,
        "record_count": EXPECTED_SENTENCE_COUNT,
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        # Records are self-keyed by sample_id (one canonical attempt envelope
        # per locked sentence, in report call order) so the linkage runner's
        # sample-id projection can consume them unchanged.
        "records": ordered,
    }
    all_attempted = len(ledger.records) == EXPECTED_SENTENCE_COUNT
    status = "complete" if (all_attempted and not in_doubt and not failed) else (
        "complete_with_explicit_failures" if all_attempted else "partial"
    )
    telemetry = {
        "schema_version": TELEMETRY_SCHEMA,
        "status": status,
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "records_attempted": len(ledger.records),
        "records_expected": EXPECTED_SENTENCE_COUNT,
        "completed_calls": completed,
        "in_doubt_calls": in_doubt,
        "failed_calls": failed,
        "ok_prediction_rows": ok_rows,
        "cumulative": dict(state),
        "ledger_path": str(raw_dir / "ledger.jsonl"),
        "raw_responses_path": str(raw_dir / "raw_responses.jsonl"),
        "text_or_gold_payload_committed": False,
        "fake_run_program_verification_only": fake,
    }
    cost_doc = {
        "schema_version": COST_SCHEMA,
        "status": status,
        "llm_calls": int(state.get("calls", 0)),
        "network_calls": 0 if fake else int(state.get("calls", 0)),
        "input_tokens_billed": int(state.get("input_tokens", 0)),
        "output_tokens_billed": int(state.get("output_tokens", 0)),
        "actual_cost_usd": round(float(state.get("cost_usd", 0.0)), 8),
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "billing_source": "fixture_zero_no_billing" if fake else "response_usage",
        "price_snapshot": dict(price),
        "caps": dict(auth.get("caps") or {}),
        "planning_tokens_are_proxy_not_billing": True,
    }
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": "gdpr7_direct_llm_v1",
        "arm": METHOD_ID,
        "status": status,
        "dataset_id": DATASET_ID,
        "arm_capsule": {
            "path": arm_capsule_rel,
            "schema": PREDICTION_SCHEMA,
            "note": (
                "the canonical arm capsule home referenced by the linkage "
                "runner; this run publishes the development capsule only -- "
                "promotion to the arm capsule is a separate explicit step"
            ),
        },
        "schema": PREDICTION_SCHEMA,
        "input_binding": {
            "path": "data/input/gdpr7_stage2_input_v1.json",
            "sha256": EXPECTED_INPUT_SHA256,
            "records": EXPECTED_SENTENCE_COUNT,
        },
        "preflight_binding": {
            "path": report_rel,
            "sha256": report_sha,
        },
        "model": {
            "id": REQUIRED_MODEL,
            "published_alias": PUBLISHED_ALIAS,
            "prompt_name": PROMPT_NAME,
            "prompt_sha256": EXPECTED_PROMPT_SHA256,
            "registry_sha256": EXPECTED_REGISTRY_SHA256,
        },
        "caps": dict(auth.get("caps") or {}),
        "pricing": dict(price),
        "per_call_status_counts": {
            "completed": completed,
            "in_doubt": in_doubt,
            "failed": failed,
        },
        "cost_usd": round(float(state.get("cost_usd", 0.0)), 8),
        "runtime_seconds": round(runtime_seconds, 3),
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "authorization": {
            "required_event_scope": AUTHORIZATION_SCOPE,
            "real_authorized": not fake,
        },
        "gold_isolation": {
            "gold_read_by_runner": False,
            "predictions_locked_before_evaluation": True,
            "post_result_tuning_forbidden": True,
        },
        "outputs": {
            "raw_dir": _rel(raw_dir),
            "capsule_dir": _rel(output_dir),
        },
        "safety": {
            "llm_api_calls": int(state.get("calls", 0)) if not fake else 0,
            "network_calls": 0 if fake else int(state.get("calls", 0)),
            "cost_usd": round(float(state.get("cost_usd", 0.0)), 8),
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command_fake_verify": reproduce_fake,
        "reproduce_command_real": reproduce_real,
        "resume_command_fake": reproduce_resume_fake,
        "resume_command_real": reproduce_resume_real,
    }
    return prediction_doc, telemetry, cost_doc, manifest


def execute_batch(
    *,
    raw_dir: Path,
    capsule_dir: Path,
    fake: bool,
    report_file: Path | None = None,
    contract_file: Path | None = None,
    authorization_file: Path | None = None,
    resume: bool = False,
    transport: LLMTransport | None = None,
    usage_provider: Callable[[int], Mapping[str, Any]] | None = None,
    fake_model: str = REQUIRED_MODEL,
    fake_decode_status: str = "ok_message_content",
    fake_transport_error_at: int | None = None,
    fake_usage: Mapping[str, Any] | None = None,
    now_provider: Any = None,
    timeout_seconds: float = 180.0,
) -> dict[str, Any]:
    """Run (or resume) the GDPR Direct-LLM batch and return a rich summary.

    Raises :class:`Gdpr7ExecutionError` on any refusal/abort; on such an
    abort nothing is published (raw + ledger stay durable for --resume).
    """
    started = time.perf_counter()
    now_provider = now_provider or datetime.now
    report_path = Path(report_file) if report_file is not None else REPORT_DEFAULT
    report_path = Path(report_path)
    report = load_report(report_path)
    report["_sha256"] = _sha(report_path)

    # Fail-closed input and plan verification happens BEFORE any send.
    input_doc = load_input_doc()
    sentence_texts = resolve_sentence_texts(input_doc)
    plan_rows = build_plan_rows(report, sentence_texts)

    raw_dir = Path(raw_dir).resolve()
    capsule_dir = Path(capsule_dir).resolve()
    fake = bool(fake)
    auth: dict[str, Any]
    if fake:
        auth = synthetic_auth_for_fake(report)
    else:
        if contract_file is None:
            raise Gdpr7ExecutionError(
                "--contract-file is required for a real run; refusing to run"
            )
        contract_path = Path(contract_file)
        contract = validate_contract(contract_path, report_path)
        event = validate_authorization_event(
            Path(authorization_file) if authorization_file else None,
            contract_path, report_path,
        )
        auth = dict(event)
        auth["caps"] = {
            "max_calls": MAX_CALLS,
            "global_input_token_cap": INPUT_TOKEN_CAP,
            "global_output_token_cap": OUTPUT_TOKEN_TOTAL_CAP,
            "max_output_tokens_per_call": OUTPUT_TOKENS_PER_CALL,
            "global_usd_cost_cap": USD_CAP_OFF_PEAK,
        }

    # Capsule dir must never be overwritten; this executor never publishes to
    # a formal arm capsule path under data/predictions.
    if capsule_dir.exists():
        raise Gdpr7ExecutionError(
            f"refusing to overwrite existing capsule: {capsule_dir}"
        )
    try:
        capsule_dir.resolve().relative_to(
            (ROOT / "data/predictions").resolve()
        )
        raise Gdpr7ExecutionError(
            "this executor publishes development capsules only; refusing the "
            f"formal arm capsule path {capsule_dir}"
        )
    except ValueError:
        pass  # not under data/predictions -> OK

    # Build the payload lock + transport (transport only after auth checks).
    config = _config()
    builder = OpenAICompatibleRequestBuilder(config)
    policy = _policy()
    payload_lock = PayloadLock(plan_rows, builder, policy)

    real_transport = None
    if fake:
        if transport is not None:
            active_transport = transport
        else:
            active_transport = PayloadLockedFakeTransport(
                payload_lock,
                usage=fake_usage,
                usage_provider=usage_provider,
                model=fake_model,
                decode_status=fake_decode_status,
                transport_error_at=fake_transport_error_at,
            )
    else:
        if transport is not None:
            raise Gdpr7ExecutionError(
                "a caller-supplied transport is only allowed on the fake path"
            )
        # Real transport: only process environment (never project .env).
        real_config = LLMConfig.from_env(project_root=ROOT, load_project_env=False)
        if real_config.provider == "mock" or not real_config.enabled:
            raise Gdpr7ExecutionError(
                "real provider is not enabled (process environment only; a "
                "project .env is never read)"
            )
        if real_config.model != REQUIRED_MODEL:
            raise Gdpr7ExecutionError(
                f"resolved model {real_config.model!r} != {REQUIRED_MODEL!r}"
            )
        if not real_config.api_key or real_config.base_url != BASE_URL:
            raise Gdpr7ExecutionError(
                "real provider base_url/api_key must match the locked endpoint"
            )
        real_transport = PayloadLockedRealTransport(
            payload_lock, real_config, timeout_seconds=timeout_seconds,
        )
        active_transport = real_transport

    # Ledger + raw store (resume semantics).
    ledger_path = raw_dir / "ledger.jsonl"
    if resume:
        if not ledger_path.is_file():
            raise Gdpr7ExecutionError(
                f"--resume requires an existing ledger: {ledger_path}"
            )
    elif ledger_path.exists():
        raise Gdpr7ExecutionError(
            f"existing ledger without --resume: {ledger_path} "
            "(refusing to overwrite; pass --resume or use a fresh raw dir)"
        )
    ledger = ExecutionLedger(ledger_path)
    raw_store = RawResponseStore(raw_dir / "raw_responses.jsonl", resume=resume)

    # Rebuild cumulative state from the ledger (resume support).
    state = CumulativeState()
    price = dict(auth["price_snapshot"])
    for rec in ledger.records:
        if rec["status"] == "completed":
            state.add_usage(rec.get("usage") or {}, price)

    plan_by_sha = {row["request_body_sha256"]: row for row in plan_rows}
    called = ledger.called_payloads()
    response_lines: list[dict[str, Any]] = []
    aborted = False
    abort_reason: str | None = None
    try:
        for row in plan_rows:                       # original (report) order
            ordinal = int(row["call_index"])
            payload_sha = row["request_body_sha256"]
            if payload_sha in called:
                continue                             # resume: never re-call
            request = LLMRequest(
                source_id=row["sample_id"],
                source_text=row["source_text"],
                system_prompt=row["system_prompt"],
                user_prompt=row["user_prompt"],
            )
            check_pre_call(auth=auth, row=row, state=state,
                           now_utc=now_provider())
            try:
                response = active_transport.send(request, ordinal=ordinal)
            except LLMClientError as exc:
                raw_store.append({
                    "call_index": ordinal,
                    "sample_id": row["sample_id"],
                    "request_body_sha256": payload_sha,
                    "outcome": "transport_error",
                    "error": str(exc),
                })
                ledger.append(ledger_record(
                    prev_hash=ledger.last_hash,
                    call_index=ordinal,
                    sample_id=row["sample_id"],
                    rule_id=row.get("rule_id"),
                    request_body_sha256=payload_sha,
                    status="failed",
                    usage={},
                    returned_model=None,
                    cost_usd=None,
                    error=f"transport:{exc}",
                    request_time_utc=datetime.now(timezone.utc).isoformat(),
                ))
                called.add(payload_sha)
                raise Gdpr7ExecutionError(
                    f"transport failure on {row['sample_id']} (ordinal "
                    f"{ordinal}); recorded as failed, batch aborted: {exc}"
                ) from exc
            returned = getattr(response, "model", None)
            returned_model = str(returned) if returned else None
            if returned and str(returned) != REQUIRED_MODEL:
                raise Gdpr7ExecutionError(
                    f"returned model {returned!r} != {REQUIRED_MODEL!r} "
                    f"(ordinal {ordinal}); batch aborted"
                )
            decode = getattr(active_transport, "last_decode", None) or {}
            decode_status = str(decode.get("status") or "n/a")
            usage = dict(decode.get("usage") or {})
            content = getattr(response, "content", "") or ""
            ok_message = decode_status == "ok_message_content" and bool(content)
            raw_store.append({
                "call_index": ordinal,
                "sample_id": row["sample_id"],
                "rule_id": row.get("rule_id"),
                "request_body_sha256": payload_sha,
                "outcome": "response",
                "decode_status": decode_status,
                "returned_model": returned_model,
                "usage": dict(usage),
                "content": content,
                "content_sha256": _sha_text(content) if content else None,
            })
            if not ok_message or not usage:
                reason = (
                    "usage_missing" if not usage
                    else f"decode_status:{decode_status}"
                )
                ledger.append(ledger_record(
                    prev_hash=ledger.last_hash,
                    call_index=ordinal,
                    sample_id=row["sample_id"],
                    rule_id=row.get("rule_id"),
                    request_body_sha256=payload_sha,
                    status="in_doubt",
                    usage=dict(usage),
                    returned_model=returned_model,
                    cost_usd=None,
                    error=reason,
                    request_time_utc=datetime.now(timezone.utc).isoformat(),
                ))
                called.add(payload_sha)
                raise Gdpr7ExecutionError(
                    f"ordinal {ordinal} ({row['sample_id']}) has {reason}; "
                    "recorded as in_doubt (never auto-resent); batch aborted"
                )
            per_call = state.add_usage(usage, price)
            ledger.append(ledger_record(
                prev_hash=ledger.last_hash,
                call_index=ordinal,
                sample_id=row["sample_id"],
                rule_id=row.get("rule_id"),
                request_body_sha256=payload_sha,
                status="completed",
                usage=dict(usage),
                returned_model=returned_model,
                cost_usd=per_call["cost_usd"],
                error=None,
                request_time_utc=datetime.now(timezone.utc).isoformat(),
            ))
            called.add(payload_sha)
            response_lines.append({
                "call_index": ordinal,
                "sample_id": row["sample_id"],
                "request_body_sha256": payload_sha,
                "returned_model": returned_model,
                "usage": dict(usage),
                "cost_usd": per_call["cost_usd"],
                "content_sha256": _sha_text(content),
            })
            check_post_call(auth=auth, state=state)
    except Gdpr7ExecutionError:
        raw_store.close()
        raise
    finally:
        raw_store.close()

    all_attempted = len(ledger.records) == EXPECTED_SENTENCE_COUNT
    if not all_attempted:
        raise Gdpr7ExecutionError(
            "batch did not attempt all 74 locked requests; partial ledger and "
            "raw responses are retained (use --resume); nothing published"
        )

    # ---- canonical conversion + publish ----------------------------------
    raw_lines = load_raw_lines(raw_dir / "raw_responses.jsonl")
    elapsed = time.perf_counter() - started
    doc_arm_capsule_rel = str(ARM_CAPSULE_PATH.relative_to(ROOT)).replace(os.sep, "/")
    reproduce_fake = (
        "python formal_experiment/scripts/run_gdpr7_direct_llm_v1.py "
        "--fake-transport"
    )
    reproduce_real = (
        "python formal_experiment/scripts/run_gdpr7_direct_llm_v1.py "
        "--contract-file formal_experiment/configs/ablations/"
        "gdpr7_direct_llm_execution_contract_v1.json "
        "--authorization-file <gdpr7-direct-llm-authorization-event-file>"
    )
    resume_fake = reproduce_fake + " --resume"
    resume_real = reproduce_real + " --resume"

    prediction_doc, telemetry, cost_doc, manifest = build_capsule_docs(
        plan_rows=plan_rows,
        ledger=ledger,
        state=state.snapshot(),
        raw_lines=raw_lines,
        fake=fake,
        auth=auth,
        price=price,
        runtime_seconds=elapsed,
        output_dir=capsule_dir,
        raw_dir=raw_dir,
        arm_capsule_rel=doc_arm_capsule_rel,
        report_rel=_rel(report_path),
        report_sha=report["_sha256"],
        reproduce_fake=reproduce_fake,
        reproduce_real=reproduce_real,
        reproduce_resume_fake=resume_fake,
        reproduce_resume_real=resume_real,
    )

    # Fail closed if any raw-text / decision / Gold key leaked into the docs.
    for doc, label in (
        (prediction_doc, "predictions"),
        (telemetry, "telemetry"),
        (cost_doc, "cost"),
        (manifest, "manifest"),
    ):
        if _contains_keys(doc, _FORBIDDEN_TEXT_KEYS):
            raise Gdpr7ExecutionError(
                f"raw text containment failed for committed {label} doc"
            )
        if _contains_keys(doc, _FORBIDDEN_DECISION_KEYS):
            raise Gdpr7ExecutionError(
                f"decision/Gold containment failed for committed {label} doc"
            )

    files = {
        "predictions.json": _json_bytes(prediction_doc),
        "telemetry.json": _json_bytes(telemetry),
        "cost.json": _json_bytes(cost_doc),
        "manifest.json": _json_bytes(manifest),
    }
    atomic_publish_directory(capsule_dir, files)

    # Ledger path may live in the raw dir (already there) -- capsule files do
    # not embed the ledger (it stays append-only outside the capsule).
    return {
        "status": manifest["status"],
        "prediction_doc": prediction_doc,
        "telemetry": telemetry,
        "cost": cost_doc,
        "manifest": manifest,
        "ledger": ledger,
        "raw_dir": raw_dir,
        "capsule_dir": capsule_dir,
        "state": state.snapshot(),
        "response_lines": response_lines,
        "fake": fake,
        "per_call_status_counts": manifest["per_call_status_counts"],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--contract-file", type=Path, default=None,
        help="Path to the execution contract JSON.  REQUIRED for real runs; "
             "the executor refuses a real run otherwise.",
    )
    parser.add_argument(
        "--authorization-file", type=Path, default=None,
        help="Path to the user's authorization event file (real runs only). "
             "Absent -> hard refuse before the first send.",
    )
    parser.add_argument(
        "--report-file", type=Path, default=None,
        help="Path to the locked preflight report (default: "
             "outputs/reports/gdpr7_direct_llm_preflight_v1.json).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--runtime-dry-run", dest="fake_transport", action="store_true",
        help="Full 74-call fake verification run (zero network, zero API).",
    )
    mode.add_argument(
        "--fake-transport", action="store_true",
        help="Alias of --runtime-dry-run: full 74-call fake verification run.",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume a partial/aborted run from the raw dir ledger; re-sends "
             "ONLY never-attempted requests (never re-sends completed or "
             "auto-resends in_doubt entries).",
    )
    parser.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_RAW_DIR,
        help="Directory for raw_responses.jsonl + ledger.jsonl.",
    )
    parser.add_argument(
        "--capsule-dir", type=Path, default=DEFAULT_CAPSULE_DIR,
        help="Directory for predictions/telemetry/cost/manifest (published "
             "only when all 74 requests were attempted).",
    )
    parser.add_argument("--transport-timeout", type=float, default=180.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    fake = bool(args.fake_transport)
    try:
        summary = execute_batch(
            raw_dir=args.raw_dir,
            capsule_dir=args.capsule_dir,
            fake=fake,
            report_file=args.report_file,
            contract_file=args.contract_file,
            authorization_file=args.authorization_file,
            resume=args.resume,
            timeout_seconds=args.transport_timeout,
        )
    except Gdpr7ExecutionError as exc:
        print(f"GDPR Direct-LLM executor refused/aborted: {exc}")
        return 2
    counts = summary["per_call_status_counts"]
    state = summary["state"]
    print(
        f"GDPR Direct-LLM executor: status={summary['status']} "
        f"(fake={summary['fake']})"
    )
    print(
        f"attempted={sum(counts.values())} completed={counts['completed']} "
        f"in_doubt={counts['in_doubt']} failed={counts['failed']} "
        f"cost_usd={state['cost_usd']}"
    )
    print(f"capsule={_rel(summary['capsule_dir'])} "
          f"raw={_rel(summary['raw_dir'])}")
    print("reproduce (fake verify): "
          f"{summary['manifest']['reproduce_command_fake_verify']}")
    print("reproduce (real, after authorization): "
          f"{summary['manifest']['reproduce_command_real']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

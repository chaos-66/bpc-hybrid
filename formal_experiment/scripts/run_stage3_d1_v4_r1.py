# -*- coding: utf-8 -*-
"""Controlled five-call Direct-LLM runner for the v4 Table 3 benchmark.

This runner reuses the exact five request bodies produced by
``prepare_stage3_execution_v4.request_bodies()`` and binds them to the frozen
preflight hashes.  It never reads project ``.env`` files.  The API key is
read only from the current process environment.  Real dispatch is serial,
capped at five calls, retry=0, with a persistent attempt ledger written before
each HTTP request so restart cannot resend an attempted sample.

Zero network mode:
* ``--check-only`` validates prompt/registry/preflight/body/source bindings.
* Tests inject an offline transport into ``execute``; no real network is used.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.d1_schema_adapter import adapt_relay_record  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402
from bpc_hybrid.h1_transport import decode_chat_completion_envelope  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402

import prepare_stage3_execution_v4 as prep  # noqa: E402

OUT_DIR = ROOT / "data/predictions/stage3_v4_d1_frozen_v1"
PREFLIGHT = ROOT / "outputs/reports/stage3_d1_preflight_v4.json"
AUTH = ROOT / "configs/authorization/stage3_d1_v4_r1_user_authorization_v1.json"
LIVE_CONTRACT_CHECK = ROOT / "outputs/reports/stage3_d1_v4_r1_live_contract_check.json"
PREFLIGHT_SHA256 = "b79cae69bd295d1be933eb4109a44c5a88ca8579ee646833d59dd5d0411020c5"
PROMPT_SHA256 = "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
REGISTRY_SHA256 = "31f3358d089611b85a4a50d36444a4c59f6d965abbf0b8770aeb73db13642749"
SAMPLE_IDS = (
    "gdpr_article13p3_s001",
    "gdpr_article14p4_s001",
    "gdpr_article18p3_s001",
    "gdpr_article35p1_s001",
    "gdpr_article36p1_s001",
)
MODEL = "deepseek-v4-pro"
RELEASE = "DeepSeek-V4-Pro-0813"
BASE_URL = "https://api.deepseek.com/v1"
CALLS_CAP = 5
RETRY_CAP = 0
MAX_OUTPUT_TOKENS = 4096
TOTAL_OUTPUT_CAP = 20480
TOTAL_BUDGET_USD = 8.02
PEAK_INPUT_PER_MILLION = 1.32
PEAK_OUTPUT_PER_MILLION = 3.96


class D1RunError(RuntimeError):
    """Fail-closed runner precondition or state error."""


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _encode_preflight_body(body: Mapping[str, Any]) -> bytes:
    """Encode exactly as ``prepare_stage3_execution_v4.build_preflight`` did.

    The historical preflight used ``json.dumps(body)`` with default
    ``ensure_ascii=True``.  The R1 contract requires the HTTP request bytes to
    be those preflight bytes, not a re-serialization with different escaping.
    """
    return json.dumps(dict(body)).encode("utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def verify_live_contract() -> dict[str, Any]:
    """Fail closed unless the live official model/price check is present.

    The check file is produced by the executing agent from an HTTP 200 fetch
    of the official pricing page and contains no credentials.
    """
    if not LIVE_CONTRACT_CHECK.is_file():
        raise D1RunError(f"live contract check missing: {_rel(LIVE_CONTRACT_CHECK)}")
    doc = _read_json(LIVE_CONTRACT_CHECK)
    if doc.get("contract_match") is not True:
        raise D1RunError("live model/price contract check did not match")
    if doc.get("model_name_present") is not True or doc.get("documented_release_present") is not True:
        raise D1RunError("live model identity check did not match")
    if float(doc.get("peak_input_cache_miss_per_million") or -1) != PEAK_INPUT_PER_MILLION:
        raise D1RunError("live input price drift")
    if float(doc.get("peak_output_per_million") or -1) != PEAK_OUTPUT_PER_MILLION:
        raise D1RunError("live output price drift")
    return doc


def verify_authorization() -> dict[str, Any]:
    if not AUTH.is_file():
        raise D1RunError(f"authorization file missing: {_rel(AUTH)}")
    auth = _read_json(AUTH)
    status = str(auth.get("status") or "")
    if not (status == "authorized" or status.startswith("authorized_r1")):
        raise D1RunError("authorization status is not authorized for R1")
    caps = auth.get("hard_caps") or {}
    if int(caps.get("calls", 0)) != CALLS_CAP or int(caps.get("retries", -1)) != RETRY_CAP:
        raise D1RunError("authorization call/retry caps drift")
    if int(caps.get("total_output_tokens", 0)) != TOTAL_OUTPUT_CAP:
        raise D1RunError("authorization output-token cap drift")
    if float(caps.get("total_budget_usd", 0.0)) != TOTAL_BUDGET_USD:
        raise D1RunError("authorization budget cap drift")
    if list(auth.get("sample_ids") or []) != list(SAMPLE_IDS):
        raise D1RunError("authorization sample-id scope drift")
    if auth.get("prompt_sha256") != PROMPT_SHA256:
        raise D1RunError("authorization prompt hash drift")
    if auth.get("registry_sha256") != REGISTRY_SHA256:
        raise D1RunError("authorization registry hash drift")
    if auth.get("model") != MODEL:
        raise D1RunError("authorization model drift")
    return auth


def verify_preflight_and_bodies() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not PREFLIGHT.is_file():
        raise D1RunError(f"preflight missing: {_rel(PREFLIGHT)}")
    if _sha_bytes(PREFLIGHT.read_bytes()) != PREFLIGHT_SHA256:
        raise D1RunError("preflight SHA drift")
    preflight = _read_json(PREFLIGHT)
    if preflight.get("planned_calls") != CALLS_CAP or int(preflight.get("retry_cap", -1)) != RETRY_CAP:
        raise D1RunError("preflight call/retry policy drift")
    if (preflight.get("method") or {}).get("model") != MODEL:
        raise D1RunError("preflight model drift")
    rows = prep.request_bodies()
    if len(rows) != CALLS_CAP:
        raise D1RunError("preparer did not produce exactly five request bodies")
    calls = preflight.get("calls") or []
    if len(calls) != CALLS_CAP:
        raise D1RunError("preflight calls array drift")
    verified: list[dict[str, Any]] = []
    for index, ((sentence, body), call) in enumerate(zip(rows, calls), start=1):
        if sentence.get("sample_id") != call.get("sample_id"):
            raise D1RunError(f"sample order drift at call {index}")
        if sentence.get("sample_id") not in SAMPLE_IDS:
            raise D1RunError(f"out-of-scope sample at call {index}")
        if sentence.get("text_sha256") != call.get("source_text_sha256"):
            raise D1RunError(f"source text hash drift at call {index}")
        raw = _encode_preflight_body(body)
        if _sha_bytes(raw) != call.get("body_sha256"):
            raise D1RunError(f"body SHA drift at call {index}")
        if len(raw) != int(call.get("body_bytes", -1)):
            raise D1RunError(f"body byte length drift at call {index}")
        if int(body.get("max_tokens", -1)) != MAX_OUTPUT_TOKENS:
            raise D1RunError(f"max_tokens drift at call {index}")
        verified.append({
            "index": index,
            "sample_id": sentence["sample_id"],
            "source_text": sentence["approved_text_en"],
            "source_text_sha256": sentence["text_sha256"],
            "body": body,
            "body_sha256": call["body_sha256"],
            "body_bytes": call["body_bytes"],
        })
    return preflight, verified


class RunLock:
    def __init__(self, path: Path):
        self.path = path
        self.acquired = False

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            existing = ""
            try:
                existing = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            raise D1RunError(f"run lock already exists: {_rel(self.path)} content={existing!r}") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "pid": os.getpid(),
                "started_utc": _utc_now(),
                "calls_cap": CALLS_CAP,
                "retry_cap": RETRY_CAP,
            }, ensure_ascii=False) + "\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False


def _cost_usd(usage: Mapping[str, Any]) -> float | None:
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, (int, float)) or isinstance(prompt, bool):
        return None
    if not isinstance(completion, (int, float)) or isinstance(completion, bool):
        return None
    return (float(prompt) * PEAK_INPUT_PER_MILLION
            + float(completion) * PEAK_OUTPUT_PER_MILLION) / 1_000_000.0

class FrozenBodyHttpTransport:
    """Single-use HTTP transport for one exact preflight body.

    The API key is injected only into the Authorization header.  The body is
    serialized exactly as the preflight did and its SHA-256 is checked before
    dispatch.  Errors are sanitized and never include the key or URL query.
    """

    def __init__(self, api_key: str, base_url: str = BASE_URL, timeout_seconds: float = 180.0):
        if not api_key:
            raise D1RunError("empty API key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = float(timeout_seconds)

    def send(self, body: Mapping[str, Any], expected_body_sha256: str,
             expected_body_bytes: int | None = None) -> dict[str, Any]:
        raw_body = _encode_preflight_body(body)
        if _sha_bytes(raw_body) != expected_body_sha256:
            raise D1RunError("request body SHA mismatch before dispatch")
        if expected_body_bytes is not None and len(raw_body) != int(expected_body_bytes):
            raise D1RunError("request body byte-length mismatch before dispatch")
        url = self._base_url
        if url.endswith("/chat/completions"):
            pass
        elif url.endswith("/v1"):
            url = url + "/chat/completions"
        else:
            url = url + "/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0.0.0 Safari/537.36"),
        }
        request = urllib.request.Request(url, data=raw_body, headers=headers, method="POST")
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                response_body = response.read()
                status_code = int(response.status)
                content_type = response.headers.get("Content-Type")
        except urllib.error.HTTPError as exc:
            raise D1RunError(f"HTTP error status={getattr(exc, 'code', 'unknown')}") from exc
        except socket.timeout as exc:
            raise D1RunError("HTTP timeout") from exc
        except ssl.SSLError as exc:
            raise D1RunError("HTTP SSL error") from exc
        except urllib.error.URLError as exc:
            raise D1RunError("HTTP URL error") from exc
        except OSError as exc:
            raise D1RunError("HTTP OS error") from exc
        elapsed = time.perf_counter() - started
        if status_code != 200:
            raise D1RunError(f"HTTP non-200 status={status_code}")
        decode = decode_chat_completion_envelope(response_body, content_type)
        return {
            "http_status": status_code,
            "content_type": content_type,
            "raw_response_body": response_body,
            "decode": decode,
            "elapsed_seconds": round(elapsed, 3),
        }

def _strip_json_content(raw: str) -> str:
    content = (raw or "").strip().strip("`").strip()
    if content.lower().startswith("json"):
        content = content[4:].strip()
    return content


def _binding_check(payload: Any, sample_id: str, source_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "failed",
        "errors": [],
        "expected": {
            "sample_id": sample_id,
            "source_id": sample_id,
            "source_text_sha256": _sha_text(source_text),
            "source_text_length": len(source_text),
        },
        "observed": {
            "payload_type": type(payload).__name__,
            "sample_id": None,
            "source_id": None,
            "source_text_sha256": None,
            "source_text_length": None,
        },
    }
    if not isinstance(payload, dict):
        result["errors"].append("payload_not_json_object")
        return result
    for field in ("sample_id", "source_id"):
        actual = payload.get(field)
        result["observed"][field] = actual
        if actual != sample_id:
            result["errors"].append(f"{field}_mismatch")
    actual_text = payload.get("source_text")
    if not isinstance(actual_text, str):
        result["errors"].append("source_text_not_string")
    else:
        result["observed"]["source_text_sha256"] = _sha_text(actual_text)
        result["observed"]["source_text_length"] = len(actual_text)
        if actual_text != source_text:
            result["errors"].append("source_text_mismatch")
    if not result["errors"]:
        result["status"] = "passed"
    return result


def convert_response_content(*, sample_id: str, source_text: str, content: str,
                             call_meta: Mapping[str, Any]) -> dict[str, Any]:
    """Parse and canonicalize one model response without repairing it."""
    base: dict[str, Any] = {
        "sample_id": sample_id,
        "request_status": "failed",
        "error_category": None,
        "error": None,
        "failure_stage": None,
        "raw_response_content_sha256": _sha_text(content),
        "request_body_sha256": call_meta.get("body_sha256"),
        "api_call_status": call_meta.get("api_call_status"),
        "transport_error": call_meta.get("transport_error"),
        "output_parse_status": "not_attempted",
        "input_binding_status": "not_attempted",
        "canonical_validation_status": "not_attempted",
        "record": None,
    }
    try:
        payload = json.loads(_strip_json_content(content))
    except Exception as exc:  # noqa: BLE001
        base.update({
            "error_category": "output_parse_failed",
            "error": f"output_parse_failed: {type(exc).__name__}: {exc}",
            "failure_stage": "output_parse",
            "output_parse_status": "failed",
        })
        return base
    base["output_parse_status"] = "passed"
    binding = _binding_check(payload, sample_id, source_text)
    base["input_binding"] = binding
    if binding["status"] != "passed":
        base.update({
            "request_status": "failed",
            "error_category": "input_binding_failed",
            "error": "input_binding_failed: " + "; ".join(binding["errors"]),
            "failure_stage": "input_binding",
            "input_binding_status": "failed",
        })
        return base
    base["input_binding_status"] = "passed"
    try:
        adapted, adapt_audit = adapt_relay_record(copy.deepcopy(payload), source_text)
    except Exception as exc:  # noqa: BLE001
        base.update({
            "error_category": "adapter_exception",
            "error": f"adapter_exception: {type(exc).__name__}: {exc}",
            "failure_stage": "adapter",
            "parser_audit": None,
        })
        return base
    base["parser_audit"] = adapt_audit
    if adapt_audit.get("status") == "failed":
        base.update({
            "error_category": "relay_schema_adaptation_failed",
            "error": "relay_schema_adaptation_failed: " + "; ".join(adapt_audit.get("failed_reasons") or []),
            "failure_stage": "adapter",
        })
        return base
    try:
        canonical, span_audit = canonicalize_record_coordinates(adapted, source_text)
    except Exception as exc:  # noqa: BLE001
        base.update({
            "error_category": "canonicalizer_exception",
            "error": f"canonicalizer_exception: {type(exc).__name__}: {exc}",
            "failure_stage": "canonicalizer",
            "canonicalizer_audit": None,
        })
        return base
    base["canonicalizer_audit"] = span_audit
    if span_audit.get("status") == "failed":
        base.update({
            "error_category": "span_canonicalization_failed",
            "error": "span_canonicalization_failed: " + "; ".join(span_audit.get("failed_reasons") or []),
            "failure_stage": "canonicalizer",
        })
        return base
    try:
        report = validate_canonical(canonical)
    except Exception as exc:  # noqa: BLE001
        base.update({
            "error_category": "canonical_validation_exception",
            "error": f"canonical_validation_exception: {type(exc).__name__}: {exc}",
            "failure_stage": "canonical_validation",
        })
        return base
    base["runtime_validation"] = report.to_dict()
    if not (report.schema_valid and report.cross_field_valid):
        base.update({
            "error_category": "canonical_validation_failed",
            "error": "canonical_validation_failed: " + "; ".join(report.errors),
            "failure_stage": "canonical_validation",
            "canonical_validation_status": "failed",
        })
        return base
    base.update({
        "request_status": "ok",
        "error_category": None,
        "error": None,
        "failure_stage": None,
        "canonical_validation_status": "passed",
        "record": canonical,
    })
    return base

def _persist_raw_response(out_dir: Path, index: int, sample_id: str,
                          response: Mapping[str, Any], body_sha256: str) -> Path:
    raw = response.get("raw_response_body") or b""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    decode = response.get("decode") or {}
    payload = {
        "schema_version": "stage3_d1_v4_raw_response@1.0.0",
        "sample_id": sample_id,
        "index": index,
        "request_body_sha256": body_sha256,
        "http_status": response.get("http_status"),
        "content_type": response.get("content_type"),
        "elapsed_seconds": response.get("elapsed_seconds"),
        "raw_response_body_sha256": _sha_bytes(raw),
        "raw_response_body_base64": base64.b64encode(raw).decode("ascii"),
        "response_model": decode.get("model"),
        "usage": decode.get("usage") or {},
        "decode": {k: v for k, v in decode.items() if k != "content"},
    }
    path = out_dir / "raw_responses" / f"{index:02d}_{sample_id}.json"
    _write_json(path, payload)
    return path


def execute(*, out_dir: Path = OUT_DIR,
            transport: Any,
            check_only: bool = False) -> dict[str, Any]:
    authorization = verify_authorization()
    live_contract = verify_live_contract()
    preflight, verified = verify_preflight_and_bodies()
    if check_only:
        return {
            "status": "verified_no_dispatch",
            "authorized_calls": CALLS_CAP,
            "retry_cap": RETRY_CAP,
            "samples": [row["sample_id"] for row in verified],
            "preflight_sha256": PREFLIGHT_SHA256,
            "prompt_sha256": PROMPT_SHA256,
            "registry_sha256": REGISTRY_SHA256,
            "authorization": _rel(AUTH),
            "live_contract_check": {
                "path": _rel(LIVE_CONTRACT_CHECK),
                "sha256": _sha_bytes(LIVE_CONTRACT_CHECK.read_bytes()),
            },
            "network_calls": 0,
            "blocked_before_dispatch": False,
        }
    out_dir = Path(out_dir)
    lock = RunLock(out_dir / ".run.lock")
    with lock:
        ledger_path = out_dir / "calls_ledger.jsonl"
        prior = _read_jsonl(ledger_path)
        attempted = {str(row.get("sample_id")) for row in prior if row.get("event") in ("attempted", "completed", "failed")}
        if attempted:
            raise D1RunError(
                "attempt ledger is not empty; refusing to reset or resend. "
                f"Attempted sample_ids: {sorted(attempted)}"
            )
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_json(out_dir / "authorization_snapshot.json", authorization)
        _write_json(out_dir / "preflight_snapshot.json", {
            "path": _rel(PREFLIGHT),
            "sha256": PREFLIGHT_SHA256,
            "planned_calls": preflight.get("planned_calls"),
            "model": (preflight.get("method") or {}).get("model"),
            "price_snapshot": preflight.get("price_snapshot"),
        })
        predictions: list[dict[str, Any]] = []
        usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        cost_total = 0.0
        output_total = 0
        completed = 0
        failed = 0
        for row in verified:
            sample_id = row["sample_id"]
            index = int(row["index"])
            if output_total + MAX_OUTPUT_TOKENS > TOTAL_OUTPUT_CAP or cost_total >= TOTAL_BUDGET_USD:
                failed += 1
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "budget_cap_pre_dispatch",
                    "error": "budget_cap_pre_dispatch",
                    "record": None,
                })
                _append_jsonl(ledger_path, {
                    "event": "failed", "sample_id": sample_id, "index": index,
                    "timestamp_utc": _utc_now(), "error": "budget_cap_pre_dispatch",
                    "state": "failed_budget_pre_dispatch",
                })
                break
            _append_jsonl(ledger_path, {
                "event": "attempted",
                "sample_id": sample_id,
                "index": index,
                "timestamp_utc": _utc_now(),
                "request_body_sha256": row["body_sha256"],
                "model": MODEL,
                "release": RELEASE,
                "state": "attempted",
            })
            try:
                response = transport.send(row["body"], row["body_sha256"], row["body_bytes"])
            except Exception as exc:  # noqa: BLE001
                failed += 1
                _append_jsonl(ledger_path, {
                    "event": "failed",
                    "sample_id": sample_id,
                    "index": index,
                    "timestamp_utc": _utc_now(),
                    "error": str(exc),
                    "state": "failed_transport",
                })
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "transport_failure",
                    "error": f"transport_failure: {type(exc).__name__}: {exc}",
                    "record": None,
                })
                break
            raw_path = _persist_raw_response(out_dir, index, sample_id, response, row["body_sha256"])
            decode = response.get("decode") or {}
            api_status = str(decode.get("status") or "unknown")
            usage = dict(decode.get("usage") or {})
            response_model = decode.get("model")
            if api_status != "ok_message_content":
                failed += 1
                _append_jsonl(ledger_path, {
                    "event": "failed",
                    "sample_id": sample_id,
                    "index": index,
                    "timestamp_utc": _utc_now(),
                    "api_call_status": api_status,
                    "error_detail": decode.get("error_detail"),
                    "state": "failed_decoder",
                })
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": f"decoder_{api_status}",
                    "error": f"decoder_status: {api_status}",
                    "record": None,
                })
                break
            if not isinstance(response_model, str) or response_model != MODEL:
                failed += 1
                _append_jsonl(ledger_path, {
                    "event": "failed",
                    "sample_id": sample_id,
                    "index": index,
                    "timestamp_utc": _utc_now(),
                    "api_call_status": api_status,
                    "response_model": response_model,
                    "error": "response_model_mismatch",
                    "state": "failed_model_contract",
                })
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "response_model_mismatch",
                    "error": f"response_model_mismatch: expected {MODEL!r}, observed {response_model!r}",
                    "response_model": response_model,
                    "record": None,
                })
                break
            if not usage or "completion_tokens" not in usage:
                failed += 1
                _append_jsonl(ledger_path, {
                    "event": "failed",
                    "sample_id": sample_id,
                    "index": index,
                    "timestamp_utc": _utc_now(),
                    "api_call_status": api_status,
                    "error_detail": "usage_or_completion_tokens_missing",
                    "state": "failed_unknown_charge",
                })
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "usage_missing",
                    "error": "usage_or_completion_tokens_missing",
                    "record": None,
                })
                break
            completion_tokens = int(usage.get("completion_tokens") or 0)
            output_total += completion_tokens
            for key in usage_total:
                if isinstance(usage.get(key), (int, float)) and not isinstance(usage.get(key), bool):
                    usage_total[key] += int(usage[key])
            call_cost = _cost_usd(usage)
            if call_cost is None:
                failed += 1
                _append_jsonl(ledger_path, {
                    "event": "failed",
                    "sample_id": sample_id,
                    "index": index,
                    "timestamp_utc": _utc_now(),
                    "error": "cost_unknown",
                    "state": "failed_unknown_charge",
                })
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "cost_unknown",
                    "error": "cost_unknown",
                    "record": None,
                })
                break
            cost_total += call_cost
            if output_total > TOTAL_OUTPUT_CAP or cost_total > TOTAL_BUDGET_USD:
                failed += 1
                _append_jsonl(ledger_path, {
                    "event": "failed",
                    "sample_id": sample_id,
                    "index": index,
                    "timestamp_utc": _utc_now(),
                    "error": "budget_cap_exceeded",
                    "output_total": output_total,
                    "cost_total_usd": round(cost_total, 6),
                    "state": "failed_budget",
                })
                predictions.append({
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "budget_cap_exceeded",
                    "error": "budget_cap_exceeded",
                    "record": None,
                })
                break
            content = decode.get("content") or ""
            prediction = convert_response_content(
                sample_id=sample_id,
                source_text=row["source_text"],
                content=content,
                call_meta={
                    "body_sha256": row["body_sha256"],
                    "api_call_status": api_status,
                    "transport_error": None,
                    "raw_response_path": _rel(raw_path),
                },
            )
            prediction["raw_response_path"] = _rel(raw_path)
            prediction["response_model"] = response_model
            prediction["usage"] = usage
            prediction["cost_usd"] = round(call_cost, 8)
            predictions.append(prediction)
            if prediction.get("request_status") == "ok":
                completed += 1
            else:
                failed += 1
            _append_jsonl(ledger_path, {
                "event": "completed" if prediction.get("request_status") == "ok" else "failed",
                "sample_id": sample_id,
                "index": index,
                "timestamp_utc": _utc_now(),
                "api_call_status": api_status,
                "response_model": response_model,
                "request_status": prediction.get("request_status"),
                "error_category": prediction.get("error_category"),
                "usage": usage,
                "cost_usd": round(call_cost, 8),
                "raw_response_path": _rel(raw_path),
                "state": "completed",
            })
            if prediction.get("request_status") != "ok":
                break
        # Fill failed envelopes for any sample not attempted or aborted after.
        by_sample = {p["sample_id"]: p for p in predictions}
        for row in verified:
            sample_id = row["sample_id"]
            if sample_id not in by_sample:
                by_sample[sample_id] = {
                    "sample_id": sample_id,
                    "request_status": "failed",
                    "error_category": "not_attempted_after_stop",
                    "error": "not_attempted_after_stop",
                    "record": None,
                }
        records = [by_sample[sid] for sid in SAMPLE_IDS]
        capsule = {
            "schema_version": "gdpr7_direct_llm_predictions@1.0.0",
            "dataset_id": "stage3_scoped_gdpr_v4_r1",
            "method_id": "direct_llm",
            "record_count": len(records),
            "gold_read_by_runner": False,
            "raw_text_committed": False,
            "records": records,
        }
        predictions_path = out_dir / "predictions.json"
        _write_json(predictions_path, capsule)
        manifest = {
            "schema_version": "stage3_v4_d1_r1_run@1.0.0",
            "run_id": "stage3_v4_d1_frozen_v1",
            "outputs": {
                "predictions": {
                    "path": str(predictions_path.relative_to(ROOT)).replace("\\", "/"),
                    "sha256": _sha_bytes(predictions_path.read_bytes()),
                }
            },
            "status": ("complete" if completed == CALLS_CAP else
                       f"partial_or_blocked_completed={completed}_failed={failed}"),
            "method": {"model": MODEL, "documented_release": RELEASE,
                       "expected_response_model": MODEL,
                       "temperature": 0, "top_p": 1, "max_tokens": MAX_OUTPUT_TOKENS,
                       "thinking": "disabled", "stream": False,
                       "response_format": None, "seed": "omitted"},
            "response_models": sorted({str(p.get("response_model")) for p in predictions
                                       if p.get("response_model") is not None}),
            "authorization": {"path": _rel(AUTH), "calls_cap": CALLS_CAP,
                              "retry_cap": RETRY_CAP,
                              "total_output_tokens_cap": TOTAL_OUTPUT_CAP,
                              "total_budget_usd_cap": TOTAL_BUDGET_USD},
            "preflight": {"path": _rel(PREFLIGHT), "sha256": PREFLIGHT_SHA256,
                          "prompt_sha256": PROMPT_SHA256,
                          "registry_sha256": REGISTRY_SHA256},
            "live_contract_check": {
                "path": _rel(LIVE_CONTRACT_CHECK),
                "sha256": _sha_bytes(LIVE_CONTRACT_CHECK.read_bytes()),
                "contract_match": live_contract.get("contract_match"),
                "checked_at_utc": live_contract.get("checked_at_utc"),
            },
            "counts": {"attempted": sum(1 for p in predictions if p.get("request_status") != "not_attempted_after_stop"),
                       "completed": completed, "failed": failed,
                       "planned": CALLS_CAP, "retry": 0},
            "usage": usage_total,
            "output_tokens_total": output_total,
            "cost_usd_peak_conservative": round(cost_total, 8),
            "raw_response_files": sorted(str(p.relative_to(out_dir)).replace("\\", "/")
                                         for p in (out_dir / "raw_responses").glob("*.json"))
                                   if (out_dir / "raw_responses").exists() else [],
            "gold_read": False,
            "env_read_by_runner": False,
            "command": "python formal_experiment/scripts/run_stage3_d1_v4_r1.py --execute",
            "timestamp_utc": _utc_now(),
        }
        _write_json(out_dir / "manifest.json", manifest)
        return manifest


def _env_api_key() -> str | None:
    # R1: DEEPSEEK_API_KEY is the first supported alias; the two BPC names
    # remain accepted so an existing controlled process does not need renaming.
    return (os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("BPC_HYBRID_DeepSeek_API_KEY")
            or os.environ.get("BPC_HYBRID_LLM_API_KEY"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()
    if not (args.check_only or args.execute):
        parser.error("choose --check-only or --execute")
    if args.check_only:
        result = execute(out_dir=args.out_dir, transport=None, check_only=True)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    api_key = _env_api_key()
    if not api_key:
        print(json.dumps({
            "status": "blocked_missing_process_env_api_key",
            "message": "DEEPSEEK_API_KEY / BPC_HYBRID_DeepSeek_API_KEY / BPC_HYBRID_LLM_API_KEY not present in current process environment",
            "network_calls": 0,
            "env_file_read": False,
        }, ensure_ascii=False, indent=2))
        return 3
    transport = FrozenBodyHttpTransport(api_key=api_key)
    manifest = execute(out_dir=args.out_dir, transport=transport, check_only=False)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest.get("status") == "complete" else 4


if __name__ == "__main__":
    raise SystemExit(main())
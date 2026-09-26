# -*- coding: utf-8 -*-
"""Execute the frozen 19-call S3-TABLE3-R5 Ours Stage-2 API run.

The runner reads only the committed frozen payload manifest, the committed Gold
release/authorization artifacts, and the process environment API key.  It never
reads/stores ``.env``.  It creates the durable real-call ledger before the first
network send, stores every raw response (including error bodies when present),
stops after the first failed call, and never retries.

After a complete 19/19 API run it canonicalizes the new predictions with the
frozen existing D1 canonical pipeline, combines them with the 14 verified
historical predictions, writes the formal 33-record Ours Stage-2 capsule, and
freezes it before any Stage-3 metric is computed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import build_stage3_table3_r5_api_payload_freeze_v2 as payload_freeze  # noqa: E402
import run_stage3_d1_v4_r1 as d1  # noqa: E402
from bpc_hybrid.h1_transport import decode_chat_completion_envelope  # noqa: E402

PAYLOAD = ROOT / "outputs/reports/stage3_table3_r5_api_payload_freeze_v2.json"
GOLD_RELEASE = ROOT / "outputs/reports/stage3_table3_r5_formal_gold_release_v1.json"
AUTH = ROOT / "configs/authorization/stage3_table3_r5_user_authorization_v1.json"
REUSE = ROOT / "outputs/reports/stage3_table3_r5_prediction_reuse_v2.json"
OUT_DIR = ROOT / "data/predictions/stage3_table3_r5_ours_stage2_new19_v1"
COMBINED_DIR = ROOT / "data/predictions/stage3_table3_r5_ours_stage2_formal_v1"
REPORT_DIR = ROOT / "outputs/reports"
LEDGER_PATH = OUT_DIR / "api_execution_ledger_v1.json"
RAW_DIR = OUT_DIR / "raw_responses"
LIVE_PRICE_PATH = REPORT_DIR / "stage3_table3_r5_live_pricing_check_v1.json"
API_REPORT_PATH = REPORT_DIR / "stage3_table3_r5_api_execution_v1.json"
OURS_MANIFEST_PATH = REPORT_DIR / "stage3_table3_r5_ours_prediction_manifest_v1.json"
OURS_FREEZE_PATH = REPORT_DIR / "stage3_table3_r5_ours_prediction_freeze_v1.json"
BLOCKED_PATH = REPORT_DIR / "stage3_table3_r5_api_execution_blocked_v1.json"

EXPECTED_PAYLOAD_SHA = "bd029e42ff6db8752e138827ad9861c660f1eda1b4b6dbaac8ee7715b30d3707"
EXPECTED_PROMPT_SHA = "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
EXPECTED_GOLD_JSON_SHA = "1e6de56fb3a934646816fe361873966acae1b0022e80c65f9eadf45d591c5884"
MODEL = "deepseek-v4-pro"
BASE_URL = "https://api.deepseek.com/v1"
PEAK_INPUT_PER_MILLION = 1.32
PEAK_OUTPUT_PER_MILLION = 3.96
MAX_OUTPUT_TOKENS = 4096
COST_CAP_USD = 0.91
RETRY_CAP = 0
REQUEST_IDS = [
    "R5-S1-T1", "R5-S1-T2", "R5-S1-T3", "R5-S1-T4", "R5-S2-T2",
    "R5-S3-T1", "R5-S3-T2", "R5-S4-T1", "R5-S4-T2", "R5-S4-T3",
    "R5-S4-T4", "R5-S5-T1", "R5-S5-T2", "R5-S5-T3", "R5-S5-T4",
    "R5-S6-T1", "R5-S6-T2", "R5-S7-T1", "R5-S8-T1",
]
FORBIDDEN_BODY_KEYS = payload_freeze.FORBIDDEN_BODY_KEYS


class ApiRunError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_text(value: str) -> str:
    return _sha_bytes(value.encode("utf-8"))


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _write_bytes_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    with tmp.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _encode_body(body: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(body)).encode("utf-8")


def _env_api_key() -> str | None:
    return (os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("BPC_HYBRID_DeepSeek_API_KEY")
            or os.environ.get("BPC_HYBRID_LLM_API_KEY"))


def _validate_payload() -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = _load_json(PAYLOAD)
    rebuilt = payload_freeze.build_payload_manifest()
    if rebuilt != frozen:
        raise ApiRunError("frozen payload manifest drift or non-reconstructible")
    if frozen.get("payload_manifest_sha256") != EXPECTED_PAYLOAD_SHA:
        raise ApiRunError("payload manifest internal SHA drift")
    if frozen.get("new_request_count") != len(REQUEST_IDS):
        raise ApiRunError("request count drift")
    if frozen.get("request_ids") != REQUEST_IDS:
        raise ApiRunError("request id order drift")
    if frozen.get("prompt", {}).get("sha256_text_normalized") != EXPECTED_PROMPT_SHA:
        raise ApiRunError("prompt SHA drift")
    if len(frozen.get("requests") or []) != len(REQUEST_IDS):
        raise ApiRunError("request row count drift")
    for ordinal, row in enumerate(frozen["requests"], start=1):
        if int(row.get("request_ordinal") or -1) != ordinal:
            raise ApiRunError(f"request ordinal drift at {ordinal}")
        raw = _encode_body(row["request_body"])
        if _sha_bytes(raw) != row.get("request_body_sha256"):
            raise ApiRunError(f"request body SHA drift: {row.get('requirement_id')}")
        if len(raw) != int(row.get("request_body_utf8_bytes") or -1):
            raise ApiRunError(f"request body byte size drift: {row.get('requirement_id')}")
        if row.get("model") != MODEL:
            raise ApiRunError(f"request model drift: {row.get('requirement_id')}")
        forbidden = sorted(FORBIDDEN_BODY_KEYS & payload_freeze._walk_keys(row["request_body"]))
        if forbidden:
            raise ApiRunError(f"forbidden body keys at {row.get('requirement_id')}: {forbidden}")
    return frozen, rebuilt


def _validate_release_and_auth() -> tuple[dict[str, Any], dict[str, Any]]:
    release = _load_json(GOLD_RELEASE)
    if release.get("formal_gold_released") is not True:
        raise ApiRunError("Gold release marker is not released")
    if release.get("gold_packet_json", {}).get("sha256") != EXPECTED_GOLD_JSON_SHA:
        raise ApiRunError("Gold release packet SHA drift")
    auth = _load_json(AUTH)
    if auth.get("status") != "authorized":
        raise ApiRunError("authorization status is not authorized")
    if auth.get("authorized_call_count_max") != len(REQUEST_IDS):
        raise ApiRunError("authorized call count drift")
    if auth.get("authorized_retry_count") != RETRY_CAP:
        raise ApiRunError("authorized retry cap drift")
    if float(auth.get("authorized_cost_cap_usd", -1.0)) != COST_CAP_USD:
        raise ApiRunError("authorized cost cap drift")
    if auth.get("payload_manifest_sha256") != EXPECTED_PAYLOAD_SHA:
        raise ApiRunError("authorization payload SHA drift")
    if auth.get("request_ids") != REQUEST_IDS:
        raise ApiRunError("authorization request scope drift")
    return release, auth


def _live_pricing_check() -> dict[str, Any]:
    url = "https://api-docs.deepseek.com/quick_start/pricing/"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/126.0.0.0 Safari/537.36"),
            "Accept-Encoding": "identity",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            status = int(response.status)
    except Exception as exc:  # noqa: BLE001
        check = {
            "schema_version": "stage3_table3_r5_live_pricing_check@1.0.0",
            "fetched_at_utc": _utc_now(),
            "url": url,
            "http_status": None,
            "contract_match": False,
            "error": f"{type(exc).__name__}: {exc}",
            "network_calls_to_llm_api": 0,
        }
        _write_json_atomic(LIVE_PRICE_PATH, check)
        raise ApiRunError("official pricing page could not be fetched") from exc
    text = raw.decode("utf-8", errors="replace")
    lower = text.lower()
    model_name_present = "deepseek-v4-pro" in lower
    release_present = "deepseek-v4-pro-0813" in lower
    cache_hit = "0.044" in text
    cache_miss = "1.32" in text
    output = "3.96" in text
    contract_match = bool(model_name_present and release_present and cache_hit and cache_miss and output)
    check = {
        "schema_version": "stage3_table3_r5_live_pricing_check@1.0.0",
        "fetched_at_utc": _utc_now(),
        "url": url,
        "http_status": status,
        "page_sha256": _sha_bytes(raw),
        "model_name_present": model_name_present,
        "documented_release_present": release_present,
        "peak_input_cache_hit_per_million_observed": 0.044 if cache_hit else None,
        "peak_input_cache_miss_per_million_observed": 1.32 if cache_miss else None,
        "peak_output_per_million_observed": 3.96 if output else None,
        "expected_peak_input_cache_miss_per_million": PEAK_INPUT_PER_MILLION,
        "expected_peak_output_per_million": PEAK_OUTPUT_PER_MILLION,
        "contract_match": contract_match,
        "network_calls_to_llm_api": 0,
    }
    _write_json_atomic(LIVE_PRICE_PATH, check)
    if not contract_match:
        raise ApiRunError("official pricing/model identity did not match frozen assumptions")
    return check


def _worst_case_cost(row: Mapping[str, Any]) -> float:
    body_bytes = len(_encode_body(row["request_body"]))
    return (body_bytes * PEAK_INPUT_PER_MILLION + MAX_OUTPUT_TOKENS * PEAK_OUTPUT_PER_MILLION) / 1_000_000.0


def _usage_cost(usage: Mapping[str, Any]) -> float:
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    if not isinstance(prompt, (int, float)) or isinstance(prompt, bool):
        raise ApiRunError("usage missing prompt_tokens")
    if not isinstance(completion, (int, float)) or isinstance(completion, bool):
        raise ApiRunError("usage missing completion_tokens")
    return (float(prompt) * PEAK_INPUT_PER_MILLION
            + float(completion) * PEAK_OUTPUT_PER_MILLION) / 1_000_000.0


def _new_ledger(requests: list[Mapping[str, Any]]) -> dict[str, Any]:
    rows = []
    for row in requests:
        rows.append({
            "request_ordinal": int(row["request_ordinal"]),
            "requirement_id": row["requirement_id"],
            "request_body_sha256": row["request_body_sha256"],
            "send_started_utc": None,
            "send_finished_utc": None,
            "http_status": None,
            "result_status": "not_started",
            "response_raw_sha256": None,
            "response_raw_path": None,
            "response_model": None,
            "usage": {},
            "input_tokens": None,
            "output_tokens": None,
            "error": None,
            "retry_count": 0,
            "state": "not_started",
        })
    return {
        "schema_version": "stage3_table3_r5_api_execution_ledger@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "provider": "DeepSeek",
        "model": MODEL,
        "base_url": BASE_URL,
        "authorized_calls_max": len(requests),
        "retry_cap": RETRY_CAP,
        "authorized_cost_cap_usd": COST_CAP_USD,
        "real_api_calls_made": 0,
        "status": "initialized_before_first_send",
        "rows": rows,
        "actual_usage_total": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "estimated_cost_usd_total": 0.0,
        "ambiguous_send_state": False,
        "created_utc": _utc_now(),
    }


def _find_row(ledger: dict[str, Any], ordinal: int) -> dict[str, Any]:
    for row in ledger["rows"]:
        if int(row["request_ordinal"]) == ordinal:
            return row
    raise ApiRunError(f"ledger row missing: {ordinal}")


def _classify_http(raw: bytes, content_type: str | None, decode: Mapping[str, Any]) -> str:
    status = str(decode.get("status") or "")
    if status != "ok_message_content":
        return f"failed_decoder_{status or 'unknown'}"
    return "completed"


def execute(*, api_key: str | None, check_only: bool = False) -> dict[str, Any]:
    frozen, rebuilt = _validate_payload()
    release, auth = _validate_release_and_auth()
    price_check = _live_pricing_check()
    requests = list(frozen["requests"])
    worst = [_worst_case_cost(row) for row in requests]
    total_worst = sum(worst)
    if total_worst > COST_CAP_USD:
        raise ApiRunError(f"frozen worst-case total {total_worst:.6f} exceeds cap")
    if check_only:
        key_present = bool(api_key or _env_api_key())
        return {
            "status": "verified_no_dispatch" if key_present else "verified_no_dispatch_key_missing",
            "authorized_calls": len(requests),
            "retry_cap": RETRY_CAP,
            "cost_cap_usd": COST_CAP_USD,
            "frozen_worst_case_total_usd": round(total_worst, 8),
            "payload_manifest_sha256": frozen["payload_manifest_sha256"],
            "prompt_sha256": frozen["prompt"]["sha256_text_normalized"],
            "gold_release_sha256": _sha_file(GOLD_RELEASE),
            "authorization_sha256": _sha_file(AUTH),
            "live_pricing_check": price_check,
            "api_key_present": key_present,
            "network_calls_to_llm_api": 0,
        }

    key = api_key or _env_api_key()
    if not key:
        raise ApiRunError("no API key in current process environment")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ledger = _new_ledger(requests)
    _write_json_atomic(LEDGER_PATH, ledger)
    _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
        "event": "ledger_initialized", "timestamp_utc": _utc_now(),
        "authorized_calls_max": len(requests), "real_api_calls_made": 0,
    })

    actual_cost = 0.0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    attempted = 0
    completed = 0
    failed = 0
    stop_reason = None

    for index, row in enumerate(requests):
        ordinal = int(row["request_ordinal"])
        req_id = str(row["requirement_id"])
        body = row["request_body"]
        expected_body_sha = str(row["request_body_sha256"])
        raw_body = _encode_body(body)
        if _sha_bytes(raw_body) != expected_body_sha:
            raise ApiRunError(f"body SHA drift before dispatch: {req_id}")
        remaining_worst = sum(worst[index:])
        if actual_cost + remaining_worst > COST_CAP_USD + 1e-12:
            stop_reason = f"cost gate would be exceeded before {req_id}"
            break

        ledger_row = _find_row(ledger, ordinal)
        ledger_row.update({
            "send_started_utc": _utc_now(),
            "state": "send_started",
            "result_status": "send_started",
        })
        ledger["real_api_calls_made"] = attempted + 1
        ledger["status"] = "send_started"
        _write_json_atomic(LEDGER_PATH, ledger)
        _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
            "event": "send_started", "ordinal": ordinal, "requirement_id": req_id,
            "request_body_sha256": expected_body_sha, "timestamp_utc": ledger_row["send_started_utc"],
        })
        attempted += 1

        url = BASE_URL.rstrip("/") + "/chat/completions"
        http_request = urllib.request.Request(
            url,
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/126.0.0.0 Safari/537.36"),
            },
            method="POST",
        )
        raw_response = b""
        content_type = None
        http_status = None
        transport_error = None
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(http_request, timeout=240) as response:
                http_status = int(response.status)
                content_type = response.headers.get("Content-Type")
                raw_response = response.read()
        except urllib.error.HTTPError as exc:
            http_status = int(getattr(exc, "code", 0) or 0)
            content_type = getattr(exc, "headers", None).get("Content-Type") if getattr(exc, "headers", None) else None
            try:
                raw_response = exc.read() or b""
            except Exception:  # noqa: BLE001
                raw_response = b""
            transport_error = f"HTTP error status={http_status}"
        except ssl.SSLError as exc:
            transport_error = f"HTTP SSL error: {type(exc).__name__}"
        except urllib.error.URLError as exc:
            transport_error = f"HTTP URL error: {type(exc).__name__}"
        except OSError as exc:
            transport_error = f"HTTP OS error: {type(exc).__name__}"
        elapsed = round(time.perf_counter() - started, 3)
        finished = _utc_now()

        raw_path = RAW_DIR / f"{ordinal:02d}_{req_id}.json"
        raw_sha = _sha_bytes(raw_response) if raw_response else None
        raw_payload = {
            "schema_version": "stage3_table3_r5_api_raw_response@1.0.0",
            "request_ordinal": ordinal,
            "requirement_id": req_id,
            "request_body_sha256": expected_body_sha,
            "http_status": http_status,
            "content_type": content_type,
            "elapsed_seconds": elapsed,
            "raw_response_body_sha256": raw_sha,
            "raw_response_body_base64": base64.b64encode(raw_response).decode("ascii") if raw_response else None,
            "transport_error": transport_error,
            "received_utc": finished,
        }
        ledger_row.update({
            "send_finished_utc": finished,
            "http_status": http_status,
            "response_raw_sha256": raw_sha,
            "response_raw_path": _rel(raw_path),
            "error": transport_error,
        })

        decode: dict[str, Any] = {}
        if raw_response:
            try:
                decode = decode_chat_completion_envelope(raw_response, content_type)
            except Exception as exc:  # noqa: BLE001
                decode = {"status": "decode_exception", "error_detail": f"{type(exc).__name__}: {exc}"}
        raw_payload["decode"] = {k: v for k, v in decode.items() if k != "content"}
        _write_json_atomic(raw_path, raw_payload)

        if transport_error:
            failed += 1
            ledger_row.update({
                "result_status": "failed",
                "state": "failed",
                "error": transport_error,
            })
            ledger["status"] = "failed"
            ledger["actual_usage_total"] = usage_total
            ledger["estimated_cost_usd_total"] = round(actual_cost, 8)
            _write_json_atomic(LEDGER_PATH, ledger)
            _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
                "event": "failed", "ordinal": ordinal, "requirement_id": req_id,
                "error": transport_error, "http_status": http_status,
                "timestamp_utc": finished,
            })
            stop_reason = f"transport failure at {req_id}"
            break

        api_status = str(decode.get("status") or "unknown")
        response_model = decode.get("model")
        usage = dict(decode.get("usage") or {})
        content = decode.get("content") or ""
        ledger_row.update({
            "response_model": response_model,
            "usage": usage,
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
        })
        if api_status != "ok_message_content":
            failed += 1
            ledger_row.update({
                "result_status": "failed",
                "state": "failed",
                "error": f"decoder status: {api_status}; detail={decode.get('error_detail')}",
            })
            ledger["status"] = "failed"
            ledger["actual_usage_total"] = usage_total
            ledger["estimated_cost_usd_total"] = round(actual_cost, 8)
            _write_json_atomic(LEDGER_PATH, ledger)
            _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
                "event": "failed", "ordinal": ordinal, "requirement_id": req_id,
                "error": f"decoder status: {api_status}", "timestamp_utc": finished,
                "usage": usage,
            })
            stop_reason = f"decoder failure at {req_id}"
            break
        if response_model != MODEL:
            failed += 1
            ledger_row.update({
                "result_status": "failed",
                "state": "failed",
                "error": f"response_model_mismatch: {response_model!r}",
            })
            ledger["status"] = "failed"
            ledger["actual_usage_total"] = usage_total
            ledger["estimated_cost_usd_total"] = round(actual_cost, 8)
            _write_json_atomic(LEDGER_PATH, ledger)
            _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
                "event": "failed", "ordinal": ordinal, "requirement_id": req_id,
                "error": f"response_model_mismatch: {response_model!r}",
                "timestamp_utc": finished,
            })
            stop_reason = f"response model mismatch at {req_id}"
            break
        if not usage or "prompt_tokens" not in usage or "completion_tokens" not in usage:
            failed += 1
            ledger_row.update({
                "result_status": "failed",
                "state": "failed",
                "error": "usage_or_prompt_completion_tokens_missing",
            })
            ledger["status"] = "failed"
            _write_json_atomic(LEDGER_PATH, ledger)
            _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
                "event": "failed", "ordinal": ordinal, "requirement_id": req_id,
                "error": "usage_or_prompt_completion_tokens_missing", "timestamp_utc": finished,
            })
            stop_reason = f"missing usage at {req_id}"
            break
        call_cost = _usage_cost(usage)
        actual_cost += call_cost
        for key_name in usage_total:
            value = usage.get(key_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                usage_total[key_name] += int(value)
        completed += 1
        ledger_row.update({
            "result_status": "completed",
            "state": "completed",
            "error": None,
            "estimated_cost_usd": round(call_cost, 8),
        })
        ledger["status"] = "in_progress" if ordinal < len(requests) else "completed"
        ledger["actual_usage_total"] = usage_total
        ledger["estimated_cost_usd_total"] = round(actual_cost, 8)
        _write_json_atomic(LEDGER_PATH, ledger)
        _append_jsonl(OUT_DIR / "api_execution_events_v1.jsonl", {
            "event": "completed", "ordinal": ordinal, "requirement_id": req_id,
            "http_status": http_status, "response_model": response_model,
            "usage": usage, "estimated_cost_usd": round(call_cost, 8),
            "response_raw_sha256": raw_sha, "timestamp_utc": finished,
        })

    ledger["real_api_calls_made"] = attempted
    ledger["actual_usage_total"] = usage_total
    ledger["estimated_cost_usd_total"] = round(actual_cost, 8)
    if completed == len(requests):
        ledger["status"] = "completed"
    elif stop_reason:
        ledger["status"] = "failed"
        ledger["stop_reason"] = stop_reason
    else:
        ledger["status"] = "incomplete"
    _write_json_atomic(LEDGER_PATH, ledger)

    api_report = {
        "schema_version": "stage3_table3_r5_api_execution@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "provider": "DeepSeek",
        "model": MODEL,
        "base_url": BASE_URL,
        "authorized_calls_max": len(requests),
        "attempted": attempted,
        "completed": completed,
        "failed": failed,
        "not_started": len(requests) - attempted,
        "retries": 0,
        "ambiguous_send_state": False,
        "actual_usage_total": usage_total,
        "estimated_cost_usd": round(actual_cost, 8),
        "authorized_cost_cap_usd": COST_CAP_USD,
        "frozen_worst_case_total_usd": round(total_worst, 8),
        "ledger_path": _rel(LEDGER_PATH),
        "raw_response_dir": _rel(RAW_DIR),
        "live_pricing_check": {
            "path": _rel(LIVE_PRICE_PATH), "sha256": _sha_file(LIVE_PRICE_PATH)
        },
        "gold_release_path": _rel(GOLD_RELEASE),
        "authorization_path": _rel(AUTH),
        "status": "completed" if completed == len(requests) else "blocked_or_incomplete",
        "timestamp_utc": _utc_now(),
    }
    _write_json_atomic(API_REPORT_PATH, api_report)
    if completed != len(requests):
        _write_json_atomic(BLOCKED_PATH, {
            "schema_version": "stage3_table3_r5_api_execution_blocked@1.0.0",
            "status": "EXTERNAL_SEND_PHASE_INCOMPLETE",
            "stop_reason": stop_reason,
            "attempted": attempted,
            "completed": completed,
            "failed": failed,
            "retries": 0,
            "ledger_path": _rel(LEDGER_PATH),
            "raw_response_dir": _rel(RAW_DIR),
            "remaining_not_started": [r["requirement_id"] for r in requests[attempted:]],
            "timestamp_utc": _utc_now(),
        })
        return api_report

    # Canonicalize every successful new response using the existing frozen pipeline.
    new_rows: list[dict[str, Any]] = []
    for row in requests:
        ordinal = int(row["request_ordinal"])
        req_id = str(row["requirement_id"])
        ledger_row = _find_row(ledger, ordinal)
        raw_path = ROOT / ledger_row["response_raw_path"]
        raw_doc = _load_json(raw_path)
        raw_bytes = base64.b64decode(raw_doc["raw_response_body_base64"])
        decode = decode_chat_completion_envelope(raw_bytes, raw_doc.get("content_type"))
        content = decode.get("content") or ""
        canonical = d1.convert_response_content(
            sample_id=row["sample_id"],
            source_text=row["source_text"],
            content=content,
            call_meta={
                "body_sha256": row["request_body_sha256"],
                "api_call_status": decode.get("status"),
                "transport_error": None,
                "raw_response_path": _rel(raw_path),
            },
        )
        canonical["requirement_id"] = req_id
        canonical["prediction_source_type"] = "NEW_AUTHORIZED_RUN"
        canonical["prediction_sample_id"] = row["sample_id"]
        canonical["request_ordinal"] = ordinal
        canonical["raw_response_path"] = _rel(raw_path)
        canonical["raw_response_sha256"] = raw_doc.get("raw_response_body_sha256")
        canonical["response_model"] = decode.get("model")
        canonical["usage"] = decode.get("usage") or {}
        canonical["estimated_cost_usd"] = ledger_row.get("estimated_cost_usd")
        new_rows.append(canonical)

    new_predictions = {
        "schema_version": "stage3_table3_r5_ours_stage2_new19_predictions@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "method_id": "ours_direct_llm_stage2",
        "model": MODEL,
        "record_count": len(new_rows),
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": new_rows,
    }
    new_predictions_path = OUT_DIR / "predictions.json"
    _write_json_atomic(new_predictions_path, new_predictions)

    failed_canonical = [r for r in new_rows if r.get("request_status") != "ok"]
    if failed_canonical:
        _write_json_atomic(BLOCKED_PATH, {
            "schema_version": "stage3_table3_r5_api_execution_blocked@1.0.0",
            "status": "CANONICALIZATION_FAILURE_AFTER_API",
            "failed_requirement_ids": [r["requirement_id"] for r in failed_canonical],
            "new_predictions_path": _rel(new_predictions_path),
            "new_predictions_sha256": _sha_file(new_predictions_path),
            "ledger_path": _rel(LEDGER_PATH),
            "retries": 0,
            "timestamp_utc": _utc_now(),
        })
        return {**api_report, "status": "canonicalization_failed", "failed_canonical": [r["requirement_id"] for r in failed_canonical]}

    # Historical reuse records from the frozen reuse verification report.
    reuse = _load_json(REUSE)
    historical: dict[str, dict[str, Any]] = {}
    for row in reuse.get("rows") or []:
        if not row.get("core_eligible"):
            continue
        ours = row.get("ours") or {}
        if ours.get("status") != "verified":
            continue
        req_id = row["requirement_id"]
        pred_path = ROOT / ours["prediction_path"]
        pred_doc = _load_json(pred_path)
        sample_id = ours["prediction_sample_id"]
        record_env = next((r for r in pred_doc.get("records") or [] if str(r.get("sample_id")) == str(sample_id)), None)
        if record_env is None:
            raise ApiRunError(f"historical prediction record not found: {req_id}/{sample_id}")
        historical[req_id] = {
            "requirement_id": req_id,
            "prediction_source_type": ours.get("reuse_evidence_strength"),
            "prediction_sample_id": sample_id,
            "prediction_artifact": _rel(pred_path),
            "prediction_artifact_sha256": _sha_file(pred_path),
            "record": record_env.get("record"),
            "request_status": record_env.get("request_status"),
            "canonical_validation_status": "passed_historical_reuse",
            "reuse_evidence": ours.get("evidence") or {},
        }

    new_by_requirement = {r["requirement_id"]: r for r in new_rows}
    combined_records = []
    for req_id in [r["requirement_id"] for r in frozen["requests"]]:
        if req_id in historical:
            source_type = historical[req_id]["prediction_source_type"]
            if source_type not in ("STRONG_REUSE", "HISTORICAL_CHAIN_REUSE"):
                raise ApiRunError(f"unexpected historical strength for {req_id}: {source_type}")
            combined_records.append(historical[req_id])
        elif req_id in new_by_requirement:
            combined_records.append(new_by_requirement[req_id])
        else:
            raise ApiRunError(f"missing prediction for {req_id}")
    # Add the 14 historical requirements that are not new requests.
    for req_id, row in historical.items():
        if req_id not in {r["requirement_id"] for r in combined_records}:
            combined_records.append(row)
    if len(combined_records) != 33:
        raise ApiRunError(f"combined Ours prediction count != 33: {len(combined_records)}")
    # Deterministic order: new request order first, then historical non-new in requirement order is not ideal;
    # use frozen benchmark config order instead.
    config = _load_json(ROOT / "configs/stage3_table3_r5_benchmark_v2.json")
    core_ids = [r["requirement_id"] for r in config["requirements"] if r.get("core_eligible")]
    by_id = {r["requirement_id"]: r for r in combined_records}
    combined_records = [by_id[req_id] for req_id in core_ids]

    combined = {
        "schema_version": "stage3_table3_r5_ours_stage2_predictions@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "method_id": "ours_direct_llm_stage2",
        "record_count": len(combined_records),
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": combined_records,
    }
    COMBINED_DIR.mkdir(parents=True, exist_ok=True)
    combined_path = COMBINED_DIR / "predictions.json"
    _write_json_atomic(combined_path, combined)
    combined_sha = _sha_file(combined_path)

    # Count canonicalization outcomes for the new 19.
    valid = degraded = malformed = empty = coordinate_reanchored = 0
    for row in new_rows:
        audit = row.get("canonicalizer_audit") or {}
        if int(audit.get("reanchored_count") or 0) > 0:
            coordinate_reanchored += 1
        if row.get("request_status") != "ok":
            malformed += 1
            continue
        if row.get("canonical_validation_status") != "passed":
            malformed += 1
            continue
        if not ((row.get("record") or {}).get("clauses") or []):
            empty += 1
        if audit.get("status") == "degraded":
            degraded += 1
        else:
            valid += 1
    strength_counts = {
        "STRONG_REUSE": sum(1 for r in combined_records if r.get("prediction_source_type") == "STRONG_REUSE"),
        "HISTORICAL_CHAIN_REUSE": sum(1 for r in combined_records if r.get("prediction_source_type") == "HISTORICAL_CHAIN_REUSE"),
        "NEW_AUTHORIZED_RUN": sum(1 for r in combined_records if r.get("prediction_source_type") == "NEW_AUTHORIZED_RUN"),
    }
    if strength_counts != {"STRONG_REUSE": 5, "HISTORICAL_CHAIN_REUSE": 9, "NEW_AUTHORIZED_RUN": 19}:
        raise ApiRunError(f"reuse strength counts drift: {strength_counts}")

    manifest = {
        "schema_version": "stage3_table3_r5_ours_prediction_manifest@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "OURS_STAGE2_FORMAL_CANDIDATE_BEFORE_FREEZE",
        "method_id": "ours_direct_llm_stage2",
        "model": MODEL,
        "prompt_sha256": EXPECTED_PROMPT_SHA,
        "payload_manifest_sha256": EXPECTED_PAYLOAD_SHA,
        "combined_predictions": {
            "path": _rel(combined_path),
            "sha256": combined_sha,
            "record_count": len(combined_records),
        },
        "reuse_strength_counts": strength_counts,
        "new_run_canonicalization": {
            "valid": valid,
            "degraded": degraded,
            "malformed_or_failed": malformed,
            "empty": empty,
            "coordinate_reanchored": coordinate_reanchored,
            "new_prediction_capsule": {
                "path": _rel(new_predictions_path),
                "sha256": _sha_file(new_predictions_path),
            },
        },
        "records": [
            {
                "requirement_id": r["requirement_id"],
                "prediction_source_type": r.get("prediction_source_type"),
                "prediction_sample_id": r.get("prediction_sample_id"),
                "prediction_artifact": r.get("prediction_artifact", _rel(new_predictions_path)),
                "prediction_artifact_sha256": r.get("prediction_artifact_sha256", _sha_file(new_predictions_path)),
                "record_sha256": _sha_text(json.dumps(r.get("record"), ensure_ascii=False, sort_keys=True)),
                "request_status": r.get("request_status"),
                "canonical_validation_status": r.get("canonical_validation_status", "passed"),
                "canonicalizer_audit": r.get("canonicalizer_audit"),
                "model": MODEL if r.get("prediction_source_type") == "NEW_AUTHORIZED_RUN" else None,
                "prompt_sha256": EXPECTED_PROMPT_SHA if r.get("prediction_source_type") == "NEW_AUTHORIZED_RUN" else None,
            }
            for r in combined_records
        ],
        "api_execution_manifest": {
            "path": _rel(API_REPORT_PATH),
            "sha256": _sha_file(API_REPORT_PATH),
            "attempted": attempted,
            "completed": completed,
            "failed": failed,
            "retries": 0,
            "estimated_cost_usd": round(actual_cost, 8),
        },
        "gold_read": False,
        "timestamp_utc": _utc_now(),
    }
    _write_json_atomic(OURS_MANIFEST_PATH, manifest)

    freeze = {
        "schema_version": "stage3_table3_r5_ours_prediction_freeze@1.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "FROZEN_BEFORE_STAGE3_METRIC",
        "ours_prediction_manifest": {
            "path": _rel(OURS_MANIFEST_PATH),
            "sha256": _sha_file(OURS_MANIFEST_PATH),
        },
        "combined_predictions": {
            "path": _rel(combined_path),
            "sha256": combined_sha,
            "record_count": len(combined_records),
        },
        "reuse_strength_counts": strength_counts,
        "expected_counts": {
            "core_predictions": 33,
            "historical_strong_reuse": 5,
            "historical_chain_reuse": 9,
            "new_authorized_run": 19,
        },
        "post_freeze_repair_forbidden": True,
        "frozen_utc": _utc_now(),
    }
    _write_json_atomic(OURS_FREEZE_PATH, freeze)
    return {**api_report, "status": "completed_with_frozen_ours_predictions",
            "combined_predictions": {"path": _rel(combined_path), "sha256": combined_sha},
            "ours_manifest": {"path": _rel(OURS_MANIFEST_PATH), "sha256": _sha_file(OURS_MANIFEST_PATH)},
            "ours_freeze": {"path": _rel(OURS_FREEZE_PATH), "sha256": _sha_file(OURS_FREEZE_PATH)}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not (args.check_only or args.execute):
        parser.error("choose --check-only or --execute")
    if args.check_only:
        result = execute(api_key=None, check_only=True)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("api_key_present") else 3
    try:
        result = execute(api_key=_env_api_key(), check_only=False)
    except ApiRunError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc),
                          "network_calls_to_llm_api": 0,
                          "env_file_read": False}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(result.get("status", "")).startswith("completed") else 4


if __name__ == "__main__":
    raise SystemExit(main())

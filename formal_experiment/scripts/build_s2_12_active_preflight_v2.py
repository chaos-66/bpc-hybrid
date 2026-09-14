# -*- coding: utf-8 -*-
"""Build the successor S2.12 two-method (Direct-LLM-only) preflight.

The user cancelled Rules+LLM-Repair on 2026-09-14.  The historical v1
three-method lock/report remain byte-exact provenance, but they are no longer
the current execution scope.  This builder reconstructs the *same* 36 Direct-
LLM request bodies through the current code path with ``arms=('direct_llm',)``,
asserts byte-identical bodies against the historical v1 direct rows, and
publishes a direct-only successor lock/report binding the actual current
implementation files.

ZERO API / ZERO network.  This script never reads Gold, never opens .env, and
does not create a billing authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.s2_12_execution as ex  # noqa: E402

V1_LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"
V1_REPORT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"
ACTIVE_SCOPE = ROOT / "configs/s2_12_active_method_scope_v1.json"
LOCK_OUT = ROOT / "configs/s2_12_active_preflight_v2.json"
REPORT_OUT = ROOT / "outputs/reports/s2_12_active_preflight_v2.json"
PRICE_EVIDENCE = ROOT / "outputs/reports/sep_c2_execution_preflight_v1.json"

BINDING_PATHS = (
    "src/bpc_hybrid/s2_12_execution.py",
    "scripts/run_s2_12_direct_llm_v1.py",
    "scripts/run_direct_llm.py",
    "scripts/build_s2_12_api_preflight_v1.py",
    "src/bpc_hybrid/llm_client.py",
    "src/bpc_hybrid/h1_transport.py",
    "src/bpc_hybrid/prompt_loader.py",
    "src/bpc_hybrid/estg150_b0_development_v10.py",
    "src/bpc_hybrid/s2_12_method_adapter.py",
)


class ActivePreflightFail(ValueError):
    """Fail-closed successor preflight build error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _summary(values: Sequence[int]) -> dict[str, int]:
    if not values:
        return {"minimum": 0, "maximum": 0, "total": 0}
    return {"minimum": min(values), "maximum": max(values), "total": sum(values)}


def _implementation_bindings() -> dict[str, str]:
    for rel in BINDING_PATHS:
        if not (ROOT / rel).is_file():
            raise ActivePreflightFail(f"binding file missing: {rel}")
    return {rel: _sha(ROOT / rel) for rel in BINDING_PATHS}


def _price_evidence() -> dict[str, Any]:
    if not PRICE_EVIDENCE.is_file():
        raise ActivePreflightFail(
            "missing price-evidence report; cannot build active preflight")
    doc = json.loads(PRICE_EVIDENCE.read_text(encoding="utf-8"))
    prices = doc.get("price_reverification") or {}
    if prices.get("matches_existing_authorized_prices") is not True:
        raise ActivePreflightFail("price evidence is not a matching re-verification")
    return {
        "planning_only": True,
        "source_report": "outputs/reports/sep_c2_execution_preflight_v1.json",
        "source_report_sha256": _sha(PRICE_EVIDENCE),
        "official_source": prices.get("source"),
        "model": prices.get("model"),
        "published_alias": prices.get("published_alias"),
        "currency": "USD",
        "per_million_tokens": {
            "off_peak": prices.get("off_peak"),
            "peak": prices.get("peak"),
        },
        "actual_billing_requires_response_usage": True,
        "recheck_official_price_before_authorized_run": True,
        "this_is_not_a_price_guarantee": True,
    }


def _build_lock(report: Mapping[str, Any], scope: Mapping[str, Any],
                v1_lock: Mapping[str, Any]) -> dict[str, Any]:
    direct_spec = dict(v1_lock["arms"]["direct_llm"])
    direct_spec["max_calls"] = 36
    lock = {
        "schema_version": "s2_12_active_preflight_lock@2.0.0",
        "status": "locked_two_method_without_api_authorization",
        "locked_date": "2026-09-14",
        "scope_id": "sep_c2_two_method_v1",
        "active_methods": ["sun_rule_only", "direct_llm"],
        "cancelled_methods": ["sun_llm_fallback"],
        "cancelled_stages": ["F-1", "F-2", "F-3"],
        "cancelled_calls": 27,
        "cancelled_calls_reassigned": False,
        "dataset_id": v1_lock["dataset_id"],
        "input": dict(v1_lock["input"]),
        "locked_b0_predictions": dict(v1_lock["locked_b0_predictions"]),
        "provider": dict(v1_lock["provider"]),
        "common_sampling": dict(v1_lock["common_sampling"]),
        "arms": {"direct_llm": direct_spec},
        "global_caps": {
            "max_calls": 36,
            "max_output_tokens": 36 * int(v1_lock["common_sampling"]["max_output_tokens_per_call"]),
            "retry_count": 0,
        },
        "pricing": _price_evidence(),
        "gold_isolation": dict(v1_lock["gold_isolation"]),
        "hard_stops": list(v1_lock["hard_stops"]) + [
            "cancelled Rules+LLM-Repair arm F-1/F-2/F-3 must not run or be reassigned",
        ],
        "authorization": {
            "real_api_calls_allowed_by_this_lock": False,
            "pending_explicit_user_decisions": [
                "exact successor two-method API authorization sentence",
                "total billed input-token cap",
                "total USD cost cap",
            ],
            "existing_137_confirmation_scope_superseded": True,
            "current_cancellation_is_not_external_send_authorization": True,
            "automatic_external_transmission_approval_blocker_active": True,
        },
        "active_method_scope_sha256": _sha(ACTIVE_SCOPE),
        "implementation_bindings": _implementation_bindings(),
        "cancelled_arm": {
            "method_id": "sun_llm_fallback",
            "paper_label": "Rules+LLM-Repair",
            "historical_provenance_only": True,
            "must_not_run": True,
            "must_not_be_reassigned": True,
        },
    }
    lock["report_binding"] = {
        "path": "outputs/reports/s2_12_active_preflight_v2.json",
        "rebuilt_from": "historical_v1_direct_rows_byte_identical",
        "direct_payloads": len(report["arms"]["direct_llm"]["calls"]),
        "historical_v1_report_sha256": _sha(V1_REPORT),
    }
    return lock


def build(runtime_home: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    # 1) historical source, kept byte-exact and never rewritten
    for path in (V1_LOCK, V1_REPORT, ACTIVE_SCOPE, PRICE_EVIDENCE):
        if not path.is_file():
            raise ActivePreflightFail(f"required source missing: {path}")
    v1_lock = json.loads(V1_LOCK.read_text(encoding="utf-8"))
    v1_report = json.loads(V1_REPORT.read_text(encoding="utf-8"))
    scope = json.loads(ACTIVE_SCOPE.read_text(encoding="utf-8"))

    if v1_lock.get("status") != "locked_without_api_authorization":
        raise ActivePreflightFail("historical v1 lock status drift")
    if v1_report.get("status") != "payloads_locked_zero_api_authorization_pending":
        raise ActivePreflightFail("historical v1 report status drift")
    if scope.get("active_methods") != ["sun_rule_only", "direct_llm"]:
        raise ActivePreflightFail("active method scope is not two-method")
    if "sun_llm_fallback" not in (scope.get("cancelled_methods") or {}):
        raise ActivePreflightFail("active method scope does not cancel fallback")

    # 2) reconstruct the actual current direct bodies through the active code
    rows = ex.rebuild_and_verify_payloads(
        v1_lock, v1_report, runtime_home, arms=("direct_llm",))
    direct_rows = rows.get("direct_llm") or []
    if len(direct_rows) != 36:
        raise ActivePreflightFail("active direct rebuild did not yield 36 rows")

    v1_direct = {int(row["call_index"]): row
                 for row in v1_report["arms"]["direct_llm"]["calls"]}
    calls: list[dict[str, Any]] = []
    for row in direct_rows:
        index = int(row["call_index"])
        expected = v1_direct.get(index)
        if expected is None:
            raise ActivePreflightFail(f"v1 direct row {index} missing")
        if expected.get("request_body_sha256") != row["request_body_sha256"]:
            raise ActivePreflightFail(
                f"direct call {index} body SHA drift against historical v1: "
                f"{row['request_body_sha256'][:12]} != "
                f"{expected.get('request_body_sha256', '?')[:12]}")
        if expected.get("request_body_utf8_bytes") != row["request_body_utf8_bytes"]:
            raise ActivePreflightFail(f"direct call {index} byte-size drift")
        proxy = expected.get("local_proxy_tokens")
        if not isinstance(proxy, int) or proxy <= 0:
            raise ActivePreflightFail(f"direct call {index} local proxy count missing")
        calls.append({
            "call_index": index,
            "sample_id": row["sample_id"],
            "clause_id": None,
            "request_body_sha256": row["request_body_sha256"],
            "request_body_utf8_bytes": row["request_body_utf8_bytes"],
            "system_prompt_utf8_bytes": expected.get("system_prompt_utf8_bytes"),
            "user_prompt_utf8_bytes": expected.get("user_prompt_utf8_bytes"),
            "local_proxy_tokens": proxy,
            "historical_v1_row_sha256": _sha_bytes(json.dumps(
                expected, ensure_ascii=False, sort_keys=True).encode("utf-8")),
        })

    direct_arm = {
        "prompt_name": v1_lock["arms"]["direct_llm"]["prompt_name"],
        "prompt_sha256": v1_lock["arms"]["direct_llm"]["prompt_sha256"],
        "transport_policy": dict(v1_lock["arms"]["direct_llm"]["transport_policy"]),
        "planned_calls": 36,
        "max_calls": 36,
        "max_output_tokens_per_call": 4096,
        "max_output_tokens_total": 36 * 4096,
        "retry_count": 0,
        "request_body_utf8_bytes": _summary(
            [row["request_body_utf8_bytes"] for row in calls]),
        "local_proxy_tokens": _summary(
            [row["local_proxy_tokens"] for row in calls]),
        "calls": calls,
        "historical_v1_direct_rows_byte_identical": True,
    }

    body_summary = _summary([row["request_body_utf8_bytes"] for row in calls])
    proxy_summary = _summary([row["local_proxy_tokens"] for row in calls])
    report = {
        "schema_version": "s2_12_active_preflight_report@2.0.0",
        "status": "payloads_locked_two_method_no_api_authorization",
        "report_id": "s2_12_active_preflight_v2",
        "scope_id": "sep_c2_two_method_v1",
        "active_methods": ["sun_rule_only", "direct_llm"],
        "cancelled_methods": ["sun_llm_fallback"],
        "supersedes": {
            "historical_v1_lock": {
                "path": "configs/s2_12_api_arms_preflight_v1.json",
                "sha256": _sha(V1_LOCK),
            },
            "historical_v1_report": {
                "path": "outputs/reports/s2_12_api_preflight_v1.json",
                "sha256": _sha(V1_REPORT),
            },
            "reason": ("historical three-method payload lock/report remain "
                       "provenance; their cancelled 27 fallback calls are not "
                       "part of the current execution scope"),
        },
        "preflight_lock": {
            "path": "configs/s2_12_active_preflight_v2.json",
            "sha256": None,
        },
        "input": {
            "path": v1_lock["input"]["path"],
            "sha256": v1_lock["input"]["sha256"],
            "records": 36,
            "gold_blind": True,
            "raw_text_committed": False,
        },
        "model": {
            "provider": v1_lock["provider"]["kind"],
            "base_url": v1_lock["provider"]["base_url"],
            "id": v1_lock["provider"]["model"],
            "fail_closed": True,
            "common_sampling": dict(v1_lock["common_sampling"]),
            "implementation_bindings": _implementation_bindings(),
        },
        "token_measurement": {
            "exact_measurement": "final request body serialized by default json.dumps then UTF-8",
            "official_deepseek_v4_pro_tokenizer_available_locally": False,
            "official_billing_input_tokens": None,
            "official_billing_input_tokens_status": "available only from response usage after a real call",
            "local_proxy": {
                "model_id": v1_lock["local_tokenizer_proxy"]["model_id"],
                "revision": v1_lock["local_tokenizer_proxy"]["revision"],
                "kind": v1_lock["local_tokenizer_proxy"]["kind"],
                "is_deepseek_tokenizer": False,
                "is_billing_token_count": False,
                "values_reused_from_v1_by_matching_body_sha256": True,
                "note": ("the 36 direct bodies are byte-identical to the "
                         "historical v1 direct bodies, so the validated "
                         "historical proxy counts are still the bound planning "
                         "proxy for those exact bodies"),
            },
        },
        "arms": {"direct_llm": direct_arm},
        "global": {
            "planned_calls": 36,
            "configured_hard_call_cap": 36,
            "retry_count": 0,
            "request_body_utf8_bytes": {
                "maximum_per_call": body_summary["maximum"],
                "total": body_summary["total"],
            },
            "local_proxy_tokens": {
                "maximum_per_call": proxy_summary["maximum"],
                "total": proxy_summary["total"],
            },
            "max_output_tokens_per_call": 4096,
            "max_output_tokens_total": 36 * 4096,
        },
        "pricing": _price_evidence(),
        "authorization": {
            "real_api_calls_made": 0,
            "real_api_calls_authorized": False,
            "this_report_is_not_an_authorization": True,
            "existing_137_confirmation_scope_superseded": True,
            "current_cancellation_is_not_external_send_authorization": True,
            "pending": [
                "exact successor two-method API authorization sentence",
                "explicit total input-token cap",
                "explicit total USD cost cap",
                "external transmission approval",
            ],
            "recommended_planning_limits": {
                "max_calls": 36,
                "max_request_body_utf8_bytes_per_call": body_summary["maximum"],
                "max_request_body_utf8_bytes_total": body_summary["total"],
                "max_output_tokens_per_call": 4096,
                "max_output_tokens_total": 36 * 4096,
                "retry_count": 0,
            },
            "hard_stops": list(v1_lock["hard_stops"]),
        },
        "cancelled_arm": {
            "method_id": "sun_llm_fallback",
            "paper_label": "Rules+LLM-Repair",
            "cancelled_stages": ["F-1", "F-2", "F-3"],
            "cancelled_calls": 27,
            "calls_reassigned": False,
            "historical_provenance_only": True,
            "will_not_run_or_be_evaluated": True,
            "must_not_be_reintroduced_under_another_name": True,
        },
        "active_method_scope": {
            "path": "configs/s2_12_active_method_scope_v1.json",
            "sha256": _sha(ACTIVE_SCOPE),
            "active_methods": ["sun_rule_only", "direct_llm"],
            "cancelled_methods": ["sun_llm_fallback"],
            "remaining_calls": {"s2_12_direct": 36, "gdpr7_direct": 74,
                                "total": 110},
        },
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "raw_payload_or_source_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command": (
            "python formal_experiment/scripts/build_s2_12_active_preflight_v2.py "
            "--runtime-home D:/environment/stanford-corenlp-4.5.10 --check"
        ),
    }
    lock = _build_lock(report, scope, v1_lock)
    report["preflight_lock"]["sha256"] = _sha_bytes(_json_bytes(lock))
    # Validate the shape through the same active loaders before publishing.
    return lock, report


def _publish(lock: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    if LOCK_OUT.exists() or REPORT_OUT.exists():
        raise ActivePreflightFail(
            "refusing to overwrite existing successor preflight; publish a "
            "later successor version instead"
        )
    LOCK_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    lock_bytes = _json_bytes(lock)
    report_bytes = _json_bytes(report)
    lock_stage = LOCK_OUT.with_suffix(f".tmp-{os.getpid()}")
    report_stage = REPORT_OUT.with_suffix(f".tmp-{os.getpid()}")
    lock_stage.write_bytes(lock_bytes)
    report_stage.write_bytes(report_bytes)
    lock_stage.replace(LOCK_OUT)
    try:
        report_stage.replace(REPORT_OUT)
    except Exception:
        LOCK_OUT.unlink(missing_ok=True)
        report_stage.unlink(missing_ok=True)
        raise


def _check(lock: Mapping[str, Any], report: Mapping[str, Any]) -> None:
    for path, expected in ((LOCK_OUT, _json_bytes(lock)), (REPORT_OUT, _json_bytes(report))):
        if not path.is_file() or path.read_bytes() != expected:
            raise ActivePreflightFail(f"published successor preflight differs: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        lock, report = build(args.runtime_home)
        if args.check:
            _check(lock, report)
        else:
            _publish(lock, report)
    except (OSError, ValueError) as exc:
        print(f"S2.12 active two-method preflight refused: {exc}")
        return 2
    print(
        "S2.12 active two-method preflight verified: direct_llm=36, "
        "fallback_cancelled=27, llm_api_calls=0, network_calls=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

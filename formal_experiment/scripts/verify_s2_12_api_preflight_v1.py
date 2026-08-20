# -*- coding: utf-8 -*-
"""Independent, zero-call verifier for the S2.12 API preflight v1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"
LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"
SCHEMA = ROOT / "configs/schemas/s2_12_api_preflight_v1.schema.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contains_forbidden_payload(value: Any) -> bool:
    forbidden = {
        "source_text", "approved_text_en", "raw_text_de", "system_prompt",
        "user_prompt", "messages", "body", "gold", "decisions", "proposals",
    }
    if isinstance(value, dict):
        return any(
            str(key).lower() in forbidden or _contains_forbidden_payload(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_payload(child) for child in value)
    return False


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        expected_top = set(schema["required"])
        check(
            "report validates against strict top-level schema",
            set(report) == expected_top
            and report.get("schema_version") == "s2_12_api_preflight_report@1.0.0"
            and set(report.get("arms", {})) == {"direct_llm", "sun_llm_fallback"},
        )
    except Exception as exc:
        check("report validates against strict top-level schema", False, str(exc))
        return {"verified": False, "checks": checks}

    check("lock binding", report["preflight_lock"] == {
        "path": "configs/s2_12_api_arms_preflight_v1.json", "sha256": _sha(LOCK)})
    check("status is authorization-pending", report["status"] == "payloads_locked_zero_api_authorization_pending")
    check("lock itself authorizes no API", lock["authorization"]["real_api_calls_allowed_by_this_lock"] is False)
    check("Gold isolation", all(report["gold_isolation"].get(key) is False for key in (
        "preflight_reads_gold", "preflight_reads_decisions", "preflight_reads_proposals")))
    check("no prompt/source/Gold payload committed", not _contains_forbidden_payload(report))

    for rel, expected in lock["implementation_bindings"].items():
        path = ROOT / rel
        check(f"implementation binding {rel}", path.is_file() and _sha(path) == expected)
    input_path = ROOT / lock["input"]["path"]
    predictions_path = ROOT / lock["locked_b0_predictions"]["path"]
    check("input binding", input_path.is_file() and _sha(input_path) == lock["input"]["sha256"])
    check("prediction binding", predictions_path.is_file() and _sha(predictions_path) == lock["locked_b0_predictions"]["sha256"])

    direct = report["arms"]["direct_llm"]
    h1 = report["arms"]["sun_llm_fallback"]
    check("direct payload count is 36/36", direct["planned_calls"] == len(direct["calls"]) == direct["max_calls"] == 36)
    check("H1 payload count within 72-call cap", h1["planned_calls"] == len(h1["calls"]) == 27 and h1["max_calls"] == 72)
    all_calls = direct["calls"] + h1["calls"]
    check("global call count", report["global"]["planned_calls"] == len(all_calls) == 63)
    check("configured cap and zero retries", report["global"]["configured_hard_call_cap"] == 108 and report["global"]["retry_count"] == 0)
    check("unique request bodies", len({row["request_body_sha256"] for row in all_calls}) == len(all_calls))

    for arm_name, arm in report["arms"].items():
        byte_values = [row["request_body_utf8_bytes"] for row in arm["calls"]]
        token_values = [row["local_proxy_tokens"] for row in arm["calls"]]
        check(f"{arm_name} byte aggregate", arm["request_body_utf8_bytes"] == {
            "minimum": min(byte_values), "maximum": max(byte_values), "total": sum(byte_values)})
        check(f"{arm_name} proxy aggregate", arm["local_proxy_tokens"] == {
            "minimum": min(token_values), "maximum": max(token_values), "total": sum(token_values)})
        check(f"{arm_name} output cap", arm["max_output_tokens_total"] == len(arm["calls"]) * 4096)
        check(f"{arm_name} prompt binding", arm["prompt_sha256"] == lock["arms"][arm_name]["prompt_sha256"])

    byte_total = sum(row["request_body_utf8_bytes"] for row in all_calls)
    proxy_total = sum(row["local_proxy_tokens"] for row in all_calls)
    output_total = len(all_calls) * 4096
    check("global exact byte aggregate", report["global"]["request_body_utf8_bytes"] == {
        "maximum_per_call": max(row["request_body_utf8_bytes"] for row in all_calls), "total": byte_total})
    check("global proxy aggregate", report["global"]["local_proxy_tokens"] == {
        "maximum_per_call": max(row["local_proxy_tokens"] for row in all_calls), "total": proxy_total})
    check("global output cap", report["global"]["max_output_tokens_total"] == output_total)
    check("DeepSeek exact tokens honestly unavailable", report["token_measurement"]["official_deepseek_v4_pro_tokenizer_available_locally"] is False and report["token_measurement"]["official_billing_input_tokens"] is None and report["token_measurement"]["local_proxy"]["is_billing_token_count"] is False)

    price = report["pricing"]["per_million_tokens"]
    check("official pinned rates", price == {"input_cache_hit": 0.003625, "input_cache_miss": 0.435, "output": 0.87})
    proxy_plan = report["pricing"]["proxy_based_planning_only_not_billable_exact"]
    check("proxy cache-miss arithmetic", math.isclose(proxy_plan["all_input_cache_miss_usd"], proxy_total * price["input_cache_miss"] / 1_000_000))
    check("maximum output cost arithmetic", math.isclose(proxy_plan["max_output_usd"], output_total * price["output"] / 1_000_000))
    absolute = report["pricing"]["official_context_derived_absolute_bound"]
    expected_absolute = absolute["input_tokens"] * price["input_cache_miss"] / 1_000_000 + output_total * price["output"] / 1_000_000
    check("absolute cost bound arithmetic", math.isclose(absolute["cache_miss_input_plus_max_output_usd"], expected_absolute) and absolute["recommended_rounded_hard_cost_cap_usd"] == math.ceil(expected_absolute * 100) / 100)
    check("actual cost remains null", report["pricing"]["actual_cost_usd"] is None)

    limits = report["authorization"]["recommended_hard_limits"]
    check("recommended limits bind payload", limits["max_calls"] == 63 and limits["max_request_body_utf8_bytes_per_call"] == max(row["request_body_utf8_bytes"] for row in all_calls) and limits["max_request_body_utf8_bytes_total"] == byte_total)
    check("recommended token/cost limits bind conservative bound", limits["max_billed_input_tokens_total"] == absolute["input_tokens"] and limits["max_cost_usd"] == absolute["recommended_rounded_hard_cost_cap_usd"])
    check("no API/GRR/Oracle", report["safety"] == {
        "llm_api_calls": 0, "network_calls": 0,
        "raw_payload_or_source_text_committed": False,
        "gold_rule_records_created": False, "oracle_started": False})
    return {"verified": all(item["ok"] for item in checks), "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for item in result["checks"]:
            print(("PASS" if item["ok"] else "FAIL"), item["name"], item["detail"])
        print("S2.12 API PREFLIGHT VERIFIED (ZERO CALLS)" if result["verified"] else "S2.12 API PREFLIGHT NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

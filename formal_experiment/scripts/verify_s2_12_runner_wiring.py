# -*- coding: utf-8 -*-
"""Independent verifier for the S2.12 runner-wiring batch (zero API).

Runs offline and never touches Gold, decisions, proposals, Oracle, or Gold
Rule Records; never reads ``.env``; never opens a network socket.  It checks
that the new runner wiring and its assets are consistent with the locked
preflight contract, and that the committed state still says
``RUNNER READY / API NOT AUTHORIZED / ZERO CALLS``.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
PREFLIGHT_LOCK = ROOT / "configs/s2_12_api_arms_preflight_v1.json"
PREFLIGHT_REPORT = ROOT / "outputs/reports/s2_12_api_preflight_v1.json"
FROZEN_PLAN = ROOT / "configs/s2_12_fallback_trigger_plan_v1.json"
AUTH_SCHEMA = ROOT / "configs/schemas/s2_12_api_authorization_v1.schema.json"
EXPECTED_INPUT_SHA = "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e"

NEW_ASSETS = (
    "src/bpc_hybrid/s2_12_execution.py",
    "scripts/run_s2_12_direct_llm_v1.py",
    "scripts/run_s2_12_sun_llm_fallback_v1.py",
    "scripts/build_s2_12_fallback_trigger_plan_v1.py",
    "configs/s2_12_fallback_trigger_plan_v1.json",
    "configs/schemas/s2_12_api_authorization_v1.schema.json",
)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    # 1) All new assets exist.
    for rel in NEW_ASSETS:
        check(f"asset_present:{rel}", (ROOT / rel).is_file())

    # 2) Preflight lock/report/input identities.
    check("input_sha", _sha_file(INPUT) == EXPECTED_INPUT_SHA)
    lock = json.loads(PREFLIGHT_LOCK.read_text(encoding="utf-8"))
    check(
        "lock_status",
        lock.get("status") == "locked_without_api_authorization",
        lock.get("status"),
    )
    check(
        "lock_no_api_authorization",
        lock.get("authorization", {}).get("real_api_calls_allowed_by_this_lock")
        is False,
    )
    report = json.loads(PREFLIGHT_REPORT.read_text(encoding="utf-8"))
    check(
        "report_payloads_locked",
        report.get("status") == "payloads_locked_zero_api_authorization_pending",
    )
    check("report_calls_63", report["global"]["planned_calls"] == 63)
    check("report_direct_36", report["arms"]["direct_llm"]["planned_calls"] == 36)
    check(
        "report_fallback_27",
        report["arms"]["sun_llm_fallback"]["planned_calls"] == 27,
    )
    check("report_zero_calls", report["safety"]["llm_api_calls"] == 0)

    # 3) Frozen plan identity: 27 entries, retry 0, no text.
    plan = json.loads(FROZEN_PLAN.read_text(encoding="utf-8"))
    check("plan_27", len(plan.get("selected_plans", [])) == 27)
    check("plan_retry_0", plan.get("retry") == 0)
    check(
        "plan_no_text",
        "source_text" not in json.dumps(plan).lower()
        and '"text"' not in json.dumps(plan),
    )
    # Every frozen entry body SHA must appear in the locked report fallback set.
    report_fb = {c["request_body_sha256"] for c in report["arms"]["sun_llm_fallback"]["calls"]}
    plan_shas = {e["request_body_sha256"] for e in plan["selected_plans"]}
    check("plan_shas_subset_of_report", plan_shas <= report_fb)

    # 4) Authorization schema present with the required field set.
    schema = json.loads(AUTH_SCHEMA.read_text(encoding="utf-8"))
    check(
        "auth_schema_fields",
        {
            "schema_version", "authorization_sentence_utf8_sha256",
            "authorization_event_file", "authorization_event_file_sha256",
            "model", "calls", "payload_hashes", "retry",
            "input_token_cap", "output_token_cap", "usd_cost_cap",
            "allowed_windows", "price_snapshot", "price_checked_at_utc",
            "runner_implementation_hashes", "input_config_prompt_hashes",
            "gold_isolation",
        } == set(schema.get("required", [])),
    )

    # 5) No real authorization file exists; zero calls state preserved.
    check(
        "no_real_auth_file",
        not (ROOT / "configs/s2_12_api_authorization_v1.json").exists(),
    )

    # 6) Shared module is network-free by import surface.
    shared = (ROOT / "src/bpc_hybrid/s2_12_execution.py").read_text(encoding="utf-8")
    check(
        "shared_no_netimport",
        all(
            token not in shared
            for token in (
                "import requests", "import httpx", "import openai",
                "from urllib.request", "import urllib.request",
            )
        ),
    )

    verified = all(item["ok"] for item in checks)
    return {
        "schema_version": "s2_12_runner_wiring_verify@1.0.0",
        "verified": verified,
        "asset_hashes": {rel: _sha_file(ROOT / rel) for rel in NEW_ASSETS},
        "checks": checks,
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
            "real_authorization_file_created": False,
        },
    }


def main() -> int:
    try:
        result = verify()
    except (OSError, ValueError, KeyError) as exc:
        print(f"S2.12 runner-wiring verifier failed: {exc}")
        return 2
    for item in result["checks"]:
        mark = "PASS" if item["ok"] else "FAIL"
        print(f"{mark} {item['name']} {item['detail']}")
    print(
        "S2.12 RUNNER WIRING "
        + ("VERIFIED" if result["verified"] else "FAILED")
        + " (ZERO CALLS)"
    )
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
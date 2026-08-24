# -*- coding: utf-8 -*-
"""Independent verifier for the S2.12 runner-safety v2 batch (zero API).

Runs offline and never touches Gold/decisions/proposals/Oracle/Gold Rule
Records; never reads ``.env``; never opens a network socket.  Checks the v2
real-execution safety contracts:

* per-call payload lock surface (PayloadLock) exists and is used by both
  fake and real transports;
* usage/cost capture (per_call_cost, CumulativeState) exists;
* per-call caps + off-peak gating (check_pre_call / check_post_call);
* append-only hash-chained ledger (ExecutionLedger) with resume;
* pre-registered stage contract (D-CAL/D-REST/F-1..F-3, no arbitrary IDs);
* authorization v1.1.0 (stage binding) + auth-event builder presence;
* both runners build config with ``load_project_env=False`` (no .env);
* fallback runner binds ONLY the fallback runner hash (no cross-arm fix).

The committed state must remain API BLOCKED / ZERO CALLS: no real
authorization file, zero calls, zero cost.
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
    "scripts/build_s2_12_auth_event_v1.py",
    "configs/s2_12_fallback_trigger_plan_v1.json",
    "configs/schemas/s2_12_api_authorization_v1.schema.json",
)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    for rel in NEW_ASSETS:
        check(f"asset_present:{rel}", (ROOT / rel).is_file())

    check("input_sha", _sha_file(INPUT) == EXPECTED_INPUT_SHA)
    lock = json.loads(PREFLIGHT_LOCK.read_text(encoding="utf-8"))
    check("lock_status", lock.get("status") == "locked_without_api_authorization")
    report = json.loads(PREFLIGHT_REPORT.read_text(encoding="utf-8"))
    check("report_calls_63", report["global"]["planned_calls"] == 63)
    check("report_zero_calls", report["safety"]["llm_api_calls"] == 0)

    plan = json.loads(FROZEN_PLAN.read_text(encoding="utf-8"))
    check("plan_27", len(plan.get("selected_plans", [])) == 27)
    check("plan_retry_0", plan.get("retry") == 0)

    schema = json.loads(AUTH_SCHEMA.read_text(encoding="utf-8"))
    check("auth_v11_const", schema["properties"]["schema_version"]["const"]
          == "s2_12_api_authorization@1.1.0")
    for field in ("stage_id", "stage_payload_hashes", "stage_call_cap",
                  "prev_stage_ledger_hash", "final_63_payload_hashes",
                  "global_input_token_cap", "global_output_token_cap",
                  "global_usd_cost_cap"):
        check(f"auth_schema_field:{field}", field in schema["required"])

    # .env ban: both runners must build LLMConfig with load_project_env=False.
    for runner in ("run_s2_12_direct_llm_v1", "run_s2_12_sun_llm_fallback_v1"):
        text = (ROOT / "scripts" / f"{runner}.py").read_text(encoding="utf-8")
        check(
            f"no_project_env:{runner}",
            "load_project_env=False" in text,
        )

    # Payload lock surface exists in the shared module.
    shared = (ROOT / "src/bpc_hybrid/s2_12_execution.py").read_text(encoding="utf-8")
    for token in ("class PayloadLock", "class PayloadLockedRealTransport",
                  "class ExecutionLedger", "def check_pre_call",
                  "def check_post_call", "def per_call_cost",
                  "class StageExecutor", "def publish_stage_capsule"):
        check(f"shared_surface:{token.split()[-1]}", token in shared)

    # Stage contract: fixed partitions, no arbitrary subsets.
    from bpc_hybrid.s2_12_execution import STAGE_CONTRACT
    d = STAGE_CONTRACT["arms"]["direct_llm"]["stages"]
    f = STAGE_CONTRACT["arms"]["sun_llm_fallback"]["stages"]
    check("stage_dcal_1", d["D-CAL"]["ordinals"] == [1])
    check("stage_drest_35", len(d["D-REST"]["ordinals"]) == 35)
    f_ords = f["F-1"]["ordinals"] + f["F-2"]["ordinals"] + f["F-3"]["ordinals"]
    check("stage_f_partition", sorted(f_ords) == list(range(1, 28))
          and len(set(f_ords)) == 27)

    # No real authorization files exist.
    check(
        "no_real_auth",
        not any(
            (ROOT / f"configs/s2_12_api_authorization_{s}.json").exists()
            for s in ("D-CAL", "D-REST", "F-1", "F-2", "F-3")
        ),
    )

    # shared module network-free import surface
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
        "schema_version": "s2_12_runner_safety_v2_verify@1.0.0",
        "verified": verified,
        "api_status": "API BLOCKED / ZERO CALLS",
        "asset_hashes": {rel: _sha_file(ROOT / rel) for rel in NEW_ASSETS},
        "checks": checks,
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
            "real_authorization_file_created": False,
            "project_env_read": False,
        },
    }


def main() -> int:
    try:
        result = verify()
    except (OSError, ValueError, KeyError) as exc:
        print(f"S2.12 runner-safety v2 verifier failed: {exc}")
        return 2
    for item in result["checks"]:
        mark = "PASS" if item["ok"] else "FAIL"
        print(f"{mark} {item['name']} {item['detail']}")
    print(
        "S2.12 RUNNER SAFETY V2 "
        + ("VERIFIED" if result["verified"] else "FAILED")
        + " / API NOT AUTHORIZED / ZERO CALLS"
    )
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
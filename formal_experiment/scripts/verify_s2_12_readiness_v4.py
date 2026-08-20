# -*- coding: utf-8 -*-
"""Independent verifier for S2.12 execution readiness v4."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "outputs/reports/s2_12_execution_readiness_v4.json"
SCHEMA = ROOT / "configs/schemas/s2_12_execution_readiness_v4.schema.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def check(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except Exception as exc:
        check("read report/schema", False, str(exc))
        return {"verified": False, "checks": checks}
    check("strict top-level schema", set(report) == set(schema["required"]))
    check("partial status", report["status"] == "partial_zero_api_arm_complete_api_arms_pending_authorization")
    check("S2.11 verified/frozen 36/36", report["s2_11"]["status"] == "verified_frozen" and report["s2_11"]["frozen"] is True and report["s2_11"]["adjudicated"] == 36 and report["s2_11"]["unresolved"] == 0)
    for section, names in (("s2_11", ("formal_gold", "formal_gold_manifest", "confirmation_event", "freeze_publication_capsule")),):
        for name in names:
            item = report[section][name]
            path = ROOT / item["path"]
            check(f"binding {section}.{name}", path.is_file() and _sha(path) == item["sha256"] and path.stat().st_size == item["byte_size"])
    zero = report["s2_12"]["sun_rule_only"]
    check("zero arm complete and bounded", zero["status"] == "verified_complete" and zero["single_zero_api_arm_only"] is True and zero["actual_cost_usd"] == 0.0)
    check("L1/L2/L3 counts", [zero["strata"][level]["samples"] for level in ("L1", "L2", "L3")] == [31, 5, 0])
    check("L3 no samples", zero["strata"]["L3"]["span_fields"] is None and "no samples" in zero["strata"]["L3"]["note"])
    check("API arms pending", report["s2_12"]["direct_llm"] == report["s2_12"]["sun_llm_fallback"] == "pending_explicit_api_authorization")
    check("not a full comparison/no tuning", report["s2_12"]["three_method_comparison_complete"] is False and report["s2_12"]["post_result_tuning_performed"] is False)
    check("preflight exact counts", report["api_preflight"]["planned_calls"] == 63 and report["api_preflight"]["direct_llm_calls"] == 36 and report["api_preflight"]["sun_llm_fallback_calls"] == 27)
    check("preflight exact bytes/proxy", report["api_preflight"]["request_body_utf8_bytes"] == {"maximum_per_call": 17493, "total": 749805} and report["api_preflight"]["local_proxy_tokens"] == {"maximum_per_call": 4960, "total": 207468})
    check("billing tokens/cost honestly unknown", report["api_preflight"]["official_billing_input_tokens"] is None and report["api_preflight"]["actual_cost_usd"] is None)
    check("downstream states", report["downstream"] == {"S2.13": "blocked_only_on_remaining_S2.12_DoD", "S3.4_S3.6": "development_only", "S3.7": "formal_oracle_not_started", "gold_rule_records": "absent"})
    check("authorization not granted", report["authorization"]["api_authorized"] is False and report["authorization"]["suggested_copyable_sentence_is_not_itself_authorization"] is True)
    check("zero API/GRR/Oracle", report["safety"]["new_llm_api_calls"] == 0 and report["safety"]["gold_rule_records_created"] is False and report["safety"]["oracle_started"] is False)
    for name, item in report["verifiers"].items():
        path = ROOT / item["path"]
        check(f"verifier binding {name}", path.is_file() and _sha(path) == item["sha256"] and item["verified"] is True and item["exit_code"] == 0)
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/s2_12_build_readiness_v4.py"), "--check"], cwd=ROOT.parent, capture_output=True, text=True)
    check("builder replay byte-identical", proc.returncode == 0, (proc.stderr or proc.stdout)[-500:])
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
        print("S2.12 READINESS V4 VERIFIED" if result["verified"] else "S2.12 READINESS V4 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

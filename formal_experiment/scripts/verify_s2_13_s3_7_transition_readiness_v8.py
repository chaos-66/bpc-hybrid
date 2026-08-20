# -*- coding: utf-8 -*-
"""Independent verifier for transition readiness v8."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v8.json"
MARKDOWN = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v8.md"
MANIFEST = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v8.manifest.json"
EXPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v8_export_index.json"
SCHEMA = ROOT / "configs/schemas/s2_13_s3_7_transition_readiness_v8.schema.json"
BUILDER = ROOT / "scripts/build_s2_13_s3_7_transition_readiness_v8.py"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_builder():
    spec = importlib.util.spec_from_file_location("transition_v8_builder", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def check(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
    try:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        export = json.loads(EXPORT.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except Exception as exc:
        check("read v8 artifacts", False, str(exc))
        return {"verified": False, "checks": checks}
    check("strict report top-level schema", set(report) == set(schema["required"]))
    check("pipeline state", report["pipeline_state"] == {
        "S1.7": "frozen", "S2.11": "verified_frozen",
        "S2.12": "partial_zero_api_arm_complete_api_arms_pending",
        "S2.13": "blocked_only_on_remaining_S2.12_DoD",
        "S3.4_S3.6": "development_only", "S3.7": "formal_oracle_not_started"})
    check("S2.11 formal Gold published", report["s2_11"]["status"] == "verified_frozen" and report["s2_11"]["adjudicated"] == 36 and report["s2_11"]["unresolved"] == 0)
    check("S2.12 exact scope", report["s2_12"]["status"] == "partial" and report["s2_12"]["sun_rule_only"]["status"] == "verified_complete" and report["s2_12"]["sun_rule_only"]["single_zero_api_arm_only"] is True and report["s2_12"]["three_method_comparison_complete"] is False and report["s2_12"]["post_result_tuning_performed"] is False)
    check("API arms pending", report["s2_12"]["direct_llm"] == report["s2_12"]["sun_llm_fallback"] == "pending_explicit_api_authorization")
    check("S2.13 only S2.12 blocker", report["s2_13"]["status"] == "blocked" and len(report["s2_13"]["blockers"]) == 1 and "S2.12" in report["s2_13"]["blockers"][0])
    check("Stage 3 development/Oracle boundary", all(report["stage3"][key] == "development_only" for key in ("S3.4", "S3.5", "S3.6")) and report["stage3"]["S3.7"]["status"] == "formal_oracle_not_started" and report["stage3"]["S3.7"]["authorized"] is False)
    check("Gold Rule Records absent", report["gold_rule_records"]["exist"] is False and report["gold_rule_records"]["candidate_probe_found"] == [])
    check("zero API/Oracle", report["safety"]["new_llm_api_calls"] == 0 and report["safety"]["oracle_started"] is False and report["safety"]["gold_rule_records_created"] is False)
    check("all eight v7 assets superseded and bound", len(report["supersedes"]) == 8 and all((ROOT / item["path"]).is_file() and _sha(ROOT / item["path"]) == item["sha256"] for item in report["supersedes"]))
    for rel, expected in manifest["bindings"].items():
        path = ROOT / rel
        check(f"manifest binding {rel}", path.is_file() and _sha(path) == expected)
    for name, item in manifest["artifacts"].items():
        path = ROOT / item["path"]
        check(f"manifest artifact {name}", path.is_file() and _sha(path) == item["sha256"] and path.stat().st_size == item["byte_size"])
    expected_export = {
        REPORT.relative_to(ROOT).as_posix(): {"sha256": _sha(REPORT), "byte_size": REPORT.stat().st_size},
        MARKDOWN.relative_to(ROOT).as_posix(): {"sha256": _sha(MARKDOWN), "byte_size": MARKDOWN.stat().st_size},
        MANIFEST.relative_to(ROOT).as_posix(): {"sha256": _sha(MANIFEST), "byte_size": MANIFEST.stat().st_size},
    }
    check("export exact reconstruction", export["files"] == expected_export)
    builder = _load_builder()
    try:
        history = builder.run_historical_verifiers()
        check("historical v1-v7 lifecycle matrix", history == report["historical_transition_verifiers"])
        expected = builder.build_artifacts(history)
        check("builder byte-identical replay", all(path.read_bytes() == payload for path, payload in expected.items()))
    except Exception as exc:
        check("historical v1-v7 lifecycle matrix", False, str(exc))
        check("builder byte-identical replay", False, str(exc))
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
        print("TRANSITION READINESS V8 VERIFIED" if result["verified"] else "TRANSITION READINESS V8 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

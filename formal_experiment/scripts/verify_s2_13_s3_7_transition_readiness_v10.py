# -*- coding: utf-8 -*-
"""Independent verifier for transition readiness v10.

It re-derives every current-state judgment from disk: the two-method contract
is replayed by its own builder, the Gold Rule Records verifier is re-executed,
the v10 builder is replayed byte-identically, and every binding/hash is
recomputed.  Historical v1-v9 capsules are bound, never re-executed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10.json"
MARKDOWN = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10.md"
MANIFEST = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10.manifest.json"
EXPORT = ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v10_export_index.json"
SCHEMA = ROOT / "configs/schemas/s2_13_s3_7_transition_readiness_v10.schema.json"
BUILDER = ROOT / "scripts/build_s2_13_s3_7_transition_readiness_v10.py"
TWO_METHOD_CONTRACT = ROOT / "outputs/reports/s2_12_two_method_contract_v1.json"
TWO_METHOD_MANIFEST = ROOT / "outputs/reports/s2_12_two_method_contract_v1.manifest.json"
TWO_METHOD_BUILDER = ROOT / "scripts/build_s2_12_two_method_contract_v1.py"
GOLD_VERIFIER = ROOT / "scripts/verify_gdpr7_gold_rule_records_v1.py"

EXPECTED_COUNTS = {"rules": 9, "sentences": 74, "items": 92, "spans": 235,
                   "modality_evidence_spans": 85, "relation_entries": 38}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_builder():
    spec = importlib.util.spec_from_file_location("transition_v10_builder", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT.parent, capture_output=True, text=True, timeout=300)


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    try:
        report = _load_json(REPORT)
        manifest = _load_json(MANIFEST)
        export = _load_json(EXPORT)
        schema = _load_json(SCHEMA)
        contract = _load_json(TWO_METHOD_CONTRACT)
        contract_manifest = _load_json(TWO_METHOD_MANIFEST)
    except Exception as exc:
        check("read v10 artifacts", False, str(exc))
        return {"verified": False, "checks": checks}

    check("strict report top-level schema", set(report) == set(schema["required"]))
    check("schema version", report["schema_version"]
          == "s2_13_s3_7_transition_readiness@10.0.0")
    check("report id", report["report_id"]
          == "s2_13_s3_7_transition_readiness_v10")

    # --- independent two-method contract replay --------------------------
    proc = _run(TWO_METHOD_BUILDER, "--check")
    check("two-method contract replay re-executed", proc.returncode == 0,
          (proc.stdout + proc.stderr).strip()[-300:])
    check("two-method contract manifest binds report",
          contract_manifest.get("report", {}).get("sha256") == _sha(TWO_METHOD_CONTRACT)
          and contract_manifest.get("report", {}).get("byte_size")
          == TWO_METHOD_CONTRACT.stat().st_size)
    comparison = contract["comparison"]
    evidence = comparison["evidence"]
    complete = comparison.get("complete") is True
    evidence_complete = all(
        e.get(key) is True for e in (evidence["sun_rule_only"], evidence["direct_llm"])
        for key in ("verified", "input_binding_ok", "all_36_rows", "metrics_valid")
    )
    check("two-method complete flag equals verified evidence", complete == evidence_complete)
    check("cancelled repair not required by contract",
          "sun_llm_fallback" in contract.get("cancelled_methods", {})
          and comparison.get("fallback_results_or_ledger_required") is False
          and contract.get("freeze", {}).get("cancelled_repair_arm_required") is False)

    expected_pipeline = {
        "S1.7": "frozen",
        "S2.11": "verified_frozen",
        "S2.12": ("complete_two_method_evidence" if complete else
                  "partial_two_method_contract_pending_direct_llm"),
        "S2.13": ("ready_for_separate_freeze_checkpoint" if complete else
                  "blocked_only_on_two_method_contract"),
        "S3.4_S3.6": "development_only",
        "S3.7": ("gold_rule_records_published_oracle_isolation_run_"
                 "formal_main_table_not_authorized"),
    }
    check("pipeline state derived from two-method contract",
          report["pipeline_state"] == expected_pipeline)
    check("S2.12 scope and cancellation",
          report["s2_12"]["active_methods"] == ["sun_rule_only", "direct_llm"]
          and report["s2_12"]["cancelled_methods"] == ["sun_llm_fallback"]
          and report["s2_12"]["cancelled_repair_arm"]["required_for_completion"] is False)
    check("S2.12 comparison flag derived",
          report["s2_12"]["comparison_complete"] is complete)
    check("S2.12 remaining calls derived",
          report["s2_12"]["remaining_calls"]
          == contract["call_plan"]["remaining_calls"])
    check("S2.13 state and blockers derived",
          report["s2_13"]["status"] == expected_pipeline["S2.13"]
          and report["s2_13"]["blockers"] == (
              ["separate S2.13 freeze checkpoint not yet executed"]
              if complete else list(comparison.get("blockers") or [])))
    check("S2.12 evidence mirrors contract",
          report["s2_12"]["completion_evidence"]["sun_rule_only"]
          == {key: evidence["sun_rule_only"].get(key) is True
              for key in ("verified", "input_binding_ok", "all_36_rows", "metrics_valid")}
          and report["s2_12"]["completion_evidence"]["direct_llm"]
          == {key: evidence["direct_llm"].get(key) is True
              for key in ("verified", "input_binding_ok", "all_36_rows", "metrics_valid")})

    check("S2.11 formal Gold published",
          report["s2_11"]["status"] == "verified_frozen"
          and report["s2_11"]["adjudicated"] == 36
          and report["s2_11"]["unresolved"] == 0)
    check("Stage 3 development/Oracle boundary",
          all(report["stage3"][key] == "development_only"
              for key in ("S3.4", "S3.5", "S3.6"))
          and report["stage3"]["S3.7"]["authorized"] is False
          and report["stage3"]["S3.7"]["gold_rule_records_present"] is True)

    # --- Gold Rule Records are re-verified, not trusted -------------------
    gold = report["gold_rule_records"]
    check("Gold Rule Records present", gold["exist"] is True
          and gold["verifier_verified"] is True)
    check("Gold Rule Records counts", gold["counts"] == EXPECTED_COUNTS)
    for rel, entry in gold["bindings"].items():
        path = ROOT / entry["path"]
        check(f"gold binding {rel}", path.is_file()
              and _sha(path) == entry["sha256"]
              and path.stat().st_size == entry["byte_size"])
    proc = _run(GOLD_VERIFIER)
    gold_ok = False
    detail: Any = proc.stdout.strip()[:200]
    if proc.returncode == 0:
        try:
            gold_ok = json.loads(proc.stdout).get("verified") is True
        except Exception:
            gold_ok = False
    check("Gold Rule Records verifier re-executed", gold_ok, detail)

    check("zero API / Oracle / cancelled-arm safety",
          report["safety"]["new_llm_api_calls"] == 0
          and report["safety"]["new_network_calls"] == 0
          and report["safety"]["oracle_started"] is False
          and report["safety"]["gold_rule_records_created"] is False
          and report["safety"]["cancelled_repair_arm_used"] is False)
    check("v9 superseded byte-exact",
          len(report["supersedes"]) == 8
          and all((ROOT / item["path"]).is_file()
                  and _sha(ROOT / item["path"]) == item["sha256"]
                  for item in report["supersedes"]))

    # --- manifest / export / builder replay ------------------------------
    for rel, expected in manifest["bindings"].items():
        path = ROOT / rel
        check(f"manifest binding {rel}", path.is_file()
              and _sha(path) == expected)
    for name, item in manifest["artifacts"].items():
        path = ROOT / item["path"]
        check(f"manifest artifact {name}",
              path.is_file() and _sha(path) == item["sha256"]
              and path.stat().st_size == item["byte_size"])
    expected_export = {
        REPORT.relative_to(ROOT).as_posix(): {"sha256": _sha(REPORT),
                                              "byte_size": REPORT.stat().st_size},
        MARKDOWN.relative_to(ROOT).as_posix(): {"sha256": _sha(MARKDOWN),
                                                "byte_size": MARKDOWN.stat().st_size},
        MANIFEST.relative_to(ROOT).as_posix(): {"sha256": _sha(MANIFEST),
                                                "byte_size": MANIFEST.stat().st_size},
    }
    check("export exact reconstruction", export["files"] == expected_export)

    builder = _load_builder()
    try:
        history = builder.historical_asset_ledger()
        check("historical asset ledger matches the report",
              history == report["historical_transition_verifiers"])
        check("historical verifiers are not re-executed",
              history["historical_verifiers_executed"] is False)
        missing = []
        for version, assets in history["assets"].items():
            for rel, entry in assets.items():
                if entry is None:
                    missing.append(f"{version}:{rel}")
                    continue
                path = ROOT / rel
                if not path.is_file() or _sha(path) != entry["sha256"]:
                    missing.append(f"{version}:{rel}")
        check("historical assets byte-exact", not missing, missing[:5])
        expected = builder.build_artifacts(history)
        check("v10 builder byte-identical replay",
              all(path.read_bytes() == payload
                  for path, payload in expected.items()))
    except Exception as exc:
        check("historical asset ledger matches the report", False, str(exc))
        check("v10 builder byte-identical replay", False, str(exc))
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
        print("TRANSITION READINESS V10 VERIFIED" if result["verified"]
              else "TRANSITION READINESS V10 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

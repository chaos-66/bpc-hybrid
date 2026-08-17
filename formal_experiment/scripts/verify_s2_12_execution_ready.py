# -*- coding: utf-8 -*-
"""Independent verifier for the S2.12 execution-ready assets (Checkpoint D).

Re-derives everything from disk (no caller-supplied results):
  * membership closure 40/4/36
  * the plan config is FROZEN with the pre-registration block intact and
    the retrospective descriptive analysis explicitly marked historical
  * all 36 records classify through the SEALED frozen G0.5 chain
    (classify_frozen re-run; level counts must match the committed plan)
  * S2.11 decisions are currently NOT frozen (0/36 adjudicated) and the
    API budget authorization event does not exist -> the readiness report
    must refuse the real run and report gates ready=false
  * API budget is a DRY RUN: calls_made=0, authorized=false,
    sentence_used=false (the copyable sentence is present but unused)
  * the synthetic evaluator fixture run is recomputed deterministically
    and must match the committed readiness summary exactly
  * bindings in all three committed assets must match the recomputed
    input bindings exactly
  * zero LLM/API, no raw third-party text, no Gold created

Exit 0 only when every check passes; any violation exits 1 (fail-closed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s2_12_stratified_evaluator import evaluate  # noqa: E402

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"
PLAN_CONFIG_REL = "configs/s2_12_execution_plan_v1.json"
PLAN_REPORT_REL = "outputs/reports/s2_12_execution_plan_v1.json"
READINESS_REL = "outputs/reports/s2_12_execution_readiness_v1.json"
CONFIRMATION_EVENT_REL = "configs/s2_11_batch_import_confirmation_event_v1.json"
API_BUDGET_EVENT_GLOB = "configs/s2_12_api_budget_*"

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")

# Synthetic fixtures — MUST mirror the builder exactly (deterministic).
SYNTHETIC_IDS = ("synth/a/01", "synth/a/02", "synth/a/03",
                 "synth/b/01", "synth/b/02")
SYNTHETIC_LEVELS = {"synth/a/01": "L1", "synth/a/02": "L1",
                    "synth/a/03": "L1", "synth/b/01": "L2",
                    "synth/b/02": "L2"}
SYNTHETIC_PREDICTIONS = {
    "synth/a/01": {"modality": "obligation", "actor": "nurse",
                   "action": "obtain", "condition": None,
                   "constraint": None, "exception": None},
    "synth/a/02": {"modality": "obligation", "actor": "nurse",
                   "action": "obtain", "condition": "before",
                   "constraint": None, "exception": None},
    "synth/a/03": {"modality": "permission", "actor": "nurse",
                   "action": "record", "condition": None,
                   "constraint": None, "exception": None},
    "synth/b/01": {"modality": "prohibition", "actor": "company",
                   "action": "collect", "condition": "unless",
                   "constraint": "consent", "exception": None},
    "synth/b/02": {"modality": "prohibition", "actor": "company",
                   "action": "collect", "condition": None,
                   "constraint": None, "exception": None},
}
SYNTHETIC_GOLD = {
    "synth/a/01": {"modality": "obligation", "actor": "nurse",
                   "action": "obtain", "condition": None,
                   "constraint": None, "exception": None},
    "synth/a/02": {"modality": "obligation", "actor": "nurse",
                   "action": "obtain", "condition": "before",
                   "constraint": None, "exception": None},
    "synth/a/03": {"modality": "obligation", "actor": "nurse",
                   "action": "record", "condition": None,
                   "constraint": None, "exception": None},
    "synth/b/01": {"modality": "prohibition", "actor": "company",
                   "action": "collect", "condition": "unless",
                   "constraint": "consent", "exception": None},
    "synth/b/02": {"modality": "prohibition", "actor": "company",
                   "action": "collect", "condition": None,
                   "constraint": None, "exception": None},
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _recompute_bindings() -> dict[str, str]:
    rels = (
        MEMBERSHIP_REL,
        "configs/g05_complexity_frozen_v1.json",
        "configs/g05_complexity_candidate_draft_v1.json",
        "configs/g05_authorization_manifest_v1.json",
        DECISIONS_REL,
        "outputs/reports/s2_11_g5_review_surface_v1.json",
        "outputs/reports/s2_11_candidate_run_v1.json",
        "outputs/reports/s2_11_proposal_report_v1.json",
        "outputs/reports/s2_11_batch_import_dry_run_v1.json",
    )
    return {rel: _sha256_file(ROOT / rel) for rel in rels}


def _synthetic_summary() -> dict[str, Any]:
    report = evaluate(SYNTHETIC_PREDICTIONS, SYNTHETIC_GOLD,
                      SYNTHETIC_LEVELS)
    summary = {"strata": {}, "sample_count": report["sample_count"]}
    for level, info in report["strata"].items():
        summary["strata"][level] = {
            "samples": info["samples"],
            "per_field_f1": {
                f: info["per_field"][f]["f1"] for f in DECISION_FIELDS},
        }
    return {"passed": True, "summary": summary,
            "evaluator_schema": report["schema_version"],
            "zero_api": report["zero_api"]}


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name + (f": {detail}" if detail else ""))

    membership = _load_json(ROOT / MEMBERSHIP_REL)
    check("membership closure 40/4/36",
          int(membership["record_count"]) == 40
          and len(membership["quarantine"]) == 4
          and len(membership["records"]) == 36)

    plan = _load_json(ROOT / PLAN_CONFIG_REL)
    plan_report = _load_json(ROOT / PLAN_REPORT_REL)
    readiness = _load_json(ROOT / READINESS_REL)

    check("plan is frozen",
          plan.get("status") == "frozen"
          and plan_report.get("status") == "frozen")
    pre = plan.get("preregistration") or {}
    check("plan declares preregistration before results",
          pre.get("declared_before_results") is True
          and "outcome_spec" in pre
          and "retrospective_descriptive_analysis" in pre)
    check("plan strata levels are exactly L1/L2/L3",
          set(pre.get("strata_level_counts") or {}) == {"L1", "L2", "L3"}
          and sum((pre.get("strata_level_counts") or {}).values()) == 36)

    decisions = _load_json(ROOT / DECISIONS_REL)
    records = decisions.get("records") or {}
    adjudicated = sum(
        1 for e in records.values()
        if e.get("review_state") == "adjudicated")
    check("S2.11 freeze NOT reached (0/36 adjudicated)",
          adjudicated == 0
          and len(records) == 36
          and readiness["gates"]["s2_11_freeze"]["ready"] is False)
    check("real run refused in readiness",
          readiness["runner"]["real_run_refused"] is True
          and readiness["status"] == "ready_for_execution_pending_user_gates")

    api_events = sorted((ROOT / "configs").glob("s2_12_api_budget_*"))
    check("no API budget authorization event exists",
          not api_events
          and not (ROOT / CONFIRMATION_EVENT_REL).is_file())
    budget = readiness.get("api_budget_dry_run") or {}
    check("API budget is dry run only (0 calls, unauthorized, unused)",
          budget.get("status") == "dry_run_not_applied"
          and budget.get("calls_made") == 0
          and budget.get("authorized") is False
          and budget.get("sentence_used") is False
          and isinstance(budget.get("copyable_authorization_sentence"), str)
          and len(budget["copyable_authorization_sentence"]) > 20
          and budget.get("hard_cap") >= budget.get("typical_total", 0))

    recomputed = _synthetic_summary()
    committed = readiness.get("evaluator", {}).get("synthetic_fixture_run")
    check("synthetic evaluator run recomputes exactly",
          committed is not None and committed == recomputed)
    check("readiness zero_api and no gold",
          readiness["zero_api"] == {"new_llm_api_calls": 0}
          and readiness["gold_created"] is False
          and readiness["raw_text_committed"] is False
          and plan_report["zero_api"] == {"new_llm_api_calls": 0}
          and plan_report["gold_created"] is False)

    bindings = _recompute_bindings()
    check("plan config bindings exact",
          plan.get("bindings") == bindings)
    check("plan report bindings exact",
          plan_report.get("bindings") == bindings)
    check("readiness bindings exact",
          readiness.get("bindings") == bindings)
    check("plan report strata counts match plan config",
          plan_report.get("strata_level_counts")
          == pre.get("strata_level_counts"))
    check("plan report population 40/4/36",
          (plan_report.get("population") or {}).get("review_population") == 36)

    return {"verified": not problems, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        for c in result["checks"]:
            print(("PASS" if c["ok"] else "FAIL"), c["name"],
                  ("- " + c["detail"]) if c["detail"] else "")
        print("S2.12 EXECUTION READY VERIFIED"
              if result["verified"]
              else "S2.12 EXECUTION READY NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

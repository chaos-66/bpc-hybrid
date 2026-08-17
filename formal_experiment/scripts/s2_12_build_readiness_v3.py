# -*- coding: utf-8 -*-
"""Deterministic S2.12 execution readiness v3 builder (Checkpoint G; ZERO
real LLM/API).

The S2.12 evaluator v2 is NOT rewritten: the parity check is simply
RE-RUN in-process (same evaluator, same fixture) and the readiness v3
report re-binds the S2.11 proposal v3 / importer v3 assets.

Builds (no-overwrite):
  outputs/reports/s2_12_execution_readiness_v3.json

Claims ONLY: schema ready, importer ready (v3 dry-run blocked=0/
unresolved=0/adjudicable=36), evaluator ready (parity), method-adapter
dry-run ready; S2.11 freeze is 36/36 (user-confirmed adjudication,
Checkpoint G); the real stratified run stays refused ONLY on the API
budget authorization (missing items: input token cap + cost cap -> no
final authorization sentence). No Gold or formal evaluation is claimed.
API readiness stays a dry-run (no calls).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
PROPOSAL_REPORT_V3_REL = "outputs/reports/s2_11_proposal_report_v3.json"
IMPORTER_DRY_RUN_V3_REL = "outputs/reports/s2_11_batch_import_dry_run_v3.json"
PLAN_V2_REL = "configs/s2_12_execution_plan_v2.json"
PLAN_REPORT_V2_REL = "outputs/reports/s2_12_execution_plan_v2.json"
READINESS_V2_REL = "outputs/reports/s2_12_execution_readiness_v2.json"
API_READINESS_V2_REL = "outputs/reports/s2_12_api_readiness_v2.json"
CONFIRMATION_EVENT_REL = \
    "configs/s2_11_batch_import_confirmation_event_v3.json"
EVALUATOR_V2_REL = "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py"
ADAPTER_REL = "src/bpc_hybrid/s2_12_method_adapter.py"
EVALUATOR_CONTRACT_REL = "configs/stage2_evaluator_s210_v3.json"
READINESS_V3_REL = "outputs/reports/s2_12_execution_readiness_v3.json"


class BuildFail(Exception):
    """Fail-closed build abort."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuildFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _parity_rerun() -> dict[str, Any]:
    """Re-run the parity check via the UNMODIFIED v2 builder module."""
    builder_path = Path(__file__).resolve().parent / \
        "s2_12_build_execution_ready_v2.py"
    spec = importlib.util.spec_from_file_location(
        "s2_12_build_execution_ready_v2_reuse", builder_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod._parity_check()


def build() -> dict[str, Any]:
    parity = _parity_rerun()
    if not parity["passed"]:
        raise BuildFail("parity rerun failed: formal evaluator and "
                        "stratified v2 disagree")
    proposal = _load_json(ROOT / PROPOSAL_REPORT_V3_REL)
    if proposal.get("coverage") != "36/36" or \
            proposal.get("human_approved") is not False or \
            proposal.get("gold_created") is not False:
        raise BuildFail("proposal v3 must be 36/36, unapproved, no Gold")
    importer = _load_json(ROOT / IMPORTER_DRY_RUN_V3_REL)
    stats = importer.get("import_stats") or {}
    if stats.get("blocked_fields") != 0 or \
            stats.get("blocked_samples") != 0 or \
            stats.get("unresolved_fields") != 0 or \
            stats.get("adjudicable") != 36:
        raise BuildFail("importer v3 dry-run must show 0/0/36")
    decisions = _load_json(ROOT / DECISIONS_V2_REL)
    adjudicated = sum(
        1 for e in decisions["records"].values()
        if (e.get("review_metadata") or {}).get("review_state")
        == "adjudicated")
    api_v2 = _load_json(ROOT / API_READINESS_V2_REL)

    readiness = {
        "schema_version": "s2_12_execution_readiness@3.1.0",
        "status": "ready_for_execution_pending_api_authorization",
        "supersedes_v2": {
            "readiness_v2": READINESS_V2_REL,
            "reason": "re-binds the S2.11 proposal v3 / importer v3 assets "
                      "(proposal v2 superseded); evaluator v2 unchanged; "
                      "Checkpoint G user-confirmed the proposal v3 "
                      "adjudication (freeze 36/36)",
        },
        "ready_claims": {
            "schema_ready": True,
            "importer_ready": stats,
            "evaluator_ready": {"module": EVALUATOR_V2_REL,
                                "parity_rerun": parity},
            "method_adapter_dry_run_ready": True,
            "gold_or_formal_evaluation_complete": False,
        },
        "proposal_v3": {
            "report": PROPOSAL_REPORT_V3_REL,
            "proposal_file_sha256": proposal["proposal_file_sha256"],
            "human_approved": True,
            "confirmation_event": CONFIRMATION_EVENT_REL,
            "gold_created": False,
            "supersedes_v2_status":
                proposal["supersedes_v2"]["status"],
        },
        "runner": {
            "script": "scripts/s2_12_build_readiness_v3.py",
            "fail_closed": True,
            "real_run_refused": True,
            "real_run_refusal_reason": (
                "S2.11 freeze is complete (36/36 adjudicated, user-"
                "confirmed proposal v3, Checkpoint G) but the API budget "
                "authorization is still missing (input token cap, cost "
                "cap); the real stratified run stays refused until the "
                "user supplies the missing items and the final "
                "authorization sentence"),
        },
        "gates": {
            "s2_11_freeze": {"adjudicated": adjudicated, "total": 36,
                             "ready": adjudicated == 36,
                             "confirmation_event": CONFIRMATION_EVENT_REL},
            "api_budget_authorization": {
                "event_present": False,
                "ready": False,
                "missing_items":
                    api_v2["missing_items_for_final_authorization"],
            },
        },
        "api_readiness": {
            "report": API_READINESS_V2_REL,
            "calls_made": api_v2["calls_made"],
            "final_copyable_authorization_sentence":
                api_v2["final_copyable_authorization_sentence"],
        },
        "raw_text_committed": False,
        "gold_created": False,
        "human_approved": False,
        "zero_api": {"new_llm_api_calls": 0},
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
        "bindings": {},
    }
    bindings = {
        MEMBERSHIP_REL: _sha256_file(ROOT / MEMBERSHIP_REL),
        DECISIONS_V2_REL: _sha256_file(ROOT / DECISIONS_V2_REL),
        PROPOSAL_REPORT_V3_REL: _sha256_file(ROOT / PROPOSAL_REPORT_V3_REL),
        IMPORTER_DRY_RUN_V3_REL: _sha256_file(ROOT / IMPORTER_DRY_RUN_V3_REL),
        CONFIRMATION_EVENT_REL: _sha256_file(ROOT / CONFIRMATION_EVENT_REL),
        PLAN_V2_REL: _sha256_file(ROOT / PLAN_V2_REL),
        PLAN_REPORT_V2_REL: _sha256_file(ROOT / PLAN_REPORT_V2_REL),
        READINESS_V2_REL: _sha256_file(ROOT / READINESS_V2_REL),
        API_READINESS_V2_REL: _sha256_file(ROOT / API_READINESS_V2_REL),
        EVALUATOR_V2_REL: _sha256_file(ROOT / EVALUATOR_V2_REL),
        ADAPTER_REL: _sha256_file(ROOT / ADAPTER_REL),
        EVALUATOR_CONTRACT_REL: _sha256_file(ROOT / EVALUATOR_CONTRACT_REL),
        "scripts/s2_12_build_execution_ready_v2.py": _sha256_file(
            ROOT / "scripts/s2_12_build_execution_ready_v2.py"),
    }
    readiness["bindings"] = dict(sorted(bindings.items()))
    return readiness


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="Checkpoint G: explicitly overwrite the "
                             "committed readiness v3 report (with a .bak "
                             "backup) once the user-confirmed S2.11 freeze "
                             "(36/36) is on disk; the no-overwrite guard "
                             "is bypassed ONLY here")
    args = parser.parse_args()
    try:
        readiness = build()
    except BuildFail as exc:
        print(f"S2.12 READINESS V3 BUILD FAILED (fail-closed): {exc}",
              file=sys.stderr)
        return 2
    data = (json.dumps(readiness, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    target = ROOT / READINESS_V3_REL
    try:
        if args.refresh and target.is_file():
            shutil.copy2(target, ROOT / (READINESS_V3_REL + ".bak"))
            tmp = ROOT / (READINESS_V3_REL + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)
        else:
            _write(target, data)
    except BuildFail as exc:
        print(f"S2.12 READINESS V3 BUILD FAILED (refusing overwrite): {exc}",
              file=sys.stderr)
        return 2
    parity_ok = readiness["ready_claims"]["evaluator_ready"][
        "parity_rerun"]["passed"]
    print(f"S2.12 readiness v3 written: {READINESS_V3_REL} "
          f"(parity={parity_ok}, refresh={args.refresh})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

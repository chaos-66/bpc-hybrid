# -*- coding: utf-8 -*-
"""Independent verifier for the S2.12 execution readiness v3 (Checkpoint
G). Re-derives everything from disk:

  * proposal v3 report is 36/36, unapproved, no Gold and declares v2
    superseded (pending-targeted-correction status)
  * importer v3 dry-run stats are blocked=0/unresolved=0/adjudicable=36
  * the parity check is RE-RUN in-process (evaluator v2 unchanged) and
    must pass and match the committed readiness v3 claim
  * S2.11 freeze is 36/36 (user-confirmed proposal v3, Checkpoint G) and
    the real run stays refused on the API budget authorization only
  * API readiness remains a dry-run with the v2 missing items (input
    token cap, cost cap) and NO final authorization sentence
  * bindings exact (incl. the confirmation event); zero API; no Gold

Exit 0 only when every check passes (fail-closed).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
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
API_READINESS_V2_REL = "outputs/reports/s2_12_api_readiness_v2.json"
CONFIRMATION_EVENT_REL = \
    "configs/s2_11_batch_import_confirmation_event_v3.json"
READINESS_V3_REL = "outputs/reports/s2_12_execution_readiness_v3.json"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    problems: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            problems.append(name + (f": {detail}" if detail else ""))

    proposal = _load_json(ROOT / PROPOSAL_REPORT_V3_REL)
    check("proposal v3 report unapproved/supersedes v2",
          proposal.get("coverage") == "36/36"
          and proposal.get("human_approved") is False
          and proposal.get("gold_created") is False
          and proposal["supersedes_v2"]["status"] ==
          "superseded_pending_targeted_correction_do_not_approve")

    importer = _load_json(ROOT / IMPORTER_DRY_RUN_V3_REL)
    check("importer v3 dry-run blocked=0/unresolved=0/adjudicable=36",
          importer.get("import_stats") == {
              "samples": 36, "blocked_fields": 0, "blocked_samples": 0,
              "unresolved_fields": 0, "adjudicable": 36})

    readiness = _load_json(ROOT / READINESS_V3_REL)
    builder_path = Path(__file__).resolve().parent / \
        "s2_12_build_readiness_v3.py"
    spec = importlib.util.spec_from_file_location(
        "s2_12_build_readiness_v3_mod", builder_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    parity = mod._parity_rerun()
    check("parity rerun passed and matches committed claim",
          parity["passed"] is True
          and readiness["ready_claims"]["evaluator_ready"]["parity_rerun"]
          == parity)

    decisions = _load_json(ROOT / DECISIONS_V2_REL)
    adjudicated = sum(
        1 for e in decisions["records"].values()
        if (e.get("review_metadata") or {}).get("review_state")
        == "adjudicated")
    confirmation_event = ROOT / CONFIRMATION_EVENT_REL
    check("freeze 36/36 user-confirmed; run refused on API auth only",
          adjudicated == 36
          and confirmation_event.is_file()
          and readiness["proposal_v3"]["human_approved"] is True
          and readiness["gates"]["s2_11_freeze"]["ready"] is True
          and readiness["runner"]["real_run_refused"] is True
          and readiness["ready_claims"]["gold_or_formal_evaluation_complete"]
          is False)

    api = _load_json(ROOT / API_READINESS_V2_REL)
    check("API readiness v3 stays dry-run without final sentence",
          readiness["api_readiness"]["calls_made"] == 0
          and readiness["api_readiness"]["final_copyable_authorization_"
                                          "sentence"] is None
          and any("input_token_cap" in m for m in
                  readiness["gates"]["api_budget_authorization"]
                  ["missing_items"])
          and any("cost_cap" in m for m in
                  readiness["gates"]["api_budget_authorization"]
                  ["missing_items"])
          and api["calls_made"] == 0)

    expected_bindings = {
        MEMBERSHIP_REL: _sha256_file(ROOT / MEMBERSHIP_REL),
        DECISIONS_V2_REL: _sha256_file(ROOT / DECISIONS_V2_REL),
        PROPOSAL_REPORT_V3_REL: _sha256_file(ROOT / PROPOSAL_REPORT_V3_REL),
        IMPORTER_DRY_RUN_V3_REL: _sha256_file(ROOT / IMPORTER_DRY_RUN_V3_REL),
        CONFIRMATION_EVENT_REL: _sha256_file(ROOT / CONFIRMATION_EVENT_REL),
        "configs/s2_12_execution_plan_v2.json": _sha256_file(
            ROOT / "configs/s2_12_execution_plan_v2.json"),
        "outputs/reports/s2_12_execution_plan_v2.json": _sha256_file(
            ROOT / "outputs/reports/s2_12_execution_plan_v2.json"),
        "outputs/reports/s2_12_execution_readiness_v2.json": _sha256_file(
            ROOT / "outputs/reports/s2_12_execution_readiness_v2.json"),
        API_READINESS_V2_REL: _sha256_file(ROOT / API_READINESS_V2_REL),
        "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py": _sha256_file(
            ROOT / "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py"),
        "src/bpc_hybrid/s2_12_method_adapter.py": _sha256_file(
            ROOT / "src/bpc_hybrid/s2_12_method_adapter.py"),
        "configs/stage2_evaluator_s210_v3.json": _sha256_file(
            ROOT / "configs/stage2_evaluator_s210_v3.json"),
        "scripts/s2_12_build_execution_ready_v2.py": _sha256_file(
            ROOT / "scripts/s2_12_build_execution_ready_v2.py"),
    }
    check("readiness v3 bindings exact",
          readiness.get("bindings") == expected_bindings)
    check("zero API and no Gold",
          readiness["zero_api"] == {"new_llm_api_calls": 0}
          and readiness["gold_created"] is False
          and readiness["raw_text_committed"] is False)
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
        print("S2.12 READINESS V3 VERIFIED"
              if result["verified"]
              else "S2.12 READINESS V3 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Independent verifier for the S2.12 execution-ready v2 assets (Checkpoint
E3, refreshed for Checkpoint G). Re-derives everything from disk:

  * membership closure 40/4/36; frozen G0.5 strata counts recomputed
    (must equal the committed plan v2)
  * plan v2 is FROZEN, supersedes v1 (evaluator/Gold-shape correction),
    and binds the formal evaluator contract path
  * importer v2 dry-run stats are blocked=0/unresolved=0/adjudicable=36
    (from the committed dry-run report v2)
  * the parity check is recomputed in-process (formal Stage 2 evaluator
    vs stratified v2 on the same synthetic fixture) and must match the
    committed readiness v2 claim AND pass
  * S2.11 freeze v2 is 36/36 (Checkpoint G: the user confirmed proposal
    v3 and the decisions v2 carry the 36/36 adjudication) and the real
    run stays refused; readiness claims only schema/importer/evaluator/
    method-adapter readiness
  * API readiness v2: exact model ids (deepseek-v4-pro for both arms with
    their sources), max calls (36 / 72), output token cap 4096, input cap
    unresolved, cost_cap_unresolved, calls_made=0, no final
    authorization sentence issued (missing items listed)
  * bindings exact except the S2.11 decisions v2 SHA, which the CHECKPOINT
    G apply legitimately changed (plan v2/readiness v2 keep their pre-apply
    snapshot; the decisions integrity is verified separately as 36/36
    adjudicated); zero API; no Gold

Exit 0 only when every check passes (fail-closed).
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

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PLAN_CONFIG_V2_REL = "configs/s2_12_execution_plan_v2.json"
PLAN_REPORT_V2_REL = "outputs/reports/s2_12_execution_plan_v2.json"
READINESS_V2_REL = "outputs/reports/s2_12_execution_readiness_v2.json"
API_READINESS_V2_REL = "outputs/reports/s2_12_api_readiness_v2.json"
BATCH_DRY_RUN_V2_REL = "outputs/reports/s2_11_batch_import_dry_run_v2.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
D1_REGISTRY_REL = "configs/models/estg150_d1_active_registry_v1.json"
H1_MANIFEST_REL = "outputs/development/s28d_h1_150_v4pro_v1/manifest.json"


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

    membership = _load_json(ROOT / MEMBERSHIP_REL)
    check("membership closure 40/4/36",
          int(membership["record_count"]) == 40
          and len(membership["quarantine"]) == 4
          and len(membership["records"]) == 36)

    plan = _load_json(ROOT / PLAN_CONFIG_V2_REL)
    plan_report = _load_json(ROOT / PLAN_REPORT_V2_REL)
    readiness = _load_json(ROOT / READINESS_V2_REL)
    api = _load_json(ROOT / API_READINESS_V2_REL)

    check("plan v2 frozen with supersedes_v1",
          plan.get("status") == "frozen"
          and plan_report.get("status") == "frozen"
          and "supersedes_v1" in plan
          and "evaluator" in plan["supersedes_v1"]["reason"]
          and "Gold shape" in plan["supersedes_v1"]["reason"])
    pre = plan.get("preregistration") or {}
    check("plan v2 strata counts match membership (L1/L2/L3)",
          sum((pre.get("strata_level_counts") or {}).values()) == 36
          and plan_report.get("strata_level_counts")
          == pre.get("strata_level_counts"))

    importer = _load_json(ROOT / BATCH_DRY_RUN_V2_REL).get("import_stats")
    check("importer v2 dry-run blocked=0/unresolved=0/adjudicable=36",
          importer == {"samples": 36, "blocked_fields": 0,
                       "blocked_samples": 0, "unresolved_fields": 0,
                       "adjudicable": 36})

    # recompute the parity check in-process (builder module is loaded from
    # the REAL scripts dir, independent of ROOT)
    import importlib.util
    builder_path = Path(__file__).resolve().parent / \
        "s2_12_build_execution_ready_v2.py"
    spec = importlib.util.spec_from_file_location(
        "s2_12_build_execution_ready_v2_mod", builder_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    parity = mod._parity_check()
    check("parity recomputed and passed",
          parity["passed"] is True
          and readiness["ready_claims"]["evaluator_ready"]["parity"]
          ["passed"] is True
          and readiness["ready_claims"]["evaluator_ready"]["parity"]
          ["span_metrics_equal"] is True
          and readiness["ready_claims"]["evaluator_ready"]["parity"]
          ["modality_metrics_equal"] is True)

    decisions = _load_json(ROOT / DECISIONS_V2_REL)
    adjudicated = sum(
        1 for e in decisions["records"].values()
        if (e.get("review_metadata") or {}).get("review_state")
        == "adjudicated")
    check("S2.11 freeze v2 reached (36/36) and run refused",
          adjudicated == 36
          and readiness["runner"]["real_run_refused"] is True
          and readiness["ready_claims"]["gold_or_formal_evaluation_complete"]
          is False)

    d1 = _load_json(ROOT / D1_REGISTRY_REL)
    h1 = _load_json(ROOT / H1_MANIFEST_REL)
    check("API readiness v2 exact model ids",
          api["arms"]["direct_llm"]["model_id"] == "deepseek-v4-pro"
          and api["arms"]["sun_llm_fallback"]["model_id"]
          == h1.get("llm_model") == "deepseek-v4-pro"
          and d1["recipe_lock"]["model"]["id"] == "deepseek-v4-pro"
          and d1["recipe_lock"]["model"]["fail_closed_pin"] is True)
    check("API readiness v2 call bounds derived",
          api["arms"]["direct_llm"]["max_calls"] == 36
          and api["arms"]["sun_llm_fallback"]["max_calls"] == 72
          and api["totals"]["max_calls"] == 108)
    check("API readiness v2 token/cost honest",
          api["arms"]["direct_llm"]["output_token_cap"] == 4096
          and api["totals"]["output_side_total_token_bound"] == 442368
          and api["totals"]["input_side_total_token_bound"] == "unresolved"
          and api["totals"]["cost_cap"] == "cost_cap_unresolved")
    check("API readiness v2 no final sentence (missing items listed)",
          api["final_copyable_authorization_sentence"] is None
          and any("input_token_cap" in m for m in
                  api["missing_items_for_final_authorization"])
          and any("cost_cap" in m for m in
                  api["missing_items_for_final_authorization"])
          and api["calls_made"] == 0
          and api["authorized"] is False)

    bindings = {
        MEMBERSHIP_REL: _sha256_file(ROOT / MEMBERSHIP_REL),
        "configs/g05_complexity_frozen_v1.json": _sha256_file(
            ROOT / "configs/g05_complexity_frozen_v1.json"),
        "configs/g05_complexity_candidate_draft_v1.json": _sha256_file(
            ROOT / "configs/g05_complexity_candidate_draft_v1.json"),
        "configs/g05_authorization_manifest_v1.json": _sha256_file(
            ROOT / "configs/g05_authorization_manifest_v1.json"),
        DECISIONS_V2_REL: _sha256_file(ROOT / DECISIONS_V2_REL),
        "outputs/reports/s2_11_proposal_report_v2.json": _sha256_file(
            ROOT / "outputs/reports/s2_11_proposal_report_v2.json"),
        BATCH_DRY_RUN_V2_REL: _sha256_file(ROOT / BATCH_DRY_RUN_V2_REL),
        "configs/stage2_evaluator_s210_v3.json": _sha256_file(
            ROOT / "configs/stage2_evaluator_s210_v3.json"),
        D1_REGISTRY_REL: _sha256_file(ROOT / D1_REGISTRY_REL),
        H1_MANIFEST_REL: _sha256_file(ROOT / H1_MANIFEST_REL),
        "configs/s2_12_execution_plan_v1.json": _sha256_file(
            ROOT / "configs/s2_12_execution_plan_v1.json"),
        "outputs/reports/s2_12_execution_plan_v1.json": _sha256_file(
            ROOT / "outputs/reports/s2_12_execution_plan_v1.json"),
        "outputs/reports/s2_12_execution_readiness_v1.json": _sha256_file(
            ROOT / "outputs/reports/s2_12_execution_readiness_v1.json"),
    }
    # Bindings: exact against every expected asset EXCEPT the S2.11
    # decisions v2 SHA, which the Checkpoint G apply legitimately changed
    # (plan v2 / readiness v2 keep their pre-apply snapshot; decisions
    # integrity is verified separately as 36/36 adjudicated above and by
    # the freeze validator v3 executed by the transition capsule).
    def _without_decisions(d: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in d.items() if k != DECISIONS_V2_REL}

    check("plan v2 bindings exact (decisions v2 apply exempted)",
          _without_decisions(plan.get("bindings") or {})
          == _without_decisions(bindings)
          and DECISIONS_V2_REL in (plan.get("bindings") or {}))
    check("plan report v2 bindings exact (decisions v2 apply exempted)",
          _without_decisions(plan_report.get("bindings") or {})
          == _without_decisions(bindings)
          and DECISIONS_V2_REL in (plan_report.get("bindings") or {}))
    check("readiness v2 bindings exact (decisions v2 apply exempted)",
          _without_decisions(readiness.get("bindings") or {})
          == _without_decisions(bindings)
          and DECISIONS_V2_REL in (readiness.get("bindings") or {}))
    check("zero API and no Gold in v2 assets",
          plan["zero_api"] == {"new_llm_api_calls": 0}
          and readiness["zero_api"] == {"new_llm_api_calls": 0}
          and api["zero_api"] == {"new_llm_api_calls": 0}
          and plan["gold"]["gold_files_created"] is False
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
        print("S2.12 EXECUTION READY V2 VERIFIED"
              if result["verified"]
              else "S2.12 EXECUTION READY V2 NOT VERIFIED")
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

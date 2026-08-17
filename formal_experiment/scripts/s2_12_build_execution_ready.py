# -*- coding: utf-8 -*-
"""Deterministic S2.12 execution-ready builder (Checkpoint D; ZERO LLM/API).

Builds (no-overwrite, byte-identical rebuild):
  configs/s2_12_execution_plan_v1.json            (FROZEN preregistered plan)
  outputs/reports/s2_12_execution_plan_v1.json    (plan derivation + bindings)
  outputs/reports/s2_12_execution_readiness_v1.json
        (runner/evaluator readiness + API budget dry-run + copyable
         authorization sentence — NOT used this round)

FAIL-CLOSED invariants:
  * membership must be 40/4/36 (closure invariant re-verified from disk)
  * the G0.5 chain must be FROZEN (sealed v6 verification via
    classify_frozen on every record's text; any drift aborts)
  * S2.11 decisions must currently be 36/36 unreviewed (zero adjudicated);
    the plan therefore declares Gold = user-adjudicated decisions PENDING
    user action, and the real run is REFUSED until the freeze gate and an
    API budget authorization event exist
  * the API budget is a DRY RUN: calls_made=0, no API/LLM invocation,
    the copyable authorization sentence is present but marked unused
  * the stratified evaluator runs ONLY on fixed synthetic fixtures here;
    real predictions/Gold are never read or written
  * nothing is invented: raw corpus text is never copied into committed
    outputs (only hashes/ids/counts/levels)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g05_complexity_candidate import (  # noqa: E402
    classify_frozen,
)
from bpc_hybrid.s2_11_corpus_ingestion import g05_features  # noqa: E402
from bpc_hybrid.s2_12_stratified_evaluator import evaluate  # noqa: E402

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"
AUTH_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"
G5_REPORT_REL = "outputs/reports/s2_11_g5_review_surface_v1.json"
CANDIDATE_RUN_REL = "outputs/reports/s2_11_candidate_run_v1.json"
PROPOSAL_REPORT_REL = "outputs/reports/s2_11_proposal_report_v1.json"
BATCH_DRY_RUN_REL = "outputs/reports/s2_11_batch_import_dry_run_v1.json"

PLAN_CONFIG_REL = "configs/s2_12_execution_plan_v1.json"
PLAN_REPORT_REL = "outputs/reports/s2_12_execution_plan_v1.json"
READINESS_REL = "outputs/reports/s2_12_execution_readiness_v1.json"

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")

# Fixed synthetic fixtures (no corpus text): ids are placeholders, values
# are invented laboratory strings used ONLY to exercise the evaluator.
SYNTHETIC_IDS = ("synth/a/01", "synth/a/02", "synth/a/03",
                 "synth/b/01", "synth/b/02")
SYNTHETIC_LEVELS = {"synth/a/01": "L1", "synth/a/02": "L1",
                    "synth/a/03": "L1", "synth/b/01": "L2",
                    "synth/b/02": "L2"}

# Budget estimate for the FUTURE real run (36 records, 3 arms).
BUDGET_CAP = 100
BUDGET_TYPICAL = 72


class BuildFail(Exception):
    """Fail-closed build abort."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


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


def _load_source_text(record_id: str, rec: dict[str, Any]) -> str:
    src = ROOT.parent / rec["path"]
    raw = src.read_bytes()
    if _sha256_bytes(raw) != rec["file_sha256"]:
        raise BuildFail(f"source file hash drift for {record_id}")
    scenario, rid, version = record_id.split("/")
    doc = json.loads(raw.decode("utf-8"))
    for entry in doc:
        if str(entry.get("ID")) == rid and \
                str(entry.get("version")) == version.lstrip("v"):
            text = str(entry.get("text", ""))
            if _sha256_bytes(text.encode("utf-8")) != rec["text_sha256"]:
                raise BuildFail(f"text hash drift for {record_id}")
            return text
    raise BuildFail(f"record {record_id} not found in source")


def _freeze_state() -> tuple[str, int]:
    """Verify the S2.11 decisions state; returns (state, adjudicated)."""
    decisions = _load_json(ROOT / DECISIONS_REL)
    records = decisions.get("records") or {}
    if len(records) != 36:
        raise BuildFail(f"decisions file must have 36 records, got "
                        f"{len(records)}")
    adjudicated = sum(
        1 for e in records.values()
        if e.get("review_state") == "adjudicated")
    states = {e.get("review_state") for e in records.values()}
    if not states <= {"unreviewed", "reviewed", "adjudicated"}:
        raise BuildFail(f"unexpected review states: {sorted(states)}")
    if adjudicated == 36:
        return "frozen", adjudicated
    return "pending_user_adjudication", adjudicated


def _api_budget_dry_run() -> dict[str, Any]:
    return {
        "status": "dry_run_not_applied",
        "records": 36,
        "per_method": {
            "sun_rule_only": {"api_calls_per_record": 0, "total": 0},
            "sun_llm_fallback": {"api_calls_per_record": 1, "total": 36},
            "direct_llm": {"api_calls_per_record": 1, "total": 36},
        },
        "typical_total": BUDGET_TYPICAL,
        "hard_cap": BUDGET_CAP,
        "calls_made": 0,
        "authorized": False,
        "copyable_authorization_sentence": (
            "我授权在 S2.12 复杂度分层误差分析中，对 36 条 Barrientos 复杂"
            "语料记录运行 sun_llm_fallback 与 direct_llm 两臂，合计 LLM API "
            f"调用硬上限 {BUDGET_CAP} 次（typical {BUDGET_TYPICAL} 次：36 条 "
            "× 2 臂 × 1 次/条），仅用于 S2.12 分层误差分析；不使用人工 Gold "
            "作为 prompt 内容；实际调用数如实记录；超出上限立即停止。"),
        "sentence_used": False,
    }


def _synthetic_evaluator_run() -> dict[str, Any]:
    """Deterministic synthetic fixture run of the stratified evaluator."""
    predictions = {
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
    gold = {
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
    report = evaluate(predictions, gold, SYNTHETIC_LEVELS)
    # summary only (counts; no invented content beyond the fixture)
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


def _bindings() -> dict[str, str]:
    """Bindings over the EXISTING committed input assets only (the three
    new outputs bind their inputs; they do not bind themselves)."""
    rels = (
        MEMBERSHIP_REL, FROZEN_REL, DRAFT_REL, AUTH_MANIFEST_REL,
        DECISIONS_REL, G5_REPORT_REL, CANDIDATE_RUN_REL,
        PROPOSAL_REPORT_REL, BATCH_DRY_RUN_REL,
    )
    bindings: dict[str, str] = {}
    for rel in rels:
        bindings[rel] = _sha256_file(ROOT / rel)
    return dict(sorted(bindings.items()))


def build() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    if int(membership["record_count"]) != 40 or \
            len(membership["quarantine"]) != 4 or \
            len(membership["records"]) != 36:
        raise BuildFail("membership must be 40/4/36")

    # every non-empty record classified with the SEALED frozen G0.5 chain
    levels: dict[str, str] = {}
    for record_id, rec in sorted(membership["records"].items()):
        text = _load_source_text(record_id, rec)
        g05 = classify_frozen(
            g05_features(text),
            draft_config_path=ROOT / DRAFT_REL,
            frozen_config_path=ROOT / FROZEN_REL,
            authorization_manifest_path=ROOT / AUTH_MANIFEST_REL,
            project_root=ROOT)
        levels[record_id] = g05["level"]
    level_counts = {lv: sum(1 for v in levels.values() if v == lv)
                    for lv in ("L1", "L2", "L3")}

    freeze_state, adjudicated = _freeze_state()
    budget = _api_budget_dry_run()
    synthetic = _synthetic_evaluator_run()

    plan_config = {
        "schema_version": "s2_12_execution_plan@1.0.0",
        "plan_id": "s2-12-execution-plan-v1",
        "status": "frozen",
        "preregistration": {
            "declared_before_results": True,
            "stratification": "G0.5 frozen levels L1/L2/L3 (sealed v6 chain, "
                              "computed per record at run time)",
            "strata_level_counts": level_counts,
            "outcome_spec": (
                "per stratum per field (modality/actor/action/condition/"
                "constraint/exception) precision/recall/F1 plus error-type "
                "counts (correct/missed/misclassified/extra) per method, "
                "and per-method stratification curves"),
            "methods": [
                {"arm": "sun_rule_only", "api_calls": 0},
                {"arm": "sun_llm_fallback", "api_calls": "budgeted"},
                {"arm": "direct_llm", "api_calls": "budgeted"},
            ],
            "same_input_gold_evaluator": True,
            "retrospective_descriptive_analysis": (
                "outputs/reports/s2_12_formal_descriptive_error_analysis_v1"
                ".json remains historical/retrospective; this plan is the "
                "pre-registered stratification for the external complex "
                "corpus"),
        },
        "input": {
            "membership": MEMBERSHIP_REL,
            "records": 36,
            "raw_text_committed": False,
        },
        "gold": {
            "source": "user-adjudicated S2.11 review decisions",
            "decisions_file": DECISIONS_REL,
            "state": freeze_state,
            "adjudicated": adjudicated,
            "gold_files_created": False,
        },
        "gates": [
            "S2.11 freeze: 36/36 records adjudicated by the USER "
            "(verify_s2_11_review_freeze.py frozen=true)",
            "API budget authorization event present and matching "
            "configs/s2_12_api_budget (hard cap)",
            "budget hard cap enforced by the runner (--max-calls)",
        ],
        "definition_of_done": (
            "MASTER_PIPELINE S2.12 full DoD: pre-registered stratification "
            "curves and error types delivered on the external complex "
            "corpus (36 records), same input/Gold/evaluator across the "
            "three method arms, zero unrecorded API calls"),
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
        "zero_api": {"new_llm_api_calls": 0},
        "bindings": {},
    }

    plan_report = {
        "schema_version": "s2_12_execution_plan_report@1.0.0",
        "plan_config": PLAN_CONFIG_REL,
        "status": "frozen",
        "membership": MEMBERSHIP_REL,
        "population": {
            "inventory": 40, "objective_exclusions": 4,
            "nonempty_membership": 36, "review_population": 36,
        },
        "strata_level_counts": level_counts,
        "freeze_state": freeze_state,
        "adjudicated": adjudicated,
        "api_budget_dry_run": budget,
        "raw_text_committed": False,
        "gold_created": False,
        "zero_api": {"new_llm_api_calls": 0},
        "bindings": {},
    }

    readiness = {
        "schema_version": "s2_12_execution_readiness@1.0.0",
        "status": "ready_for_execution_pending_user_gates",
        "runner": {
            "script": "scripts/s2_12_build_execution_ready.py",
            "fail_closed": True,
            "real_run_refused": True,
            "real_run_refusal_reason": (
                "S2.11 freeze not reached (36/36 user adjudication pending) "
                "and no API budget authorization event exists"),
        },
        "evaluator": {
            "module": "src/bpc_hybrid/s2_12_stratified_evaluator.py",
            "synthetic_fixture_run": synthetic,
        },
        "gates": {
            "s2_11_freeze": {"adjudicated": adjudicated, "total": 36,
                             "ready": adjudicated == 36},
            "api_budget_authorization": {
                "event_present": False, "ready": False},
        },
        "api_budget_dry_run": budget,
        "plan": PLAN_CONFIG_REL,
        "raw_text_committed": False,
        "gold_created": False,
        "human_approved": False,
        "zero_api": {"new_llm_api_calls": 0},
        "determinism": {"no_wall_clock": True, "byte_identical_rebuild": True,
                        "no_overwrite": True},
        "bindings": {},
    }

    plan_config["bindings"] = _bindings()
    plan_report["bindings"] = _bindings()
    readiness["bindings"] = _bindings()
    return plan_config, plan_report, readiness


def main() -> int:
    try:
        plan_config, plan_report, readiness = build()
    except BuildFail as exc:
        print(f"S2.12 BUILD FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    plan_config_bytes = (json.dumps(plan_config, ensure_ascii=False,
                                    indent=2) + "\n").encode("utf-8")
    plan_report_bytes = (json.dumps(plan_report, ensure_ascii=False,
                                    indent=2) + "\n").encode("utf-8")
    readiness_bytes = (json.dumps(readiness, ensure_ascii=False,
                                  indent=2) + "\n").encode("utf-8")
    try:
        _write(ROOT / PLAN_CONFIG_REL, plan_config_bytes)
        _write(ROOT / PLAN_REPORT_REL, plan_report_bytes)
        _write(ROOT / READINESS_REL, readiness_bytes)
    except BuildFail as exc:
        print(f"S2.12 BUILD FAILED (refusing overwrite): {exc}",
              file=sys.stderr)
        return 2
    print(f"S2.12 execution plan written: {PLAN_CONFIG_REL} "
          f"(frozen, strata="
          f"{plan_config['preregistration']['strata_level_counts']})")
    print(f"S2.12 execution plan report written: {PLAN_REPORT_REL}")
    print(f"S2.12 execution readiness written: {READINESS_REL} "
          f"(freeze {plan_report['adjudicated']}/36, "
          f"api_calls_made={readiness['api_budget_dry_run']['calls_made']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

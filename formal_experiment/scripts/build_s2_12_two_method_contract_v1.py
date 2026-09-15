# -*- coding: utf-8 -*-
"""Build the successor S2.12 two-method execution/evaluation/freeze contract.

This is the zero-API SEP-C2 adaptation requested after the user cancelled
Rules+LLM-Repair.  It binds the actual successor Direct-only preflight, the
already-correct Rules-Only evaluation, the expected Direct-LLM output
locations, the remaining 36+74=110 Direct calls, and the S2.12/S2.13 freeze
conditions.  It does not create an authorization and never claims that a
missing Direct-LLM result is complete.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SCOPE = ROOT / "configs/s2_12_active_method_scope_v1.json"
ACTIVE_LOCK = ROOT / "configs/s2_12_active_preflight_v2.json"
ACTIVE_REPORT = ROOT / "outputs/reports/s2_12_active_preflight_v2.json"
RULES_EVAL = ROOT / "data/results/s2_12_sun_rule_only_v1/evaluation.json"
RULES_MANIFEST = ROOT / "data/results/s2_12_sun_rule_only_v1/manifest.json"
RULES_PRED = ROOT / "data/predictions/s2_12_sun_rule_only_v1/predictions.json"
RULES_RUN_MANIFEST = ROOT / "data/predictions/s2_12_sun_rule_only_v1/manifest.json"
RULES_VERIFIER = ROOT / "scripts/verify_s2_12_sun_rule_only_v1.py"
DIRECT_VERIFIER = ROOT / "scripts/verify_s2_12_api_arm_v1.py"
S2_12_INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
DATASET_ID = "s2_11_barrientos_complex_corpus_36_v1"
DIRECT_EVAL = ROOT / "data/results/s2_12_direct_llm_v1/evaluation.json"
DIRECT_PRED = ROOT / "data/predictions/s2_12_direct_llm_v1/predictions.json"
DIRECT_MANIFEST = ROOT / "data/predictions/s2_12_direct_llm_v1/manifest.json"
SEP_C2_PREFLIGHT = ROOT / "outputs/reports/sep_c2_execution_preflight_v1.json"
GDPR_PREFLIGHT = ROOT / "outputs/reports/gdpr7_direct_llm_preflight_v1.json"
GDPR_FAKE_DIR = ROOT / "outputs/development/gdpr7_direct_llm_v1"
OUT = ROOT / "outputs/reports/s2_12_two_method_contract_v1.json"
OUT_MD = ROOT / "outputs/reports/s2_12_two_method_contract_v1.md"
OUT_MANIFEST = ROOT / "outputs/reports/s2_12_two_method_contract_v1.manifest.json"


class ContractFail(ValueError):
    """Fail-closed two-method contract build error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _binding(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractFail(f"binding file missing: {path.relative_to(ROOT)}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha(path),
        "byte_size": path.stat().st_size,
    }


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ContractFail(f"cannot load evidence verifier: {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _finite_unit(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _failed_checks(verification: Mapping[str, Any] | None) -> list[str]:
    failed: list[str] = []
    for check in (verification or {}).get("checks") or []:
        if not check.get("ok"):
            failed.append(str(check.get("name")))
    return failed


def _metrics_valid(evaluation: Mapping[str, Any] | None, method: str) -> bool:
    """Validate the fixed 36-row metric shape before ANY completion claim."""
    if not evaluation:
        return False
    metrics = evaluation.get("metrics") or {}
    if metrics.get("dataset_id") not in (None, DATASET_ID):
        return False
    if metrics.get("method_id") not in (None, method):
        return False
    overall = metrics.get("overall") or {}
    if overall.get("samples") != 36:
        return False
    span = ((overall.get("span_fields") or {}).get("overall") or {})
    modality = overall.get("modality_labels") or {}
    if modality.get("records") != 36:
        return False
    values = (
        span.get("precision"), span.get("recall"), span.get("f1"),
        modality.get("accuracy"), modality.get("macro_f1"),
    )
    return all(_finite_unit(value) for value in values)


def _method_evidence(method: str, run_manifest_path: Path,
                     predictions_path: Path,
                     evaluation: Mapping[str, Any] | None,
                     verifier_path: Path,
                     active_input: Mapping[str, Any],
                     verifier_arm: str | None = None) -> dict[str, Any]:
    """Run the existing independent verifier, then add the evidence checks the
    verifier does not itself expose (input binding, 36-row membership, metric
    shape).  No new governance layer is defined here; the verifier remains the
    authority for capsule/evaluation replay and frozen bindings."""
    evidence: dict[str, Any] = {
        "method": method,
        "verified": False,
        "verifier_path": verifier_path.relative_to(ROOT).as_posix(),
        "failed_checks": [],
        "input_binding_ok": False,
        "all_36_rows": False,
        "metrics_valid": _metrics_valid(evaluation, method),
        "requirements": [
            "independent verifier verified",
            "prediction input binding matches the frozen S2.12 input",
            "all 36 fixed S2.12 rows are present",
            "metrics contain finite 36-row span/modality values",
        ],
    }
    try:
        verifier = _load_module(f"sep_c2_{method}_evidence_verifier", verifier_path)
        verification = (verifier.verify(verifier_arm)
                        if verifier_arm is not None else verifier.verify())
        evidence["verified"] = verification.get("verified") is True
        evidence["checks_total"] = len(verification.get("checks") or [])
        evidence["failed_checks"] = _failed_checks(verification)
    except Exception as exc:  # fail closed and expose the exact loader/verifier error
        evidence["error"] = f"{type(exc).__name__}: {exc}"
        evidence["failed_checks"] = ["verifier_execution_error"]

    if run_manifest_path.is_file() and S2_12_INPUT.is_file():
        try:
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            binding = run_manifest.get("input_binding") or {}
            evidence["input_binding_ok"] = bool(
                binding.get("path") == str(active_input.get("path"))
                and binding.get("sha256") == active_input.get("sha256")
                and int(binding.get("records") or 0) == 36
                and _sha(S2_12_INPUT) == active_input.get("sha256")
            )
            evidence["run_manifest"] = _binding(run_manifest_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            evidence["input_binding_error"] = f"{type(exc).__name__}: {exc}"

    if predictions_path.is_file() and S2_12_INPUT.is_file():
        try:
            predictions = json.loads(predictions_path.read_text(encoding="utf-8"))
            rows = predictions.get("records") or []
            input_doc = json.loads(S2_12_INPUT.read_text(encoding="utf-8"))
            expected_ids = {str(row.get("sample_id"))
                            for row in input_doc.get("records") or []}
            row_ids = [row.get("sample_id") for row in rows
                       if isinstance(row, dict)]
            evidence["all_36_rows"] = bool(
                predictions.get("record_count") == 36
                and len(rows) == 36
                and len(row_ids) == 36
                and set(row_ids) == expected_ids
            )
            evidence["prediction_row_ids"] = len(row_ids)
            evidence["predictions"] = _binding(predictions_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            evidence["row_check_error"] = f"{type(exc).__name__}: {exc}"

    if evaluation is not None:
        evidence["evaluation"] = {
            "status": evaluation.get("status"),
            "dataset_id": evaluation.get("dataset_id"),
            "arm": evaluation.get("arm"),
        }
    return evidence


def _write_text_md(report: Mapping[str, Any]) -> bytes:
    c = report["comparison"]
    calls = report["call_plan"]["remaining_calls"]
    missing = report["zero_api_continuation"]["real_results_missing"]
    lines = [
        "# S2.12 Two-Method Execution Contract (SEP-C2)",
        "",
        f"- status: **{report['status']}**",
        "- active methods: `sun_rule_only`, `direct_llm`",
        "- cancelled: `sun_llm_fallback` (Rules+LLM-Repair); 27 F-1/F-2/F-3 calls removed and not reassignable",
        f"- remaining Direct calls: S2.12 {calls['s2_12_direct']} + GDPR {calls['gdpr7_direct']} = **{calls['total']}**; calls made by this contract build: **{report['call_plan']['real_api_calls_made']}**",
        f"- S2.12 two-method evidence complete: **{report['freeze']['s2_12_complete']}**",
        f"- S2.13 freeze checkpoint complete: **{report['freeze']['s2_13_complete']}** (eligible: **{report['freeze']['s2_13_eligible_for_freeze_check']}**)",
        "",
        "## Comparison evidence",
        "",
        f"- status: `{c['status']}`",
        f"- two-method comparison complete: **{c['complete']}**",
        "- Direct-LLM dependency on the cancelled repair ledger/results: **false**",
    ]
    for method in ("sun_rule_only", "direct_llm"):
        e = (c.get("evidence") or {}).get(method) or {}
        lines.append(
            f"- `{method}`: verified={e.get('verified')}, "
            f"input_binding_ok={e.get('input_binding_ok')}, "
            f"all_36_rows={e.get('all_36_rows')}, "
            f"metrics_valid={e.get('metrics_valid')}"
        )
        if e.get("failed_checks"):
            lines.append(f"  - failed checks: {', '.join(e['failed_checks'])}")
    lines += [
        f"- blockers: {', '.join(c['blockers']) if c['blockers'] else 'none'}",
        "",
        "## Remaining real evidence",
        "",
    ]
    if missing:
        for item in missing:
            lines.append(f"- {item}")
    else:
        lines.append("- none in the current two-method scope")
    lines += [
        "",
        "## Boundary",
        "",
        report["claim_boundary"],
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def compare_two_methods(rules_eval: Mapping[str, Any] | None,
                        direct_eval: Mapping[str, Any] | None,
                        *,
                        rules_evidence: Mapping[str, Any] | None = None,
                        direct_evidence: Mapping[str, Any] | None = None
                        ) -> dict[str, Any]:
    """Compare the two active methods only when both have full evidence.

    The status literal and dataset id are necessary but deliberately NOT
    sufficient.  The caller must supply the summaries produced by the existing
    independent verifiers plus input-binding, 36-row, and metric-shape checks.
    A cancelled repair arm is never consulted.
    """
    rules_status_ok = bool(
        rules_eval
        and rules_eval.get("status") == "verified_zero_api_arm_complete"
        and rules_eval.get("dataset_id") == DATASET_ID
    )
    direct_status_ok = bool(
        direct_eval
        and direct_eval.get("status") == "verified_direct_llm_arm_complete"
        and direct_eval.get("dataset_id") == DATASET_ID
    )

    def _evidence_complete(evidence: Mapping[str, Any] | None) -> bool:
        e = evidence or {}
        return bool(e.get("verified") is True
                    and e.get("input_binding_ok") is True
                    and e.get("all_36_rows") is True
                    and e.get("metrics_valid") is True)

    rules_ok = rules_status_ok and _evidence_complete(rules_evidence)
    direct_ok = direct_status_ok and _evidence_complete(direct_evidence)
    blockers: list[str] = []

    if not rules_status_ok:
        blockers.append("rules_only_evaluation_missing_or_not_complete")
    if not direct_status_ok:
        blockers.append("direct_llm_evaluation_missing_or_not_complete")
    for label, status_ok, evidence in (
        ("rules_only", rules_status_ok, rules_evidence),
        ("direct_llm", direct_status_ok, direct_evidence),
    ):
        current = evidence or {}
        if not status_ok:
            continue
        if current.get("verified") is not True:
            failed = current.get("failed_checks") or []
            suffix = (":" + ",".join(str(item) for item in failed[:3])
                      if failed else "")
            blockers.append(f"{label}_evidence_verifier_failed{suffix}")
        if current.get("input_binding_ok") is not True:
            blockers.append(f"{label}_input_binding_missing_or_mismatch")
        if current.get("all_36_rows") is not True:
            blockers.append(f"{label}_fixed_36_row_population_missing")
        if current.get("metrics_valid") is not True:
            blockers.append(f"{label}_metrics_missing_or_invalid")
    # De-duplicate while retaining order.
    blockers = list(dict.fromkeys(blockers))

    def _overall(doc: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not doc or not _metrics_valid(doc, str(doc.get("arm") or "")):
            return None
        metrics = doc.get("metrics") or {}
        overall = metrics.get("overall") or {}
        span = (overall.get("span_fields") or {}).get("overall") or {}
        modality = overall.get("modality_labels") or {}
        return {
            "span_precision": span.get("precision"),
            "span_recall": span.get("recall"),
            "span_f1": span.get("f1"),
            "modality_accuracy": modality.get("accuracy"),
            "modality_macro_f1": modality.get("macro_f1"),
        }

    rules_overall = _overall(rules_eval)
    direct_overall = _overall(direct_eval)
    deltas = None
    if rules_overall and direct_overall:
        deltas = {
            key: (
                None if direct_overall.get(key) is None
                or rules_overall.get(key) is None
                else round(float(direct_overall[key]) - float(rules_overall[key]), 6)
            )
            for key in rules_overall
        }

    def _public_evidence(evidence: Mapping[str, Any] | None) -> dict[str, Any]:
        current = evidence or {}
        return {
            "verified": current.get("verified") is True,
            "verifier_path": current.get("verifier_path"),
            "checks_total": current.get("checks_total"),
            "failed_checks": list(current.get("failed_checks") or []),
            "input_binding_ok": current.get("input_binding_ok") is True,
            "all_36_rows": current.get("all_36_rows") is True,
            "prediction_row_ids": current.get("prediction_row_ids"),
            "metrics_valid": current.get("metrics_valid") is True,
            "error": current.get("error"),
        }

    complete = rules_ok and direct_ok
    return {
        "status": "complete_two_method_comparison" if complete else "pending_direct_llm",
        "complete": complete,
        "active_methods": ["sun_rule_only", "direct_llm"],
        "cancelled_methods": ["sun_llm_fallback"],
        "fallback_results_or_ledger_required": False,
        "three_method_requirement_removed": True,
        "completion_requires": [
            "existing independent verifier verified",
            "prediction input binding matches the frozen S2.12 input",
            "all 36 fixed S2.12 rows present, including explicit failures",
            "finite 36-row span/modality metrics present",
        ],
        "evidence": {
            "sun_rule_only": _public_evidence(rules_evidence),
            "direct_llm": _public_evidence(direct_evidence),
        },
        "metrics": {
            "sun_rule_only": rules_overall,
            "direct_llm": direct_overall,
            "direct_minus_rules_only": deltas,
        },
        "blockers": blockers,
    }


def build_contract() -> dict[str, Any]:
    required = (
        SCOPE, ACTIVE_LOCK, ACTIVE_REPORT, RULES_EVAL, RULES_MANIFEST,
        RULES_PRED, RULES_RUN_MANIFEST, RULES_VERIFIER, DIRECT_VERIFIER,
        S2_12_INPUT, SEP_C2_PREFLIGHT, GDPR_PREFLIGHT,
    )
    for path in required:
        if not path.is_file():
            raise ContractFail(f"required asset missing: {path.relative_to(ROOT)}")
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    active_lock = json.loads(ACTIVE_LOCK.read_text(encoding="utf-8"))
    active_report = json.loads(ACTIVE_REPORT.read_text(encoding="utf-8"))
    if scope.get("active_methods") != ["sun_rule_only", "direct_llm"]:
        raise ContractFail("active method scope drift")
    if "sun_llm_fallback" not in (scope.get("cancelled_methods") or {}):
        raise ContractFail("cancelled repair arm missing from scope")
    if active_lock.get("arms", {}).keys() != {"direct_llm"}:
        raise ContractFail("active lock is not direct-only")
    if active_report.get("arms", {}).keys() != {"direct_llm"}:
        raise ContractFail("active report is not direct-only")
    if active_report.get("status") != "payloads_locked_two_method_no_api_authorization":
        raise ContractFail("active preflight report status drift")

    active_input = active_report["input"]
    if _sha(S2_12_INPUT) != active_input.get("sha256"):
        raise ContractFail("frozen S2.12 input hash drift")
    input_doc = json.loads(S2_12_INPUT.read_text(encoding="utf-8"))
    if input_doc.get("record_count") != 36 or len(input_doc.get("records") or []) != 36:
        raise ContractFail("frozen S2.12 input does not contain 36 records")

    rules_eval = json.loads(RULES_EVAL.read_text(encoding="utf-8"))
    direct_eval = (json.loads(DIRECT_EVAL.read_text(encoding="utf-8"))
                   if DIRECT_EVAL.is_file() else None)

    # Reuse the existing independent verifiers; do not re-implement their
    # capsule/evaluation replay checks.  Missing Direct evidence fails closed.
    rules_evidence = _method_evidence(
        "sun_rule_only", RULES_RUN_MANIFEST, RULES_PRED, rules_eval,
        RULES_VERIFIER, active_input,
    )
    direct_evidence = _method_evidence(
        "direct_llm", DIRECT_MANIFEST, DIRECT_PRED, direct_eval,
        DIRECT_VERIFIER, active_input, verifier_arm="direct_llm",
    )
    comparison = compare_two_methods(
        rules_eval, direct_eval,
        rules_evidence=rules_evidence, direct_evidence=direct_evidence,
    )
    if direct_eval is None and DIRECT_PRED.is_file():
        comparison["blockers"].append(
            "direct_llm_predictions_present_but_evaluation_missing")
    comparison["blockers"] = list(dict.fromkeys(comparison["blockers"]))

    preflight = json.loads(SEP_C2_PREFLIGHT.read_text(encoding="utf-8"))
    process_env = (preflight.get("checks") or {}).get("process_environment") or {}
    s2_12_complete = comparison["complete"]
    freeze = {
        "s2_12_complete": s2_12_complete,
        "s2_13_complete": False,
        "s2_13_eligible_for_freeze_check": s2_12_complete,
        "cancelled_repair_arm_required": False,
        "three_method_completeness_required_for_current_scope": False,
        "historical_three_method_formal_capsules_retained": True,
        "other_input_gold_freeze_conditions_unchanged": True,
        "required_evidence_for_two_method_completion": [
            "Rules-Only and Direct-LLM real predictions on the same frozen 36 S2.12 inputs",
            "same-caliber evaluation against frozen S2.11 Gold and evaluator v2; the cancelled repair ledger/results are not inputs",
            "existing independent verifier replay, frozen input binding, fixed 36-row population, and finite metrics",
        ],
        "cancelled_repair_arm_not_a_completion_condition": True,
        "blockers": list(comparison["blockers"]),
        "note": (
            "S2.13 freeze remains a separate checkpoint and is never auto-marked "
            "complete by this builder. The only current-scope blocker is the "
            "two-method evidence chain; the cancelled repair arm is not consulted."
            if s2_12_complete else
            "S2.13 is not marked complete and does not wait for the cancelled "
            "repair arm; it remains blocked until complete verified two-method "
            "evidence (36-row Direct-LLM prediction capsule, same-caliber "
            "evaluation, and comparison) exists."
        ),
    }

    direct_payload_set_hash = _sha_bytes(json.dumps(
        sorted(row["request_body_sha256"]
               for row in active_report["arms"]["direct_llm"]["calls"]),
        separators=(",", ":")).encode("utf-8"))
    gdpr_preflight = json.loads(GDPR_PREFLIGHT.read_text(encoding="utf-8"))
    gdpr_planned = int((gdpr_preflight.get("global") or {}).get("planned_calls")
                       or (gdpr_preflight.get("summary") or {}).get("total") or 74)
    remaining_s2_direct = 0 if s2_12_complete else 36
    remaining_total = remaining_s2_direct + gdpr_planned
    observed_direct_calls = None
    if direct_eval is not None:
        cost = direct_eval.get("cost") or {}
        observed_direct_calls = {
            "llm_api_calls": cost.get("llm_api_calls"),
            "network_calls": cost.get("network_calls"),
            "actual_cost_usd": cost.get("actual_cost_usd"),
        }

    command_prefix = "python formal_experiment/scripts/"
    commands = {
        "s2_12_direct": [
            command_prefix + "run_s2_12_direct_llm_v1.py "
            "--runtime-home <corenlp-home> --transport real --allow-llm "
            "--auth-file <successor-two-method-direct-authorization.json> "
            "--stage-id D-CAL "
            "--output-dir formal_experiment/outputs/development/s2_12_direct_llm_stage_dcal_v1 "
            "--raw-dir formal_experiment/outputs/development/s2_12_direct_llm_raw_dcal_v1",
            command_prefix + "run_s2_12_direct_llm_v1.py "
            "--runtime-home <corenlp-home> --transport real --allow-llm "
            "--auth-file <successor-two-method-direct-authorization.json> "
            "--stage-id D-REST "
            "--resume-from-ledger formal_experiment/outputs/development/s2_12_direct_llm_stage_dcal_v1.ledger.jsonl "
            "--output-dir formal_experiment/outputs/development/s2_12_direct_llm_stage_drest_v1 "
            "--raw-dir formal_experiment/outputs/development/s2_12_direct_llm_raw_drest_v1",
        ],
        "s2_12_finalize": command_prefix + "finalize_s2_12_arm_v1.py "
        "--arm direct_llm --runtime-home <corenlp-home> "
        "--raw-dir formal_experiment/outputs/development/s2_12_direct_llm_raw_dcal_v1 "
        "--raw-dir formal_experiment/outputs/development/s2_12_direct_llm_raw_drest_v1 "
        "--ledger formal_experiment/outputs/development/s2_12_direct_llm_stage_drest_v1.ledger.jsonl "
        "--output-dir formal_experiment/data/predictions/s2_12_direct_llm_v1",
        "s2_12_evaluate": command_prefix + "evaluate_s2_12_api_arm_v1.py "
        "--arm direct_llm --evaluate",
        "gdpr7_direct": command_prefix + "run_gdpr7_direct_llm_v1.py "
        "--contract-file formal_experiment/configs/ablations/gdpr7_direct_llm_execution_contract_v1.json "
        "--authorization-file <successor-gdpr7-direct-authorization-event.json> "
        "--raw-dir formal_experiment/outputs/development/gdpr7_direct_llm_raw_real_v1 "
        "--capsule-dir formal_experiment/outputs/development/gdpr7_direct_llm_real_v1",
        "gdpr7_promotion": command_prefix + "promote_gdpr7_direct_llm_arm_v1.py --apply",
        "contract_check": command_prefix + "build_s2_12_two_method_contract_v1.py --check",
    }

    missing: list[str] = []
    if not s2_12_complete:
        missing.extend([
            "S2.12 Direct-LLM D-CAL/D-REST real responses (36 calls; no fake substitution)",
            "S2.12 Direct-LLM finalized prediction capsule at data/predictions/s2_12_direct_llm_v1",
            "S2.12 Direct-LLM evaluation at data/results/s2_12_direct_llm_v1/evaluation.json",
            "S2.12 two-method Rules-Only vs Direct-LLM comparison",
        ])
    missing.extend([
        "GDPR-7 Direct-LLM real 74-call capsule/promotion (fake v1 74 rows excluded)",
        "successor two-method external-send authorization and automatic approval (only if remaining calls reveal a new external-send blocker)",
    ])

    claim_boundary = (
        "This contract records complete, independently verified two-method S2.12 "
        "evidence from frozen capsules. It does not perform the separate S2.13 "
        "freeze checkpoint, does not authorize or run GDPR Direct-LLM calls, and "
        "does not restart the cancelled Rules+LLM-Repair arm."
        if s2_12_complete else
        "This contract and its evidence are implementation/readiness work only. "
        "No complete real S2.12 Direct-LLM or GDPR API result is recorded here; "
        "S2.12 and S2.13 are not complete. The cancelled Rules+LLM-Repair arm is "
        "not a dependency and must not be restarted."
    )

    report = {
        "schema_version": "s2_12_two_method_contract@1.0.0",
        "report_id": "s2_12_two_method_contract_v1",
        "status": (
            "complete_two_method_contract"
            if s2_12_complete else
            "partial_two_method_contract_pending_direct_llm"
        ),
        "scope_id": "sep_c2_two_method_v1",
        "active_methods": ["sun_rule_only", "direct_llm"],
        "cancelled_methods": {
            "sun_llm_fallback": {
                "paper_label": "Rules+LLM-Repair",
                "cancelled_stages": ["F-1", "F-2", "F-3"],
                "cancelled_calls": 27,
                "must_not_run": True,
                "must_not_be_reassigned": True,
                "historical_provenance_retained": True,
            }
        },
        "current_state": {
            "s2_12_direct_evidence_complete": s2_12_complete,
            "s2_12_direct_real_calls_observed": observed_direct_calls,
            "two_method_comparison_complete": comparison["complete"],
            "s2_13_freeze_eligible": s2_12_complete,
            "cancelled_repair_arm_used": False,
        },
        "input_request_bindings": {
            "s2_12_input": {
                "path": active_input["path"],
                "sha256": active_input["sha256"],
                "records": 36,
            },
            "s2_12_input_file": _binding(S2_12_INPUT),
            "s2_12_active_preflight_lock": _binding(ACTIVE_LOCK),
            "s2_12_active_preflight_report": _binding(ACTIVE_REPORT),
            "rules_only_predictions": _binding(RULES_PRED),
            "rules_only_prediction_manifest": _binding(RULES_RUN_MANIFEST),
            "s2_12_direct_prompt_sha256": active_lock["arms"]["direct_llm"]["prompt_sha256"],
            "s2_12_direct_payload_set_sha256": direct_payload_set_hash,
            "s2_12_direct_payload_count": 36,
            "gdpr7_input": _binding(ROOT / "data/input/gdpr7_stage2_input_v1.json"),
            "gdpr7_preflight_report": _binding(GDPR_PREFLIGHT),
            "gdpr7_planned_calls": gdpr_planned,
        },
        "output_dirs": {
            "s2_12_stage_raw_dcal": "outputs/development/s2_12_direct_llm_raw_dcal_v1",
            "s2_12_stage_raw_drest": "outputs/development/s2_12_direct_llm_raw_drest_v1",
            "s2_12_stage_capsule_dcal": "outputs/development/s2_12_direct_llm_stage_dcal_v1",
            "s2_12_stage_capsule_drest": "outputs/development/s2_12_direct_llm_stage_drest_v1",
            "s2_12_predictions": "data/predictions/s2_12_direct_llm_v1",
            "s2_12_results": "data/results/s2_12_direct_llm_v1",
            "gdpr7_raw_real": "outputs/development/gdpr7_direct_llm_raw_real_v1",
            "gdpr7_capsule_real": "outputs/development/gdpr7_direct_llm_real_v1",
            "gdpr7_fake_rehearsal_excluded": "outputs/development/gdpr7_direct_llm_v1",
        },
        "call_plan": {
            "remaining_calls": {
                "s2_12_direct": remaining_s2_direct,
                "gdpr7_direct": gdpr_planned,
                "total": remaining_total,
            },
            "s2_12_direct_stages": {"D-CAL": 1, "D-REST": 35},
            "s2_12_direct_completed_observed": (36 if s2_12_complete else 0),
            "cancelled_repair_calls": 27,
            "cancelled_repair_calls_reassigned": False,
            "real_api_calls_made": 0,
            "real_api_calls_made_meaning": "new calls made by this zero-API contract build; observed capsule calls are reported in current_state",
            "real_api_authorization_created": False,
            "retry": 0,
        },
        "comparison": comparison,
        "freeze": freeze,
        "execution_commands": commands,
        "gdpr7_boundary": {
            "fake_rehearsal_dir": "outputs/development/gdpr7_direct_llm_v1",
            "fake_rows": 74,
            "fake_network_calls": 0,
            "fake_is_not_real_prediction_or_promotion_source": True,
            "real_raw_dir": "outputs/development/gdpr7_direct_llm_raw_real_v1",
            "real_capsule_dir": "outputs/development/gdpr7_direct_llm_real_v1",
            "formal_arm_home": "data/predictions/gdpr7_direct_llm_v1",
        },
        "authorization_status": {
            "api_authorized": False,
            "s2_12_external_send_no_longer_needed": s2_12_complete,
            "existing_137_confirmation_scope_superseded": True,
            "current_cancellation_is_not_external_send_authorization": True,
            "new_authorization_file_created_this_round": False,
            "automatic_external_transmission_approval_blocker_active": bool(
                preflight.get("scope_update_2026_09_14", {}).get(
                    "automatic_external_transmission_approval_blocker_resolved") is False),
            "credentials": {
                "process_environment_ready_after_temporary_nonsecret_configuration": bool(
                    process_env.get("offline_ready_after_temporary_nonsecret_configuration")),
                "api_key_present": bool(process_env.get("api_key_present")),
                "credential_value_printed": False,
                "project_env_read": False,
                "remote_authentication_not_yet_tested": bool(
                    process_env.get("remote_authentication_not_yet_tested")),
            },
            "note": (
                "S2.12 now has complete verified evidence, so no new S2.12 "
                "external-send authorization is needed. This build itself made "
                "zero new calls. GDPR-7 remains a separate scope."
                if s2_12_complete else
                "The credential precondition is documented as present from the "
                "offline re-check; it is not a send authorization and does not "
                "clear the external-transmission approval blocker."
            ),
        },
        "zero_api_continuation": {
            "audit_project_required": True,
            "real_api_calls": 0,
            "network_calls": 0,
            "observed_s2_12_direct": observed_direct_calls,
            "real_results_missing": missing,
            "released_scope": "Rules-Only and Direct-LLM; the cancelled 27 repair calls remain removed",
        },
        "claim_boundary": claim_boundary,
        "reproduce_command": (
            "python formal_experiment/scripts/build_s2_12_two_method_contract_v1.py "
            "--check"
        ),
    }
    report["input_request_bindings"]["rules_only_evaluation"] = _binding(RULES_EVAL)
    if DIRECT_EVAL.is_file():
        report["input_request_bindings"]["direct_llm_evaluation"] = _binding(DIRECT_EVAL)
    if DIRECT_PRED.is_file():
        report["input_request_bindings"]["direct_llm_predictions"] = _binding(DIRECT_PRED)
    if DIRECT_MANIFEST.is_file():
        report["input_request_bindings"]["direct_llm_prediction_manifest"] = _binding(DIRECT_MANIFEST)
    return report


def build_artifacts() -> dict[Path, bytes]:
    report = build_contract()
    report_bytes = _json_bytes(report)
    md_bytes = _write_text_md(report)
    manifest = {
        "schema_version": "s2_12_two_method_contract_manifest@1.0.0",
        "report": {
            "path": "outputs/reports/s2_12_two_method_contract_v1.json",
            "sha256": _sha_bytes(report_bytes),
            "byte_size": len(report_bytes),
        },
        "report_md": {
            "path": "outputs/reports/s2_12_two_method_contract_v1.md",
            "sha256": _sha_bytes(md_bytes),
            "byte_size": len(md_bytes),
        },
        "bindings": {
            "active_scope": _binding(SCOPE),
            "active_preflight_lock": _binding(ACTIVE_LOCK),
            "active_preflight_report": _binding(ACTIVE_REPORT),
            "s2_12_input": _binding(S2_12_INPUT),
            "rules_only_evaluation": _binding(RULES_EVAL),
            "rules_only_predictions": _binding(RULES_PRED),
            "rules_only_prediction_manifest": _binding(RULES_RUN_MANIFEST),
            "sep_c2_execution_preflight": _binding(SEP_C2_PREFLIGHT),
            "gdpr7_preflight": _binding(GDPR_PREFLIGHT),
        },
        "builder": _binding(Path(__file__).resolve()),
        "zero_api": {"new_llm_api_calls": 0, "new_network_calls": 0},
    }
    for key, path in (
        ("direct_llm_evaluation", DIRECT_EVAL),
        ("direct_llm_predictions", DIRECT_PRED),
        ("direct_llm_prediction_manifest", DIRECT_MANIFEST),
    ):
        if path.is_file():
            manifest["bindings"][key] = _binding(path)
    return {OUT: report_bytes, OUT_MD: md_bytes, OUT_MANIFEST: _json_bytes(manifest)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        artifacts = build_artifacts()
        if args.publish:
            existing = [path for path in artifacts if path.exists()]
            if existing:
                raise ContractFail(f"refusing to overwrite existing contract: {existing}")
            for target, payload in artifacts.items():
                target.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
                    stage = Path(stream.name)
                    stream.write(payload)
                stage.replace(target)
        else:
            for path, expected in artifacts.items():
                if not path.is_file() or path.read_bytes() != expected:
                    raise ContractFail(f"contract replay differs: {path.relative_to(ROOT)}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"S2.12 two-method contract refused: {exc}")
        return 2
    report = json.loads(artifacts[OUT].decode("utf-8"))
    print(
        "S2.12 two-method contract verified: active=Rules-Only/Direct-LLM; "
        "cancelled=Rules+LLM-Repair; comparison_complete="
        f"{report['comparison']['complete']}; "
        f"remaining_calls={report['call_plan']['remaining_calls']['total']}; "
        "real_api_calls_this_build=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

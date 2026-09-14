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
import json
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


def _write_text_md(report: Mapping[str, Any]) -> bytes:
    c = report["comparison"]
    lines = [
        "# S2.12 Two-Method Execution Contract (SEP-C2)",
        "",
        f"- status: **{report['status']}**",
        "- active methods: `sun_rule_only`, `direct_llm`",
        "- cancelled: `sun_llm_fallback` (Rules+LLM-Repair); 27 F-1/F-2/F-3 calls removed and not reassignable",
        f"- remaining Direct calls: S2.12 36 + GDPR 74 = **110**; real calls made this round: **0**",
        f"- S2.12 complete: **{report['freeze']['s2_12_complete']}**",
        f"- S2.13 complete: **{report['freeze']['s2_13_complete']}**",
        "",
        "## Comparison",
        "",
        f"- status: `{c['status']}`",
        f"- two-method comparison complete: **{c['complete']}**",
        "- Direct-LLM dependency on the cancelled repair ledger/results: **false**",
        f"- blockers: {', '.join(c['blockers']) if c['blockers'] else 'none'}",
        "",
        "## Remaining real evidence",
        "",
    ]
    for item in report["zero_api_continuation"]["real_results_missing"]:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Boundary",
        "",
        report["claim_boundary"],
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def compare_two_methods(rules_eval: Mapping[str, Any] | None,
                        direct_eval: Mapping[str, Any] | None) -> dict[str, Any]:
    """Pure comparison helper used by tests and by the file-based builder."""
    rules_ok = bool(
        rules_eval
        and rules_eval.get("status") == "verified_zero_api_arm_complete"
        and rules_eval.get("dataset_id") == "s2_11_barrientos_complex_corpus_36_v1"
    )
    direct_ok = bool(
        direct_eval
        and direct_eval.get("status") == "verified_direct_llm_arm_complete"
        and direct_eval.get("dataset_id") == "s2_11_barrientos_complex_corpus_36_v1"
    )
    blockers: list[str] = []
    if not rules_ok:
        blockers.append("rules_only_evaluation_missing_or_not_complete")
    if not direct_ok:
        blockers.append("direct_llm_evaluation_missing_or_not_complete")
    complete = rules_ok and direct_ok

    def _overall(doc: Mapping[str, Any] | None) -> dict[str, Any] | None:
        if not doc:
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
                None if direct_overall.get(key) is None or rules_overall.get(key) is None
                else round(float(direct_overall[key]) - float(rules_overall[key]), 6)
            )
            for key in rules_overall
        }
    return {
        "status": "complete_two_method_comparison" if complete else "pending_direct_llm",
        "complete": complete,
        "active_methods": ["sun_rule_only", "direct_llm"],
        "cancelled_methods": ["sun_llm_fallback"],
        "fallback_results_or_ledger_required": False,
        "three_method_requirement_removed": True,
        "metrics": {
            "sun_rule_only": rules_overall,
            "direct_llm": direct_overall,
            "direct_minus_rules_only": deltas,
        },
        "blockers": blockers,
    }


def build_contract() -> dict[str, Any]:
    for path in (SCOPE, ACTIVE_LOCK, ACTIVE_REPORT, RULES_EVAL, RULES_MANIFEST,
                 SEP_C2_PREFLIGHT, GDPR_PREFLIGHT):
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

    rules_eval = json.loads(RULES_EVAL.read_text(encoding="utf-8"))
    direct_eval = json.loads(DIRECT_EVAL.read_text(encoding="utf-8")) if DIRECT_EVAL.is_file() else None
    direct_pred_complete = bool(
        DIRECT_PRED.is_file()
        and DIRECT_MANIFEST.is_file()
        and json.loads(DIRECT_MANIFEST.read_text(encoding="utf-8")).get("capsule_status") == "complete"
    )
    comparison = compare_two_methods(rules_eval, direct_eval)
    if direct_eval is None and direct_pred_complete:
        comparison["blockers"].append("direct_llm_predictions_present_but_evaluation_missing")

    preflight = json.loads(SEP_C2_PREFLIGHT.read_text(encoding="utf-8"))
    process_env = (preflight.get("checks") or {}).get("process_environment") or {}
    auth_pending = (preflight.get("scope_update_2026_09_14") or {}).get(
        "two_method_machine_contract_adaptation_pending", True)
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
            "two-method comparison record and S2.12 completion checkpoint before S2.13 freeze",
        ],
        "cancelled_repair_arm_not_a_completion_condition": True,
        "blockers": list(comparison["blockers"]),
        "note": (
            "S2.13 is not marked complete and does not wait for the cancelled "
            "repair arm; it remains blocked until Direct-LLM predictions, "
            "evaluation, and the two-method comparison exist."
        ),
    }

    direct_payload_set_hash = _sha_bytes(json.dumps(
        sorted(row["request_body_sha256"]
               for row in active_report["arms"]["direct_llm"]["calls"]),
        separators=(",", ":")).encode("utf-8"))
    gdpr_preflight = json.loads(GDPR_PREFLIGHT.read_text(encoding="utf-8"))
    gdpr_planned = int((gdpr_preflight.get("global") or {}).get("planned_calls")
                       or (gdpr_preflight.get("summary") or {}).get("total") or 74)
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
        "input_request_bindings": {
            "s2_12_input": {
                "path": active_report["input"]["path"],
                "sha256": active_report["input"]["sha256"],
                "records": 36,
            },
            "s2_12_active_preflight_lock": _binding(ACTIVE_LOCK),
            "s2_12_active_preflight_report": _binding(ACTIVE_REPORT),
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
                "s2_12_direct": 36,
                "gdpr7_direct": 74,
                "total": 110,
            },
            "s2_12_direct_stages": {"D-CAL": 1, "D-REST": 35},
            "cancelled_repair_calls": 27,
            "cancelled_repair_calls_reassigned": False,
            "real_api_calls_made": 0,
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
                "The credential precondition is documented as present from the "
                "offline re-check; it is not a send authorization and does not "
                "clear the external-transmission approval blocker."
            ),
        },
        "zero_api_continuation": {
            "audit_project_required": True,
            "real_api_calls": 0,
            "network_calls": 0,
            "real_results_missing": [
                "S2.12 Direct-LLM D-CAL/D-REST real responses (36 calls; no fake substitution)",
                "S2.12 Direct-LLM finalized prediction capsule at data/predictions/s2_12_direct_llm_v1",
                "S2.12 Direct-LLM evaluation at data/results/s2_12_direct_llm_v1/evaluation.json",
                "S2.12 two-method Rules-Only vs Direct-LLM comparison",
                "GDPR-7 Direct-LLM real 74-call capsule/promotion (fake v1 74 rows excluded)",
                "successor two-method external-send authorization and automatic approval",
            ],
            "released_scope": "Rules-Only and Direct-LLM; the cancelled 27 repair calls remain removed",
        },
        "claim_boundary": (
            "This contract and its evidence are implementation/readiness work only. "
            "No real Direct-LLM or GDPR API result exists; S2.12 and S2.13 are not "
            "complete. The cancelled Rules+LLM-Repair arm is not a dependency and "
            "must not be restarted."
        ),
        "reproduce_command": (
            "python formal_experiment/scripts/build_s2_12_two_method_contract_v1.py "
            "--check"
        ),
    }
    report["input_request_bindings"]["rules_only_evaluation"] = _binding(RULES_EVAL)
    if DIRECT_EVAL.is_file():
        report["input_request_bindings"]["direct_llm_evaluation"] = _binding(DIRECT_EVAL)
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
            "rules_only_evaluation": _binding(RULES_EVAL),
            "sep_c2_execution_preflight": _binding(SEP_C2_PREFLIGHT),
            "gdpr7_preflight": _binding(GDPR_PREFLIGHT),
        },
        "builder": _binding(Path(__file__).resolve()),
        "zero_api": {"new_llm_api_calls": 0, "new_network_calls": 0},
    }
    if DIRECT_EVAL.is_file():
        manifest["bindings"]["direct_llm_evaluation"] = _binding(DIRECT_EVAL)
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
    print(
        "S2.12 two-method contract verified: active=Rules-Only/Direct-LLM; "
        "cancelled=Rules+LLM-Repair; direct pending; real_api_calls=0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

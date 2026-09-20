# -*- coding: utf-8 -*-
"""Prepare offline execution capsules and frozen contracts for the SEP-C3
definition-targeted refinement (BASE vs R_DEF).

This script never sends a model request.  It writes a deterministic schedule,
rendered request bodies, a budget/cost gate, an evaluation contract, an
execution plan, a leakage-audit handoff, and an authorization request.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402
import audit_sep_c3_definition_targeted_leakage_v1 as leakage  # noqa: E402


SUITE_ID = "SEP-C3-DEFINITION-TARGETED-REFINEMENT-001"
ARMS = ("BASE", "R_DEF")
REPEAT_ID = "repeat-01"
PLANNED_CALLS = 84
CALL_CAP = 84

PANEL_PATH = ROOT / "configs" / "sep_c3_definition_targeted_panel_v1.json"
PANEL_MANIFEST_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_panel_manifest_v1.json"
)
SCHEDULE_PATH = (
    ROOT / "configs" / "sep_c3_definition_targeted_schedule_v1.json"
)
BUDGET_PATH = ROOT / "configs" / "sep_c3_definition_targeted_budget_v1.json"
EVALUATION_CONTRACT_PATH = (
    ROOT / "configs"
    / "sep_c3_definition_targeted_evaluation_contract_v1.json"
)
EVIDENCE_DIR = (
    ROOT / "outputs" / "evidence"
    / "sep_c3_definition_targeted_refinement_v1"
)
OFFLINE_REQUESTS_PATH = EVIDENCE_DIR / "offline_requests.jsonl"
REQUEST_MANIFEST_PATH = EVIDENCE_DIR / "request_manifest.json"
BUDGET_REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_budget_v1.json"
)
BUDGET_REPORT_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_budget_v1.md"
)
EVALUATION_CONTRACT_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_evaluation_contract_v1.md"
)
EXECUTION_PLAN_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_execution_plan_v1.md"
)
AUTHORIZATION_REQUEST_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_authorization_request_v1.json"
)
AUTHORIZATION_REQUEST_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_authorization_request_v1.md"
)

PRICE_SNAPSHOT = {
    "currency": "USD",
    "mode_used_for_gate": "peak_conservative",
    "input_cache_miss_per_million": 1.32,
    "output_per_million": 3.96,
    "source_url": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
    "verified_at_utc": "2026-08-30T00:00:00Z",
    "note": "Reuses the frozen SEP-C3 project price snapshot; no online re-check.",
}


class PreparationError(RuntimeError):
    """A frozen contract cannot be prepared safely."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _load_panel() -> dict[str, Any]:
    panel = _read_json(PANEL_PATH)
    if panel.get("status") != "FROZEN_BEFORE_NEW_API":
        raise PreparationError("panel is not frozen before new API")
    accounting = panel.get("panel_accounting") or {}
    if int(accounting.get("unique_sample_count_N", 0)) != 42:
        raise PreparationError("panel N != 42")
    if int(accounting.get("expected_api_calls", {}).get("total_new", 0)) != 84:
        raise PreparationError("panel expected calls != 84")
    return panel


def _sample_text_map() -> dict[str, str]:
    rows = core.samples(core.SAMPLES_PER_ARM)
    return {str(row["sample_id"]): str(row["text"]) for row in rows}


def _request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    prompt = dr.render_definition_prompt(arm)
    messages = prompt.request_messages(sample_id, source_text)
    return {
        "model": core.MODEL_ALIAS,
        "messages": messages,
        "temperature": core.TEMPERATURE,
        "top_p": core.TOP_P,
        "max_tokens": core.MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def _build_schedule(panel: Mapping[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    execution_index = 0
    for sample_id in panel["selected_sample_ids"]:
        for arm_order, arm in enumerate(ARMS, start=1):
            execution_index += 1
            entries.append({
                "execution_index": execution_index,
                "sample_id": str(sample_id),
                "arm": arm,
                "arm_order_within_sample": arm_order,
                "repeat_id": REPEAT_ID,
            })
    entries_sha = _sha256_text(_canonical_json(entries))
    return {
        "schema_version": "sep_c3_definition_targeted_schedule@1.0.0",
        "suite_id": SUITE_ID,
        "status": "FROZEN_BEFORE_NEW_API",
        "repeat_id": REPEAT_ID,
        "scheme": "panel_sample_order_with_fixed_arm_order",
        "panel_path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
        "panel_sha256": _sha256_file(PANEL_PATH),
        "sample_count": len(panel["selected_sample_ids"]),
        "arms": list(ARMS),
        "planned_calls": len(entries),
        "entries": entries,
        "entries_sha256": entries_sha,
    }


def _build_offline_requests(
    panel: Mapping[str, Any], sample_text: Mapping[str, str]
) -> dict[str, Any]:
    schedule = _read_json(SCHEDULE_PATH)
    rows: list[dict[str, Any]] = []
    for entry in schedule["entries"]:
        sample_id = str(entry["sample_id"])
        if sample_id not in sample_text:
            raise PreparationError(f"unknown panel sample: {sample_id}")
        arm = str(entry["arm"])
        body = _request_body(arm, sample_id, sample_text[sample_id])
        body_bytes = json.dumps(
            body, ensure_ascii=False, sort_keys=True
        ).encode("utf-8")
        rows.append({
            "suite_id": SUITE_ID,
            "repeat_id": REPEAT_ID,
            "execution_index": int(entry["execution_index"]),
            "sample_id": sample_id,
            "arm": arm,
            "arm_order_within_sample": int(
                entry["arm_order_within_sample"]
            ),
            "input_text_sha256": _sha256_text(sample_text[sample_id]),
            "request_body_sha256": _sha256_bytes(body_bytes),
            "estimated_input_tokens_ceil_bytes_div_3": math.ceil(
                len(body_bytes) / 3
            ),
            "request_body": body,
        })
    rows.sort(key=lambda row: int(row["execution_index"]))
    per_arm: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        arm_rows = [row for row in rows if row["arm"] == arm]
        per_arm[arm] = {
            "call_count": len(arm_rows),
            "estimated_input_tokens": sum(
                int(row["estimated_input_tokens_ceil_bytes_div_3"])
                for row in arm_rows
            ),
            "max_input_tokens_estimate_per_call": max(
                int(row["estimated_input_tokens_ceil_bytes_div_3"])
                for row in arm_rows
            ),
            "max_request_body_bytes": max(
                len(json.dumps(
                    row["request_body"], ensure_ascii=False, sort_keys=True
                ).encode("utf-8"))
                for row in arm_rows
            ),
        }
    total_input_estimate = sum(
        int(row["estimated_input_tokens_ceil_bytes_div_3"]) for row in rows
    )
    return {
        "rows": rows,
        "per_arm": per_arm,
        "planned_calls": len(rows),
        "total_input_tokens_estimate": total_input_estimate,
        "max_input_tokens_estimate_per_call": max(
            int(row["estimated_input_tokens_ceil_bytes_div_3"])
            for row in rows
        ),
    }


def _build_budget(
    panel: Mapping[str, Any],
    schedule: Mapping[str, Any],
    request_stats: Mapping[str, Any],
) -> dict[str, Any]:
    planned_calls = int(request_stats["planned_calls"])
    input_estimate = int(request_stats["total_input_tokens_estimate"])
    input_cap = int(math.ceil(input_estimate * 2.0))
    output_cap = planned_calls * int(core.MAX_TOKENS)
    input_price = float(PRICE_SNAPSHOT["input_cache_miss_per_million"])
    output_price = float(PRICE_SNAPSHOT["output_per_million"])
    peak_estimated_usd = round(
        input_estimate * input_price / 1e6
        + output_cap * output_price / 1e6,
        8,
    )
    usd_cap = round(
        (input_cap * input_price + output_cap * output_price) / 1e6,
        8,
    )
    candidate_manifest = (
        ROOT / "prompts" / "sun_compat"
        / "modular_definition_refinement_v1" / "generated" / "manifest.json"
    )
    return {
        "schema_version": "sep_c3_definition_targeted_budget@1.0.0",
        "suite_id": SUITE_ID,
        "status": "prepared_not_run",
        "purpose": (
            "Targeted development contrast: BASE = candidate E4 v2, no R_DEF; "
            "R_DEF = candidate E4 v2 + definition guidance."
        ),
        "arms": list(ARMS),
        "arm_definitions": {
            "BASE": "candidate-local E4 v2 replacement; no R_DEF",
            "R_DEF": "candidate-local E4 v2 replacement + R_DEF guidance",
        },
        "A_policy": "reuse existing historical A predictions read-only; 0 new A calls",
        "panel_binding": {
            "path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(PANEL_PATH),
            "unique_sample_count_N": int(
                panel["panel_accounting"]["unique_sample_count_N"]
            ),
            "unique_selected_clause_count": int(
                panel["panel_accounting"]["unique_selected_clause_count"]
            ),
        },
        "schedule_binding": {
            "path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(SCHEDULE_PATH),
            "entries_sha256": schedule["entries_sha256"],
            "level": "sample_level",
        },
        "planned_calls": planned_calls,
        "call_cap": CALL_CAP,
        "calls_per_arm": {
            arm: int(request_stats["per_arm"][arm]["call_count"])
            for arm in ARMS
        },
        "estimated_input_tokens": input_estimate,
        "estimated_input_tokens_per_arm": {
            arm: int(request_stats["per_arm"][arm]["estimated_input_tokens"])
            for arm in ARMS
        },
        "max_input_tokens_estimate_per_call": int(
            request_stats["max_input_tokens_estimate_per_call"]
        ),
        "max_output_tokens_per_call": int(core.MAX_TOKENS),
        "total_max_output_tokens": output_cap,
        "input_token_cap": input_cap,
        "output_token_cap": output_cap,
        "peak_estimated_usd": peak_estimated_usd,
        "usd_cost_cap": usd_cap,
        "repeat_strategy": {
            "repeat_id": REPEAT_ID,
            "repeats_per_arm": 1,
            "retry": 0,
            "failure_policy": (
                "One recorded send per scheduled sample/arm; transport and "
                "parse failures persist in the denominator; no result-dependent "
                "retry."
            ),
        },
        "model": {
            "id": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "provider": "openai_compatible",
        },
        "inference": {
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
        },
        "data_binding": {
            "input_path": str(core.ESTG_INPUT.relative_to(ROOT)).replace("\\", "/"),
            "input_sha256": _sha256_file(core.ESTG_INPUT),
            "gold_path": str(core.FORMAL_GOLD.relative_to(ROOT)).replace("\\", "/"),
            "gold_sha256": _sha256_file(core.FORMAL_GOLD),
            "panel_path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
            "panel_sha256": _sha256_file(PANEL_PATH),
        },
        "prompt_binding": {
            "candidate_family": "direct_llm_definition_refinement_candidate_v1",
            "candidate_manifest_path": str(
                candidate_manifest.relative_to(ROOT)
            ).replace("\\", "/"),
            "candidate_manifest_sha256": _sha256_file(candidate_manifest),
            "arm_hashes": {
                arm: {
                    "system_sha256": _sha256_text(
                        dr.render_definition_prompt(arm).system_prompt
                    ),
                    "user_sha256": _sha256_text(
                        dr.render_definition_prompt(arm).user_prompt_template
                    ),
                    "composition_sha256": dr.render_definition_prompt(
                        arm
                    ).composition_sha256,
                    "generated_path": str(
                        dr.generated_path(arm).relative_to(ROOT)
                    ).replace("\\", "/"),
                    "generated_sha256": _sha256_file(dr.generated_path(arm)),
                }
                for arm in ARMS
            },
        },
        "parser_binding": {
            "schema_adapter_module": "src/bpc_hybrid/d1_schema_adapter.py",
            "schema_adapter_sha256": _sha256_file(
                ROOT / "src" / "bpc_hybrid" / "d1_schema_adapter.py"
            ),
            "span_canonicalizer_module": (
                "src/bpc_hybrid/d1_span_canonicalizer.py"
            ),
            "span_canonicalizer_sha256": _sha256_file(
                ROOT / "src" / "bpc_hybrid" / "d1_span_canonicalizer.py"
            ),
        },
        "evaluator_binding": {
            "coarse_metric_module": (
                "src/bpc_hybrid/sep_c3_modular_evaluation.py"
            ),
            "coarse_metric_sha256": _sha256_file(
                ROOT / "src" / "bpc_hybrid" / "sep_c3_modular_evaluation.py"
            ),
            "frozen_evaluator_module": (
                "src/bpc_hybrid/stage2_sun_literal_overlap.py"
            ),
            "frozen_evaluator_sha256": _sha256_file(
                ROOT / "src" / "bpc_hybrid" / "stage2_sun_literal_overlap.py"
            ),
            "targeted_contract_path": str(
                EVALUATION_CONTRACT_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
        },
        "price_snapshot": PRICE_SNAPSHOT,
        "actuals": None,
        "authorization": {
            "required": True,
            "status": "NOT_AUTHORIZED",
            "request_path": str(
                AUTHORIZATION_REQUEST_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
        },
    }


def _build_evaluation_contract(panel: Mapping[str, Any]) -> dict[str, Any]:
    slices = panel["slice_summary"]
    accounting = panel["panel_accounting"]
    return {
        "schema_version": (
            "sep_c3_definition_targeted_evaluation_contract@1.0.0"
        ),
        "suite_id": SUITE_ID,
        "status": "FROZEN_BEFORE_NEW_API",
        "panel_path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
        "panel_sha256": _sha256_file(PANEL_PATH),
        "api_input_unit": "sample_id",
        "gold_read_timing": "after_predictions_are_frozen_and_hashed",
        "evaluation_units": {
            "primary_targeted_clause_set": {
                "rule": "unique union of A/B/C/D selected clauses",
                "clause_count": accounting["unique_selected_clause_count"],
                "definition_count": accounting["definition_case_count"],
                "non_definition_count": accounting["non_definition_case_count"],
            },
            "definition_action_presence_set": {
                "rule": "unique targeted clauses whose Gold modality is definition",
                "clause_count": accounting["definition_case_count"],
            },
            "all_clauses_in_selected_samples_diagnostic": {
                "rule": "all Gold clauses belonging to the 42 selected samples",
                "clause_count": accounting[
                    "all_clauses_in_selected_samples"
                ],
            },
        },
        "slice_metrics": {
            "A_shall_definition": {
                "clause_count": slices["A_shall_definition"]["clause_count"],
                "metrics": [
                    "accuracy",
                    "definition_recall",
                    "corrected_relative_to_A_count",
                    "regressed_relative_to_A_count",
                ],
            },
            "B_non_definition_shall_controls": {
                "clause_count": slices["B_non_definition_shall_controls"][
                    "clause_count"
                ],
                "metrics": [
                    "modality_accuracy",
                    "false_definition_count",
                    "false_definition_rate",
                    "per_gold_label_breakdown",
                ],
            },
            "C_apply_applies_stress": {
                "clause_count": slices["C_apply_applies_stress"]["clause_count"],
                "metrics": [
                    "per_case_A_BASE_R_DEF_prediction",
                    "aggregate_descriptive_counts_only",
                    "NEEDS_GOLD_ADJUDICATION_retained",
                ],
            },
            "D_non_shall_definition_controls": {
                "clause_count": slices[
                    "D_non_shall_definition_controls"
                ]["clause_count"],
                "metrics": [
                    "modality_accuracy",
                    "definition_recall",
                    "action_presence",
                ],
            },
        },
        "primary_targeted_metrics": {
            "modality": [
                "modality_accuracy_on_targeted_clause_set",
                "definition_precision",
                "definition_recall",
                "definition_f1",
                "confusion_definition_to_obligation_count",
                "confusion_obligation_to_definition_count",
                "confusion_prohibition_to_definition_count",
                "confusion_permission_to_definition_count",
            ],
            "shall_definition": [
                "accuracy_on_all_15_shall_definition_clauses",
                "definition_recall_on_all_15_shall_definition_clauses",
                "numbered_corrected_relative_to_A",
                "numbered_regressed_relative_to_A",
            ],
            "non_definition_shall_controls": [
                "modality_accuracy_on_15_controls",
                "false_definition_count",
                "false_definition_rate",
                "per_label_breakdown",
            ],
            "apply_applies_stress": [
                "per_case_A_BASE_R_DEF_predictions",
                "aggregate_descriptive_counts_only",
            ],
            "definition_action_presence": [
                "fraction_of_Gold_definition_clauses_with_at_least_one_predicted_action",
                "empty_action_count",
                "diagnostic_action_span_f1",
            ],
        },
        "secondary_diagnostics": [
            "actor/action/condition/constraint/exception field F1",
            "five-field micro-F1 if supported by frozen evaluator",
            "parse/schema validity",
            "prediction_count",
            "output_validation_failures",
        ],
        "arithmetic_rules": [
            "Do not average modality accuracy and span-field F1.",
            "Do not make significance claims from this targeted development run.",
        ],
        "ambiguity_policy": {
            "apply_applies_family_status": "NEEDS_GOLD_ADJUDICATION",
            "no_lexical_apply_to_definition_rule": True,
            "gold_inconsistency_cases": panel["gold_inconsistency_cases"],
            "case_handling": (
                "Keep frozen Gold exactly as annotated; report cases in the "
                "main frozen evaluation and in a separate ambiguity diagnostic; "
                "do not tune the prompt to these cases."
            ),
        },
        "leakage_policy": {
            "gold_labels_or_spans_in_inference_requests": False,
            "panel_membership_frozen_before_outputs": True,
            "evaluation_reads_gold_only_after_predictions_fixed": True,
        },
    }


def _build_authorization_request(
    panel: Mapping[str, Any],
    budget: Mapping[str, Any],
    request_stats: Mapping[str, Any],
    leakage_audit: Mapping[str, Any],
) -> dict[str, Any]:
    request_set_sha = _sha256_text(
        _canonical_json([
            {
                "execution_index": row["execution_index"],
                "sample_id": row["sample_id"],
                "arm": row["arm"],
                "request_body_sha256": row["request_body_sha256"],
            }
            for row in request_stats["rows"]
        ])
    )
    return {
        "schema_version": (
            "sep_c3_definition_targeted_authorization_request@1.0.0"
        ),
        "suite_id": SUITE_ID,
        "scope": "SEP-C3-DEFINITION-TARGETED-REFINEMENT-001",
        "provider": "openai_compatible",
        "model": core.MODEL_ALIAS,
        "documented_release": core.MODEL_RELEASE,
        "arms": {
            "A": {
                "new_calls": 0,
                "source": "historical predictions reused read-only",
            },
            "BASE": {"new_calls": int(request_stats["per_arm"]["BASE"]["call_count"])},
            "R_DEF": {"new_calls": int(request_stats["per_arm"]["R_DEF"]["call_count"])},
        },
        "unique_panel_samples_N": int(
            panel["panel_accounting"]["unique_sample_count_N"]
        ),
        "new_calls": int(request_stats["planned_calls"]),
        "retry": 0,
        "off_peak_only": False,
        "model_sampling": {
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
        },
        "expected_input_tokens": int(
            request_stats["total_input_tokens_estimate"]
        ),
        "max_input_tokens_estimate_per_call": int(
            request_stats["max_input_tokens_estimate_per_call"]
        ),
        "input_token_cap": int(budget["input_token_cap"]),
        "max_output_tokens_per_call": int(core.MAX_TOKENS),
        "total_output_token_cap": int(budget["output_token_cap"]),
        "peak_estimated_usd": budget["peak_estimated_usd"],
        "usd_cap": budget["usd_cost_cap"],
        "rmb_cap_at_7_2": round(float(budget["usd_cost_cap"]) * 7.2, 2),
        "price_snapshot": PRICE_SNAPSHOT,
        "panel_sha256": _sha256_file(PANEL_PATH),
        "schedule_sha256": _sha256_file(SCHEDULE_PATH),
        "budget_sha256": _sha256_file(BUDGET_PATH),
        "evaluation_contract_sha256": _sha256_file(
            EVALUATION_CONTRACT_PATH
        ),
        "request_set_sha256": request_set_sha,
        "prompt_hashes": {
            arm: {
                "system_sha256": _sha256_text(
                    dr.render_definition_prompt(arm).system_prompt
                ),
                "user_sha256": _sha256_text(
                    dr.render_definition_prompt(arm).user_prompt_template
                ),
                "composition_sha256": dr.render_definition_prompt(
                    arm
                ).composition_sha256,
            }
            for arm in ARMS
        },
        "leakage_audit_status": leakage_audit.get("status"),
        "leakage_blocking_checks": leakage_audit.get("blocking_checks") or [],
        "suggested_authorization_sentence": (
            "I authorize exactly 84 real API calls for "
            "SEP-C3-DEFINITION-TARGETED-REFINEMENT-001, using "
            "openai_compatible/deepseek-v4-pro with retry=0, on the 42 frozen "
            "panel samples for BASE=42 and R_DEF=42, with input cap "
            f"{budget['input_token_cap']}, output cap "
            f"{budget['output_token_cap']}, USD cap {budget['usd_cost_cap']}, "
            f"panel SHA-256 {_sha256_file(PANEL_PATH)}, schedule SHA-256 "
            f"{_sha256_file(SCHEDULE_PATH)}, and request-set SHA-256 "
            f"{request_set_sha}."
        ),
        "execution_command": (
            "cd formal_experiment && python "
            "scripts/run_sep_c3_definition_targeted_refinement_v1.py "
            "--execute --allow-llm --authorization "
            "outputs/reports/sep_c3_definition_targeted_authorization_request_v1.json"
        ),
        "decision": "BLOCKED_NO_MATCHING_AUTHORIZATION",
        "authorization_status": "NOT_AUTHORIZED",
        "leakage_residual_note": (
            "The frozen active user envelope echoes the input sample_id and "
            "source_id because the Stage-2 output schema requires them.  This "
            "does not add Gold labels or spans, but it is a strict reading "
            "residual relative to a literal no-sample-id-in-prompt statement.  "
            "Resolve explicitly before execution if that strict reading "
            "controls."
        ),
    }


def _render_budget_markdown(budget: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Targeted Budget v1",
        "",
        f"- Status: **{budget['status']}**",
        f"- Suite: `{budget['suite_id']}`",
        f"- Panel N: **{budget['panel_binding']['unique_sample_count_N']}**",
        f"- Planned calls: **{budget['planned_calls']}** "
        f"(BASE={budget['calls_per_arm']['BASE']}, "
        f"R_DEF={budget['calls_per_arm']['R_DEF']}; A=0 new calls)",
        f"- Retry: **0**; failure policy: **{budget['repeat_strategy']['failure_policy']}**",
        f"- Estimated input tokens: **{budget['estimated_input_tokens']}**",
        f"- Input token cap: **{budget['input_token_cap']}**",
        f"- Max output tokens per call: **{budget['max_output_tokens_per_call']}**",
        f"- Total max output tokens: **{budget['total_max_output_tokens']}**",
        f"- Peak estimated USD: **{budget['peak_estimated_usd']}**",
        f"- USD cap: **{budget['usd_cost_cap']}**",
        "",
        "## Model/config",
        "",
        f"- Model: `{budget['model']['id']}` / `{budget['model']['documented_release']}`",
        f"- Inference: `{json.dumps(budget['inference'], ensure_ascii=False)}`",
        "",
        "## Prompt bindings",
        "",
        "| Arm | System | User | Composition |",
        "|---|---|---|---|",
    ]
    for arm, row in budget["prompt_binding"]["arm_hashes"].items():
        lines.append(
            f"| {arm} | `{row['system_sha256']}` | `{row['user_sha256']}` | "
            f"`{row['composition_sha256']}` |"
        )
    lines += [
        "",
        "## Price snapshot",
        "",
        f"- Input (cache miss): `{budget['price_snapshot']['input_cache_miss_per_million']}` USD/M",
        f"- Output: `{budget['price_snapshot']['output_per_million']}` USD/M",
        f"- Source/verified: `{budget['price_snapshot']['source_url']}` / "
        f"`{budget['price_snapshot']['verified_at_utc']}`",
        "",
        "## Authorization",
        "",
        f"- Required: `{budget['authorization']['required']}`",
        f"- Status: `{budget['authorization']['status']}`",
        "",
    ]
    return "\n".join(lines)


def _render_evaluation_contract_md(contract: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Targeted Evaluation Contract v1",
        "",
        f"- Status: **{contract['status']}**",
        f"- Suite: `{contract['suite_id']}`",
        f"- Panel SHA-256: `{contract['panel_sha256']}`",
        f"- API input unit: `{contract['api_input_unit']}`",
        f"- Gold read timing: `{contract['gold_read_timing']}`",
        "",
        "## Primary targeted metrics",
        "",
    ]
    for section, metrics in contract["primary_targeted_metrics"].items():
        lines.append(f"### {section}")
        lines.append("")
        for metric in metrics:
            lines.append(f"- {metric}")
        lines.append("")
    lines += [
        "## Secondary diagnostics",
        "",
    ]
    for metric in contract["secondary_diagnostics"]:
        lines.append(f"- {metric}")
    lines += [
        "",
        "## Arithmetic and interpretation rules",
        "",
    ]
    for rule in contract["arithmetic_rules"]:
        lines.append(f"- {rule}")
    lines += [
        "",
        "## Ambiguity policy",
        "",
        f"- Apply/applies: `{contract['ambiguity_policy']['apply_applies_family_status']}`",
        f"- No lexical apply=>definition rule: "
        f"`{contract['ambiguity_policy']['no_lexical_apply_to_definition_rule']}`",
        "",
        "## Gold inconsistency cases",
        "",
    ]
    for row in contract["ambiguity_policy"]["gold_inconsistency_cases"]:
        lines.append(
            f"- `{row['sample_id']} {row['clause_id']}` "
            f"modality={row['modality']} in_panel={row['in_panel']} "
            f"status={row['status']}"
        )
    lines.append("")
    return "\n".join(lines)


def _render_execution_plan(
    panel: Mapping[str, Any],
    budget: Mapping[str, Any],
    leakage_audit: Mapping[str, Any],
) -> str:
    return "\n".join([
        "# SEP-C3 Definition Targeted Execution Plan v1",
        "",
        "- Status: **prepared offline; not executed**",
        "- New API calls authorized: **no**",
        f"- Suite: `{SUITE_ID}`",
        f"- Unique panel samples N: **{panel['panel_accounting']['unique_sample_count_N']}**",
        f"- Planned calls: **{budget['planned_calls']}** "
        f"(BASE={budget['calls_per_arm']['BASE']}, "
        f"R_DEF={budget['calls_per_arm']['R_DEF']}; A=0 new calls)",
        f"- Retry: **0** (identical for both arms)",
        f"- Model: `{budget['model']['id']}` / "
        f"`{budget['model']['documented_release']}`",
        f"- Sampling: `{json.dumps(budget['inference'], ensure_ascii=False)}`",
        "",
        "## Frozen inputs",
        "",
        f"- Panel: `{budget['panel_binding']['path']}` "
        f"SHA-256 `{budget['panel_binding']['sha256']}`",
        f"- Schedule: `{budget['schedule_binding']['path']}` "
        f"SHA-256 `{budget['schedule_binding']['sha256']}`",
        f"- Gold read timing: after predictions are fixed and hashed",
        f"- Prompt BASE system SHA-256: "
        f"`{budget['prompt_binding']['arm_hashes']['BASE']['system_sha256']}`",
        f"- Prompt R_DEF system SHA-256: "
        f"`{budget['prompt_binding']['arm_hashes']['R_DEF']['system_sha256']}`",
        "",
        "## Execution order",
        "",
        "1. Re-validate panel, schedule, budget, prompt, parser, and evaluator hashes.",
        "2. Render and persist offline request capsules.",
        "3. Freeze and record the request-set hash and leakage audit.",
        "4. Obtain explicit authorization for exactly 84 calls.",
        "5. Execute BASE and R_DEF with identical model/config/parser/evaluator.",
        "6. Canonicalize predictions and hash them before reading Gold for scoring.",
        "7. Evaluate the frozen slices and report trade-offs; do not promote R_DEF automatically.",
        "",
        "## Current authorization gate",
        "",
        f"- Leakage audit status: `{leakage_audit.get('status')}`",
        f"- Blocking checks: `{leakage_audit.get('blocking_checks')}`",
        "- Decision: **STOP before real calls** until explicit user authorization "
        "for this exact suite/scope exists and any leakage residual is resolved.",
        "",
    ])


def _render_authorization_markdown(request: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Targeted Authorization Request v1",
        "",
        f"- Suite: `{request['suite_id']}`",
        f"- Provider/model: `{request['provider']}` / `{request['model']}`",
        f"- Unique panel samples: **{request['unique_panel_samples_N']}**",
        f"- New calls: **{request['new_calls']}** "
        f"(BASE={request['arms']['BASE']['new_calls']}, "
        f"R_DEF={request['arms']['R_DEF']['new_calls']}, A=0)",
        f"- Retry: `{request['retry']}`",
        f"- Expected input tokens: `{request['expected_input_tokens']}`; "
        f"input cap: `{request['input_token_cap']}`",
        f"- Max output tokens per call: `{request['max_output_tokens_per_call']}`; "
        f"total output cap: `{request['total_output_token_cap']}`",
        f"- Peak estimated USD: `{request['peak_estimated_usd']}`; "
        f"USD cap: `{request['usd_cap']}`",
        f"- Panel SHA-256: `{request['panel_sha256']}`",
        f"- Schedule SHA-256: `{request['schedule_sha256']}`",
        f"- Budget SHA-256: `{request['budget_sha256']}`",
        f"- Request-set SHA-256: `{request['request_set_sha256']}`",
        f"- Leakage audit status: `{request['leakage_audit_status']}`",
        f"- Leakage blocking checks: `{request['leakage_blocking_checks']}`",
        "",
        "## Exact one-sentence authorization request",
        "",
        request["suggested_authorization_sentence"],
        "",
        "SHA-256 of sentence: `" + _sha256_text(
            request["suggested_authorization_sentence"]
        ) + "`",
        "",
        "## Decision",
        "",
        f"- Current decision: **{request['decision']}**",
        f"- {request['leakage_residual_note']}",
        "",
    ]
    return "\n".join(lines)


def build(*, write: bool = True) -> dict[str, Any]:
    panel = _load_panel()
    sample_text = _sample_text_map()

    schedule = _build_schedule(panel)
    if write:
        _write_json(SCHEDULE_PATH, schedule)

    request_stats = _build_offline_requests(panel, sample_text)
    if write:
        EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
        OFFLINE_REQUESTS_PATH.write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in request_stats["rows"]
            ),
            encoding="utf-8",
            newline="\n",
        )
        _write_json(
            REQUEST_MANIFEST_PATH,
            {
                "schema_version": (
                    "sep_c3_definition_targeted_request_manifest@1.0.0"
                ),
                "status": "FROZEN_OFFLINE_CAPSULE_NOT_SENT",
                "suite_id": SUITE_ID,
                "panel_path": str(PANEL_PATH.relative_to(ROOT)).replace("\\", "/"),
                "panel_sha256": _sha256_file(PANEL_PATH),
                "schedule_path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
                "schedule_sha256": _sha256_file(SCHEDULE_PATH),
                "offline_requests_path": str(
                    OFFLINE_REQUESTS_PATH.relative_to(ROOT)
                ).replace("\\", "/"),
                "offline_requests_sha256": _sha256_file(OFFLINE_REQUESTS_PATH),
                "request_count": request_stats["planned_calls"],
                "requests_per_arm": {
                    arm: request_stats["per_arm"][arm]["call_count"]
                    for arm in ARMS
                },
                "estimated_input_tokens": request_stats[
                    "total_input_tokens_estimate"
                ],
                "estimated_input_tokens_per_arm": {
                    arm: request_stats["per_arm"][arm][
                        "estimated_input_tokens"
                    ]
                    for arm in ARMS
                },
                "max_input_tokens_estimate_per_call": request_stats[
                    "max_input_tokens_estimate_per_call"
                ],
            },
        )

    budget = _build_budget(panel, schedule, request_stats)
    evaluation_contract = _build_evaluation_contract(panel)
    if write:
        _write_json(BUDGET_PATH, budget)
        _write_json(EVALUATION_CONTRACT_PATH, evaluation_contract)
        _write_json(BUDGET_REPORT_PATH, budget)
        _write_text(BUDGET_REPORT_MD_PATH, _render_budget_markdown(budget))
        _write_text(
            EVALUATION_CONTRACT_MD_PATH,
            _render_evaluation_contract_md(evaluation_contract),
        )

    # Leakage audit needs the rendered request capsule and evaluation contract.
    leakage_audit = leakage.run_audit(
        offline_requests_path=OFFLINE_REQUESTS_PATH,
        write=write,
    )

    execution_plan = _render_execution_plan(panel, budget, leakage_audit)
    if write:
        _write_text(EXECUTION_PLAN_PATH, execution_plan)

    authorization_request = _build_authorization_request(
        panel, budget, request_stats, leakage_audit
    )
    if write:
        # Rebuild authorization now that the leakage audit exists; hash the
        # frozen budget and evaluation contract used in the request.
        authorization_request["budget_sha256"] = _sha256_file(BUDGET_PATH)
        authorization_request["evaluation_contract_sha256"] = _sha256_file(
            EVALUATION_CONTRACT_PATH
        )
        _write_json(AUTHORIZATION_REQUEST_PATH, authorization_request)
        _write_text(
            AUTHORIZATION_REQUEST_MD_PATH,
            _render_authorization_markdown(authorization_request),
        )

    return {
        "panel": panel,
        "schedule": schedule,
        "request_stats": request_stats,
        "budget": budget,
        "evaluation_contract": evaluation_contract,
        "leakage_audit": leakage_audit,
        "authorization_request": authorization_request,
    }


def main() -> int:
    result = build(write=True)
    print(json.dumps({
        "status": "prepared_offline",
        "suite_id": SUITE_ID,
        "N": result["request_stats"]["planned_calls"] // 2,
        "new_calls": result["request_stats"]["planned_calls"],
        "offline_requests_path": str(
            OFFLINE_REQUESTS_PATH.relative_to(ROOT)
        ).replace("\\", "/"),
        "budget_path": str(BUDGET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "leakage_status": result["leakage_audit"]["status"],
        "authorization_decision": result["authorization_request"]["decision"],
        "authorization_request_path": str(
            AUTHORIZATION_REQUEST_PATH.relative_to(ROOT)
        ).replace("\\", "/"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
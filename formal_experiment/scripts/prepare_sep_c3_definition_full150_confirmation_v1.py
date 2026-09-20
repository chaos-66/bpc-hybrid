# -*- coding: utf-8 -*-
"""Freeze the full-150 R_DEF confirmation artifacts and rescore historical A.

This script performs zero API calls.  It creates:
  * the exact 150-sample schedule and request capsule for the single frozen
    R_DEF package;
  * the budget and execution contract;
  * a current-contract rescore of historical Arm A from its frozen raw
    responses (failures become empty predictions exactly as in the runner);
  * a full-150 evaluator dry check;
  * an explicit authorization event recording the user's execution decision.

The R_DEF treatment is the complete package E4 v2 + R_DEF guidance.  BASE is
not executed here.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import run_sep_c3_targeted_refinement_v1 as tr  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    attempt_rows,
    evaluate_coarse,
)


SUITE_ID = "SEP-C3-DEFINITION-FULL150-CONFIRMATION-001"
ARM = "R_DEF"
REPEAT_ID = "repeat-01"
PLANNED_CALLS = 150
CALL_CAP = 150
OUTPUT_VALIDATION_PATH_VERSION = "sep_c3_targeted_refinement_runtime_validation_v1"

SCHEDULE_PATH = ROOT / "configs" / "sep_c3_definition_full150_schedule_v1.json"
BUDGET_PATH = ROOT / "configs" / "sep_c3_definition_full150_budget_v1.json"
EXECUTION_CONTRACT_PATH = (
    ROOT / "configs" / "sep_c3_definition_full150_execution_contract_v1.json"
)
AUTHORIZATION_EVENT_PATH = (
    ROOT / "configs" / "sep_c3_definition_full150_authorization_event_v1.json"
)
EVIDENCE_DIR = ROOT / "outputs" / "evidence" / "sep_c3_definition_full150_confirmation_v1"
OFFLINE_REQUESTS_PATH = EVIDENCE_DIR / "offline_requests.jsonl"
REQUEST_MANIFEST_PATH = EVIDENCE_DIR / "request_manifest.json"
PREFLIGHT_REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_preflight_v1.json"
)
PREFLIGHT_REPORT_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_preflight_v1.md"
)
A_OUT_DIR = (
    ROOT / "outputs" / "development"
    / "sep_c3_definition_full150_confirmation_v1"
    / "A_current_contract" / REPEAT_ID
)
A_REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_A_current_contract_freeze_v1.json"
)
DRY_CHECK_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_evaluator_dry_check_v1.json"
)
EXPECTED_A_FIVE_FIELD_MEAN_F1 = 0.7080951816362215
LEGACY_A_FIVE_FIELD_MEAN_F1 = 0.7245765761849047
HISTORICAL_RAW_PATH = (
    ROOT / "outputs" / "development" / "sep_c3_targeted_refinement_v1"
    / "A" / REPEAT_ID / "raw_responses.jsonl"
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

USER_AUTHORIZATION_QUOTE = (
    "Proceed with the frozen R_DEF full-150 confirmation experiment."
)


class Full150PreparationError(RuntimeError):
    """A frozen full-150 artifact could not be prepared safely."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _prompt():
    return dr.render_definition_prompt(ARM)


def _prompt_binding() -> dict[str, Any]:
    prompt = _prompt()
    generated_manifest = dr.generated_manifest_path()
    return {
        "candidate_family": "direct_llm_definition_refinement_candidate_v1",
        "package_name": "E4_v2_replacement_plus_R_DEF_guidance",
        "r_def_text_sha256": _sha256_text(dr.R_DEF_TEXT),
        "system_sha256": _sha256_text(prompt.system_prompt),
        "user_sha256": _sha256_text(prompt.user_prompt_template),
        "composition_sha256": prompt.composition_sha256,
        "generated_prompt_path": str(prompt and dr.generated_path(ARM).relative_to(ROOT)).replace("\\", "/"),
        "generated_prompt_sha256": _sha256_file(dr.generated_path(ARM)),
        "generated_manifest_path": str(generated_manifest.relative_to(ROOT)).replace("\\", "/"),
        "generated_manifest_sha256": _sha256_file(generated_manifest),
        "source_hashes": dict(prompt.source_hashes),
    }


def _module_binding() -> dict[str, Any]:
    modules = {
        "schema_adapter": "src/bpc_hybrid/d1_schema_adapter.py",
        "span_canonicalizer": "src/bpc_hybrid/d1_span_canonicalizer.py",
        "canonical_validator": "src/bpc_hybrid/stage2_canonical.py",
        "coarse_view": "src/bpc_hybrid/g04_coarse_view.py",
        "coarse_evaluator": "src/bpc_hybrid/sep_c3_modular_evaluation.py",
        "frozen_span_evaluator": "src/bpc_hybrid/stage2_sun_literal_overlap.py",
        "formal_stage2_evaluator": "src/bpc_hybrid/formal_stage2_evaluation.py",
        "maximal_overlap_evaluator": "src/bpc_hybrid/stage2_maximal_overlap.py",
    }
    out: dict[str, Any] = {
        "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
        "parser_canonicalizer_validator": {},
        "evaluator": {},
    }
    for key in ("schema_adapter", "span_canonicalizer", "canonical_validator"):
        rel = modules[key]
        path = ROOT / rel
        out["parser_canonicalizer_validator"][key] = {
            "path": rel,
            "sha256": _sha256_file(path),
        }
    for key in (
        "coarse_view",
        "coarse_evaluator",
        "frozen_span_evaluator",
        "formal_stage2_evaluator",
    ):
        rel = modules[key]
        path = ROOT / rel
        out["evaluator"][key] = {
            "path": rel,
            "sha256": _sha256_file(path),
        }
    missing = [key for key in ("maximal_overlap_evaluator",)]
    for key in missing:
        rel = modules[key]
        path = ROOT / rel
        out["evaluator"][key] = {
            "path": rel,
            "sha256": _sha256_file(path) if path.is_file() else None,
            "present": path.is_file(),
        }
    out["evaluator"]["official_metric"] = "coarse_five_field_mean_f1"
    out["evaluator"]["official_view"] = "coarse_sentence_level"
    out["evaluator"]["dataset_id"] = "independently_reconstructed_estg_150_v1"
    return out


def _build_schedule() -> dict[str, Any]:
    samples = core.samples(core.SAMPLES_PER_ARM)
    if len(samples) != PLANNED_CALLS:
        raise Full150PreparationError(
            f"frozen input must contain {PLANNED_CALLS} records"
        )
    if len({s["sample_id"] for s in samples}) != PLANNED_CALLS:
        raise Full150PreparationError("frozen input sample_ids are not unique")
    entries = [
        {
            "execution_index": index,
            "sample_id": row["sample_id"],
            "arm": ARM,
            "arm_order_within_sample": 1,
            "repeat_id": REPEAT_ID,
        }
        for index, row in enumerate(samples, start=1)
    ]
    entries_sha = _sha256_text(_canonical_json(entries))
    membership_order = [row["sample_id"] for row in samples]
    membership_sha = _sha256_text(_canonical_json(membership_order))
    schedule = {
        "schema_version": "sep_c3_definition_full150_schedule@1.0.0",
        "suite_id": SUITE_ID,
        "status": "FROZEN_BEFORE_NEW_API",
        "arm": ARM,
        "treatment_package": "E4 v2 replacement + R_DEF guidance",
        "repeat_id": REPEAT_ID,
        "scheme": "frozen_input_order_single_arm",
        "input_path": str(core.ESTG_INPUT.relative_to(ROOT)).replace("\\", "/"),
        "input_sha256": _sha256_file(core.ESTG_INPUT),
        "sample_count": len(entries),
        "sample_membership_order": membership_order,
        "sample_membership_order_sha256": membership_sha,
        "planned_calls": len(entries),
        "entries": entries,
        "entries_sha256": entries_sha,
    }
    return schedule


def _request_body(sample_id: str, source_text: str) -> dict[str, Any]:
    prompt = _prompt()
    return {
        "model": core.MODEL_ALIAS,
        "messages": prompt.request_messages(sample_id, source_text),
        "temperature": core.TEMPERATURE,
        "top_p": core.TOP_P,
        "max_tokens": core.MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def _build_offline_requests(schedule: Mapping[str, Any]) -> dict[str, Any]:
    sample_by_id = {row["sample_id"]: row for row in core.samples(core.SAMPLES_PER_ARM)}
    rows: list[dict[str, Any]] = []
    for entry in schedule["entries"]:
        sample_id = str(entry["sample_id"])
        source_text = str(sample_by_id[sample_id]["text"])
        body = _request_body(sample_id, source_text)
        body_bytes = json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        rows.append({
            "suite_id": SUITE_ID,
            "repeat_id": REPEAT_ID,
            "execution_index": int(entry["execution_index"]),
            "sample_id": sample_id,
            "arm": ARM,
            "arm_order_within_sample": 1,
            "input_text_sha256": _sha256_text(source_text),
            "request_body_sha256": _sha256_bytes(body_bytes),
            "estimated_input_tokens_ceil_bytes_div_3": math.ceil(len(body_bytes) / 3),
            "request_body": body,
        })
    rows.sort(key=lambda row: int(row["execution_index"]))
    return {
        "rows": rows,
        "planned_calls": len(rows),
        "total_input_tokens_estimate": sum(
            int(row["estimated_input_tokens_ceil_bytes_div_3"]) for row in rows
        ),
        "max_input_tokens_estimate_per_call": max(
            int(row["estimated_input_tokens_ceil_bytes_div_3"]) for row in rows
        ),
    }


def _build_budget(
    schedule: Mapping[str, Any],
    request_stats: Mapping[str, Any],
) -> dict[str, Any]:
    input_estimate = int(request_stats["total_input_tokens_estimate"])
    input_cap = int(math.ceil(input_estimate * 2.0))
    output_cap = PLANNED_CALLS * int(core.MAX_TOKENS)
    input_price = float(PRICE_SNAPSHOT["input_cache_miss_per_million"])
    output_price = float(PRICE_SNAPSHOT["output_per_million"])
    peak_estimated_usd = round(
        input_estimate * input_price / 1e6 + output_cap * output_price / 1e6,
        8,
    )
    usd_cap = round(
        (input_cap * input_price + output_cap * output_price) / 1e6,
        8,
    )
    prompt_binding = _prompt_binding()
    modules = _module_binding()
    return {
        "schema_version": "sep_c3_definition_full150_budget@1.0.0",
        "suite_id": SUITE_ID,
        "status": "FROZEN_BEFORE_NEW_API",
        "purpose": "Full-corpus confirmation of the frozen R_DEF package against historical A_current_contract.",
        "arms": [ARM],
        "arm_definition": {
            ARM: "complete frozen treatment package: E4 v2 replacement + R_DEF guidance",
        },
        "A_policy": "reuse frozen historical Arm A raw responses; 0 new A calls; current-contract rescore only",
        "BASE_policy": "not executed in this full-150 confirmation",
        "schedule_binding": {
            "path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(SCHEDULE_PATH),
            "entries_sha256": schedule["entries_sha256"],
            "level": "sample_level",
        },
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "calls_per_arm": {ARM: PLANNED_CALLS},
        "estimated_input_tokens": input_estimate,
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
                "One recorded send per scheduled sample; transport, parse, "
                "binding, and canonical-validation failures persist in the "
                "denominator; no result-dependent retry; no regeneration."
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
            "gold_record_count": 150,
        },
        "prompt_binding": prompt_binding,
        "parser_binding": modules["parser_canonicalizer_validator"],
        "evaluator_binding": modules["evaluator"],
        "price_snapshot": PRICE_SNAPSHOT,
        "actuals": None,
        "authorization": {
            "required": True,
            "status": "AUTHORIZED_FOR_EXECUTION",
            "event_path": str(AUTHORIZATION_EVENT_PATH.relative_to(ROOT)).replace("\\", "/"),
        },
    }


def _load_a_raw_rows() -> dict[str, dict[str, Any]]:
    if not HISTORICAL_RAW_PATH.is_file():
        raise Full150PreparationError(
            f"historical A raw responses not found: {HISTORICAL_RAW_PATH}"
        )
    rows = _read_jsonl(HISTORICAL_RAW_PATH)
    by_sid: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("sample_id") or "")
        if not sid or sid in by_sid:
            raise Full150PreparationError(
                f"historical A raw response has missing/duplicate sample_id: {sid!r}"
            )
        by_sid[sid] = row
    expected = {row["sample_id"] for row in core.samples(core.SAMPLES_PER_ARM)}
    if set(by_sid) != expected:
        raise Full150PreparationError("historical A raw membership does not match frozen 150")
    return by_sid


def _rescore_historical_a() -> dict[str, Any]:
    samples = core.samples(core.SAMPLES_PER_ARM)
    raw_by_sid = _load_a_raw_rows()
    predictions: list[dict[str, Any]] = []
    for sample in samples:
        sid = str(sample["sample_id"])
        prediction = tr.convert_refinement_response(
            raw_by_sid[sid], "A", str(sample["text"])
        )
        prediction.update({
            "suite_id": SUITE_ID,
            "arm": "A_current_contract",
            "source_raw_path": str(HISTORICAL_RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
            "source_raw_sha256": _sha256_file(HISTORICAL_RAW_PATH),
            "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
        })
        predictions.append(prediction)
    failed = [row for row in predictions if row.get("request_status") != "ok"]
    gold = _read_json(core.FORMAL_GOLD)
    evaluation = evaluate_coarse(
        gold,
        attempt_rows(predictions),
        method_id="A_current_contract_full150",
    )
    observed = float(evaluation["coarse_five_field_mean_f1"])
    if abs(observed - EXPECTED_A_FIVE_FIELD_MEAN_F1) > 1e-12:
        raise Full150PreparationError(
            "historical A current-contract rescore did not reproduce the frozen "
            f"baseline: observed={observed!r}, expected={EXPECTED_A_FIVE_FIELD_MEAN_F1!r}"
        )
    status_counts: dict[str, dict[str, int]] = {}
    for field in (
        "request_status",
        "api_call_status",
        "output_parse_status",
        "input_binding_status",
        "canonical_validation_status",
    ):
        status_counts[field] = dict(Counter(str(row.get(field) or "missing") for row in predictions))
    failure_stage_counts = dict(Counter(str(row.get("failure_stage") or "none") for row in failed))
    manifest = {
        "schema_version": "sep_c3_definition_full150_A_current_contract_manifest@1.0.0",
        "suite_id": SUITE_ID,
        "arm": "A_current_contract",
        "status": "FROZEN_BEFORE_R_DEF_EVALUATION_INSPECTION",
        "sample_count": len(predictions),
        "failure_count": len(failed),
        "failure_stage_counts": failure_stage_counts,
        "status_counts": status_counts,
        "raw_source_path": str(HISTORICAL_RAW_PATH.relative_to(ROOT)).replace("\\", "/"),
        "raw_source_sha256": _sha256_file(HISTORICAL_RAW_PATH),
        "canonical_predictions_sha256": _sha256_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions)
        ),
        "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
        "parser_canonicalizer_validator_binding": _module_binding()[
            "parser_canonicalizer_validator"
        ],
        "evaluator_binding": _module_binding()["evaluator"],
        "legacy_label": {
            "legacy_official_five_field_mean_f1": LEGACY_A_FIVE_FIELD_MEAN_F1,
            "must_not_be_directly_compared_to_r_def": True,
        },
        "current_contract": {
            "five_field_mean_f1": observed,
            "five_field_micro_f1": float(evaluation["coarse_five_field_micro"]["f1"]),
            "modality_accuracy": float(evaluation["modality_labels"]["accuracy"]),
            "modality_macro_f1": float(evaluation["modality_labels"]["macro_f1"]),
        },
        "empty_on_failure_policy": True,
    }
    A_OUT_DIR.mkdir(parents=True, exist_ok=True)
    (A_OUT_DIR / "canonical_predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(A_OUT_DIR / "evaluation.json", {
        "schema_version": "sep_c3_definition_full150_A_current_contract_evaluation@1.0.0",
        "suite_id": SUITE_ID,
        "arm": "A_current_contract",
        "denominator": len(predictions),
        "failed_count": len(failed),
        "evaluation": evaluation,
        "manifest_sha_source": "A_current_contract",
    })
    _write_json(A_OUT_DIR / "manifest.json", manifest)
    _write_json(A_REPORT_PATH, {
        "schema_version": "sep_c3_definition_full150_A_current_contract_freeze@1.0.0",
        "suite_id": SUITE_ID,
        "status": "FROZEN_BEFORE_R_DEF_EVALUATION_INSPECTION",
        "observed_five_field_mean_f1": observed,
        "expected_five_field_mean_f1": EXPECTED_A_FIVE_FIELD_MEAN_F1,
        "legacy_five_field_mean_f1": LEGACY_A_FIVE_FIELD_MEAN_F1,
        "reproduced_exactly": True,
        "canonical_predictions_path": str((A_OUT_DIR / "canonical_predictions.jsonl").relative_to(ROOT)).replace("\\", "/"),
        "canonical_predictions_sha256": _sha256_file(A_OUT_DIR / "canonical_predictions.jsonl"),
        "manifest_path": str((A_OUT_DIR / "manifest.json").relative_to(ROOT)).replace("\\", "/"),
        "manifest_sha256": _sha256_file(A_OUT_DIR / "manifest.json"),
        "evaluation": evaluation,
        "failure_stage_counts": failure_stage_counts,
        "status_counts": status_counts,
    })
    return {
        "manifest": manifest,
        "manifest_path": A_OUT_DIR / "manifest.json",
        "evaluation": evaluation,
    }


def _evaluator_dry_check(a_manifest: Mapping[str, Any]) -> dict[str, Any]:
    gold = _read_json(core.FORMAL_GOLD)
    a_predictions = _read_jsonl(A_OUT_DIR / "canonical_predictions.jsonl")
    a_attempts = attempt_rows(a_predictions)
    empty_attempts = [
        {
            "sample_id": row["sample_id"],
            "request_status": "failed",
            "record": {},
        }
        for row in a_predictions
    ]
    a_eval = evaluate_coarse(gold, a_attempts, method_id="dry_check_A_current_contract_full150")
    empty_eval = evaluate_coarse(gold, empty_attempts, method_id="dry_check_empty_full150")
    if int(a_eval.get("denominator") or 0) != PLANNED_CALLS:
        raise Full150PreparationError("full-150 A evaluator dry check denominator != 150")
    if int(empty_eval.get("denominator") or 0) != PLANNED_CALLS:
        raise Full150PreparationError("full-150 empty evaluator dry check denominator != 150")
    if abs(float(a_eval["coarse_five_field_mean_f1"]) - EXPECTED_A_FIVE_FIELD_MEAN_F1) > 1e-12:
        raise Full150PreparationError("dry check A score does not match frozen baseline")
    if abs(float(empty_eval["coarse_five_field_mean_f1"])) > 1e-12:
        raise Full150PreparationError("dry check empty score is not zero")
    report = {
        "schema_version": "sep_c3_definition_full150_evaluator_dry_check@1.0.0",
        "suite_id": SUITE_ID,
        "status": "PASS",
        "api_calls_made": 0,
        "gold_record_count": 150,
        "prediction_envelope_count": len(a_attempts),
        "unique_sample_ids": len({row["sample_id"] for row in a_attempts}),
        "A_current_contract": {
            "denominator": int(a_eval["denominator"]),
            "five_field_mean_f1": float(a_eval["coarse_five_field_mean_f1"]),
            "matches_frozen_expected": True,
        },
        "empty_attempts": {
            "denominator": int(empty_eval["denominator"]),
            "five_field_mean_f1": float(empty_eval["coarse_five_field_mean_f1"]),
        },
        "membership_check": {
            "status": "pass",
            "note": "All 150 frozen sample_ids were supplied to the full-150 evaluator wrapper; the prior 42-subset membership failure cannot recur.",
        },
        "a_manifest_sha256": _sha256_file(A_OUT_DIR / "manifest.json"),
        "a_manifest_status": a_manifest.get("status"),
    }
    _write_json(DRY_CHECK_PATH, report)
    return report


def _build_execution_contract(
    schedule: Mapping[str, Any],
    budget: Mapping[str, Any],
    request_stats: Mapping[str, Any],
    a_freeze: Mapping[str, Any],
    dry_check: Mapping[str, Any],
) -> dict[str, Any]:
    prompt_binding = _prompt_binding()
    module_binding = _module_binding()
    request_set_sha = _sha256_text(_canonical_json([
        {
            "execution_index": row["execution_index"],
            "sample_id": row["sample_id"],
            "arm": row["arm"],
            "request_body_sha256": row["request_body_sha256"],
        }
        for row in request_stats["rows"]
    ]))
    return {
        "schema_version": "sep_c3_definition_full150_execution_contract@1.0.0",
        "suite_id": SUITE_ID,
        "status": "FROZEN_BEFORE_NEW_API",
        "scope": "full-corpus confirmation, not independent held-out validation",
        "treatment_package": "E4 v2 replacement + R_DEF guidance",
        "does_not_isolate": "incremental causal effect of the R_DEF paragraph alone",
        "decomposition_evidence": "targeted A->BASE and BASE->R_DEF development comparison remains separate",
        "arms": {
            "A": {
                "new_calls": 0,
                "source": "historical frozen raw responses rescored under current contract",
                "current_contract_five_field_mean_f1": EXPECTED_A_FIVE_FIELD_MEAN_F1,
                "legacy_score_label": {
                    "value": LEGACY_A_FIVE_FIELD_MEAN_F1,
                    "comparable_to_r_def_full150": False,
                },
            },
            "R_DEF": {
                "new_calls": PLANNED_CALLS,
                "treatment": "complete frozen package",
            },
            "BASE": {
                "new_calls": 0,
                "executed": False,
            },
        },
        "schedule_binding": {
            "path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(SCHEDULE_PATH),
            "entries_sha256": schedule["entries_sha256"],
            "sample_membership_order_sha256": schedule["sample_membership_order_sha256"],
            "sample_count": schedule["sample_count"],
        },
        "sample_membership_order": list(schedule["sample_membership_order"]),
        "input_binding": {
            "path": str(core.ESTG_INPUT.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(core.ESTG_INPUT),
            "record_count": 150,
        },
        "gold_binding": {
            "path": str(core.FORMAL_GOLD.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(core.FORMAL_GOLD),
            "record_count": 150,
        },
        "prompt_binding": prompt_binding,
        "model_and_generation": {
            "model": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "thinking": {"type": "disabled"},
            "response_format": None,
            "stream": False,
            "retry": 0,
        },
        "parser_canonicalizer_validator_binding": module_binding[
            "parser_canonicalizer_validator"
        ],
        "evaluator_binding": module_binding["evaluator"],
        "output_validation_path_version": OUTPUT_VALIDATION_PATH_VERSION,
        "empty_on_failure_policy": True,
        "retry_policy": {
            "retry": 0,
            "attempts_per_scheduled_request": 1,
            "no_repair_or_regeneration_after_observation": True,
        },
        "budget_binding": {
            "path": str(BUDGET_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(BUDGET_PATH),
            "planned_calls": PLANNED_CALLS,
            "call_cap": CALL_CAP,
            "input_token_cap": budget["input_token_cap"],
            "output_token_cap": budget["output_token_cap"],
            "usd_cost_cap": budget["usd_cost_cap"],
        },
        "request_capsule_binding": {
            "path": str(OFFLINE_REQUESTS_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(OFFLINE_REQUESTS_PATH) if OFFLINE_REQUESTS_PATH.is_file() else None,
            "request_manifest_path": str(REQUEST_MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
            "request_manifest_sha256": _sha256_file(REQUEST_MANIFEST_PATH) if REQUEST_MANIFEST_PATH.is_file() else None,
            "request_count": request_stats["planned_calls"],
            "request_set_sha256": request_set_sha,
        },
        "A_current_contract_freeze": {
            "status": a_freeze["manifest"]["status"],
            "five_field_mean_f1": EXPECTED_A_FIVE_FIELD_MEAN_F1,
            "manifest_path": str((A_OUT_DIR / "manifest.json").relative_to(ROOT)).replace("\\", "/"),
            "manifest_sha256": _sha256_file(A_OUT_DIR / "manifest.json"),
            "canonical_predictions_path": str((A_OUT_DIR / "canonical_predictions.jsonl").relative_to(ROOT)).replace("\\", "/"),
            "canonical_predictions_sha256": _sha256_file(A_OUT_DIR / "canonical_predictions.jsonl"),
        },
        "evaluator_dry_check": {
            "status": dry_check["status"],
            "path": str(DRY_CHECK_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": _sha256_file(DRY_CHECK_PATH),
            "denominator": dry_check["prediction_envelope_count"],
        },
        "no_scope_creep": {
            "R_DEF2": False,
            "additional_examples": False,
            "new_semantic_rules": False,
            "lexical_fixes": False,
            "validator_fixes": False,
            "new_prompt_arms": False,
            "BASE_full_150": False,
            "A_regeneration": False,
            "Stage_3": False,
        },
    }


def _build_request_manifest(
    schedule: Mapping[str, Any],
    budget: Mapping[str, Any],
    request_stats: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "sep_c3_definition_full150_request_manifest@1.0.0",
        "status": "FROZEN_OFFLINE_CAPSULE_NOT_SENT",
        "suite_id": SUITE_ID,
        "arm": ARM,
        "treatment_package": "E4 v2 replacement + R_DEF guidance",
        "schedule_path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "schedule_sha256": _sha256_file(SCHEDULE_PATH),
        "schedule_entries_sha256": schedule["entries_sha256"],
        "sample_membership_order_sha256": schedule["sample_membership_order_sha256"],
        "offline_requests_path": str(OFFLINE_REQUESTS_PATH.relative_to(ROOT)).replace("\\", "/"),
        "offline_requests_sha256": _sha256_file(OFFLINE_REQUESTS_PATH),
        "request_count": request_stats["planned_calls"],
        "estimated_input_tokens": request_stats["total_input_tokens_estimate"],
        "max_input_tokens_estimate_per_call": request_stats["max_input_tokens_estimate_per_call"],
        "budget_path": str(BUDGET_PATH.relative_to(ROOT)).replace("\\", "/"),
        "budget_sha256": _sha256_file(BUDGET_PATH),
        "prompt_binding": _prompt_binding(),
        "model_and_generation": {
            "model": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "thinking": {"type": "disabled"},
            "response_format": None,
            "stream": False,
            "retry": 0,
        },
    }


def _build_authorization_event(
    schedule: Mapping[str, Any],
    budget: Mapping[str, Any],
    contract: Mapping[str, Any],
    request_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "sep_c3_definition_full150_authorization_event@1.0.0",
        "suite_id": SUITE_ID,
        "scope": "full-150 R_DEF confirmation on frozen EStG-150 input",
        "authorized_by_user": True,
        "decision": "AUTHORIZED_FOR_EXECUTION",
        "new_calls": PLANNED_CALLS,
        "arm": ARM,
        "treatment_package": "E4 v2 replacement + R_DEF guidance",
        "model": core.MODEL_ALIAS,
        "documented_release": core.MODEL_RELEASE,
        "retry": 0,
        "temperature": core.TEMPERATURE,
        "top_p": core.TOP_P,
        "max_tokens": core.MAX_TOKENS,
        "thinking": {"type": "disabled"},
        "response_format": None,
        "stream": False,
        "budget_sha256": _sha256_file(BUDGET_PATH),
        "schedule_sha256": _sha256_file(SCHEDULE_PATH),
        "execution_contract_sha256": _sha256_file(EXECUTION_CONTRACT_PATH),
        "request_manifest_sha256": _sha256_file(REQUEST_MANIFEST_PATH),
        "prompt_composition_sha256": contract["prompt_binding"]["composition_sha256"],
        "user_authorization_quote": USER_AUTHORIZATION_QUOTE,
        "constraints": {
            "no_A_regeneration": True,
            "no_BASE_full_150": True,
            "no_R_DEF2": True,
            "no_repair_or_regeneration_after_observation": True,
        },
    }


def _render_preflight_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Full-150 R_DEF Confirmation Preflight",
        "",
        f"- Suite: `{result['suite_id']}`",
        f"- Status: **{result['status']}**",
        f"- API calls made: **{result['api_calls_made']}**",
        f"- New R_DEF calls planned: **{result['planned_calls']}**",
        f"- Arm: `{result['arm']}`",
        f"- Treatment package: {result['treatment_package']}",
        "",
        "## Frozen inputs",
        f"- Input SHA-256: `{result['input_sha256']}`",
        f"- Schedule SHA-256: `{result['schedule_sha256']}`",
        f"- Sample membership/order SHA-256: `{result['sample_membership_order_sha256']}`",
        f"- Prompt composition SHA-256: `{result['prompt_composition_sha256']}`",
        "",
        "## A current-contract baseline",
        f"- Rescored A five-field mean F1: `{result['A_current_contract_five_field_mean_f1']}`",
        f"- Expected: `{EXPECTED_A_FIVE_FIELD_MEAN_F1}`",
        f"- Legacy score, separately labeled and not directly comparable: `{LEGACY_A_FIVE_FIELD_MEAN_F1}`",
        f"- Freeze artifact: `{result['A_current_contract_manifest_path']}`",
        "",
        "## Evaluator dry check",
        f"- Status: `{result['dry_check_status']}`",
        f"- Full-150 denominator: `{result['dry_check_denominator']}`",
        "",
        "## Execution command",
        "```powershell",
        result["execution_command"],
        "```",
        "",
        "The comparison is a full-corpus confirmation of the frozen package, not an independent held-out generalization test.",
        "",
    ]
    return "\n".join(lines)


def build() -> dict[str, Any]:
    schedule = _build_schedule()
    _write_json(SCHEDULE_PATH, schedule)
    sample_text_by_id = {row["sample_id"]: row["text"] for row in core.samples(core.SAMPLES_PER_ARM)}
    request_stats = _build_offline_requests(schedule)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    OFFLINE_REQUESTS_PATH.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in request_stats["rows"]
        ),
        encoding="utf-8",
        newline="\n",
    )
    budget = _build_budget(schedule, request_stats)
    _write_json(BUDGET_PATH, budget)
    a_freeze = _rescore_historical_a()
    dry_check = _evaluator_dry_check(a_freeze["manifest"])
    request_manifest = _build_request_manifest(schedule, budget, request_stats)
    _write_json(REQUEST_MANIFEST_PATH, request_manifest)
    execution_contract = _build_execution_contract(
        schedule, budget, request_stats, a_freeze, dry_check
    )
    _write_json(EXECUTION_CONTRACT_PATH, execution_contract)
    authorization_event = _build_authorization_event(
        schedule, budget, execution_contract, request_manifest
    )
    _write_json(AUTHORIZATION_EVENT_PATH, authorization_event)
    # Re-write the request manifest with the final contract/authorization
    # hashes only if a future schema version needs them; current fields do not.
    result = {
        "schema_version": "sep_c3_definition_full150_confirmation_preflight@1.0.0",
        "suite_id": SUITE_ID,
        "status": "PASS_FROZEN_BEFORE_NEW_API",
        "api_calls_made": 0,
        "arm": ARM,
        "treatment_package": "E4 v2 replacement + R_DEF guidance",
        "planned_calls": PLANNED_CALLS,
        "input_sha256": _sha256_file(core.ESTG_INPUT),
        "schedule_sha256": _sha256_file(SCHEDULE_PATH),
        "sample_membership_order_sha256": schedule["sample_membership_order_sha256"],
        "prompt_composition_sha256": execution_contract["prompt_binding"]["composition_sha256"],
        "A_current_contract_five_field_mean_f1": EXPECTED_A_FIVE_FIELD_MEAN_F1,
        "A_current_contract_manifest_path": str((A_OUT_DIR / "manifest.json").relative_to(ROOT)).replace("\\", "/"),
        "dry_check_status": dry_check["status"],
        "dry_check_denominator": dry_check["prediction_envelope_count"],
        "execution_command": (
            "cd formal_experiment && python scripts/run_sep_c3_definition_full150_confirmation_v1.py "
            "--execute --allow-llm --project-env"
        ),
        "authorization_event_path": str(AUTHORIZATION_EVENT_PATH.relative_to(ROOT)).replace("\\", "/"),
    }
    _write_json(PREFLIGHT_REPORT_PATH, result)
    _write_text(PREFLIGHT_REPORT_MD_PATH, _render_preflight_markdown(result))
    return result


def main() -> int:
    result = build()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

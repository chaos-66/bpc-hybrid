# -*- coding: utf-8 -*-
"""Execute the frozen full-150 R_DEF confirmation run.

Exactly 150 scheduled real API calls are sent: one call for each frozen EStG-150
sample, with retry=0 and no result-dependent repair or regeneration.  Historical
Arm A is not called; its current-contract rescore is frozen by the preparation
step before this runner can execute.

Usage:
  python scripts/prepare_sep_c3_definition_full150_confirmation_v1.py
  python scripts/run_sep_c3_definition_full150_confirmation_v1.py --check
  python scripts/run_sep_c3_definition_full150_confirmation_v1.py --execute --allow-llm --project-env
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import run_sep_c3_targeted_refinement_v1 as tr  # noqa: E402
import run_sep_c3_definition_targeted_refinement_v1 as dtr  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402
import prepare_sep_c3_definition_full150_confirmation_v1 as prep  # noqa: E402


SUITE_ID = prep.SUITE_ID
ARM = prep.ARM
REPEAT_ID = prep.REPEAT_ID
PLANNED_CALLS = prep.PLANNED_CALLS
CALL_CAP = prep.CALL_CAP
OUT_DIR = prep.A_OUT_DIR.parent.parent  # outputs/development/sep_c3_definition_full150_confirmation_v1
EXECUTION_REPORT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_execution_v1.json"
)
EXECUTION_MD_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_full150_confirmation_execution_v1.md"
)

# Reuse the targeted-refinement call/persist/parse/evaluate stack with the
# frozen full-150 schedule and the single R_DEF arm.
tr.SUITE_ID = SUITE_ID
tr.ARMS = (ARM,)
tr.REPEAT_ID = REPEAT_ID
tr.PLANNED_CALLS = PLANNED_CALLS
tr.CALL_CAP = CALL_CAP
tr.OUT_DIR = OUT_DIR
tr.MODEL_ALIAS = core.MODEL_ALIAS
tr.MODEL_RELEASE = core.MODEL_RELEASE
tr.TEMPERATURE = core.TEMPERATURE
tr.TOP_P = core.TOP_P
tr.MAX_TOKENS = core.MAX_TOKENS


class Full150RunError(RuntimeError):
    """A fail-closed full-150 runner precondition failed."""


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


def _sha256_file(path: Path) -> str:
    return core._sha256_file(path)


def _sample_order() -> list[str]:
    return [str(row["sample_id"]) for row in core.samples(core.SAMPLES_PER_ARM)]


def _load_schedule() -> dict[str, Any]:
    if not prep.SCHEDULE_PATH.is_file():
        raise Full150RunError(f"schedule not found: {prep.SCHEDULE_PATH}")
    schedule = _read_json(prep.SCHEDULE_PATH)
    entries = schedule.get("entries")
    if not isinstance(entries, list):
        raise Full150RunError("schedule entries missing")
    canonical = _canonical_json(entries)
    if schedule.get("entries_sha256") != core._sha256_text(canonical):
        raise Full150RunError("schedule entries hash mismatch")
    if len(entries) != PLANNED_CALLS:
        raise Full150RunError(
            f"schedule must contain exactly {PLANNED_CALLS} entries"
        )
    if schedule.get("sample_count") != PLANNED_CALLS:
        raise Full150RunError("schedule sample_count mismatch")
    expected_ids = _sample_order()
    observed_ids = [str(entry.get("sample_id")) for entry in entries]
    if observed_ids != expected_ids:
        raise Full150RunError("schedule sample membership/order does not match frozen input")
    if schedule.get("sample_membership_order") != expected_ids:
        raise Full150RunError("schedule membership order field mismatch")
    if schedule.get("sample_membership_order_sha256") != core._sha256_text(
        _canonical_json(expected_ids)
    ):
        raise Full150RunError("schedule membership order hash mismatch")
    for entry in entries:
        if str(entry.get("arm")) != ARM:
            raise Full150RunError(
                f"schedule contains unexpected arm: {entry.get('arm')!r}"
            )
    return schedule


def _authorization_ok(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"authorization event not found: {path}"
    data = _read_json(path)
    if data.get("suite_id") != SUITE_ID:
        return False, "authorization suite_id mismatch"
    if data.get("decision") != "AUTHORIZED_FOR_EXECUTION":
        return False, "authorization decision mismatch"
    if data.get("authorized_by_user") is not True:
        return False, "authorization lacks authorized_by_user=true"
    if int(data.get("new_calls", -1)) != PLANNED_CALLS:
        return False, "authorization new_calls mismatch"
    if data.get("arm") != ARM:
        return False, "authorization arm mismatch"
    if int(data.get("retry", -1)) != 0:
        return False, "authorization retry mismatch"
    return True, "authorized"


def _validate_prompt() -> None:
    candidate_manifest_path = (
        ROOT / "prompts" / "sun_compat"
        / "modular_definition_refinement_v1" / "generated" / "manifest.json"
    )
    candidate_manifest = _read_json(candidate_manifest_path)
    prompt = dr.render_definition_prompt(ARM)
    generated = candidate_manifest["prompts"][ARM]
    if core._sha256_text(prompt.system_prompt) != generated["system_sha256"]:
        raise Full150RunError("R_DEF system prompt hash mismatch vs candidate manifest")
    if core._sha256_text(prompt.user_prompt_template) != generated["user_sha256"]:
        raise Full150RunError("R_DEF user prompt hash mismatch vs candidate manifest")
    if prompt.composition_sha256 != generated["composition_sha256"]:
        raise Full150RunError("R_DEF composition hash mismatch vs candidate manifest")
    if _sha256_file(dr.generated_path(ARM)) != generated["markdown_sha256"]:
        raise Full150RunError("R_DEF generated prompt markdown hash mismatch")
    if _sha256_file(candidate_manifest_path) != _read_json(
        prep.REQUEST_MANIFEST_PATH
    )["prompt_binding"]["generated_manifest_sha256"]:
        raise Full150RunError("candidate manifest hash mismatch vs request manifest")


def validate_contracts() -> dict[str, Any]:
    errors: list[str] = []
    for path in (
        prep.SCHEDULE_PATH,
        prep.BUDGET_PATH,
        prep.EXECUTION_CONTRACT_PATH,
        prep.AUTHORIZATION_EVENT_PATH,
        prep.OFFLINE_REQUESTS_PATH,
        prep.REQUEST_MANIFEST_PATH,
        prep.DRY_CHECK_PATH,
        prep.A_OUT_DIR / "canonical_predictions.jsonl",
        prep.A_OUT_DIR / "manifest.json",
    ):
        if not path.is_file():
            errors.append(f"missing frozen artifact: {path}")

    if not errors:
        try:
            schedule = _load_schedule()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"schedule validation failed: {exc}")
            schedule = None
        try:
            budget = core._load_budget(
                prep.BUDGET_PATH,
                planned_calls=PLANNED_CALLS,
                call_cap=CALL_CAP,
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(f"budget validation failed: {exc}")
            budget = None
        if schedule is not None and budget is not None:
            if budget.get("arms") != [ARM]:
                errors.append("budget arms mismatch")
            if budget.get("calls_per_arm") != {ARM: PLANNED_CALLS}:
                errors.append("budget calls_per_arm mismatch")
            if budget.get("model", {}).get("id") != core.MODEL_ALIAS:
                errors.append("budget model alias mismatch")
            if budget.get("model", {}).get("documented_release") != core.MODEL_RELEASE:
                errors.append("budget model release mismatch")
            expected_inference = {
                "temperature": core.TEMPERATURE,
                "top_p": core.TOP_P,
                "max_tokens": core.MAX_TOKENS,
                "retry": 0,
                "stream": False,
                "thinking": {"type": "disabled"},
                "response_format": None,
            }
            if budget.get("inference") != expected_inference:
                errors.append("budget inference settings mismatch")
            if budget.get("schedule_binding", {}).get("sha256") != _sha256_file(
                prep.SCHEDULE_PATH
            ):
                errors.append("budget schedule hash mismatch")
            if budget.get("data_binding", {}).get("input_sha256") != _sha256_file(
                core.ESTG_INPUT
            ):
                errors.append("budget input hash mismatch")
            if budget.get("data_binding", {}).get("gold_sha256") != _sha256_file(
                core.FORMAL_GOLD
            ):
                errors.append("budget Gold hash mismatch")
            if budget.get("parser_binding", {}).get("schema_adapter", {}).get(
                "sha256"
            ) != _sha256_file(ROOT / "src" / "bpc_hybrid" / "d1_schema_adapter.py"):
                errors.append("budget schema-adapter hash mismatch")
            if budget.get("evaluator_binding", {}).get("coarse_evaluator", {}).get(
                "sha256"
            ) != _sha256_file(
                ROOT / "src" / "bpc_hybrid" / "sep_c3_modular_evaluation.py"
            ):
                errors.append("budget evaluator hash mismatch")
            request_manifest = _read_json(prep.REQUEST_MANIFEST_PATH)
            if int(request_manifest.get("request_count", -1)) != PLANNED_CALLS:
                errors.append("request manifest request_count mismatch")
            if request_manifest.get("offline_requests_sha256") != _sha256_file(
                prep.OFFLINE_REQUESTS_PATH
            ):
                errors.append("request manifest offline request hash mismatch")
            if request_manifest.get("schedule_sha256") != _sha256_file(prep.SCHEDULE_PATH):
                errors.append("request manifest schedule hash mismatch")
            contract = _read_json(prep.EXECUTION_CONTRACT_PATH)
            if contract.get("suite_id") != SUITE_ID:
                errors.append("execution contract suite_id mismatch")
            if contract.get("status") != "FROZEN_BEFORE_NEW_API":
                errors.append("execution contract is not frozen")
            if int(contract.get("arms", {}).get(ARM, {}).get("new_calls", -1)) != PLANNED_CALLS:
                errors.append("execution contract R_DEF new_calls mismatch")
            if int(contract.get("arms", {}).get("A", {}).get("new_calls", -1)) != 0:
                errors.append("execution contract A new_calls must be 0")
            if bool(contract.get("arms", {}).get("BASE", {}).get("executed", True)):
                errors.append("execution contract unexpectedly marks BASE executed")
            if contract.get("schedule_binding", {}).get("sha256") != _sha256_file(
                prep.SCHEDULE_PATH
            ):
                errors.append("execution contract schedule hash mismatch")
            if contract.get("budget_binding", {}).get("sha256") != _sha256_file(
                prep.BUDGET_PATH
            ):
                errors.append("execution contract budget hash mismatch")
            if contract.get("prompt_binding", {}).get("composition_sha256") != (
                dr.render_definition_prompt(ARM).composition_sha256
            ):
                errors.append("execution contract prompt hash mismatch")
            if contract.get("evaluator_dry_check", {}).get("status") != "PASS":
                errors.append("execution contract dry check is not PASS")
            a_manifest = _read_json(prep.A_OUT_DIR / "manifest.json")
            if a_manifest.get("status") != "FROZEN_BEFORE_R_DEF_EVALUATION_INSPECTION":
                errors.append("A current-contract freeze status mismatch")
            if abs(
                float(a_manifest.get("current_contract", {}).get("five_field_mean_f1", -1))
                - prep.EXPECTED_A_FIVE_FIELD_MEAN_F1
            ) > 1e-12:
                errors.append("A current-contract baseline score mismatch")
            if contract.get("A_current_contract_freeze", {}).get(
                "manifest_sha256"
            ) != _sha256_file(prep.A_OUT_DIR / "manifest.json"):
                errors.append("execution contract A freeze hash mismatch")
            dry_check = _read_json(prep.DRY_CHECK_PATH)
            if dry_check.get("status") != "PASS":
                errors.append("dry check status mismatch")
            if int(dry_check.get("prediction_envelope_count", -1)) != PLANNED_CALLS:
                errors.append("dry check denominator mismatch")
            auth_ok, auth_reason = _authorization_ok(prep.AUTHORIZATION_EVENT_PATH)
            if not auth_ok:
                errors.append(f"authorization check failed: {auth_reason}")
            try:
                _validate_prompt()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"prompt validation failed: {exc}")

    raw_path = OUT_DIR / ARM / REPEAT_ID / "raw_responses.jsonl"
    ledger_path = OUT_DIR / ARM / REPEAT_ID / "calls_ledger.jsonl"
    if raw_path.exists() or ledger_path.exists():
        errors.append(
            "run directory already contains raw/ledger state; refusing a second "
            "or duplicate full-150 execution"
        )
    return {
        "schema_version": "sep_c3_definition_full150_contract_validation@1.0.0",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def _load_config(project_env: bool):
    return core._load_config(project_env)


def execute(*, project_env: bool = False) -> dict[str, Any]:
    validation = validate_contracts()
    if validation["status"] != "pass":
        raise Full150RunError(
            "contract validation failed: " + "; ".join(validation["errors"])
        )
    schedule = _load_schedule()
    budget = core._load_budget(
        prep.BUDGET_PATH,
        planned_calls=PLANNED_CALLS,
        call_cap=CALL_CAP,
    )
    samples = core.samples(core.SAMPLES_PER_ARM)
    sample_by_id = {str(row["sample_id"]): row for row in samples}
    gold_doc = _read_json(core.FORMAL_GOLD)
    run_out_dir = OUT_DIR
    run_out_dir.mkdir(parents=True, exist_ok=True)

    config = _load_config(project_env)
    core._validate_runtime_config(config, budget)
    transport = core.RealAPITransport(
        config,
        timeout_seconds=180.0,
        policy=core.H1RequestPolicy(
            stream=False,
            thinking={"type": "disabled"},
            response_format=None,
        ),
    )
    gate = core.AblationBudgetGate(budget, core.MODEL_ALIAS)

    result: dict[str, Any] = {
        "schema_version": "sep_c3_definition_full150_execution@1.0.0",
        "suite_id": SUITE_ID,
        "arm": ARM,
        "treatment_package": "E4 v2 replacement + R_DEF guidance",
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "actual_calls": 0,
        "complete": False,
        "aborted": False,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "schedule_sha256": _sha256_file(prep.SCHEDULE_PATH),
        "budget_sha256": _sha256_file(prep.BUDGET_PATH),
        "model": {
            "id": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "thinking": {"type": "disabled"},
            "response_format": None,
            "stream": False,
            "retry": 0,
        },
        "output_validation_path_version": prep.OUTPUT_VALIDATION_PATH_VERSION,
    }
    new_sends = 0
    started = time.time()
    with tr.RunLock(run_out_dir / ".run.lock"):
        gate.calls_made = 0
        try:
            for entry in schedule["entries"]:
                sid = str(entry["sample_id"])
                sample = sample_by_id.get(sid)
                if sample is None:
                    raise Full150RunError(f"schedule references unknown sample: {sid}")
                call = tr._call_once(
                    ARM,
                    sample,
                    transport,
                    gate,
                    budget,
                    execution_index=int(entry["execution_index"]),
                    arm_order_within_sample=1,
                    enforce_off_peak=False,
                )
                tr._persist_call(ARM, call, run_out_dir)
                new_sends += 1
                if gate.aborted or call.get("gate_error"):
                    raise Full150RunError(
                        f"run stopped after sample {sid}: "
                        f"{call.get('gate_error') or gate.abort_reason}"
                    )
            raw_rows = _read_jsonl(run_out_dir / ARM / REPEAT_ID / "raw_responses.jsonl")
            raw_by_sid = {str(row["sample_id"]): row for row in raw_rows}
            if len(raw_by_sid) != PLANNED_CALLS:
                raise Full150RunError(
                    f"completed run has {len(raw_by_sid)} unique raw samples, "
                    f"expected {PLANNED_CALLS}"
                )
            run = tr._build_arm_outputs(
                ARM,
                raw_by_sid,
                samples,
                gold_doc,
                run_out_dir,
                _sha256_file(prep.SCHEDULE_PATH),
                actual_call_count=new_sends,
                resumed_completed_count=0,
            )
            evaluation = run["evaluation"]
            result["actual_calls"] = new_sends
            result["complete"] = new_sends == PLANNED_CALLS
            result["official_evaluation"] = {
                "primary_metric": evaluation["primary_metric"],
                "coarse_five_field_mean_f1": evaluation["coarse_five_field_mean_f1"],
                "coarse_five_field_micro_f1": evaluation["coarse_five_field_micro"]["f1"],
                "five_fields": evaluation["five_fields"],
                "modality_labels": evaluation["modality_labels"],
                "denominator": evaluation["denominator"],
                "failed_count": evaluation["failed_count"],
            }
        except Exception as exc:  # noqa: BLE001 - persist terminal partial state.
            result["aborted"] = True
            result["abort_reason"] = f"{type(exc).__name__}: {exc}"
            result["actual_calls"] = new_sends
    result["budget_gate"] = gate.to_dict()
    result["runtime_seconds"] = round(time.time() - started, 3)
    result["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(run_out_dir / "execution_summary.json", result)
    if result.get("complete"):
        _write_json(EXECUTION_REPORT_PATH, result)
        _write_text(EXECUTION_MD_PATH, _render_markdown(result))
    return result


def _render_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C3 Definition Full-150 R_DEF Confirmation Execution",
        "",
        f"- Suite: `{result['suite_id']}`",
        f"- Arm: `{result['arm']}`",
        f"- Treatment package: {result['treatment_package']}",
        f"- Planned calls: {result['planned_calls']}",
        f"- Actual calls: {result['actual_calls']}",
        f"- Complete: `{result['complete']}`",
        f"- Aborted: `{result['aborted']}`",
        f"- Schedule SHA-256: `{result['schedule_sha256']}`",
        f"- Budget SHA-256: `{result['budget_sha256']}`",
    ]
    if result.get("official_evaluation"):
        ev = result["official_evaluation"]
        lines += [
            "",
            "## Official evaluation",
            f"- Primary metric: `{ev['primary_metric']}`",
            f"- Five-field mean F1: `{ev['coarse_five_field_mean_f1']}`",
            f"- Five-field micro F1: `{ev['coarse_five_field_micro_f1']}`",
            f"- Failed envelopes (denominator retained): `{ev['failed_count']}`",
        ]
    if result.get("abort_reason"):
        lines += ["", f"- Abort reason: `{result['abort_reason']}`"]
    lines += [
        "",
        "No retry, repair, regeneration, R_DEF2, BASE full-150, or A rerun was performed by this executor.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--project-env", action="store_true")
    args = parser.parse_args()

    if args.check:
        validation = validate_contracts()
        if validation["status"] == "pass" and args.project_env:
            try:
                config = _load_config(True)
                budget = core._load_budget(
                    prep.BUDGET_PATH,
                    planned_calls=PLANNED_CALLS,
                    call_cap=CALL_CAP,
                )
                core._validate_runtime_config(config, budget)
                validation["runtime_config"] = {
                    "provider": config.provider,
                    "enabled": bool(config.enabled),
                    "model": config.model,
                    "temperature": config.temperature,
                    "top_p": config.top_p,
                    "max_tokens": int(config.max_tokens),
                    "api_key_present": bool(config.api_key),
                }
            except Exception as exc:  # noqa: BLE001
                validation["status"] = "fail"
                validation.setdefault("errors", []).append(
                    f"runtime configuration validation failed: {type(exc).__name__}: {exc}"
                )
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0 if validation["status"] == "pass" else 1
    if args.execute:
        if not args.allow_llm:
            print(json.dumps({
                "status": "refused",
                "reason": "--execute requires --allow-llm",
            }, ensure_ascii=False, indent=2))
            return 2
        result = execute(project_env=args.project_env)
        print(json.dumps({
            "status": "complete" if result.get("complete") else "aborted",
            "actual_calls": result.get("actual_calls"),
            "abort_reason": result.get("abort_reason"),
            "summary": str((OUT_DIR / "execution_summary.json").relative_to(ROOT)).replace("\\", "/"),
        }, ensure_ascii=False, indent=2))
        return 0 if result.get("complete") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


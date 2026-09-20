# -*- coding: utf-8 -*-
"""Guarded real-run entry for the frozen SEP-C3 definition targeted panel.

This module reuses the existing targeted-refinement call/parse/evaluate
mechanics but binds them to the frozen BASE/R_DEF candidate prompt family and
the 42-sample targeted panel.  It is intentionally fail-closed.

No network call occurs unless all of the following are true:
  * --execute --allow-llm are supplied;
  * --authorization points to a matching authorization event;
  * the frozen panel/schedule/budget/prompt/request hashes validate;
  * the leakage audit has no blocking check.

The default mode is validation only.
"""

from __future__ import annotations

import argparse
import json
import sys
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

import prepare_sep_c3_definition_targeted_execution_v1 as prep  # noqa: E402


SUITE_ID = prep.SUITE_ID
ARMS = prep.ARMS
REPEAT_ID = prep.REPEAT_ID
PLANNED_CALLS = prep.PLANNED_CALLS
CALL_CAP = prep.CALL_CAP
OUT_DIR = (
    ROOT / "outputs" / "development"
    / "sep_c3_definition_targeted_refinement_v1"
)
EXECUTION_SUMMARY_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_refinement_v1_execution.json"
)

# Bind the existing targeted-refinement execution helpers to the candidate
# prompt renderer.  This does not modify any active registry or active prompt.
tr.rp = dr
tr.SUITE_ID = SUITE_ID
tr.ARMS = ARMS
tr.REPEAT_ID = REPEAT_ID
tr.PLANNED_CALLS = PLANNED_CALLS
tr.CALL_CAP = CALL_CAP
tr.MODEL_ALIAS = core.MODEL_ALIAS
tr.MODEL_RELEASE = core.MODEL_RELEASE
tr.TEMPERATURE = core.TEMPERATURE
tr.TOP_P = core.TOP_P
tr.MAX_TOKENS = core.MAX_TOKENS
dr.render_refinement_prompt = dr.render_definition_prompt  # type: ignore[attr-defined]
dr.ARM_REPAIRS = {  # type: ignore[attr-defined]
    "BASE": "candidate E4 v2; no R_DEF",
    "R_DEF": "candidate E4 v2 + R_DEF definition guidance",
}


class DefinitionTargetedRunError(RuntimeError):
    """A fail-closed runner precondition failed."""


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return core._sha256_file(path)


def validate_contracts() -> dict[str, Any]:
    errors: list[str] = []
    panel = _read_json(prep.PANEL_PATH)
    schedule = _read_json(prep.SCHEDULE_PATH)
    budget = _read_json(prep.BUDGET_PATH)
    request_manifest = _read_json(prep.REQUEST_MANIFEST_PATH)
    candidate_manifest = _read_json(
        ROOT / "prompts" / "sun_compat"
        / "modular_definition_refinement_v1" / "generated" / "manifest.json"
    )

    if panel.get("status") != "FROZEN_BEFORE_NEW_API":
        errors.append("panel status is not frozen")
    if int(panel["panel_accounting"]["unique_sample_count_N"]) != 42:
        errors.append("panel N != 42")
    if _sha256_file(prep.PANEL_PATH) != request_manifest.get("panel_sha256"):
        errors.append("request manifest panel hash mismatch")
    if int(budget.get("planned_calls", 0)) != PLANNED_CALLS:
        errors.append("budget planned_calls mismatch")
    if int(budget.get("call_cap", 0)) != CALL_CAP:
        errors.append("budget call_cap mismatch")
    if budget.get("arms") != list(ARMS):
        errors.append("budget arms mismatch")
    if budget.get("model", {}).get("id") != core.MODEL_ALIAS:
        errors.append("budget model mismatch")
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
        errors.append("budget inference mismatch")
    if _sha256_file(prep.SCHEDULE_PATH) != budget.get(
        "schedule_binding", {}
    ).get("sha256"):
        errors.append("budget schedule hash mismatch")
    if _sha256_file(prep.OFFLINE_REQUESTS_PATH) != request_manifest.get(
        "offline_requests_sha256"
    ):
        errors.append("offline request capsule hash mismatch")
    if request_manifest.get("request_count") != PLANNED_CALLS:
        errors.append("request capsule count mismatch")
    for arm in ARMS:
        prompt = dr.render_definition_prompt(arm)
        expected = budget.get("prompt_binding", {}).get(
            "arm_hashes", {}
        ).get(arm, {})
        if core._sha256_text(prompt.system_prompt) != expected.get(
            "system_sha256"
        ):
            errors.append(f"budget system hash mismatch for {arm}")
        if core._sha256_text(prompt.user_prompt_template) != expected.get(
            "user_sha256"
        ):
            errors.append(f"budget user hash mismatch for {arm}")
        if prompt.composition_sha256 != expected.get("composition_sha256"):
            errors.append(f"budget composition hash mismatch for {arm}")
        generated = candidate_manifest.get("prompts", {}).get(arm, {})
        if prompt.composition_sha256 != generated.get("composition_sha256"):
            errors.append(f"candidate manifest composition mismatch for {arm}")

    entries = schedule.get("entries")
    if not isinstance(entries, list) or len(entries) != PLANNED_CALLS:
        errors.append("schedule entry count mismatch")
    else:
        counts = {arm: 0 for arm in ARMS}
        for entry in entries:
            arm = str(entry.get("arm"))
            if arm not in counts:
                errors.append(f"schedule unknown arm: {arm!r}")
            else:
                counts[arm] += 1
            if str(entry.get("sample_id")) not in set(
                panel["selected_sample_ids"]
            ):
                errors.append(
                    f"schedule sample outside panel: {entry.get('sample_id')}"
                )
        if any(value != 42 for value in counts.values()):
            errors.append(f"schedule per-arm counts mismatch: {counts}")

    leakage_status = None
    leakage_path = (
        ROOT / "outputs" / "reports"
        / "sep_c3_definition_targeted_leakage_audit_v1.json"
    )
    if leakage_path.is_file():
        leakage_status = _read_json(leakage_path).get("status")
    if leakage_status != "PASS":
        errors.append(
            f"leakage audit is not clean: {leakage_status!r}"
        )

    return {
        "schema_version": (
            "sep_c3_definition_targeted_contract_validation@1.0.0"
        ),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "leakage_status": leakage_status,
    }


def _authorization_ok(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"authorization file not found: {path}"
    data = _read_json(path)
    if data.get("suite_id") != SUITE_ID:
        return False, "authorization suite_id mismatch"
    if int(data.get("new_calls", -1)) != PLANNED_CALLS:
        return False, "authorization new_calls mismatch"
    if data.get("authorized_by_user") is not True:
        return False, "authorization lacks authorized_by_user=true"
    if data.get("decision") != "AUTHORIZED_FOR_EXECUTION":
        return False, "authorization decision is not AUTHORIZED_FOR_EXECUTION"
    return True, "authorized"


def execute(
    *,
    project_env: bool = False,
    transport_factory: Any = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    validation = validate_contracts()
    if validation["status"] != "pass":
        raise DefinitionTargetedRunError(
            "contract validation failed: " + "; ".join(validation["errors"])
        )
    run_out_dir = Path(out_dir or OUT_DIR)
    panel = _read_json(prep.PANEL_PATH)
    schedule = _read_json(prep.SCHEDULE_PATH)
    budget = _read_json(prep.BUDGET_PATH)
    gold_doc = _read_json(core.FORMAL_GOLD)

    all_samples = core.samples(core.SAMPLES_PER_ARM)
    sample_by_id = {str(row["sample_id"]): row for row in all_samples}
    panel_rows = [
        sample_by_id[sid] for sid in panel["selected_sample_ids"]
    ]

    result: dict[str, Any] = {
        "schema_version": "sep_c3_definition_targeted_execution@1.0.0",
        "suite_id": SUITE_ID,
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "actual_calls": 0,
        "complete": False,
        "aborted": False,
        "arms": list(ARMS),
        "model": {
            "id": core.MODEL_ALIAS,
            "documented_release": core.MODEL_RELEASE,
            "temperature": core.TEMPERATURE,
            "top_p": core.TOP_P,
            "max_tokens": core.MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "panel_sha256": _sha256_file(prep.PANEL_PATH),
        "schedule_sha256": _sha256_file(prep.SCHEDULE_PATH),
    }

    with tr.RunLock(run_out_dir / ".run.lock"):
        state = tr._load_persisted_state(run_out_dir)
        tr._check_in_doubt(state)
        gate = core.AblationBudgetGate(budget, core.MODEL_ALIAS)
        core._restore_gate(gate, arms=ARMS, out_dir=run_out_dir)

        if transport_factory is None:
            config = core._load_config(project_env)
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
        else:
            transport = transport_factory()

        initial_raw_counts = {
            arm: len(state[arm]["raw_by_sid"]) for arm in ARMS
        }
        new_sends = {arm: 0 for arm in ARMS}
        try:
            for entry in schedule["entries"]:
                arm = str(entry["arm"])
                sid = str(entry["sample_id"])
                if sid in state[arm]["raw_by_sid"]:
                    continue
                if sid in state[arm]["ledger_by_sid"]:
                    raise DefinitionTargetedRunError(
                        f"in_doubt sample requires manual resolution: {arm}/{sid}"
                    )
                sample = sample_by_id.get(sid)
                if sample is None:
                    raise DefinitionTargetedRunError(
                        f"schedule references unknown sample: {sid}"
                    )
                call = tr._call_once(
                    arm,
                    sample,
                    transport,
                    gate,
                    budget,
                    execution_index=int(entry["execution_index"]),
                    arm_order_within_sample=int(
                        entry["arm_order_within_sample"]
                    ),
                    enforce_off_peak=False,
                )
                tr._persist_call(arm, call, run_out_dir)
                state[arm]["raw_by_sid"][sid] = call
                state[arm]["raw_rows"].append(call)
                state[arm]["ledger_by_sid"][sid] = {
                    "sample_id": sid,
                    "arm": arm,
                    "state": "completed",
                }
                new_sends[arm] += 1
                if gate.aborted or call.get("gate_error"):
                    raise DefinitionTargetedRunError(
                        f"arm {arm} stopped after sample {sid}: "
                        f"{call.get('gate_error') or gate.abort_reason}"
                    )

            for arm in ARMS:
                expected = sum(1 for e in schedule["entries"] if e["arm"] == arm)
                if len(state[arm]["raw_by_sid"]) != expected:
                    raise DefinitionTargetedRunError(
                        f"arm {arm} completed {len(state[arm]['raw_by_sid'])}/"
                        f"{expected} scheduled samples"
                    )
                run = tr._build_arm_outputs(
                    arm,
                    state[arm]["raw_by_sid"],
                    panel_rows,
                    gold_doc,
                    run_out_dir,
                    _sha256_file(prep.SCHEDULE_PATH),
                    actual_call_count=new_sends[arm],
                    resumed_completed_count=initial_raw_counts[arm],
                )
                result.setdefault("runs", []).append({
                    "arm": arm,
                    "actual_call_count": new_sends[arm],
                    "resumed_completed_count": initial_raw_counts[arm],
                    "failed_count": run["manifest"]["failed_count"],
                    "primary_metric": run["evaluation"]["primary_metric"],
                    "coarse_five_field_mean_f1": run["evaluation"][
                        "coarse_five_field_mean_f1"
                    ],
                    "coarse_five_field_micro_f1": run["evaluation"][
                        "coarse_five_field_micro"
                    ]["f1"],
                })
            result["actual_calls"] = sum(new_sends.values())
            result["complete"] = (
                result["actual_calls"] == PLANNED_CALLS
                and gate.calls_made == PLANNED_CALLS
            )
        except Exception as exc:  # noqa: BLE001 - persist partial state.
            result["aborted"] = True
            result["abort_reason"] = f"{type(exc).__name__}: {exc}"
            result["actual_calls"] = sum(new_sends.values())
        result["budget_gate"] = gate.to_dict()
        result["new_sends_per_arm"] = dict(new_sends)
        result["raw_counts_per_arm"] = {
            arm: len(state[arm]["raw_by_sid"]) for arm in ARMS
        }

    run_out_dir.mkdir(parents=True, exist_ok=True)
    (run_out_dir / "execution_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if result.get("complete"):
        EXECUTION_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXECUTION_SUMMARY_PATH.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--project-env", action="store_true")
    args = parser.parse_args()

    if args.prepare:
        result = prep.build(write=True)
        print(json.dumps({
            "status": "prepared_offline",
            "new_calls": result["request_stats"]["planned_calls"],
            "authorization_decision": result["authorization_request"][
                "decision"
            ],
        }, ensure_ascii=False, indent=2))

    if args.check:
        validation = validate_contracts()
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        if validation["status"] != "pass":
            return 1

    if args.execute:
        if not args.allow_llm:
            print(json.dumps({
                "status": "refused",
                "reason": "--execute requires --allow-llm and a matching authorization event",
            }, ensure_ascii=False, indent=2))
            return 2
        if args.authorization is None:
            print(json.dumps({
                "status": "refused",
                "reason": "--execute requires --authorization",
            }, ensure_ascii=False, indent=2))
            return 2
        allowed, reason = _authorization_ok(args.authorization)
        if not allowed:
            print(json.dumps({
                "status": "refused",
                "reason": reason,
            }, ensure_ascii=False, indent=2))
            return 2
        result = execute(project_env=args.project_env)
        print(json.dumps({
            "status": "complete" if result.get("complete") else "aborted",
            "actual_calls": result.get("actual_calls"),
            "abort_reason": result.get("abort_reason"),
        }, ensure_ascii=False, indent=2))
        return 0 if result.get("complete") else 1

    if not any((args.check, args.prepare, args.execute)):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
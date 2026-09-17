# -*- coding: utf-8 -*-
"""Interleaved real-run entry for the SEP-C3 targeted-refinement arms.

Arms (common + E baseline plus independently switchable repairs):
  A = common + E
  B = common + E + R_A
  C = common + E + R_C
  D = common + E + R_A + R_C

ZERO network by default.  Real sends require ``--execute --allow-llm`` and the
prepared budget/schedule files.  The schedule is generated before any call and
is loaded, never reordered, by the runner.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_barrientos_ablation_suite_v2 as base  # noqa: E402
import run_sep_c3_modular_ablation_v1 as core  # noqa: E402
import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402
import prepare_sep_c3_targeted_refinement_v1 as prep  # noqa: E402
from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from bpc_hybrid.llm_client import LLMRequest, RealAPITransport  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    attempt_rows,
    evaluate_coarse,
)


SUITE_ID = "SEP-C3-TARGETED-REFINEMENT-001"
ARMS = tuple(rp.ARMS)
SAMPLES_PER_ARM = 150
PLANNED_CALLS = 600
CALL_CAP = 750
REPEAT_ID = "repeat-01"
MODEL_ALIAS = core.MODEL_ALIAS
MODEL_RELEASE = core.MODEL_RELEASE
TEMPERATURE = core.TEMPERATURE
TOP_P = core.TOP_P
MAX_TOKENS = core.MAX_TOKENS

BUDGET_PATH = prep.BUDGET_PATH
SCHEDULE_PATH = prep.SCHEDULE_PATH
OUT_DIR = ROOT / "outputs" / "development" / "sep_c3_targeted_refinement_v1"
RESULT_REPORT = (
    ROOT / "outputs" / "reports"
    / "sep_c3_targeted_refinement_v1_execution.json"
)
RUN_LOCK = OUT_DIR / ".run.lock"


class RefinementRunError(RuntimeError):
    """A fail-closed runner precondition failed."""


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def _arm_dir(arm: str, out_dir: Path | None = None) -> Path:
    return Path(out_dir or OUT_DIR) / arm / REPEAT_ID


def _read_json(path: Path) -> dict[str, Any]:
    return core._read_json(path)


def _write_json(path: Path, value: Any) -> None:
    core._write_json(path, value)


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    core._append_jsonl(path, dict(row))


def _bare_json_status(content: str) -> str:
    text = (content or "").strip()
    if not text:
        return "empty"
    if text.startswith("```"):
        return "markdown_fenced"
    try:
        value = json.loads(text)
    except Exception:  # noqa: BLE001 - classification only.
        return "non_object_prefix" if not text.startswith("{") else "invalid_json"
    if isinstance(value, dict) and text.startswith("{") and text.endswith("}"):
        return "bare_json_object"
    return "json_parsable_non_object"


def _render_prompt(arm: str, sample_id: str, source_text: str) -> tuple[str, str]:
    prompt = rp.render_refinement_prompt(arm)
    user = prompt.render_user(sample_id, source_text)
    if not prompt.system_prompt or not user:
        raise RefinementRunError(f"empty rendered prompt for arm {arm}")
    return prompt.system_prompt, user


def request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    system, user = _render_prompt(arm, sample_id, source_text)
    return {
        "model": MODEL_ALIAS,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "disabled"},
    }


def _call_once(
    arm: str,
    sample: Mapping[str, str],
    transport: Any,
    gate: core.AblationBudgetGate,
    budget: Mapping[str, Any],
    *,
    execution_index: int,
    arm_order_within_sample: int,
    enforce_off_peak: bool,
) -> dict[str, Any]:
    sid = str(sample["sample_id"])
    text = str(sample["text"])
    prompt = rp.render_refinement_prompt(arm)
    system, user = _render_prompt(arm, sid, text)
    body = request_body(arm, sid, text)
    body_bytes = json.dumps(
        body, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    projected = math.ceil(len(body_bytes) / 3)
    gate.check_before_send(projected, MAX_TOKENS)
    if enforce_off_peak:
        base._require_beijing_off_peak()

    started_at = datetime.now(timezone.utc).isoformat()
    request_id = f"{arm}:{sid}:{time.time_ns()}"
    try:
        response = transport.send(LLMRequest(
            source_id=sid,
            source_text=text,
            system_prompt=system,
            user_prompt=user,
        ))
        content = response.content or ""
        decode = getattr(transport, "last_decode", None) or {}
        usage = dict(decode.get("usage") or {})
        status = "ok" if decode.get("status") in (
            None, "ok_message_content"
        ) else "error"
        error = None
        returned_model = decode.get("model")
    except Exception as exc:  # noqa: BLE001 - persist transport failures.
        content, decode, usage = "", {}, {}
        status, error = "error", str(exc)
        returned_model = None

    gate_error = None
    try:
        gate.record_response(usage if usage else None, returned_model)
    except core.SepC3Error as exc:
        gate_error = str(exc)

    completed_at = datetime.now(timezone.utc).isoformat()
    return {
        "suite_id": SUITE_ID,
        "sample_id": sid,
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "execution_index": int(execution_index),
        "arm_order_within_sample": int(arm_order_within_sample),
        "timestamp_utc": started_at,
        "completed_at_utc": completed_at,
        "request_body_sha256": core._sha256_bytes(body_bytes),
        "request_id": (
            (decode.get("request_id") if isinstance(decode, Mapping) else None)
            or request_id
        ),
        "raw_model_output": content,
        "raw_response_content": content,
        "raw_output_sha256": core._sha256_text(content),
        "response_sha256": core._sha256_text(content),
        "bare_json_status": _bare_json_status(content),
        "usage": usage,
        "cost": core._cost_of(usage, budget),
        "request_status": status,
        "error": error,
        "gate_error": gate_error,
        "returned_model": returned_model,
        "model": MODEL_ALIAS,
        "documented_release": MODEL_RELEASE,
        "sampling_parameters": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
            "response_format": None,
        },
        "rendered_prompt_version_hash": prompt.composition_sha256,
        "rendered_prompt_system_sha256": core._sha256_text(system),
        "rendered_prompt_user_sha256": core._sha256_text(user),
        "network_call": 1,
    }


class RunLock:
    """Atomic same-directory lock to prevent duplicate interleaved batches."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.acquired = False

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            existing = ""
            try:
                existing = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            raise RefinementRunError(
                f"run lock already exists: {_relative(self.path)}; "
                f"another batch may be running or the lock is stale. "
                f"Lock content: {existing!r}"
            ) from exc
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "suite_id": SUITE_ID,
                "pid": os.getpid(),
                "started_at_utc": datetime.now(timezone.utc).isoformat(),
                "planned_calls": PLANNED_CALLS,
                "arms": list(ARMS),
            }, ensure_ascii=False) + "\n")
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
        self.acquired = False


def _load_schedule(path: Path | None = None) -> dict[str, Any]:
    schedule = _read_json(Path(path or SCHEDULE_PATH))
    entries = schedule.get("entries")
    if not isinstance(entries, list):
        raise RefinementRunError("schedule entries missing")
    canonical = json.dumps(
        entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    if schedule.get("schedule_sha256") != core._sha256_text(canonical):
        raise RefinementRunError("schedule hash mismatch")
    if len(entries) != PLANNED_CALLS:
        raise RefinementRunError("schedule must contain exactly 600 entries")
    counts: dict[str, int] = {arm: 0 for arm in ARMS}
    for entry in entries:
        arm = str(entry.get("arm"))
        if arm not in counts:
            raise RefinementRunError(f"unknown arm in schedule: {arm!r}")
        counts[arm] += 1
    if any(value != SAMPLES_PER_ARM for value in counts.values()):
        raise RefinementRunError("schedule does not contain 150 entries per arm")
    return schedule


def _load_persisted_state(out_dir: Path) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        run_dir = _arm_dir(arm, out_dir)
        raw_rows = core._read_jsonl(run_dir / "raw_responses.jsonl")
        ledger_rows = core._read_jsonl(run_dir / "calls_ledger.jsonl")
        raw_by_sid: dict[str, dict[str, Any]] = {}
        ledger_by_sid: dict[str, dict[str, Any]] = {}
        for row in raw_rows:
            sid = str(row.get("sample_id") or "")
            if not sid or sid in raw_by_sid:
                raise RefinementRunError(f"duplicate/missing raw sample: {arm}/{sid}")
            raw_by_sid[sid] = row
        for row in ledger_rows:
            sid = str(row.get("sample_id") or "")
            if not sid or sid in ledger_by_sid:
                raise RefinementRunError(f"duplicate/missing ledger sample: {arm}/{sid}")
            ledger_by_sid[sid] = row
        state[arm] = {
            "raw_rows": raw_rows,
            "ledger_rows": ledger_rows,
            "raw_by_sid": raw_by_sid,
            "ledger_by_sid": ledger_by_sid,
        }
    return state


def _check_in_doubt(state: Mapping[str, Mapping[str, Any]]) -> None:
    for arm in ARMS:
        raw = state[arm]["raw_by_sid"]
        ledger = state[arm]["ledger_by_sid"]
        for sid in ledger:
            if sid not in raw:
                raise RefinementRunError(
                    f"in_doubt sample requires manual resolution: {arm}/{sid}"
                )


def _persist_call(arm: str, row: Mapping[str, Any], out_dir: Path) -> None:
    run_dir = _arm_dir(arm, out_dir)
    _append_jsonl(run_dir / "raw_responses.jsonl", row)
    _append_jsonl(run_dir / "calls_ledger.jsonl", {
        "suite_id": SUITE_ID,
        "sample_id": row["sample_id"],
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "execution_index": row["execution_index"],
        "timestamp_utc": row["timestamp_utc"],
        "state": "completed",
        "response_sha256": row["response_sha256"],
    })
    _append_jsonl(out_dir / "calls_ledger.jsonl", {
        "suite_id": SUITE_ID,
        "sample_id": row["sample_id"],
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "execution_index": row["execution_index"],
        "arm_order_within_sample": row["arm_order_within_sample"],
        "timestamp_utc": row["timestamp_utc"],
        "state": "completed",
        "response_sha256": row["response_sha256"],
        "request_status": row["request_status"],
    })


def _strip_json_content(raw: str) -> str:
    content = (raw or "").strip().strip("`").strip()
    if content.lower().startswith("json"):
        content = content[4:].strip()
    return content


def _best_effort_audits(
    raw: str, source_text: str
) -> tuple[Any, Any, Any]:
    from bpc_hybrid.d1_schema_adapter import adapt_relay_record
    from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates

    content = _strip_json_content(raw)
    try:
        payload = json.loads(content)
    except Exception:  # noqa: BLE001 - audit metadata only.
        return None, None, None
    adapt_audit = None
    span_audit = None
    try:
        adapted, adapt_audit = adapt_relay_record(payload, source_text)
        if adapt_audit.get("status") != "failed":
            _, span_audit = canonicalize_record_coordinates(adapted, source_text)
    except Exception:  # noqa: BLE001 - audit metadata only.
        pass
    return payload, adapt_audit, span_audit


def _prediction_with_provenance(
    call: Mapping[str, Any], arm: str, source_text: str
) -> dict[str, Any]:
    parsed = base.parse_same_response(call, arm, source_text)
    prediction = base._prediction_row(parsed, arm)
    payload, adapt_audit, span_audit = _best_effort_audits(
        str(call.get("raw_response_content") or ""), source_text
    )
    prediction.update({
        "suite_id": SUITE_ID,
        "arm": arm,
        "execution_index": call.get("execution_index"),
        "arm_order_within_sample": call.get("arm_order_within_sample"),
        "timestamp_utc": call.get("timestamp_utc"),
        "rendered_prompt_version_hash": call.get(
            "rendered_prompt_version_hash"
        ),
        "model": call.get("model"),
        "documented_release": call.get("documented_release"),
        "sampling_parameters": call.get("sampling_parameters"),
        "raw_model_output": call.get("raw_model_output"),
        "bare_json_status": call.get("bare_json_status"),
        "parsed_output": payload,
        "canonical_output": (
            prediction.get("record") if prediction.get("request_status") == "ok"
            else None
        ),
        "parser_audit": adapt_audit,
        "canonicalizer_audit": span_audit,
    })
    return prediction


def _build_arm_outputs(
    arm: str,
    raw_by_sid: Mapping[str, Mapping[str, Any]],
    input_rows: Sequence[Mapping[str, str]],
    gold_doc: Mapping[str, Any],
    out_dir: Path,
    schedule_sha256: str,
    *,
    actual_call_count: int,
    resumed_completed_count: int,
) -> dict[str, Any]:
    run_dir = _arm_dir(arm, out_dir)
    predictions: list[dict[str, Any]] = []
    input_text = {str(row["sample_id"]): str(row["text"]) for row in input_rows}
    for row in input_rows:
        sid = str(row["sample_id"])
        if sid not in raw_by_sid:
            raise RefinementRunError(f"arm {arm} missing raw sample {sid}")
        predictions.append(
            _prediction_with_provenance(raw_by_sid[sid], arm, input_text[sid])
        )
    failed = [
        row for row in predictions if row.get("request_status") != "ok"
    ]
    evaluation = evaluate_coarse(
        gold_doc,
        attempt_rows(predictions),
        method_id=f"direct_llm_refinement_{arm}",
    )
    evaluation_rel = _relative(run_dir / "evaluation.json")
    evaluation_result = {
        "artifact": evaluation_rel,
        "method_id": evaluation["method_id"],
        "view": evaluation["view"],
        "primary_metric": evaluation["primary_metric"],
        "coarse_five_field_mean_f1": evaluation["coarse_five_field_mean_f1"],
        "coarse_five_field_micro_f1": evaluation["coarse_five_field_micro"]["f1"],
    }
    for prediction in predictions:
        prediction["evaluation_artifact"] = evaluation_rel
        prediction["evaluation_result"] = dict(evaluation_result)

    _write_json(run_dir / "evaluation.json", {
        "suite_id": SUITE_ID,
        "arm": arm,
        "repeat_id": REPEAT_ID,
        "denominator": len(predictions),
        "evaluation": evaluation,
    })
    (run_dir / "canonical_predictions.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in predictions
        ),
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "failed_samples.jsonl").write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in failed
        ),
        encoding="utf-8",
        newline="\n",
    )
    raw_rows = [raw_by_sid[str(row["sample_id"])] for row in input_rows]
    manifest = {
        "schema_version": "sep_c3_targeted_refinement_manifest@1.0.0",
        "suite_id": SUITE_ID,
        "arm": arm,
        "arm_definition": rp.ARM_REPAIRS[arm],
        "repeat_id": REPEAT_ID,
        "prompt_family": "direct_llm_refinement_v1",
        "sample_count": len(input_rows),
        "actual_call_count": actual_call_count,
        "resumed_completed_count": resumed_completed_count,
        "failed_count": len(failed),
        "evaluation_denominator": len(predictions),
        "schedule_sha256": schedule_sha256,
        "source_hashes": dict(rp.render_refinement_prompt(arm).source_hashes),
        "prompt_hashes": {
            "system_sha256": core._sha256_text(
                rp.render_refinement_prompt(arm).system_prompt
            ),
            "user_sha256": core._sha256_text(
                rp.render_refinement_prompt(arm).user_prompt_template
            ),
            "composition_sha256": rp.render_refinement_prompt(
                arm
            ).composition_sha256,
            "generated_prompt_path": _relative(rp.generated_path(arm)),
            "generated_prompt_sha256": core._sha256_file(
                rp.generated_path(arm)
            ),
        },
        "raw_responses_aggregate_sha256": base.aggregate_hash(raw_rows),
        "canonical_predictions_aggregate_sha256": base.aggregate_hash(
            predictions
        ),
        "same_response_binding": all(
            raw.get("response_sha256") == pred.get("response_sha256")
            for raw, pred in zip(raw_rows, predictions)
            if pred.get("request_status") == "ok"
        ),
    }
    _write_json(run_dir / "manifest.json", manifest)
    return {
        "arm": arm,
        "manifest": manifest,
        "evaluation": evaluation,
        "failed": failed,
        "predictions": predictions,
    }


def validate_contracts() -> dict[str, Any]:
    errors: list[str] = []
    prep_result = prep.validate()
    if prep_result.get("status") != "pass":
        errors.extend(prep_result.get("errors") or ["prepare validation failed"])

    schedule = _load_schedule()
    budget = _read_json(BUDGET_PATH)
    if budget.get("planned_calls") != PLANNED_CALLS:
        errors.append("budget planned_calls != 600")
    if budget.get("call_cap") != CALL_CAP:
        errors.append("budget call_cap != 750")
    if budget.get("arms") != list(ARMS):
        errors.append("budget arms mismatch")
    if budget.get("model", {}).get("id") != MODEL_ALIAS:
        errors.append("budget model alias mismatch")
    if budget.get("model", {}).get("documented_release") != MODEL_RELEASE:
        errors.append("budget model release mismatch")
    expected_inference = {
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "retry": 0,
        "stream": False,
        "thinking": {"type": "disabled"},
        "response_format": None,
    }
    if budget.get("inference") != expected_inference:
        errors.append("budget inference settings mismatch")
    if budget.get("schedule_binding", {}).get("sha256") != schedule.get(
        "schedule_sha256"
    ):
        errors.append("budget schedule binding mismatch")
    if budget.get("data_binding", {}).get("input_sha256") != core._sha256_file(
        core.ESTG_INPUT
    ):
        errors.append("input hash mismatch")
    if budget.get("data_binding", {}).get("gold_sha256") != core._sha256_file(
        core.FORMAL_GOLD
    ):
        errors.append("Gold hash mismatch")
    prompt_manifest = _read_json(rp.generated_manifest_path())
    if budget.get("prompt_binding", {}).get(
        "generated_manifest_sha256"
    ) != core._sha256_file(rp.generated_manifest_path()):
        errors.append("prompt manifest hash mismatch")
    for arm in ARMS:
        expected = prompt_manifest["arms"][arm]["composition_sha256"]
        if budget.get("prompt_binding", {}).get(
            "arm_composition_sha256"
        , {}).get(arm) != expected:
            errors.append(f"budget prompt composition mismatch for {arm}")
        try:
            rp.load_generated_prompt(arm)
        except Exception as exc:  # noqa: BLE001 - report loader failure.
            errors.append(f"prompt loader parity failed for {arm}: {exc}")
    return {
        "schema_version": "sep_c3_targeted_refinement_contract_validation@1.0.0",
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def execute(
    project_env: bool = False,
    *,
    transport_factory: Any = None,
    enforce_off_peak: bool = True,
    out_dir: Path | None = None,
    budget_path: Path | None = None,
    schedule_path: Path | None = None,
    result_writer: Any = None,
) -> dict[str, Any]:
    validation = validate_contracts()
    if validation["status"] != "pass":
        raise RefinementRunError(
            "contract validation failed: " + "; ".join(validation["errors"])
        )
    run_out_dir = Path(out_dir or OUT_DIR)
    run_budget_path = Path(budget_path or BUDGET_PATH)
    schedule = _load_schedule(schedule_path)
    entries = schedule["entries"]
    input_rows = core.samples(SAMPLES_PER_ARM)
    sample_by_id = {str(row["sample_id"]): row for row in input_rows}
    if len(sample_by_id) != SAMPLES_PER_ARM:
        raise RefinementRunError("EStG input sample ids are not unique")
    gold_doc = _read_json(core.FORMAL_GOLD)
    budget = core._load_budget(
        run_budget_path, planned_calls=PLANNED_CALLS, call_cap=CALL_CAP
    )

    result: dict[str, Any] = {
        "schema_version": "sep_c3_targeted_refinement_execution@1.0.0",
        "suite_id": SUITE_ID,
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "actual_calls": 0,
        "completed_samples": 0,
        "aborted": False,
        "complete": False,
        "runs": [],
        "arms": list(ARMS),
        "schedule_sha256": schedule["schedule_sha256"],
        "model": {
            "id": MODEL_ALIAS,
            "documented_release": MODEL_RELEASE,
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
    }
    started = time.time()
    with RunLock(run_out_dir / ".run.lock"):
        state = _load_persisted_state(run_out_dir)
        _check_in_doubt(state)
        gate = core.AblationBudgetGate(budget, MODEL_ALIAS)
        core._restore_gate(gate, arms=ARMS, out_dir=run_out_dir)

        real = transport_factory is None
        if real:
            config = core._load_config(project_env)
            core._validate_runtime_config(config, budget)
            transport = RealAPITransport(
                config,
                timeout_seconds=180.0,
                policy=H1RequestPolicy(
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
            for entry in entries:
                arm = str(entry["arm"])
                sid = str(entry["sample_id"])
                if sid in state[arm]["raw_by_sid"]:
                    continue
                if sid in state[arm]["ledger_by_sid"]:
                    raise RefinementRunError(
                        f"in_doubt sample requires manual resolution: {arm}/{sid}"
                    )
                sample = sample_by_id.get(sid)
                if sample is None:
                    raise RefinementRunError(
                        f"schedule references unknown sample: {sid}"
                    )
                call = _call_once(
                    arm,
                    sample,
                    transport,
                    gate,
                    budget,
                    execution_index=int(entry["execution_index"]),
                    arm_order_within_sample=int(
                        entry["arm_order_within_sample"]
                    ),
                    enforce_off_peak=enforce_off_peak,
                )
                _persist_call(arm, call, run_out_dir)
                state[arm]["raw_by_sid"][sid] = call
                state[arm]["raw_rows"].append(call)
                state[arm]["ledger_by_sid"][sid] = {
                    "sample_id": sid,
                    "arm": arm,
                    "state": "completed",
                }
                new_sends[arm] += 1
                if gate.aborted or call.get("gate_error"):
                    raise RefinementRunError(
                        f"arm {arm} stopped after sample {sid}: "
                        f"{call.get('gate_error') or gate.abort_reason}"
                    )
            if any(
                len(state[arm]["raw_by_sid"]) != SAMPLES_PER_ARM
                for arm in ARMS
            ):
                raise RefinementRunError(
                    "schedule completed without 150 persisted samples per arm"
                )
            for arm in ARMS:
                run = _build_arm_outputs(
                    arm,
                    state[arm]["raw_by_sid"],
                    input_rows,
                    gold_doc,
                    run_out_dir,
                    schedule["schedule_sha256"],
                    actual_call_count=new_sends[arm],
                    resumed_completed_count=initial_raw_counts[arm],
                )
                result["runs"].append({
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
                    "modality_label_macro_f1": run["evaluation"][
                        "modality_labels"
                    ].get("macro_f1"),
                })
            result["actual_calls"] = sum(new_sends.values())
            result["completed_samples"] = sum(
                new_sends[arm] + initial_raw_counts[arm] for arm in ARMS
            )
            result["complete"] = (
                result["completed_samples"] == PLANNED_CALLS
                and gate.calls_made == PLANNED_CALLS
            )
        except Exception as exc:  # noqa: BLE001 - persist partial state.
            result["aborted"] = True
            result["abort_reason"] = f"{type(exc).__name__}: {exc}"
            result["actual_calls"] = sum(new_sends.values())
            result["completed_samples"] = sum(
                new_sends[arm] + initial_raw_counts[arm] for arm in ARMS
            )
        result["budget_gate"] = gate.to_dict()
        result["runtime_seconds"] = round(time.time() - started, 3)
        result["raw_counts_per_arm"] = {
            arm: len(state[arm]["raw_by_sid"]) for arm in ARMS
        }
        result["new_sends_per_arm"] = dict(new_sends)

    run_out_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_out_dir / "execution_summary.json", result)
    if result["complete"]:
        if result_writer is not None:
            result_writer(result)
        else:
            _write_json(RESULT_REPORT, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare/check/execute the SEP-C3 targeted-refinement arms."
    )
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--project-env", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.prepare:
        report = prep.prepare(overwrite=args.overwrite)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report.get("status") != "pass":
            return 1
    if args.check:
        validation = validate_contracts()
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        if validation["status"] != "pass":
            return 1
    if args.execute:
        if not args.allow_llm:
            print(json.dumps({
                "status": "refused",
                "reason": "--execute requires --allow-llm and prepared contracts",
            }, ensure_ascii=False, indent=2))
            return 2
        result = execute(project_env=args.project_env)
        print(json.dumps({
            "status": "complete" if result.get("complete") else "aborted",
            "actual_calls": result.get("actual_calls"),
            "abort_reason": result.get("abort_reason"),
            "summary": _relative(OUT_DIR / "execution_summary.json"),
        }, ensure_ascii=False, indent=2))
        return 0 if result.get("complete") else 1
    if not any((args.prepare, args.check, args.execute)):
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""SEP-C3 real-run entry for the modular E/S/J Direct-LLM prompt family.

Arms (combination order E/S/J):
  111 = full modular prompt
  011 = delete E (examples)
  101 = delete S (semantic rules)
  110 = delete J (output organization)

The runner sends exactly the generated modular system/user messages for the
requested arm.  It never appends the historical v6 examples, ``few_shot_block``
placeholders, or old guidance.  The executable path is deliberately separate
from the immutable historical 450-call D1 factorial runner.

ZERO network by default.  Real sends require ``--execute --allow-llm`` and a
recorded budget file.  With ``--project-env`` the existing project ``.env`` is
loaded through ``LLMConfig.from_env(load_project_env=True)``; secrets are never
printed.  Without that flag only process environment variables are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import run_barrientos_ablation_suite_v2 as base  # noqa: E402
from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from bpc_hybrid.llm_client import LLMRequest, RealAPITransport  # noqa: E402
from bpc_hybrid.llm_config import LLMConfig  # noqa: E402
from bpc_hybrid.modular_prompt import render_modular_prompt  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    attempt_rows,
    evaluate_coarse,
)

ARMS = ("111", "011", "101", "110")
SAMPLES_PER_ARM = 150
PLANNED_CALLS = 600
CALL_CAP = 750
MODEL_ALIAS = "deepseek-v4-pro"
MODEL_RELEASE = "DeepSeek-V4-Pro-0813"
MAX_TOKENS = 4096
TEMPERATURE = 0.0
TOP_P = 1.0

ESTG_INPUT = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
FORMAL_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
BUDGET_PATH = ROOT / "configs" / "sep_c3_modular_ablation_budget_v1.json"
OFFLINE_REPORT = (
    ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_offline_check_v1.json"
)
RESULT_REPORT = (
    ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_v1.json"
)
RESULT_MD = ROOT / "outputs" / "reports" / "sep_c3_modular_ablation_v1.md"
OUT_DIR = ROOT / "outputs" / "development" / "sep_c3_modular_ablation_v1"

D_FULL_0813 = (
    ROOT / "outputs" / "development" / "barrientos_ablation_suite_v2"
    / "D-full-0813" / "repeat-01" / "canonical_predictions.jsonl"
)
OLD_V6_HIST = (
    ROOT / "outputs" / "development"
    / "s27_d1_v6_r3_clean_rerun_150_hist56d_v1" / "d1_responses.jsonl"
)

OLD_MARKERS = (
    "Output discipline:",
    "Final self-check before output:",
    "Six-element semantics:",
    "Field-typing precision (D1-R1):",
    "in accordance with Section 11(1)",
    "synthetic_condition_constraint_01",
    "Example 5",
    "{few_shot_block}",
)

COMMON_BOUNDARY_MARKERS = (
    "zero-based start and exclusive end",
    "IDs are unique within the complete record",
    "may reference IDs only from the same clause",
)
MODULE_MARKERS = {
    "E": "Synthetic worked examples",
    "S": "Semantic interpretation rules",
    "J": "Output organization",
}


class SepC3Error(RuntimeError):
    """Fail-closed SEP-C3 runner error."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SepC3Error(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _append_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        fh.flush()
        import os
        os.fsync(fh.fileno())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def samples() -> list[dict[str, str]]:
    doc = _read_json(ESTG_INPUT)
    rows = doc.get("records")
    if not isinstance(rows, list) or len(rows) != SAMPLES_PER_ARM:
        raise SepC3Error("EStG input must contain exactly 150 records")
    out = [
        {
            "sample_id": str(row["sample_id"]),
            "text": str(row["approved_text_en"]),
            "input_text_sha256": str(row.get("input_text_sha256") or ""),
        }
        for row in rows
    ]
    if len({r["sample_id"] for r in out}) != SAMPLES_PER_ARM:
        raise SepC3Error("EStG sample ids must be unique")
    return out


def _prompt(arm: str):
    if arm not in ARMS:
        raise SepC3Error(f"unknown arm: {arm}")
    return render_modular_prompt(arm)


def _generated_prompt_name(arm: str) -> str:
    return f"modular_v1/generated/direct_llm_modular_{arm}_v1"


def _load_generated_prompt(arm: str):
    composed = _prompt(arm)
    loaded = load_prompt(_generated_prompt_name(arm))
    if (loaded.system_prompt != composed.system_prompt
            or loaded.user_prompt_template != composed.user_prompt_template):
        raise SepC3Error(
            f"generated prompt {arm} differs from composer; regenerate before sending")
    return loaded


def render_prompt(arm: str, sample_id: str, source_text: str) -> tuple[str, str]:
    loaded = _load_generated_prompt(arm)
    user = loaded.user_prompt_template.format(
        sample_id=sample_id,
        source_id=sample_id,
        source_text=source_text,
    )
    system = loaded.system_prompt
    if not system or not user:
        raise SepC3Error(f"empty rendered prompt for arm {arm}")
    return system, user


def request_body(arm: str, sample_id: str, source_text: str) -> dict[str, Any]:
    system, user = render_prompt(arm, sample_id, source_text)
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


def _request_bytes(arm: str, sample_id: str, source_text: str) -> bytes:
    return json.dumps(
        request_body(arm, sample_id, source_text),
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def _baseline_attempts(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    if len(rows) != SAMPLES_PER_ARM:
        raise SepC3Error(f"baseline rows must be 150: {path} ({len(rows)})")
    return [
        {
            "sample_id": str(row["sample_id"]),
            "request_status": str(row.get("request_status") or "ok"),
            "record": row.get("record") or {},
        }
        for row in rows
    ]


def _evaluate_baselines(gold_doc: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, path, label in (
        ("old_v6_full_0813_reused", D_FULL_0813,
         "historical old v6 full prompt, same model-release batch"),
        ("old_v6_full_hist_r3_preview", OLD_V6_HIST,
         "historical old v6 full prompt snapshot; context only"),
    ):
        if not path.is_file():
            out[key] = {"status": "missing", "path": str(path.relative_to(ROOT))}
            continue
        evaluation = evaluate_coarse(
            gold_doc,
            _baseline_attempts(path),
            method_id=key,
        )
        out[key] = {
            "status": "evaluated_zero_api",
            "path": str(path.relative_to(ROOT)),
            "sha256": _sha256_file(path),
            "label": label,
            "prompt_sha256": (
                "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
            ),
            "evaluation": evaluation,
        }
    return out


def offline_check() -> dict[str, Any]:
    gold_doc = _read_json(FORMAL_GOLD)
    prompts = {arm: _prompt(arm) for arm in ARMS}
    checks: dict[str, bool] = {}
    arm_rows: dict[str, Any] = {}
    total_input_tokens = 0
    for arm in ARMS:
        prompt = prompts[arm]
        errors: list[str] = []
        text = prompt.system_prompt + "\n" + prompt.user_prompt_template
        for marker in COMMON_BOUNDARY_MARKERS:
            if marker not in prompt.system_prompt:
                errors.append(f"missing common boundary marker: {marker}")
        for module, marker in MODULE_MARKERS.items():
            enabled = prompt.flags[module]
            present = marker in (prompt.user_prompt_template
                                 if module == "E" else prompt.system_prompt)
            if enabled and not present:
                errors.append(f"enabled module {module} marker missing")
            if not enabled and present:
                errors.append(f"disabled module {module} marker present")
        for marker in OLD_MARKERS:
            if marker in text:
                errors.append(f"old prompt marker leaked: {marker}")
        if prompt.user_prompt_template.strip() == "":
            errors.append("empty user prompt template")
        if "source_text:" not in prompt.user_prompt_template:
            errors.append("source_text envelope missing")
        rendered = prompt.render_user("estg_offline_check", "A must act.")
        if "A must act." not in rendered:
            errors.append("source_text render failed")

        per_sample_tokens = []
        for row in samples():
            body_bytes = _request_bytes(arm, row["sample_id"], row["text"])
            per_sample_tokens.append(math.ceil(len(body_bytes) / 3))
        arm_input = sum(per_sample_tokens)
        total_input_tokens += arm_input
        generated = _load_generated_prompt(arm)
        arm_rows[arm] = {
            "flags": dict(prompt.flags),
            "generated_prompt_path": str(generated.path.relative_to(ROOT)).replace("\\", "/"),
            "generated_prompt_sha256": generated.sha256,
            "loader_matches_composer": (
                generated.system_prompt == prompt.system_prompt
                and generated.user_prompt_template == prompt.user_prompt_template
            ),
            "system_chars": len(prompt.system_prompt),
            "user_chars": len(prompt.user_prompt_template),
            "system_sha256": _sha256_text(prompt.system_prompt),
            "user_sha256": _sha256_text(prompt.user_prompt_template),
            "composition_sha256": prompt.composition_sha256,
            "estimated_input_tokens_150": arm_input,
            "errors": errors,
        }
        checks[f"arm_{arm}_clean"] = not errors

    baselines = _evaluate_baselines(gold_doc)
    checks["six_hundred_call_plan"] = PLANNED_CALLS == 600
    checks["call_cap_750_recorded"] = CALL_CAP == 750
    checks["baseline_old_full_0813_available"] = (
        baselines["old_v6_full_0813_reused"]["status"] == "evaluated_zero_api"
    )
    report = {
        "schema_version": "sep_c3_modular_ablation_offline_check@1.0.0",
        "status": "pass" if all(checks.values()) else "fail",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "network_calls": 0,
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
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
        "input_path": str(ESTG_INPUT.relative_to(ROOT)),
        "input_sha256": _sha256_file(ESTG_INPUT),
        "gold_path": str(FORMAL_GOLD.relative_to(ROOT)),
        "gold_sha256": _sha256_file(FORMAL_GOLD),
        "arms": arm_rows,
        "estimated_total_input_tokens": total_input_tokens,
        "baselines": baselines,
        "checks": checks,
        "notes": [
            "Offline request check only; no network/API call was made.",
            "Request bodies are rendered from prompts/sun_compat/modular_v1/generated.",
            "The old-v6 full 0813 baseline is reused from the immutable 450-call factorial batch.",
            "Primary metric is coarse_five_field_mean_f1; modality labels are separate.",
        ],
    }
    _write_json(OFFLINE_REPORT, report)
    return report


class AblationBudgetGate:
    """Call/token/cost gate for the 600-call E/S/J ablation.

    A failed transport call still consumes one call slot and is persisted as a
    failure.  Missing usage is recorded (never silently treated as a successful
    zero-cost call), but does not abort the remaining 600-call batch.
    """

    def __init__(self, budget: Mapping[str, Any], model_id: str) -> None:
        self.call_cap = int(budget["call_cap"])
        self.input_token_cap = float(budget["input_token_cap"])
        self.output_token_cap = float(budget["output_token_cap"])
        self.usd_cost_cap = float(budget["usd_cost_cap"])
        price = budget["price_snapshot"]
        self.input_price = float(price["input_cache_miss_per_million"])
        self.output_price = float(price["output_per_million"])
        self.model_id = model_id
        self.calls_made = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.missing_usage_calls = 0
        self.aborted = False
        self.abort_reason: str | None = None

    def abort(self, reason: str) -> None:
        self.aborted = True
        self.abort_reason = reason
        raise SepC3Error(reason)

    def check_before_send(self, projected_input_tokens: int,
                          projected_max_output_tokens: int) -> None:
        if self.aborted:
            self.abort(f"budget gate already aborted: {self.abort_reason}")
        if self.calls_made + 1 > self.call_cap:
            self.abort(
                f"next send would exceed call cap "
                f"({self.calls_made} made, cap {self.call_cap})"
            )
        proj_input = self.input_tokens + projected_input_tokens
        proj_output = self.output_tokens + projected_max_output_tokens
        proj_cost = self.cost_usd + (
            projected_input_tokens * self.input_price
            + projected_max_output_tokens * self.output_price
        ) / 1e6
        if proj_input > self.input_token_cap:
            self.abort(f"next send would exceed input token cap ({proj_input:.0f})")
        if proj_output > self.output_token_cap:
            self.abort(
                f"next send would exceed output token cap ({proj_output:.0f})")
        if proj_cost > self.usd_cost_cap:
            self.abort(f"next send would exceed USD cap ({proj_cost:.4f})")

    def record_response(self, usage: Mapping[str, Any] | None,
                        returned_model: str | None) -> None:
        self.calls_made += 1
        if returned_model and self.model_id and returned_model != self.model_id:
            self.abort(
                f"returned model {returned_model!r} != contract model "
                f"{self.model_id!r}")
        if not usage or not isinstance(usage, Mapping):
            self.missing_usage_calls += 1
        else:
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")
            if isinstance(prompt_tokens, (int, float)) and isinstance(
                    completion_tokens, (int, float)):
                self.input_tokens += int(prompt_tokens)
                self.output_tokens += int(completion_tokens)
                self.cost_usd += (
                    float(prompt_tokens) * self.input_price
                    + float(completion_tokens) * self.output_price
                ) / 1e6
            else:
                self.missing_usage_calls += 1
        if self.calls_made > self.call_cap:
            self.abort(f"call cap exceeded ({self.calls_made} > {self.call_cap})")
        if self.input_tokens > self.input_token_cap:
            self.abort(f"input token cap exceeded ({self.input_tokens})")
        if self.output_tokens > self.output_token_cap:
            self.abort(f"output token cap exceeded ({self.output_tokens})")
        if self.cost_usd > self.usd_cost_cap:
            self.abort(f"USD cap exceeded ({self.cost_usd:.4f})")

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_made": self.calls_made,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 8),
            "missing_usage_calls": self.missing_usage_calls,
            "call_cap": self.call_cap,
            "input_token_cap": self.input_token_cap,
            "output_token_cap": self.output_token_cap,
            "usd_cost_cap": self.usd_cost_cap,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }


def _load_budget() -> dict[str, Any]:
    budget = _read_json(BUDGET_PATH)
    if int(budget.get("planned_calls", 0)) != PLANNED_CALLS:
        raise SepC3Error("budget planned_calls must be 600")
    if int(budget.get("call_cap", 0)) != CALL_CAP:
        raise SepC3Error("budget call_cap must be 750")
    for key in ("input_token_cap", "output_token_cap", "usd_cost_cap"):
        if not isinstance(budget.get(key), (int, float)) or budget[key] <= 0:
            raise SepC3Error(f"invalid budget cap: {key}")
    if not isinstance(budget.get("price_snapshot"), Mapping):
        raise SepC3Error("budget price_snapshot missing")
    return budget


def _model_contract(budget: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model": {
            "id": MODEL_ALIAS,
            "provider": "openai_compatible",
        },
        "sampling": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "retry": 0,
            "stream": False,
            "thinking": {"type": "disabled"},
        },
        "budget": {
            "planned_calls": int(budget["call_cap"]),
            "input_token_cap": float(budget["input_token_cap"]),
            "output_token_cap": float(budget["output_token_cap"]),
            "usd_cost_cap": float(budget["usd_cost_cap"]),
            "price_snapshot": dict(budget["price_snapshot"]),
        },
    }


def _load_config(project_env: bool) -> LLMConfig:
    config = LLMConfig.from_env(
        project_root=ROOT, load_project_env=bool(project_env))
    return config


def _validate_runtime_config(config: LLMConfig, budget: Mapping[str, Any]) -> None:
    if not config.enabled or config.provider != "openai_compatible":
        raise SepC3Error("real provider is not enabled")
    if config.model != MODEL_ALIAS:
        raise SepC3Error(f"runtime model {config.model!r} != {MODEL_ALIAS!r}")
    if config.temperature != TEMPERATURE:
        raise SepC3Error("runtime temperature != 0.0")
    if config.top_p != TOP_P:
        raise SepC3Error("runtime top_p != 1.0")
    if int(config.max_tokens) != MAX_TOKENS:
        raise SepC3Error("runtime max_tokens != 4096")
    if not config.api_key:
        raise SepC3Error("runtime API key missing")


def _cost_of(usage: Mapping[str, Any] | None,
             budget: Mapping[str, Any]) -> float | str:
    if not usage:
        return "unknown"
    price = budget["price_snapshot"]
    try:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
    except (TypeError, ValueError):
        return "unknown"
    return round(
        prompt_tokens * float(price["input_cache_miss_per_million"]) / 1e6
        + completion_tokens * float(price["output_per_million"]) / 1e6,
        8,
    )


def _restore_gate(gate: AblationBudgetGate) -> None:
    for arm in ARMS:
        run_dir = OUT_DIR / arm / "repeat-01"
        for row in _read_jsonl(run_dir / "raw_responses.jsonl"):
            usage = row.get("usage") if isinstance(row, Mapping) else None
            returned_model = (
                row.get("returned_model") if isinstance(row, Mapping) else None
            )
            try:
                gate.record_response(usage if isinstance(usage, Mapping) else None,
                                     returned_model)
            except SepC3Error:
                raise
    if gate.aborted:
        raise SepC3Error(f"restored budget gate aborted: {gate.abort_reason}")


def _call_once(arm: str, sample: Mapping[str, str], transport: Any,
               gate: AblationBudgetGate, budget: Mapping[str, Any]) -> dict[str, Any]:
    sid = sample["sample_id"]
    text = sample["text"]
    system, user = render_prompt(arm, sid, text)
    body = request_body(arm, sid, text)
    body_bytes = json.dumps(
        body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    projected = math.ceil(len(body_bytes) / 3)
    gate.check_before_send(projected, MAX_TOKENS)
    base._require_beijing_off_peak()

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
            None, "ok_message_content") else "error"
        error = None
        returned_model = decode.get("model")
    except Exception as exc:  # noqa: BLE001 - persist transport failures.
        content, decode, usage = "", {}, {}
        status, error = "error", str(exc)
        returned_model = None

    gate_error = None
    try:
        gate.record_response(usage if usage else None, returned_model)
    except SepC3Error as exc:
        gate_error = str(exc)

    return {
        "sample_id": sid,
        "arm": arm,
        "repeat_id": "repeat-01",
        "request_body_sha256": _sha256_bytes(body_bytes),
        "request_id": (decode.get("request_id") if isinstance(decode, Mapping)
                       else None) or request_id,
        "raw_response_content": content,
        "response_sha256": _sha256_bytes(content.encode("utf-8")),
        "usage": usage,
        "cost": _cost_of(usage, budget),
        "request_status": status,
        "error": error,
        "gate_error": gate_error,
        "returned_model": returned_model,
        "network_call": 1,
    }


def _run_arm(arm: str, rows: Sequence[Mapping[str, str]], transport: Any,
             gate: AblationBudgetGate, budget: Mapping[str, Any],
             gold_doc: dict[str, Any]) -> dict[str, Any]:
    run_dir = OUT_DIR / arm / "repeat-01"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw_responses.jsonl"
    ledger_path = run_dir / "calls_ledger.jsonl"
    persisted_raw = {r["sample_id"]: r for r in _read_jsonl(raw_path)}
    persisted_ledger = {r["sample_id"]: r for r in _read_jsonl(ledger_path)}

    raw_rows: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    new_sends = 0
    resumed = 0
    for sample in rows:
        sid = sample["sample_id"]
        if sid in persisted_raw:
            call = persisted_raw[sid]
            resumed += 1
        elif sid in persisted_ledger:
            raise SepC3Error(f"in_doubt sample requires manual resolution: {arm}/{sid}")
        else:
            call = _call_once(arm, sample, transport, gate, budget)
            new_sends += 1
            _append_jsonl(raw_path, call)
            _append_jsonl(ledger_path, {
                "sample_id": sid,
                "arm": arm,
                "repeat_id": "repeat-01",
                "state": "completed",
                "response_sha256": call["response_sha256"],
            })
            if gate.aborted or call.get("gate_error"):
                raise SepC3Error(
                    f"arm {arm} stopped after sample {sid}: "
                    f"{call.get('gate_error') or gate.abort_reason}")
        raw_rows.append(call)
        parsed = base.parse_same_response(call, arm, sample["text"])
        prediction = base._prediction_row(parsed, arm)
        predictions.append(prediction)
        if prediction["request_status"] != "ok":
            failed.append(prediction)

    evaluation = evaluate_coarse(
        gold_doc, attempt_rows(predictions),
        method_id=f"direct_llm_modular_{arm}")
    (run_dir / "canonical_predictions.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
        encoding="utf-8",
        newline="\n",
    )
    (run_dir / "failed_samples.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in failed),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(run_dir / "evaluation.json", {
        "arm": arm,
        "repeat_id": "repeat-01",
        "denominator": len(predictions),
        "evaluation": evaluation,
    })
    manifest = {
        "arm": arm,
        "repeat_id": "repeat-01",
        "prompt_family": "direct_llm_modular_v1",
        "prompt_combination_ESJ": arm,
        "sample_count": len(rows),
        "actual_call_count": new_sends,
        "resumed_completed_count": resumed,
        "failed_count": len(failed),
        "evaluation_denominator": len(predictions),
        "raw_responses_aggregate_sha256": base.aggregate_hash(raw_rows),
        "canonical_predictions_aggregate_sha256": base.aggregate_hash(predictions),
        "same_response_binding": all(
            raw.get("response_sha256") == pred.get("response_sha256")
            for raw, pred in zip(raw_rows, predictions)
            if pred["request_status"] == "ok"
        ),
        "prompt_hashes": {
            "system_sha256": _sha256_text(_prompt(arm).system_prompt),
            "user_sha256": _sha256_text(_prompt(arm).user_prompt_template),
            "composition_sha256": _prompt(arm).composition_sha256,
            "generated_prompt_path": str(
                _load_generated_prompt(arm).path.relative_to(ROOT)
            ).replace("\\", "/"),
            "generated_prompt_sha256": _load_generated_prompt(arm).sha256,
        },
    }
    _write_json(run_dir / "manifest.json", manifest)
    return {
        "manifest": manifest,
        "evaluation": evaluation,
        "failed": failed,
    }


def execute(project_env: bool = False, *, transport_factory: Any = None) -> dict[str, Any]:
    budget = _load_budget()
    gold_doc = _read_json(FORMAL_GOLD)
    gate = AblationBudgetGate(budget, MODEL_ALIAS)
    _restore_gate(gate)

    real = transport_factory is None
    if real:
        config = _load_config(project_env)
        _validate_runtime_config(config, budget)
        transport_factory = lambda: RealAPITransport(
            config,
            timeout_seconds=180.0,
            policy=H1RequestPolicy(
                stream=False,
                thinking={"type": "disabled"},
                response_format=None,
            ),
        )
    else:
        config = None

    result: dict[str, Any] = {
        "schema_version": "sep_c3_modular_ablation_execution@1.0.0",
        "planned_calls": PLANNED_CALLS,
        "call_cap": CALL_CAP,
        "actual_calls": 0,
        "completed_samples": 0,
        "aborted": False,
        "runs": [],
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
    try:
        for arm in ARMS:
            run = _run_arm(
                arm,
                samples(),
                transport_factory(),
                gate,
                budget,
                gold_doc,
            )
            manifest = run["manifest"]
            result["actual_calls"] += manifest["actual_call_count"]
            result["completed_samples"] += (
                manifest["actual_call_count"] + manifest["resumed_completed_count"])
            result["runs"].append({
                "arm": arm,
                "actual_call_count": manifest["actual_call_count"],
                "resumed_completed_count": manifest["resumed_completed_count"],
                "failed_count": manifest["failed_count"],
                "primary_metric": run["evaluation"]["primary_metric"],
                "coarse_five_field_mean_f1": (
                    run["evaluation"]["coarse_five_field_mean_f1"]),
                "coarse_five_field_micro_f1": (
                    run["evaluation"]["coarse_five_field_micro"]["f1"]),
                "modality_label_macro_f1": (
                    run["evaluation"]["modality_labels"].get("macro_f1")),
            })
    except Exception as exc:  # noqa: BLE001 - partial runs stay visible.
        result["aborted"] = True
        result["abort_reason"] = f"{type(exc).__name__}: {exc}"
    result["budget_gate"] = gate.to_dict()
    result["runtime_seconds"] = round(time.time() - started, 3)
    result["complete"] = (
        not result["aborted"]
        and result["completed_samples"] == PLANNED_CALLS
        and gate.calls_made == PLANNED_CALLS
        and len(result["runs"]) == len(ARMS)
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUT_DIR / "execution_summary.json", result)
    if result["complete"]:
        _write_result_report(result)
    return result


def _build_comparison(result: Mapping[str, Any]) -> dict[str, Any]:
    gold_doc = _read_json(FORMAL_GOLD)
    baseline = _evaluate_baselines(gold_doc)
    metrics: dict[str, Any] = {}
    for run in result.get("runs", []):
        metrics[run["arm"]] = {
            "source": f"outputs/development/sep_c3_modular_ablation_v1/{run['arm']}/repeat-01",
            "coarse_five_field_mean_f1": run.get("coarse_five_field_mean_f1"),
            "coarse_five_field_micro_f1": run.get("coarse_five_field_micro_f1"),
            "modality_label_macro_f1": run.get("modality_label_macro_f1"),
            "failed_count": run.get("failed_count"),
        }
    full = metrics.get("111", {}).get("coarse_five_field_mean_f1")
    old = (baseline.get("old_v6_full_0813_reused", {})
           .get("evaluation", {}).get("coarse_five_field_mean_f1"))
    deltas = {}
    for arm in ARMS:
        value = metrics.get(arm, {}).get("coarse_five_field_mean_f1")
        if value is None:
            continue
        row = {"vs_old_v6_full_0813": None, "vs_full_111": None}
        if old is not None:
            row["vs_old_v6_full_0813"] = round(value - old, 6)
        if full is not None:
            row["vs_full_111"] = round(value - full, 6)
        deltas[arm] = row
    return {
        "primary_metric": "coarse_five_field_mean_f1",
        "primary_metric_definition": (
            "arithmetic mean of the coarse sentence-level F1 across "
            "actor/action/condition/constraint/exception; modality labels "
            "are reported separately"
        ),
        "acceptance_thresholds": {
            "full_vs_old_max_drop": 0.01,
            "each_deletion_min_full_gap": 0.01,
            "note": "engineering acceptance criteria; not statistical significance",
        },
        "metrics": metrics,
        "old_baselines": baseline,
        "deltas": deltas,
        "acceptance": _acceptance(baseline, metrics),
    }


def _acceptance(baseline: Mapping[str, Any],
                metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    old = (baseline.get("old_v6_full_0813_reused", {})
           .get("evaluation", {}).get("coarse_five_field_mean_f1"))
    full = metrics.get("111", {}).get("coarse_five_field_mean_f1")
    checks: dict[str, Any] = {}
    if old is None or full is None:
        return {"status": "indeterminate", "checks": checks}
    checks["full_not_worse_than_old_by_more_than_0.01"] = (old - full) <= 0.01
    for arm in ("011", "101", "110"):
        value = metrics.get(arm, {}).get("coarse_five_field_mean_f1")
        checks[f"full_minus_{arm}_at_least_0.01"] = (
            value is not None and (full - value) >= 0.01
        )
    checks["full_not_better_than_old?"] = None  # not an acceptance requirement
    passed = all(v is True for k, v in checks.items() if v is not None)
    return {
        "status": "pass" if passed else "fail",
        "checks": checks,
        "interpretation": (
            "all three module deletions must have at least 0.01 lower "
            "coarse_five_field_mean_f1 than full 111; the full prompt must "
            "not be more than 0.01 below the comparable old v6 full baseline"
        ),
    }


def _write_result_report(result: Mapping[str, Any]) -> None:
    comparison = _build_comparison(result)
    report = {
        "schema_version": "sep_c3_modular_ablation_report@1.0.0",
        "run_status": "complete_real_execution"
        if result.get("complete") else "partial",
        "execution": result,
        "comparison": comparison,
        "notes": [
            "Old v6 full baseline is the reused D-full-0813 arm from the same model-release batch.",
            "All 150 samples per arm remain in the evaluation denominator.",
            "Modality labels and span F1 are reported separately.",
        ],
    }
    _write_json(RESULT_REPORT, report)
    lines = [
        "# SEP-C3 modular E/S/J ablation",
        "",
        f"- status: {report['run_status']}",
        f"- planned calls: {PLANNED_CALLS}",
        f"- actual calls: {result.get('actual_calls')}",
        f"- primary metric: `coarse_five_field_mean_f1`",
        f"- old v6 full (reused D-full-0813): "
        f"{comparison['old_baselines']['old_v6_full_0813_reused'].get('evaluation', {}).get('coarse_five_field_mean_f1')}",
        "",
        "| arm | mean F1 | micro F1 | modality macro-F1 | failed | delta vs old | delta vs 111 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        metric = comparison["metrics"].get(arm, {})
        delta = comparison["deltas"].get(arm, {})
        lines.append(
            f"| {arm} | {metric.get('coarse_five_field_mean_f1')} | "
            f"{metric.get('coarse_five_field_micro_f1')} | "
            f"{metric.get('modality_label_macro_f1')} | "
            f"{metric.get('failed_count')} | "
            f"{delta.get('vs_old_v6_full_0813')} | "
            f"{delta.get('vs_full_111')} |"
        )
    lines += [
        "",
        f"Acceptance: **{comparison['acceptance']['status']}**",
        "",
        "```json",
        json.dumps(comparison["acceptance"], ensure_ascii=False, indent=2),
        "```",
    ]
    RESULT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline-check", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument(
        "--project-env", action="store_true",
        help="load project .env through the existing LLMConfig fallback; "
             "secrets are never printed",
    )
    args = parser.parse_args()
    if args.offline_check:
        report = offline_check()
        print(json.dumps({
            "status": report["status"],
            "planned_calls": report["planned_calls"],
            "estimated_total_input_tokens": report["estimated_total_input_tokens"],
            "checks": report["checks"],
        }, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 1
    if not args.allow_llm:
        print("refusing real execution without --allow-llm", file=sys.stderr)
        return 2
    try:
        result = execute(project_env=args.project_env)
    except Exception as exc:  # noqa: BLE001
        print(f"EXECUTION ABORTED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    if not result.get("complete"):
        print(f"INCOMPLETE: {result.get('abort_reason') or 'partial run'}",
              file=sys.stderr)
        return 3
    print(f"SEP-C3 modular ablation complete: {result['actual_calls']}/600")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

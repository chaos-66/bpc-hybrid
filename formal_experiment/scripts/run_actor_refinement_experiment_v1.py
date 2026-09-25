# -*- coding: utf-8 -*-
"""Execute the four-arm D1 Actor-refinement development screening experiment.

The experiment is intentionally one-factor-per-arm and pre-registered before
any model output is examined:

* B0: fresh unchanged baseline
* R : actor noun-phrase role eligibility only
* P : unresolved actor pronoun policy only
* C : explicit condition-to-actor projection only

The runner persists every raw request/response and derives parsed, adapted,
repair_v1-canonicalized, validated, and canonical prediction artifacts without
using Gold.  Gold is only read by the offline evaluator in a separate step.
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
from typing import Any, Callable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _path in (SRC, SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import run_barrientos_ablation_suite_v2 as base  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402

EXPERIMENT_ID = "d1_actor_refinement_v1"
PROMPT_DIR_NAME = "actor_refinement_v1"
PROMPT_DIR = ROOT / "prompts" / "sun_compat" / PROMPT_DIR_NAME
PROMPT_MANIFEST = PROMPT_DIR / "manifest.json"
DIFF_MANIFEST = PROMPT_DIR / "prompt_diff_manifest.json"
OUT_DIR = ROOT / "outputs" / "development" / EXPERIMENT_ID
EXPERIMENT_MANIFEST = OUT_DIR / "experiment_manifest.json"
EXECUTION_SUMMARY = OUT_DIR / "execution_summary.json"
SMOKE_REPORT = OUT_DIR / "smoke_report.json"
INPUT_PATH = ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
REPORT_JSON = ROOT / "outputs" / "reports" / f"{EXPERIMENT_ID}.json"
REPORT_MD = ROOT / "outputs" / "reports" / f"{EXPERIMENT_ID}.md"

MODEL_ID = "deepseek-v4-pro"
MODEL_PROVIDER = "openai_compatible"
MODEL_RELEASE = "DeepSeek-V4-Pro-0813"
TEMPERATURE = 0.0
TOP_P = 1.0
MAX_TOKENS = 4096
RETRY = 0
STREAM = False
THINKING = {"type": "disabled"}
RESPONSE_FORMAT = None
CANONICALIZER_POLICY = "repair_v1"
EVALUATOR_ID = "sun_literal_overlap_evaluation@2.0.0"
PLANNED_CALLS = 600
SAMPLES_PER_ARM = 150

ARM_ORDER = ("B0", "R", "P", "C")
ARMS: dict[str, dict[str, str]] = {
    "B0": {
        "name": f"{PROMPT_DIR_NAME}/direct_llm_actor_baseline_v1",
        "file": "direct_llm_actor_baseline_v1.md",
        "conceptual_factor": "fresh_unchanged_baseline",
    },
    "R": {
        "name": f"{PROMPT_DIR_NAME}/direct_llm_actor_role_eligibility_v1",
        "file": "direct_llm_actor_role_eligibility_v1.md",
        "conceptual_factor": "actor_role_eligibility_only",
    },
    "P": {
        "name": f"{PROMPT_DIR_NAME}/direct_llm_actor_pronoun_policy_v1",
        "file": "direct_llm_actor_pronoun_policy_v1.md",
        "conceptual_factor": "unresolved_pronoun_policy_only",
    },
    "C": {
        "name": f"{PROMPT_DIR_NAME}/direct_llm_actor_condition_projection_v1",
        "file": "direct_llm_actor_condition_projection_v1.md",
        "conceptual_factor": "condition_actor_projection_only",
    },
}


class ActorRefinementError(RuntimeError):
    """Fail-closed error for the frozen Actor-refinement experiment."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(
        microsecond=0).isoformat().replace("+00:00", "Z")


def prompt_path(arm: str) -> Path:
    if arm not in ARMS:
        raise ActorRefinementError(f"unknown arm: {arm}")
    return PROMPT_DIR / ARMS[arm]["file"]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ActorRefinementError(f"expected JSON object: {path}")
    return value


def load_samples() -> list[dict[str, str]]:
    doc = _read_json(INPUT_PATH)
    rows = doc.get("records")
    if not isinstance(rows, list) or len(rows) != SAMPLES_PER_ARM:
        raise ActorRefinementError(
            f"input must contain exactly {SAMPLES_PER_ARM} records"
        )
    result = [
        {
            "sample_id": str(row["sample_id"]),
            "text": str(row["approved_text_en"]),
        }
        for row in rows
    ]
    ids = [row["sample_id"] for row in result]
    if len(set(ids)) != SAMPLES_PER_ARM:
        raise ActorRefinementError("sample ids must be unique")
    if ids[0] != "estg_000002":
        raise ActorRefinementError("unexpected first sample id")
    return result


def sample_ids_sha256(samples: Sequence[Mapping[str, str]] | None = None) -> str:
    rows = list(samples or load_samples())
    payload = json.dumps(
        [row["sample_id"] for row in rows], ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(payload)


def output_hashes(paths: Sequence[Path]) -> dict[str, str | None]:
    return {
        str(path.relative_to(ROOT)): (_sha256_file(path) if path.is_file() else None)
        for path in paths
    }


def _file_rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def build_experiment_manifest() -> dict[str, Any]:
    sample_rows = load_samples()
    arm_entries: dict[str, Any] = {}
    for arm in ARM_ORDER:
        path = prompt_path(arm)
        if not path.is_file():
            raise ActorRefinementError(f"missing prompt variant: {path}")
        arm_entries[arm] = {
            "path": _file_rel(path),
            "sha256": _sha256_file(path),
            "conceptual_factor": ARMS[arm]["conceptual_factor"],
        }
    manifest = {
        "schema_version": "d1_actor_refinement_experiment@1.0.0",
        "experiment_id": EXPERIMENT_ID,
        "created_at_utc": _utc_now(),
        "status": "frozen_pre_execution",
        "scope": "development_screening_only",
        "design": {
            "arms": list(ARM_ORDER),
            "planned_calls": PLANNED_CALLS,
            "samples_per_arm": SAMPLES_PER_ARM,
            "repeat_count": 0,
            "fresh_baseline": True,
            "one_factor_per_arm": True,
            "combined_arm_allowed": False,
        },
        "prompts": arm_entries,
        "model": {
            "id": MODEL_ID,
            "provider": MODEL_PROVIDER,
            "documented_release": MODEL_RELEASE,
        },
        "sampling": {
            "temperature": TEMPERATURE,
            "top_p": TOP_P,
            "max_tokens": MAX_TOKENS,
            "retry": RETRY,
            "stream": STREAM,
            "thinking": THINKING,
            "response_format": RESPONSE_FORMAT,
        },
        "dataset": {
            "path": _file_rel(INPUT_PATH),
            "sha256": _sha256_file(INPUT_PATH),
            "sample_count": len(sample_rows),
            "sample_ids_sha256": sample_ids_sha256(sample_rows),
            "first_sample_id": sample_rows[0]["sample_id"],
            "ordering": "frozen_input_array_order",
        },
        "canonicalizer": {
            "module": "bpc_hybrid.d1_span_canonicalizer",
            "policy": CANONICALIZER_POLICY,
            "policy_explicit_pin": True,
            "cost_metric": "sum_absolute_endpoint_distance",
        },
        "evaluator": {
            "id": EVALUATOR_ID,
            "same_for_all_arms": True,
        },
        "gold_isolation": {
            "used_during_prompt_construction": False,
            "used_during_api_execution": False,
            "evaluation_after_predictions_locked": True,
        },
        "provenance_requirements": [
            "sample_id",
            "arm",
            "request_body_sha256",
            "prompt_sha256",
            "raw_response_content",
            "parsed_response",
            "adapter_output",
            "canonicalizer_output",
            "validation",
            "canonical_final_record",
            "failure_reason",
        ],
    }
    return manifest


def write_frozen_experiment_manifest() -> dict[str, Any]:
    manifest = build_experiment_manifest()
    manifest["runner"] = {
        "path": _file_rel(Path(__file__).resolve()),
        "sha256": _sha256_file(Path(__file__).resolve()),
    }
    EXPERIMENT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return manifest


def validate_experiment_manifest() -> dict[str, Any]:
    if not EXPERIMENT_MANIFEST.is_file():
        raise ActorRefinementError(
            f"experiment manifest missing: {EXPERIMENT_MANIFEST}"
        )
    manifest = _read_json(EXPERIMENT_MANIFEST)
    design = manifest.get("design") or {}
    if design.get("arms") != list(ARM_ORDER):
        raise ActorRefinementError("arm order in manifest is not frozen")
    if design.get("planned_calls") != PLANNED_CALLS:
        raise ActorRefinementError("planned call count is not frozen 600")
    if design.get("samples_per_arm") != SAMPLES_PER_ARM:
        raise ActorRefinementError("sample count per arm is not frozen 150")
    if design.get("repeat_count") != 0:
        raise ActorRefinementError("repeat_count must be zero")
    if design.get("combined_arm_allowed") is not False:
        raise ActorRefinementError("combined arm must be forbidden")
    prompts = manifest.get("prompts") or {}
    for arm in ARM_ORDER:
        expected = prompts.get(arm) or {}
        path = prompt_path(arm)
        if not path.is_file():
            raise ActorRefinementError(f"prompt variant missing: {path}")
        if expected.get("sha256") != _sha256_file(path):
            raise ActorRefinementError(f"prompt hash drift for arm {arm}")
    canon = manifest.get("canonicalizer") or {}
    if canon.get("policy") != CANONICALIZER_POLICY:
        raise ActorRefinementError("repair_v1 is not explicitly pinned")
    if canon.get("policy_explicit_pin") is not True:
        raise ActorRefinementError("canonicalizer explicit-pin flag missing")
    evaluator = manifest.get("evaluator") or {}
    if evaluator.get("id") != EVALUATOR_ID:
        raise ActorRefinementError("evaluator id drift")
    if evaluator.get("same_for_all_arms") is not True:
        raise ActorRefinementError("evaluator is not marked same-for-all-arms")
    dataset = manifest.get("dataset") or {}
    if dataset.get("sha256") and dataset["sha256"] != _sha256_file(INPUT_PATH):
        raise ActorRefinementError("dataset hash drift")
    if dataset.get("sample_count") != SAMPLES_PER_ARM:
        raise ActorRefinementError("dataset sample count drift")
    if dataset.get("sample_ids_sha256") and dataset[
            "sample_ids_sha256"] != sample_ids_sha256():
        raise ActorRefinementError("sample id ordering drift")
    return manifest


# ---------------------------------------------------------------------------
# Rendering and one API call
# ---------------------------------------------------------------------------

_PROMPT_CACHE: dict[str, Any] = {}


def _loaded_prompt(arm: str):
    if arm not in _PROMPT_CACHE:
        _PROMPT_CACHE[arm] = load_prompt(ARMS[arm]["name"])
    return _PROMPT_CACHE[arm]


def _few_shot_block(prompt: Any) -> str:
    raw = getattr(prompt, "raw_text", "")
    start = raw.find("## Examples")
    end = raw.find("## Notes", start)
    if start < 0 or end < 0:
        return ""
    return raw[start:end].strip()


def render_prompt(arm: str, sample_id: str, source_text: str) -> tuple[str, str]:
    prompt = _loaded_prompt(arm)
    expected = ARMS[arm]
    if prompt.sha256 != _sha256_file(prompt_path(arm)):
        raise ActorRefinementError(f"loaded prompt hash mismatch: {arm}")
    if prompt.path.parent.name != PROMPT_DIR_NAME:
        raise ActorRefinementError("loaded prompt path mismatch")
    user = prompt.user_prompt_template.format(
        sample_id=sample_id,
        source_id=sample_id,
        source_text=source_text,
        few_shot_block=_few_shot_block(prompt),
    )
    if not prompt.system_prompt or not user:
        raise ActorRefinementError(f"empty rendered prompt: {arm}")
    return prompt.system_prompt, user


def deterministic_request_body(
    system_prompt: str, user_prompt: str
) -> dict[str, Any]:
    return {
        "model": MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "stream": STREAM,
        "thinking": THINKING,
    }


def estimate_tokens() -> dict[str, Any]:
    total = 0
    per_arm: dict[str, int] = {}
    for arm in ARM_ORDER:
        arm_total = 0
        for sample in load_samples():
            system, user = render_prompt(
                arm, sample["sample_id"], sample["text"])
            body = deterministic_request_body(system, user)
            raw = json.dumps(
                body, ensure_ascii=False, sort_keys=True).encode("utf-8")
            arm_total += math.ceil(len(raw) / 3)
        per_arm[arm] = arm_total
        total += arm_total
    return {"total": total, "per_arm": per_arm}


def _call_model(
    arm: str,
    sample: Mapping[str, str],
    transport: Any,
    *,
    enforce_off_peak: bool = True,
) -> dict[str, Any]:
    sid = sample["sample_id"]
    source_text = sample["text"]
    system, user = render_prompt(arm, sid, source_text)
    body = deterministic_request_body(system, user)
    body_sha = _sha256_bytes(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    )
    if enforce_off_peak:
        base._require_beijing_off_peak()
    from bpc_hybrid.llm_client import LLMRequest

    started_ns = time.time_ns()
    request_id = f"{arm}:{sid}:{started_ns}"
    try:
        response = transport.send(LLMRequest(
            source_id=sid,
            source_text=source_text,
            system_prompt=system,
            user_prompt=user,
        ))
        content = response.content or ""
        decode = getattr(transport, "last_decode", None) or {}
        usage = dict(decode.get("usage") or {})
        status = "ok" if decode.get("status") in (
            None, "ok_message_content") else "error"
        error = None
    except Exception as exc:
        content = ""
        decode = {}
        usage = {}
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
    actual_body_sha = getattr(
        transport, "last_request_body_sha256", None) or body_sha
    returned_model = decode.get("model")
    return {
        "sample_id": sid,
        "arm": arm,
        "sample_index": next(
            index for index, row in enumerate(load_samples())
            if row["sample_id"] == sid
        ),
        "prompt_name": ARMS[arm]["name"],
        "prompt_sha256": _sha256_file(prompt_path(arm)),
        "request_body_sha256": actual_body_sha,
        "deterministic_request_body_sha256": body_sha,
        "request_id": decode.get("request_id") or request_id,
        "raw_response_content": content,
        "response_sha256": _sha256_bytes(content.encode("utf-8")),
        "usage": usage,
        "request_status": status,
        "error": error,
        "returned_model": returned_model,
        "network_call": 1,
        "created_at_utc": _utc_now(),
    }


# ---------------------------------------------------------------------------
# Parsing and post-processing
# ---------------------------------------------------------------------------

def _safe_json_load(content: str) -> tuple[Any | None, str | None]:
    raw = (content or "").strip().strip("`")
    raw = raw.strip()
    if raw.lower().startswith("json"):
        raw = raw[4:].strip()
    if not raw:
        return None, "empty response content"
    try:
        return json.loads(raw), None
    except Exception as exc:
        return None, f"json_parse: {type(exc).__name__}: {exc}"


def _postprocess_call(
    call: Mapping[str, Any], source_text: str
) -> dict[str, Any]:
    from bpc_hybrid.d1_schema_adapter import adapt_relay_record
    from bpc_hybrid.d1_span_canonicalizer import (
        COST_METRIC_START_END,
        POLICY_REPAIR,
        canonicalize_record_coordinates,
    )
    from bpc_hybrid.stage2_canonical import validate_canonical

    if POLICY_REPAIR != CANONICALIZER_POLICY:
        raise ActorRefinementError("canonicalizer policy constant mismatch")

    parsed_payload, parse_error = _safe_json_load(
        str(call.get("raw_response_content") or ""))
    out: dict[str, Any] = {
        "sample_id": call.get("sample_id"),
        "parse_status": "ok" if parse_error is None else "failed",
        "parsed_response": parsed_payload,
        "parse_error": parse_error,
        "adapter_status": None,
        "adapter_output": None,
        "adapter_audit": None,
        "canonicalizer_status": None,
        "canonicalizer_output": None,
        "canonicalizer_audit": None,
        "validation": None,
        "canonical_final_record": None,
        "failure_reason": None,
        "success": False,
        "json_parse_ok": False,
        "adapter_ok": False,
        "canonicalizer_ok": False,
        "validator_ok": False,
    }
    if parse_error is not None:
        out["failure_reason"] = parse_error
        return out
    out["json_parse_ok"] = True

    try:
        adapted, adapter_audit = adapt_relay_record(
            parsed_payload, source_text)
        out["adapter_output"] = adapted
        out["adapter_audit"] = adapter_audit
        out["adapter_status"] = adapter_audit.get("status")
        if adapter_audit.get("status") == "failed":
            out["failure_reason"] = (
                "adapter: " + "; ".join(
                    adapter_audit.get("failed_reasons") or ["unknown"]))
            return out
        out["adapter_ok"] = True

        canonical, span_audit = canonicalize_record_coordinates(
            adapted,
            source_text,
            policy=POLICY_REPAIR,
            cost_metric=COST_METRIC_START_END,
        )
        out["canonicalizer_output"] = canonical
        out["canonicalizer_audit"] = span_audit
        out["canonicalizer_status"] = span_audit.get("status")
        if span_audit.get("status") == "failed":
            out["failure_reason"] = (
                "canonicalizer: " + "; ".join(
                    span_audit.get("failed_reasons") or ["unknown"]))
            return out
        out["canonicalizer_ok"] = True

        validation = validate_canonical(canonical)
        validation_dict = {
            "schema_valid": bool(validation.schema_valid),
            "cross_field_valid": bool(validation.cross_field_valid),
            "errors": list(validation.errors),
        }
        out["validation"] = validation_dict
        out["canonical_final_record"] = canonical
        out["validator_ok"] = bool(
            validation.schema_valid and validation.cross_field_valid)
        if not out["validator_ok"]:
            out["failure_reason"] = (
                "validator: " + "; ".join(validation.errors))
            return out
        out["success"] = True
        return out
    except Exception as exc:
        out["failure_reason"] = (
            f"postprocess: {type(exc).__name__}: {exc}")
        return out


def _prediction_row(processed: Mapping[str, Any]) -> dict[str, Any]:
    if processed.get("success"):
        return {
            "sample_id": processed["sample_id"],
            "request_status": "ok",
            "error": None,
            "record": processed["canonical_final_record"],
        }
    return {
        "sample_id": processed["sample_id"],
        "request_status": "failed",
        "error": processed.get("failure_reason") or "postprocess_failed",
        "record": {},
    }


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return base._read_jsonl(path)


def _flush_jsonl(path: Path, row: Mapping[str, Any]) -> None:
    base._append_jsonl(path, row)


def _process_arm(
    arm: str,
    samples: Sequence[Mapping[str, str]],
    transport: Any,
    *,
    enforce_off_peak: bool = True,
    sample_limit: int | None = None,
    stop_after_new_calls: int | None = None,
) -> dict[str, Any]:
    run_dir = OUT_DIR / arm / "repeat-01"
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw_responses.jsonl"
    ledger_path = run_dir / "calls_ledger.jsonl"
    existing_rows = _read_jsonl(raw_path)
    existing_by_id: dict[str, dict[str, Any]] = {}
    for row in existing_rows:
        sid = str(row.get("sample_id"))
        if not sid or sid in existing_by_id:
            raise ActorRefinementError(
                f"duplicate or malformed raw row for {arm}: {sid!r}")
        existing_by_id[sid] = row
    known_ids = {row["sample_id"] for row in samples}
    if set(existing_by_id) - known_ids:
        raise ActorRefinementError("raw response contains unknown sample_id")

    raw_rows: list[dict[str, Any]] = []
    new_calls = 0
    resumed = 0
    limit = len(samples) if sample_limit is None else min(sample_limit, len(samples))
    for index, sample in enumerate(samples[:limit]):
        sid = sample["sample_id"]
        if sid in existing_by_id:
            call = existing_by_id[sid]
            resumed += 1
        else:
            call = _call_model(
                arm, sample, transport,
                enforce_off_peak=enforce_off_peak)
            _flush_jsonl(raw_path, call)
            _flush_jsonl(ledger_path, {
                "sample_id": sid,
                "arm": arm,
                "repeat_id": "repeat-01",
                "state": "completed",
                "request_status": call.get("request_status"),
                "response_sha256": call.get("response_sha256"),
                "created_at_utc": call.get("created_at_utc"),
            })
            new_calls += 1
            if new_calls % 10 == 0:
                print(
                    f"[{arm}] new calls={new_calls} "
                    f"resumed={resumed} last={sid}",
                    flush=True,
                )
            if stop_after_new_calls is not None and new_calls >= stop_after_new_calls:
                raw_rows.append(call)
                break
        raw_rows.append(call)

    processed_rows: list[dict[str, Any]] = []
    for call in raw_rows:
        sid = str(call.get("sample_id"))
        source_text = next(
            row["text"] for row in samples if row["sample_id"] == sid)
        processed = _postprocess_call(call, source_text)
        processed_rows.append(processed)

    predictions = [_prediction_row(row) for row in processed_rows]
    raw_by_id = {str(row["sample_id"]): row for row in raw_rows}
    prediction_by_id = {
        str(row["sample_id"]): row for row in predictions}
    processed_by_id = {
        str(row["sample_id"]): row for row in processed_rows}
    ordered_sids = [row["sample_id"] for row in samples[:len(raw_rows)]]

    raw_ordered = [raw_by_id[sid] for sid in ordered_sids]
    parsed_rows = [
        {
            "sample_id": sid,
            "arm": arm,
            "parse_status": processed_by_id[sid]["parse_status"],
            "parsed_response": processed_by_id[sid]["parsed_response"],
            "parse_error": processed_by_id[sid]["parse_error"],
        }
        for sid in ordered_sids
    ]
    adapter_rows = [
        {
            "sample_id": sid,
            "arm": arm,
            "status": processed_by_id[sid]["adapter_status"],
            "adapter_output": processed_by_id[sid]["adapter_output"],
            "adapter_audit": processed_by_id[sid]["adapter_audit"],
        }
        for sid in ordered_sids
    ]
    canonicalizer_rows = [
        {
            "sample_id": sid,
            "arm": arm,
            "status": processed_by_id[sid]["canonicalizer_status"],
            "canonicalizer_output": processed_by_id[sid]["canonicalizer_output"],
            "canonicalizer_audit": processed_by_id[sid]["canonicalizer_audit"],
        }
        for sid in ordered_sids
    ]
    validation_rows = [
        {
            "sample_id": sid,
            "arm": arm,
            "validation": processed_by_id[sid]["validation"],
            "failure_reason": processed_by_id[sid]["failure_reason"],
        }
        for sid in ordered_sids
    ]
    provenance_rows = []
    for sid in ordered_sids:
        call = raw_by_id[sid]
        processed = processed_by_id[sid]
        provenance_rows.append({
            "sample_id": sid,
            "arm": arm,
            "request_body_sha256": call.get("request_body_sha256"),
            "deterministic_request_body_sha256": call.get(
                "deterministic_request_body_sha256"),
            "prompt_sha256": call.get("prompt_sha256"),
            "request_id": call.get("request_id"),
            "raw_response_content": call.get("raw_response_content"),
            "response_sha256": call.get("response_sha256"),
            "raw_request_status": call.get("request_status"),
            "raw_error": call.get("error"),
            "parsed_response": processed.get("parsed_response"),
            "parse_error": processed.get("parse_error"),
            "adapter_output": processed.get("adapter_output"),
            "adapter_audit": processed.get("adapter_audit"),
            "canonicalizer_output": processed.get("canonicalizer_output"),
            "canonicalizer_audit": processed.get("canonicalizer_audit"),
            "validation": processed.get("validation"),
            "canonical_final_record": processed.get("canonical_final_record"),
            "failure_reason": processed.get("failure_reason"),
            "success": processed.get("success"),
        })

    _write_jsonl(run_dir / "parsed_responses.jsonl", parsed_rows)
    _write_jsonl(run_dir / "adapter_output.jsonl", adapter_rows)
    _write_jsonl(run_dir / "canonicalizer_output.jsonl", canonicalizer_rows)
    _write_jsonl(run_dir / "validation.jsonl", validation_rows)
    _write_jsonl(run_dir / "provenance.jsonl", provenance_rows)
    _write_jsonl(run_dir / "canonical_predictions.jsonl", predictions)
    _write_jsonl(
        run_dir / "failed_samples.jsonl",
        [row for row in predictions if row["request_status"] != "ok"],
    )
    # Keep the ledger complete and deterministic; raw responses remain the
    # crash-safe source of truth.
    _write_jsonl(ledger_path, [
        {
            "sample_id": row["sample_id"],
            "arm": arm,
            "repeat_id": "repeat-01",
            "state": "completed",
            "request_status": row.get("request_status"),
            "response_sha256": row.get("response_sha256"),
            "created_at_utc": row.get("created_at_utc"),
        }
        for row in raw_ordered
    ])
    manifest = {
        "arm": arm,
        "repeat_id": "repeat-01",
        "sample_count": len(raw_ordered),
        "planned_sample_count": len(samples),
        "new_calls": new_calls,
        "resumed_completed_count": resumed,
        "api_ok_count": sum(
            1 for row in raw_ordered
            if row.get("request_status") == "ok"),
        "json_parse_ok_count": sum(
            1 for row in processed_rows if row.get("json_parse_ok")),
        "adapter_ok_count": sum(
            1 for row in processed_rows if row.get("adapter_ok")),
        "canonicalizer_ok_count": sum(
            1 for row in processed_rows if row.get("canonicalizer_ok")),
        "validator_ok_count": sum(
            1 for row in processed_rows if row.get("validator_ok")),
        "prediction_ok_count": sum(
            1 for row in predictions if row["request_status"] == "ok"),
        "failed_count": sum(
            1 for row in predictions if row["request_status"] != "ok"),
        "prompt_sha256": _sha256_file(prompt_path(arm)),
        "raw_responses_sha256": _sha256_file(raw_path),
        "canonical_predictions_sha256": _sha256_file(
            run_dir / "canonical_predictions.jsonl"),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return {
        "manifest": manifest,
        "predictions": predictions,
        "processed_rows": processed_rows,
        "raw_rows": raw_ordered,
    }


def dry_run() -> dict[str, Any]:
    manifest = validate_experiment_manifest()
    estimates = estimate_tokens()
    result = {
        "schema_version": "actor_refinement_dry_run@1.0.0",
        "mode": "dry_run_off_network",
        "experiment_id": EXPERIMENT_ID,
        "planned_calls": PLANNED_CALLS,
        "llm_api_calls": 0,
        "network_calls": 0,
        "model": manifest["model"],
        "sampling": manifest["sampling"],
        "dataset": manifest["dataset"],
        "canonicalizer": manifest["canonicalizer"],
        "evaluator": manifest["evaluator"],
        "estimated_input_tokens": estimates["total"],
        "estimated_input_tokens_per_arm": estimates["per_arm"],
        "prompts": manifest["prompts"],
    }
    return result


def _validate_runtime_config(llm_config: Any) -> None:
    if not getattr(llm_config, "enabled", False):
        raise ActorRefinementError("real provider is not enabled")
    if llm_config.provider != MODEL_PROVIDER:
        raise ActorRefinementError("provider mismatch")
    if llm_config.model != MODEL_ID:
        raise ActorRefinementError("model mismatch")
    if llm_config.temperature != TEMPERATURE:
        raise ActorRefinementError("temperature mismatch")
    if llm_config.top_p != TOP_P:
        raise ActorRefinementError("top_p mismatch")
    if llm_config.max_tokens != MAX_TOKENS:
        raise ActorRefinementError("max_tokens mismatch")


def _new_transport() -> Any:
    from bpc_hybrid.h1_transport import H1RequestPolicy
    from bpc_hybrid.llm_client import RealAPITransport
    from bpc_hybrid.llm_config import LLMConfig

    llm_config = LLMConfig.from_env(
        project_root=ROOT, load_project_env=True)
    _validate_runtime_config(llm_config)
    return RealAPITransport(
        llm_config,
        timeout_seconds=180.0,
        policy=H1RequestPolicy(
            stream=STREAM,
            thinking=THINKING,
            response_format=RESPONSE_FORMAT,
        ),
    )


def smoke() -> dict[str, Any]:
    validate_experiment_manifest()
    # A one-call interface/parser/schema smoke test on B0 sample 1.  It is
    # part of the 600-call plan and is resumed by the full run; no metric is
    # computed here and no prompt is changed based on this output.
    samples = load_samples()[:1]
    result = _process_arm(
        "B0", samples, _new_transport(),
        enforce_off_peak=True,
        sample_limit=1,
        stop_after_new_calls=1,
    )
    report = {
        "schema_version": "actor_refinement_smoke@1.0.0",
        "experiment_id": EXPERIMENT_ID,
        "purpose": "interface_parser_schema_smoke_only",
        "evaluation_scores_computed": False,
        "prompt_modified_after_smoke": False,
        "network_calls_in_planned_budget": result["manifest"]["new_calls"],
        "arm": "B0",
        "sample_id": samples[0]["sample_id"],
        "raw_request_status": result["raw_rows"][0].get("request_status"),
        "json_parse_ok": result["processed_rows"][0].get("json_parse_ok"),
        "adapter_ok": result["processed_rows"][0].get("adapter_ok"),
        "canonicalizer_ok": result["processed_rows"][0].get("canonicalizer_ok"),
        "validator_ok": result["processed_rows"][0].get("validator_ok"),
        "failure_reason": result["processed_rows"][0].get("failure_reason"),
    }
    SMOKE_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return report


def execute() -> dict[str, Any]:
    manifest = validate_experiment_manifest()
    samples = load_samples()
    started = time.time()
    arm_results: dict[str, Any] = {}
    actual_new_calls = 0
    resumed_total = 0
    try:
        for arm in ARM_ORDER:
            transport = _new_transport()
            result = _process_arm(
                arm, samples, transport, enforce_off_peak=True)
            arm_results[arm] = result["manifest"]
            actual_new_calls += result["manifest"]["new_calls"]
            resumed_total += result["manifest"]["resumed_completed_count"]
    except Exception as exc:
        summary = {
            "schema_version": "d1_actor_refinement_execution@1.0.0",
            "experiment_id": EXPERIMENT_ID,
            "status": "aborted",
            "abort_reason": f"{type(exc).__name__}: {exc}",
            "actual_new_calls": actual_new_calls,
            "resumed_completed_count": resumed_total,
            "arms": arm_results,
            "runtime_seconds": round(time.time() - started, 3),
        }
        EXECUTION_SUMMARY.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n",
        )
        raise

    complete_counts = {
        arm: arm_results[arm]["sample_count"] for arm in ARM_ORDER
    }
    complete = all(
        complete_counts[arm] == SAMPLES_PER_ARM for arm in ARM_ORDER)
    actual_calls_this_invocation = actual_new_calls
    total_accounted = actual_calls_this_invocation + resumed_total
    summary = {
        "schema_version": "d1_actor_refinement_execution@1.0.0",
        "experiment_id": EXPERIMENT_ID,
        "status": "complete" if complete else "incomplete",
        "model": manifest["model"],
        "sampling": manifest["sampling"],
        "dataset": manifest["dataset"],
        "canonicalizer": manifest["canonicalizer"],
        "evaluator": manifest["evaluator"],
        "planned_calls": PLANNED_CALLS,
        "actual_new_calls": actual_calls_this_invocation,
        "resumed_completed_count": resumed_total,
        "total_calls_accounted": total_accounted,
        "complete": complete,
        "arms": arm_results,
        "runtime_seconds": round(time.time() - started, 3),
        "finished_at_utc": _utc_now(),
    }
    EXECUTION_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--freeze-manifest", action="store_true",
                      help="write/refresh the pre-execution manifest only")
    args = parser.parse_args()
    try:
        if args.freeze_manifest:
            print(json.dumps(
                write_frozen_experiment_manifest(),
                ensure_ascii=False, indent=2))
            return 0
        if args.dry_run:
            print(json.dumps(dry_run(), ensure_ascii=False, indent=2))
            return 0
        if args.smoke:
            print(json.dumps(smoke(), ensure_ascii=False, indent=2))
            return 0
        summary = execute()
        print(json.dumps({
            "status": summary["status"],
            "planned_calls": summary["planned_calls"],
            "actual_new_calls": summary["actual_new_calls"],
            "resumed_completed_count": summary["resumed_completed_count"],
            "total_calls_accounted": summary["total_calls_accounted"],
            "complete": summary["complete"],
        }, ensure_ascii=False, indent=2))
        return 0 if summary["complete"] else 3
    except ActorRefinementError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
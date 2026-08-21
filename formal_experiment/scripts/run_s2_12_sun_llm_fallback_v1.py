# -*- coding: utf-8 -*-
"""Run the locked S2.12 ``sun_llm_fallback`` arm (27 triggered calls) as a
fail-closed comparison-only control.

* Replays the locked risk-descending trigger selection (frozen plan) and
  verifies every one of the 27 request bodies against the frozen plan AND
  the locked preflight report before any transport call.
* Zero API by default (payload-locked fake transport, deterministic no-op
  patch envelopes, no network, no ``.env``).
* Real transport requires ``--allow-llm`` + ``--auth-file`` (full S2.12
  authorization contract).  This batch does NOT create a real authorization
  file; real calls remain pending user authorization.
* H1/Rules+LLM-Repair remains comparison-only: trigger, prompt, actor
  limits, and repair logic are NOT modified here.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s2_12_execution import (  # noqa: E402
    INPUT,
    OUTPUT_DIRS,
    PREFLIGHT_LOCK,
    PREFLIGHT_REPORT,
    REQUIRED_MODEL,
    S212ExecutionError,
    PayloadLockedFakeTransport,
    _FORBIDDEN_SECRET_KEYS,
    _FORBIDDEN_TEXT_KEYS,
    _contains_forbidden,
    _json_bytes,
    _sha,
    atomic_publish_directory,
    build_cost_doc,
    check_off_peak_only,
    load_and_validate_authorization,
    load_lock,
    load_report,
    manifest_capsule,
    rebuild_and_verify_payloads,
    verify_63_count,
)
from bpc_hybrid.llm_client import (  # noqa: E402
    LLMClientError,
    LLMRequest,
    RealAPITransport,
)
from bpc_hybrid.h1_transport import (  # noqa: E402
    DEEPSEEK_V4_PRO_H1_POLICY,
    build_transport_capture_row,
)
from run_sun_llm_fallback import (  # noqa: E402
    _patch_event_base,
    apply_patch_envelope,
)
from bpc_hybrid.b0_artifact import prediction_hash  # noqa: E402

FROZEN_PLAN = ROOT / "configs/s2_12_fallback_trigger_plan_v1.json"


def _assemble_capsule(
    outputs: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    capture_rows: list[dict[str, Any]],
    stats: dict[str, Any],
    output_dir: Path,
) -> Any:
    """Assemble the fallback prediction capsule (predictions/manifest/
    telemetry/cost/transport_capture) and return an object with ``files``."""
    from dataclasses import dataclass

    @dataclass
    class Capsule:
        files: dict[str, bytes]

    from bpc_hybrid.s2_12_execution import _strip_text_fields

    records = [
        {
            "sample_id": sample_id,
            "request_status": "ok",
            "error_category": None,
            "record": _strip_text_fields(record),
        }
        for sample_id, record in sorted(outputs.items())
    ]
    if len(records) != 36:
        raise S212ExecutionError(
            f"fallback capsule must contain 36 records, got {len(records)}"
        )
    prediction_doc = {
        "schema_version": "s2_12_sun_llm_fallback_predictions@1.0.0",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "sun_llm_fallback",
        "record_count": len(records),
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": records,
    }
    if _contains_forbidden(prediction_doc, _FORBIDDEN_TEXT_KEYS):
        raise S212ExecutionError("text containment failed for committed predictions")
    if _contains_forbidden(prediction_doc, _FORBIDDEN_SECRET_KEYS):
        raise S212ExecutionError("secret containment failed for committed predictions")

    telemetry = {
        "schema_version": "s2_12_sun_llm_fallback_telemetry@1.0.0",
        "transport": "fake_payload_locked" if stats["fake"] else "real_authorized",
        "llm_calls": stats["llm_calls"],
        "max_calls": stats["max_calls"],
        "returned_models": stats["returned_models"],
        "patch_events": events,
        "patch_accepted": stats["accepted"],
        "prediction_changed": stats["changed"],
        "text_or_gold_payload_committed": False,
    }
    cost = build_cost_doc(
        llm_calls=stats["llm_calls"],
        max_calls=stats["max_calls"],
        input_tokens_billed=stats["input_tokens_billed"],
        output_tokens_billed=stats["output_tokens_billed"],
        actual_cost_usd=stats["cost_usd"],
        fake=stats["fake"],
    )
    files = {
        "predictions.json": _json_bytes(prediction_doc),
        "telemetry.json": _json_bytes(telemetry),
        "cost.json": _json_bytes(cost),
    }
    if stats["fake"]:
        files["transport_capture.jsonl"] = "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in capture_rows
        ).encode("utf-8")
    manifest = {
        "schema_version": "s2_12_sun_llm_fallback_manifest@1.0.0",
        "run_id": "s2_12_sun_llm_fallback_v1",
        "status": (
            "completed_fake_zero_api" if stats["fake"]
            else "completed_real_authorized"
        ),
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "sun_llm_fallback",
        "role": "comparison_only_negative_result_control",
        "frozen_trigger_plan": {
            "path": "configs/s2_12_fallback_trigger_plan_v1.json",
            "sha256": _sha(FROZEN_PLAN),
        },
        "input_binding": {
            "path": "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "sha256": _sha(INPUT),
            "records": 36,
        },
        "run_lock": {
            "path": "configs/s2_12_api_arms_preflight_v1.json",
            "sha256": _sha(PREFLIGHT_LOCK),
        },
        "preflight_report": {
            "path": "outputs/reports/s2_12_api_preflight_v1.json",
            "sha256": _sha(PREFLIGHT_REPORT),
        },
        "gold_isolation": {
            "gold_read_by_runner": False,
            "predictions_locked_before_evaluation": True,
            "post_result_tuning_forbidden": True,
        },
        "runtime_summary": telemetry,
        "artifacts": manifest_capsule(files),
        "safety": {
            "llm_api_calls": stats["llm_calls"],
            "network_calls": 0 if stats["fake"] else stats["llm_calls"],
            "cost_usd": stats["cost_usd"],
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command": "python formal_experiment/scripts/"
        "run_s2_12_sun_llm_fallback_v1.py --runtime-home "
        "D:/environment/stanford-corenlp-4.5.10",
    }
    files["manifest.json"] = _json_bytes(manifest)
    return Capsule(files=files)


def _load_auth(args, lock, report) -> dict[str, Any] | None:
    if not args.auth_file:
        return None
    runner_hash = _sha(Path(__file__))
    auth = load_and_validate_authorization(
        args.auth_file, lock, report, runner_hash
    )
    return auth


def run(args) -> dict[str, Any]:
    lock = load_lock()
    report = load_report()
    # FROZEN plan binding: replay must reproduce byte-identical plan.
    frozen = json.loads(FROZEN_PLAN.read_text(encoding="utf-8"))
    if frozen.get("schema_version") != "s2_12_fallback_trigger_plan@1.0.0":
        raise S212ExecutionError("frozen trigger plan schema identity drift")
    if frozen.get("status") != "frozen_locked_before_api_authorization":
        raise S212ExecutionError("frozen trigger plan status drift")
    if frozen.get("retry") != 0:
        raise S212ExecutionError("frozen trigger plan retry must be 0")

    output_dir = (args.output_dir or OUTPUT_DIRS["sun_llm_fallback"]).resolve()
    fake = not args.allow_llm
    if fake and output_dir in {path.resolve() for path in OUTPUT_DIRS.values()}:
        raise S212ExecutionError(
            "fake transport must not publish to a formal prediction directory"
        )

    auth = _load_auth(args, lock, report) if args.allow_llm else None
    if args.allow_llm and auth is None:
        raise S212ExecutionError(
            "real transport requires --allow-llm AND --auth-file (no call made)"
        )
    if args.allow_llm and args.transport != "real":
        raise S212ExecutionError("--allow-llm requires --transport real")
    if args.allow_llm:
        check_off_peak_only(auth)

    # Rebuild + verify the 27 fallback payloads against the frozen plan AND
    # the locked preflight report.
    rows_by_arm = rebuild_and_verify_payloads(lock, report, args.runtime_home)
    verify_63_count(rows_by_arm)
    fallback = rows_by_arm["sun_llm_fallback"]
    frozen_entries = {
        (e["sample_id"], e["clause_id"]): e for e in frozen["selected_plans"]
    }
    if len(frozen_entries) != 27:
        raise S212ExecutionError("frozen trigger plan must contain exactly 27 entries")
    for row in fallback:
        entry = frozen_entries.get((row["sample_id"], row["clause_id"]))
        if entry is None:
            raise S212ExecutionError(
                f"rebuilt fallback call not in frozen plan: "
                f"{row['sample_id']}/{row['clause_id']}"
            )
        if entry["request_body_sha256"] != row["request_body_sha256"]:
            raise S212ExecutionError(
                f"frozen plan body sha mismatch for "
                f"{row['sample_id']}/{row['clause_id']}"
            )
        if list(entry["repair_fields"]) != list(row["plan"].repair_fields):
            raise S212ExecutionError(
                f"frozen plan repair_fields drift for "
                f"{row['sample_id']}/{row['clause_id']}"
            )

    # Full B0 batch (all 36) for the prediction capsule.
    from build_s2_12_api_preflight_v1 import _rerun_b0 as _rerun
    _adapted, batch = _rerun(args.runtime_home)
    records_by_id = {item.record["sample_id"]: item.record for item in batch}
    if len(records_by_id) != 36:
        raise S212ExecutionError(f"full B0 batch != 36 records")

    transport = PayloadLockedFakeTransport(
        {row["request_body_sha256"]: row for row in fallback},
        "sun_llm_fallback",
        policy=DEEPSEEK_V4_PRO_H1_POLICY,
    )
    if not fake:
        from bpc_hybrid.llm_config import LLMConfig
        config = LLMConfig.from_env(project_root=ROOT)
        if config.provider == "mock" or not config.enabled:
            raise S212ExecutionError("real provider is not enabled")
        if config.model != REQUIRED_MODEL:
            raise S212ExecutionError("resolved model != deepseek-v4-pro")
        transport = RealAPITransport(config, timeout_seconds=args.transport_timeout)

    capture_rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    outputs: dict[str, dict[str, Any]] = dict(records_by_id)
    returned_models: set[str] = set()
    llm_calls = 0
    max_calls = 27
    input_tokens_billed = 0
    output_tokens_billed = 0
    cost_usd = 0.0
    accepted = 0
    changed = 0

    for row in fallback:
        if llm_calls >= max_calls:
            raise S212ExecutionError(
                "max-calls would be exceeded before the next transport call"
            )
        plan = row["plan"]
        record = row["plan_record"]
        request = LLMRequest(
            source_id=plan.sample_id,
            source_text=record.get("source_text", ""),
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
        )
        try:
            response = transport.send(request)
        except LLMClientError as exc:
            raise S212ExecutionError(
                f"transport failure on {plan.sample_id}/{plan.clause_id}: {exc}"
            ) from exc
        llm_calls += 1
        returned = getattr(response, "model", None)
        if returned:
            returned_models.add(str(returned))
            if str(returned) != REQUIRED_MODEL:
                raise S212ExecutionError(
                    f"returned model {returned!r} != {REQUIRED_MODEL!r} "
                    f"({plan.sample_id}/{plan.clause_id})"
                )

        event = _patch_event_base(plan)
        event["selected_for_call"] = True
        event["llm_call_performed"] = True
        try:
            envelope = json.loads(response.content)
        except json.JSONDecodeError as exc:
            event["status"] = "invalid_patch_json"
            event["rejection_reasons"] = [f"invalid JSON: {exc}"]
            events.append(event)
            capture_rows.append(
                build_transport_capture_row(
                    request_id=f"{plan.sample_id}/{plan.clause_id}",
                    sample_id=plan.sample_id,
                    clause_id=plan.clause_id,
                    clause_index=plan.clause_index,
                    prompt_sha256=frozen["prompt"]["sha256"],
                    prompt_variant="full_b0_v4",
                    b0_prediction_sha256=prediction_hash(record),
                    request_body_sha256=row["request_body_sha256"],
                    request_policy=DEEPSEEK_V4_PRO_H1_POLICY.to_dict(),
                    http_status=None,
                    endpoint_descriptor={"host": None},
                    requested_model=REQUIRED_MODEL,
                    resolved_model=REQUIRED_MODEL,
                    decode={"status": "invalid_patch_json",
                            "usage": {}, "model": None},
                    sanitized_response_envelope=None,
                )
            )
            continue
        if not isinstance(envelope, dict):
            event["status"] = "invalid_patch_envelope"
            event["rejection_reasons"] = ["envelope is not an object"]
            events.append(event)
            capture_rows.append(
                build_transport_capture_row(
                    request_id=f"{plan.sample_id}/{plan.clause_id}",
                    sample_id=plan.sample_id,
                    clause_id=plan.clause_id,
                    clause_index=plan.clause_index,
                    prompt_sha256=frozen["prompt"]["sha256"],
                    prompt_variant="full_b0_v4",
                    b0_prediction_sha256=prediction_hash(record),
                    request_body_sha256=row["request_body_sha256"],
                    request_policy=DEEPSEEK_V4_PRO_H1_POLICY.to_dict(),
                    http_status=None,
                    endpoint_descriptor={"host": None},
                    requested_model=REQUIRED_MODEL,
                    resolved_model=REQUIRED_MODEL,
                    decode={"status": "invalid_patch_envelope",
                            "usage": {}, "model": None},
                    sanitized_response_envelope=None,
                )
            )
            continue

        outputs[plan.sample_id], patch_event = apply_patch_envelope(
            records_by_id[plan.sample_id], envelope, plan
        )
        event.update(patch_event)
        events.append(event)
        capture_rows.append(
            build_transport_capture_row(
                request_id=f"{plan.sample_id}/{plan.clause_id}",
                sample_id=plan.sample_id,
                clause_id=plan.clause_id,
                clause_index=plan.clause_index,
                prompt_sha256=frozen["prompt"]["sha256"],
                prompt_variant="full_b0_v4",
                b0_prediction_sha256=prediction_hash(record),
                request_body_sha256=row["request_body_sha256"],
                request_policy=DEEPSEEK_V4_PRO_H1_POLICY.to_dict(),
                http_status=None,
                endpoint_descriptor={"host": None},
                requested_model=REQUIRED_MODEL,
                resolved_model=REQUIRED_MODEL,
                decode={"status": "ok_message_content",
                        "usage": {}, "model": REQUIRED_MODEL},
                sanitized_response_envelope=None,
            )
        )
        if patch_event.get("patch_accepted"):
            accepted += 1
            if prediction_hash(record) != prediction_hash(outputs[plan.sample_id]):
                changed += 1
        if not fake:
            usage = getattr(response, "usage", None) or {}
            input_tokens_billed += int(usage.get("prompt_tokens", 0))
            output_tokens_billed += int(usage.get("completion_tokens", 0))

    if llm_calls != 27:
        raise S212ExecutionError(f"expected 27 calls, made {llm_calls}")

    stats = {
        "llm_calls": llm_calls,
        "max_calls": max_calls,
        "returned_models": sorted(returned_models),
        "accepted": accepted,
        "changed": changed,
        "input_tokens_billed": input_tokens_billed,
        "output_tokens_billed": output_tokens_billed,
        "cost_usd": cost_usd,
        "fake": fake,
    }
    return outputs, events, capture_rows, stats, output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-home", type=Path,
        default=Path("D:/environment/stanford-corenlp-4.5.10"),
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Override the formal output directory (tests only; the formal "
             "path is used when omitted).",
    )
    parser.add_argument(
        "--transport", choices=("fake", "real"), default="fake",
    )
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--auth-file", type=Path)
    parser.add_argument("--transport-timeout", type=float, default=180.0)
    args = parser.parse_args()
    try:
        outputs, events, capture_rows, stats, output_dir = run(args)
        capsule = _assemble_capsule(
            outputs, events, capture_rows, stats, output_dir
        )
        if output_dir is not None:
            atomic_publish_directory(output_dir, capsule.files)
    except S212ExecutionError as exc:
        print(f"S2.12 sun_llm_fallback refused: {exc}")
        return 2
    print(
        "S2.12 sun_llm_fallback predictions locked before Gold evaluation "
        f"(fake={stats['fake']})"
    )
    print(
        f"records=36 calls={stats['llm_calls']} accepted={stats['accepted']} "
        f"changed={stats['changed']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
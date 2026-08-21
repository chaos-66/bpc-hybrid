# -*- coding: utf-8 -*-
"""Run the locked S2.12 ``direct_llm`` arm (36 calls) with a fail-closed
payload contract.

* Zero API by default: ``--transport fake`` (payload-locked fake transport,
  deterministic synthetic responses, no network, no ``.env``, no API key).
* Real transport requires ``--allow-llm`` AND ``--auth-file`` with the full
  S2.12 authorization contract (see ``bpc_hybrid.s2_12_execution``).
* Every one of the 36 request bodies is rebuilt with the exact preflight
  paths and must SHA-256-match the locked preflight report before any
  transport call; any drift aborts before the first call.
* This batch does NOT create a real authorization file; real calls remain
  pending user authorization.
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
    _strip_text_fields,
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
from bpc_hybrid.h1_transport import H1RequestPolicy  # noqa: E402
from run_s2_12_sun_rule_only_v1 import _resolve_records  # noqa: E402
from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402
from bpc_hybrid.d1_schema_adapter import adapt_relay_record  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from bpc_hybrid.prompt_loader import build_manifest_entry  # noqa: E402


def _load_auth(args, lock, report) -> dict[str, Any] | None:
    if not args.auth_file:
        return None
    runner_hash = _sha(Path(__file__))
    return load_and_validate_authorization(
        args.auth_file, lock, report, runner_hash
    )


def run(args) -> dict[str, Any]:
    lock = load_lock()
    report = load_report()
    rows_by_arm = rebuild_and_verify_payloads(lock, report, args.runtime_home)
    verify_63_count(rows_by_arm)
    direct = rows_by_arm["direct_llm"]

    output_dir = (args.output_dir or OUTPUT_DIRS["direct_llm"]).resolve()
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

    transport = PayloadLockedFakeTransport(
        {row["request_body_sha256"]: row for row in direct},
        "direct_llm",
        policy=H1RequestPolicy(stream=False, thinking={"type": "disabled"},
                               response_format=None),
    )
    if not fake:
        from bpc_hybrid.llm_config import LLMConfig
        config = LLMConfig.from_env(project_root=ROOT)
        if config.provider == "mock" or not config.enabled:
            raise S212ExecutionError("real provider is not enabled")
        if config.model != REQUIRED_MODEL:
            raise S212ExecutionError("resolved model != deepseek-v4-pro")
        transport = RealAPITransport(config, timeout_seconds=args.transport_timeout)

    # Resolve the hash-bound source text once (Gold-blind) for fake responses.
    # _resolve_records returns runtime IDs (s212_0001..); map back to the
    # formal payload IDs via the runtime->formal mapping.
    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    records, runtime_to_formal = _resolve_records(input_doc)
    runtime_text = {rec["sample_id"]: rec["approved_text_en"] for rec in records}
    source_by_id = {
        formal_id: runtime_text[runtime_id]
        for runtime_id, formal_id in runtime_to_formal.items()
    }

    responses: list[dict[str, Any]] = []
    returned_models: set[str] = set()
    llm_calls = 0
    max_calls = len(direct)
    output_tokens_billed = 0
    input_tokens_billed = 0
    cost_usd = 0.0
    span_audit_summary = {
        "records": 0, "reanchored": 0, "clause_spans": 0, "field_spans": 0,
        "dropped_spans": 0, "dropped_clauses": 0, "adapted_spans": 0,
    }

    for row in direct:
        if llm_calls >= max_calls:
            raise S212ExecutionError(
                "max-calls would be exceeded before the next transport call"
            )
        sample_text = source_by_id[row["sample_id"]]
        request = LLMRequest(
            source_id=row["sample_id"],
            source_text=sample_text,
            system_prompt=row["system_prompt"],
            user_prompt=row["user_prompt"],
        )
        try:
            response = transport.send(request)
        except LLMClientError as exc:
            raise S212ExecutionError(
                f"transport failure on {row['sample_id']} (details redacted): {exc}"
            ) from exc
        llm_calls += 1
        returned = getattr(response, "model", None)
        if returned:
            returned_models.add(str(returned))
            if str(returned) != REQUIRED_MODEL:
                raise S212ExecutionError(
                    f"returned model {returned!r} != {REQUIRED_MODEL!r} "
                    f"({row['sample_id']})"
                )

        raw_text = response.content.strip()
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise S212ExecutionError(
                f"non-JSON response for {row['sample_id']}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise S212ExecutionError(
                f"response payload not a dict for {row['sample_id']}"
            )
        payload.setdefault("source_id", row["sample_id"])
        payload.setdefault("sample_id", row["sample_id"])
        payload.setdefault("schema_version", "1.0.0")
        payload.setdefault("method", {
            "name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0",
        })
        payload.setdefault("unsupported_or_ambiguous", [])

        payload, adapt_audit = adapt_relay_record(payload, sample_text or "")
        if adapt_audit["status"] == "failed":
            raise S212ExecutionError(
                f"relay adaptation failed for {row['sample_id']}: "
                f"{adapt_audit['failed_reasons']}"
            )
        payload, span_audit = canonicalize_record_coordinates(payload, sample_text or "")
        if span_audit["status"] == "failed":
            raise S212ExecutionError(
                f"span canonicalization failed for {row['sample_id']}: "
                f"{span_audit['failed_reasons']}"
            )
        report_v = validate_canonical(payload)
        if not (report_v.schema_valid and report_v.cross_field_valid):
            raise S212ExecutionError(
                f"canonical validation failed for {row['sample_id']}: "
                f"{report_v.errors}"
            )
        responses.append({
            "sample_id": row["sample_id"],
            "request_status": "ok",
            "error_category": None,
            "errors": [],
            "span_canonicalization": span_audit,
            "record": payload,
        })
        span_audit_summary["records"] += 1
        span_audit_summary["reanchored"] += span_audit["reanchored_count"]
        span_audit_summary["clause_spans"] += span_audit["clause_span_count"]
        span_audit_summary["field_spans"] += span_audit["field_span_count"]
        span_audit_summary["dropped_spans"] += len(span_audit.get("dropped_spans", []))
        span_audit_summary["dropped_clauses"] += len(span_audit.get("dropped_clauses", []))
        span_audit_summary["adapted_spans"] += adapt_audit["spans_adapted"]
        if not fake:
            usage = getattr(response, "usage", None) or {}
            input_tokens_billed += int(usage.get("prompt_tokens", 0))
            output_tokens_billed += int(usage.get("completion_tokens", 0))
            # Cost from real usage is recorded in cost.json by the executor;
            # fake mode bills zero.

    if llm_calls != 36:
        raise S212ExecutionError(f"expected 36 calls, made {llm_calls}")

    prediction_doc = {
        "schema_version": "s2_12_direct_llm_predictions@1.0.0",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "direct_llm",
        "record_count": len(responses),
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": [
            {
                "sample_id": row["sample_id"],
                "request_status": row["request_status"],
                "error_category": row["error_category"],
                "record": _strip_text_fields(row["record"]),
            }
            for row in responses
        ],
    }
    if _contains_forbidden(prediction_doc, _FORBIDDEN_TEXT_KEYS):
        raise S212ExecutionError("text containment failed for committed predictions")
    if _contains_forbidden(prediction_doc, _FORBIDDEN_SECRET_KEYS):
        raise S212ExecutionError("secret containment failed for committed predictions")

    telemetry = {
        "schema_version": "s2_12_direct_llm_telemetry@1.0.0",
        "transport": "fake_payload_locked" if fake else "real_authorized",
        "llm_calls": llm_calls,
        "max_calls": max_calls,
        "returned_models": sorted(returned_models),
        "span_canonicalization": span_audit_summary,
        "request_body_utf8_bytes_total": sum(
            row["request_body_utf8_bytes"] for row in direct
        ),
        "text_or_gold_payload_committed": False,
    }
    cost = build_cost_doc(
        llm_calls=llm_calls,
        max_calls=max_calls,
        input_tokens_billed=input_tokens_billed,
        output_tokens_billed=output_tokens_billed,
        actual_cost_usd=cost_usd,
        fake=fake,
    )

    files = {
        "predictions.json": _json_bytes(prediction_doc),
        "telemetry.json": _json_bytes(telemetry),
        "cost.json": _json_bytes(cost),
    }
    manifest = {
        "schema_version": "s2_12_direct_llm_manifest@1.0.0",
        "run_id": "s2_12_direct_llm_v1",
        "status": (
            "completed_fake_zero_api" if fake
            else "completed_real_authorized"
        ),
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "direct_llm",
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
            "llm_api_calls": llm_calls,
            "network_calls": 0 if fake else llm_calls,
            "cost_usd": cost_usd,
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command": " ".join(
            "python formal_experiment/scripts/run_s2_12_direct_llm_v1.py"
            " --runtime-home D:/environment/stanford-corenlp-4.5.10".split()
        ),
    }
    files["manifest.json"] = _json_bytes(manifest)
    atomic_publish_directory(output_dir, files)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-home", type=Path,
        default=Path("D:/environment/stanford-corenlp-4.5.10"),
        help="CoreNLP runtime home (only used to verify the payload contract "
             "via the preflight diagnostic replay).",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Override the formal output directory (tests only; the formal "
             "path is used when omitted).",
    )
    parser.add_argument(
        "--transport", choices=("fake", "real"), default="fake",
        help="fake = payload-locked fake transport (default, zero API); "
             "real = requires --allow-llm + --auth-file.",
    )
    parser.add_argument("--allow-llm", action="store_true")
    parser.add_argument("--auth-file", type=Path)
    parser.add_argument("--transport-timeout", type=float, default=180.0)
    args = parser.parse_args()
    try:
        manifest = run(args)
    except S212ExecutionError as exc:
        print(f"S2.12 direct_llm refused: {exc}")
        return 2
    print("S2.12 direct_llm predictions locked before Gold evaluation")
    print(
        f"records=36 llm_calls={manifest['safety']['llm_api_calls']} "
        f"cost_usd={manifest['safety']['cost_usd']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
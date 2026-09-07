# -*- coding: utf-8 -*-
"""Finalize a completed S2.12 API arm (``direct_llm`` / ``sun_llm_fallback``).

The stage runners (``run_s2_12_direct_llm_v1`` / ``run_s2_12_sun_llm_fallback_v1``)
only capture raw responses into gitignored dev directories and append to the
hash-chained execution ledger; they never convert model output into evaluable
canonical attempts.  This finalizer is the offline, zero-network conversion +
publication step:

1. Verifies the preflight lock/report, rebuilds the locked payloads and checks
   that every locked arm payload is present in the live ledger of the last
   stage (a chained resume ledger contains the whole arm).  A partial arm is
   refused (exit 2) and never published.
2. Reads every raw ``<STAGE>.jsonl`` file from ``--raw-dir`` (one directory
   per stage, in execution order) and maps each raw response to its locked
   payload SHA (duplicate payloads are a fail-closed error).
3. Resolves the Gold-blind third-party source text locally (hash-bound, read
   only from the read-only corpus via the locked B0 resolver) and converts
   each response into a coordinate-only canonical attempt:
   * direct arm: ``direct_content_to_attempt``; missing/incident raw rows are
     explicit ``in_doubt`` rows (``raw_response_missing`` /
     ``transport_error:*`` / ``usage_missing:*``);
   * fallback arm: B0 diagnostic replay supplies the immutable text-bearing
     base record; the 27 locked repair plans are applied in
     ``execution_order`` using the exact shared H1 chain (envelope parse ->
     ``canonicalize_patch_coordinates`` -> ``apply_patch_envelope``).  Only
     accepted patches mutate the record; every plan emits a text-free event.
4. Publishes the 4-file prediction capsule atomically
   (predictions/telemetry/cost/manifest) ONLY if the output directory does
   not exist, and only after a recursive scan proves no raw-text or
   Gold/decision keys are present in any committed document.

ZERO network, ZERO LLM, never reads Gold.  Committed artifacts carry
coordinates/ids/hashes only; raw model content and third-party text stay in
the gitignored raw/dev directories.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]          # formal_experiment/
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.s2_12_execution import (  # noqa: E402
    EXPECTED_INPUT_SHA,
    INPUT,
    OUTPUT_DIRS,
    PREFLIGHT_LOCK,
    PREFLIGHT_REPORT,
    ExecutionLedger,
    S212ExecutionError,
    _json_bytes,
    _sha,
    atomic_publish_directory,
    per_call_cost,
    load_lock,
    load_report,
    rebuild_and_verify_payloads,
)
from bpc_hybrid.s2_12_response_convert import (  # noqa: E402
    ResponseConvertError,
    direct_content_to_attempt,
    fallback_envelope_from_content,
)
from bpc_hybrid.h1_span_canonicalizer import (  # noqa: E402
    STATUS_FAILED as CANONICALIZE_FAILED,
    canonicalize_patch_coordinates,
)
from run_s2_12_sun_rule_only_v1 import _resolve_records  # noqa: E402
from build_s2_12_api_preflight_v1 import _rerun_b0  # noqa: E402
from run_sun_llm_fallback import apply_patch_envelope, _rejection_codes  # noqa: E402

ARM_STAGES = {
    "direct_llm": ("D-CAL", "D-REST"),
    "sun_llm_fallback": ("F-1", "F-2", "F-3"),
}
FALLBACK_PLAN_CONFIG = ROOT / "configs/s2_12_fallback_trigger_plan_v1.json"
RULES_ONLY_PREDICTIONS = ROOT / "data/predictions/s2_12_sun_rule_only_v1/predictions.json"
DATASET_ID = "s2_11_barrientos_complex_corpus_36_v1"

# Official off-peak deepseek-v4-pro price snapshot used to re-derive real cost
# from the ledger usage at finalize time (cache split only when the provider
# reported it; otherwise all input tokens bill at the conservative cache-miss
# price).
OFFICIAL_OFFPEAK_PRICE = {
    "schema_version": "s2_12_price_snapshot@1.0.0",
    "currency": "USD",
    "input_cache_hit_per_million": 0.022,
    "input_cache_miss_per_million": 0.66,
    "output_per_million": 1.98,
}

# Raw-text keys that must never appear in committed capsule documents.
_FORBIDDEN_TEXT_KEYS = (
    "text", "source_text", "approved_text_en", "normalized", "marker_surface",
)
# Gold / decision keys that must never appear in committed capsule documents.
_FORBIDDEN_DECISION_KEYS = (
    "expected", "decision", "gold", "ground_truth", "oracle",
    "expected_violation", "human_correction", "adjudicat", "gold_rule",
)


class FinalizeFail(ValueError):
    """Fail-closed S2.12 arm-finalization error."""


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _strip_text_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_text_keys(child)
            for key, child in value.items()
            if key not in _FORBIDDEN_TEXT_KEYS
        }
    if isinstance(value, list):
        return [_strip_text_keys(item) for item in value]
    return value


def _json_hash(value: Any) -> str:
    payload = json.dumps(
        _strip_text_keys(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _scan_forbidden(name: str, value: Any) -> list[str]:
    """Return every forbidden text/Gold key path in one document (by key)."""
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_TEXT_KEYS:
                hits.append(f"{name}.{key}")
            elif key in _FORBIDDEN_DECISION_KEYS:
                hits.append(f"{name}.{key}")
            hits.extend(_scan_forbidden(f"{name}.{key}", child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            hits.extend(_scan_forbidden(f"{name}[{index}]", item))
    return hits


def _coord_span(span: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"start": span.get("start"), "end": span.get("end")}
    if isinstance(span.get("id"), str) and span["id"]:
        out["id"] = span["id"]
    return out


def capsule_record(
    record: Mapping[str, Any],
    method_name: str,
    method_variant: str | None = None,
) -> dict[str, Any]:
    """Strict coordinate-only canonical capsule record (mirrors the locked
    Rules-Only capsule row shape; only coordinates/ids survive)."""
    method: dict[str, Any] = {"name": method_name}
    if method_variant:
        method["method_variant"] = method_variant
    clauses: list[dict[str, Any]] = []
    for clause in record.get("clauses") or []:
        modality = clause.get("modality") or {}
        clause_span = clause.get("clause_span") or {}
        clauses.append({
            "clause_id": clause.get("clause_id"),
            "clause_span": {
                "start": clause_span.get("start"), "end": clause_span.get("end"),
            },
            "modality": {
                "label": modality.get("label"),
                "evidence": [
                    _coord_span(span) for span in modality.get("evidence") or []
                ],
            },
            "actors": [_coord_span(s) for s in clause.get("actors") or []],
            "actions": [_coord_span(s) for s in clause.get("actions") or []],
            "conditions": [_coord_span(s) for s in clause.get("conditions") or []],
            "constraints": [_coord_span(s) for s in clause.get("constraints") or []],
            "exceptions": [_coord_span(s) for s in clause.get("exceptions") or []],
            "actor_action_map": copy.deepcopy(clause.get("actor_action_map") or []),
            "order_relations": copy.deepcopy(clause.get("order_relations") or []),
        })
    return {
        "schema_version": "1.0.0",
        "sample_id": record.get("sample_id"),
        "source_id": record.get("source_id"),
        "clauses": clauses,
        "method": method,
        "validation": copy.deepcopy(record.get("validation") or {}),
    }


# ---------------------------------------------------------------------------
# Pure validation helpers (unit-testable without a B0 replay)
# ---------------------------------------------------------------------------


def coverage_errors(
    arm_rows: Sequence[Mapping[str, Any]],
    ledger: ExecutionLedger,
) -> list[str]:
    """Every locked arm payload missing from the ledger (partial arm)."""
    arm_payloads = {row["request_body_sha256"] for row in arm_rows}
    called = ledger.called_payloads()
    missing = sorted(arm_payloads - called)
    if missing:
        return [f"arm incomplete: {len(missing)} locked payloads not in the "
                f"ledger (first {missing[0][:12]}...)"]
    extra = sorted(called - arm_payloads)
    if extra:
        return [f"ledger contains {len(extra)} payloads outside the arm"]
    return []


def layout_errors(arm: str, raw_dirs: Sequence[Path]) -> list[str]:
    """Stage distribution vs raw-directory layout errors."""
    stages = ARM_STAGES[arm]
    errors: list[str] = []
    if len(raw_dirs) != len(stages):
        errors.append(
            f"raw directory count {len(raw_dirs)} != {arm} stage count "
            f"{len(stages)} ({'/'.join(stages)})"
        )
        return errors
    for stage in stages:
        present = [Path(d) for d in raw_dirs if (Path(d) / f"{stage}.jsonl").is_file()]
        if not present:
            errors.append(f"raw file missing for stage {stage} "
                          f"(expected <raw-dir>/{stage}.jsonl)")
        elif len(present) > 1:
            errors.append(f"raw file for stage {stage} present in multiple "
                          f"raw directories")
    return errors


def collect_stage_files(arm: str, raw_dirs: Sequence[Path]) -> dict[str, Path]:
    """Map each arm stage to its ``<stage>.jsonl`` file (strict)."""
    problems = layout_errors(arm, raw_dirs)
    if problems:
        raise FinalizeFail("; ".join(problems))
    return {stage: Path(d) / f"{stage}.jsonl"
            for stage in ARM_STAGES[arm]
            for d in raw_dirs if (Path(d) / f"{stage}.jsonl").is_file()}


def load_raw_payload_map(
    arm_rows: Sequence[Mapping[str, Any]],
    stage_files: Mapping[str, Path],
) -> tuple[dict[str, Mapping[str, Any]], list[str]]:
    """Read all raw rows; return ``{payload_sha: raw_row}`` + row problems."""
    payload_to_row: dict[str, Mapping[str, Any]] = {}
    problems: list[str] = []
    arm_payloads = {row["request_body_sha256"] for row in arm_rows}
    for stage, path in stage_files.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                problems.append(f"{stage}:{number} invalid JSONL: {exc}")
                continue
            payload = row.get("payload_sha")
            if not isinstance(payload, str) or payload not in arm_payloads:
                problems.append(f"{stage}:{number} payload not in the arm")
                continue
            if payload in payload_to_row:
                problems.append(f"{stage}:{number} duplicate payload {payload[:12]}...")
                continue
            payload_to_row[payload] = row
    return payload_to_row, problems


def ledger_stage_errors(arm: str, ledger: ExecutionLedger) -> list[str]:
    """Verify the ledger has every expected stage covered by its records."""
    stages = ARM_STAGES[arm]
    per_stage: dict[str, int] = {}
    for rec in ledger.records:
        stage_id = rec.get("stage_id")
        if stage_id not in stages:
            return [f"ledger contains unexpected stage {stage_id!r}"]
        per_stage[stage_id] = per_stage.get(stage_id, 0) + 1
    missing = [s for s in stages if not per_stage.get(s)]
    if missing:
        return [f"ledger missing records for stage(s): {', '.join(missing)}"]
    return []


# ---------------------------------------------------------------------------
# Attempt construction
# ---------------------------------------------------------------------------


def _truncate(value: str, limit: int = 160) -> str:
    value = (value or "").strip()
    return value if len(value) <= limit else value[:limit] + "..."


def direct_attempt_from_raw(
    arm_row: Mapping[str, Any],
    raw: Mapping[str, Any] | None,
    text_by_formal: Mapping[str, str],
) -> dict[str, Any]:
    sample_id = str(arm_row["sample_id"])
    if raw is None:
        return {
            "sample_id": sample_id, "request_status": "in_doubt",
            "record": None, "error_category": "raw_response_missing",
        }
    decode_status = str(raw.get("decode_status") or "")
    if decode_status.startswith("transport_error") or \
            decode_status.startswith("usage_missing"):
        return {
            "sample_id": sample_id, "request_status": "in_doubt",
            "record": None, "error_category": _truncate(decode_status),
        }
    if decode_status != "ok_message_content":
        return {
            "sample_id": sample_id, "request_status": "in_doubt",
            "record": None, "error_category": _truncate(
                f"decode_status:{decode_status}"),
        }
    content = raw.get("content")
    if not isinstance(content, str) or not content:
        return {
            "sample_id": sample_id, "request_status": "in_doubt",
            "record": None, "error_category": "decode_content_missing",
        }
    if raw.get("content_sha256") != _sha_text(content):
        return {
            "sample_id": sample_id, "request_status": "in_doubt",
            "record": None, "error_category": "decode_content_hash_mismatch",
        }
    source_text = text_by_formal.get(sample_id)
    if not source_text:
        raise FinalizeFail(f"no resolved source text for {sample_id}")
    attempt = direct_content_to_attempt(sample_id, content, source_text)
    if attempt.get("record"):
        attempt = {
            **attempt,
            "record": capsule_record(attempt["record"], "direct_llm"),
        }
    return attempt


@dataclass
class _PlanAdapter:
    """Lightweight RepairPlan-compatible adapter bound to the frozen config."""
    sample_id: str
    clause_id: str
    clause_index: int
    repair_fields: tuple[str, ...]
    reasons: tuple[str, ...]
    risk_score: int
    execution_order: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "clause_id": self.clause_id,
            "clause_index": self.clause_index,
            "repair_fields": list(self.repair_fields),
            "reasons": list(self.reasons),
            "risk_score": self.risk_score,
            "execution_order": self.execution_order,
        }


def _rejection_codes_for(reasons: Sequence[str]) -> list[str]:
    codes = list(_rejection_codes(list(reasons)))
    return codes or (["other"] if reasons else [])


def fallback_event_for_plan(
    plan: Mapping[str, Any],
    record: dict[str, Any],
    source_text: str,
    raw: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Apply one repair plan to ``record``; return ``(event, updated_record)``.

    ``updated_record`` is the patched deep copy when the patch was accepted,
    otherwise None (the caller keeps its current record).
    """
    adapter = _PlanAdapter(
        sample_id=str(plan["sample_id"]),
        clause_id=str(plan["clause_id"]),
        clause_index=int(plan["clause_index"]),
        repair_fields=tuple(plan["repair_fields"]),
        reasons=tuple(plan["reasons"]),
        risk_score=int(plan["risk_score"]),
        execution_order=int(plan["execution_order"]),
    )
    base = {
        "execution_order": adapter.execution_order,
        "sample_id": adapter.sample_id,
        "clause_id": adapter.clause_id,
        "repair_fields": list(adapter.repair_fields),
        "patch_accepted": False,
        "rejection_reasons": [],
        "field_diff_summary": [],
    }
    if raw is None:
        return {**base, "status": "unresolved_raw_missing"}, None
    decode_status = str(raw.get("decode_status") or "")
    if decode_status.startswith("transport_error") or \
            decode_status.startswith("usage_missing"):
        return {**base, "status": "unresolved_transport_incident",
                "rejection_reasons": [_truncate(decode_status, 120)]}, None
    content = raw.get("content")
    if not isinstance(content, str) or not content:
        return {**base, "status": "unresolved_malformed_envelope",
                "rejection_reasons": ["empty_response_content"]}, None
    try:
        envelope = fallback_envelope_from_content(content)
    except ResponseConvertError as exc:
        return {**base, "status": "unresolved_malformed_envelope",
                "rejection_reasons": ["patch_envelope_parse_failed"]}, None
    clause = record["clauses"][adapter.clause_index]
    if clause.get("clause_id") != adapter.clause_id:
        raise FinalizeFail(
            f"plan clause mismatch for {adapter.sample_id}: "
            f"{clause.get('clause_id')} != {adapter.clause_id}")
    canonicalized, audit = canonicalize_patch_coordinates(
        envelope, source_text, clause.get("clause_span"))
    if audit.get("status") == CANONICALIZE_FAILED:
        return {
            **base, "status": "rejected",
            "rejection_reasons": list(audit.get("reason_codes") or []),
        }, None
    merged, merge_event = apply_patch_envelope(record, canonicalized, adapter)
    event = {**base}
    if merge_event.get("patch_accepted"):
        event["status"] = "accepted"
        event["patch_accepted"] = True
        event["field_diff_summary"] = [
            {
                "field": item["field"],
                "before_sha256": _json_hash(item["before"]),
                "after_sha256": _json_hash(item["after"]),
            }
            for item in merge_event.get("field_diffs") or []
        ]
        return event, merged
    event["status"] = "rejected"
    event["rejection_reasons"] = _rejection_codes_for(
        merge_event.get("rejection_reasons") or [])
    return event, None


def _rel(path: Path) -> str:
    try:
        return os.path.relpath(path, ROOT).replace("\\", "/")
    except ValueError:
        return str(path)


def _count_rows(rows: Sequence[Mapping[str, Any]]) -> tuple[int, int, int]:
    ok = in_doubt = failed = 0
    for row in rows:
        if row["request_status"] == "in_doubt":
            in_doubt += 1
        elif row["request_status"] == "ok" and row.get("record") is not None \
                and row.get("error_category") is None:
            ok += 1
        else:
            failed += 1
    return ok, in_doubt, failed


def _cost_from_ledger(ledger: ExecutionLedger,
                      price: Mapping[str, Any]) -> dict[str, Any]:
    success_calls = 0
    input_tokens = output_tokens = hit_tokens = miss_tokens = 0
    cost = 0.0
    for rec in ledger.records:
        usage = rec.get("usage") or {}
        if not usage:
            continue
        success_calls += 1
        info = per_call_cost(usage, price)
        input_tokens += info["input_tokens"]
        output_tokens += info["output_tokens"]
        hit_tokens += info["cache_hit_tokens"]
        miss_tokens += info["cache_miss_tokens"]
        cost += info["cost_usd"]
    cumulative = 0.0
    for rec in ledger.records:
        value = rec.get("cumulative_cost_usd")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            cumulative = float(value)
    return {
        "success_calls": success_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_hit_tokens": hit_tokens,
        "cache_miss_tokens": miss_tokens,
        "cost_usd": round(cost, 8),
        "ledger_cumulative_cost_usd": round(cumulative, 8),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    arm = args.arm
    if arm not in ARM_STAGES:
        raise FinalizeFail(f"unknown arm {arm!r}")
    runtime_home = Path(args.runtime_home)

    lock = load_lock()
    report = load_report()
    rows_by_arm = rebuild_and_verify_payloads(lock, report, runtime_home)
    arm_rows = report["arms"][arm]["calls"]
    if len(arm_rows) != len(rows_by_arm[arm]):
        raise FinalizeFail(f"arm row count drift: {len(arm_rows)}")

    ledger = ExecutionLedger(Path(args.ledger))
    errors: list[str] = []
    errors.extend(coverage_errors(arm_rows, ledger))
    errors.extend(ledger_stage_errors(arm, ledger))
    raw_dirs = [Path(d) for d in args.raw_dir]
    stage_files = {}
    try:
        stage_files = collect_stage_files(arm, raw_dirs)
    except FinalizeFail as exc:
        errors.append(str(exc))
    if errors:
        raise FinalizeFail("; ".join(errors))
    raw_map, raw_problems = load_raw_payload_map(arm_rows, stage_files)
    if raw_problems:
        raise FinalizeFail("raw response problems: " + "; ".join(raw_problems))

    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    source_records, runtime_to_formal = _resolve_records(input_doc)
    by_runtime = {rec["sample_id"]: rec for rec in source_records}
    text_by_formal = {
        formal_id: by_runtime[runtime_id]["approved_text_en"]
        for runtime_id, formal_id in runtime_to_formal.items()
    }
    if len(text_by_formal) != 36:
        raise FinalizeFail("expected 36 resolved source texts")

    plan_events: list[dict[str, Any]] = []
    if arm == "direct_llm":
        rows: list[dict[str, Any]] = []
        for arm_row in arm_rows:
            raw = raw_map.get(arm_row["request_body_sha256"])
            rows.append(direct_attempt_from_raw(arm_row, raw, text_by_formal))
    else:
        adapted, _batch = _rerun_b0(runtime_home)
        records_by_id: dict[str, dict[str, Any]] = {}
        for attempt in adapted:
            sample_id = str(attempt["sample_id"])
            if not isinstance(attempt.get("record"), dict):
                raise FinalizeFail(f"B0 attempt {sample_id} has no record")
            records_by_id[sample_id] = copy.deepcopy(attempt["record"])
        plan_doc = json.loads(FALLBACK_PLAN_CONFIG.read_text(encoding="utf-8"))
        plans = sorted(
            plan_doc["selected_plans"], key=lambda p: int(p["execution_order"]))
        if len(plans) != len(arm_rows):
            raise FinalizeFail("fallback plan count != locked call count")
        arm_payload_by_sha = {row["request_body_sha256"]: row
                              for row in arm_rows}
        for plan in plans:
            sample_id = str(plan["sample_id"])
            record = records_by_id.get(sample_id)
            if record is None:
                raise FinalizeFail(f"plan sample {sample_id} not in B0 replay")
            if int(plan["clause_index"]) >= len(record.get("clauses") or []):
                raise FinalizeFail(f"plan clause index out of bounds: {sample_id}")
            payload_sha = str(plan["request_body_sha256"])
            if payload_sha not in arm_payload_by_sha:
                raise FinalizeFail(
                    f"plan {plan['execution_order']} payload not in the locked "
                    f"arm rows (config drift): {payload_sha[:12]}...")
            raw = raw_map.get(payload_sha)
            event, merged = fallback_event_for_plan(
                plan, record, text_by_formal[sample_id], raw)
            plan_events.append(event)
            if merged is not None:
                records_by_id[sample_id] = merged
        ordered_ids = [row["sample_id"] for row in json.loads(
            RULES_ONLY_PREDICTIONS.read_text(encoding="utf-8"))["records"]]
        if sorted(ordered_ids) != sorted(records_by_id):
            raise FinalizeFail("B0 replay sample set != locked capsule set")
        rows = [
            {
                "sample_id": sample_id,
                "request_status": "ok",
                "record": capsule_record(
                    records_by_id[sample_id], "sun_llm_fallback",
                    method_variant="b0_enhanced_v10a"),
                "error_category": None,
            }
            for sample_id in ordered_ids
        ]

    ok_rows, in_doubt, failed = _count_rows(rows)
    capsule_status = "complete" if (in_doubt == 0 and failed == 0) \
        else "complete_with_explicit_failures"

    predictions_doc = {
        "schema_version": f"s2_12_{arm}_predictions@1.0.0",
        "dataset_id": DATASET_ID,
        "method_id": arm,
        "arm": arm,
        "record_count": len(rows),
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": rows,
    }
    telemetry_doc: dict[str, Any] = {
        "schema_version": f"s2_12_{arm}_telemetry@1.0.0",
        "status": capsule_status,
        "arm": arm,
        "record_count": len(rows),
        "ok_prediction_rows": ok_rows,
        "in_doubt": in_doubt,
        "failed": failed,
        "raw_dirs": [_rel(Path(d)) for d in raw_dirs],
        "ledger": {
            "path": _rel(Path(args.ledger)),
            "records": len(ledger.records),
            "last_hash": ledger.last_hash,
        },
        "transport": "real_authorized",
        "raw_text_committed": False,
    }
    if arm == "sun_llm_fallback":
        telemetry_doc["plan_events"] = plan_events

    cost_info = _cost_from_ledger(ledger, OFFICIAL_OFFPEAK_PRICE)
    cost_doc = {
        "schema_version": f"s2_12_{arm}_cost@1.0.0",
        "arm": arm,
        "llm_calls": cost_info["success_calls"],
        "llm_api_calls": cost_info["success_calls"],
        "network_calls": cost_info["success_calls"],
        "input_tokens_billed": cost_info["input_tokens"],
        "output_tokens_billed": cost_info["output_tokens"],
        "cache_hit_tokens_billed": cost_info["cache_hit_tokens"],
        "cache_miss_tokens_billed": cost_info["cache_miss_tokens"],
        "actual_cost_usd": cost_info["cost_usd"],
        "ledger_cumulative_cost_usd": cost_info["ledger_cumulative_cost_usd"],
        "billing": {
            "basis": "ledger_response_usage_recomputed_at_finalize",
            "cache_split": ("provider_usage" if cost_info["cache_hit_tokens"]
                            or cost_info["cache_miss_tokens"]
                            else "conservative_all_input_cache_miss"),
            "official_off_peak_per_million_tokens": {
                "input_cache_hit": OFFICIAL_OFFPEAK_PRICE["input_cache_hit_per_million"],
                "input_cache_miss": OFFICIAL_OFFPEAK_PRICE["input_cache_miss_per_million"],
                "output": OFFICIAL_OFFPEAK_PRICE["output_per_million"],
                "currency": "USD",
            },
            "note": ("when the provider usage does not split prompt cache "
                     "hit/miss, ALL input tokens are billed at the "
                     "conservative cache-miss price"),
        },
        "raw_text_committed": False,
    }

    files = {
        "predictions.json": _json_bytes(predictions_doc),
        "telemetry.json": _json_bytes(telemetry_doc),
        "cost.json": _json_bytes(cost_doc),
    }
    manifest = {
        "schema_version": f"s2_12_{arm}_manifest@1.0.0",
        "status": "predictions_locked_before_gold_evaluation",
        "capsule_status": capsule_status,
        "arm": arm,
        "method_id": arm,
        "dataset_id": DATASET_ID,
        "record_count": len(rows),
        "input_binding": {
            "path": "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "sha256": EXPECTED_INPUT_SHA,
            "records": 36,
            "raw_text_committed": False,
        },
        "preflight_bindings": {
            "lock": {
                "path": "configs/s2_12_api_arms_preflight_v1.json",
                "sha256": _sha(PREFLIGHT_LOCK),
            },
            "report": {
                "path": "outputs/reports/s2_12_api_preflight_v1.json",
                "sha256": _sha(PREFLIGHT_REPORT),
            },
        },
        "gold_isolation": {
            "gold_read_by_runner": False,
            "predictions_locked_before_evaluation": True,
            "post_result_tuning_forbidden": True,
        },
        "raw_dirs": [_rel(Path(d)) for d in raw_dirs],
        "ledger": {
            "path": _rel(Path(args.ledger)),
            "records": len(ledger.records),
            "last_hash": ledger.last_hash,
        },
        "artifacts": {
            name: {"sha256": hashlib.sha256(data).hexdigest(),
                   "byte_size": len(data)}
            for name, data in files.items()
        },
        "safety": {
            "llm_api_calls": cost_info["success_calls"],
            "network_calls": cost_info["success_calls"],
            "cost_usd": cost_info["cost_usd"],
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce": {
            "arm": arm,
            "summary": ("run every locked stage with the authorized real "
                        "transport and raw capture, chain-resume into the "
                        "final stage ledger, then finalize"),
            "stage_commands": [
                "python formal_experiment/scripts/"
                f"run_s2_12_{arm}_v1.py --transport real --allow-llm "
                "--auth-file <auth> "
                f"--stage-id {stage} --raw-dir <raw-dir-{stage}>"
                + (" --resume-from-ledger <prev-ledger>" if index else "")
                for index, stage in enumerate(ARM_STAGES[arm])
            ],
            "finalize_command": (
                "python formal_experiment/scripts/finalize_s2_12_arm_v1.py "
                f"--arm {arm} "
                + " ".join(f"--raw-dir <raw-{stage}>" for stage in ARM_STAGES[arm])
                + f" --ledger <live-ledger> --output-dir data/predictions/"
                  f"s2_12_{arm}_v1"),
        },
    }
    files["manifest.json"] = _json_bytes(manifest)

    all_docs = {
        "predictions.json": predictions_doc,
        "telemetry.json": telemetry_doc,
        "cost.json": cost_doc,
        "manifest.json": manifest,
    }
    forbidden = [
        hit for name, doc in all_docs.items()
        for hit in _scan_forbidden(name, doc)
    ]
    if forbidden:
        raise FinalizeFail(
            "forbidden text/Gold keys in committed docs: " + ", ".join(forbidden))

    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists():
        raise FinalizeFail(f"refusing to overwrite existing run: {output_dir}")
    atomic_publish_directory(output_dir, files)
    return {
        "arm": arm,
        "capsule_status": capsule_status,
        "ok_rows": ok_rows,
        "in_doubt": in_doubt,
        "failed": failed,
        "cost_usd": cost_info["cost_usd"],
        "record_count": len(rows),
        "output_dir": output_dir,
        "manifest": manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("direct_llm", "sun_llm_fallback"),
                        required=True)
    parser.add_argument("--runtime-home", type=Path,
                        default=Path("D:/environment/stanford-corenlp-4.5.10"))
    parser.add_argument("--raw-dir", type=Path, action="append", default=[],
                        help="Gitignored raw-response directory per stage, in "
                             "execution order (D-CAL,D-REST or F-1,F-2,F-3).")
    parser.add_argument("--ledger", type=Path, required=True,
                        help="Live execution ledger of the final stage "
                             "(contains the whole chained arm).")
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    try:
        if args.output_dir is None:
            args.output_dir = OUTPUT_DIRS[args.arm]
        result = run(args)
    except (FinalizeFail, S212ExecutionError, OSError) as exc:
        print(f"S2.12 finalize refused: {exc}")
        return 2
    print(f"S2.12 finalize arm={result['arm']} "
          f"capsule_status={result['capsule_status']} "
          f"records={result['record_count']} ok={result['ok_rows']} "
          f"in_doubt={result['in_doubt']} failed={result['failed']} "
          f"cost_usd={result['cost_usd']}")
    print(f"published={result['output_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

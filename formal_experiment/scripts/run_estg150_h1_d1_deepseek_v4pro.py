"""Run the authorized one-repeat DeepSeek V4 Pro H1/D1 development comparison.

The runner is resumable and failure preserving. It never reads ``.env`` and
uses only ``DEEPSEEK_API_KEY`` from the process environment. Gold is loaded
only after requests finish, for the shared Sun literal-overlap evaluation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import requests


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development import (  # noqa: E402
    build_canonical_gold_records,
    sha256_file,
)
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from bpc_hybrid.stage2_sun_table8_compatible import (  # noqa: E402
    evaluate_sun_table8_literal_overlap,
)
from bpc_hybrid.sun_style.d1_direct import render_d1_request, render_few_shot_block  # noqa: E402
from bpc_hybrid.sun_style.h1_selective import (  # noqa: E402
    apply_repair_patch,
    detect_repair_plan,
    finalize_h1_record,
    render_h1_request,
)


CONFIG_PATH = ROOT / "configs" / "models" / "estg150_h1_d1_deepseek_v4pro_live_v1.json"
CANONICAL_CLAUSE_KEYS = (
    "clause_id",
    "clause_span",
    "modality",
    "actors",
    "actions",
    "conditions",
    "constraints",
    "exceptions",
    "actor_action_map",
    "order_relations",
)
SPAN_FIELDS = ("actors", "actions", "conditions", "constraints", "exceptions")
WRITE_LOCK = threading.Lock()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    line = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
    with WRITE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line)
            stream.flush()


def _write_json(path: Path, value: Any, *, replace: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_suffix(path.suffix + ".tmp")
    with target.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    if path.exists() and not replace:
        target.unlink()
        raise FileExistsError(f"refusing to overwrite {path}")
    target.replace(path)


def _load_jsonl_by_id(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return result
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        sample_id = value.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in result:
            raise RuntimeError(f"invalid or duplicate sample_id in {path}:{number}")
        result[sample_id] = value
    return result


def _clean_b0_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Remove development diagnostics while preserving B0 semantic values."""

    record = {
        "schema_version": raw.get("schema_version"),
        "sample_id": raw.get("sample_id"),
        "source_id": raw.get("source_id"),
        "source_text": raw.get("source_text"),
        "clauses": [],
        "method": {
            "name": "sun_rule_only",
            "schema_source": "stage2_prediction.schema.json@1.0.0",
        },
        "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
    }
    if isinstance(raw.get("unsupported_or_ambiguous"), list):
        record["unsupported_or_ambiguous"] = copy.deepcopy(raw["unsupported_or_ambiguous"])
    for raw_clause in raw.get("clauses", []):
        if not isinstance(raw_clause, Mapping):
            continue
        clause = {key: copy.deepcopy(raw_clause.get(key)) for key in CANONICAL_CLAUSE_KEYS}
        modality = clause.get("modality")
        if isinstance(modality, Mapping):
            clause["modality"] = {
                "label": modality.get("label"),
                "evidence": copy.deepcopy(modality.get("evidence", [])),
            }
        record["clauses"].append(clause)
    report = validate_canonical(record)
    record["validation"] = {
        "schema_valid": report.schema_valid,
        "cross_field_valid": report.cross_field_valid,
        "errors": list(report.errors),
    }
    if not (report.schema_valid and report.cross_field_valid):
        raise RuntimeError(f"cleaned B0 is not canonical: {record['sample_id']}: {report.errors[:3]}")
    return record


def _load_b0(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    attempts = _json(ROOT / config["inputs"]["b0_attempts"])
    if not isinstance(attempts, list) or len(attempts) != 150:
        raise RuntimeError("B0 input must contain exactly 150 attempts")
    records = [_clean_b0_record(item["record"]) for item in attempts]
    if len({item["sample_id"] for item in records}) != 150:
        raise RuntimeError("B0 sample membership is not unique")
    return records


def _parse_json_loose(content: str) -> tuple[Any | None, list[str]]:
    repairs: list[str] = []
    value = content.lstrip("\ufeff").strip()
    if value != content.strip():
        repairs.append("stripped_utf8_bom")
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", value, flags=re.DOTALL | re.IGNORECASE)
    if match:
        value = match.group(1).strip()
        repairs.append("stripped_markdown_code_fence")
    if value and value[0] not in "{[":
        positions = [pos for pos in (value.find("{"), value.find("[")) if pos >= 0]
        if positions:
            value = value[min(positions):]
            repairs.append("stripped_non_json_prefix")
    if value and value[-1] not in "}]":
        end = max(value.rfind("}"), value.rfind("]"))
        if end >= 0:
            value = value[: end + 1]
            repairs.append("stripped_non_json_suffix")
    try:
        return json.loads(value), repairs
    except (TypeError, json.JSONDecodeError):
        return None, repairs + ["json_parse_failed"]


def _repair_span(span: Any, source_text: str, notes: list[str], path: str) -> Any:
    if not isinstance(span, dict):
        return span
    text = span.get("text")
    start = span.get("start")
    end = span.get("end")
    if not isinstance(text, str) or not text:
        return span
    if isinstance(start, int) and isinstance(end, int) and source_text[start:end] == text:
        return span
    positions: list[int] = []
    offset = 0
    while True:
        found = source_text.find(text, offset)
        if found < 0:
            break
        positions.append(found)
        offset = found + 1
    if not positions:
        return span
    hint = start if isinstance(start, int) else positions[0]
    chosen = min(positions, key=lambda value: (abs(value - hint), value))
    fixed = copy.deepcopy(span)
    fixed["start"] = chosen
    fixed["end"] = chosen + len(text)
    notes.append(f"coordinate_repaired:{path}")
    return fixed


def _repair_record_coordinates(record: dict[str, Any], source_text: str) -> list[str]:
    notes: list[str] = []
    for ci, clause in enumerate(record.get("clauses", [])):
        if not isinstance(clause, dict):
            continue
        clause["clause_span"] = _repair_span(
            clause.get("clause_span"), source_text, notes, f"clauses[{ci}].clause_span"
        )
        modality = clause.get("modality")
        if isinstance(modality, dict) and isinstance(modality.get("evidence"), list):
            modality["evidence"] = [
                _repair_span(span, source_text, notes, f"clauses[{ci}].modality.evidence[{si}]")
                for si, span in enumerate(modality["evidence"])
            ]
        for field in SPAN_FIELDS:
            if isinstance(clause.get(field), list):
                clause[field] = [
                    _repair_span(span, source_text, notes, f"clauses[{ci}].{field}[{si}]")
                    for si, span in enumerate(clause[field])
                ]
        for ri, relation in enumerate(clause.get("order_relations", [])):
            if isinstance(relation, dict) and isinstance(relation.get("evidence"), list):
                relation["evidence"] = [
                    _repair_span(span, source_text, notes, f"clauses[{ci}].order_relations[{ri}].evidence[{si}]")
                    for si, span in enumerate(relation["evidence"])
                ]
    return notes


def _call_api(
    *,
    messages: list[dict[str, str]],
    runtime_config: Mapping[str, Any],
    api_key: str,
) -> dict[str, Any]:
    body = {
        "model": runtime_config["model"],
        "messages": messages,
        "temperature": runtime_config["temperature"],
        "top_p": runtime_config["top_p"],
        "max_tokens": runtime_config["max_tokens"],
        "response_format": {"type": runtime_config["response_format"]},
        "thinking": {"type": runtime_config["thinking_mode"]},
    }
    started = time.perf_counter()
    try:
        response = requests.post(
            runtime_config["endpoint"],
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=runtime_config["timeout_seconds"],
        )
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            return {
                "ok": False,
                "error_category": f"http_{response.status_code}",
                "latency_ms": latency_ms,
                "request_sha256": _sha256_text(json.dumps(body, ensure_ascii=False, sort_keys=True)),
            }
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
        return {
            "ok": True,
            "content": content,
            "response_sha256": _sha256_text(content),
            "latency_ms": latency_ms,
            "prompt_tokens": int(usage.get("prompt_tokens") or 0),
            "completion_tokens": int(usage.get("completion_tokens") or 0),
            "total_tokens": int(usage.get("total_tokens") or 0),
            "request_sha256": _sha256_text(json.dumps(body, ensure_ascii=False, sort_keys=True)),
        }
    except requests.Timeout:
        return {"ok": False, "error_category": "timeout", "latency_ms": (time.perf_counter() - started) * 1000}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return {"ok": False, "error_category": "provider_or_response_error", "latency_ms": (time.perf_counter() - started) * 1000}


def _runtime(call: Mapping[str, Any], performed: bool) -> dict[str, Any]:
    prompt = int(call.get("prompt_tokens") or 0)
    completion = int(call.get("completion_tokens") or 0)
    total = int(call.get("total_tokens") or (prompt + completion))
    if total != prompt + completion:
        total = prompt + completion
    return {
        "llm_call_performed": performed,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
        "estimated_cost_usd": 0.0,
        "latency_ms": float(call.get("latency_ms") or 0.0),
    }


def _d1_job(
    row: Mapping[str, Any],
    prompt: Any,
    protocol_config: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    api_key: str,
) -> dict[str, Any]:
    rendered = render_d1_request(row, prompt, protocol_config)
    call = _call_api(
        messages=[
            {"role": "system", "content": rendered["system_prompt"]},
            {"role": "user", "content": rendered["user_prompt"]},
        ],
        runtime_config=runtime_config,
        api_key=api_key,
    )
    base = {
        "sample_id": row["sample_id"],
        "repeat_index": 1,
        "model": runtime_config["model"],
        "thinking_mode": runtime_config["thinking_mode"],
        "request_sha256": call.get("request_sha256"),
        "runtime": _runtime(call, True),
        "record": None,
    }
    if not call.get("ok"):
        return {**base, "request_status": "api_error", "error_category": call["error_category"], "response_sha256": None}
    parsed, repairs = _parse_json_loose(call["content"])
    if not isinstance(parsed, dict):
        return {
            **base,
            "request_status": "ok",
            "error_category": "non_object_or_non_json",
            "response_sha256": call["response_sha256"],
            "postprocess": repairs,
        }
    record = copy.deepcopy(parsed)
    identity_changes = []
    for key in ("sample_id", "source_id", "source_text"):
        if record.get(key) != row[key]:
            record[key] = row[key]
            identity_changes.append(f"input_identity_restored:{key}")
    if record.get("method") != {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"}:
        record["method"] = {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"}
        identity_changes.append("method_identity_restored")
    coordinate_repairs = _repair_record_coordinates(record, row["source_text"])
    try:
        report = validate_canonical(record)
        validation = {
            "schema_valid": report.schema_valid,
            "cross_field_valid": report.cross_field_valid,
            "errors": list(report.errors),
        }
    except (KeyError, TypeError, ValueError) as exc:
        validation = {
            "schema_valid": False,
            "cross_field_valid": False,
            "errors": [f"validator_exception:{type(exc).__name__}"],
        }
    return {
        **base,
        "request_status": "ok",
        "record": record,
        "error_category": None if validation["schema_valid"] and validation["cross_field_valid"] else "canonical_validation_warning",
        "response_sha256": call["response_sha256"],
        "postprocess": repairs + identity_changes + coordinate_repairs,
        "canonical_validation": validation,
    }


def _run_d1(
    records: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    api_key: str,
    workers: int,
    limit: int | None,
) -> None:
    output = ROOT / config["output"] / "d1_responses.jsonl"
    completed = _load_jsonl_by_id(output)
    rows = [
        {
            "sample_id": record["sample_id"],
            "source_id": record["source_id"],
            "source_text": record["source_text"],
            "data_role": "development_input",
        }
        for record in records
    ]
    pending = [row for row in rows if row["sample_id"] not in completed]
    if limit is not None:
        pending = pending[: max(0, limit - len(completed))]
    if len(completed) + len(pending) > config["budget"]["d1_hard_max_calls"]:
        raise RuntimeError("D1 hard call budget would be exceeded")
    prompt = load_prompt("direct_llm_sun_record_prompt")
    protocol_config = _json(ROOT / config["methods"]["D1"]["protocol_config"])
    runtime_config = config["shared_runtime"]
    done = len(completed)
    print(f"D1 resume={done}, pending={len(pending)}, workers={workers}", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_d1_job, row, prompt, protocol_config, runtime_config, api_key): row["sample_id"]
            for row in pending
        }
        for future in as_completed(futures):
            result = future.result()
            _append_jsonl(output, result)
            done += 1
            if done % 10 == 0 or done == len(rows) or len(pending) <= 3:
                print(f"D1 completed {done}/150", flush=True)


def _d1_recovery_batch_job(
    batch_id: int,
    rows: list[dict[str, Any]],
    prompt: Any,
    runtime_config: Mapping[str, Any],
    api_key: str,
) -> dict[str, Any]:
    few_shot = render_few_shot_block(prompt)
    inputs = "\n\n".join(
        f"TARGET {index}\nsample_id: {row['sample_id']}\nsource_id: {row['source_id']}\nsource_text:\n{row['source_text']}"
        for index, row in enumerate(rows, start=1)
    )
    user = (
        "Input mode: target_text_only. Process every target independently under the same "
        "Stage 2 six-element contract. Return only one JSON object with the top-level key "
        '"results"; results maps each supplied sample_id to its complete canonical JSON record. '
        "Do not omit a target. Each nested record uses method.name=direct_llm.\n\n"
        + inputs
        + "\n\nThe same four synthetic contract examples follow:\n\n"
        + few_shot
    )
    system = (
        prompt.system_prompt
        + "\n\nTRANSPORT RECOVERY WRAPPER: For this request only, the outer object is "
        '{"results":{"<sample_id>":<canonical record>}}. The exact canonical schema applies '
        "independently to every nested record; the wrapper is not a semantic schema change."
    )
    call = _call_api(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        runtime_config=runtime_config,
        api_key=api_key,
    )
    sample_results: list[dict[str, Any]] = []
    parsed: Any = None
    cleanup: list[str] = []
    if call.get("ok"):
        parsed, cleanup = _parse_json_loose(call["content"])
    bodies = parsed.get("results") if isinstance(parsed, dict) else None
    for row in rows:
        base = {
            "sample_id": row["sample_id"],
            "repeat_index": 1,
            "model": runtime_config["model"],
            "thinking_mode": runtime_config["thinking_mode"],
            "request_sha256": call.get("request_sha256"),
            "response_sha256": call.get("response_sha256"),
            "recovery_batch_id": batch_id,
            "runtime": _runtime(call, True),
            "record": None,
        }
        if not call.get("ok"):
            sample_results.append({**base, "request_status": "api_error", "error_category": call["error_category"]})
            continue
        body = bodies.get(row["sample_id"]) if isinstance(bodies, dict) else None
        if not isinstance(body, dict):
            sample_results.append(
                {
                    **base,
                    "request_status": "ok",
                    "error_category": "missing_or_non_object_batch_result",
                    "postprocess": cleanup,
                }
            )
            continue
        record = copy.deepcopy(body)
        notes = list(cleanup)
        for key in ("sample_id", "source_id", "source_text"):
            if record.get(key) != row[key]:
                record[key] = row[key]
                notes.append(f"input_identity_restored:{key}")
        expected_method = {"name": "direct_llm", "schema_source": "stage2_prediction.schema.json@1.0.0"}
        if record.get("method") != expected_method:
            record["method"] = expected_method
            notes.append("method_identity_restored")
        notes.extend(_repair_record_coordinates(record, row["source_text"]))
        try:
            report = validate_canonical(record)
            validation = {
                "schema_valid": report.schema_valid,
                "cross_field_valid": report.cross_field_valid,
                "errors": list(report.errors),
            }
        except (KeyError, TypeError, ValueError) as exc:
            validation = {
                "schema_valid": False,
                "cross_field_valid": False,
                "errors": [f"validator_exception:{type(exc).__name__}"],
            }
        sample_results.append(
            {
                **base,
                "request_status": "ok",
                "record": record,
                "error_category": None if validation["schema_valid"] and validation["cross_field_valid"] else "canonical_validation_warning",
                "postprocess": notes,
                "canonical_validation": validation,
            }
        )
    return {
        "batch_id": batch_id,
        "sample_ids": [row["sample_id"] for row in rows],
        "called_at_utc": _utc(),
        "model": runtime_config["model"],
        "thinking_mode": runtime_config["thinking_mode"],
        "request_status": "ok" if call.get("ok") else "api_error",
        "error_category": call.get("error_category"),
        "request_sha256": call.get("request_sha256"),
        "response_sha256": call.get("response_sha256"),
        "runtime": _runtime(call, True),
        "sample_results": sample_results,
    }


def _run_d1_recovery(
    records: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    api_key: str,
    workers: int,
) -> None:
    output_root = ROOT / config["output"]
    responses_path = output_root / "d1_responses.jsonl"
    receipts_path = output_root / "d1_recovery_batches.jsonl"
    incident_path = output_root / "d1_primary_call_incident.json"
    completed = _load_jsonl_by_id(responses_path)
    receipts: dict[int, dict[str, Any]] = {}
    if receipts_path.exists():
        for line in receipts_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                receipt = json.loads(line)
                receipts[int(receipt["batch_id"])] = receipt
        for receipt in receipts.values():
            for result in receipt.get("sample_results", []):
                if result["sample_id"] not in completed:
                    _append_jsonl(responses_path, result)
                    completed[result["sample_id"]] = result
    missing_records = [record for record in records if record["sample_id"] not in completed]
    recovery = config["methods"]["D1"]["incident_recovery"]
    batch_size = int(recovery["batch_size"])
    batches = [missing_records[index:index + batch_size] for index in range(0, len(missing_records), batch_size)]
    if len(receipts) + len(batches) > int(recovery["hard_max_recovery_calls"]):
        raise RuntimeError("D1 incident recovery would exceed its share of the combined call budget")
    if not incident_path.exists():
        _write_json(
            incident_path,
            {
                "schema_version": "d1_primary_call_incident@1.0.0",
                "recorded_at_utc": _utc(),
                "primary_submitted_call_count": 150,
                "persisted_before_recovery_count": len(completed),
                "lost_result_count": len(missing_records),
                "cause": "uncaught local validator KeyError after all ThreadPoolExecutor futures had been submitted; executor shutdown waited for queued calls",
                "primary_calls_retried_individually": False,
                "recovery_batch_size": batch_size,
                "planned_recovery_call_count": len(batches),
            },
        )
    if not batches:
        print("D1 recovery complete; no missing samples", flush=True)
        return
    prompt = load_prompt("direct_llm_sun_record_prompt")
    runtime_config = config["shared_runtime"]
    first_batch_id = max(receipts, default=0) + 1
    print(f"D1 recovery missing={len(missing_records)}, batches={len(batches)}, workers={min(workers, 12)}", flush=True)
    with ThreadPoolExecutor(max_workers=min(workers, 12)) as pool:
        futures = {
            pool.submit(
                _d1_recovery_batch_job,
                first_batch_id + offset,
                [
                    {
                        "sample_id": record["sample_id"],
                        "source_id": record["source_id"],
                        "source_text": record["source_text"],
                    }
                    for record in batch
                ],
                prompt,
                runtime_config,
                api_key,
            ): first_batch_id + offset
            for offset, batch in enumerate(batches)
        }
        for future in as_completed(futures):
            receipt = future.result()
            _append_jsonl(receipts_path, receipt)
            for result in receipt["sample_results"]:
                _append_jsonl(responses_path, result)
            completed.update({result["sample_id"]: result for result in receipt["sample_results"]})
            print(f"D1 recovery completed {len(completed)}/150", flush=True)


def _h1_job(
    record: Mapping[str, Any],
    confidence: float,
    prompt: Any,
    protocol_config: Mapping[str, Any],
    runtime_config: Mapping[str, Any],
    api_key: str,
) -> dict[str, Any]:
    plan = detect_repair_plan(record, {"modality_confidence": confidence}, protocol_config, clause_index=0)
    rendered = render_h1_request(record, plan, prompt, protocol_config)
    call = _call_api(
        messages=rendered["api_request"]["messages"],
        runtime_config=runtime_config,
        api_key=api_key,
    )
    base = {
        "sample_id": record["sample_id"],
        "model": runtime_config["model"],
        "thinking_mode": runtime_config["thinking_mode"],
        "request_sha256": call.get("request_sha256"),
        "runtime": _runtime(call, True),
        "repair_plan": plan.to_dict(),
    }
    if not call.get("ok"):
        return {
            **base,
            "request_status": "ok",
            "record": finalize_h1_record(record, original_b0=record, fallback_to_b0=True),
            "error_category": None,
            "recovered_runtime_error_category": call["error_category"],
            "response_sha256": None,
            "merge": {"accepted": False, "status": "provider_error", "errors": []},
        }
    parsed, repairs = _parse_json_loose(call["content"])
    if isinstance(parsed, dict):
        parsed = copy.deepcopy(parsed)
        patches = parsed.get("patches")
        coordinate_repairs = _repair_record_coordinates({"clauses": [parsed.get("patches", {})]}, record["source_text"])
        if isinstance(patches, dict) and "clause_span" in patches and "clause_span" not in plan.repair_fields:
            patches.pop("clause_span")
            repairs.append("discarded_unrequested_nonsemantic_patch:clause_span")
    else:
        coordinate_repairs = []
    merged = apply_repair_patch(record, parsed, plan) if isinstance(parsed, dict) else None
    accepted = bool(merged and merged.accepted)
    final_record = merged.record if accepted else finalize_h1_record(record, original_b0=record, fallback_to_b0=True)
    return {
        **base,
        "request_status": "ok",
        "record": final_record,
        "error_category": None,
        "response_sha256": call["response_sha256"],
        "parsed_patch": parsed,
        "postprocess": repairs + coordinate_repairs,
        "merge": (
            merged.to_summary()
            if merged is not None
            else {"accepted": False, "status": "rejected_non_json", "errors": ["response did not parse as an object"]}
        ),
    }


def _adapt_stored_h1_response(
    response: Mapping[str, Any],
    record: Mapping[str, Any],
    confidence: float,
    protocol_config: Mapping[str, Any],
) -> dict[str, Any]:
    """Apply the declared nonsemantic cleanup to an already paid response."""

    adapted = copy.deepcopy(dict(response))
    parsed = copy.deepcopy(adapted.get("parsed_patch"))
    if not isinstance(parsed, dict):
        return adapted
    plan = detect_repair_plan(record, {"modality_confidence": confidence}, protocol_config, clause_index=0)
    notes = list(adapted.get("postprocess") or [])
    patches = parsed.get("patches")
    if isinstance(patches, dict):
        coordinate_notes = _repair_record_coordinates({"clauses": [patches]}, record["source_text"])
        notes.extend(coordinate_notes)
        if "clause_span" in patches and "clause_span" not in plan.repair_fields:
            patches.pop("clause_span")
            notes.append("discarded_unrequested_nonsemantic_patch:clause_span")
    merged = apply_repair_patch(record, parsed, plan)
    adapted["parsed_patch_after_adapter"] = parsed
    adapted["postprocess"] = list(dict.fromkeys(notes))
    adapted["merge"] = merged.to_summary()
    adapted["record"] = (
        merged.record
        if merged.accepted
        else finalize_h1_record(record, original_b0=record, fallback_to_b0=True)
    )
    return adapted


def _run_h1(
    records: list[dict[str, Any]],
    config: Mapping[str, Any],
    *,
    api_key: str,
    workers: int,
    limit: int | None,
) -> None:
    output_root = ROOT / config["output"]
    responses_path = output_root / "h1_responses.jsonl"
    completed = _load_jsonl_by_id(responses_path)
    selection = _json(ROOT / config["inputs"]["h1_trigger_selection"])
    selected = {item["sample_id"]: float(item["b0_confidence"]) for item in selection["selection"]["samples"]}
    record_by_id = {record["sample_id"]: record for record in records}
    missing = sorted(set(selected) - set(record_by_id))
    if missing:
        raise RuntimeError(f"H1 selected samples are absent from B0: {missing}")
    pending_ids = [sample_id for sample_id in sorted(selected) if sample_id not in completed]
    if limit is not None:
        pending_ids = pending_ids[: max(0, limit - len(completed))]
    if len(completed) + len(pending_ids) > config["budget"]["h1_hard_max_calls"]:
        raise RuntimeError("H1 hard call budget would be exceeded")
    prompt = load_prompt("rule_first_llm_fallback_prompt")
    protocol_config = _json(ROOT / config["methods"]["H1"]["protocol_config"])
    runtime_config = config["shared_runtime"]
    print(f"H1 resume={len(completed)}, pending={len(pending_ids)}, workers={min(workers, 7)}", flush=True)
    with ThreadPoolExecutor(max_workers=min(workers, 7)) as pool:
        futures = {
            pool.submit(
                _h1_job,
                record_by_id[sample_id],
                selected[sample_id],
                prompt,
                protocol_config,
                runtime_config,
                api_key,
            ): sample_id
            for sample_id in pending_ids
        }
        for future in as_completed(futures):
            result = future.result()
            _append_jsonl(responses_path, result)
            print(f"H1 completed {len(_load_jsonl_by_id(responses_path))}/7", flush=True)
    responses = _load_jsonl_by_id(responses_path)
    if len(responses) == len(selected):
        evaluated_responses = {
            sample_id: _adapt_stored_h1_response(
                response,
                record_by_id[sample_id],
                selected[sample_id],
                protocol_config,
            )
            for sample_id, response in responses.items()
        }
        _write_json(
            output_root / "h1_evaluated_responses.json",
            [evaluated_responses[sample_id] for sample_id in sorted(evaluated_responses)],
            replace=True,
        )
        attempts: list[dict[str, Any]] = []
        zero = _runtime({}, False)
        for record in records:
            if record["sample_id"] in evaluated_responses:
                attempts.append(evaluated_responses[record["sample_id"]])
            else:
                attempts.append(
                    {
                        "sample_id": record["sample_id"],
                        "request_status": "ok",
                        "record": finalize_h1_record(record, original_b0=record, fallback_to_b0=True),
                        "error_category": None,
                        "runtime": zero,
                        "selection_status": "not_triggered",
                    }
                )
        _write_json(output_root / "h1_attempts.json", attempts, replace=True)


def _finalize(records: list[dict[str, Any]], config: Mapping[str, Any]) -> None:
    output_root = ROOT / config["output"]
    d1_by_id = _load_jsonl_by_id(output_root / "d1_responses.jsonl")
    h1_path = output_root / "h1_attempts.json"
    if len(d1_by_id) != 150 or not h1_path.exists():
        print(f"Run is resumable but incomplete: D1={len(d1_by_id)}/150 H1_attempts={h1_path.exists()}", flush=True)
        return
    ordered_ids = [record["sample_id"] for record in records]
    d1_attempts = [d1_by_id[sample_id] for sample_id in ordered_ids]
    _write_json(output_root / "d1_attempts.json", d1_attempts, replace=True)
    h1_attempts = _json(h1_path)

    layer_e = ROOT / config["inputs"]["human_gold_evaluation_only"]
    membership = ROOT / config["inputs"]["membership"]
    gold, _ = build_canonical_gold_records(layer_e, membership)
    metrics = {
        "H1": evaluate_sun_table8_literal_overlap(
            gold,
            h1_attempts,
            dataset_id="independently_reconstructed_estg_150_v1",
            method_id="sun_llm_fallback:deepseek-v4-pro:r1",
        ),
        "D1": evaluate_sun_table8_literal_overlap(
            gold,
            d1_attempts,
            dataset_id="independently_reconstructed_estg_150_v1",
            method_id="direct_llm:deepseek-v4-pro:r1",
        ),
    }
    _write_json(output_root / "metrics.json", metrics, replace=True)
    h1_evaluated_calls = sum(bool(item.get("runtime", {}).get("llm_call_performed")) for item in h1_attempts)
    rejected_round_path = output_root / "h1_responses_v1_rejected.jsonl"
    h1_diagnostic_calls = len(_load_jsonl_by_id(rejected_round_path)) if rejected_round_path.exists() else 0
    h1_calls = h1_evaluated_calls + h1_diagnostic_calls
    incident_path = output_root / "d1_primary_call_incident.json"
    recovery_path = output_root / "d1_recovery_batches.jsonl"
    if incident_path.exists():
        d1_primary_calls = int(_json(incident_path)["primary_submitted_call_count"])
    else:
        d1_primary_calls = sum(bool(item.get("runtime", {}).get("llm_call_performed")) for item in d1_attempts)
    d1_recovery_calls = (
        sum(1 for line in recovery_path.read_text(encoding="utf-8").splitlines() if line.strip())
        if recovery_path.exists()
        else 0
    )
    d1_calls = d1_primary_calls + d1_recovery_calls
    manifest = {
        "schema_version": "estg150_h1_d1_deepseek_v4pro_run_manifest@1.0.0",
        "run_id": "s28_s29_deepseek_v4pro_sun_literal_v1",
        "status": "succeeded_development_not_formal",
        "completed_at_utc": _utc(),
        "claim_scope": config["claim_scope"],
        "model": config["shared_runtime"]["model"],
        "repeat_count": 1,
        "llm_call_budget": copy.deepcopy(config["budget"]),
        "llm_call_count": {
            "H1": h1_calls,
            "H1_evaluated": h1_evaluated_calls,
            "H1_diagnostic_adapter_round": h1_diagnostic_calls,
            "D1": d1_calls,
            "D1_primary_submitted": d1_primary_calls,
            "D1_incident_recovery_batches": d1_recovery_calls,
            "combined": h1_calls + d1_calls,
        },
        "failure_policy": {
            "max_retries": 0,
            "H1": "provider or rejected patch preserves B0",
            "D1": "API/non-JSON failure stays as an empty attempt",
        },
        "transport_variance": {
            "preflight_sample_id": "estg_000002",
            "preflight_thinking_mode": "provider_default_enabled",
            "preflight_outcome": "completion_token_limit_non_json_failure_retained_in_D1_denominator",
            "remaining_requests_thinking_mode": config["shared_runtime"]["thinking_mode"],
            "preflight_retried": False
        },
        "d1_runtime_incident": (
            _json(incident_path)
            if incident_path.exists()
            else None
        ),
        "h1_adapter_round": {
            "diagnostic_response_path": "h1_responses_v1_rejected.jsonl",
            "diagnostic_outcome": "all seven patches contained an extra nonsemantic clause_span member",
            "evaluated_round_adjustment": "discard only the unrequested clause_span member before the unchanged six-element patch merge",
            "gold_or_test_metrics_used": False
        },
        "shared_protocol": copy.deepcopy(config["shared_semantic_protocol"]),
        "prompt_bindings": {
            "H1": {
                "path": config["methods"]["H1"]["prompt"],
                "sha256": sha256_file(ROOT / config["methods"]["H1"]["prompt"]),
            },
            "D1": {
                "path": config["methods"]["D1"]["prompt"],
                "sha256": sha256_file(ROOT / config["methods"]["D1"]["prompt"]),
            },
        },
        "input_bindings": {
            "b0_attempts_sha256": sha256_file(ROOT / config["inputs"]["b0_attempts"]),
            "layer_e_sha256": sha256_file(layer_e),
            "membership_sha256": sha256_file(membership),
            "config_sha256": sha256_file(CONFIG_PATH),
        },
        "artifacts": {
            "h1_attempts": {"path": "h1_attempts.json", "sha256": sha256_file(h1_path)},
            "d1_attempts": {"path": "d1_attempts.json", "sha256": sha256_file(output_root / "d1_attempts.json")},
            "metrics": {"path": "metrics.json", "sha256": sha256_file(output_root / "metrics.json")},
            "d1_primary_call_incident": (
                {"path": "d1_primary_call_incident.json", "sha256": sha256_file(incident_path)}
                if incident_path.exists()
                else None
            ),
            "d1_recovery_batches": (
                {"path": "d1_recovery_batches.jsonl", "sha256": sha256_file(recovery_path)}
                if recovery_path.exists()
                else None
            ),
        },
        "safety": {
            "gold_modified": False,
            "gold_visible_to_requests": False,
            "env_file_read": False,
            "raw_provider_response_persisted": False,
            "network_called": True,
            "real_llm_api_called": True,
        },
    }
    _write_json(output_root / "manifest.json", manifest, replace=True)
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", choices=("H1", "D1", "all"), default="all")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, help="Total completed-call ceiling per selected method; useful for smoke/resume.")
    parser.add_argument("--recover-d1", action="store_true", help="Use bounded four-record recovery batches after the recorded primary-call incident.")
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        raise SystemExit("--workers must be in 1..12")
    config = _json(CONFIG_PATH)
    api_key = os.environ.get(config["shared_runtime"]["api_key_environment_variable"], "")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is unavailable; .env is intentionally not read")
    records = _load_b0(config)
    if args.method in ("H1", "all"):
        _run_h1(records, config, api_key=api_key, workers=args.workers, limit=args.limit)
    if args.method in ("D1", "all"):
        if args.recover_d1:
            _run_d1_recovery(records, config, api_key=api_key, workers=args.workers)
        else:
            _run_d1(records, config, api_key=api_key, workers=args.workers, limit=args.limit)
    _finalize(records, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Run the locked S2.12 ``sun_rule_only`` arm without reading Gold.

This runner consumes the committed hash-only input, resolves third-party text
locally after hash verification, invokes the already locked B0 v10a method,
and atomically publishes a text-free prediction capsule.  It has no API or
network path and deliberately contains no Gold path constant.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.estg150_b0_development_v10 import (  # noqa: E402
    Estg150B0DevelopmentError,
    run_b0_batch_v10,
)
from bpc_hybrid.s2_12_method_adapter import adapt_method_attempts  # noqa: E402

INPUT = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
LOCK = ROOT / "configs/s2_12_sun_rule_only_run_v1.json"
OUTPUT_DIR = ROOT / "data/predictions/s2_12_sun_rule_only_v1"
EXPECTED_INPUT_SHA = "892d4284ea70c38f82a47f821c13622f1b07744253429e466038ddb5db96660e"


class S212RunFail(ValueError):
    """Fail-closed S2.12 run error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _verify_lock() -> dict[str, Any]:
    if _sha(INPUT) != EXPECTED_INPUT_SHA:
        raise S212RunFail("Gold-blind input drift")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "s2_12_sun_rule_only_lock@1.0.0":
        raise S212RunFail("run-lock schema identity drift")
    if lock.get("status") != "locked_before_gold_read":
        raise S212RunFail("method was not locked before Gold read")
    if lock.get("gold_isolation", {}).get("runner_reads_gold") is not False:
        raise S212RunFail("Gold isolation declaration invalid")
    if lock.get("safety", {}).get("llm_api_calls") != 0:
        raise S212RunFail("zero-API lock invalid")
    for rel, expected in lock.get("bindings", {}).items():
        path = ROOT / Path(rel.replace("/", os.sep))
        if not path.is_file() or _sha(path) != expected:
            raise S212RunFail(f"locked binding drift: {rel}")
    return lock


def _resolve_records(
    input_doc: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if input_doc.get("schema_version") != "s2_12_complex_corpus_input@1.0.0":
        raise S212RunFail("input schema identity drift")
    if input_doc.get("gold_blind") is not True or input_doc.get("record_count") != 36:
        raise S212RunFail("input must be Gold-blind with 36 records")
    records: list[dict[str, Any]] = []
    runtime_to_formal: dict[str, str] = {}
    seen: set[str] = set()
    for item in input_doc.get("records", []):
        sample_id = item.get("sample_id")
        source = item.get("source") or {}
        if not isinstance(sample_id, str) or sample_id in seen:
            raise S212RunFail("input sample IDs are missing or duplicated")
        seen.add(sample_id)
        source_path = ROOT.parent / Path(str(source.get("path", "")).replace("/", os.sep))
        if not source_path.is_file() or _sha(source_path) != source.get("file_sha256"):
            raise S212RunFail(f"source file drift: {sample_id}")
        raw = source_path.read_bytes()
        try:
            rows = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise S212RunFail(f"source JSON invalid: {sample_id}") from exc
        matches = [
            row for row in rows
            if str(row.get("ID")) == str(source.get("record_id"))
            and int(row.get("version")) == int(source.get("version"))
        ]
        if len(matches) != 1:
            raise S212RunFail(f"source locator not unique: {sample_id}")
        text = str(matches[0].get("text", ""))
        text_bytes = text.encode("utf-8")
        if hashlib.sha256(text_bytes).hexdigest() != source.get("text_sha256"):
            raise S212RunFail(f"source text drift: {sample_id}")
        if len(text_bytes) != source.get("text_byte_size") or not text.strip():
            raise S212RunFail(f"source text size/emptiness invalid: {sample_id}")
        # The corpus is English-only.  The locked cross-language boundary is
        # explicit: no translation is synthesized; the same source text is
        # passed through the legacy classifier slot.
        runtime_sample_id = f"s212_{len(records) + 1:04d}"
        runtime_to_formal[runtime_sample_id] = sample_id
        records.append({
            # B0 uses sample_id as a temporary filename.  Formal IDs contain
            # '/', so a deterministic filesystem-safe runtime ID is used and
            # mapped back before any prediction is persisted.
            "sample_id": runtime_sample_id,
            "approved_text_en": text,
            "raw_text_de": text,
            "legacy_record_id": sample_id.replace("/", "_"),
        })
    if len(records) != 36:
        raise S212RunFail(f"expected 36 resolved records, got {len(records)}")
    return records, runtime_to_formal


def _coord_span(span: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"start": span.get("start"), "end": span.get("end")}
    if isinstance(span.get("id"), str):
        out["id"] = span["id"]
    return out


def _sanitize_attempt(attempt: Mapping[str, Any]) -> dict[str, Any]:
    record = attempt.get("record") or {}
    clauses = []
    for clause in record.get("clauses") or []:
        modality = clause.get("modality") or {}
        clauses.append({
            "clause_id": clause.get("clause_id"),
            "clause_span": {
                "start": (clause.get("clause_span") or {}).get("start"),
                "end": (clause.get("clause_span") or {}).get("end"),
            },
            "modality": {
                "label": modality.get("label"),
                "evidence": [_coord_span(s) for s in modality.get("evidence") or []],
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
        "sample_id": attempt.get("sample_id"),
        "request_status": attempt.get("request_status"),
        "record": {
            "schema_version": record.get("schema_version"),
            "sample_id": record.get("sample_id"),
            "source_id": record.get("source_id"),
            "clauses": clauses,
            "method": {"name": "sun_rule_only", "method_variant": "b0_enhanced_v10a"},
            "validation": copy.deepcopy(record.get("validation") or {}),
        },
        "error_category": attempt.get("error_category"),
    }


def _contains_raw_text(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"text", "source_text", "normalized", "marker_surface"}:
                return True
            if _contains_raw_text(child):
                return True
    elif isinstance(value, list):
        return any(_contains_raw_text(item) for item in value)
    return False


def run(runtime_home: Path, device: str) -> dict[str, Any]:
    lock = _verify_lock()
    input_doc = json.loads(INPUT.read_text(encoding="utf-8"))
    source_records, runtime_to_formal = _resolve_records(input_doc)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="s212-b0-", dir=ROOT / ".tmp") as raw_work:
        attempts, runtime = run_b0_batch_v10(
            ROOT,
            source_records,
            runtime_home=runtime_home,
            work_dir=Path(raw_work),
            device=device,
        )
    for attempt in attempts:
        runtime_sample_id = str(attempt.get("sample_id"))
        formal_sample_id = runtime_to_formal.get(runtime_sample_id)
        if formal_sample_id is None:
            raise S212RunFail(f"unknown B0 runtime sample ID: {runtime_sample_id}")
        attempt["sample_id"] = formal_sample_id
        record = attempt.get("record") or {}
        record["sample_id"] = formal_sample_id
    adapted = adapt_method_attempts(attempts, "sun_rule_only")
    if len(adapted) != 36 or {a.get("request_status") for a in adapted} != {"ok"}:
        raise S212RunFail("B0 did not return 36 successful attempts")
    predictions = [_sanitize_attempt(a) for a in adapted]
    if _contains_raw_text(predictions):
        raise S212RunFail("text containment failed for committed predictions")

    prediction_doc = {
        "schema_version": "s2_12_sun_rule_only_predictions@1.0.0",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "sun_rule_only",
        "record_count": 36,
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": predictions,
    }
    telemetry = {
        "schema_version": "s2_12_sun_rule_only_telemetry@1.0.0",
        "record_count": runtime.get("record_count"),
        "predicted_clause_count": runtime.get("predicted_clause_count"),
        "corenlp_seconds": runtime.get("corenlp_seconds"),
        "bridge_seconds": runtime.get("bridge_seconds"),
        "classifier_seconds": runtime.get("classifier_seconds"),
        "compose_seconds": runtime.get("compose_seconds"),
        "total_seconds": runtime.get("total_seconds"),
        "device": runtime.get("device"),
        "modality_route_counts": runtime.get("modality_route_counts"),
        "label_counts": runtime.get("final_hybrid_label_counts_by_clause"),
        "alignment_summary": runtime.get("alignment_summary"),
        "text_or_gold_payload_committed": False,
    }
    cost = {
        "schema_version": "s2_12_zero_api_cost@1.0.0",
        "llm_api_calls": 0,
        "network_calls": 0,
        "input_tokens_billed": 0,
        "output_tokens_billed": 0,
        "actual_cost_usd": 0.0,
    }
    files = {
        "predictions.json": _json_bytes(prediction_doc),
        "telemetry.json": _json_bytes(telemetry),
        "cost.json": _json_bytes(cost),
    }
    artifacts = {
        name: {"sha256": hashlib.sha256(data).hexdigest(), "byte_size": len(data)}
        for name, data in files.items()
    }
    manifest = {
        "schema_version": "s2_12_sun_rule_only_manifest@1.0.0",
        "run_id": "s2_12_sun_rule_only_v1",
        "status": "predictions_locked_before_gold_evaluation",
        "dataset_id": "s2_11_barrientos_complex_corpus_36_v1",
        "method_id": "sun_rule_only",
        "method_variant": "b0_enhanced_v10a",
        "single_arm_only": True,
        "input_binding": {
            "path": "data/input/s2_12_complex_corpus_formal_input_v1.json",
            "sha256": EXPECTED_INPUT_SHA,
            "records": 36,
        },
        "run_lock": {
            "path": "configs/s2_12_sun_rule_only_run_v1.json",
            "sha256": _sha(LOCK),
        },
        "method_bindings": lock["bindings"],
        "language_boundary": lock["method"]["language_boundary"],
        "gold_isolation": {
            "gold_read_by_runner": False,
            "predictions_locked_before_evaluation": True,
            "post_result_tuning_forbidden": True,
        },
        "runtime_summary": telemetry,
        "artifacts": artifacts,
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "cost_usd": 0.0,
            "raw_text_committed": False,
            "gold_rule_records_created": False,
            "oracle_started": False,
        },
        "reproduce_command": (
            "python formal_experiment/scripts/run_s2_12_sun_rule_only_v1.py "
            "--runtime-home D:/environment/stanford-corenlp-4.5.10 --device cpu"
        ),
    }
    files["manifest.json"] = _json_bytes(manifest)

    if OUTPUT_DIR.exists():
        raise S212RunFail(f"refusing to overwrite existing run: {OUTPUT_DIR}")
    stage = OUTPUT_DIR.parent / f".{OUTPUT_DIR.name}.staging-{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        for name, data in files.items():
            (stage / name).write_bytes(data)
        stage.rename(OUTPUT_DIR)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-home", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    try:
        manifest = run(args.runtime_home, args.device)
    except (S212RunFail, Estg150B0DevelopmentError) as exc:
        print(f"S2.12 sun_rule_only refused: {exc}")
        return 2
    print("S2.12 sun_rule_only predictions locked before Gold evaluation")
    print(f"records=36 total_seconds={manifest['runtime_summary']['total_seconds']}")
    print("llm_api_calls=0 network_calls=0 actual_cost_usd=0.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

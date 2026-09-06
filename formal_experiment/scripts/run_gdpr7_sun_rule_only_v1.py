# -*- coding: utf-8 -*-
"""Run the locked ``sun_rule_only`` (Rules-Only / B0 v10a) arm over the
GDPR Stage-2 sentence input without reading Gold.

The arm consumes ``data/input/gdpr7_stage2_input_v1.json`` (74 sentences,
9 GDPR rule texts from the frozen Stage-3 inference pack), invokes the same
locked B0 v10a method used by the S2.12 complex-corpus zero-API arm
(``bpc_hybrid.estg150_b0_development_v10.run_b0_batch_v10``), and atomically
publishes a text-free prediction capsule.  Language boundary: the locked
modality classifier was developed with a German inference-language contract;
this English sentence pass-through run is descriptive (same disclosure as
the S2.12 zero-API arm) and is not a language-matched classifier validation.
No LLM/API/network path; no Gold path constant.
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

INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
LOCK = ROOT / "configs/gdpr7_sun_rule_only_run_v1.json"
OUTPUT_DIR = ROOT / "data/predictions/gdpr7_sun_rule_only_v1"
EXPECTED_INPUT_SHA = "558b80131394c8ac349db42cc323ffcf7264b7ae7da796522d55bf5ff89eb109"
EXPECTED_SENTENCE_COUNT = 74
DATASET_ID = "gdpr7_stage2_sentences_v1"
RUN_ID = "gdpr7_sun_rule_only_v1"
PREDICTION_SCHEMA = "gdpr7_sun_rule_only_predictions@1.0.0"
TELEMETRY_SCHEMA = "gdpr7_sun_rule_only_telemetry@1.0.0"
COST_SCHEMA = "gdpr7_zero_api_cost@1.0.0"
MANIFEST_SCHEMA = "gdpr7_sun_rule_only_manifest@1.0.0"


class Gdr7RunFail(ValueError):
    """Fail-closed GDPR Rules-Only run error."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _verify_lock() -> dict[str, Any]:
    if _sha(INPUT) != EXPECTED_INPUT_SHA:
        raise Gdr7RunFail("Gold-blind input drift")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    if lock.get("schema_version") != "gdpr7_sun_rule_only_lock@1.0.0":
        raise Gdr7RunFail("run-lock schema identity drift")
    if lock.get("status") != "locked_before_gold_read":
        raise Gdr7RunFail("method was not locked before Gold read")
    if lock.get("gold_isolation", {}).get("runner_reads_gold") is not False:
        raise Gdr7RunFail("Gold isolation declaration invalid")
    if lock.get("safety", {}).get("llm_api_calls") != 0:
        raise Gdr7RunFail("zero-API lock invalid")
    for rel, expected in lock.get("bindings", {}).items():
        path = ROOT / Path(rel.replace("/", os.sep))
        if not path.is_file() or _sha(path) != expected:
            raise Gdr7RunFail(f"locked binding drift: {rel}")
    return lock


def _resolve_records(input_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    if input_doc.get("schema_version") != "gdpr7_stage2_input@1.0.0":
        raise Gdr7RunFail("input schema identity drift")
    if input_doc.get("gold_visible") is not False:
        raise Gdr7RunFail("input must be Gold-blind")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rule in input_doc.get("rules", []):
        for s in rule.get("sentences", []):
            sample_id = s.get("sample_id")
            text = s.get("approved_text_en")
            if not isinstance(sample_id, str) or sample_id in seen:
                raise Gdr7RunFail("sentence sample IDs are missing or duplicated")
            if not isinstance(text, str) or not text.strip():
                raise Gdr7RunFail(f"empty sentence text: {sample_id}")
            if _sha_of_text(text) != s.get("text_sha256"):
                raise Gdr7RunFail(f"sentence text hash drift: {sample_id}")
            seen.add(sample_id)
            # The corpus is English-only.  The locked cross-language boundary
            # is explicit: no translation is synthesized; the same source
            # text is passed through the legacy classifier slot.
            records.append({
                # sample_id is already filesystem-safe (gdpr_<article>_sNNN).
                "sample_id": sample_id,
                "approved_text_en": text,
                "raw_text_de": text,
                "legacy_record_id": sample_id,
            })
    if len(records) != EXPECTED_SENTENCE_COUNT:
        raise Gdr7RunFail(
            f"expected {EXPECTED_SENTENCE_COUNT} resolved sentence records, "
            f"got {len(records)}"
        )
    return records


def _sha_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    source_records = _resolve_records(input_doc)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gdpr7-b0-", dir=ROOT / ".tmp") as raw_work:
        attempts, runtime = run_b0_batch_v10(
            ROOT,
            source_records,
            runtime_home=runtime_home,
            work_dir=Path(raw_work),
            device=device,
        )
    adapted = adapt_method_attempts(attempts, "sun_rule_only")
    if len(adapted) != EXPECTED_SENTENCE_COUNT:
        raise Gdr7RunFail(
            f"B0 did not return {EXPECTED_SENTENCE_COUNT} attempts; got "
            f"{len(adapted)}"
        )
    predictions = [_sanitize_attempt(a) for a in adapted]
    if _contains_raw_text(predictions):
        raise Gdr7RunFail("text containment failed for committed predictions")

    empty_clause_samples = [
        p["sample_id"] for p in predictions
        if p.get("request_status") == "ok"
        and not (p.get("record") or {}).get("clauses")
    ]
    failed = [
        p for p in predictions
        if p.get("request_status") != "ok" or p.get("error_category")
    ]

    prediction_doc = {
        "schema_version": PREDICTION_SCHEMA,
        "dataset_id": DATASET_ID,
        "method_id": "sun_rule_only",
        "record_count": EXPECTED_SENTENCE_COUNT,
        "gold_read_by_runner": False,
        "raw_text_committed": False,
        "records": predictions,
    }
    telemetry = {
        "schema_version": TELEMETRY_SCHEMA,
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
        "empty_output_samples": {
            "count": len(empty_clause_samples),
            "sample_ids": empty_clause_samples,
        },
        "failed_attempts": {
            "count": len(failed),
            "sample_ids": [p["sample_id"] for p in failed],
            "error_categories": [
                {"sample_id": p["sample_id"], "error_category": p["error_category"]}
                for p in failed
            ],
        },
        "text_or_gold_payload_committed": False,
    }
    cost = {
        "schema_version": COST_SCHEMA,
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
        "schema_version": MANIFEST_SCHEMA,
        "run_id": RUN_ID,
        "status": "predictions_locked_before_gold_evaluation",
        "dataset_id": DATASET_ID,
        "method_id": "sun_rule_only",
        "method_variant": "b0_enhanced_v10a",
        "single_arm_only": True,
        "input_binding": {
            "path": "data/input/gdpr7_stage2_input_v1.json",
            "sha256": EXPECTED_INPUT_SHA,
            "records": EXPECTED_SENTENCE_COUNT,
        },
        "run_lock": {
            "path": "configs/gdpr7_sun_rule_only_run_v1.json",
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
            "python formal_experiment/scripts/run_gdpr7_sun_rule_only_v1.py "
            "--runtime-home D:/environment/stanford-corenlp-4.5.10 --device cpu"
        ),
    }
    files["manifest.json"] = _json_bytes(manifest)

    if OUTPUT_DIR.exists():
        raise Gdr7RunFail(f"refusing to overwrite existing run: {OUTPUT_DIR}")
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
    except (Gdr7RunFail, Estg150B0DevelopmentError) as exc:
        print(f"GDPR sun_rule_only refused: {exc}")
        return 2
    print("GDPR sun_rule_only predictions locked before Gold evaluation")
    print(
        f"records={EXPECTED_SENTENCE_COUNT} "
        f"total_seconds={manifest['runtime_summary']['total_seconds']}"
    )
    print("llm_api_calls=0 network_calls=0 actual_cost_usd=0.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

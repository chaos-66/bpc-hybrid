# -*- coding: utf-8 -*-
"""Same-evaluator bridge for the SEP-C2 predecessor modality baselines.

Prediction code in this module never reads ``data/gold``.  Evaluation code is a
separate function that loads the frozen published Gold and delegates the actual
metric computation to ``bpc_hybrid.formal_stage2_evaluation`` so that the
predecessor rows and the existing B0/D1 rows share exactly one implementation.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.formal_stage2_evaluation import (
    evaluate_modality_labels,
    published_gold_to_evaluator,
)
from bpc_hybrid.sun_predecessors.common import (
    MODALITY_CLASSES,
    SunPredecessorError,
    load_json,
)

FORMAL_INPUT_REL = "data/input/estg150_formal_inference_input_v2.json"
FORMAL_GOLD_REL = "data/gold/stage2/estg150_formal_gold_v1.json"


def load_formal_input(formal_root: Path) -> list[dict[str, Any]]:
    document = load_json(Path(formal_root) / FORMAL_INPUT_REL)
    if document.get("schema_version") != "estg150_formal_inference_input@2.0.0":
        raise SunPredecessorError("unexpected formal input schema")
    records = document.get("records")
    if not isinstance(records, list) or len(records) != 150:
        raise SunPredecessorError("formal input must contain exactly 150 records")
    if len({row.get("sample_id") for row in records}) != 150:
        raise SunPredecessorError("formal input sample_ids must be unique")
    for row in records:
        for key in ("sample_id", "approved_text_en", "raw_text_de"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise SunPredecessorError(f"formal input row missing non-empty {key}")
    return records


def load_gold_eval(formal_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gold_doc = load_json(Path(formal_root) / FORMAL_GOLD_REL)
    return gold_doc, published_gold_to_evaluator(gold_doc)


def make_modality_record(
    *,
    sample_id: str,
    source_text: str,
    label: str,
    method_id: str,
    evidence_text: str | None = None,
) -> dict[str, Any]:
    """Build a scorable prediction record without claiming six-element output."""
    if label not in MODALITY_CLASSES:
        raise SunPredecessorError(f"invalid modality label: {label!r}")
    evidence = evidence_text if evidence_text is not None else source_text
    start = 0
    end = len(evidence)
    if not evidence:
        evidence = source_text[:1] if source_text else ""
        end = len(evidence)
    clause = {
        "clause_id": f"{sample_id}.c1",
        "clause_span": {"text": source_text, "start": 0, "end": len(source_text)},
        "modality": {
            "label": label,
            "evidence": [{"text": evidence, "start": start, "end": end}],
        },
        "actors": [],
        "actions": [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
    }
    return {
        "schema_version": "sep_c2_sun_predecessor_modality_record@1.0.0",
        "sample_id": sample_id,
        "source_id": sample_id,
        "source_text": source_text,
        "clauses": [clause],
        "method": {
            "name": method_id,
            "schema_source": "sep_c2_sun_predecessors_v1",
        },
        "validation": {"schema_valid": None, "cross_field_valid": None, "errors": []},
    }


def make_attempt(
    *,
    sample_id: str,
    source_text: str,
    label: str,
    method_id: str,
    evidence_text: str | None = None,
    runtime: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "sample_id": sample_id,
        "request_status": "ok",
        "record": make_modality_record(
            sample_id=sample_id,
            source_text=source_text,
            label=label,
            method_id=method_id,
            evidence_text=evidence_text,
        ),
        "error_category": None,
        "runtime": {
            "llm_call_performed": False,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "latency_ms": None,
            **(dict(runtime) if runtime else {}),
        },
    }


def _first_modality_from_gold(gold_eval_records: Mapping[str, Mapping[str, Any]], sample_id: str) -> str | None:
    record = gold_eval_records.get(sample_id) or {}
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label:
            return label
    return None


def _first_modality_from_attempt(attempt: Mapping[str, Any] | None) -> str | None:
    if not attempt:
        return None
    record = attempt.get("record") or {}
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label:
            return label
    return None


def evaluate_attempts(
    formal_root: Path,
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Run the frozen evaluator and add transparent denominator/failure detail.

    The official evaluator's returned per-class precision/recall/F1 values are
    preserved byte-for-byte in ``official_evaluator``.  The extra accounting is
    derived from the same pairs and never changes the official numbers.
    """
    _, gold_eval = load_gold_eval(formal_root)
    official = evaluate_modality_labels(gold_eval, list(attempts))
    gold_by_id = {row["sample_id"]: row for row in gold_eval}
    attempt_by_id = {row["sample_id"]: row for row in attempts}
    pairs = []
    for sample_id in sorted(gold_by_id):
        attempt = attempt_by_id.get(sample_id)
        pairs.append(
            {
                "sample_id": sample_id,
                "gold": _first_modality_from_gold(gold_by_id, sample_id),
                "predicted": _first_modality_from_attempt(attempt),
                "row_present": attempt is not None,
                "request_status": None if attempt is None else attempt.get("request_status"),
            }
        )
    support = Counter(pair["gold"] for pair in pairs)
    predicted_counts = Counter(pair["predicted"] for pair in pairs if pair["predicted"])
    confusion = {
        gold_class: {
            (pred_class if pred_class is not None else "__missing__"): sum(
                1 for pair in pairs
                if pair["gold"] == gold_class and pair["predicted"] == pred_class
            )
            for pred_class in (*MODALITY_CLASSES, None)
        }
        for gold_class in MODALITY_CLASSES
    }
    failed = [pair["sample_id"] for pair in pairs if pair["request_status"] not in (None, "ok")]
    missing = [pair["sample_id"] for pair in pairs if not pair["row_present"]]
    unlabeled = [pair["sample_id"] for pair in pairs if pair["predicted"] is None]
    return {
        "schema_version": "sep_c2_sun_predecessor_evaluation@1.0.0",
        "task_id": "estg150_modality_label_classification_v1",
        "unit": "first clause modality per formal input record, frozen Gold order",
        "evaluator": "bpc_hybrid.formal_stage2_evaluation.evaluate_modality_labels",
        "evaluator_source": "src/bpc_hybrid/formal_stage2_evaluation.py",
        "official_evaluator": official,
        "records_expected": len(pairs),
        "records_scored": sum(1 for pair in pairs if pair["row_present"]),
        "records_missing": len(missing),
        "missing_sample_ids": missing,
        "records_failed": len(failed),
        "failed_sample_ids": failed,
        "unlabeled_predictions": len(unlabeled),
        "unlabeled_sample_ids": unlabeled,
        "correct": sum(1 for pair in pairs if pair["gold"] == pair["predicted"]),
        "gold_support": {label: support.get(label, 0) for label in MODALITY_CLASSES},
        "predicted_count": {label: predicted_counts.get(label, 0) for label in MODALITY_CLASSES},
        "confusion_rows_gold_columns_predicted": confusion,
    }
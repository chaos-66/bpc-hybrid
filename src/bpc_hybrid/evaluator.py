"""Multi-clause evaluation (R5).

Deterministic evaluation of extraction quality using clause-level
and field-level precision / recall / F1 metrics.

This evaluator is for **synthetic prototype sanity checking only**.
It is NOT a formal benchmark and must NOT be used to claim performance
against Sun, Winter-style textual baselines, or any LLM baseline.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bpc_hybrid.schema import (
    ClauseExtraction,
    FieldSpan,
    MultiClauseExtractionResponse,
    SchemaValidationError,
)

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class EvaluationError(ValueError):
    """Raised when the evaluator encounters an unexpected state."""


# ---------------------------------------------------------------------------
# Per-field metrics
# ---------------------------------------------------------------------------

@dataclass
class FieldMetrics:
    """Precision, recall, and F1 for a single semantic field."""

    field: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom > 0 else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom > 0 else 0.0

    @property
    def f1(self) -> float:
        p = self.precision
        r = self.recall
        return 2 * p * r / (p + r) if (p + r) > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


# ---------------------------------------------------------------------------
# Evaluation report
# ---------------------------------------------------------------------------

@dataclass
class EvaluationReport:
    """Full evaluation report for a synthetic prototype dataset."""

    dataset_type: str = "synthetic_prototype"
    is_formal_benchmark: bool = False
    compares_against_sun: bool = False

    total_gold_clauses: int = 0
    total_predicted_clauses: int = 0
    matched_clauses: int = 0

    clause_precision: float = 0.0
    clause_recall: float = 0.0
    clause_f1: float = 0.0

    # Field micro metrics (across all six fields)
    field_micro_precision: float = 0.0
    field_micro_recall: float = 0.0
    field_micro_f1: float = 0.0

    # Per-field breakdown
    per_field: dict[str, FieldMetrics] = field(default_factory=dict)

    num_gold_sources: int = 0
    num_predicted_sources: int = 0

    # Source-level details (for debugging)
    source_details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_type": self.dataset_type,
            "is_formal_benchmark": self.is_formal_benchmark,
            "compares_against_sun": self.compares_against_sun,
            "num_gold_sources": self.num_gold_sources,
            "num_predicted_sources": self.num_predicted_sources,
            "total_gold_clauses": self.total_gold_clauses,
            "total_predicted_clauses": self.total_predicted_clauses,
            "matched_clauses": self.matched_clauses,
            "clause_precision": round(self.clause_precision, 4),
            "clause_recall": round(self.clause_recall, 4),
            "clause_f1": round(self.clause_f1, 4),
            "field_micro_precision": round(self.field_micro_precision, 4),
            "field_micro_recall": round(self.field_micro_recall, 4),
            "field_micro_f1": round(self.field_micro_f1, 4),
            "per_field": {
                name: fm.to_dict() for name, fm in self.per_field.items()
            },
            "source_details": self.source_details,
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r'[^\w\s]')


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip punctuation, collapse whitespace."""
    t = text.lower()
    t = _PUNCT_RE.sub(' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------

_SEMANTIC_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")


def _compare_field(
    gold_fs: FieldSpan | None,
    pred_fs: FieldSpan | None,
    metrics: FieldMetrics,
) -> None:
    """Compare a single field and update *metrics* in-place."""
    if gold_fs is None and pred_fs is None:
        # True negative — not counted
        return
    if gold_fs is not None and pred_fs is not None:
        if _normalize(gold_fs.text) == _normalize(pred_fs.text):
            metrics.tp += 1
        else:
            metrics.fp += 1
            metrics.fn += 1
    elif gold_fs is None and pred_fs is not None:
        metrics.fp += 1
    else:  # gold_fs is not None and pred_fs is None
        metrics.fn += 1


# ---------------------------------------------------------------------------
# Core evaluation function
# ---------------------------------------------------------------------------

def evaluate_responses(
    gold: list[MultiClauseExtractionResponse],
    predicted: list[MultiClauseExtractionResponse],
) -> EvaluationReport:
    """Evaluate *predicted* responses against *gold* responses.

    Aligns responses by *source_id*, then aligns clauses by position
    within each source.
    """
    report = EvaluationReport()
    report.num_gold_sources = len(gold)
    report.num_predicted_sources = len(predicted)

    # --- Index by source_id --------------------------------------------
    gold_by_id: dict[str, MultiClauseExtractionResponse] = {}
    for g in gold:
        if g.source_id in gold_by_id:
            raise EvaluationError(
                f"Duplicate source_id '{g.source_id}' in gold data"
            )
        gold_by_id[g.source_id] = g

    pred_by_id: dict[str, MultiClauseExtractionResponse] = {}
    for p in predicted:
        if p.source_id in pred_by_id:
            raise EvaluationError(
                f"Duplicate source_id '{p.source_id}' in predicted data"
            )
        pred_by_id[p.source_id] = p

    # --- Initialize per-field metrics ----------------------------------
    per_field: dict[str, FieldMetrics] = {
        f: FieldMetrics(field=f) for f in _SEMANTIC_FIELDS
    }

    total_gold_clauses = 0
    total_pred_clauses = 0
    total_matched = 0

    # --- Evaluate each source ------------------------------------------
    for source_id, gold_resp in gold_by_id.items():
        pred_resp = pred_by_id.get(source_id)

        gold_clauses = gold_resp.clauses
        pred_clauses = pred_resp.clauses if pred_resp else []

        n_gold = len(gold_clauses)
        n_pred = len(pred_clauses)
        n_matched = min(n_gold, n_pred)

        total_gold_clauses += n_gold
        total_pred_clauses += n_pred
        total_matched += n_matched

        # Clause-level detail
        src_detail: dict[str, Any] = {
            "source_id": source_id,
            "gold_clauses": n_gold,
            "predicted_clauses": n_pred,
            "matched_clauses": n_matched,
        }

        # Compare matched clauses field-by-field
        matched_details: list[dict[str, Any]] = []
        for i in range(n_matched):
            gc = gold_clauses[i]
            pc = pred_clauses[i]
            clause_info: dict[str, Any] = {
                "clause_index": i,
                "gold_clause_id": gc.clause_id,
                "pred_clause_id": pc.clause_id,
            }
            for field_name in _SEMANTIC_FIELDS:
                gf = getattr(gc, field_name)
                pf = getattr(pc, field_name)
                _compare_field(gf, pf, per_field[field_name])
                clause_info[field_name] = {
                    "gold": gf.text if gf else None,
                    "predicted": pf.text if pf else None,
                }
            matched_details.append(clause_info)

        # Handle unmatched clauses
        for i in range(n_matched, n_gold):
            # Extra gold clause → all fields are FN
            gc = gold_clauses[i]
            for field_name in _SEMANTIC_FIELDS:
                gf = getattr(gc, field_name)
                if gf is not None:
                    per_field[field_name].fn += 1
        for i in range(n_matched, n_pred):
            # Extra predicted clause → all fields are FP
            pc = pred_clauses[i]
            for field_name in _SEMANTIC_FIELDS:
                pf = getattr(pc, field_name)
                if pf is not None:
                    per_field[field_name].fp += 1

        src_detail["matched_details"] = matched_details
        report.source_details.append(src_detail)

    # --- Clause-level metrics ------------------------------------------
    report.total_gold_clauses = total_gold_clauses
    report.total_predicted_clauses = total_pred_clauses
    report.matched_clauses = total_matched
    report.clause_precision = (
        total_matched / total_pred_clauses if total_pred_clauses > 0 else 0.0
    )
    report.clause_recall = (
        total_matched / total_gold_clauses if total_gold_clauses > 0 else 0.0
    )
    if report.clause_precision + report.clause_recall > 0:
        report.clause_f1 = (
            2
            * report.clause_precision
            * report.clause_recall
            / (report.clause_precision + report.clause_recall)
        )
    else:
        report.clause_f1 = 0.0

    # --- Field micro metrics -------------------------------------------
    total_tp = sum(fm.tp for fm in per_field.values())
    total_fp = sum(fm.fp for fm in per_field.values())
    total_fn = sum(fm.fn for fm in per_field.values())

    report.field_micro_precision = (
        total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    )
    report.field_micro_recall = (
        total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    )
    if report.field_micro_precision + report.field_micro_recall > 0:
        report.field_micro_f1 = (
            2
            * report.field_micro_precision
            * report.field_micro_recall
            / (report.field_micro_precision + report.field_micro_recall)
        )
    else:
        report.field_micro_f1 = 0.0

    report.per_field = per_field

    return report


# ---------------------------------------------------------------------------
# JSONL loading
# ---------------------------------------------------------------------------

def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL file, returning a list of dicts.

    Empty lines and lines starting with ``#`` are skipped.
    """
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line_num, line in enumerate(fh, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise EvaluationError(
                    f"Invalid JSON at {path}:{line_num}: {exc}"
                ) from exc
            records.append(record)
    return records


def load_gold_responses(path: str | Path) -> list[MultiClauseExtractionResponse]:
    """Load gold multi-clause responses from a JSONL file.

    Each record is validated through :meth:`MultiClauseExtractionResponse.from_dict`
    followed by :meth:`MultiClauseExtractionResponse.validate`.
    """
    records = load_jsonl(path)
    responses: list[MultiClauseExtractionResponse] = []
    for i, rec in enumerate(records):
        try:
            resp = MultiClauseExtractionResponse.from_dict(rec)
            resp.validate()
        except SchemaValidationError as exc:
            raise EvaluationError(
                f"Gold record {i} (source_id={rec.get('source_id', '?')!r}): {exc}"
            ) from exc
        responses.append(resp)
    return responses


def load_predicted_responses(path: str | Path) -> list[MultiClauseExtractionResponse]:
    """Load predicted multi-clause responses from a JSONL file.

    Each record must be a JSON object with the full
    :class:`MultiClauseExtractionResponse` structure.
    """
    records = load_jsonl(path)
    responses: list[MultiClauseExtractionResponse] = []
    for i, rec in enumerate(records):
        try:
            resp = MultiClauseExtractionResponse.from_dict(rec)
            resp.validate()
        except SchemaValidationError as exc:
            raise EvaluationError(
                f"Predicted record {i} (source_id={rec.get('source_id', '?')!r}): {exc}"
            ) from exc
        responses.append(resp)
    return responses

"""
R14 Field-level Evaluator
=========================
Computes field-level metrics for R14.2 rule-only baseline (and later R14.3).

Implements the scoring taxonomy from docs/r14_0_metric_definition.md:
  exact / partial / missing / wrong / not_applicable

Supports:
  - Jaccard 1.0 → exact (even with different string order)
  - Jaccard >= 0.5 and < 1.0 → partial
  - Jaccard < 0.5 → wrong
  - Jaccard = 0.5 → partial

Outputs:
  - Evaluation summary JSON (overall + field-level metrics)
  - Evaluation details JSONL (per-sample per-field scores)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# Ensure src/ is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_FIELDS = ["modality", "actor", "action", "condition", "constraint", "exception"]
_LABELS = ["exact", "partial", "missing", "wrong", "not_applicable"]
_MODALITY_ENUM = {"obligation", "prohibition", "permission", "definition"}

_SIMPLE_PUNCTUATION_TABLE = str.maketrans("", "", ".,;:!?\"'()-")


# ---------------------------------------------------------------------------
# Normalization and Jaccard
# ---------------------------------------------------------------------------

def _normalize(text: str | None) -> str:
    """Lowercase, collapse whitespace, remove simple punctuation."""
    if text is None:
        return ""
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = t.translate(_SIMPLE_PUNCTUATION_TABLE)
    return t.strip()


def _token_jaccard(a: str, b: str) -> float:
    """Jaccard similarity between token sets of two normalized strings."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Field scoring
# ---------------------------------------------------------------------------

def score_modality(pred_val: str | None, gold_val: str | None) -> str:
    """Score modality as a closed-set enum. Only exact/wrong/missing/NA."""
    p = (pred_val or "").lower().strip() if pred_val else None
    g = (gold_val or "").lower().strip() if gold_val else None

    if not g and not p:
        return "not_applicable"
    if g and not p:
        return "missing"
    if not g and p:
        return "wrong"
    if p == g:
        return "exact"
    return "wrong"


def score_text_field(pred_val: str | None, gold_val: str | None) -> str:
    """Score a free-text field using Jaccard overlap.

    Returns: exact | partial | missing | wrong | not_applicable
    """
    p = pred_val if pred_val else None
    g = gold_val if gold_val else None

    # Both null → NA
    if not g and not p:
        return "not_applicable"
    # Gold has value, pred missing → missing
    if g and not p:
        return "missing"
    # Pred has value, gold missing → wrong (false positive)
    if not g and p:
        return "wrong"

    # Both non-null: compare
    p_norm = _normalize(p)
    g_norm = _normalize(g)

    # Exact: normalized string equality OR Jaccard = 1.0
    if p_norm == g_norm:
        return "exact"

    # Check Jaccard
    jaccard = _token_jaccard(p_norm, g_norm)

    # Jaccard = 1.0 → exact (token-set equivalence, order may differ)
    if jaccard >= 1.0:
        return "exact"

    # Jaccard >= 0.5 → partial
    if jaccard >= 0.5:
        return "partial"

    # Jaccard < 0.5 → wrong
    return "wrong"


# ---------------------------------------------------------------------------
# Per-sample scoring
# ---------------------------------------------------------------------------

def score_one(prediction: dict, gold: dict) -> dict:
    """Score one prediction against one gold record."""
    sample_id = prediction.get("sample_id", "unknown")
    pred_fields = prediction.get("prediction_fields", {})
    gold_fields = gold.get("gold_fields", {})

    field_scores: dict[str, str] = {}
    for field in _FIELDS:
        pred_f = pred_fields.get(field, {})
        gold_f = gold_fields.get(field, {})

        pred_val = pred_f.get("value") if isinstance(pred_f, dict) else pred_f
        gold_val = gold_f.get("value") if isinstance(gold_f, dict) else gold_f

        if field == "modality":
            field_scores[field] = score_modality(pred_val, gold_val)
        else:
            field_scores[field] = score_text_field(pred_val, gold_val)

    return {
        "sample_id": sample_id,
        "field_scores": field_scores,
    }


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

def _compute_field_metrics(
    field: str,
    counts: dict[str, int],
    total_applicable: int,
    total_predictions: int,
) -> dict[str, float]:
    """Compute strict and lenient metrics for one field."""
    exact = counts.get("exact", 0)
    partial = counts.get("partial", 0)
    missing = counts.get("missing", 0)
    wrong = counts.get("wrong", 0)

    # Predictions made on applicable samples (predicted non-null for applicable):
    # For strict: correct = exact, incorrect = partial + missing + wrong
    # For lenient: correct = exact + partial, incorrect = missing + wrong

    predicted_non_null = exact + partial + wrong  # non-null pred on applicable

    # Strict
    if predicted_non_null > 0:
        strict_precision = exact / predicted_non_null
    else:
        strict_precision = 0.0

    if total_applicable > 0:
        strict_recall = exact / total_applicable
    else:
        strict_recall = 0.0

    if strict_precision + strict_recall > 0:
        strict_f1 = 2 * strict_precision * strict_recall / (strict_precision + strict_recall)
    else:
        strict_f1 = 0.0

    # Lenient
    lenient_correct = exact + partial
    if predicted_non_null > 0:
        lenient_precision = lenient_correct / predicted_non_null
    else:
        lenient_precision = 0.0

    if total_applicable > 0:
        lenient_recall = lenient_correct / total_applicable
    else:
        lenient_recall = 0.0

    if lenient_precision + lenient_recall > 0:
        lenient_f1 = 2 * lenient_precision * lenient_recall / (lenient_precision + lenient_recall)
    else:
        lenient_f1 = 0.0

    # Accuracy: exact / total_applicable
    accuracy = exact / total_applicable if total_applicable > 0 else 0.0

    return {
        "field": field,
        "applicable_gold_count": total_applicable,
        "exact_count": exact,
        "partial_count": partial,
        "missing_count": missing,
        "wrong_count": wrong,
        "not_applicable_count": total_predictions - total_applicable,
        "strict_precision": round(strict_precision, 4),
        "strict_recall": round(strict_recall, 4),
        "strict_f1": round(strict_f1, 4),
        "lenient_precision": round(lenient_precision, 4),
        "lenient_recall": round(lenient_recall, 4),
        "lenient_f1": round(lenient_f1, 4),
        "field_exact_accuracy": round(accuracy, 4),
    }


def _micro_average(
    field_metrics: list[dict],
    prefix: str,
) -> dict[str, float]:
    """Micro-average across all fields."""
    total_exact = sum(m["exact_count"] for m in field_metrics)
    total_partial = sum(m["partial_count"] for m in field_metrics)
    total_missing = sum(m["missing_count"] for m in field_metrics)
    total_wrong = sum(m["wrong_count"] for m in field_metrics)
    total_applicable = sum(m["applicable_gold_count"] for m in field_metrics)

    predicted_non_null = total_exact + total_partial + total_wrong

    # Strict
    sp = total_exact / predicted_non_null if predicted_non_null > 0 else 0.0
    sr = total_exact / total_applicable if total_applicable > 0 else 0.0
    sf1 = 2 * sp * sr / (sp + sr) if (sp + sr) > 0 else 0.0

    # Lenient
    lenient_correct = total_exact + total_partial
    lp = lenient_correct / predicted_non_null if predicted_non_null > 0 else 0.0
    lr = lenient_correct / total_applicable if total_applicable > 0 else 0.0
    lf1 = 2 * lp * lr / (lp + lr) if (lp + lr) > 0 else 0.0

    return {
        f"{prefix}_precision": round(sp, 4),
        f"{prefix}_recall": round(sr, 4),
        f"{prefix}_f1": round(sf1, 4),
        f"{prefix}_lenient_precision": round(lp, 4),
        f"{prefix}_lenient_recall": round(lr, 4),
        f"{prefix}_lenient_f1": round(lf1, 4),
    }


def evaluate(predictions: list[dict], gold_records: list[dict]) -> tuple[dict, list[dict]]:
    """Evaluate predictions against gold annotations."""
    # Build gold lookup
    gold_by_id: dict[str, dict] = {g["sample_id"]: g for g in gold_records}

    # Validate IDs match
    pred_ids = {p["sample_id"] for p in predictions}
    gold_ids = set(gold_by_id.keys())
    if pred_ids != gold_ids:
        missing = gold_ids - pred_ids
        extra = pred_ids - gold_ids
        raise ValueError(f"ID mismatch: missing={sorted(missing)}, extra={sorted(extra)}")

    details: list[dict] = []
    field_counts: dict[str, dict[str, int]] = {
        f: {label: 0 for label in _LABELS} for f in _FIELDS
    }

    for pred in predictions:
        sid = pred["sample_id"]
        gold = gold_by_id[sid]

        detail = score_one(pred, gold)
        details.append(detail)

        for field in _FIELDS:
            label = detail["field_scores"].get(field, "wrong")
            if label in field_counts[field]:
                field_counts[field][label] += 1
            else:
                field_counts[field]["wrong"] += 1

    # Build field-level metrics
    n = len(predictions)
    field_metrics: list[dict] = []
    for field in _FIELDS:
        counts = field_counts[field]
        na = counts.get("not_applicable", 0)
        applicable = n - na
        fm = _compute_field_metrics(field, counts, applicable, n)
        field_metrics.append(fm)

    # Micro-average (strict)
    micro_strict = _micro_average(field_metrics, "micro_strict")
    # No separate micro lenient — it's the same micro with lenient counts
    # Actually, let's compute micro for both strict and lenient separately

    # Macro-F1 (average of per-field strict F1)
    macro_strict_f1 = sum(m["strict_f1"] for m in field_metrics) / len(field_metrics)
    macro_lenient_f1 = sum(m["lenient_f1"] for m in field_metrics) / len(field_metrics)

    # Overall field exact accuracy: sum(exact) / sum(applicable)
    total_exact = sum(m["exact_count"] for m in field_metrics)
    total_applicable = sum(m["applicable_gold_count"] for m in field_metrics)
    overall_accuracy = total_exact / total_applicable if total_applicable > 0 else 0.0

    summary = {
        "stage": "R14.2",
        "method": "rule_only",
        "sample_count": n,
        "real_api_call_performed": False,
        "llm_call_performed": False,
        "rule_plus_llm_experiment_run": False,
        "benchmark": False,
        "method_validation": False,
        "sun_reproduction": False,
        "llm_superiority_claim": False,
        "overall_field_exact_accuracy": round(overall_accuracy, 4),
        "strict_precision": micro_strict["micro_strict_precision"],
        "strict_recall": micro_strict["micro_strict_recall"],
        "strict_f1": micro_strict["micro_strict_f1"],
        "lenient_partial_precision": micro_strict["micro_strict_lenient_precision"],
        "lenient_partial_recall": micro_strict["micro_strict_lenient_recall"],
        "lenient_partial_f1": micro_strict["micro_strict_lenient_f1"],
        "macro_strict_f1": round(macro_strict_f1, 4),
        "micro_strict_f1": micro_strict["micro_strict_f1"],
        "macro_lenient_f1": round(macro_lenient_f1, 4),
        "micro_lenient_f1": micro_strict["micro_strict_lenient_f1"],
        "field_level_summary": {m["field"]: m for m in field_metrics},
    }

    return summary, details


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="R14 field-level evaluator")
    parser.add_argument("--predictions", required=True, help="Path to predictions JSONL")
    parser.add_argument("--gold", required=True, help="Path to gold JSONL")
    parser.add_argument("--summary", required=True, help="Path to output summary JSON")
    parser.add_argument("--details", required=True, help="Path to output details JSONL")
    args = parser.parse_args()

    # Load predictions
    predictions: list[dict] = []
    with open(args.predictions, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            predictions.append(json.loads(stripped))

    # Load gold
    gold_records: list[dict] = []
    with open(args.gold, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            gold_records.append(json.loads(stripped))

    summary, details = evaluate(predictions, gold_records)

    # Write summary
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    with open(args.summary, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    # Write details
    Path(args.details).parent.mkdir(parents=True, exist_ok=True)
    with open(args.details, "w", encoding="utf-8") as fh:
        for d in details:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"R14 evaluation: summary → {args.summary}, details → {args.details}")
    print(f"  overall_field_exact_accuracy = {summary['overall_field_exact_accuracy']}")
    print(f"  strict_f1 (micro)            = {summary['strict_f1']}")
    print(f"  macro_strict_f1              = {summary['macro_strict_f1']}")
    print(f"  lenient_f1 (micro)           = {summary['lenient_partial_f1']}")
    print(f"  macro_lenient_f1             = {summary['macro_lenient_f1']}")


if __name__ == "__main__":
    main()

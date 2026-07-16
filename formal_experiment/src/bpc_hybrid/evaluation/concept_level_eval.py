"""Concept-level evaluation matching Sun et al. (2024) Table 8 methodology.

Sun's evaluation approach:
  - Counts individual concepts (spans) across ALL sentences, not per-sentence Jaccard.
  - For each (sentence, field) pair:
    * Gold concept: exists if gold has a non-null value for that field
    * Extracted concept: exists if system extracted a non-null value
    * If both exist → compare: matched (overlap) or misclassified (no overlap)
    * If gold exists but no extraction → missed
    * If extraction exists but no gold → false positive (extra extraction)
  - P = Matched / Extracted
  - R = Matched / GroundTruth
  - Per-field and overall metrics

This is fundamentally different from sentence-level Jaccard evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


_FIELDS = ["modality", "actor", "action", "condition", "constraint", "exception"]


def _normalize(text: str) -> str:
    """Normalize text for comparison."""
    t = text.lower()
    t = re.sub(r'[^\w\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def _token_jaccard(a: str, b: str) -> float:
    """Compute Jaccard similarity over token sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def _concept_match(gold_val: str, pred_val: str, field_name: str = "", threshold: float = 0.3) -> bool:
    """Determine if a predicted concept matches a gold concept.
    
    Uses token overlap with a lenient threshold (default 0.3) for concept-level matching.
    For modality, uses exact match on normalized values.
    """
    g = _normalize(gold_val)
    p = _normalize(pred_val)
    
    if not g or not p:
        return False
    
    # Modality: exact match
    if field_name == "modality":
        return g == p
    
    # For other fields: check if the core content overlaps
    # Strategy 1: Exact match
    if g == p:
        return True
    
    # Strategy 2: One contains the other (after normalization)
    if g in p or p in g:
        return True
    
    # Strategy 3: Token Jaccard ≥ threshold
    jac = _token_jaccard(g, p)
    if jac >= threshold:
        return True
    
    # Strategy 4: Significant token overlap (at least 50% of shorter side's tokens)
    tokens_g = set(g.split())
    tokens_p = set(p.split())
    overlap = tokens_g & tokens_p
    min_len = min(len(tokens_g), len(tokens_p))
    if min_len > 0 and len(overlap) / min_len >= 0.5:
        return True
    
    return False


@dataclass
class ConceptMatch:
    """One concept-level match result for a (sentence, field) pair."""
    sample_id: str
    field: str
    gold_val: str | None
    pred_val: str | None
    status: str  # "matched", "misclassified", "missed", "extra_fp", "both_empty"


@dataclass
class ConceptLevelMetrics:
    """Concept-level evaluation results matching Sun Table 8 format."""
    # Overall counts
    total_gold_concepts: int = 0
    total_extracted_concepts: int = 0
    total_matched: int = 0
    total_misclassified: int = 0
    total_missed: int = 0
    total_extra_fp: int = 0
    
    # Per-field counts
    field_gold: dict = field(default_factory=dict)
    field_extracted: dict = field(default_factory=dict)
    field_matched: dict = field(default_factory=dict)
    field_misclassified: dict = field(default_factory=dict)
    field_missed: dict = field(default_factory=dict)
    
    # Computed metrics
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    field_precision: dict = field(default_factory=dict)
    field_recall: dict = field(default_factory=dict)
    field_f1: dict = field(default_factory=dict)
    
    # Details
    details: list = field(default_factory=list)


def evaluate_concept_level(
    gold_map: dict,
    predictions: list[dict],
    match_threshold: float = 0.3,
    method_name: str = "unknown",
) -> ConceptLevelMetrics:
    """Evaluate at concept level matching Sun et al. (2024) methodology.
    
    Args:
        gold_map: {sample_id: {"gold_fields": {field: {"value": ..., "applicable": bool}}}}
        predictions: [{"sample_id": ..., "fields": {field: value}}]
        match_threshold: Jaccard threshold for concept matching (default 0.3, lenient)
        method_name: Name of the extraction method
    
    Returns:
        ConceptLevelMetrics with Sun Table 8 format
    """
    metrics = ConceptLevelMetrics()
    metrics.field_gold = {f: 0 for f in _FIELDS}
    metrics.field_extracted = {f: 0 for f in _FIELDS}
    metrics.field_matched = {f: 0 for f in _FIELDS}
    metrics.field_misclassified = {f: 0 for f in _FIELDS}
    metrics.field_missed = {f: 0 for f in _FIELDS}
    
    # Build prediction map
    pred_map = {p["sample_id"]: p["fields"] for p in predictions}
    
    for sid, gold_obj in gold_map.items():
        gold_fields = gold_obj.get("gold_fields", {})
        pred_fields = pred_map.get(sid, {})
        
        for f in _FIELDS:
            gold_entry = gold_fields.get(f, {})
            gold_val = gold_entry.get("value")
            gold_applicable = gold_entry.get("applicable", False)
            pred_val = pred_fields.get(f)
            
            # Normalize
            gold_has = bool(gold_val and str(gold_val).strip() and str(gold_val).lower() not in ("null", "none", "n/a"))
            pred_has = bool(pred_val and str(pred_val).strip() and str(pred_val).lower() not in ("null", "none", "n/a"))
            
            if gold_has:
                metrics.total_gold_concepts += 1
                metrics.field_gold[f] += 1
            
            if pred_has:
                metrics.total_extracted_concepts += 1
                metrics.field_extracted[f] += 1
            
            # Determine status
            if gold_has and pred_has:
                if _concept_match(str(gold_val), str(pred_val), f, match_threshold):
                    status = "matched"
                    metrics.total_matched += 1
                    metrics.field_matched[f] += 1
                else:
                    status = "misclassified"
                    metrics.total_misclassified += 1
                    metrics.field_misclassified[f] += 1
            elif gold_has and not pred_has:
                status = "missed"
                metrics.total_missed += 1
                metrics.field_missed[f] += 1
            elif not gold_has and pred_has:
                status = "extra_fp"
                metrics.total_extra_fp += 1
            else:
                status = "both_empty"
            
            metrics.details.append(ConceptMatch(
                sample_id=sid, field=f,
                gold_val=str(gold_val) if gold_val else None,
                pred_val=str(pred_val) if pred_val else None,
                status=status,
            ))
    
    # Compute metrics (matching Sun's formulas)
    matched = metrics.total_matched
    extracted = metrics.total_extracted_concepts
    gold = metrics.total_gold_concepts
    
    metrics.precision = matched / extracted if extracted > 0 else 0.0
    metrics.recall = matched / gold if gold > 0 else 0.0
    metrics.f1 = (2 * metrics.precision * metrics.recall / (metrics.precision + metrics.recall)
                  if (metrics.precision + metrics.recall) > 0 else 0.0)
    
    for f in _FIELDS:
        m = metrics.field_matched[f]
        e = metrics.field_extracted[f]
        g = metrics.field_gold[f]
        fp = m / e if e > 0 else 0.0
        fr = m / g if g > 0 else 0.0
        metrics.field_precision[f] = round(fp, 4)
        metrics.field_recall[f] = round(fr, 4)
        metrics.field_f1[f] = round(2 * fp * fr / (fp + fr), 4) if (fp + fr) > 0 else 0.0
    
    return metrics


def print_sun_table8(metrics: ConceptLevelMetrics, method_name: str = ""):
    """Print results in Sun Table 8 format."""
    print(f"\n{'=' * 80}")
    print(f"Concept-Level Evaluation: {method_name}")
    print(f"{'=' * 80}")
    print(f"Total ground truth concepts: {metrics.total_gold_concepts}")
    print(f"Total extracted concepts:    {metrics.total_extracted_concepts}")
    print(f"Matched:                     {metrics.total_matched}")
    print(f"Misclassified:               {metrics.total_misclassified}")
    print(f"Missed:                      {metrics.total_missed}")
    print(f"Extra FP:                    {metrics.total_extra_fp}")
    print(f"\nOverall: P={metrics.precision:.1%} R={metrics.recall:.1%} F1={metrics.f1:.1%}")
    print(f"\n{'Field':<15} {'Gold':>5} {'Extract':>8} {'Match':>6} {'Miscl':>6} {'Miss':>5} {'P':>8} {'R':>8} {'F1':>8}")
    print("-" * 80)
    for f in _FIELDS:
        print(f"{f:<15} {metrics.field_gold[f]:>5} {metrics.field_extracted[f]:>8} "
              f"{metrics.field_matched[f]:>6} {metrics.field_misclassified[f]:>6} "
              f"{metrics.field_missed[f]:>5} "
              f"{metrics.field_precision[f]:>8.1%} {metrics.field_recall[f]:>8.1%} "
              f"{metrics.field_f1[f]:>8.1%}")


# Sun's actual results for comparison
SUN_TABLE8_REFERENCE = {
    "total_gold": 443,
    "total_extracted": 431,
    "total_matched": 422,
    "total_misclassified": 9,
    "total_missed": 21,
    "overall_precision": 0.979,
    "overall_recall": 0.953,
    "fields": {
        "modality":    {"p": 0.988, "r": 0.976},
        "actor":       {"p": 0.991, "r": 0.924},
        "action":      {"p": 0.986, "r": 0.986},
        "condition":   {"p": 1.000, "r": 0.869},
        "constraint":  {"p": 0.895, "r": 0.971},
        "exception":   {"p": 0.933, "r": 0.933},
    }
}

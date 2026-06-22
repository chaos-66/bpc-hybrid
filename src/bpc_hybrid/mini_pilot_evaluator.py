"""
R13.4.1 Local Mini-pilot Evaluator

Field-level scoring for 8-sample mini-gold evaluation.
Supports modality exact match and text-field exact/partial/missing/wrong/not_applicable scoring.
No real API, no network, no .env — purely local mechanics.
"""
import json
import re
from typing import Any, Optional


# ---------------------------------------------------------------------------
# JSONL helpers
# ---------------------------------------------------------------------------

def load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file, returning a list of parsed dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def write_jsonl(path: str, records: list[dict]) -> None:
    """Write a list of dicts to a JSONL file."""
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_json(path: str, obj: Any) -> None:
    """Write a JSON-serialisable object to a file."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_SIMPLE_PUNCTUATION_TABLE = str.maketrans("", "", ".,;:!?\"'()-")


def _normalize_text(text: Optional[str]) -> Optional[str]:
    """Normalize a text field for comparison.

    Steps:
      1. lowercase
      2. strip leading/trailing whitespace
      3. collapse internal whitespace to single spaces
      4. remove simple punctuation ``.,;:!?\"'()-``
    """
    if text is None:
        return None
    t = text.lower().strip()
    t = re.sub(r"\s+", " ", t)
    t = t.translate(_SIMPLE_PUNCTUATION_TABLE)
    return t


def _token_overlap_ratio(a: str, b: str) -> float:
    """Jaccard-like token overlap between two normalised strings."""
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
# Schema validation
# ---------------------------------------------------------------------------

_REQUIRED_TOP_FIELDS = {"sample_id", "source_id", "predicted", "runtime", "schema_valid"}
_REQUIRED_PREDICTED_FIELDS = {"modality", "actor", "action", "condition", "constraint", "exception"}


def validate_prediction_record(record: dict) -> bool:
    """Return True if the record has all required top-level fields,
    schema_valid is boolean True, and predicted has all required fields."""
    if not isinstance(record, dict):
        return False
    missing_top = _REQUIRED_TOP_FIELDS - set(record.keys())
    if missing_top:
        return False
    # schema_valid must be boolean True (string "false" or False → invalid)
    if record.get("schema_valid") is not True:
        return False
    predicted = record.get("predicted")
    if not isinstance(predicted, dict):
        return False
    missing_pred = _REQUIRED_PREDICTED_FIELDS - set(predicted.keys())
    if missing_pred:
        return False
    return True


# ---------------------------------------------------------------------------
# Field scoring
# ---------------------------------------------------------------------------

def score_modality(pred_modality: Optional[str], gold_modality: Optional[str]) -> str:
    """Score modality field — exact match only (no partial)."""
    if not pred_modality and gold_modality:
        return "missing"
    if pred_modality and not gold_modality:
        return "wrong"
    if (pred_modality or "").lower().strip() == (gold_modality or "").lower().strip():
        return "exact"
    return "wrong"


def score_text_field(pred_value: Optional[str], gold_value: Optional[str]) -> str:
    """Score a text field using the five-label system.

    Returns: exact | partial | missing | wrong | not_applicable
    """
    p = pred_value if pred_value else None
    g = gold_value if gold_value else None

    # Both absent → not_applicable
    if not g and not p:
        return "not_applicable"

    # Gold present, pred absent → missing
    if g and not p:
        return "missing"

    # Gold absent, pred present → wrong (hallucination)
    if not g and p:
        return "wrong"

    # Both present — normalize and compare
    p_norm = _normalize_text(p) or ""
    g_norm = _normalize_text(g) or ""

    if p_norm == g_norm:
        return "exact"

    # One contains the other → partial
    if (len(p_norm) > 0 and len(g_norm) > 0 and
            (p_norm in g_norm or g_norm in p_norm)):
        return "partial"

    # Token overlap >= 0.5 → partial
    if _token_overlap_ratio(p_norm, g_norm) >= 0.5:
        return "partial"

    return "wrong"


# ---------------------------------------------------------------------------
# Failure category derivation
# ---------------------------------------------------------------------------

def _derive_failure_categories(field_scores: dict, runtime: Optional[dict],
                               schema_valid: bool) -> list[str]:
    """Derive failure category list from field scores and runtime metadata."""
    failures: list[str] = []

    if not schema_valid:
        failures.append("schema_invalid")

    # modality
    mod_score = field_scores.get("modality", "exact")
    if mod_score in ("wrong", "missing"):
        failures.append("modality_wrong")

    # actor
    if field_scores.get("actor") == "missing":
        failures.append("actor_missing")

    # action
    if field_scores.get("action") == "missing":
        failures.append("action_missing")

    # condition
    if field_scores.get("condition") in ("wrong", "missing"):
        failures.append("condition_wrong")

    # constraint
    if field_scores.get("constraint") in ("wrong", "missing"):
        failures.append("constraint_wrong")

    # exception
    if field_scores.get("exception") in ("wrong", "missing"):
        failures.append("exception_wrong")

    # runtime error category
    if isinstance(runtime, dict):
        ec = runtime.get("error_category")
        if ec and isinstance(ec, str):
            failures.append(ec)

    return sorted(set(failures))


# ---------------------------------------------------------------------------
# Per-prediction scoring
# ---------------------------------------------------------------------------

def score_prediction(
    candidate: dict,
    gold: dict,
    prediction: dict,
) -> dict:
    """Score a single prediction against candidate and gold records.

    Returns an evaluation detail dict.
    """
    sample_id = prediction.get("sample_id", "unknown")
    source_id = prediction.get("source_id", "unknown")

    # Structural validation (includes schema_valid bool check)
    schema_valid = validate_prediction_record(prediction)

    pred = prediction.get("predicted", {}) if isinstance(prediction.get("predicted"), dict) else {}
    g = gold if isinstance(gold, dict) else {}

    field_scores = {
        "modality": score_modality(pred.get("modality"), g.get("modality")),
        "actor": score_text_field(pred.get("actor"), g.get("actor")),
        "action": score_text_field(pred.get("action"), g.get("action")),
        "condition": score_text_field(pred.get("condition"), g.get("condition")),
        "constraint": score_text_field(pred.get("constraint"), g.get("constraint")),
        "exception": score_text_field(pred.get("exception"), g.get("exception")),
    }

    runtime = prediction.get("runtime")
    failure_categories = _derive_failure_categories(field_scores, runtime, schema_valid)

    return {
        "sample_id": sample_id,
        "source_id": source_id,
        "schema_valid": schema_valid,
        "field_scores": field_scores,
        "failure_categories": failure_categories,
        "notes": "",
    }


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

# All evaluation dimensions (in order)
_DIMENSIONS = ["modality", "actor", "action", "condition", "constraint", "exception"]
_LABELS = ["exact", "partial", "missing", "wrong", "not_applicable"]


def _empty_field_counts() -> dict:
    return {label: 0 for label in _LABELS}


def evaluate_predictions(
    candidates: list[dict],
    gold_records: list[dict],
    predictions: list[dict],
    stage: str = "R13.4.1",
    claim_boundary: str = "",
) -> tuple[dict, list[dict]]:
    """Evaluate all predictions against gold records.

    Returns (summary_dict, details_list).
    Raises ValueError on sample_id mismatch between gold and predictions.

    Parameters
    ----------
    stage : str
        Stage identifier for the summary metadata (default ``"R13.4.1"``).
    claim_boundary : str
        Explicit claim boundary string. When empty, auto-derives from
        ``real_api_call`` detection.
    """
    # Detect duplicate sample_ids
    gold_ids_list = [g.get("sample_id", "") for g in gold_records]
    if len(gold_ids_list) != len(set(gold_ids_list)):
        raise ValueError("duplicate sample_id in gold records")
    pred_ids_list = [p.get("sample_id", "") for p in predictions]
    if len(pred_ids_list) != len(set(pred_ids_list)):
        raise ValueError("duplicate sample_id in predictions")
    cand_ids_list = [c.get("sample_id", "") for c in candidates]
    if len(cand_ids_list) != len(set(cand_ids_list)):
        raise ValueError("duplicate sample_id in candidates")

    # Index gold by sample_id
    gold_by_id: dict[str, dict] = {}
    for g in gold_records:
        sid = g.get("sample_id", "")
        gold_by_id[sid] = g

    # Index candidates by sample_id (optional, for metadata)
    cand_by_id: dict[str, dict] = {}
    for c in candidates:
        sid = c.get("sample_id", "")
        cand_by_id[sid] = c

    # Check sample_id alignment
    pred_ids = {p.get("sample_id") for p in predictions}
    gold_ids = set(gold_by_id.keys())
    if pred_ids != gold_ids:
        missing_in_pred = gold_ids - pred_ids
        extra_in_pred = pred_ids - gold_ids
        msgs: list[str] = []
        if missing_in_pred:
            msgs.append(f"gold sample_ids not in predictions: {sorted(missing_in_pred)}")
        if extra_in_pred:
            msgs.append(f"prediction sample_ids not in gold: {sorted(extra_in_pred)}")
        raise ValueError("sample_id mismatch: " + "; ".join(msgs))

    details: list[dict] = []
    field_counts: dict[str, dict] = {dim: _empty_field_counts() for dim in _DIMENSIONS}
    failure_counts: dict[str, int] = {}
    schema_valid_count = 0

    for pred in predictions:
        sid = pred.get("sample_id")
        gold = gold_by_id.get(sid, {})
        candidate = cand_by_id.get(sid, {})

        detail = score_prediction(candidate, gold, pred)
        details.append(detail)

        # Accumulate field counts
        for dim in _DIMENSIONS:
            label = detail["field_scores"].get(dim, "wrong")
            if label in _LABELS:
                field_counts[dim][label] += 1
            else:
                field_counts[dim]["wrong"] += 1

        # Accumulate failure counts
        for fc in detail.get("failure_categories", []):
            failure_counts[fc] = failure_counts.get(fc, 0) + 1

        if detail.get("schema_valid"):
            schema_valid_count += 1

    # Derive real_api_call and type from prediction runtime metadata
    real_api_call = any(
        isinstance(p.get("runtime"), dict) and p["runtime"].get("real_api_call_performed") is True
        for p in predictions
    )

    # Derive claim_boundary if not explicitly provided
    if not claim_boundary:
        if real_api_call:
            claim_boundary = (
                "8-sample real API mini-pilot only. "
                "No benchmark, no method validation, no Sun reproduction."
            )
        else:
            claim_boundary = (
                "Mock local evaluator test only. "
                "No benchmark, no method validation, no Sun reproduction."
            )

    summary: dict = {
        "stage": stage,
        "type": "real_mini_pilot_evaluation" if real_api_call else "mock_local_evaluation",
        "real_api_call": real_api_call,
        "benchmark": False,
        "method_validation": False,
        "sun_reproduction": False,
        "sample_count": len(predictions),
        "schema_valid_count": schema_valid_count,
        "field_score_counts": field_counts,
        "failure_category_counts": failure_counts,
        "claim_boundary": claim_boundary,
    }

    return summary, details

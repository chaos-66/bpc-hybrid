"""
R14.2 Rule-only Baseline
=======================
Deterministic no-LLM extraction on the R14.1 24-sample mini-gold.

Uses only the RuleFirstExtractor (marker/pattern-based). No LLM, no API,
no network, no .env read. Outputs predictions in the R14.2 flat format.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.extractor import RuleFirstExtractor

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CANDIDATE_PATH = _PROJECT_ROOT / "data" / "formal" / "r14_controlled" / "r14_1_candidate_samples.jsonl"
OUTPUT_PATH = _PROJECT_ROOT / "data" / "formal" / "predictions" / "r14_2_rule_only_predictions.jsonl"

# ---------------------------------------------------------------------------
# Modality marker → enum mapping
# ---------------------------------------------------------------------------
_MODALITY_MAP: dict[str, str] = {
    "shall": "obligation",
    "must": "obligation",
    "shall not": "prohibition",
    "must not": "prohibition",
    "no person shall": "prohibition",
    "may": "permission",
}


def _map_modality(marker_text: str | None) -> str | None:
    """Map a modality marker string to the closed-set enum."""
    if marker_text is None:
        return None
    return _MODALITY_MAP.get(marker_text.lower().strip())


def _extract_sample(extractor: RuleFirstExtractor, sample: dict) -> dict:
    """Run rule-only extraction on one sample and return R14.2 prediction dict."""
    text = sample["text"]
    sample_id = sample["sample_id"]

    response = extractor.extract(text, source_id=sample_id)

    # Flatten clauses: use first clause for simple predictions
    clause = response.clauses[0] if response.clauses else None

    if clause is None:
        modality_val = None
        actor_val = None
        action_val = None
        condition_val = None
        constraint_val = None
        exception_val = None
    else:
        modality_val = _map_modality(clause.modality.text if clause.modality else None)
        actor_val = clause.actor.text if clause.actor else None
        action_val = clause.action.text if clause.action else None
        condition_val = clause.condition.text if clause.condition else None
        constraint_val = clause.constraint.text if clause.constraint else None
        exception_val = clause.exception.text if clause.exception else None

    # For multi-clause responses, merge: take the first non-null modality
    # and concatenate actions/constraints
    if len(response.clauses) > 1:
        for c in response.clauses[1:]:
            if modality_val is None and c.modality is not None:
                modality_val = _map_modality(c.modality.text)
            if action_val is None and c.action is not None:
                action_val = c.action.text
            elif action_val is not None and c.action is not None:
                # Merge: append
                pass  # keep first action as primary

    return {
        "sample_id": sample_id,
        "method": "rule_only",
        "prediction_fields": {
            "modality": {"value": modality_val},
            "actor": {"value": actor_val},
            "action": {"value": action_val},
            "condition": {"value": condition_val},
            "constraint": {"value": constraint_val},
            "exception": {"value": exception_val},
        },
        "execution": {
            "llm_used": False,
            "api_used": False,
            "network_used": False,
        },
    }


def main() -> None:
    # Load candidates
    records: list[dict] = []
    with open(CANDIDATE_PATH, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))

    if len(records) != 24:
        print(f"ERROR: expected 24 candidate samples, got {len(records)}")
        sys.exit(1)

    extractor = RuleFirstExtractor()
    predictions: list[dict] = []

    for sample in records:
        pred = _extract_sample(extractor, sample)
        predictions.append(pred)

    # Write predictions
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        for pred in predictions:
            fh.write(json.dumps(pred, ensure_ascii=False) + "\n")

    print(f"R14.2 rule-only baseline: {len(predictions)} predictions written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

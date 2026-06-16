#!/usr/bin/env python3
"""Evaluate multi-clause extraction against gold data (R5).

Reads gold and predicted multi-clause extraction responses,
computes clause-level and field-level metrics, and prints a JSON
evaluation report.

Usage::

    # Generate predictions on-the-fly and evaluate:
    .venv/Scripts/python.exe scripts/evaluate_multi_clause.py \
        --gold data/prototype/gold_multiclause.jsonl \
        --input data/prototype/legal_sentences.jsonl

    # Evaluate from pre-computed predictions:
    .venv/Scripts/python.exe scripts/evaluate_multi_clause.py \
        --gold data/prototype/gold_multiclause.jsonl \
        --pred predictions.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

# ---- Ensure bpc_hybrid is importable when script is run directly ---------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


def _run_baseline(input_path: Path) -> Path:
    """Run the rule baseline and return a path to the predictions file."""
    # Use a temp file for predictions
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    tmp_path = Path(tmp.name)

    from bpc_hybrid.extractor import extract_rule_first

    with open(input_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rec = json.loads(line)
            sid = rec["id"]
            text = rec["text"]
            try:
                resp = extract_rule_first(text, source_id=sid)
                tmp.write(json.dumps(resp.to_dict()) + "\n")
            except Exception as exc:
                error_rec = {
                    "schema_version": "0.1.0",
                    "source_id": sid,
                    "source_text": text,
                    "clauses": [],
                }
                tmp.write(json.dumps(error_rec) + "\n")

    tmp.close()
    return tmp_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate multi-clause extraction on synthetic prototype data."
    )
    parser.add_argument(
        "--gold",
        required=True,
        type=Path,
        help="Path to gold JSONL file (MultiClauseExtractionResponse per line).",
    )
    pred_group = parser.add_mutually_exclusive_group()
    pred_group.add_argument(
        "--pred",
        type=Path,
        default=None,
        help="Path to predicted JSONL file. If not provided, use --input to generate.",
    )
    pred_group.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to legal_sentences.jsonl. Used to generate predictions on-the-fly.",
    )
    args = parser.parse_args()

    # --- Load gold -------------------------------------------------------
    from bpc_hybrid.evaluator import (
        EvaluationError,
        evaluate_responses,
        load_gold_responses,
        load_predicted_responses,
    )

    try:
        gold = load_gold_responses(args.gold)
    except (EvaluationError, Exception) as exc:
        print(f"ERROR loading gold: {exc}", file=sys.stderr)
        sys.exit(1)

    # --- Get predictions ------------------------------------------------
    pred_path = args.pred
    cleanup_pred = False
    if pred_path is None:
        if args.input is None:
            print(
                "ERROR: must provide either --pred or --input.", file=sys.stderr
            )
            sys.exit(1)
        pred_path = _run_baseline(args.input)
        cleanup_pred = True

    try:
        predicted = load_predicted_responses(pred_path)
    except (EvaluationError, Exception) as exc:
        print(f"ERROR loading predictions: {exc}", file=sys.stderr)
        if cleanup_pred:
            pred_path.unlink(missing_ok=True)
        sys.exit(1)

    # --- Evaluate --------------------------------------------------------
    try:
        report = evaluate_responses(gold, predicted)
    except EvaluationError as exc:
        print(f"ERROR during evaluation: {exc}", file=sys.stderr)
        sys.exit(1)

    print(report.to_json())

    # --- Cleanup ---------------------------------------------------------
    if cleanup_pred:
        pred_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

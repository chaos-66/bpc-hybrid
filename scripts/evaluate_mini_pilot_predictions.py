#!/usr/bin/env python3
"""
R13.4.1 CLI — Evaluate mini-pilot predictions against gold annotations.

Usage:
  python scripts/evaluate_mini_pilot_predictions.py \
      --candidates data/formal/processed/r13_3_candidate_samples.jsonl \
      --gold data/formal/gold/r13_3_manual_gold_template.jsonl \
      --predictions data/formal/predictions/r13_4_1_mock_predictions.jsonl \
      --summary-out data/formal/results/r13_4_1_mock_evaluation_summary.json \
      --details-out data/formal/results/r13_4_1_mock_evaluation_details.jsonl

This script:
  - Does NOT call any real API.
  - Does NOT read .env.
  - Does NOT access the network.
  - Only performs local file I/O and scoring.
"""
import argparse
import sys
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bpc_hybrid.mini_pilot_evaluator import (  # noqa: E402
    evaluate_predictions,
    load_jsonl,
    write_json,
    write_jsonl,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="R13.4.1 Local mini-pilot evaluator (no real API)"
    )
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidate samples JSONL",
    )
    parser.add_argument(
        "--gold",
        required=True,
        help="Path to gold annotations JSONL",
    )
    parser.add_argument(
        "--predictions",
        required=True,
        help="Path to prediction JSONL",
    )
    parser.add_argument(
        "--summary-out",
        required=True,
        help="Path to write evaluation summary JSON",
    )
    parser.add_argument(
        "--details-out",
        required=True,
        help="Path to write evaluation details JSONL",
    )
    args = parser.parse_args()

    # Load inputs
    for label, path in [
        ("candidates", args.candidates),
        ("gold", args.gold),
        ("predictions", args.predictions),
    ]:
        if not Path(path).is_file():
            print(f"ERROR: {label} file not found: {path}", file=sys.stderr)
            return 1

    try:
        candidates = load_jsonl(args.candidates)
        gold_records = load_jsonl(args.gold)
        predictions = load_jsonl(args.predictions)
    except Exception as exc:
        print(f"ERROR: failed to load input files: {exc}", file=sys.stderr)
        return 2

    # Ensure non-empty
    if not gold_records:
        print("ERROR: no gold records loaded", file=sys.stderr)
        return 3
    if not predictions:
        print("ERROR: no prediction records loaded", file=sys.stderr)
        return 4

    # Evaluate
    try:
        summary, details = evaluate_predictions(candidates, gold_records, predictions)
    except ValueError as exc:
        print(f"ERROR: evaluation failed: {exc}", file=sys.stderr)
        return 5

    # Write outputs
    try:
        write_json(args.summary_out, summary)
        write_jsonl(args.details_out, details)
    except Exception as exc:
        print(f"ERROR: failed to write output files: {exc}", file=sys.stderr)
        return 6

    print(f"Evaluation complete: {summary['sample_count']} samples")
    print(f"  schema_valid: {summary['schema_valid_count']}")
    print(f"  summary -> {args.summary_out}")
    print(f"  details -> {args.details_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

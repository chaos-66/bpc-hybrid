"""CLI wrapper for the EStG-150 v2 human_correction global validator.

The actual logic lives in
`formal_experiment.src.formal_experiment.estg150_validator.validate_global`.
This script is a thin CLI front-end so the existing
``python scripts/validate_human_correction.py`` command still works
and ``audit_project.py`` and the GUI can invoke the same code path.

Run from formal_experiment/ as:
    python scripts/validate_human_correction.py
    python scripts/validate_human_correction.py --json
    python scripts/validate_human_correction.py --path <other_file>

Exit codes:
  0  — format-valid
  2  — format-invalid (structural errors)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from formal_experiment.estg150_validator import validate_global  # noqa: E402


DEFAULT_PATH = (
    FORMAL_ROOT / "data" / "development" / "human_review"
    / "estg_150_human_correction_v1.json"
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", type=Path, default=DEFAULT_PATH)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = validate_global(args.path)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"path                          : {result['path']}")
        print(f"records                       : {result['n_records']}/150")
        print(f"approved_text_en              : {result['n_approved_en']}/150")
        print(f"translation unreviewed        : {result['n_translation_unreviewed']}/150")
        # The "six element" decision counter is across 6 fields × 150
        # records = 900 decisions, NOT 150 records. The display makes
        # this explicit so the denominator is never confused with a
        # per-record metric.
        print(f"six-element decisions unresolved: {result['n_field_decisions_unreviewed']}/{result['n_field_decisions_total']} (6 fields x 150 records)")
        print(f"six-element decisions resolved  : {result['n_field_decisions_resolved']}/{result['n_field_decisions_total']}")
        print(f"records fully decided         : {result['n_records_fully_decided']}/150")
        print(f"records incomplete            : {result['n_records_incomplete']}/150")
        print(f"review_state counts           : {result['review_state_counts']}")
        print(f"format_valid                  : {result['format_valid']}")
        print(f"review_ready                  : {result['review_ready']}")
        print(f"freeze_ready                  : {result['freeze_ready']}")
        if result["format_errors"]:
            print("format errors:")
            for e in result["format_errors"][:10]:
                print(" ", e)
        if result["review_blockers"]:
            print("review blockers (first 10):")
            for e in result["review_blockers"][:10]:
                print(" ", e)
        if result["freeze_blockers"]:
            print("freeze blockers (first 10):")
            for e in result["freeze_blockers"][:10]:
                print(" ", e)
    if not result["format_valid"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

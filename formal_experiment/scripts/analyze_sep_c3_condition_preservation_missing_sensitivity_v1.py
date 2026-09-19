# -*- coding: utf-8 -*-
"""CLI for the fixed 149-sample missing-response sensitivity analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import analyze_sep_c3_condition_preservation_bootstrap_v1 as bs  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "reports"
    / "sep_c3_condition_preservation_v1_missing_response_sensitivity.json"
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed 149-sample missing-response sensitivity bootstrap. "
            "Local files only; never calls an LLM."
        )
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--rc1", type=Path, required=True)
    parser.add_argument("--rc-keep", type=Path, required=True)
    parser.add_argument("--exclude-sample-id", default="estg_000074")
    parser.add_argument("--input", type=Path, default=bs.DEFAULT_INPUT)
    parser.add_argument("--gold", type=Path, default=bs.DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    result = bs.analyze_missing_sensitivity(
        base_path=args.base,
        rc1_path=args.rc1,
        rc_keep_path=args.rc_keep,
        excluded_sample_id=args.exclude_sample_id,
        input_path=args.input,
        gold_path=args.gold,
        output_path=args.output,
    )
    summary = {
        "output": str(args.output),
        "excluded_sample_id": result["excluded_sample_id"],
        "denominator_per_arm": result["denominator_per_arm"],
        "real_api_calls": 0,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
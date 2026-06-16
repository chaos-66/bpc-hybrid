#!/usr/bin/env python3
"""Run the rule-first baseline on legal sentences (R5).

Reads synthetic prototype sentences from a JSONL file, runs the
rule-first extractor on each, and prints predictions as JSONL to stdout.

Usage::

    .venv/Scripts/python.exe scripts/run_rule_baseline.py --input data/prototype/legal_sentences.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---- Ensure bpc_hybrid is importable when script is run directly ---------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SRC_ROOT = _PROJECT_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run rule-first baseline on synthetic prototype sentences."
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to JSONL file with sentences (each line: {id, text}).",
    )
    args = parser.parse_args()

    # --- Load sentences --------------------------------------------------
    sentences: list[dict[str, str]] = []
    with open(args.input, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            sentences.append(json.loads(line))

    # --- Import extractor (after arg parsing, for faster --help) --------
    from bpc_hybrid.extractor import extract_rule_first

    # --- Run extraction --------------------------------------------------
    for rec in sentences:
        sid = rec["id"]
        text = rec["text"]
        try:
            resp = extract_rule_first(text, source_id=sid)
            print(json.dumps(resp.to_dict()))
        except Exception as exc:
            # Emit an error record instead of crashing
            error_rec = {
                "schema_version": "0.1.0",
                "source_id": sid,
                "source_text": text,
                "clauses": [],
                "_error": f"{type(exc).__name__}: {exc}",
            }
            print(json.dumps(error_rec), file=sys.stderr)
            # Also print to stdout for clarity
            print(json.dumps(error_rec))


if __name__ == "__main__":
    main()

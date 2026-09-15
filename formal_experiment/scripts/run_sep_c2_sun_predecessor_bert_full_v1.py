# -*- coding: utf-8 -*-
"""CLI for the final-paper BERT-TextCNN predecessor rows.

Usage:
    python scripts/run_sep_c2_sun_predecessor_bert_full_v1.py \
        --method bert_base_uncased --model-root D:/.../sep_c2_models \
        --external-data-root D:/.../formal_experiment --publish
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_predecessors import common  # noqa: E402
from bpc_hybrid.sun_predecessors.runner_bert_full import (  # noqa: E402
    build_bert_full,
    render_bert_full_markdown,
)

METHODS = (
    "bert_base_uncased",
    "bert_base_cased",
    "bert_large_uncased",
    "bert_large_cased",
    "bert_legal_uncased",
)


def _payload(value: Any) -> bytes:
    return common.json_bytes(value)


def _expected_files(result: dict[str, Any]) -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    for rel, value in result["artifacts"].items():
        files[FORMAL_ROOT / rel] = _payload(value)
    files[FORMAL_ROOT / result["report_rel"]] = _payload(result["report"])
    files[FORMAL_ROOT / result["report_md_rel"]] = render_bert_full_markdown(
        result["report"]
    ).encode("utf-8")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True, choices=list(METHODS))
    parser.add_argument("--formal-root", type=Path, default=FORMAL_ROOT)
    parser.add_argument("--external-data-root", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_bert_full(
            Path(args.formal_root),
            Path(args.external_data_root),
            args.method,
            Path(args.model_root),
        )
        expected = _expected_files(result)
        if args.publish:
            existing = [path for path in expected if path.exists()]
            if existing:
                raise common.SunPredecessorError(
                    "refusing to overwrite existing artifacts: "
                    + ", ".join(str(path.relative_to(FORMAL_ROOT)) for path in existing[:8])
                )
            for path, payload in expected.items():
                common.write_bytes_atomic(path, payload)
            print(f"SEP-C2 {args.method} PUBLISHED")
        else:
            mismatches = []
            for path, payload in expected.items():
                if not path.is_file() or path.read_bytes() != payload:
                    mismatches.append(str(path.relative_to(FORMAL_ROOT)))
            if mismatches:
                raise common.SunPredecessorError(
                    "replay mismatch: " + ", ".join(mismatches[:8])
                )
            official = result["report"]["evaluation"]["official_evaluator"]
            print(f"SEP-C2 {args.method} REPLAY VERIFIED")
            print(f"task={result['report']['report_id']}")
            print(
                f"accuracy={official['accuracy']:.4f} macro_f1={official['macro_f1']:.4f} "
                f"records={result['report']['evaluation']['records_scored']} "
                f"missing={result['report']['evaluation']['records_missing']} "
                f"failed={result['report']['evaluation']['records_failed']} "
                f"unlabeled={result['report']['evaluation']['unlabeled_predictions']}"
            )
    except common.SunPredecessorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

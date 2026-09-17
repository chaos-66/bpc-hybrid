# -*- coding: utf-8 -*-
"""CLI for the SEP-C2 neural predecessor reconstruction (CF_RNN / CF_CNN).

The training corpus lives in the main workspace's ignored development data
store.  Use --external-data-root to point at it when running from a worktree:

    python scripts/run_sep_c2_sun_predecessor_neural_v1.py \
        --method cf_rnn --external-data-root D:/Paper/experiment/bpc-hybrid/formal_experiment \
        --publish
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
from bpc_hybrid.sun_predecessors.runner_neural import build_neural, render_neural_markdown  # noqa: E402


def _payload(value: Any) -> bytes:
    return common.json_bytes(value)


def _expected_files(result: dict[str, Any]) -> dict[Path, bytes]:
    files: dict[Path, bytes] = {}
    for rel, value in result["artifacts"].items():
        files[FORMAL_ROOT / rel] = _payload(value)
    files[FORMAL_ROOT / result["report_rel"]] = _payload(result["report"])
    files[FORMAL_ROOT / result["report_md_rel"]] = render_neural_markdown(
        result["report"]
    ).encode("utf-8")
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True, choices=["cf_rnn", "cf_cnn"])
    parser.add_argument("--formal-root", type=Path, default=FORMAL_ROOT)
    parser.add_argument(
        "--external-data-root",
        type=Path,
        required=True,
        help="main formal_experiment directory containing the ignored official modality splits/source ZIP",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = build_neural(
            Path(args.formal_root),
            Path(args.external_data_root),
            args.method,
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
                    "replay differs for: " + ", ".join(mismatches[:8])
                )
            print(f"SEP-C2 {args.method} REPLAY VERIFIED")
        report = result["report"]
        official = report["evaluation"]["official_evaluator"]
        print(f"task={report['report_id']}")
        print(
            "accuracy={:.4f} macro_f1={:.4f} records={} missing={} failed={} unlabeled={}".format(
                official["accuracy"],
                official["macro_f1"],
                report["evaluation"]["records_expected"],
                report["evaluation"]["records_missing"],
                report["evaluation"]["records_failed"],
                report["evaluation"]["unlabeled_predictions"],
            )
        )
        for row in official["per_class"]:
            print(
                "{class}: P={precision:.4f} R={recall:.4f} F1={f1:.4f}".format(**row)
            )
        print(
            "best_dev_macro_f1={:.4f} official_test_macro_f1={:.4f} new_llm_api_calls=0".format(
                report["training"]["best_dev"]["macro_f1"],
                report["official_clean_test"]["macro_f1"],
            )
        )
        return 0
    except (OSError, ValueError, common.SunPredecessorError) as exc:
        print(f"SEP-C2 neural predecessor runner refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
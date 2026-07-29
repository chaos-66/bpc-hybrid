"""Run the frozen S2.10 aggregate evaluator over explicit local files.

The evaluator is offline.  ``--claim-scope formal`` is fail-closed against the
project's independent final-readiness gate; there is no command-line override.
The output path must not already exist, which preserves run identity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage2_evaluation import (  # noqa: E402
    Stage2EvaluationError,
    evaluate_stage2,
    load_evaluator_contract,
    validate_evaluation_report,
)


DEFAULT_CONTRACT = ROOT / "configs" / "stage2_evaluator_s210.json"


def _load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        result: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as stream:
            for line_number, raw in enumerate(stream, 1):
                if not raw.strip():
                    continue
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise Stage2EvaluationError(
                        f"invalid JSONL at {path}:{line_number}"
                    ) from exc
                if not isinstance(item, dict):
                    raise Stage2EvaluationError(
                        f"JSONL item at {path}:{line_number} must be an object"
                    )
                result.append(item)
        return result
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2EvaluationError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise Stage2EvaluationError(f"JSON input must be an array of objects: {path}")
    return value


def _formal_ready() -> bool:
    from formal_experiment.status import collect_status

    return bool(collect_status().get("final_experiment_ready"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--attempts", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument(
        "--method",
        choices=("sun_rule_only", "sun_llm_fallback", "direct_llm"),
        required=True,
    )
    parser.add_argument("--expected-membership-sha256", required=True)
    parser.add_argument(
        "--claim-scope",
        choices=("synthetic_contract", "development", "formal"),
        required=True,
    )
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.output.exists():
        raise Stage2EvaluationError(
            f"refusing to overwrite existing evaluator output: {args.output}"
        )
    report = evaluate_stage2(
        _load_records(args.gold),
        _load_records(args.attempts),
        contract=load_evaluator_contract(args.contract),
        dataset_id=args.dataset_id,
        method_id=args.method,
        expected_membership_sha256=args.expected_membership_sha256,
        claim_scope=args.claim_scope,
        formal_ready=_formal_ready() if args.claim_scope == "formal" else False,
    )
    errors = validate_evaluation_report(report)
    if errors:
        raise Stage2EvaluationError("aggregate report is invalid: " + "; ".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sample_count": report["membership"]["sample_count"],
                "claim_scope": report["claim_scope"],
                "is_formal_performance_result": report["is_formal_performance_result"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

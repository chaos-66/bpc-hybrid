"""R14.5 — Descriptive Comparison of Rule-only vs Rule+LLM Outputs.

Reads already-computed R14.2 and R14.4 evaluation summaries/details.
Does NOT re-run any predictor, runner, or evaluator.
Does NOT call any API or LLM.

Usage::

    $env:BPC_HYBRID_DISABLE_PROJECT_ENV = "1"
    .venv/Scripts/python.exe scripts/compare_r14_rule_only_vs_rule_plus_llm.py \
        --rule-only-summary data/formal/results/r14_2_rule_only_evaluation_summary.json \
        --rule-llm-summary data/formal/results/r14_4_rule_plus_llm_evaluation_summary.json \
        --rule-only-details data/formal/results/r14_2_rule_only_evaluation_details.jsonl \
        --rule-llm-details data/formal/results/r14_4_rule_plus_llm_evaluation_details.jsonl \
        --summary-out data/formal/results/r14_5_rule_only_vs_rule_plus_llm_comparison_summary.json \
        --field-out data/formal/results/r14_5_rule_only_vs_rule_plus_llm_field_comparison.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")

COMPARISON_CLAIM_TYPE = "descriptive_small_scale_observation"
CLAIM_BOUNDARY = (
    "R14.5 is a descriptive comparison of two already accepted bounded pilot "
    "outputs. It does not prove generalized LLM advantage, does not validate "
    "a method, does not reproduce Sun et al., and is not a formal benchmark."
)

DESCRIPTIVE_DELTA_ONLY = "descriptive_delta_only"


def _safe_get(d: dict, key: str, default=None):
    return d.get(key, default)


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            records.append(json.loads(stripped))
    return records


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _delta(a: float, b: float) -> float:
    """Compute delta = a - b (R14.4 minus R14.2)."""
    return round(a - b, 6)


def build_comparison_summary(
    rule_only: dict,
    rule_llm: dict,
) -> dict:
    """Build the R14.5 comparison summary JSON."""
    # Overall metric keys to compare
    metric_keys = [
        "overall_field_exact_accuracy",
        "macro_strict_f1",
        "micro_strict_f1",
        "macro_lenient_f1",
        "micro_lenient_f1",
    ]

    overall_metrics: dict[str, dict] = {}
    deltas: dict[str, float] = {}
    for key in metric_keys:
        ro_val = _safe_get(rule_only, key)
        rl_val = _safe_get(rule_llm, key)
        available = ro_val is not None and rl_val is not None
        overall_metrics[key] = {
            "rule_only": ro_val,
            "rule_plus_llm": rl_val,
            "available": available,
        }
        if available:
            deltas[f"{key}_delta"] = _delta(rl_val, ro_val)
        else:
            deltas[f"{key}_delta"] = None

    return {
        "stage": "R14.5",
        "type": "descriptive_comparison",
        "sample_count": 24,
        "comparison": "rule_only_vs_rule_plus_llm_assisted",
        "rule_only_source_stage": "R14.2",
        "rule_plus_llm_source_stage": "R14.4",
        "real_api_call_performed": False,
        "llm_call_performed": False,
        "runner_rerun": False,
        "evaluator_rerun": False,
        "metrics_recomputed": False,
        "prediction_files_modified": False,
        "evaluation_files_modified": False,
        "benchmark": False,
        "method_validation": False,
        "sun_reproduction": False,
        "llm_superiority_claim": False,
        "comparison_claim_type": COMPARISON_CLAIM_TYPE,
        "claim_boundary": CLAIM_BOUNDARY,
        "overall_metrics": overall_metrics,
        "overall_deltas": deltas,
    }


def build_field_comparison(
    rule_only: dict,
    rule_llm: dict,
) -> list[dict]:
    """Build field-level comparison JSONL rows."""
    ro_fields = rule_only.get("field_level_summary", {})
    rl_fields = rule_llm.get("field_level_summary", {})

    rows: list[dict] = []
    for field in FIELDS:
        ro = ro_fields.get(field, {})
        rl = rl_fields.get(field, {})

        ro_exact = _safe_get(ro, "field_exact_accuracy", 0.0)
        ro_strict = _safe_get(ro, "strict_f1", 0.0)
        ro_lenient = _safe_get(ro, "lenient_f1", 0.0)
        rl_exact = _safe_get(rl, "field_exact_accuracy", 0.0)
        rl_strict = _safe_get(rl, "strict_f1", 0.0)
        rl_lenient = _safe_get(rl, "lenient_f1", 0.0)

        row = {
            "field": field,
            "rule_only": {
                "exact_accuracy": ro_exact,
                "strict_f1": ro_strict,
                "lenient_f1": ro_lenient,
            },
            "rule_plus_llm": {
                "exact_accuracy": rl_exact,
                "strict_f1": rl_strict,
                "lenient_f1": rl_lenient,
            },
            "delta": {
                "exact_accuracy": _delta(rl_exact, ro_exact),
                "strict_f1": _delta(rl_strict, ro_strict),
                "lenient_f1": _delta(rl_lenient, ro_lenient),
            },
            "claim_boundary": DESCRIPTIVE_DELTA_ONLY,
        }
        rows.append(row)

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="R14.5 — Descriptive Rule-only vs Rule+LLM comparison"
    )
    parser.add_argument(
        "--rule-only-summary",
        type=Path,
        required=True,
        help="R14.2 rule-only evaluation summary JSON",
    )
    parser.add_argument(
        "--rule-llm-summary",
        type=Path,
        required=True,
        help="R14.4 Rule+LLM evaluation summary JSON",
    )
    parser.add_argument(
        "--rule-only-details",
        type=Path,
        required=True,
        help="R14.2 rule-only evaluation details JSONL",
    )
    parser.add_argument(
        "--rule-llm-details",
        type=Path,
        required=True,
        help="R14.4 Rule+LLM evaluation details JSONL",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        required=True,
        help="Output comparison summary JSON",
    )
    parser.add_argument(
        "--field-out",
        type=Path,
        required=True,
        help="Output field comparison JSONL",
    )
    args = parser.parse_args()

    # Read inputs (read-only)
    rule_only_summary = _read_json(args.rule_only_summary)
    rule_llm_summary = _read_json(args.rule_llm_summary)

    # Validate sample counts
    ro_count = rule_only_summary.get("sample_count", 0)
    rl_count = rule_llm_summary.get("sample_count", 0)
    if ro_count != 24 or rl_count != 24:
        print(
            f"WARNING: sample counts differ — rule_only={ro_count}, rule_llm={rl_count}",
            file=sys.stderr,
        )

    # Build comparison outputs
    summary = build_comparison_summary(rule_only_summary, rule_llm_summary)
    field_rows = build_field_comparison(rule_only_summary, rule_llm_summary)

    # Write outputs
    _write_json(args.summary_out, summary)
    _write_jsonl(args.field_out, field_rows)

    # Print summary
    print("--- R14.5 Descriptive Comparison ---")
    deltas = summary.get("overall_deltas", {})
    for key, val in deltas.items():
        if val is not None:
            print(f"  {key}: {val:+.4f}")
        else:
            print(f"  {key}: N/A (unavailable)")
    print(f"  Summary written: {args.summary_out}")
    print(f"  Field comparison written: {args.field_out}")
    print("  Done.")


if __name__ == "__main__":
    main()

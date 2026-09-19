# -*- coding: utf-8 -*-
"""Fixed paired-sample bootstrap for the SEP-C3 condition-preservation round.

Zero API.  The script expects the three future canonical prediction JSONL files
and the frozen Gold.  It uses only already-produced local predictions; it never
imports an LLM transport or reads ``.env``.

The bootstrap is intentionally count-based: for each sample the script
precomputes the frozen evaluator's per-field counts, then each resample sums
those counts and recomputes aggregate F1 from the sums.  It does not average
single-sample F1 values.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    SPAN_FIELDS,
    attempt_rows,
    evaluate_coarse,
)
from bpc_hybrid import stage2_sun_literal_overlap as sun  # noqa: E402


ARMS = ("BASE", "RC1", "RC_KEEP")
COMPARISONS = {
    "RC_KEEP-RC1_condition_f1": ("RC_KEEP", "RC1", "condition_f1"),
    "RC_KEEP-BASE_five_field_mean_f1": (
        "RC_KEEP",
        "BASE",
        "coarse_five_field_mean_f1",
    ),
}
BOOTSTRAP_SEED = 20260919
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_INTERVAL = "95% percentile"
DEFAULT_GOLD = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
DEFAULT_INPUT = (
    ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "outputs"
    / "reports"
    / "sep_c3_condition_preservation_v1_bootstrap.json"
)


class BootstrapError(RuntimeError):
    """A bootstrap precondition failed."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BootstrapError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise BootstrapError(f"empty JSONL: {path}")
    return rows


def _zero_counts() -> dict[str, dict[str, int]]:
    return {
        field: {
            "ground_truth": 0,
            "extracted": 0,
            "matched_predictions": 0,
            "matched_ground_truth": 0,
        }
        for field in SPAN_FIELDS
    }


def _prf(
    *,
    extracted: int,
    ground_truth: int,
    matched_predictions: int,
    matched_ground_truth: int,
) -> dict[str, float | int]:
    precision = matched_predictions / extracted if extracted else 0.0
    recall = matched_ground_truth / ground_truth if ground_truth else 0.0
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        "ground_truth": ground_truth,
        "extracted": extracted,
        "matched_predictions": matched_predictions,
        "matched_ground_truth": matched_ground_truth,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fp": extracted - matched_predictions,
        "missed": ground_truth - matched_ground_truth,
    }


def _metrics_from_field_counts(
    counts: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    field_metrics: dict[str, dict[str, float | int]] = {}
    for field in SPAN_FIELDS:
        values = counts.get(field) or _zero_counts()[field]
        field_metrics[field] = _prf(
            extracted=int(values.get("extracted") or 0),
            ground_truth=int(values.get("ground_truth") or 0),
            matched_predictions=int(values.get("matched_predictions") or 0),
            matched_ground_truth=int(
                values.get("matched_ground_truth") or 0
            ),
        )
    micro = _prf(
        extracted=sum(v["extracted"] for v in field_metrics.values()),
        ground_truth=sum(v["ground_truth"] for v in field_metrics.values()),
        matched_predictions=sum(
            v["matched_predictions"] for v in field_metrics.values()
        ),
        matched_ground_truth=sum(
            v["matched_ground_truth"] for v in field_metrics.values()
        ),
    )
    result: dict[str, Any] = {
        field: field_metrics[field] for field in SPAN_FIELDS
    }
    result["condition_f1"] = field_metrics["condition"]["f1"]
    result["condition_fp"] = field_metrics["condition"]["fp"]
    result["condition_missed"] = field_metrics["condition"]["missed"]
    result["actor_f1"] = field_metrics["actor"]["f1"]
    result["actor_fp"] = field_metrics["actor"]["fp"]
    result["constraint_recall"] = field_metrics["constraint"]["recall"]
    result["constraint_fp"] = field_metrics["constraint"]["fp"]
    result["coarse_five_field_mean_f1"] = sum(
        field_metrics[field]["f1"] for field in SPAN_FIELDS
    ) / len(SPAN_FIELDS)
    result["coarse_five_field_micro_f1"] = micro["f1"]
    result["micro_counts"] = micro
    return result


def _add_counts(
    target: dict[str, dict[str, int]],
    source: Mapping[str, Mapping[str, int]],
) -> None:
    for field in SPAN_FIELDS:
        values = source.get(field) or {}
        for key in (
            "ground_truth",
            "extracted",
            "matched_predictions",
            "matched_ground_truth",
        ):
            target[field][key] += int(values.get(key) or 0)


def _per_sample_counts(
    gold_record: Mapping[str, Any],
    prediction_row: Mapping[str, Any],
) -> dict[str, dict[str, int]]:
    predicted = prediction_row.get("record")
    if (
        prediction_row.get("request_status") != "ok"
        or not isinstance(predicted, Mapping)
    ):
        predicted = {"clauses": []}
    counts = _zero_counts()
    for field in SPAN_FIELDS:
        gold_spans = sun._field_spans(gold_record, field)
        predicted_spans = sun._field_spans(predicted, field)
        counts[field]["ground_truth"] += len(gold_spans)
        counts[field]["extracted"] += len(predicted_spans)
        counts[field]["matched_predictions"] += sum(
            any(
                sun._intersects(predicted_span, gold_span)
                for gold_span in gold_spans
            )
            for predicted_span in predicted_spans
        )
        counts[field]["matched_ground_truth"] += sum(
            any(
                sun._intersects(gold_span, predicted_span)
                for predicted_span in predicted_spans
            )
            for gold_span in gold_spans
        )
    return counts


def _percentile(values: Sequence[float], q: float) -> float:
    if not values:
        raise BootstrapError("cannot take percentile of empty values")
    ordered = sorted(float(v) for v in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _interval(values: Sequence[float]) -> list[float]:
    return [
        _percentile(values, 0.025),
        _percentile(values, 0.975),
    ]


def paired_bootstrap(
    sample_order: Sequence[str],
    counts_by_arm: Mapping[str, Mapping[str, Mapping[str, Mapping[str, int]]]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    n = len(sample_order)
    if n == 0:
        raise BootstrapError("sample order is empty")
    rng = random.Random(seed)
    diffs: dict[str, list[float]] = {name: [] for name in COMPARISONS}
    for _ in range(resamples):
        sampled_ids = [sample_order[rng.randrange(n)] for _ in range(n)]
        arm_metrics: dict[str, dict[str, Any]] = {}
        for arm in ARMS:
            total = _zero_counts()
            arm_counts = counts_by_arm[arm]
            for sid in sampled_ids:
                _add_counts(total, arm_counts[sid])
            arm_metrics[arm] = _metrics_from_field_counts(total)
        for name, (left, right, metric) in COMPARISONS.items():
            diffs[name].append(
                float(arm_metrics[left][metric])
                - float(arm_metrics[right][metric])
            )
    point_counts = {arm: _zero_counts() for arm in ARMS}
    for arm in ARMS:
        for sid in sample_order:
            _add_counts(point_counts[arm], counts_by_arm[arm][sid])
    point_metrics = {
        arm: _metrics_from_field_counts(point_counts[arm]) for arm in ARMS
    }
    result: dict[str, Any] = {
        "seed": seed,
        "resamples": resamples,
        "interval": BOOTSTRAP_INTERVAL,
        "pairing": (
            "same resampled sample_id multiset for BASE, RC1, and RC_KEEP"
        ),
        "metric_recompute": (
            "sum per-sample frozen-evaluator counts, then recompute F1; "
            "never average per-sample F1"
        ),
        "point_metrics": point_metrics,
        "point_metric_basis": (
            "sum counts over the complete frozen 150-sample denominator, "
            "then recompute the metric"
        ),
        "comparisons": {},
    }
    for name, values in diffs.items():
        left_arm, right_arm, metric_name = COMPARISONS[name]
        point_difference = float(point_metrics[left_arm][metric_name]) - float(
            point_metrics[right_arm][metric_name]
        )
        bootstrap_mean_difference = sum(values) / len(values)
        lo, hi = _interval(values)
        result["comparisons"][name] = {
            "difference_values": values,
            "point_difference": point_difference,
            "bootstrap_mean_difference": bootstrap_mean_difference,
            "ci95_percentile": [lo, hi],
            "contains_zero": lo <= 0.0 <= hi,
        }
    return result


def _load_arm_predictions(
    paths: Mapping[str, Path],
    expected_sample_ids: Sequence[str],
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    expected_ids = [str(sid) for sid in expected_sample_ids]
    if len(expected_ids) != 150:
        raise BootstrapError(
            f"frozen input must contain exactly 150 sample_ids, got {len(expected_ids)}"
        )
    if len(expected_ids) != len(set(expected_ids)):
        raise BootstrapError("frozen input sample_ids are not unique")
    expected_set = set(expected_ids)
    rows_by_arm: dict[str, list[dict[str, Any]]] = {}
    for arm in ARMS:
        rows = _read_jsonl(paths[arm])
        ids = [str(row.get("sample_id") or "") for row in rows]
        if any(not sid for sid in ids):
            raise BootstrapError(f"{arm}: missing sample_id")
        if len(ids) != len(set(ids)):
            raise BootstrapError(f"{arm}: duplicate sample_id")
        observed_set = set(ids)
        if observed_set != expected_set or len(ids) != len(expected_ids):
            missing = sorted(expected_set - observed_set)
            extra = sorted(observed_set - expected_set)
            raise BootstrapError(
                f"{arm}: sample membership does not match the frozen 150."
                f" denominator={len(ids)}, missing={missing[:10]}"
                f"{'...' if len(missing) > 10 else ''},"
                f" extra={extra[:10]}{'...' if len(extra) > 10 else ''}"
            )
        rows_by_arm[arm] = rows
    return rows_by_arm, list(expected_ids)
def _point_metrics(
    gold_doc: Mapping[str, Any],
    rows_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        evaluation = evaluate_coarse(
            gold_doc,
            attempt_rows(rows_by_arm[arm]),
            method_id=f"direct_llm_condition_preservation_{arm}",
        )
        per_field = evaluation["five_fields"]
        output[arm] = {
            "five_fields": per_field,
            "condition_f1": per_field["condition"]["f1"],
            "condition_fp": (
                per_field["condition"]["extracted"]
                - per_field["condition"]["matched_predictions"]
            ),
            "condition_missed": (
                per_field["condition"]["ground_truth"]
                - per_field["condition"]["matched_ground_truth"]
            ),
            "actor_f1": per_field["actor"]["f1"],
            "actor_fp": (
                per_field["actor"]["extracted"]
                - per_field["actor"]["matched_predictions"]
            ),
            "constraint_recall": per_field["constraint"]["recall"],
            "constraint_fp": (
                per_field["constraint"]["extracted"]
                - per_field["constraint"]["matched_predictions"]
            ),
            "coarse_five_field_mean_f1": evaluation[
                "coarse_five_field_mean_f1"
            ],
            "coarse_five_field_micro_f1": evaluation[
                "coarse_five_field_micro"
            ]["f1"],
            "denominator": evaluation["denominator"],
            "failed_count": evaluation["failed_count"],
        }
    return output


def _processing_failure_counts(
    rows_by_arm: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for arm in ARMS:
        rows = rows_by_arm[arm]
        status_counts: dict[str, dict[str, int]] = {
            "api_call_status": dict(Counter(
                str(row.get("api_call_status") or "missing") for row in rows
            )),
            "output_parse_status": dict(Counter(
                str(row.get("output_parse_status") or "missing")
                for row in rows
            )),
            "input_binding_status": dict(Counter(
                str(row.get("input_binding_status") or "missing")
                for row in rows
            )),
            "canonical_validation_status": dict(Counter(
                str(row.get("canonical_validation_status") or "missing")
                for row in rows
            )),
        }
        output_processing_failures = sum(
            1
            for row in rows
            if row.get("output_parse_status") == "failed"
            or row.get("input_binding_status") == "failed"
            or row.get("canonical_validation_status") == "failed"
        )
        transport_failures = sum(
            1
            for row in rows
            if str(row.get("api_call_status") or "").lower() != "ok"
        )
        output[arm] = {
            "transport_failures": transport_failures,
            "output_processing_failures": output_processing_failures,
            "status_counts": status_counts,
        }
    return output


def _criterion(
    criterion_id: str,
    difference: float,
    operator: str,
    *,
    left: float,
    right: float,
    metric: str,
) -> dict[str, Any]:
    passed = False
    if operator == "> 0":
        passed = difference > 0.0
    elif operator == ">= 0":
        passed = difference >= 0.0
    elif operator == "< 0":
        passed = difference < 0.0
    elif operator == "<= 0":
        passed = difference <= 0.0
    else:
        raise BootstrapError(f"unknown operator: {operator}")
    return {
        "id": criterion_id,
        "metric": metric,
        "operator": operator,
        "left_value": left,
        "right_value": right,
        "difference": difference,
        "pass": passed,
    }


def evaluate_retention(
    points: Mapping[str, Mapping[str, Any]],
    bootstrap: Mapping[str, Any],
    failures: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    base = points["BASE"]
    rc1 = points["RC1"]
    keep = points["RC_KEEP"]
    failures_base = failures["BASE"]["output_processing_failures"]
    failures_rc1 = failures["RC1"]["output_processing_failures"]
    failures_keep = failures["RC_KEEP"]["output_processing_failures"]
    criteria = [
        _criterion(
            "condition_f1_improves_vs_RC1",
            keep["condition_f1"] - rc1["condition_f1"],
            "> 0",
            left=keep["condition_f1"],
            right=rc1["condition_f1"],
            metric="condition_f1",
        ),
        _criterion(
            "condition_missed_decreases_vs_RC1",
            keep["condition_missed"] - rc1["condition_missed"],
            "< 0",
            left=keep["condition_missed"],
            right=rc1["condition_missed"],
            metric="condition_missed",
        ),
        _criterion(
            "five_field_mean_f1_improves_vs_BASE",
            keep["coarse_five_field_mean_f1"]
            - base["coarse_five_field_mean_f1"],
            "> 0",
            left=keep["coarse_five_field_mean_f1"],
            right=base["coarse_five_field_mean_f1"],
            metric="coarse_five_field_mean_f1",
        ),
        _criterion(
            "micro_f1_improves_vs_BASE",
            keep["coarse_five_field_micro_f1"]
            - base["coarse_five_field_micro_f1"],
            "> 0",
            left=keep["coarse_five_field_micro_f1"],
            right=base["coarse_five_field_micro_f1"],
            metric="coarse_five_field_micro_f1",
        ),
        _criterion(
            "actor_f1_not_below_BASE",
            keep["actor_f1"] - base["actor_f1"],
            ">= 0",
            left=keep["actor_f1"],
            right=base["actor_f1"],
            metric="actor_f1",
        ),
        _criterion(
            "actor_fp_not_above_BASE",
            keep["actor_fp"] - base["actor_fp"],
            "<= 0",
            left=keep["actor_fp"],
            right=base["actor_fp"],
            metric="actor_fp",
        ),
        _criterion(
            "condition_fp_not_above_BASE",
            keep["condition_fp"] - base["condition_fp"],
            "<= 0",
            left=keep["condition_fp"],
            right=base["condition_fp"],
            metric="condition_fp",
        ),
        _criterion(
            "constraint_recall_not_below_RC1",
            keep["constraint_recall"] - rc1["constraint_recall"],
            ">= 0",
            left=keep["constraint_recall"],
            right=rc1["constraint_recall"],
            metric="constraint_recall",
        ),
        _criterion(
            "constraint_fp_not_above_RC1",
            keep["constraint_fp"] - rc1["constraint_fp"],
            "<= 0",
            left=keep["constraint_fp"],
            right=rc1["constraint_fp"],
            metric="constraint_fp",
        ),
        {
            "id": "output_processing_failures_not_above_each_control",
            "metric": "output_processing_failures",
            "operator": "<= min(BASE, RC1)",
            "left_value": failures_keep,
            "right_value": min(failures_base, failures_rc1),
            "difference": failures_keep - min(failures_base, failures_rc1),
            "pass": failures_keep <= min(failures_base, failures_rc1),
        },
    ]
    interval_checks = {
        name: {
            "contains_zero": bool(payload["contains_zero"]),
            "pass": not bool(payload["contains_zero"]),
        }
        for name, payload in bootstrap["comparisons"].items()
    }
    all_criteria_pass = all(item["pass"] for item in criteria)
    all_intervals_exclude_zero = all(
        item["pass"] for item in interval_checks.values()
    )
    return {
        "criteria": criteria,
        "all_criteria_pass": all_criteria_pass,
        "required_interval_checks": interval_checks,
        "all_required_intervals_exclude_zero": all_intervals_exclude_zero,
        "worth_retaining": (
            all_criteria_pass and all_intervals_exclude_zero
        ),
        "decision": (
            "candidate_worth_keeping"
            if all_criteria_pass and all_intervals_exclude_zero
            else "keep_BASE_or_evidence_uncertain"
        ),
    }


def analyze(
    *,
    base_path: Path,
    rc1_path: Path,
    rc_keep_path: Path,
    input_path: Path = DEFAULT_INPUT,
    gold_path: Path = DEFAULT_GOLD,
    output_path: Path = DEFAULT_OUTPUT,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    if resamples != BOOTSTRAP_RESAMPLES or seed != BOOTSTRAP_SEED:
        raise BootstrapError(
            "this round fixes resamples=10000 and seed=20260919"
        )
    input_doc = _read_json(input_path)
    input_records = input_doc.get("records")
    if not isinstance(input_records, list):
        raise BootstrapError("frozen input records must be a list")
    expected_ids = [str(record.get("sample_id") or "") for record in input_records]
    if any(not sid for sid in expected_ids):
        raise BootstrapError("frozen input contains a missing sample_id")
    rows_by_arm, sample_order = _load_arm_predictions(
        {
            "BASE": base_path,
            "RC1": rc1_path,
            "RC_KEEP": rc_keep_path,
        },
        expected_ids,
    )
    gold_doc = _read_json(gold_path)
    coarse_gold = {str(rec["sample_id"]): rec for rec in build_coarse_view(gold_doc)}
    counts_by_arm: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
    for arm in ARMS:
        counts_by_arm[arm] = {}
        for row in rows_by_arm[arm]:
            sid = str(row["sample_id"])
            if sid not in coarse_gold:
                raise BootstrapError(f"{arm}: unknown sample_id {sid}")
            counts_by_arm[arm][sid] = _per_sample_counts(
                coarse_gold[sid], row
            )
    points = _point_metrics(gold_doc, rows_by_arm)
    # Freeze point estimates and the count-based recomputation together.
    for arm in ARMS:
        total = _zero_counts()
        for sid in sample_order:
            _add_counts(total, counts_by_arm[arm][sid])
        recomputed = _metrics_from_field_counts(total)
        for field in SPAN_FIELDS:
            frozen_f1 = float(points[arm]["five_fields"][field]["f1"])
            recomputed_f1 = float(recomputed[field]["f1"])
            if abs(frozen_f1 - recomputed_f1) > 1e-12:
                raise BootstrapError(
                    f"{arm}.{field}: count-recomputed F1 differs from "
                    "frozen evaluator"
                )
        if abs(
            float(points[arm]["coarse_five_field_mean_f1"])
            - float(recomputed["coarse_five_field_mean_f1"])
        ) > 1e-12:
            raise BootstrapError(
                f"{arm}: count-recomputed mean F1 differs from frozen evaluator"
            )
        if abs(
            float(points[arm]["coarse_five_field_micro_f1"])
            - float(recomputed["coarse_five_field_micro_f1"])
        ) > 1e-12:
            raise BootstrapError(
                f"{arm}: count-recomputed micro F1 differs from frozen evaluator"
            )
    bootstrap = paired_bootstrap(
        sample_order,
        counts_by_arm,
        resamples=resamples,
        seed=seed,
    )
    failures = _processing_failure_counts(rows_by_arm)
    retention = evaluate_retention(points, bootstrap, failures)
    result = {
        "schema_version": "sep_c3_condition_preservation_bootstrap@1.0.0",
        "suite_id": "SEP-C3-CONDITION-PRESERVATION-001",
        "real_api_calls": 0,
        "input_paths": {
            "BASE": str(base_path),
            "RC1": str(rc1_path),
            "RC_KEEP": str(rc_keep_path),
            "frozen_input": str(input_path),
            "gold": str(gold_path),
        },
        "expected_sample_count": len(expected_ids),
        "sample_order": sample_order,
        "denominator_per_arm": {
            arm: len(rows_by_arm[arm]) for arm in ARMS
        },
        "point_metrics": points,
        "processing_failures": failures,
        "bootstrap": bootstrap,
        "retention": retention,
        "limitations": (
            "The percentile interval reflects sample-composition sensitivity "
            "only. It does not estimate server, channel, or repeat-run variance."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed paired-sample bootstrap for the SEP-C3 "
            "condition-preservation arms. This command uses local files only."
        )
    )
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--rc1", type=Path, required=True)
    parser.add_argument("--rc-keep", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    result = analyze(
        base_path=args.base,
        rc1_path=args.rc1,
        rc_keep_path=args.rc_keep,
        input_path=args.input,
        gold_path=args.gold,
        output_path=args.output,
    )
    summary = {
        "output": str(args.output),
        "worth_retaining": result["retention"]["worth_retaining"],
        "decision": result["retention"]["decision"],
        "real_api_calls": 0,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
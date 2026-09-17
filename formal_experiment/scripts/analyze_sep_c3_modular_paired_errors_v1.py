# -*- coding: utf-8 -*-
"""Zero-API paired error attribution for the SEP-C3 modular E/S/J ablation.

This script reads only the frozen Gold, persisted canonical predictions,
persisted evaluation JSON, raw responses, and manifests. It does not call an
LLM, does not modify predictions/Gold/prompts, and derives all sample-level
comparisons from the same coarse five-field evaluator contract used by
``bpc_hybrid.sep_c3_modular_evaluation``.

The derived paired labels are diagnostic overlays on the existing evaluator:
a sample-field is called "evaluator-correct" when every predicted span in that
sample-field intersects at least one coarse Gold span in the same field and
every coarse Gold span is intersected by at least one prediction. Boundary
classes are reported only as diagnostics and are not used to recompute F1.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.stage2_sun_literal_overlap import (  # noqa: E402
    _field_spans,
    _intersects,
)

SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
PLURAL_KEYS = {
    "actor": "actors",
    "action": "actions",
    "condition": "conditions",
    "constraint": "constraints",
    "exception": "exceptions",
}
ALL_FIELDS = SPAN_FIELDS + ("modality_label",)
GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
OUT_JSON = ROOT / "outputs" / "reports" / "sep_c3_modular_paired_error_attribution_v1.json"

ARM_PATHS = {
    "111": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "arms" / "111",
    "011": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "arms" / "011",
    "101": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "arms" / "101",
    "110": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v1" / "arms" / "110",
    "000": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "arms" / "000" / "repeat-01",
    "001": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "arms" / "001" / "repeat-01",
    "010": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "arms" / "010" / "repeat-01",
    "100": ROOT / "outputs" / "evidence" / "sep_c3_modular_ablation_v2" / "arms" / "100" / "repeat-01",
}

PAIR_DEFS = [
    ("100_vs_000", "000", "100", "same_new_batch", "E contribution against the common skeleton"),
    ("010_vs_000", "000", "010", "same_new_batch", "S contribution against the common skeleton"),
    ("001_vs_000", "000", "001", "same_new_batch", "J contribution against the common skeleton"),
    ("111_vs_011", "011", "111", "same_old_batch", "adding E when S+J are present"),
    ("111_vs_101", "101", "111", "same_old_batch", "adding S when E+J are present"),
    ("111_vs_110", "110", "111", "same_old_batch", "adding J when E+S are present"),
    ("100_vs_110", "100", "110", "cross_batch_confounded", "adding S when E is present (new-batch baseline vs old-batch variant)"),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_arm(arm: str) -> dict[str, Any]:
    base = ARM_PATHS[arm]
    rows = read_jsonl(base / "canonical_predictions.jsonl")
    raw = read_jsonl(base / "raw_responses.jsonl")
    evaluation = read_json(base / "evaluation.json")
    manifest = read_json(base / "manifest.json")
    by_id = {row["sample_id"]: row for row in rows}
    raw_by_id = {row["sample_id"]: row for row in raw}
    if set(by_id) != set(raw_by_id):
        raise RuntimeError(f"canonical/raw membership mismatch for arm {arm}")
    return {
        "path": str(base.relative_to(ROOT)).replace("\\", "/"),
        "rows": rows,
        "raw": raw,
        "by_id": by_id,
        "raw_by_id": raw_by_id,
        "evaluation": evaluation,
        "manifest": manifest,
    }


def span_summary(span: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "text": span.get("text"),
        "start": span.get("start"),
        "end": span.get("end"),
        "normalized": span.get("normalized"),
    }


def sample_field_score(gold_record: Mapping[str, Any],
                       prediction_row: Mapping[str, Any],
                       field: str) -> dict[str, Any]:
    gold_spans = _field_spans(gold_record, field)
    predicted_spans = _field_spans(
        prediction_row.get("record") or {}, field)
    predicted_matched = [
        any(_intersects(predicted, gold) for gold in gold_spans)
        for predicted in predicted_spans
    ]
    gold_matched = [
        any(_intersects(gold, predicted) for predicted in predicted_spans)
        for gold in gold_spans
    ]
    matched_pred_count = sum(predicted_matched)
    matched_gold_count = sum(gold_matched)
    evaluator_correct = (
        matched_pred_count == len(predicted_spans)
        and matched_gold_count == len(gold_spans)
    )
    boundary = Counter()
    matched_boundary_ratios: list[float] = []
    for predicted, is_matched in zip(predicted_spans, predicted_matched):
        if not is_matched:
            boundary["unmatched"] += 1
            continue
        hits = [
            gold for gold in gold_spans
            if _intersects(predicted, gold)
        ]
        gold = max(
            hits,
            key=lambda item: (
                min(int(predicted["end"]), int(item["end"]))
                - max(int(predicted["start"]), int(item["start"]))
            ),
        )
        p_start, p_end = int(predicted["start"]), int(predicted["end"])
        g_start, g_end = int(gold["start"]), int(gold["end"])
        gold_len = g_end - g_start
        predicted_len = p_end - p_start
        if gold_len:
            matched_boundary_ratios.append(predicted_len / gold_len)
        if p_start == g_start and p_end == g_end:
            boundary["exact"] += 1
        elif p_start <= g_start and p_end >= g_end:
            boundary["expansion"] += 1
        elif p_start >= g_start and p_end <= g_end:
            boundary["contraction"] += 1
        else:
            boundary["shifted_partial"] += 1
    duplicate_overlap_pairs = 0
    for i, left in enumerate(predicted_spans):
        for right in predicted_spans[i + 1:]:
            if _intersects(left, right):
                duplicate_overlap_pairs += 1
    return {
        "gold_count": len(gold_spans),
        "pred_count": len(predicted_spans),
        "matched_pred": matched_pred_count,
        "matched_gold": matched_gold_count,
        "unmatched_pred": len(predicted_spans) - matched_pred_count,
        "missed_gold": len(gold_spans) - matched_gold_count,
        "evaluator_correct": evaluator_correct,
        "hallucinated_field": len(gold_spans) == 0 and len(predicted_spans) > 0,
        "missed_field": len(gold_spans) > 0 and len(predicted_spans) == 0,
        "boundary": dict(boundary),
        "matched_boundary_length_ratio_mean": (
            sum(matched_boundary_ratios) / len(matched_boundary_ratios)
            if matched_boundary_ratios else None
        ),
        "duplicate_overlap_pairs": duplicate_overlap_pairs,
    }


def modality_label(prediction_row: Mapping[str, Any]) -> str | None:
    for clause in (prediction_row.get("record") or {}).get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label:
            return label
    return None


def gold_modality_label(gold_record: Mapping[str, Any]) -> str | None:
    for clause in gold_record.get("clauses") or []:
        label = clause.get("modality")
        if isinstance(label, str) and label:
            return label
    return None


def field_semantic_signature(record: Mapping[str, Any], field: str) -> tuple:
    out = []
    for clause in record.get("clauses") or []:
        for span in clause.get(PLURAL_KEYS[field]) or []:
            out.append((
                span.get("start"),
                span.get("end"),
                span.get("normalized") or span.get("text"),
            ))
    return tuple(out)


def semantic_signature(record: Mapping[str, Any]) -> tuple:
    out = []
    for clause in record.get("clauses") or []:
        label = (clause.get("modality") or {}).get("label")
        out.append(("modality_label", label))
        for field in SPAN_FIELDS:
            for span in clause.get(PLURAL_KEYS[field]) or []:
                out.append((
                    field,
                    span.get("start"),
                    span.get("end"),
                    span.get("normalized") or span.get("text"),
                ))
    return tuple(out)


def cross_field_candidate_counts(
    gold_record: Mapping[str, Any],
    prediction_row: Mapping[str, Any],
) -> Counter:
    gold_by_field = {
        field: _field_spans(gold_record, field)
        for field in SPAN_FIELDS
    }
    counts: Counter = Counter()
    for target_field in SPAN_FIELDS:
        target_gold = gold_by_field[target_field]
        for predicted in _field_spans(
                prediction_row.get("record") or {}, target_field):
            if any(_intersects(predicted, gold) for gold in target_gold):
                continue
            for other_field, other_gold in gold_by_field.items():
                if other_field == target_field:
                    continue
                if any(_intersects(predicted, gold) for gold in other_gold):
                    counts[f"{target_field}->{other_field}"] += 1
    return counts


def evaluate_pair(coarse_gold: Mapping[str, Mapping[str, Any]],
                  arms: Mapping[str, Mapping[str, Any]],
                  baseline_arm: str,
                  variant_arm: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in ALL_FIELDS:
        field_counts: Counter = Counter()
        for sample_id, gold_record in coarse_gold.items():
            base_row = arms[baseline_arm]["by_id"][sample_id]
            var_row = arms[variant_arm]["by_id"][sample_id]
            if field == "modality_label":
                gold_value = gold_modality_label(gold_record)
                base_score = {"evaluator_correct": modality_label(base_row) == gold_value}
                var_score = {"evaluator_correct": modality_label(var_row) == gold_value}
                # Keep the same output schema for modality while making it
                # explicit that span counts are not applicable.
                for key in (
                    "gold_count", "pred_count", "matched_pred", "matched_gold",
                    "unmatched_pred", "missed_gold", "hallucinated_field",
                    "missed_field", "duplicate_overlap_pairs",
                    "matched_boundary_length_ratio_mean",
                ):
                    base_score[key] = None
                    var_score[key] = None
                base_score["boundary"] = {}
                var_score["boundary"] = {}
            else:
                base_score = sample_field_score(gold_record, base_row, field)
                var_score = sample_field_score(gold_record, var_row, field)
            base_correct = bool(base_score["evaluator_correct"])
            var_correct = bool(var_score["evaluator_correct"])
            if base_correct and var_correct:
                field_counts["both_correct"] += 1
            elif base_correct and not var_correct:
                field_counts["regressed"] += 1
            elif not base_correct and var_correct:
                field_counts["fixed"] += 1
            else:
                field_counts["both_wrong"] += 1
            for prefix, score in (("base", base_score), ("var", var_score)):
                for key in (
                    "gold_count", "pred_count", "matched_pred", "matched_gold",
                    "unmatched_pred", "missed_gold", "duplicate_overlap_pairs",
                ):
                    field_counts[f"{prefix}_{key}"] += int(score[key] or 0)
                field_counts[f"{prefix}_hallucinated_fields"] += int(
                    bool(score.get("hallucinated_field")))
                field_counts[f"{prefix}_missed_fields"] += int(
                    bool(score.get("missed_field")))
                boundary = score.get("boundary") or {}
                for boundary_key, boundary_value in boundary.items():
                    field_counts[f"{prefix}_boundary_{boundary_key}"] += int(boundary_value)
                if score.get("matched_boundary_length_ratio_mean") is not None:
                    field_counts[f"{prefix}_boundary_ratio_sum"] += float(
                        score["matched_boundary_length_ratio_mean"])
                    field_counts[f"{prefix}_boundary_ratio_n"] += 1
                if field != "modality_label":
                    for candidate_key, candidate_value in cross_field_candidate_counts(
                            gold_record, base_row if prefix == "base" else var_row).items():
                        field_counts[f"{prefix}_cross_field_{candidate_key}"] += candidate_value
        fields[field] = {
            "unit": "sample_field_record_label",
            "units": len(coarse_gold),
            "both_correct": field_counts["both_correct"],
            "fixed": field_counts["fixed"],
            "regressed": field_counts["regressed"],
            "both_wrong": field_counts["both_wrong"],
            "base_correct": (
                field_counts["both_correct"] + field_counts["regressed"]),
            "var_correct": (
                field_counts["both_correct"] + field_counts["fixed"]),
            "base_pred_count": field_counts["base_pred_count"],
            "var_pred_count": field_counts["var_pred_count"],
            "pred_count_delta": (
                field_counts["var_pred_count"] - field_counts["base_pred_count"]),
            "base_matched_pred": field_counts["base_matched_pred"],
            "var_matched_pred": field_counts["var_matched_pred"],
            "matched_pred_delta": (
                field_counts["var_matched_pred"] - field_counts["base_matched_pred"]),
            "base_unmatched_pred": field_counts["base_unmatched_pred"],
            "var_unmatched_pred": field_counts["var_unmatched_pred"],
            "unmatched_pred_delta": (
                field_counts["var_unmatched_pred"] - field_counts["base_unmatched_pred"]),
            "base_matched_gold": field_counts["base_matched_gold"],
            "var_matched_gold": field_counts["var_matched_gold"],
            "matched_gold_delta": (
                field_counts["var_matched_gold"] - field_counts["base_matched_gold"]),
            "base_missed_gold": field_counts["base_missed_gold"],
            "var_missed_gold": field_counts["var_missed_gold"],
            "missed_gold_delta": (
                field_counts["var_missed_gold"] - field_counts["base_missed_gold"]),
            "base_hallucinated_fields": field_counts["base_hallucinated_fields"],
            "var_hallucinated_fields": field_counts["var_hallucinated_fields"],
            "base_missed_fields": field_counts["base_missed_fields"],
            "var_missed_fields": field_counts["var_missed_fields"],
            "base_duplicate_overlap_pairs": field_counts["base_duplicate_overlap_pairs"],
            "var_duplicate_overlap_pairs": field_counts["var_duplicate_overlap_pairs"],
            "boundary_counts": {
                key: {
                    "base": field_counts.get(f"base_boundary_{key}", 0),
                    "var": field_counts.get(f"var_boundary_{key}", 0),
                }
                for key in ("exact", "expansion", "contraction", "shifted_partial", "unmatched")
            },
            "matched_boundary_length_ratio_mean": {
                "base": (
                    field_counts["base_boundary_ratio_sum"] / field_counts["base_boundary_ratio_n"]
                    if field_counts["base_boundary_ratio_n"] else None),
                "var": (
                    field_counts["var_boundary_ratio_sum"] / field_counts["var_boundary_ratio_n"]
                    if field_counts["var_boundary_ratio_n"] else None),
            },
            "cross_field_candidate_counts": {
                key.replace("base_cross_field_", "").replace("var_cross_field_", ""): {
                    "base": field_counts.get(f"base_cross_field_{key}", 0),
                    "var": field_counts.get(f"var_cross_field_{key}", 0),
                }
                for key in sorted({
                    key[len("base_cross_field_"):]
                    for key in field_counts
                    if key.startswith("base_cross_field_")
                } | {
                    key[len("var_cross_field_"):]
                    for key in field_counts
                    if key.startswith("var_cross_field_")
                })
            },
        }
    return {
        "pair_id": f"{baseline_arm}_to_{variant_arm}",
        "baseline_arm": baseline_arm,
        "variant_arm": variant_arm,
        "fields": fields,
    }


def primary_metric(evaluation: Mapping[str, Any]) -> float:
    return float(evaluation["evaluation"]["coarse_five_field_mean_f1"])


def boundary_diagnostics_for_arm(
    coarse_gold: Mapping[str, Mapping[str, Any]],
    arm: Mapping[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field in SPAN_FIELDS:
        counter: Counter = Counter()
        ratio_values: list[float] = []
        for sample_id, gold_record in coarse_gold.items():
            score = sample_field_score(gold_record, arm["by_id"][sample_id], field)
            for key, value in score["boundary"].items():
                counter[key] += value
            if score["matched_boundary_length_ratio_mean"] is not None:
                ratio_values.append(score["matched_boundary_length_ratio_mean"])
        out[field] = {
            "boundary_counts": dict(counter),
            "matched_boundary_length_ratio_mean": (
                sum(ratio_values) / len(ratio_values) if ratio_values else None),
        }
    return out


def select_cases(coarse_gold: Mapping[str, Mapping[str, Any]],
                 arms: Mapping[str, Mapping[str, Any]],
                 baseline_arm: str,
                 variant_arm: str,
                 field: str,
                 outcome: str,
                 limit: int = 3) -> list[dict[str, Any]]:
    cases = []
    for sample_id, gold_record in coarse_gold.items():
        base_row = arms[baseline_arm]["by_id"][sample_id]
        var_row = arms[variant_arm]["by_id"][sample_id]
        base_score = sample_field_score(gold_record, base_row, field)
        var_score = sample_field_score(gold_record, var_row, field)
        if outcome == "fixed":
            is_requested = (
                not base_score["evaluator_correct"]
                and var_score["evaluator_correct"]
            )
        elif outcome == "regressed":
            is_requested = (
                base_score["evaluator_correct"]
                and not var_score["evaluator_correct"]
            )
        else:
            raise ValueError(f"unknown outcome: {outcome}")
        if not is_requested:
            continue
        if outcome == "fixed":
            rank = (
                base_score["unmatched_pred"] - var_score["unmatched_pred"]
                + base_score["missed_gold"] - var_score["missed_gold"]
            )
        else:
            rank = (
                var_score["unmatched_pred"] - base_score["unmatched_pred"]
                + var_score["missed_gold"] - base_score["missed_gold"]
            )
        cases.append((rank, sample_id, gold_record, base_score, var_score,
                      base_row, var_row))
    cases.sort(key=lambda item: item[0], reverse=True)
    selected = []
    for rank, sample_id, gold_record, base_score, var_score, base_row, var_row in cases[:limit]:
        gold_fine_spans = []
        for clause in gold_record.get("clauses") or []:
            for span in clause.get(PLURAL_KEYS[field]) or []:
                gold_fine_spans.append(span_summary(span))
        selected.append({
            "sample_id": sample_id,
            "field": field,
            "outcome": outcome,
            "pair_id": f"{baseline_arm}_to_{variant_arm}",
            "baseline_arm": baseline_arm,
            "variant_arm": variant_arm,
            "source_text": gold_record.get("source_text"),
            "gold_coarse_spans": [span_summary(s) for s in _field_spans(gold_record, field)],
            "gold_fine_spans": gold_fine_spans,
            "baseline_spans": [span_summary(s) for s in _field_spans(base_row["record"], field)],
            "variant_spans": [span_summary(s) for s in _field_spans(var_row["record"], field)],
            "baseline_score": base_score,
            "variant_score": var_score,
            "mechanical_observation": (
                f"{baseline_arm}: {base_score['pred_count']} predicted span(s), "
                f"{base_score['unmatched_pred']} unmatched, "
                f"{base_score['missed_gold']} missed Gold span(s); "
                f"{variant_arm}: {var_score['pred_count']} predicted span(s), "
                f"{var_score['unmatched_pred']} unmatched, "
                f"{var_score['missed_gold']} missed Gold span(s)."
            ),
        })
    return selected


def raw_format_stats(arm: Mapping[str, Any]) -> dict[str, Any]:
    parsed = 0
    bare_object = 0
    fenced = 0
    non_object_prefix = 0
    empty = 0
    for row in arm["raw"]:
        content = (row.get("raw_response_content") or "").strip()
        if not content:
            empty += 1
            continue
        try:
            json.loads(content)
            parsed += 1
        except Exception:
            pass
        if content.startswith("```"):
            fenced += 1
        if content.startswith("{") and content.endswith("}"):
            try:
                json.loads(content)
                bare_object += 1
            except Exception:
                pass
        elif not content.startswith("{"):
            non_object_prefix += 1
    return {
        "rows": len(arm["raw"]),
        "json_parsable_raw_content": parsed,
        "bare_json_object_raw_content": bare_object,
        "markdown_fenced_raw_content": fenced,
        "non_object_prefix_raw_content": non_object_prefix,
        "empty_raw_content": empty,
        "canonical_predictions": len(arm["rows"]),
        "canonical_request_status_ok": sum(
            1 for row in arm["rows"] if row.get("request_status") == "ok"),
        "canonical_schema_valid_true": sum(
            1 for row in arm["rows"]
            if ((row.get("record") or {}).get("validation") or {}).get("schema_valid") is True),
        "canonical_cross_field_valid_true": sum(
            1 for row in arm["rows"]
            if ((row.get("record") or {}).get("validation") or {}).get("cross_field_valid") is True),
        "canonical_validation_errors_nonempty": sum(
            1 for row in arm["rows"]
            if (((row.get("record") or {}).get("validation") or {}).get("errors") or [])),
    }


def main() -> None:
    gold_doc = read_json(GOLD_PATH)
    coarse_gold_list = build_coarse_view(gold_doc)
    coarse_gold = {record["sample_id"]: record for record in coarse_gold_list}
    if len(coarse_gold) != 150:
        raise RuntimeError("coarse Gold must contain 150 records")

    arms = {arm: load_arm(arm) for arm in ARM_PATHS}
    report: dict[str, Any] = {
        "schema_version": "sep_c3_modular_paired_error_attribution@1.0.0",
        "status": "complete_zero_api",
        "network_calls": 0,
        "llm_calls": 0,
        "diagnostic_contract": {
            "gold_view": "bpc_hybrid.g04_coarse_view.build_coarse_view",
            "match_rule": "stage2_sun_literal_overlap independent same-field any non-empty character intersection",
            "sample_field_correct": "all predicted spans in the sample-field are matched and all coarse Gold spans are matched",
            "boundary_counts": "diagnostic overlay only; not used to recompute the official F1",
            "modality_label": "record-level first non-empty label; reported separately from span fields",
            "cross_field_candidates": "diagnostic only; nested/overlapping Gold field spans can produce legitimate cross-field overlaps",
        },
        "gold": {
            "path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(GOLD_PATH),
            "records": len(gold_doc["records"]),
        },
        "arms": {},
        "pair_analyses": {},
        "representative_cases": {},
        "semantic_change_audit": {},
        "raw_format_audit": {},
        "unresolved_or_confounded": [
            "All arms are single runs; paired differences include run-to-run generation variation.",
            "The original four arms and the new four arms are batch/time confounded; cross-batch pair attribution is descriptive only.",
            "Boundary and cross-field counts are derived diagnostics, not altered official metrics.",
        ],
    }

    for arm_name, arm in arms.items():
        report["arms"][arm_name] = {
            "path": arm["path"],
            "canonical_predictions_sha256": sha256_file(
                Path(ROOT) / arm["path"] / "canonical_predictions.jsonl"),
            "evaluation_sha256": sha256_file(Path(ROOT) / arm["path"] / "evaluation.json"),
            "manifest_sha256": sha256_file(Path(ROOT) / arm["path"] / "manifest.json"),
            "primary_metric": primary_metric(arm["evaluation"]),
            "coarse_five_field_mean_f1": primary_metric(arm["evaluation"]),
            "coarse_five_field_micro": arm["evaluation"]["evaluation"]["coarse_five_field_micro"],
            "modality_labels": arm["evaluation"]["evaluation"]["modality_labels"],
            "five_fields": arm["evaluation"]["evaluation"]["five_fields"],
            "boundary_diagnostics": boundary_diagnostics_for_arm(coarse_gold, arm),
            "raw_format": raw_format_stats(arm),
        }

    for pair_id, baseline_arm, variant_arm, batch_relation, purpose in PAIR_DEFS:
        pair = evaluate_pair(coarse_gold, arms, baseline_arm, variant_arm)
        pair.update({
            "pair_id": pair_id,
            "batch_relation": batch_relation,
            "purpose": purpose,
            "baseline_primary_metric": primary_metric(arms[baseline_arm]["evaluation"]),
            "variant_primary_metric": primary_metric(arms[variant_arm]["evaluation"]),
        })
        pair["primary_metric_delta_variant_minus_baseline"] = (
            pair["variant_primary_metric"] - pair["baseline_primary_metric"])
        report["pair_analyses"][pair_id] = pair

    # Representative cases are selected only from the pairs needed for the
    # Stage-2 narrative. They are real artifacts, not synthetic examples.
    report["representative_cases"] = {
        "e_fixes_actor_000_to_100": select_cases(
            coarse_gold, arms, "000", "100", "actor", "fixed", limit=3),
        "e_fixes_constraint_000_to_100": select_cases(
            coarse_gold, arms, "000", "100", "constraint", "fixed", limit=3),
        "s_fixes_actor_000_to_010": select_cases(
            coarse_gold, arms, "000", "010", "actor", "fixed", limit=2),
        "s_fixes_constraint_000_to_010": select_cases(
            coarse_gold, arms, "000", "010", "constraint", "fixed", limit=3),
        "s_regresses_actor_101_to_111": select_cases(
            coarse_gold, arms, "101", "111", "actor", "regressed", limit=3),
        "s_regresses_constraint_101_to_111": select_cases(
            coarse_gold, arms, "101", "111", "constraint", "regressed", limit=3),
        "s_regresses_actor_100_to_110_cross_batch": select_cases(
            coarse_gold, arms, "100", "110", "actor", "regressed", limit=2),
        "s_regresses_constraint_100_to_110_cross_batch": select_cases(
            coarse_gold, arms, "100", "110", "constraint", "regressed", limit=2),
        "j_fixes_action_000_to_001": select_cases(
            coarse_gold, arms, "000", "001", "action", "fixed", limit=2),
        "j_regresses_action_000_to_001": select_cases(
            coarse_gold, arms, "000", "001", "action", "regressed", limit=2),
        "j_fixes_constraint_000_to_001": select_cases(
            coarse_gold, arms, "000", "001", "constraint", "fixed", limit=2),
    }

    for baseline_arm, variant_arm in (
        ("000", "001"), ("100", "101"), ("010", "011"), ("110", "111")):
        changed_samples = []
        changed_fields: Counter = Counter()
        clause_count_changed = 0
        for sample_id in coarse_gold:
            base_record = arms[baseline_arm]["by_id"][sample_id]["record"]
            var_record = arms[variant_arm]["by_id"][sample_id]["record"]
            if semantic_signature(base_record) != semantic_signature(var_record):
                changed_samples.append(sample_id)
            if len(base_record.get("clauses") or []) != len(var_record.get("clauses") or []):
                clause_count_changed += 1
            for field in SPAN_FIELDS:
                if field_semantic_signature(base_record, field) != field_semantic_signature(var_record, field):
                    changed_fields[field] += 1
        report["semantic_change_audit"][f"{baseline_arm}_to_{variant_arm}"] = {
            "semantic_changed_samples": len(changed_samples),
            "clause_count_changed_samples": clause_count_changed,
            "changed_sample_ids_sample": changed_samples[:20],
            "changed_field_sample_counts": dict(changed_fields),
            "note": (
                "Each arm is a separate LLM generation; changes include both "
                "the prompt factor and run-to-run variation. They cannot be "
                "attributed to the factor alone from single runs."
            ),
        }

    report["raw_format_audit"] = {
        arm: report["arms"][arm]["raw_format"]
        for arm in ("000", "001", "010", "100", "011", "110", "101", "111")
    }
    OUT_JSON.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(json.dumps({
        "pairs": {
            pair_id: {
                "baseline": data["baseline_arm"],
                "variant": data["variant_arm"],
                "delta_primary": data["primary_metric_delta_variant_minus_baseline"],
                "actor_fixed": data["fields"]["actor"]["fixed"],
                "actor_regressed": data["fields"]["actor"]["regressed"],
                "constraint_fixed": data["fields"]["constraint"]["fixed"],
                "constraint_regressed": data["fields"]["constraint"]["regressed"],
            }
            for pair_id, data in report["pair_analyses"].items()
        }
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

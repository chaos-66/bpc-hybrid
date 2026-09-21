# -*- coding: utf-8 -*-
"""Zero-API Phase-2 analysis for SEP-C3 targeted refinement A/B/C/D.

Reads the persisted run artifacts created by
``run_sep_c3_targeted_refinement_v1.py`` and writes:

* ``outputs/reports/sep_c3_targeted_refinement_v1_phase2_analysis.json``
* ``outputs/reports/sep_c3_targeted_refinement_v1_phase2_summary.json``
* ``outputs/reports/sep_c3_targeted_refinement_v1_phase2_evidence.md``

The script does not modify prompts, Gold, the evaluator, parser, canonicalizer,
or the persisted predictions.  Paired sample-field labels are reused from the
existing ``analyze_sep_c3_modular_paired_errors_v1`` diagnostic overlay, which
uses the frozen coarse evaluator's own intersection rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import analyze_sep_c3_modular_paired_errors_v1 as paired  # noqa: E402
from bpc_hybrid.g04_coarse_view import build_coarse_view  # noqa: E402
from bpc_hybrid.stage2_sun_literal_overlap import _field_spans  # noqa: E402

ARMS = ("A", "B", "C", "D")
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
REPORT_FIELDS = ("modality",) + SPAN_FIELDS
RUN_DIR = ROOT / "outputs" / "development" / "sep_c3_targeted_refinement_v1"
GOLD_PATH = ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json"
SCHEDULE_PATH = ROOT / "configs" / "sep_c3_targeted_refinement_schedule_v1.json"
BUDGET_PATH = ROOT / "configs" / "sep_c3_targeted_refinement_budget_v1.json"
FULL_JSON = ROOT / "outputs" / "reports" / "sep_c3_targeted_refinement_v1_phase2_analysis.json"
SUMMARY_JSON = ROOT / "outputs" / "reports" / "sep_c3_targeted_refinement_v1_phase2_summary.json"
EVIDENCE_MD = ROOT / "outputs" / "reports" / "sep_c3_targeted_refinement_v1_phase2_evidence.md"

CUE_ONLY_WORDS = {"only", "solely", "exclusively", "merely"}
LEXICAL_MARKER_PATTERNS = {
    "time_candidate": re.compile(
        r"\b(?:before|after|until|within|during|by|from|to|"
        r"january|february|march|april|may|june|july|august|september|"
        r"october|november|december|year|month|week|day|"
        r"19\d{2}|20\d{2})\b",
        re.IGNORECASE,
    ),
    "quantity_candidate": re.compile(
        r"\b(?:\d+(?:[.,]\d+)?\s*(?:%|percent|euro|eur|euros|"
        r"years?|months?|days?|hours?)|"
        r"amount|sum|maximum|minimum|at least|at most|more than|less than)\b",
        re.IGNORECASE,
    ),
    "purpose_candidate": re.compile(
        r"\b(?:for|to|in order to|so that|for the purpose of)\b",
        re.IGNORECASE,
    ),
    "legal_reference_candidate": re.compile(
        r"\b(?:section|sec\.|§|article|art\.|paragraph|abs\.|satz|act)\b",
        re.IGNORECASE,
    ),
    "exclusivity_candidate": re.compile(
        r"\b(?:only|solely|exclusively|merely)\b",
        re.IGNORECASE,
    ),
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_get(mapping: Mapping[str, Any] | None, *keys: str, default: Any = None) -> Any:
    cur: Any = mapping
    for key in keys:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def fmt_num(value: Any, digits: int = 4) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return str(value)
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_spans(spans: Sequence[Mapping[str, Any]]) -> str:
    if not spans:
        return "[]"
    return "; ".join(
        f"`{s.get('text')}` [{s.get('start')},{s.get('end')}]"
        for s in spans
    )


def normalize_span_text(span: Mapping[str, Any]) -> str:
    text = str(span.get("normalized") or span.get("text") or "").strip().lower()
    return " ".join(text.split())


def arm_dir(arm: str) -> Path:
    return RUN_DIR / arm / "repeat-01"


def load_arm(arm: str) -> dict[str, Any]:
    run_dir = arm_dir(arm)
    raw = read_jsonl(run_dir / "raw_responses.jsonl")
    rows = read_jsonl(run_dir / "canonical_predictions.jsonl")
    evaluation_doc = read_json(run_dir / "evaluation.json")
    evaluation = evaluation_doc.get("evaluation") or {}
    manifest = read_json(run_dir / "manifest.json")
    by_id = {str(row["sample_id"]): row for row in rows}
    raw_by_id = {str(row["sample_id"]): row for row in raw}
    if set(by_id) != set(raw_by_id):
        raise RuntimeError(f"raw/canonical membership mismatch for arm {arm}")
    return {
        "arm": arm,
        "path": str(run_dir.relative_to(ROOT)).replace("\\", "/"),
        "run_dir": run_dir,
        "raw": raw,
        "raw_by_id": raw_by_id,
        "rows": rows,
        "by_id": by_id,
        "evaluation": evaluation,
        "manifest": manifest,
    }


def gold_coarse() -> dict[str, dict[str, Any]]:
    gold_doc = read_json(GOLD_PATH)
    coarse_list = build_coarse_view(gold_doc)
    out = {str(record["sample_id"]): record for record in coarse_list}
    if len(out) != 150:
        raise RuntimeError(f"expected 150 coarse Gold records, got {len(out)}")
    return out


def arm_metric_bundle(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    evaluation = arm_data["evaluation"]
    fields = evaluation.get("five_fields") or {}
    modality = evaluation.get("modality_labels") or {}
    per_class = modality.get("per_class") or []
    macro_p = (
        sum(float(row.get("precision") or 0.0) for row in per_class) / len(per_class)
        if per_class else None
    )
    macro_r = (
        sum(float(row.get("recall") or 0.0) for row in per_class) / len(per_class)
        if per_class else None
    )
    bundle = {
        "primary_mean_f1": evaluation.get("coarse_five_field_mean_f1"),
        "micro_precision": safe_get(evaluation, "coarse_five_field_micro", "precision"),
        "micro_recall": safe_get(evaluation, "coarse_five_field_micro", "recall"),
        "micro_f1": safe_get(evaluation, "coarse_five_field_micro", "f1"),
        "micro_counts": evaluation.get("coarse_five_field_micro") or {},
        "modality_macro_f1": modality.get("macro_f1"),
        "modality_accuracy": modality.get("accuracy"),
        "modality_macro_precision": macro_p,
        "modality_macro_recall": macro_r,
        "modality_per_class": per_class,
        "fields": {},
    }
    for field in SPAN_FIELDS:
        bundle["fields"][field] = dict(fields.get(field) or {})
    return bundle


def field_metric(metrics: Mapping[str, Any], field: str, metric: str) -> Any:
    if field == "modality":
        return metrics.get(f"modality_{metric}_{'f1' if metric == 'f1' else metric}")
    return safe_get(metrics, "fields", field, metric)


def compute_arm_metrics(arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    return {arm: arm_metric_bundle(arms[arm]) for arm in ARMS}


def sample_all_fields_correct(gold_record: Mapping[str, Any],
                              prediction_row: Mapping[str, Any]) -> bool:
    return all(
        paired.sample_field_score(gold_record, prediction_row, field)["evaluator_correct"]
        for field in SPAN_FIELDS
    )


def overall_sample_overlay(gold: Mapping[str, Mapping[str, Any]],
                           arms: Mapping[str, Mapping[str, Any]],
                           baseline_arm: str,
                           variant_arm: str) -> dict[str, Any]:
    counts = Counter()
    sample_ids: dict[str, list[str]] = defaultdict(list)
    for sid, gold_record in gold.items():
        base_correct = sample_all_fields_correct(
            gold_record, arms[baseline_arm]["by_id"][sid])
        var_correct = sample_all_fields_correct(
            gold_record, arms[variant_arm]["by_id"][sid])
        if base_correct and var_correct:
            counts["both_correct"] += 1
        elif base_correct and not var_correct:
            counts["regressed"] += 1
            sample_ids["regressed"].append(sid)
        elif not base_correct and var_correct:
            counts["corrected"] += 1
            sample_ids["corrected"].append(sid)
        else:
            counts["both_wrong"] += 1
    counts["unchanged_total"] = counts["both_correct"] + counts["both_wrong"]
    return {
        "definition": (
            "overall sample-level diagnostic overlay: all five span fields are "
            "evaluator-correct under the frozen coarse intersection rule; "
            "corrected = baseline wrong and variant correct; "
            "regressed = baseline correct and variant wrong."
        ),
        "counts": dict(counts),
        "sample_ids": {k: v[:50] for k, v in sample_ids.items()},
    }


def empty_gold_false_positive(gold: Mapping[str, Mapping[str, Any]],
                              arm_data: Mapping[str, Any],
                              field: str) -> dict[str, Any]:
    field_count = 0
    span_count = 0
    sample_ids: list[str] = []
    for sid, gold_record in gold.items():
        gold_spans = _field_spans(gold_record, field)
        if gold_spans:
            continue
        pred_spans = _field_spans(
            arm_data["by_id"][sid].get("record") or {}, field)
        if pred_spans:
            field_count += 1
            span_count += len(pred_spans)
            sample_ids.append(sid)
    return {
        "unit": "sample_field_with_empty_Gold_and_nonempty_prediction",
        "field_count": field_count,
        "predicted_span_count": span_count,
        "sample_ids_sample": sample_ids[:50],
    }


def cue_stats(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    exact_only = 0
    only_any = 0
    cue_only_candidate = 0
    spans: list[dict[str, Any]] = []
    for row in arm_data["rows"]:
        record = row.get("record") or {}
        for clause in record.get("clauses") or []:
            for span in clause.get("constraints") or []:
                norm = normalize_span_text(span)
                tokens = re.findall(r"[a-z]+", norm)
                if norm == "only":
                    exact_only += 1
                if "only" in tokens:
                    only_any += 1
                if len(tokens) <= 2 and any(tok in CUE_ONLY_WORDS for tok in tokens):
                    cue_only_candidate += 1
                    spans.append({
                        "sample_id": row.get("sample_id"),
                        "text": span.get("text"),
                        "normalized": span.get("normalized"),
                    })
    return {
        "constraint_span_count": sum(
            len(clause.get("constraints") or [])
            for row in arm_data["rows"]
            for clause in (row.get("record") or {}).get("clauses") or []
        ),
        "exact_only_span_count": exact_only,
        "only_anywhere_span_count": only_any,
        "short_cue_only_candidate_count": cue_only_candidate,
        "short_cue_only_candidate_examples": spans[:20],
    }


def lexical_marker_flags(case: Mapping[str, Any]) -> dict[str, bool]:
    texts: list[str] = []
    for key in ("gold_coarse_spans", "baseline_spans", "variant_spans"):
        for span in case.get(key) or []:
            texts.append(str(span.get("text") or ""))
            texts.append(str(span.get("normalized") or ""))
    joined = " || ".join(texts)
    return {
        name: bool(pattern.search(joined))
        for name, pattern in LEXICAL_MARKER_PATTERNS.items()
    }


def select_targeted_cases(gold: Mapping[str, Mapping[str, Any]],
                          arms: Mapping[str, Mapping[str, Any]],
                          baseline_arm: str,
                          variant_arm: str,
                          field: str,
                          outcome: str,
                          predicate: Any = None,
                          limit: int = 5) -> list[dict[str, Any]]:
    cases = paired.select_cases(
        gold, arms, baseline_arm, variant_arm, field, outcome, limit=200)
    if predicate is not None:
        cases = [case for case in cases if predicate(case)]
    return cases[:limit]


def pair_targeted_analysis(gold: Mapping[str, Mapping[str, Any]],
                           arms: Mapping[str, Mapping[str, Any]],
                           baseline_arm: str,
                           variant_arm: str,
                           field: str,
                           overall_metrics: Mapping[str, Any]) -> dict[str, Any]:
    pair = paired.evaluate_pair(gold, arms, baseline_arm, variant_arm)
    field_stats = pair["fields"][field]
    corrected_cases = select_targeted_cases(
        gold, arms, baseline_arm, variant_arm, field, "fixed", limit=5)
    regressed_cases = select_targeted_cases(
        gold, arms, baseline_arm, variant_arm, field, "regressed", limit=200)
    over_cases = [
        case for case in regressed_cases
        if (
            int(case["variant_score"]["pred_count"])
            > int(case["baseline_score"]["pred_count"])
            or int(case["variant_score"]["unmatched_pred"])
            > int(case["baseline_score"]["unmatched_pred"])
        )
    ]
    under_cases = [
        case for case in regressed_cases
        if (
            int(case["variant_score"]["missed_gold"])
            > int(case["baseline_score"]["missed_gold"])
            or int(case["variant_score"]["pred_count"])
            < int(case["baseline_score"]["pred_count"])
        )
    ]
    regressed_cases = regressed_cases[:5]
    out = {
        "pair_id": f"{baseline_arm}_to_{variant_arm}",
        "baseline_arm": baseline_arm,
        "variant_arm": variant_arm,
        "field": field,
        "baseline_field_f1": safe_get(overall_metrics, baseline_arm, "fields", field, "f1"),
        "variant_field_f1": safe_get(overall_metrics, variant_arm, "fields", field, "f1"),
        "field_f1_delta_variant_minus_baseline": (
            (safe_get(overall_metrics, variant_arm, "fields", field, "f1") or 0.0)
            - (safe_get(overall_metrics, baseline_arm, "fields", field, "f1") or 0.0)
        ),
        "paired_field_counts": field_stats,
        "empty_gold_false_positive": {
            baseline_arm: empty_gold_false_positive(gold, arms[baseline_arm], field),
            variant_arm: empty_gold_false_positive(gold, arms[variant_arm], field),
        },
        "corrected_cases": corrected_cases,
        "regressed_cases": regressed_cases,
        "over_extraction_candidate_count": len(over_cases),
        "over_extraction_candidate_sample_ids": [c["sample_id"] for c in over_cases[:50]],
        "over_extraction_candidate_examples": over_cases[:5],
        "under_extraction_candidate_count": len(under_cases),
        "under_extraction_candidate_sample_ids": [c["sample_id"] for c in under_cases[:50]],
        "under_extraction_candidate_examples": under_cases[:5],
    }
    if field == "constraint":
        out["cue_stats"] = {
            baseline_arm: cue_stats(arms[baseline_arm]),
            variant_arm: cue_stats(arms[variant_arm]),
        }
    for key in ("corrected_cases", "regressed_cases",
                "over_extraction_candidate_examples",
                "under_extraction_candidate_examples"):
        for case in out.get(key) or []:
            case["lexical_marker_flags"] = lexical_marker_flags(case)
    return out


def compute_config_and_schedule_integrity(
    gold: Mapping[str, Mapping[str, Any]],
    arms: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    schedule = read_json(SCHEDULE_PATH)
    budget = read_json(BUDGET_PATH)
    schedule_by_key = {
        (str(e["arm"]), str(e["sample_id"])): e for e in schedule.get("entries") or []
    }
    deviations: list[dict[str, Any]] = []
    for arm in ARMS:
        seen: set[str] = set()
        for row in arms[arm]["raw"]:
            sid = str(row.get("sample_id") or "")
            if not sid or sid in seen:
                deviations.append({
                    "type": "duplicate_or_missing_sample",
                    "arm": arm,
                    "sample_id": sid,
                })
                continue
            seen.add(sid)
            entry = schedule_by_key.get((arm, sid))
            if entry is None:
                deviations.append({
                    "type": "sample_not_in_schedule",
                    "arm": arm,
                    "sample_id": sid,
                })
            elif int(row.get("execution_index", -1)) != int(entry["execution_index"]):
                deviations.append({
                    "type": "execution_index_mismatch",
                    "arm": arm,
                    "sample_id": sid,
                    "raw": row.get("execution_index"),
                    "schedule": entry["execution_index"],
                })
            if int(row.get("arm_order_within_sample", -1)) != int(
                entry.get("arm_order_within_sample", -2)
            ):
                deviations.append({
                    "type": "arm_order_mismatch",
                    "arm": arm,
                    "sample_id": sid,
                    "raw": row.get("arm_order_within_sample"),
                    "schedule": entry.get("arm_order_within_sample"),
                })
    global_ledger_path = RUN_DIR / "calls_ledger.jsonl"
    global_ledger = read_jsonl(global_ledger_path)
    if global_ledger:
        expected = schedule.get("entries") or []
        for index, row in enumerate(global_ledger):
            expected_row = expected[index] if index < len(expected) else None
            if expected_row is None:
                deviations.append({"type": "extra_global_ledger_row", "index": index})
                continue
            if (
                row.get("arm") != expected_row.get("arm")
                or str(row.get("sample_id")) != str(expected_row.get("sample_id"))
                or int(row.get("execution_index", -1)) != int(expected_row["execution_index"])
            ):
                deviations.append({
                    "type": "global_ledger_order_mismatch",
                    "index": index,
                    "ledger": {
                        "arm": row.get("arm"),
                        "sample_id": row.get("sample_id"),
                        "execution_index": row.get("execution_index"),
                    },
                    "schedule": expected_row,
                })

    expected_model = budget.get("model", {}).get("id")
    expected_release = budget.get("model", {}).get("documented_release")
    expected_sampling = budget.get("inference") or {}
    expected_prompt_hashes = {
        arm: safe_get(budget, "prompt_binding", "arm_composition_sha256", arm)
        for arm in ARMS
    }
    config_deviation_rows: list[dict[str, Any]] = []
    returned_models: Counter = Counter()
    for arm in ARMS:
        for row in arms[arm]["raw"]:
            returned_models[str(row.get("returned_model"))] += 1
            if row.get("model") != expected_model:
                config_deviation_rows.append({
                    "arm": arm,
                    "sample_id": row.get("sample_id"),
                    "field": "model",
                    "expected": expected_model,
                    "actual": row.get("model"),
                })
            if row.get("documented_release") != expected_release:
                config_deviation_rows.append({
                    "arm": arm,
                    "sample_id": row.get("sample_id"),
                    "field": "documented_release",
                    "expected": expected_release,
                    "actual": row.get("documented_release"),
                })
            if row.get("sampling_parameters") != expected_sampling:
                config_deviation_rows.append({
                    "arm": arm,
                    "sample_id": row.get("sample_id"),
                    "field": "sampling_parameters",
                    "expected": expected_sampling,
                    "actual": row.get("sampling_parameters"),
                })
            if row.get("rendered_prompt_version_hash") != expected_prompt_hashes.get(arm):
                config_deviation_rows.append({
                    "arm": arm,
                    "sample_id": row.get("sample_id"),
                    "field": "rendered_prompt_version_hash",
                    "expected": expected_prompt_hashes.get(arm),
                    "actual": row.get("rendered_prompt_version_hash"),
                })
    return {
        "schedule_path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
        "schedule_sha256": schedule.get("schedule_sha256"),
        "schedule_scheme": schedule.get("scheme"),
        "schedule_deviation_count": len(deviations),
        "schedule_deviations_sample": deviations[:50],
        "global_ledger_path": str(global_ledger_path.relative_to(ROOT)).replace("\\", "/"),
        "global_ledger_rows": len(global_ledger),
        "config_deviation_count": len(config_deviation_rows),
        "config_deviations_sample": config_deviation_rows[:50],
        "expected_model": expected_model,
        "expected_documented_release": expected_release,
        "expected_inference": expected_sampling,
        "returned_model_counts": dict(returned_models),
        "gold_sample_count": len(gold),
    }


def json_reliability(arm_data: Mapping[str, Any]) -> dict[str, Any]:
    raw = arm_data["raw"]
    rows = arm_data["rows"]
    bare = Counter(str(row.get("bare_json_status")) for row in raw)
    parsed_success = 0
    bare_object = 0
    for row in raw:
        content = str(row.get("raw_response_content") or "").strip()
        try:
            value = json.loads(content)
            parsed_success += 1
            if isinstance(value, dict) and content.startswith("{") and content.endswith("}"):
                bare_object += 1
        except Exception:
            pass
    validation = Counter()
    parser_status = Counter()
    canonicalizer_status = Counter()
    parser_warnings = 0
    canonicalizer_warnings = 0
    for row in rows:
        rec = row.get("record") or {}
        val = rec.get("validation") or {}
        if val.get("schema_valid") is True:
            validation["schema_valid_true"] += 1
        if val.get("cross_field_valid") is True:
            validation["cross_field_valid_true"] += 1
        if val.get("schema_valid") is True and val.get("cross_field_valid") is True:
            validation["canonical_valid_both_true"] += 1
        if val.get("errors"):
            validation["validation_errors_nonempty"] += 1
        pa = row.get("parser_audit") or {}
        ca = row.get("canonicalizer_audit") or {}
        parser_status[str(pa.get("status"))] += 1
        canonicalizer_status[str(ca.get("status"))] += 1
        if pa.get("status") in ("failed", "degraded") or pa.get("failed_reasons") or pa.get("dropped_spans"):
            parser_warnings += 1
        if (
            ca.get("status") in ("failed", "degraded")
            or ca.get("failed_reasons")
            or ca.get("dropped_spans")
            or ca.get("dropped_clauses")
            or ca.get("dropped_edges")
        ):
            canonicalizer_warnings += 1
    n = len(raw)
    return {
        "raw_rows": n,
        "bare_json_status_counts": dict(bare),
        "json_parsable_raw_content": parsed_success,
        "json_parsable_raw_rate": (parsed_success / n if n else 0.0),
        "bare_json_object_raw_content": bare_object,
        "bare_json_object_raw_rate": (bare_object / n if n else 0.0),
        "request_status_ok": sum(
            1 for row in rows if row.get("request_status") == "ok"),
        "parsed_output_present": sum(
            1 for row in rows if row.get("parsed_output") is not None),
        "canonical_output_nonempty": sum(
            1 for row in rows if row.get("canonical_output") is not None),
        "canonical_schema_valid_true": validation["schema_valid_true"],
        "canonical_cross_field_valid_true": validation["cross_field_valid_true"],
        "canonical_valid_both_true": validation["canonical_valid_both_true"],
        "canonical_valid_rate_both": (
            validation["canonical_valid_both_true"] / n if n else 0.0
        ),
        "validation_errors_nonempty": validation["validation_errors_nonempty"],
        "parser_status_counts": dict(parser_status),
        "canonicalizer_status_counts": dict(canonicalizer_status),
        "parser_warning_rows": parser_warnings,
        "canonicalizer_warning_rows": canonicalizer_warnings,
    }


def execution_integrity(gold: Mapping[str, Mapping[str, Any]],
                        arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    summary_path = RUN_DIR / "execution_summary.json"
    summary = read_json(summary_path) if summary_path.is_file() else {}
    raw_counts = {arm: len(arms[arm]["raw"]) for arm in ARMS}
    success = {
        arm: sum(1 for r in arms[arm]["raw"] if r.get("request_status") == "ok")
        for arm in ARMS
    }
    failed = {
        arm: sum(1 for r in arms[arm]["raw"] if r.get("request_status") != "ok")
        for arm in ARMS
    }
    expected_ids = set(gold)
    missing: dict[str, list[str]] = {}
    extra: dict[str, list[str]] = {}
    for arm in ARMS:
        actual = set(arms[arm]["by_id"])
        miss = sorted(expected_ids - actual)
        ext = sorted(actual - expected_ids)
        if miss:
            missing[arm] = miss
        if ext:
            extra[arm] = ext
    sets = [set(arms[arm]["by_id"]) for arm in ARMS]
    complete_sets = all(s == expected_ids for s in sets)
    attempted = sum(raw_counts.values())
    successful = sum(success.values())
    failed_total = sum(failed.values())
    resumed_by_arm: dict[str, int] = {}
    for run in summary.get("runs") or []:
        if isinstance(run, Mapping) and run.get("arm") in ARMS:
            resumed_by_arm[str(run["arm"])] = int(run.get("resumed_completed_count") or 0)
    resumed = sum(resumed_by_arm.get(arm, 0) for arm in ARMS)
    return {
        "planned_calls": 600,
        "attempted_calls": attempted,
        "successful_calls": successful,
        "failed_calls": failed_total,
        "successful_calls_per_arm": success,
        "failed_calls_per_arm": failed,
        "raw_counts_per_arm": raw_counts,
        "resumed_calls": resumed,
        "resumed_calls_per_arm": resumed_by_arm,
        "execution_summary_path": str(summary_path.relative_to(ROOT)).replace("\\", "/"),
        "execution_summary_complete": bool(summary.get("complete")),
        "execution_summary_aborted": bool(summary.get("aborted")),
        "execution_summary_abort_reason": summary.get("abort_reason"),
        "missing_samples_by_arm": missing,
        "extra_samples_by_arm": extra,
        "all_arms_have_all_samples": complete_sets,
        "canonical_valid_rate_per_arm": {
            arm: json_reliability(arms[arm])["canonical_valid_rate_both"]
            for arm in ARMS
        },
        "bare_json_object_rate_per_arm": {
            arm: json_reliability(arms[arm])["bare_json_object_raw_rate"]
            for arm in ARMS
        },
        "failed_rows_sample": [
            {
                "arm": arm,
                "sample_id": row.get("sample_id"),
                "request_status": row.get("request_status"),
                "error": row.get("error"),
                "gate_error": row.get("gate_error"),
            }
            for arm in ARMS
            for row in arms[arm]["raw"]
            if row.get("request_status") != "ok"
        ][:100],
    }


def pair_analysis(gold: Mapping[str, Mapping[str, Any]],
                  arms: Mapping[str, Mapping[str, Any]],
                  baseline_arm: str,
                  variant_arm: str,
                  arm_metrics: Mapping[str, Any]) -> dict[str, Any]:
    pair = paired.evaluate_pair(gold, arms, baseline_arm, variant_arm)
    out = dict(pair)
    out["primary_metric_delta_variant_minus_baseline"] = (
        float(safe_get(arm_metrics, variant_arm, "primary_mean_f1") or 0.0)
        - float(safe_get(arm_metrics, baseline_arm, "primary_mean_f1") or 0.0)
    )
    out["overall_sample_overlay"] = overall_sample_overlay(
        gold, arms, baseline_arm, variant_arm)
    return out


def interaction_values(arm_metrics: Mapping[str, Any]) -> dict[str, Any]:
    metrics = {
        "primary_mean_f1": lambda d: d["primary_mean_f1"],
        "actor_f1": lambda d: safe_get(d, "fields", "actor", "f1"),
        "constraint_f1": lambda d: safe_get(d, "fields", "constraint", "f1"),
        "actor_precision": lambda d: safe_get(d, "fields", "actor", "precision"),
        "actor_recall": lambda d: safe_get(d, "fields", "actor", "recall"),
        "constraint_precision": lambda d: safe_get(d, "fields", "constraint", "precision"),
        "constraint_recall": lambda d: safe_get(d, "fields", "constraint", "recall"),
    }
    out: dict[str, Any] = {}
    for name, getter in metrics.items():
        a = float(getter(arm_metrics["A"]) or 0.0)
        b = float(getter(arm_metrics["B"]) or 0.0)
        c = float(getter(arm_metrics["C"]) or 0.0)
        d = float(getter(arm_metrics["D"]) or 0.0)
        out[name] = {
            "A": a, "B": b, "C": c, "D": d,
            "I_M_equals_D_minus_B_minus_C_plus_A": d - b - c + a,
        }
    return out


def git_info(pre_run_head: str | None, pre_run_branch: str | None) -> dict[str, Any]:
    repo = ROOT.parent

    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=repo, text=True, encoding="utf-8", errors="replace"
        ).strip()

    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        head = git("rev-parse", "HEAD")
        status = git("status", "--short", "--branch").splitlines()
        commits = []
        if pre_run_head:
            commits = [
                line for line in git("log", "--oneline", f"{pre_run_head}..HEAD").splitlines()
                if line.strip()
            ]
        return {
            "pre_run_head": pre_run_head,
            "pre_run_branch": pre_run_branch,
            "post_run_head": head,
            "post_run_branch": branch,
            "new_commits": commits,
            "git_status_short": status,
        }
    except Exception as exc:  # pragma: no cover - report-only fallback.
        return {
            "pre_run_head": pre_run_head,
            "pre_run_branch": pre_run_branch,
            "error": str(exc),
        }


def render_markdown(full: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# SEP-C3 targeted refinement v1 — Phase 2 evidence")
    lines.append("")
    lines.append("Status: **complete zero-API analysis of the persisted A/B/C/D run**.")
    lines.append("")
    lines.append("## 1. Execution integrity")
    lines.append("")
    ex = full["execution_integrity"]
    lines.append(
        f"- Planned calls: {ex['planned_calls']}; attempted: {ex['attempted_calls']}; "
        f"successful: {ex['successful_calls']}; failed: {ex['failed_calls']}; "
        f"resumed: {ex['resumed_calls']}."
    )
    lines.append(f"- All four arms have all 150 samples: `{ex['all_arms_have_all_samples']}`.")
    lines.append(
        f"- Per-arm successful calls: "
        + ", ".join(f"{arm}={ex['successful_calls_per_arm'][arm]}" for arm in ARMS)
        + "."
    )
    lines.append(
        f"- Schedule deviations: {full['schedule_integrity']['schedule_deviation_count']}; "
        f"config deviations: {full['schedule_integrity']['config_deviation_count']}."
    )
    if ex["missing_samples_by_arm"] or ex["extra_samples_by_arm"] or ex["failed_calls"]:
        lines.append(f"- Missing samples: `{ex['missing_samples_by_arm']}`.")
        lines.append(f"- Extra samples: `{ex['extra_samples_by_arm']}`.")
        lines.append(f"- Failed rows: `{ex['failed_rows_sample']}`.")
    else:
        lines.append("- No missing sample/arm, extra sample, or failed call was observed.")
    lines.append("")
    lines.append("## 2. Frozen experiment identity")
    lines.append("")
    ident = full["experiment_identity"]
    lines.append(f"- Suite: `{ident['suite_id']}`; repeat: `{ident['repeat_id']}`.")
    lines.append(f"- Arms: {', '.join(ident['arms'])}.")
    lines.append(f"- Schedule: `{ident['schedule_path']}` SHA-256 `{ident['schedule_sha256']}` scheme `{ident['schedule_scheme']}`.")
    lines.append(f"- Model alias: `{ident['model_alias']}`; documented release: `{ident['documented_release']}`.")
    lines.append(f"- Returned model counts: `{full['schedule_integrity']['returned_model_counts']}`.")
    lines.append(f"- Temperature/top_p/max_tokens: {ident['temperature']}/{ident['top_p']}/{ident['max_tokens']}; retry=0; stream=false; thinking=disabled.")
    lines.append("")
    lines.append("## 3. Overall results")
    lines.append("")
    lines.append("| Arm | Mean F1 | Micro P | Micro R | Micro F1 |")
    lines.append("| --- | ------: | ------: | ------: | -------: |")
    for arm in ARMS:
        m = full["arm_metrics"][arm]
        lines.append(
            f"| {arm} | {fmt_num(m['primary_mean_f1'])} | "
            f"{fmt_num(m['micro_precision'])} | {fmt_num(m['micro_recall'])} | "
            f"{fmt_num(m['micro_f1'])} |"
        )
    lines.append("")
    lines.append("## 4. Per-field results")
    lines.append("")
    lines.append("| Field | A P/R/F1 | B P/R/F1 | C P/R/F1 | D P/R/F1 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for field in REPORT_FIELDS:
        cells = []
        for arm in ARMS:
            m = full["arm_metrics"][arm]
            if field == "modality":
                p = m["modality_macro_precision"]
                r = m["modality_macro_recall"]
                f = m["modality_macro_f1"]
            else:
                row = (m.get("fields") or {}).get(field) or {}
                p, r, f = row.get("precision"), row.get("recall"), row.get("f1")
            cells.append(f"{fmt_num(p)}/{fmt_num(r)}/{fmt_num(f)}")
        lines.append(f"| {field} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("*Modality is reported as a macro average over the evaluator's four label classes; it is separate from the five span fields.*")
    lines.append("")
    lines.append("## 5. A vs B actor analysis")
    lines.append("")
    actor_ab = full["actor_targeted_analysis"]["A_to_B"]
    lines.append(f"- Actor F1: A={fmt_num(actor_ab['baseline_field_f1'])}, B={fmt_num(actor_ab['variant_field_f1'])}, delta={fmt_num(actor_ab['field_f1_delta_variant_minus_baseline'])}.")
    lines.append(f"- Actor corrected sample-fields: {actor_ab['paired_field_counts']['fixed']}; regressed: {actor_ab['paired_field_counts']['regressed']}.")
    lines.append(f"- Unmatched actor predictions: A={actor_ab['paired_field_counts']['base_unmatched_pred']}, B={actor_ab['paired_field_counts']['var_unmatched_pred']}.")
    lines.append(f"- Empty-Gold actor false-positive sample-fields: A={actor_ab['empty_gold_false_positive']['A']['field_count']}, B={actor_ab['empty_gold_false_positive']['B']['field_count']}.")
    lines.append(f"- Actor over-extraction candidate regressions: {actor_ab['over_extraction_candidate_count']}; under-extraction/newly-missed candidate regressions: {actor_ab['under_extraction_candidate_count']}.")
    lines.append("")
    lines.append("## 6. C vs D actor analysis")
    lines.append("")
    actor_cd = full["actor_targeted_analysis"]["C_to_D"]
    lines.append(f"- Actor F1: C={fmt_num(actor_cd['baseline_field_f1'])}, D={fmt_num(actor_cd['variant_field_f1'])}, delta={fmt_num(actor_cd['field_f1_delta_variant_minus_baseline'])}.")
    lines.append(f"- Actor corrected sample-fields: {actor_cd['paired_field_counts']['fixed']}; regressed: {actor_cd['paired_field_counts']['regressed']}.")
    lines.append(f"- Unmatched actor predictions: C={actor_cd['paired_field_counts']['base_unmatched_pred']}, D={actor_cd['paired_field_counts']['var_unmatched_pred']}.")
    lines.append(f"- Empty-Gold actor false-positive sample-fields: C={actor_cd['empty_gold_false_positive']['C']['field_count']}, D={actor_cd['empty_gold_false_positive']['D']['field_count']}.")
    lines.append(f"- Actor over-extraction candidate regressions: {actor_cd['over_extraction_candidate_count']}; under-extraction/newly-missed candidate regressions: {actor_cd['under_extraction_candidate_count']}.")
    lines.append("")
    lines.append("## 7. A vs C constraint analysis")
    lines.append("")
    con_ac = full["constraint_targeted_analysis"]["A_to_C"]
    lines.append(f"- Constraint F1: A={fmt_num(con_ac['baseline_field_f1'])}, C={fmt_num(con_ac['variant_field_f1'])}, delta={fmt_num(con_ac['field_f1_delta_variant_minus_baseline'])}.")
    lines.append(f"- Constraint corrected sample-fields: {con_ac['paired_field_counts']['fixed']}; regressed: {con_ac['paired_field_counts']['regressed']}.")
    lines.append(f"- Constraint missed Gold: A={con_ac['paired_field_counts']['base_missed_gold']}, C={con_ac['paired_field_counts']['var_missed_gold']}.")
    lines.append(f"- Constraint unmatched predictions: A={con_ac['paired_field_counts']['base_unmatched_pred']}, C={con_ac['paired_field_counts']['var_unmatched_pred']}.")
    lines.append(f"- Exact isolated `only` constraints: A={con_ac['cue_stats']['A']['exact_only_span_count']}, C={con_ac['cue_stats']['C']['exact_only_span_count']}.")
    lines.append(f"- Over-extraction candidate regressions: {con_ac['over_extraction_candidate_count']}; under-extraction candidate regressions: {con_ac['under_extraction_candidate_count']}.")
    lines.append("")
    lines.append("## 8. B vs D constraint analysis")
    lines.append("")
    con_bd = full["constraint_targeted_analysis"]["B_to_D"]
    lines.append(f"- Constraint F1: B={fmt_num(con_bd['baseline_field_f1'])}, D={fmt_num(con_bd['variant_field_f1'])}, delta={fmt_num(con_bd['field_f1_delta_variant_minus_baseline'])}.")
    lines.append(f"- Constraint corrected sample-fields: {con_bd['paired_field_counts']['fixed']}; regressed: {con_bd['paired_field_counts']['regressed']}.")
    lines.append(f"- Constraint missed Gold: B={con_bd['paired_field_counts']['base_missed_gold']}, D={con_bd['paired_field_counts']['var_missed_gold']}.")
    lines.append(f"- Constraint unmatched predictions: B={con_bd['paired_field_counts']['base_unmatched_pred']}, D={con_bd['paired_field_counts']['var_unmatched_pred']}.")
    lines.append(f"- Exact isolated `only` constraints: B={con_bd['cue_stats']['B']['exact_only_span_count']}, D={con_bd['cue_stats']['D']['exact_only_span_count']}.")
    lines.append(f"- Over-extraction candidate regressions: {con_bd['over_extraction_candidate_count']}; under-extraction candidate regressions: {con_bd['under_extraction_candidate_count']}.")
    lines.append("")
    lines.append("Constraint lexical-marker candidates for manual review:")
    lines.append("")
    lines.append(
        "These are deterministic lexical-marker candidates, not a semantic "
        "category classifier; the frozen evaluator is unchanged."
    )
    for pair_key, data in full["constraint_lexical_marker_candidates"].items():
        rows = data.get("rows") or []
        lines.append(f"- {pair_key}: {len(rows)} selected corrected/regressed cases with at least one lexical marker.")
        for row in rows[:3]:
            flags = [name for name, value in (row.get("lexical_marker_flags") or {}).items() if value]
            lines.append(
                f"  - {row['sample_id']} ({row['outcome']}, "
                f"{row['baseline_arm']}->{row['variant_arm']}): {', '.join(flags)}"
            )
    lines.append("")
    lines.append("## 9. Combined arm analysis")
    lines.append("")
    lines.append("Pair-level primary deltas:")
    lines.append("")
    lines.append("| Comparison | Baseline mean F1 | Variant mean F1 | Delta |")
    lines.append("| --- | ------: | ------: | ------: |")
    for pair_id, pair in full["paired_comparisons"].items():
        base = pair["baseline_arm"]
        var = pair["variant_arm"]
        bm = full["arm_metrics"][base]["primary_mean_f1"]
        vm = full["arm_metrics"][var]["primary_mean_f1"]
        lines.append(
            f"| {base} vs {var} | {fmt_num(bm)} | {fmt_num(vm)} | "
            f"{fmt_num(pair['primary_metric_delta_variant_minus_baseline'])} |"
        )
    lines.append("")
    lines.append("Pair-level overall sample overlay (all five span fields evaluator-correct):")
    lines.append("")
    lines.append("| Comparison | Corrected | Regressed | Both correct | Both wrong | Unchanged total |")
    lines.append("| --- | ------: | ------: | ------: | ------: | ------: |")
    for pair_id, pair in full["paired_comparisons"].items():
        counts = pair["overall_sample_overlay"]["counts"]
        lines.append(
            f"| {pair['baseline_arm']} vs {pair['variant_arm']} | "
            f"{counts.get('corrected', 0)} | {counts.get('regressed', 0)} | "
            f"{counts.get('both_correct', 0)} | {counts.get('both_wrong', 0)} | "
            f"{counts.get('unchanged_total', 0)} |"
        )
    lines.append("")
    lines.append("Per-field paired fixed/regressed counts (fixed = baseline wrong -> variant correct):")
    lines.append("")
    lines.append("| Comparison | actor F/R | action F/R | condition F/R | constraint F/R | exception F/R |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for pair_id, pair in full["paired_comparisons"].items():
        cells = []
        for field in SPAN_FIELDS:
            f = pair["fields"][field]
            cells.append(f"{f['fixed']}/{f['regressed']}")
        lines.append(
            f"| {pair['baseline_arm']} vs {pair['variant_arm']} | "
            + " | ".join(cells) + " |"
        )
    lines.append("")
    pair_bd = full["paired_comparisons"]["B_vs_D"]
    pair_cd = full["paired_comparisons"]["C_vs_D"]
    lines.append("Observable D-related paired facts (descriptive only):")
    lines.append(
        f"- B->D actor fixed/regressed: {pair_bd['fields']['actor']['fixed']}/"
        f"{pair_bd['fields']['actor']['regressed']}; C->D actor: "
        f"{pair_cd['fields']['actor']['fixed']}/{pair_cd['fields']['actor']['regressed']}."
    )
    lines.append(
        f"- B->D constraint fixed/regressed: {pair_bd['fields']['constraint']['fixed']}/"
        f"{pair_bd['fields']['constraint']['regressed']}; C->D constraint: "
        f"{pair_cd['fields']['constraint']['fixed']}/{pair_cd['fields']['constraint']['regressed']}."
    )
    lines.append(
        f"- Exact isolated `only` constraints: B="
        f"{full['constraint_targeted_analysis']['B_to_D']['cue_stats']['B']['exact_only_span_count']}, "
        f"C={full['constraint_targeted_analysis']['A_to_C']['cue_stats']['C']['exact_only_span_count']}, "
        f"D={full['constraint_targeted_analysis']['B_to_D']['cue_stats']['D']['exact_only_span_count']}."
    )
    lines.append(
        f"- Overall sample corrected/regressed: B->D="
        f"{pair_bd['overall_sample_overlay']['counts']['corrected']}/"
        f"{pair_bd['overall_sample_overlay']['counts']['regressed']}; C->D="
        f"{pair_cd['overall_sample_overlay']['counts']['corrected']}/"
        f"{pair_cd['overall_sample_overlay']['counts']['regressed']}."
    )
    lines.append("")
    lines.append("## 10. Descriptive interaction")
    lines.append("")
    lines.append("$I_M = M_D - M_B - M_C + M_A$ (descriptive / observed only).")
    lines.append("")
    lines.append("| Metric | A | B | C | D | I_M |")
    lines.append("| --- | ------: | ------: | ------: | ------: | ------: |")
    for name, values in full["interaction_values"].items():
        lines.append(
            f"| {name} | {fmt_num(values['A'])} | {fmt_num(values['B'])} | "
            f"{fmt_num(values['C'])} | {fmt_num(values['D'])} | "
            f"{fmt_num(values['I_M_equals_D_minus_B_minus_C_plus_A'])} |"
        )
    lines.append("")
    lines.append(
        "No validated paired bootstrap utility was found in the repository for "
        "this experiment; only descriptive paired evidence is reported here. "
        "No new significance-testing procedure was added."
    )
    lines.append("")
    lines.append("## 11. Raw JSON / canonical reliability")
    lines.append("")
    lines.append("| Arm | Raw rows | Bare JSON object | Parsable JSON | Request OK | Canonical valid | Parser warning rows | Canonicalizer warning rows |")
    lines.append("| --- | ------: | ------: | ------: | ------: | ------: | ------: | ------: |")
    for arm in ARMS:
        r = full["raw_reliability"][arm]
        lines.append(
            f"| {arm} | {r['raw_rows']} | {r['bare_json_object_raw_content']} "
            f"({fmt_num(r['bare_json_object_raw_rate'])}) | "
            f"{r['json_parsable_raw_content']} ({fmt_num(r['json_parsable_raw_rate'])}) | "
            f"{r['request_status_ok']} | {r['canonical_valid_both_true']} "
            f"({fmt_num(r['canonical_valid_rate_both'])}) | "
            f"{r['parser_warning_rows']} | {r['canonicalizer_warning_rows']} |"
        )
    lines.append("")
    lines.append("## 12. Representative corrected cases")
    lines.append("")
    case_sets = [
        ("Actor corrected by R_A: A -> B", full["actor_targeted_analysis"]["A_to_B"]["corrected_cases"]),
        ("Actor corrected by R_A: C -> D", full["actor_targeted_analysis"]["C_to_D"]["corrected_cases"]),
        ("Constraint corrected by R_C: A -> C", full["constraint_targeted_analysis"]["A_to_C"]["corrected_cases"]),
        ("Constraint corrected by R_C: B -> D", full["constraint_targeted_analysis"]["B_to_D"]["corrected_cases"]),
    ]
    for title, cases in case_sets:
        lines.append(f"### {title}")
        lines.append("")
        if not cases:
            lines.append("_No paired corrected case selected._")
            lines.append("")
            continue
        for case in cases:
            lines.append(f"- **{case['sample_id']}** ({case['baseline_arm']}→{case['variant_arm']}, {case['field']})")
            lines.append(f"  - Source: `{case.get('source_text','')}`")
            lines.append(f"  - Gold: {fmt_spans(case.get('gold_coarse_spans') or [])}")
            lines.append(f"  - Baseline: {fmt_spans(case.get('baseline_spans') or [])}")
            lines.append(f"  - Variant: {fmt_spans(case.get('variant_spans') or [])}")
            lines.append(f"  - Observation: {case.get('mechanical_observation','')}")
        lines.append("")
    lines.append("## 13. Representative regressed cases")
    lines.append("")
    case_sets = [
        ("Actor regressed by R_A: A -> B", full["actor_targeted_analysis"]["A_to_B"]["regressed_cases"]),
        ("Actor regressed by R_A: C -> D", full["actor_targeted_analysis"]["C_to_D"]["regressed_cases"]),
        ("Constraint regressed by R_C: A -> C", full["constraint_targeted_analysis"]["A_to_C"]["regressed_cases"]),
        ("Constraint regressed by R_C: B -> D", full["constraint_targeted_analysis"]["B_to_D"]["regressed_cases"]),
    ]
    for title, cases in case_sets:
        lines.append(f"### {title}")
        lines.append("")
        if not cases:
            lines.append("_No paired regressed case selected._")
            lines.append("")
            continue
        for case in cases:
            lines.append(f"- **{case['sample_id']}** ({case['baseline_arm']}→{case['variant_arm']}, {case['field']})")
            lines.append(f"  - Source: `{case.get('source_text','')}`")
            lines.append(f"  - Gold: {fmt_spans(case.get('gold_coarse_spans') or [])}")
            lines.append(f"  - Baseline: {fmt_spans(case.get('baseline_spans') or [])}")
            lines.append(f"  - Variant: {fmt_spans(case.get('variant_spans') or [])}")
            lines.append(f"  - Observation: {case.get('mechanical_observation','')}")
        lines.append("")
    lines.append("## 14. Failures / anomalies")
    lines.append("")
    lines.append(f"- Failed calls: {full['execution_integrity']['failed_calls']}.")
    lines.append(f"- Schedule deviations: {full['schedule_integrity']['schedule_deviation_count']}.")
    lines.append(f"- Config deviations: {full['schedule_integrity']['config_deviation_count']}.")
    lines.append(f"- Execution summary aborted: `{full['execution_integrity']['execution_summary_aborted']}`; complete: `{full['execution_integrity']['execution_summary_complete']}`.")
    if full["execution_integrity"]["execution_summary_abort_reason"]:
        lines.append(f"- Abort reason: {full['execution_integrity']['execution_summary_abort_reason']}.")
    if full["execution_integrity"]["failed_rows_sample"]:
        lines.append(f"- Failed row sample: `{full['execution_integrity']['failed_rows_sample'][:10]}`.")
    lines.append("")
    lines.append("## 15. Artifact locations")
    lines.append("")
    lines.append(f"- Run root: `{full['artifact_locations']['run_root']}`.")
    lines.append(f"- A/B/C/D arm directories: `{full['artifact_locations']['arm_dirs']}`.")
    lines.append(f"- Raw responses: `{full['artifact_locations']['raw_responses']}`.")
    lines.append(f"- Global execution ledger / final order: `{full['artifact_locations']['global_ledger']}`.")
    lines.append(f"- Canonical predictions: `{full['artifact_locations']['canonical_predictions']}`.")
    lines.append(f"- Evaluation artifacts: `{full['artifact_locations']['evaluations']}`.")
    lines.append(f"- Manifests: `{full['artifact_locations']['manifests']}`.")
    lines.append(f"- Full analysis JSON: `{full['artifact_locations']['full_analysis_json']}`.")
    lines.append(f"- Summary JSON: `{full['artifact_locations']['summary_json']}`.")
    lines.append("")
    lines.append("## 16. Git status / commit information")
    lines.append("")
    g = full["git"]
    lines.append(f"- Branch: `{g.get('post_run_branch')}`; pre-run HEAD: `{g.get('pre_run_head')}`; post-run HEAD: `{g.get('post_run_head')}`.")
    lines.append(f"- New commits: `{g.get('new_commits', [])}`.")
    lines.append(f"- `git status --short --branch` lines: {len(g.get('git_status_short') or [])}.")
    lines.append("- Working tree lines (first 30):")
    for line in (g.get("git_status_short") or [])[:30]:
        lines.append(f"  - `{line}`")
    lines.append("")
    lines.append("*This report is descriptive. It does not modify the frozen prompts, Gold, evaluator, parser, canonicalizer, or dataset and does not state a research conclusion.*")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze SEP-C3 targeted refinement Phase 2 outputs.")
    parser.add_argument("--pre-run-head", default=None)
    parser.add_argument("--pre-run-branch", default=None)
    args = parser.parse_args()

    gold = gold_coarse()
    arms = {arm: load_arm(arm) for arm in ARMS}
    arm_metrics = compute_arm_metrics(arms)
    raw_reliability = {arm: json_reliability(arms[arm]) for arm in ARMS}
    schedule_integrity = compute_config_and_schedule_integrity(gold, arms)
    ex_integrity = execution_integrity(gold, arms)

    pair_defs = [
        ("A", "B"),
        ("A", "C"),
        ("A", "D"),
        ("B", "D"),
        ("C", "D"),
        ("B", "C"),
    ]
    pairs = {
        f"{base}_vs_{var}": pair_analysis(gold, arms, base, var, arm_metrics)
        for base, var in pair_defs
    }

    actor_ab = pair_targeted_analysis(gold, arms, "A", "B", "actor", arm_metrics)
    actor_cd = pair_targeted_analysis(gold, arms, "C", "D", "actor", arm_metrics)
    constraint_ac = pair_targeted_analysis(gold, arms, "A", "C", "constraint", arm_metrics)
    constraint_bd = pair_targeted_analysis(gold, arms, "B", "D", "constraint", arm_metrics)

    constraint_categories: dict[str, Any] = {}
    for pair_key, pair in (("A_to_C", constraint_ac), ("B_to_D", constraint_bd)):
        rows = []
        for case in (pair.get("corrected_cases") or []) + (pair.get("regressed_cases") or []):
            flags = case.get("lexical_marker_flags") or {}
            if any(flags.values()):
                rows.append({
                    "sample_id": case["sample_id"],
                    "outcome": case["outcome"],
                    "baseline_arm": case["baseline_arm"],
                    "variant_arm": case["variant_arm"],
                    "gold_spans": case.get("gold_coarse_spans"),
                    "baseline_spans": case.get("baseline_spans"),
                    "variant_spans": case.get("variant_spans"),
                    "lexical_marker_flags": flags,
                })
        constraint_categories[pair_key] = {
            "note": (
                "Deterministic lexical-marker candidates for manual follow-up only; "
                "this is not a semantic category classifier and does not change the evaluator."
            ),
            "rows": rows,
        }

    budget = read_json(BUDGET_PATH)
    full: dict[str, Any] = {
        "schema_version": "sep_c3_targeted_refinement_phase2_analysis@1.0.0",
        "suite_id": "SEP-C3-TARGETED-REFINEMENT-001",
        "status": "complete_zero_api",
        "network_calls": 0,
        "experiment_identity": {
            "suite_id": "SEP-C3-TARGETED-REFINEMENT-001",
            "repeat_id": "repeat-01",
            "arms": list(ARMS),
            "schedule_path": str(SCHEDULE_PATH.relative_to(ROOT)).replace("\\", "/"),
            "schedule_sha256": schedule_integrity.get("schedule_sha256"),
            "schedule_scheme": schedule_integrity.get("schedule_scheme"),
            "model_alias": schedule_integrity.get("expected_model"),
            "documented_release": schedule_integrity.get("expected_documented_release"),
            "temperature": safe_get(budget, "inference", "temperature"),
            "top_p": safe_get(budget, "inference", "top_p"),
            "max_tokens": safe_get(budget, "inference", "max_tokens"),
            "retry": safe_get(budget, "inference", "retry"),
            "stream": safe_get(budget, "inference", "stream"),
            "thinking": safe_get(budget, "inference", "thinking"),
        },
        "execution_integrity": ex_integrity,
        "schedule_integrity": schedule_integrity,
        "arm_metrics": arm_metrics,
        "raw_reliability": raw_reliability,
        "paired_comparisons": pairs,
        "actor_targeted_analysis": {"A_to_B": actor_ab, "C_to_D": actor_cd},
        "constraint_targeted_analysis": {"A_to_C": constraint_ac, "B_to_D": constraint_bd},
        "constraint_lexical_marker_candidates": constraint_categories,
        "interaction_values": interaction_values(arm_metrics),
        "artifact_locations": {
            "run_root": str(RUN_DIR.relative_to(ROOT)).replace("\\", "/"),
            "arm_dirs": {
                arm: str(arm_dir(arm).relative_to(ROOT)).replace("\\", "/")
                for arm in ARMS
            },
            "raw_responses": {
                arm: str((arm_dir(arm) / "raw_responses.jsonl").relative_to(ROOT)).replace("\\", "/")
                for arm in ARMS
            },
            "global_ledger": str((RUN_DIR / "calls_ledger.jsonl").relative_to(ROOT)).replace("\\", "/"),
            "canonical_predictions": {
                arm: str((arm_dir(arm) / "canonical_predictions.jsonl").relative_to(ROOT)).replace("\\", "/")
                for arm in ARMS
            },
            "evaluations": {
                arm: str((arm_dir(arm) / "evaluation.json").relative_to(ROOT)).replace("\\", "/")
                for arm in ARMS
            },
            "manifests": {
                arm: str((arm_dir(arm) / "manifest.json").relative_to(ROOT)).replace("\\", "/")
                for arm in ARMS
            },
            "full_analysis_json": str(FULL_JSON.relative_to(ROOT)).replace("\\", "/"),
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)).replace("\\", "/"),
        },
    }
    full["git"] = git_info(args.pre_run_head, args.pre_run_branch)

    # Summary keeps the required machine-readable fields and a compact case pointer.
    summary = {
        "schema_version": "sep_c3_targeted_refinement_phase2_summary@1.0.0",
        "suite_id": full["suite_id"],
        "status": full["status"],
        "execution_integrity": full["execution_integrity"],
        "arm_metrics": full["arm_metrics"],
        "per_field_metrics": {
            arm: {
                "five_fields": full["arm_metrics"][arm]["fields"],
                "modality": {
                    "macro_precision": full["arm_metrics"][arm]["modality_macro_precision"],
                    "macro_recall": full["arm_metrics"][arm]["modality_macro_recall"],
                    "macro_f1": full["arm_metrics"][arm]["modality_macro_f1"],
                    "accuracy": full["arm_metrics"][arm]["modality_accuracy"],
                    "per_class": full["arm_metrics"][arm]["modality_per_class"],
                },
            }
            for arm in ARMS
        },
        "paired_counts": {
            pair_id: {
                "baseline_arm": pair_data["baseline_arm"],
                "variant_arm": pair_data["variant_arm"],
                "primary_metric_delta_variant_minus_baseline": pair_data["primary_metric_delta_variant_minus_baseline"],
                "overall_sample_overlay": pair_data["overall_sample_overlay"]["counts"],
                "fields": {
                    field: {
                        "both_correct": field_data["both_correct"],
                        "fixed": field_data["fixed"],
                        "regressed": field_data["regressed"],
                        "both_wrong": field_data["both_wrong"],
                    }
                    for field, field_data in pair_data["fields"].items()
                },
            }
            for pair_id, pair_data in pairs.items()
        },
        "interaction_values": full["interaction_values"],
        "actor_targeted_analysis": {
            key: {
                "baseline_field_f1": value["baseline_field_f1"],
                "variant_field_f1": value["variant_field_f1"],
                "field_f1_delta_variant_minus_baseline": value["field_f1_delta_variant_minus_baseline"],
                "paired_field_counts": {
                    k: value["paired_field_counts"].get(k)
                    for k in ("both_correct", "fixed", "regressed", "both_wrong",
                              "base_unmatched_pred", "var_unmatched_pred",
                              "base_missed_gold", "var_missed_gold")
                },
                "empty_gold_false_positive": value["empty_gold_false_positive"],
                "over_extraction_candidate_count": value["over_extraction_candidate_count"],
                "under_extraction_candidate_count": value["under_extraction_candidate_count"],
            }
            for key, value in full["actor_targeted_analysis"].items()
        },
        "constraint_targeted_analysis": {
            key: {
                "baseline_field_f1": value["baseline_field_f1"],
                "variant_field_f1": value["variant_field_f1"],
                "field_f1_delta_variant_minus_baseline": value["field_f1_delta_variant_minus_baseline"],
                "paired_field_counts": {
                    k: value["paired_field_counts"].get(k)
                    for k in ("both_correct", "fixed", "regressed", "both_wrong",
                              "base_unmatched_pred", "var_unmatched_pred",
                              "base_missed_gold", "var_missed_gold")
                },
                "cue_stats": value.get("cue_stats"),
                "over_extraction_candidate_count": value["over_extraction_candidate_count"],
                "under_extraction_candidate_count": value["under_extraction_candidate_count"],
            }
            for key, value in full["constraint_targeted_analysis"].items()
        },
        "raw_reliability": full["raw_reliability"],
        "schedule_integrity": full["schedule_integrity"],
        "artifact_locations": full["artifact_locations"],
        "git": full["git"],
    }
    write_json(FULL_JSON, full)
    write_json(SUMMARY_JSON, summary)
    write_text(EVIDENCE_MD, render_markdown(full))
    print(json.dumps({
        "status": "ok",
        "full_analysis": str(FULL_JSON.relative_to(ROOT)).replace("\\", "/"),
        "summary": str(SUMMARY_JSON.relative_to(ROOT)).replace("\\", "/"),
        "evidence": str(EVIDENCE_MD.relative_to(ROOT)).replace("\\", "/"),
        "attempted_calls": ex_integrity["attempted_calls"],
        "successful_calls": ex_integrity["successful_calls"],
        "failed_calls": ex_integrity["failed_calls"],
        "schedule_deviations": schedule_integrity["schedule_deviation_count"],
        "config_deviations": schedule_integrity["config_deviation_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

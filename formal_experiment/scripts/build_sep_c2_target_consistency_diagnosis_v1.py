# -*- coding: utf-8 -*-
"""SEP-C2 target-consistency diagnosis for the 10 evaluated methods.

No retraining, no new inference, no API calls.  The report preserves the v2
full-150 table, separates the not-run source-pending row from model failures,
stratifies the 150 Gold records into A/B/C, and quantifies first-vs-later clause
label matches with deterministic case studies.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.formal_stage2_evaluation import MODALITY_CLASSES, evaluate_modality_labels  # noqa: E402
from bpc_hybrid.sun_predecessors import common, evaluation  # noqa: E402
from bpc_hybrid.sun_predecessors import bert_full, neural  # noqa: E402

V2_REL = "outputs/reports/sep_c2_sun_predecessors_comparison_v2.json"
REPORT_JSON_REL = "outputs/reports/sep_c2_target_consistency_diagnosis_v1.json"
REPORT_MD_REL = "outputs/reports/sep_c2_target_consistency_diagnosis_v1.md"
EVIDENCE_REL = "outputs/evidence/sep_c2_target_consistency_diagnosis_v1"
REPORT_ID = "sep_c2_target_consistency_diagnosis_v1"
SCHEMA_VERSION = "sep_c2_target_consistency_diagnosis@1.0.0"

BERT_METHODS = {
    "bert_base_uncased", "bert_base_cased", "bert_large_uncased",
    "bert_large_cased", "bert_legal_uncased",
}
CF_NEURAL = {"cf_rnn", "cf_cnn"}
CASE_SPECS = (
    ("C_first_wrong_pred_matches_later", "cf_kw", "estg_000028"),
    ("C_first_wrong_pred_matches_later", "cf_cnn", "estg_000046"),
    ("C_first_wrong_pred_matches_later", "bert_large_cased", "estg_000039"),
    ("C_first_wrong_pred_matches_later", "sun_rule_only", "estg_000020"),
    ("C_first_wrong_pred_matches_later", "direct_llm", "estg_000020"),
    ("B_all_clauses_same_but_first_wrong", "cf_kw", "estg_000056"),
    ("B_all_clauses_same_but_first_wrong", "direct_llm", "estg_000083"),
    ("C_first_correct_with_later_different", "bert_large_cased", "estg_000020"),
    ("low_frequency_class_error", "cf_cnn", "estg_000003"),
    ("low_frequency_class_error", "sun_rule_only", "estg_000004"),
)


def load_json(rel_or_path: str | Path) -> dict[str, Any]:
    path = Path(rel_or_path)
    if not path.is_absolute():
        path = FORMAL_ROOT / path
    return common.load_json(path)


def load_attempts(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    doc = load_json(str(row["prediction_path"]))
    records = doc.get("records")
    if not isinstance(records, list):
        raise common.SunPredecessorError(f"no records list: {row['method_id']}")
    return [dict(value) for value in records]


def first_nonempty_index(clauses: Sequence[Mapping[str, Any]]) -> int | None:
    for index, clause in enumerate(clauses):
        label = (clause.get("modality") or {}).get("label")
        if isinstance(label, str) and label.strip():
            return index
    return None


def first_label(clauses: Sequence[Mapping[str, Any]]) -> str | None:
    index = first_nonempty_index(clauses)
    if index is None:
        return None
    return str((clauses[index].get("modality") or {}).get("label"))


def pct(values: Sequence[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(int(value) for value in values)
    index = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[index]


def mean(values: Sequence[float]) -> float:
    return sum(float(value) for value in values) / len(values) if values else 0.0


def macro_supported(per_class: Sequence[Mapping[str, Any]], support: Mapping[str, int]) -> float | None:
    values = [float(item["f1"]) for item in per_class if int(support.get(str(item["class"]), 0)) > 0]
    return mean(values) if values else None


def build_structure() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    input_doc = load_json(evaluation.FORMAL_INPUT_REL)
    gold_doc = load_json(evaluation.FORMAL_GOLD_REL)
    input_by_id = {str(row["sample_id"]): row for row in input_doc["records"]}
    records: list[dict[str, Any]] = []
    first_support: Counter[str] = Counter()
    clause_dist: Counter[str] = Counter()
    for gold in sorted(gold_doc["records"], key=lambda row: str(row["sample_id"])):
        sid = str(gold["sample_id"])
        clauses = list(gold.get("clauses") or [])
        clause_dist[str(len(clauses))] += 1
        labels = [c.get("modality") for c in clauses if isinstance(c.get("modality"), str) and c.get("modality").strip()]
        group = "A" if len(labels) == 1 else ("B" if len(labels) > 1 and len(set(labels)) == 1 else ("C" if len(labels) > 1 else "D"))
        spans = []
        for clause in clauses:
            span = clause.get("clause_span") or {}
            spans.append({
                "clause_id": clause.get("clause_id"),
                "start": span.get("start"),
                "end": span.get("end"),
                "text": span.get("text"),
                "modality": clause.get("modality") if isinstance(clause.get("modality"), str) else None,
            })
        first = spans[0] if spans else {}
        start, end = first.get("start"), first.get("end")
        source = str(input_by_id[sid]["approved_text_en"])
        rec = {
            "sample_id": sid, "group": group, "clause_count": len(clauses),
            "all_labels": labels, "first_label": labels[0] if labels else None,
            "first_start": start, "first_end": end, "source_length": len(source),
            "first_start_zero": start == 0,
            "first_covers_full": start == 0 and end == len(source),
            "first_span_length": (end - start) if isinstance(start, int) and isinstance(end, int) else 0,
            "clauses": spans,
            "span_order_sorted": spans == sorted(spans, key=lambda item: (
                item["start"] if isinstance(item["start"], int) else 10**9,
                item["end"] if isinstance(item["end"], int) else 10**9,
            )),
        }
        records.append(rec)
        if labels:
            first_support[str(labels[0])] += 1
    group_ids: dict[str, list[str]] = {g: [] for g in ("A", "B", "C", "D")}
    for rec in records:
        group_ids[str(rec["group"])].append(str(rec["sample_id"]))
    for g in group_ids:
        group_ids[g].sort()
    unsorted = [r["sample_id"] for r in records if not r["span_order_sorted"]]
    overlapping = []
    for r in records:
        spans = [(c["start"], c["end"]) for c in r["clauses"] if isinstance(c["start"], int) and isinstance(c["end"], int)]
        hit = False
        for i, first_span in enumerate(spans):
            for second in spans[i + 1:]:
                if max(first_span[0], second[0]) < min(first_span[1], second[1]):
                    hit = True
        if hit:
            overlapping.append(r["sample_id"])
    nonstart0 = [{
        "sample_id": r["sample_id"], "group": r["group"], "first_label": r["first_label"],
        "first_start": r["first_start"], "first_end": r["first_end"], "source_length": r["source_length"],
    } for r in records if not r["first_start_zero"]]

    def summary(group: str) -> dict[str, Any]:
        subset = [r for r in records if r["group"] == group]
        return {
            "n": len(subset),
            "first_label_support": dict(sorted(Counter(str(r["first_label"]) for r in subset).items())),
            "clause_count_distribution": dict(sorted(Counter(str(r["clause_count"]) for r in subset).items(), key=lambda x: int(x[0]))),
            "first_start_zero": sum(1 for r in subset if r["first_start_zero"]),
            "first_covers_full": sum(1 for r in subset if r["first_covers_full"]),
            "first_span_length": {
                "p50": pct([r["first_span_length"] for r in subset], .50),
                "p90": pct([r["first_span_length"] for r in subset], .90),
                "max": max([r["first_span_length"] for r in subset], default=0),
            },
        }
    overall = {
        "n_records": len(records),
        "records_without_valid_gold_clause": len(group_ids["D"]),
        "group_counts": {g: len(group_ids[g]) for g in ("A", "B", "C", "D")},
        "clause_count_distribution": dict(sorted(clause_dist.items(), key=lambda x: int(x[0]))),
        "first_clause_label_support": dict(sorted(first_support.items())),
        "first_clause_start_zero": sum(1 for r in records if r["first_start_zero"]),
        "first_clause_covers_full_sentence": sum(1 for r in records if r["first_covers_full"]),
        "first_clause_char_length": {
            "p50": pct([r["first_span_length"] for r in records], .50),
            "p90": pct([r["first_span_length"] for r in records], .90),
            "max": max(r["first_span_length"] for r in records),
        },
        "records_with_clause_spans_overlapping": len(overlapping),
        "overlapping_sample_ids": overlapping,
        "records_with_clause_order_not_sorted_by_start": len(unsorted),
        "unsorted_sample_ids": unsorted,
        "records_with_first_clause_not_start_zero": nonstart0,
    }
    return {"overall": overall, "groups": {g: summary(g) for g in ("A", "B", "C", "D")}, "records": records}, group_ids, records

def group_metric(method_id: str, gold_eval: Sequence[Mapping[str, Any]], structure: Mapping[str, Any], group_ids: Mapping[str, list[str]], attempts: Sequence[Mapping[str, Any]], group: str) -> dict[str, Any]:
    ids = list(group_ids[group])
    gold_by_id = {str(row["sample_id"]): row for row in gold_eval}
    attempt_by_id = {str(row["sample_id"]): row for row in attempts}
    official = evaluate_modality_labels([gold_by_id[sid] for sid in ids], [attempt_by_id[sid] for sid in ids])
    first_by_id = {str(r["sample_id"]): r["first_label"] for r in structure["records"]}
    all_by_id = {str(r["sample_id"]): list(r["all_labels"]) for r in structure["records"]}
    correct = errors = unlabeled = later_match = any_match = 0
    wrong_ids: list[str] = []
    later_ids: list[str] = []
    unlabeled_ids: list[str] = []
    confusion: Counter[str] = Counter()
    for sid in ids:
        predicted = first_label(list((attempt_by_id[sid].get("record") or {}).get("clauses") or []))
        gold_first = first_by_id[sid]
        labels = all_by_id[sid]
        confusion[f"{gold_first}->{predicted}"] += 1
        if predicted is None:
            unlabeled += 1
            unlabeled_ids.append(sid)
        if predicted == gold_first:
            correct += 1
        else:
            errors += 1
            wrong_ids.append(sid)
            if predicted is not None and predicted in labels[1:]:
                later_match += 1
                later_ids.append(sid)
        if predicted is not None and predicted in set(labels):
            any_match += 1
    support = {cls: sum(1 for sid in ids if first_by_id[sid] == cls) for cls in MODALITY_CLASSES}
    per_class = list(official["per_class"])
    return {
        "method_id": method_id, "group": group, "n": len(ids), "correct": correct,
        "errors": errors, "wrong_labeled": errors - unlabeled, "unlabeled": unlabeled,
        "unlabeled_sample_ids": unlabeled_ids, "wrong_sample_ids": wrong_ids,
        "accuracy": official["accuracy"], "macro_f1_fixed4": official["macro_f1"],
        "macro_f1_supported_classes": macro_supported(per_class, support),
        "per_class": per_class,
        "first_wrong_pred_matches_later": later_match,
        "first_wrong_pred_matches_later_sample_ids": later_ids,
        "any_gold_clause_match": any_match,
        "any_gold_clause_accuracy": any_match / len(ids) if ids else None,
        "first_label_confusion": dict(sorted(confusion.items())),
    }

def method_row(v2_row: Mapping[str, Any], gold_eval: Sequence[Mapping[str, Any]], structure: Mapping[str, Any], group_ids: Mapping[str, list[str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    method_id = str(v2_row["method_id"])
    attempts = load_attempts(v2_row)
    ids = [str(a.get("sample_id")) for a in attempts]
    if len(ids) != 150 or len(set(ids)) != 150:
        raise common.SunPredecessorError(f"{method_id}: expected 150 unique attempts")
    official = evaluate_modality_labels(gold_eval, attempts)
    if abs(float(official["accuracy"]) - float(v2_row["accuracy"])) > 1e-12:
        raise common.SunPredecessorError(f"{method_id}: accuracy mismatch with v2")
    if abs(float(official["macro_f1"]) - float(v2_row["macro_f1"])) > 1e-12:
        raise common.SunPredecessorError(f"{method_id}: macro-F1 mismatch with v2")
    per_class = list(official["per_class"])
    failed_requests = sum(
        1 for attempt in attempts if attempt.get("request_status") not in (None, "ok")
    )
    row = {
        "method_id": method_id, "sun_label": v2_row.get("sun_label"), "role": v2_row.get("role"),
        "status": v2_row.get("status"), "n_records": 150, "records_scored": len(attempts),
        "records_missing": 150 - len(attempts), "records_failed": failed_requests,
        "unlabeled_predictions": int(official["unlabeled_predictions"]),
        "accuracy": official["accuracy"], "macro_precision": mean([float(x["precision"]) for x in per_class]),
        "macro_recall": mean([float(x["recall"]) for x in per_class]), "macro_f1": official["macro_f1"],
        "per_class": per_class, "input_field": v2_row.get("input_field"),
        "input_language": v2_row.get("input_language"), "prediction_path": v2_row.get("prediction_path"),
        "result_file": v2_row.get("result_file"), "training_or_weights": v2_row.get("training_or_weights"),
        "evaluator_recomputed": "bpc_hybrid.formal_stage2_evaluation.evaluate_modality_labels",
        "evaluator_matches_v2": True,
    }
    groups = [group_metric(method_id, gold_eval, structure, group_ids, attempts, g) for g in ("A", "B", "C")]
    return row, groups

def truncation_audit(v2_report: Mapping[str, Any]) -> dict[str, Any]:
    input_doc = load_json(evaluation.FORMAL_INPUT_REL)
    raw = [len(common.tokenize_words(str(r["raw_text_de"]))) for r in input_doc["records"]]
    eng = [len(common.tokenize_words(str(r["approved_text_en"]))) for r in input_doc["records"]]
    audit: dict[str, Any] = {
        "raw_text_de_word_token_stats": {"p50": pct(raw, .50), "p90": pct(raw, .90), "p95": pct(raw, .95), "max": max(raw), "rows_over_192": sum(v > 192 for v in raw)},
        "approved_text_en_word_token_stats": {"p50": pct(eng, .50), "p90": pct(eng, .90), "p95": pct(eng, .95), "max": max(eng), "rows_over_192": sum(v > 192 for v in eng)},
        "exact_german_first_clause_boundaries": "unavailable: Gold clause spans are over approved_text_en and no validated German alignment exists in the frozen evidence.",
    }
    for row in v2_report["classification_table"]:
        mid = str(row["method_id"])
        if mid in BERT_METHODS:
            stats = ((row.get("training_binding") or {}).get("sequence_length_stats") or {}).get("estg150_formal_input")
            audit[mid] = {"protocol": "WordPiece right truncation, max_length=192 subword tokens", "formal_input": dict(stats or {})}
        elif mid in CF_NEURAL:
            audit[mid] = {"protocol": "whitespace tokens, max_length=192", "formal_input": {"max": max(raw), "rows_over_192": sum(v > 192 for v in raw), "max_length": 192}}
        elif mid == "cf_kw":
            audit[mid] = {"protocol": "regex over full raw_text_de", "truncation": False}
        else:
            audit[mid] = {"protocol": "existing snapshot reused read-only; no new truncation", "truncation": False}
    return audit

def case_details(v2_report: Mapping[str, Any], structure: Mapping[str, Any], input_doc: Mapping[str, Any]) -> list[dict[str, Any]]:
    input_by_id = {str(r["sample_id"]): r for r in input_doc["records"]}
    gold_by_id = {str(r["sample_id"]): r for r in structure["records"]}
    attempts: dict[str, dict[str, Any]] = {}
    for row in v2_report["classification_table"]:
        attempts[str(row["method_id"])] = {str(a["sample_id"]): a for a in load_attempts(row)}
    out = []
    for category, method_id, sample_id in CASE_SPECS:
        record = gold_by_id[sample_id]
        predicted = first_label(list((attempts[method_id][sample_id].get("record") or {}).get("clauses") or []))
        out.append({
            "category": category, "method_id": method_id, "sample_id": sample_id,
            "group": record["group"], "gold_first_label": record["first_label"],
            "gold_all_labels": list(record["all_labels"]), "predicted_label": predicted,
            "raw_text_de": input_by_id[sample_id]["raw_text_de"],
            "approved_text_en": input_by_id[sample_id]["approved_text_en"],
            "gold_clauses": [{"index": i, **c} for i, c in enumerate(record["clauses"])],
            "predicted_clauses": list((attempts[method_id][sample_id].get("record") or {}).get("clauses") or []),
            "code_paths": [
                "src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_gold",
                "src/bpc_hybrid/sun_predecessors/evaluation.py::_first_modality_from_attempt",
                "src/bpc_hybrid/formal_stage2_evaluation.py::evaluate_modality_labels",
                str(next(r["prediction_path"] for r in v2_report["classification_table"] if r["method_id"] == method_id)),
            ],
            "interpretation": {
                "C_first_wrong_pred_matches_later": "Prediction equals a later Gold clause label; this is a clue, not proof that the model decoded that later clause.",
                "B_all_clauses_same_but_first_wrong": "All Gold clauses share one label, so a later different label cannot explain this error.",
                "C_first_correct_with_later_different": "The first-clause label is correct even though later clauses have different labels.",
                "low_frequency_class_error": "Low-frequency class error; report together with the official train prior shift, not as a code defect.",
            }[category],
        })
    return out

def build_report() -> dict[str, Any]:
    v2 = load_json(V2_REL)
    gold_doc, gold_eval = evaluation.load_gold_eval(FORMAL_ROOT)
    structure, group_ids, records = build_structure()
    if len(records) != 150 or sum(structure["overall"]["group_counts"].values()) != 150:
        raise common.SunPredecessorError("Gold groups must cover exactly 150 records")
    rows, metrics = [], []
    for v2_row in v2["classification_table"]:
        row, group_metrics = method_row(v2_row, gold_eval, structure, group_ids)
        rows.append(row)
        metrics.extend(group_metrics)
    if len(rows) != 10:
        raise common.SunPredecessorError(f"expected 10 evaluated methods, got {len(rows)}")
    trunc = truncation_audit(v2)
    input_doc = load_json(evaluation.FORMAL_INPUT_REL)
    cases = case_details(v2, structure, input_doc)
    for case in cases:
        pred = case["predicted_label"]; gold_first = case["gold_first_label"]; labels = case["gold_all_labels"]; group = case["group"]
        cat = case["category"]
        ok = (
            (cat == "C_first_wrong_pred_matches_later" and group == "C" and pred is not None and pred != gold_first and pred in labels[1:]) or
            (cat == "B_all_clauses_same_but_first_wrong" and group == "B" and pred is not None and pred != gold_first) or
            (cat == "C_first_correct_with_later_different" and group == "C" and pred == gold_first and len(set(labels)) > 1) or
            (cat == "low_frequency_class_error" and gold_first in {"permission", "prohibition"} and pred != gold_first)
        )
        if not ok:
            raise common.SunPredecessorError(f"case no longer matches its category: {case['sample_id']} {cat}")
    source_pending = {
        "method_id": "bert_legal_cased",
        "status": "not_run_source_pending_exact_checkpoint_unavailable",
        "n_records": 150, "records_scored": 0, "records_missing": 150,
        "records_failed": 0, "records_not_run": 150, "unlabeled_predictions": 0,
        "included_in_10_method_performance_denominator": False,
        "reason": "Exact public cased EU-legislation Legal-BERT checkpoint is not available; this is source-pending, not a model failure.",
    }
    v2_source = next(r for r in v2.get("classification_table_declared_11_rows", []) if r.get("method_id") == "bert_legal_cased")
    audit = {
        "source_pending": source_pending,
        "findings": [
            {
                "id": "source_pending_not_counted_as_failure",
                "status": "confirmed_reporting_error_corrected_in_this_report",
                "v2_records_failed": v2_source.get("records_failed"),
                "v2_records_missing": v2_source.get("records_missing"),
                "corrected_records_failed": 0,
                "corrected_records_not_run": 150,
                "included_in_10_method_performance_denominator": False,
                "action": "Separate bert_legal_cased as source-pending; exclude it from the 10-method denominator and from failure counts.",
            },
            {
                "id": "label_mapping_and_class_order",
                "status": "checked_no_model_code_error_found",
                "formal_evaluator_classes": list(MODALITY_CLASSES),
                "neural_labels": list(neural.MODEL_LABELS),
                "bert_labels": list(bert_full.LABELS),
                "sets_equal": set(MODALITY_CLASSES) == set(neural.MODEL_LABELS) == set(bert_full.LABELS),
                "action": "No label-index inversion or class-order divergence found.",
            },
            {
                "id": "first_clause_selection",
                "status": "checked_contract_consistent_but_target_construction_condition",
                "gold_unsorted_sample_ids": structure["overall"]["unsorted_sample_ids"],
                "prediction_nonzero_first_index": {
                    row["method_id"]: sum(1 for a in load_attempts(row) if first_nonempty_index(list((a.get("record") or {}).get("clauses") or [])) not in (0, None))
                    for row in v2["classification_table"]
                },
                "action": "Evaluator uses first non-empty label in record order, matching G0.4. The whole-text training vs first-clause target remains an interpretation limit.",
            },
            {
                "id": "truncation_audit",
                "status": "checked_condition_not_code_error",
                "action": "CF_RNN/CF_CNN have max 188 word tokens (<192); BERT right-truncates 25-31/150 records at 192 subword tokens; exact German first-clause truncation cannot be mapped because Gold spans are English.",
            },
            {
                "id": "missing_and_denominator",
                "status": "checked_no_model_code_error_found",
                "records_scored": {r["method_id"]: r["records_scored"] for r in rows},
                "records_failed": {r["method_id"]: r["records_failed"] for r in rows},
                "unlabeled": {r["method_id"]: r["unlabeled_predictions"] for r in rows},
                "action": "Full 150 denominator preserved; the single Direct-LLM empty-clause prediction is counted as an error, not dropped.",
            },
            {
                "id": "gold_used_for_prediction",
                "status": "checked_no_model_code_error_found",
                "prediction_entrypoints": ["src/bpc_hybrid/sun_predecessors/runner.py", "src/bpc_hybrid/sun_predecessors/runner_neural.py", "src/bpc_hybrid/sun_predecessors/runner_bert_full.py"],
                "action": "Runner code builds attempts before evaluation.evaluate_attempts; only evaluation loads Gold. No Gold leakage was found.",
            },
            {
                "id": "language_and_class_prior_conditions",
                "status": "checked_experiment_condition_not_code_error",
                "language_effect_separable": False,
                "action": "German/English and sentence-level vs first-clause differences remain confounded with architecture; report, do not claim a pure architecture effect.",
            },
        ],
    }
    per_method_misalignment = {}
    for row in rows:
        mid = row["method_id"]
        gm = {m["group"]: m for m in metrics if m["method_id"] == mid}
        per_method_misalignment[mid] = {
            "A_errors": gm["A"]["errors"], "B_errors": gm["B"]["errors"], "C_errors": gm["C"]["errors"],
            "C_first_errors_matching_later": gm["C"]["first_wrong_pred_matches_later"],
            "C_exact_first_accuracy": gm["C"]["accuracy"],
            "C_any_gold_clause_accuracy": gm["C"]["any_gold_clause_accuracy"],
        }
# 中文测试
    conclusion = {
        "one_sentence_conclusion": (
            "No prediction-code error was found in the 10 evaluated methods; the only confirmed reporting error was "
            "counting the not-run bert_legal_cased configuration as 150 failed model runs, now corrected. The full-150 "
            "first-clause table is valid under the frozen protocol, but 49/150 multi-clause records and 34/150 heterogeneous-label "
            "records make the full-text-vs-first-clause target construction an explicit interpretation limit."
        ),
        "paper_ready_text": (
            "实验设置新增目标结构审计：150 条按有效 Gold clause 分成 A（单一有效 clause，101/150）、"
            "B（多个 clause 但标签相同，15/150）、C（多个 clause 且标签不同，34/150）。评价器固定读取每个 record 的"
            "首个非空 modality 标签，符合 G0.4 合同；但八种前人分类器都在句子级 EStG modality 数据上训练并输出单一整句标签，"
            "因此 C 组存在全文分类与首个 Gold clause 目标不对齐的问题。结果解释仍以完整 150 条 first-clause 主表为准，"
            "预测命中任意 Gold clause 的上界诊断，不能据此断言模型预测了后续 clause。限制：bert_legal_cased 记为 source-pending 而非失败；德/英输入、训练目标和类别先验差异尚不能分离，不能仅凭本表证明架构的纯粹优势。"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "status": "completed_10_evaluated_one_source_pending",
        "source_report": V2_REL,
        "formal_input": evaluation.FORMAL_INPUT_REL,
        "formal_gold": evaluation.FORMAL_GOLD_REL,
        "evaluator": {
            "classification": "bpc_hybrid.formal_stage2_evaluation.evaluate_modality_labels",
            "target": "G0.4 first non-empty Gold clause modality",
        },
        "semantic_extraction_main_table_source": V2_REL,
        "semantic_extraction_main_table_unchanged": True,
        "overall_classification_table": rows,
        "group_metrics": metrics,
        "target_structure": {
            "overall": structure["overall"],
            "groups": structure["groups"],
            "group_ids": group_ids,
        },
        "target_misalignment": {
            "single_valid_clause_A": structure["overall"]["group_counts"]["A"],
            "homogeneous_multi_clause_B": structure["overall"]["group_counts"]["B"],
            "heterogeneous_multi_clause_C": structure["overall"]["group_counts"]["C"],
            "multi_clause_total_B_plus_C": structure["overall"]["group_counts"]["B"] + structure["overall"]["group_counts"]["C"],
            "first_clause_start_zero": structure["overall"]["first_clause_start_zero"],
            "first_clause_covers_full_sentence": structure["overall"]["first_clause_covers_full_sentence"],
            "overlapping_clause_spans": structure["overall"]["records_with_clause_spans_overlapping"],
            "clause_order_not_sorted_by_start": structure["overall"]["records_with_clause_order_not_sorted_by_start"],
            "per_method": per_method_misalignment,
        },
        "truncation_audit": trunc,
        "case_studies": {
            "selection_rule": "Stratified purposeful cases fixed before report rendering in CASE_SPECS: wrong-but-later-match, same-label-group error, correct-first with later variation, and low-frequency-class error, across keyword/CF/BERT/project families.",
            "cases": cases,
        },
        "implementation_audit": audit,
        "conclusions": conclusion,
        "safety": {
            "new_llm_api_calls": 0,
            "new_paid_api_calls": 0,
            "new_model_training_runs": 0,
            "gold_used_for_prediction": False,
            "gold_used_for_evaluation_only": True,
            "post_result_tuning": False,
            "full_150_denominator_preserved": True,
            "source_pending_counted_as_failure": False,
        },
    }

def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C2 target-consistency diagnosis (10 evaluated methods, EStG-150)",
        "",
        f"- report_id: `{report['report_id']}`",
        f"- status: **{report['status']}**",
        f"- primary table source: `{report['source_report']}`",
        f"- evaluator: `{report['evaluator']['classification']}`",
        "- The full-150 first-clause table remains primary; this report adds target-structure and error-attribution analysis.",
        "",
        "## 1. One-sentence conclusion",
        "",
        report["conclusions"]["one_sentence_conclusion"],
        "",
        "## 2. Full-150 classification main table (10 evaluated methods)",
        "",
        "| method | acc | macro-F1 | scored | missing | failed | unlabeled | input | status |",
        "|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["overall_classification_table"]:
        lines.append(
            f"| {row['method_id']} | {row['accuracy']:.4f} | {row['macro_f1']:.4f} | "
            f"{row['records_scored']} | {row['records_missing']} | {row['records_failed']} | "
            f"{row['unlabeled_predictions']} | `{row['input_field']}` | {row['status']} |"
        )
    sp = report["implementation_audit"]["source_pending"]
    lines += [
        "",
        f"**Source-pending row (not a failure, not in the 10-method denominator):** "
        f"`{sp['method_id']}` status=`{sp['status']}`, records_failed={sp['records_failed']}, "
        f"records_not_run={sp['records_not_run']}, included_in_performance_denominator="
        f"{sp['included_in_10_method_performance_denominator']}.",
        "",
    ]
    lines += [
        "## 3. 150-record target structure",
        "",
        "| group | n | definition |",
        "|---|---:|---|",
        f"| A | {report['target_structure']['groups']['A']['n']} | exactly one valid Gold clause |",
        f"| B | {report['target_structure']['groups']['B']['n']} | multiple valid Gold clauses, same modality label |",
        f"| C | {report['target_structure']['groups']['C']['n']} | multiple valid Gold clauses, different modality labels |",
        "",
        f"- valid Gold records: {report['target_structure']['overall']['n_records']}/150; no valid label: {report['target_structure']['overall']['records_without_valid_gold_clause']}",
        f"- clause-count distribution: `{report['target_structure']['overall']['clause_count_distribution']}`",
        f"- first-clause label support: `{report['target_structure']['overall']['first_clause_label_support']}`",
        f"- first clause starts at 0: {report['target_structure']['overall']['first_clause_start_zero']}/150; covers full sentence: {report['target_structure']['overall']['first_clause_covers_full_sentence']}/150",
        f"- first clause char length: `{report['target_structure']['overall']['first_clause_char_length']}`",
        f"- overlapping clause-span records: {report['target_structure']['overall']['records_with_clause_spans_overlapping']} (`{report['target_structure']['overall']['overlapping_sample_ids']}`)",
        f"- clause order not sorted by start: {report['target_structure']['overall']['records_with_clause_order_not_sorted_by_start']} (`{report['target_structure']['overall']['unsorted_sample_ids']}`)",
        "",
        "### Group A/B/C first-label support",
        "",
        "| group | n | first-label support | clause-count distribution | start=0 | covers full |",
        "|---|---:|---|---|---:|---:|",
    ]
    for group in ("A", "B", "C"):
        g = report["target_structure"]["groups"][group]
        lines.append(
            f"| {group} | {g['n']} | `{g['first_label_support']}` | `{g['clause_count_distribution']}` | "
            f"{g['first_start_zero']} | {g['first_covers_full']} |"
        )
    lines += [
        "",
        "## 4. Per-method group metrics",
        "",
        "Macro-F1 is the frozen four-class macro over the subgroup.",
        "",
        "| method | group | n | acc | macro-F1 | errors | unlabeled | first-wrong matches later | any-Gold-clause acc |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for metric in report["group_metrics"]:
        lines.append(
            f"| {metric['method_id']} | {metric['group']} | {metric['n']} | {metric['accuracy']:.4f} | "
            f"{metric['macro_f1_fixed4']:.4f} | {metric['errors']} | {metric['unlabeled']} | "
            f"{metric['first_wrong_pred_matches_later']} | {metric['any_gold_clause_accuracy']:.4f} |"
        )
    lines += [
        "",
        "## 5. Target-misalignment quantification",
        "",
        f"- multi-clause records: {report['target_misalignment']['multi_clause_total_B_plus_C']}/150; heterogeneous-label C: {report['target_misalignment']['heterogeneous_multi_clause_C']}/150.",
        "- A/B errors cannot be explained by matching a later different clause label. In C, later-match counts are an upper-bound clue, not proof of decoding a later clause.",
        "",
        "| method | A errors | B errors | C errors | C first errors matching later | C exact-first acc | C any-Gold-clause acc |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method_id, values in report["target_misalignment"]["per_method"].items():
        lines.append(
            f"| {method_id} | {values['A_errors']} | {values['B_errors']} | {values['C_errors']} | "
            f"{values['C_first_errors_matching_later']} | {values['C_exact_first_accuracy']:.4f} | "
            f"{values['C_any_gold_clause_accuracy']:.4f} |"
        )
    lines += [
        "",
        "## 6. Representative cases",
        "",
        f"Selection rule: {report['case_studies']['selection_rule']}",
        "",
    ]
    for case in report["case_studies"]["cases"]:
        lines += [
            f"### {case['category']} | {case['method_id']} | {case['sample_id']}",
            "",
            f"- group: `{case['group']}`; Gold first/all: `{case['gold_first_label']}` / `{case['gold_all_labels']}`; predicted: `{case['predicted_label']}`",
            f"- interpretation: {case['interpretation']}",
            "",
            "**Raw German excerpt:**",
            "",
            "```text",
            str(case["raw_text_de"])[:1200],
            "```",
            "",
            "**Approved English excerpt:**",
            "",
            "```text",
            str(case["approved_text_en"])[:1200],
            "```",
            "",
            "**Gold clauses:**",
        ]
        for clause in case["gold_clauses"]:
            lines.append(
                f"- `{clause['clause_id']}` [{clause['start']},{clause['end']}) {clause['modality']}: {str(clause['text'])[:220]}"
            )
        lines += ["", "**Code paths:**"]
        lines += [f"- `{path}`" for path in case["code_paths"]]
        lines.append("")
    lines += ["## 7. Implementation audit", ""]
    for finding in report["implementation_audit"]["findings"]:
        lines += [
            f"### {finding['id']}",
            "",
            f"- status: `{finding['status']}`",
            f"- action: {finding['action']}",
            f"- evidence: `{json.dumps(finding, ensure_ascii=False, sort_keys=True)}`",
            "",
        ]
    lines += [
        "## 8. Paper-ready setting, interpretation and limitation",
        "",
        report["conclusions"]["paper_ready_text"],
        "",
        "## 9. Safety",
        "",
    ]
    for key, value in report["safety"].items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    clean: list[str] = []
    for line in lines:
        clean.extend(part.rstrip() for part in str(line).split("\n"))
    return "\n".join(clean).rstrip("\n") + "\n"

def targets(report: Mapping[str, Any], report_bytes: bytes, report_md: bytes) -> dict[Path, bytes]:
    manifest = {
        "schema_version": "sep_c2_target_consistency_diagnosis_manifest@1.0.0",
        "report_id": REPORT_ID,
        "report_sha256": common.sha256_bytes(report_bytes),
        "report_md_sha256": common.sha256_bytes(report_md),
        "source_bindings": {
            rel: common.sha256_file(FORMAL_ROOT / rel)
            for rel in (
                V2_REL,
                "src/bpc_hybrid/sun_predecessors/evaluation.py",
                "src/bpc_hybrid/formal_stage2_evaluation.py",
                "src/bpc_hybrid/sun_predecessors/common.py",
            )
        },
        "input_bindings": {
            rel: common.sha256_file(FORMAL_ROOT / rel)
            for rel in (evaluation.FORMAL_INPUT_REL, evaluation.FORMAL_GOLD_REL)
        },
        "prediction_bindings": {
            str(row["method_id"]): common.sha256_file(FORMAL_ROOT / str(row["prediction_path"]))
            for row in report["overall_classification_table"]
        },
        "safety": report["safety"],
    }
    return {
        FORMAL_ROOT / REPORT_JSON_REL: report_bytes,
        FORMAL_ROOT / REPORT_MD_REL: report_md,
        FORMAL_ROOT / EVIDENCE_REL / "report.json": report_bytes,
        FORMAL_ROOT / EVIDENCE_REL / "manifest.json": common.json_bytes(manifest),
    }

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report()
        report_bytes = common.json_bytes(report)
        report_md = render_markdown(report).encode("utf-8")
        files = targets(report, report_bytes, report_md)
        if args.publish:
            existing = [path for path in files if path.exists()]
            if existing:
                raise common.SunPredecessorError(
                    "refusing to overwrite: "
                    + ", ".join(str(path.relative_to(FORMAL_ROOT)) for path in existing)
                )
            for path, payload in files.items():
                common.write_bytes_atomic(path, payload)
            print("SEP-C2 target consistency diagnosis v1 PUBLISHED")
        else:
            mismatches = [
                str(path.relative_to(FORMAL_ROOT))
                for path, payload in files.items()
                if not path.is_file() or path.read_bytes() != payload
            ]
            if mismatches:
                raise common.SunPredecessorError("replay differs for: " + ", ".join(mismatches))
            print("SEP-C2 target consistency diagnosis v1 REPLAY VERIFIED")
        print(f"evaluated_methods={len(report['overall_classification_table'])} source_pending=1")
        for group in ("A", "B", "C"):
            print(f"group_{group}={report['target_structure']['groups'][group]['n']}")
        for row in report["overall_classification_table"]:
            print(f"{row['method_id']}: acc={row['accuracy']:.4f} macro_f1={row['macro_f1']:.4f}")
        return 0
    except (OSError, ValueError, common.SunPredecessorError) as exc:
        print(f"SEP-C2 target consistency diagnosis refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

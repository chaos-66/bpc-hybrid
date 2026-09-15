# -*- coding: utf-8 -*-
"""Build the same-evaluator SEP-C2 predecessor comparison table.

Read-only evaluator phase.  It loads the predecessor capsules produced by the
method-specific runs and the existing B0/D1 formal-arm predictions.  It never
calls an LLM, never retrains, and never modifies Gold.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.formal_stage2_evaluation import (  # noqa: E402
    published_gold_to_evaluator,
)
from bpc_hybrid.stage2_sun_literal_overlap import evaluate_sun_literal_overlap  # noqa: E402
from bpc_hybrid.sun_predecessors import common, evaluation  # noqa: E402

EVIDENCE_REL = "outputs/evidence/sep_c2_sun_predecessors_v1"
REPORTS_REL = "outputs/reports"
COMPARISON_REL = f"{EVIDENCE_REL}/comparison"
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
DATASET_ID = "independently_reconstructed_estg_150_v1"


METHOD_ROWS: list[dict[str, str]] = [
    {
        "method_id": "cf_kw",
        "sun_source": "Sun et al. (2024) author-manuscript Table 7, CF_KW",
        "role": "keyword modality-classification baseline; no semantic extraction",
        "reproduction": "deterministic German keyword rules reconstructed because the paper omits the keyword list",
        "training_or_weights": "none (rule list frozen in configs/sep_c2_sun_predecessors_v1/cf_kw_v1.json)",
        "input_language": "de (raw_text_de)",
        "result_file": "outputs/reports/sep_c2_sun_predecessor_cf_kw_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "cf_rnn",
        "sun_source": "Sun et al. (2024) author-manuscript Table 7, CF_RNN (BiLSTM)",
        "role": "neural modality-classification baseline; no semantic extraction",
        "reproduction": "BiLSTM retrained locally on clean official EStG train split; unpublished hyperparameters disclosed",
        "training_or_weights": "official 300-d EStG vectors + locally trained BiLSTM (train 1927 / dev 414 clean rows)",
        "input_language": "de (raw_text_de)",
        "result_file": "outputs/reports/sep_c2_sun_predecessor_cf_rnn_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "cf_cnn",
        "sun_source": "Sun et al. (2024) author-manuscript Table 7, CF_CNN",
        "role": "neural modality-classification baseline; no semantic extraction",
        "reproduction": "3/4/5-gram CNN retrained locally on clean official EStG train split; unpublished hyperparameters disclosed",
        "training_or_weights": "official 300-d EStG vectors + locally trained TextCNN (train 1927 / dev 414 clean rows)",
        "input_language": "de (raw_text_de)",
        "result_file": "outputs/reports/sep_c2_sun_predecessor_cf_cnn_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "bert_legal_uncased_probe",
        "sun_source": "Sun et al. (2024) author-manuscript Table 6, bert-legal-uncased",
        "role": "pre-trained legal-BERT modality-classification comparison; no semantic extraction",
        "reproduction": "closest local public encoder (nlpaueb/legal-bert-base-uncased) frozen + locally trained MLP probe; full CPU fine-tuning not attempted",
        "training_or_weights": "public legal-BERT base uncased encoder + locally trained 256-unit MLP head on clean official train (1927/414)",
        "input_language": "de (raw_text_de)",
        "result_file": "outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_probe_v1.json",
        "status": "completed_zero_api_weaker_adaptation_disclosed",
    },
    {
        "method_id": "bert_legal_uncased_textcnn_existing",
        "sun_source": "Sun et al. (2024) final-paper-style BERT-TextCNN component (author-manuscript Table 6 best encoder family; final version Figure 3 architecture)",
        "role": "existing full fine-tuned BERT-TextCNN modality classifier reused read-only; diagnostic only",
        "reproduction": "reused existing project S2.4/S2.6 checkpoint; no retraining in this round",
        "training_or_weights": "existing S2.4 Legal-BERT + TextCNN checkpoint; original train split has 24 flagged EStG-150 overlap rows (4 exact normalized)",
        "input_language": "de (raw_text_de)",
        "result_file": "outputs/reports/sep_c2_sun_predecessor_bert_legal_uncased_textcnn_existing_v1.json",
        "status": "completed_diagnostic_training_overlap_flagged",
    },
    {
        "method_id": "sun_rule_only",
        "sun_source": "Sun et al. (2024) complete Stage 2 baseline as reconstructed by this project (B0 formal arm)",
        "role": "Sun/Rules-Only complete Stage 2 method; six-element extraction and modality",
        "reproduction": "project paper-faithful independent reconstruction; existing formal B0 arm reused read-only",
        "training_or_weights": "existing B0 checkpoint/config; no new training or LLM call in this comparison",
        "input_language": "de classifier input + en phrase input (existing B0 formal arm)",
        "result_file": "data/results/b0_formal_arm_v1/modality_labels.json",
        "status": "existing_formal_arm_reused_zero_api",
    },
    {
        "method_id": "direct_llm",
        "sun_source": "not a Sun method; direct LLM replacement arm in the project comparison",
        "role": "complete Stage 2 replacement; six-element extraction and modality",
        "reproduction": "existing Direct-LLM formal arm reused read-only; no new LLM call in this comparison",
        "training_or_weights": "existing Direct-LLM formal prediction snapshot",
        "input_language": "en (approved_text_en)",
        "result_file": "data/results/direct_llm_formal_arm_v1/modality_labels.json",
        "status": "existing_formal_arm_reused_zero_api",
    },
]

BLOCKED_METHODS = [
    {"method_id": name, "reason": "no local public weights; offline environment cannot download", "sun_source": f"Table 6, {name}"}
    for name in ("bert-base-uncased", "bert-base-cased", "bert-large-uncased", "bert-large-cased", "bert-legal-cased")
]


def _prediction_path(method_id: str) -> Path:
    if method_id in {"sun_rule_only", "direct_llm"}:
        dirname = {
            "sun_rule_only": "b0_formal_arm_v1",
            "direct_llm": "direct_llm_formal_arm_v1",
        }[method_id]
        return FORMAL_ROOT / "data/predictions" / dirname / "predictions.json"
    return FORMAL_ROOT / f"{EVIDENCE_REL}/{method_id}/predictions.json"


def _load_attempts(method_id: str) -> list[dict[str, Any]]:
    path = _prediction_path(method_id)
    document = common.load_json(path)
    records = document.get("records")
    if not isinstance(records, list):
        raise common.SunPredecessorError(f"prediction document has no records list: {path}")
    return [dict(row) for row in records]


def _macro(per_class: Sequence[Mapping[str, Any]], key: str) -> float:
    return sum(float(row[key]) for row in per_class) / len(per_class) if per_class else 0.0


def _modality_row(method: Mapping[str, str], attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    evaluated = evaluation.evaluate_attempts(FORMAL_ROOT, attempts)
    official = evaluated["official_evaluator"]
    per_class = list(official["per_class"])
    gold_by_id = {row["sample_id"]: row for row in evaluation.load_gold_eval(FORMAL_ROOT)[1]}
    attempt_by_id = {row["sample_id"]: row for row in attempts}
    examples = []
    for sample_id in sorted(gold_by_id):
        gold = evaluation._first_modality_from_gold(gold_by_id, sample_id)
        predicted = evaluation._first_modality_from_attempt(attempt_by_id.get(sample_id))
        if gold != predicted:
            examples.append({"sample_id": sample_id, "gold": gold, "predicted": predicted})
        if len(examples) >= 5:
            break
    return {
        **method,
        "task": "first-clause modality label (same frozen evaluator as B0/D1)",
        "n_records": evaluated["records_expected"],
        "records_scored": evaluated["records_scored"],
        "records_missing": evaluated["records_missing"],
        "records_failed": evaluated["records_failed"],
        "unlabeled_predictions": evaluated["unlabeled_predictions"],
        "accuracy": official["accuracy"],
        "macro_precision": _macro(per_class, "precision"),
        "macro_recall": _macro(per_class, "recall"),
        "macro_f1": official["macro_f1"],
        "per_class": per_class,
        "gold_support": evaluated["gold_support"],
        "predicted_count": evaluated["predicted_count"],
        "error_examples": examples,
    }


def _span_only_overall(per_field: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    extracted = sum(int(per_field[field]["extracted"]) for field in SPAN_FIELDS)
    ground_truth = sum(int(per_field[field]["ground_truth"]) for field in SPAN_FIELDS)
    matched_predictions = sum(int(per_field[field]["matched_predictions"]) for field in SPAN_FIELDS)
    matched_ground_truth = sum(int(per_field[field]["matched_ground_truth"]) for field in SPAN_FIELDS)
    precision = matched_predictions / extracted if extracted else 0.0
    recall = matched_ground_truth / ground_truth if ground_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "ground_truth": ground_truth,
        "extracted": extracted,
        "matched_predictions": matched_predictions,
        "matched_ground_truth": matched_ground_truth,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fields_included": list(SPAN_FIELDS),
        "excludes_modality_evidence": True,
    }


def _semantic_row(method: Mapping[str, str], attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    gold_doc, gold_eval = evaluation.load_gold_eval(FORMAL_ROOT)
    report = evaluate_sun_literal_overlap(
        gold_eval,
        list(attempts),
        dataset_id=DATASET_ID,
        method_id=method["method_id"],
    )
    per_field = {
        field: dict(report["per_field"][field])
        for field in SPAN_FIELDS
    }
    return {
        **method,
        "task": "Sun literal-overlap per-field span extraction (same evaluator as B0/D1)",
        "n_records": report["sample_count"],
        "invalid_attempt_count": report["invalid_attempt_count"],
        "per_field": per_field,
        "published_evaluator_overall": dict(report["overall"]),
        "span_only_overall": _span_only_overall(per_field),
        "modality_span_available": False,
        "modality_span_reason": "published Gold stores modality as a plain string; evidence spans are absent",
        "match_rule": report["match_rule"],
    }


def build_report() -> dict[str, Any]:
    modality_rows = []
    semantic_rows = []
    statuses = {}
    for method in METHOD_ROWS:
        method_id = method["method_id"]
        path = _prediction_path(method_id)
        if not path.is_file():
            statuses[method_id] = {"status": "missing_prediction_artifact", "path": str(path)}
            continue
        attempts = _load_attempts(method_id)
        modality_rows.append(_modality_row(method, attempts))
        if method_id in {"sun_rule_only", "direct_llm"}:
            semantic_rows.append(_semantic_row(method, attempts))
        else:
            semantic_rows.append(
                {
                    **method,
                    "task": "not_applicable",
                    "native_six_element_output": False,
                    "reason": "modality classifier only; it does not produce actor/action/condition/constraint/exception spans and must not be credited with six-element extraction",
                }
            )
        statuses[method_id] = {"status": "evaluated", "path": str(path)}
    return {
        "schema_version": "sep_c2_sun_predecessor_comparison@1.0.0",
        "report_id": "sep_c2_sun_predecessors_comparison_v1",
        "status": "completed_zero_api_same_evaluator_comparison",
        "dataset_id": DATASET_ID,
        "formal_input": "data/input/estg150_formal_inference_input_v2.json",
        "formal_gold": "data/gold/stage2/estg150_formal_gold_v1.json",
        "evaluator": {
            "modality": "bpc_hybrid.formal_stage2_evaluation.evaluate_modality_labels",
            "semantic": "bpc_hybrid.stage2_sun_literal_overlap.evaluate_sun_literal_overlap",
        },
        "version_scope": {
            "local_source": "earlier author manuscript (references/papers/extracted/sun_2024_full_text.txt)",
            "final_springer_version": "not accessible offline; not claimed as final-version reproduction",
            "final_version_check_status": "blocked_no_network",
        },
        "modality_table": modality_rows,
        "semantic_table": semantic_rows,
        "blocked_methods": BLOCKED_METHODS,
        "method_statuses": statuses,
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_used_for_evaluation_only": True,
            "post_result_tuning": False,
        },
    }


def _fmt(value: float) -> str:
    return f"{value:.4f}"


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C2 Sun predecessor comparison (EStG-150, same evaluator)",
        "",
        "- zero new LLM/API calls; existing B0/D1 formal predictions reused read-only",
        "- local source version: earlier author manuscript; final Springer version was not accessible offline",
        "",
        "## Modality classification (first-clause label, frozen evaluator)",
        "",
        "| method | Sun source/role | reproduction | training/weights | language | n | missing/failed/unlabeled | accuracy | macro P/R/F1 | result file | status |",
        "|---|---|---|---|---|---:|---|---:|---|---|---|",
    ]
    for row in report["modality_table"]:
        lines.append(
            "| {method_id} | {sun_source} | {reproduction} | {training_or_weights} | {input_language} | "
            "{n_records} | {records_missing}/{records_failed}/{unlabeled_predictions} | {acc} | "
            "{p}/{r}/{f1} | {result_file} | {status} |".format(
                **row,
                acc=_fmt(row["accuracy"]),
                p=_fmt(row["macro_precision"]),
                r=_fmt(row["macro_recall"]),
                f1=_fmt(row["macro_f1"]),
            )
        )
    lines += [
        "",
        "### Per-class modality metrics",
        "",
        "| method | class | precision | recall | F1 | gold support | predicted count |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["modality_table"]:
        for cls in row["per_class"]:
            lines.append(
                f"| {row['method_id']} | {cls['class']} | {_fmt(cls['precision'])} | "
                f"{_fmt(cls['recall'])} | {_fmt(cls['f1'])} | {row['gold_support'][cls['class']]} | "
                f"{row['predicted_count'][cls['class']]} |"
            )
    lines += [
        "",
        "## Semantic extraction",
        "",
        "Sun's author manuscript §5.2 reports only Sun's own extraction with no external six-element method comparison. "
        "The rows below are the methods in this project that can actually produce semantic fields; modality classifiers are marked N/A.",
        "",
        "| method | task | overall (published evaluator) P/R/F1 | five-span-only P/R/F1 | result file | status |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in report["semantic_table"]:
        if row.get("native_six_element_output") is False:
            lines.append(
                f"| {row['method_id']} | not applicable | N/A | N/A | {row['result_file']} | {row['status']} |"
            )
        else:
            overall = row["published_evaluator_overall"]
            span_only = row["span_only_overall"]
            lines.append(
                f"| {row['method_id']} | {row['task']} | "
                f"{_fmt(overall['precision'])}/{_fmt(overall['recall'])}/{_fmt(overall['f1'])} | "
                f"{_fmt(span_only['precision'])}/{_fmt(span_only['recall'])}/{_fmt(span_only['f1'])} | "
                f"{row['result_file']} | {row['status']} |"
            )
    lines += [
        "",
        "### Per-field semantic metrics (same literal-overlap evaluator)",
        "",
        "| method | field | ground truth | extracted | precision | recall | F1 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["semantic_table"]:
        if row.get("native_six_element_output") is False:
            continue
        for field, values in row["per_field"].items():
            lines.append(
                f"| {row['method_id']} | {field} | {values['ground_truth']} | {values['extracted']} | "
                f"{_fmt(values['precision'])} | {_fmt(values['recall'])} | {_fmt(values['f1'])} |"
            )
    lines += [
        "",
        "## Blocked/unsupported rows",
        "",
    ]
    for item in report["blocked_methods"]:
        lines.append(f"- {item['method_id']}: {item['reason']} ({item['sun_source']})")
    lines += [
        "",
        "## Error examples for the modality task",
        "",
        "| method | sample_id | gold | predicted |",
        "|---|---|---|---|",
    ]
    for row in report["modality_table"]:
        for example in row["error_examples"]:
            lines.append(
                f"| {row['method_id']} | {example['sample_id']} | {example['gold']} | {example['predicted']} |"
            )
    lines += [
        "",
        "Boundary: all values above are measured on the project's independently reconstructed EStG-150 with the frozen published Gold and the existing evaluators. "
        "They are not Sun's original 150-sentence phrase Gold and not the paper's reported numbers.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report()
        report_json = common.json_bytes(report)
        report_md = render_markdown(report).encode("utf-8")
        evidence_manifest = {
            "schema_version": "sep_c2_sun_predecessor_comparison_manifest@1.0.0",
            "report_id": report["report_id"],
            "method_statuses": report["method_statuses"],
            "source_bindings": {
                rel: {"sha256": common.sha256_file(FORMAL_ROOT / rel)}
                for rel in (
                    "src/bpc_hybrid/sun_predecessors/evaluation.py",
                    "src/bpc_hybrid/formal_stage2_evaluation.py",
                    "src/bpc_hybrid/stage2_sun_literal_overlap.py",
                    "data/input/estg150_formal_inference_input_v2.json",
                    "data/gold/stage2/estg150_formal_gold_v1.json",
                )
            },
            "safety": report["safety"],
        }
        manifest_json = common.json_bytes(evidence_manifest)
        targets = {
            FORMAL_ROOT / f"{REPORTS_REL}/sep_c2_sun_predecessors_comparison_v1.json": report_json,
            FORMAL_ROOT / f"{REPORTS_REL}/sep_c2_sun_predecessors_comparison_v1.md": report_md,
            FORMAL_ROOT / f"{COMPARISON_REL}/report.json": report_json,
            FORMAL_ROOT / f"{COMPARISON_REL}/manifest.json": manifest_json,
        }
        if args.publish:
            existing = [path for path in targets if path.exists()]
            if existing:
                raise common.SunPredecessorError(
                    "refusing to overwrite: " + ", ".join(str(path.relative_to(FORMAL_ROOT)) for path in existing)
                )
            for path, payload in targets.items():
                common.write_bytes_atomic(path, payload)
            print("SEP-C2 predecessor comparison PUBLISHED")
        else:
            mismatches = []
            for path, payload in targets.items():
                if not path.is_file() or path.read_bytes() != payload:
                    mismatches.append(str(path.relative_to(FORMAL_ROOT)))
            if mismatches:
                raise common.SunPredecessorError("replay differs for: " + ", ".join(mismatches))
            print("SEP-C2 predecessor comparison REPLAY VERIFIED")
        print(f"methods={[row['method_id'] for row in report['modality_table']]}")
        for row in report["modality_table"]:
            print(
                f"{row['method_id']}: acc={row['accuracy']:.4f} macro_f1={row['macro_f1']:.4f} "
                f"missing={row['records_missing']} failed={row['records_failed']} unlabeled={row['unlabeled_predictions']}"
            )
        return 0
    except (OSError, ValueError, common.SunPredecessorError) as exc:
        print(f"SEP-C2 comparison refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
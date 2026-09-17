# -*- coding: utf-8 -*-
"""Corrected SEP-C2 Sun predecessor comparison report (v2).

Historical note (2026-09-15): this report's not-run `bert_legal_cased` row is
counted as `records_failed=150`.  That source-pending accounting is superseded
by `build_sep_c2_target_consistency_diagnosis_v1.py`, which reports
`records_failed=0`, `records_not_run=150`, and excludes the row from the
10-method denominator.  This v2 output is retained as historical provenance.

Fixes the v1 report wiring:
* classification table uses exactly one evaluator for all rows;
* semantic extraction main table uses the project's coarse sentence-level Gold
  view and the five span-bearing fields (modality-evidence unavailable);
* fine five-field results are reported only as a diagnostic;
* input/target language and granularity conditions are stated explicitly;
* the missing exact bert-legal-cased checkpoint remains a named blocker.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

FORMAL_ROOT = Path(__file__).resolve().parents[1]
SRC = FORMAL_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_predecessors import common, dataset, evaluation  # noqa: E402

EVIDENCE_REL = "outputs/evidence/sep_c2_sun_predecessors_v1"
REPORT_REL = "outputs/reports"
COMPARISON_V2_REL = f"{EVIDENCE_REL}/comparison_v2"
SPAN_FIELDS = ("actor", "action", "condition", "constraint", "exception")
DATASET_ID = "independently_reconstructed_estg_150_v1"
REPORT_ID = "sep_c2_sun_predecessors_comparison_v2"


def _pred_path(row: Mapping[str, Any]) -> Path:
    return FORMAL_ROOT / str(row["prediction_path"])


def _load_attempts(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    document = common.load_json(_pred_path(row))
    records = document.get("records")
    if not isinstance(records, list):
        raise common.SunPredecessorError(f"prediction document has no records list: {_pred_path(row)}")
    return [dict(value) for value in records]


def _fmt(value: float | None, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    return f"{float(value):.{digits}f}"


def _macro(per_class: Sequence[Mapping[str, Any]], key: str) -> float:
    return sum(float(item[key]) for item in per_class) / len(per_class) if per_class else 0.0


def _aggregate_span_fields(per_field: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    extracted = sum(int(per_field[field]["extracted"]) for field in SPAN_FIELDS)
    ground_truth = sum(int(per_field[field]["ground_truth"]) for field in SPAN_FIELDS)
    matched_predictions = sum(
        int(round(float(per_field[field]["precision"]) * int(per_field[field]["extracted"])))
        for field in SPAN_FIELDS
    )
    matched_ground_truth = sum(
        int(round(float(per_field[field]["recall"]) * int(per_field[field]["ground_truth"])))
        for field in SPAN_FIELDS
    )
    precision = matched_predictions / extracted if extracted else 0.0
    recall = matched_ground_truth / ground_truth if ground_truth else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
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


CLASSIFICATION_ROWS: list[dict[str, Any]] = [
    {
        "method_id": "cf_kw",
        "sun_label": "CF_KW",
        "sun_source": "Sun et al. (2024) Table 7, CF_KW",
        "role": "keyword modality-classification baseline (no semantic extraction)",
        "reproduction": "deterministic German keyword rules reconstructed; paper publishes no keyword list",
        "training_or_weights": "none (rule list frozen in configs/sep_c2_sun_predecessors_v1/cf_kw_v1.json)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/cf_kw/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_cf_kw_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "cf_rnn",
        "sun_label": "CF_RNN (BiLSTM)",
        "sun_source": "Sun et al. (2024) Table 7, CF_RNN",
        "role": "BiLSTM modality-classification baseline (no semantic extraction)",
        "reproduction": "paper-described BiLSTM retrained on clean official EStG train split; unpublished hyperparameters disclosed",
        "training_or_weights": "official 300-d EStG vectors + locally trained BiLSTM (1927 train / 414 dev clean rows)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/cf_rnn/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_cf_rnn_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "cf_cnn",
        "sun_label": "CF_CNN",
        "sun_source": "Sun et al. (2024) Table 7, CF_CNN",
        "role": "CNN modality-classification baseline (no semantic extraction)",
        "reproduction": "paper-described CNN retrained on clean official EStG train split; unpublished hyperparameters disclosed",
        "training_or_weights": "official 300-d EStG vectors + locally trained TextCNN (1927 train / 414 dev clean rows)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/cf_cnn/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_cf_cnn_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "bert_base_uncased",
        "sun_label": "bert-base-uncased",
        "sun_source": "Sun et al. (2024) final version Table 6/7; Section 4.2.1 / Fig. 3 BERT-TextCNN",
        "role": "pre-trained BERT-TextCNN modality-classification comparison (no semantic extraction)",
        "reproduction": "public google-bert/bert-base-uncased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split",
        "training_or_weights": "public pinned BERT base uncased encoder + locally trained final-paper BERT-TextCNN head (1927/414)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_base_uncased/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_base_uncased_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "bert_base_cased",
        "sun_label": "bert-base-cased",
        "sun_source": "Sun et al. (2024) final version Table 6/7; Section 4.2.1 / Fig. 3 BERT-TextCNN",
        "role": "pre-trained BERT-TextCNN modality-classification comparison (no semantic extraction)",
        "reproduction": "public google-bert/bert-base-cased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split",
        "training_or_weights": "public pinned BERT base cased encoder + locally trained final-paper BERT-TextCNN head (1927/414)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_base_cased/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_base_cased_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "bert_large_uncased",
        "sun_label": "bert-large-uncased",
        "sun_source": "Sun et al. (2024) final version Table 6/7; Section 4.2.1 / Fig. 3 BERT-TextCNN",
        "role": "pre-trained BERT-TextCNN modality-classification comparison (no semantic extraction)",
        "reproduction": "public google-bert/bert-large-uncased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split",
        "training_or_weights": "public pinned BERT large uncased encoder + locally trained final-paper BERT-TextCNN head (1927/414)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_large_uncased/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_large_uncased_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "bert_large_cased",
        "sun_label": "bert-large-cased",
        "sun_source": "Sun et al. (2024) final version Table 6/7; Section 4.2.1 / Fig. 3 BERT-TextCNN",
        "role": "pre-trained BERT-TextCNN modality-classification comparison (no semantic extraction)",
        "reproduction": "public google-bert/bert-large-cased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split",
        "training_or_weights": "public pinned BERT large cased encoder + locally trained final-paper BERT-TextCNN head (1927/414)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_large_cased/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_large_cased_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "bert_legal_uncased",
        "sun_label": "bert-legal-uncased",
        "sun_source": "Sun et al. (2024) final version Table 6/7; Section 4.2.1 / Fig. 3 BERT-TextCNN",
        "role": "pre-trained BERT-TextCNN modality-classification comparison (no semantic extraction)",
        "reproduction": "public nlpaueb/legal-bert-base-uncased + final-paper per-layer [CLS] TextCNN head, fine-tuned jointly on clean official EStG train split",
        "training_or_weights": "public pinned Legal-BERT base uncased encoder + locally trained final-paper BERT-TextCNN head (1927/414)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_legal_uncased/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_legal_uncased_v1.json",
        "status": "completed_zero_api",
    },
    {
        "method_id": "sun_rule_only",
        "sun_label": "Sun/Rules-Only",
        "sun_source": "Project B0 formal arm: Sun Stage 2 method-level reconstruction",
        "role": "complete Stage 2 method: modality + five span fields",
        "reproduction": "existing B0 formal arm reused read-only; no new training or LLM call",
        "training_or_weights": "existing B0 checkpoint/config",
        "input_field": "raw_text_de (classifier) + approved_text_en (phrases)",
        "input_language": "de classifier / en phrase view",
        "prediction_path": "data/predictions/b0_formal_arm_v1/predictions.json",
        "result_file": "data/results/b0_formal_arm_v1/modality_labels.json",
        "status": "existing_formal_arm_reused_zero_api",
    },
    {
        "method_id": "direct_llm",
        "sun_label": "Direct-LLM",
        "sun_source": "Project Direct-LLM arm (not a Sun baseline)",
        "role": "complete Stage 2 method: modality + five span fields",
        "reproduction": "existing Direct-LLM formal prediction snapshot reused read-only; no new LLM call",
        "training_or_weights": "existing Direct-LLM prediction snapshot",
        "input_field": "approved_text_en",
        "input_language": "en",
        "prediction_path": "data/predictions/direct_llm_formal_arm_v1/predictions.json",
        "result_file": "data/results/direct_llm_formal_arm_v1/modality_labels.json",
        "status": "existing_formal_arm_reused_zero_api",
    },
]

SUPPLEMENTARY_BERT_ROWS: list[dict[str, Any]] = [
    {
        "method_id": "bert_legal_uncased_probe",
        "sun_label": "bert-legal-uncased (frozen-encoder probe; not the main method completion)",
        "sun_source": "Sun et al. (2024) Table 6 family; project supplement",
        "role": "diagnostic supplement: encoder frozen, MLP head only",
        "reproduction": "public nlpaueb/legal-bert-base-uncased frozen encoder + locally trained 256-unit MLP head",
        "training_or_weights": "frozen public encoder; local MLP head on clean official train (1927/414)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_legal_uncased_probe/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_legal_uncased_probe_v1.json",
        "status": "completed_diagnostic_supplement_weaker_adaptation",
        "limitation": "Not a replacement for full BERT-TextCNN fine-tuning; reported only to preserve the earlier probe evidence.",
    },
    {
        "method_id": "bert_legal_uncased_textcnn_existing",
        "sun_label": "Legal-BERT + TextCNN (existing S2.4 checkpoint; diagnostic only)",
        "sun_source": "Existing project final-paper-style BERT-TextCNN component",
        "role": "diagnostic reused checkpoint with known training/EStG-150 overlap",
        "reproduction": "existing S2.4/S2.6 checkpoint reused read-only; no retraining in this round",
        "training_or_weights": "existing legal-BERT + TextCNN checkpoint; original train split had 24 flagged EStG-150 overlap rows (4 exact normalized)",
        "input_field": "raw_text_de",
        "input_language": "de",
        "prediction_path": f"{EVIDENCE_REL}/bert_legal_uncased_textcnn_existing/predictions.json",
        "result_file": f"{REPORT_REL}/sep_c2_sun_predecessor_bert_legal_uncased_textcnn_existing_v1.json",
        "status": "completed_diagnostic_training_overlap_flagged",
        "limitation": "Not eligible as the clean main comparison because its training split overlaps EStG-150.",
    },
]

BLOCKED_ROW = {
    "method_id": "bert_legal_cased",
    "sun_label": "bert-legal-cased",
    "status": "blocked_exact_public_checkpoint_unavailable",
    "sun_source": "Sun et al. (2024) final version Table 6/7",
    "reason": (
        "The exact cased EU-legislation legal-BERT checkpoint ('bert-legal-cased') was not located in "
        "the checked official sources: Sun's text gives no model citation/version, the official "
        "Archive.org supplement contains data only, and the local official model cache contains "
        "nlpaueb/legal-bert-base-uncased but no cased legal-BERT. Project-record checks reported no "
        "exact Hugging Face/GitHub release. This is source-pending, not evidence that the model or "
        "public weights do not exist. A cased generic BERT or an uncased Legal-BERT is not allowed "
        "to occupy this exact configuration's completion position."
    ),
    "attempted_public_paths": [
        "https://huggingface.co/nlpaueb/legal-bert-base-cased (project-record check 404; no model page returned)",
        "Hugging Face model search (project record): legal-bert / eurlex / legal cased family; exact cased EU-legislation model not located",
        "GitHub repository title-matching the final paper (project record): only README/LICENSE; no model or training code",
        "Archive.org Decision_Logic_data.zip (2026-09-17 local inspection): data members only (EStG_raw.txt, EStG_sent_vec.csv, estg.html); no checkpoint or training code",
    ],
    "blocked_scope": "One of the nine requested baseline configurations remains open; all other eight predecessor configurations and the two project methods proceed.",
}


def _classification_row(row: Mapping[str, Any]) -> dict[str, Any]:
    attempts = _load_attempts(row)
    evaluated = evaluation.evaluate_attempts(FORMAL_ROOT, attempts)
    official = evaluated["official_evaluator"]
    per_class = list(official["per_class"])
    gold_by_id = {item["sample_id"]: item for item in evaluation.load_gold_eval(FORMAL_ROOT)[1]}
    attempt_by_id = {item["sample_id"]: item for item in attempts}
    examples = []
    for sample_id in sorted(gold_by_id):
        gold = evaluation._first_modality_from_gold(gold_by_id, sample_id)
        predicted = evaluation._first_modality_from_attempt(attempt_by_id.get(sample_id))
        if gold != predicted:
            examples.append({"sample_id": sample_id, "gold": gold, "predicted": predicted})
        if len(examples) >= 5:
            break
    report_path = FORMAL_ROOT / str(row["result_file"])
    training_binding = None
    if report_path.is_file():
        report = common.load_json(report_path)
        training = report.get("training")
        if isinstance(training, Mapping):
            training_binding = {
                "best_epoch": training.get("best_epoch"),
                "best_dev": training.get("best_dev"),
                "clean_train_rows": training.get("clean_train_rows"),
                "clean_dev_rows": training.get("clean_dev_rows"),
                "checkpoint": training.get("checkpoint"),
                "encoder": training.get("encoder"),
                "model_file_hashes": training.get("model_file_hashes"),
                "sequence_length_stats": training.get("sequence_length_stats"),
                "device": training.get("device"),
            }
    return {
        **row,
        "task": "first-clause modality label per project G0.4 coarse view",
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
        "training_binding": training_binding,
    }


def _semantic_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if row["method_id"] not in {"sun_rule_only", "direct_llm"}:
        return {
            **row,
            "semantic_output": False,
            "reason": "modality classifier only; no actor/action/condition/constraint/exception spans",
        }
    directory = {
        "sun_rule_only": "data/results/b0_formal_arm_v1",
        "direct_llm": "data/results/direct_llm_formal_arm_v1",
    }[row["method_id"]]
    coarse = common.load_json(FORMAL_ROOT / directory / "evaluation_coarse.json")
    fine = common.load_json(FORMAL_ROOT / directory / "evaluation_fine.json")
    coarse_fields = {field: dict(coarse["span_fields"][field]) for field in SPAN_FIELDS}
    fine_fields = {field: dict(fine["span_fields"][field]) for field in SPAN_FIELDS}
    return {
        **row,
        "semantic_output": True,
        "main_view": "coarse_sentence_level",
        "main_result_file": f"{directory}/evaluation_coarse.json",
        "main_five_field": _aggregate_span_fields(coarse_fields),
        "main_per_field": coarse_fields,
        "diagnostic_view": "fine_gold_clause_level",
        "diagnostic_result_file": f"{directory}/evaluation_fine.json",
        "diagnostic_five_field": _aggregate_span_fields(fine_fields),
        "diagnostic_per_field": fine_fields,
        "modality_span_available": False,
        "modality_span_reason": "published decision-only Gold stores modality as a plain string; modality evidence spans are unavailable",
        "no_cross_view_mixing": True,
    }


def _input_target_audit(external_root: Path) -> dict[str, Any]:
    input_doc = common.load_json(FORMAL_ROOT / evaluation.FORMAL_INPUT_REL)
    gold_doc = common.load_json(FORMAL_ROOT / evaluation.FORMAL_GOLD_REL)
    by_id = {row["sample_id"]: row for row in input_doc["records"]}
    clause_counts = Counter()
    first_start0 = 0
    first_full_sentence = 0
    first_labels = Counter()
    first_char_lengths = []
    for record in gold_doc["records"]:
        clauses = list(record.get("clauses") or [])
        clause_counts[str(len(clauses))] += 1
        if not clauses:
            continue
        clause = clauses[0]
        first_labels[str(clause.get("modality"))] += 1
        span = clause.get("clause_span") or {}
        start = int(span.get("start", 0))
        end = int(span.get("end", 0))
        source = by_id[record["sample_id"]]["approved_text_en"]
        if start == 0:
            first_start0 += 1
        if start == 0 and end == len(source):
            first_full_sentence += 1
        first_char_lengths.append(max(0, end - start))
    first_char_lengths.sort()
    def pct(values: Sequence[int], q: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))
        return int(values[index])
    splits = dataset.build_clean_splits(FORMAL_ROOT, Path(external_root))
    return {
        "schema_version": "sep_c2_predecessor_input_target_audit@1.0.0",
        "formal_input_records": len(input_doc["records"]),
        "gold_records": len(gold_doc["records"]),
        "classification_target_definition": (
            "Project G0.4 coarse sentence-level view: one synthetic clause over approved_text_en; "
            "modality label = first non-empty Gold clause modality string. This is a statement-level "
            "target extracted from the first Gold clause, not a request to classify only the first clause span."
        ),
        "gold_clause_count_distribution": dict(sorted(clause_counts.items(), key=lambda item: int(item[0]))),
        "gold_first_clause_start_zero": first_start0,
        "gold_first_clause_covers_full_sentence": first_full_sentence,
        "gold_first_clause_label_support": dict(sorted(first_labels.items())),
        "gold_first_clause_char_length": {
            "p50": pct(first_char_lengths, 0.50),
            "p90": pct(first_char_lengths, 0.90),
            "max": max(first_char_lengths) if first_char_lengths else 0,
        },
        "official_clean_split_audit": splits["audit"],
        "classification_input_conditions": [
            {
                "method_id": row["method_id"],
                "input_field": row["input_field"],
                "input_language": row["input_language"],
                "target": "first Gold clause modality per project G0.4",
            }
            for row in CLASSIFICATION_ROWS
        ],
        "language_comparability_note": (
            "Sun's official modality corpus is German and its archived sentence vectors are German. "
            "CF_KW/CF_RNN/CF_CNN and the six BERT-family rows therefore consume raw_text_de, which preserves "
            "the predecessor method's native language and available public training material. Direct-LLM uses "
            "approved_text_en because its prompt/snapshot was executed in English. The German/English difference "
            "is a method/design condition, not silently normalized away; no new paid LLM calls are made to translate it."
        ),
        "granularity_note": (
            "The predecessor classifiers receive the full formal-input statement in their native language, matching "
            "the sentence-level official training data. The target is the project's first-Gold-clause modality label. "
            "Where a formal input contains multiple clauses, this remains a target-construction difference and is "
            "reported rather than hidden."
        ),
        "class_prior_shift": {
            "eStG150_gold_first_clause": dict(sorted(first_labels.items())),
            "official_clean_train": splits["audit"]["final"]["train"]["label_distribution"],
            "official_clean_dev": splits["audit"]["final"]["dev"]["label_distribution"],
            "official_clean_test": splits["audit"]["final"]["test"]["label_distribution"],
        },
        "no_gold_used_for_prediction": True,
    }


def build_report(external_root: Path) -> dict[str, Any]:
    classification_rows = [_classification_row(row) for row in CLASSIFICATION_ROWS]
    semantic_rows = [_semantic_row(row) for row in CLASSIFICATION_ROWS]
    blocked_classification_row = {
        **BLOCKED_ROW,
        "task": "blocked: exact public checkpoint unavailable",
        "n_records": 150,
        "records_scored": 0,
        "records_missing": 150,
        "records_failed": 150,
        "unlabeled_predictions": 0,
        "accuracy": None,
        "macro_precision": None,
        "macro_recall": None,
        "macro_f1": None,
        "per_class": [],
        "gold_support": {},
        "predicted_count": {},
        "error_examples": [],
        "input_field": "raw_text_de",
        "input_language": "de",
        "result_file": None,
        "training_binding": None,
    }
    statuses = {
        row["method_id"]: {"status": row["status"], "prediction": row["prediction_path"]}
        for row in classification_rows
    }
    statuses[BLOCKED_ROW["method_id"]] = {
        "status": BLOCKED_ROW["status"],
        "reason": BLOCKED_ROW["reason"],
    }
    for row in SUPPLEMENTARY_BERT_ROWS:
        statuses[row["method_id"]] = {"status": row["status"], "prediction": row["prediction_path"], "diagnostic_only": True}
    all_evaluated = all(
        row["status"].startswith("completed") or row["status"].startswith("existing")
        for row in classification_rows
    )
    complete = all_evaluated and not BLOCKED_ROW
    return {
        "schema_version": "sep_c2_sun_predecessor_comparison@2.0.0",
        "report_id": REPORT_ID,
        "status": "completed_zero_api" if complete else "completed_with_one_exact_checkpoint_blocker",
        "supersedes": "sep_c2_sun_predecessors_comparison_v1",
        "dataset_id": DATASET_ID,
        "formal_input": evaluation.FORMAL_INPUT_REL,
        "formal_gold": evaluation.FORMAL_GOLD_REL,
        "evaluator": {
            "classification": "bpc_hybrid.formal_stage2_evaluation.evaluate_modality_labels",
            "semantic_main": "precomputed project G0.4 coarse sentence-level evaluation (five span fields)",
            "semantic_diagnostic": "precomputed project fine clause-level evaluation (five span fields)",
        },
        "version_scope": {
            "sun_source": "Sun et al. (2024) final version, DOI 10.1007/s11227-023-05626-0 (accessible and used to verify Fig. 3 / Section 4.2.1 architecture)",
            "local_author_manuscript": "also present; final-version architecture check removes the earlier offline-version caveat for BERT-TextCNN",
            "model_weight_scope": "Four generic BERT/BERT-large public revisions and nlpaueb/legal-bert-base-uncased are pinned; the exact 'bert-legal-cased' checkpoint is not public and remains blocked.",
            "comparison_boundary": "Results are measured on the project's independently reconstructed EStG-150 with project Gold; they are not Sun's original 150-sentence phrase Gold and not the numbers reported in the paper.",
        },
        "classification_table": classification_rows,
        "classification_table_declared_11_rows": classification_rows + [blocked_classification_row],
        "supplementary_bert_diagnostics": [_classification_row(row) | {"limitation": row["limitation"], "diagnostic_only": True} for row in SUPPLEMENTARY_BERT_ROWS],
        "blocked_methods": [BLOCKED_ROW],
        "semantic_extraction_main_table": semantic_rows,
        "input_target_audit": _input_target_audit(external_root),
        "method_statuses": statuses,
        "safety": {
            "new_llm_api_calls": 0,
            "new_paid_api_calls": 0,
            "new_network_calls_for_model_download": True,
            "network_calls_were_public_model_repositories_only": True,
            "gold_used_for_evaluation_only": True,
            "post_result_tuning": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# SEP-C2 corrected comparison v2 (EStG-150, same evaluator)",
        "",
        f"- status: **{report['status']}**",
        f"- supersedes: `{report['supersedes']}`",
        "- classification table declares 11 rows: 10 evaluated (3 predecessor + 5 BERT-family + 2 project) and 1 explicitly blocked exact checkpoint (`bert-legal-cased`)",
        "- semantic main table: project G0.4 coarse sentence-level view, five span fields only; modality evidence unavailable",
        "",
        "## Classification: per-method summary",
        "",
        "| method | Sun label | n | missing/failed/unlabeled | accuracy | macro P/R/F1 | input field / language | status |",
        "|---|---|---:|---|---:|---|---|---|",
    ]
    for row in report["classification_table_declared_11_rows"]:
        lines.append(
            f"| {row['method_id']} | {row['sun_label']} | {row['n_records']} | "
            f"{row['records_missing']}/{row['records_failed']}/{row['unlabeled_predictions']} | "
            f"{_fmt(row['accuracy'])} | {_fmt(row['macro_precision'])}/{_fmt(row['macro_recall'])}/{_fmt(row['macro_f1'])} | "
            f"`{row.get('input_field', 'N/A')}` / {row.get('input_language', 'N/A')} | {row['status']} |"
        )
    lines += [
        "",
        "### Classification: per-class P/R/F1 and support",
        "",
        "| method | class | precision | recall | F1 | gold support | predicted count |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["classification_table"]:
        for item in row["per_class"]:
            lines.append(
                f"| {row['method_id']} | {item['class']} | {_fmt(item['precision'])} | {_fmt(item['recall'])} | "
                f"{_fmt(item['f1'])} | {row['gold_support'][item['class']]} | {row['predicted_count'][item['class']]} |"
            )
    lines += [
        "",
        "### Classification: implementation / binding summary",
        "",
        "| method | reproduction | training/weights | result file |",
        "|---|---|---|---|",
    ]
    for row in report["classification_table"]:
        lines.append(
            f"| {row['method_id']} | {row['reproduction']} | {row['training_or_weights']} | `{row['result_file']}` |"
        )
    lines += [
        "",
        "## Supplementary BERT adaptations (not part of the 9 baseline completion table)",
        "",
        "| method | diagnostic scope | accuracy | macro P/R/F1 | limitation |",
        "|---|---|---:|---|---|",
    ]
    for row in report.get("supplementary_bert_diagnostics", []):
        lines.append(
            f"| {row['method_id']} | {row['role']} | {_fmt(row['accuracy'])} | "
            f"{_fmt(row['macro_precision'])}/{_fmt(row['macro_recall'])}/{_fmt(row['macro_f1'])} | {row['limitation']} |"
        )
    lines += [
        "",
        "## Semantic extraction main table (coarse sentence-level, five span fields)",
        "",
        "Modality evidence is unavailable in the published decision-only Gold and is therefore not included. "
        "The values below are the project's authorized coarse main view, not a fine-grained five-field re-aggregation.",
        "",
        "| method | ground truth | extracted | precision | recall | F1 | result file |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["semantic_extraction_main_table"]:
        if not row.get("semantic_output"):
            lines.append(f"| {row['method_id']} | N/A | N/A | N/A | N/A | N/A | `{row['result_file']}` |")
        else:
            values = row["main_five_field"]
            lines.append(
                f"| {row['method_id']} | {values['ground_truth']} | {values['extracted']} | "
                f"{_fmt(values['precision'])} | {_fmt(values['recall'])} | {_fmt(values['f1'])} | "
                f"`{row['main_result_file']}` |"
            )
    lines += [
        "",
        "### Semantic extraction main table: per field",
        "",
        "| method | field | ground truth | extracted | precision | recall | F1 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["semantic_extraction_main_table"]:
        if not row.get("semantic_output"):
            continue
        for field, values in row["main_per_field"].items():
            lines.append(
                f"| {row['method_id']} | {field} | {values['ground_truth']} | {values['extracted']} | "
                f"{_fmt(values['precision'])} | {_fmt(values['recall'])} | {_fmt(values['f1'])} |"
            )
    lines += [
        "",
        "## Semantic extraction diagnostic table (fine clause-level, five span fields)",
        "",
        "| method | ground truth | extracted | precision | recall | F1 | result file |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["semantic_extraction_main_table"]:
        if not row.get("semantic_output"):
            lines.append(f"| {row['method_id']} | N/A | N/A | N/A | N/A | N/A | `{row['result_file']}` |")
        else:
            values = row["diagnostic_five_field"]
            lines.append(
                f"| {row['method_id']} | {values['ground_truth']} | {values['extracted']} | "
                f"{_fmt(values['precision'])} | {_fmt(values['recall'])} | {_fmt(values['f1'])} | "
                f"`{row['diagnostic_result_file']}` |"
            )
    lines += [
        "",
        "## Blocked rows",
        "",
    ]
    for row in report["blocked_methods"]:
        lines.append(f"- **{row['method_id']}**: {row['reason']}")
        for path in row.get("attempted_public_paths", []):
            lines.append(f"  - attempted/checked: {path}")
    audit = report["input_target_audit"]
    lines += [
        "",
        "## Input / target audit",
        "",
        f"- target: {audit['classification_target_definition']}",
        f"- Gold first-clause label support: `{audit['gold_first_clause_label_support']}`",
        f"- Gold clause-count distribution: `{audit['gold_clause_count_distribution']}`",
        f"- first clause starts at 0: {audit['gold_first_clause_start_zero']}/150; covers full sentence: {audit['gold_first_clause_covers_full_sentence']}/150",
        f"- language condition: {audit['language_comparability_note']}",
        f"- granularity condition: {audit['granularity_note']}",
        f"- class-prior shift: `{audit['class_prior_shift']}`",
        "",
        "## Error examples for the modality task",
        "",
        "| method | sample_id | gold | predicted |",
        "|---|---|---|---|",
    ]
    for row in report["classification_table"]:
        for example in row.get("error_examples", []):
            lines.append(f"| {row['method_id']} | {example['sample_id']} | {example['gold']} | {example['predicted']} |")
    lines += [
        "",
        "## Safety and reproducibility",
        "",
        "- zero new paid LLM/API calls; Direct-LLM and B0 predictions are reused read-only",
        "- public model downloads only; BERT encoders are pinned in their method configs",
        "- each method has predictions, evaluation, training/weights, config, and checkpoint bindings in its capsule",
        "- `bert-legal-cased` remains blocked because the exact cased EU-legislation checkpoint is not public; no substitute is reported in its place",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-data-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build_report(Path(args.external_data_root))
        report_json = common.json_bytes(report)
        report_md = render_markdown(report).encode("utf-8")
        manifest = {
            "schema_version": "sep_c2_sun_predecessor_comparison_manifest@2.0.0",
            "report_id": report["report_id"],
            "source_bindings": {
                rel: {"sha256": common.sha256_file(FORMAL_ROOT / rel)}
                for rel in (
                    "src/bpc_hybrid/sun_predecessors/evaluation.py",
                    "src/bpc_hybrid/formal_stage2_evaluation.py",
                    "data/input/estg150_formal_inference_input_v2.json",
                    "data/gold/stage2/estg150_formal_gold_v1.json",
                )
            },
            "method_statuses": report["method_statuses"],
            "safety": report["safety"],
        }
        targets = {
            FORMAL_ROOT / f"{REPORT_REL}/sep_c2_sun_predecessors_comparison_v2.json": report_json,
            FORMAL_ROOT / f"{REPORT_REL}/sep_c2_sun_predecessors_comparison_v2.md": report_md,
            FORMAL_ROOT / f"{COMPARISON_V2_REL}/report.json": report_json,
            FORMAL_ROOT / f"{COMPARISON_V2_REL}/manifest.json": common.json_bytes(manifest),
        }
        if args.publish:
            existing = [path for path in targets if path.exists()]
            if existing:
                raise common.SunPredecessorError(
                    "refusing to overwrite: " + ", ".join(str(path.relative_to(FORMAL_ROOT)) for path in existing)
                )
            for path, payload in targets.items():
                common.write_bytes_atomic(path, payload)
            print("SEP-C2 predecessor comparison v2 PUBLISHED")
        else:
            mismatches = [str(path.relative_to(FORMAL_ROOT)) for path, payload in targets.items() if not path.is_file() or path.read_bytes() != payload]
            if mismatches:
                raise common.SunPredecessorError("replay differs for: " + ", ".join(mismatches))
            print("SEP-C2 predecessor comparison v2 REPLAY VERIFIED")
        print(f"classification methods evaluated={len(report['classification_table'])} blocked={len(report['blocked_methods'])}")
        for row in report["classification_table"]:
            print(f"{row['method_id']}: acc={_fmt(row['accuracy'])} macro_f1={_fmt(row['macro_f1'])}")
        return 0
    except (OSError, ValueError, common.SunPredecessorError) as exc:
        print(f"SEP-C2 comparison v2 refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Reuse the existing S2.4 BERT-TextCNN checkpoint as a diagnostic BERT row.

The checkpoint is the project's already-trained Legal-BERT + TextCNN modality
classifier (the component used by the B0 formal arm).  It is a full
fine-tuned model, but its original training split contains a small number of
EStG-150 overlap rows.  It is therefore reported as a diagnostic sensitivity
row, separately from the clean frozen-encoder probe.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import torch

from bpc_hybrid.sun_predecessors import common, dataset, evaluation, neural
from bpc_hybrid.sun_predecessors.runner import (
    REPORTS_ROOT_REL,
    _artifact_path_prefix,
    _report_basename,
    _source_binding,
)

LOCAL_RUN_REL = "outputs/development/sep_c2_sun_predecessors_v1"


def _predict_in_batches(classifier: Any, texts: Sequence[str], *, batch_size: int = 16) -> list[Any]:
    predictions: list[Any] = []
    for start in range(0, len(texts), batch_size):
        predictions.extend(classifier.predict(list(texts[start:start + batch_size])))
    return predictions


def build_bert_existing(formal_root: Path, external_root: Path) -> dict[str, Any]:
    formal_root = Path(formal_root)
    external_root = Path(external_root)
    method_id = "bert_legal_uncased_textcnn_existing"
    spec = common.method_spec(method_id)
    records = evaluation.load_formal_input(formal_root)
    splits = dataset.build_clean_splits(formal_root, external_root)
    s26_path = external_root / "configs/models/sun_b0_s26_candidate_B_v1.json"
    s26_config = common.load_json(s26_path)
    try:
        from bpc_hybrid.sun_style.sun_b0 import LockedBertTextCNNInference
    except ImportError as exc:
        raise common.SunPredecessorError("existing S2.4 loader is unavailable") from exc
    try:
        classifier = LockedBertTextCNNInference.load(external_root, s26_config, device="cpu")
    except Exception as exc:
        raise common.SunPredecessorError("existing S2.4 BERT-TextCNN checkpoint cannot be loaded") from exc
    formal_texts = [str(row[spec.input_field]) for row in records]
    formal_predictions = _predict_in_batches(classifier, formal_texts)
    predicted_labels = [prediction.label for prediction in formal_predictions]
    attempts = [
        evaluation.make_attempt(
            sample_id=row["sample_id"],
            source_text=row[spec.input_field],
            label=label,
            method_id=spec.method_id,
            evidence_text=row[spec.input_field],
        )
        for row, label in zip(records, predicted_labels, strict=True)
    ]
    evaluated = evaluation.evaluate_attempts(formal_root, attempts)
    official_test_texts = [str(row["text"]) for row in splits["official_test"]]
    official_test_predictions = _predict_in_batches(classifier, official_test_texts)
    official_test_labels = [neural.LABEL_TO_INDEX[str(row["label"])] for row in splits["official_test"]]
    official_test_indices = [
        neural.LABEL_TO_INDEX[prediction.label] for prediction in official_test_predictions
    ]
    official_test_metrics = neural.classification_metrics(
        official_test_labels, official_test_indices
    )
    # Contamination flag: count all original official train rows that the clean
    # splitter excludes for overlapping the EStG-150 raw/translation probes.
    original_train_path = (
        external_root
        / "data/development/modality/sun_estg_modality_v1/splits/train.jsonl"
    )
    original_train_rows = [
        __import__("json").loads(line)
        for line in original_train_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    probes = dataset._test_probes(formal_root)  # read-only overlap detector used for the clean split
    flagged = sum(1 for row in original_train_rows if dataset._overlaps_estg150(str(row["text"]), probes))
    exact_norm = sum(
        1
        for row in original_train_rows
        if common.normalize_for_match(str(row["text"]))
        in {value for value, _ in probes}
    )
    checkpoint_binding = s26_config["classifier"]["checkpoint"]
    classifier_config_binding = s26_config["classifier"]["config"]
    run_manifest_binding = s26_config["classifier"]["run_manifest"]
    model_card = {
        "schema_version": "sep_c2_sun_predecessor_existing_bert_model_card@1.0.0",
        "method_id": method_id,
        "model_family": "Legal-BERT base uncased + TextCNN head (existing project S2.4 reconstruction)",
        "architecture_scope": "full fine-tuned BERT encoder plus TextCNN head",
        "checkpoint": {
            "path": str(checkpoint_binding["path"]),
            "sha256": str(checkpoint_binding["sha256"]),
            "byte_size": int(checkpoint_binding["bytes"]),
            "versioned_in_main_workspace": False,
        },
        "classifier_config": {
            "path": str(classifier_config_binding["path"]),
            "sha256": str(classifier_config_binding["sha256"]),
        },
        "run_manifest": {
            "path": str(run_manifest_binding["path"]),
            "sha256": str(run_manifest_binding["sha256"]),
        },
        "input_language": str(s26_config["classifier"].get("inference_language", "de")),
        "original_training_rows": len(original_train_rows),
        "estg150_overlap_rows_flagged_by_clean_splitter": flagged,
        "estg150_exact_normalized_overlap_rows": exact_norm,
        "contamination_note": (
            "This checkpoint was trained before this SEP-C2 run on the official split without "
            f"the EStG-150 overlap exclusion; {flagged} flagged train rows (including {exact_norm} exact "
            "normalized matches) may have been seen during training. Therefore this row is diagnostic, "
            "not the primary clean BERT comparison."
        ),
    }
    diagnostics = {
        "schema_version": "sep_c2_sun_predecessor_bert_diagnostics@1.0.0",
        "method_id": method_id,
        "predicted_label_counts": dict(sorted(Counter(predicted_labels).items())),
        "official_clean_test_metrics": official_test_metrics,
        "model_card": model_card,
        "dataset_audit": splits["audit"],
    }
    manifest = {
        "schema_version": "sep_c2_sun_predecessor_method_manifest@1.0.0",
        "method_id": spec.method_id,
        "claim_scope": "development_zero_api_predecessor_method_comparison",
        "sun_source_and_role": spec.sun_role,
        "reproduction_class": spec.reproduction_class,
        "version_caveat": (
            "Built against the locally available earlier author manuscript; the final Springer version "
            "could not be checked. This row reuses an existing project checkpoint and is flagged for "
            "small EStG-150 training overlap; it is a diagnostic, not a clean trained-from-scratch run."
        ),
        "formal_input_binding": _source_binding(formal_root, evaluation.FORMAL_INPUT_REL),
        "formal_gold_binding_read_only_for_evaluation": _source_binding(
            formal_root, evaluation.FORMAL_GOLD_REL
        ),
        "evaluator_binding": _source_binding(
            formal_root, "src/bpc_hybrid/formal_stage2_evaluation.py"
        ),
        "external_checkpoint_or_config_bindings": {
            "s26_config": {
                "path": str(s26_path.relative_to(external_root)),
                "sha256": common.sha256_file(s26_path),
            },
            "classifier": model_card,
        },
        "dataset_audit": splits["audit"],
        "implementation_bindings": {
            rel: _source_binding(formal_root, rel)
            for rel in (
                "src/bpc_hybrid/sun_predecessors/common.py",
                "src/bpc_hybrid/sun_predecessors/dataset.py",
                "src/bpc_hybrid/sun_predecessors/evaluation.py",
                "src/bpc_hybrid/sun_predecessors/neural.py",
                "src/bpc_hybrid/sun_predecessors/runner_bert_existing.py",
                "scripts/run_sep_c2_sun_predecessor_bert_existing_v1.py",
            )
        },
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "gold_read_by_prediction_code": False,
            "gold_used_for_evaluation": True,
            "estg150_used_for_training_or_selection": "pre-existing checkpoint may contain overlap; flagged",
            "post_result_tuning": False,
        },
    }
    config_snapshot = {
        "schema_version": "sep_c2_sun_predecessor_config@1.0.0",
        "method": {
            "method_id": spec.method_id,
            "sun_role": spec.sun_role,
            "reproduction_class": spec.reproduction_class,
            "input_field": spec.input_field,
            "input_language": spec.input_language,
            "training_data": spec.training_data,
            "notes": spec.notes,
        },
        "model_card": model_card,
    }
    prediction_document = {
        "schema_version": "sep_c2_sun_predecessor_predictions@1.0.0",
        "method_id": spec.method_id,
        "records": attempts,
    }
    evaluation_document = {
        "schema_version": "sep_c2_sun_predecessor_evaluation_file@1.0.0",
        "method_id": spec.method_id,
        "evaluation": evaluated,
    }
    artifacts = {
        f"{_artifact_path_prefix(spec.method_id)}/predictions.json": prediction_document,
        f"{_artifact_path_prefix(spec.method_id)}/evaluation.json": evaluation_document,
        f"{_artifact_path_prefix(spec.method_id)}/diagnostics.json": diagnostics,
        f"{_artifact_path_prefix(spec.method_id)}/model_card.json": model_card,
        f"{_artifact_path_prefix(spec.method_id)}/config_snapshot.json": config_snapshot,
        f"{_artifact_path_prefix(spec.method_id)}/manifest.json": manifest,
    }
    report = {
        "schema_version": "sep_c2_sun_predecessor_report@1.0.0",
        "report_id": _report_basename(spec.method_id),
        "status": "completed_zero_api_predecessor_method_run",
        "method": config_snapshot["method"],
        "version_caveat": manifest["version_caveat"],
        "execution": {
            "formal_input": evaluation.FORMAL_INPUT_REL,
            "formal_input_sha256": manifest["formal_input_binding"]["sha256"],
            "input_field": spec.input_field,
            "input_language": spec.input_language,
            "records": len(records),
        },
        "training": {
            "required": False,
            "training_data": spec.training_data,
            "model_selection": "existing checkpoint; no new training or selection",
            "model_card": model_card,
        },
        "official_clean_test": official_test_metrics,
        "prediction": {
            "artifact_dir": _artifact_path_prefix(spec.method_id),
            "predicted_count": diagnostics["predicted_label_counts"],
        },
        "evaluation": evaluated,
        "safety": manifest["safety"],
    }
    return {
        "artifacts": artifacts,
        "report": report,
        "report_rel": f"{REPORTS_ROOT_REL}/{_report_basename(spec.method_id)}.json",
        "report_md_rel": f"{REPORTS_ROOT_REL}/{_report_basename(spec.method_id)}.md",
    }


def render_existing_markdown(report: Mapping[str, Any]) -> str:
    method = report["method"]
    evaluated = report["evaluation"]
    official = evaluated["official_evaluator"]
    model_card = report["training"]["model_card"]
    lines = [
        f"# SEP-C2 Sun-predecessor run: {method['method_id']}",
        "",
        f"- status: **{report['status']}**",
        f"- Sun role: {method['sun_role']}",
        f"- reproduction class: {method['reproduction_class']}",
        f"- input field/language: `{report['execution']['input_field']}` / `{report['execution']['input_language']}`",
        f"- records scored: {evaluated['records_scored']} / {evaluated['records_expected']}",
        f"- missing / failed / unlabeled: {evaluated['records_missing']} / {evaluated['records_failed']} / {evaluated['unlabeled_predictions']}",
        f"- accuracy: {official['accuracy']:.4f}",
        f"- macro-F1: {official['macro_f1']:.4f}",
        "",
        "| class | precision | recall | F1 | gold support | predicted count |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    support = evaluated["gold_support"]
    predicted = evaluated["predicted_count"]
    for row in official["per_class"]:
        lines.append(
            f"| {row['class']} | {row['precision']:.4f} | {row['recall']:.4f} | "
            f"{row['f1']:.4f} | {support[row['class']]} | {predicted[row['class']]} |"
        )
    lines += [
        "",
        f"- model: {model_card['model_family']}",
        f"- checkpoint: `{model_card['checkpoint']['path']}`",
        f"- EStG-150 overlap flagged in original train: {model_card['estg150_overlap_rows_flagged_by_clean_splitter']} "
        f"rows ({model_card['estg150_exact_normalized_overlap_rows']} exact normalized)",
        f"- official clean test diagnostic: accuracy {report['official_clean_test']['accuracy']:.4f}, "
        f"macro-F1 {report['official_clean_test']['macro_f1']:.4f}, "
        f"n={report['official_clean_test']['n']}",
        "",
        f"- version caveat: {report['version_caveat']}",
        f"- new LLM/API calls: {report['safety']['new_llm_api_calls']}",
        "",
    ]
    return "\n".join(lines)
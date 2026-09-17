# -*- coding: utf-8 -*-
"""SEP-C2 BERT-TextCNN predecessor runner.

The implementation covers six pre-trained encoder rows sourced from the local
Sun et al. (2024) author manuscript Table 6.  The head follows the
project-record final-version architecture (Section 4.2.1 / Fig. 3; not
re-fetched/re-verified 2026-09-17): per-layer [CLS] sequence -> TextCNN -> max pooling -> four-class linear output.  The encoder
and head are fine-tuned together on the clean official EStG modality train
split; the official dev split selects the epoch.  EStG-150 Gold is read only
after predictions have been materialised for evaluation.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import torch

from bpc_hybrid.sun_predecessors import bert_full, common, dataset, evaluation, neural
from bpc_hybrid.sun_predecessors.runner import (
    EVIDENCE_ROOT_REL,
    REPORTS_ROOT_REL,
    _artifact_path_prefix,
    _report_basename,
    _source_binding,
)

LOCAL_RUN_REL = "outputs/development/sep_c2_sun_predecessors_v1"
CONFIG_DIR_REL = "configs/sep_c2_sun_predecessors_v1/bert_full_v1"
ARCHITECTURE_EVIDENCE = (
    "Sun et al. (2024), final article, Section 4.2.1 / Fig. 3: 'For each encoding layer, "
    "the vector of its first token (i.e., [CLS]) is extracted, and these vectors are "
    "concatenated together as the input of the TextCNN layer.' The figure labels CLS1..CLS12 "
    "and a TextCNN with kernel widths 3/4/5 and 256 filters per width."
)


def _config_rel(method_id: str) -> str:
    return f"{CONFIG_DIR_REL}/{method_id}_v1.json"


def _checkpoint_rel(method_id: str) -> str:
    return f"{LOCAL_RUN_REL}/{method_id}/best_model.pt"


def _model_file_hashes(model_dir: Path) -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for name in ("config.json", "pytorch_model.bin", "model.safetensors", "vocab.txt", "tokenizer.json", "tokenizer_config.json"):
        path = Path(model_dir) / name
        if path.is_file():
            rows[name] = {"sha256": common.sha256_file(path), "byte_size": path.stat().st_size}
    if not rows:
        raise common.SunPredecessorError(f"model directory has no recognised files: {model_dir}")
    return rows


def build_bert_full(
    formal_root: Path,
    external_root: Path,
    method_id: str,
    model_root: Path,
) -> dict[str, Any]:
    formal_root = Path(formal_root)
    external_root = Path(external_root)
    model_root = Path(model_root)
    config_rel = _config_rel(method_id)
    config_path = formal_root / config_rel
    config = common.load_json(config_path)
    if config.get("method_id") != method_id:
        raise common.SunPredecessorError("BERT-full config method_id mismatch")
    spec = common.method_spec(method_id)
    records = evaluation.load_formal_input(formal_root)
    splits = dataset.build_clean_splits(formal_root, external_root)
    model_config = config["model"]
    model_dir = model_root / str(model_config["local_dir"])
    encoder, tokenizer, encoder_metadata = bert_full.load_encoder_and_tokenizer(
        model_dir,
        expected_hidden_size=int(model_config["hidden_size"]),
        expected_num_hidden_layers=int(model_config["num_hidden_layers"]),
    )
    architecture = config["architecture"]
    optimization = config["optimization"]
    model = bert_full.BertLayerTextCNN(
        encoder,
        hidden_size=int(encoder_metadata["hidden_size"]),
        num_hidden_layers=int(encoder_metadata["num_hidden_layers"]),
        kernel_sizes=tuple(architecture["kernel_sizes"]),
        filters_per_kernel=int(architecture["filters_per_kernel"]),
        dropout=float(architecture["dropout"]),
        num_labels=4,
        encoder_trainable=bool(optimization.get("encoder_trainable", True)),
    )
    device = bert_full.resolve_device(str(optimization.get("device", "auto")))
    model.to(device)
    max_length = int(architecture["max_length"])
    train_examples = bert_full.tokenize_examples(
        tokenizer,
        splits["train"],
        text_field="text",
        max_length=max_length,
        label_field="label",
    )
    dev_examples = bert_full.tokenize_examples(
        tokenizer,
        splits["dev"],
        text_field="text",
        max_length=max_length,
        label_field="label",
    )
    official_test_examples = bert_full.tokenize_examples(
        tokenizer,
        splits["official_test"],
        text_field="text",
        max_length=max_length,
        label_field="label",
    )
    formal_examples = bert_full.tokenize_examples(
        tokenizer,
        records,
        text_field=spec.input_field,
        max_length=max_length,
        label_field=None,
    )
    training = bert_full.train_model(
        model=model,
        train_examples=train_examples,
        dev_examples=dev_examples,
        optimization=optimization,
        device=device,
    )
    batch_size = int(optimization["batch_size"])
    official_test_predictions = bert_full.predict_indices(
        model, official_test_examples, batch_size=batch_size, device=device
    )
    official_test_metrics = neural.classification_metrics(
        [neural.LABEL_TO_INDEX[row["label"]] for row in splits["official_test"]],
        official_test_predictions,
    )
    formal_predictions = bert_full.predict_indices(
        model, formal_examples, batch_size=batch_size, device=device
    )
    predicted_labels = [neural.MODEL_LABELS[index] for index in formal_predictions]
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
    length_stats = {
        "official_train": bert_full.sequence_length_stats(
            tokenizer, splits["train"], text_field="text", max_length=max_length
        ),
        "official_dev": bert_full.sequence_length_stats(
            tokenizer, splits["dev"], text_field="text", max_length=max_length
        ),
        "estg150_formal_input": bert_full.sequence_length_stats(
            tokenizer, records, text_field=spec.input_field, max_length=max_length
        ),
    }
    checkpoint_rel = _checkpoint_rel(method_id)
    checkpoint = bert_full.save_checkpoint(
        formal_root / checkpoint_rel,
        model,
        metadata={
            "method_id": method_id,
            "config_sha256": common.sha256_file(config_path),
            "encoder_metadata": encoder_metadata,
            "best_epoch": training["best_epoch"],
            "labels": list(neural.MODEL_LABELS),
            "architecture_evidence": ARCHITECTURE_EVIDENCE,
        },
    )
    checkpoint["path"] = checkpoint_rel
    diagnostics = {
        "schema_version": "sep_c2_sun_predecessor_bert_full_diagnostics@1.0.0",
        "method_id": method_id,
        "predicted_label_counts": dict(sorted(Counter(predicted_labels).items())),
        "training_best_dev": training["best_dev"],
        "training_history": training["history"],
        "official_clean_test_metrics": official_test_metrics,
        "sequence_length_stats": length_stats,
        "encoder": encoder_metadata,
        "architecture_evidence": ARCHITECTURE_EVIDENCE,
    }
    training_document = {
        "schema_version": "sep_c2_sun_predecessor_training@1.0.0",
        "method_id": method_id,
        "config_path": config_rel,
        "config": config,
        "dataset_audit": splits["audit"],
        "encoder": encoder_metadata,
        "model_file_hashes": _model_file_hashes(model_dir),
        "sequence_length_stats": length_stats,
        "best_dev": training["best_dev"],
        "history": training["history"],
        "official_clean_test_metrics": official_test_metrics,
        "checkpoint": checkpoint,
        "architecture_evidence": ARCHITECTURE_EVIDENCE,
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
        "config_path": config_rel,
        "config_sha256": common.sha256_file(config_path),
        "frozen_model": model_config,
        "frozen_architecture": architecture,
        "frozen_optimization": optimization,
    }
    manifest = {
        "schema_version": "sep_c2_sun_predecessor_method_manifest@1.0.0",
        "method_id": spec.method_id,
        "claim_scope": "development_zero_api_predecessor_method_comparison",
        "sun_source_and_role": spec.sun_role,
        "reproduction_class": spec.reproduction_class,
        "version_caveat": (
            "Architecture and training mode follow the final article Section 4.2.1 / Fig. 3 "
            "(per-layer [CLS] sequence -> TextCNN -> global max -> 4-class output). The public "
            "encoder revision is pinned in the config; unpublished hyperparameters are stated "
            "in the config and treated as reconstruction parameters."
        ),
        "architecture_evidence": ARCHITECTURE_EVIDENCE,
        "formal_input_binding": _source_binding(formal_root, evaluation.FORMAL_INPUT_REL),
        "formal_gold_binding_read_only_for_evaluation": _source_binding(
            formal_root, evaluation.FORMAL_GOLD_REL
        ),
        "evaluator_binding": _source_binding(
            formal_root, "src/bpc_hybrid/formal_stage2_evaluation.py"
        ),
        "config_binding": _source_binding(formal_root, config_rel),
        "checkpoint_binding": checkpoint,
        "dataset_audit": splits["audit"],
        "encoder": encoder_metadata,
        "model_file_hashes": _model_file_hashes(model_dir),
        "implementation_bindings": {
            rel: _source_binding(formal_root, rel)
            for rel in (
                "src/bpc_hybrid/sun_predecessors/common.py",
                "src/bpc_hybrid/sun_predecessors/dataset.py",
                "src/bpc_hybrid/sun_predecessors/evaluation.py",
                "src/bpc_hybrid/sun_predecessors/neural.py",
                "src/bpc_hybrid/sun_predecessors/bert_full.py",
                "src/bpc_hybrid/sun_predecessors/runner_bert_full.py",
                "scripts/run_sep_c2_sun_predecessor_bert_full_v1.py",
            )
        },
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
            "local_files_only": True,
            "gold_read_by_prediction_code": False,
            "gold_used_for_evaluation": True,
            "estg150_used_for_training_or_selection": False,
            "post_result_tuning": False,
        },
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
        f"{_artifact_path_prefix(spec.method_id)}/training.json": training_document,
        f"{_artifact_path_prefix(spec.method_id)}/config_snapshot.json": config_snapshot,
        f"{_artifact_path_prefix(spec.method_id)}/manifest.json": manifest,
    }
    report = {
        "schema_version": "sep_c2_sun_predecessor_report@1.0.0",
        "report_id": _report_basename(spec.method_id),
        "status": "completed_zero_api_predecessor_method_run",
        "method": config_snapshot["method"],
        "version_caveat": manifest["version_caveat"],
        "architecture_evidence": ARCHITECTURE_EVIDENCE,
        "execution": {
            "formal_input": evaluation.FORMAL_INPUT_REL,
            "formal_input_sha256": manifest["formal_input_binding"]["sha256"],
            "input_field": spec.input_field,
            "input_language": spec.input_language,
            "records": len(records),
        },
        "training": {
            "required": True,
            "training_data": spec.training_data,
            "clean_train_rows": len(train_examples),
            "clean_dev_rows": len(dev_examples),
            "best_epoch": training["best_epoch"],
            "best_dev": training["best_dev"],
            "checkpoint": checkpoint,
            "encoder": encoder_metadata,
            "model_file_hashes": _model_file_hashes(model_dir),
            "sequence_length_stats": length_stats,
            "device": training["device"],
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


def render_bert_full_markdown(report: Mapping[str, Any]) -> str:
    method = report["method"]
    evaluated = report["evaluation"]
    official = evaluated["official_evaluator"]
    training = report["training"]
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
        f"- encoder: {training['encoder']['model_type']} hidden={training['encoder']['hidden_size']} layers={training['encoder']['num_hidden_layers']}",
        f"- training rows: {training['clean_train_rows']} train / {training['clean_dev_rows']} dev",
        f"- best dev macro-F1: {training['best_dev']['macro_f1']:.4f} (epoch {training['best_epoch']})",
        f"- device: {training['device']}",
        f"- official clean test diagnostic: accuracy {report['official_clean_test']['accuracy']:.4f}, "
        f"macro-F1 {report['official_clean_test']['macro_f1']:.4f}, "
        f"n={report['official_clean_test']['n']}",
        "",
        f"- architecture evidence: {report['architecture_evidence']}",
        f"- new LLM/API calls: {report['safety']['new_llm_api_calls']}",
        "",
    ]
    return "\n".join(lines)

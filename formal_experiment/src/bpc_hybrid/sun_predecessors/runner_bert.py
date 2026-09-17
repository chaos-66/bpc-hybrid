# -*- coding: utf-8 -*-
"""SEP-C2 BERT probe builder for the closest available legal-BERT encoder."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import torch
import numpy as np

from bpc_hybrid.sun_predecessors import bert_probe, common, dataset, evaluation, neural
from bpc_hybrid.sun_predecessors.runner import (
    EVIDENCE_ROOT_REL,
    REPORTS_ROOT_REL,
    _artifact_path_prefix,
    _report_basename,
    _source_binding,
)

LOCAL_RUN_REL = "outputs/development/sep_c2_sun_predecessors_v1"


def _sanitized_cache_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != "vocab"}


def _load_feature_cache(
    formal_root: Path,
    split: str,
    expected_sample_ids: Sequence[str],
    *,
    encoder_revision: str,
    max_length: int,
) -> dict[str, Any]:
    """Load frozen-encoder chunk features and fail closed on any order drift."""
    cache_dir = Path(formal_root) / LOCAL_RUN_REL / "bert_features_v1"
    metadata_paths = sorted(cache_dir.glob(f"{split}_*.json"))
    if not metadata_paths:
        raise common.SunPredecessorError(
            f"missing frozen-encoder feature cache for {split}; run "
            "scripts/build_sep_c2_sun_predecessor_bert_features_v1.py for each chunk first"
        )
    feature_blocks: list[Any] = []
    sample_ids: list[str] = []
    chunk_metadata: list[dict[str, Any]] = []
    for metadata_path in metadata_paths:
        metadata = common.load_json(metadata_path)
        npz_path = metadata_path.with_suffix(".npz")
        if not npz_path.is_file():
            raise common.SunPredecessorError(f"feature chunk missing: {npz_path.name}")
        if metadata.get("encoder_revision") != encoder_revision:
            raise common.SunPredecessorError("feature cache encoder revision mismatch")
        if int(metadata.get("max_length", -1)) != max_length:
            raise common.SunPredecessorError("feature cache max_length mismatch")
        arrays = np.load(npz_path, allow_pickle=False)
        features = np.asarray(arrays["features"], dtype=np.float32)
        if features.shape[0] != int(metadata.get("rows", -1)):
            raise common.SunPredecessorError("feature cache row-count mismatch")
        feature_blocks.append(torch.from_numpy(features))
        sample_ids.extend(str(value) for value in metadata.get("sample_ids", []))
        chunk_metadata.append(
            {
                "path": metadata_path.name,
                "sha256": common.sha256_file(metadata_path),
                "text_sha256": metadata.get("text_sha256"),
                "features_sha256": metadata.get("features_sha256"),
                "rows": metadata.get("rows"),
                "start": metadata.get("start"),
                "end": metadata.get("end"),
            }
        )
    if sample_ids != list(expected_sample_ids):
        raise common.SunPredecessorError(f"feature cache sample order mismatch for {split}")
    return {
        "features": torch.cat(feature_blocks, dim=0).float(),
        "chunks": chunk_metadata,
    }

def build_bert_probe(formal_root: Path, external_root: Path) -> dict[str, Any]:
    formal_root = Path(formal_root)
    external_root = Path(external_root)
    method_id = "bert_legal_uncased_probe"
    config_rel = f"configs/sep_c2_sun_predecessors_v1/{method_id}_v1.json"
    config_path = formal_root / config_rel
    config = common.load_json(config_path)
    if config.get("method_id") != method_id:
        raise common.SunPredecessorError("BERT probe config method_id mismatch")
    spec = common.method_spec(method_id)
    records = evaluation.load_formal_input(formal_root)
    splits = dataset.build_clean_splits(formal_root, external_root)
    bundle = bert_probe.load_local_legal_bert(formal_root)
    max_length = int(config["optimization"]["max_length"])
    feature_batch_size = int(config["optimization"]["feature_extraction_batch_size"])
    train_texts = [str(row["text"]) for row in splits["train"]]
    dev_texts = [str(row["text"]) for row in splits["dev"]]
    test_texts = [str(row["text"]) for row in splits["official_test"]]
    formal_texts = [str(row[spec.input_field]) for row in records]
    feature_cache = _load_feature_cache(
        formal_root,
        "train",
        [str(row["sample_id"]) for row in splits["train"]],
        encoder_revision=bundle.metadata["revision"],
        max_length=max_length,
    )
    train_features = feature_cache["features"]
    feature_cache_dev = _load_feature_cache(
        formal_root,
        "dev",
        [str(row["sample_id"]) for row in splits["dev"]],
        encoder_revision=bundle.metadata["revision"],
        max_length=max_length,
    )
    dev_features = feature_cache_dev["features"]
    feature_cache_test = _load_feature_cache(
        formal_root,
        "official_test",
        [str(row["sample_id"]) for row in splits["official_test"]],
        encoder_revision=bundle.metadata["revision"],
        max_length=max_length,
    )
    test_features = feature_cache_test["features"]
    formal_feature_cache = bert_probe.extract_features(
        bundle, formal_texts, max_length=max_length, batch_size=feature_batch_size
    )
    formal_features = formal_feature_cache
    train_labels = [neural.LABEL_TO_INDEX[str(row["label"])] for row in splits["train"]]
    dev_labels = [neural.LABEL_TO_INDEX[str(row["label"])] for row in splits["dev"]]
    test_labels = [neural.LABEL_TO_INDEX[str(row["label"])] for row in splits["official_test"]]
    head, training = bert_probe.train_linear_probe(
        train_features=train_features,
        train_labels=train_labels,
        dev_features=dev_features,
        dev_labels=dev_labels,
        hyperparameters=config["optimization"],
        head_config=config["head"],
    )
    test_predictions = bert_probe.predict_with_head(head, test_features)
    test_metrics = neural.classification_metrics(test_labels, test_predictions)
    formal_predictions = bert_probe.predict_with_head(head, formal_features)
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
        "estg150_formal_input_raw_text_de": bert_probe.sequence_length_stats(
            bundle, formal_texts, max_length=max_length
        ),
        "official_clean_test": bert_probe.sequence_length_stats(
            bundle, test_texts, max_length=max_length
        ),
    }
    checkpoint_rel = f"{LOCAL_RUN_REL}/{method_id}/best_head.pt"
    checkpoint = neural.save_checkpoint(
        formal_root / checkpoint_rel,
        head,
        metadata={
            "method_id": method_id,
            "config_sha256": common.sha256_file(config_path),
            "encoder_revision": bundle.metadata["revision"],
            "feature_pooling": config["encoder"]["feature_pooling"],
            "best_epoch": training["best_epoch"],
            "labels": list(neural.MODEL_LABELS),
        },
    )
    checkpoint["path"] = checkpoint_rel
    diagnostics = {
        "schema_version": "sep_c2_sun_predecessor_bert_diagnostics@1.0.0",
        "method_id": method_id,
        "predicted_label_counts": dict(sorted(Counter(predicted_labels).items())),
        "training_best_dev": training["best_dev"],
        "training_history": training["history"],
        "official_clean_test_metrics": test_metrics,
        "sequence_length_stats": length_stats,
        "encoder": bundle.metadata,
    }
    training_document = {
        "schema_version": "sep_c2_sun_predecessor_training@1.0.0",
        "method_id": method_id,
        "config_path": config_rel,
        "config": config,
        "dataset_audit": splits["audit"],
        "encoder": bundle.metadata,
        "sequence_length_stats": length_stats,
        "best_dev": training["best_dev"],
        "history": training["history"],
        "official_clean_test_metrics": test_metrics,
        "checkpoint": checkpoint,
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
        "frozen_hyperparameters": config["optimization"],
        "encoder": config["encoder"],
        "head": config["head"],
    }
    manifest = {
        "schema_version": "sep_c2_sun_predecessor_method_manifest@1.0.0",
        "method_id": spec.method_id,
        "claim_scope": "development_zero_api_predecessor_method_comparison",
        "sun_source_and_role": spec.sun_role,
        "reproduction_class": spec.reproduction_class,
        "version_caveat": (
            "Built against the locally available earlier author manuscript; the final Springer version "
            "could not be checked in this offline environment. The encoder is a public EU-legislation "
            "legal-BERT base uncased model, not Sun's unpublished checkpoint."
        ),
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
        "encoder": bundle.metadata,
        "sequence_length_stats": length_stats,
        "implementation_bindings": {
            rel: _source_binding(formal_root, rel)
            for rel in (
                "src/bpc_hybrid/sun_predecessors/common.py",
                "src/bpc_hybrid/sun_predecessors/dataset.py",
                "src/bpc_hybrid/sun_predecessors/evaluation.py",
                "src/bpc_hybrid/sun_predecessors/neural.py",
                "src/bpc_hybrid/sun_predecessors/bert_probe.py",
                "src/bpc_hybrid/sun_predecessors/runner_bert.py",
                "scripts/run_sep_c2_sun_predecessor_bert_v1.py",
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
            "clean_train_rows": len(train_texts),
            "clean_dev_rows": len(dev_texts),
            "best_epoch": training["best_epoch"],
            "best_dev": training["best_dev"],
            "checkpoint": checkpoint,
            "encoder": bundle.metadata,
            "sequence_length_stats": length_stats,
        },
        "official_clean_test": test_metrics,
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


def render_bert_markdown(report: Mapping[str, Any]) -> str:
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
        f"- encoder: {training['encoder']['repository_id']} @ {training['encoder']['revision']} (frozen)",
        f"- training rows: {training['clean_train_rows']} train / {training['clean_dev_rows']} dev",
        f"- best dev macro-F1: {training['best_dev']['macro_f1']:.4f} (epoch {training['best_epoch']})",
        f"- official clean test diagnostic: accuracy {report['official_clean_test']['accuracy']:.4f}, "
        f"macro-F1 {report['official_clean_test']['macro_f1']:.4f}, "
        f"n={report['official_clean_test']['n']}",
        "",
        f"- version caveat: {report['version_caveat']}",
        f"- new LLM/API calls: {report['safety']['new_llm_api_calls']}",
        "",
    ]
    return "\n".join(lines)
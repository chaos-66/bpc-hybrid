# -*- coding: utf-8 -*-
"""SEP-C2 neural predecessor builders (CF_RNN / CF_CNN).

Kept separate from the CF_KW runner so that the already-committed CF_KW
manifest remains bound to its original source files.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import torch

from bpc_hybrid.sun_predecessors import common, dataset, evaluation, neural
from bpc_hybrid.sun_predecessors.runner import (
    EVIDENCE_ROOT_REL,
    REPORTS_ROOT_REL,
    _artifact_path_prefix,
    _report_basename,
    _source_binding,
)

LOCAL_RUN_REL = "outputs/development/sep_c2_sun_predecessors_v1"
NEURAL_CACHE_REL = f"{LOCAL_RUN_REL}/embedding_cache"


def _sanitized_cache_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in metadata.items() if key != "vocab"}


def _sanitized_dataset_audit(audit: Mapping[str, Any]) -> dict[str, Any]:
    return dict(audit)


def _model_checkpoint_rel(method_id: str) -> str:
    return f"{LOCAL_RUN_REL}/{method_id}/best_model.pt"


def build_neural(formal_root: Path, external_root: Path, method_id: str) -> dict[str, Any]:
    formal_root = Path(formal_root)
    external_root = Path(external_root)
    config_rel = f"configs/sep_c2_sun_predecessors_v1/{method_id}_v1.json"
    config_path = formal_root / config_rel
    config = common.load_json(config_path)
    if config.get("method_id") != method_id:
        raise common.SunPredecessorError("neural config method_id mismatch")
    spec = common.method_spec(method_id)
    records = evaluation.load_formal_input(formal_root)
    splits = dataset.build_clean_splits(formal_root, external_root)
    embedding = dataset.build_embedding_cache(
        formal_root,
        external_root,
        formal_root / NEURAL_CACHE_REL,
    )
    vocab = [str(value) for value in embedding["vocab"]]
    token_to_id = {token: index for index, token in enumerate(vocab)}
    max_length = int(config["optimization"]["max_length"])
    train_records = neural.encode_records(
        splits["train"], token_to_id, max_length=max_length, text_field="text", label_field="label"
    )
    dev_records = neural.encode_records(
        splits["dev"], token_to_id, max_length=max_length, text_field="text", label_field="label"
    )
    hyperparameters = dict(config["architecture"])
    hyperparameters.update(config["optimization"])
    model, training = neural.train_model(
        kind=method_id,
        train_records=train_records,
        dev_records=dev_records,
        embedding_matrix=embedding["matrix"],
        hyperparameters=hyperparameters,
    )
    batch_size = int(config["optimization"]["batch_size"])
    device = torch.device("cpu")
    official_test_records = neural.encode_records(
        splits["official_test"],
        token_to_id,
        max_length=max_length,
        text_field="text",
        label_field="label",
    )
    official_test_predictions = neural.predict_indices(
        model, official_test_records, batch_size=batch_size, device=device
    )
    official_test_metrics = neural.classification_metrics(
        [neural.LABEL_TO_INDEX[row["label"]] for row in splits["official_test"]],
        official_test_predictions,
    )
    formal_encoded = neural.encode_records(
        records,
        token_to_id,
        max_length=max_length,
        text_field=spec.input_field,
        label_field=None,
    )
    predicted_indices = neural.predict_indices(
        model, formal_encoded, batch_size=batch_size, device=device
    )
    predicted_labels = [neural.MODEL_LABELS[index] for index in predicted_indices]
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
    oov = {
        "train": neural.sample_oov_rate(splits["train"], token_to_id, text_field="text"),
        "dev": neural.sample_oov_rate(splits["dev"], token_to_id, text_field="text"),
        "official_test": neural.sample_oov_rate(splits["official_test"], token_to_id, text_field="text"),
        "estg150_formal_input": neural.sample_oov_rate(
            records, token_to_id, text_field=spec.input_field
        ),
    }
    checkpoint_rel = _model_checkpoint_rel(method_id)
    checkpoint = neural.save_checkpoint(
        formal_root / checkpoint_rel,
        model,
        metadata={
            "method_id": method_id,
            "config_sha256": common.sha256_file(config_path),
            "train_membership_sha256": splits["audit"]["final"]["train"]["membership_sha256"],
            "best_epoch": training["best_epoch"],
            "labels": list(neural.MODEL_LABELS),
        },
    )
    checkpoint["path"] = checkpoint_rel
    diagnostics = {
        "schema_version": "sep_c2_sun_predecessor_neural_diagnostics@1.0.0",
        "method_id": method_id,
        "predicted_label_counts": dict(sorted(Counter(predicted_labels).items())),
        "oov_rate": oov,
        "training_best_dev": training["best_dev"],
        "training_history": training["history"],
        "official_clean_test_metrics": official_test_metrics,
        "dataset_audit": _sanitized_dataset_audit(splits["audit"]),
        "embedding_cache": _sanitized_cache_metadata(embedding["metadata"]),
    }
    training_document = {
        "schema_version": "sep_c2_sun_predecessor_training@1.0.0",
        "method_id": method_id,
        "config_path": config_rel,
        "config": config,
        "dataset_audit": splits["audit"],
        "embedding_cache": _sanitized_cache_metadata(embedding["metadata"]),
        "oov_rate": oov,
        "best_dev": training["best_dev"],
        "history": training["history"],
        "official_clean_test_metrics": official_test_metrics,
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
        "frozen_hyperparameters": hyperparameters,
    }
    manifest = {
        "schema_version": "sep_c2_sun_predecessor_method_manifest@1.0.0",
        "method_id": spec.method_id,
        "claim_scope": "development_zero_api_predecessor_method_comparison",
        "sun_source_and_role": spec.sun_role,
        "reproduction_class": spec.reproduction_class,
        "version_caveat": (
            "Built against the locally available earlier author manuscript; the final Springer version "
            "could not be checked in this offline environment. Hyperparameters not given by Sun are frozen "
            "in the method config and reported here."
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
        "embedding_cache": _sanitized_cache_metadata(embedding["metadata"]),
        "implementation_bindings": {
            rel: _source_binding(formal_root, rel)
            for rel in (
                "src/bpc_hybrid/sun_predecessors/common.py",
                "src/bpc_hybrid/sun_predecessors/dataset.py",
                "src/bpc_hybrid/sun_predecessors/evaluation.py",
                "src/bpc_hybrid/sun_predecessors/neural.py",
                "src/bpc_hybrid/sun_predecessors/runner_neural.py",
                "scripts/run_sep_c2_sun_predecessor_neural_v1.py",
            )
        },
        "safety": {
            "new_llm_api_calls": 0,
            "new_network_calls": 0,
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
            "clean_train_rows": len(train_records),
            "clean_dev_rows": len(dev_records),
            "best_epoch": training["best_epoch"],
            "best_dev": training["best_dev"],
            "checkpoint": checkpoint,
            "oov_rate": oov,
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


def render_neural_markdown(report: Mapping[str, Any]) -> str:
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
        f"- training rows: {training['clean_train_rows']} train / {training['clean_dev_rows']} dev",
        f"- best dev macro-F1: {training['best_dev']['macro_f1']:.4f} (epoch {training['best_epoch']})",
        f"- official clean test diagnostic: accuracy {report['official_clean_test']['accuracy']:.4f}, "
        f"macro-F1 {report['official_clean_test']['macro_f1']:.4f}, "
        f"n={report['official_clean_test']['n']}",
        f"- OOV rate (train/dev/official test/EStG-150): "
        f"{training['oov_rate']['train']:.4f} / {training['oov_rate']['dev']:.4f} / "
        f"{training['oov_rate']['official_test']:.4f} / {training['oov_rate']['estg150_formal_input']:.4f}",
        "",
        f"- version caveat: {report['version_caveat']}",
        f"- new LLM/API calls: {report['safety']['new_llm_api_calls']}",
        "",
    ]
    return "\n".join(lines)
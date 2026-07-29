"""Verify, smoke-test, or train the locked S2.4 Legal-BERT + TextCNN model."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import torch
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.bert_textcnn import (  # noqa: E402
    LABELS,
    BertTextCNN,
    BertTextCNNError,
    build_collate_fn,
    compute_classification_metrics,
    load_records,
    load_training_config,
    set_deterministic_seed,
    sha256_file,
)
from formal_experiment.s2_4_license_gate import verify_s2_4_license_gate  # noqa: E402


DEFAULT_CONFIG = ROOT / "configs" / "models" / "sun_bert_textcnn_s24.json"


def _project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _verify_inputs(config_path: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    gate = verify_s2_4_license_gate(ROOT)
    if gate.get("ready") is not True:
        raise BertTextCNNError(f"S2.4 local research gate is not ready: {gate}")
    verified_splits: dict[str, dict[str, Any]] = {}
    for name in ("train", "dev", "test"):
        spec = config["dataset"][name]
        path = _project_path(spec["path"])
        actual_hash = sha256_file(path)
        if actual_hash != spec["sha256"]:
            raise BertTextCNNError(f"{name} split SHA-256 mismatch")
        records = load_records(path, expected_rows=spec["rows"])
        verified_splits[name] = {
            "path": spec["path"],
            "rows": len(records),
            "sha256": actual_hash,
        }
    use_spec = config["local_research_use_gate"]
    use_path = _project_path(use_spec["path"])
    if sha256_file(use_path) != use_spec["sha256"]:
        raise BertTextCNNError("local research use decision SHA-256 mismatch")
    return {
        "config_path": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": sha256_file(config_path),
        "s2_4_ready": True,
        "rights_status": gate["rights_status"],
        "redistribution_allowed": gate["redistribution_allowed"],
        "splits": verified_splits,
    }


def _resolve_local_model(config: Mapping[str, Any]) -> tuple[Path, dict[str, str]]:
    from huggingface_hub import snapshot_download

    spec = config["pretrained_model"]
    try:
        snapshot = Path(
            snapshot_download(
                repo_id=spec["repository_id"],
                revision=spec["revision"],
                local_files_only=True,
            )
        )
    except Exception as exc:  # huggingface_hub exposes several cache errors
        raise BertTextCNNError(
            "locked Legal-BERT snapshot is not available in the local cache"
        ) from exc
    verified: dict[str, str] = {}
    for name, expected_hash in spec["required_files"].items():
        path = snapshot / name
        if not path.is_file():
            raise BertTextCNNError(f"cached Legal-BERT file is missing: {name}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise BertTextCNNError(f"cached Legal-BERT hash mismatch: {name}")
        verified[name] = actual_hash
    return snapshot, verified


def _load_model_and_tokenizer(
    config: Mapping[str, Any], device: torch.device
) -> tuple[BertTextCNN, Any, Path, dict[str, str]]:
    snapshot, hashes = _resolve_local_model(config)
    tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
    encoder = AutoModel.from_pretrained(snapshot, local_files_only=True)
    architecture = config["architecture"]
    model = BertTextCNN(
        encoder,
        kernel_sizes=architecture["kernel_sizes"],
        filters_per_kernel=architecture["filters_per_kernel"],
        dropout=architecture["dropout"],
        num_labels=architecture["num_labels"],
    ).to(device)
    return model, tokenizer, snapshot, hashes


def _device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if requested == "cuda" and not torch.cuda.is_available():
        raise BertTextCNNError("CUDA was requested but is not available")
    return torch.device(requested)


@torch.no_grad()
def _evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> dict[str, Any]:
    model.eval()
    total_loss = 0.0
    total_rows = 0
    gold: list[int] = []
    predicted: list[int] = []
    loss_function = nn.CrossEntropyLoss()
    for batch in loader:
        labels = batch["labels"].to(device)
        logits = model(
            input_ids=batch["input_ids"].to(device),
            attention_mask=batch["attention_mask"].to(device),
        )
        loss = loss_function(logits, labels)
        total_loss += float(loss.item()) * labels.shape[0]
        total_rows += labels.shape[0]
        gold.extend(labels.cpu().tolist())
        predicted.extend(logits.argmax(dim=1).cpu().tolist())
    metrics = compute_classification_metrics(gold, predicted)
    metrics["loss"] = total_loss / total_rows
    return metrics


def _smoke(config: Mapping[str, Any], device: torch.device) -> dict[str, Any]:
    model, tokenizer, snapshot, hashes = _load_model_and_tokenizer(config, device)
    encoded = tokenizer(
        [
            "Income is defined as the total taxable amount.",
            "The taxpayer shall submit the declaration.",
            "The authority may grant an extension.",
            "The applicant must not disclose the record.",
        ],
        padding=True,
        truncation=True,
        max_length=config["tokenization"]["max_length"],
        return_tensors="pt",
    )
    model.eval()
    with torch.no_grad():
        logits = model(
            input_ids=encoded["input_ids"].to(device),
            attention_mask=encoded["attention_mask"].to(device),
        )
    if tuple(logits.shape) != (4, 4) or not torch.isfinite(logits).all():
        raise BertTextCNNError("S2.4 real-model smoke produced invalid logits")
    return {
        "status": "smoke_passed",
        "device": str(device),
        "shape": list(logits.shape),
        "local_snapshot_revision": snapshot.name,
        "verified_model_files": hashes,
        "network_called": False,
        "dataset_rows_read": 0,
        "test_evaluation_count": 0,
    }


def _train(
    config_path: Path,
    config: Mapping[str, Any],
    preflight: Mapping[str, Any],
    device: torch.device,
    output_dir: Path,
    manifest_out: Path,
    run_id: str,
) -> dict[str, Any]:
    if output_dir.exists():
        raise BertTextCNNError(f"output directory already exists: {output_dir}")
    if manifest_out.exists():
        raise BertTextCNNError(f"manifest already exists: {manifest_out}")
    output_dir.mkdir(parents=True, exist_ok=False)
    manifest_out.parent.mkdir(parents=True, exist_ok=True)

    optimization = config["optimization"]
    set_deterministic_seed(optimization["seed"])
    model, tokenizer, snapshot, model_hashes = _load_model_and_tokenizer(config, device)
    collate = build_collate_fn(
        tokenizer, max_length=config["tokenization"]["max_length"]
    )
    split_records = {
        name: load_records(
            _project_path(config["dataset"][name]["path"]),
            expected_rows=config["dataset"][name]["rows"],
        )
        for name in ("train", "dev", "test")
    }
    generator = torch.Generator().manual_seed(optimization["seed"])
    train_loader = DataLoader(
        split_records["train"],
        batch_size=optimization["batch_size"],
        shuffle=True,
        generator=generator,
        collate_fn=collate,
        num_workers=0,
    )
    dev_loader = DataLoader(
        split_records["dev"],
        batch_size=optimization["batch_size"],
        shuffle=False,
        collate_fn=collate,
        num_workers=0,
    )
    test_loader = DataLoader(
        split_records["test"],
        batch_size=optimization["batch_size"],
        shuffle=False,
        collate_fn=collate,
        num_workers=0,
    )

    encoder_parameters = list(model.encoder.parameters())
    encoder_ids = {id(parameter) for parameter in encoder_parameters}
    head_parameters = [
        parameter for parameter in model.parameters() if id(parameter) not in encoder_ids
    ]
    optimizer = AdamW(
        [
            {"params": encoder_parameters, "lr": optimization["encoder_learning_rate"]},
            {"params": head_parameters, "lr": optimization["head_learning_rate"]},
        ],
        weight_decay=optimization["weight_decay"],
    )
    accumulation = optimization["gradient_accumulation_steps"]
    updates_per_epoch = (len(train_loader) + accumulation - 1) // accumulation
    total_updates = updates_per_epoch * optimization["max_epochs"]
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=round(total_updates * optimization["warmup_ratio"]),
        num_training_steps=total_updates,
    )
    loss_function = nn.CrossEntropyLoss()
    checkpoint_path = output_dir / "best_model.pt"
    history: list[dict[str, Any]] = []
    best_macro_f1 = -1.0
    best_epoch = 0
    stale_epochs = 0

    for epoch in range(1, optimization["max_epochs"] + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        loss_sum = 0.0
        rows_seen = 0
        for batch_index, batch in enumerate(train_loader, start=1):
            labels = batch["labels"].to(device)
            logits = model(
                input_ids=batch["input_ids"].to(device),
                attention_mask=batch["attention_mask"].to(device),
            )
            raw_loss = loss_function(logits, labels)
            (raw_loss / accumulation).backward()
            loss_sum += float(raw_loss.item()) * labels.shape[0]
            rows_seen += labels.shape[0]
            if batch_index % accumulation == 0 or batch_index == len(train_loader):
                nn.utils.clip_grad_norm_(model.parameters(), optimization["gradient_clip_norm"])
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
        dev_metrics = _evaluate(model, dev_loader, device)
        history.append(
            {
                "epoch": epoch,
                "train_loss": loss_sum / rows_seen,
                "dev": dev_metrics,
            }
        )
        print(
            json.dumps(
                {
                    "epoch": epoch,
                    "train_loss": history[-1]["train_loss"],
                    "dev_loss": dev_metrics["loss"],
                    "dev_macro_f1": dev_metrics["macro_f1"],
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )
        improvement = dev_metrics["macro_f1"] - best_macro_f1
        if improvement > optimization["early_stopping_min_delta"]:
            best_macro_f1 = dev_metrics["macro_f1"]
            best_epoch = epoch
            stale_epochs = 0
            torch.save(
                {
                    "schema_version": "sun_bert_textcnn_checkpoint@1.0.0",
                    "config_sha256": preflight["config_sha256"],
                    "labels": list(LABELS),
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                },
                checkpoint_path,
            )
        else:
            stale_epochs += 1
            if stale_epochs >= optimization["early_stopping_patience"]:
                break

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    best_dev = _evaluate(model, dev_loader, device)
    test_metrics = _evaluate(model, test_loader, device)
    checkpoint_hash = sha256_file(checkpoint_path)
    local_history_path = output_dir / "aggregate_history.json"
    local_history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "schema_version": "sun_bert_textcnn_run_manifest@1.0.0",
        "task_id": "S2.4",
        "run_id": run_id,
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "paper_faithful_independent_legal_bert_textcnn_reconstruction",
        "claim_boundary": config["claim_boundary"],
        "config": {
            "path": config_path.relative_to(ROOT).as_posix(),
            "sha256": preflight["config_sha256"],
            "schema_version": config["schema_version"],
        },
        "runtime": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": __import__("transformers").__version__,
            "device": str(device),
            "cuda_available": torch.cuda.is_available(),
        },
        "pretrained_model": {
            "repository_id": config["pretrained_model"]["repository_id"],
            "revision": snapshot.name,
            "verified_files": model_hashes,
            "local_files_only": True,
        },
        "dataset": preflight["splits"],
        "selection": {
            "split": "dev",
            "metric": "macro_f1",
            "best_epoch": best_epoch,
            "epochs_completed": len(history),
            "best_dev": best_dev,
        },
        "test": {
            "policy": "single_evaluation_after_best_dev_checkpoint",
            "evaluation_count": 1,
            "metrics": test_metrics,
        },
        "checkpoint": {
            "path": checkpoint_path.relative_to(ROOT).as_posix(),
            "sha256": checkpoint_hash,
            "bytes": checkpoint_path.stat().st_size,
            "versioned": False,
        },
        "artifacts": {
            "aggregate_history_path": local_history_path.relative_to(ROOT).as_posix(),
            "row_level_predictions_persisted": False,
        },
        "safety": {
            "rights_status": preflight["rights_status"],
            "local_noncommercial_training_and_evaluation_authorized": True,
            "redistribution_allowed": False,
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "test_evaluation_count": 1,
        },
    }
    local_manifest = output_dir / "run_manifest.json"
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    local_manifest.write_text(payload, encoding="utf-8")
    manifest_out.write_text(payload, encoding="utf-8")
    return manifest


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", choices=("verify", "smoke", "train"), default="verify")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--manifest-out", type=Path)
    parser.add_argument("--run-id")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        config_path = args.config.resolve()
        config = load_training_config(config_path)
        preflight = _verify_inputs(config_path, config)
        if args.mode == "verify":
            result: Mapping[str, Any] = {"status": "verified", **preflight}
        elif args.mode == "smoke":
            result = {**preflight, **_smoke(config, _device(args.device))}
        else:
            if not args.output_dir or not args.manifest_out or not args.run_id:
                raise BertTextCNNError(
                    "train mode requires --output-dir, --manifest-out, and --run-id"
                )
            output_dir = _project_path(str(args.output_dir))
            manifest_out = _project_path(str(args.manifest_out))
            result = _train(
                config_path,
                config,
                preflight,
                _device(args.device),
                output_dir,
                manifest_out,
                args.run_id,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BertTextCNNError, OSError, KeyError, TypeError) as exc:
        print(f"S2.4 failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

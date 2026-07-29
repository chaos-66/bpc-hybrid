"""Preregistered S2.4 BERT-TextCNN candidate trainer (A/B/C).

Candidates are fixed in configs/models/s24_bert_textcnn_candidate_registry_v1.json
before any result. Selection uses dev macro-F1 only. Test is evaluated once
per candidate run and MUST NOT be used to choose among candidates after the fact
in the same process as selection; the compare script only ranks by dev.

Does not overwrite the locked s24_legal_bert_textcnn_seed20260717_v1 artifacts.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import torch
from torch import nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, WeightedRandomSampler
from transformers import get_linear_schedule_with_warmup

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.sun_style.bert_textcnn import (  # noqa: E402
    LABELS,
    BertTextCNNError,
    build_collate_fn,
    load_records,
    load_training_config,
    set_deterministic_seed,
    sha256_file,
)
from formal_experiment.s2_4_license_gate import verify_s2_4_license_gate  # noqa: E402

# Reuse private helpers from the locked trainer module via import of the script package path
sys.path.insert(0, str(ROOT / "scripts"))
from train_sun_bert_textcnn import (  # noqa: E402
    _device,
    _evaluate,
    _load_model_and_tokenizer,
    _project_path,
    _verify_inputs,
)


REGISTRY = ROOT / "configs/models/s24_bert_textcnn_candidate_registry_v1.json"
PARENT_CONFIG = ROOT / "configs/models/sun_bert_textcnn_s24.json"


def _load_registry() -> dict[str, Any]:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if reg.get("schema_version") != "s24_bert_textcnn_candidate_registry@1.0.0":
        raise BertTextCNNError("candidate registry schema mismatch")
    if len(reg.get("candidates", {})) != 3:
        raise BertTextCNNError("exactly 3 preregistered candidates required")
    return reg


def _make_train_loader(
    records: list,
    *,
    collate,
    batch_size: int,
    seed: int,
    sampler_name: str,
) -> DataLoader:
    if sampler_name == "shuffle":
        generator = torch.Generator().manual_seed(seed)
        return DataLoader(
            records,
            batch_size=batch_size,
            shuffle=True,
            generator=generator,
            collate_fn=collate,
            num_workers=0,
        )
    if sampler_name == "balanced_weighted_random":
        counts = Counter(r.label for r in records)
        # weight per sample = 1/count(class)
        sample_weights = [1.0 / counts[r.label] for r in records]
        sampler = WeightedRandomSampler(
            weights=torch.as_tensor(sample_weights, dtype=torch.double),
            num_samples=len(records),
            replacement=True,
            generator=torch.Generator().manual_seed(seed),
        )
        return DataLoader(
            records,
            batch_size=batch_size,
            sampler=sampler,
            shuffle=False,
            collate_fn=collate,
            num_workers=0,
        )
    raise BertTextCNNError(f"unknown sampler: {sampler_name}")


def _loss_fn(candidate: Mapping[str, Any], device: torch.device) -> nn.Module:
    loss_name = candidate["loss"]
    if loss_name == "unweighted_cross_entropy":
        return nn.CrossEntropyLoss()
    if loss_name == "inverse_sqrt_class_frequency_weighted_cross_entropy":
        vector = candidate.get("class_weight_vector")
        if not isinstance(vector, list) or len(vector) != 4:
            raise BertTextCNNError("missing class_weight_vector for weighted CE")
        weight = torch.tensor([float(x) for x in vector], dtype=torch.float32, device=device)
        return nn.CrossEntropyLoss(weight=weight)
    raise BertTextCNNError(f"unknown loss: {loss_name}")


def train_candidate(candidate_key: str, device_name: str = "cpu") -> dict[str, Any]:
    reg = _load_registry()
    if candidate_key not in reg["candidates"]:
        raise BertTextCNNError(f"unknown candidate key: {candidate_key}")
    candidate = reg["candidates"][candidate_key]
    run_id = candidate["run_id"]
    output_dir = ROOT / "outputs/development" / run_id
    manifest_out = ROOT / "outputs/reports" / f"{run_id}.manifest.json"
    if output_dir.exists() or manifest_out.exists():
        raise BertTextCNNError(f"refusing overwrite of existing candidate run: {run_id}")

    config_path = PARENT_CONFIG.resolve()
    config = load_training_config(config_path)
    preflight = _verify_inputs(config_path, config)
    device = _device(device_name if device_name != "cpu" else "cpu")
    optimization = config["optimization"]
    set_deterministic_seed(optimization["seed"])

    model, tokenizer, snapshot, model_hashes = _load_model_and_tokenizer(config, device)
    collate = build_collate_fn(tokenizer, max_length=config["tokenization"]["max_length"])
    split_records = {
        name: load_records(
            _project_path(config["dataset"][name]["path"]),
            expected_rows=config["dataset"][name]["rows"],
        )
        for name in ("train", "dev", "test")
    }
    train_loader = _make_train_loader(
        split_records["train"],
        collate=collate,
        batch_size=optimization["batch_size"],
        seed=optimization["seed"],
        sampler_name=candidate["sampler"],
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
    loss_function = _loss_fn(candidate, device)

    output_dir.mkdir(parents=True, exist_ok=False)
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
                "train_loss": loss_sum / max(rows_seen, 1),
                "dev": dev_metrics,
            }
        )
        print(
            json.dumps(
                {
                    "candidate": candidate_key,
                    "epoch": epoch,
                    "train_loss": history[-1]["train_loss"],
                    "dev_macro_f1": dev_metrics["macro_f1"],
                    "dev_per_class_f1": {
                        k: v["f1"] for k, v in dev_metrics["per_class"].items()
                    },
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
                    "candidate_key": candidate_key,
                    "candidate_loss": candidate["loss"],
                    "candidate_sampler": candidate["sampler"],
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
    # Single test evaluation after best-dev checkpoint freeze for this candidate.
    test_metrics = _evaluate(model, test_loader, device)
    checkpoint_hash = sha256_file(checkpoint_path)
    history_path = output_dir / "aggregate_history.json"
    history_path.write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    parent = reg["parent_locked_run"]
    manifest = {
        "schema_version": "sun_bert_textcnn_candidate_run_manifest@1.0.0",
        "task_id": "S2.4-CAND",
        "run_id": run_id,
        "candidate_key": candidate_key,
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "parent_locked_run_id": parent["run_id"],
        "parent_dev_macro_f1": parent["dev_macro_f1"],
        "parent_test_macro_f1": parent["test_macro_f1"],
        "preregistration": {
            "registry_path": "configs/models/s24_bert_textcnn_candidate_registry_v1.json",
            "registry_sha256": sha256_file(REGISTRY),
            "loss": candidate["loss"],
            "sampler": candidate["sampler"],
            "class_weights": candidate.get("class_weights"),
        },
        "config": {
            "path": "configs/models/sun_bert_textcnn_s24.json",
            "sha256": preflight["config_sha256"],
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
            "policy": "single_evaluation_after_best_dev_checkpoint_per_candidate",
            "evaluation_count": 1,
            "metrics": test_metrics,
            "used_for_selection": False,
        },
        "checkpoint": {
            "path": checkpoint_path.relative_to(ROOT).as_posix(),
            "sha256": checkpoint_hash,
            "bytes": checkpoint_path.stat().st_size,
        },
        "artifacts": {
            "aggregate_history_path": history_path.relative_to(ROOT).as_posix(),
            "row_level_predictions_persisted": False,
        },
        "safety": {
            "gold_read_or_modified": False,
            "llm_api_called": False,
            "network_called": False,
            "estg150_used": False,
            "test_used_for_selection": False,
            "no_overwrite": True,
        },
    }
    payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    (output_dir / "run_manifest.json").write_text(payload, encoding="utf-8")
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(payload, encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate",
        required=True,
        choices=(
            "A_unweighted_ce",
            "B_invsqrt_weighted_ce",
            "C_balanced_sampler",
        ),
    )
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    args = parser.parse_args()
    try:
        gate = verify_s2_4_license_gate(ROOT)
        if gate.get("ready") is not True:
            raise BertTextCNNError(f"S2.4 gate not ready: {gate}")
        result = train_candidate(args.candidate, device_name=args.device)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (BertTextCNNError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"candidate train failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

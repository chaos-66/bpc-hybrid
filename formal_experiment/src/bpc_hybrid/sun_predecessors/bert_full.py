# -*- coding: utf-8 -*-
"""Final-paper BERT-TextCNN modality classifier for SEP-C2.

Architecture source: Sun et al. (2024), final article Fig. 3: the [CLS]
vectors of all BERT encoder layers (CLS1..CLS12 for a 12-layer encoder) are
concatenated as the input sequence of a TextCNN head, followed by global max
pooling and a fully connected four-class output.  The encoder and head are
fine-tuned jointly on the clean official EStG train split.  The module never
reads Gold during prediction.
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn
from transformers import AutoModel, AutoTokenizer

from bpc_hybrid.sun_predecessors import neural
from bpc_hybrid.sun_predecessors.common import SunPredecessorError

LABELS = ("definition", "obligation", "permission", "prohibition")
LABEL_TO_INDEX = {label: index for index, label in enumerate(LABELS)}


@dataclass(frozen=True)
class EncodedExample:
    sample_id: str
    text: str
    input_ids: list[int]
    attention_mask: list[int]
    label: str | None = None


class BertFullError(SunPredecessorError):
    """Raised when the final-paper BERT-TextCNN contract cannot be honoured."""


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def resolve_device(preference: str = "auto") -> torch.device:
    preference = str(preference or "auto").lower()
    if preference == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if preference == "cuda" and not torch.cuda.is_available():
        raise BertFullError("CUDA requested but torch.cuda.is_available() is false")
    if preference not in {"cpu", "cuda"}:
        raise BertFullError(f"unsupported device preference: {preference!r}")
    return torch.device(preference)


def load_encoder_and_tokenizer(
    model_dir: Path,
    *,
    expected_hidden_size: int | None = None,
    expected_num_hidden_layers: int | None = None,
) -> tuple[nn.Module, Any, dict[str, Any]]:
    model_dir = Path(model_dir)
    if not (model_dir / "config.json").is_file():
        raise BertFullError(f"local model directory has no config.json: {model_dir}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True)
        encoder = AutoModel.from_pretrained(str(model_dir), local_files_only=True)
    except Exception as exc:  # pragma: no cover - exact backend errors vary
        raise BertFullError(f"cannot load local BERT model from {model_dir}") from exc
    config = encoder.config
    hidden_size = int(getattr(config, "hidden_size", 0) or 0)
    num_layers = int(getattr(config, "num_hidden_layers", 0) or 0)
    if expected_hidden_size is not None and hidden_size != int(expected_hidden_size):
        raise BertFullError(
            f"hidden size mismatch: expected {expected_hidden_size}, got {hidden_size}"
        )
    if expected_num_hidden_layers is not None and num_layers != int(expected_num_hidden_layers):
        raise BertFullError(
            f"layer count mismatch: expected {expected_num_hidden_layers}, got {num_layers}"
        )
    metadata = {
        "model_dir": str(model_dir),
        "hidden_size": hidden_size,
        "num_hidden_layers": num_layers,
        "vocab_size": int(getattr(config, "vocab_size", 0) or 0),
        "max_position_embeddings": int(getattr(config, "max_position_embeddings", 0) or 0),
        "model_type": str(getattr(config, "model_type", "")),
    }
    return encoder, tokenizer, metadata


class BertLayerTextCNN(nn.Module):
    """TextCNN over the sequence of per-layer [CLS] vectors (paper Fig. 3)."""

    def __init__(
        self,
        encoder: nn.Module,
        *,
        hidden_size: int,
        num_hidden_layers: int,
        kernel_sizes: Sequence[int] = (3, 4, 5),
        filters_per_kernel: int = 256,
        dropout: float = 0.5,
        num_labels: int = 4,
        encoder_trainable: bool = True,
    ) -> None:
        super().__init__()
        if hidden_size <= 0 or num_hidden_layers <= 0:
            raise BertFullError("hidden_size and num_hidden_layers must be positive")
        if tuple(int(v) for v in kernel_sizes) != (3, 4, 5):
            raise BertFullError("paper figure fixes kernel sizes to (3, 4, 5)")
        if filters_per_kernel <= 0 or num_labels != len(LABELS):
            raise BertFullError("invalid TextCNN or label dimensions")
        self.encoder = encoder
        self.hidden_size = int(hidden_size)
        self.num_hidden_layers = int(num_hidden_layers)
        self.kernel_sizes = (3, 4, 5)
        self.filters_per_kernel = int(filters_per_kernel)
        self.convolutions = nn.ModuleList(
            nn.Conv1d(self.hidden_size, self.filters_per_kernel, kernel_size)
            for kernel_size in self.kernel_sizes
        )
        self.dropout = nn.Dropout(float(dropout))
        self.classifier = nn.Linear(self.filters_per_kernel * len(self.kernel_sizes), num_labels)
        for parameter in self.encoder.parameters():
            parameter.requires_grad = bool(encoder_trainable)
        self.encoder_trainable = bool(encoder_trainable)

    def forward(self, *, input_ids: Tensor, attention_mask: Tensor) -> Tensor:
        encoded = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True,
            return_dict=True,
        )
        hidden_states = getattr(encoded, "hidden_states", None)
        if hidden_states is None or len(hidden_states) < self.num_hidden_layers + 1:
            raise BertFullError("BERT encoder did not return all hidden states")
        # Fig. 3 uses CLS1..CLSL from each encoder layer, not the embedding layer.
        cls_vectors = [state[:, 0, :] for state in hidden_states[1 : self.num_hidden_layers + 1]]
        feature_sequence = torch.stack(cls_vectors, dim=1).transpose(1, 2)
        pooled: list[Tensor] = []
        for convolution in self.convolutions:
            convolved = F.relu(convolution(feature_sequence))
            pooled.append(convolved.amax(dim=2))
        return self.classifier(self.dropout(torch.cat(pooled, dim=1)))


def tokenize_examples(
    tokenizer: Any,
    rows: Sequence[Mapping[str, Any]],
    *,
    text_field: str,
    max_length: int,
    label_field: str | None = None,
) -> list[EncodedExample]:
    encoded: list[EncodedExample] = []
    for row in rows:
        text = row.get(text_field)
        if not isinstance(text, str) or not text.strip():
            raise BertFullError(f"empty text in {text_field} for sample {row.get('sample_id')!r}")
        batch = tokenizer(
            text,
            padding=False,
            truncation=True,
            max_length=int(max_length),
            return_attention_mask=True,
        )
        input_ids = [int(value) for value in batch["input_ids"]]
        attention_mask = [int(value) for value in batch["attention_mask"]]
        label = None
        if label_field is not None:
            label = row.get(label_field)
            if label not in LABEL_TO_INDEX:
                raise BertFullError(f"unknown label for sample {row.get('sample_id')!r}: {label!r}")
        encoded.append(
            EncodedExample(
                sample_id=str(row["sample_id"]),
                text=text,
                input_ids=input_ids,
                attention_mask=attention_mask,
                label=str(label) if label is not None else None,
            )
        )
    return encoded


def sequence_length_stats(
    tokenizer: Any,
    rows: Sequence[Mapping[str, Any]],
    *,
    text_field: str,
    max_length: int,
) -> dict[str, Any]:
    lengths = [
        len(tokenizer(str(row[text_field]), add_special_tokens=True)["input_ids"])
        for row in rows
    ]
    if not lengths:
        return {"rows": 0, "max_length": int(max_length)}
    return {
        "rows": len(lengths),
        "p50": int(np.percentile(lengths, 50)),
        "p95": int(np.percentile(lengths, 95)),
        "p99": int(np.percentile(lengths, 99)),
        "max": int(max(lengths)),
        "rows_over_max_length": int(sum(1 for length in lengths if length > int(max_length))),
        "max_length": int(max_length),
    }


def _batch(
    examples: Sequence[EncodedExample],
    *,
    device: torch.device,
    with_labels: bool,
) -> tuple[Tensor, Tensor, Tensor | None]:
    max_len = max(len(example.input_ids) for example in examples)
    input_ids = torch.zeros((len(examples), max_len), dtype=torch.long)
    attention_mask = torch.zeros((len(examples), max_len), dtype=torch.long)
    labels: list[int] = []
    for index, example in enumerate(examples):
        length = len(example.input_ids)
        input_ids[index, :length] = torch.tensor(example.input_ids, dtype=torch.long)
        attention_mask[index, :length] = torch.tensor(example.attention_mask, dtype=torch.long)
        if with_labels:
            if example.label is None:
                raise BertFullError("missing label in labelled batch")
            labels.append(LABEL_TO_INDEX[example.label])
    label_tensor = torch.tensor(labels, dtype=torch.long) if with_labels else None
    return input_ids.to(device), attention_mask.to(device), (
        label_tensor.to(device) if label_tensor is not None else None
    )


@torch.no_grad()
def predict_indices(
    model: nn.Module,
    examples: Sequence[EncodedExample],
    *,
    batch_size: int,
    device: torch.device,
) -> list[int]:
    model.eval()
    predictions: list[int] = []
    for start in range(0, len(examples), batch_size):
        batch = examples[start : start + batch_size]
        input_ids, attention_mask, _ = _batch(batch, device=device, with_labels=False)
        logits = model(input_ids=input_ids, attention_mask=attention_mask)
        predictions.extend(int(value) for value in logits.argmax(dim=1).detach().cpu().tolist())
    return predictions


def metrics_for_examples(
    model: nn.Module,
    examples: Sequence[EncodedExample],
    *,
    batch_size: int,
    device: torch.device,
) -> dict[str, Any]:
    gold = [LABEL_TO_INDEX[example.label] for example in examples]
    predicted = predict_indices(model, examples, batch_size=batch_size, device=device)
    return neural.classification_metrics(gold, predicted)


def train_model(
    *,
    model: BertLayerTextCNN,
    train_examples: Sequence[EncodedExample],
    dev_examples: Sequence[EncodedExample],
    optimization: Mapping[str, Any],
    device: torch.device,
) -> dict[str, Any]:
    if not train_examples or not dev_examples:
        raise BertFullError("train and dev examples must be non-empty")
    seed = int(optimization["seed"])
    set_seed(seed)
    batch_size = int(optimization["batch_size"])
    max_epochs = int(optimization["max_epochs"])
    patience = int(optimization["early_stopping_patience"])
    encoder_lr = float(optimization["encoder_learning_rate"])
    head_lr = float(optimization["head_learning_rate"])
    weight_decay = float(optimization["weight_decay"])
    grad_clip = float(optimization["gradient_clip_norm"])
    warmup_ratio = float(optimization.get("warmup_ratio", 0.0))
    encoder_params = [p for p in model.encoder.parameters() if p.requires_grad]
    head_params = [p for p in model.parameters() if not any(p is q for q in encoder_params)]
    parameter_groups: list[dict[str, Any]] = []
    if encoder_params:
        parameter_groups.append({"params": encoder_params, "lr": encoder_lr})
    if head_params:
        parameter_groups.append({"params": head_params, "lr": head_lr})
    optimizer = torch.optim.AdamW(parameter_groups, lr=head_lr, weight_decay=weight_decay)
    steps_per_epoch = max(1, math.ceil(len(train_examples) / batch_size))
    total_steps = steps_per_epoch * max_epochs
    scheduler = None
    if warmup_ratio > 0:
        try:
            from transformers import get_linear_schedule_with_warmup

            warmup_steps = int(total_steps * warmup_ratio)
            scheduler = get_linear_schedule_with_warmup(
                optimizer,
                num_warmup_steps=warmup_steps,
                num_training_steps=total_steps,
            )
        except Exception as exc:
            raise BertFullError("cannot create learning-rate scheduler") from exc
    loss_function = nn.CrossEntropyLoss()
    best_state = {
        key: value.detach().cpu().clone() for key, value in model.state_dict().items()
    }
    best_metrics = metrics_for_examples(
        model, dev_examples, batch_size=batch_size, device=device
    )
    best_epoch = 0
    stale = 0
    history: list[dict[str, Any]] = []
    rng = random.Random(seed)
    for epoch in range(1, max_epochs + 1):
        model.train()
        order = list(range(len(train_examples)))
        rng.shuffle(order)
        epoch_loss = 0.0
        batch_count = 0
        for start in range(0, len(order), batch_size):
            batch_indices = order[start : start + batch_size]
            batch = [train_examples[index] for index in batch_indices]
            input_ids, attention_mask, labels = _batch(batch, device=device, with_labels=True)
            if labels is None:
                raise BertFullError("training batch lost labels")
            optimizer.zero_grad(set_to_none=True)
            logits = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = loss_function(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()
            if scheduler is not None:
                scheduler.step()
            epoch_loss += float(loss.detach().cpu().item())
            batch_count += 1
        dev_metrics = metrics_for_examples(
            model, dev_examples, batch_size=batch_size, device=device
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss_mean": epoch_loss / max(batch_count, 1),
                "dev": dev_metrics,
            }
        )
        if dev_metrics["macro_f1"] > best_metrics["macro_f1"] + 1e-12:
            best_metrics = dev_metrics
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            best_epoch = epoch
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return {
        "seed": seed,
        "best_epoch": best_epoch,
        "best_dev": best_metrics,
        "history": history,
        "device": str(device),
        "selection_split": "official_clean_dev",
        "selection_metric": "macro_f1",
        "test_used_for_selection": False,
        "encoder_trainable": model.encoder_trainable,
    }


def save_checkpoint(
    path: Path,
    model: nn.Module,
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    import hashlib

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "sep_c2_sun_predecessor_bert_full_checkpoint@1.0.0",
        "model_state_dict": model.state_dict(),
        "metadata": dict(metadata),
    }
    torch.save(payload, path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "sha256": digest,
        "byte_size": path.stat().st_size,
        "versioned": False,
        "local_only_do_not_commit": True,
    }

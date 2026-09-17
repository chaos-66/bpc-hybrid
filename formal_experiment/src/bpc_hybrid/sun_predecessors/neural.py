# -*- coding: utf-8 -*-
"""Paper-described BiLSTM and CNN modality classifiers, trained locally.

These are independent reconstructions of the baselines in Sun et al.
(2024), Table 7.  The paper does not disclose all hyperparameters; every
reconstruction choice is stored in the per-method config.  Training uses only
the clean official EStG train split; the official dev split selects the best
epoch.  EStG-150 is never read during fitting, hyperparameter search, or model
selection.
"""

from __future__ import annotations

import copy
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn.utils import clip_grad_norm_

from bpc_hybrid.sun_predecessors.common import MODALITY_CLASSES, SunPredecessorError, tokenize_words

MODEL_LABELS = ("definition", "obligation", "permission", "prohibition")
LABEL_TO_INDEX = {label: index for index, label in enumerate(MODEL_LABELS)}
PAD_ID = 0
UNK_ID = 1


@dataclass(frozen=True)
class EncodedRecord:
    sample_id: str
    token_ids: list[int]
    label: str | None = None


def set_deterministic_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False


def encode_text(text: str, token_to_id: Mapping[str, int], *, max_length: int) -> list[int]:
    tokens = tokenize_words(text)
    if not tokens:
        return [UNK_ID]
    return [token_to_id.get(token, UNK_ID) for token in tokens[:max_length]]


def encode_records(
    rows: Sequence[Mapping[str, Any]],
    token_to_id: Mapping[str, int],
    *,
    max_length: int,
    text_field: str,
    label_field: str | None = None,
) -> list[EncodedRecord]:
    return [
        EncodedRecord(
            sample_id=str(row["sample_id"]),
            token_ids=encode_text(str(row[text_field]), token_to_id, max_length=max_length),
            label=str(row[label_field]) if label_field and row.get(label_field) is not None else None,
        )
        for row in rows
    ]


class BiLSTMClassifier(nn.Module):
    def __init__(self, embedding_matrix: np.ndarray, *, hidden_size: int, dropout: float) -> None:
        super().__init__()
        matrix = torch.as_tensor(embedding_matrix, dtype=torch.float32)
        self.embedding = nn.Embedding.from_pretrained(matrix, freeze=False, padding_idx=PAD_ID)
        self.lstm = nn.LSTM(
            input_size=matrix.shape[1],
            hidden_size=hidden_size,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size * 4, len(MODEL_LABELS))

    def forward(self, *, input_ids: Tensor, attention_mask: Tensor) -> Tensor:
        embedded = self.embedding(input_ids)
        hidden, _ = self.lstm(embedded)
        mask = attention_mask.unsqueeze(-1).to(dtype=hidden.dtype)
        mean = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
        masked = hidden.masked_fill(mask == 0, -torch.inf)
        maximum = masked.amax(dim=1)
        maximum = torch.where(torch.isfinite(maximum), maximum, torch.zeros_like(maximum))
        features = torch.cat([mean, maximum], dim=1)
        return self.classifier(self.dropout(features))


class TextCNNClassifier(nn.Module):
    def __init__(
        self,
        embedding_matrix: np.ndarray,
        *,
        kernel_sizes: Sequence[int],
        filters_per_kernel: int,
        dropout: float,
    ) -> None:
        super().__init__()
        matrix = torch.as_tensor(embedding_matrix, dtype=torch.float32)
        self.embedding = nn.Embedding.from_pretrained(matrix, freeze=False, padding_idx=PAD_ID)
        self.kernel_sizes = tuple(int(value) for value in kernel_sizes)
        self.convolutions = nn.ModuleList(
            nn.Conv1d(matrix.shape[1], filters_per_kernel, kernel_size)
            for kernel_size in self.kernel_sizes
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(filters_per_kernel * len(self.kernel_sizes), len(MODEL_LABELS))

    def forward(self, *, input_ids: Tensor, attention_mask: Tensor) -> Tensor:
        embedded = self.embedding(input_ids).transpose(1, 2)
        valid = attention_mask.unsqueeze(1)
        pooled_features = []
        for kernel_size, convolution in zip(self.kernel_sizes, self.convolutions, strict=True):
            convolved = torch.relu(convolution(embedded))
            valid_windows = torch.nn.functional.avg_pool1d(
                valid.float(), kernel_size=kernel_size, stride=1
            ).eq(1.0)
            masked = convolved.masked_fill(~valid_windows, -torch.inf)
            pooled = masked.amax(dim=2)
            pooled = torch.where(torch.isfinite(pooled), pooled, torch.zeros_like(pooled))
            pooled_features.append(pooled)
        return self.classifier(self.dropout(torch.cat(pooled_features, dim=1)))


def _batch_tensors(
    records: Sequence[EncodedRecord],
    *,
    device: torch.device,
) -> tuple[Tensor, Tensor, Tensor | None]:
    max_length = max(len(record.token_ids) for record in records)
    input_ids = torch.zeros((len(records), max_length), dtype=torch.long)
    attention_mask = torch.zeros((len(records), max_length), dtype=torch.long)
    labels: list[int] = []
    for row_index, record in enumerate(records):
        length = len(record.token_ids)
        input_ids[row_index, :length] = torch.tensor(record.token_ids, dtype=torch.long)
        attention_mask[row_index, :length] = 1
        if record.label is not None:
            labels.append(LABEL_TO_INDEX[record.label])
    label_tensor = torch.tensor(labels, dtype=torch.long) if labels else None
    return input_ids.to(device), attention_mask.to(device), (
        label_tensor.to(device) if label_tensor is not None else None
    )


def classification_metrics(gold_indices: Sequence[int], predicted_indices: Sequence[int]) -> dict[str, Any]:
    if len(gold_indices) != len(predicted_indices) or not gold_indices:
        raise SunPredecessorError("metrics require equal non-empty gold/prediction lists")
    size = len(MODEL_LABELS)
    confusion = [[0 for _ in range(size)] for _ in range(size)]
    for gold, predicted in zip(gold_indices, predicted_indices, strict=True):
        confusion[gold][predicted] += 1
    per_class = {}
    f1_values = []
    for index, label in enumerate(MODEL_LABELS):
        tp = confusion[index][index]
        support = sum(confusion[index])
        predicted_count = sum(row[index] for row in confusion)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
            "predicted_count": predicted_count,
        }
        f1_values.append(f1)
    correct = sum(confusion[index][index] for index in range(size))
    return {
        "n": len(gold_indices),
        "accuracy": correct / len(gold_indices),
        "macro_f1": sum(f1_values) / size,
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


@torch.no_grad()
def predict_indices(
    model: nn.Module,
    records: Sequence[EncodedRecord],
    *,
    batch_size: int,
    device: torch.device,
) -> list[int]:
    model.eval()
    predictions: list[int] = []
    for start in range(0, len(records), batch_size):
        batch = records[start:start + batch_size]
        input_ids, attention_mask, _ = _batch_tensors(batch, device=device)
        logits = model(input_ids=input_ids, attention_mask=attention_mask)
        predictions.extend(int(value) for value in logits.argmax(dim=1).cpu().tolist())
    return predictions


def _metrics_from_records(model: nn.Module, records: Sequence[EncodedRecord], *, batch_size: int, device: torch.device) -> dict[str, Any]:
    labels = [LABEL_TO_INDEX[record.label] for record in records]
    predictions = predict_indices(model, records, batch_size=batch_size, device=device)
    return classification_metrics(labels, predictions)


def train_model(
    *,
    kind: str,
    train_records: Sequence[EncodedRecord],
    dev_records: Sequence[EncodedRecord],
    embedding_matrix: np.ndarray,
    hyperparameters: Mapping[str, Any],
) -> tuple[nn.Module, dict[str, Any]]:
    if kind not in {"cf_rnn", "cf_cnn"}:
        raise SunPredecessorError(f"unsupported neural kind: {kind}")
    if not train_records or not dev_records:
        raise SunPredecessorError("train and dev records must be non-empty")
    seed = int(hyperparameters["seed"])
    set_deterministic_seed(seed)
    device = torch.device("cpu")
    if kind == "cf_rnn":
        model: nn.Module = BiLSTMClassifier(
            embedding_matrix,
            hidden_size=int(hyperparameters["hidden_size"]),
            dropout=float(hyperparameters["dropout"]),
        )
    else:
        model = TextCNNClassifier(
            embedding_matrix,
            kernel_sizes=tuple(hyperparameters["kernel_sizes"]),
            filters_per_kernel=int(hyperparameters["filters_per_kernel"]),
            dropout=float(hyperparameters["dropout"]),
        )
    model.to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(hyperparameters["learning_rate"]),
        weight_decay=float(hyperparameters["weight_decay"]),
    )
    loss_function = nn.CrossEntropyLoss()
    batch_size = int(hyperparameters["batch_size"])
    max_epochs = int(hyperparameters["max_epochs"])
    patience = int(hyperparameters["early_stopping_patience"])
    best_state = copy.deepcopy(model.state_dict())
    best_metrics: dict[str, Any] = _metrics_from_records(
        model, dev_records, batch_size=batch_size, device=device
    )
    best_epoch = 0
    stale_epochs = 0
    history: list[dict[str, Any]] = []
    rng = random.Random(seed)
    for epoch in range(1, max_epochs + 1):
        model.train()
        order = list(range(len(train_records)))
        rng.shuffle(order)
        epoch_loss = 0.0
        epoch_batches = 0
        for start in range(0, len(order), batch_size):
            batch = [train_records[index] for index in order[start:start + batch_size]]
            input_ids, attention_mask, labels = _batch_tensors(batch, device=device)
            if labels is None:
                raise SunPredecessorError("training batch has no labels")
            optimizer.zero_grad(set_to_none=True)
            logits = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = loss_function(logits, labels)
            loss.backward()
            clip_grad_norm_(model.parameters(), float(hyperparameters["gradient_clip_norm"]))
            optimizer.step()
            epoch_loss += float(loss.detach().cpu().item())
            epoch_batches += 1
        metrics = _metrics_from_records(model, dev_records, batch_size=batch_size, device=device)
        history.append(
            {
                "epoch": epoch,
                "train_loss_mean": epoch_loss / max(epoch_batches, 1),
                "dev": metrics,
            }
        )
        if metrics["macro_f1"] > best_metrics["macro_f1"] + 1e-12:
            best_metrics = metrics
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            stale_epochs = 0
        else:
            stale_epochs += 1
            if stale_epochs >= patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, {
        "kind": kind,
        "seed": seed,
        "best_epoch": best_epoch,
        "best_dev": best_metrics,
        "history": history,
        "device": "cpu",
        "selection_split": "official_clean_dev",
        "selection_metric": "macro_f1",
        "test_used_for_selection": False,
    }


def sample_oov_rate(
    rows: Sequence[Mapping[str, Any]],
    token_to_id: Mapping[str, int],
    *,
    text_field: str,
) -> float:
    total = 0
    unknown = 0
    for row in rows:
        for token in tokenize_words(str(row[text_field])):
            total += 1
            if token not in token_to_id:
                unknown += 1
    return unknown / total if total else 0.0

def save_checkpoint(
    path: Path,
    model: nn.Module,
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a local-only checkpoint and return its deterministic binding."""
    import hashlib

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "sep_c2_sun_predecessor_checkpoint@1.0.0",
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

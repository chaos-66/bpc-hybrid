"""S2.4 Legal-BERT + TextCNN modality classifier.

The implementation is deliberately local-only and data-minimizing.  It reads
the locked development JSONL splits, never reads Gold, never calls a network or
LLM, and exposes only aggregate evaluation metrics.  Sun's unpublished code and
checkpoint are not used; reconstruction-only parameters live in the versioned
S2.4 config.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn


CONFIG_SCHEMA = "sun_bert_textcnn_s24@1.0.0"
LABELS = ("definition", "obligation", "permission", "prohibition")


class BertTextCNNError(ValueError):
    """Raised when an S2.4 input or configuration fails closed."""


@dataclass(frozen=True)
class ModalityRecord:
    sample_id: str
    text: str
    label: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_training_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BertTextCNNError(f"invalid S2.4 config: {path}") from exc
    if not isinstance(value, dict):
        raise BertTextCNNError("S2.4 config root must be an object")
    if value.get("schema_version") != CONFIG_SCHEMA:
        raise BertTextCNNError("unexpected S2.4 config schema_version")
    if value.get("task_id") != "S2.4":
        raise BertTextCNNError("S2.4 config task_id mismatch")
    if tuple(value.get("labels", ())) != LABELS:
        raise BertTextCNNError("S2.4 label order changed")
    architecture = value.get("architecture")
    if not isinstance(architecture, Mapping):
        raise BertTextCNNError("architecture must be an object")
    if (
        architecture.get("bert_output") != "last_hidden_state"
        or tuple(architecture.get("kernel_sizes", ())) != (2, 3, 4)
        or architecture.get("filters_per_kernel") != 128
        or architecture.get("activation") != "relu"
        or architecture.get("pooling") != "attention-mask-aware global max"
        or architecture.get("num_labels") != 4
    ):
        raise BertTextCNNError("BERT-TextCNN architecture is not locked")
    pretrained = value.get("pretrained_model")
    if not isinstance(pretrained, Mapping):
        raise BertTextCNNError("pretrained_model must be an object")
    if (
        pretrained.get("repository_id") != "nlpaueb/legal-bert-base-uncased"
        or pretrained.get("revision")
        != "15b570cbf88259610b082a167dacc190124f60f6"
        or pretrained.get("local_files_only") is not True
        or pretrained.get("hidden_size") != 768
    ):
        raise BertTextCNNError("pretrained model identity changed")
    evaluation = value.get("evaluation")
    safety = value.get("safety")
    if not isinstance(evaluation, Mapping) or not isinstance(safety, Mapping):
        raise BertTextCNNError("evaluation and safety sections are required")
    if (
        evaluation.get("selection_split") != "dev"
        or evaluation.get("selection_metric") != "macro_f1"
        or evaluation.get("test_policy")
        != "single_evaluation_after_best_dev_checkpoint"
        or evaluation.get("persist_row_level_predictions") is not False
    ):
        raise BertTextCNNError("evaluation boundary changed")
    locked_false = (
        "gold_read_or_modified",
        "llm_api_called",
        "network_allowed_by_runner",
        "raw_or_row_level_data_redistribution",
    )
    if any(safety.get(key) is not False for key in locked_false):
        raise BertTextCNNError("S2.4 safety boundary was relaxed")
    if safety.get("no_overwrite") is not True:
        raise BertTextCNNError("S2.4 no-overwrite boundary is required")
    return value


def load_records(path: Path, *, expected_rows: int | None = None) -> list[ModalityRecord]:
    records: list[ModalityRecord] = []
    seen: set[str] = set()
    try:
        stream = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise BertTextCNNError(f"split is unavailable: {path}") from exc
    with stream:
        for line_number, raw in enumerate(stream, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise BertTextCNNError(
                    f"invalid JSON at {path}:{line_number}"
                ) from exc
            if not isinstance(row, Mapping):
                raise BertTextCNNError(f"record must be an object at line {line_number}")
            sample_id = row.get("sample_id")
            text = row.get("text")
            label = row.get("label")
            if not isinstance(sample_id, str) or not sample_id or sample_id in seen:
                raise BertTextCNNError(f"invalid or duplicate sample_id at line {line_number}")
            if not isinstance(text, str) or not text.strip():
                raise BertTextCNNError(f"empty text at line {line_number}")
            if label not in LABELS:
                raise BertTextCNNError(f"unknown label at line {line_number}: {label!r}")
            seen.add(sample_id)
            records.append(ModalityRecord(sample_id=sample_id, text=text, label=label))
    if expected_rows is not None and len(records) != expected_rows:
        raise BertTextCNNError(
            f"split row count mismatch: expected {expected_rows}, got {len(records)}"
        )
    return records


def set_deterministic_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


class BertTextCNN(nn.Module):
    """Apply valid-width TextCNN filters over BERT contextual token states."""

    def __init__(
        self,
        encoder: nn.Module,
        *,
        kernel_sizes: Sequence[int] = (2, 3, 4),
        filters_per_kernel: int = 128,
        dropout: float = 0.1,
        num_labels: int = 4,
    ) -> None:
        super().__init__()
        hidden_size = getattr(getattr(encoder, "config", None), "hidden_size", None)
        if not isinstance(hidden_size, int) or hidden_size <= 0:
            raise BertTextCNNError("encoder.config.hidden_size must be a positive integer")
        if tuple(kernel_sizes) != (2, 3, 4):
            raise BertTextCNNError("kernel sizes must remain (2, 3, 4)")
        if filters_per_kernel <= 0 or num_labels != len(LABELS):
            raise BertTextCNNError("invalid TextCNN output dimensions")
        self.encoder = encoder
        self.kernel_sizes = tuple(int(value) for value in kernel_sizes)
        self.convolutions = nn.ModuleList(
            nn.Conv1d(hidden_size, filters_per_kernel, kernel)
            for kernel in self.kernel_sizes
        )
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(filters_per_kernel * len(self.kernel_sizes), num_labels)

    def forward(self, *, input_ids: Tensor, attention_mask: Tensor) -> Tensor:
        encoded = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        hidden = encoded.last_hidden_state
        if hidden.ndim != 3 or hidden.shape[:2] != input_ids.shape:
            raise BertTextCNNError("encoder returned an invalid last_hidden_state")
        features = hidden.transpose(1, 2)
        mask = attention_mask.to(dtype=features.dtype).unsqueeze(1)
        pooled_features: list[Tensor] = []
        for kernel, convolution in zip(self.kernel_sizes, self.convolutions, strict=True):
            convolved = F.relu(convolution(features))
            valid_windows = F.avg_pool1d(mask, kernel_size=kernel, stride=1).eq(1.0)
            masked = convolved.masked_fill(~valid_windows, -torch.inf)
            pooled = masked.amax(dim=2)
            pooled = torch.where(torch.isfinite(pooled), pooled, torch.zeros_like(pooled))
            pooled_features.append(pooled)
        return self.classifier(self.dropout(torch.cat(pooled_features, dim=1)))


def build_collate_fn(
    tokenizer: Any,
    *,
    max_length: int,
    label_to_id: Mapping[str, int] | None = None,
) -> Callable[[Sequence[ModalityRecord]], dict[str, Any]]:
    mapping = dict(label_to_id or {label: index for index, label in enumerate(LABELS)})

    def collate(batch: Sequence[ModalityRecord]) -> dict[str, Any]:
        encoded = tokenizer(
            [record.text for record in batch],
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        return {
            "input_ids": encoded["input_ids"],
            "attention_mask": encoded["attention_mask"],
            "labels": torch.tensor([mapping[record.label] for record in batch]),
        }

    return collate


def compute_classification_metrics(
    gold: Iterable[int],
    predicted: Iterable[int],
    *,
    labels: Sequence[str] = LABELS,
) -> dict[str, Any]:
    gold_values = list(gold)
    predicted_values = list(predicted)
    if len(gold_values) != len(predicted_values) or not gold_values:
        raise BertTextCNNError("metrics require equal non-empty gold and prediction lists")
    size = len(labels)
    confusion = [[0 for _ in range(size)] for _ in range(size)]
    for truth, guess in zip(gold_values, predicted_values, strict=True):
        if truth not in range(size) or guess not in range(size):
            raise BertTextCNNError("metric label index is out of range")
        confusion[truth][guess] += 1
    per_class: dict[str, dict[str, float | int]] = {}
    precision_values: list[float] = []
    recall_values: list[float] = []
    f1_values: list[float] = []
    for index, label in enumerate(labels):
        true_positive = confusion[index][index]
        support = sum(confusion[index])
        predicted_count = sum(row[index] for row in confusion)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = (
            2.0 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        precision_values.append(precision)
        recall_values.append(recall)
        f1_values.append(f1)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
    correct = sum(confusion[index][index] for index in range(size))
    return {
        "n": len(gold_values),
        "accuracy": correct / len(gold_values),
        "macro_precision": sum(precision_values) / size,
        "macro_recall": sum(recall_values) / size,
        "macro_f1": sum(f1_values) / size,
        "per_class": per_class,
        "confusion_matrix": {
            "label_order": list(labels),
            "rows_gold_columns_predicted": confusion,
        },
    }

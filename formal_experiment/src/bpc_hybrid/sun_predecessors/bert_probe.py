# -*- coding: utf-8 -*-
"""bert-legal-uncased comparison: frozen public legal-BERT + trained linear head.

This is the closest local match to Sun et al.'s Table 6 ``bert-legal-uncased``
row.  The encoder is the public ``nlpaueb/legal-bert-base-uncased`` snapshot,
loaded from the local Hugging Face cache with no network.  Full CPU
fine-tuning of a 110M-parameter encoder is not attempted; instead the encoder
is frozen and a supervised linear classification head is trained on the clean
official train split.  The weaker adaptation is disclosed in every artifact.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import Tensor, nn

from bpc_hybrid.sun_predecessors import common, neural


class BertProbeError(common.SunPredecessorError):
    """Raised when the local legal-BERT probe cannot run as contracted."""


@dataclass(frozen=True)
class EncoderBundle:
    encoder: nn.Module
    tokenizer: Any
    snapshot_path: str
    metadata: dict[str, Any]


def load_local_legal_bert(formal_root: Path) -> EncoderBundle:
    """Load the exact public legal-BERT revision pinned by the project."""
    formal_root = Path(formal_root)
    s24_config_path = formal_root / "configs/models/sun_bert_textcnn_s24.json"
    s24_config = common.load_json(s24_config_path)
    pretrained = s24_config.get("pretrained_model")
    if not isinstance(pretrained, Mapping):
        raise BertProbeError("S2.4 config has no pretrained_model block")
    try:
        from huggingface_hub import snapshot_download
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise BertProbeError("transformers/huggingface_hub are required for the BERT probe") from exc
    try:
        snapshot = Path(
            snapshot_download(
                repo_id=str(pretrained["repository_id"]),
                revision=str(pretrained["revision"]),
                local_files_only=True,
            )
        )
    except Exception as exc:
        raise BertProbeError("local Legal-BERT cache is unavailable") from exc
    required = pretrained.get("required_files")
    if not isinstance(required, Mapping):
        raise BertProbeError("S2.4 config has no required_files hashes")
    for name, expected in required.items():
        path = snapshot / str(name)
        if not path.is_file() or common.sha256_file(path) != str(expected):
            raise BertProbeError(f"local Legal-BERT file hash mismatch: {name}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
        encoder = AutoModel.from_pretrained(snapshot, local_files_only=True)
    except Exception as exc:
        raise BertProbeError("local Legal-BERT load failed") from exc
    encoder.eval()
    return EncoderBundle(
        encoder=encoder,
        tokenizer=tokenizer,
        snapshot_path=str(snapshot),
        metadata={
            "repository_id": str(pretrained["repository_id"]),
            "revision": str(pretrained["revision"]),
            "required_file_hashes": {str(k): str(v) for k, v in required.items()},
            "local_files_only": True,
            "network_calls": 0,
        },
    )


@torch.no_grad()
def extract_features(
    bundle: EncoderBundle,
    texts: Sequence[str],
    *,
    max_length: int,
    batch_size: int,
) -> Tensor:
    if not texts:
        raise BertProbeError("feature extraction requires non-empty texts")
    features: list[Tensor] = []
    for start in range(0, len(texts), batch_size):
        batch = list(texts[start:start + batch_size])
        encoded = bundle.tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        output = bundle.encoder(
            input_ids=encoded["input_ids"],
            attention_mask=encoded["attention_mask"],
        )
        hidden = output.last_hidden_state
        mask = encoded["attention_mask"].unsqueeze(-1).to(dtype=hidden.dtype)
        pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1.0)
        features.append(pooled.detach().cpu())
    return torch.cat(features, dim=0).float()


class LinearHead(nn.Module):
    def __init__(self, input_dimension: int, num_labels: int = 4) -> None:
        super().__init__()
        self.classifier = nn.Linear(input_dimension, num_labels)

    def forward(self, features: Tensor) -> Tensor:
        return self.classifier(features)


class MLPHead(nn.Module):
    def __init__(
        self,
        input_dimension: int,
        *,
        hidden_size: int,
        dropout: float,
        num_labels: int = 4,
    ) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dimension, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, num_labels),
        )

    def forward(self, features: Tensor) -> Tensor:
        return self.network(features)


def build_head(
    input_dimension: int,
    *,
    head_config: Mapping[str, Any],
    num_labels: int = 4,
) -> nn.Module:
    head_type = str(head_config.get("type"))
    if head_type == "linear":
        return LinearHead(input_dimension, num_labels=num_labels)
    if head_type == "mlp":
        return MLPHead(
            input_dimension,
            hidden_size=int(head_config["hidden_size"]),
            dropout=float(head_config["dropout"]),
            num_labels=num_labels,
        )
    raise BertProbeError(f"unsupported BERT probe head type: {head_type!r}")


def train_linear_probe(
    *,
    train_features: Tensor,
    train_labels: Sequence[int],
    dev_features: Tensor,
    dev_labels: Sequence[int],
    hyperparameters: Mapping[str, Any],
    head_config: Mapping[str, Any],
) -> tuple[nn.Module, dict[str, Any]]:
    seed = int(hyperparameters["seed"])
    neural.set_deterministic_seed(seed)
    device = torch.device("cpu")
    model = build_head(
        train_features.shape[1],
        head_config=head_config,
        num_labels=len(neural.MODEL_LABELS),
    ).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(hyperparameters["learning_rate"]),
        weight_decay=float(hyperparameters["weight_decay"]),
    )
    loss_function = nn.CrossEntropyLoss()
    train_labels_tensor = torch.tensor(list(train_labels), dtype=torch.long, device=device)
    dev_labels_tensor = torch.tensor(list(dev_labels), dtype=torch.long, device=device)
    train_features = train_features.to(device)
    dev_features = dev_features.to(device)
    batch_size = int(hyperparameters["batch_size"])
    max_epochs = int(hyperparameters["max_epochs"])
    patience = int(hyperparameters["early_stopping_patience"])
    rng = random.Random(seed)

    def metrics(features: Tensor, labels: Tensor) -> dict[str, Any]:
        model.eval()
        with torch.no_grad():
            predictions = model(features).argmax(dim=1)
            return neural.classification_metrics(
                labels.cpu().tolist(), predictions.cpu().tolist()
            )

    best_state = copy.deepcopy(model.state_dict())
    best_metrics = metrics(dev_features, dev_labels_tensor)
    best_epoch = 0
    stale_epochs = 0
    history: list[dict[str, Any]] = []
    for epoch in range(1, max_epochs + 1):
        model.train()
        order = list(range(train_features.shape[0]))
        rng.shuffle(order)
        epoch_loss = 0.0
        batches = 0
        for start in range(0, len(order), batch_size):
            indices = order[start:start + batch_size]
            batch_features = train_features[indices]
            batch_labels = train_labels_tensor[indices]
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_features)
            loss = loss_function(logits, batch_labels)
            loss.backward()
            optimizer.step()
            epoch_loss += float(loss.detach().cpu().item())
            batches += 1
        dev_metrics = metrics(dev_features, dev_labels_tensor)
        history.append(
            {
                "epoch": epoch,
                "train_loss_mean": epoch_loss / max(batches, 1),
                "dev": dev_metrics,
            }
        )
        if dev_metrics["macro_f1"] > best_metrics["macro_f1"] + 1e-12:
            best_metrics = dev_metrics
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
        "seed": seed,
        "best_epoch": best_epoch,
        "best_dev": best_metrics,
        "history": history,
        "device": "cpu",
        "selection_split": "official_clean_dev",
        "selection_metric": "macro_f1",
        "test_used_for_selection": False,
        "encoder_frozen": True,
        "head_type": str(head_config.get("type")),
    }


@torch.no_grad()
def predict_with_head(model: nn.Module, features: Tensor) -> list[int]:
    model.eval()
    return [int(value) for value in model(features).argmax(dim=1).cpu().tolist()]


@torch.no_grad()
def sequence_length_stats(
    bundle: EncoderBundle,
    texts: Sequence[str],
    *,
    max_length: int,
) -> dict[str, Any]:
    lengths = []
    for text in texts:
        token_ids = bundle.tokenizer(text, add_special_tokens=True)["input_ids"]
        lengths.append(len(token_ids))
    if not lengths:
        return {"rows": 0}
    return {
        "rows": len(lengths),
        "p50": int(np.percentile(lengths, 50)),
        "p95": int(np.percentile(lengths, 95)),
        "p99": int(np.percentile(lengths, 99)),
        "max": int(max(lengths)),
        "rows_over_max_length": int(sum(1 for length in lengths if length > max_length)),
        "max_length": int(max_length),
    }
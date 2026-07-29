from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import torch
from torch import nn

from bpc_hybrid.sun_style.bert_textcnn import (
    LABELS,
    BertTextCNN,
    BertTextCNNError,
    ModalityRecord,
    build_collate_fn,
    compute_classification_metrics,
    load_records,
    load_training_config,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "models" / "sun_bert_textcnn_s24.json"


class TinyEncoder(nn.Module):
    def __init__(self, hidden_size: int = 12) -> None:
        super().__init__()
        self.config = SimpleNamespace(hidden_size=hidden_size)
        self.embedding = nn.Embedding(32, hidden_size)

    def forward(self, *, input_ids: torch.Tensor, attention_mask: torch.Tensor):
        del attention_mask
        return SimpleNamespace(last_hidden_state=self.embedding(input_ids))


class TinyTokenizer:
    def __call__(self, texts, **kwargs):
        del kwargs
        width = max(len(text.split()) for text in texts) + 2
        input_ids = []
        masks = []
        for text in texts:
            length = len(text.split()) + 2
            input_ids.append([1] * length + [0] * (width - length))
            masks.append([1] * length + [0] * (width - length))
        return {
            "input_ids": torch.tensor(input_ids),
            "attention_mask": torch.tensor(masks),
        }


def test_locked_s2_4_config_is_loadable() -> None:
    config = load_training_config(CONFIG)
    assert config["labels"] == list(LABELS)
    assert config["pretrained_model"]["local_files_only"] is True
    assert config["evaluation"]["test_policy"] == (
        "single_evaluation_after_best_dev_checkpoint"
    )
    assert config["evaluation"]["persist_row_level_predictions"] is False


def test_textcnn_forward_uses_four_class_output_and_masks_padding() -> None:
    torch.manual_seed(7)
    model = BertTextCNN(TinyEncoder(), filters_per_kernel=3, dropout=0.0)
    input_ids = torch.tensor([[1, 2, 3, 4, 0, 0], [1, 2, 3, 4, 5, 6]])
    attention_mask = torch.tensor([[1, 1, 1, 1, 0, 0], [1, 1, 1, 1, 1, 1]])
    logits = model(input_ids=input_ids, attention_mask=attention_mask)
    assert logits.shape == (2, 4)
    assert torch.isfinite(logits).all()


def test_textcnn_rejects_architecture_drift() -> None:
    with pytest.raises(BertTextCNNError, match="kernel sizes"):
        BertTextCNN(TinyEncoder(), kernel_sizes=(3, 4, 5))


def test_collate_keeps_only_tensors_not_text_or_sample_ids() -> None:
    batch = [
        ModalityRecord("a", "alpha beta", "definition"),
        ModalityRecord("b", "gamma delta epsilon", "prohibition"),
    ]
    collated = build_collate_fn(TinyTokenizer(), max_length=16)(batch)
    assert set(collated) == {"input_ids", "attention_mask", "labels"}
    assert collated["labels"].tolist() == [0, 3]


def test_metrics_have_fixed_orientation_and_macro_f1() -> None:
    metrics = compute_classification_metrics([0, 0, 1, 2, 3], [0, 1, 1, 2, 2])
    assert metrics["n"] == 5
    assert metrics["accuracy"] == pytest.approx(3 / 5)
    assert metrics["confusion_matrix"]["label_order"] == list(LABELS)
    assert metrics["confusion_matrix"]["rows_gold_columns_predicted"] == [
        [1, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 0],
    ]
    assert 0.0 <= metrics["macro_f1"] <= 1.0


def test_split_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = tmp_path / "split.jsonl"
    rows = [
        {"sample_id": "same", "text": "one", "label": "definition"},
        {"sample_id": "same", "text": "two", "label": "obligation"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    with pytest.raises(BertTextCNNError, match="duplicate sample_id"):
        load_records(path)


def test_config_rejects_network_or_row_prediction_relaxation(tmp_path: Path) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["safety"]["network_allowed_by_runner"] = True
    path = tmp_path / "relaxed.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(BertTextCNNError, match="safety boundary"):
        load_training_config(path)

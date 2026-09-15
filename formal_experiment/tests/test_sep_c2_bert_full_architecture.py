# -*- coding: utf-8 -*-
from __future__ import annotations

import types

import torch
from torch import nn

from bpc_hybrid.sun_predecessors import common
from bpc_hybrid.sun_predecessors.bert_full import BertLayerTextCNN, LABELS


class _DummyEncoder(nn.Module):
    def __init__(self, hidden_size: int, num_layers: int) -> None:
        super().__init__()
        self.config = types.SimpleNamespace(hidden_size=hidden_size, num_hidden_layers=num_layers)
        self.linear = nn.Linear(hidden_size, hidden_size)

    def forward(self, *, input_ids, attention_mask, output_hidden_states=True, return_dict=True):
        batch, length = input_ids.shape
        base = torch.randn(batch, length, self.config.hidden_size)
        # hidden_states[0] is the embedding output; [1:] are encoder layers.
        states = tuple(base + float(i) for i in range(self.config.num_hidden_layers + 1))
        return types.SimpleNamespace(hidden_states=states, last_hidden_state=states[-1])


def test_bert_full_uses_per_layer_cls_sequence() -> None:
    encoder = _DummyEncoder(hidden_size=8, num_layers=8)
    model = BertLayerTextCNN(
        encoder,
        hidden_size=8,
        num_hidden_layers=8,
        kernel_sizes=(3, 4, 5),
        filters_per_kernel=4,
        dropout=0.0,
        num_labels=4,
    )
    input_ids = torch.zeros((2, 6), dtype=torch.long)
    attention_mask = torch.ones((2, 6), dtype=torch.long)
    logits = model(input_ids=input_ids, attention_mask=attention_mask)
    assert logits.shape == (2, 4)
    # The convolution input sequence length must be exactly the encoder layer count.
    cls_vectors = [state[:, 0, :] for state in encoder(input_ids=input_ids, attention_mask=attention_mask).hidden_states[1:]]
    assert len(cls_vectors) == 8


def test_new_bert_method_specs_are_registered() -> None:
    for method_id in (
        "bert_base_uncased",
        "bert_base_cased",
        "bert_large_uncased",
        "bert_large_cased",
        "bert_legal_uncased",
    ):
        spec = common.method_spec(method_id)
        assert spec.input_field == "raw_text_de"
        assert spec.input_language == "de"
    assert tuple(LABELS) == ("definition", "obligation", "permission", "prohibition")


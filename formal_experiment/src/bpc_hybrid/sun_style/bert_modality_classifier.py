"""Generic BERT classification scaffold (Wave 1.1 §7 clarification).

The current module is a **generic BERT sequence-classification
scaffold** that *can* be configured for 4-class modality
classification. It does **not** contain the BERT-TextCNN architecture
that Sun et al. (2024) describe; the TextCNN head with 2/3/4-gram
convolutions and max-pooling is not yet implemented. The current
scaffold also does not include a pre-trained checkpoint on the
official EStG modality dataset.

When the paper-faithful B0 is implemented, this module must be
extended with:
  * TextCNN head (conv kernels 2/3/4-gram, max-pooling, concat -> softmax)
  * Training pipeline on the official EStG modality CSV
  * Frozen-bert vs full-fine-tune support

Until then, this file must NOT be advertised as a "BERT-TextCNN
modality classifier". The 4-class label mapping and the
``from_pretrained_hub`` / ``from_pretrained`` helpers are useful
scaffolding but the model architecture is incomplete.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Label mapping (Sun论文 Table 6 顺序) ──────────────────────────
LABEL2ID = {"definition": 0, "obligation": 1, "prohibition": 2, "permission": 3}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}
NUM_LABELS = 4


@dataclass
class ModalityResult:
    """Classification result, compatible with existing ModalityResult interface."""
    modality: str
    confidence: float
    bert_used: bool = True
    probabilities: dict[str, float] = field(default_factory=dict)


class BertModalityClassifier:
    """BERT-based modality classifier for regulatory sentences.

    Usage:
        classifier = BertModalityClassifier.from_pretrained("models/bert_modality")
        result = classifier.classify("The controller shall process personal data lawfully.")
        print(result.modality)  # "obligation"
    """

    def __init__(self, model=None, tokenizer=None, device: str = "cpu"):
        self.model = model
        self.tokenizer = tokenizer
        self.device = device
        self._loaded = model is not None

    @classmethod
    def from_pretrained(cls, model_dir: str | Path, device: str = "cpu") -> "BertModalityClassifier":
        """Load a fine-tuned BERT modality classifier from disk."""
        model_dir = Path(model_dir)
        if not model_dir.exists():
            raise FileNotFoundError(f"Model directory not found: {model_dir}")

        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
        model = AutoModelForSequenceClassification.from_pretrained(str(model_dir))
        model.to(device)
        model.eval()

        instance = cls(model=model, tokenizer=tokenizer, device=device)
        logger.info("Loaded BERT modality classifier from %s", model_dir)
        return instance

    @classmethod
    def from_pretrained_hub(cls, model_name: str = "nlpaueb/legal-bert-base-uncased",
                            device: str = "cpu") -> "BertModalityClassifier":
        """Load a pre-trained BERT from HuggingFace Hub (not fine-tuned yet).
        
        Used as starting point for fine-tuning. Ignores existing id2label config
        to avoid conflicts with our 4-class modality classification.
        """
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=NUM_LABELS,
            ignore_mismatched_sizes=True,
        )
        # Override id2label/label2id after loading
        model.config.id2label = ID2LABEL
        model.config.label2id = LABEL2ID
        model.config.num_labels = NUM_LABELS
        model.to(device)

        instance = cls(model=model, tokenizer=tokenizer, device=device)
        logger.info("Loaded pre-trained BERT from hub: %s", model_name)
        return instance

    def classify(self, text: str) -> ModalityResult:
        """Classify a single sentence into modality category."""
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call from_pretrained() first.")

        import torch

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1).cpu().numpy()[0]

        pred_id = int(probs.argmax())
        return ModalityResult(
            modality=ID2LABEL[pred_id],
            confidence=float(probs[pred_id]),
            bert_used=True,
            probabilities={ID2LABEL[i]: float(p) for i, p in enumerate(probs)},
        )

    def save(self, output_dir: str | Path) -> None:
        """Save model and tokenizer to disk."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(output_dir))
        self.tokenizer.save_pretrained(str(output_dir))
        logger.info("Saved BERT modality classifier to %s", output_dir)

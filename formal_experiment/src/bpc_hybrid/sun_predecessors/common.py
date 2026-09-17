# -*- coding: utf-8 -*-
"""Shared helpers for the SEP-C2 Sun predecessor reconstruction.

The package is deliberately read-only with respect to Gold during prediction.
Only the evaluation entry points load ``data/gold``.  The module never imports
anything from ``references/`` or ``_retired/``.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "sep_c2_sun_predecessors@1.0.0"
METHOD_IDS = (
    "cf_kw",
    "cf_rnn",
    "cf_cnn",
    "bert_base_uncased",
    "bert_base_cased",
    "bert_large_uncased",
    "bert_large_cased",
    "bert_legal_uncased",
    "bert_legal_uncased_probe",
    "bert_legal_uncased_textcnn_existing",
)
MODALITY_CLASSES = ("obligation", "permission", "prohibition", "definition")


class SunPredecessorError(ValueError):
    """Fail-closed error for the predecessor reconstruction."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SunPredecessorError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise SunPredecessorError(f"JSON root must be an object: {path}")
    return value


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    path = Path(path)
    try:
        stream = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise SunPredecessorError(f"cannot read JSONL: {path}") from exc
    with stream:
        for line_number, raw in enumerate(stream, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise SunPredecessorError(
                    f"invalid JSON at {path}:{line_number}"
                ) from exc
            if not isinstance(row, dict):
                raise SunPredecessorError(
                    f"JSONL row must be an object at {path}:{line_number}"
                )
            yield row


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def write_bytes_atomic(path: Path, payload: bytes) -> None:
    """Fail-closed atomic write that refuses to overwrite an existing file."""
    path = Path(path)
    if path.exists():
        raise SunPredecessorError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        stage = Path(stream.name)
        stream.write(payload)
    try:
        stage.replace(path)
    except Exception:
        stage.unlink(missing_ok=True)
        raise


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_WHITESPACE_RE = re.compile(r"[\s\u00a0]+", re.UNICODE)
_NON_WORD_RE = re.compile(r"[^\w]", re.UNICODE)


def normalize_for_match(text: str) -> str:
    """Normalization used only for exclusion/leakage checks, never for scoring."""
    if not isinstance(text, str):
        return ""
    value = value if (value := text.strip().lower()) is not None else ""
    value = _WHITESPACE_RE.sub(" ", value)
    value = _NON_WORD_RE.sub("", value)
    return value


def tokenize_words(text: str) -> list[str]:
    """Deterministic tokenization used by the local classifier baselines.

    The official EStG modality CSV carries one 300-d vector per whitespace token
    in ``text.split()``.  The imported development split preserves that token
    count, so this function must reproduce it exactly for official rows.
    """
    if not isinstance(text, str):
        return []
    tokens: list[str] = []
    for token in text.split():
        cleaned = _NON_WORD_RE.sub("", token).casefold()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def contiguous_subsequence(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    first = needle[0]
    for index, value in enumerate(haystack):
        if value != first:
            continue
        if list(haystack[index:index + len(needle)]) == list(needle):
            return True
    return False


def bool_as_int(value: bool) -> int:
    return 1 if value else 0


def require_keys(row: Mapping[str, Any], keys: Sequence[str], *, where: str) -> None:
    missing = [key for key in keys if key not in row]
    if missing:
        raise SunPredecessorError(f"{where}: missing keys {missing}")


@dataclass(frozen=True)
class MethodSpec:
    method_id: str
    sun_role: str
    reproduction_class: str
    input_field: str
    input_language: str
    training_data: str
    notes: str


METHOD_SPECS: dict[str, MethodSpec] = {
    "cf_kw": MethodSpec(
        method_id="cf_kw",
        sun_role="local author-manuscript Table 7 keyword classification baseline (CF_KW)",
        reproduction_class="paper-described rule baseline; keyword list reconstructed because the paper does not publish it",
        input_field="raw_text_de",
        input_language="de",
        training_data="none (deterministic keyword patterns)",
        notes=("Sun et al. local author manuscript Table 7 reports CF_KW 62.7/64.7/60.8 on their modality split. "
               "The local author-manuscript text only says 'simply uses keywords', so the exact keyword list is unavailable. "
               "This reconstruction uses an a-priori German legal-modal rule list and a definition fallback."),
    ),
    "cf_rnn": MethodSpec(
        method_id="cf_rnn",
        sun_role="local author-manuscript Table 7 bidirectional-LSTM classification baseline (CF_RNN)",
        reproduction_class="paper-described architecture retrained locally on the official EStG modality train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); dev for selection",
        notes=("Sun et al. do not publish hidden size, optimizer, vector initialization, or early-stop details. "
               "This run uses the official 300-d token vectors carried by EStG_sent_vec.csv and reports every chosen parameter."),
    ),
    "cf_cnn": MethodSpec(
        method_id="cf_cnn",
        sun_role="local author-manuscript Table 7 CNN classification baseline (CF_CNN)",
        reproduction_class="paper-described architecture retrained locally on the official EStG modality train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); dev for selection",
        notes=("Sun et al. cite a standard CNN for sentence classification and do not publish the exact kernel/filter settings; "
               "the reconstruction uses 3/4/5-gram filters, 100 filters each, dropout 0.5, and the official 300-d token vectors."),
    ),
    "bert_base_uncased": MethodSpec(
        method_id="bert_base_uncased",
        sun_role="local author-manuscript Table 6 bert-base-uncased comparison (directly verified); project-record final-version BERT-TextCNN architecture Section 4.2.1 / Fig. 3 (not re-fetched/re-verified 2026-09-17)",
        reproduction_class="public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); official dev for selection",
        notes=("Project record (2026-09-15) quotes the final article Section 4.2.1 / Fig. 3 as specifying per-layer [CLS] vectors as the TextCNN input; base 12-layer / 768-hidden, 12 encoder layers. "
               "The encoder revision is pinned in the method config. Unpublished hyperparameters are frozen there before the EStG-150 run. Final table numbering/numeric equality with the local author manuscript is not re-verified 2026-09-17 (TODO-SOURCE)."),
    ),
    "bert_base_cased": MethodSpec(
        method_id="bert_base_cased",
        sun_role="local author-manuscript Table 6 bert-base-cased comparison (directly verified); project-record final-version BERT-TextCNN architecture Section 4.2.1 / Fig. 3 (not re-fetched/re-verified 2026-09-17)",
        reproduction_class="public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); official dev for selection",
        notes=("Project record (2026-09-15) quotes the final article Section 4.2.1 / Fig. 3 as specifying per-layer [CLS] vectors as the TextCNN input; base 12-layer / 768-hidden, 12 encoder layers. "
               "The encoder revision is pinned in the method config. Unpublished hyperparameters are frozen there before the EStG-150 run. Final table numbering/numeric equality with the local author manuscript is not re-verified 2026-09-17 (TODO-SOURCE)."),
    ),
    "bert_large_uncased": MethodSpec(
        method_id="bert_large_uncased",
        sun_role="local author-manuscript Table 6 bert-large-uncased comparison (directly verified); project-record final-version BERT-TextCNN architecture Section 4.2.1 / Fig. 3 (not re-fetched/re-verified 2026-09-17)",
        reproduction_class="public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); official dev for selection",
        notes=("Project record (2026-09-15) quotes the final article Section 4.2.1 / Fig. 3 as specifying per-layer [CLS] vectors as the TextCNN input; large 24-layer / 1024-hidden, 24 encoder layers. "
               "The encoder revision is pinned in the method config. Unpublished hyperparameters are frozen there before the EStG-150 run. Final table numbering/numeric equality with the local author manuscript is not re-verified 2026-09-17 (TODO-SOURCE)."),
    ),
    "bert_large_cased": MethodSpec(
        method_id="bert_large_cased",
        sun_role="local author-manuscript Table 6 bert-large-cased comparison (directly verified); project-record final-version BERT-TextCNN architecture Section 4.2.1 / Fig. 3 (not re-fetched/re-verified 2026-09-17)",
        reproduction_class="public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); official dev for selection",
        notes=("Project record (2026-09-15) quotes the final article Section 4.2.1 / Fig. 3 as specifying per-layer [CLS] vectors as the TextCNN input; large 24-layer / 1024-hidden, 24 encoder layers. "
               "The encoder revision is pinned in the method config. Unpublished hyperparameters are frozen there before the EStG-150 run. Final table numbering/numeric equality with the local author manuscript is not re-verified 2026-09-17 (TODO-SOURCE)."),
    ),
    "bert_legal_uncased": MethodSpec(
        method_id="bert_legal_uncased",
        sun_role="local author-manuscript Table 6 bert-legal-uncased (nlpaueb/legal-bert-base-uncased) comparison (directly verified); project-record final-version BERT-TextCNN architecture Section 4.2.1 / Fig. 3 (not re-fetched/re-verified 2026-09-17)",
        reproduction_class="public pre-trained encoder plus project-record final-version BERT-TextCNN head, fine-tuned locally on the clean official EStG train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered against EStG-150 duplicates); official dev for selection",
        notes=("Project record (2026-09-15) quotes the final article Section 4.2.1 / Fig. 3 as specifying per-layer [CLS] vectors as the TextCNN input; base 12-layer / 768-hidden, 12 encoder layers. "
               "The encoder revision is pinned in the method config. Unpublished hyperparameters are frozen there before the EStG-150 run. Final table numbering/numeric equality with the local author manuscript is not re-verified 2026-09-17 (TODO-SOURCE)."),
    ),
    "bert_legal_uncased_probe": MethodSpec(
        method_id="bert_legal_uncased_probe",
        sun_role="local author-manuscript Table 6 bert-legal-uncased comparison; closest locally available public legal-BERT encoder (final table numbering not re-verified 2026-09-17)",
        reproduction_class="matched public encoder frozen; classification head trained locally on the clean official train split",
        input_field="raw_text_de",
        input_language="de",
        training_data="official Sun/Michel EStG modality train split (filtered); dev for selection",
        notes=("Local cache contains nlpaueb/legal-bert-base-uncased (EU legislation), the closest available match to Sun's "
               "bert-legal-uncased family. CPU-only full fine-tuning is not attempted; the encoder is frozen and a linear "
               "classification head is trained on clean data. This is disclosed as a weaker, method-level reconstruction."),
    ),
    "bert_legal_uncased_textcnn_existing": MethodSpec(
        method_id="bert_legal_uncased_textcnn_existing",
        sun_role="Existing project S2.4/S2.6 BERT-TextCNN classifier using the project-record final-version head, reused read-only",
        reproduction_class="existing locally trained checkpoint; reused without retraining",
        input_field="raw_text_de",
        input_language="de",
        training_data="existing S2.4 checkpoint trained on the official EStG modality train split before this SEP-C2 run",
        notes=("This is the already published B0 classifier component (nlpaueb/legal-bert-base-uncased + TextCNN). "
               "Its original train split contains a small number of normalized-text overlaps with EStG-150; therefore it is "
               "reported as a diagnostic sensitivity row, not as the primary clean BERT comparison."),
    ),
}


def method_spec(method_id: str) -> MethodSpec:
    try:
        return METHOD_SPECS[method_id]
    except KeyError as exc:
        raise SunPredecessorError(f"unknown predecessor method: {method_id}") from exc
# -*- coding: utf-8 -*-
"""Clean official EStG modality splits and 300-d embedding cache for SEP-C2.

The official ``records.jsonl``/split JSONL files intentionally omit the raw
300-d vectors.  The vectors still live in the locally authorized Archive.org
supplement.  This module streams that CSV, verifies its 1:1 token alignment,
and builds a train-only vocabulary.  No sentence text, label, vector value, or
row is copied into a versioned artifact; only aggregate audit metadata and a
local ignore-rule development cache are produced.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import numbers
import re
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from bpc_hybrid.sun_predecessors.common import (
    SunPredecessorError,
    contiguous_subsequence,
    load_json,
    normalize_for_match,
    sha256_file,
    tokenize_words,
)

OFFICIAL_SPLIT_DIR_REL = "data/development/modality/sun_estg_modality_v1/splits"
OFFICIAL_SOURCE_ZIP_REL = "data/development/sun_modality/raw/Decision_Logic_data.zip"
CSV_MEMBER = "EStG_sent_vec.csv"
CSV_TEXT_COLUMN = 3
CSV_VECTOR_COLUMN = 9
VECTOR_DIMENSION = 300
MIN_TOKEN_SUBSEQUENCE = 8
CACHE_SCHEMA = "sep_c2_sun_predecessor_embedding_cache@1.0.0"


@dataclass(frozen=True)
class OfficialRow:
    sample_id: str
    text: str
    label: str
    source_row_index: int


def _official_rows(path: Path) -> list[OfficialRow]:
    rows: list[OfficialRow] = []
    seen_ids: set[str] = set()
    for line_number, row in enumerate(
        (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()),
        start=1,
    ):
        if not isinstance(row, dict):
            raise SunPredecessorError(f"official split row is not an object: {path.name}:{line_number}")
        sample_id = row.get("sample_id")
        text = row.get("text")
        label = row.get("label")
        row_index = row.get("source_row_index")
        if not isinstance(sample_id, str) or not sample_id or sample_id in seen_ids:
            raise SunPredecessorError(f"invalid or duplicate sample_id at {path.name}:{line_number}")
        if not isinstance(text, str) or not text.strip():
            raise SunPredecessorError(f"empty text at {path.name}:{line_number}")
        if label not in {"definition", "obligation", "permission", "prohibition"}:
            raise SunPredecessorError(f"unknown label at {path.name}:{line_number}: {label!r}")
        if not isinstance(row_index, int) or isinstance(row_index, bool) or row_index < 0:
            raise SunPredecessorError(f"invalid source_row_index at {path.name}:{line_number}")
        tokens = tokenize_words(text)
        if int(row.get("vector_token_count") or -1) != len(tokens):
            raise SunPredecessorError(f"vector token count mismatch at {path.name}:{line_number}")
        seen_ids.add(sample_id)
        rows.append(OfficialRow(sample_id=sample_id, text=text, label=label, source_row_index=row_index))
    return rows


def _test_probes(formal_root: Path) -> list[tuple[str, list[str]]]:
    document = load_json(Path(formal_root) / "data/input/estg150_formal_inference_input_v2.json")
    probes: list[tuple[str, list[str]]] = []
    for row in document["records"]:
        raw = row["raw_text_de"]
        approved = row["approved_text_en"]
        for text in (raw, approved):
            normalized = normalize_for_match(text)
            if normalized:
                probes.append((normalized, tokenize_words(text)))
    return probes


def _overlaps_estg150(text: str, probes: Sequence[tuple[str, list[str]]]) -> bool:
    normalized = normalize_for_match(text)
    tokens = tokenize_words(text)
    if not normalized:
        return True
    for probe_norm, probe_tokens in probes:
        if normalized == probe_norm:
            return True
        if len(normalized) >= 30 and len(probe_norm) >= 30:
            if normalized in probe_norm or probe_norm in normalized:
                return True
        if len(tokens) >= MIN_TOKEN_SUBSEQUENCE and contiguous_subsequence(tokens, probe_tokens):
            return True
        if len(probe_tokens) >= MIN_TOKEN_SUBSEQUENCE and contiguous_subsequence(probe_tokens, tokens):
            return True
    return False


def _label_distribution(rows: Sequence[OfficialRow]) -> dict[str, int]:
    return dict(sorted(Counter(row.label for row in rows).items()))


def _membership_hash(rows: Sequence[OfficialRow]) -> str:
    payload = json.dumps(
        sorted((row.sample_id, row.label) for row in rows), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_clean_splits(formal_root: Path, external_root: Path) -> dict[str, Any]:
    """Load official train/dev/test and remove EStG-150 overlaps and duplicates."""
    formal_root = Path(formal_root)
    external_root = Path(external_root)
    split_dir = external_root / OFFICIAL_SPLIT_DIR_REL
    probes = _test_probes(formal_root)
    original = {
        split: _official_rows(split_dir / f"{split}.jsonl")
        for split in ("train", "dev", "test")
    }
    audit: dict[str, Any] = {
        "schema_version": "sep_c2_sun_predecessor_split_audit@1.0.0",
        "official_split_origin": "project_reconstructed_deterministic_group_aware_split_not_sun_original",
        "source_files": {
            split: {
                "path": f"{OFFICIAL_SPLIT_DIR_REL}/{split}.jsonl",
                "sha256": sha256_file(split_dir / f"{split}.jsonl"),
                "rows": len(rows),
                "label_distribution": _label_distribution(rows),
            }
            for split, rows in original.items()
        },
        "estg150_probe_count": len(probes),
        "excluded_estg150_overlap": {},
        "excluded_cross_split_duplicate": {},
        "excluded_conflicting_duplicate": {},
        "final": {},
    }
    filtered: dict[str, list[OfficialRow]] = {}
    seen_normalized: dict[str, tuple[str, str]] = {}
    for split in ("train", "dev", "test"):
        kept: list[OfficialRow] = []
        overlap = 0
        cross_duplicate = 0
        conflict = 0
        for row in original[split]:
            if _overlaps_estg150(row.text, probes):
                overlap += 1
                continue
            normalized = normalize_for_match(row.text)
            previous = seen_normalized.get(normalized)
            if previous is not None:
                previous_split, previous_label = previous
                if previous_label == row.label:
                    cross_duplicate += 1
                else:
                    conflict += 1
                continue
            seen_normalized[normalized] = (split, row.label)
            kept.append(row)
        if split == "train":
            # Cross-split duplicates are resolved in train-first order above.
            pass
        filtered[split] = kept
        audit["excluded_estg150_overlap"][split] = overlap
        audit["excluded_cross_split_duplicate"][split] = cross_duplicate
        audit["excluded_conflicting_duplicate"][split] = conflict
        audit["final"][split] = {
            "rows": len(kept),
            "label_distribution": _label_distribution(kept),
            "membership_sha256": _membership_hash(kept),
            "source_row_indices_sha256": hashlib.sha256(
                json.dumps(sorted(row.source_row_index for row in kept)).encode("ascii")
            ).hexdigest(),
        }
    if not filtered["train"] or not filtered["dev"]:
        raise SunPredecessorError("filtered train/dev splits must be non-empty")
    return {
        "train": [row.__dict__ for row in filtered["train"]],
        "dev": [row.__dict__ for row in filtered["dev"]],
        "official_test": [row.__dict__ for row in filtered["test"]],
        "audit": audit,
    }


def _read_source_rows(source_zip: Path, wanted: set[int]) -> tuple[dict[int, list[float]], dict[int, str]]:
    """Stream the official CSV and parse only the requested data rows."""
    if not source_zip.is_file():
        raise SunPredecessorError(f"official source ZIP is unavailable: {source_zip}")
    vectors: dict[int, list[float]] = {}
    found_texts: dict[int, str] = {}
    csv.field_size_limit(sys.maxsize)
    with zipfile.ZipFile(source_zip) as archive:
        try:
            member = archive.open(CSV_MEMBER)
        except KeyError as exc:
            raise SunPredecessorError(f"missing {CSV_MEMBER} in official ZIP") from exc
        with member, io.TextIOWrapper(member, encoding="utf-8", newline="") as text_stream:
            reader = csv.reader(text_stream)
            for row_index, row in enumerate(reader):
                if row_index not in wanted:
                    continue
                if len(row) <= CSV_VECTOR_COLUMN:
                    raise SunPredecessorError(f"official CSV row {row_index} is too short")
                text = row[CSV_TEXT_COLUMN]
                raw_vector = row[CSV_VECTOR_COLUMN].strip()
                if raw_vector.startswith("[") and raw_vector.endswith("]"):
                    raw_vector = raw_vector[1:-1]
                values = [value for value in re.split(r"[,\s]+", raw_vector) if value]
                if len(values) % VECTOR_DIMENSION:
                    raise SunPredecessorError(
                        f"official CSV row {row_index} vector length is not divisible by {VECTOR_DIMENSION}"
                    )
                if len(values) != VECTOR_DIMENSION * len(tokenize_words(text)):
                    raise SunPredecessorError(
                        f"official CSV row {row_index} vector/token count mismatch"
                    )
                try:
                    parsed = [float(value) for value in values]
                except ValueError as exc:
                    raise SunPredecessorError(
                        f"official CSV row {row_index} has a non-numeric vector value"
                    ) from exc
                if not all(isinstance(value, numbers.Real) and np.isfinite(value) for value in parsed):
                    raise SunPredecessorError(f"official CSV row {row_index} has a non-finite vector value")
                vectors[row_index] = parsed
                found_texts[row_index] = text
                if len(vectors) == len(wanted):
                    break
    missing = sorted(wanted - set(vectors))
    if missing:
        raise SunPredecessorError(f"official CSV rows missing for indices: {missing[:8]}")
    return vectors, found_texts


def build_embedding_cache(
    formal_root: Path,
    external_root: Path,
    cache_dir: Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Build or load a train-only vocabulary/embedding cache.

    The cache stores no sentence text.  It contains one token list and one
    float32 matrix derived from the official vectors.
    """
    formal_root = Path(formal_root)
    external_root = Path(external_root)
    splits = build_clean_splits(formal_root, external_root)
    train = splits["train"]
    wanted = {int(row["source_row_index"]) for row in train}
    source_zip = external_root / OFFICIAL_SOURCE_ZIP_REL
    source_hash = sha256_file(source_zip)
    membership_hash = splits["audit"]["final"]["train"]["membership_sha256"]
    cache_key = hashlib.sha256(
        json.dumps(
            {"source_zip_sha256": source_hash, "train_membership_sha256": membership_hash},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    cache_dir = Path(cache_dir)
    meta_path = cache_dir / f"embeddings_{cache_key}.json"
    npz_path = cache_dir / f"embeddings_{cache_key}.npz"
    if not force and meta_path.is_file() and npz_path.is_file():
        metadata = load_json(meta_path)
        if metadata.get("schema_version") == CACHE_SCHEMA and metadata.get(
            "source_zip_sha256"
        ) == source_hash and metadata.get("train_membership_sha256") == membership_hash:
            metadata_vocab = metadata.get("vocab")
            if not isinstance(metadata_vocab, list) or not metadata_vocab:
                raise SunPredecessorError("embedding cache metadata has no vocabulary")
            arrays = np.load(npz_path, allow_pickle=False)
            return {
                "vocab": [str(value) for value in metadata_vocab],
                "matrix": np.asarray(arrays["matrix"], dtype=np.float32),
                "metadata": metadata,
                "cache_path": str(npz_path),
            }
    vectors_by_row, texts_by_row = _read_source_rows(source_zip, wanted)
    token_to_sum: dict[str, np.ndarray] = {}
    token_to_count: dict[str, int] = defaultdict(int)
    vector_sum = np.zeros(VECTOR_DIMENSION, dtype=np.float64)
    vector_count = 0
    for row in train:
        source_index = int(row["source_row_index"])
        row_text = str(row["text"])
        if normalize_for_match(texts_by_row[source_index]) != normalize_for_match(row_text):
            raise SunPredecessorError(
                f"official source row {source_index} text does not match the imported split"
            )
        row_vectors = np.asarray(vectors_by_row[source_index], dtype=np.float32).reshape(-1, VECTOR_DIMENSION)
        tokens = tokenize_words(row_text)
        if len(tokens) != len(row_vectors):
            raise SunPredecessorError("cached official split text/vector alignment drifted")
        for token, vector in zip(tokens, row_vectors, strict=True):
            if token not in token_to_sum:
                token_to_sum[token] = np.zeros(VECTOR_DIMENSION, dtype=np.float64)
            token_to_sum[token] += vector
            token_to_count[token] += 1
            vector_sum += vector
            vector_count += 1
    if not token_to_sum:
        raise SunPredecessorError("no official train vectors were parsed")
    mean_vector = vector_sum / max(vector_count, 1)
    vocab = ["<pad>", "<unk>"]
    rows_matrix = [np.zeros(VECTOR_DIMENSION, dtype=np.float32), mean_vector.astype(np.float32)]
    for token in sorted(token_to_sum):
        vocab.append(token)
        rows_matrix.append((token_to_sum[token] / token_to_count[token]).astype(np.float32))
    matrix = np.vstack(rows_matrix).astype(np.float32)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz_path, matrix=matrix)
    metadata = {
        "schema_version": CACHE_SCHEMA,
        "source_zip": OFFICIAL_SOURCE_ZIP_REL,
        "source_zip_sha256": source_hash,
        "train_membership_sha256": membership_hash,
        "train_rows": len(train),
        "vocab": vocab,
        "vocab_size": len(vocab),
        "embedding_dimension": VECTOR_DIMENSION,
        "mean_vector_norm": float(np.linalg.norm(mean_vector)),
        "contains_raw_text": False,
        "local_only_do_not_commit": True,
        "split_audit": splits["audit"],
    }
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "vocab": vocab,
        "matrix": matrix,
        "metadata": metadata,
        "cache_path": str(npz_path),
        "splits": splits,
    }
# -*- coding: utf-8 -*-
"""Deterministic TF-IDF + SVD dense representation (S3.6-B graph baseline).

word + character n-gram TF-IDF over the unlabeled rule texts and process
labels, then a fixed-seed truncated SVD to a fixed dimension (numpy only).
Similarity between two texts is cosine in the dense space, [0, 1] after
clipping. The representation is fit ONLY on unlabeled rule text and process
labels (no Gold, no decisions). Honest naming: this is a TF-IDF/SVD dense
baseline, NOT a pretrained transformer embedding.

Empty inputs: empty text -> zero vector -> cosine 0.0.
"""

from __future__ import annotations

import re
import string

import numpy as np

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = frozenset(string.punctuation)


def _word_ngrams(text: str, n: int = 1) -> list[str]:
    words = _WORD_RE.findall(text.lower())
    return [" ".join(words[i:i + n]) for i in range(max(0, len(words) - n + 1))]


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    cleaned = re.sub(r"\s+", "", text.lower())
    return [cleaned[i:i + n] for i in range(max(0, len(cleaned) - n + 1))]


class TfidfSvd:
    def __init__(self, seed: int = 20260808, dim: int = 64,
                 word_ngram: int = 1, char_ngram: int = 3,
                 sublinear_tf: bool = True):
        self.seed = seed
        self.dim = dim
        self.word_ngram = word_ngram
        self.char_ngram = char_ngram
        self.sublinear_tf = sublinear_tf
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.svd_vt: np.ndarray | None = None
        self.svd_s: np.ndarray | None = None
        self.n_docs = 0

    def _features(self, text: str) -> list[str]:
        return _word_ngrams(text, self.word_ngram) + _char_ngrams(text, self.char_ngram)

    def fit(self, corpus: list[str]) -> "TfidfSvd":
        """Fit on unlabeled texts only (rule texts + process labels)."""
        docs = [self._features(t) for t in corpus]
        self.n_docs = len(docs)
        df: dict[str, int] = {}
        for feats in docs:
            for f in set(feats):
                df[f] = df.get(f, 0) + 1
        self.vocab = {f: i for i, f in enumerate(sorted(df))}
        self.idf = {f: math_log(1 + self.n_docs / (df[f] + 1e-9)) for f in df}
        matrix = np.zeros((self.n_docs, len(self.vocab)), dtype=np.float64)
        for row, feats in enumerate(docs):
            counts = {}
            for f in feats:
                counts[f] = counts.get(f, 0) + 1
            for f, c in counts.items():
                tf = 1 + math_log(c) if self.sublinear_tf else float(c)
                matrix[row, self.vocab[f]] = tf * self.idf[f]
        # deterministic truncated SVD: keep the first k right singular
        # vectors V (rows of vt), so x @ V.T projects a vocab vector into
        # the k-dimensional dense space
        u, s, vt = np.linalg.svd(matrix, full_matrices=False)
        k = min(self.dim, vt.shape[0])
        self.svd_vt = vt[:k]
        self.svd_s = s[:k]
        return self

    def _vector(self, text: str) -> np.ndarray:
        if self.svd_vt is None:
            raise RuntimeError("TfidfSvd must be fit first")
        feats = self._features(text)
        counts = {}
        for f in feats:
            counts[f] = counts.get(f, 0) + 1
        row = np.zeros(len(self.vocab), dtype=np.float64)
        for f, c in counts.items():
            if f not in self.vocab:
                continue
            tf = 1 + math_log(c) if self.sublinear_tf else float(c)
            row[self.vocab[f]] = tf * self.idf[f]
        dense = row @ self.svd_vt.T  # (vocab,) @ (vocab, k) -> (k,)
        return dense

    def similarity(self, a: str, b: str) -> float:
        va, vb = self._vector(a), self._vector(b)
        na, nb = np.linalg.norm(va), np.linalg.norm(vb)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.clip(np.dot(va, vb) / (na * nb), 0.0, 1.0))


def math_log(x: float) -> float:
    import math
    return math.log(x) if x > 0 else 0.0

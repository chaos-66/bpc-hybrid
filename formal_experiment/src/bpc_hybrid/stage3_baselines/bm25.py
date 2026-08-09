# -*- coding: utf-8 -*-
"""Deterministic BM25 lexical retrieval (S3.6-A lower bound).

Pure-Python BM25 (Okapi) with fixed k1/b; no sklearn dependency. Documents
are the process action labels of a model; queries are rule action/actor
texts. Scores are normalized by the maximum possible score for the query
(all query terms in one document), so the result lies in [0, 1] and a fixed
pre-registered threshold is meaningful. Empty queries and empty corpora have
explicit semantics (score 0.0, no match).

All parameters live in the versioned baseline config; nothing is tuned on
the 58-item Gold.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (deterministic, no stopword removal:
    this is the lexical lower bound and must not hide term overlap)."""
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = [tokenize(d) for d in documents]
        self.doc_freqs: list[Counter] = [Counter(t) for t in self.doc_tokens]
        self.doc_lens = [sum(c.values()) for c in self.doc_freqs]
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0.0
        self.n_docs = len(self.documents() if False else self.doc_tokens)
        self.df: Counter[str] = Counter()
        for freq in self.doc_freqs:
            for term in freq:
                self.df[term] += 1

    def documents(self) -> list[str]:
        return [d for d in self.doc_tokens]  # placeholder kept for clarity

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5))

    def score_doc(self, query_terms: list[str], doc_idx: int) -> float:
        freq = self.doc_freqs[doc_idx]
        dl = self.doc_lens[doc_idx]
        score = 0.0
        for term in query_terms:
            tf = freq.get(term, 0)
            if tf == 0:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl else tf + self.k1
            score += self.idf(term) * tf * (self.k1 + 1) / denom
        return score

    def max_possible(self, query_terms: list[str]) -> float:
        """Maximum score if every query term occurred in one document of
        average length (normalization base; never zero when terms exist)."""
        if not query_terms:
            return 0.0
        return sum(self.idf(t) * (self.k1 + 1) / (1 + self.k1 * (1 - self.b + self.b * self.avgdl / self.avgdl))
                   if self.avgdl else self.idf(t) * (self.k1 + 1) / (self.k1 + 1)
                   for t in set(query_terms))

    def query(self, query: str) -> tuple[float, str | None]:
        """Normalized best-document score in [0,1] plus the best document
        (or None for an empty query/corpus)."""
        terms = tokenize(query)
        if not terms or not self.doc_tokens:
            return 0.0, None
        best = 0.0
        best_idx = None
        for idx in range(self.n_docs):
            s = self.score_doc(terms, idx)
            if s > best:
                best = s
                best_idx = idx
        base = self.max_possible(terms)
        normalized = best / base if base > 0 else 0.0
        return normalized, (best_idx if best_idx is not None else None)

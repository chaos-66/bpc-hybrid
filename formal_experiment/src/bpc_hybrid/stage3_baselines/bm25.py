# -*- coding: utf-8 -*-
"""Deterministic candidate-specific BM25 lexical similarity (S3.6-A v3).

Corrects the v1/v2 defect: the old ``sim(a, b)`` ignored ``b`` and returned
the best-document score of the whole action corpus for every candidate, so
``_best_action`` always picked the first action and actor/business-object
comparisons actually queried the action corpus.

This version provides a true candidate-specific API:

- ``score(query, candidate_text)`` computes the BM25 score of the CANDIDATE
  document for the query, with IDF and length statistics taken from the
  candidate pool (action corpus or actor/business-object corpus); ``b``
  genuinely affects the length normalisation;
- the score is normalized to [0,1] by the per-term upper bound
  ``sum(IDF(t)*(k1+1))`` over the unique query terms, which is a real bound
  for every term contribution ``IDF*tf*(k1+1)/(tf + k1*(1-b+b*dl/avgdl))``
  (the fraction is < 1 for all tf/dl >= 0); repeated query tokens are
  collapsed for the bound, empty query/corpus yields 0.0;
- best-match and ID resolution live in the caller (BaselineScorer iterates
  the model's actions and keeps the action id with the candidate label), so
  duplicate labels resolve deterministically (score desc, first-seen order)
  and out-of-order endpoints map to the true action id.

Retrieval domains (action corpus vs actor/business-object corpus) are
declared in the versioned config (``retrieval_domains``).
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase alphanumeric tokens (no stopword removal: lexical lower bound)."""
    return _TOKEN_RE.findall(text.lower())


class BM25Index:
    """BM25 over a candidate document pool. ``score(query, candidate)`` is
    candidate-specific: the candidate's own term frequencies and length are
    used, IDF/length statistics come from the pool."""

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = [tokenize(d) for d in documents]
        self.doc_freqs: list[Counter] = [Counter(t) for t in self.doc_tokens]
        self.doc_lens = [sum(c.values()) for c in self.doc_freqs]
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0.0
        self.n_docs = len(self.doc_tokens)
        self.df: Counter[str] = Counter()
        for freq in self.doc_freqs:
            for term in freq:
                self.df[term] += 1

    def idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.n_docs - n + 0.5) / (n + 0.5))

    def _term_score(self, term: str, tf: int, dl: int) -> float:
        """Raw BM25 contribution of one term in the candidate document."""
        denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl) if self.avgdl else tf + self.k1
        return self.idf(term) * tf * (self.k1 + 1) / denom

    def score(self, query: str, candidate: str) -> float:
        """Candidate-specific BM25 score in [0, 1]. The candidate text may or
        may not be part of the pool; its tf/dl are its own, IDF/avgdl come
        from the pool. Returns 0.0 for an empty query, an empty candidate, or
        an empty pool (explicit semantics, never silently positive)."""
        q_terms = tokenize(query)
        if not q_terms or not candidate.strip() or not self.doc_tokens:
            return 0.0
        c_tokens = tokenize(candidate)
        if not c_tokens:
            return 0.0
        c_counts = Counter(c_tokens)
        dl = sum(c_counts.values())
        unique_terms = set(q_terms)
        upper = sum(self.idf(t) * (self.k1 + 1) for t in unique_terms)
        if upper <= 0:
            return 0.0
        total = 0.0
        for term in unique_terms:
            tf = c_counts.get(term, 0)
            if tf == 0:
                continue
            total += self._term_score(term, tf, dl)
        return min(1.0, total / upper)

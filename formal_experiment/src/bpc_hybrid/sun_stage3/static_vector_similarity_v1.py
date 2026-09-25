# -*- coding: utf-8 -*-
"""M2 static-word-vector similarity backend.

The parser and lemma remain the frozen ``en_core_web_sm`` pipeline.  The
``en_core_web_lg`` model is used only as a static vector table.  For a
normalized text, every non-punctuation/non-space token contributes its lemma
vector (falling back to its lower-case surface form only for vector lookup,
never to sm/dictionary similarity).  The mean vector is compared with cosine
similarity and clipped to [0, 1].  No valid vector or a zero norm returns a
fixed non-match with unavailable evidence.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def directory_sha256(path: Path, *, skip_names: set[str] | None = None) -> str:
    skip_names = skip_names or {"__init__.py"}
    total = hashlib.sha256()
    root = Path(path)
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.name in skip_names:
            continue
        rel = file.relative_to(root).as_posix()
        total.update(rel.encode("utf-8"))
        total.update(b"\0")
        total.update(file.read_bytes())
        total.update(b"\0")
    return total.hexdigest()


class StaticVectorSimilarity:
    def __init__(self, nlp_parser: Any, nlp_vectors: Any, *,
                 model_path: str | None = None,
                 model_version: str | None = None,
                 resource_sha256: str | None = None):
        self.nlp_parser = nlp_parser
        self.nlp_vectors = nlp_vectors
        self.model_path = model_path
        self.model_version = model_version or str(getattr(nlp_vectors, "meta", {}).get("version", ""))
        self.resource_sha256 = resource_sha256
        vocab = getattr(nlp_vectors, "vocab", None)
        self.vector_dimension = int(
            getattr(nlp_vectors, "vector_size", None)
            or getattr(vocab, "vectors_length", 0)
            or 0
        )
        self._cache: dict[str, dict[str, Any]] = {}

    def _token_lookup(self, token: Any) -> tuple[Any | None, str | None, int]:
        candidates: list[str] = []
        lemma = str(getattr(token, "lemma_", "") or "").strip().lower()
        lower = str(getattr(token, "lower_", "") or "").strip().lower()
        if lemma:
            candidates.append(lemma)
        if lower and lower not in candidates:
            candidates.append(lower)
        for key in candidates:
            try:
                lex = self.nlp_vectors.vocab[key]
            except Exception:
                continue
            if lex is None or not getattr(lex, "has_vector", False):
                continue
            vector = getattr(lex, "vector", None)
            if vector is None:
                continue
            norm = float((vector @ vector) ** 0.5)
            if norm <= 0.0:
                continue
            return vector, key, len(candidates)
        return None, None, len(candidates)

    def _encode(self, text: str) -> dict[str, Any]:
        cached = self._cache.get(text)
        if cached is not None:
            return cached
        doc = self.nlp_parser(text)
        tokens = [t for t in doc if not t.is_punct and not t.is_space]
        vectors: list[Any] = []
        keys: list[str] = []
        details: list[dict[str, Any]] = []
        for token in tokens:
            vector, key, candidate_count = self._token_lookup(token)
            if vector is not None:
                vectors.append(vector)
                keys.append(str(key))
            details.append({
                "token": token.text,
                "lemma": token.lemma_,
                "lookup_key": key,
                "has_valid_vector": vector is not None,
                "lookup_candidate_count": candidate_count,
            })
        coverage = (len(vectors) / len(tokens)) if tokens else 0.0
        if not vectors:
            result = {
                "available": False,
                "reason": "no_static_vectors_for_any_token" if tokens else "empty_text",
                "token_count": len(tokens),
                "vector_token_count": 0,
                "coverage": coverage,
                "dimension": self.vector_dimension,
                "mean_vector_norm": 0.0,
                "token_details": details,
                "keys": keys,
            }
            self._cache[text] = result
            return result
        mean = vectors[0]
        for vector in vectors[1:]:
            mean = mean + vector
        mean = mean / float(len(vectors))
        norm = float((mean @ mean) ** 0.5)
        if norm <= 0.0:
            result = {
                "available": False,
                "reason": "zero_norm_mean_vector",
                "token_count": len(tokens),
                "vector_token_count": len(vectors),
                "coverage": coverage,
                "dimension": self.vector_dimension,
                "mean_vector_norm": 0.0,
                "token_details": details,
                "keys": keys,
            }
            self._cache[text] = result
            return result
        result = {
            "available": True,
            "reason": None,
            "token_count": len(tokens),
            "vector_token_count": len(vectors),
            "coverage": coverage,
            "dimension": self.vector_dimension,
            "mean_vector_norm": norm,
            "mean_vector": mean,
            "token_details": details,
            "keys": keys,
        }
        self._cache[text] = result
        return result

    def similarity_with_evidence(self, left: str, right: str) -> dict[str, Any]:
        left_enc = self._encode(left)
        right_enc = self._encode(right)
        evidence: dict[str, Any] = {
            "backend": "en_core_web_lg_static_vector_mean_cosine@1.0.0",
            "model_path": self.model_path,
            "model_version": self.model_version,
            "resource_sha256": self.resource_sha256,
            "left_text": left,
            "right_text": right,
            "left_available": left_enc.get("available"),
            "right_available": right_enc.get("available"),
            "left_coverage": left_enc.get("coverage"),
            "right_coverage": right_enc.get("coverage"),
            "left_vector_token_count": left_enc.get("vector_token_count"),
            "right_vector_token_count": right_enc.get("vector_token_count"),
            "left_token_count": left_enc.get("token_count"),
            "right_token_count": right_enc.get("token_count"),
            "dimension": left_enc.get("dimension") or right_enc.get("dimension"),
            "left_mean_vector_norm": left_enc.get("mean_vector_norm"),
            "right_mean_vector_norm": right_enc.get("mean_vector_norm"),
            "left_reason": left_enc.get("reason"),
            "right_reason": right_enc.get("reason"),
            "score": 0.0,
            "raw_cosine": None,
            "available": False,
            "reason": None,
        }
        if not left_enc.get("available") or not right_enc.get("available"):
            evidence["reason"] = "one_or_both_texts_have_no_valid_static_vectors"
            return evidence
        left_vec = left_enc["mean_vector"]
        right_vec = right_enc["mean_vector"]
        denom = float(left_enc["mean_vector_norm"]) * float(right_enc["mean_vector_norm"])
        if denom <= 0.0:
            evidence["reason"] = "zero_norm_denominator"
            return evidence
        raw = float((left_vec @ right_vec) / denom)
        clipped = max(0.0, min(1.0, raw))
        evidence.update({
            "raw_cosine": raw,
            "score": clipped,
            "available": True,
            "reason": None,
        })
        return evidence

    def text_pair(self, left: str, right: str) -> float:
        evidence = self.similarity_with_evidence(left, right)
        return float(evidence.get("score") or 0.0)


__all__ = ["StaticVectorSimilarity", "directory_sha256"]

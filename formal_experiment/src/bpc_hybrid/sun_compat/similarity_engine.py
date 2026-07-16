"""SimilarityEngine: development approximation for Stage 3 (Wave 1.1 §7).

The current engine is a **spaCy-vector-based similarity approximation
** intended as a development scaffold. It is not a replication of
Sun's SimilarityComputer because:

  * Sun's SimilarityComputer combines spaCy vectors, gamma/delta
    thresholds, and an obligation cost / resource cost / order cost
    model. The current engine implements only the vector similarity
    primitive + threshold-based matching.
  * The threshold ``gamma=0.4`` and ``delta=0.8`` are heuristic
    starting values, not Sun's calibrated values.
  * The cache mirrors the structure of Sun's ``spacy_simcache`` but
    the key derivation and persistence format are not byte-identical.

When the paper-faithful Stage 3 is implemented, this module must be
extended with the obligation cost / resource cost / order cost
calculations and the gamma/delta calibration. Until then, this
file must NOT be advertised as replicating Sun's SimilarityComputer.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

try:
    import spacy
    from spacy.tokens import Doc
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


class SimilarityEngine:
    """spaCy vector similarity engine for obligation matching.

    Usage::

        >>> engine = SimilarityEngine()
        >>> score = engine.similarity("controller notify authority", ["notify", "national", "authority"])
        >>> print(score)  # 0.85 (example)
        >>> matched = engine.is_match("controller notify authority", ["notify", "national", "authority"], threshold=0.4)
        >>> print(matched)  # True
    """

    def __init__(
        self,
        nlp: Any | None = None,
        model_name: str = "en_core_web_md",
        cache_path: str | Path | None = None,
    ) -> None:
        if not SPACY_AVAILABLE:
            raise ImportError("spaCy is required for SimilarityEngine")
        self._nlp = nlp or spacy.load(model_name)
        self._cache: dict[str, float] = {}
        self._cache_path = Path(cache_path) if cache_path else None
        if self._cache_path and self._cache_path.exists():
            self._load_cache()

    def similarity(
        self,
        text_obligation: str,
        model_obligation: list[str],
    ) -> float:
        """Compute cosine similarity between text obligation and model obligation.

        Args:
            text_obligation: Lemmatized bag-of-words string from regulation
                (e.g., "controller notify authority")
            model_obligation: Lemmatized token list from BPMN task label
                (e.g., ["notify", "national", "authority"])

        Returns:
            Cosine similarity score in [0.0, 1.0]. Returns 0.0 if either
            input has no vector.
        """
        # Check cache
        cache_key = self._make_cache_key(text_obligation, model_obligation)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Compute similarity
        model_str = " ".join(model_obligation)
        doc1 = self._nlp(text_obligation)
        doc2 = self._nlp(model_str)

        # Check if vectors are available
        if not doc1.has_vector or not doc2.has_vector:
            self._cache[cache_key] = 0.0
            return 0.0

        sim_val = doc1.similarity(doc2)

        # Clamp to [0, 1]
        sim_val = max(0.0, min(1.0, sim_val))

        # Cache
        self._cache[cache_key] = sim_val
        return sim_val

    def is_match(
        self,
        text_obligation: str,
        model_obligation: list[str],
        threshold: float = 0.4,
    ) -> bool:
        """Check if text obligation matches model obligation above threshold.

        Args:
            text_obligation: Lemmatized bag-of-words string from regulation.
            model_obligation: Lemmatized token list from BPMN task label.
            threshold: Similarity threshold (default 0.4, same as Sun's gamma).

        Returns:
            True if similarity > threshold.
        """
        return self.similarity(text_obligation, model_obligation) > threshold

    def find_best_match(
        self,
        text_obligation: str,
        model_obligations: dict[str, list[list[str]]],
        threshold: float = 0.4,
        require_overlap: bool = True,
    ) -> tuple[str, list[str], float] | None:
        """Find the best matching model obligation for a text obligation.

        Replicates Sun's Pair._max_text_obligation_to_model().

        Args:
            text_obligation: Lemmatized bag-of-words string from regulation.
            model_obligations: Dict of participant → list of lemmatized token lists.
                (e.g., {"Data Controller": [["notify", "authority"], ["report", "breach"]]})
            threshold: Minimum similarity threshold.
            require_overlap: If True, require meaningful token overlap (default).
                Set to False for short segments (order relation matching).

        Returns:
            Tuple of (participant, model_obligation_tokens, similarity_score),
            or None if no match above threshold.
        """
        best_participant = None
        best_obligation = None
        best_score = 0.0

        text_tokens = set(text_obligation.lower().split())

        for participant, obligations in model_obligations.items():
            for obligation in obligations:
                if require_overlap:
                    # Require meaningful token overlap to avoid false positives
                    # from spaCy's high baseline similarity for unrelated texts.
                    # 0.7 ratio ensures shared nouns (e.g. "data breach") alone
                    # aren't enough — the action verb must also overlap.
                    model_tokens = set(t.lower() for t in obligation)
                    shared = text_tokens & model_tokens
                    min_overlap = max(2, min(len(text_tokens), len(model_tokens)) * 0.7)
                    if len(shared) < min_overlap:
                        continue  # Insufficient token overlap, skip

                score = self.similarity(text_obligation, obligation)
                if score > best_score:
                    best_score = score
                    best_participant = participant
                    best_obligation = obligation

        if best_score > threshold and best_participant is not None:
            return (best_participant, best_obligation, best_score)
        return None

    def compute_fitness_score(
        self,
        text_obligations: list[str],
        model_obligations: dict[str, list[list[str]]],
        threshold: float = 0.4,
    ) -> float:
        """Compute fitness score (like Sun's Pair.fitness_score()).

        Fitness = average similarity of matched obligations / total obligations.

        Args:
            text_obligations: List of lemmatized bag-of-words strings.
            model_obligations: Dict of participant → list of lemmatized token lists.
            threshold: Similarity threshold (gamma).

        Returns:
            Fitness score in [0.0, 1.0].
        """
        if not text_obligations:
            return 0.0

        sum_scores = 0.0
        count_matched = 0

        for text_obl in text_obligations:
            match = self.find_best_match(text_obl, model_obligations, threshold)
            if match is not None:
                sum_scores += match[2]  # similarity score
                count_matched += 1

        if count_matched == 0:
            return 0.0

        return sum_scores / count_matched

    def compute_obligation_cost(
        self,
        text_obligations: list[str],
        model_obligations: dict[str, list[list[str]]],
        threshold: float = 0.4,
    ) -> float:
        """Compute obligation cost (like Sun's Pair.cost_obligation()).

        Obligation cost = fraction of text obligations that don't match any model obligation.

        Args:
            text_obligations: List of lemmatized bag-of-words strings.
            model_obligations: Dict of participant → list of lemmatized token lists.
            threshold: Similarity threshold (gamma).

        Returns:
            Obligation cost in [0.0, 1.0].
        """
        if not text_obligations:
            return 0.0

        violations = 0
        for text_obl in text_obligations:
            match = self.find_best_match(text_obl, model_obligations, threshold)
            if match is None:
                violations += 1

        return violations / len(text_obligations)

    def compute_resource_cost(
        self,
        text_obligations: list[str],
        text_actors: list[str],
        model_obligations: dict[str, list[list[str]]],
        threshold: float = 0.4,
        resource_threshold: float = 0.8,
    ) -> float:
        """Compute resource cost (like Sun's Pair.cost_resource()).

        Resource cost = fraction of obligations where actor doesn't match the
        BPMN participant (lane) that handles the matched model obligation.

        Args:
            text_obligations: List of lemmatized bag-of-words strings.
            text_actors: List of actor strings (parallel to text_obligations).
            model_obligations: Dict of participant → list of lemmatized token lists.
            threshold: Similarity threshold for obligation matching.
            resource_threshold: Similarity threshold for resource matching.

        Returns:
            Resource cost in [0.0, 1.0].
        """
        if not text_obligations:
            return 0.0

        violations = 0
        for i, text_obl in enumerate(text_obligations):
            match = self.find_best_match(text_obl, model_obligations, threshold)
            if match is None:
                continue

            participant = match[0]
            actor = text_actors[i] if i < len(text_actors) else ""

            if actor:
                # Combined check: substring match OR spaCy similarity
                actor_lower = actor.lower().strip()
                participant_lower = participant.lower().strip()

                # Substring match: "controller" in "Data Controller" => match
                is_substring = (
                    actor_lower in participant_lower
                    or participant_lower in actor_lower
                )

                if not is_substring:
                    # Fall back to spaCy similarity
                    actor_doc = self._nlp(actor_lower)
                    participant_doc = self._nlp(participant_lower)
                    if actor_doc.has_vector and participant_doc.has_vector:
                        resource_sim = actor_doc.similarity(participant_doc)
                        if resource_sim < resource_threshold:
                            violations += 1

        return violations / len(text_obligations)

    def save_cache(self) -> None:
        """Save similarity cache to disk."""
        if self._cache_path:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f)

    def _load_cache(self) -> None:
        """Load similarity cache from disk."""
        if self._cache_path and self._cache_path.exists():
            with open(self._cache_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)

    def _make_cache_key(
        self, text_obligation: str, model_obligation: list[str]
    ) -> str:
        """Create cache key for similarity computation."""
        model_str = " ".join(model_obligation)
        raw = f"{text_obligation}___{model_str}"
        return hashlib.md5(raw.encode()).hexdigest()

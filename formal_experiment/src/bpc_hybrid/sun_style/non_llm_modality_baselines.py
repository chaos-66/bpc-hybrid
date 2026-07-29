"""Pure-standard-library S2.7-M non-LLM modality baselines.

The module implements three fixed comparators on the locked S2.1 reconstructed
split: train-majority, a transparent German keyword rule, and word 1--2 gram
Multinomial Naive Bayes.  It returns aggregate metrics only and never persists
row-level predictions or source text.
"""

from __future__ import annotations

import collections
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


CONFIG_SCHEMA = "s27_non_llm_baselines@1.0.0"


class NonLLMBaselineError(ValueError):
    """Raised when the frozen S2.7-M baseline contract is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NonLLMBaselineError(f"invalid S2.7-M config: {path}") from exc
    if not isinstance(config, dict):
        raise NonLLMBaselineError("S2.7-M config root must be an object")
    if config.get("schema_version") != CONFIG_SCHEMA or config.get("task_id") != "S2.7-M":
        raise NonLLMBaselineError("S2.7-M config identity mismatch")
    labels = config.get("labels")
    if labels != ["definition", "obligation", "permission", "prohibition"]:
        raise NonLLMBaselineError("S2.7-M label order changed")
    methods = config.get("methods", {})
    majority = methods.get("train_majority", {})
    keyword = methods.get("german_keyword", {})
    nb = methods.get("word_ngram_multinomial_nb", {})
    if majority.get("expected_train_majority") != "obligation":
        raise NonLLMBaselineError("S2.7-M expected train majority changed")
    if (
        keyword.get("precedence") != ["prohibition", "permission", "obligation", "definition"]
        or keyword.get("default") != "train_majority"
        or set(keyword.get("patterns", {})) != set(labels)
    ):
        raise NonLLMBaselineError("S2.7-M German keyword contract changed")
    if (
        nb.get("ngram_range") != [1, 2]
        or nb.get("min_document_frequency") != 2
        or nb.get("max_features") is not None
        or nb.get("likelihood_smoothing_alpha") != 1.0
        or nb.get("class_prior") != "empirical_with_add_one_smoothing"
        or nb.get("hyperparameter_search") is not False
        or nb.get("external_ml_dependency") is not False
    ):
        raise NonLLMBaselineError("S2.7-M Multinomial NB contract changed")
    disclosure = config.get("test_execution_disclosure", {})
    if (
        disclosure.get("development_smoke_accessed_test_labels_before_versioned_run") is not True
        or disclosure.get("hyperparameter_or_model_selection_on_test") is not False
        or disclosure.get("versioned_test_run_limit") != 1
        or disclosure.get("known_total_test_evaluations_after_versioned_run") != 2
    ):
        raise NonLLMBaselineError("S2.7-M test-access disclosure changed")
    if config.get("phrase_track", {}).get("status") != "blocked_pending_s2_2_human_phrase_gold":
        raise NonLLMBaselineError("S2.7-M phrase-track blocker changed")
    return config


def project_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(project_root) / path


def verify_locked_inputs(project_root: Path, config: Mapping[str, Any]) -> dict[str, str]:
    specs: dict[str, Mapping[str, Any]] = {
        "dataset_contract": config["dataset_binding"]["dataset_contract"],
        "dataset_manifest": config["dataset_binding"]["dataset_manifest"],
        "split_summary": config["dataset_binding"]["split_summary"],
        "local_research_use_decision": config["dataset_binding"]["local_research_use_decision"],
        **config["dataset_binding"]["splits"],
    }
    hashes: dict[str, str] = {}
    for name, spec in specs.items():
        path = project_path(project_root, spec["path"])
        if not path.is_file():
            raise NonLLMBaselineError(f"locked S2.7-M input is missing: {name}")
        actual = sha256_file(path)
        if actual != spec["sha256"]:
            raise NonLLMBaselineError(f"locked S2.7-M input hash mismatch: {name}")
        hashes[name] = actual
    return hashes


def load_split(path: Path, *, expected_count: int, labels: Sequence[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        with Path(path).open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise NonLLMBaselineError(f"split line {line_number} is not an object")
                sample_id = value.get("sample_id")
                text = value.get("text")
                label = value.get("label")
                if not isinstance(sample_id, str) or not sample_id:
                    raise NonLLMBaselineError(f"split line {line_number} has no sample_id")
                if sample_id in seen:
                    raise NonLLMBaselineError(f"duplicate split sample_id: {sample_id}")
                if not isinstance(text, str) or not text:
                    raise NonLLMBaselineError(f"split line {line_number} has no text")
                if label not in labels:
                    raise NonLLMBaselineError(f"split line {line_number} has unknown label")
                seen.add(sample_id)
                rows.append({"sample_id": sample_id, "text": text, "label": label})
    except NonLLMBaselineError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NonLLMBaselineError(f"invalid locked split: {path}") from exc
    if len(rows) != expected_count:
        raise NonLLMBaselineError(
            f"locked split count mismatch: expected {expected_count}, got {len(rows)}"
        )
    return rows


def _tokens(text: str) -> list[str]:
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)


def _features(text: str) -> list[str]:
    tokens = _tokens(text)
    return tokens + [f"{tokens[index]}__{tokens[index + 1]}" for index in range(len(tokens) - 1)]


def train_majority(rows: Sequence[Mapping[str, str]], labels: Sequence[str]) -> tuple[str, dict[str, int]]:
    counts = collections.Counter(row["label"] for row in rows)
    majority = max(labels, key=lambda label: (counts[label], -labels.index(label)))
    return majority, {label: counts[label] for label in labels}


def compile_keyword_patterns(config: Mapping[str, Any]) -> dict[str, tuple[re.Pattern[str], ...]]:
    result: dict[str, tuple[re.Pattern[str], ...]] = {}
    for label, patterns in config["methods"]["german_keyword"]["patterns"].items():
        try:
            result[label] = tuple(re.compile(pattern, flags=re.UNICODE) for pattern in patterns)
        except re.error as exc:
            raise NonLLMBaselineError(f"invalid keyword regex for {label}") from exc
    return result


def predict_keyword(
    text: str,
    *,
    patterns: Mapping[str, Sequence[re.Pattern[str]]],
    precedence: Sequence[str],
    default_label: str,
) -> str:
    normalized = text.casefold()
    for label in precedence:
        if any(pattern.search(normalized) for pattern in patterns[label]):
            return label
    return default_label


@dataclass
class MultinomialNBModel:
    labels: tuple[str, ...]
    vocabulary: frozenset[str]
    class_document_counts: dict[str, int]
    class_feature_counts: dict[str, collections.Counter[str]]
    class_feature_totals: dict[str, int]
    alpha: float = 1.0

    def predict(self, text: str) -> str:
        feature_counts = collections.Counter(
            feature for feature in _features(text) if feature in self.vocabulary
        )
        document_total = sum(self.class_document_counts.values())
        vocabulary_size = len(self.vocabulary)
        scores: dict[str, float] = {}
        for label in self.labels:
            prior = (self.class_document_counts[label] + 1) / (document_total + len(self.labels))
            denominator = self.class_feature_totals[label] + self.alpha * vocabulary_size
            score = math.log(prior)
            counts = self.class_feature_counts[label]
            for feature, frequency in feature_counts.items():
                score += frequency * math.log((counts[feature] + self.alpha) / denominator)
            scores[label] = score
        return max(self.labels, key=lambda label: (scores[label], -self.labels.index(label)))


def train_multinomial_nb(
    rows: Sequence[Mapping[str, str]],
    labels: Sequence[str],
    *,
    min_document_frequency: int = 2,
    alpha: float = 1.0,
) -> MultinomialNBModel:
    if min_document_frequency < 1 or alpha <= 0:
        raise NonLLMBaselineError("invalid Multinomial NB hyperparameters")
    document_frequency: collections.Counter[str] = collections.Counter()
    for row in rows:
        document_frequency.update(set(_features(row["text"])))
    vocabulary = frozenset(
        feature for feature, frequency in document_frequency.items()
        if frequency >= min_document_frequency
    )
    if not vocabulary:
        raise NonLLMBaselineError("Multinomial NB vocabulary is empty")
    class_documents = collections.Counter(row["label"] for row in rows)
    class_features = {label: collections.Counter() for label in labels}
    class_totals = collections.Counter()
    for row in rows:
        counts = collections.Counter(
            feature for feature in _features(row["text"]) if feature in vocabulary
        )
        class_features[row["label"]].update(counts)
        class_totals[row["label"]] += sum(counts.values())
    return MultinomialNBModel(
        labels=tuple(labels),
        vocabulary=vocabulary,
        class_document_counts={label: class_documents[label] for label in labels},
        class_feature_counts=class_features,
        class_feature_totals={label: class_totals[label] for label in labels},
        alpha=alpha,
    )


def evaluate(
    rows: Sequence[Mapping[str, str]],
    predictions: Iterable[str],
    labels: Sequence[str],
) -> dict[str, Any]:
    confusion = {gold: {predicted: 0 for predicted in labels} for gold in labels}
    count = 0
    correct = 0
    for row, predicted in zip(rows, predictions, strict=True):
        if predicted not in labels:
            raise NonLLMBaselineError(f"prediction has unknown label: {predicted}")
        gold = row["label"]
        confusion[gold][predicted] += 1
        count += 1
        correct += int(gold == predicted)
    if count != len(rows) or count == 0:
        raise NonLLMBaselineError("prediction count mismatch or empty evaluation")
    per_class: dict[str, Any] = {}
    macro_f1 = 0.0
    for label in labels:
        tp = confusion[label][label]
        fp = sum(confusion[other][label] for other in labels if other != label)
        fn = sum(confusion[label][other] for other in labels if other != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        support = sum(confusion[label].values())
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        macro_f1 += f1
    return {
        "sample_count": count,
        "accuracy": correct / count,
        "macro_f1": macro_f1 / len(labels),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def run_locked_baselines(project_root: Path, config: Mapping[str, Any]) -> dict[str, Any]:
    labels = tuple(config["labels"])
    hashes = verify_locked_inputs(project_root, config)
    splits: dict[str, list[dict[str, str]]] = {}
    for split_name, spec in config["dataset_binding"]["splits"].items():
        splits[split_name] = load_split(
            project_path(project_root, spec["path"]),
            expected_count=spec["count"],
            labels=labels,
        )
    all_ids = [row["sample_id"] for rows in splits.values() for row in rows]
    if len(all_ids) != len(set(all_ids)):
        raise NonLLMBaselineError("sample IDs overlap across train/dev/test")

    majority, train_counts = train_majority(splits["train"], labels)
    if majority != config["methods"]["train_majority"]["expected_train_majority"]:
        raise NonLLMBaselineError("observed train-majority class changed")
    patterns = compile_keyword_patterns(config)
    precedence = config["methods"]["german_keyword"]["precedence"]
    nb_config = config["methods"]["word_ngram_multinomial_nb"]
    nb = train_multinomial_nb(
        splits["train"],
        labels,
        min_document_frequency=nb_config["min_document_frequency"],
        alpha=nb_config["likelihood_smoothing_alpha"],
    )

    results: dict[str, Any] = {}
    for split_name in ("dev", "test"):
        rows = splits[split_name]
        results[split_name] = {
            "train_majority": evaluate(rows, (majority for _ in rows), labels),
            "german_keyword": evaluate(
                rows,
                (
                    predict_keyword(
                        row["text"],
                        patterns=patterns,
                        precedence=precedence,
                        default_label=majority,
                    )
                    for row in rows
                ),
                labels,
            ),
            "word_ngram_multinomial_nb": evaluate(
                rows, (nb.predict(row["text"]) for row in rows), labels
            ),
        }
    return {
        "input_hashes": hashes,
        "split_counts": {name: len(rows) for name, rows in splits.items()},
        "split_ids_disjoint": True,
        "train_class_counts": train_counts,
        "train_majority_label": majority,
        "nb_vocabulary_size": len(nb.vocabulary),
        "results": results,
        "row_level_predictions_persisted": False,
    }

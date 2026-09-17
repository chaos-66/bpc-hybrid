# -*- coding: utf-8 -*-
"""CF_KW: a deterministic keyword modality classifier reconstruction.

The published paper does not include the keyword list.  This module therefore
implements the minimum baseline it describes ("simply uses keywords to
determine the type of text") with an explicit, versioned rule list and an
ordered priority.  It never reads Gold and never learns from the EStG-150 test
records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from bpc_hybrid.sun_predecessors.common import load_json, SunPredecessorError


@dataclass(frozen=True)
class KeywordDecision:
    label: str
    matched_class: str
    matched_rule: str | None
    matched_surface: str | None


class KeywordRuleError(SunPredecessorError):
    """Raised when the keyword contract is malformed."""


class KeywordClassifier:
    """Ordered keyword rules with a deterministic fallback class."""

    def __init__(self, contract: Mapping[str, Any]) -> None:
        if contract.get("method_id") != "cf_kw":
            raise KeywordRuleError("CF_KW contract method_id mismatch")
        priority = contract.get("class_priority")
        rules = contract.get("rules")
        mapping = contract.get("class_to_evaluator_label")
        fallback = contract.get("fallback_label")
        if not isinstance(priority, list) or not all(isinstance(x, str) for x in priority):
            raise KeywordRuleError("class_priority must be a list of strings")
        if not isinstance(rules, Mapping) or not isinstance(mapping, Mapping):
            raise KeywordRuleError("rules and class_to_evaluator_label must be objects")
        if (not isinstance(fallback, str)) or fallback not in mapping or mapping[fallback] not in {
            "obligation", "permission", "prohibition", "definition"
        }:
            raise KeywordRuleError("fallback label is not a valid evaluator class")
        self.contract = dict(contract)
        self.priority = list(priority)
        self.mapping = {str(k): str(v) for k, v in mapping.items()}
        self.fallback = str(fallback)
        compiled: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        for class_name in priority:
            raw_patterns = rules.get(class_name)
            if not isinstance(raw_patterns, list) or not raw_patterns:
                raise KeywordRuleError(f"missing non-empty keyword list for {class_name!r}")
            entries: list[tuple[str, re.Pattern[str]]] = []
            for pattern in raw_patterns:
                if not isinstance(pattern, str) or not pattern:
                    raise KeywordRuleError(f"invalid pattern in {class_name!r}")
                try:
                    entries.append((pattern, re.compile(pattern, re.IGNORECASE)))
                except re.error as exc:
                    raise KeywordRuleError(f"invalid regex in {class_name!r}: {pattern!r}") from exc
            compiled[class_name] = entries
        self.compiled = compiled

    @classmethod
    def from_path(cls, path: Path) -> "KeywordClassifier":
        return cls(load_json(Path(path)))

    def classify(self, text: str) -> KeywordDecision:
        if not isinstance(text, str) or not text.strip():
            raise KeywordRuleError("keyword input text must be non-empty")
        for class_name in self.priority:
            for pattern, regex in self.compiled[class_name]:
                match = regex.search(text)
                if match is not None:
                    return KeywordDecision(
                        label=self.mapping[class_name],
                        matched_class=class_name,
                        matched_rule=pattern,
                        matched_surface=match.group(0),
                    )
        return KeywordDecision(
            label=self.mapping[self.fallback],
            matched_class=self.fallback,
            matched_rule=None,
            matched_surface=None,
        )

    def predict(self, texts: Sequence[str]) -> list[KeywordDecision]:
        return [self.classify(text) for text in texts]


def load_keyword_classifier(path: Path) -> KeywordClassifier:
    return KeywordClassifier.from_path(path)
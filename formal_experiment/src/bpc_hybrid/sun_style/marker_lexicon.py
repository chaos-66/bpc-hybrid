"""Domain-marked lexicon for Sun-style semantic extraction.

Loads and provides structured access to the bundled marker lexicon in
``resources/sun_marker_lexicon.json``.

All marker categories are ordered by priority (longest match first)
for greedy token-level matching.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar


# ---------------------------------------------------------------------------
# Marker category enums
# ---------------------------------------------------------------------------

class ModalityCategory(str, Enum):
    OBLIGATION = "obligation"
    PROHIBITION = "prohibition"
    PERMISSION = "permission"
    DEFINITION = "definition"


class ConditionCategory(str, Enum):
    CONDITION = "condition"


class ConstraintCategory(str, Enum):
    CONSTRAINT = "constraint"


class ExceptionCategory(str, Enum):
    EXCEPTION = "exception"


class ActorCategory(str, Enum):
    ACTOR = "actor"


# ---------------------------------------------------------------------------
# Marker lexicon
# ---------------------------------------------------------------------------


@dataclass
class MarkerLexicon:
    """Structured in-memory representation of the Sun-style marker lexicon.

    Loads from the canonical JSON file.  Markers are sorted by descending
    length so that greedy matching prefers longer (more specific) patterns.
    """

    modality_obligation: list[str] = field(default_factory=list)
    modality_prohibition: list[str] = field(default_factory=list)
    modality_permission: list[str] = field(default_factory=list)
    modality_definition: list[str] = field(default_factory=list)

    condition_markers: list[str] = field(default_factory=list)
    constraint_markers: list[str] = field(default_factory=list)
    exception_markers: list[str] = field(default_factory=list)
    actor_markers: list[str] = field(default_factory=list)

    # Compiled regex patterns (lazy)
    _modality_re: ClassVar[re.Pattern | None] = None
    _condition_re: ClassVar[re.Pattern | None] = None
    _constraint_re: ClassVar[re.Pattern | None] = None
    _exception_re: ClassVar[re.Pattern | None] = None

    _DEFAULT_PATH: ClassVar[Path] = (
        Path(__file__).resolve().parents[3]
        / "resources"
        / "sun_marker_lexicon.json"
    )

    @classmethod
    def from_default(cls) -> MarkerLexicon:
        """Load the lexicon from the canonical JSON file."""
        return cls.from_path(cls._DEFAULT_PATH)

    @classmethod
    def from_public_v1(cls) -> MarkerLexicon:
        """Load the locked S2.3 public-source English v1 resources.

        This is an explicit opt-in seam for later S2.5 work.  S2.3 does not
        silently replace the legacy development heuristic's default resource.
        """

        from bpc_hybrid.sun_style.public_marker_lexicon import (
            load_public_marker_entries,
        )

        entries = load_public_marker_entries()

        def surfaces(category: str) -> list[str]:
            return [str(item["surface"]) for item in entries[category]]

        modality = entries["modality"]
        return cls(
            modality_obligation=[
                str(item["surface"])
                for item in modality
                if item.get("modality_class") == "obligation"
            ],
            modality_prohibition=[
                str(item["surface"])
                for item in modality
                if item.get("modality_class") == "prohibition"
            ],
            modality_permission=[
                str(item["surface"])
                for item in modality
                if item.get("modality_class") == "permission"
            ],
            modality_definition=[
                str(item["surface"])
                for item in modality
                if item.get("modality_class") == "definition"
            ],
            condition_markers=surfaces("condition"),
            constraint_markers=surfaces("constraint"),
            exception_markers=surfaces("exception"),
            actor_markers=surfaces("actor"),
        )

    @classmethod
    def from_path(cls, path: Path) -> MarkerLexicon:
        """Load the lexicon from *path*."""
        data = json.loads(path.read_text(encoding="utf-8"))
        cats = data["categories"]

        def _sorted(entries: list[str]) -> list[str]:
            return sorted(entries, key=len, reverse=True)

        return cls(
            modality_obligation=_sorted(cats["modality"]["classifications"]["obligation"]),
            modality_prohibition=_sorted(cats["modality"]["classifications"]["prohibition"]),
            modality_permission=_sorted(cats["modality"]["classifications"]["permission"]),
            modality_definition=_sorted(cats["modality"]["classifications"]["definition"]),
            condition_markers=_sorted(cats["condition"]["markers"]),
            constraint_markers=_sorted(cats["constraint"]["markers"]),
            exception_markers=_sorted(cats["exception"]["markers"]),
            actor_markers=_sorted(cats["actor"]["markers"]),
        )

    # -- Lookup helpers ---------------------------------------------------

    def find_modality(self, text_lower: str) -> tuple[str, str] | None:
        """Return ``(marker_text, modality_category)`` or ``None``.

        Checks in priority order: prohibition, obligation, permission, definition.
        """
        for cat, markers in [
            ("prohibition", self.modality_prohibition),
            ("obligation", self.modality_obligation),
            ("permission", self.modality_permission),
            ("definition", self.modality_definition),
        ]:
            for m in markers:
                if self._find_first_marker(text_lower, m) is not None:
                    return (m, cat)
        return None

    def find_all_modalities(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, modality_category)`` marker positions."""
        results: list[tuple[int, int, str]] = []
        for cat, markers in [
            ("prohibition", self.modality_prohibition),
            ("obligation", self.modality_obligation),
            ("permission", self.modality_permission),
            ("definition", self.modality_definition),
        ]:
            for marker in markers:
                for start, end in self._find_all_marker_positions(text_lower, marker):
                    results.append((start, end, cat))
        results.sort(key=lambda x: x[0])
        return results

    def find_all_conditions(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, marker)`` positions of condition markers."""
        results: list[tuple[int, int, str]] = []
        for m in self.condition_markers:
            for start, end in self._find_all_marker_positions(text_lower, m):
                results.append((start, end, m))
        results.sort(key=lambda x: x[0])
        return results

    def find_all_constraints(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, marker)`` positions of constraint markers."""
        results: list[tuple[int, int, str]] = []
        for m in self.constraint_markers:
            for start, end in self._find_all_marker_positions(text_lower, m):
                results.append((start, end, m))
        results.sort(key=lambda x: x[0])
        return results

    def find_all_exceptions(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, marker)`` positions of exception markers."""
        results: list[tuple[int, int, str]] = []
        for m in self.exception_markers:
            for start, end in self._find_all_marker_positions(text_lower, m):
                results.append((start, end, m))
        results.sort(key=lambda x: x[0])
        return results

    def find_actor(self, text_lower: str) -> tuple[int, int, str] | None:
        """Return ``(start, end, marker)`` of the first actor marker found."""
        best: tuple[int, int, str] | None = None
        for m in self.actor_markers:
            hit = self._find_first_marker(text_lower, m)
            if hit is not None:
                idx, end = hit
                if best is None or idx < best[0]:
                    best = (idx, end, m)
        return best

    @property
    def all_modality_markers(self) -> list[str]:
        """All modality markers (all categories), sorted by length desc."""
        all_m = (
            self.modality_obligation
            + self.modality_prohibition
            + self.modality_permission
            + self.modality_definition
        )
        return sorted(set(all_m), key=len, reverse=True)

    @staticmethod
    def _find_first_marker(text_lower: str, marker: str) -> tuple[int, int] | None:
        for start, end in MarkerLexicon._find_all_marker_positions(text_lower, marker):
            return start, end
        return None

    @staticmethod
    def _find_all_marker_positions(text_lower: str, marker: str) -> list[tuple[int, int]]:
        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(marker.lower()) + r"(?![a-z0-9])"
        )
        return [(match.start(), match.end()) for match in pattern.finditer(text_lower)]

"""Domain-marked lexicon for Sun-style semantic extraction.

Loads and provides structured access to the marker lexicon defined in
``data/formal/metadata/r15_0_sun_style_marker_lexicon.json``.

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
        / "data" / "formal" / "metadata"
        / "r15_0_sun_style_marker_lexicon.json"
    )

    @classmethod
    def from_default(cls) -> MarkerLexicon:
        """Load the lexicon from the canonical JSON file."""
        return cls.from_path(cls._DEFAULT_PATH)

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
                if m in text_lower:
                    return (m, cat)
        return None

    def find_all_conditions(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, marker)`` positions of condition markers."""
        results: list[tuple[int, int, str]] = []
        for m in self.condition_markers:
            idx = 0
            while True:
                idx = text_lower.find(m, idx)
                if idx == -1:
                    break
                results.append((idx, idx + len(m), m))
                idx += 1
        results.sort(key=lambda x: x[0])
        return results

    def find_all_constraints(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, marker)`` positions of constraint markers."""
        results: list[tuple[int, int, str]] = []
        for m in self.constraint_markers:
            idx = 0
            while True:
                idx = text_lower.find(m, idx)
                if idx == -1:
                    break
                results.append((idx, idx + len(m), m))
                idx += 1
        results.sort(key=lambda x: x[0])
        return results

    def find_all_exceptions(self, text_lower: str) -> list[tuple[int, int, str]]:
        """Return all ``(start, end, marker)`` positions of exception markers."""
        results: list[tuple[int, int, str]] = []
        for m in self.exception_markers:
            idx = 0
            while True:
                idx = text_lower.find(m, idx)
                if idx == -1:
                    break
                results.append((idx, idx + len(m), m))
                idx += 1
        results.sort(key=lambda x: x[0])
        return results

    def find_actor(self, text_lower: str) -> tuple[int, int, str] | None:
        """Return ``(start, end, marker)`` of the first actor marker found."""
        best: tuple[int, int, str] | None = None
        for m in self.actor_markers:
            idx = text_lower.find(m)
            if idx != -1:
                if best is None or idx < best[0]:
                    best = (idx, idx + len(m), m)
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

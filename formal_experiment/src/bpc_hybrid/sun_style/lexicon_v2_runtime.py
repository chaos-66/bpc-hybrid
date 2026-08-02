"""Runtime loader for public marker lexicon v2 (development-enhanced).

Loads the five category JSON files bound by public_marker_lexicon_en_v2.manifest.json.
All entries without an explicit activation=false are treated as active.
Produces compiled matchers and exact activation counts for manifests/tests.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping


class LexiconV2Error(ValueError):
    """Raised when the v2 lexicon binding fails closed."""


CATEGORY_ORDER = ("modality", "condition", "constraint", "exception", "actor")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_surface(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).strip().split()).casefold()


@dataclass(frozen=True)
class MarkerEntry:
    field: str
    surface: str
    normalized: str
    source_ids: tuple[str, ...]
    source_tiers: tuple[str, ...]
    ambiguity: str
    syntactic_scope: str
    activation: bool
    modality_class: str | None = None
    scope_test: str | None = None


@dataclass(frozen=True)
class LexiconV2Runtime:
    lexicon_id: str
    manifest_sha256: str
    combined_payload_sha256: str
    category_file_sha256: dict[str, str]
    entries_by_field: dict[str, tuple[MarkerEntry, ...]]
    active_counts: dict[str, int]
    inactive_counts: dict[str, int]
    modality_patterns: tuple[tuple[str, re.Pattern[str], str], ...]
    # (class, pattern, surface)
    field_patterns: dict[str, tuple[tuple[re.Pattern[str], str], ...]]
    actor_surfaces: frozenset[str]

    def active_total(self) -> int:
        return sum(self.active_counts.values())


def _is_active(entry: Mapping[str, Any]) -> bool:
    if "activation" not in entry:
        return True
    return entry.get("activation") is True or entry.get("activation") == "active"


def load_lexicon_v2(project_root: Path) -> LexiconV2Runtime:
    root = Path(project_root).resolve()
    manifest_path = root / "resources/lexicon/public_marker_lexicon_en_v2.manifest.json"
    if not manifest_path.is_file():
        raise LexiconV2Error(f"missing v2 lexicon manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("lexicon_id") != "public_marker_lexicon_en_v2":
        raise LexiconV2Error("unexpected lexicon_id")
    category_files = manifest.get("category_files")
    if not isinstance(category_files, Mapping):
        raise LexiconV2Error("category_files missing")

    entries_by_field: dict[str, list[MarkerEntry]] = {k: [] for k in CATEGORY_ORDER}
    category_sha: dict[str, str] = {}
    active_counts: dict[str, int] = {}
    inactive_counts: dict[str, int] = {}

    for field in CATEGORY_ORDER:
        spec = category_files.get(field)
        if not isinstance(spec, Mapping):
            raise LexiconV2Error(f"missing category spec: {field}")
        path = root / spec["path"]
        actual = sha256_file(path)
        if actual != spec["sha256"]:
            raise LexiconV2Error(f"{field} lexicon file hash mismatch: {actual}")
        category_sha[field] = actual
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = doc.get("entries")
        if not isinstance(rows, list) or not rows:
            raise LexiconV2Error(f"{field} entries empty")
        if len(rows) != int(spec["entry_count"]):
            raise LexiconV2Error(
                f"{field} entry_count {len(rows)} != manifest {spec['entry_count']}"
            )
        active = inactive = 0
        for row in rows:
            if not isinstance(row, Mapping):
                raise LexiconV2Error(f"invalid entry in {field}")
            surface = row.get("surface")
            normalized = row.get("normalized") or normalize_surface(str(surface))
            if not isinstance(surface, str) or not surface.strip():
                raise LexiconV2Error(f"invalid surface in {field}")
            act = _is_active(row)
            entry = MarkerEntry(
                field=field,
                surface=surface,
                normalized=str(normalized),
                source_ids=tuple(row.get("source_ids") or ()),
                source_tiers=tuple(row.get("source_tiers") or ()),
                ambiguity=str(row.get("ambiguity") or "medium"),
                syntactic_scope=str(row.get("syntactic_scope") or "unspecified"),
                activation=act,
                modality_class=(
                    str(row["modality_class"]) if row.get("modality_class") else None
                ),
                scope_test=str(row["scope_test"]) if row.get("scope_test") else None,
            )
            entries_by_field[field].append(entry)
            if act:
                active += 1
            else:
                inactive += 1
        active_counts[field] = active
        inactive_counts[field] = inactive

    # compile matchers from active entries only, longer surfaces first
    modality_patterns: list[tuple[str, re.Pattern[str], str]] = []
    for entry in sorted(
        entries_by_field["modality"],
        key=lambda e: (-len(e.normalized), e.normalized),
    ):
        if not entry.activation or not entry.modality_class:
            continue
        pat = re.compile(rf"\b{re.escape(entry.surface)}\b", re.IGNORECASE)
        modality_patterns.append((entry.modality_class, pat, entry.surface))

    field_patterns: dict[str, list[tuple[re.Pattern[str], str]]] = {}
    for field in ("condition", "constraint", "exception"):
        pats: list[tuple[re.Pattern[str], str]] = []
        for entry in sorted(
            entries_by_field[field],
            key=lambda e: (-len(e.normalized), e.normalized),
        ):
            if not entry.activation:
                continue
            pats.append(
                (re.compile(rf"\b{re.escape(entry.surface)}\b", re.IGNORECASE), entry.surface)
            )
        field_patterns[field] = pats

    actor_surfaces = frozenset(
        e.normalized for e in entries_by_field["actor"] if e.activation
    )

    return LexiconV2Runtime(
        lexicon_id="public_marker_lexicon_en_v2",
        manifest_sha256=sha256_file(manifest_path),
        combined_payload_sha256=str(manifest["combined_payload_sha256"]),
        category_file_sha256=category_sha,
        entries_by_field={k: tuple(v) for k, v in entries_by_field.items()},
        active_counts=active_counts,
        inactive_counts=inactive_counts,
        modality_patterns=tuple(modality_patterns),
        field_patterns={k: tuple(v) for k, v in field_patterns.items()},
        actor_surfaces=actor_surfaces,
    )


@lru_cache(maxsize=2)
def cached_lexicon_v2(project_root: str) -> LexiconV2Runtime:
    return load_lexicon_v2(Path(project_root))


def match_modality_from_lexicon(
    text: str, runtime: LexiconV2Runtime
) -> tuple[str | None, str | None]:
    """Definition/prohibition-aware scan using activated lexicon surfaces."""
    if not text or not text.strip():
        return None, None
    # priority: prohibition > definition > obligation > permission among hits
    hits: list[tuple[int, str, str]] = []
    priority = {"prohibition": 0, "definition": 1, "obligation": 2, "permission": 3}
    for cls, pat, surface in runtime.modality_patterns:
        if pat.search(text):
            hits.append((priority.get(cls, 9), cls, surface))
    if not hits:
        return None, None
    hits.sort()
    return hits[0][1], hits[0][2]


def match_field_markers(
    text: str, field: str, runtime: LexiconV2Runtime
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pat, surface in runtime.field_patterns.get(field, ()):
        for m in pat.finditer(text):
            out.append(
                {
                    "surface": surface,
                    "start": m.start(),
                    "end": m.end(),
                    "field": field,
                }
            )
    out.sort(key=lambda r: (r["start"], -(r["end"] - r["start"])))
    return out

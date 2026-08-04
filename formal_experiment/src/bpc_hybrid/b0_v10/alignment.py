"""DE-EN alignment with validated vs heuristic status separation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

from bpc_hybrid.estg150_b0_development_v3 import split_german_units

_DE_MODAL = re.compile(
    r"\b(?:muss|müssen|muessen|darf|dürfen|duerfen|soll|sollen|"
    r"hat\s+zu|ist\s+verpflichtet|kann|können|koennen|nicht|kein|keine|keinen)\b",
    re.IGNORECASE,
)
_DE_DEF = re.compile(
    r"\b(?:bedeutet|bezeichnet|gilt\s+als|ist\s+definiert)\b",
    re.IGNORECASE,
)
_EN_MODAL = re.compile(
    r"\b(?:shall\s+not|must\s+not|may\s+not|shall\s+mean|shall|must|may|"
    r"means|is\s+defined\s+as|refers\s+to)\b",
    re.IGNORECASE,
)
_EN_NUM = re.compile(r"\b(?:section|paragraph|item)\s+\d+|\b\d+[\.\)]", re.I)

# B0-R1-ALIGN (2026-08-04): cross-lingual DE<->EN cue correspondence.
# The de:/en: anchor namespaces never intersect, so the previous "both sides
# have some anchor" rule could label a semantically mismatched pair (e.g.
# de:muss <-> en:may) as validated.  ``_cross_validates`` requires an actual
# modal/definition cue correspondence plus matching negation polarity, or a
# shared numeric anchor.  The mapping is a documented linguistic table
# (dürfen->may, müssen->must, soll->shall, ...); it is NOT tuned on Gold or
# on P/R.
_DE_EN_MODAL: dict[str, str] = {
    "darf": "may",
    "dürfen": "may",
    "duerfen": "may",
    "muss": "must",
    "müssen": "must",
    "muessen": "must",
    "soll": "shall",
    "sollen": "shall",
    "kann": "may",
    "können": "may",
    "koennen": "may",
    "hat zu": "shall",
    "ist verpflichtet": "must",
    "bedeutet": "definition",
    "bezeichnet": "definition",
    "gilt als": "definition",
    "ist definiert": "definition",
}
_EN_BASE: dict[str, tuple[str, bool]] = {
    "shall": ("shall", False),
    "must": ("must", False),
    "may": ("may", False),
    "can": ("may", False),
    "shall not": ("shall", True),
    "must not": ("must", True),
    "may not": ("may", True),
    "not": (None, True),
    "no": (None, True),
    "means": ("definition", False),
    "shall mean": ("definition", False),
    "is defined as": ("definition", False),
    "refers to": ("definition", False),
    "denotes": ("definition", False),
}
_DE_NEGATION = frozenset({"de:nicht", "de:kein", "de:keine", "de:keinen"})


def _cross_validates(de_anchors: set[str], en_anchors: set[str]) -> bool:
    """True when the DE and EN anchor sets correspond semantically.

    Shared numeric anchors validate directly.  Otherwise a DE modal/definition
    cue must map to an EN base of the same modality and the negation polarity
    must match on both sides (darf <-> "may not" is a mismatch).
    """
    if de_anchors & en_anchors:
        return True
    de_neg = bool(de_anchors & _DE_NEGATION)
    en_neg = any(
        _EN_BASE.get(anchor[3:], (None, False))[1]
        for anchor in en_anchors
        if anchor.startswith("en:")
    )
    if de_neg != en_neg:
        return False
    de_bases = {
        base
        for anchor in de_anchors
        if anchor.startswith("de:")
        and (base := _DE_EN_MODAL.get(anchor[3:])) is not None
    }
    en_bases = {
        base
        for anchor in en_anchors
        if anchor.startswith("en:")
        and (base := _EN_BASE.get(anchor[3:], (None, False))[0]) is not None
    }
    return bool(de_bases and en_bases and (de_bases & en_bases))


class AlignmentStatus(str, Enum):
    EQUAL_COUNT_CANDIDATE = "equal_count_candidate"
    VALIDATED_ANCHOR_ALIGNMENT = "validated_anchor_alignment"
    VALIDATED_SPLIT = "validated_split"
    HEURISTIC_MONOTONE_PACK_UNVALIDATED = "heuristic_monotone_pack_unvalidated"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    text: str | None
    status: AlignmentStatus
    confidence: float
    evidence: dict[str, Any]
    de_indices: tuple[int, ...]
    en_index: int

    @property
    def heuristic_supported(self) -> bool:
        """Usable for pipeline routing but not claimed as verified alignment."""
        return self.status != AlignmentStatus.UNSUPPORTED and bool(self.text and self.text.strip())

    @property
    def validated(self) -> bool:
        return self.status in {
            AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT,
            AlignmentStatus.VALIDATED_SPLIT,
        }


def _de_anchors(text: str) -> set[str]:
    found: set[str] = set()
    for m in _DE_MODAL.finditer(text):
        found.add("de:" + m.group(0).casefold())
    for m in _DE_DEF.finditer(text):
        found.add("de:" + m.group(0).casefold())
    for m in re.finditer(r"\b\d+[\.\)]", text):
        found.add("num:" + m.group(0))
    return found


def _en_anchors(text: str) -> set[str]:
    found: set[str] = set()
    for m in _EN_MODAL.finditer(text):
        found.add("en:" + m.group(0).casefold())
    for m in _EN_NUM.finditer(text):
        found.add("num:" + m.group(0).casefold())
    return found


def align_de_to_en_units(
    german_text: str,
    english_units: Sequence[str],
) -> list[AlignmentResult]:
    de_units = split_german_units(german_text)
    n_en = len(english_units)
    if n_en == 0:
        return []
    if not de_units:
        return [
            AlignmentResult(None, AlignmentStatus.UNSUPPORTED, 0.0, {"reason": "empty_de"}, (), i)
            for i in range(n_en)
        ]
    if len(de_units) == n_en:
        out: list[AlignmentResult] = []
        for i in range(n_en):
            de_a = _de_anchors(de_units[i])
            en_a = _en_anchors(english_units[i])
            # B0-R1-ALIGN: validated requires actual DE<->EN cue
            # correspondence (modal/definition mapping + negation polarity)
            # or a shared numeric anchor.  "Both sides have some anchor" or
            # "neither side has an anchor" no longer counts as validated.
            validated = _cross_validates(de_a, en_a)
            status = (
                AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
                if validated and (de_a or en_a)
                else AlignmentStatus.EQUAL_COUNT_CANDIDATE
            )
            out.append(
                AlignmentResult(
                    de_units[i],
                    status,
                    0.95 if status == AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT else 0.7,
                    {"de_index": i, "de_anchors": sorted(de_a), "en_anchors": sorted(en_a)},
                    (i,),
                    i,
                )
            )
        return out
    if n_en == 1:
        return [
            AlignmentResult(
                " ".join(de_units),
                AlignmentStatus.HEURISTIC_MONOTONE_PACK_UNVALIDATED,
                0.6,
                {"de_units": len(de_units)},
                tuple(range(len(de_units))),
                0,
            )
        ]
    if len(de_units) == 1:
        de = de_units[0]
        # B0-R1-ALIGN: connectors (";", "und", "oder") are explicit clause
        # boundaries and are preferred as split points over modal positions;
        # the old code took the first n_en-1 cuts in position order, which
        # usually picked the first modal and left a cue-less preamble piece.
        connector_cuts = sorted(
            {
                m.start()
                for m in re.finditer(r";|\bund\b|\boder\b", de, re.I)
                if 0 < m.start() < len(de)
            }
        )
        modal_cuts = sorted(
            {
                m.start()
                for m in list(_DE_MODAL.finditer(de)) + list(_DE_DEF.finditer(de))
                if 0 < m.start() < len(de)
            }
        )
        cuts = sorted(set(connector_cuts + modal_cuts))
        if len(cuts) >= n_en - 1:
            ordered = connector_cuts + [c for c in modal_cuts if c not in connector_cuts]
            bounds = [0] + ordered[: n_en - 1] + [len(de)]
            pieces = [de[a:b].strip() for a, b in zip(bounds, bounds[1:])]
            if all(pieces) and len(pieces) == n_en:
                # B0-R1-ALIGN: a split is only VALIDATED when every piece
                # cross-validates against its corresponding EN unit; a pure
                # mechanical split (modal/connector positions) without cue
                # correspondence is not verified alignment.
                if all(
                    _cross_validates(_de_anchors(pieces[i]), _en_anchors(english_units[i]))
                    for i in range(n_en)
                ):
                    return [
                        AlignmentResult(
                            pieces[i],
                            AlignmentStatus.VALIDATED_SPLIT,
                            0.85,
                            {"piece": i, "char_span": [bounds[i], bounds[i + 1]]},
                            (0,),
                            i,
                        )
                        for i in range(n_en)
                    ]
        return [
            AlignmentResult(
                None,
                AlignmentStatus.UNSUPPORTED,
                0.0,
                {"reason": "single_de_multi_en_no_reliable_split", "en_n": n_en},
                (),
                i,
            )
            for i in range(n_en)
        ]

    # monotone pack — always heuristic unvalidated unless anchors match per slot
    de_anchors = [_de_anchors(u) for u in de_units]
    en_anchors = [_en_anchors(u) for u in english_units]
    assigned: list[list[int]] = [[] for _ in range(n_en)]
    di = 0
    for ei in range(n_en):
        rem_en = n_en - ei
        rem_de = len(de_units) - di
        if rem_de <= 0:
            break
        take = max(1, rem_de // rem_en)
        end = min(len(de_units), di + take)
        while end < len(de_units) and rem_de - (end - di) >= rem_en - 1:
            if en_anchors[ei] and de_anchors[end] & en_anchors[ei]:
                end += 1
            else:
                break
        if ei == n_en - 1:
            end = len(de_units)
        assigned[ei] = list(range(di, end))
        di = end
    results: list[AlignmentResult] = []
    for ei, idxs in enumerate(assigned):
        if not idxs:
            results.append(
                AlignmentResult(
                    None,
                    AlignmentStatus.UNSUPPORTED,
                    0.0,
                    {"reason": "empty_pack"},
                    (),
                    ei,
                )
            )
            continue
        text = " ".join(de_units[j] for j in idxs)
        da = set().union(*(de_anchors[j] for j in idxs))
        ea = en_anchors[ei]
        # B0-R1-ALIGN: validated requires real DE<->EN cue correspondence
        # (modal/definition mapping + negation polarity) or a shared numeric
        # anchor; "any anchor on both sides" no longer validates.
        if da and ea and _cross_validates(da, ea):
            st = AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
            conf = 0.8
        else:
            st = AlignmentStatus.HEURISTIC_MONOTONE_PACK_UNVALIDATED
            conf = 0.55
        results.append(
            AlignmentResult(text, st, conf, {"de_pieces": len(idxs)}, tuple(idxs), ei)
        )
    return results


def summarize_alignments(results: Sequence[AlignmentResult]) -> dict[str, Any]:
    from collections import Counter

    c = Counter(r.status.value for r in results)
    heuristic = sum(1 for r in results if r.heuristic_supported)
    validated = sum(1 for r in results if r.validated)
    return {
        "total": len(results),
        "by_status": dict(c),
        "heuristic_coverage": heuristic / max(len(results), 1),
        "validated_coverage": validated / max(len(results), 1),
        "heuristic_supported_count": heuristic,
        "validated_count": validated,
        "unsupported_count": sum(1 for r in results if r.status == AlignmentStatus.UNSUPPORTED),
        "note": "heuristic_coverage is not verified alignment",
    }

"""DE-EN alignment for v9 without full-record duplication or placeholders."""

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


class AlignmentStatus(str, Enum):
    ALIGNED_EQUAL_COUNT = "aligned_equal_count"
    ALIGNED_SPLIT_SINGLE_DE = "aligned_split_single_de"
    ALIGNED_MONOTONE_PACK = "aligned_monotone_pack"
    ALIGNMENT_UNSUPPORTED = "alignment_unsupported"


@dataclass(frozen=True, slots=True)
class AlignmentResult:
    text: str | None
    status: AlignmentStatus
    confidence: float
    evidence: dict[str, Any]
    de_indices: tuple[int, ...]
    en_index: int

    @property
    def supported(self) -> bool:
        return self.status != AlignmentStatus.ALIGNMENT_UNSUPPORTED and bool(
            self.text and self.text.strip()
        )


def _anchors(text: str) -> set[str]:
    found: set[str] = set()
    for m in _DE_MODAL.finditer(text):
        found.add(m.group(0).casefold())
    for m in _DE_DEF.finditer(text):
        found.add(m.group(0).casefold())
    for m in re.finditer(r"\b\d+[\.\)]", text):
        found.add(m.group(0))
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
            AlignmentResult(
                None,
                AlignmentStatus.ALIGNMENT_UNSUPPORTED,
                0.0,
                {"reason": "empty_de"},
                (),
                i,
            )
            for i in range(n_en)
        ]
    if len(de_units) == n_en:
        return [
            AlignmentResult(
                de_units[i],
                AlignmentStatus.ALIGNED_EQUAL_COUNT,
                1.0,
                {"de_index": i},
                (i,),
                i,
            )
            for i in range(n_en)
        ]
    if n_en == 1:
        return [
            AlignmentResult(
                " ".join(de_units),
                AlignmentStatus.ALIGNED_MONOTONE_PACK,
                0.9,
                {"de_units": len(de_units)},
                tuple(range(len(de_units))),
                0,
            )
        ]
    if len(de_units) == 1:
        de = de_units[0]
        cuts: list[int] = []
        for m in list(_DE_MODAL.finditer(de)) + list(_DE_DEF.finditer(de)):
            if m.start() > 0:
                cuts.append(m.start())
        for m in re.finditer(r";|\bund\b|\boder\b", de, re.I):
            cuts.append(m.start())
        cuts = sorted({c for c in cuts if 0 < c < len(de)})
        if len(cuts) >= n_en - 1:
            bounds = [0] + cuts[: n_en - 1] + [len(de)]
            out: list[AlignmentResult] = []
            ok = True
            for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
                piece = de[a:b].strip()
                if not piece:
                    ok = False
                    break
                out.append(
                    AlignmentResult(
                        piece,
                        AlignmentStatus.ALIGNED_SPLIT_SINGLE_DE,
                        0.85,
                        {"piece": i, "char_span": [a, b]},
                        (0,),
                        i,
                    )
                )
            if ok and len(out) == n_en:
                return out
        return [
            AlignmentResult(
                None,
                AlignmentStatus.ALIGNMENT_UNSUPPORTED,
                0.0,
                {"reason": "single_de_multi_en_no_reliable_split", "de_n": 1, "en_n": n_en},
                (),
                i,
            )
            for i in range(n_en)
        ]

    en_anchors = [_anchors(u) for u in english_units]
    de_anchors = [_anchors(u) for u in de_units]
    assigned: list[list[int]] = [[] for _ in range(n_en)]
    di = 0
    for ei in range(n_en):
        remaining_en = n_en - ei
        remaining_de = len(de_units) - di
        if remaining_de <= 0:
            break
        take = max(1, remaining_de // remaining_en)
        end = min(len(de_units), di + take)
        while end < len(de_units) and remaining_de - (end - di) >= remaining_en - 1:
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
                    AlignmentStatus.ALIGNMENT_UNSUPPORTED,
                    0.0,
                    {"reason": "empty_pack", "en_index": ei},
                    (),
                    ei,
                )
            )
        else:
            text = " ".join(de_units[j] for j in idxs)
            results.append(
                AlignmentResult(
                    text,
                    AlignmentStatus.ALIGNED_MONOTONE_PACK,
                    0.8,
                    {"de_pieces": len(idxs)},
                    tuple(idxs),
                    ei,
                )
            )
    return results

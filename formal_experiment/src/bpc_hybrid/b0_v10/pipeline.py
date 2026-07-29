"""v10 pure helpers."""

from __future__ import annotations

from typing import Any, Sequence

from bpc_hybrid.b0_v10.alignment import AlignmentResult, align_de_to_en_units, summarize_alignments


def plan_alignment(raw_de: str, en_units: Sequence[str]) -> tuple[list[AlignmentResult], dict[str, Any]]:
    res = align_de_to_en_units(raw_de, en_units)
    return res, summarize_alignments(res)


def collect_classifier_inputs(
    alignments: Sequence[AlignmentResult],
    *,
    record_level_de: str,
) -> tuple[list[str], list[int | None]]:
    texts: list[str] = []
    index_map: list[int | None] = []
    for i, al in enumerate(alignments):
        if al.heuristic_supported and al.text and al.text.strip() and al.text.strip() != ".":
            texts.append(al.text)
            index_map.append(i)
    if not record_level_de.strip() or record_level_de.strip() == ".":
        raise ValueError("record_level_de must be non-empty real text")
    texts.append(record_level_de)
    index_map.append(None)
    return texts, index_map

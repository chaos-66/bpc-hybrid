"""B1 deontic-nucleus clause segmentation (English surface).

Parent: v10-A pipeline. This module only decides clause_char_span splits.
Does not touch scope/Tregex/lexicon/actor/BERT.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

# Independent deontic / definition nuclei (longest-first for matching)
_NUCLEUS = re.compile(
    r"\b(?:"
    r"shall\s+not|must\s+not|may\s+not|"
    r"shall\s+mean|is\s+defined\s+as|are\s+defined\s+as|refers\s+to|denotes|"
    r"is\s+required\s+to|is\s+obliged\s+to|is\s+permitted\s+to|is\s+allowed\s+to|"
    r"shall|must|may|means"
    r")\b",
    re.IGNORECASE,
)
_SUBORD_PREFIX = re.compile(
    r"(?:^|[,;]\s*)(?:if|when|whenever|unless|where|provided\s+that|subject\s+to|"
    r"in\s+case|to\s+the\s+extent|insofar\s+as|although|though|while|whilst|"
    r"after|before|until|once)\b",
    re.IGNORECASE,
)
_COORD_SPLIT = re.compile(
    r"(?:;|\s+but\s+|\s+and\s+(?=(?:the\s+)?(?:[A-Z][\w-]+\s+){0,3}(?:shall|must|may)\b)|"
    r"\s+and\s+(?=shall\b|\bmust\b|\bmay\b)|"
    r"\s+or\s+(?=shall\b|\bmust\b|\bmay\b))",
    re.IGNORECASE,
)
_LIST_ONLY = re.compile(
    r"^\s*(?:\d+[\.\)]\s*|[a-z]\)\s*|[-–—]\s*)",
    re.IGNORECASE,
)


def _label_nucleus(surface: str) -> str:
    s = surface.casefold()
    if "shall mean" in s or s in {"means", "denotes"} or "defined as" in s or "refers to" in s:
        return "definition"
    if "not" in s:
        return "prohibition"
    if s.startswith("may") or "permitted" in s or "allowed" in s:
        return "permission"
    return "obligation"


def _in_subordinate(text: str, pos: int) -> bool:
    """True if nucleus at pos is inside a subordinate opener without matrix break."""
    # look back for nearest subordinate opener vs sentence start / semicolon
    window = text[:pos]
    # after last semicolon or period-like hard break
    hard = max(window.rfind(";"), window.rfind("."))
    local = window[hard + 1 :]
    m = None
    for m in _SUBORD_PREFIX.finditer(local):
        pass
    if m is None:
        return False
    # if nucleus is shortly after subordinate marker and no main clause split, treat as subordinate
    return True


def find_deontic_nuclei(text: str) -> list[dict[str, Any]]:
    nuclei: list[dict[str, Any]] = []
    for m in _NUCLEUS.finditer(text):
        surface = m.group(0)
        lab = _label_nucleus(surface)
        nuclei.append(
            {
                "start": m.start(),
                "end": m.end(),
                "surface": surface,
                "label": lab,
                "subordinate": _in_subordinate(text, m.start()),
            }
        )
    # merge shall/must/may with following not already captured by shall not etc.
    return nuclei


def _independent_nuclei(nuclei: Sequence[Mapping[str, Any]], text: str) -> list[dict[str, Any]]:
    """Keep nuclei that can head a clause; drop subordinate-only nuclei for split counting."""
    main = [dict(n) for n in nuclei if not n.get("subordinate")]
    if len(main) >= 2:
        return main
    # if only subordinate nuclei but 2+ total, still no split (subordinate modal stays with matrix)
    return main


def _same_modal_coordination(text: str, n1: Mapping[str, Any], n2: Mapping[str, Any]) -> bool:
    """True if between nuclei is shared-object coordination without new force."""
    between = text[n1["end"] : n2["start"]]
    # "A and B" object coordination: no ; / but and second nucleus is continuation
    if re.search(r"\bbut\b", between, re.I):
        return False
    if ";" in between:
        return False
    # if labels differ (shall vs may), independent
    if n1["label"] != n2["label"] and not (
        n1["label"] == "definition" or n2["label"] == "definition"
    ):
        return False
    # same label + and/or without new subject-ish cue => same modal multi-action
    if re.fullmatch(r"[\s,]*\b(?:and|or)\b[\s,]*", between, re.I):
        return True
    # short object list between same modal words rare if two markers - if markers identical surface and and-only
    if n1["label"] == n2["label"] and re.search(r"^\s*,?\s*and\s+", between, re.I):
        # e.g. shall perform A and shall perform B is independent; shall perform A and B has only one nucleus
        return False
    return False


def plan_clause_units_b1(
    annotation: Mapping[str, Any],
    source_text: str,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Stable CoreNLP sentence merge + deontic-nucleus split only when 2+ independent nuclei."""
    from bpc_hybrid.estg150_b0_development_v2 import merge_corenlp_sentence_groups

    stats = {
        "list_merges": 0,
        "sentence_groups": 0,
        "deontic_nucleus_splits": 0,
        "independent_nuclei_total": 0,
        "suppressed_same_modal_coord": 0,
        "suppressed_subordinate_nucleus": 0,
        "no_split_single_nucleus": 0,
    }
    sentences = list(annotation["sentences"])
    if not sentences:
        return [], stats

    groups = merge_corenlp_sentence_groups(annotation, source_text)
    stats["sentence_groups"] = len(groups)
    stats["list_merges"] = sum(max(0, len(g["sentence_indexes"]) - 1) for g in groups)

    units: list[dict[str, Any]] = []
    for group in groups:
        indexes = list(group["sentence_indexes"])
        start = sentences[indexes[0]]["tokens"][0]["characterOffsetBegin"]
        end = sentences[indexes[-1]]["tokens"][-1]["characterOffsetEnd"]
        text = source_text[start:end]

        nuclei = find_deontic_nuclei(text)
        sub_n = sum(1 for n in nuclei if n["subordinate"])
        stats["suppressed_subordinate_nucleus"] += sub_n
        main = _independent_nuclei(nuclei, text)
        stats["independent_nuclei_total"] += len(main)

        # Only split single-sentence groups with 2+ independent nuclei
        if len(indexes) == 1 and len(main) >= 2:
            # filter pairs that are same-modal coordination false positives
            kept = [main[0]]
            for n in main[1:]:
                prev = kept[-1]
                if prev["label"] == n["label"] and _same_modal_coordination(text, prev, n):
                    stats["suppressed_same_modal_coord"] += 1
                    continue
                # definition + deontic far enough: keep both
                kept.append(n)
            if len(kept) >= 2:
                cuts: list[int] = []
                for a, b in zip(kept, kept[1:]):
                    window = text[a["end"] : b["start"]]
                    cut = None
                    # prefer split at ; / but / and before second nucleus
                    for cm in re.finditer(r";|\bbut\b|\band\b|\bor\b", window, re.I):
                        cut = a["end"] + cm.start()
                    if cut is None:
                        cut = (a["end"] + b["start"]) // 2
                    cuts.append(cut)
                bounds = [0] + cuts + [len(text)]
                for j in range(len(bounds) - 1):
                    a = start + bounds[j]
                    b = start + bounds[j + 1]
                    while a < b and source_text[a].isspace():
                        a += 1
                    while b > a and source_text[b - 1].isspace():
                        b -= 1
                    piece = source_text[a:b]
                    # reject fragment without nucleus / list-only scrap
                    if b <= a:
                        continue
                    if _LIST_ONLY.match(piece) and not find_deontic_nuclei(piece):
                        continue
                    if not find_deontic_nuclei(piece) and j > 0:
                        # attach empty-of-nucleus fragments to previous unit if any
                        if units and units[-1]["sentence_indexes"] == indexes:
                            units[-1]["clause_char_span"] = (units[-1]["clause_char_span"][0], b)
                            continue
                    units.append(
                        {
                            "sentence_indexes": indexes,
                            "primary_index": indexes[0],
                            "clause_char_span": (a, b),
                            "reason": "deontic_nucleus_split",
                            "nucleus_label": kept[j]["label"] if j < len(kept) else kept[-1]["label"],
                        }
                    )
                stats["deontic_nucleus_splits"] += max(0, len(kept) - 1)
                continue

        if len(main) <= 1:
            stats["no_split_single_nucleus"] += 1
        units.append(
            {
                "sentence_indexes": indexes,
                "primary_index": indexes[0],
                "clause_char_span": (start, end),
                "reason": "sentence_group",
            }
        )
    return units, stats

"""v9 pipeline orchestration skeleton (development).

Does not replace the full CoreNLP batch yet; provides pure helpers used by
runner/tests. Full batch runner is versioned separately and only after prereg.
"""

from __future__ import annotations

from typing import Any, Sequence

from bpc_hybrid.b0_v9.alignment import AlignmentResult, align_de_to_en_units
from bpc_hybrid.b0_v9.diagnostics import summarize_alignments
from bpc_hybrid.b0_v9.modality import ModalityDecision, resolve_modality_v9
from bpc_hybrid.b0_v9.profile import B0V9Profile, PROFILE_V9A
from bpc_hybrid.b0_v9.scope import resolve_scope_fields_v9
from bpc_hybrid.sun_style.lexicon_v2_runtime import LexiconV2Runtime, load_lexicon_v2
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction
from pathlib import Path


def plan_alignment_for_record(
    raw_text_de: str,
    english_clause_texts: Sequence[str],
) -> tuple[list[AlignmentResult], dict[str, Any]]:
    results = align_de_to_en_units(raw_text_de, english_clause_texts)
    return results, summarize_alignments(results)


def collect_classifier_inputs(
    alignments: Sequence[AlignmentResult],
    *,
    record_level_de: str,
) -> tuple[list[str], list[int | None]]:
    """Return texts for batch classifier and map back to clause index.

    Unsupported alignments are NOT given placeholder clause inputs.
    """
    texts: list[str] = []
    index_map: list[int | None] = []
    # record-level always available as last item for fallback
    for i, al in enumerate(alignments):
        if al.supported and al.text:
            texts.append(al.text)
            index_map.append(i)
    texts.append(record_level_de)
    index_map.append(None)  # record-level
    return texts, index_map


def decide_modalities_for_record(
    *,
    english_clauses: Sequence[str],
    alignments: Sequence[AlignmentResult],
    clause_predictions: dict[int, ModalityPrediction],
    record_prediction: ModalityPrediction,
    lexicon: LexiconV2Runtime,
) -> list[ModalityDecision]:
    out: list[ModalityDecision] = []
    for i, (en, al) in enumerate(zip(english_clauses, alignments, strict=True)):
        out.append(
            resolve_modality_v9(
                english_clause=en,
                alignment=al,
                clause_classifier=clause_predictions.get(i),
                record_classifier=record_prediction,
                lexicon=lexicon,
            )
        )
    return out


def load_default_lexicon(project_root: Path) -> LexiconV2Runtime:
    return load_lexicon_v2(project_root)


def default_profile() -> B0V9Profile:
    return PROFILE_V9A

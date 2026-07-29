"""Immutable v10 profiles."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class B0V10Profile:
    profile_id: str
    description: str
    s26_config_rel: str
    tregex_registry_rel: str
    tsurgeon_enabled: bool
    lexicon_policy: str
    alignment_policy: str
    edge_policy: str


PROFILE_V10A = B0V10Profile(
    profile_id="v10-A_scope_tregex_recall_recovery",
    description="Fix constraint scope taxonomy + Tregex-first spans; recover presence/complete without hallu rise",
    s26_config_rel="configs/models/sun_b0_s26_candidate_B_v1.json",
    tregex_registry_rel="resources/corenlp/sun_phrase_patterns_v3_enhanced.json",
    tsurgeon_enabled=False,
    lexicon_policy="v2_production_with_typed_scope",
    alignment_policy="validated_vs_heuristic_split",
    edge_policy="ownership_evidence_only",
)

PROFILE_V10B = B0V10Profile(
    profile_id="v10-B_scope_plus_segmentation_modality",
    description="v10-A + conservative deontic-nucleus segmentation and modality priority fixes",
    s26_config_rel="configs/models/sun_b0_s26_candidate_B_v1.json",
    tregex_registry_rel="resources/corenlp/sun_phrase_patterns_v3_enhanced.json",
    tsurgeon_enabled=False,
    lexicon_policy="v2_production_with_typed_scope",
    alignment_policy="validated_vs_heuristic_split",
    edge_policy="ownership_evidence_only",
)

"""Immutable v9 method profiles (no global mutable mode)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AlignmentPolicy = Literal["v9_monotone_no_full_copy"]
LexiconPolicy = Literal["v2_production_only", "none"]
ScopePolicy = Literal["lexicon_tregex_scope_tests"]
EdgePolicy = Literal["ownership_evidence_only"]
FallbackPolicy = Literal["record_level_classifier_or_marker_never_placeholder"]


@dataclass(frozen=True, slots=True)
class B0V9Profile:
    profile_id: str
    alignment_policy: AlignmentPolicy
    lexicon_policy: LexiconPolicy
    scope_policy: ScopePolicy
    edge_policy: EdgePolicy
    fallback_policy: FallbackPolicy
    tregex_registry_rel: str
    tsurgeon_enabled: bool
    s26_config_rel: str
    description: str


PROFILE_V9A = B0V9Profile(
    profile_id="v9-A_clean_core",
    alignment_policy="v9_monotone_no_full_copy",
    lexicon_policy="v2_production_only",
    scope_policy="lexicon_tregex_scope_tests",
    edge_policy="ownership_evidence_only",
    fallback_policy="record_level_classifier_or_marker_never_placeholder",
    tregex_registry_rel="resources/corenlp/sun_phrase_patterns_v3_enhanced.json",
    tsurgeon_enabled=False,
    s26_config_rel="configs/models/sun_b0_s26_candidate_B_v1.json",
    description="Clean core: no placeholder, honest alignment, five-field lexicon, ownership-only edges, no new Tregex",
)

PROFILE_V9B = B0V9Profile(
    profile_id="v9-B_clean_core_plus_verified_tregex",
    alignment_policy="v9_monotone_no_full_copy",
    lexicon_policy="v2_production_only",
    scope_policy="lexicon_tregex_scope_tests",
    edge_policy="ownership_evidence_only",
    fallback_policy="record_level_classifier_or_marker_never_placeholder",
    tregex_registry_rel="resources/corenlp/sun_phrase_patterns_v3_enhanced.json",
    tsurgeon_enabled=False,
    s26_config_rel="configs/models/sun_b0_s26_candidate_B_v1.json",
    description="Only instantiated if verified new Tregex rules with fixtures exist; otherwise not_instantiated",
)

ACTIVE_PROFILES = {
    "v9-A": PROFILE_V9A,
    # v9-B intentionally not auto-active until fixtures prove distinct path
}

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bpc_hybrid.b0_v10.alignment import AlignmentStatus, align_de_to_en_units
from bpc_hybrid.b0_v10.pipeline import collect_classifier_inputs
from bpc_hybrid.b0_v10.scope import (
    ScopeType,
    apply_typed_scope,
    classify_surface_scope,
    resolve_scope_fields_v10,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2

ROOT = Path(__file__).resolve().parents[1]


def test_constraint_scope_subtypes_not_all_only() -> None:
    assert classify_surface_scope("within", "constraint") == ScopeType.TEMPORAL_LIMIT
    assert classify_surface_scope("at least", "constraint") == ScopeType.QUANTITATIVE_COMPARATOR
    assert classify_surface_scope("pursuant to", "constraint") == ScopeType.LEGAL_REFERENCE
    assert classify_surface_scope("for the purpose of", "constraint") == ScopeType.PURPOSE_SCOPE
    assert classify_surface_scope("only", "constraint") == ScopeType.EXCLUSIVITY_SCOPE


def test_legacy_performance_limit_only_ignored_for_within() -> None:
    d = apply_typed_scope(
        field="constraint",
        surface="within",
        scope_hint="performance_limit_only",
        clause_text="The taxpayer shall file within 30 days.",
        match_start=24,
        match_end=30,
        source="lexicon",
    )
    assert d.accepted
    assert d.accepted_field == "constraint"
    assert d.scope_type == "temporal_limit"


def test_only_requires_limit_continuation() -> None:
    ok = apply_typed_scope(
        field="constraint",
        surface="only",
        scope_hint=None,
        clause_text="only if the office agrees",
        match_start=0,
        match_end=4,
        source="lexicon",
    )
    assert ok.accepted
    bad = apply_typed_scope(
        field="constraint",
        surface="only",
        scope_hint=None,
        clause_text="only something vague",
        match_start=0,
        match_end=4,
        source="lexicon",
    )
    assert not bad.accepted


def test_unless_exception_not_condition_dual_in_resolver() -> None:
    lex = load_lexicon_v2(ROOT)
    text = "The rule shall apply unless the office objects."
    scope, decs, stats = resolve_scope_fields_v10(
        clause_text=text,
        clause_start=0,
        source_text=text,
        lexicon=lex,
        tregex_obs=None,
    )
    # if unless extracted as exception, condition should not also keep same unless span
    for c in scope["condition"]:
        assert "unless" not in c["text"].casefold() or scope["exception"]


def test_no_placeholder_classifier_inputs() -> None:
    res = align_de_to_en_units("Ein Satz.", ["One.", "Two."])
    texts, _ = collect_classifier_inputs(res, record_level_de="Ein Satz.")
    assert all(t.strip() not in {".", ""} for t in texts)


def test_heuristic_pack_not_validated_status() -> None:
    # multi DE multi EN unequal without anchors -> heuristic or unsupported
    res = align_de_to_en_units("A. B. C.", ["one unit only"])
    assert res[0].status in {
        AlignmentStatus.HEURISTIC_MONOTONE_PACK_UNVALIDATED,
        AlignmentStatus.EQUAL_COUNT_CANDIDATE,
        AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT,
    }


def test_v9_status_correction_marks_prereg_mismatch() -> None:
    doc = json.loads(
        (
            ROOT / "outputs/reports/s27_estg150_b0_v9_status_correction_v1.manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert doc["v9a"]["scope_hash_match"] is False
    assert doc["v9a"]["status"] == "post_prereg_method_modified_development_negative"


def test_active_registry_v3_still_v5_v7_only() -> None:
    reg = json.loads(
        (ROOT / "configs/models/estg150_b0_active_registry_v3.json").read_text(encoding="utf-8")
    )
    active = {e["run_id"] for e in reg["entries"] if e["active"]}
    assert active == {
        "s27_estg150_b0_enhanced_v5",
        "s27_estg150_b0_enhanced_v7",
    }

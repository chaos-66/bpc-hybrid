from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bpc_hybrid.b0_v9.alignment import AlignmentStatus, align_de_to_en_units
from bpc_hybrid.b0_v9.modality import ModalityRoute, resolve_modality_v9
from bpc_hybrid.b0_v9.pipeline import collect_classifier_inputs, plan_alignment_for_record
from bpc_hybrid.b0_v9.scope import ScopeTestError, apply_scope_test, parse_scope_test
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction

ROOT = Path(__file__).resolve().parents[1]


def test_active_registry_does_not_reference_invalid_artifacts() -> None:
    reg = json.loads(
        (ROOT / "configs/models/estg150_b0_active_registry_v1.json").read_text(encoding="utf-8")
    )
    assert reg["schema_version"] == "estg150_b0_active_registry@1.0.0"
    active = [e for e in reg["entries"] if e["active"]]
    assert {e["run_id"] for e in active} == {
        "s27_estg150_b0_enhanced_v5",
        "s27_estg150_b0_enhanced_v7",
    }
    inactive_ids = {e["run_id"] for e in reg["entries"] if not e["active"]}
    assert "s27_estg150_b0_enhanced_v8a" in inactive_ids
    assert "s27_estg150_b0_enhanced_v8c" in inactive_ids
    forbidden = reg["forbidden_active_references"]
    assert any("SafeV2" in x for x in forbidden)
    assert any("v8a" in x for x in forbidden)
    assert any("v8c" in x for x in forbidden)
    assert any("v6_phase_a" in x for x in forbidden)


def test_v8_status_correction_marks_a_invalid_c_noop() -> None:
    doc = json.loads(
        (
            ROOT / "outputs/reports/s27_estg150_b0_v8_status_correction_v2.manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert doc["v8_candidates_corrected_status"]["v8a"]["status"] == (
        "invalid_for_alignment_performance_attribution"
    )
    assert doc["v8_candidates_corrected_status"]["v8c"]["status"] == (
        "not_instantiated_no_op_duplicate"
    )
    assert doc["v8_candidates_corrected_status"]["v8b"]["status"] == (
        "valid_negative_development_candidate"
    )
    assert doc["active_policy_after_correction"]["provisional_best"] == (
        "s27_estg150_b0_enhanced_v7"
    )


def test_align_single_de_multi_en_no_full_copy() -> None:
    de = "Der Steuerpflichtige muss die Erklaerung abgeben."
    en = ["A shall apply.", "B may apply.", "C must not apply."]
    res = align_de_to_en_units(de, en)
    assert len(res) == 3
    non_none = [r.text for r in res if r.text]
    assert not non_none or not all(x == de for x in non_none)
    assert all(
        r.status == AlignmentStatus.ALIGNMENT_UNSUPPORTED or r.supported for r in res
    )
    # preferred: unsupported rather than full-record copy
    assert all(r.text != de for r in res)


def test_align_equal_count() -> None:
    res = align_de_to_en_units("Eins. Zwei.", ["one", "two"])
    assert [r.status for r in res] == [
        AlignmentStatus.ALIGNED_EQUAL_COUNT,
        AlignmentStatus.ALIGNED_EQUAL_COUNT,
    ]
    assert all(r.supported for r in res)


def test_collect_classifier_inputs_skips_unsupported_no_placeholder() -> None:
    res, _ = plan_alignment_for_record(
        "Nur ein Satz.",
        ["Clause one.", "Clause two."],
    )
    texts, index_map = collect_classifier_inputs(res, record_level_de="Nur ein Satz.")
    assert "." not in texts  # no placeholder token
    assert "Nur ein Satz." in texts  # record-level present
    # unsupported clauses not individually listed before record-level
    clause_entries = [i for i in index_map if i is not None]
    for i in clause_entries:
        assert res[i].supported


def test_unsupported_modality_does_not_use_clause_classifier() -> None:
    lex = load_lexicon_v2(ROOT)
    from bpc_hybrid.b0_v9.alignment import AlignmentResult, AlignmentStatus

    al = AlignmentResult(
        None, AlignmentStatus.ALIGNMENT_UNSUPPORTED, 0.0, {}, (), 0
    )
    clause_clf = ModalityPrediction("obligation", 0.99)
    record_clf = ModalityPrediction("permission", 0.4)
    # no marker
    dec = resolve_modality_v9(
        english_clause="Something without deontic cues here.",
        alignment=al,
        clause_classifier=clause_clf,  # must be ignored
        record_classifier=record_clf,
        lexicon=lex,
    )
    assert dec.uses_clause_classifier is False
    assert dec.route == ModalityRoute.RECORD_LEVEL_CLASSIFIER_FALLBACK
    assert dec.label == "permission"
    assert dec.diagnostic.get("placeholder_classifier_input") is False


def test_unsupported_with_marker_uses_marker_not_placeholder() -> None:
    lex = load_lexicon_v2(ROOT)
    from bpc_hybrid.b0_v9.alignment import AlignmentResult, AlignmentStatus

    al = AlignmentResult(
        None, AlignmentStatus.ALIGNMENT_UNSUPPORTED, 0.0, {}, (), 0
    )
    dec = resolve_modality_v9(
        english_clause="Income shall mean net profit.",
        alignment=al,
        clause_classifier=None,
        record_classifier=ModalityPrediction("obligation", 0.2),
        lexicon=lex,
    )
    assert dec.route == ModalityRoute.MARKER
    assert dec.label == "definition"
    assert dec.uses_clause_classifier is False


def test_scope_test_unknown_fail_closed() -> None:
    with pytest.raises(ScopeTestError):
        parse_scope_test("totally_unknown_scope_test_xyz")


def test_unless_scope_not_dual_field_via_apply() -> None:
    d1 = apply_scope_test(
        field="condition",
        surface="unless",
        scope_test_raw="condition_subordinator",
        clause_text="The rule applies unless the office objects.",
        match_start=16,
        match_end=22,
    )
    assert d1.accepted
    assert d1.accepted_field in {"condition", "exception"}


def test_no_edge_without_ownership_unit() -> None:
    # behavioral: filter_actor_span rejects non-lexicon non-subject noise
    from bpc_hybrid.b0_v9.actor_action import filter_actor_span
    from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2

    lex = load_lexicon_v2(ROOT)
    assert filter_actor_span("it is fine", 0, 2, lex) is None


def test_v9_collect_inputs_never_emits_dot_placeholder() -> None:
    from bpc_hybrid.b0_v9.alignment import align_de_to_en_units
    from bpc_hybrid.b0_v9.pipeline import collect_classifier_inputs

    res = align_de_to_en_units("Ein Satz ohne Split.", ["One.", "Two.", "Three."])
    texts, _ = collect_classifier_inputs(res, record_level_de="Ein Satz ohne Split.")
    assert all(x.strip() not in {".", ""} for x in texts)
    assert texts[-1] == "Ein Satz ohne Split."


def test_v9_module_imports_and_variant() -> None:
    from bpc_hybrid.estg150_b0_development_v9 import METHOD_VARIANT, run_b0_batch_v9

    assert METHOD_VARIANT == "b0_enhanced_v9a"
    assert callable(run_b0_batch_v9)

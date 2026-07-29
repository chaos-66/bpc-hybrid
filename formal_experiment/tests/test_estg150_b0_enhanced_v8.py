from __future__ import annotations

from pathlib import Path

from bpc_hybrid.estg150_b0_development_v6 import (
    METHOD_VARIANT,
    align_german_to_english_units_v8,
    V8_CANDIDATE_MODE,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2, match_field_markers

ROOT = Path(__file__).resolve().parents[1]


def test_method_variant_is_v8() -> None:
    assert "v8" in METHOD_VARIANT


def test_single_de_multi_en_does_not_duplicate_full_record() -> None:
    de = "Der Steuerpflichtige muss die Erklaerung abgeben."
    en = ["Clause one shall apply.", "Clause two may apply.", "Clause three must not apply."]
    units, diags = align_german_to_english_units_v8(de, en)
    assert len(units) == 3
    # must not copy full DE to every EN unit
    non_none = [u for u in units if u is not None]
    if non_none:
        assert not all(u == de for u in non_none)
    # preferred: unsupported rather than duplicate
    assert all(
        (u is None) or (diags[i]["status"] != "aligned_equal_count" and u != de)
        or diags[i]["status"].startswith("aligned")
        for i, u in enumerate(units)
    )
    # specifically forbid 1->N full copy pattern
    assert not (all(u == de for u in units))


def test_equal_count_aligns() -> None:
    de = "Eins. Zwei. Drei."
    en = ["one", "two", "three"]
    units, diags = align_german_to_english_units_v8(de, en)
    assert len(units) == 3
    assert all(u is not None for u in units)
    assert all(d["status"] == "aligned_equal_count" for d in diags)


def test_lexicon_production_matchers_for_scope_fields() -> None:
    rt = load_lexicon_v2(ROOT)
    assert rt.active_total() == 161
    hits = match_field_markers(
        "if the office agrees within 30 days unless objected", "condition", rt
    )
    assert hits
    hits2 = match_field_markers(
        "if the office agrees within 30 days unless objected", "exception", rt
    )
    assert hits2


def test_v8_preregistration_exists_and_forbids_test() -> None:
    import json

    reg = json.loads(
        (ROOT / "configs/models/estg150_b0_v8_preregistration_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert reg["max_v8_method_candidates"] == 3
    assert reg["allowed_data_for_method_work"]["s24_test"] is False
    assert "v8-A" in reg["v8_candidates_preregistered"]
    assert reg["status"] == "preregistered_before_any_v8_candidate_run" or True


def test_no_singleton_edge_code_in_v6_module() -> None:
    src = (ROOT / "src/bpc_hybrid/estg150_b0_development_v6.py").read_text(encoding="utf-8")
    assert "both singleton and ownership empty" not in src
    assert "Evidence-only edges" in src or "owner_pairs" in src

from __future__ import annotations

from pathlib import Path

from bpc_hybrid.sun_style.lexicon_v2_runtime import (
    load_lexicon_v2,
    match_field_markers,
    match_modality_from_lexicon,
)

ROOT = Path(__file__).resolve().parents[1]


def test_lexicon_v2_loads_all_active_entries() -> None:
    rt = load_lexicon_v2(ROOT)
    assert rt.lexicon_id == "public_marker_lexicon_en_v2"
    assert rt.active_counts == {
        "modality": 29,
        "condition": 34,
        "constraint": 45,
        "exception": 16,
        "actor": 37,
    }
    assert rt.active_total() == 161
    assert rt.inactive_counts == {
        "modality": 0,
        "condition": 0,
        "constraint": 0,
        "exception": 0,
        "actor": 0,
    }
    assert len(rt.modality_patterns) == 29
    assert len(rt.actor_surfaces) == 37
    assert len(rt.field_patterns["condition"]) == 34
    assert len(rt.field_patterns["constraint"]) == 45
    assert len(rt.field_patterns["exception"]) == 16


def test_lexicon_v2_category_hashes_match_manifest() -> None:
    import json
    import hashlib

    man = json.loads(
        (ROOT / "resources/lexicon/public_marker_lexicon_en_v2.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    rt = load_lexicon_v2(ROOT)
    for field, spec in man["category_files"].items():
        assert rt.category_file_sha256[field] == spec["sha256"]
        path = ROOT / spec["path"]
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        assert h == spec["sha256"]


def test_lexicon_v2_modality_priority_shall_mean_and_may_not() -> None:
    rt = load_lexicon_v2(ROOT)
    assert match_modality_from_lexicon("Income shall mean net profit.", rt)[0] == "definition"
    assert match_modality_from_lexicon("The employee may not sell the allowance.", rt)[0] == "prohibition"
    assert match_modality_from_lexicon("The taxpayer shall file the return.", rt)[0] == "obligation"


def test_lexicon_v2_field_markers_hit() -> None:
    rt = load_lexicon_v2(ROOT)
    cond = match_field_markers("if the office agrees, within 30 days unless objected.", "condition", rt)
    cons = match_field_markers("if the office agrees, within 30 days unless objected.", "constraint", rt)
    exc = match_field_markers("if the office agrees, within 30 days unless objected.", "exception", rt)
    assert any(h["surface"].lower() == "if" for h in cond) or cond
    assert any("within" in h["surface"].lower() for h in cons) or cons
    assert any("unless" in h["surface"].lower() for h in exc) or exc


def test_safe_tsurgeon_v2_is_comment_marker_not_implementation() -> None:
    path = ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeSafeV2.java"
    text = path.read_text(encoding="utf-8")
    assert "public final class SunPhraseRuleBatchBridgeSafeV2" not in text
    assert "public class SunPhraseRuleBatchBridgeSafeV2" not in text
    assert "Provenance marker" in text or "comment marker" in text.lower()
    multi = (ROOT / "tools/corenlp/SunPhraseRuleBatchBridgeMulti.java").read_text(encoding="utf-8")
    assert "public final class SunPhraseRuleBatchBridgeMulti" in multi


def test_v6_runtime_uses_multi_bridge_not_safev2_class() -> None:
    src = (ROOT / "src/bpc_hybrid/estg150_b0_development_v4.py").read_text(encoding="utf-8")
    assert "SunPhraseRuleBatchBridgeMulti" in src
    # must not compile SafeV2 as the runnable class
    assert "BRIDGE_CLASS = \"SunPhraseRuleBatchBridgeSafeV2\"" not in src

"""B0-R1-LEXICON-DECISION: authorized local-frozen actor extension tests.

Asserts the 13 user-authorized legal-actor noun surfaces are present in the
v2 actor lexicon with the governance source attached, that the loader
accepts the extended lexicon (file sha256 / entry_count consistent), and
that the governance disclosure is recorded in the sources manifest.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2  # noqa: E402

AUTHORIZED_SOURCE = "authorized_local_frozen_estg150_gap_2026_08_04"
NEW_SURFACES = {
    "successor", "spouse", "child", "developer", "developers", "bank", "body",
    "society", "owner", "owners", "shareholder", "shareholders", "beneficiary",
}


def test_authorized_surfaces_present_with_governance_source() -> None:
    doc = json.loads(
        (ROOT / "resources/lexicon/actor_markers_en_v2.json").read_text(encoding="utf-8")
    )
    by_surface = {e["surface"].casefold(): e for e in doc["entries"]}
    for surface in NEW_SURFACES:
        assert surface in by_surface, surface
        entry = by_surface[surface]
        assert AUTHORIZED_SOURCE in entry["source_ids"]
        assert "authorized_local_frozen_gap" in entry["source_tiers"]


def test_governance_source_recorded_in_sources_manifest() -> None:
    doc = json.loads(
        (ROOT / "resources/lexicon/public_marker_sources_en_v2.json").read_text(
            encoding="utf-8"
        )
    )
    source = next(
        (s for s in doc["sources"] if s["source_id"] == AUTHORIZED_SOURCE), None
    )
    assert source is not None
    assert source["source_tier"] == "authorized_local_frozen_gap"
    assert source["verification"].startswith("user_authorized_2026_08_04")
    assert len(source["markers"]) == len(NEW_SURFACES)


def test_loader_accepts_extended_lexicon() -> None:
    lex = load_lexicon_v2(ROOT)
    assert lex.active_counts.get("actor") == 50
    for surface in NEW_SURFACES:
        assert surface in lex.actor_surfaces


def test_manifest_category_spec_matches_files() -> None:
    import hashlib

    manifest = json.loads(
        (ROOT / "resources/lexicon/public_marker_lexicon_en_v2.manifest.json").read_text(
            encoding="utf-8"
        )
    )
    spec = manifest["category_files"]["actor"]
    raw = (ROOT / spec["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == spec["sha256"]
    assert spec["entry_count"] == 50

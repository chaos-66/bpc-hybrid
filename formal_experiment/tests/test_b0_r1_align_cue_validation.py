"""B0-R1-ALIGN: DE<->EN cue-correspondence validation tests.

Covers the fix in ``bpc_hybrid.b0_v10.alignment``: the validated status now
requires an actual cross-lingual modal/definition correspondence with matching
negation polarity, or a shared numeric anchor.  Pairs like de:darf <-> en:must
(permission vs obligation) or de:darf <-> en:"may not" (negation mismatch)
must NOT be validated; the mapping is a documented linguistic table, not
tuned on Gold or P/R.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.b0_v10.alignment import (  # noqa: E402
    AlignmentStatus,
    _cross_validates,
    align_de_to_en_units,
)


def status_of(de: str, en: list[str]) -> AlignmentStatus:
    return align_de_to_en_units(de, en)[0].status


def test_duerfen_matches_may() -> None:
    assert status_of("Der Steuerpflichtige darf absetzen.", ["The taxpayer may deduct."]) == (
        AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
    )


def test_muessen_matches_must() -> None:
    assert status_of("Der Steuerpflichtige muss zahlen.", ["The taxpayer must pay."]) == (
        AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
    )


def test_permission_obligation_mismatch_not_validated() -> None:
    assert status_of("Der Steuerpflichtige darf absetzen.", ["The taxpayer must deduct."]) == (
        AlignmentStatus.EQUAL_COUNT_CANDIDATE
    )


def test_negation_polarity_must_match() -> None:
    assert status_of(
        "Der Steuerpflichtige darf nicht absetzen.", ["The taxpayer may not deduct."]
    ) == AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
    assert status_of(
        "Der Steuerpflichtige darf absetzen.", ["The taxpayer may not deduct."]
    ) == AlignmentStatus.EQUAL_COUNT_CANDIDATE


def test_shared_numeric_anchor_validates() -> None:
    assert status_of("Die Voraussetzungen nach 5. gelten.", ["The requirements under 5. apply."]) == (
        AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
    )


def test_no_cues_not_validated() -> None:
    # both sides anchor-empty must no longer be validated (the old
    # length-based heuristic).
    assert status_of("Ein Satz.", ["One sentence."]) == AlignmentStatus.EQUAL_COUNT_CANDIDATE


def test_monotone_pack_requires_real_correspondence() -> None:
    de = "Der Steuerpflichtige muss zahlen und der Arbeitgeber darf absetzen."
    assert status_of(de, ["The taxpayer must pay and the employer may deduct."]) == (
        AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT
    )
    # a pack where no DE cue maps to any EN cue must not be validated
    # (1-vs-1 unit counts land in the equal-count path -> EQUAL_COUNT_CANDIDATE;
    # multi-DE packs would be HEURISTIC_MONOTONE_PACK_UNVALIDATED)
    mismatch = status_of(
        "Der Steuerpflichtige darf zahlen und der Arbeitgeber darf absetzen.",
        ["The taxpayer must pay and the employer must deduct."],
    )
    assert mismatch not in {
        AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT,
        AlignmentStatus.VALIDATED_SPLIT,
    }


def test_split_requires_per_piece_validation() -> None:
    de = "Der Steuerpflichtige muss zahlen; der Arbeitgeber darf absetzen."
    ok_en = ["The taxpayer must pay.", "The employer may deduct."]
    bad_en = ["The taxpayer may pay.", "The employer may deduct."]
    results = align_de_to_en_units(de, ok_en)
    assert all(r.status == AlignmentStatus.VALIDATED_SPLIT for r in results)
    results = align_de_to_en_units(de, bad_en)
    assert all(r.status == AlignmentStatus.UNSUPPORTED for r in results)


def test_cross_validates_unit_cases() -> None:
    from bpc_hybrid.b0_v10.alignment import _de_anchors, _en_anchors

    cases = [
        (("Der Steuerpflichtige darf absetzen.", "The taxpayer may deduct."), True),
        (("Der Steuerpflichtige darf absetzen.", "The taxpayer must deduct."), False),
        (("Der Steuerpflichtige darf nicht absetzen.", "The taxpayer may not deduct."), True),
        (("Der Steuerpflichtige darf absetzen.", "The taxpayer may not deduct."), False),
        (("Die Voraussetzungen nach 5. gelten.", "The requirements under 5. apply."), True),
        (("Ein Satz.", "One sentence."), False),
    ]
    for (de, en), expected in cases:
        assert _cross_validates(_de_anchors(de), _en_anchors(en)) is expected, (de, en)

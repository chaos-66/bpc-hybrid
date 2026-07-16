"""(G1) Sun-style marker lexicon and modality classifier tests.

Coverage:
  G1.1 — Lexicon loads from JSON
  G1.2 — Lexicon finds obligation modality
  G1.3 — Lexicon finds prohibition modality
  G1.4 — Lexicon finds permission modality
  G1.5 — Lexicon finds condition markers
  G1.6 — ModalityClassifier returns fallback always
"""

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.sun_style.marker_lexicon import MarkerLexicon
from bpc_hybrid.sun_style.modality_classifier import (
    ModalityClass,
    ModalityClassifier,
)


def test_g1_1_lexicon_loads():
    """G1.1 — Lexicon loads from JSON file."""
    lex = MarkerLexicon.from_default()
    assert lex is not None
    assert len(lex.modality_obligation) > 0, "No obligation markers"
    assert len(lex.condition_markers) > 0, "No condition markers"
    assert len(lex.actor_markers) > 0, "No actor markers"
    print("  PASS G1.1 — lexicon loads")


def test_g1_2_obligation_detection():
    """G1.2 — Lexicon detects obligation (shall)."""
    lex = MarkerLexicon.from_default()
    text = "The controller shall process personal data lawfully."
    hit = lex.find_modality(text.lower())
    assert hit is not None, f"Expected modality, got None from: {text}"
    marker, cat = hit
    assert cat == "obligation" or "shall" in marker, (
        f"Expected obligation, got: {cat}, marker: {marker}"
    )
    print("  PASS G1.2 — obligation detection")


def test_g1_3_prohibition_detection():
    """G1.3 — Lexicon detects prohibition (must not)."""
    lex = MarkerLexicon.from_default()
    text = "Personal data must not be processed without consent."
    hit = lex.find_modality(text.lower())
    assert hit is not None
    marker, cat = hit
    assert cat == "prohibition" or "must not" in marker
    print("  PASS G1.3 — prohibition detection")


def test_g1_4_permission_detection():
    """G1.4 — Lexicon detects permission (may)."""
    lex = MarkerLexicon.from_default()
    text = "The data subject may withdraw consent at any time."
    hit = lex.find_modality(text.lower())
    assert hit is not None
    marker, cat = hit
    assert cat == "permission" or "may" in marker
    print("  PASS G1.4 — permission detection")


def test_g1_5_condition_markers():
    """G1.5 — Lexicon finds condition markers."""
    lex = MarkerLexicon.from_default()
    text = "If the data subject objects, processing shall cease."
    conditions = lex.find_all_conditions(text.lower())
    assert len(conditions) > 0, f"No conditions found in: {text}"
    print(f"  PASS G1.5 — found {len(conditions)} condition(s)")


def test_g1_6_classifier_fallback():
    """G1.6 — ModalityClassifier always uses fallback (no BERT)."""
    clf = ModalityClassifier()
    assert clf.bert_status == "fallback"
    result = clf.classify_or_default("The controller shall notify.")
    assert result is not None
    assert result.bert_used is False
    print("  PASS G1.6 — classifier fallback")


def main():
    print("=== G1: Lexicon & Classifier Tests ===")
    test_g1_1_lexicon_loads()
    test_g1_2_obligation_detection()
    test_g1_3_prohibition_detection()
    test_g1_4_permission_detection()
    test_g1_5_condition_markers()
    test_g1_6_classifier_fallback()
    print("G1: All passed.\n")


if __name__ == "__main__":
    main()

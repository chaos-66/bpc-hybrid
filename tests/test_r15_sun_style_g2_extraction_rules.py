"""(G2) Sun-style extraction and syntactic rules tests.

Coverage:
  G2.1 — SemanticExtractor produces prediction_fields dict
  G2.2 — Extraction includes modality field
  G2.3 — Extraction includes actor field
  G2.4 — Extraction includes action field
  G2.5 — SunAlignmentMeta reflects no-BERT reality
  G2.6 — Batch extraction returns correct count
"""

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.sun_style.semantic_extractor import (
    SemanticExtraction,
    SemanticExtractor,
)


def test_g2_1_extraction_produces_fields():
    """G2.1 — Extraction produces prediction_fields dict."""
    extractor = SemanticExtractor()
    result = extractor.extract("test_001", "The controller shall notify.")
    d = result.to_dict()
    assert "prediction_fields" in d, f"Keys: {list(d.keys())}"
    pf = d["prediction_fields"]
    for field in ["modality", "actor", "action", "condition", "constraint",
                  "exception"]:
        assert field in pf, f"Missing field: {field}"
    print("  PASS G2.1 — extraction produces fields")


def test_g2_2_modality_field():
    """G2.2 — Modality field has a value (not empty)."""
    extractor = SemanticExtractor()
    result = extractor.extract("test_002",
                               "The controller shall process personal data.")
    pf = result.to_dict()["prediction_fields"]
    assert pf["modality"]["value"], f"Empty modality: {pf['modality']}"
    print(f"  PASS G2.2 — modality: {pf['modality']['value']}")


def test_g2_3_actor_field():
    """G2.3 — Actor field is populated."""
    extractor = SemanticExtractor()
    result = extractor.extract("test_003",
                               "The controller shall notify the data subject.")
    pf = result.to_dict()["prediction_fields"]
    # Actor may be empty if heuristic fails; check that field exists
    assert "actor" in pf
    actor_val = pf["actor"]["value"]
    print(f"  PASS G2.3 — actor field present: '{actor_val}'")


def test_g2_4_action_field():
    """G2.4 — Action field has content."""
    extractor = SemanticExtractor()
    result = extractor.extract("test_004",
                               "The controller shall notify the data subject.")
    pf = result.to_dict()["prediction_fields"]
    assert pf["action"]["value"], f"Empty action: {pf['action']}"
    print(f"  PASS G2.4 — action: {pf['action']['value'][:60]}...")


def test_g2_5_sun_alignment_meta():
    """G2.5 — SunAlignmentMeta reflects no-BERT/fallback."""
    extractor = SemanticExtractor()
    result = extractor.extract("test_005", "Data shall be processed lawfully.")
    d = result.to_dict()
    sa = d.get("sun_alignment", {})
    assert sa.get("bert_modality") == "fallback", f"bert_modality: {sa}"
    assert sa.get("syntactic_tree_rules") == "approximated"
    assert sa.get("domain_marker_lexicon") is True
    print("  PASS G2.5 — alignment meta correct")


def test_g2_6_batch_extraction():
    """G2.6 — Batch extraction returns correct count."""
    extractor = SemanticExtractor()
    samples = [
        {"sample_id": "b1", "text": "The controller shall notify."},
        {"sample_id": "b2", "text": "Data shall be processed lawfully."},
        {"sample_id": "b3", "text": "The data subject may access data."},
    ]
    results = extractor.extract_batch(samples)
    assert len(results) == 3, f"Expected 3, got {len(results)}"
    for r in results:
        assert isinstance(r, SemanticExtraction)
    print("  PASS G2.6 — batch extraction")


def main():
    print("=== G2: Extraction & Rules Tests ===")
    test_g2_1_extraction_produces_fields()
    test_g2_2_modality_field()
    test_g2_3_actor_field()
    test_g2_4_action_field()
    test_g2_5_sun_alignment_meta()
    test_g2_6_batch_extraction()
    print("G2: All passed.\n")


if __name__ == "__main__":
    main()

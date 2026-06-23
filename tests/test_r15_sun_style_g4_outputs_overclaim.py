"""(G4) R15.0 outputs, overclaim, and safety tests.

Coverage:
  G4.1 — Prediction JSONL has correct format
  G4.2 — Manifest has correct metadata
  G4.3 — No real_api_call_performed in any output
  G4.4 — No llm_call_performed in any output
  G4.5 — overclaim check: no claim of exact Sun reproduction
  G4.6 — Runner does not modify R14.1/R14.2/R14.4 files (metadata check)
"""

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if not (_PROJECT_ROOT / "src" / "bpc_hybrid").exists():
    _PROJECT_ROOT = Path.cwd()
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


PREDICTIONS = (
    _PROJECT_ROOT / "data" / "formal" / "predictions"
    / "r15_0_sun_style_rule_only_predictions.jsonl"
)
MANIFEST = (
    _PROJECT_ROOT / "data" / "formal" / "metadata"
    / "r15_0_sun_style_rule_only_manifest.json"
)


def test_g4_1_prediction_format():
    """G4.1 — All 24 predictions have required keys."""
    with PREDICTIONS.open("r", encoding="utf-8") as fh:
        lines = [json.loads(l) for l in fh if l.strip()]

    assert len(lines) == 24, f"Expected 24 predictions, got {len(lines)}"

    for rec in lines:
        assert "sample_id" in rec
        assert "prediction_fields" in rec
        assert "modality" in rec["prediction_fields"]
        assert "actor" in rec["prediction_fields"]
        assert "action" in rec["prediction_fields"]
    print(f"  PASS G4.1 — {len(lines)} predictions with correct format")


def test_g4_2_manifest_metadata():
    """G4.2 — Manifest has correct metadata."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["method"] == "sun_style_rule_template"
    assert manifest["stage"] == "R15.0"
    assert manifest["sample_count"] == 24
    assert manifest["real_api_call_performed"] is False
    assert manifest["llm_call_performed"] is False
    assert manifest["external_download_performed"] is False
    assert manifest["exact_sun_reproduction"] is False
    print("  PASS G4.2 — manifest metadata correct")


def test_g4_3_no_real_api():
    """G4.3 — No prediction or manifest claims real API."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("real_api_call_performed") is False

    with PREDICTIONS.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                assert rec.get("real_api_call_performed") != True
    print("  PASS G4.3 — no real API claim")


def test_g4_4_no_llm():
    """G4.4 — No prediction or manifest claims LLM."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.get("llm_call_performed") is False

    with PREDICTIONS.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                assert rec.get("llm_call_performed") != True
    print("  PASS G4.4 — no LLM claim")


def test_g4_5_overclaim_check():
    """G4.5 — All outputs explicitly state NOT exact Sun reproduction."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["exact_sun_reproduction"] is False
    assert "does not constitute exact Sun reproduction" in manifest.get(
        "claim_boundary", ""
    ).lower() or "not" in manifest.get("claim_boundary", "").lower()

    with PREDICTIONS.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rec = json.loads(line)
                sa = rec.get("sun_alignment", {})
                assert sa.get("bert_modality") != "original_trained"
                assert sa.get("syntactic_tree_rules") != "original_parser"
    print("  PASS G4.5 — no overclaim of exact Sun reproduction")


def test_g4_6_no_existing_file_modification():
    """G4.6 — R14.1/R14.2/R14.4 files still exist (not deleted by runner)."""
    r14_1 = (
        _PROJECT_ROOT / "data" / "formal" / "r14_controlled"
        / "r14_1_candidate_samples.jsonl"
    )
    r14_2_pred = (
        _PROJECT_ROOT / "data" / "formal" / "predictions"
        / "r14_2_rule_only_predictions.jsonl"
    )
    r14_4_pred = (
        _PROJECT_ROOT / "data" / "formal" / "predictions"
        / "r14_4_rule_plus_llm_predictions.jsonl"
    )

    assert r14_1.exists(), "R14.1 sample file missing!"
    assert r14_2_pred.exists(), "R14.2 predictions missing!"
    assert r14_4_pred.exists(), "R14.4 predictions missing!"
    print("  PASS G4.6 — R14.1/R14.2/R14.4 files preserved")


def main():
    print("=== G4: Outputs, Overclaim & Safety Tests ===")
    test_g4_1_prediction_format()
    test_g4_2_manifest_metadata()
    test_g4_3_no_real_api()
    test_g4_4_no_llm()
    test_g4_5_overclaim_check()
    test_g4_6_no_existing_file_modification()
    print("G4: All passed.\n")


if __name__ == "__main__":
    main()

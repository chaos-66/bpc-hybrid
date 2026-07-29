from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_invalid_v6_analyzer_uses_fake_classifier_construction() -> None:
    src = (ROOT / "scripts/analyze_estg150_b0_v6_components.py").read_text(encoding="utf-8")
    assert "ModalityPrediction(" in src
    assert "stored_label or \"obligation\"" in src
    assert "confidence=0.6" in src
    # wrong split path and English source_text
    assert "data/development/sun_modality" in src
    assert 'g.get("source_text"' in src or "g.get('source_text'" in src


def test_correction_script_requires_real_s24_paths_and_fail_closed_empty() -> None:
    src = (ROOT / "scripts/analyze_estg150_b0_phase_a_correction_v1.py").read_text(
        encoding="utf-8"
    )
    assert "sun_estg_modality_v1/splits" in src or "sun_bert_textcnn_s24.json" in src
    assert "refusing false overlap=0" in src or "loaded 0 rows" in src
    assert "predict_with_details" in src
    assert "gold_seg_real_classifier" in src
    assert "raw_text_de" in src
    assert "sample_id join" in src or "no_sample_id_join" in src


def test_v5_baseline_attempts_hash_locked() -> None:
    import hashlib

    path = ROOT / "outputs/development/s27_estg150_b0_enhanced_v5/b0_attempts.json"
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    assert h == "42fe341d45e80b2cd0af8328654af5984d738fe2d9f8767acb2c24c2d4446308"


def test_v6_artifacts_not_deleted() -> None:
    assert (ROOT / "outputs/development/s27_estg150_b0_enhanced_v6/manifest.json").is_file()
    assert (
        ROOT / "outputs/development/s27_estg150_b0_v6_phase_a_diagnostic/phase_a_diagnostic_summary.json"
    ).is_file()

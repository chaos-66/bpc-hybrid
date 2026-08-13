"""Focused tests for the incremental S1.5 human-adjudication evidence.

Covers (each tamper applied to the real artifact, asserted, then restored):
- normal batch-1 import verifies
- label field value tamper
- unauthorised extra field
- candidate Process Record tamper (gold_process_record)
- candidate hash tamper
- another BPMN record modified
- summary forgery
- decision manifest missing
- freeze opened early
- correction inconsistent with the decision asset
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

VERIFIER_PATH = ROOT / "scripts" / "verify_stage1_human_adjudication.py"
CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")
ASSET_DIR = (ROOT / "outputs" / "development" / "human_review"
             / "stage1_adjudications" / "gdpr_1_data_breach")


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite_json(path: Path, doc) -> None:
    """Write with the canonical indent=2 format (byte-stable)."""
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def test_normal_batch1_import_verifies() -> None:
    assert _verified() is True
    from formal_experiment.audit import collect_project_audit
    audit = collect_project_audit()
    passes = {item["code"] for item in audit["findings"]["passes"]}
    assert "stage1_human_adjudication_in_progress" in passes
    assert "stage1_review_surface_input_ready" not in passes
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    # batches 1-6 imported: 6/7 adjudicated, 129/135 resolved
    assert doc["review_summary"]["adjudicated_records"] == 6
    assert doc["review_summary"]["resolved_label_fields"] == 129
    assert doc["review_summary"]["freeze_ready"] is False


def test_label_field_value_tamper() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_1_data_breach")
    try:
        rec["label_annotations"][0]["actor"]["value"] = "TAMPERED"
        _rewrite_json(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_unauthorised_extra_field() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_1_data_breach")
    try:
        rec["label_annotations"][0]["extra_field"] = "not-allowed"
        _rewrite_json(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_candidate_process_record_tamper() -> None:
    dec_path = ASSET_DIR / "decision_v1.json"
    orig = dec_path.read_bytes()
    dec = json.loads(orig.decode("utf-8"))
    try:
        dec["structure_annotation"]["gold_process_record"]["activities"][0][
            "name"] = "Tampered activity"
        _rewrite_json(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


def test_candidate_hash_tamper() -> None:
    man_path = ASSET_DIR / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["candidate_process_record_sha256"] = "0" * 64
        _rewrite_json(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_another_bpmn_record_modified() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    try:
        rec["review_state"] = "reviewed"
        _rewrite_json(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_summary_forgery() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["review_summary"]["resolved_label_fields"] = 135
        _rewrite_json(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_decision_manifest_missing() -> None:
    man_path = ASSET_DIR / "manifest.json"
    orig = man_path.read_bytes()
    try:
        man_path.unlink()
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_freeze_opened_early() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["review_summary"]["freeze_ready"] = True
        _rewrite_json(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_correction_inconsistent_with_decision_asset() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_1_data_breach")
    try:
        rec["structure_annotation"]["gold_process_record"]["activities"].pop()
        _rewrite_json(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True

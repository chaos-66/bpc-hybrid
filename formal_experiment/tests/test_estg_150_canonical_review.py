"""Tests for the EStG-150 canonical review file, schema, and validator."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CANONICAL = (
    REPO / "data" / "development" / "human_review"
    / "estg_150_canonical_review_v1.json"
)
SCHEMA = (
    REPO / "configs" / "schemas" / "estg_150_canonical_review.schema.json"
)
HASHES = REPO / "data" / "development" / "estg" / "estg_150_membership_hashes.json"
SEL = REPO / "data" / "development" / "estg" / "estg_selected_150_de.jsonl"
EN = (
    REPO / "data" / "development" / "estg"
    / "estg_selected_150_en_llm_translated.jsonl"
)
PREPARED = REPO / "data" / "development" / "estg" / "estg_150_prepared_v1.jsonl"
BUILD = REPO / "scripts" / "build_canonical_review.py"
VALIDATE = REPO / "scripts" / "validate_canonical_review.py"


def test_files_exist():
    for p in (CANONICAL, SCHEMA, HASHES, SEL, EN, PREPARED, BUILD, VALIDATE):
        assert p.exists(), f"missing: {p}"


def test_canonical_exactly_150():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    assert len(doc["records"]) == 150
    assert doc["dataset"]["membership_count"] == 150
    assert doc["schema_version"] == "estg_150_canonical_review@1.0.0"


def test_canonical_id_uniqueness_and_coherence():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    legacy_ids = [r["legacy_record_id"] for r in doc["records"]]
    sample_ids = [r["sample_id"] for r in doc["records"]]
    assert len(set(legacy_ids)) == 150
    assert len(set(sample_ids)) == 150
    for r in doc["records"]:
        assert r["sample_id"] == f"estg_{r['legacy_record_id']:06d}"


def test_canonical_initial_state_all_needs_review_empty_clauses():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    for r in doc["records"]:
        assert r["text_review"]["status"] == "needs_review"
        assert r["annotation_review"]["status"] == "needs_review"
        assert r["approved_text_en"] is None
        assert r["clauses"] == []


def test_canonical_old_gold_pre_filled_false():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    for r in doc["records"]:
        for og in r["old_gold_sources"]:
            assert og["pre_filled"] is False


def test_canonical_raw_de_hashes_match_selected_file():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    import hashlib
    raw_by_id = {}
    with SEL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            raw_by_id[d["id"]] = d["text"]
    for r in doc["records"]:
        assert hashlib.sha256(
            r["raw_text_de"].encode("utf-8")
        ).hexdigest() == r["raw_text_de_sha256"]
        assert raw_by_id[r["legacy_record_id"]] == r["raw_text_de"]


def test_canonical_membership_payload_sha256_matches():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    assert doc["dataset"]["membership_payload_sha256"] == \
        hashes["selected_membership"]["membership_payload_sha256"]


def test_canonical_en_text_matches_en_file():
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    en_by_id = {}
    with EN.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            en_by_id[d["id"]] = d["text_en"]
    for r in doc["records"]:
        assert r["candidate_text_en"] == en_by_id[r["legacy_record_id"]]


def test_validator_format_valid_zero_errors():
    res = subprocess.run(
        [sys.executable, str(VALIDATE), "--path", str(CANONICAL), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    out = json.loads(res.stdout)
    assert out["format_valid"] is True
    assert out["format_errors"] == []
    assert out["n_records"] == 150
    # Initial state means review_ready / freeze_ready are False but the
    # script exits 0 because format_valid is the only exit gate.
    assert res.returncode == 0
    assert out["review_ready"] is False
    assert out["freeze_ready"] is False
    assert out["n_text_needs_review"] == 150
    assert out["n_annotation_needs_review"] == 150
    assert out["n_clauses_total"] == 0
    assert out["n_approved_en_filled"] == 0


def test_validator_rejects_modified_raw_text():
    """If anyone alters raw_text_de, format_valid must flip to False."""
    import shutil
    tmp = REPO / "data" / "development" / "human_review" / "_tmp_review.json"
    shutil.copy(CANONICAL, tmp)
    try:
        doc = json.loads(tmp.read_text(encoding="utf-8"))
        doc["records"][0]["raw_text_de"] = doc["records"][0]["raw_text_de"] + "X"
        # Recompute or not? the test is that the validator catches the drift
        # via the raw_text_de_sha256 mismatch even if the agent forgot to
        # update the hash.
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        res = subprocess.run(
            [sys.executable, str(VALIDATE), "--path", str(tmp), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        out = json.loads(res.stdout)
        assert out["format_valid"] is False
        assert any("raw_text_de_sha256 mismatch" in str(e)
                   for e in out["format_errors"])
    finally:
        tmp.unlink(missing_ok=True)


def test_validator_rejects_duplicate_legacy_id():
    import shutil
    tmp = REPO / "data" / "development" / "human_review" / "_tmp_review.json"
    shutil.copy(CANONICAL, tmp)
    try:
        doc = json.loads(tmp.read_text(encoding="utf-8"))
        # Make a duplicate legacy id (legitimately preserve hash)
        doc["records"][1]["legacy_record_id"] = doc["records"][0]["legacy_record_id"]
        doc["records"][1]["sample_id"] = f"estg_{doc['records'][0]['legacy_record_id']:06d}"
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        res = subprocess.run(
            [sys.executable, str(VALIDATE), "--path", str(tmp), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        out = json.loads(res.stdout)
        assert out["format_valid"] is False
    finally:
        tmp.unlink(missing_ok=True)


def test_validator_rejects_pre_filled_old_gold():
    import shutil
    tmp = REPO / "data" / "development" / "human_review" / "_tmp_review.json"
    shutil.copy(CANONICAL, tmp)
    try:
        doc = json.loads(tmp.read_text(encoding="utf-8"))
        doc["records"][0]["old_gold_sources"][0]["pre_filled"] = True
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        res = subprocess.run(
            [sys.executable, str(VALIDATE), "--path", str(tmp), "--json"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        out = json.loads(res.stdout)
        assert out["format_valid"] is False
    finally:
        tmp.unlink(missing_ok=True)


def test_schema_is_present_and_loadable():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["title"].startswith("EStG-150 Canonical")
    assert "records" in schema["properties"]
    assert "additionalProperties" in schema
    assert schema["additionalProperties"] is False

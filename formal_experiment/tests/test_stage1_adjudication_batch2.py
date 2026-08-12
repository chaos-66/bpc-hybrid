"""Batch-2 focused tests for the S1.5 adjudication chain (gdpr_2).

Every tamper is applied to the real artifact, asserted to FAIL the chain
verifier, then restored byte-exactly. Also verifies the batch-2 value
guardrails: the whole-"if..." sentence must NOT be smuggled into a
business_object, outer quotes must NOT be added, and 'purposses' must NOT
be silently corrected to 'purposes'.
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
ASSET = (ROOT / "outputs" / "development" / "human_review"
         / "stage1_adjudications" / "gdpr_2_consent_to_use_the_data")


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_b2_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_b2_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    # write_bytes keeps LF line endings (matches the review tool's
    # byte-stable atomic save; write_text would produce CRLF on Windows and
    # break hash comparisons)
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def test_batch2_chain_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    assert r["adjudicated_processes"] == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data"]
    # batch-2 derives 72 fields from 24 activities
    assert any("field count derived (72)" in c["name"]
               for c in r["checks"])
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert doc["review_summary"]["adjudicated_records"] == 2
    assert doc["review_summary"]["resolved_label_fields"] == 90
    assert doc["review_summary"]["freeze_ready"] is False


def test_batch2_actor_tamper() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    orig = json.dumps(rec["label_annotations"][0]["actor"])
    try:
        rec["label_annotations"][0]["actor"]["value"] = "TAMPERED"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec["label_annotations"][0]["actor"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_batch2_business_object_tamper() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    orig = json.dumps(rec["label_annotations"][10]["business_object"])
    try:
        rec["label_annotations"][10]["business_object"]["value"] = "X"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec["label_annotations"][10]["business_object"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_batch2_if_sentence_smuggled_as_business_object() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    orig = json.dumps(rec["label_annotations"][9]["business_object"])
    try:
        rec["label_annotations"][9]["business_object"]["value"] = (
            "if data has been obtained from Data Subject")
        _rewrite(CORRECTION, doc)
        assert _verified() is False  # the whole-if sentence must not be Gold
    finally:
        rec["label_annotations"][9]["business_object"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_batch2_outer_quotes_added() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    orig = json.dumps(rec["label_annotations"][3]["business_object"])
    try:
        rec["label_annotations"][3]["business_object"]["value"] = (
            '"existence of the right to withdraw"')
        _rewrite(CORRECTION, doc)
        assert _verified() is False  # outer quotes must not be added
    finally:
        rec["label_annotations"][3]["business_object"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_batch2_purposses_must_not_be_corrected() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    la = next(x for x in rec["label_annotations"]
              if x["activity_id"] == "sid-DE86B81E-D959-47C5-A6F6-C6C4308FBDC1")
    orig = json.dumps(la["business_object"])
    try:
        la["business_object"]["value"] = "processing purposes"  # 'corrected'
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        la["business_object"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True
    # and the original value stays 'processing purposses'
    doc2 = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec2 = next(r for r in doc2["records"]
                if r["process_id"] == "gdpr_2_consent_to_use_the_data")
    la2 = next(x for x in rec2["label_annotations"]
               if x["activity_id"] == "sid-DE86B81E-D959-47C5-A6F6-C6C4308FBDC1")
    assert la2["business_object"]["value"] == "processing purposses"


def test_batch2_candidate_tamper() -> None:
    dec_path = ASSET / "decision_v1.json"
    orig = dec_path.read_bytes()
    dec = json.loads(orig.decode("utf-8"))
    try:
        dec["structure_annotation"]["gold_process_record"]["activities"][0][
            "name"] = "Tampered"
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


def test_batch2_import_hash_tamper() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["import_record_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_chain_broken_between_batches() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["before_correction_sha256"] = "0" * 64  # break 1->2 link
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_unadjudicated_process_modified() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_3_right_to_access")
    orig = rec["review_state"]
    try:
        rec["review_state"] = "reviewed"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec["review_state"] = orig
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_summary_forgery_and_freeze() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    orig = json.dumps(doc["review_summary"])
    try:
        doc["review_summary"]["resolved_label_fields"] = 135
        doc["review_summary"]["freeze_ready"] = True
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        doc["review_summary"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True

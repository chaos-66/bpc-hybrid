"""Batch-6 focused tests for the S1.5 adjudication chain (gdpr_6).

Focus: the E2 raw_label trailing newline (preserved in evidence) vs the
clean semantic values (no newline / trailing whitespace) -- an explicit
user adjudication, not evidence cleaning. Every tamper is applied to the
real artifact, asserted to FAIL the chain verifier, then restored
byte-exactly.
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
PROCESS_RECORDS = (ROOT / "data" / "development" / "human_review"
                   / "stage1_gdpr7_process_records_v1.json")
ASSET = (ROOT / "outputs" / "development" / "human_review"
         / "stage1_adjudications" / "gdpr_6_right_to_rectify")

E1 = "sid-2D1BF282-F735-4BE0-996F-4D9C7DBED814"
E2 = "sid-F9E3B912-20D2-4AD2-B92F-811216B4F746"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_b6_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_b6_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def _rec(doc):
    return next(r for r in doc["records"]
                if r["process_id"] == "gdpr_6_right_to_rectify")


def test_batch6_chain_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    assert r["adjudicated_processes"] == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
        "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
        "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify"]
    assert any("field count derived (6)" in c["name"] for c in r["checks"])
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert doc["review_summary"]["adjudicated_records"] == 6
    assert doc["review_summary"]["resolved_label_fields"] == 129
    assert doc["review_summary"]["freeze_ready"] is False


def test_e2_raw_label_newline_preserved() -> None:
    """The trailing newline is part of the raw evidence (blank raw_label and
    locked candidate name), while the semantic values are clean."""
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == E2)
    assert la["raw_label"].endswith("\n")
    assert "\n" not in la["action"]["value"]
    assert "\n" not in la["business_object"]["value"]
    assert not la["action"]["value"].strip().endswith(" ")
    recs = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))["records"]
    cand = next(r for r in recs
                if r["process_id"] == "gdpr_6_right_to_rectify")
    e2 = next(a for a in cand["activities"] if a["id"] == E2)
    assert e2["name"].endswith("\n")


def test_remove_e2_raw_label_newline_fails() -> None:
    """Deleting the trailing newline from the correction's raw_label must
    fail (raw evidence must stay byte-stable)."""
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == E2)
    try:
        la["raw_label"] = la["raw_label"].rstrip("\n")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_action_with_newline_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == E2)
    try:
        la["action"]["value"] = "Communicate\n"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_business_object_with_newline_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == E2)
    try:
        la["business_object"]["value"] = "the rectification "
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_business_object_without_article_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == E2)
    try:
        la["business_object"]["value"] = "rectification"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == E2)
    assert la["business_object"]["value"] == "the rectification"


def test_generic_tamper_and_chain() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        la = next(x for x in _rec(doc)["label_annotations"]
                  if x["activity_id"] == E1)
        la["action"]["value"] = "Fix"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    # activity id extra
    imp_path = ASSET / "import_record_v1.json"
    orig_i = imp_path.read_bytes()
    imp = json.loads(orig_i.decode("utf-8"))
    try:
        imp["records"][0]["label_annotations"].append({
            "activity_id": "sid-FAKE", "actor": {"status": "present",
                                                 "value": "X"},
            "action": {"status": "present", "value": "X"},
            "business_object": {"status": "present", "value": "X"}})
        _rewrite(imp_path, imp)
        assert _verified() is False
    finally:
        imp_path.write_bytes(orig_i)
    assert _verified() is True
    # decision tamper
    dec_path = ASSET / "decision_v1.json"
    orig_d = dec_path.read_bytes()
    dec = json.loads(orig_d.decode("utf-8"))
    try:
        dec["structure_annotation"]["gold_process_record"]["activities"][0][
            "name"] = "X"
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig_d)
    assert _verified() is True
    # chain break 5->6
    man_path = ASSET / "manifest.json"
    orig_m = man_path.read_bytes()
    man = json.loads(orig_m.decode("utf-8"))
    try:
        man["before_correction_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig_m)
    assert _verified() is True


def test_earlier_batches_and_gdpr7() -> None:
    import subprocess
    for pid in ("gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
                "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
                "gdpr_5_right_to_withdraw"):
        for name in ("decision_v1.json", "import_record_v1.json",
                     "manifest.json"):
            diff = subprocess.run(
                ["git", "diff", "--quiet", "HEAD", "--",
                 f"formal_experiment/outputs/development/human_review/"
                 f"stage1_adjudications/{pid}/{name}"],
                capture_output=True)
            assert diff.returncode == 0, f"{pid}/{name} changed"
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec7 = next(r for r in doc["records"]
                if r["process_id"] == "gdpr_7_right_to_be_forgotten")
    assert rec7["review_state"] == "unreviewed"
    assert all(la["actor"]["status"] == "unreviewed"
               and la["actor"]["value"] is None
               for la in rec7["label_annotations"])


def test_summary_forgery_and_freeze() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["review_summary"]["resolved_label_fields"] = 135
        doc["review_summary"]["freeze_ready"] = True
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True

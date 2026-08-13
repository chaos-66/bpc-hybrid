"""Batch-4 focused tests for the S1.5 adjudication chain (gdpr_4).

Focus: gdpr_3/gdpr_4 share the raw XML process id but must remain fully
independent formal samples (dataset identity, source, candidate, evidence
assets). Every tamper is applied to the real artifact, asserted to FAIL the
chain verifier, then restored byte-exactly.
"""

from __future__ import annotations

import hashlib
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
ADJ = ROOT / "outputs" / "development" / "human_review" / "stage1_adjudications"
ASSET4 = ADJ / "gdpr_4_right_of_portability"
ASSET3 = ADJ / "gdpr_3_right_to_access"

C1 = "sid-2E045BBD-9F82-497F-8458-49AA9129F991"
C3 = "sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_b4_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_b4_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def test_batch4_chain_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    assert r["adjudicated_processes"] == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
        "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
        "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify"]
    assert any("field count derived (9)" in c["name"] for c in r["checks"])
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert doc["review_summary"]["adjudicated_records"] == 6
    assert doc["review_summary"]["resolved_label_fields"] == 129
    assert doc["review_summary"]["freeze_ready"] is False


def test_gdpr4_identity_independent_of_gdpr3() -> None:
    """Shared raw XML process id must not merge gdpr_3/gdpr_4 formal
    identities: dataset process_id, source and pool binding belong to each
    process separately."""
    recs = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))["records"]
    r3 = next(x for x in recs if x["process_id"] == "gdpr_3_right_to_access")
    r4 = next(x for x in recs
              if x["process_id"] == "gdpr_4_right_of_portability")
    # distinct formal identities and distinct sources
    assert r4["process_id"] == "gdpr_4_right_of_portability"
    assert r4["source"]["input_id"] == "gdpr_4_right_of_portability"
    assert r4["source"]["sha256"] != r3["source"]["sha256"]
    assert r4["pools"][0]["process_ref"] == "gdpr_4_right_of_portability"
    assert r4["pools"][0]["process_ref"] != r3["pools"][0]["process_ref"]
    # same activities structure but the same activity IDs are fine as long
    # as lookups are process-scoped (both candidates record them)


def test_gdpr4_gold_bound_to_gdpr4_candidate() -> None:
    dec = json.loads((ASSET4 / "decision_v1.json").read_text(encoding="utf-8"))
    gold = dec["structure_annotation"]["gold_process_record"]
    assert gold["process_id"] == "gdpr_4_right_of_portability"
    assert gold["source"]["input_id"] == "gdpr_4_right_of_portability"
    assert gold["pools"][0]["process_ref"] == "gdpr_4_right_of_portability"
    assert dec["evidence_hashes"]["candidate_process_record_sha256"] == (
        "a1d77e897e80491c9f47725c812917ae98d9aca143b6478cbd62b9bff5727446")


def test_gdpr3_assets_byte_unchanged_and_independent() -> None:
    """gdpr_3 decision/import/manifest must be byte-identical to the
    committed batch-3 versions, and gdpr_4 assets must differ."""
    import subprocess
    for name in ("decision_v1.json", "import_record_v1.json", "manifest.json"):
        # autocrlf-aware: compare through git itself (worktree vs HEAD)
        diff = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--",
             "formal_experiment/outputs/development/human_review/"
             "stage1_adjudications/gdpr_3_right_to_access/" + name],
            capture_output=True)
        assert diff.returncode == 0, f"gdpr_3 {name} changed"
    for name in ("decision_v1.json", "import_record_v1.json", "manifest.json"):
        assert (ASSET3 / name).read_bytes() != (ASSET4 / name).read_bytes(), \
            f"{name} must be independent"


def test_cross_process_activity_match_fails_closed() -> None:
    """A cross-process activity match (gdpr_4 correction edited with the
    gdpr_3 process identity) must fail the verifier. Byte-level restore:
    renaming the process id makes gdpr_4 unfindable, so a content-level
    restore would miss it."""
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_4_right_of_portability")
    try:
        rec["process_id"] = "gdpr_3_right_to_access"  # wrong binding
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_gdpr3_candidate_copied_to_gdpr4_fails() -> None:
    """Copying the gdpr_3 candidate object into gdpr_4's decision must fail
    (candidate hash binding + gold identity)."""
    dec_path = ASSET4 / "decision_v1.json"
    orig = dec_path.read_bytes()
    dec = json.loads(orig.decode("utf-8"))
    d3 = json.loads((ASSET3 / "decision_v1.json").read_text(encoding="utf-8"))
    try:
        dec["structure_annotation"]["gold_process_record"] = json.loads(
            json.dumps(d3["structure_annotation"]["gold_process_record"]))
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


def test_gdpr4_source_misbound_to_gdpr3_fails() -> None:
    dec_path = ASSET4 / "decision_v1.json"
    orig = dec_path.read_bytes()
    dec = json.loads(orig.decode("utf-8"))
    try:
        dec["structure_annotation"]["gold_process_record"]["source"]["sha256"] = \
            "d6e48d09bf821f700813bff5806f59323a7dd266223a6bb1a1eb45647bbbd3b1"  # gdpr_3
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


def test_c1_narrowing_and_c3_split_fail() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_4_right_of_portability")
    la1 = next(x for x in rec["label_annotations"] if x["activity_id"] == C1)
    orig1 = json.dumps(la1["business_object"])
    try:
        la1["business_object"]["value"] = "available data"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        la1["business_object"] = json.loads(orig1)
        _rewrite(CORRECTION, doc)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_4_right_of_portability")
    la3 = next(x for x in rec["label_annotations"] if x["activity_id"] == C3)
    orig3 = json.dumps(la3["business_object"])
    try:
        la3["business_object"]["value"] = "data"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        la3["business_object"] = json.loads(orig3)
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_label_and_activity_tamper_fail() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = next(r for r in doc["records"]
               if r["process_id"] == "gdpr_4_right_of_portability")
    orig = json.dumps(rec["label_annotations"][0]["actor"])
    try:
        rec["label_annotations"][0]["actor"]["value"] = "X"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec["label_annotations"][0]["actor"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True
    imp_path = ASSET4 / "import_record_v1.json"
    orig_i = imp_path.read_bytes()
    imp = json.loads(orig_i.decode("utf-8"))
    try:
        imp["records"][0]["label_annotations"] = \
            imp["records"][0]["label_annotations"][:2]
        _rewrite(imp_path, imp)
        assert _verified() is False
    finally:
        imp_path.write_bytes(orig_i)
    assert _verified() is True


def test_candidate_decision_import_hash_tamper_and_chain_break() -> None:
    dec_path = ASSET4 / "decision_v1.json"
    orig_d = dec_path.read_bytes()
    dec = json.loads(orig_d.decode("utf-8"))
    try:
        dec["structure_annotation"]["gold_process_record"]["activities"][0][
            "name"] = "Tampered"
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig_d)
    assert _verified() is True
    man_path = ASSET4 / "manifest.json"
    orig_m = man_path.read_bytes()
    man = json.loads(orig_m.decode("utf-8"))
    try:
        man["import_record_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig_m)
    assert _verified() is True
    man = json.loads(man_path.read_text(encoding="utf-8"))
    try:
        man["before_correction_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig_m)
    assert _verified() is True


def test_summary_unadjudicated_freeze() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    orig = json.dumps(doc["review_summary"])
    try:
        doc["review_summary"]["freeze_ready"] = True
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        doc["review_summary"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec5 = next(r for r in doc["records"]
                if r["process_id"] == "gdpr_5_right_to_withdraw")
    orig5 = rec5["review_state"]
    try:
        rec5["review_state"] = "reviewed"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec5["review_state"] = orig5
        _rewrite(CORRECTION, doc)
    assert _verified() is True

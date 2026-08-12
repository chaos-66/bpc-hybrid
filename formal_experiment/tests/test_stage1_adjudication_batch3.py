"""Batch-3 focused tests for the S1.5 adjudication chain (gdpr_3).

Every tamper is applied to the real artifact, asserted to FAIL the chain
verifier, then restored byte-exactly. Also verifies the batch-3 value
guardrails (no narrowing of C1's business object, no splitting of C3's
coordinated object) and the presentation-only type correction (C1/C2 are
subProcess, C3 is task in the LOCKED candidate; the earlier read-only
package table had shown them as tasks -- a presentation error only, never
written back).
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
         / "stage1_adjudications" / "gdpr_3_right_to_access")

C1 = "sid-2E045BBD-9F82-497F-8458-49AA9129F991"
C2 = "sid-7CABF962-BFAE-4BFD-9C33-E7ED63548824"
C3 = "sid-BB84BABD-20ED-4C97-B755-BDA101C57A8D"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_b3_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_b3_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def _rec(doc):
    return next(r for r in doc["records"]
                if r["process_id"] == "gdpr_3_right_to_access")


def test_batch3_chain_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    assert r["adjudicated_processes"] == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
        "gdpr_3_right_to_access", "gdpr_4_right_of_portability"]
    assert any("field count derived (9)" in c["name"] for c in r["checks"])
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert doc["review_summary"]["adjudicated_records"] == 4
    assert doc["review_summary"]["resolved_label_fields"] == 108
    assert doc["review_summary"]["freeze_ready"] is False


def test_candidate_real_types_subprocess_task() -> None:
    """Presentation-only correction: the locked candidate records C1/C2 as
    subProcess and C3 as task; the earlier read-only package table wrongly
    showed tasks -- never written back to the candidate."""
    recs = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))["records"]
    cand = next(r for r in recs if r["process_id"] == "gdpr_3_right_to_access")
    types = {a["id"]: a["type"] for a in cand["activities"]}
    assert types[C1] == "subProcess"
    assert types[C2] == "subProcess"
    assert types[C3] == "task"


def test_c1_business_object_not_narrowed() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = _rec(doc)
    la = next(x for x in rec["label_annotations"] if x["activity_id"] == C1)
    orig = json.dumps(la["business_object"])
    try:
        la["business_object"]["value"] = "available data"  # narrowed
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        la["business_object"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True
    assert la["business_object"]["value"] == "available data of the data subject"


def test_c3_business_object_not_split() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = _rec(doc)
    la = next(x for x in rec["label_annotations"] if x["activity_id"] == C3)
    orig = json.dumps(la["business_object"])
    try:
        la["business_object"]["value"] = "data"  # lost 'and elaborations'
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        la["business_object"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True
    assert la["business_object"]["value"] == "data and elaborations"


def test_batch3_actor_action_tamper() -> None:
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec = _rec(doc)
    orig = json.dumps(rec["label_annotations"][0]["action"])
    try:
        rec["label_annotations"][0]["action"]["value"] = "Fetch"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec["label_annotations"][0]["action"] = json.loads(orig)
        _rewrite(CORRECTION, doc)
    assert _verified() is True


def test_activity_id_missing_extra() -> None:
    imp_path = ASSET / "import_record_v1.json"
    orig = imp_path.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["records"][0]["label_annotations"] = \
            doc["records"][0]["label_annotations"][:2]  # missing
        _rewrite(imp_path, doc)
        assert _verified() is False
    finally:
        imp_path.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["records"][0]["label_annotations"].append({
            "activity_id": "sid-FAKE", "actor": {"status": "present",
                                                 "value": "X"},
            "action": {"status": "present", "value": "X"},
            "business_object": {"status": "present", "value": "X"}})
        _rewrite(imp_path, doc)
        assert _verified() is False
    finally:
        imp_path.write_bytes(orig)
    assert _verified() is True


def test_candidate_tamper_and_hash() -> None:
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
    man_path = ASSET / "manifest.json"
    orig_m = man_path.read_bytes()
    man = json.loads(orig_m.decode("utf-8"))
    try:
        man["candidate_process_record_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig_m)
    assert _verified() is True


def test_import_manifest_hash_tamper_and_chain_break() -> None:
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
    man = json.loads(man_path.read_text(encoding="utf-8"))
    try:
        man["before_correction_sha256"] = "0" * 64  # break 2->3 link
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_summary_forgery_unadjudicated_freeze() -> None:
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
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec4 = next(r for r in doc["records"]
                if r["process_id"] == "gdpr_4_right_of_portability")
    orig4 = rec4["review_state"]
    try:
        rec4["review_state"] = "reviewed"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        rec4["review_state"] = orig4
        _rewrite(CORRECTION, doc)
    assert _verified() is True

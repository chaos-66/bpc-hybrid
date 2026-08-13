"""Batch-7 focused tests for the S1.5 adjudication chain (gdpr_7, 7/7).

Focus: the explicit user adjudication for gdpr_7_right_to_be_forgotten:
  - F1 (sid-7E4D1233...): actor=Data Controller, action=Communication,
    business_object=data subject  (the preposition 'with' does NOT enter the
    business_object; the raw label stays 'Communication with data subject')
  - F2 (sid-96C77979...): actor=Data Controller, action=Retrieve,
    business_object=data  (standard verb-object split)

Every tamper is applied to the real artifact, asserted to FAIL the chain
verifier, then restored byte-exactly; the verifier must pass afterwards.
Also covers identity/structure tampering (source/candidate/membership
hashes, process_id, previous chain node, sequence-flow/structural candidate)
and the seven-batch chain invariants (delete / swap / duplicate / broken
before-after / final mismatch).
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
         / "stage1_adjudications" / "gdpr_7_right_to_be_forgotten")
AUTH_MANIFEST = (ROOT / "outputs" / "reports"
                 / "s1_5_review_surface_authorization_v1.manifest.json")

F1 = "sid-7E4D1233-F8F9-4883-9711-2B148DA4EF67"
F2 = "sid-96C77979-3657-4A97-91E3-AF3186FAD889"

EXPECTED = {
    "candidate": "250bdecd830806e43549e6c60d84848d57a85539cce25af88330d4a4d8c98375",
    "source": "8c5b05e3093c84336b3faa2df74cb50afd9f86bed51a10717d9ab01c6f830da0",
    "membership": "e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d",
}


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_b7_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_b7_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def _rec(doc):
    return next(r for r in doc["records"]
                if r["process_id"] == "gdpr_7_right_to_be_forgotten")


def _la(doc, activity_id: str):
    return next(x for x in _rec(doc)["label_annotations"]
                if x["activity_id"] == activity_id)


# ---------------------------------------------------------------------------
# exact values
# ---------------------------------------------------------------------------

def test_batch7_chain_verified_and_exact_values() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    assert r["adjudicated_processes"] == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
        "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
        "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
        "gdpr_7_right_to_be_forgotten"]
    names = [c["name"] for c in r["checks"]]
    assert any("adjudication completeness fact consistent (freeze_ready "
               "derived)" in n for n in names)
    assert any("formal gold freeze NOT authorized" in n for n in names)
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert doc["review_summary"] == {
        "records": 7, "adjudicated_records": 7, "label_fields": 135,
        "resolved_label_fields": 135, "freeze_ready": True}
    rec = _rec(doc)
    assert rec["review_state"] == "adjudicated"
    assert rec["structure_annotation"]["decision"] == "accepted_candidate"
    # F1 exact
    f1 = _la(doc, F1)
    assert f1["actor"] == {"status": "present", "value": "Data Controller"}
    assert f1["action"] == {"status": "present", "value": "Communication"}
    assert f1["business_object"] == {"status": "present",
                                     "value": "data subject"}
    assert f1["raw_label"] == "Communication with data subject"
    # F2 exact
    f2 = _la(doc, F2)
    assert f2["actor"] == {"status": "present", "value": "Data Controller"}
    assert f2["action"] == {"status": "present", "value": "Retrieve"}
    assert f2["business_object"] == {"status": "present", "value": "data"}
    assert f2["raw_label"] == "Retrieve data"
    # locked candidate XML types (cross-checked against the real XML)
    recs = json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))["records"]
    cand = next(r for r in recs
                if r["process_id"] == "gdpr_7_right_to_be_forgotten")
    by_id = {a["id"]: a for a in cand["activities"]}
    assert by_id[F1]["type"] == "subProcess"
    assert by_id[F2]["type"] == "subProcess"


def test_lock_hashes_in_manifest() -> None:
    man = json.loads((ASSET / "manifest.json").read_text(encoding="utf-8"))
    assert man["before_correction_sha256"] == \
        "947487b19e91da5db6c9d971c5cd3f10e0e8d83c728e4dcba13497ec3a465e38"
    assert man["after_correction_sha256"] == \
        "6a9c055a8f92c04aa5c44c92d4653bad128f048103fd16584754c121cb0ba18e"
    assert man["prev_process"] == "gdpr_6_right_to_rectify"
    assert man["candidate_process_record_sha256"] == EXPECTED["candidate"]
    assert man["bpmn_source_sha256"] == EXPECTED["source"]
    assert man["membership_payload_sha256"] == EXPECTED["membership"]
    assert man["gold_freeze_authorized"] is False
    assert man["llm_api_calls"] == 0


# ---------------------------------------------------------------------------
# F1 semantic tampering (must fail)
# ---------------------------------------------------------------------------

def test_f1_action_tamper_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["action"]["value"] = "Notify"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f1_object_with_preposition_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["business_object"]["value"] = "with data subject"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f1_object_whitespace_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["business_object"]["value"] = " data subject"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["business_object"]["value"] = "data subject "
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f1_actor_missing_or_rewritten_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["actor"] = {"status": "unreviewed", "value": None}
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["actor"]["value"] = "Data Processor"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f1_activity_id_replace_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        f1 = _la(doc, F1)
        f1["activity_id"] = F2  # swap ids: mismatch vs candidate set/order
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f1_raw_label_rewrite_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["raw_label"] = "Communication with data subject "
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


# ---------------------------------------------------------------------------
# F2 semantic tampering (must fail)
# ---------------------------------------------------------------------------

def test_f2_merged_action_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F2)["action"]["value"] = "Retrieve data"
        _la(doc, F2)["business_object"]["value"] = None
        _la(doc, F2)["business_object"]["status"] = "absent"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f2_object_missing_or_rewritten_fails() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F2)["business_object"] = {"status": "unreviewed",
                                           "value": None}
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F2)["business_object"]["value"] = "personal data"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_f2_activity_id_or_type_replace_fails() -> None:
    # activity id swap in the decision asset
    dec_path = ASSET / "decision_v1.json"
    orig = dec_path.read_bytes()
    dec = json.loads(orig.decode("utf-8"))
    try:
        dec["label_annotations"][1]["activity_id"] = F1
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True
    # XML type tamper in the locked gold copy (subProcess -> task)
    dec = json.loads(orig.decode("utf-8"))
    try:
        for a in dec["structure_annotation"]["gold_process_record"][
                "activities"]:
            if a["id"] == F2:
                a["type"] = "task"
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


# ---------------------------------------------------------------------------
# identity / structure tampering (must fail)
# ---------------------------------------------------------------------------

def test_source_hash_tamper_fails() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["bpmn_source_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_candidate_hash_tamper_fails() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["candidate_process_record_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_membership_payload_tamper_fails() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["membership_payload_sha256"] = "1" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_process_id_tamper_fails() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["process_id"] = "gdpr_7_wrong"
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_previous_chain_node_tamper_fails() -> None:
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["before_correction_sha256"] = "0" * 64
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_sequence_flow_structure_tamper_fails() -> None:
    dec_path = ASSET / "decision_v1.json"
    orig = dec_path.read_bytes()
    dec = json.loads(orig.decode("utf-8"))
    try:
        flows = dec["structure_annotation"]["gold_process_record"][
            "sequence_flows"]
        flows[0]["source_ref"], flows[0]["target_ref"] = \
            flows[0]["target_ref"], flows[0]["source_ref"]
        _rewrite(dec_path, dec)
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


def test_gold_freeze_authorization_force_fails() -> None:
    auth_path = AUTH_MANIFEST
    orig = auth_path.read_bytes()
    auth = json.loads(orig.decode("utf-8"))
    try:
        auth["authorization_scope"]["gold_freeze_authorized"] = True
        _rewrite(auth_path, auth)
        assert _verified() is False
    finally:
        auth_path.write_bytes(orig)
    assert _verified() is True


# ---------------------------------------------------------------------------
# seven-batch chain invariants (must fail)
# ---------------------------------------------------------------------------

def test_batch_delete_fails() -> None:
    dec_path = ASSET / "decision_v1.json"
    orig = dec_path.read_bytes()
    try:
        dec_path.unlink()
        assert _verified() is False
    finally:
        dec_path.write_bytes(orig)
    assert _verified() is True


def test_batch_duplicate_predecessor_fails() -> None:
    """Reusing batch-6's before hash as batch-7's before hash would share a
    predecessor (fork) and break the sequential chain."""
    b6 = (ROOT / "outputs" / "development" / "human_review"
          / "stage1_adjudications" / "gdpr_6_right_to_rectify"
          / "manifest.json")
    b6_man = json.loads(b6.read_text(encoding="utf-8"))
    man_path = ASSET / "manifest.json"
    orig = man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["before_correction_sha256"] = b6_man["before_correction_sha256"]
        _rewrite(man_path, man)
        assert _verified() is False
    finally:
        man_path.write_bytes(orig)
    assert _verified() is True


def test_mid_chain_break_fails() -> None:
    """A broken before/after hash in the MIDDLE of the chain (batch 4) must
    fail, not just the last batch."""
    b4_man_path = (ROOT / "outputs" / "development" / "human_review"
                   / "stage1_adjudications" / "gdpr_4_right_of_portability"
                   / "manifest.json")
    orig = b4_man_path.read_bytes()
    man = json.loads(orig.decode("utf-8"))
    try:
        man["after_correction_sha256"] = "0" * 64
        _rewrite(b4_man_path, man)
        assert _verified() is False
    finally:
        b4_man_path.write_bytes(orig)
    assert _verified() is True


def test_final_correction_mismatch_fails() -> None:
    """The final on-disk correction must equal the seven-batch replay."""
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _la(doc, F1)["actor"]["value"] = "Data Controller "
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_swap_batch_process_fails() -> None:
    """Swapping gdpr_7's import payload onto gdpr_6's slot must fail."""
    b6_imp = (ROOT / "outputs" / "development" / "human_review"
              / "stage1_adjudications" / "gdpr_6_right_to_rectify"
              / "import_record_v1.json")
    orig6 = b6_imp.read_bytes()
    imp = json.loads(orig6.decode("utf-8"))
    try:
        imp["records"][0]["process_id"] = "gdpr_7_right_to_be_forgotten"
        _rewrite(b6_imp, imp)
        assert _verified() is False
    finally:
        b6_imp.write_bytes(orig6)
    assert _verified() is True

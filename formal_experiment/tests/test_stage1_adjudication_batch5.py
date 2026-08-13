"""Batch-5 focused tests for the S1.5 adjudication chain (gdpr_5).

Real semantic-boundary guardrails: compound actions (Stop running / Stop
using), if/that clause boundaries (D3/D5), preserved surface form (D4
'the withdraw'). Every tamper is applied to the real artifact, asserted to
FAIL the chain verifier, then restored byte-exactly.
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
         / "stage1_adjudications" / "gdpr_5_right_to_withdraw")

D1 = "sid-07817A82-69C2-45A1-9ABC-277F17D93747"
D2 = "sid-1A48D305-CB15-4C57-A988-B39ED62DE531"
D3 = "sid-A9B97678-298C-4EE7-82A3-836179299938"
D4 = "sid-BB5F1C3A-DCD5-4C17-90CF-503D23B048FB"
D5 = "sid-DFB327FD-78D3-4012-8BAC-82AF87341389"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1ad_b5_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1ad_b5_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def _rec(doc):
    return next(r for r in doc["records"]
                if r["process_id"] == "gdpr_5_right_to_withdraw")


def _tamper_field(correction_doc, activity_id, field, new_value) -> None:
    rec = _rec(correction_doc)
    la = next(x for x in rec["label_annotations"]
              if x["activity_id"] == activity_id)
    la[field]["value"] = new_value


def test_batch5_chain_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    assert r["adjudicated_processes"] == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
        "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
        "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
        "gdpr_7_right_to_be_forgotten"]
    assert any("field count derived (15)" in c["name"] for c in r["checks"])
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    # post-Batch-7: 7/7 adjudicated, 135/135 resolved, freeze_ready true
    assert doc["review_summary"]["adjudicated_records"] == 7
    assert doc["review_summary"]["resolved_label_fields"] == 135
    assert doc["review_summary"]["freeze_ready"] is True


def test_compound_action_stop_running() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D1, "action", "Stop")  # split compound
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == D1)
    assert la["action"]["value"] == "Stop running"
    assert la["business_object"]["value"] == "BPs using withdrawn data"


def test_d1_object_back_to_p1_remainder() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D1, "business_object",
                      "running BPs using withdrawn data")  # P1 remainder
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_compound_action_stop_using() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D2, "action", "Stop")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == D2)
    assert la["action"]["value"] == "Stop using"
    assert la["business_object"]["value"] == "withdrawn data"


def test_d2_object_back_to_using_phrase() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D2, "business_object", "using withdrawn data")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True


def test_d3_full_if_clause_as_object() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D3, "business_object",
                      "if withdrawn data are relevant")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == D3)
    assert la["business_object"]["value"] == "withdrawn data"


def test_d4_withdraw_surface_form() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D4, "business_object", "withdrawal")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    try:
        _tamper_field(doc, D4, "business_object", "withdraw")  # no article
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == D4)
    assert la["business_object"]["value"] == "the withdraw"


def test_d5_that_clause_boundary() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D5, "business_object",
                      "the user that the withdraw will stop all running BPs")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    try:
        _tamper_field(doc, D5, "business_object",
                      "the withdraw will stop all running BPs")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    try:
        _tamper_field(doc, D5, "business_object", "all running BPs")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    la = next(x for x in _rec(doc)["label_annotations"]
              if x["activity_id"] == D5)
    assert la["business_object"]["value"] == "the user"


def test_generic_tampers_and_chain() -> None:
    # actor tamper
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        _tamper_field(doc, D1, "actor", "X")
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True
    # activity id missing
    imp_path = ASSET / "import_record_v1.json"
    orig_i = imp_path.read_bytes()
    imp = json.loads(orig_i.decode("utf-8"))
    try:
        imp["records"][0]["label_annotations"] = \
            imp["records"][0]["label_annotations"][:4]
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
    # chain break 4->5
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


def test_earlier_batches_assets_unchanged() -> None:
    import subprocess
    for pid in ("gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
                "gdpr_3_right_to_access", "gdpr_4_right_of_portability"):
        for name in ("decision_v1.json", "import_record_v1.json",
                     "manifest.json"):
            diff = subprocess.run(
                ["git", "diff", "--quiet", "HEAD", "--",
                 f"formal_experiment/outputs/development/human_review/"
                 f"stage1_adjudications/{pid}/{name}"],
                capture_output=True)
            assert diff.returncode == 0, f"{pid}/{name} changed"


def test_unadjudicated_not_prefilled() -> None:
    """Post-Batch-7: gdpr_7 is fully adjudicated (covered in depth by the
    batch-7 focused tests); before Batch 7 it was unreviewed with no value
    prefilled."""
    doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    rec7 = next(r for r in doc["records"]
                if r["process_id"] == "gdpr_7_right_to_be_forgotten")
    assert rec7["review_state"] == "adjudicated"
    assert all(la["actor"]["status"] == "present"
               and la["actor"]["value"] == "Data Controller"
               for la in rec7["label_annotations"])


def test_summary_forgery_and_freeze() -> None:
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        # forge an inconsistent count (real resolved count is 135) and flip
        # freeze_ready off; both must fail
        doc["review_summary"]["resolved_label_fields"] = 134
        doc["review_summary"]["freeze_ready"] = False
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True

"""Focused tests for the published Stage 1 Process Gold (2026-08-13,
user-authorized freeze + publication).

Every tamper is applied to the real artifact, asserted to FAIL the gold
verifier, then restored byte-exactly; the verifier must pass afterwards.
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

VERIFIER_PATH = ROOT / "scripts" / "verify_stage1_process_gold.py"
GOLD = ROOT / "data" / "gold" / "stage1" / "process_records" \
    / "stage1_process_gold_v1.json"
GOLD_MANIFEST = ROOT / "data" / "gold" / "stage1" / "manifest.json"
AUTH = ROOT / "outputs" / "reports" \
    / "s1_5_process_gold_freeze_authorization_v1.manifest.json"
CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")

F1 = "sid-7E4D1233-F8F9-4883-9711-2B148DA4EF67"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1gold_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1gold_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def _g7(doc):
    return next(r for r in doc["records"]
                if r["process_id"] == "gdpr_7_right_to_be_forgotten")


def test_gold_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    assert len(gold["records"]) == 7
    assert gold["schema_version"] == "stage1_process_gold@1.0.0"
    # every record == correction record
    corr = json.loads(CORRECTION.read_text(encoding="utf-8"))
    assert {r["process_id"] for r in gold["records"]} == \
        {r["process_id"] for r in corr["records"]}
    assert all(next(r for r in corr["records"]
                    if r["process_id"] == g["process_id"]) == g
               for g in gold["records"])
    # exact F1 semantics preserved in the published Gold
    f1 = next(la for la in _g7(gold)["label_annotations"]
              if la["activity_id"] == F1)
    assert f1["raw_label"] == "Communication with data subject"
    assert f1["business_object"]["value"] == "data subject"
    assert f1["action"]["value"] == "Communication"


def test_gold_value_tamper_fails() -> None:
    orig = GOLD.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        f1 = next(la for la in _g7(doc)["label_annotations"]
                  if la["activity_id"] == F1)
        f1["business_object"]["value"] = "with data subject"
        _rewrite(GOLD, doc)
        assert _verified() is False
    finally:
        GOLD.write_bytes(orig)
    assert _verified() is True


def test_gold_record_delete_fails() -> None:
    orig = GOLD.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["records"] = [r for r in doc["records"]
                          if r["process_id"] != "gdpr_7_right_to_be_forgotten"]
        _rewrite(GOLD, doc)
        assert _verified() is False
    finally:
        GOLD.write_bytes(orig)
    assert _verified() is True


def test_gold_record_add_fails() -> None:
    orig = GOLD.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        extra = json.loads(json.dumps(doc["records"][0]))
        extra["process_id"] = "gdpr_8_fake"
        doc["records"].append(extra)
        _rewrite(GOLD, doc)
        assert _verified() is False
    finally:
        GOLD.write_bytes(orig)
    assert _verified() is True


def test_gold_process_record_tamper_fails() -> None:
    orig = GOLD.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        gpr = _g7(doc)["structure_annotation"]["gold_process_record"]
        for a in gpr["activities"]:
            if a["id"] == F1:
                a["type"] = "task"  # subProcess -> task tamper
        _rewrite(GOLD, doc)
        assert _verified() is False
    finally:
        GOLD.write_bytes(orig)
    assert _verified() is True


def test_gold_manifest_hash_tamper_fails() -> None:
    orig = GOLD_MANIFEST.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["artifacts"][
            "data/gold/stage1/process_records/stage1_process_gold_v1.json"][
            "sha256"] = "0" * 64
        _rewrite(GOLD_MANIFEST, doc)
        assert _verified() is False
    finally:
        GOLD_MANIFEST.write_bytes(orig)
    assert _verified() is True


def test_authorization_sentence_tamper_fails() -> None:
    orig = AUTH.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["authorization_sentence"] = doc["authorization_sentence"] \
            .replace("publish ONLY", "publish ALMOST ALL")
        _rewrite(AUTH, doc)
        assert _verified() is False
    finally:
        AUTH.write_bytes(orig)
    assert _verified() is True


def test_authorized_by_user_tamper_fails() -> None:
    orig = AUTH.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["authorized_by_user"] = False
        _rewrite(AUTH, doc)
        assert _verified() is False
    finally:
        AUTH.write_bytes(orig)
    assert _verified() is True


def test_gold_file_delete_fails() -> None:
    orig = GOLD.read_bytes()
    try:
        GOLD.unlink()
        assert _verified() is False
    finally:
        GOLD.write_bytes(orig)
    assert _verified() is True


def test_extra_gold_file_fails() -> None:
    """An unexpected file inside data/gold/stage1 must fail (only the
    published artifact + manifest are allowed)."""
    extra = ROOT / "data" / "gold" / "stage1" / "unexpected.json"
    try:
        extra.write_text("{}", encoding="utf-8")
        assert _verified() is False
    finally:
        extra.unlink(missing_ok=True)
    assert _verified() is True


def test_correction_tamper_fails_through_chain() -> None:
    """A tampered correction breaks the seven-batch chain; the gold verifier
    must fail (it re-runs the chain verifier)."""
    orig = CORRECTION.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        g7 = next(r for r in doc["records"]
                  if r["process_id"] == "gdpr_7_right_to_be_forgotten")
        next(la for la in g7["label_annotations"]
             if la["activity_id"] == F1)["actor"]["value"] = "TAMPERED"
        _rewrite(CORRECTION, doc)
        assert _verified() is False
    finally:
        CORRECTION.write_bytes(orig)
    assert _verified() is True

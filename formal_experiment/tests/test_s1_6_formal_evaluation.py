"""Focused tests for the S1.6 formal one-shot evaluation capsule.

Every tamper is applied to the real artifact, asserted to FAIL the capsule
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

VERIFIER_PATH = ROOT / "scripts" / "verify_stage1_formal_evaluation.py"
CAPSULE = ROOT / "outputs" / "development" / "stage1_formal_capsule_v1"
PREDICTIONS = (ROOT / "outputs" / "development" / "stage1_predictions"
               / "formal_predictions_v1.json")
GOLD = (ROOT / "data" / "gold" / "stage1" / "process_records"
        / "stage1_process_gold_v1.json")
P2_CONFIG = ROOT / "configs" / "stage1_label_p2_v1.json"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s1formal_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s1formal_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def test_capsule_verified_and_counts() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    evaluation = json.loads((CAPSULE / "evaluation.json").read_text(
        encoding="utf-8"))
    report = evaluation["report"]
    assert report["scope"] == "formal"
    assert set(report["methods"]) == {"P0", "P1", "P2"}
    assert sorted(report["membership"]) == [
        "gdpr_1_data_breach", "gdpr_2_consent_to_use_the_data",
        "gdpr_3_right_to_access", "gdpr_4_right_of_portability",
        "gdpr_5_right_to_withdraw", "gdpr_6_right_to_rectify",
        "gdpr_7_right_to_be_forgotten"]
    assert evaluation["one_shot"] is True
    assert evaluation["safety"]["p2_tuned_after_evaluation"] is False
    assert evaluation["safety"]["p2_unchanged_after_lock"] is True


def test_evaluation_value_tamper_fails() -> None:
    path = CAPSULE / "evaluation.json"
    orig = path.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["report"]["methods"]["P2"]["semantics"]["micro"]["f1"] = 1.0
        _rewrite(path, doc)
        assert _verified() is False
    finally:
        path.write_bytes(orig)
    assert _verified() is True


def test_predictions_copy_tamper_fails() -> None:
    path = CAPSULE / "predictions_copy.json"
    orig = path.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["attempts"][0]["label_record"]["activities"][0][
            "action_surface"] = "X"
        _rewrite(path, doc)
        assert _verified() is False
    finally:
        path.write_bytes(orig)
    assert _verified() is True


def test_manifest_hash_tamper_fails() -> None:
    path = CAPSULE / "manifest.json"
    orig = path.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["evaluation_sha256"] = "0" * 64
        _rewrite(path, doc)
        assert _verified() is False
    finally:
        path.write_bytes(orig)
    assert _verified() is True


def test_p2_config_change_detected_fails() -> None:
    """Changing the locked P2 config after the lock must fail the capsule
    verifier (P2 unchanged-after-lock invariant)."""
    orig = P2_CONFIG.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["runtime"]["model"] = "en_core_web_md"
        _rewrite(P2_CONFIG, doc)
        assert _verified() is False
    finally:
        P2_CONFIG.write_bytes(orig)
    assert _verified() is True


def test_limitations_removal_fails() -> None:
    path = CAPSULE / "evaluation.json"
    orig = path.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["limitations"] = [x for x in doc["limitations"]
                              if "Gold was formed" not in x]
        _rewrite(path, doc)
        assert _verified() is False
    finally:
        path.write_bytes(orig)
    assert _verified() is True


def test_gold_tamper_fails_through_rerun() -> None:
    """A tampered Gold changes the re-run report; the stored report then
    mismatches -> verifier fails."""
    orig = GOLD.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        g7 = next(r for r in doc["records"]
                  if r["process_id"] == "gdpr_7_right_to_be_forgotten")
        next(la for la in g7["label_annotations"]
             if la["activity_id"]
             == "sid-7E4D1233-F8F9-4883-9711-2B148DA4EF67")[
            "business_object"]["value"] = "the data subject"
        _rewrite(GOLD, doc)
        assert _verified() is False
    finally:
        GOLD.write_bytes(orig)
    assert _verified() is True

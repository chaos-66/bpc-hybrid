"""Focused tests for the S1.7 freeze-readiness dry-run packet.

Every tamper is applied to the real artifact, asserted to FAIL the dry-run
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

VERIFIER_PATH = ROOT / "scripts" / "verify_s1_7_freezer_dry_run.py"
PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v1.json"
P2_CONFIG = ROOT / "configs" / "stage1_label_p2_v1.json"


def _load_verifier() -> object:
    spec = importlib.util.spec_from_file_location(
        "s17_verifier", VERIFIER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s17_verifier"] = module
    spec.loader.exec_module(module)
    return module


def _verified() -> bool:
    return _load_verifier().verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


def test_s17_dry_run_verified() -> None:
    m = _load_verifier()
    r = m.verify()
    assert r["verified"] is True, [c for c in r["checks"] if not c["ok"]]
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    assert packet["status"] == "dry_run_not_applied"
    assert packet["target_status"] == "S1.7 ready_for_user_freeze_authorization"
    assert packet["pipeline_state"]["S1.3"].startswith("verified")
    assert packet["pipeline_state"]["S1.6"].startswith("verified")
    assert packet["pipeline_state"]["S1.7"].startswith(
        "ready_for_user_freeze_authorization")
    assert "NOT auto-authorized" in packet["pipeline_state"]["S3.7"]
    assert packet["consistency"]["zero_new_llm_api_calls"] == 0
    assert packet["consistency"]["p2_unchanged_after_lock"] is True
    assert packet["consistency"]["stage3_not_started"] is True


def test_packet_status_tamper_fails() -> None:
    orig = PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["status"] = "freeze_applied"
        _rewrite(PACKET, doc)
        assert _verified() is False
    finally:
        PACKET.write_bytes(orig)
    assert _verified() is True


def test_packet_hash_tamper_fails() -> None:
    orig = PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        key = next(iter(doc["hashes"]))
        doc["hashes"][key] = "0" * 64
        _rewrite(PACKET, doc)
        assert _verified() is False
    finally:
        PACKET.write_bytes(orig)
    assert _verified() is True


def test_authorization_sentence_tamper_fails() -> None:
    orig = PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["authorization_sentence"] = doc["authorization_sentence"].replace(
            "shall NOT modify P2", "may modify P2")
        _rewrite(PACKET, doc)
        assert _verified() is False
    finally:
        PACKET.write_bytes(orig)
    assert _verified() is True


def test_p2_config_change_fails_through_hash() -> None:
    """A P2 config change after the lock must be caught by the packet hash
    binding."""
    orig = P2_CONFIG.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["runtime"]["model"] = "en_core_web_md"
        _rewrite(P2_CONFIG, doc)
        assert _verified() is False
    finally:
        P2_CONFIG.write_bytes(orig)
    assert _verified() is True


def test_verifier_result_claim_tamper_fails() -> None:
    orig = PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        first = next(iter(doc["verifier_results"]))
        doc["verifier_results"][first]["verified"] = False
        doc["all_verifiers_verified"] = False
        _rewrite(PACKET, doc)
        assert _verified() is False
    finally:
        PACKET.write_bytes(orig)
    assert _verified() is True

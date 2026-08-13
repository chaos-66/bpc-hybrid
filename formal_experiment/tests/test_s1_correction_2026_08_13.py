"""Focused tamper tests for the 2026-08-13 correction assets.

Covers: overlap audit invariants (overlap count, 200/200, conclusions),
formal v2 asset invariants (claim, bindings, paths, numbers) and the S1.7
v2 packet. Every tamper is applied to the real artifact, asserted to FAIL
the corresponding verifier, then restored byte-exactly.
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

AUDIT = ROOT / "outputs" / "reports" / "s1_p2_target_overlap_audit_v1.json"
AUDIT_VERIFIER = ROOT / "scripts" / "verify_s1_p2_target_overlap_audit.py"
V2_REPORT = ROOT / "outputs" / "reports" / "stage1_formal_evaluation_v2.json"
V2_VERIFIER = ROOT / "scripts" / "verify_stage1_formal_evaluation_v2.py"
V2_PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v2.json"
V2_PACKET_VERIFIER = ROOT / "scripts" / "verify_s1_7_freezer_dry_run_v2.py"
V1_PACKET = ROOT / "outputs" / "reports" / "s1_7_freezer_readiness_dry_run_v1.json"
AUTH_PRED = (ROOT / "data" / "predictions" / "stage1_formal_v1"
             / "formal_predictions_v1.json")
AUTH_RESULTS = (ROOT / "data" / "results" / "stage1_formal_v1"
                / "stage1_formal_evaluation_v1.json")
SRC_PRED = (ROOT / "outputs" / "development" / "stage1_predictions"
            / "formal_predictions_v1.json")


def _load_verifier(path: Path, name: str) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _audit_verified() -> bool:
    return _load_verifier(AUDIT_VERIFIER, "corr_audit").verify()["verified"]


def _v2_verified() -> bool:
    return _load_verifier(V2_VERIFIER, "corr_v2").verify()["verified"]


def _v2p_verified() -> bool:
    return _load_verifier(V2_PACKET_VERIFIER, "corr_v2p").verify()["verified"]


def _rewrite(path: Path, doc) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2)
                      + "\n").encode("utf-8"))


# ---------------------------------------------------------------------------
# overlap audit invariants
# ---------------------------------------------------------------------------

def test_audit_overlap_count_zero_tamper_fails() -> None:
    orig = AUDIT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["overlap_historical"]["exact"]["count"] = 0
        doc["overlap_historical"]["exact"]["labels"] = []
        _rewrite(AUDIT, doc)
        assert _audit_verified() is False
    finally:
        AUDIT.write_bytes(orig)
    assert _audit_verified() is True


def test_audit_overlap_label_removal_fails() -> None:
    orig = AUDIT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["overlap_historical"]["exact"]["labels"] = [
            x for x in doc["overlap_historical"]["exact"]["labels"]
            if x != "Retrieve data"]
        doc["overlap_historical"]["exact"]["count"] = \
            len(doc["overlap_historical"]["exact"]["labels"])
        _rewrite(AUDIT, doc)
        assert _audit_verified() is False
    finally:
        AUDIT.write_bytes(orig)
    assert _audit_verified() is True


def test_audit_verb_199_tamper_fails() -> None:
    orig = AUDIT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["verb_list"]["total_entries"] = 199
        doc["verb_list"]["unique_entries"] = 199
        _rewrite(AUDIT, doc)
        assert _audit_verified() is False
    finally:
        AUDIT.write_bytes(orig)
    assert _audit_verified() is True


def test_audit_target_awareness_tamper_fails() -> None:
    orig = AUDIT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["conclusions"]["development_was_target_aware"] = False
        _rewrite(AUDIT, doc)
        assert _audit_verified() is False
    finally:
        AUDIT.write_bytes(orig)
    assert _audit_verified() is True
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["conclusions"]["strict_test_blind_supported"] = True
        _rewrite(AUDIT, doc)
        assert _audit_verified() is False
    finally:
        AUDIT.write_bytes(orig)
    assert _audit_verified() is True


# ---------------------------------------------------------------------------
# formal v2 invariants
# ---------------------------------------------------------------------------

def test_v2_claim_revert_to_test_blind_fails() -> None:
    orig = V2_REPORT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["claim"]["strict_test_blind"] = True
        doc["claim"]["held_out_generalization_claim_allowed"] = True
        _rewrite(V2_REPORT, doc)
        assert _v2_verified() is False
    finally:
        V2_REPORT.write_bytes(orig)
    assert _v2_verified() is True


def test_v2_number_tamper_fails() -> None:
    orig = V2_REPORT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["metrics"]["P2"]["semantic_micro"]["f1"] = 1.0
        _rewrite(V2_REPORT, doc)
        assert _v2_verified() is False
    finally:
        V2_REPORT.write_bytes(orig)
    assert _v2_verified() is True


def test_v2_predictions_tamper_fails() -> None:
    orig = AUTH_PRED.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["attempts"][0]["label_record"]["activities"][0][
            "action_surface"] = "X"
        _rewrite(AUTH_PRED, doc)
        assert _v2_verified() is False
    finally:
        AUTH_PRED.write_bytes(orig)
    assert _v2_verified() is True


def test_v2_audit_deletion_fails() -> None:
    orig = AUDIT.read_bytes()
    try:
        AUDIT.unlink()
        assert _v2_verified() is False
    finally:
        AUDIT.write_bytes(orig)
    assert _v2_verified() is True


def test_v2_development_path_reference_fails() -> None:
    """Pointing the authoritative predictions back to the development path
    must fail."""
    orig = V2_REPORT.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["bindings"]["predictions_authoritative"]["path"] = \
            "outputs/development/stage1_predictions/formal_predictions_v1.json"
        _rewrite(V2_REPORT, doc)
        assert _v2_verified() is False
    finally:
        V2_REPORT.write_bytes(orig)
    assert _v2_verified() is True


def test_v2_numeric_body_has_claim_metadata_fails() -> None:
    orig = AUTH_RESULTS.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["claim"] = {"strict_test_blind": False}
        _rewrite(AUTH_RESULTS, doc)
        assert _v2_verified() is False
    finally:
        AUTH_RESULTS.write_bytes(orig)
    assert _v2_verified() is True


# ---------------------------------------------------------------------------
# S1.7 v2 packet invariants
# ---------------------------------------------------------------------------

def test_v2p_status_freeze_applied_fails() -> None:
    orig = V2_PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["status"] = "freeze_applied"
        _rewrite(V2_PACKET, doc)
        assert _v2p_verified() is False
    finally:
        V2_PACKET.write_bytes(orig)
    assert _v2p_verified() is True


def test_v2p_authorization_sentence_tamper_fails() -> None:
    orig = V2_PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["authorization_sentence"] = doc["authorization_sentence"].replace(
            "NOT held-out generalization evidence",
            "is held-out generalization evidence")
        _rewrite(V2_PACKET, doc)
        assert _v2p_verified() is False
    finally:
        V2_PACKET.write_bytes(orig)
    assert _v2p_verified() is True


def test_v2p_p2_config_tamper_fails() -> None:
    p2_config = ROOT / "configs" / "stage1_label_p2_v1.json"
    orig = p2_config.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["runtime"]["model"] = "en_core_web_md"
        _rewrite(p2_config, doc)
        assert _v2p_verified() is False
    finally:
        p2_config.write_bytes(orig)
    assert _v2p_verified() is True


def test_v2p_sentence_acknowledgement_removed_fails() -> None:
    """Removing the target-awareness acknowledgement from the authorization
    sentence must fail (the v2 sentence must disclose the post-Gold
    development and the fixture overlap)."""
    orig = V2_PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc["authorization_sentence"] = doc["authorization_sentence"].replace(
            "I acknowledge that the P2 method was developed AFTER the Stage 1 "
            "Process Gold was formed and that at least three target activity "
            "labels ", "I authorize the freeze of ")
        _rewrite(V2_PACKET, doc)
        assert _v2p_verified() is False
    finally:
        V2_PACKET.write_bytes(orig)
    assert _v2p_verified() is True


def test_v1_superseded_marker_removed_fails() -> None:
    orig = V1_PACKET.read_bytes()
    doc = json.loads(orig.decode("utf-8"))
    try:
        doc.pop("superseded_by", None)
        _rewrite(V1_PACKET, doc)
        assert _v2p_verified() is False
    finally:
        V1_PACKET.write_bytes(orig)
    assert _v2p_verified() is True


def test_byte_locks_hold() -> None:
    """P2 config/impl, predictions, and the v2 report bindings are
    byte-locked (already covered by the verifiers; assert the reference
    hashes here too)."""
    import hashlib
    p2_config = ROOT / "configs" / "stage1_label_p2_v1.json"
    p2_impl = ROOT / "src" / "bpc_hybrid" / "stage1_label_semantics_p2.py"
    assert hashlib.sha256(p2_config.read_bytes()).hexdigest() == \
        "59ac4e8ec2b02632366cac229b5538c4f243910f6a371b5e14e1be65817cc49d"
    assert hashlib.sha256(p2_impl.read_bytes()).hexdigest() == \
        "c95910efe80992e0b49be7859e9c9a7b48493e9c794472ed86bcb129d2a5a3c2"
    assert hashlib.sha256(SRC_PRED.read_bytes()).hexdigest() == \
        "79a9b2c17185d63dc5ab5d9c47c8c592469b30f3cf7298740e593838166a94a8"

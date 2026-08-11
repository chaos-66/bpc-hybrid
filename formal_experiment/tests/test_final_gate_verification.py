"""Focused tests for the real fail-closed final-gate verification.

Covers (each tamper is applied to the real artifact, asserted, then
restored in a finally block):
- tampering ONE artifact of each of the three arms -> verify fails
- tampering one arm manifest (method_id) -> verify fails
- tampering the comparison capsule per-method hash -> verify fails
- tampering the G0.4 manifest semantic hash -> verify fails
- after any tamper: verify_all_static / verify_all_with_verifiers report
  not-verified (final_experiment_ready must NOT survive on config ready alone)
- the audit surfaces an explicit error when the tampered state is live
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.formal_arm_verification import (  # noqa: E402
    ARM_REGISTRY,
    COMPARISON_CAPSULE,
    G04_MANIFEST,
    verify_all_static,
    verify_all_with_verifiers,
    verify_arm_static,
)


def _arm_artifact_path(method: str, key: str) -> Path:
    manifest = json.loads((ROOT / ARM_REGISTRY[method]["manifest"])
                          .read_text(encoding="utf-8"))
    info = manifest["artifacts"][key]
    return ROOT / info["path"]


@pytest.mark.parametrize("method,key", [
    ("sun_rule_only", "predictions/predictions.json"),
    ("direct_llm", "results/evaluation_fine.json"),
    ("sun_llm_fallback", "results/modality_labels.json"),
])
def test_tamper_one_arm_artifact_fails(method: str, key: str) -> None:
    path = _arm_artifact_path(method, key)
    assert path.exists(), f"{method}/{key}"
    orig = path.read_bytes()
    try:
        path.write_bytes(orig + b" ")
        arm = verify_arm_static(method)
        assert arm["verified"] is False
        full = verify_all_static()
        assert full["verified"] is False
        assert not full["capsule_complete"]
    finally:
        path.write_bytes(orig)
    assert verify_all_static()["verified"] is True


def test_tamper_arm_manifest_method_id_fails() -> None:
    path = ROOT / ARM_REGISTRY["direct_llm"]["manifest"]
    doc = json.loads(path.read_text(encoding="utf-8"))
    orig = path.read_bytes()
    try:
        doc["method_id"] = "tampered_method"
        path.write_text(json.dumps(doc), encoding="utf-8")
        arm = verify_arm_static("direct_llm")
        assert arm["verified"] is False
        assert any("method_id exact" in c["name"] and not c["ok"]
                   for c in arm["checks"])
    finally:
        path.write_bytes(orig)
    assert verify_all_static()["verified"] is True


def test_tamper_comparison_capsule_hash_fails() -> None:
    doc = json.loads(COMPARISON_CAPSULE.read_text(encoding="utf-8"))
    orig = COMPARISON_CAPSULE.read_bytes()
    try:
        doc["formal_arm_capsules"]["per_method"]["sun_rule_only"][
            "manifest_sha256"] = "0" * 64
        COMPARISON_CAPSULE.write_text(json.dumps(doc), encoding="utf-8")
        full = verify_all_static()
        assert full["verified"] is False
        assert not full["comparison_consistent"]
    finally:
        COMPARISON_CAPSULE.write_bytes(orig)
    assert verify_all_static()["verified"] is True


def test_tamper_g04_manifest_hash_fails() -> None:
    doc = json.loads(G04_MANIFEST.read_text(encoding="utf-8"))
    orig = G04_MANIFEST.read_bytes()
    try:
        doc["derived_view"]["semantic_sha256"] = "0" * 64
        G04_MANIFEST.write_text(json.dumps(doc), encoding="utf-8")
        full = verify_all_static()
        assert full["verified"] is False
        assert not full["comparison_consistent"]
    finally:
        G04_MANIFEST.write_bytes(orig)
    assert verify_all_static()["verified"] is True


def test_tamper_surfaces_audit_error_and_keeps_final_gate_closed() -> None:
    """With a tampered artifact live, collect_project_audit must surface an
    explicit error (methods_unexpectedly_ready) and final_experiment_ready
    must be False -- config 'ready' alone must not keep the gate open."""
    from formal_experiment.audit import collect_project_audit
    path = _arm_artifact_path("sun_rule_only", "predictions/predictions.json")
    orig = path.read_bytes()
    try:
        path.write_bytes(orig + b" ")
        audit = collect_project_audit()
        errors = {item["code"] for item in audit["findings"]["errors"]}
        assert "methods_unexpectedly_ready" in errors
        assert audit["final_experiment_ready"] is False
        assert "final_gate_conditions_met" not in {
            item["code"] for item in audit["findings"]["passes"]}
    finally:
        path.write_bytes(orig)
    audit = collect_project_audit()
    assert audit["final_experiment_ready"] is True


def test_verifiers_executed_and_verified() -> None:
    result = verify_all_with_verifiers()
    assert result["verified"] is True
    assert result["verifiers_executed_and_verified"] is True
    for method in ARM_REGISTRY:
        v = result["verifiers"][method]
        assert v["executed"] is True
        assert v["verified"] is True


def test_all_three_published_is_derived_not_trusted() -> None:
    """The comparison capsule's all_three_published_and_verified flag is
    recomputed; a corrupted self-report must not matter."""
    doc = json.loads(COMPARISON_CAPSULE.read_text(encoding="utf-8"))
    orig = COMPARISON_CAPSULE.read_bytes()
    try:
        doc["formal_arm_capsules"]["all_three_published_and_verified"] = True
        # force a real inconsistency elsewhere: corrupt one recorded hash
        doc["formal_arm_capsules"]["per_method"]["sun_llm_fallback"][
            "manifest_sha256"] = "f" * 64
        COMPARISON_CAPSULE.write_text(json.dumps(doc), encoding="utf-8")
        result = verify_all_static()
        assert result["verified"] is False
        assert any("manifest hash == comparison record" in c["name"]
                   and not c["ok"] for c in result["comparison"]["checks"])
    finally:
        COMPARISON_CAPSULE.write_bytes(orig)
    assert verify_all_static()["verified"] is True

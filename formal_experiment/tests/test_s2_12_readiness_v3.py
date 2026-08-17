"""Focused tests for S2.12 execution readiness v3 (Checkpoint G; zero
API).

Covers:
  * parity RE-RUN (evaluator v2 unchanged) passes and matches the
    committed readiness v3 claim
  * readiness v3 re-binds proposal v3 / importer v3 (blocked=0/
    unresolved=0/adjudicable=36) and the user confirmation event;
    S2.11 freeze is 36/36 (user-confirmed, Checkpoint G); the real run
    stays refused ONLY on the API budget authorization (input token cap,
    cost cap; NO final authorization sentence)
  * independent verifier passes on the committed assets and fails closed
    on a tampered proposal binding
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

import s2_12_build_readiness_v3 as builder
import verify_s2_12_readiness_v3 as verifier

ROOT = Path(__file__).resolve().parents[1]

PROPOSAL_REPORT_V3_REL = "outputs/reports/s2_11_proposal_report_v3.json"
IMPORTER_DRY_RUN_V3_REL = "outputs/reports/s2_11_batch_import_dry_run_v3.json"
READINESS_V3_REL = "outputs/reports/s2_12_execution_readiness_v3.json"
API_READINESS_V2_REL = "outputs/reports/s2_12_api_readiness_v2.json"
CONFIRMATION_EVENT_REL = \
    "configs/s2_11_batch_import_confirmation_event_v3.json"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_readiness_v3_parity_rerun_and_bindings() -> None:
    readiness = _load(READINESS_V3_REL)
    parity = readiness["ready_claims"]["evaluator_ready"]["parity_rerun"]
    assert parity["passed"] is True
    assert parity["span_metrics_equal"] is True
    assert parity["modality_metrics_equal"] is True
    # re-run in-process and compare
    rerun = builder._parity_rerun()
    assert rerun == parity
    proposal = _load(PROPOSAL_REPORT_V3_REL)
    assert readiness["proposal_v3"]["proposal_file_sha256"] == \
        proposal["proposal_file_sha256"]
    assert readiness["proposal_v3"]["supersedes_v2_status"] == \
        "superseded_pending_targeted_correction_do_not_approve"
    assert readiness["proposal_v3"]["human_approved"] is True
    assert readiness["proposal_v3"]["confirmation_event"] == \
        CONFIRMATION_EVENT_REL
    assert readiness["ready_claims"]["importer_ready"] == {
        "samples": 36, "blocked_fields": 0, "blocked_samples": 0,
        "unresolved_fields": 0, "adjudicable": 36}
    assert readiness["runner"]["real_run_refused"] is True
    assert readiness["ready_claims"]["gold_or_formal_evaluation_complete"] \
        is False
    assert readiness["gates"]["s2_11_freeze"]["adjudicated"] == 36
    assert readiness["gates"]["s2_11_freeze"]["ready"] is True
    assert readiness["gates"]["s2_11_freeze"]["confirmation_event"] == \
        CONFIRMATION_EVENT_REL
    assert (ROOT / CONFIRMATION_EVENT_REL).is_file()
    assert readiness["api_readiness"]["calls_made"] == 0
    assert readiness["api_readiness"]["final_copyable_authorization_"
                                      "sentence"] is None
    missing = " ".join(readiness["gates"]["api_budget_authorization"]
                       ["missing_items"])
    assert "input_token_cap" in missing and "cost_cap" in missing


def test_readiness_v3_builder_deterministic() -> None:
    first = json.dumps(builder.build(), sort_keys=True, ensure_ascii=False)
    second = json.dumps(builder.build(), sort_keys=True, ensure_ascii=False)
    assert first == second


def test_readiness_v3_verifier_passes() -> None:
    result = verifier.verify()
    assert result["verified"] is True, \
        "; ".join(c["name"] for c in result["checks"] if not c["ok"])


VERIFIER_INPUTS = [
    "outputs/reports/s2_11_corpus_membership_v1.json",
    "data/development/human_review/s2_11_review_decisions_v2.json",
    PROPOSAL_REPORT_V3_REL,
    IMPORTER_DRY_RUN_V3_REL,
    CONFIRMATION_EVENT_REL,
    "configs/s2_12_execution_plan_v2.json",
    "outputs/reports/s2_12_execution_plan_v2.json",
    "outputs/reports/s2_12_execution_readiness_v2.json",
    API_READINESS_V2_REL,
    "src/bpc_hybrid/s2_12_stratified_evaluator_v2.py",
    "src/bpc_hybrid/s2_12_method_adapter.py",
    "configs/stage2_evaluator_s210_v3.json",
    "scripts/s2_12_build_execution_ready_v2.py",
    READINESS_V3_REL,
]


@pytest.fixture()
def verifier_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "formal_experiment"
    for rel in VERIFIER_INPUTS:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    monkeypatch.setattr(verifier, "ROOT", root)
    yield root


def test_readiness_v3_verifier_fails_on_forged_proposal_binding(
        verifier_tmp: Path) -> None:
    p = verifier_tmp / PROPOSAL_REPORT_V3_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["supersedes_v2"]["status"] = "approved"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False


def test_readiness_v3_verifier_fails_on_forged_sentence(
        verifier_tmp: Path) -> None:
    p = verifier_tmp / READINESS_V3_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["api_readiness"]["final_copyable_authorization_sentence"] = \
        "I authorize the run"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False

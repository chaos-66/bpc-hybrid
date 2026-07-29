from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from formal_experiment.audit import collect_project_audit
from formal_experiment.s2_4_license_gate import (
    CONTRACT_REL,
    EVIDENCE_REL,
    HUMAN_RECORD_REL,
    LOCAL_USE_REL,
    RUN_MANIFEST_REL,
    SOURCE_MANIFEST_REL,
    TRAINING_CONFIG_REL,
    verify_s2_4_license_gate,
)
from formal_experiment.status import collect_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_gate_inputs(tmp_path: Path) -> Path:
    for rel in (
        EVIDENCE_REL,
        LOCAL_USE_REL,
        TRAINING_CONFIG_REL,
        RUN_MANIFEST_REL,
        CONTRACT_REL,
        SOURCE_MANIFEST_REL,
        HUMAN_RECORD_REL,
    ):
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_ROOT / rel, target)
    return tmp_path


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _relock_evidence_hash(root: Path) -> None:
    contract_path = root / CONTRACT_REL
    contract = _load(contract_path)
    contract["sun_stage2_method"]["statement_classifier_gate"]["license_evidence"][
        "sha256"
    ] = _sha256(root / EVIDENCE_REL)
    _write(contract_path, contract)


def _relock_local_use_hash(root: Path) -> None:
    contract_path = root / CONTRACT_REL
    contract = _load(contract_path)
    contract["sun_stage2_method"]["statement_classifier_gate"][
        "local_research_use_decision"
    ]["sha256"] = _sha256(root / LOCAL_USE_REL)
    _write(contract_path, contract)


def _relock_training_config_hash(root: Path) -> None:
    contract_path = root / CONTRACT_REL
    contract = _load(contract_path)
    contract["sun_stage2_method"]["statement_classifier_gate"]["training_config"][
        "sha256"
    ] = _sha256(root / TRAINING_CONFIG_REL)
    _write(contract_path, contract)


def test_exact_s2_4_evidence_and_local_use_decision_are_ready() -> None:
    gate = verify_s2_4_license_gate(PROJECT_ROOT)
    assert gate["evidence_verified"] is True
    assert gate["ready"] is True
    assert gate["rights_status"] == "unknown_pending_confirmation"
    assert gate["training_authorized"] is True
    assert gate["evaluation_authorized"] is True
    assert gate["redistribution_allowed"] is False
    assert gate["training_completed"] is True
    assert gate["test_evaluation_count"] == 1
    assert gate["authorization_basis"] == (
        "project_owner_research_use_decision_not_rightsholder_license"
    )
    assert gate["errors"] == []
    assert gate["blockers"] == []


def test_evidence_byte_change_fails_exact_hash(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    evidence_path = root / EVIDENCE_REL
    evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "license_evidence_hash_mismatch" in gate["errors"]


def test_null_archive_license_fields_cannot_be_invented(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    evidence_path = root / EVIDENCE_REL
    evidence = _load(evidence_path)
    evidence["sources"]["archive_org_metadata"]["licenseurl"] = (
        "https://example.invalid/invented-license"
    )
    _write(evidence_path, evidence)
    _relock_evidence_hash(root)
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "archive_licenseurl_not_null" in gate["errors"]


def test_training_cannot_be_enabled_by_editing_evidence(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    evidence_path = root / EVIDENCE_REL
    evidence = _load(evidence_path)
    evidence["decision"]["training_authorized"] = True
    _write(evidence_path, evidence)
    _relock_evidence_hash(root)
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "license_decision_boundary_relaxed" in gate["errors"]
    assert gate["ready"] is False


def test_local_use_decision_is_hash_locked(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    decision_path = root / LOCAL_USE_REL
    decision_path.write_text(
        decision_path.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "local_research_use_decision_hash_mismatch" in gate["errors"]


def test_local_use_decision_cannot_enable_redistribution(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    decision_path = root / LOCAL_USE_REL
    decision = _load(decision_path)
    decision["boundaries"]["redistribute_row_level_derived_data"] = True
    _write(decision_path, decision)
    _relock_local_use_hash(root)
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "local_research_use_boundary_relaxed" in gate["errors"]
    assert gate["ready"] is False


def test_training_config_is_hash_locked(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    config_path = root / TRAINING_CONFIG_REL
    config = _load(config_path)
    config["optimization"]["hyperparameter_search"] = True
    _write(config_path, config)
    _relock_training_config_hash(root)
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "s2_4_training_config_boundary_invalid" in gate["errors"]
    assert gate["ready"] is False


def test_human_license_record_is_hash_locked(tmp_path: Path) -> None:
    root = _copy_gate_inputs(tmp_path)
    record_path = root / HUMAN_RECORD_REL
    record_path.write_text(
        record_path.read_text(encoding="utf-8") + "\nchanged",
        encoding="utf-8",
    )
    gate = verify_s2_4_license_gate(root)
    assert gate["evidence_verified"] is False
    assert "human_license_record_hash_mismatch" in gate["errors"]


def test_status_and_audit_separate_unknown_license_from_ready_local_use() -> None:
    status = collect_status()
    assert status["s2_4_license_evidence_verified"] is True
    assert status["s2_4_ready"] is True
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert "s2_4_license_evidence_verified" in pass_codes
    assert "s2_4_local_research_use_ready" in pass_codes
    assert audit["integrity_pass"] is True

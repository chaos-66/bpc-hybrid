"""Fail-closed S2.4 evidence and local-research-use gate.

This module verifies the exact offline evidence snapshot produced by the
read-only S2.4-L review and the separate project-owner research-use decision.
It deliberately does not fetch the network, interpret copyright law, train a
model, or evaluate predictions.  The two records stay separate so an unknown
rightsholder license cannot be rewritten as an explicit license while the local,
noncommercial thesis workflow can proceed under the project decision.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from formal_experiment.paths import REPO_ROOT


EVIDENCE_REL = Path("configs/datasets/sun_modality_license_evidence.json")
LOCAL_USE_REL = Path("configs/datasets/sun_modality_local_research_use.json")
TRAINING_CONFIG_REL = Path("configs/models/sun_bert_textcnn_s24.json")
RUN_MANIFEST_REL = Path(
    "outputs/reports/s24_legal_bert_textcnn_seed20260717_v1.manifest.json"
)
CONTRACT_REL = Path("configs/experiment_contract.json")
SOURCE_MANIFEST_REL = Path("data/development/sun_modality/source_manifest.json")
HUMAN_RECORD_REL = Path("docs/research/SUN_OFFICIAL_LICENSE_RECORD.md")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _nested(value: Mapping[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def verify_s2_4_license_gate(project_root: Path = REPO_ROOT) -> dict[str, Any]:
    """Verify the locked S2.4-L evidence and return a fail-closed summary."""

    evidence_path = project_root / EVIDENCE_REL
    local_use_path = project_root / LOCAL_USE_REL
    training_config_path = project_root / TRAINING_CONFIG_REL
    run_manifest_path = project_root / RUN_MANIFEST_REL
    contract_path = project_root / CONTRACT_REL
    source_manifest_path = project_root / SOURCE_MANIFEST_REL
    human_record_path = project_root / HUMAN_RECORD_REL
    evidence = _load_json(evidence_path)
    local_use = _load_json(local_use_path)
    training_config = _load_json(training_config_path)
    run_manifest = _load_json(run_manifest_path)
    contract = _load_json(contract_path)
    source_manifest = _load_json(source_manifest_path)
    errors: list[str] = []

    def require(condition: bool, code: str) -> None:
        if not condition:
            errors.append(code)

    classifier_gate = _nested(
        contract, "sun_stage2_method", "statement_classifier_gate"
    )
    if not isinstance(classifier_gate, Mapping):
        classifier_gate = {}
    pointer = classifier_gate.get("license_evidence", {})
    if not isinstance(pointer, Mapping):
        pointer = {}
    local_use_pointer = classifier_gate.get("local_research_use_decision", {})
    if not isinstance(local_use_pointer, Mapping):
        local_use_pointer = {}
    training_pointer = classifier_gate.get("training_config", {})
    if not isinstance(training_pointer, Mapping):
        training_pointer = {}

    evidence_sha256 = _sha256(evidence_path)
    local_use_sha256 = _sha256(local_use_path)
    training_config_sha256 = _sha256(training_config_path)
    run_manifest_sha256 = _sha256(run_manifest_path)
    human_record_sha256 = _sha256(human_record_path)
    source_manifest_sha256 = _sha256(source_manifest_path)

    require(evidence_path.is_file(), "license_evidence_missing")
    require(local_use_path.is_file(), "local_research_use_decision_missing")
    require(training_config_path.is_file(), "s2_4_training_config_missing")
    require(run_manifest_path.is_file(), "s2_4_run_manifest_missing")
    require(contract_path.is_file(), "experiment_contract_missing")
    require(source_manifest_path.is_file(), "source_manifest_missing")
    require(human_record_path.is_file(), "human_license_record_missing")
    require(
        pointer.get("path") == EVIDENCE_REL.as_posix(),
        "license_evidence_path_mismatch",
    )
    require(
        pointer.get("sha256") == evidence_sha256 and bool(evidence_sha256),
        "license_evidence_hash_mismatch",
    )
    require(
        pointer.get("human_record_path") == HUMAN_RECORD_REL.as_posix(),
        "human_license_record_path_mismatch",
    )
    require(
        pointer.get("human_record_sha256") == human_record_sha256
        and bool(human_record_sha256),
        "human_license_record_hash_mismatch",
    )
    require(
        local_use_pointer.get("path") == LOCAL_USE_REL.as_posix(),
        "local_research_use_decision_path_mismatch",
    )
    require(
        local_use_pointer.get("sha256") == local_use_sha256
        and bool(local_use_sha256),
        "local_research_use_decision_hash_mismatch",
    )
    require(
        training_pointer.get("path") == TRAINING_CONFIG_REL.as_posix(),
        "s2_4_training_config_path_mismatch",
    )
    require(
        training_pointer.get("sha256") == training_config_sha256
        and bool(training_config_sha256),
        "s2_4_training_config_hash_mismatch",
    )
    run_pointer = training_pointer.get("run_manifest", {})
    if not isinstance(run_pointer, Mapping):
        run_pointer = {}
    require(
        run_pointer.get("path") == RUN_MANIFEST_REL.as_posix(),
        "s2_4_run_manifest_path_mismatch",
    )
    require(
        run_pointer.get("sha256") == run_manifest_sha256
        and bool(run_manifest_sha256),
        "s2_4_run_manifest_hash_mismatch",
    )
    require(
        _nested(
            contract,
            "stage2_dataset",
            "modality_dataset",
            "source_manifest",
            "sha256",
        )
        == source_manifest_sha256
        and bool(source_manifest_sha256),
        "source_manifest_hash_mismatch",
    )

    archive = _nested(evidence, "sources", "archive_org_metadata")
    springer = _nested(evidence, "sources", "springer_article")
    local_archive = _nested(evidence, "sources", "local_archive")
    decision = evidence.get("decision", {})
    boundaries = evidence.get("boundaries", {})
    local_scope = local_use.get("scope", {})
    local_boundaries = local_use.get("boundaries", {})
    for name, value in (
        ("archive", archive),
        ("springer", springer),
        ("local_archive", local_archive),
        ("decision", decision),
        ("boundaries", boundaries),
    ):
        require(isinstance(value, Mapping), f"{name}_section_invalid")
    archive = archive if isinstance(archive, Mapping) else {}
    springer = springer if isinstance(springer, Mapping) else {}
    local_archive = local_archive if isinstance(local_archive, Mapping) else {}
    decision = decision if isinstance(decision, Mapping) else {}
    boundaries = boundaries if isinstance(boundaries, Mapping) else {}
    require(isinstance(local_scope, Mapping), "local_use_scope_invalid")
    require(isinstance(local_boundaries, Mapping), "local_use_boundaries_invalid")
    local_scope = local_scope if isinstance(local_scope, Mapping) else {}
    local_boundaries = (
        local_boundaries if isinstance(local_boundaries, Mapping) else {}
    )

    require(
        evidence.get("schema_version") == "sun_modality_license_evidence@1.0.0",
        "license_evidence_schema_mismatch",
    )
    require(evidence.get("task_id") == "S2.4-L", "license_task_id_mismatch")
    require(
        evidence.get("status")
        == "verified_no_explicit_license_training_evaluation_not_authorized",
        "license_evidence_status_mismatch",
    )
    require(
        archive.get("url") == "https://archive.org/metadata/input-2",
        "archive_metadata_url_mismatch",
    )
    require(archive.get("identifier") == "input-2", "archive_identifier_mismatch")
    require(archive.get("licenseurl") is None, "archive_licenseurl_not_null")
    require(archive.get("rights") is None, "archive_rights_not_null")
    require(
        _nested(archive, "asset", "name") == "Decision_Logic_data.zip"
        and _nested(archive, "asset", "size_bytes") == 191_874_718
        and _nested(archive, "asset", "sha1")
        == "0346f84a246b7049d5aef58bcb33471435bee106",
        "archive_asset_identity_mismatch",
    )
    require(
        springer.get("doi") == "10.1007/s11227-023-05626-0",
        "springer_doi_mismatch",
    )
    require(
        springer.get("explicit_dataset_license_observed") is False
        and springer.get("explicit_training_permission_observed") is False
        and springer.get("explicit_evaluation_permission_observed") is False
        and springer.get("explicit_redistribution_permission_observed") is False,
        "springer_permission_boundary_relaxed",
    )
    require(
        local_archive.get("path")
        == "data/development/sun_modality/raw/Decision_Logic_data.zip"
        and local_archive.get("sha256")
        == "ada231f092927813ba9f1cd32a44a3d30d96b57fc463d042dfd76c652b6d58f2",
        "local_archive_identity_mismatch",
    )
    require(
        local_archive.get("member_names")
        == ["EStG_sent_vec.csv", "EStG_raw.txt", "estg.html"]
        and local_archive.get("license_member_present") is False,
        "local_archive_license_member_claim_invalid",
    )
    require(
        decision.get("rights_status") == "unknown_pending_confirmation"
        and decision.get("evidence_review_complete") is True,
        "license_decision_status_invalid",
    )
    require(
        decision.get("training_authorized") is False
        and decision.get("evaluation_authorized") is False
        and decision.get("formal_use_allowed") is False
        and decision.get("publication_allowed") is False
        and decision.get("redistribution_allowed") is False,
        "license_decision_boundary_relaxed",
    )
    require(
        boundaries.get("training_run") is False
        and boundaries.get("evaluation_run") is False
        and boundaries.get("gold_modified") is False
        and boundaries.get("formal_artifact_written") is False
        and boundaries.get("llm_api_called") is False
        and boundaries.get("s2_4_ready") is False
        and boundaries.get("s2_6_entered") is False,
        "license_run_boundary_relaxed",
    )
    require(
        local_use.get("schema_version")
        == "sun_modality_local_research_use_decision@1.0.0"
        and local_use.get("task_id") == "S2.4-U"
        and local_use.get("decided_at") == "2026-07-17"
        and local_use.get("decision_source")
        == "explicit_user_instruction_in_current_project_session"
        and local_use.get("rights_evidence_status")
        == "unknown_pending_confirmation"
        and local_use.get("authorization_basis")
        == "project_owner_research_use_decision_not_rightsholder_license",
        "local_research_use_decision_identity_invalid",
    )
    require(
        local_scope.get("local_noncommercial_research") is True
        and local_scope.get("training") is True
        and local_scope.get("development_selection") is True
        and local_scope.get("evaluation") is True
        and local_scope.get("paper_aggregate_metrics") is True
        and local_scope.get("paper_methods_and_configs") is True
        and local_scope.get("commercial_use") is False,
        "local_research_use_scope_invalid",
    )
    require(
        local_boundaries.get("claim_explicit_license") is False
        and local_boundaries.get("redistribute_original_archive") is False
        and local_boundaries.get("redistribute_raw_or_extracted_text") is False
        and local_boundaries.get("redistribute_row_level_derived_data") is False
        and local_boundaries.get("upload_data_to_external_service") is False
        and local_boundaries.get("commit_data_to_git") is False
        and local_boundaries.get("modify_gold") is False
        and local_boundaries.get("authorize_llm_api_calls") is False,
        "local_research_use_boundary_relaxed",
    )
    require(
        training_config.get("schema_version") == "sun_bert_textcnn_s24@1.0.0"
        and training_config.get("task_id") == "S2.4"
        and training_config.get("status")
        == "preregistered_implementation_ready_not_run"
        and _nested(training_config, "optimization", "hyperparameter_search")
        is False
        and _nested(training_config, "evaluation", "test_policy")
        == "single_evaluation_after_best_dev_checkpoint"
        and _nested(training_config, "evaluation", "persist_row_level_predictions")
        is False,
        "s2_4_training_config_boundary_invalid",
    )
    require(
        run_manifest.get("schema_version")
        == "sun_bert_textcnn_run_manifest@1.0.0"
        and run_manifest.get("task_id") == "S2.4"
        and run_manifest.get("run_id")
        == "s24_legal_bert_textcnn_seed20260717_v1"
        and run_manifest.get("status") == "succeeded"
        and _nested(run_manifest, "config", "sha256") == training_config_sha256
        and _nested(run_manifest, "selection", "split") == "dev"
        and _nested(run_manifest, "selection", "metric") == "macro_f1"
        and _nested(run_manifest, "selection", "best_epoch") == 5
        and _nested(run_manifest, "selection", "epochs_completed") == 7
        and _nested(run_manifest, "test", "policy")
        == "single_evaluation_after_best_dev_checkpoint"
        and _nested(run_manifest, "test", "evaluation_count") == 1
        and _nested(run_manifest, "artifacts", "row_level_predictions_persisted")
        is False,
        "s2_4_run_manifest_identity_invalid",
    )
    require(
        _nested(run_manifest, "safety", "gold_read_or_modified") is False
        and _nested(run_manifest, "safety", "llm_api_called") is False
        and _nested(run_manifest, "safety", "network_called") is False
        and _nested(run_manifest, "safety", "redistribution_allowed") is False
        and _nested(run_manifest, "safety", "test_evaluation_count") == 1,
        "s2_4_run_manifest_safety_invalid",
    )
    require(
        classifier_gate.get("status")
        == "verified_training_dev_selection_single_test_evaluation"
        and classifier_gate.get("ready") is True
        and classifier_gate.get("training_authorized") is True
        and classifier_gate.get("evaluation_authorized") is True
        and classifier_gate.get("license_evidence_review_complete") is True
        and classifier_gate.get("redistribution_allowed") is False
        and classifier_gate.get("commercial_use_allowed") is False
        and classifier_gate.get("separate_license_closure_required") is False
        and classifier_gate.get("permission_confirmation_required_to_unlock") is False
        and local_use_pointer.get("authorization_basis")
        == "project_owner_research_use_decision_not_rightsholder_license",
        "statement_classifier_license_contract_inconsistent",
    )
    require(
        training_pointer.get("status")
        == "verified_training_dev_selection_single_test_evaluation"
        and training_pointer.get("hyperparameter_search") is False
        and training_pointer.get("test_evaluation_count") == 1
        and run_pointer.get("run_id")
        == "s24_legal_bert_textcnn_seed20260717_v1"
        and _nested(training_pointer, "checkpoint", "sha256")
        == _nested(run_manifest, "checkpoint", "sha256")
        and _nested(training_pointer, "checkpoint", "versioned") is False,
        "statement_classifier_training_contract_inconsistent",
    )
    require(
        _nested(source_manifest, "s2_4_license_closure_2026_07_16", "evidence_review_complete")
        is True
        and _nested(source_manifest, "s2_4_license_closure_2026_07_16", "rights_status")
        == "unknown_pending_confirmation"
        and _nested(source_manifest, "s2_4_license_closure_2026_07_16", "s2_4_ready")
        is False,
        "source_manifest_license_closure_inconsistent",
    )

    evidence_verified = not errors
    ready = bool(
        evidence_verified
        and local_scope.get("training") is True
        and local_scope.get("evaluation") is True
        and classifier_gate.get("ready") is True
        and run_manifest.get("status") == "succeeded"
    )
    blockers = [] if ready or not evidence_verified else ["local_use_not_authorized"]
    return {
        "task_id": "S2.4-L",
        "status": evidence.get("status", "invalid"),
        "evidence_verified": evidence_verified,
        "ready": ready,
        "rights_status": decision.get("rights_status", "unknown"),
        "training_authorized": local_scope.get("training") is True,
        "evaluation_authorized": local_scope.get("evaluation") is True,
        "authorization_basis": local_use.get("authorization_basis", "unknown"),
        "redistribution_allowed": False,
        "evidence_sha256": evidence_sha256,
        "local_use_sha256": local_use_sha256,
        "training_config_sha256": training_config_sha256,
        "run_manifest_sha256": run_manifest_sha256,
        "training_completed": run_manifest.get("status") == "succeeded",
        "test_evaluation_count": _nested(run_manifest, "test", "evaluation_count"),
        "human_record_sha256": human_record_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "errors": errors,
        "blockers": blockers,
    }


@lru_cache(maxsize=1)
def get_cached_s2_4_license_gate() -> dict[str, Any]:
    """Return the current-project S2.4 license gate once per process."""

    return verify_s2_4_license_gate(REPO_ROOT)

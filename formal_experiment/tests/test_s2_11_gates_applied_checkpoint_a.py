"""Focused tests for the S2.11 / G0.5 CHECKPOINT A applied-gates assets
(user-authorized non-API application round, 2026-08-17).

Covers:
  * user authorization event: exact forwarded instruction + exact UTF-8
    SHA-256 + normalized scope + containment policy + append-only
  * G1: containment (license NOT verified, 91 files inventoried, no
    license-named artifact files, redistribution/publication forbidden)
  * G2: applied_local_read_only with the exact scope and membership
    read-discipline
  * G3: M1 modality identity mapping applied (candidate-only)
  * G6: S0_no_automatic_structural_mapping (field_mapping={})
  * G4: the sealed v6 chain validates the REAL frozen application from
    disk; classify_frozen works with the REAL frozen config; prior
    results scan empty; no candidates exist before the freeze
  * G0.5: frozen_for_future_external_complex_corpora; draft config stays
    byte-unchanged (61938c99…); preregistration claims stay forbidden
  * G5: NOT applied until Checkpoint B
  * the applied-gates report/manifest bindings match disk
  * S2.13 / S3.7 are NOT advanced
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.g05_complexity_candidate import (
    G05ClassificationError,
    classify_frozen,
    derive_promotion_readiness,
    derive_prior_results,
    validate_frozen_application,
)

ROOT = Path(__file__).resolve().parents[1]

USER_INSTRUCTION = "除了用apikey的时候要授权，其他直接正常进行即可。"
USER_INSTRUCTION_SHA256 = \
    "a8a1dec4c826b1303fde64f2ac111ea2886ad0b08fd8a20af68b5a67130bfc64"
DRAFT_RAW_SHA = \
    "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"
AUTHORIZATION_SCOPE = "local_read_only_nonredistributive_s2_11"
FROZEN_STATUS = "frozen_for_future_external_complex_corpora"

USER_AUTH_REL = "configs/s2_11_user_authorization_event_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
EVENT_REL = "configs/g05_authorization_event_v1.json"
MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
POLICY_REL = "configs/s2_11_mapping_policy_m1_v1.json"
G1_REL = "outputs/reports/s2_11_g1_license_containment_v1.json"
G2_REL = "outputs/reports/s2_11_g2_activation_v1.json"
GATES_REL = "outputs/reports/s2_11_gates_applied_checkpoint_a_v1.json"
GATES_MANIFEST_REL = \
    "outputs/reports/s2_11_gates_applied_checkpoint_a_v1.manifest.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"

LOCAL_WORKING_DIR = ROOT / "outputs" / "development" / "s2_11_local_working"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha_file(rel: str) -> str:
    return _sha((ROOT / rel).read_bytes())


# ---------------------------------------------------------------------------
# User authorization event
# ---------------------------------------------------------------------------
def test_user_authorization_event_exact_instruction_and_hash() -> None:
    doc = _load(USER_AUTH_REL)
    assert doc["kind"] == "user_authorization"
    assert doc["user_instruction_utf8"] == USER_INSTRUCTION
    assert doc["user_instruction_utf8_sha256"] == USER_INSTRUCTION_SHA256
    assert _sha(USER_INSTRUCTION.encode("utf-8")) == USER_INSTRUCTION_SHA256
    assert doc["source"] == "user_instruction_forwarded_in_current_task"
    assert doc["authorization_scope"] == AUTHORIZATION_SCOPE
    assert doc["append_only"] is True
    assert {"G1", "G2", "G3", "G4", "G5", "G6"} == set(
        doc["gates_covered"])


def test_user_authorization_does_not_grant_ip_or_gold() -> None:
    doc = _load(USER_AUTH_REL)
    joined = "\n".join(doc["normalized_scope"]).lower()
    assert "real llm/api calls are not authorized" in joined
    assert "no third-party intellectual property grant" in joined
    assert "must not fabricate human gold" in joined
    assert "local read-only research use" in joined


def test_containment_policy_exact_values() -> None:
    cp = _load(USER_AUTH_REL)["containment_policy"]
    assert cp["artifact_license_verified"] is False
    assert cp["artifact_license_status"] == "unknown_pending_confirmation"
    assert cp["local_read_only_research_use_authorized_by_user"] is True
    assert cp["raw_redistribution_allowed"] is False
    assert cp["raw_publication_allowed"] is False
    assert cp["references_mutation_allowed"] is False
    assert cp["formal_export_may_include_only_hashes_ids_aggregates_and_user_created_decisions"] is True


# ---------------------------------------------------------------------------
# G1 / G2 / G3 / G6
# ---------------------------------------------------------------------------
def test_g1_containment_report() -> None:
    g1 = _load(G1_REL)
    assert g1["status"] == "resolved_for_local_nonredistributive_analysis"
    assert g1["artifact_license_verified"] is False
    assert g1["artifact_license_status"] == "unknown_pending_confirmation"
    ev = g1["evidence"]
    assert ev["inventoried_files"] == 91
    assert ev["license_named_files_found"] == []
    assert ev["article_license_scope"] == "article_only"
    assert ev["article_license_does_not_auto_cover_artifact"] is True
    cp = g1["containment_policy"]
    assert cp["raw_redistribution_allowed"] is False
    assert cp["raw_publication_allowed"] is False
    assert cp["references_mutation_allowed"] is False
    # the inventory is hash-bound and matches disk
    assert len(g1["inventory"]) == 91
    for entry in g1["inventory"]:
        p = ROOT.parent / entry["path"]
        assert p.is_file()
        assert _sha(p.read_bytes()) == entry["sha256"]
        assert p.stat().st_size == entry["byte_size"]


def test_g2_activation_applied() -> None:
    g2 = _load(G2_REL)
    assert g2["status"] == "applied_local_read_only"
    assert g2["scope"] == AUTHORIZATION_SCOPE
    assert any("deterministic parsing" in p for p in g2["permitted"])
    assert any("human review" in p for p in g2["permitted"])
    assert any("modifying references" in f for f in g2["forbidden"])
    assert any("API/network inference" in f for f in g2["forbidden"])
    assert "membership manifest" in g2["read_discipline"]
    assert g2["bindings"]["user_authorization_event_id"] == \
        _load(USER_AUTH_REL)["event_id"]


def test_g3_m1_policy_applied() -> None:
    policy = _load(POLICY_REL)
    assert policy["selected_option"] == "M1"
    assert policy["modality_identity"] == {
        "obligation": "obligation",
        "permission": "permission",
        "prohibition": "prohibition",
    }
    assert policy["candidate_only"] is True
    assert policy["gold_authorization"] is False
    assert "never auto-produced" in policy["definition_handling"]
    assert policy["external_annotation_role"] == \
        "review aid only; never the final answer"
    assert policy["bindings"]["user_authorization_event_sha256"] == \
        _sha_file(USER_AUTH_REL)
    adapter = ROOT / policy["bindings"]["adapter_source_path"]
    assert adapter.is_file()
    assert _sha(adapter.read_bytes()) == \
        policy["bindings"]["adapter_source_sha256"]


def test_g6_conservative_structural_policy_is_s0() -> None:
    policy = _load(POLICY_REL)
    assert policy["structural_policy"] == \
        "S0_no_automatic_structural_mapping"
    assert policy["field_mapping"] == {}
    reason = policy["structural_policy_reason"].lower()
    assert "nested logical objects" in reason
    assert "never inferred" in reason


# ---------------------------------------------------------------------------
# G4 sealed chain + G0.5 frozen state
# ---------------------------------------------------------------------------
def test_g4_sealed_chain_validates_real_application() -> None:
    result = validate_frozen_application(
        ROOT / DRAFT_REL, ROOT / FROZEN_REL, ROOT / MANIFEST_REL,
        project_root=ROOT)
    assert result["frozen_application_valid"] is True
    assert result["draft_config_sha256"] == DRAFT_RAW_SHA
    assert result["approved_frozen_config_sha256"] == _sha_file(FROZEN_REL)
    assert result["prior_results_found"] == []
    assert result["authorization_event_id"] == \
        _load(EVENT_REL)["event_id"]


def test_g4_frozen_config_fields() -> None:
    frozen = _load(FROZEN_REL)
    assert frozen["status"] == "frozen"
    assert frozen["frozen_before_new_results"] is True
    assert frozen["retrospective_use_forbidden"] is True
    assert frozen["s2_10_retrospective_use_forbidden"] is True
    assert frozen["scope"] == "future_external_complex_corpora_only"
    assert frozen["draft_config_sha256"] == DRAFT_RAW_SHA
    assert frozen["application_checkpoint"]["pending_commit_not_applied"] \
        is True
    # the frozen config reuses the draft rule payload unchanged
    draft = _load(DRAFT_REL)
    for key in ("fields", "levels", "config_version"):
        assert frozen[key] == draft[key]


def test_classify_frozen_works_with_real_frozen_config() -> None:
    out = classify_frozen(
        {"text_length": 150, "clause_count": 2, "dependency_depth": 3,
         "actor_count": 1, "action_count": 2, "condition_count": 1,
         "constraint_count": 1, "exception_count": 0, "nesting_depth": 1,
         "passive_voice_count": 0, "implicit_actor_count": 0,
         "cross_reference_count": 0, "language_markers": "original",
         "bpmn_activities": 8, "bpmn_gateways": 2, "bpmn_flows": 10,
         "bpmn_pools_lanes": 1, "bpmn_parallel_branches": 1,
         "bpmn_cycles": 0},
        draft_config_path=ROOT / DRAFT_REL,
        frozen_config_path=ROOT / FROZEN_REL,
        authorization_manifest_path=ROOT / MANIFEST_REL,
        project_root=ROOT)
    assert out["level"] == "L1"
    assert out["status"] == "frozen"


def test_g0_5_readiness_reports_frozen_state() -> None:
    readiness = derive_promotion_readiness(ROOT)
    assert readiness["g0_5_status"] == FROZEN_STATUS
    assert readiness["validated_asset_combinations"] >= 1
    assert readiness["prior_results_found"] == []
    assert readiness["preregistration_claim_allowed"] is False
    # the frozen config + manifest are discovered
    assert FROZEN_REL.split("/")[-1] in \
        " ".join(readiness["frozen_configs_found"])
    assert MANIFEST_REL.split("/")[-1] in \
        " ".join(readiness["authorization_manifests_found"])


def test_draft_config_stays_byte_unchanged() -> None:
    assert _sha_file(DRAFT_REL) == DRAFT_RAW_SHA
    draft = _load(DRAFT_REL)
    assert draft["status"] == "draft_not_frozen"
    assert draft["retrospective_use_forbidden"] is True


def test_no_candidates_before_freeze() -> None:
    # The sealed chain's prior-results scan (data/results/*g05* and
    # outputs/evidence/*g05*) must stay EMPTY: the freeze was applied
    # before any candidate/result existed. The Checkpoint B candidate
    # artifacts live ONLY in the gitignored local working directory
    # (outputs/development/s2_11_local_working), which the scan patterns
    # deliberately do not cover.
    scan = derive_prior_results(ROOT)
    assert scan["result_paths"] == []
    local_dir = LOCAL_WORKING_DIR
    if local_dir.is_dir():
        local_files = sorted(p for p in local_dir.rglob("*")
                             if p.is_file())
        assert local_files, "local working dir must not be empty after B"
        # the local artifacts are NOT committed (git-ignored)
        import subprocess as _sp
        proc = _sp.run(["git", "check-ignore", "--",
                        str(local_files[0].relative_to(ROOT))],
                       cwd=ROOT, capture_output=True, text=True)
        assert proc.returncode == 0, \
            "local candidate artifacts must be git-ignored"


# ---------------------------------------------------------------------------
# Report / manifest bindings + non-advancement
# ---------------------------------------------------------------------------
def test_gates_report_states() -> None:
    report = _load(GATES_REL)
    gates = report["gates"]
    assert gates["G1"]["status"] == \
        "resolved_for_local_nonredistributive_analysis"
    assert gates["G2"]["status"] == "applied_local_read_only"
    assert gates["G3"]["status"] == "applied"
    assert gates["G4"]["status"] == "applied"
    assert gates["G4"]["chain_validation"]["frozen_application_valid"] \
        is True
    assert gates["G5"]["status"] == "not_applied_until_checkpoint_b"
    assert gates["G6"]["policy"] == "S0_no_automatic_structural_mapping"
    assert report["g0_5"]["status"] == FROZEN_STATUS
    assert report["no_candidates_before_freeze"] is True
    assert report["s2_13_s3_7_not_advanced"] is True
    assert report["zero_api"]["new_llm_api_calls"] == 0


def test_gates_manifest_bindings_match_disk() -> None:
    manifest = _load(GATES_MANIFEST_REL)
    bindings = manifest["bindings"]
    assert bindings[DRAFT_REL] == DRAFT_RAW_SHA
    assert bindings[FROZEN_REL] == _sha_file(FROZEN_REL)
    assert bindings[MANIFEST_REL] == _sha_file(MANIFEST_REL)
    assert bindings[EVENT_REL] == _sha_file(EVENT_REL)
    assert bindings[USER_AUTH_REL] == _sha_file(USER_AUTH_REL)
    assert bindings[POLICY_REL] == _sha_file(POLICY_REL)
    assert bindings[G1_REL] == _sha_file(G1_REL)
    assert bindings[G2_REL] == _sha_file(G2_REL)
    assert bindings[GATES_REL] == _sha_file(GATES_REL)
    assert manifest["determinism"]["no_wall_clock"] is True
    assert manifest["determinism"]["no_overwrite"] is True


def test_no_oracle_authorization_sentence_anywhere() -> None:
    report = _load(GATES_REL)
    text = json.dumps(report, ensure_ascii=False)
    assert "Oracle" not in text
    assert "s2_13_s3_7_not_advanced" in report

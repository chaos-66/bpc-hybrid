# -*- coding: utf-8 -*-
"""Deterministic builder for the S2.11 / G0.5 CHECKPOINT A applied-gates
assets (user-authorized non-API application round).

Builds (all under formal_experiment/, no wall-clock, no-overwrite):
  configs/g05_authorization_event_v1.json
  configs/g05_authorization_manifest_v1.json
  configs/g05_complexity_frozen_v1.json
  configs/s2_11_user_authorization_event_v1.json
  configs/s2_11_mapping_policy_m1_v1.json
  outputs/reports/s2_11_g1_license_containment_v1.json
  outputs/reports/s2_11_g2_activation_v1.json
  outputs/reports/s2_11_gates_applied_checkpoint_a_v1.json
  outputs/reports/s2_11_gates_applied_checkpoint_a_v1.manifest.json

What is APPLIED here (all recorded, no gate flips beyond the user's
forwarded authorization):
  * G1  -> resolved_for_local_nonredistributive_analysis (no authoritative
           artifact license found; containment policy applied; license is
           NOT claimed verified)
  * G2  -> applied_local_read_only (scope local_read_only_nonredistributive_s2_11)
  * G3  -> applied (M1 modality identity candidate mapping)
  * G4  -> applied (G0.5 frozen for future external complex corpora via
           the sealed v6 validation chain: draft/frozen configs, the
           authorization manifest, the append-only authorization event
           and the empty prior-results scan all re-verified from disk)
  * G6  -> applied (S0_no_automatic_structural_mapping: the real artifact
           records {ID, version, text} carry NO verifiable leaf-span
           structure fields, so no structural field is auto-mapped)
  * G5  -> NOT applied here: the blank review surface opens in Checkpoint
           B once membership/workload are known.

The user's forwarded instruction
  '除了用apikey的时候要授权，其他直接正常进行即可。'
authorizes all non-API, non-destructive, local pipeline operations; it
does NOT authorize real LLM/API calls, does NOT grant third-party IP, and
does NOT authorize fabricating human Gold. When the artifact license is
unknown, only local read-only non-redistributive research use applies.

The original G0.5 draft config stays byte-unchanged as historical
provenance; S2.10 results are never re-labeled preregistered.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g05_complexity_candidate import (  # noqa: E402
    APPROVED_AUTHORIZATION_SCOPE,
    AUTHORIZATION_EVENT_KIND,
    AUTHORIZATION_MANIFEST_SCHEMA_VERSION,
    approved_authorization_sentence,
    derive_prior_results,
    validate_frozen_application,
)

DRAFT_CONFIG_REL = "configs/g05_complexity_candidate_draft_v1.json"
DRAFT_CONFIG_RAW_SHA256 = \
    "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"
FROZEN_CONFIG_REL = "configs/g05_complexity_frozen_v1.json"
AUTHORIZATION_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"
AUTHORIZATION_EVENT_REL = "configs/g05_authorization_event_v1.json"
USER_AUTHORIZATION_EVENT_REL = "configs/s2_11_user_authorization_event_v1.json"
MAPPING_POLICY_REL = "configs/s2_11_mapping_policy_m1_v1.json"
G1_REPORT_REL = "outputs/reports/s2_11_g1_license_containment_v1.json"
G2_REPORT_REL = "outputs/reports/s2_11_g2_activation_v1.json"
GATES_REPORT_REL = "outputs/reports/s2_11_gates_applied_checkpoint_a_v1.json"
GATES_MANIFEST_REL = \
    "outputs/reports/s2_11_gates_applied_checkpoint_a_v1.manifest.json"

# The user's forwarded instruction (current task) and its exact UTF-8 hash.
USER_INSTRUCTION = "除了用apikey的时候要授权，其他直接正常进行即可。"
USER_INSTRUCTION_SHA256 = \
    "a8a1dec4c826b1303fde64f2ac111ea2886ad0b08fd8a20af68b5a67130bfc64"
USER_AUTHORIZATION_SOURCE = "user_instruction_forwarded_in_current_task"
USER_AUTHORIZATION_EVENT_ID = "s2-11-user-auth-2026-08-17-v1"
G05_AUTHORIZATION_EVENT_ID = "g05-freeze-event-2026-08-17-v1"
G05_AUTHORIZATION_MANIFEST_ID = "g05-auth-manifest-2026-08-17-v1"

AUTHORIZATION_SCOPE = "local_read_only_nonredistributive_s2_11"
FROZEN_STATUS = "frozen_for_future_external_complex_corpora"

ARTIFACT_DIR = "references/barrientos_2026"
ARTIFACT_URL = ("https://anonymous.4open.science/r/"
                "Requirements_Change_for_Business_Process_Compliance")
LICENSE_NAME_RE = ("license", "copying", "notice", "readme", "metadata")


class BuilderFail(Exception):
    """Fail-closed build abort."""


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuilderFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n") \
        .encode("utf-8")
    _write(path, data)


def _require_asset(rel: str, what: str) -> str:
    p = ROOT / rel
    if not p.is_file():
        raise BuilderFail(f"fail-closed: required asset missing: {rel} "
                          f"({what})")
    return _sha256_file(p)


def _containment_policy() -> dict[str, Any]:
    return {
        "artifact_license_verified": False,
        "artifact_license_status": "unknown_pending_confirmation",
        "local_read_only_research_use_authorized_by_user": True,
        "raw_redistribution_allowed": False,
        "raw_publication_allowed": False,
        "references_mutation_allowed": False,
        "formal_export_may_include_only_hashes_ids_aggregates_and_user_created_decisions": True,
    }


def build_user_authorization_event() -> dict[str, Any]:
    return {
        "kind": "user_authorization",
        "event_id": USER_AUTHORIZATION_EVENT_ID,
        "event_seq": 1,
        "source": USER_AUTHORIZATION_SOURCE,
        "user_instruction_utf8": USER_INSTRUCTION,
        "user_instruction_utf8_sha256": USER_INSTRUCTION_SHA256,
        "normalized_scope": [
            "all non-API, non-destructive, local pipeline operations may "
            "proceed directly and be recorded",
            "G2/G3/G4/G5/G6 may be applied under conservative schemes and "
            "recorded",
            "real LLM/API calls are NOT authorized",
            "no third-party intellectual property grant is claimed on "
            "behalf of the user",
            "when the artifact license is unknown, only local read-only "
            "research use is authorized; raw redistribution and raw "
            "publication are forbidden",
            "the agent must not fabricate human Gold",
        ],
        "authorization_scope": AUTHORIZATION_SCOPE,
        "gates_covered": ["G1", "G2", "G3", "G4", "G5", "G6"],
        "containment_policy": _containment_policy(),
        "append_only": True,
    }


def build_g05_authorization_event(manifest_id: str) -> dict[str, Any]:
    sentence = approved_authorization_sentence(DRAFT_CONFIG_RAW_SHA256)
    return {
        "kind": AUTHORIZATION_EVENT_KIND,
        "event_id": G05_AUTHORIZATION_EVENT_ID,
        "authorization_sentence": sentence,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "manifest_id": manifest_id,
        "append_only": True,
        "gate_application": "G4_G0_5_future_corpus_freeze",
        "user_authorization_event_id": USER_AUTHORIZATION_EVENT_ID,
        "user_instruction_utf8_sha256": USER_INSTRUCTION_SHA256,
        "user_instruction_source": USER_AUTHORIZATION_SOURCE,
    }


def build_frozen_config() -> dict[str, Any]:
    draft = _load_json(ROOT / DRAFT_CONFIG_REL)
    if draft.get("status") != "draft_not_frozen":
        raise BuilderFail(
            "fail-closed: draft config status is "
            f"{draft.get('status')!r}")
    if _sha256_file(ROOT / DRAFT_CONFIG_REL) != DRAFT_CONFIG_RAW_SHA256:
        raise BuilderFail(
            "fail-closed: draft config raw-byte hash drifted from "
            f"{DRAFT_CONFIG_RAW_SHA256[:12]}...")
    frozen = dict(draft)
    frozen.update({
        "status": "frozen",
        "status_reason": (
            "G0.5 frozen for future external complex corpora by user "
            "authorization (Checkpoint A, 2026-08-17); the draft config "
            "stays byte-unchanged as historical provenance; S2.10 results "
            "are never re-labeled preregistered"),
        "frozen_before_new_results": True,
        "retrospective_use_forbidden": True,
        "s2_10_retrospective_use_forbidden": True,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "draft_config_path": DRAFT_CONFIG_REL,
        "draft_config_sha256": DRAFT_CONFIG_RAW_SHA256,
        "authorization_manifest_id": G05_AUTHORIZATION_MANIFEST_ID,
        "authorization_event_id": G05_AUTHORIZATION_EVENT_ID,
        "application_checkpoint": {
            "pending_commit_not_applied": True,
            "commit_sha256": None,
        },
    })
    return frozen


def build_authorization_manifest(frozen_sha: str,
                                 event_sha: str) -> dict[str, Any]:
    sentence = approved_authorization_sentence(DRAFT_CONFIG_RAW_SHA256)
    scan = derive_prior_results(ROOT)
    if scan["result_paths"]:
        raise BuilderFail(
            "fail-closed: prior results exist before the freeze: "
            + "; ".join(scan["result_paths"][:10]))
    return {
        "schema_version": AUTHORIZATION_MANIFEST_SCHEMA_VERSION,
        "manifest_id": G05_AUTHORIZATION_MANIFEST_ID,
        "authorization_applied": True,
        "draft_config_path": DRAFT_CONFIG_REL,
        "draft_config_sha256": DRAFT_CONFIG_RAW_SHA256,
        "approved_frozen_config_path": FROZEN_CONFIG_REL,
        "approved_frozen_config_sha256": frozen_sha,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "authorization_sentence": sentence,
        "authorization_sentence_sha256": _sha256_bytes(
            sentence.encode("utf-8")),
        "retrospective_use_forbidden": True,
        "frozen_before_new_results": True,
        "s2_10_retrospective_use_forbidden": True,
        "prior_results_scan_sha256": scan["scan_sha256"],
        "authorization_event_id": G05_AUTHORIZATION_EVENT_ID,
        "authorization_event_path": AUTHORIZATION_EVENT_REL,
        "authorization_event_sha256": event_sha,
        "application_checkpoint": {
            "pending_commit_not_applied": True,
            "commit_sha256": None,
        },
        "user_authorization": {
            "event_id": USER_AUTHORIZATION_EVENT_ID,
            "instruction_utf8_sha256": USER_INSTRUCTION_SHA256,
            "source": USER_AUTHORIZATION_SOURCE,
        },
    }


def build_mapping_policy(auth_event_sha: str) -> dict[str, Any]:
    adapter_rel = "src/bpc_hybrid/s2_11_barrientos_adapter.py"
    return {
        "schema_version": "s2_11_mapping_policy@1.0.0",
        "policy_id": "s2-11-m1-candidate-modality-identity",
        "selected_option": "M1",
        "modality_identity": {
            "obligation": "obligation",
            "permission": "permission",
            "prohibition": "prohibition",
        },
        "structural_policy": "S0_no_automatic_structural_mapping",
        "structural_policy_reason": (
            "the real artifact requirement records are "
            "{ID, version, text} natural-language sentences; the "
            "compliance_requirements_format.json schema defines "
            "precondition/temporal_validity as NESTED logical objects "
            "(and/or/not actions), not verifiable leaf-text spans; no "
            "structure field is auto-mapped; actor/action/exception are "
            "never inferred from missing structure; unresolvable fields "
            "stay blank for human adjudication"),
        "field_mapping": {},
        "candidate_only": True,
        "definition_handling": ("never auto-produced; definition-class "
                                "records require separate human "
                                "adjudication"),
        "external_annotation_role": ("review aid only; never the final "
                                     "answer"),
        "gold_authorization": False,
        "bindings": {
            "user_authorization_event_id": USER_AUTHORIZATION_EVENT_ID,
            "user_authorization_event_sha256": auth_event_sha,
            "adapter_source_path": adapter_rel,
            "adapter_source_sha256": _require_asset(
                adapter_rel, "adapter source"),
        },
    }


def build_g1_containment() -> dict[str, Any]:
    artifact_root = ROOT.parent / ARTIFACT_DIR
    if not artifact_root.is_dir():
        raise BuilderFail("fail-closed: artifact directory missing")
    files = sorted(p for p in artifact_root.rglob("*") if p.is_file())
    inventory = []
    license_named = []
    for p in files:
        rel = p.relative_to(ROOT.parent).as_posix()
        entry = {"path": rel,
                 "sha256": _sha256_file(p),
                 "byte_size": p.stat().st_size}
        inventory.append(entry)
        name_lower = p.name.lower()
        if any(tok in name_lower for tok in LICENSE_NAME_RE):
            license_named.append(rel)
    return {
        "schema_version": "s2_11_g1_license@1.0.0",
        "status": "resolved_for_local_nonredistributive_analysis",
        "artifact_license_verified": False,
        "artifact_license_status": "unknown_pending_confirmation",
        "evidence": {
            "artifact_dir": ARTIFACT_DIR,
            "inventoried_files": len(inventory),
            "license_named_files_found": license_named,
            "artifact_url": ARTIFACT_URL,
            "artifact_url_license_check": (
                "no resolvable license identifier on the anonymous "
                "artifact page (anonymous preview; no login/token used; "
                "no bulk download)"),
            "article_license": "CC-BY-4.0",
            "article_license_scope": "article_only",
            "article_license_does_not_auto_cover_artifact": True,
        },
        "containment_policy": _containment_policy(),
        "conclusion": (
            "no authoritative artifact license was found; the user "
            "authorized local read-only non-redistributive research use; "
            "artifact_license_verified stays false; raw text is never "
            "copied into committed formal reports/public packages; the "
            "review tool loads raw text read-only from references at "
            "runtime"),
        "inventory": inventory,
    }


def build_g2_activation(auth_event_sha: str) -> dict[str, Any]:
    return {
        "schema_version": "s2_11_activation@1.0.0",
        "activation_id": "s2-11-local-read-only-activation-v1",
        "status": "applied_local_read_only",
        "scope": AUTHORIZATION_SCOPE,
        "permitted": [
            "deterministic parsing of membership-listed files",
            "hash inventory and membership locking",
            "candidate generation (M1 + applied G6 policy)",
            "G0.5 frozen classification",
            "human review of candidates",
        ],
        "forbidden": [
            "modifying references/",
            "publishing raw payloads",
            "API/network inference",
            "external annotation as the final answer",
            "fabricating human Gold",
        ],
        "read_discipline": (
            "formal runs read ONLY the files listed in the membership "
            "manifest (relative path + raw-byte SHA-256 + size); any "
            "other read refuses"),
        "bindings": {
            "user_authorization_event_id": USER_AUTHORIZATION_EVENT_ID,
            "user_authorization_event_sha256": auth_event_sha,
        },
    }


def _g4_validation() -> dict[str, Any]:
    result = validate_frozen_application(
        ROOT / DRAFT_CONFIG_REL,
        ROOT / FROZEN_CONFIG_REL,
        ROOT / AUTHORIZATION_MANIFEST_REL,
        project_root=ROOT)
    return {
        "frozen_application_valid": bool(
            result["frozen_application_valid"]),
        "validation_token_prefix": result["validation_token"][:12],
        "draft_config_sha256": result["draft_config_sha256"],
        "approved_frozen_config_sha256": result[
            "approved_frozen_config_sha256"],
        "authorization_event_id": result["authorization_event_id"],
        "prior_results_found": list(result["prior_results_found"]),
    }


def build_gates_report(bindings: dict[str, str]) -> dict[str, Any]:
    frozen_sha = bindings[FROZEN_CONFIG_REL]
    g4 = _g4_validation()
    return {
        "schema_version": "s2_11_gates_applied@1.0.0",
        "report_id": "s2_11_gates_applied_checkpoint_a_v1",
        "build_note": (
            "Checkpoint A of the user-authorized non-API application "
            "round: G1/G2/G3/G4/G6 applied and recorded; G5 opens in "
            "Checkpoint B after membership/workload are known; the v6 "
            "pre-authorization capsule stays as the historical safety "
            "baseline (byte-exact); no real LLM/API calls; no Gold "
            "created; no S2.13/S3.7 advancement."),
        "user_authorization": {
            "event_id": USER_AUTHORIZATION_EVENT_ID,
            "instruction_utf8_sha256": USER_INSTRUCTION_SHA256,
            "source": USER_AUTHORIZATION_SOURCE,
            "scope": AUTHORIZATION_SCOPE,
        },
        "gates": {
            "G1": {
                "status": "resolved_for_local_nonredistributive_analysis",
                "artifact_license_verified": False,
                "artifact_license_status": "unknown_pending_confirmation",
                "report": G1_REPORT_REL,
            },
            "G2": {
                "status": "applied_local_read_only",
                "scope": AUTHORIZATION_SCOPE,
                "report": G2_REPORT_REL,
            },
            "G3": {
                "status": "applied",
                "policy_id": "s2-11-m1-candidate-modality-identity",
                "option": "M1",
                "policy": MAPPING_POLICY_REL,
            },
            "G4": {
                "status": "applied",
                "frozen_config": FROZEN_CONFIG_REL,
                "frozen_config_sha256": frozen_sha,
                "authorization_manifest": AUTHORIZATION_MANIFEST_REL,
                "authorization_event": AUTHORIZATION_EVENT_REL,
                "chain_validation": g4,
            },
            "G5": {
                "status": "not_applied_until_checkpoint_b",
                "reason": "membership/workload unknown until the corpus "
                          "inventory completes",
            },
            "G6": {
                "status": "applied",
                "policy": "S0_no_automatic_structural_mapping",
                "field_mapping": {},
                "policy_config": MAPPING_POLICY_REL,
            },
        },
        "g0_5": {
            "status": FROZEN_STATUS,
            "draft_config": DRAFT_CONFIG_REL,
            "draft_config_sha256": DRAFT_CONFIG_RAW_SHA256,
            "frozen_config_sha256": frozen_sha,
            "scope": APPROVED_AUTHORIZATION_SCOPE,
            "preregistration_claim_allowed": False,
        },
        "no_candidates_before_freeze": True,
        "s2_13_s3_7_not_advanced": True,
        "zero_api": {"new_llm_api_calls": 0},
        "bindings": bindings,
    }


def build_gates_manifest(hashes: dict[str, str]) -> dict[str, Any]:
    return {
        "schema_version": "s2_11_gates_applied_manifest@1.0.0",
        "manifest_id": "s2_11_gates_applied_checkpoint_a_v1.manifest",
        "artifact_type": "applied_gates_checkpoint",
        "determinism": {
            "no_wall_clock": True,
            "byte_identical_rebuild": True,
            "no_overwrite": True,
        },
        "bindings": dict(sorted(hashes.items())),
        "zero_api": {"new_llm_api_calls": 0},
    }


def main() -> int:
    try:
        user_auth = build_user_authorization_event()
        if _sha256_bytes(user_auth["user_instruction_utf8"].encode("utf-8")) \
                != USER_INSTRUCTION_SHA256:
            raise BuilderFail("fail-closed: user instruction hash mismatch")
        _write_json(ROOT / USER_AUTHORIZATION_EVENT_REL, user_auth)
        user_auth_sha = _sha256_file(ROOT / USER_AUTHORIZATION_EVENT_REL)

        frozen = build_frozen_config()
        _write_json(ROOT / FROZEN_CONFIG_REL, frozen)
        frozen_sha = _sha256_file(ROOT / FROZEN_CONFIG_REL)

        g05_event = build_g05_authorization_event(G05_AUTHORIZATION_MANIFEST_ID)
        _write_json(ROOT / AUTHORIZATION_EVENT_REL, g05_event)
        event_sha = _sha256_file(ROOT / AUTHORIZATION_EVENT_REL)

        manifest = build_authorization_manifest(frozen_sha, event_sha)
        _write_json(ROOT / AUTHORIZATION_MANIFEST_REL, manifest)

        policy = build_mapping_policy(user_auth_sha)
        _write_json(ROOT / MAPPING_POLICY_REL, policy)

        g1 = build_g1_containment()
        _write_json(ROOT / G1_REPORT_REL, g1)

        g2 = build_g2_activation(user_auth_sha)
        _write_json(ROOT / G2_REPORT_REL, g2)

        # Re-verify the sealed chain on the written bytes before reporting.
        validation = _g4_validation()
        if not validation["frozen_application_valid"]:
            raise BuilderFail("fail-closed: frozen chain did not validate")
        if validation["prior_results_found"]:
            raise BuilderFail("fail-closed: prior results before freeze")

        asset_rels = (
            USER_AUTHORIZATION_EVENT_REL,
            FROZEN_CONFIG_REL,
            AUTHORIZATION_EVENT_REL,
            AUTHORIZATION_MANIFEST_REL,
            MAPPING_POLICY_REL,
            G1_REPORT_REL,
            G2_REPORT_REL,
            "src/bpc_hybrid/g05_complexity_candidate.py",
            "src/bpc_hybrid/s2_11_barrientos_adapter.py",
        )
        hashes = {rel: _require_asset(rel, "checkpoint A asset")
                  for rel in asset_rels}
        hashes[DRAFT_CONFIG_REL] = DRAFT_CONFIG_RAW_SHA256

        report = build_gates_report(hashes)
        _write_json(ROOT / GATES_REPORT_REL, report)
        hashes[GATES_REPORT_REL] = _sha256_file(ROOT / GATES_REPORT_REL)

        gates_manifest = build_gates_manifest(hashes)
        _write_json(ROOT / GATES_MANIFEST_REL, gates_manifest)
    except BuilderFail as exc:
        print(f"BUILD FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2

    print(f"checkpoint A applied gates written: {GATES_REPORT_REL}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

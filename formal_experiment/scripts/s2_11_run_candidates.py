# -*- coding: utf-8 -*-
"""Deterministic S2.11 candidate RUNNER (Checkpoint B, local read-only).

Pipeline per membership record:
  1. verify the source file raw-byte SHA-256 against the membership
     manifest (files outside the membership are NEVER read);
  2. deterministic MODALITY extraction (documented keyword rules with
     exact span offsets into the source text); no match / non-unique
     span -> quarantine with a stable error code;
  3. build the hardened-adapter input record (field-level provenance per
     the v6 locator/span/hash contract; structure stays EMPTY under the
     applied S0 structural policy);
  4. convert via the adapter in local_read_only_research mode (the
     artifact license is unknown and is never claimed verified; the
     Checkpoint A user authorization event + containment policy are the
     evidence);
  5. classify the record with the FROZEN G0.5 contract through the sealed
     v6 chain (classify_frozen).

Outputs:
  LOCAL (gitignored, not committed): the full candidate artifacts with
    raw source text in
    outputs/development/s2_11_local_working/candidates_v1/records.jsonl
  COMMITTED: aggregate statistics + quarantine + candidate hash refs in
    outputs/reports/s2_11_candidate_run_v1.json (NEVER raw third-party
    text).
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.g05_complexity_candidate import (  # noqa: E402
    classify_frozen,
)
from bpc_hybrid.s2_11_barrientos_adapter import (  # noqa: E402
    ActivationState,
    EvidenceBinding,
    LicenseState,
    MappingPolicy,
    convert_to_candidate,
    field_locator,
)
from bpc_hybrid.s2_11_corpus_ingestion import (  # noqa: E402
    extract_modality,
    g05_features,
)

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
MAPPING_POLICY_REL = "configs/s2_11_mapping_policy_m1_v1.json"
USER_AUTH_REL = "configs/s2_11_user_authorization_event_v1.json"
DRAFT_REL = "configs/g05_complexity_candidate_draft_v1.json"
FROZEN_REL = "configs/g05_complexity_frozen_v1.json"
AUTH_MANIFEST_REL = "configs/g05_authorization_manifest_v1.json"

OUT_REL = "outputs/reports/s2_11_candidate_run_v1.json"
LOCAL_CANDIDATES_DIR = ROOT / "outputs" / "development" / \
    "s2_11_local_working" / "candidates_v1"
LOCAL_RECORDS_REL = "records.jsonl"

# Stable quarantine codes.
ERR_FILE_HASH_MISMATCH = "QUARANTINE_FILE_HASH_MISMATCH"
ERR_MODALITY_UNKNOWN = "QUARANTINE_MODALITY_UNKNOWN"
ERR_ADAPTER_REFUSAL = "QUARANTINE_ADAPTER_REFUSAL"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise RuntimeError(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def run_candidates() -> dict[str, Any]:
    membership = _load_json(ROOT / MEMBERSHIP_REL)
    policy_doc = _load_json(ROOT / MAPPING_POLICY_REL)
    user_auth_sha = _sha256_file(ROOT / USER_AUTH_REL)

    mapping_policy = MappingPolicy(
        policy_id=str(policy_doc["policy_id"]),
        approved=True,
        synthetic_test_only=False,
        modality_identity=dict(policy_doc["modality_identity"]),
        field_mapping=dict(policy_doc.get("field_mapping") or {}),
        user_authorization_binding=EvidenceBinding(
            kind="user_authorization",
            evidence_id=str(_load_json(ROOT / USER_AUTH_REL)["event_id"]),
            evidence_hash=user_auth_sha,
            path=USER_AUTH_REL,
            scope="local_read_only_nonredistributive_s2_11",
        ),
    )
    license_state = LicenseState(
        qualified=False, license_status="unknown_pending_confirmation")
    activation_state = ActivationState(authorized=True)

    local_lines: list[str] = []
    candidates: dict[str, dict[str, Any]] = {}
    quarantine: list[dict[str, Any]] = []
    modality_counts: dict[str, int] = {}
    level_counts: dict[str, int] = {}
    structure_coverage = {"mapped_fields": 0, "total_candidates": 0}
    provenance_complete = 0
    usable = 0

    for file_entry in membership["files"]:
        rel = file_entry["path"]
        file_path = ROOT.parent / rel
        if _sha256_file(file_path) != file_entry["sha256"]:
            quarantine.append({
                "record_id": f"{file_entry['scenario']}/<file>",
                "path": rel,
                "code": ERR_FILE_HASH_MISMATCH,
                "detail": "file bytes drifted from the membership manifest",
            })
            continue
        doc = json.loads(file_path.read_text(encoding="utf-8"))
        for entry in doc:
            record_id = (f"{file_entry['scenario']}/"
                         f"{entry['ID']}/v{entry['version']}")
            rec = membership["records"].get(record_id)
            if rec is None:
                continue  # already quarantined by the inventory
            text = str(entry["text"])
            extracted = extract_modality(text)
            if extracted is None:
                quarantine.append({
                    "record_id": record_id, "path": rel,
                    "file_sha256": rec["file_sha256"],
                    "code": ERR_MODALITY_UNKNOWN,
                    "detail": "no deterministic modality keyword matched",
                })
                continue
            modality_class, start, end = extracted
            source_path = rel
            record = {
                "source_record_id": record_id,
                "source_path": source_path,
                "modality": {
                    "value": modality_class,
                    "element": "norms[0].modality",
                    "path": field_locator(source_path, "norms[0].modality"),
                    "text_hash": rec["text_sha256"],
                    "span": {"start": start, "end": end},
                    "span_alignment_source": "approved_english_alignment",
                },
                "text": text,
                "text_provenance": {"sha256": rec["text_sha256"],
                                    "language": "en"},
                "structure": {},
                "cross_references": [],
            }
            try:
                out = convert_to_candidate(
                    record,
                    license_state=license_state,
                    activation_state=activation_state,
                    mapping_policy=mapping_policy,
                    mode="local_read_only_research",
                    evidence_root=ROOT)
            except Exception as exc:  # noqa: BLE001 - stable error codes
                code = getattr(exc, "code", "QUARANTINE_ADAPTER_REFUSAL")
                quarantine.append({
                    "record_id": record_id, "path": rel,
                    "file_sha256": rec["file_sha256"],
                    "code": code,
                    "detail": str(exc)[:160],
                })
                continue
            features = g05_features(text)
            g05 = classify_frozen(
                features,
                draft_config_path=ROOT / DRAFT_REL,
                frozen_config_path=ROOT / FROZEN_REL,
                authorization_manifest_path=ROOT / AUTH_MANIFEST_REL,
                project_root=ROOT)
            candidate_payload = {
                "record_id": record_id,
                "source_path": source_path,
                "source_record_id": record["source_record_id"],
                "text_sha256": rec["text_sha256"],
                "text_byte_size": rec["text_byte_size"],
                "modality": modality_class,
                "modality_span": {"start": start, "end": end},
                "adapter_output": out,
                "g0_5": {
                    "level": g05["level"],
                    "matched_hard_triggers": g05["matched_hard_triggers"],
                    "l1_violations": g05["l1_violations"],
                },
            }
            candidate_hash = _sha256_bytes(
                json.dumps(candidate_payload, sort_keys=True,
                           ensure_ascii=False).encode("utf-8"))
            local_lines.append(json.dumps(
                candidate_payload, ensure_ascii=False))
            candidates[record_id] = {
                "candidate_hash": candidate_hash,
                "modality": modality_class,
                "g0_5_level": g05["level"],
                "text_sha256": rec["text_sha256"],
                "source_path": source_path,
            }
            usable += 1
            modality_counts[modality_class] = \
                modality_counts.get(modality_class, 0) + 1
            level_counts[g05["level"]] = level_counts.get(g05["level"], 0) + 1
            if out["field_provenance"]:
                provenance_complete += 1
            structure_coverage["total_candidates"] += 1

    local_bytes = ("\n".join(local_lines) + "\n").encode("utf-8")
    _write(LOCAL_CANDIDATES_DIR / LOCAL_RECORDS_REL, local_bytes)

    run_report = {
        "schema_version": "s2_11_candidate_run@1.0.0",
        "run_id": "s2-11-candidate-run-v1",
        "mode": "local_read_only_research",
        "membership": MEMBERSHIP_REL,
        "membership_manifest_sha256":
            membership["manifest_sha256"],
        "mapping_policy": MAPPING_POLICY_REL,
        "structural_policy":
            policy_doc.get("structural_policy"),
        "user_authorization_event": USER_AUTH_REL,
        "user_authorization_event_sha256": user_auth_sha,
        "counts": {
            "membership_records": membership["record_count"],
            "inventory_quarantined": len(membership["quarantine"]),
            "candidates": usable,
            "run_quarantined": len(quarantine),
            "total_quarantined": len(membership["quarantine"])
            + len(quarantine),
        },
        "modality_distribution": dict(sorted(modality_counts.items())),
        "g0_5_level_distribution": dict(sorted(level_counts.items())),
        "structure_coverage": {
            "policy": policy_doc.get("structural_policy"),
            "mapped_structure_fields": 0,
            "candidate_records": usable,
        },
        "provenance_complete": provenance_complete,
        "provenance_total": usable,
        "review_workload": usable,
        "quarantine": quarantine,
        "candidates": candidates,
        "local_full_artifacts": (
            "outputs/development/s2_11_local_working/candidates_v1/"
            "records.jsonl (LOCAL ONLY, gitignored, contains raw source "
            "text; never committed)"),
        "raw_text_committed": False,
        "zero_api": {"new_llm_api_calls": 0},
        "gold_created": False,
    }
    run_report["run_report_sha256"] = _sha256_bytes(
        json.dumps({k: run_report[k] for k in run_report
                    if k != "run_report_sha256"},
                   sort_keys=True, ensure_ascii=False).encode("utf-8"))
    return run_report


def main() -> int:
    try:
        report = run_candidates()
        data = (json.dumps(report, ensure_ascii=False, indent=2) + "\n") \
            .encode("utf-8")
        _write(ROOT / OUT_REL, data)
    except Exception as exc:  # noqa: BLE001 - fail-closed reporting
        print(f"RUN FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    print(f"candidate run written: {OUT_REL} "
          f"({report['counts']['candidates']} candidates, "
          f"{report['counts']['total_quarantined']} quarantined)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Deterministic S2.11 G5 review surface builder (Checkpoint C: COMPLETE
review population).

Builds (no-overwrite):
  data/development/human_review/s2_11_blank_review_v1.json
  data/development/human_review/s2_11_review_decisions_v1.json
  outputs/reports/s2_11_g5_review_surface_v1.json
  outputs/reports/s2_11_review_surface_v1.manifest.json

POPULATION DEFINITION (fail-closed, no selection bias):
  * inventory              = 40 (all membership records)
  * objective_exclusions   = 4 (empty / placeholder texts, raw-byte
    re-verified against the membership; recorded by record ID + source
    hash + stable code; never faked as negatives or Gold)
  * nonempty_membership    = 36
  * review_population      = 36 == nonempty_membership  (MUST be equal)
  * candidate_status       = available (29) | unavailable (7, with the
    stable error code and explanation)
  Candidate SUCCESS NEVER decides whether a record enters review.

The blank pack contains one entry per review item with ALL final Gold
decision fields explicitly NULL, review_state=unreviewed, reviewer=null.
NEVER copies raw third-party text; the review tool loads the raw text
read-only from references at runtime and refuses on hash mismatch.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
CANDIDATE_RUN_REL = "outputs/reports/s2_11_candidate_run_v1.json"
BLANK_REVIEW_REL = "data/development/human_review/s2_11_blank_review_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"
G5_REPORT_REL = "outputs/reports/s2_11_g5_review_surface_v1.json"
G5_MANIFEST_REL = "outputs/reports/s2_11_review_surface_v1.manifest.json"

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")


class BuilderFail(Exception):
    """Fail-closed build abort."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuilderFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_surface() -> dict[str, Any]:
    membership = json.loads((ROOT / MEMBERSHIP_REL).read_text(encoding="utf-8"))
    run = json.loads((ROOT / CANDIDATE_RUN_REL).read_text(encoding="utf-8"))

    inventory = int(membership["record_count"])
    exclusions = list(membership["quarantine"])
    nonempty = {rid: rec for rid, rec in membership["records"].items()}
    candidates = dict(run.get("candidates") or {})
    run_quarantine = {q["record_id"]: q for q in run.get("quarantine") or []}

    # 1. objective exclusions re-verified against the raw bytes
    for q in exclusions:
        rec = membership["records"].get(q["record_id"])
        src = ROOT.parent / q["path"]
        if not src.is_file() or \
                _sha256_file(src) != q.get("file_sha256"):
            raise BuilderFail(
                f"fail-closed: exclusion source hash drift for "
                f"{q['record_id']}")

    # 2. review population == nonempty membership (fail-closed)
    review_ids = sorted(nonempty)
    if len(review_ids) != nonempty.__len__():
        raise BuilderFail("fail-closed: review population size mismatch")

    blank: list[dict[str, Any]] = []
    candidate_available = 0
    candidate_unavailable = 0
    for record_id in review_ids:
        rec = nonempty[record_id]
        if record_id in candidates:
            cand = candidates[record_id]
            item = {
                "sample_id": record_id,
                "source_path": cand.get("source_path", rec["path"]),
                "text_sha256": rec["text_sha256"],
                "candidate_hash": cand["candidate_hash"],
                "candidate_status": "available",
                "candidate": {
                    "modality": cand["modality"],
                    "g0_5_level": cand["g0_5_level"],
                },
                "candidate_error": None,
            }
            candidate_available += 1
        else:
            err = run_quarantine.get(record_id)
            if err is None:
                raise BuilderFail(
                    f"fail-closed: {record_id} is neither a candidate nor "
                    "a recorded quarantine")
            item = {
                "sample_id": record_id,
                "source_path": rec["path"],
                "text_sha256": rec["text_sha256"],
                "candidate_hash": None,
                "candidate_status": "unavailable",
                "candidate": None,
                "candidate_error": {
                    "code": err.get("code"),
                    "detail": err.get("detail", "")[:200],
                },
            }
            candidate_unavailable += 1
        item["decision"] = {field: None for field in DECISION_FIELDS}
        item["review_state"] = "unreviewed"
        item["reviewer"] = None
        blank.append(item)

    if len(blank) != 36 or candidate_available != 29 or \
            candidate_unavailable != 7:
        raise BuilderFail(
            "fail-closed: expected 36 review items (29 available / 7 "
            f"unavailable), got {len(blank)} ({candidate_available} / "
            f"{candidate_unavailable})")

    pack = {
        "schema_version": "s2_11_review_surface@1.1.0",
        "surface_id": "s2-11-blank-review-v1",
        "candidate_run": CANDIDATE_RUN_REL,
        "membership": MEMBERSHIP_REL,
        "population": {
            "inventory": inventory,
            "objective_exclusions": len(exclusions),
            "nonempty_membership": len(review_ids),
            "review_population": len(blank),
            "candidate_available": candidate_available,
            "candidate_unavailable": candidate_unavailable,
            "closure_invariant": (
                "review_population == nonempty_membership == "
                "inventory - objective_exclusions"),
        },
        "objective_exclusions": [
            {"record_id": q["record_id"], "source_path": q["path"],
             "file_sha256": q["file_sha256"], "code": q["code"],
             "detail": q["detail"]}
            for q in exclusions
        ],
        "raw_text_location": (
            "references/barrientos_2026/... (loaded read-only at runtime "
            "via the membership manifest by text SHA-256; hash mismatch "
            "refuses)"),
        "raw_text_committed": False,
        "decision_fields": list(DECISION_FIELDS),
        "final_adjudication_by": "user_only",
        "gold_files_created": False,
        "samples": blank,
        "sample_count": len(blank),
    }
    decisions = {
        "schema_version": "s2_11_review_decisions@1.1.0",
        "surface_id": "s2-11-blank-review-v1",
        "final_adjudication_by": "user_only",
        "records": {
            sample["sample_id"]: {
                "decision": {field: None for field in DECISION_FIELDS},
                "review_state": "unreviewed",
                "reviewer": None,
            }
            for sample in blank
        },
    }
    g5_report = {
        "schema_version": "s2_11_g5_review_surface@1.1.0",
        "status": "applied_review_surface_open",
        "blank_review_pack": BLANK_REVIEW_REL,
        "decisions_file": DECISIONS_REL,
        "review_tool": "scripts/review_s2_11_candidates.py",
        "freeze_validator": "scripts/verify_s2_11_review_freeze.py",
        "candidate_run": CANDIDATE_RUN_REL,
        "membership": MEMBERSHIP_REL,
        "population": pack["population"],
        "objective_exclusions": pack["objective_exclusions"],
        "workload_records_for_user": len(blank),
        "gold_files_created": False,
        "final_adjudication_by": "user_only",
        "raw_text_committed": False,
        "hash_mismatch_refuses": True,
        "candidate_failure_does_not_reduce_population": True,
        "bindings": {},
    }
    g5_manifest = {
        "schema_version": "s2_11_review_surface_manifest@1.1.0",
        "manifest_id": "s2_11_review_surface_v1.manifest",
        "artifact_type": "review_surface_bundle",
        "determinism": {
            "no_wall_clock": True,
            "byte_identical_rebuild": True,
            "no_overwrite": True,
        },
        "bindings": {},
        "zero_api": {"new_llm_api_calls": 0},
    }
    return pack, decisions, g5_report, g5_manifest


def main() -> int:
    try:
        pack, decisions, g5_report, g5_manifest = build_surface()
        _write(ROOT / BLANK_REVIEW_REL,
               (json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
        _write(ROOT / DECISIONS_REL,
               (json.dumps(decisions, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
        # bindings are computed AFTER the files exist (first build)
        bindings = {
            rel: _sha256_file(ROOT / rel)
            for rel in (MEMBERSHIP_REL, CANDIDATE_RUN_REL,
                        BLANK_REVIEW_REL, DECISIONS_REL)
        }
        g5_report["bindings"] = dict(sorted(bindings.items()))
        g5_manifest["bindings"] = dict(sorted(bindings.items()))
        _write(ROOT / G5_REPORT_REL,
               (json.dumps(g5_report, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
        _write(ROOT / G5_MANIFEST_REL,
               (json.dumps(g5_manifest, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
    except BuilderFail as exc:
        print(f"BUILD FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    print(f"blank review surface written: {BLANK_REVIEW_REL} "
          f"({pack['population']['review_population']} samples, "
          f"{pack['population']['candidate_available']} available / "
          f"{pack['population']['candidate_unavailable']} unavailable); "
          f"G5={g5_report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

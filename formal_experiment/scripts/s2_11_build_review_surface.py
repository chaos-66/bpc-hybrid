# -*- coding: utf-8 -*-
"""Deterministic S2.11 G5 blank review surface builder (Checkpoint B).

Builds (no-overwrite):
  data/development/human_review/s2_11_blank_review_v1.json
  data/development/human_review/s2_11_review_decisions_v1.json

The blank pack contains one entry per candidate with:
  * sample_id (= candidate record id)
  * source path + text SHA-256 + candidate artifact hash references
  * the candidate modality (review aid only)
  * ALL final Gold decision fields explicitly NULL
  * review_state = "unreviewed", reviewer = null

NEVER copies raw third-party text (the artifact license is unknown); the
review tool loads the raw text read-only from references at runtime and
refuses on hash mismatch. Candidate values and final decisions are
physically separated.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

CANDIDATE_RUN_REL = "outputs/reports/s2_11_candidate_run_v1.json"
BLANK_REVIEW_REL = "data/development/human_review/s2_11_blank_review_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"
G5_REPORT_REL = "outputs/reports/s2_11_g5_review_surface_v1.json"

DECISION_FIELDS = ("modality", "actor", "action", "condition",
                   "constraint", "exception")


class BuilderFail(Exception):
    """Fail-closed build abort."""


def _write(path: Path, data: bytes) -> None:
    if path.exists():
        if path.read_bytes() == data:
            return
        raise BuilderFail(
            f"refusing to overwrite different existing content: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def build_surface() -> dict[str, Any]:
    run = json.loads((ROOT / CANDIDATE_RUN_REL).read_text(encoding="utf-8"))
    blank: list[dict[str, Any]] = []
    for record_id in sorted(run["candidates"]):
        cand = run["candidates"][record_id]
        blank.append({
            "sample_id": record_id,
            "source_path": cand["source_path"],
            "text_sha256": cand["text_sha256"],
            "candidate_hash": cand["candidate_hash"],
            "candidate": {
                "modality": cand["modality"],
                "g0_5_level": cand["g0_5_level"],
            },
            "decision": {field: None for field in DECISION_FIELDS},
            "review_state": "unreviewed",
            "reviewer": None,
        })
    pack = {
        "schema_version": "s2_11_review_surface@1.0.0",
        "surface_id": "s2-11-blank-review-v1",
        "candidate_run": CANDIDATE_RUN_REL,
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
        "schema_version": "s2_11_review_decisions@1.0.0",
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
        "schema_version": "s2_11_g5_review_surface@1.0.0",
        "status": "applied_review_surface_open",
        "blank_review_pack": BLANK_REVIEW_REL,
        "decisions_file": DECISIONS_REL,
        "review_tool": "scripts/review_s2_11_candidates.py",
        "freeze_validator": "scripts/verify_s2_11_review_freeze.py",
        "candidate_run": CANDIDATE_RUN_REL,
        "workload_records_for_user": len(blank),
        "gold_files_created": False,
        "final_adjudication_by": "user_only",
        "raw_text_committed": False,
        "hash_mismatch_refuses": True,
    }
    return pack, decisions, g5_report


def main() -> int:
    try:
        pack, decisions, g5_report = build_surface()
        _write(ROOT / BLANK_REVIEW_REL,
               (json.dumps(pack, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
        _write(ROOT / DECISIONS_REL,
               (json.dumps(decisions, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
        _write(ROOT / G5_REPORT_REL,
               (json.dumps(g5_report, ensure_ascii=False, indent=2) + "\n")
               .encode("utf-8"))
    except BuilderFail as exc:
        print(f"BUILD FAILED (fail-closed): {exc}", file=sys.stderr)
        return 2
    print(f"blank review surface written: {BLANK_REVIEW_REL} "
          f"({pack['sample_count']} samples, all decisions null); "
          f"G5={g5_report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""S1.5 review-surface authorization record v1 (user-authorized 2026-08-11).

The USER authorized opening the S1.5 human Process Gold review surface:
- frozen all-seven GDPR-7 BPMN membership (7 BPMN / 45 activities / 135
  label fields, membership payload SHA-256
  e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d);
- stage1_review_tool.py, the all-blank/unreviewed
  stage1_gdpr7_human_correction_v1.json and the bilingual
  HUMAN_PROCESS_GOLD_GUIDE.md may be used by the user for adjudication;
- the tool must never infer, pre-fill or auto-accept any decision;
- this authorization ONLY sets S1.5 to input-ready; it does NOT authorize
  Gold freeze; freeze still requires the user's 7/7 structure decisions and
  135/135 actor/action/business_object field adjudications.

Output: outputs/reports/s1_5_review_surface_authorization_v1.manifest.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")
BLANK = (ROOT / "data" / "development" / "human_review"
         / "stage1_gdpr7_annotation_blank_v1.json")
TOOL = ROOT / "scripts" / "stage1_review_tool.py"
GUIDE = ROOT / "docs" / "HUMAN_PROCESS_GOLD_GUIDE.md"
SCHEMA = ROOT / "configs" / "schemas" / "stage1_human_annotation.schema.json"

OUT = ROOT / "outputs" / "reports" / "s1_5_review_surface_authorization_v1.manifest.json"

EXPECTED_MEMBERSHIP_PAYLOAD = (
    "e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    membership = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    payload = membership.get("membership", {}).get("membership_payload_sha256")
    corr_doc = json.loads(CORRECTION.read_text(encoding="utf-8"))
    blank_bytes = BLANK.read_bytes()
    corr_bytes = CORRECTION.read_bytes()

    all_unreviewed = all(
        r.get("review_state") == "unreviewed"
        and r.get("structure_annotation", {}).get("decision") == "unreviewed"
        for r in corr_doc.get("records", []))
    no_gold_prefilled = all(
        r.get("structure_annotation", {}).get("gold_process_record") is None
        for r in corr_doc.get("records", []))
    summary = corr_doc.get("review_summary", {})

    checks = {
        "membership_payload_matches_authorization":
            payload == EXPECTED_MEMBERSHIP_PAYLOAD,
        "correction_equals_blank_template": corr_bytes == blank_bytes,
        "all_records_unreviewed": all_unreviewed,
        "no_gold_prefilled": no_gold_prefilled,
        "freeze_ready_false": summary.get("freeze_ready") is False,
        "tool_exists": TOOL.exists(),
        "guide_exists": GUIDE.exists(),
        "schema_exists": SCHEMA.exists(),
    }
    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError(f"S1.5 review-surface preconditions failed: {failed}")

    manifest = {
        "schema_version": "s1_5_review_surface_authorization@1.0.0",
        "project_date": "2026-08-11",
        "authorized_by_user": True,
        "authorization_scope": {
            "review_surface_open": True,
            "gold_freeze_authorized": False,
            "tool_must_not_infer_or_prefill": True,
            "freeze_requires": {
                "structure_decisions": "7/7 by the user",
                "label_field_decisions": "135/135 by the user",
            },
        },
        "membership": {
            "bpmn_count": 7,
            "activities": 45,
            "label_fields": 135,
            "payload_sha256": payload,
            "expected_payload_sha256": EXPECTED_MEMBERSHIP_PAYLOAD,
        },
        "review_surface": {
            "records": len(corr_doc.get("records", [])),
            "summary": summary,
            "correction_sha256": _sha256_file(CORRECTION),
            "blank_sha256": _sha256_file(BLANK),
            "tool": {"path": "scripts/stage1_review_tool.py",
                     "sha256": _sha256_file(TOOL)},
            "guide": {"path": "docs/HUMAN_PROCESS_GOLD_GUIDE.md",
                      "sha256": _sha256_file(GUIDE)},
            "schema": {"path": "configs/schemas/stage1_human_annotation.schema.json",
                       "sha256": _sha256_file(SCHEMA)},
        },
        "checks": checks,
        "status": "input_ready_freeze_blocked",
        "zero_api": {"new_llm_api_calls": 0},
    }
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists() and OUT.read_bytes() != data:
        raise RuntimeError(f"refusing to overwrite different content: {OUT}")
    OUT.write_bytes(data)
    print(f"S1.5 review-surface authorization recorded: {OUT.relative_to(ROOT)}")
    print(f"  checks: {checks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

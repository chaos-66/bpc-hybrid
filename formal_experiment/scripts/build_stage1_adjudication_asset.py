# -*- coding: utf-8 -*-
"""Build the S1.5 human-adjudication evidence asset for ONE process
(generic, reusable across the seven BPMN batches).

The decision JSON is built from the USER's explicit adjudication only
(mechanical transcription by DeepSeek; no inference). For
`accepted_candidate` the `gold_process_record` is copied byte-semantically
from the membership-locked process records file (never regenerated).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    build_formal_process_records,
    canonical_sha256,
    load_formal_membership_contract,
)

MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
PROCESS_RECORDS = (ROOT / "data" / "development" / "human_review"
                   / "stage1_gdpr7_process_records_v1.json")
CORRECTION = (ROOT / "data" / "development" / "human_review"
              / "stage1_gdpr7_human_correction_v1.json")
AUTH_MANIFEST = (ROOT / "outputs" / "reports"
                 / "s1_5_review_surface_authorization_v1.manifest.json")
OUT_DIR = (ROOT / "outputs" / "development" / "human_review"
           / "stage1_adjudications")

EXPECTED_MEMBERSHIP_PAYLOAD = (
    "e88caf8157c4e6e5c2d789ed0f2b6bbac2aac2e89d2384db7762549751a1663d")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_records_doc() -> dict[str, Any]:
    return json.loads(PROCESS_RECORDS.read_text(encoding="utf-8"))


def build_asset(process_id: str, user_decision: dict[str, Any],
                adjudication_date: str) -> dict[str, Any]:
    """user_decision: {review_state, structure_annotation:{decision,
    gold_process_record|null}, label_annotations:[{activity_id, actor,
    action, business_object}]} with explicit status/value per field."""
    records_doc = _canonical_records_doc()
    candidate = next(r for r in records_doc["records"]
                     if r["process_id"] == process_id)
    candidate_sha = canonical_sha256(candidate)

    if user_decision["structure_annotation"]["decision"] == "accepted_candidate":
        # gold_process_record must be the locked candidate, byte-semantically
        gold = json.loads(json.dumps(candidate, ensure_ascii=False))
        user_decision["structure_annotation"]["gold_process_record"] = gold

    # build the exact correction record for this process
    record = {
        "process_id": process_id,
        "source": {"path": candidate["source"]["path"],
                   "sha256": candidate["source"]["sha256"],
                   "process_record_sha256": candidate_sha},
        "review_state": user_decision["review_state"],
        "structure_annotation": user_decision["structure_annotation"],
        "label_annotations": user_decision["label_annotations"],
    }
    asset = {
        "schema_version": "s1_5_human_adjudication_decision@1.0.0",
        "process_id": process_id,
        "adjudication_date": adjudication_date,
        "adjudicated_by": "user",
        "mechanical_transcription_by": "DeepSeek (no inference; explicit "
                                       "user decisions transcribed only)",
        "review_state": user_decision["review_state"],
        "structure_annotation": user_decision["structure_annotation"],
        "label_annotations": user_decision["label_annotations"],
        "evidence_hashes": {
            "candidate_process_record_sha256": candidate_sha,
            "bpmn_source_sha256": candidate["source"]["sha256"],
            "membership_payload_sha256": EXPECTED_MEMBERSHIP_PAYLOAD,
        },
        "safety": {
            "llm_api_calls": 0,
            "gold_freeze_authorized": False,
            "inferred_by_agent": False,
        },
    }
    return {"asset": asset, "record": record}


def write_asset(process_id: str, asset: dict[str, Any],
                record: dict[str, Any]) -> dict[str, Any]:
    before_sha = _sha256_file(CORRECTION)
    out = OUT_DIR / process_id
    out.mkdir(parents=True, exist_ok=True)
    decision_path = out / "decision_v1.json"
    decision_data = (json.dumps(asset, ensure_ascii=False, indent=2)
                     + "\n").encode("utf-8")
    if decision_path.exists() and decision_path.read_bytes() != decision_data:
        raise RuntimeError(f"refusing to overwrite different content: {decision_path}")
    decision_path.write_bytes(decision_data)
    decision_sha = hashlib.sha256(decision_data).hexdigest()

    manifest = {
        "schema_version": "s1_5_human_adjudication_manifest@1.0.0",
        "process_id": process_id,
        "adjudication_date": asset["adjudication_date"],
        "decision_asset": {"path": f"outputs/development/human_review/stage1_adjudications/{process_id}/decision_v1.json",
                           "sha256": decision_sha},
        "before_correction_sha256": before_sha,
        "after_correction_sha256": None,
        "candidate_process_record_sha256":
            asset["evidence_hashes"]["candidate_process_record_sha256"],
        "bpmn_source_sha256": asset["evidence_hashes"]["bpmn_source_sha256"],
        "membership_payload_sha256":
            asset["evidence_hashes"]["membership_payload_sha256"],
        "llm_api_calls": 0,
        "gold_freeze_authorized": False,
    }
    man_path = out / "manifest.json"
    man_data = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if man_path.exists() and man_path.read_bytes() != man_data:
        raise RuntimeError(f"refusing to overwrite different content: {man_path}")
    man_path.write_bytes(man_data)
    return manifest


def main() -> int:
    parser = __import__("argparse").ArgumentParser(description=__doc__)
    parser.add_argument("--decision-json", required=True)
    parser.add_argument("--date", default="2026-08-11")
    args = parser.parse_args()

    user_decision = json.loads(Path(args.decision_json).read_text(encoding="utf-8"))
    process_id = user_decision["process_id"]
    built = build_asset(process_id, user_decision, args.date)
    manifest = write_asset(process_id, built["asset"], built["record"])
    # emit the import JSON (record) for the review tool
    import_path = OUT_DIR / process_id / "import_record_v1.json"
    import_data = (json.dumps({"records": [built["record"]]}, ensure_ascii=False,
                              indent=2) + "\n").encode("utf-8")
    if import_path.exists() and import_path.read_bytes() != import_data:
        raise RuntimeError(f"refusing to overwrite different content: {import_path}")
    import_path.write_bytes(import_data)
    print(f"adjudication asset written: {OUT_DIR.relative_to(ROOT)}/{process_id}")
    print(f"  candidate sha256: {manifest['candidate_process_record_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

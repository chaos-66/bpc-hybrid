# -*- coding: utf-8 -*-
"""Verify the Stage 3 Gold annotation blank pack (S3.2 matching + S3.3 violation).

Checks (all offline, fail closed):
- pack identity: schema_version / dataset_id / claim boundary present
- processes match the frozen S3.1 membership contract exactly (same 7
  process_ids, same source paths)
- every matching_item and violation_item: unique item_id, known process_id,
  legal rule_id (article 5-50), legal review_state, non-empty candidates
- deterministic regeneration: rebuilding the pack from the same inputs
  reproduces the stored file byte-identically

No decision is read or inferred; no Gold is touched; no BPMN is modified.

Usage:
    python scripts/verify_stage3_gold_annotation.py
    python scripts/verify_stage3_gold_annotation.py --manifest-out <path>
"""

from __future__ import annotations

import argparse
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
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bpc_hybrid.stage1_formal_dataset import Stage1FormalDatasetError  # noqa: E402
from build_stage3_gold_annotation import (  # noqa: E402
    DEFAULT_OUTPUT,
    build_blank_pack,
)

PACK_PATH = DEFAULT_OUTPUT
MEMBERSHIP_CONTRACT = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"
DEFAULT_MANIFEST = ROOT / "outputs" / "reports" / "s32_s33_gold_annotation_blank_v1.manifest.json"

RULE_ID_PATTERN = re.compile(r"^article(5|6|7|8|9|1[0-9]|2[0-9]|3[0-9]|4[0-9]|50)$")
REVIEW_STATES = {"unreviewed", "reviewed", "adjudicated"}
VIOLATION_TYPES = {"missing_action", "incorrect_actor", "out_of_order", None}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage1FormalDatasetError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise Stage1FormalDatasetError(f"{label} root must be an object")
    return value


def verify_pack(pack: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []

    if pack.get("schema_version") != "stage3_gold_annotation@1.0.0":
        errors.append("schema_version mismatch")
    if pack.get("dataset_id") != "stage3_gold_annotation_v1":
        errors.append("dataset_id mismatch")
    if not pack.get("claim_boundary"):
        errors.append("claim_boundary missing")

    # processes must match the frozen S3.1 membership contract
    contract = _load_json(MEMBERSHIP_CONTRACT, "S3.1 membership contract")
    frozen_ids = [item["input_id"] for item in contract["membership"]["files"]]
    processes = pack.get("processes", [])
    pack_ids = [p.get("process_id") for p in processes]
    if pack_ids != frozen_ids:
        errors.append(f"process list differs from frozen S3.1 membership: {pack_ids}")

    # matching items
    m_items = pack.get("matching_items", [])
    seen_m: set[str] = set()
    for item in m_items:
        item_id = item.get("item_id")
        if not item_id or item_id in seen_m:
            errors.append(f"duplicate/missing matching item_id: {item_id}")
        seen_m.add(item_id)
        if item.get("process_id") not in frozen_ids:
            errors.append(f"matching item {item_id}: unknown process_id")
        rule_id = item.get("rule_id")
        if not rule_id or not RULE_ID_PATTERN.match(rule_id):
            errors.append(f"matching item {item_id}: illegal rule_id {rule_id}")
        if item.get("candidate_relevant") not in (True, False):
            errors.append(f"matching item {item_id}: candidate_relevant must be bool")
        if item.get("review_state") not in REVIEW_STATES:
            errors.append(f"matching item {item_id}: illegal review_state")
        if item.get("decision_relevant") is not None:
            errors.append(f"matching item {item_id}: inferred decision present")

    # violation items
    v_items = pack.get("violation_items", [])
    seen_v: set[str] = set()
    for item in v_items:
        item_id = item.get("item_id")
        if not item_id or item_id in seen_v:
            errors.append(f"duplicate/missing violation item_id: {item_id}")
        seen_v.add(item_id)
        if item.get("process_id") not in frozen_ids:
            errors.append(f"violation item {item_id}: unknown process_id")
        rule_id = item.get("rule_id")
        if not rule_id or not RULE_ID_PATTERN.match(rule_id):
            errors.append(f"violation item {item_id}: illegal rule_id {rule_id}")
        if item.get("candidate_violation_type") not in VIOLATION_TYPES:
            errors.append(f"violation item {item_id}: illegal candidate_violation_type")
        if not item.get("candidate_evidence"):
            errors.append(f"violation item {item_id}: candidate_evidence empty")
        if item.get("review_state") not in REVIEW_STATES:
            errors.append(f"violation item {item_id}: illegal review_state")
        if item.get("decision_violation_type") is not None or item.get("decision_evidence") is not None:
            errors.append(f"violation item {item_id}: inferred decision present")

    if errors:
        raise Stage1FormalDatasetError("Stage 3 gold blank pack invalid: " + "; ".join(errors[:8]))

    return {
        "process_count": len(processes),
        "matching_candidate_count": len(m_items),
        "violation_candidate_count": len(v_items),
        "all_unreviewed": all(i.get("review_state") == "unreviewed" for i in m_items + v_items),
        "no_decisions_inferred": all(
            i.get("decision_relevant") is None and i.get("decision_violation_type") is None
            for i in m_items + v_items
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    try:
        stored = _load_json(PACK_PATH, "Stage 3 gold blank pack")
        summary = verify_pack(stored)
        # deterministic regeneration check
        rebuilt = build_blank_pack()
        stored_payload = PACK_PATH.read_text(encoding="utf-8")
        rebuilt_payload = json.dumps(rebuilt, ensure_ascii=False, indent=2) + "\n"
        if stored_payload != rebuilt_payload:
            raise Stage1FormalDatasetError("stored pack is not byte-identical to a deterministic rebuild")
        manifest = {
            "schema_version": "stage3_gold_annotation_verification@1.0.0",
            "run_id": "s32_s33_gold_annotation_blank_v1",
            "task_ids": ["S3.2", "S3.3"],
            "status": "succeeded_blank_pack_ready_for_human_review",
            "dataset": {
                "dataset_id": stored["dataset_id"],
                "processes": summary["process_count"],
                "matching_candidates": summary["matching_candidate_count"],
                "violation_candidates": summary["violation_candidate_count"],
                "all_unreviewed": summary["all_unreviewed"],
                "no_decisions_inferred": summary["no_decisions_inferred"],
                "membership_contract": str(MEMBERSHIP_CONTRACT.relative_to(ROOT)),
            },
            "artifacts": {
                "blank_pack": {
                    "path": str(PACK_PATH.relative_to(ROOT).as_posix()),
                    "sha256": _sha256(PACK_PATH),
                    "byte_size": PACK_PATH.stat().st_size,
                }
            },
            "safety": {
                "human_gold_read_or_modified": False,
                "gold_auto_filled": False,
                "bpmn_modified": False,
                "llm_api_called": False,
                "network_called": False,
                "performance_evaluation": False,
                "no_overwrite": True,
            },
            "claim_boundary": stored["claim_boundary"],
        }
        output = args.manifest_out.resolve()
        if output.exists():
            raise Stage1FormalDatasetError(f"refusing to overwrite: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            "verified Stage 3 gold blank pack: "
            f"{summary['process_count']} processes, {summary['matching_candidate_count']} "
            f"matching, {summary['violation_candidate_count']} violation candidates; "
            "ready for human review"
        )
        return 0
    except Stage1FormalDatasetError as exc:
        print(f"Stage 3 gold blank pack verification failed closed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

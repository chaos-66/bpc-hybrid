# -*- coding: utf-8 -*-
"""Regression tests for the Stage 3 Gold annotation blank pack (S3.2/S3.3).

Covers: pack identity, frozen-S3.1 process alignment, candidate completeness
(matching relevant + negative pairs, violation types per relevant rule),
review-state discipline (all unreviewed, no inferred decisions), deterministic
rebuild, and fail-closed verification of a tampered pack.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    Stage1FormalDatasetError,
    load_formal_membership_contract,
)
from build_stage3_gold_annotation import (  # noqa: E402
    CANDIDATE_MATCHING,
    CANDIDATE_VIOLATIONS,
    DEFAULT_OUTPUT,
    build_blank_pack,
)
from verify_stage3_gold_annotation import verify_pack  # noqa: E402

MEMBERSHIP = ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json"


def _pack() -> dict:
    return json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))


def test_pack_identity_and_frozen_process_alignment() -> None:
    pack = _pack()
    assert pack["schema_version"] == "stage3_gold_annotation@1.0.0"
    assert pack["dataset_id"] == "stage3_gold_annotation_v1"
    contract = load_formal_membership_contract(MEMBERSHIP)
    frozen_ids = [item["input_id"] for item in contract["membership"]["files"]]
    assert [p["process_id"] for p in pack["processes"]] == frozen_ids
    assert all(p["source_path"].startswith("data/input/stage1_stage3/gdpr7/") for p in pack["processes"])
    assert all(p["activity_names"] for p in pack["processes"])


def test_matching_candidates_cover_relevant_and_negative_pairs() -> None:
    pack = _pack()
    by_process: dict[str, list[dict]] = {}
    for item in pack["matching_items"]:
        by_process.setdefault(item["process_id"], []).append(item)
    assert set(by_process) == set(CANDIDATE_MATCHING)
    for process_id, candidates in CANDIDATE_MATCHING.items():
        items = by_process[process_id]
        relevant = {i["rule_id"] for i in items if i["candidate_relevant"] is True}
        negative = {i["rule_id"] for i in items if i["candidate_relevant"] is False}
        assert relevant == set(candidates["relevant"]), process_id
        assert negative == set(candidates["negative"]), process_id
        # at least one relevant pair must name an existing activity as evidence
        activity_names = [
            p["activity_names"] for p in pack["processes"] if p["process_id"] == process_id
        ][0]
        for i in items:
            if i["candidate_relevant"] and i["evidence_activity"] is not None:
                assert i["evidence_activity"] in activity_names


def test_violation_candidates_one_of_each_type_per_relevant_rule() -> None:
    pack = _pack()
    by_key: dict[tuple[str, str], list[dict]] = {}
    for item in pack["violation_items"]:
        by_key.setdefault((item["process_id"], item["rule_id"]), []).append(item)
    for process_id, rules in CANDIDATE_VIOLATIONS.items():
        for rule_id, viols in rules.items():
            items = by_key[(process_id, rule_id)]
            assert {v["candidate_violation_type"] for v in items} == {v["type"] for v in viols}
            assert len(items) == len(viols)
            for item, viol in zip(items, viols):
                assert item["candidate_location"] == viol["location"]
                assert item["candidate_evidence"]


def test_all_items_unreviewed_and_no_decisions_inferred() -> None:
    pack = _pack()
    for item in pack["matching_items"] + pack["violation_items"]:
        assert item["review_state"] == "unreviewed"
        assert item.get("decision_relevant") is None
        assert item.get("decision_violation_type") is None
        assert item.get("decision_evidence") is None


def test_deterministic_rebuild_is_byte_identical() -> None:
    stored = DEFAULT_OUTPUT.read_text(encoding="utf-8")
    rebuilt = json.dumps(build_blank_pack(), ensure_ascii=False, indent=2) + "\n"
    assert stored == rebuilt


def test_verify_pack_rejects_tampered_process_list() -> None:
    pack = _pack()
    pack["processes"] = pack["processes"][:6]
    with pytest.raises(Stage1FormalDatasetError):
        verify_pack(pack)


def test_verify_pack_rejects_inferred_decision() -> None:
    pack = _pack()
    pack["matching_items"][0]["review_state"] = "adjudicated"
    pack["matching_items"][0]["decision_relevant"] = True
    with pytest.raises(Stage1FormalDatasetError):
        verify_pack(pack)


def test_builder_no_overwrite_and_manifest_verification() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_stage3_gold_annotation.py"), "--write"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 2, completed.stdout  # refusing to overwrite
    assert "refusing to overwrite" in completed.stdout
    manifest_path = ROOT / "outputs" / "reports" / "s32_s33_gold_annotation_blank_v1.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "succeeded_blank_pack_ready_for_human_review"
    assert manifest["dataset"]["matching_candidates"] == 25
    assert manifest["dataset"]["violation_candidates"] == 33
    assert manifest["dataset"]["all_unreviewed"] is True
    assert manifest["safety"]["bpmn_modified"] is False

"""Focused tests for the S2.11 Checkpoint C offline proposals and the
DRY-RUN batch accept/revise import tool (zero LLM/API, no raw third-party
text in committed assets, reviewer is never the user, no confirmation
event this round).

Covers:
  * committed proposal report: 36/36 coverage, confidence/issue counts,
    needs_attention ids, per-entry human_approved=false/gold=false/
    reviewer=null, zero API, no raw source fragments, deterministic
    regeneration, local proposal-file SHA-256 binding
  * batch dry-run: fail-closed invariants (membership closure, sample-set
    match, hash binding), would-be decisions (36 records, reviewed,
    reviewer=null, pending user confirmation), import-blocked stats,
    live decisions file untouched, --apply refusal without a confirmation
    event, revisions (valid reduce blocked fields; invalid revisions
    refused), no reviewer="user" anywhere
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

import review_s2_11_candidates as tool  # noqa: F401  (scripts on path)
import s2_11_batch_import_dry_run as batch
import s2_11_generate_proposals as proposals

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PROPOSAL_REPORT_REL = "outputs/reports/s2_11_proposal_report_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"

NEEDS_ATTENTION_IDS = {
    "SIM_card_scenario/r10/v1", "SIM_card_scenario/r11/v1",
    "blood_donation_scenario/r16/v1", "blood_donation_scenario/r17/v1",
    "blood_donation_scenario/r17/v2", "emergencies_scenario/r2/v1",
    "emergencies_scenario/r2/v2", "emergencies_scenario/r3/v1",
}


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _has_40_char_source_fragment(blob: str) -> bool:
    """True if any 40-char contiguous run of source text is in blob."""
    membership = _load(MEMBERSHIP_REL)
    for record_id, rec in membership["records"].items():
        doc = json.loads(
            (ROOT.parent / rec["path"]).read_bytes().decode("utf-8"))
        scenario, rid, version = record_id.split("/")
        for entry in doc:
            if str(entry.get("ID")) == rid and \
                    str(entry.get("version")) == version.lstrip("v"):
                text = entry["text"]
                for i in range(len(text) - 39):
                    if text[i:i + 40] in blob:
                        return True
                break
    return False


# ---------------------------------------------------------------------------
# Proposal report
# ---------------------------------------------------------------------------
def test_proposal_report_coverage_and_flags() -> None:
    report = _load(PROPOSAL_REPORT_REL)
    membership = _load(MEMBERSHIP_REL)
    assert report["schema_version"] == "s2_11_proposal_report@1.0.0"
    assert report["coverage"] == "36/36"
    assert report["proposal_count"] == 36
    assert report["proposal_source"] == "deepseek_offline_proposal"
    assert set(report["entries"]) == set(membership["records"])
    assert report["confidence_counts"] == {"high": 13, "low": 4,
                                           "medium": 19}
    assert report["issue_counts"] == {"needs_attention": 8, "none": 28}
    assert set(report["needs_attention_ids"]) == NEEDS_ATTENTION_IDS
    for entry in report["entries"].values():
        assert entry["human_approved"] is False
        assert entry["gold"] is False
        assert entry["reviewer"] is None
        assert entry["proposal_source"] == "deepseek_offline_proposal"
        assert len(entry["text_sha256"]) == 64
        assert len(entry["file_sha256"]) == 64
        assert set(entry["fields"]) == {"modality", "actor", "action",
                                        "condition", "constraint",
                                        "exception"}
    assert report["raw_text_committed"] is False
    assert report["human_approved"] is False
    assert report["gold_created"] is False
    assert report["zero_api"] == {"new_llm_api_calls": 0}


def test_proposal_report_has_no_raw_source_fragments() -> None:
    report = _load(PROPOSAL_REPORT_REL)
    blob = json.dumps(report, ensure_ascii=False)
    assert not _has_40_char_source_fragment(blob)


def test_proposal_report_binds_local_proposal_file() -> None:
    report = _load(PROPOSAL_REPORT_REL)
    local = ROOT / report["proposal_file"]
    assert local.is_file()
    assert _sha(local.read_bytes()) == report["proposal_file_sha256"]
    lines = [ln for ln in local.read_text(encoding="utf-8").splitlines()
             if ln]
    assert len(lines) == 36


def test_proposal_report_deterministic_regeneration() -> None:
    on_disk = _load(PROPOSAL_REPORT_REL)
    regenerated = proposals.generate()
    assert regenerated == on_disk


# ---------------------------------------------------------------------------
# Batch import dry-run
# ---------------------------------------------------------------------------
@pytest.fixture()
def batch_tmp(tmp_path: Path):
    """Point the batch tool's writable outputs at a tmp tree while keeping
    ROOT (and the references sources) real."""
    old_local = batch.LOCAL_DIR
    old_report = batch.DRY_RUN_REPORT_REL
    batch.LOCAL_DIR = tmp_path / "local"
    batch.DRY_RUN_REPORT_REL = tmp_path / "dry_run_report_v1.json"
    yield tmp_path
    batch.LOCAL_DIR = old_local
    batch.DRY_RUN_REPORT_REL = old_report


def test_batch_dry_run_accept_all_invariants(batch_tmp: Path) -> None:
    before = _sha((ROOT / DECISIONS_REL).read_bytes())
    report = batch.run_dry_run(None)
    assert report["schema_version"] == \
        "s2_11_batch_import_dry_run@1.0.0"
    assert report["proposal_report_sha256"] == \
        _sha((ROOT / PROPOSAL_REPORT_REL).read_bytes())
    assert report["population"] == {
        "inventory": 40, "objective_exclusions": 4,
        "nonempty_membership": 36, "review_population": 36,
        "closure_invariant": (
            "review_population == nonempty_membership == "
            "inventory - objective_exclusions"),
    }
    assert report["batch_import_mode"] == "accept_all_with_listed_revisions"
    assert report["revisions_file"] is None
    assert report["revisions_file_sha256"] is None
    assert report["import_stats"]["samples"] == 36
    assert report["import_stats"]["import_blocked_fields"] == 10
    assert report["import_stats"]["import_blocked_samples"] == 7
    assert set(report["recommended_for_user_revision"]) == \
        NEEDS_ATTENTION_IDS
    assert report["fail_closed"] == {
        "confirmation_event_present": False,
        "applied": False,
        "wrote_decisions": False,
        "reviewer_never_user": True,
        "gold_created": False,
        "human_approved": False,
    }
    assert report["zero_api"] == {"new_llm_api_calls": 0}
    # would-be decisions file exists locally, hash matches, state reviewed
    would_be_path = batch.ROOT / report["would_be_decisions_file"]
    assert would_be_path.is_file()
    assert _sha(would_be_path.read_bytes()) == \
        report["would_be_decisions_sha256"]
    would_be = json.loads(would_be_path.read_text(encoding="utf-8"))
    assert would_be["schema_version"] == \
        "s2_11_review_decisions_dry_run@1.0.0"
    assert would_be["applied"] is False
    assert would_be["adjudication_pending_user_confirmation"] is True
    assert len(would_be["records"]) == 36
    for entry in would_be["records"].values():
        assert entry["review_state"] == "reviewed"
        assert entry["reviewer"] is None
    # the LIVE decisions file is untouched
    assert _sha((ROOT / DECISIONS_REL).read_bytes()) == before


def test_batch_dry_run_deterministic(batch_tmp: Path) -> None:
    first = json.dumps(batch.run_dry_run(None), sort_keys=True,
                       ensure_ascii=False)
    second = json.dumps(batch.run_dry_run(None), sort_keys=True,
                        ensure_ascii=False)
    assert first == second


def test_batch_dry_run_revisions_reduce_blocked_fields(
        batch_tmp: Path) -> None:
    revisions = {
        "emergencies_scenario/r2/v1": {
            "modality": "obligation",
            "actor": "the nurse",
            "action": "obtain the patient\u2019s consent",
        },
    }
    rev_path = batch_tmp / "revisions.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    report = batch.run_dry_run(rev_path)
    assert report["revisions_file_sha256"] == _sha(rev_path.read_bytes())
    assert report["import_stats"]["import_blocked_fields"] == 9
    would_be = json.loads(
        (batch.ROOT / report["would_be_decisions_file"])
        .read_text(encoding="utf-8"))
    decision = would_be["records"]["emergencies_scenario/r2/v1"]["decision"]
    assert decision["modality"] == "obligation"
    assert decision["actor"] == "the nurse"
    assert decision["action"] == "obtain the patient\u2019s consent"


def test_batch_dry_run_invalid_revision_refused(batch_tmp: Path) -> None:
    revisions = {
        "emergencies_scenario/r2/v1": {"actor": "not an exact substring"},
    }
    rev_path = batch_tmp / "bad_revisions.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    with pytest.raises(batch.ImportFail, match="not an exact substring"):
        batch.run_dry_run(rev_path)


def test_batch_dry_run_unknown_sample_revision_refused(
        batch_tmp: Path) -> None:
    revisions = {"not/a/real/sample": {"modality": "obligation"}}
    rev_path = batch_tmp / "unknown_revisions.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    with pytest.raises(batch.ImportFail, match="unknown sample"):
        batch.run_dry_run(rev_path)


def test_batch_apply_refused_without_confirmation_event() -> None:
    with pytest.raises(batch.ImportFail, match="no user confirmation"):
        batch.run_apply()
    # and the live decisions file must remain untouched
    decisions = _load(DECISIONS_REL)
    assert all(e["review_state"] == "unreviewed"
               for e in decisions["records"].values())


def test_batch_dry_run_never_writes_reviewer_user(batch_tmp: Path) -> None:
    report = batch.run_dry_run(None)
    blob = json.dumps(report, ensure_ascii=False)
    assert '"reviewer": "user"' not in blob
    assert "reviewer_never_user" in blob
    would_be = json.loads(
        (batch.ROOT / report["would_be_decisions_file"])
        .read_text(encoding="utf-8"))
    wb_blob = json.dumps(would_be, ensure_ascii=False)
    assert '"reviewer": "user"' not in wb_blob


def test_batch_dry_run_report_has_no_raw_source_fragments(
        batch_tmp: Path) -> None:
    report = batch.run_dry_run(None)
    blob = json.dumps(report, ensure_ascii=False)
    assert not _has_40_char_source_fragment(blob)

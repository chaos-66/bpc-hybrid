"""Focused tests for the S2.11 Checkpoint B corpus activation (local
read-only, zero LLM/API, no raw third-party text in committed assets).

Covers:
  * membership manifest: hash-only, 40 records, 4 inventory-quarantined,
    files match disk, no raw text
  * deterministic modality extraction (keyword rules with spans)
  * deterministic G0.5 feature extraction
  * candidate run: deterministic double-run, counts, modality/level
    distributions, quarantine codes, NO raw text in the committed report
  * G5 blank review surface: 29 samples, all decisions null,
    unreviewed, candidate/Gold separation, no raw text
  * review tool plumbing: verify, show (hash-verified text), set/undo/
    state/backup on a tmp copy, progress
  * review freeze validator: valid structure, frozen=false, remaining 29
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.s2_11_corpus_ingestion import (  # type: ignore[attr-defined]
    extract_modality,
    g05_features,
)

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
CANDIDATE_RUN_REL = "outputs/reports/s2_11_candidate_run_v1.json"
BLANK_REVIEW_REL = "data/development/human_review/s2_11_blank_review_v1.json"
DECISIONS_REL = "data/development/human_review/s2_11_review_decisions_v1.json"
USER_AUTH_REL = "configs/s2_11_user_authorization_event_v1.json"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# Membership
# ---------------------------------------------------------------------------
def test_membership_hash_only_and_matches_disk() -> None:
    membership = _load(MEMBERSHIP_REL)
    assert membership["record_count"] == 40
    assert len(membership["records"]) == 36  # 4 inventory-quarantined
    assert len(membership["quarantine"]) == 4
    assert all(q["code"] == "QUARANTINE_EMPTY_TEXT"
               for q in membership["quarantine"])
    for f in membership["files"]:
        p = ROOT.parent / f["path"]
        assert p.is_file()
        assert _sha(p.read_bytes()) == f["sha256"]
        assert p.stat().st_size == f["byte_size"]
    # no raw text anywhere in the membership
    blob = json.dumps(membership, ensure_ascii=False)
    for fragment in ("donor", "SIM card", "anesthesia", "consent"):
        assert fragment not in blob


def test_membership_records_have_text_hashes() -> None:
    membership = _load(MEMBERSHIP_REL)
    for record_id, rec in membership["records"].items():
        assert len(rec["text_sha256"]) == 64
        assert rec["text_byte_size"] > 0
        assert rec["path"].startswith("references/barrientos_2026/")


# ---------------------------------------------------------------------------
# Modality extraction
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("text,cls", [
    ("the nurse must obtain consent", "obligation"),
    ("the patient may refuse", "permission"),
    ("the company is prohibited from collecting", "prohibition"),
    ("the phone company can take longer", "permission"),
    ("customers are not eligible to receive", "prohibition"),
    ("information needs to be provided", "obligation"),
    ("blood has to be analyzed", "obligation"),
    ("the hospital must not collect", "prohibition"),
    ("the process is not obligated to ask", "prohibition"),
])
def test_extract_modality_rules(text: str, cls: str) -> None:
    result = extract_modality(text)
    assert result is not None
    cls_, start, end = result
    assert cls_ == cls
    assert 0 <= start < end <= len(text)
    assert text[start:end].strip()


def test_extract_modality_none_when_no_keyword() -> None:
    assert extract_modality("the donor is monitored") is None
    assert extract_modality("assess the donor") is None


def test_extract_modality_must_not_beats_must() -> None:
    cls_, start, end = extract_modality("the hospital must not collect")
    assert cls_ == "prohibition"
    assert "must not" == "the hospital must not collect"[start:end]


def test_g05_features_deterministic_and_documented() -> None:
    f1 = g05_features("If the patient is over 65, a nurse must approve "
                      "discharge before the patient is discharged.")
    f2 = g05_features("If the patient is over 65, a nurse must approve "
                      "discharge before the patient is discharged.")
    assert f1 == f2
    assert f1["condition_count"] == 1
    assert f1["constraint_count"] == 1
    assert f1["language_markers"] == "original"
    assert f1["dependency_depth"] == 1
    assert f1["bpmn_activities"] == 0


# ---------------------------------------------------------------------------
# Candidate run
# ---------------------------------------------------------------------------
def test_candidate_run_counts_and_distributions() -> None:
    run = _load(CANDIDATE_RUN_REL)
    assert run["counts"]["membership_records"] == 40
    assert run["counts"]["candidates"] == 29
    assert run["counts"]["total_quarantined"] == 11
    assert sum(run["modality_distribution"].values()) == 29
    assert sum(run["g0_5_level_distribution"].values()) == 29
    assert run["review_workload"] == 29
    assert run["provenance_complete"] == run["provenance_total"] == 29
    assert run["raw_text_committed"] is False
    assert run["zero_api"]["new_llm_api_calls"] == 0
    assert run["gold_created"] is False
    # every candidate level is a frozen-classified level
    assert set(run["g0_5_level_distribution"]) <= {"L1", "L2", "L3"}


def test_candidate_run_quarantine_has_stable_codes() -> None:
    run = _load(CANDIDATE_RUN_REL)
    codes = {q["code"] for q in run["quarantine"]}
    assert codes <= {"QUARANTINE_MODALITY_UNKNOWN",
                     "FIELD_SPAN_AMBIGUOUS"}
    for q in run["quarantine"]:
        assert q["record_id"].count("/") == 2
        assert len(q.get("file_sha256", "00" * 64)) == 64


def test_candidate_run_contains_no_raw_third_party_text() -> None:
    blob = json.dumps(_load(CANDIDATE_RUN_REL), ensure_ascii=False)
    for fragment in ("donor", "SIM card", "anesthesia", "consent",
                     "blood sample", "time out"):
        assert fragment not in blob, f"raw text leaked: {fragment}"


def test_candidate_run_deterministic_double_run() -> None:
    import importlib.util
    import sys as _sys
    spec = importlib.util.spec_from_file_location(
        "s2_11_run_candidates_mod",
        ROOT / "scripts" / "s2_11_run_candidates.py")
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[spec.name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    first = json.dumps(mod.run_candidates(), sort_keys=True,
                       ensure_ascii=False)
    second = json.dumps(mod.run_candidates(), sort_keys=True,
                        ensure_ascii=False)
    assert first == second
    # the committed report matches the deterministic run
    on_disk = json.dumps(_load(CANDIDATE_RUN_REL), sort_keys=True,
                         ensure_ascii=False)
    assert second == on_disk


# ---------------------------------------------------------------------------
# G5 blank review surface
# ---------------------------------------------------------------------------
def test_blank_review_surface_all_null_and_separated() -> None:
    pack = _load(BLANK_REVIEW_REL)
    run = _load(CANDIDATE_RUN_REL)
    assert pack["sample_count"] == 29
    assert set(pack["decision_fields"]) == {
        "modality", "actor", "action", "condition", "constraint",
        "exception"}
    sample_ids = [s["sample_id"] for s in pack["samples"]]
    assert set(sample_ids) == set(run["candidates"])
    for sample in pack["samples"]:
        assert sample["review_state"] == "unreviewed"
        assert sample["reviewer"] is None
        assert all(v is None for v in sample["decision"].values())
        assert len(sample["text_sha256"]) == 64
        assert len(sample["candidate_hash"]) == 64
        assert sample["source_path"].startswith(
            "references/barrientos_2026/")
    assert pack["final_adjudication_by"] == "user_only"
    assert pack["gold_files_created"] is False
    assert pack["raw_text_committed"] is False
    blob = json.dumps(pack, ensure_ascii=False)
    for fragment in ("donor", "SIM card", "anesthesia", "consent"):
        assert fragment not in blob


def test_review_decisions_file_all_unreviewed() -> None:
    decisions = _load(DECISIONS_REL)
    assert len(decisions["records"]) == 29
    for entry in decisions["records"].values():
        assert entry["review_state"] == "unreviewed"
        assert entry["reviewer"] is None
        assert all(v is None for v in entry["decision"].values())


# ---------------------------------------------------------------------------
# Review tool plumbing (tmp copies; never touches the live decisions file)
# ---------------------------------------------------------------------------
@pytest.fixture()
def tmp_decisions(tmp_path: Path):
    import review_s2_11_candidates as tool
    tmp_root = tmp_path / "formal_experiment"
    tmp_root.mkdir()
    target = tmp_root / DECISIONS_REL
    target.parent.mkdir(parents=True)
    shutil.copy2(ROOT / DECISIONS_REL, target)
    old_root = tool.ROOT
    tool.ROOT = tmp_root
    yield tool
    tool.ROOT = old_root


def test_review_verify_ok_on_live_file() -> None:
    import review_s2_11_candidates as tool
    doc = tool.load_decisions()
    assert tool.verify_decisions(doc) == []


def test_review_show_loads_hash_verified_text() -> None:
    import review_s2_11_candidates as tool
    membership = _load(MEMBERSHIP_REL)
    sample_id = sorted(membership["records"])[0]
    text, sha = tool.load_source_text(sample_id)
    assert sha == membership["records"][sample_id]["text_sha256"]
    assert _sha(text.encode("utf-8")) == sha
    assert len(text) > 0


def test_review_set_undo_and_backup_on_tmp_copy(tmp_decisions: Any) -> None:
    tool = tmp_decisions
    doc = tool.load_decisions()
    sample_id = sorted(doc["records"])[0]
    tool.write_decisions(doc)  # baseline backup path
    doc["records"][sample_id]["decision"]["modality"] = "obligation"
    doc["records"][sample_id]["review_state"] = "reviewed"
    tool.write_decisions(doc)
    reloaded = tool.load_decisions()
    assert reloaded["records"][sample_id]["decision"]["modality"] == \
        "obligation"
    assert reloaded["records"][sample_id]["review_state"] == "reviewed"
    # undo
    reloaded["records"][sample_id]["decision"]["modality"] = None
    tool.write_decisions(reloaded)
    again = tool.load_decisions()
    assert again["records"][sample_id]["decision"]["modality"] is None
    # backup file exists (created by write_decisions)
    assert (tool.ROOT / (DECISIONS_REL + ".bak")).is_file()


def test_review_progress_and_freeze_validator() -> None:
    import review_s2_11_candidates as tool
    import verify_s2_11_review_freeze as freeze
    doc = tool.load_decisions()
    counts = tool.progress(doc)
    assert counts == {"unreviewed": 29, "reviewed": 0, "adjudicated": 0}
    result = freeze.verify()
    assert result["verified"] is True
    assert result["frozen"] is False
    assert result["remaining_for_user"] == 29
    assert result["gold_rule_records_created"] is False
    assert result["gold_creation_requires_user_authorization"] is True


def test_freeze_validator_detects_adjudicated_with_null_fields(
        tmp_path: Path) -> None:
    import verify_s2_11_review_freeze as freeze
    doc = _load(DECISIONS_REL)
    first = sorted(doc["records"])[0]
    doc["records"][first]["review_state"] = "adjudicated"
    doc["records"][first]["reviewer"] = "user"
    target = tmp_path / DECISIONS_REL
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    old = freeze.ROOT
    freeze.ROOT = tmp_path
    try:
        result = freeze.verify()
        assert result["verified"] is False
        assert any(first in p for p in result["problems"])
    finally:
        freeze.ROOT = old


# ---------------------------------------------------------------------------
# Activation context
# ---------------------------------------------------------------------------
def test_user_authorization_event_present_and_committed() -> None:
    doc = _load(USER_AUTH_REL)
    assert doc["kind"] == "user_authorization"
    assert doc["authorization_scope"] == \
        "local_read_only_nonredistributive_s2_11"
    assert doc["append_only"] is True


def test_candidate_run_binds_user_authorization() -> None:
    run = _load(CANDIDATE_RUN_REL)
    doc = _load(USER_AUTH_REL)
    assert run["user_authorization_event"] == USER_AUTH_REL
    assert run["user_authorization_event_sha256"] == \
        _sha((ROOT / USER_AUTH_REL).read_bytes())
    assert run["user_authorization_event_sha256"] == \
        run["user_authorization_event_sha256"]
    assert doc["event_id"] == "s2-11-user-auth-2026-08-17-v1"

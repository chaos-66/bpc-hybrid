"""Focused tests for S2.11 canonical proposal v2 + importer v2 (Checkpoint
E1/E2; zero LLM/API).

E1 acceptance (test-forced):
  * review population 36/36; proposal coverage 36/36
  * present ordinary span exact-slice failures = 0 (byte-verified)
  * modality evidence missing = 0; value_missing_in_text = 0
  * present fields displayed as None = 0 (package rendered from LOCAL full
    entries)
  * multi-value field structures legal; duplicate/missing/extra sample = 0
  * source/file/text hash drift refuses; v1 preserved byte-exact and
    declared superseded

E2 acceptance:
  * dry-run accept-all: blocked fields = 0, blocked samples = 0,
    unresolved = 0, adjudicable = 36/36, applied=false, wrote_decisions=
    false, reviewer never the user
  * accept-all-with-revisions; multi-span; absent; invalid revisions
    refuse; wrong proposal SHA refuses; missing confirmation event
    refuses; reviewer only from the event; atomic write + backup; illegal
    apply modifies nothing
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.s2_11_canonical_v2 import (
    CanonicalFail,
    MODALITY_LABELS,
    ORDINARY_FIELDS,
    validate,
    validate_record,
)
import s2_11_batch_import_v2 as batch
import s2_11_build_proposals_v2 as builder
import verify_s2_11_review_freeze_v2 as freeze_v2

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PROPOSAL_REPORT_V2_REL = "outputs/reports/s2_11_proposal_report_v2.json"
PROPOSAL_REPORT_V1_REL = "outputs/reports/s2_11_proposal_report_v1.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
BLANK_REVIEW_V2_REL = "data/development/human_review/s2_11_blank_review_v2.json"
V1_PROPOSAL_SHA256 = \
    "14c1ec909b2c5aa2249d2acfac1f3e411ff00a3c967a3d6b2ed06ddba8c7364b"

V2_PACKAGE_REL = ("outputs/development/s2_11_local_working/"
                  "adjudication_proposals_v2")
V2_PROPOSALS_LOCAL = V2_PACKAGE_REL + "/proposals.jsonl"
V2_PACKAGE_MD = V2_PACKAGE_REL + "/decision_package.md"
V2_DIFF_MD = V2_PACKAGE_REL + "/v1_to_v2_semantic_diff.md"
V2_QUALITY_MD = V2_PACKAGE_REL + "/quality_report.md"

EXPECTED_NEEDS_ATTENTION = {
    "SIM_card_scenario/r10/v1", "SIM_card_scenario/r10/v2",
    "SIM_card_scenario/r11/v1", "blood_donation_scenario/r16/v1",
    "blood_donation_scenario/r17/v1", "blood_donation_scenario/r17/v2",
    "blood_donation_scenario/r18/v2", "blood_donation_scenario/r19/v1",
    "blood_donation_scenario/r19/v2", "emergencies_scenario/r1/v1",
    "emergencies_scenario/r3/v1", "emergencies_scenario/r4/v2",
    "emergencies_scenario/r5/v1", "emergencies_scenario/r7/v2",
}


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _source_texts() -> dict[str, str]:
    membership = _load(MEMBERSHIP_REL)
    texts = {}
    for rid, rec in membership["records"].items():
        doc = json.loads(
            (ROOT.parent / rec["path"]).read_bytes().decode("utf-8"))
        sc, rid2, ver = rid.split("/")
        for en in doc:
            if str(en.get("ID")) == rid2 and \
                    str(en.get("version")) == ver.lstrip("v"):
                texts[rid] = en["text"]
    return texts


def _local_entries() -> dict[str, Any]:
    lines = [ln for ln in
             (ROOT / V2_PROPOSALS_LOCAL).read_text(encoding="utf-8")
             .splitlines() if ln]
    return {json.loads(ln)["sample_id"]: json.loads(ln) for ln in lines}


def _has_40_char_corpus_fragment(blob: str) -> bool:
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
# E1: proposal v2 report
# ---------------------------------------------------------------------------
def test_proposal_v2_report_coverage_and_flags() -> None:
    report = _load(PROPOSAL_REPORT_V2_REL)
    membership = _load(MEMBERSHIP_REL)
    assert report["schema_version"] == "s2_11_proposal_report@2.0.0"
    assert report["coverage"] == "36/36"
    assert report["proposal_count"] == 36
    assert set(report["entries"]) == set(membership["records"])
    assert report["confidence_counts"] == {"high": 23, "medium": 9,
                                           "low": 4}
    assert set(report["needs_attention_ids"]) == EXPECTED_NEEDS_ATTENTION
    assert report["supersedes_v1"]["status"] == \
        "superseded_proposal_provenance_do_not_approve"
    assert report["supersedes_v1"]["proposal_file_sha256"] == \
        V1_PROPOSAL_SHA256
    assert report["human_approved"] is False
    assert report["gold_created"] is False
    assert report["zero_api"] == {"new_llm_api_calls": 0}
    assert report["raw_text_committed"] is False
    for entry in report["entries"].values():
        assert entry["human_approved"] is False
        assert entry["gold"] is False
        assert entry["reviewer"] is None
        # committed entries carry coordinates only - no span text
        for clause in entry["canonical"]["clauses"]:
            assert "text" not in clause["clause_span"]
            assert all("text" not in ev for ev in
                       clause["modality"]["evidence"])
            for field in ORDINARY_FIELDS:
                assert all("text" not in s for s in
                           clause[field]["spans"])


def test_proposal_v2_binds_local_file_sha() -> None:
    report = _load(PROPOSAL_REPORT_V2_REL)
    local = ROOT / report["proposal_file"]
    assert local.is_file()
    assert _sha(local.read_bytes()) == report["proposal_file_sha256"]
    lines = [ln for ln in local.read_text(encoding="utf-8").splitlines()
             if ln]
    assert len(lines) == 36


def test_proposal_v2_has_no_value_missing_in_text() -> None:
    blob = json.dumps(_load(PROPOSAL_REPORT_V2_REL), ensure_ascii=False)
    assert "value_missing_in_text" not in blob
    for entry in _local_entries().values():
        assert "value_missing_in_text" not in json.dumps(entry)


def test_proposal_v2_no_raw_corpus_fragments_committed() -> None:
    blob = json.dumps(_load(PROPOSAL_REPORT_V2_REL), ensure_ascii=False)
    assert not _has_40_char_corpus_fragment(blob)


def test_proposal_v2_canonical_valid_and_zero_evidence_missing() -> None:
    entries = _local_entries()
    texts = _source_texts()
    payloads = {sid: {"canonical": e["canonical"]} for sid, e in
                entries.items()}
    result = validate(payloads, texts, allow_unresolved=True,
                      expected_ids=sorted(texts))
    assert result["valid"] is True, "; ".join(result["problems"][:10])
    # modality evidence present on every clause; no unresolved anywhere
    for sid, e in entries.items():
        for clause in e["canonical"]["clauses"]:
            mod = clause["modality"]
            assert mod["status"] == "present"
            assert mod["label"] in MODALITY_LABELS
            assert len(mod["evidence"]) >= 1
            for field in ORDINARY_FIELDS:
                assert clause[field]["status"] in ("present", "absent")
                if clause[field]["status"] == "present":
                    assert len(clause[field]["spans"]) >= 1


def test_proposal_v2_multi_value_structures_legal() -> None:
    entries = _local_entries()
    multi = 0
    for e in entries.values():
        for clause in e["canonical"]["clauses"]:
            for field in ORDINARY_FIELDS:
                if len(clause[field]["spans"]) > 1:
                    multi += 1
    assert multi >= 3  # e.g. r17v1 actions, r3v1 constraints, r16v1
    # r2v1/r2v2 have two clauses each with an order relation
    r2v1 = entries["emergencies_scenario/r2/v1"]["canonical"]
    assert len(r2v1["clauses"]) == 2
    assert len(r2v1["order_relations"]) == 1
    assert len(r2v1["actor_action_map"]) == 2
    r17v1 = entries["blood_donation_scenario/r17/v1"]["canonical"]
    assert len(r17v1["clauses"][0]["action"]["spans"]) == 2
    assert len(r17v1["order_relations"]) == 1


def test_proposal_v2_absent_fields_are_explicit() -> None:
    entries = _local_entries()
    absent_actors = [sid for sid, e in entries.items()
                     if e["canonical"]["clauses"][0]["actor"]["status"]
                     == "absent"]
    # passive clauses with no stated executor keep actor absent
    assert "SIM_card_scenario/r12/v1" in absent_actors
    assert "blood_donation_scenario/r18/v2" in absent_actors
    assert "emergencies_scenario/r1/v1" in absent_actors


def test_decision_package_renders_values_not_none() -> None:
    import re
    md = (ROOT / V2_PACKAGE_MD).read_text(encoding="utf-8")
    assert len(re.findall(r"^## ", md, flags=re.M)) == 36
    assert "`None`" not in md
    assert "**UNRESOLVED**" not in md  # no unresolved field lines
    assert "**ABSENT**" in md
    # present values are shown with their actual span text
    assert "obtain the patient\u2019s consent" in md
    assert "be immediately sent the reason for rejection" in md


def test_v1_to_v2_diff_and_quality_report_exist() -> None:
    diff = (ROOT / V2_DIFF_MD).read_text(encoding="utf-8")
    assert "value_missing_in_text" in diff
    assert V1_PROPOSAL_SHA256 in diff
    quality = (ROOT / V2_QUALITY_MD).read_text(encoding="utf-8")
    assert "exact-slice failures (text == source[start:end]): 0" in quality
    assert "modality evidence missing: 0" in quality
    assert "coverage: 36/36" in quality


def test_v1_files_preserved_byte_exact() -> None:
    # v1 local proposals are untouched (still the recorded SHA)
    v1_local = ROOT / "outputs" / "development" / "s2_11_local_working" / \
        "adjudication_proposals_v1" / "proposals.jsonl"
    assert _sha(v1_local.read_bytes()) == V1_PROPOSAL_SHA256
    # committed v1 report is byte-identical to HEAD
    repo = ROOT.parent
    rel = "formal_experiment/outputs/reports/s2_11_proposal_report_v1.json"
    proc = subprocess.run(["git", "-C", str(repo), "hash-object", rel],
                          cwd=repo, capture_output=True, text=True,
                          check=True)
    proc2 = subprocess.run(["git", "-C", str(repo), "rev-parse",
                            f"HEAD:{rel}"], cwd=repo, capture_output=True,
                           text=True, check=True)
    assert proc.stdout.strip() == proc2.stdout.strip()


def test_proposal_v2_builder_deterministic() -> None:
    first = json.dumps(builder.build()[0], sort_keys=True,
                       ensure_ascii=False)
    second = json.dumps(builder.build()[0], sort_keys=True,
                        ensure_ascii=False)
    assert first == second


def test_canonical_validator_refuses_bad_slice() -> None:
    entry = _local_entries()["SIM_card_scenario/r10/v1"]["canonical"]
    import copy
    tampered = copy.deepcopy(entry)
    span = tampered["clauses"][0]["action"]["spans"][0]
    span["start"] = span["start"] + 1  # now the slice is wrong
    problems = validate_record({"canonical": tampered},
                               _source_texts()["SIM_card_scenario/r10/v1"],
                               allow_unresolved=True)
    assert any("slice mismatch" in p for p in problems)


def test_canonical_validator_refuses_bad_refs() -> None:
    entry = _local_entries()["SIM_card_scenario/r10/v1"]["canonical"]
    import copy
    tampered = copy.deepcopy(entry)
    tampered["order_relations"] = [
        {"before_span_id": "no_such_id", "after_span_id": "also_missing"}]
    problems = validate_record({"canonical": tampered},
                               _source_texts()["SIM_card_scenario/r10/v1"],
                               allow_unresolved=True)
    assert any("bad before ref" in p for p in problems)
    assert any("bad after ref" in p for p in problems)


# ---------------------------------------------------------------------------
# E1: blank pack v2 + decisions v2 + freeze validator v2
# ---------------------------------------------------------------------------
def test_blank_pack_v2_all_unresolved() -> None:
    pack = _load(BLANK_REVIEW_V2_REL)
    decisions = _load(DECISIONS_V2_REL)
    assert pack["sample_count"] == 36
    assert pack["population"]["review_population"] == 36
    assert pack["population"]["candidate_available"] == 29
    assert pack["population"]["candidate_unavailable"] == 7
    assert len(decisions["records"]) == 36
    assert set(decisions["records"]) == set(pack["samples"] and
                                            [s["sample_id"] for s in
                                             pack["samples"]])
    # The blank pack template is the all-unresolved PRE-ADJUDICATION shape;
    # the live decisions file was adjudicated by the v3 apply (Checkpoint G).
    for sample in pack["samples"]:
        assert sample["review_metadata"]["review_state"] == "unreviewed"
        for clause in sample["canonical"]["clauses"]:
            assert clause["modality"]["status"] == "unresolved"

def test_decisions_v2_adjudicated_by_v3_apply() -> None:
    decisions = _load(DECISIONS_V2_REL)
    assert decisions["applied"] is True
    assert decisions["adjudication_pending_user_confirmation"] is False
    event = _load(
        "configs/s2_11_batch_import_confirmation_event_v3.json")
    for sid, entry in decisions["records"].items():
        assert entry["review_metadata"]["review_state"] == "adjudicated"
        assert entry["review_metadata"]["reviewer"] == event["reviewer"]
        for clause in entry["canonical"]["clauses"]:
            assert clause["modality"]["status"] in ("present", "absent")


def test_freeze_validator_v2_current_state() -> None:
    result = freeze_v2.verify()
    assert result["verified"] is True
    assert result["frozen"] is True
    assert result["progress"] == {"unreviewed": 0, "reviewed": 0,
                                  "adjudicated": 36}
    assert result["remaining_for_user"] == 0
    assert result["gold_rule_records_created"] is False


def test_freeze_validator_v2_refuses_adjudicated_with_unresolved(
        tmp_path: Path) -> None:
    doc = _load(DECISIONS_V2_REL)
    first = sorted(doc["records"])[0]
    doc["records"][first]["canonical"]["clauses"][0]["modality"] = {
        "status": "unresolved", "label": None, "evidence": []}
    target = tmp_path / DECISIONS_V2_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    pack_target = tmp_path / BLANK_REVIEW_V2_REL
    pack_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / BLANK_REVIEW_V2_REL, pack_target)
    mem_target = tmp_path / MEMBERSHIP_REL
    mem_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / MEMBERSHIP_REL, mem_target)
    old = freeze_v2.ROOT
    freeze_v2.ROOT = tmp_path
    try:
        result = freeze_v2.verify()
        assert result["verified"] is False
        assert any("unresolved fields" in p for p in result["problems"])
    finally:
        freeze_v2.ROOT = old


# ---------------------------------------------------------------------------
# E2: importer v2 dry-run
# ---------------------------------------------------------------------------
def test_import_v2_dry_run_accept_all_zero_blocked() -> None:
    report = batch.run_dry_run(None)
    assert report["import_stats"] == {
        "samples": 36, "blocked_fields": 0, "blocked_samples": 0,
        "unresolved_fields": 0, "adjudicable": 36}
    assert report["fail_closed"]["confirmation_event_present"] is False
    assert report["fail_closed"]["applied"] is False
    assert report["fail_closed"]["wrote_decisions"] is False
    assert report["fail_closed"]["reviewer_never_user"] is True
    assert report["zero_api"] == {"new_llm_api_calls": 0}
    # live decisions file untouched (still the adjudicated v3-apply state)
    decisions = _load(DECISIONS_V2_REL)
    assert all(e["review_metadata"]["review_state"] == "adjudicated"
               for e in decisions["records"].values())


def test_import_v2_dry_run_deterministic() -> None:
    first = json.dumps(batch.run_dry_run(None), sort_keys=True,
                       ensure_ascii=False)
    second = json.dumps(batch.run_dry_run(None), sort_keys=True,
                        ensure_ascii=False)
    assert first == second


def test_import_v2_dry_run_would_be_passes_freeze_structure(
        tmp_path: Path) -> None:
    report = batch.run_dry_run(None)
    would_be = json.loads(
        (ROOT / report["would_be_decisions_file"])
        .read_text(encoding="utf-8"))
    target = tmp_path / DECISIONS_V2_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(would_be, ensure_ascii=False),
                      encoding="utf-8")
    pack_target = tmp_path / BLANK_REVIEW_V2_REL
    pack_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / BLANK_REVIEW_V2_REL, pack_target)
    mem_target = tmp_path / MEMBERSHIP_REL
    mem_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / MEMBERSHIP_REL, mem_target)
    old = freeze_v2.ROOT
    freeze_v2.ROOT = tmp_path
    try:
        result = freeze_v2.verify()
        assert result["verified"] is True
        assert result["progress"] == {"unreviewed": 0, "reviewed": 36,
                                      "adjudicated": 0}
        assert result["frozen"] is False
    finally:
        freeze_v2.ROOT = old


@pytest.fixture()
def batch_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the importer v2 writable outputs at a tmp tree while
    keeping ROOT (and the hash-bound sources) real."""
    monkeypatch.setattr(batch, "LOCAL_DIR", tmp_path / "local")
    monkeypatch.setattr(batch, "DRY_RUN_REPORT_REL",
                        tmp_path / "dry_run_report_v2.json")
    yield tmp_path


def test_import_v2_dry_run_with_revisions(batch_tmp: Path) -> None:
    revisions = {
        "SIM_card_scenario/r11/v1": {
            "modality": {"status": "present", "label": "prohibition",
                         "evidence": ["is not obligated"]},
        },
        "blood_donation_scenario/r16/v1": {
            "actor": "absent",
        },
    }
    rev_path = batch_tmp / "revisions_v2.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    report = batch.run_dry_run(rev_path)
    assert report["import_stats"]["blocked_fields"] == 0
    assert report["import_stats"]["adjudicable"] == 36
    would_be = json.loads(
        (ROOT / report["would_be_decisions_file"])
        .read_text(encoding="utf-8"))
    mod = would_be["records"]["SIM_card_scenario/r11/v1"]["canonical"] \
        ["clauses"][0]["modality"]
    assert mod["label"] == "prohibition"
    actor = would_be["records"]["blood_donation_scenario/r16/v1"] \
        ["canonical"]["clauses"][0]["actor"]
    assert actor["status"] == "absent"


def test_import_v2_invalid_revision_refused(tmp_path: Path) -> None:
    revisions = {"SIM_card_scenario/r11/v1":
                 {"modality": {"status": "present", "label": "obligation",
                               "evidence": ["not an exact substring"]}}}
    rev_path = tmp_path / "bad_revisions_v2.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    with pytest.raises(batch.ImportFail, match="not an exact substring"):
        batch.run_dry_run(rev_path)


def test_import_v2_apply_refused_without_event() -> None:
    with pytest.raises(batch.ImportFail, match="no user confirmation"):
        batch.run_apply(None, None)
    # live decisions file untouched (still the adjudicated v3-apply state)
    decisions = _load(DECISIONS_V2_REL)
    assert all(e["review_metadata"]["review_state"] == "adjudicated"
               for e in decisions["records"].values())


def test_import_v2_apply_refused_on_wrong_proposal_sha(tmp_path: Path) -> None:
    event = {
        "kind": "s2_11_batch_import_confirmation",
        "event_id": "fake",
        "proposal_file_sha256": "00" * 64,
        "reviewer": "SomeUser",
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False),
                          encoding="utf-8")
    before = _sha((ROOT / DECISIONS_V2_REL).read_bytes())
    with pytest.raises(batch.ImportFail, match="does not bind this "
                                               "proposal v2 SHA"):
        batch.run_apply(event_path, None)
    assert _sha((ROOT / DECISIONS_V2_REL).read_bytes()) == before


def test_import_v2_apply_writes_adjudicated_with_event_reviewer(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _load(PROPOSAL_REPORT_V2_REL)
    event = {
        "kind": "s2_11_batch_import_confirmation",
        "event_id": "s2-11-batch-confirm-v2-test",
        "proposal_file_sha256": report["proposal_file_sha256"],
        "reviewer": "Eve",
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False),
                          encoding="utf-8")
    # redirect the live decisions target into tmp (never touch the real
    # committed file)
    target = tmp_path / DECISIONS_V2_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / DECISIONS_V2_REL, target)
    real_target = batch.DECISIONS_V2_REL
    monkeypatch.setattr(batch, "DECISIONS_V2_REL", str(target))
    real_sha = _sha((ROOT / DECISIONS_V2_REL).read_bytes())
    try:
        result = batch.run_apply(event_path, None)
        assert result["applied"] is True
        assert result["reviewer"] == "Eve"
        written = json.loads(target.read_text(encoding="utf-8"))
        assert written["applied"] is True
        for entry in written["records"].values():
            assert entry["review_metadata"]["review_state"] == "adjudicated"
            assert entry["review_metadata"]["reviewer"] == "Eve"
            assert entry["review_metadata"]["confirmation_event"] is not None
        # backup exists
        assert (tmp_path / (DECISIONS_V2_REL + ".bak")).is_file()
    finally:
        monkeypatch.setattr(batch, "DECISIONS_V2_REL", real_target)
    # the REAL committed decisions file is untouched
    assert _sha((ROOT / DECISIONS_V2_REL).read_bytes()) == real_sha


def test_import_v2_reviewer_never_user() -> None:
    report = batch.run_dry_run(None)
    blob = json.dumps(report, ensure_ascii=False)
    assert '"reviewer": "user"' not in blob
    would_be = json.loads(
        (ROOT / report["would_be_decisions_file"])
        .read_text(encoding="utf-8"))
    wb_blob = json.dumps(would_be, ensure_ascii=False)
    assert '"reviewer": "user"' not in wb_blob


def test_import_v2_dry_run_report_no_raw_fragments() -> None:
    blob = json.dumps(_load("outputs/reports/s2_11_batch_import_dry_run_v2"
                            ".json"), ensure_ascii=False)
    assert not _has_40_char_corpus_fragment(blob)


def test_import_v2_wrong_revisions_sha_refused(tmp_path: Path) -> None:
    event = {
        "kind": "s2_11_batch_import_confirmation",
        "event_id": "fake2",
        "proposal_file_sha256":
            _load(PROPOSAL_REPORT_V2_REL)["proposal_file_sha256"],
        "revisions_file_sha256": "00" * 64,
        "reviewer": "Eve",
    }
    event_path = tmp_path / "event2.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False),
                          encoding="utf-8")
    revisions = {"SIM_card_scenario/r11/v1": {"actor": "absent"}}
    rev_path = tmp_path / "rev.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    with pytest.raises(batch.ImportFail, match="does not bind the "
                                               "revisions SHA"):
        batch.run_apply(event_path, rev_path)

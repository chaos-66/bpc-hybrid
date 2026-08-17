"""Focused tests for S2.11 canonical proposal v3 (Checkpoint F; zero API).

Covers:
  * REPRODUCTIONS: the six confirmed v2 issues are demonstrated to FAIL
    under the strengthened canonical v3 rules and are FIXED in v3
      - r10/v1 duplicate actor span ids + condition-customer + missing
        actor-action mapping
      - canonical validator v2 gap: duplicate ORDINARY span ids refused
        by v3; duplicate clause ids refused; actor_action_map existence /
        same-clause / duplicate-edge / coverage rules; order relations
        must reference two DIFFERENT existing actions
      - r4/v2 action/constraint overlap eliminated (raw 'happen' +
        normalized; overlap=0)
      - r8/v1 'longer than 30 days' constraint; action 'sending the SIM
        card' (normalized); r18/v2 'immediately' constraint; action
        'sent the reason for rejection' (normalized)
      - r3/v1 + r3/v2 temporal-validity constraints
      - ambiguous auto-occurrence refuses (no occurrence index + multiple
        hits)
  * v3 HARD ACCEPTANCE on the committed assets: 36/36 coverage, exact
    slice=0, duplicate span ids=0, duplicate clause ids=0, ambiguous
    auto-occurrences=0, invalid/missing aam=0, invalid orders=0,
    action/constraint overlaps=0, modality evidence missing=0,
    unresolved=0, display None=0
  * importer v3 dry-run: blocked=0 / unresolved=0 / adjudicable=36/36;
    apply refused; no confirmation event; v1/v2 byte-preserved
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.s2_11_canonical_v3 import (
    validate,
    validate_record,
)
import s2_11_batch_import_v3 as batch
import s2_11_build_proposals_v3 as builder
import verify_s2_11_review_freeze_v3 as freeze_v3

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PROPOSAL_REPORT_V3_REL = "outputs/reports/s2_11_proposal_report_v3.json"
PROPOSAL_REPORT_V1_REL = "outputs/reports/s2_11_proposal_report_v1.json"
PROPOSAL_REPORT_V2_REL = "outputs/reports/s2_11_proposal_report_v2.json"
DECISIONS_V2_REL = "data/development/human_review/s2_11_review_decisions_v2.json"
BLANK_REVIEW_V2_REL = "data/development/human_review/s2_11_blank_review_v2.json"

V1_PROPOSAL_SHA256 = \
    "14c1ec909b2c5aa2249d2acfac1f3e411ff00a3c967a3d6b2ed06ddba8c7364b"
V2_PROPOSAL_SHA256 = \
    "9386642738e73ac2296edb709bd1183b072cacca328b3359762551d0e2b2e5ac"

V3_PACKAGE_REL = ("outputs/development/s2_11_local_working/"
                  "adjudication_proposals_v3")
V3_PROPOSALS_LOCAL = V3_PACKAGE_REL + "/proposals.jsonl"
V3_PACKAGE_MD = V3_PACKAGE_REL + "/decision_package.md"
V3_DIFF_MD = V3_PACKAGE_REL + "/v2_to_v3_semantic_diff.md"
V3_QUALITY_MD = V3_PACKAGE_REL + "/quality_report.md"

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
             (ROOT / V3_PROPOSALS_LOCAL).read_text(encoding="utf-8")
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
# Reproductions: v2 payloads must FAIL under canonical v3 rules
# ---------------------------------------------------------------------------
def test_repro_v2_r10v1_duplicate_actor_ids_rejected() -> None:
    """The v2 r10/v1 payload (two 'the customer' actor spans with the SAME
    id) must be rejected by canonical v3 as a duplicate span id."""
    lines = [ln for ln in
             (ROOT / "outputs" / "development" / "s2_11_local_working" /
              "adjudication_proposals_v2" / "proposals.jsonl")
             .read_text(encoding="utf-8").splitlines() if ln]
    v2 = {json.loads(ln)["sample_id"]: json.loads(ln) for ln in lines}
    entry = v2["SIM_card_scenario/r10/v1"]
    ids = [s["id"] for s in
           entry["canonical"]["clauses"][0]["actor"]["spans"]]
    assert len(ids) == 2 and ids[0] == ids[1]  # the confirmed bug
    problems = validate_record(
        {"canonical": entry["canonical"]},
        _source_texts()["SIM_card_scenario/r10/v1"], allow_unresolved=True)
    assert any("duplicate span id" in p for p in problems)


def test_repro_v2_r10v1_missing_aam_rejected() -> None:
    lines = [ln for ln in
             (ROOT / "outputs" / "development" / "s2_11_local_working" /
              "adjudication_proposals_v2" / "proposals.jsonl")
             .read_text(encoding="utf-8").splitlines() if ln]
    v2 = {json.loads(ln)["sample_id"]: json.loads(ln) for ln in lines}
    entry = v2["SIM_card_scenario/r10/v1"]
    assert entry["canonical"]["actor_action_map"] == []  # the confirmed bug
    problems = validate_record(
        {"canonical": entry["canonical"]},
        _source_texts()["SIM_card_scenario/r10/v1"], allow_unresolved=True)
    assert any("has no actor_action_map edge" in p for p in problems)


def test_repro_v2_r4v2_overlap_eliminated_in_v3() -> None:
    entries = _local_entries()
    c = entries["emergencies_scenario/r4/v2"]["canonical"]["clauses"][0]
    action = c["action"]["spans"][0]
    constraint = c["constraint"]["spans"][0]
    assert action["text"] == "happen"
    assert action.get("normalized") == "happen before the surgery"
    assert constraint["text"] == "before the surgery"
    overlap = max(0, min(action["end"], constraint["end"]) -
                  max(action["start"], constraint["start"]))
    assert overlap == 0


def test_repro_v2_r8v1_constraint_restored() -> None:
    c = _local_entries()["SIM_card_scenario/r8/v1"]["canonical"][
        "clauses"][0]
    constraints = [s["text"] for s in c["constraint"]["spans"]]
    assert "longer than 30 days" in constraints
    action = c["action"]["spans"][0]
    assert action["text"] == "sending the SIM card"
    assert action.get("normalized") == \
        "take longer than 30 days in sending the SIM card"
    assert c["modality"]["label"] == "permission"
    assert c["actor"]["spans"][0]["text"] == "The phone company"


def test_repro_v2_r18v2_immediately_constraint_restored() -> None:
    c = _local_entries()["blood_donation_scenario/r18/v2"]["canonical"][
        "clauses"][0]
    constraints = [s["text"] for s in c["constraint"]["spans"]]
    assert "immediately" in constraints
    action = c["action"]["spans"][0]
    assert action["text"] == "sent the reason for rejection"
    assert action.get("normalized") == \
        "be immediately sent the reason for rejection"
    assert c["actor"]["status"] == "absent"


def test_repro_v2_r3_validity_constraints_added() -> None:
    entries = _local_entries()
    c1 = entries["emergencies_scenario/r3/v1"]["canonical"]["clauses"][0]
    c2 = entries["emergencies_scenario/r3/v2"]["canonical"]["clauses"][0]
    assert [s["text"] for s in c1["constraint"]["spans"]] == [
        "before the patient is discharged",
        "within 24 hours prior to discharge",
        "valid from 2024 to 2030",
    ]
    assert [s["text"] for s in c2["constraint"]["spans"]] == [
        "before the patient is discharged",
        "valid from 2025 to 2031",
    ]
    # the normative clause span covers the full record (no fake clause)
    assert c1["clause_span"]["end"] == len(
        _source_texts()["emergencies_scenario/r3/v1"])
    assert c2["clause_span"]["end"] == len(
        _source_texts()["emergencies_scenario/r3/v2"])


def test_repro_ambiguous_auto_occurrence_refuses() -> None:
    """A spec without an occurrence index that matches multiple times in
    the clause must refuse (no automatic add-all)."""
    text = "the customer X, the customer Y"
    with pytest.raises(builder.BuildFail, match="explicit occurrence"):
        builder._resolve_spec(text, "the customer", None, 0, len(text),
                              "test")


def test_canonical_v3_rejects_duplicate_ordinary_span_ids() -> None:
    entry = _local_entries()["SIM_card_scenario/r10/v1"]["canonical"]
    tampered = copy.deepcopy(entry)
    spans = tampered["clauses"][0]["action"]["spans"]
    spans.append(dict(spans[0]))  # duplicate id
    problems = validate_record({"canonical": tampered},
                               _source_texts()["SIM_card_scenario/r10/v1"],
                               allow_unresolved=True)
    assert any("duplicate span id" in p for p in problems)


def test_canonical_v3_rejects_duplicate_clause_ids() -> None:
    entry = _local_entries()["emergencies_scenario/r2/v1"]["canonical"]
    tampered = copy.deepcopy(entry)
    tampered["clauses"][1]["clause_id"] = tampered["clauses"][0]["clause_id"]
    problems = validate_record({"canonical": tampered},
                               _source_texts()["emergencies_scenario/r2/v1"],
                               allow_unresolved=True)
    assert any("duplicate clause id" in p for p in problems)


def test_canonical_v3_rejects_cross_clause_aam_edge() -> None:
    entry = _local_entries()["emergencies_scenario/r2/v1"]["canonical"]
    tampered = copy.deepcopy(entry)
    tampered["actor_action_map"] = [
        {"actor_span_id": tampered["clauses"][0]["actor"]["spans"][0]["id"],
         "action_span_id": tampered["clauses"][1]["action"]["spans"][0]
         ["id"]}]
    problems = validate_record({"canonical": tampered},
                               _source_texts()["emergencies_scenario/r2/v1"],
                               allow_unresolved=True)
    assert any("different clauses" in p for p in problems)


def test_canonical_v3_rejects_duplicate_aam_edge() -> None:
    entry = _local_entries()["SIM_card_scenario/r10/v1"]["canonical"]
    tampered = copy.deepcopy(entry)
    edge = tampered["actor_action_map"][0]
    tampered["actor_action_map"].append(dict(edge))
    problems = validate_record({"canonical": tampered},
                               _source_texts()["SIM_card_scenario/r10/v1"],
                               allow_unresolved=True)
    assert any("duplicate edge" in p for p in problems)


def test_canonical_v3_rejects_order_before_equals_after() -> None:
    entry = _local_entries()["blood_donation_scenario/r17/v1"]["canonical"]
    tampered = copy.deepcopy(entry)
    aid = tampered["clauses"][0]["action"]["spans"][0]["id"]
    tampered["order_relations"] = [
        {"before_span_id": aid, "after_span_id": aid}]
    problems = validate_record({"canonical": tampered},
                               _source_texts()[
                                   "blood_donation_scenario/r17/v1"],
                               allow_unresolved=True)
    assert any("before == after" in p for p in problems)


def test_canonical_v3_rejects_order_bad_ref() -> None:
    entry = _local_entries()["blood_donation_scenario/r17/v1"]["canonical"]
    tampered = copy.deepcopy(entry)
    tampered["order_relations"] = [
        {"before_span_id": "no_such", "after_span_id": "also_missing"}]
    problems = validate_record({"canonical": tampered},
                               _source_texts()[
                                   "blood_donation_scenario/r17/v1"],
                               allow_unresolved=True)
    assert any("bad before ref" in p for p in problems)


# ---------------------------------------------------------------------------
# v3 hard acceptance (committed assets)
# ---------------------------------------------------------------------------
def test_proposal_v3_report_acceptance_counts() -> None:
    report = _load(PROPOSAL_REPORT_V3_REL)
    assert report["coverage"] == "36/36"
    assert report["proposal_count"] == 36
    assert report["supersedes_v2"]["status"] == \
        "superseded_pending_targeted_correction_do_not_approve"
    assert report["supersedes_v2"]["proposal_file_sha256"] == \
        V2_PROPOSAL_SHA256
    counts = report["acceptance_counts"]
    for key in ("exact_slice_failures", "duplicate_span_ids",
                "duplicate_clause_ids", "ambiguous_auto_occurrences",
                "invalid_or_missing_actor_action_mappings",
                "invalid_order_relations", "action_constraint_overlaps",
                "modality_evidence_missing", "unresolved_fields"):
        assert counts[key] == 0, f"{key} = {counts[key]}"
    assert set(report["needs_attention_ids"]) == EXPECTED_NEEDS_ATTENTION
    assert report["human_approved"] is False
    assert report["gold_created"] is False
    assert report["zero_api"] == {"new_llm_api_calls": 0}


def test_proposal_v3_binds_local_file_and_canonical_valid() -> None:
    report = _load(PROPOSAL_REPORT_V3_REL)
    local = ROOT / report["proposal_file"]
    assert local.is_file()
    assert _sha(local.read_bytes()) == report["proposal_file_sha256"]
    entries = _local_entries()
    payloads = {sid: {"canonical": e["canonical"]} for sid, e in
                entries.items()}
    result = validate(payloads, _source_texts(), allow_unresolved=True,
                      expected_ids=sorted(_source_texts()))
    assert result["valid"] is True, "; ".join(result["problems"][:10])


def test_proposal_v3_no_raw_fragments_committed() -> None:
    blob = json.dumps(_load(PROPOSAL_REPORT_V3_REL), ensure_ascii=False)
    assert not _has_40_char_corpus_fragment(blob)


def test_proposal_v3_package_renders_values_and_normalized() -> None:
    md = (ROOT / V3_PACKAGE_MD).read_text(encoding="utf-8")
    assert len(re.findall(r"^## ", md, flags=re.M)) == 36
    assert "`None`" not in md
    assert "**UNRESOLVED**" not in md
    assert "**ABSENT**" in md
    assert "normalized: happen before the surgery" in md
    assert "valid from 2024 to 2030" in md
    assert "valid from 2025 to 2031" in md


def test_v3_diff_and_quality_reports() -> None:
    diff = (ROOT / V3_DIFF_MD).read_text(encoding="utf-8")
    assert V2_PROPOSAL_SHA256 in diff
    assert "no evidence-based change" in diff
    quality = (ROOT / V3_QUALITY_MD).read_text(encoding="utf-8")
    assert "coverage: 36/36" in quality
    assert "duplicate span IDs: 0" in quality
    assert "ambiguous auto-occurrences: 0" in quality
    assert "action/constraint overlaps: 0" in quality


def test_v1_v2_preserved_byte_exact() -> None:
    v1_local = ROOT / "outputs" / "development" / "s2_11_local_working" / \
        "adjudication_proposals_v1" / "proposals.jsonl"
    v2_local = ROOT / "outputs" / "development" / "s2_11_local_working" / \
        "adjudication_proposals_v2" / "proposals.jsonl"
    assert _sha(v1_local.read_bytes()) == V1_PROPOSAL_SHA256
    assert _sha(v2_local.read_bytes()) == V2_PROPOSAL_SHA256
    for rel in (PROPOSAL_REPORT_V1_REL, PROPOSAL_REPORT_V2_REL):
        repo = ROOT.parent
        proc = subprocess.run(["git", "-C", str(repo), "hash-object",
                               "formal_experiment/" + rel],
                              cwd=repo, capture_output=True, text=True,
                              check=True)
        proc2 = subprocess.run(["git", "-C", str(repo), "rev-parse",
                                "HEAD:formal_experiment/" + rel],
                               cwd=repo, capture_output=True, text=True,
                               check=True)
        assert proc.stdout.strip() == proc2.stdout.strip(), rel


def test_proposal_v3_builder_deterministic() -> None:
    first = json.dumps(builder.build()[0], sort_keys=True,
                       ensure_ascii=False)
    second = json.dumps(builder.build()[0], sort_keys=True,
                        ensure_ascii=False)
    assert first == second


# ---------------------------------------------------------------------------
# Importer v3
# ---------------------------------------------------------------------------
def test_import_v3_dry_run_accept_all() -> None:
    report = batch.run_dry_run(None)
    assert report["import_stats"] == {
        "samples": 36, "blocked_fields": 0, "blocked_samples": 0,
        "unresolved_fields": 0, "adjudicable": 36}
    assert report["fail_closed"]["confirmation_event_present"] is False
    assert report["fail_closed"]["applied"] is False
    assert report["fail_closed"]["wrote_decisions"] is False
    decisions = _load(DECISIONS_V2_REL)
    assert all(e["review_metadata"]["review_state"] == "unreviewed"
               for e in decisions["records"].values())


def test_import_v3_dry_run_would_be_passes_freeze_v3(tmp_path: Path) -> None:
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
    old = freeze_v3.ROOT
    freeze_v3.ROOT = tmp_path
    try:
        result = freeze_v3.verify()
        assert result["verified"] is True
        assert result["progress"] == {"unreviewed": 0, "reviewed": 36,
                                      "adjudicated": 0}
    finally:
        freeze_v3.ROOT = old


def test_import_v3_apply_refused_without_event() -> None:
    with pytest.raises(batch.ImportFail, match="no user confirmation"):
        batch.run_apply(None, None)
    decisions = _load(DECISIONS_V2_REL)
    assert all(e["review_metadata"]["review_state"] == "unreviewed"
               for e in decisions["records"].values())


def test_import_v3_apply_refused_on_wrong_proposal_sha(
        tmp_path: Path) -> None:
    event = {
        "kind": "s2_11_batch_import_confirmation",
        "event_id": "fake3",
        "proposal_file_sha256": "00" * 64,
        "reviewer": "hyc",
    }
    event_path = tmp_path / "event3.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False),
                          encoding="utf-8")
    before = _sha((ROOT / DECISIONS_V2_REL).read_bytes())
    with pytest.raises(batch.ImportFail, match="does not bind this "
                                               "proposal v3 SHA"):
        batch.run_apply(event_path, None)
    assert _sha((ROOT / DECISIONS_V2_REL).read_bytes()) == before


def test_import_v3_wrong_revisions_sha_refused(tmp_path: Path) -> None:
    report = _load(PROPOSAL_REPORT_V3_REL)
    event = {
        "kind": "s2_11_batch_import_confirmation",
        "event_id": "fake3b",
        "proposal_file_sha256": report["proposal_file_sha256"],
        "revisions_file_sha256": "00" * 64,
        "reviewer": "hyc",
    }
    event_path = tmp_path / "event3b.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False),
                          encoding="utf-8")
    revisions = {"SIM_card_scenario/r11/v1": {"actor": "absent"}}
    rev_path = tmp_path / "rev3.json"
    rev_path.write_text(json.dumps(revisions, ensure_ascii=False),
                        encoding="utf-8")
    with pytest.raises(batch.ImportFail, match="does not bind the "
                                               "revisions SHA"):
        batch.run_apply(event_path, rev_path)

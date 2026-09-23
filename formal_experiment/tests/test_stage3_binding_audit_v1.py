"""Focused tests for the Stage-3 binding audit, reference and eligibility layer."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTH = ROOT / "data/development/stage3_synth"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_binding_audit_is_machine_readable_and_separates_ai_from_human():
    audit = _load(SYNTH / "stage3_binding_audit_v1.json")
    assert audit["status"] == "audit_complete"
    assert audit["is_gold"] is False
    assert len(audit["records"]) == 30
    summary = audit["summary"]
    assert summary["action:A"] == 25
    assert summary["action:U"] == 5
    assert summary["actor:A"] == 22
    assert summary["actor:N"] == 7
    assert summary["actor:U"] == 1
    assert summary["order:U"] == 10
    # Every AI-only or missing field is explicitly not human-approved.
    for row in audit["records"]:
        for field in ("action", "actor", "order"):
            value = row[field]
            if value["class"] == "N":
                assert value["human_approved"] is False
            if value["class"] == "U":
                assert value["human_approved"] is False


def test_reference_preserves_human_fields_and_flags_ai_proposals():
    ref = _load(SYNTH / "stage3_binding_reference_v1.json")
    assert ref["is_gold"] is False
    assert ref["human_approved_new_judgments"] is False
    assert len(ref["records"]) == 30
    action_human = sum(1 for r in ref["records"]
                       if r["action_binding"]["human_approved"])
    actor_human = sum(1 for r in ref["records"]
                      if r["actor_binding"]["human_approved"])
    assert action_human == 25
    assert actor_human == 22
    for row in ref["records"]:
        if not row["action_binding"]["human_approved"]:
            assert row["action_binding"]["authority"] in (
                "ai_proposal", "ai_proposed_unresolved")
        if not row["actor_binding"]["human_approved"]:
            assert row["actor_binding"]["authority"] in (
                "ai_proposal", "ai_proposed_unresolved")


def test_eligibility_denominators_are_not_forced_to_ten():
    audit = _load(SYNTH / "stage3_paired_benchmark_eligibility_v1.json")
    assert audit["eligible_pairs_by_type"]["missing_action"] == [
        "syn_missing_action_01", "syn_missing_action_02",
        "syn_missing_action_03", "syn_missing_action_04",
        "syn_missing_action_05", "syn_missing_action_06",
        "syn_missing_action_09", "syn_missing_action_10",
    ]
    assert audit["eligible_pairs_by_type"]["incorrect_actor"] == [
        "syn_incorrect_actor_01", "syn_incorrect_actor_02",
        "syn_incorrect_actor_04", "syn_incorrect_actor_05",
        "syn_incorrect_actor_08",
    ]
    assert audit["eligible_pairs_by_type"]["out_of_order"] == []
    for row in audit["records"]:
        if row["violation_type"] == "out_of_order":
            assert row["eligible"] is False
            assert "ineligible_no_explicit_rule_order" in row["reason"]


def test_strict_validator_reports_provisional_not_ready():
    import validate_stage3_binding_reference_v1 as validator
    report = validator.validate()
    assert report["items"] == 30
    assert report["ready"] is False
    assert report["errors"] == []
    assert report["ready_pairs"] == 13

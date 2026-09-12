# -*- coding: utf-8 -*-
"""Focused checks for the SIM case run (S3.9-EXT-REAL-CASE).

Covers the transforms (flatten + process-level r8 timeout + four minimal
repairs), the run invariants (group C reuses group B's three-type rows;
reference judgments never enter the rule side), P1 status/value-flow
corrections, P2 alarm/reference separation, P2 repair-control validity,
and the publication guard.

Only one full in-memory run is performed (module-scoped fixture); no API.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from bpc_hybrid import sim_case_c1 as core  # noqa: E402
from bpc_hybrid.sim_case_c1_transforms import flatten_collaboration, repair_variant  # noqa: E402
from bpc_hybrid.sim_case_c1_transforms import repair_variant_r8_task_scoped_legacy  # noqa: E402

import run_sim_case_c1_v1 as runner  # noqa: E402

RESTRICTED_MIN_LEN = 40
CAPSULE = ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json"


@pytest.fixture(scope="module")
def flat() -> bytes:
    payload, _ = flatten_collaboration(core.BPMN.read_bytes())
    return payload


@pytest.fixture(scope="module")
def run_result() -> dict:
    return runner.run(overwrite=False, check_only=True)


@pytest.fixture(scope="module")
def capsule() -> dict:
    return json.loads(CAPSULE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def test_flatten_keeps_lane_names_and_drops_collaboration(flat):
    info = json.loads(json.dumps(repair_variant(flat, "r13_threshold_50")[1]))  # sanity
    assert info["repair_id"] == "r13_threshold_50"
    payload, meta = flatten_collaboration(core.BPMN.read_bytes())
    assert meta["transform"] == "flatten_collaboration_v2"
    assert sorted(meta["participants"]) == ["Another phone company", "Customer", "Phone company"]
    assert b"collaboration" not in payload
    assert b"Activate SIM card" in payload


def test_repair_r8_is_process_level_event_subprocess(flat):
    payload, detail = repair_variant(flat, "r8_timeout_termination")
    assert b"triggeredByEvent" in payload
    assert b"P30D" in payload
    assert b"terminateEventDefinition" in payload
    ops = [op["op"] for op in detail["operations"]]
    assert "add_process_level_event_subprocess" in ops
    assert "add_interrupting_timer_start" in ops
    assert "add_terminate_end" in ops


def test_repair_r8_legacy_control_is_preserved_but_task_scoped(flat):
    payload, detail = repair_variant_r8_task_scoped_legacy(flat)
    assert b"sim_fix_timeout_boundary_legacy" in payload
    assert b"P30D" in payload
    assert detail["operations"][0]["op"] == "add_boundary_timer"
    assert detail["operations"][0]["scope"] == "task_scoped"


def test_repair_r9_adds_verification_task(flat):
    payload, detail = repair_variant(flat, "r9_add_verification")
    assert b"sim_fix_verify_correctness" in payload
    ops = [op["op"] for op in detail["operations"]]
    assert ops == ["add_task", "rewire_flow"]


def test_repair_r10_moves_activation_lane(flat):
    payload, detail = repair_variant(flat, "r10_activation_owner")
    assert detail["operations"][0]["to"] == "Phone company"


def test_repair_r11_moves_consent_before_retrieval(flat):
    payload, detail = repair_variant(flat, "r11_consent_before_retrieval")
    ops = {op["op"] for op in detail["operations"]}
    assert ops == {"rewire_flow", "add_sequence_flow", "remove_sequence_flow"}


def test_repair_r13_relabels_threshold(flat):
    payload, detail = repair_variant(flat, "r13_threshold_50")
    assert b"Debt &lt;= 50" in payload or b"Debt <= 50" in payload
    assert detail["operations"][0]["from"] == "Debt < 100"


def test_unknown_repair_is_rejected(flat):
    with pytest.raises(ValueError):
        repair_variant(flat, "not_a_repair")


# ---------------------------------------------------------------------------
# run invariants / P1 status and value flow
# ---------------------------------------------------------------------------

def test_run_covers_the_five_v2_rules_and_reports_counts(run_result):
    assert set(run_result["summary"]) == {"A", "B", "C"}
    assert run_result["summary"]["A"]["checks"] == 15
    assert run_result["summary"]["B"]["checks"] == 15
    assert run_result["summary"]["C"]["checks"] == 35
    for block in run_result["summary"].values():
        assert sum(block["status_counts"].values()) == block["checks"]
        assert sum(block["machine_status_counts"].values()) == block["checks"]
    assert run_result["summary"]["A"]["status_counts"].get("not_applicable", 0) == 0
    assert run_result["summary"]["A"]["status_counts"]["undetermined"] == 12
    assert run_result["summary"]["A"]["machine_status_counts"]["not_applicable"] == 2


def test_empty_rule_action_is_undetermined_not_not_applicable(capsule):
    for rule_id in ("r9", "r13"):
        check = capsule["rules"][rule_id]["sides"]["A"]["checks"]["missing_action"]
        assert check["status"] == core.STATUS_UNDETERMINED
        assert check["machine_status"] == core.STATUS_NOT_APPLICABLE
        assert check["status_source"] == "extraction"
        assert check["evaluation_reason"] == "empty_rule_action_rule_element_not_extracted"
        assert check["denominator"] == 0
        assert check["score"] == 0.0


def test_order_derivation_handles_comma_and_comma_less_conditions():
    action = {"action": "verify the correctness of their personal information"}
    comma = core.derive_order_relations({**action, "condition": "After receiving the data, the controller verifies it"})
    assert comma == [("receiving the data", action["action"])]
    no_comma = core.derive_order_relations({**action, "condition": "After receiving the customer's personal information"})
    assert no_comma == [("receiving the customer's personal information", action["action"])]
    before = core.derive_order_relations({"action": "ask for consent",
                                          "condition": "Before retrieving any kind of personal data"})
    assert before == [("ask for consent", "retrieving any kind of personal data")]
    for non_order in ("if it takes more than 30 days for any reason",
                      "When the customer receives the SIM card", ""):
        assert core.derive_order_relations({**action, "condition": non_order}) == []


def test_group_a_consumes_the_locked_non_llm_baseline(capsule):
    for rule_id in core.MAIN_RULES:
        meta = capsule["rules"][rule_id]["sides"]["A"]["stage2_meta"]
        assert meta["source"] == "sun_rule_only_b0_v10a"
        assert meta["ok"] is True
    assert capsule["plan"]["components"]["A.stage2"]["profile"] == "PROFILE_V10A"


def test_group_c_uses_the_accepted_repair_with_comparison_gate(capsule):
    component = capsule["plan"]["components"]["C.stage3"]["four_types"]
    assert "RepairedExtendedScorerV2" in component
    assert "aggregate_with_comparison_gate" in component
    for rule_id in core.MAIN_RULES:
        gate = capsule["rules"][rule_id]["sides"]["C"]["gate"]
        assert "evidence_comparisons_performed" in gate
        assert gate["explicit_compliance_requires_an_evidence_comparison"] is True


def test_group_c_reuses_group_b_three_type_rows(capsule):
    for rule_id in core.MAIN_RULES:
        sides = capsule["rules"][rule_id]["sides"]
        for check in ("missing_action", "incorrect_actor", "out_of_order"):
            assert sides["C"]["checks"][check] == sides["B"]["checks"][check], (rule_id, check)
        assert sides["C"]["reuses_group_b"] == ["stage2", "three_type_rows"]


def test_chains_record_where_information_was_lost(capsule):
    allowed = {"not_extracted", "full_carry", "partially_carried_by_declared_policy",
               "lost_in_adaptation", "derived_by_declared_policy",
               "present_in_record_without_raw"}
    for rule_id in core.MAIN_RULES:
        chain = capsule["rules"][rule_id]["chain"]
        assert chain["groups"]["B"]["ok"] is True
        assert {v["verdict"] for v in chain["groups"]["B"]["field_flow"].values()} <= allowed
    assert capsule["rules"]["r11"]["chain"]["groups"]["B"]["field_flow"]["order_relations"]["verdict"] \
        == "derived_by_declared_policy"
    assert capsule["rules"]["r9"]["chain"]["groups"]["A"]["field_flow"]["actions"]["verdict"] == "not_extracted"
    r10 = capsule["rules"]["r10"]["chain"]["groups"]["A"]["field_flow"]
    assert r10["actions"]["raw_count"] == 2
    assert r10["actions"]["projected_candidate_count"] == 2
    assert r10["actions"]["adapted_record_count"] == 1
    assert r10["actions"]["verdict"] == "partially_carried_by_declared_policy"
    assert r10["conditions"]["verdict"] == "partially_carried_by_declared_policy"
    assert capsule["rules"]["r10"]["chain"]["groups"]["A"]["actor_action_pair_flow"]["verdict"] == "full_carry"
    assert capsule["rules"]["r8"]["chain"]["groups"]["B"]["actor_action_pair_flow"]["verdict"] \
        == "invalid_in_raw_no_valid_pair"


def test_a_to_b_attribution_records_adaptation_loss(capsule):
    a_to_b = capsule["stage_attribution"]["a_to_b"]
    assert a_to_b["r10"]["difference_attribution"] == "extraction"
    assert a_to_b["r10"]["attribution"] == "extraction_with_adaptation_loss"
    losses = {(x["group"], x["field"]) for x in a_to_b["r10"]["adaptation_loss"]}
    assert ("A", "actions") in losses and ("A", "conditions") in losses


def test_declared_thresholds_are_the_frozen_ones(capsule):
    config = json.loads(core.SUN_CONFIG.read_text(encoding="utf-8"))["method"]["thresholds"]
    thresholds = capsule["plan"]["thresholds"]
    assert thresholds["tau"] == float(config["tau"])
    assert thresholds["gamma"] == float(config["gamma"])
    assert thresholds["theta"] == float(config["theta"])
    assert thresholds["gamma_ext"] == 0.5


def test_reference_judgments_never_enter_the_rule_side(capsule):
    curated = json.loads(core.CURATED.read_text(encoding="utf-8"))
    reference_strings = [item["semantic_issue"]["summary_zh"] for item in curated["items"]]
    reference_strings += [item["dev_reference_judgment"]["judgment"] for item in curated["items"]]
    blob = json.dumps({rid: capsule["rules"][rid]["sides"][g].get("rule")
                       for rid in core.MAIN_RULES for g in ("A", "B")}, ensure_ascii=False)
    for text in reference_strings:
        assert text not in blob


def test_two_runs_produce_identical_results(run_result):
    again = runner.run(overwrite=False, check_only=True)
    assert json.dumps(again, ensure_ascii=False, sort_keys=True) == \
        json.dumps(run_result, ensure_ascii=False, sort_keys=True)


def test_status_vocabulary_is_closed(capsule):
    allowed = {core.STATUS_VIOLATION, core.STATUS_SATISFIED, core.STATUS_UNDETERMINED,
               core.STATUS_NOT_APPLICABLE}
    for row in capsule["comparison"]:
        for group in row["groups"].values():
            for lens in group["lens_results"].values():
                assert lens["status"] in allowed
    for row in capsule["rows"]:
        assert row["status"] in allowed
        assert row["machine_status"] in allowed


# ---------------------------------------------------------------------------
# P2: alarm/reference separation and repair-control validity
# ---------------------------------------------------------------------------

def test_alarm_correspondence_is_not_type_and_status_only(capsule):
    by_rule = {c["rule_id"]: c for c in capsule["comparison"]}
    r8 = by_rule["r8"]["groups"]["C"]
    assert r8["type_and_status_only_match"] is True
    assert r8["found_corresponding_problem"] is False
    assert r8["correspondence_judgment"] == "machine_alarm_but_reference_correspondence_unverified"
    assert r8["machine_alarms"]
    assert by_rule["r9"]["groups"]["C"]["found_corresponding_problem"] is True
    assert by_rule["r10"]["groups"]["C"]["found_corresponding_problem"] is True
    r11 = by_rule["r11"]["groups"]["C"]
    assert r11["found_corresponding_problem"] is False
    assert any(a["check"] == "missing_action" for a in r11["machine_alarms"])
    r13 = by_rule["r13"]["groups"]["C"]
    assert r13["found_corresponding_problem"] is False
    assert {a["check"] for a in r13["machine_alarms"]} == {"incorrect_actor", "prohibited_action_present"}


def test_effective_repair_denominator_excludes_non_evaluable_controls(capsule):
    repairs = {r["repair_id"]: r for r in capsule["repairs"]}
    r8 = repairs["r8_timeout_termination"]
    assert r8["independent_verification"]["repair_semantics_valid"] is True
    assert r8["independent_verification"]["semantics_entered_detection_chain"] is False
    assert r8["in_effective_repair_denominator"] is False
    assert r8["effective_control_exclusion_reason"] == "repair_semantics_not_carried_by_stage1"
    assert "legacy_partial_control" in r8
    assert r8["legacy_partial_control"]["independent_verification"]["repair_semantics_valid"] is False
    r13 = repairs["r13_threshold_50"]
    assert r13["independent_verification"]["repair_semantics_valid"] is True
    assert r13["in_effective_repair_denominator"] is False
    assert r13["effective_control_exclusion_reason"] == "empty_rule_condition"
    effective = {rid for rid, row in repairs.items() if row["in_effective_repair_denominator"]}
    assert effective == {"r9_add_verification", "r10_activation_owner",
                         "r11_consent_before_retrieval"}
    assert capsule["repair_control_summary"]["effective_repair_controls"] == 3


def test_repair_after_evidence_is_preserved_for_effective_controls(capsule):
    repairs = {r["repair_id"]: r for r in capsule["repairs"]}
    r9 = repairs["r9_add_verification"]
    assert r9["before"]["status"] == core.STATUS_VIOLATION
    assert r9["after"]["status"] == core.STATUS_VIOLATION
    assert r9["after"]["details"][0]["best_model_action"] == "Verify correctness of customer personal data"
    r10 = repairs["r10_activation_owner"]
    assert r10["after"]["status"] == core.STATUS_VIOLATION
    owners = {owner for evidence in r10["after"]["matched_action_owner_evidence"]
              for owner in evidence["owners"]}
    assert "Phone company" in owners
    r11 = repairs["r11_consent_before_retrieval"]
    assert r11["after"]["status"] == core.STATUS_UNDETERMINED
    assert r11["after"]["reason"] == "no_mapped_rule_order_endpoints"


# ---------------------------------------------------------------------------
# publication guard
# ---------------------------------------------------------------------------

def test_committable_reports_have_no_restricted_corpus_text():
    requirements = core.load_requirements()
    texts = [t for t in requirements.values() if t.strip()]
    payloads = []
    for path in (ROOT / "outputs/reports/sim_case_c1_results.json",
                 ROOT / "outputs/reports/sim_case_c1_results.md"):
        if path.exists():
            payloads.append(path.read_text(encoding="utf-8"))
    assert payloads
    hits = []
    for text in texts:
        window = text[:RESTRICTED_MIN_LEN]
        for payload in payloads:
            if window in payload:
                hits.append(window)
    assert hits == []


def test_supplement_records_the_missing_llm_group():
    report = json.loads((ROOT / "outputs/reports/sim_case_c1_supplement.json").read_text(encoding="utf-8"))
    assert report["groups_missing"]["B"].startswith("real-LLM")
    assert all(not item["reusable"] for item in report["prediction_reuse_audit"])
    assert report["model_identity"].startswith("our reconstruction")

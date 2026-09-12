# -*- coding: utf-8 -*-
"""Focused checks for the SIM case run (S3.9-EXT-REAL-CASE).

Covers the transforms (flatten + five minimal repairs), the run invariants
(group C reuses group B's three-type rows; reference judgments never enter the
rule side; declared thresholds; status vocabulary) and the publication guard
(no restricted corpus text in the committable reports).

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

import run_sim_case_c1_v1 as runner  # noqa: E402

RESTRICTED_MIN_LEN = 40


@pytest.fixture(scope="module")
def flat() -> bytes:
    payload, _ = flatten_collaboration(core.BPMN.read_bytes())
    return payload


@pytest.fixture(scope="module")
def run_result() -> dict:
    return runner.run(overwrite=False, check_only=True)


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def test_flatten_keeps_lane_names_and_drops_collaboration(flat):
    info = json.loads(json.dumps(repair_variant(flat, "r13_threshold_50")[1]))  # sanity: flat parses
    assert info["repair_id"] == "r13_threshold_50"
    payload, meta = flatten_collaboration(core.BPMN.read_bytes())
    assert meta["transform"] == "flatten_collaboration_v2"
    assert sorted(meta["participants"]) == ["Another phone company", "Customer", "Phone company"]
    assert b"collaboration" not in payload
    assert b"Activate SIM card" in payload  # element labels preserved


def test_repair_r9_adds_verification_task(flat):
    payload, detail = repair_variant(flat, "r9_add_verification")
    assert b"sim_fix_verify_correctness" in payload
    assert b"Verify correctness of customer personal data" in payload
    ops = [op["op"] for op in detail["operations"]]
    assert ops == ["add_task", "rewire_flow"]
    assert detail["original_unmodified"] is True


def test_repair_r10_moves_activation_lane(flat):
    payload, detail = repair_variant(flat, "r10_activation_owner")
    assert detail["operations"][0]["to"] == "Phone company"
    assert b"sim_flat_lane" in payload


def test_repair_r11_moves_consent_before_retrieval(flat):
    payload, detail = repair_variant(flat, "r11_consent_before_retrieval")
    ops = {op["op"] for op in detail["operations"]}
    assert ops == {"rewire_flow", "add_sequence_flow", "remove_sequence_flow"}
    assert b"sim_fix_consent_to_retrieval" in payload


def test_repair_r13_relabels_threshold(flat):
    payload, detail = repair_variant(flat, "r13_threshold_50")
    assert b"Debt &lt;= 50" in payload or b"Debt <= 50" in payload
    assert detail["operations"][0]["from"] == "Debt < 100"


def test_repair_r8_adds_timer_and_termination(flat):
    payload, detail = repair_variant(flat, "r8_timeout_termination")
    assert b"timerEventDefinition" in payload
    assert b"P30D" in payload
    assert detail["operations"][0]["duration"] == "P30D"


def test_unknown_repair_is_rejected(flat):
    with pytest.raises(ValueError):
        repair_variant(flat, "not_a_repair")


# ---------------------------------------------------------------------------
# run invariants
# ---------------------------------------------------------------------------

def test_run_covers_the_five_v2_rules_and_reports_counts(run_result):
    assert set(run_result["summary"]) == {"A", "B", "C"}
    assert run_result["summary"]["A"]["checks"] == 15
    assert run_result["summary"]["B"]["checks"] == 15
    # C = 15 inherited three-type rows + 20 extended rows
    assert run_result["summary"]["C"]["checks"] == 35
    for block in run_result["summary"].values():
        assert sum(block["status_counts"].values()) == block["checks"]


def test_order_derivation_handles_comma_and_comma_less_conditions():
    """P1.3: the temporal adapter must not require a comma (regression guard)."""
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


def test_group_a_consumes_the_locked_non_llm_baseline(run_result):
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    for rule_id in core.MAIN_RULES:
        meta = capsule["rules"][rule_id]["sides"]["A"]["stage2_meta"]
        assert meta["source"] == "sun_rule_only_b0_v10a"
        assert meta["ok"] is True
    assert capsule["plan"]["components"]["A.stage2"]["profile"] == "PROFILE_V10A"


def test_group_c_uses_the_accepted_repair_with_comparison_gate(run_result):
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    component = capsule["plan"]["components"]["C.stage3"]["four_types"]
    assert "RepairedExtendedScorerV2" in component
    assert "aggregate_with_comparison_gate" in component
    for rule_id in core.MAIN_RULES:
        gate = capsule["rules"][rule_id]["sides"]["C"]["gate"]
        assert "evidence_comparisons_performed" in gate
        assert gate["explicit_compliance_requires_an_evidence_comparison"] is True


def test_repairs_are_independently_verified_and_scope_is_recorded(run_result):
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    repairs = {row["repair_id"]: row for row in capsule["repairs"]}
    assert set(repairs) == {"r8_timeout_termination", "r9_add_verification", "r10_activation_owner",
                            "r11_consent_before_retrieval", "r13_threshold_50"}
    for row in repairs.values():
        assert row["independent_verification"]["fix_expressed"] is True, row["repair_id"]
    r8 = repairs["r8_timeout_termination"]["independent_verification"]
    assert r8["scope"] == "task_scoped_timeout"
    assert r8["scope_matches_rule_semantics"] is False
    assert "整个流程" in r8["scope_note_zh"]


def test_chains_record_where_information_was_lost(run_result):
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    for rule_id in core.MAIN_RULES:
        chain = capsule["rules"][rule_id]["chain"]
        assert chain["groups"]["B"]["ok"] is True
        verdicts = {v["verdict"] for v in chain["groups"]["B"]["field_flow"].values()}
        assert verdicts <= {"carried", "not_extracted", "lost_in_adaptation",
                            "derived_by_declared_policy", "present_in_record_without_raw"}
    # the fixed temporal adapter derives order relations for the two temporal rules
    assert capsule["rules"]["r11"]["chain"]["groups"]["B"]["field_flow"]["order_relations"]["verdict"] \
        == "derived_by_declared_policy"
    # the non-LLM baseline failed to extract any action for r9 and r13
    assert capsule["rules"]["r9"]["chain"]["groups"]["A"]["field_flow"]["actions"]["verdict"] == "not_extracted"


def test_group_c_reuses_group_b_three_type_rows(run_result):
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    for rule_id in core.MAIN_RULES:
        sides = capsule["rules"][rule_id]["sides"]
        for check in ("missing_action", "incorrect_actor", "out_of_order"):
            assert sides["C"]["checks"][check] == sides["B"]["checks"][check], (rule_id, check)
        assert sides["C"]["reuses_group_b"] == ["stage2", "three_type_rows"]


def test_declared_thresholds_are_the_frozen_ones(run_result):
    config = json.loads(core.SUN_CONFIG.read_text(encoding="utf-8"))["method"]["thresholds"]
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    thresholds = capsule["plan"]["thresholds"]
    assert thresholds["tau"] == float(config["tau"])
    assert thresholds["gamma"] == float(config["gamma"])
    assert thresholds["theta"] == float(config["theta"])
    assert thresholds["gamma_ext"] == 0.5


def test_reference_judgments_never_enter_the_rule_side(run_result):
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
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


def test_status_vocabulary_is_closed(run_result):
    allowed = {core.STATUS_VIOLATION, core.STATUS_SATISFIED, core.STATUS_UNDETERMINED,
               core.STATUS_NOT_APPLICABLE}
    capsule = json.loads((ROOT / "outputs/development/sim_case_c1/run_v1/capsule.json")
                         .read_text(encoding="utf-8"))
    for row in capsule["comparison"]:
        for group in row["groups"].values():
            for lens in group["lens_results"].values():
                assert lens["status"] in allowed
    for row in capsule["rows"]:
        assert row["status"] in allowed


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

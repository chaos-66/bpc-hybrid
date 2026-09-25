"""Focused R5.1 tests: real v2 data passes, and minimal counterexamples are caught.

No API, no Gold, no old-experiment run.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_stage3_table3_r5_benchmark_v2 as v  # noqa: E402


def bundle() -> dict:
    return copy.deepcopy(v.load_bundle())


def test_real_v2_data_passes_all_checks():
    passed, report = v.validate()
    assert passed, [c["check_id"] for c in report["structural_checks"] + report["content_qualification_checks"] if not c["passed"]]
    assert report["structural_passed"] is True
    assert report["content_qualification_passed"] is True


def test_counterexample_family_crosses_split_is_caught():
    b = bundle()
    for s in b["source"]["requirements"]:
        if s["requirement_id"] == "R5-D-01":
            s["split"] = "test"
    assert not v.check_family_split(b)["passed"]


def test_counterexample_dev_missing_violation_positives_is_caught():
    b = bundle()
    b["reference"]["cases"] = [c for c in b["reference"]["cases"]
                               if not (c["split"] == "development" and c["variant"] == "missing_action")]
    assert not v.check_dev_positive_examples(b)["passed"]


def test_counterexample_order_eligible_without_basis_is_caught():
    b = bundle()
    for s in b["config"]["requirements"]:
        if s["eligible_out_of_order"]:
            s["order_evidence"] = "general business habit"
            break
    assert not v.check_order_eligibility(b)["passed"]


def test_counterexample_permission_scored_by_missing_action_is_caught():
    b = bundle()
    for s in b["config"]["requirements"]:
        if s["modality"] in ("permission", "prohibition"):
            s["eligible_missing_action"] = True
    assert not v.check_permission_prohibition_not_scored(b)["passed"]


def test_counterexample_element_evidence_not_in_input_is_caught():
    b = bundle()
    for s in b["source"]["requirements"]:
        e = s["elements"]["actor"]["evidence"]
        if e["scope"] == "source_excerpt":
            e["text"] = "evidence_phrase_absent_from_the_excerpt_zzz"
            break
    assert not v.check_element_evidence(b)["passed"]


def test_counterexample_challenge_answer_hint_is_caught():
    b = bundle()
    hinted = (b'<?xml version="1.0" encoding="utf-8"?>\n'
              b'<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">'
              b'<process id="P" name="violated condition true"><task id="T1" name="x"/>'
              b'</process></definitions>')
    b["_bpmn_reader"] = lambda rel: hinted
    assert not v.check_challenge_bpmn(b)["passed"]


def test_counterexample_challenge_dangling_task_is_caught():
    b = bundle()
    dangling = (b'<?xml version="1.0" encoding="utf-8"?>\n'
                b'<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">'
                b'<process id="P"><startEvent id="Start"/><task id="T1" name="x"/>'
                b'<endEvent id="End"/><sequenceFlow id="f1" sourceRef="Start" targetRef="End"/>'
                b'</process></definitions>')
    b["_bpmn_reader"] = lambda rel: dangling
    assert not v.check_challenge_bpmn(b)["passed"]


def test_counterexample_exception_polarity_is_caught():
    b = bundle()
    for pair in b["semantic"]["pairs"]:
        if pair["pair_kind"] == "exception":
            for c in pair["cases"]:
                if c["applicability_facts"].get("exception_applies") is True:
                    c["reference"]["outcome"] = "violation"  # wrong: exception true must exempt
                    c["reference"]["duty_in_force"] = True
    assert not v.check_exception_polarity(b)["passed"]


def test_counterexample_reuse_verified_with_failed_check_is_caught():
    b = bundle()
    for row in b["reuse"]["rows"]:
        if row["ours"]["status"] == "verified":
            row["ours"]["checks"]["input_source_text_sha_match"] = {"passed": False, "kind": "input"}
            break
    assert not v.check_budget_and_reuse(b)["passed"]


def test_counterexample_budget_from_quota_is_caught():
    b = bundle()
    b["budget"]["calls_cap_core_request_list"] = 24
    b["budget"]["new_requests"] = 24
    b["budget"]["request_rows"] = b["budget"]["request_rows"] + [{}] * (24 - len(b["budget"]["request_rows"]))
    assert not v.check_budget_and_reuse(b)["passed"]


def test_counterexample_inference_context_leak_is_caught():
    b = bundle()
    b["common_context"]["items"][0]["applicability_scope"] = "violated"
    assert not v.check_inference_isolation(b)["passed"]


def test_counterexample_condition_clause_not_flagged_is_caught():
    b = bundle()
    for s in b["source"]["requirements"]:
        if s["elements"]["condition"]["present"]:
            s["elements"]["condition"] = {"present": False, "value": "", "evidence": {"scope": "not_present", "text": "", "in_input": False}}
            s["excerpt_text"] = "Where personal data are collected, the controller shall provide information."
            break
    assert not v.check_condition_flags(b)["passed"]

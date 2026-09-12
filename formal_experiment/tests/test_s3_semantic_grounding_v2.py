# -*- coding: utf-8 -*-
"""Focused tests for s3_semantic_grounding_v2 evaluation and fallback prep."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    MockSemanticGroundingTransport,
    build_request_set,
    execute_fallback,
    validate_authorization,
    validate_semantic_grounding_response,
)
from bpc_hybrid.s3_semantic_grounding_v2 import (  # noqa: E402
    CONTROL_GLOBAL_VERIFIED,
    audit_composite_collisions,
    build_clean_control_set,
    build_compact_local_context,
    build_fallback_pack,
    control_global_compliance_status,
    evaluate_target_paired,
    input_identity,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES, NONE_LABEL  # noqa: E402

TYPES = list(EXTENDED_TYPES)


def clean_checks():
    return {
        target: {"status": "not_applicable", "observable": True,
                 "violation": False, "reason": "empty_rule_field"}
        for target in TYPES
    }


def make_row(item_id, side, label, *, rule_hash="rule-a", process_hash="proc-a",
             bpmn_hash="bpmn-a", checks=None, action_status="resolved",
             rule=None, context=None):
    return {
        "item_id": item_id,
        "side": side,
        "expected_label": label,
        "canonical_rule_input_hash": rule_hash,
        "canonical_process_input_hash": process_hash,
        "bpmn_sha256": bpmn_hash,
        "checks": checks or clean_checks(),
        "action_grounding": {"status": action_status, "candidates": []},
        "model_visible_rule_input": rule or {
            "rule_id": "r", "sentence_idx": 0, "modality": "obligation",
            "actor": "controller", "action": "notify", "condition": None,
            "constraint": None, "exception": None,
        },
        "compact_local_context": context or {
            "candidate_activities": [{"activity_id": "A", "label": "Notify",
                                      "owners": [], "similarity": 1.0,
                                      "lexical_coverage": 1.0}],
            "nodes": [{"id": "A", "kind": "activity", "label": "Notify"}],
            "sequence_flows": [],
            "condition_evidence": [],
            "constraint_bound_evidence": [],
            "constraint_unbound_evidence": [],
            "exception_handler_candidates": [],
            "evidence_ids": ["A"],
        },
    }


def test_composite_collision_true_and_false_cases():
    true_a = make_row("true-a", "variant", "required_condition_not_enforced")
    true_b = make_row("true-b", "variant", "constraint_violated")
    different_rule = make_row("other-rule", "variant", "exception_not_handled",
                              rule_hash="rule-b")
    same_bpmn_other_rule = make_row("other-rule-b", "variant", "constraint_violated",
                                    rule_hash="rule-c")
    result = audit_composite_collisions([true_a, true_b, different_rule, same_bpmn_other_rule])
    assert result["true_collision_group_count"] == 1
    assert result["true_collision_item_count"] == 2
    assert result["old_bpmn_only_variant_collision_group_count"] >= 1


def test_same_bpmn_different_rule_is_not_true_collision():
    record = {"process_id": "p", "activities": [], "events": [], "gateways": [],
              "sequence_flows": [], "pools": [], "lanes": [], "control_flow": {}}
    xml = ET.fromstring("<process/>")
    a = input_identity({"rule_id": "r", "sentence_idx": 0, "action": "a"}, record, xml, "same")
    b = input_identity({"rule_id": "r", "sentence_idx": 0, "action": "b"}, record, xml, "same")
    assert a["bpmn_sha256"] == b["bpmn_sha256"]
    assert a["canonical_process_input_hash"] == b["canonical_process_input_hash"]
    assert a["canonical_rule_input_hash"] != b["canonical_rule_input_hash"]


def test_same_rule_same_process_different_gold_is_true_collision():
    row_a = make_row("a", "variant", "required_condition_not_enforced")
    row_b = make_row("b", "variant", "constraint_violated")
    result = audit_composite_collisions([row_a, row_b])
    assert result["true_collision_group_count"] == 1
    assert result["true_collision_item_count"] == 2
    assert result["identity_definition"].startswith("canonical_rule_input_hash")


def test_target_paired_evaluator_is_prediction_blind():
    checks_variant = clean_checks()
    checks_variant["required_condition_not_enforced"] = {
        "status": "not_enforced", "observable": True, "violation": True,
        "reason": "condition_absent"}
    checks_control = clean_checks()
    variant = make_row("pair", "variant", "required_condition_not_enforced",
                       checks=checks_variant)
    control = make_row("pair", "control", NONE_LABEL, checks=checks_control)
    result = evaluate_target_paired([variant], [control],
                                    {"pair": "required_condition_not_enforced"})
    assert result["per_type"]["required_condition_not_enforced"]["variant"]["TP"] == 1
    assert result["per_type"]["required_condition_not_enforced"]["control"]["TN"] == 1
    # Prediction/check content must remain untouched.
    assert variant["checks"]["required_condition_not_enforced"]["violation"] is True
    assert "does_not_mutate_predictions" in result and result["does_not_mutate_predictions"]


def test_control_global_compliance_does_not_read_expected_label():
    checks = clean_checks()
    row = make_row("control", "control", "constraint_violated", checks=checks)
    status = control_global_compliance_status(row["checks"])
    assert status["status"] == CONTROL_GLOBAL_VERIFIED
    assert status["reads_expected_label"] is False
    clean = build_clean_control_set([row])
    assert clean["verified_compliant_item_ids"] == ["control"]


def test_fallback_payload_anonymization_and_no_metadata_leakage():
    checks = clean_checks()
    checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "condition_surface_ambiguous_or_incomplete"}
    context = {
        "candidate_activities": [{"activity_id": "syn_v2_handler_01", "label": "Handler",
                                  "owners": [], "similarity": 1.0,
                                  "lexical_coverage": 1.0}],
        "nodes": [{"id": "syn_v2_handler_01", "kind": "activity", "label": "Handler"}],
        "sequence_flows": [],
        "condition_evidence": [{"id": "syn_v2_handler_01", "text": "condition"}],
        "constraint_bound_evidence": [],
        "constraint_unbound_evidence": [],
        "exception_handler_candidates": [],
        "evidence_ids": ["syn_v2_handler_01"],
    }
    row = make_row("item", "variant", "required_condition_not_enforced",
                   checks=checks, context=context)
    pack = build_fallback_pack([row])
    assert pack["item_count"] == 1
    item = pack["items"][0]
    serialized = json.dumps(item["llm_visible_payload"], ensure_ascii=False)
    assert "syn_v2_" not in serialized
    for forbidden in ("expected_violation", "mutation_type", "target_field",
                      "mutation_config", "target_activity_id", "Gold"):
        assert forbidden not in serialized
    assert item["side"] == "variant"


def test_strict_evidence_id_validation_and_fail_closed():
    request = {
        "input_payload": {
            "rule_record": {"condition": "consent obtained", "constraint": None,
                            "exception": None, "action": "notify"},
            "candidate_activity_ids": ["A"],
            "local_context": {"evidence_ids": ["E1"]},
        }
    }
    valid = {
        "action_grounding": {"status": "matched", "activity_id": "A", "confidence": 0.9},
        "condition": {"status": "enforced", "evidence_ids": ["E1"], "confidence": 0.9},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    assert validate_semantic_grounding_response(json.dumps(valid), request)["status"] == "valid"
    hallucinated = json.loads(json.dumps(valid))
    hallucinated["condition"]["evidence_ids"] = ["HALLUCINATED"]
    assert validate_semantic_grounding_response(json.dumps(hallucinated), request)["status"] == "failed"
    assert validate_semantic_grounding_response("{not json", request)["status"] == "failed"


def test_mock_execution_and_resume_no_double_send(tmp_path):
    checks = clean_checks()
    checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "condition_surface_ambiguous_or_incomplete"}
    item = make_row("item", "variant", "required_condition_not_enforced", checks=checks)
    pack = build_fallback_pack([item])
    config = {"model": "mock-model", "max_output_tokens_per_call": 32,
              "temperature": 0.0, "top_p": 1.0}
    request_set = build_request_set(pack, config)
    first = execute_fallback(pack=pack, request_set=request_set, config=config,
                             output_root=tmp_path, mode="mock",
                             transport=MockSemanticGroundingTransport())
    second = execute_fallback(pack=pack, request_set=request_set, config=config,
                              output_root=tmp_path, mode="mock",
                              transport=MockSemanticGroundingTransport())
    assert first["counts"]["attempted"] == 1
    assert second["counts"]["skipped_resume_protected"] == 1
    assert (tmp_path / "s3_semantic_grounding_llm_v1_mock_run/execution_ledger.jsonl").is_file()


def test_authorization_scope_mismatch_is_rejected():
    pack = build_fallback_pack([])
    request_set = build_request_set(pack, {"model": "m", "max_output_tokens_per_call": 8})
    auth = {"scope": "OLD-TASK", "model": "m", "max_calls": 1, "retry": 0,
            "off_peak_only": True, "candidate_pack_sha256": "x",
            "request_set_sha256": "y", "status": "authorized_unconsumed",
            "usd_cap": 9999, "required_usd_cap": 0,
            "authorization_sentence_sha256": "z"}
    result = validate_authorization(auth, pack, request_set,
                                    {"model": "m"})
    assert result["valid"] is False
    assert "scope_mismatch" in result["errors"]


def test_c36_original_three_and_v1_artifacts_unchanged():
    c36 = json.loads((ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json")
                     .read_text(encoding="utf-8"))
    for key, expected in c36["artifacts"].items():
        path = ROOT / key.replace("\\", "/")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, key
    v1_hashes = json.loads(
        (ROOT / "outputs/evidence/s3_semantic_grounding_v1/artifact_hashes.json")
        .read_text(encoding="utf-8"))
    for key, expected in v1_hashes["artifacts"].items():
        path = ROOT / key
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, key


def test_build_fallback_pack_is_deterministic():
    checks = clean_checks()
    checks["constraint_violated"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "unsupported_abstract_constraint_kind"}
    row = make_row("item", "variant", "constraint_violated", checks=checks)
    first = json.dumps(build_fallback_pack([row]), ensure_ascii=False, sort_keys=True)
    second = json.dumps(build_fallback_pack([row]), ensure_ascii=False, sort_keys=True)
    assert first == second

def test_final_deterministic_violation_is_excluded_from_fallback_pack():
    checks = clean_checks()
    checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "condition_surface_ambiguous_or_incomplete"}
    row = make_row("item", "variant", "required_condition_not_enforced", checks=checks)
    row["predicted_violation_type"] = "required_condition_not_enforced"
    pack = build_fallback_pack([row])
    assert pack["item_count"] == 0


def test_target_paired_evaluation_is_deterministic():
    checks_variant = clean_checks()
    checks_variant["required_condition_not_enforced"] = {
        "status": "not_enforced", "observable": True, "violation": True,
        "reason": "condition_absent"}
    variant = make_row("pair", "variant", "required_condition_not_enforced",
                       checks=checks_variant)
    control = make_row("pair", "control", NONE_LABEL, checks=clean_checks())
    expected = {"pair": "required_condition_not_enforced"}
    first = json.dumps(evaluate_target_paired([variant], [control], expected),
                       ensure_ascii=False, sort_keys=True)
    second = json.dumps(evaluate_target_paired([variant], [control], expected),
                        ensure_ascii=False, sort_keys=True)
    assert first == second

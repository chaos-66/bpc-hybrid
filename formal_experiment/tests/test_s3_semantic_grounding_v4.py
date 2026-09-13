# -*- coding: utf-8 -*-
"""Focused offline tests for the v4 field-wise LLM application chain."""

from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_v1 import validate_llm_response  # noqa: E402
from bpc_hybrid.s3_semantic_grounding_llm_v1 import (  # noqa: E402
    validate_semantic_grounding_response,
)
from bpc_hybrid.s3_semantic_grounding_v4 import (  # noqa: E402
    NONE_LABEL,
    apply_llm_grounding,
    build_fallback_pack,
    normalize_llm_status,
)
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402

TYPES = list(EXTENDED_TYPES)


def clean_checks():
    return {
        target: {"status": "not_applicable", "observable": True,
                  "violation": False, "reason": "empty_rule_field"}
        for target in TYPES
    }


def make_record(*, activity_id="A2", action_label="notify subject",
                condition="consent obtained", include_flow=True,
                include_exception_handler=False):
    activities = [{"id": "A1", "name": "review request"},
                  {"id": activity_id, "name": action_label}]
    flows = []
    if include_flow:
        flows.append({
            "id": "F1", "name": None,
            "source_ref": "A1", "target_ref": activity_id,
            "condition_expression": condition,
        })
    if include_exception_handler:
        activities.append({"id": "A3", "name": "fallback handler"})
        flows.append({
            "id": "F2", "name": None,
            "source_ref": activity_id, "target_ref": "A3",
            "condition_expression": None,
        })
    return {
        "process_id": "p",
        "pools": [{"process_ref": "p", "name": "Controller"}],
        "lanes": [],
        "activities": activities,
        "events": [],
        "gateways": [],
        "sequence_flows": flows,
        "control_flow": {},
    }


def make_xml(*, include_flow=True, include_timer=False, include_handler=False):
    parts = ['<process id="p">']
    if include_flow:
        parts.append('<sequenceFlow id="F1" sourceRef="A1" targetRef="A2" />')
    if include_timer:
        parts.append('<dataObjectReference id="D1" name="48 hours" />')
        parts.append('<association id="AS1" sourceRef="A2" targetRef="D1" />')
    if include_handler:
        parts.append('<sequenceFlow id="F2" sourceRef="A2" targetRef="A3" />')
    parts.append("</process>")
    return ET.fromstring("".join(parts))


def make_row(*, modality="obligation", action="notify subject",
             condition="consent obtained", constraint=None, exception=None,
             action_status="unresolved", checks=None, record=None,
             context_extra=None):
    record = record or make_record()
    context = {
        "sentence": {
            "rule_id": "r1",
            "sentence_idx": 0,
            "modality": modality,
            "actor": "the controller",
            "action": action,
            "condition": condition,
            "constraint": constraint,
            "exception": exception,
        },
        "record": record,
        "xml_root": make_xml(),
    }
    raw_context = {
        "candidate_activities": [
            {"activity_id": "A2", "label": "notify subject", "owners": [],
             "similarity": 0.9, "lexical_coverage": 0.9},
        ],
        "nodes": [{"id": "A2", "kind": "activity", "label": "notify subject"}],
        "sequence_flows": [],
        "condition_evidence": [
            {"id": "F1", "text": "consent obtained", "kind": "condition_expression"},
        ],
        "constraint_bound_evidence": [],
        "constraint_unbound_evidence": [],
        "exception_handler_candidates": [],
        "evidence_ids": ["F1"],
    }
    if context_extra:
        raw_context.update(context_extra)
    return {
        "item_id": "item",
        "side": "variant",
        "process_id": "p",
        "rule_id": "r1",
        "expected_label": "required_condition_not_enforced",
        "predicted_violation_type": None,
        "decision": {"predicted": None, "reason": "semantic_grounding_ambiguous",
                     "pending_types": ["required_condition_not_enforced"]},
        "scores": None,
        "observability": None,
        "checks": checks or clean_checks(),
        "action_grounding": {
            "schema": "s3_semantic_grounding_action@1.0.0",
            "status": action_status,
            "reason": "test_stub",
            "activity_id": None,
            "candidate_activity_ids": ["A2"],
            "candidates": [
                {"activity_id": "A2", "label": "notify subject",
                 "owners": [], "similarity": 0.9, "lexical_coverage": 0.9},
            ],
            "alternatives": [],
        },
        "model_visible_rule_input": context["sentence"],
        "canonical_rule_input_hash": "rule",
        "canonical_process_input_hash": "process",
        "bpmn_sha256": "bpmn",
        "compact_local_context": raw_context,
        "control_global_compliance": None,
        "fallback_triggers": [],
        "_grounding_context": context,
    }


def unknown_condition_checks():
    checks = clean_checks()
    checks["required_condition_not_enforced"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "action_grounding_unresolved",
    }
    return checks


def response_with_anonymous_ids(pack):
    item = pack["items"][0]
    forward = item["anonymized_id_map"]
    anonymous = {real: anon for real, anon in forward.items()}
    return item, anonymous


def test_one_ambiguous_field_does_not_block_action_and_condition():
    checks = unknown_condition_checks()
    checks["constraint_violated"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "unsupported_abstract_constraint_kind",
    }
    row = make_row(checks=checks, constraint="without undue delay")
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    response = {
        "action_grounding": {
            "status": "matched", "activity_id": anonymous["A2"], "confidence": 0.9,
        },
        "condition": {
            "status": "enforced", "evidence_ids": [anonymous["F1"]], "confidence": 0.9,
        },
        "constraint": {
            "status": "ambiguous", "evidence_ids": [], "confidence": 0.0,
        },
        "exception": {
            "status": "not_applicable", "evidence_ids": [], "confidence": 0.9,
        },
    }
    assert normalize_llm_status(response) == "resolved"
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    assert applied["action_grounding"]["activity_id"] == "A2"
    assert applied["checks"]["required_condition_not_enforced"]["violation"] is False
    assert applied["checks"]["constraint_violated"]["status"] == "unknown"
    assert applied["predicted_violation_type"] is None
    assert applied["decision"]["decision"] == "abstention"
    assert applied["llm_application"]["action_grounding_applied"] is True


def test_action_mapping_recheck_updates_prohibited_consumer():
    checks = unknown_condition_checks()
    checks["prohibited_action_present"] = {
        "status": "unresolved", "observable": False, "violation": None,
        "reason": "action_grounding_unresolved",
    }
    row = make_row(modality="prohibition", action="notify subject", checks=checks)
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    response = {
        "action_grounding": {
            "status": "matched", "activity_id": anonymous["A2"], "confidence": 0.9,
        },
        "condition": {"status": "ambiguous", "evidence_ids": [], "confidence": 0.0},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    prohibited = applied["checks"]["prohibited_action_present"]
    assert prohibited["observable"] is True
    assert prohibited["violation"] is True
    assert applied["predicted_violation_type"] == "prohibited_action_present"
    assert applied["llm_application"]["action_real_activity_id"] == "A2"


def test_negative_claim_without_closed_scope_stays_unknown():
    record = make_record(include_flow=False, condition="consent obtained")
    row = make_row(condition="consent obtained", record=record,
                   checks=unknown_condition_checks())
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    response = {
        "action_grounding": {
            "status": "matched", "activity_id": anonymous["A2"], "confidence": 0.9,
        },
        "condition": {"status": "not_enforced", "evidence_ids": [], "confidence": 0.95},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    condition = applied["checks"]["required_condition_not_enforced"]
    assert condition["violation"] is not True
    assert condition["status"] == "unknown"
    assert applied["predicted_violation_type"] is None


def test_high_confidence_without_evidence_abstains():
    row = make_row(checks=unknown_condition_checks(),
                   record=make_record(condition="different condition"))
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    response = {
        "action_grounding": {"status": "matched", "activity_id": anonymous["A2"],
                              "confidence": 1.0},
        "condition": {"status": "enforced", "evidence_ids": [], "confidence": 1.0},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 1.0},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 1.0},
    }
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    condition = applied["checks"]["required_condition_not_enforced"]
    assert condition["observable"] is not True
    assert condition["violation"] is None
    assert "condition" in applied["llm_application"]["fields_abstained"]


def test_unresolvable_or_out_of_surface_evidence_is_rejected():
    row = make_row(checks=unknown_condition_checks(),
                   record=make_record(condition="different condition"))
    row["compact_local_context"]["nodes"].append(
        {"id": "A1", "kind": "activity", "label": "review request"})
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    base = {
        "action_grounding": {"status": "matched", "activity_id": anonymous["A2"],
                              "confidence": 0.9},
        "condition": {"status": "enforced", "evidence_ids": ["HALLUCINATED"],
                       "confidence": 0.9},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": base}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    assert applied["checks"]["required_condition_not_enforced"]["violation"] is not True
    failures = applied["llm_application"]["evidence_binding_failures"]
    assert any(f["kind"] == "evidence_id_not_reversible" for f in failures)

    # A reverse-mappable id that is not in the target action surface is also rejected.
    response = json.loads(json.dumps(base))
    response["condition"]["evidence_ids"] = [anonymous["A1"]]
    applied2 = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    assert applied2["checks"]["required_condition_not_enforced"]["violation"] is not True
    assert any(f["kind"] == "evidence_id_out_of_surface"
               for f in applied2["llm_application"]["evidence_binding_failures"])


def test_constraint_claim_requires_programmatic_time_confirmation():
    record = make_record()
    xml = make_xml(include_timer=True)
    row = make_row(action="notify subject", constraint="within 24 hours",
                   checks=unknown_condition_checks(), record=record)
    row["_grounding_context"]["xml_root"] = xml
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    # The D1 evidence is outside the row stubs visible context until we refresh it.
    row["compact_local_context"]["constraint_bound_evidence"] = [
        {"id": "D1", "text": "48 hours", "kind": "dataObjectReference",
         "relation": "action_associated_data"}
    ]
    row["compact_local_context"]["evidence_ids"] = ["F1", "D1"]
    row["_grounding_context"]["sentence"]["constraint"] = "within 24 hours"
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    response = {
        "action_grounding": {"status": "matched", "activity_id": anonymous["A2"],
                              "confidence": 0.9},
        "condition": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "constraint": {"status": "violated", "evidence_ids": [anonymous["D1"]],
                        "confidence": 0.95},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    constraint = applied["checks"]["constraint_violated"]
    assert constraint["observable"] is True
    assert constraint["violation"] is True
    assert constraint["source"] in {"program_recheck_after_llm_action",
                                      "program_verified_llm_evidence"}


def test_clear_deterministic_check_is_not_overwritten():
    checks = clean_checks()
    checks["required_condition_not_enforced"] = {
        "status": "enforced", "observable": True, "violation": False,
        "reason": "deterministic_closed_scope",
    }
    checks["constraint_violated"] = {
        "status": "unknown", "observable": False, "violation": None,
        "reason": "unsupported_abstract_constraint_kind",
    }
    row = make_row(checks=checks)
    pack = build_fallback_pack([row])
    item, anonymous = response_with_anonymous_ids(pack)
    response = {
        "action_grounding": {"status": "matched", "activity_id": anonymous["A2"],
                              "confidence": 0.9},
        "condition": {"status": "not_enforced", "evidence_ids": [], "confidence": 0.9},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    applied = apply_llm_grounding(
        [row],
        [{"source_index": 0, "fallback_item_id": item["fallback_item_id"],
          "status": "validated", "response": response}],
        pack=pack,
        contexts={(0, "variant"): row["_grounding_context"]},
    )[0]
    assert applied["checks"]["required_condition_not_enforced"]["reason"] \
        == "deterministic_closed_scope"


def test_visibility_derivation_after_context_truncation():
    context = {
        "candidate_activities": [
            {"activity_id": "A2", "label": "notify subject", "owners": [],
             "similarity": 0.9, "lexical_coverage": 0.9},
        ],
        "nodes": [{"id": "A2", "kind": "activity", "label": "notify subject"}],
        "sequence_flows": [],
        "condition_evidence": [
            {"id": f"E{i:02d}", "text": f"evidence {i}", "kind": "condition_expression"}
            for i in range(25)
        ],
        "constraint_bound_evidence": [],
        "constraint_unbound_evidence": [],
        "exception_handler_candidates": [],
        "evidence_ids": [f"E{i:02d}" for i in range(25)],
    }
    row = make_row(checks=unknown_condition_checks(), context_extra=context)
    pack = build_fallback_pack([row])
    assert pack["item_count"] == 1
    item = pack["items"][0]
    assert item["evidence_ids_visible_in_payload"] is True
    visible_condition = item["llm_visible_payload"]["local_context"]["condition_evidence"]
    visible_ids = {entry["id"] for entry in visible_condition}
    advertised = set(item["llm_visible_payload"]["local_context"]["evidence_ids"])
    assert advertised <= visible_ids
    assert "E24" not in advertised


def test_validator_rejects_nan_infinity_and_non_object_fields():
    request = {
        "input_payload": {
            "rule_record": {"condition": "consent obtained", "constraint": None,
                            "exception": None, "action": "notify"},
            "candidate_activity_ids": ["A"],
            "local_context": {"evidence_ids": []},
        }
    }
    base = {
        "action_grounding": {"status": "matched", "activity_id": "A", "confidence": 0.9},
        "condition": {"status": "enforced", "evidence_ids": [], "confidence": float("nan")},
        "constraint": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
        "exception": {"status": "not_applicable", "evidence_ids": [], "confidence": 0.9},
    }
    result = validate_semantic_grounding_response(json.dumps(base), request)
    assert result["status"] == "failed"
    base["condition"] = None
    result = validate_semantic_grounding_response(json.dumps(base), request)
    assert result["status"] == "failed"
    assert "not_object" in result["error"] or "keys" in result["error"]

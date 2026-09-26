# -*- coding: utf-8 -*-
"""Focused named tests for S3.9-EXT-PC-V1.

These tests exercise the bounded semantic checker, the inference-view isolation
boundary, deterministic replay, and evaluator freeze ordering.  They do not run
the full mechanism diagnosis or the full project test suite.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.s3_ext_pc_v1 import (  # noqa: E402
    REL_ABSENCE,
    REL_CONDITIONAL_PROHIBITION,
    REL_DIRECT_PROHIBITION,
    REL_NECESSARY_PRECONDITION,
    REL_PERMISSION,
    REL_RULE_APPLICABILITY,
    REL_TRIGGER_OBLIGATION,
    check_object,
    supported_bpmn_fragment,
)

MECH_DIR = ROOT / "data/development/stage3_ext_pc_v1"
BUILD_LEGACY = ROOT / "scripts/build_s3_ext_pc_v1.py"
BUILD_MECHANISM = ROOT / "scripts/build_s3_ext_pc_v1_mechanism.py"


# ---------------------------------------------------------------------------
# minimal process-record helpers
# ---------------------------------------------------------------------------

def _activity(activity_id: str, name: str, activity_type: str = "task") -> dict:
    return {"id": activity_id, "name": name, "type": activity_type, "lane_ids": []}


def _event(event_id: str, event_type: str = "startEvent", name: str = "Event") -> dict:
    return {"id": event_id, "name": name, "type": event_type, "lane_ids": []}


def _gateway(gateway_id: str, gateway_type: str = "exclusiveGateway", name: str = "Gateway") -> dict:
    return {"id": gateway_id, "name": name, "type": gateway_type, "lane_ids": []}


def _flow(flow_id: str, source: str, target: str, condition: str | None = None, name: str = "") -> dict:
    return {
        "id": flow_id,
        "name": name,
        "source_ref": source,
        "target_ref": target,
        "condition_expression": condition,
        "is_default": False,
    }


def _record(activities=(), gateways=(), flows=(), start_ids=("start",), event_types=None):
    events = [_event("start", "startEvent", "Start"), _event("end", "endEvent", "End")]
    if event_types:
        events = event_types
    return {
        "process_id": "test_process",
        "activities": list(activities),
        "events": events,
        "gateways": list(gateways),
        "sequence_flows": list(flows),
        "control_flow": {
            "start_event_ids": list(start_ids),
            "cycle_detected": False,
        },
    }


def _rule(relation_type: str, action: str = "disclose personal data", condition: str | None = None,
          vocabulary=None, contract: str = "exact_normalized_complete_enumeration") -> dict:
    return {
        "relation_type": relation_type,
        "action": action,
        "condition": condition,
        "canonical_action_vocabulary": vocabulary or [action],
        "action_binding_contract": contract,
        "condition_binding_contract": "exact_canonical_condition_surface_complete",
    }


# ---------------------------------------------------------------------------
# applicability tests
# ---------------------------------------------------------------------------

def test_not_required_is_not_prohibition() -> None:
    result = check_object(_rule(REL_ABSENCE), _record())
    assert result["applicability"] == "not_applicable"
    assert result["decision"] is None
    assert result["reason"] == "absence_of_obligation_not_prohibition"


def test_permission_is_not_prohibition() -> None:
    result = check_object(_rule(REL_PERMISSION), _record())
    assert result["applicability"] == "not_applicable"
    assert result["reason"] == "permission_not_prohibition"


def test_shall_not_apply_is_not_process_action_prohibition() -> None:
    result = check_object(_rule(REL_RULE_APPLICABILITY), _record())
    assert result["applicability"] == "not_applicable"
    assert result["reason"] == "rule_applicability_not_process_action_prohibition"


def test_conditional_prohibition_is_unsupported_v1() -> None:
    result = check_object(_rule(REL_CONDITIONAL_PROHIBITION), _record())
    assert result["applicability"] == "unsupported"
    assert result["decision"] is None
    assert result["reason"] == "conditional_prohibition_outside_v1"


# ---------------------------------------------------------------------------
# prohibition tests
# ---------------------------------------------------------------------------

def test_prohibition_requires_reachable_executable_activity() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data")],
        flows=[_flow("f1", "start", "a"), _flow("f2", "a", "end")],
    )
    result = check_object(_rule(REL_DIRECT_PROHIBITION), record)
    assert result["applicability"] == "applicable"
    assert result["decision"] == "violation"
    assert result["evidence"]["reachable_path"]["node_ids"] == ["start", "a"]


def test_prohibition_unreachable_decoy_does_not_violate() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data")],
        flows=[_flow("f1", "start", "end")],
    )
    result = check_object(_rule(REL_DIRECT_PROHIBITION), record)
    assert result["decision"] == "satisfied"
    assert result["reason"] == "prohibited_action_nodes_unreachable_from_any_start"


def test_prohibition_non_action_text_does_not_count() -> None:
    record = _record(
        gateways=[_gateway("g", "exclusiveGateway", "disclose personal data")],
        flows=[_flow("f1", "start", "g"), _flow("f2", "g", "end")],
    )
    result = check_object(_rule(REL_DIRECT_PROHIBITION), record)
    assert result["decision"] == "satisfied"
    assert result["evidence"]["reachable_action_ids"] == []


def test_prohibition_same_verb_different_object_does_not_match() -> None:
    record = _record(
        activities=[_activity("a", "disclose metadata")],
        flows=[_flow("f1", "start", "a"), _flow("f2", "a", "end")],
    )
    result = check_object(
        _rule(REL_DIRECT_PROHIBITION, vocabulary=["disclose metadata", "disclose personal data"]),
        record,
    )
    assert result["decision"] == "satisfied"
    assert result["evidence"]["action_binding"]["status"] == "absent_confirmed"


# ---------------------------------------------------------------------------
# necessary-precondition tests
# ---------------------------------------------------------------------------

def test_if_c_then_must_a_is_not_necessary_precondition() -> None:
    result = check_object(_rule(REL_TRIGGER_OBLIGATION, condition="breach occurs"), _record())
    assert result["applicability"] == "not_applicable"
    assert result["reason"] == "trigger_obligation_not_necessary_precondition"


def test_condition_guard_blocks_all_paths() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data"), _activity("deny", "deny request")],
        gateways=[_gateway("g", "exclusiveGateway")],
        flows=[
            _flow("f1", "start", "g"),
            _flow("f2", "g", "a", condition="valid consent exists"),
            _flow("f3", "g", "deny", name="", condition=None),
            _flow("f4", "a", "end"),
            _flow("f5", "deny", "end"),
        ],
    )
    result = check_object(_rule(REL_NECESSARY_PRECONDITION, condition="valid consent exists"), record)
    assert result["decision"] == "satisfied"
    assert result["evidence"]["removed_condition_edge_ids"] == ["f2"]
    assert result["evidence"]["reachable_target_action_ids_after_removal"] == []


def test_condition_bypass_path_causes_violation() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data"), _activity("deny", "deny request")],
        gateways=[_gateway("g", "exclusiveGateway")],
        flows=[
            _flow("f1", "start", "g"),
            _flow("f2", "g", "a", condition="valid consent exists"),
            _flow("f3", "g", "deny"),
            _flow("f4", "a", "end"),
            _flow("f5", "deny", "end"),
            _flow("f6", "g", "a"),
        ],
    )
    result = check_object(_rule(REL_NECESSARY_PRECONDITION, condition="valid consent exists"), record)
    assert result["decision"] == "violation"
    assert result["evidence"]["bypass_evidence_path"]["node_ids"][0] == "start"
    assert "f2" in result["evidence"]["removed_condition_edge_ids"]


def test_condition_default_flow_bypass_causes_violation() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data")],
        gateways=[_gateway("g", "exclusiveGateway")],
        flows=[
            _flow("f1", "start", "g"),
            _flow("f2", "g", "a", condition="valid consent exists"),
            _flow("f3", "g", "a"),
            _flow("f4", "a", "end"),
        ],
    )
    # f3 is the default-flow bypass in the frozen mechanism case; the checker
    # treats it as an ordinary unguarded flow after E_C removal.
    result = check_object(_rule(REL_NECESSARY_PRECONDITION, condition="valid consent exists"), record)
    assert result["decision"] == "violation"


def test_condition_text_without_control_effect_does_not_satisfy() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data")],
        gateways=[_gateway("g", "exclusiveGateway", "valid consent exists")],
        flows=[_flow("f1", "start", "g"), _flow("f2", "g", "a"), _flow("f3", "a", "end")],
    )
    result = check_object(_rule(REL_NECESSARY_PRECONDITION, condition="valid consent exists"), record)
    assert result["decision"] == "violation"
    assert result["evidence"]["removed_condition_edge_ids"] == []


def test_unrelated_condition_does_not_satisfy() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data")],
        gateways=[_gateway("g", "exclusiveGateway", "valid consent exists")],
        flows=[
            _flow("f1", "start", "g"),
            _flow("f2", "g", "a", condition="request is authenticated"),
            _flow("f3", "a", "end"),
        ],
    )
    result = check_object(_rule(REL_NECESSARY_PRECONDITION, condition="valid consent exists"), record)
    assert result["decision"] == "violation"
    assert result["evidence"]["removed_condition_edge_ids"] == []


def test_and_loop_or_subprocess_is_unsupported() -> None:
    and_record = _record(
        activities=[_activity("a", "disclose personal data")],
        gateways=[_gateway("p", "parallelGateway")],
        flows=[_flow("f1", "start", "p"), _flow("f2", "p", "a"), _flow("f3", "a", "end")],
    )
    loop_record = _record(
        activities=[_activity("a", "disclose personal data")],
        flows=[_flow("f1", "start", "a"), _flow("f2", "a", "a")],
    )
    loop_record["control_flow"]["cycle_detected"] = True
    subprocess_record = _record(
        activities=[_activity("s", "disclose personal data", "subProcess")],
        flows=[_flow("f1", "start", "s"), _flow("f2", "s", "end")],
    )
    for record in (and_record, loop_record, subprocess_record):
        result = supported_bpmn_fragment(record)
        assert result["supported"] is False
        assert result["reason"].startswith("unsupported_bpmn_fragment:")


def test_unresolved_action_is_unknown_not_compliant() -> None:
    record = _record()
    result = check_object(
        _rule(REL_DIRECT_PROHIBITION, vocabulary=["some other canonical action"]),
        record,
    )
    assert result["applicability"] == "applicable"
    assert result["decision"] == "unknown"
    assert result["reason"] == "action_binding_unresolved_or_ambiguous"


# ---------------------------------------------------------------------------
# data isolation and replay
# ---------------------------------------------------------------------------

def _run_check(script: Path) -> None:
    result = subprocess.run([sys.executable, str(script), "--check"], cwd=ROOT, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_legacy_disposition_is_reproducible() -> None:
    _run_check(BUILD_LEGACY)


def test_mechanism_freeze_hashes_are_reproducible() -> None:
    _run_check(BUILD_MECHANISM)


def _walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_inference_view_contains_no_expected_pair_side_or_mutation_metadata() -> None:
    view = json.loads((MECH_DIR / "inference_view_v1.json").read_text(encoding="utf-8"))
    forbidden = {
        "expected", "expected_label", "expected_decision", "target_type",
        "mutation_type", "pair_id", "side", "control", "variant", "gold", "case_id",
    }
    seen = {key for key, _ in _walk(view)}
    assert not (seen & forbidden)
    assert len(view["objects"]) == 26
    manifest = json.loads((MECH_DIR / "mechanism_case_manifest_v1.json").read_text(encoding="utf-8"))
    assert len(manifest["objects"]) == 26
    assert manifest["pair_success_denominators"] == {"prohibition": 5, "necessary_precondition": 5, "total": 10}


def _load_evaluator_module():
    path = ROOT / "scripts/evaluate_s3_ext_pc_v1.py"
    spec = importlib.util.spec_from_file_location("s3_ext_pc_v1_evaluator", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_evaluator_reads_targets_only_after_prediction_freeze(tmp_path: Path) -> None:
    module = _load_evaluator_module()
    predictions = tmp_path / "predictions.jsonl"
    predictions.write_text('{"object_id":"x"}\n', encoding="utf-8")
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({
        "status": "PREDICTIONS_FROZEN_BEFORE_EVALUATION",
        "prediction_sha256": "not-the-real-hash",
    }), encoding="utf-8")
    def _explode():
        raise AssertionError("targets/manifest were read before prediction freeze verification")
    try:
        module.load_targets_after_prediction_freeze(predictions, freeze, _explode)
    except module.PredictionFreezeError as exc:
        assert "hash mismatch" in str(exc)
    else:
        raise AssertionError("expected PredictionFreezeError")


def test_deterministic_replay_byte_identical() -> None:
    record = _record(
        activities=[_activity("a", "disclose personal data")],
        flows=[_flow("f1", "start", "a"), _flow("f2", "a", "end")],
    )
    rule = _rule(REL_DIRECT_PROHIBITION)
    first = json.dumps(check_object(rule, record), ensure_ascii=False, sort_keys=True).encode("utf-8")
    second = json.dumps(check_object(rule, record), ensure_ascii=False, sort_keys=True).encode("utf-8")
    assert first == second

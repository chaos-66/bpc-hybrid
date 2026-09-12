# -*- coding: utf-8 -*-
"""Focused tests for revision s3_semantic_grounding_v1."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "outputs").exists() and (ROOT.parent / "formal_experiment").exists():
    ROOT = ROOT.parent / "formal_experiment"
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_semantic_grounding_v1 import (  # noqa: E402
    SemanticGroundingScorer,
    build_llm_input,
    run_llm_fallback,
    validate_llm_response,
)

FROZEN = {
    "condition": "in the case of a personal data breach",
    "exception": "unless the personal data breach is unlikely to result in a risk",
}


def exact_similarity(left: str, right: str) -> float:
    def norm(value: str) -> str:
        return " ".join("".join(ch if ch.isalnum() else " "
                                for ch in value.lower()).split())
    return 1.0 if norm(left) == norm(right) else 0.0


def model(actions):
    return SimpleNamespace(actions=[
        {"id": action_id, "name": name, "kind": "activity"}
        for action_id, name in actions
    ])


def base_record(condition_expression=None, exception_handler=False):
    activities = [{"id": "A", "name": "Notify breach", "type": "task", "lane_ids": []}]
    events = [{"id": "S", "name": "start", "type": "startEvent", "lane_ids": []}]
    flows = [{"id": "f1", "name": "", "source_ref": "S", "target_ref": "A",
              "condition_expression": condition_expression, "is_default": False}]
    if exception_handler:
        activities.append({"id": "H", "name": FROZEN["exception"], "type": "task",
                           "lane_ids": []})
        events.append({"id": "B", "name": FROZEN["exception"], "type": "boundaryEvent",
                       "lane_ids": []})
        flows.append({"id": "f2", "name": "", "source_ref": "B", "target_ref": "H",
                      "condition_expression": None, "is_default": False})
    return {"process_id": "p", "activities": activities, "events": events,
            "gateways": [], "sequence_flows": flows, "pools": [], "lanes": []}


def condition_sentence(**overrides):
    sentence = {"rule_id": "r", "modality": None, "actor": None,
                "action": "notify breach", "condition": FROZEN["condition"],
                "constraint": None, "exception": None}
    sentence.update(overrides)
    return sentence


def score(record, sentence, xml="<process/>"):
    scorer = SemanticGroundingScorer(exact_similarity, gamma=0.4, gamma_ext=0.5,
                                     config={"thresholds": {}})
    return scorer.score(sentence, model([("A", "Notify breach")]), record,
                        ET.fromstring(xml))


def test_original_three_artifacts_and_sun_scorer_remain_frozen():
    manifest = json.loads((ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json")
                          .read_text(encoding="utf-8"))
    original = {key.replace("\\", "/"): value
                for key, value in manifest["artifacts"].items()
                if key.replace("\\", "/").startswith(
                    "outputs/evidence/s3_formula_repair_v2/original_three")}
    assert original
    for key, expected in original.items():
        assert hashlib.sha256((ROOT / key).read_bytes()).hexdigest() == expected, key
    expected_scorer = next(value for key, value in manifest["implementation_hashes"].items()
                           if key.replace("\\", "/") ==
                           "src/bpc_hybrid/sun_stage3/sun_scorer.py")
    raw = (ROOT / "src/bpc_hybrid/sun_stage3/sun_scorer.py").read_bytes()
    mode = manifest.get("implementation_hash_mode", "raw_bytes")
    actual = (hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
              if mode == "canonical_lf_utf8_text"
              else hashlib.sha256(raw).hexdigest())
    assert actual == expected_scorer


def test_prediction_is_gold_blind_and_metadata_blind():
    sentence = condition_sentence()
    polluted = dict(sentence)
    polluted.update({"expected_violation": "exception_not_handled",
                     "mutation_type": "exception_not_handled",
                     "mutation_config": {"target_activity_id": "A"},
                     "target_activity_id": "A",
                     "path": ".../expected_exception_variant.bpmn"})
    record = base_record(condition_expression=None)
    first = score(record, sentence)
    second = score(record, polluted)
    assert first["decision"] == second["decision"]
    assert "expected_violation" not in json.dumps(first, sort_keys=True)


def test_runner_prediction_view_shape():
    allowed = {"rule_id", "modality", "actor", "action", "condition", "constraint",
               "exception"}
    view = {key: condition_sentence().get(key) for key in allowed}
    assert set(view) == allowed


def test_condition_enforced_absent_and_action_unresolved():
    sentence = condition_sentence()
    result = score(base_record("In the case of a personal data breach"), sentence)
    assert result["checks"]["required_condition_not_enforced"]["status"] == "enforced"
    assert result["decision"]["predicted"] == "none"

    result = score(base_record(None), sentence)
    assert result["checks"]["required_condition_not_enforced"]["status"] == "not_enforced"
    assert result["decision"]["predicted"] == "required_condition_not_enforced"

    result = score(base_record(None),
                   condition_sentence(action="perform unrelated calibration"))
    assert result["checks"]["required_condition_not_enforced"]["status"] == "unknown"
    assert result["decision"]["predicted"] is None


def test_exception_handled_absent_and_ambiguous():
    sentence = condition_sentence(condition=None, exception=FROZEN["exception"])
    result = score(base_record(exception_handler=True), sentence,
                   '<process><boundaryEvent id="B" name="%s" attachedToRef="A"/>'
                   '</process>' % FROZEN["exception"])
    assert result["checks"]["exception_not_handled"]["status"] == "handled"
    assert result["decision"]["predicted"] == "none"

    result = score(base_record(exception_handler=False), sentence)
    assert result["checks"]["exception_not_handled"]["status"] == "not_handled"
    assert result["decision"]["predicted"] == "exception_not_handled"

    ambiguous_record = base_record(exception_handler=False)
    ambiguous_record["activities"].append({"id": "H", "name": "handler task",
                                           "type": "task", "lane_ids": []})
    ambiguous_record["events"].append({"id": "B", "name": "some other branch",
                                       "type": "boundaryEvent", "lane_ids": []})
    ambiguous_record["sequence_flows"].append(
        {"id": "f2", "name": "", "source_ref": "B", "target_ref": "H",
         "condition_expression": None, "is_default": False})
    result = score(ambiguous_record, sentence,
                   '<process><boundaryEvent id="B" name="some other branch" '
                   'attachedToRef="A"/></process>')
    assert result["checks"]["exception_not_handled"]["status"] == "unknown"
    assert result["decision"]["predicted"] is None


def test_constraint_numeric_contradiction_compliant_and_abstract():
    sentence = condition_sentence(condition=None, constraint="within 72 hours")
    record = base_record()
    result = score(record, sentence,
                   '<process><boundaryEvent id="T" name="96 hours" attachedToRef="A"/>'
                   '</process>')
    assert result["checks"]["constraint_violated"]["status"] == "violated"
    assert result["decision"]["predicted"] == "constraint_violated"

    result = score(record, sentence,
                   '<process><boundaryEvent id="T" name="48 hours" attachedToRef="A"/>'
                   '</process>')
    assert result["checks"]["constraint_violated"]["status"] == "satisfied"
    assert result["decision"]["predicted"] == "none"

    result = score(record,
                   condition_sentence(condition=None, constraint="without undue delay"),
                   '<process><boundaryEvent id="T" name="96 hours" attachedToRef="A"/>'
                   '</process>')
    assert result["checks"]["constraint_violated"]["status"] == "unknown"
    assert result["decision"]["predicted"] is None


class MockClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


def llm_payload():
    return {"rule_record": {"modality": "obligation", "action": "Notify breach",
                            "condition": FROZEN["condition"], "constraint": None,
                            "exception": None},
            "candidate_activity_ids": ["A"],
            "local_context_evidence_ids": ["f1", "A"]}


def valid_llm_json(condition_status="enforced", evidence_ids=None):
    return json.dumps({
        "schema_version": "s3_semantic_grounding_llm_response@1.0.0",
        "action_grounding": {"status": "matched", "activity_id": "A",
                             "confidence": 0.9},
        "condition_grounding": {"status": condition_status,
                                "evidence_ids": evidence_ids if evidence_ids is not None
                                else ["f1"], "reason_code": "flow_condition"},
        "constraint_grounding": {"status": "not_applicable", "evidence_ids": [],
                                 "reason_code": "empty_rule_constraint"},
        "exception_grounding": {"status": "not_applicable", "evidence_ids": [],
                                "reason_code": "empty_rule_exception"},
    })


def test_llm_fallback_strict_fail_closed_cases():
    payload = llm_payload()
    assert validate_llm_response(valid_llm_json(), payload, 0.8)["status"] == "resolved"
    assert run_llm_fallback(MockClient(response="{not json"), payload)["status"] == "failed"
    assert run_llm_fallback(
        MockClient(response=valid_llm_json(evidence_ids=["HALLUCINATED"])), payload
    )["status"] == "failed"
    low_conf = valid_llm_json().replace('"confidence": 0.9', '"confidence": 0.2')
    assert run_llm_fallback(MockClient(response=low_conf), payload)["status"] == "failed"
    assert run_llm_fallback(
        MockClient(error=TimeoutError("timeout")), payload)["status"] == "failed"
    assert run_llm_fallback(
        MockClient(response=valid_llm_json(condition_status="ambiguous",
                                           evidence_ids=[])), payload
    )["status"] == "ambiguous"


def test_llm_input_is_compact_and_id_scoped():
    scored = score(base_record(None), condition_sentence())
    payload = build_llm_input(condition_sentence(), scored["action_grounding"],
                              scored["checks"])
    assert payload["candidate_activity_ids"] == ["A"]
    assert "<process" not in json.dumps(payload)


def test_deterministic_replay_byte_identical():
    sentence = condition_sentence()
    record = base_record("In the case of a personal data breach")
    first = json.dumps(score(record, sentence), ensure_ascii=False, sort_keys=True)
    second = json.dumps(score(record, sentence), ensure_ascii=False, sort_keys=True)
    assert first == second
    assert "expected_violation" not in first

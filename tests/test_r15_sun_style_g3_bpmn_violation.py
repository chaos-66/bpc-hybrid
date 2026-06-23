"""(G3) BPMN semantics and violation detection tests.

Coverage:
  G3.1 — BPMN parser parses XML string
  G3.2 — BPMN parser extracts activities
  G3.3 — BPMN parser extracts lanes
  G3.4 — ViolationDetector finds missing_action
  G3.5 — ViolationDetector finds incorrect_actor
  G3.6 — ViolationDetector finds out_of_order
"""

import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
# If running from tests/ under project root, this should be the project root.
# But pytest might resolve differently; fall back to relative path.
if not (_PROJECT_ROOT / "src" / "bpc_hybrid").exists():
    _PROJECT_ROOT = Path.cwd()
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from bpc_hybrid.sun_style.bpmn_semantics import BPMNSemanticParser
from bpc_hybrid.sun_style.rule_record import RuleRecord
from bpc_hybrid.sun_style.violation_detection import (
    ViolationDetector,
    ViolationType,
)

_FIXTURES = (
    _PROJECT_ROOT / "data" / "formal" / "r15_sun_style" / "fixtures"
)


def _load_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def test_g3_1_parse_xml_string():
    """G3.1 — BPMN parser parses an XML string."""
    xml_str = _load_fixture("minimal_bpmn_missing_action.bpmn")
    parser = BPMNSemanticParser()
    record = parser.parse_string(xml_str)
    assert record is not None
    assert record.process_id is not None
    print(f"  PASS G3.1 — parsed process: {record.process_id}")


def test_g3_2_extracts_activities():
    """G3.2 — BPMN parser extracts activities from minimal fixture."""
    xml_str = _load_fixture("minimal_bpmn_missing_action.bpmn")
    parser = BPMNSemanticParser()
    record = parser.parse_string(xml_str)
    assert len(record.activities) > 0, "No activities found"
    print(f"  PASS G3.2 — activities: {record.activity_names}")


def test_g3_3_extracts_lanes():
    """G3.3 — BPMN parser extracts lanes."""
    xml_str = _load_fixture("minimal_bpmn_incorrect_actor.bpmn")
    parser = BPMNSemanticParser()
    record = parser.parse_string(xml_str)
    assert len(record.lanes) > 0, "No lanes found"
    print(f"  PASS G3.3 — lanes: {record.lane_names}")


def test_g3_4_missing_action_violation():
    """G3.4 — ViolationDetector finds missing_action."""
    xml_str = _load_fixture("minimal_bpmn_missing_action.bpmn")
    parser = BPMNSemanticParser()
    process = parser.parse_string(xml_str)

    # Rule says "record the decision" but BPMN has "Notify data subject"
    rule = RuleRecord(
        sample_id="test_missing",
        source_text="The controller shall record the decision.",
        prediction_fields={
            "modality": {"value": "obligation"},
            "actor": {"value": "controller"},
            "action": {"value": "record the decision"},
            "condition": {"value": ""},
            "constraint": {"value": ""},
            "exception": {"value": ""},
        },
    )

    detector = ViolationDetector()
    report = detector.detect(rule, process)
    violation_types = {v.violation_type for v in report.violations}
    assert ViolationType.MISSING_ACTION in violation_types, (
        f"Expected missing_action, got: {violation_types}"
    )
    print(f"  PASS G3.4 — detected missing_action")


def test_g3_5_incorrect_actor_violation():
    """G3.5 — ViolationDetector finds incorrect_actor."""
    xml_str = _load_fixture("minimal_bpmn_incorrect_actor.bpmn")
    parser = BPMNSemanticParser()
    process = parser.parse_string(xml_str)

    # Rule says "Controller shall record" but BPMN has "Processor" lane
    rule = RuleRecord(
        sample_id="test_actor",
        source_text="The controller shall record the decision.",
        prediction_fields={
            "modality": {"value": "obligation"},
            "actor": {"value": "controller"},
            "action": {"value": "record the decision"},
            "condition": {"value": ""},
            "constraint": {"value": ""},
            "exception": {"value": ""},
        },
    )

    detector = ViolationDetector()
    report = detector.detect(rule, process)
    violation_types = {v.violation_type for v in report.violations}
    assert ViolationType.INCORRECT_ACTOR in violation_types, (
        f"Expected incorrect_actor, got: {violation_types}"
    )
    print(f"  PASS G3.5 — detected incorrect_actor")


def test_g3_6_out_of_order_violation():
    """G3.6 — ViolationDetector finds out_of_order."""
    xml_str = _load_fixture("minimal_bpmn_out_of_order.bpmn")
    parser = BPMNSemanticParser()
    process = parser.parse_string(xml_str)

    # BPMN has "Notify data subject" then "Record decision"
    # Rule says "Record decision before Notify data subject" -> out of order
    rule = RuleRecord(
        sample_id="test_order",
        source_text="The controller shall record decision before notify data subject.",
        prediction_fields={
            "modality": {"value": "obligation"},
            "actor": {"value": "controller"},
            "action": {"value": "record decision"},
            "condition": {"value": ""},
            "constraint": {"value": ""},
            "exception": {"value": ""},
        },
    )

    detector = ViolationDetector()
    report = detector.detect(rule, process)
    violation_types = {v.violation_type for v in report.violations}
    assert ViolationType.OUT_OF_ORDER in violation_types, (
        f"Expected out_of_order, got: {violation_types}, violations: "
        f"{[v.description for v in report.violations]}"
    )
    print(f"  PASS G3.6 — detected out_of_order (violations: {violation_types})")


def main():
    print("=== G3: BPMN & Violation Tests ===")
    test_g3_1_parse_xml_string()
    test_g3_2_extracts_activities()
    test_g3_3_extracts_lanes()
    test_g3_4_missing_action_violation()
    test_g3_5_incorrect_actor_violation()
    test_g3_6_out_of_order_violation()
    print("G3: All passed.\n")


if __name__ == "__main__":
    main()

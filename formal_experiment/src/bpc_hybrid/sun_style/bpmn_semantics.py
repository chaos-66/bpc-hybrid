"""Sun-style BPMN process model semantic disassembly (R15.0).

Parses BPMN 2.0 XML to extract process semantic records, including:
- activities (tasks)
- events (start, end, intermediate)
- gateways
- actor/resource (from lanes)
- control flow (sequence flows)
- label action/object semantics (from task names)

Uses only ``xml.etree.ElementTree`` (Python stdlib).

This is a scaffold implementation.  It does NOT reproduce Sun's
original BPMN compliance benchmark due to missing original datasets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# BPMN namespace
# ---------------------------------------------------------------------------

_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_BPMN = f"{{{_BPMN_NS}}}"


def _tag(local: str) -> str:
    """Return a fully qualified BPMN tag name."""
    return f"{_BPMN}{local}"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class BPMNActivity:
    """A BPMN activity (task)."""

    id: str
    name: str
    activity_type: str = "task"  # task, subProcess, etc.


@dataclass
class BPMNEvent:
    """A BPMN event."""

    id: str
    name: str
    event_type: str  # startEvent, endEvent, intermediateCatchEvent, etc.


@dataclass
class BPMNGateway:
    """A BPMN gateway."""

    id: str
    name: str
    gateway_type: str  # exclusiveGateway, parallelGateway, etc.


@dataclass
class BPMNLane:
    """A BPMN lane representing an actor/resource."""

    id: str
    name: str
    flow_node_refs: list[str] = field(default_factory=list)


@dataclass
class BPMNSequenceFlow:
    """A BPMN sequence flow."""

    id: str
    source_ref: str
    target_ref: str


@dataclass
class ProcessSemanticRecord:
    """Semantic record extracted from a BPMN process model.

    Corresponds to Sun et al.'s process semantic extraction.
    """

    process_id: str
    activities: list[BPMNActivity] = field(default_factory=list)
    events: list[BPMNEvent] = field(default_factory=list)
    gateways: list[BPMNGateway] = field(default_factory=list)
    lanes: list[BPMNLane] = field(default_factory=list)
    sequence_flows: list[BPMNSequenceFlow] = field(default_factory=list)

    @property
    def activity_names(self) -> list[str]:
        """All activity (task) names (lowercased)."""
        return [a.name.lower() for a in self.activities]

    @property
    def lane_names(self) -> list[str]:
        """All lane names (lowercased)."""
        return [ln.name.lower() for ln in self.lanes]

    def task_order(self) -> list[str]:
        """Derive task execution order from sequence flows (topological)."""
        # Build adjacency
        successors: dict[str, list[str]] = {}
        for sf in self.sequence_flows:
            successors.setdefault(sf.source_ref, []).append(sf.target_ref)

        # Find start events
        start_ids = {e.id for e in self.events if e.event_type == "startEvent"}

        # BFS from start events
        order: list[str] = []
        visited: set[str] = set()
        queue: list[str] = list(start_ids)

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            # Check if this is an activity
            for act in self.activities:
                if act.id == node_id:
                    order.append(act.name.lower())

            for succ in successors.get(node_id, []):
                if succ not in visited:
                    queue.append(succ)

        return order


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class BPMNSemanticParser:
    """Parse BPMN 2.0 XML and produce ProcessSemanticRecord.

    Usage::

        >>> parser = BPMNSemanticParser()
        >>> record = parser.parse_file("model.bpmn")
        >>> print(record.activity_names)
    """

    def parse_file(self, path: str | Path) -> ProcessSemanticRecord:
        """Parse a BPMN XML file and return a semantic record."""
        tree = ET.parse(str(path))
        return self.parse_tree(tree)

    def parse_string(self, xml_string: str) -> ProcessSemanticRecord:
        """Parse a BPMN XML string and return a semantic record."""
        root = ET.fromstring(xml_string)
        return self._parse_root(root)

    def parse_tree(self, tree: ET.ElementTree) -> ProcessSemanticRecord:
        """Parse an ElementTree and return a semantic record."""
        return self._parse_root(tree.getroot())

    def _parse_root(self, root: ET.Element) -> ProcessSemanticRecord:
        """Parse from an Element root."""
        # Find the process element
        process = root.find(f".//{_tag('process')}")
        if process is None:
            # Try without namespace
            process = root.find(".//process")
        if process is None:
            raise ValueError("No BPMN process element found")

        process_id = process.get("id", "unknown")

        # Parse sub-elements
        record = ProcessSemanticRecord(process_id=process_id)

        record.activities = self._parse_activities(process)
        record.events = self._parse_events(process)
        record.gateways = self._parse_gateways(process)
        record.lanes = self._parse_lanes(process)
        record.sequence_flows = self._parse_sequence_flows(process)

        return record

    # ------------------------------------------------------------------
    # Sub-parsers
    # ------------------------------------------------------------------

    def _parse_activities(self, process: ET.Element) -> list[BPMNActivity]:
        activities: list[BPMNActivity] = []
        for tag_name in ["task", "userTask", "serviceTask", "sendTask",
                         "receiveTask", "manualTask", "businessRuleTask",
                         "scriptTask", "subProcess", "callActivity"]:
            for elem in process.findall(f".//{_tag(tag_name)}"):
                activities.append(BPMNActivity(
                    id=elem.get("id", ""),
                    name=elem.get("name", ""),
                    activity_type=tag_name,
                ))
        # Also try without namespace
        if not activities:
            for elem in process.findall(".//task"):
                activities.append(BPMNActivity(
                    id=elem.get("id", ""),
                    name=elem.get("name", ""),
                    activity_type="task",
                ))
        return activities

    def _parse_events(self, process: ET.Element) -> list[BPMNEvent]:
        events: list[BPMNEvent] = []
        for tag_name in ["startEvent", "endEvent", "intermediateCatchEvent",
                         "intermediateThrowEvent", "boundaryEvent"]:
            for elem in process.findall(f".//{_tag(tag_name)}"):
                events.append(BPMNEvent(
                    id=elem.get("id", ""),
                    name=elem.get("name", ""),
                    event_type=tag_name,
                ))
        # Fallback without namespace
        if not events:
            for elem in process.findall(".//startEvent"):
                events.append(BPMNEvent(
                    id=elem.get("id", ""), name=elem.get("name", ""),
                    event_type="startEvent",
                ))
            for elem in process.findall(".//endEvent"):
                events.append(BPMNEvent(
                    id=elem.get("id", ""), name=elem.get("name", ""),
                    event_type="endEvent",
                ))
        return events

    def _parse_gateways(self, process: ET.Element) -> list[BPMNGateway]:
        gateways: list[BPMNGateway] = []
        for tag_name in ["exclusiveGateway", "parallelGateway",
                         "inclusiveGateway", "complexGateway",
                         "eventBasedGateway"]:
            for elem in process.findall(f".//{_tag(tag_name)}"):
                gateways.append(BPMNGateway(
                    id=elem.get("id", ""),
                    name=elem.get("name", ""),
                    gateway_type=tag_name,
                ))
        return gateways

    def _parse_lanes(self, process: ET.Element) -> list[BPMNLane]:
        lanes: list[BPMNLane] = []
        for elem in process.findall(f".//{_tag('lane')}"):
            refs = [
                ref.text or ""
                for ref in elem.findall(f"{_tag('flowNodeRef')}")
            ]
            lanes.append(BPMNLane(
                id=elem.get("id", ""),
                name=elem.get("name", ""),
                flow_node_refs=refs,
            ))
        # Fallback without namespace
        if not lanes:
            for elem in process.findall(".//lane"):
                refs = [ref.text or "" for ref in elem.findall("flowNodeRef")]
                lanes.append(BPMNLane(
                    id=elem.get("id", ""), name=elem.get("name", ""),
                    flow_node_refs=refs,
                ))
        return lanes

    def _parse_sequence_flows(self, process: ET.Element) -> list[BPMNSequenceFlow]:
        flows: list[BPMNSequenceFlow] = []
        for elem in process.findall(f".//{_tag('sequenceFlow')}"):
            flows.append(BPMNSequenceFlow(
                id=elem.get("id", ""),
                source_ref=elem.get("sourceRef", ""),
                target_ref=elem.get("targetRef", ""),
            ))
        # Fallback
        if not flows:
            for elem in process.findall(".//sequenceFlow"):
                flows.append(BPMNSequenceFlow(
                    id=elem.get("id", ""),
                    source_ref=elem.get("sourceRef", ""),
                    target_ref=elem.get("targetRef", ""),
                ))
        return flows

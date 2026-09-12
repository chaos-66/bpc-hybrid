# -*- coding: utf-8 -*-
"""Deterministic BPMN transforms for the SIM case (S3.9-EXT-REAL-CASE).

Two declared, group-independent transforms:

``flatten_collaboration``
    The frozen Stage 1 parser accepts exactly one ``<process>`` per file, while
    the SIM model is a three-participant collaboration (Customer / Phone company
    / Another phone company).  The transform merges the three processes into one
    process and represents each original participant as a **named lane**, so
    actor attribution survives.  Element ids, sequence flows, gateways, events
    and the diagram section are kept unchanged.  This adaptation is applied
    identically to the original model and to every repair variant; it is
    recorded with hashes and is NOT answer-informed.

``repair_variant``
    Minimal development control models, one per expressible rule issue.  Each
    repair changes only the declared issue and is fixed before any run.  The
    original file is never modified; repaired XML is produced in memory and
    written only to a gitignored local directory.

Both transforms are pure functions over XML text.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"

FLOW_NODE_TAGS = {
    "task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
    "scriptTask", "businessRuleTask", "callActivity", "subProcess",
    "exclusiveGateway", "parallelGateway", "inclusiveGateway", "eventBasedGateway",
    "complexGateway", "startEvent", "endEvent", "intermediateCatchEvent",
    "intermediateThrowEvent", "boundaryEvent",
}


def _tag(elem) -> str:
    return elem.tag.split("}")[1]


def _q(local: str, ns: str = BPMN_NS) -> str:
    return f"{{{ns}}}{local}"


def register_namespaces() -> None:
    ET.register_namespace("bpmn", BPMN_NS)
    ET.register_namespace("bpmndi", BPMNDI_NS)
    ET.register_namespace("xsi", XSI_NS)


def flatten_collaboration(payload: bytes) -> tuple[bytes, dict[str, Any]]:
    """Merge all processes into one process; one named lane per participant."""
    register_namespaces()
    root = ET.fromstring(payload)
    processes = [e for e in root if _tag(e) == "process"]
    if not processes:
        raise ValueError("no process element")

    participant_name: dict[str, str] = {}
    for collab in [e for e in root if _tag(e) == "collaboration"]:
        for participant in [c for c in collab if _tag(c) == "participant"]:
            participant_name[participant.get("processRef")] = participant.get("name") or participant.get("id")

    merged = ET.Element(_q("process"), {"id": "sim_flat_process", "name": "SIM card scenario (flattened)",
                                        "isExecutable": "false"})
    lane_set = ET.SubElement(merged, _q("laneSet"), {"id": "sim_flat_lanes"})
    lane_report = []
    moved = 0
    for process in processes:
        pid = process.get("id")
        lane_name = participant_name.get(pid) or process.get("name") or pid
        existing_lanes = [lane for lane_set_el in process if _tag(lane_set_el) == "laneSet"
                          for lane in lane_set_el if _tag(lane) == "lane"]
        covered: set[str] = set()
        for lane in existing_lanes:
            new_lane = ET.SubElement(lane_set, _q("lane"),
                                     {"id": f"sim_flat_{lane.get('id')}",
                                      "name": (lane.get("name") or lane_name or "")})
            count = 0
            for ref in lane:
                if _tag(ref) != "flowNodeRef":
                    continue
                node_id = (ref.text or "").strip()
                if not node_id:
                    continue
                covered.add(node_id)
                new_ref = ET.SubElement(new_lane, _q("flowNodeRef"))
                new_ref.text = node_id
                count += 1
            lane_report.append({"lane": new_lane.get("name"), "process": pid, "nodes": count,
                                "source": "preserved_lane"})
        refs = []
        for child in list(process):
            if _tag(child) in FLOW_NODE_TAGS:
                refs.append(child.get("id"))
                merged.append(child)
                moved += 1
            elif _tag(child) in ("sequenceFlow", "dataObject", "dataObjectReference",
                                 "dataStoreReference", "textAnnotation", "association",
                                 "extensionElements"):
                merged.append(child)
        leftover = [element_id for element_id in refs if element_id not in covered]
        if leftover:
            fallback = ET.SubElement(lane_set, _q("lane"),
                                     {"id": f"sim_flat_lane_{pid}", "name": lane_name or ""})
            for element_id in leftover:
                ref = ET.SubElement(fallback, _q("flowNodeRef"))
                ref.text = element_id
            lane_report.append({"lane": lane_name, "process": pid, "nodes": len(leftover),
                                "source": "fallback_for_unlaned_nodes"})

    for process in processes:
        root.remove(process)
    # Drop the collaboration wrapper: pool-level ownership would attribute every
    # merged task to every participant, destroying lane-based actor attribution.
    # Participant names are preserved as lane names, so actor information is kept.
    collab = next((e for e in root if _tag(e) == "collaboration"), None)
    if collab is not None:
        root.remove(collab)
    root.insert(0, merged)

    info = {
        "transform": "flatten_collaboration_v2",
        "reason": "frozen Stage 1 parser accepts exactly one process; SIM model is a 3-participant collaboration",
        "participants": [participant_name.get(p.get("id")) for p in processes],
        "lanes": lane_report,
        "flow_nodes_merged": moved,
        "ids_preserved": True,
        "collaboration_wrapper": "removed (participant names kept as lane names; pool-level ownership would "
                                 "attribute every task to every participant)",
    }
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), info


def _find(root, local: str, element_id: str):
    for elem in root.iter():
        if _tag(elem) == local and elem.get("id") == element_id:
            return elem
    return None


def _flow(root, flow_id: str):
    return _find(root, "sequenceFlow", flow_id)


def _lane_of(root, node_id: str):
    for lane in root.iter():
        if _tag(lane) != "lane":
            continue
        for ref in lane:
            if _tag(ref) == "flowNodeRef" and (ref.text or "").strip() == node_id:
                return lane
    return None


def _first_flow_into(root, target_id: str):
    for flow in root.iter():
        if _tag(flow) == "sequenceFlow" and flow.get("targetRef") == target_id:
            return flow
    return None


def _first_flow_out_of(root, source_id: str):
    for flow in root.iter():
        if _tag(flow) == "sequenceFlow" and flow.get("sourceRef") == source_id:
            return flow
    return None


def repair_variant(payload: bytes, repair_id: str) -> tuple[bytes, dict[str, Any]]:
    """Apply one minimal, pre-declared repair to an already flattened model."""
    register_namespaces()
    root = ET.fromstring(payload)
    process = next(e for e in root if _tag(e) == "process")
    detail: dict[str, Any] = {"repair_id": repair_id, "operations": []}

    if repair_id == "r8_timeout_termination":
        # Canonical process-level timeout: a process-level event subprocess
        # whose interrupting timer starts when the process instance starts and
        # whose terminate end event terminates the process instance.
        sub = ET.SubElement(process, _q("subProcess"), {
            "id": "sim_fix_process_timeout_scope",
            "name": "Process-wide timeout scope (30 days)",
            "triggeredByEvent": "true",
        })
        start_event = ET.SubElement(sub, _q("startEvent"), {
            "id": "sim_fix_process_timeout_start",
            "name": "Process duration exceeds 30 days",
            "isInterrupting": "true",
        })
        timer = ET.SubElement(start_event, _q("timerEventDefinition"))
        duration = ET.SubElement(timer, _q("timeDuration"))
        duration.text = "P30D"
        end_event = ET.SubElement(sub, _q("endEvent"), {
            "id": "sim_fix_process_timeout_end",
            "name": "Terminate entire process",
        })
        ET.SubElement(end_event, _q("terminateEventDefinition"))
        flow = ET.SubElement(sub, _q("sequenceFlow"), {
            "id": "sim_fix_process_timeout_flow",
            "sourceRef": start_event.get("id"),
            "targetRef": end_event.get("id"),
        })
        detail["operations"] = [
            {"op": "add_process_level_event_subprocess", "id": sub.get("id"),
             "triggered_by_event": True},
            {"op": "add_interrupting_timer_start", "id": start_event.get("id"),
             "duration": "P30D", "scope": "process_instance"},
            {"op": "add_terminate_end", "id": end_event.get("id"),
             "termination_scope": "process_instance"},
            {"op": "add_sequence_flow", "id": flow.get("id"),
             "source": start_event.get("id"), "target": end_event.get("id")},
        ]
        detail["semantic_zh"] = (
            "增加进程级事件子流程：30 天计时从流程实例启动时开始，超时中断并触发"
            "终止整个流程实例。"
        )

    elif repair_id == "r9_add_verification":
        anchor = None
        for elem in process.iter():
            if _tag(elem) == "task" and (elem.get("name") or "") == "Sign contract":
                anchor = elem
                break
        if anchor is None:
            raise ValueError("anchor task not found")
        incoming = _first_flow_into(root, anchor.get("id"))
        if incoming is None:
            raise ValueError("no incoming flow")
        task = ET.SubElement(process, _q("task"),
                             {"id": "sim_fix_verify_correctness",
                              "name": "Verify correctness of customer personal data"})
        incoming.set("targetRef", task.get("id"))
        flow = ET.SubElement(process, _q("sequenceFlow"),
                             {"id": "sim_fix_verify_flow", "sourceRef": task.get("id"),
                              "targetRef": anchor.get("id")})
        lane = _lane_of(root, anchor.get("id"))
        if lane is not None:
            ref = ET.SubElement(lane, _q("flowNodeRef"))
            ref.text = task.get("id")
        detail["operations"] = [
            {"op": "add_task", "id": task.get("id"), "insert_before": anchor.get("id")},
            {"op": "rewire_flow", "flow": incoming.get("id"), "new_target": task.get("id")},
        ]
        detail["semantic_zh"] = "在 Sign contract 之前插入核验个人信息正确性的活动"

    elif repair_id == "r10_activation_owner":
        target = None
        for elem in process.iter():
            if _tag(elem) == "task" and (elem.get("name") or "") == "Activate SIM card":
                target = elem
                break
        if target is None:
            raise ValueError("target task not found")
        old_lane = _lane_of(root, target.get("id"))
        new_lane = None
        for lane in process.iter():
            if _tag(lane) == "lane" and (lane.get("name") or "").strip() == "Phone company":
                new_lane = lane
                break
        if new_lane is None:
            raise ValueError("Phone company lane not found")
        if old_lane is not None:
            for ref in list(old_lane):
                if _tag(ref) == "flowNodeRef" and (ref.text or "").strip() == target.get("id"):
                    old_lane.remove(ref)
        ref = ET.SubElement(new_lane, _q("flowNodeRef"))
        ref.text = target.get("id")
        detail["operations"] = [{"op": "move_node_between_lanes", "node": target.get("id"),
                                 "from": old_lane.get("name") if old_lane is not None else None,
                                 "to": "Phone company"}]
        detail["semantic_zh"] = "把 Activate SIM card 的归属从 Customer 改为 Phone company"

    elif repair_id == "r11_consent_before_retrieval":
        consent = None
        retrieval = None
        for elem in process.iter():
            name = elem.get("name") or ""
            if _tag(elem) == "task" and name == "Ask for consent":
                consent = elem
            if _tag(elem) == "task" and name == "Request personal data":
                retrieval = elem
        if consent is None or retrieval is None:
            raise ValueError("consent or retrieval task not found")
        into_retrieval = _first_flow_into(root, retrieval.get("id"))
        into_consent = _first_flow_into(root, consent.get("id"))
        out_of_consent = _first_flow_out_of(root, consent.get("id"))
        if None in (into_retrieval, into_consent, out_of_consent):
            raise ValueError("consent wiring incomplete")
        # 1. whatever used to enter retrieval now enters consent
        into_retrieval.set("targetRef", consent.get("id"))
        # 2. consent now proceeds to retrieval (new flow)
        new_flow = ET.SubElement(process, _q("sequenceFlow"),
                                 {"id": "sim_fix_consent_to_retrieval",
                                  "sourceRef": consent.get("id"), "targetRef": retrieval.get("id")})
        # 3. the old "Store Data -> consent" edge disappears
        store_source = into_consent.get("sourceRef")
        process.remove(into_consent)
        # 4. consent's old successor edge is repurposed as Store Data -> its former target
        out_of_consent.set("sourceRef", store_source)
        detail["operations"] = [
            {"op": "rewire_flow", "flow": into_retrieval.get("id"), "new_target": consent.get("id")},
            {"op": "add_sequence_flow", "id": new_flow.get("id"),
             "source": consent.get("id"), "target": retrieval.get("id")},
            {"op": "remove_sequence_flow", "flow": into_consent.get("id"),
             "was": f"{store_source} -> {consent.get('id')}"},
            {"op": "rewire_flow", "flow": out_of_consent.get("id"),
             "new_source": store_source, "unchanged_target": out_of_consent.get("targetRef")},
        ]
        detail["semantic_zh"] = "把同意活动移到取数之前（同意 -> 取数），并恢复 Store Data 的原后继路径"

    elif repair_id == "r13_threshold_50":
        label_flow = None
        for flow in process.iter():
            if _tag(flow) == "sequenceFlow" and (flow.get("name") or "") == "Debt < 100":
                label_flow = flow
                break
        if label_flow is None:
            raise ValueError("debt condition flow not found")
        label_flow.set("name", "Debt <= 50")
        detail["operations"] = [{"op": "relabel_sequence_flow", "flow": label_flow.get("id"),
                                 "from": "Debt < 100", "to": "Debt <= 50"}]
        detail["semantic_zh"] = "把路由条件标签改为 Debt <= 50，使欠款超过 50 的客户被排除"

    else:
        raise ValueError(f"unknown repair id {repair_id!r}")

    detail["original_unmodified"] = True
    detail["constructed_by"] = "programmatic minimal repair (development control), not an author model"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), detail


def repair_variant_r8_task_scoped_legacy(payload: bytes) -> tuple[bytes, dict[str, Any]]:
    """Preserve the rejected task-scoped r8 control as partial/invalid evidence.

    This is the precursor that attached a timer only to ``Send SIM card``.  It
    is retained for comparison, is never counted as an effective repair
    control, and is not used by the main run as the r8 repair.
    """
    register_namespaces()
    root = ET.fromstring(payload)
    process = next(e for e in root if _tag(e) == "process")
    detail: dict[str, Any] = {"repair_id": "r8_timeout_termination_task_scoped_legacy",
                              "operations": []}
    anchor = None
    for elem in process.iter():
        if _tag(elem) == "task" and (elem.get("name") or "") == "Send SIM card":
            anchor = elem
            break
    if anchor is None:
        raise ValueError("anchor task not found")
    boundary = ET.SubElement(process, _q("boundaryEvent"),
                             {"id": "sim_fix_timeout_boundary_legacy", "name": "30 days exceeded",
                              "attachedToRef": anchor.get("id"), "cancelActivity": "true"})
    timer = ET.SubElement(boundary, _q("timerEventDefinition"))
    duration = ET.SubElement(timer, _q("timeDuration"))
    duration.text = "P30D"
    end = ET.SubElement(process, _q("endEvent"), {"id": "sim_fix_timeout_end_legacy",
                                                   "name": "Process terminated"})
    flow = ET.SubElement(process, _q("sequenceFlow"),
                         {"id": "sim_fix_timeout_flow_legacy", "sourceRef": boundary.get("id"),
                          "targetRef": end.get("id")})
    lane = _lane_of(root, anchor.get("id"))
    if lane is not None:
        ref = ET.SubElement(lane, _q("flowNodeRef"))
        ref.text = boundary.get("id")
    detail["operations"] = [
        {"op": "add_boundary_timer", "attached_to": anchor.get("id"), "duration": "P30D",
         "scope": "task_scoped"},
        {"op": "add_end_event", "id": end.get("id")},
        {"op": "add_sequence_flow", "id": flow.get("id")},
    ]
    detail["semantic_zh"] = "旧版修复：仅在 Send SIM card 任务上挂 30 天边界计时器。"
    detail["original_unmodified"] = True
    detail["constructed_by"] = "legacy task-scoped development control (partial/invalid)"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), detail

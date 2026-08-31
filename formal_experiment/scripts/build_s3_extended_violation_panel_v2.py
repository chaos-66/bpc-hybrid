# -*- coding: utf-8 -*-
"""S3.9-EXT synthetic controlled-error extension v2 generator (zero API).

Produces a separate, explicitly-labelled development-only panel of 40
controlled mutations over the frozen GDPR-7 BPMN membership
(``synthetic_controlled_error_extension_v2``), adding FOUR new violation
categories (10 each) on top of the v1 three-type panel:

* prohibited_action_present      — a task whose label is the locked rule action
  of a prohibition sentence is inserted into a chain position (control = frozen
  BPMN, which lacks the prohibited action);
* required_condition_not_enforced — a conditionExpression carrying the locked
  rule condition is added to the incoming flow of the affinity activity in the
  CONTROL; the variant removes it;
* constraint_violated            — three sub-kinds: (a) annotation evidence
  (textAnnotation with the locked constraint phrase, removed in the variant),
  (b) data-object evidence (dataObject named with the constraint phrase,
  removed in the variant), (c) timer contradiction (the frozen gdpr_1 timer
  start event "72 hours" is renamed to a conflicting value in the variant;
  control == frozen bytes);
* exception_not_handled          — two sub-kinds: (a) boundary-event handler
  (boundaryEvent + errorEventDefinition + handler task labelled with the
  locked exception clause, removed in the variant), (b) alternate-branch
  handler (new gateway/activity outgoing branch to a handler task, removed in
  the variant).

Discipline (mirrors the v1 builder):

* The frozen GDPR-7 BPMN files are never modified (byte-unchanged check against
  the recorded source hashes; only the source bytes are copied into the
  development synthetic directory for controls/variants).
* The 40-item plan (rule, sentence, process, sub-kind, anchor) is LOCKED in
  this generator BEFORE any Stage 3 method runs; no result-driven selection.
* Every variant must: parse as XML; pass the frozen structural parser; keep the
  source bytes untouched; differ from its control in exactly one targeted
  dimension; keep non-target activities, lanes, labels and order relations
  unchanged; replay byte-identically.
* The panel is NOT human Gold and must never be merged into the 33-item
  human-adjudicated violation Gold nor presented as the formal Oracle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import spacy  # noqa: E402

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_bytes,
    validate_process_record,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    extract_six_element_sentences,
)

BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
MEMBERSHIP_CONTRACT = ROOT / "configs/datasets/stage1_stage3_gdpr7_v1.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
EXTENSION_CONFIG = ROOT / "configs/stage3_extended_violation_v2.json"
OUTPUT_DIR = ROOT / "data/development/stage3_synth"
MANIFEST = OUTPUT_DIR / "synthetic_controlled_error_extension_v2.json"

NS_BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
SCHEMA_VERSION = "s3_synthetic_controlled_error_extension@2.0.0"

SHORT_TYPE = {
    "prohibited_action_present": "prohibited_action",
    "required_condition_not_enforced": "required_condition",
    "constraint_violated": "constraint_violated",
    "exception_not_handled": "exception_not_handled",
}


class MutationError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _elements(root: ET.Element) -> list[ET.Element]:
    return list(root.iter())


def _parent_of(root: ET.Element, child: ET.Element) -> ET.Element | None:
    for el in root.iter():
        if any(c is child for c in list(el)):
            return el
    return None


def _structural(record: Mapping[str, Any]) -> dict[str, Any]:
    """Process Record without provenance fields (source/method) — used to
    compare process STRUCTURE between source/control/variant."""
    return {
        "pools": record["pools"],
        "lanes": record["lanes"],
        "activities": record["activities"],
        "events": record["events"],
        "gateways": record["gateways"],
        "sequence_flows": record["sequence_flows"],
        "control_flow": record["control_flow"],
    }


def _node_by_id(root: ET.Element, node_id: str) -> ET.Element | None:
    for el in root.iter():
        if el.get("id") == node_id:
            return el
    return None


def _process_element(root: ET.Element) -> ET.Element:
    processes = [el for el in root.iter() if _local(el.tag) == "process"]
    if len(processes) != 1:
        raise MutationError("BPMN must contain exactly one process")
    return processes[0]


def _definitions_element(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if _local(el.tag) == "definitions":
            return el
    raise MutationError("no definitions element")


# ---------------------------------------------------------------------------
# Affinity target (deterministic, backend-independent, frozen-data only)
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _prefix_stem(word: str) -> str:
    word = word.lower()
    return word[:4] if len(word) >= 4 else word


def _affinity_target(action_text: str, record: Mapping[str, Any]) -> str | None:
    """Activity (by id) with the maximum prefix-stem token overlap with the
    rule action; ties resolved by ascending id.  None when no overlap."""
    action_tokens = {_prefix_stem(t) for t in _TOKEN_RE.findall(action_text or "")}
    best_count = 0
    best_id: str | None = None
    for act in record["activities"]:
        label = act["name"] or ""
        label_tokens = {_prefix_stem(t) for t in _TOKEN_RE.findall(label)}
        overlap = len(action_tokens & label_tokens)
        if overlap > best_count:
            best_count = overlap
            best_id = act["id"]
    return best_id if best_count > 0 else None


def _chain_activities(record: Mapping[str, Any]) -> list[str]:
    """Activities with exactly one incoming and one outgoing flow, id-sorted."""
    in_count: dict[str, int] = {}
    out_count: dict[str, int] = {}
    for flow in record["sequence_flows"]:
        out_count[flow["source_ref"]] = out_count.get(flow["source_ref"], 0) + 1
        in_count[flow["target_ref"]] = in_count.get(flow["target_ref"], 0) + 1
    return [
        act["id"] for act in record["activities"]
        if in_count.get(act["id"], 0) == 1 and out_count.get(act["id"], 0) == 1
    ]


def _first_gateway_with_outgoing(record: Mapping[str, Any]) -> str | None:
    gateway_ids = {g["id"] for g in record["gateways"]}
    for flow in record["sequence_flows"]:
        if flow["source_ref"] in gateway_ids:
            return flow["source_ref"]
    return None


def _first_end_event(record: Mapping[str, Any]) -> str | None:
    ends = [e["id"] for e in record["events"] if e["type"] == "endEvent"]
    return ends[0] if ends else None


def _incoming_flow(record: Mapping[str, Any], activity_id: str) -> dict[str, Any] | None:
    candidates = [f for f in record["sequence_flows"] if f["target_ref"] == activity_id]
    return candidates[0] if candidates else None


def _flow_element(root: ET.Element, flow_id: str) -> ET.Element:
    el = _node_by_id(root, flow_id)
    if el is None:
        raise MutationError(f"flow {flow_id} not found")
    return el


# ---------------------------------------------------------------------------
# XML mutations
# ---------------------------------------------------------------------------


def _insert_chain_task(root: ET.Element, anchor_id: str, task_id: str,
                       task_name: str, flow_new_1: str, flow_new_2: str,
                       record: Mapping[str, Any]) -> dict[str, Any]:
    """Insert task T between anchor X and its single outgoing target Y:
    X -> T -> Y (the flow X->Y is rewired to X->T; a new flow T->Y is added)."""
    out_flows = [f for f in record["sequence_flows"] if f["source_ref"] == anchor_id]
    if len(out_flows) != 1:
        raise MutationError(
            f"prohibited anchor {anchor_id}: expected exactly 1 outgoing flow"
        )
    old_flow = out_flows[0]
    old_target = old_flow["target_ref"]

    process = _process_element(root)
    old_flow_el = _flow_element(root, old_flow["id"])
    old_flow_el.set("targetRef", task_id)

    task = ET.SubElement(process, f"{{{NS_BPMN}}}task")
    task.set("id", task_id)
    task.set("name", task_name)
    incoming_ref = ET.SubElement(task, f"{{{NS_BPMN}}}incoming")
    incoming_ref.text = old_flow["id"]
    outgoing_ref = ET.SubElement(task, f"{{{NS_BPMN}}}outgoing")
    outgoing_ref.text = flow_new_2

    flow1 = ET.SubElement(process, f"{{{NS_BPMN}}}sequenceFlow")
    flow1.set("id", flow_new_1)
    flow1.set("sourceRef", anchor_id)
    flow1.set("targetRef", task_id)

    flow2 = ET.SubElement(process, f"{{{NS_BPMN}}}sequenceFlow")
    flow2.set("id", flow_new_2)
    flow2.set("sourceRef", task_id)
    flow2.set("targetRef", old_target)

    return {
        "inserted_task_id": task_id,
        "inserted_task_name": task_name,
        "anchor_id": anchor_id,
        "rewired_flow_id": old_flow["id"],
        "rewired_flow_from": [anchor_id, old_target],
        "new_flows": [flow_new_1, flow_new_2],
    }


def _add_condition_expression(root: ET.Element, flow_id: str, text: str) -> dict[str, Any]:
    flow_el = _flow_element(root, flow_id)
    cond = ET.SubElement(flow_el, f"{{{NS_BPMN}}}conditionExpression")
    cond.text = text
    return {"flow_id": flow_id, "condition_expression": text}


def _remove_all_condition_expressions(root: ET.Element) -> int:
    removed = 0
    for el in _elements(root):
        if _local(el.tag) != "conditionExpression":
            continue
        parent = _parent_of(root, el)
        if parent is not None:
            parent.remove(el)
            removed += 1
    return removed


def _add_text_annotation(root: ET.Element, ann_id: str, assoc_id: str,
                         text: str, target_id: str) -> dict[str, Any]:
    process = _process_element(root)
    ann = ET.SubElement(process, f"{{{NS_BPMN}}}textAnnotation")
    ann.set("id", ann_id)
    text_el = ET.SubElement(ann, f"{{{NS_BPMN}}}text")
    text_el.text = text
    assoc = ET.SubElement(process, f"{{{NS_BPMN}}}association")
    assoc.set("id", assoc_id)
    assoc.set("sourceRef", ann_id)
    assoc.set("targetRef", target_id)
    assoc.set("associationDirection", "One")
    return {"annotation_id": ann_id, "association_id": assoc_id,
            "annotation_text": text, "target_id": target_id}


def _remove_text_annotation(root: ET.Element, ann_id: str, assoc_id: str) -> dict[str, Any]:
    removed_ann = 0
    removed_assoc = 0
    for el in _elements(root):
        if _local(el.tag) == "textAnnotation" and el.get("id") == ann_id:
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed_ann += 1
        if _local(el.tag) == "association" and el.get("id") == assoc_id:
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed_assoc += 1
    return {"removed_annotation": removed_ann == 1, "removed_association": removed_assoc == 1}


def _add_data_object(root: ET.Element, obj_id: str, name: str) -> dict[str, Any]:
    process = _process_element(root)
    obj = ET.SubElement(process, f"{{{NS_BPMN}}}dataObject")
    obj.set("id", obj_id)
    obj.set("name", name)
    obj.set("isCollection", "false")
    return {"data_object_id": obj_id, "data_object_name": name}


def _remove_data_object(root: ET.Element, obj_id: str) -> dict[str, Any]:
    removed = 0
    for el in _elements(root):
        if _local(el.tag) == "dataObject" and el.get("id") == obj_id:
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed += 1
    return {"removed_data_object": removed == 1}


def _rename_event(root: ET.Element, event_id: str, new_name: str) -> dict[str, Any]:
    el = _node_by_id(root, event_id)
    if el is None:
        raise MutationError(f"event {event_id} not found")
    old_name = el.get("name", "")
    el.set("name", new_name)
    return {"event_id": event_id, "old_name": old_name, "new_name": new_name}


def _add_boundary_handler(root: ET.Element, boundary_id: str, handler_id: str,
                          handler_name: str, flow_1: str, flow_2: str,
                          attached_id: str, end_id: str, error_id: str) -> dict[str, Any]:
    """boundaryEvent (error) attached to ``attached_id`` + handler task ->
    first end event; the boundary event and handler carry the locked exception
    clause as labels."""
    process = _process_element(root)
    boundary = ET.SubElement(process, f"{{{NS_BPMN}}}boundaryEvent")
    boundary.set("id", boundary_id)
    boundary.set("attachedToRef", attached_id)
    boundary.set("name", handler_name)
    boundary.set("cancelActivity", "true")
    outgoing_ref = ET.SubElement(boundary, f"{{{NS_BPMN}}}outgoing")
    outgoing_ref.text = flow_1
    error_def = ET.SubElement(boundary, f"{{{NS_BPMN}}}errorEventDefinition")
    error_def.set("id", f"{boundary_id}_errdef")
    error_def.set("errorRef", error_id)

    handler = ET.SubElement(process, f"{{{NS_BPMN}}}task")
    handler.set("id", handler_id)
    handler.set("name", handler_name)
    h_in = ET.SubElement(handler, f"{{{NS_BPMN}}}incoming")
    h_in.text = flow_1
    h_out = ET.SubElement(handler, f"{{{NS_BPMN}}}outgoing")
    h_out.text = flow_2

    flow1 = ET.SubElement(process, f"{{{NS_BPMN}}}sequenceFlow")
    flow1.set("id", flow_1)
    flow1.set("sourceRef", boundary_id)
    flow1.set("targetRef", handler_id)
    flow2 = ET.SubElement(process, f"{{{NS_BPMN}}}sequenceFlow")
    flow2.set("id", flow_2)
    flow2.set("sourceRef", handler_id)
    flow2.set("targetRef", end_id)

    # error element at definitions level (parser ignores definitions children)
    definitions = _definitions_element(root)
    error = ET.SubElement(definitions, f"{{{NS_BPMN}}}error")
    error.set("id", error_id)
    error.set("name", handler_name)

    return {"boundary_event_id": boundary_id, "handler_task_id": handler_id,
            "handler_name": handler_name, "attached_to": attached_id,
            "end_event_id": end_id, "flows": [flow_1, flow_2],
            "error_id": error_id}


def _remove_boundary_handler(root: ET.Element, boundary_id: str, handler_id: str,
                             flow_1: str, flow_2: str) -> dict[str, Any]:
    removed = {"boundary": 0, "handler": 0, "flow1": 0, "flow2": 0}
    for el in _elements(root):
        local = _local(el.tag)
        el_id = el.get("id")
        if local == "boundaryEvent" and el_id == boundary_id:
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed["boundary"] += 1
        elif local == "task" and el_id == handler_id:
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed["handler"] += 1
        elif local == "sequenceFlow" and el_id in (flow_1, flow_2):
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed["flow1" if el_id == flow_1 else "flow2"] += 1
    return removed


def _add_branch_handler(root: ET.Element, handler_id: str, handler_name: str,
                        flow_1: str, flow_2: str, anchor_id: str,
                        end_id: str) -> dict[str, Any]:
    """Alternate outgoing branch: anchor -> handler task -> first end event."""
    process = _process_element(root)
    handler = ET.SubElement(process, f"{{{NS_BPMN}}}task")
    handler.set("id", handler_id)
    handler.set("name", handler_name)
    h_in = ET.SubElement(handler, f"{{{NS_BPMN}}}incoming")
    h_in.text = flow_1
    h_out = ET.SubElement(handler, f"{{{NS_BPMN}}}outgoing")
    h_out.text = flow_2

    flow1 = ET.SubElement(process, f"{{{NS_BPMN}}}sequenceFlow")
    flow1.set("id", flow_1)
    flow1.set("sourceRef", anchor_id)
    flow1.set("targetRef", handler_id)
    flow2 = ET.SubElement(process, f"{{{NS_BPMN}}}sequenceFlow")
    flow2.set("id", flow_2)
    flow2.set("sourceRef", handler_id)
    flow2.set("targetRef", end_id)
    return {"handler_task_id": handler_id, "handler_name": handler_name,
            "anchor_id": anchor_id, "end_event_id": end_id,
            "flows": [flow_1, flow_2]}


def _remove_branch_handler(root: ET.Element, handler_id: str,
                           flow_1: str, flow_2: str) -> dict[str, Any]:
    removed = {"handler": 0, "flow1": 0, "flow2": 0}
    for el in _elements(root):
        local = _local(el.tag)
        el_id = el.get("id")
        if local == "task" and el_id == handler_id:
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed["handler"] += 1
        elif local == "sequenceFlow" and el_id in (flow_1, flow_2):
            parent = _parent_of(root, el)
            if parent is not None:
                parent.remove(el)
                removed["flow1" if el_id == flow_1 else "flow2"] += 1
    return removed


def _serialize(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# Exactly-one-targeted-error validation
# ---------------------------------------------------------------------------


def _check_xml_and_structure(data: bytes, source_path: str,
                             contract: Mapping[str, Any]) -> dict[str, Any]:
    try:
        ET.fromstring(data)
    except ET.ParseError as exc:
        return {"xml_parse": False, "failure_reason": f"xml_parse: {exc}"}
    record = parse_bpmn_bytes(data, source_path=source_path, contract=contract)
    report = validate_process_record(record)
    if not report.valid:
        return {"xml_parse": True, "structure_valid": False,
                "failure_reason": f"structure: {report.errors}"}
    return {"xml_parse": True, "structure_valid": True, "record": record}


def _validate_variant(*, mtype: str, kind: str | None, plan: dict[str, Any],
                      source_bytes: bytes, control_bytes: bytes,
                      variant_bytes: bytes, source_record: Mapping[str, Any],
                      control_record: Mapping[str, Any],
                      variant_record: Mapping[str, Any],
                      contract: Mapping[str, Any],
                      source_path: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    for label, data in (("control", control_bytes), ("variant", variant_bytes)):
        result = _check_xml_and_structure(
            data, f"synthetic_controlled_error_extension/{source_path}", contract
        )
        checks[f"{label}_xml_parse"] = result.get("xml_parse", False)
        checks[f"{label}_structure_valid"] = result.get("structure_valid", False)
        if result.get("failure_reason"):
            checks["status"] = "failed"
            checks["failure_reason"] = f"{label}: {result['failure_reason']}"
            return checks

    src_struct = _structural(source_record)
    ctl_struct = _structural(control_record)
    var_struct = _structural(variant_record)

    src_acts = {a["id"]: a for a in source_record["activities"]}
    var_acts = {a["id"]: a for a in variant_record["activities"]}
    ctl_acts = {a["id"]: a for a in control_record["activities"]}
    src_rel = {
        (r["before_activity_id"], r["after_activity_id"])
        for r in source_record["control_flow"]["activity_order_relations"]
    }
    var_rel = {
        (r["before_activity_id"], r["after_activity_id"])
        for r in variant_record["control_flow"]["activity_order_relations"]
    }

    def non_target_relations(relations, target_ids):
        return {(a, b) for a, b in relations
                if a not in target_ids and b not in target_ids}

    if mtype == "prohibited_action_present":
        inserted = plan["mutation"]["inserted_task_id"]
        checks["control_is_source"] = ctl_struct == src_struct
        checks["variant_has_only_inserted_task"] = (
            set(var_acts) - set(ctl_acts) == {inserted}
            and len(var_acts) == len(ctl_acts) + 1
        )
        checks["events_and_gateways_identical"] = (
            variant_record["events"] == control_record["events"]
            and variant_record["gateways"] == control_record["gateways"]
        )
        checks["inserted_label_locked"] = (
            var_acts[inserted]["name"] == plan["rule_element"]["action"]
        )
        checks["non_target_activities_unchanged"] = all(
            var_acts[a]["name"] == ctl_acts[a]["name"]
            and var_acts[a]["lane_ids"] == ctl_acts[a]["lane_ids"]
            for a in ctl_acts if a in var_acts
        )
        checks["non_target_order_unchanged"] = (
            non_target_relations(src_rel, {inserted})
            == non_target_relations(var_rel, {inserted})
        )
        checks["lanes_identical"] = (
            variant_record["lanes"] == control_record["lanes"]
        )
        checks["variant_differs_from_source"] = variant_bytes != source_bytes
    elif mtype == "required_condition_not_enforced":
        locked = plan["mutation"]["condition_expression"]
        locked_flow_id = plan["mutation"]["flow_id"]
        checks["variant_is_source"] = var_struct == src_struct
        diff_flows = [
            f for f in control_record["sequence_flows"]
            if f["condition_expression"] == locked
        ]
        checks["control_has_one_locked_condition"] = (
            len(diff_flows) == 1 and diff_flows[0]["id"] == locked_flow_id
        )
        ctl_without_cond = [
            {**f, "condition_expression": None} if f["condition_expression"] == locked else f
            for f in control_record["sequence_flows"]
        ]
        checks["control_minus_condition_is_source"] = (
            ctl_without_cond == src_struct["sequence_flows"]
        )
        checks["variant_has_no_condition"] = all(
            f["condition_expression"] is None for f in variant_record["sequence_flows"]
        )
        checks["variant_differs_from_control"] = variant_bytes != control_bytes
    elif mtype == "constraint_violated":
        checks["variant_is_source"] = var_struct == src_struct
        if kind == "timer":
            locked = plan["mutation"]
            checks["control_is_source_bytes"] = control_bytes == source_bytes
            ctl_el = _node_by_id(ET.fromstring(control_bytes), locked["event_id"])
            var_el = _node_by_id(ET.fromstring(variant_bytes), locked["event_id"])
            checks["timer_name_changed"] = (
                ctl_el is not None and var_el is not None
                and ctl_el.get("name") != var_el.get("name")
                and var_el.get("name") == locked["conflict_value"]
            )
            checks["variant_differs_from_control"] = variant_bytes != control_bytes
        else:
            checks["control_differs_from_source"] = control_bytes != source_bytes
            if kind == "annotation":
                checks["control_has_annotation"] = (
                    plan["mutation"]["annotation_text"]
                    in [a for a in [
                        " ".join("".join(el.itertext()).split())
                        for el in _elements(ET.fromstring(control_bytes))
                        if _local(el.tag) == "textAnnotation"
                    ]]
                )
                checks["variant_lacks_annotation"] = not any(
                    _local(el.tag) == "textAnnotation"
                    for el in _elements(ET.fromstring(variant_bytes))
                )
            elif kind == "dataobject":
                checks["control_has_data_object"] = any(
                    _local(el.tag) == "dataObject"
                    and el.get("name") == plan["mutation"]["data_object_name"]
                    for el in _elements(ET.fromstring(control_bytes))
                )
                checks["variant_lacks_data_object"] = not any(
                    _local(el.tag) == "dataObject"
                    and el.get("id") == plan["mutation"]["data_object_id"]
                    for el in _elements(ET.fromstring(variant_bytes))
                )
            else:
                checks["status"] = "failed"
                checks["failure_reason"] = f"unknown constraint kind {kind}"
                return checks
            checks["variant_differs_from_control"] = variant_bytes != control_bytes
    elif mtype == "exception_not_handled":
        mut = plan["mutation"]
        checks["variant_is_source"] = var_struct == src_struct
        if kind == "boundary":
            boundary_ctl = next(
                (e for e in control_record["events"]
                 if e["id"] == mut["boundary_event_id"]), None)
            handler_ctl = next(
                (a for a in control_record["activities"]
                 if a["id"] == mut["handler_task_id"]), None)
            checks["control_has_boundary_and_handler"] = (
                boundary_ctl is not None and handler_ctl is not None
            )
            checks["handler_labels_locked"] = (
                boundary_ctl is not None
                and boundary_ctl.get("name") == plan["rule_element"]["exception"]
                and handler_ctl is not None
                and handler_ctl.get("name") == plan["rule_element"]["exception"]
            )
            checks["variant_lacks_boundary_and_handler"] = (
                not any(e["id"] == mut["boundary_event_id"] for e in variant_record["events"])
                and not any(a["id"] == mut["handler_task_id"] for a in variant_record["activities"])
                and not any(_local(el.tag) == "boundaryEvent"
                            for el in _elements(ET.fromstring(variant_bytes)))
            )
        elif kind == "branch":
            handler_ctl = next(
                (a for a in control_record["activities"]
                 if a["id"] == mut["handler_task_id"]), None)
            checks["control_has_handler"] = handler_ctl is not None
            checks["handler_label_locked"] = (
                handler_ctl is not None
                and handler_ctl.get("name") == plan["rule_element"]["exception"]
            )
            checks["variant_lacks_handler"] = not any(
                a["id"] == mut["handler_task_id"] for a in variant_record["activities"]
            )
        else:
            checks["status"] = "failed"
            checks["failure_reason"] = f"unknown exception kind {kind}"
            return checks
        checks["non_target_activities_unchanged"] = all(
            var_acts[a]["name"] == ctl_acts[a]["name"]
            and var_acts[a]["lane_ids"] == ctl_acts[a]["lane_ids"]
            for a in ctl_acts if a in var_acts
        )
        checks["non_target_order_unchanged"] = (
            non_target_relations(src_rel, set()) == non_target_relations(var_rel, set())
        )
        checks["variant_differs_from_control"] = variant_bytes != control_bytes
    else:
        checks["status"] = "failed"
        checks["failure_reason"] = f"unknown mutation type {mtype}"
        return checks

    all_pass = all(isinstance(v, bool) and v for k, v in checks.items()
                   if k not in ("status",))
    checks["all_pass"] = all_pass
    checks["status"] = "passed" if all_pass else "failed"
    return checks


# ---------------------------------------------------------------------------
# Locked 40-item plan (frozen before any method runs)
# ---------------------------------------------------------------------------

_PLAN: dict[str, list[dict[str, Any]]] = {
    "prohibited_action_present": [
        {"rule_id": "article22", "sentence_idx": 0, "process_id": "gdpr_2_consent_to_use_the_data", "anchor": 0},
        {"rule_id": "article22", "sentence_idx": 0, "process_id": "gdpr_2_consent_to_use_the_data", "anchor": 1},
        {"rule_id": "article22", "sentence_idx": 1, "process_id": "gdpr_2_consent_to_use_the_data", "anchor": 0},
        {"rule_id": "article22", "sentence_idx": 1, "process_id": "gdpr_2_consent_to_use_the_data", "anchor": 1},
        {"rule_id": "article7", "sentence_idx": 2, "process_id": "gdpr_5_right_to_withdraw", "anchor": 0},
        {"rule_id": "article7", "sentence_idx": 2, "process_id": "gdpr_5_right_to_withdraw", "anchor": 1},
        {"rule_id": "article7", "sentence_idx": 4, "process_id": "gdpr_3_right_to_access", "anchor": 0},
        {"rule_id": "article15", "sentence_idx": 12, "process_id": "gdpr_1_data_breach", "anchor": 0},
        {"rule_id": "article20", "sentence_idx": 3, "process_id": "gdpr_4_right_of_portability", "anchor": 0},
        {"rule_id": "article17", "sentence_idx": 8, "process_id": "gdpr_7_right_to_be_forgotten", "anchor": 0},
    ],
    "required_condition_not_enforced": [
        {"rule_id": "article33", "sentence_idx": 0, "process_id": "gdpr_1_data_breach"},
        {"rule_id": "article33", "sentence_idx": 1, "process_id": "gdpr_1_data_breach"},
        {"rule_id": "article33", "sentence_idx": 2, "process_id": "gdpr_1_data_breach"},
        {"rule_id": "article34", "sentence_idx": 0, "process_id": "gdpr_1_data_breach"},
        {"rule_id": "article17", "sentence_idx": 0, "process_id": "gdpr_7_right_to_be_forgotten"},
        {"rule_id": "article20", "sentence_idx": 0, "process_id": "gdpr_4_right_of_portability"},
        {"rule_id": "article20", "sentence_idx": 0, "process_id": "gdpr_3_right_to_access"},
        {"rule_id": "article17", "sentence_idx": 0, "process_id": "gdpr_5_right_to_withdraw"},
        {"rule_id": "article15", "sentence_idx": 0, "process_id": "gdpr_3_right_to_access"},
        {"rule_id": "article15", "sentence_idx": 0, "process_id": "gdpr_6_right_to_rectify"},
    ],
    "constraint_violated": [
        {"rule_id": "article33", "sentence_idx": 0, "process_id": "gdpr_1_data_breach", "kind": "timer", "conflict_value": "7 days"},
        {"rule_id": "article33", "sentence_idx": 1, "process_id": "gdpr_1_data_breach", "kind": "timer", "conflict_value": "30 days"},
        {"rule_id": "article16", "sentence_idx": 0, "process_id": "gdpr_6_right_to_rectify", "kind": "annotation"},
        {"rule_id": "article34", "sentence_idx": 0, "process_id": "gdpr_1_data_breach", "kind": "annotation"},
        {"rule_id": "article17", "sentence_idx": 0, "process_id": "gdpr_7_right_to_be_forgotten", "kind": "annotation"},
        {"rule_id": "article17", "sentence_idx": 0, "process_id": "gdpr_4_right_of_portability", "kind": "annotation"},
        {"rule_id": "article20", "sentence_idx": 0, "process_id": "gdpr_3_right_to_access", "kind": "annotation"},
        {"rule_id": "article20", "sentence_idx": 0, "process_id": "gdpr_4_right_of_portability", "kind": "dataobject"},
        {"rule_id": "article17", "sentence_idx": 0, "process_id": "gdpr_5_right_to_withdraw", "kind": "dataobject"},
        {"rule_id": "article7", "sentence_idx": 1, "process_id": "gdpr_2_consent_to_use_the_data", "kind": "dataobject"},
    ],
    "exception_not_handled": [
        {"rule_id": "article33", "sentence_idx": 0, "process_id": "gdpr_1_data_breach", "kind": "boundary"},
        {"rule_id": "article34", "sentence_idx": 2, "process_id": "gdpr_1_data_breach", "kind": "boundary"},
        {"rule_id": "article34", "sentence_idx": 3, "process_id": "gdpr_1_data_breach", "kind": "boundary"},
        {"rule_id": "article22", "sentence_idx": 1, "process_id": "gdpr_2_consent_to_use_the_data", "kind": "boundary"},
        {"rule_id": "article17", "sentence_idx": 8, "process_id": "gdpr_7_right_to_be_forgotten", "kind": "boundary"},
        {"rule_id": "article33", "sentence_idx": 0, "process_id": "gdpr_5_right_to_withdraw", "kind": "branch"},
        {"rule_id": "article20", "sentence_idx": 1, "process_id": "gdpr_3_right_to_access", "kind": "branch"},
        {"rule_id": "article20", "sentence_idx": 1, "process_id": "gdpr_4_right_of_portability", "kind": "branch"},
        {"rule_id": "article20", "sentence_idx": 1, "process_id": "gdpr_6_right_to_rectify", "kind": "branch"},
        {"rule_id": "article15", "sentence_idx": 11, "process_id": "gdpr_3_right_to_access", "kind": "branch"},
    ],
}


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _rule_texts(inference: Mapping[str, Any]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for item in inference.get("matching_items", []) + inference.get("violation_items", []):
        rid = item["rule_id"]
        text = item["rule_text"]
        if rid in texts and texts[rid] != text:
            raise MutationError(f"conflicting rule_text for {rid}")
        texts[rid] = text
    return texts


def _locked_plan_check(mtype: str, plan_entry: dict[str, Any],
                       sentence: dict[str, Any]) -> None:
    field = {
        "prohibited_action_present": "modality",
        "required_condition_not_enforced": "condition",
        "constraint_violated": "constraint",
        "exception_not_handled": "exception",
    }[mtype]
    if mtype == "prohibited_action_present":
        if sentence.get("modality") != "prohibition":
            raise MutationError(
                f"{mtype} plan {plan_entry}: sentence modality is "
                f"{sentence.get('modality')}, expected prohibition")
    elif not (sentence.get(field) or "").strip():
        raise MutationError(
            f"{mtype} plan {plan_entry}: locked rule {field} is empty")
    if not (sentence.get("action") or "").strip():
        raise MutationError(
            f"{mtype} plan {plan_entry}: locked rule action is empty")


def _build_one(mtype: str, plan_entry: dict[str, Any], vid: str,
               source_bytes: bytes, source_record: Mapping[str, Any],
               sentence: dict[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    pid = plan_entry["process_id"]
    src_name = f"{pid}.bpmn"
    source_path = f"synthetic_controlled_error_extension_v2/{vid}/{src_name}"
    root = ET.fromstring(source_bytes)

    action = sentence["action"]
    affinity_id = _affinity_target(action, source_record)

    if mtype == "prohibited_action_present":
        anchor_idx = int(plan_entry["anchor"])
        chains = _chain_activities(source_record)
        if not chains:
            raise MutationError(f"{vid}: no chain activities in {pid}")
        anchor_id = chains[anchor_idx % len(chains)]
        task_id = f"syn_task_{vid}"
        mut = _insert_chain_task(
            root, anchor_id, task_id, action,
            f"syn_flow_{vid}_1", f"syn_flow_{vid}_2", source_record,
        )
        control_bytes = source_bytes  # control == frozen bytes (compliant)
        variant_bytes = _serialize(root)
        target_ids = {task_id}
    elif mtype == "required_condition_not_enforced":
        target_id = affinity_id or next(
            (a["id"] for a in source_record["activities"]), None)
        if target_id is None:
            raise MutationError(f"{vid}: no target activity in {pid}")
        flow = _incoming_flow(source_record, target_id) or (
            source_record["sequence_flows"][0] if source_record["sequence_flows"] else None)
        if flow is None:
            raise MutationError(f"{vid}: no flow to attach condition in {pid}")
        _add_condition_expression(root, flow["id"], sentence["condition"])
        control_bytes = _serialize(root)
        # variant = control minus the condition expression
        _remove_all_condition_expressions(root)
        variant_bytes = _serialize(root)
        mut = {"flow_id": flow["id"], "condition_expression": sentence["condition"],
               "target_activity_id": target_id}
        target_ids = set()
    elif mtype == "constraint_violated":
        kind = plan_entry["kind"]
        target_id = affinity_id or next(
            (a["id"] for a in source_record["activities"]), None)
        if kind == "timer":
            # the timer evidence ("72 hours" start event) may live inside a
            # subProcess, so it is found at the raw-XML level, not in the
            # process-level record
            timer_events = [
                el for el in _elements(root)
                if _local(el.tag) in ("startEvent", "intermediateCatchEvent",
                                      "boundaryEvent", "intermediateThrowEvent")
                and re.search(r"\b\d+\s*(?:hours?|days?)\b",
                              el.get("name") or "", re.IGNORECASE)
            ]
            if not timer_events:
                raise MutationError(f"{vid}: no timer event in {pid}")
            timer_event = timer_events[0]
            mut = _rename_event(root, timer_event.get("id"), plan_entry["conflict_value"])
            mut["conflict_value"] = plan_entry["conflict_value"]
            mut["target_activity_id"] = target_id
            control_bytes = source_bytes
            variant_bytes = _serialize(root)
        elif kind == "annotation":
            if target_id is None:
                raise MutationError(f"{vid}: no target activity in {pid}")
            ann_id = f"syn_annotation_{vid}"
            assoc_id = f"syn_assoc_{vid}"
            mut = _add_text_annotation(root, ann_id, assoc_id,
                                       sentence["constraint"], target_id)
            mut["target_activity_id"] = target_id
            control_bytes = _serialize(root)
            _remove_text_annotation(root, ann_id, assoc_id)
            variant_bytes = _serialize(root)
        elif kind == "dataobject":
            obj_id = f"syn_dataobj_{vid}"
            mut = _add_data_object(root, obj_id, sentence["constraint"])
            mut["target_activity_id"] = target_id
            control_bytes = _serialize(root)
            _remove_data_object(root, obj_id)
            variant_bytes = _serialize(root)
        else:
            raise MutationError(f"{vid}: unknown constraint kind {kind}")
        target_ids = set()
    elif mtype == "exception_not_handled":
        kind = plan_entry["kind"]
        if kind == "boundary":
            attached_id = affinity_id or next(
                (a["id"] for a in source_record["activities"]), None)
            if attached_id is None:
                raise MutationError(f"{vid}: no attachment activity in {pid}")
            end_id = _first_end_event(source_record)
            if end_id is None:
                raise MutationError(f"{vid}: no end event in {pid}")
            boundary_id = f"syn_boundary_{vid}"
            handler_id = f"syn_handler_{vid}"
            error_id = f"syn_error_{vid}"
            mut = _add_boundary_handler(
                root, boundary_id, handler_id, sentence["exception"],
                f"syn_flow_{vid}_1", f"syn_flow_{vid}_2",
                attached_id, end_id, error_id,
            )
            mut["target_activity_id"] = attached_id
            control_bytes = _serialize(root)
            _remove_boundary_handler(root, boundary_id, handler_id,
                                     f"syn_flow_{vid}_1", f"syn_flow_{vid}_2")
            variant_bytes = _serialize(root)
        elif kind == "branch":
            anchor_id = _first_gateway_with_outgoing(source_record)
            if anchor_id is None:
                anchor_id = affinity_id or next(
                    (a["id"] for a in source_record["activities"]), None)
            if anchor_id is None:
                raise MutationError(f"{vid}: no branch anchor in {pid}")
            end_id = _first_end_event(source_record)
            if end_id is None:
                raise MutationError(f"{vid}: no end event in {pid}")
            handler_id = f"syn_handler_{vid}"
            mut = _add_branch_handler(
                root, handler_id, sentence["exception"],
                f"syn_flow_{vid}_1", f"syn_flow_{vid}_2",
                anchor_id, end_id,
            )
            mut["target_activity_id"] = anchor_id
            control_bytes = _serialize(root)
            _remove_branch_handler(root, handler_id,
                                   f"syn_flow_{vid}_1", f"syn_flow_{vid}_2")
            variant_bytes = _serialize(root)
        else:
            raise MutationError(f"{vid}: unknown exception kind {kind}")
        target_ids = set()
    else:
        raise MutationError(f"unknown type {mtype}")

    # -- parse control/variant and validate -------------------------------
    control_check = _check_xml_and_structure(
        control_bytes, f"synthetic_controlled_error_extension_v2/{vid}/control/{src_name}",
        contract)
    if not control_check.get("structure_valid"):
        raise MutationError(f"{vid}: control invalid: {control_check.get('failure_reason')}")
    variant_check = _check_xml_and_structure(
        variant_bytes, f"synthetic_controlled_error_extension_v2/{vid}/variant/{src_name}",
        contract)
    if not variant_check.get("structure_valid"):
        raise MutationError(f"{vid}: variant invalid: {variant_check.get('failure_reason')}")

    # when the variant is structurally identical to the source, store the RAW
    # source bytes as the variant file (the frozen process IS the violated
    # model).  EXCEPT the timer kind: its rename lives inside a subProcess and
    # is invisible to the record parser, so the serialized bytes must be kept.
    # The CONTROL is always stored as built (raw source bytes for the
    # prohibited/timer kinds, serialized tree for the added-structure kinds —
    # never overwritten, because annotation/data-object structures are
    # invisible to the record parser).
    is_timer = mtype == "constraint_violated" and plan_entry.get("kind") == "timer"
    if not is_timer and _structural(variant_check["record"]) == _structural(source_record):
        variant_bytes = source_bytes

    check = _validate_variant(
        mtype=mtype, kind=plan_entry.get("kind"), plan={
            "rule_element": sentence, "mutation": mut,
        },
        source_bytes=source_bytes, control_bytes=control_bytes,
        variant_bytes=variant_bytes, source_record=source_record,
        control_record=control_check["record"],
        variant_record=variant_check["record"],
        contract=contract, source_path=src_name,
    )
    if check["status"] != "passed":
        raise MutationError(f"{vid} failed validation: {check}")

    control_dir = OUTPUT_DIR / vid / "control"
    variant_dir = OUTPUT_DIR / vid / "variant"
    control_dir.mkdir(parents=True, exist_ok=True)
    variant_dir.mkdir(parents=True, exist_ok=True)
    control_path = control_dir / src_name
    variant_path = variant_dir / src_name
    control_path.write_bytes(control_bytes)
    variant_path.write_bytes(variant_bytes)

    return {
        "variant_id": vid,
        "process_id": pid,
        "rule_id": plan_entry["rule_id"],
        "mutation_type": mtype,
        "expected_violation": mtype,
        "sub_kind": plan_entry.get("kind"),
        "source_bpmn": f"data/input/stage1_stage3/gdpr7/{src_name}",
        "source_bpmn_sha256": _sha256_bytes(source_bytes),
        "control_bpmn": control_path.relative_to(ROOT).as_posix(),
        "control_bpmn_sha256": _sha256_bytes(control_bytes),
        "variant_bpmn": variant_path.relative_to(ROOT).as_posix(),
        "variant_bpmn_sha256": _sha256_bytes(variant_bytes),
        "control_equals_source_bytes": control_bytes == source_bytes,
        "variant_equals_source_bytes": variant_bytes == source_bytes,
        "target_activity_id": mut.get("target_activity_id"),
        "mutation_config": mut,
        "rule_element": {
            "field": {
                "prohibited_action_present": "modality+action",
                "required_condition_not_enforced": "condition",
                "constraint_violated": "constraint",
                "exception_not_handled": "exception",
            }[mtype],
            "sentence_idx": sentence["sentence_idx"],
            "sentence_text": sentence["sentence_text"],
            "modality": sentence["modality"],
            "actor": sentence["actor"],
            "action": sentence["action"],
            "condition": sentence["condition"],
            "constraint": sentence["constraint"],
            "exception": sentence["exception"],
        },
        "validation_checks": {k: v for k, v in check.items()
                              if k not in ("all_pass", "record")},
        "generator_sha256": _sha256_file(Path(__file__)),
    }


def _build_variants(originals: Mapping[str, Mapping[str, Any]],
                    source_bytes: Mapping[str, bytes],
                    contract: Mapping[str, Any],
                    sentences_by_rule: Mapping[str, list[dict[str, Any]]],
                    inference: Mapping[str, Any]) -> list[dict[str, Any]]:
    bindings: dict[str, set[str]] = {}
    for item in inference.get("matching_items", []) + inference.get("violation_items", []):
        bindings.setdefault(item["rule_id"], set()).add(item["process_id"])

    variants: list[dict[str, Any]] = []
    for mtype, plan_entries in _PLAN.items():
        for idx, plan_entry in enumerate(plan_entries, start=1):
            rid = plan_entry["rule_id"]
            pid = plan_entry["process_id"]
            if pid not in bindings.get(rid, set()):
                raise MutationError(f"{mtype} plan {plan_entry}: {rid} not bound to {pid}")
            sentences = sentences_by_rule.get(rid, [])
            sentence = next(
                (s for s in sentences if s["sentence_idx"] == plan_entry["sentence_idx"]),
                None)
            if sentence is None:
                raise MutationError(f"{mtype} plan {plan_entry}: sentence not found")
            _locked_plan_check(mtype, plan_entry, sentence)
            vid = f"syn_v2_{SHORT_TYPE[mtype]}_{idx:02d}"
            variant = _build_one(
                mtype, plan_entry, vid, source_bytes[pid], originals[pid],
                sentence, contract,
            )
            variants.append(variant)
    return variants


def _aggregate_sha(files: Mapping[str, bytes]) -> str:
    return _sha256_bytes(b"".join(sorted(files[k] for k in files)))


def generate() -> dict[str, Any]:
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    membership = json.loads(MEMBERSHIP_CONTRACT.read_text(encoding="utf-8"))
    extension_cfg = json.loads(EXTENSION_CONFIG.read_text(encoding="utf-8"))
    bpmn_files = sorted(BPMN_DIR.glob("*.bpmn"))
    if len(bpmn_files) != 7:
        raise MutationError(f"expected 7 GDPR BPMN files, got {len(bpmn_files)}")
    if extension_cfg["counts"]["total"] != 40:
        raise MutationError("extension config counts changed")

    originals: dict[str, dict[str, Any]] = {}
    source_bytes: dict[str, bytes] = {}
    for bpmn in bpmn_files:
        data = bpmn.read_bytes()
        source_bytes[bpmn.stem] = data
        originals[bpmn.stem] = parse_bpmn_bytes(
            data, source_path=str(bpmn), contract=contract
        )

    inference = json.loads(INFERENCE_PACK.read_text(encoding="utf-8"))
    rules = _rule_texts(inference)
    nlp = spacy.load("en_core_web_sm")
    sentences_by_rule = {
        rid: extract_six_element_sentences(rid, text, nlp)
        for rid, text in sorted(rules.items())
    }

    generator_sha = _sha256_file(Path(__file__))
    variants = _build_variants(
        originals, source_bytes, contract, sentences_by_rule, inference
    )

    # the frozen source BPMN files must be byte-unchanged on disk after
    # generation (the generator only ever writes under data/development/)
    source_hashes_after = {
        bpmn.stem: _sha256_bytes(bpmn.read_bytes()) for bpmn in bpmn_files
    }
    if source_hashes_after != {k: _sha256_bytes(v) for k, v in source_bytes.items()}:
        raise MutationError("frozen GDPR-7 BPMN files changed on disk during generation")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "panel_id": "synthetic_controlled_error_extension_v2",
        "panel_label": "synthetic_controlled_error_extension_v2",
        "status": "dev_only_panel_not_human_gold",
        "selection_discipline": (
            "40-item plan (rule sentence x process x sub-kind x anchor) locked in "
            "scripts/build_s3_extended_violation_panel_v2.py BEFORE any Stage 3 "
            "method ran; no result-driven selection; affinity target and anchors "
            "derived deterministically from the ORIGINAL process records and rule "
            "texts only"
        ),
        "counts": {
            t: sum(1 for v in variants if v["mutation_type"] == t)
            for t in ("prohibited_action_present", "required_condition_not_enforced",
                      "constraint_violated", "exception_not_handled")
        },
        "counts_total": len(variants),
        "originals": {
            "bpmn_dir": "data/input/stage1_stage3/gdpr7",
            "bpmn_file_count": len(bpmn_files),
            "source_hashes": {
                bpmn.stem: _sha256_bytes(source_bytes[bpmn.stem])
                for bpmn in bpmn_files
            },
            "aggregate_sha256": _aggregate_sha(source_bytes),
            "membership_payload_sha256": membership.get("membership", {}).get(
                "membership_payload_sha256", ""),
        },
        "rule_binding": {
            "source": "data/development/human_review/stage3_gold_inference_v1.json",
            "inference_pack_sha256": _sha256_file(INFERENCE_PACK),
            "per_variant": {
                v["variant_id"]: {
                    "process_id": v["process_id"],
                    "rule_id": v["rule_id"],
                    "sentence_idx": v["rule_element"]["sentence_idx"],
                }
                for v in variants
            },
        },
        "config": {
            "config_path": "configs/stage3_extended_violation_v2.json",
            "config_sha256": _sha256_file(EXTENSION_CONFIG),
            "gamma_ext": extension_cfg["thresholds"]["gamma_ext"],
        },
        "outputs": {
            "aggregate_variant_sha256": _aggregate_sha({
                v["variant_id"]: v["variant_bpmn_sha256"].encode("ascii")
                for v in variants
            }),
            "variant_dir": "data/development/stage3_synth",
            "layout": "<variant_id>/control/<process_id>.bpmn and <variant_id>/variant/<process_id>.bpmn",
        },
        "variants": variants,
        "safety": {
            "llm_api_calls": 0,
            "network_calls": 0,
            "gold_modified": False,
            "original_bpmn_modified": False,
            "oracle_started": False,
            "panel_is_human_gold": False,
        },
    }
    return manifest


def _replay_check() -> None:
    manifest = generate()
    if not MANIFEST.exists():
        raise MutationError("committed manifest missing; run --publish first")
    committed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if committed != manifest:
        raise MutationError("replay is not byte-identical to the committed manifest")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publish", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            _replay_check()
            print("S3.9-EXT panel v2 replay byte-identical (zero API)")
            return 0
        manifest = generate()
        if MANIFEST.exists():
            raise MutationError("refusing to overwrite existing manifest")
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "S3.9-EXT synthetic controlled extension v2 published: "
            f"{manifest['counts_total']} variants "
            f"(PROH={manifest['counts']['prohibited_action_present']} "
            f"COND={manifest['counts']['required_condition_not_enforced']} "
            f"CONSTR={manifest['counts']['constraint_violated']} "
            f"EXC={manifest['counts']['exception_not_handled']}) zero API"
        )
        return 0
    except MutationError as exc:
        print(f"S3.9-EXT panel v2 refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

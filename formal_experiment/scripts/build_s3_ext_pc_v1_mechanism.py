# -*- coding: utf-8 -*-
"""Phase B builder for S3.9-EXT-PC-V1 mechanism cases.

Builds the frozen 10-pair (20-object) AI-constructed mechanism set and six
non-scoring counterexamples.  The builder writes only into
``data/development/stage3_ext_pc_v1/`` and never calls a real API or reads
Gold.  The inference view is written separately from the evaluation manifest
so a runner can be mechanically checked for answer-metadata leakage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_bytes,
)

OUT = ROOT / "data/development/stage3_ext_pc_v1"
BPMN_DIR = OUT / "bpmn"
RULE_DIR = OUT / "rules"
PLAN_PATH = OUT / "mechanism_plan_v1.json"
MANIFEST_PATH = OUT / "mechanism_case_manifest_v1.json"
INFERENCE_PATH = OUT / "inference_view_v1.json"
FREEZE_PATH = OUT / "mechanism_freeze_v1.json"
STAGE1_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
REAL_STAGE2_INPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

REL_DIRECT_PROHIBITION = "direct_unconditional_action_prohibition"
REL_NECESSARY_PRECONDITION = "necessary_precondition"
REL_ABSENCE = "absence_of_obligation"
REL_PERMISSION = "permission"
REL_RULE_APPLICABILITY = "rule_applicability"
REL_LEGAL_EFFECT = "legal_effect_or_state"
REL_TRIGGER_OBLIGATION = "trigger_obligation_C_implies_OA"
REL_CONDITIONAL_PROHIBITION = "conditional_action_prohibition"
REL_AMBIGUOUS = "ambiguous"
REL_OTHER = "other"

ACTION = "disclose personal data"
CONDITION = "valid consent exists"
CONDITION_ALT = "request is authenticated"


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_json(value), encoding="utf-8", newline="\n")


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _real_source_texts() -> dict[str, str]:
    data = _load_json(REAL_STAGE2_INPUT)
    mapping: dict[str, str] = {}
    for rule in data.get("rules") or []:
        for sentence in rule.get("sentences") or []:
            mapping[sentence["sample_id"]] = sentence["approved_text_en"]
    return mapping


def _q(local: str) -> str:
    return f"{{{BPMN_NS}}}{local}"


def _make_bpmn(process_id: str, nodes: list[dict[str, Any]], flows: list[dict[str, Any]]) -> bytes:
    from xml.etree import ElementTree as ET

    ET.register_namespace("bpmn", BPMN_NS)
    root = ET.Element(
        _q("definitions"),
        {
            "id": "Definitions_1",
            "targetNamespace": "http://bpmn.io/schema/bpmn",
        },
    )
    process = ET.SubElement(root, _q("process"), {"id": process_id, "isExecutable": "true"})
    for node in nodes:
        kind = node["kind"]
        attrs = {"id": node["id"]}
        if node.get("name") is not None:
            attrs["name"] = node["name"]
        if node.get("default_flow") is not None:
            attrs["default"] = node["default_flow"]
        element = ET.SubElement(process, _q(kind), attrs)
        if kind == "textAnnotation":
            text = ET.SubElement(element, _q("text"))
            text.text = node.get("text") or ""
    for flow in flows:
        attrs = {
            "id": flow["id"],
            "sourceRef": flow["source_ref"],
            "targetRef": flow["target_ref"],
        }
        if flow.get("name") is not None:
            attrs["name"] = flow["name"]
        element = ET.SubElement(process, _q("sequenceFlow"), attrs)
        if flow.get("condition_expression") is not None:
            condition = ET.SubElement(element, _q("conditionExpression"))
            condition.text = str(flow["condition_expression"])
    indent = getattr(ET, "indent", None)
    if indent is not None:
        indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _node(kind: str, node_id: str, name: str | None = None, **extra: Any) -> dict[str, Any]:
    node = {"kind": kind, "id": node_id}
    if name is not None:
        node["name"] = name
    node.update(extra)
    return node


def _flow(flow_id: str, source_ref: str, target_ref: str, *, name: str | None = None,
          condition_expression: str | None = None) -> dict[str, Any]:
    flow = {"id": flow_id, "source_ref": source_ref, "target_ref": target_ref}
    if name is not None:
        flow["name"] = name
    if condition_expression is not None:
        flow["condition_expression"] = condition_expression
    return flow


def _activity_names(nodes: list[dict[str, Any]]) -> list[str]:
    return sorted({node.get("name") or "" for node in nodes if node.get("kind") in {
        "task", "userTask", "serviceTask", "sendTask", "receiveTask", "manualTask",
        "businessRuleTask", "scriptTask", "subProcess", "callActivity",
    }} - {""})


def _case(case_id: str, family: str, relation_type: str, *, action: str = ACTION,
          condition: str | None = None, source_clause_ref: str = "AI_constructed",
          source_clause_text: str | None = None, note: str = "",
          control_nodes: list[dict[str, Any]] | None = None,
          control_flows: list[dict[str, Any]] | None = None,
          variant_nodes: list[dict[str, Any]] | None = None,
          variant_flows: list[dict[str, Any]] | None = None,
          expected_control: str = "satisfied", expected_variant: str = "violation",
          expected_control_applicability: str = "applicable",
          expected_variant_applicability: str = "applicable") -> dict[str, Any]:
    return {
        "case_id": case_id,
        "family": family,
        "relation_type": relation_type,
        "action": action,
        "condition": condition,
        "source_clause_ref": source_clause_ref,
        "source_clause_text": source_clause_text or "AI-constructed mechanism rule",
        "note": note,
        "control_nodes": control_nodes or [],
        "control_flows": control_flows or [],
        "variant_nodes": variant_nodes or [],
        "variant_flows": variant_flows or [],
        "expected_control": expected_control,
        "expected_variant": expected_variant,
        "expected_control_applicability": expected_control_applicability,
        "expected_variant_applicability": expected_variant_applicability,
    }


def _base_linear_nodes(task_name: str = "review request") -> list[dict[str, Any]]:
    return [
        _node("startEvent", "start", "Start"),
        _node("task", "review", task_name),
        _node("endEvent", "end", "End"),
    ]


def _base_linear_flows() -> list[dict[str, Any]]:
    return [
        _flow("f_start_review", "start", "review"),
        _flow("f_review_end", "review", "end"),
    ]


def _p1() -> dict[str, Any]:
    c_nodes = _base_linear_nodes()
    c_flows = _base_linear_flows()
    v_nodes = [
        _node("startEvent", "start", "Start"),
        _node("task", "review", "review request"),
        _node("task", "disclose", ACTION),
        _node("endEvent", "end", "End"),
    ]
    v_flows = [
        _flow("f_start_review", "start", "review"),
        _flow("f_review_disclose", "review", "disclose"),
        _flow("f_disclose_end", "disclose", "end"),
    ]
    return _case("P1", "prohibition", REL_DIRECT_PROHIBITION, control_nodes=c_nodes,
                 control_flows=c_flows, variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Linear reachable task: variant inserts exact-canonical prohibited task.")


def _p2() -> dict[str, Any]:
    c_nodes = [
        _node("startEvent", "start", "Start"),
        _node("exclusiveGateway", "g1", "Choose branch"),
        _node("task", "review", "review request"),
        _node("task", "archive", "archive record"),
        _node("endEvent", "end", "End"),
    ]
    c_flows = [
        _flow("f_start_g1", "start", "g1"),
        _flow("f_g1_review", "g1", "review"),
        _flow("f_g1_archive", "g1", "archive"),
        _flow("f_review_end", "review", "end"),
        _flow("f_archive_end", "archive", "end"),
    ]
    v_nodes = [
        _node("startEvent", "start", "Start"),
        _node("exclusiveGateway", "g1", "Choose branch"),
        _node("task", "disclose", ACTION),
        _node("task", "archive", "archive record"),
        _node("endEvent", "end", "End"),
    ]
    v_flows = [
        _flow("f_start_g1", "start", "g1"),
        _flow("f_g1_disclose", "g1", "disclose"),
        _flow("f_g1_archive", "g1", "archive"),
        _flow("f_disclose_end", "disclose", "end"),
        _flow("f_archive_end", "archive", "end"),
    ]
    return _case("P2", "prohibition", REL_DIRECT_PROHIBITION, control_nodes=c_nodes,
                 control_flows=c_flows, variant_nodes=v_nodes, variant_flows=v_flows,
                 note="XOR branch: one structurally reachable branch carries the prohibited task.")


def _p3() -> dict[str, Any]:
    c_nodes = [
        _node("startEvent", "start", "Start"),
        _node("task", "review", "review request"),
        _node("task", "decoy", ACTION),
        _node("endEvent", "end", "End"),
    ]
    c_flows = [
        _flow("f_start_review", "start", "review"),
        _flow("f_review_end", "review", "end"),
    ]
    v_nodes = [
        _node("startEvent", "start", "Start"),
        _node("task", "review", "review request"),
        _node("task", "decoy", ACTION),
        _node("endEvent", "end", "End"),
    ]
    v_flows = [
        _flow("f_start_review", "start", "review"),
        _flow("f_review_decoy", "review", "decoy"),
        _flow("f_decoy_end", "decoy", "end"),
    ]
    return _case("P3", "prohibition", REL_DIRECT_PROHIBITION, control_nodes=c_nodes,
                 control_flows=c_flows, variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Unreachable decoy: node existence is not process permission.")


def _p4() -> dict[str, Any]:
    c_nodes = [
        _node("startEvent", "start", "Start"),
        _node("exclusiveGateway", "g1", ACTION),
        _node("task", "review", "review request"),
        _node("endEvent", "end", "End"),
    ]
    c_flows = [
        _flow("f_start_g1", "start", "g1"),
        _flow("f_g1_review", "g1", "review"),
        _flow("f_review_end", "review", "end"),
    ]
    v_nodes = [
        _node("startEvent", "start", "Start"),
        _node("exclusiveGateway", "g1", ACTION),
        _node("task", "review", "review request"),
        _node("task", "disclose", ACTION),
        _node("endEvent", "end", "End"),
    ]
    v_flows = [
        _flow("f_start_g1", "start", "g1"),
        _flow("f_g1_review", "g1", "review"),
        _flow("f_review_disclose", "review", "disclose"),
        _flow("f_disclose_end", "disclose", "end"),
    ]
    return _case("P4", "prohibition", REL_DIRECT_PROHIBITION, control_nodes=c_nodes,
                 control_flows=c_flows, variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Non-action text decoy: gateway label is not an executable activity.")


def _p5() -> dict[str, Any]:
    c_nodes = [
        _node("startEvent", "start", "Start"),
        _node("task", "metadata", "disclose metadata"),
        _node("endEvent", "end", "End"),
    ]
    c_flows = [
        _flow("f_start_metadata", "start", "metadata"),
        _flow("f_metadata_end", "metadata", "end"),
    ]
    v_nodes = [
        _node("startEvent", "start", "Start"),
        _node("task", "metadata", "disclose metadata"),
        _node("task", "disclose", ACTION),
        _node("endEvent", "end", "End"),
    ]
    v_flows = [
        _flow("f_start_metadata", "start", "metadata"),
        _flow("f_metadata_disclose", "metadata", "disclose"),
        _flow("f_disclose_end", "disclose", "end"),
    ]
    return _case("P5", "prohibition", REL_DIRECT_PROHIBITION, control_nodes=c_nodes,
                 control_flows=c_flows, variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Same verb / different object; exact canonical action is required.")


def _guarded_branch(condition: str = CONDITION) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = [
        _node("startEvent", "start", "Start"),
        _node("exclusiveGateway", "g1", "Consent check", default_flow="f_default"),
        _node("task", "disclose", ACTION),
        _node("task", "deny", "deny request"),
        _node("endEvent", "end", "End"),
    ]
    flows = [
        _flow("f_start_g1", "start", "g1"),
        _flow("f_guard", "g1", "disclose", condition_expression=condition),
        _flow("f_default", "g1", "deny"),
        _flow("f_disclose_end", "disclose", "end"),
        _flow("f_deny_end", "deny", "end"),
    ]
    return nodes, flows


def _c1() -> dict[str, Any]:
    c_nodes, c_flows = _guarded_branch()
    v_nodes = [dict(node) for node in c_nodes]
    v_flows = [dict(flow) for flow in c_flows]
    v_flows.append(_flow("f_bypass", "g1", "disclose"))
    return _case("C1", "necessary_precondition", REL_NECESSARY_PRECONDITION,
                 condition=CONDITION, control_nodes=c_nodes, control_flows=c_flows,
                 variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Single guarded route; variant adds an unconditional bypass flow.")


def _c2() -> dict[str, Any]:
    c_nodes, c_flows = _guarded_branch()
    v_nodes = [dict(node) for node in c_nodes]
    v_flows = [
        _flow("f_start_g1", "start", "g1"),
        _flow("f_guard", "g1", "disclose", condition_expression=CONDITION),
        _flow("f_default", "g1", "disclose"),
        _flow("f_disclose_end", "disclose", "end"),
    ]
    return _case("C2", "necessary_precondition", REL_NECESSARY_PRECONDITION,
                 condition=CONDITION, control_nodes=c_nodes, control_flows=c_flows,
                 variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Default-flow bypass: the XOR default branch reaches the target action.")


def _c3() -> dict[str, Any]:
    c_nodes, c_flows = _guarded_branch()
    v_nodes = [dict(node) for node in c_nodes]
    for node in v_nodes:
        if node["id"] == "g1":
            node["name"] = CONDITION
    v_flows = [dict(flow) for flow in c_flows]
    for flow in v_flows:
        if flow["id"] == "f_guard":
            flow.pop("condition_expression", None)
    return _case("C3", "necessary_precondition", REL_NECESSARY_PRECONDITION,
                 condition=CONDITION, control_nodes=c_nodes, control_flows=c_flows,
                 variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Condition text remains on the gateway, but no sequence flow enforces it.")


def _c4() -> dict[str, Any]:
    c_nodes, c_flows = _guarded_branch()
    v_nodes = [dict(node) for node in c_nodes]
    for node in v_nodes:
        if node["id"] == "g1":
            node["name"] = CONDITION
    v_flows = [dict(flow) for flow in c_flows]
    for flow in v_flows:
        if flow["id"] == "f_guard":
            flow["condition_expression"] = CONDITION_ALT
    return _case("C4", "necessary_precondition", REL_NECESSARY_PRECONDITION,
                 condition=CONDITION, control_nodes=c_nodes, control_flows=c_flows,
                 variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Unrelated condition: C text is non-controlling; the actual guard is C2.")


def _c5() -> dict[str, Any]:
    c_nodes = [
        _node("startEvent", "start", "Start"),
        _node("exclusiveGateway", "g0", "Consent routes", default_flow="f_default"),
        _node("task", "disclose", ACTION),
        _node("task", "deny", "deny request"),
        _node("endEvent", "end", "End"),
    ]
    c_flows = [
        _flow("f_start_g0", "start", "g0"),
        _flow("f_guard_a", "g0", "disclose", condition_expression=CONDITION),
        _flow("f_guard_b", "g0", "disclose", condition_expression=CONDITION),
        _flow("f_default", "g0", "deny"),
        _flow("f_disclose_end", "disclose", "end"),
        _flow("f_deny_end", "deny", "end"),
    ]
    v_nodes = [dict(node) for node in c_nodes]
    v_flows = [dict(flow) for flow in c_flows]
    v_flows.append(_flow("f_multiple_bypass", "g0", "disclose"))
    return _case("C5", "necessary_precondition", REL_NECESSARY_PRECONDITION,
                 condition=CONDITION, control_nodes=c_nodes, control_flows=c_flows,
                 variant_nodes=v_nodes, variant_flows=v_flows,
                 note="Multiple C-guarded routes; variant adds one unconditional route.")


def _simple_nodes(name: str = "review request") -> list[dict[str, Any]]:
    return [
        _node("startEvent", "start", "Start"),
        _node("task", "review", name),
        _node("endEvent", "end", "End"),
    ]


def _simple_flows() -> list[dict[str, Any]]:
    return [
        _flow("f_start_review", "start", "review"),
        _flow("f_review_end", "review", "end"),
    ]


def _counterexample_specs(source_map: Mapping[str, str]) -> list[dict[str, Any]]:
    simple_nodes = _simple_nodes()
    simple_flows = _simple_flows()
    return [
        _case("CE1", "prohibition", REL_ABSENCE, action=ACTION,
              source_clause_ref="AI_constructed_CE1",
              control_nodes=simple_nodes, control_flows=simple_flows,
              variant_nodes=simple_nodes, variant_flows=simple_flows,
              expected_control="not_applicable", expected_variant="not_applicable",
              expected_control_applicability="not_applicable",
              expected_variant_applicability="not_applicable",
              note="The controller is not required to A: absence of obligation."),
        _case("CE2", "prohibition", REL_PERMISSION, action=ACTION,
              source_clause_ref="AI_constructed_CE2",
              control_nodes=simple_nodes, control_flows=simple_flows,
              variant_nodes=simple_nodes, variant_flows=simple_flows,
              expected_control="not_applicable", expected_variant="not_applicable",
              expected_control_applicability="not_applicable",
              expected_variant_applicability="not_applicable",
              note="The controller may A: permission is not prohibition."),
        _case("CE3", "prohibition", REL_RULE_APPLICABILITY, action="apply",
              source_clause_ref="gdpr_article22_s002",
              source_clause_text=source_map.get("gdpr_article22_s002"),
              control_nodes=simple_nodes, control_flows=simple_flows,
              variant_nodes=simple_nodes, variant_flows=simple_flows,
              expected_control="not_applicable", expected_variant="not_applicable",
              expected_control_applicability="not_applicable",
              expected_variant_applicability="not_applicable",
              note="Paragraph 1 shall not apply if C: rule applicability, not process action."),
        _case("CE4", "necessary_precondition", REL_TRIGGER_OBLIGATION, action=ACTION,
              condition="personal data breach occurs",
              source_clause_ref="gdpr_article33_s001",
              source_clause_text=source_map.get("gdpr_article33_s001"),
              control_nodes=simple_nodes, control_flows=simple_flows,
              variant_nodes=simple_nodes, variant_flows=simple_flows,
              expected_control="not_applicable", expected_variant="not_applicable",
              expected_control_applicability="not_applicable",
              expected_variant_applicability="not_applicable",
              note="If C then must A: trigger obligation, not A only if C."),
        _case("CE5", "prohibition", REL_CONDITIONAL_PROHIBITION, action=ACTION,
              condition="a specific circumstance holds",
              source_clause_ref="AI_constructed_CE5",
              control_nodes=simple_nodes, control_flows=simple_flows,
              variant_nodes=simple_nodes, variant_flows=simple_flows,
              expected_control="unsupported", expected_variant="unsupported",
              expected_control_applicability="unsupported",
              expected_variant_applicability="unsupported",
              note="If C, the controller must not A: conditional prohibition outside v1."),
        _case("CE6", "necessary_precondition", REL_NECESSARY_PRECONDITION, action=ACTION,
              condition=CONDITION,
              source_clause_ref="AI_constructed_CE6",
              control_nodes=[
                  _node("startEvent", "start", "Start"),
                  _node("parallelGateway", "g_split", "AND split"),
                  _node("task", "disclose", ACTION),
                  _node("task", "archive", "archive record"),
                  _node("parallelGateway", "g_join", "AND join"),
                  _node("endEvent", "end", "End"),
              ],
              control_flows=[
                  _flow("f_start_split", "start", "g_split"),
                  _flow("f_split_disclose", "g_split", "disclose"),
                  _flow("f_split_archive", "g_split", "archive"),
                  _flow("f_disclose_join", "disclose", "g_join"),
                  _flow("f_archive_join", "archive", "g_join"),
                  _flow("f_join_end", "g_join", "end"),
              ],
              variant_nodes=None, variant_flows=None,
              expected_control="unsupported", expected_variant="unsupported",
              expected_control_applicability="unsupported",
              expected_variant_applicability="unsupported",
              note="A only if C, but the relevant BPMN slice uses an AND gateway."),
    ]


def _relation_check_family(relation_type: str) -> str:
    if relation_type in {REL_NECESSARY_PRECONDITION, REL_TRIGGER_OBLIGATION}:
        return "necessary_precondition"
    return "prohibition"


def _build_rule_spec(case: Mapping[str, Any], object_id: str, side: str | None,
                     nodes: list[dict[str, Any]]) -> dict[str, Any]:
    vocabulary = sorted(set(_activity_names(nodes)) | {case["action"]})
    return {
        "rule_spec_id": f"{object_id}_rulespec",
        "relation_type": case["relation_type"],
        "modality": "prohibition" if _relation_check_family(case["relation_type"]) == "prohibition" else "obligation",
        "actor": "The controller",
        "action": case["action"],
        "condition": case["condition"],
        "constraint": None,
        "exception": None,
        "canonical_action_vocabulary": vocabulary,
        "action_binding_contract": "exact_normalized_complete_enumeration",
        "condition_canonical_surface": case["condition"],
        "condition_binding_contract": (
            "exact_canonical_condition_surface_complete"
            if case["condition"] is not None else None
        ),
        "source_clause_ref": case["source_clause_ref"],
        "source_clause_text": case["source_clause_text"],
        "mechanism_note": case["note"],
    }


def _object_entry(object_id: str, case: Mapping[str, Any], side: str | None,
                  *,
                  manifest_path: str,
                  kind: str,
                  pair_id: str | None = None,
                  source_clause_ref: str | None = None) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "case_id": case["case_id"],
        "kind": kind,
        "family": case["family"],
        "side": side,
        "pair_id": pair_id,
        "mutation": case["note"],
        "source_clause_ref": source_clause_ref if source_clause_ref is not None else case.get("source_clause_ref"),
        "expected_applicability": (
            case["expected_control_applicability"] if side != "variant" else case["expected_variant_applicability"]
        ),
        "expected_decision": (
            case["expected_control"] if side != "variant" else case["expected_variant"]
        ),
        "expected_check_family": _relation_check_family(case["relation_type"]),
        "manifest_path": manifest_path,
    }


def build_mechanism() -> dict[str, Any]:
    contract = load_stage1_contract(STAGE1_CONTRACT)
    source_map = _real_source_texts()
    pair_cases = [_p1(), _p2(), _p3(), _p4(), _p5(), _c1(), _c2(), _c3(), _c4(), _c5()]
    for case in pair_cases:
        if case["case_id"] in {"P1", "P2", "P3", "P4"}:
            case["source_clause_ref"] = "gdpr_article22_s001"
            case["source_clause_text"] = source_map.get("gdpr_article22_s001")
        if case["case_id"] in {"C1", "C2", "C3", "C4", "C5"}:
            case["source_clause_ref"] = "gdpr_article6_s001"
            case["source_clause_text"] = source_map.get("gdpr_article6_s001")
    counter_cases = _counterexample_specs(source_map)

    BPMN_DIR.mkdir(parents=True, exist_ok=True)
    RULE_DIR.mkdir(parents=True, exist_ok=True)

    manifest_objects: list[dict[str, Any]] = []
    inference_objects: list[dict[str, Any]] = []
    bpmn_hashes: dict[str, str] = {}
    rulespec_hashes: dict[str, str] = {}
    pair_records: list[dict[str, Any]] = []
    counter_records: list[dict[str, Any]] = []
    object_counter = 0

    for case in pair_cases:
        pair_id = case["case_id"]
        pair_members: dict[str, str] = {}
        for side in ("control", "variant"):
            object_counter += 1
            object_id = f"pcv1_obj_{object_counter:03d}"
            if side == "control":
                nodes = case["control_nodes"]
                flows = case["control_flows"]
            else:
                nodes = case["variant_nodes"]
                flows = case["variant_flows"]
            process_id = f"pcv1_process_{object_counter:03d}"
            payload = _make_bpmn(process_id, nodes, flows)
            rel_bpmn = f"data/development/stage3_ext_pc_v1/bpmn/{object_id}.bpmn"
            process_record = parse_bpmn_bytes(payload, source_path=rel_bpmn, contract=contract)
            bpmn_path = BPMN_DIR / f"{object_id}.bpmn"
            bpmn_path.write_bytes(payload)
            rule_spec = _build_rule_spec(case, object_id, side, nodes)
            rulespec_path = RULE_DIR / f"{object_id}.rulespec.json"
            _write_json(rulespec_path, rule_spec)
            bpmn_hashes[object_id] = _sha256_bytes(payload)
            rulespec_hashes[object_id] = _sha256_file(rulespec_path)
            pair_members[side] = object_id
            manifest_objects.append(_object_entry(
                object_id, case, side, manifest_path=f"bpmn/{object_id}.bpmn", kind="pair_member", pair_id=pair_id,
            ))
            inference_objects.append({
                "object_id": object_id,
                "rule_spec": rule_spec,
                "bpmn_path": f"bpmn/{object_id}.bpmn",
                "bpmn_sha256": bpmn_hashes[object_id],
                "process_record": process_record,
            })
        pair_records.append({
            "pair_id": pair_id,
            "family": case["family"],
            "relation_type": case["relation_type"],
            "condition": case["condition"],
            "control_object_id": pair_members["control"],
            "variant_object_id": pair_members["variant"],
            "expected_control": case["expected_control"],
            "expected_variant": case["expected_variant"],
        })

    for case in counter_cases:
        object_counter += 1
        object_id = f"pcv1_obj_{object_counter:03d}"
        nodes = case["control_nodes"]
        flows = case["control_flows"]
        process_id = f"pcv1_process_{object_counter:03d}"
        payload = _make_bpmn(process_id, nodes, flows)
        rel_bpmn = f"data/development/stage3_ext_pc_v1/bpmn/{object_id}.bpmn"
        process_record = parse_bpmn_bytes(payload, source_path=rel_bpmn, contract=contract)
        bpmn_path = BPMN_DIR / f"{object_id}.bpmn"
        bpmn_path.write_bytes(payload)
        rule_spec = _build_rule_spec(case, object_id, None, nodes)
        rulespec_path = RULE_DIR / f"{object_id}.rulespec.json"
        _write_json(rulespec_path, rule_spec)
        bpmn_hashes[object_id] = _sha256_bytes(payload)
        rulespec_hashes[object_id] = _sha256_file(rulespec_path)
        manifest_objects.append(_object_entry(
            object_id, case, None, manifest_path=f"bpmn/{object_id}.bpmn", kind="counterexample",
        ))
        inference_objects.append({
            "object_id": object_id,
            "rule_spec": rule_spec,
            "bpmn_path": f"bpmn/{object_id}.bpmn",
            "bpmn_sha256": bpmn_hashes[object_id],
            "process_record": process_record,
        })
        counter_records.append({
            "object_id": object_id,
            "case_id": case["case_id"],
            "expected_applicability": case["expected_control_applicability"],
            "expected_decision": case["expected_control"],
            "expected_check_family": _relation_check_family(case["relation_type"]),
            "relation_type": case["relation_type"],
            "note": case["note"],
        })

    plan = {
        "schema_version": "s3_ext_pc_v1_mechanism_plan@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "frozen_before_predictions",
        "development_only": True,
        "not_human_gold": True,
        "semantic_definitions": {
            "direct_unconditional_action_prohibition_v1": {
                "formula": "V_proh(r,G)=1 iff eligible_prohibition(r) and exists a in B_A(r,G): Reach_G(S,a)",
                "action_node": "executable activity/task only; gateway labels, annotations, event names and condition texts are not action nodes",
                "binding": "exact canonical normalized action enumeration in the AI-constructed mechanism contract",
            },
            "necessary_precondition_bypass_v1": {
                "legacy_target_type": "required_condition_not_enforced",
                "formula": "A only if C; G_without_C=(V,E\\E_C); violation iff A reachable in G_without_C",
                "E_C": "sequence-flow conditionExpression or explicit guarded flow label only",
            },
        },
        "supported_bpmn_fragment": {
            "allowed": ["flat process", "startEvent", "endEvent", "task/activity", "sequenceFlow", "exclusiveGateway", "DAG/acyclic", "explicit flow conditionExpression or guarded flow name"],
            "default_flow": "allowed; default flow is not automatically C",
            "unsupported": ["parallelGateway", "inclusiveGateway", "eventBasedGateway", "complexGateway", "loops/cycles", "subProcess", "callActivity", "boundary/intermediate event condition semantics", "dynamic data-state evaluation"],
        },
        "case_composition": {
            "pair_count": len(pair_records),
            "object_count": len(manifest_objects),
            "counterexample_count": len(counter_records),
            "pairs": pair_records,
            "counterexamples": counter_records,
        },
    }
    _write_json(PLAN_PATH, plan)
    plan_sha = _sha256_file(PLAN_PATH)

    inference_view = {
        "schema_version": "s3_ext_pc_v1_inference_view@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "frozen_before_predictions",
        "objects": inference_objects,
    }
    _write_json(INFERENCE_PATH, inference_view)
    inference_sha = _sha256_file(INFERENCE_PATH)

    case_manifest = {
        "schema_version": "s3_ext_pc_v1_case_manifest@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "frozen_before_predictions",
        "development_only": True,
        "not_human_gold": True,
        "plan_path": PLAN_PATH.relative_to(ROOT).as_posix(),
        "plan_sha256": plan_sha,
        "inference_view_path": INFERENCE_PATH.relative_to(ROOT).as_posix(),
        "inference_view_sha256": inference_sha,
        "objects": manifest_objects,
        "pair_success_denominators": {
            "prohibition": 5,
            "necessary_precondition": 5,
            "total": 10,
        },
        "counterexample_count": len(counter_records),
    }
    _write_json(MANIFEST_PATH, case_manifest)
    manifest_sha = _sha256_file(MANIFEST_PATH)

    freeze = {
        "schema_version": "s3_ext_pc_v1_freeze@1.0.0",
        "revision": "s3_ext_pc_v1",
        "status": "frozen_before_predictions",
        "development_only": True,
        "not_human_gold": True,
        "mechanism_plan_sha256": plan_sha,
        "mechanism_case_manifest_sha256": manifest_sha,
        "inference_view_sha256": inference_sha,
        "bpmn_sha256": bpmn_hashes,
        "rulespec_sha256": rulespec_hashes,
        "object_count": len(manifest_objects),
        "pair_count": len(pair_records),
        "counterexample_count": len(counter_records),
        "real_api_calls": 0,
        "network_experiment_calls": 0,
        "gold_status": "AI_constructed_development_not_gold",
    }
    _write_json(FREEZE_PATH, freeze)

    # The inference view is the leak boundary.  Refuse to leave explicit
    # answer-bearing keys in it.
    forbidden = {"expected", "expected_label", "expected_decision", "target_type",
                 "mutation_type", "pair_id", "side", "control", "variant", "gold"}
    def _walk(value: Any, path: str = "$") -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in forbidden:
                    raise ValueError(f"inference view leaks forbidden key {key!r} at {path}")
                _walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                _walk(child, f"{path}[{index}]")
    _walk(inference_view)

    return {
        "plan_sha256": plan_sha,
        "manifest_sha256": manifest_sha,
        "inference_view_sha256": inference_sha,
        "object_count": len(manifest_objects),
        "pair_count": len(pair_records),
        "counterexample_count": len(counter_records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the frozen artifact hashes from mechanism_freeze_v1.json")
    args = parser.parse_args(argv)
    if args.check:
        if not FREEZE_PATH.exists():
            raise SystemExit("mechanism freeze file is missing")
        freeze = _load_json(FREEZE_PATH)
        checks = {
            "mechanism_plan_sha256": PLAN_PATH,
            "mechanism_case_manifest_sha256": MANIFEST_PATH,
            "inference_view_sha256": INFERENCE_PATH,
        }
        for key, path in checks.items():
            if _sha256_file(path) != freeze[key]:
                raise SystemExit(f"hash mismatch for {path}")
        for object_id, expected in freeze["bpmn_sha256"].items():
            if _sha256_file(BPMN_DIR / f"{object_id}.bpmn") != expected:
                raise SystemExit(f"BPMN hash mismatch for {object_id}")
        for object_id, expected in freeze["rulespec_sha256"].items():
            if _sha256_file(RULE_DIR / f"{object_id}.rulespec.json") != expected:
                raise SystemExit(f"RuleSpec hash mismatch for {object_id}")
        print("mechanism freeze check: OK")
        return 0
    result = build_mechanism()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

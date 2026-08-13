"""Focused tests for the S1.3 P2 label semantics (Sun/Leopold-style
method-level independent reconstruction).

All expectations derive from the locked P2 method contract (configs/
stage1_label_p2_v1.json + the S1.3 P2 crosswalk), NEVER from the GDPR-7
Process Gold. Covers: lane/pool actor context, verb/noun styles, compound
actions, preposition phrases, that/whether clauses, conjunctions, passive
voice, empty/degenerate labels, punctuation and Unicode whitespace,
determinism (double-run byte-identical), fail-closed runtime behavior,
no-hardcoding, Gold-path isolation and no-P1-fallback.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    Stage1LabelError,
    render_label_semantics,
)
from bpc_hybrid.stage1_label_semantics_p2 import (  # noqa: E402
    render_p2_label_semantics,
    validate_p2_label_semantics,
)
from bpc_hybrid.stage1_formal_dataset import (  # noqa: E402
    load_formal_membership_contract,
    load_stage1_contract,
)
from bpc_hybrid.stage1_process import parse_bpmn_bytes  # noqa: E402

CONFIG = json.loads((ROOT / "configs" / "stage1_label_p2_v1.json")
                    .read_text(encoding="utf-8"))
LABEL_CONTRACT = json.loads((ROOT / "configs" / "stage1_label_semantics_s13.json")
                            .read_text(encoding="utf-8"))
MEMBERSHIP = load_formal_membership_contract(
    ROOT / "configs" / "datasets" / "stage1_stage3_gdpr7_v1.json")
STRUCTURAL_CONTRACT = load_stage1_contract(
    ROOT / MEMBERSHIP["process_record_activation"]["structural_contract_path"])

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"


def _synthetic_bpmn(path: Path, *, labels: dict[str, str],
                    lane_assign: dict[str, list[str]],
                    pool_name: str = "Synthetic Controller",
                    lane_names: dict[str, str] | None = None) -> None:
    """Build a minimal valid BPMN (one pool, one process, one laneSet) and
    parse it with the real stage-1 parser so every structural invariant of
    the Process Record holds. labels: activity_id -> raw label;
    lane_assign: lane_id -> list of activity ids in that lane."""
    lane_names = lane_names or {"lane1": "Data Controller", "lane2": ""}
    lane_xml = "\n".join(
        '<bpmn:lane id="%s" name="%s">%s</bpmn:lane>' % (
            lane_id, lane_names.get(lane_id, ""),
            "".join(f'<bpmn:flowNodeRef>{aid}</bpmn:flowNodeRef>'
                    for aid in lane_assign.get(lane_id, [])))
        for lane_id in lane_assign)
    activities_xml = "".join(
        f'<bpmn:task id="{aid}" name="{name}"/>'
        for aid, name in labels.items())
    flows = []
    prev = "start1"
    for aid in labels:
        flows.append(f'<bpmn:sequenceFlow id="sf_{prev}_to_{aid}" '
                     f'sourceRef="{prev}" targetRef="{aid}"/>')
        prev = aid
    flows.append(f'<bpmn:sequenceFlow id="sf_{prev}_to_end" '
                 f'sourceRef="{prev}" targetRef="end1"/>')
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<definitions xmlns:bpmn="{BPMN_NS}" id="synthetic_defs"
             targetNamespace="http://example.org/synth">
  <bpmn:collaboration id="collab">
    <bpmn:participant id="pool1" name="{pool_name}" processRef="proc1"/>
  </bpmn:collaboration>
  <bpmn:process id="proc1" name="{pool_name}" isExecutable="false">
    <bpmn:laneSet>{lane_xml}</bpmn:laneSet>
    <bpmn:startEvent id="start1" name="Start"/>
    {activities_xml}
    <bpmn:endEvent id="end1" name="End"/>
    {"".join(flows)}
  </bpmn:process>
</definitions>"""
    path.write_text(xml, encoding="utf-8")


def _parse_record(bpmn_path: Path, process_id: str) -> dict:
    record = parse_bpmn_bytes(
        bpmn_path.read_bytes(),
        source_path=f"data/input/synthetic/{process_id}.bpmn",
        contract=STRUCTURAL_CONTRACT,
    )
    return record


def _synthetic_record(process_id: str, activities: list[dict],
                      lanes: list[dict], pool_name: str = "Synthetic Controller",
                      pool_id: str = "pool1") -> dict:
    activities = sorted(activities, key=lambda a: a["id"])
    for lane in lanes:
        lane["flow_node_refs"] = sorted(lane.get("flow_node_refs", []))
    return {
        "schema_version": "process_record@1.0.0",
        "process_id": process_id,
        "source": {
            "input_id": process_id,
            "path": f"data/input/synthetic/{process_id}.bpmn",
            "sha256": "0" * 64,
            "byte_size": 1,
            "bpmn_namespace": BPMN_NS,
        },
        "method": {
            "name": "stage1_bpmn_xml_structural",
            "parser_version": "stage1_bpmn_parser@1.0.0",
            "label_semantics": "preserve_original_labels_only",
        },
        "pools": [{"id": pool_id, "name": pool_name,
                   "process_ref": process_id}],
        "lanes": lanes,
        "activities": activities,
        "events": [],
        "gateways": [],
        "sequence_flows": [],
        "control_flow": {
            "direct_edges": [], "reachable_pairs": [],
            "activity_order_relations": [],
            "start_event_ids": [], "end_event_ids": [],
            "branching_gateway_ids": [], "parallel_gateway_ids": [],
            "parallel_split_gateway_ids": [], "parallel_join_gateway_ids": [],
            "cyclic_node_ids": [], "cycle_detected": False,
            "unreachable_node_ids": [],
        },
    }


def _activity(activity_id: str, name: str, lane_ids: list[str],
              act_type: str = "task") -> dict:
    return {"id": activity_id, "name": name, "type": act_type,
            "lane_ids": lane_ids}


def _render(record: dict, bpmn_path: Path):
    return render_p2_label_semantics(record, bpmn_path=bpmn_path,
                                     config=CONFIG)


def _by_id(sidecar, activity_id: str) -> dict:
    return next(a for a in sidecar["activities"]
                if a["activity_id"] == activity_id)


@pytest.fixture()
def world(tmp_path: Path) -> tuple[dict, Path]:
    bpmn = tmp_path / "synthetic.bpmn"
    labels = {
        "act_retrieve": "Retrieve data",
        "act_communicate": "Communication with data subject",
        "act_rectify": "Rectify data",
        "act_stop": "Stop running",
        "act_check": "Check whether the data is processed",
        "act_review": "Review the report and the contract",
        "act_passive": "Data is retrieved",
        "act_empty": "",
        "act_degenerate": "!!!",
        "act_unicode": "\u00a0Notify\u00a0the\u00a0authority\u00a0",
        "act_empty_lane": "Transfer data",
        "act_no_lane": "Send data to the authority",
        "act_subproc": "Approve the request",
    }
    _synthetic_bpmn(
        bpmn, labels=labels,
        lane_assign={
            "lane1": ["act_retrieve", "act_communicate", "act_rectify",
                      "act_stop", "act_check", "act_review", "act_passive",
                      "act_empty", "act_degenerate", "act_unicode",
                      "act_subproc"],
            "lane2": ["act_empty_lane"],
        },
    )
    record = _parse_record(bpmn, "synth_process_1")
    # move the no-lane activity out of both lanes (lane1 set excludes it)
    return record, bpmn


# ---------------------------------------------------------------------------
# actor: model context analysis
# ---------------------------------------------------------------------------

def test_single_lane_actor(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    assert _by_id(sidecar, "act_retrieve")["actor_surface"] == \
        "Data Controller"
    assert _by_id(sidecar, "act_retrieve")["actor_status"] == \
        "single_lane_label"


def test_empty_lane_pool_fallback(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    assert _by_id(sidecar, "act_empty_lane")["actor_surface"] == \
        "Synthetic Controller"
    assert _by_id(sidecar, "act_empty_lane")["actor_status"] == \
        "pool_fallback_empty_lane"


def test_ambiguous_lanes_pool_fallback(tmp_path) -> None:
    bpmn = tmp_path / "amb.bpmn"
    labels = {"act1": "Retrieve data"}
    _synthetic_bpmn(bpmn, labels=labels,
                    lane_assign={"lane1": ["act1"], "lane2": ["act1"]},
                    lane_names={"lane1": "Lane A", "lane2": "Lane B"})
    record = _parse_record(bpmn, "synth_process_2")
    # act1 belongs to BOTH lanes -> ambiguous (lane1 + lane2 non-empty)
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act1")
    assert act["actor_surface"] == "Synthetic Controller"
    assert act["actor_status"] == "pool_fallback_ambiguous_lanes"


def test_no_lane_single_pool_fallback(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_no_lane")
    assert act["actor_surface"] == "Synthetic Controller"
    assert act["actor_status"] == "pool_fallback_single_lane"


# ---------------------------------------------------------------------------
# label language analysis
# ---------------------------------------------------------------------------

def test_verb_object(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_retrieve")
    assert act["action_surface"] == "Retrieve"
    assert act["business_object_surface"] == "data"
    assert act["label_status"] == "verb_style_action_object"


def test_noun_style_prep_phrase(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_communicate")
    assert act["action_surface"] == "Communication"
    assert act["business_object_surface"] == "data subject"
    assert act["label_status"] == "noun_style_action_object"


def test_compound_action_verb_chain(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_stop")
    assert act["action_surface"] == "Stop running"
    assert act["business_object_surface"] is None
    assert act["label_status"] == "verb_style_action_only"


def test_that_clause_not_in_object(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_check")
    assert act["action_surface"] == "Check"
    assert act["business_object_surface"] is None
    assert act["label_status"] == "verb_style_action_only"


def test_conjunction_object(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_review")
    assert act["action_surface"] == "Review"
    assert act["business_object_surface"] == \
        "the report and the contract"
    assert act["label_status"] == "verb_style_action_object"


def test_passive_voice(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_passive")
    assert act["action_surface"] == "retrieved"
    assert act["business_object_surface"] == "Data"
    assert act["label_status"] == "passive_style_action_object"


def test_empty_label(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_empty")
    assert act["action_surface"] is None
    assert act["business_object_surface"] is None
    assert act["label_status"] == "empty_label"


def test_degenerate_label(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_degenerate")
    assert act["action_surface"] is None
    assert act["business_object_surface"] is None
    assert act["label_status"] == "degenerate_label"


def test_unicode_whitespace_collapse(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_unicode")
    assert act["raw_label"] == "\u00a0Notify\u00a0the\u00a0authority\u00a0"
    assert act["action_surface"] == "Notify"
    assert act["business_object_surface"] == "the authority"


def test_type_consistency_subprocess(world) -> None:
    """P2 does not modify the structural record; task/subProcess types pass
    through unchanged (structure comes from the frozen Process Record)."""
    record, bpmn = world
    sidecar = _render(record, bpmn)
    act = _by_id(sidecar, "act_subproc")
    assert act["action_surface"] == "Approve"
    assert act["business_object_surface"] == "the request"
    assert act["label_status"] == "verb_style_action_object"


# ---------------------------------------------------------------------------
# no P1 fallback / P2 != P1
# ---------------------------------------------------------------------------

def test_p2_differs_from_p1_on_prep_phrase(world) -> None:
    """P1's first-token split yields business_object='with data subject';
    P2's linguistic analysis yields 'data subject' (preposition excluded).
    This proves P2 is not a P1 fallback."""
    record, bpmn = world
    p1 = render_label_semantics(record, baseline="P1",
                                contract=LABEL_CONTRACT)
    p2 = _render(record, bpmn)
    p1_act = next(a for a in p1["activities"]
                  if a["activity_id"] == "act_communicate")
    p2_act = next(a for a in p2["activities"]
                  if a["activity_id"] == "act_communicate")
    assert p1_act["business_object_surface"] == "with data subject"
    assert p2_act["business_object_surface"] == "data subject"


# ---------------------------------------------------------------------------
# determinism, fail-closed, isolation
# ---------------------------------------------------------------------------

def test_double_run_byte_identical(world) -> None:
    record, bpmn = world
    a = json.dumps(_render(record, bpmn), ensure_ascii=False, sort_keys=True)
    b = json.dumps(_render(record, bpmn), ensure_ascii=False, sort_keys=True)
    assert a == b
    assert hashlib.sha256(a.encode("utf-8")).hexdigest() == \
        hashlib.sha256(b.encode("utf-8")).hexdigest()


def test_validate_rejects_tamper(world) -> None:
    record, bpmn = world
    sidecar = _render(record, bpmn)
    report = validate_p2_label_semantics(sidecar, process_record=record,
                                         bpmn_path=bpmn, config=CONFIG)
    assert report.valid is True
    tampered = copy.deepcopy(sidecar)
    next(a for a in tampered["activities"]
         if a["activity_id"] == "act_retrieve")["action_surface"] = "X"
    report = validate_p2_label_semantics(tampered, process_record=record,
                                         bpmn_path=bpmn, config=CONFIG)
    assert report.valid is False


def test_runtime_missing_fail_closed(world, monkeypatch) -> None:
    """If the offline spaCy runtime is unavailable, P2 must raise (never
    silently degrade to P1)."""
    record, bpmn = world
    import bpc_hybrid.stage1_label_semantics_p2 as p2mod
    monkeypatch.setattr(p2mod, "_nlp", None)
    # make the in-function `import spacy` fail closed
    monkeypatch.setitem(sys.modules, "spacy", None)
    with pytest.raises(Stage1LabelError):
        _render(record, bpmn)
    monkeypatch.undo()
    assert _render(record, bpmn) is not None


def test_no_hardcoded_ids_or_labels(world) -> None:
    """Renaming process_id and activity ids (with all structural references
    renamed consistently) must not change the semantic outputs (no
    per-sample hardcoding)."""
    record, bpmn = world
    sidecar_a = _render(record, bpmn)
    renamed = copy.deepcopy(record)
    renamed["process_id"] = "completely_different_process"
    for pool in renamed["pools"]:
        pool["process_ref"] = renamed["process_id"]
    id_map = {a["id"]: "renamed_" + a["id"] for a in record["activities"]}
    for act in renamed["activities"]:
        act["id"] = id_map[act["id"]]
    for lane in renamed["lanes"]:
        lane["flow_node_refs"] = [id_map[ref] for ref in lane["flow_node_refs"]]
    for flow in renamed["sequence_flows"]:
        flow["id"] = "r_" + flow["id"]
        flow["source_ref"] = id_map.get(flow["source_ref"], flow["source_ref"])
        flow["target_ref"] = id_map.get(flow["target_ref"], flow["target_ref"])
    cf = renamed["control_flow"]
    for pair in cf["direct_edges"] + cf["reachable_pairs"]:
        pair["source_ref"] = id_map.get(pair["source_ref"], pair["source_ref"])
        pair["target_ref"] = id_map.get(pair["target_ref"], pair["target_ref"])
    for pair in cf["activity_order_relations"]:
        pair["before_activity_id"] = id_map.get(
            pair["before_activity_id"], pair["before_activity_id"])
        pair["after_activity_id"] = id_map.get(
            pair["after_activity_id"], pair["after_activity_id"])
    # the validator recomputes these from the (renamed) flows and compares
    # as sorted structures; re-sort with the new ids
    cf["reachable_pairs"] = [
        {"source_ref": s, "target_ref": t}
        for s, t in sorted((p["source_ref"], p["target_ref"])
                           for p in cf["reachable_pairs"])]
    cf["activity_order_relations"] = [
        {"before_activity_id": s, "after_activity_id": t,
         "relation": "reachable_before"}
        for s, t in sorted((p["before_activity_id"], p["after_activity_id"])
                           for p in cf["activity_order_relations"])]
    sidecar_b = _render(renamed, bpmn)
    values_a = [(a["action_surface"], a["business_object_surface"])
                for a in sidecar_a["activities"]]
    values_b = [(a["action_surface"], a["business_object_surface"])
                for a in sidecar_b["activities"]]
    assert values_a == values_b


def test_gold_path_isolation_source_check() -> None:
    """P2 source must not bind to any Gold/correction/adjudication path; the
    config must DECLARE the forbidden inputs explicitly."""
    src = (ROOT / "src" / "bpc_hybrid"
           / "stage1_label_semantics_p2.py").read_text(encoding="utf-8")
    for forbidden in ("data/gold", "human_correction", "adjudications",
                      "stage1_gdpr7_human_correction"):
        assert forbidden not in src
    cfg = json.loads((ROOT / "configs" / "stage1_label_p2_v1.json")
                     .read_text(encoding="utf-8"))
    forbidden_inputs = cfg["input_contract"]["forbidden_inputs"]
    assert any("data/gold" in item for item in forbidden_inputs)
    assert any("human_correction" in item for item in forbidden_inputs)
    assert any("adjudications" in item for item in forbidden_inputs)


def test_verb_resource_is_generic() -> None:
    """The locked verb-root resource must contain only generic English
    verbs (no GDPR-7-specific tokens)."""
    doc = json.loads((ROOT / "configs" / "resources"
                      / "english_verb_roots_v1.json")
                     .read_text(encoding="utf-8"))
    verbs = doc["verbs"]
    assert len(verbs) >= 100
    assert isinstance(verbs, list) and len(verbs) == len(set(verbs))
    assert all(v.islower() and v.isalpha() for v in verbs)
    assert "data" not in verbs and "subject" not in verbs

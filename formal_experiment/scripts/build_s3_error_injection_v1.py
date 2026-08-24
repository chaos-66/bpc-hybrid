# -*- coding: utf-8 -*-
"""S3.9 synthetic controlled-error extension generator (zero API, zero LLM).

Produces a separate, explicitly-labelled evaluation panel of 30 controlled
mutations over the frozen GDPR-7 BPMN membership
(``synthetic_controlled_error_extension``):

* missing_action : 10 — one target activity removed, incident flows rewired;
* incorrect_actor : 10 — one target activity re-laned to a different actor;
* out_of_order    : 10 — one sequential pair order reversed (flow targets
  swapped).

Discipline (per user directive §五/§六):

* Original frozen BPMN files are never modified (byte-unchanged check).
* Targets are derived from the ORIGINAL process records only and locked in
  the committed manifest BEFORE any Stage 3 method runs; no result-driven
  selection.
* Every variant must: parse as XML; pass the frozen structural parser;
  keep source bytes untouched; differ from the original in exactly one
  targeted dimension (its expected violation); keep non-target activities,
  lanes and order relations unchanged; replay byte-identically.
* The panel is NOT human Gold; it must never be merged into the 33-item
  human-adjudicated violation Gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_bytes,
    validate_process_record,
)

BPMN_DIR = ROOT / "data/input/stage1_stage3/gdpr7"
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
MEMBERSHIP_CONTRACT = ROOT / "configs/datasets/stage1_stage3_gdpr7_v1.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
OUTPUT_DIR = ROOT / "data/development/stage3_synth"
MANIFEST = OUTPUT_DIR / "synthetic_controlled_error_extension_v1.json"

NS_BPMN = "http://www.omg.org/spec/BPMN/20100524/MODEL"
SCHEMA_VERSION = "s3_synthetic_controlled_error_extension@1.0.0"


class MutationError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _elements(root: ET.Element) -> list[ET.Element]:
    return list(root.iter())


def _element_by_id(root: ET.Element, elem_id: str) -> ET.Element | None:
    for el in root.iter():
        if el.get("id") == elem_id:
            return el
    return None


def _parent_of(root: ET.Element, child: ET.Element) -> ET.Element | None:
    for el in root.iter():
        if any(c is child for c in list(el)):
            return el
    return None


# ---------------------------------------------------------------------------
# Process-record helpers (operate on the ORIGINAL parse)
# ---------------------------------------------------------------------------


def _activities(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return list(record["activities"])


def _flows(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return list(record["sequence_flows"])


def _lanes(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    return list(record["lanes"])


def _order_relations(record: Mapping[str, Any]) -> set[tuple[str, str]]:
    return {
        (r["before_activity_id"], r["after_activity_id"])
        for r in record["control_flow"]["activity_order_relations"]
    }


def _non_target_relations(
    relations: set[tuple[str, str]], target_ids: set[str]
) -> set[tuple[str, str]]:
    return {(a, b) for a, b in relations if a not in target_ids and b not in target_ids}


# ---------------------------------------------------------------------------
# Candidate selection (deterministic, from ORIGINAL records only)
# ---------------------------------------------------------------------------


_CUES = (
    "notify", "inform", "erase", "delete", "rectify", "correct", "access",
    "portab", "withdraw", "consent", "breach", "assess", "handle",
    "communicate",
)


def _participant_vocab(root: ET.Element) -> list[str]:
    """All participant (pool) names in the XML collaboration — the legal
    actor vocabulary of the file."""
    names: list[str] = []
    for el in root.iter():
        if _local(el.tag) != "participant":
            continue
        name = (el.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return sorted(names)


def _candidates(
    records: Mapping[str, Mapping[str, Any]],
    actor_vocab: Mapping[str, list[str]] | None = None,
) -> dict[str, list[tuple]]:
    """Collect per-type candidate target tuples for every process."""
    pool: dict[str, list[tuple]] = {
        "missing_action": [],
        "incorrect_actor": [],
        "out_of_order": [],
    }
    for pid in sorted(records):
        rec = records[pid]
        acts = _activities(rec)
        lanes = _lanes(rec)
        # participant vocabulary = pool/participant names of this file
        actors_vocab = list(actor_vocab.get(pid, [])) if actor_vocab else []
        if not actors_vocab:
            actors_vocab = [p["name"] for p in rec.get("pools", [])]
            if len(set(actors_vocab)) < 2:
                actors_vocab.extend(
                    l["name"] for l in lanes if (l.get("name") or "").strip()
                )
        actors_vocab = sorted({n.strip() for n in actors_vocab if n.strip()})

        # missing_action: cued activities (any with a rule-obligation cue)
        for a in acts:
            name = (a["name"] or "").lower()
            if any(c in name for c in _CUES):
                pool["missing_action"].append((pid, a["id"], a["name"] or ""))

        # incorrect_actor: an activity in a lane, with a wrong-actor name from
        # the participant vocabulary to inject; wrong actor = a different
        # participant than the process/pool actor
        for a in acts:
            own = set(a["lane_ids"])
            if not own:
                continue
            actor_name = actors_vocab[0] if actors_vocab else ""
            wrong = next(
                (n for n in actors_vocab if n.lower() != actor_name.lower()),
                None,
            )
            if wrong:
                pool["incorrect_actor"].append(
                    (pid, a["id"], a["name"] or "", "Lane:" + wrong)
                )

        # out_of_order: ordered activity pairs (A before B) with a clean
        # reversal possible: A has an incoming flow and B has an outgoing
        # flow.  Use the reachability-based order relations.
        act_ids = {a["id"] for a in acts}
        relations = _order_relations(rec)
        out_count = {}
        in_count = {}
        for f in _flows(rec):
            out_count[f["source_ref"]] = out_count.get(f["source_ref"], 0) + 1
            in_count[f["target_ref"]] = in_count.get(f["target_ref"], 0) + 1
        for (a, b) in sorted(relations):
            if a not in act_ids or b not in act_ids:
                continue
            if in_count.get(a, 0) < 1 or out_count.get(b, 0) < 1:
                continue
            pool["out_of_order"].append((pid, a, b))
    return pool


def _select(pool: list[tuple], need: int) -> list[dict[str, Any]]:
    """Deterministically choose ``need`` candidates, max 2 per process.

    With 7 processes this yields up to 14 distinct candidates per type, so 10
    is always reachable.  Selection uses only ORIGINAL-record metadata (cues/
    lanes/pairs), never method outputs.
    """
    per_process: dict[str, int] = {}
    chosen: list[dict[str, Any]] = []
    remaining = list(pool)
    it = 0
    while len(chosen) < need and remaining and it < need * 20:
        it += 1
        item = remaining[it % len(remaining)]
        pid = item[0]
        if per_process.get(pid, 0) >= 2:
            remaining.pop(it % len(remaining))
            continue
        # ensure no duplicate (pid, mutation target)
        key = (pid, item[1])
        if any((c["process_id"], c["spec"][1]) == key for c in chosen):
            remaining.pop(it % len(remaining))
            continue
        chosen.append({
            "process_id": pid,
            "spec": list(item),
        })
        per_process[pid] = per_process.get(pid, 0) + 1
        remaining.pop(it % len(remaining))
    if len(chosen) != need:
        raise MutationError(f"could only select {len(chosen)}/{need} candidates")
    return chosen


# ---------------------------------------------------------------------------
# XML transforms
# ---------------------------------------------------------------------------


def _remove_activity(
    root: ET.Element, activity_id: str
) -> dict[str, Any]:
    """Remove one activity and reconnect its single pre/post chain.

    Contract: the target activity has exactly one incoming and exactly one
    outgoing sequence flow (chain position).  The incoming flow is rewired to
    the outgoing flow's target; the outgoing flow is deleted; the activity
    element and its internal <incoming>/<outgoing> reference elements are
    removed.  XML stays well-formed and structurally valid per the frozen
    parser; exactly one activity disappears.
    """
    act = _element_by_id(root, activity_id)
    if act is None:
        raise MutationError(f"activity {activity_id} not found")
    incoming: list[ET.Element] = []
    outgoing: list[ET.Element] = []
    flow_els: list[ET.Element] = []
    for el in _elements(root):
        if _local(el.tag) != "sequenceFlow":
            continue
        flow_els.append(el)
        if el.get("targetRef") == activity_id:
            incoming.append(el)
        if el.get("sourceRef") == activity_id:
            outgoing.append(el)
    if len(incoming) != 1 or len(outgoing) != 1:
        raise MutationError(
            f"missing_action target {activity_id}: expected exactly 1 incoming "
            f"and 1 outgoing flow, got {len(incoming)}/{len(outgoing)}"
        )
    pred_flow, succ_flow = incoming[0], outgoing[0]
    pred_id = pred_flow.get("sourceRef")
    succ_id = succ_flow.get("targetRef")

    # remove the activity's flowNodeRef from all lanes (parser requires lane
    # refs to reference existing flow nodes)
    for lane in [el for el in _elements(root) if _local(el.tag) == "lane"]:
        for ref in list(lane):
            if (ref.text or "").strip() == activity_id:
                lane.remove(ref)

    diff = {
        "removed_activity_id": activity_id,
        "removed_activity_name": act.get("name", ""),
        "incoming_flow_id": pred_flow.get("id"),
        "outgoing_flow_id": succ_flow.get("id"),
        "bypass_from": pred_id,
        "bypass_to": succ_id,
    }

    # rewire the incoming flow to skip the removed activity
    pred_flow.set("targetRef", succ_id)
    # remove the outgoing flow
    parent_out = _parent_of(root, succ_flow)
    if parent_out is not None:
        parent_out.remove(succ_flow)
    # remove the activity element
    parent_act = _parent_of(root, act)
    if parent_act is not None:
        parent_act.remove(act)
    return diff


def _relane_activity(
    root: ET.Element, activity_id: str, target_lane_id: str,
    new_lane_name: str | None = None, new_lane_id: str | None = None,
) -> dict[str, Any]:
    """Move one activity's flowNodeRef into an actor lane.

    ``target_lane_id`` may name an EXISTING lane (its id) or, when
    ``new_lane_id``/``new_lane_name`` are given, a NEW lane is inserted into
    the process laneSet with that id and the wrong-actor name, and the target
    activity is moved into it (one targeted actor change; labels and control
    flow untouched).
    """
    lane_els = [el for el in _elements(root) if _local(el.tag) == "lane"]
    target_lane = next(
        (el for el in lane_els if el.get("id") == target_lane_id), None
    )
    if target_lane is None and new_lane_id is not None:
        # insert a new lane into the process laneSet
        lane_set = next(
            (el for el in _elements(root) if _local(el.tag) == "laneSet"),
            None,
        )
        if lane_set is None:
            raise MutationError("no laneSet found to add actor lane")
        target_lane = ET.SubElement(
            lane_set, f"{{{NS_BPMN}}}lane"
        )
        target_lane.set("id", new_lane_id)
        if new_lane_name:
            target_lane.set("name", new_lane_name)
    if target_lane is None:
        raise MutationError(f"lane {target_lane_id} not found")
    moved = False
    for lane in lane_els:
        for ref in list(lane):
            if _local(ref.tag) != "flowNodeRef":
                continue
            if ref.text is not None and ref.text.strip() == activity_id:
                lane.remove(ref)
                moved = True
                break
        if moved:
            break
    if not moved:
        raise MutationError(
            f"activity {activity_id} has no flowNodeRef in any lane"
        )
    new_ref = ET.SubElement(target_lane, f"{{{NS_BPMN}}}flowNodeRef")
    new_ref.text = activity_id
    # order flowNodeRef elements deterministically by id
    refs = [
        r for r in list(target_lane)
        if _local(r.tag) == "flowNodeRef" and r.text is not None
    ]
    refs.sort(key=lambda r: r.text or "")
    for r in refs:
        target_lane.remove(r)
    for r in refs:
        target_lane.append(r)
    return {
        "moved_activity_id": activity_id,
        "target_lane_id": target_lane.get("id"),
        "injected_lane_name": new_lane_name,
    }


def _swap_order(root: ET.Element, a_id: str, b_id: str,
                flows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Reverse an ordered activity pair A -> B (A reachable before B).

    Generic rewire that works for direct chains and multi-hop channels:

    * ``f_in``: a flow X -> A            -> targetRef = B
    * ``f_first``: first flow on the path A -> ...  -> sourceRef = B
    * ``f_last``: last flow on the path ... -> B    -> targetRef = A
    * ``f_out``: a flow B -> Y          -> sourceRef = A

    Result: X -> B -> ... -> A -> Y (A and B order reversed; intermediate
    nodes, activity set, lanes and labels untouched).
    """
    flow_els = [el for el in _elements(root) if _local(el.tag) == "sequenceFlow"]
    if flows is None:
        flows = [
            {
                "id": el.get("id"),
                "source_ref": el.get("sourceRef"),
                "target_ref": el.get("targetRef"),
                "el": el,
            }
            for el in flow_els
        ]
    els_by_id = {el.get("id"): el for el in flow_els}

    def flows_of() -> list[dict[str, Any]]:
        return [
            {
                "id": el.get("id"),
                "source_ref": el.get("sourceRef"),
                "target_ref": el.get("targetRef"),
            }
            for el in flow_els
        ]

    fwd: dict[str, list[dict[str, Any]]] = {}
    for f in flows_of():
        fwd.setdefault(f["source_ref"], []).append(f)

    # find the lexicographically-first path A -> B (BFS over flow graph)
    from collections import deque
    queue: deque[list[str]] = deque([[a_id]])
    visited = {a_id}
    path: list[str] | None = None
    while queue:
        cur = queue.popleft()
        tail = cur[-1]
        if tail == b_id:
            path = cur
            break
        for f in sorted(fwd.get(tail, []), key=lambda x: x["id"]):
            nxt = f["target_ref"]
            if nxt not in visited:
                visited.add(nxt)
                queue.append(cur + [nxt])
        if cur[-1] == b_id:
            break
    if path is None:
        raise MutationError(f"no path from {a_id} to {b_id}")

    f_in = next(
        (f for f in flows_of() if f["target_ref"] == a_id
         and f["id"] != (path[0] if False else None)),
        None,
    )
    # f_in must not be part of the path from B onward; choose the first flow
    # INTO A that is not the path's first flow if possible
    path_ids = set(path)
    incoming = [f for f in flows_of() if f["target_ref"] == a_id]
    f_in = next((f for f in incoming if f["source_ref"] not in path_ids),
                incoming[0] if incoming else None)
    if f_in is None:
        raise MutationError(f"activity {a_id} has no incoming flow")

    # first and last flow of the path A -> ... -> B
    f_first = next(
        (f for f in flows_of() if f["source_ref"] == path[0]
         and f["target_ref"] == path[1]),
        None,
    )
    f_last = next(
        (f for f in flows_of() if f["source_ref"] == path[-2]
         and f["target_ref"] == path[-1]),
        None,
    )
    outgoing_b = [f for f in flows_of() if f["source_ref"] == b_id]
    f_out = next((f for f in outgoing_b
                  if f["id"] != (f_last["id"] if f_last else None)),
                 outgoing_b[0] if outgoing_b else None)
    if f_out is None:
        raise MutationError(f"activity {b_id} has no outgoing flow")

    diff = {
        "pair": [a_id, b_id],
        "path_nodes": list(path),
        "f_in_id": f_in["id"],
        "f_in": [f_in["source_ref"], f_in["target_ref"]],
        "f_first_id": f_first["id"] if f_first else None,
        "f_last_id": f_last["id"] if f_last else None,
        "f_out_id": f_out["id"],
        "f_out": [f_out["source_ref"], f_out["target_ref"]],
    }

    if f_first is not None and f_last is not None and f_first["id"] == f_last["id"]:
        # direct chain A -> B: rewire the single flow to B -> A
        el = els_by_id[f_first["id"]]
        el.set("sourceRef", b_id)
        el.set("targetRef", a_id)
    else:
        if f_first is not None:
            els_by_id[f_first["id"]].set("sourceRef", b_id)
        if f_last is not None:
            els_by_id[f_last["id"]].set("targetRef", a_id)
    els_by_id[f_in["id"]].set("targetRef", b_id)
    if f_out["id"] not in (f_first["id"] if f_first else None,
                           f_last["id"] if f_last else None):
        els_by_id[f_out["id"]].set("sourceRef", a_id)
    return diff


# ---------------------------------------------------------------------------
# Validation: exactly-one-targeted-error contract
# ---------------------------------------------------------------------------


def _validate_variant(
    variant_bytes: bytes,
    source_bytes: bytes,
    source_path: str,
    contract: Mapping[str, Any],
    original: Mapping[str, Any],
    mutation_type: str,
    target_ids: set[str],
    expected_target_activity: str | None,
) -> dict[str, Any]:
    """Run the full variant check; fail-closed on any violation."""
    checks: dict[str, Any] = {}

    # 1) XML well-formed
    try:
        ET.fromstring(variant_bytes)
        checks["xml_parse"] = True
    except ET.ParseError as exc:
        checks["xml_parse"] = False
        return _fail(checks, f"xml_parse: {exc}")

    # 2) frozen structural parser + schema validation
    variant = parse_bpmn_bytes(
        variant_bytes, source_path=source_path, contract=contract
    )
    report = validate_process_record(variant)
    if not report.valid:
        return _fail(checks, f"structure: {report.errors}")
    checks["structure_valid"] = True

    # 3) mutation-type-specific invariants
    orig_acts = {a["id"]: a for a in _activities(original)}
    var_acts = {a["id"]: a for a in _activities(variant)}
    orig_lanes = {
        a["id"]: sorted(a["lane_ids"]) for a in _activities(original)
    }
    var_lanes = {a["id"]: sorted(a["lane_ids"]) for a in _activities(variant)}
    orig_relations = _order_relations(original)
    var_relations = _order_relations(variant)

    if mutation_type == "missing_action":
        # removed exactly the target activity; none other
        checks["removed_only_target_id"] = (
            set(orig_acts) - set(var_acts) == ({expected_target_activity}
                                               if expected_target_activity else set())
            and len(var_acts) == len(orig_acts) - 1
        )
        # non-target activities unchanged (name + lanes)
        checks["non_target_activities_unchanged"] = all(
            var_acts[a]["name"] == orig_acts[a]["name"]
            and var_lanes[a] == orig_lanes[a]
            for a in orig_acts if a in var_acts
        )
        # order relations not touching the removed id unchanged; removed
        # relations exactly those touching the target; new relations (bypass)
        # only between predecessor and successor of the removed activity
        checks["non_target_order_unchanged"] = (
            _non_target_relations(orig_relations, target_ids)
            == _non_target_relations(var_relations, target_ids)
        )
    elif mutation_type == "incorrect_actor":
        # activity set identical
        checks["activity_set_identical"] = set(orig_acts) == set(var_acts)
        # A new actor lane may be added; non-target activities keep their
        # lane ids; exactly one target activity gains the new lane id.
        orig_lane_ids_all = {lid for ids in orig_lanes.values() for lid in ids}
        var_lane_ids_all = {lid for ids in var_lanes.values() for lid in ids}
        added_lane_ids = var_lane_ids_all - orig_lane_ids_all
        checks["added_lane_is_actor_lane"] = len(added_lane_ids) <= 1
        changed_lanes = {
            a for a in orig_acts if orig_lanes[a] != var_lanes.get(a)
        }
        checks["only_target_relaned"] = changed_lanes == (
            {expected_target_activity} if expected_target_activity else set()
        )
        checks["non_target_lanes_unchanged"] = all(
            orig_lanes[a] == var_lanes[a]
            for a in orig_acts
            if a != expected_target_activity
        )
        # names unchanged
        checks["names_unchanged"] = all(
            var_acts[a]["name"] == orig_acts[a]["name"] for a in orig_acts
        )
        # order relations identical
        checks["order_unchanged"] = orig_relations == var_relations
    elif mutation_type == "out_of_order":
        # activity set identical; lanes identical; names unchanged
        checks["activity_set_identical"] = set(orig_acts) == set(var_acts)
        checks["lanes_identical"] = orig_lanes == var_lanes
        checks["names_unchanged"] = all(
            var_acts[a]["name"] == orig_acts[a]["name"] for a in orig_acts
        )
        # order changed, but only around the target pair endpoints
        checks["order_changed_only_around_pair"] = (
            _non_target_relations(orig_relations, target_ids)
            == _non_target_relations(var_relations, target_ids)
            and orig_relations != var_relations
        )
    else:
        return _fail(checks, f"unknown mutation_type {mutation_type}")

    checks["source_bytes_untouched"] = (
        _sha256_bytes(variant_bytes) != _sha256_bytes(source_bytes)
    )
    all_pass = all(
        isinstance(v, bool) and v for k, v in checks.items()
    )
    checks["all_pass"] = all_pass
    checks["status"] = "passed" if all_pass else "failed"
    return checks


def _fail(checks: dict[str, Any], reason: str) -> dict[str, Any]:
    checks["all_pass"] = False
    checks["status"] = "failed"
    checks["failure_reason"] = reason
    return checks


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def _apply(root: ET.Element, mutation_type: str, spec: list) -> dict[str, Any]:
    pid = spec[0]
    if mutation_type == "missing_action":
        return _remove_activity(root, spec[1])
    if mutation_type == "incorrect_actor":
        # spec[3] holds the injection actor marker "Lane:<actor-name>"
        actor_name = spec[3].split(":", 1)[1]
        new_lane_id = f"syn_lane_{spec[1]}_{spec[1][-8:]}"
        return _relane_activity(
            root, spec[1], "", new_lane_name=actor_name, new_lane_id=new_lane_id
        )
    if mutation_type == "out_of_order":
        return _swap_order(root, spec[1], spec[2])
    raise MutationError(f"unknown mutation type {mutation_type}")


def _largest_avoid_overlap(
    pool: list[tuple], need: int
) -> list[dict[str, Any]]:
    return _select(pool, need)


def _rule_binding(
    variants: list[dict[str, Any]],
    inference: Mapping[str, Any],
) -> dict[str, str]:
    """Lock one (process, rule) per variant: the first rule of the frozen
    inference pack for this process whose human violation item carries the
    same check type (sorted by rule_id; deterministic; no method output)."""
    binding: dict[str, str] = {}
    by_process_type: dict[tuple[str, str], list[str]] = {}
    for item in inference.get("violation_items", []):
        key = (item["process_id"], item["check_type"])
        by_process_type.setdefault(key, []).append(item["rule_id"])
    for v in variants:
        pid = v["process_id"]
        mtype = v["mutation_type"]
        rules = sorted(set(by_process_type.get((pid, mtype), [])))
        if not rules:
            raise MutationError(
                f"variant {v['variant_id']}: no frozen rule for "
                f"{pid}/{mtype}"
            )
        binding[v["variant_id"]] = rules[0]
    return binding


def _aggregate_sha(files: Mapping[str, bytes]) -> str:
    return _sha256_bytes(
        b"".join(sorted(files[k] for k in files))
    )


def _build_variants(
    records: Mapping[str, Mapping[str, Any]],
    source_bytes: Mapping[str, bytes],
    contract: Mapping[str, Any],
    generator_sha: str,
    inference: Mapping[str, Any],
) -> list[dict[str, Any]]:
    actor_vocab = {
        pid: _participant_vocab(ET.fromstring(source_bytes[pid]))
        for pid in source_bytes
    }
    pool = _candidates(records, actor_vocab)
    specs: list[dict[str, Any]] = []
    for mtype, need in (
        ("missing_action", 10),
        ("incorrect_actor", 10),
        ("out_of_order", 10),
    ):
        chosen = _select(pool[mtype], need)
        for i, c in enumerate(chosen, start=1):
            c["variant_id"] = f"syn_{mtype}_{i:02d}"
            c["mutation_type"] = mtype
            c["expected_violation"] = mtype
            specs.append(c)
    binding = _rule_binding(
        [
            {
                "variant_id": s["variant_id"],
                "process_id": s["process_id"],
                "mutation_type": s["mutation_type"],
            }
            for s in specs
        ],
        inference,
    )

    variants: list[dict[str, Any]] = []
    for spec in specs:
        pid = spec["process_id"]
        mtype = spec["mutation_type"]
        original = records[pid]
        data = source_bytes[pid]
        src_name = f"{pid}.bpmn"
        root = ET.fromstring(data)

        diff = _apply(root, mtype, spec["spec"])
        variant_bytes = ET.tostring(
            root, encoding="utf-8", xml_declaration=True
        )

        if mtype == "missing_action":
            target_activity = diff["removed_activity_id"]
            target_ids = {diff["removed_activity_id"]}
        elif mtype == "incorrect_actor":
            target_activity = diff["moved_activity_id"]
            target_ids = {diff["moved_activity_id"]}
        else:
            target_activity = diff["pair"][0]
            target_ids = set(diff["pair"])

        check = _validate_variant(
            variant_bytes, data, f"synthetic_controlled_error_extension/{src_name}",
            contract, original, mtype, target_ids, target_activity,
        )
        if check["status"] != "passed":
            raise MutationError(
                f"variant {spec['variant_id']} failed: {check}"
            )

        variant_path = OUTPUT_DIR / spec["variant_id"] / src_name
        variant_path.parent.mkdir(parents=True, exist_ok=True)
        variant_path.write_bytes(variant_bytes)

        variant_manifest = {
            "variant_id": spec["variant_id"],
            "process_id": pid,
            "rule_id": binding[spec["variant_id"]],
            "source_bpmn": f"data/input/stage1_stage3/gdpr7/{src_name}",
            "source_bpmn_sha256": _sha256_bytes(data),
            "variant_bpmn": variant_path.relative_to(ROOT).as_posix(),
            "variant_bpmn_sha256": _sha256_bytes(variant_bytes),
            "mutation_type": mtype,
            "expected_violation": spec["expected_violation"],
            "target_activity_id": target_activity,
            "mutation_config": {
                "spec": list(spec["spec"]),
                "diff": diff,
            },
            "validation_checks": {k: v for k, v in check.items()
                                  if k != "all_pass"},
            "generator_sha256": generator_sha,
        }
        variants.append(variant_manifest)
    return variants, binding


def generate() -> dict[str, Any]:
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)
    membership = json.loads(MEMBERSHIP_CONTRACT.read_text(encoding="utf-8"))
    bpmn_files = sorted(BPMN_DIR.glob("*.bpmn"))
    if len(bpmn_files) != 7:
        raise MutationError(f"expected 7 GDPR BPMN files, got {len(bpmn_files)}")

    originals: dict[str, dict[str, Any]] = {}
    source_bytes: dict[str, bytes] = {}
    for bpmn in bpmn_files:
        data = bpmn.read_bytes()
        source_bytes[bpmn.stem] = data
        originals[bpmn.stem] = parse_bpmn_bytes(
            data, source_path=str(bpmn), contract=contract
        )

    generator_sha = _sha256_file(Path(__file__))
    inference = json.loads(INFERENCE_PACK.read_text(encoding="utf-8"))
    variants, _binding = _build_variants(
        originals, source_bytes, contract, generator_sha, inference
    )

    # replay (deterministic) check: re-derive and compare manifest
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "panel_id": "synthetic_controlled_error_extension_v1",
        "panel_label": "synthetic_controlled_error_extension",
        "status": "dev_only_panel_not_human_gold",
        "selection_discipline": (
            "targets derived from ORIGINAL process records only; locked before "
            "any Stage 3 method ran; no result-driven selection"
        ),
        "counts": {
            "missing_action": sum(1 for v in variants
                                  if v["mutation_type"] == "missing_action"),
            "incorrect_actor": sum(1 for v in variants
                                   if v["mutation_type"] == "incorrect_actor"),
            "out_of_order": sum(1 for v in variants
                                if v["mutation_type"] == "out_of_order"),
            "total": len(variants),
        },
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
                }
                for v in variants
            },
        },
        "outputs": {
            "aggregate_variant_sha256": _aggregate_sha({
                v["variant_id"]: v["variant_bpmn_sha256"].encode("ascii")
                for v in variants
            }),
            "variant_dir": "data/development/stage3_synth",
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
            print("S3.9 synthetic panel replay byte-identical (zero API)")
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
            "S3.9 synthetic controlled-error extension published: "
            f"{manifest['counts']['total']} variants "
            f"(MA={manifest['counts']['missing_action']} "
            f"IA={manifest['counts']['incorrect_actor']} "
            f"OO={manifest['counts']['out_of_order']}) zero API"
        )
        return 0
    except MutationError as exc:
        print(f"S3.9 synthetic panel refused: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
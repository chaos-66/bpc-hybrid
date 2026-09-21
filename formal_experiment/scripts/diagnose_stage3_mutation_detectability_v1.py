# -*- coding: utf-8 -*-
"""READ-ONLY structural feasibility probe for a Stage 3 mutation benchmark.

Motivation
----------
The viability diagnostic proved that the existing 30-item mutation panel is
unmeasurable with the *similarity-based* Sun scorer: the unmutated originals
already score as violations, because the rule text and the BPMN activity
labels share too little vocabulary for the gamma threshold.

That finding conflates two different questions:

  (a) LEXICAL - can a similarity baseline ground the rule's actions onto the
      process activities?  (measured: no, below gamma)
  (b) STRUCTURAL - does the mutation actually change the process in a way
      that a *correctly grounded* checker would detect?

Question (b) does not depend on the detector at all.  It can be answered from
the BPMN XML alone, and it determines whether a real benchmark is even
buildable.  If the mutations are not structurally detectable, no detector can
be measured; if they are, then the benchmark is sound and the only remaining
work is grounding.

For each panel item this probe compares the mutated BPMN against its unmutated
original and asks, using the canonical Stage 1 Process Record:

- missing_action  : is the manifest's `target_activity_id` absent from the
  mutated process while present in the original?
- incorrect_actor : did the target activity's lane membership change?
- out_of_order   : did the reachability (control-flow order) relation between
  the manifest's pair endpoints actually change?

Nothing is written.  No LLM/API is called.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)

PANEL = (ROOT / "data/development/stage3_synth"
         / "synthetic_controlled_error_extension_v1.json")
STRUCTURAL_CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _activity_ids(record: dict[str, Any]) -> set[str]:
    return {a["id"] for a in record.get("activities") or []}


def _lane_of(record: dict[str, Any], activity_id: str) -> str | None:
    """Lane name owning `activity_id` (via lane flow_node_refs)."""
    owner = None
    for lane in record.get("lanes") or []:
        if activity_id in (lane.get("flow_node_refs") or []):
            # last writer wins is fine: a node belongs to one lane in these files
            owner = lane.get("name") or lane.get("id")
    return owner


def _reachable(record: dict[str, Any]) -> set[tuple[str, str]]:
    """Direct + transitive control-flow reachability as (source, target) ids.

    ``control_flow.reachable_pairs`` and ``direct_edges`` are lists of OBJECTS
    (``{"source_ref": ..., "target_ref": ...}``), not tuples.  Both shapes are
    handled explicitly: getting this wrong silently yields a set of strings
    instead of pairs and produces a false "no change" verdict, which is exactly
    the mistake this helper now guards against.
    """
    flow = record.get("control_flow") or {}
    normalised: set[tuple[str, str]] = set()
    for item in flow.get("reachable_pairs") or []:
        if isinstance(item, dict):
            source, target = item.get("source_ref"), item.get("target_ref")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            source, target = item
        else:
            raise TypeError(f"unexpected reachable_pairs element: {item!r}")
        if source and target:
            normalised.add((source, target))
    if normalised:
        return normalised
    for item in flow.get("direct_edges") or []:
        if isinstance(item, dict):
            source, target = item.get("source_ref"), item.get("target_ref")
            if source and target:
                normalised.add((source, target))
    return normalised


def _direct_edges(record: dict[str, Any]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for item in (record.get("control_flow") or {}).get("direct_edges") or []:
        if isinstance(item, dict):
            source, target = item.get("source_ref"), item.get("target_ref")
            if source and target:
                out.add((source, target))
    return out


def main() -> int:
    panel = _load(PANEL)
    contract = load_stage1_contract(STRUCTURAL_CONTRACT)

    rows: list[dict[str, Any]] = []
    for variant in panel["variants"]:
        original_path = ROOT / variant["source_bpmn"]
        mutated_path = ROOT / variant["variant_bpmn"]
        if not original_path.is_file() or not mutated_path.is_file():
            continue
        original = parse_bpmn_file(original_path, contract=contract)
        mutated = parse_bpmn_file(mutated_path, contract=contract)
        target = variant["mutation_type"]
        target_activity = variant.get("target_activity_id")
        config = variant.get("mutation_config") or {}
        diff = config.get("diff") or {}

        row: dict[str, Any] = {
            "variant_id": variant["variant_id"],
            "process_id": variant["process_id"],
            "target_type": target,
            "target_activity_id": target_activity,
            "detectable": False,
            "evidence": None,
        }

        orig_acts = _activity_ids(original)
        mut_acts = _activity_ids(mutated)
        orig_reach = _reachable(original)
        mut_reach = _reachable(mutated)

        if target == "missing_action":
            present_before = target_activity in orig_acts
            absent_after = target_activity not in mut_acts
            removed = sorted(orig_acts - mut_acts)
            added = sorted(mut_acts - orig_acts)
            row["detectable"] = bool(present_before and absent_after
                                     and not added)
            row["evidence"] = {
                "target_present_in_original": present_before,
                "target_absent_in_mutated": absent_after,
                "activities_removed": removed,
                "activities_added": added,
            }

        elif target == "incorrect_actor":
            before = _lane_of(original, target_activity)
            after = _lane_of(mutated, target_activity)
            row["detectable"] = bool(
                target_activity in orig_acts and target_activity in mut_acts
                and before != after and after)
            row["evidence"] = {
                "lane_before": before,
                "lane_after": after,
                "injected_lane_name": diff.get("injected_lane_name"),
                "target_lane_id": diff.get("target_lane_id"),
                "activity_retained": target_activity in mut_acts,
            }

        else:  # out_of_order
            edges_before = _direct_edges(original)
            edges_after = _direct_edges(mutated)
            edge_delta = sorted(edges_before ^ edges_after)
            reach_delta = sorted(orig_reach ^ mut_reach)
            # `f_first_id`/`f_last_id` in the manifest are SEQUENCE-FLOW ids,
            # not node ids; the node pair is `pair`.  Testing flow ids against
            # a node-level reachability relation is meaningless and would
            # report a false negative.
            pair = [n for n in (diff.get("pair") or []) if n]
            fwd_before = (pair[0], pair[1]) in orig_reach if len(pair) == 2 else None
            fwd_after = (pair[0], pair[1]) in mut_reach if len(pair) == 2 else None
            back_before = (pair[1], pair[0]) in orig_reach if len(pair) == 2 else None
            back_after = (pair[1], pair[0]) in mut_reach if len(pair) == 2 else None
            pair_reversed = (
                len(pair) == 2
                and (fwd_before, back_before) != (fwd_after, back_after))
            # the mutation rewires flow endpoints, so a genuine reorder must
            # show up as a change in the DIRECT edges even when the transitive
            # reachability closure is unchanged (parallel gateways can keep the
            # closure stable while the local order flips).
            row["detectable"] = bool(edge_delta or reach_delta or pair_reversed)
            row["evidence"] = {
                "direct_edges_before": len(edges_before),
                "direct_edges_after": len(edges_after),
                "direct_edge_delta": len(edge_delta),
                "direct_edge_delta_sample": edge_delta[:4],
                "reachability_pairs_before": len(orig_reach),
                "reachability_pairs_after": len(mut_reach),
                "reachability_delta": len(reach_delta),
                "manifest_node_pair": pair,
                "pair_forward_before": fwd_before,
                "pair_forward_after": fwd_after,
                "pair_backward_before": back_before,
                "pair_backward_after": back_after,
                "pair_order_reversed": pair_reversed,
            }

        rows.append(row)

    print("=" * 100)
    print("STRUCTURAL DETECTABILITY (BPMN-only; independent of any detector)")
    print("=" * 100)
    print(f"{'variant':<26}{'target':<18}{'detectable':>11}   evidence")
    print("-" * 100)
    for row in rows:
        ev = row["evidence"] or {}
        if row["target_type"] == "missing_action":
            note = (f"removed={len(ev.get('activities_removed') or [])} "
                    f"added={len(ev.get('activities_added') or [])}")
        elif row["target_type"] == "incorrect_actor":
            note = f"{ev.get('lane_before')!r} -> {ev.get('lane_after')!r}"
        else:
            note = (f"edge_delta={ev.get('direct_edge_delta')} reach_delta={ev.get('reachability_delta')} " f"reversed={ev.get('pair_order_reversed')}")
        print(f"{row['variant_id']:<26}{row['target_type']:<18}"
              f"{('YES' if row['detectable'] else 'no'):>11}   {note}")

    print()
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)
    totals: Counter = Counter()
    ok: Counter = Counter()
    for row in rows:
        totals[row["target_type"]] += 1
        if row["detectable"]:
            ok[row["target_type"]] += 1
    for t in TYPES:
        print(f"  {t:<18} structurally detectable in {ok[t]:>2}/{totals[t]:<2}")
    print(f"  {'TOTAL':<18} {sum(ok.values()):>14}/{sum(totals.values())}")
    print()
    print("Reading: a benchmark item is usable only if the mutation is")
    print("structurally detectable. Lexical grounding is a SEPARATE problem;")
    print("this probe removes it from the question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

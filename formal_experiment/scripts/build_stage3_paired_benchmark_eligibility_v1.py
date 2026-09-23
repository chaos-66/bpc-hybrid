# -*- coding: utf-8 -*-
"""Audit benchmark eligibility after binding completeness and rule semantics.

The benchmark's 10/10/10 design is NOT treated as an eligibility guarantee.
A pair is eligible for a violation type only when that type has a complete,
human-approved binding and, for out_of_order, an explicit rule-side order.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file  # noqa: E402

REFERENCE = ROOT / "data/development/stage3_synth/stage3_binding_reference_v1.json"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
CONTRACT = ROOT / "configs/stage1_structural_s11_s14.json"
OUT = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_eligibility_v1.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _lane_tokens(record: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for lane in record.get("lanes") or []:
        for key in ("id", "name"):
            if lane.get(key):
                values.add(str(lane[key]))
    for pool in record.get("pools") or []:
        if pool.get("id"):
            values.add(str(pool["id"]))
        if pool.get("name"):
            values.add(str(pool["name"]))
    return values


def _ordering(record: dict[str, Any], before: str, after: str) -> dict[str, bool]:
    edges = {
        (str(e.get("source_ref")), str(e.get("target_ref")))
        for e in (record.get("control_flow") or {}).get("direct_edges") or []
        if e.get("source_ref") and e.get("target_ref")
    }
    reach = {
        (str(e.get("source_ref")), str(e.get("target_ref")))
        for e in (record.get("control_flow") or {}).get("reachable_pairs") or []
        if e.get("source_ref") and e.get("target_ref")
    }
    forward = (before, after) in edges or (before, after) in reach
    backward = (after, before) in edges or (after, before) in reach
    return {"forward": forward, "backward": backward}


def build() -> dict[str, Any]:
    reference = {str(r["pair_id"]): r for r in _load(REFERENCE)["records"]}
    benchmark = _load(BENCHMARK)
    items_by_pair: dict[str, dict[str, dict[str, Any]]] = {}
    for item in benchmark.get("items") or []:
        items_by_pair.setdefault(str(item["pair_id"]), {})[str(item["role"])] = item
    contract = load_stage1_contract(CONTRACT)
    cache: dict[str, dict[str, Any]] = {}

    def parsed(rel_path: str) -> dict[str, Any]:
        if rel_path not in cache:
            cache[rel_path] = parse_bpmn_file(ROOT / rel_path, contract=contract)
        return cache[rel_path]

    records: list[dict[str, Any]] = []
    summary = Counter()
    for pair_id in sorted(reference):
        ref = reference[pair_id]
        roles = items_by_pair[pair_id]
        control = roles["control"]
        variant = roles["variant"]
        target_type = str(ref.get("target_violation_type") or "")
        target_id = ref.get("target_activity_id") or control.get("grounding", {}).get("target_activity_id")
        control_record = parsed(control["bpmn_path"])
        variant_record = parsed(variant["bpmn_path"])
        action = ref.get("action_binding") or {}
        actor = ref.get("actor_binding") or {}
        order = ref.get("order_binding") or {}

        action_ok = bool(action.get("human_approved")
                         and action.get("rule_action_id"))
        actor_ok = bool(actor.get("human_approved")
                        and actor.get("rule_actor_id")
                        and actor.get("expected_lane_id") in _lane_tokens(control_record))
        order_ok = bool(order.get("human_approved")
                        and order.get("before_rule_action_id")
                        and order.get("after_rule_action_id")
                        and order.get("status") != "ineligible_no_rule_order")
        activity_ok = bool(target_id and target_id in {
            str(a["id"]) for a in control_record.get("activities") or []
        })

        reasons: list[str] = []
        if target_type == "missing_action":
            eligible = action_ok and activity_ok
            if not action_ok:
                reasons.append("action_binding_not_human_complete")
            if not activity_ok:
                reasons.append("target_activity_absent_from_control")
        elif target_type == "incorrect_actor":
            eligible = action_ok and actor_ok and activity_ok
            if not action_ok:
                reasons.append("action_binding_not_human_complete")
            if not actor_ok:
                reasons.append("actor_or_lane_binding_not_human_complete")
            if not activity_ok:
                reasons.append("target_activity_absent_from_control")
        elif target_type == "out_of_order":
            eligible = action_ok and order_ok and activity_ok
            if not action_ok:
                reasons.append("action_binding_not_human_complete")
            if not order_ok:
                reasons.append("ineligible_no_explicit_rule_order")
            if not activity_ok:
                reasons.append("target_activity_absent_from_control")
            if order_ok:
                before = order.get("before_rule_action_id")
                after = order.get("after_rule_action_id")
                # The order relation is between rule actions.  Process
                # reachability can only be checked when those actions have
                # explicit process endpoints; otherwise keep the rule-side
                # eligibility and mark process observability separately.
                order_pair = control.get("grounding", {}).get("order_pair") or []
                if len(order_pair) == 2:
                    co = _ordering(control_record, order_pair[0], order_pair[1])
                    va = _ordering(variant_record, order_pair[0], order_pair[1])
                    if not (co["forward"] and not co["backward"]):
                        reasons.append("control_order_not_forward_ordered")
                    if not (va["backward"] and not va["forward"]):
                        reasons.append("variant_order_not_inverted")
        else:
            eligible = False
            reasons.append("unknown_target_violation_type")

        order_semantics = None
        if target_type == "out_of_order":
            rule_text = str((control.get("grounding") or {}).get("rule_action_text") or "")
            cue_hits = sorted(set(match.group(0).lower() for match in re.finditer(
                r"\b(before|after|prior\s+to|following|once|without\s+undue\s+delay\s+after|prerequisite|precondition)\b",
                rule_text, flags=re.IGNORECASE)))
            order_semantics = {
                "regulation_text_length": len(rule_text),
                "explicit_order_cue_hits": cue_hits,
                "direct_llm_order_relation_count": 0,
                "gold_rule_order_relation_count": 0,
                "human_review_order_scope": (ref.get("order_binding") or {}).get(
                    "process_only_human_candidates", {}
                ).get("order_scope"),
                "note": ("Cue hits are diagnostic only. An eligible formal rule "
                         "order also requires a human-approved endpoint binding "
                         "and an explicit/entailed relation."),
            }
        completeness = {
            "action": "human_complete" if action_ok else "incomplete_or_ai_only",
            "actor": "human_complete" if actor_ok else "incomplete_or_ai_only",
            "order": "human_complete_explicit_rule_order" if order_ok else (
                "ineligible_no_explicit_rule_order"),
            "target_activity_in_control": activity_ok,
        }
        records.append({
            "pair_id": pair_id,
            "rule_id": ref.get("rule_id"),
            "process_id": ref.get("process_id"),
            "violation_type": target_type,
            "eligible": bool(eligible),
            "reason": "eligible" if eligible else ";".join(reasons),
            "binding_completeness": completeness,
            "order_semantics_audit": order_semantics,
        })
        summary[target_type if eligible else f"{target_type}:ineligible"] += 1

    output = {
        "schema_version": "stage3_paired_benchmark_eligibility@1.0.0",
        "status": "eligibility_audit_complete",
        "is_gold": False,
        "policy": ("Rule-side eligibility is independent of whether a mutated "
                   "process exhibits the violation.  out_of_order requires an "
                   "explicit rule order; process-only order mutations are "
                   "ineligible."),
        "summary": dict(summary),
        "eligible_pairs_by_type": {
            t: [r["pair_id"] for r in records
                if r["violation_type"] == t and r["eligible"]]
            for t in ("missing_action", "incorrect_actor", "out_of_order")
        },
        "records": records,
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    return output


def main() -> int:
    output = build()
    print(json.dumps({"output": str(OUT), "summary": output["summary"],
                      "eligible": output["eligible_pairs_by_type"]},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

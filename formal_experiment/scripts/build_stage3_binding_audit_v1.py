# -*- coding: utf-8 -*-
"""Machine-readable audit of the 30 Stage-3 binding pairs.

Classes
-------
H  already direct/complete human-approved binding surface (or N/A field)
A  human-confirmed candidate; only mechanical schema/ID conversion is missing
N  AI added a substantive binding judgment with no human confirmation
U  the current Rule Record lacks a legal span/relation, so no ID can be filled
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HUMAN = ROOT / "data/development/stage3_synth/stage3_binding_human_decisions_v1.json"
RESOLVED = ROOT / "data/development/stage3_synth/stage3_binding_resolved_reference_v1.json"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
OUT = ROOT / "data/development/stage3_synth/stage3_binding_audit_v1.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _classify_action(v: dict[str, Any], res: dict[str, Any]) -> dict[str, Any]:
    human = v.get("action_id")
    if human:
        return {"class": "A", "human_value": human,
                "human_approved": True,
                "resolved_value": res.get("rule_action_id"),
                "resolved_status": res.get("status"),
                "reason": "human-confirmed action candidate; mechanical schema conversion only"}
    if res.get("rule_action_id"):
        return {"class": "N", "human_value": None,
                "human_approved": False,
                "resolved_value": res.get("rule_action_id"),
                "resolved_status": res.get("status"),
                "reason": "AI proposed an action binding after the human left the field null"}
    return {"class": "U", "human_value": None,
            "human_approved": False,
            "resolved_value": None,
            "resolved_status": res.get("status"),
            "reason": res.get("reason_zh") or "no supported legal action candidate"}


def _classify_actor(v: dict[str, Any], res: dict[str, Any]) -> dict[str, Any]:
    human = v.get("actor_id")
    if human:
        return {"class": "A", "human_value": human,
                "human_approved": True,
                "resolved_value": res.get("rule_actor_id"),
                "resolved_status": res.get("status"),
                "reason": "human-confirmed actor candidate; mechanical schema conversion only"}
    if res.get("status") == "inferred_counterparty_executor":
        return {"class": "N", "human_value": None,
                "human_approved": False,
                "resolved_value": res.get("rule_actor_id"),
                "resolved_status": res.get("status"),
                "executor": res.get("executor"),
                "reason": res.get("reason_zh") or "AI inferred a counterparty executor"}
    return {"class": "U", "human_value": None,
            "human_approved": False,
            "resolved_value": res.get("rule_actor_id"),
            "resolved_status": res.get("status"),
            "executor": res.get("executor"),
            "reason": res.get("reason_zh") or "no legal actor span available for binding"}


def _classify_order(target_type: str, v: dict[str, Any],
                    res: dict[str, Any]) -> dict[str, Any]:
    if target_type != "out_of_order":
        return {"class": "H", "status": "not_applicable",
                "human_approved": True,
                "reason": "target violation is not out_of_order"}
    if res.get("rule_relation"):
        return {"class": "A", "human_value": res.get("rule_relation"),
                "human_approved": bool(res.get("human_approved")),
                "resolved_value": res.get("rule_relation"),
                "resolved_status": res.get("status"),
                "reason": "explicit rule-side order relation"}
    return {"class": "U", "human_value": {
                "before_action_id": v.get("order_before_action_id"),
                "after_action_id": v.get("order_after_action_id"),
                "order_scope": v.get("order_scope"),
            },
            "human_approved": False,
            "resolved_value": None,
            "resolved_status": res.get("status") or "ineligible_no_rule_order",
            "reason": res.get("reason_zh") or "no explicit rule-side order requirement"}


def build() -> dict[str, Any]:
    human = _load(HUMAN)["records"]
    resolved = {str(r["pair_id"]): r for r in _load(RESOLVED)["records"]}
    benchmark = _load(BENCHMARK)
    target_types = {
        str(i["pair_id"]): str(i.get("target_violation_type") or "")
        for i in benchmark.get("items") or []
        if i.get("role") == "control"
    }
    records: list[dict[str, Any]] = []
    summary = Counter()
    for pair_id in sorted(human):
        h = human[pair_id]
        v = h.get("values") or {}
        rr = resolved[pair_id]
        target_type = target_types.get(pair_id, "")
        action = _classify_action(v, rr.get("action_resolution") or {})
        actor = _classify_actor(v, rr.get("actor_resolution") or {})
        order = _classify_order(target_type, v, rr.get("order_resolution") or {})
        classes = [action["class"], actor["class"], order["class"]]
        if "U" in classes:
            overall = "U"
        elif "N" in classes:
            overall = "N"
        elif "A" in classes:
            overall = "A"
        else:
            overall = "H"
        summary[overall] += 1
        summary[f"action:{action['class']}"] += 1
        summary[f"actor:{actor['class']}"] += 1
        summary[f"order:{order['class']}"] += 1
        records.append({
            "pair_id": pair_id,
            "rule_id": rr.get("rule_id") or h.get("rule_id"),
            "process_id": rr.get("process_id") or h.get("process_id"),
            "target_violation_type": target_type,
            "overall_class": overall,
            "action": action,
            "actor": actor,
            "order": order,
        })

    output = {
        "schema_version": "stage3_binding_audit@1.0.0",
        "status": "audit_complete",
        "is_gold": False,
        "human_approved_new_judgments": False,
        "classes": {
            "H": "already direct/complete human-approved surface",
            "A": "human-confirmed candidate; mechanical conversion only",
            "N": "AI substantive judgment without human approval",
            "U": "Rule Record lacks a legal span/relation; cannot fill an ID",
        },
        "summary": dict(summary),
        "records": records,
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    return output


def main() -> int:
    output = build()
    print(json.dumps({"output": str(OUT), "summary": output["summary"]},
                     ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

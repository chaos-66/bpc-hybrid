# -*- coding: utf-8 -*-
"""Build the Stage-3 binding reference from human decisions + AI supplement.

The output keeps every field's provenance.  Human-confirmed fields are marked
``human_approved=true``.  AI-only judgments are written as ``ai_proposal`` or
``ai_proposed_unresolved`` and NEVER as human Gold.  Ineligible order cases are
kept as ``ineligible_no_rule_order``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HUMAN = ROOT / "data/development/stage3_synth/stage3_binding_human_decisions_v1.json"
RESOLVED = ROOT / "data/development/stage3_synth/stage3_binding_resolved_reference_v1.json"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
GOLD_RULES = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"
OUT = ROOT / "data/development/stage3_synth/stage3_binding_reference_v1.json"
OUT_HUMAN_ONLY = ROOT / "data/development/stage3_synth/stage3_binding_reference_human_approved_v1.json"
CORRECTION = ROOT / "data/development/stage3_synth/stage3_binding_rule_record_correction_proposal_v1.json"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _control_items(benchmark: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["pair_id"]): item
        for item in benchmark.get("items") or []
        if item.get("role") == "control"
    }


def build() -> dict[str, Any]:
    human = _load(HUMAN)["records"]
    resolved = {str(r["pair_id"]): r for r in _load(RESOLVED)["records"]}
    benchmark = _load(BENCHMARK)
    controls = _control_items(benchmark)
    gold = _load(GOLD_RULES)

    records: list[dict[str, Any]] = []
    correction_items: list[dict[str, Any]] = []
    for pair_id in sorted(human):
        h = human[pair_id]
        v = h.get("values") or {}
        rr = resolved[pair_id]
        control = controls[pair_id]
        target_type = str(control.get("target_violation_type") or "")
        action_res = rr.get("action_resolution") or {}
        actor_res = rr.get("actor_resolution") or {}
        order_res = rr.get("order_resolution") or {}

        human_action = v.get("action_id")
        if human_action:
            action = {
                "rule_action_id": human_action,
                "rule_action_text": h.get("action_text") or action_res.get("text"),
                "human_approved": True,
                "authority": "human_decision",
                "status": "human_approved",
                "evidence": [],
            }
        elif action_res.get("rule_action_id"):
            action = {
                "rule_action_id": action_res.get("rule_action_id"),
                "rule_action_text": action_res.get("text"),
                "human_approved": False,
                "authority": "ai_proposal",
                "status": action_res.get("status"),
                "reason": action_res.get("reason_zh"),
                "evidence": action_res.get("evidence") or [],
            }
        else:
            action = {
                "rule_action_id": None,
                "rule_action_text": action_res.get("candidate_considered", {}).get("text"),
                "human_approved": False,
                "authority": "ai_proposed_unresolved",
                "status": action_res.get("status") or "unresolved",
                "reason": action_res.get("reason_zh"),
                "evidence": action_res.get("evidence") or [],
            }

        human_actor = v.get("actor_id")
        if human_actor:
            actor = {
                "rule_actor_id": human_actor,
                "rule_actor_text": h.get("actor_span_text") or actor_res.get("text"),
                "expected_lane_id": v.get("expected_lane_id"),
                "executor_name": v.get("process_actor"),
                "human_approved": True,
                "authority": "human_decision",
                "status": "human_approved",
                "evidence": [],
            }
        elif actor_res.get("rule_actor_id"):
            actor = {
                "rule_actor_id": actor_res.get("rule_actor_id"),
                "rule_actor_text": actor_res.get("text"),
                "expected_lane_id": actor_res.get("expected_lane_id") or v.get("expected_lane_id"),
                "executor_name": actor_res.get("executor"),
                "human_approved": False,
                "authority": "ai_proposal",
                "status": actor_res.get("status"),
                "reason": actor_res.get("reason_zh"),
                "evidence": actor_res.get("rule_executor_evidence") or [],
            }
        elif actor_res.get("status") == "inferred_counterparty_executor":
            actor = {
                "rule_actor_id": None,
                "rule_actor_text": actor_res.get("text"),
                "expected_lane_id": actor_res.get("expected_lane_id") or v.get("expected_lane_id"),
                "executor_name": actor_res.get("executor") or v.get("process_actor"),
                "human_approved": False,
                "authority": "ai_proposal",
                "status": "inferred_counterparty_executor",
                "reason": actor_res.get("reason_zh"),
                "right_holder_reference": actor_res.get("right_holder_reference"),
                "evidence": actor_res.get("rule_executor_evidence") or [],
            }
        else:
            actor = {
                "rule_actor_id": None,
                "rule_actor_text": None,
                "expected_lane_id": actor_res.get("expected_lane_id") or v.get("expected_lane_id"),
                "executor_name": actor_res.get("executor") or v.get("process_actor"),
                "human_approved": False,
                "authority": "ai_proposed_unresolved",
                "status": actor_res.get("status") or "unresolved",
                "reason": actor_res.get("reason_zh"),
                "right_holder_reference": actor_res.get("right_holder_reference"),
                "evidence": actor_res.get("rule_executor_evidence") or [],
            }

        if target_type != "out_of_order":
            order = {
                "before_rule_action_id": None,
                "after_rule_action_id": None,
                "human_approved": True,
                "authority": "not_applicable",
                "status": "not_applicable",
                "reason": "target violation is not out_of_order",
            }
        else:
            relation = order_res.get("rule_relation") or {}
            before = relation.get("before_rule_action_id")
            after = relation.get("after_rule_action_id")
            if before and after:
                order = {
                    "before_rule_action_id": before,
                    "after_rule_action_id": after,
                    "human_approved": bool(order_res.get("human_approved")),
                    "authority": order_res.get("authority") or "ai_proposal",
                    "status": order_res.get("status") or "explicit_rule_order",
                    "reason": order_res.get("reason_zh"),
                    "evidence": order_res.get("evidence") or [],
                }
            else:
                order = {
                    "before_rule_action_id": None,
                    "after_rule_action_id": None,
                    "human_approved": False,
                    "authority": "ai_assessment",
                    "status": "ineligible_no_rule_order",
                    "reason": order_res.get("reason_zh") or (
                        "The supplied rule record does not express an explicit "
                        "order relation between the two endpoints."),
                    "process_only_human_candidates": {
                        "before_action_id": v.get("order_before_action_id"),
                        "after_action_id": v.get("order_after_action_id"),
                        "order_scope": v.get("order_scope"),
                    },
                    "evidence": order_res.get("evidence") or [],
                }

        required = {
            "missing_action": [action["human_approved"]],
            "incorrect_actor": [action["human_approved"],
                                actor["human_approved"]],
            "out_of_order": [action["human_approved"],
                             order["human_approved"]],
        }.get(target_type, [action["human_approved"]])
        review_state = "human_approved" if all(required) else "needs_human_approval"

        records.append({
            "pair_id": pair_id,
            "process_id": rr.get("process_id") or control.get("process_id"),
            "rule_id": rr.get("rule_id") or control.get("rule_id"),
            "target_violation_type": target_type,
            "target_activity_id": control.get("grounding", {}).get("target_activity_id"),
            "target_activity_name": None,
            "control": {
                "item_id": control.get("item_id"),
                "bpmn_path": control.get("bpmn_path"),
                "bpmn_sha256": control.get("bpmn_sha256"),
            },
            "action_binding": action,
            "actor_binding": actor,
            "order_binding": order,
            "review_state": review_state,
        })

        if (not action["human_approved"] and action["rule_action_id"] is None):
            correction_items.append({
                "pair_id": pair_id,
                "field": "action",
                "issue": action.get("status"),
                "proposed_correction": None,
                "reason": action.get("reason"),
                "auto_applied": False,
            })
        if (not actor["human_approved"] and actor["rule_actor_id"] is None):
            if actor.get("status") == "inferred_counterparty_executor":
                evidence = actor.get("evidence") or []
                proposed = {
                    "type": "gold_annotation_omission",
                    "field": "actor",
                    "source_span": evidence[0] if evidence else None,
                    "proposed_actor_text": (
                        evidence[0].get("text") if evidence else None),
                    "requires_human_approval": True,
                }
            else:
                proposed = None
            correction_items.append({
                "pair_id": pair_id,
                "field": "actor",
                "issue": actor.get("status"),
                "proposed_correction": proposed,
                "reason": actor.get("reason"),
                "auto_applied": False,
            })
        if target_type == "out_of_order" and not order["human_approved"]:
            correction_items.append({
                "pair_id": pair_id,
                "field": "order",
                "issue": order.get("status"),
                "proposed_correction": None,
                "reason": order.get("reason"),
                "auto_applied": False,
            })

    counts = Counter()
    for row in records:
        counts[f"review_state:{row['review_state']}"] += 1
        for field in ("action_binding", "actor_binding", "order_binding"):
            binding = row[field]
            counts[f"{field}:{'human' if binding['human_approved'] else binding['authority']}"] += 1

    output = {
        "schema_version": "stage3_binding_reference@1.0.0",
        "status": "provisional_ai_assisted_reference",
        "is_gold": False,
        "human_approved_new_judgments": False,
        "requires_human_approval_for_full_benchmark": True,
        "formal_evaluation_reference_ready": False,
        "decision_authority": "human_decisions_preserved_ai_supplement_separated",
        "sources": [
            {"path": str(HUMAN.relative_to(ROOT)).replace("\\", "/"),
             "sha256": _sha256(HUMAN)},
            {"path": str(RESOLVED.relative_to(ROOT)).replace("\\", "/"),
             "sha256": _sha256(RESOLVED)},
            {"path": str(BENCHMARK.relative_to(ROOT)).replace("\\", "/"),
             "sha256": _sha256(BENCHMARK)},
        ],
        "counts": dict(counts),
        "records": records,
    }
    _write(OUT, output)

    human_only_records: list[dict[str, Any]] = []
    for row in records:
        clone = json.loads(json.dumps(row, ensure_ascii=False))
        for field in ("action_binding", "actor_binding", "order_binding"):
            binding = clone[field]
            if not binding.get("human_approved"):
                binding["rule_action_id"] = None
                binding["rule_actor_id"] = None
                binding["expected_lane_id"] = None
                binding["before_rule_action_id"] = None
                binding["after_rule_action_id"] = None
                binding["withheld_from_formal_evaluation"] = True
        human_only_records.append(clone)
    _write(OUT_HUMAN_ONLY, {
        "schema_version": "stage3_binding_reference@1.0.0",
        "status": "human_approved_fields_only",
        "is_gold": False,
        "human_approved_new_judgments": False,
        "formal_evaluation_reference_ready": any(
            r["review_state"] == "human_approved" for r in human_only_records),
        "counts": dict(counts),
        "records": human_only_records,
    })

    _write(CORRECTION, {
        "schema_version": "stage3_binding_rule_record_correction_proposal@1.0.0",
        "status": "proposal_only_not_applied",
        "is_gold": False,
        "policy": ("No span id is fabricated.  Items remain unresolved until "
                   "final human approval; a correction is proposed only when "
                   "the regulation contains a clear omitted semantic element."),
        "items": correction_items,
    })
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    output = build()
    print(json.dumps({
        "output": str(OUT),
        "status": output["status"],
        "counts": output["counts"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

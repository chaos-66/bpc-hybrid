# -*- coding: utf-8 -*-
"""Evaluate automatic grounding AFTER its predictions are persisted.

This evaluator is the first point in the Ours path allowed to read Binding
Reference / benchmark answers.  It never feeds those values back to grounding.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
GROUNDING = ROOT / "outputs/development/stage3_ours_v1/automatic_grounding_predictions_v1.json"
REFERENCE = ROOT / "data/development/stage3_synth/stage3_binding_reference_v1.json"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
OUT_JSON = ROOT / "outputs/reports/stage3_automatic_grounding_evaluation_v1.json"
OUT_MD = ROOT / "outputs/reports/stage3_automatic_grounding_evaluation_v1.md"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rate(numerator: int, denominator: int) -> float | None:
    return (numerator / denominator) if denominator else None


def build() -> dict[str, Any]:
    grounding = _load(GROUNDING)
    reference = {str(r["pair_id"]): r for r in _load(REFERENCE)["records"]}
    benchmark = _load(BENCHMARK)
    bench_controls = {
        str(i["pair_id"]): i for i in benchmark["items"]
        if i.get("role") == "control"
    }
    ground_rows = {str(r["pair_id"]): r for r in grounding.get("rows") or []}

    action_any_top1 = 0
    action_candidate = 0
    action_strong = 0
    action_coverage = 0
    action_unobservable = 0
    actor_lane_coverage = 0
    actor_lane_exact = 0
    actor_lane_human_expected = 0
    order_relation_available = 0
    order_endpoint_coverage = 0
    order_endpoint_exact = 0
    order_unobservable = 0
    rows: list[dict[str, Any]] = []

    for pair_id, ref in sorted(reference.items()):
        ground = ground_rows.get(pair_id) or {}
        target_type = str(ref.get("target_violation_type") or "")
        target_activity = str(ref.get("target_activity_id") or "")
        actions = ground.get("actions") or []
        detector_ids = {str(x) for x in ground.get("detector_activity_ids") or []}
        strong_ids: set[str] = set()
        for action in actions:
            strong_ids.update(str(x) for x in action.get("strong_activity_ids") or [])
        top1_hit = any(str(a.get("predicted_activity_id") or "") == target_activity
                       for a in actions)
        candidate_hit = target_activity in detector_ids
        strong_hit = target_activity in strong_ids
        coverage = bool(detector_ids)
        if top1_hit:
            action_any_top1 += 1
        if candidate_hit:
            action_candidate += 1
        if strong_hit:
            action_strong += 1
        if coverage:
            action_coverage += 1
        else:
            action_unobservable += 1

        lane_map = ground.get("activity_lane_map") or {}
        predicted_lane = lane_map.get(target_activity)
        actor = ref.get("actor_binding") or {}
        expected_lane = actor.get("expected_lane_id")
        lane_exact: bool | None = None
        if target_activity in lane_map:
            actor_lane_coverage += 1
            if expected_lane is not None:
                actor_lane_human_expected += 1
                lane_exact = str(predicted_lane) == str(expected_lane)
                if lane_exact:
                    actor_lane_exact += 1
        else:
            lane_exact = None

        order = ref.get("order_binding") or {}
        relation_available = bool(order.get("before_rule_action_id")
                                 and order.get("after_rule_action_id"))
        order_ground = ground.get("order_predictions") or []
        predicted_before = predicted_after = None
        for relation in order_ground:
            if (str(relation.get("before_rule_action_id"))
                    == str(order.get("before_rule_action_id"))
                    and str(relation.get("after_rule_action_id"))
                    == str(order.get("after_rule_action_id"))):
                predicted_before = relation.get("before_predicted_activity_id")
                predicted_after = relation.get("after_predicted_activity_id")
                break
        if relation_available:
            order_relation_available += 1
            if predicted_before and predicted_after:
                order_endpoint_coverage += 1
                # Process-side endpoints are benchmark-declared; compare only
                # after the grounding file was frozen.
                order_pair = (bench_controls.get(pair_id, {}).get("grounding", {})
                              .get("order_pair") or [])
                if len(order_pair) == 2 and {
                    str(predicted_before), str(predicted_after)
                } == {str(order_pair[0]), str(order_pair[1])}:
                    order_endpoint_exact += 1
        else:
            if target_type == "out_of_order":
                order_unobservable += 1

        rows.append({
            "pair_id": pair_id,
            "target_violation_type": target_type,
            "target_activity_id": target_activity,
            "action_top1_hit": top1_hit,
            "action_candidate_hit": candidate_hit,
            "action_strong_hit": strong_hit,
            "action_coverage": coverage,
            "predicted_lane_id": predicted_lane,
            "expected_lane_id": expected_lane,
            "actor_lane_exact": lane_exact,
            "order_relation_available": relation_available,
            "order_endpoint_coverage": bool(predicted_before and predicted_after),
            "order_endpoint_exact": bool(
                relation_available and predicted_before and predicted_after
                and len(bench_controls.get(pair_id, {}).get("grounding", {})
                        .get("order_pair") or []) == 2
                and {str(predicted_before), str(predicted_after)}
                == set(map(str, bench_controls[pair_id]["grounding"]["order_pair"]))
            ),
        })

    n = len(reference)
    report = {
        "schema_version": "stage3_automatic_grounding_evaluation@1.0.0",
        "method_id": grounding.get("method_id"),
        "status": "complete",
        "items": n,
        "gold_read_after_prediction_persisted": True,
        "binding_reference_read_after_prediction_persisted": True,
        "action_grounding": {
            "any_action_top1_accuracy": _rate(action_any_top1, n),
            "candidate_set_recall": _rate(action_candidate, n),
            "strong_set_recall": _rate(action_strong, n),
            "coverage": _rate(action_coverage, n),
            "unobservable": action_unobservable,
        },
        "actor_lane_grounding": {
            "lane_coverage": _rate(actor_lane_coverage, n),
            "lane_exact_accuracy_on_expected_lanes": _rate(
                actor_lane_exact, actor_lane_human_expected),
            "expected_lane_available": actor_lane_human_expected,
        },
        "order_grounding": {
            "rule_order_reference_available": order_relation_available,
            "endpoint_coverage": _rate(order_endpoint_coverage,
                                       order_relation_available),
            "endpoint_exact_accuracy": _rate(order_endpoint_exact,
                                             order_endpoint_coverage),
            "unobservable_no_rule_order": order_unobservable,
        },
        "rows": rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n",
                       encoding="utf-8", newline="\n")
    lines = [
        "# Automatic grounding evaluation",
        "",
        f"- items: {n}",
        f"- action any-action top1 accuracy: {report['action_grounding']['any_action_top1_accuracy']}",
        f"- action candidate-set recall: {report['action_grounding']['candidate_set_recall']}",
        f"- action strong-set recall: {report['action_grounding']['strong_set_recall']}",
        f"- action coverage: {report['action_grounding']['coverage']}",
        f"- lane coverage: {report['actor_lane_grounding']['lane_coverage']}",
        f"- lane exact accuracy: {report['actor_lane_grounding']['lane_exact_accuracy_on_expected_lanes']}",
        f"- rule-order reference available: {order_relation_available}",
        f"- order endpoint coverage: {report['order_grounding']['endpoint_coverage']}",
        "",
        "The evaluator read the binding reference only after the grounding "
        "predictions had been persisted.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report = build()
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

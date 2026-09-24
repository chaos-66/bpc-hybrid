# -*- coding: utf-8 -*-
"""Full-rule-base Sun/Ours checker without the v3 outer matching gate.

The frozen ``SunScorer`` implements Definitions 4-7.  The historical v3
``SunStyleChecker.check`` first filtered rule records by
``matching_score > tau`` and then evaluated Definitions 5-7 only on the
surviving rules.  The v4 contract forbids that outer gate: Definition 4 ranks
are diagnostic only and every rule record receives all three three-state
signals.

This module reuses the frozen scorer and the frozen ``normalize_sun_signal``
conversion, but applies Definitions 5-7 to every rule record.  It never reads
Gold, a target rule/type/activity, a mutation class, or another BPMN.
"""

from __future__ import annotations

from typing import Any, Mapping

from bpc_hybrid.stage3_sun_style_checker import normalize_sun_signal

TYPES = ("missing_action", "incorrect_actor", "out_of_order")


class NoGateSunChecker:
    """Apply the frozen Sun Definition 5-7 checker to all rule records."""

    def __init__(self, scorer: Any):
        self.scorer = scorer

    def check(self, model: Any,
              rule_records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
        matching: list[dict[str, Any]] = []
        for rule_id, record in sorted(rule_records.items()):
            raw = self.scorer.matching_score(
                list(record.get("actions") or []),
                list(record.get("actors") or []),
                model,
            )
            matching.append({
                "rule_id": str(rule_id),
                "matching_score": float(raw.get("matching_score") or 0.0),
                "action_ratio": float(raw.get("action_ratio") or 0.0),
                "actor_object_ratio": float(raw.get("actor_object_ratio") or 0.0),
                "action_map": _jsonable(raw.get("action_map") or []),
                "actor_object_map": _jsonable(raw.get("actor_object_map") or []),
            })
        matching.sort(key=lambda row: (-row["matching_score"], row["rule_id"]))
        for rank, row in enumerate(matching, start=1):
            row["rank"] = rank
            row["outer_gate_relevant"] = row["matching_score"] > self.scorer.tau
            row["used_for_signal"] = True

        signals_by_rule: dict[str, dict[str, Any]] = {}
        violations: list[dict[str, Any]] = []
        for row in matching:
            rule_id = row["rule_id"]
            record = rule_records[rule_id]
            if record.get("failed"):
                signals = {
                    check_type: {
                        "status": "unknown",
                        "raw_score": None,
                        "denominator": 0,
                        "observable": False,
                        "reason": "stage2_rule_record_failed",
                        "evidence": {
                            "failure_reasons": record.get("failure_reasons") or []
                        },
                    }
                    for check_type in TYPES
                }
            else:
                raw_missing = self.scorer.missing_action(
                    list(record.get("actions") or []), model)
                raw_actor = self.scorer.incorrect_actor(
                    list(record.get("actions") or []),
                    list(record.get("actors") or []),
                    model,
                    list(record.get("actor_action_pairs") or []),
                )
                raw_order = self.scorer.out_of_order(
                    list(record.get("order_relations") or []),
                    list(record.get("actions") or []),
                    model,
                )
                signals = {
                    "missing_action": normalize_sun_signal(
                        "missing_action", raw_missing),
                    "incorrect_actor": normalize_sun_signal(
                        "incorrect_actor", raw_actor),
                    "out_of_order": normalize_sun_signal(
                        "out_of_order", raw_order),
                }
            signals_by_rule[rule_id] = signals
            for check_type in TYPES:
                signal = signals[check_type]
                if signal.get("status") != "violated":
                    continue
                violations.append({
                    "rule_id": rule_id,
                    "violation_type": check_type,
                    "raw_score": signal.get("raw_score"),
                    "denominator": signal.get("denominator"),
                    "observable": bool(signal.get("observable")),
                    "reason": signal.get("reason"),
                })

        return {
            "matching": matching,
            "signals_by_rule": signals_by_rule,
            "violations": violations,
            "violated_types": sorted({v["violation_type"] for v in violations}),
            "checker_policy": {
                "name": "no_gate_full_rule_base_v1",
                "outer_matching_gate_applied": False,
                "matching_used_for_diagnostic_only": True,
                "definitions_applied": ["Def5", "Def6", "Def7"],
                "rules_evaluated": sorted(str(rule_id) for rule_id in rule_records),
            },
        }


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return str(value)


__all__ = ["NoGateSunChecker", "TYPES"]
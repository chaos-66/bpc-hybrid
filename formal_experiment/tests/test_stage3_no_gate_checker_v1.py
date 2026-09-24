# -*- coding: utf-8 -*-
from __future__ import annotations

from bpc_hybrid.sun_stage3.no_gate_checker_v1 import NoGateSunChecker


class _LowMatchingScorer:
    tau = 0.8

    def __init__(self) -> None:
        self.calls: list[str] = []

    def matching_score(self, rule_actions, rule_actors, model):
        return {"matching_score": 0.1, "action_ratio": 0.0,
                "actor_object_ratio": 0.0, "action_map": [], "actor_object_map": []}

    def missing_action(self, rule_actions, model):
        self.calls.append("missing_action")
        return {"score": 1.0, "missing": 1, "denominator": 1, "details": [{"missing": True}]}

    def incorrect_actor(self, rule_actions, rule_actors, model, pairs):
        self.calls.append("incorrect_actor")
        return {"score": None, "denominator": 0, "observable": False,
                "reason": "missing_rule_actor_action_map", "details": []}

    def out_of_order(self, relations, rule_actions, model):
        self.calls.append("out_of_order")
        return {"score": 0.0, "denominator": 0, "satisfied": 0, "violations": 0, "details": []}


def test_low_matching_score_is_still_checked() -> None:
    scorer = _LowMatchingScorer()
    checker = NoGateSunChecker(scorer)
    records = {
        "r1": {"actions": ["provide"], "actors": ["controller"],
               "actor_action_pairs": [], "order_relations": []}
    }
    result = checker.check(object(), records)
    assert scorer.calls == ["missing_action", "incorrect_actor", "out_of_order"]
    assert result["matching"][0]["matching_score"] == 0.1
    assert result["matching"][0]["outer_gate_relevant"] is False
    assert result["matching"][0]["used_for_signal"] is True
    assert result["checker_policy"]["outer_matching_gate_applied"] is False


def test_three_state_normalization_and_failed_record() -> None:
    scorer = _LowMatchingScorer()
    checker = NoGateSunChecker(scorer)
    result = checker.check(object(), {
        "r1": {"actions": ["provide"], "actors": ["controller"],
               "actor_action_pairs": [], "order_relations": []},
        "r2": {"actions": [], "actors": [], "actor_action_pairs": [],
               "order_relations": [], "failed": True,
               "failure_reasons": ["stage2_failed"]},
    })
    signals = result["signals_by_rule"]
    assert signals["r1"]["missing_action"]["status"] == "violated"
    assert signals["r1"]["incorrect_actor"]["status"] == "unknown"
    assert signals["r1"]["out_of_order"]["status"] == "unknown"
    assert all(signals["r2"][kind]["status"] == "unknown" for kind in signals["r2"])
    assert all(signals["r2"][kind]["reason"] == "stage2_rule_record_failed" for kind in signals["r2"])

def test_reference_and_target_fields_do_not_change_predictions() -> None:
    scorer = _LowMatchingScorer()
    checker = NoGateSunChecker(scorer)
    base = {
        "r1": {"actions": ["provide"], "actors": ["controller"],
               "actor_action_pairs": [], "order_relations": []}
    }
    plain = checker.check(object(), base)
    decorated = checker.check(object(), {
        "r1": {
            **base["r1"],
            "reference_state": "violated",
            "target_rule_id": "r1",
            "target_violation_type": "missing_action",
            "mutation_type": "missing_action",
        }
    })
    assert plain["signals_by_rule"] == decorated["signals_by_rule"]
    assert plain["violations"] == decorated["violations"]
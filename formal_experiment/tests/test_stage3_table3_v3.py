# -*- coding: utf-8 -*-
"""Focused acceptance tests for the full-rule-base Stage 3 Table 3 v3 pipeline."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEW_V3 = (
    ROOT / "data/development/stage3_synth/stage3_sun_style_inference_view_v3.json"
)
CASE_MAP_V3 = (
    ROOT / "data/development/stage3_synth/stage3_sun_style_case_map_v3.json"
)
AUDIT_V3 = ROOT / "outputs/reports/stage3_sun_style_benchmark_audit_v3.json"
PREDICTIONS = (
    ROOT / "outputs/development/stage3_table3_v3/predictions.jsonl"
)
REPORT = ROOT / "outputs/reports/stage3_table3_v3.json"
RUNNER = ROOT / "scripts/run_stage3_table3_v3.py"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner_module():
    return _load_module("stage3_table3_v3_runner", RUNNER)


@pytest.fixture(scope="module")
def checker_module():
    sys.path.insert(0, str(ROOT / "src"))
    import bpc_hybrid.stage3_sun_style_checker as module
    return module


def test_v3_inference_view_is_blinded():
    view = _load(VIEW_V3)
    assert view["allowed_item_keys"] == ["case_id", "bpmn_path", "process_id"]
    assert view["safety"]["gold_labels_present"] is False
    assert view["safety"]["rule_id_present"] is False
    assert view["safety"]["target_violation_type_present"] is False
    assert view["safety"]["target_activity_present"] is False
    assert view["safety"]["mutation_type_present"] is False
    for item in view["items"]:
        assert set(item) == {"case_id", "bpmn_path", "process_id"}


def test_case_map_is_separate_and_has_expected_denominators():
    case_map = _load(CASE_MAP_V3)
    assert case_map["counts"]["cases"] == 60
    assert case_map["counts"]["controls"] == 30
    assert case_map["counts"]["variants"] == 30
    assert case_map["counts"]["eligible_pairs"] == 13
    assert case_map["counts"]["unique_control_bpmn"] == 6
    assert case_map["counts"]["duplicate_control_items"] == 24
    assert case_map["counts"]["duplicate_control_items_eligible"] == 7
    assert "contains Gold labels" in case_map["label_read_policy"]


def test_control_audit_marks_order_unavailable():
    audit = _load(AUDIT_V3)
    assert audit["counts"]["pairs"] == 30
    assert audit["counts"]["eligible_missing_action"] == 8
    assert audit["counts"]["eligible_incorrect_actor"] == 5
    assert audit["counts"]["eligible_out_of_order"] == 0
    assert audit["counts"]["out_of_order_unavailable"] == 10
    assert audit["control_compliance"]["full_rule_base_multi_label_gold"] is False


def test_sun_style_checker_ranks_all_and_checks_only_relevant(checker_module):
    class FakeScorer:
        def __init__(self):
            self.calls = []

        def matching_score(self, actions, actors, model):
            key = actions[0]
            score = {"action_a": 0.9, "action_b": 0.5}[key]
            return {
                "matching_score": score,
                "action_ratio": score,
                "actor_object_ratio": 0.0,
                "action_map": [],
                "actor_object_map": [],
            }

        def missing_action(self, actions, model):
            self.calls.append(("missing", actions[0]))
            return {"score": 1.0, "denominator": 1, "details": [{}]}

        def incorrect_actor(self, actions, actors, model, pairs):
            self.calls.append(("actor", actions[0]))
            return {"score": None, "denominator": 0, "observable": False,
                    "reason": "unobservable", "details": []}

        def out_of_order(self, relations, actions, model):
            self.calls.append(("order", actions[0]))
            return {"score": 0.0, "denominator": 0, "details": []}

    scorer = FakeScorer()
    checker = checker_module.SunStyleChecker(scorer, tau=0.8)
    result = checker.check(
        model=object(),
        rule_records={
            "rule_a": {"actions": ["action_a"], "actors": [], "order_relations": []},
            "rule_b": {"actions": ["action_b"], "actors": [], "order_relations": []},
        },
    )
    assert [row["rule_id"] for row in result["matching"]] == ["rule_a", "rule_b"]
    assert result["matching"][0]["relevant"] is True
    assert result["matching"][1]["relevant"] is False
    assert set(result["signals_by_rule"]) == {"rule_a"}
    assert result["violations"] == [{
        "rule_id": "rule_a",
        "violation_type": "missing_action",
        "raw_score": 1.0,
        "denominator": 1,
        "observable": True,
        "reason": None,
    }]
    assert ("missing", "action_b") not in scorer.calls
    assert ("actor", "action_b") not in scorer.calls


def test_v3_predictions_have_no_gold_or_target_fields():
    rows = _load_jsonl(PREDICTIONS)
    assert len(rows) == 180
    methods = {row["method_id"] for row in rows}
    assert methods == {
        "sun_rules_only_full_sun_stage3",
        "ours_direct_llm_full_sun_stage3",
        "winter_2020_native_full_pipeline",
    }
    for row in rows:
        assert "pair_id" not in row
        assert "role" not in row
        assert "target_rule_id" not in row
        assert "target_violation_type" not in row
        assert "gold_violation_type" not in row
        assert "grounding" not in row
        for match in row["matching"]:
            assert set(match) >= {"rank", "rule_id", "matching_score", "relevant"}


def test_v3_report_separates_matching_and_checking():
    report = _load(REPORT)
    assert report["status"] == "complete_target_seeded_full_matching"
    assert report["denominators"]["eligible_pairs"] == 13
    assert report["denominators"]["eligible_out_of_order"] == 0
    assert set(report["matching"]) == set(report["checking_target_after_matching"])
    assert report["acceptance_gates"]["G11_full_rule_base_matching"] is True
    assert report["acceptance_gates"]["G12_relevant_rules_only"] is True
    assert report["acceptance_gates"]["G13_control_compliance"] == (
        "true_for_scoped_target_seed")
    assert report["acceptance_gates"]["complete_multi_label_main_table_publishable"] is False


def test_runner_refuses_to_overwrite_existing_output(tmp_path, runner_module):
    out_dir = tmp_path / "existing"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit):
        runner_module.run(out_dir=out_dir, overwrite=False)

"""Tests for automatic grounding and the Ours detector pipeline."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUNDING = ROOT / "outputs/development/stage3_ours_v1/automatic_grounding_predictions_v1.json"
VIEW = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_inference_view_v1.json"
PREDICTIONS = ROOT / "outputs/development/stage3_ours_v1/predictions.jsonl"
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def test_projection_drops_mutation_answers():
    from bpc_hybrid.stage3_grounding.automatic_rule_process_grounding_v1 import (
        project_benchmark_items,
    )
    item = {
        "item_id": "i", "pair_id": "p", "role": "control",
        "bpmn_path": "x.bpmn", "rule_id": "r", "process_id": "proc",
        "grounding": {"target_activity_id": "secret"},
        "gold_violation_type": "missing_action",
        "target_violation_type": "missing_action",
    }
    projected = project_benchmark_items({"items": [item]})[0]
    assert "grounding" not in projected
    assert "gold_violation_type" not in projected
    assert "target_violation_type" not in projected


def test_inference_view_removes_all_mutation_answers():
    view = _load(VIEW)
    assert view["safety"] == {
        "mutation_answers_present": False,
        "binding_gold_present": False,
        "gold_labels_present": False,
    }
    for item in view["items"]:
        assert set(item) <= {"item_id", "pair_id", "role", "bpmn_path",
                             "rule_id", "process_id"}


def test_grounding_run_has_no_gold_and_has_candidate_recall():
    grounding = _load(GROUNDING)
    assert grounding["gold_read"] is False
    assert grounding["binding_reference_read"] is False
    assert len(grounding["rows"]) == 30
    for row in grounding["rows"]:
        assert "target_activity_id" not in row
        assert "gold_violation_type" not in row
        assert "grounding" not in row
    import evaluate_stage3_automatic_grounding_v1 as evaluator
    report = evaluator.build()
    assert report["action_grounding"]["candidate_set_recall"] == 1.0
    assert report["action_grounding"]["coverage"] == 1.0
    assert report["actor_lane_grounding"]["lane_exact_accuracy_on_expected_lanes"] == 1.0
    assert report["order_grounding"]["rule_order_reference_available"] == 0


def test_ours_predictions_are_gold_blind_and_eligible_metrics_are_perfect():
    rows = _load_jsonl(PREDICTIONS)
    assert len(rows) == 60
    for row in rows:
        assert "gold_violation_type" not in row
        assert "target_violation_type" not in row
        assert "grounding" not in row
    import evaluate_stage3_ours_v1 as evaluator
    report = evaluator.build()
    assert report["overall_eligible"]["items"] == 26
    assert report["overall_eligible"]["macro_f1"] == 1.0
    assert report["overall_eligible"]["micro_f1"]["f1"] == 1.0
    assert report["overall_eligible"]["compliant_specificity"] == 1.0
    assert report["per_violation_type_eligible"]["out_of_order"]["items"] == 0

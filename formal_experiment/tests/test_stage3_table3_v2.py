# -*- coding: utf-8 -*-
"""Focused acceptance tests for the repaired Stage-3 Table 3 v2 pipeline."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEW_V2 = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_inference_view_v2.json"
)
TEXT_V2 = (
    ROOT / "data/development/stage3_synth/stage3_regulation_text_view_v2.json"
)
PREDICTIONS = (
    ROOT / "outputs/development/stage3_table3_v2/predictions.jsonl"
)
REPORT = ROOT / "outputs/reports/stage3_table3_v2.json"
RUNNER = ROOT / "scripts/run_stage3_table3_v2.py"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner_module():
    return _load_module("stage3_table3_v2_runner", RUNNER)


@pytest.fixture(scope="module")
def common_module():
    sys.path.insert(0, str(ROOT / "src"))
    import bpc_hybrid.stage3_table3_v2 as module
    return module


@pytest.fixture(scope="module")
def nlp():
    import spacy
    return spacy.load("en_core_web_sm")


def test_v2_inference_view_has_no_role_or_labels():
    view = _load(VIEW_V2)
    assert view["safety"] == {
        "pair_role_present": False,
        "gold_labels_present": False,
        "mutation_answers_present": False,
    }
    assert "role" not in view["allowed_item_keys"]
    for item in view["items"]:
        assert set(item) <= set(view["allowed_item_keys"])
        assert "role" not in item


def test_forbidden_fields_and_missing_pair_control_do_not_change_prediction(
    tmp_path, runner_module
):
    full_rows = _load_jsonl(PREDICTIONS)
    target_item = next(
        row for row in full_rows
        if row["method_id"] == "ours_direct_llm_frozen_sun_stage3"
        and row["item_id"] == "syn_missing_action_01__variant"
    )
    view = _load(VIEW_V2)
    item = next(i for i in view["items"]
                if i["item_id"] == "syn_missing_action_01__variant")
    poisoned = dict(item)
    poisoned.update({
        "role": "variant",
        "target_violation_type": "missing_action",
        "gold_violation_type": "missing_action",
        "grounding": {"target_activity_id": "sentinel"},
        "expected_lane": "sentinel",
    })
    temp_view = {
        "safety": {
            "pair_role_present": False,
            "gold_labels_present": False,
            "mutation_answers_present": False,
        },
        "items": [poisoned],
    }
    view_path = tmp_path / "view.json"
    view_path.write_text(json.dumps(temp_view), encoding="utf-8")
    out_dir = tmp_path / "out"
    runner_module.run(
        view_path=view_path,
        text_view_path=TEXT_V2,
        stage2_input_path=ROOT / "data/input/gdpr7_stage2_input_v1.json",
        out_dir=out_dir,
        nlp_model="en_core_web_sm",
    )
    one_rows = _load_jsonl(out_dir / "predictions.jsonl")
    target_row = next(
        row for row in one_rows
        if row["method_id"] == "ours_direct_llm_frozen_sun_stage3")
    assert target_row["signals"] == target_item["signals"]


def test_missing_action_comes_from_rule_process_mismatch(common_module, nlp):
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer
    from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity
    sim = WinterSimilarity(nlp)
    scorer = SunScorer(sim, 0.8, 0.8, 0.8, nlp=nlp)
    model = SimpleNamespace(
        actions=[{"id": "A1", "name": "Approve request"}],
        actors=["Controller"],
        actor_sources={"Controller": "pool"},
        action_actor_names={"A1": ["Controller"]},
        business_objects=[],
    )
    raw = scorer.missing_action(["notify the supervisory authority"], model)
    signal = common_module.normalize_sun_signal("missing_action", raw)
    assert raw["score"] == 1.0
    assert signal["status"] == "violated"
    assert signal["reason"] is None


def test_incorrect_actor_comes_from_rule_actor_relation_not_lane(common_module):
    from bpc_hybrid.sun_stage3.sun_scorer import SunScorer

    class ExactSim:
        def text_pair(self, left, right):
            return 1.0 if left == right else 0.0

    scorer = SunScorer(ExactSim(), 0.8, 0.8, 0.8, nlp=None)
    model = SimpleNamespace(
        actions=[{"id": "A1", "name": "notify the authority"}],
        actors=["Processor"],
        actor_sources={"Processor": "pool"},
        action_actor_names={"A1": ["Processor"]},
        business_objects=[],
    )
    raw = scorer.incorrect_actor(
        ["notify the authority"],
        ["Controller"],
        model,
        [{"actor": "Controller", "action": "notify the authority"}],
    )
    signal = common_module.normalize_sun_signal("incorrect_actor", raw)
    assert raw["observable"] is True
    assert raw["score"] == 1.0
    assert signal["status"] == "violated"


def test_empty_or_failed_relations_are_unknown_not_compliant(common_module):
    missing = common_module.normalize_sun_signal(
        "missing_action", {"score": 0.0, "denominator": 0, "details": []})
    actor = common_module.normalize_sun_signal(
        "incorrect_actor",
        {"score": None, "denominator": 0, "observable": False,
         "reason": "empty_rule_actor_denominator"})
    order = common_module.normalize_sun_signal(
        "out_of_order", {"score": 0.0, "denominator": 0, "details": []})
    assert missing["status"] == "unknown"
    assert actor["status"] == "unknown"
    assert order["status"] == "unknown"


def test_evaluator_counts_unknown_as_miss_and_not_tn(common_module):
    benchmark = {
        "benchmark_id": "synthetic",
        "items": [
            {"item_id": "p__control", "pair_id": "p", "role": "control",
             "target_violation_type": "missing_action",
             "gold_violation_type": "compliant"},
            {"item_id": "p__variant", "pair_id": "p", "role": "variant",
             "target_violation_type": "missing_action",
             "gold_violation_type": "missing_action"},
        ],
    }
    eligibility = {
        "schema_version": "eligibility",
        "records": [{"pair_id": "p", "violation_type": "missing_action",
                     "eligible": True}],
    }
    predictions = [
        {"method_id": "m", "item_id": "p__control",
         "signals": {"missing_action": {"status": "unknown"}}},
        {"method_id": "m", "item_id": "p__variant",
         "signals": {"missing_action": {"status": "violated"}}},
    ]
    report = common_module.evaluate_predictions(
        benchmark=benchmark,
        eligibility=eligibility,
        prediction_rows=predictions,
        method_ids=["m"],
    )
    block = report["methods"]["m"]["per_type"]["missing_action"]
    assert block["tp"] == 1
    assert block["fp"] == 0
    assert block["fn"] == 0
    assert block["tn"] == 0
    assert block["unknown_negative"] == 1
    assert block["positive_coverage"] == 1.0
    assert block["negative_coverage"] == 0.0
    assert block["pair_both_correct"] == 0


def test_runner_refuses_to_overwrite_existing_output(tmp_path, runner_module):
    out_dir = tmp_path / "existing"
    out_dir.mkdir()
    (out_dir / "keep.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(SystemExit):
        runner_module.run(out_dir=out_dir, overwrite=False)


def test_v2_report_separates_na_and_records_duplicate_controls():
    report = _load(REPORT)
    assert report["status"] == "complete"
    assert report["denominators"]["eligible_pairs_total"] == 13
    assert report["duplicate_control_audit"]["unique_control_bpmn"] == 6
    assert report["duplicate_control_audit"]["duplicate_control_items"] == 7
    for method in report["methods"].values():
        assert method["per_type"]["out_of_order"]["status"] == (
            "N/A_no_eligible_positive")
        assert method["per_type"]["out_of_order"]["f1"] is None
        assert method["per_type"]["incorrect_actor"]["non_target_evaluation_status"] == (
            "not_evaluated_no_reference_label")


def test_main_v2_methods_do_not_use_legacy_automatic_grounding(common_module):
    assert "automatic_rule_process_grounding_v1" not in common_module.METHODS
    assert set(common_module.METHODS) == {
        "sun_rules_only_frozen_sun_stage3",
        "ours_direct_llm_frozen_sun_stage3",
        "winter_2020_native_wrapper",
    }
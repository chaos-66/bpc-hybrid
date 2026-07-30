"""Exact zero-regression gate and paired config tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from bpc_hybrid.estg150_b0_development import sha256_file
from bpc_hybrid.marker_lexicon_v3_pair import FIELD_ORDER, build_paired_comparison


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/models/estg150_b0_marker_lexicon_v3_paired_v1.json"
OUTPUT = ROOT / "outputs/development/s27_estg150_b0_marker_lexicon_v3_paired_v1"


def _metrics() -> dict:
    item = {
        "ground_truth": 10,
        "extracted": 10,
        "matched_predictions": 5,
        "matched_ground_truth": 5,
        "misclassified": 5,
        "missed": 5,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }
    return {"per_field": {field: copy.deepcopy(item) for field in FIELD_ORDER}}


def test_equal_pair_rejects_without_target_improvement() -> None:
    metrics = _metrics()
    comparison = build_paired_comparison(metrics, copy.deepcopy(metrics))
    assert comparison["gate"]["zero_regression_passed"] is True
    assert comparison["gate"]["target_improvement_passed"] is False
    assert comparison["gate"]["replacement_allowed"] is False
    assert comparison["gate"]["decision"] == "reject_candidate_keep_active_v2"


def test_exact_target_improvement_promotes_when_all_twelve_checks_hold() -> None:
    baseline = _metrics()
    candidate = copy.deepcopy(baseline)
    candidate["per_field"]["condition"]["matched_predictions"] = 6
    comparison = build_paired_comparison(baseline, candidate)
    assert comparison["gate"]["regressions"] == []
    assert comparison["gate"]["target_improvements"] == ["condition.precision"]
    assert comparison["gate"]["replacement_allowed"] is True


def test_any_regression_rejects_even_with_target_improvement() -> None:
    baseline = _metrics()
    candidate = copy.deepcopy(baseline)
    candidate["per_field"]["condition"]["matched_predictions"] = 6
    candidate["per_field"]["actor"]["matched_ground_truth"] = 4
    comparison = build_paired_comparison(baseline, candidate)
    assert comparison["gate"]["regressions"] == ["actor.recall"]
    assert comparison["gate"]["replacement_allowed"] is False


def test_pair_config_pins_baseline_and_frozen_candidate() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    baseline = config["baseline_config"]
    assert sha256_file(ROOT / baseline["path"]) == baseline["sha256"]
    freeze = config["candidate_freeze"]
    for key in ("source_snapshot", "manifest", "provenance_report"):
        assert sha256_file(ROOT / freeze[key]["path"]) == freeze[key]["sha256"]
    assert {
        field: spec["entry_count"] for field, spec in freeze["category_files"].items()
    } == {
        "modality": 7,
        "actor": 8,
        "action": 0,
        "condition": 26,
        "constraint": 41,
        "exception": 5,
    }
    for field, spec in freeze["category_files"].items():
        assert sha256_file(ROOT / spec["path"]) == spec["sha256"], field
    assert config["paired_protocol"]["sole_variable"] == (
        "method.marker_parameter.category_files"
    )


def test_persisted_full_pair_is_hash_complete_and_rejects_v3() -> None:
    manifest = json.loads((OUTPUT / "manifest.json").read_text(encoding="utf-8"))
    comparison = json.loads((OUTPUT / "comparison.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "succeeded_development_not_formal"
    assert manifest["sole_variable"] == "marker_parameter_category_files"
    assert manifest["safety"]["gold_read_only"] is True
    assert manifest["safety"]["llm_call_count"] == 0
    assert manifest["gate"] == comparison["gate"]
    assert comparison["gate"]["decision"] == "reject_candidate_keep_active_v2"
    assert comparison["gate"]["replacement_allowed"] is False
    assert len(comparison["gate"]["regressions"]) == 8
    for spec in manifest["artifacts"].values():
        assert sha256_file(OUTPUT / spec["path"]) == spec["sha256"]


def test_paired_baseline_exactly_reproduces_existing_paper_spec_metrics() -> None:
    paired = json.loads((OUTPUT / "baseline_metrics.json").read_text(encoding="utf-8"))
    existing = json.loads(
        (
            ROOT
            / "outputs/development/s27_estg150_b0_sun_paper_v1/metrics.json"
        ).read_text(encoding="utf-8")
    )
    assert paired == existing

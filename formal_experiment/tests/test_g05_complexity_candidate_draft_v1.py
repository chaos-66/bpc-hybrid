"""Synthetic boundary tests for the G0.5 complexity candidate classifier.

The candidate contract is `draft_not_frozen` and applies ONLY to future
complex corpora; these tests use synthetic feature records and assert
deterministic L1/L2/L3 classification, boundary values, conflict handling
and fail-closed behaviour. Nothing here freezes the contract.
"""

from __future__ import annotations

from typing import Any

import pytest

from bpc_hybrid.g05_complexity_candidate import (
    DraftNotFrozenViolationError,
    G05ClassificationError,
    InvalidFeatureValueError,
    MissingFeatureError,
    UnknownFeatureError,
    classify,
    load_config,
)

L1_FEATURES: dict[str, Any] = {
    "text_length": 150,
    "clause_count": 2,
    "dependency_depth": 3,
    "actor_count": 1,
    "action_count": 2,
    "condition_count": 1,
    "constraint_count": 1,
    "exception_count": 0,
    "nesting_depth": 1,
    "passive_voice_count": 0,
    "implicit_actor_count": 0,
    "cross_reference_count": 0,
    "language_markers": "original",
    "bpmn_activities": 8,
    "bpmn_gateways": 2,
    "bpmn_flows": 10,
    "bpmn_pools_lanes": 1,
    "bpmn_parallel_branches": 1,
    "bpmn_cycles": 0,
}


def _with(**overrides: Any) -> dict[str, Any]:
    features = dict(L1_FEATURES)
    features.update(overrides)
    return features


def test_contract_is_draft_not_frozen() -> None:
    config = load_config()
    assert config["status"] == "draft_not_frozen"
    assert config["retrospective_use_forbidden"] is True


def test_l1_features_classify_l1() -> None:
    result = classify(_with())
    assert result["level"] == "L1"
    assert result["matched_hard_triggers"] == []
    assert result["l1_violations"] == []
    assert result["status"] == "draft_not_frozen"


def test_l1_boundary_exact_maxima_classify_l1() -> None:
    result = classify(_with(
        text_length=200, clause_count=3, dependency_depth=4,
        actor_count=2, action_count=2, condition_count=2,
        constraint_count=1, exception_count=1, nesting_depth=1,
        passive_voice_count=1, implicit_actor_count=1,
        cross_reference_count=1, bpmn_activities=10, bpmn_gateways=3,
        bpmn_flows=15, bpmn_pools_lanes=2, bpmn_parallel_branches=1,
        bpmn_cycles=0))
    assert result["level"] == "L1"


def test_one_maximum_exceeded_yields_l2() -> None:
    result = classify(_with(clause_count=4))
    assert result["level"] == "L2"
    assert any(v.startswith("clause_count=") for v in result["l1_violations"])


def test_hard_trigger_dependency_depth_yields_l3() -> None:
    result = classify(_with(dependency_depth=9))
    assert result["level"] == "L3"
    assert "dependency_depth_min" in result["matched_hard_triggers"]


def test_hard_trigger_cross_reference_yields_l3() -> None:
    result = classify(_with(cross_reference_count=4))
    assert result["level"] == "L3"
    assert "cross_reference_count_min" in result["matched_hard_triggers"]


def test_hard_trigger_bpmn_activities_yields_l3() -> None:
    result = classify(_with(bpmn_activities=30))
    assert result["level"] == "L3"


def test_mixed_language_markers_yield_l3() -> None:
    result = classify(_with(language_markers="mixed"))
    assert result["level"] == "L3"
    assert "language_markers=mixed" in result["matched_hard_triggers"]


def test_conflict_hard_trigger_overrides_l1_satisfaction() -> None:
    # everything L1-satisfying except one L3 hard trigger -> L3 wins
    result = classify(_with(bpmn_cycles=3))
    assert result["level"] == "L3"


def test_partial_l1_without_trigger_yields_l2() -> None:
    result = classify(_with(text_length=250, cross_reference_count=2))
    assert result["level"] == "L2"


def test_deterministic_same_input_same_output() -> None:
    assert classify(_with()) == classify(_with())


def test_input_order_does_not_matter() -> None:
    features_a = dict(L1_FEATURES)
    features_b = dict(reversed(list(L1_FEATURES.items())))
    assert classify(features_a) == classify(features_b)


def test_missing_feature_fails_closed() -> None:
    features = dict(L1_FEATURES)
    del features["dependency_depth"]
    with pytest.raises(MissingFeatureError) as exc:
        classify(features)
    assert exc.value.code == "G05_MISSING_FEATURE"
    assert "dependency_depth" in exc.value.detail


def test_unknown_feature_fails_closed() -> None:
    with pytest.raises(UnknownFeatureError) as exc:
        classify(_with(bogus_feature=1))
    assert exc.value.code == "G05_UNKNOWN_FEATURE"


def test_negative_value_fails_closed() -> None:
    with pytest.raises(InvalidFeatureValueError) as exc:
        classify(_with(clause_count=-1))
    assert exc.value.code == "G05_INVALID_FEATURE_VALUE"


def test_wrong_type_fails_closed() -> None:
    with pytest.raises(InvalidFeatureValueError) as exc:
        classify(_with(clause_count="3"))
    assert exc.value.code == "G05_INVALID_FEATURE_VALUE"


def test_invalid_language_marker_fails_closed() -> None:
    with pytest.raises(InvalidFeatureValueError) as exc:
        classify(_with(language_markers="bilingual"))
    assert exc.value.code == "G05_INVALID_FEATURE_VALUE"


def test_frozen_config_refuses_classification() -> None:
    config = load_config()
    config = dict(config)
    config["status"] = "frozen"
    with pytest.raises(DraftNotFrozenViolationError) as exc:
        classify(_with(), config=config)
    assert exc.value.code == "G05_DRAFT_NOT_FROZEN_VIOLATION"


def test_retrospective_flag_required() -> None:
    config = load_config()
    config = dict(config)
    config["retrospective_use_forbidden"] = False
    with pytest.raises(DraftNotFrozenViolationError):
        classify(_with(), config=config)


def test_error_codes_are_machine_decodable() -> None:
    for trigger in (
            lambda: classify(_with(clause_count=-1)),
            lambda: classify(_with(bogus=1)),
            lambda: classify(_with(dependency_depth=None))):
        with pytest.raises(G05ClassificationError) as exc:
            trigger()
        assert isinstance(exc.value.code, str)
        assert exc.value.code.startswith("G05_")

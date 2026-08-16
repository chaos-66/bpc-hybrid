"""Synthetic boundary tests for the G0.5 complexity candidate classifier.

The candidate contract is `draft_not_frozen` and applies ONLY to future
complex corpora; these tests use synthetic feature records and assert
deterministic L1/L2/L3 classification, boundary values, conflict handling
and fail-closed behaviour. Nothing here freezes the contract.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from bpc_hybrid.g05_complexity_candidate import (
    DraftNotFrozenViolationError,
    G05ClassificationError,
    InvalidFeatureValueError,
    MissingFeatureError,
    UnknownFeatureError,
    classify,
    derive_promotion_readiness,
    load_config,
    validate_frozen_application,
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


# ---------------------------------------------------------------------------
# Promotion readiness (current disk state + future frozen path, synthetic)
# ---------------------------------------------------------------------------
def test_current_promotion_readiness_is_draft_not_frozen(tmp_path: Path) -> None:
    import json
    from pathlib import Path as _Path
    root = tmp_path
    cfg_dir = root / "configs"
    cfg_dir.mkdir(parents=True)
    cfg_dir.joinpath("g05_complexity_candidate_draft_v1.json").write_text(
        json.dumps(load_config()), encoding="utf-8")
    readiness = derive_promotion_readiness(root)
    assert readiness["g0_5_status"] == "draft_not_frozen"
    assert readiness["promotion_ready_for_application"] is False
    assert any("user authorization manifest" in m
               for m in readiness["missing"])
    assert readiness["authorization_manifests_found"] == []
    assert readiness["frozen_configs_found"] == []
    assert readiness["prior_results_found"] == []
    assert readiness["preregistration_claim_allowed"] is False


def _synthetic_draft_config() -> dict:
    return dict(load_config())


def _synthetic_frozen_config() -> dict:
    config = dict(_synthetic_draft_config())
    config["status"] = "frozen"
    config["frozen_before_new_results"] = True
    config["retrospective_use_forbidden"] = True
    return config


def _auth_manifest(draft: dict, frozen: dict, sentence: str = "I authorize "
                   "freezing the G0.5 complexity contract") -> dict:
    import hashlib
    return {
        "manifest_id": "syn-g05-auth-1",
        "draft_config_sha256": hashlib.sha256(json.dumps(
            draft, sort_keys=True).encode("utf-8")).hexdigest(),
        "approved_frozen_config_sha256": hashlib.sha256(json.dumps(
            frozen, sort_keys=True).encode("utf-8")).hexdigest(),
        "scope": "future external complex corpora only; never "
                 "retrospective on S2.10",
        "authorization_sentence": sentence,
    }


def test_future_frozen_application_valid_with_synthetic_fixture() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    manifest = _auth_manifest(draft, frozen)
    result = validate_frozen_application(draft, frozen, manifest,
                                         corpus_has_prior_results=False)
    assert result["frozen_application_valid"] is True
    assert result["g0_5_status"] == "frozen"
    assert result["frozen_before_new_results"] is True
    assert result["preregistration_claim_allowed"] is True


def test_frozen_application_rejects_unbound_manifest_hash() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    manifest = _auth_manifest(draft, frozen)
    manifest["draft_config_sha256"] = "00" * 64
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "draft config hash" in exc.value.message


def test_frozen_application_rejects_draft_status_config() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    frozen["status"] = "draft_not_frozen"
    manifest = _auth_manifest(draft, frozen)
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "frozen" in exc.value.message


def test_frozen_application_rejects_missing_frozen_before_flag() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    del frozen["frozen_before_new_results"]
    manifest = _auth_manifest(draft, frozen)
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert exc.value.code == "G05_CLASSIFICATION_ERROR"


def test_frozen_application_rejects_prior_results() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    manifest = _auth_manifest(draft, frozen)
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    corpus_has_prior_results=True)
    assert "prior prediction/result" in exc.value.message


def test_frozen_application_rejects_retrospective_flag_missing() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    del frozen["retrospective_use_forbidden"]
    manifest = _auth_manifest(draft, frozen)
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "retrospective" in exc.value.message


def test_frozen_application_rejects_empty_sentence() -> None:
    draft = _synthetic_draft_config()
    frozen = _synthetic_frozen_config()
    manifest = _auth_manifest(draft, frozen, sentence="   ")
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "authorization sentence" in exc.value.message

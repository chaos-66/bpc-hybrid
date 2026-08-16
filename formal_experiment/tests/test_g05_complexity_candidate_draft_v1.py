"""Synthetic boundary tests for the G0.5 complexity candidate classifier
and the FUTURE frozen-application path (v5 raw-byte hash domain).

The candidate contract is `draft_not_frozen` and applies ONLY to future
complex corpora; these tests use synthetic feature records and synthetic
fixture files in pytest tmp directories. The authorization hash domain is
the RAW FILE BYTES (never a re-serialized semantic dict). Nothing here
freezes the contract or creates real authorization manifests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.g05_complexity_candidate import (
    DraftNotFrozenViolationError,
    G05ClassificationError,
    InvalidFeatureValueError,
    MissingFeatureError,
    UnknownFeatureError,
    classify,
    classify_frozen,
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


def _raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Draft classifier
# ---------------------------------------------------------------------------
def test_contract_is_draft_not_frozen() -> None:
    config = load_config()
    assert config["status"] == "draft_not_frozen"
    assert config["retrospective_use_forbidden"] is True


def test_l1_features_classify_l1() -> None:
    result = classify(_with())
    assert result["level"] == "L1"
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


def test_hard_trigger_dependency_depth_yields_l3() -> None:
    result = classify(_with(dependency_depth=9))
    assert result["level"] == "L3"
    assert "dependency_depth_min" in result["matched_hard_triggers"]


def test_hard_trigger_cross_reference_yields_l3() -> None:
    result = classify(_with(cross_reference_count=4))
    assert result["level"] == "L3"


def test_mixed_language_markers_yield_l3() -> None:
    result = classify(_with(language_markers="mixed"))
    assert result["level"] == "L3"


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


def test_unknown_feature_fails_closed() -> None:
    with pytest.raises(UnknownFeatureError) as exc:
        classify(_with(bogus_feature=1))
    assert exc.value.code == "G05_UNKNOWN_FEATURE"


def test_negative_value_fails_closed() -> None:
    with pytest.raises(InvalidFeatureValueError) as exc:
        classify(_with(clause_count=-1))
    assert exc.value.code == "G05_INVALID_FEATURE_VALUE"


def test_frozen_config_refuses_plain_classify() -> None:
    config = load_config()
    config = dict(config)
    config["status"] = "frozen"
    with pytest.raises(DraftNotFrozenViolationError) as exc:
        classify(_with(), config=config)
    assert exc.value.code == "G05_DRAFT_NOT_FROZEN_VIOLATION"


# ---------------------------------------------------------------------------
# Current promotion readiness (real project disk state)
# ---------------------------------------------------------------------------
def test_current_project_promotion_readiness_is_draft_not_frozen() -> None:
    from pathlib import Path as _Path
    import bpc_hybrid.g05_complexity_candidate as g05
    root = _Path(g05.__file__).resolve().parents[2]
    readiness = derive_promotion_readiness(root)
    assert readiness["g0_5_status"] == "draft_not_frozen"
    assert readiness["promotion_ready_for_application"] is False
    assert any("user authorization manifest" in m
               for m in readiness["missing"])
    assert readiness["authorization_manifests_found"] == []
    assert readiness["frozen_configs_found"] == []
    assert readiness["prior_results_found"] == []
    assert readiness["validated_asset_combinations"] == 0
    assert readiness["preregistration_claim_allowed"] is False


def test_derive_promotion_readiness_ignores_bare_filenames(
        tmp_path: Path) -> None:
    # A file whose NAME matches the globs but whose content is not a valid
    # frozen config / manifest must NOT make readiness true.
    root = tmp_path
    cfg_dir = root / "configs"
    cfg_dir.mkdir(parents=True)
    cfg_dir.joinpath("g05_complexity_candidate_draft_v1.json").write_text(
        json.dumps(load_config()), encoding="utf-8")
    cfg_dir.joinpath("g05_complexity_candidate_frozen_v1.json").write_text(
        json.dumps({"status": "not_even_frozen"}), encoding="utf-8")
    (root / "outputs" / "reports").mkdir(parents=True)
    (root / "outputs" / "reports" /
     "g05_freeze_authorization_v1.manifest.json").write_text(
        json.dumps({"bogus": True}), encoding="utf-8")
    readiness = derive_promotion_readiness(root)
    assert readiness["promotion_ready_for_application"] is False
    assert readiness["validated_asset_combinations"] == 0
    assert any("VALIDATED" in m for m in readiness["missing"])


# ---------------------------------------------------------------------------
# FUTURE frozen-application path: RAW BYTE hash domain (v5)
# ---------------------------------------------------------------------------
def _write_config(path: Path, status: str, **extra: Any) -> None:
    doc = dict(load_config())
    doc["status"] = status
    doc.update(extra)
    path.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                     .encode("utf-8"))


def _real_draft_config_path() -> Path:
    import bpc_hybrid.g05_complexity_candidate as g05
    from pathlib import Path as _Path
    root = _Path(g05.__file__).resolve().parents[2]
    return root / "configs" / "g05_complexity_candidate_draft_v1.json"


def _make_frozen_fixture(tmp_path: Path) -> tuple[Path, Path, Path, str]:
    # The draft config is the REAL project draft config copied byte-for-byte,
    # so its raw-byte hash IS the dry-run G4 hash domain (61938c99…).
    draft_path = tmp_path / "draft.json"
    draft_path.write_bytes(_real_draft_config_path().read_bytes())
    frozen_path = tmp_path / "frozen.json"
    manifest_path = tmp_path / "manifest.json"
    _write_config(frozen_path, "frozen",
                  frozen_before_new_results=True,
                  retrospective_use_forbidden=True)
    manifest = {
        "manifest_id": "syn-g05-auth-1",
        "draft_config_sha256": _raw_sha(draft_path),
        "approved_frozen_config_sha256": _raw_sha(frozen_path),
        "scope": "future external complex corpora only; never "
                 "retrospective on S2.10",
        "authorization_sentence": "synthetic G4 dry-run fixture",
    }
    manifest_path.write_bytes(json.dumps(manifest, ensure_ascii=False,
                                         indent=2).encode("utf-8"))
    return draft_path, frozen_path, manifest_path, _raw_sha(manifest_path)


def test_draft_config_raw_byte_hash_is_61938c99() -> None:
    import bpc_hybrid.g05_complexity_candidate as g05
    from pathlib import Path as _Path
    root = _Path(g05.__file__).resolve().parents[2]
    path = root / "configs" / "g05_complexity_candidate_draft_v1.json"
    assert _raw_sha(path) == \
        "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"


def test_future_frozen_application_valid_with_raw_byte_hashes(
        tmp_path: Path) -> None:
    draft, frozen, manifest, manifest_sha = _make_frozen_fixture(tmp_path)
    result = validate_frozen_application(draft, frozen, manifest)
    assert result["frozen_application_valid"] is True
    assert result["draft_config_sha256"] == _raw_sha(draft)
    assert result["approved_frozen_config_sha256"] == _raw_sha(frozen)
    assert result["validation_token"] == manifest_sha
    # the validation chain accepts the EXACT raw-byte hash domain of the
    # dry-run G4 sentence (61938c99…) — the semantic re-serialization hash
    # 51a6e4fe… must never be used as the authorization hash.
    assert result["draft_config_sha256"].startswith("61938c99")


def test_future_frozen_application_rejects_semantic_hash(tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    # Rebind the manifest to the OLD semantic hash domain (json.dumps of
    # the dict) — the validator must reject it.
    semantic = hashlib.sha256(json.dumps(
        json.loads(draft.read_text(encoding="utf-8")),
        sort_keys=True).encode("utf-8")).hexdigest()
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["draft_config_sha256"] = semantic
    manifest.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "RAW BYTE hash" in exc.value.message


def test_future_frozen_application_rejects_unbound_manifest_hash(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["draft_config_sha256"] = "00" * 64
    manifest.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "draft config RAW BYTE hash" in exc.value.message


def test_future_frozen_application_rejects_draft_status_config(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _write_config(frozen, "draft_not_frozen")
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["approved_frozen_config_sha256"] = _raw_sha(frozen)
    manifest.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "frozen" in exc.value.message


def test_future_frozen_application_rejects_missing_frozen_before_flag(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _write_config(frozen, "frozen",
                  retrospective_use_forbidden=True)
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["approved_frozen_config_sha256"] = _raw_sha(frozen)
    manifest.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "frozen_before_new_results" in exc.value.message


def test_future_frozen_application_rejects_retrospective_flag_missing(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    doc = dict(load_config())
    doc.pop("retrospective_use_forbidden")
    doc["status"] = "frozen"
    doc["frozen_before_new_results"] = True
    frozen.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                       .encode("utf-8"))
    mdoc = json.loads(manifest.read_text(encoding="utf-8"))
    mdoc["approved_frozen_config_sha256"] = _raw_sha(frozen)
    manifest.write_bytes(json.dumps(mdoc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "retrospective" in exc.value.message


def test_future_frozen_application_rejects_prior_results(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    corpus_has_prior_results=True)
    assert "prior prediction/result" in exc.value.message


def test_future_frozen_application_rejects_empty_sentence(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["authorization_sentence"] = "   "
    manifest.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "authorization sentence" in exc.value.message


def test_future_frozen_application_rejects_missing_scope(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    doc["scope"] = ""
    manifest.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                         .encode("utf-8"))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest)
    assert "scope" in exc.value.message


# ---------------------------------------------------------------------------
# classify_frozen: only a complete validation result unlocks frozen config
# ---------------------------------------------------------------------------
def test_classify_frozen_requires_complete_validation_result(
        tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), frozen, {"frozen_application_valid": True})
    assert "validation token" in exc.value.message


def test_classify_frozen_accepts_validated_result(tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    result = validate_frozen_application(draft, frozen, manifest)
    out = classify_frozen(_with(), frozen, result)
    assert out["level"] == "L1"
    assert out["status"] == "frozen"


def test_classify_frozen_rejects_wrong_file(tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    other = tmp_path / "other.json"
    doc = dict(load_config())
    doc["status"] = "frozen"
    doc["frozen_before_new_results"] = True
    doc["retrospective_use_forbidden"] = True
    doc["status_reason"] = "different bytes than the validated frozen file"
    other.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                      .encode("utf-8"))
    result = validate_frozen_application(draft, frozen, manifest)
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), other, result)
    assert "does not bind THIS frozen config" in exc.value.message


def test_classify_frozen_rejects_handbuilt_result(tmp_path: Path) -> None:
    draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    # A hand-built result with a malformed token must be rejected.
    fake = {
        "frozen_application_valid": True,
        "validation_token": "not-a-64-hex-token",
        "approved_frozen_config_sha256": _raw_sha(frozen),
    }
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), frozen, fake)
    assert "validation token" in exc.value.message
    # A hand-built result with a well-formed token but a WRONG config hash
    # must be rejected as well.
    fake2 = {
        "frozen_application_valid": True,
        "validation_token": "11" * 32,
        "approved_frozen_config_sha256": "22" * 32,
    }
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), frozen, fake2)
    assert "does not bind THIS frozen config" in exc.value.message

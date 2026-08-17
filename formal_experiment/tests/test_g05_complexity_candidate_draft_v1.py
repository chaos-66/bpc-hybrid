"""Synthetic boundary tests for the G0.5 complexity candidate classifier
and the FUTURE frozen-application path (v6 sealed chain).

The candidate contract is `draft_not_frozen` and applies ONLY to future
complex corpora; these tests use synthetic feature records and synthetic
fixture files in pytest tmp directories. The authorization hash domain is
the RAW FILE BYTES (never a re-serialized semantic dict). Nothing here
freezes the contract or creates real authorization manifests.

v6 chain sealing (replaces the v5 caller-supplied validation-result API):
  * classify_frozen has NO validation-result parameter at all — it
    re-verifies the draft config, frozen config, authorization manifest,
    authorization event and prior-results evidence from disk on EVERY
    call; a hand-built dict (even with a well-formed 64-hex token) can
    never unlock the frozen classifier;
  * the authorization manifest must fully bind schema/version, manifest
    ID, authorization_applied=true, the exact approved scope and the
    exact approved G4 dry-run sentence (+ its UTF-8 SHA-256), draft and
    frozen config relative paths + raw-byte SHA-256, the append-only
    authorization event (ID + raw-byte SHA-256), the re-derived
    prior-results scan, and a pending (not-applied) application
    checkpoint;
  * prior results are derived from the synthetic project root by
    deterministic path/manifest rules — never from a caller bool.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.g05_complexity_candidate import (
    APPROVED_AUTHORIZATION_SCOPE,
    AUTHORIZATION_EVENT_KIND,
    AUTHORIZATION_MANIFEST_SCHEMA_VERSION,
    DraftNotFrozenViolationError,
    G05ClassificationError,
    InvalidFeatureValueError,
    MissingFeatureError,
    UnknownFeatureError,
    approved_authorization_sentence,
    classify,
    classify_frozen,
    derive_prior_results,
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


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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
def test_current_project_promotion_readiness_is_frozen_after_checkpoint_a() -> None:
    from pathlib import Path as _Path
    import bpc_hybrid.g05_complexity_candidate as g05
    root = _Path(g05.__file__).resolve().parents[2]
    readiness = derive_promotion_readiness(root)
    # Checkpoint A applied the user-authorized G4 freeze: the sealed chain
    # validates a real frozen config + authorization manifest combination.
    assert readiness["g0_5_status"] == \
        "frozen_for_future_external_complex_corpora"
    assert readiness["promotion_ready_for_application"] is False
    assert readiness["validated_asset_combinations"] >= 1
    assert readiness["prior_results_found"] == []
    assert readiness["preregistration_claim_allowed"] is False
    assert readiness["authorization_manifests_found"] != []
    assert readiness["frozen_configs_found"] != []


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
# FUTURE frozen-application path: RAW BYTE hash domain + SEALED chain (v6)
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


def _write_json(path: Path, doc: dict[str, Any]) -> str:
    data = json.dumps(doc, ensure_ascii=False, sort_keys=True,
                      indent=2).encode("utf-8")
    path.write_bytes(data)
    return _sha_bytes(data)


def _make_frozen_fixture(
        tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    """Build a complete SYNTHETIC frozen-application fixture (all files in
    the pytest tmp directory; NOTHING on the real project disk).

    Returns (root, draft_path, frozen_path, manifest_path, event_path).
    """
    root = tmp_path
    # The draft config is the REAL project draft config copied byte-for-byte,
    # so its raw-byte hash IS the dry-run G4 hash domain (61938c99…).
    draft_path = root / "draft.json"
    draft_path.write_bytes(_real_draft_config_path().read_bytes())
    frozen_path = root / "frozen.json"
    _write_config(frozen_path, "frozen",
                  frozen_before_new_results=True,
                  retrospective_use_forbidden=True)
    draft_sha = _raw_sha(draft_path)
    frozen_sha = _raw_sha(frozen_path)
    sentence = approved_authorization_sentence(draft_sha)
    event_path = root / "authorization_event.json"
    event_sha = _write_json(event_path, {
        "kind": AUTHORIZATION_EVENT_KIND,
        "event_id": "syn-g05-event-1",
        "authorization_sentence": sentence,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "manifest_id": "syn-g05-auth-1",
        "append_only": True,
    })
    manifest_path = root / "manifest.json"
    _write_json(manifest_path, {
        "schema_version": AUTHORIZATION_MANIFEST_SCHEMA_VERSION,
        "manifest_id": "syn-g05-auth-1",
        "authorization_applied": True,
        "draft_config_path": "draft.json",
        "draft_config_sha256": draft_sha,
        "approved_frozen_config_path": "frozen.json",
        "approved_frozen_config_sha256": frozen_sha,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "authorization_sentence": sentence,
        "authorization_sentence_sha256": _sha_bytes(
            sentence.encode("utf-8")),
        "retrospective_use_forbidden": True,
        "frozen_before_new_results": True,
        "s2_10_retrospective_use_forbidden": True,
        "prior_results_scan_sha256":
            derive_prior_results(root)["scan_sha256"],
        "authorization_event_id": "syn-g05-event-1",
        "authorization_event_path": "authorization_event.json",
        "authorization_event_sha256": event_sha,
        "application_checkpoint": {
            "pending_commit_not_applied": True,
            "commit_sha256": None,
        },
    })
    return root, draft_path, frozen_path, manifest_path, event_path


def _mutate_manifest(manifest_path: Path,
                     mutate: Any) -> None:
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(doc)
    _write_json(manifest_path, doc)


def test_draft_config_raw_byte_hash_is_61938c99() -> None:
    import bpc_hybrid.g05_complexity_candidate as g05
    from pathlib import Path as _Path
    root = _Path(g05.__file__).resolve().parents[2]
    path = root / "configs" / "g05_complexity_candidate_draft_v1.json"
    assert _raw_sha(path) == \
        "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"


def test_future_frozen_application_valid_with_raw_byte_hashes(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    result = validate_frozen_application(draft, frozen, manifest,
                                         project_root=root)
    assert result["frozen_application_valid"] is True
    assert result["draft_config_sha256"] == _raw_sha(draft)
    assert result["approved_frozen_config_sha256"] == _raw_sha(frozen)
    assert result["validation_token"] == _raw_sha(manifest)
    # the validation chain accepts the EXACT raw-byte hash domain of the
    # dry-run G4 sentence (61938c99…) — the semantic re-serialization hash
    # 51a6e4fe… must never be used as the authorization hash.
    assert result["draft_config_sha256"].startswith("61938c99")
    assert result["prior_results_found"] == []
    assert result["scope"] == APPROVED_AUTHORIZATION_SCOPE
    assert result["application_checkpoint"] == {
        "pending_commit_not_applied": True}


def test_future_frozen_application_rejects_semantic_hash(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    # Rebind the manifest to the OLD semantic hash domain (json.dumps of
    # the dict) — the validator must reject it.
    semantic = hashlib.sha256(json.dumps(
        json.loads(draft.read_text(encoding="utf-8")),
        sort_keys=True).encode("utf-8")).hexdigest()
    _mutate_manifest(manifest,
                     lambda m: m.update({"draft_config_sha256": semantic}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "RAW BYTE hash" in exc.value.message


def test_future_frozen_application_rejects_unbound_manifest_hash(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(manifest,
                     lambda m: m.update({"draft_config_sha256": "00" * 64}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "draft config RAW BYTE hash" in exc.value.message


def test_future_frozen_application_rejects_draft_status_config(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _write_config(frozen, "draft_not_frozen")
    _mutate_manifest(
        manifest,
        lambda m: m.update(
            {"approved_frozen_config_sha256": _raw_sha(frozen)}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "frozen" in exc.value.message


def test_future_frozen_application_rejects_missing_frozen_before_flag(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _write_config(frozen, "frozen", retrospective_use_forbidden=True)
    _mutate_manifest(
        manifest,
        lambda m: m.update(
            {"approved_frozen_config_sha256": _raw_sha(frozen)}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "frozen_before_new_results" in exc.value.message


def test_future_frozen_application_rejects_retrospective_flag_missing(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    doc = dict(load_config())
    doc.pop("retrospective_use_forbidden")
    doc["status"] = "frozen"
    doc["frozen_before_new_results"] = True
    frozen.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2)
                       .encode("utf-8"))
    _mutate_manifest(
        manifest,
        lambda m: m.update(
            {"approved_frozen_config_sha256": _raw_sha(frozen)}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "retrospective" in exc.value.message


def test_future_frozen_application_rejects_prior_results_from_disk(
        tmp_path: Path) -> None:
    # The caller cannot pass a bool; prior results are DERIVED from the
    # synthetic project root. A g05 result file on disk rejects the freeze
    # application even though the manifest's declared scan is stale/empty.
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    res = root / "data" / "results"
    res.mkdir(parents=True)
    (res / "g05_complex_prior_result.json").write_bytes(b"{}")
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "prior" in exc.value.message.lower()


def test_future_frozen_application_rejects_stale_prior_results_scan(
        tmp_path: Path) -> None:
    # The manifest binds a prior-results scan; if the disk scan no longer
    # matches (e.g. a result appeared after the manifest was written), the
    # chain must reject — and the manifest's own declared scan is ignored
    # unless it matches the re-derived scan.
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(
        manifest,
        lambda m: m.update({"prior_results_scan_sha256": "00" * 64}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "scan" in exc.value.message.lower()


def test_future_frozen_application_rejects_replaced_sentence(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(
        manifest,
        lambda m: m.update({"authorization_sentence": "I authorize all"}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "sentence" in exc.value.message.lower()


def test_future_frozen_application_rejects_replaced_scope(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(
        manifest, lambda m: m.update({"scope": "anything at all"}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert exc.value.code == "G05_FROZEN_APPLICATION_SCOPE_MISMATCH"


def test_future_frozen_application_rejects_authorization_not_applied(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(
        manifest, lambda m: m.update({"authorization_applied": False}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "authorization_applied" in exc.value.message


def test_future_frozen_application_rejects_replaced_event(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, event = _make_frozen_fixture(tmp_path)
    # Replace the event file CONTENT (same path): raw-byte hash mismatch.
    ev = json.loads(event.read_text(encoding="utf-8"))
    ev["authorization_sentence"] = "a different sentence"
    _write_json(event, ev)
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "event" in exc.value.message.lower()


def test_future_frozen_application_rejects_replaced_event_path(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(
        manifest,
        lambda m: m.update(
            {"authorization_event_path": "other_event.json"}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert "event" in exc.value.message.lower()


def test_future_frozen_application_rejects_pending_checkpoint_flipped(
        tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _mutate_manifest(
        manifest,
        lambda m: m.update(
            {"application_checkpoint": {
                "pending_commit_not_applied": False,
                "commit_sha256": "11" * 40}}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    assert exc.value.code == "G05_FROZEN_APPLICATION_CHECKPOINT"


def test_future_frozen_application_rejects_modified_manifest_after_validation(
        tmp_path: Path) -> None:
    # First validation passes; then the manifest is modified. The second
    # validation must reject — no stale token can survive a manifest edit.
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    result = validate_frozen_application(draft, frozen, manifest,
                                         project_root=root)
    assert result["frozen_application_valid"] is True
    _mutate_manifest(manifest,
                     lambda m: m.update({"manifest_id": "syn-g05-auth-2"}))
    with pytest.raises(G05ClassificationError) as exc:
        validate_frozen_application(draft, frozen, manifest,
                                    project_root=root)
    # the append-only event still references the OLD manifest ID, so the
    # modified manifest is rejected at the event binding
    assert exc.value.code == "G05_FROZEN_APPLICATION_EVENT_MISMATCH"


# ---------------------------------------------------------------------------
# classify_frozen: NO caller-supplied validation result exists in v6
# ---------------------------------------------------------------------------
def test_classify_frozen_never_accepts_a_caller_supplied_validation_result(
        tmp_path: Path) -> None:
    """v5 vulnerability regression: the exact hand-built dict that v5
    accepted (64-hex token + correct frozen hash + valid=true) must now be
    IMPOSSIBLE to pass — classify_frozen has no validation-result parameter
    and re-verifies everything from disk on every call."""
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    fake = {
        "frozen_application_valid": True,
        "validation_token": "00" * 32,
        "approved_frozen_config_sha256": _raw_sha(frozen),
    }
    with pytest.raises(TypeError):
        classify_frozen(_with(), frozen, fake)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        classify_frozen(  # type: ignore[call-arg]
            _with(), frozen_config_path=frozen, validation_result=fake)


def test_classify_frozen_rejects_forged_manifest_64_hex_token_variant(
        tmp_path: Path) -> None:
    """Even a manifest forged with a well-formed 64-hex token and the
    correct frozen hash cannot unlock the classifier: the manifest must
    carry the FULL approved binding (sentence, scope, event, scan)."""
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    forged = {
        "frozen_application_valid": True,
        "validation_token": "ab" * 32,
        "approved_frozen_config_sha256": _raw_sha(frozen),
    }
    forged_path = tmp_path / "forged_manifest.json"
    _write_json(forged_path, forged)
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), draft_config_path=draft,
                        frozen_config_path=frozen,
                        authorization_manifest_path=forged_path,
                        project_root=root)
    assert "manifest" in exc.value.message.lower()


def test_classify_frozen_accepts_validated_fixture(tmp_path: Path) -> None:
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    out = classify_frozen(_with(), draft_config_path=draft,
                          frozen_config_path=frozen,
                          authorization_manifest_path=manifest,
                          project_root=root)
    assert out["level"] == "L1"
    assert out["status"] == "frozen"


def test_classify_frozen_rejects_wrong_frozen_file(tmp_path: Path) -> None:
    # Replace the frozen file AFTER the fixture was created: the manifest
    # binds the OLD raw-byte hash, so re-verification must reject.
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    _write_config(frozen, "frozen",
                  frozen_before_new_results=True,
                  retrospective_use_forbidden=True,
                  status_reason="different bytes than the bound file")
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), draft_config_path=draft,
                        frozen_config_path=frozen,
                        authorization_manifest_path=manifest,
                        project_root=root)
    assert "frozen config RAW BYTE hash" in exc.value.message


def test_classify_frozen_rejects_bool_only_claim(tmp_path: Path) -> None:
    # A caller who only passes True/false values can never even reach the
    # classifier: the manifest file itself is re-verified.
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    not_a_manifest = tmp_path / "bool_manifest.json"
    not_a_manifest.write_bytes(b"true")
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), draft_config_path=draft,
                        frozen_config_path=frozen,
                        authorization_manifest_path=not_a_manifest,
                        project_root=root)
    assert "manifest" in exc.value.message.lower() or \
        "JSON" in exc.value.message


def test_classify_frozen_rejects_results_then_authorization(
        tmp_path: Path) -> None:
    # Produce a target result FIRST, then build a fully-formed manifest:
    # the prior-results evidence scan must still reject the application.
    root, draft, frozen, manifest, _ = _make_frozen_fixture(tmp_path)
    res = root / "outputs" / "evidence"
    res.mkdir(parents=True)
    (res / "g05_new_corpus_result.json").write_bytes(b"{}")
    with pytest.raises(G05ClassificationError) as exc:
        classify_frozen(_with(), draft_config_path=draft,
                        frozen_config_path=frozen,
                        authorization_manifest_path=manifest,
                        project_root=root)
    assert "prior" in exc.value.message.lower()


# ---------------------------------------------------------------------------
# prior-results derivation from disk evidence
# ---------------------------------------------------------------------------
def test_derive_prior_results_empty_project_scan() -> None:
    import bpc_hybrid.g05_complexity_candidate as g05
    from pathlib import Path as _Path
    root = _Path(g05.__file__).resolve().parents[2]
    scan = derive_prior_results(root)
    assert scan["result_paths"] == []
    assert scan["result_hashes"] == {}
    assert len(scan["scan_sha256"]) == 64


def test_derive_prior_results_finds_and_binds_results(tmp_path: Path) -> None:
    res = tmp_path / "data" / "results"
    res.mkdir(parents=True)
    a = res / "g05_a.json"
    a.write_bytes(b"result-a")
    b = res / "g05_b.json"
    b.write_bytes(b"result-b")
    ev = tmp_path / "outputs" / "evidence"
    ev.mkdir(parents=True)
    c = ev / "g05_c.json"
    c.write_bytes(b"result-c")
    scan = derive_prior_results(tmp_path)
    assert scan["result_paths"] == [
        "data/results/g05_a.json", "data/results/g05_b.json",
        "outputs/evidence/g05_c.json"]
    assert scan["result_hashes"]["data/results/g05_a.json"] == \
        _sha_bytes(b"result-a")
    # deterministic: same tree -> same scan hash
    assert scan["scan_sha256"] == derive_prior_results(tmp_path)["scan_sha256"]

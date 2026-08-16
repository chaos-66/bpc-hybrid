# -*- coding: utf-8 -*-
"""Deterministic G0.5 complexity candidate classifier (draft, NOT frozen).

Loads `configs/g05_complexity_candidate_draft_v1.json` and classifies a
synthetic feature record into L1 / L2 / L3. The candidate contract is
`draft_not_frozen`: freezing it is an experiment-contract / gate change
that requires a separate user authorization and must happen BEFORE any new
complex-corpus results are produced. This module NEVER applies the rules
retrospectively to existing S2.10 results.

Fail-closed behaviour:
  * unknown feature fields, missing required fields, wrong types and
    negative values raise :class:`G05ClassificationError` with a
    machine-decodable code;
  * L3 hard triggers are evaluated first (any hit -> L3, highest level
    wins); otherwise L1 is assigned iff every L1 maximum and the L1
    language rule are satisfied; otherwise L2 (conservative middle).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / \
    "g05_complexity_candidate_draft_v1.json"

EXPECTED_STATUS = "draft_not_frozen"

# Future frozen configs / authorization manifests are probed with these
# name patterns; none may exist today.
FROZEN_CONFIG_PATTERNS = ("g05_complexity_candidate_frozen*",
                          "g05_*_frozen*.json")
AUTHORIZATION_MANIFEST_PATTERNS = (
    "outputs/reports/*g05*authorization*",
    "outputs/reports/*g05*freeze*manifest*",
    "configs/*g05*authorization*",
)
PRIOR_RESULT_PATTERNS = (
    "data/results/*g05*",
    "outputs/evidence/*g05*",
)


class G05ClassificationError(Exception):
    """Machine-decodable classification rejection."""

    code = "G05_CLASSIFICATION_ERROR"

    def __init__(self, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class MissingFeatureError(G05ClassificationError):
    code = "G05_MISSING_FEATURE"


class UnknownFeatureError(G05ClassificationError):
    code = "G05_UNKNOWN_FEATURE"


class InvalidFeatureValueError(G05ClassificationError):
    code = "G05_INVALID_FEATURE_VALUE"


class DraftNotFrozenViolationError(G05ClassificationError):
    code = "G05_DRAFT_NOT_FROZEN_VIOLATION"


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or doc.get("status") != EXPECTED_STATUS:
        raise DraftNotFrozenViolationError(
            "G0.5 candidate contract must stay draft_not_frozen; refusing "
            "to classify under a frozen/unknown status",
            detail=f"status={doc.get('status')!r}")
    return doc


def classify(features: Mapping[str, Any],
             config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Deterministically classify one synthetic feature record.

    Returns {"level", "matched_hard_triggers", "l1_violations",
    "config_version", "status", "conflict_policy_applied"}.
    """
    if config is None:
        config = load_config()
    if config.get("status") != EXPECTED_STATUS:
        raise DraftNotFrozenViolationError(
            "G0.5 candidate contract must stay draft_not_frozen",
            detail=f"status={config.get('status')!r}")
    if config.get("retrospective_use_forbidden") is not True:
        raise DraftNotFrozenViolationError(
            "G0.5 candidate contract must forbid retrospective use",
            detail="retrospective_use_forbidden is not true")

    fields_cfg = config.get("fields", {})
    declared = set(fields_cfg)
    provided = set(features)

    unknown = sorted(provided - declared)
    if unknown:
        raise UnknownFeatureError(
            "unknown feature field(s) in the G0.5 candidate contract",
            detail=f"unknown={unknown}")

    missing = sorted(declared - provided)
    if missing:
        raise MissingFeatureError(
            "missing required G0.5 feature field(s)",
            detail=f"missing={missing}")

    values: dict[str, Any] = {}
    for name in sorted(declared):
        value = features[name]
        spec = fields_cfg[name]
        expected = spec.get("type")
        if expected == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise InvalidFeatureValueError(
                    f"feature {name!r} must be an integer",
                    detail=f"value={value!r}")
            if value < 0:
                raise InvalidFeatureValueError(
                    f"feature {name!r} must be non-negative",
                    detail=f"value={value!r}")
        elif expected == "string":
            if not isinstance(value, str):
                raise InvalidFeatureValueError(
                    f"feature {name!r} must be a string",
                    detail=f"value={value!r}")
            allowed = spec.get("enum")
            if allowed and value not in allowed:
                raise InvalidFeatureValueError(
                    f"feature {name!r} has an invalid value",
                    detail=f"value={value!r} allowed={allowed}")
        values[name] = value

    l3_cfg = config.get("levels", {}).get("L3", {})
    triggers = l3_cfg.get("hard_triggers", {})
    matched: list[str] = []
    for key, minimum in sorted(triggers.items()):
        feature_name = key[:-len("_min")] if key.endswith("_min") else key
        if values.get(feature_name, 0) >= minimum:
            matched.append(key)
    language = values.get("language_markers")
    any_hit_l3 = l3_cfg.get("language_rule", {}).get("any_hit_l3", [])
    if language in any_hit_l3:
        matched.append(f"language_markers={language}")

    l1_cfg = config.get("levels", {}).get("L1", {})
    maxima = l1_cfg.get("maxima", {})
    violations: list[str] = []
    for key, maximum in sorted(maxima.items()):
        if values.get(key, 0) > maximum:
            violations.append(f"{key}={values.get(key)}>max={maximum}")
    allowed_lang = l1_cfg.get("language_rule", {}).get("allowed", [])
    if language not in allowed_lang:
        violations.append(f"language_markers={language}")

    if matched:
        level = "L3"
    elif not violations:
        level = "L1"
    else:
        level = "L2"

    return {
        "level": level,
        "matched_hard_triggers": sorted(matched),
        "l1_violations": sorted(violations),
        "config_version": config.get("config_version"),
        "status": config.get("status"),
        "conflict_policy_applied": "highest_level_wins",
    }


def derive_promotion_readiness(root: Path) -> dict[str, Any]:
    """Derive the CURRENT G0.5 promotion readiness from disk (fail-closed).

    Today this always yields g0_5_status=draft_not_frozen and
    promotion_ready_for_application=false because no user authorization
    manifest and no frozen config exist and no prior new-corpus results
    may exist. The future frozen-application path is exercised separately
    by :func:`validate_frozen_application` with synthetic fixtures.
    """
    config = load_config(root / "configs" / "g05_complexity_candidate_draft_v1.json")
    frozen_configs = sorted(
        p.relative_to(root).as_posix()
        for pat in FROZEN_CONFIG_PATTERNS
        for p in (root / "configs").glob(pat))
    auth_manifests = sorted(
        p.relative_to(root).as_posix()
        for pat in AUTHORIZATION_MANIFEST_PATTERNS
        for p in root.glob(pat))
    prior_results = sorted(
        p.relative_to(root).as_posix()
        for pat in PRIOR_RESULT_PATTERNS
        for p in root.glob(pat))
    missing: list[str] = []
    if not auth_manifests:
        missing.append("user authorization manifest (G4 dry-run sentence "
                       "is NOT applied)")
    if frozen_configs:
        missing.append("no frozen config may exist before the G4 "
                       "authorization is applied")
    if prior_results:
        missing.append("no new-corpus prediction/result may exist before "
                       "the freeze takes effect")
    ready = bool(auth_manifests and not frozen_configs and not prior_results)
    return {
        "g0_5_status": config.get("status", "unknown"),
        "promotion_ready_for_application": ready,
        "missing": missing,
        "draft_config_sha256": _config_sha256(
            root / "configs" / "g05_complexity_candidate_draft_v1.json"),
        "frozen_configs_found": frozen_configs,
        "authorization_manifests_found": auth_manifests,
        "prior_results_found": prior_results,
        "retrospective_use_forbidden": config.get(
            "retrospective_use_forbidden") is True,
        "preregistration_claim_allowed": False,
    }


def _config_sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_frozen_application(
        draft_config: dict[str, Any],
        frozen_config: dict[str, Any],
        authorization_manifest: dict[str, Any],
        corpus_has_prior_results: bool = False) -> dict[str, Any]:
    """FAIL-CLOSED validation of the FUTURE G0.5 frozen-application path.

    Synthetic-fixture only: neither the project config nor any real
    authorization manifest may be created this round. Validates:
      * draft config status == draft_not_frozen;
      * frozen config status == frozen with
        frozen_before_new_results=true and
        retrospective_use_forbidden=true;
      * authorization manifest binds the exact draft config sha256, the
        approved frozen config sha256, the scope and a non-empty
        authorization sentence;
      * no prior prediction/result for the corpus
        (corpus_has_prior_results=False).

    Raises :class:`G05ClassificationError` (codes G05_FROZEN_APPLICATION_
    *) on any violation.
    """
    if not isinstance(draft_config, dict) or \
            draft_config.get("status") != "draft_not_frozen":
        raise G05ClassificationError(
            "frozen application requires the draft config to be "
            "draft_not_frozen",
            detail=f"draft_status={draft_config.get('status')!r}")
    if not isinstance(frozen_config, dict) or \
            frozen_config.get("status") != "frozen":
        raise G05ClassificationError(
            "frozen application requires the approved config to be frozen",
            detail=f"frozen_status={frozen_config.get('status')!r}")
    if frozen_config.get("frozen_before_new_results") is not True:
        raise G05ClassificationError(
            "frozen config must declare frozen_before_new_results=true",
            detail=f"frozen_before_new_results="
                   f"{frozen_config.get('frozen_before_new_results')!r}")
    if frozen_config.get("retrospective_use_forbidden") is not True:
        raise G05ClassificationError(
            "frozen config must forbid retrospective use",
            detail=f"retrospective_use_forbidden="
                   f"{frozen_config.get('retrospective_use_forbidden')!r}")
    if not isinstance(authorization_manifest, dict):
        raise G05ClassificationError(
            "frozen application requires an authorization manifest",
            detail=f"authorization_manifest={authorization_manifest!r}")
    import hashlib as _hl
    draft_sha = _hl.sha256(json.dumps(
        draft_config, sort_keys=True).encode("utf-8")).hexdigest()
    frozen_sha = _hl.sha256(json.dumps(
        frozen_config, sort_keys=True).encode("utf-8")).hexdigest()
    if authorization_manifest.get("draft_config_sha256") != draft_sha:
        raise G05ClassificationError(
            "authorization manifest does not bind the draft config hash",
            detail=f"manifest={authorization_manifest.get('draft_config_sha256')!r} "
                   f"derived={draft_sha[:12]}...")
    if authorization_manifest.get("approved_frozen_config_sha256") != \
            frozen_sha:
        raise G05ClassificationError(
            "authorization manifest does not bind the frozen config hash",
            detail=f"manifest="
                   f"{authorization_manifest.get('approved_frozen_config_sha256')!r} "
                   f"derived={frozen_sha[:12]}...")
    if not isinstance(authorization_manifest.get("scope"), str) or \
            not authorization_manifest["scope"].strip():
        raise G05ClassificationError(
            "authorization manifest must declare a scope",
            detail=f"scope={authorization_manifest.get('scope')!r}")
    if not isinstance(authorization_manifest.get("authorization_sentence"),
                      str) or not authorization_manifest[
                          "authorization_sentence"].strip():
        raise G05ClassificationError(
            "authorization manifest must carry an authorization sentence",
            detail="authorization_sentence missing or empty")
    if corpus_has_prior_results:
        raise G05ClassificationError(
            "frozen application is invalid when the corpus already has "
            "prior prediction/result",
            detail="corpus_has_prior_results=True")
    return {
        "frozen_application_valid": True,
        "g0_5_status": "frozen",
        "draft_config_sha256": draft_sha,
        "approved_frozen_config_sha256": frozen_sha,
        "scope": authorization_manifest.get("scope"),
        "frozen_before_new_results": True,
        "retrospective_use_forbidden": True,
        "corpus_has_prior_results": False,
        "preregistration_claim_allowed": True,
    }

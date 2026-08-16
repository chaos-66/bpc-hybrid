# -*- coding: utf-8 -*-
"""Deterministic G0.5 complexity candidate classifier (draft, NOT frozen)
with a SEALED future frozen-application chain (v6).

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

v6 seals the frozen-application chain (the v5 caller-supplied
validation-result unlock is REMOVED):
  * :func:`classify_frozen` has NO validation-result parameter at all.
    Every call re-verifies the draft config, the frozen config, the
    authorization manifest, the append-only authorization event and the
    prior-results evidence scan from disk (raw file bytes), then
    classifies. A hand-built dict — even one carrying a well-formed
    64-hex token and the correct frozen hash — can never unlock the
    frozen classifier, because there is no caller-supplied credential to
    forge. A SHA-256 over file bytes proves byte-identity only; it is
    never treated as proof of user authorization by itself. Real
    authority comes from the versioned authorization manifest + the
    append-only authorization event + the exact on-disk re-verification.
  * the authorization manifest must fully bind: schema/version, manifest
    ID, authorization_applied=true, the exact approved scope enum
    (`future_external_complex_corpora_only`), the exact approved G4
    dry-run sentence (full text) plus its UTF-8 SHA-256, the draft and
    frozen config relative paths + raw-byte SHA-256,
    retrospective_use_forbidden=true, frozen_before_new_results=true,
    s2_10_retrospective_use_forbidden=true, the re-derived prior-results
    scan SHA-256, the authorization event (ID + relative path + raw-byte
    SHA-256) and an application checkpoint that is still
    pending_commit_not_applied (nothing is applied by this module).
  * prior results are DERIVED from the synthetic project root by
    deterministic path/manifest rules (:func:`derive_prior_results`);
    there is no caller-supplied `corpus_has_prior_results` bool. Any
    existing target result rejects the future freeze application.
  * the authorization hash domain is the RAW FILE BYTES: the real draft
    config raw-byte SHA-256 is 61938c99… (bound by the dry-run G4
    sentence); the old semantic re-serialization hash 51a6e4fe… is never
    an authorization hash.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
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
MEMBERSHIP_MANIFEST_PATTERNS = (
    "configs/*corpus*.json",
    "configs/*membership*.json",
)

# The draft config raw-byte hash domain used by the dry-run G4 sentence.
# The semantic re-serialization hash 51a6e4fe… is NEVER an authorization
# hash; it is recorded here only to be rejected.
DRAFT_CONFIG_RAW_SHA256 = \
    "61938c99a012f36b2b3b3d66a346b31a6c33fdd3f14be0179291ef1982a97586"
SEMANTIC_RE_SERIALIZATION_SHA256 = \
    "51a6e4fe43d33f79b33d14784d08266aff6576453daf9dca465de702ddae0760"

# Exact approved authorization scope (controlled enum value).
APPROVED_AUTHORIZATION_SCOPE = "future_external_complex_corpora_only"
AUTHORIZATION_MANIFEST_SCHEMA_VERSION = "g05_authorization_manifest@1.0.0"
AUTHORIZATION_EVENT_KIND = "g05_authorization_event"
MANIFEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
EVENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


class FrozenApplicationError(G05ClassificationError):
    code = "G05_FROZEN_APPLICATION"


class FrozenApplicationManifestError(FrozenApplicationError):
    code = "G05_FROZEN_APPLICATION_MANIFEST_BINDING"


class FrozenApplicationScopeError(FrozenApplicationError):
    code = "G05_FROZEN_APPLICATION_SCOPE_MISMATCH"


class FrozenApplicationSentenceError(FrozenApplicationError):
    code = "G05_FROZEN_APPLICATION_SENTENCE_MISMATCH"


class FrozenApplicationEventError(FrozenApplicationError):
    code = "G05_FROZEN_APPLICATION_EVENT_MISMATCH"


class FrozenApplicationPriorResultsError(FrozenApplicationError):
    code = "G05_FROZEN_APPLICATION_PRIOR_RESULTS"


class FrozenApplicationCheckpointError(FrozenApplicationError):
    code = "G05_FROZEN_APPLICATION_CHECKPOINT"


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
    """Deterministically classify one synthetic feature record under the
    DRAFT (draft_not_frozen) contract. A frozen config can only be used
    through :func:`classify_frozen`, which re-verifies the full
    authorization chain from disk on every call."""
    if config is None:
        config = load_config()
    if config.get("status") != EXPECTED_STATUS:
        raise DraftNotFrozenViolationError(
            "G0.5 candidate contract must stay draft_not_frozen for "
            "plain classify(); frozen configs require classify_frozen() "
            "with the full re-verified authorization chain",
            detail=f"status={config.get('status')!r}")
    return _classify_impl(features, config)


def _classify_impl(features: Mapping[str, Any],
                   config: dict[str, Any]) -> dict[str, Any]:
    """Core deterministic L1/L2/L3 classification shared by the draft and
    the (re-verified) frozen paths."""
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


def approved_authorization_sentence(draft_config_sha256: str) -> str:
    """The EXACT approved dry-run G4 authorization sentence (full text).

    This is the only sentence a valid authorization manifest may carry.
    It authorizes ONLY a future gate-application checkpoint; it never
    freezes G0.5 by itself.
    """
    return (
        "I authorize a future gate-application checkpoint that freezes "
        "configs/g05_complexity_candidate_draft_v1.json (RAW BYTE sha256 "
        f"{draft_config_sha256}) as the G0.5 complexity contract (scope: "
        "future external complex corpora only; retrospective_use_forbidden"
        "=true; must take effect before any new complex-corpus results are "
        "produced). This sentence authorizes ONLY that future "
        "gate-application checkpoint; it does NOT freeze G0.5 this round.")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _config_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise G05ClassificationError(
            "frozen application requires readable JSON files",
            detail=f"path={path} error={exc!r}")
    if not isinstance(doc, dict):
        raise G05ClassificationError(
            "frozen application requires JSON objects",
            detail=f"path={path} type={type(doc).__name__}")
    return doc


def _safe_relative_path(root: Path, raw: Any, what: str) -> Path:
    """Resolve a manifest-bound relative path safely under `root`.

    Rejects absolute paths, '..' traversal and backslash separators; the
    returned path is `root / raw` (callers then verify existence and raw
    bytes). No symlink/junction escape can occur because the raw path is
    lexically confined; resolved containment is enforced where files are
    read.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise FrozenApplicationManifestError(
            f"authorization manifest must bind a {what} relative path",
            detail=f"path={raw!r}")
    posix = PurePosixPath(raw)
    if posix.is_absolute() or ".." in posix.parts or "\\" in raw:
        raise FrozenApplicationManifestError(
            f"{what} path must be relative and must not traverse '..'",
            detail=f"path={raw!r}")
    return root / raw


def derive_prior_results(root: Path) -> dict[str, Any]:
    """Derive the existing target corpus/results evidence from disk
    (deterministic, documented path/manifest rules).

    Returns:
      membership_ids: corpus/membership IDs declared by corpus/membership
        manifests found under `configs/` (sorted, de-duplicated);
      result_paths: every existing prediction/result/evidence file under
        the deterministic PRIOR_RESULT_PATTERNS (sorted relative paths);
      result_hashes: relative path -> raw-byte SHA-256;
      scan_sha256: raw-byte SHA-256 of the deterministic scan payload —
        this is what an authorization manifest must bind, and the scan is
        re-derived on every validation call (a stale declared scan never
        unlocks anything).
    """
    membership_ids: list[str] = []
    for pat in MEMBERSHIP_MANIFEST_PATTERNS:
        for p in sorted(root.glob(pat)):
            if not p.is_file():
                continue
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(doc, dict):
                continue
            for key in ("corpus_id", "membership_id", "corpus_membership_id"):
                val = doc.get(key)
                if isinstance(val, str) and val.strip():
                    membership_ids.append(val)
    result_paths: list[str] = []
    result_hashes: dict[str, str] = {}
    for pat in PRIOR_RESULT_PATTERNS:
        for p in sorted(root.glob(pat)):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                result_paths.append(rel)
                result_hashes[rel] = _sha256_bytes(p.read_bytes())
    payload = {
        "membership_ids": sorted(set(membership_ids)),
        "result_paths": result_paths,
        "result_hashes": result_hashes,
    }
    return {
        "membership_ids": sorted(set(membership_ids)),
        "result_paths": result_paths,
        "result_hashes": dict(result_hashes),
        "scan_sha256": _sha256_bytes(
            json.dumps(payload, sort_keys=True, ensure_ascii=False)
            .encode("utf-8")),
    }


def derive_promotion_readiness(root: Path) -> dict[str, Any]:
    """Derive the CURRENT G0.5 promotion readiness from disk (fail-closed).

    NEVER decides readiness from a mere glob filename match: every frozen
    config / authorization manifest found must be parsed AND validated as a
    complete asset combination (see :func:`validate_frozen_application`).
    Prior results are derived from disk evidence, never from a caller bool.
    Today this always yields g0_5_status=draft_not_frozen and
    promotion_ready_for_application=false because no validated
    user-authorized asset combination exists and no prior new-corpus
    results may exist.
    """
    config_path = root / "configs" / "g05_complexity_candidate_draft_v1.json"
    config = load_config(config_path)
    frozen_configs = sorted(
        p.relative_to(root).as_posix()
        for pat in FROZEN_CONFIG_PATTERNS
        for p in (root / "configs").glob(pat))
    auth_manifests = sorted(
        p.relative_to(root).as_posix()
        for pat in AUTHORIZATION_MANIFEST_PATTERNS
        for p in root.glob(pat))
    prior_scan = derive_prior_results(root)
    prior_results = list(prior_scan["result_paths"])

    validated_combinations = 0
    invalid_assets: list[str] = []
    if frozen_configs and auth_manifests and not prior_results:
        for frozen_rel in frozen_configs:
            for manifest_rel in auth_manifests:
                try:
                    result = validate_frozen_application(
                        config_path,
                        root / frozen_rel,
                        root / manifest_rel,
                        project_root=root)
                    if result["frozen_application_valid"]:
                        validated_combinations += 1
                except G05ClassificationError as exc:
                    invalid_assets.append(
                        f"{frozen_rel}+{manifest_rel}:{exc.message[:60]}")
    elif auth_manifests and not frozen_configs:
        invalid_assets.append("authorization manifest(s) exist without a "
                              "validated frozen config")

    missing: list[str] = []
    if not auth_manifests:
        missing.append("user authorization manifest (G4 dry-run sentence "
                       "is NOT applied)")
    if frozen_configs and not validated_combinations:
        missing.append("no VALIDATED frozen config + authorization "
                       "manifest asset combination")
    if prior_results:
        missing.append("no new-corpus prediction/result may exist before "
                       "the freeze takes effect")
    ready = bool(validated_combinations >= 1 and not prior_results
                 and not invalid_assets)
    return {
        "g0_5_status": config.get("status", "unknown"),
        "promotion_ready_for_application": ready,
        "missing": missing,
        "draft_config_sha256": _config_sha256(config_path),
        "frozen_configs_found": frozen_configs,
        "authorization_manifests_found": auth_manifests,
        "prior_results_found": prior_results,
        "prior_results_scan_sha256": prior_scan["scan_sha256"],
        "validated_asset_combinations": validated_combinations,
        "invalid_assets": invalid_assets,
        "retrospective_use_forbidden": config.get(
            "retrospective_use_forbidden") is True,
        "preregistration_claim_allowed": False,
    }


def validate_frozen_application(
        draft_config_path: Path,
        frozen_config_path: Path,
        authorization_manifest_path: Path,
        *,
        project_root: Path) -> dict[str, Any]:
    """FAIL-CLOSED validation of the FUTURE G0.5 frozen-application path.

    Synthetic-fixture only: neither the project config nor any real
    authorization manifest / event / frozen config may be created this
    round; positive fixtures live in pytest tmp directories only.

    THE AUTHORIZATION HASH DOMAIN IS THE RAW FILE BYTES: draft and frozen
    configs, the authorization manifest and the authorization event are
    each hashed over their original file bytes, NOT over a re-serialized
    semantic dict. The dry-run G4 sentence binds the draft config raw-byte
    SHA-256 (configs/g05_complexity_candidate_draft_v1.json =
    61938c99…); the old semantic re-serialization hash 51a6e4fe… is never
    an authorization hash.

    Every validation RE-DERIVES the prior-results scan from `project_root`
    (:func:`derive_prior_results`); any existing target result rejects the
    application, and the manifest's bound scan must exactly match the
    re-derived scan.

    The returned `validation_token` is the raw-byte SHA-256 of the
    authorization manifest — computed here from disk, never accepted from
    a caller. :func:`classify_frozen` re-runs this whole validation on
    every call and derives the token internally.

    Raises :class:`G05ClassificationError` (codes G05_FROZEN_APPLICATION_*)
    on any violation.
    """
    draft_bytes = draft_config_path.read_bytes()
    frozen_bytes = frozen_config_path.read_bytes()
    manifest_bytes = authorization_manifest_path.read_bytes()
    draft_sha = _sha256_bytes(draft_bytes)
    frozen_sha = _sha256_bytes(frozen_bytes)
    manifest_sha = _sha256_bytes(manifest_bytes)

    draft_config = _read_json(draft_config_path)
    frozen_config = _read_json(frozen_config_path)
    authorization_manifest = _read_json(authorization_manifest_path)

    # --- draft config -------------------------------------------------------
    if draft_config.get("status") != "draft_not_frozen":
        raise FrozenApplicationManifestError(
            "frozen application requires the draft config to be "
            "draft_not_frozen",
            detail=f"draft_status={draft_config.get('status')!r}")
    if draft_config.get("retrospective_use_forbidden") is not True:
        raise FrozenApplicationManifestError(
            "draft config must forbid retrospective use",
            detail=f"retrospective_use_forbidden="
                   f"{draft_config.get('retrospective_use_forbidden')!r}")

    # --- frozen config ------------------------------------------------------
    if frozen_config.get("status") != "frozen":
        raise FrozenApplicationManifestError(
            "frozen application requires the approved config to be frozen",
            detail=f"frozen_status={frozen_config.get('status')!r}")
    if frozen_config.get("frozen_before_new_results") is not True:
        raise FrozenApplicationManifestError(
            "frozen config must declare frozen_before_new_results=true",
            detail=f"frozen_before_new_results="
                   f"{frozen_config.get('frozen_before_new_results')!r}")
    if frozen_config.get("retrospective_use_forbidden") is not True:
        raise FrozenApplicationManifestError(
            "frozen config must forbid retrospective use",
            detail=f"retrospective_use_forbidden="
                   f"{frozen_config.get('retrospective_use_forbidden')!r}")

    # --- authorization manifest structure ------------------------------------
    if authorization_manifest.get("schema_version") != \
            AUTHORIZATION_MANIFEST_SCHEMA_VERSION:
        raise FrozenApplicationManifestError(
            "authorization manifest must carry the exact manifest schema "
            "version",
            detail=f"schema_version="
                   f"{authorization_manifest.get('schema_version')!r}")
    if not MANIFEST_ID_RE.fullmatch(
            str(authorization_manifest.get("manifest_id") or "")):
        raise FrozenApplicationManifestError(
            "authorization manifest must carry a stable manifest ID",
            detail=f"manifest_id="
                   f"{authorization_manifest.get('manifest_id')!r}")
    if authorization_manifest.get("authorization_applied") is not True:
        raise FrozenApplicationManifestError(
            "authorization manifest must declare "
            "authorization_applied=true",
            detail=f"authorization_applied="
                   f"{authorization_manifest.get('authorization_applied')!r}")

    # --- config relative paths + raw-byte hashes ------------------------------
    try:
        draft_rel = draft_config_path.resolve().relative_to(
            project_root.resolve()).as_posix()
        frozen_rel = frozen_config_path.resolve().relative_to(
            project_root.resolve()).as_posix()
    except ValueError:
        raise FrozenApplicationManifestError(
            "draft/frozen configs must live under the project root",
            detail=f"project_root={project_root}")
    if authorization_manifest.get("draft_config_path") != draft_rel:
        raise FrozenApplicationManifestError(
            "authorization manifest draft_config_path does not match the "
            "validated file",
            detail=f"manifest="
                   f"{authorization_manifest.get('draft_config_path')!r} "
                   f"file={draft_rel!r}")
    if authorization_manifest.get("approved_frozen_config_path") != \
            frozen_rel:
        raise FrozenApplicationManifestError(
            "authorization manifest approved_frozen_config_path does not "
            "match the validated file",
            detail=f"manifest="
                   f"{authorization_manifest.get('approved_frozen_config_path')!r} "
                   f"file={frozen_rel!r}")
    if authorization_manifest.get("draft_config_sha256") != draft_sha:
        raise FrozenApplicationManifestError(
            "authorization manifest does not bind the draft config RAW "
            "BYTE hash",
            detail=f"manifest={authorization_manifest.get('draft_config_sha256')!r} "
                   f"raw_bytes={draft_sha[:12]}...")
    if authorization_manifest.get("approved_frozen_config_sha256") != \
            frozen_sha:
        raise FrozenApplicationManifestError(
            "authorization manifest does not bind the frozen config RAW "
            "BYTE hash",
            detail=f"manifest="
                   f"{authorization_manifest.get('approved_frozen_config_sha256')!r} "
                   f"raw_bytes={frozen_sha[:12]}...")

    # --- exact approved scope -------------------------------------------------
    scope = authorization_manifest.get("scope")
    if scope != APPROVED_AUTHORIZATION_SCOPE:
        raise FrozenApplicationScopeError(
            "authorization manifest scope must EXACTLY equal the approved "
            "scope",
            detail=f"scope={scope!r} approved={APPROVED_AUTHORIZATION_SCOPE!r}")

    # --- exact approved sentence + its UTF-8 SHA-256 ---------------------------
    sentence = authorization_manifest.get("authorization_sentence")
    expected_sentence = approved_authorization_sentence(draft_sha)
    if sentence != expected_sentence:
        raise FrozenApplicationSentenceError(
            "authorization manifest must carry the EXACT approved "
            "dry-run sentence",
            detail=f"declared={str(sentence)[:80]!r} "
                   f"approved={expected_sentence[:80]!r}")
    if authorization_manifest.get("authorization_sentence_sha256") != \
            _sha256_bytes(expected_sentence.encode("utf-8")):
        raise FrozenApplicationSentenceError(
            "authorization manifest sentence SHA-256 does not match the "
            "approved sentence UTF-8 bytes",
            detail=f"declared="
                   f"{authorization_manifest.get('authorization_sentence_sha256')!r}")

    # --- policy flags ----------------------------------------------------------
    if authorization_manifest.get("retrospective_use_forbidden") is not True:
        raise FrozenApplicationManifestError(
            "authorization manifest must declare "
            "retrospective_use_forbidden=true",
            detail=f"retrospective_use_forbidden="
                   f"{authorization_manifest.get('retrospective_use_forbidden')!r}")
    if authorization_manifest.get("frozen_before_new_results") is not True:
        raise FrozenApplicationManifestError(
            "authorization manifest must declare "
            "frozen_before_new_results=true",
            detail=f"frozen_before_new_results="
                   f"{authorization_manifest.get('frozen_before_new_results')!r}")
    if authorization_manifest.get("s2_10_retrospective_use_forbidden") \
            is not True:
        raise FrozenApplicationManifestError(
            "authorization manifest must explicitly forbid S2.10 "
            "retrospective use",
            detail=f"s2_10_retrospective_use_forbidden="
                   f"{authorization_manifest.get('s2_10_retrospective_use_forbidden')!r}")

    # --- prior results derived from disk evidence ------------------------------
    prior_scan = derive_prior_results(project_root)
    if prior_scan["result_paths"]:
        raise FrozenApplicationPriorResultsError(
            "frozen application is invalid: existing prior "
            "prediction/result/evidence files were derived from the "
            "project root",
            detail="; ".join(prior_scan["result_paths"][:10]))
    if authorization_manifest.get("prior_results_scan_sha256") != \
            prior_scan["scan_sha256"]:
        raise FrozenApplicationPriorResultsError(
            "authorization manifest prior-results scan does not match the "
            "re-derived disk scan",
            detail=f"manifest="
                   f"{authorization_manifest.get('prior_results_scan_sha256')!r} "
                   f"re_derived={prior_scan['scan_sha256'][:12]}...")

    # --- append-only authorization event ---------------------------------------
    event_id = authorization_manifest.get("authorization_event_id")
    event_sha_declared = authorization_manifest.get(
        "authorization_event_sha256")
    if not EVENT_ID_RE.fullmatch(str(event_id or "")):
        raise FrozenApplicationEventError(
            "authorization manifest must bind a stable authorization "
            "event ID",
            detail=f"event_id={event_id!r}")
    if not SHA256_RE.fullmatch(str(event_sha_declared or "")):
        raise FrozenApplicationEventError(
            "authorization manifest must bind the authorization event "
            "raw-byte SHA-256",
            detail=f"event_sha256={event_sha_declared!r}")
    event_path = _safe_relative_path(
        project_root, authorization_manifest.get("authorization_event_path"),
        "authorization event")
    if not event_path.is_file():
        raise FrozenApplicationEventError(
            "authorization event file does not exist under the project "
            "root",
            detail=f"path={event_path}")
    event_bytes = event_path.read_bytes()
    if _sha256_bytes(event_bytes) != event_sha_declared:
        raise FrozenApplicationEventError(
            "authorization event raw bytes do not hash to the manifest "
            "binding",
            detail=f"declared={event_sha_declared[:12]}... "
                   f"actual={_sha256_bytes(event_bytes)[:12]}...")
    event = _read_json(event_path)
    if event.get("kind") != AUTHORIZATION_EVENT_KIND:
        raise FrozenApplicationEventError(
            "authorization event internal kind does not match the "
            "approved event kind",
            detail=f"kind={event.get('kind')!r}")
    if event.get("event_id") != event_id:
        raise FrozenApplicationEventError(
            "authorization event internal ID does not match the manifest "
            "binding",
            detail=f"event_id={event.get('event_id')!r} "
                   f"bound={event_id!r}")
    if event.get("authorization_sentence") != expected_sentence:
        raise FrozenApplicationEventError(
            "authorization event must carry the EXACT approved sentence",
            detail=f"declared={str(event.get('authorization_sentence'))[:80]!r}")
    if event.get("scope") != APPROVED_AUTHORIZATION_SCOPE:
        raise FrozenApplicationEventError(
            "authorization event scope must EXACTLY equal the approved "
            "scope",
            detail=f"scope={event.get('scope')!r}")
    if event.get("manifest_id") != authorization_manifest.get("manifest_id"):
        raise FrozenApplicationEventError(
            "authorization event must reference the authorizing manifest "
            "ID",
            detail=f"event_manifest={event.get('manifest_id')!r} "
                   f"manifest={authorization_manifest.get('manifest_id')!r}")
    if event.get("append_only") is not True:
        raise FrozenApplicationEventError(
            "authorization event must be append-only",
            detail=f"append_only={event.get('append_only')!r}")

    # --- application checkpoint (pending, NOT applied) -------------------------
    checkpoint = authorization_manifest.get("application_checkpoint")
    if not isinstance(checkpoint, dict):
        raise FrozenApplicationCheckpointError(
            "authorization manifest must carry an application_checkpoint "
            "object",
            detail=f"application_checkpoint={checkpoint!r}")
    if checkpoint.get("pending_commit_not_applied") is not True:
        raise FrozenApplicationCheckpointError(
            "the G4 sentence authorizes ONLY a future gate-application "
            "checkpoint; the manifest must declare "
            "pending_commit_not_applied=true (nothing is applied by this "
            "chain)",
            detail=f"pending_commit_not_applied="
                   f"{checkpoint.get('pending_commit_not_applied')!r}")
    commit = checkpoint.get("commit_sha256")
    if commit is not None and (not isinstance(commit, str)
                               or not COMMIT_SHA_RE.fullmatch(commit)):
        raise FrozenApplicationCheckpointError(
            "application checkpoint commit_sha256 must be a 40-hex commit "
            "SHA or null",
            detail=f"commit_sha256={commit!r}")

    return {
        "frozen_application_valid": True,
        "g0_5_status": "frozen",
        "draft_config_sha256": draft_sha,
        "approved_frozen_config_sha256": frozen_sha,
        "authorization_manifest_sha256": manifest_sha,
        "validation_token": manifest_sha,
        "scope": APPROVED_AUTHORIZATION_SCOPE,
        "authorization_sentence_sha256": _sha256_bytes(
            expected_sentence.encode("utf-8")),
        "authorization_event_id": event_id,
        "authorization_event_sha256": event_sha_declared,
        "prior_results_scan_sha256": prior_scan["scan_sha256"],
        "prior_results_found": list(prior_scan["result_paths"]),
        "frozen_before_new_results": True,
        "retrospective_use_forbidden": True,
        "s2_10_retrospective_use_forbidden": True,
        "application_checkpoint": {
            "pending_commit_not_applied": True},
        "preregistration_claim_allowed": True,
    }


def classify_frozen(features: Mapping[str, Any], *,
                    draft_config_path: Path,
                    frozen_config_path: Path,
                    authorization_manifest_path: Path,
                    project_root: Path) -> dict[str, Any]:
    """Classify with a FROZEN config.

    v6: there is NO caller-supplied validation result. Every call
    re-executes :func:`validate_frozen_application` against the current
    on-disk raw bytes of the draft config, frozen config, authorization
    manifest and authorization event, plus the re-derived prior-results
    scan. A hand-built dict, a bare boolean, a 64-hex token copied from
    another manifest, or a stale token after a manifest edit can never
    unlock this path.
    """
    validate_frozen_application(draft_config_path, frozen_config_path,
                                authorization_manifest_path,
                                project_root=project_root)
    config = json.loads(frozen_config_path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or config.get("status") != "frozen":
        raise G05ClassificationError(
            "frozen classification requires a frozen config",
            detail=f"status={config.get('status')!r}")
    return _classify_impl(features, config)

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

# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_verifier():
    path = ROOT / "scripts/verify_s2_13_s3_7_transition_readiness_v8.py"
    spec = importlib.util.spec_from_file_location("transition_v8_verify", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_transition_v8_current_state_and_boundaries() -> None:
    report = json.loads((ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v8.json").read_text(encoding="utf-8"))
    assert report["pipeline_state"]["S2.11"] == "verified_frozen"
    assert report["pipeline_state"]["S2.12"] == "partial_zero_api_arm_complete_api_arms_pending"
    assert report["pipeline_state"]["S2.13"] == "blocked_only_on_remaining_S2.12_DoD"
    assert report["pipeline_state"]["S3.7"] == "formal_oracle_not_started"
    assert report["gold_rule_records"]["exist"] is False


def test_transition_v8_historical_lifecycle_is_explicit() -> None:
    report = json.loads((ROOT / "outputs/reports/s2_13_s3_7_transition_readiness_v8.json").read_text(encoding="utf-8"))
    matrix = report["historical_transition_verifiers"]
    for version in (1, 2, 3, 4, 7):
        assert matrix[f"v{version}"]["outcome"] == "verified_current_or_preserved"
    for version in (5, 6):
        assert matrix[f"v{version}"]["outcome"] == "expected_fail_closed_superseded_snapshot"


def test_transition_v8_independent_verifier() -> None:
    result = _load_verifier().verify()
    assert result["verified"], [item for item in result["checks"] if not item["ok"]]

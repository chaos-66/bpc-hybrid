# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readiness_v4_reports_partial_and_precise_blocker() -> None:
    report = json.loads((ROOT / "outputs/reports/s2_12_execution_readiness_v4.json").read_text(encoding="utf-8"))
    assert report["status"] == "partial_zero_api_arm_complete_api_arms_pending_authorization"
    assert report["s2_11"]["status"] == "verified_frozen"
    assert report["s2_12"]["sun_rule_only"]["status"] == "verified_complete"
    assert report["s2_12"]["three_method_comparison_complete"] is False
    assert report["downstream"]["S2.13"] == "blocked_only_on_remaining_S2.12_DoD"


def test_readiness_v4_suggested_sentence_is_bounded_but_not_authorization() -> None:
    report = json.loads((ROOT / "outputs/reports/s2_12_execution_readiness_v4.json").read_text(encoding="utf-8"))
    auth = report["authorization"]
    assert auth["api_authorized"] is False
    sentence = auth["suggested_copyable_sentence"]
    for fragment in ("63 次调用", "0 次重试", "总计费输入≤63000000 tokens", "总费用≤US$27.63", "不得调用 Oracle"):
        assert fragment in sentence


def test_readiness_v4_independent_verifier() -> None:
    verifier = _load("s212_ready_v4", "scripts/verify_s2_12_readiness_v4.py")
    result = verifier.verify()
    assert result["verified"], [item for item in result["checks"] if not item["ok"]]

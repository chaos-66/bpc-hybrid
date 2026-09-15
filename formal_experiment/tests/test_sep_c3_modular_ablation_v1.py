# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_sep_c3_modular_ablation_v1 as runner  # noqa: E402
from bpc_hybrid.sep_c3_modular_evaluation import (  # noqa: E402
    PRIMARY_METRIC,
    SPAN_FIELDS,
)


def test_budget_declares_600_calls_750_cap():
    budget = json.loads(
        (ROOT / "configs" / "sep_c3_modular_ablation_budget_v1.json")
        .read_text(encoding="utf-8")
    )
    assert budget["planned_calls"] == 600
    assert budget["call_cap"] == 750
    assert budget["arms_esj"] == ["111", "011", "101", "110"]
    assert budget["actuals"]["actual_api_attempts_total"] == 600
    assert budget["actuals"]["duplicate_sample_sends"] == 0


def test_primary_metric_is_five_span_fields_without_modality():
    assert SPAN_FIELDS == (
        "actor", "action", "condition", "constraint", "exception")
    assert PRIMARY_METRIC == "coarse_five_field_mean_f1"
    assert "modality" not in SPAN_FIELDS


def test_generated_prompts_use_modular_modules_without_old_guidance():
    for arm in runner.ARMS:
        system, user = runner.render_prompt(arm, "s_offline", "A must act.")
        text = system + "\n" + user
        for marker in runner.COMMON_BOUNDARY_MARKERS:
            assert marker in system
        for marker in runner.OLD_MARKERS:
            assert marker not in text
        if arm[1] == "1":
            assert "Semantic interpretation rules" in system
        else:
            assert "Semantic interpretation rules" not in system
        if arm[0] == "1":
            assert "Synthetic worked examples" in user
        else:
            assert "Synthetic worked examples" not in user
        if arm[2] == "1":
            assert "Output organization" in system
        else:
            assert "Output organization" not in system
        assert "A must act." in user


def test_generated_file_is_the_actual_request_source():
    for arm in runner.ARMS:
        assert runner._load_generated_prompt(arm).path.name.endswith(
            f"direct_llm_modular_{arm}_v1.md")

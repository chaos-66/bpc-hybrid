# -*- coding: utf-8 -*-
"""Static/offline tests for the four-arm Actor-refinement experiment."""

from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _path in (SRC, SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import run_actor_refinement_experiment_v1 as runner  # noqa: E402


def test_t7_repair_v1_explicitly_pinned() -> None:
    assert runner.CANONICALIZER_POLICY == "repair_v1"
    manifest = runner.validate_experiment_manifest()
    assert manifest["canonicalizer"]["policy"] == "repair_v1"
    assert manifest["canonicalizer"]["policy_explicit_pin"] is True
    assert runner.build_experiment_manifest()["canonicalizer"]["policy"] == "repair_v1"


def test_t8_same_evaluator_for_all_arms() -> None:
    manifest = runner.validate_experiment_manifest()
    assert manifest["evaluator"]["id"] == runner.EVALUATOR_ID
    assert manifest["evaluator"]["same_for_all_arms"] is True
    assert runner.EVALUATOR_ID == "sun_literal_overlap_evaluation@2.0.0"


def test_t9_same_frozen_150_sample_ids() -> None:
    samples = runner.load_samples()
    assert len(samples) == 150
    assert len({row["sample_id"] for row in samples}) == 150
    assert samples[0]["sample_id"] == "estg_000002"
    manifest = runner.validate_experiment_manifest()
    assert manifest["dataset"]["sample_count"] == 150
    assert manifest["dataset"]["sample_ids_sha256"] == runner.sample_ids_sha256(samples)
    assert manifest["design"]["samples_per_arm"] == 150
    assert manifest["design"]["planned_calls"] == 600


def test_four_experimental_arms_and_no_combined_arm() -> None:
    assert runner.ARM_ORDER == ("B0", "R", "P", "C")
    assert set(runner.ARMS) == {"B0", "R", "P", "C"}
    manifest = runner.validate_experiment_manifest()
    assert manifest["design"]["arms"] == ["B0", "R", "P", "C"]
    assert manifest["design"]["combined_arm_allowed"] is False
    assert manifest["design"]["repeat_count"] == 0


def test_retry_policy_is_zero() -> None:
    assert runner.RETRY == 0
    assert runner.STREAM is False
    assert runner.THINKING == {"type": "disabled"}
    manifest = runner.validate_experiment_manifest()
    assert manifest["sampling"]["retry"] == 0
    assert manifest["sampling"]["stream"] is False
    assert manifest["sampling"]["thinking"] == {"type": "disabled"}


def test_dry_run_is_zero_api_and_deterministic() -> None:
    result = runner.dry_run()
    assert result["planned_calls"] == 600
    assert result["llm_api_calls"] == 0
    assert result["network_calls"] == 0
    assert set(result["estimated_input_tokens_per_arm"]) == {"B0", "R", "P", "C"}
    assert sum(result["estimated_input_tokens_per_arm"].values()) == result[
        "estimated_input_tokens"]


def test_prompt_hashes_match_frozen_manifest() -> None:
    manifest = runner.validate_experiment_manifest()
    for arm in runner.ARM_ORDER:
        assert manifest["prompts"][arm]["sha256"] == runner._sha256_file(
            runner.prompt_path(arm))


def test_no_gold_construction_in_execution_runner_source() -> None:
    source = inspect.getsource(runner)
    for forbidden in (
        "build_canonical_gold_records",
        "evaluate_sun_literal_overlap",
        "estg_150_human_correction",
        "data/gold",
    ):
        assert forbidden not in source
    assert "load_project_env=True" in source
    assert "POLICY_REPAIR" in source
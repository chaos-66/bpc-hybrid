# -*- coding: utf-8 -*-
"""Focused tests for the Stage 3 paired benchmark and its arms.

Locks the properties the paper's Table 3 depends on:

- the benchmark has compliant controls, so precision and specificity have a
  denominator (the original 30-item panel had none);
- every pair is anti-degenerate (control compliant, variant violating);
- a correctly GROUNDED checker scores perfectly, which proves the benchmark is
  measurable and its Ground Truth is internally consistent;
- the similarity-grounded predecessors score degenerately on exactly the same
  items, so the gap is a grounding effect rather than a benchmark defect.

All three artifacts are zero-API; these tests only read the frozen reports.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
BENCHMARK_MANIFEST = (ROOT / "data" / "development" / "stage3_synth"
                      / "stage3_paired_benchmark_v1.json")
TYPES = ("missing_action", "incorrect_actor", "out_of_order")


@pytest.fixture(scope="module")
def benchmark():
    if not BENCHMARK_MANIFEST.is_file():
        pytest.skip("paired benchmark manifest unavailable")
    return json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def grounded():
    path = REPORTS / "stage3_grounded_checker_v1.json"
    if not path.is_file():
        pytest.skip("grounded checker report unavailable")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def predecessors():
    path = REPORTS / "stage3_predecessors_paired_v1.json"
    if not path.is_file():
        pytest.skip("predecessor report unavailable")
    return json.loads(path.read_text(encoding="utf-8"))


def test_benchmark_has_compliant_controls(benchmark) -> None:
    counts = benchmark["counts"]
    assert counts["items"] == 60
    assert counts["pairs"] == 30
    assert counts["by_role"] == {"control": 30, "variant": 30}
    # the compliant class must exist, or precision/specificity have no
    # denominator -- this is the defect the benchmark was built to fix
    assert counts["by_gold_label"]["compliant"] == 30
    for t in TYPES:
        assert counts["by_gold_label"][t] == 10


def test_every_pair_is_anti_degenerate(benchmark) -> None:
    """A control must NOT violate; its variant MUST."""
    assert benchmark["anti_degeneracy"]["passed"] is True
    assert benchmark["anti_degeneracy"]["problems_count"] == 0

    observed = 0
    for item in benchmark["items"]:
        if item["role"] != "control":
            continue
        variant = next(i for i in benchmark["items"]
                       if i["pair_id"] == item["pair_id"]
                       and i["role"] == "variant")
        assert item["structural_observation"]["violated"] is False
        assert variant["structural_observation"]["violated"] is True
        assert item["gold_violation_type"] == "compliant"
        assert variant["gold_violation_type"] == item["target_violation_type"]
        observed += 1
    assert observed == 30


def test_controls_are_the_frozen_original_bpmn(benchmark) -> None:
    """Controls must reuse frozen Stage 1 bytes, not newly authored files."""
    panel = json.loads((
        ROOT / "data" / "development" / "stage3_synth"
        / "synthetic_controlled_error_extension_v1.json"
    ).read_text(encoding="utf-8"))
    source_hashes = {v["source_bpmn_sha256"] for v in panel["variants"]}
    for item in benchmark["items"]:
        if item["role"] != "control":
            continue
        assert item["bpmn_path"].startswith("data/input/stage1_stage3/gdpr7/")
        assert item["bpmn_sha256"] in source_hashes


def test_grounded_checker_scores_perfectly(grounded) -> None:
    """The benchmark is measurable: correct grounding => perfect score."""
    assert grounded["items"] == 60
    assert grounded["llm_calls"] == 0
    for t in TYPES:
        assert grounded["per_type"][t]["f1"] == 1.0, t
    assert grounded["macro_f1"] == 1.0
    assert grounded["micro_f1"]["f1"] == 1.0
    assert grounded["compliant_specificity"] == 1.0
    assert grounded["compliant_false_positive_rate"] == 0.0
    assert grounded["variant_exact_type_accuracy"] == 1.0
    assert grounded["unobservable"] == 0


def test_predecessors_are_degenerate_on_the_same_items(predecessors) -> None:
    """The negative result the paper must report honestly.

    Similarity grounding fails here; that is a grounding effect, not evidence
    that the predecessors' algorithms are weak, and the report says so.
    """
    assert predecessors["items"] == 60
    assert predecessors["llm_calls"] == 0
    arms = predecessors["arms"]
    assert set(arms) == {"sun_reconstruction", "winter_wrapper"}

    sun = arms["sun_reconstruction"]
    winter = arms["winter_wrapper"]

    # neither predecessor reaches a usable macro-F1 on this corpus
    assert sun["macro_f1"] < 0.40
    assert winter["macro_f1"] < 0.40
    # out_of_order is 0 for both -- the relation never grounds
    assert sun["per_type"]["out_of_order"]["f1"] == 0.0
    assert winter["per_type"]["out_of_order"]["f1"] == 0.0
    # the Sun arm cannot even observe many items; never zero-filled
    assert sun["unobservable"] > 0
    # and the grounded reference is far above both
    reference = predecessors["grounded_reference"]
    assert reference is not None
    assert reference["macro_f1"] == 1.0
    assert reference["macro_f1"] > sun["macro_f1"]
    assert reference["macro_f1"] > winter["macro_f1"]

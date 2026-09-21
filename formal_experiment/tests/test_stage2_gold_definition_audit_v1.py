# -*- coding: utf-8 -*-
"""Focused tests for the Stage 2 Gold definition audit.

Locks the audit invariants that the paper's Table 1 relies on, so a future
Gold or evaluator edit cannot silently change them:

- the published Gold's five-field spans are structurally well formed
  (span text == approved_text_en[start:end]) and their counts are frozen;
- the Gold is demonstrably human-adjudicated (no record accepted verbatim);
- the condition/constraint boundary is applied consistently;
- the Direct-LLM advantage over the rules baseline SURVIVES a matched
  constraint definition (this is the fairness property Table 1 depends on).

The audit is zero-API and reads only the published Gold plus the two frozen
formal arm prediction envelopes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for candidate in (ROOT, SRC):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))


def _load_audit_module():
    path = ROOT / "scripts" / "audit_stage2_gold_definition_v1.py"
    spec = importlib.util.spec_from_file_location("gold_definition_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def report():
    return _load_audit_module().collect()


def test_gold_structure_is_well_formed(report) -> None:
    assert report["records"] == 150
    assert report["structure"]["all_span_texts_match_source_slice"] is True
    assert report["structure"]["malformed_count"] == 0
    assert report["structure"]["per_field_spans"] == {
        "actor": 48, "action": 247, "condition": 214,
        "constraint": 302, "exception": 13,
    }
    assert report["structure"]["total_five_field_spans"] == 824


def test_gold_is_human_adjudicated_not_accepted_verbatim(report) -> None:
    assert report["provenance"][
        "records_with_all_six_decisions_accepted"] == 0
    counts = report["provenance"]["decision_counts"]
    for field in ("action", "condition"):
        assert counts[f"{field}=edited"] == 150, field


def test_condition_constraint_boundary_is_consistent(report) -> None:
    boundary = report["boundary"]
    assert boundary["constraint_spans"] == 302
    # only a handful of constraints open with a condition marker
    assert boundary["constraints_starting_with_condition_marker"] == 6
    # overlaps are the documented nested-constraint rule, not label confusion
    assert boundary["condition_constraint_overlapping_pairs"] == 11
    assert boundary["constraint_strictly_inside_condition"] == 7
    assert boundary["condition_strictly_inside_constraint"] == 4
    assert len(boundary["identical_text_used_as_both_fields"]) == 1


def test_definitional_breadth_is_disclosed(report) -> None:
    """Our constraint definition is broader than Sun's marker-based one.

    This is the comparability caveat the paper must state, so the audit has to
    keep measuring it.
    """
    coverage = report["marker_coverage"]["constraint"]
    assert coverage["spans"] == 302
    # a clear majority of our constraints carry no Sun marker class at all
    assert coverage["no_marker_class_share"] > 0.50
    # and only a minority carry a Sun marker
    assert coverage["sun_marker_share"] < 0.50


def test_direct_llm_advantage_survives_matched_definition(report) -> None:
    """The fairness property Table 1 depends on."""
    views = report["fairness"]["views"]
    assert set(views) == {
        "full_gold_definition",
        "matched_sun_marker_phrases",
        "matched_sun_marker_phrases_and_numerals",
    }

    # baseline: the published (broader) definition
    assert abs(views["full_gold_definition"]["arms"]["sun_rule_only"]["f1"]
               - 0.7631) < 0.0002
    assert abs(views["full_gold_definition"]["arms"]["direct_llm"]["f1"]
               - 0.8378) < 0.0002
    assert abs(views["full_gold_definition"]["delta_overall_f1_pp"]
               - 7.47) < 0.05

    # the advantage survives every matched view
    assert report["fairness"][
        "direct_llm_advantage_survives_matched_view"] is True
    for label in ("matched_sun_marker_phrases",
                  "matched_sun_marker_phrases_and_numerals"):
        assert views[label]["delta_overall_f1_pp"] > 0, label
        # narrowing the definition reduces the constraint-field advantage
        assert (views[label]["delta_constraint_f1_pp"]
                < views["full_gold_definition"]["delta_constraint_f1_pp"])
    # ...but the constraint advantage must never be spun as a single number
    matched_constraint = [views[label]["delta_constraint_f1_pp"]
                          for label in ("matched_sun_marker_phrases",
                                        "matched_sun_marker_phrases_and_numerals")]
    assert min(matched_constraint) < 3.0
    assert max(matched_constraint) > 5.0

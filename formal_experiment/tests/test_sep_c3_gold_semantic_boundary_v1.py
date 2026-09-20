# -*- coding: utf-8 -*-
"""Focused tests for the Gold-driven semantic-boundary analysis script."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_sep_c3_gold_semantic_boundary_v1 as boundary  # noqa: E402


def _gold_records():
    return list(boundary.read_json(boundary.GOLD_PATH)["records"])


def test_condition_constraint_actual_overlap_counts():
    records = _gold_records()
    overlap = boundary.actual_overlap_summary(records)
    assert overlap["clause_level_condition_constraint_pairs"] == 11
    assert set(overlap["clause_level_condition_constraint_samples"]) == {
        "estg_000028",
        "estg_000037",
        "estg_000057",
        "estg_000061",
        "estg_000077",
        "estg_000106",
        "estg_000214",
        "estg_000218",
        "estg_000223",
        "estg_000716",
    }
    assert overlap["sample_level_condition_constraint_pairs"] == 21


def test_merged_hull_overlap_is_diagnostic_only():
    merged = boundary.merged_span_overlap_summary(_gold_records())
    assert merged["counts"]["hull_overlap"] == 43
    assert merged["counts"]["hull_contains"] == 14
    assert merged["counts"]["hull_contained_by"] == 17
    assert merged["counts"]["hull_partial_overlap"] == 12


def test_nested_pair_geometry_and_manual_flag():
    cases = boundary.build_gold_cases(_gold_records())
    nested_pairs = [
        pair for case in cases for pair in case.get("nested_pairs") or []
    ]
    assert len(nested_pairs) == 11
    counts = Counter(pair["relation"] for pair in nested_pairs)
    assert counts == {"contains": 7, "contained_by": 4}
    assert all(pair["manual_review_required"] for pair in nested_pairs)

    by_id = {case["sample_id"]: case for case in cases}
    assert by_id["estg_000052"]["condition_only"] is True
    assert by_id["estg_000052"]["nested_condition_constraint"] is False
    assert by_id["estg_000106"]["nested_condition_constraint"] is True


def test_source_text_anomaly_detection_targeted_arms():
    summary = boundary.source_text_anomaly_summary()
    assert summary["targeted_arm_anomaly_count"] == 4
    observed = {
        (row["arm"], row["sample_id"])
        for row in summary["targeted_arm_anomalies"]
    }
    assert observed == {
        ("A", "estg_000044"),
        ("A", "estg_000720"),
        ("C", "estg_000035"),
        ("C", "estg_000044"),
    }
    assert all(
        row["spans_beyond_original_source"] == 0
        for row in summary["targeted_arm_anomalies"]
    )
    assert all(
        row["original_slice_check_passed"]
        for row in summary["targeted_arm_anomalies"]
    )

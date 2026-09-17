# -*- coding: utf-8 -*-
"""Focused verification for the SEP-C2 target-consistency diagnosis."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_sep_c2_target_consistency_diagnosis_v1.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("sep_c2_target_diagnosis", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load diagnosis builder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_target_diagnosis_structure_and_safety():
    module = _load_module()
    report = module.build_report()
    assert report["status"] == "completed_10_evaluated_one_source_pending"
    assert len(report["overall_classification_table"]) == 10
    assert report["target_structure"]["overall"]["group_counts"] == {
        "A": 101,
        "B": 15,
        "C": 34,
        "D": 0,
    }
    assert len(report["group_metrics"]) == 30
    assert sum(row["n"] for row in report["group_metrics"]) == 1500
    assert len(report["case_studies"]["cases"]) == 10
    assert report["implementation_audit"]["source_pending"]["records_failed"] == 0
    assert report["implementation_audit"]["source_pending"]["records_not_run"] == 150
    assert report["safety"]["full_150_denominator_preserved"] is True
    assert report["safety"]["source_pending_counted_as_failure"] is False


def test_first_clause_target_audit_is_contract_consistent():
    module = _load_module()
    report = module.build_report()
    assert report["target_structure"]["overall"]["first_clause_start_zero"] == 141
    assert report["target_structure"]["overall"]["first_clause_covers_full_sentence"] == 26
    assert report["target_structure"]["overall"]["records_with_clause_order_not_sorted_by_start"] == 1
    assert report["target_structure"]["overall"]["unsorted_sample_ids"] == ["estg_000136"]
    for metric in report["group_metrics"]:
        if metric["group"] in {"A", "B"}:
            assert metric["first_wrong_pred_matches_later"] == 0

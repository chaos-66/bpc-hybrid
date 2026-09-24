# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evaluate_stage3_table3_v4_r1 as evaluator


TYPES = ("missing_action", "incorrect_actor", "out_of_order")
RULES = ("r1", "r2", "r3", "r4", "r5")
METHODS = ("sun", "ours", "winter")


def _valid_docs():
    rows = []
    signals = []
    for method in METHODS:
        for case_index in range(20):
            case_id = f"case_{case_index:02d}"
            signals_by_rule = {}
            for rule_id in RULES:
                checks = {}
                for check_type in TYPES:
                    signal = {"status": "unknown", "raw_score": None,
                              "denominator": 0, "observable": False,
                              "reason": "synthetic"}
                    checks[check_type] = signal
                    signals.append({"method": method, "case_id": case_id,
                                    "rule_id": rule_id, "check_type": check_type, **signal})
                signals_by_rule[rule_id] = checks
            rows.append({"row_method_id": method, "case_id": case_id,
                         "signals_by_rule": signals_by_rule})
    cfg = {"scope": {"rule_ids": list(RULES), "case_count": 20}}
    return rows, {"count": len(signals), "signals": signals}, cfg


def test_coverage_formula_subtracts_both_unknown_directions() -> None:
    counts = {
        "tp": 1, "fp": 1, "fn": 1, "tn": 1,
        "unknown_positive": 2, "unknown_negative": 3,
        "positive_cells": 4, "negative_cells": 5,
        "not_applicable_cells": 0, "cells": 10,
    }
    out = evaluator._finalize(counts)
    assert out["observable_coverage"] == 0.5
    assert out["unknown_rate"] == 0.5
    assert out["observable_coverage"] + out["unknown_rate"] == 1.0


def test_unique_key_validation_accepts_complete_matrix() -> None:
    rows, signals_doc, cfg = _valid_docs()
    evaluator._validate_prediction_structure(rows=rows, signals_doc=signals_doc, cfg=cfg)


def test_unique_key_validation_rejects_duplicate_row() -> None:
    rows, signals_doc, cfg = _valid_docs()
    rows[1] = dict(rows[0])
    with pytest.raises(RuntimeError, match="duplicate prediction row"):
        evaluator._validate_prediction_structure(rows=rows, signals_doc=signals_doc, cfg=cfg)


def test_unique_key_validation_rejects_missing_rule() -> None:
    rows, signals_doc, cfg = _valid_docs()
    rows[0]["signals_by_rule"].pop("r1")
    with pytest.raises(RuntimeError, match="rule-key drift"):
        evaluator._validate_prediction_structure(rows=rows, signals_doc=signals_doc, cfg=cfg)

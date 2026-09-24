# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evaluate_stage3_table3_v4 as evaluator


def test_classify_contract() -> None:
    assert evaluator._classify("violated", "violated") == "tp"
    assert evaluator._classify("violated", "satisfied") == "fn"
    assert evaluator._classify("violated", "unknown") == "unknown_positive"
    assert evaluator._classify("satisfied", "violated") == "fp"
    assert evaluator._classify("satisfied", "satisfied") == "tn"
    assert evaluator._classify("satisfied", "unknown") == "unknown_negative"


def test_finalize_null_precision_and_zero_f1() -> None:
    no_positive = evaluator._finalize({
        "tp": 0, "fp": 0, "fn": 5, "tn": 10,
        "unknown_positive": 0, "unknown_negative": 0,
        "positive_cells": 5, "negative_cells": 10,
        "not_applicable_cells": 5, "cells": 15,
    })
    assert no_positive["precision"] is None
    assert no_positive["recall"] == 0.0
    assert no_positive["f1"] == 0.0
    perfect = evaluator._finalize({
        "tp": 5, "fp": 0, "fn": 0, "tn": 10,
        "unknown_positive": 0, "unknown_negative": 0,
        "positive_cells": 5, "negative_cells": 10,
        "not_applicable_cells": 5, "cells": 15,
    })
    assert perfect["f1"] == 1.0


def test_real_v4_report_is_complete_and_reference_blind(tmp_path) -> None:
    report = evaluator.evaluate(
        out_dir=Path("outputs/development/stage3_table3_v4"),
        report_json=tmp_path / "report.json",
        report_md=tmp_path / "report.md",
        report_manifest=tmp_path / "manifest.json",
    )
    assert report["schema_version"] == "stage3_table3_v4_report@1.0.0"
    assert report["diagnostics"]["reference_leakage_check"]["runner_declared_no_reference"] is True
    assert report["diagnostics"]["reference_leakage_check"]["prediction_declared_no_reference"] is True
    for method in ("sun", "ours", "winter"):
        overall = report["methods"][method]["overall"]
        assert overall["cells"] == 50
        assert overall["not_applicable_cells"] == 10
        assert overall["tp"] + overall["fn"] == 15
        assert overall["fp"] + overall["tn"] + overall["unknown_negative"] == 35
    assert report["diagnostics"]["acceptance"] == "needs_method_review"
    assert report["diagnostics"]["unknown_cause_counts"]["order_denominator_zero_cells"] > 0
    assert report["diagnostics"]["structural_checks"]["no_prediction_modification"] is True
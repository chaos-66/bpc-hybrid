# -*- coding: utf-8 -*-
"""Focused tests for the unified five-class re-evaluation
(``bpc_hybrid.s3_extended_unified`` + runner).

Required verifications (task sheet item 2.7):
- changing only evaluation labels (expected/gold) never changes predictions;
- the SAME decision function is applied to the compliant (control) side and
  the violation (variant) side;
- failed and unobservable samples stay inside the evaluation denominators.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bpc_hybrid.s3_extended_unified import (  # noqa: E402
    unified_prediction,
    unified_rows,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    EXTENDED_TYPES,
    evaluate_extended,
)
import reevaluate_s3_extended_unified_v1 as runner  # noqa: E402

PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
REF_SRC = ROOT / "outputs/development/s3_extended_unified_v1/reference"
RULES_SRC = ROOT / "outputs/development/s3_extended_unified_v1/rules_only"


def _real_row(source: Path, method: str = "winter", index: int = 0) -> dict:
    rows = [
        json.loads(line) for line in
        (source / method / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return copy.deepcopy(rows[index])


def test_unified_prediction_never_reads_expected_or_id() -> None:
    row = _real_row(REF_SRC)
    base = unified_prediction(row, "variant", 0.5)
    tampered = copy.deepcopy(row)
    tampered["expected_violation"] = (
        "exception_not_handled" if row["expected_violation"]
        != "exception_not_handled" else "constraint_violated")
    tampered["item_id"] = "completely_different_id"
    other = unified_prediction(tampered, "variant", 0.5)
    assert base["predicted"] == other["predicted"]
    assert base["all_unobservable"] == other["all_unobservable"]


def test_same_decision_function_on_both_sides() -> None:
    """If the variant scores equal the control scores the unified decisions
    must be identical (one rule, both sides)."""
    row = _real_row(RULES_SRC)
    variant_decision = unified_prediction(row, "variant", 0.5)
    # move variant score fields into control_scores shape
    control = {}
    for t in EXTENDED_TYPES:
        control[t] = {
            "score": row["scores"][t],
            "observable": row["observability"][t]["observable"],
            "reason": row["observability"][t]["reason"],
            "exact_contradiction":
                row["scores_detail"][t].get("exact_contradiction"),
        }
    twin = dict(row)
    twin["control_scores"] = control
    control_decision = unified_prediction(twin, "control", 0.5)
    assert control_decision["predicted"] == variant_decision["predicted"]
    assert control_decision["all_unobservable"] == \
        variant_decision["all_unobservable"]


def test_unified_rows_keep_old_and_record_raw() -> None:
    rows = [
        json.loads(line) for line in
        (REF_SRC / "winter" / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][:5]
    out = unified_rows(rows, 0.5)
    assert len(out) == 5
    for row, new in zip(rows, out):
        assert new["predicted_conditional_old"] == row["predicted_violation_type"]
        assert new["prediction_rule"].startswith("unified_five_class")
        assert new["unified_predicted_raw"] is not None or new[
            "prediction_all_unobservable"] is True


def test_failed_and_unobservable_samples_stay_in_denominator() -> None:
    """A variant with every type unobservable must predict None and count as
    FN in the evaluator with the reason preserved (never dropped, never
    treated as compliant)."""
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    gold = {v["variant_id"]: {"expected_violation": v["expected_violation"]}
            for v in panel["variants"]}
    items = list(gold.items())[:3]
    rows = []
    for i, (item_id, g) in enumerate(items):
        unobs = {t: {"observable": False, "reason": "stage2_prediction_failed"}
                 for t in EXTENDED_TYPES}
        rows.append({
            "schema_version": "stage3_extended_prediction@1.0.0",
            "item_id": item_id,
            "expected_violation": g["expected_violation"],
            "predicted_violation_type": None,
            "scores": {t: None for t in EXTENDED_TYPES},
            "scores_detail": {t: {} for t in EXTENDED_TYPES},
            "observability": unobs,
            "control_scores": {
                t: {"score": None, "observable": False,
                    "reason": "stage2_prediction_failed",
                    "exact_contradiction": None} for t in EXTENDED_TYPES},
        })
    ev = evaluate_extended(rows, gold)
    assert ev["detected"] == 0
    assert ev["missed"] == len(rows)
    assert ev["denominator"]["unobservable_total"] == len(rows)
    assert ev["denominator"]["unobservable_by_reason"][
        "stage2_prediction_failed"] == len(rows)
    assert ev["macro_f1"] == 0.0


def test_runner_reproduces_committed_reference_numbers(tmp_path: Path) -> None:
    """A tmp re-run over the real persisted rows must reproduce the committed
    unified aggregate (same rows, same decision -> same numbers)."""
    committed = json.loads(
        (ROOT / "outputs/reports/s3_extended_unified_v1_reference.json")
        .read_text(encoding="utf-8"))
    agg = runner.run_source("reference", methods=("winter",), overwrite=True,
                            output_root=tmp_path / "out",
                            report_root=tmp_path / "rep")
    ev = agg["methods"]["winter"]["variant_only_evaluation_unified"]
    cev = committed["methods"]["winter"]["variant_only_evaluation_unified"]
    assert ev["macro_f1"] == pytest.approx(cev["macro_f1"])
    assert ev["exact_type_accuracy"] == pytest.approx(cev["exact_type_accuracy"])
    assert ev["wrong_type"] == cev["wrong_type"]
    pe = agg["methods"]["winter"]["paired_evaluation_unified"]
    cpe = committed["methods"]["winter"]["paired_evaluation_unified"]
    assert pe["five_class_accuracy"] == pytest.approx(cpe["five_class_accuracy"])


def test_old_conditional_reproduction_matches_stored_values() -> None:
    """Self-check: the old-conditional numbers recomputed from persisted rows
    equal the numbers stored before this re-evaluation."""
    stored = json.loads(
        (ROOT / "outputs/reports/s3_extended_unified_v1_reference.json")
        .read_text(encoding="utf-8"))
    for method in ("winter", "sun", "bm25", "tfidf_svd"):
        o = json.loads((REF_SRC / method / "old_vs_new.json")
                       .read_text(encoding="utf-8"))
        # stored five_class old values are part of the aggregate's old_vs_new
        assert o["paired"]["five_class_accuracy"]["old_conditional"] == \
            pytest.approx(
                stored["methods"][method]["old_vs_new"]["paired"][
                    "five_class_accuracy"]["old_conditional"])

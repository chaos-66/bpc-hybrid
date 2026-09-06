# -*- coding: utf-8 -*-
"""Focused tests for the Stage-2 -> Stage-3 linkage runner
(``scripts/run_gdpr_s2_s3_linkage_v1.py``).

Verifies on the REAL committed artifacts:
- the runner consumes the external Rules-Only GDPR prediction capsule and
  never falls back to the panel's locked deterministic extraction (every
  output row carries an external arm/sample provenance; a capsule with zero
  prediction records produces 40 explicit failure rows with reason
  stage2_prediction_missing);
- full four-method run reproduces the committed report numbers (aggregate
  report JSON on disk); evaluation/paired structures are evaluator-complete.
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
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_gdpr_s2_s3_linkage_v1 import ARM_PATHS  # noqa: E402
import run_gdpr_s2_s3_linkage_v1 as linkage  # noqa: E402
from bpc_hybrid.stage3_extended_violations import EXTENDED_TYPES  # noqa: E402

ARM_CAPSULE = ARM_PATHS["rules_only"]
REPORT = ROOT / "outputs/reports/gdpr_s2_s3_linkage_v1_rules_only.json"
PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"


def test_real_capsule_exists() -> None:
    assert ARM_CAPSULE.is_file()
    doc = json.loads(ARM_CAPSULE.read_text(encoding="utf-8"))
    assert doc["schema_version"] == "gdpr7_sun_rule_only_predictions@1.0.0"
    assert doc["record_count"] == 74
    assert all(r["request_status"] == "ok" for r in doc["records"])


def test_report_aggregate_exists_and_has_four_methods() -> None:
    agg = json.loads(REPORT.read_text(encoding="utf-8"))
    assert set(agg["methods"]) == {"winter", "sun", "bm25", "tfidf_svd"}
    for method, info in agg["methods"].items():
        ev = info["variant_only_evaluation"]
        pe = info["paired_evaluation"]
        assert ev["denominator"]["total_items"] == 40
        assert pe["total_objects"] == 80
        assert pe["control_objects"] == 40
        assert pe["variant_objects"] == 40
        assert set(ev["per_type"]) == set(EXTENDED_TYPES)
        assert 0 <= pe["control_false_positive_rate"] <= 1


def test_every_row_has_external_provenance_no_fallback(tmp_path: Path) -> None:
    """A real single-method re-run to a temp output root must label every
    row as external (no fallback to the locked reference extraction)."""
    out_root = tmp_path / "out"
    rep_root = tmp_path / "rep"
    summary = linkage.run_arm("rules_only", methods=("winter",),
                              overwrite=True, output_root=out_root,
                              report_root=rep_root)
    rows = [
        json.loads(line)
        for line in (out_root / "gdpr_s2_s3_linkage_v1_rules_only"
                     / "winter" / "predictions.jsonl")
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 40
    for row in rows:
        assert row["external_arm"] == "rules_only"
        assert row["external_projection"].startswith(
            "stage2_first_valid_span_projection")
        assert "external_sample_id" in row
    # numbers must match the committed full-method run for winter
    committed = json.loads(REPORT.read_text(encoding="utf-8"))
    assert summary["methods"]["winter"]["variant_only_evaluation"]["macro_f1"] == \
        pytest.approx(
            committed["methods"]["winter"]["variant_only_evaluation"]["macro_f1"])
    assert summary["methods"]["winter"]["paired_evaluation"]["paired_accuracy"] == \
        pytest.approx(
            committed["methods"]["winter"]["paired_evaluation"]["paired_accuracy"])


def test_empty_arm_capsule_never_backfills(tmp_path: Path) -> None:
    """With zero prediction records every variant row must be an explicit
    stage2_prediction_missing failure (the detector must NOT fall back to
    the locked deterministic six-element extraction)."""
    doc = json.loads(ARM_CAPSULE.read_text(encoding="utf-8"))
    empty = copy.deepcopy(doc)
    empty["records"] = []
    fake = tmp_path / "empty_predictions.json"
    fake.write_text(json.dumps(empty, ensure_ascii=False), encoding="utf-8")
    out_root = tmp_path / "out2"
    rep_root = tmp_path / "rep2"
    summary = linkage.run_arm("rules_only", predictions_path=fake,
                              methods=("winter",), overwrite=True,
                              output_root=out_root, report_root=rep_root)
    rows = [
        json.loads(line)
        for line in (out_root / "gdpr_s2_s3_linkage_v1_rules_only"
                     / "winter" / "predictions.jsonl")
        .read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 40
    assert all(r["predicted_violation_type"] is None for r in rows)
    reasons = {
        r["observability"][r["expected_violation"]]["reason"] for r in rows
    }
    assert reasons == {"stage2_prediction_missing"}
    ev = summary["methods"]["winter"]["variant_only_evaluation"]
    assert ev["detected"] == 0
    assert ev["denominator"]["unobservable_by_reason"].get(
        "stage2_prediction_missing") == 40

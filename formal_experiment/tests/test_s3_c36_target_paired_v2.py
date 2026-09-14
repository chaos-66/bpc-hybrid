# -*- coding: utf-8 -*-
"""Focused tests for the gated C36 target-paired successor."""

from __future__ import annotations

import importlib.util
import json
import shutil
import uuid
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path[:0] = [str(ROOT / "src")]

from bpc_hybrid.s3_c36_target_paired_v2 import (  # noqa: E402
    BASELINE_NAME,
    audit_gate,
    compare_target_paired_gated,
    derive_target_paired_rows,
    read_json,
    read_jsonl,
)

PANEL_PATH = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"
C36_PREDICTIONS = (ROOT / "outputs/evidence/s3_formula_repair_v2/"
                   "extended_four/reference/winter/predictions.jsonl")
C36_MANIFEST = ROOT / "outputs/evidence/s3_formula_repair_v2/manifest.json"
C36_REPORT = ROOT / "outputs/reports/s3_formula_repair_v2.json"
V5_PREDICTIONS = ROOT / "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl"
V5_ARTIFACT_HASHES = ROOT / "outputs/evidence/s3_semantic_grounding_v5/artifact_hashes.json"


def _tmp_dir(name: str) -> Path:
    base = ROOT / ".tmp_c36_v2_tests" / f"{name}-{uuid.uuid4().hex}"
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_inputs():
    return (
        read_json(PANEL_PATH),
        read_jsonl(C36_PREDICTIONS),
        read_jsonl(V5_PREDICTIONS),
        read_json(C36_MANIFEST),
        read_json(V5_ARTIFACT_HASHES),
        read_json(C36_REPORT),
    )


def _gate(panel, c36_rows, current_rows, c36_manifest, current_hashes):
    return audit_gate(
        c36_rows=c36_rows, panel=panel, current_rows=current_rows,
        c36_manifest=c36_manifest,
        current_artifact_hashes=current_hashes,
        current_predictions_path=V5_PREDICTIONS,
        c36_predictions_path=C36_PREDICTIONS,
        c36_report=read_json(C36_REPORT), root=ROOT)


def test_real_frozen_inputs_pass_gate_with_verified_dependency():
    panel, c36_rows, current_rows, c36_manifest, hashes, _ = _load_inputs()
    audit = _gate(panel, c36_rows, current_rows, c36_manifest, hashes)
    assert audit["gate_status"] == "pass"
    assert audit["can_build_target_paired"] is True
    assert audit["blocking_issue_count"] == 0
    dep = audit["dependency_bindings"]["control_reconstruction"]
    assert dep["verified_frozen_match"] is True
    assert dep["verification_basis"] == "canonical_lf_utf8_text hash match"
    threshold = audit["threshold_binding"]
    assert threshold["all_rows_match_frozen_threshold"] is True
    assert threshold["frozen_manifest_gamma_ext"] == 0.5
    assert audit["field_audit"]["blocking_issues"] == []


def test_missing_or_duplicate_objects_block_gate():
    panel, c36_rows, current_rows, c36_manifest, hashes, _ = _load_inputs()
    broken = deepcopy(c36_rows)
    broken.pop()
    audit = _gate(panel, broken, current_rows, c36_manifest, hashes)
    assert audit["can_build_target_paired"] is False
    assert "incomplete_c36_rows" in audit["blocking_issue_codes"]

    duplicated = deepcopy(c36_rows)
    duplicated.append(deepcopy(duplicated[0]))
    audit2 = _gate(panel, duplicated, current_rows, c36_manifest, hashes)
    assert audit2["can_build_target_paired"] is False
    assert "duplicate_c36_ids" in audit2["blocking_issue_codes"]

    current_broken = [r for r in current_rows if not (
        r["side"] == "control" and r["item_id"] == panel["variants"][0]["variant_id"])]
    audit3 = _gate(panel, c36_rows, current_broken, c36_manifest, hashes)
    assert audit3["can_build_target_paired"] is False
    assert "incomplete_current_objects" in audit3["blocking_issue_codes"]


def test_input_hash_and_prediction_identity_drift_block_gate():
    panel, c36_rows, current_rows, c36_manifest, hashes, _ = _load_inputs()
    drifted = deepcopy(c36_rows)
    drifted[0]["source_hashes"]["variant_bpmn_sha256"] = "0" * 64
    audit = _gate(panel, drifted, current_rows, c36_manifest, hashes)
    assert audit["can_build_target_paired"] is False
    assert "c36_bpmn_hash_mismatch" in audit["blocking_issue_codes"]

    bad_hashes = deepcopy(hashes)
    key = "outputs/evidence/s3_semantic_grounding_v5/predictions.jsonl"
    bad_hashes["artifacts"][key] = "0" * 64
    audit2 = _gate(panel, c36_rows, current_rows, c36_manifest, bad_hashes)
    assert audit2["can_build_target_paired"] is False
    assert "current_prediction_hash_mismatch" in audit2["blocking_issue_codes"]


def test_invalid_reconstruction_fields_and_threshold_block_gate():
    panel, c36_rows, current_rows, c36_manifest, hashes, _ = _load_inputs()
    bad_score = deepcopy(c36_rows)
    bad_score[0]["control_scores"]["constraint_violated"] = {
        "observable": True, "score": None, "reason": None,
        "exact_contradiction": None,
    }
    audit = _gate(panel, bad_score, current_rows, c36_manifest, hashes)
    assert audit["can_build_target_paired"] is False
    assert any(code in audit["blocking_issue_codes"] for code in (
        "control_score_missing_or_invalid",
        "control_reconstruction_not_boolean"))

    bad_gamma = deepcopy(c36_rows)
    bad_gamma[0]["gamma_ext"] = None
    bad_manifest = deepcopy(c36_manifest)
    audit2 = _gate(panel, bad_gamma, current_rows, bad_manifest, hashes)
    assert audit2["can_build_target_paired"] is False
    assert "invalid_row_gamma_ext" in audit2["blocking_issue_codes"]


def test_dependency_mismatch_blocks_gate():
    panel, c36_rows, current_rows, c36_manifest, hashes, _ = _load_inputs()
    broken_manifest = deepcopy(c36_manifest)
    key = next(k for k in broken_manifest["implementation_hashes"]
               if "stage3_extended_violations.py" in k.replace("\\", "/"))
    broken_manifest["implementation_hashes"][key] = "0" * 64
    audit = _gate(panel, c36_rows, current_rows, broken_manifest, hashes)
    assert audit["can_build_target_paired"] is False
    assert "reconstruction_dependency_mismatch" in audit["blocking_issue_codes"]
    assert audit["dependency_bindings"]["control_reconstruction"][
        "verified_frozen_match"] is False


def test_comparison_numbers_are_preserved_after_gate():
    panel, c36_rows, current_rows, c36_manifest, hashes, _ = _load_inputs()
    audit = _gate(panel, c36_rows, current_rows, c36_manifest, hashes)
    assert audit["can_build_target_paired"] is True
    derived = derive_target_paired_rows(c36_rows)
    comparison = compare_target_paired_gated(derived, current_rows, panel)
    baseline = comparison["c36_winter_style_baseline"]
    current = comparison["current_v5"]
    assert baseline["target_paired_macro_f1_four_types"] == 0.6036
    assert baseline["pair_success_count"] == 18
    assert current["target_paired_macro_f1_four_types"] == 0.6737
    assert current["pair_success_count"] == 21
    assert BASELINE_NAME == "Winter-style four-type extension baseline"


def test_blocked_entry_writes_no_valid_comparison(monkeypatch):
    tmp = _tmp_dir("blocked")
    try:
        from importlib.util import spec_from_file_location, module_from_spec
        runner_path = ROOT / "scripts/run_s3_c36_target_paired_v2.py"
        spec = spec_from_file_location("c36_v2_runner_test", runner_path)
        runner = module_from_spec(spec)
        spec.loader.exec_module(runner)
        runner.OUT_DIR = tmp / "evidence"
        runner.REPORT_JSON = tmp / "report.json"
        runner.REPORT_MD = tmp / "report.md"
        fake_audit = {
            "can_build_target_paired": False,
            "gate_status": "blocked",
            "blocking_issue_count": 1,
            "blocking_issue_codes": ["synthetic_block"],
            "blocking_issues": [{"code": "synthetic_block"}],
        }
        runner.audit_gate = lambda **kwargs: fake_audit
        result = runner.run(overwrite=False)
        assert result["status"] == "blocked"
        assert not (runner.OUT_DIR / "comparison.json").exists()
        report = json.loads(runner.REPORT_JSON.read_text(encoding="utf-8"))
        assert report["status"] == "BLOCKED_COMPATIBILITY_AUDIT"
        assert report["valid_comparison_generated"] is False
        assert "VERIFIED_DEVELOPMENT_COMPARISON" not in json.dumps(report)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

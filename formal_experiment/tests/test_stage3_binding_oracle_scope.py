"""Privileged binding inputs must never be reported as end-to-end Ours."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import run_stage3_binding_oracle_v1 as oracle


@pytest.mark.parametrize("ready", [False, True])
def test_both_report_paths_disclose_oracle_inputs(tmp_path, monkeypatch, ready):
    # Synthetic in-memory validation result isolates report propagation from
    # unchanged BPMN/annotation validation. No real review or Gold is read.
    monkeypatch.setattr(oracle, "ROOT", tmp_path)
    monkeypatch.setattr(oracle.validator, "validate_binding_gold", lambda doc: {
        "ready": ready, "status": "ready" if ready else "invalid_or_incomplete",
        "items_ready": 0, "items": 0, "errors": [], "warnings": [],
    })
    inputs = {
        "binding.json": {"items": []},
        "benchmark.json": {"benchmark_id": "synthetic", "items": []},
        "rules.json": {"schema_version": "synthetic", "records": []},
    }
    for name, content in inputs.items():
        (tmp_path / name).write_text(json.dumps(content), encoding="utf-8")
    originals = {name: (tmp_path / name).read_bytes() for name in inputs}
    report_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    out_dir = tmp_path / "diagnostic"
    report = oracle.run(
        tmp_path / "binding.json", tmp_path / "benchmark.json",
        tmp_path / "rules.json", out_dir, report_path, markdown_path)
    assert report["status"] == ("complete" if ready else "blocked_on_human_annotation")
    assert json.loads(report_path.read_text(encoding="utf-8")) == report
    assert report["claim_scope"] == "development_oracle_diagnostic"
    assert report["inference_uses_human_bindings"] is True
    assert report["inference_uses_declared_activity_ids"] is True
    assert report["automatic_grounding_evaluated"] is False
    assert report["end_to_end_ours_claim_allowed"] is False
    assert "oracle" in markdown_path.read_text(encoding="utf-8").lower()
    if ready:
        evaluation = json.loads((out_dir / "evaluation.json").read_text(encoding="utf-8"))
        assert evaluation["claim_scope"] == "development_oracle_diagnostic"
        assert evaluation["end_to_end_ours_claim_allowed"] is False
    else:
        assert not out_dir.exists()
    assert all((tmp_path / name).read_bytes() == content for name, content in originals.items())

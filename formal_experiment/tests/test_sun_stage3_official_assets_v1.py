"""Evidence integrity tests for the asset audit; no experiment/model execution."""
import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def audit_module():
    path = Path(__file__).resolve().parents[1] / "scripts/audit_sun_stage3_official_assets_v1.py"
    spec = importlib.util.spec_from_file_location("asset_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_missing_source_fails(audit_module, tmp_path):
    with pytest.raises(FileNotFoundError):
        audit_module.inventory(tmp_path / "missing")


def test_inventory_detects_changed_and_missing_bytes(audit_module, tmp_path):
    left, right = tmp_path / "a", tmp_path / "b"
    left.mkdir(); right.mkdir()
    (left / "base.bpmn").write_bytes(b"same")
    (right / "base.bpmn").write_bytes(b"same")
    (left / "rule.txt").write_bytes(b"original")
    (right / "rule.txt").write_bytes(b"changed")
    (left / "missing.txt").write_bytes(b"record")
    result = audit_module.compare(audit_module.inventory(left), audit_module.inventory(right))
    assert result["identical_count"] == 1
    assert result["different"] == ["rule.txt"]
    assert result["left_only"] == ["missing.txt"]


def test_metadata_exclusion_keeps_actual_inputs(audit_module, tmp_path):
    (tmp_path / "__MACOSX").mkdir()
    (tmp_path / "__MACOSX/._base.bpmn").write_bytes(b"metadata")
    (tmp_path / ".DS_Store").write_bytes(b"metadata")
    (tmp_path / "base.bpmn").write_bytes(b"input")
    assert list(audit_module.inventory(tmp_path)) == ["base.bpmn"]


def test_reference_gaps_are_not_negative_labels(audit_module):
    report = audit_module.build_report()
    assert report["copy_comparison"]["identical_count"] == 57
    reference = report["existing_project_reference"]
    assert reference["labeled_matching_pairs"] + len(reference["unlabeled_matching_pairs"]) == reference["full_matching_pairs"]
    assert reference["unlabeled_is_negative"] is False
    assert all(m["semantic_compliance"] == "not_determined_by_file_inventory" for m in report["models"])
    assert report["methodological_conclusions"]["v3_performance_publishable"] is False

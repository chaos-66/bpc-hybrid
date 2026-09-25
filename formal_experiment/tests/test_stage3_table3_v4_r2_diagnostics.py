# -*- coding: utf-8 -*-
"""Synthetic fixtures for the R2 non-scoring order diagnostics and contracts."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.sun_stage3 import order_failure_diagnostics_v1 as diag  # noqa: E402


class _FakeModel:
    def __init__(self):
        self.actions = [
            {"id": "T1", "name": "task one", "kind": "activity"},
            {"id": "T2", "name": "task two", "kind": "activity"},
        ]
        self.reachable = {}

    def is_reachable(self, source_id, target_id):
        return target_id in self.reachable.get(source_id, set())


class _FakeScorer:
    gamma = 0.8

    def __init__(self, mapping):
        self.mapping = mapping

    def _lemma(self, text):
        return str(text).lower()

    def _best_action_match(self, text, model):
        return self.mapping.get(text, (None, 0.0))


def _record(relations=None, projection=None, failed=False):
    return {
        "failed": failed,
        "order_relations": list(relations or []),
        "order_relation_projection": projection,
    }


def _signal(denominator=0, status="unknown"):
    return {"denominator": denominator, "status": status, "reason": "no_rule_order_endpoints"}


def _projection(reasons):
    return {"clause_audits": [{"clause_id": "c1", "rejections": [{"reason": r} for r in reasons]}]}


def test_projection_rejection_categories_are_distinguished():
    scorer = _FakeScorer({})
    model = _FakeModel()
    cases = [
        ("marker_outside_selected_span", "projection_rejected_range"),
        ("multiple_legal_pcomp_children", "projection_rejected_ambiguity"),
        ("no_single_main_action_endpoint", "projection_rejected_syntax"),
    ]
    for reason, expected in cases:
        out = diag.build_sun_order_diagnostic(_record(projection=_projection([reason])), _signal(), model, scorer)
        assert out["category"] == expected


def test_no_relation_without_projection_rejection_is_no_rule_order_relation():
    out = diag.build_sun_order_diagnostic(_record(projection={"clause_audits": []}), _signal(), _FakeModel(), _FakeScorer({}))
    assert out["category"] == "no_rule_order_relation"


def test_endpoint_unmapped_and_similarity_below_gamma_are_distinguished():
    relation = [["missing endpoint", "task two"]]
    out = diag.build_sun_order_diagnostic(_record(relation), _signal(), _FakeModel(), _FakeScorer({"task two": ("task two", 0.9)}))
    assert out["category"] == "endpoint_unmapped"

    relation = [["endpoint low", "task two"]]
    scorer = _FakeScorer({"endpoint low": ("task one", 0.9), "task two": ("task two", 0.7)})
    out = diag.build_sun_order_diagnostic(_record(relation), _signal(), _FakeModel(), scorer)
    assert out["category"] == "endpoint_similarity_below_gamma"


def test_reachability_satisfied_and_violated_are_distinguished():
    relation = [["endpoint one", "endpoint two"]]
    scorer = _FakeScorer({"endpoint one": ("task one", 0.9), "endpoint two": ("task two", 0.9)})
    model = _FakeModel()
    model.reachable = {"T1": {"T2"}}
    out = diag.build_sun_order_diagnostic(_record(relation), _signal(denominator=1, status="satisfied"), model, scorer)
    assert out["category"] == "reachability_satisfied"
    assert out["relation_evidence"][0]["reachability"]["satisfied"] is True

    model.reachable = {"T1": {"T2"}, "T2": {"T1"}}
    out = diag.build_sun_order_diagnostic(_record(relation), _signal(denominator=1, status="violated"), model, scorer)
    assert out["category"] == "reachability_violated"
    assert out["relation_evidence"][0]["reachability"]["satisfied"] is False


def test_failed_rule_record_and_winter_native_no_flow_are_distinguished():
    out = diag.build_sun_order_diagnostic(_record(failed=True), _signal(), _FakeModel(), _FakeScorer({}))
    assert out["category"] == "stage2_rule_record_failed"
    winter = diag.build_winter_order_diagnostic({"denominator": 0, "status": "unknown", "reason": "no_rule_side_flow_relations"})
    assert winter["category"] == "no_rule_order_relation"


def _load_script(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_r2_config_uses_one_strict_projection_for_sun_and_ours():
    cfg = json.loads((ROOT / "configs/stage3_table3_v4_execution_r2.json").read_text(encoding="utf-8"))
    assert cfg["temporal_projection"]["algorithm"] == "sun_stage3_temporal_projection_v3@1.0.0"
    assert cfg["temporal_projection"]["module"].endswith("temporal_projection_v3.py")
    for method in ("sun", "ours"):
        assert cfg["methods"][method]["order_relation_source"] == "temporal_projection_v3_plus_valid_native_edges"
        assert cfg["methods"][method]["order_relation_source"].startswith("temporal_projection_v3")


def test_exact_id_set_validation_rejects_missing_case_and_rule():
    module = _load_script("r2_eval_contract", "scripts/evaluate_stage3_table3_v4_r2.py")
    expected_cases = ["c1"]
    expected_rules = ["r1"]
    predictions = {"records": [
        {"row_method_id": "sun", "case_id": "c1", "signals_by_rule": {"r1": {}}},
        {"row_method_id": "ours", "case_id": "c1", "signals_by_rule": {"r1": {}}},
    ]}
    manifest = {"actual_output_case_ids": ["c1"], "actual_output_rule_ids": ["r1"]}
    out = module._validate_exact_id_sets(predictions, manifest, expected_cases, expected_rules)
    assert out["case_ids"] == ["c1"]
    with pytest.raises(RuntimeError, match="case-id set"):
        module._validate_exact_id_sets({"records": [
            {"row_method_id": "sun", "case_id": "c2", "signals_by_rule": {"r1": {}}},
        ]}, manifest, expected_cases, expected_rules)
    with pytest.raises(RuntimeError, match="rule-id set"):
        module._validate_exact_id_sets({"records": [
            {"row_method_id": "sun", "case_id": "c1", "signals_by_rule": {"r2": {}}},
        ]}, manifest, expected_cases, expected_rules)


def test_output_binding_postprocess_recomputes_hashes_and_ids(tmp_path):
    module = _load_script("r2_runner_contract", "scripts/run_stage3_table3_v4_r2.py")
    out = tmp_path / "out"
    out.mkdir()
    predictions = {
        "records": [
            {"row_method_id": "sun", "case_id": "c1", "signals_by_rule": {"r1": {"out_of_order": {"order_diagnostic": {"category": "no_rule_order_relation"}, "reason": "no_rule_order_relation"}}}},
        ]
    }
    (out / "predictions.json").write_text(json.dumps(predictions), encoding="utf-8")
    (out / "signals_matrix.json").write_text(json.dumps({"signals": [
        {"method": "sun", "case_id": "c1", "rule_id": "r1", "check_type": "out_of_order", "reason": "no_rule_order_relation"}
    ]}), encoding="utf-8")
    (out / "rule_records.json").write_text(json.dumps({"sun": {"records": {}}}), encoding="utf-8")
    (out / "global_role_candidates.json").write_text(json.dumps({"roles": []}), encoding="utf-8")
    manifest = module._postprocess_outputs(out, {"run_id": "old"})
    assert manifest["run_id"] == "stage3_table3_v4_r2"
    assert manifest["actual_output_case_ids"] == ["c1"]
    assert manifest["actual_output_rule_ids"] == ["r1"]
    for binding in manifest["outputs"].values():
        assert len(binding["sha256"]) == 64
        bound = Path(binding["path"])
        if not bound.is_absolute():
            bound = ROOT / bound
        assert bound.is_file()
    signals = json.loads((out / "signals_matrix.json").read_text(encoding="utf-8"))
    assert signals["signals"][0]["order_diagnostic"]["category"] == "no_rule_order_relation"


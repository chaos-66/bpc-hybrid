# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complex_input_is_exactly_36_and_gold_blind() -> None:
    path = ROOT / "data/input/s2_12_complex_corpus_formal_input_v1.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "configs/schemas/s2_12_complex_corpus_input_v1.schema.json").read_text(encoding="utf-8"))
    assert set(schema["required"]).issubset(doc)
    assert doc["record_count"] == len(doc["records"]) == 36
    assert doc["gold_blind"] is True
    assert {tuple(row) for row in doc["records"]} == {("sample_id", "source")}
    serialized = json.dumps(doc["records"]).lower()
    assert all(term not in serialized for term in ('"clauses"', '"modality"', '"decisions"', '"gold"'))


def test_zero_api_predictions_are_locked_and_text_free() -> None:
    doc = json.loads((ROOT / "data/predictions/s2_12_sun_rule_only_v1/predictions.json").read_text(encoding="utf-8"))
    assert doc["record_count"] == len(doc["records"]) == 36
    assert doc["gold_read_by_runner"] is False
    assert doc["raw_text_committed"] is False
    serialized = json.dumps(doc).lower()
    assert all(term not in serialized for term in ('"source_text"', '"text"', '"normalized"', '"marker_surface"'))


def test_zero_api_evaluation_scope_and_strata() -> None:
    report = json.loads((ROOT / "data/results/s2_12_sun_rule_only_v1/evaluation.json").read_text(encoding="utf-8"))
    assert report["metrics"]["overall"]["samples"] == 36
    assert [report["metrics"]["strata"][level]["samples"] for level in ("L1", "L2", "L3")] == [31, 5, 0]
    assert report["metrics"]["strata"]["L3"]["span_fields"] is None
    assert "no samples" in report["metrics"]["strata"]["L3"]["note"]
    assert report["scope_boundary"]["single_zero_api_arm_only"] is True
    assert report["scope_boundary"]["post_result_tuning_performed"] is False


def test_zero_api_independent_verifier_passes() -> None:
    verifier = _load("s212_zero_verify", "scripts/verify_s2_12_sun_rule_only_v1.py")
    result = verifier.verify()
    assert result["verified"], [item for item in result["checks"] if not item["ok"]]


def test_api_preflight_schema_and_zero_call_state() -> None:
    report = json.loads((ROOT / "outputs/reports/s2_12_api_preflight_v1.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "configs/schemas/s2_12_api_preflight_v1.schema.json").read_text(encoding="utf-8"))
    assert set(report) == set(schema["required"])
    assert report["global"]["planned_calls"] == 63
    assert report["arms"]["direct_llm"]["planned_calls"] == 36
    assert report["arms"]["sun_llm_fallback"]["planned_calls"] == 27
    assert report["safety"]["llm_api_calls"] == 0
    assert report["authorization"]["real_api_calls_authorized"] is False


def test_api_preflight_exact_size_and_proxy_counts() -> None:
    report = json.loads((ROOT / "outputs/reports/s2_12_api_preflight_v1.json").read_text(encoding="utf-8"))
    assert report["global"]["request_body_utf8_bytes"] == {
        "maximum_per_call": 17493, "total": 749805}
    assert report["global"]["local_proxy_tokens"] == {
        "maximum_per_call": 4960, "total": 207468}
    assert report["token_measurement"]["official_billing_input_tokens"] is None
    assert report["token_measurement"]["local_proxy"]["is_billing_token_count"] is False


def test_api_preflight_independent_verifier_passes() -> None:
    verifier = _load("s212_api_verify", "scripts/verify_s2_12_api_preflight_v1.py")
    result = verifier.verify()
    assert result["verified"], [item for item in result["checks"] if not item["ok"]]


def test_api_lock_has_zero_retries_and_no_authorization() -> None:
    lock = json.loads((ROOT / "configs/s2_12_api_arms_preflight_v1.json").read_text(encoding="utf-8"))
    assert lock["global_caps"] == {"max_calls": 108, "max_output_tokens": 442368, "retry_count": 0}
    assert lock["authorization"]["real_api_calls_allowed_by_this_lock"] is False
    assert lock["gold_isolation"]["preflight_reads_gold"] is False


def test_preflight_summary_helper() -> None:
    builder = _load("s212_api_builder", "scripts/build_s2_12_api_preflight_v1.py")
    assert builder._summary([4, 1, 7]) == {"minimum": 1, "maximum": 7, "total": 12}
    assert builder._summary([]) == {"minimum": 0, "maximum": 0, "total": 0}


def test_file_catalog_excludes_local_audit_backups() -> None:
    catalog = _load("catalog_builder", "scripts/generate_file_catalog.py")
    files = catalog.collect_files()
    assert files
    assert not any(path.suffix.lower() == ".bak" for path in files)

"""Focused tests for the G0.4 coarse view + B0 formal arm evaluation.

Covers:
- the derived coarse view's five span-bearing fields match the historical
  sentence-level coarse gold record-for-record (modality evidence is the
  only known difference, reported as unavailable)
- formal evaluation: modality evidence-span unavailable, modality-label
  metrics separate, timing stripped from canonical artifacts
- B0 formal arm preconditions fail closed (method gate not ready -> raise)
- audit method-coverage distinction (partial vs complete vs not produced)
"""

from __future__ import annotations

import importlib.util
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

from bpc_hybrid.g04_coarse_view import (  # noqa: E402
    HISTORICAL_COARSE_SEMANTIC_SHA,
    build_coarse_view,
    semantic_hash_json,
)
from bpc_hybrid.formal_stage2_evaluation import (  # noqa: E402
    evaluate_modality_labels,
    evaluate_span_metrics,
    predictions_to_evaluator,
    published_gold_to_evaluator,
    strip_timing,
    telemetry_only,
)

GOLD = json.loads(
    (ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json")
    .read_text(encoding="utf-8"))
HISTORICAL_COARSE = json.loads(
    (ROOT / "outputs" / "development"
     / "s27_b0_coarse_gold_sentence_granularity_v1"
     / "coarse_gold_sentence_level.json").read_text(encoding="utf-8"))


def _sample_attempts() -> list[dict]:
    """Small synthetic attempts envelope (2 rows) for module-level tests."""
    return [
        {"sample_id": "estg_000002", "request_status": "ok",
         "record": {"clauses": [{"modality": {"label": "obligation",
                                              "evidence": [{"start": 0, "end": 4}]},
                                 "actors": [{"start": 0, "end": 8}],
                                 "actions": [{"start": 9, "end": 18}],
                                 "conditions": [], "constraints": [],
                                 "exceptions": []}]},
         "error_category": None,
         "runtime": {"llm_call_performed": False, "latency_ms": 123.0,
                     "total_tokens": 0}},
        {"sample_id": "estg_000003", "request_status": "ok",
         "record": {"clauses": [{"modality": {"label": "permission",
                                              "evidence": [{"start": 0, "end": 3}]},
                                 "actors": [{"start": 0, "end": 6}],
                                 "actions": [{"start": 7, "end": 15}],
                                 "conditions": [], "constraints": [],
                                 "exceptions": []}]},
         "error_category": None,
         "runtime": {"llm_call_performed": False, "latency_ms": 80.0,
                     "total_tokens": 0}},
    ]


# --------------------------------------------------------------------------- G0.4 coarse view


def test_coarse_view_five_fields_match_historical() -> None:
    derived = build_coarse_view(GOLD)
    h_by_id = {r["sample_id"]: r for r in HISTORICAL_COARSE}
    mismatch = 0
    for rec in derived:
        h = h_by_id[rec["sample_id"]]
        hc = h["clauses"][0]
        dc = rec["clauses"][0]
        for plural in ("actors", "actions", "conditions", "constraints",
                       "exceptions"):
            if hc.get(plural) != dc.get(plural):
                mismatch += 1
        if h.get("source_text") != rec.get("source_text"):
            mismatch += 1
        if h.get("source_id") != rec.get("source_id"):
            mismatch += 1
        if hc.get("clause_span") != dc.get("clause_span"):
            mismatch += 1
    assert mismatch == 0


def test_coarse_view_modality_evidence_difference_is_reported() -> None:
    derived = build_coarse_view(GOLD)
    semantic_sha = semantic_hash_json(derived)
    # the derived view must NOT silently claim the historical semantic hash
    assert semantic_sha != HISTORICAL_COARSE_SEMANTIC_SHA
    # and the only field difference is modality evidence
    field_diff = 0
    for rec in derived:
        h = {r["sample_id"]: r for r in HISTORICAL_COARSE}[rec["sample_id"]]
        if h["clauses"][0].get("modality") != rec["clauses"][0].get("modality"):
            field_diff += 1
    assert field_diff > 0
    # modality evidence in the derived view is the merged clause span (no
    # local evidence in the published Gold), which is the documented reason
    mod = derived[0]["clauses"][0]["modality"]
    assert mod["label"] in ("obligation", "permission", "prohibition",
                            "definition")


# --------------------------------------------------------------------------- formal evaluation


def test_published_gold_conversion_and_modality_unavailable() -> None:
    fine = published_gold_to_evaluator(GOLD)
    assert len(fine) == 150
    clause = fine[0]["clauses"][0]
    assert clause["modality"]["label"] in (
        "obligation", "permission", "prohibition", "definition")
    assert clause["modality"]["evidence"] == []


def test_span_metrics_five_fields_and_modality_unavailable() -> None:
    fine = published_gold_to_evaluator(GOLD)
    attempts = predictions_to_evaluator(_sample_attempts())
    # attempts must match gold membership; use full real attempts instead
    real = json.loads((ROOT / "outputs" / "development"
                       / "b0_r4_formal_candidate_v1" / "b0_attempts.json")
                      .read_text(encoding="utf-8"))["records"]
    if len(real) != 150:
        pytest.skip("candidate attempts unavailable")
    metrics = evaluate_span_metrics(
        fine, real, dataset_id="independently_reconstructed_estg_150_v1",
        method_id="sun_rule_only", view="fine")
    assert set(metrics["span_fields"]) == {
        "actor", "action", "condition", "constraint", "exception"}
    assert metrics["modality_span"]["available"] is False
    assert "plain string" in metrics["modality_span"]["reason"]
    assert metrics["no_cross_view_mixing"] is True
    assert all(0.0 <= v["f1"] <= 1.0 for v in metrics["span_fields"].values())


def test_coarse_span_metrics_match_historical_per_field() -> None:
    """The coarse-view five-field metrics computed from the published Gold
    must match the historical coarse per-field numbers (2026-08-07)."""
    coarse = build_coarse_view(GOLD)
    real = json.loads((ROOT / "outputs" / "development"
                       / "b0_r4_formal_candidate_v1" / "b0_attempts.json")
                      .read_text(encoding="utf-8"))["records"]
    if len(real) != 150:
        pytest.skip("candidate attempts unavailable")
    metrics = evaluate_span_metrics(
        coarse, real, dataset_id="independently_reconstructed_estg_150_v1",
        method_id="sun_rule_only", view="coarse")
    expected = {"actor": 0.8203, "action": 0.8927, "condition": 0.7738,
                "constraint": 0.6182, "exception": 0.8800}
    for field, want in expected.items():
        got = round(metrics["span_fields"][field]["f1"], 4)
        assert abs(got - want) < 0.0002, f"{field}: {got} vs {want}"


def test_modality_labels_separate() -> None:
    fine = published_gold_to_evaluator(GOLD)
    real = json.loads((ROOT / "outputs" / "development"
                       / "b0_r4_formal_candidate_v1" / "b0_attempts.json")
                      .read_text(encoding="utf-8"))["records"]
    if len(real) != 150:
        pytest.skip("candidate attempts unavailable")
    result = evaluate_modality_labels(fine, real)
    assert result["separate_from_span_metrics"] is True
    assert 0.0 <= result["accuracy"] <= 1.0
    assert result["records"] == 150
    assert len(result["per_class"]) == 4


def test_strip_timing_isolates_telemetry() -> None:
    attempts = _sample_attempts()
    stripped = strip_timing(attempts)
    for rec in stripped:
        assert "runtime" not in rec
        assert "latency" not in json.dumps(rec)
    telemetry = telemetry_only(attempts)
    assert telemetry["latency_ms_total"] == pytest.approx(203.0)
    assert telemetry["llm_call_performed_any"] is False


# --------------------------------------------------------------------------- formal arm preconditions


def test_formal_arm_preconditions_fail_closed(monkeypatch) -> None:
    spec = importlib.util.spec_from_file_location(
        "b0fa_test", ROOT / "scripts" / "run_b0_formal_arm.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["b0fa_test"] = m
    spec.loader.exec_module(m)
    # break the method gate: sun_rule_only not ready
    methods = {"methods": [
        {"id": "sun_rule_only", "formal_status": "blocked",
         "command_status": "development_only_not_formal", "llm_used": False},
        {"id": "direct_llm", "formal_status": "blocked", "llm_used": True},
        {"id": "sun_llm_fallback", "formal_status": "blocked", "llm_used": True},
    ]}
    tmp = Path(__import__("tempfile").mkdtemp())
    methods_path = tmp / "methods.json"
    methods_path.write_text(json.dumps(methods), encoding="utf-8")
    monkeypatch.setattr(m, "METHODS_CONFIG", methods_path)
    with pytest.raises(Exception, match="sun_rule_only_formal_status_ready"):
        m.check_preconditions()


# --------------------------------------------------------------------------- audit method coverage


def test_audit_capsule_method_coverage(tmp_path: Path, monkeypatch) -> None:
    """A single arm in data/predictions must produce the PARTIAL warning,
    never silence the three-method capsule check."""
    from formal_experiment import audit as audit_mod
    pred_dir = tmp_path / "predictions"
    (pred_dir / "b0_formal_arm_v1").mkdir(parents=True)
    res_dir = tmp_path / "results"
    (res_dir / "b0_formal_arm_v1").mkdir(parents=True)
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "b0_formal_arm_v1.manifest.json").write_text(
        json.dumps({"method_id": "sun_rule_only"}), encoding="utf-8")
    monkeypatch.setattr(audit_mod, "FORMAL_PREDICTIONS_DIR", pred_dir)
    monkeypatch.setattr(audit_mod, "FORMAL_RESULTS_DIR", res_dir)
    monkeypatch.setattr(audit_mod, "FORMAL_REPORTS_DIR", reports)
    methods = audit_mod._formal_capsule_methods()
    assert methods == {"sun_rule_only"}
    assert methods != {"sun_rule_only", "sun_llm_fallback", "direct_llm"}


def test_audit_capsule_coverage_empty() -> None:
    from formal_experiment import audit as audit_mod
    assert audit_mod._formal_capsule_methods() != {
        "sun_rule_only", "sun_llm_fallback", "direct_llm"}


def test_audit_current_state_partial_or_not_produced() -> None:
    """Current real state: either no capsule (warning not_produced) or only
    the B0 arm (warning partial); never the complete pass."""
    from formal_experiment.audit import collect_project_audit
    audit = collect_project_audit()
    warnings = {item["code"] for item in audit["findings"]["warnings"]}
    passes = {item["code"] for item in audit["findings"]["passes"]}
    assert "formal_predictions_results_capsule_complete" not in passes
    assert ("formal_predictions_results_capsule_not_produced" in warnings
            or "formal_predictions_results_capsule_partial" in warnings)


def test_b0_formal_arm_verifier_tamper_fail_closed() -> None:
    """The generated B0 formal arm verifier must fail on tampering and pass
    on the intact capsule (test restores the file afterwards)."""
    import subprocess
    pred = (ROOT / "data" / "predictions" / "b0_formal_arm_v1"
            / "predictions.json")
    verifier = (ROOT / "outputs" / "reports"
                / "verify_b0_formal_arm_v1.py")
    if not pred.exists() or not verifier.exists():
        pytest.skip("B0 formal arm capsule not published yet")
    orig = pred.read_bytes()
    try:
        pred.write_bytes(orig.replace(b'"records"', b'"records" '))
        r = subprocess.run([sys.executable, str(verifier)],
                           capture_output=True, text=True)
        assert r.returncode != 0, "verifier must fail on tampered capsule"
    finally:
        pred.write_bytes(orig)
    r2 = subprocess.run([sys.executable, str(verifier)],
                        capture_output=True, text=True)
    assert r2.returncode == 0, "verifier must pass on the intact capsule"


def test_b0_formal_arm_capsule_published_and_semantics() -> None:
    """Published B0 formal arm capsule: claim_scope=formal, timing-free
    canonical predictions, five-field metrics, modality-label table."""
    manifest_path = (ROOT / "outputs" / "reports"
                     / "b0_formal_arm_v1.manifest.json")
    if not manifest_path.exists():
        pytest.skip("B0 formal arm capsule not published yet")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["claim_scope"] == "formal"
    assert manifest["is_formal_performance_result"] is True
    assert manifest["arm_scope"]["final_experiment_ready"] is False
    assert manifest["safety"]["gold_read_by_runner"] is False
    assert manifest["safety"]["llm_api_called"] is False
    pred = json.loads((ROOT / "data" / "predictions" / "b0_formal_arm_v1"
                       / "predictions.json").read_text(encoding="utf-8"))
    assert len(pred["records"]) == 150
    assert all("runtime" not in r and "latency" not in json.dumps(r)
               for r in pred["records"])

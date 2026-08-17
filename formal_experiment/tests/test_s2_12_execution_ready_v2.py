"""Focused tests for S2.12 execution-ready v2 (Checkpoint E3; zero API).

Covers:
  * stratified evaluator v2: per-stratum span P/R/F1 + modality label
    metrics; L3 with zero samples reported with no performance
    conclusion; fail-closed on sample/level mismatch
  * PARITY: the same synthetic fixture through the FORMAL Stage 2
    evaluator and the stratified v2 wrapper yields identical overall
    span + modality-label metrics
  * method adapter: canonical envelopes accepted; the v1 flat
    {field: string} shape refused; unknown method refused
  * plan/readiness/API v2: frozen plan supersedes v1, readiness claims
    only schema/importer/evaluator/adapter readiness, API readiness
    exact model ids (deepseek-v4-pro both arms), call bounds 36/72/108,
    output cap 4096, input cap unresolved, cost_cap_unresolved, NO final
    authorization sentence
  * independent verifier v2 passes on the committed assets and fails
    closed on tampered copies
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from bpc_hybrid.s2_12_method_adapter import (
    AdapterFail,
    adapt_method_attempts,
)
from bpc_hybrid.s2_12_stratified_evaluator_v2 import (
    EvaluatorFail,
    evaluate_stratified,
)
import s2_12_build_execution_ready_v2 as builder
import verify_s2_12_execution_ready_v2 as verifier

ROOT = Path(__file__).resolve().parents[1]

MEMBERSHIP_REL = "outputs/reports/s2_11_corpus_membership_v1.json"
PLAN_CONFIG_V2_REL = "configs/s2_12_execution_plan_v2.json"
PLAN_REPORT_V2_REL = "outputs/reports/s2_12_execution_plan_v2.json"
READINESS_V2_REL = "outputs/reports/s2_12_execution_readiness_v2.json"
API_READINESS_V2_REL = "outputs/reports/s2_12_api_readiness_v2.json"


def _load(rel: str) -> dict[str, Any]:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture(scope="module")
def fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]],
                       dict[str, str]]:
    return builder._parity_fixture()


# ---------------------------------------------------------------------------
# Stratified evaluator v2 + parity
# ---------------------------------------------------------------------------
def test_evaluator_v2_strata_and_l3_no_samples(
        fixture: Any) -> None:
    gold, attempts, levels = fixture
    result = evaluate_stratified(gold, attempts, levels=levels,
                                 dataset_id="parity_fixture",
                                 method_id="sun_rule_only")
    assert result["schema_version"] == "s2_12_stratified_evaluator@2.0.0"
    assert result["strata"]["L1"]["samples"] == 2
    assert result["strata"]["L2"]["samples"] == 2
    l3 = result["strata"]["L3"]
    assert l3["samples"] == 0
    assert l3["span_fields"] is None
    assert l3["modality_labels"] is None
    assert "no samples" in l3["note"]
    # overall aggregation present
    assert result["overall"]["samples"] == 4
    assert result["zero_api"] == {"new_llm_api_calls": 0}


def test_evaluator_v2_fail_closed_sample_mismatch(
        fixture: Any) -> None:
    gold, attempts, levels = fixture
    with pytest.raises(EvaluatorFail, match="sample mismatch"):
        evaluate_stratified(gold, attempts[:3], levels=levels,
                            dataset_id="x", method_id="sun_rule_only")


def test_evaluator_v2_fail_closed_bad_level(fixture: Any) -> None:
    gold, attempts, levels = fixture
    bad = dict(levels)
    bad["synth/01"] = "L9"
    with pytest.raises(EvaluatorFail, match="bad level"):
        evaluate_stratified(gold, attempts, levels=bad,
                            dataset_id="x", method_id="sun_rule_only")


def test_parity_formal_vs_stratified_v2(fixture: Any) -> None:
    """The unstratified overall of the stratified v2 wrapper must equal
    the FORMAL Stage 2 evaluator on the same fixture."""
    from bpc_hybrid import formal_stage2_evaluation as formal
    gold, attempts, levels = fixture
    formal_span = formal.evaluate_span_metrics(
        gold, attempts, dataset_id="parity_fixture",
        method_id="sun_rule_only", view="coarse")
    formal_mod = formal.evaluate_modality_labels(gold, attempts)
    stratified = evaluate_stratified(gold, attempts, levels=levels,
                                     dataset_id="parity_fixture",
                                     method_id="sun_rule_only")
    overall_span = stratified["overall"]["span_fields"]
    overall_mod = stratified["overall"]["modality_labels"]
    for field in ("actor", "action", "condition", "constraint",
                  "exception"):
        fs = formal_span["span_fields"][field]
        ss = overall_span["span_fields"][field]
        assert fs["precision"] == ss["precision"], field
        assert fs["recall"] == ss["recall"], field
        assert fs["f1"] == ss["f1"], field
    assert formal_mod["accuracy"] == overall_mod["accuracy"]
    assert formal_mod["macro_f1"] == overall_mod["macro_f1"]
    assert formal_mod["per_class"] == overall_mod["per_class"]
    # and the fixture itself produces a non-trivial measurement
    assert formal_span["span_fields"]["action"]["recall"] < 1.0
    assert formal_span["span_fields"]["action"]["precision"] < 1.0


def test_parity_check_builder_embeds_passed(fixture: Any) -> None:
    parity = builder._parity_check()
    assert parity["passed"] is True
    assert parity["span_metrics_equal"] is True
    assert parity["modality_metrics_equal"] is True
    assert parity["l3_no_samples"] is True


# ---------------------------------------------------------------------------
# Method adapter
# ---------------------------------------------------------------------------
def test_method_adapter_accepts_canonical_envelope(fixture: Any) -> None:
    gold, attempts, _ = fixture
    adapted = adapt_method_attempts(attempts, "sun_llm_fallback")
    assert len(adapted) == 4
    for a in adapted:
        assert a["request_status"] == "success"
        assert a["record"]["clauses"][0]["modality"]["label"] is not None


def test_method_adapter_refuses_flat_shape() -> None:
    flat = [{"sample_id": "x/1", "request_status": "success",
             "record": {"sample_id": "x/1",
                        "clauses": [{"modality": {"label": "obligation"},
                                     "actor": {"spans": []}}]}}]
    # missing condition/constraint/exception span arrays -> refused
    with pytest.raises(AdapterFail, match="span array"):
        adapt_method_attempts(flat, "direct_llm")


def test_method_adapter_refuses_unknown_method() -> None:
    with pytest.raises(AdapterFail, match="unknown method_id"):
        adapt_method_attempts([], "production_typo")


def test_method_adapter_refuses_v1_flat_string_shape() -> None:
    v1_shape = [{"sample_id": "x/1", "request_status": "success",
                 "record": {"sample_id": "x/1",
                            "clauses": [{"modality": "obligation",
                                         "actor": {"spans": []},
                                         "action": {"spans": []},
                                         "condition": {"spans": []},
                                         "constraint": {"spans": []},
                                         "exception": {"spans": []}}]}}]
    with pytest.raises(AdapterFail, match="modality"):
        adapt_method_attempts(v1_shape, "direct_llm")


# ---------------------------------------------------------------------------
# Plan / readiness / API v2
# ---------------------------------------------------------------------------
def test_plan_v2_frozen_supersedes_v1() -> None:
    plan = _load(PLAN_CONFIG_V2_REL)
    plan_report = _load(PLAN_REPORT_V2_REL)
    assert plan["status"] == "frozen"
    assert plan["preregistration"]["declared_before_results"] is True
    assert sum(plan["preregistration"]["strata_level_counts"].values()) == 36
    assert "evaluator" in plan["supersedes_v1"]["reason"]
    assert "Gold shape" in plan["supersedes_v1"]["reason"]
    assert plan_report["importer_v2_dry_run"] == {
        "samples": 36, "blocked_fields": 0, "blocked_samples": 0,
        "unresolved_fields": 0, "adjudicable": 36}
    assert plan["gold"]["gold_files_created"] is False
    assert plan["zero_api"] == {"new_llm_api_calls": 0}


def test_readiness_v2_claims_only_readiness() -> None:
    readiness = _load(READINESS_V2_REL)
    assert readiness["status"] == "ready_for_execution_pending_user_gates"
    claims = readiness["ready_claims"]
    assert claims["schema_ready"] is True
    assert claims["importer_ready"]["blocked_fields"] == 0
    assert claims["evaluator_ready"]["parity"]["passed"] is True
    assert claims["method_adapter_dry_run_ready"] is True
    assert claims["gold_or_formal_evaluation_complete"] is False
    assert readiness["runner"]["real_run_refused"] is True
    assert readiness["gates"]["s2_11_freeze_v2"]["adjudicated"] == 0
    assert readiness["gates"]["api_budget_authorization"]["ready"] is False
    assert readiness["gold_created"] is False


def test_api_readiness_v2_precise_derivation() -> None:
    api = _load(API_READINESS_V2_REL)
    assert api["arms"]["direct_llm"]["model_id"] == "deepseek-v4-pro"
    assert api["arms"]["sun_llm_fallback"]["model_id"] == "deepseek-v4-pro"
    assert api["arms"]["direct_llm"]["max_calls"] == 36
    assert api["arms"]["sun_llm_fallback"]["max_calls"] == 72
    assert api["totals"]["max_calls"] == 108
    assert api["arms"]["direct_llm"]["output_token_cap"] == 4096
    assert api["totals"]["output_side_total_token_bound"] == 442368
    assert api["totals"]["input_side_total_token_bound"] == "unresolved"
    assert api["totals"]["cost_cap"] == "cost_cap_unresolved"
    assert api["final_copyable_authorization_sentence"] is None
    missing = " ".join(api["missing_items_for_final_authorization"])
    assert "input_token_cap" in missing and "cost_cap" in missing
    assert api["calls_made"] == 0
    assert api["authorized"] is False
    assert api["zero_api"] == {"new_llm_api_calls": 0}


def test_builder_v2_deterministic() -> None:
    first = json.dumps(builder.build(), sort_keys=True, ensure_ascii=False)
    second = json.dumps(builder.build(), sort_keys=True, ensure_ascii=False)
    assert first == second


def test_committed_v2_assets_match_builder() -> None:
    plan_config, plan_report, readiness, api = builder.build()
    assert plan_config == _load(PLAN_CONFIG_V2_REL)
    assert plan_report == _load(PLAN_REPORT_V2_REL)
    assert readiness == _load(READINESS_V2_REL)
    assert api == _load(API_READINESS_V2_REL)


# ---------------------------------------------------------------------------
# Verifier v2
# ---------------------------------------------------------------------------
VERIFIER_INPUTS = [
    MEMBERSHIP_REL,
    "configs/g05_complexity_frozen_v1.json",
    "configs/g05_complexity_candidate_draft_v1.json",
    "configs/g05_authorization_manifest_v1.json",
    "data/development/human_review/s2_11_review_decisions_v2.json",
    "outputs/reports/s2_11_proposal_report_v2.json",
    "outputs/reports/s2_11_batch_import_dry_run_v2.json",
    "configs/stage2_evaluator_s210_v3.json",
    "configs/models/estg150_d1_active_registry_v1.json",
    "outputs/development/s28d_h1_150_v4pro_v1/manifest.json",
    "configs/s2_12_execution_plan_v1.json",
    "outputs/reports/s2_12_execution_plan_v1.json",
    "outputs/reports/s2_12_execution_readiness_v1.json",
    PLAN_CONFIG_V2_REL,
    PLAN_REPORT_V2_REL,
    READINESS_V2_REL,
    API_READINESS_V2_REL,
]


@pytest.fixture()
def verifier_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "formal_experiment"
    for rel in VERIFIER_INPUTS:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, target)
    monkeypatch.setattr(verifier, "ROOT", root)
    yield root


def test_verifier_v2_passes_on_committed_assets() -> None:
    result = verifier.verify()
    assert result["verified"] is True, \
        "; ".join(c["name"] for c in result["checks"] if not c["ok"])


def test_verifier_v2_fails_on_tampered_plan_status(
        verifier_tmp: Path) -> None:
    p = verifier_tmp / PLAN_CONFIG_V2_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["status"] = "unfrozen"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False


def test_verifier_v2_fails_on_forged_cost_cap(
        verifier_tmp: Path) -> None:
    p = verifier_tmp / API_READINESS_V2_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["totals"]["cost_cap"] = "0.001 USD/token"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False
    assert any("token/cost honest" in c["name"] for c in result["checks"]
               if not c["ok"])


def test_verifier_v2_fails_on_final_sentence_injected(
        verifier_tmp: Path) -> None:
    p = verifier_tmp / API_READINESS_V2_REL
    doc = json.loads(p.read_text(encoding="utf-8"))
    doc["final_copyable_authorization_sentence"] = "I authorize 100 calls"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    result = verifier.verify()
    assert result["verified"] is False

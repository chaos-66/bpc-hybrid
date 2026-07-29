"""Regression tests for the frozen S2.10-E Stage 2 evaluator."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage2_evaluation import (  # noqa: E402
    Stage2EvaluationError,
    _hybrid_pairs,
    build_style_review_template,
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    normalize_span_text,
    validate_evaluation_report,
    validate_style_review_document,
)
from formal_experiment.s2_10_evaluator_gate import (  # noqa: E402
    S210_EXPECTATIONS,
    verify_s2_10_evaluator_gate,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


CONTRACT_PATH = ROOT / "configs" / "stage2_evaluator_s210.json"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "stage2_evaluator" / "s210_contract_fixture.json"
EXPECTED_MEMBERSHIP = "f74be514b6ffed61cb196feb730ec6db29ca0c8e2ffd6a00cf248a6187e5af47"


def _contract() -> dict:
    return load_evaluator_contract(CONTRACT_PATH)


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _report(fixture: dict | None = None) -> dict:
    fixture = fixture or _fixture()
    return evaluate_stage2(
        fixture["gold_records"],
        fixture["attempts"],
        contract=_contract(),
        dataset_id=fixture["dataset_id"],
        method_id=fixture["method_id"],
        expected_membership_sha256=EXPECTED_MEMBERSHIP,
    )


def test_s210_fixture_membership_and_report_contract_are_exact() -> None:
    fixture = _fixture()
    assert membership_sha256(fixture["gold_records"]) == EXPECTED_MEMBERSHIP
    report = _report(fixture)
    assert validate_evaluation_report(report) == []
    assert report["membership"] == {
        "sample_count": 5,
        "payload_sha256": EXPECTED_MEMBERSHIP,
        "gold_attempt_ids_exact_match": True,
    }
    assert report["safety"]["row_level_predictions_persisted_in_report"] is False
    assert "source_text" not in report
    assert "predictions" not in report


def test_modality_is_clause_level_four_class_with_missing_class_na() -> None:
    metric = _report()["primary_metrics"]["modality"]
    assert metric["unit"] == "clause"
    assert metric["labels"] == ["obligation", "prohibition", "permission", "definition"]
    assert metric["macro_f1"] == pytest.approx(5 / 12)
    assert metric["per_class"]["prohibition"]["precision"] is None
    assert metric["per_class"]["prohibition"]["precision_display"] == "N/A"
    assert metric["per_class"]["prohibition"]["support"] == 1
    assert metric["confusion_matrix"]["permission"]["obligation"] == 1


def test_strict_safe_and_token_metrics_remain_separate() -> None:
    action = _report()["primary_metrics"]["fields"]["action"]
    assert action["strict_exact"]["f1"] == 0.25
    assert action["safe_normalized"]["f1"] == 0.5
    assert action["normalized_f1_lift"] == 0.25
    assert action["token_overlap_micro"]["f1"] == 0.5
    assert action["token_overlap_macro"]["evaluated_sample_count"] == 5


def test_safe_normalization_does_not_remove_articles_or_lemma_or_plural() -> None:
    contract = _contract()
    assert normalize_span_text("The Controllers.", profile="safe", contract=contract) == "the controllers"
    assert normalize_span_text("deletes", profile="safe", contract=contract) != "delete"
    assert normalize_span_text("the file", profile="safe", contract=contract) != "file"
    assert contract["normalization"]["disabled_high_risk_rules"] == [
        "article_removal",
        "plural_collapse",
        "verb_lemmatization",
        "abbreviation_expansion",
        "synonym_replacement",
        "number_or_unit_conversion",
    ]


def test_alignment_is_id_then_exact_span_not_array_position() -> None:
    gold = [
        {"id": "g1", "text": "alpha", "start": 0, "end": 5},
        {"id": "g2", "text": "beta", "start": 6, "end": 10},
    ]
    predicted = [
        {"id": "g2", "text": "beta", "start": 6, "end": 10},
        {"id": "new", "text": "alpha", "start": 0, "end": 5},
    ]
    pairs, gold_left, pred_left = _hybrid_pairs(gold, predicted)
    assert pairs == [(0, 1), (1, 0)]
    assert gold_left == []
    assert pred_left == []


def test_coverage_hallucination_invalid_and_api_denominators_are_explicit() -> None:
    coverage = _report()["semantic_coverage"]
    assert coverage["gold_required_count"] == 14
    assert coverage["predicted_count"] == 9
    assert coverage["matched_presence_count"] == 7
    assert coverage["gold_required_presence_recall"] == 0.5
    assert coverage["predicted_field_precision"] == pytest.approx(7 / 9)
    assert coverage["hallucinated_field_rate"] == pytest.approx(2 / 9)
    assert coverage["complete_record_rate"] == 0.4
    assert coverage["schema_valid_rate"] == 0.6
    assert coverage["invalid_record_rate"] == 0.2
    assert coverage["api_error_rate"] == 0.2
    assert coverage["recovered_api_error_rate"] == 0.2
    assert coverage["any_api_error_rate"] == 0.4
    assert coverage["invalid_or_api_error_rate"] == 0.4


def test_recovered_runtime_error_requires_scorable_llm_fallback() -> None:
    fixture = _fixture()
    recovered = fixture["attempts"][1]
    assert recovered["recovered_runtime_error_category"] == "timeout"
    report = _report(fixture)
    assert report["error_accounting"]["counts"]["recovered_api_error:timeout"] == 1

    invalid = copy.deepcopy(fixture)
    invalid["attempts"][1]["runtime"]["llm_call_performed"] = False
    with pytest.raises(Stage2EvaluationError, match="invalid recovered runtime error"):
        _report(invalid)


def test_structural_edges_report_prf_and_jaccard_not_accuracy() -> None:
    structural = _report()["structural_encoding"]
    actor_action = structural["actor_action_edges"]
    assert actor_action["tp"] == 2
    assert actor_action["fp"] == 1
    assert actor_action["fn"] == 3
    assert actor_action["f1"] == 0.5
    assert actor_action["jaccard_iou"] == pytest.approx(1 / 3)
    assert "accuracy" not in actor_action
    assert structural["order_relation_edges"]["fn"] == 1
    assert structural["clause_segmentation"]["exact_recall"] == 0.6


def test_cost_accounting_keeps_failed_and_invalid_requests() -> None:
    assert _report()["cost_accounting"] == {
        "request_count": 5,
        "llm_call_count": 3,
        "prompt_tokens": 190,
        "completion_tokens": 36,
        "total_tokens": 226,
        "estimated_cost_usd": 0.0036,
        "latency_ms_total": 5227.0,
        "latency_ms_mean_per_request": 1045.4,
    }


def test_input_array_order_does_not_change_report() -> None:
    fixture = _fixture()
    expected = _report(fixture)
    fixture["gold_records"].reverse()
    fixture["attempts"].reverse()
    assert _report(fixture) == expected


def test_missing_extra_or_duplicate_attempts_fail_closed() -> None:
    fixture = _fixture()
    fixture["attempts"] = fixture["attempts"][:-1]
    with pytest.raises(Stage2EvaluationError, match="membership mismatch"):
        _report(fixture)
    fixture = _fixture()
    fixture["attempts"].append(copy.deepcopy(fixture["attempts"][0]))
    with pytest.raises(Stage2EvaluationError, match="duplicate attempt"):
        _report(fixture)


def test_wrong_membership_hash_and_source_mismatch_fail_closed() -> None:
    fixture = _fixture()
    with pytest.raises(Stage2EvaluationError, match="membership SHA-256"):
        evaluate_stage2(
            fixture["gold_records"],
            fixture["attempts"],
            contract=_contract(),
            dataset_id=fixture["dataset_id"],
            method_id=fixture["method_id"],
            expected_membership_sha256="0" * 64,
        )
    fixture["attempts"][0]["record"]["source_id"] = "synthetic:wrong"
    with pytest.raises(Stage2EvaluationError, match="source_id mismatch"):
        _report(fixture)


def test_runtime_token_mismatch_and_formal_scope_bypass_fail_closed() -> None:
    fixture = _fixture()
    fixture["attempts"][0]["runtime"]["total_tokens"] = 1
    with pytest.raises(Stage2EvaluationError, match="token totals disagree"):
        _report(fixture)
    fixture = _fixture()
    with pytest.raises(Stage2EvaluationError, match="final-readiness"):
        evaluate_stage2(
            fixture["gold_records"],
            fixture["attempts"],
            contract=_contract(),
            dataset_id=fixture["dataset_id"],
            method_id=fixture["method_id"],
            expected_membership_sha256=EXPECTED_MEMBERSHIP,
            claim_scope="formal",
            formal_ready=False,
        )


def test_style_equivalent_template_is_deterministic_blank_and_human_only() -> None:
    fixture = _fixture()
    contract = _contract()
    kwargs = {
        "dataset_id": fixture["dataset_id"],
        "method_id": fixture["method_id"],
        "sample_size": 2,
        "seed": contract["style_equivalent_review"]["seed"],
    }
    first = build_style_review_template(fixture["style_review_candidates"], **kwargs)
    second = build_style_review_template(
        list(reversed(fixture["style_review_candidates"])), **kwargs
    )
    # Candidate payload records input order for provenance, while selection is
    # deterministic by rank. Compare selected identities rather than payload hash.
    assert [r["sample_id"] for r in first["records"]] == [r["sample_id"] for r in second["records"]]
    assert validate_style_review_document(first, require_blank=True) == []
    assert first["human_only"] is True
    assert all(record["decision"] is None for record in first["records"])


def test_s210_exact_hash_gate_is_ready_and_wrong_hash_fails() -> None:
    gate = verify_s2_10_evaluator_gate(ROOT)
    assert gate["ready"] is True
    assert gate["sample_count"] == 5
    assert gate["main_data_results_ready"] is False
    wrong = replace(S210_EXPECTATIONS, contract_sha256="0" * 64)
    failed = verify_s2_10_evaluator_gate(ROOT, expectations=wrong)
    assert failed["ready"] is False
    assert "s210_contract_hash_mismatch" in failed["blockers"]


def test_status_and_audit_distinguish_evaluator_from_formal_results() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["s2_10_evaluator_verified"] is True
    assert status["s2_10_main_data_results_ready"] is False
    assert status["final_experiment_ready"] is False
    assert "s2_10_unified_evaluator_contract_verified" in pass_codes

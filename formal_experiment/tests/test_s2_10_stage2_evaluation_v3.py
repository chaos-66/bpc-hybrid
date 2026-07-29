"""Regression and adversarial tests for the S2.10-E v1.2 evaluator."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage2_evaluation_v3 import (  # noqa: E402
    CLAUSE_MINIMUM_IOU,
    Stage2EvaluationError,
    _maximum_weight_pairs,
    clause_iou_pairs,
    evaluate_stage2,
    load_evaluator_contract,
    membership_sha256,
    validate_evaluation_report,
)


CONTRACT_PATH = ROOT / "configs" / "stage2_evaluator_s210_v3.json"
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
        expected_membership_sha256=membership_sha256(fixture["gold_records"]),
    )


def test_v3_contract_freezes_task_independent_alignment_and_no_score_targeting() -> None:
    contract = _contract()
    assert contract["alignment"]["clause"] == "maximum_total_character_span_iou"
    assert contract["alignment"]["clause_minimum_iou"] == CLAUSE_MINIMUM_IOU
    assert contract["alignment"]["prediction_ids_are_method_local"] is True
    assert contract["alignment"]["threshold_search_forbidden"] is True
    assert contract["alignment"]["paper_score_targeting_forbidden"] is True
    assert contract["literature_comparison"]["maximum_absolute_difference_is_acceptance_criterion"] is False
    assert contract["literature_comparison"]["difference_over_0_10_is_diagnostic_alert_only"] is True


def test_v3_preserves_frozen_synthetic_metrics_and_adds_alignment_diagnostics() -> None:
    report = _report()
    assert validate_evaluation_report(report) == []
    assert report["membership"]["payload_sha256"] == EXPECTED_MEMBERSHIP
    assert report["primary_metrics"]["modality"]["macro_f1"] == pytest.approx(5 / 12)
    assert report["primary_metrics"]["modality"]["micro"] == {
        "tp": 2.0,
        "fp": 1.0,
        "fn": 3.0,
        "precision": pytest.approx(2 / 3),
        "recall": 0.4,
        "f1": 0.5,
    }
    action = report["primary_metrics"]["fields"]["action"]
    assert action["strict_exact"]["f1"] == 0.25
    assert action["safe_normalized"]["f1"] == 0.5
    segmentation = report["structural_encoding"]["clause_segmentation"]
    assert segmentation["exact_match_count"] == 3
    assert segmentation["aligned_match_count"] == 3
    assert segmentation["minimum_iou"] == 0.5
    assert report["safety"]["paper_score_targeting_used"] is False


def test_method_local_ids_and_one_character_boundary_difference_do_not_hide_semantics() -> None:
    fixture = _fixture()
    gold = copy.deepcopy(fixture["gold_records"][0])
    attempt = copy.deepcopy(fixture["attempts"][0])
    gold_clause = gold["clauses"][0]
    pred_clause = attempt["record"]["clauses"][0]

    gold_clause["clause_id"] = "gold_clause"
    gold_clause["actors"][0]["id"] = "gold_actor"
    gold_clause["actions"][0]["id"] = "gold_action"
    gold_clause["actor_action_map"] = [
        {"actor_id": "gold_actor", "action_id": "gold_action"}
    ]
    pred_clause["clause_id"] = "method_clause"
    pred_clause["actors"][0]["id"] = "method_actor"
    pred_clause["actions"][0].update(
        {"id": "method_action", "text": "archive records", "end": 31}
    )
    pred_clause["actor_action_map"] = [
        {"actor_id": "method_actor", "action_id": "method_action"}
    ]
    pred_clause["clause_span"] = {
        "text": "The clerk shall archive records",
        "start": 0,
        "end": 31,
    }

    report = evaluate_stage2(
        [gold],
        [attempt],
        contract=_contract(),
        dataset_id="s210_adversarial_method_local_ids",
        method_id="sun_llm_fallback",
        expected_membership_sha256=membership_sha256([gold]),
    )
    segmentation = report["structural_encoding"]["clause_segmentation"]
    assert segmentation["exact_match_count"] == 0
    assert segmentation["aligned_match_count"] == 1
    assert report["primary_metrics"]["modality"]["per_class"]["obligation"]["tp"] == 1
    assert report["primary_metrics"]["fields"]["actor"]["strict_exact"]["tp"] == 1
    assert report["primary_metrics"]["fields"]["action"]["strict_exact"]["tp"] == 1
    assert report["structural_encoding"]["actor_action_edges"]["tp"] == 1


def test_clause_threshold_accepts_majority_boundary_and_rejects_below_half() -> None:
    gold = [{"id": "g", "text": "g", "start": 0, "end": 1000}]
    at_half = [{"id": "p", "text": "p", "start": 0, "end": 500}]
    below_half = [{"id": "p", "text": "p", "start": 0, "end": 499}]
    assert clause_iou_pairs(gold, at_half)[0] == [(0, 0)]
    assert clause_iou_pairs(gold, below_half)[0] == []


def test_shared_id_never_overrides_disjoint_spans() -> None:
    gold = [{"id": "same", "text": "left", "start": 0, "end": 10}]
    predicted = [{"id": "same", "text": "right", "start": 20, "end": 30}]
    pairs, gold_left, pred_left, _ = clause_iou_pairs(gold, predicted)
    assert pairs == []
    assert gold_left == [0]
    assert pred_left == [0]


def test_assignment_is_global_optimum_not_greedy() -> None:
    left = [
        {"id": "l0", "text": "l0", "start": 0, "end": 1},
        {"id": "l1", "text": "l1", "start": 1, "end": 2},
    ]
    right = [
        {"id": "r0", "text": "r0", "start": 0, "end": 1},
        {"id": "r1", "text": "r1", "start": 1, "end": 2},
    ]
    weights = {
        ("l0", "r0"): 0.90,
        ("l0", "r1"): 0.80,
        ("l1", "r0"): 0.85,
        ("l1", "r1"): 0.10,
    }
    pairs, _, _, observed = _maximum_weight_pairs(
        left,
        right,
        score=lambda a, b: weights[(a["id"], b["id"])],
        minimum=0.0,
    )
    assert pairs == [(0, 1), (1, 0)]
    assert sum(observed[pair] for pair in pairs) == pytest.approx(1.65)


def test_clause_and_record_array_order_do_not_change_v3_report() -> None:
    fixture = _fixture()
    expected = _report(fixture)
    fixture["gold_records"].reverse()
    fixture["attempts"].reverse()
    for record in fixture["gold_records"]:
        record["clauses"].reverse()
    for attempt in fixture["attempts"]:
        if attempt.get("record"):
            attempt["record"]["clauses"].reverse()
    assert _report(fixture) == expected


def test_formal_scope_and_membership_still_fail_closed() -> None:
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

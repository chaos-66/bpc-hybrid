"""Regression tests for the S2.11 official-source complex legal freeze."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.complex_legal import (  # noqa: E402
    DATASET_ID,
    DECISION_FIELDS,
    build_blank_review,
    membership_sha256,
    parse_article_units,
    select_coverage_seeded50,
    validate_human_gold_review,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.s2_11_gate import (  # noqa: E402
    S211_EXPECTATIONS,
    verify_s2_11_gate,
)
from formal_experiment.status import collect_status  # noqa: E402


BASE = ROOT / "data/development/complex_legal/gdpr_2016_679_oj_en"
SOURCE = BASE / "source/DOC_2_body.xml"
DATASET = BASE / "gdpr_articles_5_50_seeded50_v1.jsonl"
MEMBERSHIP = BASE / "gdpr_articles_5_50_seeded50_v1.membership.json"
REVIEW = BASE / "gdpr_articles_5_50_seeded50_human_gold_v1.json"
SCHEMA = ROOT / "configs/schemas/complex_legal_human_gold.schema.json"
CONFIG = ROOT / "configs/datasets/gdpr_articles_5_50_s211.json"


def _dataset() -> list[dict]:
    return [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]


def _review() -> dict:
    return json.loads(REVIEW.read_text(encoding="utf-8"))


def test_official_formex_scope_has_200_units_across_articles_5_50() -> None:
    units = parse_article_units(SOURCE)
    assert len(units) == 200
    assert {unit.article for unit in units} == set(range(5, 51))
    assert len({unit.sample_id for unit in units}) == 200
    assert all(unit.source_text for unit in units)


def test_coverage_first_selection_is_deterministic_and_exactly_matches_frozen_data() -> None:
    expected = select_coverage_seeded50(parse_article_units(SOURCE))
    actual = _dataset()
    assert actual == expected
    assert len(actual) == 50
    assert {record["article"] for record in actual} == set(range(5, 51))
    assert sum(record["selection_role"] == "article_coverage" for record in actual) == 46
    assert sum(record["selection_role"] == "coverage_supplement" for record in actual) == 4
    assert len({record["source_text_sha256"] for record in actual}) == 50
    assert {record["dataset_id"] for record in actual} == {DATASET_ID}


def test_membership_hash_and_no_method_result_inputs_are_locked() -> None:
    dataset = _dataset()
    membership = json.loads(MEMBERSHIP.read_text(encoding="utf-8"))
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    digest = membership_sha256(dataset)
    assert digest == "9a6a2c892e6e9ef86877066fb3c88ad03d06ca999c41ecbd91c6df35d09c28b9"
    assert membership["membership_sha256"] == digest
    assert membership["method_outputs_used"] is False
    assert membership["evaluation_results_used"] is False
    assert membership["legacy_gdpr50_used"] is False
    assert config["selection"]["method_outputs_used"] is False
    assert config["selection"]["evaluation_results_used"] is False
    assert "model prediction" in config["selection"]["forbidden_inputs"]
    assert "evaluation result" in config["selection"]["forbidden_inputs"]


def test_blank_human_gold_is_input_ready_but_not_frozen() -> None:
    dataset = _dataset()
    review = _review()
    assert review == build_blank_review(dataset)
    report = validate_human_gold_review(review, dataset, SCHEMA)
    assert report == {
        "format_valid": True,
        "input_ready": True,
        "freeze_ready": False,
        "reviewed": 0,
        "adjudicated": 0,
        "canonical_rule_present": 0,
        "errors": [],
    }


def test_agent_style_auto_progress_from_blank_is_rejected() -> None:
    review = _review()
    review["records"][0]["review_state"] = "reviewed"
    report = validate_human_gold_review(review, _dataset(), SCHEMA)
    assert report["format_valid"] is False
    assert any("reviewed source" in error or "unresolved" in error for error in report["errors"])


def test_frozen_source_text_tampering_is_rejected() -> None:
    review = _review()
    review["records"][0]["source_text"] += " changed"
    report = validate_human_gold_review(review, _dataset(), SCHEMA)
    assert report["format_valid"] is False
    assert any("differs from frozen input" in error for error in report["errors"])


def test_explicit_human_negative_decision_can_be_structurally_reviewed() -> None:
    review = _review()
    record = review["records"][0]
    record["review_state"] = "reviewed"
    record["record_decision"] = "no_canonical_rule"
    record["decisions"] = {field: "rejected" for field in DECISION_FIELDS}
    record["decisions"]["source_verified"] = "accepted"
    record["reviewer"] = "human-reviewer"
    record["reviewed_at"] = "2026-07-17T00:00:00Z"
    review["status"] = "human_annotation_in_progress"
    report = validate_human_gold_review(review, _dataset(), SCHEMA)
    assert report["format_valid"] is True
    assert report["reviewed"] == 1
    assert report["adjudicated"] == 0
    assert report["freeze_ready"] is False


def test_canonical_gold_clause_uses_shared_span_contract() -> None:
    dataset = _dataset()
    review = _review()
    source_index = next(
        index for index, item in enumerate(dataset)
        if "shall" in item["source_text"].lower()
    )
    source = dataset[source_index]["source_text"]
    evidence_start = source.lower().index("shall")
    evidence_end = evidence_start + len("shall")
    record = review["records"][source_index]
    record["review_state"] = "reviewed"
    record["record_decision"] = "canonical_rule_present"
    record["canonical_gold"] = {
        "clauses": [
            {
                "clause_id": "c1",
                "clause_span": {"text": source, "start": 0, "end": len(source)},
                "modality": {
                    "label": "obligation",
                    "evidence": [
                        {"text": source[evidence_start:evidence_end], "start": evidence_start, "end": evidence_end}
                    ],
                },
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
                "actor_action_map": [],
                "order_relations": [],
            }
        ]
    }
    record["decisions"] = {field: "accepted" for field in DECISION_FIELDS}
    record["reviewer"] = "human-reviewer"
    record["reviewed_at"] = "2026-07-17T00:00:00Z"
    review["status"] = "human_annotation_in_progress"
    report = validate_human_gold_review(review, dataset, SCHEMA)
    assert report["format_valid"] is True
    assert report["canonical_rule_present"] == 1


def test_s211_exact_hash_gate_is_ready_but_gold_freeze_is_false() -> None:
    gate = verify_s2_11_gate(ROOT)
    assert gate["ready"] is True
    assert gate["input_ready"] is True
    assert gate["human_gold_freeze_ready"] is False
    assert gate["selected_count"] == 50
    assert gate["article_coverage_count"] == 46
    assert gate["performance_evaluation"] is False


def test_s211_wrong_expected_hash_fails_closed() -> None:
    wrong = replace(S211_EXPECTATIONS, dataset_sha256="0" * 64)
    gate = verify_s2_11_gate(ROOT, expectations=wrong)
    assert gate["ready"] is False
    assert "s211_dataset_hash_mismatch" in gate["blockers"]


def test_status_and_audit_report_s211_without_final_readiness() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["s2_11_verified"] is True
    assert status["s2_11_input_ready"] is True
    assert status["s2_11_human_gold_freeze_ready"] is False
    assert status["final_experiment_ready"] is False
    assert "s2_11_complex_legal_source_membership_protocol_verified" in pass_codes

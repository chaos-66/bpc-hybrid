# -*- coding: utf-8 -*-
"""Focused tests for the SEP-C3 definition-clause analysis."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import analyze_sep_c3_definition_clause_v1 as definition  # noqa: E402


def _corpus():
    gold = definition.load_gold()
    arms = definition.load_arms()
    cases, candidates = definition.build_cases(gold, arms)
    summary = definition.summarize_gold(gold, arms)
    return gold, arms, cases, candidates, summary


def test_definition_corpus_counts():
    _, _, cases, candidates, summary = _corpus()
    assert len(cases) == 39
    assert summary["definition_clause_count"] == 39
    assert summary["definition_sample_count_any"] == 34
    assert summary["first_definition_sample_count"] == 29
    assert summary["definition_action_span_count"] == 46
    assert summary["definition_clauses_with_empty_action"] == 0
    assert len(candidates) == 14


def test_modality_failure_counts_and_shall():
    _, _, _, _, summary = _corpus()
    assert summary["first_definition_sample_all_four_modality_wrong"] == 20
    assert summary["clause_all_four_modality_wrong"] == 25
    assert summary["shall_definition_clause_count"] == 15
    assert summary["shall_definition_clauses_all_four_wrong"] == 15
    assert summary["first_definition_all_wrong_with_shall"] == 12


def test_definition_actions_are_never_empty_and_taxonomy_is_complete():
    _, _, cases, _, _ = _corpus()
    assert all(case["gold"]["actions"] for case in cases)
    rows = definition.action_matrix_rows(cases)
    assert len(rows) == 46
    assert Counter(row["taxonomy_primary"] for row in rows) == {
        "action_span_includes_subordinate_phrase": 2,
        "classification_verb": 9,
        "copular_action": 6,
        "deeming_legal_fiction": 10,
        "definitional_verb": 3,
        "other_event_predicate": 6,
        "relational_predicate": 10,
    }
    keys = {
        (case["sample_id"], case["clause_id"], index)
        for case in cases
        for index, _ in enumerate(case["gold"]["actions"])
    }
    assert keys == set(definition.ACTION_TAXONOMY)


def test_e4_and_s_texts_keep_the_relevant_conflict():
    e_text = definition.PROMPT_PATHS["E"].read_text(encoding="utf-8")
    s_text = definition.PROMPT_PATHS["S"].read_text(encoding="utf-8")
    assert "actors and actions empty" in e_text
    assert "a definition clause may have no actions" in s_text
    _, _, cases, _, _ = _corpus()
    assert sum(1 for case in cases if case["gold"]["actions"]) == 39


def test_definition_reports_exist_and_are_nonempty():
    required = [
        definition.REPORT_DIR / "sep_c3_definition_clause_semantics_v1.md",
        definition.REPORT_DIR / "sep_c3_definition_clause_cases.jsonl",
        definition.REPORT_DIR / "sep_c3_definition_modality_matrix.csv",
        definition.REPORT_DIR / "sep_c3_definition_action_matrix.csv",
        definition.REPORT_DIR / "sep_c3_definition_contrastive_pairs.md",
        definition.REPORT_DIR / "sep_c3_E4_coverage_audit.md",
        definition.REPORT_DIR / "sep_c3_E_examples_coverage_matrix.md",
        definition.REPORT_DIR / "sep_c3_S_modality_action_audit.md",
        definition.REPORT_DIR / "sep_c3_definition_gold_consistency_audit.md",
        definition.REPORT_DIR / "sep_c3_definition_field_priority.md",
    ]
    for path in required:
        assert path.exists(), path
        assert path.stat().st_size > 0, path
    assert "CONFLICTS_WITH_GOLD" in (
        definition.REPORT_DIR / "sep_c3_E4_coverage_audit.md"
    ).read_text(encoding="utf-8")


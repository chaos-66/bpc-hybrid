# -*- coding: utf-8 -*-
"""Focused invariants for the SEP-C3 definition prompt-design reports."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "outputs" / "reports"

DESIGN_REPORT = REPORT_DIR / "sep_c3_definition_prompt_design_v1.md"
DIFF_REPORT = REPORT_DIR / "sep_c3_definition_prompt_candidate_diff_v1.md"
SAFETY_REPORT = REPORT_DIR / "sep_c3_definition_prompt_safety_review_v1.md"
E4_CANDIDATE = REPORT_DIR / "sep_c3_definition_synthetic_E4_candidate_v1.json"


def test_design_reports_exist_and_nonempty():
    for path in (DESIGN_REPORT, DIFF_REPORT, SAFETY_REPORT):
        assert path.exists(), path
        assert path.stat().st_size > 0, path
        text = path.read_text(encoding="utf-8")
        assert "New API / LLM calls" in text


def test_s2_and_s11_candidates_are_recorded():
    design = DESIGN_REPORT.read_text(encoding="utf-8")
    for marker in (
        "S2_CURRENT",
        "S2_PROPOSED",
        "S2_DIFF",
        "S11_CURRENT",
        "S11_PROPOSED",
        "S11_DIFF",
    ):
        assert marker in design, marker
    diff = DIFF_REPORT.read_text(encoding="utf-8")
    assert "semantic_rules_S.md" in diff
    assert "a definition clause may have no actions" in diff
    assert "classification or membership" in diff


def test_e4_candidate_is_synthetic_and_has_action_in_every_definition_clause():
    candidate = json.loads(E4_CANDIDATE.read_text(encoding="utf-8"))
    sentence = candidate["synthetic_sentence"]
    assert sentence
    assert sentence == candidate["expected_rule_record"]["source_text"]
    assert "estg_" not in sentence
    assert not re.search(r"estg_\d+", sentence)

    clauses = candidate["expected_rule_record"]["clauses"]
    assert len(clauses) == 2
    for clause in clauses:
        assert clause["modality"]["label"] == "definition"
        assert len(clause["actions"]) >= 1
        assert clause["clause_span"]["text"] == sentence[
            clause["clause_span"]["start"]:clause["clause_span"]["end"]
        ]
        for field in ("actions", "conditions", "constraints", "exceptions"):
            for item in clause[field]:
                assert sentence[item["start"]:item["end"]] == item["text"]
                assert clause["clause_span"]["start"] <= item["start"] <= item["end"] <= clause["clause_span"]["end"]
        for evidence in clause["modality"]["evidence"]:
            assert sentence[evidence["start"]:evidence["end"]] == evidence["text"]
            assert clause["clause_span"]["start"] <= evidence["start"] <= evidence["end"] <= clause["clause_span"]["end"]


def test_safety_report_preserves_unresolved_apply_and_boundary_issues():
    safety = SAFETY_REPORT.read_text(encoding="utf-8")
    assert "apply-family" in safety.lower()
    assert "UNRESOLVED" in safety or "unresolved" in safety
    assert "S8" in safety
    assert "measured" in safety.lower()
    assert "READY_FOR_OFFLINE_PATCH" in safety
    assert "NEEDS_GOLD_ADJUDICATION" in safety

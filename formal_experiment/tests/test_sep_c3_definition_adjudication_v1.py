# -*- coding: utf-8 -*-
"""Focused tests for SEP-C3 definition adjudication / Prompt Design Gate."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "analyze_sep_c3_definition_adjudication_v1.py"
REPORT_DIR = ROOT / "outputs" / "reports"
PROMPT_HASHES = {
    ROOT / "prompts" / "sun_compat" / "modular_v1" / "examples_E.md":
        "fa04d454914fd85ad422ed40b3e4d3f71027ad87e9a46b1f4808f0cb4e21aebd",
    ROOT / "prompts" / "sun_compat" / "modular_v1" / "semantic_rules_S.md":
        "113037b73485adb071dbfeabc54dfe6906514279c3dd065f72b4eb019d3a0025",
    ROOT / "prompts" / "sun_compat" / "modular_v1" / "common_system.md":
        "b8cfc32b87f446ced89da83fd0ad5aef69ee418a116c6ede534816c5204ac2d7",
}


def load_module():
    spec = importlib.util.spec_from_file_location("adjudication_v1", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def test_definition_corpus_and_action_presence_counts():
    module = load_module()
    summary = module.build_analysis()["summary"]
    assert summary["definition_clause_count"] == 39
    assert summary["definition_sample_count"] == 34
    assert summary["first_definition_sample_count"] == 29
    assert summary["definition_action_span_count"] == 46
    assert summary["definition_empty_action_count"] == 0
    assert summary["definition_actor_count"] == 2
    assert summary["definition_condition_count"] == 28
    assert summary["definition_constraint_count"] == 28
    assert summary["definition_exception_count"] == 5
    assert summary["definition_all_three_empty_count"] == 0
    assert summary["definition_all_four_wrong_count"] == 25
    assert summary["first_definition_all_four_wrong_count"] == 20
    assert summary["shall_definition_count"] == 15
    assert summary["shall_definition_all_four_wrong_count"] == 15
    assert summary["overlapping_definition_case_count"] == 6
    assert summary["predicate_marked_definition_count"] == 39
    assert summary["per_arm_empty_action_count"] == {"A": 10, "B": 13, "C": 12, "D": 12}


def test_apply_family_and_shall_family_counts():
    module = load_module()
    summary = module.build_analysis()["summary"]
    assert summary["apply_core_count"] == 12
    assert summary["apply_definition_count"] == 7
    assert summary["apply_nondefinition_count"] == 5
    assert sum(v["definition_count"] for k, v in summary["family_summary"].items()
               if not k.startswith("_")) == 15
    assert summary["family_summary"]["shall_be_assumed"]["similar_nondefinition"][0]["sample_id"] == "estg_000505"
    assert {c["sample_id"] for c in summary["family_summary"]["shall_apply"]["similar_nondefinition"]} == {
        "estg_000056", "estg_000128", "estg_000208"}
    assert summary["family_summary"]["shall_be_determined"]["similar_nondefinition"][0]["sample_id"] == "estg_000812"


def test_target_505_509_pair_adjudication():
    module = load_module()
    data = module.build_analysis()
    case_map = data["case_map"]
    c505 = case_map[("estg_000505", "c2")]
    c509 = case_map[("estg_000509", "c2")]
    assert c505["gold"]["modality"] == "obligation"
    assert c509["gold"]["modality"] == "definition"
    assert c505["gold_action_presence"]["action_texts"] == ["be assumed"]
    assert c509["gold_action_presence"]["action_texts"] == ["be assumed"]
    assert c505["predictions"]["A"]["modality_label"] == "obligation"
    assert c509["predictions"]["A"]["modality_label"] == "obligation"
    row = next(r for r in data["matrix_rows"]
               if r["analysis_group"] == "pair_estg_000505_vs_estg_000509"
               and r["sample_id"] == "estg_000505")
    assert row["adjudication_label"] == "POTENTIAL_GOLD_INCONSISTENCY"


def test_target_determined_pair_adjudication():
    module = load_module()
    data = module.build_analysis()
    case_map = data["case_map"]
    c136 = case_map[("estg_000136", "c1")]
    c812 = case_map[("estg_000812", "c1")]
    assert c136["gold"]["modality"] == "definition"
    assert c812["gold"]["modality"] == "obligation"
    assert c136["gold_action_presence"]["action_texts"] == ["be determined"]
    assert c812["gold_action_presence"]["action_texts"] == ["be determined"]
    rows = [r for r in data["matrix_rows"]
            if r["analysis_group"] == "pair_shall_be_determined"]
    assert {r["sample_id"] for r in rows} == {"estg_000136", "estg_000812"}
    assert all(r["adjudication_label"] == "CONTEXTUALLY_EXPLAINABLE" for r in rows)


def test_action_spans_all_within_clause_and_predicate_marked():
    module = load_module()
    data = module.build_analysis()
    for case in data["definition_cases"]:
        assert case["gold_action_presence"]["has_action"] is True
        assert case["gold_action_presence"]["all_actions_within_clause"] is True
        for action in case["gold"]["actions"]:
            assert module.PREDICATE_MARKER_RE.search(action["text"])


def test_output_artifacts_exist_and_matrix_groups():
    paths = [
        REPORT_DIR / "sep_c3_definition_adjudication_v1.md",
        REPORT_DIR / "sep_c3_definition_adjudication_cases.jsonl",
        REPORT_DIR / "sep_c3_definition_modality_contrastive_matrix.csv",
        REPORT_DIR / "sep_c3_definition_prompt_design_gate.md",
        REPORT_DIR / "sep_c3_E4_final_diagnosis.md",
        REPORT_DIR / "sep_c3_S_definition_guidance_diagnosis.md",
    ]
    for path in paths:
        assert path.exists() and path.stat().st_size > 0
    cases = read_jsonl(REPORT_DIR / "sep_c3_definition_adjudication_cases.jsonl")
    assert len(cases) == 46
    matrix_rows = list(csv.DictReader(
        (REPORT_DIR / "sep_c3_definition_modality_contrastive_matrix.csv").open(
            encoding="utf-8")))
    groups = {row["analysis_group"] for row in matrix_rows}
    assert "pair_estg_000505_vs_estg_000509" in groups
    assert "pair_shall_be_determined" in groups
    assert "apply_family_core" in groups
    assert "shall_definition_family" in groups
    assert "definition_action_presence" in groups


def test_e4_and_s_diagnosis_text():
    e4 = (REPORT_DIR / "sep_c3_E4_final_diagnosis.md").read_text(encoding="utf-8")
    s = (REPORT_DIR / "sep_c3_S_definition_guidance_diagnosis.md").read_text(encoding="utf-8")
    assert "CONFLICTS_WITH_GOLD" in e4
    assert "CONFLICTING" in e4
    assert "UNDER-REPRESENTATIVE" in e4
    assert "MISSING_DEFINITION_MODALITY_GUIDANCE" in s
    assert "MISLEADING_PERMISSIVE_GUIDANCE" in s
    assert "LOCALLY_CONFLICTING_ACTION_BOUNDARY_GUIDANCE" in s


def test_prompt_modules_were_not_modified():
    for path, expected in PROMPT_HASHES.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, path

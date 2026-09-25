"""Focused tests for the S3-TABLE3-R5 benchmark construction (no API)."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/development/stage3_table3_r5_benchmark_v1"
REPORTS = ROOT / "outputs/reports"
sys.path.insert(0, str(ROOT / "scripts"))
import validate_stage3_table3_r5_benchmark as validator  # noqa: E402


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_counts_and_split():
    manifest = load(DATA / "manifest.json")
    assert manifest["independent_requirements"] == 36
    assert manifest["core_cases"] == 108
    assert manifest["baseline_controls"] == 36
    assert manifest["variants_per_type"] == {"missing_action": 24, "incorrect_actor": 24, "out_of_order": 24}
    assert manifest["development_requirements"] == 12
    assert manifest["test_requirements"] == 24
    assert manifest["test_independent_candidate_count"] >= 20
    assert all(manifest["scenario_counts"].get(s, 0) >= 4 for s in ["S1", "S2", "S3", "S4", "S5", "S6"])
    assert manifest["element_coverage"]["modality"] == 36
    assert manifest["element_coverage"]["actor"] == 36
    assert manifest["element_coverage"]["action"] == 36
    assert manifest["element_coverage"]["condition"] >= 12
    assert manifest["element_coverage"]["constraint"] >= 20
    assert manifest["element_coverage"]["exception"] >= 8


def test_source_hashes_and_unique_texts():
    doc = load(DATA / "source_requirements.json")
    hashes = [r["text_sha256"] for r in doc["requirements"]]
    assert len(hashes) == len(set(hashes)) == 36
    for rec in doc["requirements"]:
        assert rec["source_url"]
        assert rec["document_version"]
        assert rec["citation"]
        assert rec["text_sha256"] == validator.sha_text(rec["excerpt_text"])
        assert rec["elements"]["actor"]["present"] is True
        assert rec["elements"]["action"]["present"] is True


def test_reference_single_error_and_na():
    doc = load(DATA / "reference/reference_cases.json")
    for case in doc["cases"]:
        violated = [k for k, v in case["reference_states"].items() if v == "violated"]
        if case["variant"] == "baseline":
            assert not violated
        else:
            assert len(violated) == 1
        if case["variant"] == "missing_action":
            assert case["reference_states"]["incorrect_actor"] == "not_applicable"
            assert case["reference_states"]["out_of_order"] == "not_applicable"


def test_bpmn_structural_mutation_and_validity():
    passed, checks = validator.validate()
    failed = [c for c in checks if not c["passed"]]
    assert passed, failed


def test_inference_isolation():
    doc = load(DATA / "inference/inference_view.json")
    text = json.dumps(doc, ensure_ascii=False).lower()
    assert "missing_action" not in text
    assert "incorrect_actor" not in text
    assert "out_of_order" not in text
    assert "reference_states" not in text
    for item in doc["items"]:
        assert "variant" not in item
        assert "requirement_id" not in item
        assert "family_id" not in item


def test_semantic_challenges_separate():
    doc = load(DATA / "semantic_challenges.json")
    assert doc["not_mixed_with_core_f1"] is True
    assert doc["modality_fragment_counts"] == {"prohibition": 4, "permission": 4, "definition": 4}
    assert sum(1 for p in doc["pairs"] if p["pair_kind"] == "condition") == 6
    assert sum(1 for p in doc["pairs"] if p["pair_kind"] == "exception") == 6


def test_reuse_and_budget_are_stage2_input_units():
    reuse = load(REPORTS / "stage3_table3_r5_prediction_reuse_v1.json")
    budget = load(REPORTS / "stage3_table3_r5_api_budget_v1.json")
    assert reuse["reused_unique_inputs"] + reuse["new_ours_requests"] == 36
    assert budget["calls_cap"] == reuse["new_ours_requests"] == 22
    assert budget["calls_cap"] != 108
    assert budget["retry_cap"] == 0
    assert budget["total_output_tokens_cap"] == budget["calls_cap"] * budget["max_output_tokens_per_call"]


def test_readiness_statuses_not_masked_by_completed():
    readiness = load(REPORTS / "stage3_table3_r5_readiness_v1.json")
    assert readiness["statuses"] == {
        "data": "DATA_READY",
        "methods": "METHODS_NOT_READY",
        "api": "API_AUTHORIZATION_PENDING",
        "formal_release": "FORMAL_RELEASE_NOT_APPROVED",
    }
    assert readiness["can_start_formal_method_run"] is False
    assert len(readiness["prechecks"]) >= 7

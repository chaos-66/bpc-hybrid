"""Regression tests for the pre-result G0.5 complexity contract."""

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

from bpc_hybrid.complexity import (  # noqa: E402
    ComplexityContractError,
    load_complexity_contract,
    profile_bpmn_complexity,
    profile_text_complexity,
    validate_complexity_profile,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.g05_complexity_gate import (  # noqa: E402
    G05_EXPECTATIONS,
    verify_g05_complexity_gate,
)
from formal_experiment.status import collect_status  # noqa: E402


CONTRACT_PATH = ROOT / "configs" / "complexity_contract.json"
SCHEMA_PATH = ROOT / "configs" / "schemas" / "complexity_profile.schema.json"
TEXT_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "complexity" / "text_two_sentence_fixture.json"
BPMN_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "complexity" / "bpmn_cycle_fixture.bpmn"


def _contract() -> dict:
    return load_complexity_contract(CONTRACT_PATH)


def _text_fixture() -> dict:
    return json.loads(TEXT_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_g05_contract_freezes_indicators_strata_and_no_result_boundary() -> None:
    contract = _contract()
    assert len(contract["text"]["score_indicators"]) == 11
    assert len(contract["bpmn"]["score_indicators"]) == 12
    assert contract["text"]["strata"]["medium"] == {"min_score": 4, "max_score": 7}
    assert contract["bpmn"]["strata"]["high"] == {"min_score": 8, "max_score": 12}
    assert contract["leakage_boundary"]["strata_frozen_before_method_outputs"] is True
    assert "model_prediction" in contract["leakage_boundary"]["forbidden_sources"]
    assert "test_result" in contract["leakage_boundary"]["forbidden_sources"]


def test_text_fixture_profile_matches_fixed_medium_stratum() -> None:
    profile = profile_text_complexity(_text_fixture(), _contract())
    assert profile["metrics"]["character_count"] == 66
    assert profile["metrics"]["token_count"] == 13
    assert profile["metrics"]["max_dependency_depth"] == 3
    assert profile["metrics"]["actor_count"] == 2
    assert profile["metrics"]["action_count"] == 2
    assert profile["metrics"]["cross_sentence_reference_count"] == 1
    assert profile["complexity_score"] == 4
    assert profile["complexity_stratum"] == "medium"
    assert validate_complexity_profile(profile, SCHEMA_PATH) == []


def test_translation_status_is_reported_but_not_scored() -> None:
    original = _text_fixture()
    translated = copy.deepcopy(original)
    translated["translation_status"] = "human_translation"
    translated["source_language"] = "de"
    original_profile = profile_text_complexity(original, _contract())
    translated_profile = profile_text_complexity(translated, _contract())
    assert translated_profile["metrics"]["translation_status"] == "human_translation"
    assert translated_profile["metrics"]["source_language"] == "de"
    assert translated_profile["indicator_flags"] == original_profile["indicator_flags"]
    assert translated_profile["complexity_score"] == original_profile["complexity_score"]


@pytest.mark.parametrize("source_role", ["model_prediction", "development_prediction", "test_result"])
def test_text_method_or_result_roles_fail_closed(source_role: str) -> None:
    fixture = _text_fixture()
    fixture["source_role"] = source_role
    with pytest.raises(ComplexityContractError, match="forbidden"):
        profile_text_complexity(fixture, _contract())


def test_text_token_offset_tampering_fails_closed() -> None:
    fixture = _text_fixture()
    fixture["annotation"]["sentences"][0]["tokens"][0]["characterOffsetEnd"] = 4
    with pytest.raises(ComplexityContractError, match="offsets"):
        profile_text_complexity(fixture, _contract())


def test_duplicate_cross_sentence_reference_fails_closed() -> None:
    fixture = _text_fixture()
    fixture["cross_sentence_reference_links"].append(
        copy.deepcopy(fixture["cross_sentence_reference_links"][0])
    )
    with pytest.raises(ComplexityContractError, match="duplicate"):
        profile_text_complexity(fixture, _contract())


def test_bpmn_cycle_fixture_profile_matches_fixed_low_stratum() -> None:
    profile = profile_bpmn_complexity(
        item_id="g05_bpmn_cycle_fixture_1",
        xml_text=BPMN_FIXTURE_PATH.read_text(encoding="utf-8"),
        source_role="synthetic_fixture",
        contract=_contract(),
    )
    assert profile["metrics"]["flow_node_count"] == 5
    assert profile["metrics"]["cycle_present"] is True
    assert profile["metrics"]["cyclomatic_complexity"] == 2
    assert profile["metrics"]["condensation_dag_depth"] == 4
    assert profile["complexity_score"] == 1
    assert profile["complexity_stratum"] == "low"
    assert validate_complexity_profile(profile, SCHEMA_PATH) == []


def test_bpmn_external_entity_declaration_fails_closed() -> None:
    with pytest.raises(ComplexityContractError, match="external entities"):
        profile_bpmn_complexity(
            item_id="bad",
            xml_text='<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><definitions/>',
            source_role="synthetic_fixture",
            contract=_contract(),
        )


def test_bpmn_unknown_sequence_endpoint_fails_closed() -> None:
    xml = BPMN_FIXTURE_PATH.read_text(encoding="utf-8").replace(
        'targetRef="task_1"', 'targetRef="missing_node"', 1
    )
    with pytest.raises(ComplexityContractError, match="endpoints"):
        profile_bpmn_complexity(
            item_id="bad",
            xml_text=xml,
            source_role="synthetic_fixture",
            contract=_contract(),
        )


def test_g05_exact_hash_gate_is_ready() -> None:
    gate = verify_g05_complexity_gate(ROOT)
    assert gate["ready"] is True
    assert gate["text_indicator_count"] == 11
    assert gate["bpmn_indicator_count"] == 12
    assert gate["complex_dataset_selected"] is False
    assert gate["performance_evaluation"] is False


def test_g05_wrong_expected_hash_fails_closed() -> None:
    wrong = replace(G05_EXPECTATIONS, contract_config_sha256="0" * 64)
    gate = verify_g05_complexity_gate(ROOT, expectations=wrong)
    assert gate["ready"] is False
    assert "g05_contract_config_hash_mismatch" in gate["blockers"]


def test_status_and_audit_report_verified_g05_without_final_readiness() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["g05_complexity_verified"] is True
    assert status["final_experiment_ready"] is False
    assert "g05_pre_result_complexity_contract_verified" in pass_codes


"""S2.5 CoreNLP/Tregex/Tsurgeon contract, live evidence, and gate tests."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

from bpc_hybrid.sun_style.corenlp_runtime import (
    CONFIG_REL,
    EXTRACTION_ORDER,
    CoreNLPContractError,
    build_stanford_corenlp_command,
    load_runtime_contract,
    resolve_corenlp_runtime,
    validate_fixture_document,
)
from formal_experiment.audit import collect_project_audit
from formal_experiment.corenlp_gate import (
    CORENLP_CONTRACT_EXPECTATIONS,
    CoreNLPContractExpectations,
    verify_corenlp_contract,
)
from formal_experiment.status import collect_status


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "corenlp"
    / "obligation_condition_constraint.json"
)
PATTERN_PATH = PROJECT_ROOT / "resources" / "corenlp" / "sun_phrase_patterns_v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_s2_5_production_contract_and_attested_runtime_are_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CORENLP_HOME", raising=False)
    gate = verify_corenlp_contract(PROJECT_ROOT)
    assert gate["contract_ready"] is True
    assert gate["runtime_ready"] is True
    assert gate["ready"] is True
    assert gate["runtime_probe_ready"] is False
    assert gate["corenlp_version"] == "4.5.10"
    assert gate["extraction_order"] == list(EXTRACTION_ORDER)
    assert gate["blockers"] == []
    assert gate["live_summary"] == {
        "match_count": 11,
        "pattern_count": 12,
        "surgery_count": 7,
        "tree_count": 2,
    }


def test_s2_5_exact_hashes_are_locked() -> None:
    gate = verify_corenlp_contract(PROJECT_ROOT)
    assert gate["runtime_config_sha256"] == (
        CORENLP_CONTRACT_EXPECTATIONS.runtime_config_sha256
    )
    assert gate["pattern_registry_sha256"] == (
        CORENLP_CONTRACT_EXPECTATIONS.pattern_registry_sha256
    )
    assert gate["fixture_sha256"] == CORENLP_CONTRACT_EXPECTATIONS.fixture_sha256
    assert gate["live_manifest_sha256"] == (
        CORENLP_CONTRACT_EXPECTATIONS.live_manifest_sha256
    )
    assert gate["java_bridge_sha256"] == (
        CORENLP_CONTRACT_EXPECTATIONS.java_bridge_sha256
    )


def test_s2_5_runtime_contract_tracks_verified_s2_4_and_safety_boundaries() -> None:
    contract = load_runtime_contract(PROJECT_ROOT)
    boundaries = contract["project_boundaries"]
    assert boundaries["s2_4_status"] == (
        "verified_training_dev_selection_single_test_evaluation"
    )
    assert boundaries["sun_modality_dataset_license_dependency"] == (
        "rights_unknown_local_research_use_ready_no_redistribution"
    )
    assert boundaries["activation_authorized"] is True
    assert boundaries["s2_5_overall_verified"] is True
    assert boundaries["s2_6_component_composition_authorized"] is True
    assert boundaries["training_run"] is False
    assert boundaries["evaluation_run"] is False
    assert boundaries["formal_use_allowed"] is False
    assert contract["official_distribution"]["archive_sha256"] == (
        "76a04089069dad21176c02881f46e07c19ca148b71c8581de2b5b2e2855e042e"
    )
    assert contract["official_distribution"]["network_download_performed"] is True
    assert boundaries["network_called_by_implementation"] is False


def test_s2_5_rule_registry_locks_six_fields_and_action_actor_order() -> None:
    registry = _load(PATTERN_PATH)
    assert tuple(registry["extraction_order"]) == EXTRACTION_ORDER
    assert tuple(item["field"] for item in registry["fields"]) == EXTRACTION_ORDER
    assert registry["ordering_policy"]["action_after_removed_context"] == list(
        EXTRACTION_ORDER[:4]
    )
    assert registry["ordering_policy"]["actor_after_action"] is True
    operations = {
        item["field"]: item["tsurgeon_operations"] for item in registry["fields"]
    }
    assert operations == {
        "modality": ["prune modality"],
        "condition": ["prune condition"],
        "constraint": ["prune constraint"],
        "exception": ["prune exception"],
        "action": [],
        "actor": [],
    }
    assert registry["boundaries"]["live_java_tregex_executed"] is True


def test_s2_5_synthetic_fixture_offsets_and_corenlp_shape_are_valid() -> None:
    summary = validate_fixture_document(_load(FIXTURE_PATH))
    assert summary == {"sentences": 1, "tokens": 13, "dependencies": 11}


def test_s2_5_multiline_official_parse_shape_is_accepted() -> None:
    fixture = copy.deepcopy(_load(FIXTURE_PATH))
    fixture["annotation"]["sentences"][0]["parse"] = fixture[
        "annotation"
    ]["sentences"][0]["parse"].replace("(S ", "(S\n  ", 1)
    summary = validate_fixture_document(fixture)
    assert summary["sentences"] == 1


def test_s2_5_fixture_offset_tamper_fails_closed() -> None:
    fixture = copy.deepcopy(_load(FIXTURE_PATH))
    fixture["annotation"]["sentences"][0]["tokens"][0]["characterOffsetEnd"] = 1
    with pytest.raises(CoreNLPContractError, match="originalText disagrees"):
        validate_fixture_document(fixture)


def test_s2_5_runtime_probe_requires_explicit_home() -> None:
    probe = resolve_corenlp_runtime(
        PROJECT_ROOT,
        environ={},
        java_executable=sys.executable,
    )
    assert probe.ready is False
    assert "corenlp_home_not_configured" in probe.reasons
    assert probe.classpath_entries == ()


def test_s2_5_fake_external_runtime_builds_command_without_running_java(
    tmp_path: Path,
) -> None:
    home = tmp_path / "corenlp"
    home.mkdir()
    for jar_name in load_runtime_contract(PROJECT_ROOT)["runtime"]["required_jars"]:
        (home / jar_name).write_bytes(b"fixture-only")
    (home / "support.jar").write_bytes(b"fixture-only")
    probe = resolve_corenlp_runtime(
        PROJECT_ROOT,
        home=home,
        environ={},
        java_executable=sys.executable,
    )
    assert probe.ready is True
    input_path = tmp_path / "input.txt"
    output_directory = tmp_path / "output"
    command = build_stanford_corenlp_command(
        PROJECT_ROOT,
        probe,
        input_path=input_path,
        output_directory=output_directory,
    )
    assert command[0] == str(Path(sys.executable).resolve())
    assert "edu.stanford.nlp.pipeline.StanfordCoreNLP" in command
    assert "tokenize,ssplit,pos,lemma,parse,depparse" in command
    assert str(input_path.resolve()) in command
    assert not input_path.exists()
    assert not output_directory.exists()


def test_s2_5_wrong_expected_hash_fails_closed() -> None:
    wrong = CoreNLPContractExpectations(
        runtime_config_sha256="0" * 64,
        pattern_registry_sha256=CORENLP_CONTRACT_EXPECTATIONS.pattern_registry_sha256,
        fixture_sha256=CORENLP_CONTRACT_EXPECTATIONS.fixture_sha256,
    )
    gate = verify_corenlp_contract(PROJECT_ROOT, expectations=wrong)
    assert gate["contract_ready"] is False
    assert "s2_5_runtime_config_hash_mismatch" in gate["blockers"]


def test_s2_5_deactivated_runtime_contract_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / CONFIG_REL
    target.parent.mkdir(parents=True)
    contract = _load(PROJECT_ROOT / CONFIG_REL)
    contract["project_boundaries"]["activation_authorized"] = False
    target.write_text(json.dumps(contract), encoding="utf-8")
    with pytest.raises(CoreNLPContractError, match="runtime/live activation"):
        load_runtime_contract(tmp_path)


def test_s2_5_status_and_audit_expose_verified_extractor_and_ready_s2_4() -> None:
    status = collect_status()
    assert status["s2_5_contract_verified"] is True
    assert status["s2_5_runtime_ready"] is True
    assert status["s2_5_verified"] is True
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    blocker_codes = {item["code"] for item in audit["findings"]["blockers"]}
    assert "s2_5_corenlp_contract_verified" in pass_codes
    assert "s2_5_corenlp_runtime_ready" in pass_codes
    assert "s2_4_local_research_use_ready" in pass_codes
    assert "s2_4_license_gate_blocked" not in blocker_codes
    assert "s2_5_corenlp_runtime_missing" not in blocker_codes
    assert "s2_6_canonical_b0_composition_verified" in pass_codes
    assert "b0_paper_faithful_components_present" in pass_codes
    assert "sun_stage2_baseline_not_paper_faithful" not in blocker_codes
    assert audit["integrity_pass"] is True
    assert audit["s2_5_verified"] is True

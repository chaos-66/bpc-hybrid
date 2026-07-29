from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bpc_hybrid.stage2_canonical import validate_canonical
from bpc_hybrid.sun_style.sun_b0 import (
    ModalityPrediction,
    SunB0CompositionError,
    build_canonical_record,
    load_s26_config,
    locked_synthetic_inputs,
)
from formal_experiment.audit import collect_project_audit
from formal_experiment.s2_6_gate import (
    S26_EXPECTATIONS,
    S26Expectations,
    verify_s2_6_gate,
)
from formal_experiment.status import collect_status


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "models" / "sun_b0_s26.json"


def test_s2_6_config_locks_components_and_no_llm_boundary() -> None:
    config = load_s26_config(CONFIG)
    assert config["classifier"]["test_evaluation_repeated_by_s2_6"] is False
    assert config["phrase_extractor"]["inference_language"] == "en"
    assert config["classifier"]["inference_language"] == "de"
    assert len(config["verification"]["classifier_input_texts_de"]) == 1
    assert config["verification"][
        "classifier_and_phrase_inputs_are_language_aligned_parallel_synthetic_texts"
    ] is True
    assert config["safety"]["llm_api_called"] is False
    assert config["safety"]["test_split_read_or_evaluated"] is False


def test_s2_6_builds_schema_valid_canonical_record_from_locked_s2_5_evidence() -> None:
    config = load_s26_config(CONFIG)
    source_text, annotation, cases = locked_synthetic_inputs(ROOT, config)
    record = build_canonical_record(
        sample_id="fixture-1",
        source_id="s25-fixture",
        source_text=source_text,
        annotation=annotation,
        phrase_cases=cases,
        predictions=[ModalityPrediction("obligation", 0.9)],
    )
    report = validate_canonical(record)
    assert report.schema_valid is True
    assert report.cross_field_valid is True
    clause = record["clauses"][0]
    assert clause["modality"]["label"] == "obligation"
    assert clause["modality"]["evidence"][0]["text"] == "shall"
    assert clause["conditions"][0]["text"] == "If notice is required"
    assert clause["constraints"][0]["text"] == "within 30 days"
    assert clause["actions"][0]["text"] == "file"
    assert clause["actors"][0]["text"] == "the company"
    assert clause["actor_action_map"] == [
        {
            "actor_id": "fixture-1.c1.actor.1",
            "action_id": "fixture-1.c1.action.1",
        }
    ]
    assert record["method"]["name"] == "sun_rule_only"


def test_s2_6_classifier_label_is_not_replaced_by_phrase_marker() -> None:
    config = load_s26_config(CONFIG)
    source_text, annotation, cases = locked_synthetic_inputs(ROOT, config)
    record = build_canonical_record(
        sample_id="fixture-2",
        source_id="s25-fixture",
        source_text=source_text,
        annotation=annotation,
        phrase_cases=cases,
        predictions=[ModalityPrediction("permission", 0.6)],
    )
    assert record["clauses"][0]["modality"]["label"] == "permission"
    assert record["clauses"][0]["modality"]["evidence"][0]["text"] == "shall"


def test_s2_6_rejects_tampered_phrase_token_offsets() -> None:
    config = load_s26_config(CONFIG)
    source_text, annotation, cases = locked_synthetic_inputs(ROOT, config)
    tampered = copy.deepcopy(cases)
    tampered[0]["fields"]["action"]["end"] = 99
    with pytest.raises(SunB0CompositionError, match="token span"):
        build_canonical_record(
            sample_id="fixture-3",
            source_id="s25-fixture",
            source_text=source_text,
            annotation=annotation,
            phrase_cases=tampered,
            predictions=[ModalityPrediction("obligation", 0.8)],
        )


def test_s2_6_rejects_safety_relaxation(tmp_path: Path) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    config["safety"]["llm_api_called"] = True
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(SunB0CompositionError, match="safety boundary"):
        load_s26_config(path)


def test_s2_6_exact_hash_gate_is_ready() -> None:
    gate = verify_s2_6_gate(ROOT)
    assert gate["ready"] is True
    assert gate["hashes"]["config"] == S26_EXPECTATIONS.config_sha256
    assert gate["hashes"]["manifest"] == S26_EXPECTATIONS.manifest_sha256
    assert gate["record_count"] == 1
    assert gate["schema_invalid"] == 0
    assert gate["cross_field_invalid"] == 0
    assert gate["classifier_input_language"] == "de"
    assert gate["canonical_source_language"] == "en"
    assert gate["performance_evaluation"] is False
    assert gate["llm_api_called"] is False


def test_s2_6_wrong_expected_hash_fails_closed() -> None:
    wrong = S26Expectations(config_sha256="0" * 64)
    gate = verify_s2_6_gate(ROOT, expectations=wrong)
    assert gate["ready"] is False
    assert "s2_6_config_hash_mismatch" in gate["blockers"]


def test_s2_6_status_and_audit_remove_only_the_composition_blocker() -> None:
    status = collect_status()
    assert status["s2_6_verified"] is True
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    blocker_codes = {item["code"] for item in audit["findings"]["blockers"]}
    assert "s2_6_canonical_b0_composition_verified" in pass_codes
    assert "b0_paper_faithful_components_present" in pass_codes
    assert "sun_stage2_baseline_not_paper_faithful" not in blocker_codes
    assert "annotation_freeze_pending" not in blocker_codes
    assert "s2_2_annotation_freeze_verified" in pass_codes
    assert audit["integrity_pass"] is True

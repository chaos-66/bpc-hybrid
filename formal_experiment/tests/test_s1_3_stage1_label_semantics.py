"""Regression tests for the S1.3 P0/P1 label-semantics contract."""

from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.stage1_label_semantics import (  # noqa: E402
    Stage1LabelError,
    canonical_process_record_sha256,
    load_label_contract,
    render_label_semantics,
    validate_label_semantics,
)
from bpc_hybrid.stage1_process import (  # noqa: E402
    load_stage1_contract,
    parse_bpmn_file,
)
from formal_experiment.s1_label_semantics_gate import (  # noqa: E402
    STAGE1_LABEL_EXPECTATIONS,
    verify_stage1_label_semantics_gate,
)
from formal_experiment.audit import collect_project_audit  # noqa: E402
from formal_experiment.status import collect_status  # noqa: E402


LABEL_CONFIG = ROOT / "configs" / "stage1_label_semantics_s13.json"
STRUCTURAL_CONFIG = ROOT / "configs" / "stage1_structural_s11_s14.json"
FIXTURE = ROOT / "tests" / "fixtures" / "stage1" / "s13_label_edge_cases.bpmn"


def _inputs() -> tuple[dict, dict]:
    label_contract = load_label_contract(LABEL_CONFIG)
    structural_contract = load_stage1_contract(STRUCTURAL_CONFIG)
    process_record = parse_bpmn_file(FIXTURE, contract=structural_contract)
    return label_contract, process_record


def _by_id(record: dict) -> dict[str, dict]:
    return {item["activity_id"]: item for item in record["activities"]}


def test_s13_contract_freezes_two_nonlearned_synthetic_baselines() -> None:
    contract = load_label_contract(LABEL_CONFIG)
    assert contract["task_ids"] == ["S1.3"]
    assert set(contract["baselines"]) == {"P0", "P1"}
    assert contract["baselines"]["P1"]["lemmatization"] is False
    assert contract["baselines"]["P1"]["part_of_speech_tagging"] is False
    assert contract["safety"]["learned_model_used"] is False
    assert contract["safety"]["performance_evaluation"] is False


def test_p0_preserves_context_and_never_infers_semantics() -> None:
    contract, process_record = _inputs()
    record = render_label_semantics(process_record, baseline="P0", contract=contract)
    assert validate_label_semantics(
        record, process_record=process_record, contract=contract
    ).valid
    assert record["method"]["baseline"] == "P0"
    assert all(item["label_status"] == "raw_only" for item in record["activities"])
    assert all(item["actor_status"] == "p0_not_inferred" for item in record["activities"])
    assert all(item["actor_surface"] is None for item in record["activities"])
    assert all(item["action_surface"] is None for item in record["activities"])
    assert all(item["business_object_surface"] is None for item in record["activities"])


def test_p1_surface_split_handles_actor_and_label_edge_cases() -> None:
    contract, process_record = _inputs()
    record = render_label_semantics(process_record, baseline="P1", contract=contract)
    items = _by_id(record)
    assert items["Task_Punct"]["action_surface"] == "Approve"
    assert items["Task_Punct"]["business_object_surface"] == "claim request"
    assert items["Task_Single"]["label_status"] == "parsed_action_only"
    assert items["Task_Empty"]["label_status"] == "empty_label"
    assert items["Task_Unparseable"]["label_status"] == "unparsed_label"
    assert items["Task_NoLane"]["actor_status"] == "no_lane_label"
    assert items["Task_Ambiguous"]["actor_status"] == "ambiguous_lane_labels"
    assert items["Task_Ambiguous"]["actor_surface"] is None


def test_process_binding_uses_stable_canonical_json_hash() -> None:
    contract, process_record = _inputs()
    p0 = render_label_semantics(process_record, baseline="P0", contract=contract)
    p1 = render_label_semantics(process_record, baseline="P1", contract=contract)
    digest = canonical_process_record_sha256(process_record)
    assert p0["process_record"]["sha256"] == digest
    assert p1["process_record"]["sha256"] == digest
    reordered_mapping = dict(reversed(list(process_record.items())))
    assert canonical_process_record_sha256(reordered_mapping) == digest


def test_schema_and_cross_field_tampering_fail_closed() -> None:
    contract, process_record = _inputs()
    record = render_label_semantics(process_record, baseline="P1", contract=contract)
    extra = copy.deepcopy(record)
    extra["unexpected"] = True
    assert validate_label_semantics(
        extra, process_record=process_record, contract=contract
    ).schema_valid is False
    tampered = copy.deepcopy(record)
    _by_id(tampered)["Task_Punct"]["action_surface"] = "Reject"
    report = validate_label_semantics(
        tampered, process_record=process_record, contract=contract
    )
    assert report.schema_valid is True
    assert report.cross_field_valid is False


def test_unknown_baseline_and_invalid_process_record_are_rejected() -> None:
    contract, process_record = _inputs()
    with pytest.raises(Stage1LabelError, match="unknown S1.3 baseline"):
        render_label_semantics(process_record, baseline="P2", contract=contract)
    invalid = copy.deepcopy(process_record)
    invalid["activities"].reverse()
    with pytest.raises(Stage1LabelError, match="invalid upstream Process Record"):
        render_label_semantics(invalid, baseline="P1", contract=contract)


def test_s13_runner_is_offline_fixture_only() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_stage1_label_semantics.py")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert '"P0"' in completed.stdout and '"P1"' in completed.stdout
    refused = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_stage1_label_semantics.py"),
            "--bpmn",
            str(ROOT / "configs" / "stage1_label_semantics_s13.json"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert refused.returncode == 2
    assert "restricted to synthetic Stage 1 fixtures" in refused.stdout


def test_s13_exact_hash_gate_is_ready_and_wrong_hash_fails() -> None:
    gate = verify_stage1_label_semantics_gate(ROOT)
    assert gate["ready"] is True
    assert gate["synthetic_fixture_only"] is True
    assert gate["performance_evaluation"] is False
    failed = verify_stage1_label_semantics_gate(
        ROOT,
        expectations=replace(STAGE1_LABEL_EXPECTATIONS, config_sha256="0" * 64),
    )
    assert failed["ready"] is False
    assert "stage1_label_config_hash_mismatch" in failed["blockers"]


def test_status_and_audit_surface_verified_s13_without_formal_claim() -> None:
    status = collect_status()
    audit = collect_project_audit()
    pass_codes = {item["code"] for item in audit["findings"]["passes"]}
    assert status["stage1_label_semantics_verified"] is True
    assert "stage1_label_semantics_p0_p1_verified" in pass_codes
    # 2026-08-11: fail-closed final-gate conditions really satisfied
    # (three verified capsules / comparison consistent / G0.4
    # authorized) -> final gate open.
    assert status["final_experiment_ready"] is True

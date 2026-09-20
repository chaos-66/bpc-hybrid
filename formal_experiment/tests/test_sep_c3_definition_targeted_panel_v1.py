# -*- coding: utf-8 -*-
"""Focused offline tests for the frozen SEP-C3 definition targeted panel.

No model or network call is performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402
import build_sep_c3_definition_targeted_panel_v1 as builder  # noqa: E402
import prepare_sep_c3_definition_targeted_execution_v1 as prep  # noqa: E402
import run_sep_c3_definition_targeted_refinement_v1 as runner  # noqa: E402


PANEL_PATH = prep.PANEL_PATH
PANEL_MANIFEST_PATH = prep.PANEL_MANIFEST_PATH
BUDGET_PATH = prep.BUDGET_PATH
EVALUATION_CONTRACT_PATH = prep.EVALUATION_CONTRACT_PATH
OFFLINE_REQUESTS_PATH = prep.OFFLINE_REQUESTS_PATH
LEAKAGE_AUDIT_PATH = (
    ROOT / "outputs" / "reports"
    / "sep_c3_definition_targeted_leakage_audit_v1.json"
)
AUTHORIZATION_REQUEST_PATH = prep.AUTHORIZATION_REQUEST_PATH


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_panel_builder_matches_frozen_files_and_counts():
    built = builder.build_panel(write=False)
    panel = _read_json(PANEL_PATH)
    assert built["panel"] == panel
    assert panel["status"] == "FROZEN_BEFORE_NEW_API"
    accounting = panel["panel_accounting"]
    assert accounting["unique_sample_count_N"] == 42
    assert accounting["unique_selected_clause_count"] == 45
    assert accounting["sum_of_slice_clause_counts_before_dedup"] == 48
    assert accounting["definition_case_count"] == 25
    assert accounting["non_definition_case_count"] == 20
    assert accounting["expected_api_calls"] == {
        "A_existing_read_only": 0,
        "BASE": 42,
        "R_DEF": 42,
        "total_new": 84,
    }
    manifest = _read_json(PANEL_MANIFEST_PATH)
    assert manifest["panel_sha256"] == hashlib.sha256(
        PANEL_PATH.read_bytes()
    ).hexdigest()
    assert manifest["prompt_hashes"]["A"]["composition_sha256"] == (
        rp.render_refinement_prompt("A").composition_sha256
    )


def test_slices_have_exact_requested_composition():
    gold = _read_json(builder.GOLD_PATH)
    clauses = builder._flatten_gold(gold)
    a = builder._select_slice_a(clauses)
    b = builder._select_slice_b(clauses)
    c = builder._select_slice_c(clauses)
    d = builder._select_slice_d(clauses)
    assert len(a) == 15
    assert all(row["modality"] == "definition" for row in a)
    assert all(builder._contains_shall(row["text"]) for row in a)
    assert len(b) == 15
    assert dict(Counter(row["modality"] for row in b)) == {
        "obligation": 6,
        "prohibition": 6,
        "permission": 3,
    }
    assert len(c) == 12
    assert dict(Counter(row["modality"] for row in c)) == {
        "definition": 7,
        "obligation": 4,
        "permission": 1,
    }
    assert len(d) == 6
    assert all(row["modality"] == "definition" for row in d)
    assert all(not builder._contains_shall(row["text"]) for row in d)


def test_dedup_and_overlap_accounting_are_deterministic():
    built = builder.build_panel(write=False)["panel"]
    assert built["pairwise_sample_overlap"] == {
        "A&B": 0,
        "A&B&C&D": 0,
        "A&C": 2,
        "A&D": 0,
        "B&C": 0,
        "B&D": 0,
        "C&D": 3,
    }
    assert built["pairwise_unique_clause_overlap"] == {
        "A&B": 0,
        "A&B&C&D": 0,
        "A&C": 1,
        "A&D": 0,
        "B&C": 0,
        "B&D": 0,
        "C&D": 2,
    }
    assert sorted(
        (
            row["sample_id"],
            row["clause_id"],
            tuple(row["slices"]),
        )
        for row in built["clause_keys_in_multiple_slices"]
    ) == [
        ("estg_000209", "c2", ("C", "D")),
        ("estg_000218", "c1", ("C", "D")),
        ("estg_000664", "c1", ("A", "C")),
    ]


def test_prompt_hashes_and_only_intended_prompt_differences():
    active_a = rp.render_refinement_prompt("A")
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")
    assert base.system_prompt == active_a.system_prompt
    assert rdef.system_prompt == base.system_prompt + "\n\n" + dr.R_DEF_TEXT
    assert base.user_prompt_template == rdef.user_prompt_template
    assert dr.OLD_E4_BLOCK not in dr.expected_candidate_e_text()
    assert dr.NEW_E4_BLOCK in dr.expected_candidate_e_text()


def test_offline_request_capsule_is_frozen_and_gold_free():
    rows = _read_jsonl(OFFLINE_REQUESTS_PATH)
    assert len(rows) == 84
    assert {row["arm"] for row in rows} == {"BASE", "R_DEF"}
    assert len({row["sample_id"] for row in rows}) == 42
    for row in rows:
        body = row["request_body"]
        assert set(body) == {
            "model",
            "messages",
            "temperature",
            "top_p",
            "max_tokens",
            "stream",
            "thinking",
        }
        blob = json.dumps(body, ensure_ascii=False)
        assert re.search(r"estg_\d+_c\d+", blob) is None
        assert re.search(r"estg_\d+_sp\d+", blob) is None
    by_key = {(row["sample_id"], row["arm"]): row for row in rows}
    for sample_id in {row["sample_id"] for row in rows}:
        base = by_key[(sample_id, "BASE")]["request_body"]
        rdef = by_key[(sample_id, "R_DEF")]["request_body"]
        assert base["messages"][1] == rdef["messages"][1]
        assert rdef["messages"][0]["content"] == (
            base["messages"][0]["content"] + "\n\n" + dr.R_DEF_TEXT
        )


def test_budget_is_frozen_to_same_84_call_two_arm_scope():
    budget = _read_json(BUDGET_PATH)
    assert budget["planned_calls"] == 84
    assert budget["call_cap"] == 84
    assert budget["calls_per_arm"] == {"BASE": 42, "R_DEF": 42}
    assert budget["inference"]["retry"] == 0
    assert budget["inference"]["temperature"] == 0.0
    assert budget["inference"]["top_p"] == 1.0
    assert budget["inference"]["max_tokens"] == 4096
    assert budget["total_max_output_tokens"] == 84 * 4096
    assert budget["usd_cost_cap"] > 0
    assert budget["price_snapshot"]["input_cache_miss_per_million"] == 1.32
    assert budget["price_snapshot"]["output_per_million"] == 3.96


def test_evaluation_contract_freezes_required_rules():
    contract = _read_json(EVALUATION_CONTRACT_PATH)
    assert contract["gold_read_timing"] == (
        "after_predictions_are_frozen_and_hashed"
    )
    assert contract["evaluation_units"]["primary_targeted_clause_set"][
        "clause_count"
    ] == 45
    assert "definition_f1" in contract["primary_targeted_metrics"]["modality"]
    assert (
        "confusion_definition_to_obligation_count"
        in contract["primary_targeted_metrics"]["modality"]
    )
    assert contract["ambiguity_policy"][
        "apply_applies_family_status"
    ] == "NEEDS_GOLD_ADJUDICATION"
    assert any(
        "Do not average modality accuracy and span-field F1." == rule
        for rule in contract["arithmetic_rules"]
    )
    assert any(
        "Do not make significance claims" in rule
        for rule in contract["arithmetic_rules"]
    )


def test_leakage_audit_documents_strict_sample_id_residual():
    audit = _read_json(LEAKAGE_AUDIT_PATH)
    checks = audit["checks"]
    assert checks["r_def_no_full_estg_sample_or_clause_text"]["status"] == "pass"
    assert checks["r_def_no_long_estg_shingles"]["status"] == "pass"
    assert checks["synthetic_e4_not_copied_from_estg"]["status"] == "pass"
    assert checks["no_concrete_sample_id_in_prompt_templates"]["status"] == "pass"
    assert checks["offline_requests_no_gold_ids_or_annotations"]["status"] == "pass"
    assert (
        checks["strict_no_concrete_sample_id_in_rendered_model_prompt"]["status"]
        == "fail"
    )
    assert audit["status"] == "BLOCKED_STRICT_LEAKAGE_CHECK"
    assert audit["blocking_checks"] == [
        "strict_no_concrete_sample_id_in_rendered_model_prompt"
    ]


def test_generated_authorization_request_is_not_an_authorization_event():
    request = _read_json(AUTHORIZATION_REQUEST_PATH)
    assert request["suite_id"] == prep.SUITE_ID
    assert request["new_calls"] == 84
    assert request["decision"] == "BLOCKED_NO_MATCHING_AUTHORIZATION"
    allowed, reason = runner._authorization_ok(AUTHORIZATION_REQUEST_PATH)
    assert allowed is False
    assert reason
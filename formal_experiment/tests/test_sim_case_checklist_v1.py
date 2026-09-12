# -*- coding: utf-8 -*-
"""Focused checks for the Case C (SIM) checklist capsule (S3.9-EXT-REAL-CASE, C0).

Scope of this file:

* the builder is answer-independent: it never reads the external answer key on
  the prediction path, and the taxonomy reading aid is never used to synthesise
  an expected result;
* every input is hash-bound, the coverage is complete, and the empty-text
  requirement versions are excluded from detection input;
* the committable summary contains no restricted corpus text (>= 40 characters);
* the stored artifacts exist and their recorded hashes match the files on disk.

Nothing here runs Stage 3 inference, loads a model, or calls any API.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import build_sim_case_checklist_v1 as builder  # noqa: E402

LOCAL_DIR = ROOT / "outputs/development/sim_case_c1"
REPORT_JSON = ROOT / "outputs/reports/sim_case_c1_checklist.json"
REPORT_MD = ROOT / "outputs/reports/sim_case_c1_checklist.md"

EXPECTED_PREFIXES = {
    "bpmn": "338c8144",
    "requirements": "e13d9a2a",
    "step3": "96b3c1e8",
}


@pytest.fixture(scope="module")
def doc() -> dict:
    return builder.build()


# ---------------------------------------------------------------------------
# 1. input binding
# ---------------------------------------------------------------------------

def test_inputs_exist_and_hashes_match_recorded_prefixes(doc):
    inputs = doc["inputs"]
    assert inputs["process_model"]["sha256"].startswith(EXPECTED_PREFIXES["bpmn"])
    assert inputs["requirements"]["sha256"].startswith(EXPECTED_PREFIXES["requirements"])
    assert inputs["step_3_baseline"]["sha256"].startswith(EXPECTED_PREFIXES["step3"])
    for key, meta in inputs.items():
        if key == "predictions_repeats":
            assert len(meta) == 5
            continue
        assert (builder.REPO / meta["path"]).exists(), key
    for meta in inputs["predictions_repeats"]:
        assert (builder.REPO / meta["path"]).exists()


def test_references_are_read_only_inputs_not_copies(doc):
    """The BPMN and requirement file are read in place from references/."""
    assert doc["inputs"]["process_model"]["path"].startswith("references/")
    assert doc["inputs"]["requirements"]["path"].startswith("references/")
    assert not (ROOT / "data/input/sim_case").exists()


# ---------------------------------------------------------------------------
# 2. binding policy and coverage
# ---------------------------------------------------------------------------

def test_coverage_is_complete_and_empty_text_entries_excluded(doc):
    coverage = doc["coverage"]
    assert coverage["curated_items"] == 6
    assert coverage["main_denominator_size"] == 5
    assert coverage["main_denominator"] == ["r10", "r11", "r13", "r8", "r9"]
    assert coverage["main_denominator_matches"] is True
    assert coverage["background_items"] == ["r12"]
    assert coverage["external_deviations_total"] == 6
    assert coverage["empty_text_entries"] == ["r12/v2", "r9/v1"]
    assert coverage["excluded_from_detection"] == ["r12/v2", "r9/v1"]

    plan = doc["detection_plan"]
    assert sorted(plan["main_denominator"]) == ["r10/v2", "r11/v2", "r13/v2", "r8/v2", "r9/v2"]
    assert plan["background_items"] == ["r12"]
    assert plan["role_binding"] == {"Data Controller": "Phone company", "Data Subject": "Customer"}
    assert doc["run_results"] is None  # the checklist never fabricates (3)(4)(5)


def test_reference_judgments_are_detector_independent(doc):
    check = doc["reference_policy_check"]
    assert check["capability_conditioned_fields"] == 0
    assert check["gold_claims"] == 0
    for item in doc["items"]:
        judgment = item["dev_reference_judgment"]
        assert judgment["is_gold"] is False
        assert judgment["sources"], item["rule_id"]
        assert item["semantic_issue"]["summary_zh"]
        assert "proposed_expected" not in item and "capability" not in item
    by_rule = {i["rule_id"]: i["dev_reference_judgment"]["judgment"] for i in doc["items"]}
    assert by_rule == {"r8": "issue_present", "r9": "issue_present", "r10": "issue_present",
                       "r11": "issue_present", "r13": "issue_present_with_premise",
                       "r12": "background_only"}
    r13 = [i for i in doc["items"] if i["rule_id"] == "r13"][0]
    assert r13["dev_reference_judgment"]["premise_zh"]
    assert "连线标签" in r13["dev_reference_judgment"]["premise_zh"]


def test_numeric_boundary_policy_is_explicit(doc):
    policy = doc["binding_policy"]["numeric_boundary_policy_r13"]
    assert policy["difference_interval"].startswith("50 < debt < 100")
    r13 = [i for i in doc["items"] if i["rule_id"] == "r13"][0]
    assert r13["semantic_issue"]["evidence"]["example_value"] == 75
    assert r13["semantic_issue"]["evidence"]["difference_interval"] == "50 < debt < 100"
    assert "does not trigger" in policy["natural_language_meaning"]
    assert "NOT adopted" in policy["external_suggestion"]
    assert policy["executable_condition_expression"].startswith("absent")


# ---------------------------------------------------------------------------
# 3. process-model facts used by the checklist
# ---------------------------------------------------------------------------

def test_process_model_facts_match_evidence(doc):
    counts = doc["process_structure"]["counts"]
    assert counts["timer_event_definitions"] == 0
    assert counts["boundary_events"] == 0
    assert counts["condition_expressions"] == 0
    assert counts["labelled_flows"] == 4

    labels = sorted(f["label"] for f in doc["process_structure"]["labelled_flows"])
    assert labels == ["Debt < 100", "Granted", "Not requested", "Requested"]
    numeric = [f for f in doc["process_structure"]["labelled_flows"] if "Debt" in f["label"]]
    assert len(numeric) == 1 and numeric[0]["target"] == "Ask portability"

    consent = doc["process_structure"]["consent_position_evidence"]
    assert consent["activity_present"] is True
    assert consent["preceded_by_store_data"] is True
    assert "Store Data" in consent["predecessors"]

    lanes = {lane["process"]: lane["elements"] for lane in doc["process_structure"]["lanes"]}
    assert "Activate SIM card" in lanes["Customer"]
    assert "Ask for consent" in lanes["Phone company"]


# ---------------------------------------------------------------------------
# 4. prediction reuse audit
# ---------------------------------------------------------------------------

def test_prediction_reuse_counts_and_repeat_handling(doc):
    reuse = doc["prediction_reuse"]
    assert reuse["independent_inputs"] == 10
    assert reuse["repeat_count"] == 5
    assert reuse["total_rows"] == 50
    assert reuse["order_relations_total_all_rows"] == 0
    assert reuse["repeats_identical"] is True
    assert reuse["independent_inputs"] == len(reuse["sample_ids"])
    assert not any(sid.endswith("/r9/v1") or sid.endswith("/r12/v2") for sid in reuse["sample_ids"])


def test_prediction_path_never_reads_the_answer_key():
    """The prediction parser must not touch the external deviation file."""
    source = inspect.getsource(builder.parse_predictions)
    for forbidden in ("STEP3", "step_3", "deviations", "mitigation", "bpmn_element"):
        assert forbidden not in source, forbidden


# ---------------------------------------------------------------------------
# 5. reading aid is not a scoring key
# ---------------------------------------------------------------------------

def test_reading_aid_is_only_a_documented_aid(doc):
    assert "READING AID ONLY" in doc["taxonomy_reading_aid_boundary"]
    for item in doc["items"]:
        blob = json.dumps(item["dev_reference_judgment"], ensure_ascii=False) + \
            json.dumps(item["semantic_issue"], ensure_ascii=False)
        for value in doc["taxonomy_reading_aid"].values():
            assert value not in blob
        for dev in item["external_annotation_source"]["deviations"]:
            assert dev["reading_aid"] in set(doc["taxonomy_reading_aid"].values()) | {"未映射"}


def test_open_questions_replaced_by_recorded_source_conflicts(doc):
    assert doc["open_questions"] == []
    noted = {entry["rule_id"] for entry in doc["unresolved_source_notes"]}
    assert noted == {"r9", "r11", "r12", "r13"}
    r11 = [i for i in doc["items"] if i["rule_id"] == "r11"][0]
    assert "missing_vs_misplaced" in {c["kind"] for c in r11["conflicts"]}


def test_paper_conflict_record_keeps_both_readings(doc):
    record = doc["paper_conflict_record"]
    assert "R2 = out-of-order" in record["reading_text"]
    assert "V4/R4 = Out-of-order Execution" in record["reading_figure"]
    assert "R2 and R4 are swapped" in record["difference"]
    assert record["version_of_record_status"].startswith("not_obtainable")
    assert "neither" in record["handling"] and "Gold" in record["handling"]


# ---------------------------------------------------------------------------
# 6. restricted-text guard
# ---------------------------------------------------------------------------

def test_committable_payload_has_no_restricted_text(doc):
    committable = builder.to_committable(doc)
    corpus = builder.build_restricted_corpus(
        builder.parse_requirements(builder.REQUIREMENTS), builder.parse_step3(builder.STEP3)
    )
    guard = builder.assert_no_restricted_text(
        builder.render_report_md(doc) + json.dumps(committable, ensure_ascii=False), corpus
    )
    assert guard["hits"] == []
    assert guard["restricted_windows_checked"] == len(corpus)


def test_committable_items_drop_full_requirement_text(doc):
    committable = builder.to_committable(doc)
    for item in committable["items"]:
        for version in item["requirement_versions"]:
            assert "text" not in version
    local_texts = [rv["text"] for item in doc["items"] for rv in item["requirement_versions"] if rv["text"]]
    assert local_texts  # the local capsule keeps the full text


# ---------------------------------------------------------------------------
# 7. determinism and no-overwrite
# ---------------------------------------------------------------------------

def test_rebuild_is_deterministic(doc):
    again = builder.build()
    assert json.dumps(builder.to_committable(doc), ensure_ascii=False, sort_keys=True) == \
        json.dumps(builder.to_committable(again), ensure_ascii=False, sort_keys=True)


def test_write_refuses_to_overwrite(tmp_path):
    target = tmp_path / "artifact.json"
    builder.write(target, "{}\n", overwrite=False)
    with pytest.raises(SystemExit):
        builder.write(target, "{}\n", overwrite=False)
    builder.write(target, '{"a": 1}\n', overwrite=True)
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}


# ---------------------------------------------------------------------------
# 8. stored artifacts match the manifest
# ---------------------------------------------------------------------------

def test_stored_artifacts_exist_and_match_manifest():
    assert REPORT_JSON.exists() and REPORT_MD.exists()
    assert (LOCAL_DIR / "checklist.json").exists() and (LOCAL_DIR / "manifest.json").exists()
    manifest = json.loads((LOCAL_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["api_calls"] == 0
    assert manifest["network"] is False
    for name, meta in manifest["outputs"].items():
        path = builder.REPO / meta["path"]
        assert path.exists(), name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == meta["sha256"], name
    assert manifest["restricted_text_guard"]["hits"] == []

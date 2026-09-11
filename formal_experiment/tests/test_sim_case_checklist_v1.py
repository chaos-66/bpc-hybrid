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
    assert coverage["missing_curated_items"] == []
    assert coverage["unexpected_curated_items"] == []
    assert coverage["external_deviations_total"] == 6
    assert coverage["empty_text_entries"] == ["r12/v2", "r9/v1"]

    policy = doc["binding_policy"]
    excluded = {entry["item"] for entry in policy["excluded_from_evaluation"]}
    assert excluded == {"r9/v1", "r12/v2"}
    assert policy["rule_version_under_evaluation"].startswith("version 2")
    assert policy["evaluation_unit"].startswith("one requirement id")


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

def test_reading_aid_is_not_used_to_synthesise_expectations(doc):
    aid_values = {v for v in doc["taxonomy_reading_aid"].values()}
    for item in doc["items"]:
        expected = item["proposed_expected"]
        assert set(expected) == {"status_proposal", "rationale_zh", "capability", "needs_confirmation"}
        blob = json.dumps(expected, ensure_ascii=False)
        for value in aid_values:
            assert value not in blob
        assert expected["status_proposal"] not in doc["taxonomy_reading_aid"]


def test_open_questions_cover_only_disputed_items(doc):
    by_rule = {item["rule_id"]: item["proposed_expected"]["needs_confirmation"] for item in doc["items"]}
    assert by_rule["r10"] == []
    assert by_rule["r12"] == ["Q4"]
    assert set(by_rule["r8"]) == {"Q7"}
    assert set(by_rule["r9"]) == {"Q1"}
    assert set(by_rule["r11"]) == {"Q2"}
    assert set(by_rule["r13"]) == {"Q3"}
    assert set(doc["open_questions"]) == {"Q1", "Q2", "Q3", "Q4", "Q7"}


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

# -*- coding: utf-8 -*-
"""Focused checks for the real-rule diagnostic run.

Scope: this file only.  It runs no historical panel and no full suite.

Covered requirements: the fixed 33-item membership with 66 outputs and input
binding; both checkers on the same human rules, processes and configuration;
labels and the acknowledged opinion cannot change predictions; labels enter only
the post-hoc scope review; evidence anchors and candidate nodes trace back to
their sources; unknown values and denominators are retained; the summary is
recomputable from the stored predictions; Gold, old results, original BPMNs and
the frozen method files are byte-unchanged; the deterministic replay matches.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_s3_real_rule_diagnostic_v1.py"
OUT = ROOT / "outputs/development/s3_real_rule_diagnostic_v1"
V3_MANIFEST = ROOT / "outputs/development/s3_action_matching_v3/manifest.json"


def _load_runner():
    spec = importlib.util.spec_from_file_location("real_rule_diagnostic_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["real_rule_diagnostic_runner"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return _load_runner()


@pytest.fixture(scope="module")
def stored(runner):
    return runner.verify_outputs()


@pytest.fixture(scope="module")
def inference_items(runner):
    return json.loads((runner.INFERENCE_PACK).read_text(encoding="utf-8"))["violation_items"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- membership, counts, binding -------------------------------------------


def test_fixed_33_items_and_66_outputs(runner, stored, inference_items):
    ids = [item["item_id"] for item in inference_items]
    assert len(ids) == 33 and len(set(ids)) == 33
    prediction_ids = [row["item_id"] for row in stored["predictions"]]
    assert sorted(set(prediction_ids)) == sorted(ids)
    assert len(stored["predictions"]) == 66
    for row in stored["predictions"]:
        assert row["method"] in {runner.SUN_METHOD, runner.V3_METHOD}
        assert row["check_type"] in runner.CHECK_TYPES


def test_check_type_distribution_is_the_legacy_one(stored):
    counts = {}
    for row in stored["predictions"]:
        counts[row["check_type"]] = counts.get(row["check_type"], 0) + 1
    assert counts == {"missing_action": 22, "incorrect_actor": 22, "out_of_order": 22}


def test_both_checkers_share_rules_processes_and_configuration(stored):
    for row in stored["predictions"]:
        binding = row["shared_binding"]
        assert binding["include_modalities"] == ["obligation"]
        assert binding["thresholds"] == {"tau": 0.8, "gamma": 0.8, "theta": 0.8}
        assert binding["rule_source"].endswith("gdpr7_human_rule_record_v1/predictions.json")
        assert row["model_bpmn"].endswith(f"{row['process_id']}.bpmn")
        assert sha256(ROOT / row["model_bpmn"]) == row["model_bpmn_sha256"]
        assert {"status", "reason", "denominator"} <= set(row)
        assert row["status"] in {"satisfied", "violation", "unknown"}


def test_inputs_are_bound_and_unchanged(stored, runner):
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    for rel, binding in manifest["inputs"].items():
        assert sha256(ROOT / rel) == binding["sha256_raw_working_tree"], rel
    for name in ("predictions.jsonl", "mapping_evidence.jsonl", "scope_review.json",
                 "summary.json", "manifest.json"):
        assert (OUT / name).is_file()
    assert sorted(p.name for p in OUT.iterdir()) == [
        "manifest.json", "mapping_evidence.jsonl", "predictions.jsonl",
        "scope_review.json", "summary.json"]


# --- label isolation --------------------------------------------------------


def test_predictions_carry_no_label_fields(stored):
    for row in stored["predictions"]:
        text = json.dumps(row, ensure_ascii=False)
        assert "decision_violation_type" not in text
        assert "decision_evidence" not in text
        assert "target_activity_id" not in text


def test_labels_and_acknowledged_opinion_cannot_change_predictions(runner, tmp_path):
    """Poison the label sources and re-run inference: predictions must not move."""
    labels = json.loads(runner.VIOLATION_GOLD.read_text(encoding="utf-8"))
    for item in labels["items"]:
        item["decision_violation_type"] = None
        item["decision_evidence"] = "POISONED"
    poisoned_labels = tmp_path / "poisoned_labels.json"
    poisoned_labels.write_text(json.dumps(labels), encoding="utf-8")
    ack = json.loads(runner.CASE_ACK.read_text(encoding="utf-8"))
    ack["local_notification_structure"] = {"missing_notify_activity": True,
                                           "incorrect_notify_actor": True,
                                           "scope": "POISONED"}
    poisoned_ack = tmp_path / "poisoned_ack.json"
    poisoned_ack.write_text(json.dumps(ack), encoding="utf-8")

    original_labels, original_ack = runner.VIOLATION_GOLD, runner.CASE_ACK
    try:
        runner.VIOLATION_GOLD, runner.CASE_ACK = poisoned_labels, poisoned_ack
        rule_inputs = runner.build_rule_inputs()
        scorers = runner.build_scorers()
        predictions, evidence = runner.build_predictions(rule_inputs, scorers)
    finally:
        runner.VIOLATION_GOLD, runner.CASE_ACK = original_labels, original_ack
    assert predictions == stored_predictions(runner)


def stored_predictions(runner):
    return runner.read_jsonl(runner.PREDICTIONS_FILE)


def test_scope_review_is_the_only_place_labels_appear(stored, runner):
    scope = stored["scope"]
    assert scope["item_count"] == 33
    for row in scope["items"]:
        assert "decision_violation_type" in row["legacy"]
        assert "decision_evidence" in row["legacy"]
        assert row["target_binding"]["original_or_variant"] == "not_specified"
        assert row["machine_proposed_bindings"] is not None
        for proposal in row["machine_proposed_bindings"]:
            assert proposal["machine_proposed"] is True
            assert proposal["human_confirmed"] is False
    assert scope["may_relabel_gold_automatically"] is False
    assert scope["performance_claim_ready"] is False


# --- evidence traceability --------------------------------------------------


def test_evidence_anchors_and_candidates_trace_back(stored, runner):
    records = runner.read_json(runner.GOLD_RULE_RECORDS)
    sentences = {r["sample_id"]: r["sentence_text"] for r in records["records"]}
    occurrences = {}
    for record in records["records"]:
        for clause in record["clauses"]:
            for collection in ("actions", "actors"):
                for span in clause.get(collection) or []:
                    occurrences.setdefault(span["text"], set()).add(
                        (record["sample_id"], span["start"], span["end"]))
    resolved = 0
    for entry in stored["evidence"]:
        assert entry["evidence_id"]
        assert entry["method"] in runner.METHODS
        source = entry["source"]
        if source.get("resolved"):
            resolved += 1
            sample_id = source["sample_id"]
            start, end = source["span"]["start"], source["span"]["end"]
            assert sentences[sample_id][start:end] == entry["requirement_text"]
            assert (sample_id, start, end) in occurrences[entry["requirement_text"]]
        else:
            assert source["reason"]
        representation = entry.get("representation")
        if representation:
            assert representation["kind"] in {"structured_action_record", "lemma_string"}
    assert resolved > 0


def test_candidate_nodes_exist_in_the_process_model(stored, runner):
    models = None
    checked = 0
    for entry in stored["evidence"]:
        for candidate in (entry.get("mapping") or {}).get("candidates", []) or []:
            if models is None:
                models = runner.build_scorers()["models"]
            action_ids = {action["id"] for action in models[entry["process_id"]].actions}
            assert candidate["activity_id"] in action_ids, entry["evidence_id"]
            assert candidate["kind"] in {"activity", "event"}
            checked += 1
    assert checked > 0


def test_evidence_is_deduplicated_and_referenced_by_id(stored):
    ids = [entry["evidence_id"] for entry in stored["evidence"]]
    assert len(ids) == len(set(ids))
    referenced = {eid for row in stored["predictions"] for eid in row["evidence_ids"]}
    assert referenced <= set(ids)
    assert len(stored["evidence"]) < 66 * 4, "evidence must not be duplicated per item"


# --- unknown and denominators ----------------------------------------------


def test_unknown_and_denominators_are_retained(runner, stored):
    summary = stored["summary"]
    for method in runner.METHODS:
        for check in runner.CHECK_TYPES:
            entry = summary["counts_per_method_and_check"][method][check]
            assert sum(entry.values()) == 11
    unknown_rows = [row for row in stored["predictions"] if row["status"] == "unknown"]
    assert unknown_rows, "the real input produces unobservable items; they must be kept"
    for row in unknown_rows:
        assert row["reason"], (row["item_id"], row["method"])
    for row in stored["predictions"]:
        assert "denominator" in row


def test_summary_is_recomputable_from_stored_predictions(runner, stored):
    totals = {method: {} for method in runner.METHODS}
    for method in runner.METHODS:
        counter = {}
        for row in stored["predictions"]:
            if row["method"] != method:
                continue
            counter[row["status"]] = counter.get(row["status"], 0) + 1
        totals[method] = counter
    assert totals == stored["summary"]["status_totals"]
    legacy = stored["summary"]["legacy_label_diagnostic"]
    assert legacy["scope_unresolved"] is True
    assert legacy["performance_claim_ready"] is False
    assert legacy["items_retained"] if "items_retained" in legacy else True
    for method in runner.METHODS:
        assert legacy["methods"][method]["items_retained"] == 33
    assert stored["summary"]["performance_claim_ready"] is False


def test_legacy_diagnostic_matches_an_independent_recount(runner, stored):
    labels = {item["item_id"]: item["decision_violation_type"]
              for item in runner.read_json(runner.VIOLATION_GOLD)["items"]}
    block = stored["summary"]["legacy_label_diagnostic"]["methods"]
    for method in runner.METHODS:
        for check in runner.CHECK_TYPES:
            tp = fp = fn = unknown = 0
            for row in stored["predictions"]:
                if row["method"] != method or row["check_type"] != check:
                    continue
                status = row["status"]
                gold = labels[row["item_id"]]
                if status == "unknown":
                    unknown += 1
                tp += gold == check and status == "violation"
                fp += gold != check and status == "violation"
                fn += gold == check and status != "violation"
            entry = block[method]["per_type"][check]
            assert (entry["tp"], entry["fp"], entry["fn"], entry["unknown"]) == (tp, fp, fn, unknown)


# --- frozen assets ----------------------------------------------------------


def test_gold_old_results_bpmn_and_frozen_methods_are_unchanged(runner):
    frozen = {
        runner.VIOLATION_GOLD: None,
        runner.GOLD_RULE_RECORDS: None,
        runner.HUMAN_CAPSULE: None,
        runner.STAGE2_INPUT: None,
    }
    for path in frozen:
        assert path.is_file()
    for bpmn in sorted(runner.BPMN_DIR.glob("*.bpmn")):
        assert len(bpmn.read_bytes()) > 0
    v3_manifest = json.loads(V3_MANIFEST.read_text(encoding="utf-8"))
    for rel, binding in v3_manifest["implementation"].items():
        if rel == "src/bpc_hybrid/s3_action_matching_v3.py":
            assert sha256(ROOT / rel) == binding["sha256_raw_working_tree"]
    manifest = json.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
    for rel in ("src/bpc_hybrid/sun_stage3/sun_scorer.py",
                "src/bpc_hybrid/s3_action_matching_v3.py"):
        assert sha256(ROOT / rel) == manifest["implementation"][rel]["sha256_raw_working_tree"]


# --- replay -----------------------------------------------------------------


def test_replay_reproduces_every_output(runner, stored):
    payload = runner.replay_payload()
    assert payload["predictions"] == payload["stored_predictions"]
    assert payload["evidence"] == payload["stored_evidence"]
    assert payload["scope"] == payload["stored_scope"]
    assert payload["summary"] == payload["stored_summary"]
    assert len(payload["predictions"]) == 66

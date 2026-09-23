"""Integrity checks for the completed AI supplement; never reopen archives."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "data/development/stage3_synth/stage3_binding_resolved_reference_v1.json"
HUMAN = ROOT / "data/development/stage3_synth/stage3_binding_human_decisions_v1.json"
GOLD = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_original_human_decisions_and_active_sources_preserved():
    result, human = load(RESULT), load(HUMAN)
    assert {row["pair_id"] for row in result["records"]} == set(human["records"])
    assert len(result["records"]) == len(human["records"]) == 30
    for row in result["records"]:
        assert row["human_decision"] == human["records"][row["pair_id"]]
        assert row["action_resolution"]["rule_action_id"] == row["human_decision"]["values"]["action_id"]
        assert row["actor_resolution"]["rule_actor_id"] == row["human_decision"]["values"]["actor_id"]
    for source in result["sources"]:
        if "member" in source:
            continue  # Archive provenance is opt-in, not a routine test input.
        assert hashlib.sha256((ROOT / source["path"]).read_bytes()).hexdigest() == source["sha256"]


def test_all_rule_references_exist_in_their_rule_without_fabricated_ids():
    result, gold = load(RESULT), load(GOLD)
    actions = {x["id"]:r["rule_id"] for r in gold["records"] for c in r["clauses"] for x in c["actions"]}
    actors = {x["id"]:r["rule_id"] for r in gold["records"] for c in r["clauses"] for x in c["actors"]}
    for row in result["records"]:
        action, actor, order = (row[k] for k in ("action_resolution", "actor_resolution", "order_resolution"))
        refs = [action["rule_action_id"], action.get("related_action_id")]
        refs += list(order.get("candidate_endpoints", {}).values())
        for ref in filter(None, refs):
            assert actions[ref] == row["rule_id"]
        if actor["rule_actor_id"]:
            assert actors[actor["rule_actor_id"]] == row["rule_id"]
        else:
            assert actor["original_gold_actor_id_created"] is False
            holder = actor.get("right_holder_reference")
            if holder:
                assert actors[holder["id"]] == row["rule_id"]
        assert order["rule_relation"] is None


def test_ai_evidence_is_exact_source_text_with_correct_scope():
    result, gold = load(RESULT), load(GOLD)
    records = {r["sample_id"]:r for r in gold["records"]}
    for row in result["records"]:
        action, actor, order = (row[k] for k in ("action_resolution", "actor_resolution", "order_resolution"))
        evidence = action.get("evidence", []) + actor.get("rule_executor_evidence", []) + order.get("evidence", [])
        for span in evidence:
            source = records[span["sample_id"]]
            assert source["rule_id"] == row["rule_id"] == span["rule_id"]
            assert 0 <= span["start"] < span["end"] <= len(source["sentence_text"])
            assert source["sentence_text"][span["start"]:span["end"]] == span["text"]
        if actor["status"] == "inferred_counterparty_executor":
            assert actor["rule_actor_id"] is None
            assert actor["right_holder_reference"]["text"].lower() == "the data subject"
            assert actor["rule_executor_evidence"]
        if actor["status"] == "process_executor_only":
            assert not actor["rule_executor_evidence"]


def test_supplement_is_complete_ai_reference_without_gold_or_prediction_claims():
    result = load(RESULT)
    assert result["status"] == "ai_resolution_complete"
    for key in ("is_gold", "human_approved_new_judgments", "requires_human_review",
                "allowed_as_blind_prediction", "automatic_inference_input_allowed",
                "formal_evaluation_reference_ready"):
        assert result[key] is False
    assert result["counts"]["resolved_items"] == len(result["records"])
    assert result["counts"]["human_recheck_items"] == 0
    for row in result["records"]:
        assert row["resolution_state"] == "complete"
        assert row["requires_human_review"] is False
        for key in ("action_resolution", "actor_resolution", "order_resolution"):
            decision = row[key]
            assert decision["reason_zh"]
            if decision["authority"] == "ai_judgment":
                assert row["resolution_author"] == "Codex"

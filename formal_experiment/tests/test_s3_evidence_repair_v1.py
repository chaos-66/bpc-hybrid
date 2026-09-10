"""Independent synthetic checks; never tune the repair on GDPR labels."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from bpc_hybrid.s3_evidence_checks_v1 import (
    EvidenceChecks, evaluate_items, project_confirmed_temporal_notes, score_items,
)

ROOT = Path(__file__).resolve().parents[1]


class ExactSimilarity:
    def text_pair(self, left, right):
        return float(left.casefold() == right.casefold())


@pytest.fixture(scope="module")
def checker():
    import spacy
    return EvidenceChecks(ExactSimilarity(), 0.8, 0.8, 0.8, spacy.load("en_core_web_sm"))


def model(actions=None, owners=None, reachable=None, lanes=None, objects=None):
    actions = actions or [{"id": "a", "name": "Review invoice"}, {"id": "b", "name": "Archive invoice"}]
    return SimpleNamespace(actions=actions, record={"lanes": lanes or []},
        action_actor_names=owners or {a["id"]: ["Manager"] for a in actions},
        business_objects=objects or [], actors=["Manager"],
        is_reachable=lambda a, b: (a, b) in (reachable or []))


def test_long_action_matches_same_predicate_and_object(checker):
    match = checker.action_match("review the invoice for the annual accounts", model())
    assert match["mapped"] and match["best"]["activity_id"] == "a"
    assert match["best"]["strategy"] == "predicate_and_content"


def test_same_verb_different_recipient_not_forced_to_match(checker):
    m = model([{"id": "a", "name": "Notify authority"}])
    assert not checker.action_match("notify the customer", m)["mapped"]


def test_duplicate_action_labels_are_unknown(checker):
    m = model([{"id": "a", "name": "Review invoice"}, {"id": "b", "name": "Review invoice"}])
    assert checker.action_match("Review invoice", m)["reason"] == "ambiguous_action_mapping"
    assert checker.missing_action(["Review invoice"], m)["status"] == "unknown"


def test_matched_executor_is_satisfied_even_when_business_object_differs(checker):
    m = model(objects=[{"activity_id": "a", "object": "invoice"}])
    result = checker.incorrect_actor(["Review invoice"], ["Manager"], m)
    assert result["status"] == "satisfied" and result["score"] == 0


def test_wrong_executor_detected(checker):
    result = checker.incorrect_actor(["Review invoice"], ["Auditor"], model())
    assert result["status"] == "violation" and result["score"] == 1


def test_crossed_assignments_are_not_masked_by_global_actor_bag(checker):
    m = model(owners={"a": ["Clerk"], "b": ["Manager"]})
    result = checker.incorrect_actor(["Review invoice", "Archive invoice"], ["Manager", "Clerk"], m,
        [{"actor": "Manager", "action": "Review invoice"}, {"actor": "Clerk", "action": "Archive invoice"}])
    assert result["violations"] == 2


def test_lane_executor_takes_precedence_over_pool(checker):
    m = model(lanes=[{"name": "Clerk", "flow_node_refs": ["a"]}])
    assert checker.incorrect_actor(["Review invoice"], ["Manager"], m)["status"] == "violation"


def test_unmatched_action_does_not_become_actor_violation(checker):
    result = checker.incorrect_actor(["Deliver package"], ["Auditor"], model())
    assert result["status"] == "unknown" and result["score"] is None


def test_partial_actor_evidence_does_not_claim_all_satisfied(checker):
    result = checker.incorrect_actor(["Review invoice", "Deliver package"], ["Manager"], model(),
        [{"actor": "Manager", "action": "Review invoice"}, {"actor": "Manager", "action": "Deliver package"}])
    assert result["observable"] and not result["complete"]
    assert result["status"] == "unknown" and result["score"] is None


@pytest.mark.parametrize("relations,reason", [([], "missing_rule_order_relations"),
    ([("Receive parcel", "Review invoice")], "order_endpoint_unmapped"),
    ([("Review invoice", "Review invoice")], "order_endpoints_same_activity")])
def test_unavailable_order_never_returns_zero(checker, relations, reason):
    result = checker.out_of_order(relations, [], model())
    assert result["status"] == "unknown" and result["score"] is None
    assert result["reason"] == reason


@pytest.mark.parametrize("reachable,status", [([("a", "b")], "satisfied"),
    ([("b", "a")], "violation"), ([], "violation")])
def test_explicit_order_direction(checker, reachable, status):
    result = checker.out_of_order([("Review invoice", "Archive invoice")], [], model(reachable=reachable))
    assert result["status"] == status and result["denominator"] == 1


def temporal_source(note="review invoice 在 archive invoice 之前。"):
    return {"records": [{"sample_id": "synthetic_s1", "rule_id": "synthetic",
        "sentence_text": "review invoice before archive invoice", "temporal_suggestions": [note]}]}


def test_temporal_note_projection_preserves_all_sources_and_obligation_actions():
    original = {"synthetic": {"actions": ["archive invoice"], "order_relations": []}}
    doc = temporal_source()
    before = copy.deepcopy((original, doc))
    result, diag = project_confirmed_temporal_notes(original, doc)
    assert (original, doc) == before
    assert result["synthetic"]["order_relations"] == [("review invoice", "archive invoice")]
    assert result["synthetic"]["actions"] == ["archive invoice"]
    edge = diag["accepted"][0]
    for name in ("before", "after"):
        span = edge[name]
        assert doc["records"][0]["sentence_text"][span["start"]:span["end"]] == span["text"]


@pytest.mark.parametrize("note", ["obtain approval 在 archive invoice 之前。",
    "可能先 review invoice。", "review invoice 在 review invoice 之前。"])
def test_unanchored_or_uncertain_temporal_notes_are_not_promoted(note):
    result, diag = project_confirmed_temporal_notes({"synthetic": {"order_relations": []}}, temporal_source(note))
    assert not diag["accepted"] and diag["rejected"]
    assert not result["synthetic"]["order_relations"]


def test_prediction_ignores_gold_decision_and_prose(checker):
    records = {"r": {"actions": ["Review invoice"], "actors": ["Manager"], "order_relations": []}}
    items = [{"item_id": "x", "rule_id": "r", "process_id": "m", "check_type": "incorrect_actor"}]
    before = score_items(items, records, {"m": model()}, checker)
    altered = [{**items[0], "decision_violation_type": "incorrect_actor", "decision_evidence": "Always report a violation"}]
    assert score_items(altered, records, {"m": model()}, checker) == before


def test_unknown_counts_as_fn_and_is_not_true_negative():
    rows = [{"item_id": k, "check_type": "out_of_order", "predicted_violation_type": None,
             "result": {"status": "unknown", "observable": False}} for k in ("positive", "control")]
    gold = [{"item_id": "positive", "decision_violation_type": "out_of_order"},
            {"item_id": "control", "decision_violation_type": None}]
    ev = evaluate_items(rows, gold)
    assert ev["per_type"]["out_of_order"]["fn"] == 1
    assert ev["per_type"]["out_of_order"]["tn"] == 0
    assert ev["unknown_total"] == 2 and ev["dropped_items"] == 0


def test_missing_or_duplicate_predictions_fail_closed():
    gold = [{"item_id": "x", "decision_violation_type": "out_of_order"}]
    with pytest.raises(ValueError, match="membership"):
        evaluate_items([], gold)
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_items([], gold + gold)


def test_published_diagnostic_binds_sources_and_preserves_claim_boundary():
    import importlib.util
    path = ROOT / "scripts/run_s3_evidence_repair_v1.py"
    spec = importlib.util.spec_from_file_location("repair_run", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = module.verify_manifest()
    assert report["performance_claim_ready"] is False
    projection = report["arms"]["human_obligations"]["temporal_projection"]
    assert len(projection["accepted"]) == 3 and not projection["rejected"]
    assert report["local_notification_check"]["missing_action"]["status"] == "satisfied"
    assert report["local_notification_check"]["incorrect_actor"]["status"] == "satisfied"
    assert report["scope_audit"]["negative_control_count"] == 0
    assert report["scope_audit"]["out_of_input_reference_items"] == ["v018", "v021", "v030", "v033"]

# -*- coding: utf-8 -*-
"""Focused tests for the R4 targeted action-surface fix."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bpc_hybrid.stage3_r3_p2_adapter_v1 import (  # noqa: E402
    R3ActionView,
    R3P2Model,
    analyze_label_text,
    build_rule_action_views,
)
from bpc_hybrid.sun_stage3.r4_action_surface_scorer import R4ActionSurfaceScorer  # noqa: E402
from bpc_hybrid.winter_stage3.winter_similarity import WinterSimilarity  # noqa: E402


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def nlp():
    import spacy  # type: ignore
    return spacy.load("en_core_web_sm")


@pytest.fixture(scope="module")
def scorer(nlp):
    sim = WinterSimilarity(nlp)
    return R4ActionSurfaceScorer(sim, 0.8, 0.8, 0.8, nlp=nlp)


def _model(nlp, nodes, reachable=None):
    built = []
    actors = []
    actor_sources = {}
    action_actor_names = {}
    business_objects = []
    for spec in nodes:
        label = str(spec["label"])
        analysis = analyze_label_text(nlp, label, source="r4_test_node")
        action_surface = spec.get("action_surface", analysis["action_surface"])
        actor = str(spec.get("actor") or "FixtureActor")
        if actor not in actors:
            actors.append(actor)
        actor_sources[actor] = "pool"
        action_actor_names[str(spec["node_id"])] = [actor]
        node = {
            "node_id": str(spec["node_id"]),
            "node_type": "activity",
            "raw_label": label,
            "actor_surface": actor,
            "actor_status": "pool",
            "action_surface": action_surface,
            "business_object_surface": analysis["business_object_surface"],
            "match_source_text": analysis["match_source_text"],
            "matching_text": analysis["matching_text"],
            "parse_status": analysis["parse_status"],
            "parse_source": "r4_test_node",
        }
        built.append(node)
        if node.get("business_object_surface"):
            business_objects.append({
                "activity_id": str(spec["node_id"]),
                "object": node["business_object_surface"],
                "match_source_text": node["business_object_surface"],
                "matching_text": node["matching_text"],
            })
    sidecar = {
        "nodes": built,
        "actors": actors,
        "actor_sources": actor_sources,
        "action_actor_names": action_actor_names,
        "business_objects": business_objects,
        "reachable": reachable or {},
    }
    return R3P2Model(sidecar)


def test_action_surface_only_does_not_use_legacy_join(nlp, scorer):
    model = _model(nlp, [{"node_id": "N1", "label": "Approve the invoice"}])
    rule = build_rule_action_views(nlp, ["approve the invoice"])[0][0]
    assert scorer._model_action_source(model.actions[0]) == "Approve"
    assert model.actions[0]["match_source_text"] == "Approve the invoice"
    evidence = scorer.action_candidate_evidence(rule, model)
    assert evidence[0]["candidate_action_match_text"] == "Approve"
    assert evidence[0]["selected"] is True


def test_missing_action_surface_never_falls_back_to_full_label(nlp, scorer):
    model = _model(nlp, [{"node_id": "N1", "label": "Inform the data subject", "action_surface": None}])
    rule = build_rule_action_views(nlp, ["inform"])[0][0]
    evidence = scorer.action_candidate_evidence(rule, model)
    assert evidence[0]["reason"] == "model_action_missing_action_surface"
    assert not any(row.get("selected") for row in evidence)

    override = R3ActionView(
        "inform the data subject",
        original_text="inform the data subject",
        action_surface=None,
        business_object_surface=None,
        match_source_text=None,
        matching_text=None,
        parse_status="explicit_missing",
        parse_source="test",
        parse_error=None,
    )
    model2 = _model(nlp, [{"node_id": "N1", "label": "Inform the data subject"}])
    evidence2 = scorer.action_candidate_evidence(override, model2)
    assert evidence2[0]["reason"] == "rule_action_missing_action_surface"
    assert not any(row.get("selected") for row in evidence2)


def test_def4_def5_def6_def7_share_action_comparison(scorer, nlp):
    class Tracking(R4ActionSurfaceScorer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.calls = 0

        def _best_action_match(self, rule_action, model):
            self.calls += 1
            return super()._best_action_match(rule_action, model)

    model = _model(nlp, [{"node_id": "N1", "label": "Inform the data subject"}], {"N1": ["N2"]})
    model2 = _model(nlp, [{"node_id": "N2", "label": "Archive the record"}])
    model.reachable["N1"] = {"N2"}
    rule = build_rule_action_views(nlp, ["inform"])[0][0]
    track = Tracking(scorer.sim, scorer.tau, scorer.gamma, scorer.theta, nlp=nlp)
    track.matching_score([rule], ["FixtureActor"], model)
    c1 = track.calls
    track.missing_action([rule], model)
    c2 = track.calls
    track.out_of_order([(rule, build_rule_action_views(nlp, ["archive"])[0][0])], [rule], model)
    c3 = track.calls
    track.incorrect_actor([rule], ["FixtureActor"], model, [{"actor": "FixtureActor", "action": rule}])
    c4 = track.calls
    assert c1 > 0 and c2 > c1 and c3 > c2 and c4 > c3


def test_def6_candidate_evidence_is_per_candidate(nlp, scorer):
    model = _model(nlp, [{"node_id": "N1", "label": "Inform the data"}])
    rule = build_rule_action_views(nlp, ["inform"])[0][0]
    result = scorer.incorrect_actor([rule], ["the controller"], model,
                                    [{"actor": "the controller", "action": rule}])
    assert result["observable"] is True
    detail = result["details"][0]
    assert detail["minimum_candidates"]
    kinds = {row.get("kind") for row in result["process_actor_candidates"]}
    assert "business_object" in kinds
    for row in detail["process_actor_candidates"]:
        assert "rule_actor_similarity_raw" in row
        assert "entry_action_similarity_raw" in row


def test_mechanism_check_separates_contracts_probes_and_limitations():
    module = _load_module(ROOT / "scripts/run_stage3_r4_mechanism_check.py", "r4_mech_for_test")
    result = module.run_mechanism("r4_sm")
    assert result["status"] == "pass"
    assert result["summary"]["implementation_contract_checks_passed"] == result["summary"]["implementation_contract_checks_total"]
    assert result["summary"]["behavior_probes_passed"] == result["summary"]["behavior_probes_total"]
    assert result["summary"]["known_limitation_reproductions_observed"] == result["summary"]["known_limitation_reproductions_total"]
    assert result["summary"]["failed_contract_checks"] == []


def test_mechanism_failure_exit_code_is_nonzero():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_stage3_r4_mechanism_check.py"),
         "--backend", "r4_sm", "--self-test-failure"],
        cwd=ROOT, capture_output=True, text=True, timeout=180,
    )
    assert completed.returncode != 0
    assert completed.returncode == 1


def test_backend_selection_is_explicit_and_rejects_unknown():
    module = _load_module(ROOT / "scripts/run_stage3_table3_r4_targeted.py", "r4_runner_for_test")
    assert module._canonical_backend("sm") == "sm"
    assert module._canonical_backend("frozen_spacy_sm_text_similarity") == "sm"
    with pytest.raises(ValueError):
        module._canonical_backend("")
    with pytest.raises(ValueError):
        module._canonical_backend("definitely-not-a-backend")


def test_saved_r4_order_diagnostics_are_precise():
    pred_path = ROOT / "outputs/development/stage3_table3_r4_targeted_v1/predictions.json"
    if not pred_path.is_file():
        pytest.skip("R4 run output is not present")
    pred = json.loads(pred_path.read_text(encoding="utf-8"))
    categories = set()
    for row in pred.get("records") or []:
        for signals in (row.get("signals_by_rule") or {}).values():
            diag = (signals.get("out_of_order") or {}).get("r4_order_diagnostic") or {}
            if diag.get("category"):
                categories.add(diag["category"])
    assert "candidate_below_gamma" in categories
    assert "projection_rejected_multiple_predicate" in categories or "projection_rejected_span_or_projection" in categories
    assert "winter_native_unsupported" in categories

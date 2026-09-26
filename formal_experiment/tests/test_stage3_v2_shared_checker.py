# -*- coding: utf-8 -*-
"""Focused tests for the Stage 3-v2 shared semantic/order revision."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
import sys
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.stage3_v2.action_order_projection_v2 import (  # noqa: E402
    EXTENDED_ORDER_TYPE,
    MAIN_ORDER_TYPE,
    UNSUPPORTED_ORDER_TYPE,
    SharedActionOrderProjectionV2,
    Stage2ActionElement,
    _selected_endpoint,
)
from bpc_hybrid.stage3_v2.evaluation_v2 import DevelopmentEvaluationError, evaluate_dev_method  # noqa: E402
from bpc_hybrid.stage3_v2.semantic_matcher_v2 import (  # noqa: E402
    SPACY_MD,
    SPACY_SM,
    SharedSemanticMatcherV2,
    inventory_backends,
)

CONFIG = ROOT / "configs/stage3_v2_development_v1.json"
DEV_MANIFEST = ROOT / "data/development/stage3_v2/reference_dev_v1.json"
ORDER_SCOPE = ROOT / "outputs/reports/stage3_v2_order_scope_manifest_v1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- semantic
def test_semantic_backend_deterministic_symmetric_and_shared():
    matcher = SharedSemanticMatcherV2.for_backend(SPACY_SM)
    a = "provide information to the data subject"
    b = "inform the data subject"
    first = matcher.similarity(a, b)
    second = matcher.similarity(a, b)
    reverse = matcher.similarity(b, a)
    assert first == second
    assert reverse == pytest.approx(first, abs=1e-12)
    assert matcher.similarity(a, a) == 1.0
    identity = matcher.identity()
    assert identity["short_name"] == SPACY_SM
    assert identity["backend_identity_sha256"]


def test_inventory_preferred_sentence_embedding_requires_download_without_network():
    rows = {row["short_name"]: row for row in inventory_backends()}
    preferred = rows["sentence_transformers_all_mpnet_base_v2"]
    assert preferred["available"] is False
    assert preferred["download_required"] is True
    assert preferred["estimated_download_size_mb"] > 0
    assert rows[SPACY_MD]["available"] is True
    assert rows[SPACY_SM]["available"] is True


# ------------------------------------------------------- order projection
def test_order_projection_binds_existing_actions_before_after():
    source = "Submit the draft code before approving it"
    record = {
        "clauses": [{
            "modality": {"label": "obligation"},
            "clause_id": "c1",
            "actions": [
                {"id": "a1", "text": "Submit the draft code", "start": 0, "end": 21},
                {"id": "a2", "text": "approving it", "start": 28, "end": 40},
            ],
        }]
    }
    import spacy
    nlp = spacy.load("en_core_web_sm")
    result = SharedActionOrderProjectionV2().project(source, record, nlp=nlp, rule_id="R")
    assert result["status"] == "projected"
    assert result["edges"][0]["before_text"] == "Submit the draft code"
    assert result["edges"][0]["after_text"] == "approving it"


def test_order_projection_nominal_phrase_cannot_become_action():
    source = "Submit the request before the restriction of processing"
    record = {
        "clauses": [{
            "modality": {"label": "obligation"},
            "clause_id": "c1",
            "actions": [
                {"id": "a1", "text": "Submit the request", "start": 0, "end": 18},
            ],
        }]
    }
    import spacy
    nlp = spacy.load("en_core_web_sm")
    result = SharedActionOrderProjectionV2().project(source, record, nlp=nlp, rule_id="R")
    assert result["status"] == "no_edge"
    assert result["edges"] == []


def test_order_projection_ambiguous_endpoint_generates_no_edge():
    # Two overlapping/nested candidate actions with the same end are the same
    # character distance from the marker; the deterministic tie policy must
    # refuse to choose one.
    tied = [
        Stage2ActionElement("a", "A", 0, 3),
        Stage2ActionElement("b", "B", 1, 3),
    ]
    selected, audit = _selected_endpoint(tied, 5, 6, side="left",
                                         sentence_start=0, sentence_end=20)
    assert selected is None
    assert audit["selection_reason"] in {
        "ambiguous_tie_for_nearest_candidate",
        "ambiguous_multiple_candidates_same_distance",
    }


def test_order_projection_preserves_native_relation():
    record = {"clauses": []}
    source = "irrelevant"
    native = [{"before_action_id": "x", "after_action_id": "y",
               "before_text": "first", "after_text": "second"}]
    result = SharedActionOrderProjectionV2().project(source, record,
                                                     action_elements=[], native_relations=native,
                                                     rule_id="R")
    assert result["status"] == "native_preserved"
    assert result["edges"][0]["before_text"] == "first"


# ----------------------------------------------------------- calibration
def test_calibration_config_is_dev_only_and_frozen():
    config = load(CONFIG)
    assert config["calibration"]["development_only"] is True
    assert config["calibration"]["test_access_forbidden"] is True
    assert config["thresholds"]["grid_frozen_before_metrics"] is True
    assert config["thresholds"]["gamma_grid"] == [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    assert config["thresholds"]["theta_grid"] == config["thresholds"]["gamma_grid"]
    assert config["calibration"]["objective"] == "mean_of_sun_and_ours_development_macro_f1"
    assert "ours_minus_sun" in config["calibration"]["forbidden_objectives"]


def test_development_manifest_contains_only_development_cases():
    manifest = load(DEV_MANIFEST)
    assert manifest["case_count"] == len(manifest["cases"])
    assert manifest["test_cases_written"] == 0
    assert all(case["split"] == "development" for case in manifest["cases"])


def test_calibration_evaluator_rejects_test_case():
    cases = [{"case_id": "t1", "requirement_id": "R", "split": "test",
              "reference_states": {"missing_action": "satisfied"}}]
    with pytest.raises(DevelopmentEvaluationError):
        evaluate_dev_method("sun", cases, {}, {}, fail_on_test=True)


def test_order_scope_type_a_main_type_b_extended_type_c_unsupported():
    scope = load(ORDER_SCOPE)
    assert scope["main_metric_type"] == MAIN_ORDER_TYPE
    assert scope["extended_diagnostic_type"] == EXTENDED_ORDER_TYPE
    assert scope["unsupported_not_scored_type"] == UNSUPPORTED_ORDER_TYPE
    req = scope["requirements"]
    assert req["R5-D-01"]["order_type"] == MAIN_ORDER_TYPE
    assert req["R5-D-01"]["main_metric_eligible"] is True
    assert req["R5-D-12"]["order_type"] == EXTENDED_ORDER_TYPE
    assert req["R5-D-12"]["main_metric_eligible"] is False
    assert req["R5-S5-T4"]["order_type"] == UNSUPPORTED_ORDER_TYPE
    assert req["R5-S5-T4"]["main_metric_eligible"] is False


def test_stage3_v2_readiness_has_expected_freeze_flags():
    readiness_path = ROOT / "outputs/reports/stage3_v2_readiness_v1.json"
    readiness = load(readiness_path)
    assert readiness["WINTER_ARCHIVED"] is True
    assert readiness["STAGE3_V1_PRESERVED"] is True
    assert readiness["STAGE3_V2_BACKEND_FROZEN"] is True
    assert readiness["STAGE3_V2_TYPE_A_ORDER_SCOPE_FROZEN"] is True
    assert readiness["STAGE3_V2_ORDER_PROJECTION_FROZEN"] is True
    assert readiness["ACTION_SCOPE_CHANGE_IMPLEMENTED"] is False
    assert readiness["FINAL_UNSEEN_HOLDOUT_CREATED"] is False
    assert readiness["FINAL_TABLE3_V2_RUN"] is False
    assert readiness["REAL_API_CALLS"] == 0

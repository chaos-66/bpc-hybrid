# -*- coding: utf-8 -*-
"""Focused tests for the Stage-3 final convergence components.

These are intentionally scoped to the changed behaviour: the shared MPNet
backend constructor, the shared RuleRecord U_r adapter, and the order
supplement contract.  They do not run the full experiment suite.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import spacy  # noqa: E402

from bpc_hybrid.stage3_v2.action_order_projection_v2 import Stage2ActionElement  # noqa: E402
from bpc_hybrid.stage3_v2.rule_order_adapter_v3 import SharedRuleOrderAdapterV3  # noqa: E402
from bpc_hybrid.stage3_v2.semantic_matcher_v2 import (  # noqa: E402
    SPACY_SM,
    ST_MPNET,
    SharedSemanticMatcherV2,
)


def test_adapter_direction_inline_and_fronted() -> None:
    nlp = spacy.load("en_core_web_sm")
    matcher = SharedSemanticMatcherV2.for_backend(SPACY_SM)
    adapter = SharedRuleOrderAdapterV3(matcher)

    inline = "The processor shall inform the controller before processing personal data."
    actions = [
        Stage2ActionElement("a_inform", "inform the controller", 21, 42, "c1"),
        Stage2ActionElement("a_process", "processing personal data", 50, 75, "c1"),
    ]
    result = adapter.project(inline, nlp=nlp, rule_id="synthetic_inline",
                            action_elements=actions, native_relations=[])
    assert result["status"] == "projected"
    assert result["edges"][0]["before_action_id"] == "a_inform"
    assert result["edges"][0]["after_action_id"] == "a_process"

    fronted = "After processing personal data, the processor shall notify the controller."
    actions2 = [
        Stage2ActionElement("a_process", "processing personal data", 6, 31, "c1"),
        Stage2ActionElement("a_notify", "notify the controller", 59, 80, "c1"),
    ]
    result2 = adapter.project(fronted, nlp=nlp, rule_id="synthetic_fronted",
                              action_elements=actions2, native_relations=[])
    assert result2["status"] == "projected"
    assert result2["edges"][0]["before_action_id"] == "a_process"
    assert result2["edges"][0]["after_action_id"] == "a_notify"


def test_adapter_never_invents_nominal_endpoint() -> None:
    nlp = spacy.load("en_core_web_sm")
    matcher = SharedSemanticMatcherV2.for_backend(SPACY_SM)
    adapter = SharedRuleOrderAdapterV3(matcher)
    # Only ``inform`` exists in A_r; ``processing`` must not be invented.
    source = "The processor shall inform the controller before processing personal data."
    actions = [Stage2ActionElement("a_inform", "inform the controller", 21, 42, "c1")]
    result = adapter.project(source, nlp=nlp, rule_id="synthetic_no_invent",
                             action_elements=actions, native_relations=[])
    assert result["edges"] == []
    assert result["status"] in ("no_edge", "projected")
    assert result["status"] == "no_edge"


def test_mpnet_shared_local_backend_is_deterministic() -> None:
    try:
        matcher = SharedSemanticMatcherV2.for_backend(ST_MPNET)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"local MPNet snapshot not available: {exc}")
    a = "provide information prior to further processing"
    b = "inform the controller before processing"
    first = matcher.similarity(a, b)
    second = matcher.similarity(a, b)
    reverse = matcher.similarity(b, a)
    assert first == second
    assert first == pytest.approx(reverse, abs=1e-12)
    assert 0.0 <= first <= 1.0
    assert matcher.similarity(a, a) == 1.0
    identity = matcher.identity()
    assert identity["kind"] == "sentence_transformers"
    assert identity["vector_dim"] == 768


def test_final_development_pool_marks_all_seen_cases_not_final_eligible() -> None:
    pool_path = ROOT / "data/development/stage3_final_development_pool_v1.json"
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    assert pool["ALL_EXISTING_CASES_SEEN"] is True
    assert pool["FINAL_TEST_ELIGIBLE"] is False
    assert pool["case_count"] == 113
    assert all(case["split"] == "development" for case in pool["cases"])
    assert all(case["FINAL_TEST_ELIGIBLE"] is False for case in pool["cases"])


def test_order_supplement_is_dev_only_and_source_identity_checked() -> None:
    supplement = json.loads(
        (ROOT / "data/development/stage3_final_order_supplement_v1/manifest.json")
        .read_text(encoding="utf-8")
    )
    assert supplement["dev_only"] is True
    assert supplement["seen_during_method_development"] is True
    assert supplement["final_table3_eligible"] is False
    source = json.loads(
        (ROOT / "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json")
        .read_text(encoding="utf-8")
    )
    requirement = next(
        row for row in source["requirements"] if row["requirement_id"] == "R5-S4-T3"
    )
    expected = hashlib.sha256(requirement["excerpt_text"].encode("utf-8")).hexdigest()
    assert supplement["source_requirement_text_sha256"] == expected

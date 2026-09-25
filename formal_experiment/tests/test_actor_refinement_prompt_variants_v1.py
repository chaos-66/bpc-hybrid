# -*- coding: utf-8 -*-
"""Static tests for the frozen Actor-refinement prompt variants."""

from __future__ import annotations

import copy
import difflib
import hashlib
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for _path in (SRC, SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import build_actor_refinement_prompt_variants_v1 as builder  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402


PROMPT_NAMES = {
    "B0": "direct_llm_actor_baseline_v1",
    "R": "direct_llm_actor_role_eligibility_v1",
    "P": "direct_llm_actor_pronoun_policy_v1",
    "C": "direct_llm_actor_condition_projection_v1",
}
BASE_BYTES = builder.BASE_PROMPT.read_bytes()


def _variant_bytes(arm: str) -> bytes:
    return (builder.OUT_DIR / f"{PROMPT_NAMES[arm]}.md").read_bytes()


def _changed_variant_lines(arm: str) -> list[str]:
    base_text = BASE_BYTES.decode("utf-8")
    variant_text = _variant_bytes(arm).decode("utf-8")
    hunks = builder._line_diff(base_text, variant_text)
    return [line for hunk in hunks for line in hunk["variant_changed_lines"]]


def test_t1_baseline_semantically_and_byte_identical() -> None:
    assert _variant_bytes("B0") == BASE_BYTES
    assert hashlib.sha256(_variant_bytes("B0")).hexdigest() == builder.EXPECTED_BASE_SHA


@pytest.mark.parametrize("arm", ["R", "P", "C"])
def test_t2_t3_t4_only_expected_regions_change(arm: str) -> None:
    base_text = BASE_BYTES.decode("utf-8")
    variant_text = _variant_bytes(arm).decode("utf-8")
    hunks = builder._line_diff(base_text, variant_text)
    builder._classify_hunks(arm, hunks)
    assert all(hunk["allowed_by_arm"] for hunk in hunks)
    if arm == "R":
        allowed = {"rule10"}
    elif arm == "P":
        allowed = {"rule10", "rule1617", "example1"}
    else:
        allowed = {"rule2728"}
    observed = {
        region
        for hunk in hunks
        for region in (hunk["baseline_regions"] + hunk["variant_regions"])
    }
    assert observed <= allowed


def test_t2_role_eligibility_semantics_and_non_interference() -> None:
    text = _variant_bytes("R").decode("utf-8")
    assert "Grammatical subjecthood alone is not sufficient for actor status." in text
    assert "regulated object, legal provision, amount, asset, proposition, event/state" in text
    assert "A subject pronoun it/they/this/these/such is a real" in text
    assert "actor mention." in text
    assert "may be emitted as an actor only when its antecedent" not in text
    assert "Actor and condition spans may overlap." not in text
    changed = "\n".join(_changed_variant_lines("R"))
    for forbidden in ("taxpayer", "employee", "recipient", "bank", "authority",
                      "fund", "building society", "agreement", "register"):
        assert forbidden not in changed.lower()


def test_t3_pronoun_policy_semantics_and_same_factor_example() -> None:
    text = _variant_bytes("P").decode("utf-8")
    assert "whose antecedent is not explicitly\n    recoverable within source_text, do not emit" in text
    assert "Preserve uncertain surface mentions as usual, except for unresolved" in text
    assert "antecedent inferred from outside source_text" in text
    assert "Example 1 — unresolved subject pronoun is not promoted to actor:" in text
    assert '"actors": [],' in text
    assert '"actor_action_map": [{"actor_id": null, "action_id": "p01"}],' in text
    assert "Grammatical subjecthood alone" not in text
    assert "Actor and condition spans may overlap." not in text


def test_t4_condition_projection_semantics_and_non_interference() -> None:
    text = _variant_bytes("C").decode("utf-8")
    assert "28. Actor and condition spans may overlap." in text
    assert "emit the smallest exact actor mention" in text
    assert "Do not infer an unstated actor." in text
    assert "regulated object, legal provision, amount, asset" not in text
    assert "may be emitted as an actor only when its antecedent" not in text
    assert "A subject pronoun it/they/this/these/such is a real" in text


def test_t5_hard_json_interface_contract_preserved() -> None:
    required = [
        "stage2_extraction_contract@1.0.0",
        "stage2_prediction.schema.json@1.0.0",
        "schema_version, sample_id,",
        "source_id, source_text, clauses, method, validation,",
        "unsupported_or_ambiguous",
        "Return ONLY one valid JSON object.",
        'method.name = "direct_llm"',
    ]
    for arm in PROMPT_NAMES:
        text = _variant_bytes(arm).decode("utf-8")
        for marker in required:
            assert marker in text
        loaded = load_prompt(f"actor_refinement_v1/{PROMPT_NAMES[arm]}")
        assert loaded.system_prompt
        assert loaded.user_prompt_template
        assert len(loaded.few_shot_examples) == 6
        assert all(isinstance(ex["output"], dict)
                   for ex in loaded.few_shot_examples)


@pytest.mark.parametrize("arm", sorted(PROMPT_NAMES))
def test_t6_prompt_loader_loads_all_variants(arm: str) -> None:
    loaded = load_prompt(f"actor_refinement_v1/{PROMPT_NAMES[arm]}")
    assert loaded.path.is_file()
    assert loaded.sha256 == hashlib.sha256(_variant_bytes(arm)).hexdigest()
    assert loaded.extras.get("contract_id") == "stage2_extraction_contract@1.0.0"


def test_t10_no_gold_used_during_prompt_construction() -> None:
    manifest = json.loads(builder.PROMPT_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["construction"]["gold_used"] is False
    source = inspect.getsource(builder)
    for forbidden in (
        "build_canonical_gold_records",
        "evaluate_sun_literal_overlap",
        "estg_150_human_correction",
        "data/gold",
        "data\\\\gold",
    ):
        assert forbidden not in source
    for arm in PROMPT_NAMES:
        text = _variant_bytes(arm).decode("utf-8")
        assert "estg_000002" not in text
        assert "estg_000003" not in text
# -*- coding: utf-8 -*-
"""Focused offline tests for the non-active definition-refinement candidate.

These tests are prompt-content / assembly / contract tests only.  They never
invoke a model and never claim predicted correctness.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for candidate in (SRC, SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import bpc_hybrid.modular_prompt as mp  # noqa: E402
import bpc_hybrid.modular_refinement_prompt as rp  # noqa: E402
import bpc_hybrid.sep_c3_definition_refinement_prompt as dr  # noqa: E402
import build_sep_c3_definition_refinement_v1 as build  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402


FIXTURE_PATH = (
    ROOT / "tests" / "fixtures" / "sep_c3_definition_synthetic_cases_v1.json"
)

ACTIVE_SHA256 = {
    "common_system": "b8cfc32b87f446ced89da83fd0ad5aef69ee418a116c6ede534816c5204ac2d7",
    "user_envelope": "e8f18096d7260ccd23a6a1ed562b15c861f4e6caf2e5bc7de96a8a23d4e98728",
    "examples_E": "fa04d454914fd85ad422ed40b3e4d3f71027ad87e9a46b1f4808f0cb4e21aebd",
    "semantic_rules_S": "113037b73485adb071dbfeabc54dfe6906514279c3dd065f72b4eb019d3a0025",
    "output_format_J": "aa4ed3db8c8b55090a719467802cc878847b436fab9ec8af4d730dce9e899879",
    "R_A": "0d1a0b131c88394304ac22d510740694fed5069f9cc8b4b9612fd33285e789c9",
    "R_C": "cfcbbc45e278ab3ad4fad8784c5a6bcc551c0b51a2e1833ac2c4e56d0571fcae",
    "active_manifest": "3d9ceb897b0582bf862a7d4c9ca130b07533a37c272e59b37c7323bededc9414",
    "active_A": "d24c0c0d5150dd6382260f91614cc6d475ecdb68efb2cfe8d48347272d74a580",
    "active_B": "c468c631b6e454522994d6839f6a4021a259daedea7f3a2852b7b4343cd22849",
    "active_C": "d58163b677c6a7bda06f4de3ea8de743d8568e0d5e2c740bdea8af48ccfa4479",
    "active_D": "b241126dcb04001872e3bfd60deb330ed884ccad50537cc2031017a66835c091",
    "registry": "31f3358d089611b85a4a50d36444a4c59f6d965abbf0b8770aeb73db13642749",
    "gold": "c31a514a6b58b640ed020c380c0b7bed136dc9574b2c98c98dedec1ecdb57100",
}

ACTIVE_PATHS = {
    "common_system": ROOT / "prompts" / "sun_compat" / "modular_v1" / "common_system.md",
    "user_envelope": ROOT / "prompts" / "sun_compat" / "modular_v1" / "user_envelope.md",
    "examples_E": ROOT / "prompts" / "sun_compat" / "modular_v1" / "examples_E.md",
    "semantic_rules_S": ROOT / "prompts" / "sun_compat" / "modular_v1" / "semantic_rules_S.md",
    "output_format_J": ROOT / "prompts" / "sun_compat" / "modular_v1" / "output_format_J.md",
    "R_A": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "R_A_actor_minimality.md",
    "R_C": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "R_C_constraint_recall.md",
    "active_manifest": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "generated" / "manifest.json",
    "active_A": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "generated" / "direct_llm_refinement_A_v1.md",
    "active_B": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "generated" / "direct_llm_refinement_B_v1.md",
    "active_C": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "generated" / "direct_llm_refinement_C_v1.md",
    "active_D": ROOT / "prompts" / "sun_compat" / "modular_refinement_v1" / "generated" / "direct_llm_refinement_D_v1.md",
    "registry": ROOT / "configs" / "models" / "estg150_d1_active_registry_v1.json",
    "gold": ROOT / "data" / "gold" / "stage2" / "estg150_formal_gold_v1.json",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _span(sentence: str, text: str) -> tuple[int, int]:
    start = sentence.index(text)
    end = start + len(text)
    assert sentence[start:end] == text
    return start, end


def _sent_text(prompt) -> str:
    return (
        prompt.system_prompt
        + "\n\n<!--USER-->\n\n"
        + prompt.user_prompt_template
    )


def test_guidance_exists_exactly_once_and_is_semantic_not_lexical():
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")

    assert dr.R_DEF_TEXT not in base.system_prompt
    assert rdef.system_prompt.count(dr.R_DEF_TEXT) == 1
    assert "semantic" in dr.R_DEF_TEXT.lower()
    assert "context" in dr.R_DEF_TEXT.lower()
    assert "shall" in dr.R_DEF_TEXT
    assert "action-presence principle" in dr.R_DEF_TEXT

    forbidden = (
        "shall be deemed => definition",
        "shall apply => definition",
        "shall be treated => definition",
        "shall be deemed -> definition",
        "shall apply -> definition",
        "shall be treated -> definition",
        "=> definition",
    )
    for shortcut in forbidden:
        assert shortcut not in rdef.system_prompt, shortcut


def test_candidate_replaces_only_E4_and_keeps_other_E_examples():
    active_e = mp.load_module_texts()["E"]
    candidate_e = dr.expected_candidate_e_text()

    assert active_e.count(dr.OLD_E4_BLOCK) == 1
    assert dr.OLD_E4_BLOCK not in candidate_e
    assert candidate_e.count(dr.NEW_E4_BLOCK) == 1
    assert active_e.replace(dr.OLD_E4_BLOCK, "", 1) == candidate_e.replace(
        dr.NEW_E4_BLOCK, "", 1
    )

    base = dr.render_definition_prompt("BASE")
    assert "actors and actions empty" not in base.user_prompt_template
    assert "Example E1" in base.user_prompt_template
    assert "Example E2" in base.user_prompt_template
    assert "Example E3" in base.user_prompt_template
    assert "Example E5" in base.user_prompt_template


def test_common_system_is_identical_and_R_DEF_is_only_addition():
    active_a = rp.render_refinement_prompt("A")
    base = dr.render_definition_prompt("BASE")
    rdef = dr.render_definition_prompt("R_DEF")

    assert base.system_prompt == active_a.system_prompt
    assert rdef.system_prompt == base.system_prompt + "\n\n" + dr.R_DEF_TEXT
    assert base.user_prompt_template == rdef.user_prompt_template
    assert rdef.user_prompt_template == mp.render_modular_prompt(
        "100", dr.candidate_module_texts()
    ).user_prompt_template


def test_E4_v2_record_spans_are_valid_nonempty_and_have_empty_other_fields():
    wrapper = dr.e4_v2_candidate_record()
    record = wrapper["expected_rule_record"]
    sentence = record["source_text"]
    clause = record["clauses"][0]
    clause_span = clause["clause_span"]
    evidence = clause["modality"]["evidence"][0]
    action = clause["actions"][0]

    assert wrapper["status"] == "DESIGN_CANDIDATE_NOT_APPLIED"
    assert re.search(r"estg_\d+", sentence) is None
    assert clause["modality"]["label"] == "definition"
    assert clause["actors"] == []
    assert len(clause["actions"]) == 1
    assert action["text"] == dr.E4_V2_ACTION_TEXT
    assert evidence["text"] == dr.E4_V2_EVIDENCE_TEXT
    assert clause["conditions"] == []
    assert clause["constraints"] == []
    assert clause["exceptions"] == []
    assert clause["actor_action_map"] == []
    assert clause["order_relations"] == []

    for item in (clause_span, evidence, action):
        assert sentence[item["start"]:item["end"]] == item["text"]
        assert clause_span["start"] <= item["start"] <= item["end"] <= clause_span["end"]

    assert clause_span["text"] == sentence[:-1]
    assert clause_span["end"] == len(sentence) - 1
    assert action["start"] >= evidence["end"]
    assert action["end"] == clause_span["end"]


def test_E4_v2_block_does_not_teach_condition_constraint_exception_labels():
    lowered = dr.NEW_E4_BLOCK.lower()
    assert "condition" not in lowered
    assert "constraint" not in lowered
    assert "exception" not in lowered
    assert "no other field populated" in lowered
    assert "actors empty" in dr.NEW_E4_BLOCK
    assert dr.E4_V2_ACTION_TEXT in dr.NEW_E4_BLOCK


def test_fixture_cases_A_to_F_have_deterministic_contract_spans():
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    categories = {case["category"] for case in cases}
    assert {
        "explicit_means_definition",
        "synthetic_shall_definition",
        "ordinary_actor_directed_shall_obligation",
        "may_permission",
        "may_not_prohibition",
        "ambiguous_applicability_statement",
    }.issubset(categories)

    for case in cases:
        sentence = case["sentence"]
        assert re.search(r"estg_\d+", sentence) is None
        assert case["expected_evidence_text"] in sentence
        _span(sentence, case["expected_evidence_text"])
        if case["expected_actor_text"] is not None:
            _span(sentence, case["expected_actor_text"])
        if case["expected_action_text"] is not None:
            _span(sentence, case["expected_action_text"])
        if case["ambiguous"]:
            assert isinstance(case["expected_modality"], list)
            assert "must not justify a lexical rule" in case["note"].lower()
        else:
            assert isinstance(case["expected_modality"], str)


def test_candidate_arms_have_no_S_S8_or_J_leakage():
    for arm in dr.CANDIDATE_ARMS:
        prompt = dr.render_definition_prompt(arm)
        text = _sent_text(prompt)
        for marker in (
            "Semantic interpretation rules",
            "2. Modality:",
            "8. Field partition:",
            "11. Definition and empty records:",
            "Output organization",
            "S2",
            "S11",
            "S8",
        ):
            assert marker not in text, (arm, marker)


def test_generated_candidate_prompts_match_renderer_and_loader():
    for arm in dr.ALL_ARMS:
        path = dr.generated_path(arm)
        assert path.is_file(), path
        rendered = dr.render_definition_prompt(arm)
        assert path.read_text(encoding="utf-8") == rendered.to_markdown()
        loaded = load_prompt(dr.loader_name(arm))
        assert loaded.system_prompt == rendered.system_prompt
        assert loaded.user_prompt_template == rendered.user_prompt_template


def test_active_prompt_registry_gold_and_related_components_are_byte_identical():
    for name, path in ACTIVE_PATHS.items():
        assert path.is_file(), path
        actual = _sha256_bytes(path.read_bytes())
        assert actual == ACTIVE_SHA256[name], (name, actual)


def test_builder_audit_passes_without_writing_active_prompts():
    audit = build.build(write=False, overwrite=False)
    assert audit["status"] == "pass"
    assert audit["api_calls"] == 0
    assert audit["checks"]["common_system_identical_to_active_A"] is True
    assert audit["checks"]["candidate_E4_v2_exactly_once"] is True
    assert audit["checks"]["lexical_shortcuts_absent_from_R_DEF"] is True
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid import modular_prompt as mp  # noqa: E402


SYNTHETIC_EXAMPLES = (
    ("It may cover a shorter period if a business is opened.",
     {"actor": "It", "action": "cover a shorter period",
      "condition": "if a business is opened"}),
    ("The report must be filed within 72 hours and retained for 5 years.",
     {"action": "filed", "constraint": "within 72 hours"}),
    ("The controller may not disclose data unless the data subject consents.",
     {"actor": "The controller", "action": "disclose data",
      "exception": "unless the data subject consents"}),
    ("'Personal data' means information about a person; the controller must protect it.",
     {"action": "protect it"}),
    ("The tax office shall refund the amount if the application is filed within two years.",
     {"action": "refund the amount",
      "condition": "if the application is filed within two years",
      "constraint": "within two years"}),
)


def test_all_eight_combinations_render():
    prompts = mp.render_all()
    assert set(prompts) == set(mp.COMBINATIONS)
    assert len(prompts) == 8
    for code, prompt in prompts.items():
        assert prompt.combination == code
        assert prompt.system_prompt
        assert prompt.user_prompt_template
        assert prompt.composition_sha256


def test_required_interface_is_in_every_combination_once():
    for prompt in mp.render_all().values():
        system = prompt.system_prompt
        for marker in mp.REQUIRED_COMMON_MARKERS:
            assert marker in system
        # Common interface names must not depend on S, E, or J being enabled.
        assert "Top level: schema_version, sample_id, source_id" in system
        assert "Clause: clause_id, clause_span, modality" in system


def test_basic_output_conventions_live_in_common_not_s():
    # Deleting S must not remove the coordinate/ID output contract.
    for code, prompt in mp.render_all().items():
        system = prompt.system_prompt
        assert "zero-based start and exclusive end" in system
        assert "IDs are unique within the complete record" in system
        assert "may reference IDs only from the same clause" in system
        if prompt.flags["S"]:
            assert "Every evidence text must equal" not in system
            assert "IDs are unique within the record" not in system
        else:
            assert "Semantic interpretation rules" not in system


def test_disabled_modules_are_absent_and_no_dangling_references():
    for code, prompt in mp.render_all().items():
        flags = prompt.flags
        user = prompt.user_prompt_template
        text = prompt.system_prompt + "\n" + user
        if flags["S"]:
            assert "Semantic interpretation rules" in text
        else:
            assert "Semantic interpretation rules" not in text
            assert "Source boundary:" not in text
        if flags["E"]:
            assert "Synthetic worked examples" in user
            assert "Example E1" in user
        else:
            assert "Synthetic worked examples" not in user
            assert "Example E1" not in user
        if flags["J"]:
            assert "Output organization" in prompt.system_prompt
        else:
            assert "Output organization" not in prompt.system_prompt
            assert "Return one bare JSON object" not in prompt.system_prompt
        assert "{few_shot_block}" not in user
        assert "Use these examples" not in user


def test_user_template_renders_for_every_combination():
    for prompt in mp.render_all().values():
        user = prompt.render_user("s1", "A must act.")
        assert "sample_id: s1" in user
        assert "source_id: s1" in user
        assert "source_text:\nA must act." in user
        messages = prompt.request_messages("s1", "A must act.")
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == user


def test_examples_are_synthetic_and_spans_are_exact():
    formal_text = (
        ROOT / "data" / "input" / "estg150_formal_inference_input_v2.json"
    ).read_text(encoding="utf-8")
    examples = mp.load_module_texts()["E"]
    for input_text, choices in SYNTHETIC_EXAMPLES:
        assert input_text not in formal_text
        for substring in choices.values():
            start = input_text.index(substring)
            assert input_text[start:start + len(substring)] == substring
    # The generated example block must not contain copied formal input text.
    assert "estg_" not in examples


def test_generated_prompts_match_renderer_and_loader():
    from bpc_hybrid.prompt_loader import load_prompt

    for code, prompt in mp.render_all().items():
        path = mp.generated_path(code)
        assert path.is_file()
        assert path.read_text(encoding="utf-8") == prompt.to_markdown()
        loader_name = path.relative_to(
            ROOT / "prompts" / "sun_compat"
        ).with_suffix("").as_posix()
        loaded = load_prompt(loader_name)
        assert loaded.system_prompt == prompt.system_prompt
        assert loaded.user_prompt_template == prompt.user_prompt_template


def test_full_combination_uses_only_new_modular_text():
    prompt = mp.render_modular_prompt("111")
    text = prompt.system_prompt + "\n" + prompt.user_prompt_template
    # Historical section headings and full-JSON example literals must not leak
    # into the newly sent prompt.
    for old_marker in (
        "Output discipline:",
        "Final self-check before output:",
        "Six-element semantics:",
        "Field-typing precision (D1-R1):",
        "in accordance with Section 11(1)",
        "synthetic_condition_constraint_01",
        "Example 5",
    ):
        assert old_marker not in text
    assert "Example E1" in prompt.user_prompt_template


def test_manifest_is_complete_and_deterministic():
    manifest_path = mp.generated_manifest_path()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["prompt_family"] == "direct_llm_modular_v1"
    assert manifest["combination_order"] == ["E", "S", "J"]
    assert set(manifest["combinations"]) == set(mp.COMBINATIONS)
    for code, row in manifest["combinations"].items():
        prompt = mp.render_modular_prompt(code)
        assert row["composition_sha256"] == prompt.composition_sha256
        assert row["flags"] == prompt.flags
        assert row["sha256"] == mp._sha256_text(prompt.to_markdown())


def test_build_check_reports_pass_without_network():
    import importlib.util

    script = ROOT / "scripts" / "build_modular_prompt_v1.py"
    spec = importlib.util.spec_from_file_location("build_modular_test", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    report = module.check(require_generated=True)
    assert report["status"] == "pass"
    assert report["checks"]["eight_combinations_rendered"] is True
    assert report["checks"]["all_required_interface_markers"] is True
    assert report["checks"]["loader_matches_renderer"] is True
    assert report["errors"] == []

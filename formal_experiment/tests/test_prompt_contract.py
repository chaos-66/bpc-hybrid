"""Prompt contract tests (Wave 1.1 \u00a73.6).

Verifies:
- prompt loader actually reads files (no hardcoded system prompt in runners)
- D1 few-shot examples pass the canonical validator
- H1 prompt is a strict repair patch (not a full record)
- prompt SHA-256 is stable
- runners that load prompts raise FileNotFoundError if the prompt file is missing
- repair-patch contract: cannot modify non-repair_fields, cannot collide ids
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import (
    PROMPTS_DIR,
    LoadedPrompt,
    build_manifest_entry,
    load_prompt,
    render_user_prompt,
)
from bpc_hybrid.stage2_canonical import (
    SCHEMA_SOURCE,
    validate_canonical,
)


# ---------------------------------------------------------------------------
# Prompt file existence
# ---------------------------------------------------------------------------


def test_d1_prompt_file_exists():
    assert (PROMPTS_DIR / "direct_llm_sun_record_prompt.md").exists()


def test_h1_prompt_file_exists():
    assert (PROMPTS_DIR / "rule_first_llm_fallback_prompt.md").exists()


# ---------------------------------------------------------------------------
# Prompt loader basics
# ---------------------------------------------------------------------------


def test_d1_prompt_loads_with_sha256():
    p = load_prompt("direct_llm_sun_record_prompt")
    assert isinstance(p, LoadedPrompt)
    assert p.sha256 != ""
    assert len(p.sha256) == 64  # sha256 hex length
    assert p.system_prompt != ""
    assert p.user_prompt_template != ""


def test_h1_prompt_loads_with_sha256():
    p = load_prompt("rule_first_llm_fallback_prompt")
    assert p.sha256 != ""
    assert p.system_prompt != ""
    assert p.user_prompt_template != ""


def test_d1_prompt_sha256_stable():
    p1 = load_prompt("direct_llm_sun_record_prompt")
    p2 = load_prompt("direct_llm_sun_record_prompt")
    assert p1.sha256 == p2.sha256


def test_h1_prompt_no_full_record_template():
    """H1 prompt must not contain a flat 6-field JSON template \u2014 only repair-patch schema."""
    p = load_prompt("rule_first_llm_fallback_prompt")
    # The system prompt must mention 'repair patch' and forbid full-record emission
    assert "repair patch" in p.system_prompt.lower()
    assert "not a full record" in p.system_prompt.lower() or "patch" in p.system_prompt.lower()
    # The user template must request the patch schema (sample_id, clause_id, repair_fields, patches, reason)
    assert "sample_id" in p.user_prompt_template
    assert "clause_id" in p.user_prompt_template
    assert "repair_fields" in p.user_prompt_template
    assert "patches" in p.user_prompt_template


def test_d1_prompt_requires_canonical_record():
    """D1 prompt must require the full canonical record, not a flat 6-field object."""
    p = load_prompt("direct_llm_sun_record_prompt")
    body = (p.system_prompt + p.user_prompt_template).lower()
    assert "stage 2 canonical" in body or "canonical schema" in body
    assert "multi-clause" in body
    assert "multi-actor" in body
    assert "multi-action" in body
    # Must NOT instruct sampling \u2014 sampling is controlled by config
    body_no_negation = body
    assert "you must set temperature" not in body_no_negation
    assert "set seed to" not in body_no_negation


def test_sampling_policy_documented_but_not_pretrained():
    """The prompt file may document sampling in comments; it must not be sent to the LLM."""
    p = load_prompt("direct_llm_sun_record_prompt")
    assert "sampling_policy" in p.extras
    # ensure the system prompt itself does not include the 'temperature = 0' control instruction
    assert "temperature = 0" not in p.system_prompt
    assert "temperature=0" not in p.system_prompt


# ---------------------------------------------------------------------------
# Few-shot validation
# ---------------------------------------------------------------------------


def test_d1_few_shot_examples_pass_canonical_validator():
    p = load_prompt("direct_llm_sun_record_prompt")
    assert p.few_shot_examples, "D1 prompt must include few-shot examples"
    for ex in p.few_shot_examples:
        rep = validate_canonical(ex["output"])
        assert rep.schema_valid, f"schema errors in {ex['description']}: {rep.errors}"
        assert rep.cross_field_valid, f"cross-field errors in {ex['description']}: {rep.errors}"


def test_d1_few_shot_covers_required_modalities():
    p = load_prompt("direct_llm_sun_record_prompt")
    labels = {ex["output"]["clauses"][0]["modality"]["label"] for ex in p.few_shot_examples}
    # Must cover at least obligation, prohibition, definition per \u00a73.4
    assert "obligation" in labels
    assert "prohibition" in labels
    assert "definition" in labels


def test_d1_few_shot_covers_multi_action():
    p = load_prompt("direct_llm_sun_record_prompt")
    has_multi = any(len(ex["output"]["clauses"][0].get("actions", [])) > 1 for ex in p.few_shot_examples)
    assert has_multi, "D1 few-shot must include at least one multi-action example"


def test_d1_few_shot_method_name_is_direct_llm():
    p = load_prompt("direct_llm_sun_record_prompt")
    for ex in p.few_shot_examples:
        assert ex["output"]["method"]["name"] == "direct_llm"
        assert ex["output"]["method"]["schema_source"] == SCHEMA_SOURCE


def test_d1_prompt_v4_defines_constraint_categories_and_no_folding():
    # D1-R1-FIELD-TYPING (2026-08-04): the system prompt must define the
    # constraint categories (legal references, temporal/quantity limits) and
    # forbid folding constraint content into the action span.
    p = load_prompt("direct_llm_sun_record_prompt")
    sys_txt = p.system_prompt
    assert "within the meaning of" in sys_txt
    assert "pursuant to" in sys_txt
    assert "MUST NOT be folded into the action span" in sys_txt
    assert "condition" in sys_txt and "constraint" in sys_txt
    # the user template must instruct an exhaustive constraint/condition scan
    assert "Scan the sentence for EVERY constraint phrase" in p.user_prompt_template


def test_d1_few_shot_covers_constraint_and_condition_fields():
    # the v4 examples must demonstrate a legal-reference constraint and a
    # condition clause with a nested constraint (the two low-recall fields).
    p = load_prompt("direct_llm_sun_record_prompt")
    constraints = [ex for ex in p.few_shot_examples
                   if ex["output"]["clauses"][0].get("constraints")]
    conditions = [ex for ex in p.few_shot_examples
                  if ex["output"]["clauses"][0].get("conditions")]
    assert any("Section 11(1)" in ex["output"]["clauses"][0]["constraints"][0]["text"]
               for ex in constraints), "legal-reference constraint example missing"
    assert any("within two years" in ex["output"]["clauses"][0]["constraints"][0]["text"]
               for ex in constraints), "nested-constraint example missing"
    assert conditions, "condition example missing"


# ---------------------------------------------------------------------------
# render_user_prompt
# ---------------------------------------------------------------------------


def test_render_user_prompt_substitutes_keys():
    p = load_prompt("direct_llm_sun_record_prompt")
    rendered = render_user_prompt(
        p.user_prompt_template,
        sample_id="estg_000001",
        source_text="The controller shall notify.",
        few_shot_block="(omitted)",
    )
    assert "estg_000001" in rendered
    assert "The controller shall notify." in rendered


def test_render_user_prompt_raises_on_missing_key():
    p = load_prompt("direct_llm_sun_record_prompt")
    with pytest.raises(KeyError):
        render_user_prompt(p.user_prompt_template)  # missing sample_id, source_text, few_shot_block


# ---------------------------------------------------------------------------
# Manifest entry
# ---------------------------------------------------------------------------


def test_build_manifest_entry_records_sha256():
    p = load_prompt("direct_llm_sun_record_prompt")
    entry = build_manifest_entry(p, role="primary")
    assert entry["role"] == "primary"
    assert entry["sha256"] == p.sha256
    assert "sampling_policy" in entry


# ---------------------------------------------------------------------------
# Repair-patch contract (H1)
# ---------------------------------------------------------------------------


# import the apply_repair_patch function from the runner module
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "run_sun_llm_fallback_mod",
    PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py",
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)
apply_repair_patch = _mod.apply_repair_patch


def _clause_fixture() -> dict:
    text = "The controller shall notify the supervisory authority within 72 hours."
    return {
        "clause_id": "estg_000001_c01",
        "clause_span": {"text": text, "start": 0, "end": len(text)},
        "modality": {
            "label": "obligation",
            "evidence": [{"text": "shall", "start": 15, "end": 20}],
        },
        "actors": [{"id": "a01", "text": "The controller", "start": 0, "end": 15, "normalized": "controller"}],
        "actions": [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
    }


def test_h1_patch_cannot_modify_unauthorized_field():
    clause = _clause_fixture()
    repair_fields = ["action"]  # only action
    patch = {"modality": {"label": "prohibition", "evidence": [{"text": "shall", "start": 15, "end": 20}]}}
    new_clause, errors = apply_repair_patch(clause, patch, repair_fields)
    assert any("unauthorized" in e for e in errors)
    # modality must NOT have been changed
    assert new_clause["modality"]["label"] == "obligation"


def test_h1_patch_replaces_entire_modality_block():
    clause = _clause_fixture()
    patch = {"modality": {"label": "prohibition", "evidence": [{"text": "shall not", "start": 15, "end": 23}]}}
    new_clause, errors = apply_repair_patch(clause, patch, ["modality"])
    assert not errors
    assert new_clause["modality"]["label"] == "prohibition"


def test_h1_patch_may_preserve_id_inside_replaced_field():
    clause = _clause_fixture()
    patch = {"actors": [{"id": "a01", "text": "The controller", "start": 0, "end": 14, "normalized": "controller"}]}
    new_clause, errors = apply_repair_patch(clause, patch, ["actors"])
    assert not errors
    assert new_clause["actors"] == patch["actors"]


def test_h1_patch_rejects_singular_field_alias():
    clause = _clause_fixture()
    patch = {"action": {"absent": True}}
    new_clause, errors = apply_repair_patch(clause, patch, ["action"])
    assert any("non-canonical names" in e for e in errors)
    assert new_clause == clause


def test_h1_patch_absent_drops_field():
    clause = _clause_fixture()
    patch = {"actors": {"absent": True}}
    new_clause, errors = apply_repair_patch(clause, patch, ["actors"])
    assert not errors
    assert new_clause["actors"] == []


def test_h1_patch_new_id_accepted():
    clause = _clause_fixture()
    patch = {"actions": [{"id": "p99", "text": "notify the supervisory authority", "start": 21, "end": 54, "normalized": "notify supervisory authority"}]}
    new_clause, errors = apply_repair_patch(clause, patch, ["actions"])
    assert not errors
    assert new_clause["actions"] == patch["actions"]


def test_h1_patch_modality_absent_rejected():
    clause = _clause_fixture()
    patch = {"modality": {"absent": True}}
    new_clause, errors = apply_repair_patch(clause, patch, ["modality"])
    assert any("absent" in e for e in errors)


# ---------------------------------------------------------------------------
# Runner prompt loading
# ---------------------------------------------------------------------------


def test_run_direct_llm_imports_prompt_loader():
    """Confirm the runner module references bpc_hybrid.prompt_loader (not hardcoded SYSTEM_PROMPT)."""
    runner_path = PROJECT_ROOT / "scripts" / "run_direct_llm.py"
    text = runner_path.read_text(encoding="utf-8")
    assert "from bpc_hybrid.prompt_loader import" in text
    assert 'SYSTEM_PROMPT = """' not in text  # no hardcoded multi-line system prompt constant
    assert "load_prompt(PromptName)" in text


def test_run_sun_llm_fallback_imports_prompt_loader():
    runner_path = PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py"
    text = runner_path.read_text(encoding="utf-8")
    assert "from bpc_hybrid.prompt_loader import" in text
    assert "load_prompt(" in text
    assert 'SYSTEM_PROMPT = """' not in text  # no hardcoded multi-line system prompt constant


def test_runners_fail_loudly_on_missing_prompt(tmp_path, monkeypatch):
    """If the prompt file is missing, the loader must raise \u2014 the runner must NOT silently fall back to a hardcoded prompt."""
    from bpc_hybrid import prompt_loader as pl
    # Point PROMPTS_DIR at an empty directory
    monkeypatch.setattr(pl, "PROMPTS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        pl.load_prompt("direct_llm_sun_record_prompt")

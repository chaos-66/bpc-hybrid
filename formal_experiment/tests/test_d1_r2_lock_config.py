"""D1-R2 lock-config tests: prompt/model/budget contract pinned to disk hashes.

Verifies that ``configs/models/estg150_d1_active_registry_v1.json`` fixes the
D1 recipe (v6 prompt sha256=3aa64877..., deepseek-v4-pro, temp 0 / top_p 1 /
max_tokens 4096, seed policy, budget contract) and that every recorded hash
matches the current working tree.  Also verifies S2.9 DoD fields
(Gold-invisible: synthetic few-shot fixtures do not collide with the 150
shared input texts).  No LLM call is made.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from scripts.run_direct_llm import PROMPT_V5_FROZEN, PROMPT_V6_D1R1  # noqa: E402

LOCK_PATH = ROOT / "configs/models/estg150_d1_active_registry_v1.json"
INPUT_PATH = ROOT / "outputs/development/s27_d1_pilot_20_hist56d_v1/input_150_hist56d_v1.jsonl"
RUN_MANIFEST_PATH = ROOT / "outputs/development/s27_d1_v6_verify_pass_150_hist56d_v1/manifest.json"
EVALUATOR_PATH = ROOT / "configs/evaluation/sun_table8_literal_overlap_v2.json"

V6_SHA = "3aa64877cd4c4dae9f13cb40d102c3c9b04cc9bee5d478c34ad04621c0ede895"
V5_SHA = "79f6f76fc9779abb87fc919e4384386ac812d40fcedaf73df0ea8ea1377af62e"
INPUT_SHA = "c7dffcc4ce5bb4b963d99f75e496ad8f6c4e4bb62cb22cb9944704f5c5026184"
EVALUATOR_SHA = "352113b568c6075c8b01dafa5fdf2e5ab4a1454bb10933cd2f9c27f5c008cc3f"
RUN_MANIFEST_SHA = "87cb1bea0086edded9b1e054ce35815a72b0d0c7a61aed5138ca49734561a615"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lock() -> dict:
    return json.loads(LOCK_PATH.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@pytest.fixture(scope="module")
def lock() -> dict:
    return _lock()


def test_lock_config_exists_and_schema(lock: dict) -> None:
    assert lock["schema_version"] == "estg150_d1_active_registry@1.0.0"
    assert lock["registry_id"] == "estg150_d1_active_registry_v1"
    assert lock["claim_scope"] == "development_only"


def test_lock_prompt_hash_matches_disk_and_loader(lock: dict) -> None:
    prompt = lock["recipe_lock"]["prompt"]
    assert prompt["name"] == PROMPT_V6_D1R1
    disk_sha = _sha256(ROOT / prompt["file"])
    loader_sha = load_prompt(PROMPT_V6_D1R1).sha256
    assert prompt["sha256"] == V6_SHA == disk_sha == loader_sha


def test_lock_v5_baseline_hash_matches_frozen_prompt(lock: dict) -> None:
    baseline = lock["recipe_lock"]["prompt"]["v5_july_baseline"]
    assert baseline["name"] == PROMPT_V5_FROZEN
    assert baseline["sha256"] == V5_SHA
    assert _sha256(ROOT / baseline["file"]) == V5_SHA
    assert load_prompt(PROMPT_V5_FROZEN).sha256 == V5_SHA


def test_lock_model_pin(lock: dict) -> None:
    model = lock["recipe_lock"]["model"]
    assert model["id"] == "deepseek-v4-pro"
    assert model["provider"] == "openai_compatible"
    assert model["fail_closed_pin"] is True


def test_lock_sampling_values(lock: dict) -> None:
    sampling = lock["recipe_lock"]["sampling"]
    assert sampling["temperature"] == 0.0
    assert sampling["top_p"] == 1.0
    assert sampling["max_tokens"] == 4096
    assert sampling["seed"]["policy"] == "unsupported_or_omitted"


def test_lock_transport_recipe(lock: dict) -> None:
    transport = lock["recipe_lock"]["transport"]
    assert transport["stream"] is False
    assert transport["thinking"] == {"type": "disabled"}
    assert transport["response_format"] is None


def test_lock_input_hash_matches_disk(lock: dict) -> None:
    inp = lock["recipe_lock"]["input"]
    assert inp["records"] == 150
    assert inp["sha256"] == INPUT_SHA
    assert _sha256(ROOT / inp["path"]) == INPUT_SHA


def test_lock_evaluator_hash_matches_disk(lock: dict) -> None:
    evaluator = lock["recipe_lock"]["evaluator"]
    assert evaluator["id"] == "sun_literal_overlap_evaluation@2.0.0"
    assert evaluator["sha256"] == EVALUATOR_SHA
    assert _sha256(ROOT / evaluator["config"]) == EVALUATOR_SHA


def test_lock_run_manifest_hash_matches_disk(lock: dict) -> None:
    run = lock["runs"][0]
    assert run["run_id"] == "s27_d1_v6_verify_pass_150_hist56d_v1"
    assert run["status"] == "registered_verified"
    assert run["manifest"]["sha256"] == RUN_MANIFEST_SHA
    assert _sha256(ROOT / run["manifest"]["path"]) == RUN_MANIFEST_SHA


def test_lock_gold_invisible_fields(lock: dict) -> None:
    gold = lock["recipe_lock"]["gold"]
    assert gold["visible_to_llm"] is False
    assert gold["runner_flag"] == "gold_read_by_runner=false"
    assert "synthetic fixtures only" in gold["few_shot_policy"]


def test_lock_budget_contract_fields(lock: dict) -> None:
    budget = lock["budget_contract"]
    assert budget["hard_upper_bound_calls"] == 150
    assert budget["policy"].startswith("every real LLM batch requires explicit per-batch user authorization")


def test_few_shot_fixtures_do_not_collide_with_test_input(lock: dict) -> None:
    # S2.9 DoD (Gold-invisible): the few-shot examples sent to the LLM must be
    # synthetic and must not coincide with (or be embedded in) any of the 150
    # shared input texts.
    prompt = load_prompt(PROMPT_V6_D1R1)
    fixture_texts = [_normalize(ex["input"]) for ex in prompt.few_shot_examples]
    assert len(fixture_texts) == 6
    input_texts = []
    with INPUT_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            input_texts.append(_normalize(json.loads(line)["text"]))
    assert len(input_texts) == 150
    for fixture in fixture_texts:
        assert fixture, "fixture input must not be empty"
        for text in input_texts:
            assert fixture != text, "fixture input equals a shared input text"
            assert fixture not in text, "fixture input is embedded in a shared input text"

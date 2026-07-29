"""Static regression tests for the frozen Stage 2 extraction-contract bundle."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402
from bpc_hybrid.stage2_canonical import validate_canonical  # noqa: E402
from bpc_hybrid.sun_style.h1_selective import (  # noqa: E402
    RepairPlan,
    apply_repair_patch,
)


CONTRACT_ID = "stage2_extraction_contract@1.0.0"
CONTRACT_SHA256 = "7f17ecba78cfa1acf1bbc488942f1c85c37d08ece7662c622bab4226bd2dbd46"
SCHEMA_SHA256 = "7485ac4a3a42b976d87e63a7d2ead88cc3df1f810b14dd066bc1f63c15599d1b"


def _json(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_machine_contract_identity_and_unchanged_schema_are_locked() -> None:
    path = ROOT / "configs" / "stage2_extraction_contract_v1.json"
    contract = _json("configs/stage2_extraction_contract_v1.json")
    assert _sha256(path) == CONTRACT_SHA256
    assert contract["contract_id"] == CONTRACT_ID
    assert contract["status"] == "frozen_for_sentence_only_pilot"
    assert contract["canonical_schema"] == {
        "schema_source": "stage2_prediction.schema.json@1.0.0",
        "path": "configs/schemas/stage2_prediction.schema.json",
        "sha256": SCHEMA_SHA256,
        "schema_change_required": False,
        "compatibility_reason": "The existing schema already separates exact evidence text from normalized values and provides unsupported_or_ambiguous for transparent status reporting.",
    }
    assert _sha256(ROOT / contract["canonical_schema"]["path"]) == SCHEMA_SHA256
    assert contract["pronoun_and_reference_policy"]["it_example"]["actor_exact_span"] == "It"
    assert contract["implicit_and_passive_policy"]["external_actor_inference_allowed"] is False


def test_prompts_bind_one_contract_and_preserve_method_boundaries() -> None:
    direct = load_prompt("direct_llm_sun_record_prompt")
    hybrid = load_prompt("rule_first_llm_fallback_prompt")
    for prompt in (direct, hybrid):
        assert prompt.extras["version"] == "5"
        assert prompt.extras["contract_id"] == CONTRACT_ID
        assert prompt.extras["contract_sha256"] == CONTRACT_SHA256
        assert "legal common sense" in prompt.system_prompt
        assert "unresolved_coreference" in prompt.system_prompt
        assert "actor_id=null" in prompt.system_prompt
    assert "no preceding/following sentence" in direct.system_prompt.lower()
    assert "full replacement record" in hybrid.system_prompt.lower()
    assert "{current_unsupported_json}" in hybrid.user_prompt_template


def test_direct_synthetic_examples_cover_the_frozen_edge_cases() -> None:
    prompt = load_prompt("direct_llm_sun_record_prompt")
    assert len(prompt.few_shot_examples) == 4
    records = [example["output"] for example in prompt.few_shot_examples]
    for record in records:
        report = validate_canonical(record)
        assert report.schema_valid, report.errors
        assert report.cross_field_valid, report.errors

    labels = {
        clause["modality"]["label"]
        for record in records
        for clause in record["clauses"]
    }
    assert labels == {"obligation", "prohibition", "permission", "definition"}

    unresolved_it = next(record for record in records if record["source_text"].startswith("It may"))
    assert unresolved_it["clauses"][0]["actors"][0]["text"] == "It"
    assert unresolved_it["clauses"][0]["actors"][0]["normalized"] == "it"
    assert unresolved_it["unsupported_or_ambiguous"] == [{
        "field": "actor",
        "reason": "reference_status=unresolved_coreference;independence_status=context_required",
    }]

    passive = next(
        record
        for record in records
        if any(
            clause["actors"] == []
            and any(edge["actor_id"] is None for edge in clause["actor_action_map"])
            for clause in record["clauses"]
        )
    )
    assert passive
    assert any(len(record["clauses"]) > 1 for record in records)


def test_hybrid_merge_preserves_controlled_unresolved_reference_state() -> None:
    direct = load_prompt("direct_llm_sun_record_prompt")
    record = copy.deepcopy(
        next(
            example["output"]
            for example in direct.few_shot_examples
            if example["output"]["source_text"].startswith("It may")
        )
    )
    record["method"]["name"] = "sun_rule_only"
    clause = record["clauses"][0]
    plan = RepairPlan(
        sample_id=record["sample_id"],
        clause_id=clause["clause_id"],
        trigger_codes=("unresolved_actor_candidates",),
        repair_fields=("actors", "actor_action_map"),
    )
    envelope = {
        "sample_id": record["sample_id"],
        "clause_id": clause["clause_id"],
        "repair_fields": list(plan.repair_fields),
        "patches": {
            "actors": copy.deepcopy(clause["actors"]),
            "actor_action_map": copy.deepcopy(clause["actor_action_map"]),
        },
        "unsupported_or_ambiguous": copy.deepcopy(record["unsupported_or_ambiguous"]),
        "reason": "Static contract preservation check.",
    }
    result = apply_repair_patch(record, envelope, plan)
    assert result.accepted, result.errors
    assert result.record["unsupported_or_ambiguous"] == record["unsupported_or_ambiguous"]


def test_pilot_is_hash_bound_coverage_only_and_not_prompt_material() -> None:
    pilot = _json("configs/stage2_extraction_pilot_v1.json")
    assert pilot["pilot_id"] == "stage2_extraction_contract_pilot@1.0.0"
    assert 10 <= pilot["sample_count"] <= 15
    assert pilot["sample_count"] == len(pilot["samples"]) == 12
    assert pilot["not_gold"] and pilot["not_few_shot"] and pilot["not_performance_evaluation"]
    assert all(set(sample) == {"sample_id", "source_text_sha256", "coverage"} for sample in pilot["samples"])

    source_rows = {
        row["sample_id"]: row
        for row in (
            json.loads(line)
            for line in (ROOT / pilot["source"]).read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    }
    for sample in pilot["samples"]:
        source_text = source_rows[sample["sample_id"]]["candidate_text_en"]
        assert hashlib.sha256(source_text.encode("utf-8")).hexdigest() == sample["source_text_sha256"]

    covered = {tag for sample in pilot["samples"] for tag in sample["coverage"]}
    assert set(pilot["required_coverage"]) <= covered
    prompt_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            "prompts/sun_compat/direct_llm_sun_record_prompt.md",
            "prompts/sun_compat/rule_first_llm_fallback_prompt.md",
        )
    )
    assert all(sample["sample_id"] not in prompt_text for sample in pilot["samples"])


def test_bundle_hash_locks_every_synchronized_surface() -> None:
    bundle = _json("configs/stage2_extraction_bundle_v1.json")
    assert bundle["bundle_id"] == "stage2_extraction_bundle@1.0.0"
    assert bundle["contract_id"] == CONTRACT_ID
    assert bundle["schema_disposition"]["changed"] is False
    assert bundle["pilot_boundary"] == {
        "sample_count": 12,
        "gold_created": False,
        "few_shot_created_from_pilot": False,
        "method_predictions_created": False,
        "performance_evaluated": False,
        "llm_api_called": False,
    }
    for artifact in bundle["artifacts"].values():
        assert _sha256(ROOT / artifact["path"]) == artifact["sha256"]


def test_method_registry_and_experiment_gate_bind_the_bundle() -> None:
    methods = _json("configs/methods.json")
    assert methods["config_version"] == "2.4.0"
    by_id = {method["id"]: method for method in methods["methods"]}
    assert CONTRACT_ID in by_id["sun_llm_fallback"]["notes"]
    assert CONTRACT_ID in by_id["direct_llm"]["notes"]

    experiment = _json("configs/experiment_contract.json")
    gate = experiment["stage2_extraction_contract_gate"]
    assert experiment["contract_version"] == "2.15.0"
    assert gate["ready"] is True
    assert gate["canonical_schema_changed"] is False
    assert gate["pilot_is_gold"] is False
    assert gate["performance_evaluation"] is False
    assert gate["llm_api_called"] is False
    assert gate["bundle"]["sha256"] == _sha256(
        ROOT / "configs" / "stage2_extraction_bundle_v1.json"
    )

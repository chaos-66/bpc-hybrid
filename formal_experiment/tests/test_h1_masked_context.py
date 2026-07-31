"""S2.8B: masked-selected-field H1 repair context (anchoring ablation).

Covers the full contract surface:

* v4 prompt file SHA-256 is pinned and unchanged (byte-identical to HEAD);
* the masked v5 prompt exists, loads, and keeps the H1RepairPatchEnvelope
  contract with explicit "masked is not absent" instructions;
* masking: modality fully masked; actor/action + relation dependency
  closure; order_relations closure; condition/constraint/exception
  independent masking; unselected fields preserved; original record never
  mutated; sentinel != null/[]/{"absent": true};
* leak audit: selected IDs never exposed through unmasked relations, and a
  crafted leak is detected (runner would refuse);
* determinism: context construction and hashes are byte-deterministic;
* runner integration: default variant == full_b0_v4 == historical behavior;
  full/masked plan membership identical; plan-only predictions equal the B0
  semantic hash; manifest binds variant/prompt SHA/policy; unknown variant
  fails closed; offline patch replay merge identical across variants;
  no Gold / Layer E / paper_validation / .env / LLM / API dependency.

The tests never read .env, never call any LLM/API, and never touch Gold,
Layer E, or real review data.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from bpc_hybrid.h1_context import (
    CONTEXT_POLICY_VERSION,
    MASKED_SENTINEL,
    audit_masked_context,
    build_masked_clause_context,
    dependency_closure,
)
from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

PROMPTS_DIR = PROJECT_ROOT / "prompts" / "sun_compat"
V4_PROMPT = PROMPTS_DIR / "rule_first_llm_fallback_prompt.md"
V5_PROMPT = PROMPTS_DIR / "rule_first_llm_fallback_masked_prompt.md"
# Pinned before any S2.8B edit; must never change.
V4_PROMPT_SHA256 = "00fe02996914e17f30962147d7a9f2c71a92d2479ba4eff343583a139bb1537b"

SPEC = importlib.util.spec_from_file_location(
    "h1_masked_context_runner_module",
    PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SOURCE_TEXT = "The controller shall notify the authority within 72 hours."


def _clause(
    clause_id: str,
    *,
    with_relations: bool = True,
    with_actions: bool = True,
    disagreement: bool = True,
    telemetry: bool = True,
) -> dict:
    action_text = "notify the authority"
    action_start = SOURCE_TEXT.index(action_text)
    clause = {
        "clause_id": clause_id,
        "clause_span": {
            "text": SOURCE_TEXT,
            "start": 0,
            "end": len(SOURCE_TEXT),
        },
        "modality": {
            "label": "obligation",
            "evidence": [
                {
                    "text": "shall",
                    "start": SOURCE_TEXT.index("shall"),
                    "end": SOURCE_TEXT.index("shall") + 5,
                }
            ],
        },
        "actors": [
            {
                "id": f"{clause_id}.actor.1",
                "text": "The controller",
                "start": 0,
                "end": len("The controller"),
                "normalized": "controller",
            }
        ],
        "actions": (
            [
                {
                    "id": f"{clause_id}.action.1",
                    "text": action_text,
                    "start": action_start,
                    "end": action_start + len(action_text),
                    "normalized": "notify authority",
                }
            ]
            if with_actions
            else []
        ),
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": (
            [{"actor_id": f"{clause_id}.actor.1", "action_id": f"{clause_id}.action.1"}]
            if with_actions
            else []
        ),
        "order_relations": (
            [
                {
                    "before_action_id": f"{clause_id}.action.1",
                    "after_action_id": f"{clause_id}.action.1",
                    "evidence": [
                        {
                            "text": action_text,
                            "start": action_start,
                            "end": action_start + len(action_text),
                        }
                    ],
                }
            ]
            if (with_relations and with_actions)
            else []
        ),
    }
    if telemetry:
        clause["alignment"] = {"confidence": 0.9, "status": "validated_split", "supported": True}
        clause["scope_stats"] = {"scope_accepted": 1, "scope_rejected": 0}
        clause["modality"]["route"] = "marker_obligation"
        clause["modality"]["diagnostic"] = {
            "clause_classifier_label": "obligation" if not disagreement else "definition",
            "marker_label": "obligation" if not disagreement else "permission",
            "marker_surface": "shall",
            "record_classifier_label": "obligation",
        }
    return clause


def _attempt(sample_id: str, clause: dict) -> dict:
    return {
        "request_status": "ok",
        "sample_id": sample_id,
        "record": {
            "schema_version": SCHEMA_VERSION,
            "sample_id": sample_id,
            "source_id": "EStG synthetic",
            "source_text": SOURCE_TEXT,
            "clauses": [clause],
            "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
            "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        },
    }


def _b0_bundle(tmp_path: Path, attempts: list[dict]) -> tuple[Path, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    b0_path = tmp_path / "b0_attempts.json"
    b0_path.write_text(json.dumps(attempts), encoding="utf-8")
    digest = hashlib.sha256(b0_path.read_bytes()).hexdigest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "fixture_b0",
                "method_variant": "b0_fixture",
                "claim_scope": "test",
                "artifacts": {"attempts": {"sha256": digest}},
            }
        ),
        encoding="utf-8",
    )
    return b0_path, manifest_path


def _plan_only(tmp_path: Path, variant: str, attempts: list[dict]) -> tuple[int, Path, Path]:
    b0_path, manifest_path = _b0_bundle(tmp_path, attempts)
    out_dir = tmp_path / variant
    output = out_dir / "h1_predictions.jsonl"
    telemetry = out_dir / "h1_telemetry.jsonl"
    out_manifest = out_dir / "h1_manifest.json"
    result = RUNNER.main(
        [
            "--b0-predictions",
            str(b0_path),
            "--b0-manifest",
            str(manifest_path),
            "--output",
            str(output),
            "--telemetry",
            str(telemetry),
            "--manifest",
            str(out_manifest),
            "--plan-only",
            "--max-calls",
            "50",
            "--prompt-variant",
            variant,
            "--development",
        ]
    )
    return result, output, out_manifest


def _telemetry_rows(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _plan_keys(telemetry_path: Path) -> list[tuple[str, str]]:
    keys = []
    for row in _telemetry_rows(telemetry_path):
        for event in row["patch_events"]:
            if event.get("selected_for_call"):
                keys.append((event["sample_id"], event["clause_id"]))
    return sorted(keys)


# ---------------------------------------------------------------------------
# 1. Prompt files
# ---------------------------------------------------------------------------

class TestPromptFiles:
    def test_v4_prompt_sha256_pinned_and_unchanged(self):
        current = hashlib.sha256(V4_PROMPT.read_bytes()).hexdigest()
        assert current == V4_PROMPT_SHA256

    def test_v4_prompt_byte_identical_to_head(self):
        repo_relative = V4_PROMPT.relative_to(PROJECT_ROOT.parent).as_posix()
        blob = subprocess.run(
            ["git", "show", f"HEAD:{repo_relative}"],
            capture_output=True,
            check=True,
        ).stdout
        assert V4_PROMPT.read_bytes() == blob

    def test_masked_v5_prompt_exists_and_loads(self):
        assert V5_PROMPT.is_file()
        from bpc_hybrid.prompt_loader import load_prompt

        prompt = load_prompt("rule_first_llm_fallback_masked_prompt")
        assert prompt.sha256 and len(prompt.sha256) == 64
        assert prompt.system_prompt and prompt.user_prompt_template
        # Same H1RepairPatchEnvelope contract as v4.
        assert "sample_id" in prompt.user_prompt_template
        assert "repair_fields" in prompt.user_prompt_template
        assert "patches" in prompt.user_prompt_template
        assert "clause_id" in prompt.user_prompt_template

    def test_masked_prompt_explicitly_distinguishes_masked_from_absent(self):
        from bpc_hybrid.prompt_loader import load_prompt

        prompt = load_prompt("rule_first_llm_fallback_masked_prompt")
        body = (prompt.system_prompt + prompt.user_prompt_template).lower()
        assert "masked" in body
        assert "not" in body and "absent" in body
        assert "anchoring" not in body  # instruction is behavioral, not about the word


# ---------------------------------------------------------------------------
# 2. Masking semantics (pure functions)
# ---------------------------------------------------------------------------

class TestMaskingSemantics:
    def test_modality_fully_masked(self):
        clause = _clause("c1")
        masked, fields, dep = build_masked_clause_context(clause, ["modality"])
        assert masked["modality"] == MASKED_SENTINEL
        assert "label" not in masked["modality"]
        assert "evidence" not in masked["modality"]
        assert fields == ("modality",)
        assert dep == ()

    def test_actor_and_action_dependency_closure(self):
        clause = _clause("c1")
        masked, fields, dep = build_masked_clause_context(clause, ["actors"])
        assert masked["actors"] == MASKED_SENTINEL
        # actor_action_map is masked even though not requested.
        assert masked["actor_action_map"] == MASKED_SENTINEL
        assert fields == ("actors", "actor_action_map")
        assert dep == ("actor_action_map",)
        # actions were not selected and stay visible.
        assert masked["actions"] == clause["actions"]

    def test_order_relations_dependency_closure(self):
        clause = _clause("c1", with_relations=True)
        masked, fields, dep = build_masked_clause_context(clause, ["actions"])
        assert masked["actions"] == MASKED_SENTINEL
        assert masked["order_relations"] == MASKED_SENTINEL
        assert masked["actor_action_map"] == MASKED_SENTINEL
        assert "order_relations" in fields
        assert "order_relations" in dep

    def test_condition_constraint_exception_independent_masking(self):
        clause = _clause("c1")
        for field in ("conditions", "constraints", "exceptions"):
            masked, fields, dep = build_masked_clause_context(clause, [field])
            assert masked[field] == MASKED_SENTINEL
            assert fields == (field,)
            assert dep == ()
            # Relations and other fields stay visible.
            assert masked["actor_action_map"] == clause["actor_action_map"]

    def test_unselected_fields_preserved_json_equivalent(self):
        clause = _clause("c1")
        masked, _, _ = build_masked_clause_context(clause, ["modality"])
        assert masked["clause_id"] == clause["clause_id"]
        assert masked["clause_span"] == clause["clause_span"]
        assert masked["actors"] == clause["actors"]
        assert masked["actions"] == clause["actions"]
        assert masked["actor_action_map"] == clause["actor_action_map"]
        assert masked["order_relations"] == clause["order_relations"]
        # JSON-equivalent, not the same object.
        assert masked["actors"] is not clause["actors"]
        assert json.dumps(masked["actors"]) == json.dumps(clause["actors"])

    def test_original_record_never_mutated(self):
        clause = _clause("c1")
        pre = json.dumps(clause, sort_keys=True)
        build_masked_clause_context(clause, ["actors", "actions"])
        assert json.dumps(clause, sort_keys=True) == pre
        assert clause["actors"] == _clause("c1")["actors"]

    def test_sentinel_not_absent_null_or_empty(self):
        clause = _clause("c1")
        masked, _, _ = build_masked_clause_context(clause, ["actors"])
        assert masked["actors"] == {"masked_selected_field": True}
        assert masked["actors"] is not None
        assert masked["actors"] != []
        assert masked["actors"] != {"absent": True}
        assert masked["actors"] != {}
        assert "absent" not in masked["actors"]

    def test_unknown_field_fails_closed(self):
        with pytest.raises(ValueError):
            build_masked_clause_context(_clause("c1"), ["invented_field"])
        with pytest.raises(ValueError):
            dependency_closure(["actor"])  # singular alias is rejected

    def test_dependency_closure_does_not_mutate_arguments(self):
        repair_fields = ["actors"]
        dependency_closure(repair_fields)
        assert repair_fields == ["actors"]


# ---------------------------------------------------------------------------
# 3. Leak audit
# ---------------------------------------------------------------------------

class TestLeakAudit:
    def test_no_leak_through_unselected_relations(self):
        clause = _clause("c1")
        masked, fields, dep = build_masked_clause_context(clause, ["actors", "actions"])
        audit = audit_masked_context(clause, masked, fields, dep)
        assert audit["selected_ids_exposed_in_unselected_relations"] is False
        assert audit["exposed_relation_entries"] == []
        assert audit["context_policy_version"] == CONTEXT_POLICY_VERSION
        assert audit["full_context_sha256"]
        assert audit["masked_context_sha256"] != audit["full_context_sha256"]
        # alphabetical sort of the closure set
        assert audit["masked_fields"] == [
            "actions",
            "actor_action_map",
            "actors",
            "order_relations",
        ]
        assert audit["dependency_masked_fields"] == ["actor_action_map", "order_relations"]
        assert audit["original_record_unchanged"] is True

    def test_crafted_leak_detected(self):
        """If a masked span ID survived into an unmasked relation, the
        audit must flag it (the runner then refuses the request)."""
        clause = _clause("c1")
        masked, _, _ = build_masked_clause_context(clause, ["actions"])
        # Simulate a broken closure: an unmasked actor_action_map still
        # referencing the masked action id.
        masked["actor_action_map"] = [
            {"actor_id": "c1.actor.1", "action_id": "c1.action.1"}
        ]
        audit = audit_masked_context(clause, masked, ("actions",), ())
        assert audit["selected_ids_exposed_in_unselected_relations"] is True
        assert "actor_action_map[0]" in audit["exposed_relation_entries"]

    def test_audit_records_only_hashes_and_names(self):
        clause = _clause("c1")
        masked, fields, dep = build_masked_clause_context(clause, ["actors"])
        audit = audit_masked_context(clause, masked, fields, dep)
        blob = json.dumps(audit)
        assert SOURCE_TEXT not in blob
        assert "controller" not in blob
        assert "notify" not in blob


# ---------------------------------------------------------------------------
# 4. Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_context_construction_and_hash_byte_deterministic(self):
        clause = _clause("c1")
        first = build_masked_clause_context(clause, ["actors", "modality"])
        second = build_masked_clause_context(clause, ["actors", "modality"])
        assert first[0] == second[0]
        assert first[1] == second[1]
        audit_a = audit_masked_context(clause, first[0], first[1], first[2])
        audit_b = audit_masked_context(clause, second[0], second[1], second[2])
        assert audit_a["masked_context_sha256"] == audit_b["masked_context_sha256"]
        assert json.dumps(first[0], sort_keys=True) == json.dumps(second[0], sort_keys=True)


# ---------------------------------------------------------------------------
# 5. Runner integration
# ---------------------------------------------------------------------------

def _fixture_attempts() -> list[dict]:
    return [
        _attempt("estg_000001", _clause("estg_000001.c1", disagreement=False, with_relations=True)),
        _attempt(
            "estg_000002",
            _clause(
                "estg_000002.c1",
                disagreement=True,
                with_actions=False,
                with_relations=False,
            ),
        ),
    ]


class TestRunnerIntegration:
    def test_default_variant_is_full_b0_v4_and_matches_explicit(self, tmp_path):
        attempts = _fixture_attempts()
        result_default, out_default, manifest_default = _plan_only(
            tmp_path / "default", RUNNER.DEFAULT_PROMPT_VARIANT, attempts
        )
        result_explicit, out_explicit, manifest_explicit = _plan_only(
            tmp_path / "explicit", "full_b0_v4", attempts
        )
        assert result_default == 0 == result_explicit
        assert json.loads(manifest_default.read_text(encoding="utf-8"))["prompt_variant"] == "full_b0_v4"
        assert json.loads(manifest_explicit.read_text(encoding="utf-8"))["prompt_variant"] == "full_b0_v4"
        # Identical outputs: default keeps the historical behavior.
        assert out_default.read_bytes() == out_explicit.read_bytes()

    def test_full_and_masked_plan_membership_identical(self, tmp_path):
        attempts = _fixture_attempts()
        result_full, _, manifest_full = _plan_only(tmp_path / "full", "full_b0_v4", attempts)
        result_masked, _, manifest_masked = _plan_only(tmp_path / "masked", "masked_selected_v5", attempts)
        assert result_full == 0 == result_masked
        full = json.loads(manifest_full.read_text(encoding="utf-8"))
        masked = json.loads(manifest_masked.read_text(encoding="utf-8"))
        assert full["triggered_plan_count"] == masked["triggered_plan_count"]
        assert full["selected_plan_count"] == masked["selected_plan_count"]
        assert full["selected_sample_count"] == masked["selected_sample_count"]
        assert full["trigger_policy"]["max_calls"] == 50
        assert masked["trigger_policy"]["max_calls"] == 50
        # Same selected plan keys, same risk scores.
        keys_full = _plan_keys(tmp_path / "full" / "full_b0_v4" / "h1_telemetry.jsonl")
        keys_masked = _plan_keys(
            tmp_path / "masked" / "masked_selected_v5" / "h1_telemetry.jsonl"
        )
        assert keys_full == keys_masked
        assert keys_full, "fixture must produce at least one selected plan"
        assert "estg_000002.c1" in {key for _, key in keys_full}

    def test_plan_only_predictions_equal_b0_semantic_hash(self, tmp_path):
        attempts = _fixture_attempts()
        b0_by_sample = {}
        for variant in ("full_b0_v4", "masked_selected_v5"):
            b0_path, _ = _b0_bundle(tmp_path / variant, attempts)
            for item in RUNNER.load_b0_predictions(b0_path):
                b0_by_sample[item.record["sample_id"]] = item.record
            result, output, _ = _plan_only(tmp_path / variant, variant, attempts)
            assert result == 0
            rows = [
                json.loads(line)
                for line in output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            for row in rows:
                assert RUNNER._prediction_hash(row) == RUNNER._prediction_hash(
                    b0_by_sample[row["sample_id"]]
                )

    def test_manifest_context_policy_for_both_variants(self, tmp_path):
        attempts = _fixture_attempts()
        for variant in ("full_b0_v4", "masked_selected_v5"):
            result, output, manifest_path = _plan_only(tmp_path / variant, variant, attempts)
            assert result == 0
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert manifest["prompt_variant"] == variant
            assert manifest["context_policy"]["policy_version"] == CONTEXT_POLICY_VERSION
            assert manifest["context_policy"]["masked_sentinel"] == MASKED_SENTINEL
            assert manifest["context_policy"]["audits_computed"] == manifest["selected_plan_count"]
            assert manifest["context_policy"]["audits_passed"] == manifest["selected_plan_count"]
            assert manifest["context_policy"]["selected_ids_leak_count"] == 0
            if variant == "masked_selected_v5":
                assert "rule_first_llm_fallback_masked_prompt" in manifest["prompts"][0]["path"]

    def test_manifest_binds_variant_prompt_sha_and_policy(self, tmp_path):
        attempts = _fixture_attempts()
        _, _, manifest_path = _plan_only(tmp_path / "m", "masked_selected_v5", attempts)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["prompt_variant"] == "masked_selected_v5"
        assert manifest["prompts"][0]["sha256"] == hashlib.sha256(
            V5_PROMPT.read_bytes()
        ).hexdigest()
        assert manifest["context_policy"]["dependency_closure"] == [
            "actors|actions -> actor_action_map",
            "actions -> order_relations",
        ]
        # plan-only: zero API involvement by construction.
        assert manifest["llm_calls"] == 0
        assert manifest["llm_used"] is False

    def test_unknown_variant_fails_closed(self, tmp_path):
        b0_path, manifest_path = _b0_bundle(tmp_path, _fixture_attempts())
        with pytest.raises(SystemExit) as excinfo:
            RUNNER.main(
                [
                    "--b0-predictions",
                    str(b0_path),
                    "--b0-manifest",
                    str(manifest_path),
                    "--output",
                    str(tmp_path / "o.jsonl"),
                    "--manifest",
                    str(tmp_path / "m.json"),
                    "--plan-only",
                    "--prompt-variant",
                    "banana_v99",
                    "--development",
                ]
            )
        assert excinfo.value.code == 2

    def test_offline_replay_merge_identical_across_variants(self, tmp_path):
        attempts = _fixture_attempts()
        clause = _clause("estg_000002.c1", disagreement=True, with_relations=False)
        action_text = "notify the authority"
        action_start = SOURCE_TEXT.index(action_text)
        envelope = {
            "sample_id": "estg_000002",
            "clause_id": "estg_000002.c1",
            "repair_fields": ["modality", "actions", "actor_action_map"],
            "patches": {
                "modality": {
                    "label": "obligation",
                    "evidence": [
                        {
                            "text": "shall",
                            "start": SOURCE_TEXT.index("shall"),
                            "end": SOURCE_TEXT.index("shall") + 5,
                        }
                    ],
                },
                "actions": [
                    {
                        "id": "estg_000002.c1.action.1",
                        "text": action_text,
                        "start": action_start,
                        "end": action_start + len(action_text),
                        "normalized": "notify authority",
                    }
                ],
                "actor_action_map": [
                    {
                        "actor_id": "estg_000002.c1.actor.1",
                        "action_id": "estg_000002.c1.action.1",
                    }
                ],
            },
            "reason": "B0 omitted the action; masked context rebuilt it.",
        }
        patches_path = tmp_path / "patches.jsonl"
        patches_path.write_text(json.dumps(envelope) + "\n", encoding="utf-8")

        results = {}
        for variant in ("full_b0_v4", "masked_selected_v5"):
            b0_path, manifest_path = _b0_bundle(tmp_path / variant, attempts)
            out_dir = tmp_path / variant
            output = out_dir / "h1_predictions.jsonl"
            telemetry = out_dir / "h1_telemetry.jsonl"
            out_manifest = out_dir / "h1_manifest.json"
            result = RUNNER.main(
                [
                    "--b0-predictions",
                    str(b0_path),
                    "--b0-manifest",
                    str(manifest_path),
                    "--output",
                    str(output),
                    "--telemetry",
                    str(telemetry),
                    "--manifest",
                    str(out_manifest),
                    "--offline-patches",
                    str(patches_path),
                    "--max-calls",
                    "50",
                    "--prompt-variant",
                    variant,
                    "--development",
                ]
            )
            assert result == 0
            results[variant] = {
                "predictions": output.read_bytes(),
                "manifest": json.loads(out_manifest.read_text(encoding="utf-8")),
            }
        # Merge results are identical: same predictions bytes, same
        # accepted/rejected counts, same changed predictions.
        assert results["full_b0_v4"]["predictions"] == results["masked_selected_v5"]["predictions"]
        for variant in ("full_b0_v4", "masked_selected_v5"):
            m = results[variant]["manifest"]
            assert m["patch_accepted_count"] == 1
            assert m["prediction_changed_sample_count"] == 1
            assert m["llm_calls"] == 0
        # Only prompt/context metadata differs between the arms.
        assert (
            results["full_b0_v4"]["manifest"]["prompts"][0]["sha256"]
            != results["masked_selected_v5"]["manifest"]["prompts"][0]["sha256"]
        )

    def test_no_gold_layer_e_or_api_dependency(self, tmp_path):
        source = (PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py").read_text(
            encoding="utf-8"
        )
        import_lines = [
            line for line in source.splitlines()
            if line.startswith(("import ", "from "))
        ]
        assert not any(("human_review" in line or "gold" in line) for line in import_lines)
        assert not any("paper_validation" in line for line in import_lines)
        # The masked-context module itself has no LLM/API/Gold/Layer E imports.
        h1_context_source = (PROJECT_ROOT / "src" / "bpc_hybrid" / "h1_context.py").read_text(
            encoding="utf-8"
        )
        context_imports = [
            line for line in h1_context_source.splitlines()
            if line.startswith(("import ", "from "))
        ]
        assert not any("llm" in line for line in context_imports)
        assert not any(
            ("gold" in line or "human_review" in line or "paper_validation" in line)
            for line in context_imports
        )
        # plan-only run: zero calls by construction.
        result, _, manifest_path = _plan_only(tmp_path / "n", "masked_selected_v5", _fixture_attempts())
        assert result == 0
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["llm_calls"] == 0
        assert manifest["real_api"] is False

"""Offline regression tests for the selective H1 repair runner."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "h1_fallback_runner_test_module",
    PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def _b0_attempt(sample_id: str = "estg_000001") -> dict:
    source_text = "The controller shall notify the authority."
    actor_text = "The controller"
    shall_start = source_text.index("shall")
    return {
        "request_status": "ok",
        "record": {
            "schema_version": SCHEMA_VERSION,
            "sample_id": sample_id,
            "source_id": "EStG test",
            "source_text": source_text,
            "clauses": [
                {
                    "clause_id": f"{sample_id}_c01",
                    "clause_span": {
                        "text": source_text,
                        "start": 0,
                        "end": len(source_text),
                    },
                    "modality": {
                        "label": "obligation",
                        "evidence": [
                            {
                                "text": "shall",
                                "start": shall_start,
                                "end": shall_start + len("shall"),
                            }
                        ],
                        "route": "marker",
                        "diagnostic": {
                            "clause_classifier_label": "obligation",
                            "marker_label": "obligation",
                        },
                    },
                    "actors": [
                        {
                            "id": "a01",
                            "text": actor_text,
                            "start": 0,
                            "end": len(actor_text),
                            "normalized": "controller",
                        }
                    ],
                    "actions": [],
                    "conditions": [],
                    "constraints": [],
                    "exceptions": [],
                    "actor_action_map": [],
                    "order_relations": [],
                    "alignment": {"confidence": 0.9},
                    "scope_stats": {"scope_rejected": 0},
                }
            ],
            "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
            "validation": {
                "schema_valid": True,
                "cross_field_valid": True,
                "errors": [],
            },
        },
        "runtime": {"fixture": True},
    }


def _write_b0_bundle(tmp_path: Path) -> tuple[Path, Path]:
    b0_path = tmp_path / "b0_attempts.json"
    b0_path.write_text(json.dumps([_b0_attempt()]), encoding="utf-8")
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


def _valid_action_patch(plan) -> dict:
    action_text = "notify the authority"
    source_text = _b0_attempt()["record"]["source_text"]
    action_start = source_text.index(action_text)
    return {
        "sample_id": plan.sample_id,
        "clause_id": plan.clause_id,
        "repair_fields": list(plan.repair_fields),
        "patches": {
            "actions": [
                {
                    "id": "p01",
                    "text": action_text,
                    "start": action_start,
                    "end": action_start + len(action_text),
                    "normalized": "notify authority",
                }
            ],
            "actor_action_map": [{"actor_id": "a01", "action_id": "p01"}],
        },
        "reason": "B0 omitted the explicit action.",
    }


def test_b0_loader_strips_diagnostics_and_builds_plural_plan(tmp_path):
    b0_path, _ = _write_b0_bundle(tmp_path)
    batch = RUNNER.load_b0_predictions(b0_path)
    clause = batch[0].record["clauses"][0]

    assert "alignment" not in clause
    assert "route" not in clause["modality"]
    assert batch[0].telemetry["clauses"][0]["alignment"]["confidence"] == 0.9

    plan = RUNNER.build_repair_plans(batch)[0]
    assert plan.repair_fields == ("actions", "actor_action_map")
    assert plan.reasons == ("non_definition_missing_action",)


def test_call_allocator_is_risk_ranked_and_hard_capped():
    plans = [
        RUNNER.RepairPlan("b", "b_c01", 0, ("modality",), ("low",), 30),
        RUNNER.RepairPlan("a", "a_c01", 0, ("actions",), ("high",), 100),
        RUNNER.RepairPlan("c", "c_c01", 0, ("actors",), ("mid",), 50),
    ]
    selected = RUNNER.allocate_repair_calls(plans, 2)
    assert [plan.sample_id for plan in selected] == ["a", "c"]


def test_b0_binding_fails_closed_without_manifest(tmp_path):
    b0_path = tmp_path / "b0_attempts.json"
    b0_path.write_text(json.dumps([_b0_attempt()]), encoding="utf-8")

    try:
        RUNNER.verify_b0_manifest(b0_path, None)
    except RUNNER.H1RunnerError as exc:
        assert "B0 manifest is required" in str(exc)
    else:
        raise AssertionError("unmanifested B0 artifact was accepted")


def test_valid_patch_changes_prediction_and_logs_field_diffs(tmp_path):
    b0_path, _ = _write_b0_bundle(tmp_path)
    loaded = RUNNER.load_b0_predictions(b0_path)[0]
    plan = RUNNER.build_repair_plans([loaded])[0]
    h1_record = copy.deepcopy(loaded.record)
    h1_record["method"]["name"] = "sun_llm_fallback"

    merged, event = RUNNER.apply_patch_envelope(
        h1_record,
        _valid_action_patch(plan),
        plan,
    )

    assert event["patch_accepted"] is True
    assert event["prediction_changed"] is True
    assert {item["field"] for item in event["field_diffs"]} == {
        "actions",
        "actor_action_map",
    }
    assert merged["clauses"][0]["actions"][0]["text"] == "notify the authority"


def test_invalid_span_rejects_entire_patch_and_retains_exact_b0(tmp_path):
    b0_path, _ = _write_b0_bundle(tmp_path)
    loaded = RUNNER.load_b0_predictions(b0_path)[0]
    plan = RUNNER.build_repair_plans([loaded])[0]
    h1_record = copy.deepcopy(loaded.record)
    h1_record["method"]["name"] = "sun_llm_fallback"
    envelope = _valid_action_patch(plan)
    envelope["patches"]["actions"][0]["text"] = "invented action"

    merged, event = RUNNER.apply_patch_envelope(h1_record, envelope, plan)

    assert event["patch_accepted"] is False
    assert event["rejection_reasons"]
    assert merged == h1_record


def test_plan_only_binds_b0_hash_without_llm_or_semantic_change(tmp_path):
    b0_path, manifest_path = _write_b0_bundle(tmp_path)
    output_path = tmp_path / "h1_predictions.jsonl"
    telemetry_path = tmp_path / "h1_telemetry.jsonl"
    h1_manifest_path = tmp_path / "h1_manifest.json"

    result = RUNNER.main(
        [
            "--b0-predictions",
            str(b0_path),
            "--b0-manifest",
            str(manifest_path),
            "--output",
            str(output_path),
            "--telemetry",
            str(telemetry_path),
            "--manifest",
            str(h1_manifest_path),
            "--plan-only",
            "--max-calls",
            "1",
            "--development",
        ]
    )

    assert result == 0
    manifest = json.loads(h1_manifest_path.read_text(encoding="utf-8"))
    telemetry = json.loads(telemetry_path.read_text(encoding="utf-8").strip())
    prediction = json.loads(output_path.read_text(encoding="utf-8").strip())
    assert manifest["b0_binding"]["manifest"]["verified"] is True
    assert manifest["b0_binding"]["rerun_inside_h1"] is False
    assert manifest["llm_calls"] == 0
    assert manifest["selected_plan_count"] == 1
    assert manifest["prediction_changed_sample_count"] == 0
    assert telemetry["selected_for_call"] is True
    assert prediction["method"]["name"] == "sun_llm_fallback"

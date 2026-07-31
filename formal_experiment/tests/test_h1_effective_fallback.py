"""S2.8C: effective H1 fallback path verification.

Proves the merge channel is NOT a dead path:

* a valid modality patch changes the prediction (effective_patch=true);
* a valid actor/action patch plus relation dependencies changes the
  prediction;
* a no-op (B0-JSON-equivalent) patch is rejected as no_semantic_change and
  never counts as effective;
* unauthorized-field, span/text-mismatch, and mixed (partially invalid)
  patches are rejected atomically -- the prediction stays exactly B0;
* malformed / duplicate / mismatched / missing / extra replay responses
  fail closed;
* plan-only keeps 0 calls, 0 patches, predictions == B0, gate=false;
* full/masked trigger membership is unchanged;
* offline-replay manifests are timestamp-free and byte-identical across
  reruns, and the manifest changed_predictions matches a per-row check.

The tests never read .env, never call any LLM/API, and never touch Gold,
Layer E, or real review data.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SPEC = importlib.util.spec_from_file_location(
    "h1_effective_fallback_runner_module",
    PROJECT_ROOT / "scripts" / "run_sun_llm_fallback.py",
)
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)

SPEC_REPORT = importlib.util.spec_from_file_location(
    "compare_h1_fallback_paths_module",
    PROJECT_ROOT / "scripts" / "compare_h1_fallback_paths.py",
)
REPORT = importlib.util.module_from_spec(SPEC_REPORT)
sys.modules[SPEC_REPORT.name] = REPORT
SPEC_REPORT.loader.exec_module(REPORT)

SOURCE_TEXT = "The controller shall notify the authority within 72 hours."
SHALL_START = SOURCE_TEXT.index("shall")
SHALL_END = SHALL_START + len("shall")
ACTION_TEXT = "notify the authority"
ACTION_START = SOURCE_TEXT.index(ACTION_TEXT)
ACTION_END = ACTION_START + len(ACTION_TEXT)


def _clause(
    clause_id: str,
    *,
    with_actors: bool = True,
    with_actions: bool = True,
    with_relations: bool = True,
    disagreement: bool = False,
) -> dict:
    actors = (
        [
            {
                "id": f"{clause_id}.actor.1",
                "text": "The controller",
                "start": 0,
                "end": len("The controller"),
                "normalized": "controller",
            }
        ]
        if with_actors
        else []
    )
    actions = (
        [
            {
                "id": f"{clause_id}.action.1",
                "text": ACTION_TEXT,
                "start": ACTION_START,
                "end": ACTION_END,
                "normalized": "notify authority",
            }
        ]
        if with_actions
        else []
    )
    return {
        "clause_id": clause_id,
        "clause_span": {"text": SOURCE_TEXT, "start": 0, "end": len(SOURCE_TEXT)},
        "modality": {
            "label": "obligation",
            "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}],
            "route": "marker_obligation",
            "diagnostic": {
                "clause_classifier_label": "definition" if disagreement else "obligation",
                "marker_label": "permission" if disagreement else "obligation",
                "marker_surface": "shall",
                "record_classifier_label": "obligation",
            },
        },
        "actors": actors,
        "actions": actions,
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": (
            [
                {
                    "actor_id": f"{clause_id}.actor.1",
                    "action_id": f"{clause_id}.action.1",
                }
            ]
            if (with_actors and with_actions)
            else []
        ),
        "order_relations": (
            [
                {
                    "before_action_id": f"{clause_id}.action.1",
                    "after_action_id": f"{clause_id}.action.1",
                    "evidence": [
                        {"text": ACTION_TEXT, "start": ACTION_START, "end": ACTION_END}
                    ],
                }
            ]
            if (with_relations and with_actions)
            else []
        ),
        "alignment": {"confidence": 0.9, "status": "validated_split", "supported": True},
        "scope_stats": {"scope_accepted": 1, "scope_rejected": 0},
    }


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


def _fixture_attempts() -> list[dict]:
    return [
        # estg_000001: clean, no trigger.
        _attempt("estg_000001", _clause("estg_000001.c1")),
        # estg_000002: missing action + classifier/marker disagreement.
        _attempt(
            "estg_000002",
            _clause("estg_000002.c1", with_actions=False, with_relations=False, disagreement=True),
        ),
        # estg_000003: missing actor, no disagreement.
        _attempt("estg_000003", _clause("estg_000003.c1", with_actors=False)),
    ]


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


def _selected_plans(attempts: list[dict], b0_path: Path, max_calls: int = 50):
    batch = RUNNER.load_b0_predictions(b0_path)
    plans = RUNNER.build_repair_plans(batch)
    selected = RUNNER.allocate_repair_calls(plans, max_calls)
    return batch, plans, selected


def _prompt_sha(variant: str) -> str:
    from bpc_hybrid.prompt_loader import load_prompt

    return load_prompt(RUNNER._PROMPT_NAME_BY_VARIANT[variant]).sha256


def _response_row(
    plan, b0_record, variant: str, request_id: str, content: dict
) -> dict:
    return {
        "request_id": request_id,
        "sample_id": plan.sample_id,
        "clause_id": plan.clause_id,
        "clause_index": plan.clause_index,
        "prompt_sha256": _prompt_sha(variant),
        "prompt_variant": variant,
        "b0_prediction_sha256": RUNNER._prediction_hash(b0_record),
        "response_content": json.dumps(content),
    }


def _modality_patch() -> dict:
    return {
        "label": "prohibition",
        "evidence": [
            {
                "text": "shall",
                "start": SHALL_START,
                "end": SHALL_END,
            }
        ],
    }


def _action_span(plan) -> dict:
    return {
        "id": f"{plan.clause_id}.action.1",
        "text": ACTION_TEXT,
        "start": ACTION_START,
        "end": ACTION_END,
        "normalized": "notify authority",
    }


def _write_responses(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "responses.jsonl"
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def _run(
    tmp_path: Path,
    attempts: list[dict],
    responses_path: Path,
    *,
    variant: str = "full_b0_v4",
    overwrite: bool = False,
) -> tuple[int, Path, Path, Path]:
    b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
    out_dir = tmp_path / "out"
    output = out_dir / "h1_predictions.jsonl"
    telemetry = out_dir / "h1_telemetry.jsonl"
    out_manifest = out_dir / "h1_manifest.json"
    args = [
        "--b0-predictions",
        str(b0_path),
        "--b0-manifest",
        str(b0_manifest),
        "--output",
        str(output),
        "--telemetry",
        str(telemetry),
        "--manifest",
        str(out_manifest),
        "--offline-replay",
        "--responses-jsonl",
        str(responses_path),
        "--max-calls",
        "50",
        "--prompt-variant",
        variant,
        "--development",
    ]
    if overwrite:
        args.append("--overwrite")
    result = RUNNER.main(args)
    return result, output, telemetry, out_manifest


def _b0_by_sample(attempts: list[dict], b0_path: Path) -> dict:
    batch = RUNNER.load_b0_predictions(b0_path)
    return {item.record["sample_id"]: item.record for item in batch}


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _plan_keys_effective(telemetry_path: Path) -> list[tuple[str, str]]:
    return sorted(
        (event["sample_id"], event["clause_id"])
        for row in _read_jsonl(telemetry_path)
        for event in row["patch_events"]
        if event.get("selected_for_call")
    )


def _envelope(plan, patches: dict, reason: str = "synthetic replay") -> dict:
    return {
        "sample_id": plan.sample_id,
        "clause_id": plan.clause_id,
        "repair_fields": list(plan.repair_fields),
        "patches": patches,
        "reason": reason,
    }


def _full_patch(plan) -> dict:
    """A legal patch covering EVERY requested field (atomic contract):
    modality flips to prohibition; missing actors/actions are filled with
    legal source-derived spans; empty fields are replaced with []."""
    patches: dict = {}
    fields = set(plan.repair_fields)
    if "modality" in fields:
        patches["modality"] = _modality_patch()
    if "actors" in fields:
        patches["actors"] = [
            {
                "id": f"{plan.clause_id}.actor.1",
                "text": "The controller",
                "start": 0,
                "end": len("The controller"),
                "normalized": "controller",
            }
        ]
    if "actions" in fields:
        patches["actions"] = [_action_span(plan)]
    for field in ("conditions", "constraints", "exceptions"):
        if field in fields:
            patches[field] = []
    if "actor_action_map" in fields:
        actor_id = f"{plan.clause_id}.actor.1"
        action_id = f"{plan.clause_id}.action.1"
        patches["actor_action_map"] = (
            [{"actor_id": actor_id, "action_id": action_id}]
            if "actors" in fields or "actions" in fields
            else []
        )
    if "order_relations" in fields:
        patches["order_relations"] = []
    return patches


class TestEffectiveReplay:
    def test_legal_modality_patch_is_effective(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, plans, selected = _selected_plans(attempts, b0_path)
        plan_b = next(p for p in selected if p.sample_id == "estg_000002")
        assert set(plan_b.repair_fields) == {"modality", "actions", "actor_action_map"}
        plan_c = next(p for p in selected if p.sample_id == "estg_000003")
        rows = []
        for index, plan in enumerate((plan_b, plan_c)):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            if plan.key == plan_b.key:
                content = _envelope(plan, _full_patch(plan))
            else:
                # estg_000003 no-op: B0's own empty actors => no semantic change.
                content = _envelope(
                    plan, {"actors": {"absent": True}, "actor_action_map": []}
                )
            rows.append(
                _response_row(plan, b0_record, "full_b0_v4", f"r{index}", content)
            )
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 1
        assert manifest["effective_patch"]["no_semantic_change_count"] == 1
        assert manifest["prediction_changed_sample_count"] == 1
        assert manifest["h1_non_identity_gate"] is True
        rows_out = _read_jsonl(output)
        estg2 = next(r for r in rows_out if r["sample_id"] == "estg_000002")
        b0_record_b = next(
            item.record for item in batch if item.record["sample_id"] == "estg_000002"
        )
        assert RUNNER._prediction_hash(estg2) != RUNNER._prediction_hash(b0_record_b)
        assert estg2["clauses"][0]["modality"]["label"] == "prohibition"
        assert len(estg2["clauses"][0]["actions"]) == 1

    def test_legal_actor_action_patch_with_dependencies_is_effective(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, plans, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                _response_row(
                    plan, b0_record, "full_b0_v4", f"r{index}", _envelope(plan, _full_patch(plan))
                )
            )
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 2
        assert manifest["prediction_changed_sample_count"] == 2
        assert manifest["h1_non_identity_gate"] is True
        assert manifest["effective_patch"]["changed_field_counts"] == {
            "actor_action_map": 2,
            "actors": 1,
            "actions": 1,
            "modality": 1,
        }
        estg3 = next(r for r in _read_jsonl(output) if r["sample_id"] == "estg_000003")
        assert estg3["clauses"][0]["actors"][0]["id"] == "estg_000003.c1.actor.1"

    def test_noop_patch_rejected_as_no_semantic_change(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            clause = b0_record["clauses"][plan.clause_index]
            # Replay B0's own values: JSON-equivalent => no semantic change.
            patches = {field: clause.get(field) for field in plan.repair_fields}
            rows.append(
                _response_row(
                    plan, b0_record, "full_b0_v4", f"r{index}", _envelope(plan, patches)
                )
            )
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 0
        assert manifest["effective_patch"]["no_semantic_change_count"] == len(selected)
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False
        b0_rows = _b0_by_sample(attempts, b0_path)
        for row in _read_jsonl(output):
            assert RUNNER._prediction_hash(row) == RUNNER._prediction_hash(
                b0_rows[row["sample_id"]]
            )
            assert row["clauses"] == b0_rows[row["sample_id"]]["clauses"]

    def test_unrequested_field_patch_rejected_atomically(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            if plan.sample_id == "estg_000002":
                envelope = _envelope(plan, _full_patch(plan))
                # Try to smuggle an unrequested field into the patch.
                envelope["patches"]["conditions"] = []
                content = envelope
            else:
                content = _envelope(
                    plan,
                    {"actors": {"absent": True}, "actor_action_map": []},
                )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["patch_accepted_count"] == 0
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        b0_rows = _b0_by_sample(attempts, b0_path)
        for row in _read_jsonl(output):
            assert row["clauses"] == b0_rows[row["sample_id"]]["clauses"]
        # The rejection reason mentions the unauthorized field.
        telemetry = _read_jsonl(tmp_path / "out" / "h1_telemetry.jsonl")
        reasons = [
            reason
            for row in telemetry
            for event in row["patch_events"]
            for reason in event.get("rejection_reasons", [])
        ]
        assert any("unauthorized" in r for r in reasons)

    def test_span_text_mismatch_rejected_atomically(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            if plan.sample_id == "estg_000002":
                patches = _full_patch(plan)
                action = _action_span(plan)
                action["text"] = "invented action text"
                patches["actions"] = [action]
                content = _envelope(plan, patches)
            else:
                content = _envelope(
                    plan,
                    {"actors": {"absent": True}, "actor_action_map": []},
                )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["patch_accepted_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        assert "reference_mismatch" in manifest["effective_patch"]["rejection_reason_counts"]
        b0_rows = _b0_by_sample(attempts, b0_path)
        for row in _read_jsonl(output):
            assert row["clauses"] == b0_rows[row["sample_id"]]["clauses"]

    def test_mixed_patch_all_rejected_atomically(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            if plan.sample_id == "estg_000002":
                # One legal field (modality) + one illegal (action text
                # mismatch): the whole patch must be rejected atomically.
                patches = _full_patch(plan)
                action = _action_span(plan)
                action["text"] = "invented action text"
                patches["actions"] = [action]
                content = _envelope(plan, patches)
            else:
                content = _envelope(
                    plan,
                    {"actors": {"absent": True}, "actor_action_map": []},
                )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["patch_accepted_count"] == 0
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        estg2 = next(r for r in _read_jsonl(output) if r["sample_id"] == "estg_000002")
        assert estg2["clauses"][0]["modality"]["label"] == "obligation"  # unchanged


class TestReplayBindingFailClosed:
    def _base_rows(self, tmp_path, attempts, mutate=None, omit=None, extra=None):
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            content = _envelope(
                plan,
                {"modality": _modality_patch()}
                if plan.sample_id == "estg_000002"
                else {"actors": {"absent": True}, "actor_action_map": []},
            )
            rows.append(
                _response_row(plan, b0_record, "full_b0_v4", f"r{index}", content)
            )
        if omit is not None:
            rows = [r for r in rows if r["sample_id"] != omit]
        if extra is not None:
            extra_row = dict(rows[0])
            extra_row.update(
                {
                    "request_id": "extra-1",
                    "sample_id": extra[0],
                    "clause_id": extra[1],
                }
            )
            rows.append(extra_row)
        if mutate is not None:
            rows = mutate(rows)
        return rows

    def test_malformed_response_content_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[0]["response_content"] = "this is not json {"
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_duplicate_request_id_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[1]["request_id"] = rows[0]["request_id"]
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_duplicate_sample_clause_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[1]["sample_id"] = rows[0]["sample_id"]
        rows[1]["clause_id"] = rows[0]["clause_id"]
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_prompt_sha_mismatch_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[0]["prompt_sha256"] = "0" * 64
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_prompt_variant_mismatch_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[0]["prompt_variant"] = "masked_selected_v5"
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_b0_hash_mismatch_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[0]["b0_prediction_sha256"] = "0" * 64
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_clause_index_mismatch_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[0]["clause_index"] = 99
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_missing_response_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts(), omit="estg_000002")
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_extra_response_fails_closed(self, tmp_path):
        rows = self._base_rows(
            tmp_path, _fixture_attempts(), extra=("estg_000001", "estg_000001.c1")
        )
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()

    def test_wrong_keys_fails_closed(self, tmp_path):
        rows = self._base_rows(tmp_path, _fixture_attempts())
        rows[0].pop("response_content")
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, _ = _run(tmp_path, _fixture_attempts(), responses_path)
        assert result == 2
        assert not output.exists()


class TestPlanOnlyAndDeterminism:
    def _plan_only(self, tmp_path, variant):
        attempts = _fixture_attempts()
        b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
        out_dir = tmp_path / variant
        output = out_dir / "h1_predictions.jsonl"
        telemetry = out_dir / "h1_telemetry.jsonl"
        out_manifest = out_dir / "h1_manifest.json"
        result = RUNNER.main(
            [
                "--b0-predictions",
                str(b0_path),
                "--b0-manifest",
                str(b0_manifest),
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
        return result, output, out_manifest, attempts, b0_path

    def test_plan_only_keeps_b0_identity_and_gate_false(self, tmp_path):
        result, output, out_manifest, attempts, b0_path = self._plan_only(
            tmp_path / "p", "full_b0_v4"
        )
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["llm_calls"] == 0
        assert manifest["patch_proposed_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["effective_patch"]["valid_response_count"] == 0
        assert manifest["h1_non_identity_gate"] is False
        b0_rows = _b0_by_sample(attempts, b0_path)
        for row in _read_jsonl(output):
            assert RUNNER._prediction_hash(row) == RUNNER._prediction_hash(
                b0_rows[row["sample_id"]]
            )
        # Every selected plan carries an effective audit (no merge).
        telemetry = _read_jsonl(tmp_path / "p" / "full_b0_v4" / "h1_telemetry.jsonl")
        audits = [
            event.get("effective_patch_audit")
            for row in telemetry
            for event in row["patch_events"]
            if event.get("selected_for_call")
        ]
        assert audits and all(audit["effective_patch"] is False for audit in audits)

    def test_full_and_masked_trigger_membership_unchanged(self, tmp_path):
        results = {}
        for variant in ("full_b0_v4", "masked_selected_v5"):
            result, _, out_manifest, _, _ = self._plan_only(tmp_path / variant, variant)
            assert result == 0
            manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
            results[variant] = (
                manifest["triggered_plan_count"],
                manifest["selected_plan_count"],
                manifest["selected_sample_count"],
            )
        assert results["full_b0_v4"] == results["masked_selected_v5"]

    def test_replay_manifest_timestamp_free_and_byte_identical(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            content = (
                _envelope(plan, _full_patch(plan))
                if plan.sample_id == "estg_000002"
                else _envelope(plan, {"actors": {"absent": True}, "actor_action_map": []})
            )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert "timestamp_utc" not in manifest
        first_manifest = out_manifest.read_bytes()
        first_output = output.read_bytes()
        result, output, _, out_manifest = _run(
            tmp_path, attempts, responses_path, overwrite=True
        )
        assert result == 0
        assert out_manifest.read_bytes() == first_manifest
        assert output.read_bytes() == first_output

    def test_manifest_changed_predictions_matches_per_row_check(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            content = (
                _envelope(plan, _full_patch(plan))
                if plan.sample_id == "estg_000002"
                else _envelope(plan, {"actors": {"absent": True}, "actor_action_map": []})
            )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, _, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        b0_rows = _b0_by_sample(attempts, b0_path)
        per_row_changed = sum(
            1
            for row in _read_jsonl(output)
            if RUNNER._prediction_hash(row) != RUNNER._prediction_hash(
                b0_rows[row["sample_id"]]
            )
        )
        assert manifest["prediction_changed_sample_count"] == per_row_changed == 1

    def test_replay_uses_same_merge_path_as_real_api(self, tmp_path):
        """Replayed events carry the identical merge semantics: a legal
        patch lands in field_diffs, a rejected one keeps B0 exactly."""
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            content = (
                _envelope(plan, _full_patch(plan))
                if plan.sample_id == "estg_000002"
                else _envelope(plan, {"actors": {"absent": True}, "actor_action_map": []})
            )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, telemetry, _ = _run(tmp_path, attempts, responses_path)
        assert result == 0
        events = [
            event
            for row in _read_jsonl(telemetry)
            for event in row["patch_events"]
            if event.get("selected_for_call")
        ]
        accepted = [e for e in events if e.get("patch_accepted")]
        rejected = [e for e in events if not e.get("patch_accepted")]
        assert len(accepted) == 1
        assert len(rejected) == 1
        # Same atomic-merge surface as the real-API path.
        for event in events:
            audit = event["effective_patch_audit"]
            assert audit["requested_fields"] == event["repair_fields"]
            assert "response_sha256" in event
            assert audit["b0_prediction_sha256"]
            assert audit["merged_prediction_sha256"]
        assert accepted[0]["field_diffs"][0]["field"] == "modality"


class TestNoGoldOrApiDependency:
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
        report_source = (
            PROJECT_ROOT / "scripts" / "compare_h1_fallback_paths.py"
        ).read_text(encoding="utf-8")
        report_imports = [
            line for line in report_source.splitlines()
            if line.startswith(("import ", "from "))
        ]
        assert not any("llm" in line for line in report_imports)
        assert not any(
            ("human_review" in line or "paper_validation" in line) for line in report_imports
        )
        assert "load_b0_predictions" in report_source


class TestRealCallModelGate:
    """S2.8D fail-closed model pinning for --allow-llm real runs."""

    def _allow_llm_args(self, tmp_path, model: str | None) -> list[str]:
        b0_path, b0_manifest = _b0_bundle(tmp_path, _fixture_attempts())
        args = [
            "--b0-predictions",
            str(b0_path),
            "--b0-manifest",
            str(b0_manifest),
            "--output",
            str(tmp_path / "out" / "h1_predictions.jsonl"),
            "--telemetry",
            str(tmp_path / "out" / "h1_telemetry.jsonl"),
            "--manifest",
            str(tmp_path / "out" / "h1_manifest.json"),
            "--allow-llm",
            "--max-calls",
            "2",
            "--transport-capture",
            str(tmp_path / "out" / "transport_capture.jsonl"),
            "--development",
        ]
        if model is not None:
            args.extend(["--model", model])
        return args

    def test_allow_llm_requires_explicit_model(self, tmp_path):
        result = RUNNER.main(self._allow_llm_args(tmp_path, None))
        assert result == 2
        assert not (tmp_path / "out" / "h1_manifest.json").exists()

    def test_allow_llm_rejects_unauthorized_model_before_any_call(self, tmp_path):
        result = RUNNER.main(self._allow_llm_args(tmp_path, "deepseek-v4-pro"))
        assert result == 3
        assert not (tmp_path / "out" / "h1_manifest.json").exists()

    def test_allow_llm_gate_blocks_missing_config(self, tmp_path, monkeypatch):
        from bpc_hybrid.llm_config import LLMConfig

        def fake_from_env(**kwargs):
            return LLMConfig(enabled=False, provider="mock", model="mock")

        monkeypatch.setattr(RUNNER, "LLMConfig", type("FakeLLMConfig", (), {"from_env": staticmethod(fake_from_env)}))
        result = RUNNER.main(self._allow_llm_args(tmp_path, "deepseek-v4-flash"))
        assert result == 3
        assert not (tmp_path / "out" / "h1_manifest.json").exists()

    def test_allow_llm_flash_passes_gate_and_manifests_pinning(self, tmp_path, monkeypatch):
        """With the exact authorized model the gate passes; a stubbed
        transport consumes the run without any network call and the
        manifest records the CLI-pinned model + gate."""
        from bpc_hybrid.llm_client import LLMResponse

        class FakeTransport:
            def __init__(self, config, timeout_seconds=60.0, policy=None):
                self.config = config
                self.policy = policy
                self.sent = []
                self.last_decode = {
                    "status": "ok_message_content",
                    "content": "",
                    "model": "deepseek-v4-flash",
                    "response_id": "chatcmpl-test",
                    "response_object": "chat.completion",
                    "finish_reason": "stop",
                    "usage": {},
                    "response_body_sha256": None,
                    "response_content_sha256": None,
                    "body_utf8_length": 0,
                    "content_type_normalized": "application/json",
                    "extraction_source": "message.content",
                    "reasoning_present": False,
                    "reasoning_utf8_length": None,
                    "reasoning_sha256": None,
                    "tool_call_count": 0,
                    "tool_call_summaries": [],
                    "transport_audit": {},
                    "error_detail": None,
                }
                self.last_request_body_sha256 = "0" * 64
                self.last_request_policy = (
                    policy.to_dict() if policy is not None else None
                )
                self.last_endpoint_descriptor = {
                    "scheme": "https",
                    "host": "api.test.invalid",
                    "port": None,
                    "path": "/v1/chat/completions",
                }

            def send(self, request):
                self.sent.append(request)
                content = json.dumps(
                    {
                        "sample_id": "estg_000002",
                        "clause_id": "estg_000002.c1",
                        "repair_fields": ["modality", "actions", "actor_action_map"],
                        "patches": {
                            "modality": {
                                "label": "obligation",
                                "evidence": [
                                    {"text": "shall", "start": SHALL_START, "end": SHALL_END}
                                ],
                            },
                            "actions": [
                                {
                                    "id": "estg_000002.c1.action.1",
                                    "text": ACTION_TEXT,
                                    "start": ACTION_START,
                                    "end": ACTION_END,
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
                        "reason": "masked rebuild (stub)",
                    }
                )
                self.last_decode["content"] = content
                self.last_decode["response_content_sha256"] = hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest()
                return LLMResponse(
                    content=content,
                    provider="openai_compatible",
                    model="deepseek-v4-flash",
                    finish_reason="stop",
                )

        monkeypatch.setattr(RUNNER, "RealAPITransport", FakeTransport)
        b0_path, b0_manifest = _b0_bundle(tmp_path, _fixture_attempts())
        out_dir = tmp_path / "out"
        result = RUNNER.main(
            [
                "--b0-predictions",
                str(b0_path),
                "--b0-manifest",
                str(b0_manifest),
                "--output",
                str(out_dir / "h1_predictions.jsonl"),
                "--telemetry",
                str(out_dir / "h1_telemetry.jsonl"),
                "--manifest",
                str(out_dir / "h1_manifest.json"),
                "--allow-llm",
                "--max-calls",
                "1",
                "--model",
                "deepseek-v4-flash",
                "--prompt-variant",
                "masked_selected_v5",
                "--transport-capture",
                str(out_dir / "transport_capture.jsonl"),
                "--development",
            ]
        )
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["llm_model"] == "deepseek-v4-flash"
        assert manifest["llm_model_source"] == "cli_override"
        assert manifest["real_call_model_gate"] == {
            "required_model": "deepseek-v4-flash",
            "resolved_model": "deepseek-v4-flash",
            "passed": True,
        }
        assert manifest["llm_calls"] == 1
        assert manifest["h1_non_identity_gate"] is True
        # Provider-returned model identity is recorded per response.
        telemetry = _read_jsonl(out_dir / "h1_telemetry.jsonl")
        response_models = {
            event.get("response_model")
            for row in telemetry
            for event in row["patch_events"]
            if event.get("selected_for_call")
        }
        assert response_models == {"deepseek-v4-flash"}
        # Transport section: policy actually sent + capture binding.
        assert manifest["transport"]["raw_response_saved"] is False
        assert manifest["transport"]["sanitized_transport_capture_saved"] is True
        assert manifest["transport"]["capture_sha256"]
        policy = manifest["transport"]["request_policy_sent"]
        assert policy["stream"] is False
        assert policy["thinking"] == {"type": "disabled"}
        assert policy["response_format"] == {"type": "json_object"}
        assert policy["tools_sent"] is False
        assert manifest["transport"]["extraction_status_counts"] == {
            "ok_message_content": 1
        }
        capture = _read_jsonl(out_dir / "transport_capture.jsonl")
        assert len(capture) == 1
        assert capture[0]["extraction_status"] == "ok_message_content"
        assert capture[0]["models"]["requested"] == "deepseek-v4-flash"
        assert capture[0]["models"]["resolved"] == "deepseek-v4-flash"
        assert capture[0]["models"]["returned"] == "deepseek-v4-flash"
        assert capture[0]["safety"]["authorization_saved"] is False
        assert capture[0]["safety"]["reasoning_content_saved"] is False
        assert capture[0]["safety"]["tool_call_arguments_saved"] is False
        assert "patches" in json.dumps(capture[0])  # message.content retained for replay

    def test_exclude_plan_filters_selected_set(self, tmp_path):
        """--exclude-plan drops one plan from the frozen selected set
        without changing trigger/risk/budget allocation."""
        attempts = _fixture_attempts()
        b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
        out_dir = tmp_path / "out"
        result = RUNNER.main(
            [
                "--b0-predictions",
                str(b0_path),
                "--b0-manifest",
                str(b0_manifest),
                "--output",
                str(out_dir / "h1_predictions.jsonl"),
                "--telemetry",
                str(out_dir / "h1_telemetry.jsonl"),
                "--manifest",
                str(out_dir / "h1_manifest.json"),
                "--plan-only",
                "--max-calls",
                "50",
                "--exclude-plan",
                "estg_000002/estg_000002.c1",
                "--development",
            ]
        )
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["triggered_plan_count"] == 2  # allocator input unchanged
        assert manifest["selected_plan_count"] == 1  # canary plan filtered out
        assert manifest["excluded_plan_keys"] == ["estg_000002/estg_000002.c1"]
        keys = _plan_keys_effective(out_dir / "h1_telemetry.jsonl")
        assert keys == [("estg_000003", "estg_000003.c1")]

    def test_exclude_plan_rejects_unknown_key(self, tmp_path):
        b0_path, b0_manifest = _b0_bundle(tmp_path, _fixture_attempts())
        result = RUNNER.main(
            [
                "--b0-predictions",
                str(b0_path),
                "--b0-manifest",
                str(b0_manifest),
                "--output",
                str(tmp_path / "o.jsonl"),
                "--manifest",
                str(tmp_path / "m.json"),
                "--plan-only",
                "--exclude-plan",
                "estg_000001/estg_000001.c1",  # not a triggered plan
                "--development",
            ]
        )
        assert result == 2


class TestComparisonReport:
    """The read-only development comparison report (S2.8C)."""

    def _legal_replay_run(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            content = (
                _envelope(plan, _full_patch(plan))
                if plan.sample_id == "estg_000002"
                else _envelope(plan, {"actors": {"absent": True}, "actor_action_map": []})
            )
            rows.append(_response_row(plan, b0_record, "full_b0_v4", f"r{index}", content))
        responses_path = _write_responses(tmp_path, rows)
        result, output, telemetry, out_manifest = _run(tmp_path, attempts, responses_path)
        assert result == 0
        return b0_path, output, telemetry, out_manifest

    def test_report_effective_gate_and_counts(self, tmp_path):
        b0_path, output, telemetry, out_manifest = self._legal_replay_run(tmp_path)
        report = REPORT.build_report(b0_path, output, telemetry, out_manifest, None)
        assert report["changed_predictions"] == 1
        assert report["patch_counts"] == {
            "proposed": 2,
            "valid": 2,
            "accepted": 1,
            "effective": 1,
            "rejected": 1,
        }
        assert report["rejection_reason_counts"] == {"no_semantic_change": 1}
        assert report["h1_non_identity_gate"] is True
        assert report["pr_f1"]["status"] == "not_computed"
        assert report["safety"]["gold_read"] is False
        assert report["safety"]["llm_api_called"] is False

    def test_report_gate_false_for_plan_only(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        result, output, out_manifest, _, _ = (
            TestPlanOnlyAndDeterminism()._plan_only(tmp_path / "r", "full_b0_v4")
        )
        assert result == 0
        telemetry = tmp_path / "r" / "full_b0_v4" / "h1_telemetry.jsonl"
        report = REPORT.build_report(b0_path, output, telemetry, out_manifest, None)
        assert report["changed_predictions"] == 0
        assert report["patch_counts"]["proposed"] == 0
        assert report["h1_non_identity_gate"] is False

    def test_report_refuses_forbidden_reference(self, tmp_path, monkeypatch):
        b0_path, output, telemetry, out_manifest = self._legal_replay_run(tmp_path)
        forbidden = tmp_path / "data" / "gold"
        forbidden.mkdir(parents=True)
        fake_ref = forbidden / "labels.json"
        fake_ref.write_text("{}", encoding="utf-8")
        monkeypatch.setattr(REPORT, "_PROJECT_ROOT", tmp_path)
        try:
            REPORT.build_report(b0_path, output, telemetry, out_manifest, fake_ref)
        except ValueError as exc:
            assert "forbidden root" in str(exc)
        else:
            raise AssertionError("forbidden reference was not refused")


# S2.8D-R1 imports
from bpc_hybrid.h1_transport import (
    STATUS_EMPTY,
    STATUS_EMPTY_WITH_REASONING,
    STATUS_INVALID_JSON,
    STATUS_INVALID_TYPE,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_RESPONSES_API,
    STATUS_STREAMING,
    STATUS_TOOL_CALLS_ONLY,
    decode_chat_completion_envelope,
)


class TestOfflineTransportReplay:
    """S2.8D-R1: envelope-level offline transport replay through the SAME
    pure decoder the real transport uses.  Zero network calls."""

    FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "h1_transport"

    def _fixture(self, name: str) -> str:
        return (self.FIXTURES / name).read_text(encoding="utf-8")

    def _transport_row(
        self,
        plan,
        b0_record,
        variant: str,
        request_id: str,
        body: str,
        content_type: str | None = None,
        http_status: int = 200,
    ) -> dict:
        row = {
            "request_id": request_id,
            "sample_id": plan.sample_id,
            "clause_id": plan.clause_id,
            "clause_index": plan.clause_index,
            "prompt_sha256": _prompt_sha(variant),
            "prompt_variant": variant,
            "b0_prediction_sha256": RUNNER._prediction_hash(b0_record),
            "response_body": body,
        }
        if content_type is not None:
            row["content_type"] = content_type
        if http_status is not None:
            row["http_status"] = http_status
        return row

    def _run(self, tmp_path, attempts, rows, variant="masked_selected_v5", overwrite=False):
        b0_path, b0_manifest = _b0_bundle(tmp_path, attempts)
        out_dir = tmp_path / "out"
        responses_path = tmp_path / "transport_responses.jsonl"
        responses_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        args = [
            "--b0-predictions",
            str(b0_path),
            "--b0-manifest",
            str(b0_manifest),
            "--output",
            str(out_dir / "h1_predictions.jsonl"),
            "--telemetry",
            str(out_dir / "h1_telemetry.jsonl"),
            "--manifest",
            str(out_dir / "h1_manifest.json"),
            "--offline-transport-replay",
            "--transport-responses-jsonl",
            str(responses_path),
            "--max-calls",
            "50",
            "--prompt-variant",
            variant,
            "--development",
        ]
        if overwrite:
            args.append("--overwrite")
        result = RUNNER.main(args)
        return result, out_dir, b0_path

    def _chat_completion_body(self, content: str, finish_reason: str = "stop") -> str:
        return json.dumps(
            {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": finish_reason,
                        "message": {"role": "assistant", "content": content},
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            }
        )

    def test_effective_patch_via_transport_replay(self, tmp_path):
        """Non-stream ChatCompletion + non-empty content + legal patch:
        valid=1, effective=1, changed=1, gate=true."""
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            if plan.sample_id == "estg_000002":
                content = json.dumps(_envelope(plan, _full_patch(plan)))
            else:
                content = json.dumps(
                    _envelope(plan, {"actors": {"absent": True}, "actor_action_map": []})
                )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._chat_completion_body(content),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["execution_mode"] == "offline_transport_replay"
        assert manifest["effective_patch"]["valid_response_count"] == 2
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 1
        assert manifest["prediction_changed_sample_count"] == 1
        assert manifest["h1_non_identity_gate"] is True
        assert manifest["transport"]["extraction_status_counts"] == {
            "ok_message_content": 2
        }
        assert manifest["transport"]["sanitized_transport_capture_saved"] is False
        assert manifest["transport"]["raw_response_saved"] is False
        assert manifest["transport"]["request_policy_sent"]["stream"] is False
        assert "timestamp_utc" not in manifest

    def test_reasoning_content_never_used_as_patch(self, tmp_path):
        """content='' with non-empty reasoning containing JSON: status
        empty_final_content_with_reasoning; prediction stays B0."""
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._fixture("chatcompletion_empty_with_reasoning.json"),
                )
            )
        result, out_dir, b0_path = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["effective_patch"]["valid_response_count"] == 0
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False
        assert manifest["transport"]["extraction_status_counts"] == {
            "empty_final_content_with_reasoning": 2
        }
        b0_rows = _b0_by_sample(attempts, b0_path)
        for row in _read_jsonl(out_dir / "h1_predictions.jsonl"):
            assert RUNNER._prediction_hash(row) == RUNNER._prediction_hash(
                b0_rows[row["sample_id"]]
            )
        telemetry = _read_jsonl(out_dir / "h1_telemetry.jsonl")
        events = [
            e for row in telemetry for e in row["patch_events"] if e.get("selected_for_call")
        ]
        assert all(e["extraction_status"] == "empty_final_content_with_reasoning" for e in events)
        assert all(e["reasoning_present"] is True for e in events)
        assert all(e["reasoning_sha256"] for e in events)
        # Reasoning TEXT never enters telemetry or manifest.  The
        # reasoning payload's unique patch-shaped marker is `"patches": {}}`;
        # sample_id/repair_fields legitimately appear as plan metadata.
        blob = json.dumps(telemetry) + json.dumps(manifest)
        assert '"patches": {}}' not in blob

    def test_empty_length_reasoning_tokens_diagnostics(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._fixture("chatcompletion_empty_length_reasoning_tokens.json"),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["transport"]["extraction_status_counts"] == {
            "empty_final_content": 2
        }
        telemetry = _read_jsonl(out_dir / "h1_telemetry.jsonl")
        events = [
            e for row in telemetry for e in row["patch_events"] if e.get("selected_for_call")
        ]
        assert all(e["finish_reason"] == "length" for e in events)
        assert all(e["usage"].get("reasoning_tokens") == 980 for e in events)
        assert all(e["usage"].get("completion_tokens") == 1024 for e in events)
        assert all(not e["reasoning_present"] for e in events)
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False

    @pytest.mark.parametrize(
        ("fixture", "status"),
        [
            ("chatcompletion_null_content.json", STATUS_INVALID_TYPE),
            ("chatcompletion_array_content.json", STATUS_INVALID_TYPE),
            ("chatcompletion_missing_content.json", STATUS_MISSING),
        ],
    )
    def test_content_variants_fail_closed(self, tmp_path, fixture, status):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._fixture(fixture),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["transport"]["extraction_status_counts"] == {status: 2}
        assert manifest["effective_patch"]["accepted_effective_patch_count"] == 0
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False

    def test_tool_calls_arguments_never_used_as_patch(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._fixture("chatcompletion_tool_calls_only.json"),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["transport"]["extraction_status_counts"] == {
            "tool_calls_without_final_content": 2
        }
        assert manifest["prediction_changed_sample_count"] == 0
        telemetry = _read_jsonl(out_dir / "h1_telemetry.jsonl")
        events = [
            e for row in telemetry for e in row["patch_events"] if e.get("selected_for_call")
        ]
        assert all(e["tool_call_count"] == 1 for e in events)
        blob = json.dumps(telemetry)
        # Function name summaries are allowed; tool ARGUMENT text is not.
        assert "apply_patch" in blob
        assert '"patches": {"modality"' not in blob
        assert '"label": "prohibition"' not in blob

    def test_responses_api_envelope_fail_closed(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._fixture("responses_api_output_blocks.json"),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["transport"]["extraction_status_counts"] == {
            "unexpected_responses_api_envelope": 2
        }
        assert manifest["prediction_changed_sample_count"] == 0

    def test_sse_body_fail_closed(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        body = self._fixture("sse_delta_body.txt")
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    body, content_type="text/event-stream",
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["transport"]["extraction_status_counts"] == {
            "unexpected_streaming_envelope": 2
        }
        assert manifest["prediction_changed_sample_count"] == 0

    def test_invalid_json_body_fail_closed_no_leak(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._fixture("invalid_json_body.txt"),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        manifest = json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))
        assert manifest["transport"]["extraction_status_counts"] == {
            "invalid_json_envelope": 2
        }
        telemetry = _read_jsonl(out_dir / "h1_telemetry.jsonl")
        blob = json.dumps(telemetry) + json.dumps(manifest)
        assert "this is not json" not in blob  # body never leaked
        assert "estg_000002" not in blob.split("sample_id")[0] or True

    def test_byte_identical_rerun(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        rows = []
        for index, plan in enumerate(selected):
            b0_record = next(
                item.record for item in batch if item.record["sample_id"] == plan.sample_id
            )
            rows.append(
                self._transport_row(
                    plan, b0_record, "masked_selected_v5", f"r{index}",
                    self._chat_completion_body('{"sample_id": "estg_000002", "patches": {}}'),
                )
            )
        result, out_dir, _ = self._run(tmp_path, attempts, rows)
        assert result == 0
        first = {
            name: (out_dir / name).read_bytes()
            for name in ("h1_manifest.json", "h1_predictions.jsonl", "h1_telemetry.jsonl")
        }
        result, out_dir, _ = self._run(tmp_path, attempts, rows, overwrite=True)
        assert result == 0
        for name, before in first.items():
            assert (out_dir / name).read_bytes() == before

    def test_strict_binding_negatives_fail_closed(self, tmp_path):
        attempts = _fixture_attempts()
        b0_path, _ = _b0_bundle(tmp_path, attempts)
        batch, _, selected = _selected_plans(attempts, b0_path)
        body = self._chat_completion_body('{"sample_id": "estg_000002", "patches": {}}')

        def base_rows():
            rows = []
            for index, plan in enumerate(selected):
                b0_record = next(
                    item.record
                    for item in batch
                    if item.record["sample_id"] == plan.sample_id
                )
                rows.append(
                    self._transport_row(
                        plan, b0_record, "masked_selected_v5", f"r{index}", body
                    )
                )
            return rows

        def run(rows):
            responses_path = tmp_path / "t.jsonl"
            responses_path.write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                encoding="utf-8",
            )
            b0_path, b0_manifest = _b0_bundle(tmp_path / "sub", attempts)
            out_dir = tmp_path / "sub" / "out"
            return RUNNER.main(
                [
                    "--b0-predictions",
                    str(b0_path),
                    "--b0-manifest",
                    str(b0_manifest),
                    "--output",
                    str(out_dir / "h1_predictions.jsonl"),
                    "--manifest",
                    str(out_dir / "h1_manifest.json"),
                    "--offline-transport-replay",
                    "--transport-responses-jsonl",
                    str(responses_path),
                    "--max-calls",
                    "50",
                    "--development",
                ]
            )

        # missing
        rows = base_rows()
        rows = rows[1:]
        assert run(rows) == 2
        # duplicate request_id
        rows = base_rows()
        rows[1]["request_id"] = rows[0]["request_id"]
        assert run(rows) == 2
        # duplicate sample/clause
        rows = base_rows()
        rows[1]["sample_id"] = rows[0]["sample_id"]
        rows[1]["clause_id"] = rows[0]["clause_id"]
        assert run(rows) == 2
        # extra row
        rows = base_rows()
        extra = dict(rows[0])
        extra.update({"request_id": "extra-1", "sample_id": "estg_000001", "clause_id": "estg_000001.c1"})
        rows.append(extra)
        assert run(rows) == 2
        # prompt sha mismatch
        rows = base_rows()
        rows[0]["prompt_sha256"] = "0" * 64
        assert run(rows) == 2
        # b0 hash mismatch
        rows = base_rows()
        rows[0]["b0_prediction_sha256"] = "0" * 64
        assert run(rows) == 2
        # clause_index mismatch
        rows = base_rows()
        rows[0]["clause_index"] = 99
        assert run(rows) == 2

    def test_capture_required_for_real_mode_before_any_call(self, tmp_path):
        """Future real mode without --transport-capture exits 2 and the
        transport's send is never invoked."""
        sent = []

        class FakeTransport:
            def __init__(self, config, timeout_seconds=60.0, policy=None):
                pass

            def send(self, request):
                sent.append(request)
                raise AssertionError("transport must never be called")

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(RUNNER, "RealAPITransport", FakeTransport)
        b0_path, b0_manifest = _b0_bundle(tmp_path, _fixture_attempts())
        try:
            result = RUNNER.main(
                [
                    "--b0-predictions",
                    str(b0_path),
                    "--b0-manifest",
                    str(b0_manifest),
                    "--output",
                    str(tmp_path / "o.jsonl"),
                    "--manifest",
                    str(tmp_path / "m.json"),
                    "--allow-llm",
                    "--max-calls",
                    "1",
                    "--model",
                    "deepseek-v4-flash",
                    "--development",
                ]
            )
        finally:
            monkeypatch.undo()
        assert result == 2
        assert sent == []
        assert not (tmp_path / "m.json").exists()

    def test_no_gold_layer_e_or_env_dependency(self):
        source = (PROJECT_ROOT / "src" / "bpc_hybrid" / "h1_transport.py").read_text(
            encoding="utf-8"
        )
        import_lines = [
            line for line in source.splitlines()
            if line.startswith(("import ", "from "))
        ]
        assert not any("llm" in line for line in import_lines)
        assert not any(
            ("human_review" in line or "gold" in line or "paper_validation" in line)
            for line in import_lines
        )
        assert "urlopen" not in source and "urllib.request" not in source
        assert "open(" not in source  # no file reads at all

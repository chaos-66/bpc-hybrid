"""S2.8D-R3: fail-closed unique exact-text span coordinate canonicalization.

Unit tests for ``bpc_hybrid.h1_span_canonicalizer`` plus runner-integration
tests proving the canonicalizer sits on the shared path used by offline
replay and offline transport replay, and that the existing canonical
validator + atomic merge still gate everything afterwards.

All fixtures use invented ASCII/Unicode text; no real source text, Gold,
Layer E, ``.env``, or network/API access is involved.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

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

from bpc_hybrid.h1_span_canonicalizer import (  # noqa: E402
    CODE_AMBIGUOUS_MATCH,
    CODE_CONTRACT_VIOLATION,
    CODE_ZERO_MATCH,
    STATUS_FAILED,
    STATUS_REANCHORED,
    STATUS_UNCHANGED,
    canonicalize_patch_coordinates,
)

SOURCE_TEXT = "Alpha beta gamma delta epsilon zeta, if eta theta iota kappa."
CLAUSE_SPAN = {"start": 0, "end": len(SOURCE_TEXT), "text": SOURCE_TEXT}


def _span(text: str, start: int, end: int, **extra) -> dict:
    span = {"text": text, "start": start, "end": end}
    span.update(extra)
    return span


def _envelope(patches: dict) -> dict:
    return {
        "sample_id": "syn_000001",
        "clause_id": "syn_000001.c1",
        "repair_fields": ["modality", "actors", "actions", "actor_action_map"],
        "patches": patches,
        "reason": "synthetic fixture",
    }


def _strip_offsets(value):
    """Recursively delete ``start``/``end`` from span-like dicts so that the
    "only start/end may change" invariant can be asserted semantically."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key in ("start", "end") and "text" in value:
                continue
            out[key] = _strip_offsets(item)
        return out
    if isinstance(value, list):
        return [_strip_offsets(item) for item in value]
    return value


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class TestUnitCanonicalizer:
    def test_already_valid_unchanged(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 0, 10)]},
            "actors": [_span("epsilon zeta", 23, 35)],
            "actions": [],
            "actor_action_map": [],
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_UNCHANGED
        assert audit["already_valid_count"] == 2
        assert audit["reanchored_count"] == 0
        assert audit["corrections"] == []
        assert audit["original_patch_sha256"] == audit["canonicalized_patch_sha256"]
        assert out is env  # untouched object

    def test_unique_exact_match_reanchors_only_start_end(self):
        text = "epsilon zeta"
        start = SOURCE_TEXT.index(text)
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 0, 10)]},
            "actors": [_span(text, start + 2, start + len(text) + 1)],
            "actions": [],
            "actor_action_map": [],
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_REANCHORED
        assert audit["reanchored_count"] == 1
        assert audit["already_valid_count"] == 1
        correction = audit["corrections"][0]
        assert correction["field_path"] == "actors[0]"
        assert correction["proposed_start"] == start + 2
        assert correction["corrected_start"] == start
        assert correction["corrected_end"] == start + len(text)
        assert correction["exact_occurrence_count"] == 1
        assert out["patches"]["actors"][0]["start"] == start
        assert out["patches"]["actors"][0]["end"] == start + len(text)
        assert out["patches"]["actors"][0]["text"] == text
        assert _json(_strip_offsets(env)) == _json(_strip_offsets(out))

    def test_zero_match_fails_whole_patch(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("never appears", 0, 10)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_ZERO_MATCH]
        assert audit["zero_match_count"] == 1
        assert audit["corrections"] == []
        assert out is env
        assert audit["canonicalized_patch_sha256"] is None

    def test_ambiguous_match_fails_whole_patch(self):
        # "Alpha" appears twice in this source.
        source = "Alpha beta Alpha gamma"
        clause_span = {"start": 0, "end": len(source), "text": source}
        text = "Alpha"
        patch = {
            "modality": {"label": "obligation", "evidence": [_span(text, 0, 10)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, source, clause_span)
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_AMBIGUOUS_MATCH]
        assert audit["ambiguous_match_count"] == 1
        assert out is env

    def test_empty_text_contract_violation(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("", 0, 0)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(
            _envelope(patch), SOURCE_TEXT, CLAUSE_SPAN
        )
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_CONTRACT_VIOLATION]
        assert audit["contract_violation_count"] == 1

    def test_non_integer_offset_contract_violation(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha", "0", 10)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(
            _envelope(patch), SOURCE_TEXT, CLAUSE_SPAN
        )
        assert audit["reason_codes"] == [CODE_CONTRACT_VIOLATION]
        assert audit["status"] == STATUS_FAILED

    def test_bool_offset_contract_violation(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha", True, 10)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(
            _envelope(patch), SOURCE_TEXT, CLAUSE_SPAN
        )
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_CONTRACT_VIOLATION]

    def test_start_gt_end_contract_violation(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha", 10, 3)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(
            _envelope(patch), SOURCE_TEXT, CLAUSE_SPAN
        )
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_CONTRACT_VIOLATION]

    def test_nonzero_clause_start_uses_global_coordinates(self):
        full = "PRE. " + SOURCE_TEXT
        clause_start = len("PRE. ")
        clause_span = {"start": clause_start, "end": len(full), "text": full[clause_start:]}
        text = "epsilon zeta"
        global_start = full.index(text)
        patch = {
            "modality": {"label": "obligation", "evidence": [_span(text, 0, 3)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), full, clause_span)
        assert audit["status"] == STATUS_REANCHORED
        correction = audit["corrections"][0]
        assert correction["corrected_start"] == global_start
        assert correction["corrected_end"] == global_start + len(text)
        assert correction["clause_start"] == clause_start
        assert out["patches"]["modality"]["evidence"][0]["start"] == global_start
        assert out["patches"]["modality"]["evidence"][0]["end"] == global_start + len(text)

    def test_unique_inside_clause_wins_over_outside_matches(self):
        # "gamma" occurs once inside the window and once outside it.
        full = "gamma gamma delta"
        clause_span = {"start": 6, "end": len(full), "text": full[6:]}
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("gamma", 0, 3)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), full, clause_span)
        assert audit["status"] == STATUS_REANCHORED
        correction = audit["corrections"][0]
        assert correction["corrected_start"] == 6
        assert correction["corrected_end"] == 11

    def test_only_outside_match_is_zero_match(self):
        full = "gamma gamma delta"
        # Window [6, 11] covers only the second "gamma"; "delta" is outside.
        clause_span = {"start": 6, "end": 11, "text": full[6:11]}
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("delta", 0, 3)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), full, clause_span)
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_ZERO_MATCH]

    def test_unicode_code_point_coordinates(self):
        full = "x caf\u00e9 y latte"
        clause_span = {"start": 0, "end": len(full), "text": full}
        text = "caf\u00e9"
        global_start = full.index(text)
        patch = {
            "modality": {"label": "obligation", "evidence": [_span(text, 0, 3)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), full, clause_span)
        assert audit["status"] == STATUS_REANCHORED
        correction = audit["corrections"][0]
        # code-point indexing: é is one code point
        assert correction["corrected_start"] == global_start
        assert correction["corrected_end"] == global_start + len(text)
        assert correction["text_char_length"] == 4
        assert correction["text_utf8_length"] == 5  # é is 2 UTF-8 bytes
        assert out["patches"]["modality"]["evidence"][0]["end"] == global_start + 4

    def test_overlapping_occurrences_are_ambiguous(self):
        full = "aaaa"
        clause_span = {"start": 0, "end": len(full), "text": full}
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("aaa", 0, 2)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), full, clause_span)
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_AMBIGUOUS_MATCH]
        assert audit["ambiguous_match_count"] == 1

    def test_all_unique_spans_corrected(self):
        a_text = "Alpha beta"
        b_text = "epsilon zeta"
        c_text = "if eta theta iota"
        patch = {
            "modality": {
                "label": "obligation",
                "evidence": [_span(a_text, 0, 3), _span(b_text, 0, 3)],
            },
            "actors": [_span(c_text, 0, 3)],
            "conditions": [_span("gamma delta", 0, 3)],
            "actions": [],
            "constraints": [],
            "exceptions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_REANCHORED
        assert audit["reanchored_count"] == 4
        assert [c["field_path"] for c in audit["corrections"]] == [
            "modality.evidence[0]",
            "modality.evidence[1]",
            "actors[0]",
            "conditions[0]",
        ]
        assert out["patches"]["modality"]["evidence"][0]["start"] == SOURCE_TEXT.index(a_text)
        assert out["patches"]["modality"]["evidence"][1]["start"] == SOURCE_TEXT.index(b_text)
        assert out["patches"]["actors"][0]["start"] == SOURCE_TEXT.index(c_text)
        assert out["patches"]["conditions"][0]["start"] == SOURCE_TEXT.index("gamma delta")

    def test_one_ambiguous_blocks_all_corrections(self):
        source = "Alpha beta gamma Alpha, epsilon zeta."
        clause_span = {"start": 0, "end": len(source), "text": source}
        env = _envelope(
            {
                "modality": {
                    "label": "obligation",
                    "evidence": [_span("epsilon zeta", 0, 3)],
                },
                "actors": [_span("Alpha", 0, 3)],
                "actions": [],
                "actor_action_map": [],
            }
        )
        out, audit = canonicalize_patch_coordinates(env, source, clause_span)
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_AMBIGUOUS_MATCH]
        assert audit["corrections"] == []
        assert audit["reanchored_count"] == 0
        assert out is env  # original envelope returned untouched, no partial fix
        assert out["patches"]["modality"]["evidence"][0]["start"] == 0

    def test_relation_fields_never_touched(self):
        relations = {
            "actor_action_map": [{"actor_id": "a.1", "action_id": "ac.1"}],
            "order_relations": [
                {
                    "before_action_id": "ac.1",
                    "after_action_id": "ac.2",
                    "evidence": [_span("epsilon zeta", 23, 35)],
                }
            ],
        }
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 0, 3)]},
            "actors": [],
            "actions": [],
            **relations,
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_REANCHORED
        assert out["patches"]["actor_action_map"] == relations["actor_action_map"]
        assert out["patches"]["order_relations"] == relations["order_relations"]

    def test_only_start_end_change_semantically(self):
        patch = {
            "modality": {
                "label": "obligation",
                "route": "marker_obligation",
                "diagnostic": {"marker_surface": "shall"},
                "evidence": [_span("Alpha beta", 1, 9)],
            },
            "actors": [
                _span("epsilon zeta", 24, 36, id="syn.actor.1", normalized="epsilon zeta")
            ],
            "actions": [],
            "actor_action_map": [{"actor_id": "syn.actor.1", "action_id": "syn.action.1"}],
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_REANCHORED
        assert _json(_strip_offsets(env)) == _json(_strip_offsets(out))
        # key order preserved for the envelope keys
        assert list(out.keys()) == list(env.keys())

    def test_deterministic_rerun(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 1, 9)]},
            "actors": [_span("epsilon zeta", 24, 36)],
            "actions": [],
            "actor_action_map": [],
        }
        env = _envelope(patch)
        out1, audit1 = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        out2, audit2 = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert _json(audit1) == _json(audit2)
        assert _json(out1) == _json(out2)

    def test_absent_markers_and_empty_lists_are_skipped(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 0, 10)]},
            "actors": {"absent": True},
            "actions": [],
            "conditions": [],
            "constraints": {"absent": True},
            "exceptions": [],
            "actor_action_map": [],
        }
        env = _envelope(patch)
        out, audit = canonicalize_patch_coordinates(env, SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_UNCHANGED
        assert audit["span_count"] == 1
        assert out is env

    def test_illegal_span_container_contract_violation(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 0, 10)]},
            "actors": {"text": "not a list", "start": 0, "end": 3},
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(_envelope(patch), SOURCE_TEXT, CLAUSE_SPAN)
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_CONTRACT_VIOLATION]

    def test_illegal_clause_span_contract_violation(self):
        patch = {
            "modality": {"label": "obligation", "evidence": [_span("Alpha beta", 0, 10)]},
            "actors": [],
            "actions": [],
            "actor_action_map": [],
        }
        out, audit = canonicalize_patch_coordinates(
            _envelope(patch), SOURCE_TEXT, {"start": "0", "end": 100}
        )
        assert audit["status"] == STATUS_FAILED
        assert audit["reason_codes"] == [CODE_CONTRACT_VIOLATION]


# ---------------------------------------------------------------------------
# Runner integration: shared canonicalizer path + existing gates still apply
# ---------------------------------------------------------------------------

FIXTURE_SOURCE = "The controller shall notify the authority within 72 hours."
SHALL_START = FIXTURE_SOURCE.index("shall")
SHALL_END = SHALL_START + len("shall")
ACTION_TEXT = "notify the authority"
ACTION_START = FIXTURE_SOURCE.index(ACTION_TEXT)
ACTION_END = ACTION_START + len(ACTION_TEXT)


def _clause() -> dict:
    return {
        "clause_id": "syn_000002.c1",
        "clause_span": {"text": FIXTURE_SOURCE, "start": 0, "end": len(FIXTURE_SOURCE)},
        "modality": {
            "label": "obligation",
            "evidence": [{"text": "shall", "start": SHALL_START, "end": SHALL_END}],
            "route": "marker_obligation",
            "diagnostic": {
                "clause_classifier_label": "definition",
                "marker_label": "permission",
                "marker_surface": "shall",
                "record_classifier_label": "obligation",
            },
        },
        "actors": [],
        "actions": [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
        "alignment": {"confidence": 0.9, "status": "validated_split", "supported": True},
        "scope_stats": {"scope_accepted": 1, "scope_rejected": 0},
    }


def _b0_attempt() -> dict:
    return {
        "request_status": "ok",
        "sample_id": "syn_000002",
        "record": {
            "schema_version": "1.0.0",
            "sample_id": "syn_000002",
            "source_id": "SYNTHETIC",
            "source_text": FIXTURE_SOURCE,
            "clauses": [_clause()],
            "method": {"name": "sun_rule_only", "schema_source": "stage2_prediction.schema.json@1.0.0"},
            "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        },
    }


def _b0_bundle(tmp_path: Path) -> tuple[Path, Path]:
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


def _prompt_sha() -> str:
    from bpc_hybrid.prompt_loader import load_prompt

    return load_prompt("rule_first_llm_fallback_masked_prompt").sha256


def _plan(tmp_path: Path) -> tuple[Path, Path, object]:
    b0_path, b0_manifest = _b0_bundle(tmp_path)
    batch = RUNNER.load_b0_predictions(b0_path)
    plans = RUNNER.build_repair_plans(batch)
    selected = RUNNER.allocate_repair_calls(plans, 1)
    assert len(selected) == 1
    return b0_path, b0_manifest, selected[0]


def _wrong_offset_patch() -> dict:
    return {
        "sample_id": "syn_000002",
        "clause_id": "syn_000002.c1",
        "repair_fields": ["modality", "actors", "actions", "actor_action_map"],
        "patches": {
            "modality": {
                "label": "prohibition",
                "evidence": [_span("shall", SHALL_START - 1, SHALL_END + 2)],
            },
            "actors": [
                _span(
                    "The controller", 1, 13,
                    id="syn_000002.c1.actor.1", normalized="controller",
                )
            ],
            "actions": [
                _span(
                    ACTION_TEXT, ACTION_START - 2, ACTION_END + 1,
                    id="syn_000002.c1.action.1", normalized="notify authority",
                )
            ],
            "actor_action_map": [
                {
                    "actor_id": "syn_000002.c1.actor.1",
                    "action_id": "syn_000002.c1.action.1",
                }
            ],
        },
        "reason": "synthetic wrong-offset patch",
    }


def _response_row(plan, b0_record, request_id: str, content: dict) -> dict:
    return {
        "request_id": request_id,
        "sample_id": plan.sample_id,
        "clause_id": plan.clause_id,
        "clause_index": plan.clause_index,
        "prompt_sha256": _prompt_sha(),
        "prompt_variant": "masked_selected_v5",
        "b0_prediction_sha256": RUNNER._prediction_hash(b0_record),
        "response_content": json.dumps(content),
    }


def _transport_row(plan, b0_record, request_id: str, content: dict) -> dict:
    body = {
        "id": "syn-chatcmpl-1",
        "object": "chat.completion",
        "model": "deepseek-v4-pro",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(content)},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }
    return {
        "request_id": request_id,
        "sample_id": plan.sample_id,
        "clause_id": plan.clause_id,
        "clause_index": plan.clause_index,
        "prompt_sha256": _prompt_sha(),
        "prompt_variant": "masked_selected_v5",
        "b0_prediction_sha256": RUNNER._prediction_hash(b0_record),
        "response_body": json.dumps(body),
        "content_type": "application/json",
        "http_status": 200,
    }


def _run_replay(tmp_path: Path, args_extra: list[str], responses_path: Path) -> dict:
    b0_path, b0_manifest = _b0_bundle(tmp_path)
    out_dir = tmp_path / "out"
    if "--offline-replay" in args_extra:
        responses_args = ["--responses-jsonl", str(responses_path)]
    else:
        responses_args = ["--transport-responses-jsonl", str(responses_path)]
    result = RUNNER.main(
        [
            "--b0-predictions", str(b0_path),
            "--b0-manifest", str(b0_manifest),
            "--output", str(out_dir / "h1_predictions.jsonl"),
            "--telemetry", str(out_dir / "h1_telemetry.jsonl"),
            "--manifest", str(out_dir / "h1_manifest.json"),
            *args_extra,
            *responses_args,
            "--prompt-variant", "masked_selected_v5",
            "--max-calls", "1",
            "--development",
        ]
    )
    assert result == 0
    return json.loads((out_dir / "h1_manifest.json").read_text(encoding="utf-8"))


def _write_rows(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


class TestRunnerIntegration:
    def test_offline_replay_reanchors_and_merges(self, tmp_path):
        b0_path, b0_manifest = _b0_bundle(tmp_path)
        batch = RUNNER.load_b0_predictions(b0_path)
        plans = RUNNER.build_repair_plans(batch)
        plan = RUNNER.allocate_repair_calls(plans, 1)[0]
        b0_record = batch[0].record
        rows_path = _write_rows(
            tmp_path / "responses.jsonl",
            [_response_row(plan, b0_record, "r1", _wrong_offset_patch())],
        )
        manifest = _run_replay(
            tmp_path, ["--offline-replay"], rows_path
        )
        canon = manifest["coordinate_canonicalization"]
        assert canon["attempted_patch_count"] == 1
        assert canon["reanchored_patch_count"] == 1
        assert canon["reanchored_span_count"] == 3
        assert canon["zero_match_count"] == 0
        assert canon["ambiguous_match_count"] == 0
        assert canon["contract_violation_count"] == 0
        assert manifest["patch_accepted_count"] == 1
        assert manifest["prediction_changed_sample_count"] == 1
        assert manifest["h1_non_identity_gate"] is True
        # corrections recorded with offsets only
        event = next(
            e for e in manifest["patch_events"] if e.get("selected_for_call")
        )
        audit = event["coordinate_canonicalization"]
        assert audit["status"] == "reanchored"
        assert {c["field_path"] for c in audit["corrections"]} == {
            "modality.evidence[0]", "actors[0]", "actions[0]",
        }
        for c in audit["corrections"]:
            assert set(c) == {
                "field_path", "proposed_start", "proposed_end",
                "corrected_start", "corrected_end", "text_char_length",
                "text_utf8_length", "text_sha256", "clause_start",
                "clause_end", "exact_occurrence_count",
            }

    def test_offline_transport_replay_uses_same_canonicalizer(self, tmp_path):
        b0_path, b0_manifest = _b0_bundle(tmp_path)
        batch = RUNNER.load_b0_predictions(b0_path)
        plans = RUNNER.build_repair_plans(batch)
        plan = RUNNER.allocate_repair_calls(plans, 1)[0]
        b0_record = batch[0].record
        rows_path = _write_rows(
            tmp_path / "transport.jsonl",
            [_transport_row(plan, b0_record, "t1", _wrong_offset_patch())],
        )
        manifest = _run_replay(
            tmp_path, ["--offline-transport-replay"], rows_path
        )
        canon = manifest["coordinate_canonicalization"]
        assert canon["reanchored_patch_count"] == 1
        assert canon["reanchored_span_count"] == 3
        assert manifest["transport"]["extraction_status_counts"] == {
            "ok_message_content": 1
        }
        assert manifest["patch_accepted_count"] == 1
        assert manifest["h1_non_identity_gate"] is True

    def test_reanchored_but_relation_id_error_still_rejected(self, tmp_path):
        patch = _wrong_offset_patch()
        patch["patches"]["actor_action_map"] = [
            {"actor_id": "syn_000002.c1.actor.1", "action_id": "missing.action.1"}
        ]
        b0_path, b0_manifest = _b0_bundle(tmp_path)
        batch = RUNNER.load_b0_predictions(b0_path)
        plans = RUNNER.build_repair_plans(batch)
        plan = RUNNER.allocate_repair_calls(plans, 1)[0]
        rows_path = _write_rows(
            tmp_path / "responses.jsonl",
            [_response_row(plan, batch[0].record, "r1", patch)],
        )
        manifest = _run_replay(tmp_path, ["--offline-replay"], rows_path)
        canon = manifest["coordinate_canonicalization"]
        assert canon["reanchored_patch_count"] == 1  # canonicalization itself succeeded
        assert manifest["patch_accepted_count"] == 0
        assert "canonical_invalid" in manifest["effective_patch"]["rejection_reason_counts"]
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False

    def test_unauthorized_field_still_rejected_by_merge(self, tmp_path):
        patch = _wrong_offset_patch()
        patch["patches"]["conditions"] = []  # not in repair_fields
        b0_path, b0_manifest = _b0_bundle(tmp_path)
        batch = RUNNER.load_b0_predictions(b0_path)
        plans = RUNNER.build_repair_plans(batch)
        plan = RUNNER.allocate_repair_calls(plans, 1)[0]
        rows_path = _write_rows(
            tmp_path / "responses.jsonl",
            [_response_row(plan, batch[0].record, "r1", patch)],
        )
        manifest = _run_replay(tmp_path, ["--offline-replay"], rows_path)
        canon = manifest["coordinate_canonicalization"]
        assert canon["reanchored_patch_count"] == 1
        assert manifest["patch_accepted_count"] == 0
        assert "unauthorized_fields" in manifest["effective_patch"]["rejection_reason_counts"]
        assert manifest["prediction_changed_sample_count"] == 0
        assert manifest["h1_non_identity_gate"] is False

    def test_correct_offsets_recorded_unchanged(self, tmp_path):
        patch = _wrong_offset_patch()
        # Fix the offsets to be exactly correct: unchanged path, no merge change.
        patch["patches"]["modality"]["evidence"][0] = {
            "text": "shall", "start": SHALL_START, "end": SHALL_END,
        }
        patch["patches"]["actors"][0]["start"] = 0
        patch["patches"]["actors"][0]["end"] = len("The controller")
        patch["patches"]["actions"][0]["start"] = ACTION_START
        patch["patches"]["actions"][0]["end"] = ACTION_END
        b0_path, b0_manifest = _b0_bundle(tmp_path)
        batch = RUNNER.load_b0_predictions(b0_path)
        plans = RUNNER.build_repair_plans(batch)
        plan = RUNNER.allocate_repair_calls(plans, 1)[0]
        rows_path = _write_rows(
            tmp_path / "responses.jsonl",
            [_response_row(plan, batch[0].record, "r1", patch)],
        )
        manifest = _run_replay(tmp_path, ["--offline-replay"], rows_path)
        canon = manifest["coordinate_canonicalization"]
        assert canon["unchanged_patch_count"] == 1
        assert canon["reanchored_patch_count"] == 0
        # Semantic change still comes from the modality label flip.
        assert manifest["patch_accepted_count"] == 1
        event = next(
            e for e in manifest["patch_events"] if e.get("selected_for_call")
        )
        audit = event["coordinate_canonicalization"]
        assert audit["status"] == "unchanged"
        assert audit["original_patch_sha256"] == audit["canonicalized_patch_sha256"]

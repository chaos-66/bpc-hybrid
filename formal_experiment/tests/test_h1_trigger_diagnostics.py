"""Offline regression tests for the Gold-blind H1 diagnostics generator.

Covers the S2.8A acceptance surface:

* normal synthetic B0 -> sorted, feature-complete rows;
* manifest / hash mismatch -> fail closed;
* duplicate sample / clause / span IDs, cross-field ID collisions, span
  out-of-bounds, and span-text mismatches -> fail closed;
* missing telemetry -> rows generated with per-feature missing indicators
  (values are never auto-filled or coerced to 0);
* repeated runs are byte-identical;
* the generator has no Gold / Layer E / evaluator / API dependency.

The tests intentionally do NOT read or print ``.env``, call any LLM/API,
touch Layer E or Gold, or modify any real artifact.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from bpc_hybrid.stage2_canonical import SCHEMA_SOURCE, SCHEMA_VERSION


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "h1_diagnostics_test_module",
    PROJECT_ROOT / "scripts" / "build_h1_trigger_diagnostics.py",
)
DIAG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DIAG
SPEC.loader.exec_module(DIAG)

SOURCE_TEXT = "The controller shall notify the authority within 72 hours."
ACTOR_TEXT = "The controller"
SHALL_START = SOURCE_TEXT.index("shall")


def _span(id_: str, text: str, start: int, end: int) -> dict:
    return {
        "id": id_,
        "text": text,
        "start": start,
        "end": end,
        "normalized": text.lower(),
    }


def _clause(
    clause_id: str,
    *,
    modality_label: str = "obligation",
    telemetry: bool = True,
    extra_telemetry: dict | None = None,
) -> dict:
    action_text = "notify the authority"
    action_start = SOURCE_TEXT.index(action_text)
    constraint_text = "within 72 hours."
    clause = {
        "clause_id": clause_id,
        "clause_span": {
            "text": SOURCE_TEXT,
            "start": 0,
            "end": len(SOURCE_TEXT),
        },
        "modality": {
            "label": modality_label,
            "evidence": [
                {
                    "text": "shall",
                    "start": SHALL_START,
                    "end": SHALL_START + len("shall"),
                }
            ],
        },
        "actors": [_span(f"{clause_id}.a1", ACTOR_TEXT, 0, len(ACTOR_TEXT))],
        "actions": [_span(f"{clause_id}.x1", action_text, action_start, action_start + len(action_text))],
        "conditions": [],
        "constraints": [
            _span(
                f"{clause_id}.c1",
                constraint_text,
                SOURCE_TEXT.index("within"),
                len(SOURCE_TEXT),
            )
        ],
        "exceptions": [],
        "actor_action_map": [
            {"actor_id": f"{clause_id}.a1", "action_id": f"{clause_id}.x1"}
        ],
        "order_relations": [],
    }
    if telemetry:
        clause["alignment"] = {
            "confidence": 0.9,
            "status": "validated_split",
            "supported": True,
        }
        clause["scope_stats"] = {"scope_accepted": 1, "scope_rejected": 0}
        clause["modality"]["route"] = "marker_obligation"
        clause["modality"]["diagnostic"] = {
            "clause_classifier_label": "obligation",
            "marker_label": "obligation",
            "marker_surface": "shall",
            "alignment_status": "validated_split",
            "validated_alignment": True,
            "record_classifier_label": "obligation",
            "placeholder_classifier_input": False,
        }
        if extra_telemetry:
            modality_overrides = extra_telemetry.get("modality")
            if isinstance(modality_overrides, dict):
                clause["modality"].update(modality_overrides)
            clause.update(
                {key: value for key, value in extra_telemetry.items() if key != "modality"}
            )
    return clause


def _attempt(sample_id: str, clauses: list[dict]) -> dict:
    return {
        "request_status": "ok",
        "sample_id": sample_id,
        "runtime": {"latency_ms": 10, "llm_call_performed": False},
        "record": {
            "schema_version": SCHEMA_VERSION,
            "sample_id": sample_id,
            "source_id": "EStG synthetic",
            "source_text": SOURCE_TEXT,
            "clauses": clauses,
            "method": {"name": "sun_rule_only", "schema_source": SCHEMA_SOURCE},
            "validation": {
                "schema_valid": True,
                "cross_field_valid": True,
                "errors": [],
            },
        },
    }


def _write_bundle(tmp_path: Path, attempts: list[dict]) -> tuple[Path, Path]:
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


def _normal_batch() -> list[dict]:
    return [
        _attempt("estg_a", [_clause("estg_a.c1"), _clause("estg_a.c2", telemetry=False)]),
        _attempt(
            "estg_b",
            [
                _clause(
                    "estg_b.c1",
                    modality_label="definition",
                    extra_telemetry={
                        "alignment": {"confidence": 0.55, "status": "unsupported"},
                        "modality": {
                            "route": "marker_permission",
                            "diagnostic": {
                                "clause_classifier_label": "definition",
                                "marker_label": "permission",
                                "record_classifier_label": "definition",
                            },
                        },
                    },
                )
            ],
        ),
    ]


def _run(
    tmp_path: Path,
    attempts: list[dict] | None = None,
    *,
    overwrite: bool = False,
    development: bool = True,
) -> tuple[int, Path, Path]:
    b0_path, manifest_path = _write_bundle(
        tmp_path, attempts if attempts is not None else _normal_batch()
    )
    output = tmp_path / "out" / "diagnostics.jsonl"
    out_manifest = tmp_path / "out" / "manifest.json"
    args = [
        "--b0-predictions",
        str(b0_path),
        "--b0-manifest",
        str(manifest_path),
        "--output",
        str(output),
        "--manifest",
        str(out_manifest),
    ]
    if overwrite:
        args.append("--overwrite")
    if development:
        args.append("--development")
    return DIAG.main(args), output, out_manifest


def _read_rows(output: Path) -> list[dict]:
    return [
        json.loads(line) for line in output.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


class TestNormalGeneration:
    def test_synthetic_b0_produces_sorted_feature_rows(self, tmp_path):
        result, output, out_manifest = _run(tmp_path)
        assert result == 0
        rows = _read_rows(output)
        assert [row["sample_id"] for row in rows] == ["estg_a", "estg_a", "estg_b"]
        assert [row["clause_index"] for row in rows] == [0, 1, 0]
        assert [row["clause_id"] for row in rows] == [
            "estg_a.c1",
            "estg_a.c2",
            "estg_b.c1",
        ]

        first = rows[0]
        assert first["source_id"] == "EStG synthetic"
        assert first["clause_span_length"] == len(SOURCE_TEXT)
        assert 0.0 < first["clause_span_ratio"] <= 1.0
        assert first["b0_prediction_sha256"]
        assert first["b0_attempts_sha256"] == hashlib.sha256(
            (tmp_path / "b0_attempts.json").read_bytes()
        ).hexdigest()
        assert first["modality_label"] == "obligation"
        assert first["modality_route"] == "marker_obligation"
        assert first["classifier_label"] == "obligation"
        assert first["marker_label"] == "obligation"
        assert first["classifier_marker_disagreement"] is False
        assert first["alignment_confidence"] == 0.9
        assert first["n_actors"] == 1
        assert first["n_actions"] == 1
        assert first["n_conditions"] == 0
        assert first["n_constraints"] == 1
        assert first["n_exceptions"] == 0
        assert first["actor_action_map_count"] == 1
        assert first["order_relations_count"] == 0
        assert first["relation_invalid_reference_count"] == 0
        assert first["span_text_mismatch_count"] == 0
        assert first["span_outside_clause_count"] == 0
        assert first["span_id_duplicate_count"] == 0
        assert first["span_id_cross_field_collision_count"] == 0
        assert first["non_definition_missing_actor"] is False
        assert first["non_definition_missing_action"] is False
        assert first["scope_accepted"] == 1
        assert first["scope_rejected"] == 0
        assert first["schema_valid"] is True
        assert first["cross_field_valid"] is True
        assert first["stage3_adapter_status"] in ("ok", "not_available")
        assert set(first["missing"]) == set(first) - {"missing", "missing_features"}
        if first["stage3_adapter_status"] == "ok":
            assert first["missing_features"] == []

        # No full source text and no span text in the table.
        for row in rows:
            assert "source_text" not in row
            assert "text" not in row

    def test_definition_clause_with_disagreement_row(self, tmp_path):
        result, output, _ = _run(tmp_path)
        assert result == 0
        row = [r for r in _read_rows(output) if r["sample_id"] == "estg_b"][0]
        assert row["modality_label"] == "definition"
        assert row["classifier_label"] == "definition"
        assert row["marker_label"] == "permission"
        assert row["classifier_marker_disagreement"] is True
        assert row["alignment_confidence"] == 0.55
        assert row["non_definition_missing_actor"] is False
        assert row["non_definition_missing_action"] is False

    def test_manifest_binds_inputs_and_outputs(self, tmp_path):
        result, output, out_manifest = _run(tmp_path)
        assert result == 0
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["schema_version"] == DIAG.MANIFEST_VERSION
        assert manifest["status"] == "development_not_formal"
        assert manifest["b0_binding"]["manifest"]["verified"] is True
        assert manifest["b0_binding"]["rerun_inside_diagnostics"] is False
        assert manifest["outputs"]["diagnostics"]["sha256"] == hashlib.sha256(
            output.read_bytes()
        ).hexdigest()
        assert manifest["outputs"]["diagnostics"]["row_count"] == 3
        assert manifest["coverage"]["expected_attempts"] == 2
        assert manifest["coverage"]["loaded_samples"] == 2
        assert manifest["coverage"]["clause_rows"] == 3
        assert manifest["coverage"]["excluded_rows"] == 0
        assert manifest["coverage"]["coverage_complete"] is True
        assert manifest["config"]["contains_full_source_or_span_text"] is False
        assert manifest["safety"] == {
            "gold_visible": False,
            "layer_e_accessed": False,
            "evaluator_accessed": False,
            "paper_validation_accessed": False,
            "llm_api_called": False,
            "b0_modified": False,
        }
        assert manifest["signal_candidate_counts"]["rows_with_any_signal_candidate"] >= 1


class TestFailClosedInputs:
    def test_manifest_hash_mismatch_fails_closed(self, tmp_path):
        b0_path, manifest_path = _write_bundle(tmp_path, _normal_batch())
        with b0_path.open("a", encoding="utf-8") as stream:
            stream.write(" ")
        output = tmp_path / "out" / "d.jsonl"
        result = DIAG.main(
            [
                "--b0-predictions",
                str(b0_path),
                "--b0-manifest",
                str(manifest_path),
                "--output",
                str(output),
                "--manifest",
                str(tmp_path / "out" / "m.json"),
                "--development",
            ]
        )
        assert result == 2
        assert not output.exists()

    def test_duplicate_sample_id_fails_closed(self, tmp_path):
        attempts = [_attempt("dup", [_clause("dup.c1")]), _attempt("dup", [_clause("dup.c2")])]
        result, output, _ = _run(tmp_path, attempts)
        assert result == 2
        assert not output.exists()

    def test_duplicate_clause_id_fails_closed(self, tmp_path):
        attempts = [_attempt("s", [_clause("s.c1"), _clause("s.c1")])]
        result, output, _ = _run(tmp_path, attempts)
        assert result == 2
        assert not output.exists()

    def test_span_out_of_bounds_fails_closed(self, tmp_path):
        clause = _clause("s.c1")
        clause["constraints"][0]["end"] = len(SOURCE_TEXT) + 5
        result, output, _ = _run(tmp_path, [_attempt("s", [clause])])
        assert result == 2
        assert not output.exists()

    def test_span_text_mismatch_fails_closed(self, tmp_path):
        clause = _clause("s.c1")
        clause["actors"][0]["text"] = "invented actor"
        result, output, _ = _run(tmp_path, [_attempt("s", [clause])])
        assert result == 2
        assert not output.exists()

    def test_duplicate_span_id_fails_closed(self, tmp_path):
        clause = _clause("s.c1")
        clause["constraints"][0]["id"] = "s.c1.a1"  # collides with the actor id
        result, output, _ = _run(tmp_path, [_attempt("s", [clause])])
        assert result == 2
        assert not output.exists()

    def test_invalid_relation_reference_fails_closed(self, tmp_path):
        clause = _clause("s.c1")
        clause["actor_action_map"][0]["action_id"] = "missing_action_id"
        result, output, _ = _run(tmp_path, [_attempt("s", [clause])])
        assert result == 2
        assert not output.exists()


class TestMissingTelemetry:
    def test_missing_telemetry_kept_with_missing_indicators(self, tmp_path):
        result, output, _ = _run(tmp_path)
        assert result == 0
        row = [r for r in _read_rows(output) if r["clause_id"] == "estg_a.c2"][0]
        assert row["modality_route"] is None
        assert row["classifier_label"] is None
        assert row["marker_label"] is None
        assert row["alignment_status"] is None
        assert row["alignment_confidence"] is None
        assert row["scope_accepted"] is None
        assert row["scope_rejected"] is None
        assert row["classifier_marker_disagreement"] is None
        assert row["missing"]["modality_route"] is True
        assert row["missing"]["classifier_label"] is True
        assert row["missing"]["marker_label"] is True
        assert row["missing"]["alignment_status"] is True
        assert row["missing"]["alignment_confidence"] is True
        assert row["missing"]["scope_accepted"] is True
        assert row["missing"]["scope_rejected"] is True
        assert row["missing"]["classifier_marker_disagreement"] is True
        # Structural features are never silently missing, and none is
        # auto-filled: counts stay real, missing stays False.
        assert row["missing"]["n_actors"] is False
        assert row["n_actors"] == 1
        assert row["span_text_mismatch_count"] == 0


class TestDeterminismAndGating:
    def test_repeated_run_is_byte_identical(self, tmp_path):
        result, output, out_manifest = _run(tmp_path)
        assert result == 0
        first_rows = output.read_bytes()
        first_manifest = out_manifest.read_bytes()
        result, output, out_manifest = _run(tmp_path, overwrite=True)
        assert result == 0
        assert output.read_bytes() == first_rows
        assert out_manifest.read_bytes() == first_manifest

    def test_overwrite_guard(self, tmp_path):
        result, output, _ = _run(tmp_path)
        assert result == 0
        result, output, _ = _run(tmp_path)
        assert result == 2

    def test_non_formal_write_requires_development_flag(self, tmp_path):
        result, output, _ = _run(tmp_path, development=False)
        assert result == 2
        assert not output.exists()

    def test_no_gold_layer_e_or_api_dependency(self, tmp_path):
        source = (PROJECT_ROOT / "scripts" / "build_h1_trigger_diagnostics.py").read_text(
            encoding="utf-8"
        )
        import_lines = [
            line for line in source.splitlines()
            if line.startswith(("import ", "from "))
        ]
        assert not any("llm" in line for line in import_lines)
        assert not any(("human_review" in line or "gold" in line) for line in import_lines)
        assert not any("paper_validation" in line for line in import_lines)
        data_files_before = {
            str(p.relative_to(PROJECT_ROOT))
            for p in (PROJECT_ROOT / "data").rglob("*")
            if p.is_file()
        }
        result, output, out_manifest = _run(tmp_path)
        assert result == 0
        data_files_after = {
            str(p.relative_to(PROJECT_ROOT))
            for p in (PROJECT_ROOT / "data").rglob("*")
            if p.is_file()
        }
        assert data_files_after == data_files_before
        manifest = json.loads(out_manifest.read_text(encoding="utf-8"))
        assert manifest["safety"]["llm_api_called"] is False
        assert manifest["safety"]["gold_visible"] is False
        assert manifest["safety"]["layer_e_accessed"] is False

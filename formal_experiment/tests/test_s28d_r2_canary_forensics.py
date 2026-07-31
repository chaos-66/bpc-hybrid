"""S2.8D-R2: offline span/offset forensics tooling tests.

Covers the pure diagnostic functions and the end-to-end main() flow of
``scripts/s28d_r2_canary_forensics.py`` with fully synthetic fixtures:

* slice check + occurrence analysis + conservative classification;
* fail-closed reanchoring (zero_match / ambiguous_match / empty text);
* corrections touch ONLY start/end;
* rejection-path parsing matches the canonical error format;
* transport-body reconstruction decodes to the same content;
* deterministic byte-identical diagnostics across output dirs;
* binding violations fail closed.

All fixtures use invented ASCII text; no source text, prompt text, Gold,
Layer E, ``.env``, or network access is involved.
"""

from __future__ import annotations

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
    "s28d_r2_canary_forensics_module",
    PROJECT_ROOT / "scripts" / "s28d_r2_canary_forensics.py",
)
FORENSICS = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FORENSICS
SPEC.loader.exec_module(FORENSICS)

from bpc_hybrid.b0_artifact import (  # noqa: E402
    load_b0_predictions,
    prediction_hash,
    sha256_file,
)
from bpc_hybrid.h1_transport import decode_chat_completion_envelope  # noqa: E402
from bpc_hybrid.prompt_loader import load_prompt  # noqa: E402

SOURCE_TEXT = (
    "Alpha beta gamma delta epsilon zeta, if eta theta iota kappa "
    "lambda mu nu xi omicron pi rho sigma tau upsilon phi."
)
CLAUSE_SPAN = {"start": 0, "end": len(SOURCE_TEXT), "text": SOURCE_TEXT}

MODALITY_TEXT = SOURCE_TEXT[0:23]  # "Alpha beta gamma delta eps" (unique)
ACTOR_TEXT = "epsilon zeta"  # unique
CONDITION_TEXT = "if eta theta iota kappa lambda mu nu xi"  # unique


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _clause() -> dict:
    action_text = "theta iota kappa"
    action_start = SOURCE_TEXT.index(action_text)
    return {
        "clause_id": "syn_000001.c1",
        "clause_span": dict(CLAUSE_SPAN),
        "modality": {
            "label": "prohibition",
            "evidence": [{"text": "eta", "start": SOURCE_TEXT.index("eta"),
                          "end": SOURCE_TEXT.index("eta") + 3}],
            "route": "prohibition_negation",
            "diagnostic": {
                "clause_classifier_label": "definition",
                "marker_label": "prohibition",
                "marker_surface": "if",
                "record_classifier_label": "definition",
            },
        },
        "actors": [],
        "actions": [
            {
                "id": "syn_000001.c1.action.1",
                "text": action_text,
                "start": action_start,
                "end": action_start + len(action_text),
                "normalized": "theta iota kappa",
            }
        ],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
        "actor_action_map": [],
        "order_relations": [],
        "alignment": {"confidence": 0.6, "status": "heuristic_pack", "supported": True},
        "scope_stats": {"scope_accepted": 0, "scope_rejected": 1},
    }


def _b0_attempt() -> dict:
    return {
        "request_status": "ok",
        "sample_id": "syn_000001",
        "record": {
            "schema_version": "1.0.0",
            "sample_id": "syn_000001",
            "source_id": "SYNTHETIC",
            "source_text": SOURCE_TEXT,
            "clauses": [_clause()],
            "method": {"name": "sun_rule_only", "schema_source": "stage2_prediction.schema.json@1.0.0"},
            "validation": {"schema_valid": True, "cross_field_valid": True, "errors": []},
        },
    }


def _write_b0_bundle(tmp_path: Path) -> tuple[Path, Path]:
    b0_path = tmp_path / "b0_attempts.json"
    b0_path.write_text(json.dumps([_b0_attempt()]), encoding="utf-8")
    manifest_path = tmp_path / "b0_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "run_id": "synthetic_b0",
                "method_variant": "b0_fixture",
                "claim_scope": "test",
                "artifacts": {"attempts": {"sha256": sha256_file(b0_path)}},
            }
        ),
        encoding="utf-8",
    )
    return b0_path, manifest_path


def _envelope() -> dict:
    modality_start = SOURCE_TEXT.index(MODALITY_TEXT)
    actor_start = SOURCE_TEXT.index(ACTOR_TEXT)
    condition_start = SOURCE_TEXT.index(CONDITION_TEXT)
    return {
        "sample_id": "syn_000001",
        "clause_id": "syn_000001.c1",
        "repair_fields": [
            "modality", "actors", "conditions", "constraints", "exceptions",
            "actor_action_map",
        ],
        "patches": {
            "modality": {
                "label": "permission",
                "evidence": [
                    {
                        "text": MODALITY_TEXT,
                        "start": modality_start,
                        "end": modality_start + len(MODALITY_TEXT) + 4,
                    }
                ],
            },
            "actors": [
                {
                    "id": "syn_000001.c1.actor.1",
                    "text": ACTOR_TEXT,
                    "start": actor_start + 2,
                    "end": actor_start + len(ACTOR_TEXT) + 1,
                    "normalized": ACTOR_TEXT,
                }
            ],
            "conditions": [
                {
                    "id": "syn_000001.c1.condition.1",
                    "text": CONDITION_TEXT,
                    "start": condition_start + 2,
                    "end": condition_start + len(CONDITION_TEXT) + 3,
                    "normalized": CONDITION_TEXT,
                }
            ],
            "constraints": {"absent": True},
            "exceptions": {"absent": True},
            "actor_action_map": [
                {
                    "actor_id": "syn_000001.c1.actor.1",
                    "action_id": "syn_000001.c1.action.1",
                }
            ],
        },
        "reason": "synthetic forensic fixture",
    }


def _rejection_errors() -> list[str]:
    env = _envelope()
    m = env["patches"]["modality"]["evidence"][0]
    a = env["patches"]["actors"][0]
    c = env["patches"]["conditions"][0]
    src = SOURCE_TEXT
    return [
        "post-patch canonical validation failed",
        f"clauses[0].modality.evidence[0] span text {m['text']!r} does not "
        f"match source_text[{m['start']}:{m['end']}]={src[m['start']:m['end']]!r}",
        f"clauses[0].actors[0] span text {a['text']!r} does not match "
        f"source_text[{a['start']}:{a['end']}]={src[a['start']:a['end']]!r}",
        f"clauses[0].conditions[0] span text {c['text']!r} does not match "
        f"source_text[{c['start']}:{c['end']}]={src[c['start']:c['end']]!r}",
    ]


def _capture_row(tmp_path: Path, b0_path: Path) -> dict:
    record = load_b0_predictions(b0_path)[0].record
    env = _envelope()
    content = json.dumps(env, ensure_ascii=False)
    row = {
        "request_id": "syn_000001/syn_000001.c1",
        "sample_id": "syn_000001",
        "clause_id": "syn_000001.c1",
        "clause_index": 0,
        "prompt_sha256": load_prompt("rule_first_llm_fallback_masked_prompt").sha256,
        "prompt_variant": "masked_selected_v5",
        "b0_prediction_sha256": prediction_hash(record),
        "request_body_sha256": "0" * 64,
        "response_body_sha256": "1" * 64,
        "http_status": 200,
        "content_type": "application/json",
        "endpoint": {"scheme": "https", "host": "api.synthetic.invalid", "port": None, "path": "/v1/chat/completions"},
        "models": {
            "requested": "deepseek-v4-flash",
            "resolved": "deepseek-v4-flash",
            "returned": "deepseek-v4-flash",
        },
        "request_policy": {"stream": False, "thinking": {"type": "disabled"}, "response_format": {"type": "json_object"}, "tools_sent": False},
        "extraction_status": "ok_message_content",
        "extraction_source": "message.content",
        "finish_reason": "stop",
        "response_id": "syn-id-1",
        "response_object": "chat.completion",
        "usage": {"prompt_tokens": 1305, "completion_tokens": 436, "total_tokens": 1741},
        "reasoning": {"present": False, "utf8_length": None, "sha256": None},
        "tool_calls": {"count": 0, "summaries": []},
        "message_content_sha256": FORENSICS._sha256_text(content),
        "sanitized_response_envelope": {
            "status": "ok_message_content",
            "content": content,
        },
        "safety": {"raw_response_saved": False, "sanitized": True},
    }
    return row


def _canary_manifest(capture_path: Path) -> dict:
    return {
        "schema_version": "h1_selective_manifest@2.0.0",
        "llm_calls": 1,
        "h1_non_identity_gate": False,
        "transport": {"capture_sha256": sha256_file(capture_path)},
        "effective_patch": {
            "rejection_reason_counts": {"canonical_invalid": 1, "reference_mismatch": 1}
        },
        "patch_events": [
            {
                "sample_id": "syn_000001",
                "clause_id": "syn_000001.c1",
                "selected_for_call": True,
                "rejection_reasons": _rejection_errors(),
            }
        ],
    }


def _write_canary_bundle(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    b0_path, b0_manifest = _write_b0_bundle(tmp_path)
    capture_path = tmp_path / "transport_capture.jsonl"
    capture_path.write_text(
        json.dumps(_capture_row(tmp_path, b0_path), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "canary_manifest.json"
    manifest_path.write_text(
        json.dumps(_canary_manifest(capture_path)), encoding="utf-8"
    )
    return capture_path, manifest_path, b0_path, b0_manifest


def _run_forensics(capture, manifest, b0, b0_manifest, output_dir) -> int:
    return FORENSICS.main(
        [
            "--capture", str(capture),
            "--canary-manifest", str(manifest),
            "--b0-predictions", str(b0),
            "--b0-manifest", str(b0_manifest),
            "--output-dir", str(output_dir),
        ]
    )


class TestAnalyzeSpan:
    def test_slice_ok_span(self):
        row = FORENSICS.analyze_span(
            field_path="modality.evidence[0]",
            text=MODALITY_TEXT,
            start=0,
            end=len(MODALITY_TEXT),
            source_text=SOURCE_TEXT,
            clause_span=CLAUSE_SPAN,
        )
        assert row["slice_matches"] is True
        assert "slice_ok" in row["classification_codes"]
        assert row["full_source_occurrences"] == 1
        assert row["clause_window_occurrences"] == 1

    def test_wrong_coordinates_unique_match(self):
        start = SOURCE_TEXT.index(MODALITY_TEXT)
        row = FORENSICS.analyze_span(
            field_path="modality.evidence[0]",
            text=MODALITY_TEXT,
            start=start,
            end=start + len(MODALITY_TEXT) + 4,
            source_text=SOURCE_TEXT,
            clause_span=CLAUSE_SPAN,
        )
        assert row["slice_matches"] is False
        assert row["full_source_occurrences"] == 1
        assert row["full_source_unique_start"] == 0
        assert row["full_source_unique_end"] == len(MODALITY_TEXT)
        assert "correct_text_wrong_coordinates" in row["classification_codes"]
        assert row["proposed_text_char_length"] == row["proposed_text_utf8_length"]
        assert row["source_text_all_ascii"] is True
        assert "unicode_byte_confusion_possible" not in row["classification_codes"]

    def test_zero_match(self):
        row = FORENSICS.analyze_span(
            field_path="actors[0]",
            text="never appears anywhere",
            start=0,
            end=10,
            source_text=SOURCE_TEXT,
            clause_span=CLAUSE_SPAN,
        )
        assert row["full_source_occurrences"] == 0
        assert "zero_match" in row["classification_codes"]

    def test_ambiguous_match(self):
        text = "alpha"
        row = FORENSICS.analyze_span(
            field_path="actors[0]",
            text=text,
            start=0,
            end=len(text) + 1,
            source_text=f"{text} beta {text}",
            clause_span=CLAUSE_SPAN,
        )
        assert row["full_source_occurrences"] == 2
        assert row["slice_matches"] is False
        assert "ambiguous_match" in row["classification_codes"]

    def test_unicode_byte_length_evidence(self):
        source = "caf\xe9 au lait, caf\xe9 cr\xe8me"
        text = "caf\xe9"
        row = FORENSICS.analyze_span(
            field_path="actors[0]",
            text=text,
            start=0,
            end=5,
            source_text=source,
            clause_span={"start": 0, "end": len(source)},
        )
        assert row["source_text_all_ascii"] is False
        assert row["proposed_text_utf8_length"] != row["proposed_text_char_length"]
        assert "unicode_byte_confusion_possible" in row["classification_codes"]


class TestReanchoring:
    def test_unique_corrections(self):
        corrections, failures = FORENSICS.build_counterfactual_corrections(
            FORENSICS.extract_patch_spans(_envelope()), SOURCE_TEXT, CLAUSE_SPAN
        )
        assert corrections is not None
        assert failures == {}
        assert corrections["modality.evidence[0]"] == (0, len(MODALITY_TEXT))
        assert corrections["actors[0]"] == (
            SOURCE_TEXT.index(ACTOR_TEXT),
            SOURCE_TEXT.index(ACTOR_TEXT) + len(ACTOR_TEXT),
        )
        assert corrections["conditions[0]"] == (
            SOURCE_TEXT.index(CONDITION_TEXT),
            SOURCE_TEXT.index(CONDITION_TEXT) + len(CONDITION_TEXT),
        )

    def test_zero_match_fails_closed(self):
        spans = [
            {
                "field_path": "actors[0]",
                "span": {"text": "does not exist", "start": 1, "end": 9},
            }
        ]
        corrections, failures = FORENSICS.build_counterfactual_corrections(
            spans, SOURCE_TEXT, CLAUSE_SPAN
        )
        assert corrections is None
        assert "zero_match" in failures["actors[0]"]

    def test_ambiguous_match_fails_closed(self):
        text = "alpha"
        source = f"{text} beta {text}"
        spans = [
            {
                "field_path": "actors[0]",
                "span": {"text": text, "start": 0, "end": len(text) + 1},
            }
        ]
        corrections, failures = FORENSICS.build_counterfactual_corrections(
            spans, source, {"start": 0, "end": len(source)}
        )
        assert corrections is None
        assert "ambiguous_match" in failures["actors[0]"]

    def test_empty_text_fails_closed(self):
        spans = [{"field_path": "actors[0]", "span": {"text": "", "start": 0, "end": 0}}]
        corrections, failures = FORENSICS.build_counterfactual_corrections(
            spans, SOURCE_TEXT, CLAUSE_SPAN
        )
        assert corrections is None
        assert "empty" in failures["actors[0]"]

    def test_corrections_touch_only_start_end(self):
        envelope = _envelope()
        corrections, _ = FORENSICS.build_counterfactual_corrections(
            FORENSICS.extract_patch_spans(envelope), SOURCE_TEXT, CLAUSE_SPAN
        )
        corrected = FORENSICS.apply_corrections(envelope, corrections)
        before = _envelope()
        after = corrected
        # Semantic content is untouched: sample_id, clause_id, repair_fields,
        # labels, texts, ids, normalized values, relations, absent markers.
        for key in ("sample_id", "clause_id", "repair_fields", "reason"):
            assert before[key] == after[key]
        assert before["patches"]["modality"]["label"] == after["patches"]["modality"]["label"]
        assert (
            before["patches"]["modality"]["evidence"][0]["text"]
            == after["patches"]["modality"]["evidence"][0]["text"]
        )
        assert before["patches"]["actors"][0]["id"] == after["patches"]["actors"][0]["id"]
        assert before["patches"]["conditions"][0]["normalized"] == after["patches"]["conditions"][0]["normalized"]
        assert before["patches"]["constraints"] == after["patches"]["constraints"]
        assert before["patches"]["exceptions"] == after["patches"]["exceptions"]
        assert before["patches"]["actor_action_map"] == after["patches"]["actor_action_map"]
        # Only the three mismatch spans' offsets changed.
        assert before["patches"]["modality"]["evidence"][0] != after["patches"]["modality"]["evidence"][0]
        assert after["patches"]["modality"]["evidence"][0] == {
            "text": MODALITY_TEXT, "start": 0, "end": len(MODALITY_TEXT),
        }


class TestParsingHelpers:
    def test_extract_patch_spans_flattens(self):
        spans = FORENSICS.extract_patch_spans(_envelope())
        paths = [s["field_path"] for s in spans]
        assert paths == ["modality.evidence[0]", "actors[0]", "conditions[0]"]

    def test_collect_rejected_field_paths(self):
        paths = FORENSICS.collect_rejected_field_paths(_rejection_errors())
        assert paths == ["modality.evidence[0]", "actors[0]", "conditions[0]"]

    def test_span_text_quoted_extraction(self):
        text = FORENSICS._span_text_of(_rejection_errors()[1])
        assert text == MODALITY_TEXT


class TestReconstructBody:
    def test_body_decodes_to_same_content(self, tmp_path):
        b0_path, _ = _write_b0_bundle(tmp_path)
        row = _capture_row(tmp_path, b0_path)
        content = row["sanitized_response_envelope"]["content"]
        body = FORENSICS.reconstruct_response_body(row, content)
        decode = decode_chat_completion_envelope(body, "application/json")
        assert decode["status"] == "ok_message_content"
        assert decode["content"] == content
        assert decode["model"] == "deepseek-v4-flash"
        assert decode["finish_reason"] == "stop"
        assert decode["usage"]["prompt_tokens"] == 1305


class TestMainEndToEnd:
    def test_forensics_success_and_determinism(self, tmp_path):
        capture, manifest, b0, b0_manifest = _write_canary_bundle(tmp_path)
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        assert _run_forensics(capture, manifest, b0, b0_manifest, out1) == 0
        assert _run_forensics(capture, manifest, b0, b0_manifest, out2) == 0
        for name in ("diagnostics.json", "transport_replay_row.jsonl",
                     "counterfactual_responses.jsonl"):
            a = (out1 / name).read_bytes()
            b = (out2 / name).read_bytes()
            assert a == b, name
        diagnostics = json.loads((out1 / "diagnostics.json").read_text(encoding="utf-8"))
        assert diagnostics["sample_id"] == "syn_000001"
        assert diagnostics["counterfactual"]["ready"] is True
        assert all(binding["ok"] for binding in diagnostics["bindings"])
        rejected = [
            row for row in diagnostics["span_diagnostics"] if not row["slice_matches"]
        ]
        assert [row["field_path"] for row in rejected] == [
            "modality.evidence[0]", "actors[0]", "conditions[0]",
        ]
        assert all(
            "correct_text_wrong_coordinates" in row["classification_codes"]
            for row in rejected
        )
        # No raw text anywhere in the diagnostics.
        raw = (out1 / "diagnostics.json").read_bytes()
        assert SOURCE_TEXT.encode("utf-8") not in raw
        assert MODALITY_TEXT.encode("utf-8") not in raw

    def test_overwrite_refusal(self, tmp_path):
        capture, manifest, b0, b0_manifest = _write_canary_bundle(tmp_path)
        out = tmp_path / "out"
        assert _run_forensics(capture, manifest, b0, b0_manifest, out) == 0
        assert _run_forensics(capture, manifest, b0, b0_manifest, out) == 2

    def test_binding_violation_fails_closed(self, tmp_path):
        capture, manifest, b0, b0_manifest = _write_canary_bundle(tmp_path)
        manifest_dict = json.loads(manifest.read_text(encoding="utf-8"))
        manifest_dict["llm_calls"] = 2
        manifest.write_text(json.dumps(manifest_dict), encoding="utf-8")
        assert _run_forensics(capture, manifest, b0, b0_manifest, tmp_path / "out") == 2

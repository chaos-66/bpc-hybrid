from __future__ import annotations

import json
from pathlib import Path

import pytest

from bpc_hybrid.estg150_b0_development import (
    Estg150B0DevelopmentError,
    _parse_bridge_output,
    build_canonical_gold_records,
    canonical_gold_record,
    summarize_evaluation,
)
from bpc_hybrid.stage2_canonical import validate_canonical
from formal_experiment.s2_7_b0_development_gate import (
    S27B0DevelopmentExpectations,
    verify_s2_7_b0_development_gate,
)


ROOT = Path(__file__).resolve().parents[1]
LAYER_E = ROOT / "data/development/human_review/estg_150_human_correction_v1.json"
MEMBERSHIP = ROOT / "data/development/estg/estg_150_membership_hashes.json"
LOW_QUOTA_PILOT = ROOT / "configs/models/estg150_h1_d1_low_quota_pilot_v1.json"


def test_frozen_layer_e_adapts_to_150_canonical_gold_records() -> None:
    gold, source = build_canonical_gold_records(LAYER_E, MEMBERSHIP)
    assert len(gold) == len(source) == 150
    assert sum(len(record["clauses"]) for record in gold) == 231
    assert len({record["sample_id"] for record in gold}) == 150
    assert all(validate_canonical(record).schema_valid for record in gold)
    assert all(validate_canonical(record).cross_field_valid for record in gold)


def test_gold_adapter_drops_review_metadata_and_adds_normalized_spans() -> None:
    layer_e = json.loads(LAYER_E.read_text(encoding="utf-8"))
    adapted = canonical_gold_record(layer_e["records"][0])
    blob = json.dumps(adapted, ensure_ascii=False)
    assert "decision" not in blob
    assert "review_state" not in blob
    spans = [
        span
        for clause in adapted["clauses"]
        for field in ("actors", "actions", "conditions", "constraints", "exceptions")
        for span in clause[field]
    ]
    assert all(span["normalized"] == " ".join(span["text"].casefold().split()) for span in spans)


def test_gold_adapter_rejects_missing_approved_text() -> None:
    layer_e = json.loads(LAYER_E.read_text(encoding="utf-8"))
    record = dict(layer_e["records"][0])
    record["approved_text_en"] = None
    with pytest.raises(Estg150B0DevelopmentError, match="approved_text_en"):
        canonical_gold_record(record)


def test_summary_derives_modality_accuracy_and_exposes_prf() -> None:
    report = {
        "membership": {"sample_count": 2},
        "primary_metrics": {
            "modality": {
                "labels": ["obligation", "prohibition", "permission", "definition"],
                "macro_f1": 0.5,
                "per_class": {},
                "confusion_matrix": {
                    "obligation": {"obligation": 1, "prohibition": 0, "permission": 0, "definition": 0},
                    "prohibition": {"obligation": 0, "prohibition": 0, "permission": 0, "definition": 0},
                    "permission": {"obligation": 1, "prohibition": 0, "permission": 0, "definition": 0},
                    "definition": {"obligation": 0, "prohibition": 0, "permission": 0, "definition": 0},
                },
                "missing_prediction_by_gold_class": {
                    "obligation": 0, "prohibition": 0, "permission": 0, "definition": 0
                },
            },
            "fields": {
                "action": {
                    "strict_exact": {"precision": 0.5, "recall": 0.25, "f1": 1 / 3},
                    "token_overlap_micro": {"precision": 0.75, "recall": 0.5, "f1": 0.6},
                }
            },
        },
        "structural_encoding": {"clause_segmentation": {}},
        "semantic_coverage": {},
    }
    summary = summarize_evaluation(report)
    assert summary["modality_clause_accuracy"] == 0.5
    assert summary["field_strict_exact"]["action"]["recall"] == 0.25


def test_batch_bridge_parser_records_terminal_tree_removal() -> None:
    cases, summary = _parse_bridge_output(
        "MATCH\t0\tconstraint\t0\t3\tall text\t1\ttrue\n"
        "MISS\t0\texception\n"
        "MISS\t0\taction\n"
        "MISS\t0\tactor\n"
        "TERMINAL_TREE_REMOVALS\t1\n"
        "SUMMARY\t1\t12\t1\t1\n"
    )
    assert len(cases) == 1
    assert summary["tree_count"] == 1
    assert summary["terminal_tree_removal_count"] == 1


def test_exact_development_gate_locks_metrics_membership_and_no_llm() -> None:
    gate = verify_s2_7_b0_development_gate(ROOT)
    assert gate["ready"] is True
    assert gate["development_only"] is True
    assert gate["formal_performance_result"] is False
    assert gate["all150"]["sample_count"] == 150
    assert gate["independent82_sensitivity"]["sample_count"] == 82
    assert gate["llm_call_count"] == 0


def test_exact_development_gate_rejects_hash_drift() -> None:
    bad = S27B0DevelopmentExpectations(config_sha256="0" * 64)
    gate = verify_s2_7_b0_development_gate(ROOT, expectations=bad)
    assert gate["ready"] is False
    assert "s2_7_b0_dev_config_hash_mismatch" in gate["blockers"]


def test_low_quota_pilot_is_paired_bounded_and_not_silently_remodeled() -> None:
    plan = json.loads(LOW_QUOTA_PILOT.read_text(encoding="utf-8"))
    samples = plan["selection"]["samples"]
    assert len(samples) == len({item["sample_id"] for item in samples}) == 7
    assert all(item["b0_confidence"] < 0.6 for item in samples)
    assert plan["budget"] == {
        "h1_max_calls": 7,
        "d1_max_calls": 7,
        "combined_max_calls": 14,
        "max_retries": 0,
    }
    assert plan["model_boundary"]["codex_subagent_exact_model_available"] is False
    assert plan["model_boundary"]["silent_substitution_allowed"] is False
    assert plan["safety"]["llm_api_called"] is False

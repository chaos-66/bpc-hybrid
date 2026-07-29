from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest
import torch

from bpc_hybrid.b0_v10.alignment import AlignmentResult, AlignmentStatus
from bpc_hybrid.b0_v10.clause_probability_adapter_b2a2 import (
    ClauseProbabilityAdapterError,
    predict_clause_probability_vectors,
    validate_probability_mapping,
)
from bpc_hybrid.b0_v10.definition_resolver import (
    CLASSIFIER_ONLY_DEFINITION_MIN_CONF,
)
from bpc_hybrid.b0_v10.definition_resolver_b2a2 import resolve_modality_b2a2
from bpc_hybrid.b0_v10.modality import ModalityRoute, resolve_modality_v10
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction


ROOT = Path(__file__).resolve().parents[1]
LEXICON = load_lexicon_v2(ROOT)
VALID_PROBABILITIES = {
    "definition": 0.70,
    "obligation": 0.12,
    "permission": 0.10,
    "prohibition": 0.08,
}


def _alignment(
    status: AlignmentStatus = AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT,
    text: str | None = "Dies ist derselbe deutsche Teilsatz.",
) -> AlignmentResult:
    return AlignmentResult(
        text,
        status,
        0.9 if status in {
            AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT,
            AlignmentStatus.VALIDATED_SPLIT,
        } else 0.5,
        {},
        (0,) if text else (),
        0,
    )


def _decision(
    english: str,
    *,
    alignment: AlignmentResult | None = None,
    german: str | None = None,
    clause: ModalityPrediction | None = None,
    probabilities: dict[str, float] | None = None,
    record: ModalityPrediction | None = None,
):
    selected_alignment = alignment or _alignment()
    return resolve_modality_b2a2(
        english_clause=english,
        german_clause=selected_alignment.text if german is None else german,
        alignment=selected_alignment,
        clause_classifier=clause,
        clause_probabilities=probabilities,
        record_classifier=record or ModalityPrediction("obligation", 0.41),
        lexicon=LEXICON,
    )


@pytest.mark.parametrize(
    "english",
    [
        "Income shall mean net profit.",
        "Expenditure means non-capital costs.",
        "Taxable income is defined as the residual amount.",
        "Business assets refers to assets used for the business.",
    ],
)
def test_strong_english_definitions_remain_definition(english: str) -> None:
    decision = _decision(
        english,
        clause=ModalityPrediction("obligation", 0.74),
        probabilities={**VALID_PROBABILITIES, "definition": 0.2, "obligation": 0.62},
    )
    assert decision.label == "definition"
    assert decision.route == ModalityRoute.DEFINITION_STRUCTURE


def test_validated_german_definition_anchor_remains_definition() -> None:
    german = "Einkünfte bedeutet den Nettogewinn."
    decision = _decision(
        "This term covers the net amount.",
        alignment=_alignment(text=german),
        german=german,
        clause=ModalityPrediction("obligation", 0.74),
        probabilities={**VALID_PROBABILITIES, "definition": 0.2, "obligation": 0.62},
    )
    assert decision.label == "definition"
    assert decision.diagnostic["b2a2_rule"] == "validated_align_german_definition_anchor"


@pytest.mark.parametrize(
    ("english", "expected"),
    [
        ("The taxpayer may not claim the allowance.", "prohibition"),
        ("The taxpayer may claim the allowance.", "permission"),
        ("The taxpayer shall pay the tax due.", "obligation"),
    ],
)
def test_explicit_deontic_markers_keep_priority(english: str, expected: str) -> None:
    decision = _decision(
        english,
        clause=ModalityPrediction("definition", 0.91),
        probabilities=VALID_PROBABILITIES,
    )
    assert decision.label == expected
    assert decision.route.value != "definition_rejected_clause_local_constrained"


def test_strict_classifier_definition_acceptance_uses_existing_threshold() -> None:
    decision = _decision(
        "Taxable income is the amount after deductions.",
        clause=ModalityPrediction("definition", CLASSIFIER_ONLY_DEFINITION_MIN_CONF),
        probabilities=VALID_PROBABILITIES,
    )
    assert decision.label == "definition"
    assert decision.diagnostic["b2a2_rule"] == "classifier_only_definition_strict"


@pytest.mark.parametrize(
    ("probabilities", "expected"),
    [
        ({"definition": 0.70, "obligation": 0.20, "permission": 0.06, "prohibition": 0.04}, "obligation"),
        ({"definition": 0.70, "obligation": 0.04, "permission": 0.20, "prohibition": 0.06}, "permission"),
        ({"definition": 0.70, "obligation": 0.04, "permission": 0.06, "prohibition": 0.20}, "prohibition"),
    ],
)
def test_rejected_definition_decodes_only_non_definition_argmax(
    probabilities: dict[str, float], expected: str
) -> None:
    decision = _decision(
        "The amount applies for the relevant year.",
        clause=ModalityPrediction("definition", 0.70),
        probabilities=probabilities,
        record=ModalityPrediction("definition", 0.99),
    )
    assert decision.label == expected
    assert decision.confidence == probabilities[expected]
    assert decision.route.value == "definition_rejected_clause_local_constrained"
    assert decision.route != ModalityRoute.RECORD_LEVEL_FALLBACK


def test_both_classifiers_definition_never_copies_record_definition() -> None:
    decision = _decision(
        "The amount applies for the relevant year.",
        clause=ModalityPrediction("definition", 0.70),
        probabilities=VALID_PROBABILITIES,
        record=ModalityPrediction("definition", 0.99),
    )
    assert decision.label == "obligation"
    assert decision.diagnostic["record_classifier_used_for_final_label"] is False


def test_record_classifier_is_irrelevant_to_constrained_decoding() -> None:
    inputs = dict(
        english="The amount applies for the relevant year.",
        clause=ModalityPrediction("definition", 0.70),
        probabilities=VALID_PROBABILITIES,
    )
    definition_record = _decision(
        **inputs, record=ModalityPrediction("definition", 0.99)
    )
    prohibition_record = _decision(
        **inputs, record=ModalityPrediction("prohibition", 0.99)
    )
    assert (
        definition_record.label,
        definition_record.route,
        definition_record.confidence,
    ) == (
        prohibition_record.label,
        prohibition_record.route,
        prohibition_record.confidence,
    )


def test_unsupported_clause_keeps_exact_parent_decision_fields() -> None:
    alignment = _alignment(AlignmentStatus.UNSUPPORTED, None)
    record = ModalityPrediction("permission", 0.37)
    parent = resolve_modality_v10(
        english_clause="Income shall mean net profit.",
        alignment=alignment,
        clause_classifier=None,
        record_classifier=record,
        lexicon=LEXICON,
    )
    decision = _decision(
        "Income shall mean net profit.",
        alignment=alignment,
        clause=None,
        probabilities=None,
        record=record,
    )
    assert (decision.label, decision.route, decision.confidence, decision.uses_clause_classifier) == (
        parent.label,
        parent.route,
        parent.confidence,
        parent.uses_clause_classifier,
    )


def test_missing_clause_probabilities_keep_exact_parent_decision_fields() -> None:
    alignment = _alignment()
    clause = ModalityPrediction("definition", 0.73)
    record = ModalityPrediction("prohibition", 0.88)
    parent = resolve_modality_v10(
        english_clause="The amount applies for the relevant year.",
        alignment=alignment,
        clause_classifier=clause,
        record_classifier=record,
        lexicon=LEXICON,
    )
    decision = _decision(
        "The amount applies for the relevant year.",
        alignment=alignment,
        clause=clause,
        probabilities=None,
        record=record,
    )
    assert (decision.label, decision.route, decision.confidence, decision.uses_clause_classifier) == (
        parent.label,
        parent.route,
        parent.confidence,
        parent.uses_clause_classifier,
    )


def test_non_definition_parent_decision_is_unchanged() -> None:
    alignment = _alignment()
    clause = ModalityPrediction("permission", 0.66)
    record = ModalityPrediction("obligation", 0.81)
    parent = resolve_modality_v10(
        english_clause="The amount applies for the relevant year.",
        alignment=alignment,
        clause_classifier=clause,
        record_classifier=record,
        lexicon=LEXICON,
    )
    decision = _decision(
        "The amount applies for the relevant year.",
        alignment=alignment,
        clause=clause,
        probabilities=VALID_PROBABILITIES,
        record=record,
    )
    assert (decision.label, decision.route, decision.confidence, decision.uses_clause_classifier) == (
        parent.label,
        parent.route,
        parent.confidence,
        parent.uses_clause_classifier,
    )


@pytest.mark.parametrize(
    "probabilities",
    [
        {"definition": 0.7, "obligation": 0.2, "permission": 0.1},
        {"definition": 0.7, "obligation": 0.2, "permission": 0.1, "prohibition": 0.1},
        {"definition": math.nan, "obligation": 0.2, "permission": 0.1, "prohibition": 0.7},
    ],
)
def test_invalid_probability_mappings_fail_closed(probabilities: dict[str, float]) -> None:
    with pytest.raises(ClauseProbabilityAdapterError):
        validate_probability_mapping(probabilities)


@pytest.mark.parametrize("texts", [[], [""], ["   "], ["."]])
def test_empty_and_placeholder_inputs_fail_closed(texts: list[str]) -> None:
    with pytest.raises(ClauseProbabilityAdapterError):
        predict_clause_probability_vectors(SimpleNamespace(), texts)


def test_probability_adapter_returns_complete_same_text_vector() -> None:
    class Tokenizer:
        def __call__(self, texts, **kwargs):
            assert texts == ["derselbe Teilsatz"]
            return {
                "input_ids": torch.tensor([[1, 2]]),
                "attention_mask": torch.tensor([[1, 1]]),
            }

    class Model:
        def __call__(self, **kwargs):
            return torch.tensor([[4.0, 3.0, 2.0, 1.0]])

    inference = SimpleNamespace(
        tokenizer=Tokenizer(), model=Model(), max_length=128, device="cpu"
    )
    vector = predict_clause_probability_vectors(inference, ["derselbe Teilsatz"])[0]
    assert vector.text == "derselbe Teilsatz"
    assert tuple(vector.probabilities) == (
        "definition",
        "obligation",
        "permission",
        "prohibition",
    )
    assert math.isclose(
        sum(vector.probabilities.values()), 1.0, rel_tol=1e-6, abs_tol=1e-6
    )
    assert vector.top_label == "definition"


def test_constrained_diagnostics_are_route_honest() -> None:
    decision = _decision(
        "The amount applies for the relevant year.",
        clause=ModalityPrediction("definition", 0.70),
        probabilities=VALID_PROBABILITIES,
        record=ModalityPrediction("definition", 0.99),
    )
    assert decision.diagnostic["b2a2_probability_input"] == "same_aligned_german_clause_text"
    assert decision.diagnostic["uses_clause_classifier"] is True
    assert decision.diagnostic["record_classifier_used_for_final_label"] is False
    assert decision.diagnostic["b2a2_clause_probabilities"] == VALID_PROBABILITIES


def test_no_sample_id_or_placeholder_decision_logic_is_present() -> None:
    resolver = (ROOT / "src/bpc_hybrid/b0_v10/definition_resolver_b2a2.py").read_text(
        encoding="utf-8"
    )
    adapter = (ROOT / "src/bpc_hybrid/b0_v10/clause_probability_adapter_b2a2.py").read_text(
        encoding="utf-8"
    )
    assert "sample_id" not in resolver
    assert "sample_id" not in adapter
    assert "placeholder_classifier_input\": True" not in resolver


def test_runner_help_is_windows_utf8_subprocess_safe() -> None:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/run_estg150_b0_enhanced_b2a2_development.py"),
            "--help",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert "--runtime-home" in completed.stdout

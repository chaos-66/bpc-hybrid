from __future__ import annotations

from bpc_hybrid.b0_v10.alignment import AlignmentResult, AlignmentStatus
from bpc_hybrid.b0_v10.definition_resolver import (
    CLASSIFIER_ONLY_DEFINITION_MIN_CONF,
    resolve_modality_b2a,
)
from bpc_hybrid.sun_style.lexicon_v2_runtime import load_lexicon_v2
from bpc_hybrid.sun_style.sun_b0 import ModalityPrediction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEX = load_lexicon_v2(ROOT)


def _al(status: AlignmentStatus, text: str | None = "de text") -> AlignmentResult:
    return AlignmentResult(text, status, 0.9 if status.name.startswith("VALIDATED") else 0.5, {}, (0,), 0)


def _dec(en: str, *, al=None, clf=None, record=None, de=None):
    return resolve_modality_b2a(
        english_clause=en,
        german_clause=de,
        alignment=al or _al(AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT),
        clause_classifier=clf,
        record_classifier=record or ModalityPrediction("obligation", 0.4),
        lexicon=LEX,
    )


def test_shall_mean_is_definition() -> None:
    d = _dec("Income shall mean net profit.", clf=ModalityPrediction("obligation", 0.9))
    assert d.label == "definition"
    assert d.diagnostic["b2a_rule"] == "en_strong_definition_structure"


def test_means_is_definition() -> None:
    d = _dec("Expenditure means costs that are not capital.")
    assert d.label == "definition"


def test_is_defined_as_is_definition() -> None:
    d = _dec("Taxable income is defined as the residual amount.")
    assert d.label == "definition"


def test_refers_to_is_definition() -> None:
    d = _dec("Business assets refers to assets used for the business.")
    assert d.label == "definition"


def test_german_bedeutet_with_validated_align() -> None:
    d = _dec(
        "This term covers the net amount.",
        de="Einkünfte bedeutet den Nettogewinn.",
        al=_al(AlignmentStatus.VALIDATED_ANCHOR_ALIGNMENT, "Einkünfte bedeutet den Nettogewinn."),
        clf=ModalityPrediction("obligation", 0.8),
    )
    assert d.label == "definition"
    assert "german_definition" in d.diagnostic["b2a_rule"]


def test_shall_pay_not_definition() -> None:
    d = _dec("The taxpayer shall pay the tax due.", clf=ModalityPrediction("definition", 0.95))
    assert d.label == "obligation"
    assert d.label != "definition"


def test_may_apply_not_definition() -> None:
    d = _dec("The office may apply the reduced rate.", clf=ModalityPrediction("definition", 0.9))
    assert d.label == "permission"


def test_shall_not_apply_not_definition() -> None:
    d = _dec("This section shall not apply to partnerships.", clf=ModalityPrediction("definition", 0.9))
    assert d.label == "prohibition"


def test_classifier_definition_blocked_when_unvalidated() -> None:
    d = _dec(
        "Something is the residual amount after deductions.",
        al=_al(AlignmentStatus.HEURISTIC_MONOTONE_PACK_UNVALIDATED),
        clf=ModalityPrediction("definition", 0.99),
        record=ModalityPrediction("obligation", 0.5),
    )
    assert d.label != "definition" or d.diagnostic.get("b2a_rule") == "en_strong_definition_structure"


def test_classifier_definition_blocked_with_permission_marker() -> None:
    d = _dec(
        "The taxpayer may claim the allowance.",
        al=_al(AlignmentStatus.VALIDATED_SPLIT),
        clf=ModalityPrediction("definition", 0.99),
    )
    assert d.label == "permission"


def test_threshold_constant_is_preregistered() -> None:
    assert CLASSIFIER_ONLY_DEFINITION_MIN_CONF == 0.55

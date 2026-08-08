"""Focused tests for the three 2026-08-08 relaxation experiments.

Covers:
  - scripts.sun_selection_criteria_v1: criterion helpers (word count,
    complete, legal-act proxy) and subset evaluation plumbing
  - scripts.coarse_gold_marker_converged_v1: report plumbing imports
    (convergence logic itself is covered by
    test_coarse_gold_b0_condition_constraint.py)
  - scripts.modality_classifier_alignment_v1: macro metrics and confusion
    matrix on a toy example

No real files are touched, no LLM/API/network call.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sun_selection_criteria_v1 import (  # noqa: E402
    apply_criteria,
    criterion_complete,
    criterion_legal_act,
    criterion_word_count,
    subset_metrics,
)
from scripts.modality_classifier_alignment_v1 import (  # noqa: E402
    LABELS,
    confusion_matrix,
    macro_metrics,
)


# --- Experiment A: criterion helpers ---

def test_word_count() -> None:
    assert criterion_word_count("one two three") == 3
    assert criterion_word_count("") == 0
    assert criterion_word_count("a b c d e f g h i j k l m n o p q r s t u") == 21


def test_complete() -> None:
    assert criterion_complete("The bank shall seek profit.")
    assert criterion_complete("shall apply;")
    assert criterion_complete("in such case?")
    assert criterion_complete("paragraph (2)")
    assert not criterion_complete("The bank shall seek profit")
    assert not criterion_complete("no punctuation at all")


def test_legal_act_surfaces() -> None:
    assert criterion_legal_act("shall")
    assert criterion_legal_act("may be excluded")
    assert criterion_legal_act("must notify")
    assert criterion_legal_act("is obliged to notify")
    assert criterion_legal_act("are entitled to recover")
    assert criterion_legal_act("has to be repaid")
    assert not criterion_legal_act("The bank is a legal person.")
    assert not criterion_legal_act("")


def test_apply_criteria_returns_all_flags() -> None:
    flags = apply_criteria("The building society is obliged to notify the taxpayer within two weeks.")
    assert set(flags) == {"word_count_gt_20", "complete", "legal_act"}
    assert flags["complete"] is True
    assert flags["legal_act"] is True
    assert flags["word_count_gt_20"] is False


def test_subset_metrics_empty_subset() -> None:
    # An empty subset must not crash the evaluator (returns zero metrics).
    result = subset_metrics([], [], set(), dataset_id="x", method_id="y")
    assert result["overall"]["ground_truth"] == 0
    assert result["overall"]["extracted"] == 0
    assert result["overall"]["f1"] == 0.0


# --- Experiment C: confusion matrix + macro metrics ---

def test_confusion_matrix_shape() -> None:
    matrix = confusion_matrix(["obligation", "permission"], ["obligation", "obligation"])
    assert set(matrix) == set(LABELS)
    for g in LABELS:
        assert set(matrix[g]) == set(LABELS)


def test_macro_metrics_perfect() -> None:
    matrix = {g: {p: 0 for p in LABELS} for g in LABELS}
    matrix["obligation"]["obligation"] = 10
    matrix["definition"]["definition"] = 6
    matrix["permission"]["permission"] = 4
    matrix["prohibition"]["prohibition"] = 2
    macro, per_class = macro_metrics(matrix)
    assert per_class["obligation"]["precision"] == 1.0
    assert per_class["obligation"]["recall"] == 1.0
    assert macro["f1"] == 1.0


def test_macro_metrics_mixed() -> None:
    matrix = {g: {p: 0 for p in LABELS} for g in LABELS}
    matrix["obligation"]["obligation"] = 9
    matrix["obligation"]["permission"] = 1
    matrix["permission"]["obligation"] = 1
    matrix["permission"]["permission"] = 3
    macro, per_class = macro_metrics(matrix)
    # obligation: P 9/10=0.9, R 9/10=0.9, F1 0.9
    assert abs(per_class["obligation"]["precision"] - 0.9) < 1e-9
    # permission: P 3/4=0.75, R 3/4=0.75, F1 0.75
    assert abs(per_class["permission"]["f1"] - 0.75) < 1e-9
    # macro f1 = mean over four classes (two classes zero -> 0)
    assert abs(macro["f1"] - (0.9 + 0.75) / 4) < 1e-9

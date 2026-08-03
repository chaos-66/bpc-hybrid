from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_b0_error_types import (  # noqa: E402
    _span_intersects,
    classify_field,
    clause_planning_diagnostic,
    modality_label_panel,
)


def span(start: int, end: int) -> dict[str, int]:
    return {"start": start, "end": end}


def clause(cid: str, start: int, end: int) -> dict[str, object]:
    return {
        "clause_id": cid,
        "clause_span": {"start": start, "end": end},
        "modality": {"label": "obligation", "evidence": [span(start, start + 2)]},
        "actors": [],
        "actions": [],
        "conditions": [],
        "constraints": [],
        "exceptions": [],
    }


class TestIntersects:
    def test_touching_spans_do_not_intersect(self) -> None:
        assert _span_intersects(span(0, 5), span(5, 10)) is False

    def test_partial_overlap_intersects(self) -> None:
        assert _span_intersects(span(0, 10), span(8, 12)) is True


class TestClassifyField:
    def test_missed_content_in_other_field(self) -> None:
        gold = [span(0, 10)]
        pred_other = [span(2, 8)]
        out = classify_field(gold, [], gold_other=[], pred_other=pred_other)
        assert out["missed"] == 1
        assert out["missed_subtypes"] == {"content_in_other_field": 1, "no_overlap": 0}

    def test_missed_absent_and_extra_with_and_without_gold(self) -> None:
        gold = [span(20, 30)]
        pred = [span(40, 50), span(0, 5)]
        out = classify_field(gold, pred, gold_other=[span(0, 5)], pred_other=[])
        assert out["missed"] == 1
        assert out["missed_subtypes"]["no_overlap"] == 1
        assert out["misclassified"] == 2
        assert out["misclassified_subtypes"] == {
            "overlaps_other_field_gold": 1,
            "no_gold_overlap": 1,
        }

    def test_matched_quality_counts(self) -> None:
        gold = [span(0, 10)]
        pred = [span(0, 10), span(0, 20), span(9, 12)]
        out = classify_field(gold, pred, gold_other=[], pred_other=[])
        assert out["matched_gold"] == 1
        assert out["matched_quality"] == {"exact": 1, "containment": 0, "partial": 0}
        assert out["matched_pred"] == 3


class TestModalityLabelPanel:
    def test_label_accuracy_and_confusion(self) -> None:
        gold = {"clauses": [
            {**clause("g1", 0, 20), "modality": {"label": "obligation", "evidence": [span(2, 6)]}},
            {**clause("g2", 20, 40), "modality": {"label": "permission", "evidence": [span(22, 26)]}},
        ]}
        pred = {"clauses": [
            {**clause("p1", 0, 20), "modality": {"label": "obligation", "evidence": [span(3, 7)]}},
            {**clause("p2", 20, 40), "modality": {"label": "obligation", "evidence": [span(23, 27)]}},
        ]}
        panel = modality_label_panel(gold, pred)
        assert panel["evidence_matched_clauses"] == 2
        assert panel["label_accuracy_matched"] == 0.5
        assert panel["confusion"]["obligation"]["obligation"] == 1
        assert panel["confusion"]["permission"]["obligation"] == 1


class TestClausePlanningDiagnostic:
    def test_unmatched_gold_clauses(self) -> None:
        gold = {"clauses": [clause("g1", 0, 50), clause("g2", 100, 150)]}
        pred = {"clauses": [clause("p1", 0, 48)]}
        out = clause_planning_diagnostic(gold, pred)
        assert out["gold_clauses"] == 2
        assert out["pred_clauses"] == 1
        assert out["gold_clauses_matched_iou05"] == 1
        assert out["gold_clauses_unmatched"] == 1

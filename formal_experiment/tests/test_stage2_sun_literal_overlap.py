from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bpc_hybrid.stage2_sun_literal_overlap import (
    SunLiteralOverlapError,
    evaluate_sun_literal_overlap,
)


ROOT = Path(__file__).resolve().parents[1]


def span(start: int, end: int) -> dict[str, object]:
    return {"text": "x" * (end - start), "start": start, "end": end}


def record(sample_id: str, clause_spans: list[tuple[int, int]]) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "clauses": [
            {
                "clause_id": f"{sample_id}.c{index}",
                "clause_span": span(start, end),
                "modality": {
                    "label": "obligation",
                    "evidence": [span(start, start + 2)],
                },
                "actors": [],
                "actions": [],
                "conditions": [],
                "constraints": [],
                "exceptions": [],
            }
            for index, (start, end) in enumerate(clause_spans, start=1)
        ],
    }


def attempt(value: dict[str, object]) -> dict[str, object]:
    return {"sample_id": value["sample_id"], "request_status": "ok", "record": value}


def evaluate(gold: dict[str, object], predicted: dict[str, object]) -> dict[str, object]:
    return evaluate_sun_literal_overlap(
        [gold],
        [attempt(predicted)],
        dataset_id="fixture",
        method_id="fixture_method",
    )


def test_cross_clause_overlap_is_primary_match_without_clause_alignment() -> None:
    gold = record("s1", [(0, 10), (10, 20)])
    predicted = record("s1", [(0, 20)])
    gold["clauses"][1]["actions"] = [span(12, 16)]
    predicted["clauses"][0]["actions"] = [span(15, 18)]

    report = evaluate(gold, predicted)
    values = report["per_field"]["action"]

    assert report["clause_alignment_required"] is False
    assert report["assignment"] == "none_independent_overlap_coverage"
    assert values["matched_predictions"] == 1
    assert values["matched_ground_truth"] == 1
    assert values["precision"] == 1.0
    assert values["recall"] == 1.0


def test_legacy_b0_entry_point_delegates_to_global_literal_overlap() -> None:
    from bpc_hybrid.estg150_b0_development_v2 import (
        sun_table8_any_overlap_diagnostic,
    )

    gold = record("s1", [(0, 10), (10, 20)])
    predicted = record("s1", [(0, 20)])
    gold["clauses"][1]["constraints"] = [span(12, 16)]
    predicted["clauses"][0]["constraints"] = [span(15, 18)]

    report = sun_table8_any_overlap_diagnostic([gold], [attempt(predicted)])

    assert report["assignment"] == "none_independent_overlap_coverage"
    assert report["clause_alignment_required"] is False
    assert report["per_field"]["constraint"]["f1"] == 1.0


def test_versioned_config_and_b0_runner_lock_primary_and_diagnostic_roles() -> None:
    config = json.loads(
        (
            ROOT / "configs/evaluation/sun_table8_literal_overlap_v2.json"
        ).read_text(encoding="utf-8")
    )
    runner = (
        ROOT / "scripts/run_estg150_b0_enhanced_v10_development.py"
    ).read_text(encoding="utf-8")

    assert config["evaluation_unit"] == "statement"
    assert config["clause_alignment_required"] is False
    assert config["assignment"] == "none_independent_overlap_coverage"
    assert "sun_literal_overlap_primary" in runner
    assert "strict_clause_aligned_all150_diagnostic" in runner
    assert "strict_clause_aligned_independent82_diagnostic" in runner


def test_many_to_many_overlap_has_no_one_to_one_restriction() -> None:
    gold = record("s1", [(0, 20)])
    predicted = copy.deepcopy(gold)
    gold["clauses"][0]["actions"] = [span(2, 5), span(5, 8)]
    predicted["clauses"][0]["actions"] = [span(2, 8), span(3, 7)]

    values = evaluate(gold, predicted)["per_field"]["action"]

    assert values["matched_predictions"] == 2
    assert values["matched_ground_truth"] == 2
    assert values["precision"] == 1.0
    assert values["recall"] == 1.0


def test_one_character_intersection_matches_but_adjacent_spans_do_not() -> None:
    gold = record("s1", [(0, 30)])
    predicted = copy.deepcopy(gold)
    gold["clauses"][0]["conditions"] = [span(2, 6), span(12, 16)]
    predicted["clauses"][0]["conditions"] = [span(5, 9), span(16, 20)]

    values = evaluate(gold, predicted)["per_field"]["condition"]

    assert values["matched_predictions"] == 1
    assert values["matched_ground_truth"] == 1
    assert values["precision"] == 0.5
    assert values["recall"] == 0.5


def test_all_six_fields_use_the_same_overlap_rule() -> None:
    gold = record("s1", [(0, 30)])
    predicted = copy.deepcopy(gold)
    for key in ("actors", "actions", "conditions", "constraints", "exceptions"):
        gold["clauses"][0][key] = [span(4, 8)]
        predicted["clauses"][0][key] = [span(7, 12)]
    gold["clauses"][0]["modality"]["evidence"] = [span(4, 8)]
    predicted["clauses"][0]["modality"]["evidence"] = [span(7, 12)]
    predicted["clauses"][0]["modality"]["label"] = "permission"

    report = evaluate(gold, predicted)

    assert report["modality_policy"] == "evidence_span_extraction_only_label_ignored"
    for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
        assert report["per_field"][field]["precision"] == 1.0
        assert report["per_field"][field]["recall"] == 1.0


def test_invalid_attempt_remains_in_recall_denominator_as_empty_prediction() -> None:
    gold = record("s1", [(0, 20)])
    report = evaluate_sun_literal_overlap(
        [gold],
        [{"sample_id": "s1", "request_status": "schema_error", "record": None}],
        dataset_id="fixture",
        method_id="fixture_method",
    )

    assert report["invalid_attempt_count"] == 1
    assert report["per_field"]["modality"]["missed"] == 1


def test_membership_mismatch_and_invalid_spans_fail_closed() -> None:
    with pytest.raises(SunLiteralOverlapError, match="membership differs"):
        evaluate_sun_literal_overlap(
            [record("s1", [(0, 20)])],
            [attempt(record("s2", [(0, 20)]))],
            dataset_id="fixture",
            method_id="fixture_method",
        )

    gold = record("s1", [(0, 20)])
    predicted = copy.deepcopy(gold)
    predicted["clauses"][0]["actions"] = [{"text": "bad", "start": 4, "end": 4}]
    with pytest.raises(SunLiteralOverlapError, match=r"invalid \[start,end\) span"):
        evaluate(gold, predicted)

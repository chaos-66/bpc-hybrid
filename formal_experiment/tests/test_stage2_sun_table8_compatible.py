from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bpc_hybrid.estg150_b0_development import (
    build_canonical_gold_records,
    sha256_file,
)
from bpc_hybrid.stage2_sun_table8_compatible import (
    SunTable8EvaluationError,
    evaluate_sun_table8_compatible,
    evaluate_sun_table8_literal_overlap,
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
                "modality": {"label": "obligation", "evidence": [span(start, start + 2)]},
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


def evaluate(gold: list[dict[str, object]], predicted: list[dict[str, object]]):
    return evaluate_sun_table8_compatible(
        gold,
        [attempt(value) for value in predicted],
        dataset_id="fixture",
        method_id="fixture_method",
    )


def test_statement_level_any_nonempty_intersection_ignores_clause_boundaries() -> None:
    gold = record("s1", [(0, 10), (10, 20)])
    predicted = record("s1", [(0, 20)])
    gold["clauses"][1]["actions"] = [span(12, 16)]
    predicted["clauses"][0]["actions"] = [span(15, 18)]

    report = evaluate([gold], [predicted])

    assert report["clause_alignment_required"] is False
    assert report["per_field"]["action"] == {
        "ground_truth": 1,
        "extracted": 1,
        "matched": 1,
        "misclassified": 0,
        "missed": 0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }


def test_one_character_intersection_counts_as_match() -> None:
    gold = record("s1", [(0, 20)])
    predicted = copy.deepcopy(gold)
    gold["clauses"][0]["conditions"] = [span(2, 6)]
    predicted["clauses"][0]["conditions"] = [span(5, 9)]

    assert evaluate([gold], [predicted])["per_field"]["condition"]["matched"] == 1


def test_maximum_one_to_one_matching_preserves_table8_count_identities() -> None:
    gold = record("s1", [(0, 20)])
    predicted = copy.deepcopy(gold)
    gold["clauses"][0]["actions"] = [span(2, 5)]
    predicted["clauses"][0]["actions"] = [span(2, 6), span(3, 7)]

    values = evaluate([gold], [predicted])["per_field"]["action"]

    assert values["matched"] == 1
    assert values["misclassified"] == 1
    assert values["missed"] == 0
    assert values["extracted"] == values["matched"] + values["misclassified"]
    assert values["ground_truth"] == values["matched"] + values["missed"]


def test_modality_row_evaluates_evidence_span_not_four_class_label() -> None:
    gold = record("s1", [(0, 20)])
    predicted = copy.deepcopy(gold)
    predicted["clauses"][0]["modality"]["label"] = "permission"

    values = evaluate([gold], [predicted])["per_field"]["modality"]

    assert values["matched"] == 1
    assert values["precision"] == 1.0
    assert values["recall"] == 1.0


def test_invalid_attempt_is_kept_in_denominator_as_empty_prediction() -> None:
    gold = record("s1", [(0, 20)])
    report = evaluate_sun_table8_compatible(
        [gold],
        [{"sample_id": "s1", "request_status": "schema_error", "record": None}],
        dataset_id="fixture",
        method_id="fixture_method",
    )

    assert report["invalid_attempt_count"] == 1
    assert report["per_field"]["modality"]["missed"] == 1


def test_membership_mismatch_fails_closed() -> None:
    with pytest.raises(SunTable8EvaluationError, match="membership differs"):
        evaluate_sun_table8_compatible(
            [record("s1", [(0, 20)])],
            [attempt(record("s2", [(0, 20)]))],
            dataset_id="fixture",
            method_id="fixture_method",
        )


def test_versioned_b0_result_recomputes_from_bound_inputs() -> None:
    config_path = ROOT / "configs/models/estg150_b0_enhanced_s27_v10a.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    layer_e = ROOT / config["inputs"]["human_correction_layer_e"]["path"]
    membership = ROOT / config["inputs"]["membership_hashes"]["path"]
    attempts_path = (
        ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
    )
    output = ROOT / "outputs/development/s27_estg150_b0_sun_table8_compatible_v1"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    expected = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
    gold, _ = build_canonical_gold_records(layer_e, membership)

    actual = evaluate_sun_table8_compatible(
        gold,
        attempts,
        dataset_id=config["dataset_id"],
        method_id="sun_rule_only:b0_enhanced_v10a",
    )

    assert actual == expected
    assert expected["per_field"]["action"]["precision"] == pytest.approx(
        0.8285714285714286
    )
    assert expected["per_field"]["action"]["recall"] == pytest.approx(
        0.8218623481781376
    )
    assert manifest["input_binding"]["layer_e_sha256"] == sha256_file(layer_e)
    assert manifest["input_binding"]["b0_attempts_sha256"] == sha256_file(attempts_path)
    assert manifest["artifacts"]["metrics"]["sha256"] == sha256_file(
        output / "metrics.json"
    )


def test_literal_overlap_has_no_one_to_one_restriction() -> None:
    gold = record("s1", [(0, 20)])
    predicted = copy.deepcopy(gold)
    gold["clauses"][0]["actions"] = [span(2, 5), span(5, 8)]
    predicted["clauses"][0]["actions"] = [span(2, 8), span(3, 7)]

    report = evaluate_sun_table8_literal_overlap(
        [gold],
        [attempt(predicted)],
        dataset_id="fixture",
        method_id="fixture_method",
    )
    values = report["per_field"]["action"]

    assert report["assignment"] == "none_independent_overlap_coverage"
    assert values["matched_predictions"] == 2
    assert values["matched_ground_truth"] == 2
    assert values["precision"] == 1.0
    assert values["recall"] == 1.0


def test_literal_overlap_applies_to_every_semantic_field() -> None:
    gold = record("s1", [(0, 30)])
    predicted = copy.deepcopy(gold)
    for key in ("actors", "actions", "conditions", "constraints", "exceptions"):
        gold["clauses"][0][key] = [span(4, 8)]
        predicted["clauses"][0][key] = [span(7, 12)]
    gold["clauses"][0]["modality"]["evidence"] = [span(4, 8)]
    predicted["clauses"][0]["modality"]["evidence"] = [span(7, 12)]

    report = evaluate_sun_table8_literal_overlap(
        [gold],
        [attempt(predicted)],
        dataset_id="fixture",
        method_id="fixture_method",
    )

    for field in ("modality", "actor", "action", "condition", "constraint", "exception"):
        assert report["per_field"][field]["precision"] == 1.0
        assert report["per_field"][field]["recall"] == 1.0


def test_versioned_b0_literal_result_recomputes_from_bound_inputs() -> None:
    config = json.loads(
        (ROOT / "configs/models/estg150_b0_enhanced_s27_v10a.json").read_text(
            encoding="utf-8"
        )
    )
    layer_e = ROOT / config["inputs"]["human_correction_layer_e"]["path"]
    membership = ROOT / config["inputs"]["membership_hashes"]["path"]
    attempts_path = (
        ROOT / "outputs/development/s27_estg150_b0_enhanced_v10a/b0_attempts.json"
    )
    output = ROOT / "outputs/development/s27_estg150_b0_sun_table8_literal_v2"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    expected = json.loads((output / "metrics.json").read_text(encoding="utf-8"))
    attempts = json.loads(attempts_path.read_text(encoding="utf-8"))
    gold, _ = build_canonical_gold_records(layer_e, membership)

    actual = evaluate_sun_table8_literal_overlap(
        gold,
        attempts,
        dataset_id=config["dataset_id"],
        method_id="sun_rule_only:b0_enhanced_v10a",
    )

    assert actual == expected
    assert expected["per_field"]["action"]["precision"] == pytest.approx(
        0.8571428571428571
    )
    assert expected["per_field"]["action"]["recall"] == pytest.approx(
        0.8582995951417004
    )
    assert manifest["input_binding"]["layer_e_sha256"] == sha256_file(layer_e)
    assert manifest["artifacts"]["metrics"]["sha256"] == sha256_file(
        output / "metrics.json"
    )

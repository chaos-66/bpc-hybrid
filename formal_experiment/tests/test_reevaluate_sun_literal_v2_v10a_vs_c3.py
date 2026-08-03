from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reevaluate_sun_literal_v2_v10a_vs_c3 import (  # noqa: E402
    METRIC_KEYS,
    ReevaluationError,
    compute_delta,
    git_blob_oid,
    git_full_sha,
    git_show_bytes,
    semantic_hash_json,
    validate_attempts,
)


def _record(sample_id: str) -> dict[str, object]:
    return {"sample_id": sample_id, "clauses": []}


def _attempt(sample_id: str, status: str = "ok") -> dict[str, object]:
    return {"sample_id": sample_id, "request_status": status, "record": _record(sample_id)}


def _metrics(values: dict[str, float | int]) -> dict[str, float | int]:
    return {key: values.get(key, 0) for key in METRIC_KEYS}


class TestSemanticHash:
    def test_deterministic_across_call_and_key_order(self) -> None:
        obj = {"b": 2, "a": [{"x": 1, "y": "z"}], "c": "德文文本"}
        first = semantic_hash_json(obj)
        reordered = semantic_hash_json({"c": "德文文本", "b": 2, "a": [{"y": "z", "x": 1}]})
        assert first == reordered
        assert first == semantic_hash_json(obj)

    def test_sensitive_to_value(self) -> None:
        assert semantic_hash_json({"a": 1}) != semantic_hash_json({"a": 2})


class TestDelta:
    def test_c3_minus_v10a_arithmetic(self) -> None:
        v10a = {"overall": _metrics({"precision": 0.5, "recall": 0.4, "f1": 0.44,
                                     "ground_truth": 100, "extracted": 80,
                                     "matched_predictions": 40, "matched_ground_truth": 40,
                                     "misclassified": 40, "missed": 60}),
                "per_field": {"action": _metrics({"precision": 0.6, "recall": 0.5, "f1": 0.545,
                                                  "ground_truth": 50, "extracted": 40,
                                                  "matched_predictions": 24, "matched_ground_truth": 25,
                                                  "misclassified": 16, "missed": 25})}}
        c3 = {"overall": _metrics({"precision": 0.6, "recall": 0.5, "f1": 0.545,
                                   "ground_truth": 100, "extracted": 90,
                                   "matched_predictions": 54, "matched_ground_truth": 50,
                                   "misclassified": 36, "missed": 50}),
              "per_field": {"action": _metrics({"precision": 0.7, "recall": 0.6, "f1": 0.646,
                                                "ground_truth": 50, "extracted": 40,
                                                "matched_predictions": 28, "matched_ground_truth": 30,
                                                "misclassified": 12, "missed": 20})}}

        delta = compute_delta(v10a, c3)
        assert delta["basis"] == "c3_minus_v10a"
        assert delta["overall"]["precision"] == pytest.approx(0.1)
        assert delta["overall"]["recall"] == pytest.approx(0.1)
        assert delta["overall"]["ground_truth"] == 0
        assert delta["overall"]["extracted"] == 10
        assert delta["overall"]["matched_predictions"] == 14
        assert delta["overall"]["matched_ground_truth"] == 10
        assert delta["overall"]["misclassified"] == -4
        assert delta["overall"]["missed"] == -10
        assert delta["per_field"]["action"]["precision"] == pytest.approx(0.1)
        assert delta["per_field"]["action"]["recall"] == pytest.approx(0.1)
        assert delta["per_field"]["action"]["matched_predictions"] == 4
        assert delta["per_field"]["action"]["matched_ground_truth"] == 5

    def test_zero_delta_when_identical(self) -> None:
        same = {"overall": _metrics({"precision": 0.3, "recall": 0.2, "f1": 0.24}),
                "per_field": {"constraint": _metrics({})}}
        delta = compute_delta(same, copy.deepcopy(same))
        assert all(delta["overall"][k] == 0 for k in METRIC_KEYS)
        assert all(delta["per_field"]["constraint"][k] == 0 for k in METRIC_KEYS)


class TestValidateAttempts:
    def test_matching_ids_pass(self) -> None:
        gold = {"s1": _record("s1"), "s2": _record("s2")}
        attempts = [_attempt("s1"), _attempt("s2")]
        by_id = validate_attempts(gold, attempts, label="fixture")
        assert set(by_id) == {"s1", "s2"}

    def test_duplicate_ids_fail_closed(self) -> None:
        gold = {"s1": _record("s1")}
        with pytest.raises(ReevaluationError, match="unique non-empty"):
            validate_attempts(gold, [_attempt("s1"), _attempt("s1")], label="fixture")

    def test_missing_and_extra_ids_fail_closed(self) -> None:
        gold = {"s1": _record("s1"), "s2": _record("s2")}
        with pytest.raises(ReevaluationError, match="membership differs.*s2"):
            validate_attempts(gold, [_attempt("s1"), _attempt("s3")], label="fixture")


class TestGitHelpers:
    def test_git_show_bytes_round_trips_raw_blob_hash(self) -> None:
        bytes_out = git_show_bytes(
            "56d2b03",
            "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
        )
        assert len(bytes_out) > 0
        oid = git_blob_oid(
            "56d2b03",
            "formal_experiment/data/development/estg/estg_150_membership_hashes.json",
        )
        assert len(oid) == 40
        full = git_full_sha("56d2b03")
        assert len(full) == 40
        assert full.startswith("56d2b03")


class TestOutputFailClosed:
    def test_existing_output_dir_fails_closed(self, tmp_path: Path) -> None:
        from scripts.reevaluate_sun_literal_v2_v10a_vs_c3 import run

        target = tmp_path / "existing_out"
        target.mkdir()
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.reevaluate_sun_literal_v2_v10a_vs_c3",
                "--output-dir",
                str(target),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        assert completed.returncode == 2
        assert "refusing to overwrite" in completed.stderr
        assert list(target.iterdir()) == []

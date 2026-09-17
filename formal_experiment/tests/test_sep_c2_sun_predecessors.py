# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from bpc_hybrid.sun_predecessors import evaluation
from bpc_hybrid.sun_predecessors.keyword import KeywordClassifier
from bpc_hybrid.sun_predecessors.runner import build_artifacts

FORMAL_ROOT = Path(__file__).resolve().parents[1]
CONFIG = FORMAL_ROOT / "configs/sep_c2_sun_predecessors_v1/cf_kw_v1.json"


def test_cf_kw_keyword_priority_is_deterministic() -> None:
    classifier = KeywordClassifier(json.loads(CONFIG.read_text(encoding="utf-8")))
    assert classifier.classify("Der Antragsteller muss die Frist beachten.").label == "obligation"
    assert classifier.classify("Der Antragsteller darf die Frist nicht versäumen.").label == "prohibition"
    assert classifier.classify("Der Antragsteller ist berechtigt, die Frist zu verlängern.").label in {
        "permission",
        "obligation",
    }
    assert classifier.classify("Die Frist bezeichnet den Zeitraum.").label == "definition"
    assert classifier.classify("Eine sonstige Vorschrift.").label == "definition"


def test_cf_kw_build_is_replayable_and_gold_blind_for_prediction() -> None:
    first = build_artifacts("cf_kw", FORMAL_ROOT)
    second = build_artifacts("cf_kw", FORMAL_ROOT)
    assert first["artifacts"] == second["artifacts"]
    prediction = first["artifacts"][
        "outputs/evidence/sep_c2_sun_predecessors_v1/cf_kw/predictions.json"
    ]
    assert len(prediction["records"]) == 150
    assert all(row["request_status"] == "ok" for row in prediction["records"])
    report = first["report"]
    assert report["evaluation"]["records_expected"] == 150
    assert report["evaluation"]["records_missing"] == 0
    assert report["safety"]["gold_read_by_prediction_code"] is False


def test_modality_evaluator_uses_all_150_records_as_denominator() -> None:
    records = evaluation.load_formal_input(FORMAL_ROOT)
    attempts = [
        evaluation.make_attempt(
            sample_id=row["sample_id"],
            source_text=row["raw_text_de"],
            label="obligation",
            method_id="test_constant",
        )
        for row in records
    ]
    result = evaluation.evaluate_attempts(FORMAL_ROOT, attempts)
    assert result["records_expected"] == 150
    assert result["records_missing"] == 0
    assert result["records_failed"] == 0
    assert result["official_evaluator"]["records"] == 150
    assert sum(result["gold_support"].values()) == 150
    assert sum(result["predicted_count"].values()) == 150
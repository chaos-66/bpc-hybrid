# -*- coding: utf-8 -*-
"""Focused tests for the GDPR "原三类" Stage-2 -> Stage-3 linkage v1
(``scripts/run_gdpr_3type_linkage_v1.py`` + the deterministic capsule
converter ``bpc_hybrid/sun_stage3/gdpr_capsule_converter.py``).

Verifies, on the real frozen artifacts and real frozen Sun scoring:
(a) the reference arm is deterministic: two separate runs produce
    byte-identical predictions and deep-equal evaluations (and reproduce the
    committed S3.5 dev numbers on the same 33 violation items);
(b) predictions never depend on Gold: shuffling the Gold decision fields
    leaves the persisted predictions byte-identical (Gold is only consumed
    after predictions are fixed);
(c) a Rules-Only capsule with ZERO records yields explicit failure rows for
    every rule/item (no fabricated fields, nothing scored as compliant);
(d) all 33 items v001..v033 are present in both arms' output rows.
"""

from __future__ import annotations

import copy
import json
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_gdpr_3type_linkage_v1 as linkage  # noqa: E402

GOLD = ROOT / "data" / "gold" / "stage3" / "stage3_violation_gold_v1.json"
S35_DEV = ROOT / "outputs" / "development" / "s35_sun_stage3_development_v2"
REAL_REFERENCE_DIR = ROOT / "outputs" / "development" / "gdpr_3type_linkage_v1_reference"
REAL_RULES_ONLY_DIR = ROOT / "outputs" / "development" / "gdpr_3type_linkage_v1_rules_only"

EXPECTED_ITEM_IDS = [f"v{i:03d}" for i in range(1, 34)]
ALL_TYPES = ("missing_action", "incorrect_actor", "out_of_order")
CAPSULE_SCHEMA = "gdpr7_sun_rule_only_predictions@1.0.0"
RULE_IDS = ["article6", "article7", "article15", "article16", "article17",
            "article20", "article22", "article33", "article34"]

warnings.filterwarnings("ignore", category=UserWarning, module="winter_similarity")


def _read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ (a)
def test_reference_arm_double_run_byte_equal(tmp_path: Path) -> None:
    out1 = tmp_path / "run1"
    out2 = tmp_path / "run2"
    linkage.run_arm("reference", output_root=out1, report_root=out1 / "reports",
                    overwrite=True)
    linkage.run_arm("reference", output_root=out2, report_root=out2 / "reports",
                    overwrite=True)
    pred1 = (out1 / "gdpr_3type_linkage_v1_reference" / "predictions.jsonl").read_bytes()
    pred2 = (out2 / "gdpr_3type_linkage_v1_reference" / "predictions.jsonl").read_bytes()
    assert pred1 == pred2  # byte-identical second run
    rows = _read_rows(out1 / "gdpr_3type_linkage_v1_reference" / "predictions.jsonl")
    assert len(rows) == 33
    ev1 = _read_json(out1 / "gdpr_3type_linkage_v1_reference" / "evaluation.json")
    ev2 = _read_json(out2 / "gdpr_3type_linkage_v1_reference" / "evaluation.json")
    assert ev1 == ev2
    # reproduces the committed S3.5 dev evaluation numbers on the same items
    v = ev1["violation"]
    assert v["detected"] == 12
    assert v["exact_type_accuracy"] == pytest.approx(0.3636, abs=1e-4)
    assert v["macro_f1"] == pytest.approx(0.3889, abs=1e-4)
    assert v["unobservable"] == 10
    # Historical non-actor behavior must be unchanged. Definition 6 now
    # preserves action associations, so actor diagnostics are versioned in v2.
    stored = {r["item_id"]: r for r in _read_rows(S35_DEV / "predictions.jsonl")
              if r["task"] == "violation"}
    for row in rows:
        ref = stored[row["item_id"]]
        for key, value in ref.items():
            if key in ("run_id", "method_provenance", "incorrect_actor_score",
                       "incorrect_actor_observable", "incorrect_actor_reason", "scores"):
                continue
            assert row[key] == value, (row["item_id"], key)
        for key in ("missing_action", "out_of_order", "missing_action_denominator", "out_of_order_denominator"):
            assert row["scores"][key] == ref["scores"][key]


# ------------------------------------------------------------------ (b)
def _shuffle_gold_decisions(source: dict, rotation: int) -> dict:
    out = copy.deepcopy(source)
    for item in out["items"]:
        idx = ALL_TYPES.index(item["decision_violation_type"])
        item["decision_violation_type"] = ALL_TYPES[(idx + rotation) % len(ALL_TYPES)]
    return out


def test_predictions_invariant_under_gold_shuffle(tmp_path: Path) -> None:
    """Rules-Only arm: swapping the Gold decision types must not change any
    persisted prediction byte; only the post-hoc evaluation may differ."""
    gold = _read_json(GOLD)
    shuffled1 = tmp_path / "gold_shuffled_1.json"
    shuffled2 = tmp_path / "gold_shuffled_2.json"
    shuffled1.write_text(json.dumps(_shuffle_gold_decisions(gold, 1), ensure_ascii=False),
                         encoding="utf-8")
    shuffled2.write_text(json.dumps(_shuffle_gold_decisions(gold, 2), ensure_ascii=False),
                         encoding="utf-8")

    def _run(gold_path: Path, tag: str):
        out = tmp_path / tag
        linkage.run_arm("rules_only", output_root=out, report_root=out / "reports",
                        overwrite=True, gold_path=gold_path)
        return (out / "gdpr_3type_linkage_v1_rules_only" / "predictions.jsonl").read_bytes()

    p0 = _run(GOLD, "gold0")
    p1 = _run(shuffled1, "gold1")
    p2 = _run(shuffled2, "gold2")
    assert p1 == p0 == p2  # gold decisions never influence the prediction phase
    ev0 = _read_json(tmp_path / "gold0" / "gdpr_3type_linkage_v1_rules_only" / "evaluation.json")
    ev1 = _read_json(tmp_path / "gold1" / "gdpr_3type_linkage_v1_rules_only" / "evaluation.json")
    ev2 = _read_json(tmp_path / "gold2" / "gdpr_3type_linkage_v1_rules_only" / "evaluation.json")
    # the shuffles must disagree with the original Gold evaluation (i.e. the
    # evaluator really consumed the (shuffled) decisions after predictions
    # were fixed, proving the invariance test has power)
    assert ev0["violation"]["exact_type_accuracy"] != ev1["violation"]["exact_type_accuracy"]
    assert ev0["violation"]["exact_type_accuracy"] != ev2["violation"]["exact_type_accuracy"]


# ------------------------------------------------------------------ (c)
def test_zero_record_capsule_yields_explicit_failure_rows(tmp_path: Path) -> None:
    empty_capsule = {
        "schema_version": CAPSULE_SCHEMA,
        "dataset_id": "gdpr7_stage2_sentences_v1",
        "method_id": "sun_rule_only",
        "record_count": 0,
        "records": [],
    }
    capsule_path = tmp_path / "empty_capsule.json"
    capsule_path.write_text(json.dumps(empty_capsule, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    linkage.run_arm("rules_only", output_root=out, report_root=out / "reports",
                    overwrite=True, predictions_path=capsule_path)
    run_dir = out / "gdpr_3type_linkage_v1_rules_only"
    rows = _read_rows(run_dir / "predictions.jsonl")
    assert len(rows) == 33
    assert {r["item_id"] for r in rows} == set(EXPECTED_ITEM_IDS)
    # every item is an explicit failure row: no prediction, no fabricated fields
    for row in rows:
        assert row["rule_record_failed"] is True
        assert row["predicted_violation_type"] is None
        assert row["external_failure"] and "stage2_prediction_missing" in row["external_failure"]
        assert row["scores"]["missing_action"] is None
        assert row["scores"]["incorrect_actor"] is None
        assert row["scores"]["out_of_order"] is None
    assert {r["rule_id"] for r in rows} == set(RULE_IDS)
    # rule records: 9 failed records with empty actions/actors/order
    records = _read_rows(run_dir / "rule_records.jsonl")
    assert len(records) == 9
    for rec in records:
        assert rec["failed"] is True
        assert rec["actions"] == [] and rec["actors"] == [] and rec["order_relations"] == []
        assert rec["failure_reasons"]
    # explicit accounting in the evaluation/manifest
    ev = _read_json(run_dir / "evaluation.json")
    assert ev["capsule_failure_accounting"]["failed_row_count"] == 33
    manifest = _read_json(run_dir / "manifest.json")
    assert manifest["capsule_failure_accounting"]["failed_row_count"] == 33


# ------------------------------------------------------------------ (d)
@pytest.mark.parametrize("arm_dir", [REAL_REFERENCE_DIR, REAL_RULES_ONLY_DIR])
def test_all_33_items_present_in_output_rows(arm_dir: Path) -> None:
    rows = _read_rows(arm_dir / "predictions.jsonl")
    item_ids = [r["item_id"] for r in rows]
    assert item_ids == EXPECTED_ITEM_IDS  # sorted v001..v033, none missing
    assert len({r["item_id"] for r in rows}) == 33
    # evaluation denominator keeps every item
    ev = _read_json(arm_dir / "evaluation.json")
    assert ev["violation"]["denominator"]["total_items"] == 33
    assert len(ev["items"]) == 33


# ------------------------------------------------------- (e) Oracle arm
HUMAN_RULES_DIR = ROOT / "outputs" / "development" / "gdpr_3type_linkage_v1_human_rules"
HUMAN_GOLD = ROOT / "data" / "gold" / "stage3" / "gdpr7_gold_rule_records_v1.json"
HUMAN_CAPSULE = (ROOT / "data" / "predictions" / "gdpr7_human_rule_record_v1"
                 / "predictions.json")


def test_human_rules_arm_is_registered() -> None:
    assert "human_rules" in linkage.ARM_LABELS
    assert "human_rules" in linkage.CAPSULE_CONFIGS
    cfg = linkage.CAPSULE_CONFIGS["human_rules"]
    assert cfg["schema"] == "gdpr7_human_rule_record_predictions@1.0.0"
    assert cfg["expected_records"] == 74
    # the Oracle arm must NOT drop permission/prohibition/definition items
    assert tuple(cfg["include_modalities"]) == (
        "obligation", "permission", "prohibition", "definition")


def test_human_rules_capsule_is_bound_to_the_gold_rule_records() -> None:
    import hashlib
    capsule = _read_json(HUMAN_CAPSULE)
    gold = _read_json(HUMAN_GOLD)
    assert capsule["schema_version"] == "gdpr7_human_rule_record_predictions@1.0.0"
    assert capsule["record_count"] == 74
    assert len(capsule["records"]) == 74
    assert gold["counts"]["items"] == 92
    assert capsule["source_rule_record_schema"] == gold["schema_version"]
    capsule_manifest = _read_json(
        ROOT / "data/predictions/gdpr7_human_rule_record_v1/manifest.json")
    assert capsule_manifest["predictions_sha256"] == hashlib.sha256(
        HUMAN_CAPSULE.read_bytes()).hexdigest()
    assert capsule_manifest["source_rule_records"]["sha256"] == hashlib.sha256(
        HUMAN_GOLD.read_bytes()).hexdigest()


def test_human_rules_arm_run_is_deterministic(tmp_path: Path) -> None:
    """Two independent Oracle-arm runs must be byte-identical."""
    def _run(tag: str) -> bytes:
        out = tmp_path / tag
        linkage.run_arm("human_rules", output_root=out,
                        report_root=out / "reports", overwrite=True)
        return (out / "gdpr_3type_linkage_v1_human_rules"
                / "predictions.jsonl").read_bytes()

    first = _run("a")
    second = _run("b")
    assert first == second
    rows = [json.loads(line) for line in first.decode("utf-8").splitlines()
            if line.strip()]
    assert len(rows) == 33
    assert [r["item_id"] for r in rows] == EXPECTED_ITEM_IDS
    # the Oracle arm receives correct rules: no rule record may have failed
    assert all(r["rule_record_failed"] is False for r in rows)
    assert all(r["external_failure"] is None for r in rows)
    # predictions still precede Gold: every row is Gold-blind
    assert all(r["gold_visible"] is False for r in rows)


def test_human_rules_arm_includes_all_four_modalities() -> None:
    """The Oracle arm must consume every confirmed modality, not obligation only."""
    if not HUMAN_RULES_DIR.is_dir():
        pytest.skip("Oracle arm run dir not present")
    manifest = _read_json(HUMAN_RULES_DIR / "manifest.json")
    summary = manifest["rule_record_diagnostics"]["conversion_summary"]
    assert tuple(summary["include_modalities"]) == (
        "obligation", "permission", "prohibition", "definition")
    per_rule = summary["per_rule"]
    # every clause of every rule is included: nothing excluded by modality
    for rule_id, per in per_rule.items():
        assert per["envelopes_failed"] == 0, rule_id
        assert per["excluded_modality_counts"] == {}, rule_id
        assert per["included_clause_count"] == per["clause_count"], rule_id
        assert per["invalid_span_count"] == 0, rule_id


def test_human_rules_arm_records_the_gold_rule_records_as_source() -> None:
    if not HUMAN_RULES_DIR.is_dir():
        pytest.skip("Oracle arm run dir not present")
    manifest = _read_json(HUMAN_RULES_DIR / "manifest.json")
    diag = manifest["rule_record_diagnostics"]
    assert diag["capsule_schema"] == "gdpr7_human_rule_record_predictions@1.0.0"
    assert "gdpr7_human_rule_record_v1" in diag["capsule_path"]
    assert diag["capsule_integrity"]["all_rows_ok"] is True
    assert diag["capsule_integrity"]["unique_samples"] == 74

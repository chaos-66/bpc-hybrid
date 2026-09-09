"""Oracle Stage 3 with Gold rules: inputs, determinism, and claim boundaries.

Offline; no LLM/API; never modifies Gold or existing predictions.
"""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_s3_oracle_gold_rules_v1 as oracle  # noqa: E402

REPORT = ROOT / "outputs/reports/s3_oracle_gold_rules_v1.json"
MANIFEST = ROOT / "outputs/reports/s3_oracle_gold_rules_v1.manifest.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_oracle_inputs_exist():
    assert oracle.GOLD_RULE_RECORDS.is_file()
    assert oracle.ORACLE_CAPSULE.is_file()
    assert oracle.ORACLE_CAPSULE_MANIFEST.is_file()


def test_report_is_present_and_bound():
    if not REPORT.is_file():
        pytest.skip("Oracle report not produced yet")
    report = _read(REPORT)
    assert report["run_id"] == oracle.RUN_ID
    assert report["scope"] == "development_only_frozen_evaluation_surface"
    # the claim boundary must be explicit: not the formal S3.7 main table
    assert "NOT the formal S3.7 main table" in report["claim_status"]
    assert report["zero_api"]["new_llm_api_calls"] == 0
    assert report["boundaries"]["gold_modified"] is False
    assert report["boundaries"]["thresholds_changed"] is False
    assert report["boundaries"]["llm_or_api_called"] is False


def test_oracle_uses_the_gold_rule_records_capsule():
    if not REPORT.is_file():
        pytest.skip("Oracle report not produced yet")
    report = _read(REPORT)
    assert report["rule_source"]["arm"] == "oracle"
    assert "gdpr7_human_rule_record_v1" in report["rule_source"]["capsule"]
    # every confirmed modality must reach the checker
    assert tuple(report["rule_source"]["include_modalities"]) == (
        "obligation", "permission", "prohibition", "definition")
    assert report["rule_source"]["failed_rules"] == []


def test_oracle_beats_reference_on_missing_action():
    """The correct rules must not lose the one fully observable check type."""
    if not REPORT.is_file():
        pytest.skip("Oracle report not produced yet")
    three = _read(REPORT)["original_three_types"]
    oracle_ma = three["oracle"]["evaluation"]["per_type"]["missing_action"]
    reference_ma = three["reference"]["evaluation"]["per_type"]["missing_action"]
    assert oracle_ma["f1"] == 1.0
    assert oracle_ma["f1"] >= reference_ma["f1"]


def test_unobservable_checks_are_reported_not_hidden():
    """incorrect_actor / out_of_order must stay in the denominator."""
    if not REPORT.is_file():
        pytest.skip("Oracle report not produced yet")
    ev = _read(REPORT)["original_three_types"]["oracle"]["evaluation"]
    assert ev["denominator"]["total_items"] == 33
    assert ev["denominator"]["per_type_support"]["incorrect_actor"] == 11
    assert ev["denominator"]["per_type_support"]["out_of_order"] == 11
    # unobservable items are counted as FN, never dropped
    assert ev["detected"] + ev["missed"] + ev["wrong_type"] == 33
    assert ev["denominator"]["unobservable_total"] == ev["unobservable"]


def test_mapping_diagnostic_explains_def6_observability():
    if not REPORT.is_file():
        pytest.skip("Oracle report not produced yet")
    diag = _read(REPORT)["mapping_diagnostics"]
    assert set(diag) == {"oracle_all_modalities", "oracle_obligation_only",
                         "reference"}
    for policy, per_rule in diag.items():
        assert set(per_rule) == {
            "article6", "article7", "article15", "article16", "article17",
            "article20", "article22", "article33", "article34"}
        for rule_id, block in per_rule.items():
            assert block["policy"] == policy
            assert block["def6_observable"] == (
                block["pairs_mapped_above_gamma"] > 0)
            assert len(block["best_action_matches"]) == block["action_count"]


def test_four_type_panel_keeps_controls_and_separates_panels():
    if not REPORT.is_file():
        pytest.skip("Oracle report not produced yet")
    report = _read(REPORT)
    four = report["extended_four_types"]
    assert set(four["methods"]) == {"winter", "sun", "bm25", "tfidf_svd"}
    for method, block in four["methods"].items():
        assert block["paired"]["total_objects"] == 80  # 40 variants + 40 controls
        assert block["evaluation"]["support"] == 40
    # the synthetic panel is never merged into the human Gold surface
    assert report["boundaries"]["synthetic_panel_merged_into_human_gold"] is False


def test_oracle_replay_is_deterministic():
    assert oracle.main(["--check"]) == 0


def test_manifest_binds_every_artifact():
    if not MANIFEST.is_file():
        pytest.skip("Oracle manifest not produced yet")
    import hashlib
    manifest = _read(MANIFEST)
    assert manifest["artifacts"]
    for path, entry in manifest["artifacts"].items():
        target = ROOT / path
        assert target.is_file(), path
        assert hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]

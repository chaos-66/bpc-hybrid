"""Stage-2 -> Stage-3 downstream paired comparison: arms, deltas, boundaries."""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "src", ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import run_s3_downstream_paired_v1 as paired  # noqa: E402

REPORT = ROOT / "outputs/reports/s3_downstream_paired_v1.json"
MANIFEST = ROOT / "outputs/reports/s3_downstream_paired_v1.manifest.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_arm_availability_is_derived_from_disk():
    arms = paired.arm_availability()
    assert set(arms) == {"rules_only", "human_rules", "direct_llm"}
    assert arms["rules_only"]["available"] is True
    assert arms["human_rules"]["available"] is True
    # the Direct-LLM capsule must not be invented
    assert arms["direct_llm"]["available"] is False
    assert arms["direct_llm"]["status"] == "blocked"
    assert arms["direct_llm"]["blocked_reason"]


def test_report_records_the_blocked_arm_without_imputing():
    if not REPORT.is_file():
        pytest.skip("paired report not produced yet")
    report = _read(REPORT)
    assert report["original_three_types"]["direct_llm"]["status"] == "blocked"
    assert report["extended_four_types"]["arms"]["direct_llm"]["status"] == "blocked"
    assert report["boundaries"]["missing_arm_fabricated"] is False
    assert "direct_llm_minus_rules_only" not in report["deltas"]


def test_report_shares_everything_except_the_rule_source():
    if not REPORT.is_file():
        pytest.skip("paired report not produced yet")
    report = _read(REPORT)
    assert report["bindings"]["thresholds"] == {"tau": 0.8, "gamma": 0.8,
                                                "theta": 0.8}
    assert report["boundaries"]["gold_modified"] is False
    assert report["boundaries"]["thresholds_changed"] is False
    assert report["boundaries"]["processes_changed"] is False
    assert report["boundaries"]["llm_or_api_called"] is False
    assert report["zero_api"]["new_llm_api_calls"] == 0


def test_both_available_arms_are_evaluated_on_the_human_gold():
    if not REPORT.is_file():
        pytest.skip("paired report not produced yet")
    three = _read(REPORT)["original_three_types"]
    for arm in ("rules_only", "human_rules"):
        block = three[arm]
        assert block["status"] == "evaluated"
        assert block["failed_rules"] == []
        ev = block["evaluation"]
        assert ev["denominator"]["total_items"] == 33
        assert ev["detected"] + ev["missed"] + ev["wrong_type"] == 33
        assert set(ev["per_type"]) == {"missing_action", "incorrect_actor",
                                       "out_of_order"}


def test_delta_isolates_the_rule_source():
    if not REPORT.is_file():
        pytest.skip("paired report not produced yet")
    report = _read(REPORT)
    delta = report["deltas"]["human_rules_minus_rules_only"]
    oracle = report["original_three_types"]["human_rules"]["evaluation"]
    baseline = report["original_three_types"]["rules_only"]["evaluation"]
    assert delta["macro_f1"] == round(oracle["macro_f1"] - baseline["macro_f1"], 6)
    assert delta["detected"] == oracle["detected"] - baseline["detected"]


def test_panel_bias_is_disclosed():
    if not REPORT.is_file():
        pytest.skip("paired report not produced yet")
    note = _read(REPORT)["conclusion"]["panel_bias_note"]
    # the panel binds to the development extraction, not to the human rules
    assert "stage3_gold_inference_v1" in note
    assert "first-valid-span" in note


def test_four_type_panel_has_controls_for_every_available_arm():
    if not REPORT.is_file():
        pytest.skip("paired report not produced yet")
    arms = _read(REPORT)["extended_four_types"]["arms"]
    for arm in ("rules_only", "human_rules"):
        for method, entry in arms[arm]["methods"].items():
            assert entry["paired"]["total_objects"] == 80
            assert entry["evaluation"]["support"] == 40


def test_replay_is_deterministic():
    assert paired.main(["--check"]) == 0


def test_manifest_binds_every_artifact():
    if not MANIFEST.is_file():
        pytest.skip("paired manifest not produced yet")
    import hashlib
    manifest = _read(MANIFEST)
    assert manifest["artifacts"]
    for path, entry in manifest["artifacts"].items():
        target = ROOT / path
        assert target.is_file(), path
        assert hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]

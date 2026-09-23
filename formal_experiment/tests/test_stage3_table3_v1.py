"""Tests for the final eligibility-audited Stage-3 Table 3."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "outputs/reports/stage3_table3_v1.json"
PACKET = ROOT / "outputs/reports/stage3_binding_final_human_approval_packet_v1.md"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_table3_uses_eligibility_and_separates_oracle():
    table = _load(TABLE)
    assert table["eligible_pairs"]["missing_action"].__len__() == 8
    assert table["eligible_pairs"]["incorrect_actor"].__len__() == 5
    assert table["eligible_pairs"]["out_of_order"] == []
    for method in ("sun_reconstruction", "winter_wrapper", "ours"):
        assert method in table["methods"]
    ours = table["methods"]["ours"]
    oracle = table["methods"]["oracle_grounded_upper_bound"]
    assert ours["per_type"]["missing_action"]["f1"] == 1.0
    assert ours["per_type"]["incorrect_actor"]["f1"] == 1.0
    assert ours["per_type"]["out_of_order"]["support"] == 0
    assert oracle["per_type"]["missing_action"]["f1"] == 1.0
    assert oracle["per_type"]["out_of_order"]["support"] == 0
    assert table["methods"]["sun_reconstruction"]["macro_f1_eligible_types"] < 1.0
    assert table["methods"]["winter_wrapper"]["macro_f1_eligible_types"] < 1.0
    assert "Oracle" in table["oracle_label"]


def test_human_approval_packet_exists_and_has_simple_options():
    text = PACKET.read_text(encoding="utf-8")
    assert "final human approval packet" in text
    assert "Pairs requiring approval: 19 / 30" in text
    assert "ACCEPT" in text and "CHANGE TO" in text and "N/A" in text
    assert "syn_out_of_order_01" in text
    assert "syn_incorrect_actor_06" in text

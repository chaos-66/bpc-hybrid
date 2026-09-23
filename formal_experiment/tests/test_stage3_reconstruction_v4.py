"""Independent construction checks; no fitted checker or LLM used as an oracle."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("reconstruction_v4", ROOT / "scripts/build_stage3_reconstruction_v4.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_sources_and_all_three_mutations_are_complete():
    artifacts = builder.build()
    manifest = json.loads(artifacts["manifest.json"])
    assert manifest["case_count"] == 20
    assert manifest["independent_source_requirements"] == 5
    assert manifest["scored_reference_cells"] == 50
    assert manifest["reference_not_applicable_cells"] == 10
    reference = json.loads(artifacts["construction_reference.json"])
    assert not reference["is_gold"] and not reference["human_adjudicated"]
    for row in reference["cases"]:
        source = row["source"]
        raw_text = (ROOT.parent / source["source_path"]).read_text(encoding="utf-8")
        start, end = source["char_span"]
        assert raw_text[start:end] == source["text"]
        for evidence in source["evidence"].values():
            a, b = evidence["span_in_excerpt"]
            assert source["text"][a:b] == evidence["text"]
        assert sum(v == "violated" for v in row["reference_states"].values()) == (row["variant"] != "control")


def test_mutation_integrity_detects_wrong_control_or_extra_error():
    config = json.loads(builder.CONFIG.read_text(encoding="utf-8"))
    rule = config["rules"][0]
    with pytest.raises(ValueError, match="single mutation"):
        builder.validate_construction(rule, builder.create_bpmn(rule, "out_of_order"), "control")
    raw = builder.create_bpmn(rule, "out_of_order").replace(b'name="Controller"', b'name="Data subject"')
    with pytest.raises(ValueError, match="single mutation"):
        builder.validate_construction(rule, raw, "out_of_order")


def test_inference_view_does_not_expose_reference_or_variant():
    artifacts = builder.build()
    view = json.loads(artifacts["inference_view.json"])
    for row in view["items"]:
        assert set(row) == {"case_id", "bpmn_path", "process_id"}
        assert all(v not in row["bpmn_path"] for v in builder.VARIANTS)
    inputs = json.loads(artifacts["stage2_input.json"])
    assert inputs["gold_visible"] is False
    assert len(inputs["rules"]) == 5


def test_missing_or_ambiguous_source_evidence_fails():
    config = json.loads(builder.CONFIG.read_text(encoding="utf-8"))
    bad = copy.deepcopy(config)
    bad["rules"][0]["order_marker"] = "ordinary and is sequential"
    with pytest.raises(ValueError, match="evidence must occur"):
        builder.build(bad)


def test_generated_models_pass_existing_structural_parser():
    from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file
    contract = load_stage1_contract(ROOT / "configs/stage1_structural_s11_s14.json")
    for path in sorted(builder.OUT.glob("bpmn/*.bpmn")):
        record = parse_bpmn_file(path, contract=contract)
        assert record["process_id"] == "Process"
        assert len(record["activities"]) in (3, 4)
    assert len(list(builder.OUT.glob("bpmn/*.bpmn"))) == 20

"""Formal GDPR-7 Gold Rule Records: lossless derivation, capsule wiring, verifier.

These tests are offline and deterministic.  They never modify the confirmed
human bundle, the published artifacts or any Gold.
"""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
import sys
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.gdpr7_gold_rule_records import (  # noqa: E402
    CAPSULE_SCHEMA,
    GoldRuleRecordError,
    build_capsule,
    build_rule_records,
    summarize,
)

CONFIRMED = (ROOT / "data/development/human_review/gdpr7_human_confirmed_v1"
             / "confirmed_rule_items.json")
GOLD = ROOT / "data/gold/stage3/gdpr7_gold_rule_records_v1.json"


def _load_script(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def confirmed():
    return json.loads(CONFIRMED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def converted(confirmed):
    rule_records = build_rule_records(confirmed)
    return rule_records, build_capsule(rule_records)


def test_counts_and_losslessness(confirmed, converted):
    rule_records, capsule = converted
    summary = summarize(rule_records, capsule)
    assert summary["rules"] == 9
    assert summary["sentences"] == 74
    assert summary["items"] == 92
    # element spans + modality evidence spans reproduce anchored_spans=320
    assert summary["spans"] + summary["modality_evidence_spans"] == 320
    assert capsule["record_count"] == 74
    assert capsule["unresolved_relation_endpoints"] == []
    # the confirmed input is never mutated
    assert confirmed["is_gold"] is False
    assert confirmed["status"] == "human_confirmed_not_published_gold"


def test_every_confirmed_item_becomes_its_own_clause(confirmed, converted):
    rule_records, _capsule = converted
    by_sample = {r["sample_id"]: r for r in rule_records["records"]}
    for record in confirmed["records"]:
        out = by_sample[record["sample_id"]]
        assert len(out["clauses"]) == len(record["rule_items"])
        for item, clause in zip(record["rule_items"], out["clauses"]):
            assert clause["item_id"] == item["item_id"]
            assert clause["modality"]["label"] == item["modality"]
            assert clause["clause_span"] == {"start": 0,
                                             "end": len(record["sentence_text"])}


def test_multi_modality_sentence_is_not_collapsed(converted):
    """The legacy export takes the first label; this contract must not."""
    rule_records, _capsule = converted
    record = next(r for r in rule_records["records"]
                  if r["sample_id"] == "gdpr_article17_s001")
    labels = [c["modality"]["label"] for c in record["clauses"]]
    assert labels == ["permission", "obligation"]
    assert len({c["clause_id"] for c in record["clauses"]}) == 2


def test_spans_reproduce_sentence_text(converted):
    rule_records, _capsule = converted
    for record in rule_records["records"]:
        text = record["sentence_text"]
        for clause in record["clauses"]:
            for span in clause["modality"]["evidence"]:
                assert text[span["start"]:span["end"]] == span["text"]
            for field in ("actors", "actions", "conditions", "constraints",
                          "exceptions"):
                for span in clause[field]:
                    assert text[span["start"]:span["end"]] == span["text"]


def test_actor_action_map_copied_verbatim(confirmed, converted):
    rule_records, _capsule = converted
    by_sample = {r["sample_id"]: r for r in rule_records["records"]}
    checked = 0
    for record in confirmed["records"]:
        out = by_sample[record["sample_id"]]
        for item, clause in zip(record["rule_items"], out["clauses"]):
            assert len(clause["actor_action_map"]) == len(item["actor_action_map"])
            for entry, source in zip(clause["actor_action_map"],
                                     item["actor_action_map"]):
                assert entry["actor_id"].endswith(
                    f".actor.{source['actor_span_index'] + 1}")
                if source["action_item_id"] == item["item_id"]:
                    assert entry["action_id"].endswith(".action.1")
                    checked += 1
                else:
                    assert entry["action_item_id"] == source["action_item_id"]
    assert checked == 38  # every confirmed binding is a within-item binding


def test_span_text_mismatch_raises(confirmed):
    doc = copy.deepcopy(confirmed)
    doc["records"][0]["rule_items"][0]["actor"][0]["text"] = "WRONG"
    with pytest.raises(GoldRuleRecordError):
        build_rule_records(doc)


def test_out_of_range_actor_index_raises(confirmed):
    doc = copy.deepcopy(confirmed)
    target = next(r for r in doc["records"]
                  if r["rule_items"][0]["actor_action_map"])
    target["rule_items"][0]["actor_action_map"][0]["actor_span_index"] = 99
    with pytest.raises(GoldRuleRecordError):
        build_rule_records(doc)


def test_bad_modality_raises(confirmed):
    doc = copy.deepcopy(confirmed)
    doc["records"][0]["rule_items"][0]["modality"] = "may"
    with pytest.raises(GoldRuleRecordError):
        build_rule_records(doc)


def test_duplicate_item_id_raises(confirmed):
    doc = copy.deepcopy(confirmed)
    items = doc["records"][0]["rule_items"]
    if len(items) < 2:
        pytest.skip("first sentence has a single item")
    items[1]["item_id"] = items[0]["item_id"]
    with pytest.raises(GoldRuleRecordError):
        build_rule_records(doc)


def test_wrong_source_schema_raises(confirmed):
    doc = copy.deepcopy(confirmed)
    doc["schema_version"] = "something_else@1.0.0"
    with pytest.raises(GoldRuleRecordError):
        build_rule_records(doc)


def test_deterministic_rebuild(confirmed, converted):
    rule_records, capsule = converted
    again = build_rule_records(confirmed)
    assert json.dumps(rule_records, ensure_ascii=False, sort_keys=True) == \
        json.dumps(again, ensure_ascii=False, sort_keys=True)
    assert build_capsule(again) == capsule


def test_stage3_converter_consumes_the_capsule(converted):
    """The published capsule must feed the frozen Stage-3 converter unchanged."""
    pytest.importorskip("spacy")
    from bpc_hybrid.sun_stage3.gdpr_capsule_converter import build_rule_records as conv
    _rule_records, capsule = converted
    input_doc = json.loads(
        (ROOT / "data/input/gdpr7_stage2_input_v1.json").read_text(encoding="utf-8"))
    texts = {s["sample_id"]: s["approved_text_en"]
             for rule in input_doc["rules"] for s in rule["sentences"]}
    rule_ids = sorted({rec["sample_id"].split("_s")[0][len("gdpr_"):]
                       for rec in capsule["records"]})
    records, summary = conv(
        capsule, texts, rule_ids,
        include_modalities=("obligation", "permission", "prohibition", "definition"),
        expected_schema=CAPSULE_SCHEMA)
    assert summary["capsule_schema_ok"] is True
    assert summary["total_envelopes_failed"] == 0
    assert summary["total_invalid_spans"] == 0
    # every rule keeps at least one action: the Oracle arm must not be empty
    assert all(rec["actions"] for rec in records.values())
    assert all(not rec["failed"] for rec in records.values())


def test_published_artifacts_match_a_fresh_build():
    """The published Gold and capsule must equal a fresh, fully bound build."""
    builder = _load_script("bgr_fresh",
                           "scripts/build_gdpr7_gold_rule_records_v1.py")
    rule_records, capsule, _hashes, _confirmed = builder.build_all()
    assert json.loads(GOLD.read_text(encoding="utf-8")) == rule_records
    assert json.loads(
        (ROOT / "data/predictions/gdpr7_human_rule_record_v1/predictions.json")
        .read_text(encoding="utf-8")) == capsule


def test_verifier_detects_a_tampered_artifact(tmp_path, monkeypatch):
    """The independent verifier must fail closed on a tampered Gold file."""
    verifier = _load_script("vgr", "scripts/verify_gdpr7_gold_rule_records_v1.py")
    assert verifier.main() == 0
    tampered = tmp_path / "gdpr7_gold_rule_records_v1.json"
    doc = json.loads(verifier.GOLD.read_text(encoding="utf-8"))
    doc["records"][0]["clauses"][0]["modality"]["label"] = "obligation"
    tampered.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
                         .encode("utf-8"))
    monkeypatch.setattr(verifier, "GOLD", tampered)
    assert verifier.main() != 0


def test_builder_check_mode_is_green():
    builder = _load_script("bgr", "scripts/build_gdpr7_gold_rule_records_v1.py")
    assert builder.main(["--check"]) == 0

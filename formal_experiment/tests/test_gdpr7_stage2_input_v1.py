# -*- coding: utf-8 -*-
"""Focused tests for the GDPR Stage-2 sentence input pack builder.

Verifies:
- the input pack is Gold-blind and structurally complete (9 rules / actual
  sentence count / hash bindings / no decision or panel labels);
- the builder's sentence segmentation exactly reproduces the segmentation of
  the frozen S3.9-EXT panel rule bindings (locked sentence_idx/text for all
  40 variants) and of the frozen inference pack used by Stage 3;
- deterministic content identity (output sha256 pinned);
- fail-closed guards: source drift rejected, overwrite refused.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_gdpr7_stage2_input_v1 import (  # noqa: E402
    EXPECTED_INFERENCE_PACK_SHA256,
    INFERENCE_PACK,
    OUTPUT,
    SCHEMA_VERSION,
    build,
    split_rule_sentences,
)
from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    extract_six_element_sentences,
)

EXPECTED_OUTPUT_SHA256 = "558b80131394c8ac349db42cc323ffcf7264b7ae7da796522d55bf5ff89eb109"
PANEL = ROOT / "data/development/stage3_synth/synthetic_controlled_error_extension_v2.json"


@pytest.fixture(scope="module")
def input_doc() -> dict:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_output_exists_and_matches_pinned_sha() -> None:
    assert OUTPUT.is_file()
    assert _sha256_bytes(OUTPUT.read_bytes()) == EXPECTED_OUTPUT_SHA256


def test_schema_and_gold_blindness(input_doc: dict) -> None:
    assert input_doc["schema_version"] == SCHEMA_VERSION
    assert input_doc["gold_visible"] is False
    assert input_doc["counts"] == {"rules": 9, "sentences": 74}
    assert input_doc["source"]["inference_pack_sha256"] == EXPECTED_INFERENCE_PACK_SHA256


def test_no_decision_or_panel_labels(input_doc: dict) -> None:
    forbidden = {
        "expected_violation", "decision", "check_type",
        "control_scores", "variant_id", "mutation_type", "gold",
    }
    found: list[str] = []

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in forbidden:
                    found.append(key)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(input_doc)
    assert found == []


def test_every_record_carries_bindings(input_doc: dict) -> None:
    seen: set[str] = set()
    for rule in input_doc["rules"]:
        assert rule["rule_id"].startswith("article")
        assert rule["sentence_count"] == len(rule["sentences"])
        for s in rule["sentences"]:
            assert s["sample_id"] not in seen
            seen.add(s["sample_id"])
            assert isinstance(s["approved_text_en"], str) and s["approved_text_en"].strip()
            assert isinstance(s["text_sha256"], str) and len(s["text_sha256"]) == 64
            assert s["char_span"][0] < s["char_span"][1]
            # hash of embedded text must match the recorded hash
            assert _sha256_bytes(
                s["approved_text_en"].encode("utf-8")) == s["text_sha256"]
    assert len(seen) == 74


def test_segmentation_matches_frozen_stage3_extraction() -> None:
    """The splitter must reproduce extract_six_element_sentences sentence
    boundaries (spaCy) exactly for all nine rule texts."""
    import spacy

    nlp = spacy.load("en_core_web_sm")
    pack = json.loads(INFERENCE_PACK.read_text(encoding="utf-8"))
    items = pack["matching_items"] + pack["violation_items"]
    texts: dict[str, str] = {}
    for it in items:
        texts.setdefault(it["rule_id"], it["rule_text"])
    assert len(texts) == 9
    for rid, text in texts.items():
        ours = split_rule_sentences(rid, text, nlp)
        ref = extract_six_element_sentences(rid, text, nlp)
        assert len(ours) == len(ref)
        for a, b in zip(ours, ref):
            assert a["sentence_idx"] == b["sentence_idx"]
            assert a["sentence_text"] == b["sentence_text"]


def test_segmentation_matches_locked_panel_bindings() -> None:
    """All 40 S3.9-EXT variants' locked (rule_id, sentence_idx,
    sentence_text) bindings must be reproduced by the splitter."""
    import spacy

    nlp = spacy.load("en_core_web_sm")
    pack = json.loads(INFERENCE_PACK.read_text(encoding="utf-8"))
    items = pack["matching_items"] + pack["violation_items"]
    texts: dict[str, str] = {}
    for it in items:
        texts.setdefault(it["rule_id"], it["rule_text"])
    panel = json.loads(PANEL.read_text(encoding="utf-8"))
    by_id = {v["variant_id"]: v for v in panel["variants"]}
    checked = 0
    for vid, meta in panel["rule_binding"]["per_variant"].items():
        sents = split_rule_sentences(meta["rule_id"], texts[meta["rule_id"]], nlp)
        sent = sents[meta["sentence_idx"]]
        assert sent["sentence_text"] == by_id[vid]["rule_element"]["sentence_text"]
        assert sent["sentence_idx"] == by_id[vid]["rule_element"]["sentence_idx"]
        checked += 1
    assert checked == 40


def test_builder_rejects_source_drift(tmp_path: Path) -> None:
    import copy

    doc = json.loads(INFERENCE_PACK.read_text(encoding="utf-8"))
    drifted = copy.deepcopy(doc)
    drifted["schema_version"] = "tampered"
    src = tmp_path / "pack.json"
    src.write_text(json.dumps(drifted), encoding="utf-8")
    # monkeypatch-free: builder validates its own constant against the real
    # path; emulate drift by pointing at the tampered copy with the real
    # constant -> sha mismatch must raise ValueError.
    with pytest.raises(ValueError):
        build(src, tmp_path / "out.json")


def test_builder_refuses_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "out.json"
    out.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(INFERENCE_PACK, out)

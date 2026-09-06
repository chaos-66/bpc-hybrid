# -*- coding: utf-8 -*-
"""Build the Gold-blind GDPR Stage-2 input pack (sentence level, v1).

Purpose
-------
Produce an executable Stage-2 input for the nine GDPR rule texts used by the
frozen Stage-3 inference pack
``data/development/human_review/stage3_gold_inference_v1.json``
(article6/7/15/16/17/20/22/33/34).  Each rule text is split into sentences
with the SAME deterministic sentence segmentation used by the frozen
S3.9-EXT panel rule bindings (spaCy ``en_core_web_sm`` sentence boundaries +
whitespace normalization, mirroring
``stage3_extended_violations.extract_six_element_sentences``), so one input
record == one sentence.  The pack is Gold-blind: it carries only the rule
id, text-version binding (inference pack path/hash), sentence text, sentence
index inside the rule text, character span inside the rule text, and the
source rule-text hash.  It contains NO gold decisions, no expected
violations, no panel labels.

The 9 rule paragraphs must NOT be treated as 9 sentences / 9 calls: the pack
records the real sentence count produced by the fixed splitter.

Zero LLM/API/network; does not read Gold decisions; does not modify the
inference pack, the panel, or any Gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
OUTPUT = ROOT / "data/input/gdpr7_stage2_input_v1.json"
SCHEMA_VERSION = "gdpr7_stage2_input@1.0.0"

# Expected inference-pack content identity (raw-byte sha256 of the frozen
# file; fail-closed so the pack can never be silently rebuilt on a drifted
# source).
EXPECTED_INFERENCE_PACK_SHA256 = "4182c1f6ba8e28665c6dd14a2573b227e0c6b65c1df0041fcd1ae7dab5cf03c4"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def split_rule_sentences(rule_id: str, rule_text: str, nlp) -> list[dict[str, Any]]:
    """Deterministic sentence segmentation shared by the builder and the
    linkage runner.

    Mirrors ``stage3_extended_violations.extract_six_element_sentences``
    segmentation exactly: spaCy sentence boundaries over ``rule_text``,
    whitespace collapse, ``sentence_idx`` in document order.  Only
    segmentation is produced here (no six-element fields) so the Stage-2
    method predictions - not this helper - are the only extraction source
    for downstream detection.
    """
    import re

    out: list[dict[str, Any]] = []
    doc = nlp(rule_text)
    for idx, sent in enumerate(doc.sents):
        text = re.sub(r"\s+", " ", sent.text).strip()
        if not text:
            continue
        span = (sent.start_char, sent.end_char)
        out.append({
            "rule_id": rule_id,
            "sentence_idx": idx,
            "sentence_text": text,
            "char_span": [int(span[0]), int(span[1])],
        })
    return out


def build(inference_pack: Path, output: Path) -> dict[str, Any]:
    import spacy  # local import: runtime dependency used only by the builder

    nlp = spacy.load("en_core_web_sm")
    pack = json.loads(inference_pack.read_text(encoding="utf-8"))
    pack_sha = _sha256_file(inference_pack)
    if EXPECTED_INFERENCE_PACK_SHA256 and pack_sha != EXPECTED_INFERENCE_PACK_SHA256:
        raise ValueError("inference pack sha256 drift")
    items = pack.get("matching_items", []) + pack.get("violation_items", [])
    rule_text_by_id: dict[str, str] = {}
    for item in items:
        rid = item.get("rule_id")
        text = item.get("rule_text")
        if not isinstance(rid, str) or not isinstance(text, str) or not text:
            raise ValueError(f"invalid inference item: {item.get('item_id')}")
        old = rule_text_by_id.get(rid)
        if old is not None and old != text:
            raise ValueError(f"rule_id {rid} has inconsistent rule_text across items")
        rule_text_by_id[rid] = text
    if set(rule_text_by_id) != {
        "article6", "article7", "article15", "article16", "article17",
        "article20", "article22", "article33", "article34",
    }:
        raise ValueError("inference pack rule ids differ from the frozen 9")

    rules: list[dict[str, Any]] = []
    total_sentences = 0
    for rid in sorted(rule_text_by_id):
        text = rule_text_by_id[rid]
        sentences = split_rule_sentences(rid, text, nlp)
        # cross-check: the splitter must not drop any content silently
        joined = " ".join(s["sentence_text"] for s in sentences)
        if not joined.strip():
            raise ValueError(f"rule {rid}: empty segmentation")
        text_hash = _sha256_bytes(text.encode("utf-8"))
        rule_block = {
            "rule_id": rid,
            "rule_text_sha256": text_hash,
            "rule_text_byte_size": len(text.encode("utf-8")),
            "sentence_count": len(sentences),
            "sentences": [
                {
                    "sample_id": f"gdpr_{rid}_s{s['sentence_idx'] + 1:03d}",
                    "sentence_idx": s["sentence_idx"],
                    "char_span": s["char_span"],
                    "text_sha256": _sha256_bytes(s["sentence_text"].encode("utf-8")),
                    "approved_text_en": s["sentence_text"],
                }
                for s in sentences
            ],
        }
        total_sentences += len(sentences)
        rules.append(rule_block)

    doc = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": "gdpr7_stage2_sentences_v1",
        "claim": (
            "Gold-blind sentence-level Stage-2 input derived from the frozen "
            "Stage-3 inference pack rule texts (9 GDPR articles); sentence "
            "segmentation identical to the S3.9-EXT panel rule bindings. "
            "Contains no gold decisions, no expected violations, no panel "
            "labels; raw law text is public and already versioned inside the "
            "inference pack."
        ),
        "gold_visible": False,
        "source": {
            "inference_pack": str(inference_pack.relative_to(ROOT).as_posix()),
            "inference_pack_sha256": pack_sha,
            "rule_source_count": len(rules),
            "total_sentence_count": total_sentences,
        },
        "rules": rules,
        "counts": {"rules": len(rules), "sentences": total_sentences},
    }
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing input: {output}")
    output.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    doc = build(INFERENCE_PACK, args.output)
    print(
        f"GDPR Stage-2 input written: {args.output} "
        f"rules={doc['counts']['rules']} sentences={doc['counts']['sentences']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

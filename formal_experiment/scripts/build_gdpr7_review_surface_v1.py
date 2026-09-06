# -*- coding: utf-8 -*-
"""Build the blank six-element human-review surface for the 9 GDPR rule texts (v1).

Purpose
-------
Produce a MINIMAL, decisions-NOT-prefilled human-adjudication surface
(``data/development/human_review/gdpr7_six_element_review_blank_v1.json``,
schema ``gdpr7_six_element_review_surface@1.0.0``) over the 74 sentences of the
frozen Stage-3 inference pack rule texts (GDPR article6/7/15/16/17/20/22/33/34).

The surface binds, per sentence of the existing Gold-blind Stage-2 input pack
``data/input/gdpr7_stage2_input_v1.json`` (which is NOT regenerated or
modified here):

* the sentence identity block (sample_id / sentence_idx / char_span /
  text_sha256 / approved English sentence text);
* a development-only deterministic six-element CANDIDATE produced by
  ``bpc_hybrid.stage3_extended_violations.extract_six_element_sentences``
  for the matching (rule_id, sentence_idx), labelled
  ``candidate_source: "deterministic_development_extraction_v1"`` and
  ``is_gold: false`` — a candidate is NEVER Gold and is never auto-promoted;
* an empty ``review`` object: exactly six per-field blocks
  (modality/actor/action/condition/constraint/exception) with
  ``decision: null`` and ``edited_value: null``, plus
  ``review_state: "unreviewed"`` and ``notes: null``.

Guards (all fail-closed, zero LLM/API/network):

1. the frozen inference pack path is a constant and its recorded raw-byte
   sha256 (``4182c1f6...``) is verified before any output is written;
2. the Stage-2 input pack's rule/sentence structure must exactly match a
   fresh deterministic segmentation recomputed with the SAME segmentation
   logic as ``extract_six_element_sentences`` (spaCy ``en_core_web_sm``
   ``doc.sents`` over each rule text, whitespace collapse, empty-sentence
   skip) — sentence_idx and text per sentence must match for all 9 rules;
3. the builder asserts that NO decision value anywhere is non-null and that
   no other label columns were added.

``build()`` exposes ``verify_pinned_sha`` (default True, CLI always True) only
so the segmentation guard can be unit-tested offline against a doctored
development copy; the canonical CLI run always enforces the pinned sha.
The output is deterministic JSON (stable key order), LF line endings, a single
trailing newline, and refuses to overwrite an existing file unless
``--overwrite`` is passed.
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

from bpc_hybrid.stage3_extended_violations import (  # noqa: E402
    extract_six_element_sentences,
)

INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
INPUT_PACK = ROOT / "data/input/gdpr7_stage2_input_v1.json"
OUTPUT = ROOT / "data/development/human_review/gdpr7_six_element_review_blank_v1.json"
SCHEMA_VERSION = "gdpr7_six_element_review_surface@1.0.0"
DATASET_ID = "gdpr7_six_element_review_blank_v1"

# Expected inference-pack content identity (raw-byte sha256 of the frozen file;
# fail-closed so the surface can never be silently built on a drifted source).
EXPECTED_INFERENCE_PACK_SHA256 = "4182c1f6ba8e28665c6dd14a2573b227e0c6b65c1df0041fcd1ae7dab5cf03c4"

# Expected Stage-2 input pack schema (read-only reference; never regenerated).
EXPECTED_INPUT_PACK_SCHEMA = "gdpr7_stage2_input@1.0.0"

CANDIDATE_SOURCE = "deterministic_development_extraction_v1"
FROZEN_RULE_IDS = frozenset({
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
})
REVIEW_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
CANDIDATE_FIELD_KEYS = (
    "modality", "actor", "action", "condition", "constraint", "exception",
    "constraint_kind", "exception_kind",
)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _repo_relative_posix(path: Path) -> str:
    """Repo-relative posix path for provenance; absolute posix path when the
    file lies outside the repo (e.g. a doctored copy injected by tests)."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _derive_rule_texts(inference_pack: Path) -> dict[str, str]:
    """Re-derive the 9 unique rule texts from the inference pack items
    (matching_items + violation_items); one consistent text per rule_id."""
    pack = json.loads(inference_pack.read_text(encoding="utf-8"))
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
    if set(rule_text_by_id) != FROZEN_RULE_IDS:
        raise ValueError(
            f"inference pack rule ids differ from the frozen 9: "
            f"{sorted(set(rule_text_by_id))}"
        )
    return rule_text_by_id


def _load_input_pack(input_pack: Path) -> dict[str, Any]:
    doc = json.loads(input_pack.read_text(encoding="utf-8"))
    if doc.get("schema_version") != EXPECTED_INPUT_PACK_SCHEMA:
        raise ValueError(
            f"Stage-2 input pack schema mismatch: "
            f"{doc.get('schema_version')!r} != {EXPECTED_INPUT_PACK_SCHEMA!r}"
        )
    rules: list[dict[str, Any]] = doc.get("rules")
    if not isinstance(rules, list) or len(rules) != 9:
        raise ValueError(f"Stage-2 input pack must carry 9 rule blocks, got {len(rules or [])}")
    return doc


def _verify_segmentation(input_rule: Mapping[str, Any],
                         fresh: list[dict[str, Any]]) -> None:
    """Fail-closed cross-check: every sentence of the Stage-2 input pack for
    one rule must be reproduced by the SAME deterministic segmentation logic as
    ``extract_six_element_sentences`` (spaCy doc.sents + whitespace collapse +
    empty-sentence skip)."""
    rid = input_rule["rule_id"]
    input_sents = input_rule["sentences"]
    if len(input_sents) != len(fresh):
        raise ValueError(
            f"rule {rid}: sentence count mismatch vs Stage-2 input pack "
            f"(input pack {len(input_sents)} != fresh deterministic "
            f"segmentation {len(fresh)})"
        )
    by_idx = {row["sentence_idx"]: row for row in fresh}
    for s in input_sents:
        row = by_idx.get(s["sentence_idx"])
        if row is None:
            raise ValueError(
                f"rule {rid} sentence_idx {s['sentence_idx']}: not produced by "
                f"fresh deterministic segmentation"
            )
        if row["sentence_text"] != s["approved_text_en"]:
            raise ValueError(
                f"rule {rid} sentence_idx {s['sentence_idx']}: sentence text "
                f"diverges from Stage-2 input pack\n  input pack: "
                f"{s['approved_text_en']!r}\n  fresh      : "
                f"{row['sentence_text']!r}"
            )


def _blank_review_block() -> dict[str, Any]:
    review: dict[str, Any] = {
        field: {"decision": None, "edited_value": None} for field in REVIEW_FIELDS
    }
    review["review_state"] = "unreviewed"
    review["notes"] = None
    return review


def _assert_blank(surface: Mapping[str, Any]) -> None:
    """Builder assertion: absolutely no decision value may be non-null and no
    other label columns exist."""
    found: list[str] = []
    for rule in surface["rules"]:
        rule_keys = set(rule.keys())
        allowed_rule = {"rule_id", "rule_text_sha256", "source_binding", "sentences"}
        extra = rule_keys - allowed_rule
        if extra:
            found.append(f"rule {rule['rule_id']}: extra keys {sorted(extra)}")
        for s in rule["sentences"]:
            allowed_sent = {
                "sample_id", "sentence_idx", "char_span", "text_sha256",
                "sentence_text", "candidate", "review",
            }
            extra = set(s.keys()) - allowed_sent
            if extra:
                found.append(
                    f"{s['sample_id']}: extra keys {sorted(extra)}"
                )
            review = s.get("review")
            if not isinstance(review, dict):
                found.append(f"{s['sample_id']}: missing review object")
                continue
            if set(review.keys()) != set(REVIEW_FIELDS) | {"review_state", "notes"}:
                found.append(f"{s['sample_id']}: review keys = {sorted(review)}")
            if review.get("review_state") != "unreviewed":
                found.append(f"{s['sample_id']}: review_state != unreviewed")
            if review.get("notes") is not None:
                found.append(f"{s['sample_id']}: notes must be null in blank surface")
            for field in REVIEW_FIELDS:
                entry = review.get(field)
                if not isinstance(entry, dict):
                    found.append(f"{s['sample_id']}.{field}: missing decision block")
                    continue
                if set(entry.keys()) != {"decision", "edited_value"}:
                    found.append(
                        f"{s['sample_id']}.{field}: decision block keys = {sorted(entry)}"
                    )
                if entry.get("decision") is not None:
                    found.append(f"{s['sample_id']}.{field}.decision is non-null")
                if entry.get("edited_value") is not None:
                    found.append(f"{s['sample_id']}.{field}.edited_value is non-null")
    if found:
        raise AssertionError("blank-surface invariant violated:\n  " + "\n  ".join(found))


def build(inference_pack: Path = INFERENCE_PACK,
          input_pack: Path = INPUT_PACK,
          output: Path = OUTPUT,
          overwrite: bool = False,
          verify_pinned_sha: bool = True) -> dict[str, Any]:
    """Build the blank review surface document and write it to ``output``.

    ``verify_pinned_sha=False`` skips ONLY the pinned inference-pack sha gate
    (intended for offline unit tests that inject a doctored development copy
    to exercise the segmentation guard); every structural guard still applies
    and the CLI never disables it.
    """
    import spacy  # local import: runtime dependency used only by the builder

    if output.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing surface: {output}")

    pack_sha = _sha256_file(inference_pack)
    if verify_pinned_sha and pack_sha != EXPECTED_INFERENCE_PACK_SHA256:
        raise ValueError(
            f"inference pack sha256 drift: {pack_sha} != "
            f"{EXPECTED_INFERENCE_PACK_SHA256} ({inference_pack})"
        )

    rule_text_by_id = _derive_rule_texts(inference_pack)
    input_doc = _load_input_pack(input_pack)
    input_rules = input_doc["rules"]
    if len(input_rules) != 9:
        raise ValueError("Stage-2 input pack must carry exactly 9 rule blocks")

    nlp = spacy.load("en_core_web_sm")

    rules: list[dict[str, Any]] = []
    total_sentences = 0
    for input_rule in input_rules:
        rid = input_rule["rule_id"]
        if rid not in rule_text_by_id:
            raise ValueError(f"rule {rid} missing from inference pack")
        rule_text = rule_text_by_id[rid]
        fresh = extract_six_element_sentences(rid, rule_text, nlp)
        _verify_segmentation(input_rule, fresh)

        by_idx = {row["sentence_idx"]: row for row in fresh}
        sentences: list[dict[str, Any]] = []
        for s in input_rule["sentences"]:
            cand = by_idx[s["sentence_idx"]]
            candidate: dict[str, Any] = {
                key: cand.get(key) for key in CANDIDATE_FIELD_KEYS
            }
            candidate["candidate_source"] = CANDIDATE_SOURCE
            candidate["is_gold"] = False
            sentences.append({
                "sample_id": s["sample_id"],
                "sentence_idx": s["sentence_idx"],
                "char_span": list(s["char_span"]),
                "text_sha256": s["text_sha256"],
                "sentence_text": s["approved_text_en"],
                "candidate": candidate,
                "review": _blank_review_block(),
            })
        total_sentences += len(sentences)
        rules.append({
            "rule_id": rid,
            "rule_text_sha256": _sha256_bytes(rule_text.encode("utf-8")),
            "source_binding": {
                "inference_pack": _repo_relative_posix(inference_pack),
                "inference_pack_sha256": pack_sha,
                "rule_text_char_count": len(rule_text),
            },
            "sentences": sentences,
        })

    surface = {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": DATASET_ID,
        "claim": (
            "MINIMAL human-adjudication surface for six-element Rule Records "
            "over the 9 GDPR rule texts (article6/7/15/16/17/20/22/33/34; 74 "
            "sentences) bound to the frozen Stage-3 inference pack. Each "
            "sentence carries only a development-only deterministic extraction "
            "candidate (candidate_source=deterministic_development_extraction_"
            "v1, is_gold=false); NO decision is prefilled (all review decisions "
            "are null, review_state=unreviewed). Only a human reviewer may set "
            "review decisions; agents must never infer or prefill them."
        ),
        "status": "blank_unreviewed",
        "counts": {"rules": len(rules), "sentences": total_sentences},
        "rules": rules,
    }

    _assert_blank(surface)
    if total_sentences != 74 or len(rules) != 9:
        raise AssertionError(
            f"surface must contain 9 rules / 74 sentences, got "
            f"{len(rules)} rules / {total_sentences} sentences"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    # LF line endings, single trailing newline (write bytes: no OS newline
    # translation on Windows).
    payload = (json.dumps(surface, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output.write_bytes(payload)
    return surface


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inference-pack", type=Path, default=INFERENCE_PACK)
    parser.add_argument("--input-pack", type=Path, default=INPUT_PACK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--overwrite", action="store_true",
                        help="allow replacing an existing surface file")
    args = parser.parse_args()
    doc = build(
        inference_pack=args.inference_pack,
        input_pack=args.input_pack,
        output=args.output,
        overwrite=args.overwrite,
        verify_pinned_sha=True,
    )
    print(
        f"GDPR7 six-element review surface written: {args.output} "
        f"rules={doc['counts']['rules']} sentences={doc['counts']['sentences']} "
        f"status={doc['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

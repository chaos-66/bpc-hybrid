# -*- coding: utf-8 -*-
"""Validate the blank GDPR7 six-element human-review surface (v1).

``--check`` mode verifies the surface file
``data/development/human_review/gdpr7_six_element_review_blank_v1.json``
against the frozen Stage-3 inference pack rule texts and the Gold-blind
Stage-2 input pack:

* file exists and ``schema_version`` is ``gdpr7_six_element_review_surface@1.0.0``;
* exactly the 9 frozen rule ids
  {article6, article7, article15, article16, article17, article20, article22,
  article33, article34} and 74 sentences in total;
* sample_ids are unique and equal to the Stage-2 input pack sample ids in the
  same order; every sentence_text equals the input pack approved text;
* every ``review.<field>.decision`` is null and ``review_state`` is
  ``"unreviewed"`` (blank surface invariant; nothing prefilled);
* candidate element fields (modality/actor/action/condition/constraint/
  exception + the two kinds) contain only strings or null;
* ``text_sha256`` matches the UTF-8 bytes of ``sentence_text``;
* ``rule_text_sha256`` matches the rule text re-derived from the inference
  pack items (sha256 of the UTF-8 rule text).

Exit code is 0 when every check passes and non-zero with per-check messages
otherwise.  Zero LLM/API/network; reads only the surface, the Stage-2 input
pack and the inference pack (never Gold decisions of any other file).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]

SURFACE = ROOT / "data/development/human_review/gdpr7_six_element_review_blank_v1.json"
INPUT_PACK = ROOT / "data/input/gdpr7_stage2_input_v1.json"
INFERENCE_PACK = ROOT / "data/development/human_review/stage3_gold_inference_v1.json"

SCHEMA_VERSION = "gdpr7_six_element_review_surface@1.0.0"
FROZEN_RULE_IDS = frozenset({
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
})
REVIEW_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
CANDIDATE_ELEMENT_KEYS = (
    "modality", "actor", "action", "condition", "constraint", "exception",
    "constraint_kind", "exception_kind",
)
CANDIDATE_SOURCE = "deterministic_development_extraction_v1"
EXPECTED_SENTENCE_COUNT = 74
EXPECTED_RULE_COUNT = 9


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _derive_rule_texts(inference_pack: Path) -> dict[str, str]:
    """Re-derive the 9 unique rule texts from the inference pack items."""
    pack = json.loads(inference_pack.read_text(encoding="utf-8"))
    items = pack.get("matching_items", []) + pack.get("violation_items", [])
    texts: dict[str, str] = {}
    for item in items:
        rid = item.get("rule_id")
        text = item.get("rule_text")
        if isinstance(rid, str) and isinstance(text, str) and text:
            texts.setdefault(rid, text)
    return texts


def check_surface(surface_path: Path = SURFACE,
                  input_pack_path: Path = INPUT_PACK,
                  inference_pack_path: Path = INFERENCE_PACK) -> list[str]:
    """Return a list of human-readable problems; empty list == pass."""
    problems: list[str] = []

    if not surface_path.is_file():
        return [f"surface file missing: {surface_path}"]
    if not input_pack_path.is_file():
        return [f"Stage-2 input pack missing: {input_pack_path}"]
    if not inference_pack_path.is_file():
        return [f"inference pack missing: {inference_pack_path}"]

    surface = json.loads(surface_path.read_text(encoding="utf-8"))
    input_doc = json.loads(input_pack_path.read_text(encoding="utf-8"))

    # -- schema --------------------------------------------------------------
    if surface.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"schema_version {surface.get('schema_version')!r} != {SCHEMA_VERSION!r}"
        )

    # -- rule ids ------------------------------------------------------------
    rules: Sequence[Mapping[str, Any]] = surface.get("rules")
    if not isinstance(rules, list):
        problems.append("surface.rules must be a list")
        rules = []
    rule_ids = [r.get("rule_id") for r in rules if isinstance(r, dict)]
    if len(rule_ids) != EXPECTED_RULE_COUNT or set(rule_ids) != FROZEN_RULE_IDS:
        problems.append(
            f"rule ids = {sorted(rule_ids)}; expected exactly the 9 frozen ids "
            f"{sorted(FROZEN_RULE_IDS)}"
        )

    # -- input pack reference ------------------------------------------------
    input_rules: Sequence[Mapping[str, Any]] = input_doc.get("rules")
    if not isinstance(input_rules, list):
        return problems + ["Stage-2 input pack has no rules list"]
    input_flat: list[tuple[str, str, str]] = []  # (sample_id, sentence_text, rule_id)
    input_by_sample: dict[str, dict[str, Any]] = {}
    for r in input_rules:
        for s in r.get("sentences", []):
            sid = s.get("sample_id")
            input_flat.append((sid, s.get("approved_text_en"), r.get("rule_id")))
            input_by_sample[sid] = s
    input_flat_ids = [t[0] for t in input_flat]

    # -- sentence census + ordering ------------------------------------------
    surface_flat: list[tuple[str, str]] = []  # (sample_id, sentence_text)
    for r in rules:
        if not isinstance(r, dict):
            continue
        sents = r.get("sentences")
        if not isinstance(sents, list):
            problems.append(f"rule {r.get('rule_id')}: sentences must be a list")
            continue
        for s in sents:
            surface_flat.append((s.get("sample_id"), s.get("sentence_text")))
    if len(surface_flat) != EXPECTED_SENTENCE_COUNT:
        problems.append(
            f"sentence count {len(surface_flat)} != {EXPECTED_SENTENCE_COUNT}"
        )

    surface_ids = [sid for sid, _ in surface_flat]
    if len(set(surface_ids)) != len(surface_ids):
        problems.append("surface sample_ids are not unique")
    if surface_ids != input_flat_ids:
        problems.append("surface sample_id order differs from the Stage-2 input pack")

    # -- per-sentence identity + blank invariant + hashes --------------------
    seen: set[str] = set()
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        for s in r.get("sentences", []) or []:
            if not isinstance(s, dict):
                problems.append(f"{rid}: sentence entry is not an object")
                continue
            sid = s.get("sample_id")
            if sid in seen:
                problems.append(f"duplicate sample_id {sid}")
            seen.add(sid)
            text = s.get("sentence_text")
            if not isinstance(text, str):
                problems.append(f"{sid}: sentence_text missing")
                continue
            inp = input_by_sample.get(sid)
            if inp is None:
                problems.append(f"{sid}: unknown sample_id (not in Stage-2 input pack)")
            elif inp.get("approved_text_en") != text:
                problems.append(
                    f"{sid}: sentence_text differs from Stage-2 input pack"
                )
            recorded = s.get("text_sha256")
            if recorded != _sha256_bytes(text.encode("utf-8")):
                problems.append(
                    f"{sid}: text_sha256 {recorded!r} does not match sentence_text bytes"
                )
            candidate = s.get("candidate")
            if not isinstance(candidate, dict):
                problems.append(f"{sid}: candidate missing")
            else:
                for key in CANDIDATE_ELEMENT_KEYS:
                    value = candidate.get(key)
                    if value is not None and not isinstance(value, str):
                        problems.append(
                            f"{sid}: candidate.{key} is {type(value).__name__}, "
                            f"expected string or null"
                        )
                if candidate.get("candidate_source") != CANDIDATE_SOURCE:
                    problems.append(
                        f"{sid}: candidate_source {candidate.get('candidate_source')!r}"
                    )
                if candidate.get("is_gold") is not False:
                    problems.append(f"{sid}: candidate.is_gold must be false")
            review = s.get("review")
            if not isinstance(review, dict):
                problems.append(f"{sid}: review missing")
                continue
            if review.get("review_state") != "unreviewed":
                problems.append(f"{sid}: review_state = {review.get('review_state')!r}")
            for field in REVIEW_FIELDS:
                entry = review.get(field)
                if not isinstance(entry, dict):
                    problems.append(f"{sid}: review.{field} missing")
                    continue
                if entry.get("decision") is not None:
                    problems.append(
                        f"{sid}: review.{field}.decision = "
                        f"{entry.get('decision')!r} (must be null)"
                    )
                if entry.get("edited_value") is not None:
                    problems.append(
                        f"{sid}: review.{field}.edited_value = "
                        f"{entry.get('edited_value')!r} (must be null)"
                    )

    # -- per-rule rule_text_sha256 vs inference pack -------------------------
    rule_texts = _derive_rule_texts(inference_pack_path)
    for r in rules:
        if not isinstance(r, dict):
            continue
        rid = r.get("rule_id")
        text = rule_texts.get(rid)
        if text is None:
            problems.append(f"rule {rid}: not derivable from the inference pack items")
            continue
        expected_hash = _sha256_bytes(text.encode("utf-8"))
        if r.get("rule_text_sha256") != expected_hash:
            problems.append(
                f"rule {rid}: rule_text_sha256 {r.get('rule_text_sha256')!r} "
                f"!= sha256(rule_text) {expected_hash}"
            )

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", type=Path, default=SURFACE)
    parser.add_argument("--input-pack", type=Path, default=INPUT_PACK)
    parser.add_argument("--inference-pack", type=Path, default=INFERENCE_PACK)
    parser.add_argument("--check", action="store_true", required=True,
                        help="run the checks; exit 0 on pass, non-zero on fail")
    args = parser.parse_args()

    problems = check_surface(args.surface, args.input_pack, args.inference_pack)
    if problems:
        print(f"GDPR7 six-element review surface validation FAILED ({len(problems)}):")
        for msg in problems:
            print(f"  - {msg}")
        return 1

    surface = json.loads(args.surface.read_text(encoding="utf-8"))
    counts = surface.get("counts", {})
    print(
        f"GDPR7 six-element review surface validation PASSED: "
        f"rules={counts.get('rules', len(surface.get('rules', [])))} "
        f"sentences={counts.get('sentences')} status={surface.get('status')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

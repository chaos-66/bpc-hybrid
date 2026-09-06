# -*- coding: utf-8 -*-
"""Focused tests for the blank GDPR7 six-element human-review surface (v1).

Covers:
- (a) the committed surface file exists and passes every validator check
  (``validate_gdpr7_review_surface_v1.check_surface``);
- (b) the builder refuses to overwrite an existing surface file;
- (c) the builder fails (ValueError) when the input pack's sentence
  segmentation diverges from a doctored rule text (tampered development copy
  of the inference pack; pinned-sha gate bypassed only so the segmentation
  guard itself is exercised);
- (d) no decision field (or edited_value) is non-null anywhere and no stray
  label columns exist;
- determinism: a fresh offline rebuild byte-matches the committed surface.
"""

from __future__ import annotations

import copy
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

from build_gdpr7_review_surface_v1 import (  # noqa: E402
    EXPECTED_INFERENCE_PACK_SHA256,
    INFERENCE_PACK,
    INPUT_PACK,
    OUTPUT,
    SCHEMA_VERSION,
    build,
)
from validate_gdpr7_review_surface_v1 import (  # noqa: E402
    check_surface,
)

REVIEW_FIELDS = ("modality", "actor", "action", "condition", "constraint", "exception")
FROZEN_RULE_IDS = {
    "article6", "article7", "article15", "article16", "article17",
    "article20", "article22", "article33", "article34",
}


@pytest.fixture(scope="module")
def surface_doc() -> dict:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# (a) committed surface exists and passes the validator
# ---------------------------------------------------------------------------
def test_surface_file_exists_and_passes_validator(surface_doc: dict) -> None:
    assert OUTPUT.is_file()
    assert surface_doc["schema_version"] == SCHEMA_VERSION
    assert surface_doc["status"] == "blank_unreviewed"
    assert surface_doc["counts"] == {"rules": 9, "sentences": 74}
    problems = check_surface(OUTPUT, INPUT_PACK, INFERENCE_PACK)
    assert problems == [], f"validator problems: {problems}"


def test_rule_ids_and_sentence_census(surface_doc: dict) -> None:
    rules = surface_doc["rules"]
    assert len(rules) == 9
    assert {r["rule_id"] for r in rules} == FROZEN_RULE_IDS
    total = sum(len(r["sentences"]) for r in rules)
    assert total == 74


# ---------------------------------------------------------------------------
# (b) builder refuses to overwrite
# ---------------------------------------------------------------------------
def test_builder_refuses_overwrite(tmp_path: Path) -> None:
    out = tmp_path / "surface.json"
    out.write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        build(inference_pack=INFERENCE_PACK, input_pack=INPUT_PACK,
              output=out, overwrite=False)


# ---------------------------------------------------------------------------
# (c) builder fails when segmentation diverges from a doctored rule text
# ---------------------------------------------------------------------------
def test_builder_rejects_doctored_rule_text_segmentation(tmp_path: Path) -> None:
    doc = json.loads(INFERENCE_PACK.read_text(encoding="utf-8"))
    tampered = copy.deepcopy(doc)
    doctored = (
        "This is a doctored development rule text for article16. "
        "Its sentences must not match the frozen sentence segmentation."
    )
    altered = 0
    for key in ("matching_items", "violation_items"):
        for item in tampered.get(key, []):
            if item["rule_id"] == "article16":
                item["rule_text"] = doctored
                altered += 1
    assert altered >= 1
    src = tmp_path / "tampered_pack.json"
    src.write_text(json.dumps(tampered, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out.json"
    # Pinned-sha gate bypassed ONLY here so the doctored copy can reach the
    # segmentation guard (the CLI never disables the pin).
    with pytest.raises(ValueError) as exc_info:
        build(inference_pack=src, input_pack=INPUT_PACK, output=out,
              overwrite=False, verify_pinned_sha=False)
    message = str(exc_info.value)
    assert "article16" in message and (
        "diverges" in message or "sentence count" in message
    ), message


# ---------------------------------------------------------------------------
# (d) absolutely no decision value non-null; no stray label columns
# ---------------------------------------------------------------------------
def test_no_decision_field_non_null_anywhere(surface_doc: dict) -> None:
    violations: list[str] = []
    for rule in surface_doc["rules"]:
        if set(rule.keys()) != {
            "rule_id", "rule_text_sha256", "source_binding", "sentences",
        }:
            violations.append(f"rule {rule['rule_id']}: stray keys {sorted(rule)}")
        for s in rule["sentences"]:
            if set(s.keys()) != {
                "sample_id", "sentence_idx", "char_span", "text_sha256",
                "sentence_text", "candidate", "review",
            }:
                violations.append(f"{s['sample_id']}: stray keys {sorted(s)}")
            review = s["review"]
            if set(review.keys()) != set(REVIEW_FIELDS) | {"review_state", "notes"}:
                violations.append(f"{s['sample_id']}: review keys {sorted(review)}")
            assert review["review_state"] == "unreviewed"
            for field in REVIEW_FIELDS:
                entry = review[field]
                if entry["decision"] is not None:
                    violations.append(f"{s['sample_id']}.{field}.decision non-null")
                if entry["edited_value"] is not None:
                    violations.append(f"{s['sample_id']}.{field}.edited_value non-null")
    assert violations == []


# ---------------------------------------------------------------------------
# determinism: offline rebuild byte-matches the committed surface
# ---------------------------------------------------------------------------
def test_deterministic_rebuild_matches_committed_surface(tmp_path: Path) -> None:
    out = tmp_path / "surface.json"
    build(inference_pack=INFERENCE_PACK, input_pack=INPUT_PACK, output=out,
          overwrite=False)
    assert out.read_bytes() == OUTPUT.read_bytes()

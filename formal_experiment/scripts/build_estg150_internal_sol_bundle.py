#!/usr/bin/env python3
"""Validate and merge the internal GPT-5.6 Sol EStG-150 candidates.

This command is offline.  It never calls an API and never reads or writes
Layer E.  It combines the validated three-record pilot with contiguous batch
files produced by the authorized internal Codex subagents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "codex_internal_gpt56sol_full150_v1"
RUN_DIR = ROOT / "data" / "development" / "estg" / "llm_candidate_runs" / RUN_ID
PILOT_PATH = (
    ROOT
    / "data"
    / "development"
    / "estg"
    / "llm_candidate_runs"
    / "codex_internal_gpt56sol_pilot3_v1"
    / "pass_b_candidates.json"
)
OUTPUT_PATH = RUN_DIR / "ai_review_candidates.json"
RUN_CONFIG_PATH = RUN_DIR / "run_config.json"
MANIFEST_PATH = RUN_DIR / "manifest.json"
SCHEMA_PATH = ROOT / "configs" / "schemas" / "estg150_ai_review_model_output.schema.json"
PROMPT_PATH = ROOT / "prompts" / "estg150_ai_review" / "internal_sol_full_extract_v1.md"
BATCH_RE = re.compile(r"batch_(\d{3})_(\d{3})\.json")
NORMATIVE_CUE_RE = re.compile(
    r"\b(?:shall(?:\s+not)?|must(?:\s+not)?|may(?:\s+not)?|"
    r"is\s+required\s+to|are\s+required\s+to|is\s+deemed|are\s+deemed|means)\b",
    re.IGNORECASE,
)

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_estg150_ai_review import (  # noqa: E402
    EXPECTED_MEMBERSHIP_SHA256,
    LAYER_A_PATH,
    LAYER_B_PATH,
    LAYER_C_PATH,
    load_fixed_inputs,
    load_json,
    sha256_path,
    validate_candidate,
)


def _write_new_or_same(path: Path, value: dict) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise SystemExit(f"refusing to overwrite drifted artifact: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _load_batches() -> tuple[dict[int, dict], list[dict]]:
    indexed: dict[int, dict] = {}
    sources: list[dict] = []
    for path in sorted(RUN_DIR.glob("batch_*.json")):
        match = BATCH_RE.fullmatch(path.name)
        if not match:
            continue
        start = int(match.group(1))
        inclusive_end = int(match.group(2))
        batch = load_json(path)
        end = batch.get("end_index_exclusive")
        if batch.get("start_index") != start or end != inclusive_end + 1:
            raise SystemExit(f"batch metadata/name mismatch: {path.name}")
        records = batch.get("records")
        if not isinstance(records, list) or len(records) != end - start:
            raise SystemExit(f"batch record count mismatch: {path.name}")
        for offset, candidate in enumerate(records):
            index = start + offset
            if index in indexed:
                raise SystemExit(f"duplicate candidate index {index}")
            indexed[index] = candidate
        sources.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256_path(path),
            "start_index": start,
            "end_index_exclusive": end,
        })
    return indexed, sources


def _uncovered_normative_cues(candidate: dict) -> list[str]:
    """Catch obvious clause omissions without creating another review stage."""
    text = candidate["translation"]["proposed_text_en"]
    bounds = [
        (clause["clause_span"]["start"], clause["clause_span"]["end"])
        for clause in candidate["clauses"]
    ]
    uncovered = [
        match.group(0)
        for match in NORMATIVE_CUE_RE.finditer(text)
        if not any(start <= match.start() and match.end() <= end for start, end in bounds)
    ]
    return uncovered


def build_bundle() -> tuple[dict, dict, dict]:
    samples = load_fixed_inputs()
    schema = load_json(SCHEMA_PATH)
    pilot = load_json(PILOT_PATH)
    pilot_records = pilot.get("records")
    if not isinstance(pilot_records, list) or len(pilot_records) != 3:
        raise SystemExit("the locked internal Sol pilot must contain exactly 3 records")

    indexed: dict[int, dict] = {index: value for index, value in enumerate(pilot_records)}
    batches, batch_sources = _load_batches()
    for index, candidate in batches.items():
        if index in indexed:
            raise SystemExit(f"batch overlaps the locked pilot at index {index}")
        indexed[index] = candidate
    missing = [index for index in range(150) if index not in indexed]
    extras = sorted(set(indexed) - set(range(150)))
    if missing or extras:
        raise SystemExit(
            f"candidate coverage incomplete: missing={missing[:20]}"
            f"{'...' if len(missing) > 20 else ''}, extras={extras}"
        )

    records: list[dict] = []
    coverage_errors: list[str] = []
    for index, sample in enumerate(samples):
        candidate = indexed[index]
        if candidate.get("sample_id") != sample["sample_id"]:
            raise SystemExit(
                f"index {index} sample mismatch: expected {sample['sample_id']}, "
                f"got {candidate.get('sample_id')}"
            )
        validate_candidate(
            candidate,
            expected_sample_id=sample["sample_id"],
            frozen_candidate_text_en=sample["candidate_text_en"],
            schema=schema,
        )
        uncovered = _uncovered_normative_cues(candidate)
        if uncovered:
            coverage_errors.append(
                f"{candidate['sample_id']}: normative cue(s) outside every clause: {uncovered}"
            )
        records.append(candidate)
    if coverage_errors:
        raise SystemExit("normative-cue coverage failed:\n" + "\n".join(coverage_errors))

    bundle = {
        "schema_version": "estg150_internal_sol_candidates@1.0.0",
        "run_id": RUN_ID,
        "model": "gpt-5.6-sol",
        "output_class": "development_ai_candidate_user_review_required",
        "membership_payload_sha256": EXPECTED_MEMBERSHIP_SHA256,
        "record_count": len(records),
        "records": records,
    }
    run_config = {
        "schema_version": "estg150_internal_sol_run@1.0.0",
        "run_id": RUN_ID,
        "model": "gpt-5.6-sol",
        "reasoning_effort": "high",
        "execution_surface": "Codex internal subagents",
        "agent_count": 3,
        "generation_design": {
            "indices_0_2": "locked two-pass internal Sol pilot (Pass A then independent Pass B)",
            "indices_3_149": (
                "one internal Sol extraction per record; independent A/B reading first, "
                "then fallible Layer-C self-check"
            ),
            "root_validation": (
                "strict schema, sample order, exact spans, relation IDs, and obvious "
                "normative-cue clause coverage"
            ),
        },
        "external_api_called": False,
        "external_cost": None,
        "output_class": "development_ai_candidate_user_review_required",
        "membership_payload_sha256": EXPECTED_MEMBERSHIP_SHA256,
        "layer_a_sha256": sha256_path(LAYER_A_PATH),
        "layer_b_sha256": sha256_path(LAYER_B_PATH),
        "layer_c_sha256": sha256_path(LAYER_C_PATH),
        "schema_sha256": sha256_path(SCHEMA_PATH),
        "prompt_contract": PROMPT_PATH.relative_to(ROOT).as_posix(),
        "prompt_contract_sha256": sha256_path(PROMPT_PATH),
        "pilot": {
            "path": PILOT_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_path(PILOT_PATH),
            "indices": [0, 3],
        },
        "batches": batch_sources,
        "layer_d_used": False,
        "layer_e_read": False,
        "layer_e_write": False,
        "human_gold_claim": False,
    }
    bundle_bytes = (json.dumps(bundle, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    translation_counts = Counter(
        candidate["translation"]["decision"] for candidate in records
    )
    context_counts = Counter(candidate["context_sufficiency"] for candidate in records)
    confidence_counts = Counter(candidate["confidence"] for candidate in records)
    manifest = {
        "schema_version": "estg150_internal_sol_manifest@1.0.0",
        "run_id": RUN_ID,
        "status": "succeeded",
        "candidate_count": len(records),
        "validated_candidate_count": len(records),
        "candidate_bundle_sha256": hashlib.sha256(bundle_bytes).hexdigest(),
        "total_clause_count": sum(len(candidate["clauses"]) for candidate in records),
        "translation_decision_counts": dict(sorted(translation_counts.items())),
        "context_sufficiency_counts": dict(sorted(context_counts.items())),
        "confidence_counts": dict(sorted(confidence_counts.items())),
        "external_api_called": False,
        "layer_e_changed": False,
    }
    return bundle, run_config, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the new immutable aggregate, run config, and summary",
    )
    args = parser.parse_args()
    bundle, run_config, manifest = build_bundle()
    if args.write:
        _write_new_or_same(OUTPUT_PATH, bundle)
        manifest["candidate_bundle_sha256"] = sha256_path(OUTPUT_PATH)
        _write_new_or_same(RUN_CONFIG_PATH, run_config)
        _write_new_or_same(MANIFEST_PATH, manifest)
        print(f"written: {OUTPUT_PATH}")
    print(f"validated: {manifest['validated_candidate_count']}/150")
    print("external API: not called; Layer E: not read or written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

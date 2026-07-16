"""Build the canonical EStG-150 review file from the prepared v1 input.

Run from formal_experiment/ as:
    python scripts/build_canonical_review.py --dry-run
    python scripts/build_canonical_review.py --write

Builds data/development/human_review/estg_150_canonical_review_v1.json
with exactly 150 records, all in needs_review state, clauses empty,
approved_text_en empty. Old auto-Gold files are listed in
old_gold_sources only (pre_filled MUST be false).

This script is the only place that creates the canonical review file. It
must NOT be re-run after the user starts editing, or it will silently
clobber the user's work; a separate `--force` flag would be needed and is
intentionally not present.
"""
import argparse
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "development"
ESTG = BASE / "estg"
SOURCE = ESTG / "estg_selected_150_de.jsonl"
SOURCE_EN = ESTG / "estg_selected_150_en_llm_translated.jsonl"
PREPARED = ESTG / "estg_150_prepared_v1.jsonl"
HASHES = ESTG / "estg_150_membership_hashes.json"
DEST = BASE / "human_review" / "estg_150_canonical_review_v1.json"


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.write:
        args.dry_run = True

    # Read the prepared file (which already has raw_de, cleaned_de, candidate_en)
    # and reuse its hashes.
    prepared = []
    with PREPARED.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                prepared.append(json.loads(line))
    assert len(prepared) == 150, f"expected 150 prepared, got {len(prepared)}"

    # Read membership hashes
    hashes = json.loads(HASHES.read_text(encoding="utf-8"))
    membership_payload_sha = hashes["selected_membership"]["membership_payload_sha256"]
    sorted_ids = hashes["selected_membership"]["sorted_legacy_record_ids"]
    assert len(sorted_ids) == 150
    assert sorted_ids == sorted(r["legacy_record_id"] for r in prepared), (
        "membership identity broken between hashes and prepared"
    )

    # Build the dataset record
    dataset = {
        "name": "independently_reconstructed_estg_150",
        "version": "v1",
        "membership_payload_sha256": membership_payload_sha,
        "membership_count": 150,
        "language_pair": {"source": "de", "translation": "en"},
        "source_candidate_corpus": "data/development/estg/estg_sentences_de.jsonl",
        "source_selected": "data/development/estg/estg_selected_150_de.jsonl",
        "source_translation": "data/development/estg/estg_selected_150_en_llm_translated.jsonl",
        "frozen_v1_files": [
            "data/development/estg/estg_selected_150_de.jsonl",
            "data/development/estg/estg_selected_150_en_llm_translated.jsonl",
            "data/development/estg/estg_150_membership_hashes.json",
        ],
        "provenance_notes": (
            "Independently reconstructed EStG-150 benchmark, not Sun et al. "
            "(2024)'s original 150-sentence phrase Gold. The 150 legacy "
            "record_ids are taken once from estg_selected_150_de.jsonl and "
            "are not re-sampled, supplemented, or split. Old auto-Gold files "
            "are listed in old_gold_sources for provenance only; they are "
            "NEVER pre-filled into this file (anchoring protection)."
        ),
    }

    # Build the records
    records = []
    for r in prepared:
        legacy_id = r["legacy_record_id"]
        sample_id = f"estg_{legacy_id:06d}"
        rec = {
            "sample_id": sample_id,
            "legacy_record_id": legacy_id,
            "raw_text_de": r["raw_text_de"],
            "raw_text_de_sha256": r["raw_text_de_sha256"],
            "cleaned_text_de_candidate": r["cleaned_text_de_candidate"],
            "cleaned_text_de_candidate_sha256": r[
                "cleaned_text_de_candidate_sha256"
            ],
            "cleaning_flags": r.get("cleaning_flags", []),
            "source_boundary_issue": bool(r.get("needs_adjudication", False)),
            "official_text_match": None,  # filled by separate offline tool
            "candidate_text_en": r["candidate_text_en"],
            "candidate_text_en_sha256": r.get("candidate_text_en_sha256"),
            "approved_text_en": None,
            "approved_text_en_sha256": None,
            "text_review": {
                "status": "needs_review",
                "reviewer": None,
                "reviewed_at": None,
                "notes": None,
            },
            "annotation_review": {
                "status": "needs_review",
                "reviewer": None,
                "reviewed_at": None,
                "confidence": None,
                "notes": None,
            },
            "clauses": [],
            "old_gold_sources": [
                {
                    "path": "data/development/estg/estg_gold_150_llm_draft.jsonl",
                    "version_label": "llm_draft",
                    "extraction_kind": "pre_canonical_schema_auto_annotation",
                    "pre_filled": False,
                },
                {
                    "path": "data/development/estg/estg_gold_150_v1_backup.jsonl",
                    "version_label": "v1_backup",
                    "extraction_kind": "pre_canonical_schema_auto_annotation",
                    "pre_filled": False,
                },
                {
                    "path": "data/development/estg/estg_gold_150_v2_distribution_targeted.jsonl",
                    "version_label": "v2_distribution_targeted",
                    "extraction_kind": "pre_canonical_schema_auto_annotation",
                    "pre_filled": False,
                },
            ],
        }
        records.append(rec)

    out = {
        "schema_version": "estg_150_canonical_review@1.0.0",
        "dataset": dataset,
        "records": records,
    }

    summary = {
        "destination": str(DEST.relative_to(DEST.parents[2])),
        "records": len(records),
        "membership_payload_sha256": membership_payload_sha,
        "n_text_needs_review": sum(
            1 for r in records if r["text_review"]["status"] == "needs_review"
        ),
        "n_annotation_needs_review": sum(
            1 for r in records
            if r["annotation_review"]["status"] == "needs_review"
        ),
        "n_clauses_total": sum(len(r["clauses"]) for r in records),
        "n_approved_en_filled": sum(
            1 for r in records if r["approved_text_en"]
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.write:
        DEST.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {DEST}")


if __name__ == "__main__":
    main()

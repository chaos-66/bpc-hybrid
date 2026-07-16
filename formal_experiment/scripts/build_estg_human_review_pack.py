"""Build the blank EStG-150 human-review pack without network or LLM calls.

This script copies source and candidate translation text only. It never creates
semantic labels, spans, clauses, reviewer names, or approval decisions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/development/estg/estg_selected_150_en_llm_translated.jsonl"
DEFAULT_OUTPUT = ROOT / "data/development/human_review/estg150_review_pack_v1.jsonl"
SELECTION_POLICY = (
    "Existing marker-enriched EStG-150 reconstruction retained for controlled "
    "comparison; not Sun et al.'s original sample and not a random sample."
)


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def build_record(row: dict, selection_rank: int) -> dict:
    record_id = int(row["id"])
    return {
        "schema_version": "1.0.0",
        "sample_id": f"estg_{record_id:06d}",
        "source": {
            "record_id": record_id,
            "source_name": row.get("source", "EStG 1988"),
            "source_text_de_ocr": row["text_de"],
            "candidate_text_en": row["text_en"],
            "selection_rank": selection_rank,
            "selection_policy": SELECTION_POLICY,
            "provenance_path": "references/datasets/estg_1988.pdf",
        },
        "text_review": {
            "status": "needs_review",
            "reviewer": None,
            "reviewed_at": None,
            "corrected_text_de": None,
            "approved_text_en": None,
            "notes": None,
        },
        "clauses": [],
        "annotation_review": {
            "status": "needs_review",
            "reviewer": None,
            "reviewed_at": None,
            "confidence": None,
            "no_normative_clause_reason": None,
            "notes": None,
        },
        "do_not_auto_score": True,
    }


def build_pack(source: Path, output: Path, *, overwrite: bool = False) -> int:
    if output.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing review pack: {output}")
    rows = load_jsonl(source)
    if len(rows) != 150:
        raise ValueError(f"Expected 150 source records, found {len(rows)}")
    ids = [int(row["id"]) for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate EStG source IDs")
    records = [build_record(row, rank) for rank, row in enumerate(rows, 1)]
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    try:
        count = build_pack(args.source, args.output, overwrite=args.overwrite)
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(f"Created blank human-review pack: {args.output} ({count} records)")
    print("No Gold labels, spans, or review decisions were generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

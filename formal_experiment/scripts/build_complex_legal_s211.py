"""Build the deterministic S2.11 GDPR-50 input and blank Gold template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.complex_legal import (  # noqa: E402
    ARTICLE_MAX,
    ARTICLE_MIN,
    DATASET_ID,
    SELECTION_SEED,
    SOURCE_ID,
    TARGET_COUNT,
    build_blank_review,
    membership_payload,
    membership_sha256,
    parse_article_units,
    select_coverage_seeded50,
    sha256_file,
)


SOURCE = (
    ROOT
    / "data/development/complex_legal/gdpr_2016_679_oj_en/source/DOC_2_body.xml"
)
DATASET = (
    ROOT
    / "data/development/complex_legal/gdpr_2016_679_oj_en/"
    "gdpr_articles_5_50_seeded50_v1.jsonl"
)
MEMBERSHIP = DATASET.with_suffix(".membership.json")
REVIEW = (
    ROOT
    / "data/development/complex_legal/gdpr_2016_679_oj_en/"
    "gdpr_articles_5_50_seeded50_human_gold_v1.json"
)


def _write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--dataset-out", type=Path, default=DATASET)
    parser.add_argument("--membership-out", type=Path, default=MEMBERSHIP)
    parser.add_argument("--review-out", type=Path, default=REVIEW)
    args = parser.parse_args()

    units = parse_article_units(args.source.resolve())
    records = select_coverage_seeded50(units)
    digest = membership_sha256(records)
    dataset_text = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in records
    )
    membership = {
        "schema_version": "complex_legal_membership@1.0.0",
        "dataset_id": DATASET_ID,
        "source_id": SOURCE_ID,
        "source_sha256": sha256_file(args.source.resolve()),
        "selection_seed": SELECTION_SEED,
        "selection_algorithm": (
            "minimum SHA-256 rank per Article 5-50, then four minimum-ranked "
            "remaining units; final source order"
        ),
        "article_range": [ARTICLE_MIN, ARTICLE_MAX],
        "target_count": TARGET_COUNT,
        "source_unit_count": len(units),
        "membership_sha256": digest,
        "membership_payload": membership_payload(records),
        "sample_ids": [record["sample_id"] for record in records],
        "article_coverage": sorted({record["article"] for record in records}),
        "selection_role_counts": {
            "article_coverage": sum(
                record["selection_role"] == "article_coverage" for record in records
            ),
            "coverage_supplement": sum(
                record["selection_role"] == "coverage_supplement" for record in records
            ),
        },
        "method_outputs_used": False,
        "evaluation_results_used": False,
        "legacy_gdpr50_used": False,
    }
    review = build_blank_review(records)

    _write_new(args.dataset_out.resolve(), dataset_text)
    _write_new(
        args.membership_out.resolve(),
        json.dumps(membership, ensure_ascii=False, indent=2) + "\n",
    )
    _write_new(
        args.review_out.resolve(),
        json.dumps(review, ensure_ascii=False, indent=2) + "\n",
    )
    print(
        json.dumps(
            {
                "dataset_id": DATASET_ID,
                "records": len(records),
                "source_units": len(units),
                "membership_sha256": digest,
                "dataset": str(args.dataset_out.resolve()),
                "membership": str(args.membership_out.resolve()),
                "review": str(args.review_out.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

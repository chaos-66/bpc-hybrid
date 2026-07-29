"""Validate the S2.11 complex-legal human-Gold review file offline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.complex_legal import validate_human_gold_review  # noqa: E402


BASE = ROOT / "data/development/complex_legal/gdpr_2016_679_oj_en"
DEFAULT_DATASET = BASE / "gdpr_articles_5_50_seeded50_v1.jsonl"
DEFAULT_REVIEW = BASE / "gdpr_articles_5_50_seeded50_human_gold_v1.json"
DEFAULT_SCHEMA = ROOT / "configs/schemas/complex_legal_human_gold.schema.json"


def _load_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"JSONL row must be an object at {path}:{number}")
        records.append(value)
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--require-freeze-ready", action="store_true")
    args = parser.parse_args()
    dataset = _load_jsonl(args.dataset.resolve())
    review = json.loads(args.review.resolve().read_text(encoding="utf-8"))
    report = validate_human_gold_review(review, dataset, args.schema.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["format_valid"]:
        return 1
    if args.require_freeze_ready and not report["freeze_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

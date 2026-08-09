# -*- coding: utf-8 -*-
"""Build the Gold-blind Stage 3 development inference pack.

Deterministically derives the inference pack from the frozen S3.2/S3.3 blank
pack: matching items keep item_id/process_id/rule_id/rule_text; violation
items additionally carry an explicit ``check_type`` (routing metadata of the
frozen test point, taken from the blank pack's test-point definition at build
time). The generated pack NEVER contains decision_*, candidate_*, evidence,
or review_state fields, and runners must consume ONLY this pack.

The output is sorted by item_id, so shuffling the blank pack's item order
cannot change the generated pack (covered by a negative test).

Usage:
    python scripts/build_stage3_gold_inference.py [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BLANK_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_blank_v1.json"
DEFAULT_OUTPUT = ROOT / "data" / "development" / "human_review" / "stage3_gold_inference_v1.json"

FORBIDDEN = {
    "decision_relevant", "decision_violation_type", "decision_evidence",
    "candidate_relevant", "candidate_violation_type", "candidate_evidence",
    "candidate_location", "review_state",
}


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} root must be an object")
    return value


def build_inference_pack(blank: dict[str, Any]) -> dict[str, Any]:
    matching_items = []
    for item in sorted(blank.get("matching_items", []), key=lambda i: i["item_id"]):
        matching_items.append({
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "rule_text": item["rule_text"],
        })
    violation_items = []
    for item in sorted(blank.get("violation_items", []), key=lambda i: i["item_id"]):
        check_type = item.get("candidate_violation_type")
        if check_type not in ("missing_action", "incorrect_actor", "out_of_order"):
            raise RuntimeError(f"blank pack violation item {item['item_id']} has no legal check_type")
        violation_items.append({
            "item_id": item["item_id"],
            "process_id": item["process_id"],
            "rule_id": item["rule_id"],
            "rule_text": item["rule_text"],
            "check_type": check_type,
        })
    pack = {
        "schema_version": "stage3_inference@1.0.0",
        "dataset_id": "stage3_gold_inference_v1",
        "matching_items": matching_items,
        "violation_items": violation_items,
    }
    return pack


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    blank = _load_json(BLANK_PACK, "blank pack")
    pack = build_inference_pack(blank)
    payload = json.dumps(pack, ensure_ascii=False, indent=2) + "\n"
    if not args.write:
        print(f"inference pack: {len(pack['matching_items'])} matching, "
              f"{len(pack['violation_items'])} violation items (dry-run)")
        return 0
    output = args.output.resolve()
    if output.exists():
        print(f"refusing to overwrite: {output}", file=sys.stderr)
        return 2
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

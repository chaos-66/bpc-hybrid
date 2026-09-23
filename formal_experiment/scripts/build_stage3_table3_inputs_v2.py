# -*- coding: utf-8 -*-
"""Build sanitized Stage-3 Table 3 v2 inference inputs.

The repaired runner must not receive pair role or any benchmark target label.
This builder projects the existing gold-blind inference view to the five
current-item keys and extracts the frozen regulation text into a separate
view that contains no check type.  It does not create or modify Gold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_inference_view_v1.json"
)
SOURCE_INFERENCE_PACK = (
    ROOT / "data/development/human_review/stage3_gold_inference_v1.json"
)
OUT_VIEW = (
    ROOT / "data/development/stage3_synth"
    / "stage3_paired_benchmark_inference_view_v2.json"
)
OUT_TEXT = (
    ROOT / "data/development/stage3_synth"
    / "stage3_regulation_text_view_v2.json"
)
ALLOWED_KEYS = ("item_id", "pair_id", "bpmn_path", "rule_id", "process_id")


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(*, overwrite: bool = False) -> dict[str, Any]:
    if (OUT_VIEW.exists() or OUT_TEXT.exists()) and not overwrite:
        raise SystemExit(
            f"refusing to overwrite existing v2 inputs: {OUT_VIEW} {OUT_TEXT}"
        )
    source_view = _load(SOURCE_VIEW)
    items: list[dict[str, Any]] = []
    for raw in source_view.get("items") or []:
        item = {key: raw.get(key) for key in ALLOWED_KEYS}
        if not all(item.get(key) for key in ALLOWED_KEYS):
            raise ValueError(f"incomplete source item: {raw!r}")
        items.append(item)
    view = {
        "schema_version": "stage3_paired_benchmark_inference_view_v2@1.0.0",
        "view_id": "stage3_paired_benchmark_inference_view_v2",
        "benchmark_id": source_view.get("benchmark_id"),
        "source_view": SOURCE_VIEW.relative_to(ROOT).as_posix(),
        "source_view_sha256": _sha256(SOURCE_VIEW),
        "allowed_item_keys": list(ALLOWED_KEYS),
        "removed_fields": ["role", "target_violation_type",
                           "gold_violation_type", "grounding",
                           "structural_observation", "bpmn_sha256"],
        "safety": {
            "pair_role_present": False,
            "gold_labels_present": False,
            "mutation_answers_present": False,
        },
        "items": items,
    }
    _write(OUT_VIEW, view)

    current_pack = _load(SOURCE_INFERENCE_PACK)
    rule_texts: dict[str, str] = {}
    for section in ("matching_items", "violation_items"):
        for item in current_pack.get(section) or []:
            rule_id = str(item.get("rule_id") or "")
            rule_text = str(item.get("rule_text") or "")
            if not rule_id or not rule_text:
                raise ValueError(f"missing rule text in {section}: {item!r}")
            previous = rule_texts.get(rule_id)
            if previous is not None and previous != rule_text:
                raise ValueError(
                    f"conflicting rule_text for {rule_id} in {section}")
            rule_texts[rule_id] = rule_text
    text_view = {
        "schema_version": "stage3_regulation_text_view_v2@1.0.0",
        "source_inference_pack": SOURCE_INFERENCE_PACK.relative_to(
            ROOT).as_posix(),
        "source_inference_pack_sha256": _sha256(SOURCE_INFERENCE_PACK),
        "note": (
            "Only rule_id and frozen regulation rule_text are retained. "
            "check_type and all item labels are removed."
        ),
        "rule_texts": [
            {
                "rule_id": rule_id,
                "rule_text": rule_texts[rule_id],
                "rule_text_sha256": hashlib.sha256(
                    rule_texts[rule_id].encode("utf-8")).hexdigest(),
            }
            for rule_id in sorted(rule_texts)
        ],
    }
    _write(OUT_TEXT, text_view)
    return {
        "view": OUT_VIEW.relative_to(ROOT).as_posix(),
        "view_sha256": _sha256(OUT_VIEW),
        "regulation_text": OUT_TEXT.relative_to(ROOT).as_posix(),
        "regulation_text_sha256": _sha256(OUT_TEXT),
        "items": len(items),
        "rules": len(rule_texts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true",
                        help="replace the v2 sanitized inputs")
    args = parser.parse_args()
    report = build(overwrite=args.overwrite)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
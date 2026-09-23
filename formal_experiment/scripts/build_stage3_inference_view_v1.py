# -*- coding: utf-8 -*-
"""Build a gold-blind inference view of the paired benchmark.

The view contains only the fields the Ours inference path is allowed to see.
Mutation manifests, grounding blocks, target ids, expected lanes, order pairs
and gold labels are removed *before* the Ours runner starts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_v1.json"
OUT = ROOT / "data/development/stage3_synth/stage3_paired_benchmark_inference_view_v1.json"
ALLOWED_KEYS = ("item_id", "pair_id", "role", "bpmn_path", "rule_id", "process_id")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict[str, Any]:
    source = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    items = []
    for raw in source.get("items") or []:
        items.append({key: raw.get(key) for key in ALLOWED_KEYS})
    output = {
        "schema_version": "stage3_paired_benchmark_inference_view@1.0.0",
        "view_id": "stage3_paired_benchmark_inference_view_v1",
        "benchmark_id": source.get("benchmark_id"),
        "source_benchmark": str(BENCHMARK.relative_to(ROOT)).replace("\\", "/"),
        "source_benchmark_sha256": _sha256(BENCHMARK),
        "allowed_item_keys": list(ALLOWED_KEYS),
        "removed_fields": [
            "grounding", "target_violation_type", "gold_violation_type",
            "structural_observation", "bpmn_sha256",
        ],
        "safety": {
            "mutation_answers_present": False,
            "binding_gold_present": False,
            "gold_labels_present": False,
        },
        "items": items,
    }
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2,
                              sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    output = build()
    print(json.dumps({"output": str(OUT), "items": len(output["items"]),
                      "source_benchmark_sha256": output["source_benchmark_sha256"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""DEV_ONLY descriptive comparison of all five Stage 3 development methods
(Winter corrected, Winter prototype-literal, Sun, BM25, TF-IDF/SVD) on the
SAME 58 item IDs with the SAME common evaluator and the SAME Gold.

Descriptive only - no superiority claim from development numbers.

Usage:
    python scripts/compare_stage3_methods_dev.py --out <comparison.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"

RUNS = {
    "winter_2020_corrected": "s34_winter_stage3_development_v3_clean",
    "winter_2020_prototype_literal": "s34_winter_stage3_development_v3_prototype_literal",
    "sun_2024": "s35_sun_stage3_development_v2",
    "s36_bm25": "s36_bm25_stage3_development_v2",
    "s36_tfidf_svd": "s36_tfidf_svd_stage3_development_v2",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows: dict[str, Any] = {}
    for name, run_dir_name in RUNS.items():
        run_dir = ROOT / "outputs" / "development" / run_dir_name
        if not (run_dir / "evaluation.json").exists():
            raise RuntimeError(f"missing evaluation for {name}: {run_dir}")
        ev = _load_json(run_dir / "evaluation.json")
        v = ev["violation"]
        rows[name] = {
            "matching": {
                "MAP": ev["matching"]["MAP"],
                "binary": ev["matching"].get("binary"),
                "per_process_ap": ev["matching"].get("per_process_ap"),
            },
            "violation": {
                "macro_f1": v["macro_f1"],
                "micro_f1": v["micro_f1"],
                "observable_only_macro_f1": v.get("observable_only_macro_f1"),
                "exact_type_accuracy": v["exact_type_accuracy"],
                "per_type_f1": {k: x["f1"] for k, x in v["per_type"].items()},
                "per_type": v["per_type"],
                "detected": v["detected"],
                "missed": v["missed"],
                "wrong_type": v["wrong_type"],
                "unobservable": v["unobservable"],
                "denominator": v["denominator"],
            },
        }

    comparison = {
        "schema_version": "stage3_methods_dev_comparison@1.0.0",
        "note": "DEV_ONLY descriptive comparison; same 58 item IDs, same common evaluator, same Gold; "
                "no superiority claim from development numbers",
        "runs": rows,
        "caveats": [
            "the frozen violation pack has no compliant (none) gold items, so specificity is N/A and "
            "missing-action F1 can be an all-positive artifact",
            "Sun gamma=0.8 is strict under the spaCy en_core_web_sm backend (no word vectors): most "
            "incorrect-actor check points are unobservable (action mapping below gamma) - reported, not hidden",
            "Winter participant attribute is empty in the GDPR7 files, so its resource (actor) cost is vacuous",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

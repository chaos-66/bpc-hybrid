# -*- coding: utf-8 -*-
"""DEV_ONLY comparison between the Winter baseline (S3.4) and the Sun
reconstruction (S3.5) on the SAME 58 frozen item IDs with the SAME common
evaluator and the SAME Gold. Descriptive only - no superiority claim.

Usage:
    python scripts/compare_winter_sun_stage3_dev.py \
        --winter <winter predictions.jsonl> \
        --sun <sun predictions.jsonl> \
        --winter-run <winter run dir> --sun-run <sun run dir> \
        --out <comparison_with_winter_dev.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluate_stage3_common import evaluate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CORRECTION_PACK = ROOT / "data" / "development" / "human_review" / "stage3_gold_annotation_human_correction_v1.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--winter", type=Path, required=True)
    parser.add_argument("--sun", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--correction", type=Path, default=CORRECTION_PACK)
    args = parser.parse_args()

    winter = [json.loads(l) for l in args.winter.read_text(encoding="utf-8").splitlines() if l.strip()]
    sun = [json.loads(l) for l in args.sun.read_text(encoding="utf-8").splitlines() if l.strip()]
    correction = _load_json(args.correction)

    w_ids = {(p["task"], p["item_id"]) for p in winter}
    s_ids = {(p["task"], p["item_id"]) for p in sun}
    if w_ids != s_ids:
        raise RuntimeError(
            f"item id sets differ between Winter and Sun: only-winter={sorted(w_ids - s_ids)[:5]} "
            f"only-sun={sorted(s_ids - w_ids)[:5]}"
        )

    w_eval = evaluate(winter, correction)
    s_eval = evaluate(sun, correction)

    comparison = {
        "schema_version": "winter_sun_dev_comparison@1.0.0",
        "note": "DEV_ONLY descriptive comparison; same 58 item IDs, same common evaluator, same Gold; no superiority claim",
        "matching": {
            "winter": {"MAP": w_eval["matching"]["MAP"],
                       "binary": w_eval["matching"].get("binary")},
            "sun": {"MAP": s_eval["matching"]["MAP"],
                    "binary": s_eval["matching"].get("binary")},
            "per_process_ap": {
                "winter": w_eval["matching"]["per_process_ap"],
                "sun": s_eval["matching"]["per_process_ap"],
            },
            "difference_attribution": [
                "Winter: clause-bag spaCy similarity, relevance = fitness > 0 (no tau)",
                "Sun: Definition 4 matching score with tau=0.8; Rule Record action/actor separation",
                "ranking quality differences come from the score distribution, not the binary rule",
            ],
        },
        "violation": {
            "winter": {"per_type": w_eval["violation"]["per_type"],
                       "macro_f1": w_eval["violation"]["macro_f1"],
                       "exact_type_accuracy": w_eval["violation"]["exact_type_accuracy"],
                       "unobservable": w_eval["violation"]["unobservable"]},
            "sun": {"per_type": s_eval["violation"]["per_type"],
                    "macro_f1": s_eval["violation"]["macro_f1"],
                    "exact_type_accuracy": s_eval["violation"]["exact_type_accuracy"],
                    "unobservable": s_eval["violation"]["unobservable"]},
            "difference_attribution": [
                "missing_action: Sun Def 5 scores rule actions (denominator |Ar|); Winter obligation cost is clause-level",
                "incorrect_actor: Sun uses pool/lane names (observable on GDPR7 pools); Winter participant attribute is empty (vacuous)",
                "out_of_order: Sun Def 7 uses Rule Record order relations + Process Record reachability; Winter uses paragraph flow markers + sequence-flow reachability (bug-fixed mode)",
                "no compliant gold items exist, so specificity stays N/A for both",
            ],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

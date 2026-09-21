# -*- coding: utf-8 -*-
"""Cross-verify the thesis draft's Table 1/2/3 numbers against the frozen reports.

Asserts that every headline number the draft prints for the three paper tables
is the number actually present in the corresponding frozen report, and that the
mandatory claim-boundary wordings are still in place. This is the guard that
stops the draft drifting away from the artifacts after a report is regenerated.

Read-only. Exits non-zero if any check fails.

Usage:
    python scripts/verify_thesis_tables_v1.py
"""

from __future__ import annotations

import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str):
    return json.load(io.open(ROOT / rel, encoding="utf-8"))


def main() -> int:
    draft = io.open(ROOT / "paper" / "THESIS_DRAFT.md",
                    encoding="utf-8").read()
    t1 = _load("outputs/reports/stage2_table1_paper_final_v1.json")
    t2 = _load(
        "outputs/reports/stage2_table2_prompt_ablation_paper_final_v1.json")
    t3 = _load("outputs/reports/stage3_predecessors_paired_v1.json")
    grounded = _load("outputs/reports/stage3_grounded_checker_v1.json")

    baseline = t1["arms"]["sun_rule_only"]["overall_pooled_five_span_fields"]["f1"]
    ours = t1["arms"]["direct_llm"]["overall_pooled_five_span_fields"]["f1"]
    full = t2["arms"]["D-full-0813"]["overall_pooled_five_span_fields"]["f1"]
    sun = t3["arms"]["sun_reconstruction"]["macro_f1"]
    winter = t3["arms"]["winter_wrapper"]["macro_f1"]

    checks = [
        ("T1 pooled baseline 0.7631 present and correct",
         "0.7631" in draft and abs(baseline - 0.7631) < 2e-4),
        ("T1 pooled ours 0.8378 present and correct",
         "0.8378" in draft and abs(ours - 0.8378) < 2e-4),
        ("T1 delta +7.47 pp present and correct",
         "+7.47" in draft and abs(100 * (ours - baseline) - 7.47) < 0.05),
        ("T1 mean view 0.7970 / 0.8088 still reported",
         "0.7970" in draft and "0.8088" in draft),
        ("T2 Full 0.8224 present and correct",
         "0.8224" in draft and abs(full - 0.8224) < 2e-4),
        ("T2 states no deletion is significant on the pooled metric",
         "CI \u6392\u9664 0" in draft),
        ("T2 demotes J to Base Output Contract",
         "Base Output Contract" in draft),
        ("T3 sun_reconstruction 0.3175 present and correct",
         "0.3175" in draft and abs(sun - 0.3175) < 2e-4),
        ("T3 winter_wrapper 0.2222 present and correct",
         "0.2222" in draft and abs(winter - 0.2222) < 2e-4),
        ("T3 grounded reference 1.0000 present and correct",
         "1.0000" in draft and grounded["macro_f1"] == 1.0),
        ("T3 33-item table marked retired", "\u5df2\u5e9f\u6b62" in draft),
        ("T3 keeps the grounding-effect wording",
         "grounding \u6548\u5e94" in draft),
        ("T3 disclaims the grounded upper bound as Ours",
         '\u4e0d\u662f "Ours"' in draft),
        ("T3 keeps the out_of_order no-claim wording",
         "\u4e0d\u6784\u6210\u65b9\u6cd5\u95f4\u5dee\u5f02" in draft),
    ]

    failed = 0
    for name, ok in checks:
        print(("PASS " if ok else "FAIL ") + name)
        if not ok:
            failed += 1
    print()
    print(f"failed: {failed} / {len(checks)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""R15.0 Sun-style vs R14.4 Rule+LLM Comparison.

Compares R15.0 evaluation metrics against R14.4 evaluation metrics.
Produces:
  - comparison summary JSON
  - field-level comparison JSONL
  - descriptive report Markdown
  - PPT-safe Markdown doc

Usage::

    $env:BPC_HYBRID_DISABLE_PROJECT_ENV = "1"
    .venv/Scripts/python.exe scripts/compare_r15_sun_style_vs_rule_llm.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_R15_SUMMARY = (
    _PROJECT_ROOT / "data" / "formal" / "results"
    / "r15_0_sun_style_rule_only_evaluation_summary.json"
)
_R15_DETAILS = (
    _PROJECT_ROOT / "data" / "formal" / "results"
    / "r15_0_sun_style_rule_only_evaluation_details.jsonl"
)
_R14_SUMMARY = (
    _PROJECT_ROOT / "data" / "formal" / "results"
    / "r14_4_rule_plus_llm_evaluation_summary.json"
)
_R14_DETAILS = (
    _PROJECT_ROOT / "data" / "formal" / "results"
    / "r14_4_rule_plus_llm_evaluation_details.jsonl"
)

_COMPARISON_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "results"
    / "r15_vs_r14_4_comparison_summary.json"
)
_FIELD_OUT = (
    _PROJECT_ROOT / "data" / "formal" / "results"
    / "r15_vs_r14_4_field_comparison.jsonl"
)
_REPORT_OUT = (
    _PROJECT_ROOT / "docs"
    / "r15_0_sun_style_vs_r14_4_rule_llm_comparison_report.md"
)
_PPT_OUT = (
    _PROJECT_ROOT / "docs"
    / "r15_0_sun_style_vs_r14_4_ppt_doc.md"
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== R15.0 Sun-style vs R14.4 Rule+LLM Comparison ===")
    print()

    # Load summaries
    r15_summary = json.loads(_R15_SUMMARY.read_text(encoding="utf-8"))
    r14_summary = json.loads(_R14_SUMMARY.read_text(encoding="utf-8"))

    # Build comparison
    metrics = [
        "overall_field_exact_accuracy",
        "strict_f1",
        "macro_strict_f1",
        "lenient_partial_f1",
        "macro_lenient_f1",
    ]

    comparison = {
        "comparison_name": "R15.0 Sun-style Rule-Template vs R14.4 Rule+LLM",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "r15_method": "sun_style_rule_template",
        "r14_method": "rule_plus_llm",
        "r15_no_llm": True,
        "r14_used_llm": True,
        "key_claim": (
            "R15.0 Sun-style rule-template baseline is structurally more "
            "aligned with Sun et al. (2024) method than R14.2 lightweight "
            "rule-only baseline.  R15.0 does NOT outperform R14.4 (rule+LLM) "
            "on numeric metrics because R15.0 uses no LLM.  Still, R15.0 is "
            "NOT an exact Sun reproduction — the original datasets, trained "
            "BERT model, full marker lexicon, and original BPMN benchmark "
            "are unavailable."
        ),
        "metrics": {},
        "field_comparison": {},
    }

    for m in metrics:
        v15 = r15_summary.get(m)
        v14 = r14_summary.get(m)
        delta = None
        if isinstance(v15, (int, float)) and isinstance(v14, (int, float)):
            delta = round(v15 - v14, 4)
        comparison["metrics"][m] = {
            "R15_0": v15,
            "R14_4": v14,
            "delta_R15_minus_R14": delta,
        }

    # Field-level comparison
    r15_fields = r15_summary.get("field_level_summary", {})
    r14_fields = r14_summary.get("field_level_summary", {})

    for field_name in sorted(r15_fields.keys() | r14_fields.keys()):
        f15 = r15_fields.get(field_name, {})
        f14 = r14_fields.get(field_name, {})
        comparison["field_comparison"][field_name] = {
            "R15_0_strict_f1": f15.get("strict_f1"),
            "R14_4_strict_f1": f14.get("strict_f1"),
            "R15_0_lenient_f1": f15.get("lenient_f1"),
            "R14_4_lenient_f1": f14.get("lenient_f1"),
            "R15_0_exact_accuracy": f15.get("field_exact_accuracy"),
            "R14_4_exact_accuracy": f14.get("field_exact_accuracy"),
            "delta_strict_f1": (
                round(f15.get("strict_f1", 0) - f14.get("strict_f1", 0), 4)
                if isinstance(f15.get("strict_f1"), (int, float))
                and isinstance(f14.get("strict_f1"), (int, float))
                else None
            ),
        }

    # Write comparison summary
    _COMPARISON_OUT.parent.mkdir(parents=True, exist_ok=True)
    _COMPARISON_OUT.write_text(
        json.dumps(comparison, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Comparison summary: {_COMPARISON_OUT}")

    # Write field JSONL
    with _FIELD_OUT.open("w", encoding="utf-8") as fh:
        for field_name, data in comparison["field_comparison"].items():
            fh.write(json.dumps({"field": field_name, **data},
                                ensure_ascii=False) + "\n")
    print(f"Field JSONL: {_FIELD_OUT}")

    # Generate descriptive report
    report = _generate_report(comparison)
    _REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_OUT.write_text(report, encoding="utf-8")
    print(f"Report: {_REPORT_OUT}")

    # Generate PPT-safe doc
    ppt = _generate_ppt_doc(comparison)
    _PPT_OUT.parent.mkdir(parents=True, exist_ok=True)
    _PPT_OUT.write_text(ppt, encoding="utf-8")
    print(f"PPT doc: {_PPT_OUT}")

    # Print summary
    print()
    print("=== Key Numbers ===")
    for m in metrics:
        v15 = comparison["metrics"][m]["R15_0"]
        v14 = comparison["metrics"][m]["R14_4"]
        d = comparison["metrics"][m]["delta_R15_minus_R14"]
        print(f"  {m}: R15={v15}, R14.4={v14}, delta={d}")

    print()
    print("Done.")


def _generate_report(comparison: dict) -> str:
    """Generate a Markdown comparison report."""
    m = comparison["metrics"]
    lines = [
        "# R15.0 Sun-style Rule-Template vs R14.4 Rule+LLM Comparison Report",
        "",
        f"**Generated**: {comparison['timestamp_utc']}",
        "",
        "## Methods Compared",
        "",
        f"- **R15.0**: `{comparison['r15_method']}` (no LLM, no API, no external downloads)",
        f"- **R14.4**: `{comparison['r14_method']}` (rule extraction + LLM for additional fields)",
        "",
        "## Key Claim",
        "",
        comparison["key_claim"],
        "",
        "## Overall Metrics",
        "",
        "| Metric | R15.0 | R14.4 | Delta (R15-R14) |",
        "|--------|-------|-------|------------------|",
    ]
    for metric_name in ["overall_field_exact_accuracy", "strict_f1",
                         "macro_strict_f1", "lenient_partial_f1",
                         "macro_lenient_f1"]:
        data = m.get(metric_name, {})
        lines.append(
            f"| {metric_name} | {data.get('R15_0')} | {data.get('R14_4')} "
            f"| {data.get('delta_R15_minus_R14')} |"
        )

    lines += [
        "",
        "## Field-Level Comparison",
        "",
        "| Field | R15 Strict F1 | R14.4 Strict F1 | Delta |",
        "|-------|--------------|-----------------|-------|",
    ]
    for field_name, fdata in comparison.get("field_comparison", {}).items():
        lines.append(
            f"| {field_name} | {fdata.get('R15_0_strict_f1')} "
            f"| {fdata.get('R14_4_strict_f1')} "
            f"| {fdata.get('delta_strict_f1')} |"
        )

    lines += [
        "",
        "## Important Context",
        "",
        "- R15.0 is **rule-only** — NO LLM/API calls.",
        "- R14.4 is **rule+LLM** — uses LLM for additional field extraction.",
        "- R15.0 uses **Sun-style method structure** (modality classifier,",
        "  domain marker lexicon, syntactic rules, BPMN/violation scaffold).",
        "- R14.2 lightweight baseline did NOT use Sun-style method structure.",
        "- R15.0 does NOT constitute exact Sun reproduction.",
        "- The original Sun et al. datasets, trained BERT model, full marker",
        "  lexicon, and original BPMN evaluation benchmark are UNAVAILABLE.",
        "",
        "## Conclusion",
        "",
        "R15.0 provides a **method-aligned but not equivalent** rule-template",
        "baseline.  It is structurally closer to Sun et al. (2024) than the",
        "R14.2 lightweight baseline.  However, it still does not match the",
        "original Sun et al. numbers due to:",
        "",
        "1. No original trained BERT model",
        "2. No original syntactic parsing infrastructure",
        "3. No full GDPR BPMN benchmark dataset",
        "4. Deterministic fallback marker lexicon (hand-crafted, not learned)",
        "",
        "This establishes the correct baseline for any future LLM-free",
        "Sun-style comparison.",
    ]
    return "\n".join(lines) + "\n"


def _generate_ppt_doc(comparison: dict) -> str:
    """Generate a PPT-safe Markdown document (bullets, no complex tables)."""
    m = comparison["metrics"]
    lines = [
        "# R15.0 vs R14.4 — Presentation Summary",
        "",
        "## Slide 1: Title",
        "",
        "- R15.0: Sun-style Rule-Template Baseline",
        "- Comparison with R14.4 Rule+LLM",
        "",
        "## Slide 2: What is R15.0?",
        "",
        "- Rule-template extraction following Sun et al. (2024) method structure",
        "- Uses modality classifier, domain marker lexicon, syntactic rules",
        "- Includes BPMN process semantic parser and violation detector",
        "- NO LLM, NO API, NO external downloads",
        "- NOT an exact Sun reproduction (datasets/model unavailable)",
        "",
        "## Slide 3: Key Numbers",
        "",
        f"- R15.0 Overall Field Exact Accuracy: {m['overall_field_exact_accuracy']['R15_0']}",
        f"- R14.4 Overall Field Exact Accuracy: {m['overall_field_exact_accuracy']['R14_4']}",
        f"- R15.0 Strict F1: {m['strict_f1']['R15_0']}",
        f"- R14.4 Strict F1: {m['strict_f1']['R14_4']}",
        f"- R15.0 Macro Strict F1: {m['macro_strict_f1']['R15_0']}",
        f"- R14.4 Macro Strict F1: {m['macro_strict_f1']['R14_4']}",
        "",
        "## Slide 4: Method Structural Comparison",
        "",
        "R15.0 (Sun-style):",
        "- Modality classification (obligation/prohibition/permission/definition)",
        "- Domain marker lexicon (conditions, constraints, exceptions, actors)",
        "- Syntactic span-based extraction (surrogate for tree patterns)",
        "- BPMN process semantics (import/parse BPMN 2.0 XML)",
        "- Violation detection (missing action, incorrect actor, out-of-order)",
        "",
        "R14.2 (Lightweight):",
        "- Regex-based keyword extraction",
        "- Simple token-based field assignment",
        "- No marker lexicon",
        "- No BPMN support",
        "- No violation detection",
        "",
        "R14.4 (Rule+LLM):",
        "- Same rule extraction as R14.2",
        "- Plus LLM for additional field extraction",
        "",
        "## Slide 5: Important Limitations",
        "",
        "- R15.0 is rule-only and does NOT outperform rule+LLM",
        "- No original Sun trained BERT model available",
        "- No original syntactic parser available (deterministic fallback)",
        "- No full GDPR BPMN benchmark dataset",
        "- Hand-crafted marker lexicon (not learned from data)",
        "- NOT an exact reproduction of Sun et al. (2024)",
        "",
        "## Slide 6: What R15.0 Achieves",
        "",
        "- Corrects methodological risk identified in R14.2",
        "- Provides structurally aligned rule-template baseline",
        "- Enables honest comparison: 'our best approximation of Sun'",
        "- Documents all gaps between our implementation and original method",
        "- Ready for future enhancement if BERT/parser/datasets become available",
        "",
        "## Slide 7: Key Takeaway",
        "",
        "\"R15 Sun-style rule-template baseline is more method-aligned than",
        "R14.2 lightweight baseline. Still not exact Sun reproduction.\"",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()

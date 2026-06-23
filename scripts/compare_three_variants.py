"""Compare three variants: Sun-style, spaCy-enhanced, Rule+LLM"""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

files = {
    "Sun-style (rule-only)": PROJECT_ROOT / "outputs/r15_gdpr50_sun_style_summary.json",
    "spaCy-enhanced": PROJECT_ROOT / "outputs/r15_gdpr50_spacy_enhanced_summary.json",
    "Rule+LLM fallback": PROJECT_ROOT / "outputs/r15_gdpr50_rule_plus_llm_summary.json",
}

fields = ["modality", "actor", "action", "condition", "constraint", "exception"]

summaries = {}
for name, path in files.items():
    with open(path) as f:
        summaries[name] = json.load(f)

# Print overall comparison
print("=" * 80)
print("GDPR-50 Three-Way Comparison")
print("=" * 80)

header = f"{'Metric':<25s} | {'Sun-style':>12s} | {'spaCy-enh':>12s} | {'Rule+LLM':>12s}"
print(header)
print("-" * 80)

for metric_key, metric_name in [
    ("strict_f1", "Strict F1 (micro)"),
    ("lenient_partial_f1", "Lenient F1 (micro)"),
    ("macro_strict_f1", "Strict F1 (macro)"),
    ("macro_lenient_f1", "Lenient F1 (macro)"),
    ("overall_field_exact_accuracy", "Exact Accuracy"),
]:
    vals = []
    for name in files:
        s = summaries[name]
        v = s.get(metric_key)
        if v is None:
            v = s.get("lenient_f1", 0)
        vals.append(v)
    print(f"{metric_name:<25s} | {vals[0]:>12.4f} | {vals[1]:>12.4f} | {vals[2]:>12.4f}")

# Print field-level comparison
print()
print("=" * 80)
print("Field-Level Strict F1")
print("=" * 80)
header = f"{'Field':<15s} | {'Sun-style':>12s} | {'spaCy-enh':>12s} | {'Rule+LLM':>12s}"
print(header)
print("-" * 80)

for field in fields:
    vals = []
    for name in files:
        fs = summaries[name].get("field_level_summary", {})
        f_data = fs.get(field, {})
        vals.append(f_data.get("strict_f1", 0))
    print(f"{field:<15s} | {vals[0]:>12.4f} | {vals[1]:>12.4f} | {vals[2]:>12.4f}")

# Print exact counts
print()
print("=" * 80)
print("Field-Level Exact Counts (exact / gold_count)")
print("=" * 80)
header = f"{'Field':<15s} | {'Sun-style':>12s} | {'spaCy-enh':>12s} | {'Rule+LLM':>12s}"
print(header)
print("-" * 80)

for field in fields:
    vals = []
    for name in files:
        fs = summaries[name].get("field_level_summary", {})
        f_data = fs.get(field, {})
        ec = f_data.get("exact_count", 0)
        gc = f_data.get("applicable_gold_count", 0)
        vals.append(f"{ec}/{gc}")
    print(f"{field:<15s} | {vals[0]:>12s} | {vals[1]:>12s} | {vals[2]:>12s}")

# Print non-empty field counts from predictions
print()
print("=" * 80)
print("Non-Empty Field Coverage")
print("=" * 80)

pred_files = {
    "Sun-style (rule-only)": PROJECT_ROOT / "data/formal/predictions/r15_gdpr50_sun_style_predictions.jsonl",
    "spaCy-enhanced": PROJECT_ROOT / "data/formal/predictions/r15_gdpr50_spacy_enhanced_predictions.jsonl",
    "Rule+LLM fallback": PROJECT_ROOT / "data/formal/predictions/r15_gdpr50_rule_plus_llm_predictions.jsonl",
}

header = f"{'Field':<15s} | {'Sun-style':>12s} | {'spaCy-enh':>12s} | {'Rule+LLM':>12s}"
print(header)
print("-" * 80)

for field in fields:
    vals = []
    for name in files:
        path = pred_files[name]
        count = 0
        total = 0
        with open(path) as f:
            for line in f:
                rec = json.loads(line)
                total += 1
                pf = rec.get("prediction_fields", {})
                fv = pf.get(field, {}).get("value", "")
                if fv and fv.strip():
                    count += 1
        vals.append(f"{count}/{total}")
    print(f"{field:<15s} | {vals[0]:>12s} | {vals[1]:>12s} | {vals[2]:>12s}")

# Summary
print()
print("=" * 80)
print("KEY FINDINGS")
print("=" * 80)

best_strict = max(summaries.items(), key=lambda x: x[1].get("strict_f1", 0))
best_lenient = max(summaries.items(), key=lambda x: x[1].get("lenient_partial_f1", x[1].get("lenient_f1", 0)))

print(f"  Best Strict F1:  {best_strict[0]} = {best_strict[1]['strict_f1']:.4f}")
print(f"  Best Lenient F1: {best_lenient[0]} = {best_lenient[1].get('lenient_partial_f1', best_lenient[1].get('lenient_f1', 0)):.4f}")
print()
print("  In this local GDPR-50 run, Rule+LLM had higher non-empty field coverage (more fields filled)")
print("  but uses longer/different phrasing that lowers Jaccard similarity.")
print("  The gap between strict and lenient F1 narrows with Rule+LLM,")
print("  suggesting the LLM fills content that is semantically relevant")
print("  but not exactly matching the gold annotations.")

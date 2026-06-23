import json

# Load predictions (has actual pred values)
predictions = []
with open("data/formal/predictions/r15_gdpr50_rule_plus_llm_predictions.jsonl", encoding="utf-8") as f:
    for line in f:
        predictions.append(json.loads(line))

# Load gold
gold = []
with open("data/formal/r15_gdpr50/r15_gdpr50_gold.jsonl", encoding="utf-8") as f:
    for line in f:
        gold.append(json.loads(line))

# Load candidate samples for text
candidates = []
with open("data/formal/r15_gdpr50/r15_gdpr50_candidate_samples.jsonl", encoding="utf-8") as f:
    for line in f:
        candidates.append(json.loads(line))

# Load details (has scores)
details = []
with open("data/formal/results/r15_gdpr50_rule_plus_llm_details.jsonl", encoding="utf-8") as f:
    for line in f:
        details.append(json.loads(line))

# Check ALL samples for mismatches
total = 0
exact = 0
mismatched = []
for i in range(min(len(predictions), len(gold))):
    total += 1
    p = predictions[i]
    g = gold[i]
    c = candidates[i] if i < len(candidates) else {}
    dt = details[i] if i < len(details) else {}

    mismatches = []
    for field in ["modality", "actor", "action", "condition", "constraint", "exception"]:
        # Gold: gold_fields.{field}.value
        gold_val = g.get("gold_fields", {}).get(field, {}).get("value")
        # Pred: prediction_fields.{field}.value
        pred_val = p.get("prediction_fields", {}).get(field, {}).get("value")
        # Score: field_scores.{field}
        score = dt.get("field_scores", {}).get(field, "")

        # Normalize
        gold_norm = str(gold_val or "").strip().lower()
        pred_norm = str(pred_val or "").strip().lower()

        if gold_norm != pred_norm:
            mismatches.append({"field": field, "gold": gold_val, "pred": pred_val, "score": score})

    if len(mismatches) == 0:
        exact += 1
    else:
        entry = {
            "sample_index": i,
            "sample_id": g.get("sample_id"),
            "text_preview": c.get("sentence", c.get("text", p.get("source_text", "")))[:100],
            "mismatch_count": len(mismatches),
            "mismatches": mismatches,
        }
        # Classify
        has_none_pred = any(m["pred"] is None for m in mismatches)
        has_none_gold = any(m["gold"] is None for m in mismatches)
        wrong_count = sum(1 for m in mismatches if m["score"] == "wrong")
        partial_count = sum(1 for m in mismatches if m["score"] == "partial")

        if has_none_pred and not has_none_gold:
            entry["classification"] = "pred_missing_fields_gold_has_values"
        elif has_none_gold and not has_none_pred:
            entry["classification"] = "pred_too_verbose"
        elif wrong_count > 0 and partial_count > 0:
            entry["classification"] = "mixed_errors"
        elif wrong_count > 0:
            entry["classification"] = "semantic_mismatch"
        else:
            entry["classification"] = "partial_match_or_format_diff"

        mismatched.append(entry)

print(f"Total: {total}")
print(f"Exact: {exact}")
print(f"Mismatched: {len(mismatched)}")
print()

# Class breakdown
from collections import Counter
classes = Counter(m["classification"] for m in mismatched)
for cls, cnt in classes.most_common():
    print(f"  {cls}: {cnt}")
print()

# Print first 10
for m in mismatched[:10]:
    print(f"Sample {m['sample_index']} ({m['sample_id']}): {m['text_preview']}...")
    print(f"  Class: {m['classification']}, Mismatches: {m['mismatch_count']}")
    for mm in m["mismatches"]:
        print(f"    {mm['field']}: gold={mm['gold']!r} pred={mm['pred']!r} score={mm['score']}")
    print()

# Save all
with open("data/formal/results/h1_gold_annotation_mismatch_samples.jsonl", "w", encoding="utf-8") as f:
    for m in mismatched:
        f.write(json.dumps(m, ensure_ascii=False) + "\n")

print(f"Saved {len(mismatched)} mismatch samples")

import json

details = []
with open("data/formal/results/r15_gdpr50_rule_plus_llm_details.jsonl", encoding="utf-8") as f:
    for line in f:
        details.append(json.loads(line))

gold = []
with open("data/formal/r15_gdpr50/r15_gdpr50_gold.jsonl", encoding="utf-8") as f:
    for line in f:
        gold.append(json.loads(line))

# Load candidate samples for text
candidates = []
with open("data/formal/r15_gdpr50/r15_gdpr50_candidate_samples.jsonl", encoding="utf-8") as f:
    for line in f:
        candidates.append(json.loads(line))

# Check ALL samples for mismatches
total = 0
exact = 0
mismatched = []
for i in range(min(len(details), len(gold))):
    total += 1
    d = details[i]
    g = gold[i]
    c = candidates[i] if i < len(candidates) else {}
    
    mismatches = []
    for field in ["modality", "actor", "action", "condition", "constraint", "exception"]:
        # Gold has nested structure: gold_fields.{field}.value
        gold_val = g.get("gold_fields", {}).get(field, {}).get("value")
        # Details has nested structure: field_scores.{field}.pred
        pred_val = d.get("field_scores", {}).get(field, {}).get("pred")
        
        # Normalize
        gold_norm = str(gold_val or "").strip().lower()
        pred_norm = str(pred_val or "").strip().lower()
        
        if gold_norm != pred_norm:
            mismatches.append(field)
    
    if len(mismatches) == 0:
        exact += 1
    else:
        mismatched.append({
            "sample_index": i,
            "sample_id": g.get("sample_id"),
            "text_preview": c.get("sentence", c.get("text", ""))[:80],
            "mismatched_fields": mismatches,
            "details": {
                f: {
                    "gold": g.get("gold_fields", {}).get(f, {}).get("value"),
                    "pred": d.get("field_scores", {}).get(f, {}).get("pred"),
                    "gold_applicable": g.get("gold_fields", {}).get(f, {}).get("applicable"),
                    "pred_score": d.get("field_scores", {}).get(f, {}).get("score")
                } for f in mismatches
            }
        })

print(f"Total: {total}")
print(f"Exact: {exact}")
print(f"Mismatched: {len(mismatched)}")
print()

# Classify mismatches
for m in mismatched:
    has_none_pred = any(m["details"][f]["pred"] is None for f in m["details"])
    has_none_gold = any(m["details"][f]["gold"] is None for f in m["details"])
    if has_none_pred and not has_none_gold:
        m["classification"] = "gold_too_short_or_missing_in_pred"
    elif has_none_gold and not has_none_pred:
        m["classification"] = "prediction_too_verbose"
    elif len(m["mismatched_fields"]) == 1:
        m["classification"] = "single_field_mismatch"
    else:
        m["classification"] = "semantic_mismatch"

# Print first 15
for m in mismatched[:15]:
    print(f"Sample {m['sample_index']} ({m['sample_id']}): {m['text_preview']}...")
    print(f"  Classification: {m['classification']}")
    for f, vals in m["details"].items():
        print(f"  {f}: gold={vals['gold']!r}, pred={vals['pred']!r}")
    print()

# Save
with open("data/formal/results/h1_gold_annotation_mismatch_samples.jsonl", "w", encoding="utf-8") as f:
    for m in mismatched:
        f.write(json.dumps(m, ensure_ascii=False) + "\n")

print(f"Saved {len(mismatched)} mismatch samples")

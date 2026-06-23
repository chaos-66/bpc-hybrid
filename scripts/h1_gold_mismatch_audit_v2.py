import json

details = []
with open("data/formal/results/r15_gdpr50_rule_plus_llm_details.jsonl", encoding="utf-8") as f:
    for line in f:
        details.append(json.loads(line))

gold = []
with open("data/formal/r15_gdpr50/r15_gdpr50_gold.jsonl", encoding="utf-8") as f:
    for line in f:
        gold.append(json.loads(line))

# Check ALL samples for mismatches
total = 0
exact = 0
mismatched = []
for i in range(min(len(details), len(gold))):
    total += 1
    d = details[i]
    g = gold[i]
    
    mismatches = []
    for field in ["modality", "actor", "action", "condition", "constraint", "exception"]:
        pred_val = d.get(field)
        gold_val = g.get(field)
        # Normalize: None vs empty string
        if str(pred_val or "").strip().lower() != str(gold_val or "").strip().lower():
            mismatches.append(field)
    
    if len(mismatches) == 0:
        exact += 1
    else:
        mismatched.append({
            "sample_index": i,
            "text_preview": d.get("text", "")[:80],
            "mismatched_fields": mismatches,
            "details": {f: {"gold": g.get(f), "pred": d.get(f)} for f in mismatches}
        })

print(f"Total: {total}")
print(f"Exact: {exact}")
print(f"Mismatched: {len(mismatched)}")
print()
for m in mismatched[:15]:
    print(f"Sample {m['sample_index']}: {m['text_preview']}...")
    for f, vals in m["details"].items():
        print(f"  {f}: gold={vals['gold']!r}, pred={vals['pred']!r}")
    print()

# Save
with open("data/formal/results/h1_gold_annotation_mismatch_samples.jsonl", "w", encoding="utf-8") as f:
    for m in mismatched:
        # Add classification
        has_none_pred = any(m["details"][f]["pred"] is None for f in m["details"])
        has_none_gold = any(m["details"][f]["gold"] is None for f in m["details"])
        if has_none_pred and not has_none_gold:
            m["classification"] = "gold_too_short_or_missing_in_pred"
        elif has_none_gold and not has_none_pred:
            m["classification"] = "prediction_too_verbose"
        else:
            m["classification"] = "semantic_mismatch"
        f.write(json.dumps(m, ensure_ascii=False) + "\n")

print(f"Saved {len(mismatched)} mismatch samples")

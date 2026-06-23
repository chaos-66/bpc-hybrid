import json

details = []
with open("data/formal/results/r15_gdpr50_rule_plus_llm_details.jsonl", encoding="utf-8") as f:
    for line in f:
        details.append(json.loads(line))

gold = []
with open("data/formal/r15_gdpr50/r15_gdpr50_gold.jsonl", encoding="utf-8") as f:
    for line in f:
        gold.append(json.loads(line))

samples = []
indices = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45]
for i in indices:
    if i < len(details) and i < len(gold):
        d = details[i]
        g = gold[i]
        text = d.get("text", "")
        
        mismatches = []
        for field in ["modality", "actor", "action", "condition", "constraint", "exception"]:
            pred_val = d.get(field)
            gold_val = g.get(field)
            if pred_val != gold_val:
                mismatches.append(field)
        
        # Classify
        if len(mismatches) == 0:
            classification = "exact_match"
        elif any(d.get(f) is None and g.get(f) is not None for f in mismatches):
            classification = "gold_too_short_or_missing_in_pred"
        elif any(d.get(f) is not None and g.get(f) is None for f in mismatches):
            classification = "prediction_too_verbose"
        else:
            classification = "semantic_mismatch"
        
        sample = {
            "sample_index": i,
            "text_preview": text[:100],
            "mismatched_fields": mismatches,
            "classification": classification,
            "details": {}
        }
        for field in mismatches:
            sample["details"][field] = {
                "gold": g.get(field),
                "pred": d.get(field)
            }
        samples.append(sample)

with open("data/formal/results/h1_gold_annotation_mismatch_samples.jsonl", "w", encoding="utf-8") as f:
    for s in samples:
        f.write(json.dumps(s, ensure_ascii=False) + "\n")

print(f"Audited {len(samples)} samples")
print(f"Exact matches: {sum(1 for s in samples if s['classification'] == 'exact_match')}")
print(f"Gold too short: {sum(1 for s in samples if 'gold_too_short' in s['classification'])}")
print(f"Prediction verbose: {sum(1 for s in samples if 'verbose' in s['classification'])}")
print(f"Semantic mismatch: {sum(1 for s in samples if 'mismatch' in s['classification'])}")

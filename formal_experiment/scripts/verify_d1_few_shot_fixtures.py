"""Quick ad-hoc verifier: run prompt loader over D1 prompt, check few-shot examples pass canonical validator."""
import sys
sys.path.insert(0, "formal_experiment/src")

from bpc_hybrid.prompt_loader import load_prompt
from bpc_hybrid.stage2_canonical import validate_canonical

p = load_prompt("direct_llm_sun_record_prompt")
print(f"Validating {len(p.few_shot_examples)} few-shot examples...")
ok = bad = 0
for i, ex in enumerate(p.few_shot_examples):
    payload = ex["output"]
    rep = validate_canonical(payload)
    is_valid = rep.schema_valid and rep.cross_field_valid
    if is_valid:
        ok += 1
    else:
        bad += 1
        print(f"  Example {i+1} ({ex['description'][:60]}): BAD")
        for err in rep.errors[:5]:
            print(f"    - {err}")
print(f"OK: {ok}, BAD: {bad}")

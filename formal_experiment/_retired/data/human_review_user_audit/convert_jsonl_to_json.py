"""Convert JSONL to formatted JSON array for easier human editing."""
import json, sys, pathlib

src = pathlib.Path(__file__).parent / "estg150_review_pack_user_audit_v1.jsonl"
dst = pathlib.Path(__file__).parent / "estg150_review_pack_user_audit_v1.json"

with open(src, encoding="utf-8") as f:
    records = [json.loads(line) for line in f if line.strip()]

with open(dst, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"Done: {len(records)} records -> {dst.name}")

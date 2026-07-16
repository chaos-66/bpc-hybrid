"""Compute EStG-150 membership hashes. One-shot helper.

Run from formal_experiment/ as:
    python scripts/compute_estg_membership_hashes.py
"""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data" / "development" / "estg"


def load_jsonl(p):
    out = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def main():
    sel = load_jsonl(BASE / "estg_selected_150_de.jsonl")
    sel_ids = sorted(r["id"] for r in sel)
    assert len(sel_ids) == 150, f"expected 150 selected, got {len(sel_ids)}"
    assert len(set(sel_ids)) == 150, "selected ids not unique"

    # Per-record raw German SHA-256
    per_record = []
    for r in sel:
        h = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
        per_record.append({
            "legacy_record_id": r["id"],
            "sha256_raw_de": h,
            "text_len": len(r["text"]),
            "word_count": r.get("word_count"),
        })

    # Membership manifest SHA-256 (sorted ids, comma-joined)
    membership_payload = ",".join(str(i) for i in sel_ids)
    membership_sha256 = hashlib.sha256(membership_payload.encode("utf-8")).hexdigest()

    # Whole-file SHA-256 of the selected 150 (binary content)
    file_sha = hashlib.sha256(
        (BASE / "estg_selected_150_de.jsonl").read_bytes()
    ).hexdigest()

    out = {
        "candidate_pool": {
            "path": "data/development/estg/estg_sentences_de.jsonl",
            "count": 885,
        },
        "selected_membership": {
            "path": "data/development/estg/estg_selected_150_de.jsonl",
            "count": 150,
            "sorted_legacy_record_ids": sel_ids,
            "membership_payload_sha256": membership_sha256,
            "file_sha256": file_sha,
        },
        "per_record_raw_de_sha256": per_record,
    }

    dst = BASE / "estg_150_membership_hashes.json"
    dst.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {dst} with {len(per_record)} per-record hashes.")
    print(f"membership_payload_sha256 = {membership_sha256}")
    print(f"file_sha256 = {file_sha}")


if __name__ == "__main__":
    main()

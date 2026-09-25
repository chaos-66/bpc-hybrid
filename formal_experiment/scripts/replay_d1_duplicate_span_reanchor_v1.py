"""Offline replay for D1 duplicate-text re-anchoring (zero API).

Reads already-persisted raw responses if available.  The committed report
contains only derived offsets/hashes and booleans, not raw response text.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from bpc_hybrid.d1_span_canonicalizer import canonicalize_record_coordinates  # noqa: E402

DEFAULT_RAW_DIR = ROOT / "data/predictions/stage3_v4_d1_frozen_v1/raw_responses"
OUTPUT = ROOT / "outputs/reports/stage3_table3_r5_d1_duplicate_span_replay_v2.json"
TARGET_FILES = {
    "R5-D-01": "01_gdpr_article13p3_s001.json",
    "R5-D-02": "02_gdpr_article14p4_s001.json",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def load_raw_record(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    body = json.loads(base64.b64decode(doc["raw_response_body_base64"]))
    content = body["choices"][0]["message"]["content"]
    return json.loads(content)


def replay(raw_dir: Path) -> dict:
    rows = []
    for rid, filename in TARGET_FILES.items():
        path = raw_dir / filename
        if not path.exists():
            rows.append({"requirement_id": rid, "status": "raw_response_unavailable", "raw_file": filename})
            continue
        raw = load_raw_record(path)
        src = raw["source_text"]
        canonical, audit = canonicalize_record_coordinates(raw, src)
        original_spans = []
        for ci, clause in enumerate(raw.get("clauses") or []):
            for field in ("actors", "actions", "conditions", "constraints", "exceptions"):
                for span in clause.get(field) or []:
                    text = span.get("text")
                    if isinstance(text, str) and text and src.count(text) > 1:
                        original_spans.append({
                            "clause_index": ci,
                            "field": field,
                            "span_id": span.get("id"),
                            "text": text,
                            "raw_start": span.get("start"),
                            "raw_end": span.get("end"),
                            "occurrence_count": src.count(text),
                            "occurrence_starts": [i for i in range(len(src)) if src.startswith(text, i)],
                        })
        recovered_clauses = canonical.get("clauses") or []
        actor_spans = [
            span for clause in recovered_clauses for span in (clause.get("actors") or [])
        ]
        edges = [
            edge for clause in recovered_clauses for edge in (clause.get("actor_action_map") or [])
        ]
        rows.append({
            "requirement_id": rid,
            "status": "replayed",
            "raw_file": filename,
            "source_text_sha256": __import__("hashlib").sha256(src.encode("utf-8")).hexdigest(),
            "duplicate_spans": original_spans,
            "canonicalizer_audit": {
                "status": audit.get("status"),
                "reanchored_count": audit.get("reanchored_count"),
                "dropped_spans": audit.get("dropped_spans"),
                "dropped_edges": audit.get("dropped_edges"),
            },
            "actor_recovered": bool(actor_spans),
            "actor_action_relation_recovered": bool(edges),
            "remaining_ambiguity": bool(audit.get("dropped_spans") or audit.get("dropped_edges")),
        })
    return {
        "schema_version": "stage3_table3_r5_d1_duplicate_span_replay@2.0.0",
        "method": "raw LLM start/end interval + unique_overlap/nearest_occurrence",
        "used_gold": False,
        "used_reference": False,
        "real_api_calls_made": 0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = replay(args.raw_dir)
    if args.write:
        write_json(OUTPUT, report)
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

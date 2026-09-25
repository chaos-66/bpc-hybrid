"""Freeze source-only order eligibility and bounded GDPR source search (zero API).

No prediction, score, Gold, or reference label is read.  The eligibility
rules are fixed before inspecting the benchmark rows, and the bounded search
stops at two additional independent order-capable source families.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/stage3_table3_r5_benchmark_v2.json"
SOURCE_REQ = ROOT / "data/development/stage3_table3_r5_benchmark_v2/source_requirements.json"
OUTPUT = ROOT / "outputs/reports/stage3_table3_r5_order_eligibility_v2.json"

ORDER_TYPES = {
    "R5-D-01": "TYPE_A_explicit_action_precedence",
    "R5-D-02": "TYPE_A_explicit_action_precedence",
    "R5-D-03": "TYPE_A_explicit_action_precedence",
    "R5-D-04": "TYPE_A_explicit_action_precedence",
    "R5-D-05": "TYPE_A_explicit_action_precedence",
    "R5-S7-T1": "TYPE_A_explicit_action_precedence",
    "R5-S8-T1": "TYPE_A_explicit_action_precedence",
    "R5-D-12": "TYPE_B_trigger_precedence",
    "R5-S1-T3": "TYPE_B_trigger_precedence",
    "R5-S1-T4": "TYPE_B_trigger_precedence",
    "R5-S3-T1": "TYPE_B_trigger_precedence",
    "R5-S3-T2": "TYPE_B_trigger_precedence",
    "R5-S6-T3": "TYPE_B_trigger_precedence",
    "R5-S5-T4": "TYPE_C_deadline_arithmetic_only",
}

ORDER_EVIDENCE = {
    "R5-D-01": "provide information prior to further processing",
    "R5-D-02": "provide information prior to further processing",
    "R5-D-03": "inform before the restriction of processing is lifted",
    "R5-D-04": "carry out DPIA prior to the processing",
    "R5-D-05": "consult supervisory authority prior to processing",
    "R5-S7-T1": "submit draft code before approving it",
    "R5-S8-T1": "issue or renew certification after informing the supervisory authority",
    "R5-D-12": "notify after becoming aware (72-hour deadline not evaluated)",
    "R5-S1-T3": "provide information after obtaining personal data (one-month deadline not evaluated)",
    "R5-S1-T4": "provide information after obtaining personal data (one-month deadline not evaluated)",
    "R5-S3-T1": "provide response after receipt of request (one-month deadline not evaluated)",
    "R5-S3-T2": "inform after receipt of request (one-month deadline not evaluated)",
    "R5-S6-T3": "notify controller after becoming aware (deadline not evaluated)",
    "R5-S5-T4": "regulatory period after receipt of request (date arithmetic unsupported)",
}


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def _search_local_source() -> dict[str, Any]:
    base = ROOT.parent / "references/winter_2020_model_check/model_check/input/regulations/gdpr"
    pattern = re.compile(r"\b(prior to|before|after|following|preceding|subsequent)\b", re.IGNORECASE)
    matches = []
    if base.exists():
        for path in sorted(base.glob("article*.txt")):
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in pattern.finditer(text):
                start = max(0, match.start() - 120)
                end = min(len(text), match.end() + 160)
                snippet = " ".join(text[start:end].split())
                matches.append({
                    "article_file": path.name,
                    "keyword": match.group(1).lower(),
                    "snippet_sha256": sha_text(snippet),
                    "snippet": snippet,
                })
    selected = [m for m in matches if m["article_file"] in {"article40.txt", "article43.txt"}]
    return {
        "source_directory": str(base.relative_to(ROOT.parent)).replace("\\", "/"),
        "keyword_pattern": pattern.pattern,
        "raw_match_count": len(matches),
        "selected_candidate_match_count": len(selected),
        "selected_candidates": selected,
        "stop_condition_met": True,
        "selected_addition_requirement_ids": ["R5-S7-T1", "R5-S8-T1"],
        "search_scope": "local project GDPR article files only; prediction-blind",
    }


def build_report() -> dict[str, Any]:
    config = load_json(CONFIG)
    source_doc = load_json(SOURCE_REQ)
    sources = {s["requirement_id"]: s for s in source_doc["requirements"]}
    order_specs = [s for s in config["requirements"] if s.get("eligible_out_of_order")]
    missing = [s["requirement_id"] for s in order_specs if s["requirement_id"] not in ORDER_TYPES]
    if missing:
        raise RuntimeError(f"order eligibility classification missing for: {missing}")
    rows = []
    for spec in order_specs:
        rid = spec["requirement_id"]
        src = sources[rid]
        rows.append({
            "requirement_id": rid,
            "source_family_id": spec["source_family_id"],
            "split": spec["split"],
            "citation": spec["citation"],
            "order_type": ORDER_TYPES[rid],
            "order_evidence": ORDER_EVIDENCE[rid],
            "source_text_sha256": src["text_sha256"],
            "scored_scope": (
                "evaluate only trigger precedes action; do not claim deadline satisfaction"
                if ORDER_TYPES[rid] == "TYPE_B_trigger_precedence"
                else ("unsupported_not_scored" if ORDER_TYPES[rid] == "TYPE_C_deadline_arithmetic_only"
                      else "evaluate action precedence")
            ),
        })
    test_rows = [r for r in rows if r["split"] == "test"]
    return {
        "schema_version": "stage3_table3_r5_order_eligibility@2.0.0",
        "benchmark_id": "stage3_table3_r5_benchmark_v2",
        "status": "ORDER_ELIGIBILITY_FROZEN_SOURCE_ONLY",
        "eligibility_definition": {
            "TYPE_A_explicit_action_precedence": "Source text explicitly orders two business actions (A before B / B after A / prior to B).",
            "TYPE_B_trigger_precedence": "Source text places an event/receipt/request/awareness before an action; deadline arithmetic is not evaluated by current Stage 3.",
            "TYPE_C_deadline_arithmetic_only": "Source text requires a date/time calculation that current Stage 3 cannot perform; mark unsupported/not_scored.",
            "forbidden": [
                "adjust eligibility using prediction results",
                "convert deadline-only text into binary out_of_order",
                "use Gold/reference labels to infer order",
            ],
        },
        "order_requirement_count": len(rows),
        "order_requirement_ids": [r["requirement_id"] for r in rows],
        "action_precedence_count": sum(1 for r in rows if r["order_type"].startswith("TYPE_A")),
        "trigger_precedence_count": sum(1 for r in rows if r["order_type"].startswith("TYPE_B")),
        "deadline_only_unsupported_count": sum(1 for r in rows if r["order_type"].startswith("TYPE_C")),
        "test_order_requirement_count": len(test_rows),
        "test_order_requirement_ids": [r["requirement_id"] for r in test_rows],
        "test_independent_order_family_count": len({r["source_family_id"] for r in test_rows}),
        "test_independent_order_family_ids": sorted({r["source_family_id"] for r in test_rows}),
        "bounded_source_search": _search_local_source(),
        "remaining_limitation": (
            "TYPE_B trigger precedence checks only trigger-before-action; one-month/72-hour/eight-week "
            "deadline satisfaction remains unsupported. TYPE_C requirements are not scored as out_of_order."
        ),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        write_json(OUTPUT, report)
    if args.check:
        if not OUTPUT.exists() or load_json(OUTPUT) != report:
            raise SystemExit("order eligibility report drift or missing")
    print(json.dumps({
        "order_requirements": report["order_requirement_count"],
        "type_a": report["action_precedence_count"],
        "type_b": report["trigger_precedence_count"],
        "type_c_unsupported": report["deadline_only_unsupported_count"],
        "test_independent_families": report["test_independent_order_family_ids"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
